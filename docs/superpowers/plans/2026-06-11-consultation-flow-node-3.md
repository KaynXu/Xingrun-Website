# Consultation Flow Node 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire consultation flow graph left-click/tap and right-click/long-press into the tested flow pure functions without restoring complex dialogs.

**Architecture:** Keep `ConsultationFlowBar` visual markup mostly unchanged. Add explicit current-stage gesture props, convert `ConsultationFormValues` to the domain flow state for temporary transitions, then write the updated `flow_stage` and `completed_stages` back to existing consultation records.

**Tech Stack:** React, TypeScript, Node source tests, Vite.

---

### Task 1: Source Test For Gesture Wiring

**Files:**
- Create: `frontend/src/consultation-flow-wiring.test.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `docs/superpowers/specs/2026-06-11-consultation-flow-redesign-spec.md`

- [x] **Step 1: Write the failing test**

Add source-level tests that assert:
- `App.tsx` imports the pure consultation flow helpers.
- `ConsultationFlowBar` exposes `onStageContextMenu` and `onStageLongPress`.
- Node buttons wire `onContextMenu` to the current-stage handler.
- Long press uses a timer and calls the current-stage handler.
- Inline card flow uses separate left-click and current-stage handlers.
- The complex dialog state names remain absent.

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts`

Expected: FAIL because the right-click/long-press props do not exist yet.

- [x] **Step 3: Implement minimal wiring**

Update `App.tsx` to:
- import domain helpers from `./domain/consultationFlow`.
- add temporary `applyConsultationFlowStateToValues`, `toggleConsultationFlowStageWithRules`, and `setConsultationFlowCurrentStageWithRules`.
- add `onStageContextMenu` and `onStageLongPress` props to `ConsultationFlowBar`.
- wire right-click and long-press on process nodes.
- use these new handlers in list cards and edit modal.

- [x] **Step 4: Run focused tests**

Run:
- `cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts`
- `cd frontend && npx tsx --test src/domain/consultationFlow.test.ts`

Expected: PASS.

- [x] **Step 5: Build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [x] **Step 6: Update progress**

Mark Node 3 completed in the spec progress log.
