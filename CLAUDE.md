# Black Heron — instructions for a coding agent working in this repo

Black Heron is a multi-lens repository audit tool: four LLM lenses, an adversarial verifier, Markdown/JSON/SARIF output. This file is for the agent that edits the code. The public entry point is `README.md`.

## Constraints

1. **Never fabricate evidence.** Every `evidence` field must substring-match the input bundle; `evidence_verifier.py` enforces it before the LLM verifier runs.
2. **Never push.** Local commits are routine; a push happens only when the owner says so, in his own terminal. `scripts/hooks/block-git-push.sh` blocks it at the tool boundary.
3. **Never run Haiku or Sonnet for substantive reasoning by default.** Lenses run on `claude-opus-4-8`, the verifier on `claude-opus-5` (Law VIII: different checkpoints, different blind spots). `--budget-mode` is the only way to put the lenses on `claude-sonnet-5`, and the user opts in explicitly.
4. **Never change `severity_confidence_floors` in `rubric.default.json` without bumping `rubric_version`.** Floor changes are policy changes.
5. **Never skip the verifier.** Even on empty lens output it runs and confirms emptiness.
6. **Never hardcode secrets.** The API key comes from `ANTHROPIC_API_KEY` only; `.env` is gitignored, `.env.example` is committed.
7. **Always report cost** at the end of every audit.
8. **Always keep rejected findings** in `REPORT.md` and `findings.json`.

The full set of fifteen rules with their evidence base is in `docs/LAW.md`.

## Who

- **The owner** (Josip Lipak, GitHub `jlipak`) sets direction, approves spend and pushes. He is not a coder: lead with the action, explain after, and push back once with the reason when something is wrong.
- **The agent** works autonomously inside the bounds of `docs/LAW.md` and `rubric.default.json`. "cook" / "do it" / "go" means execute; "suggest" / "plan" means present options and wait.
- Platform: Windows 11 with Git Bash, Python 3.11+. Use `python`, not `python3`.

## Validation

Free, non-interactive, no API calls. Run from the repo root; on Linux/macOS replace `.venv/Scripts/` with `.venv/bin/`.

```bash
python -m venv .venv                                  # once
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m ruff check src tests
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m black_heron.cli --version
.venv/Scripts/python -m black_heron.cli --help
```

All four commands must exit 0 before a change is "done". A live audit (`black-heron <repo>` or `bash scripts/self-audit.sh`) spends Anthropic credit and runs only on the owner's word.

## Codebase map

| Path | Role |
|---|---|
| `src/black_heron/cli.py` | Click entry point (`black-heron`), lens orchestration, cache, drift, session record |
| `src/black_heron/lenses/` | Four lens modules; `blind_spot` runs last and reads the others' findings |
| `src/black_heron/synthesis.py` | Adversarial verifier (KEEP / REJECT / DOWNGRADE) |
| `src/black_heron/evidence_verifier.py` | Deterministic substring pre-check before the LLM verifier |
| `src/black_heron/cost_tracker.py` | Price table and the cost kill-switch |
| `src/black_heron/cache.py`, `drift.py` | Content-hash cache and baseline drift, both deterministic |
| `src/black_heron/mcp_server.py` | stdio MCP server exposing `audit_repository`, `verify_findings`, `quick_scan` |
| `src/black_heron/mcp_consumers/` | Optional enrichment through external MCP servers |
| `src/black_heron/rubric.default.json` | Bundled rubric: floors, caps, lens toggles, ignore patterns |
| `tests/` | 103 pytest tests, no API calls |
| `docs/` | LAW, PHILOSOPHY, OPERATIONS, KNOWN_LIMITATIONS |
| `examples/self-audit-<date>/` | Committed showcase: Black Heron audited on itself |
| `skill/` | Markdown-only Claude Code skill distribution of the same prompts |
| `.claude/` | Rules, skills, agents and hooks for agentic use of this repo |
| `scripts/` | Hook scripts and installers, `self-audit.sh` |

`MEMORY.md` and `SESSION-DIGEST.md` are local session state and gitignored.

## How to work

- One concern per commit, specific paths, no `git add -A`. Commit after every meaningful change.
- Read before writing. New library API: check the docs, not memory. New model id: check the current Anthropic model list, never guess.
- A release bumps `version` in `pyproject.toml` (the package reads it at runtime), adds a `CHANGELOG.md` entry and tags `vX.Y.Z` locally. The push and the GitHub release are the owner's.
- Model ids, prices and `--budget-mode` are documented in `README.md` and `ARCHITECTURE.md`; keep the three in sync when they change.

## Cross-references

- `docs/LAW.md` — the fifteen rules with evidence
- `ARCHITECTURE.md` — module layout, data flow, model strategy
- `docs/OPERATIONS.md` — install, run, troubleshoot
- `docs/KNOWN_LIMITATIONS.md` — honest gaps
- `.claude/rules/` — core, quality, security and Python rules for agent sessions
