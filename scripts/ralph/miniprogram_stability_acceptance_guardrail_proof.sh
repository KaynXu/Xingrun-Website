#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRD_FILE="$ROOT_DIR/scripts/ralph/prd.json"
PROGRESS_FILE="$ROOT_DIR/scripts/ralph/progress.txt"
DESIGN_FILE="$ROOT_DIR/docs/superpowers/specs/2026-05-06-miniprogram-ralph-stability-loop-design.md"
INSTRUCTIONS_FILE="$ROOT_DIR/scripts/ralph/miniprogram_stability_loop_instructions.md"
VISUAL_PROOF="$ROOT_DIR/scripts/ralph/miniprogram_visual_acceptance_guardrail_proof.sh"
PARENT_UPLOAD_PROOF="$ROOT_DIR/scripts/ralph/parent_upload_2_acceptance_guardrail_proof.sh"
STABILITY_LOOP_PROOF="$ROOT_DIR/scripts/ralph/miniprogram_stability_loop_proof.sh"
UPLOAD_PROOF="$ROOT_DIR/scripts/ralph/miniprogram_upload_stability_proof.sh"
PRODUCTION_RUNBOOK_PROOF="$ROOT_DIR/scripts/ralph/production_upload_smoke_runbook_proof.sh"

if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="$PYTHON"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

require_command() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "missing command: $name"
    exit 1
  fi
  echo "ok command: $name"
}

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "missing file: ${path#$ROOT_DIR/}"
    exit 1
  fi
  echo "ok file: ${path#$ROOT_DIR/}"
}

