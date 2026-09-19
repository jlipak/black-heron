# Black Heron

[![CI](https://github.com/jlipak/black-heron/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/jlipak/black-heron/actions/workflows/ci.yml) ![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue) [![MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE) ![v1.4.0](https://img.shields.io/badge/release-v1.4.0-black)

Black Heron audits a local repository with four independent Claude lenses and an adversarial verifier that tries to reject what they found, then writes a Markdown report, a JSON file and a SARIF 2.1.0 file for GitHub Code Scanning.

It is for maintainers and reviewers who want a second opinion on a codebase: code quality, governance, drift between docs and code, and the blind spots in between. Every finding must quote the repo verbatim, rejected findings stay in the report, and the cost is printed at the end.

## Install and run

```bash
git clone https://github.com/jlipak/black-heron.git && cd black-heron
python -m venv .venv && .venv/Scripts/python -m pip install -e .   # Linux/macOS: .venv/bin/python
cp .env.example .env                                                # then put your ANTHROPIC_API_KEY in it
.venv/Scripts/black-heron /path/to/repo --out audit/                # --help lists every flag
```

## Example

From [`examples/self-audit-2026-05-21/REPORT.md`](examples/self-audit-2026-05-21/REPORT.md), Black Heron v1.0 run on its own source (57 files):

> This audit surfaced **7 issues** across multiple lenses (0 P0 / 5 P1 / 2 P2). Review priority order; the verifier filtered 7 additional noise candidates.
>
> **P1.1 — The run functions in code_quality.py, governance.py, and drift.py are near-identical**, differing only in the SYSTEM prompt string.
> Lens: `code_quality` · File: `src/black_heron/lenses/code_quality.py` lines `L1-L68` · Confidence: 0.95
> *Verifier note:* Evidence supports the duplication claim and the maintenance burden is concrete.
>
> **Rejected:** *No `.env.example` file with placeholder values is committed to the repository.* — rejected: absence claim with no verification that the file listing was inspected.

## How it works

```
repo path ─► discovery ─► code_quality ─┐
              (file listing,  governance   ├─► blind_spot ─► evidence pre-check ─► adversarial verifier ─► REPORT.md
               30 samples,    drift      ─┘   (runs last)    (verbatim quote      (KEEP / REJECT /         findings.json
               entry-points,                                  must exist in         DOWNGRADE)              findings.sarif
               git log)                                       the bundle)
```

1. **Discovery** walks the repo, loads entry-point files in full and up to 30 small samples, reads the last 30 commits and counts TODOs. No LLM.
2. **Three first-pass lenses** run in parallel and return findings as JSON: `code_quality` (what a senior reviewer flags), `governance` (versioned policy, audit trails, secrets via env, escalation paths) and `drift` (README promises vs. the file listing, commit messages vs. artefacts, TODO accumulation).
3. **`blind_spot`** runs last with the other findings in its prompt and looks for issues at the intersection of two domains (PII in logs, secrets in commit messages, a documented flag no code parses).
4. **Evidence pre-check** substring-matches every `evidence` field against the input bundle. A miss is a strong prior for rejection.
5. **The verifier** runs on a different model than the lenses and returns KEEP, REJECT or DOWNGRADE with a one-sentence note for each finding. It also enforces confidence floors per severity (P0 ≥ 0.85, P1 ≥ 0.70, P2 ≥ 0.50) from the bundled rubric.
6. **Report** writes `REPORT.md` (summary, metrics, findings, rejected list), `findings.json` and `findings.sarif`.

Two deterministic extras need no LLM: `--baseline previous/findings.json` diffs this run against an earlier one (new / closed / persisting / drifted), and a content-hash cache under `~/.black-heron/cache/` skips the API for any lens whose input did not change (`--no-cache` to bypass).

More flags: `--lenses`, `--rubric custom.json`, `--cost-cap`, `--time-cap`, `--mode suggest` (draft patches for verified P0/P1, never applied), `--enrich context7,firecrawl,playwright,sequential-thinking` (optional MCP enrichment), `--dry-run` (writes the prompt, calls nothing). `black-heron --help` lists them all.

## Two distributions

| | Python CLI (this repository) | Claude Code skill ([`skill/`](skill/)) |
|---|---|---|
| Form | pip package, CLI, stdio MCP server (`scripts/install-mcp.sh`) | Markdown only: prompts Claude Code reads |
| Install | `pip install -e .` | copy `skill/` into `.claude/skills/` |
| Output | Deterministic JSON and SARIF shape, content-hash cache, baseline drift | Report in the chat, no cache, no drift |
| Tests | 109 pytest tests, CI on 3.11 and 3.12 | none (the logic is in the prompts) |
| Best for | CI, audit over time, Code Scanning | quick audits, prompt iteration |

Both use the same four lens prompts, the same `docs/LAW.md` and the same verifier discipline.

## Cost and model policy

| Role | Model | Price per MTok (input / output) |
|---|---|---|
| Four lenses | `claude-opus-4-8` | $5 / $25 |
| Verifier | `claude-opus-5` | $5 / $25 |
| Lenses with `--budget-mode` | `claude-sonnet-5` | $2 / $10 |

The verifier always runs on a different checkpoint than the lenses so that they do not share blind spots. Sonnet is never used unless you pass `--budget-mode`, and the verifier stays on Opus even then.

How to cap spend:

- `--cost-cap 1.0` aborts before the next lens once the tracked cost reaches $1 (default $2 from the rubric); `--time-cap 300` does the same for wall time.
- The cache means re-running on an unchanged repo costs nothing. `--dry-run` writes the prompt bundle and makes no API call.
- The tracker prices unknown model ids at the dearest tier, so a typo never under-reports.

The showcase run above recorded $2.89 with the v1.0 price table, which billed Opus at $15 / $75; at the $5 / $25 rate the tracker uses now the same token volume comes to about $0.96. No run has been made with the 1.4.0 defaults yet, so treat that as an estimate.

## Limits

See [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) for the full list. The headline gaps:

- Lenses see a sample (up to 30 files at 4 KB) plus entry points in full; anything else is visible only through the file listing.
- Local paths only; no GitHub URL ingest yet.
- Findings are LLM judgments that survived a second LLM. The verifier lowers the false-positive rate, it does not make it zero. Read the evidence before acting.
- No auto-fix: `--mode suggest` drafts patches and never applies them.

## Roadmap

- GitHub URL ingest (`black-heron https://github.com/<org>/<repo>`)
- A review queue for findings the verifier is unsure about
- Multi-baseline drift
- PyPI release

## Contributing and docs

`CONTRIBUTING.md` for the rules, `ARCHITECTURE.md` for the module layout, `docs/` for operations, limits, the fifteen laws and the design rationale, `CHANGELOG.md` for history. Validation for a change is `ruff check src tests`, `pytest -q` and `black-heron --help`, all free.

## Why "Black Heron"

The black heron (*Egretta ardesiaca*) spreads its wings into a canopy over the water. The shade draws small fish; the bird waits, then strikes. Wide cover, stillness, one precise strike.

## Licence

MIT, see [`LICENSE`](LICENSE). Built by Josip Lipak, 2026.
