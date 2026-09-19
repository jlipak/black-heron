# The Law of Black Heron

Fifteen sacred rules. Each is the **inverse of a proven failure mode** — drawn from the Apollo Lex audit (37% false-positive rate without verifier), a compliance-pipeline build, and the 968-session AKIRA collapse that EZEKIEL was forged from. None of these are aspirational. Every one is paid for in past pain.

```
Trust = (Verified Findings × Speed) / (False Positives × Scope Creep)
```

---

## I. NEVER FABRICATE EVIDENCE
**Evidence base:** Apollo Lex Audit — Phase 1 agent fabricated `docs/legal/dpa-template.md:251` quote. File did not exist. Verifier caught it via `Glob`. Same pattern repeats: "verbatim quote" that is paraphrase or invention.

Every `evidence` field must be a substring of the input bundle (sample files + entry-point files). `evidence_verifier.py` enforces this pre-LLM. If you can't quote literally, you cannot raise the finding.

**Cost of violating:** every fabricated finding poisons the entire audit report. One forgery kills the reader's trust forever.

---

## II. NEVER SOFTEN SEVERITY PREEMPTIVELY
**Evidence base:** When a lens is uncertain whether a finding is P0 or P1, the tempting move is to call it P1 to be "safe." This drops material findings under the verifier's radar.

The lens calls severity as the evidence supports. The **verifier** downgrades or rejects, with explicit `verifier_note`. The lens does not pre-soften to avoid being wrong.

---

## III. NEVER REWRITE — ALWAYS PATCH
**Evidence base:** AKIRA Session 777, 968 sessions of rewrite-driven decay. 544 documented rewrite anti-pattern occurrences. Rewrites silently drop accumulated bug fixes — the single most destructive pattern across 1,000+ sessions.

If a lens prompt has 30+ sessions of tuning embedded in it, do not rewrite "to clean it up." Patch the specific line. Read the git log before touching old code.

---

## IV. VERIFY BEFORE "DONE"
**Evidence base:** AKIRA S25 spread gate "deployed" but default 0.0 was effectively dead code. Three sessions of dead "deployed" feature. EZEKIEL Rule IV (315 verify + 282 make_sure events).

For BH: every audit ships with three artifacts (`REPORT.md`, `findings.json`, `findings.sarif`) AND the verification commands listed in `CLAUDE.md` must succeed before declaring done. "Should work" is a lie.

---

## V. NEVER CLAIM ABSENCE WITHOUT CHECKING AUTHORITATIVE SOURCES
**Evidence base:** BH v0.1 on a client compliance repo: lens raised "LICENSE missing" + "smoke-mcp tools missing." Both files existed — lens didn't see them in the 30-file sample. v1.0 mitigates via `absence_claim: true` flag + entry-point full-content loading.

If a finding asserts a file or feature is missing, the lens MUST set `absence_claim: true` AND state in `why_it_matters` which authoritative section was checked (file listing? entry-point content?). Verifier applies extra skepticism to absence claims.

---

## VI. NEVER SKIP THE ADVERSARIAL VERIFIER
**Evidence base:** Apollo Lex Audit found 37% false-positive rate even with multi-agent cross-validation. Convergence between lenses is NOT a guarantee — all lenses can miss the same thing. Without an adversarial Opus pass, theoretical attacks get categorized as P0 without exploitability proof.

Every audit, even when raw lens output is empty, runs through `synthesis.synthesize()`. Verifier confirms emptiness or filters noise. No exceptions.

---

## VII. ALWAYS DISTINGUISH THEORETICAL FROM OBSERVABLE
**Evidence base:** Apollo Lex Audit: "AI prompt injection via role" was a theoretical attack — Anthropic API rejects `role='system'` in messages array. No exploit existed. Lens raised it as P0 anyway because "it could happen."

Lens prompts include the rule: "Only raise findings where cited evidence shows the issue is observable in the code path, not merely a hypothetical edge case." Verifier rejects theoretical-only findings.

---

## VIII. ALWAYS RUN VERIFIER ON A DIFFERENT MODEL THAN THE LENS
**Evidence base:** When lens and verifier are the same model with the same prompt structure, they share the same blind spots. Apollo lesson: "Generic agents trust each other and repeat the same analytical patterns."

Lenses run on `claude-opus-4-6`. Verifier runs on `claude-opus-4-7`. Different model checkpoint = different training distribution = different blind spots. Model differential is a feature, not an artifact.

---

## IX. NEVER USE HAIKU OR SONNET FOR SUBSTANTIVE REASONING
**Evidence base:** Owner preference + AKIRA collapse documenting that cost-cutting on substance produces silent decay. Sonnet for lens work means cheaper audits AND lower-quality findings. The savings is illusory.

