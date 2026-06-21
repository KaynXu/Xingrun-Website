# Consultation Flow Finish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the consultation flow node rules, teacher markers, card synchronization, enter-class filtering, and transfer display without changing the page filter structure.

**Architecture:** Keep the existing consultation stages and current modal style. Put deterministic flow-state behavior in domain helpers and keep React components as render/wiring layers. Backend assignment visibility stays in `lesson_manager.py`; frontend renders the returned transfer metadata.

**Tech Stack:** React, TypeScript source tests with `tsx --test`, Python `unittest`, Flask backend helpers.

---

### Task 1: Flow Light And Cancel Rules

**Files:**
- Modify: `frontend/src/domain/consultationFlow.test.ts`
- Modify: `frontend/src/domain/consultationFlow.ts`
- Modify: `frontend/src/App.tsx`

- [x] **Step 1: Write failing tests**

Add focused tests proving:
- Completing A and E shows A green, B/C/D white, E blue.
- Canceling a lit green stage removes its fields and light.
- Canceling the blue stage removes its fields and moves blue to the previous completed stage.
- Successful Over does not auto-complete skipped process stages.

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx tsx --test src/domain/consultationFlow.test.ts src/consultation-flow-node-dialog.test.ts`

- [x] **Step 3: Implement minimal corrections**

Update the pure helpers and flow click wiring so saved stages alone drive green lights, current stage is the last saved visible stage, and canceling a lit node clears mapped content.

- [x] **Step 4: Run focused tests**

Run: `cd frontend && npx tsx --test src/domain/consultationFlow.test.ts src/consultation-flow-node-dialog.test.ts src/consultation-flow-wiring.test.ts`

### Task 2: Teacher Marker And Card Synchronization

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/consultation-flow-node-dialog.test.ts`

- [x] **Step 1: Write failing tests**

Add tests proving:
- Flow lamps render teacher name initials, not stage initials, for green and blue process nodes.
- The customer-service stage falls back to the default teacher 雷老师 when saved without an explicit teacher.
- View/edit summaries render saved stage teacher status cards such as `测试教师：雷老师 ✓`.

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx tsx --test src/consultation-flow-node-dialog.test.ts`

- [x] **Step 3: Implement minimal corrections**

Update marker construction and compact status rendering. Keep transferred markers as light dashed circles.

- [x] **Step 4: Run focused tests**

Run: `cd frontend && npx tsx --test src/consultation-flow-node-dialog.test.ts`

### Task 3: Enter-Class Filtering And Quick Class Persistence

**Files:**
- Modify: `frontend/src/domain/consultationEnterClass.test.ts`
- Modify: `frontend/src/domain/consultationEnterClass.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `tests/test_consultation_flow.py`
- Modify: `lesson_manager.py`

- [x] **Step 1: Write failing tests**

Add tests proving:
- Existing-class filters preselect consultation subject/grade as recommendations and still allow changes.
- Quick create persists a real class discoverable by class-management data.
- Successful enter-class creates success Over without auto-completing skipped stages.

- [x] **Step 2: Run tests to verify failure**

Run frontend enter-class tests and focused backend enter-class tests.

- [x] **Step 3: Implement minimal corrections**

Update filter defaults/backfill payload and backend enter-class completion behavior.

- [x] **Step 4: Run focused tests**

Run frontend enter-class tests and focused backend consultation flow tests.

### Task 4: Transfer Display And Edit Scope Smoke Check

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `tests/test_consultation_flow.py`

- [x] **Step 1: Write failing tests**

Add or extend tests proving teachers see self-created plus transferred consultations, transferred cards show marker/current responsibility/note, and prior assignees become read-only after same-stage reassignment.

- [x] **Step 2: Run tests to verify failure if behavior is missing**

Run focused backend transfer tests.

- [x] **Step 3: Implement minimal corrections**

Adjust frontend display classes and backend annotation only where tests show gaps.

- [x] **Step 4: Run focused and build verification**

Run focused TypeScript tests, focused Python tests, then `cd frontend && npm run build`.
