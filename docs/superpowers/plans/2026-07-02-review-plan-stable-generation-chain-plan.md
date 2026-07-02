# 复习计划稳定生成链路开发计划

日期：2026-07-02
分支：`codex/review-plan-chain-audit`
目标：让复习计划生成在新建、重新生成、预览、PDF 和后续 DOCX 导出中都稳定、快速、可对比。

## 架构

目标链路：

```text
文本 / PDF / PPT / DOCX / 录音
-> LessonSourcePack
-> lesson_review_plan_v1
-> validator
-> 必要时 evaluator
-> 必要时 targeted repair
-> renderer
```

不做：

- 不构建多智能体循环。
- 不让 LLM 生成最终 HTML/CSS/DOCX layout。
- 在合同稳定前，不做大框架迁移。

## Phase 0：基于 Lesson 100 的热修

### Task 0.1：读取最新已完成质量 run

文件：

- `lesson_manager.py`
- `app.py`
- `tests/test_review_plan_async_api.py`

改动：

- 新增 `get_latest_completed_review_plan_quality_run_for_version(version_id)`。
- 只读取 completed/succeeded 且 quality review 非空的 run。
- `_review_plan_quality_failure_message()` 改用这个 helper。
- 后续空的 `running/interrupted` telemetry run 不能隐藏已经失败的质量结果。

测试：

- 某 version 有旧的失败质量 run，后面有新的空 interrupted run：仍返回失败质量原因。
- 某 version 有更新的通过质量 run：不返回失败原因。

验收：

- 最新已完成质量结果失败时，version 不能被标记为 ready。

### Task 0.2：停止 PDF 选择题截断

文件：

- `review_plan_templates/single_lesson_pdf.py`
- `tests/test_single_lesson_pdf_unification.py`

改动：

- 把 `explicit_choices[:2]` 改成渲染所有通过规则的 explicit choices。
- 如果视觉密度需要上限，把上限暴露成 validator 规则，不能在 renderer 里静默截断。

测试：

- day 有 5 道填空和 3 道选择时，PDF 渲染 8 道题，答案区有 8 条。
- Lesson 100 fixture 在 plan 有 10 道可打印题时，PDF 正好渲染 10 道。

验收：

- PDF 可见题量等于 canonical printable question count。

### Task 0.3：解析老师题量约束

文件：

- `review_plan_workflow/generation_options.py`
- `review_plan_workflow/schemas.py`
- `review_plan_workflow/quality_gate.py`
- `review_plan_workflow/nodes/parent_planner.py`
- `review_plan_workflow/nodes/plan_generator.py`
- `tests/test_review_plan_workflow.py`

改动：

- 新增 `GenerationConstraint`。
- 解析 `题目控制在10道题`、`10题`、`选择题多一点`、`不要全是选择题`、`只要当天` 等表达。
- parsed count 作为 validator 硬输入。
- 原始老师 prompt 仍保留给 LLM。

测试：

- `题目控制在10道题` 要求正好 10 道可见可打印题。
- 没有解析出题量时，回退到当前最低密度规则。
- 用户题量不能覆盖 schema、安全和答案正确性。

验收：

- 老师 prompt 里的可解析约束被确定性校验。

### Task 0.4：增强 source brief 标题和章节抽取

文件：

- `review_plan_workflow/source_brief.py`
- `tests/test_review_plan_source_brief.py`

改动：

- 首个非空行如果像课堂标题，就作为 title candidate。
- 抽取 `第一部分：`、`一、`、`二、`、`课堂收尾` 这类标题。
- 从章节标题中抽取 topic-like noun phrases。
- 抽取老师动作提示，例如 `必须背熟`、`课后作业`、`明天抽查`。

测试：

- 用户提供的逐字稿抽到包含 `勾股数` 的标题候选。
- 用户提供的逐字稿至少抽到 5 个 knowledge points / method chains。
- 原有 marker-based extraction 仍正常。

验收：

- 信息丰富的逐字稿不再落入 `topic=null`、`knowledge_points=[]`、`lesson_title_candidates=[]`。

### Task 0.5：兼容 reviewer 可空字段

文件：

- `review_plan_workflow/schemas.py`
- `review_plan_workflow/nodes/llm_quality_reviewer.py`
- `tests/test_review_plan_workflow.py`

改动：

- 把 `question_type=null` 这类可空 reviewer 字段归一化为空字符串。
- target path 解析保持容错。

验收：

- 一个有用的 reviewer 结果不会因为某个可选定位字段是 null 而被整体丢弃。

## Phase 1：Canonical Contracts

### Task 1.1：定义 LessonSourcePack

文件：

