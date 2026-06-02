# 学生错题回顾 / 错题本自动生成系统评估报告

日期：2026-06-03

本文是对当前“学生错题回顾 / 错题本自动生成系统”的证据型评估，只记录审查、诊断和改进建议。本文不改 prompt、不改代码、不替换现有工作流，也不重新设计一套独立系统。

## 审查依据

- Skill：`using-superpowers`，要求被点名或相关的 skill 必须读取并使用。
- Skill：`plan-eng-review`，用于检查系统边界、数据流、错误路径、测试覆盖和可复现性。
- Skill：`plan-design-review`，用于检查信息架构、状态、设计系统、AI slop 和响应适配。
- Skill：`impeccable`，用于 UI 设计评估。`impeccable` 已找到，路径为 `/Users/xiaodi/.agents/skills/impeccable/SKILL.md`。其 `context.mjs` 返回 `NO_PRODUCT_MD`，说明项目未找到 `PRODUCT.md`，因此本文把“缺少产品/设计基准”列为风险。
- 项目文件：
  - `/Users/xiaodi/Desktop/xingrun.web/docs/wrong-questions/wrong-question-review-workflow.md`
  - `/Users/xiaodi/Desktop/xingrun.web/docs/wrong-questions/daily-wecom-wrong-question-automation-workflow.md`
  - `/Users/xiaodi/Desktop/xingrun.web/ai_processor.py`
  - `/Users/xiaodi/Desktop/xingrun.web/pdf_engine.py`
  - `/Users/xiaodi/Desktop/xingrun.web/lesson_manager.py`
  - `/Users/xiaodi/Desktop/xingrun.web/app.py`
  - `/Users/xiaodi/Desktop/xingrun.web/frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs`
  - `/Users/xiaodi/Desktop/xingrun.web/frontend/src/render-wrong-question-practice-sheet-pdf.test.ts`
  - `/Users/xiaodi/Desktop/xingrun.web/tests/test_ai_processor_prompt.py`
  - `/Users/xiaodi/Desktop/xingrun.web/tests/test_wrong_question_practice_store.py`
  - `/Users/xiaodi/Desktop/xingrun.web/tests/test_wrong_question_practice_packs.py`
- 样例 PDF：
  - `/Users/xiaodi/Desktop/xingrun.web/output/pdf/2025级·七年级·4班-吴靖萱-错题练习-20260603/2025级·七年级·4班-吴靖萱-错题练习-20260603.pdf`
  - `/Users/xiaodi/Desktop/xingrun.web/output/pdf/每日错题发送测试-2025级七年级4班-20260602-230903/2025级·七年级·4班/2025级·七年级·4班-吴靖萱-reason具体错因专项错题练习-20260602-230903.pdf`

# 0. 结论摘要

- 当前实现与工作流文档不一致：文档要求至少覆盖 `原题 / 原图`、`方法提醒`、`挖空复盘`、`订正区` 四个必要功能区，但最新吴靖萱 PDF 文本统计里这四个标题全是 `0`，只出现 `题目内容` 和 `重做这题`。
- 当前 UI 更像“把内容放进卡片和横线”，还不是稳定的错题本版式；最低四个功能区没有被明确承载，错因定位、学习目标、老师反馈和需确认提示也未形成完整信息结构。
- 文案规则已经在 prompt 里收紧，但样例 PDF 仍暴露两类问题：旧自动化样张有模板腔，新样张有兜底句太机械、空格上下文不完整的问题。
- 当前链路有结构化中间数据，但 schema 不完整：没有保存 `prompt_version / template_version / model_version / rule_version / teacher_review_status / needs_teacher_confirmation`。
- 图像保真存在高风险：几何题优先尝试结构化重绘或抓原图，但最新吴靖萱 PDF 文本只显示“几何原题图片”，缺少“需老师确认 / 图片不可载入”的人审提示。
- 题型规则主要是通用规则，只有几何、函数图、数轴、选择题拆行有明确依据；未找到立体几何、证明题、概率统计、微积分、经济 / 商务题等专项挖空策略。
- Human-in-the-loop 目前更多是“老师能看结果、失败能记录”，未找到结构化反馈闭环：反馈归类、本次修正、长期规则候选、人工确认、回归测试、版本入库。
- 不看当前成熟度、只看未来方向，标注 + eval + 分类器 / fine-tuning 是提高题型分类、错因分类、挖空策略选择准确率的最合适长期路径；但题干保真、图像保留、排版稳定和超纲拦截不能只靠训练解决。

