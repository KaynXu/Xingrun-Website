#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BRANCH="${1:-master}"

if [[ -f .env.runtime ]]; then
  set -a
  source .env.runtime
  set +a
fi

PYTHON_BIN="${XR_PYTHON_BIN:-python3}"
WEB_PROCESS_NAME="${XR_PM2_WEB_PROCESS_NAME:-xingrun}"
MEMORY_PROCESS_NAME="${XR_PM2_MEMORY_PROCESS_NAME:-xingrun-class-commentary-memory-worker}"
MEMORY_KILL_TIMEOUT_MS="${XR_CLASS_COMMENTARY_MEMORY_WORKER_KILL_TIMEOUT:-330000}"
HEALTHCHECK_URL="${XR_HEALTHCHECK_URL:-http://127.0.0.1:5001/}"

python_version() {
  "$1" --version 2>&1 | sed 's/^Python //'
}

require_python_312() {
  local python_bin="$1"
  local label="$2"

  if ! command -v "$python_bin" >/dev/null 2>&1; then
    echo "$label was not found: $python_bin" >&2
    echo "Python 3.12.x is required. Set XR_PYTHON_BIN to a Python 3.12 executable." >&2
    exit 1
  fi

  if ! "$python_bin" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))'; then
    echo "$label uses Python $(python_version "$python_bin"); Python 3.12.x is required." >&2
    exit 1
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command was not found: $1" >&2
    exit 1
  fi
}

is_enabled() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

require_python_312 "$PYTHON_BIN" "XR_PYTHON_BIN"

if [[ -d .venv ]]; then
  if [[ ! -x .venv/bin/python ]]; then
    echo "Existing .venv has no executable Python interpreter. Remove .venv and rerun." >&2
    exit 1
  fi
  if ! .venv/bin/python -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))'; then
    echo "Existing .venv uses Python $(python_version .venv/bin/python); Python 3.12.x is required." >&2
    echo "Remove .venv and rerun with XR_PYTHON_BIN pointing to Python 3.12." >&2
    exit 1
  fi
fi

require_command pm2
require_command curl
if ! is_enabled "${XR_SKIP_GIT_SYNC:-0}"; then
  require_command git
fi

if is_enabled "${XR_SKIP_GIT_SYNC:-0}"; then
  echo "==> Skipping git sync for the current checked-out revision"
else
  echo "==> Fetching branch $BRANCH"
  git fetch origin
  git checkout "$BRANCH"
  git pull --ff-only origin "$BRANCH"
fi

if [[ ! -d .venv ]]; then
  echo "==> Creating Python 3.12 virtual environment"
  "$PYTHON_BIN" -m venv .venv
fi

require_python_312 .venv/bin/python ".venv/bin/python"

echo "==> Installing backend dependencies"
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt

echo "==> Initializing database"
XR_OPEN_BROWSER=0 .venv/bin/python - <<'PY'
from lesson_manager import init_db

init_db()
PY

MEMORY_ENABLED=0
if .venv/bin/python -c '
import config_runtime

raise SystemExit(
    0
    if config_runtime.get_runtime_config().get("class_commentary_memory_enabled")
    else 1
)
'; then
  MEMORY_ENABLED=1
fi
GRAPH_ENABLED=0
if .venv/bin/python -c '
import config_runtime

raise SystemExit(
    0
    if config_runtime.get_runtime_config().get("class_commentary_graph_enabled")
    else 1
)
'; then
  GRAPH_ENABLED=1
fi
WORKER_ENABLED=0
if (( MEMORY_ENABLED || GRAPH_ENABLED )); then
  WORKER_ENABLED=1
fi
if (( WORKER_ENABLED )) \
  && { ! [[ "$MEMORY_KILL_TIMEOUT_MS" =~ ^[0-9]+$ ]] \
    || (( MEMORY_KILL_TIMEOUT_MS < 330000 )); }; then
  echo "XR_CLASS_COMMENTARY_MEMORY_WORKER_KILL_TIMEOUT must be at least 330000 ms." >&2
  exit 1
fi

export XR_OPEN_BROWSER=0

start_or_restart_web() {
  if pm2 describe "$WEB_PROCESS_NAME" >/dev/null 2>&1; then
    pm2 restart "$WEB_PROCESS_NAME" --update-env
  else
    pm2 start "$ROOT_DIR/scripts/run_backend.sh" \
      --name "$WEB_PROCESS_NAME" \
      --interpreter bash \
      --time
  fi
}

start_or_restart_memory_worker() {
  if pm2 describe "$MEMORY_PROCESS_NAME" >/dev/null 2>&1; then
    pm2 restart "$MEMORY_PROCESS_NAME" \
      --update-env \
      --kill-timeout "$MEMORY_KILL_TIMEOUT_MS"
  else
    pm2 start "$ROOT_DIR/scripts/run_class_commentary_memory_worker.sh" \
      --name "$MEMORY_PROCESS_NAME" \
      --interpreter bash \
      --kill-timeout "$MEMORY_KILL_TIMEOUT_MS" \
      --time
  fi
}

