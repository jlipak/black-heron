# Black Heron — Audit Report

> Generated 2026-05-21 17:35 UTC by Black Heron v1.0.0

**Repository:** `./black-heron`
**Files audited:** 57 (primary language: Python)
**TODO markers found in source:** 22
**Entry-point files loaded full-content:** 4 (pyproject.toml, src/black_heron/cli.py, src/black_heron/__init__.py, src/black_heron/lenses/__init__.py)

## Summary

This audit surfaced **7 issues** across multiple lenses (0 P0 / 5 P1 / 2 P2). Review priority order; the verifier filtered 7 additional noise candidates.

## Metrics

- **Wall time:** 298.92s
- **Total cost:** $2.8927
- **Per-lens cost (USD):**
  - `code_quality`: $0.5747
  - `governance`: $0.5711
  - `drift`: $0.6549
  - `blind_spot`: $0.7008
  - `verifier`: $0.3912
- **Per-lens latency (s):**
  - `code_quality`: 48.3s
  - `governance`: 50.6s
  - `drift`: 64.0s
  - `blind_spot`: 87.9s
- **Rubric version:** `1.0.0` (source: `bundled-default`)

## Lens raw output

| Lens | Raw findings |
|---|---|
| code_quality | 8 |
| governance | 6 |
| drift | 0 |
| blind_spot | 0 |

**After adversarial verifier:** 7 kept, 7 rejected.
**Verifier reject ratio:** 50.0%

## P1 findings (5)

### P1.1 — The run functions in code_quality.py, governance.py, and drift.py are near-identical (same structure, same MODEL, same API call pattern), differing only in the SYSTEM prompt string, constituting significant code duplication across three files.

- **Lens:** code_quality
- **File:** `src/black_heron/lenses/code_quality.py` lines `L1-L68`
- **Confidence:** 0.95

**Evidence:**
```
def run(ctx: RepoContext, client: anthropic.Anthropic, tracker: CostTracker | None = None) -> list[Finding]:
    user = build_repo_prompt(ctx)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
```
**Why it matters:** Three copies of the same 10-line function body means any change to the API call pattern (e.g., adding temperature, retry logic, or structured output) must be made in three places, increasing the risk of inconsistency.
**Verifier note:** Evidence supports the duplication claim and the maintenance burden is concrete.

### P1.2 — check_evidence_in_context only searches sample_files and entry_points but not the file_listing or git_log_recent, so findings that cite evidence from git commit messages (which are part of the prompt sent to the LLM) will be incorrectly flagged as evidence-not-in-bundle.

- **Lens:** code_quality
- **File:** `src/black_heron/evidence_verifier.py` lines `L35-L52`
- **Confidence:** 0.90

**Evidence:**
```
haystack_parts = list(ctx.sample_files.values())
    haystack_parts.extend(ep.content for ep in ctx.entry_points)
    haystack = _norm("\n".join(haystack_parts))
```
**Why it matters:** The drift lens explicitly asks the LLM to cite commit messages as evidence; if git_log_recent is not in the haystack, valid drift findings will be marked evidence_in_bundle=false and the verifier will have a strong prior to reject them.
**Verifier note:** Concrete asymmetry between what is sent to LLM versus what is checked for evidence presence; affects drift findings systematically.

### P1.3 — The MCP server registration hardcodes "command": "py" which only works on Windows; on Linux/macOS the Python launcher is typically `python3`, making the installed MCP config non-functional on those platforms.

- **Lens:** code_quality
- **File:** `scripts/install-mcp.sh` lines `L42`
- **Confidence:** 0.92

**Evidence:**
```
mcp_servers["black-heron"] = {
    "command": "py",
    "args": ["-m", "black_heron.mcp_server"],
```
**Why it matters:** The script already detects the correct Python interpreter (`for cand in py python3 python`) but then ignores that detection and hardcodes "py" in the JSON output, breaking cross-platform portability.
**Verifier note:** Clear portability bug supported by the cited line.

### P1.4 — The jq fallback regex for extracting content only captures the first match of `content` or `new_string` and uses a non-greedy pattern `[^"]*` that will silently truncate any content containing escaped quotes, allowing secrets in later portions of the string to bypass the scan.

- **Lens:** code_quality
- **File:** `scripts/hooks/scan-secrets.sh` lines `L20-L27`
- **Confidence:** 0.82

**Evidence:**
```
CONTENT=$(echo "$INPUT" | grep -oE '"(content|new_string)"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/^"(content|new_string)"[[:space:]]*:[[:space:]]*"(.*)"$/\2/')
```
**Why it matters:** If the written content contains escaped double quotes (common in code files), the regex match terminates early, and secret patterns after the first escaped quote are never scanned — this is a security bypass in the secret-scanning hook.
**Verifier note:** Real security gap but it is a fallback path (jq is the primary); downgraded from P0 to P1 since severity floor for P0 requires conf ≥ 0.85 and exploitability depends on jq being absent.

### P1.5 — The evidence-presence verifier uses hardcoded thresholds (`len(needle) < 20` and `needle[:60]`) with no citation to a rubric field, spec, or prior-art justification for why 20 characters and 60-character prefix were chosen.

- **Lens:** governance
- **File:** `src/black_heron/evidence_verifier.py` lines `L36-L38, L43`
- **Confidence:** 0.85

