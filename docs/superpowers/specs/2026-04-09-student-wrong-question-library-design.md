# Student Wrong Question Library Design

## Goal

把当前“家长上传错题记录 + 网页端老师处理”的松散记录流，升级成“每个学生一份持续累积的错题库 PDF”。

这次改动要求双端访问同一份学生级错题库：

- 网页端老师在 `智能错题` 工作台查看、编辑、重建
- 家长小程序端查看同一个学生对应的错题库 PDF

并引入新的题目入库规则：

- 非几何题必须先通过 AI 提取出可用题目文本，才允许入库
- 几何题不要求提取题目文本，直接以题图形式入库
- 如果非几何题 AI 提取失败，则阻止入库，要求重新识别
- 老师在网页端拥有修改 AI 识别出的题目文本的权限

## Background

当前系统已经有两条相关链路：

- 微信小程序家长上传链路
  - 家长基于 `openid + binding_id` 上传错题图片
  - 本地表 `wrong_question_submissions` 保存图片、家长备注、孩子原因、老师备注等字段
- 网站 `智能错题` 工作台
  - 网站通过 `/api/wrong-questions` 合并展示下游错题服务记录与本地微信上传记录
  - 本地微信上传记录目前只是“逐条记录”，还不是学生维度的统一错题库

当前最关键的问题不是展示页不够，而是数据模型还停留在“单条上传记录”。这样会带来三个问题：

- 网页端与小程序端虽然都能看记录，但看不到同一个“学生错题库成品”
- PDF 仍是按列表导出或下游能力导出，不是学生长期累积资产
- 非几何题没有稳定的题目文本，后续老师复盘、学生检索、PDF 呈现都不够好

## Product Decision

### 1. 学生错题库是固定资产，不是临时导出

每个学生长期对应一份固定路径的错题库 PDF。

产品语义是：

- 学生一旦有第一条成功入库的错题，就生成该学生错题库 PDF
- 后续每新增一条合法错题，就往这本错题库“新增一页”

实现语义不要求做 PDF 二进制层面的原地增量拼接。为了稳定性，允许后台每次基于该学生的全量有效错题记录，重建同一路径 PDF。对外表现仍然是“同一本 PDF 持续累积变厚”。

### 2. 非几何题必须识别成功后才能入库

上传图片后，后端先做 AI 识别。只有满足以下条件才允许写入正式错题库记录：

- 识别结论为“几何题”
- 或识别结论为“非几何题且拿到了可信题目文本”

如果模型判断是非几何题，但未拿到可信题目文本，则本次上传直接失败，不创建正式错题记录，不更新学生错题库 PDF，前端提示家长重新识别。

### 3. 几何题只保留图片页

几何题和几何体相关题目不要求强制提取题目文本。

原因：

- 这类题往往高度依赖图形关系
- 题干 OCR 或结构化提取容易失真
- 最终老师和家长更关注图像原题本身

因此几何题的入库页以图片为主，必要时只附带家长备注、时间、老师备注等元信息。

### 4. 老师可以在网页端修改题目文本

AI 提取出来的 `question_text` 不是不可变真相，而是初稿。

网页端老师必须可以：

- 查看 AI 提取出的题目文本
- 直接编辑题目文本
- 保存老师修订结果
- 保存后立即触发该学生错题库 PDF 重建

老师修订后，学生错题库以老师修订文本为准。

### 5. 双端访问同一份 PDF

网页端和小程序端不各自生成各自版本的 PDF。

统一原则：

- 学生错题库 PDF 的生成与存储完全在网站后端负责
- 小程序端只读取这个学生当前最新 PDF 的访问地址
- 网页端也读取同一路径或同一下载接口

这保证双端看到的是同一份成品，而不是“同源记录、不同导出结果”。

## Scope

本期包含：

- 为微信本地错题记录补齐 AI 识别与学生级错题库字段
- 非几何题入库前识别与失败拦截
- 几何题图片页入库
- 学生级固定 PDF 生成与重建
- 网页端老师编辑题目文本
- 小程序端返回学生错题库 PDF 访问入口

