"""Context7 enricher — fetch live library docs for imports detected in the repo.

Pipeline per library:
  1. resolve-library-id   -> id like "facebook/react"
  2. query-docs           -> markdown chunk

Inputs are extracted from entry-point files (pyproject.toml dependencies,
package.json dependencies, requirements.txt) — NOT from source samples,
because samples are coverage-only per Law V.
"""
from __future__ import annotations

import json
import re
import time

from .._models import RepoContext
from ._base import BaseEnricher, EnrichmentReport
from .client import McpClientError, McpInitializeError, McpToolError
from .config import McpServerSpec

_PYPROJECT_DEP_RE = re.compile(r'^\s*"?([A-Za-z0-9_.\-]+)"?\s*[=<>~!]', re.MULTILINE)
_REQUIREMENTS_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)", re.MULTILINE)


class Context7Enricher(BaseEnricher):
    name = "context7"

    def __init__(self, spec: McpServerSpec) -> None:
        super().__init__(spec)
        self.max_items = spec.max_items or 5
        self.max_bytes = spec.max_bytes_per_item or 8000

    def run(self, ctx: RepoContext) -> EnrichmentReport:
        t0 = time.time()
        libs = self._extract_libraries(ctx)
        if not libs:
            return self._skip("no library declarations found in entry-point manifests")

        libs = libs[: self.max_items]
        report = EnrichmentReport(name=self.name, available=True, queries=list(libs))

        try:
            with self._open_client() as client:
                if not self._safe_open(client):
                    return self._skip("MCP initialize failed")
                tool_names = [t.get("name") for t in client.list_tools()]
                resolve_name = self._pick_tool(tool_names, ["resolve-library-id", "context7.resolve-library-id"])
                query_name = self._pick_tool(tool_names, ["query-docs", "get-library-docs", "context7.query-docs"])
                if resolve_name is None or query_name is None:
                    return self._skip(
                        f"required tools not exposed by server (saw {tool_names!r})"
                    )

                blocks: list[str] = []
                for lib in libs:
                    try:
                        resolved = client.call_tool(resolve_name, {"libraryName": lib})
                        lib_id = self._first_id(client.content_text(resolved)) or lib
                        docs = client.call_tool(query_name, {"context7CompatibleLibraryID": lib_id, "tokens": 2000})
                        text = client.content_text(docs)[: self.max_bytes]
                        if text:
                            report.items_fetched += 1
                            report.bytes_fetched += len(text)
                            blocks.append(f"### Library: `{lib}` (context7 id: `{lib_id}`)\n\n{text}")
                    except (McpToolError, McpClientError) as e:
                        self._log(f"tool error for {lib!r}: {e}")
                        continue

                if blocks:
                    report.payload_markdown = (
                        "## External library docs (via context7)\n\n"
                        + "\n\n---\n\n".join(blocks)
                    )
        except McpInitializeError as e:
            return self._skip(f"binary unavailable: {e}")
        except McpClientError as e:
            self._log(f"client error: {e}")
            report.available = False
            report.skipped_reason = str(e)

        report.wall_seconds = time.time() - t0
        if report.items_fetched == 0 and report.skipped_reason is None:
            report.skipped_reason = "no docs returned"
        return report

    @staticmethod
    def _pick_tool(names: list, candidates: list[str]) -> str | None:
        names_lc = [n.lower() if isinstance(n, str) else "" for n in names]
        for c in candidates:
            if c in names:
                return c
            if c.lower() in names_lc:
                return names[names_lc.index(c.lower())]
        return None

    @staticmethod
    def _first_id(text: str) -> str | None:
        """Many context7 servers return resolve results as JSON, others as markdown.
        We try JSON first, then fall back to a `/owner/repo` pattern in markdown.
        """
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                for k in ("libraryID", "id", "context7CompatibleLibraryID"):
                    if isinstance(data.get(k), str):
                        return data[k]
                results = data.get("results")
                if isinstance(results, list) and results:
                    first = results[0]
                    if isinstance(first, dict):
                        for k in ("libraryID", "id"):
                            if isinstance(first.get(k), str):
                                return first[k]
        except (json.JSONDecodeError, TypeError):
            pass
        m = re.search(r"\b(?:context7CompatibleLibraryID|library[_\- ]?id)\b[^\w]*([A-Za-z0-9_./@\-]+)", text)
        if m:
            return m.group(1)
        m = re.search(r"\b(?:`)?(/?[a-z0-9_\-]+/[a-z0-9_\-.]+)`?", text)
        if m:
            return m.group(1).lstrip("/")
        return None

    @staticmethod
    def _extract_libraries(ctx: RepoContext) -> list[str]:
        libs: list[str] = []
        for ep in ctx.entry_points:
            name = ep.path.lower().split("/")[-1]
            if name == "package.json":
                libs.extend(_extract_from_package_json(ep.content))
            elif name == "pyproject.toml":
                libs.extend(_extract_from_pyproject(ep.content))
            elif name == "requirements.txt":
                libs.extend(_extract_from_requirements(ep.content))
        deduped: list[str] = []
        seen: set[str] = set()
        for lib in libs:
            lib_norm = lib.strip().lower()
            if not lib_norm or lib_norm in seen:
                continue
            seen.add(lib_norm)
            deduped.append(lib.strip())
        return deduped


def _extract_from_package_json(content: str) -> list[str]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    out: list[str] = []
    for key in ("dependencies", "peerDependencies", "devDependencies"):
        d = data.get(key) or {}
        if isinstance(d, dict):
            out.extend(name for name in d.keys() if isinstance(name, str))
    return out


def _extract_from_pyproject(content: str) -> list[str]:
    in_deps = False
    out: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("dependencies"):
            in_deps = True
            continue
        if in_deps and stripped.startswith("]"):
            break
        if in_deps:
            m = re.match(r'^\s*"([A-Za-z0-9_.\-]+)', stripped)
            if m:
                out.append(m.group(1))
    return out


def _extract_from_requirements(content: str) -> list[str]:
    out: list[str] = []
    for line in content.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("-"):
            continue
        m = _REQUIREMENTS_RE.match(s)
        if m:
            out.append(m.group(1))
    return out
