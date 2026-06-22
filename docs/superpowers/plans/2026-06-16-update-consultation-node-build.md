# 更新咨询节点构建 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize the local consultation flow preview for 更新咨询节点构建 by making the flow graph, card display, edit modal, enter-class result, Over behavior, and transfer scope follow one clear rule set.

**Architecture:** Treat `frontend/src/domain/consultationFlow.ts` as the source of truth for lights and transitions. Keep UI components thin: `ConsultationFlowBar` renders state, `ConsultationFlowNodeDialog` edits stage content, `ConsultationEnterClassDialog` handles class conversion, and page/modal wrappers decide whether changes are saved immediately or held in the form.

**Tech Stack:** React, TypeScript, Vite, Node `tsx --test`, Playwright with local Chrome for visual verification.

---

### Task 1: Freeze The Current Rule Table

**Files:**
- Modify: `docs/superpowers/specs/2026-06-11-consultation-flow-redesign-spec.md`
- Modify: `docs/superpowers/plans/2026-06-16-update-consultation-node-build.md`

- [x] **Step 1: Confirm the single rule table**

Use these rules as the baseline:

```text
Left click / tap on white stage: open dialog, save lights the stage.
Left click / tap on green or blue stage: cancel that stage, delete that stage content.
Right click / long press on process stage: open dialog, save makes it current and deletes later stage content.
Green: saved completed stage before current.
Blue: current stage, normally the last completed visible stage.
White: not saved, or hidden because it is after current.
Red: failed Over.
Successful Over: blue Over, skipped process stages are not auto-completed.
```

- [x] **Step 2: Mark deferred work**

Keep these out of this stabilization pass:

```text
Real push notifications.
Large redesign of view/edit modal layout.
Full historical assignment timeline.
Deleting real created classes/student profiles when canceling Over.
```

### Task 2: Make Page And Modal Save Semantics Explicit

**Files:**
- Modify: `frontend/src/features/consultation/ConsultationPage.tsx`
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx`
- Test: `frontend/src/consultation-flow-wiring.test.ts`

- [x] **Step 1: Write failing source tests**

Add assertions that card flow actions save immediately through `saveInlineConsultationUpdate`, while modal flow actions only mutate `form` until the modal Save button submits.

- [x] **Step 2: Keep the behavior but make UI copy clear**

In the card flow, keep immediate save. In the modal, keep draft save. Add concise local labels or helper copy only where users might confuse the two.

- [x] **Step 3: Verify**

Run:

```bash
cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts
cd frontend && npm run build
```

Expected: tests pass and build exits 0.

### Task 3: Normalize Flow Bar Rendering

**Files:**
- Modify: `frontend/src/features/consultation/consultationShared.tsx`
- Modify: `frontend/src/features/consultation/ConsultationPage.tsx`
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx`
- Modify: `frontend/src/features/consultation/ConsultationMeetingWorkbench.tsx`
- Test: `frontend/src/consultation-flow-wiring.test.ts`

- [x] **Step 1: Lock rendering rules**

Test that:

```text
Process lamp center text uses saved teacher initial when available.
Empty saved teacher means empty lamp text, not stage name.
Stage label remains below the lamp.
Blue connector only appears from a completed left stage into the current stage.
No process stage after blue appears green.
```

- [x] **Step 2: Keep one shared FlowBar**

All consultation surfaces use `ConsultationFlowBar`. Do not create separate flow implementations for cards, modal, and workbench.

- [x] **Step 3: Verify with browser**

Open local consultation page and inspect the first visible cards:

```bash
cd frontend && node /tmp/check-consultation-flow.js
```

Expected: page loads, no console errors, lamp centers show teacher initials or blank, not process names.

### Task 4: Restore Enter-Class As A Dedicated Path

