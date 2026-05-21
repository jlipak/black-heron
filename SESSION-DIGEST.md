# Session Digest — 2026-05-21 (Phase S shipped — third phase this session)

## Quick State
- Project: black-heron
- Directory: /c/Users/DOBY/Desktop/black-heron
- Branch: master
- Last commit: `3b0ccc5` v1.3.2 Phase S: content-hash cache for lens outputs (--no-cache to bypass)
- Prior commits this session: `a1453d5` (Law XV fix) + `bd03f22` (Phase R wrap) + `52705e3` (Phase R code) + `e3d9873` (Phase G wrap) + `96992f5` (Phase G code)
- Uncommitted: just this digest + MEMORY.md NEXT pointer update
- Version: **v1.3.2** (was v1.3.1 mid-session, v1.3.0 earlier, v1.2.0 at session start)
- Tests: **103 passing** (was 81 post-Phase-R, 57 post-Phase-G, 35 at session start)

## What shipped this turn (Phase S)

Re-running BH on an unchanged repo skips the Anthropic API entirely for any lens whose `(ctx, lens, model, rubric_version)` quadruple matches a prior cached entry. Backward-compatible; cache is enabled by default. `--no-cache` reverts to v1.3.1 behavior.

### Code (2 new files, 4 modified)
- `src/black_heron/cache.py` (~250 lines):
  - `compute_ctx_hash(ctx)` — SHA256 over canonical `RepoContext.model_dump(mode="json")` with `sort_keys=True`. Captures file listing + sample contents + entry-points + git log + todo count + external enrichments.
  - `compute_findings_hash(findings)` — order-insensitive hash over `(lens, file, lines, severity, claim[:80])` tuples sorted lexicographically. Used as `blind_spot` prior-hash so first-pass concurrency ordering doesn't invalidate.
  - `compute_cache_key(ctx_hash, lens_name, lens_model, rubric_version, prior_findings_hash="")` — full per-(lens, run-config) key including a `CACHE_FORMAT_VERSION` byte.
  - `read_cache` / `write_cache` — sharded layout `<dir>/<key[:2]>/<key[2:18]>/<lens>.json`, atomic via `.tmp` + `os.replace`. Corruption -> stderr note + miss (Law IV).
  - `run_lens_with_cache(*, ..., lens_call: Callable[[], list])` — closure indirection lets one wrapper handle heterogeneous lens signatures (3-arg first-pass vs 4-arg blind_spot) without refactoring lens modules (Law III).
  - `purge_cache(dir)` — explicit wipe entry point for ops outside the rubric-bump path.
- `cli.py` — `--no-cache` + `--cache-dir` flags. Wrapped all 3 lens call sites (parallel `ThreadPoolExecutor.submit`, sequential fallback loop, blind_spot post-pass) via `run_lens_with_cache`. `ctx_hash` computed once per run; printed (first 12 chars) in the audit header so cross-run continuity is visible.
- `report.py` — `BLACK_HERON_VERSION = "1.3.2"`. New line in Metrics: `**Cache:** N hit / M miss (dir: ...)` or `disabled this run` when bypassed.
- `pyproject.toml` — version + description bump.

### Tests (1 new file, 22 new tests, 81 -> 103)
- `tests/test_cache.py`:
  - 4 ctx-hash tests (stability, sample-content sensitivity, entry-point sensitivity, todo-count sensitivity)
  - 4 cache-key tests (lens_name, model, rubric_version, prior_findings_hash all change the key)
  - 3 findings-hash tests (order-independence, sensitivity to new finding, empty-list determinism)
  - 5 read/write tests (round-trip, miss-returns-None, corrupted JSON -> None, format-version mismatch -> None, malformed findings field -> None)
  - 1 deserialize test (invalid finding skipped without crash)
  - 3 wrapper-behavior tests (miss-then-hit closure-call count, bypass when disabled, write-failure-tolerated)
  - 2 purge tests (removes files, no-op on missing dir)

