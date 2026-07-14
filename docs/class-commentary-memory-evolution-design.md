# 课堂点评记忆与 Skill 进化设计

日期: 2026-07-14

状态: 设计 v3, 待最终确认后进入实现

## 1. 背景

当前课堂点评链路已经支持录音或文本输入, 转写确认, 到课学生选择, skill 选择, AI 生成和历史任务查看. 生成结果目前是只读文本, 老师只能复制, 无法在系统内修改, 确认或让系统学习修改结果.

本设计增加一个可审计的学习闭环:

1. AI 使用指定 skill 生成课堂点评.
2. 老师在系统内修改生成文本.
3. 老师显式确认是否将本次修改用于学习.
4. 系统永久保留 AI 原稿, 老师终稿和差异证据.
5. Mem0 从确认样本中提取老师表达偏好和学生历史事实.
6. 后续生成通过 Mem0 检索相关记忆并注入上下文.
7. 多次确认修改形成稳定规律后, 系统生成对应 skill 的候选新版本.
8. 老师本人查看差异和评测结果, 决定启用或回滚.

本设计只依据当前课堂点评实现, 2026-07-11 会议需求和本轮确认结论. 历史课堂反馈设计不作为本功能的需求来源.

## 2. 已确认的产品决策

### 2.1 采用 Mem0

Mem0 OSS 是本功能的记忆提取和检索层. 应用不再建设另一套独立的向量 RAG 管线.

Mem0 底层仍需要向量存储和 embedding 服务. 这些属于 Mem0 的运行依赖, 不视为第二套产品级 RAG.

### 2.2 暂不建设知识图谱

本阶段不建设知识点本体, 图关系, Graph RAG 或学生知识图谱.

现有错题知识标签和掌握度仍可作为学生记忆证据写入 Mem0. 将来如果建立统一知识点目录, 可以在不改变本设计事件模型的情况下增加知识图谱.

### 2.3 不存在公共 skill

每个 `skill_id` 对应一个具体老师的蒸馏 skill. 不设计公共 skill, 个人 fork 或机构级共享升级.

老师确认的修改只影响当前任务使用的 `skill_id`. 不同 skill 之间不共享风格记忆和进化证据.

### 2.4 老师本人是唯一确认人

编辑者和 skill 对应老师是同一人. 只有老师本人提交的确认结果可以进入学习和 skill 进化证据.

### 2.5 单次修改不直接改写 skill

单次确认修改可以立即更新 Mem0 记忆, 让下一次生成受益. 只有多个独立任务反复支持同一规律时, 才生成 skill 候选版本.

任何 skill 候选都不能自动激活. 激活和回滚均由老师本人操作.

### 2.6 学生记忆在机构内按权限共享

学生事实使用 `organization_id + student_id + subject_key` 作为范围. 同一机构内, 当前仍有该学生访问权限的老师可以检索同一学科的历史事实.

`source_teacher_user_id` 和 `source_skill_id` 只用于证据溯源, 撤销和审计, 不作为学生记忆的隔离维度. 风格记忆仍严格按 `organization_id + scope_skill_registry_id` 隔离.

### 2.7 新 revision 取代旧 revision evidence

再次确认代表老师用新终稿取代旧终稿. 无论新 revision 是否选择学习, 同 task 所有 earlier revision 的 active evidence 都会被 supersede, 未完成 extraction job 会进入 terminal `obsolete`, 旧 revision 也不能 retry. `确认但不学习`不会提取新 evidence, 因此它的准确语义是`保存新终稿, 撤销旧版学习, 不学习新版`.

### 2.8 每个 generation 独立保留草稿

草稿按 task + generation + teacher 独立保存. 在 generation A 和 B 之间切换不会互相覆盖草稿. 每条草稿使用递增 version 和 CAS, 旧标签页不能覆盖较新保存.

### 2.9 Skill 只使用 latest effective revision

每个 task 对一个 skill 最多贡献一条样本, 即 task `latest_revision_id`指向的 effective revision. 已被取代的 revision 和 superseded/revoked evidence 不参与候选支持数和评测权重.

### 2.10 v3 关键闭环

| 问题 | v3 的唯一方案 |
| --- | --- |
| AI 原稿会被重新生成覆盖 | 每次生成创建 immutable `class_commentary_generations`, revision 必须引用 `generation_id` |
| 确认幂等缺少数据约束 | `confirmation_request_id`和 payload hash 入 revision, transaction 同时创建 revision, draft sync, task cache 和 extraction job |
| SQLite 和 Mem0 无法原子双写 | SQLite desired state + item outbox operation + Mem0 worker + reconciliation |
| Skill owner 无可信来源 | `class_commentary_skills`显式 registry 和一次性 owner manifest import |
| 学生记忆范围未决 | 采用 A, 机构内按学生和学科共享, 每次检索实时检查学生访问权 |
| Active version 没有唯一事实 | Registry `active_version_id` + immutable activation event + CAS |
| 旧 revision 延迟 job 可能重新学习 | Confirmation 终止旧 job + worker 写入前 latest revision 双门禁 + obsolete 禁止 retry |
| 错题和掌握度会随时间变化 | Confirmation 冻结 immutable learning evidence snapshot, extraction/rebuild 禁止查询实时数据 |
| 草稿跨 generation 和标签页覆盖 | 每 generation 独立 draft + `draft_version` CAS |
| 多 revision 重复计权 | 每 task 只取 latest effective revision, 候选冻结实际 revision/evidence 集合 |

## 3. 目标

### 3.1 主要目标

- 允许老师修改课堂点评并保存草稿.
- 允许老师显式选择`确认并学习`或`确认但不学习`.
- 永久保留 AI 原稿, 老师终稿, diff, skill 快照, 课堂上下文和确认时 learning evidence 快照.
- 从确认修改中学习老师的表达风格, 结构, 长度, 措辞和关注重点.
- 记录与具体学生关联的可靠历史事实和后续关注点.
- 在后续生成时通过 Mem0 检索老师风格记忆和学生历史记忆.
- 从重复确认规律中生成可评测, 可确认, 可回滚的 skill 候选版本.
- 保证组织和学生之间的事实隔离, 保证不同 skill 之间的风格隔离, 并只向当前有学生访问权限的老师共享学生事实.

### 3.2 非目标

- 不建设知识图谱或 Graph RAG.
- 不建设独立于 Mem0 的文档向量库.
- 不做模型微调或自动训练基础模型.
- 不把一次修改直接写回外部 `SKILL.md` 文件.
- 不跨老师或跨 skill 共享风格记忆.
- 不向当前无学生访问权限的老师共享学生记忆.
- 不从未确认的草稿, 复制动作或输入过程学习.
- 不使用旧课堂反馈表或恢复旧课堂反馈 API.

## 4. 设计原则

### 4.1 SQLite 是事实来源

SQLite 保存 generation 原稿和输入快照, 终稿, 差异, 确认身份, 确认时 learning evidence 快照, skill registry 和版本, memory evidence, 目标状态, outbox operation 和评测结果. 即使 Redis 或 Mem0 不可用, 这些事实也不能丢失.

### 4.2 Mem0 是可重建的记忆索引

Mem0 保存经过提取的风格记忆和学生记忆, 并负责语义检索. 所有 Mem0 记录必须能追溯到 SQLite 中的 canonical memory record 和一条或多条确认 evidence.

如果 Mem0 数据损坏或需要迁移, 系统从 SQLite 当前 active canonical memory/evidence 重建 projection, 不重新提取 superseded revision. 只有 latest effective revision 可以在 extractor/schema 升级时使用原 immutable snapshot 重新提取.

### 4.3 风格和事实严格分离

老师风格记忆只能描述表达方式, 结构, 语气, 长度, 反馈维度和措辞偏好. 其中不能包含学生姓名, 学情事实或一次性课堂内容.

学生记忆只能描述该学生的已确认表现, 问题, 改进, 后续动作和证据. 其中不能包含老师的通用表达规则.

### 4.4 显式确认优先

系统不能把输入过程中的每一次变化当作学习信号. 只有明确提交的确认版本才能触发记忆提取.

### 4.5 失败不阻断核心流程

老师终稿保存成功后, Mem0 写入失败不能阻止复制和查看终稿. 失败任务进入可重试状态.

### 4.6 学习输入在确认时冻结

错题和掌握度只在老师确认 transaction 中生成安全摘要快照. Extraction, retry 和 rebuild 只能读取 revision 中的 immutable snapshot, 禁止重新查询实时错题或掌握度数据.

## 5. 用户流程

### 5.1 生成

现有上传, 转写, 转写确认, 到课学生选择和生成流程保持不变.

每次点击生成或重新生成都创建新的 immutable generation. 同一 task 可以有多个 generation, 后一次生成不能覆盖前一次生成. 生成时必须快照:

- 本次确认转写和 hash.
- 到课学生 ID 和姓名快照.
- 本次使用的 skill registry ID, skill version ID, skill 内容和内容 hash.
- provider, 模型, prompt 版本和生成请求标识.
- AI 原始生成文本.
- 本次检索并注入的 memory ID, scope, hash 和字符数.

老师确认时必须明确引用当前看到的 `generation_id`. 修改转写, roster, skill, 模型配置或 memory context 后再次生成, 都产生新的 generation, 不改变旧 revision 的证据链.

当前生成格式继续使用纯文本. 输出规则继续要求以学生姓名作为可见分节标签. 本阶段不强制迁移为 JSON 输出或学生卡片编辑器.

### 5.2 编辑

反馈结果区从只读 `pre` 改为可编辑 `Textarea`.

页面提供 3 个动作:

- `保存草稿`: 保存当前编辑结果, 不确认, 不学习.
- `确认但不学习`: 将当前版本保存为老师终稿, 不提取新 evidence; 再次修订时会 supersede 旧 revision evidence.
- `确认并学习`: 将当前版本保存为老师终稿, 并创建后台记忆任务.

每个 generation 有自己的草稿. 页面切换 generation 时恢复对应草稿, 不用 task 级单槽位覆盖其他 generation. 保存草稿必须提交当前 `draft_version`; 版本落后时返回冲突并提示老师选择保留当前页面或加载服务器新稿.

复制按钮复制当前 generation 的已保存草稿. 没有草稿时, 如果当前 effective revision 引用该 generation, 则复制其终稿; 否则复制该 generation 的 AI 原稿. 确认当前 generation 时, confirmation transaction 会把该 generation 草稿同步为本次终稿并递增 `draft_version`, 使确认前打开的旧标签页无法在确认后用旧 version 覆盖它. 其他 generation 草稿不变.

### 5.3 再次修订

老师确认后仍可选择`继续修订`. 再次确认会创建新的 immutable revision, 不覆盖旧 revision.

Mem0 记忆必须指向具体 revision. 新 revision 如果推翻旧结论, 后台任务先在 SQLite 保存目标状态和稳定 operation key, 再异步更新, supersede 或删除对应 Mem0 记忆.

任何新 revision 都使同 task earlier revisions 的 active evidence 进入 `superseded`, 未完成 extraction job 进入 `obsolete`. 这是确定性的版本替换, 不属于从新文本学习. `确认并学习`会同时为新 revision 创建 extraction job; `确认但不学习`不提取新 evidence, 因而旧版已学内容被撤销后不会自动替换. UI 必须在再次确认前明确提示这一结果.

确认时按 generation 的 organization, class, subject 和到课 roster 冻结相关错题与掌握度安全摘要. 后续源记录变化不会改变本 revision 的提取输入.

### 5.4 学习结果反馈

页面显示本次学习状态:

- 未学习.
- 排队中.
- 提取中.
- 已完成.
- 部分完成.
- 失败可重试.
- 已被新版取代, 不可重试.

完成后展示`本次学到的内容`, 分为老师风格和学生历史两组. 每条内容显示 canonical memory 摘要, 本人 evidence, 来源 revision, 当前有效 evidence 数量和`撤销我的来源`动作.

撤销只停用本人 evidence, 不删除原始 revision. 如果仍有其他 active evidence, 页面明确显示`已撤销我的来源, 该事实仍由其他证据支持`; 只有没有其他证据时 canonical memory 才停用.

