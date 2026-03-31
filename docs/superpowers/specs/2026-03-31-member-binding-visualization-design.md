# Member-Centric Teaching Binding Visualization Design

## Goal

Make the existing `账号审批` page show whether each member has been successfully unified into the newer SaaS master-data model.

The page should answer three questions without requiring the user to jump into multiple modules:

- does this member correspond to a mini-program teacher identity?
- which SaaS classes is this member currently responsible for?
- are wrong-question mappings under this member healthy, incomplete, or waiting for review?

This design is intentionally read-only for the first step. It adds visibility, not new editing workflows.

## Product Decision

The user confirmed the desired model:

- mini-program teachers should map to SaaS members instead of remaining a separate identity system
- mini-program classes and SaaS classes should converge on the same canonical class records
- the SaaS database is the source of truth for member, teacher, and class identity
- the `账号审批` page should present this information from the member perspective

## Scope

This project adds member-centric binding visibility to the existing `账号审批` page.

In scope:

- show a `教学绑定` summary block on each member card
- summarize mini-program teacher identity binding status for that member
- summarize class responsibility for that member
- summarize wrong-question mapping health for records attributable to that member

Out of scope for this step:

- editing aliases directly inside the approval page
- editing wrong-question mappings inside the approval page
- introducing a second full mapping-management UI inside the approval page
- changing mini-program APIs or storage shape in this task

## Why This Approach

### Recommended: Read-Only Summary Inside Approval Cards

Add one compact `教学绑定` section per member card inside `账号审批`.

Why this is the recommended approach:

- matches the user's request to visualize the state in the approval page itself
- keeps the page focused on member oversight instead of turning it into a second mapping console
- reuses existing canonical fields such as `teacher_user_id`, `class_id`, and `mapping_status`
- is the smallest safe change that surfaces whether the master-data model is actually working

### Alternative: Separate Detail Drawer

Add a summary line on each member and open a deeper detail drawer.

Why not now:

- higher UI and state-management complexity
- unnecessary for the first visibility pass

### Alternative: Link Out To Master Data Only

Show a status badge in approval and force users to open `主数据映射` for detail.

Why not:

- too weak for the user's stated goal
- still requires cross-page mental reconstruction

## Current System Facts

The current codebase already contains the foundation needed for this view:

- SaaS users are canonical teacher or member identities
- class responsibility is already modeled through `classes.teacher_user_id`
- wrong-question normalization already outputs canonical fields such as:
  - `teacher_user_id`
  - `teacher_display_name`
  - `class_id`
  - `class_display_name`
  - `mapping_status`
- wrong-question mappings can degrade from `mapped` to `needs_review` when class-teacher responsibility changes

This means the missing piece is visibility, not the underlying identity model.

## UI Design

### Placement

Inside each member card on the existing `账号审批` page, add a new section titled `教学绑定`.

This section appears below the role controls and uses the same card styling language already used by the workspace UI.

### Fields Shown

Each member card should display three read-only rows.

#### 1. Mini-Program Teacher

Display whether the system can currently recognize this member as a mini-program teacher identity.

Expected labels:

- `已绑定` when the member has evidence of teacher identity binding
- `未绑定` when no teacher identity evidence exists

This is not a new editable binding switch. It is a health indicator derived from the current master-data layer.

#### 2. Responsible Classes

Display the classes whose canonical `teacher_user_id` points to this member.

Presentation:

- summary count such as `2 个班级`
- class names listed inline or stacked beneath the label
- if the list is long, show the first three names and a `+N` remainder indicator

#### 3. Mapping Status

Display a high-level health status for wrong-question mappings attributable to this member.

Visible states:

- `正常`
- `待复核`
- `未完成`

Optional secondary text may show a compact breakdown such as `待复核 1 / 未映射 2` if the data is available without clutter.

## Status Rules

### Mini-Program Teacher Status

For this first version, a member is treated as `已绑定` when at least one of the following is true:

- the member currently owns at least one class and wrong-question records mapped through that class resolve to this member as `teacher_user_id`
- the member appears in persisted wrong-question mappings as the canonical `teacher_user_id`