本期不包含：

- 重构旧下游错题服务的数据结构
- 把所有历史外部错题服务记录都自动迁移成学生级 PDF
- 图片上传来源从 URL 改成对象存储流程重构
- 图像去重、相似题聚类、题目标签检索等高级能力
- 家长端直接编辑题目文本

## Architecture

### 1. 数据源边界

学生级错题库只对本地微信上传记录负责。

原因：

- 当前 `/api/wrong-questions` 仍然合并本地下发记录与下游代理记录
- 下游代理记录的字段形态与可控程度不足，不适合直接承担“稳定学生资产”职责
- 本次学生级 PDF 需要稳定触发、稳定重建、稳定编辑，最适合完全落在本地表上

因此本次“学生错题库 PDF”能力只建立在本地 `wrong_question_submissions` 之上。

网页端工作台仍可以继续展示混合列表，但只有本地微信上传记录具备“学生错题库正式入库 + PDF 重建”能力。

### 2. 写入流程

新的家长上传流程变为：

1. 家长小程序上传图片与绑定信息
2. 后端先调用 AI 识别服务
3. AI 返回结构化结论：
   - 是否几何题
   - 题目文本
   - 识别可信度或识别备注
4. 后端做入库判定：
   - 几何题：允许入库
   - 非几何题且题目文本可信：允许入库
   - 非几何题但文本无效：拒绝入库
5. 成功入库后重建该学生错题库 PDF
6. 返回最新记录与学生错题库 PDF 信息

### 3. PDF 更新策略

产品上是“新增一页”，工程上采用“同路径全量重建”。

推荐原因：

- 不依赖 PDF 增量拼接兼容性
- 老师修订题目文本后可以简单重建全书
- 后续加入排序、归档过滤也更清晰

重建触发场景：

- 新错题成功入库
- 老师修改题目文本
- 老师修改老师备注且该备注会出现在 PDF 中
- 老师归档 / 取消归档导致是否出现在学生错题库中的集合发生变化

## Data Model Changes

### 1. 扩展 `wrong_question_submissions`

当前表已经有：

- `image_url`
- `parent_note`
- `teacher_comment`
  - 兼容旧列，当前本地微信老师跟进主流程不再依赖它驱动状态变更
- `status`
  - 兼容旧列，当前本地微信主流程不再以 `pending` / `reviewed` 作为有效状态切换
- 孩子原因类字段

本期新增以下字段：

- `recognition_status TEXT NOT NULL DEFAULT 'pending'`
  - `pending`
  - `recognized`
  - `failed`
- `is_geometry INTEGER NOT NULL DEFAULT 0`
- `question_text TEXT NOT NULL DEFAULT ''`
  - AI 原始识别通过后的当前生效文本
- `question_text_edited INTEGER NOT NULL DEFAULT 0`
  - 老师是否人工改过文本
- `question_text_source TEXT NOT NULL DEFAULT 'ai'`
  - `ai`
  - `teacher`
- `recognition_error TEXT NOT NULL DEFAULT ''`
  - 上传失败原因或最近一次识别失败信息
- `student_library_pdf_path TEXT NOT NULL DEFAULT ''`
  - 该条记录保存后所对应学生当前错题库 PDF 路径快照

说明：

- `question_text` 始终保存“当前生效版本”，不再额外拆原始 AI 文本列
- 如果后续确实需要审计 AI 原文，可再补 `question_text_ai_raw`
- 本期为最小入侵，不先扩展复杂版本历史表

### 2. 学生错题库视图模型

生成 PDF 时，每条记录都投影为统一页模型：

- `record_id`
- `student_id`
- `student_name`
- `class_name`
- `teacher_name`
- `created_at`
- `is_geometry`
- `question_text`
- `image_url`
- `parent_note`
- `teacher_comment`

### 3. 记录状态语义

当前实现里，本地微信记录的老师跟进已经不再用 `status='pending/reviewed'` 驱动；保存 review 时实际生效的是 `is_mastered` 与 `archive_status`。

因此：