## 6. 学习信号分类

后台提取器接收以下输入:

- AI 原稿.
- 老师终稿.
- Generation 原稿到当前终稿的累计规范化 diff.
- Previous revision 到当前终稿的增量规范化 diff.
- 当前 skill 快照.
- 到课学生快照.
- 确认转写.
- Revision 中确认时冻结的错题和掌握度安全摘要, 包括来源 ID, version/hash 和实际摘要文本.

提取器不得在后台执行时重新读取错题或掌握度实时表.

输出必须是结构化结果, 每项只允许属于以下类型之一.

### 6.1 `teacher_style`

示例:

- 更偏好短段落, 每段只表达一个重点.
- 批评前先说明学生已经做到的部分.
- 结尾需要给家长一个明确可执行动作.
- 避免正式报告语气.

### 6.2 `student_fact`

示例:

- 学生最近在绝对值分类讨论中仍会遗漏边界条件.
- 学生本次口算速度比上一次稳定.
- 下次需要继续检查草稿中的步骤书写.

学生事实只有在满足以下条件时才允许写入:

- 能映射到到课名单中的唯一 `student_id`.
- 内容得到本次转写, 老师终稿或现有确认记录支持.
- 不包含家长联系方式, 地址或无关个人信息.

无法唯一映射学生时, 该项进入`仅保留证据`, 不写入 Mem0 学生空间.

### 6.3 `evaluation_only`

以下内容只作为评测或一次性修正证据:

- 当前课程临时安排.
- 只适用于本次课堂的活动信息.
- 纯错字或标点修正.
- 无法判断是否为长期偏好的改写.
- 老师选择`确认但不学习`的完整 revision.

### 6.4 无修改确认

`accepted_without_edit`始终表示当前终稿与 generation 原稿相同. `unchanged_from_previous_revision`单独表示与上一 revision 相同. 无修改确认不创建新的风格记忆. 只有该 revision 仍是 task latest effective revision 时, 它才作为每 task 一次的 replay evaluation 和接受率样本, 不计入风格支持次数.

## 7. Mem0 范围和 RAG

### 7.1 记忆空间

老师风格记忆使用以下精确范围:

```text
organization_id + scope_skill_registry_id + memory_type=teacher_style
```

学生记忆使用以下精确范围:

```text
organization_id + student_id + subject_key + memory_type=student_fact
```

学生记忆是机构内共享事实. `source_teacher_user_id` 和 `source_skill_id` 作为证据来源保存, 不参与学生记忆 scope. Registry 主键 `scope_skill_registry_id`只用于风格隔离, 外部字符串 `skill_id`不作为 Mem0 scope key.

检索学生记忆前, 后端必须根据当前数据库关系确认登录老师仍能访问该学生. 不能因为知道 `student_id` 就直接查询 Mem0.

### 7.2 `subject_key`事实来源

`subject_key`不能由前端自由填写或从自然语言临时推断. 权威值来自班级或课程的受控字段. Migration 根据受控映射规范化现有 `classes.subject`, 例如`数学`和`math`映射为 `math`; 不能把所有历史班级一律假定为数学. 未识别值保留为 NULL, 后续只能使用受控学科目录中的 canonical key.

显示名称可以是`数学`, 但存储和检索必须统一为 `math`. 未能解析 canonical key 时不检索或写入学生记忆, 并记录可观察的跳过原因; 普通无记忆生成仍可继续.

### 7.3 Metadata

每条 Mem0 记录至少包含:

```json
{
  "organization_id": 1,
  "scope_skill_registry_id": 12,
  "student_id": null,
  "subject_key": null,
  "memory_type": "teacher_style",
  "generation_id": 122,
  "created_from_revision_id": 123,
  "memory_record_id": 456,
  "record_version": 1,
  "evidence_count": 1,
  "operation_key": "memory-record-456-add-v1",
  "status": "active",
  "confidence": 0.9,
  "occurred_at": "2026-07-14T10:00:00Z"
}
```

所有检索必须先完成应用数据库权限校验, 再使用 `organization_id` 和 scope key 做精确 metadata 过滤, 最后执行语义相似度排序.

Style query 过滤 numeric `scope_skill_registry_id`. Student fact 的 `scope_skill_registry_id`必须为 null, query 只能按 organization, student 和 subject 过滤, 禁止按任何 source skill 过滤. 多来源 provenance 只保存在 SQLite evidence, 避免把共享学生事实误隔离到来源 skill.

### 7.4 检索策略

每次生成执行 2 类检索:

1. 使用当前任务, 当前 skill 和明确生成要求查询老师风格记忆.
2. 对转写中明确提到, 且存在于当前 generation 确认到课 roster 的每位学生, 使用本次课堂主题查询该学生历史记忆.

Mem0 返回结果只作为候选. Adapter 必须按 `memory_record_id`批量回查 SQLite, 仅保留 `desired_status=active`, metadata `record_version`等于 SQLite 当前版本, 至少一条 active evidence 且 scope/当前访问权限仍有效的记录. 因 revoke 或 supersede 尚未同步到 Mem0 的旧结果必须立即丢弃并标记 reconciliation, 不能等待修复完成后才停止注入.

默认限制:

- 老师风格记忆最多 8 条.
- 每位学生历史记忆最多 5 条.
- 总 memory context 默认不超过 3000 个中文字符.
- 相同 revision 或语义近似内容在注入前去重.
- 低置信度, 已撤销和已 supersede 记录不得注入.

这些限制通过运行配置调整, 不在 prompt 中硬编码.

学生历史可能由同机构内不同老师提供. 检索结果必须保留来源和时间, 相互冲突时不能静默合并为确定事实.

### 7.5 上下文优先级

事实冲突时使用以下优先级:

1. 本次老师确认的转写和到课名单.
2. 当前数据库中的确认事实和错题证据.
3. Mem0 学生历史记忆.

风格冲突时使用以下优先级:

1. 老师本次明确选择的生成要求.
2. 已确认的当前 skill 风格记忆.
3. 当前激活的 skill 版本.

Memory 不得把历史事实改写为本次已经发生的事实. Prompt 必须明确区分`本次证据`和`历史参考`.

### 7.6 Mem0 运行方式

- 使用 Mem0 OSS, 不依赖 Mem0 Cloud.
- Flask 请求只做检索, 不在请求内执行重型记忆归纳.
- 记忆提取, 合并, 更新, 删除和 reconciliation 由课堂点评记忆专用 RQ worker 执行, 不复用错题上传队列.
- 生产向量存储使用独立 Qdrant 服务.
- 本地开发可以使用隔离的 Qdrant local path, 但不能将 local path 模式用于 Flask 和 RQ 多进程生产环境.
- Embedding provider 通过运行配置注入, 必须支持中文, 不在代码中硬编码供应商.
- 应用通过 `ClassCommentaryMemoryService` adapter 调用 Mem0, 业务代码不能直接依赖 Mem0 SDK.

## 8. 数据模型

先为 `classes`增加 nullable `subject_key`. Migration 只根据受控 alias mapping 回填已知学科; 未知值保持 NULL. 后端从 class 读取并快照到 generation, 前端不能提交或覆盖该字段.

### 8.1 `class_commentary_tasks`扩展

Task 只表示工作流容器和最新状态缓存, 不再承担 AI 原稿的审计职责. 新增字段:

- `confirmed_transcript_version`: 每次老师确认或修改转写时原子递增.
- `final_feedback_text`: 最新确认终稿, 仅作为快速读取缓存.
- `latest_generation_id`: 最新 generation 指针.
- `latest_revision_id`: 最新 revision 指针.
- `generation_seq`: 已分配的最新 generation 序号.
- `feedback_confirmed_at`: 最新确认时间.
- `feedback_revision_no`: 最新 revision 序号.

现有 `feedback_text`在 migration 期间只作为兼容缓存. 历史数据迁移成首条 generation 后, generation 表才是 AI 原稿的唯一事实来源. 再次生成不得覆盖旧 generation.

### 8.2 `class_commentary_feedback_drafts`

每个 generation 独立保存一条老师当前草稿:

- `id`.
- `organization_id`.
- `task_id`.
- `generation_id`.
- `teacher_user_id`.
- `based_on_revision_id` nullable.
- `feedback_text`.
- `content_hash`.
- `draft_version`.
- `created_at`.
- `updated_at`.

唯一约束:

```text
UNIQUE(task_id, generation_id, teacher_user_id)
```

首次保存要求 `expected_draft_version=0`, 创建 version 1. 后续保存执行 conditional UPDATE, 只有数据库当前 `draft_version`等于请求 expected version 时才更新文本并原子加 1. 更新行数不是 1 时返回 `409 Conflict`和当前 draft metadata, 不覆盖服务器草稿.

Draft 是可变工作区, 不进入学习输入, 也不替代 immutable revision. Generation A 和 B 的草稿可以同时存在.

新 generation 不自动继承旧 generation 草稿. `继续修订`可以把同 generation 的 revision 记录为 `based_on_revision_id`; 跨 generation 复用必须由老师显式复制文本.

确认时必须使用同一 CAS 规则同步当前 generation 草稿: 无草稿且 expected version 为 0 时创建 version 1; 有草稿时只有当前 version 等于 expected version 才把草稿更新为终稿, 原子递增 version 并把 `based_on_revision_id`设为新 revision. 这样 confirmation 本身也是该草稿的一次受控写入. 它不能删除或修改其他 generation 的草稿.

### 8.3 `class_commentary_generations`

每次生成或重新生成创建一条独立记录:

- `id`.
- `organization_id`.
- `task_id`.
- `generation_no`.
- `generation_request_id`.
- `generation_request_payload_hash`: 在 Mem0 检索和模型调用前计算的 canonical 请求 hash.
- `teacher_user_id`.
- `class_id`.
- `subject_key` nullable when class subject is not mapped.
- `confirmed_transcript_version`.
- `confirmed_transcript_snapshot`.
- `confirmed_transcript_hash`.
- `attending_roster_snapshot_json`.
- `attending_roster_hash`.
- `attending_roster_explicit`: 客户端是否显式提交 attendance selection. 它参与 request intent, 用于区分"明确选择全班"与"省略字段采用默认全班".
- `skill_registry_id`.
- `skill_id`.
- `skill_version_id`.
- `skill_content_snapshot`.
- `skill_content_hash`.
- `model_provider`.
- `model_name`.
- `model_parameters_json`.
- `prompt_version`.
- `prompt_payload_snapshot_json`: 实际发送给模型的完整可审计 payload, 按隐私规则存储.
- `prompt_payload_hash`.
- `memory_context_snapshot_json`: 实际注入文本, memory record ID, Mem0 ID, scope, source revision, hash 和字符数.
- `memory_context_hash`.
- `execution_snapshot_status`: `pending`, `ready`. 只表示 prompt 和 memory execution snapshot 是否已冻结, 不代替 generation 终态.
- `execution_snapshot_finalized_at` nullable.
- `generated_feedback_text`.
- `origin`: `runtime`, `legacy_migration`.
- `snapshot_completeness`: `complete`, `partial`. 该字段描述可永久还原的 generation core snapshot; prompt 和 memory execution snapshot 是否已冻结由 `execution_snapshot_status`单独表达.
- `missing_snapshot_fields_json`.
- `status`: `generating`, `succeeded`, `failed`.
- `error_code` nullable.
- `created_at`.
- `completed_at` nullable.

唯一约束:

```text
UNIQUE(task_id, generation_no)
UNIQUE(task_id, generation_request_id)
```

Canonical generation request hash 包含 task ID, `confirmed_transcript_version`, transcript hash, canonical subject key, attendance IDs, attendance 字段是否显式提交, skill registry/version 和显式生成选项. 它不包含 Mem0 检索结果, prompt payload hash 或 memory context hash. Auth 和 task owner 校验后, 先按 `task_id + generation_request_id`查重. 命中时只校验客户端显式提交的 skill 和 attendance intent 是否与原 generation 一致, 不重新读取 live transcript, roster, skill active 状态, 模型配置或 Mem0; 一致则返回原 generation, 冲突则返回 409.

