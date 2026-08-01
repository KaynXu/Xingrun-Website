# 课堂反馈结构化学生反馈与单独复制设计

## 状态

- 日期: 2026-08-02
- 阶段: design approved, pending implementation
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
- 学生事实只能来自确认转写和经过隔离的该学生历史记忆.
- Skill 只控制判断重点, 结构, 语气和表达习惯, 不能提供学生事实.

模型调用使用 `response_format={"type":"json_object"}`. 返回后使用 JSON parser 和 Pydantic model 做本地校验. v1 不增加第二次收费的模型修复调用.

## 服务端校验和 canonicalization

### Frozen roster

服务端从 `attending_roster_snapshot_json` 建立唯一映射:

```text
student_id -> frozen student_name -> frozen roster position
```

所有输出, 草稿和确认请求都必须基于对应 generation 的 frozen roster 校验, 不能改用当前班级 live roster. 学生后续转班, 改名或被删除都不能改变历史 generation 的姓名和排序.

### Mention coverage

服务端用确认转写和 frozen roster 计算本次 eligible student IDs:

- 对学生姓名做首尾空白和 Unicode 标准化.
- 只有完整 frozen student name 在确认转写中明确出现, 才视为被点名.
- 返回 item 集合必须和 eligible student ID 集合完全一致.
- 当前工作流已经要求老师按名单清楚点名. v1 不处理小名, 同音字或重名推断.

如果确认转写没有命中任何 frozen roster 学生, 在调用模型前直接返回 roster/content quality error.

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
- `generated_feedback_text` 继续存在, 值由 JSON 派生.

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

### Generation response

现有 generation endpoints 增加:

```json
{
  "feedback_schema_version": "class_commentary.student_feedback.v1",
  "student_feedback_items": [
    {
      "student_id": 123,
      "student_name": "张三",
      "feedback_text": "今天课堂计算更稳定, 下一步继续加强验算."
    }
  ],
  "generated_feedback_text": "张三:\n今天课堂计算更稳定, 下一步继续加强验算."
}
```

