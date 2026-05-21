#!/usr/bin/env bash
# Register Black Heron as an MCP server in ~/.claude.json.
# Idempotent: safe to re-run.
#
# Usage: bash scripts/install-mcp.sh

set -eu

BH_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_JSON="${HOME}/.claude.json"

if [ ! -f "$CLAUDE_JSON" ]; then
  echo "WARN: $CLAUDE_JSON not found. Skipping."
  echo "Claude Code may not be installed, or the config lives elsewhere on this OS."
  exit 0
fi

# Portable Python launcher detection with functional test (Windows python3 stub guard)
PY=""
for cand in py python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then
    PY="$cand"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "ERROR: no functional Python interpreter found (py/python3/python)" >&2
  exit 1
fi

echo "Black Heron MCP installer"
echo "  BH repo:    $BH_ROOT"
echo "  Target:     $CLAUDE_JSON"
echo "  Python:     $PY"
echo ""

# Use Python to merge the mcpServers block (jq may not be present on Windows)
"$PY" - <<PY_EOF
import json
from pathlib import Path

config_path = Path(r"${CLAUDE_JSON}")
bh_root = Path(r"${BH_ROOT}").resolve()

cfg = json.loads(config_path.read_text(encoding="utf-8"))

# Ensure mcpServers key exists
mcp_servers = cfg.setdefault("mcpServers", {})

# Black Heron entry
mcp_servers["black-heron"] = {
    "command": "py",
    "args": ["-m", "black_heron.mcp_server"],
    "env": {
        "PYTHONPATH": str(bh_root / "src"),
    }
}

# Atomic write
tmp = config_path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
tmp.replace(config_path)

print(f"Registered 'black-heron' MCP server in {config_path}")
print(f"  command: py")
print(f"  args:    -m black_heron.mcp_server")
print(f"  PYTHONPATH: {bh_root / 'src'}")
print()
print("Restart Claude Code to pick up the new MCP server.")
print("Then in any session, you can call:")
print("  mcp__black_heron__audit_repository, verify_findings, quick_scan")
PY_EOF