确认或修改转写使用 `BEGIN IMMEDIATE`递增 task `confirmed_transcript_version`; 有现存确认转写的旧 task migration 为 version 1, 无确认转写为 0. Generation transaction 同时读取 version, text 和 hash, 不能用通用 `updated_at`代替 transcript version.

创建请求使用 `BEGIN IMMEDIATE` transaction 递增 task `generation_seq`, 插入 generation, 并设置 `latest_generation_id`. 唯一冲突时按 request ID 重读并返回幂等结果或 `409 Conflict`, 不返回 500.

创建请求先在 SQLite transaction 内预留 generation 并冻结 transcript, roster, skill version/content, model 和 request hash. 此时 `execution_snapshot_status=pending`. Transaction commit 后才检索 Mem0, 且只能用 generation 内的冻结输入组装 prompt. 模型调用前, 以一次 conditional update 永久写入实际 prompt payload 和 memory context, 并把 execution snapshot 改为 `ready`; 已 ready 的 execution snapshot 不可覆盖. 模型只消费数据库重读出的 ready prompt snapshot. 这样模型实际输入和审计快照保持一致, 又不把外部 Mem0 调用放进 SQLite transaction.

`generated_feedback_text`只能写入一次. 状态进入 `succeeded`或`failed`后, 输入, 输出和错误证据不可覆盖. 同一生成请求且 payload 相同时返回原 generation; request ID 相同但 payload 不同时返回冲突. 进程在 reservation 后退出时, 同一 request ID 返回原 `generating` generation 和 202, 不再次收费或调用模型; task 的 `generating`缓存状态不阻止使用新 request ID 创建新 generation. 主动重试使用新的 request ID.

并发生成完成时, 只有 task 当前仍指向该 generation, 且 task `confirmed_transcript_version`仍等于 generation 冻结版本时, 才能更新兼容缓存. 较早请求晚完成或生成期间转写被修改时, 只更新自己的 generation 终态, 不能覆盖较新的 `latest_generation_id`, 新转写状态或页面结果.

旧 `feedback_text`迁移为 `origin=legacy_migration`的 generation. 只迁移真实存在的字段, 不把旧全班 roster 伪装为到课 roster, 不伪造旧 prompt 或 memory context. 缺失字段写入 `missing_snapshot_fields_json`, `snapshot_completeness=partial`. `complete`约束只适用于新 runtime generation.

Partial legacy generation 可以查看和`确认但不学习`, 不能提交 `learn_requested=true`. 老师必须基于当前转写, roster, registry skill 和 memory context 重新生成 complete runtime generation 后才能学习.

### 8.4 `class_commentary_revisions`

每次确认创建一条 immutable 记录:

- `id`.
- `organization_id`.
- `task_id`.
- `generation_id`.
- `teacher_user_id`.
- `revision_no`.
- `confirmation_request_id`.
- `confirmation_payload_hash`.
- `previous_revision_id` nullable.
- `confirmed_draft_version`: 本次 confirmation transaction 结束时的 draft version.
- `confirmed_draft_snapshot_json`: 本次 transaction 返回给客户端的完整 immutable draft snapshot.
- `final_feedback_text`.
- `generation_diff_json`: generation 原稿到当前终稿.
- `previous_revision_diff_json` nullable: previous revision 终稿到当前终稿.
- `learning_evidence_schema_version`.
- `learning_evidence_selector_version`.
- `learning_evidence_snapshot_json`.
- `learning_evidence_source_refs_json`: source type, record ID, monotonic source version if present, otherwise source updated_at, plus content hash.
- `learning_evidence_hash`.
- `learning_evidence_captured_at`.
- `learning_evidence_completeness`: `complete`, `partial`, `empty`.
- `learning_evidence_missing_sources_json`.
- `learn_requested`.
- `accepted_without_edit`.
- `unchanged_from_previous_revision`.
- `confirmed_at`.

唯一约束:

```text
UNIQUE(task_id, revision_no)
UNIQUE(task_id, confirmation_request_id)
```

Revision 不保存可变化的 memory job 状态或错误. 它通过 `generation_id`永久引用当时的原稿, 确认转写, roster, skill, 模型和 memory context 快照.

确认接口必须使用 `BEGIN IMMEDIATE`并在同一个 SQLite transaction 内:

1. 以 `confirmation_request_id + confirmation_payload_hash`检查幂等或冲突.
2. 确认 generation 已 `succeeded`, 属于同一 task, organization 和 owner, `expected_draft_version`仍为当前 generation 草稿版本; `learn_requested=true`时 generation 还必须是 complete runtime.
3. 按 generation organization, class, subject 和到课 roster 选择错题与掌握度来源, 冻结 deterministic safe summary, source refs 和 hash. `learn_requested=false`保存 canonical empty snapshot.
4. 原子递增 task `feedback_revision_no`并创建 revision.
5. 以步骤 2 校验的 expected version CAS upsert 当前 generation 草稿为终稿, 递增 `draft_version`并关联新 revision; 其他 generation 草稿不变. 将 CAS 后 draft version 和完整响应 snapshot 写入本 revision 的 immutable confirmation snapshot.
6. 更新 task 的最新终稿缓存和 `latest_revision_id`.
7. 将同 task 所有旧 revision 的 `queued`, `running`, `retry_wait`, `failed` extraction job 标记为 `obsolete`, 并记录本次 revision.
8. 将同 task 所有旧 revision 的 active evidence 标记为 `superseded`, 并在 canonical record 无其他 active evidence 时创建对应 outbox operation.
9. 当 `learn_requested=true`时创建新 revision 的 memory extraction job.

任一步失败都回滚该 transaction. 重试同一 request ID 且 payload 相同时返回已存在的 revision, 当时保存的 confirmed draft snapshot 和 job, 不读取后来可能已变化的 live draft, 不重复创建. 同一 request ID 对应不同 `generation_id`, `final_feedback_text`, `learn_requested`或`expected_draft_version`时返回 `409 Conflict`. 迁移前的 legacy revision 没有可信的首次 draft snapshot 时保持 version 0 和 unavailable, 禁止用当前 live draft 伪造回填.

RQ enqueue 只能在 transaction commit 后执行. Enqueue 失败不能删除已提交的 job; dispatcher 必须周期扫描 committed `queued` job 并补投, 因此 SQLite 中的 job 本身也是可靠投递事实.

Learning snapshot 内保存提取器实际可读的安全摘要文本, 不只是 source IDs. Selector 固定数据范围, 上限和排序, canonical JSON 固定 key 和 item 顺序. `learning_evidence_hash`对以下完整 canonical envelope 计算: schema version, selector version, captured at, snapshot JSON, source refs JSON, completeness 和 missing sources JSON. 修改任一内容都必须触发 hash mismatch. 只能选择同 organization, canonical subject 和 generation 到课 roster 内学生的来源. Source refs 优先保存 monotonic row version; 当前来源没有 row version 时保存 `source_id + source_updated_at + source_content_hash`, 不能把 `updated_at`本身称为版本. 即使源错题或掌握度记录之后更新或删除, extraction/retry/rebuild 仍使用相同 immutable input. Snapshot 为 partial 时只使用已冻结项目并记录 missing reason, 不允许 worker 用实时数据补齐.

### 8.5 `class_commentary_skills`

这是 skill 归属和 active 指针的唯一 registry:

- `id`.
- `organization_id`.
- `skill_id`.
- `owner_teacher_user_id`.
- `source_type`: `external_skill_package`或`database`.
- `source_path` nullable.
- `source_content_hash`.
- `active_version_id` nullable only inside initial import transaction.
- `status`: `active`, `disabled`.
- `created_at`.
- `updated_at`.

唯一约束:

```text
UNIQUE(organization_id, skill_id)
```

不能从文件名, 前端参数或最近使用者推断 owner. 现有外部 skill 必须通过一次性 import 明确绑定 `organization_id` 和 `owner_teacher_user_id`, 并把文件内容登记为 version 1. 未登记或 owner 不明确的 skill 不出现在课堂点评 skill 列表, 也不能用于生成.

Registry 先以 `active_version_id=NULL`插入, version 1, pointer 和初始 activation event 必须在同一个 SQLite transaction 完成. Transaction 对外提交后, `status=active`的 registry 不允许 NULL pointer.

实现提供一次性 import command, 输入显式 manifest: `organization_id`, `skill_id`, `owner_teacher_user_id`, `source_path`. Command 校验 organization, 用户和文件内容后再登记, 不提供`首次使用者自动成为 owner`的兼容路径. 具体生产 owner mapping 是上线数据准备项, 不阻塞代码开发.

所有 skill 列表, 生成, 候选, 激活和回滚请求都先从 registry 解析并校验当前用户就是 owner. 外部 `SKILL.md`只保留为初始来源, 不由运行时自动覆盖.

### 8.6 `class_commentary_skill_versions`

每个 registry skill 拥有独立版本链:

- `id`.
- `organization_id`.
- `skill_registry_id`.
- `version_no`.
- `version_kind`: `imported`, `candidate`.
- `candidate_build_id` nullable.
- `content`.
- `content_hash`.
- `base_version_id` nullable.
- `source_snapshot_hash` nullable.
- `evaluation_snapshot_json`.
- `evaluation_hash`.
- `review_status`: `not_required`, `pending`, `approved`, `rejected`.
- `created_at`.
- `reviewed_at` nullable.

唯一约束:

```text
UNIQUE(skill_registry_id, version_no)
UNIQUE(candidate_build_id)
```

版本自身不使用 `active`或`rolled_back`状态. 当前生效版本只由 `class_commentary_skills.active_version_id`决定, 避免候选生命周期和激活历史混为一谈.

Imported version 的 `candidate_build_id`为空. Candidate version 必须与 build 变为 `succeeded`在同一 transaction 完成. Candidate content, frozen source hash 和 evaluation snapshot 创建后 immutable.

### 8.7 `class_commentary_skill_candidate_builds`

Candidate 请求先冻结输入, 再执行模型生成和 replay evaluation:

- `id`.
- `organization_id`.
- `skill_registry_id`.
- `candidate_request_id`.
- `candidate_payload_hash`.
- `expected_active_version_id`.
- `base_version_id`.
- `source_cutoff_at`.
- `selection_policy_version`.
- `source_snapshot_hash`.
- `effective_task_count`.
- `supporting_task_count`.
- `status`: `queued`, `running`, `retry_wait`, `succeeded`, `failed`, `obsolete`.
- `attempt_count`.
- `claim_token` nullable.
- `claim_owner` nullable.
- `next_attempt_at` nullable.
- `candidate_version_id` nullable.
- `last_error` nullable.
- `created_at`.
- `started_at` nullable.
- `completed_at` nullable.

唯一约束:

```text
UNIQUE(skill_registry_id, candidate_request_id)
```

同一 request ID 且 payload 相同时返回原 build, payload 不同时返回 `409 Conflict`. Candidate API 不接受客户端提供 revision 或 evidence IDs.

创建 build 的 `BEGIN IMMEDIATE` transaction 必须:

1. 校验 registry owner 和 `expected_active_version_id`.
2. 选择目标 skill 每个 task 的 latest effective revision, 每个 task 最多一条.
3. 只选择 effective revision 对应的 active `teacher_style` evidence.
4. 使用 `COUNT(DISTINCT task_id)`校验有效任务和风格支持阈值.
5. 写入 immutable candidate revision/evidence rows 和 source snapshot hash.
6. Commit 后将 build 投递到课堂点评专用 RQ queue.

`source_snapshot_hash`覆盖排序后的 task/revision/evidence IDs 和 hashes, base version ID/hash, threshold config 和 `selection_policy_version`. 当前阶段默认使用所有符合条件的 effective tasks; 将来增加抽样上限必须升级 selection policy version.

