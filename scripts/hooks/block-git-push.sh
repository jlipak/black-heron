#!/usr/bin/env bash
# PreToolUse(Bash). HARD BLOCK on `git push` unless explicit override.
# Law XI — push requires the owner's explicit authorization.
# Override: set BH_ALLOW_PUSH=1 in env for the one operation, or edit .claude/settings.local.json.
# Exit codes: 0 = allow, 2 = HARD BLOCK.

set -u

INPUT=$(cat 2>/dev/null || echo "")

CMD=""
if command -v jq >/dev/null 2>&1; then
  CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
fi
if [ -z "$CMD" ]; then
  CMD=$(echo "$INPUT" | grep -oE '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/^"command"[[:space:]]*:[[:space:]]*"\(.*\)"$/\1/')
fi

if [ -z "$CMD" ]; then
  exit 0
fi

# Allow `git push` only when BH_ALLOW_PUSH=1 set in env for this invocation
if echo "$CMD" | grep -qE '\bgit[[:space:]]+push\b'; then
  if [ "${BH_ALLOW_PUSH:-0}" = "1" ]; then
    echo "[BH hook] git push allowed (BH_ALLOW_PUSH=1 set)" >&2
    exit 0
  fi
  echo "BLOCKED by Black Heron Law XI — git push requires the owner's explicit authorization." >&2
  echo "Override path: set BH_ALLOW_PUSH=1 in env for the one operation, OR edit .claude/settings.local.json." >&2
  echo "Command attempted: $CMD" >&2
  exit 2
fi

exit 0
