# Black Heron — Operational Memory

> Volatile state. Changes every session. 200-line hard cap (silent truncation past that).

## NEXT (priority order)

- [ ] **RESUME COMMAND for next session:** `cook v1.3 phase P` (GitHub URL ingest). Phase O shipped.
- [x] Phase O — GitHub Actions workflow template + FM9 fix (cache covers MCP server too). Shipped 2026-05-22. 103 tests passing. v1.3.3. `.github/workflows/black-heron.yml` ready to copy-paste into target repos.
- [x] Phase S — content-hash cache across audits (`--no-cache` to bypass). Shipped 2026-05-21. 103 tests passing. SHA256 over RepoContext, sharded `~/.black-heron/cache/<key[:2]>/<key[2:18]>/<lens>.json`, atomic write, format_version=1. v1.3.3: cache extended to MCP server (FM9 resolved).
- [x] Phase R — baseline drift-over-time mode (`--baseline previous.json`). Shipped 2026-05-21. 81 tests passing. Set arithmetic on identity hash — no LLM, deterministic.
- [x] Phase G — BH consumes external MCPs (context7, sequential-thinking, firecrawl, playwright). Shipped 2026-05-21. 57 tests passing. Default `--enrich none` so v1.2 commands unchanged.
- [ ] BH v1.3 sprint (active, continues):
      - Phase O — GitHub Actions workflow example ← START HERE next session
      - Phase P — GitHub URL ingest (`black-heron https://github.com/...`)
      - Phase Q — HITL queue for ambiguous findings
- [ ] QURE clean-staging push to `lipakjosip442-png/qure-compliance` PRIVATE — sutra ujutro pre-R3, separate session, separate repo.
- [ ] R3 prep sutra ujutro: REHEARSAL cold-read, dashboard test, posture.
- [ ] BH v1.2 + v1.3 push to `lipakjosip442-png/black-heron` PRIVATE — post-R3, requires `BH_ALLOW_PUSH=1`.
- [ ] Self-audit refactor candidates (from v1.1 self-audit findings):
      - Lens duplication helper (3 lens modules share 90% of run() body)
      - Cost tracker preemptive cap check (currently reactive — call that pushes over completes)
      - Evidence verifier boundary handling (cross-file false-positive risk)

## Active Projects

- **Black Heron v1.3.1** — Phase R baseline drift mode shipped 2026-05-21. `--baseline previous.json` flag, deterministic set-difference categorization on identity hash, 4 buckets (new/closed/persisting/drifted), 24 new drift tests (81 total). Phase G enrichment still in place from earlier in session.
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
- Tests: 81 passing (57 post-Phase-G baseline + 24 drift in Phase R)
