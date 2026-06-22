# Review Plan Version History Design

Date: 2026-06-23

## Context

The review plan page currently treats each `lessons` row as both the course record and the only generated artifact. A regeneration reruns the LLM pipeline and overwrites `plan_json` and `pdf_path` on the same lesson. This is risky because regenerated output can be much worse than the previous version, and the old PDF is no longer visible from the product surface.

The requested product behavior is:

- Regeneration creates a new version and automatically makes it current when it succeeds.
- The old current PDF remains usable while the new version is generating.
- If regeneration fails, the old current PDF remains current.
- The list shows the current version's generation time, not the lesson creation time.
- The detail page is lightweight: PDF preview, download, regenerate, version history, rollback.
- Old generated-artifact fields on `lessons` should be removed through a real data migration instead of being mirrored long-term.

## Goals

- Preserve every generated review plan version for comparison and rollback.
- Keep the history list as one row per lesson, not one row per version.
- Make the current PDF explicit and reversible.
- Keep the UI simple for teachers: show useful version history without exposing model logs by default.
- Simplify the code boundary between lesson metadata and generated artifacts.

## Non-Goals

- No side-by-side PDF diff view.
- No version-level delete action in the first implementation.
- No visible model log or quality review panel in the main detail page.
- No attempt to make LLM regeneration deterministic.
- No production data repair outside the version migration.

## Data Model

`lessons` remains the course-level record. It should keep lesson metadata and a pointer to the current generated version:

- `id`
- `date`
- `subject`
- `grade`
- `topic`
- `summary`
- `weak_points`
- `class_id`
- `organization_id`
- `created_by_user_id`
- `current_review_plan_version_id`
- `created_at`
- `updated_at`

Generated artifacts move into a new table, `review_plan_versions`:

- `id`
- `lesson_id`
- `version_no`
- `status`: `transcribing`, `generating`, `ready`, `failed`
- `plan_json`
- `pdf_path`
- `generation_error`
- `request_key`
- `request_id`
- `chat_provider`
- `chat_model`
- `audio_path`
- `audio_request_key`
- `same_lesson_materials_json`
- `created_by_user_id`
- `created_at`
- `completed_at`

The version table is the source of truth for generated state. `lessons.current_review_plan_version_id` points to the ready version that the list and default preview should use. If no ready version exists, the pointer is empty.

After migration, these old generated-artifact columns should be removed from `lessons`:

- `plan_json`
- `pdf_path`
- `record_status`
- `generation_error`
- `review_audio_path`
- `review_audio_request_key`
- `review_request_key`
- `review_request_id`
- `review_chat_provider`
- `review_chat_model`
- `review_same_lesson_materials_json`

## Migration

`init_db()` should create `review_plan_versions`, add `current_review_plan_version_id` to `lessons`, backfill versions from existing lesson rows, then rebuild `lessons` without old artifact columns.

Backfill rules:

- Existing ready lessons with `plan_json` or `pdf_path` become version 1 with `status='ready'`; `completed_at` uses the best available lesson timestamp.
- Existing failed lessons become version 1 with `status='failed'` and keep `generation_error`; they do not become current.
- Existing `pending`, `generating`, or `transcribing` lessons become version 1 with the corresponding version status.
- Ready migrated versions become the lesson current version.
- If a lesson has no generated artifact and no active generation state, it can exist without versions.

The migration must be idempotent. Re-running `init_db()` must not duplicate version 1 rows or lose existing current pointers.

## Backend Behavior

### New Generation

Creating a new review plan creates:

1. One `lessons` row for the course metadata.
2. One `review_plan_versions` row with `version_no=1`.

If the input is text or a text file, version 1 starts as `generating`.

If the input is audio, version 1 starts as `transcribing`. When transcription succeeds, the version moves to `generating`.

When generation succeeds:

- Write `plan_json`, `pdf_path`, `status='ready'`, and `completed_at` to the version.
- Set `lessons.current_review_plan_version_id` to that version.

When generation fails:

- Write `status='failed'` and `generation_error` to the version.
- Do not set a current version unless one already exists.

### Regeneration

Regeneration creates a new version on the same lesson:

- Use the saved lesson metadata and summary as input.
- Reuse saved same-lesson supplemental materials from the previous generation input.
- Reject regeneration with `409` if another non-terminal version for the same lesson already exists.
- Keep the old current ready version previewable and downloadable while the new version is generating.
- On success, mark the new version ready and automatically set it as current.
- On failure, leave the old current version unchanged and show the failed version in history.

### Rollback

Rollback is a pointer change:

- `POST /api/review-plans/:lesson_id/versions/:version_id/make-current`
- The target version must belong to the lesson.
- The target version must be `ready`.
- The request must pass the same lesson access checks as preview/download.
- The endpoint updates `lessons.current_review_plan_version_id`.
- It does not regenerate a PDF.

### Deletion

Deleting a lesson deletes the lesson and all its versions. All version PDFs should be removed from disk when present. If a file is already missing, deletion still succeeds.

## API Shape

`GET /api/review-plans`

Returns one row per lesson, enriched with current-version summary fields:

- `id`
- lesson metadata
- `current_version_id`
- `current_version_no`
- `current_generated_at`
- `current_pdf_url` or preview/download URLs
- `current_status`
- `has_version_generating`
- `latest_generation_error`

Sorting should use `current_generated_at` when a current version exists. Lessons with no current version fall back to lesson creation time or newest version creation time.

`GET /api/review-plans/:lesson_id`

Returns:

- lesson metadata
- current version summary
- all versions ordered by `version_no DESC`

`POST /api/review-plans/:lesson_id/regenerate`

Creates a new version and starts the async generation job. Returns the new version id and the lesson id.

`GET /api/review-plans/:lesson_id/versions/:version_id/pdf`

Previews a specific version PDF.

`GET /api/review-plans/:lesson_id/versions/:version_id/download`

Downloads a specific version PDF.

`POST /api/review-plans/:lesson_id/versions/:version_id/make-current`

Sets a ready version as current.

Existing current-PDF preview/download URLs may remain as compatibility wrappers that resolve through the current version pointer.

## Frontend Design

The review plan list remains one lesson per row. It displays current-version state:

- The time column shows the current version generation time.
- If a new version is generating, the row shows `正在生成新版`.
- Preview and download continue to target the current ready version.
- If there is no ready current version, preview and download are disabled.
- The row has a `详情` action that opens a second-level detail page.

The detail page is lightweight:

- Header: topic, subject/class metadata, current version number, current generation time.
- Main area: current PDF preview and download action.
- Version history: newest first, showing version number, status, generation time, and actions.

Version history actions:

- Current ready version: preview, download.
- Old ready version: preview, download, set as current.
- Generating version: show progress/status text only.
- Failed version: show error text; no rollback action.

The first implementation should not show model internals, trace logs, or quality scores in the main UI. Those can remain backend observability data.

## Code Organization

Use the code-simplification constraint while implementing:

- Add focused lesson/version store functions in `lesson_manager.py`, such as:
  - `create_review_plan_version`
  - `complete_review_plan_version`
  - `fail_review_plan_version`
  - `set_current_review_plan_version`
  - `list_review_plan_versions`
  - `get_review_plan_version`
- Keep migration helpers separate from the main `init_db()` flow.
- Avoid adding more version UI logic directly into `ReviewGenerationPage.tsx`.
- Prefer small frontend units:
  - `ReviewPlanDetailView`
  - `ReviewPlanVersionList`
  - version status helpers in a small module
- Keep compatibility wrappers thin and delete dead old-field reads after migration tests pass.

## Error Handling

- Regeneration returns `409` if a version is already `transcribing` or `generating`.
- If the current version PDF file is missing, the list/detail page shows a missing-PDF state and suggests regenerating; it must not silently switch versions.
- If a non-current version PDF is missing, that version's preview/download actions are disabled.
- Failed regenerations keep the old current version intact.
- Rollback to failed, generating, or foreign versions returns an error.
- Deleting a lesson ignores missing files but still removes database rows.

## Testing

Backend storage tests:

- Migrates old ready lesson artifact fields into version 1 and sets current.
- Migrates old failed lesson into failed version without current.
- Migration is idempotent.
- New generation creates lesson plus version 1.
- Regeneration creates version N without changing old current.
- Successful version N switches current.
- Failed version N leaves old current unchanged.
- `make-current` only accepts ready versions from the same lesson.

API tests:

- List rows sort by current version generation time.
- Detail returns versions newest first.
- Preview/download enforce lesson and version access.
- Regeneration rejects duplicate active versions.
- Delete removes all version rows and available PDF files.

Frontend tests:

- List displays current version generation time.
- Regeneration keeps old preview/download available and shows `正在生成新版`.
- Detail page renders version history.
- Old ready version can be set as current.
- Failed version shows error and cannot be set current.

## Acceptance Criteria

- A poor regeneration no longer destroys access to the previous good PDF.
- Regeneration success automatically updates the current version and list time.
- Regeneration failure leaves the previous current version untouched.
- Teachers can open a lightweight detail page, inspect version history, and roll back.
- `lessons` no longer stores generated artifact fields after migration.
- Tests prove migration, regeneration, rollback, preview/download, and list sorting behavior.
