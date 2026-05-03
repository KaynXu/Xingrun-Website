#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNBOOK="$ROOT_DIR/docs/production-upload-pipeline-smoke-runbook.md"

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "missing file: $path"
    exit 1
  fi
  echo "ok file: ${path#$ROOT_DIR/}"
}

require_text() {
  local path="$1"
  local needle="$2"
  local label="$3"
  if ! grep -Fq "$needle" "$path"; then
    echo "missing $label: $needle"
    echo "in file: ${path#$ROOT_DIR/}"
    exit 1
  fi
  echo "ok $label"
}

require_file "$RUNBOOK"
require_file "$ROOT_DIR/scripts/ralph/miniprogram_upload_stability_proof.sh"
require_file "$ROOT_DIR/scripts/run_backend.sh"
require_file "$ROOT_DIR/wrong_question_upload_queue.py"
require_file "$ROOT_DIR/wrong_question_upload_worker.py"

require_text "$RUNBOOK" "pm2 status xingrun xingrun-bridge xingrun-rq-worker" "PM2 service check"
require_text "$RUNBOOK" 'redis-cli -u "$XR_REDIS_URL" ping' "Redis ping check"
require_text "$RUNBOOK" '.venv/bin/rq info --url "$XR_REDIS_URL" "$QUEUE"' "RQ info check"
require_text "$RUNBOOK" 'curl -sS -D - -o /dev/null "$FLASK_URL/"' "Flask root health check"
require_text "$RUNBOOK" 'curl -fsS "$BRIDGE_URL/healthz"' "bridge health check"
require_text "$RUNBOOK" "fileSize: 10 \\\\* 1024 \\\\* 1024" "bridge upload size check"
require_text "$RUNBOOK" "/api/wechat/wrong-questions" "website upload route reference"
require_text "$RUNBOOK" '/api/wechat/wrong-question-upload-tasks/$TASK_ID?open_id=$OPEN_ID' "website task status command"
require_text "$RUNBOOK" '/wechat/parent/wrong-question-upload-tasks/$TASK_ID?openId=$OPEN_ID' "bridge task status command"
require_text "$RUNBOOK" '/wechat/parent/children/$STUDENT_ID/wrong-questions?openId=$OPEN_ID' "wrongbook list command"
require_text "$RUNBOOK" '/wechat/parent/children/$STUDENT_ID/wrong-question-library?openId=$OPEN_ID' "wrongbook PDF metadata command"
require_text "$RUNBOOK" '/api/wechat/student-libraries/$STUDENT_ID' "student PDF download command"
require_text "$RUNBOOK" "If Tasks Stay Pending" "pending troubleshooting"
require_text "$RUNBOOK" "If Enqueue Fails" "enqueue troubleshooting"
require_text "$RUNBOOK" "If Uploads Hit 413" "413 troubleshooting"
require_text "$RUNBOOK" "If PDF Refresh Fails" "PDF troubleshooting"
require_text "$RUNBOOK" "[MUTATING]" "mutating command labels"

require_text "$ROOT_DIR/app.py" "app.config[\"MAX_CONTENT_LENGTH\"] = 200 * 1024 * 1024" "Flask upload limit source"
require_text "$ROOT_DIR/app.py" "@app.route(\"/api/wechat/wrong-questions\", methods=[\"POST\"])" "Flask upload route source"
require_text "$ROOT_DIR/app.py" "@app.route(\"/api/wechat/wrong-question-upload-tasks/<int:task_id>\", methods=[\"GET\"])" "Flask task status route source"
require_text "$ROOT_DIR/app.py" "@app.route(\"/api/wechat/children/<int:student_id>/wrong-question-library\", methods=[\"GET\"])" "Flask PDF metadata route source"
require_text "$ROOT_DIR/app.py" "@app.route(\"/api/wechat/student-libraries/<int:student_id>\", methods=[\"GET\"])" "Flask PDF route source"
require_text "$ROOT_DIR/app.py" "@app.route(\"/api/wrong-question-student-libraries/<int:student_id>/refresh\", methods=[\"POST\"])" "Flask staff PDF refresh route source"

require_text "$ROOT_DIR/miniprogram/backend/src/index.ts" "app.get('/healthz'" "bridge health route source"
require_text "$ROOT_DIR/miniprogram/backend/src/index.ts" "app.post('/wechat/parent/wrong-questions'" "bridge upload route source"
require_text "$ROOT_DIR/miniprogram/backend/src/index.ts" "app.get('/wechat/parent/wrong-question-upload-tasks/:taskId'" "bridge task route source"
require_text "$ROOT_DIR/miniprogram/backend/src/index.ts" "app.get('/wechat/parent/children/:studentId/wrong-question-library'" "bridge PDF metadata route source"
require_text "$ROOT_DIR/miniprogram/backend/src/upload.ts" "limits: { fileSize: 10 * 1024 * 1024 }" "bridge upload limit source"

require_text "$ROOT_DIR/wrong_question_upload_queue.py" "wrong_question_uploads" "RQ queue default source"
require_text "$ROOT_DIR/wrong_question_upload_worker.py" "def process_wechat_wrong_question_upload_task(task_id: int) -> dict:" "worker function source"

echo "production upload smoke runbook proof passed"
