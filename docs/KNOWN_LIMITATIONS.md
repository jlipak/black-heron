# Known Limitations — Black Heron v1.0

Honest documentation of what Black Heron does *not* do yet, what known failure modes exist, and which of those later releases resolved (marked inline). Apollo-grade self-audit: a tool that audits other repos must also audit itself.

## v1.0 design boundaries (will not change in this version)

1. **Sample-based context for non-entry-point files.** Discovery loads up to 30 files under 4KB as samples + all detected entry-point files with up to 10KB each. Files outside this set are visible to lenses via the file listing only. v1.0 mitigates the resulting absence-of-evidence failure mode with `absence_claim: true` flags and post-filter severity floors, but does not eliminate it. For repos > 200 files, this is a real limitation.

2. **Entry-point detection is pattern-based.** The `_detect_entry_role` function in `discovery.py` recognises `package.json`, `tsconfig.json`, `index.ts`, `__init__.py`, `main.py`, server entry-points, build configs, and `*.rubric.json` style policy files. Custom entry-points (e.g. a project that puts its bootstrap in `core/bootstrap.py`) are not recognised without rubric customization. v1.1 candidate: rubric-driven entry-point patterns.

3. **No multi-lens parallelism.** *(resolved in 1.2: `--parallel`, on by default)* Lenses run sequentially. On a 116-file repo this is ~4 minutes wall time. Async parallel execution is v1.1.

4. **No baseline persistence.** *(resolved in 1.3.1: `--baseline previous.json`)* Each run is fresh. v1.1 candidate: `--baseline previous.json` for drift-over-time comparison.

5. **No content-hash caching.** *(resolved in 1.3.2, extended to the MCP server in 1.3.3)* Re-running on an unchanged repo costs the same as the first run. Note: in-API prompt caching IS enabled (`cache_control: ephemeral`), so within a single audit, subsequent lenses share the system prompt cache. Cross-audit caching is v1.1.

6. **Verifier uses 16K max_tokens.** Adequate for 40-finding audits. Very large repos may produce more findings than fit; the lens kill-switch (50 P0/P1 cap) catches this case but verifier output may still truncate on edge cases. Workaround: split lenses across multiple runs.

7. **SARIF output is minimal viable.** Conforms to SARIF 2.1.0 enough for GitHub Code Scanning import, but doesn't populate every optional field (e.g. `partialFingerprints`, `relatedLocations`). v1.1 candidate: extended SARIF metadata.

8. **No live GitHub URL ingest.** v1.0 audits local paths only. v1.1: `black-heron audit https://github.com/owner/repo` clones to temp + audits.

## Known failure modes observed in testing

### FM1 — Lens reasons about absence from incomplete sample

**Symptom:** Lens raises a finding of the form "file X is missing" when file X is actually present in the repo but not in the 30-file sample.

**Mitigation in v1.0:** Lens system prompts now flag `absence_claim: true` and require checking the file listing first. Verifier applies extra skepticism to `absence_claim` findings. Entry-point files (index.ts, package.json, etc.) are loaded full-content so the lens has cross-file context for entry-point reasoning.

**Residual risk:** A claim about a non-entry-point file being missing may still slip through. Honest target: reduce FP rate from ~13% (v0.1 measured on a client repo) to ~5% (v1.0 measured, n=3 verified, 1 rejected on same repo).

### FM2 — Lens reasons about inline registration patterns from file listing alone

**Symptom:** Lens sees `src/tools/` contains only `foo.ts` but the system registers `bar` and `baz` inline in `index.ts`. Lens raises a "missing tool files" finding.

**Mitigation in v1.0:** `index.ts`-style entry-points are loaded with full content. Lens sees the inline registrations and does not raise.

**Residual risk:** If the registration pattern lives outside the entry-point patterns BH detects, the failure mode returns. Rubric customization is the path forward.

### FM3 — Verifier output truncates on large finding sets

**Symptom:** With > 20 findings, the verifier's JSON output can exceed `max_tokens=16384` and the parser fails. v0.1 returned 0 verified / 0 rejected; v1.0 raises max to 16K and adds a parser fallback that preserves raw findings as "best-effort verified" with confidence cap 0.5.

**Mitigation in v1.0:** Cap raised; fallback path documented. The 50-finding kill-switch normally fires first, but the fallback is the safety net.

### FM4 — Theoretical issues raised as observable

**Symptom:** Lens raises "this could fail if X" without showing X happens in the code path. Verifier originally accepted these.

**Mitigation in v1.0:** Each lens system prompt now includes "Distinguish theoretical from observable. Only raise issues where the cited evidence shows the issue is observable in the code path, not merely a hypothetical edge case."

**Residual risk:** Lens interpretation of "observable" is subjective. Verifier carries the filtering load on edge cases.

### FM5 — Evidence fabrication

**Symptom (documented in `lesson_audit_verification.md`):** Agent quotes "verbatim" from a file it never actually read. The quote is plausible but not present in the source.

**Mitigation in v1.0:** `evidence_verifier.py` runs before the verifier and substring-checks each finding's `evidence` field against the input bundle (samples + entry-points). Findings whose evidence is not present are flagged `evidence_in_bundle: false` and the verifier prompt explicitly invites REJECT on those grounds.

**Residual risk:** Short evidence quotes (< 20 chars) skip the substring check (too noisy). Evidence that the lens paraphrased rather than quoted verbatim will fail the check even when the underlying claim is sound. Trade-off: prefer false-rejection over false-acceptance.

