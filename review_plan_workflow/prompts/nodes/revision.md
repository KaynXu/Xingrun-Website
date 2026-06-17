# Revision

根据 qualityReviewer issues 做局部修复。

只修复指出的问题，不完全重写，不引入新虚构信息，最多 revision 2 次。

## Hard Repair Rules

- 如果 quality issue 指向选择题质量，逐日检查所有 `choices`。
- 任何选项只写 `A`、`B`、`C`、`D`，或少于 4 个完整选项，必须重写成完整选择题。
- 每道选择题必须包含 `question`、4 个完整 `options`、`answer`；`options` 写成 `A. 具体选项内容` 到 `D. 具体选项内容`。
- `answer` 只能是 `A`、`B`、`C`、`D`，不能为空，不能写解释句。
- 如果无法写出真实干扰项，就删除该选择题并改成同知识点填空题或主动回忆卡片，不能保留空壳。
