#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "[1/4] Backend tests"
python -m pytest backend/tests -q

echo "[2/4] Python compile check"
find backend -type f -name '*.py' \
  -not -path '*/__pycache__/*' \
  -not -path '*/data/*' \
  -print0 | xargs -0 python -m py_compile

echo "[3/4] Frontend production build"
npm --prefix frontend run build

echo "[4/4] Git whitespace check"
git diff --check
echo "VerseNa regression checks passed."
