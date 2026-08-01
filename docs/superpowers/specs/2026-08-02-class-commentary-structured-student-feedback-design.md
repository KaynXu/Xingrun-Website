# 课堂反馈结构化学生反馈与单独复制设计

## 状态

- 日期: 2026-08-02
- 阶段: design approved and P1/P2 review hardened, pending implementation
- 目标页面: workspace `class-feedback-generation` tab
- 业务链路: `class-commentary`
- 输出 schema: `class_commentary.student_feedback.v1`

## 一句话方案

把当前一整段课堂反馈升级为服务端校验过的逐学生结构化结果, 在现有 `反馈结果` Card 内按学生编辑和单独复制, 同时继续派生现有整段文本, 并保持老师终审, 全局草稿, 确认和 AI 学习边界不变.

## 背景

当前生成链路让模型返回纯文本, 前端把结果放在一个 Textarea 中, 只提供一次 `复制结果`. 这可以满足统一复制, 但老师要单独发给某位家长时, 仍需手动查找并框选该学生段落.

当前链路已经具备以下可复用基础:

- 每次 generation 冻结到课学生 roster.
- 老师生成前确认转写, 并选择同事 Skill.
- generation, draft 和 revision 已经分层存储.
- 草稿使用 `expected_draft_version` 做 CAS 冲突保护.
- 确认分为 `确认但不学习` 和 `确认并让 AI 学习修改`.
- `super_owner` 可以只读查看和复制其他老师的结果, 但不能替代老师编辑或确认.
- Memory 提取已有 JSON response mode 和本地 schema 校验实践.

本设计只升级输出合同和结果区交互. 不重做课堂反馈工作流, 不恢复旧 `class_feedback_*` 业务, 也不绕过老师终审.

## 目标

- 每位学生的反馈有稳定 `student_id`, 不再依赖前端按姓名或空行切文本.
- 老师可以逐学生查看, 编辑和复制.
- `复制该学生` 和 `复制全部` 都复制当前界面可见文本, 包括尚未保存的本地修改.
- 服务端继续提供现有整段 `feedback_text`, 兼容历史页面, Memory 输入和后续渐进迁移.
- generation, draft 和 revision 都能保存同一份结构化内容, 支持历史回看和全局版本确认.
- 模型输出不合法时失败关闭, 不把未经校验的内容展示为可用反馈.
- 历史纯文本 generation 保持可读, 不用正则或模型强行拆分.

## 非目标

- 不新增页面或路由入口.
- 不接微信, 企业微信, 短信或家长端发送渠道.
- 不做逐学生独立保存, 独立确认, 独立 revision 或独立 AI 学习.
- 不新增 normalized per-student 数据表.
- 不把 generation 改为异步任务. 异步生成属于单独开发方向.
- 不解析或回填历史纯文本记录.
- 不修改转写确认, 到课名单, Skill 选择和 Memory 学习的产品边界.
- 不复活任何 `class_feedback_*` 表, API 或前端状态.

## 核心原则

### 1. ID 由模型返回, 姓名由服务端解析

模型只返回 `student_id` 和 `feedback_text`. `student_name` 只能来自本次 generation 已冻结的到课 roster. 前端和数据库都不能相信模型自己写出的姓名映射.

### 2. JSON 是事实来源, 整段文本是派生字段

结构化 generation 的 JSON envelope 是事实来源. 现有 `generated_feedback_text`, `feedback_text` 和 `final_feedback_text` 继续保留, 但必须由服务端按 canonical 规则从 JSON 派生, 不能作为第二个可写来源.

### 3. 逐学生编辑, 全局保存和确认

页面可以把每位学生拆开编辑, 但点击 `保存草稿` 或任一确认按钮时, 仍提交整份学生列表. 一次 draft version 对应一份完整 envelope. 一次 revision 也对应一份完整 envelope.

### 4. 复制是本地动作

复制不保存, 不确认, 不触发学习, 不改变服务端状态. 复制成功只提供当前浏览会话内的轻量反馈.

### 5. 老师终审是硬门槛

AI 初稿和未确认草稿不能进入 Memory. 只有原任务老师明确点击确认后, revision 才能按现有 `learn` 选择进入学习流程.

### 6. v1 不向生成模型注入 student history Memory

当前 generation 是一次全班模型调用. 即使 student history Memory 在 JSON 中按学生分组, 模型仍能把 A 的事实写入 B 的正文而不出现 A 姓名. v1 因此只允许 teacher style Memory 进入生成 prompt, 并把 `student_history_memory_mode` 固定为 `disabled_v1`. 确认后的 Memory 提取和未来检索数据继续保留, 但只有改为逐学生隔离调用或具备等价强隔离后, 才能重新启用 generation-time student history.

### 7. generation 冻结格式和 eligible scope

capability, schema version, response format, matcher version 和 eligible student IDs 必须在 reservation 事务内一起冻结. 模型执行, Memory retrieval, draft, confirmation 和历史读取只消费 generation 快照, 不能重新读取 live capability, live roster 或再次做姓名子串匹配.

## AI 输出合同

### Schema

模型必须只返回一个 JSON object:

```json
{
  "schema_version": "class_commentary.student_feedback.v1",
  "items": [
    {
      "student_id": 123,
      "feedback_text": "今天课堂计算更稳定, 下一步继续加强验算."
    }
  ]
}
```

固定约束:

- 顶层只允许 `schema_version` 和 `items`.
- `schema_version` 必须精确等于 `class_commentary.student_feedback.v1`.
- 每个 item 只允许 `student_id` 和 `feedback_text`.
- 模型不得返回 `student_name`, `class_name`, `status`, `evidence` 或其他字段.
- `student_id` 必须是正整数.
- `feedback_text` 必须是非空字符串.
- items 顺序不被信任, 服务端会按冻结 roster 重排.

### Prompt 规则

现有事实和 Skill 边界继续有效, 并把纯文本输出规则替换为:

- 输出符合指定 schema 的 JSON object.
- 只为确认转写中明确点名的冻结 roster 学生生成 item.
- 每个符合条件的学生恰好生成 1 个 item.
- 不为未点名学生或 roster 外学生生成内容.
- item 的正文不重复学生姓名标题.
- item 的正文不能提到本次冻结 roster 中的另一名学生.
- 学生事实只能来自确认转写. v1 不向 generation prompt 注入 student history Memory.
- Skill 只控制判断重点, 结构, 语气和表达习惯, 不能提供学生事实.

模型调用使用 `response_format={"type":"json_object"}`. 返回后使用 JSON parser 和 Pydantic model 做本地校验. v1 不增加第二次收费的模型修复调用.

### Generation-time Memory isolation

structured v1 的生成 prompt 只包含:

- frozen class and roster facts.
- frozen eligible student IDs.
- confirmed transcript snapshot.
- active Skill snapshot.
- teacher style Memory.
- output rules.

`student_history_memories` 必须传空数组, `memory_context_snapshot_json` 也必须记录 `student_history_memory_mode=disabled_v1` 和空的 student history 列表. 不能先检索全班 student history 再要求模型自行隔离. 跨学生姓名检查只是一层内容防线, 不能替代 Memory 隔离.

## 服务端校验和 canonicalization

### Frozen roster

服务端从 `attending_roster_snapshot_json` 建立唯一映射:

```text
student_id -> frozen student_name -> frozen roster position
```

所有输出, 草稿和确认请求都必须基于对应 generation 的 frozen roster 校验, 不能改用当前班级 live roster. 学生后续转班, 改名或被删除都不能改变历史 generation 的姓名和排序.

### Frozen eligible student scope

eligible scope 必须在 `reserve_class_commentary_generation()` 的 `BEGIN IMMEDIATE` 事务内, 使用该事务读到的 confirmed transcript snapshot 和 normalized frozen roster 计算. 计算必须发生在 generation row INSERT 之前. 无命中或名单歧义时直接返回 precondition error, 不创建 generation, 不扣费, 也不把 task 留在 `generating`.

matcher 固定为 `class_commentary.student_name_matcher.v1`:

1. 对 transcript 和 roster names 使用 Unicode NFKC, trim 和统一空白规则生成匹配文本.
2. 如果两个 roster items 得到同一个 normalized name, 返回 `student_roster_name_ambiguous`. v1 不猜测同班重名对应哪个 ID.
3. 枚举每个 normalized name 在 transcript 中的全部 span.
4. 同一起点优先最长 name, 已被更长 name 占用的重叠 span 不再命中短 name. 因此只出现 `张三丰` 时不会同时命中 `张三`.
5. 同一 student 的多个 span 只产生 1 个 eligible student ID.
6. 当前工作流继续要求老师按名单清楚点全名. v1 不处理小名, 同音字或人工别名推断.

reservation 持久化:

- `eligible_student_ids_json`: 按 frozen roster position 排序的唯一 ID 数组.
- `student_mention_matcher_version`: `class_commentary.student_name_matcher.v1`.
- `eligible_student_scope_hash`: 对 matcher version, confirmed transcript hash, attending roster hash 和 eligible IDs 的 canonical envelope 计算.

这 3 个字段进入 generation request payload hash 和 execution snapshot. Prompt 直接读取 frozen eligible IDs. Memory retrieval 不再读取 raw transcript 做姓名子串匹配, 也不再用 live roster 重算范围. Draft PUT 和 confirmation POST 必须要求 items 集合与 frozen eligible IDs 完全一致.

如果 eligible IDs 为空, reservation 返回 `student_feedback_no_eligible_students`. 如果 matcher 以后升级, 已有 generation 继续使用自己的 frozen version 和 IDs, 不回算历史结果.

### Structural validation

服务端必须拒绝以下结果:

- 非 JSON object 或 schema version 不匹配.
- 未知字段, 未知 student ID, 重复 student ID 或非正整数 ID.
- 缺少任一 eligible student, 或包含未被转写点名的学生.
- item 为空, 正文 trim 后为空, 或正文只剩学生姓名和标点.
- 单个 `feedback_text` 超过 2000 个 Unicode code points.
- canonical 整段文本超过 30000 个 Unicode code points.
- 某个 item 正文包含 frozen roster 中另一名学生的完整姓名.

