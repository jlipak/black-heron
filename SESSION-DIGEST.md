# Session Digest — 2026-05-21 (Phase R shipped — second phase this session)

## Quick State
- Project: black-heron
- Directory: /c/Users/DOBY/Desktop/black-heron
- Branch: master
- Last commit: `52705e3` v1.3.1 Phase R: baseline drift mode (--baseline findings.json)
- Prior commit this session: `e3d9873` wrap of Phase G, before that `96992f5` v1.3.0 Phase G
- Uncommitted: just this digest
- Version: **v1.3.1** (was v1.3.0 mid-session, v1.2.0 at session start)
- Tests: **81 passing** (was 57 post-Phase-G, 35 at session start)

## What shipped this turn (Phase R)

Phase R — Black Heron now answers "what changed since the last audit?" deterministically. `--baseline previous.json` flag → set-difference categorization into new/closed/persisting/drifted. NO LLM call (Law VII observable, not theoretical).

### Code (2 new files, 4 modified)
- `src/black_heron/drift.py` (~220 lines) — `compute_identity_hash(finding)`, `categorize(current, baseline) -> DriftReport`, defensive `load_baseline_findings`, top-level `compute_drift_from_file`.
- Identity = `sha256(lens | normalized_lines | first_8_words(claim) | file)`. Line normalization collapses `L42-L88` and `42` to the same key. 8-word claim prefix is robust to LLM rephrasing.
- Drift triggers: severity change, `|Δconf| > 0.2`, evidence non-substring.
- `cli.py` — `--baseline <path>` option (no `exists=True` so loader prints a friendly skip message rather than click's generic error). Panel header includes `Baseline:` line. Console summary post-verifier prints bucket counts or skip reason.
- `report.py` — `write_report()` gained `baseline_diff` kwarg (default safe). `_render_drift_section()` runs right after Summary: bucket table + per-bucket subsections + compliance-debt callout for persisting P0/P1 + Apollo-reverse note on Closed + LLM-noise note on Drifted. `findings.json` gains `baseline_diff` top-level field; SARIF intentionally unchanged.
- `mcp_server.py` — version bump only (write_report call still backward-compatible without baseline_diff kwarg).

### Tests (1 new file, 24 new tests, 57 → 81)
- `tests/test_drift.py`:
  - 6 identity tests (line-format variants, punctuation+case invariance, robust to claim rephrasing past first 8 words, file/lens/claim-prefix sensitivity, missing-field deterministic hash)
  - 10 categorize tests (empty baseline, identical, closed, severity-drift, confidence-jump, tiny-confidence persist, evidence change, evidence superstring persist, identity_hash propagation, all 4 buckets exercised)
  - 7 defensive-loader tests (missing path, None path, malformed JSON, unrecognized shape, full findings.json shape, bare list, generic `{"findings": []}` shape)
  - 1 payload-shape test (counts + all 4 buckets)

### Docs (4 files updated, 1 cumulative)
- `CHANGELOG.md` — full v1.3.1 entry (~75 lines). v1.3.0 retained.
- `README.md` — v1.3 → v1.3.1 banner; new "Audit-over-time with `--baseline`" usage block.
- `OPERATIONS.md` — v1.3 → v1.3.1; per-bucket governance table + identity hash formula + drift triggers.
- `KNOWN_LIMITATIONS.md` — FM7 (start-line-only identity tolerant of line drift) + FM8 (closed not auto-correlated with git log) with v1.4 candidate solutions.
- `MEMORY.md` — NEXT updated: Phase R marked done; resume command is `cook v1.3 phase S`.

## Verified this turn
- `py -m pytest -q` → **81 passed in 0.51s** (24 new drift tests, 57 prior all still green)
- Synthetic E2E smoke: T0 baseline (3 findings) + T1 current (2 of those + 1 new + 1 with severity change) → drift counts `{new: 1, closed: 1, persisting: 1, drifted: 1}` ✓
- `findings.json.baseline_diff` carries full payload incl. `identity_hash` on every finding, `drift_reasons: ['severity:P2->P1']` on the drifted bucket
- `REPORT.md` renders the drift section under Summary with bucket table + Compliance debt signal callout (fires when persisting P0/P1 ≥ 1) + Apollo-reverse note on Closed + LLM-noise note on Drifted
- `black-heron . --dry-run --baseline /tmp/nonexistent.json` → panel header shows `Baseline: ...` correctly; dry-run exits before drift compute (intentional — no current findings to compare)
- `py -m pip show black-heron` → Version: 1.3.1
- No Anthropic API calls made in this turn (Phase R is pure-deterministic per spec)

## Architecture nuances worth carrying forward
- Drift identity is **start-line only** on purpose. Adding an import shifts every subsequent finding's line number; a strict-line identity would mark nearly every persisting finding as `closed` + `new` every audit. Trade-off documented in KNOWN_LIMITATIONS FM7. `--strict-line-identity` is a v1.4 candidate.
- The 8-word claim prefix is the critical knob for LLM-rephrasing robustness. If the verifier or lens systematically rewrites claims in ways that change words 1–8, the heuristic breaks. v1.4 candidate: normalize claim via stopword-strip + Porter stem before windowing.
- Evidence substring rule is one-directional inclusion (a ⊆ b OR b ⊆ a → same). This is intentional: LLMs broaden/narrow evidence quotes constantly; treating that as drift would mislabel persistent issues as drifted.
- `compute_drift_from_file` is the single public entry point — caller passes `(current_findings, baseline_path | None)` and gets a `DriftReport` that knows how to skip gracefully. CLI doesn't need to wrap try/except around the drift call.
- `write_report` signature change is purely additive (`baseline_diff` kwarg with safe default). `mcp_server.py` calls write_report without it; tests for mcp_server still pass.

## Honest gaps for v1.4
- Identity hash uses start-line only; a finding that genuinely moved to a different code region in the same file is silently labeled `persisting`.
- Closed findings aren't auto-correlated with `git log` between baseline timestamp and now. The report tells the reader to verify, but BH doesn't itself fetch the log diff. v1.4 candidate: auto-link closed findings to touching commits.
- No multi-baseline mode (`--baseline N --baseline N-1`). Single comparison only.
- Drift compute runs ONLY on the verifier's `verified` list. A finding that was rejected by the verifier in baseline and rejected again in current is invisible to drift (which is intentional — the audit's official output is `verified`), but it means churn in the rejected pool is also invisible. Add `--include-rejected-in-drift` for transparency? v1.4 candidate.
- `_evidence_changed` strips whitespace then compares — leading-tab-vs-leading-spaces shifts will be treated as different evidence. Probably fine; flag if it shows up in real-repo testing.

## Session totals (both phases this session)
- 2 phases shipped: G (1.2.0 → 1.3.0) and R (1.3.0 → 1.3.1)
- 4 commits this session: `96992f5` (Phase G code) + `e3d9873` (Phase G wrap) + `52705e3` (Phase R code) + `bd03f22` (Phase R wrap, this digest's first revision)
- Test count: 35 → 81 (+46 across both phases)
- 4 new source modules: `enrichment.py`, `drift.py`, `mcp_consumers/` package (8 files)
- 4 new test files: `test_enrichment.py`, `test_mcp_client.py`, `test_mcp_consumers.py`, `test_drift.py`

## Resume next session
**`cook v1.3 phase S`** — content-hash caching across audits. When the same repo is audited twice without code changes, the second run should hit a content cache and return the prior findings.json at near-zero cost. Phase S touches discovery (hash inputs), CLI (`--cache <dir>` flag, default `~/.black-heron/cache/`), and synthesis (skip verifier if all inputs match). Free win for re-runs on unchanged repos.
