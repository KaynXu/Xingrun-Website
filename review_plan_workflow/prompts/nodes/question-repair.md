# Question-Level Repair

只修复输入里的目标题目，不重写整份复习计划。

必须根据 issue 描述重新验算题目、选项、答案和解析。不能改目标题目之外的计划字段，不能虚构教材页码、考试日期、学生成绩或老师原话。

## Output

返回严格 JSON object：

```json
{
  "repairs": [
    {
      "target_id": "day1_choice2",
      "kind": "choice",
      "question": "完整题干",
      "options": ["A. 具体选项", "B. 具体选项", "C. 具体选项", "D. 具体选项"],
      "answer": "A",
      "analysis": "一句话验算或判断理由"
    }
  ]
}
```

填空题返回：

```json
{
  "target_id": "day1_blank2",
  "kind": "blank",
  "text": "含______的完整题干",
  "answer": "标准答案"
}
```

主动回忆/口述卡返回：

```json
{
  "target_id": "day1_recall3",
  "kind": "active_recall",
  "instruction": "完整、可独立口述的任务题干或推导要求",
  "expected": "一句话给出正确推导链或参考答案"
}
```

## Rules

- 每个输入 target 必须返回一个同名 `target_id`。
- `choice` 必须有完整 `question`、4 个完整 `options`、单字母 `answer`。
- `blank` 必须有完整 `text` 和非空 `answer`。
- `active_recall` 必须有完整 `instruction`，数学推导类还必须给出可验算的 `expected`。
- 如果原题事实或答案错误，优先修正答案和解析；必要时才重写题干。
- 不返回整份 plan JSON。