这些限制同时应用于模型结果, draft PUT 和 confirmation POST. 客户端校验只用于即时提示, 不能替代服务端校验.

### Canonical order

服务端忽略模型和客户端的 items 顺序, 按 frozen roster position 重排. 因此生成, 保存, 确认, hash, API response 和 `复制全部` 都使用同一稳定顺序.

### Canonical JSON

持久化和 hash 前构造唯一 envelope:

```json
{
  "schema_version": "class_commentary.student_feedback.v1",
  "items": [
    {
      "student_id": 123,
      "feedback_text": "今天课堂计算更稳定, 下一步继续加强验算."
    }
  ]
}
```

JSON serialization 使用 UTF-8, `ensure_ascii=false`, 固定 key 顺序和紧凑 separators. `feedback_text` 只做现有尾部空白清理, 不重写正文内容.

### Derived full text

服务端用 frozen name 派生兼容文本:

```text
张三:
今天课堂计算更稳定, 下一步继续加强验算.

李四:
今天能跟上课堂节奏, 但还需要主动写出验算过程.
```

规则:

- 姓名标题固定为 `{frozen_student_name}:`.
- 标题和正文之间换 1 行.
- 学生块之间空 1 行.
- 不在末尾追加多余空行.
- 客户端不得提交自己拼出的整段文本作为 structured generation 的事实来源.

## 数据模型

v1 不新增逐学生表. 在现有 3 个版本层增加结构化快照字段.

### `class_commentary_generations`

- `feedback_schema_version TEXT NOT NULL DEFAULT ''`
- `structured_feedback_json TEXT NOT NULL DEFAULT ''`
- `structured_feedback_hash TEXT NOT NULL DEFAULT ''`
- `eligible_student_ids_json TEXT NOT NULL DEFAULT '[]'`
- `eligible_student_scope_hash TEXT NOT NULL DEFAULT ''`
- `student_mention_matcher_version TEXT NOT NULL DEFAULT ''`
- `response_format_json TEXT NOT NULL DEFAULT '{}'`
- `student_history_memory_mode TEXT NOT NULL DEFAULT ''`
- `generated_feedback_text` 继续存在, 值由 JSON 派生.

`feedback_schema_version`, `response_format_json`, `student_history_memory_mode`, matcher fields, prompt version 和 frozen eligible IDs 都必须进入 `generation_request_payload_hash`. 任务执行只读取这些 generation fields, 不能在模型返回时重新读取 capability.

### `class_commentary_feedback_drafts`

- `feedback_schema_version TEXT NOT NULL DEFAULT ''`
- `structured_feedback_json TEXT NOT NULL DEFAULT ''`
- 现有 `content_hash` 对 canonical structured envelope 计算, 不再对派生整段文本计算.
- `feedback_text` 继续存在, 值由 JSON 派生.

### `class_commentary_revisions`

- `feedback_schema_version TEXT NOT NULL DEFAULT ''`
- `structured_feedback_json TEXT NOT NULL DEFAULT ''`
- `structured_feedback_hash TEXT NOT NULL DEFAULT ''`
- `final_feedback_text` 继续存在, 值由 JSON 派生.

### Task compatibility fields

`class_commentary_tasks.feedback_text` 和 `final_feedback_text` 继续保存派生文本, 用于列表, 旧客户端和现有 Memory 输入. task 不是结构化内容的独立写入来源.

### Atomic write rule

同一次 generation completion, draft save 或 revision confirmation 必须在一个数据库事务中同时写入:

- schema version
- canonical structured JSON
- structured hash 或 content hash
- derived full text compatibility field

不得出现 JSON 已更新但文本仍是旧版本的中间状态.

## API 合同

### Common read envelope

generation, draft 和 revision serializers 都必须返回以下公共字段, 不能只在 generation response 返回 structured 数据:

```json
{
  "feedback_schema_version": "class_commentary.student_feedback.v1",
  "feedback_schema_status": "supported",
  "student_feedback_items": [
    {
      "student_id": 123,
      "student_name": "张三",
      "feedback_text": "今天课堂计算更稳定, 下一步继续加强验算."
    }
  ],
  "structured_feedback_hash": "server-hash",
  "derived_feedback_text": "张三:\n今天课堂计算更稳定, 下一步继续加强验算."
}
```

`student_name` 是 response-only 字段, 由服务端从 generation frozen roster 解析. structured JSON 存储中不复制姓名. `derived_feedback_text` 是统一读字段, 原有 `generated_feedback_text`, `feedback_text` 或 `final_feedback_text` 继续返回同一个值作为兼容字段.

`feedback_schema_status` 只允许:

- `plain_text`: schema version 为空, 使用 legacy 纯文本合同.
- `supported`: schema version 已知且 JSON 通过本地校验.
- `unsupported`: schema version 非空但当前服务不认识.
- `invalid`: schema version 已知, 但持久化 JSON, hash 或 derived text 一致性校验失败.

