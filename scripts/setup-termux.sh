#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"

if ! command -v pkg >/dev/null 2>&1; then
  echo "This setup script must be run inside Termux." >&2
  exit 1
fi

echo "Installing Termux runtime packages..."
pkg install -y python python-cryptography git nodejs-lts

if [[ -x "$VENV_DIR/bin/python" ]] \
  && "$VENV_DIR/bin/python" -c 'import sys, cryptography' >/dev/null 2>&1; then
  :
elif [[ -d "$VENV_DIR" ]]; then
  echo "Recreating the virtual environment with Termux system packages..."
  python -m venv --clear --system-site-packages "$VENV_DIR"
else
  echo "Creating the VerseNa virtual environment..."
  python -m venv --system-site-packages "$VENV_DIR"
fi

echo "Installing backend dependencies..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$PROJECT_ROOT/backend/requirements-termux.txt"

echo "Verifying the backend runtime..."
if ! (
  cd "$PROJECT_ROOT/backend"
  "$VENV_DIR/bin/python" -c 'import cryptography, main, pydantic; print(f"Backend runtime OK (Pydantic {pydantic.__version__}, cryptography {cryptography.__version__})")'
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
