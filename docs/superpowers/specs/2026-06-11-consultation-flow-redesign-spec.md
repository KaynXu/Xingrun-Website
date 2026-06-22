# Consultation Flow Redesign Spec

Status: Node 9 completed
Date: 2026-06-11

## Goal

Rebuild the consultation flow interaction layer in small, recoverable steps. The current baseline keeps the consultation list, filters, and basic flow graph. This spec defines the next implementation nodes so future context compaction can resume from a stable source of truth.

## Non Goals

- Do not replace the consultation page top filter structure.
- Do not implement real-time message push in this phase.
- Do not redesign the UI from scratch. Reuse the previous modal/card visual style.
- Do not automatically delete real class or student profile records when canceling a successful Over.

## Current Baseline

- Consultation cards and the edit modal show a basic flow graph.
- The complex node dialogs, enter-class dialog, Over dialog, and synchronized teacher status pills were removed during rollback.
- Default consultation list filter is `pending`.
- Existing build passes, while unrelated class-management source tests still have known failures.

## Confirmed Input Rules

- Mouse left click equals screen tap.
- Mouse right click equals screen long press.
- Left click/tap opens the node dialog for editing node information.
- Right click/long press opens the node dialog and treats the saved node as the current stage.
- A recommended teacher is only a form suggestion. It does not light the node, complete the node, or create assignment until saved.

## 2026-06-16 Stabilization Baseline

The current stabilization pass is named `更新咨询节点构建`. Its purpose is to make the local preview understandable again before adding more consultation features.

Use this single rule table as the source of truth:

- Left click/tap on a white process stage opens the node dialog; saving the dialog lights that stage.
- Left click/tap on a green or blue process stage cancels that stage directly, deletes that stage's mapped content, and turns the stage white.
- Right click/long press on a process stage opens the node dialog; saving the dialog makes that stage current and deletes later stage content.
- Green means a saved completed stage before the current stage.
- Blue means the current stage, normally the last completed visible stage.
- White means not saved, or hidden because it is after the current stage.
- Red means failed Over.
- Successful Over is blue, and skipped process stages are not auto-completed.

Save semantics are intentionally different by surface:

- Consultation list cards are immediate-action surfaces. A flow action on a card saves to the backend immediately.
- The consultation edit modal is a draft-editing surface. A flow action in the modal updates the form draft first; it is persisted when the modal Save action submits.
- The UI must make this distinction clear enough that teachers do not expect a modal flow click to be saved after closing without saving.

Deferred from this stabilization pass:

- Real push notifications.
- Large redesign of the view/edit modal layout.
- Full historical assignment timeline.
- Deleting real created classes or student profiles when canceling Over.

## Flow Light Rules

The flow graph is not a strict required sequence. It visualizes saved work and the current responsibility stage.

- Green means the stage has saved content and is marked complete.
- Blue means the current stage.
- Red means failed Over.
- White means not completed or hidden after the current stage.
- The current stage is the last completed visible stage unless Over is active.
- If only one stage is complete, it is blue.
- If the last completed stage changes, blue moves to the new last completed stage.
- Blue has priority over green: the same node is not shown as both.
- No green node may be shown after the blue node.
- Non-linear completion is allowed. Example: if A, B, and E are completed, then A/B are green, C/D are white, and E is blue.

## Cancellation Rules

Canceling a lit node deletes the node content as well as turning off the light.

- Clicking a green node cancels it directly: delete that stage's content and turn the node white.
- Clicking a blue node cancels it directly: delete that stage's content, turn it white, and move blue to the previous completed stage.
- Clicking red Over cancels failure Over directly: delete failed closing state and return to the previous stage.
- Clicking successful blue Over cancels success Over directly: delete success closing state and return to the previous stage.
- Canceling successful Over must not automatically delete created classes or student profile records. Those are real business records and require a separate admin action.

## Current Stage Reset Rule

When a user right-clicks or long-presses an earlier stage to make it current:

- The dialog must warn that choosing this current stage will delete later flow content.
- If confirmed, delete completed states and stage content after the chosen stage.
- If canceled, do not change the current stage.

## Node Dialog Rules

The previous UI style should be reused:

- White rounded modal.
- Header contains stage title and student summary.
- Main teacher selector uses a status card style: `xx教师：x老师 ✓`.
- Unselected state is light blue/gray.
- Selected state is green with a check icon.
- Below the teacher selector is the stage note field.
- Footer has save and cancel actions.

