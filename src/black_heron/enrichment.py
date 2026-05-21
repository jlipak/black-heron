"""External-MCP enrichment orchestrator.

Runs zero or more enrichers serially (concurrency would race subprocess
stdout reader threads against shared resources; gain is small for ≤4 servers).
Each enricher's payload markdown is attached to RepoContext.external_enrichments
and rendered into the lens prompt by _common.build_repo_prompt.

A failure in one enricher must not abort the audit — we collect per-enricher
EnrichmentReport objects and emit metrics. The lens prompt only includes
successful, non-empty payloads.
"""
from __future__ import annotations

import sys
import time

from ._models import RepoContext
from .mcp_consumers import ALL_ENRICHERS, McpConfig
from .mcp_consumers._base import EnrichmentReport


def parse_enrich_flag(value: str | None, available: list[str]) -> list[str]:
    """Resolve the --enrich CLI arg into a list of enricher names.

    Accepted forms:
        None / "" / "none" / "off" -> []
        "all"                      -> available
        "context7,firecrawl"       -> ["context7", "firecrawl"]
    Unknown names raise ValueError so the user sees the typo immediately.
    """
    if value is None:
        return []
    v = value.strip().lower()
    if v in {"", "none", "off"}:
        return []
    if v == "all":
        return list(available)
    parts = [p.strip() for p in value.split(",") if p.strip()]
    unknown = [p for p in parts if p not in available]
    if unknown:
        raise ValueError(
            f"Unknown enricher(s) {unknown!r}. Available: {available!r}"
        )
    return parts


def enrich_context(
    ctx: RepoContext,
    enricher_names: list[str],
    config: McpConfig,
) -> tuple[RepoContext, list[EnrichmentReport]]:
    """Run the requested enrichers and return (enriched_ctx, reports).

    The returned RepoContext is a shallow copy with external_enrichments
    populated. Reports always cover every requested enricher, including
    skipped ones (so the audit report can show what was attempted).
    """
    reports: list[EnrichmentReport] = []
    payloads: dict[str, str] = dict(ctx.external_enrichments or {})

    for name in enricher_names:
        cls = ALL_ENRICHERS.get(name)
        spec = config.servers.get(name)
        if cls is None or spec is None:
            reports.append(
                EnrichmentReport(
                    name=name,
                    available=False,
                    skipped_reason=f"no config entry for enricher {name!r}",
                )
            )
            continue
        t0 = time.time()
        try:
            report = cls(spec).run(ctx)
        except Exception as e:
            sys.stderr.write(f"[bh:{name}] unexpected error: {type(e).__name__}: {e}\n")
            report = EnrichmentReport(
                name=name,
                available=False,
                wall_seconds=time.time() - t0,
                skipped_reason=f"{type(e).__name__}: {e}",
            )
        reports.append(report)
        if report.payload_markdown:
            payloads[name] = report.payload_markdown

    enriched = ctx.model_copy(update={"external_enrichments": payloads})
    return enriched, reports
