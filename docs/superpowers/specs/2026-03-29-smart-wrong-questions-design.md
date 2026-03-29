# Smart Wrong Questions Design

## Goal

Add a new internal-only SaaS tab named `智能错题` so teachers and admins can review parent-submitted wrong-question records, add follow-up feedback, and export summaries without changing the parent-facing mini program entry.

## Why This Change

The parent workflow already exists in the mini program and should remain the submission entry. Internal staff need a stable workspace-native view inside the existing SaaS shell so they can process records with the same login, navigation, and permission model they already use for other operations.

The current `mini program/frontend` web app is not the right integration target because it is not a mature internal business console for this workflow. The practical path is to add a new SaaS module that reuses the underlying wrong-question data and processing APIs.

## Product Decision

### Dual Entry Model

The workflow keeps two separate user-facing entry points for the same business domain:

- parents continue using the mini program for submission and student-side follow-up
- internal teachers and admins use the SaaS `智能错题` tab for review and export

The two surfaces share business data, but they do not need to share the same UI or login flow.

### First Release Scope

The first release of `智能错题` must support:

- viewing wrong-question records submitted from the parent flow
- reviewing AI diagnosis details and student-added notes
- adding teacher follow-up feedback or review selections
- exporting PDF summaries

The first release does not need to reproduce the parent chat room experience or the full mini program workflow.

## Architecture

### Frontend Surface

The existing SaaS Vite + React shell remains the only internal frontend runtime.

Implementation approach:

- add `智能错题` as a new left-sidebar tab in the current workspace shell
- add a new `Page` value and render branch in `frontend/src/App.tsx`
- implement the new page in the same design language as the current SaaS pages

This avoids introducing a second router/runtime inside the internal workspace.

### Backend Boundary

The SaaS backend should provide an internal proxy layer for wrong-question operations instead of having the browser call the mini program backend directly.

Recommended request path:

- SaaS frontend calls internal `/api/wrong-questions*`
- SaaS backend validates SaaS auth token and role
- SaaS backend calls the mini program backend as the downstream data source

This keeps permissions and secrets inside the trusted server layer and preserves the option to migrate data ownership later without rewriting the frontend.

### Mini Program Boundary

The mini program remains the parent-facing submission interface.

Included behavior to preserve:

- parent uploads and image submission
- AI diagnosis generation
- student-side self-review data capture
- existing PDF generation capability

No parent-side entry changes are required for this phase.

## UX Design

### Navigation

Add a left sidebar item labeled `智能错题`.

Visibility:

- visible to `owner`
- visible to `admin`
- hidden from regular members in the first release

The page title in the workspace header should also read `智能错题`.

### Page Layout

The page uses a three-part internal workspace layout:

#### Top Summary And Filters

The top area shows summary cards and filtering controls.

Summary cards:

- 今日记录数
- 待处理数
- 需要复讲数
- 需要单独跟进数

Filter controls:

- date range
- student name
- class name
- subject
- handling status
- teacher priority

#### Record List

The main list shows wrong-question records in descending time order.

Each list item shows:

- student name
- class name when available
- subject
- submission time
- current status
- repeated-mistake signal
- teacher-priority signal

The list should make unhandled or high-priority records easy to scan.

#### Detail Workspace

Selecting a record opens a detail panel or detail column that contains:

- original image preview
- AI diagnosis data
- student self-review content
- teacher follow-up form
- export actions

### Teacher Review Area

The teacher review form supports:

- confirming or adjusting error type
- confirming or adjusting knowledge points
- marking next actions or follow-up reasons
- adding teacher notes
- saving review results back to the server

The first release should optimize for review clarity, not for real-time collaboration.

## Data Model

The SaaS frontend should normalize wrong-question records into one stable internal shape.

Recommended view model:

### WrongQuestionRecord

- `id`
- `roomId`
- `studentName`
- `teacherName`
- `className`
- `subject`
- `status`
- `note`
- `imageUrl`
- `time`
- `recordDate`
- `analysis`