Candidate worker 只读取 frozen rows. 开始生成前和创建 version 的 transaction 内都要重新验证 frozen revision 仍 effective, supporting evidence 仍 active, base version 仍是 expected active version. 任一失效时 build 进入 `obsolete`, 不创建 candidate version. Version 创建后发生的新变化不改写 frozen snapshot, 只让 candidate 派生为 stale.

Worker 使用 `BEGIN IMMEDIATE`和 conditional claim 防止重复 enqueue 并发创建版本. Claim 只允许 `queued`, 或 `retry_wait AND next_attempt_at <= now`, 且 `attempt_count < 3`; 同一 UPDATE 原子执行 `attempt_count += 1`, 写新 claim token, owner 和 `started_at`, 清空 `next_attempt_at`并转为 `running`. 更新行数不是 1 时立即退出. Finalization 再次校验 build 仍为 `running`, claim token 匹配且 frozen sources 有效, 然后在同一 transaction 插入 candidate version 和 evaluation snapshot, 写 `candidate_version_id`, 并把 build 标记为 `succeeded`. 任一步失败都回滚, 不能留下无 build 终态的孤立 version. 所有成功, 失败和 retry 状态写入必须匹配当前 token. 第 1, 2 次失败分别设置 60 和 300 秒后的 `next_attempt_at`; 第 3 次失败后进入 `failed`. 老师再次生成候选时使用新 request ID, 重新冻结当时 effective source set.

### 8.8 `class_commentary_skill_candidate_revisions`

每个 build 冻结实际使用的 task/revision 样本:

- `id`.
- `organization_id`.
- `candidate_build_id`.
- `task_id`.
- `revision_id`.
- `sample_role`: `support`, `evaluation`, `support_and_evaluation`.
- `revision_snapshot_hash`.
- `selection_policy_version`.
- `created_at`.

唯一约束:

```text
UNIQUE(candidate_build_id, task_id)
```

Revision 必须是 target registry owner, organization 和 skill 的 latest effective revision. 如果 task 最新 revision 使用另一个 skill, 该 task 不计入当前 skill, 不能回退使用更早 revision.

### 8.9 `class_commentary_skill_candidate_evidence`

每个 build 冻结实际使用的 active style evidence:

- `id`.
- `organization_id`.
- `candidate_build_id`.
- `candidate_revision_id`.
- `memory_evidence_id`.
- `memory_record_id`.
- `evidence_hash`.
- `record_version_at_selection`.
- `evidence_status_at_selection`.
- `created_at`.

唯一约束:

```text
UNIQUE(candidate_build_id, memory_evidence_id)
UNIQUE(candidate_build_id, candidate_revision_id, memory_record_id)
```

同一 `memory_record_id`代表一条 canonical 风格规则. 第二条唯一约束保证同一 task/revision 对同一规则最多冻结一条 evidence, 因而最多贡献一次支持. Superseded 或 revoked evidence 不得进入 frozen set.

### 8.10 `class_commentary_skill_activation_events`

每次激活和回滚都创建 immutable event:

- `id`.
- `organization_id`.
- `skill_registry_id`.
- `activation_request_id`.
- `activation_payload_hash`.
- `from_version_id` nullable.
- `to_version_id`.
- `actor_user_id`.
- `reason`: `initial_import`, `candidate_approved`, `rollback`.
- `evaluation_snapshot_json`.
- `created_at`.

唯一约束:

```text
UNIQUE(skill_registry_id, activation_request_id)
```

Handler 完成登录, organization 和 registry owner 授权后, 才按 registry + request ID 查 event. 已存在且 payload hash 相同时返回原成功结果, payload 不同时返回 `409 Conflict`. 只有 event 不存在的新请求才检查 expected pointer 并执行 CAS.

激活在一个 SQLite transaction 内写 event 并使用 compare-and-swap 移动指针:

```sql
UPDATE class_commentary_skills
SET active_version_id = :to_version_id
WHERE id = :skill_registry_id
  AND active_version_id IS :expected_from_version_id;
```

更新行数不是 1 时返回版本冲突, 不能覆盖另一个并发激活. 回滚本质上是指向旧版本的新 activation event.

### 8.11 `class_commentary_memory_records`

SQLite 中的 memory 目标状态和可审计映射:

- `id`.
- `organization_id`.
- `created_from_revision_id`.
- `created_by_teacher_user_id`.
- `created_from_skill_registry_id`.
- `scope_skill_registry_id` nullable.
- `student_id` nullable.
- `subject_key` nullable.
- `memory_type`: `teacher_style`, `student_fact`.
- `memory_text`.
- `normalized_memory_text`.
- `normalization_version`.
- `memory_text_hash`.
- `scope_hash`.
- `canonical_key`.
- `creation_evidence_snapshot_json`.
- `confidence`.
- `record_version`.
- `mem0_memory_id` nullable.
- `desired_status`: `active`, `superseded`, `revoked`, `deleted`.
- `applied_status`: `not_applied`, `active`, `superseded`, `revoked`, `deleted`, `unknown`.
- `superseded_by_id` nullable.
- `created_at`.
- `updated_at`.

`desired_status`是 SQLite 事实, `applied_status`只是最近一次已确认的 Mem0 投影. 两者不一致时必须存在 pending 或 reconciliation operation.

`teacher_style`必须填写 `scope_skill_registry_id`, 且 `student_id`为空. `student_fact`必须填写 `student_id`和 canonical `subject_key`, 且 `scope_skill_registry_id`为空. `created_from_skill_registry_id`只记录首次来源, 后续来源保存在 evidence. Memory 内容一旦创建不可改写; 内容更新创建新 record 并 supersede 旧 record.

`teacher_style.subject_key`必须为 NULL. `student_fact.subject_key`必须为 canonical key. `scope_hash`由 memory type 和对应精确 scope 的 canonical JSON 计算; `canonical_key`由 `normalization_version + normalized_memory_text`计算. 在 `BEGIN IMMEDIATE` transaction 内先查找或创建 canonical record, 再 attach evidence. Active canonical item 使用 partial unique index 防止并发重复:

```sql
CREATE UNIQUE INDEX uq_class_commentary_active_memory_item
ON class_commentary_memory_records (
  organization_id,
  memory_type,
  scope_hash,
  canonical_key
)
WHERE desired_status = 'active';
```

Canonical record 上的 created-from 字段只记录首次创建来源. 所有当前来源和撤销状态以 evidence 表为准. 如果同一事实仍有其他独立 active evidence, reconciliation 保留该事实并更新 evidence count.

### 8.12 `class_commentary_memory_evidence`

共享学生事实和风格规律都允许拥有多条独立证据:

- `id`.
- `organization_id`.
- `memory_record_id`.
- `revision_id`.
- `extraction_job_id`.
- `source_teacher_user_id`.
- `source_skill_registry_id`.
- `evidence_hash`.
- `status`: `active`, `revoked`, `superseded`.
- `created_at`.
- `updated_at`.

唯一约束:

```text
UNIQUE(memory_record_id, revision_id, evidence_hash)
```

撤销某位老师的来源只停用对应 evidence. 只有全部有效 evidence 都失效时, canonical memory record 才转为 `revoked`并创建 Mem0 revoke 或 delete operation.

### 8.13 `class_commentary_memory_evidence_events`

Evidence 撤销使用 immutable 幂等事件:

- `id`.
- `organization_id`.
- `evidence_id`.
- `action`: `revoke`.
- `request_id`.
- `payload_hash`.
- `actor_user_id`.
- `created_at`.

唯一约束:

```text
UNIQUE(evidence_id, request_id)
```

Evidence event, evidence status 和必要的 canonical record/outbox 变化必须在同一个 SQLite transaction 内完成. 同一 request ID 且 payload 相同时返回原 event, payload 不同时返回 `409 Conflict`.

### 8.14 `class_commentary_memory_extraction_jobs`

用于提取器幂等, 重试和版本审计:

- `id`.
- `organization_id`.
- `revision_id`.
- `request_key`.
- `extractor_version`.
- `memory_schema_version`.
- `extraction_input_hash`.
- `learning_evidence_hash`.
- `status`: `queued`, `running`, `retry_wait`, `extracted`, `failed`, `integrity_failed`, `obsolete`.
- `attempt_count`.
- `started_at` nullable.
- `claim_token` nullable.
- `claim_owner` nullable.
- `next_attempt_at` nullable.
- `last_error`.
- `obsolete_reason` nullable.
- `obsoleted_by_revision_id` nullable.
- `obsoleted_at` nullable.
- `result_summary_json`.
- `created_at`.
- `updated_at`.
- `completed_at` nullable.

唯一约束:

```text
UNIQUE(request_key)
UNIQUE(revision_id, extractor_version, memory_schema_version)
```

`request_key`由 `revision_id + extraction_input_hash + extractor_version + memory_schema_version`稳定计算. `extraction_input_hash`覆盖 AI 原稿, 终稿, 两类 diff, skill snapshot, roster, transcript 和 learning evidence hash. 升级提取器或 schema 可以创建新的重建 job, 但同一版本组合不能重复. `extracted`只表示结构化提取和 SQLite outbox transaction 完成, 不表示 Mem0 operation 已应用. `integrity_failed`和`obsolete`都是 terminal 状态, 不允许普通 retry.

Worker 领取 job 时使用 `BEGIN IMMEDIATE`和 conditional UPDATE. Claim 只允许 `queued`, 或 `retry_wait AND next_attempt_at <= now`, 且 `attempt_count < 4`; 同一 UPDATE 转为 `running`, 原子执行 `attempt_count += 1`, 写唯一 `claim_token`, worker name 和 `started_at`, 并清空 `next_attempt_at`. 更新行数不是 1 时立即退出, 防止重复 enqueue 绕过 backoff 或并发提取.

Worker 保存 evidence, canonical memory 和 outbox 的 `BEGIN IMMEDIATE` transaction 必须再次校验 `task.latest_revision_id == job.revision_id`, `job.status=running`和 `job.claim_token`仍属于本次 execution. 任一条件失败时不写任何 evidence 或 operation, 并将仍未 terminal 的 job 标记 `obsolete`. 这条 commit-time gate 与 confirmation-time obsolete 更新共同封死延迟旧 job 竞态.

Worker 所有成功, 异常和 timeout 回写都必须带 `status=running + claim_token`条件, 不能把 confirmation 已写入的 `obsolete`改回 retry 状态. 可捕获异常在退出前写 `retry_wait`, `next_attempt_at`和错误; 硬退出由 reconciliation 在 `started_at + 300s`后恢复, 但恢复前也必须确认 revision 仍 effective. 第 1, 2, 3 次失败分别在 30, 120, 600 秒后重试; 第 4 次失败后进入 `failed`, 等待显式 retry.

### 8.15 `class_commentary_memory_retry_events`

`memory-retry`使用 immutable event 保证幂等:

- `id`.
- `organization_id`.
- `scope_type`: `revision`, `operation`.
- `scope_id`.
- `revision_id` nullable.
- `request_id`.
- `payload_hash`.
- `actor_user_id` nullable.
- `actor_service` nullable.
- `extraction_job_id` nullable.
- `target_operation_ids_json`.
- `created_at`.

唯一约束:

```text
UNIQUE(organization_id, scope_type, scope_id, request_id)
```

User `memory-retry`使用 revision scope 和 actor user. Auth 完成后, handler 必须使用 `BEGIN IMMEDIATE`: 先在锁内按 request ID 和 payload hash 查幂等结果, 未命中时重新读取 `task.latest_revision_id`, `learn_requested`, job 状态和 eligible operation IDs, 然后在同一 transaction 创建 retry event并重置 frozen target IDs. 只有 effective revision 可以 retry; superseded revision, `obsolete` job, `integrity_failed` job, `learn_requested=false`或没有 eligible target 时返回 `409 revision_not_retryable`, 且不写 event. 这使 retry 与新 confirmation 串行化, 不能在事务外预检后重置已被取代的 job. 无 revision owner 的 cleanup operation 只能由内部 maintenance command 使用 operation scope 和受信 service identity 重试, 不暴露管理员代老师操作的产品 API. Event snapshot 保留上一个自动周期的 attempt count 和错误, 然后把新自动周期的 `attempt_count`重置为 0. 同一 request ID 且 payload 相同时返回原 event, payload 不同时返回 `409 Conflict`. 重置现有 extraction job, 不创建违反 extractor/schema unique constraint 的新 job.

