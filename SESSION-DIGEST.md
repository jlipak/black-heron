# Session Digest — 2026-05-21 (Phase G shipped)

## Quick State
- Project: black-heron
- Directory: /c/Users/DOBY/Desktop/black-heron
- Branch: master
- Last commit: `96992f5` v1.3.0 Phase G: external MCP enrichment (context7 / sequential-thinking / firecrawl / playwright)
- Uncommitted: just this digest
- Version: **v1.3.0** (was v1.2.0)
- Tests: **57 passing** (was 35)

## What shipped this session

Phase G — Black Heron now consumes external MCP servers to enrich audit context. Default `--enrich none`; backward-compatible.

### Code (10 new files, 6 modified)
- `src/black_heron/mcp_consumers/` package — generic JSON-RPC stdio MCP client, config schema, bundled `mcp.default.json`, 4 enricher adapters (context7 / sequential-thinking / firecrawl / playwright), shared `_base.py` protocol + `EnrichmentReport`.
- `src/black_heron/enrichment.py` — orchestrator (`parse_enrich_flag` + `enrich_context`). Per-enricher exception isolation; one failing enricher never aborts the audit.
- `_models.RepoContext.external_enrichments: dict[str, str]` — new field, default empty.
- `lenses/_common.py` — prompt builder appends "External MCP enrichments" section with discipline note (enrichment is advisory, NOT in-repo evidence).
- `cli.py` — `--enrich none|all|csv` + `--mcp-config <path>`. Invalid name exits 2 with available list. Panel header shows `Enrich:`.
- `report.py` + `mcp_server.py` — version bump 1.3.0. REPORT.md "Metrics" gained "MCP enrichment" table. `Honest scope` footer is now version-agnostic.

### Tests (4 new files, 22 new tests, 35 → 57)
- `tests/fixtures/fake_mcp_server.py` — minimal stdio MCP server in pure Python.
- `tests/test_mcp_client.py` (5) — real subprocess roundtrip incl. error path + missing-binary `McpInitializeError`.
- `tests/test_enrichment.py` (7) — flag parsing, orchestrator dispatch, exception isolation.
- `tests/test_mcp_consumers.py` (10) — per-enricher input extraction + config loader + library-id parsing.

### Docs (5 files updated)
- `CHANGELOG.md` — full v1.3.0 entry (~60 lines).
- `README.md` — v1.0 → v1.3 banner; install guide gained `--enrich` examples + `npx` install hints.
- `OPERATIONS.md` — v1.1 → v1.3; new section with per-enricher contribution table + custom mcp-config example.
- `KNOWN_LIMITATIONS.md` — FM6 added (enrichment as fabrication surface) with mitigation.
- `MEMORY.md` — NEXT updated: Phase G marked done; resume command is now `cook v1.3 phase R`.

## Verified this session
- `py -m pytest -q` → **57 passed in 0.46s**
- `black-heron . --dry-run --enrich none` → identical to v1.2 (prompt 79987 chars before / 80141 after counting new mcp_consumers files in the repo, not enrichment payload)
- `black-heron . --dry-run --enrich all` → 4 clear "binary unavailable" skips since `npx` isn't on this Windows box; audit continued; REPORT.md would render the skip table
- `black-heron . --dry-run --enrich nope` → exits 2 with "Unknown enricher(s) ['nope']. Available: [...]"
- `py -m pip show black-heron` → Version: 1.3.0

## Architecture nuances worth carrying forward
- Generic MCP client uses one stdout reader thread + a `queue.Queue` — sync-blocking from the caller, matches BH's non-async style.
- Each enricher resolves the actual tool name at runtime against `tools/list` — handles servers that use `firecrawl_scrape` vs `firecrawl.scrape` vs `scrape` without code changes.
- URL extraction has a priority pool (README / CHANGELOG / CONTRIBUTING / ARCHITECTURE / OPERATIONS / PHILOSOPHY) before falling back to other files; localhost/private ranges (10/192.168) auto-skipped.
- Context7 library detection is manifest-only (pyproject / package.json / requirements.txt) — never reads source samples, per Law V (samples are coverage, not authoritative).
- Enrichment is intentionally absent from `mcp_server.py` (BH-as-MCP server) because when BH is invoked from a Claude Code session, the host already has those MCP servers loaded — calling them again via subprocess would be redundant.

## Honest gaps for v1.4
- MCP-call cost is bytes-and-time only, not part of `--cost-cap` (MCP calls don't go through the Anthropic API).
- No retry on transient MCP errors; one failure per item drops that item.
- Bundled `npx` commands aren't version-pinned (latest from registry).
- Cross-audit caching of context7 docs would be a free win (Phase S touches this anyway).

## Resume next session
**`cook v1.3 phase R`** — baseline drift-over-time mode (`--baseline previous.json`). Reads a prior findings.json, runs a fresh audit, surfaces new/closed/persisting findings as a diff. Boot reads MEMORY.md NEXT first; this digest second.