# 1. 当前工作流地图

```text
输入
→ 微信小程序错题上传 / 本地错题库记录
  依据：wrong_question_submissions、wechat_mp 记录，lesson_manager.py 有错题库与练习单表

解析
→ ai_processor.recognize_wrong_question_image()
  依据：/Users/xiaodi/Desktop/xingrun.web/ai_processor.py:273
  有 OCR/视觉识别、LaTeX 检查、质量审稿、最多 3 次重试
  几何题在当前逻辑里会提前返回，未走后续识别质量审稿

结构化快照
→ wrong_question_practice_sheets / wrong_question_practice_sheet_items
  依据：/Users/xiaodi/Desktop/xingrun.web/lesson_manager.py:2446
  保存题干、图片 URL、错因、topic_category、生成 prompts、pdf_path
  未找到 prompt/template/model/rule 版本字段

内容生成
→ ai_processor.generate_wrong_question_practice_sheet_material()
  依据：/Users/xiaodi/Desktop/xingrun.web/ai_processor.py:1069
  输出 reason_blank_prompt、improvement_summary_prompt、answer、key_steps、pitfall_reminder

排版
→ pdf_engine.generate_wrong_question_practice_sheet_pdf()
→ frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs
  依据：/Users/xiaodi/Desktop/xingrun.web/pdf_engine.py:1268
  依据：/Users/xiaodi/Desktop/xingrun.web/frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs:275

导出
→ 浏览器 Playwright 输出 A4 PDF
  依据：/Users/xiaodi/Desktop/xingrun.web/frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs:655

人审
→ 未找到错题卡级结构化老师反馈入口；只找到失败状态、generation_error、历史任务状态

规则沉淀
→ 未找到规则库候选、老师确认入库、回归测试触发链路
```

# 2. 高风险问题

## P0

### 问题：PDF 模板没有兑现错题本最低功能区，也没有形成更完整的信息结构

- 证据：
  - `/Users/xiaodi/Desktop/xingrun.web/docs/wrong-questions/wrong-question-review-workflow.md:67` 要求每题包含 `原题 / 原图`、`方法提醒`、`挖空复盘`、`订正区`。
  - `/Users/xiaodi/Desktop/xingrun.web/frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs:184` 当前正式模板只渲染 `题目内容`、写作卡、`重做这题`。
  - 最新吴靖萱 PDF 文本统计：`原题 / 原图=0`、`方法提醒=0`、`挖空复盘=0`、`订正区=0`、`题目内容=9`、`重做这题=9`。
- 影响：学生和老师无法快速识别哪一块是原题、哪一块是方法提醒、哪一块要填写；proof 也会与工作流要求冲突。
- 修改建议：不要把四段式当成唯一模板，而是把它作为最低必备功能区。推荐结构为：页眉元信息、原题/原图、错因定位与本次复盘目标、方法提醒、挖空复盘、订正区、老师反馈区、需老师确认提示。PDF schema/template 应把两个 prompt 拆成 `method_hint_lines`、`blank_review_blocks`、`mistake_focus`、`teacher_feedback`、`confirmation_reasons[]` 等字段，由模板决定布局。
- 是否需要人工确认：需要。需确认各区块在学生版和老师版中哪些显式显示、哪些只作为老师端元信息。

### 问题：老师反馈区和“需老师确认”机制未落地

- 证据：
  - 用户目标要求错题页包含老师反馈区和必要时“需老师确认”。
  - `/Users/xiaodi/Desktop/xingrun.web/lesson_manager.py:2464` 的练习单 item 字段只有 `ai_hint / reason_blank_prompt / improvement_summary_prompt` 等，没有老师反馈和确认字段。
  - 最新吴靖萱 PDF 文本统计：`老师反馈=0`、`需老师确认=0`。
- 影响：题目识别不确定、图片无法载入、错因太模糊时，系统没有在 PDF 上把风险显性暴露给老师和学生。
- 修改建议：新增结构化字段或生成中间层：`needs_teacher_confirmation`、`confirmation_reasons[]`、`teacher_feedback_text`；渲染为简短灰框，不进入学生挖空主体。
- 是否需要人工确认：需要。需确认老师反馈区是给老师手写，还是给 AI/系统预留风险提示。

