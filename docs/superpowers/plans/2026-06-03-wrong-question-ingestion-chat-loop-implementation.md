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
- A first AI chat upload UI now exists inside the smart wrong-question notebook modal, including image upload, three-step reflection, resume, and inline archive result.

What is **not** true yet:

- There is no standalone student-facing AI chat entry outside the current smart wrong-question notebook modal.
- There is no operator workbench for multi-page PDF / batch ingestion.
- `error_correction` OCR simplification / overlapping split / correction flow has not yet been transplanted into live product code.
- Teacher confirmation, archived detail review, and mastery follow-up are not yet complete product flows.
- Later re-practice and follow-up results are still only loosely connected to the archive record; the system does not yet have a durable mastery-evidence spine that can support评级 by repeated wrong knowledge points or error causes.

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
- [x] Add ingestion-run list/history API so a future workbench can reopen unfinished runs.
- [x] Add explicit `current_step` / stage tracking on ingestion runs instead of relying only on `status`.
- [x] Add richer archive detail linkage so wrong-question detail can open the related ingestion run and chat session directly.
- [x] Add retry-safe idempotency rules for chat archive finalization and workbench archive finalization.

### Track S: Shared Content Schema And Feedback Spine

This track is now the highest-leverage foundation. It keeps us from overfitting the next phase to either the current modal chat UI or the legacy two-prompt PDF layout.

#### S1. Structured practice-content boundary

- [ ] Introduce a shared structured practice-content schema that can survive across archive detail, teacher review, PDF rendering, and later AI follow-up.
- [ ] Keep the current `reason_blank_prompt / improvement_summary_prompt` fields as compatibility outputs, but stop treating them as the long-term canonical model.
- [ ] Store at least:
  - `mistake_focus`
  - `review_goal`
  - `method_hint_lines[]`
  - `blank_review_blocks[]`
  - `teacher_feedback`
  - `confirmation_reasons[]`
- [ ] Make the PDF and follow-up surfaces consume this schema gradually instead of hard-coding two opaque writing boxes forever.

#### S2. Review and version metadata

- [x] Add prompt/template/rule/model version tracking to archive and practice generation records.
- [x] Add explicit reviewer/outcome metadata anywhere a teacher confirmation changes the final record.
- [ ] Keep AI-generated rule suggestions separate from approved production rules.

Progress note (2026-06-03):
- Local wrong-question archive records now carry confirmation reviewer/outcome metadata (`confirmation_status / confirmation_reviewed_by / confirmation_reviewed_at`) and expose it through the unified wrong-question API, so later workbench and queue flows can reuse the same review spine instead of inventing a second approval model.
- Practice generation and local archive records now also persist `generation_metadata_json`, covering `schema / prompt / template / rule / provider / model / entrypoint` in a shared shape. The practice AI helper emits this metadata at both sheet and item scope, the async sheet job stores it on `wrong_question_practice_sheets` and `wrong_question_practice_sheet_items`, and `ai_chat` archive finalization stores the same kind of spine on `wrong_question_submissions`.

#### S3. Human feedback loop

- [ ] Add a structured feedback table for teacher/student/parent corrections on wrong-question cards and practice sheets.
- [ ] Record whether a fix is local-only, should become a rule candidate, or should become an eval case.
- [ ] Turn repeated-error and mastery feedback into first-class signals, not just free-text notes.
- [ ] Add a minimal mastery-evidence spine on each archive record so later practice/follow-up attempts can write back `latest_attempt`, `attempt_count`, and repeated-topic/repeated-error summaries before we attempt richer评级.

### Track B: AI Chat Product Entry

This track is the shortest path to the intended end-user product.

#### B1. Minimal end-user chat surface

- [x] Connect the current AI chat UI to `wrong-question-chats/<session_id>/stream`.
- [x] Support upload of one or more wrong-question images into the chat session.
- [x] Show current reflection stage and assistant prompt in UI.
- [x] Support session reload / resume using persisted chat history.
- [x] Show archive result inline after final reflection step.

Current V1 note:
- This first UI slice lives inside `frontend/src/SmartWrongQuestionsPage.tsx` as a notebook-modal chat panel. It is intentionally a low-complexity bridge into the existing workspace, not yet the final standalone student chat surface.

#### B2. Archive-quality chat experience

