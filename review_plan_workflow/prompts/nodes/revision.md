# Targeted Revision

根据本地规则和 LLM quality reviewer issues 做局部修复。

只修复指出的问题，不完全重写，不引入新虚构信息，最多 revision 2 次。

必须参考 parent planner 蓝图：修订后的计划要更贴近蓝图里的知识点、错因、每日复现目标和题型设计。蓝图没有提供的信息不能编造成事实。

## Hard Repair Rules

- 修订后必须继续使用工作流变量里的本次 `review_days`，不能把 compressed/daily/custom 计划改回固定 1/2/7/14/30。
- 老师本次生成要求只能在结构、事实、schema、PDF 安全和质量门禁硬规则内执行；冲突时以硬规则为准。
- 如果 quality issue 指向全课覆盖清单，必须重写 `full_review_topics` 为 5-10 条颗粒化条目；不能只写课题名，不能只写“本节课内容/综合复习”。优先从 parent planner 的 knowledge_map、day_strategies、课堂总结、当前题干中抽取知识点、方法链和错因。
- 如果 quality issue 指向当天 10 题覆盖不足，不要增加题量；在既定题量内重分配题目，把缺失的 source key chains 放进 `full_review_topics`、填空/选择题和主动回忆卡片。
- 如果 quality issue 指向课堂金句/课堂原话，删除所有使用说明、完成标准、正确率要求和系统兜底文本；只有课堂文本中有证据的老师方法句才能放进 `quotes`，没有证据就保留 `quotes: []`。
- 如果 quality issue 指向数学公式或 LaTeX 传输，必须把相关题干、选项、答案、解析里的分式、根式、对数、分段函数、不等式链改写为 `$...$` 包裹且 JSON 反斜杠正确转义的 LaTeX。
- 禁止保留 `begincases/endcases`、`sqrt[3]x`、`log_(...)`、控制字符、乱码公式或被转义吃坏的文本。
- 如果 quality issue 指向选择题质量，逐日检查所有 `choices`。
- 任何选项只写 `A`、`B`、`C`、`D`，或少于 4 个完整选项，必须重写成完整选择题。
- 每道选择题必须包含 `question`、4 个完整 `options`、`answer`；`options` 写成 `A. 具体选项内容` 到 `D. 具体选项内容`。
- `answer` 只能是 `A`、`B`、`C`、`D`，不能为空，不能写解释句。
- 如果无法写出真实干扰项，就删除该选择题并改成同知识点填空题或主动回忆卡片，不能保留空壳。

## Targeting Rules

- issue 指向某一天时，只重写那一天相关字段。
- issue 指向题目质量时，优先重写 `blanks`、`choices`、主动回忆卡片，不要改动首页样式字段。
- issue 指向“空泛/模板化”时，必须把题目改成与本节课主题、薄弱点和错因绑定的可作答内容。
- 修订后仍必须返回完整 JSON object，不能只返回 patch。
