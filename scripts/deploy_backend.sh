#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

BRANCH="${1:-master}"
HEALTHCHECK_URL="${XR_HEALTHCHECK_URL:-http://127.0.0.1:5001/}"
PID_DIR=".run"
LOG_DIR="logs"
PID_FILE="$PID_DIR/backend.pid"
LOG_FILE="$LOG_DIR/backend.log"

mkdir -p "$PID_DIR" "$LOG_DIR"

if [ -f .env.runtime ]; then
  set -a
  . ./.env.runtime
  set +a
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required"
  exit 1
fi

stop_pid() {
  local pid="$1"
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi

  kill "$pid" >/dev/null 2>&1 || true
  for _ in $(seq 1 10); do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  kill -9 "$pid" >/dev/null 2>&1 || true
}

echo "==> Fetching branch $BRANCH"
git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

if [ ! -d .venv ]; then
  echo "==> Creating virtual environment"
  python3 -m venv .venv
fi

echo "==> Installing backend dependencies"
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt

echo "==> Initializing database"
XR_OPEN_BROWSER=0 .venv/bin/python - <<'PY'
from lesson_manager import init_db

init_db()
PY

echo "==> Stopping previous backend"
if [ -f "$PID_FILE" ]; then
  stop_pid "$(cat "$PID_FILE")"
  rm -f "$PID_FILE"
fi

while IFS= read -r pid; do
  [ -n "$pid" ] || continue
  stop_pid "$pid"
done < <(pgrep -f "$PWD/.venv/bin/python app.py" || true)

echo "==> Starting backend"
XR_OPEN_BROWSER=0 nohup ./scripts/run_backend.sh >"$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"

if ! kill -0 "$NEW_PID" >/dev/null 2>&1; then
  echo "Backend failed to start"
  tail -n 40 "$LOG_FILE" || true
  exit 1
fi

echo "==> Waiting for healthcheck: $HEALTHCHECK_URL"
for _ in $(seq 1 20); do
  if curl -fsS "$HEALTHCHECK_URL" >/dev/null 2>&1; then
    echo "Deploy complete. Backend is healthy."
    echo "PID: $NEW_PID"
    echo "Log: $LOG_FILE"
    exit 0
  fi
  sleep 1
done

echo "Healthcheck failed after restart"
tail -n 60 "$LOG_FILE" || true
exit 1