- [x] Add archive preview before final save: original image, recognized stem, tags, reflection summary.
- [x] Let student choose `先看提示` vs `完整复盘` without losing the archive loop.
- [x] Preserve assistant-side structured summary separately from student-visible reply text.
- [x] Add explicit `needs_teacher_confirmation` banner in chat when archive confidence is low.

#### B3. Closed-loop follow-up

- [ ] Link archived wrong question back into later AI follow-up.
- [ ] Use same chat record to drive later re-practice and mastery checks.
- [ ] Add mastery status inputs and repeated-error signals after later practice attempts.
- [ ] Persist re-practice evidence back onto the same archive record instead of leaving it stranded in standalone practice-sheet history.
- [ ] Reuse the same archive / chat chain when the system asks “这次真的掌握了吗” after another attempt.
- [ ] Grade mastery from later evidence using similar `topic_category` / `primary_error_type` / `knowledge_tags`, not only a manual checkbox.

Progress note (2026-06-03):
- Weekly follow-up candidates now include archived `ai_chat` records, return source-record navigation context, and expose repeated-category signals.
- Unified local review now lets teachers mark `ai_chat` archive records as mastered so they can fall out of later weekly follow-up priority.
- A first compatibility slice has started on the practice-sheet side: practice items can now carry a structured content payload in parallel with the legacy dual-prompt fields, so later PDF and review work can migrate incrementally instead of via a big-bang rewrite.
- Returned local `ai_chat` archive records can now reopen into a fresh rework chat session from the existing notebook chat panel. The rework session reuses the same ingestion context, seeds a teacher-return prompt, and on re-archive updates the original wrong-question record in place instead of creating a duplicate card.
- Confirmed or review-free local `ai_chat` archive records can now flow into the existing notebook practice-sheet pipeline. Teachers can select them alongside local wechat records once confirmation is complete, and the same async practice worker now consumes `ai_chat` snapshots without needing a parallel repractice product surface.
- Archive records now also carry a minimal mastery-evidence spine: later practice-sheet lifecycle changes write `practice_sheet_count / latest_practice_* / related_topic_categories / related_error_types` back onto the same wrong-question record, and unified detail now derives a first evidence-based mastery assessment from teacher confirmation state, re-practice status, and same-student repeated topic/error signals.
- Confirmed or review-free local `ai_chat` archive records can now reopen into a dedicated mastery-followup chat from the same notebook panel. The follow-up session reuses the original ingestion context, seeds a mastery-check prompt from `mastery_assessment + mastery_tracking`, and on re-archive updates the original wrong-question record in place instead of creating a parallel record. When the follow-up archive omits already-known stem or tag fields, the confirmation-state inference now reuses the existing record values first, so the system does not accidentally push previously confirmed records back into `pending`.

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

- [x] Wrong-question detail should show original assets, OCR/split trail, chat summary, and archive source.
- [x] Teacher should be able to see why `needs_teacher_confirmation` was triggered.
- [x] Teacher should be able to fix question text, tags, and confirmation state from the archive detail.

#### E2. Teacher confirmation workflow

- [ ] Add explicit review queue/filter for records needing confirmation.
- [ ] Add confirmation actions: confirm, edit-then-confirm, return-for-rework.
- [ ] Persist confirmation outcome and reviewer identity.

Progress note (2026-06-03):
- The web smart-wrong-question page now exposes a first explicit teacher-confirmation queue slice for local records: list filtering by `待老师复核 / 已退回 / 已确认`, reviewer/outcome metadata in record detail, and concrete `编辑后确认 / 退回待补充` actions wired into the local review save path.
- `退回待补充` no longer stops at a status tag: returned `ai_chat` records can now reopen the AI reflection loop directly, and the follow-up archive pass will reset reviewer metadata and overwrite the same record so teacher review and student补充 stay on one chain.

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

- [ ] Promote the shared Track S schema into the PDF/practice rendering path:
  - `mistake_focus`
  - `review_goal`
  - `method_hint_lines[]`
  - `blank_review_blocks[]`
  - `teacher_feedback`
  - `confirmation_reasons[]`
- [ ] Stop passing two opaque writing prompts straight into layout.

Progress note (2026-06-03):
- The browser PDF renderer has started consuming `structured_content` directly for `方法提醒 / 挖空复盘 / 需老师确认`, while still falling back to the legacy dual-prompt fields for older records and partially migrated generation paths.

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

