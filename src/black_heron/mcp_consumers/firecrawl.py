"""Firecrawl enricher — fetch external URLs referenced in README + docs.

Extracts http(s) URLs from sample_files + entry_points. Prioritizes URLs in
README*, *.md docs, and rubric/policy files (least likely to be code-internal
docs links). Calls `firecrawl_scrape` for each, keeps a markdown excerpt.
"""
from __future__ import annotations

import re
import time
from urllib.parse import urlparse

from .._models import RepoContext
from ._base import BaseEnricher, EnrichmentReport
from .client import McpClientError, McpInitializeError, McpToolError
from .config import McpServerSpec


_URL_RE = re.compile(r"https?://[^\s)>\"'\]]+", re.IGNORECASE)
_PRIORITY_FILE_RE = re.compile(r"(?:^|/)(README|CHANGELOG|CONTRIBUTING|ARCHITECTURE|OPERATIONS|PHILOSOPHY)\.md$", re.IGNORECASE)
_SKIP_HOST_RE = re.compile(r"^(localhost|127\.|0\.0\.0\.0|10\.|192\.168\.|github\.com/lipakjosip442-png/)", re.IGNORECASE)


class FirecrawlEnricher(BaseEnricher):
    name = "firecrawl"

    def __init__(self, spec: McpServerSpec) -> None:
        super().__init__(spec)
        self.max_items = spec.max_items or 3
        self.max_bytes = spec.max_bytes_per_item or 4000

    def run(self, ctx: RepoContext) -> EnrichmentReport:
        t0 = time.time()
        urls = self._extract_urls(ctx)
        if not urls:
            return self._skip("no external URLs found in README / docs / entry-points")

        urls = urls[: self.max_items]
        report = EnrichmentReport(name=self.name, available=True, queries=list(urls))

        try:
            with self._open_client() as client:
                if not self._safe_open(client):
                    return self._skip("MCP initialize failed")
                tool_names = [t.get("name") for t in client.list_tools()]
                scrape_name = self._pick_tool(
                    tool_names,
                    [
                        "firecrawl_scrape",
                        "firecrawl.scrape",
                        "scrape",
                        "fetch",
                    ],
                )
                if scrape_name is None:
                    return self._skip(f"no scrape-style tool exposed (saw {tool_names!r})")

                blocks: list[str] = []
                for url in urls:
                    try:
                        result = client.call_tool(scrape_name, {"url": url, "formats": ["markdown"]})
                        text = client.content_text(result)[: self.max_bytes]
                        if text:
                            report.items_fetched += 1
                            report.bytes_fetched += len(text)
                            blocks.append(f"### URL: {url}\n\n{text}")
                    except (McpToolError, McpClientError) as e:
                        self._log(f"tool error for {url!r}: {e}")
                        continue

                if blocks:
                    report.payload_markdown = (
                        "## External URLs (via firecrawl)\n\n"
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
            report.skipped_reason = "no URLs returned content"
        return report

    @staticmethod
    def _pick_tool(names: list, candidates: list[str]) -> str | None:
        names_set = {n for n in names if isinstance(n, str)}
        for c in candidates:
            if c in names_set:
                return c
        return None

    def _extract_urls(self, ctx: RepoContext) -> list[str]:
        priority_pool: list[str] = []
        other_pool: list[str] = []

        priority_sources: list[tuple[str, str]] = []
        other_sources: list[tuple[str, str]] = []
        for ep in ctx.entry_points:
            if _PRIORITY_FILE_RE.search(ep.path):
                priority_sources.append((ep.path, ep.content))
            else:
                other_sources.append((ep.path, ep.content))
        for path, content in ctx.sample_files.items():
            if _PRIORITY_FILE_RE.search(path):
                priority_sources.append((path, content))
            else:
                other_sources.append((path, content))

        for _, content in priority_sources:
            priority_pool.extend(_URL_RE.findall(content))
        for _, content in other_sources:
            other_pool.extend(_URL_RE.findall(content))

        deduped: list[str] = []
        seen: set[str] = set()
        for url in priority_pool + other_pool:
            url = url.rstrip(".,);]'\"")
            host = urlparse(url).netloc
            if not host or _SKIP_HOST_RE.search(host) or url in seen:
                continue
            seen.add(url)
            deduped.append(url)
        return deduped