`claude-opus-4-6` for lenses, `claude-opus-4-7` for verifier. `--budget-mode` flag is the **only** way to engage Sonnet, and the user opts in explicitly. Haiku is not configured anywhere in `rubric.default.json`.

---

## X. KILL-SWITCH ON ANY CATASTROPHIC SIGNAL
**Evidence base:** EZEKIEL S5-S6 first overnight: 3 stop-losses, -$1,071. Circuit breaker fired correctly at -10.71%. Trading-grade discipline applied to audits.

Three kill-switches in `cli.py` + `synthesis.py`:
- **Total findings cap** (default 50 P0+P1): if exceeded, abort — lens prompts have drifted.
- **Cost cap** (default $2/audit): if exceeded, abort before next API call.
- **Time cap** (default 300s/audit): if exceeded, abort.

All three are configurable in `rubric.default.json`. None are silently bypassed.

---

## XI. NEVER PUSH TO GIT REMOTE WITHOUT THE OWNER'S EXPLICIT AUTHORIZATION
**Evidence base:** EZEKIEL Constraints + universal rule. Local commits survive every catastrophe; remote pushes survive every operator regret.

`scripts/hooks/block-git-push.sh` is a PreToolUse BLOCK hook (exit 2). Unblocked only by the owner editing `.claude/settings.local.json` with explicit override, OR by the owner invoking the push command in a separate dedicated session.

---

## XII. NEVER HARDCODE SECRETS — EVER
**Evidence base:** AKIRA S29 hardcoded Discord webhook despite existing rule. AKIRA S27 `.env` was world-readable (chmod 644).

API keys come from `ANTHROPIC_API_KEY` env var only. `.env` is gitignored. `.env.example` is committed with placeholder values. PreToolUse hook scans `Write|Edit` operations for `sk-ant-`, `ghp_`, `BEGIN RSA`, etc. Exit 2 on match.

---

## XIII. ALWAYS COMMIT AFTER A MEANINGFUL CHANGE
**Evidence base:** EZEKIEL Rule I (1,524 save requests, 546 lost_work frustrations across 968 AKIRA sessions). Context dies without warning. Compaction eats in-progress work.

After every finished phase or sub-task: `git add <specific-files>`, `git commit -m "<one concern>"`. Never `git add -A`. One concern per commit.

---

## XIV. ALWAYS WRITE THE SESSION-DIGEST BEFORE WRAP
**Evidence base:** EZEKIEL Rule (S30 stale-data trap): SESSION-DIGEST said "YES leak fixed" while MEMORY.md NEXT said "[ ] FIX: YES leak." Most-recent-write wins. Stale digest = hallucination-on-reboot.

End of every BH session: update `MEMORY.md` NEXT list, write fresh `SESSION-DIGEST.md`, commit both. Boot of next session reads DIGEST first.

---

## XV. NEVER REPORT A NUMBER YOU DID NOT VERIFY THIS SESSION
**Evidence base:** EZEKIEL Rule (S30 boot hallucination): docs said "PAPER MODE ONLY" + "15 cities" when reality was LIVE + 18 cities. Bot loaded the file and parroted it.

Every cost, every finding count, every latency in the report comes from THIS run's tracker, not a memory of a previous audit. If you cite a calibration metric (e.g., "running FP rate 8%"), the calibration.json file's `last_updated` timestamp must be visible in the citation context.

---

## How To Apply

These 15 are immutable in v1.x. Adding a 16th requires:
1. Evidence base: a documented past failure that ≥3 audits would have prevented
2. Cross-reference to the failure source (session log, audit JSON, public incident)
3. Rubric version bump (`rubric_version` field)
4. Update to `MEMORY.md` "How I Operate" section

Removing a law requires: same evidence threshold, but for a documented case where the law caused MORE harm than it prevented. We have no such cases yet.

## Cross-References

- `CLAUDE.md` — identity + which 5 of these are also pinned at the top as Critical Constraints
- `MEMORY.md` — operational state, NEXT list
- `KNOWN_LIMITATIONS.md` — gaps where these laws are imperfectly enforced (e.g., FM1 sample-based context = Law V is mitigated, not eliminated)
- `.claude/rules/quality.md` — operationalization of Laws IV, VI, VII into checklists
- `.claude/rules/security.md` — operationalization of Laws XI, XII

---

*"Make findings that survive scrutiny. Protect the reviewer's trust above all else."*

Built on EZEKIEL's 10 holy rules, extended with compliance-pipeline governance, hardened by Apollo verifier lessons. Author: Josip Lipak. 2026.