- `review_plan_workflow/source_pack.py`
- `review_plan_workflow/schemas.py`
- `lesson_manager.py`
- 现有 schema bootstrap 里的迁移逻辑

字段：

```text
source_id
source_type
title
language
segments[]
detected_topics[]
math_blocks[]
teacher_actions[]
warnings[]
source_hash
created_at
```

规则：

- 文本、PDF、PPT、DOCX、录音转写全部进入这个格式。
- 音频 ASR 结果先缓存，再创建 source pack。
- source pack 归属于 version。

测试：

- 同一文本生成稳定 hash 和 segment IDs。
- 重新生成默认复用当前 version source pack。

### Task 1.2：定义 lesson_review_plan_v1

文件：

- `review_plan_workflow/plan_v1.py`
- `review_plan_workflow/schemas.py`
- `review_plan_workflow/nodes/plan_generator.py`
- `review_plan_workflow/nodes/revision.py`

字段：

```text
schema_version
document_title
audience
lesson_summary
knowledge_map[]
review_schedule[]
practice_tasks[]
self_check_questions[]
math_blocks[]
teacher_checkpoints[]
uncertainties[]
source_coverage[]
```

规则：

- LLM 只返回 `lesson_review_plan_v1`。
- 旧的 `days/blanks/choices/task_blocks` 转换移到 compatibility adapter。
- 新 validator 和 renderer 直接消费 v1。

测试：

- `plan.days` 这类包裹字段直接 schema fail。
- 缺答案直接 schema fail。
- 旧 stored version 仍可通过 compatibility adapter 渲染。

### Task 1.3：统一可打印题量函数

文件：

- `review_plan_workflow/printable_questions.py`
- `review_plan_workflow/quality_gate.py`
- `review_plan_templates/single_lesson_pdf.py`
- 后续 preview/frontend

改动：

- 创建唯一 canonical counting function。
- 返回：
  - 总可见题量
  - 每天题量
  - 答案区数量
  - 被丢弃或不可渲染的项目

验收：

- validator、PDF 和测试使用同一套 count 逻辑。

## Phase 2：拆分 Validator 和 Evaluator

### Task 2.1：确定性 Validator

文件：

- `review_plan_workflow/validator.py`
- `tests/test_review_plan_validator.py`

检查：

- schema 合法。
- days 完全匹配。
- 老师约束满足。
- 可见题量等于答案区数量。
- 每个任务有 action 和 output。
- 每个 self-check 有 answer。
- math placeholders 能解析。
- source coverage segment IDs 存在。
- renderer dry run 没有 dropped items。

验收：

- Lesson 100 这类“要求 10 道但 PDF 可见 7 道”的情况在 ready 前被 validator 拦截。

### Task 2.2：有边界的 Evaluator

文件：

- `review_plan_workflow/evaluator.py`
- `review_plan_workflow/quality_policy.py`
- `review_plan_workflow/nodes/llm_quality_reviewer.py`

规则：

- validator 通过或只有 soft warnings 后才运行。
- 不评估 broken schema。
- 返回结构化分类：
  - pedagogy
  - source_confidence
  - factuality
  - workload
  - style

验收：

- 低 source confidence 可以 warning，但不直接阻断。
- 数学答案错误必须阻断。

### Task 2.3：只做定点修复

文件：

- `review_plan_workflow/nodes/question_repair.py`
- `review_plan_workflow/nodes/revision.py`
- `review_plan_workflow/service.py`

规则：

- 题目级问题只修该题。
- source coverage 问题只修 coverage metadata 或 uncertainty 文案。
- 只有 schema-level failure 才允许 full-plan revision。
- 默认最多一次 repair attempt。

验收：

- 单个选择题答案错误不会触发完整 JSON 重写。

## Phase 3：速度和缓存

### Task 3.1：Source Cache

文件：

- `lesson_manager.py`
- `review_plan_workflow/source_pack.py`

缓存 key：

```text
raw_source_hash
cleaned_source_hash
source_pack_schema_version
parser_version
```

验收：

- 未改变 source 的重新生成，不重新跑 ASR 或文档解析。

### Task 3.2：Fast Path 和 High-Quality Path

文件：

- `review_plan_workflow/service.py`
- `review_plan_workflow/observability.py`

Fast path：

```text
source pack
-> writer
-> validator
```

High-quality path：

```text
fast path
-> evaluator
-> targeted repair
-> validator
```

验收：

- Fast path：ASR 后最多 2 次模型调用。
- High-quality path：ASR 后最多 3 次模型调用。
- Langfuse 和本地 run logs 能看到各阶段耗时。

### Task 3.3：长输入 Map-Reduce

文件：

- `review_plan_workflow/source_pack.py`
- `review_plan_workflow/source_brief.py`

改动：

