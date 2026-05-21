# Black Heron — Audit Report

> Generated 2026-05-21 15:53 UTC by Black Heron v1.0.0

**Repository:** `C:\Users\DOBY\Desktop\qure-clean-staging`
**Files audited:** 116 (primary language: TypeScript)
**TODO markers found in source:** 0
**Entry-point files loaded full-content:** 3 (poc/qure_compliance/package.json, poc/qure_compliance/tsconfig.json, poc/qure_compliance/src/index.ts)

## Summary

This audit surfaced **2 issues**, no P0. The repo looks healthy; addresses are quality-of-life.

## Metrics

- **Wall time:** 231.74s
- **Total cost:** $0.5347
- **Per-lens cost (USD):**
  - `code_quality`: $0.0974
  - `governance`: $0.1088
  - `drift`: $0.1120
  - `blind_spot`: $0.1154
  - `verifier`: $0.1011
- **Per-lens latency (s):**
  - `code_quality`: 41.6s
  - `governance`: 59.0s
  - `drift`: 56.5s
  - `blind_spot`: 62.3s
- **Rubric version:** `1.0.0` (source: `bundled-default`)

## Lens raw output

| Lens | Raw findings |
|---|---|
| code_quality | 3 |
| governance | 0 |
| drift | 0 |
| blind_spot | 0 |

**After adversarial verifier:** 2 kept, 1 rejected.
**Verifier reject ratio:** 33.3%

## P2 findings (2)

### P2.1 — nextAuditId silently swallows the readdir error with a comment '// ignore — dir didn't exist', but mkdir with recursive:true is called just before it, meaning readdir failure after a successful mkdir indicates a real filesystem error that is masked.

- **Lens:** code_quality
- **File:** `poc/qure_compliance/src/audit/serializer.ts` lines `L77-L90`
- **Confidence:** 0.85

**Evidence:**
```
await mkdir(input.outputDir, { recursive: true });
  let existing: string[] = [];
  try {
    existing = await readdir(input.outputDir);
  } catch {
    // ignore — dir didn't exist
  }
```
**Why it matters:** If readdir fails for any reason other than ENOENT (e.g. permission denied after mkdir), the function silently proceeds with an empty list and generates audit ID -001, potentially overwriting an existing audit file when the subsequent writeAuditJson is called.
**Verifier note:** Real issue but consequence (overwrite) requires writeAuditJson behavior we cannot confirm; downgrading to P2 as defensive coding concern rather than confirmed data-loss bug.

### P2.2 — ModelCall and Trace are imported from '../types.js' but ModelCall is never referenced in the file body.

- **Lens:** code_quality
- **File:** `poc/qure_compliance/src/audit/serializer.ts` lines `L4`
- **Confidence:** 0.80

**Evidence:**
```
import {
  AuditReportSchema,
  type Aggregate,
  type AuditReport,
  type CriterionVerdict,
  type ModelCall,
```
**Why it matters:** Unused imports add noise and can mislead readers into thinking ModelCall is used in audit serialization logic.
**Verifier note:** Low-severity hygiene issue with explicit evidence; uncertainty about hidden usage is acknowledged but P2 is appropriate.

## Rejected findings (transparency)

These were proposed by a lens but rejected by the adversarial verifier.

- *The default vision_model value is hardcoded to 'claude-sonnet-4-6', a non-standard model identifier string that does not match any documented Anthropic model name, creating a silent misconfiguration that will cause all compliance scans to fail at the API call unless the env var overrides it.* — rejected: The finding's own uncertainty admits vision/client.ts was not inspected; 'claude-sonnet-4-6' may be a valid or mapped identifier, and the verifier cannot confirm it is wrong without the client code or an Anthropic model list in the bundle.

---

## Honest scope (v1.0)

Black Heron v1.0 ships with: 4 lenses (code_quality, governance, drift, blind_spot), adversarial Opus verifier with severity confidence floors, evidence-presence pre-check, entry-point full-content loading, versioned rubric, cost + time kill-switches, SARIF output. Honest gaps documented in `KNOWN_LIMITATIONS.md`. See `README.md` for v1.1 roadmap.