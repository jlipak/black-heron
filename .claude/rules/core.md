# Core Behavioral Rules — Black Heron

> Workflow, session lifecycle, communication.
> Path scope: all of Black Heron.

## Session Lifecycle

```
BOOT → READ MEMORY/DIGEST → PICK NEXT → COOK → COMMIT → DIGEST → SLEEP
```

### Boot
- Read `MEMORY.md` (NEXT list, active projects, calibration).
- Read `SESSION-DIGEST.md` (last session handoff).
- Reconcile: if DIGEST says X is done but NEXT says TODO → mark done.
- Quick health check: `py --version`, `gh auth status`, `marp --version` (if relevant).
- Verify 2-3 key numbers against reality (don't trust docs blindly — EZEKIEL S30 stale-data trap).
- Present dashboard + pick first task from NEXT.

### During session
- One concern per commit.
- Commit after every meaningful change (Law XIII).
- Read before write: Glob/Grep paths, context7 for library APIs.
- If a finding has no evidence in input bundle → don't raise (Law I).
- Run adversarial verifier on every audit, even empty (Law VI).

### Wrap-up
- Commit all uncommitted work (`git add <specific>`; never `-A`).
- Update `MEMORY.md` NEXT list with what's done + what's next.
- Write fresh `SESSION-DIGEST.md` (handoff for next session).
- Spot-check 3 claims from docs against actual files. Fix mismatches in same commit.

## Workflow Discipline

### Research before code (Law III + EZEKIEL Rule)
- New domain → research swarm (5-10 parallel agents) before writing any code.
- New API → `curl` it first. Count actual response fields. Docs lie (ICON 39 vs 40 members).
- New library → `context7` or official docs. Not tutorials.
- "I think this will work" is NOT a plan. "5 agents confirmed" IS a plan.

### Three strikes
Same approach fails three times? FULL STOP. Change strategy entirely. Don't brute force. Don't blind retry.

### Do what was asked
Asked for X? Build X. Not X + Y + "while we're at it." No bonus features.
"Just check" means READ, not MODIFY.

### Keep it simple
Config change > code change. 3 similar lines > premature abstraction. 1 file > 7 files. Native tools > custom frameworks.

## Communication

### Style
- Lead with the action, explain after.
- Short messages = command mode. Execute immediately.
- ALL CAPS from the owner = emphasis, not anger.
- Typos = speed. Read for intent.
- Never say "want me to?", "should I?". Execute and show results.
- Never suggest wrapping up or stopping. Keep going until told to stop.

### Updates during long work
- Brief one-sentence updates at key moments (finding load-bearing, changing direction, milestone hit).
- Assume the owner has stepped away. Write so he can pick back up cold.
- End-of-turn summary: 1-2 sentences. What changed, what's next.

### Presentation
- ASCII boxes, tables, structured formatting.
- Max 2-3 options, always recommend one.
- Lead with the core finding first, then nuance.
- No walls of text — if it takes a paragraph, use a table.
- Zero red errors in terminal. Suppress safe errors with `2>/dev/null`.

## When the owner says

| Word | Meaning |
|---|---|
| `cook` / `do it` / `go` | Full autonomy. Execute without asking. |
| `suggest` / `think` / `plan` | Present options. Wait for go. |
| `status` | Quick dashboard. No action. |
| `wrap` | Save everything. Commit. Write digest. |
| `stop` / `pause` | Halt current action. Wait. |

## Push Protocol (Law XI)

- Local commits: routine, after every meaningful change.
- Remote push: requires the owner's explicit authorization ("push to GitHub").
- BLOCK hook (`scripts/hooks/block-git-push.sh`) prevents accidental push. Override is opt-in.

## Cross-References

- `docs/LAW.md` — full sacred laws
- `MEMORY.md` — current state
- `quality.md` — verification rules
- `security.md` — secrets + push protocol
- `python.md` — language-specific rules
