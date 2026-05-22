# Black Heron

> Multi-lens, governance-first repository audit agent with an adversarial verifier.
> **v1.3.3** — 4 lenses + adversarial Opus verifier, evidence-presence pre-check, versioned rubric, SARIF output, parallel lens execution, code-writing suggest mode, external MCP enrichment (context7 / sequential-thinking / firecrawl / playwright), **deterministic baseline drift** (`--baseline previous.json`), **content-hash cache** across CLI + MCP server paths (`--no-cache` to bypass), and a **drop-in GitHub Actions workflow** (`.github/workflows/black-heron.yml`).

## Distributions

This repository ships Black Heron in **two distributions**:

| | Python CLI (this root) | Claude Code Skill ([`/skill/`](skill/)) |
|---|---|---|
| **Form** | Pip-installable Python package + CLI + MCP server | Markdown-only skill, Karpathy-style |
| **Install** | `pip install -e .` (Python 3.11+) | `git clone ... && cp -r skill .claude/skills/bh` (30 sec) |
| **Determinism** | Deterministic JSON/SARIF shape per run | Lens output may vary slightly per run |
| **Caching** | Content-hash cache across CLI + MCP server | None (Claude Code response not keyed) |
| **Drift mode** | Yes (`--baseline previous.json`) | No |
| **Test coverage** | 103 pytest tests | 0 (logic lives in prompts) |
| **CI/CD** | Clean (`pip install` + `upload-sarif`) | Awkward (CI would need to run Claude Code) |
| **Customization** | Edit Python + reinstall | Edit `.md` files |
| **Best for** | Production CI/CD, audit-over-time, ops dashboards | Quick audits, prompt iteration, team experimentation |

Both ship the **same four lens prompts, same `LAW.md`, same adversarial-verifier discipline.** The Python edition is the same agent with a deterministic shell around it. See [`skill/README.md`](skill/README.md) for the skill distribution's install path and trade-off detail.

```
       ___
      ( o>          " spread a wide cover,
   ___// )           let the issues surface under it,
  (    )            then strike with what survives the verifier "
   ====
```

## What it does

Run Black Heron on a local repository. It runs four independent lenses (`code_quality`, `governance`, `drift`, `blind_spot`) and pipes their findings through an adversarial verifier (Opus) that challenges each one. The output is a Markdown report, a structured JSON file, and a SARIF 2.1.0 file (GitHub Code Scanning compatible). No CI integration, no auto-fix, no patch generation — Black Heron is an **audit**, in the legal sense: a snapshot meant to inform a reviewer.

**New in v1.3.1** — Phase R: baseline drift mode.
- `--baseline previous-findings.json` — compute set-difference drift between a prior audit and this one. No LLM call, fully deterministic
- 4 buckets surface in `REPORT.md` right under the Summary: **new** / **closed** / **persisting** / **drifted**
- Identity hash collapses `lens + file + start-line + first-8-words(claim)` so the same issue across runs collapses to the same key even if the LLM rephrases the claim
- Persisting P0/P1 = explicit compliance-debt signal — surfaced as a callout in the report
- Closed findings carry a "verify in `git log`" note — closed without a fix commit may indicate masking rather than fixing (Apollo-reverse discipline)
- Missing or malformed baseline = audit continues, skip reason is logged in the report (Law IV: partial result is honest)

**New in v1.3** — Phase G: external-MCP enrichment.
- `--enrich context7,firecrawl,playwright,sequential-thinking` — opt in to one or more 3rd-party MCP servers; each enricher attaches its data to the prompt bundle the lenses see
- `context7` → fetches live library docs for every dependency declared in `pyproject.toml` / `package.json` / `requirements.txt` so lenses reason against current APIs, not training-snapshot ones
- `firecrawl` → fetches external URLs referenced in README / docs; verifies they are real and current
- `playwright` → renders a JS-heavy public URL (admin panel, dashboard) so lenses see the page the docs claim exists
- `sequential-thinking` → one-shot architectural reasoning over repo metadata, surfaced to the verifier
- Each enricher gracefully skips if its binary isn't installed; missing MCP servers never fail the audit
- Default is `--enrich none` so v1.2 commands behave identically

**Earlier features (v1.0 → v1.2):**
- 4 lenses with `blind_spot` running last to catch meta-intersection issues
- Entry-point files loaded with full content for cross-file reasoning
- Evidence-presence pre-check (substring-match every finding's quote against the input bundle)
- Versioned rubric with confidence floors per severity, lens toggles, cost + time kill-switches
- Parallel lens execution (`--parallel`, default on) — first-pass lenses run on a `ThreadPoolExecutor`
- Code-writing suggest mode (`--mode suggest`) — drafts unified-diff patches for verified P0/P1 findings, with an Opus 4.7 adversarial patch-reviewer; never auto-applied
- 5-minute prompt caching on lens + verifier system prompts
- SARIF 2.1.0 output for GitHub Code Scanning

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

### Audit-over-time with `--baseline` (v1.3.1)

```bash
# First audit — save findings.json as T0
black-heron /path/to/repo --out audit-T0/

# ... fix some issues, ship some commits ...

# Second audit — diff against T0
black-heron /path/to/repo --baseline audit-T0/findings.json --out audit-T1/

# REPORT.md will gain a "Drift since baseline" section under the Summary.
# Persisting P0/P1 findings are flagged as compliance debt.
```

### Opt into external MCP enrichment (v1.3)

```bash
# All four enrichers; missing binaries skip silently
black-heron /path/to/repo --enrich all --out audit/

# Just live library docs
black-heron /path/to/repo --enrich context7 --out audit/

# Custom server commands / env / timeouts
black-heron /path/to/repo --enrich all --mcp-config ~/.black-heron/mcp.json
```

Install the underlying MCP servers (any subset) with `npx`:

```bash
# Verifies they install + run; you can skip this — BH calls them lazily on demand
npx -y @upstash/context7-mcp --help
npx -y @modelcontextprotocol/server-sequential-thinking --help
npx -y firecrawl-mcp --help
npx -y @playwright/mcp --help
```

If a binary is missing, BH logs the skip in `REPORT.md` under "MCP enrichment" and continues — never a hard failure.

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
