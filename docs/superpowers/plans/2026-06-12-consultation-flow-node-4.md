# Consultation Flow Node 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the ordinary consultation node dialog for the current process stages without adding enter-class or Over dialogs.

**Architecture:** Keep the five current process nodes unchanged. Add a reusable ordinary-node dialog component inside `App.tsx`, plus small field-mapping helpers that read/write existing consultation fields. The dialog is used by both the consultation list cards and the edit modal.

**Tech Stack:** React, TypeScript, Node source tests, Vite.

---

### Task 1: Ordinary Node Dialog

**Files:**
- Create: `frontend/src/consultation-flow-node-dialog.test.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `docs/superpowers/specs/2026-06-11-consultation-flow-redesign-spec.md`

- [x] **Step 1: Write the failing test**

Add source tests that assert:
- `ConsultationFlowNodeDialog` exists.
- It renders stage title, student summary, teacher selector status card, note field, save/cancel buttons.
- It uses `CheckCircle2` for the saved/selected teacher card state.
- There are helpers for `getConsultationFlowNodeDraft`, `applyConsultationFlowNodeDraft`, and `clearConsultationFlowNodeContent`.
- Save uses `completeConsultationFlowStage` for ordinary save and `setConsultationFlowCurrentStage` for current-stage save.
- Clicking an already lit process node cancels through `clearConsultationFlowNodeContent`.
- Inline cards open the node dialog instead of directly saving unlit nodes.
- No enter-class or Over dialog state is introduced.

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx tsx --test src/consultation-flow-node-dialog.test.ts`

Expected: FAIL because the ordinary node dialog does not exist yet.

- [x] **Step 3: Implement minimal dialog and field mapping**

Update `App.tsx` to:
- Add `ConsultationFlowNodeDialog`.
- Add stage-to-field helpers for the current five process stages.
- Open the dialog for unlit left-click/tap and right-click/long-press.
- Cancel lit nodes directly and clear that stage's mapped fields.
- Save dialog fields into the mapped consultation fields, then light/set-current via pure functions.

- [x] **Step 4: Run focused tests**

Run:
- `cd frontend && npx tsx --test src/consultation-flow-node-dialog.test.ts`
- `cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts`
- `cd frontend && npx tsx --test src/domain/consultationFlow.test.ts`

Expected: PASS.

- [x] **Step 5: Build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [x] **Step 6: Update progress**

Mark Node 4 completed in the spec progress log.
