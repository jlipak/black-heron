# Architecture — Black Heron v1.1

Technical deep dive. Companion to `README.md` (public) and `docs/PHILOSOPHY.md` (rationale).

## System overview

Black Heron is a multi-stage Claude-API pipeline that audits local repositories and produces three artifacts (`REPORT.md`, `findings.json`, `findings.sarif`). It is invokable in three modes:

1. **CLI** — `black-heron <repo>` for one-shot audits from a terminal.
2. **MCP server** — `mcp__black_heron__audit_repository` from inside any Claude Code session.
3. **Agentic orchestrator** — `.claude/agents/bh-orchestrator.md` for tool-augmented audits with sub-agents that have Read/Glob/Grep/Bash access.

## Data flow

```
repo_path
   │
   ▼
discovery.build_context()
   ├── file_listing        ← authoritative ("if not here, doesn't exist")
   ├── sample_files        ← coverage (≤30 × ≤4KB)
   ├── entry_points        ← full content (≤10KB each, role-tagged)
   ├── git_log_recent      ← last 30 commits oneline
   └── todo_count          ← TODO|FIXME|XXX|HACK across source
   │
   ▼
RepoContext (Pydantic schema)
   │
   ▼ pass to lens system prompts (cache_control: ephemeral)
   │
┌──┴─── lens pass 1 (Opus 4.6, sequential in CLI / parallel in agentic) ───┐
│   code_quality   →  findings[]                                            │
│   governance     →  findings[]                                            │
│   drift          →  findings[]                                            │
└──────────────────────────────────────────────────────────────────────────-┘
   │
   ▼ collect findings_so_far for second pass
   │
┌──┴─── lens pass 2 (Opus 4.6) ─┐
│   blind_spot ← reads findings_so_far + ctx → meta-intersection findings  │
└──────────────────────────────────────────────────────────────────────────-┘
   │
   ▼ all_findings
   │
evidence_verifier.check_evidence_in_context()
   │
   └─ {finding_index: evidence_in_bundle_bool}
   │
   ▼ (flags propagated to synthesis prompt)
   │
synthesis.synthesize() (Opus 4.7, 16384 max_tokens)
   ├── Kill-switch: abort if total findings > rubric.kill_switch_total_findings_cap
   ├── Adversarial KEEP / REJECT / DOWNGRADE per finding
   ├── Severity confidence floors applied post-LLM
   └── Fallback: raw-preserve if verifier output unparseable
   │
   ▼ VerifierResult { verified: [...], rejected: [...] }
   │
report.write_report()
   ├── REPORT.md         (human-readable, volume-calibrated summary)
   ├── findings.json     (structured, metrics + verified + rejected)
   └── findings.sarif    (SARIF 2.1.0, GitHub Code Scanning compat)
   │
   ▼
session.write_session()
   ├── ~/.black-heron/sessions/<ts>.json  (per-run record)
   └── ~/.black-heron/calibration.json    (running aggregate metrics)
```

## Module layout

```
src/black_heron/
├── __init__.py
├── _models.py            Finding, EntryPoint, RepoContext, Rubric (Pydantic v2)
├── discovery.py          File walk + entry-point detection + git log + TODO scan
├── rubric.py             Versioned rubric loader (validates schema_version)
├── rubric.default.json   Bundled default policy
├── cost_tracker.py       Per-call cost accumulator, price table, cap enforcement
├── evidence_verifier.py  Pre-LLM substring check (anti-fabrication, Law I)
├── synthesis.py          Adversarial Opus 4.7 verifier + confidence floors
├── report.py             Markdown + JSON + SARIF writer
├── session.py            Per-run session record + calibration.json update
├── cli.py                Click CLI entrypoint (CLI mode)
├── mcp_server.py         stdio JSON-RPC server (MCP mode)
└── lenses/
    ├── __init__.py       Heterogeneous registry — see _common.py docstring
    ├── _common.py        Shared prompt builder + JSON parser with stderr logging
    ├── code_quality.py   Senior-PR-review lens (Opus 4.6)
    ├── governance.py     Versioning + audit-trail + escalation lens (Opus 4.6)
    ├── drift.py          Promise-vs-delivery lens (Opus 4.6)
    └── blind_spot.py     Meta-intersection lens, reads findings_so_far (Opus 4.6)
```

## Model strategy

| Component | Model | Rationale |
|---|---|---|
| 4 lenses | `claude-opus-4-6` | Capability sufficient for structured-output lens work. Cheaper Opus tier. |
| Verifier | `claude-opus-4-7` | Latest model, different checkpoint than lenses → different blind spots (Apollo lesson) |
| Fallback | `claude-sonnet-4-6` | `--budget-mode` only. Default never engages Sonnet. |
| Helper | N/A in v1.1 | Haiku is not used. |

Cost per audit at v1.1 defaults: ~$1.50-3.00 depending on repo size + entry-point count. Cache_control: ephemeral on lens system prompts provides ~30% reduction within a single audit (lens 2-4 share cache from lens 1).

## Pydantic schemas (load-bearing)

