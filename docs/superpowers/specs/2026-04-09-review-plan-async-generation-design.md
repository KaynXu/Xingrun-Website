# Review Plan Async Generation Design

## Goal

把“生成复习计划”从同步接口改成异步任务流，保留 `n1n/gpt-5.4` 的生成质量，同时解决线上长时间转圈、重复点击触发 `409`、首个请求最终落成 `500` 的问题。

本次设计只覆盖单节复习计划与月度计划的生成链路，不扩展到班级反馈、咨询解析等其它 AI 功能。

## Confirmed Scope

- 单节复习计划生成改为异步。
- 月度复习计划生成改为异步。
- 单节复习计划继续复用现有 `lessons` 数据模型作为“任务壳”，不新增第二套单节 review job 表。
- 月度计划允许新增一个最小独立任务表，不复用 `lessons`。
- 前端在提交后立即得到任务记录并进入“生成中”状态，而不是一直等待同一个 HTTP 请求。
- 后端在后台继续调用 `gpt-5.4`，成功后写回 plan / pdf，失败后写回失败状态与错误信息。
- 当前临时止血用的“结构化生成回退到 `gpt-4o`”逻辑只作为短期保护；异步方案落地后应移除，恢复复习计划链路默认使用配置里的高质量模型。

## Existing Context

- 当前 `POST /api/review-plans` 在同一个请求里完成：
  - 读取文本或文件
  - 调 `parse_and_generate_plan()`
  - 生成 PDF
  - `save_lesson()`
- 当前 `POST /api/monthly/generate` 也在单请求里完成 AI + PDF。
- 当前前端 `frontend/src/App.tsx` 生成页是同步等待 `apiFetch('/api/review-plans')` 返回。
- 当前项目已有 `record_status='pending'` 的 lesson 语义，课程日历页也已经识别待补录/待完成记录，因此复用 lesson 作为任务壳比新增新表更符合现状。
- 当前项目已经有“任务对象 + 详情轮询式 hydration”的参考实现，最接近的是班级反馈任务流。

## Recommended Approach

采用“lesson 记录先落库，后台线程继续生成，前端轮询 lesson 状态”的方案。

### Why This Approach

- 不引入新表，侵入最小。
- lesson 本来就是最终业务对象，异步完成后无需再做 job -> lesson 的二次搬运。
- 前端现有复习计划列表已经天然能承载“生成中 / 失败 / 完成”的记录展示。
- 后端只需要在现有保存 lesson 的链路上补状态迁移，不需要重做权限模型。

## Data Model Changes

### Lesson Status Expansion

`lessons.record_status` 统一承担异步任务状态，新增并明确以下语义：

- `pending`
  - 记录已创建，后台 AI/PDF 任务尚未完成
- `ready`
  - AI 与 PDF 已成功完成，记录可正常查看和下载
- `failed`
  - 后台任务失败，记录保留以便前端展示失败原因与触发重试

如果当前库里 `record_status` 还没有稳定写入上述值，需要在 `lesson_manager.py` 中统一补齐：

- 创建 pending lesson helper
- 异步成功回写 helper
- 异步失败回写 helper

### Lesson Failure Metadata

为避免失败后前端只能看到空白记录，lesson 需要补一个轻量错误字段，推荐新增：

- `generation_error TEXT NOT NULL DEFAULT ''`

用途：

- `pending` 时为空
- `failed` 时写用户可见错误消息
- `ready` 时清空

不新增复杂的失败堆栈字段；详细异常仍写 server log。

## Backend Design

### 1. Create Pending Lesson First

`POST /api/review-plans` 改为：

1. 校验请求参数、权限、班级范围
2. 读取输入内容
3. 立即创建一条 lesson：
   - `summary` 保存用户提交的原始课堂总结
   - `subject / grade / topic / weak_points / class_id / date` 正常写入
   - `plan={}` 或最小占位
   - `pdf_path=''`
   - `record_status='pending'`
   - `generation_error=''`
4. 启动后台线程继续执行 AI + PDF
5. 立即返回 `202`

返回体至少包含：

- `id`
- `success`
- `status='pending'`

### 2. Background Worker Responsibilities

后台线程按 lesson_id 工作，流程如下：

1. 重新读取 lesson，确认仍处于 `pending`
2. 重新 claim 该机构 AI 并发锁与 request identity
3. 执行 `parse_and_generate_plan()`
4. 生成单节 PDF
5. 成功后回写：
   - `plan`
   - `pdf_path`
   - `record_status='ready'`
   - `generation_error=''`
6. 失败后回写：
   - `record_status='failed'`
   - `generation_error='用户可见错误'`

后台线程必须在 `finally` 中释放：

- `_AI_ORGANIZATION_IN_FLIGHT`
- `_AI_REQUEST_IN_FLIGHT`

否则失败后会把整个机构的下一次生成卡死。

### 3. Monthly Plan Async Flow

月度计划不复用 lesson 表，因为它当前没有 lesson 对象承载。这里建议新增一个最小独立任务对象，而不是强塞 lesson：

- 新增 `monthly_plan_jobs`

字段建议：

