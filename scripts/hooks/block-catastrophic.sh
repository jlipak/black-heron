#!/usr/bin/env bash
# PreToolUse(Bash). HARD BLOCK on catastrophic shell operations.
# Mirrors QURE's block-catastrophic pattern. Exit 2 to deny.

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

NORM=$(echo "$CMD" | tr -s ' \t' ' ')

deny() {
  local why="$1"
  echo "BLOCKED by Black Heron — catastrophic command rejected." >&2
  echo "Reason: $why" >&2
  echo "Command: $CMD" >&2
  echo "If genuinely required, SHIKA runs it himself in a fresh session." >&2
  exit 2
}

# rm -rf on system roots
if echo "$NORM" | grep -qE 'rm[[:space:]]+(-[rRf]+[[:space:]]+|-rf[[:space:]]+|-fr[[:space:]]+|-Rf[[:space:]]+|-fR[[:space:]]+)?(/|/\*)([[:space:]]|$)'; then
  deny "rm -rf on /"
fi

# Disk wipe / device redirect
if echo "$NORM" | grep -qE '\bdd\b.*of=/dev/(sda|sd[a-z]|nvme|vd[a-z]|xvd[a-z])'; then deny "dd to block device"; fi
if echo "$NORM" | grep -qE '\bmkfs(\.|\b)'; then deny "mkfs filesystem create"; fi
if echo "$NORM" | grep -qE '>\s*/dev/(sda|sd[a-z]|nvme|vd[a-z]|xvd[a-z])'; then deny "redirect to block device"; fi

# Fork bomb
if echo "$NORM" | grep -qF ':(){:|:&};:'; then deny "fork bomb"; fi
if echo "$NORM" | grep -qF ':(){ :|:& };:'; then deny "fork bomb"; fi

# Power
if echo "$NORM" | grep -qE '^\s*(shutdown|halt|poweroff|reboot)(\s|$)'; then deny "power command"; fi
if echo "$NORM" | grep -qE '^\s*init\s+(0|6)\s*$'; then deny "init 0/6"; fi

# Destructive git on main/master
if echo "$NORM" | grep -qE 'git[[:space:]]+(reset[[:space:]]+--hard|push[[:space:]]+(-f|--force)|branch[[:space:]]+-D|clean[[:space:]]+-f)[[:space:]]+(main|master)'; then
  deny "destructive git on main/master"
fi

exit 0
