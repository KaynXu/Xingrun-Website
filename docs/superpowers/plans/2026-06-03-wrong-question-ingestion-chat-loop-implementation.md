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
