#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env.runtime ]; then
  set -a
  . ./.env.runtime
  set +a
fi
export XR_OPEN_BROWSER="${XR_OPEN_BROWSER:-0}"
exec .venv/bin/python app.py
