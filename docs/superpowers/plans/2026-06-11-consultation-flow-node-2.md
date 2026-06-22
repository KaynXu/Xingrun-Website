# Consultation Flow Node 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build tested pure functions for consultation flow lights before reconnecting UI events.

**Architecture:** Put all flow state transition rules in `frontend/src/domain/consultationFlow.ts`. Keep UI-specific code in `App.tsx` unchanged during this node so later nodes can adopt the pure functions safely.

**Tech Stack:** TypeScript, Node test runner, `tsx`.

---

### Task 1: Flow Pure Function Tests

**Files:**
- Create: `frontend/src/domain/consultationFlow.test.ts`
- Create: `frontend/src/domain/consultationFlow.ts`
- Modify: `docs/superpowers/specs/2026-06-11-consultation-flow-redesign-spec.md`

- [x] **Step 1: Write the failing test**

Add tests for:
- Nonlinear A/B/E completion renders A/B green, C/D white, E blue.
- Canceling green deletes the stage content.
- Canceling blue deletes the stage content and moves blue to the previous completed stage.
- Canceling failed Over clears red Over and returns to previous stage.
- Canceling successful Over clears success Over without touching linked business record ids.
- Choosing an earlier current stage deletes later completed stage content after confirmation.

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx tsx --test src/domain/consultationFlow.test.ts`

Expected: FAIL because `consultationFlow.ts` does not exist yet.

- [x] **Step 3: Write minimal implementation**

Implement exported stage constants, state types, `calculateConsultationFlowLights`, `completeConsultationStage`, `cancelConsultationStage`, `setConsultationCurrentStage`, `cancelConsultationOver`, and `completeConsultationOver`.

- [x] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx tsx --test src/domain/consultationFlow.test.ts`

Expected: PASS.

- [x] **Step 5: Build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [x] **Step 6: Update progress**

Mark Node 1 completed and Node 2 completed in the spec progress log.