`unsupported` 和 `invalid` 都是 read-only fail-closed. GET 可以返回现有 derived text 供查看和复制, 但 items 必须为空, `writable=false`, 前端不能降级为 plain-text Textarea, 保存或确认. 所有写 endpoints 返回 `409 feedback_schema_unsupported` 或 `409 feedback_schema_invalid`.

### Generation GET and list response

generation GET 和 generation list item 除 common read envelope 外还返回:

```json
{
  "generation_id": 25,
  "generation_no": 3,
  "eligible_student_ids": [123],
  "eligible_student_scope_hash": "scope-hash",
  "student_mention_matcher_version": "class_commentary.student_name_matcher.v1",
  "prompt_version": "prompt-version",
  "response_format": {"type": "json_object"},
  "student_history_memory_mode": "disabled_v1",
  "generated_feedback_text": "张三:\n今天课堂计算更稳定, 下一步继续加强验算.",
  "status": "succeeded"
}
```

list 和 detail 必须使用同一 schema/status parser. list 不能因为 payload 较轻就把 unknown nonempty schema 当作 plain text.

### Draft GET, PUT response and 409

`GET` 和成功的 `PUT /api/class-commentary/tasks/<task_id>/generations/<generation_id>/feedback-draft` 返回:

```json
{
  "draft": {
    "id": 7,
    "task_id": 10,
    "generation_id": 25,
    "based_on_revision_id": 9,
    "feedback_schema_version": "class_commentary.student_feedback.v1",
    "feedback_schema_status": "supported",
    "student_feedback_items": [
      {
        "student_id": 123,
        "student_name": "张三",
        "feedback_text": "老师修改后的反馈."
      }
    ],
    "structured_feedback_hash": "draft-content-hash",
    "derived_feedback_text": "张三:\n老师修改后的反馈.",
    "feedback_text": "张三:\n老师修改后的反馈.",
    "content_hash": "draft-content-hash",
    "draft_version": 3
  },
  "draft_version": 3
}
```

draft 不存在时继续返回 `draft=null` 和 `draft_version=0`. structured draft conflict 返回 `409 draft_version_conflict` 和同样完整的 `current_draft` object. 前端 conflict state 必须保留完整 local items snapshot, 不能只保留拼接后的 local text.

### Structured draft PUT

`PUT /api/class-commentary/tasks/<task_id>/generations/<generation_id>/feedback-draft`

```json
{
  "feedback_schema_version": "class_commentary.student_feedback.v1",
  "student_feedback_items": [
    {
      "student_id": 123,
      "feedback_text": "老师修改后的反馈."
    }
  ],
  "expected_draft_version": 2,
  "based_on_revision_id": 9
}
```

规则:

- structured generation 不接受 `feedback_text` 作为第二来源.
- 请求中的姓名和 items 顺序都不被接受或信任.
- 服务端 canonicalize 后整体保存, draft version 只增加 1.
- CAS 冲突继续返回 `409` 和当前完整 draft, 其中包含服务端解析后的 items.
- items 必须和 generation frozen eligible student IDs 完全一致.

### Structured confirmation POST

`POST /api/class-commentary/tasks/<task_id>/feedback-confirmations`

```json
{
  "generation_id": 25,
  "feedback_schema_version": "class_commentary.student_feedback.v1",
  "student_feedback_items": [
    {
      "student_id": 123,
      "feedback_text": "老师最终确认的反馈."
    }
  ],
  "learn": true,
  "expected_draft_version": 2,
  "expected_latest_revision_id": 9,
  "request_id": "client-generated-id"
}
```

`expected_latest_revision_id` 是 task 全局 revision CAS. task 尚无 revision 时必须显式传 `null`. 它不能用 generation 内的 draft version 替代, 因为两个标签页可能分别确认不同 generation.

事务顺序必须固定:

1. `BEGIN IMMEDIATE` 后先按 `(task_id, request_id)` 查找既有 revision.
2. 已存在时比较 stored confirmation payload hash. 相同则直接返回原 revision 和原 confirmed draft snapshot, 不重新执行 generation, draft 或 latest revision CAS. 不同则返回 `409 confirmation_request_conflict`.
3. 只有 request ID 未命中时, 才校验 generation scope, schema, structured items 和 draft CAS.
4. 比较 `expected_latest_revision_id` 与 task 当前 `latest_revision_id`, 使用 null-safe equality.
5. 不一致时返回 `409 revision_version_conflict`, 并附完整 `current_latest_revision` 和 `current_latest_revision_id`. 不创建 revision, 不覆盖 task 终稿.
6. 全部通过后, 在同一事务插入 revision, 更新 confirmed draft snapshot, task latest pointer 和可选 Memory job.

confirmation payload hash 基于 canonical structured envelope, generation ID, `learn`, `expected_draft_version`, `expected_latest_revision_id` 和 task ID 计算, 不能基于客户端拼接的整段文本.

### Confirmation and revision responses

confirmation 成功返回:

```json
{
  "revision_id": 10,
  "latest_revision_id": 10,
  "latest_revision_no": 4,
  "revision": {
    "id": 10,
    "task_id": 10,
    "generation_id": 25,
    "revision_no": 4,
    "previous_revision_id": 9,
    "feedback_schema_version": "class_commentary.student_feedback.v1",
    "feedback_schema_status": "supported",
    "student_feedback_items": [
      {
        "student_id": 123,
        "student_name": "张三",
        "feedback_text": "老师最终确认的反馈."
      }
    ],
    "structured_feedback_hash": "revision-hash",
    "derived_feedback_text": "张三:\n老师最终确认的反馈.",
    "final_feedback_text": "张三:\n老师最终确认的反馈.",
    "confirmed_draft_version": 3,
    "learn_requested": true
  },
  "draft": {
    "feedback_schema_version": "class_commentary.student_feedback.v1",
    "feedback_schema_status": "supported",
    "student_feedback_items": [
      {
        "student_id": 123,
        "student_name": "张三",
        "feedback_text": "老师最终确认的反馈."
      }
    ],
    "derived_feedback_text": "张三:\n老师最终确认的反馈.",
    "draft_version": 3
  }
}
```

真实 response 必须返回完整 confirmed draft object, 与 draft GET shape 一致.

`GET /api/class-commentary/tasks/<task_id>/feedback-revisions` 的每个 revision item 必须返回 common read envelope, `revision_no`, `previous_revision_id`, `confirmed_draft_version`, `learn_requested` 和 `confirmed_at`. revision history 不能只返回时间和纯文本.

### Plain-text compatibility

旧 generation 的新增字段返回:

```json
{
  "feedback_schema_version": "",
  "feedback_schema_status": "plain_text",
  "student_feedback_items": [],
  "derived_feedback_text": "历史纯文本内容",
  "generated_feedback_text": "历史纯文本内容"
}
```

客户端把空 schema version 视为 `plain_text` mode, 继续使用现有单 Textarea 和 `复制结果` 流程. 旧 draft 和 confirmation 请求继续接受 `feedback_text`. 服务端绝不尝试用姓名, 空行或正则拆分历史内容.

如果 structured generation 收到 plain-text 请求, 或 plain-text generation 收到 structured 请求, 返回 `400 feedback_schema_mismatch`.

## UI 和交互

### 页面边界

不新增页面. 继续使用现有 `反馈结果` Card, 并保留:

- 班级和同事测评风格摘要.
- 生成版本 Select.
- generation, draft 和 revision Badge.
- 底部 3 个全局动作: `保存草稿`, `确认但不学习`, `确认并让 AI 学习修改`.
- Memory 学习状态和后续展示.

### Structured result mode

当 `feedback_schema_version` 为 `class_commentary.student_feedback.v1` 时:

- Card header 的复制动作改为 `复制全部`.
- 学生列表使用现有 shadcn/ui `Accordion`.
- 第一名学生默认展开, 其余学生按 frozen roster 顺序排列.
- 每个 Accordion trigger 显示学生姓名和轻量编辑状态.
- 每个 Accordion content 包含该学生的 Textarea 和 `复制该学生` Button.
- 1-4 名学生自然展开. 5 名及以上放入 shadcn/ui `ScrollArea`. 桌面高度使用 `clamp(320px, 60vh, 560px)`, 小于 640px 的窄屏使用 `clamp(280px, 55vh, 480px)`.
- 不新增自定义 Card, Button 或 Accordion 视觉体系, 沿用项目现有 shadcn tokens.

ScrollArea 验收不能只检查无视觉溢出. 必须断言 viewport 可滚动, 最后一名学生的 trigger, Textarea 和 copy action 都能通过键盘和滚动到达.

### Accessibility

- 每个 Textarea 有可见 label `{student_name}反馈内容`, 使用 `htmlFor` 和唯一 input ID 关联.
- validation error 时设置 `aria-invalid=true` 和指向错误文案的 `aria-describedby`.
- 服务端返回 student-specific error 后, 前端自动展开对应 Accordion item, 滚动到该项并聚焦 Textarea.
- Accordion trigger, copy action 和 revision history action 都必须可键盘操作, focus ring 沿用 shadcn tokens.
- read-only super owner 的 Textarea 使用 `readOnly`, 不使用 `disabled`, 保证正文可以聚焦, 选择和复制.

### Local editor state

前端 state 不能只用全局 `student_id` 作为 key. 使用 `workspaceKey={task_id}:{generation_id}` 隔离每份 editor, 每个 editor 内再使用 `itemsByStudentId`. revision preview 使用独立的 `revisionPreviewKey={task_id}:{revision_id}`, 不能覆盖 generation editor.

每个 generation editor 至少保存:

- `taskId` and `generationId`.
- `feedbackSchemaVersion`.
- `itemsByStudentId` current snapshot.
- `savedItemsByStudentId` last server snapshot.
- `draftVersion` and `basedOnRevisionId`.
- `latestRevisionIdAtLoad`.
- `dirty` derived from canonical current vs saved envelope.

- 编辑任一学生后, 全局状态进入 `已修改未保存`.
- 保存成功后, 所有 item 一起进入新的 draft version.
- 不显示每个学生独立的已保存或已确认状态, 避免误导为逐人版本.

structured draft conflict state 必须保存:

- `workspaceKey`.
- 完整 `localItems` canonical snapshot.
- 完整 `serverDraft` structured response.
- attempted `expectedDraftVersion`.