require_executable() {
  local path="$1"
  if [[ ! -x "$path" ]]; then
    echo "missing executable: ${path#$ROOT_DIR/}"
    exit 1
  fi
  echo "ok executable: ${path#$ROOT_DIR/}"
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

require_json_value() {
  local filter="$1"
  local expected="$2"
  local label="$3"
  local actual
  actual="$(jq -r "$filter" "$PRD_FILE")"
  if [[ "$actual" != "$expected" ]]; then
    echo "unexpected $label"
    echo "expected: $expected"
    echo "actual: $actual"
    exit 1
  fi
  echo "ok $label"
}

run() {
  echo
  echo ">>> $*"
  if [[ "${XR_RALPH_COMPACT_PROOF:-}" == "1" ]]; then
    local output_file
    output_file="$(mktemp /tmp/xingrun_mp_stability_guardrail_XXXXXX.log)"
    if "$@" >"$output_file" 2>&1; then
      echo "ok command passed: $*"
      rm -f "$output_file"
    else
      local status=$?
      cat "$output_file"
      rm -f "$output_file"
      exit "$status"
    fi
  else
    "$@"
  fi
}

run_frontend_pdf_latex_tests() {
  echo
  echo ">>> frontend PDF/LaTeX renderer tests"
  if [[ "${XR_RALPH_COMPACT_PROOF:-}" == "1" ]]; then
    local output_file
    output_file="$(mktemp /tmp/xingrun_mp_stability_frontend_pdf_XXXXXX.log)"
    if (
      cd "$ROOT_DIR/frontend"
      npx tsx --test \
        src/wrong-question-latex.test.ts \
        src/render-wrong-question-library-pdf.test.ts \
        src/render-wrong-question-practice-sheet-pdf.test.ts
    ) >"$output_file" 2>&1; then
      echo "ok command passed: frontend PDF/LaTeX renderer tests"
      rm -f "$output_file"
    else
      local status=$?
      cat "$output_file"
      rm -f "$output_file"
      exit "$status"
    fi
  else
    (
      cd "$ROOT_DIR/frontend"
      npx tsx --test \
        src/wrong-question-latex.test.ts \
        src/render-wrong-question-library-pdf.test.ts \
        src/render-wrong-question-practice-sheet-pdf.test.ts
    )
  fi
}

print_manual_smoke_checks() {
  cat <<'CHECKS'

Remaining manual smoke checks not claimed by this automated proof:
- WeChat DevTools narrow-screen smoke for parent-home, parent-upload, parent-wrongbook, and parent-bind.
- Real-phone smoke for upload image/camera, tiny/narrow boxes, rotate/delete, text reason, voice/no-recording reason, retry, wrongbook refresh, PDF download, and wx.openDocument.
- Production Redis/RQ worker smoke with a safe parent test account and a real accepted upload task.
- Production PDF smoke after a real upload reaches ready, including PDF metadata, download, openDocument, and malformed/indexed-root LaTeX readability.
CHECKS
}

cd "$ROOT_DIR"

require_command jq
require_command node
require_command npm
require_file "$PRD_FILE"
require_file "$PROGRESS_FILE"
require_file "$DESIGN_FILE"
require_file "$INSTRUCTIONS_FILE"
require_executable "$VISUAL_PROOF"
require_executable "$PARENT_UPLOAD_PROOF"
require_executable "$STABILITY_LOOP_PROOF"
require_executable "$UPLOAD_PROOF"
require_executable "$PRODUCTION_RUNBOOK_PROOF"

echo
echo ">>> final stability PRD contracts"
require_json_value '.project' "Xingrun WeChat Mini Program" "active PRD project"
require_json_value '.branchName' "ralph/miniprogram-parent-stability" "active PRD branch"
require_json_value '(.userStories | length | tostring)' "9" "exactly nine MP-STABILITY stories"
require_json_value '([.userStories[].id | test("^MP-STABILITY-[0-9]{3}$")] | all | tostring)' "true" "all story ids are MP-STABILITY"
require_json_value '([.userStories[].id] | join(","))' "MP-STABILITY-001,MP-STABILITY-002,MP-STABILITY-003,MP-STABILITY-004,MP-STABILITY-005,MP-STABILITY-006,MP-STABILITY-007,MP-STABILITY-008,MP-STABILITY-009" "active stability queue ids"
require_json_value '([.userStories[].priority] | sort | join(","))' "1,2,3,4,5,6,7,8,9" "story priorities are one through nine"
require_json_value '([.scope[] | contains("miniprogram/miniprogram/")] | any | tostring)' "true" "parent-facing mini program scope"
require_json_value '([.description, (.scope[])] | map(contains("upload-to-wrongbook-to-PDF")) | any | tostring)' "true" "upload-to-wrongbook-to-PDF scope"
require_json_value '([.nonGoals[] | contains("website React admin/frontend")] | any | tostring)' "true" "unrelated website work is excluded"
require_json_value '([.nonGoals[] | contains("payment, account approval, weekly followup, lesson planning, classroom")] | any | tostring)' "true" "unrelated business workflows are excluded"
require_json_value '([.userStories[] | select(.id == "MP-STABILITY-009") | .acceptanceCriteria[] | contains("final acceptance proof script")] | any | tostring)' "true" "final guardrail acceptance criterion"
require_json_value '([.verificationBaseline[] | contains("scripts/ralph/miniprogram_visual_acceptance_guardrail_proof.sh")] | any | tostring)' "true" "visual guardrail baseline"
require_json_value '([.verificationBaseline[] | contains("scripts/ralph/parent_upload_2_acceptance_guardrail_proof.sh")] | any | tostring)' "true" "parent upload guardrail baseline"
require_json_value '([.verificationBaseline[] | contains("scripts/ralph/miniprogram_stability_loop_proof.sh")] | any | tostring)' "true" "stability loop proof baseline"
require_json_value '([.verificationBaseline[] | contains("scripts/ralph/miniprogram_upload_stability_proof.sh")] | any | tostring)' "true" "upload stability proof baseline"
require_json_value '([.verificationBaseline[] | contains("scripts/ralph/production_upload_smoke_runbook_proof.sh")] | any | tostring)' "true" "production PDF/LaTeX runbook proof baseline"
require_json_value '([.verificationBaseline[] | contains("tests.test_wrong_question_library_pdf tests.test_ai_processor_prompt")] | any | tostring)' "true" "backend PDF/LaTeX test baseline"
require_json_value '([.verificationBaseline[] | contains("wrong-question-latex.test.ts")] | any | tostring)' "true" "frontend LaTeX test baseline"

pending_stories="$(jq -r '[.userStories[] | select(.passes != true) | .id] | join(",")' "$PRD_FILE")"
if [[ -z "$pending_stories" ]]; then
  echo "ok all MP-STABILITY stories are passes=true"
elif [[ "${XR_RALPH_ALLOW_CURRENT_STORY_PENDING:-}" == "1" && "$pending_stories" == "MP-STABILITY-009" ]]; then
  echo "ok pre-completion mode: MP-STABILITY-009 is the only pending story"
else
  echo "pending MP-STABILITY stories: $pending_stories"
  exit 1
fi

require_text "$DESIGN_FILE" "upload wrong question -> check wrongbook -> generate/download/open PDF" "design real parent path"
require_text "$DESIGN_FILE" "Visual Agent Gate" "design visual gate"
require_text "$DESIGN_FILE" "PDF And LaTeX Stability Gate" "design PDF and LaTeX gate"
require_text "$DESIGN_FILE" "do not claim visual stability if no visual evidence was inspected" "design manual visual honesty"
require_text "$INSTRUCTIONS_FILE" "必须看截图或录屏帧" "instruction visual evidence"
require_text "$INSTRUCTIONS_FILE" "LaTeX 渲染失败不能让 PDF 生成崩掉" "instruction LaTeX crash guard"
require_text "$PROGRESS_FILE" "WeChat DevTools" "progress manual WeChat DevTools checks"
require_text "$PROGRESS_FILE" "real narrow phone" "progress manual real-phone checks"
require_text "$PROGRESS_FILE" "Production Redis/RQ worker smoke" "progress manual production Redis/RQ check"
require_text "$PROGRESS_FILE" "Production PDF open smoke" "progress manual production PDF check"

run "$VISUAL_PROOF"
run "$PARENT_UPLOAD_PROOF"
run "$STABILITY_LOOP_PROOF"
run "$UPLOAD_PROOF"
run "$PRODUCTION_RUNBOOK_PROOF"
run "$PYTHON_BIN" -m unittest tests.test_wrong_question_library_pdf tests.test_ai_processor_prompt -v
run_frontend_pdf_latex_tests
run git diff --check
print_manual_smoke_checks

if [[ -z "$pending_stories" ]]; then
  echo "final mini program stability acceptance guardrail passed"
else
  echo "final mini program stability acceptance guardrail passed in pre-completion mode"
fi
