# 复习计划稳定生成链路审计

日期：2026-07-02
分支：`codex/review-plan-chain-audit`
范围：复习计划生成质量、速度、老师要求、重新生成一致性、校验和渲染。

## 结论

当前链路已经不再是最早那种“把原文丢给模型直接写 PDF”的状态，已经有 `source_brief`、质量门禁、题目级修复、版本记录和异步任务。但它还没有稳定到可以作为产品合同。

核心问题不是模型不会写，而是系统仍然把太多职责混在一起：

```text
输入理解
输出结构
老师约束
质量判断
PDF 渲染
交付状态
```

这些职责需要拆成稳定合同：

```text
文本 / PDF / PPT / DOCX / 录音
-> LessonSourcePack
-> lesson_review_plan_v1 JSON
-> 确定性 validator + 有边界的 evaluator
-> 受控 preview / PDF / DOCX renderer
```

继续补 prompt 和加重试只能缓解症状，不能保证可见题量、source 覆盖、重新生成一致性和生成速度。

## 样本证据：Lesson 100 / Version 72

线上记录：

```text
lesson_id=100
version_id=72
status=ready
generation_options={
  "schedule_mode": "compressed",
  "review_days": [1],
  "daily_count": 1,
  "user_requirements": "题目控制在10道题",
  "source": "create"
}
```

线上 PDF：

```text
文件：/Users/xiaodi/Downloads/勾股数、特殊角与和角推导-100-v1.pdf
页数：3
抽取文本长度：1235 字符
可见题量：5 道填空 + 2 道选择 = 7 道
包含：当天课后复习，当天复习后应留下的内容
不包含：10题，待确认，30天后应留下的内容
```

Codex 本地对照 PDF，使用同一份课堂文本和同一个老师要求：

```text
文件：/Users/xiaodi/Desktop/01_星润与复习计划/xingrun.web/lingshiwenjian/20260702-勾股数特殊角度αβ与和角推导-当天课后复习计划-10题对照版-20260702-194148.pdf
页数：5
抽取文本长度：2528 字符
可见题量：10 道
包含：10题对照版，当天课后复习，当天复习后应留下的内容
```

这个样本说明：

- 前端和后端收到了老师要求。
- 线上链路没有把“10 道题”当成确定性合同执行。
- PDF renderer 从生成结构里丢了内容。
- 同一个 version 已经存在失败质量结果，但最终版本仍变成了 `ready`。

## 当前实现快照

最新 `origin/develop` 上的当前链路：

```text
新建 / 重新生成请求
-> normalize_generation_options()
-> ReviewPlanInput
-> intake_normalizer
-> source_brief_builder
-> source_analyzer
-> subject_router
-> scope_planner
-> time_allocator
-> task_blueprint
-> parent_planner LLM + fallback
-> prompt_bundle_builder
-> plan_generator LLM
-> normalize_final_review_plan()
-> deterministic quality_gate
-> 按策略运行 LLM quality reviewer
-> question_repair 或 revision
-> 记录质量结果
-> single_lesson_pdf renderer
```

这比早期 raw text 直接生成 PDF 明显更好。剩余问题是：内部对象仍然是“局部结构 + 兼容适配器”，还不是一个 canonical document contract。

## 问题清单

### P0：交付状态会隐藏失败质量结果

证据：

- `app.py:895` 使用 `_review_plan_quality_failure_message(version_id)`。
- 这个函数调用 `get_latest_review_plan_run_for_version(version_id)`。
- `lesson_manager.py:5757` 按 `updated_at DESC, id DESC` 返回最新 run，不判断这个 run 是否有真实质量结果。

线上观察：

- Version 72 曾经有真实质量结果：`score=78`、`passed=false`、`must_revise=true`。
- 同一个 version 后面产生了更新的空 run 或 interrupted run。
- 交付链路读到了错误的最新 run，所以失败质量结果没有阻止 `ready`。

修复方向：

- 新增 helper：返回某个 version 最新的、已完成的、带非空 `quality_review_json` 的 run。
- `_review_plan_quality_failure_message()` 和 ready/failed 决策使用这个 helper。
- `running/interrupted` 空 run 只能作为任务 telemetry，不能作为最终质量事实。

