# Sample audit — what `/bh` produces

This folder contains a **synthetic** audit run on a hypothetical project (`acme-billing-api` — a small FastAPI service) so you can see the output shape before running `/bh` on your own code.

The repo being "audited" doesn't exist on disk in this skill repository. The findings are illustrative — they were composed to demonstrate the format, severity mix, and verifier transparency, not to claim that BH always produces this exact output for a real project.

## What's in here

- `REPORT.md` — the human-readable Markdown deliverable
- `findings.json` — the machine-readable JSON for downstream tooling
- `findings.sarif` — SARIF 2.1.0 for GitHub Code Scanning ingest

## Hypothetical project under audit

```
acme-billing-api/                 # FastAPI service, ~15 source files
├── README.md
├── pyproject.toml                # version 0.4.0
├── src/acme_billing/
│   ├── __init__.py
│   ├── main.py
│   ├── api.py
│   ├── retry.py
│   ├── billing.py
│   ├── auth.py
│   ├── logs.py
│   └── models.py
├── tests/
│   ├── test_api.py
│   └── test_billing.py
└── rubric.json                   # billing rules, no version field
```

Findings represent issues a senior engineer would surface across the four lenses (code_quality, governance, drift, blind_spot) cross-checked by the adversarial verifier.

## What to look at first

1. Open `REPORT.md` — start at the **Summary** line (volume-calibrated), then read P0 → P1 → P2 in order.
2. Scroll to the **"Rejected findings (transparency)"** section — what the verifier filtered is data too.
3. Open `findings.json` to see the machine schema.
4. Open `findings.sarif` to see the GitHub Code Scanning shape.

## Reproducing in your own project

```bash
# In your project root, with skill installed at .claude/skills/bh/:
/bh
```

Outputs land in `./audit/`.