### Docs (5 files updated)
- `CHANGELOG.md` — full v1.3.2 entry (~50 lines). v1.3.1 retained above.
- `README.md` — v1.3.1 -> v1.3.2 banner with cache mention.
- `OPERATIONS.md` — new "Content-hash cache" section between Phase R and Phase G blocks: usage examples (first run, hit, --no-cache, --cache-dir), key composition formula, miss-cause table, what-it-doesn't-detect notes (FM9, FM10).
- `KNOWN_LIMITATIONS.md` — FM9 (cache covers CLI only, MCP server uncached) + FM10 (cache key doesn't hash lens prompt modules) with v1.3.3/v1.4 candidate solutions.
- `MEMORY.md` — NEXT updated: Phase S marked done; resume command is `cook v1.3 phase O`.

## Verified this turn
- `py -m pytest -q` -> **103 passed in 0.62s** (22 new cache tests, 81 prior all still green)
- `black-heron --help` shows both `--no-cache` and `--cache-dir DIRECTORY` flags with their help text
- `black-heron . --dry-run` runs cleanly (entry-points loaded, dry-run prompt written)
- `py -m pip show black-heron` -> Version: 1.3.2
- Cache miss-then-hit semantics covered by `test_run_lens_with_cache_miss_then_hit` (closure call count assertion: 1 after miss, still 1 after hit)
- Bypass semantics covered by `test_run_lens_with_cache_bypass_when_disabled` (3 calls -> 3 lens invocations, 3 bypassed counter, 0 hits, 0 misses)
- Write-failure tolerance covered by `test_run_lens_with_cache_write_failure_does_not_abort` (mocked OSError; in-memory result still returned)
- No Anthropic API calls made in this turn (Phase S is pure-deterministic per spec)

## Architecture nuances worth carrying forward
- Cache key is `sha256("1|ctx_hash|lens|model|rubric_version|prior_findings_hash")`. The `prior_findings_hash` slot is empty string for first-pass lenses (code_quality / governance / drift) and the sorted-tuple hash of all prior findings for `blind_spot`. This keeps the four lenses in independent cache namespaces while still letting the cache work cleanly across all of them.
- Sharded directory layout (`<key[:2]>/<key[2:18]>/`) keeps directory listings manageable. The full 64-char key isn't used as a dir name because Windows path-length limits + git path-length limits get unhappy fast.
- Closure indirection for `lens_call` is the elegant escape from the heterogeneous-lens-signature problem. The wrapper doesn't need to know how blind_spot differs from code_quality — caller bakes the args into a `lambda: ALL_LENSES[name](ctx, client, tracker)` and the wrapper just invokes when needed. ThreadPoolExecutor-safe because each future has its own closure (`lambda n=name: ...` captures `name` via default-arg).
- `format_version="1"` lives in the on-disk payload AND is part of `compute_cache_key`. Belt-and-suspenders: on a schema bump, both the key changes (new payloads only) and the existing entries fail the format check on read (graceful miss).
- Disk write failure path is deliberately non-fatal. If `~/.black-heron/` is on a read-only volume or the disk is full, the audit still completes and returns the live lens output to the user; the stderr note explains the silent cache miss without aborting useful work (Law IV).
- The MCP server (`mcp_server.py`) was intentionally **not** wired into the cache this phase. The MCP path is typically one-shot from automation contexts; the iteration use case is the CLI. Lifting `run_lens_with_cache` to a shared module both `cli.py` and `mcp_server.py` import is a v1.3.3 candidate (documented FM9).

## Honest gaps for v1.3.3 / v1.4
- **FM9** — MCP server lens calls are uncached. Trivial fix when we get to it (15 minutes).
- **FM10** — Cache key doesn't hash lens prompt module bytes. By design (avoids dev-comment-change invalidation) but creates a quiet-stale-result vector for active lens-prompt development. `--no-cache` is the runtime escape; v1.4 candidate is to add a `--cache-bust-on-lens-edit` mode that hashes the lens .py file's content alongside `lens_model`.
- Cache savings aren't reported in USD. The CacheStats payload only tracks counts (hits/misses/bypassed). Estimating savings requires either (a) per-lens cost tracking from previous runs (not currently persisted across audits) or (b) priced-token estimation from prompt size (uncertain). v1.4 candidate: persist a small `~/.black-heron/calibration.json` `per_lens_avg_cost_usd` map across runs and use it for honest USD-savings estimates (Law XV: only cite numbers we can verify this session).
- Cache invalidation is **manual only**. No TTL. v1.4 candidate: optional `--cache-ttl <hours>` flag.

## Resume next session
**`cook v1.3 phase O`** — GitHub Actions workflow example. Ship a `.github/workflows/black-heron.yml` template that runs the audit on PR + comments findings.json summary back as a PR comment (or uploads SARIF for Code Scanning ingest). Boot reads MEMORY.md NEXT first; this digest second.
