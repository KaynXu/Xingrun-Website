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

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "missing file: ${path#$ROOT_DIR/}"
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

run() {
  echo
  echo ">>> $*"
  "$@"
}

cd "$ROOT_DIR"

UPLOAD_MODEL_TEST="$ROOT_DIR/miniprogram/miniprogram/pages/parent-upload/model.test.js"
UPLOAD_PAGE_TEST="$ROOT_DIR/miniprogram/miniprogram/pages/parent-upload/index.test.js"
WRONGBOOK_TEST="$ROOT_DIR/miniprogram/miniprogram/pages/parent-wrongbook/index.test.js"
PARENT_API_TEST="$ROOT_DIR/miniprogram/miniprogram/utils/parentApi.test.js"
MINIPROGRAM_SCOPE_TEST="$ROOT_DIR/miniprogram/miniprogram/parent-only-scope.test.js"
BRIDGE_TEST="$ROOT_DIR/miniprogram/backend/src/parent-wechat-bridge.test.ts"
WEBSITE_API_TEST="$ROOT_DIR/tests/test_wechat_parent_upload_api.py"
BASELINE_PROOF="$ROOT_DIR/scripts/ralph/miniprogram_upload_stability_proof.sh"
PRD_JSON="$ROOT_DIR/scripts/ralph/prd.json"

require_file "$PRD_JSON"
require_file "$BASELINE_PROOF"
require_file "$UPLOAD_MODEL_TEST"
require_file "$UPLOAD_PAGE_TEST"
require_file "$WRONGBOOK_TEST"
require_file "$PARENT_API_TEST"
require_file "$MINIPROGRAM_SCOPE_TEST"
require_file "$BRIDGE_TEST"
require_file "$WEBSITE_API_TEST"

require_text "$UPLOAD_MODEL_TEST" "appendLocalImages keeps existing images and appends new ones" "select image fixture"
require_text "$UPLOAD_MODEL_TEST" "addManualBoxToImage appends a manual box and selects it" "create box fixture"
require_text "$UPLOAD_MODEL_TEST" "buildUploadJobs creates one upload job per box across all images" "text reason upload job fixture"
require_text "$UPLOAD_MODEL_TEST" "buildUploadJobs falls back to text mode when a voice box has no recording file" "optional voice reason fallback fixture"
require_text "$UPLOAD_PAGE_TEST" "submitUpload exposes each parent-visible upload stage without real network calls" "crop export submit accepted ready happy path"
require_text "$UPLOAD_PAGE_TEST" "submitUpload reports crop export failure by item without clearing the draft" "crop/export failure fixture"
require_text "$UPLOAD_PAGE_TEST" "submitUpload keeps the original draft and allows retry after a retryable upload failure" "submit retry failure fixture"
require_text "$UPLOAD_PAGE_TEST" "pollUploadTasks exposes background processing when tasks remain pending" "polling still pending fixture"
require_text "$UPLOAD_PAGE_TEST" "pollUploadTasks exposes partial failure separately from total failure" "polling failed fixture"
require_text "$UPLOAD_PAGE_TEST" "pollUploadTasks survives one transient status request failure without losing accepted tasks" "polling ready after transient failure fixture"
require_text "$UPLOAD_PAGE_TEST" "restoreAcceptedUploadTasks resumes pending stored tasks without re-uploading cropped images" "accepted task recovery fixture"
require_text "$UPLOAD_PAGE_TEST" "openChildWrongbook keeps a clear progress path after upload acceptance" "wrongbook progress entry fixture"
require_text "$WRONGBOOK_TEST" "onShow refreshes ready upload task status before loading parent wrongbook and PDF state" "wrongbook refresh ready fixture"
require_text "$WRONGBOOK_TEST" "onShow reports failed upload tasks and marks failed wrongbook cards without AI success copy" "wrongbook failed task fixture"
require_text "$WRONGBOOK_TEST" "onShow keeps background-processing uploads visible and explains PDF is not ready yet" "wrongbook background and PDF not-ready fixture"
require_text "$WRONGBOOK_TEST" "openWrongQuestionLibraryPdf shows recovery messages for not-ready, download, and open failures" "PDF not-ready recovery fixture"
require_text "$PARENT_API_TEST" "submitParentWrongQuestion parses the upload bridge response" "parentApi task accepted fixture"
require_text "$PARENT_API_TEST" "submitParentWrongQuestion forwards the child reason text and audio url in upload form data" "parentApi optional voice/text payload fixture"
require_text "$PARENT_API_TEST" "fetchWrongQuestionUploadTask fetches the server task status" "parentApi task status fixture"
require_text "$BRIDGE_TEST" "parent upload bridge preserves website accepted task payloads with optional fields missing" "bridge accepted task fixture"
require_text "$BRIDGE_TEST" "parent upload bridge maps website enqueue failures as retryable" "bridge retryable failure fixture"
require_text "$BRIDGE_TEST" "parent bridge no longer exposes the AI box route" "bridge AI box removal fixture"
require_text "$WEBSITE_API_TEST" "test_worker_processes_pending_wrong_question_upload_task" "website worker ready fixture"
require_text "$WEBSITE_API_TEST" "test_worker_keeps_recognized_record_visible_when_pdf_rebuild_fails" "website PDF failure preservation fixture"
require_text "$WEBSITE_API_TEST" "test_wechat_upload_enqueue_failure_leaves_retryable_failed_task" "website enqueue failure fixture"
require_text "$MINIPROGRAM_SCOPE_TEST" "parent upload page exposes crop-first multi-image controls" "mini program AI box removal fixture"

