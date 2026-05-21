#!/usr/bin/env bash
# PreCompact hook. Triggered before Claude Code compacts context.
# At 85% context utilization, persist BH session state to disk so we can resume cleanly.

set -u

INPUT=$(cat 2>/dev/null || echo "{}")

# Extract context utilization if available
UTIL="unknown"
TOKENS="unknown"
MAX="unknown"
if command -v jq >/dev/null 2>&1; then
  TOKENS=$(echo "$INPUT" | jq -r '.transcript_tokens // "unknown"' 2>/dev/null)
  MAX=$(echo "$INPUT" | jq -r '.max_context_tokens // "unknown"' 2>/dev/null)
  if [ "$TOKENS" != "unknown" ] && [ "$MAX" != "unknown" ]; then
    UTIL=$(echo "scale=2; $TOKENS / $MAX" | bc 2>/dev/null || echo "unknown")
  fi
fi

# Ensure session state dir exists
STATE_DIR="${BH_STATE_DIR:-$HOME/.black-heron/sessions}"
mkdir -p "$STATE_DIR" 2>/dev/null || true

# Write a flush marker
TS=$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S)
{
  echo "{"
  echo "  \"event\": \"pre-compact-flush\","
  echo "  \"timestamp\": \"$TS\","
  echo "  \"transcript_tokens\": \"$TOKENS\","
  echo "  \"max_context_tokens\": \"$MAX\","
  echo "  \"utilization\": \"$UTIL\""
  echo "}"
} > "$STATE_DIR/last-flush.json" 2>/dev/null || true

# Log to stderr (visible to user)
if [ "$UTIL" != "unknown" ]; then
  echo "[BH PreCompact] utilization=$UTIL ($TOKENS/$MAX tokens). State flushed to $STATE_DIR/last-flush.json" >&2
else
  echo "[BH PreCompact] state flushed to $STATE_DIR/last-flush.json (utilization unknown)" >&2
fi

# Allow compaction to proceed
echo '{"decision":"allow"}'
exit 0
