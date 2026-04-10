# Remove Teacher Feedback Design

> Historical note: `frontend/src/reviewGenerationLegacyLessonFeedback.ts` was removed in the 2026-04-09 batch-1 orphan cleanup. The references below are retained for traceability.

## Summary

The review-generation workspace currently contains an unfinished legacy lesson feedback workflow that was never actually adopted in production. This design removes the feature completely across frontend, backend, tests, API surface, AI usage hooks, and persisted database schema.

After this change, the product scope returns to a simpler model:

- Review generation only creates review documents.
- History only supports viewing, downloading, and deleting generated documents.
- No lesson-level feedback editor, draft generation, autosave, copy-all, or resume-edit entry points remain.

## Scope

### Included

- Remove legacy lesson feedback UI from the review-generation page.
- Remove legacy lesson feedback resume/edit entry points from review history.
- Delete legacy lesson feedback frontend helper modules and tests.
- Delete backend legacy lesson feedback routes and helper functions.
- Delete lesson feedback persistence code and schema management.
- Delete teacher-feedback-specific AI usage and credit labels.
- Drop the `lesson_class_feedbacks` database table as part of initialization/migration logic.

### Not Included

- Changes to the core lesson creation flow outside legacy lesson feedback coupling.
- Changes to PDF generation, history sorting, history pagination, or class management beyond feedback-related branches.
- Changes to unrelated teacher, class, credit, consultation, or wrong-question features.

## Current Context

Teacher feedback is currently wired through the following layers:

- Frontend workspace state and UI in [`frontend/src/App.tsx`](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/App.tsx)
- Dedicated workspace component in [`frontend/src/LegacyLessonFeedbackWorkspace.tsx`](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/LegacyLessonFeedbackWorkspace.tsx)
- Frontend helper/api wrapper module in [`frontend/src/reviewGenerationLegacyLessonFeedback.ts`](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/reviewGenerationLegacyLessonFeedback.ts), later removed in the 2026-04-09 batch-1 orphan cleanup
- Frontend regression coverage in [`frontend/src/review-generation-teacher-feedback.test.tsx`](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/review-generation-teacher-feedback.test.tsx) and portions of [`frontend/src/workspace-navigation.test.ts`](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/workspace-navigation.test.ts)
- Backend feedback routes and helper functions in [`app.py`](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/app.py)
- Feedback persistence and editor-state assembly in [`lesson_manager.py`](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/lesson_manager.py)
- Teacher-feedback draft generation dependency in `ai_processor.py` and related imports if still referenced through `app.py`

Because the feature is a废案, keeping any part of this chain creates false affordances and maintenance cost.

## Product Decisions

### 1. Review Generation Page

- Remove all legacy lesson feedback state from `LessonInput`.
- Remove any load/save/autosave/copy/generate-feedback behavior.
- Remove the legacy lesson feedback workspace mount entirely.
- Remove “继续编辑课后反馈” branching and return the page to a single “生成复习文档” flow.

Result: after document generation, the page only refreshes history and keeps the document-generation experience focused on review content.

### 2. Review History

- Remove the pencil/edit action used for reopening feedback.
- Remove any tooltip, title, or copy referencing feedback continuation.
- Keep history actions to:
  - Preview
  - Download
  - Delete

Result: history accurately reflects the features users can still perform.

### 3. Frontend File Removal

Delete these feature-specific files completely:

- [`frontend/src/LegacyLessonFeedbackWorkspace.tsx`](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/LegacyLessonFeedbackWorkspace.tsx)
- [`frontend/src/reviewGenerationLegacyLessonFeedback.ts`](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/reviewGenerationLegacyLessonFeedback.ts), removed in the 2026-04-09 batch-1 orphan cleanup
- [`frontend/src/review-generation-teacher-feedback.test.tsx`](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/review-generation-teacher-feedback.test.tsx)

Any remaining imports, types, labels, or helper calls tied to legacy lesson feedback should be removed rather than stubbed.

### 4. Backend API Removal

Delete the feedback endpoints entirely:

- `POST /api/review-plans/<lesson_id>/feedback/draft`
- `GET /api/review-plans/<lesson_id>/feedback`
- `PUT /api/review-plans/<lesson_id>/feedback`

Also remove any local helper functions in `app.py` that only exist to normalize, validate, or assemble legacy lesson feedback payloads.

Result: the API surface stops advertising a feature the product no longer supports.

### 5. Persistence And Database Cleanup

- Remove `lesson_class_feedbacks` schema creation and compatibility migration code from `lesson_manager.py`.
- Remove all helper functions that read/write/build feedback state.
- Add explicit cleanup so database initialization drops `lesson_class_feedbacks` if it exists.

This is intentionally destructive. The user explicitly requested complete removal rather than passive abandonment.

### 6. AI Usage And Credit Cleanup

- Remove `legacy_lesson_feedback_draft` usage labels from frontend display maps.
- Remove any backend AI credit accounting branches that exist only for legacy lesson feedback draft generation.
- Remove any now-unused import of `generate_legacy_lesson_feedback_draft`.

Result: credit and usage reporting no longer references a removed feature.

## Data Flow After Removal

### Review Generation

1. User selects class, subject, and lesson content.
2. System creates a lesson/review document.
3. UI refreshes history.
4. No secondary feedback workflow is triggered.

### Review History

1. User loads history.
2. User may preview, download, or delete.
3. No feedback resume path exists.

## Error Handling

- Remove feedback-specific status messages entirely rather than replacing them with dormant placeholders.
- Ensure deleted frontend branches do not leave empty cards or dead spacing in the review-generation layout.
- Ensure removed backend routes return framework-default 404 if requested after deletion.

## Testing Strategy

- Remove obsolete teacher-feedback frontend tests.
- Update workspace navigation tests so they assert legacy lesson feedback UI and resume-edit behavior are absent.
- Add or update assertions to ensure review history only exposes remaining valid actions.
- Run frontend tests, frontend typecheck, frontend build, and backend account-flow tests.
- Add backend regression coverage where needed to confirm removed feedback endpoints are no longer reachable.

## Acceptance Criteria

- No legacy lesson feedback UI appears anywhere in review generation or history.
- No “继续编辑课后反馈” copy or edit button remains in history.
- `LegacyLessonFeedbackWorkspace` and `reviewGenerationLegacyLessonFeedback` modules are deleted.
- Teacher feedback routes are removed from the Flask app.
- Teacher feedback persistence code is removed from the data layer.
- `lesson_class_feedbacks` is dropped from runtime schema management.
- Credit/usage labels no longer mention legacy lesson feedback drafts.
- Test suite and deployment checks pass with the feature removed.