pm2_process_online() {
  local process_name="$1"
  pm2 jlist | .venv/bin/python -c '
import json
import sys

process_name = sys.argv[1]
processes = json.load(sys.stdin)
raise SystemExit(
    0
    if any(
        item.get("name") == process_name
        and item.get("pm2_env", {}).get("status") == "online"
        for item in processes
    )
    else 1
)
' "$process_name"
}

pm2_process_stopped() {
  local process_name="$1"
  pm2 jlist | .venv/bin/python -c '
import json
import sys

process_name = sys.argv[1]
processes = json.load(sys.stdin)
raise SystemExit(
    0
    if any(
        item.get("name") == process_name
        and item.get("pm2_env", {}).get("status") == "stopped"
        for item in processes
    )
    else 1
)
' "$process_name"
}

memory_worker_timeout_valid() {
  pm2 jlist | .venv/bin/python -c '
import json
import sys

process_name = sys.argv[1]
minimum = int(sys.argv[2])
processes = json.load(sys.stdin)
matching = [item for item in processes if item.get("name") == process_name]
raise SystemExit(
    0
    if len(matching) == 1
    and int(matching[0].get("pm2_env", {}).get("kill_timeout") or 0) >= minimum
    else 1
)
' "$MEMORY_PROCESS_NAME" "$MEMORY_KILL_TIMEOUT_MS"
}

echo "==> Starting PM2 services"
start_or_restart_web
if (( WORKER_ENABLED )); then
  start_or_restart_memory_worker
elif pm2 describe "$MEMORY_PROCESS_NAME" >/dev/null 2>&1; then
  echo "==> Memory feature is disabled; stopping PM2 worker"
  pm2 stop "$MEMORY_PROCESS_NAME"
else
  echo "==> Memory feature is disabled; worker is not installed"
fi

echo "==> Waiting for PM2 services"
for _ in $(seq 1 30); do
  if pm2_process_online "$WEB_PROCESS_NAME" \
    && { (( ! WORKER_ENABLED )) \
      || { pm2_process_online "$MEMORY_PROCESS_NAME" \
        && memory_worker_timeout_valid; }; }; then
    break
  fi
  sleep 1
done

if ! pm2_process_online "$WEB_PROCESS_NAME"; then
  echo "PM2 process is not online: $WEB_PROCESS_NAME" >&2
  pm2 status "$WEB_PROCESS_NAME" "$MEMORY_PROCESS_NAME" || true
  exit 1
fi
if (( WORKER_ENABLED )); then
  if ! pm2_process_online "$MEMORY_PROCESS_NAME"; then
    echo "PM2 process is not online: $MEMORY_PROCESS_NAME" >&2
    pm2 status "$WEB_PROCESS_NAME" "$MEMORY_PROCESS_NAME" || true
    exit 1
  fi
  if ! memory_worker_timeout_valid; then
    echo "PM2 memory worker kill_timeout is below $MEMORY_KILL_TIMEOUT_MS ms." >&2
    exit 1
  fi
elif pm2 describe "$MEMORY_PROCESS_NAME" >/dev/null 2>&1 \
  && ! pm2_process_stopped "$MEMORY_PROCESS_NAME"; then
  echo "PM2 memory worker must be stopped while the feature is disabled." >&2
  exit 1
fi

echo "==> Waiting for HTTP 302: $HEALTHCHECK_URL"
HTTP_STATUS=""
for _ in $(seq 1 30); do
  HTTP_STATUS="$(curl -sS -o /dev/null -w '%{http_code}' "$HEALTHCHECK_URL" || true)"
  if [[ "$HTTP_STATUS" == "302" ]]; then
    break
  fi
  sleep 1
done
if [[ "$HTTP_STATUS" != "302" ]]; then
  echo "Web healthcheck expected HTTP 302, got ${HTTP_STATUS:-no response}." >&2
  pm2 logs "$WEB_PROCESS_NAME" --lines 60 --nostream || true
  exit 1
fi

if (( MEMORY_ENABLED )); then
  echo "==> Checking class commentary memory capability"
  .venv/bin/python - <<'PY'
from datetime import datetime, timezone
import json
import uuid

from rq.registry import ScheduledJobRegistry

import config_runtime
import lesson_manager
from class_commentary_memory import ClassCommentaryMemoryService
from class_commentary_memory_queue import (
    class_commentary_memory_queue_healthcheck,
    ensure_class_commentary_memory_reconciliation_scheduled,
    get_class_commentary_memory_queue,
    get_class_commentary_memory_redis_connection,
)


