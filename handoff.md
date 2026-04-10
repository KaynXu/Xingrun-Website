## Handoff

最后更新：2026-04-10

这份文件只记录当前权威状态、下一步、风险和残留。
详细过程、proof、提交顺序、历史流水请直接看 `git log`。

### 当前状态
- 当前主线是 `智能错题` 收口。
- staff / owner / admin 的智能错题筛选已进一步收口：
  - staff 视角不再保留两个独立“班级”筛选语义，错题本区直接跟当前班级选择联动
  - 选择老师后，班级下拉只保留该老师负责班级
  - 选择班级后，学生筛选会从自由输入切到本班学生下拉
  - 科目筛选已改成下拉
  - 错误类型筛选已改成固定下拉
  - 题目详情里的 `最终错误类型` 也已改成固定下拉，同时兼容旧记录里已有的 legacy 值
- 预发布前卡住的 3 条后端失败已在本地修通：
  - `review-plans` 音频上传 credit 用例已改成异步 `202 + pending` 语义
  - `monthly` PDF 失败后不再提前扣费，重试后可成功扣一次并完成任务
  - `monthly` 后台 worker 不再依赖 request context 生成 request identity
- 合并 `master` 前暴露出的 3 条前端源码断言测试也已收口，当前是测试预期对齐现有实现，没有新增产品逻辑修改。
- 登录后工作区里的对话式文案已收口，`WorkspaceDashboard.tsx`、`App.tsx`、`SmartWrongQuestionsPage.tsx` 不再保留 `欢迎回来 / 系统会帮你 / 先这样再那样` 这类口吻。
- 登录后工作区已恢复少量明确的 `AI` 能力标识，用于保留产品定位；当前原则是“保留 AI 能力名词，不保留 AI 助手式对话口吻”。
- 旧 `导出汇总`、`onlyPendingReview`、`只看待教师跟进` 链路已经删除，前后端不再保留隐藏入口。
- 当前智能错题仍是双语义模型：
  - `wechat_mp` 走 `wechat_mastery`
  - `downstream` 走 `downstream_review`
- 当前本地微信错题主状态语义：
  - 未掌握 = `archive_status='active'`
  - 已掌握 = `archive_status='archived'`
- `teacher_comment` 和 `status='reviewed'` 在本地微信错题链路里只剩兼容旧列含义，不再作为主流程判断依据。
- staff / owner / admin / super_owner 已统一到按班级或学生打开错题本的 notebook 流程。
- `member` 端已改成学生卡片 -> 弹窗错题本，不再走旧的页面下半区详情布局。
- 最近一次相关产品代码提交并已部署生产的是 `72e0aa5 fix: remove stale smart wrong question filters`。

### 下一步
- 最值得继续做的是打开真实页面做一轮人工 smoke check，确认 staff 视角下“老师 -> 班级 -> 学生”联动和 notebook 区交互符合预期，然后再决定是否跟随下一次 release 一起部署。
- 这 3 条后端失败修完后，下一步就是按 release 流程重新做一次 `develop -> push -> merge master -> 部署`，不需要再先卡在这 3 条上。
- 最适合继续做的是确认这轮命名收口是否要继续扩到更多历史文档文件名，当前先只改了内容和活代码命名，没有批量重命名 `docs/superpowers/*` 的历史文件路径。
- 优先处理：
  - 如果还要继续收口，可以单独决定是否把 `teacher_comment` / `status='reviewed'` 这类兼容旧列也进一步包到更显式的 legacy helper 里
  - 如果还要继续清历史材料，可以再扫 `docs/` 非 `superpowers` 目录和外部备份仓库里是否还保留旧口径
- 这一步仍适合直接在 `develop` 做，小改动即可，不需要并行开第二条错题链路。

### 风险
- 当前错误类型下拉为了兼容现有错题记录，同时保留了固定错因和已出现过的 legacy downstream 分类；在真正统一错题后端分类口径前，这里仍是“固定列表 + 兼容旧值”的过渡态。
- 当前最大风险不是功能坏掉，而是“语义看起来像统一了，其实没有”。
- `monthly` 现在已经改成“PDF 成功后再扣费”，但单节 `review plan` worker 仍是 AI 成功后立即扣费；如果后面也要求单节 PDF 失败不扣费，这一块语义还没有跟上。
- `wechat_mp` 和 `downstream` 仍是两套字段语义；在真正统一后端契约前，不要只在共享前端类型上继续顺手收口字段。
- `wrong_question_submissions` 表里的兼容列 `teacher_comment` / `status` 还在，所以后续维护时仍有误写回旧字段的风险。
- `smart_wrong_questions.py` 下游代理链还在，运行时仍是“本地微信错题 + downstream 服务”双来源模型。
- 生产上 `pm2 restart xingrun` 后第一下即时健康检查偶尔会短暂失败，但随后会恢复到根路由 `302`；这是已知现象，当前未继续深挖。

### 已删除但仍有残留
- 这轮已把活代码里的旧智能错题口径收口成 `错题跟进 / 跟进记录 / 保存跟进记录 / 题目整理 / 教学素材 / 错因整理`。
- 这轮已把课堂反馈存储命名统一成 `lesson_class_feedbacks`、`save_lesson_class_feedback()`、`get_lesson_class_feedback()`、`build_lesson_class_feedback_editor_state()`，并补了旧表自动迁移测试。
- `app.py` 里对旧 helper 的未用导入已经删除。
- `docs/superpowers/*` 与本文件历史条目里的旧课堂反馈 / 已删除 helper 上下文已经同步改成 legacy 口径，避免下一轮把历史流水误判成当前实现。

### 最近相关提交
- `72e0aa5` `fix: remove stale smart wrong question filters`
- `5627f20` `fix: remove stale wrong question export flow`
- `14ac9b4` `fix: allow notebook search before class selection`
- `81b10d4` `fix: refine smart wrong question notebook filters`
- `efcda6b` `docs: record handoff review priorities`
- `6f0b39b` `docs: reaffirm smart wrong question semantic split risk`

### 当前工作区
- 当前分支：`develop`
- 当前工作区应保持短生命周期、干净状态；不要再把长流水追加回这个文件。
- 后续更新这份文件时，只写：
  - 当前状态有没有变化
  - 下一步最值得做什么
  - 风险有没有新增或解除
  - 哪些残留已经清掉
