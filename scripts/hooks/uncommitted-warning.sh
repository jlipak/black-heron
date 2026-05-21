#!/usr/bin/env bash
# SessionEnd hook. Warn if there are uncommitted changes when session ends.
# Soft warning only (exit 0) — does not block, just reminds.
# Law XIII — always commit after meaningful changes.

set -u

# Try to detect project dir from input or env
INPUT=$(cat 2>/dev/null || echo "{}")
PROJECT_DIR="${BH_PROJECT_DIR:-}"
if [ -z "$PROJECT_DIR" ] && command -v jq >/dev/null 2>&1; then
  PROJECT_DIR=$(echo "$INPUT" | jq -r '.project_dir // empty' 2>/dev/null)
fi
PROJECT_DIR="${PROJECT_DIR:-$PWD}"

if [ ! -d "$PROJECT_DIR/.git" ]; then
  exit 0  # not a git repo; nothing to warn about
fi

cd "$PROJECT_DIR" || exit 0

# Check for uncommitted changes
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
  echo "[BH SessionEnd] ⚠️  Uncommitted changes in $PROJECT_DIR." >&2
  echo "  Run \`git status\` to see what's pending." >&2
  echo "  Law XIII reminder: commit after meaningful changes." >&2
fi

exit 0
