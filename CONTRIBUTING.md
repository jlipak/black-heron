# Contributing — Black Heron

Slim guide. Mostly: read `docs/LAW.md`, follow the 15 sacred laws.

## Before opening a PR

1. Run `bash scripts/self-audit.sh` — confirm 0 P0 findings remain.
2. Bump `pyproject.toml` version if your change is user-visible.
3. Update `CHANGELOG.md` with your change under the appropriate heading.
4. If you changed any lens system prompt: re-run smoke audit on the QURE clean staging example and confirm FP rate hasn't regressed.

## What changes are easy to land

- New lens additions (must include matching `.claude/agents/bh-<name>.md`)
- Bug fixes with reproduction steps in PR description
- Documentation improvements
- New rubric variants in `rubric.default.json` schema (additive only)

## What changes need discussion

- Changes to `docs/LAW.md` (sacred laws are evidence-backed; new evidence needed)
- Changes to severity confidence floors (Law X — bump `rubric_version`)
- Changes to lens system prompts (must re-baseline FP rate)
- New external dependencies in `pyproject.toml`

## What changes will not be accepted

- Removing the adversarial verifier
- Adding lens execution paths that bypass the verifier
- Hardcoded secrets in any file
- Per-user paths in committed scripts
- Cost-cutting that uses Sonnet/Haiku as default for substantive lens reasoning (Law IX)

## Style

- Python 3.11+. Type hints everywhere. Pydantic v2 for schemas.
- See `.claude/rules/python.md` for style details.
- Comments: minimal. Only when WHY is non-obvious. Never explain WHAT well-named code already does.

## Tests (when we have them, v1.2)

Currently BH has no unit tests — smoke audits + self-audit cover validation. v1.2 will add `tests/` with pytest. PRs that add code should not be blocked on adding tests until the test infrastructure lands.

## Filing issues

- Repro steps + actual audit output (REPORT.md fragment) > "BH said wrong thing"
- Include calibration.json or sessions/<ts>.json from the failing run when relevant
- Sensitive info? Redact before filing.

## See also

- `docs/LAW.md` — sacred laws
- `ARCHITECTURE.md` — module layout + data flow
- `docs/OPERATIONS.md` — install + run
- `docs/KNOWN_LIMITATIONS.md` — gaps acknowledged
