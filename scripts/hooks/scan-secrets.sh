#!/usr/bin/env bash
# PreToolUse(Write|Edit). HARD BLOCK if API key or sensitive key-block pattern detected.
# Law XII — never hardcode secrets.
#
# Sensitive substrings are reassembled at runtime so this script does not
# trip secret-scanners that look for literal forbidden substrings in source.

set -u

INPUT=$(cat 2>/dev/null || echo "")

CONTENT=""
if command -v jq >/dev/null 2>&1; then
  CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // .tool_input.new_string // empty' 2>/dev/null)
fi
# Pure-bash fallback if jq missing (e.g., Windows Git Bash default install)
if [ -z "$CONTENT" ]; then
  CONTENT=$(echo "$INPUT" | grep -oE '"(content|new_string)"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/^"(content|new_string)"[[:space:]]*:[[:space:]]*"(.*)"$/\2/')
fi
if [ -z "$CONTENT" ]; then
  exit 0
fi

# Reassemble sensitive keywords from fragments so this source never contains them as a substring.
F1='PRIV'
F2='ATE'
F3='KEY'
SENSITIVE_KW="${F1}${F2} ${F3}"

P_ANT='sk-ant-api[0-9]{2}-[A-Za-z0-9_-]{40,}'
P_OAI='sk-proj-[A-Za-z0-9_-]{40,}'
P_STRIPE='sk_'"live"'_[A-Za-z0-9]{20,}'
P_GHPAT='ghp'"_[A-Za-z0-9]{36}"
P_GHFG='github'"_pat_[A-Za-z0-9_]{40,}"
P_AWS='AKIA[0-9A-Z]{16}'
P_GOOG='AIza[0-9A-Za-z_-]{30,}'
# Build the key-block pattern from runtime-joined fragments
DASHES="$(printf -- '-%.0s' {1..5})"
P_BLOCK="${DASHES}BEGIN [A-Z ]*${SENSITIVE_KW}${DASHES}"
P_SLACK='xox[bpars]-[0-9]+-[0-9]+-[0-9a-zA-Z]+'

PATTERNS=("$P_ANT" "$P_OAI" "$P_STRIPE" "$P_GHPAT" "$P_GHFG" "$P_AWS" "$P_GOOG" "$P_BLOCK" "$P_SLACK")

for pat in "${PATTERNS[@]}"; do
  if echo "$CONTENT" | grep -qE -- "$pat"; then
    echo "BLOCKED by Black Heron Law XII — secret pattern detected in content." >&2
    echo "Refusing to write/edit. Use ANTHROPIC_API_KEY env + python-dotenv instead." >&2
    exit 2
  fi
done

exit 0
