#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env.runtime ]]; then
  set -a
  source .env.runtime
  set +a
fi

VENV_PYTHON="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Missing executable: $VENV_PYTHON" >&2
  echo "Create .venv with Python 3.12 before starting the memory worker." >&2
  exit 1
fi

if ! "$VENV_PYTHON" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))'; then
  PYTHON_VERSION="$($VENV_PYTHON --version 2>&1 | sed 's/^Python //')"
  echo "Existing .venv uses Python $PYTHON_VERSION; Python 3.12.x is required." >&2
  echo "Remove .venv and recreate it with Python 3.12 before starting the memory worker." >&2
  exit 1
fi

if ! "$VENV_PYTHON" -c '
import config_runtime

raise SystemExit(
    0
    if (
        config_runtime.get_runtime_config().get("class_commentary_memory_enabled")
        or config_runtime.get_runtime_config().get("class_commentary_graph_enabled")
    )
    else 1
)
'; then
  echo "XR_CLASS_COMMENTARY_MEMORY_ENABLED or XR_CLASS_COMMENTARY_GRAPH_ENABLED must be enabled before starting the worker." >&2
  exit 1
fi

exec "$VENV_PYTHON" class_commentary_memory_worker.py