验收：

- 如果某个 version 最新完成质量结果是失败，则不能变成 ready；除非后面存在更新的、已完成的、通过质量结果。

### P0：老师 prompt 现在是建议，不是硬合同

证据：

- `generation_options.user_requirements` 已进入 `ReviewPlanInput`。
- `parent_planner`、`plan_generator`、`question_repair` 和 prompt 都能收到它。
- validator 对 compressed 一天只要求至少 5 个可打印题目。

线上观察：

- 老师要求 `题目控制在10道题`。
- 线上 PDF 交付了 7 道可见题。

修复方向：

- 在 planning 前把老师要求解析成确定性的 `GenerationConstraint`。
- 至少解析：
  - 总可打印题量
  - 每天题量
  - 偏好的题型
  - 排除的题型
  - 复习节奏意图
- 原始 prompt 仍给 LLM，但 parsed constraints 必须进入 validator。

验收：

- `题目控制在10道题` 表示必须正好 10 道可见可打印题，并且答案区正好 10 条；如果做不到，应在生成前或保存前拦截，并给用户可读原因。

### P0：PDF renderer 截断了选择题

证据：

- `review_plan_templates/single_lesson_pdf.py:410-421` 会收集所有显式 choices。
- `choice_values = explicit_choices[:2]` 会丢掉第二题之后的选择题。

线上观察：

- 生产 `plan_json` 有 3 道选择题。
- PDF 只渲染了 2 道选择题。

修复方向：

- 渲染所有通过 PDF-readiness 的 normalized choices。
- 如果模板有视觉密度上限，这个上限必须暴露给 validator，而不是 renderer 静默截断。
- 测试中对比 plan JSON 可打印题量和 PDF 可见题量。

验收：

- day 1 有 5 道填空和 3 道选择时，PDF 渲染 8 道题，答案区也有 8 条。

### P1：source brief 有价值，但抽取太浅

证据：

- `review_plan_workflow/source_brief.py:25` 的标题 marker 只有 `本节课主题：`、`主题：`、`topic:`。
- `_title_candidates()` 只读显式 topic 或这些 marker。
- `_looks_like_knowledge_point()` 只接受 `知识点：`、`重点：`、`结论：`、`定理：`、`公式：`、`性质：` 等 marker。
- 用户提供的逐字稿首行是自然标题：`勾股数、特殊角度αβ与和角推导完整课堂逐字稿`，后面有 `第一部分：...`、`一、奇数开头整数勾股数` 这类章节标题。

线上观察：

- `source_brief_json` 里 `topic=null`、`knowledge_points=[]`、`lesson_title_candidates=[]`。
- 输入材料本身很丰富，但下游生成只能靠 fallback assumptions。

修复方向：

- 把当前 `source_brief` 升级为 `LessonSourcePack`。
- 增加确定性抽取：
  - 首行课堂标题
  - 中文章节标题
  - 枚举型知识点列表
  - 公式和数学 token
  - 老师动作词，例如 `必须背熟`、`课后作业`、`明天抽查`
- 保留 confidence；低 confidence 本身不应该让可打印计划失败。

验收：

- 用户给的这份逐字稿在 generator 运行前，就能抽到包含 `勾股数` 的标题候选，并抽到至少 5 个 knowledge points / method chains。

### P1：输出合同仍依赖旧结构适配

证据：

- 当前 generator 要输出现有 `normalize_final_review_plan()` 和 `single_lesson_pdf.py` 能理解的 JSON。
- 最近修复过 `sections[].questions` 和 `task_blocks` 归一化，把它们提升到 `days[].blanks/choices/items`。

影响：

- writer 可以生成多种“看起来合理”的结构。
- quality gate 和 PDF renderer 可能对“什么算可打印题”理解不一致。
- 每出现一种新字段，就要补 adapter，而不是升级 schema。

修复方向：

- 定义 `lesson_review_plan_v1`，作为唯一允许的新生成输出。
- 老版本兼容只放在边界 adapter。
- validator 和 renderer 读取同一个 canonical object。

