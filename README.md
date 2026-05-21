# Black Heron

> Multi-lens, governance-first repository audit agent with an adversarial verifier.
> **v1.0** — 4 lenses, evidence-presence pre-check, versioned rubric, SARIF output.

```
       ___
      ( o>          " spread a wide cover,
   ___// )           let the issues surface under it,
  (    )            then strike with what survives the verifier "
   ====
```

## What it does

Run Black Heron on a local repository. It runs four independent lenses (`code_quality`, `governance`, `drift`, `blind_spot`) and pipes their findings through an adversarial verifier (Opus) that challenges each one. The output is a Markdown report, a structured JSON file, and a SARIF 2.1.0 file (GitHub Code Scanning compatible). No CI integration, no auto-fix, no patch generation — Black Heron is an **audit**, in the legal sense: a snapshot meant to inform a reviewer.

**New in v1.0:**
- 4th lens: `blind_spot` — runs after the first three, hunts meta-intersection issues that single-domain lenses miss
- Entry-point files (`index.ts`, `package.json`, `__init__.py`, `pyproject.toml`, etc.) loaded with full content (10KB cap) for cross-file reasoning
- Evidence-presence pre-check — substring-checks each finding's cited evidence against the input bundle, flags fabricated quotes before the LLM verifier even sees them
- Versioned rubric (`rubric.default.json`) with confidence floors per severity, lens toggles, cost + time kill-switches
- Cost tracker with per-lens accounting + cap enforcement
- 5-minute prompt caching (ephemeral) on lens + verifier system prompts → ~30% cost reduction within a single audit
- SARIF output for GitHub Code Scanning import
- Volume-calibrated summary at the top of REPORT.md
- Metrics block (latency, cost per lens, reject ratio, rubric version)

## Install + run

```bash
git clone <this-repo>
cd black-heron
pip install -e .
cp .env.example .env  # add your ANTHROPIC_API_KEY

black-heron /path/to/some/repo --out audit/
# OR:
python -m black_heron.cli /path/to/some/repo --out audit/
```

Output:

```
audit/
├── REPORT.md         human-readable Markdown report
└── findings.json     structured findings + raw lens counts + rejected list
```

## Example output

Two recursive audits ship in `examples/`:

- [`examples/qure-audit-2026-05-21/`](examples/qure-audit-2026-05-21/) — **v0.1** first run against a separate Qure compliance-pipeline repository. 25 raw findings → 15 verified, 10 rejected by the verifier. **2 of the verified P0 findings were determined to be false positives on manual review** — both stemmed from the same root cause: the lens didn't see the relevant cross-file context in its 30-file sample.

- [`examples/qure-audit-v1.0/`](examples/qure-audit-v1.0/) — **v1.0** re-run on the same repository after the v0.1 → v1.0 upgrades. 3 raw findings → 2 verified, 1 rejected. **0 manual FPs.** The 2 P0 false positives from v0.1 are eliminated (entry-point full-content + authoritative-listing rule). The verifier appropriately rejected the same `vision_model` claim that v0.1 kept at P1 — citing "vision/client.ts not inspected" as the honesty signal.

## Architecture

```
              repo path
                  │
                  ▼
            discovery.py         ── walk files, filter ignored, read up to
                  │                   30 small-file samples, scan TODO/FIXME,
                  ▼                   parse 30 most recent git commits
        ┌─── lenses (Sonnet, parallel-conceptually, sequential in code) ───┐
        │                                                                  │
        │   code_quality   ──┐                                              │
        │   governance     ──┼──→  raw findings (Finding[])                │
        │   drift          ──┘                                              │
        │                                                                  │
        └───────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                    synthesis.py — adversarial verifier (Opus)
                                  │
                          KEEP / REJECT / DOWNGRADE
                                  │
                                  ▼
                      report.py — Markdown + JSON
```

### Lens responsibilities

| Lens | Looks for |
|---|---|
| `code_quality` | Senior-PR-review issues: duplication, dead code, missing input validation, security smells. Patterns visible across multiple files, not single-line nits. |
| `governance` | Versioning of policy artifacts (rubrics/specs), audit trails persisted with model + prompt + raw response, escalation by design (`needs_human` / equivalent), secrets via env vars only, boundary validation, thresholds with citations. |
| `drift` | Promise-vs-delivery: README claims a feature that's not visible in the file listing; commit messages that reference missing artifacts; TODO accumulation without paydown; commented-out code blocks; version-number contradictions. |

### Verifier discipline

The verifier is intentionally adversarial. Its job is not to add findings — its job is to challenge them. For each raw finding it returns one of:

- **KEEP** — well-supported, severity matches the cited evidence, useful to the reader
- **REJECT** — fabricated, overstated, or duplicate
- **DOWNGRADE** — real but the original severity was too high (e.g., P0 → P1)

Findings that survive are emitted in priority order with a one-sentence `verifier_note` explaining the verdict.

### Kill switch

If raw findings exceed 50 P0+P1 entries on a single repo, the run aborts before contacting the verifier. The assumption: a lens prompt has drifted or the repo's context bundle is malformed. Better to abort visibly than ship noise.

## Honest scope (v1.0)

See [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) for full self-audit. Headline gaps:

- **Sample-based context** for non-entry-point files. Lenses see up to 30 sample files at 4KB cap. Entry-points (index, manifest, config) are loaded full-content (10KB cap). Files outside both sets are visible only via the authoritative file listing.
- **Sequential lens execution.** Async parallelism is v1.1.
- **No baseline persistence.** Every run is fresh.
- **No live GitHub URL ingest.** Local path only.
- **No HITL UI** for ambiguous findings. The verifier ships its verdict; no user-in-the-loop override path inside the tool.

## Roadmap

**v1.1 (next):**
- Async parallel lens execution — 3-4× wall-time reduction on multi-lens runs.
- Baseline persistence + drift-over-time mode (`black-heron --baseline previous.json`).
- Content-hash caching across audits.
- 1-hour ephemeral cache TTL (currently 5 min default; 1h is a beta header opt-in).
- Rubric-driven entry-point patterns (custom projects can register their bootstrap files).
- `architecture` lens (dependency graph, layering violations).

**v1.2 (after that):**
- GitHub URL ingest (`black-heron audit https://github.com/<org>/<repo>`).
- `test_coverage` lens (presence-based gap detection + coverage run if available).
- HITL escalation queue: uncertain findings route to a separate output for human review.
- Extended SARIF metadata (partialFingerprints, relatedLocations).

## Cost

A single run on a small-to-medium repo (100–500 files) costs roughly **$0.20–$0.80 in Anthropic API calls** (Sonnet for lenses, Opus for the verifier). No fixed monthly cost. No external service dependencies beyond the Anthropic API.

## Why "Black Heron"

The black heron (*Egretta ardesiaca*) feeds by spreading its wings over the water in a canopy. The shadow attracts small fish seeking shelter. The bird waits, motionless. Then strikes.

Three properties make the analogy fit:

1. **Wide cover.** Three lenses run over the entire repo at once.
2. **Stillness.** The system doesn't try to patch, fix, or interact. It observes.
3. **Precise strike.** The verifier picks the small set of findings worth shipping.

## License

MIT. See `LICENSE`.

Built by Josip Lipak (SHIKA), 2026.