### 8.16 `class_commentary_memory_operations`

每个 memory item 的 Mem0 外部操作都有独立 outbox 记录:

- `id`.
- `organization_id`.
- `extraction_job_id` nullable.
- `memory_record_id`.
- `source_type`: `revision`, `evidence_event`, `cleanup`, `reconciliation`.
- `source_id` nullable.
- `operation_type`: `add`, `update`, `supersede`, `revoke`, `delete`.
- `operation_key`.
- `operation_version`.
- `expected_record_version`.
- `target_state_json`.
- `target_state_hash`.
- `mem0_memory_id` nullable.
- `status`: `pending`, `running`, `applied`, `retry_wait`, `reconcile_needed`, `obsolete`, `failed`.
- `attempt_count`.
- `started_at` nullable.
- `lease_token` nullable.
- `lease_owner` nullable.
- `lease_until` nullable.
- `next_attempt_at` nullable.
- `last_error` nullable.
- `extractor_version`.
- `memory_schema_version`.
- `created_at`.
- `updated_at`.
- `applied_at` nullable.

唯一约束:

```text
UNIQUE(operation_key)
UNIQUE(memory_record_id, operation_version)
```

`operation_key`稳定计算为 `cc-memory-{memory_record_id}-v{operation_version}-{target_state_hash}`.

创建或改变 memory record 的目标状态时, 必须在同一个 SQLite transaction 内递增 record version 并创建 stable operation.

每个 RQ execution 先以 `BEGIN IMMEDIATE`和 conditional UPDATE claim operation: 仅 `pending`或已到期的 `retry_wait/reconcile_needed`可转为 `running`, 同时写唯一 `lease_token`, worker name, `started_at`和 `lease_until`. Operation lease 默认是 `2 * operation job timeout`, 即 240 秒. 更新行数不是 1 时立即退出, 因而重复 enqueue 不能并发调用 Mem0.

Worker 在调用 Mem0 前检查 expected record version. Version mismatch 时原子标记 `obsolete`并停止重试. 随后按 `operation_key`查询已有 Mem0 projection; 已存在时直接核对并回填, 不重复 add. 外部调用完成后的 SQLite 更新必须匹配当前 `lease_token`, `running`状态和 operation version, 旧 worker 不能回写新 claim.

Reconciliation 只在 lease 过期且确认对应 RQ execution 已结束后接管, 再把 operation 转为可 claim 状态. 240 秒 lease 晚于 120 秒 RQ timeout, 避免仍在执行的旧 worker 与 recovery worker 重叠. 旧重试不能覆盖更新的撤销或 supersede. 不能要求 SQLite 和 Mem0 同时提交.

`supersede`是应用业务状态, 不是对 Mem0 原子能力的假设. Adapter 根据目标状态将它映射为受控的 update 或 delete, 并把实际调用和结果记录在 operation 中.

### 8.17 Reconciliation

Reconciliation job 定期比较 SQLite 的 `desired_status`, 最近 operation 和 Mem0 metadata:

- SQLite 有 active record 但 Mem0 缺失时, 重新排队 `add`或`update`.
- SQLite 已 revoke 或 delete 但 Mem0 仍可检索时, 重新排队对应操作.
- Mem0 存在无法映射到 SQLite `memory_record_id`和 operation key 的记录时, 隔离并告警, 不自动注入生成.
- 已应用 operation 的 payload hash 不一致时, 标记 `reconcile_needed`并按 SQLite 目标状态修复.

页面 overall learning 状态由 extraction job 和每项 operation 派生. `partial`只是一种展示聚合, 不写回 immutable revision, 也不能代替 item 级状态.

### 8.18 关系完整性

Migration 必须用 foreign key, `CHECK`约束和 transaction assertion 保证:

- Generation, revision, task, class 和 organization 一致.
- Runtime generation 的必需快照完整; legacy generation 只能以 explicit partial 状态存在.
- Runtime generation 创建时的 transcript version, snapshot 和 hash 必须来自同一次 task transaction read.
- Draft 的 task, generation, organization 和 teacher 必须一致. `based_on_revision_id`如存在, 必须属于同一 task, generation 和 teacher. `draft_version >= 1`. Confirmation 对当前 draft 的同步和 version 递增必须与 revision 创建处于同一 transaction.
- Task latest generation 必须属于该 task. Latest/previous revision 必须属于同一 task, 且 previous revision 序号更小.
- Revision 引用同一 task 下已 `succeeded`的 generation.
- `learn_requested=true`的 revision 必须有 canonical learning evidence snapshot, source refs 和匹配 hash; `learn_requested=false`必须保存 canonical empty snapshot. Snapshot 只能包含 generation roster, organization 和 subject 范围内来源.
- Generation 的 skill version 属于 skill registry, content hash 与 version 一致, generation teacher 是 registry owner.
- Skill owner 属于同一 organization, active version 和 base version 属于同一 registry.
- Imported version 可以以 `not_required`初始激活. Candidate 只有在评测完成且老师本次确认后, 才能在同一 transaction 把 review status 改为 `approved`并移动 pointer. `pending`或`rejected`不能成为 active version.
- Candidate build base version 属于同一 registry. Frozen candidate revision 每个 task 最多一条, 必须来自同一 organization, registry 和 owner; candidate evidence 必须关联 frozen revision 且选择时为 active teacher style evidence, 同一 candidate revision 和 memory record 最多一条.
- Candidate version 的 `candidate_build_id`必须指向 succeeded build, source hash 与 build 一致.
- Memory type 与 style scope 或 student scope 的必填和互斥关系正确.
- Memory evidence 的 revision, source teacher 和 source skill 必须与 revision -> generation 证据链一致.
- Student fact 的 organization 必须与 student organization 一致, 且 evidence generation 的 subject 和到课 roster 支持该 scope.
- Extraction job 只能为创建时 effective revision; evidence 的 `extraction_job_id`, revision 和 input hash 必须一致. Obsolete job 不能关联新 evidence.
- Extraction job, candidate build, evidence event, memory record 和 operation 的 organization 链必须一致.
- 所有 status 字段只接受文档定义的 allowlist.
- Task 的 organization 以 class organization 为权威, 不能直接采用前端或跨组织管理员传入值.

## 9. API 设计

### 9.1 生成和重新生成

现有生成接口增加客户端幂等键:

```http
POST /api/class-commentary/tasks/{task_id}/generate
```

请求必须包含 `request_id`. 响应返回 `generation_id`和 generation 状态. 同一 request ID 且显式请求 intent 相同时返回原 generation; 原 generation 仍在执行时返回 202, 已结束时返回 200, 且不再次调用模型或扣费. 显式 skill 或 attendance intent 不同时返回 `409 Conflict`. 幂等查询位于 auth 和 task owner 校验之后, API key, live task 状态, live roster, live skill 和 Mem0 查询之前.

### 9.2 保存草稿

```http
GET /api/class-commentary/tasks/{task_id}/generations/{generation_id}/feedback-draft
PUT /api/class-commentary/tasks/{task_id}/generations/{generation_id}/feedback-draft
```

请求:

```json
{
  "feedback_text": "老师修改中的文本",
  "expected_draft_version": 3,
  "based_on_revision_id": 456
}
```

首次创建使用 `expected_draft_version=0`. 成功响应返回递增后的 `draft_version`. Version mismatch 返回 `409 draft_version_conflict`和当前服务器 draft metadata, 但前端必须保留本地未保存文本. 后端从 URL 和登录态解析 task, generation 和 teacher, 不信任前端 scope.

草稿绑定 generation. 页面加载顺序是: 当前页面未保存内容 -> 该 generation 已保存草稿 -> 该 generation 最近确认终稿 -> generation AI 原稿. 确认 revision 以 CAS 把当前 generation 草稿同步为终稿并返回新 `draft_version`, 但不删除或修改其他 generation 草稿.

### 9.3 确认终稿

```http
POST /api/class-commentary/tasks/{task_id}/feedback-confirmations
```

请求:

```json
{
  "generation_id": 122,
  "feedback_text": "老师最终确认文本",
  "learn": true,
  "expected_draft_version": 3,
  "request_id": "client-generated-id"
}
```

接口不要求先保存当前编辑文本, 但必须以 `expected_draft_version`证明页面没有落后于服务器草稿; 无草稿时传 0. Confirmation transaction 将当前 generation 草稿同步为确认文本并递增 version, 响应返回新 `draft_version`. 该字段进入 confirmation payload hash. 接口必须幂等. 同一 `request_id`不能创建多个 revision 或 memory job. 相同 request ID 但 payload 不同返回 `409 Conflict`.

### 9.4 查看 revision

```http
GET /api/class-commentary/tasks/{task_id}/feedback-revisions
```

### 9.5 查看本次学习结果

```http
GET /api/class-commentary/revisions/{revision_id}/memories
```

### 9.6 重试学习

```http
POST /api/class-commentary/revisions/{revision_id}/memory-retry
```

请求必须包含 `request_id`. Auth 后在一个 `BEGIN IMMEDIATE`内完成幂等查重, effective revision 和 eligible target 重读, retry event 创建及 frozen target reset. `learn_requested=true`且至少存在一个 eligible `failed` extraction job 或 item operation时才允许新 retry. `obsolete`和`integrity_failed` job 永远不 eligible; extraction 已完成但部分 operation 失败时仍可只重试失败 item. Superseded revision 或没有 eligible target 时返回 `409 revision_not_retryable`, 不写 event. 同一 payload 幂等返回, 冲突 payload 返回 `409 Conflict`.

### 9.7 撤销学习证据

```http
POST /api/class-commentary/memory-evidence/{evidence_id}/revoke
```

请求必须包含 `request_id`. API 只允许老师撤销自己提供的 evidence. 它先在 SQLite transaction 内撤销 evidence; 仅当没有其他 active evidence 时才改变 canonical memory 目标状态并创建 outbox operation.

### 9.8 Skill registry 和版本

```http
GET  /api/class-commentary/skills
GET  /api/class-commentary/skills/{skill_id}/versions
POST /api/class-commentary/skills/{skill_id}/candidates
POST /api/class-commentary/skills/{skill_id}/versions/{version_id}/activate
POST /api/class-commentary/skills/{skill_id}/versions/{version_id}/rollback
```

Candidate 请求必须包含 `request_id`和`expected_active_version_id`, 并通过 candidate build unique constraint 幂等. 后端自行选择和冻结 revision/evidence, 不接受客户端 source IDs. 激活和回滚请求必须包含同样两个字段. 所有接口必须复用现有认证, 组织范围和班级访问校验. Skill API 和生成 API 都从 registry 解析 owner, 用户只能使用和修改本人 skill.

## 10. 后台任务

### 10.1 记忆任务

Extraction job 流程:

1. 使用 `revision_id`读取 revision 和其引用的 immutable generation.
2. Claim 前校验 revision 仍是 task latest effective revision; 否则标记 job `obsolete`并退出.
3. 校验组织, skill registry 和 owner 证据链完整.
4. 读取 generation cumulative diff, previous revision incremental diff 和 immutable learning evidence snapshot, 并校验 extraction input hash.
5. 调用结构化提取器分类学习信号. 禁止查询实时错题或掌握度表.
6. 学生映射只能使用 generation 中确认的班级和到课 roster, 不信任 job 参数或前端 student ID.
7. 使用服务端 canonical `subject_key`, 丢弃无证据, 无唯一学生映射或违反隐私规则的项目.
8. 与 SQLite 中当前 memory records 和 evidence 比较.
9. 在一个 `BEGIN IMMEDIATE` transaction 内再次校验 latest revision, job status 和 claim token, 再保存 canonical memory, evidence 和逐项 outbox operation并标记 `extracted`.
10. Transaction commit 后由 dispatcher 投递 pending operation. Revision 保持 immutable, 不写 job 状态.