**Evidence:**
```
evidence_verifier.py L43: `if len(needle) < 20:` with comment `# Very short evidence — too noisy to substring-match reliably`. L50: `elif needle[:60] in haystack:` with no comment explaining the 60-char cutoff. Neither 20 nor 60 appears in `rubric.default.json`.
```
**Why it matters:** These thresholds directly affect whether fabricated evidence is caught or missed — a security-relevant code path whose tuning parameters should be traceable to a versioned policy or documented rationale.
**Verifier note:** Despite the evidence_in_bundle=false flag, the cited file is the same evidence_verifier.py that finding 5 keeps; the magic-number governance concern is consistent with the verifier's design and is verifiable from the same source.

## P2 findings (2)

### P2.1 — ALL_LENSES registry maps blind_spot to a function with a different signature than the other three lenses, yet it is stored in the same dict with no type-level distinction, making it callable with the wrong arguments if any caller iterates the dict uniformly.

- **Lens:** code_quality
- **File:** `src/black_heron/lenses/__init__.py` lines `L1-L18`
- **Confidence:** 0.70

**Evidence:**
```
ALL_LENSES = {
    "code_quality": run_code_quality,
    "governance": run_governance,
    "drift": run_drift,
    "blind_spot": run_blind_spot,
}
```
**Why it matters:** The comment documents the hazard but the design relies on every caller knowing to special-case blind_spot; a single `for name, fn in ALL_LENSES.items(): fn(ctx, client, tracker)` loop would crash or silently pass wrong args at runtime.
**Verifier note:** Real design hazard but theoretical (no caller in repo iterates uniformly); downgraded to P2 as the bundle excerpt acknowledges the signature mismatch is intentional.

### P2.2 — parse_findings uses `text.find("{")` and `text.rfind("}")` to extract JSON, which will silently produce corrupt JSON if the LLM output contains multiple top-level JSON objects or prose with curly braces before/after the intended payload.

- **Lens:** code_quality
- **File:** `src/black_heron/lenses/_common.py` lines `L30-L47`
- **Confidence:** 0.75

**Evidence:**
```
start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        sys.stderr.write(f"[bh:{lens}] no JSON block in lens output (len={len(text)})\n")
        return []
    payload = text[start:end + 1]
```
**Why it matters:** If the LLM wraps its JSON in markdown fences containing braces or emits explanatory prose with braces, the extracted substring may span unrelated brace pairs, causing json.loads to fail or parse a malformed object.
**Verifier note:** Real fragility but confidence below P1 floor; downgrade to P2.

## Rejected findings (transparency)

These were proposed by a lens but rejected by the adversarial verifier.

- *The PRICES dict uses model name keys like "claude-opus-4-6" and "claude-sonnet-4-6" that do not match the actual Anthropic API model identifiers (e.g., "claude-opus-4-20250514"), so PRICES.get(model) will always fall through to DEFAULT_PRICE for real API responses.* — rejected: Confidence 0.60 is below P1 floor of 0.70 and the finding itself flags uncertainty about what the SDK returns; speculative without evidence of actual fallthrough.
- *The `json` and `datetime` imports at the top of cli.py are unused — json is never called in the module body, and datetime/timezone are used only via the session module's own helpers.* — rejected: The finding's own uncertainty note admits cli.py may be longer than the excerpt; trivial linting issue and the claim is internally contradicted (datetime is used).
- *No `.env.example` file with placeholder values is committed to the repository.* — rejected: evidence_in_bundle=false absence claim with no verification that the file listing was actually inspected in the bundle; P2 governance polish at best.
- *The system prompts used by each lens are policy-bearing artifacts that carry audit methodology, severity definitions, and output schema, but none has a `version` field or any versioning identifier.* — rejected: evidence_in_bundle=false; the lens excerpts in the bundle would need to be inspected and the finding's evidence is paraphrased rather than quoted, making absence unverifiable here.
- *The audit decision-making pipeline does not persist an audit trail of the raw LLM responses (model name, prompt hash, raw response text, timestamp) for each lens invocation; only the parsed findings and final metrics are written to disk.* — rejected: evidence_in_bundle=false and the claim references session.py and write_report internals not in the loaded entry-points; P0 severity unjustified without verified evidence.
- *The Finding model has no explicit escalation verdict — valid severities are limited to `P0`, `P1`, `P2` with no `needs_human`, `escalate`, or `n/a` option to signal that the system cannot make a determination.* — rejected: evidence_in_bundle=false; _models.py not in loaded entry-points and the claim is design-philosophical rather than a defect against a stated requirement.
- *Hardcoded token pricing thresholds have no traceability to a source document or rubric field — the `PRICES` dict and `DEFAULT_PRICE` are inline magic numbers with only an informal comment ('snapshot 2026-05; verify before re-pricing').* — rejected: evidence_in_bundle=false and the cited comment 'verify before re-pricing' is itself the documented traceability marker; finding overstates the governance gap.

---

## Honest scope (v1.0)

Black Heron v1.0 ships with: 4 lenses (code_quality, governance, drift, blind_spot), adversarial Opus verifier with severity confidence floors, evidence-presence pre-check, entry-point full-content loading, versioned rubric, cost + time kill-switches, SARIF output. Honest gaps documented in `KNOWN_LIMITATIONS.md`. See `README.md` for v1.1 roadmap.