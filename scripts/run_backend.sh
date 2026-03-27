#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env.runtime ]; then
  set -a
  . ./.env.runtime
  set +a
fi
exec .venv/bin/python app.py
