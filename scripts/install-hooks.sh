#!/usr/bin/env bash
# Install Black Heron hooks into ~/.claude/hooks/ and merge into user-level settings.json.
# Usage: bash scripts/install-hooks.sh
# Idempotent: safe to re-run.

set -eu

BH_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER_HOOKS_DIR="${HOME}/.claude/hooks/black-heron"
USER_SETTINGS_LOCAL="${HOME}/.claude/settings.local.json"

echo "Black Heron hook installer"
echo "  BH repo:     $BH_ROOT"
echo "  Target dir:  $USER_HOOKS_DIR"
echo ""

# 1. Create the target hooks dir
mkdir -p "$USER_HOOKS_DIR"

# 2. Copy hook scripts
for script in block-git-push.sh block-catastrophic.sh scan-secrets.sh pre-compact-flush.sh uncommitted-warning.sh; do
  src="$BH_ROOT/scripts/hooks/$script"
  dst="$USER_HOOKS_DIR/$script"
  if [ -f "$src" ]; then
    cp "$src" "$dst"
    chmod +x "$dst" 2>/dev/null || true
    echo "  installed $script"
  else
    echo "  WARN: missing $src"
  fi
done

echo ""
echo "Hooks installed at $USER_HOOKS_DIR"
echo ""
echo "Next step: register these hooks in your Claude Code settings."
echo "Either:"
echo "  a) Copy $BH_ROOT/.claude/settings.json into your project's .claude/, OR"
echo "  b) Add the hook block to your $USER_SETTINGS_LOCAL (user-level overrides)"
echo ""
echo "See $BH_ROOT/docs/OPERATIONS.md for the full procedure."