### FM7 — Drift identity heuristic is line-position-tolerant (v1.3.1)

**Symptom:** The drift identity hash uses only the *start* line (collapses `"L42-L88"` and `"42"` to the same key). A finding that moves from line 10 to line 110 in the same file, same lens, same first-8-words of claim, will be flagged as `persisting`, not as a real change.

**Mitigation in v1.3.1:** This is a deliberate trade-off. Source-line drift is extremely noisy in real repos (adding an import shifts every subsequent finding's line number); a strict-line identity heuristic would mark nearly every persisting finding as `closed` + `new` every audit. Optional `--strict-line-identity` mode is a v1.4 candidate.

**Residual risk:** A finding that genuinely moved to an unrelated code path within the same file (e.g., refactored from `def parse(x)` at L10 to a new `def parse(y)` at L110 with a different semantics) will be silently mislabeled as `persisting`. Verify in `git log`.

### FM8 — Closed findings not correlated with git log (v1.3.1)

**Symptom:** A finding shows up as `closed` because the current audit didn't produce it — but the cause might be the lens being tighter (or noisier) on this run, not the code actually changing. Apollo-reverse risk.

**Mitigation in v1.3.1:** The `Closed findings` section in `REPORT.md` carries an explicit reader-facing note: "Closed findings should correspond to fixes in `git log`. If you don't see a commit between baseline and now that touches the referenced file, the finding may have been masked rather than fixed — investigate before treating as resolved."

**Residual risk:** Black Heron doesn't itself fetch the git log diff between baseline and now. v1.4 candidate: auto-link closed findings to commits that touched the referenced file between the baseline timestamp and now.

### FM9 — Cache covers CLI only; MCP server still calls API every time *(RESOLVED in v1.3.3)*

~~v1.3.2: Cache was wired in `cli.py` only. `mcp_server.py` lens calls (`audit_repository` and `quick_scan` tools) hit the API every invocation regardless of repo state.~~

**Resolved in v1.3.3:** `mcp_server.py` now uses the same `run_lens_with_cache` wrapper as the CLI. Both `audit_repository` and `quick_scan` tools accept optional `no_cache` and `cache_dir` args. The `metrics.cache` field is populated in the MCP report output too.

### FM10 — Cache key cannot detect lens prompt edits outside the version-bump path (v1.3.2)

**What happens.** Cache key includes `rubric_version` and `lens_model` but not a hash of the lens prompt module itself. If you edit `src/black_heron/lenses/code_quality.py` to change the lens prompt without bumping the rubric or model, the cache continues to serve the old result for unchanged repos.

**Why.** Hashing every lens module file would invalidate the cache on every developer edit (including comment-only changes), which defeats the purpose. The contract is: lens behavior is treated as immutable per `(rubric_version, lens_model)`.

**Mitigation.** Use `--no-cache` after editing lens prompts, or bump `rubric_version` to force a fresh run, or run `purge_cache(cache_dir)` from a Python REPL.

**Residual risk:** Quiet stale results for the engineer who edits lens prompts during development. Stable users (no lens prompt edits) are unaffected.

### FM6 — Enrichment as a fabrication surface (v1.3)

**Symptom:** v1.3 enrichment pipes external MCP content into the prompt bundle. A lens could mistakenly cite an enrichment block as in-repo evidence — fabricating cross-file context that doesn't live in the actual repo.

**Mitigation in v1.3:**
- Each enrichment block is delimited by a clearly-labeled section header (`## External library docs (via context7)`, etc.)
- The prompt builder includes an explicit discipline note: "Treat them like documentation, NOT like in-repo evidence: a finding's `evidence` field must still be a verbatim substring of an in-repo file unless the finding explicitly cites an enrichment block and the claim is about that external resource itself."
- `evidence_verifier.py` substring-matches against the WHOLE prompt context (samples + entry-points + enrichments), so a finding whose evidence quotes an enrichment block won't be flagged as fabricated — but the verifier sees the source ("evidence in samples vs in enrichment block") and can downgrade enrichment-only findings.

**Residual risk:** An aggressive lens could quote a context7 docs block, claim it's an in-repo issue, and pass evidence-presence. Verifier is the final filter. Honest target: keep enrichment opt-in (`--enrich none` default) so the failure surface is only exposed when the user has consciously elected it.

## Cost calibration

Per-audit cost on a small TypeScript repo (~116 files, 4 lenses + verifier):
- Without prompt caching: ~$0.70
- With ephemeral cache (5-min TTL, default): ~$0.55 first run, ~$0.30 subsequent runs within 5 min
- 1-hour cache TTL beta (requires explicit header opt-in, not yet enabled): would extend the discount to ~$0.30 for any audit within 1 hour

v1.1 target: enable 1-hour beta cache header by default; document in README.

## What we measure ourselves on

For each reference audit we ship (the client-repo audits left the tree in 1.4.0; `examples/self-audit-*/` remains):
- Verified count
- Rejected count
- Manual-review FP rate (on findings that survive verifier)
- Cost + wall time

v0.1 on a client compliance repo: 15 verified, 10 rejected, 2 manual FPs → ~13% FP rate after verifier.
v1.0 on the same repo: 2 verified, 1 rejected, 0 manual FPs → 0% FP rate after verifier (n too small to be representative — collect more data points).

Honest target: across 5 diverse repos averaged, < 10% FP rate post-verifier.