任务必须以 `revision_id + extraction_input_hash + extractor_version + memory_schema_version`构造 request key.

Operation worker 每次只处理一个 operation, 调用 Mem0 后回写实际状态. 失败只重试该 item. Redis enqueue 或 worker 崩溃时, dispatcher 根据 SQLite pending 状态补投.

### 10.2 Reconciliation 任务

每 10 分钟扫描一次:

- 已到 `next_attempt_at`的 `pending`, `retry_wait`和`reconcile_needed` operation.
- `lease_until`已过期, 对应 RQ execution 已结束但仍为 `running`的 operation.
- 未 enqueue 的 `queued` extraction job 和已到 `next_attempt_at`的 `retry_wait` extraction job; 补投前先查 revision effective, 否则标记 `obsolete`.
- `started_at + extraction_timeout + 60s grace`后仍为 `running`的 extraction job; revision 非 effective 时标记 `obsolete`, 否则 attempt 少于 4 时转回 retry, 达到上限标记 `failed`.
- 未 enqueue 或 retry 到期的 candidate build; worker 只 claim `queued/retry_wait`, stale frozen source set 转 `obsolete`.
- `started_at + candidate_build_timeout + 60s grace`后仍为 `running`的 candidate build; 先校验 frozen source set, stale 时转 `obsolete`, 否则 attempt 少于 3 时清除旧 claim 并转回 `retry_wait`, 达到上限转 `failed`. 下一次 claim 写新 token, 旧 token 不能写回 recovered build.
- SQLite desired state 和 Mem0 metadata 不一致的 record.
- 已提交但未成功 enqueue 的 extraction job 和 operation.

Reconciliation 永不补投 `obsolete`或`integrity_failed` extraction job, 也不补投 `obsolete` candidate build. 它只使用稳定 operation key 幂等补投, 不直接重跑整个 revision. `ensure_reconciliation_scheduled()`按 UTC 10 分钟时间桶生成唯一 RQ job ID, 格式为 `cc-memory-reconcile-YYYYMMDDHHmm`. 同一时间桶已存在视为成功. 每次任务在扫描前安排下一时间桶, 每个 worker 启动时也调用同一函数, 避免多 worker 重复续排或本次异常使周期链中断.

`operation.attempt_count`是单个自动周期内跨 RQ job 的全局计数. 前 3 次失败按 30, 120, 600 秒重试; 第 4 到第 7 次由 reconciliation 按 1, 2, 4, 6 小时补投; 第 8 次失败后进入 `failed`. Revision/evidence 来源 operation 只允许 revision owner 通过 `memory-retry`开启新自动周期; cleanup/reconciliation 来源 operation 只允许内部 maintenance command 以 service identity 重试. Reconciliation 不自动补投 `failed` operation.

### 10.3 Skill 候选任务

Effective revision 的统一定义:

- 对每个未删除 task, 唯一 effective revision 是 `class_commentary_tasks.latest_revision_id`指向的 revision.
- Revision 必须引用 complete runtime generation, 且 generation skill registry 与目标 skill 一致.
- 如果 task latest revision 使用其他 skill, 当前 skill 不得回退使用该 task 的更早 revision.
- `learn_requested=false`和`accepted_without_edit`可以作为 replay evaluation case, 但不能作为风格规则支持证据.
- 风格支持只能来自 effective revision 对应的 active `teacher_style` evidence. Superseded 或 revoked evidence 完全不计数.
- 同一 task 对同一风格规则最多贡献一次支持.

默认满足以下条件后, 页面显示`可生成新版 skill`:

- 至少 5 个不同 task 的 effective revision 可用于 replay evaluation.
- 至少一条风格规律由 3 个不同 task 的 effective revision 和 active style evidence 支持.

所有计数使用 `COUNT(DISTINCT task_id)`. 阈值是运行配置, 不是数据库常量.

老师手动触发后, 后端按 8.7 到 8.9 的规则冻结 candidate build. 候选生成器只能读取 frozen base version, candidate revisions, active style evidence snapshot 和评测规则. 不得重新查询 live revision list, 不得读取学生记忆或把学生事实写入 skill.

版本详情返回 `effective_task_count`, `supporting_task_count`, frozen revision/evidence IDs, `source_cutoff_at`, `selection_policy_version`, `is_stale`和`stale_reason`. UI 使用`支持任务数`, 不显示会重复计权的`支持 revision 数`.

## 11. Skill 评测和激活

### 11.1 评测集

评测集只来自 candidate build 冻结的 effective revisions, 每个 task 最多一个样本. 每个样本包含转写安全摘要, roster, AI 原稿, 老师终稿和差异标签. 指标分母使用 frozen distinct task 数, 不使用历史 revision 总数.

Candidate 创建后的新 task/revision 不改写 evaluation snapshot. Frozen task 产生新 revision, base active version 改变, 或 frozen supporting evidence 变为 superseded/revoked 时, candidate 派生状态变为 stale. Candidate content 和 evaluation snapshot 保持 immutable.

### 11.2 指标

- 老师终稿的 normalized edit distance.
- 无修改接受率.
- 已确认风格规则覆盖率.
- 学生姓名和 roster 一致性.
- 无证据事实数量.
- 学生事实进入 skill 的污染数量, 必须为 0.
- 输出结构和纯文本约束通过率.

### 11.3 激活

页面展示:

- 当前版本和候选版本 diff.
- 支持候选修改的 revision 证据.
- 当前版本和候选版本评测对比.
- 已知风险和失败样本.

老师点击确认后, 后端先完成登录, organization 和 registry owner 授权, 再查 activation event 完成幂等返回或 payload 冲突判断. 对没有 event 的新请求, 校验候选评测已经完成, 每条 frozen revision 仍是对应 task 的 latest effective revision, 每条 frozen supporting evidence 仍 active, version 仍为 `pending`, 且当前 pointer 等于`expected_active_version_id`. 任一来源失效时返回 `409 candidate_stale`, 禁止临时用剩余 live evidence 重算旧候选. 来源仍有效时, 同一个 SQLite transaction 将 review status 改为 `approved`, 使用 CAS 移动 `class_commentary_skills.active_version_id`并创建 activation event. 激活操作不覆盖旧版本.

Active version 的 supporting evidence 后续被 supersede 时不自动移动 pointer. 页面把当前评测标记为 stale, 提示老师`基于最新证据重新生成`或回滚; 任何自动回滚都违反本人显式确认原则.

### 11.4 回滚

老师可以选择任意历史 active version 回滚. 回滚执行同样的 owner 校验, 幂等和 CAS, 创建新的 activation event, 不删除中间版本和评测记录.

## 12. Prompt 组装

生成 prompt 分为明确分区:

```text
[CURRENT_TASK_FACTS]
本次班级, 到课名单和确认转写

[ACTIVE_SKILL]
当前激活 skill 内容

[TEACHER_STYLE_MEMORIES]
当前 skill 的相关风格记忆

[STUDENT_HISTORY_MEMORIES]
本次明确提到学生的历史参考

[OUTPUT_RULES]
事实边界, 纯文本和学生分节规则
```

Prompt 必须声明:

- `CURRENT_TASK_FACTS`是本次事实来源.
- `STUDENT_HISTORY_MEMORIES`只是历史参考, 不能伪装成本次发生的事实.
- `TEACHER_STYLE_MEMORIES`只能影响表达和关注方式.
- 不得输出没有学生 ID 映射的历史信息.

Revision `learning_evidence_snapshot_json`只用于后台学习提取, 不直接追加到后续 generation prompt. 只有经过提取, 审计和 active scope 校验的 memory 才能通过 RAG 进入生成.

应用数据库中的 generation 保存受权限保护的完整 prompt payload 快照, 用于永久还原. 外部生成 trace 只记录 memory ID, 数量, hash 和字符数, 默认不把完整学生记忆或完整转写发送到 Langfuse.

## 13. 权限和隐私

- 所有 draft, generation, revision, registry, version, candidate build, candidate relation, activation event, memory record, evidence, job 和 operation 必须包含 `organization_id`.
- 所有受保护 API 统一按以下顺序执行: 登录认证 -> organization/resource 授权 -> request ID 幂等查询 -> 业务状态和 CAS 校验 -> mutation. 幂等命中不能绕过认证和资源授权.

| 操作 | 必须满足的资源授权 |
| --- | --- |
| 查看 task summary 和最新公开终稿 | 当前班级访问权 |
| 查看完整 generation prompt, skill snapshot, revision diff, evidence 和学习状态 | `current_user.id == task.teacher_user_id` |
| 更新或重试转写 | `current_user.id == task.teacher_user_id`, 且当前仍有班级访问权 |
| 生成或重新生成 | `current_user.id == task.teacher_user_id == skill.owner_teacher_user_id` |
| 保存草稿或确认 | 当前用户是 task teacher, generation 属于该 task, generation skill owner 也是当前用户 |
| 撤销 evidence | 当前用户是 evidence source revision teacher, 且仍有 source task/class 访问权 |
| 重试学习 | 当前用户是 revision teacher, 且仍有 task/class 访问权 |
| 创建候选, 激活或回滚 | `current_user.id == skill.owner_teacher_user_id` |

以上每项还必须满足 resource organization 与当前明确 organization 上下文一致. 本阶段不提供管理员代老师修改, retry 或查看完整证据的例外 API.
- 非 task owner 的 task summary 使用 public allowlist, 只返回 task, organization, class, teacher, workflow status, `final_feedback_text`, confirmation time 和基础时间戳. 不返回 transcript, 未确认 AI 原稿兼容缓存, audio, skill, generation/revision pointer 或错误详情. Generation 和 revision 列表也只允许 task owner 查看.
- Skill 列表只返回当前用户在 registry 中拥有的 skill. 未登记 skill 和其他老师的 skill 均不可选择.
- Mem0 查询必须强制添加组织 metadata filter.
- 学生 memory 查询必须同时限制 `organization_id`, `student_id`和 `subject_key`.
- 学生 memory 检索前按角色实时校验: `member`必须通过当前 `user_classes -> class_students`关系; organization `owner/admin`使用同组织现行班级和学生访问规则; `super_owner`没有默认 memory 权限. 检索还必须确认学生属于本次 generation 的班级和到课 roster. 老师失去访问权后立即停止检索, 不删除其他有权老师仍需使用的共享事实.
- 风格 memory 查询必须同时限制 `organization_id`和当前 registry skill scope.
- `super_owner`必须进入明确的单一 organization 上下文并通过该 organization 的学生访问校验, 否则禁止检索.
- Class organization 是 task organization 的权威来源. 后端拒绝 user, task, class 或 student organization 不一致的请求.
- 前端传入的 scope 字段不可信, 后端从任务和登录用户重新解析.
- 不把家长联系方式, 地址, 账户信息或原始完整录音写入 Mem0.
- Learning evidence snapshot 只保存提取所需的安全摘要和 source refs, 不保存错题原始图片, 联系方式或无关原题内容.
- 老师只能撤销自己提供的 evidence. Canonical 学生事实是否撤销取决于是否仍有其他 active evidence.
- 组织, 学生, 任务或 revision 删除时, 必须在 SQLite 先记录目标状态和清理 operation.
- 每次 memory add, update, revoke 和 delete 都写审计记录.

### 13.1 数据生命周期

本文的`永久保留`指正常产品生命周期内不被重新生成, 编辑或普通删除覆盖. 普通删除使用 soft delete: 隐藏 task, generation 和 revision, 撤销相关 evidence, 将 Mem0 desired state 转为 delete, 但保留受限审计记录.

依法或由明确授权触发的隐私擦除是唯一例外. Erasure flow 物理删除或不可逆脱敏必须擦除的 transcript, roster, prompt, output, learning evidence snapshot 和 memory content, 同时保留不含个人内容的 erasure event, object ID, 时间和操作结果. 不能为了满足审计而继续保存被要求擦除的个人文本.

删除一条来源 evidence 不影响仍由其他 active evidence 支持的共享学生事实. 删除整个 organization 时清理该 organization 的所有 Mem0 records 和 Qdrant vectors.