```python
class Finding(BaseModel):
    lens: str
    severity: Literal["P0", "P1", "P2"]
    file: str
    lines: str
    claim: str
    evidence: str          # MUST quote verbatim; checked by evidence_verifier
    why_it_matters: str
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty_reason: str | None = None   # REQUIRED when confidence < 0.6
    absence_claim: bool = False             # REQUIRED true for "X is missing" claims

class EntryPoint(BaseModel):
    path: str
    role: Literal["package_manifest", "language_config", "build_config",
                  "module_init", "cli_entry", "server_entry", "rubric_or_policy"]
    content: str           # capped 10KB
    truncated: bool = False

class RepoContext(BaseModel):
    path: str
    file_count: int
    primary_language: str
    file_listing: list[str]
    sample_files: dict[str, str]
    entry_points: list[EntryPoint]
    git_log_recent: list[str]
    todo_count: int

class Rubric(BaseModel):
    rubric_version: str
    schema_version: str = "1.0.0"
    severity_confidence_floors: dict[str, float]
    severity_max_per_run: dict[str, int]
    kill_switch_total_findings_cap: int
    lens_enabled: dict[str, bool]
    cost_cap_usd: float
    time_cap_seconds: int
    ignore_patterns: list[str]
```

## Kill-switches

Three layers, all configurable via `rubric.default.json`:

1. **Total findings cap** (default 50 P0+P1) — synthesis aborts if exceeded. Lens prompt has drifted.
2. **Cost cap** (default $2/audit) — CLI checks `tracker.exceeded()` between lens calls. Aborts before next call if exceeded.
3. **Time cap** (default 300s/audit) — CLI checks wall time between lens calls.

All three are graceful: write whatever was produced before abort, plus a "kill-switch triggered" entry in REPORT.md.

## Caching

- **Ephemeral 5-min cache** on lens + verifier system prompts. Set via `cache_control: ephemeral` in Anthropic API messages.create call.
- First lens (cold cache) pays full token cost. Lenses 2-4 read system from cache at ~10% of cold price.
- Verifier system prompt cached separately (separate cache key).
- 1-hour TTL beta is a v1.2 candidate (requires `anthropic-beta` header opt-in).

## Hook integration (defense in depth)

`.claude/settings.json` registers 5 hooks at standard Claude Code lifecycle points:

| Event | Hook | Behavior |
|---|---|---|
| PreToolUse / Bash | `block-git-push.sh` | exit 2 on `git push` (override: `BH_ALLOW_PUSH=1`) |
| PreToolUse / Bash | `block-catastrophic.sh` | exit 2 on `rm -rf /`, `dd to /dev/sd*`, fork bomb, power cmd |
| PreToolUse / Write\|Edit | `scan-secrets.sh` | exit 2 on `sk-ant-`, `ghp_`, `BEGIN ... KEY`, etc. |
| PreCompact | `pre-compact-flush.sh` | flush BH state to `~/.black-heron/sessions/last-flush.json` |
| SessionEnd | `uncommitted-warning.sh` | soft warning if git diff non-empty |

All hooks are BLOCK-level (exit 2) where applicable. WARN-level was empirically measured at 86% violation rate (EZEKIEL evidence) so we don't use it.

## Memory + persistence

`~/.black-heron/` layout (created on first audit):

```
~/.black-heron/
├── sessions/
│   └── <timestamp>.json           one per audit run
├── audits/                         (reserved; v1.2 will write per-audit archives here)
├── calibration.json                running aggregate metrics
└── last-flush.json                 PreCompact hook output
```

Calibration tracks:
- `total_audits_run`
- `total_cost_usd`, `average_cost_usd`
- `total_wall_seconds`, `average_wall_seconds`
- `per_lens_total_findings`, `per_lens_average_findings`
- `verified_total`, `rejected_total`, `verifier_reject_ratio_average`

This gives BH cross-session memory. After 10 audits, you can see your average FP rate trend, your average cost, your per-lens hit rate.

## Identity & discipline layer

`CLAUDE.md` — identity, constraints, codebase map, validation commands.
`docs/LAW.md` — 15 sacred laws, each backed by a documented past failure (Apollo, a compliance build, AKIRA collapse).
`MEMORY.md` — operational state, NEXT list, calibration snapshot, 200-line hard cap.
`SESSION-DIGEST.md` — last-session handoff, read first at next boot.
`.claude/rules/{core,quality,security,python}.md` — behavioral rules per concern.
`.claude/skills/{boot,wrap,audit,research-swarm,self-audit}.md` — invokable skills.
`.claude/agents/bh-*.md` — sub-agent definitions for agentic mode.

This layer is the difference between "Python script that runs Claude" and "operational agent with discipline."

## Sub-agent dispatch (agentic mode)

When invoked via `bh-orchestrator`:

1. Orchestrator builds RepoContext (via Bash subprocess OR direct Glob+Read).
2. Dispatches 3 first-pass lenses in **parallel** (single message, 3 Agent calls).
3. After all three return, dispatches `bh-blind-spot` with findings_so_far.
4. After blind_spot returns, dispatches `bh-verifier` with all_findings + ctx + evidence_check flags.
5. Writes outputs via direct file writes (or via Bash → `black_heron.cli`).

Wall time in agentic mode ≈ max(lens_time) instead of sum, because of true parallelism in step 2.

Higher cost (sub-agent overhead + tool roundtrips) but higher precision (lenses can verify claims via Glob/Read before raising).

## See also

- `README.md` — public-facing
- `docs/PHILOSOPHY.md` — design rationale, canopy-feeding metaphor
- `CLAUDE.md` — identity + constraints
- `docs/LAW.md` — sacred laws
- `docs/OPERATIONS.md` — install + run procedures
- `docs/KNOWN_LIMITATIONS.md` — honest gaps
- `CHANGELOG.md` — version history
