#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"

if ! command -v pkg >/dev/null 2>&1; then
  echo "This setup script must be run inside Termux." >&2
  exit 1
fi

echo "Installing Termux runtime packages..."
pkg install -y python git nodejs-lts

if [[ -x "$VENV_DIR/bin/python" ]]; then
  if ! "$VENV_DIR/bin/python" -c 'import sys' >/dev/null 2>&1; then
    echo "Recreating the virtual environment for the current Python version..."
    python -m venv --clear "$VENV_DIR"
  fi
else
  echo "Creating the VerseNa virtual environment..."
  python -m venv "$VENV_DIR"
fi

echo "Installing backend dependencies..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$PROJECT_ROOT/backend/requirements-termux.txt"

echo "Verifying the backend runtime..."
if ! (
  cd "$PROJECT_ROOT/backend"
  "$VENV_DIR/bin/python" -c 'import main, pydantic; print(f"Backend runtime OK (Pydantic {pydantic.__version__})")'
); then
  echo "Backend verification failed; review the Python error above." >&2
  exit 1
fi

echo "Building the frontend..."
(
  cd "$PROJECT_ROOT/frontend"
  npm ci
  npm run build
)

echo
echo "VerseNa source setup completed."
echo "Start it with: bash scripts/start-termux.sh"
