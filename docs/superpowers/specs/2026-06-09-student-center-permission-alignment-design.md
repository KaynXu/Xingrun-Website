# Student Center Permission Alignment Design

## Goal

Align the student center permission layer so each role sees a consistent UI and backend authorization result.

## Role Scope

- `super_owner`, `owner`, and `admin` use organization-level scope in the student center.
- These roles can view the full campus overview, view all classes in the organization, create and edit classes, create and edit student profiles, and bind teachers to classes.
- `member` uses teacher-level scope in the student center.
- `member` can view only classes assigned to that teacher and the students inside those classes.
- `member` has no edit permission in this student center flow: no class creation, class editing, student profile creation or editing, class student add/remove, invite reset, or teacher binding.

## UI Behavior

- For organization-level roles, the overview label remains `校区总览`.
- For `member`, the same overview surface is labeled `教师总览`, with the scope pill labeled `学生人数`; the underlying read-only summary behavior remains available.
- The page must not fail with a blanket `无权限` when a `member` opens the student center.
- Edit controls must be hidden or disabled for `member` according to the centralized student center permission model.

## Backend Behavior

- Backend authorization remains the source of truth.
- Organization-level roles can access organization-level student center endpoints.
- `member` can read only the class and student data needed for assigned classes.
- `member` write attempts against student center class/student/teacher-binding endpoints return `403`.
- Class-scoped read endpoints must continue to validate that the requested class is assigned to the teacher.

## Sorting

- Student center class displays sort small classes before group classes.
- Within each class type, classes sort by grade from low to high.
- Existing filters continue to apply before display ordering.

## Tests

- Add frontend permission tests for admin organization scope and member read-only behavior.
- Add frontend load tests proving member page load skips staff-only calls and does not call forbidden organization-wide student endpoints.
- Add backend API tests proving members can load assigned class/student read data but cannot mutate student center data.
- Add sorting rule tests for small-class-first and low-to-high grade ordering.
