# Operations — Black Heron v1.3.1

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

### Audit-over-time with `--baseline` (v1.3.1 / Phase R)

Black Heron answers "what changed since the last audit?" deterministically — no LLM, no extra spend.

```bash
# Audit once, keep findings.json as the baseline
black-heron /path/to/repo --out audit/2026-05-21/

# Time passes, fixes ship, drift accumulates
# Re-audit with the prior findings as baseline
black-heron /path/to/repo \
    --baseline audit/2026-05-21/findings.json \
    --out audit/2026-06-04/
```

`REPORT.md` will gain a "Drift since baseline" section directly under the Summary. Four buckets:

| Bucket | What it means | Governance signal |
|---|---|---|
| **New** | Identity-hash absent from baseline, present now | New attack surface introduced this cycle |
| **Closed** | Present in baseline, absent now | Verify in `git log` — closed without a commit may indicate masking |
| **Persisting** | Same identity + same severity + same evidence | Each persisting P0/P1 = one audit cycle of unfixed compliance debt |
| **Drifted** | Identity match but severity / confidence / evidence shifted | De-escalation without fix-commit often = LLM noise; investigate |

Identity hash: `sha256(lens | file | start-line | first-8-words(claim))`. Collapses LLM-rephrased claims to the same key as long as the first 8 claim words and the same lens / file / start-line agree.

Drift triggers (any one moves a finding to `drifted`):
- severity change (any direction)
- `|Δconfidence| > 0.2`
- evidence string is not a substring-equal match (substring counts as same — broadening/narrowing the quote isn't drift)

Missing / malformed baseline = `REPORT.md` shows the skip reason in the drift section; audit completes normally. The drift compute is pure set-arithmetic — adds essentially no wall time to the audit.

### Content-hash cache (v1.3.2 / Phase S)

Black Heron caches lens outputs at `~/.black-heron/cache/`. On a re-audit, if the repo content + lens model + rubric version are unchanged, the prior lens output is replayed without an Anthropic API call.

```bash
# First run — cache is empty, all lenses call the API
black-heron /path/to/repo --out audit/run1/
# header: Cache: ~/.black-heron/cache (ctx hash 4f7a1b3c0d2e)

# Second run, no code changes — every lens hits the cache, zero API spend
black-heron /path/to/repo --out audit/run2/
# Metrics line: Cache: 4 hit / 0 miss (dir: ~/.black-heron/cache)

# Bypass when you suspect drift (lens prompt edit, model rollback, paranoia)
black-heron /path/to/repo --out audit/run3/ --no-cache
# Metrics line: Cache: disabled this run (4 lens calls bypassed)

# Override the cache location (CI, separate workspaces, etc.)
black-heron /path/to/repo --out audit/run4/ --cache-dir /tmp/my-cache/
```

Key composition: `sha256(ctx_hash | lens_name | lens_model | rubric_version | prior_findings_hash)`.

| Cause of miss | Behavior |
|---|---|
| First run on a repo | Miss, then write — subsequent runs hit |
| Any file content change | `ctx_hash` shifts — full miss for all lenses |
| Lens model upgrade (e.g., 4.6 → 4.7) | Per-lens miss when `lens_model` changes |
| Rubric version bump | All lenses miss (intentional — rubric edits should re-validate) |
| Corrupted cache file on disk | Logged to stderr, treated as miss, lens re-runs |
| `blind_spot` lens, prior findings changed | Miss (prior_findings_hash differs) |

What it does NOT detect:
- Lens prompt code edits without a rubric bump (FM10). Workaround: `--no-cache` or bump rubric_version.
- The MCP-server lens path (FM9). Workaround: use the CLI.

### Audit with external MCP enrichment (v1.3 / Phase G)

```bash
# Opt in to all four enrichers; missing binaries skip silently
black-heron /path/to/repo --enrich all --out audit/

# Pin which enrichers run
black-heron /path/to/repo --enrich context7,firecrawl --out audit/

# Custom MCP config (per-server command, env, timeout, caps)
black-heron /path/to/repo --enrich all --mcp-config ~/.black-heron/mcp.json
```

What each enricher contributes:

| Enricher | Input it extracts | What it asks the MCP | Where it lands in the prompt |
|---|---|---|---|
| context7 | dependencies in pyproject/package/requirements | `resolve-library-id` + `query-docs` | "External library docs (via context7)" block |
| firecrawl | URLs in README + docs (priority pool) | `firecrawl_scrape` | "External URLs (via firecrawl)" block |
| playwright | URLs in README + docs | `browser_navigate` + `browser_snapshot` | "Rendered web entry-points (via playwright)" block |
| sequential-thinking | repo metadata (no source) | `sequentialthinking` | "Architectural reasoning (via sequential-thinking)" block |

Install MCP servers (any subset) before invoking BH:

```bash
npx -y @upstash/context7-mcp --help
npx -y @modelcontextprotocol/server-sequential-thinking --help
npx -y firecrawl-mcp --help
npx -y @playwright/mcp --help
```

If a binary isn't on `PATH`, BH logs the skip in `REPORT.md` under "MCP enrichment" and keeps going. The lens prompts still contain a discipline note: enrichment is advisory context — a finding's `evidence` field must still be a verbatim substring of an in-repo file unless the claim is specifically about the external resource.

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