### 问题：几何 / 图形题可能绕过质量审稿

- 证据：
  - `/Users/xiaodi/Desktop/xingrun.web/ai_processor.py:675` 中 `recognize_wrong_question_image()` 在 `normalized["is_geometry"]` 为真时直接 `return normalized`。
  - `/Users/xiaodi/Desktop/xingrun.web/ai_processor.py:678` 起的 LaTeX 和质量审稿逻辑只覆盖非几何题。
- 影响：最依赖图像准确性的题，反而更少经过“题干完整、问法不漏、图中关系可解”的二次审稿。
- 修改建议：几何题也进入质量审稿，只是审稿标准改为“原图保留 + 题干摘要足够 + 不强制重绘通过”。
- 是否需要人工确认：需要，尤其是图像糊、截图不完整、题干缺失时。

## P1

### 问题：当前 UI 是卡片包装，不是完整错题本信息架构

- 证据：
  - `/Users/xiaodi/Desktop/xingrun.web/frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs:392` 使用 `.question-latex-card`、`.writing-card`、`.redo-work-area`。
  - `/Users/xiaodi/Desktop/xingrun.web/frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs:335` 中 `.record-page` 固定 `min-height: 265mm` 且使用 flex。
- 影响：短题看起来清爽，但长题、多图、表格题会挤压写作区和订正区；区块语义也弱。
- 修改建议：A4 模板改为“题目区自适应、复盘区固定最小高度、订正区可独立换页”；每题允许 1 到 2 页，不强行一页塞完。
- 是否需要人工确认：不需要，属于版式质量修复。

### 问题：文案清理只做字符串替换，不能阻止新模板腔

- 证据：
  - `/Users/xiaodi/Desktop/xingrun.web/ai_processor.py:777` 的 `_clean_wrong_question_practice_prompt_text()` 只去 bullet、替换 `本题重点修正`、`订正时先补全`、`这一步` 等。
  - 旧自动化样张仍出现 `本题重点修正`、`订正时先补全`、`这一步`。
  - 最新样张出现 `下次订正前先写清 ______，再检查步骤是否和“未分类”对应`。
- 影响：AI 味会反复以新形式出现，不能靠几个 replace 长期控制。
- 修改建议：建立禁用表达词库 + 文案质量检查器；PDF 生成前扫描命中后降级为“需老师确认”或重新生成。
- 是否需要人工确认：需要。需确认哪些词必须硬禁，哪些只是扣分。

### 问题：自动化工作流是文档，未找到稳定实现脚本

- 证据：
  - `/Users/xiaodi/Desktop/xingrun.web/docs/wrong-questions/daily-wecom-wrong-question-automation-workflow.md:26` 定义每日 14:00、老师 zip、企业微信发送。
  - 项目搜索只找到文档和旧 practice pack job；未找到对应 daily-wecom 生成 / 发送脚本。
- 影响：自动化依赖 Codex 临场执行，难以复现、回归、审计。
- 修改建议：保留工作流文档，但新增只读 DB 到结构化 batch plan、PDF、zip、WeCom 的脚本入口和 dry-run 模式。
- 是否需要人工确认：需要。需确认是否允许把 Computer Use 发送也纳入脚本外壳。

## P2

### 问题：没有 PRODUCT.md / DESIGN.md 作为设计基准

- 证据：
  - `impeccable` context 脚本返回 `NO_PRODUCT_MD`。
  - 项目根目录未找到 `PRODUCT.md / DESIGN.md`。
- 影响：UI 改进容易靠临时审美，不利于长期保持错题本风格。
- 修改建议：补一页“错题本 PDF 设计准则”：A4、字体、分区、色彩、留白、iPad 批注、长题策略。
- 是否需要人工确认：需要。需确认错题本审美方向。

# 3. UI 设计评审

按 `impeccable` product register：产品 UI 应克制、稳定、服务任务；卡片只在确实是最佳 affordance 时使用，避免“卡片是懒答案”。