## 14. 失败处理

### 14.1 Mem0 不可用

- 保存老师终稿和 revision.
- Extraction job 或单项 operation 标记可重试, 状态只写在 job 和 operation 表.
- 后续生成可以降级为无 memory 生成.
- 页面明确显示`记忆暂不可用`, 不能假装已经学习.

### 14.2 部分写入

如果老师风格记忆成功而部分学生记忆失败, 页面可以聚合显示 `partial`, 但每项 operation 保留独立状态. 重试只处理未完成或失败 item, 不能重复添加成功记忆.

SQLite 已提交但 Mem0 调用失败时, operation 保持 pending 或 retry 状态. Mem0 已成功但 SQLite 回写失败时, operation 标记或被扫描为 `reconcile_needed`, 通过 stable operation key 查询并回填, 不重复创建 memory.

### 14.3 重复请求

相同确认 `request_id`且 payload 相同时返回原 revision. Request ID 相同但 payload 不同返回 `409 Conflict`. 相同 memory request key 返回原 job. RQ 重试使用 operation key 和 version guard, 不得产生重复 Mem0 记录或让旧操作覆盖新状态.

### 14.4 队列投递失败

SQLite transaction 成功但 Redis enqueue 失败时, API 仍返回已保存的 revision 和`排队恢复中`状态. Dispatcher 和 reconciliation 扫描 committed job 或 operation 并补投.

### 14.5 生成失败

Mem0 检索失败时记录告警并使用 active skill 继续生成. AI 生成失败时将对应 generation 记录为终态 `failed`; 重试创建新 generation, 不覆盖失败证据.

### 14.6 草稿版本冲突

Draft CAS 失败返回 `409 draft_version_conflict`. 服务端不覆盖任何文本; 前端保留本地内容并提供加载服务器版本或复制本地内容, 不自动 last-write-wins.

### 14.7 Revision 已被取代或 snapshot 损坏

Superseded revision 的 extraction/retry 请求进入或保持 `obsolete`, 不作为普通失败重试. Learning evidence 或 extraction input hash 不匹配时 job 进入 terminal `integrity_failed`, 不允许查询实时错题数据作为 fallback, 也不允许通过普通 retry API 恢复. 修复数据后只能由受信 maintenance command 创建带新审计记录的重建 job.

### 14.8 Candidate source stale

Candidate build 执行前来源失效时标记 `obsolete`. Candidate version 创建后来源失效时派生 `is_stale=true`; 激活返回 `409 candidate_stale`, 要求基于最新 effective tasks 生成新 build.

## 15. 配置和部署

新增运行配置:

- `XR_CLASS_COMMENTARY_MEMORY_ENABLED`.
- `XR_REDIS_URL`.
- `XR_CLASS_COMMENTARY_MEMORY_QUEUE`, 默认 `class_commentary_memory`.
- `XR_CLASS_COMMENTARY_MEMORY_EXTRACTION_TIMEOUT`, 默认 300 秒.
- `XR_CLASS_COMMENTARY_MEMORY_OPERATION_TIMEOUT`, 默认 120 秒.
- `XR_CLASS_COMMENTARY_MEMORY_RECONCILE_INTERVAL`, 默认 600 秒.
- `XR_MEM0_VECTOR_PROVIDER`.
- `XR_MEM0_QDRANT_URL`.
- `XR_MEM0_QDRANT_API_KEY`.
- `XR_MEM0_COLLECTION_NAME`.
- `XR_MEM0_EMBEDDER_PROVIDER`.
- `XR_MEM0_EMBEDDER_MODEL`.
- `XR_MEM0_EMBEDDING_DIMS`.
- `XR_MEM0_STYLE_LIMIT`.
- `XR_MEM0_STUDENT_LIMIT`.
- `XR_MEM0_CONTEXT_CHAR_LIMIT`.
- `XR_SKILL_EVOLUTION_MIN_EFFECTIVE_TASKS`, 默认 5.
- `XR_SKILL_EVOLUTION_MIN_SUPPORT_TASKS`, 默认 3.
- `XR_SKILL_EVOLUTION_BUILD_TIMEOUT`, 默认 300 秒.

默认关闭 feature flag. 数据库 migration 可以提前上线, 但没有 Mem0 和 Qdrant 健康检查时不能向用户显示`确认并学习`.

### 15.1 专用 worker

课堂点评记忆不复用 `wrong_question_uploads`队列. 实现新增:

- Queue module: `class_commentary_memory_queue.py`.
- Worker entrypoint: `class_commentary_memory_worker.py`.
- Launch script: `scripts/run_class_commentary_memory_worker.sh`.
- PM2 process: `xingrun-class-commentary-memory-worker`.

Launch script 先加载 `.env.runtime`, 再执行 `exec .venv/bin/python class_commentary_memory_worker.py`. Entrypoint 使用 `if __name__ == "__main__"`保护启动逻辑, 从 `XR_CLASS_COMMENTARY_MEMORY_QUEUE`读取 queue name, 未设置时默认 `class_commentary_memory`, 并调用 `worker.work(with_scheduler=True)`. API enqueue, worker 和 healthcheck 必须调用同一个配置 loader.

Extraction job 使用 `job_timeout=300`和`Retry(max=3, interval=[30, 120, 600])`; 单项 Mem0 operation 使用 `job_timeout=120`和相同 Retry; candidate build 使用 `job_timeout=300`和`Retry(max=2, interval=[60, 300])`. 三类 job 使用 `result_ttl=86400`, `failure_ttl=604800`. RQ 重试只负责执行调度, SQLite job, build 和 operation 表仍是状态事实来源.

Reconciliation 每 10 分钟通过 `enqueue_in`自排下一次任务. Worker 启动时按时间桶 job ID 幂等补齐未来任务, 避免重启后周期链丢失. Dispatcher 只是 API commit 后和 reconciliation 共用的投递函数, 不新增第三个常驻进程.

### 15.2 发布和健康检查

生产部署以 PM2 为唯一事实来源. 首次发布保留现有 `xingrun` Web 进程, 只新增 `xingrun-class-commentary-memory-worker`, 设置 `kill_timeout >= 330000ms`, 然后执行 `pm2 save`. 后续发布必须同时重启 `xingrun`和`xingrun-class-commentary-memory-worker --update-env`.

实现阶段将 `scripts/deploy_backend.sh`从 nohup 路径改为 PM2 发布入口, 并同步更新 `server deploy.md`和`docs/deploy-release.md`. 不再保留含糊的第二套生产启动方式.

部署检查必须验证:

- Redis ping 成功.
- Qdrant 可读写.
- Embedding 维度和 collection 配置一致.
- 中文检索 smoke test 通过.
- 两个 PM2 process 均为 online.
- `pm2 status xingrun`为 online, 且 `curl -I http://127.0.0.1:5001/`返回 `HTTP/1.1 302 FOUND`.
- 加载 `.env.runtime`和默认值后, `.venv/bin/rq info --url "$XR_REDIS_URL" "$XR_CLASS_COMMENTARY_MEMORY_QUEUE"`显示 worker count >= 1.
- RQ worker 能访问同一 Mem0 配置, 并存在下一次 reconciliation 排期.
- ScheduledJobRegistry 中恰有一个下一时间桶的 `cc-memory-reconcile-*` job.
- SQLite revision 和 Mem0 memory 可以双向定位.

## 16. 可观测性

记录以下指标:

- 确认 revision 数量.
- `确认并学习`和`确认但不学习`比例.
- Draft CAS 冲突数量, generation 切换恢复次数和 confirmation draft sync 失败数.
- 无修改接受率.
- 平均和中位 normalized edit distance.
- Learning evidence snapshot 的 complete/partial/empty 数量, snapshot hash `integrity_failed`数量和 selector version 分布.
- Extraction job 的 extracted/failed/integrity_failed/obsolete 比例, obsolete reason, commit-time latest revision guard 拒绝数, overall learning partial 比例, 重试次数和延迟.
- operation 各状态数量, item 级失败率, enqueue 恢复次数和 reconciliation 修复次数.
- SQLite desired state 与 Mem0 actual state 的漂移数量和最长漂移时间.
- 每次生成检索的 style 和 student memory 数量.
- Mem0 检索延迟和降级次数.
- skill 候选生成, 激活和回滚次数.
- Candidate effective/supporting task 数量, queued/running/retry_wait/failed/obsolete build 数量, build latency 和 stale reason.
- 激活前后编辑距离变化.

日志不得包含完整学生记忆, 完整转写或完整终稿. 使用 ID, hash, 字符数和状态摘要.

## 17. 测试要求

### 17.1 数据层

- Migration 可以从当前数据库重复执行.
- Legacy task 只迁移真实存在的数据并标记 partial, 不伪造 attendance, prompt 或 memory context.
- Partial legacy generation 不能确认并学习, complete runtime generation 可以.
- 每次生成和重新生成创建独立 generation, 旧原稿和输入快照不能被覆盖.
- Generation reservation 后只从冻结 transcript, roster 和 skill snapshot 组装 prompt; 模型只消费已持久化的 ready prompt snapshot. Prompt 或 Mem0 结果变化不能改变同 request ID 的幂等结果.
- Transcript confirmation 原子递增 version, generation request hash 使用同 transaction 的 version 和 text hash.
- 并发生成晚完成或生成期间转写被修改时不能覆盖较新的 task pointer 或新转写状态.
- Generation A 和 B 的 draft 行独立, 保存任一行不能改变另一行.
- 同一 generation 两个写入者从 version N 开始时只有一个 CAS 成功, 另一个返回冲突且服务器文本不被覆盖.
- Revision immutable, `generation_id`必填, revision 序号和 confirmation request ID 唯一.
- Confirmation 幂等重放返回首次 transaction 保存的 revision 和 confirmed draft snapshot, 不返回后来修改的 live draft.
- Confirmation transaction 对 revision, 当前 generation draft sync, task cache, learning evidence snapshot, 旧 job obsolete, 旧 evidence supersede 和新 extraction job 保持原子性.
- 同一 confirmation request 在来源记录变化后仍返回原 revision 和原 learning evidence hash, 不重新捕获 snapshot.
- 空 learning evidence 也保存 canonical empty snapshot 和稳定 hash; partial snapshot 明确记录缺失来源, 不用 NULL 冒充 complete. Hash 覆盖 schema/selector version, captured at, snapshot, source refs, completeness 和 missing sources 完整 envelope.
- Memory job, operation key 和 extractor/schema version 组合幂等.
- Stale operation 在 version mismatch 时进入 terminal `obsolete`, 不重复重试.
- Candidate build 每个 task 只能冻结一个 revision, candidate version 只能关联一个 build, frozen revision/evidence 关系约束正确.
- Registry owner, version 归属, active pointer, activation event 和关系约束正确.
- 并发激活 CAS 只有一个请求成功.

### 17.2 API

- Generation scoped 草稿读取和保存, 确认不学习和确认学习.
- Draft organization, task, generation 和 teacher 越权被拒绝.
- 同一 generation stale draft save 返回 `409 draft_version_conflict`; confirmation 同步当前 draft 并递增 version, 不改变其他 generation 草稿.
- 生成和确认的重复请求不重复创建记录; request ID 相同但 payload 不同返回冲突.
- In-flight generation 的同 request ID 重试返回原 generation 和 202, 不要求 live skill 仍 active 或原 roster 学生仍在班级, 不调用模型.
- 不能确认失败 generation, 其他 task 的 generation 或已切换后未明确选择的 generation.
- 不同组织, 班级和老师的越权请求被拒绝, 只读班级权限不能执行 owner 写操作, 查看 task 时也不能看到 transcript, 未确认 AI 原稿或 generation/revision 列表.
- 未登记 skill, 非 owner skill 和 organization 不一致的 skill 不能生成或进化.
- 撤销 memory 和重试 job.
- Superseded revision, `obsolete` job 和 `integrity_failed` job 的 memory retry 均被拒绝, 不创建 retry event; extraction 已完成但部分 operation 失败时只重试失败 item.
- Evidence revoke event, Skill 候选, 激活和回滚请求均幂等, payload 冲突返回 409.
- Candidate API 拒绝客户端提供 revision/evidence IDs, 并在 source set stale 时返回明确冲突.
- Activation 首次成功后重试同一 request ID 返回原 event, 不因 pointer 已移动而冲突.