- `id`
- `organization_id`
- `user_id`
- `month_str`
- `status` (`pending` / `ready` / `failed`)
- `pdf_filename`
- `generation_error`
- `created_at`
- `updated_at`

理由：

- 月度计划不是单条 lesson，复用 lesson 会制造歧义
- 但它也不值得引入通用 AI job 系统，本轮保持单一用途表即可

接口改为：

- `POST /api/monthly/generate`
  - 创建 `pending` job
  - 返回 `202 + job_id`
- `GET /api/monthly/jobs/<id>`
  - 返回状态、失败原因、文件名
- `GET /api/monthly/<filename>`
  - 继续沿用现有文件下载能力

### 4. Model Selection

异步化完成后，复习计划与月度计划恢复使用当前配置里的默认聊天模型。

也就是：

- 如果线上配置是 `n1n/gpt-5.4`，后台线程就继续跑 `gpt-5.4`
- 当前 `_get_structured_generation_model()` 的 `gpt-4o` 回退逻辑应移除

这样“质量”和“可用性”分别由不同手段保证：

- 质量：继续用高质量模型
- 可用性：通过异步任务而不是同步超时

## Frontend Design

### Single Lesson Generation Page

生成按钮点击后：

1. 提交 `POST /api/review-plans`
2. 收到 `202` 后不再停留在整页 loading
3. 立即跳回或刷新复习计划列表
4. 高亮当前新建记录，并显示“正在生成复习资料...”

前端需要能识别 lesson 的三种状态：

- `pending`
  - 显示生成中 badge
  - 禁用下载 PDF
  - 提示“可离开页面，完成后会出现在列表中”
- `failed`
  - 显示失败 badge
  - 展示 `generation_error`
  - 提供“重新生成”按钮
- `ready`
  - 现有展示逻辑不变

### Polling Strategy

前端不需要全局长轮询，只在以下场景轮询：

- 用户刚提交生成后
- 列表中存在最近创建的 `pending` 记录时

策略建议：

- 每 3 秒拉一次 `/api/review-plans`
- 当目标记录变成 `ready` 或 `failed` 后停止
- 最长轮询 10 分钟；超时后仅停止前端轮询，不影响后台继续生成

### Retry Behavior

失败记录允许重试，但不直接复用旧请求：

- 单节计划：新增 `POST /api/review-plans/<id>/retry`
- 月度计划：新增 `POST /api/monthly/jobs/<id>/retry`

重试行为：

- 仅允许 `failed` 状态重试
- 重试时把状态重置为 `pending`
- 清空旧 `generation_error`
- 后台重新启动生成线程

## Error Handling

### User Visible Errors

前端只显示简洁错误：

- `AI 生成失败，请稍后重试`
- `PDF 生成失败，请稍后重试`
- `当前机构已有 AI 请求正在处理中，请稍后再试`

技术堆栈、三方响应体、traceback 只写日志，不直接回前端。

### Duplicate And Concurrency Rules

仍保留现有信用扣费与机构级并发保护，但 claim 时机从“接口主线程”改到“后台线程实际开始执行时”。

这样可以避免：

- 创建 pending lesson 成功，但主线程长期占着 organization lock
- 用户看见 pending 记录，却所有后续请求都被机构锁拒绝

### Restart Safety

本轮不做跨进程任务恢复系统。服务重启期间遗留的 `pending` 任务按以下规则处理：

- 服务启动时扫描过久的 `pending`
- 超过阈值（例如 15 分钟）且没有结果的，统一标成 `failed`
- `generation_error='服务重启导致任务中断，请重试'`

这比悄悄永远 pending 更可控。

## Testing Strategy

至少覆盖以下回归：

### Backend

- `POST /api/review-plans` 返回 `202`，并先创建 `pending` lesson
- 后台任务成功后 lesson 变为 `ready`
- 后台任务失败后 lesson 变为 `failed` 且写入 `generation_error`
- 失败 lesson 可以 retry 并最终成功
- 服务启动时会把超时 pending 标成 failed
- 月度 job 创建 / 查询 / 失败 / 重试

### Frontend

- 生成后不再一直卡在同步 loading
- 存在 pending lesson 时会轮询并在 ready 后停止
- failed lesson 会显示错误与 retry 入口
- retry 成功后 UI 由 failed -> pending -> ready

## Migration And Rollout

### Implementation Order

1. 后端补 lesson async 状态与回写 helpers
2. 单节复习计划接口改为 `202 + background worker`
3. 前端接入 pending / failed / polling
4. 月度计划 job 表与接口
5. 移除 `_get_structured_generation_model()` 的 `gpt-4o` 回退逻辑

### Rollout Safety

在异步链路和轮询 UI 都已就绪之前，不要先移除 `gpt-4o` 止血逻辑。

正确顺序应为：

1. 先让异步链路完整跑通
2. 验证线上 `pending -> ready/failed` 正常迁移
3. 再移除临时回退逻辑，让复习计划恢复走 `gpt-5.4`

## Non-Goals

- 不把所有 AI 能力统一抽象成通用任务中心
- 不在本轮引入 Celery、Redis、消息队列等重型基础设施
- 不改动班级反馈生成链路
- 不顺手重构复习计划 PDF 模板或 prompt 内容
