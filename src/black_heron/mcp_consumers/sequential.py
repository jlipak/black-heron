"""Sequential-thinking enricher — multi-step reasoning over a structured prompt.

Where the other 3 enrichers add data to the bundle BEFORE lenses run,
sequential-thinking is positioned to feed the VERIFIER with a reasoning
chain about borderline findings. For Phase G we expose a one-shot
"think this through" prompt that produces a markdown block; the verifier
prompt assembly is responsible for choosing whether to include it.

This adapter is intentionally minimal — sequential-thinking servers
expose one tool (typically `sequentialthinking`) and the call is a
single reasoning request.
"""
from __future__ import annotations

import time

from .._models import RepoContext
from ._base import BaseEnricher, EnrichmentReport
from .client import McpClientError, McpInitializeError, McpToolError
from .config import McpServerSpec


_DEFAULT_PROMPT_TEMPLATE = (
    "You are reasoning step-by-step about a repository under audit by Black Heron.\n"
    "Repo: {path}\n"
    "Files: {file_count} | Primary language: {language} | TODOs: {todos}\n"
    "Entry-points: {entry_points}\n\n"
    "Identify the top 3 architectural concerns this repo will face in the next 12 months "
    "based ONLY on the metadata above. Be concrete: name a concern, name the file or pattern "
    "that signals it, name the impact. If the metadata is insufficient, say so."
)


class SequentialThinkingEnricher(BaseEnricher):
    name = "sequential-thinking"

    def __init__(self, spec: McpServerSpec) -> None:
        super().__init__(spec)
        self.max_bytes = spec.max_bytes_per_item or 6000

    def run(self, ctx: RepoContext) -> EnrichmentReport:
        t0 = time.time()
        report = EnrichmentReport(name=self.name, available=True, queries=["meta-architecture-concerns"])

        prompt = _DEFAULT_PROMPT_TEMPLATE.format(
            path=ctx.path,
            file_count=ctx.file_count,
            language=ctx.primary_language,
            todos=ctx.todo_count,
            entry_points=", ".join(ep.path for ep in ctx.entry_points) or "none",
        )

        try:
            with self._open_client() as client:
                if not self._safe_open(client):
                    return self._skip("MCP initialize failed")
                tool_names = [t.get("name") for t in client.list_tools()]
                tool = self._pick_tool(
                    tool_names,
                    ["sequentialthinking", "sequential-thinking", "think", "reason"],
                )
                if tool is None:
                    return self._skip(f"no thinking-style tool exposed (saw {tool_names!r})")

                try:
                    result = client.call_tool(
                        tool,
                        {
                            "thought": prompt,
                            "thoughtNumber": 1,
                            "totalThoughts": 1,
                            "nextThoughtNeeded": False,
                        },
                    )
                    text = client.content_text(result)[: self.max_bytes]
                    if text:
                        report.items_fetched = 1
                        report.bytes_fetched = len(text)
                        report.payload_markdown = (
                            "## Architectural reasoning (via sequential-thinking)\n\n"
                            + text
                        )
                except (McpToolError, McpClientError) as e:
                    self._log(f"tool error: {e}")
        except McpInitializeError as e:
            return self._skip(f"binary unavailable: {e}")
        except McpClientError as e:
            self._log(f"client error: {e}")
            report.available = False
            report.skipped_reason = str(e)

        report.wall_seconds = time.time() - t0
        if report.items_fetched == 0 and report.skipped_reason is None:
            report.skipped_reason = "no reasoning text returned"
        return report

    @staticmethod
    def _pick_tool(names: list, candidates: list[str]) -> str | None:
        names_set = {n for n in names if isinstance(n, str)}
        for c in candidates:
            if c in names_set:
                return c
        return None
