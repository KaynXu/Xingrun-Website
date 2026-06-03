# Wrong Question Ingestion And Chat Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This plan is intentionally adapted to the current workspace rule: **do not use a worktree for this effort unless the user explicitly changes that instruction**.

**Goal:** Extend the current WeChat-rooted wrong-question pipeline into a general wrong-question ingestion platform that can accept uploads from an AI chat session or a batch workbench, guide the student through why they got a problem wrong, and then archive the original assets, structured recognition result, error details, and conversation summary back into the existing wrong-question library.

**Architecture:** V1 keeps Flask + RQ + SQLite as the main execution path and introduces a generic ingestion layer beneath the existing WeChat flow. The new layer stores upload runs, source assets, and cross-source submission metadata. WeChat upload remains a first-party client of that layer. AI chat upload and a future desktop-style workbench then attach to the same ingestion backbone. LangGraph and a knowledge graph remain optional orchestration and enrichment layers, not the first execution dependency.

**Tech Stack:** Flask, SQLite, Python `unittest`, existing `wrong_question_upload_worker.py`, existing AI processor helpers, optional PaddleOCR / EnsExam / LangGraph integration in later phases.

---

## Delivery Principles

- Keep the first usable slice low-complexity: open the data model and generic ingestion boundary before building new UI.
- Do not fork the product into separate systems for WeChat, workspace, and AI chat. They should converge into one wrong-question record model.
- Preserve the current WeChat upload flow while adding extension points for `workspace` and `ai_chat`.
- Treat the AI chat experience and the batch workbench as two front doors into one shared archival loop.
- Record AGPL-3.0 and deployment-license risk any time `error_correction` modules are reused directly.

## File Map

- Modify: `docs/wrong-questions/wrong-question-system-review-20260603.md`
  - Already contains the migration assessment and product-shape review that this execution plan turns into delivery steps.
- Create: `docs/superpowers/plans/2026-06-03-wrong-question-ingestion-chat-loop-implementation.md`
  - This implementation plan.
- Modify: `lesson_manager.py`
  - Add generic ingestion tables, cross-source wrong-question submission fields, and source-agnostic persistence helpers.
- Modify: `app.py`
  - Add generic ingestion endpoints and AI chat upload orchestration in later tasks.
- Modify: `wrong_question_upload_worker.py`
  - Reuse the generic ingestion layer instead of treating WeChat upload as a special one-off pipeline.
- Modify: `ai_processor.py`
  - Add optional adapters for OCR simplification, split/correct prompts, and guided error-summary generation.
- Modify: `tests/`
  - Add focused storage and API tests per phase.

## Phase Plan

### Phase 1: Generic Ingestion Foundation

**Outcome:** The repository can persist wrong-question uploads from non-WeChat sources without faking a parent binding.

- [x] Add a detailed implementation plan artifact tied to the existing review doc.
- [x] Extend `wrong_question_submissions` for cross-source archival:
  - `ingestion_run_id`
  - `chat_session_id`
  - `question_structured_json`
  - `knowledge_tags_json`
  - `needs_teacher_confirmation`
  - `confirmation_reasons_json`
- [x] Relax `parent_wechat_account_id` and `binding_id` so non-WeChat submissions can be stored natively.
- [x] Add `wrong_question_ingestion_runs` and `wrong_question_assets`.
- [x] Add data-layer helpers for:
  - creating ingestion runs
  - updating ingestion run status
  - attaching source assets
  - creating generic wrong-question submissions for `wechat_mp | workspace | ai_chat`
- [x] Widen the student wrong-question library query so future `workspace` and `ai_chat` records can enter the same archive loop when recognized and active.
- [x] Add storage tests for schema migration, generic submission creation, and ingestion-run persistence.

### Phase 2: Generic Backend API And Async Pipeline

**Outcome:** Upload orchestration moves from a WeChat-specific API shape to a source-agnostic ingestion contract.

