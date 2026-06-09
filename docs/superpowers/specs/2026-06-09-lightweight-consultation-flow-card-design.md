# Lightweight Consultation Flow Card Design

## Context

The consultation module should not become a heavy sales CRM. Xingrun's consultation operators are mostly teachers, so the product must let teachers record a useful consultation with very little typing while still preserving enough structured data for later conversion analysis.

The desired model is: record first, enrich gradually, analyze later.

## Goals

- Let a teacher create a consultation with only the minimum fields needed to identify the student and need.
- Keep optional fields for future conversion analysis without forcing them during creation.
- Show the consultation process directly on each consultation card.
- Allow non-linear flow updates because real consultation work can jump from teacher contact to testing, trial, or direct class enrollment.
- Treat `Over` as a closing action that always asks whether the consultation ended successfully or unsuccessfully.
- Connect successful conversion to class selection and student profile creation or completion.

## Non-Goals

- Do not add sales-person performance ranking.
- Do not force a strict left-to-right approval workflow.
- Do not require all process fields before saving, ending, or converting.
- Do not build the conversion analytics dashboard in this phase; only preserve the data needed for it.

## Create Form

Creation should require only:

- Student name
- Consultation subject
- Consultation grade
- Parent need
- Reception teacher
- Consultation time, defaulting to the creation time

The create form may optionally expose `source`, but it must not require it. All process details belong in follow-up editing after the record exists.

## Optional Fields

Optional analysis and outcome fields:

- Source
- Failure reason
- Conversion class

Optional stage notes:

- Customer-service communication note
- Communication-teacher note
- Test note
- Trial-teacher communication note
- Trial note
- Teaching-teacher communication note
- Enrollment handoff note
- Student profile completion note

These fields should be editable as each stage is handled. They should never block creation.

## Flow Card

Each consultation card should include a compact process display. The process nodes are:

1. Add customer service
2. Add communication teacher
3. Teacher communication
4. Test
5. Add trial teacher
6. Trial
7. Add teaching teacher
8. Enter class
9. Over

The card should show which nodes are completed, current, skipped, or still missing. The flow is visual progress plus a quick operation surface, not a mandatory workflow.

## Non-Linear Flow Rules

Any node can be clicked at any time. The system should not block a teacher from jumping ahead.

Examples:

- A teacher can add the communication teacher before adding customer service.
- A teacher can record a test before any communication note exists.
- A teacher can enter class directly after testing.
- A teacher can end the consultation without class enrollment.

When a later node is completed, earlier untouched nodes stay unrecorded or skipped. The system should preserve reality instead of forcing fake historical data.

## Node Actions

Clicking a node opens the matching action surface:

- Add customer service: mark customer service added and optionally record customer-service communication.
- Add communication teacher: open teacher selector. Selecting a teacher is recommended but optional.
- Teacher communication: record communication status and note.
- Test: record whether testing happened and the test situation.
- Add trial teacher: open teacher selector. Selecting a teacher is recommended but optional.
- Trial: select or type trial class and record trial situation.
- Add teaching teacher: open teacher selector. Selecting a teacher is recommended but optional.
- Enter class: open enrollment panel.
- Over: open closing-result dialog.

Teacher selectors must allow "not selected yet" because the real person may be known in chat but not yet confirmed in the system.

## Enter Class Panel

Clicking `Enter class` opens an enrollment panel with three paths:

1. Select existing class
2. Create new class quickly
3. Mark converted without selecting class yet

Quick class creation should ask only for the minimum:

- Subject, defaulting from consultation subject
- Grade, defaulting from consultation grade
- Class type: small class or group class
- Class name or class number
- Teaching teacher, defaulting from the selected teaching teacher if available

After selecting or creating a class, the system should:

- Mark the consultation as converted.
- Save the conversion class.
- Create or complete the student profile.
- Add the student to the selected class when a class is available.

If the teacher chooses "mark converted without selecting class yet", the consultation is successful but should keep a visible "conversion class missing" hint for later completion.

## Over Dialog

Clicking `Over` must not silently close the consultation. It must open a dialog with two choices:

- Consultation success
- Consultation failure

If the record already has a conversion class, an enrollment action, or a created student profile, the dialog should recommend success. If not, it should recommend failure. The teacher can override the recommendation.

Success dialog behavior:

- Use a positive, warm background such as soft green or teal.
- Copy should feel encouraging and operational, for example: "This student has been handed off. Complete the class and student profile details if anything is missing."
- Offer actions to confirm success, complete conversion class, or cancel.

Failure dialog behavior:

- Use a softer gray-orange or light red background.
- Copy should avoid blame and invite useful reflection, for example: "No conversion this time is still useful data. Record the reason so the team can understand what to improve."
- Offer actions to confirm failure, fill failure reason, or cancel.

Confirmed closing stores:

- Closing result: success or failure
- Closed at
- Closed by
- Failure reason and failure note when applicable
- Conversion class and student profile state when applicable

Closed cards should show result, not just `Over`:

- Success: "Success - entered class" or "Success - class missing"
- Failure: "Failed - reason missing" or "Failed - <reason>"

## Conversion Analysis Hooks

This phase should preserve data for later analysis:

- Source conversion
- Consultation count share by grade and subject
- Which parent needs convert more easily
- Time from consultation creation to class entry
- Failure reason distribution

Required timestamps and fields for future analysis:

- Created/consultation time
- Stage completion timestamps where available
- Enter-class timestamp
- Closing timestamp and closing result
- Source
- Parent need
- Subject and grade
- Conversion class
- Failure reason

## Permissions

The flow must respect the existing consultation access model:

- Staff roles can see and manage organization-level consultation records.
- Member teachers can create and update records they are allowed to handle.
- Closing, entering class, and assigning teachers should be limited to users who can edit the record.

## UX Principles

- Creation stays short. Follow-up details live in the card flow and detail modal.
- The card flow should be clickable and forgiving.
- Every action should be reversible or editable unless the user lacks permission.
- Missing analysis data should be hinted gently, not treated as an error.
- The language should sound like teacher collaboration, not sales pipeline management.

## Testing Notes

Implementation should include tests for:

- Create form required fields.
- Optional fields not blocking creation.
- Non-linear flow updates.
- Teacher node actions allowing empty teacher selection.
- Enter-class path for existing class, quick new class, and converted-without-class.
- Over dialog recommendation logic.
- Success and failure closing result persistence.
- Conversion-analysis fields being stored without requiring a dashboard.