Stage teacher behavior:

- Customer-service stage only offers the small customer-service teacher option for now.
- Customer-service teacher is not used as a later teacher recommendation.
- Communication, test, trial, and teaching stages can choose teachers.
- Teacher lists can use class/student-center filter logic 1 when the list is large.
- From communication onward, default recommendation is the previous saved teacher in the flow.
- If the previous teacher was not saved, it may appear as a recommendation only; it does not light the node.

Card display after save is intentionally deferred until after the core interactions work.

## Enter Class Rules

The enter-class flow must restore the previous three-card UI:

- Existing class
- Quick create class
- Converted pending class

Existing class:

- Use filter logic 1.
- Filtered results appear in a dropdown, not a full list.
- Consultation subject and grade are recommendations for the enter-class filters, not hard locks.
- If the consultation subject already exists, preselect that subject in the class filter; teachers may still change it.
- If the consultation subject is blank and the teacher selects a subject in the enter-class filter or quick-create form, save can backfill the consultation subject.
- Consultation grade should preselect the grade filter when useful, but must remain editable because a sixth-grade consultation may enter a seventh- or eighth-grade class.
- If recommended filters return no usable class, provide a way to loosen filters or show all classes instead of blocking the enter-class action.

Quick create class:

- Reuse student-center class-management create-class logic.
- Keep the compact modal layout from the previous version.
- Include class type, subject, stage, grade, class number, bridge-class controls, and modified class-name preview.

Converted pending class:

- Mark consultation as successful conversion while class/profile details can be completed later.

## Over Rules

- Successful enter-class automatically creates a successful Over state.
- On successful Over, only previously saved process stages remain green; skipped process stages must not be auto-completed. Over is blue.
- Manual Over first asks success or failure.
- Manual success opens the enter-class dialog and must complete one of the three enter-class modes before Over is saved.
- Manual failure creates red Over and records the failure path.
- Red Over can be canceled directly and returns to the previous stage.
- Successful blue Over can be canceled directly and returns to the previous stage.

## Assignment And Teacher Visibility

This phase implements assignment visibility, not real push notifications.

Teacher accounts see:

- Consultations they created.
- Consultations transferred/assigned to them.

Transferred consultations:

- Must show a `咨询转接` marker.
- Must show current responsibility, such as `试听教师：雷老师`.
- Must show assignment note.
- Should use a different card background from self-created consultations.

Editing scope:

- Teachers can edit their own created consultations according to teacher permissions.
- Teachers can edit assigned consultations from the assigned stage onward.
- Teachers cannot edit prior stages on transferred consultations.
- Admin, owner, and super admin can recover, reassign, and edit the full flow.

## Data Model Concepts

Existing fields may be reused when practical, but the implementation should preserve these concepts clearly:

- `completed_stages`: stages saved and marked complete.
- `flow_stage`: current stage, normally the last visible completed stage or Over.
- `stage_notes`: notes per stage.
- `stage_teacher_ids`: teacher assignment per stage.
- `assigned_teacher_id`: current responsible teacher.
- `assigned_stage`: stage transferred to the teacher.
- `assignment_note`: transfer note.
- `closing_result`: success or failed.

## Implementation Nodes

### Node 1: Rules Document

Status: Completed

Scope:

- Write this spec.
- Do not change functional code.

Acceptance:

- Spec records rules, UI reuse, 9 nodes, and non-goals.
- Spec can be used after context compaction to resume work.

### Node 2: Flow Pure Functions

Status: Completed

Scope:

- Implement and test pure functions for light calculation, completion, canceling, current-stage reset, and Over rollback.
- No UI changes.

Acceptance:

- Tests cover nonlinear completion such as A/B/E.
- Tests cover green cancel, blue cancel, red Over cancel, successful Over cancel.
- Tests cover choosing an earlier current stage and deleting later flow content.

### Node 3: Basic Flow Click Wiring

Status: Completed

Scope:

- Wire left click/tap and right click/long press to pure functions.
- Do not build node modal UI.
- Use temporary simple handlers only if needed to prove state transitions.

Acceptance:

- Left click/tap and right click/long press can be distinguished.
- Current stage and completed stage state follow pure-function tests.
- No enter-class or Over dialogs are introduced.

### Node 4: Ordinary Node Dialog

Status: Completed

Scope:

- Restore ordinary node modal UI for customer-service, communication, test, trial, and teaching stages.
- Save stage teacher and stage note.
- Save lights the node.

