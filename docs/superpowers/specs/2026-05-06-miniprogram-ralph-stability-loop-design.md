# Mini Program Ralph Stability Loop Design

Date: 2026-05-06

## Goal

Create a reusable Ralph loop for the Xingrun WeChat mini program that detects and improves stability before parents touch production flows. The loop focuses on the real parent path:

`open mini program -> upload wrong question -> check wrongbook -> generate/download/open PDF`

Binding and invite-code checks remain part of setup smoke when a story touches account or child selection, but this loop is mainly about upload, wrongbook, PDF, visual stability, and mini program 1.3 code quality.

## Scope

- Mini program parent pages under `miniprogram/miniprogram/`.
- Parent upload task path through bridge, Flask, Redis/RQ worker, wrongbook refresh, and PDF metadata.
- Student wrong-question library PDF generation and opening.
- LaTeX handling for wrong-question text, KaTeX browser rendering, and ReportLab fallback.
- Ralph instructions, proof scripts, runbooks, and handoff state.

## Non-Goals

- Do not redesign the product flow.
- Do not add AI box selection back.
- Do not use production invite codes unless the user explicitly provides a safe test code.
- Do not mark true-device stability complete without WeChat DevTools or real-phone evidence.

## Ralph Loop Gates

### 1. Context Gate

Every iteration must read:

- `AGENTS.md`
- `handoff.md`
- `miniprogram/handoff.md`
- `scripts/ralph/prd.json`
- `scripts/ralph/progress.txt`
- this design doc
- `scripts/ralph/miniprogram_stability_loop_instructions.md`

One iteration handles exactly one story. If proof fails, the story remains `passes=false` and there is no commit.

### 2. Real-Use Simulation Gate

For upload-related stories, Ralph must simulate the parent journey:

- open parent home
- choose current child when needed
- enter upload page
- take/select image
- add, drag, resize, delete, and rotate question boxes
- test very small/narrow question boxes
- submit with text reason
- submit with voice reason
- submit after switching to voice but recording nothing
- poll pending/ready/failed/retryable task states
- enter wrongbook from upload result
- refresh wrongbook progress
- open PDF

For binding-related stories, invite code usage is strict:

- never guess or type an invite code from memory
- only copy from `XR_TEST_CLASS_INVITE_CODE` or a user-provided safe test code
- print a masked code before using it, such as `AB***89`
- verify class name, teacher name, and student list before binding
- stop if no reliable test code is available

### 3. Visual Agent Gate

Every UI-facing story must use visual evidence:

- WeChat DevTools screenshot, real-phone screenshot/video frame, or user-provided screenshot
- at least one narrow phone size such as 360 x 800 or 375 x 667
- inspect text clipping, overlapping, awkward wrapping, touch target size, safe area, button hierarchy, and wasted space
- remove parent-facing developer leftovers such as raw IDs, debug wording, prototype wording, and technical pipeline details
- do not claim visual stability if no visual evidence was inspected

### 4. Mini Program 1.3 Code Stability Gate

Ralph must review the touched code for:

- unhandled `wx.*` API failures
- repeated submit or repeated crop/export hazards
- pending task loss after page close/reopen
- storage corruption causing blank state
- timeout paths that clear drafts too early
- stale AI box route/helper/copy
- dead code introduced by the fix
- WeChat runtime compatibility risks in page JS helpers
- narrow-screen layout risks in WXML/WXSS

Primary files:

- `miniprogram/miniprogram/pages/parent-home/`
- `miniprogram/miniprogram/pages/parent-upload/`
- `miniprogram/miniprogram/pages/parent-wrongbook/`
- `miniprogram/miniprogram/pages/parent-bind/`
- `miniprogram/miniprogram/utils/parentApi.js`

### 5. PDF And LaTeX Stability Gate

PDF stability is not just a mini program button check. Ralph must verify the full PDF path:

- upload task preserves a visible wrongbook record even if PDF rebuild fails
- wrongbook PDF metadata is honest when PDF is not ready
- `/api/wechat/student-libraries/<student_id>` returns a non-empty PDF when ready
- mini program handles `wx.downloadFile` and `wx.openDocument` failures with recovery copy
- browser renderer can render KaTeX into the student library PDF
- invalid LaTeX is preserved as readable source instead of crashing the page or PDF
- ReportLab fallback can normalize old/broken LaTeX into portable text

LaTeX stress cases must include:

- JSON-eaten backslashes such as `\frac`, `\text`, and `\mathbb{R}`
- bare LaTeX fragments outside `$...$`
- `\left`, `\right`, roots, powers, subscripts, and multi-line formulas
- Chinese prose mixed with formulas
- geometry/image records
- malformed formulas that should show raw source and continue rendering

Relevant files and tests:

- `ai_processor.py`
- `pdf_engine.py`
- `frontend/src/wrongQuestionLatex.js`
- `frontend/scripts/renderWrongQuestionLibraryPdf.mjs`
- `frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs`
- `tests/test_wrong_question_library_pdf.py`
- `tests/test_ai_processor_prompt.py`
- `frontend/src/wrong-question-latex.test.ts`
- `frontend/src/render-wrong-question-library-pdf.test.ts`
- `frontend/src/render-wrong-question-practice-sheet-pdf.test.ts`

### 6. Proof Gate

Every iteration must run proof through a temporary script and include the full output in the final report.

Baseline local proof:

```bash
scripts/ralph/miniprogram_visual_acceptance_guardrail_proof.sh
scripts/ralph/parent_upload_2_acceptance_guardrail_proof.sh
scripts/ralph/miniprogram_stability_loop_proof.sh
git diff --check
```

If the story touches upload behavior:

```bash
scripts/ralph/miniprogram_upload_stability_proof.sh
```

If the story touches production runbook, worker, PDF generation, or LaTeX:

```bash
scripts/ralph/production_upload_smoke_runbook_proof.sh
python -m unittest tests.test_wrong_question_library_pdf tests.test_ai_processor_prompt -v
cd frontend && npx tsx --test src/wrong-question-latex.test.ts src/render-wrong-question-library-pdf.test.ts src/render-wrong-question-practice-sheet-pdf.test.ts
```

True production smoke needs Redis, RQ worker, Flask, bridge, and a safe parent test account. Do not simulate that by guessing data.

## Completion Definition

A story can be marked `passes=true` only when:

- the focused fix is minimal
- all required proof passes
- visual evidence is inspected for UI changes
- PDF/LaTeX gate is covered for PDF-related changes
- remaining real-device gaps are explicitly recorded
- `progress.txt` and `handoff.md` are updated when state changes
- the verified change is committed
