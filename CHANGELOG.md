# Changelog

All notable changes to Black Heron. SemVer.

## [1.4.0] — 2026-09-19

The "public repo" release. Audit behaviour is unchanged apart from the model defaults; the work is CI, packaging, documentation and cleanup so that a stranger can read, install and trust the repository.

### Added
- `.github/workflows/ci.yml` — ruff, pytest on Python 3.11 and 3.12, and a CLI smoke on every push and pull request. The consumer audit template keeps its file, renamed "Black Heron audit (consumer template)", and installs from `jlipak/black-heron@master`.
- `--budget-mode` — promised in the docs since 1.1.0, never parsed by the CLI. Runs the four lenses on `claude-sonnet-5`; the verifier stays on Opus (Law IX). Every lens `run()` takes an optional `model`.
- `--version`. `black_heron.__version__` reads the package metadata; `report.py` and `mcp_server.py` use it, so the version lives in `pyproject.toml` only.
- `SECURITY.md`, `.editorconfig`, `.github/CODEOWNERS`, a pull-request template, `.github/dependabot.yml` (pip and GitHub Actions, weekly on Monday 07:00 Europe/Zagreb, minor and patch grouped).
- `tests/test_models.py` (6 tests): every default model is priced, Law VIII differential, Law IX defaults, budget mode, `--version`. 103 → 109 tests.
- `docs/README.md` index.

### Changed
- Model defaults: lenses `claude-opus-4-6` → `claude-opus-4-8`, verifier `claude-opus-4-7` → `claude-opus-5`, budget fallback `claude-sonnet-4-6` → `claude-sonnet-5`; the suggest-mode writer and patch reviewer follow. Ids checked against the current Anthropic model list on 2026-09-19.
- Price table re-priced at first-party rates: Opus $5 / $25, Sonnet 5 $2 / $10, Haiku 4.5 $1 / $5 per MTok; cache read 0.1x and cache write 1.25x of input. Unknown ids bill at the dearest tier ($10 / $50).
- Suggest-mode patch reviewer `max_tokens` 512 → 4096: Opus 5 thinks by default and thinking tokens count against the limit.
- `pyproject.toml`: one-line description, SPDX licence, author, URLs, classifiers, keywords, `ruff` in the dev extras, package-data so the bundled JSON ships in wheels, `setuptools>=77`.
- README rewritten: what, who, install and a real example on the first screen, then the pipeline, the two distributions, cost and model policy, limits, roadmap.
- `LAW.md`, `PHILOSOPHY.md`, `OPERATIONS.md` and `KNOWN_LIMITATIONS.md` moved under `docs/`; every reference updated.
- `CLAUDE.md` rewritten for a public repo: constraints, a free Validation block, codebase map, no personal identity section.
- Source passes `ruff check` with rules E, F, I, UP (imports sorted, `datetime.UTC`, `X | None`); the rule set is pinned in `pyproject.toml`.

### Removed
- The two example folders that audited another private repository, and the root `SELF-AUDIT-LATEST.md` (a generated copy). `examples/self-audit-2026-05-21/` stays as the showcase, with the local machine path replaced by a neutral one.
- Client names, the owner's alias and the old GitHub handle from every file in the tree. URLs point at `github.com/jlipak/black-heron`.

### Not verified in this release
- No live audit was run with the new model defaults; the unit suite mocks nothing that touches the API and the pipeline code around the calls is unchanged.

---

## [1.3.3] — 2026-05-22

The "ship-it" release. Phase O ships a copy-paste GitHub Actions workflow template + closes the FM9 gap (cache now also covers the MCP server path, not just the CLI).

### Added — GitHub Actions workflow template
- `.github/workflows/black-heron.yml` — runs on PR + push to main + manual dispatch:
  - Sets up Python 3.11, restores `~/.black-heron/cache` from `actions/cache@v4` (key invalidates on rubric change so the cache stays honest)
  - `pip install` Black Heron from the git ref
  - Runs `black-heron .` with `--cost-cap 2.0 --time-cap 300` defaults appropriate for CI
  - Uploads `audit/findings.sarif` to Code Scanning (`github/codeql-action/upload-sarif@v3`)
  - Uploads `audit/REPORT.md` + `findings.json` + `findings.sarif` as workflow artifacts (30-day retention)
  - Posts a PR comment summary: verified count by severity, top 10 findings, cost, cache hit/miss
- Permissions configured for `contents:read` + `pull-requests:write` + `security-events:write`. No more.
- `secrets.ANTHROPIC_API_KEY` is the only required setup — document this in repo secrets once.

### Fixed — FM9: cache now wraps MCP server lens calls
- `mcp_server.py` `audit_repository` tool: all 3 first-pass lens calls + the blind_spot pass now go through `run_lens_with_cache` (same wrapper as `cli.py`).
- `mcp_server.py` `quick_scan` tool: code_quality call wrapped.
- New tool args: `no_cache: bool` + `cache_dir: str` (both optional, defaults match CLI).
- `metrics.cache` is now populated in the MCP server's output report too.

