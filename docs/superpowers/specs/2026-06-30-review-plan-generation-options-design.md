# Review Plan Generation Options Design

Date: 2026-06-30

## Context

The review plan generator currently behaves as if every single lesson should use the same fixed spaced-review schedule: day 1, day 2, day 7, day 14, and day 30. That assumption is embedded beyond the UI. It appears in the workflow scope planner, time allocator labels, prompt copy, revision instructions, schema expectations, and quality gate checks.

Teachers now need two additional generation controls:

- Choose how many review days the generated PDF should contain, including compressing a full lesson into one day.
- Add one-off requirements for this generation, such as "lighter workload", "exam sprint", "mostly choice diagnostics", or "more basic".

The product must avoid fake UI support. If the teacher selects one day, the backend workflow, prompts, validation, quality gate, PDF rendering, trace, and version history must all understand that choice.

## Goals

- Let teachers choose a review schedule from common presets and custom day offsets.
- Let teachers add one-off generation requirements that are passed into the LLM prompt chain.
- Store generation settings per review plan version so different regenerations are explainable and reproducible.
- Keep existing old versions compatible by treating missing options as the current standard five-day schedule.
- Replace the current regenerate confirmation with a real settings dialog that defaults to the previous version's settings and allows changes.
- Keep quality protection active for every schedule mode instead of bypassing it when the plan is not five days.

## Non-Goals

- No saved teacher prompt templates in the first implementation.
- No arbitrary natural-language date parsing such as "next Monday and Friday".
- No side-by-side comparison of different schedule outputs.
- No automatic scoring of whether free-text teacher requirements were fully followed.
- No changes to credit pricing in this first version.

## Product Behavior

### Create Flow

The existing "生成复习文档" modal remains a one-step flow. The modal adds a "生成设置" section below "教学信息".

Schedule choices:

- 标准复习: `review_days=[1,2,7,14,30]`; this remains the default.
- 压缩 1 天: `review_days=[1]`; the whole lesson is compressed into one printable review day.
- 连续每日: teacher enters `N`; the system generates `review_days=[1..N]`.
- 自定义日期点: teacher enters comma-separated positive integers such as `1,3,5,10,21`.

The same section includes an optional "本次生成要求" textarea. This text affects only the current version.

The right-side "生成前检查" summary shows:

- selected schedule label;
- actual review days;
- whether one-off requirements are present.

### Regenerate Flow

Regeneration no longer uses `window.confirm`.

When the teacher clicks regenerate:

- open a "重新生成设置" dialog;
- prefill the latest current version's `generation_options`;
- if the current version has no saved options, use the standard five-day default;
- allow the teacher to edit schedule mode, days, and one-off requirements;
- confirm that this creates a new version and consumes one generation credit.

On submit, the app creates a new version. Ready old versions remain previewable and downloadable while the new version is generating.

### Version Display

The list and detail page should expose a short generation settings summary:

- 标准 5 次;
- 压缩 1 天;
- 连续 7 天;
- 自定义 1,3,7.

The detail version history should show the summary per version so quality differences across regenerations can be investigated without reading backend logs.

## Data Model

Add `generation_options_json` to `review_plan_versions`.

Canonical object:

```json
{
  "schedule_mode": "standard",
  "review_days": [1, 2, 7, 14, 30],
  "daily_count": null,
  "user_requirements": "",
  "source": "create"
}
```

Supported `schedule_mode` values:

- `standard`
- `compressed`
- `daily`
- `custom`

Normalization rules:

- Missing options default to `standard` with `[1,2,7,14,30]`.
- `compressed` always normalizes to `[1]`.
- `daily` requires a positive integer `daily_count` and normalizes to `[1..daily_count]`.
- `custom` requires a comma-separated or array input of positive integers, sorted and deduplicated.
- Day numbers must be positive integers.
- A conservative first limit is 30 generated review days; this matches the previous furthest day and prevents runaway PDFs.
- `user_requirements` is trimmed and length-limited before storage.

This field belongs to the version, not the lesson, because each regeneration may use different teacher requirements.

## API Design

### Create Review Plan

`POST /api/review-plans` accepts:

```json
{
  "subject": "数学",
  "class_id": 1,
  "topic": "分式方程",
  "date": "2026-06-30",
  "summary_text": "...",
  "weak_points": "...",
  "same_lesson_materials": "...",
  "generation_options": {
    "schedule_mode": "compressed",
    "review_days": [1],
    "user_requirements": "适合明天考试前冲刺，题量少一点"
  }
}
```

For multipart upload, send `generation_options` as a JSON string field.

The backend normalizes and stores the object before starting the async worker.

### Regenerate Review Plan

`POST /api/review-plans/:lesson_id/regenerate` accepts the same `generation_options` object.

Fallback behavior:

1. If the request includes options, use them.
2. Else if the current version has saved options, reuse them.
3. Else use the standard five-day default.

The response includes the new `version_id` and the normalized generation options.

### Read APIs

List and detail serializers include `generation_options` and a `generation_summary` on current and historical versions.

Old versions without the column or with an empty JSON value serialize as the standard five-day default.

## Workflow Design

`ReviewPlanInput` gains:

- `schedule_mode`
- `review_days`
- `user_requirements`

`WorkflowContext` records the normalized generation options in `node_outputs`, with a privacy-aware summary:

