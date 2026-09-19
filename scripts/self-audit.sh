#!/usr/bin/env bash
# Run Black Heron on its own source.
# Output: examples/self-audit-<date>/REPORT.md + findings.json + findings.sarif
#
# Portability: detects python3/python/py in that order. Loads ANTHROPIC_API_KEY
# from $BH_ENV_FILE (if set) or $BH_ROOT/.env (if present). No hardcoded paths.

set -eu

BH_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATE="$(date +%Y-%m-%d)"
OUT_DIR="$BH_ROOT/examples/self-audit-$DATE"

# Portable Python launcher detection.
# On Windows, `python3` may be a Microsoft Store stub that doesn't run code,
# so we functionally test each candidate. `py` is preferred on Windows;
# `python3` on Unix.
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

# Load API key — prefer explicit BH_ENV_FILE, else local .env (gitignored)
ENV_FILE="${BH_ENV_FILE:-${BH_ROOT}/.env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  . "$ENV_FILE"
  set +a
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ERROR: ANTHROPIC_API_KEY not set." >&2
  echo "  Set it in env, OR create $ENV_FILE, OR pass BH_ENV_FILE=<path>." >&2
  exit 1
fi

echo "Black Heron self-audit"
echo "  Python:  $PY"
echo "  BH root: $BH_ROOT"
echo "  Output:  $OUT_DIR"
echo ""

cd "$BH_ROOT"
"$PY" -m black_heron.cli "$BH_ROOT" --out "$OUT_DIR"

if [ -f "$OUT_DIR/REPORT.md" ]; then
  echo ""
  echo "Self-audit written to $OUT_DIR (commit it as the showcase example)"
else
  echo "WARN: no REPORT.md produced at $OUT_DIR" >&2
  exit 2
fi