### Discipline
- Phase O workflow honors Law XI: never pushes anywhere, just reads + writes SARIF/artifacts. Comments on PR but doesn't touch git refs.
- The CI cache (`actions/cache@v4`) is scoped by `runner.os + version + hash(rubric*.json)`. Rubric edit -> fresh cache. Lens-prompt edit without rubric bump -> stale cache (FM10 still applies — use `--no-cache` if you suspect drift).
- v1.3.3 bumps `SERVER_VERSION` in `mcp_server.py` to match `pyproject.toml`.

### Tests (103 -> 103, unchanged)
- No new unit tests for FM9 fix — the cache wrapper itself has 22 tests in `test_cache.py`; FM9 was a wiring change, not a new module.
- The Phase O workflow is artifact-only (YAML), not code — tested by running it against a target repo (not in unit suite).

### Files touched
- New: `.github/workflows/black-heron.yml` (ready-to-copy CI workflow).
- Patched: `mcp_server.py` (+ cache imports, + cache state in `audit_repository` and `quick_scan`, + `metrics.cache` field, + SERVER_VERSION bump), `report.py` (version), `pyproject.toml` (version + description).

---

## [1.3.2] — 2026-05-21

The "content-hash cache" release. Phase S: re-running Black Heron on an unchanged repo (or one where only a non-load-bearing file changed) skips the Anthropic API entirely for any lens whose `(ctx, lens, model, rubric_version)` quadruple matches a prior run. Backward-compatible; cache is enabled by default. `--no-cache` reverts to v1.3.1 behavior (every lens calls the API).

### Added — Deterministic content-hash cache
- `src/black_heron/cache.py`:
  - `compute_ctx_hash(ctx)` — SHA256 over Pydantic-canonical `RepoContext` dump. Captures file listing + sample file contents + entry-point contents + git log + todo count + external enrichments.
  - `compute_cache_key(ctx_hash, lens_name, lens_model, rubric_version, prior_findings_hash="")` — full per-(lens, run-config) key. `prior_findings_hash` is used for `blind_spot` because that lens consumes the first-pass output.
  - `compute_findings_hash(findings)` — order-independent hash of a finding set (sorted by `(lens, file, lines, severity, claim[:80])`), used as the blind-spot prior hash so concurrent first-pass ordering doesn't invalidate the cache.
  - `read_cache(...)` / `write_cache(...)` — atomic on disk via `.tmp` + `os.replace`. Corruption is logged and treated as a miss (Law IV: partial degradation over crash).
  - `run_lens_with_cache(...)` — wrapper used at each lens call site. Closure indirection (`lens_call: Callable[[], list]`) accommodates the heterogeneous lens signatures (blind_spot vs first-pass) without refactoring lens modules (Law III: never rewrite).
  - `purge_cache(cache_dir)` — explicit wipe, exposed for ops who suspect drift outside the version-bump path.
- Cache format carries a `format_version` ("1"); any schema change forces bypass via key mismatch — never silent invalidation.
- Sharded layout: `~/.black-heron/cache/<key[:2]>/<key[2:18]>/<lens_name>.json`.

### Added — CLI flags
- `--no-cache` — bypass cache entirely. Counters track `bypassed` so the report still reflects what happened.
- `--cache-dir <path>` — override default `~/.black-heron/cache/`.
- Default behavior: cache enabled. The audit header prints the resolved cache dir + first 12 chars of `ctx_hash` so cross-run continuity is visible.

### Added — REPORT.md + findings.json surface
- `metrics.cache = {enabled, hits, misses, bypassed, cache_dir}` in `findings.json`.
- REPORT.md "Metrics" gains one line: `- **Cache:** N hit / M miss (dir: ...)` (or "disabled this run" when `--no-cache`).

### Discipline
- Cache is **observable**, deterministic (Law VII). No LLM judges anything.
- Cache key embeds rubric version + lens model id, so any meaningful upstream change forces a fresh API call (Law V — never claim cached when the source moved).
- Disk write failures don't abort the audit; the in-memory result is still surfaced (Law IV).
- Concurrent first-pass lens cache writes are safe — separate files per `(key, lens)` and atomic rename.
- Honest gap: cache covers the CLI path only. `mcp_server.py` lens calls still hit the API every time (v1.3.3 candidate). Documented in `KNOWN_LIMITATIONS.md` (FM9).

### Tests (81 → 103)
- `tests/test_cache.py` (22): ctx-hash stability + sensitivity (sample content, entry-point content, todo count), cache-key separation by (lens, model, rubric version, prior findings), findings-hash order-independence, round-trip persistence, miss/hit/bypass counters via closure-call assertion, format-version mismatch as miss, corrupt JSON as miss, write-failure-tolerated path, purge.

### Files touched
- New: `src/black_heron/cache.py`, `tests/test_cache.py`.
- Patched: `cli.py` (+ 2 flags, + cache init, + wrap 3 lens call sites), `report.py` (+ 1 metrics line, version bump), `pyproject.toml` (version bump + description).

---

## [1.3.1] — 2026-05-21

