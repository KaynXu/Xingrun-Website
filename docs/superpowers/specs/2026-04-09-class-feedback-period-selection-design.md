# Class Feedback Period Selection Design

## Goal

把“班级反馈生成”从“老师手填开始日期 + 结束日期”的自由时间范围模式，升级为“老师显式选择反馈周期类型”的结构化模式。

本次设计要解决两个问题：

- 老师当前只能按日期范围创建反馈任务，系统再被动推断 `daily / weekly / custom`，无法稳定表达“月反馈”或“阶段反馈”。
- 历史任务、AI 上下文、后续基线对比，目前都缺少明确的周期语义，导致“同类周期对比”不够稳定。

目标状态是：老师在创建任务时直接选择 `日反馈 / 周反馈 / 月反馈 / 阶段反馈`，系统生成并保存规范周期标签，同时保留底层 `start_date / end_date` 用于命中课次素材。

## Confirmed Scope

- 只覆盖“班级反馈生成”流程。
- 本次不改单节复习计划、月度复习计划、咨询解析等其它流程。
- 反馈周期类型固定为四类：
  - `日反馈`
  - `周反馈`
  - `月反馈`
  - `阶段反馈`
- 周期标签必须规范化，不允许老师手填自由文本。
- 周期标签格式已经确认如下：
  - 日：`YYYY-MM-DD`
  - 周：`YYYY第N周`
  - 月：`YYYY三月`
  - 阶段：`YYYY春季` / `YYYY秋季` / `YYYY寒假` / `YYYY暑假`
- 日反馈使用 ISO 日期格式，不使用 `YYYY年M月D日`。
- 系统仍然需要保存 `start_date` 与 `end_date`，用于课次筛选、历史范围回看与 AI 素材汇总。
- 当前 `period_granularity` 不能再使用 `custom` 承载月反馈和阶段反馈，必须升级为明确语义。

## Existing Context

- 当前“班级反馈生成”已经存在完整任务流：创建任务、补备注、生成草稿、自动保存、确认写回长期积累。
- 当前任务创建接口只接受：
  - `class_id`
  - `start_date`
  - `end_date`
- 当前 `lesson_manager.py` 通过 `_derive_class_feedback_period_fields()` 自动推断粒度：
  - `1 天 -> daily`
  - `6-8 天 -> weekly`
  - 其它 -> `custom`
- 当前前端页面顶部仍是班级 + 起止日期输入，不支持显式选择反馈模式。
- 当前历史基线查找逻辑已经支持“优先同粒度，再回退到较宽松范围”，因此保留粒度语义对后续 AI 很重要。

## Recommended Approach

采用“显式反馈模式 + 规范周期标签 + 自动推导日期范围 + 后端结构化持久化”的方案。

### Why This Approach

- 只改前端展示不够，因为后端、历史任务、AI 上下文仍然无法知道本次到底是“2026第1周”还是“2026春季”。
- 保留日期范围但新增周期语义，可以同时满足：
  - 老师按业务概念创建任务
  - 系统按日期命中素材
  - AI 按同类周期寻找基线
- 比完整拆成多个松散字段更实用，避免把本轮需求做成过度复杂的通用时间模型。

## Data Model

### Task Fields

`class_feedback_tasks` 保持“业务周期语义”和“实际日期范围”双轨并存。

保留字段：

- `start_date`
- `end_date`
- `period_length_days`

调整字段：

- `period_granularity`
  - 旧值：`daily / weekly / custom`
  - 新值：`daily / weekly / monthly / stage`

新增字段：

- `period_label`
  - 保存规范周期标签，例如：
    - `2026-04-09`
    - `2026第15周`
    - `2026三月`
    - `2026秋季`

### Why Keep Date Range

即使老师通过“周 / 月 / 阶段”创建任务，系统仍需要实际范围去完成：

- 过滤本周期内课次记录
- 汇总阶段素材
- 在 UI 中解释任务覆盖区间
- 为历史任务回看提供可验证边界

因此本轮不是用 `period_label` 替代日期，而是让 `period_label` 成为主语义，日期范围成为派生事实。

## Period Rules

### Daily

