#!/bin/bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH="$PWD" alembic upgrade head

echo "Bootstrap complete. Run: source .venv/bin/activate && uvicorn app.main:app --reload --port 8000"