- [x] Add `POST /api/wrong-question-ingestions`.
- [x] Add `GET /api/wrong-question-ingestions/<run_id>`.
- [x] Add `POST /api/wrong-question-ingestions/<run_id>/ocr`.
- [x] Add `POST /api/wrong-question-ingestions/<run_id>/split`.
- [x] Add `POST /api/wrong-question-ingestions/<run_id>/archive`.
- [x] Refactor the current upload worker so `wechat_wrong_question_upload_tasks` can hand off into generic ingestion runs instead of owning the only async path.
- [x] Preserve current mini-program behavior by adapting WeChat upload into the new backend boundary rather than deleting it.
- [x] Add targeted API tests for generic ingestion endpoints.
- [x] Add worker tests for generic ingestion handoff.

### Phase 3: AI Chat Guided Wrong-Question Loop

**Outcome:** A student can upload a wrong question in chat and be guided into reflection before the record is archived.

- [x] Add `wrong_question_chat_sessions` and `wrong_question_chat_messages` persistence.
- [x] Add `POST /api/wrong-question-chats/<session_id>/stream`.
- [x] Add a guided teaching prompt that asks, in order:
  - whether the student knows why they got it wrong
  - which step or concept they do not understand
  - whether they want a hint first or a full replay
- [x] Store the chat summary, student self-reported error reason, and follow-up status on the archived wrong-question record.
- [x] Route low-confidence OCR / empty stem / uncertain knowledge-tag cases into `needs_teacher_confirmation=1`.
- [x] Add end-to-end tests that prove: upload in chat -> reflective questioning -> archive into wrong-question library.

Current V1 note:
- The chat loop currently uses a deterministic three-step coaching flow on top of Flask + SQLite. That is intentional for low complexity. LangGraph / knowledge-graph orchestration should layer on later only after this archive loop is stable.

### Phase 4: Workbench Migration And Rich Recognition

**Outcome:** The product gains a teacher/operator workbench for high-volume PDF and image ingestion while sharing the same archive model as AI chat.

- [ ] Add a workbench-oriented upload flow for multi-page PDFs and image batches.
- [ ] Reuse or transplant these `error_correction` building blocks where complexity stays acceptable:
  - OCR simplification
  - overlapping-page split batching
  - structured output fallback
  - split / correction prompts
  - Teach Agent guided prompts
- [ ] Evaluate direct reuse vs rewrite for:
  - Vue workbench UI
  - SQLAlchemy session state
  - export/archive surfaces
- [ ] Add optional adapters for:
  - EnsExam handwriting erasure
  - PaddleOCR client
  - LangGraph orchestration
  - knowledge-graph enrichment
- [ ] Add fallback behavior: if EnsExam or PaddleOCR is unavailable, fall back to existing AI vision recognition without blocking upload.

## Reality Check

The repository now has a meaningful amount of the **backend backbone**, but the **final product shape is still incomplete**.

What is already true:

- Generic wrong-question ingestion storage exists.
- WeChat upload now hands off into generic ingestion runs.
- AI chat can already run a minimal guided reflection loop and archive into the same wrong-question library.

What is **not** true yet:

- There is no end-user AI chat upload UI that fully uses this loop.
- There is no operator workbench for multi-page PDF / batch ingestion.
- `error_correction` OCR simplification / overlapping split / correction flow has not yet been transplanted into live product code.
- Teacher confirmation, archived detail review, and mastery follow-up are not yet complete product flows.

That distinction matters. The plan below should be read as:

- **Phase 1-3:** backend base and minimal archive loop
- **Phase 4-7:** the work needed to turn that base into the actual target product

## Detailed Development List

The list below is intentionally more detailed than the high-level phase plan. It reflects:

- the original wrong-question review document
- the `error_correction` migration assessment
- the current codebase state after Phase 1-3 backend work
- the final desired product shape: `AI chat upload -> guided reflection -> archive -> later follow-up`

### Track A: Backend Backbone And Orchestration

#### A1. Generic ingestion foundation

- [x] Cross-source wrong-question archive model (`wechat_mp | workspace | ai_chat`)
- [x] `wrong_question_ingestion_runs`
- [x] `wrong_question_assets`
- [x] Generic archive APIs (`create / detail / ocr / split / archive`)
- [x] WeChat worker handoff into ingestion runs

#### A2. AI chat archival foundation