The "baseline drift" release. Phase R: Black Heron now answers "what changed since the last audit?" deterministically (no LLM). Run an audit, save findings.json, fix some issues, run again with `--baseline previous.json` — REPORT.md gains a "Drift since baseline" section with new / closed / persisting / drifted buckets. Backward-compatible; no flag = identical behavior to v1.3.0.

### Added — Deterministic drift module
- `src/black_heron/drift.py`: `compute_identity_hash(finding)` + `categorize(current, baseline)` + `DriftReport` dataclass
- Identity hash = `sha256(lens | file | normalized_lines | first_8_words(claim))`
  - `normalized_lines` collapses `"L42-L88"` and `"42"` to the same key (start line only)
  - `first_8_words(claim)` lowercases, drops punctuation, keeps first 8 word tokens — robust to LLM rephrasing of the same issue
- 4 buckets: `new` (in current, not in baseline), `closed` (in baseline, not in current), `persisting` (identity match, same severity / confidence / evidence), `drifted` (identity match but at least one of severity / |Δconfidence|>0.2 / evidence substring changed)
- Pure function: no I/O, no Anthropic API. Phase R is **observable** drift, not LLM-judged drift (Law VII)
- `load_baseline_findings()` accepts three shapes: full Black Heron findings.json (`{"verified": [...]}`), generic `{"findings": [...]}`, or a bare list. Malformed or missing baseline produces `available=False` + `skipped_reason` — audit continues (Law IV: partial result is honest, crash is not)

### Added — CLI `--baseline <path>`
- New flag in `cli.py`; defaults to none = identical behavior to v1.3.0
- Path validation is deferred (no `exists=True` on click.Path) so the loader can produce a friendly skip message rather than click exiting with a generic error
- Console summary line after the verifier: `Drift vs baseline [path]: new=N, closed=M, persisting=K, drifted=L`
- On skip, prints `Drift baseline skipped: <reason>` and audit continues

### Added — REPORT.md "Drift since baseline" section + findings.json `baseline_diff` field
- Rendered immediately after the volume-calibrated Summary so the reader sees it before scrolling
- Bucket-count table + per-bucket subsections (`### New findings`, `### Closed findings`, `### Drifted findings`)
- **Compliance debt signal** callout when P0/P1 findings persist — each persisting high-severity finding is one audit cycle of unfixed risk
- **Closed-findings note** flags Apollo-reverse risk: closed without commit evidence may indicate masking rather than fixing
- **Drifted-findings note** flags severity de-escalation without fix-commit as common LLM noise
- `findings.json.baseline_diff` carries the full payload (counts + arrays + each finding's `identity_hash`) for machine consumption
- SARIF is intentionally unchanged — SARIF is a snapshot format, drift is meta

### Tests (57 → 81)
- `tests/test_drift.py` (24 tests):
  - Identity stability across line-format variants, punctuation+case, robust to LLM rephrasing
  - Identity changes when file / lens / claim-prefix differs
  - All 4 buckets exercised (empty baseline = all new, identical = all persisting, removal = closed, severity change = drifted, large confidence change = drifted, small change = persisting, evidence substring = persisting, evidence change = drifted)
  - Defensive loader covers missing path, None path, malformed JSON, unrecognized shape, full findings.json shape, bare list, generic `{"findings":[]}` shape
  - `to_payload()` returns all 4 buckets + counts

### Changed
- `report.BLACK_HERON_VERSION` and `mcp_server.SERVER_VERSION` → `1.3.1`
- `write_report()` gains a `baseline_diff` kwarg (default empty); backward-compatible (mcp_server.py call unchanged)
- CLI panel header now includes `Baseline:` line

### Compatibility
- v1.3.1 is a pure additive at the CLI: `black-heron <repo>` with no new flags behaves identically to v1.3.0
- `findings.json` schema gains the `baseline_diff` top-level field; consumers reading only `verified` / `rejected` / `metrics` are unaffected
- MCP server tools (`audit_repository`, `verify_findings`, `quick_scan`) unchanged

### Honest gaps (deferred to v1.4)
- Identity heuristic is start-line-only — a finding that moves from line 10 to line 110 in the same file with the same first-8-words and same lens will be flagged as `persisting`, not as a real change. The line-shift signal is intentionally hidden because line drift is too noisy in practice; trade-off documented in `KNOWN_LIMITATIONS.md` FM7
- Closed findings aren't auto-correlated with `git log`; the report tells the reader to verify, but doesn't itself fetch the log
- No multi-baseline mode (`--baseline previous-N.json --baseline previous-N-1.json`) — single comparison only

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
- `LAW.md` (15 sacred laws, every one evidence-backed from Apollo / a compliance build / AKIRA collapse)
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
- Project owner identified throughout as Josip Lipak
- LICENSE copyright: "Josip Lipak"

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
- Two reference audits of a client repository under `examples/` (removed from the tree in 1.4.0; the self-audit remains)

## [0.1.0] — 2026-05-21 (initial MVP)

### Added
- 3 lenses (code_quality, governance, drift)
- Single Opus 4.7 verifier
- Sample-based context (30 files × 4KB)
- Markdown + JSON output
- Click CLI
- MIT license