- `recognition_status` 单独表示识别结果
- `is_mastered=true` 时，记录写成 `archive_status='archived'`
- `is_mastered=false` 时，记录保持 `archive_status='active'`
- `status` 与 `teacher_comment` 保留为兼容旧列，不再作为本地微信主流程判断依据

只有 `recognition_status='recognized'` 且 `archive_status='active'` 的记录才算正式入库、才进入学生错题库 PDF。

## AI Recognition Contract

### Required Output

上传识别阶段的 AI 结果至少要返回：

- `is_geometry: boolean`
- `question_text: string`
- `confidence: string`
- `notes: string`

### Success Criteria

识别成功判定：

- 若 `is_geometry=true`，直接视为成功
- 若 `is_geometry=false`，则 `question_text` 必须满足：
  - 去空白后非空
  - 不属于占位失败文案，如“无法识别”“看不清”“题目缺失”
  - 长度达到最小可信阈值

### Failure Criteria

以下任一情况判为失败：

- 模型调用超时、报错、返回格式非法
- 非几何题但 `question_text` 为空或无效
- 关键字段缺失或类型不对
- 文本明显只是标签、单字、乱码或无关占位语

### Failure Behavior

识别失败时：

- 不创建正式错题记录
- 不重建学生错题库 PDF
- 接口返回明确错误，提示家长重新识别

为了避免把“失败记录”混入正式库，本期不做“失败也落暂存表”的扩展设计。

## API Design

### 1. 小程序上传接口

现有 `POST /api/wechat/wrong-questions` 改为“识别成功后才真正创建记录”。

请求仍包含：

- `open_id`
- `binding_id`
- `image_url`
- `parent_note`
- 孩子原因相关字段

返回：

- 成功：`201`
  - `record`
  - `student_library_pdf_url`
- 失败：`422` 或 `502`
  - `error`
  - `retryable: true`

建议错误语义：

- 识别失败但可重试：`422`
- AI 服务异常：`502`

### 2. 小程序学生错题库接口

现有 `GET /api/wechat/children/<student_id>/wrong-questions` 保留列表能力，同时增加学生库元信息：

- `student_library_pdf_url`
- `student_library_updated_at`

如果需要更清晰，也可以新增：

- `GET /api/wechat/children/<student_id>/wrong-question-library`

返回：

- `student_id`
- `pdf_url`
- `updated_at`
- `total_items`

### 3. 网页端错题详情接口

`GET /api/wrong-questions/<record_id>` 对本地微信记录返回时补全：

- `recognition_status`
- `is_geometry`
- `question_text`
- `question_text_edited`
- `question_text_source`
- `student_library_pdf_path`

### 4. 网页端老师编辑接口

在现有 `PUT /api/wrong-questions/<record_id>/review` 基础上，对本地微信记录允许老师提交：

- `is_mastered`
- `question_text`

兼容说明：

- `teacher_comment` / `status` 仍可能存在于历史数据或其他来源记录里，但不应再作为本地微信 review contract 的有效控制字段

对于本地微信记录：

- 如果 `question_text` 被修改，则写回 `question_text`
- `question_text_edited=1`
- `question_text_source='teacher'`
- 如果 `is_mastered=true`，则写回 `archive_status='archived'`
- 如果 `is_mastered=false`，则写回 `archive_status='active'`
- 传入 `teacher_comment` / `status` 时不再用它们驱动本地微信记录状态变更
- 保存成功后触发学生 PDF 重建

## PDF Design

### 1. 文件组织

每个学生固定一个 PDF 路径。

建议路径风格：

- `data/pdfs/wrong_question_libraries/student-<student_id>.pdf`

如果后续需要机构隔离，可再细化为：

- `data/pdfs/wrong_question_libraries/org-<organization_id>/student-<student_id>.pdf`

### 2. 内容结构

PDF 首页展示学生级摘要：

- 学生姓名
- 班级
- 最近更新时间
- 错题总数

后续每页一题：

- 页眉：学生、班级、上传时间
- 非几何题：
  - 题目文本
  - 原图缩略图或附图
  - 家长备注
  - 老师备注