**Files:**
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx`
- Prefer Create: `frontend/src/features/consultation/ConsultationEnterClassDialog.tsx`
- Test: `frontend/src/consultation-enter-class-dialog.test.ts`

- [x] **Step 1: Keep three-card UI**

Use exactly these choices:

```text
已有班级
快速建班
转化待进班
```

- [x] **Step 2: Keep filter logic flexible**

Subject and grade are recommendations, not locks:

```text
If consultation subject exists, preselect it.
If user changes subject in enter-class filter, allow it.
If consultation subject is blank, selected class/create-class subject can backfill it.
Grade preselects when useful but remains editable.
```

- [x] **Step 3: Verify**

Run:

```bash
cd frontend && npx tsx --test src/consultation-enter-class-dialog.test.ts
cd frontend && npm run build
```

Expected: enter-class test passes and build exits 0.

### Task 5: Reconcile Over With Enter-Class

**Files:**
- Modify: `frontend/src/domain/consultationFlow.ts`
- Modify: `frontend/src/domain/consultationFlow.test.ts`
- Modify: `frontend/src/features/consultation/consultationShared.tsx`
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx`

- [x] **Step 1: Lock pure Over rules**

Tests must cover:

```text
Successful Over is blue.
Failed Over is red.
Successful Over does not auto-complete skipped process stages.
Canceling Over returns to the previous completed/current stage.
Canceling successful Over does not delete created class or student profile records.
```

- [x] **Step 2: Wire UI through the pure rules**

Manual Over asks success/failure. Success opens enter-class first. Failure writes failed Over. Existing successful enter-class creates successful Over.

- [x] **Step 3: Verify**

Run:

```bash
cd frontend && npx tsx --test src/domain/consultationFlow.test.ts src/consultation-flow-wiring.test.ts
cd frontend && npm run build
```

Expected: pure flow tests and wiring tests pass.

### Task 6: Tighten Transfer Scope Without Redesigning Cards

**Files:**
- Modify: `frontend/src/features/consultation/ConsultationPage.tsx`
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx`
- Modify: `frontend/src/features/consultation/consultationTypes.ts`
- Test: `frontend/src/consultation-transfer-scope.test.ts`

- [x] **Step 1: Lock visibility rules**

Teacher accounts see:

```text
Consultations they created.
Consultations transferred to them.
```

Transferred cards show:

```text
咨询转接
Current responsibility, such as 试听教师：何老师
Assignment note when present
Different but subtle card background
```

- [x] **Step 2: Lock edit rules**

Teachers on transferred consultations can edit only from `assigned_stage` onward. Earlier stages must be visually non-editable, not merely rejected later.

- [x] **Step 3: Verify**

Run:

```bash
cd frontend && npx tsx --test src/consultation-transfer-scope.test.ts
python3 -m unittest tests.test_consultation_flow -v
cd frontend && npm run build
```

Expected: frontend transfer tests, backend consultation flow tests, and build pass.

### Task 7: Final Local Preview Audit

**Files:**
- No required source changes unless audit finds a bug.

- [x] **Step 1: Start services**

Backend:

```bash
XR_OPEN_BROWSER=0 python3 app.py
```

Frontend:

```bash
cd frontend && npm run dev -- --host 127.0.0.1 --port 3000
```

- [x] **Step 2: Audit three user states**

Use browser verification for:

```text
Admin/owner consultation page.
Teacher self-created consultation.
Teacher transferred consultation.
```

- [x] **Step 3: Check the five main flows**

```text
Left click/tap white stage -> save -> lamp lights.
Left click/tap lit stage -> content deleted -> lamp turns white.
Right click/long press earlier stage -> save -> later stages turn white.
Enter existing class -> successful Over blue without completing skipped stages.
Transferred teacher cannot edit earlier assigned stages.
```

- [ ] **Step 4: Final commands**

Run:

```bash
cd frontend && npx tsx --test src/domain/consultationFlow.test.ts src/consultation-flow-wiring.test.ts src/consultation-flow-node-dialog.test.ts src/consultation-enter-class-dialog.test.ts src/consultation-transfer-scope.test.ts
python3 -m unittest tests.test_consultation_flow -v
cd frontend && npm run build
```

Expected: all selected tests pass and build exits 0.

---

## Suggested Execution Order

1. Task 1: lock rules.
2. Task 2: clarify save semantics.
3. Task 3: normalize FlowBar rendering.
4. Task 5: reconcile Over.
5. Task 4: enter-class cleanup.
6. Task 6: transfer scope.
7. Task 7: local preview audit.

This order stabilizes the foundation before touching the more expensive UI flows.
