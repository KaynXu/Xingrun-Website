# Workspace Pagination And Grid Polish Design

## Summary

This design covers four UI changes in the authenticated workspace:

1. Credit center ledger should stop rendering a long single list and instead paginate the filtered ledger, showing 10 items per page.
2. Class management should reduce page length by rendering class cards in a responsive grid with three cards per row on desktop.
3. Review document history should make its ordering rule visible to users by surfacing generation time and keeping newest generated records first.
4. Review document history should switch from a long single table into a paginated multi-card grid to reduce page length.

The goal is to shorten tall pages without changing the underlying business flows for credits, class assignment, or lesson generation.

## Scope

### Included

- Frontend pagination state and controls for the credit ledger.
- Frontend responsive grid layout for class cards.
- Review history UI refactor from table layout to card grid layout.
- Review history pagination.
- Explicit display of lesson `created_at` as the generation timestamp in review history.
- Preserve newest-first ordering based on backend `created_at DESC, id DESC`.

### Not Included

- New backend pagination endpoints.
- Changes to ledger query limits or filtering rules.
- Changes to lesson creation, PDF generation, or feedback editing behavior.
- Changes to class CRUD rules or teacher assignment logic.

## Current Context

- The main implementation surface is [`frontend/src/App.tsx`](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/App.tsx), which currently contains the credit center, class management page, and review history components.
- Review history already receives lessons from `/api/lessons`.
- Backend lesson list queries in [`lesson_manager.py`](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/lesson_manager.py) and [`app.py`](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/app.py) already sort by `created_at DESC, id DESC`.
- The current mismatch is mostly presentational: the history UI emphasizes lesson date instead of generation time and uses a tall table layout.

## Design Decisions

### 1. Credit Ledger Pagination

- Keep the existing `/api/credits/ledger` fetch behavior.
- Apply pagination after the existing direction filter so page counts always reflect the visible subset.
- Default page size: 10 items.
- Reset to page 1 when the filter changes or fresh data is loaded.
- Show compact previous/next controls with current page and total page count.

This keeps the change local to the UI and avoids expanding backend API scope for a page-length problem.

### 2. Class Card Grid

- Keep the existing "only one expanded card at a time" interaction model.
- Change the collapsed class card list container from a single-column stack to a responsive grid.
- Breakpoints:
  - Mobile: 1 column
  - Medium screens: 2 columns
  - Extra-large/desktop: 3 columns
- The expanded card content remains inside each card so edit behavior stays familiar.

This reduces vertical scrolling without introducing a second navigation model.

### 3. Review History Ordering and Timestamp

- Preserve backend ordering by `created_at DESC, id DESC`.
- Explicitly display a "生成时间" field based on `lesson.created_at`.
- Keep "课程日期" available as a separate metadata field when useful, because it represents class date rather than document generation time.

This makes the existing sort rule legible to users and resolves the perception that history is not sorted by generation time.

### 4. Review History Grid and Pagination

- Replace the single table with cards that surface:
  - Topic/title
  - Subject
  - Grade
  - 课程日期
  - 生成时间
  - PDF status
  - Existing actions: continue feedback, preview, download, delete
- Use a responsive grid:
  - Mobile: 1 column
  - Large screens: 2 columns
  - Extra-large screens: 3 columns if space allows within the existing page width
- Default page size: 12 items.
- Paginate client-side using the already-fetched lessons list.
- Reset to page 1 when the history list reloads after generation or deletion.

This directly addresses the long-page problem while preserving the existing actions and data contract.

## Data Flow

### Credit Center

1. Fetch ledger items as today.
2. Apply the selected filter.
3. Slice the filtered list into the current page window.
4. Render the current page and pagination controls.

### Review History

1. Fetch lessons from `/api/lessons`.
2. Trust backend ordering contract of newest-first by `created_at DESC`.
3. Slice the lessons array into the current page window.
4. Render cards with both lesson date and generation timestamp.
5. Reset pagination on reload-triggering actions such as delete or successful creation.

## Error Handling

- Existing fetch/loading/empty/error states remain unchanged.
- Pagination controls should hide or disable themselves when only one page exists.
- If the current page becomes out of range after delete or filter change, snap back to page 1.

## Testing Strategy

- Add or update frontend source-based tests for:
  - Credit center pagination constants/state and paginated rendering hooks.
  - Class management grid classes showing multi-column layout.
  - Review history source containing generation timestamp display and client-side pagination state.
- Run the frontend test suite plus TypeScript check.

## Acceptance Criteria

- Credit center "最近流水" no longer renders an unbounded long visible list and shows 10 filtered items per page.
- Class management shows three class cards per row on desktop-sized screens.
- Review history visually communicates newest generated documents first by showing generation time.
- Review history no longer renders as one long single-column/table block and instead paginates a multi-card layout.
- Existing actions for preview, download, delete, and continue feedback still work.