验收：

- 存在一个唯一的 canonical printable question count 函数，validator、PDF renderer、preview 和测试都用它。

### P1：质量门禁方向正确，但职责混杂

当前 hard checks 包括：

- schema / review days
- 是否有可打印题
- topic / full_review_topics 密度
- 选择题完整度
- 公式传输损坏
- placeholder 文本
- LLM reviewer 判断的数学或事实错误

问题：

- 产品可交付性、source 证据强度、教学质量、renderer 安全性被混在同一个 pass/fail  lane。
- 这导致之前低证据计划失败率过高。
- 最近的 soft-pass policy 有帮助，但仍然依赖描述文本，边界脆弱。

修复方向：

拆成三层：

```text
validator
  确定性、便宜、不调用 LLM
  检查 schema、可见题量、答案区、days、renderer safety、math block 引用

evaluator
  有边界的 LLM
  检查教学有效性、适配学生、关键遗漏、证据漂移

repair
  只修失败字段或失败题目
  默认最多一次
```

验收：

- source 证据弱只能产生 warning，不能阻止一份自洽、可打印、标明 fallback 的计划。
- 错答案、坏公式、缺答案区、renderer 不一致仍然必须拦截。

### P1：速度瓶颈仍然来自大 payload LLM 调用

当前已有改进：

- parent planner 有 fallback。
- local quality/source confidence 足够时可以跳过 LLM reviewer。
- 可定位问题已经有 question-level repair。
- 机构并发已经支持最多 10 个任务。

剩余瓶颈：

- source 理解仍会把较长 cleaned transcript 片段带到下游。
- `parent_planner`、writer、evaluator、repair 都依赖模型可用性。
- source brief 弱时，下游 prompt 更长、更不确定。

修复方向：

- 按 source hash + generation settings hash 缓存 transcript、解析文本、`LessonSourcePack` 和 plan。
- fast path：

```text
deterministic parse
-> 一次 source-pack extraction 或 deterministic pack
-> 一次 writer call
-> deterministic validator
```

- high-quality path：

```text
fast path
-> 必要时 evaluator
-> 只修失败字段或题目
```

验收：

- ASR 之后，fast path 最多 2 次模型调用。
- ASR 之后，high-quality path 最多 3 次模型调用。
- 单题答案错误不能触发完整 plan JSON 重写。

### P1：新生成和重新生成仍可能效果不一致

当前状态：

- 重新生成会创建新 version，也可以复用当前 version source artifacts。
- 但它仍然使用当前 prompt、当前 runtime config 和当前 options 重新跑。
- 非零 temperature 和 fallback 路径会让结果差异继续存在。

正确产品定义：

- 新生成：摄入 source，构建 source pack，生成 version。
- 重新生成：默认复用所选 version 的 source pack 和明确 generation settings；用户改设置时才改变约束。
- 重新渲染：不调用模型；同一 canonical JSON，只生成新的文件输出。

验收：

- `重新生成` 和 `新建生成` 不要求字节级一致，但必须遵守同一 source pack、同一 constraints、同一题量合同、同一 renderer 合同。
- `重新渲染PDF` 不应改变生成内容。

## 目标架构

### 1. LessonSourcePack

所有输入统一成一个结构：

```json
{
  "source_id": "sha256:...",
  "source_type": "text|pdf|pptx|docx|audio_transcript",
  "title": "勾股数、特殊角度αβ与和角推导",
  "language": "zh",
  "segments": [
    {
      "id": "seg-001",
      "heading": "整数勾股数",
      "text": "...",
      "start_offset": 0,
      "end_offset": 120,
      "speaker": "teacher",
      "confidence": 0.88
    }
  ],
  "detected_topics": [],
  "math_blocks": [],
  "teacher_actions": [],
  "warnings": []
}
```

音频规则：

```text
audio upload
-> shared ASR
-> transcript cache
-> optional transcript polish
-> LessonSourcePack
```

音频不能直接进入 plan generator。

### 2. lesson_review_plan_v1

