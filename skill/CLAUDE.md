# CLAUDE.md — for projects using Black Heron

> **If your project doesn't have a CLAUDE.md yet:** copy this file to the project root.
> **If your project already has one:** append the sections below into it (skip duplicates of rules you already have).
>
> Claude Code reads `CLAUDE.md` on every prompt and uses it as project-level instructions.
> Once the BH-related content is in place, the `/bh` command runs the Black Heron audit on the project.

---

## What this project uses

This project audits itself with **Black Heron** — a multi-lens, governance-first repository audit skill installed at `.claude/skills/bh/`.

- Four lenses: code-quality, governance, drift, blind-spot
- Adversarial verifier (different model checkpoint when available)
- 15-rule sacred discipline (`LAW.md` inside the skill folder)
- Output: `audit/REPORT.md`, `audit/findings.json`, `audit/findings.sarif`

## How to run an audit

```
/bh
```

That's it. Claude Code loads `.claude/skills/bh/SKILL.md` and executes the 6-step audit pipeline. Output lands in `./audit/`.

Variants Claude Code also recognizes (they trigger the same skill):
- "audit this repo"
- "run black heron"
- "/bh on src/"  (scope the audit to a sub-tree)

## What to do AFTER an audit

1. Open `audit/REPORT.md` — read the verified findings, severity-sorted.
2. **Check the "Rejected findings (transparency)" section.** What the verifier filtered is part of the audit — false-positive surface area is data.
3. For each P0/P1 you want to act on: open the cited `file:line`, confirm the evidence, decide patch or accept.
4. Black Heron is **read-only**. It will NEVER auto-apply fixes. You decide what to change.

## Discipline (project-level rules Claude Code should honor)

These are derived from Black Heron's 15 sacred laws (`.claude/skills/bh/LAW.md`). They apply to any change Claude Code makes inside this project:

- **NEVER fabricate evidence.** When citing files, line ranges, or quotes — they must exist verbatim.
- **NEVER soften severity preemptively** when reporting issues. Call severity as evidence supports.
- **NEVER rewrite — always patch.** If a function has months of tuning embedded, edit specific lines, don't redo the whole thing.
- **VERIFY BEFORE "done".** Run the relevant test / lint / type-check before claiming a task is complete.
- **NEVER push to git remote without explicit authorization.** Local commits are fine; `git push` requires the user saying "push".
- **NEVER hardcode secrets.** API keys come from `.env` (gitignored). `.env.example` shows the schema with placeholder values.
- **VERIFY NUMBERS THIS SESSION.** Don't quote stats from prior sessions or memory files. Re-run the command if you need a number.

## Where things live

- **`.claude/skills/bh/`** — the Black Heron skill (this file's companion)
  - `SKILL.md` — the skill's entry orchestrator
  - `LAW.md` — 15 sacred discipline rules
  - `lenses/` — the four lens prompts
  - `verifier.md` — the adversarial verifier prompt
- **`audit/`** — where each `/bh` run writes its output (REPORT.md, findings.json, findings.sarif). Safe to gitignore or commit, your call.

## Customization

The skill is markdown. Edit it.

- Different severity bar? Open `.claude/skills/bh/verifier.md`, change the floors.
- Want a 5th lens (e.g., `accessibility`)? Add `.claude/skills/bh/lenses/accessibility.md` and reference it in `SKILL.md` Step 2.
- Your team has a private rubric? Drop it at `.claude/skills/bh/rubric.json` and add a "Load this rubric as context" step.

## Honest scope

Black Heron is a multi-LLM audit pipeline, not an autonomous agent. It runs a deterministic sequence of LLM calls and writes structured outputs. It does not loop, replan, or take corrective actions on its own.

The lens prompts are tuned against Python and TypeScript codebases. For other languages (Rust, Go, Java, C++), the underlying discipline still applies but specific lens checks may have blind spots. If you see systematic gaps, edit the lens prompt.

---

*Black Heron is MIT-licensed. Source: https://github.com/lipakjosip442-png/black-heron (`/skill/` subdir).*
*This CLAUDE.md template is part of that distribution.*
