"""Tests for enrichment orchestration: flag parsing + per-enricher dispatch.

We stub out the real enrichers in ALL_ENRICHERS with a recorder enricher to
avoid spawning subprocesses; the JSON-RPC client itself is exercised separately
in test_mcp_client.py.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from black_heron import enrichment
from black_heron.discovery import build_context
from black_heron.enrichment import enrich_context, parse_enrich_flag
from black_heron.mcp_consumers import McpConfig, McpServerSpec
from black_heron.mcp_consumers._base import BaseEnricher, EnrichmentReport


def test_parse_enrich_flag_none() -> None:
    assert parse_enrich_flag(None, ["context7"]) == []
    assert parse_enrich_flag("", ["context7"]) == []
    assert parse_enrich_flag("none", ["context7"]) == []
    assert parse_enrich_flag("off", ["context7"]) == []


def test_parse_enrich_flag_all() -> None:
    avail = ["context7", "firecrawl"]
    assert parse_enrich_flag("all", avail) == avail


def test_parse_enrich_flag_csv() -> None:
    assert parse_enrich_flag("context7,firecrawl", ["context7", "firecrawl", "playwright"]) == [
        "context7",
        "firecrawl",
    ]


def test_parse_enrich_flag_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown enricher"):
        parse_enrich_flag("nope", ["context7"])


class _RecorderEnricher(BaseEnricher):
    name = "recorder"

    def run(self, ctx) -> EnrichmentReport:
        return EnrichmentReport(
            name=self.name,
            available=True,
            items_fetched=1,
            bytes_fetched=42,
            wall_seconds=0.01,
            payload_markdown="## RECORDER\n\ndata",
            queries=["q1"],
        )


def _config_for(name: str) -> McpConfig:
    return McpConfig(
        mcp_config_version="1.0.0",
        servers={name: McpServerSpec(name=name, command=["doesnt-matter"])},
    )


def test_enrich_context_runs_registered_enrichers(tiny_clean_repo: Path) -> None:
    ctx = build_context(tiny_clean_repo)
    with patch.dict(enrichment.ALL_ENRICHERS, {"recorder": _RecorderEnricher}, clear=False):
        enriched, reports = enrich_context(ctx, ["recorder"], _config_for("recorder"))
    assert len(reports) == 1
    assert reports[0].available is True
    assert reports[0].items_fetched == 1
    assert "recorder" in enriched.external_enrichments
    assert "RECORDER" in enriched.external_enrichments["recorder"]


def test_enrich_context_skips_unknown_name(tiny_clean_repo: Path) -> None:
    ctx = build_context(tiny_clean_repo)
    enriched, reports = enrich_context(ctx, ["does-not-exist"], McpConfig())
    assert len(reports) == 1
    assert reports[0].available is False
    assert "no config entry" in (reports[0].skipped_reason or "")
    assert enriched.external_enrichments == {}


def test_enrich_context_handles_enricher_exception(tiny_clean_repo: Path) -> None:
    class _Boom(BaseEnricher):
        name = "boom"

        def run(self, ctx):
            raise RuntimeError("kaboom")

    ctx = build_context(tiny_clean_repo)
    with patch.dict(enrichment.ALL_ENRICHERS, {"boom": _Boom}, clear=False):
        enriched, reports = enrich_context(ctx, ["boom"], _config_for("boom"))
    assert reports[0].available is False
    assert "RuntimeError" in (reports[0].skipped_reason or "")
    assert enriched.external_enrichments == {}
