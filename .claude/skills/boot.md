---
name: boot
description: Session-start ritual for Black Heron. Reads MEMORY.md + SESSION-DIGEST.md, reconciles state, presents a dashboard, picks first NEXT task. Use when SHIKA says "boot" or "bh" or starts cold.
---

# Black Heron Boot

When SHIKA says `boot` or `bh`, run this sequence verbatim. Goal: pick up from last session without re-explaining.

## Step 1: Read state (parallel)

```
Read MEMORY.md
Read SESSION-DIGEST.md
Read LAW.md (if not in context — refresh on the 15 sacred laws)
```

## Step 2: Quick health check

```bash
# Python + key deps
py --version
py -c "import anthropic; print(anthropic.__version__)"

# Black Heron import
py -c "from black_heron.cli import audit; print('OK')"

# gh auth (we may want to push later this session)
PATH="/c/Program Files/GitHub CLI:$PATH" gh auth status 2>&1 | head -3

# Git state
git -C "$BH_ROOT" status --short
```

## Step 3: Reconcile MEMORY vs reality

For each item in MEMORY.md NEXT:
1. Is it actually pending or already done? (cross-check git log)
2. If done but still in NEXT → mark done in MEMORY.md, same commit.
3. If NEXT says PHASE X done but no commit visible → flag as stale.

For each "Current State" claim in MEMORY.md:
1. Verify cost figure against `~/.black-heron/calibration.json` (if exists).
2. Verify "phases completed" against actual files on disk.

## Step 4: Present dashboard

```
┌─────────────────────────────────────────────────────────┐
│  BLACK HERON — Session [N+1]                            │
├──────────────┬──────────────────────────────────────────┤
│ Version      │ v1.1.0 (in progress)                     │
│ Last session │ [date from SESSION-DIGEST.md]            │
│ Models       │ Opus 4.6 (lens) / Opus 4.7 (verifier)   │
│ Cumulative   │ N audits, $X.XX total spend             │
│ Open tasks   │ [count from MEMORY.md NEXT]              │
├──────────────┴──────────────────────────────────────────┤
│  NEXT (top 3):                                           │
│    1. [first item from MEMORY.md]                        │
│    2. [second item]                                      │
│    3. [third item]                                       │
└─────────────────────────────────────────────────────────┘
```

## Step 5: Wait for SHIKA directive

After dashboard: do NOT auto-execute. Wait for SHIKA to say `cook`, `do X`, `audit Y`, etc.

## Critical: do NOT load source code at boot

Loading source code at boot consumes context without value. Load source code ONLY when you actually start working on it.

Boot is for: identity, state, plan. Not for: code, internals, deep dives.

## Cross-References

- `MEMORY.md` — state read at boot
- `SESSION-DIGEST.md` — previous-session handoff
- `LAW.md` — sacred laws refresher
- `wrap.md` skill — the inverse of boot, run at session end
