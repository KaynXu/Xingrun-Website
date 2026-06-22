# Student Center Permission Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make student center permissions match the agreed role model: organization roles manage everything, member teachers get read-only access to their assigned class/student view.

**Architecture:** Keep backend authorization as source of truth and make the frontend load only data each role may read. Reuse existing student-center rule files and add a small shared class ordering helper so class, overview, and student displays stay consistent.

**Tech Stack:** Flask, SQLite, React, TypeScript, node:test, Python unittest.

---

### Task 1: Frontend Permission And Load Rules

**Files:**
- Modify: `frontend/src/features/student-center/permissions.ts`
- Modify: `frontend/src/features/student-center/loadPageRules.ts`
- Test: `frontend/src/features/student-center/permissions.test.ts`
- Test: `frontend/src/features/student-center/loadPageRules.test.ts`

- [ ] Write failing tests that admin uses organization scope and member has read-only, non-staff load behavior.
- [ ] Run `frontend/node_modules/.bin/tsx --test frontend/src/features/student-center/permissions.test.ts frontend/src/features/student-center/loadPageRules.test.ts` and confirm the new tests fail.
- [ ] Update permission output and student-center load arguments so `member` skips `/api/students`.
- [ ] Run the same frontend tests and confirm they pass.

### Task 2: Member Overview Labels And Read-Only Controls

**Files:**
- Modify: `frontend/src/features/student-center/CampusOverview.tsx`
- Modify: `frontend/src/features/student-center/ClassManagementTab.tsx`
- Modify: `frontend/src/features/student-center/StudentCenterPage.tsx`
- Test: `frontend/src/features/student-center/StudentCenterPage.structure.test.ts`

- [ ] Write failing structure tests for `member` seeing `教师总览` and `学生人数`, with no class/student edit affordances.
- [ ] Run `frontend/node_modules/.bin/tsx --test frontend/src/features/student-center/StudentCenterPage.structure.test.ts` and confirm failure.
- [ ] Pass role-aware labels into `CampusOverview` and use view-only class card copy/buttons for members.
- [ ] Run the structure test and confirm it passes.

### Task 3: Class Ordering

**Files:**
- Modify: `frontend/src/features/student-center/classFilterRules.ts`
- Test: `frontend/src/features/student-center/classFilterRules.test.ts`

- [ ] Write a failing test that small classes sort before group classes and each type sorts low grade to high grade.
- [ ] Run `frontend/node_modules/.bin/tsx --test frontend/src/features/student-center/classFilterRules.test.ts` and confirm failure.
- [ ] Update class sorting to rank `1v1`/small-class types before `group`, then grade, then existing name fallback.
- [ ] Run the class filter test and confirm it passes.

### Task 4: Backend Member Read-Only Contract

**Files:**
- Modify: `app.py`
- Test: `tests/test_account_flow.py`

- [ ] Add backend tests proving a member can list assigned classes and class students, cannot list all `/api/students`, and cannot mutate class/student center resources.
- [ ] Run `.venv/bin/python -m unittest tests.test_account_flow -v` and confirm the new assertion fails where current behavior is wrong.
- [ ] Keep `/api/students` staff-only and rely on class-scoped student reads for members; ensure mutating endpoints already return or are adjusted to return `403` for members.
- [ ] Run targeted backend tests and confirm they pass.

### Task 5: Verification And Commit

**Files:**
- Modify: `handoff.md`

- [ ] Run the focused frontend tests for permissions, load rules, structure, and class filters.
- [ ] Run the focused backend account-flow tests.
- [ ] Run `git diff --check`.
- [ ] Update `handoff.md` with the completed permission alignment and remaining deployment note.
- [ ] Commit the spec update, plan, code, tests, and handoff.
