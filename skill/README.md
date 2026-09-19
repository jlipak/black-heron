# Black Heron — Skill

> A drop-in Claude Code skill for governance-first repository audits.
> Four lenses + adversarial verifier. No Python install, no API key juggling.
> Just copy into `.claude/skills/` and ask Claude Code to audit.
>
> **This is the `/skill/` subdirectory of the [`black-heron`](https://github.com/jlipak/black-heron) monorepo.** For the Python CLI edition (deterministic, CI-ready), see the repo root.

```
       ___
      ( o>           " spread a wide cover,
   ___// )            let the issues surface under it,
  (    )              then strike with what survives the verifier "
   ====
```

---

## What this is

This is the **lightweight distribution** of [Black Heron](https://github.com/jlipak/black-heron). Karpathy-pattern claude.md style: instructions live in markdown, Claude Code reads them and executes the pipeline. No Python package to install, no CI runner needed.

**Trade-offs vs the Python edition** — read [`Trade-offs vs Python Black Heron`](#trade-offs-vs-python-black-heron) at the bottom of this README.

## Install (30 seconds)

### Step 1 — Pull the skill subdirectory

From the root of any repo you want to be able to audit:

```bash
# Clone the monorepo to a tmp dir, copy just /skill/ to .claude/skills/bh
git clone --depth=1 https://github.com/jlipak/black-heron /tmp/bh-monorepo
mkdir -p .claude/skills && cp -r /tmp/bh-monorepo/skill .claude/skills/bh
rm -rf /tmp/bh-monorepo
```

Or with sparse-checkout if you prefer a single shallow tree:

```bash
git clone --depth=1 --filter=blob:none --sparse https://github.com/jlipak/black-heron /tmp/bh
cd /tmp/bh && git sparse-checkout set skill
cp -r /tmp/bh/skill /path/to/your/repo/.claude/skills/bh
```

Claude Code auto-discovers the skill in `.claude/skills/bh/`. After this step, `/bh` already works.

### Step 2 — Add project-level instructions

The skill ships a `CLAUDE.md` template that tells Claude Code how to invoke `/bh` and what discipline rules to honor in this project.

**If your project doesn't have a `CLAUDE.md` yet:**

```bash
cp .claude/skills/bh/CLAUDE.md ./CLAUDE.md
```

**If your project already has a `CLAUDE.md` (recommended path — preserves your existing instructions):**

```bash
# Append the BH section to your existing CLAUDE.md
echo "" >> ./CLAUDE.md
echo "<!-- Black Heron skill — appended $(date +%Y-%m-%d) -->" >> ./CLAUDE.md
cat .claude/skills/bh/CLAUDE.md >> ./CLAUDE.md
```

Or open both files and **merge by hand** — pull just the sections you want (typically the "How to run an audit", "Discipline", and "Where things live" sections). Skip duplicates of rules you already have.

### User-level install (alternative)

If you want `/bh` available from any project without per-project clones:

```bash
git clone --depth=1 https://github.com/jlipak/black-heron /tmp/bh-monorepo
cp -r /tmp/bh-monorepo/skill ~/.claude/skills/bh
rm -rf /tmp/bh-monorepo
```

Then in each project where you actually want the audit, do Step 2 (CLAUDE.md merge) to give Claude Code the project-level context.

## Use

In any project where you've installed the skill, open Claude Code and type:

```
/bh
```

That's the primary trigger. Equivalent variants Claude Code also recognizes:

- `/black-heron` (long form)
- "audit this repo"
- "run black heron on src/" (scope to a sub-tree)

Claude Code will:
1. Build the repo context (file listing, entry-point full content, git log, samples)
2. Run the four lenses (code-quality, governance, drift, blind-spot) — each one a separate LLM call with its prompt loaded from `lenses/`
3. Run the adversarial verifier with severity confidence floors
4. Write `audit/REPORT.md`, `audit/findings.json`, `audit/findings.sarif`

Then it'll point you at `audit/REPORT.md`. That's the deliverable.

## What you get

**See [`examples/sample-audit/`](examples/sample-audit/)** for a synthetic but realistic run — full `REPORT.md`, `findings.json`, and `findings.sarif` you can read before running the audit on your own code.

### `REPORT.md`
Human-readable Markdown. Per-severity sections (P0 / P1 / P2). Each finding has:
- A factual one-sentence claim
- File + line range
- A verbatim evidence quote from your actual code
- Why it matters (engineering rationale)
- A `verifier_note` explaining the verifier's verdict
- Confidence score

Plus a **transparency section** showing what the verifier rejected — false-positive surface area is part of the audit.

### `findings.json`
Machine-readable. Schema documented in [`report-template.md`](report-template.md). Use this for downstream tooling, dashboards, or PR-comment automation.

### `findings.sarif`
SARIF 2.1.0 — directly ingestable by GitHub Code Scanning. Upload via `github/codeql-action/upload-sarif` and findings show up in the Security tab.

## How the discipline works

The audit isn't "ask an LLM to find bugs." That produces a 37% false-positive rate (Apollo Lex Audit lesson, the seed of this project). Instead:

1. **Four independent lenses** — different perspectives, different prompts. Each lens has its own surface area: code-quality covers single-file engineering nits, governance covers operating-model artifacts, drift covers claims-vs-delivery, blind-spot covers meta-intersection issues.
2. **Evidence-presence pre-check** — every finding's `evidence` field must be a verbatim substring of the input bundle. Lenses that fabricate evidence get flagged before they reach the verifier.
3. **Adversarial verifier on a different model** — if you're running Claude Opus 4.6 for lenses, run Opus 4.7 for the verifier. Different checkpoint = different blind spots. Same model = shared blind spots and a false sense of consensus.
4. **Severity confidence floors** — P0 needs `conf ≥ 0.85`; otherwise the verifier downgrades to P1. P1 needs `≥ 0.70`. P2 needs `≥ 0.50`. Anything below 0.50 gets rejected.
5. **`absence_claim: true` extra scrutiny** — a lens claiming a file or feature is missing has to prove it checked the authoritative file listing AND entry-point contents.

The full discipline — 15 sacred rules, each evidence-based against a real past failure mode — lives in [`LAW.md`](LAW.md). Read it.

## Repo structure

```
skill/                   # (this subdirectory inside the black-heron monorepo)
├── README.md            # this file (GitHub-facing)
├── CLAUDE.md            # template — copy to project root for Karpathy-style instructions
├── SKILL.md             # Claude Code skill entry — the workflow orchestrator
├── LAW.md               # 15 sacred rules (discipline)
├── verifier.md          # adversarial verifier prompt
├── report-template.md   # output format spec (REPORT.md + findings.json + SARIF)
├── lenses/
│   ├── code-quality.md  # senior PR-reviewer issues
│   ├── governance.md    # operating-model discipline
│   ├── drift.md         # claims-vs-delivery gaps
│   └── blind-spot.md    # meta-intersection issues
├── LICENSE              # MIT
└── NOTICE.md            # attribution
```

When you install via `git clone`, this whole tree lands at `.claude/skills/bh/`. Claude Code finds `SKILL.md` (frontmatter `name: bh`) and uses it as the entry point. The other files are referenced from there.

The **`CLAUDE.md`** template you copy to your project root gives Claude Code the project-level context: what the skill does, the `/bh` command, project-discipline rules derived from `LAW.md`, where audit outputs land. Karpathy-pattern: short, focused, actionable.

## Customization

This is markdown. Edit what you don't like.

- **Different severity bar?** Edit the floors in `verifier.md`.
- **Different focus areas?** Edit any lens prompt under `lenses/`.
- **Want a fifth lens?** Add `lenses/<name>.md` and reference it in `SKILL.md` Step 2.
- **Your company has a private rubric?** Drop it next to `LAW.md` and tell `SKILL.md` to load it as a context block.

The skill is fully transparent. There's no hidden state — what Claude Code sees is exactly what's in these files.

## Trade-offs vs Python Black Heron

| | This skill | Python Black Heron |
|---|---|---|
| Install | `git clone` (30 sec) | `pip install -e .` (5-15 min + Python 3.11) |
| Vendor | Any model Claude Code supports | Anthropic only (`claude-opus-4-8` / `claude-opus-5`) |
| Determinism | Lens output may vary slightly per run | Same deterministic SARIF/JSON shape per run |
| Test coverage | 0 tests (logic lives in prompts) | 103 pytest tests |
| Content-hash cache | No (Claude Code's response isn't keyed by repo state) | Yes (`--no-cache` to bypass) |
| Drift mode (baseline diff) | No | Yes (`--baseline previous.json`) |
| CI/CD integration | Awkward (CI needs to run Claude Code) | Clean (`pip install + run + upload-sarif`) |
| Customization | Edit `.md` files | Edit Python + reinstall |
| Suitable for | Quick audits, iterating on prompts, team experimentation | Production CI/CD, audit-over-time, ops dashboards |

**Recommendation:**
- **This skill** when you want to try the audit on a fresh repo without setup, or when you want to tune the prompts for your stack.
- **Python edition** when you want deterministic outputs in CI, content-hash caching to skip API spend on unchanged repos, or audit-over-time drift detection.

Both ship the same lens prompts, the same LAW.md, the same governance discipline. The Python version is the same agent with a deterministic shell around it.

## Honest scope

This is v1.0.0 of the skill distribution. The lens prompts were tuned against a small set of Python/TypeScript repos — they're solid for those stacks but **may have blind spots for Rust, Go, Java, C++**. If you run the audit on a stack we haven't tuned for and find a systematic gap, [open an issue](https://github.com/jlipak/black-heron/issues) and we'll look at it.

The discipline (LAW.md, evidence-presence check, adversarial verifier on different model, severity floors) is universal. It works regardless of stack. What varies is whether the **lens prompts** know what to look for in your particular language ecosystem.

## License

MIT. See [`LICENSE`](LICENSE). Use it, fork it, ship it.

---

*Author: Josip Lipak · 2026.*
*This is the Karpathy-style distribution. For the Python implementation with deterministic SARIF generation, content-hash cache, and CI-ready CLI, see the [repo root](https://github.com/jlipak/black-heron).*
