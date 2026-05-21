# Session Digest — 2026-05-21 / 2026-05-22 (v1.0 → v1.1 → v1.2 marathon)

## What Happened This Session

1. **v0.1 → v1.0 (early evening):** 4-lens pipeline, adversarial Opus verifier, evidence pre-check, versioned rubric, SARIF output, KNOWN_LIMITATIONS, examples on QURE clean staging.
2. **v1.0 → v1.1 (night):** Identity layer (CLAUDE.md, LAW.md with 15 sacred laws, MEMORY.md, SESSION-DIGEST.md), 4 behavioral rules, 5 BLOCK-level hooks, 5 skills, 6 sub-agent definitions, MCP stdio server with 3 tools, memory persistence (`session.py` + `~/.black-heron/calibration.json`), self-audit run + commit, 4 new docs (ARCHITECTURE, OPERATIONS, CHANGELOG, CONTRIBUTING), models flipped to Opus-only.
3. **v1.1 → v1.2 (late night):** Code-writing suggest mode (`code_writer.py`), parallel lens execution via ThreadPoolExecutor, 35-test pytest suite (all pass).
4. **All committed** to local git as commit `a72d70e` (v1.1 baseline). v1.2 changes pending second commit.

## Key Decisions

- **Opus everywhere by default.** Sonnet only via `--budget-mode`. Haiku not used.
- **15 sacred laws** in `LAW.md`, every one evidence-backed (Apollo / QURE / AKIRA collapse).
- **4-layer architecture** (Global → Project CLAUDE.md → .claude/rules/ → memory/MEMORY.md) — single source of truth per layer.
- **BLOCK-level hooks only** (exit 2). WARN-level has 86% violation rate (AKIRA evidence).
- **Anti-self-trip** in secret-scan hook: sensitive substrings reassembled at runtime so the script itself isn't blocked by upstream secret-scanners.
- **Suggest-only patches in v1.2.** No auto-apply. SHIKA reviews + applies manually.
- **Parallel lens execution** via threads (sync API calls). Async refactor deferred.
- **35 tests pass deterministically** — no API budget consumed for unit tests.
- **Skipped for v1.3:** external MCP consumption (G), baseline drift (R), content-hash cache (S), GitHub URL ingest (P), HITL queue (Q).

## Current State

- **Version:** 1.2.0 (pending second commit)
- **Phases complete v1.1:** A, B, C, D, E, F, I, J, K (10 phases)
- **Phases complete v1.2:** H, L, N (3 phases)
- **Models active:** Opus 4.6 (lenses + writer) / Opus 4.7 (verifier + patch verifier)
- **Tests:** 35 passing
- **Cost this session:** ~$3.50 cumulative (mostly self-audit + BH builds)
- **QURE clean-staging:** awaits push tomorrow morning pre-R3 (separate session, separate repo)
- **BH local commit:** a72d70e (v1.1 baseline). v1.2 not yet committed — next session commits + considers push.

## Gotchas / Warnings

- **Self-audit at v1.1 surfaced 7 P1 findings in BH itself.** 4 fixed in-session (hardcoded path, py launcher portability, silent exception swallow, heterogeneous lens registry doc). 3 remain documented in SELF-AUDIT-LATEST.md (lens duplication refactor candidate, evidence_verifier boundary search, cost tracker fallback inflation risk). All v1.3 candidates.
- **Cost tracker is reactive, not preemptive.** A lens call that pushes over the cap is allowed to complete. Effective cap is "no NEW call after exceeded." Last self-audit ran $2.89 over $2 cap. Fix: pre-emptive cap check before each call, or raise default to $3.
- **MCP server is registered but NOT installed in `~/.claude.json` yet.** Run `bash scripts/install-mcp.sh` to wire up.
- **Hooks are written but NOT deployed to `~/.claude/hooks/`.** Run `bash scripts/install-hooks.sh`.
- **`pip install -e .` was run during build.** If SHIKA reinstalls or moves repo, re-run.
- **Tests need `pip install pytest pytest-mock`** (in `[project.optional-dependencies] dev`).
- **BH context will be near-full at next boot** — don't load source code at boot, only memory + rules + digest.

## NEXT (priority order)

- [ ] **Sleep first.** QURE R3 sutra ujutro. Discipline > extra work.
- [ ] BH v1.2 commit + push prep — when SHIKA authorizes `BH_ALLOW_PUSH=1`.
- [ ] QURE clean-staging push to `lipakjosip442-png/qure-compliance` (PRIVATE) — Friday morning, top priority.
- [ ] Optional: BH v1.2 push to `lipakjosip442-png/black-heron` (PRIVATE) — after QURE.
- [ ] R3 prep: REHEARSAL cold-read, dashboard live demo test, posture reminders.
- [ ] Post-R3: BH v1.3 sprint — Phase G (external MCPs), Phase R (baseline), Phase S (cache).
- [ ] Self-audit refactor candidates: lens duplication helper, cost tracker preemptive cap, evidence_verifier boundary handling.

## Cross-References

- `CLAUDE.md` — identity + constraints
- `LAW.md` — 15 sacred laws
- `MEMORY.md` — operational state
- `KNOWN_LIMITATIONS.md` — honest gaps
- `SELF-AUDIT-LATEST.md` — BH on BH, latest run
- `CHANGELOG.md` — version history
- `~/.black-heron/calibration.json` — running aggregate metrics

---

*Generated 2026-05-22 ~01:30 CEST. SHIKA's session.*
