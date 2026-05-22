---
name: bh
description: Multi-lens governance-first repository audit. Four independent perspectives (code quality, governance, drift, blind spot) cross-checked by an adversarial verifier on a different model. Outputs REPORT.md + findings.json + SARIF. Use when the user asks to audit, review, or assess a repository, or types `/bh`, or when planning a refactor and wanting to surface hidden issues first.
aliases:
  - black-heron
  - blackheron
---

# Black Heron — Multi-lens repository audit

You are running the Black Heron audit pipeline. Your job is to surface issues a competent senior engineer would flag, then have an adversarial verifier kill false positives.

This skill is **deterministic in structure**, **non-deterministic in findings**. Follow the structure exactly. Let the lens prompts do the substantive work.

## When to run

Run when the user says any of:
- **`/bh`** (the short trigger — primary)
- `/black-heron` (long form — same skill)
- "audit this repo" / "audit the codebase"
- "find issues" / "code review the whole thing"
- "what's wrong with this repo?"
- "governance audit" / "compliance check"

Also run proactively when the user is **about to commit to a refactor** or **starts a new branch on an unfamiliar codebase** — surface issues before they pick direction.

## Sacred discipline (read `LAW.md` for the full 15)

These are the load-bearing rules. Violations poison the audit.

- **I. NEVER fabricate evidence.** Every `evidence` field must be a verbatim substring of an actual file you Read. If you can't quote it, you can't raise it.
- **II. NEVER soften severity preemptively.** The lens calls severity as the evidence supports. The verifier downgrades.
- **III. NEVER rewrite code — always patch.** This audit is read-only.
- **VI. NEVER skip the adversarial verifier.** Even zero raw findings runs through verifier (confirms emptiness).
- **VII. ALWAYS distinguish theoretical from observable.** Only raise findings the cited evidence shows are observable in the code path. "Could be exploited" without a path = REJECT.
- **VIII. Verifier runs on a different model than lenses.** If you can switch model checkpoints between lens and verifier passes, do. Same checkpoint = shared blind spots.
- **XV. NEVER report a number you did not verify this run.** Cost, finding counts, latencies — all from this run, not memory.

## Inputs you need before starting

1. **Repo path** — usually the current working directory. Confirm with `ls` or by reading the directory listing.
2. **Audit output directory** — default `./audit/`. Create if missing.

## Workflow

### Step 1 — Build repo context

Gather these artifacts (use `Read`, `Glob`, `Grep`, `Bash`):