冲突弹窗的 `复制本地内容` 从 frozen local items 生成文本. `加载服务器版本` 只替换同一个 workspaceKey, 不能误写当前已经切换到的另一个 task 或 generation.

### Revision history selection

revision rows 必须可选择, 不能只显示时间. 点击 `查看第 N 版` 后进入 immutable revision preview:

- 使用 revision response 自己的 schema and items.
- Textareas 为 readOnly, copy actions 可用.
- 不显示保存或确认 action.
- 显示 `返回当前编辑` 回到原 generation editor.
- v1 不提供从旧 revision 直接恢复为新 draft. 如果以后增加, 必须单独定义 branch/restore semantics 和 latest revision CAS.

### Dirty transition matrix

| Transition | Clean state | Dirty state | Required behavior |
| --- | --- | --- | --- |
| Switch generation | Switch immediately | Block transition | Show `保存草稿`, `复制本地内容`, `放弃并切换`, `取消` |
| Switch history task | Switch immediately | Block transition | Do not call `resetFeedbackVersionState()` until the user saves or explicitly discards |
| Open revision preview | Open immediately | Block transition | Preserve the current generation editor and use the same 4 actions |
| Leave class-feedback workspace route | Leave immediately | Block transition | Use the same in-app guard before route change |
| Browser reload or close | Leave immediately | Native browser guard | Register `beforeunload`; do not attempt silent async save |
| Draft save succeeds | Stay in editor | Clear dirty | Replace saved snapshot and draft version only for the matching workspaceKey |
| Draft CAS conflicts | Stay in editor | Remain dirty | Preserve full local items and offer copy or load server draft |
| Revision CAS conflicts | Stay in editor | Remain dirty | Show current latest revision, preserve local items, require explicit reload or retry |

No transition may clear structured local state merely because task, generation, revision or route selection changed. User-confirmed discard is the only destructive transition.

### Copy one

`复制该学生` 的默认文本格式:

```text
张三:
老师当前在界面中看到的反馈正文.
```

它必须读取当前本地 editor state, 包括未保存修改, 不读取上次保存的 draft 或 revision 快照.

复制成功后按钮短暂显示 `已复制`. 该状态只存在于当前页面会话, 并在以下任一条件发生时重置:

- 该学生正文再次变化.
- 切换 generation 或 revision.
- 页面重新加载.

### Copy all

`复制全部` 使用当前本地 editor state, 按 frozen roster 顺序生成与服务端 derived full text 相同的格式. 它同样可以复制未保存修改, 且不触发保存或确认.

### Copy audit boundary

老师终审在 v1 约束的是 Memory 学习和系统内 confirmed revision, 不是外部发送. 现有产品已经允许确认前复制, structured v1 继续保留这个效率边界, 但必须明确提示:

- 当前本地内容与已保存 draft 不同时, copy actions 附近显示 `未保存`.
- 当前内容没有对应 confirmed revision 时, 显示 `未确认`.
- 复制未保存或未确认内容成功后, toast 显示 `已复制未确认内容, 发送前请再次检查`.
- 已确认 snapshot 原样查看时显示 `已确认第 N 版`.

copy event 不写服务器. 因此服务端只能还原 generation, draft 和 revision, 不能证明老师实际复制或发送了哪段本地文本. 如果未来要求可审计对外发送, 必须新增 explicit delivery snapshot 和发送确认, 不能把 clipboard action 伪装成可审计交付.

### Empty and error states

- structured generation 成功但 items 为空不属于合法成功状态, 前端不展示空 Accordion.
- generation 校验失败时沿用现有失败态, 展示稳定的可操作提示: `反馈结构校验失败, 请重新生成`.
- 页面不展示未经校验的模型原文.
- 重新生成继续创建新的 generation, 不覆盖旧 generation.
- unknown nonempty schema 显示 `当前版本暂不支持编辑`, 只提供 read-only derived text 和 copy. 不渲染 editable plain-text fallback.
- student-specific validation error 使用安全字段定位, 自动打开并聚焦对应学生.

### Read-only super owner

只读 `super_owner` 可以:

- 展开学生项.
- 查看当前 generation, draft 和 revision.
- 使用 `复制该学生` 和 `复制全部`.

只读 `super_owner` 不能:

- 修改任一 Textarea.
- 保存草稿.
- 确认或触发 AI 学习.

read-only Textarea 使用 `readOnly`, 不使用 `disabled`.

## Memory 和学习边界

### Generation-time retrieval

v1 禁用 student history retrieval for generation. Memory retrieval 只能返回 teacher style Memory, 并直接使用 generation frozen eligible scope. 当前 `class_commentary_memory_retrieval.py` 中基于 `student_name in transcript` 的二次匹配必须从 structured path 移除. 它不能决定 prompt 学生范围, 也不能把多个学生的 history 合并后传入一次全班调用.

### Post-confirmation learning

v1 不改 Memory extraction schema. 确认并选择学习后, 继续把 revision 的 derived full text 作为现有 Memory extraction 输入.

