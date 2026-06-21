# Consultation Modular Reconnect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconnect the previously agreed consultation flow behavior into the new modular `features/consultation` frontend after pulling remote changes.

**Architecture:** Keep backend consultation APIs and the remote modular file structure. Put deterministic state behavior in reusable helpers, then wire `ConsultationFlowBar`, `ConsultationPage`, and `ConsultationModal` to those helpers. Restore richer UI in small slices: flow lights first, node dialogs second, enter-class third, transfer display last.

**Tech Stack:** React, TypeScript, Vite, `tsx --test`, Python `unittest`.

---

### Task 1: Flow Light Interaction Reconnect

**Files:**
- Modify: `frontend/src/features/consultation/consultationShared.tsx`
- Modify: `frontend/src/features/consultation/ConsultationPage.tsx`
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx`
- Test: `frontend/src/consultation-flow-wiring.test.ts`
- Test: `frontend/src/domain/consultationFlow.test.ts`

- [ ] **Step 1: Write/repair failing frontend source tests**

Lock these requirements against the modular files:
- `ConsultationFlowBar` accepts `onStageContextMenu` and `onStageLongPress`.
- It does not expose or call `onStageDoubleClick`.
- Page and modal wire left click to edit/toggle behavior and right click/long press to current-stage behavior.
- The bar uses saved completed stages for green, current stage for blue, and keeps later stages white.

- [ ] **Step 2: Verify the tests fail for the current modular UI**

Run:

```bash
cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts src/domain/consultationFlow.test.ts
```

Expected: FAIL in the wiring tests because the current modular UI still uses double-click and the older inline stage helpers.

- [ ] **Step 3: Implement the minimal flow bar wiring**

Remove double-click stage setting. Add context-menu and long-press handlers to `ConsultationFlowBar`. Route modular page/modal stage changes through the existing tested flow helper rules or equivalent wrapper functions.

- [ ] **Step 4: Verify flow interaction tests and build**

Run:

```bash
cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts src/domain/consultationFlow.test.ts
cd frontend && npm run build
```

Expected: PASS.

### Task 2: Stage Node Dialog And Teacher Recommendation

**Files:**
- Modify: `frontend/src/features/consultation/ConsultationPage.tsx`
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx`
- Modify: `frontend/src/features/consultation/consultationShared.tsx`
- Modify: `frontend/src/domain/consultationTeacherSelection.ts`
- Test: `frontend/src/domain/consultationTeacherSelection.test.ts`
- Test: `frontend/src/consultation-flow-node-dialog.test.ts`

- [ ] **Step 1: Write/repair failing tests**

Lock:
- Clicking a white stage opens a node dialog and does not light the node until save.
- Clicking a lit green/blue stage cancels the light and deletes current stage content.
- Right-click/long-press save makes the stage current and deletes later flow content.
- Customer-service only offers the default Lei customer-service teacher.
- Communication/test/trial recommend the previous saved non-service teacher without lighting the node.

- [ ] **Step 2: Implement modular node dialog**

Create or restore a compact node dialog component using the previous status-card style: `xx教师：x老师 ✓` plus stage note. Keep UI close to the earlier version.

- [ ] **Step 3: Verify focused tests and build**

Run:

```bash
cd frontend && npx tsx --test src/domain/consultationTeacherSelection.test.ts src/consultation-flow-node-dialog.test.ts src/consultation-flow-wiring.test.ts
cd frontend && npm run build
```

Expected: PASS.

### Task 3: Enter-Class Three-Card Dialog Reconnect

**Files:**
- Modify: `frontend/src/features/consultation/ConsultationPage.tsx`
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx`
- Modify/Create: `frontend/src/features/consultation/ConsultationEnterClassDialog.tsx`
- Modify: `frontend/src/domain/consultationEnterClass.ts`
- Test: `frontend/src/consultation-enter-class-dialog.test.ts`
- Test: `frontend/src/domain/consultationEnterClass.test.ts`

- [ ] **Step 1: Write/repair failing tests**

Lock:
- Success result opens the enter-class dialog instead of saving direct success.
- Existing class uses filter logic 1 and a dropdown.
- Subject and grade are editable recommendations, not hard locks.
- Quick create uses student-center class naming and persists through `/api/consultations/:id/enter-class`.
- Converted pending saves success without class.

- [ ] **Step 2: Implement modular enter-class dialog**

Restore the three cards: `已有班级`, `快速建班`, `转化待进班`. Reuse current domain payload builders and class-filter rules. Keep the compact previous UI.

- [ ] **Step 3: Verify focused frontend and backend tests**

Run:

```bash
cd frontend && npx tsx --test src/consultation-enter-class-dialog.test.ts src/domain/consultationEnterClass.test.ts
python3 -m unittest tests.test_consultation_flow -v
cd frontend && npm run build
```

Expected: PASS.

### Task 4: Transfer Display And Edit Scope Reconnect

**Files:**
- Modify: `frontend/src/features/consultation/ConsultationPage.tsx`
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx`
- Modify: `frontend/src/features/consultation/consultationTypes.ts`
- Test: `frontend/src/consultation-flow-wiring.test.ts`
- Test: `tests/test_consultation_flow.py`

- [ ] **Step 1: Write/repair failing tests**

Lock:
- Teacher accounts see self-created and transferred consultations.
- Source filter toggles between all, self-created, and transferred.
- Transferred cards show `咨询转接`, current responsibility, and assignment note.
- Member edit scope starts at `assigned_stage`; prior stages are read-only.

- [ ] **Step 2: Implement frontend transfer rendering and locks**

Use backend-returned transfer metadata. Keep default list as all, with optional `自建咨询` and `转接咨询` toggles below the main status filters.

- [ ] **Step 3: Verify focused tests and build**

Run:

```bash
cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts
python3 -m unittest tests.test_consultation_flow -v
cd frontend && npm run build
```

Expected: PASS.

