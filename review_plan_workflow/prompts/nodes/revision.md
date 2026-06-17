# Targeted Revision

根据本地规则和 LLM quality reviewer issues 做局部修复。

只修复指出的问题，不完全重写，不引入新虚构信息，最多 revision 2 次。

必须参考 parent planner 蓝图：修订后的计划要更贴近蓝图里的知识点、错因、每日复现目标和题型设计。蓝图没有提供的信息不能编造成事实。

## Hard Repair Rules

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