模型只生成这个 JSON：

```json
{
  "schema_version": "lesson_review_plan_v1",
  "document_title": "",
  "audience": {"subject": "", "grade": ""},
  "lesson_summary": "",
  "knowledge_map": [],
  "review_schedule": [],
  "practice_tasks": [],
  "self_check_questions": [],
  "math_blocks": [],
  "teacher_checkpoints": [],
  "uncertainties": [],
  "source_coverage": []
}
```

LLM 不生成 CSS、HTML、PDF layout 或 DOCX layout。

### 3. 公式合同

公式不要无约束地散落在正文里。

```text
正文引用：牛顿第二定律可以写作 {{math:newton_second_law}}。
结构保存：{"id": "newton_second_law", "latex": "F = ma", "display": true}
```

Preview 使用 KaTeX 或 MathJax。DOCX 使用 Pandoc 或 OMML 转换路径。如果第一阶段暂不做完美 DOCX 公式，DOCX 至少保留可读 LaTeX，同时 preview/PDF 必须正确。

### 4. Validator 先于 Evaluator

Validator 检查：

- 标题存在。
- review days 和 generation options 完全一致。
- 可见题量满足老师约束。
- 每个 practice task 有动作、答案和产出。
- 每个 self-check question 有答案或解释。
- 每个 math placeholder 都能找到 math block。
- 每个 math block 引用都有效。
- source coverage 引用存在的 segments。
- renderer dry run 不丢内容。

Evaluator 检查：

- 任务顺序是否有教学意义。
- 学生负担是否合理。
- 题目是否覆盖关键知识点。
- 弱 source assumptions 是否清楚。
- 计划是不是只做了摘要，而不是复习安排。

默认最多一次有边界的 repair。

## 开源策略

复用成熟思路，不整套搬平台。

- Claw-ED：借鉴结构化中间对象和质量门禁，不引入整套 CLI/本地教学包架构。
- Skill-Anything：借鉴 section-aware parsing、map-reduce、cache、concurrency、fast/smart model routing，用来处理长逐字稿和长文档。
- Open Notebook：借鉴“上传 source + 选择固定 transformation”的产品形态，不照搬整套 runtime。
- faster-whisper / WhisperX：保留 faster-whisper 作为 fallback；只有说话人分离和 word timestamps 成为刚需时，再评估 WhisperX。
- MarkItDown / Docling / MinerU：简单 Office/PDF 继续用 MarkItDown；复杂 PDF、公式、OCR、表格和阅读顺序再评估 Docling 或 MinerU。
- Instructor / PydanticAI：用于 `lesson_review_plan_v1` 的 schema-constrained generation 和 retry；如果只是稳定 JSON，Instructor 更轻。
- KaTeX / Pandoc：KaTeX 做 preview；公式导出成为刚需时，用 Pandoc 做 DOCX math。

避免：

- 为这个功能整体迁移 LangChain/Haystack。
- 默认使用 writer/reviewer/researcher 多智能体循环。
- 让模型写最终文档布局。

## 目标指标

每次生成记录：

- source pack confidence
- source pack segment count
- source coverage ratio
- model call count
- stage latency
- validator pass/fail category
- evaluator pass/fail category
- repair count
- visible question count
- answer-key count
- PDF renderer dropped-count
- teacher constraint compliance
- successful version rate

## 回归样本

新增 eval fixtures：

- `lesson-100-pythagorean-alpha-beta-one-day-10q`
- `low-evidence-text-only-math`
- `task_blocks-printable-questions`
- `sections.questions-printable-questions`
- `choice-answer-wrong-math-repair`
- `pdf-choice-count-no-truncation`
- `same-source-regeneration-contract`

## 最终判断

当前实现方向是对的：source brief、有边界的质量策略、题目级修复、版本管理和异步任务都值得保留。

下一步不是继续改 prompt，而是锁住产品合同：

```text
同一 source + 同一 constraints
-> 同一 canonical structure requirements
-> 同一 validator result
-> 同一 visible renderer result
```

这是“能演示”和“能给老师稳定使用”的分界线。
