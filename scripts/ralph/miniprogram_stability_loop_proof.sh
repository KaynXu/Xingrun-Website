#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DESIGN="$ROOT_DIR/docs/superpowers/specs/2026-05-06-miniprogram-ralph-stability-loop-design.md"
INSTRUCTIONS="$ROOT_DIR/scripts/ralph/miniprogram_stability_loop_instructions.md"
RUNBOOK="$ROOT_DIR/docs/production-upload-pipeline-smoke-runbook.md"

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

run() {
  echo
  echo ">>> $*"
  "$@"
}

cd "$ROOT_DIR"

require_file "$DESIGN"
require_file "$INSTRUCTIONS"
require_file "$RUNBOOK"
require_executable "$ROOT_DIR/scripts/ralph/miniprogram_visual_acceptance_guardrail_proof.sh"
require_executable "$ROOT_DIR/scripts/ralph/parent_upload_2_acceptance_guardrail_proof.sh"
require_executable "$ROOT_DIR/scripts/ralph/miniprogram_upload_stability_proof.sh"
require_executable "$ROOT_DIR/scripts/ralph/production_upload_smoke_runbook_proof.sh"

require_text "$DESIGN" "upload wrong question -> check wrongbook -> generate/download/open PDF" "real parent path"
require_text "$DESIGN" "PDF And LaTeX Stability Gate" "PDF and LaTeX gate"
require_text "$DESIGN" "Mini Program 1.3 Code Stability Gate" "mini program 1.3 code gate"
require_text "$DESIGN" "Visual Agent Gate" "visual agent gate"
require_text "$DESIGN" "never guess or type an invite code from memory" "invite code safety"
require_text "$DESIGN" "JSON-eaten backslashes" "old LaTeX transport stress"
require_text "$DESIGN" "ReportLab fallback" "ReportLab fallback coverage"
require_text "$DESIGN" "wx.downloadFile" "mini program PDF download coverage"
require_text "$DESIGN" "wx.openDocument" "mini program PDF open coverage"

require_text "$INSTRUCTIONS" "上传错题 -> 查看错题本 -> 生成/下载/打开 PDF" "Ralph prompt real path"
require_text "$INSTRUCTIONS" "不准猜、不准手打生产码" "Ralph prompt invite code safety"
require_text "$INSTRUCTIONS" "必须看截图或录屏帧" "Ralph prompt visual evidence"
require_text "$INSTRUCTIONS" "小程序 1.3 代码检查" "Ralph prompt code review"
require_text "$INSTRUCTIONS" "PDF / LaTeX 稳定性" "Ralph prompt PDF and LaTeX"
require_text "$INSTRUCTIONS" "LaTeX 渲染失败不能让 PDF 生成崩掉" "Ralph prompt LaTeX crash guard"

require_text "$RUNBOOK" "PDF And LaTeX Render Stability" "runbook PDF and LaTeX section"
require_text "$RUNBOOK" "tests.test_wrong_question_library_pdf tests.test_ai_processor_prompt" "runbook Python PDF tests"
require_text "$RUNBOOK" "src/wrong-question-latex.test.ts" "runbook frontend LaTeX tests"
require_text "$RUNBOOK" "src/render-wrong-question-library-pdf.test.ts" "runbook library PDF renderer tests"
require_text "$RUNBOOK" "src/render-wrong-question-practice-sheet-pdf.test.ts" "runbook practice PDF renderer tests"

require_text "$ROOT_DIR/tests/test_wrong_question_library_pdf.py" "test_generate_student_wrong_question_library_pdf_falls_back_to_reportlab_when_browser_render_fails" "ReportLab fallback test"
require_text "$ROOT_DIR/tests/test_wrong_question_library_pdf.py" "test_recognize_wrong_question_image_rewrites_when_latex_render_check_fails" "LaTeX rewrite test"
require_text "$ROOT_DIR/tests/test_wrong_question_library_pdf.py" "test_build_portable_wrong_question_text_repairs_broken_latex_for_reportlab_fallback" "broken LaTeX portable text test"
require_text "$ROOT_DIR/frontend/src/wrong-question-latex.test.ts" "reports invalid latex but keeps the raw source visible" "invalid LaTeX frontend test"
require_text "$ROOT_DIR/frontend/src/render-wrong-question-library-pdf.test.ts" "class=\"katex\"" "library PDF KaTeX test"
require_text "$ROOT_DIR/frontend/src/render-wrong-question-practice-sheet-pdf.test.ts" "question-latex-card" "practice PDF KaTeX test"
require_text "$ROOT_DIR/scripts/ralph/miniprogram_upload_stability_proof.sh" "parent-wrongbook/latex-preview.test.js" "mini program wrongbook latex preview baseline"

run "$ROOT_DIR/scripts/ralph/production_upload_smoke_runbook_proof.sh"
run git diff --check

echo "mini program Ralph stability loop proof passed"