### WrongQuestionAnalysis

- `questionCategory`
- `errorType`
- `knowledgePoints`
- `isRepeatedMistake`
- `nextSteps`
- `teacherPriority`
- `selectedErrorType`
- `selectedKnowledgePoints`
- `selectedActions`
- `selectedReasons`
- `studentNote`

This matches the downstream feedback record shape closely enough to keep the proxy layer thin while still giving the SaaS frontend a stable contract.

## API Design

The browser should only talk to SaaS-native endpoints.

Recommended first-release endpoints:

### `GET /api/wrong-questions`

Returns the filtered record list for the page.

Supported query dimensions:

- date range
- student name
- class name
- subject
- handling status
- teacher priority

### `GET /api/wrong-questions/:id`

Returns one record with full detail data needed for the detail workspace.

### `PUT /api/wrong-questions/:id/review`

Saves teacher-side review selections and notes.

### `GET /api/wrong-questions/summary/export`

Returns a download response or signed download URL for PDF summary export based on current filters.

## Permissions

The new tab must be protected at both frontend and backend layers.

Rules:

- only `owner` and `admin` can see the tab in the sidebar
- only `owner` and `admin` can access the proxy endpoints
- regular members must receive denial even if they try to call the endpoints directly
- the mini program backend must not be called directly from the browser

## Error Handling

### List Loading Failure

- show a retryable error card
- keep the current list state if stale data already exists

### Detail Loading Failure

- keep the selected record in the list
- show a detail-level retry state rather than dropping page context

### Review Save Failure

- show an explicit failure message
- do not silently discard edits
- keep the unsaved form values available for retry

### Export Failure

- show a clear export error
- do not reset current filters or selected record

### Downstream Service Failure

- the SaaS backend returns a stable business error response
- downstream URL or token details are never exposed to the browser

## Scope Boundaries

Included in scope:

- new internal-only `智能错题` tab in the existing SaaS shell
- summary cards, filter bar, record list, detail panel, review form, export action
- SaaS backend proxy endpoints for list, detail, review save, export
- wrong-question data normalization for the frontend
- owner/admin permission enforcement

Out of scope for the first release:

- parent mini program UX redesign
- merging mini program login with SaaS login
- browser-direct calls to the mini program backend
- full room chat reconstruction inside SaaS
- WebSocket live room view
- scheduled-question administration
- database migration that fully moves the wrong-question domain into the SaaS backend

## Implementation Sequence

Recommended build order:

1. add SaaS backend proxy endpoints for wrong-question list, detail, review save, and export
2. add sidebar navigation and page plumbing for `智能错题`
3. implement the minimum working page layout inside the current SaaS shell
4. connect filters, detail loading, save flow, and export
5. add role visibility and access-control regression coverage
6. run focused verification for backend and frontend changes

## Testing Strategy

### Frontend

Add or update tests to cover:

- sidebar visibility by role
- `智能错题` tab navigation
- loading and error states
- detail rendering
- save and retry states
- export action presence

Primary frontend files will likely include:

- `frontend/src/App.tsx`
- `frontend/src/account-card.test.tsx`
- `frontend/src/workspace-navigation.test.ts`

### Backend

Add tests to cover:

- role-based denial for unauthorized users
- proxy list response mapping
- proxy detail response mapping
- review-save pass-through behavior
- export behavior and downstream failure handling

## Acceptance Criteria

- `owner` and `admin` can see `智能错题` in the left sidebar
- clicking `智能错题` opens a workspace-native page inside the existing SaaS shell
- the page shows recent wrong-question records in descending time order
- staff can open a record and see image, AI diagnosis, and student self-review data
- staff can save teacher review content from the SaaS page
- staff can export a PDF summary from the SaaS page
- non-authorized users cannot see the tab and cannot access the related endpoints
- the parent mini program entry and parent submission flow remain unchanged