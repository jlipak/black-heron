# Black Heron — Audit Report

> Generated 2026-05-22 09:15 UTC by Black Heron (skill v1.0.0)

**Repository:** `acme-billing-api`
**Files audited:** 14 (primary language: python)
**TODO markers found in source:** 14
**Entry-point files loaded full-content:** 4 (`pyproject.toml`, `src/acme_billing/__init__.py`, `src/acme_billing/main.py`, `rubric.json`)
**Lens model:** claude-opus-4-6
**Verifier model:** claude-opus-4-7 *(distinct from lens model — model differential applied)*

## Summary

This audit surfaced **6 issues** across multiple lenses (1 P0 / 4 P1 / 1 P2). Review priority order; the verifier filtered 2 additional noise candidates upstream.

## Lens raw output

| Lens | Raw findings |
|---|---|
| code_quality | 2 |
| governance | 3 |
| drift | 2 |
| blind_spot | 1 |

**After adversarial verifier:** 6 kept, 2 rejected.
**Verifier reject ratio:** 25.0%

## P0 findings (1)

### P0.1 — ANTHROPIC_API_KEY referenced directly in source without `.env.example` schema documentation

- **Lens:** governance
- **File:** `src/acme_billing/main.py` lines `L18-L22`
- **Confidence:** 0.92

**Evidence:**
```
import os
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]  # fails loud if missing
client = Anthropic(api_key=ANTHROPIC_KEY)
```

**Why it matters:** A new contributor cloning the repo sees the key reference but has no scaffolded `.env.example` to know which env vars are required. First failure happens at runtime, not at clone — friction + accidental commit risk if they hardcode it temporarily.

**Verifier note:** Confirmed via file listing: no `.env.example` in repo. The env var is required at module-load time (line 19), so the failure surface is large. P0 stands — governance gap with concrete operational impact.

## P1 findings (4)

### P1.1 — Duplicate retry logic across two files diverging in backoff policy

- **Lens:** code_quality
- **File:** `src/acme_billing/retry.py` lines `L8-L24` and `src/acme_billing/billing.py` lines `L45-L61`
- **Confidence:** 0.78

**Evidence:**
```
# retry.py
def with_retry(fn, max_attempts=3, backoff=2.0):
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception:
            time.sleep(backoff ** attempt)
```

**Why it matters:** `billing.py` reimplements the same loop with `backoff=1.5` and `max_attempts=5`. Two retry behaviors for the same kind of failure invites silent inconsistency — one code path stops too early under sustained outage, the other holds onto a request too long.

**Verifier note:** Both fragments verified verbatim in the bundle. Severity P1 supported — duplication of a control-flow primitive with diverging defaults is exactly the maintainability erosion the lens flags.

### P1.2 — `rubric.json` has no `version` field

- **Lens:** governance
- **File:** `rubric.json` lines `L1-L8`
- **Confidence:** 0.95

**Evidence:**
```json
{
  "criteria": [
    {"id": "C1", "name": "transaction has merchant id", "severity": "P0"},
    {"id": "C2", "name": "amount in expected range", "severity": "P1"}
  ]
}
```

**Why it matters:** Policy-bearing artifacts must be versioned so any audit decision can be reconstructed against the rubric that produced it. Without `version`, no one can answer "which rubric was in force when this verdict was made?" three months from now.

**Verifier note:** Authoritative section (entry-point full content) confirmed no `version` field. P1 — exactly the rubric-versioning gap the governance lens is calibrated to catch.

### P1.3 — README documents `--debug` flag, not parsed in CLI

- **Lens:** drift
- **File:** `README.md` line `L42` (claim) vs. `src/acme_billing/main.py` lines `L31-L47` (CLI parser, no `--debug` option)
- **Confidence:** 0.83

**Evidence:**
```
README.md L42:  ./acme-billing-api --debug   # verbose mode
main.py L31:    parser.add_argument("--port", type=int, default=8080)
main.py L37:    parser.add_argument("--config", type=Path, default=None)
                # no --debug here or anywhere in this file
```

**Why it matters:** A user copies the README example, the flag is rejected, they assume the docs are stale. Trust in documentation degrades — drift signal exactly as the lens defines.

**Verifier note:** Confirmed via file listing — no other `add_argument` calls exist outside `main.py`. The README claim is observable drift, not roadmap aspiration. Keep.

### P1.4 — PII (customer email) logged at INFO level in observability stream (data × observability)

- **Lens:** blind_spot
- **File:** `src/acme_billing/logs.py` lines `L13-L16`
- **Confidence:** 0.81

**Evidence:**
```python
def log_charge(customer_email: str, amount: float, currency: str):
    logger.info(f"Charged {customer_email}: {amount} {currency}")
```

**Why it matters:** This is exactly the meta-intersection the blind_spot lens is designed for. The data lens audits payload shape; the observability lens audits log levels. Neither single lens flags a PII field flowing into INFO-level logs — but together it's a compliance trigger (GDPR Art. 5, principle of data minimization).

**Verifier note:** Spans (observability × data shape). The lens correctly named both domains. Evidence is verbatim. P1 stands — would be P0 if the audit established that these logs are shipped to a third-party SIEM (no evidence of that here).

## P2 findings (1)

### P2.1 — 14 TODO/FIXME markers across 9 files, 0 paydown commits in last 30 entries

- **Lens:** drift
- **File:** `src/acme_billing/` (multiple, see git log) lines `commits`
- **Confidence:** 0.62

**Evidence:**
```
src/acme_billing/billing.py:23: # TODO: handle currency conversion (Q3)
src/acme_billing/api.py:88:    # FIXME: rate-limit logic is too aggressive
src/acme_billing/auth.py:14:   # TODO: rotate keys quarterly
```

**Why it matters:** TODOs accumulating without corresponding paydown commits indicates the team has stopped pruning intent. Each surviving TODO past 60 days is a slow drift signal — the codebase remembers a future state that may never arrive.

**Verifier note:** TODO count verified (14 across 9 files via grep). No commits in `git log --oneline -30` mention "TODO" closure. P2 — informational, not blocking; teams often accept TODO accumulation as a cost of velocity.

## Rejected findings (transparency)

These were proposed by a lens but rejected by the adversarial verifier.

- *Hardcoded port number `8080` in `main.py`* — rejected: this is a CLI default with `--port` override, not a hardcoded value (lens conflated default-arg with hardcode).
- *Missing CHANGELOG.md* — rejected: opinion-only finding, no evidence of broken semver promise; not in code_quality's scope for v1.0.

---

## Honest scope

This audit was produced by Black Heron — multi-lens repository auditor with adversarial verification.

- Lens prompts: 4 perspectives (code_quality, governance, drift, blind_spot)
- Verifier: adversarial second-pass on a different model checkpoint (claude-opus-4-7 vs. lens claude-opus-4-6 — model differential applied)
- Discipline: 15-rule LAW.md, evidence-presence pre-check, severity confidence floors
- Known limits: lens prompts are tuned against Python and TypeScript codebases. Sample-based context — some findings may miss what's in unread files (mitigated by entry-point full-content loading of `pyproject.toml`, `main.py`, `__init__.py`, `rubric.json`).

For known failure modes see `LAW.md` and the verifier transparency section above.
