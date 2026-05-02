#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="$PYTHON"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

run() {
  echo
  echo ">>> $*"
  "$@"
}

cd "$ROOT_DIR"

run node --test \
  miniprogram/miniprogram/pages/parent-upload/model.test.js \
  miniprogram/miniprogram/pages/parent-wrongbook/latex-preview.test.js \
  miniprogram/miniprogram/parent-only-scope.test.js \
  miniprogram/miniprogram/utils/parentApi.test.js

echo
echo ">>> bridge parent upload tests"
(
  cd "$ROOT_DIR/miniprogram/backend"
  node --import tsx --test src/parent-wechat-bridge.test.ts
)

run node miniprogram/backend/parent-only-scope.test.cjs
run npm --prefix miniprogram/backend run build
run "$PYTHON_BIN" -m unittest \
  tests.test_wechat_parent_upload_data \
  tests.test_wechat_parent_upload_api
run git diff --check
