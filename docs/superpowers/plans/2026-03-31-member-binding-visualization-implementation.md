# Member Binding Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show read-only mini-program teacher binding, responsible classes, and mapping health summaries per member inside the approval page.

**Architecture:** Add one read-only backend summary endpoint that aggregates canonical class ownership and wrong-question mapping health per user, then fetch and render that summary beside each member in the existing approval page. Keep role management unchanged and degrade gracefully if the summary request fails.

**Tech Stack:** Flask, SQLite helpers in `master_data.py` / `lesson_manager.py`, React + TypeScript source tests, Python `unittest`

---

### Task 1: Backend Summary Endpoint

**Files:**
- Modify: `master_data.py`
- Modify: `app.py`
- Test: `tests/test_account_flow.py`

- [ ] Write failing backend tests for `GET /api/admin/member-binding-summary`
- [ ] Run the targeted `unittest` cases and confirm they fail for missing endpoint or missing fields
- [ ] Implement aggregation helper in `master_data.py` and expose the staff-only Flask route in `app.py`
- [ ] Re-run targeted backend tests until they pass

### Task 2: Approval Page Summary Rendering

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] Write failing frontend source assertions for the new `教学绑定` block and summary fetch behavior
- [ ] Run the targeted frontend test and confirm it fails
- [ ] Implement summary loading and per-member `教学绑定` rendering in `ApprovalPage`
- [ ] Re-run the targeted frontend test until it passes

### Task 3: Verification And Wrap-Up

**Files:**
- Modify: `handoff.md`

- [ ] Run backend verification for the new endpoint and existing account-flow behavior
- [ ] Run frontend verification for the approval page source checks
- [ ] Update `handoff.md` with what shipped and the proof commands
- [ ] Commit the repo changes with a focused message