Acceptance:

- Unsaved dialog close does not light the node.
- Save lights the node and records fields.
- Clicking a lit node cancels and deletes the node content according to the cancellation rules.

### Node 5: Teacher Filtering And Recommendation

Status: Completed

Scope:

- Add filter logic 1 to teacher selection where needed.
- Customer-service stage only offers small customer-service teacher.
- From communication onward, recommend previous saved teacher.

Acceptance:

- Recommendation alone does not light or assign.
- Saving a teacher writes the stage teacher.
- Customer-service teacher is not used as the next recommendation.

### Node 6: Enter-Class Dialog UI

Status: Completed

Scope:

- Restore three-card enter-class modal shell.
- Restore existing visual layout from the previous version.
- Only mode switching and field display; no final save integration yet.

Acceptance:

- Shows Existing Class, Quick Create Class, Converted Pending Class.
- Quick create layout matches compact previous UI.
- No class/student records are created in this node.

### Node 7: Enter-Class Business Integration

Status: Completed

Scope:

- Existing class mode uses filter logic 1 and dropdown.
- Quick create mode reuses student-center class-management creation logic.
- Converted pending mode saves successful conversion pending class/profile details.

Acceptance:

- Existing class selection saves conversion class.
- Quick create creates class then saves conversion.
- Converted pending saves success with pending completion state.

### Node 8: Over Logic

Status: Completed

Scope:

- Successful enter-class automatically Over.
- Manual Over success/failure flow.
- Red/blue Over display and cancellation.

Acceptance:

- Success requires enter-class modal completion.
- Failure records red Over.
- Canceling Over returns to previous stage and removes closing state.
- Canceling successful Over does not delete class/student profile records.

### Node 9: Assignment And Teacher Permissions

Status: Completed

Scope:

- Teacher consultation list includes self-created and assigned consultations.
- Add transferred-card marker/background/current responsibility/assignment note.
- Restrict transferred consultation editing to assigned stage and later.
- Admin roles can recover, reassign, and edit full flow.

Acceptance:

- Teacher sees own + assigned cards.
- Assigned cards are visually distinct and marked `咨询转接`.
- Teacher cannot edit stages before the assigned stage.
- Admin roles can reassign or recover.

## Progress Log

- 2026-06-11: Spec created as Node 1 draft.
- 2026-06-11: Node 1 marked completed after rollback baseline was confirmed.
- 2026-06-11: Node 2 added tested pure functions for flow lights, stage completion/cancel, current-stage reset, and Over rollback.
- 2026-06-11: Node 3 wired left-click/tap and right-click/long-press to the tested pure functions without restoring complex dialogs.
- 2026-06-12: Node 4 restored the ordinary process-node dialog for the current five flow nodes, with save-to-light and lit-node cancellation/field clearing.
- 2026-06-12: Node 5 added tested teacher filtering and recommendation rules to the ordinary process-node dialog.
- 2026-06-12: Node 6 restored the three-card enter-class dialog shell with existing-class, quick-create, and converted-pending modes; quick-create shows compact class fields and class-name preview without creating class/student records.
- 2026-06-12: Node 7 connected the enter-class dialog to the tested business payloads and `/api/consultations/:id/enter-class`, including existing class selection, quick-new-class structured payloads, converted-pending success, and student-center class filtering/order for the existing-class dropdown.
- 2026-06-12: Node 7 review fixes changed existing-class subject/grade from hard filters to editable recommended filters, added loosen-filter fallback, made create-modal enter-class first create the consultation then call `/enter-class`, and backfilled missing consultation subject/grade from the selected or newly created class.
- 2026-06-12: Node 8 restored the Over node on consultation cards, added the success/failure Over dialog, routed success into the enter-class flow, marked failure as red Over, colored successful Over blue without auto-completing skipped process stages, and made clicking an ended Over restore the previous completed stage without deleting class/student records.
- 2026-06-13: Node 9 added consultation assignment visibility for member accounts, including self-created consultations, stage-teacher transfers, `咨询转接` card markers, current responsibility/assignment note display, and backend restrictions that prevent transferred teachers from editing stages before the assigned stage.
- 2026-06-15: Post-node refinement connected enter-class teaching-teacher handoff: the enter-class dialog can select a `带课教师`, payloads include the teacher handoff fields, quick-created classes bind the resolved teacher user, and consultation records save `teaching_teacher` plus `stage_teacher_ids['成功进班']`.
