# Quality Rules — Black Heron

> Verification, FP discipline, post-build gates.
> Path scope: all source + audit code.

## The Verification Standard

### Verified or not done
- "Should work" is a lie (EZEKIEL Rule IV — 315 verify + 282 make_sure events).
- Run the actual command. Read the output. Don't assume green.
- If audit produces a report: open it, read summary, check at least one finding end-to-end against source.
- If config change: verify actual runtime behavior changed.

### What "done" means
- All 3 artifacts present: `REPORT.md`, `findings.json`, `findings.sarif`.
- Verification commands from `CLAUDE.md` Validation section all pass.
- Cost reported in REPORT.md.
- Verifier was actually invoked (not skipped on empty findings list).
- Self-audit clean (`scripts/self-audit.sh` returns no new P0).

## Adversarial Verifier Discipline

### Always run it (Law VI)
Even when raw lens output is empty. Verifier confirms emptiness. No exceptions.

### Different model than lens (Law VIII)
- Lenses: `claude-opus-4-6`.
- Verifier: `claude-opus-4-7`.
- Same model = shared blind spots (Apollo audit lesson).

### Evidence presence check (Law I)
- `evidence_verifier.py` runs BEFORE the LLM verifier.
- Substring-matches every finding's `evidence` field against input bundle.
- `evidence_in_bundle: false` flag → verifier strongly prefers REJECT.

### Confidence floors (rubric.default.json)
- P0 requires confidence ≥ 0.85.
- P1 requires confidence ≥ 0.70.
- P2 requires confidence ≥ 0.50.
- Below floor → post-filter downgrades or drops. No leakage.

## False-Positive Discipline

### Apollo benchmark
- 33-37% FP rate even with multi-agent cross-validation, NO verifier.
- With adversarial verifier: target < 15%, current measured 0% on the v1.0 reference audit (small sample n=2).
- Calibration tracking in `~/.black-heron/calibration.json` post Phase I.

### Theoretical vs observable (Law VII)
- Lens MUST raise only findings where cited evidence shows the issue is observable in the code path.
- "This could fail if X" without X visible in code = REJECT.
- Verifier flags theoretical-only findings for downgrade or reject.

### Absence claims (Law V)
- `absence_claim: true` flag REQUIRED if finding asserts something is missing.
- `why_it_matters` MUST state which authoritative source was checked (file_listing? entry_points? sample_files?).
- Verifier applies extra skepticism to absence claims.

## Post-Build Gates

### Before declaring a phase done
```
- [ ] All new files exist as expected (`ls` verify, not just "I wrote it")
- [ ] Import-test passes (`py -c "from black_heron.X import Y"`)
- [ ] Smoke test still passes (run audit on a known-good reference repo, compare to last known-good)
- [ ] No new P0 self-audit findings introduced
- [ ] MEMORY.md updated
- [ ] Commit staged with specific files only
```

### Before any release (v1.x bump)
```
- [ ] Self-audit clean (P0 = 0 or all documented in docs/KNOWN_LIMITATIONS.md)
- [ ] CHANGELOG.md updated
- [ ] README.md reflects new version
- [ ] pyproject.toml version bumped
- [ ] Tag created (locally, push only on the owner's go)
```

## Test Discipline

### What tests we should have (target v1.x)
- `tests/test_discovery.py` — entry-point detection on fixture repos
- `tests/test_evidence_verifier.py` — substring check edge cases
- `tests/test_cost_tracker.py` — price math
- `tests/test_synthesis.py` — fallback path (verifier unparseable output)
- `tests/test_report.py` — SARIF schema validation
- `tests/test_rubric.py` — load + validate

### What tests we have NOW (v1.1 in progress)
- Smoke tests via real audits on a reference repo (manual)
- Self-audit (post Phase I)

### Honest gap
Unit tests landed in v1.2 (`tests/`, 103 tests). Remaining gaps are in `docs/KNOWN_LIMITATIONS.md`.

## Cross-References

- `docs/LAW.md` Laws I, IV, V, VI, VII, VIII — codified here
- `docs/KNOWN_LIMITATIONS.md` — gaps
- `core.md` — workflow context
