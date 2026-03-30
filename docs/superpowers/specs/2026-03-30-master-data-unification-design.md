# Teacher, Class, and Member Master Data Unification Design

## Goal

Unify teacher, class, and member identity across the SaaS workspace and downstream business modules so the system no longer treats names in each module as separate truths.

The immediate target is to align SaaS class management and the `智能错题` workflow, while establishing a reusable master-data pattern that can later absorb consultation and other modules.

## Problem Summary

The current system has identity drift:

- SaaS already has relatively canonical user and class data
- `智能错题` and related downstream records still rely heavily on textual `teacher_name`, `class_name`, and `student_name`
- the same teacher or member can appear under multiple names
- business modules can silently invent new names instead of converging on one canonical entity

This causes inconsistent display, weak filtering, ambiguous reporting, and growing cleanup cost every time a new module is added.

## Product Decision

### Single Source of Truth

SaaS `users`, `classes`, and member relationships become the only source of truth for identity.

- canonical teacher identity: `users.id`
- canonical teacher display name: `users.display_name`
- canonical class identity: `classes.id`
- canonical member identity: SaaS member/user binding used by class membership

Other modules may retain source text, but they do not define identity truth.

### Scope For This Project

This design covers first-phase unification for:

- SaaS class and member management
- SaaS `智能错题`
- mini backend integration boundary used by `智能错题`

This phase does not require a full rewrite of the native mini-program UI or a same-day conversion of every historical module.

## Design Principles

- IDs are truth, names are not
- textual source values are preserved as snapshots, not as canonical relations
- new modules must consume centralized identity instead of maintaining private name dictionaries
- migration must be incremental and auditable
- auto-matching must be conservative; ambiguous matches require human confirmation

## Approach Options

### Recommended: SaaS Master Data Plus SaaS Mapping Layer

SaaS owns canonical identities and also owns the compatibility layer that maps historical text or external-system values onto canonical teacher, class, and member records.

Why this is the recommended path:

- matches the user's decision that SaaS `users/classes` are the source of truth
- avoids scattering mapping logic across `智能错题`, consultation, and the mini backend
- allows old records to keep working during migration
- lets the browser consume already-normalized data instead of reconstructing identity client-side

### Alternative: Push Canonical Ownership Into Every Downstream Service

Each downstream system stores and resolves SaaS canonical IDs itself.

Why not now:

- too much simultaneous change across repos
- higher rollout risk
- reintroduces duplicate mapping logic while the migration is still incomplete

### Alternative: Keep Text As Primary And Add Better Normalization Rules

Continue using names as the main relation key and improve matching heuristics.

Why not:

- does not solve root-cause identity drift
- keeps future modules fragile
- guarantees repeated reconciliation work

## Canonical Data Boundaries

### Teacher Identity

Teacher identity is defined only by SaaS `users.id`.

- canonical display name comes from `users.display_name`
- `username`, old display variants, and external teacher names are aliases or snapshots only
- business modules must not treat `teacher_name` text as the final authority for ownership or filtering

### Class Identity

Class identity is defined only by SaaS `classes.id`.

- historical matching may use normalized `class_name + subject`
- that rule is a migration and mapping rule, not a long-term primary key
- downstream modules should filter, aggregate, and permission-check against `class_id`

### Member Identity

Member identity is defined by the SaaS member or user entity that represents the student in class membership.

- if a student already exists in SaaS, business records should attach to that canonical member
- raw student names are retained only as snapshots of the source submission
- repeated-name matching must not silently guess when multiple candidates exist

### Snapshot Fields

Text fields such as `teacher_name`, `class_name`, and `student_name` remain useful, but only as source snapshots.

They are kept for:

- historical display
- source traceability
- migration support
- audit review

They are not used as the authoritative relation key once canonical IDs are known.

## Mapping Layer Design

### Purpose

The SaaS mapping layer resolves historical text and external values into canonical SaaS identities.

It centralizes:

- teacher aliases
- class text-to-class matching
- student/member reconciliation
- mapping status and manual confirmation

### Mapping Categories

Teacher mapping:

- many aliases can point to one canonical teacher user
- aliases include old names, external names, and system-specific labels

Class mapping:

- historical class text maps to one canonical SaaS class
- first-pass automatic matching uses normalized `class_name + subject`

Member mapping:

- historical student names or external identifiers map to one canonical member
- matching must use available context such as class and subject when present

### Mapping Status

Each mapped business record should surface one of these states:

- `mapped`
- `unmapped`
- `ambiguous`
- `needs_review`

These states make the data problem explicit instead of pretending that every name was resolved correctly.

## Record Model Rules

Business records should progressively move to a dual-storage pattern.

Each record should carry:

- canonical fields such as `teacher_user_id`, `class_id`, and `student_member_id`
- snapshot fields such as `teacher_name_snapshot`, `class_name_snapshot`, and `student_name_snapshot`

Rules:

- canonical fields drive filtering, grouping, reporting, and permissions
- snapshot fields preserve the original business context
- if canonical identity is missing, the record must explicitly remain pending mapping instead of silently falling back to free-text truth

## Ownership And Service Boundaries

### SaaS Responsibilities

SaaS owns:

- teacher, class, and member canonical entities
- alias management
- mapping logic and mapping status
- audit history for mapping changes
- normalized read APIs for internal modules

### Mini Backend Responsibilities

The mini backend continues to own:

- parent and student submission flow
- image handling
- AI analysis and wrong-question business data
- PDF-related business outputs

The mini backend does not remain the final authority on who the teacher, class, or student is.

### Business Module Responsibilities

Modules such as `智能错题` consume normalized identity from SaaS.

They do not:

- keep private teacher alias dictionaries
- infer canonical identity in the browser
- invent new truth based on local text fields

## API Shape

Internal SaaS APIs that expose business records to the frontend should already include normalized identity fields.

For example, a normalized wrong-question record should be able to expose:

- `teacher_user_id`
- `teacher_display_name`
- `teacher_name_snapshot`
- `class_id`
- `class_display_name`
- `class_name_snapshot`
- `student_member_id`
- `student_display_name`
- `student_name_snapshot`
- `mapping_status`

The page should display and edit business state, not rebuild identity truth itself.

## Migration Strategy

### Phase 1: Unified Read Path

Build the SaaS mapping layer and use it to normalize read-time data for `智能错题` and adjacent internal workflows.

Goals:

- standardize displayed teacher, class, and member names
- keep historical records functional
- expose mapping status clearly

### Phase 2: Unified Write Path

Start requiring new business writes to store canonical IDs whenever identity can be resolved.

Rules:

- write canonical IDs plus snapshot text
- unresolved records enter a pending-mapping state
- stop allowing new business flows to create fresh free-text identity truth silently

### Phase 3: Strong Constraint

Move core internal logic off textual identity matching.

Goals:

- make canonical IDs the required path in core workflows
- remove direct dependence on `teacher_name`, `class_name`, and `student_name` in critical logic
- keep snapshot fields for history only

## Automatic Matching Policy

Automatic matching must be confidence-based.

Recommended buckets:

- high confidence: auto-attach
- medium confidence: suggest and wait for review
- low confidence: do not attach automatically

Examples:

- unique alias hit for a teacher can be high confidence
- same class text with multiple subject candidates is medium confidence
- repeated student name without enough context is low confidence

The system should prefer explicit queueing over incorrect auto-binding.

## Manual Review Workflow

### Review Queue

The system needs a first-phase admin workflow for unresolved mappings.

Minimum capability:

- list records with unresolved or ambiguous identity
- show suggested candidates
- allow a human to confirm teacher, class, and member mapping
- persist the decision so future matches can reuse it

### Permissions

Only `owner` and `admin` should be allowed to modify canonical mappings or alias resolution.

Regular teachers may see that a record is unresolved, but they should not be allowed to redefine master-data truth.

### Auditability

Mapping actions must be recorded with:

- operator
- time
- old value
- new value
- affected alias or rule context

Without this, incorrect merges will be difficult to diagnose and reverse.

## Error Handling

### Unresolved Identity

If canonical identity cannot be determined, the system should:

- keep the original snapshot visible
- mark the record with a mapping status
- prevent the UI from presenting guessed data as confirmed truth

### Ambiguous Match

If multiple candidates exist, the system should:

- avoid automatic attachment
- surface candidate context
- wait for admin confirmation

### Canonical Rename Or Reassignment

If a canonical teacher or class display name changes later:

- historical records should display the canonical current name where the product expects canonical display
- snapshot values remain available for source traceability

## Risks

Primary risks:

- merging same-name teachers incorrectly
- binding same-name classes across subjects incorrectly
- attaching repeated student names to the wrong member

Risk controls:

- conservative auto-matching
- explicit review queue
- role-restricted manual confirmation
- audit trail for mapping changes

## Out Of Scope

This design does not include:

- a full replacement of the native mini-program frontend
- a same-phase rewrite of every legacy module
- a full redesign of teacher authentication in the mini backend
- speculative cleanup unrelated to identity convergence

## Success Criteria

The project is successful when:

- internal modules display one canonical teacher, class, and member identity for the same real-world entity
- `智能错题` records can be filtered and grouped by canonical teacher and class instead of raw text only
- new data creation stops introducing fresh free-text identity truth
- unresolved cases are visible and operable through an explicit admin workflow
- future modules can integrate by consuming SaaS master data rather than creating their own naming layer