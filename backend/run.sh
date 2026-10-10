#!/usr/bin/env bash
# One-command backend start.
# Creates a virtualenv (if missing), installs deps, then runs the API.
# Requires network access the first time (to install from PyPI).
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtualenv..."
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "Starting FastAPI on http://localhost:8000 (docs at /docs)..."
exec uvicorn app.main:app --reload --port 8000
