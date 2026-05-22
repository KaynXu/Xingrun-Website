# Consultation Meeting Workbench V1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build V1.0 of a face-to-face consultation workbench where owners can review all consultations in a temporary workspace and commit changes only at final save.

**Architecture:** Add a frontend-only workbench route opened in a new window via `?consultationMeeting=1`. It reuses existing consultation APIs and `ConsultationModal`, keeps edits in local draft state, moves edited records from pending to processed, and only writes to the backend on final save.

**Tech Stack:** React, Vite, existing Flask consultation APIs.

---

### Task 1: Workbench Entry And Route

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [x] Replace the owner/super-owner refresh button with a meeting workbench button.
- [x] Keep normal refresh visible for admins and members.
- [x] Add `?consultationMeeting=1` route handling after auth.

### Task 2: Draft Workbench

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [x] Load all consultation records into the workbench.
- [x] Add teacher filtering.
- [x] Split records into pending and processed columns.
- [x] Save modal edits to local draft state first.
- [x] Move edited cards to processed state.
- [x] Split processed cards into `待咨询` and `已结束`.

### Task 3: Final Save And Close Guard

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [x] Final save writes processed drafts through existing `PUT /api/consultations/:id`.
- [x] Add `beforeunload` guard when there are uncommitted processed drafts.
- [x] Add explicit close button that confirms before closing when drafts are uncommitted.

### Task 4: Verification

**Files:**
- Modify: `handoff.md`

- [x] Run frontend source tests.
- [x] Run frontend production build.
- [x] Run backend consultation tests.
- [x] Run `git diff --check`.
- [x] Open local preview and log in with default account.
