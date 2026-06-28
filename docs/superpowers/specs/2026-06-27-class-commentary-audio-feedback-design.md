# 课堂点评录音生成反馈包设计

## 状态

- 日期: 2026-06-27
- 阶段: design approved in conversation, pending implementation plan
- 目标页面: workspace `class-feedback-generation` tab
- 新业务名: `class-commentary`

## 背景

旧教师反馈 tab 已被清成空壳。新需求不是恢复旧的阶段课堂反馈, 而是建立一条新的课堂点评链路:

1. 老师下课前按班级名单逐个点名录音点评学生。
2. 网站上传录音并用 AI 转写。
3. 老师确认或修改转写文本。
4. 老师选择一个同事 `.skill` 风格。
5. 系统调用 AI API, 把确认后的课堂点评转成一整段可复制的反馈包。

录音转写和反馈生成都属于 AI 能力。程序只负责工作流, 存储, 权限, 文件, skill 扫描和 API 编排, 不手写复杂人名拆分或多次提及规则。

## 已确认决策

- 采用任务式工作流, 每次上传录音创建一个课堂点评任务。
- 必须先选择班级, 系统使用班级学生名单作为 AI 的合法姓名范围。
- 未在录音中被明确点名的学生不出现在结果里。
- 老师会人为规定按班级名单清楚点名, 不处理小名, 同音字, 重名歧义。
- 转写流程是两步: 先转写并展示文本, 老师确认或修改后再生成。
- 输出第一版只支持复制整段文本, 不接发送渠道。
- 输出是一整段反馈包, 按学生姓名分块。
- 每次生成前由老师选择一个同事风格 `.skill`。
- `.skill` 文件由用户通过 Codex 或服务器文件操作上传到服务器目录, 网站只扫描和展示, 不做 skill 上传管理。
- 新 API 命名使用 `class-commentary`, 不继续使用旧 `class-feedback`。
- 旧 `class-feedback` 业务代码和旧数据库表都要删除。
- 新 tab 可见 UI 必须使用 shadcn/ui 组件组合, 不使用现有 `workspaceCardClass`, `workspacePrimaryButtonClass`, `workspaceFieldClass` 等自定义 workspace UI helper 构建新界面。

## 非目标

- 不做逐学生卡片独立复制。
- 不做微信, 企业微信, 家长端等发送渠道。
- 不做同事 skill 在线上传, 编辑, 删除或版本管理页面。
- 不做多次提到同一学生的特殊合并规则。
- 不为未点名学生生成默认反馈。
- 不迁移其他页面到 shadcn/ui。
- 不保留旧 class-feedback 代码路径或旧表。

## 架构

新链路使用新的 `class-commentary` 后端模块和数据库表。旧 `class-feedback` 只作为删除对象, 不作为新功能基础。

可复用的通用能力:

- 当前登录和权限校验。
- 班级列表, 班级学生名单读取。
- 文件上传目录和文件类型校验。
- 本地 faster-whisper 转写能力。
- AI API client 和计费包装。
- 通用运行时配置读取。

新建的业务能力:

- class-commentary task 存储。
- colleague skill 目录扫描。
- 课堂点评生成 prompt 组装。
- class-commentary API。
- shadcn/ui 版教师反馈 tab。

## 数据模型

新增 `class_commentary_tasks` 表。字段:

- `id`: integer primary key
- `organization_id`: integer not null
- `class_id`: integer not null
- `teacher_user_id`: integer not null
- `status`: text not null, allowed values `uploaded`, `transcribing`, `transcribed`, `generating`, `ready`, `failed`
- `failure_stage`: text not null default empty, allowed values empty, `transcription`, `generation`
- `audio_path`: text not null default empty
- `audio_filename`: text not null default empty
- `transcript_text`: text not null default empty
- `confirmed_transcript_text`: text not null default empty
- `transcribed_at`: text not null default empty
- `skill_id`: text not null default empty
- `skill_name`: text not null default empty
- `skill_path`: text not null default empty
- `skill_content_snapshot`: text not null default empty
- `feedback_text`: text not null default empty
- `transcription_error`: text not null default empty
- `generation_error`: text not null default empty
- `transcription_request_key`: text not null default empty
- `generation_request_key`: text not null default empty
- `chat_provider`: text not null default empty
- `chat_model`: text not null default empty
- `created_at`: text not null
- `updated_at`: text not null

Old tables to drop in migration:

- `lesson_class_feedbacks`
- `class_feedback_tasks`
- `class_feedback_student_entries`
- `class_feedback_label_configs`

If more tables match `class_feedback_%`, migration deletes them too. The old class-feedback database chain is not preserved.

## Skill 扫描

新增运行时配置:

- `XR_COLLEAGUE_SKILL_DIR`: server local directory that contains `.skill` files.

