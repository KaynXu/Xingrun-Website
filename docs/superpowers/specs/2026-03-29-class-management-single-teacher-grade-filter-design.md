# Class Management Single-Teacher Grade Filter Design

## Goal

Refine the `班级管理` tab again so it matches the confirmed business rule that one class maps to one teacher, and so class cards are easier to browse by filtering them at the grade level.

## Why This Change

The current card-based redesign still exposes a multi-teacher assignment model inside each class card. That conflicts with the clarified rule that the class teacher and the assigned teacher account should represent the same person. The current card list also remains long when an organization has many classes, because all grades are mixed together in a single stream.

## Product Decision

### Single Teacher Per Class

Each class will bind to exactly one teacher account.

This means:
- `teacher_name` is no longer an independently edited free-text identity that can drift away from the selected teacher account.
- The selected teacher account becomes the single source of truth for who owns the class.
- The class card must not expose multi-select assignment checkboxes anymore.
- Reassigning a class to a new teacher replaces the old teacher binding instead of adding another teacher.

### Grade-Level Filtering

The class card area will provide a concrete grade filter above the list and only render classes belonging to the selected grade.

The filter options are:
- `全部`
- `一年级` through `六年级`
- `初一` through `初三`
- `高一` through `高三`

The list below the filter shows only classes that match the current selected grade. The summary near the filter should also reflect the visible result count so the top-level information matches what the user sees.

## Architecture

This remains a focused change inside the React workspace shell, with a small backend compatibility adjustment.

### Frontend

`ClassManagementPage` remains the primary implementation surface in `frontend/src/App.tsx`.

The page keeps the current single-expand card structure, but changes the internal card model in these ways:
- Replace the embedded multi-teacher assignment block with a single-teacher selector.
- Add a `selectedGradeFilter` state above the card list.
- Derive `filteredClasses` from the full class list and the selected grade filter.
- Show only `filteredClasses` in the card list.
- Show the bound teacher in the card summary instead of a teacher count.

### Backend

The backend should preserve the current API surface where practical, but the behavior must now enforce one teacher per class.

Recommended compatibility rule:
- Keep the existing `user_classes` table for now.
- When saving a teacher binding for a class, write the relationship so that only one `user_classes` row can exist for that class at the business-logic level.
- When reassigning, remove the previous teacher-class relation and insert the new one.
- Continue returning compatible class and user data to avoid unnecessary API churn during this iteration.

This avoids a schema migration in the same pass while still making the effective business model one-to-one.

## UX Design

### Page Header

The page header remains card-based and keeps the current workspace style, but its summary should reflect the filtered experience:
- total class count may still appear in the top summary area
- the card list section should show the visible result count for the current grade filter
- the active filter should be obvious without expanding any class

### Filter Bar

A grade filter row appears directly above the class cards.

Behavior:
- default selection is `全部`
- selecting a grade immediately filters the rendered class cards below
- when a grade has no classes, the list shows a grade-specific empty state
- filtering does not mutate data or collapse the page globally unless the currently expanded class is filtered out; if that happens, the expanded state should close cleanly

### Card Summary

Each collapsed class card shows:
- class name
- grade
- subject
- current teacher

It should no longer show teacher count because multi-teacher assignment is gone.

### Expanded Card

Each expanded class card contains two clear sections:

#### Basic Info
- class name
- subject
- grade

#### Teacher Binding
- current bound teacher
- a search input for teacher lookup
- a candidate teacher list
- single selection behavior only

The teacher picker should behave like a one-of-many selector rather than a checkbox matrix. Radio-style selection or a selectable list is acceptable as long as only one teacher can be active.

### New Class Card

The `新建班级` card keeps the same visual position and expand/collapse pattern as today, but it must also follow the single-teacher rule.

This means a new class cannot be considered complete without selecting one responsible teacher account.

## Data Flow

### Loading

The page continues loading:
- class list
- teacher-capable user list
- current class-teacher bindings

The frontend then derives:
- the current grade filter options
- the visible filtered class list
- the current single teacher bound to each class

### Saving

Saving a class should send:
- normalized class name
- subject
- grade
- selected teacher identity

`teacher_name` should be synchronized from the selected teacher account rather than manually drifting.

If backend compatibility still needs `teacher_email`, keep sending the empty-string compatibility payload as before.

### Rebinding Teacher

When the user selects a different teacher for an existing class:
- the old teacher-class relation is replaced
- the card summary updates to the new teacher
- no second teacher remains attached to the class

## Error Handling

### Filtering
- Invalid or empty filter selections fall back to `全部`.
- If a selected grade has no matching classes, show an empty-state message instead of a blank layout.

### Teacher Binding
- If no teacher accounts exist, show a clear empty state and prevent a misleading selection UI.
- If teacher reassignment fails, revert the optimistic UI back to the previous teacher binding.
- If a class save succeeds but teacher rebinding fails, the UI must clearly indicate that the class info saved but teacher assignment needs retry, or the flow should save atomically if the backend allows it.

### Expanded State
- If the currently expanded class disappears from the filtered view after the filter changes, collapse it rather than showing stale content.
- Existing async safety guards such as request-version protection and in-flight lockouts must remain intact.

## Testing Strategy

### Frontend Source-Level Tests

Update the current source-level regression tests to require:
- grade filter state and rendering logic
- filtered class list behavior
- single-teacher selector instead of multi-select teacher checkbox assignment
- removal of teacher-count summary copy
- card summary showing one current teacher

Primary files:
- `frontend/src/account-card.test.tsx`
- `frontend/src/workspace-navigation.test.ts`

### Backend Regression Tests

Add the minimum class-management backend coverage needed to lock the one-teacher rule:
- binding a teacher to a class leaves only one teacher relation for that class
- rebinding replaces the previous teacher instead of appending
- returned class-teacher data remains consistent with `teacher_name`

Primary file:
- `tests/test_account_flow.py`

### Final Verification

Before deployment, run:
- backend account/class regression tests
- focused frontend source-level tests
- `npm run lint`
- `npm run build`

## Scope Boundaries

Included in scope:
- single-teacher class ownership
- grade-level class filtering
- card summary and expanded-card UX updates
- minimal backend logic adjustments to enforce one teacher per class

Out of scope:
- redesigning account approval
- broader user-role model changes
- a full schema migration away from `user_classes`
- unrelated workspace refactors

## Rollout Plan

This should be implemented as a focused follow-up iteration on the current branch line.

Recommended sequence:
1. lock the new requirements with failing tests
2. update backend logic to enforce one teacher per class
3. update frontend card/filter interactions
4. run full regression and redeploy to the current server

## Acceptance Criteria

The feature is complete when all of the following are true:
- each class can only have one teacher account bound at a time
- the displayed `teacher_name` matches that selected teacher account
- the card list can be filtered by specific grade
- only classes from the selected grade are rendered
- the card summary shows one teacher, not multi-teacher counts
- focused frontend tests pass
- backend class-management regression tests pass
- lint and build pass