config = config_runtime.get_runtime_config()
if not config.get("class_commentary_memory_enabled"):
    raise SystemExit(
        "XR_CLASS_COMMENTARY_MEMORY_ENABLED must be enabled for the dual-process production deploy"
    )

service = ClassCommentaryMemoryService(runtime_config=config)
memory_health = service.healthcheck()
if not memory_health.get("healthy"):
    raise SystemExit(
        "Mem0/Qdrant healthcheck failed: "
        + str(memory_health.get("error_type") or memory_health.get("status") or "unknown")
    )

probe_token = uuid.uuid4().hex
scope_seed = int(probe_token[:12], 16)
organization_id = 1_000_000_000 + scope_seed % 900_000_000
skill_registry_id = 1_000_000_000 + int(probe_token[12:24], 16) % 900_000_000
probe_memory_id = ""
try:
    added = service.add_projection(
        memory_text=f"课堂点评中文检索部署探针 {probe_token}",
        metadata={
            "organization_id": organization_id,
            "scope_skill_registry_id": skill_registry_id,
            "student_id": None,
            "subject_key": None,
            "memory_type": "teacher_style",
            "generation_id": 1,
            "created_from_revision_id": 1,
            "memory_record_id": 1,
            "record_version": 1,
            "evidence_count": 1,
            "operation_key": f"deploy-health-{probe_token}",
            "status": "active",
            "confidence": 1.0,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    probe_memory_id = str(added["id"])
    results = service.search_style(
        f"课堂点评中文检索部署探针 {probe_token}",
        organization_id=organization_id,
        scope_skill_registry_id=skill_registry_id,
        limit=3,
    )
    if not any(str(item.get("id") or "") == probe_memory_id for item in results):
        raise RuntimeError("Chinese retrieval smoke did not return its probe")
finally:
    if probe_memory_id:
        service.delete(probe_memory_id)

redis_connection = get_class_commentary_memory_redis_connection(config)
queue = get_class_commentary_memory_queue(
    runtime_config=config,
    connection=redis_connection,
)
queue_health = class_commentary_memory_queue_healthcheck(
    runtime_config=config,
    connection=redis_connection,
    queue=queue,
)
if not queue_health.get("healthy"):
    raise SystemExit(
        "Redis/RQ healthcheck failed: "
        + str(queue_health.get("error_type") or queue_health.get("status") or "unknown")
    )

schedule = ensure_class_commentary_memory_reconciliation_scheduled(
    queue=queue,
    runtime_config=config,
)
registry = ScheduledJobRegistry(name=queue.name, connection=redis_connection)
reconciliation_ids = sorted(
    job_id
    for job_id in registry.get_job_ids()
    if str(job_id).startswith("cc-memory-reconcile-")
)
if reconciliation_ids != [schedule["job_id"]]:
    raise SystemExit(
        "Expected exactly one next reconciliation bucket, got "
        + str(len(reconciliation_ids))
    )

projection_status = "no_projected_records"
with lesson_manager.get_conn() as connection:
    record = connection.execute(
        """
        SELECT id, mem0_memory_id
        FROM class_commentary_memory_records
        WHERE mem0_memory_id IS NOT NULL
          AND mem0_memory_id<>''
          AND desired_status=applied_status
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """
    ).fetchone()
    if record is not None:
        projected = service.get(record["mem0_memory_id"])
        metadata = projected.get("metadata") if projected else None
        if not isinstance(metadata, dict) or int(metadata.get("memory_record_id") or 0) != int(record["id"]):
            raise SystemExit("SQLite to Mem0 projection lookup failed")
        reverse = connection.execute(
            "SELECT mem0_memory_id FROM class_commentary_memory_records WHERE id=?",
            (int(metadata["memory_record_id"]),),
        ).fetchone()
        if reverse is None or str(reverse["mem0_memory_id"] or "") != str(projected["id"]):
            raise SystemExit("Mem0 to SQLite projection lookup failed")
        projection_status = "verified"

print(
    json.dumps(
        {
            "memory": "ready",
            "redis": "ready",
            "rq_worker_count": queue_health["worker_count"],
            "reconciliation_job_id": schedule["job_id"],
            "collection": service.settings.collection_name,
            "embedding_dims": service.settings.embedding_dims,
            "projection_lookup": projection_status,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
)
PY
else
  echo "==> Memory feature is disabled; skipping Mem0, Qdrant, Redis, and RQ checks"
fi

if (( GRAPH_ENABLED )); then
  echo "==> Checking class commentary graph capability"
  .venv/bin/python scripts/check_class_commentary_graph_deploy.py
else
  echo "==> Graph feature is disabled; skipping Semantica checks"
fi

pm2 save
if (( WORKER_ENABLED )); then
  echo "Deploy complete. Web and class commentary worker are healthy."
else
  echo "Deploy complete. Web is healthy and class commentary memory is disabled."
fi