Scanning rules:

- Only files ending with `.skill` are listed.
- Directory traversal is not allowed.
- Each result contains `id`, `name`, `filename`, `updated_at`.
- The website does not upload or edit skill files.
- On generation, backend reads the selected file and saves `skill_content_snapshot` into the task.
- If a skill file is removed after a task is generated, old task detail still shows the saved snapshot metadata and result.

## API

Use `/api/class-commentary`.

All task detail endpoints return the same task JSON shape:

```json
{
  "id": 1,
  "organization_id": 1,
  "class_id": 8,
  "class_name": "数学·七年级·4班",
  "teacher_user_id": 12,
  "status": "transcribed",
  "failure_stage": "",
  "audio_filename": "lesson-commentary.m4a",
  "transcript_text": "小王今天计算有进步...",
  "confirmed_transcript_text": "小王今天计算有进步...",
  "transcribed_at": "2026-06-27 12:05:00",
  "skill_id": "teacher-style-a",
  "skill_name": "teacher-style-a",
  "skill_filename": "teacher-style-a.skill",
  "feedback_text": "小王:\n今天...",
  "transcription_error": "",
  "generation_error": "",
  "created_at": "2026-06-27 12:00:00",
  "updated_at": "2026-06-27 12:05:00"
}
```

Fields not yet available return empty strings, not `null`. `audio_path`, `skill_path`, and `skill_content_snapshot` are stored server-side and are not returned to the frontend.

### `GET /api/class-commentary/skills`

Returns scanned colleague skill options.

Response:

```json
{
  "skills": [
    {
      "id": "teacher-style-a",
      "name": "teacher-style-a",
      "filename": "teacher-style-a.skill",
      "updated_at": "2026-06-27 12:00:00"
    }
  ]
}
```

### `POST /api/class-commentary/tasks`

Multipart request:

- `class_id`
- `audio`

Behavior:

- Validates access to the class.
- Saves the audio file.
- Creates a task with `status=uploaded`.
- Enqueues background transcription through the existing AI charge wrapper and immediately moves the task to `status=transcribing`.
- Returns task detail with `status=transcribing`.
- The frontend polls `GET /api/class-commentary/tasks/<id>` until the task becomes `transcribed` or `failed`.
- On transcription success, the worker stores `transcript_text`, copies it into `confirmed_transcript_text` as the initial editable value, sets `transcribed_at`, clears `failure_stage`, clears `transcription_error`, and sets `status=transcribed`.
- On transcription failure, the worker sets `status=failed`, `failure_stage=transcription`, and `transcription_error`.

### `GET /api/class-commentary/tasks/<id>`

Returns task detail if the user can access the class or organization.

### `PUT /api/class-commentary/tasks/<id>/transcript`

Body:

```json
{
  "confirmed_transcript_text": "..."
}
```

Behavior:

- Saves the teacher-confirmed transcript.
- Sets task status to `transcribed` if it was failed with `failure_stage=generation`.
- Does not clear a transcription failure unless a successful new upload or transcription replaces the transcript.

### `POST /api/class-commentary/tasks/<id>/generate`

Body:

```json
{
  "skill_id": "teacher-style-a"
}
```

Behavior:

- Requires non-empty `confirmed_transcript_text`, falling back to `transcript_text` only if the teacher explicitly clicks confirm without edits.
- Loads class roster.
- Loads selected `.skill`.
- Calls AI API.
- Saves `skill_content_snapshot`, `feedback_text`, provider, model, and request key.
- On generation success, clears `failure_stage` and `generation_error`, then sets `status=ready`.
- On generation failure, sets `status=failed`, `failure_stage=generation`, and `generation_error`.
- Returns task detail.

## AI 合同

Generation input contains:

- Class name and student roster.
- Confirmed transcript.
- Selected colleague `.skill` content.
- Fixed output rules.

Fixed output rules:

- Only include students from the roster who are clearly mentioned in the transcript.
- Do not include unmentioned students.
- Feedback can include praise, problem, reminder, next action, or suggestion.
- Do not invent facts not supported by the transcript.
- Use the selected skill only as expression style and feedback framing, not as a source of student facts.
- Output one plain text block.
- Format:

```text
学生姓名:
一段可以直接发的测评.

学生姓名:
一段可以直接发的测评.
```

The program does not implement special logic for repeated mentions. If the teacher mentions a student more than once, AI handles it naturally from the transcript context.

## Frontend

The existing workspace page id `class-feedback-generation` stays so navigation permissions and sidebar do not need broad changes. The new page content and APIs use `class-commentary`.

The project currently is not shadcn/ui based. This feature initializes shadcn/ui for the Vite app and uses shadcn components for the new tab only.

Required shadcn/ui components for first implementation:

- `Card`
- `Button`
- `Select`
- `Input`
- `Textarea`
- `Progress`
- `Alert`
- `Badge`
- `Separator`
- `ScrollArea`
- `Skeleton`

Frontend layout:

1. Top card: class select, skill select, audio upload, create/transcribe button.
2. Status area: transcription, pending confirmation, generation, ready, failed.
3. Transcript card: editable textarea and confirm transcript action.
4. Result card: generated feedback text and copy full text button.

Rules:

- Do not build visible UI with `workspaceCardClass`, `workspacePrimaryButtonClass`, `workspaceSecondaryButtonClass`, or `workspaceFieldClass`.
- Do not hand-roll styled buttons, cards, inputs, alerts, progress bars, or empty states when a shadcn component exists.
- Business layout classes are allowed for grid, flex, width, and spacing.
- Other pages remain on the existing custom Tailwind helper system for now.

## Old Code Cleanup

Remove old backend routes:

- `GET /api/class-feedback/labels`
- `PUT /api/class-feedback/labels`
- `POST /api/class-feedback/tasks`
- `GET /api/class-feedback/tasks/<id>`
- `POST /api/class-feedback/tasks/<id>/generate`
- `POST /api/class-feedback/tasks/<id>/draft`
- `POST /api/class-feedback/tasks/<id>/confirm`

Remove old AI helper:

- `generate_class_feedback_bundle`

Remove old storage functions and imports around:

- class feedback task creation
- class feedback task hydration
- class feedback labels
- class feedback drafts
- class feedback confirmation
- recent confirmed class feedback summaries
- previous confirmed feedback lookup

Remove old dashboard integrations:

- Pending class feedback counts.
- Dashboard queue items for old feedback tasks.
- Organization attention items for old feedback tasks.
- Links driven by old feedback task status.

Remove old tests tied to old behavior and replace with new class-commentary tests.

## Permissions

- Super owner can access all organizations.
- Owner and admin can access class-commentary tasks in their organization.
- Member can access tasks for classes they can access or are assigned to.
- Skill files are global server-side options in first version. No per-organization skill permissions in first version.

## Error Handling

- Missing class: show class selection error.
- Empty or unsupported audio: reject before task creation when possible.
- Transcription failure: task status `failed`, `failure_stage=transcription`, keep audio metadata and `transcription_error`.
- Empty transcript: task status `failed`, `failure_stage=transcription`, teacher can upload again.
- Missing skill directory: skills API returns empty list with a clear configuration message.
- Missing selected skill during generation: return validation error, do not generate.
- AI generation failure: task status `failed`, `failure_stage=generation`, preserve confirmed transcript, store `generation_error`, allow retry.

## Verification Plan

Backend:

- Migration removes old `lesson_class_feedbacks` and `class_feedback_*` tables.
- Old `/api/class-feedback/*` routes are gone.
- New `class_commentary_tasks` table exists.
- New task detail response follows the documented JSON schema.
- Skill scanner returns only `.skill` files.
- Task creation validates class access and audio.
- Task creation returns `status=transcribing` and does not block on long audio.
- Frontend or tests can poll task detail until transcription completes.
- Transcription success stores transcript and status.
- Transcription failure stores `failure_stage=transcription` and `transcription_error`.
- Transcript confirmation stores teacher-edited text.
- Generation prompt includes roster, confirmed transcript, skill snapshot, and output contract.
- Generation stores result and skill snapshot.
- Failed generation preserves transcript, stores `failure_stage=generation` and `generation_error`, and can be retried.

Frontend:

- shadcn/ui is initialized in `frontend`.
- New tab imports shadcn components from the local ui component directory.
- New tab source does not import old workspace UI helpers for visible controls.
- New tab calls `/api/class-commentary/*`, not `/api/class-feedback/*`.
- Copy full text uses the generated feedback block.

Static cleanup:

- No production code references `generate_class_feedback_bundle`.
- No production code references old class-feedback storage functions.
- No production code defines old class-feedback routes.
- No production code reads or writes old class-feedback tables.
- No schema creation remains for `lesson_class_feedbacks`, `class_feedback_tasks`, `class_feedback_student_entries`, or `class_feedback_label_configs`.

Proof:

- Use a temporary proof script.
- Include backend unit tests.
- Include targeted frontend source and render tests.
- Include `npm --prefix frontend run lint`.
- Include `python -m py_compile app.py lesson_manager.py ai_processor.py`.
- Include route and table negative checks for old class-feedback.

## Rollout

This is a breaking replacement for the old teacher feedback business chain. Because the user explicitly requested old code and old tables be deleted, implementation should happen on a focused branch from `develop`, with one commit for the design and later implementation commits after the implementation plan is approved.

No production deployment is included in this design step.