- Memory extraction 只能读取已确认 revision 的 derived text.
- generation JSON 和 draft JSON 不直接进入 extraction.
- derived text 必须由已确认的 canonical structured envelope 生成.
- `learn=false` 的 revision 继续不发起学习.
- confirmation 必须先通过 task-level latest revision CAS, 才能创建 Memory job.

以后如要让生成阶段重新使用 student history, 必须改为每个 eligible student 独立 retrieval 和独立 model call, 每次 call 只能得到该 `student_id` 的 transcript evidence 和 history. 聚合层只允许按 frozen order 合并已校验 items. 这属于后续独立设计, 不能在 v1 隐式开启.

## 错误处理

模型结构或内容校验失败统一收口为稳定错误码 `structured_feedback_invalid`.

- generation 标记为 failed.
- `error_code` 保存稳定错误码, 不保存模型原文为成功内容.
- 服务端日志记录 generation ID 和具体 validation reason, 不向前端返回未经校验的学生反馈全文.
- 不做纯文本 fallback, 不做正则拆分, 不发起第二次模型修复请求.
- 老师可以使用现有 `重新生成` 创建新 generation.

草稿和确认请求失败时返回具体客户端错误码, 例如:

- `feedback_schema_mismatch`
- `student_feedback_unknown_student`
- `student_feedback_duplicate_student`
- `student_feedback_coverage_mismatch`
- `student_feedback_empty`
- `student_feedback_too_long`
- `student_feedback_cross_student_reference`
- `student_roster_name_ambiguous`
- `student_feedback_no_eligible_students`
- `revision_version_conflict`
- `feedback_schema_unsupported`
- `feedback_schema_invalid`

错误码用于测试和前端映射. 用户可见文案保持短且可行动.

student-specific client errors 使用安全定位字段, 不回传反馈正文:

```json
{
  "error": "student_feedback_too_long",
  "student_id": 123,
  "field": "feedback_text",
  "limit": 2000
}
```

允许的附加字段只有 `student_id`, `field`, `limit`, `current_draft`, `current_latest_revision` 和对应 version IDs. 错误响应不能包含未经校验的模型原文, Memory text 或其他学生的正文.

## Capability 和发布

新增 capability `structured_feedback_enabled`.

- 默认关闭时, 新 generation 继续使用现有 plain-text 合同.
- 开启后, 新 generation 使用 `class_commentary.student_feedback.v1`.
- capability 只在 reservation 时决定新 generation 的输出格式.
- capability 关闭后, 已经存在的 structured generation, draft 和 revision 仍必须可读, 可复制和按权限编辑确认.
- 前端不能用 capability 隐藏历史 structured 数据, 必须以 generation 自身 schema version 决定渲染模式.

reservation 必须冻结并进入 request hash:

- `feedback_schema_version`.
- `prompt_version`.
- `response_format_json`.
- `student_mention_matcher_version`.
- `eligible_student_ids_json` and scope hash.
- `student_history_memory_mode`.

reservation 成功后, 执行层不能重新读取 `structured_feedback_enabled`. kill switch 在 generation 进行中被关闭时, 已 reservation 的 generation 仍按自己的 frozen schema 执行或失败, 不能改成 plain text.

### Rollback floor

发布分两层:

- Compatibility floor: additive columns, schema-aware serializers, unknown schema read-only fail-closed 和 write rejection. capability 关闭.
- Feature release: structured reservation, generation, draft, confirmation 和 UI.

生产一旦产生第一条 nonempty `feedback_schema_version`, 最低可回滚版本就是 compatibility floor 对应的已记录 commit. 只能关闭 capability 阻止新的 structured generation, 不能回滚到不认识 structured columns 或会把 unknown schema 当 plain text 编辑的旧版本. 发布记录必须保存 compatibility floor commit SHA, migration 完成时间和首条 structured generation ID.

建议发布顺序:

1. 先部署 compatibility floor: additive SQLite migration, 完整双读 serializers 和 unknown schema fail-closed, capability 保持关闭.
2. 部署 structured generation, draft, confirmation 和 UI, 在本地与测试环境开启.
3. 用真实到课名单完成重名/包含名 matcher, 单独复制, 未保存复制, task/revision/generation dirty transitions, draft CAS, revision CAS, 两种确认和历史回看的 smoke.
4. 生产开启 capability, 观察 `structured_feedback_invalid` 比例和老师重新生成率.
5. kill switch 关闭时只影响新 generation, 不影响既有 structured history.

## 验收标准

### Backend