- 视觉层级：当前封面清楚，但题页层级不足。`第 N 题`、`题目内容`、写作卡、`重做这题` 是弱语义；建议题页至少承载 `原题 / 原图`、`方法提醒`、`挖空复盘`、`订正区`，但不必拘泥为四个等权卡片。更完整的层级应是：原题区最高优先级，错因定位和本次目标做小型标签，方法提醒短而靠近题目，挖空复盘占页面核心，订正区提供真实书写空间，老师反馈和需确认提示作为页尾或边栏补充。
- 信息密度：短题可接受；长题风险高。`.writing-card min-height:82mm` 和 `.redo-work-area min-height:88mm` 会固定吃掉大半页，长题或大图会挤压分页。
- 留白：留白充足，但第 16 页只有横线，像被动续页；订正区应有“第几题续写”的上下文。
- 字体：系统中文字体稳定；字号 16px 适合题干，但方法提醒和挖空没有独立字号节奏。
- 颜色：蓝色题干卡 + 灰色写作卡克制；但题干卡 `border-radius:18px` 偏圆，按 `impeccable` 规则卡片应控制在 12 到 16px 内，PDF 错题本建议更像纸面分区，不要像网页卡片。
- 卡片结构：当前是卡片套卡片，`question-latex-card` 内还有 `question-latex-preview-frame`，有“网页组件打印出来”的感觉。建议题目区只保留一层浅边框。
- 打印适配：A4 margin 有设置，依据 `/Users/xiaodi/Desktop/xingrun.web/frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs:300`；但没有页眉页脚和题目续页标记。
- iPad 批注适配：横线区可写，但挖空区下划线是固定 inline，长句换行时空格可能断裂。建议关键空使用可换行的 blank span，并给每题至少一个完整书写框。
- 长题 / 多图 / 多问稳定性：未找到多图题测试；函数图、几何图在错题库 PDF 有测试，但练习单模板只检查 `image_data_url`，没有多图布局策略。
- 是否像真实错题本：当前不够。真实错题本应有“原题很清楚、复盘是核心、订正留足空间、老师可批注”。当前更偏“PDF 任务页”。

# 4. 文案风格评审

原表达：`本题重点修正：忘记了公式导致错误。`

问题：模板腔，且“忘记了公式”没有说明是哪一个公式。

建议改法：`这题先把正方形边长和长方形面积对应起来，别直接套比例。`

原表达：`订正时先补全“面积拼图数量对应”这一步，再重新写完整过程并检查答案范围。`

问题：像系统生成的流程话，学生不知道具体补什么。

建议改法：`先写出 20×20 和目标 300cm²，再判断 3:2 的长宽能不能放下。`

原表达：`这题不是简单写“不会”，真正要补的是：少写了一种方式。`

问题：说教感强，且“少写了一种方式”不够具体。

建议改法：`平方根有正负两个值，算术平方根只取非负值。这里先把这两个条件分开写。`

原表达：`我先核对本题的 ______，再对照这次错因：手动补录：原上传任务因识别连接失败，题干由老师根据原图补录。`

问题：把内部来源说明塞进学生练习，像系统日志。

建议改法：`先核对正方形边长和目标面积：正方形边长是 ______，长方形面积是 ______。`

原表达：`下次订正前先写清 ______，再检查步骤是否和“未分类”对应。`

问题：`未分类` 是后台分类，不应出现在学生纸面。

建议改法：`下次先在图上标出已知相等关系，再决定是否需要作辅助线。`

需要建立词库：需要。

禁用词库至少包含：`本题重点修正`、`订正时先补全`、`这一步`、`完整过程并检查答案范围`、`这题不是简单写`、`相关知识点`、`具体错因复盘`、`未分类`、`分析如下`。

推荐表达词库按动作写：`先圈...`、`先标...`、`先分...两种情况`、`先把...列出来`、`检查...是否同乘/同单位/同范围`。

# 5. 内容结构评审

- 原题区：必要，但当前模板写成 `题目内容`，不符合工作流命名。几何题能保留图片入口，依据 `/Users/xiaodi/Desktop/xingrun.web/frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs:64`，但图片失败时只有“图片暂时无法载入”，未触发老师确认。
- 错因定位 / 本次目标：建议新增。它不替代方法提醒，而是用 1 行说明这张卡到底练什么，例如 `错因：漏看正负两种情况`、`本次目标：先分情况再代入验证`。这样能避免学生把错题卡当普通解析读。
- 方法提醒：必要，但当前正式模板没有独立 `方法提醒` 区。prompt 只产两个写作 prompt，没有独立方法提醒字段。
- 挖空复盘：必要，是页面核心；当前由两个 prompt 合并成一个 `writing-card`，标题被剥掉，导致“挖空复盘”语义弱。
- 订正区：必要；当前 `重做这题` 有 12 条横线，能写，但没有灰框和题号续页上下文。
- 老师反馈区：必要；未找到稳定字段和渲染区。
- 需老师确认：必要；未找到字段和渲染逻辑。建议触发条件包括：图片不可载入、识别失败补录、题干为空、`topic_category=未分类`、AI 置信不足、原图/文字不一致。