This is the practical execution order after the work already completed, reordered around the final product spine rather than around individual code surfaces:

1. **Keep `Track S` as the authority layer**
   - Continue to treat shared content schema, generation metadata, reviewer metadata, and mastery metadata as the common contract across AI chat, teacher review, practice PDF, weekly follow-up, and any future workbench.
   - Why first: the final product only stays coherent if every later surface keeps writing back onto the same record spine instead of inventing one-off payloads.

2. **Finish the same-record lifecycle before adding more入口**
   - Prioritize `E2 + B3`: teacher confirmation, return-for-rework, confirmed-to-practice, mastery follow-up, and durable mastery outcomes all need to stay on one wrong-question record.
   - Why second: the target product is not “many separate tools around a题”, but one continuous chain: `AI chat -> archive -> review -> re-practice -> mastery follow-up -> later grading`.

3. **Broaden those continuity actions across user-facing surfaces**
   - Reuse the same rework/follow-up actions from notebook modal, archive detail, weekly follow-up cards, and later student-facing entrypoints.
   - Why third: once the continuity semantics are stable, multiplying入口 is cheap and does not fragment state.

4. **F1 + F2 + F3**
   - Rebuild the practice/PDF artifact on top of the shared schema and quality rules.
   - Why fourth: the current output still does not fully match the review document’s minimum four-area teaching structure, but it is safer to rebuild it after the record spine is stable.

5. **Transplant low-coupling `error_correction` backend capability, not the whole architecture**
   - Land `prepare_input()`, `simplify_ocr_results()`, overlap split batching, and structured fallback logic onto the generic ingestion backbone.
   - Why fifth: these are high-value recognition/workbench blocks, but `error_correction` should act as an adapter layer, not become the system’s source of truth too early.

6. **C3 + D1-D2**
   - Add the React workbench UI and optional adapters only after the shared runtime is stable enough that the workbench does not fork behavior from the AI-chat path.

7. **G1-G3**
   - Turn the whole system into a measurable long-term loop with evals, labels, and lightweight classifiers.

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

The latest completed slices already cover the generic ingestion base, local AI-chat archive loop, teacher review queue starter flow, structured PDF sections, generation metadata, returned-record rework, “confirmed AI archive -> existing practice-sheet pipeline”, and a first evidence-based mastery spine.

The current round now also writes explicit mastery-followup outcome signals back onto the same record via the existing mastery metadata spine, using the smallest durable shape needed for later automation:

- `followup_count`
- `latest_followup_outcome`
- `latest_followup_completed_at`
- `latest_followup_summary`

The current round now also reuses that same mastery-followup continuity from weekly follow-up cards, instead of leaving it only inside the notebook modal:

- weekly follow-up cards can now open the matching `ai_chat` archive directly into the existing mastery-followup flow
- the card action still writes into the same `mastery_tracking / mastery_assessment / generation_metadata` chain rather than creating a side channel
- the frontend now guards the context-switch timing so “jump from weekly card -> open notebook record -> start mastery follow-up” does not get reset by the notebook chat auto-restore effect

The current round now also reuses the same continuity from the archived AI-chat panel itself:

- an archived `ai_chat` session that already has a confirmed record and at least one completed re-practice can now start mastery follow-up directly from the chat archive header
- this keeps “upload -> guided reflection -> archive -> later re-practice -> follow-up” navigable from the original chat surface, not only from notebook detail or weekly cards

The current round now also reuses the same continuity from the student notebook directory itself:

- an eligible `ai_chat` record can now start mastery follow-up directly from the left-side notebook directory row, instead of forcing the teacher to first select the row and then hunt for the action again in the detail pane
- this keeps the most common “scan student mistakes -> pick one candidate -> continue follow-up” workflow on the same single-record continuity chain, even before the detail pane fully becomes the operator’s focus

The next highest-value task is now **the next continuity reuse slice after weekly follow-up reuse**:

- extend the same mastery-followup entrypoint to the remaining archive-detail and summary surfaces that still stop at “open record”
- keep those alternate entrypoints on the same single-record continuity chain instead of inventing a second mastery workflow
- only after that, decide whether any extra mastery-specific structured card or classifier layer is actually needed

This keeps the implementation path aligned with the final desired product:

`AI chat upload -> guided reflection -> archive -> teacher confirmation -> later re-practice -> mastery follow-up outcome -> later grading / relapse detection`