Otherwise the member is `未绑定`.

This rule is deliberately pragmatic. It avoids inventing a new binding table before visibility exists.

### Mapping Health Status

For each member:

- `待复核` if any relevant wrong-question mapping is currently `needs_review`
- `未完成` if there is no `needs_review`, but there are still relevant `unmapped` or `ambiguous` records, or the member has classes but no recognizable teacher identity binding
- `正常` if the member has class and teacher identity evidence and all relevant mappings are stable

Priority order is:

1. `待复核`
2. `未完成`
3. `正常`

## Data Requirements

The approval page currently loads member records from `/api/admin/users`.

This design requires the page to receive additional per-member summary data, either by:

- extending the existing admin users payload, or
- adding a dedicated summary endpoint consumed alongside the existing users request

Recommended shape:

```json
{
  "user_id": 12,
  "mini_teacher_bound": true,
  "responsible_classes": [
    { "id": 7, "name": "六年级 2 班" },
    { "id": 9, "name": "初一 1 班" }
  ],
  "mapping_summary": {
    "status": "needs_review",
    "mapped_count": 8,
    "needs_review_count": 1,
    "unmapped_count": 2,
    "ambiguous_count": 0
  }
}
```

### Recommendation On API Shape

Prefer a dedicated read-only endpoint instead of bloating `/api/admin/users`.

Recommended endpoint:

- `GET /api/admin/member-binding-summary`

Return value:

- an array keyed by `user_id`
- one summary object per member

Why this is preferred:

- keeps approval identity data separate from role-management payloads
- avoids mixing unrelated concerns into the existing user list contract
- allows future expansion without repeatedly mutating the user API

## Backend Behavior

The summary endpoint should:

- list all relevant organization members shown in approval
- derive responsible classes from canonical SaaS `classes.teacher_user_id`
- derive wrong-question mapping counts from the master-data mapping store
- compute the member-level summary status using the priority rules above

It must not mutate any mapping or alias state.

## Frontend Behavior

The approval page should:

- request the summary payload alongside the current users list
- merge the summary by `user_id`
- render the `教学绑定` section on each member card
- degrade gracefully if the summary request fails

If the summary API fails:

- keep the approval page usable for role operations
- show a small inline warning in the `教学绑定` block such as `教学绑定摘要加载失败`
- do not block approval actions

## Empty And Edge Cases

### Member With No Classes

Display:

- `负责班级：0 个班级`
- no class chips
- mapping status most likely `未完成` unless the summary logic explicitly finds stable teacher-linked mappings

### Member With Classes But No Stable Teacher Identity Evidence

Display:

- class list normally
- `小程序老师：未绑定`
- overall status `未完成`

### Member With Historical Stale Mappings After Rebinding

Display:

- `待复核`
- optional secondary count showing how many records need review

This is important because the user specifically wants to know whether the cross-system one-to-one relationship is still intact.

## Testing Strategy

### Backend Tests

Add coverage for:

- member summary shows responsible classes derived from `teacher_user_id`
- member summary reports `mini_teacher_bound=true` when canonical mappings exist
- member summary reports `待复核` when any relevant mapping is `needs_review`
- member summary reports `未完成` when only unresolved states remain
- member summary stays read-only and requires staff authorization

### Frontend Tests

Add coverage for:

- approval page renders the `教学绑定` block per member
- responsible classes display as member-scoped summary content
- `正常 / 待复核 / 未完成` labels render from summary data
- approval page remains usable when the summary request fails

## Risks

- inferring `mini_teacher_bound` from existing mapping evidence is a pragmatic approximation, not a perfect first-class binding table
- if approval currently loads many members, extra summary aggregation must remain efficient
- if the summary definition is too strict, members may appear `未完成` more often than expected; the status rules should therefore stay explicit and test-covered

## Success Criteria

This work is successful when:

- the approval page lets the user see, per member, whether cross-system teacher identity is effectively unified
- the same page shows which canonical SaaS classes that member owns
- the same page signals whether wrong-question mappings are stable or need intervention
- users no longer need to infer teacher or class binding health indirectly from the smart wrong questions page alone