- 几何题：
  - 原题图片大图
  - 几何题标识
  - 家长备注
  - 老师备注

### 3. 纳入规则

仅以下记录进入学生错题库 PDF：

- `source='wechat_mp'`
- `recognition_status='recognized'`
- `archive_status='active'`

归档记录默认不进入 PDF。

## Frontend Design

### 1. 网页端老师工作台

本地微信上传记录详情区新增“题目文本”模块。

显示逻辑：

- 几何题：显示“该题按几何题图片入库”，题目文本编辑框隐藏或禁用
- 非几何题：显示可编辑文本框，默认填充当前 `question_text`

老师保存后：

- 调用现有 review 保存接口
- 成功后刷新记录详情
- 提示学生错题库已更新

### 2. 小程序端

家长上传成功后，不再只看到“进入老师待处理队列”，而是可以额外看到：

- 已成功加入学生错题库

学生历史页或学生详情页可直接打开：

- 当前学生错题库 PDF

上传失败时要明确提示：

- 本题未入库
- 请重新识别或重新上传更清晰图片

## Error Handling

### 1. AI 识别失败

- 返回明确错误，不入库
- 不生成无效空页
- 不污染学生错题库 PDF

### 2. PDF 重建失败

如果识别成功、记录已写入，但 PDF 重建失败：

- 记录仍保留
- 错误写日志
- 接口返回成功，但附带“错题已入库，错题库更新稍后重试”的错误提示并不理想

为了保证双端总能访问统一 PDF，本期更稳的策略是：

- 先写入数据库事务外完成 PDF 重建
- 若重建失败，则将本次记录回滚删除并返回失败

也就是：本期把“记录写入 + PDF 重建成功”视为一次完整成功。

这样代价是上传成功门槛更高，但能保持产品语义严格一致：只要接口成功，双端就一定拿得到最新 PDF。

### 3. 老师编辑后 PDF 重建失败

老师修改题目文本时，如果保存成功但 PDF 重建失败，会造成网页详情和 PDF 不一致。

因此老师编辑保存也采用同样原则：

- 先尝试保存新文本并重建 PDF
- 任一步失败则整次返回失败，不保留半成功状态

## Testing Strategy

### Backend

新增或扩展测试覆盖：

- 非几何题识别成功后才创建记录
- 非几何题识别失败时接口返回错误且数据库无新增记录
- 几何题允许以图片形式入库
- 新记录入库后学生 PDF 路径稳定且存在
- 同一学生第二题入库后同一路径 PDF 被更新
- 老师修改 `question_text` 后 PDF 重建成功
- 老师修改 `question_text` 时如果重建失败则整次保存失败

### Frontend

新增或扩展测试覆盖：

- 本地微信记录详情展示题目文本字段
- 几何题隐藏文本编辑输入
- 非几何题允许老师编辑并保存题目文本
- 保存成功后页面显示更新后的文本和学生库提示

## Risks

### 1. 上传时延变长

因为识别与 PDF 重建都放进上传同步路径，家长上传耗时会明显高于当前纯写库。

这是本期接受的产品取舍，因为用户已经明确要求“识别失败阻止入库”和“上传即进入固定错题库 PDF”。

### 2. 图片远程加载稳定性

PDF 重建依赖 `image_url` 可访问。如果外链不稳定，可能导致重建失败。

本期不重构存储链路，但实现时需要：

- 对图片下载失败给出稳定异常
- 在测试中 mock 远程图片读取

### 3. 历史记录兼容

旧本地微信错题记录没有识别字段。

迁移后它们默认不会自动进入学生错题库 PDF，除非后续补做迁移脚本。这样虽然保守，但能避免历史脏数据污染学生库。

## Final Recommendation

按“方案 A”落地：

- 录入即更新学生固定错题库 PDF
- 非几何题先识别成功再入库
- 几何题按图片页入库
- 网页老师可改题目文本并触发 PDF 重建
- 双端统一访问同一个学生级 PDF

这是当前最符合用户要求、同时边界最清晰的一版。它把“学生错题库”定义成正式业务资产，而不是临时导出视图。