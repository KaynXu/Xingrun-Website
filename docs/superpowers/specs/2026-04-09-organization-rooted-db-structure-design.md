# Organization-Rooted DB Structure Design

## Context

Current `xingrun.db` already contains many foreign keys, but the visualized schema still feels like a line graph instead of a centered business model.

The main reason is not that relations are missing everywhere. It is that the current model mixes two different ideas:

- tenant ownership: records belong to an `organization`
- operational linkage: records happen to be connected through `users`, `classes`, or join tables

That makes some important records require multiple hops before their tenant is obvious, and some entities such as `students` appear visually detached from the institution root.

The user chose `organizations` as the single structural center for the next schema cleanup.

## Goal

Reshape the schema so `organizations` becomes the clear root of the business graph:

- every core business entity can be traced back to one organization in one hop
- join tables stay as edges, not as hidden ownership anchors
- ER visualization looks like a hub-and-spoke tenant model instead of a mostly linear chain
- the change stays incremental and compatible with the current codebase

## Non-Goals

- no broad domain rewrite
- no introduction of a new generic hub table
- no unrelated cleanup of legacy wording, display names, or UI code
- no attempt to solve every historical data inconsistency in this round

## Recommended Approach

Use `organizations` as the only ownership root, and make organization ownership explicit on all core tenant-scoped tables.

This is a medium-scope structural cleanup:

- keep the existing tables and business concepts
- add missing tenant columns where the model is currently indirect
- tighten foreign keys and indexes around `organization_id`
- keep join tables focused on relationship mapping only

This avoids a risky redesign while still making the schema visibly centered and easier to query.

## Target Shape

### Root

- `organizations`

### Direct organization children

These tables should all have explicit `organization_id` and a direct foreign key to `organizations(id)`:

- `users`
- `classes`
- `students`
- `lessons`
- `consultations`
- `parent_student_bindings`
- `wrong_question_submissions`
- `class_feedback_tasks`
- `organization_credit_accounts`
- `organization_credit_ledger`
- `ai_usage_ledger`

### Organization-adjacent but still direct enough

These already point directly at organization ownership or are scoped by organization-specific parents and can stay that way:

- `organization_invites`
- `class_invite_codes`
- `xhs_order_redemptions`
- `registration_requests`

### Relationship-only tables

These should not become ownership anchors. They stay as connectors:

- `user_classes`
- `class_students`
- `class_feedback_student_entries`
- `auth_sessions`
- `user_aliases`
- `class_aliases`

## Concrete Schema Changes

### 1. Make `students` tenant-scoped

Current problem:

- `students` has no `organization_id`
- organization ownership is only inferred through `class_students -> classes -> organizations`
- in ER views, `students` floats as a global entity

Change:

- add `organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE` to `students`

Result:

- each student becomes visibly anchored to one organization
- class membership remains a placement relation, not an ownership relation

### 2. Keep `classes` and `lessons` as direct organization children

Current state:

- both already include `organization_id`

Change:

- keep them as the main instructional branch under `organizations`
- add organization-scoped indexes so they are visibly and operationally first-class tenant entities

### 3. Keep consultation and wrong-question flows directly under organizations

Current state:

- `consultations`, `wrong_question_submissions`, and `parent_student_bindings` already include `organization_id`

Change:

- keep these direct links
- avoid shifting ownership to `assigned_user_id`, `teacher_user_id`, or `class_id`

Reason:

- users/classes are operational actors in these flows, not tenant roots

### 4. Keep class feedback under organizations through explicit ownership

Current problem:

- `class_feedback_tasks` is currently linked to `class_id` and users, but does not directly show tenant ownership

Change:

- add `organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE` to `class_feedback_tasks`

Result:

- feedback tasks become direct tenant records
- the graph stops depending on `class_feedback_tasks -> classes -> organizations` as the only ownership chain

### 5. Preserve join tables as joins

No new `organization_id` should be added to these unless a future performance reason makes it necessary:

- `user_classes`
- `class_students`
- `class_feedback_student_entries`

Reason:

- their job is to connect already-owned entities
- adding redundant tenant ownership there would make the graph noisier, not clearer