- `schedule_mode`
- `review_days`
- `has_user_requirements`
- a short `user_requirements_preview` only if needed for debugging.

### Scope Planner

`scope_planner` uses `review_input.review_days` instead of returning `[1,2,7,14,30]`.

Schedule intent affects scope:

- `standard`: repeat whole-lesson coverage with different emphasis across days.
- `compressed`: cover the full lesson in day 1 with tighter prioritization.
- `daily`: split modules across consecutive days and preserve cumulative review.
- `custom`: map available modules across the provided day offsets.

### Time Allocator

`time_allocator` labels days from mode and day number.

Examples:

- `compressed`: `当天压缩复盘`
- `daily` day 3: `第 3 天每日复习`
- `custom` day 10: `第 10 天回看`
- known standard labels remain for 1, 2, 7, 14, 30 when in standard mode.

### Prompt Bundle And Generator

The task-generation prompt stops saying "固定使用 5 个复习节点". It instead says:

```text
必须且只能生成这些复习日：{review_days}
复习节奏模式：{schedule_mode_label}
```

Teacher requirements are injected as a distinct section:

```text
【老师本次生成要求】
{user_requirements}

这些要求必须尽量遵守；如果与复习日结构、可打印性、题目完整性、事实准确性冲突，以结构和质量要求优先。
```

Prompt priority:

1. System safety, factuality, printable structure, and schema requirements.
2. Required review days from `generation_options`.
3. Teacher one-off requirements.
4. Default style preferences.

### Revision

Revision instructions must use the required `review_days` from context. They must not tell the model to restore day 1, 2, 7, 14, and 30 unless that is the chosen schedule.

### Quality Gate

`review_single_lesson_plan` accepts required review days.

It checks:

- every required day exists;
- no unexpected day appears unless explicitly allowed by normalization;
- each day has printable content;
- math plans still have enough unique questions;
- compressed one-day plans have stronger density expectations because there is no later day to carry missing coverage;
- `full_review_topics` still has meaningful granular coverage.

The first version does not use a strict automated judge for `user_requirements` adherence. Free-text requirements are too open-ended, and strict matching would cause false failures. If real traces show recurring non-compliance, add a later LLM reviewer for "requirement adherence".

## PDF And Rendering

The PDF renderer should render whatever `plan.days` contains after schema normalization. The implementation must still verify:

- one-day compressed plans do not produce empty pages;
- daily plans with 7 or more days have acceptable page count and section breaks;
- custom day labels and actual dates render correctly;
- download filename remains short and stable.

No PDF template fork is planned.

## Observability

Langfuse and local `review_plan_runs` should capture:

- schedule mode;
- review days;
- whether teacher requirements were provided;
- prompt bundle version;
- quality score and issues.

Do not expose secrets or sensitive large text in logs. The full teacher requirements can live in the version JSON because it is part of the user's generated artifact metadata, but trace summaries should prefer presence flags and short previews.

## Implementation Plan Shape

The implementation will likely touch more than eight files. This is necessary complexity because the current fixed five-day assumption is cross-layer.

Expected file groups:

- Frontend create/regenerate UI and tests.
- Backend API parsing, normalization, serializers, and version storage.
- Workflow schema, state, scope planner, time allocator, prompt bundle, generator, revision, and quality gate.
- Prompt markdown/yaml files.
- Backend and workflow tests.
- Handoff update.

Keep the implementation incremental:

1. Add normalization and storage with old-data fallback.
2. Add API payload support.
3. Parameterize workflow and quality gate.
4. Add frontend controls and regenerate dialog.
5. Add focused tests and a PDF smoke proof.

## Test Matrix

Backend API:

- create with omitted options defaults to standard five-day schedule;
- create with compressed one-day options stores `[1]`;
- multipart create stores options from JSON string;
- regenerate defaults to previous version options;
- regenerate accepts edited options;
- invalid custom days return a clear 400.

Workflow:

- generated plan accepts `[1]`;
- generated plan accepts `[1,2,3,4,5,6,7]`;
- generated plan accepts `[1,3,5,10]`;
- revision prompt preserves required days;
- quality gate no longer fails non-standard plans for missing 14 or 30 unless required.

Frontend:

- create payload includes generation options;
- right summary reflects selected schedule;
- regenerate dialog pre-fills current version options;
- edited regenerate options are submitted;
- old versions without options display "标准 5 次".

PDF smoke:

- compressed one-day plan renders a nonblank PDF;
- standard five-day plan still renders as before;
- custom schedule shows correct day labels and dates.

## Risks

- UI density: the create modal is already heavy. Keep schedule controls compact and place advanced custom input behind the custom mode.
- Prompt obedience: teacher free-text requirements may not always be followed. Trace and version storage make failures diagnosable, and a later adherence reviewer can be added if needed.
- Quality gate tuning: compressed plans need enough density without making them impossible to pass.
- Old data compatibility: serializers and regenerate fallback must not assume every version has generation options.
- Long custom schedules: cap the first version to 30 days to avoid runaway PDF size and cost.

## Open Decisions

All product decisions for this design are currently resolved:

- Support both one-day compression and daily plans.
- Support both presets and custom day offsets.
- Keep teacher requirements one-off in the first version.
- Regeneration defaults to prior settings and allows edits.
- Implement the complete chain, not a frontend-only shortcut.
