# Security Rules — Black Heron

> Secrets, .env, push protocol, deploy safety.
> Path scope: all of Black Heron.

## Hard Lines

- **NEVER hardcode secrets, tokens, keys, or passwords in code.** Law XII.
- **NEVER write to `.env`, credentials, or secret files.** `.env.example` only is committed.
- **NEVER log secrets** — even in debug output.
- **NEVER commit key material.** PreToolUse hook scans for `sk-ant-`, `ghp_`, `BEGIN RSA`, etc.
- **HTTPS only** for all external requests (Anthropic API, etc.).
- **Pin dependency versions** in `pyproject.toml` — no floating ranges (>=) without an upper bound.
- **.env files chmod 600** on any deployed/staging system. NEVER 644 (AKIRA S27 world-readable secrets).

## Push Protocol (Law XI)

- Local commits are routine.
- Remote push requires **explicit SHIKA authorization** — usually "push to GitHub" or equivalent.
- `scripts/hooks/block-git-push.sh` is a PreToolUse hook on Bash. Pattern `git\s+push` → exit 2 (HARD BLOCK).
- Override path 1: SHIKA edits `.claude/settings.local.json` to disable the hook for one session.
- Override path 2: SHIKA invokes the push command in a fresh dedicated session where the hook isn't loaded.
- Either way, the push is explicit, intentional, and documented.

## API Key Handling

- Source: `ANTHROPIC_API_KEY` env variable.
- Loaded via `python-dotenv` from `.env` if present.
- `.env` is gitignored. `.env.example` is committed with placeholder values:
  ```
  ANTHROPIC_API_KEY=sk-ant-...
  ```
- If a code path detects the API key starts with the placeholder prefix `sk-ant-...` literal, treat as misconfiguration and exit 1.

## Repo Scrub Discipline (from QURE clean-staging lesson)

Before any portfolio/public-facing repo push:
1. Run grep for person names, salary mentions, interview process language.
2. Run grep for proper-noun handles (lipakjosip, jesusamongai, etc.).
3. Verify no `.env` file exists in tracked files (`git ls-files | grep '.env$'`).
4. Verify no `.git.backup-*` artifacts committed.
5. Audit log evidence in commit messages (no "war room", "interview", "Round N" leakage).

For Black Heron specifically: SHIKA is the only proper noun that appears in this codebase. No exceptions.

## Hook Enforcement

- Hook-level enforcement > text rules (EZEKIEL evidence: text rules have 86% violation rate).
- BLOCK level (exit 2) > WARN level (which gets ignored).
- Add hooks at the boundary of dangerous operations, not after the fact.

### Required hooks (Phase C deliverable)

```
PreToolUse / Bash       block-git-push.sh        (exit 2 on `git push`)
PreToolUse / Write|Edit scan-secrets.sh          (exit 2 on key patterns)
PreToolUse / Bash       block-catastrophic.sh    (exit 2 on `rm -rf /`, etc.)
PreCompact              pre-compact-flush.sh     (save state at 85% context)
SessionEnd              uncommitted-warning.sh   (warn if dirty tree)
```

## Cross-References

- `docs/LAW.md` Laws XI, XII — codified here
- `core.md` — workflow context
- `scripts/hooks/` — hook implementations (Phase C)
- `.claude/settings.json` — hook registry (Phase C)
