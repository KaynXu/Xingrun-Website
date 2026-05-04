# Practice-Based Weekly Wrong Question Followup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the web-only weekly followup assistant so it follows teacher-generated weekly wrong-question practice sheets, can ask AI to fill missing sheets, and downloads weekly practice-sheet PDF bundles.

**Architecture:** Keep the existing `/api/wrong-question-followups/weekly` surface for the frontend, but change its data source from weekly `wrong_question_submissions` rows to weekly `wrong_question_practice_sheets`. Add small data helpers in `lesson_manager.py` to summarize sheet status and candidate questions, then keep Flask as the orchestration layer for access control, async sheet creation, message generation, and zip downloads. The frontend keeps the current Smart Wrong Questions page, but the weekly section becomes "每周练习跟进" with sheet states instead of raw wrongbook states.

**Tech Stack:** Flask + SQLite in `lesson_manager.py`, existing async practice-sheet worker in `app.py`, existing AI prompt helpers in `ai_processor.py`, React/Vite TypeScript frontend, Python unittest/pytest and Node `tsx --test`.

---

### Task 1: Store Practice Sheet Source on Followup Messages

**Files:**
- Modify: `lesson_manager.py`
- Test: `tests/test_weekly_wrong_question_followups.py`

- [ ] **Step 1: Write the failing test**