- 输入：某一天
- 标签：`YYYY-MM-DD`
- 范围：`start_date == end_date == selected_date`
- `period_granularity = daily`

### Weekly

- 输入：年份 + 周次
- 标签：`YYYY第N周`
- 范围：该周的周一到周日
- `period_granularity = weekly`

这里的“第 N 周”采用系统统一规则生成，避免前端自己拼字符串后和后端算法不一致。

### Monthly

- 输入：年份 + 月份
- 标签：`YYYY三月` 等中文月名格式
- 范围：该自然月的 1 日到月末
- `period_granularity = monthly`

中文月份固定映射为：

- `1 -> 一月`
- `2 -> 二月`
- `3 -> 三月`
- `4 -> 四月`
- `5 -> 五月`
- `6 -> 六月`
- `7 -> 七月`
- `8 -> 八月`
- `9 -> 九月`
- `10 -> 十月`
- `11 -> 十一月`
- `12 -> 十二月`

### Stage

- 输入：年份 + 阶段名
- 阶段名固定为：
  - `春季`
  - `秋季`
  - `寒假`
  - `暑假`
- 标签：`YYYY春季`、`YYYY秋季`、`YYYY寒假`、`YYYY暑假`
- `period_granularity = stage`

阶段对应日期范围采用第一版固定规则：

- `春季 = YYYY-02-01 ~ YYYY-06-30`
- `暑假 = YYYY-07-01 ~ YYYY-08-31`
- `秋季 = YYYY-09-01 ~ (YYYY+1)-01-31`
- `寒假 = YYYY-01-01 ~ YYYY-02-28/29`

### Stage Year Semantics

阶段标签中的年份不是“结束日期年份”，而是“业务标签年份”。

例子：

- `2026秋季` 对应 `2026-09-01 ~ 2027-01-31`
- `2026寒假` 对应 `2026-01-01 ~ 2026-02-28/29`

这样能够保证老师使用“2026秋季”这个自然业务概念时，标签与任务名保持直观一致。

## Backend Design

### API Create Contract

`POST /api/class-feedback/tasks` 不再只接受自由日期范围，而是接受结构化模式输入。

建议请求体：

- `class_id`
- `period_granularity`
- 模式专属参数

日反馈：

- `anchor_date`

周反馈：

- `year`
- `week`

月反馈：

- `year`
- `month`

阶段反馈：

- `year`
- `stage_name`

后端负责完成统一推导：

- `period_label`
- `start_date`
- `end_date`
- `period_length_days`

### Why Backend Must Derive Final Values

前端虽然也会展示规范标签，但不能让前端成为唯一真相。后端必须做最终校验和推导，原因包括：

- 避免前端错误拼接标签
- 避免不同前端版本生成不一致的周/月/阶段规则
- 避免测试只能验证 UI、无法验证真实存储

### Storage Migration

`class_feedback_tasks` 需要新增 `period_label` 字段，并为历史任务做回填。

回填规则：

- 旧 `daily` 任务回填为 `YYYY-MM-DD`
- 旧 `weekly` 任务回填为 `YYYY第N周`
- 旧 `custom` 数据不要求在本轮被完全强归类

本轮推荐的落地做法是：

- 对新创建任务严格使用 `daily / weekly / monthly / stage`
- 对旧 `custom` 任务保留兼容读取能力，但不允许再创建新的 `custom`

这样可以控制改动风险，避免一次性强改历史数据导致错误归类。

### Baseline Lookup

历史基线查找逻辑继续保留“优先同粒度”的原则，但匹配集合改为：

- `daily`
- `weekly`
- `monthly`
- `stage`

也就是说：

- 月反馈优先找上一次月反馈
- 阶段反馈优先找上一次阶段反馈
- 找不到同粒度时，再回退到更宽松的历史记录

这样“进步明显 / 有点回落 / 变化不大”等相对表述，才不会把“日反馈”错误地和“阶段反馈”直接对比。

## Frontend Design

### Create Bar

当前 [frontend/src/App.tsx](frontend/src/App.tsx) 顶部控制栏里的两个日期输入需要被模式驱动控件替换。

新的创建流程：

