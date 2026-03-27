# Course Calendar Design

- Date: 2026-03-28
- Scope: Replace the current `题库浏览` workspace tab with a bright Starain-style `课程日历` page for demo-quality visual presentation.
- Status: Approved in terminal brainstorming on 2026-03-28

## Context

The public Starain landing and legal pages have already moved to a white, blue-cyan, bright AI Edu Platform direction. The workspace shell is being brought into the same visual language in a separate effort. The next page-level change should stay inside that workspace track and avoid broad site-wide redesign.

The current logged-in SPA keeps page switching inside `frontend/src/App.tsx` with local state. One of those tabs is `题库浏览`, backed by `/api/quiz`. That tab is no longer useful for the current product story. The replacement should feel like an institution-facing scheduling surface, but the first version is explicitly a visual demo, not a full scheduling product.

## Goals

1. Replace the `题库浏览` tab with a shorter, clearer `课程日历` tab.
2. Make the page feel like a real scheduling workspace while preserving the bright Starain workspace direction.
3. Use a recognizable calendar view instead of a generic list or analytics dashboard.
4. Keep the page compatible with later linkage to `添加课程`.
5. Avoid mixing class-creation work into this page.

## Non-Goals

1. No true scheduling editor in this iteration.
2. No new backend scheduling model such as `start_time`, `end_time`, recurrence rules, or teacher assignment per lesson.
3. No `新增班级` entry on this page.
4. No restoration or redesign of the quiz/question-bank experience.
5. No backend API changes required for this first pass.

## Chosen Direction

Use a `课程日历` page with a week-view calendar as the primary visual. The center of the page is a Monday-to-Sunday grid. The vertical axis uses three visual time bands, `上午`, `下午`, and `晚间`, to create a calendar feeling without pretending the backend already stores precise times.

This page is a demo-grade institution view, not a source-of-truth scheduler. The grid should look credible, but its placement logic should remain honest about the current data model.

## Information Architecture

The page has three layers:

1. Top control bar
   - Page title: `课程日历`
   - Week switcher: previous week, current week label, next week
   - Lightweight filters: teacher filter and class filter

2. Main calendar surface
   - Seven columns for Monday through Sunday
   - Three rows for `上午`, `下午`, `晚间`
   - Lesson cards placed inside cells for visual scheduling density
   - Empty or lightly occupied cells should still feel intentional, not broken

3. Right-side support rail
   - `本周老师负载`
   - `待补录课程`
   - `班级状态`

The right rail is supportive only. The calendar stays dominant.

## Data Mapping

The first version should reuse existing authenticated APIs:

1. `GET /api/classes`
   - Source of class name, subject, grade, teacher name, and lesson count

2. `GET /api/lessons`
   - Source of lesson date, topic, subject, grade, and `class_id`

The frontend should join lesson records with class records in memory.

Because the current schema does not store start or end times, the week grid bands are visual groupings rather than precise scheduling truth. If needed for visual density, the page may use deterministic demo placement rules derived from existing records rather than inventing a new backend model.

## Interaction Model

This page stays low-commitment in the first pass:

1. Week navigation updates the visible week presentation.
2. Teacher and class filters narrow the visible cards.
3. Lesson cards may show hover affordance and light motion.
4. Clicking a day cell or lesson card should be visually framed as a future link to `添加课程`, but full cross-page prefill is not required yet.

## Visual Design Rules

1. Keep the bright Starain workspace system: white surfaces, sky/cyan accents, soft shadows, slate text.
2. The calendar grid should feel product-grade, not like a marketing mockup.
3. The page should avoid decorative noise and keep motion restrained.
4. The right rail should support scanning, not compete with the calendar.
5. The naming should stay concise. Use `课程日历`, not `老师课程表`.

## Dashboard Consistency Adjustment

Since the `题库浏览` tab is being removed, the dashboard should no longer emphasize a question-bank primary action or stat in the same role. The current `题库题目` stat card should be replaced with a calendar- or class-relevant metric such as:

- `本周排课`
- `活跃班级`

The exact label can be finalized during implementation, but the dashboard should stay semantically aligned with the new navigation.

## Implementation Boundaries

This work should stay focused on the workspace page layer:

1. Update the page enum, sidebar item, page title map, and conditional render path.
2. Replace the current question-bank component with a new course-calendar component.
3. Reuse existing workspace shell styling patterns already introduced in the bright Starain workspace effort.
4. Do not add class-creation UI here.
5. Do not refactor unrelated backend routes.

## Verification

Because this iteration is frontend-only in intent, success is verified by:

1. `frontend/npm run lint`
2. `frontend/npm run build`

No additional backend test expansion is required unless implementation later crosses into API behavior changes.

## Risks and Constraints

1. The lack of real time-slot fields means the page must avoid implying exact scheduling fidelity.
2. Existing APIs are broad enough for the page, but later real scheduling work will need a dedicated model.
3. `frontend/src/App.tsx` is already a large file; implementation should keep changes bounded and avoid opportunistic unrelated refactors.

## Acceptance Criteria

1. The sidebar no longer shows `题库浏览`.
2. The new tab label is `课程日历`.
3. The new page is visually built around a weekly calendar grid.
4. The page preserves the bright Starain workspace style.
5. The page does not include `新增班级`.
6. The page reads as an institution scheduling surface and leaves a clear path to later `添加课程` linkage.
