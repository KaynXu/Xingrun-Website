# 课后复习计划 PDF 生成说明

本目录已经同步到主项目内，作为新版课后复习计划模板工作区使用。

## 文件说明

- `generate_review_pdfs.py`：根据课堂总结自动生成复习计划 PDF。
- `pdf_output/`：脚本运行后生成的 PDF 文件目录。

## 当前生成内容

当前脚本默认保留 1 个版式版本，但每次运行都会生成一个新的 PDF 文件，不覆盖旧文件：

- 语言风格：中文版
- 原话占比：10%-15%
- 页面风格：带课堂原话回放
- 字距：全局略微加宽
- 封面：不显示版本信息总表
- 使用对象：老师发给学生使用
- 单次时长：10-20 分钟
- 结构要求：每一个复习日都完整复习整节课内容
- 分页要求：课堂方法复盘、口述卡片等大模块在空间不足时整体移到下一页

知识点加练的默认策略已经并入最终版：

- Day 1/2 用填空+选择
- Day 7/14 用口述卡片
- Day 30 用填空+选择

## 当前输出文件

- `review-plan-chinese-only-quote-replay-default-时间戳.pdf`

## 运行方法

```bash
python review_plan_templates/generate_review_pdfs.py
```

如需保留旧的双语对照版，可显式传入：

```bash
python review_plan_templates/generate_review_pdfs.py hybrid
```

如需指定课程包：

```bash
python review_plan_templates/generate_review_pdfs.py default review_plan_templates/lesson_pack_vector_workflow.py
```

## 备注

- PDF 已包含：使用说明、5 个时间节点复习页、填空题、选择题、课堂原话、30 天总复盘、自查答案。
- 每一个时间节点都要求学生完整扫过整节课，不再按“当天只复习部分内容”的方式分拆。
- 默认正式版为中文版；旧双语版仅作为可选变体保留。
- 每次重新运行都会生成一个新的带时间戳 PDF，不会删除或覆盖之前的 PDF。
- 若后续更换课堂总结，可直接修改对应的 `lesson_pack_*.py`，或在运行时传入新的课程包文件。
- 生成的 PDF 会写入 `review_plan_templates/pdf_output/`。