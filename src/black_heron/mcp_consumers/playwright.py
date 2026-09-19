"""Playwright enricher — render a JS-heavy URL via headless browser.

Used sparingly (max 1 by default) because spawning chromium is expensive.
Picks the first interactive-looking URL not already covered by firecrawl —
e.g., dashboards, admin panels, marketing pages that need JS rendering.
"""
from __future__ import annotations

import time
from urllib.parse import urlparse

from .._models import RepoContext
from ._base import BaseEnricher, EnrichmentReport
from .client import McpClientError, McpInitializeError, McpToolError
from .config import McpServerSpec
from .firecrawl import _PRIORITY_FILE_RE, _SKIP_HOST_RE, _URL_RE


class PlaywrightEnricher(BaseEnricher):
    name = "playwright"

    def __init__(self, spec: McpServerSpec) -> None:
        super().__init__(spec)
        self.max_items = spec.max_items or 1
        self.max_bytes = spec.max_bytes_per_item or 4000

    def run(self, ctx: RepoContext) -> EnrichmentReport:
        t0 = time.time()
        urls = self._extract_urls(ctx)
        if not urls:
            return self._skip("no candidate URLs found in repo for browser verification")

        urls = urls[: self.max_items]
        report = EnrichmentReport(name=self.name, available=True, queries=list(urls))

        try:
            with self._open_client() as client:
                if not self._safe_open(client):
                    return self._skip("MCP initialize failed")
                tool_names = [t.get("name") for t in client.list_tools()]
                navigate_name = self._pick_tool(tool_names, ["browser_navigate", "playwright.navigate", "navigate"])
                snapshot_name = self._pick_tool(
                    tool_names,
                    ["browser_snapshot", "browser_take_screenshot", "playwright.snapshot", "snapshot"],
                )
                if navigate_name is None or snapshot_name is None:
                    return self._skip(f"required tools not exposed (saw {tool_names!r})")

                blocks: list[str] = []
                for url in urls:
                    try:
                        client.call_tool(navigate_name, {"url": url})
                        snap = client.call_tool(snapshot_name, {})
                        text = client.content_text(snap)[: self.max_bytes]
                        if text:
                            report.items_fetched += 1
                            report.bytes_fetched += len(text)
                            blocks.append(f"### Browser snapshot: {url}\n\n```\n{text}\n```")
                    except (McpToolError, McpClientError) as e:
                        self._log(f"tool error for {url!r}: {e}")
                        continue

                if blocks:
                    report.payload_markdown = (
                        "## Rendered web entry-points (via playwright)\n\n"
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
            report.skipped_reason = "no page renders returned content"
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
        for ep in ctx.entry_points:
            target = priority_pool if _PRIORITY_FILE_RE.search(ep.path) else other_pool
            target.extend(_URL_RE.findall(ep.content))
        for path, content in ctx.sample_files.items():
            target = priority_pool if _PRIORITY_FILE_RE.search(path) else other_pool
            target.extend(_URL_RE.findall(content))

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
