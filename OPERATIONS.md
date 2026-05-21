# Operations — Black Heron v1.1

How to install, run, and operate Black Heron in real workflows.

## Quick install

```bash
git clone <repo-url> ~/Desktop/black-heron
cd ~/Desktop/black-heron
cp .env.example .env             # edit and add ANTHROPIC_API_KEY
pip install -e .                 # editable install
black-heron --help               # verify CLI works
```

## First run

```bash
# Audit any local repo
black-heron /path/to/some/repo --out audit/

# Read the report
cat audit/REPORT.md
```

Expected: 2-5 minutes wall time, $0.50–$2.00 cost (Opus 4.6 lens + Opus 4.7 verifier), three artifacts in `audit/`.

## Common workflows

### Pre-commit audit on your own repo

```bash
black-heron . --out .bh-audit/ --cost-cap 1.0
cat .bh-audit/REPORT.md
```

### Audit someone else's PR

```bash
git clone <pr-fork-url> /tmp/audit-target
git -C /tmp/audit-target checkout <branch>
black-heron /tmp/audit-target --out /tmp/audit-report/
```

### Quick scan (1 lens, no verifier)

Via MCP server (after install-mcp.sh):

```
mcp__black_heron__quick_scan({"repo_path": "/path/to/repo"})
```

Or via CLI:

```bash
black-heron . --lenses code_quality --cost-cap 0.30
```

### Verify external findings

If you have findings from another tool (linter, scanner) and want BH's adversarial verifier to filter noise:

```bash
black-heron-verify --findings external-findings.json --repo /path/to/repo
```

(Or via MCP: `mcp__black_heron__verify_findings`.)

### Self-audit (recursive validation)

```bash
BH_ENV_FILE=~/.config/anthropic.env bash scripts/self-audit.sh
```

Updates `SELF-AUDIT-LATEST.md` in the BH repo root. Commit it to ship transparency about BH's own state.

## Install MCP server (Claude Code integration)

```bash
bash scripts/install-mcp.sh
# Restart Claude Code
# Then in any session: mcp__black_heron__audit_repository, etc.
```

This patches `~/.claude.json` to register Black Heron as an MCP server.

## Install hooks

```bash
bash scripts/install-hooks.sh
```

Copies the 5 BLOCK-level hooks to `~/.claude/hooks/black-heron/`. After install, follow on-screen prompts to merge the hook block into your `.claude/settings.json` or project-level settings.

## CLI flags reference

```
black-heron <repo_path> [options]

  --lenses <csv>          Comma-separated lenses. Default: all four.
                          Valid: code_quality, governance, drift, blind_spot

  --out <dir>             Output directory. Default: ./audit/

  --rubric <path>         Custom rubric.json. Default: bundled rubric.default.json

  --env <path>            Path to .env file with ANTHROPIC_API_KEY

  --cost-cap <usd>        Override rubric cost cap (default $2.00)

  --time-cap <sec>        Override rubric time cap (default 300s)

  --dry-run               Print prompt that would be sent; no API calls
```

## MCP tool reference

After `install-mcp.sh`:

```
mcp__black_heron__audit_repository(repo_path, lenses?, cost_cap_usd?, time_cap_seconds?, out_dir?)
mcp__black_heron__verify_findings(findings_json_path, repo_path)
mcp__black_heron__quick_scan(repo_path)
```

## Custom rubric

Copy `src/black_heron/rubric.default.json` somewhere, edit, point to it:

```bash
black-heron /target --rubric ~/.config/bh-strict-rubric.json --out audit/
```

You can adjust:
- `severity_confidence_floors` (P0/P1/P2 minimum confidence)
- `severity_max_per_run` (per-severity caps)
- `kill_switch_total_findings_cap` (abort threshold)
- `lens_enabled` (toggle individual lenses)
- `cost_cap_usd`, `time_cap_seconds`
- `ignore_patterns` (extra directories to skip)

**IMPORTANT:** bump `rubric_version` whenever you change `severity_confidence_floors` (Law X). Floor changes are policy changes.

## Calibration data

After every run, BH writes to `~/.black-heron/sessions/<timestamp>.json` and updates `~/.black-heron/calibration.json` with running aggregate metrics. Inspect with:

```bash
cat ~/.black-heron/calibration.json
ls ~/.black-heron/sessions/
```

Calibration is volatile state — it grows monotonically. Trim by deleting individual session JSON files if needed (calibration.json must be regenerated manually if you do this).

## Troubleshooting

### "ANTHROPIC_API_KEY missing"
- Set env var directly, or
- Create `.env` with `ANTHROPIC_API_KEY=sk-ant-...`, or
- Pass `--env <path>` flag

### Cost cap exceeded mid-audit
- Default is $2. Bump via `--cost-cap 5.0` or edit rubric.
- Note: cap checks happen BETWEEN lens calls, so the call that pushed over is allowed to complete. Effective cap is "no NEW call after exceeded."

### Verifier output unparseable
- Fallback: BH preserves raw findings with confidence capped at 0.5, plus stderr warning.
- Likely cause: very large finding set hit max_tokens=16384. Workaround: split lenses across runs.

### `python3` is MS Store stub on Windows
- BH scripts use functional detection. They'll find `py` first on Windows.
- If you still hit issues, set `BH_PYTHON=py` explicitly (planned v1.2 — not yet supported).

### Hooks not firing
- Confirm `.claude/settings.json` is loaded (check Claude Code logs).
- Hooks run from the working directory of the Bash/Write tool, not from BH repo root. Make sure the hook scripts are reachable.
- Test a hook manually: `echo '{"tool_input":{"command":"git push origin main"}}' | bash scripts/hooks/block-git-push.sh`

## See also

- `CLAUDE.md` — identity + constraints
- `LAW.md` — sacred laws
- `README.md` — public-facing intro
- `KNOWN_LIMITATIONS.md` — what BH doesn't do
- `CHANGELOG.md` — version history