判断：当前卡片能让学生重做一部分题，但不像完整错题本。它更偏“读提示 + 重做”，没有稳定地引导学生经历 `看原题 -> 定错因 -> 明确本次目标 -> 方法入口 -> 关键条件 -> 推理/计算 -> 结论/易错点 -> 独立订正 -> 老师反馈`。

推荐结构不是机械四段式，而是“最低四区 + 教学诊断层”：

- 页眉元信息：学生、班级、日期、题型、知识点、错因类型，弱化展示，便于老师检索。
- 原题 / 原图：最高优先级，必须保真；图片或题干不确定时直接标记需老师确认。
- 错因定位 / 本次目标：1 行即可，具体到知识点或错误原因。
- 方法提醒：2 到 3 条短句，只提示入手，不泄露完整答案。
- 挖空复盘：页面核心，按入手判断、关键条件、方法选择、推理计算、结论检查组织。
- 订正区：真实留白，长题可独立续页。
- 老师反馈区：给老师批注或后续反馈闭环使用。
- 需老师确认：只在识别、图片、分类、超纲方法等不确定时出现，不干扰普通题。

# 6. 题型规则评审

已找到覆盖：

- 几何/几何体识别：`is_geometry`、`diagram_type=geometry`，依据 `/Users/xiaodi/Desktop/xingrun.web/ai_processor.py:273`。
- 数轴、函数图像、线段示意图：`diagram_type` 支持 `number_line / function_plot`，依据 `/Users/xiaodi/Desktop/xingrun.web/ai_processor.py:285`。
- 选择题排版：紧凑选项拆行，依据 `/Users/xiaodi/Desktop/xingrun.web/frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs:107`，测试依据 `/Users/xiaodi/Desktop/xingrun.web/frontend/src/render-wrong-question-practice-sheet-pdf.test.ts:70`。
- 通用错因：知识点、细节、方法、审题，依据 `/Users/xiaodi/Desktop/xingrun.web/ai_processor.py:331`。

缺失或未找到依据：

- 立体几何专项规则：未找到“禁止默认坐标法/向量法”的规则。
- 平面几何专项挖空：只有“补标条件、角关系、辅助线”通用要求，没有按证明、辅助线、全等、相似、圆等分类。
- 函数专项规则：只有 prompt 示例，没有分段函数、定义域、单调性、图像交点等系统策略。
- 微积分、数列、概率统计、证明题、表格题、经济 / 商务题：未找到专项触发条件、挖空策略、禁用方法、超纲拦截。
- 计算失误型：有“符号、单位、计算、验算”通用要求，但未找到“定位错误发生点，不重讲整题”的强规则。
- 选择题：只有选项拆行，未找到干扰项分析规则。

必须增加特殊处理：立体几何、证明题、选择题、图形题、计算失误型、审题错误型。这些会直接影响学生是否能重新做，而不是读解析。

# 7. 稳定性与工程链路评审

- schema：有数据库表，但不是内容 schema。当前 `items` 没有题型、图像类型、不可确认项、老师审核状态、版本字段。
- 中间数据：有快照层，依据 `/Users/xiaodi/Desktop/xingrun.web/lesson_manager.py:7905`；但 AI 输出直接进入渲染字段，缺少质量检查层。
- 错误回退：AI 生成失败会标记失败，依据 `/Users/xiaodi/Desktop/xingrun.web/app.py:835`；PDF 会重试，依据 `/Users/xiaodi/Desktop/xingrun.web/app.py:889`。但 daily workflow 文档要求“无 key 时确定性内容”，代码里的正式练习单 worker 未找到对应兜底。
- OCR / 图片保真：原图只在几何题抓取，非几何截图不保留；与“原题 + 原图”目标有冲突。
- PDF / HTML 渲染：浏览器链路稳定性较好，有 Chromium 探测，依据 `/Users/xiaodi/Desktop/xingrun.web/frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs:608`。但练习单没有 ReportLab fallback，依据 `/Users/xiaodi/Desktop/xingrun.web/pdf_engine.py:1268`。
- 版本记录：未找到 prompt/template/model/rule 版本字段。
- 回归测试：有 prompt、选项拆行、LaTeX、图片数据 URL、worker retry 测试；未找到 PDF 视觉回归、长题溢出、多图、多问、老师确认测试。
- 批量生成稳定性：旧 practice pack job 有部分成功和 zip 缺失处理，依据 `/Users/xiaodi/Desktop/xingrun.web/app.py:1021`；daily-wecom 老师维度自动化未找到实现。

