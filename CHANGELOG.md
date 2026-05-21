# Changelog

All notable changes to Black Heron. SemVer.

## [1.3.0] — 2026-05-21

The "external-MCP enrichment" release. Phase G: Black Heron now consumes 3rd-party MCP servers to enrich its audit context — context7 for live library docs, firecrawl for external URLs, playwright for JS-rendered pages, sequential-thinking for architectural reasoning. Default: OFF; backward-compatible with all v1.2 commands.

### Added — Generic JSON-RPC stdio MCP client
- `src/black_heron/mcp_consumers/client.py` (~230 lines): subprocess-spawning client with initialize/tools-list/tools-call surface
- Sync-blocking I/O with a stdout reader thread (matches BH's non-async architecture)
- Explicit error classes: `McpInitializeError` (binary missing / handshake failure), `McpToolError` (call returned an error or timed out), `McpClientError` (parent)
- Context-manager interface guarantees subprocess + thread cleanup
- Stderr is drained into the BH log stream (`[mcp-stderr]` prefix) so we never silently hide server diagnostics

### Added — MCP config schema + bundled defaults
- `src/black_heron/mcp_consumers/config.py`: `McpServerSpec` + `McpConfig` Pydantic models, versioned via `mcp_config_version`
- `mcp.default.json` ships 4 server entries: context7 (`npx @upstash/context7-mcp`), sequential-thinking (`npx @modelcontextprotocol/server-sequential-thinking`), firecrawl (`npx firecrawl-mcp`), playwright (`npx @playwright/mcp`)
- All 4 ship `enabled_by_default: false` — Phase G is opt-in
- User overrides at `~/.black-heron/mcp.json` are honored when present; `--mcp-config <path>` takes highest precedence

### Added — 4 enricher adapters
- `context7.py` — reads dependencies from `pyproject.toml` / `package.json` / `requirements.txt`, calls `resolve-library-id` → `query-docs`, embeds returned docs as a prompt block. Caps: 5 libs × 8KB.
- `firecrawl.py` — extracts http(s) URLs from README and docs (priority pool) + other files (secondary), skips localhost/private ranges, calls `firecrawl_scrape`. Caps: 3 URLs × 4KB.
- `playwright.py` — same URL extraction, calls `browser_navigate` + `browser_snapshot`. Caps: 1 URL × 4KB (browser spawn is expensive).
- `sequential.py` — one-shot architectural reasoning over repo metadata via `sequentialthinking` tool. Caps: 1 thought × 6KB.
- Shared `_base.py` exposes the `Enricher` protocol and `EnrichmentReport` dataclass.

### Added — Enrichment orchestrator + RepoContext extension
- `src/black_heron/enrichment.py`: `parse_enrich_flag()` + `enrich_context()`
- `RepoContext` gained `external_enrichments: dict[str, str]` field — markdown payloads keyed by enricher name
- `lenses/_common.py` prompt builder appends an "External MCP enrichments" section with a discipline note: lenses still need verbatim in-repo evidence for findings, enrichments are advisory context only
- Per-enricher exception isolation: one enricher failing never aborts the audit; report shows which were skipped + why

### Added — CLI flags `--enrich` + `--mcp-config`
- `--enrich none` (default) — backward compatible; no behavior change
- `--enrich all` — all 4 enrichers
- `--enrich context7,firecrawl` — explicit comma list
- Unknown names error out with exit code 2 + suggestion (no silent typo absorption)
- `--mcp-config <path>` — override config source

### Added — Tests
- `tests/fixtures/fake_mcp_server.py` — minimal stdio MCP server for end-to-end client tests
- `tests/test_mcp_client.py` (5 tests) — real subprocess roundtrip: initialize, tools/list, tools/call echo, error path, missing-binary error
- `tests/test_enrichment.py` (7 tests) — flag parsing, orchestrator dispatch, exception isolation
- `tests/test_mcp_consumers.py` (10 tests) — per-enricher input-extraction (library detection, URL extraction, priority pools, host-skip rules), config loader, JSON+markdown library-id parsing
- Test count: 35 → 57. All passing.

### Changed
- `report.BLACK_HERON_VERSION` bumped to `1.3.0`
- `mcp_server.SERVER_VERSION` bumped to `1.3.0`
- CLI panel header now reads "Black Heron v1.3" and includes `Enrich:` line
- `REPORT.md` "Metrics" section gained an "MCP enrichment" table when enrichers were requested
- `findings.json` `metrics.enrichment` array — per-enricher available/items/bytes/wall/skip-reason

### Compatibility
- v1.3 is backward-compatible at the CLI: `black-heron <repo>` with no new flags behaves identically to v1.2
- Existing rubric JSON files load unchanged (rubric_version `1.0.0` retained — enrichment is orthogonal to the rubric)
- MCP server tools (`audit_repository`, `verify_findings`, `quick_scan`) unchanged in v1.3 — enrichment is CLI-only because BH-from-Claude-Code already has the host's MCP context

### Known gaps (deferred to v1.4)
- Enrichment cost is not reflected in the dollar `--cost-cap` (it's bytes-and-time only — MCP calls don't go through the Anthropic API)
- No retry on transient MCP errors; one failure per item drops that item
- Bundled npx commands haven't been version-pinned (relies on the latest the registry serves)

## [1.2.0] — 2026-05-22 (early morning)

The "code-writer + parallel + tested" release.

### Added — Code-writing suggest mode
- `src/black_heron/code_writer.py` (~170 lines): drafts unified-diff patches for verified P0/P1 findings with confidence ≥ 0.85
- Writer: Opus 4.6 reads full file (capped 20KB), produces diff + rationale + risk assessment
- Patch verifier: Opus 4.7 adversarial review (approves only if patch addresses finding without introducing new issues)
- `SuggestedPatch` Pydantic model added to `_models.py`
- CLI `--mode suggest` flag (default still `audit`)
- `REPORT.md` renders patches inline with diff block + verifier-approval badge
- `findings.json` includes `suggested_patches` array
- **Sacred Law:** suggest-only in v1.2. Never auto-applied.

### Added — Parallel lens execution
- `cli.py` first-pass lenses (code_quality, governance, drift) run in parallel via `ThreadPoolExecutor`
- CLI `--parallel / --no-parallel` flag (default: enabled)
- Wall-time reduction: ≈ max(lens_time) instead of sum
- `blind_spot` remains sequential after first-pass joins (it depends on prior findings)

### Added — Test suite
- `tests/` directory created with `conftest.py`, `test_discovery.py`, `test_evidence_verifier.py`, `test_cost_tracker.py`, `test_rubric.py`
- 35 unit tests covering deterministic logic (no API calls): file discovery, entry-point detection, evidence substring matching, cost math, rubric loading + schema validation
- Pytest config in `pyproject.toml`. `[project.optional-dependencies] dev = ["pytest", "pytest-mock"]`
- Fixtures: `tiny_clean_repo`, `tiny_dirty_repo` for positive/negative path tests
- All 35 tests pass cleanly

### Deferred to v1.3
- Phase G (BH consume external MCPs: sequential-thinking, playwright, context7, firecrawl)
- Phase R (baseline drift mode)
- Phase S (content-hash caching across audits)
- Phase O (GitHub Actions workflow example)
- Phase P (GitHub URL ingest)
- Phase Q (HITL queue for ambiguous findings)
- Code-writing apply mode (requires v1.2 suggest-mode field validation)

## [1.1.0] — 2026-05-21

The "identity-layer" release. Black Heron becomes a real operational agent, not just a CLI script.

### Added — Identity layer
- `CLAUDE.md` (identity + constraints + codebase map + validation commands)
- `LAW.md` (15 sacred laws, every one evidence-backed from Apollo / QURE / AKIRA collapse)
- `MEMORY.md` (operational state with NEXT list, 200-line cap)
- `SESSION-DIGEST.md` (session handoff template)
- `PHILOSOPHY.md` (canopy-feeding metaphor + design principles, from v1.0)

### Added — Behavioral rules
- `.claude/rules/core.md` (workflow + session lifecycle + communication)
- `.claude/rules/quality.md` (verify before done, FP discipline)
- `.claude/rules/security.md` (secrets, push protocol, .env discipline)
- `.claude/rules/python.md` (path-scoped Python style)

### Added — BLOCK-level hooks (5)
- `scripts/hooks/block-git-push.sh` — exit 2 on `git push` (Law XI)
- `scripts/hooks/block-catastrophic.sh` — exit 2 on `rm -rf /`, `dd to /dev/sd*`, fork bomb, power cmds, destructive git on main
- `scripts/hooks/scan-secrets.sh` — exit 2 on `sk-ant-`, `ghp_`, `BEGIN ... KEY`, AWS, Google, Slack patterns
- `scripts/hooks/pre-compact-flush.sh` — save BH state at 85%+ context utilization
- `scripts/hooks/uncommitted-warning.sh` — SessionEnd soft warning
- `.claude/settings.json` — hook registry
- `scripts/install-hooks.sh` — install all hooks into user's Claude Code config

### Added — Skills (5)
- `.claude/skills/boot.md` — session-start ritual
- `.claude/skills/wrap.md` — session-end ritual
- `.claude/skills/audit.md` — invoke audit on target
- `.claude/skills/research-swarm.md` — 5-10 parallel research sub-agents
- `.claude/skills/self-audit.md` — BH audits BH (recursive validation)

### Added — Sub-agents (6)
- `.claude/agents/bh-code-quality.md` (Opus 4.6 + Read/Glob/Grep tools)
- `.claude/agents/bh-governance.md`
- `.claude/agents/bh-drift.md`
- `.claude/agents/bh-blind-spot.md`
- `.claude/agents/bh-verifier.md` (Opus 4.7)
- `.claude/agents/bh-orchestrator.md` (parallel lens dispatch for agentic mode)

### Added — MCP server expose
- `src/black_heron/mcp_server.py` — stdio JSON-RPC server
- 3 tools exposed: `audit_repository`, `verify_findings`, `quick_scan`
- `scripts/install-mcp.sh` — patches `~/.claude.json`

### Added — Memory persistence
- `src/black_heron/session.py` — `SessionRecord` + `write_session()` + `update_calibration()`
- `~/.black-heron/sessions/<ts>.json` — per-run records
- `~/.black-heron/calibration.json` — running aggregate metrics (FP rate, cost averages)
- CLI integration: cli.py writes session record after every audit

### Added — Self-audit
- `scripts/self-audit.sh` — runs BH on its own source
- `SELF-AUDIT-LATEST.md` — committed report of latest self-audit
- Portable Python launcher detection (py / python3 / python with functional test for Windows MS Store stub)

### Added — Documentation
- `ARCHITECTURE.md` — technical deep dive
- `OPERATIONS.md` — install + run + troubleshoot
- `CONTRIBUTING.md` — slim contributor guide

### Changed — Models (flip from v1.0)
- All 4 lenses: `claude-sonnet-4-6` → `claude-opus-4-6`
- Verifier remains `claude-opus-4-7`
- Cost tracker price table reordered: Opus tier first, Sonnet legacy
- `--budget-mode` flag added for explicit Sonnet engagement (default never engages)

### Changed — Observability
- `lenses/_common.py::parse_findings` now logs JSON decode errors + per-finding validation errors to stderr (was silent — Apollo lesson)

### Changed — Lens registry
- `lenses/__init__.py` ALL_LENSES dict explicitly documented as heterogeneous
- New constants `FIRST_PASS_LENSES`, `SECOND_PASS_LENSES` for safer iteration

### Fixed (from self-audit run 1 findings)
- `scripts/self-audit.sh` — removed hardcoded absolute path referencing an unrelated project's .env. Now reads `$BH_ENV_FILE` env var or `$BH_ROOT/.env`.
- `scripts/install-mcp.sh` — Windows-specific `py` launcher replaced with portable detection (py / python3 / python with functional test guard for Windows MS Store stub)
- `scripts/self-audit.sh` — same portability fix
- `lenses/_common.py` — silent exception swallow in `parse_findings` now logs JSON decode + per-finding validation errors to stderr

### Identity
- Project owner identified throughout as SHIKA (Josip Lipak)
- LICENSE copyright: "Josip Lipak (SHIKA)"

## [1.0.0] — 2026-05-21 (earlier same day)

### Added
- 4 lenses (code_quality, governance, drift, blind_spot — blind_spot was the v1.0 net-new addition over v0.1)
- Adversarial Opus verifier with severity confidence floors
- Evidence-presence pre-check (`evidence_verifier.py`) — anti-fabrication, runs before LLM verifier
- Versioned rubric (`rubric.default.json`)
- Entry-point full-content loading in discovery (fixes v0.1 absence-claim FPs)
- Cost + time kill-switches
- 5-minute ephemeral cache on lens + verifier system prompts
- SARIF 2.1.0 output (GitHub Code Scanning compatible)
- Metrics block in REPORT.md (latency, cost, reject ratio)
- Volume-calibrated summary at top of REPORT.md
- `KNOWN_LIMITATIONS.md` — honest self-audit of gaps
- `PHILOSOPHY.md` — canopy-feeding metaphor
- `examples/qure-audit-2026-05-21/` (v0.1 reference) and `examples/qure-audit-v1.0/` (v1.0 reference)

## [0.1.0] — 2026-05-21 (initial MVP)

### Added
- 3 lenses (code_quality, governance, drift)
- Single Opus 4.7 verifier
- Sample-based context (30 files × 4KB)
- Markdown + JSON output
- Click CLI
- MIT license
