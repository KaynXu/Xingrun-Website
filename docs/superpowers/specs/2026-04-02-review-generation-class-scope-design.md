# Review Generation Class Scope Design

## Goal

在复习记录页面补上班级约束，确保生成复习记录时必须选择班级，并且老师账号只能看到自己负责班级生成出的复习记录。`owner` 和 `admin` 保持全量可见。

## Confirmed Scope

- 复习生成页中的“班级”字段改为必选。
- `member` 账号只能从自己负责的班级中选择。
- `member` 账号只能查看、打开、下载、删除自己负责班级下的复习记录。
- `owner`、`admin`、`super_owner` 可以查看全部复习记录，并保留全部班级选择能力。
- 权限判断继续基于已有的 `user_classes` 关系，不新增 lesson 级别的老师快照字段。

## Existing Context

- 前端复习生成页由 `frontend/src/App.tsx` 中的 `LessonInput`、`ReviewDocumentHistory`、`ReviewGenerationPage` 组成。
- 班级列表接口 `/api/classes` 已经按用户角色过滤，`member` 只能拿到自己负责的班级。
- 复习记录列表接口 `/api/lessons` 当前仍返回全量数据，详情、删除、PDF 访问也缺少相同的班级权限兜底。
- 课程/复习记录与班级的关联已经通过 `lessons.class_id` 存在；老师与班级的归属通过 `user_classes` 存在。

## Recommended Approach

采用“前端必选 + 后端强校验 + 记录读取全链路按班级权限过滤”的方案。

### Why This Approach

- 只改前端不能防止绕过接口直接访问他人记录。
- 继续沿用 `class_id -> user_classes` 的关系可以复用现有数据结构，避免新增冗余字段。
- 前端和后端同时收口后，列表页、详情、PDF、删除都会遵守同一套权限规则。

## Role Rules

### `super_owner` / `owner` / `admin`

- `/api/classes` 可看到全部班级。
- 可创建任意班级的复习记录。
- 可查看全部复习记录列表。
- 可访问任意复习记录详情、PDF 预览、PDF 下载、删除。

### `member`

- `/api/classes` 仅返回自己负责的班级。
- 创建复习记录时必须提交有效 `class_id`，且该班级必须属于自己负责范围。
- 仅能看到 `lessons.class_id` 属于自己负责班级的复习记录。
- 仅能访问、下载、删除自己负责班级的复习记录。
- 对没有 `class_id` 的历史复习记录视为不可访问。

## Frontend Design

### Review Generation Composer

- `LessonInput` 中的班级选择保持下拉模式，但从“可不选”改为“必选”。
- 提交前如果未选择班级，直接阻止生成并显示明确错误提示。
- `member` 如果没有可选班级，页面保留表单结构，但生成按钮应因无班级可选而无法成功提交，并显示“当前账号未分配负责班级”之类的提示。
- 选择班级后，保留现在“自动带出科目”的行为。

### Review History

- `ReviewDocumentHistory` 继续调用 `/api/lessons`，不在前端做额外权限过滤。
- 前端只负责展示接口返回的结果，权限以服务端为准。

## Backend Design

### Shared Permission Helper

新增或复用一个围绕 lesson 的访问判断，规则如下：

- 高权限角色直接放行。
- `member` 必须命中 `lesson.class_id in get_user_class_ids(user.id)`。
- `lesson.class_id` 为空时，`member` 一律不可访问。

### `GET /api/lessons`

- `owner`/`admin`/`super_owner` 维持现有全量返回。
- `member` 只返回自己负责班级对应的复习记录。
- 保留现有 `month`、`class_id` 查询参数行为，但最终结果仍要叠加用户权限过滤。

### `POST /api/lessons`

- 班级改为必传业务字段；缺失时返回 400。
- `member` 提交的 `class_id` 若不在自己负责班级内，返回 403。
- `class_id` 不存在时返回 404 或等价明确错误。
- 生成成功后仍按原流程写入 `lessons.class_id`。

### `GET /api/lessons/<id>`

- 加入基于 `class_id` 的访问控制。
- 无权限时返回 404，避免暴露记录存在性。

### `DELETE /api/lessons/<id>`

- 加入与详情一致的访问控制。
- `member` 只能删除自己负责班级的记录。

### PDF Routes

- `/api/pdf/<lesson_id>`
- `/api/pdf/download/<lesson_id>`

这两个路由也需要与 `GET /api/lessons/<id>` 一致的权限判断，避免通过直接访问文件链接绕过复习记录列表限制。

## Data Flow

1. 前端加载复习生成页，请求 `/api/classes`。
2. 服务端按用户角色返回班级列表。
3. 用户提交复习生成请求，必须带上 `class_id`。
4. 服务端校验当前用户是否有权为该班级生成记录。
5. 生成后的 lesson 持久化 `class_id`。
6. 历史列表、详情、PDF、删除均按 `class_id` 与当前用户负责班级关系做权限过滤。

## Error Handling

- 未选班级：返回 400，前端显示“请选择班级后再生成复习记录”。
- `member` 访问非本人负责班级记录：返回 404。
- `member` 提交越权 `class_id` 生成记录：返回 403。
- `member` 未绑定任何班级：前端显示不可生成原因；如果仍发起请求，后端返回 403。

## Testing Strategy

### Backend Tests

- 新增 `member` 只能获取自己班级 lesson 列表的测试。
- 新增 `member` 不能获取其他班级 lesson 详情的测试。
- 新增 `member` 不能删除其他班级 lesson 的测试。
- 新增 `member` 不能访问其他班级 PDF 预览/下载的测试。
- 新增 `member` 创建 lesson 时缺少 `class_id` 返回 400 的测试。
- 新增 `member` 为非本人班级创建 lesson 返回 403 的测试。
- 新增 `owner`/`admin` 仍可查看全部 lesson 的测试。

### Frontend Tests

- 新增复习生成页班级必选校验测试。
- 新增 `member` 账号仅加载自己班级选项的测试。
- 新增 `member` 无班级时显示禁止生成提示的测试。
- 保持历史列表直接消费后端结果，不增加前端重复过滤逻辑。

## Non-Goals

- 不改动班级分配模型。
- 不给 lesson 新增 `teacher_user_id` 冗余字段。
- 不处理历史无班级 lesson 的批量修复，只将其对 `member` 隐藏。

## Risks And Mitigations

- 历史上若存在较多未绑定班级的 lesson，`member` 会突然看不到这些记录。
  - 处理方式：按当前权限目标接受这一行为，后续如需要可再补历史数据修复。
- 若只拦列表不拦 PDF，会残留越权入口。
  - 处理方式：把详情、删除、PDF 路由统一纳入同一权限判断。

## Implementation Notes

- 优先在后端提取共享的 lesson 访问判断，避免多个接口各写一套条件。
- 前端改动尽量集中在 `LessonInput`，避免影响 `ReviewGenerationPage` 的现有交互结构。