- 模型乱序返回 items 后, API 和 derived text 按 frozen roster 顺序返回.
- API response 的学生姓名来自 frozen roster, 不来自模型.
- `张三/张三丰` 只命中最长非重叠姓名, Unicode equivalent names 使用同一 NFKC 规则, normalized 同名 roster 在 reservation 前失败.
- empty eligible scope 在 INSERT 前失败, 不创建 generation, 不扣费, task 不进入 `generating`.
- eligible IDs, matcher version, scope hash, schema, prompt version, response format 和 student history mode 全部冻结并进入 request hash.
- structured generation 的 prompt 和 memory snapshot 不包含 student history Memory. Memory retrieval 不再用 raw transcript 子串重算学生范围.
- 未知 ID, 重复 ID, coverage 不一致, 空正文, 超限正文和跨学生姓名污染全部失败关闭.
- structured draft 和 confirmation 不接受 `feedback_text`.
- structured draft CAS 冲突返回完整当前 structured draft.
- confirmation 先按 request ID 查重. 相同 canonical payload 返回原 revision/draft snapshot, 不受当前 CAS 状态影响; 不同 payload 冲突.
- 两个标签页确认不同 generation 时, 只有匹配 `expected_latest_revision_id` 的请求成功, 另一个得到 `revision_version_conflict` 且不创建 revision.
- generation, draft, confirmation 和 revision history serializers 都返回 schema status, parsed items, structured hash, derived text 和各自 version fields.
- unknown nonempty schema 和 known-invalid payload 只读 fail-closed, 不回退 plain-text write path.
- generation, draft 和 revision 的 JSON, hash 和 derived text 在同一事务中一致.
- 旧 plain-text generation, draft 和 revision 仍可读取, 编辑, 确认和复制.
- capability 关闭后仍能读取历史 structured generation.
- reservation 后关闭 capability 不改变该 generation 的 frozen schema 或 response format.
- Memory 只在老师确认且 `learn=true` 后读取 derived revision text.

### Frontend

- structured generation 在现有结果 Card 内显示逐学生 Accordion, 不新增页面.
- `复制该学生` 复制姓名标题和当前可见正文.
- `复制全部` 复制当前可见的所有正文, 包括未保存修改.
- 复制不调用 draft 或 confirmation API.
- 某学生正文变化后, 该学生的 `已复制` 状态重置.
- 保存草稿仍是一次全局 CAS 请求.
- 两个确认按钮仍确认整份学生反馈.
- editor state 至少按 `task_id:generation_id` 隔离, late response 和 conflict action 不能改写另一个 workspaceKey.
- task, generation, revision 和 workspace route 切换全部经过 dirty transition guard; reload/close 使用 native `beforeunload`.
- revision history 每条可以进入 immutable preview, 并可返回当前 editor.
- structured draft conflict 保留完整 local items snapshot, 不只保留 derived text.
- student-specific API error 自动展开并聚焦对应 Textarea, label, `aria-invalid` 和 error description 关联正确.
- read-only super owner 使用 readOnly Textarea, 能聚焦, 选择和复制, 但不能编辑, 保存或确认.
- 5 名及以上学生的 ScrollArea 在桌面和窄屏均可到达最后一名学生的全部 controls.
- 未保存/未确认内容在 copy action 附近和 toast 中明确提示, 同时不伪称 clipboard 内容可由服务端审计.
- plain-text history 继续显示原 Textarea, 不自动拆分.

### Regression

- 生成版本切换, revision preview, draft/revision conflict 和未保存离开保护继续工作.
- 当前 class-commentary 权限隔离不变化.
- 现有 `class_commentary_memory` 学习和撤销链路不变化.
- 不出现 `class_feedback_*` 新代码, 新表或新 API.

## 实现切片

建议按以下顺序实现, 但作为一个完整功能分支合入:

1. 先做 compatibility floor: additive migration, common read envelope, unknown schema fail-closed 和 legacy tests.
2. 增加 matcher v1, frozen eligible scope, structured schema model, canonicalization 和 reservation precondition tests.
3. 冻结 prompt/response format/memory mode, structured generation 只带 teacher style Memory.
4. 扩展 structured draft, task-level revision CAS, idempotency ordering 和完整 serializers.
5. 更新 TypeScript types, scoped editor state, API payload 和 dirty transition guard.
6. 在现有结果 Card 内实现 Accordion, ScrollArea, revision preview, accessibility 和 copy status.
7. 补定向后端/前端测试, production build 和真实浏览器 smoke.
8. capability 默认关闭部署 compatibility floor 和 feature release, 记录 rollback floor commit, 再按验收清单开启.

## 关键取舍

### 为什么 v1 不建逐学生表

当前保存, 冲突检测, 确认和学习都是一份全局 payload. 直接增加 JSON 快照可以最小改动地支持逐学生 UI, 又不制造一套与现有 revision 并行的逐学生版本系统. 当未来出现逐学生发送状态, 独立确认或家长渠道回执时, 再评估 normalized per-student delivery table.

### 为什么不解析历史文本

历史输出受 Skill, 姓名标题, 段落和 emoji 影响, 用正则无法稳定还原学生边界. 错分比保留旧 Textarea 更危险. 因此 schema version 是明确分界, 新数据结构化, 老数据原样读取.

### 为什么复制未保存文本

复制是老师把眼前内容带到外部沟通工具的动作. 如果按钮复制上次保存版本, 老师会看到一种内容却发出另一种内容. 保存和确认仍需显式动作, 所以复制当前可见文本不会削弱审计边界.

### 为什么校验失败不降级纯文本

一旦未经校验的模型输出被当作逐学生内容展示, 可能发生错学生, 漏学生或跨学生事实污染. 失败并提示重新生成比静默降级更符合家长反馈的准确性要求.
