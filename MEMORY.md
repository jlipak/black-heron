# Black Heron — Operational Memory

> Volatile state. Changes every session. 200-line hard cap (silent truncation past that).

## NEXT (priority order)

- [ ] **SLEEP** before QURE R3 sutra ujutro. Non-negotiable.
- [ ] QURE clean-staging push to `lipakjosip442-png/qure-compliance` PRIVATE — TOP PRIORITY tomorrow morning.
- [ ] R3 prep: REHEARSAL cold-read, dashboard test, posture.
- [ ] BH v1.2 second commit (current state has uncommitted v1.2 work).
- [ ] BH v1.2 push to `lipakjosip442-png/black-heron` PRIVATE — after QURE, requires `BH_ALLOW_PUSH=1`.
- [ ] BH v1.3 sprint post-R3:
      - Phase G — BH consumes external MCPs (sequential-thinking, playwright, context7, firecrawl)
      - Phase R — baseline drift-over-time mode (`--baseline previous.json`)
      - Phase S — content-hash caching across audits
      - Phase O — GitHub Actions workflow example
      - Phase P — GitHub URL ingest (`black-heron https://github.com/...`)
      - Phase Q — HITL queue for ambiguous findings
- [ ] Self-audit refactor candidates (from v1.1 self-audit findings):
      - Lens duplication helper (3 lens modules share 90% of run() body)
      - Cost tracker preemptive cap check (currently reactive — call that pushes over completes)
      - Evidence verifier boundary handling (cross-file false-positive risk)

## Active Projects

- **Black Heron v1.2** — code-writing + parallel + tests shipped. Uncommitted state in working tree. Local commit `a72d70e` is v1.1 baseline.
- **QURE clean-staging** — awaits push (separate repo, separate session).

## SHIKA Profile

- **Platform:** Windows 11, Git Bash via Claude Code.
- **GitHub:** `lipakjosip442-png` (portfolio, private repos for evaluator-invite review).
- **Models authorized:** Opus 4.6 + Opus 4.7. Sonnet only via `--budget-mode`. Haiku not used.
- **Push protocol:** every push explicit. Local commits routine.
- **Communication:** Plain language. Croatian or English. ALL CAPS = emphasis, not anger. Push back honestly.

## How I Operate

- Read MEMORY.md + SESSION-DIGEST.md at boot. Verify NEXT against actual state.
- One concern per commit. Stage specific files, never `git add -A`.
- Adversarial verifier on every audit. No exceptions.
- Sonnet only via `--budget-mode`. Default is Opus.
- BLOCK-level hooks only (exit 2). WARN-level has 86% violation rate (Ezekiel evidence).
- Self-audit before every v1.x release.
- Suggest-only for code patches in v1.2. Never auto-apply.
- Parallel lens execution by default. `--no-parallel` for debug.

## Infrastructure

- **Python:** 3.14.3 (system). `py -m pip install -e .[dev]` for editable + tests.
- **Anthropic SDK:** 0.103.1
- **Core deps:** anthropic, rich, pydantic v2, click, python-dotenv
- **Dev deps:** pytest, pytest-mock
- **MCP servers available:** sequential-thinking, playwright, context7, firecrawl, ghidra, hetzner (3), magic
- **MCP servers BH plans to consume (Phase G v1.3):** sequential-thinking, playwright, context7, firecrawl
- **gh CLI:** 2.92.0 at `/c/Program Files/GitHub CLI/gh.exe` (logged in as `lipakjosip442-png`)
- **Marp CLI:** 4.4.0 (for QURE deck rendering)

## Quick Reference

- `CLAUDE.md` — identity + constraints + commands
- `LAW.md` — 15 sacred laws, evidence-backed
- `SESSION-DIGEST.md` — last session handoff
- `KNOWN_LIMITATIONS.md` — honest gaps
- `PHILOSOPHY.md` — canopy-feeding metaphor
- `README.md` — public-facing
- `ARCHITECTURE.md` — technical deep dive
- `OPERATIONS.md` — install + run + troubleshoot
- `CHANGELOG.md` — version history (v0.1 → v1.0 → v1.1 → v1.2)
- `CONTRIBUTING.md` — slim contributor guide
- `SELF-AUDIT-LATEST.md` — BH on BH report
- `~/.black-heron/calibration.json` — running aggregate metrics

## Calibration

- Audits run: 1 (self-audit at v1.1)
- Manual-review FP rate post-verifier: 0% on v1.0 QURE run (n=2 small sample) → 7 P1 self-findings at v1.1, 4 fixed in-session
- Average cost per audit: ~$2.89 (v1.1 self-audit, Opus-everywhere)
- Average wall time: ~299s (parallel execution will reduce significantly in next run)
- Verifier reject ratio average: 50% (v1.1 self-audit)
- Tests: 35 passing
