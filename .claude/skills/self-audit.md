---
name: self-audit
description: Run Black Heron on its own source. Recursive validation — auditor that audits itself. Result is shipped with the repo under examples/self-audit-<date>/. Apollo-grade governance signal.
---

# Self-Audit

When SHIKA says `self-audit`, or before any v1.x release tag.

## Why

EZEKIEL Rule: a system that demands governance discipline from others must apply it to itself. If Black Heron audits other repos, it must audit BH. Honest reporting (Law) requires shipping the result — including any P0 findings BH catches in itself.

## Procedure

```bash
# Run BH on its own source
black-heron "$BH_ROOT" --out "$BH_ROOT/examples/self-audit-$(date +%Y-%m-%d)/"
```

## Expected output

A clean BH self-audit on a properly maintained v1.x repo should show:
- 0 P0 findings (any P0 in BH itself is a blocker for release)
- ≤2 P1 findings (acceptable maintenance items)
- ≤5 P2 findings (polish items)
- Verifier reject ratio 20-40% (healthy adversarial filter)

If any of those bounds is exceeded:
- P0 ≥ 1: STOP. Address before any release.
- P1 > 2: Triage. Either fix in same session or add to NEXT.
- P2 > 5: Slow-roll cleanup, not blocking.

## What to do with P0 in BH itself

1. Read the finding's evidence verbatim. Confirm or refute manually.
2. If confirmed: this is a real bug. Fix in same session. Commit. Re-run self-audit.
3. If refuted (false positive): document why in `docs/KNOWN_LIMITATIONS.md`. Update lens prompt if pattern recurs.

The goal isn't 0 self-findings forever. The goal is: every finding gets explicitly addressed, recorded, and resolved.

## Showcase commit hygiene

One self-audit folder under `examples/` is committed as the showcase. It's the single most credible artifact a reviewer can read:
- "BH audited BH on date X. Found N issues. Status: clean / Y pending."
- Demonstrates BH eats its own dog food.
- Demonstrates transparency (no hidden findings).

If a self-audit catches a real issue, the next session's first NEXT item is "fix BH self-audit finding from <date>".

## Cross-References

- `audit.md` skill — general audit (this is a specialization)
- `docs/LAW.md` — Law IV (verify before done) + Law VII (theoretical vs observable) apply directly
- `docs/KNOWN_LIMITATIONS.md` — where confirmed-false-positive patterns are documented
- `examples/self-audit-*/` — per-run archives (one is kept as the showcase)