- [x] `wrong_question_chat_sessions`
- [x] `wrong_question_chat_messages`
- [x] Minimal guided reflection loop
- [x] Archive into wrong-question library from AI chat
- [x] Teacher-confirmation fallback for missing stem / missing tags / missing image

#### A3. Next backend hardening tasks

- [x] Add chat-session read/recovery API for UI resume and page reload.
- [ ] Add ingestion-run list/history API so a future workbench can reopen unfinished runs.
- [ ] Add explicit `current_step` / stage tracking on ingestion runs instead of relying only on `status`.
- [ ] Add richer archive detail linkage so wrong-question detail can open the related ingestion run and chat session directly.
- [ ] Add retry-safe idempotency rules for chat archive finalization and workbench archive finalization.

### Track B: AI Chat Product Entry

This track is the shortest path to the intended end-user product.

#### B1. Minimal end-user chat surface

- [ ] Connect the current AI chat UI to `wrong-question-chats/<session_id>/stream`.
- [ ] Support upload of one or more wrong-question images into the chat session.
- [ ] Show current reflection stage and assistant prompt in UI.
- [ ] Support session reload / resume using persisted chat history.
- [ ] Show archive result inline after final reflection step.

#### B2. Archive-quality chat experience

- [ ] Add archive preview before final save: original image, recognized stem, tags, reflection summary.
- [ ] Let student choose `先看提示` vs `完整复盘` without losing the archive loop.
- [ ] Preserve assistant-side structured summary separately from student-visible reply text.
- [ ] Add explicit `needs_teacher_confirmation` banner in chat when archive confidence is low.

#### B3. Closed-loop follow-up

- [ ] Link archived wrong question back into later AI follow-up.
- [ ] Use same chat record to drive later re-practice and mastery checks.
- [ ] Add mastery status inputs and repeated-error signals after later practice attempts.

### Track C: Workbench / error_correction Product Entry

This is the shortest path to the operator/teacher workbench requested by the review.

#### C1. Workbench-ready ingestion state

- [ ] Add batch upload support for multi-page PDF and image sets.
- [ ] Store per-page asset metadata needed for OCR preview and split review.
- [ ] Support unfinished run reopen / continue.
- [ ] Support manual correction of OCR and split results before archive.

#### C2. Reuse `error_correction` backend building blocks

- [ ] Transplant `prepare_input()`-style normalization where it reduces preprocessing drift.
- [ ] Reuse `simplify_ocr_results()` as the OCR-to-agent boundary.
- [ ] Reuse overlapping-page split batching (`batch_size=2`, `overlap=1`) for multi-page papers.
- [ ] Reuse structured-output schema concepts for `question_structured_json`.
- [ ] Reuse split / OCR correction prompt rules where they fit current provider setup.

#### C3. Workbench UI

- [ ] Build a React workbench entry for upload / OCR preview / split review / archive.
- [ ] Do not port Vue pages directly; port flows and information architecture only.
- [ ] Support PDF page thumbnails, OCR block preview, split result list, archive selection.
- [ ] Support teacher/operator editing before import into the wrong-question library.

### Track D: Recognition And Processing Adapters

These are deliberately delayed until the shared ingestion backbone is stable.

#### D1. Optional adapters

- [ ] EnsExam handwriting erasure adapter
- [ ] PaddleOCR adapter for workbench-oriented OCR
- [ ] LangGraph orchestration adapter for resumable graph execution
- [ ] Knowledge-graph enrichment adapter for concept relations and similar-question retrieval

#### D2. Fallback rules

- [ ] If EnsExam is unavailable, continue without erasure.
- [ ] If PaddleOCR is unavailable, fall back to current AI-vision recognition.
- [ ] If LangGraph is unavailable, keep Flask + RQ orchestration as the default runtime.

### Track E: Wrong-Question Record Detail And Teacher Review

#### E1. Archive detail completeness

- [ ] Wrong-question detail should show original assets, OCR/split trail, chat summary, and archive source.
- [ ] Teacher should be able to see why `needs_teacher_confirmation` was triggered.
- [ ] Teacher should be able to fix question text, tags, and confirmation state from the archive detail.

#### E2. Teacher confirmation workflow