Add a test that calls `upsert_weekly_wrong_question_followup_message(..., source_sheet_id=123)` and asserts `get_weekly_wrong_question_followup_message()` returns `source_sheet_id == 123` while keeping old `source_record_ids` compatible.

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/xiaodi/Desktop/xingrun.web/.venv/bin/python -m pytest tests/test_weekly_wrong_question_followups.py -q`

Expected: fail because `source_sheet_id` is not accepted or serialized.

- [ ] **Step 3: Write minimal implementation**

Add `source_sheet_id INTEGER` to `weekly_wrong_question_followup_messages` via `_ensure_column`, include it in table creation, serializer, and upsert parameters. Preserve existing `source_record_ids_json`.

- [ ] **Step 4: Run tests and commit**

```bash
/Users/xiaodi/Desktop/xingrun.web/.venv/bin/python -m pytest tests/test_weekly_wrong_question_followups.py -q
git add lesson_manager.py tests/test_weekly_wrong_question_followups.py
git commit -m "feat: link weekly followup messages to practice sheets"
```

### Task 2: Summarize Weekly Practice Followups

**Files:**
- Modify: `lesson_manager.py`
- Test: `tests/test_weekly_wrong_question_followups.py`

- [ ] **Step 1: Write failing query tests**

Add tests proving `list_weekly_wrong_question_followup_students()` returns ready weekly practice sheets as `has_practice_sheet`, students with candidates as `needs_practice_sheet`, and excludes old questions beyond six months.

- [ ] **Step 2: Run tests to verify failure**

Run: `/Users/xiaodi/Desktop/xingrun.web/.venv/bin/python -m pytest tests/test_weekly_wrong_question_followups.py -q`

- [ ] **Step 3: Implement practice-sheet first query**

Change `list_weekly_wrong_question_followup_students()` to summarize weekly `wrong_question_practice_sheets`, active six-month candidate questions, mastered recurrence, recommended category, and recommendation reason.

- [ ] **Step 4: Verify and commit**

```bash
/Users/xiaodi/Desktop/xingrun.web/.venv/bin/python -m pytest tests/test_weekly_wrong_question_followups.py -q
git add lesson_manager.py tests/test_weekly_wrong_question_followups.py
git commit -m "feat: list practice-based weekly followups"
```

### Task 3: Generate Missing Practice Sheets

**Files:**
- Modify: `app.py`
- Modify: `lesson_manager.py`
- Test: `tests/test_weekly_wrong_question_followups.py`

- [ ] **Step 1: Write failing API tests**

Add tests for single and batch `POST /api/wrong-question-followups/weekly/practice-sheets` creation, ensuring only `needs_practice_sheet` students receive pending sheets.

- [ ] **Step 2: Run tests to verify failure**

Run: `/Users/xiaodi/Desktop/xingrun.web/.venv/bin/python -m pytest tests/test_weekly_wrong_question_followups.py -q`

- [ ] **Step 3: Implement endpoints**

Add Flask routes that reuse `create_pending_wrong_question_practice_sheet()` and `_start_wrong_question_practice_generation_thread()`.

- [ ] **Step 4: Verify and commit**

```bash
/Users/xiaodi/Desktop/xingrun.web/.venv/bin/python -m pytest tests/test_weekly_wrong_question_followups.py -q
git add app.py lesson_manager.py tests/test_weekly_wrong_question_followups.py
git commit -m "feat: generate weekly practice followup sheets"
```

### Task 4: Use Practice Sheets for Messages and Zip Downloads

**Files:**
- Modify: `app.py`
- Modify: `ai_processor.py`
- Test: `tests/test_weekly_wrong_question_followups.py`

- [ ] **Step 1: Write failing tests**

Add tests proving message generation requires a weekly practice sheet, caches `source_sheet_id`, passes practice sheet summaries to AI, and zips ready practice sheet PDFs as `学生名-错题练习.pdf`.

- [ ] **Step 2: Run tests to verify failure**

Run: `/Users/xiaodi/Desktop/xingrun.web/.venv/bin/python -m pytest tests/test_weekly_wrong_question_followups.py -q`

- [ ] **Step 3: Implement**

Update `_weekly_followup_item_payload`, message route, AI prompt payload, and zip route to use weekly practice sheets.

- [ ] **Step 4: Verify and commit**

```bash
/Users/xiaodi/Desktop/xingrun.web/.venv/bin/python -m pytest tests/test_weekly_wrong_question_followups.py -q
git add app.py ai_processor.py tests/test_weekly_wrong_question_followups.py
git commit -m "feat: base weekly followup messages on practice sheets"
```

### Task 5: Upgrade Frontend Weekly Followup UI

**Files:**
- Modify: `frontend/src/smartWrongQuestions.ts`
- Modify: `frontend/src/SmartWrongQuestionsPage.tsx`
- Test: `frontend/src/smart-wrong-questions.test.ts`

- [ ] **Step 1: Write failing frontend tests**

Add tests proving the page labels the section "每周练习跟进", renders ready sheet cards, renders missing-sheet cards, and wires single/batch generation endpoints.

- [ ] **Step 2: Run tests to verify failure**

Run: `npm --prefix frontend test -- --test-name-pattern='weekly followup|每周练习跟进'`

- [ ] **Step 3: Implement frontend model and UI**

Extend normalizers/types for `status`, `practice_sheet`, `candidate_question_count`, `recommended_category`, and `recommendation_reason`. Add builders for single and batch practice-sheet endpoints. Update the weekly panel controls and handlers.

- [ ] **Step 4: Verify and commit**

```bash
npm --prefix frontend test -- --test-name-pattern='weekly followup|每周练习跟进'
npm --prefix frontend run build
git add frontend/src/smartWrongQuestions.ts frontend/src/SmartWrongQuestionsPage.tsx frontend/src/smart-wrong-questions.test.ts
git commit -m "feat: upgrade weekly practice followup UI"
```

### Task 6: Final Verification and Integration

**Files:**
- Modify: `handoff.md`

- [ ] **Step 1: Run full proof script**

Run a temporary proof script that executes frontend tests/build, backend weekly/practice/smart wrong question tests, bridge build, and `git diff --check`.

- [ ] **Step 2: Update handoff and commit**

Add the completed work and proof to `handoff.md`, then commit.

- [ ] **Step 3: Merge back to develop and clean worktree**

From the main workspace, check branch freshness, merge into `develop`, push `origin/develop`, remove the worktree, and delete the feature branch.

---

## Self-Review

- Spec coverage: practice sheet source, missing-sheet AI generation, practice zip, practice-based messaging, 30/60 day mastered recurrence, 6-month soft archive exclusion, and web-only frontend entry are covered.
- Placeholder scan: no TBD or deferred steps; each task includes test, implementation target, verification, and commit.
- Type consistency: backend and frontend use `source_sheet_id`, `practice_sheet`, `status`, `candidate_question_count`, `recommended_category`, and `recommendation_reason`.