run "$PYTHON_BIN" - <<'PY'
import json
import os
import sys
from pathlib import Path

root = Path.cwd()
prd = json.loads((root / "scripts/ralph/prd.json").read_text(encoding="utf-8"))
stories = prd.get("userStories", [])
pending = [story.get("id", "<missing id>") for story in stories if story.get("passes") is not True]
allow_current = os.environ.get("XR_RALPH_ALLOW_CURRENT_STORY_PENDING") == "1"

if pending and not (allow_current and pending == ["MP-UPLOAD-012"]):
    print("PRD pass gate failed: " + ", ".join(pending))
    sys.exit(1)

if pending:
    print("ok PRD pass gate: MP-UPLOAD-012 is the only pending story in pre-completion mode")
else:
    print(f"ok PRD pass gate: all {len(stories)} stories are passes=true")

active_roots = [
    root / "app.py",
    root / "smart_wrong_questions.py",
    root / "miniprogram/miniprogram",
    root / "miniprogram/backend/src",
]
forbidden = [
    "AI 框选",
    "wrong-question-boxes",
    "detectParentWrongQuestionBoxes",
    "runAiBoxes",
]
allowed_suffixes = {".js", ".json", ".ts", ".wxml", ".wxss", ".py"}
violations = []

def iter_active_files(path):
    if path.is_file():
        yield path
        return
    for candidate in path.rglob("*"):
        if not candidate.is_file():
            continue
        name = candidate.name
        if ".test." in name or name.endswith(".test.cjs"):
            continue
        if candidate.suffix not in allowed_suffixes:
            continue
        yield candidate

for active_root in active_roots:
    for source_path in iter_active_files(active_root):
        text = source_path.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                violations.append(f"{source_path.relative_to(root)} contains {needle}")

if violations:
    print("active AI box selection residue found:")
    for violation in violations:
        print(f"- {violation}")
    sys.exit(1)

print("ok active code AI box guard: no current AI box selection route/helper/copy remains")
PY

run node --test \
  "$UPLOAD_MODEL_TEST" \
  "$UPLOAD_PAGE_TEST" \
  "$WRONGBOOK_TEST" \
  "$PARENT_API_TEST"

echo
echo ">>> bridge upload acceptance tests"
(
  cd "$ROOT_DIR/miniprogram/backend"
  node --import tsx --test src/parent-wechat-bridge.test.ts
)

run "$PYTHON_BIN" -m unittest "$WEBSITE_API_TEST"
run "$BASELINE_PROOF"

if [[ "${XR_RALPH_ALLOW_CURRENT_STORY_PENDING:-}" == "1" ]]; then
  echo "parent upload 2.0 acceptance guardrail passed in pre-completion mode"
else
  echo "parent upload 2.0 acceptance guardrail passed"
fi