### 17.3 Mem0 adapter

- 精确 metadata scope.
- Mem0 候选必须通过 SQLite desired state, record version, active evidence 和当前权限回查.
- 中文语义检索.
- add, update, supersede, revoke 和 rebuild.
- Mem0 不可用时的降级.
- 重试不产生重复 memory.
- Mem0 成功但 SQLite 回写失败, 以及 SQLite 成功但 Mem0 失败时均可 reconciliation.
- 旧 operation 重试不能覆盖较新 record version.

### 17.4 学习提取

- 风格修改不会带入学生姓名.
- 学生事实只能映射到唯一 roster student ID.
- 一次性事实进入 `evaluation_only`.
- 无修改确认不创建风格 memory.
- 新 revision 可以 supersede 旧 memory.
- 新 revision 选择不学习时 supersede 所有 earlier revision 的 active evidence, 但不创建新版 evidence.
- 确认后修改或删除错题和掌握度源记录, 延迟 extraction, retry 和 extractor 升级仍使用相同 frozen snapshot 和 input hash.
- 其他 organization, 其他 subject 和 roster 外学生的来源不能进入 learning evidence snapshot.
- Snapshot 或 extraction input hash 被篡改时 job 进入 `integrity_failed`, 不写 evidence, 不查询实时来源 fallback.
- 每条 evidence 可以反查 revision, extraction job, extractor/schema version 和 learning evidence hash.
- 多位老师可以为同一学生事实提供独立 evidence.
- 撤销一个来源不会删除仍有其他 active evidence 支持的事实.
- 并发提取同一 canonical fact 只创建一个 active memory record.

### 17.5 生成

- 只检索当前组织和当前 registry skill 的风格记忆.
- 学生事实可以在同机构内跨老师和跨 skill 共享, 但只检索本次明确提到且在到课 roster 中的学生.
- 老师当前有学生访问权时可检索共享事实, 访问权撤销后立即拒绝.
- `subject_key`只能来自服务端 canonical 字段, 不同学科不能串用.
- 历史信息被标记为参考, 不伪造为本次事实.
- Mem0 故障时仍可使用 active skill 生成.

### 17.6 前端

- 编辑, 草稿保存, 确认和复制状态正确.
- Generation A 和 B 分别恢复自己的草稿, 切换时不静默套用其他 generation 的草稿或终稿.
- 两个标签页同时编辑同一 generation 时, stale 页面收到 409 后保留本地未保存文本并可加载服务器版本.
- Confirmation 成功后采用响应中的新 draft version, 旧标签页后续保存不能覆盖终稿, 其他 generation 草稿仍存在.
- 离开页面前提示未保存修改.
- 学习状态轮询和失败重试.
- 学习结果可查看和撤销.
- 历史任务优先显示最新终稿.
- Skill 候选 diff, 评测, 激活和回滚流程.

### 17.7 Worker 和恢复

- SQLite commit 成功但 enqueue 失败后, dispatcher 可以补投.
- Stale running extraction job 在 timeout 后恢复或进入 failed, 不会永久卡住.
- Rev1 job 仍 queued 时先确认 rev2, rev1 进入 obsolete; 即使旧 RQ execution 随后启动也不能创建 evidence.
- Rev1 worker 已完成模型调用但未提交时先确认 rev2, commit-time latest revision 和 claim token guard 拒绝 rev1 结果.
- Rev1 先提交 evidence 后再确认 rev2, 旧 evidence 被 supersede, stale add operation 不能恢复 active.
- Rev1 failed 后确认 rev2, rev1 retry 返回 409; reconciliation 永不补投 obsolete job.
- Rev1 retry 和 rev2 confirmation 并发时由 `BEGIN IMMEDIATE`串行化: retry 先提交则 rev2 随后 obsolete 它, rev2 先提交则 retry 返回 409 且不创建 event.
- 同 task 存在多个旧 revision 时, 任一旧 job 都不能重新产生 active evidence.
- Extraction 或 candidate build 处于未到期 `retry_wait`时, 重复 enqueue 不能 claim, 不能提前递增 attempt 或绕过 backoff.
- Extraction 和 operation timeout, retry interval 和 TTL 生效.
- Reconciliation 每 10 分钟续排并修复单边成功.
- 多个 worker bootstrap 只创建一个下一时间桶 reconciliation job.
- Operation 达到全局 8 次失败后不再自动补投, 显式 retry 才能恢复.
- Worker 重启后不会丢 committed job, 不会创建重复 operation.
- 同一 operation 被重复 enqueue 时只有一个 worker claim 并调用 Mem0; lease 未过期不能被接管.
- Lease 过期且旧 RQ execution 已结束后可以恢复, 旧 lease token 不能回写.
- Stale running candidate build 在 timeout 后按 frozen source set 和 attempt 上限恢复, 旧 claim token 不能创建 version 或覆盖终态.
- PM2 在 busy job 期间按 kill timeout 退出或恢复, 不会重复 Mem0 operation.
- Web 302, memory worker, Redis queue 和 scheduled reconciliation 的 PM2 healthcheck 均通过.
- API, worker 和 healthcheck 对自定义 `XR_CLASS_COMMENTARY_MEMORY_QUEUE`读取一致.

### 17.8 Skill 候选和评测

- 同一 task 的 rev1 和 rev2 只选择 latest effective rev2.
- Rev1 有 active style evidence, 但 latest rev2 选择不学习时, 当前 skill 不能回退使用 rev1 作为支持.
- 同一 task 的 3 个 revision 或多条 evidence 不能满足 3 个不同 task 的支持阈值.
- 3 个不同 task 的 effective revisions 和 active style evidence 可以满足支持阈值.
- Superseded 或 revoked evidence 不计支持次数; `accepted_without_edit`每 task 只进入一次 evaluation, 不计 style support.
- 不同 organization, owner 或 skill 的 revision/evidence 不能进入 frozen source set.
- Candidate build 创建时永久冻结实际 revision/evidence IDs 和 hashes; 后续新 revision 不改写 snapshot.
- Frozen task 产生新 revision, supporting evidence 失效或 base pointer 改变后 candidate 为 stale, 激活返回 `409 candidate_stale`.
- Candidate stale 时不能用剩余 live evidence 临时重算并激活, 必须创建新 build.

## 18. 验收标准

功能完成必须同时满足:

1. 老师可以修改生成文本, 按 generation 独立保存草稿并显式确认; stale 标签页保存返回 409, 不静默覆盖服务器草稿或已确认终稿.
2. 每个新 runtime generation 的 AI 原稿, 转写, roster, skill, 模型, prompt 和 memory context 均可永久还原; legacy generation 对缺失字段明确标记 partial, 不伪造历史.
3. `确认并学习`在同一 SQLite transaction 创建 revision, 同步当前 draft version, 冻结 learning evidence, 更新 task cache, obsolete 所有 earlier revision 的未完成 job, supersede 所有 earlier revision 的 active evidence 并创建幂等 extraction job; `确认但不学习`不创建新 evidence, 但仍撤销所有 earlier evidence 并异步清理对应 Mem0 projection.
4. 老师能看到系统从本次修改中学到了什么, 并可以撤销自己的 evidence; 共享事实是否继续有效必须如实显示.
5. 下一次使用同一 skill 生成时可以检索相关风格记忆.
6. 同机构内有当前学生访问权的老师可以跨 skill 检索该学生同学科历史, 且不会串到其他学生, 学科或无权老师.
7. Mem0, Qdrant, Redis 或 worker 故障不丢终稿和目标状态, 可以按 item 重试, reconciliation 并支持无记忆降级.
8. 多次确认规律可以形成 skill 候选, 但不能自动激活.
9. 老师可以查看候选差异和评测, 激活后可以回滚.
10. 风格记忆不跨 skill; 学生事实按机构, 学生和学科共享, 不跨组织, 学生, 学科或当前访问权限泄漏.
11. 不建设知识图谱, 不增加第二套独立 RAG.
12. 每个 skill 有可信 registry owner, active pointer 是唯一事实来源, 未登记或非 owner skill 不能进入生成和进化链路.
13. 数据层, API, worker, adapter, 生成和前端测试全部通过.
14. 任何 superseded revision 的延迟 execution, retry 或 reconciliation 都不能创建或重新激活 active evidence.
15. 每条学习 evidence 都能还原到 confirmation 时冻结的错题和掌握度安全摘要; 后续源数据变化不改变 extraction, retry 或 rebuild 输入.
16. Skill candidate 和 evaluation 对每个 task 最多使用一条 latest effective revision, 风格支持阈值来自至少 3 个不同 task, 不按历史 revision 或 evidence 行重复计权.
17. Candidate 永久冻结实际 revision/evidence source set; 任一 frozen effective revision, supporting evidence 或 base version 失效后, 旧 candidate 不可激活.

## 19. 实施顺序

### 阶段 1: 可审计编辑闭环

- `classes.subject_key`, skill registry, initial version 和 activation event migration.
- Generation, per-generation draft, revision 和 task cache migration, 包括把旧 `feedback_text`按真实可用字段回填为 partial legacy generation.
- 现有 skill 的显式 organization 和 owner 绑定流程.
- 生成幂等, immutable snapshot 和重新生成链路.
- Generation scoped draft CAS API, confirmation draft sync 和 409 conflict contract.
- 可编辑结果区, generation 切换恢复, 冲突保留本地文本和确认动作.
- Revision 历史和 diff.

### 阶段 2: Mem0 写入和检索

- Mem0 adapter 和配置.
- 专用 RQ queue, extraction job, item outbox operation 和 dispatcher.
- Confirmation-time learning evidence snapshot selector, source refs, hash 和 immutable input validation.
- 新 revision 对旧 extraction job 的 obsolete transition, worker claim/commit 双门禁和禁止旧 revision retry.
- 风格和学生信号提取.
- Canonical memory, 多来源 evidence, 查看, 撤销和重试.
- Reconciliation 和队列恢复.
- 生成前检索和 prompt 注入.

### 阶段 3: Skill 进化

- Candidate build, latest effective revision selection, immutable revision/evidence source set 和 distinct task threshold.
- 候选生成, replay 评测, stale detection 和重新生成流程.
- Version, activation event, CAS, diff, 激活和回滚 UI.
- 激活前后指标对比.

### 阶段 4: 上线验证

- Feature flag 灰度.
- 真实确认样本回放.
- 中文检索, 风格隔离和学生共享权限验证.
- 故障降级演练.
- Web 和专用 memory worker 发布与健康检查.
- 生产指标观察.

每个阶段独立验证和提交. 阶段 2 不得绕过阶段 1 的事实记录, 阶段 3 不得绕过阶段 2 的确认证据.

## 20. 开发 Goal

在不覆盖任何历史生成和老师确认记录的前提下, 完成课堂点评的可编辑确认闭环, 通过 Mem0 提供可撤销, 可恢复, 有权限边界的风格和学生记忆, 并让每位老师自己的 skill 只能经过多样本证据, 评测和本人显式激活后进化.

Codex loop 必须按阶段 1 到阶段 4 顺序执行. 每一阶段完成 schema/API/worker/UI 中该阶段的完整垂直链路和对应测试后再进入下一阶段. 未经用户明确 `go`不得开始实现, 不自动部署, 不操作 `master`.

## 21. 设计依据

- Mem0 update: <https://docs.mem0.ai/core-concepts/memory-operations/update>
- Mem0 delete: <https://docs.mem0.ai/core-concepts/memory-operations/delete>
- RQ workers: <https://python-rq.org/docs/workers/>
- RQ scheduling: <https://python-rq.org/docs/scheduling/>
- RQ retry: <https://python-rq.org/docs/exceptions/>