- [ ] Add explicit review queue/filter for records needing confirmation.
- [ ] Add confirmation actions: confirm, edit-then-confirm, return-for-rework.
- [ ] Persist confirmation outcome and reviewer identity.

### Track F: PDF / Practice Sheet Product Surface

This track turns the archived wrong-question record into the student-facing revision artifact.

#### F1. Template structure

- [ ] Upgrade PDF/practice output to the minimum four core areas:
  - `原题 / 原图`
  - `方法提醒`
  - `挖空复盘`
  - `订正区`
- [ ] Add the broader recommended structure:
  - metadata header
  - `错因定位 / 本次目标`
  - `老师反馈区`
  - `需老师确认`

#### F2. Content schema

- [ ] Split current prompt output into:
  - `mistake_focus`
  - `review_goal`
  - `method_hint_lines[]`
  - `blank_review_blocks[]`
  - `teacher_feedback`
  - `confirmation_reasons[]`
- [ ] Stop passing two opaque writing prompts straight into layout.

#### F3. Quality rules

- [ ] Geometric / diagram-heavy records must preserve image traceability.
- [ ] Add banned-phrasing scan to reduce template-sounding AI wording.
- [ ] Add PDF eval cases for long problems, multi-image problems, proofs, function graphs, and review-required records.

### Track G: Evaluation, Labeling, And Long-Term Accuracy

#### G1. Evaluation layer

- [ ] Create a representative eval set for recognition, structure, archive quality, and practice-sheet quality.
- [ ] Run eval on every prompt/template/rule change.
- [ ] Track archive quality regressions separately from OCR quality regressions.

#### G2. Human feedback and labeling

- [ ] Add explicit labels for:
  -题型
  -错因
  -知识点
  -是否需老师确认
  -老师修改原因
  -掌握情况/复发情况
- [ ] Store feedback so repeated-error patterns can drive mastery grading.

#### G3. Model strategy

- [ ] Start with rules + schema + eval + few-shot.
- [ ] Add lightweight classifiers before fine-tuning.
- [ ] Only consider fine-tuning after enough high-quality labeled cards exist.

## Recommended Priority Order

This is the practical execution order after the work already completed:

1. **A3 + B1**
   - Make the AI chat loop recoverable and UI-ready.
   - Why first: this is the shortest path from today’s backend base to the target product shape.

2. **E1**
   - Make archived records explainable and reviewable.
   - Why second: once chat archive exists, teachers need to trust and inspect it.

3. **C1**
   - Make the ingestion runtime workbench-ready before building a full operator UI.
   - Why third: this preserves extensibility without introducing UI complexity too early.

4. **C2 + C3**
   - Migrate the highest-value `error_correction` backend flows and then add the React workbench.

5. **F1-F3**
   - Upgrade the student-facing revision artifact and review sheet structure.

6. **G1-G3**
   - Turn the system into a measurable, improvable long-term loop.

## Product Structure Recommendation

The final product should not be limited to a rigid four-block rendering, but it must at least preserve the pedagogically critical core:

1. `原题 / 原图`
2. `方法提醒`
3. `挖空复盘`
4. `订正区`

The complete product shape should also include:

- page/header metadata
- error-cause定位 and current-session goal
- teacher feedback / confirmation state
- source assets and OCR traceability
- AI chat summary and student self-reflection
- archive/export state for the wrong-question library

## Acceptance Anchors

- [ ] A single image uploaded in AI chat can trigger a guided reflection flow and then archive into the existing wrong-question library.
- [ ] A multi-page PDF uploaded in the workbench can pass through upload, erase, OCR preview, split, correction, and archive.
- [ ] Missing image / blank stem / uncertain knowledge tags / OCR ambiguity all set `needs_teacher_confirmation`.
- [ ] Archived wrong-question detail can open both the original asset trail and the related AI chat summary.
- [ ] Existing WeChat upload and teacher review flows still pass without regression.

## Current Round

The latest completed slices are **Phase 1** data foundations and the core of **Phase 2**: generic ingestion APIs plus WeChat worker handoff into ingestion runs. The next highest-value task is **Phase 3 chat-session persistence and guided dialogue orchestration**, because the storage/API base is now strong enough to support the intended AI chat upload loop.
