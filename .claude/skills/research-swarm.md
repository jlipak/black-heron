---
name: research-swarm
description: Dispatch 5-10 parallel research sub-agents on a new domain before writing code. Mandatory for new APIs, libraries, regulatory areas, or strategies. EZEKIEL Rule — "I think this will work" is NOT a plan; "5 agents confirmed" IS a plan.
---

# Research Swarm

Use BEFORE writing the first line of code on any new domain. Non-negotiable per Law (Research Before Code, derived from EZEKIEL).

## When to invoke

✓ New API → need to know actual response shape (docs lie — ICON 39 vs 40 members)
✓ New library → need actual function signatures, not tutorials
✓ New regulatory area → multiple sources required for credibility
✓ Strategy proposal → must be cross-checked across multiple angles
✓ Competitive intelligence → 8-10 sources minimum

✗ Reading a known file (use `Read`)
✗ Searching for a pattern in known code (use `Grep`)
✗ Quick fact lookup (use `WebFetch` directly)

## How to dispatch

Use the Agent tool. Send multiple Agent calls in a SINGLE message (true parallelism).

```python
# Conceptual — actual invocation depends on the Claude Code session
agents = [
    Agent(subagent_type="general-purpose", description="...", prompt="Research X. Return structured report."),
    Agent(subagent_type="researcher",     description="...", prompt="..."),
    # ...
]
# Submit all in one message
```

Each agent gets:
1. Specific focused question (not "research X" — "what is the actual response shape of API X's /v1/foo endpoint?")
2. Output format requirement (bullet points + sources + confidence)
3. Constraint: "Do NOT modify any files. Research only."

## Required output structure

Every agent returns:
```markdown
# Agent [N] — [topic]

## TL;DR
[1-2 sentence finding]

## Key findings (with sources)
- [Finding 1] [SOURCE: url] [CONFIDENCE: HIGH/MED/LOW]
- [Finding 2] ...

## Numbers (with confidence)
- [Stat] [SOURCE] [HIGH/MED/LOW]

## Gotchas / pitfalls
- [Hard-learned pitfall]

## Recommendation
[What to do with this information]
```

## Synthesis (after agents complete)

1. Aggregate into `memory/{topic}-intel.md`.
2. Preserve ALL data points — don't summarize away details.
3. Cross-check: do agents agree? If they disagree, surface the disagreement explicitly.
4. Note confidence: each major claim tagged HIGH/MED/LOW.

## Anti-patterns

- ✗ "Just one agent, it'll be enough" — single agent has Apollo-grade FP rate
- ✗ Skipping the synthesis step — agents' outputs decay if not aggregated
- ✗ Trusting docs without curl verification (ICON S23 evidence)
- ✗ "I'll do the research while I code" — no. Research first, code after.

## Cost discipline

Research swarms can spend $1-3 per swarm depending on depth. Budget accordingly:
- Quick research (5 agents, narrow): ~$0.50
- Deep research (10 agents, broad): ~$3.00
- Cap cost at the start, don't let it run away.

## Cross-References

- `core.md` rule — Research Before Code is non-negotiable
- `audit.md` skill — different purpose, sometimes invoked alongside (audit current; then research what to build next)
