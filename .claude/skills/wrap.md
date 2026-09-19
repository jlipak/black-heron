---
name: wrap
description: Session-end ritual. Commit uncommitted work, update MEMORY.md NEXT list, write fresh SESSION-DIGEST.md, spot-check 3 doc claims against reality. Run when SHIKA says "wrap" or session needs to close cleanly.
---

# Black Heron Wrap-Up

When SHIKA says `wrap`, run this sequence. Goal: leave the next session a clean handoff.

## Step 1: Survey state

```bash
git -C "$BH_ROOT" status --short
git -C "$BH_ROOT" diff --stat
git -C "$BH_ROOT" log --oneline -5
```

Note:
- Uncommitted changes (must be committed before wrap completes)
- Recently committed work (becomes "What Happened" section in DIGEST)

## Step 2: Commit uncommitted work

Per Law XIII — never end a session with uncommitted work that represents real progress.

```bash
# Stage specific files only — NEVER `git add -A`
git -C "$BH_ROOT" add <specific-files>
git -C "$BH_ROOT" commit -m "<one concern, clear subject>"
```

If multiple unrelated concerns: split into multiple commits.

## Step 3: Update MEMORY.md

Specifically:
- Move completed items from NEXT to "What Got Done" (commit-implicit).
- Add 1-3 new NEXT items if this session uncovered them.
- Update "Calibration" section if you ran any audit (cost, FP rate, etc.).
- Update "Active Projects" status line if anything shifted.
- Keep under 200 lines (silent truncation past that — EZEKIEL evidence).

## Step 4: Write SESSION-DIGEST.md

Use this template (verbatim — next session's boot reads this first):

```markdown
# Session Digest — [date] ([brief session theme])

## What Happened This Session
1. [Completed items with actual results/numbers — not aspirational]
2. ...

## Key Decisions
- [Why X was chosen over Y — future-self needs context]

## Current State
- Version: ...
- Phases done: ...
- Cost so far: ...
- Models active: ...

## Gotchas / Warnings
- [Things that could bite the next session]

## NEXT (priority order)
- [ ] First thing next session
- [ ] ...
```

## Step 5: Spot-check 3 doc claims

Pick 3 claims from CLAUDE.md / MEMORY.md / SESSION-DIGEST.md and verify against reality:

| Claim | How to verify |
|---|---|
| "Phase X complete" | `ls` the files Phase X created |
| "v1.1.0" in pyproject.toml | `grep '^version' pyproject.toml` |
| "Cost so far: $X.XX" | Sum from `~/.black-heron/sessions/*.json` if exists |

If any claim is wrong: FIX NOW, same commit. Stale docs are hallucinations (EZEKIEL S30).

## Step 6: Final commit

```bash
git -C "$BH_ROOT" add MEMORY.md SESSION-DIGEST.md
git -C "$BH_ROOT" commit -m "wrap: session-end memory + digest"
```

## Step 7: Optional — invite next session

If a clear "first thing" is queued, mention it in DIGEST's NEXT list explicitly with a short rationale ("Phase J first — it gates Phase K, which we're 1 step from done").

## Cross-References

- `MEMORY.md` — updated here
- `SESSION-DIGEST.md` — written here
- `docs/LAW.md` Laws XIII, XIV, XV — codified in this skill
- `boot.md` skill — inverse, runs at next session start
