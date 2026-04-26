# RQ Wrong Question Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make parent wrong-question upload return quickly by enqueueing server-side recognition work through RQ + Redis.

**Architecture:** Flask creates durable upload task rows and enqueues task IDs into Redis through RQ. A separate Python worker function processes each task and updates SQLite task state. The mini program and bridge consume the new task response and can query task status.

**Tech Stack:** Flask, SQLite, Redis, RQ, Node/Express bridge, WeChat mini program JavaScript.

---

### Task 1: Backend Task Store

**Files:**
- Modify: `lesson_manager.py`
- Test: `tests/test_wechat_parent_upload_data.py`

- [ ] Add failing tests for creating, fetching, updating, and parent-scoped listing of `wechat_wrong_question_upload_tasks`.
- [ ] Run `python3 -m unittest tests.test_wechat_parent_upload_data.WeChatParentUploadDataTestCase` and confirm the new tests fail because the task APIs do not exist.
- [ ] Add table migration and focused helpers in `lesson_manager.py`.
- [ ] Re-run the same unittest and confirm it passes.

### Task 2: Backend Queue And Worker

**Files:**
- Create: `wrong_question_upload_queue.py`
- Create: `wrong_question_upload_worker.py`
- Modify: `requirements.txt`
- Test: `tests/test_wechat_parent_upload_api.py`

- [ ] Add failing tests that POST `/api/wechat/wrong-questions` creates a pending task, enqueues it, and returns `202`.
- [ ] Add failing tests that the worker marks success and failure task states.
- [ ] Run the targeted API tests and confirm the new tests fail.
- [ ] Implement the queue wrapper with `redis` and `rq`.
- [ ] Move the existing synchronous processing body into a worker function that reads task payloads from the database.
- [ ] Re-run targeted API tests and confirm they pass.

### Task 3: Bridge And Mini Program Contract

**Files:**
- Modify: `miniprogram/backend/src/website-client.ts`
- Modify: `miniprogram/backend/src/index.ts`
- Modify: `miniprogram/backend/src/parent-wechat-bridge.test.ts`
- Modify: `miniprogram/miniprogram/utils/parentApi.js`
- Modify: `miniprogram/miniprogram/utils/parentApi.test.js`
- Modify: `miniprogram/miniprogram/pages/parent-upload/index.js`

- [ ] Add failing bridge tests for forwarding `202` task responses and querying task status.
- [ ] Add failing mini program tests for parsing task responses.
- [ ] Run the targeted Node tests and confirm they fail.
- [ ] Update bridge and mini program helpers to use the task response.
- [ ] Re-run targeted Node tests and confirm they pass.

### Task 4: Proof, Handoff, Commit

**Files:**
- Modify: `handoff.md`
- Modify: `miniprogram/handoff.md`

- [ ] Run a temporary proof script that executes the targeted Python and Node tests and prints full output.
- [ ] Update handoff summaries with the new RQ/Redis deployment requirement and remaining smoke risks.
- [ ] Commit the implementation changes.