### 6. Keep alias and audit tables attached to their source entities

No tenant column is needed right now on:

- `user_aliases`
- `class_aliases`
- `master_data_audit_log`
- `wrong_question_mappings`

Reason:

- they are metadata about already-owned entities
- ownership can still be derived from their direct referenced rows
- adding tenant columns here would be optional denormalization, not structural clarity

## Migration Strategy

Because the current local `data/xingrun.db` is nearly empty, this migration can stay simple and low-risk.

### Required migration steps

1. Add new nullable columns first where needed:
   - `students.organization_id`
   - `class_feedback_tasks.organization_id`
2. Backfill from existing parent relations:
   - `students.organization_id` from joined class membership where available
   - `class_feedback_tasks.organization_id` from `classes.organization_id`
3. For future inserts, write the organization explicitly in application code instead of relying on multi-hop inference.
4. Rebuild affected tables if needed to enforce final `NOT NULL` and `ON DELETE CASCADE` constraints cleanly in SQLite.
5. Add indexes for organization-scoped listing and filtering.

### Backfill rules

- If a student is linked to one or more classes, all linked classes must resolve to the same organization.
- If a student has no class membership yet, creation APIs must require an explicit organization at write time.
- If historical data ever reveals a cross-organization student linkage, migration should stop and surface the conflicting student ids instead of silently picking one.

## Indexing Plan

Add or ensure indexes for the organization-rooted branch:

- `students(organization_id, name)`
- `classes(organization_id, grade, subject, name)`
- `lessons(organization_id, class_id, date)`
- `consultations(organization_id, assigned_user_id, updated_at)`
- `class_feedback_tasks(organization_id, class_id, status, updated_at)`
- `wrong_question_submissions(organization_id, class_id, teacher_user_id, status)`

The exact index list can stay minimal in implementation, but every high-traffic tenant-scoped table should have at least one organization-leading index.

## Application-Layer Impact

The backend should stop treating organization ownership as something inferred late.

Implementation should update creation and mutation paths so that:

- student creation knows the target organization explicitly
- class feedback task creation writes `organization_id` directly
- queries can filter by organization first, then by class/user/status

This should reduce accidental cross-tenant ambiguity and make permission filtering more straightforward.

## Expected Visualization Outcome

After the change, the schema graph should read more like:

- `organizations` at the center
- direct spokes to tenant-owned business tables
- secondary edges from those business tables to operational actors like `users`, `classes`, and `students`
- small join tables hanging off the owned entities rather than acting like hidden backbone nodes

That means the graph should no longer feel like:

- `organizations -> classes -> class_students -> students -> ...`

and should instead feel like:

- `organizations -> students`
- `organizations -> classes`
- `organizations -> lessons`
- `organizations -> consultations`
- `organizations -> wrong_question_submissions`
- `organizations -> class_feedback_tasks`

with join tables remaining visually secondary.

## Testing Strategy

Implementation should prove:

- new schema initialization creates the added organization-rooted columns
- migration backfills `students.organization_id` and `class_feedback_tasks.organization_id`
- student creation rejects missing or conflicting organization ownership
- organization deletion cascades correctly for newly direct-owned tables
- tenant-scoped queries continue returning the same business rows as before

## Risks

### Student ownership ambiguity

This is the most important structural risk in the whole change. The current model implicitly allows a student to be treated as a reusable global identity. Moving to `organization_id` makes the intended ownership explicit, which is good, but any historical cross-tenant reuse will have to be detected and handled deliberately.

### SQLite migration ergonomics

SQLite is easy for additive changes and awkward for strict constraint rewrites. Implementation should use the existing migration style in `lesson_manager.py`: inspect schema, add columns safely, and rebuild only the tables that truly need final strictness.

## Recommendation Summary

Implement the organization-rooted cleanup in one focused feature branch by:

- adding `organization_id` to `students`
- adding `organization_id` to `class_feedback_tasks`
- preserving direct tenant ownership on already-correct business tables
- keeping join tables and metadata tables lean
- adding organization-leading indexes for the main operational tables

This gives the database a visible center without turning the project into a large-scale schema rewrite.