推荐链路：

```text
输入解析层
  原图 / PDF 页 / 学生错因 / 老师备注
  输出：raw_question_asset、ocr_text、student_marks、confidence

结构化数据层
  输出：question_text_exact、image_refs[]、question_type、topic、error_type、uncertain_fields[]

教学诊断层
  输出：method_entry、review_focus、pitfall_point、forbidden_methods、stage_limit

内容生成层
  输出：method_hint_lines[]、blank_review_blocks[]、correction_area_spec、teacher_feedback_hint

UI 渲染层
  固定 A4 模板，只消费 schema，不让 AI 决定布局

质量检查层
  检查题干未改、图片保留、禁用词、空格数量、四区顺序、页面溢出、坏 LaTeX

人审反馈层
  老师修改本次卡片，系统生成规则候选，不自动改总规则
```

# 8. Human-in-the-loop 方案评审

当前不够。已有失败状态和老师端历史记录，但未找到错题卡级反馈闭环。

建议闭环：

```text
老师反馈
→ 错误类型归类
→ 本次错题卡修正
→ 规则库候选建议
→ 老师确认
→ 加入规则库
→ 回归测试
→ 记录版本
```

反馈字段：

- `record_id`
- `sheet_id`
- `item_id`
- `feedback_source`: teacher / student / parent / codex_review
- `feedback_type`: 题干错误 / 图像缺失 / 文案AI味 / 挖空太空 / 方法泄答案 / 超纲方法 / 排版溢出 / 题型规则缺失
- `teacher_comment`
- `current_fix_text`
- `long_term_rule_candidate`
- `requires_rule_update`
- `approved_by_teacher`
- `prompt_version`
- `template_version`
- `rule_version`
- `model_version`
- `regression_case_id`

关键规则：AI 只能生成“规则库候选”，不能自动写入总控规则。老师确认后加入，加入前跑固定样例集，防止新规则破坏旧题型。

# 9. 数据标注与训练建议

当前不建议立即训练模型。

如果不看当前系统成熟度，只看未来提升空间，数据标注与训练是提高“不同题型准确率”和“分类问题”的最合适长期方案之一，尤其适合解决三类问题：

- 题型分类：平面几何、立体几何、函数、数列、概率统计、证明题、选择题、图像题、表格题等边界清楚但容易混淆的分类。
- 错因分类：计算失误、审题遗漏、概念混淆、方法选择错误、图形关系漏看、条件转化失败等需要从学生痕迹和老师反馈中归纳的分类。
- 策略选择：同一题型下选择哪种挖空方式、是否分析干扰项、是否需要老师确认、是否禁止坐标法/向量法等教学动作。

但它不是单独的最终答案。训练适合提升“判断”和“选择”，不适合单独保证“题干不被改写、图片不丢、数学结论正确、页面不溢出”。这些仍然要靠结构化 schema、原图引用、质量检查、题型规则库和老师确认机制兜底。未来最稳的方向不是“训练替代规则”，而是“标注数据让分类更准，规则和模板保证输出可控，eval 负责持续验收”。

原因：

- 主要问题不是模型能力单点不足，而是 schema、版本、题型规则、质量检查和人审闭环缺失。
- 没有稳定 eval 集时，fine-tuning 可能把模板腔固化。
- UI 溢出、图片保真、四区结构缺失不是训练能解决的，必须靠模板和质量检查。

建议先做标注和 eval。数据表字段：

