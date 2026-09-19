# REPORT.md — output format spec

This is the spec for the `REPORT.md` file Black Heron writes at the end of an audit. Follow this structure exactly. Substitute the bracketed fields with values from the actual audit run.

---

```markdown
# Black Heron — Audit Report

> Generated <YYYY-MM-DD HH:MM UTC> by Black Heron (skill v1.0.0)

**Repository:** `<repo_path>`
**Files audited:** <N> (primary language: <language>)
**TODO markers found in source:** <N>
**Entry-point files loaded full-content:** <N> (<list>)
**Lens model:** <lens model id, e.g., claude-opus-4-8>
**Verifier model:** <verifier model id, e.g., claude-opus-5> *(if same as lens, note "same model — quality risk")*

## Summary

<Volume-calibrated lead-in sentence. Pick based on actual mix:>

- 0 findings → "This audit found **no substantive issues** that survived the adversarial verifier. The repo passes this pass."
- ≤5 verified with P0 → "This audit surfaced **N substantive issues**, including **M P0**. Small set — recommend addressing P0 first."
- ≤5 verified no P0 → "This audit surfaced **N issues**, no P0. The repo looks healthy; addresses are quality-of-life."
- 6–15 verified → "This audit surfaced **N issues** across multiple lenses (P0 / P1 / P2). Review priority order; the verifier filtered M additional noise candidates."
- >15 verified → "This audit surfaced **N issues** — significant volume (P0 / P1 / P2) warrants triage. The verifier filtered M noise candidates upstream."

## Lens raw output

| Lens | Raw findings |
|---|---|
| code_quality | <int> |
| governance | <int> |
| drift | <int> |
| blind_spot | <int> |

**After adversarial verifier:** <N> kept, <M> rejected.
**Verifier reject ratio:** <pct>%

## P0 findings (<count>)

### P0.1 — <claim>

- **Lens:** <lens_name>
- **File:** `<path>` lines `<L-range>`
- **Confidence:** <0.00-1.00>

**Evidence:**
```
<verbatim quote>
```
**Why it matters:** <one sentence>
**Verifier note:** <one sentence>

### P0.2 — <claim>
...

## P1 findings (<count>)
...

## P2 findings (<count>)
...

## Rejected findings (transparency)

These were proposed by a lens but rejected by the adversarial verifier.

- *<claim>* — rejected: <reason>
- ...

---

## Honest scope

This audit was produced by Black Heron — multi-lens repository auditor with adversarial verification.

- Lens prompts: 4 perspectives (code_quality, governance, drift, blind_spot)
- Verifier: adversarial second-pass on a different model checkpoint (when available)
- Discipline: 15-rule LAW.md, evidence-presence pre-check, severity confidence floors
- Known limits: lens prompts may have blind spots for languages/frameworks the prompts weren't tuned on. Sample-based context — some findings may miss what's in unread files (mitigated by entry-point full-content loading).

For known failure modes see `LAW.md` and the verifier transparency section above.
```

## Findings JSON spec

The companion `findings.json` carries:

```json
{
  "schema_version": "1.0.0",
  "black_heron_version": "1.0.0-skill",
  "generated_at_utc": "<ISO 8601>",
  "repo": {
    "path": "<repo_path>",
    "file_count": <int>,
    "primary_language": "<lang>",
    "todo_count": <int>,
    "entry_points_loaded": ["<path>", ...]
  },
  "lens_raw_counts": {
    "code_quality": <int>,
    "governance": <int>,
    "drift": <int>,
    "blind_spot": <int>
  },
  "verifier": {
    "verified_count": <int>,
    "rejected_count": <int>,
    "model": "<verifier model id>",
    "same_model_as_lens": <bool>
  },
  "verified": [
    {
      "lens": "...",
      "severity": "P0|P1|P2",
      "file": "...",
      "lines": "L<n>-L<m>",
      "claim": "...",
      "evidence": "...",
      "why_it_matters": "...",
      "confidence": 0.85,
      "verifier_note": "..."
    }
  ],
  "rejected": [
    {"claim": "...", "reason": "..."}
  ]
}
```

## SARIF spec

`findings.sarif` follows SARIF 2.1.0 (https://json.schemastore.org/sarif-2.1.0.json). Minimum structure:

```json
{
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "version": "2.1.0",
  "runs": [{
    "tool": {
      "driver": {
        "name": "Black Heron",
        "version": "1.0.0-skill",
        "informationUri": "https://github.com/jlipak/black-heron",
        "rules": [
          {
            "id": "BH/<lens>/<severity>",
            "name": "<lens>-<severity>",
            "shortDescription": {"text": "<lens> lens, severity <severity>"},
            "defaultConfiguration": {"level": "error|warning|note"}
          }
        ]
      }
    },
    "results": [
      {
        "ruleId": "BH/<lens>/<severity>",
        "level": "error" | "warning" | "note",
        "message": {"text": "<claim>"},
        "locations": [{
          "physicalLocation": {
            "artifactLocation": {"uri": "<file>"},
            "region": {"startLine": <int>}
          }
        }],
        "properties": {
          "confidence": <float>,
          "lens": "<lens>",
          "severity": "P0|P1|P2",
          "why_it_matters": "<sentence>",
          "verifier_note": "<sentence>"
        }
      }
    ]
  }]
}
```

SARIF severity mapping: `P0 → error`, `P1 → warning`, `P2 → note`.
