#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/backend/.env"
LEGACY_DATA_DIR="$PROJECT_ROOT/backend/data"
TERMUX_DATA_DIR="${VERSENA_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/versena}"

if [[ ! -f "$ENV_FILE" ]]; then
  umask 077
  printf '%s\n' \
    'VERSENA_HOST=0.0.0.0' \
    'VERSENA_PORT=8002' \
    'VERSENA_AUTH_COOKIE_SECURE=false' > "$ENV_FILE"
fi

export VERSENA_HOST=0.0.0.0
export VERSENA_PORT=8002
export VERSENA_DATA_DIR="$TERMUX_DATA_DIR"
export VERSENA_SKILLS_DATA_DIR="$TERMUX_DATA_DIR/skills"

mkdir -p "$TERMUX_DATA_DIR"
chmod 700 "$TERMUX_DATA_DIR" || true
if [[ -d "$LEGACY_DATA_DIR" ]] && [[ -z "$(find "$TERMUX_DATA_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  cp -a "$LEGACY_DATA_DIR/." "$TERMUX_DATA_DIR/"
  echo "Migrated existing VerseNa data to $TERMUX_DATA_DIR"
fi

if [[ ! -f "$PROJECT_ROOT/frontend/dist/index.html" ]]; then
  echo "frontend/dist is missing; use a VerseNa Termux release package with a prebuilt frontend." >&2
  exit 1
fi

if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock || true
fi

echo
echo "VerseNa LAN access"
echo "  Port: 8002"
echo "  Data: $TERMUX_DATA_DIR"
echo

cd "$PROJECT_ROOT/backend"
exec python main.py
