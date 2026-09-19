---
name: audit
description: Run a Black Heron audit on a target repository. Args may include path, lens selection, cost cap. Returns a summary of the resulting REPORT.md verdict.
---

# Run Black Heron Audit

When the owner invokes `/audit <path>` or asks "audit X", run this.

## Step 1: Resolve target

- Default target: current working directory.
- Explicit path: use as given.
- Validate it's a directory, not a single file.

## Step 2: Pre-flight check

```bash
# API key reachable?
test -n "$ANTHROPIC_API_KEY" || { echo "ANTHROPIC_API_KEY not set"; exit 1; }

# BH installed?
py -c "from black_heron.cli import audit" || pip install -e "$BH_ROOT"
```

## Step 3: Run the audit

```bash
black-heron <target_path> --out <target>/.bh-audit/
```

Default behavior:
- All 4 lenses (code_quality, governance, drift, blind_spot)
- Models: Opus 4.6 lenses + Opus 4.7 verifier
- Cost cap $2 (from bundled rubric)
- Time cap 300s
- Outputs: REPORT.md + findings.json + findings.sarif

Custom flags worth knowing:
- `--rubric <path>` — custom rubric
- `--lenses code_quality,governance` — subset
- `--budget-mode` — downshift to Sonnet (ONLY if the owner explicitly requests cost reduction)
- `--dry-run` — no API calls; just dump prompt to disk for inspection

## Step 4: Read the report

After audit completes:
1. Open `<target>/.bh-audit/REPORT.md`.
2. Read Summary section (volume-calibrated one-liner).
3. List severity counts (P0 / P1 / P2).
4. Note any flagged P0 findings — those are first to address.

## Step 5: Present to the owner

```
┌─────────────────────────────────────────┐
│  BH Audit — <target name>               │
├─────────────────────────────────────────┤
│  Verified:   N                          │
│    P0: x   P1: y   P2: z                │
│  Rejected:  M (verifier filter)         │
│  Wall:      Ns                          │
│  Cost:      $X.XX                       │
├─────────────────────────────────────────┤
│  Reports at: <target>/.bh-audit/        │
│    REPORT.md / findings.json / .sarif   │
└─────────────────────────────────────────┘

Top finding:
  [P0/P1] [file:lines] [claim]
```

## Step 6: Honest scope statement

Always include in the summary:
- Sample-based context limitation (Law V mitigation, not elimination)
- Cost incurred
- Adversarial verifier ran (Law VI confirmation)

## Common variants

- `audit-quick <path>` → `--lenses code_quality --cost-cap 0.25` (single-lens cheap pass)
- `audit-budget <path>` → `--budget-mode` (Sonnet fallback)
- `audit-strict <path>` → no custom rubric; baseline floors

## Cross-References

- `CLAUDE.md` Validation section — verification commands
- `quality.md` rule — what "done" means for an audit
- `self-audit.md` skill — variant that audits BH itself