- **File listing** (authoritative): full list of source files, excluding `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `dist`, `build`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.idea`, `.vscode`, `audit_output`. Cap at 200 listed; if more, note "+N more not listed".
- **Entry-point files** (load full content, cap 10 KB each):
  - Package manifests: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `pom.xml`, `*.gemspec`, `requirements.txt`
  - Language config: `tsconfig.json`, `setup.cfg`, `.tool-versions`
  - Build config: `Makefile`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/*.yml`
  - Module init: `__init__.py`, `index.ts`, `index.js`, `mod.rs`, `lib.rs`
  - Entry: `main.py`, `cli.py`, `server.py`, `app.py`, `__main__.py`
  - Rubric/policy: `rubric*.json`, `policy*.yaml`, `*.policy.json`
- **Recent git history** — last 30 commits via `git log --oneline -30`. If not a git repo, note "no git history".
- **TODO/FIXME/XXX/HACK count** — `grep -rE "TODO|FIXME|XXX|HACK" --include="*.py" --include="*.ts" --include="*.js" ...` across source files. Just the count.
- **Source samples** (4 KB cap per file, max ~30 files for coverage): random selection of small files for additional context. NOT authoritative — only coverage.

Assemble all of the above into a single prompt block. This is the "repo context" passed to every lens.

### Step 2 — Run the four lenses

For each lens, send a request that includes:
- The lens prompt (load from `.claude/skills/black-heron/lenses/<lens>.md`)
- The repo context block built in Step 1

The four lenses (run in this order — `blind-spot` MUST come last because it reads other lenses' output):

1. **code-quality** — issues a senior PR reviewer would flag (`lenses/code-quality.md`)
2. **governance** — operating-model discipline, audit trails, escalation (`lenses/governance.md`)
3. **drift** — claims-vs-delivery gaps, TODO accumulation, stale references (`lenses/drift.md`)
4. **blind-spot** — meta-intersection issues the other 3 miss (`lenses/blind-spot.md`)

Each lens returns a JSON object with a `findings` array. Parse it. If parse fails, log to stderr and treat that lens as returning empty findings (do NOT fabricate replacements).

**For `blind-spot`**, append the prior 3 lenses' findings to its input (formatted as `[lens/severity] file lines: claim`).

### Step 3 — Evidence pre-check

For each finding from Step 2, check whether the `evidence` field is a verbatim substring of the input bundle (the repo context built in Step 1). If not, set an `evidence_in_bundle: false` flag on that finding. Do NOT discard — the verifier will.

Short evidence quotes (< 20 chars) skip this check (too noisy — false rejection rate too high).

### Step 4 — Adversarial verifier

Load `.claude/skills/black-heron/verifier.md`. Send it ALL findings from Step 3 (with `evidence_in_bundle` flag attached) as the user message.

**Critical:** if your model selection allows, the verifier should run on a **different model checkpoint** than the lenses (Law VIII). If using Claude family: lenses on Opus 4.6, verifier on Opus 4.7. If using another family: pick the closest available model differential. Same model for both is acceptable but document it as a quality risk in the report.

The verifier outputs `{verified: [...], rejected: [...]}`. Parse.

Apply severity confidence floors AFTER the verifier:
- P0 requires `confidence >= 0.85`; downgrade to P1 if `0.70 <= conf < 0.85`
- P1 requires `confidence >= 0.70`; downgrade to P2 if `0.50 <= conf < 0.70`
- P2 requires `confidence >= 0.50`; REJECT if `conf < 0.50`

### Step 5 — Write outputs

Create the output directory (`./audit/` by default, or whatever the user specified).

Write three files. The format spec is in `report-template.md`.

1. **`REPORT.md`** — human-readable Markdown:
   - Title + generation timestamp
   - Repo metadata (path, file count, primary language, TODO count, entry-point files loaded)
   - Volume-calibrated summary sentence (calibrate the lead-in to actual P0/P1/P2 mix and verifier reject ratio)
   - Lens raw output table (lens name + raw count)
   - Verifier reject ratio
   - Per-severity findings sections (P0, P1, P2). Each finding: claim, lens, file:lines, confidence, evidence (verbatim), why_it_matters, verifier_note
   - Rejected findings (transparency section — show what got filtered)
   - Honest scope footer ("This audit found N issues in M files; lens prompts may have blind spots; verifier ran on model X")

2. **`findings.json`** — machine-readable. Include:
   - `schema_version`, `black_heron_version` (use `1.0.0-skill` for this distribution)
   - `generated_at_utc`
   - `repo` block (path, file_count, primary_language, todo_count, entry_points_loaded)
   - `lens_raw_counts` (one int per lens)
   - `verified` (array)
   - `rejected` (array)
   - Each verified finding includes `lens, severity, file, lines, claim, evidence, why_it_matters, confidence, verifier_note`

3. **`findings.sarif`** — SARIF 2.1.0 for GitHub Code Scanning ingest. Schema: `https://json.schemastore.org/sarif-2.1.0.json`. One rule per `(lens, severity)` pair. One result per verified finding.

### Step 6 — Final response to user

Print one line summary:
```
Audit complete: <N verified> findings (<p0> P0 / <p1> P1 / <p2> P2), <M rejected> by verifier.
Reports: ./audit/REPORT.md, findings.json, findings.sarif
```

Then point them to REPORT.md. Do not summarize findings inline in chat — the report IS the deliverable.

## What to do if a step fails

- **Lens returns malformed JSON** → log to stderr, treat that lens as empty, continue.
- **Verifier returns malformed JSON** → fall back to ALL findings kept, confidence capped at 0.5, prefix every finding's `verifier_note` with "VERIFIER FAILED — preserved with conservative confidence". Continue. Do NOT abort.
- **Cost or time budget exceeded** (if user provided one) → stop on next lens boundary, write partial findings with `"truncated": true` flag in `findings.json`.
- **A finding cites a file that does not appear in the file listing** → mark `absence_claim: true`, push to verifier with extra skepticism. Verifier likely REJECTs unless authoritative check is documented.

## Output discipline

- DO NOT auto-apply fixes. Black Heron is read-only.
- DO NOT push to remote. Local-only output.
- DO NOT modify the audited repo. Only write to the output directory.
- DO surface the rejection list transparently — what got filtered is part of the audit, not separate.

## Glossary (for your model context)

- **lens** = one specialized analytical perspective (code-quality / governance / drift / blind-spot)
- **verifier** = adversarial second-pass that kills FPs from lenses, runs on a different model
- **absence_claim** = a finding asserting that a file or feature is MISSING (requires extra scrutiny because lenses may not have seen authoritative sources)
- **evidence_in_bundle** = boolean: did the cited evidence string match a verbatim substring of the input context bundle? Set in Step 3.
- **drift** (not the lens — the concept) = the gap between what the repo CLAIMS (README, commits, docs) and what it DELIVERS (source code, file listing, behavior)

---

*Author: SHIKA (Josip Lipak) · 2026. MIT license.*
*This skill is the lightweight Karpathy-style distribution of Black Heron. For the full Python implementation with deterministic SARIF generation, content-hash cache, and CI/CD integration, see `lipakjosip442-png/black-heron`.*