- 学科
- 年级 / 课程体系
- 题型
- 知识点
- 是否有图
- 图像类型
- 学生错误类型
- 最佳解法
- 禁止解法
- 是否超纲
- 方法提醒质量
- 挖空质量
- 文案 AI 味评分
- UI 排版评分
- 老师是否通过
- 老师修改原因
- 规则库建议
- 是否需老师确认
- prompt/template/model/rule 版本

标注用途：

- eval：每次 prompt/template/rule 改动跑 30 到 100 个代表题，检查四区结构、题干保真、AI 味、题型规则。
- few-shot：把老师通过的卡片作为示例，按题型分组进入 prompt。
- 轻量分类器：先训练或校准题型、错因、是否需老师确认、是否疑似超纲这几类标签，用于给生成链路选规则，不直接生成学生可见内容。
- 训练触发条件：当已有 500 到 1000 张高质量标注卡片，且 eval 显示同类文案问题反复出现、规则和 few-shot 仍无法稳定解决时，再考虑 fine-tuning 或小模型分类器。

# 10. 优先级行动清单

1. **P0：把 PDF 渲染模板改成“最低四区 + 完整错题本结构”。**
   - 为什么：当前最新 PDF 没有稳定承载 `原题 / 原图`、`方法提醒`、`挖空复盘`、`订正区`，也缺少错因定位、老师反馈和需确认提示。
   - 验收标准：PDF 每题至少包含 `原题 / 原图`、`方法提醒`、`挖空复盘`、`订正区`；同时支持 `错因定位 / 本次目标`、`老师反馈区`、`需老师确认`，且长题可以自然分页。

2. **P0：新增 `needs_teacher_confirmation` 和老师反馈区。**
   - 为什么：图片失败、题干缺失、未分类不能静默进入学生练习。
   - 验收标准：构造图片不可载入/题干为空样例时，PDF 出现“需老师确认”。

3. **P0：几何题也走质量审稿。**
   - 为什么：几何题最依赖图像准确性，当前直接返回。
   - 验收标准：几何题识别失败/题干缺问法时能进入重试或确认状态。

4. **P1：建立文案禁用词库和生成后扫描。**
   - 为什么：replace 只能修旧词，不能防新模板腔。
   - 验收标准：样例 PDF 中 `本题重点修正`、`订正时先补全`、`未分类`、`这题不是简单写` 计数为 0。

5. **P1：把内容 schema 从两个 prompt 拆成完整教学结构。**
   - 为什么：现在方法提醒和挖空复盘混在写作卡里。
   - 验收标准：中间 JSON 至少包含 `question_asset_refs[]`、`mistake_focus`、`review_goal`、`method_hint_lines[]`、`blank_review_blocks[]`、`correction_area_spec`、`teacher_feedback`、`confirmation_reasons[]`。

6. **P1：补题型规则库 v1。**
   - 为什么：当前规则太通用。
   - 验收标准：至少覆盖选择题、平面几何、立体几何、函数、证明题、计算失误、审题错误，每类有触发条件和挖空策略。

7. **P1：新增 PDF eval 样例集。**
   - 为什么：没有样例集就无法稳定迭代。
   - 验收标准：包含长题、多图、几何、函数图、选择题、证明题、表格题、识别失败题；每次生成输出结构和坏 token 统计。

8. **P2：补 prompt/template/model/rule 版本记录。**
   - 为什么：现在难以复现某次生成。
   - 验收标准：每份 sheet 和每个 item 可查到生成版本。

9. **P2：实现 daily-wecom 自动化脚本 dry-run。**
   - 为什么：当前主要是文档和临场执行，维护成本高。
   - 验收标准：dry-run 输出老师 zip 计划、学生题量、方向、PDF 路径，不发送企业微信。

10. **P2：补 PRODUCT/DESIGN 或错题本 PDF 设计准则。**
    - 为什么：`impeccable` 找不到设计基准。
    - 验收标准：项目内有一份可引用的 A4 错题本 UI 标准，包含字号、边距、分区、颜色、长题分页和 iPad 批注规则。

## 下一步建议

本文应作为错题本系统后续迭代的评估基线。后续如要实施，建议另开任务分支，并按优先级先处理 P0：最低四个功能区与更完整错题本结构、老师确认机制、几何题质量审稿。实施时不要直接改总控 prompt，应先补 schema、模板、质量检查和回归样例，再决定是否需要调整 prompt 或题型规则库。