- 按章节或时间窗口切分长输入。
- 每段抽局部 topics、examples、formulas。
- reduce 成一个 source pack。
- 缓存 segment-level extraction。

验收：

- 长逐字稿覆盖率提升，但不会每个 chunk 都生成完整计划。

## Phase 4：Renderer Contract

### Task 4.1：Renderer Dry Run

文件：

- `review_plan_templates/single_lesson_pdf.py`
- `review_plan_workflow/renderer_contract.py`

改动：

- renderer 返回 dropped items、visible question count、answer count、formula failures。
- quality validator 保存 ready 前消费这个 report。

验收：

- renderer 静默丢题无法上线。

### Task 4.2：Preview Math

文件：

- 前端复习计划详情/预览模块
- 后端 `math_blocks` serializer

改动：

- 用 KaTeX 或 MathJax 渲染 math placeholders。
- 公式失败时展示可读 fallback。

验收：

- 数学和物理 fixtures 的公式在 preview 中正确渲染。

### Task 4.3：DOCX 导出路径

决策：

- 如果排期紧，第一版 DOCX 可以保留可读 LaTeX。
- 如果数学/物理导出是上线刚需，用 Pandoc 把 Markdown/LaTeX math 转成 DOCX OMML。

验收：

- PDF/preview 先正确。
- DOCX 不静默损坏公式。

## Phase 5：观测和 Evals

### Task 5.1：Langfuse Trace 字段

字段：

- source_hash
- source_type
- source_pack_confidence
- generation_mode
- parsed_teacher_constraints
- model_call_count
- validator_result
- evaluator_result
- repair_count
- visible_question_count
- answer_key_count
- renderer_dropped_count
- latency_by_stage

验收：

- 不读取原始学生材料，也能诊断失败或低质量生成。

### Task 5.2：回归样本集

Fixtures：

- Lesson 100 pythagorean alpha/beta one-day 10-question request
- Dynamic geometry task_blocks case
- Sections/questions normalization case
- Low-evidence text-only case
- Wrong math answer repair case
- Formula transport case
- Regeneration same-source case

验收：

- CI 能发现可见题量回归和 source extraction 回归。

## Phase 6：产品语义

### Task 6.1：生成模式

用户可见标签保持明确：

- `当天课后复习`：把今天这节课内容压缩成当天完成。
- `5次间隔复习`：第 1、2、7、14、30 天。
- `每日连续复习`：第 1 天到第 N 天。
- `自定义日期`：用户选择的 day offsets。

验收：

- compressed 模式的 PDF 和前端文案不再出现 `第1天集中复习`。

### Task 6.2：重新生成 vs 重新渲染

产品定义：

- 重新生成：调用模型，新建 version，默认复用同一个 source pack，除非用户编辑 source。
- 重新渲染 PDF：不调用模型，内容不变，只重新生成文件。

验收：

- 老师可以修复显示/导出问题，而不改变生成内容。

## 实施顺序

推荐顺序：

1. Phase 0 热修。
2. Phase 1 canonical contracts。
3. Phase 2 validator/evaluator 拆分。
4. Phase 3 cache 和速度。
5. Phase 4 renderer/DOCX。
6. Phase 5 evals 和 observability。
7. Phase 6 产品语义。

不要在 Phase 0 和 Phase 1 稳定前，先做 Phase 4 的 DOCX 公式完美化。

## 全局验收标准

- Lesson 100 加 `题目控制在10道题` 后，输出正好 10 道可见题和 10 条答案。
- 最新已完成质量结果失败时，不能被后续空 run 隐藏。
- PDF 可见题量等于 canonical printable count。
- source pack 能从用户提供的逐字稿抽到标题和关键章节。
- compressed 模式使用 `当天课后复习`，不使用 `第1天集中复习`。
- 新生成和重新生成遵守同一 source/constraint 合同。
- Fast path 在 ASR 后最多 2 次模型调用。
- High-quality path 在 ASR 后最多 3 次模型调用。
- renderer 不能静默丢掉已生成题目。

## 实现后的验证命令

Phase 0 代码改完后运行：

```bash
python3 -m py_compile app.py lesson_manager.py review_plan_workflow/source_brief.py review_plan_workflow/quality_gate.py review_plan_workflow/schemas.py review_plan_templates/single_lesson_pdf.py
python3 -m unittest tests.test_review_plan_workflow tests.test_review_plan_async_api tests.test_single_lesson_pdf_unification -v
git diff --check
```

Canonical contract 工作完成后运行：

```bash
python3 -m unittest tests.test_review_plan_source_brief tests.test_review_plan_workflow tests.test_review_plan_evals tests.test_single_lesson_pdf_unification -v
cd frontend && npm run build
git diff --check
```