`student_name` 是 response-only 字段, 由服务端从 frozen roster 解析. structured JSON 存储中不复制姓名.

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
  "request_id": "client-generated-id"
}
```

确认幂等性和 `confirmation_request_conflict` 基于 canonical structured envelope, generation ID, `learn` 和现有确认上下文计算, 不能基于客户端拼接的整段文本.

### Plain-text compatibility

旧 generation 的新增字段返回:

```json
{
  "feedback_schema_version": "",
  "student_feedback_items": [],
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
- 学生数量较多时, 列表放入 shadcn/ui `ScrollArea`, 结果 Card 本身不无限增长.
- 不新增自定义 Card, Button 或 Accordion 视觉体系, 沿用项目现有 shadcn tokens.

### Local editor state

前端维护一份按 `student_id` 索引的当前可见文本, 但提交时按 generation response 顺序构造完整 items 数组.

- 编辑任一学生后, 全局状态进入 `已修改未保存`.
- 切换 generation 前继续沿用现有未保存变更保护.
- 保存成功后, 所有 item 一起进入新的 draft version.
- revision 载入后, 所有 item 一起切换到该历史快照.
- 不显示每个学生独立的已保存或已确认状态, 避免误导为逐人版本.

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

### Empty and error states

- structured generation 成功但 items 为空不属于合法成功状态, 前端不展示空 Accordion.
- generation 校验失败时沿用现有失败态, 展示稳定的可操作提示: `反馈结构校验失败, 请重新生成`.
- 页面不展示未经校验的模型原文.
- 重新生成继续创建新的 generation, 不覆盖旧 generation.

### Read-only super owner

只读 `super_owner` 可以:

- 展开学生项.
- 查看当前 generation, draft 和 revision.
- 使用 `复制该学生` 和 `复制全部`.

只读 `super_owner` 不能:

- 修改任一 Textarea.
- 保存草稿.
- 确认或触发 AI 学习.

## Memory 和学习边界

v1 不改 Memory extraction schema. 确认并选择学习后, 继续把 revision 的 derived full text 作为现有 Memory extraction 输入.

这样可以先获得逐学生编辑和复制能力, 不同时迁移 Memory pipeline. 但必须保持以下约束:

- Memory 只能读取已确认 revision 的 derived text.
- generation JSON 和 draft JSON 不直接进入 Memory.
- derived text 必须由已确认的 canonical structured envelope 生成.
- `learn=false` 的 revision 继续不发起学习.

以后如要让 Memory 直接消费结构化 items, 应单独升级 extraction contract, 不能在本设计实现中隐式切换.

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

错误码用于测试和前端映射. 用户可见文案保持短且可行动.

## Capability 和发布

新增 capability `structured_feedback_enabled`.

- 默认关闭时, 新 generation 继续使用现有 plain-text 合同.
- 开启后, 新 generation 使用 `class_commentary.student_feedback.v1`.
- capability 只决定新 generation 的输出格式.
- capability 关闭后, 已经存在的 structured generation, draft 和 revision 仍必须可读, 可复制和按权限编辑确认.
- 前端不能用 capability 隐藏历史 structured 数据, 必须以 generation 自身 schema version 决定渲染模式.

建议发布顺序:

1. 先部署 additive SQLite migration 和双读 API, capability 保持关闭.
2. 部署 structured generation, draft, confirmation 和 UI, 在本地与测试环境开启.
3. 用真实到课名单完成生成, 单独复制, 未保存复制, 保存, CAS 冲突, 两种确认和历史回看的 smoke.
4. 生产开启 capability, 观察 `structured_feedback_invalid` 比例和老师重新生成率.
5. kill switch 关闭时只影响新 generation, 不影响既有 structured history.

## 验收标准

### Backend

- 模型乱序返回 items 后, API 和 derived text 按 frozen roster 顺序返回.
- API response 的学生姓名来自 frozen roster, 不来自模型.
- 未知 ID, 重复 ID, coverage 不一致, 空正文, 超限正文和跨学生姓名污染全部失败关闭.
- structured draft 和 confirmation 不接受 `feedback_text`.
- structured draft CAS 冲突返回完整当前 structured draft.
- confirmation request ID 对相同 canonical payload 幂等, 对不同 canonical payload 冲突.
- generation, draft 和 revision 的 JSON, hash 和 derived text 在同一事务中一致.
- 旧 plain-text generation, draft 和 revision 仍可读取, 编辑, 确认和复制.
- capability 关闭后仍能读取历史 structured generation.
- Memory 只在老师确认且 `learn=true` 后读取 derived revision text.

### Frontend

- structured generation 在现有结果 Card 内显示逐学生 Accordion, 不新增页面.
- `复制该学生` 复制姓名标题和当前可见正文.
- `复制全部` 复制当前可见的所有正文, 包括未保存修改.
- 复制不调用 draft 或 confirmation API.
- 某学生正文变化后, 该学生的 `已复制` 状态重置.
- 保存草稿仍是一次全局 CAS 请求.
- 两个确认按钮仍确认整份学生反馈.
- read-only super owner 能查看和复制, 但不能编辑, 保存或确认.
- plain-text history 继续显示原 Textarea, 不自动拆分.

### Regression

- 生成版本切换, revision 恢复, draft conflict 和未保存离开保护继续工作.
- 当前 class-commentary 权限隔离不变化.
- 现有 `class_commentary_memory` 学习和撤销链路不变化.
- 不出现 `class_feedback_*` 新代码, 新表或新 API.

## 实现切片

建议按以下顺序实现, 但作为一个完整功能分支合入:

1. 增加 schema model, canonicalization, validation 和单元测试.
2. 做 additive SQLite migration, generation 写入和双读 serializer.
3. 扩展 structured draft, confirmation, hash 和 legacy compatibility tests.
4. 更新 TypeScript types, normalizers 和 API payload.
5. 在现有结果 Card 内实现 Accordion, ScrollArea, 逐人编辑和复制.
6. 补前端交互测试, production build 和真实浏览器 smoke.
7. capability 默认关闭完成部署, 再按验收清单开启.

## 关键取舍

### 为什么 v1 不建逐学生表

当前保存, 冲突检测, 确认和学习都是一份全局 payload. 直接增加 JSON 快照可以最小改动地支持逐学生 UI, 又不制造一套与现有 revision 并行的逐学生版本系统. 当未来出现逐学生发送状态, 独立确认或家长渠道回执时, 再评估 normalized per-student delivery table.

### 为什么不解析历史文本

历史输出受 Skill, 姓名标题, 段落和 emoji 影响, 用正则无法稳定还原学生边界. 错分比保留旧 Textarea 更危险. 因此 schema version 是明确分界, 新数据结构化, 老数据原样读取.

### 为什么复制未保存文本

复制是老师把眼前内容带到外部沟通工具的动作. 如果按钮复制上次保存版本, 老师会看到一种内容却发出另一种内容. 保存和确认仍需显式动作, 所以复制当前可见文本不会削弱审计边界.

### 为什么校验失败不降级纯文本

一旦未经校验的模型输出被当作逐学生内容展示, 可能发生错学生, 漏学生或跨学生事实污染. 失败并提示重新生成比静默降级更符合家长反馈的准确性要求.
