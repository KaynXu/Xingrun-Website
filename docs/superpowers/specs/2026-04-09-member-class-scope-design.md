# Member Class Scope Design

## Goal

Make class-driven teacher workflows consistently respect the current member teacher's assigned classes. A `member` teacher should only see and operate on their own classes, and the smart wrong question workspace should pivot from a flat record list to a class-scoped student notebook workflow.

## Scope

This change applies only to users with role `member`.

Roles `owner`, `admin`, and `super_owner` keep their existing organization-level or global visibility.

The affected class-driven teacher workflows are:

- Single lesson review-plan generation
- Class feedback generation
- Smart wrong questions

The class management page is not being redesigned in this round. It remains the place where staff configure class ownership and roster data.

## Product Rules

### Member teacher visibility

A `member` teacher can only see classes returned from their assigned class scope.

A `member` teacher can only read, create, update, or trigger operations for data that belongs to those assigned classes.

If a class is no longer assigned to the teacher, the frontend must clear the stale local selection and the backend must still reject access.

### Single lesson review-plan generation

The page continues to use a class selector, but the selector for `member` users must only contain assigned classes.

Any generation or upload action must only submit against a class inside that scope.

Existing backend protections remain the source of truth, and tests must verify the rejection path as well as the allowed path.

### Class feedback generation

The page continues to use a class selector, but the selector for `member` users must only contain assigned classes.

All downstream task creation, draft saving, generation, confirmation, and roster loading must remain bound to the selected in-scope class.

The page copy should consistently frame the workflow as operating on the current class.

### Smart wrong questions

For `member` users, the smart wrong question workspace changes from a flat wrong-question record list to a class-scoped student notebook workflow.

The workflow is:

1. The teacher opens the page and works inside their assigned class scope.
2. The page shows the current class and the students under that class as cards.
3. Each student card summarizes that student's wrong-question notebook for the current class.
4. Opening a student card shows the wrong-question notebook for that student in that class.
5. Saving review content updates only that student's corresponding wrong-question records.

For staff roles, the existing global workspace stays intact in this round.

## UX Design

### Shared class-context behavior

For class-driven member pages, the frontend should present a consistent notion of "current class".

If there is exactly one accessible class, the page may auto-select it.

If there are multiple accessible classes, the page should require an explicit class choice and keep the selection local to the page.

If the current selection becomes invalid after reload, the page should reset the selection and show the page's standard empty guidance instead of continuing with stale data.

### Smart wrong question member workspace

The member workspace should show:

- A top summary that is computed from the currently selected class scope.
- A student card grid or list as the primary navigation surface.
- A notebook detail panel for the selected student.

Student cards should summarize at least:

- Student name
- Current class name
- Wrong-question count
- Pending review count
- Whether there are recent teacher follow-up notes

The detail panel should show the selected student's wrong-question records in that class, ordered by recency, with the existing review controls preserved as much as possible.

The page should not allow a member teacher to browse records from other classes through filter combinations.

## Data And API Design

### Existing class scope contract

The backend already has class-scope helpers such as `_get_accessible_class_or_error`, `_filter_classes_for_user`, and wrong-question record access checks.

This round should reuse those boundaries rather than introduce a second permission system.

### Smart wrong question aggregation

The preferred implementation is to keep the existing wrong-question list endpoint as the underlying source and aggregate member-visible records into student cards in the frontend when that is sufficient.

If the current payload is not sufficient to build stable student cards or notebook detail views, add a focused backend response enhancement instead of a broad new API surface.

Any member-visible wrong-question aggregation must be constrained by both:

- accessible class scope
- selected student within the selected class

For local WeChat wrong-question records, the same rules apply. A member teacher must not see a local record unless it belongs to their assigned class scope.

### Save behavior

Saving review content from the smart wrong question member workspace must only touch records already accessible under the selected class and selected student.

The backend remains responsible for rejecting out-of-scope record access, even if a crafted request bypasses the frontend.

## Implementation Boundaries

### Backend

Likely touch points:

- `app.py` for wrong-question access filtering and any class-scoped member response shaping
- Existing lesson and class-feedback routes only if a missing member-scope regression is found

Do not redesign staff-facing permissions or organization-wide list semantics.

### Frontend

Likely touch points:

- `frontend/src/SmartWrongQuestionsPage.tsx`
- `frontend/src/smartWrongQuestions.ts`
- `frontend/src/App.tsx`

Do not introduce a global cross-page class context store in this round.

Each page keeps its own selected class state, but member-facing behavior should be aligned.

## Testing Strategy

### Backend tests

Add or update tests to prove:

- a member teacher only receives assigned classes
- a member teacher cannot access out-of-scope smart wrong question records
- local WeChat wrong-question records still respect member class scope
- allowed in-scope records remain accessible

Primary test file:

- `tests/test_smart_wrong_questions_api.py`

Additional backend tests should only be added where a real gap is found.

### Frontend tests

Add or update tests to prove:

- member class selectors only expose assigned classes on class-driven pages
- stale selected class state is cleared when it falls out of scope
- the member smart wrong question page renders student cards instead of the flat record-first workflow
- selecting a student shows that student's notebook records for the current class
- saving review content stays bound to the selected student's records

Primary frontend test files:

- `frontend/src/smart-wrong-questions.test.ts`
- existing review-plan or class-feedback tests only where current behavior is being tightened

## Risks

The largest risk is overreaching into staff workflows while tightening member workflows. The implementation should branch on role cleanly and preserve staff behavior.

Another risk is mixing class-level and student-level filtering incorrectly in the smart wrong question page, which could hide valid records or leak out-of-scope records. The backend access checks must remain authoritative.

## Out Of Scope

- Changing `owner`, `admin`, or `super_owner` visibility rules
- Building a global shared class-context store across the entire frontend
- Redesigning class management
- Redesigning parent or WeChat mini-program flows beyond preserving correct member visibility