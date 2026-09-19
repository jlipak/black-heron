"""Tests for individual enricher input-extraction logic + config loader.

These cover the pure-Python parts of context7/firecrawl/playwright/sequential
WITHOUT spawning any subprocess. Subprocess-level integration is covered by
test_mcp_client.py against the fake server.
"""
from __future__ import annotations

import json
import textwrap

from black_heron._models import EntryPoint, RepoContext
from black_heron.mcp_consumers import McpServerSpec, load_mcp_config
from black_heron.mcp_consumers.context7 import (
    Context7Enricher,
    _extract_from_package_json,
    _extract_from_pyproject,
    _extract_from_requirements,
)
from black_heron.mcp_consumers.firecrawl import FirecrawlEnricher
from black_heron.mcp_consumers.playwright import PlaywrightEnricher


def _ctx_from(samples: dict[str, str] | None = None, entry_points: list[EntryPoint] | None = None) -> RepoContext:
    return RepoContext(
        path="/fake",
        file_count=len(samples or {}),
        primary_language="Python",
        file_listing=list((samples or {}).keys()) + [ep.path for ep in (entry_points or [])],
        sample_files=samples or {},
        entry_points=entry_points or [],
        git_log_recent=[],
        todo_count=0,
    )


def test_load_bundled_default_config_has_four_servers() -> None:
    cfg = load_mcp_config(None)
    assert "context7" in cfg.servers
    assert "sequential-thinking" in cfg.servers
    assert "firecrawl" in cfg.servers
    assert "playwright" in cfg.servers
    for s in cfg.servers.values():
        assert isinstance(s, McpServerSpec)
        assert s.command  # non-empty
        assert s.enabled_by_default is False  # Phase G defaults to opt-in


def test_extract_libraries_from_package_json() -> None:
    libs = _extract_from_package_json(json.dumps({
        "name": "x",
        "dependencies": {"react": "^18", "lodash": "^4"},
        "devDependencies": {"vitest": "^1"},
    }))
    assert "react" in libs and "lodash" in libs and "vitest" in libs


def test_extract_libraries_from_pyproject() -> None:
    body = textwrap.dedent('''
        [project]
        name = "x"
        dependencies = [
            "anthropic>=0.40",
            "rich>=13",
            "pydantic>=2",
        ]
    ''')
    libs = _extract_from_pyproject(body)
    assert "anthropic" in libs and "rich" in libs and "pydantic" in libs


def test_extract_libraries_from_requirements_txt() -> None:
    body = "anthropic==0.103.1\n# comment\nclick>=8\n-e .\n"
    libs = _extract_from_requirements(body)
    assert "anthropic" in libs and "click" in libs
    assert "-e" not in libs


def test_context7_extract_libraries_dedupe_and_cap() -> None:
    ep_pyproject = EntryPoint(
        path="pyproject.toml",
        role="package_manifest",
        content='dependencies = [\n  "anthropic>=0.40",\n  "click>=8",\n]\n',
    )
    ep_package = EntryPoint(
        path="package.json",
        role="package_manifest",
        content=json.dumps({"dependencies": {"anthropic": "^1", "react": "^18"}}),
    )
    ctx = _ctx_from(entry_points=[ep_pyproject, ep_package])
    libs = Context7Enricher._extract_libraries(ctx)
    assert "anthropic" in libs
    assert "click" in libs
    assert "react" in libs
    # dedupe: only one anthropic
    lc = [name.lower() for name in libs]
    assert lc.count("anthropic") == 1


def test_firecrawl_extracts_urls_priorities_readme() -> None:
    ep = EntryPoint(
        path="README.md",
        role="module_init",  # role is irrelevant to URL extraction
        content="See https://anthropic.com/docs and https://example.com/x for details.",
    )
    samples = {"src/main.py": "# pls don't pick this URL https://hidden.example/"}
    ctx = _ctx_from(samples=samples, entry_points=[ep])
    spec = McpServerSpec(name="firecrawl", command=["x"], max_items=10)
    enricher = FirecrawlEnricher(spec)
    urls = enricher._extract_urls(ctx)
    assert "https://anthropic.com/docs" in urls
    assert urls.index("https://anthropic.com/docs") < urls.index("https://hidden.example/")


def test_firecrawl_skips_localhost_and_private_ranges() -> None:
    ep = EntryPoint(
        path="README.md",
        role="module_init",
        content="Local: http://localhost:8080 and http://192.168.1.1/admin and https://real.example.com",
    )
    ctx = _ctx_from(entry_points=[ep])
    spec = McpServerSpec(name="firecrawl", command=["x"])
    urls = FirecrawlEnricher(spec)._extract_urls(ctx)
    assert "https://real.example.com" in urls
    assert not any("localhost" in u for u in urls)
    assert not any("192.168" in u for u in urls)


def test_playwright_uses_same_url_pool() -> None:
    ep = EntryPoint(
        path="README.md",
        role="module_init",
        content="App: https://app.example.com — docs: https://docs.example.com",
    )
    ctx = _ctx_from(entry_points=[ep])
    spec = McpServerSpec(name="playwright", command=["x"])
    urls = PlaywrightEnricher(spec)._extract_urls(ctx)
    assert "https://app.example.com" in urls


def test_context7_first_id_parses_json() -> None:
    assert Context7Enricher._first_id('{"libraryID": "facebook/react"}') == "facebook/react"


def test_context7_first_id_parses_markdown_fallback() -> None:
    assert Context7Enricher._first_id("Found: /vercel/next.js docs") == "vercel/next.js"