1. 选择班级
2. 选择反馈模式
3. 根据模式展示专属选择器
4. 点击“创建反馈任务”

模式专属选择器：

- 日反馈：日期选择器
- 周反馈：年份 + 周次选择器
- 月反馈：年份 + 月份选择器
- 阶段反馈：年份 + 阶段选择器

### UI Principle

老师不输入自由文本标签，界面只允许选择结构化值，然后即时显示系统生成后的规范标签。

例如：

- 选 `2026` + `第 1 周`，界面显示 `2026第1周`
- 选 `2026` + `3 月`，界面显示 `2026三月`
- 选 `2026` + `秋季`，界面显示 `2026秋季`

### Workspace Summary

[frontend/src/ClassFeedbackGenerationWorkspace.tsx](frontend/src/ClassFeedbackGenerationWorkspace.tsx) 与摘要区的主展示应从“时间范围”升级为“反馈阶段”。

推荐展示顺序：

- `反馈阶段：2026第15周`
- `覆盖范围：2026-04-06 至 2026-04-12`

也就是：

- `period_label` 做主标题级展示
- `start_date / end_date` 做辅助说明

## Validation Rules

### Create-Time Validation

前后端都要做基础校验，但以后端为准。

校验内容包括：

- `period_granularity` 必须属于允许集合
- 日反馈必须有合法 `anchor_date`
- 周反馈必须有合法 `year` 与 `week`
- 月反馈必须有合法 `year` 与 `month`
- 阶段反馈必须有合法 `year` 与 `stage_name`
- 任何模式都必须最终生成合法 `start_date <= end_date`

### No Freeform Label Editing

`period_label` 不允许由前端自由输入。

原因：

- 老师容易输入不一致格式
- 周、月、阶段标签的规范一旦被自由输入，就无法可靠用于历史筛选和展示
- 这类字段更适合作为系统派生值，而不是用户编辑值

## Testing

### Backend

需要补充或更新：

- 创建日反馈任务时生成正确标签与日期范围
- 创建周反馈任务时生成正确标签与日期范围
- 创建月反馈任务时生成正确标签与日期范围
- 创建阶段反馈任务时生成正确标签与日期范围
- 历史基线查询优先使用同粒度任务
- 旧 `custom` 数据的兼容读取不被破坏

重点文件：

- [tests/test_class_feedback_api.py](tests/test_class_feedback_api.py)
- [tests/test_lesson_class_feedback_store.py](tests/test_lesson_class_feedback_store.py)

### Frontend

需要补充或更新：

- 模式选择器渲染
- 各模式专属选择器渲染
- 创建任务 payload 改为显式模式参数
- 工作台摘要优先显示 `period_label`
- 不再依赖手填 `startDate / endDate` 输入框

重点文件：

- [frontend/src/class-feedback-generation.test.tsx](frontend/src/class-feedback-generation.test.tsx)

## Rollout Strategy

### Step 1

先完成后端存储与创建接口升级，让新任务具备明确的 `period_granularity + period_label`。

### Step 2

前端创建栏改成模式驱动，并切换到新请求参数。

### Step 3

调整工作台摘要、状态文案与历史任务展示，让老师看到的是“反馈阶段”，不是裸日期范围。

### Step 4

补齐前后端回归测试，确认：

- 新建四类任务都正确
- 老任务仍可读取
- 同粒度历史基线对比仍成立

## Out Of Scope

- 不在本轮把阶段范围做成机构可配置能力。
- 不在本轮重做所有历史 `custom` 数据的强归一化清洗。
- 不在本轮扩展到其它 AI 生成功能。
- 不在本轮做通用“时间周期 DSL”或跨模块统一时间框架。

## Closed Decisions

- 日反馈标签使用 `YYYY-MM-DD`
- 周反馈标签使用 `YYYY第N周`
- 月反馈标签使用 `YYYY三月` 这类中文月份
- 阶段反馈标签使用 `YYYY春季 / YYYY秋季 / YYYY寒假 / YYYY暑假`
- 前端不允许自由输入标签
- 后端负责最终派生与校验
- 新任务不再创建新的 `custom` 粒度
