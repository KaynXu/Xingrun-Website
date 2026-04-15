## Handoff

最后更新：2026-04-15

这份文件只记录当前权威状态、下一步、风险和残留. 禁止记录流水账.
详细过程、proof、提交顺序、历史流水请直接看 `git log`。

### 当前状态
- 2026-04-15 内嵌小程序快照 `Xingrun-MiniProgram/miniprogram/pages/parent-upload/index.*` 已补一版更稳的本地旋转导出：选图改拿 `original` 原图、页内新增 `顺时针旋转` 兜底按钮、隐藏 canvas 现在显式带 `width/height` 实体尺寸，并在旋转/裁切导出前统一先铺白底再导出 JPG；当前手动顺时针旋转还会同步把现有题框坐标一起转过去，避免图片转了但框留在旧位置。当前目标是先止住“旋转后整张发黑/导出黑底”的问题。
- 2026-04-15 本地学生错题库 PDF 已收口旧备注残留：`wrong_question_submissions` 新库与旧库迁移都不再保留 `parent_note / teacher_comment` 两列；本地微信错题 detail/review 序列化也不再输出这两个字段；PDF 顶部标题现在改成 `学生名 错题库｜任课老师：...`，每题正文已删除单独的老师行，以及 `家长备注 / 老师备注` 两段。
- 2026-04-15 小程序错题本页已接上学生级 PDF 预览：`miniprogram/miniprogram/pages/parent-wrongbook/index.*` 现在会在页头展示 `查看 PDF`，并在每张错题卡上显示 `question_text`；同时 bridge 已补发 `GET /wechat/parent/children/<student_id>/wrong-question-library`，当前公网探测已不再返回 `Cannot GET ...`，而是正常转成 JSON 业务响应。
- 2026-04-15 本地网站端已补回家长上传 `AI 框选` 路由 `/api/wechat/wrong-question-boxes`，并在 `smart_wrong_questions.detect_wechat_wrong_question_boxes()` 里固定服务端提示词：当前会明确要求“只框题目区域，忽略孩子手写字迹、演算、答案、批改痕迹”，不改小程序请求协议；本地回归已覆盖 route 与 N1N prompt 组装。
- 2026-04-15 家长错题上传页已继续补修拍照链路：`miniprogram/miniprogram/pages/parent-upload/index.js` 现在拍照改为请求 `original` 原图，避免压缩图吞掉 EXIF 方向信息；选图后仍会先读 `wx.getImageInfo().orientation`，对 `left / right / down` 等非 `up` 图片先用隐藏 canvas 旋正，再进入后续框选、裁切和统一提交；这轮还补了“继续拍照 / 继续选图”后自动切到新加那张图，避免框选区还停在旧图，并新增了页面级 `顺时针旋转` 兜底按钮。自动判别现在还会在控制台打印 `orientation / width / height / needsNormalization`，方便继续核对真机返回值。对应 orientation/选图辅助逻辑已下沉到 `miniprogram/miniprogram/pages/parent-upload/model.js`，并补了回归测试。
- 2026-04-15 已补发小程序家长错题本 bridge：正式环境 `https://xingrun.online/wechat/parent/children/<student_id>/wrong-questions` 不再返回 `Cannot GET ...`，当前公网已能命中 bridge 并转发到网站端；用 `test-openid` 探测时现返回 JSON 业务错误 `parent wechat account not found`，说明“查看错题本”此前的 blocker 是线上 bridge 漏发了这条 GET 路由，不是网站 `/api/wechat/children/<student_id>/wrong-questions` 缺失。
- 2026-04-14 已收口咨询批量整理的跟进状态越界问题：`ai_processor.py` 里的咨询助手提示词已明确锁定 `待邀约 / 跟进中 / 已报班 / 已劝退` 4 个可用状态，并明确禁止输出 `待开课缴费`、`已试听` 这类自造状态；`lesson_manager.normalize_consultation_batch_parse_result()` 现在也会自动丢弃非法 `follow_up_status` 并返回 warning，避免脏草稿继续进入前端确认流。
- 2026-04-14 已落地“咨询记录”页备注展示：`follow_up_note` 不单独开列，直接并入现有“咨询科目 / 来源渠道”信息块；桌面端与移动端都按统一信息高度预算展示，并且明确禁止横向滚动、悬浮展开或不等高列表。
- 这一轮实现只触达 `frontend/src/App.tsx`、`frontend/src/account-card.test.tsx` 和 `handoff.md`，没有改接口、录入逻辑或搜索逻辑。
- 2026-04-14 为打通 release 补修了微信错题上传分类回退问题：`/api/wechat/wrong-questions` 不再信任客户端传来的 `primary_error_type` / `secondary_error_summary` 旧字段，而是统一走服务端 `classify_wrong_question_reason()` 重新分类，现有回归用例已恢复通过。
- 首页 hero 已去掉外部 HLS 视频背景，改为本地可控的 `Grainient` 风格动态背景；当前配色按 Starain 现有主题收口为亮色 `sky/cyan` 渐变、暗色深蓝底，并已换成更容易直接看出在流动的 `flow bands` 版本。
- landing 断言测试已同步改成检查 `data-background="grainient"` 和 `data-grainient-palette="sky-cyan"`，不再依赖旧视频流地址。
- 生产发布流程文档已经单独收口到 `docs/deploy-release.md`；下一位 AI 如果要执行 `push / merge master / 部署`，优先直接照这份文档走，不要再现场猜步骤。
- `develop -> master -> 部署` 已在 2026-04-10 走完一轮；本次服务器直拉 GitHub 仍会卡住，最终按 `bundle + scp` 兜底成功发布。
- 2026-04-10 已补修生产机 GitHub 直拉链路：服务器仓库 `origin` 已从 HTTPS 改成 `git@github-xingrun-website:KaynXu/Xingrun-Website.git`，通过专用 deploy key 走 `ssh.github.com:443`。
- 本轮现场 proof 已确认生产机 `git ls-remote origin HEAD`、`git fetch origin`、`git pull --ff-only origin master` 都能直接在约 4 秒内完成，不再需要默认走 bundle。
- 本次已部署生产的最新提交是 `5ff8adb Merge branch 'develop'`；其中包含微信错题 `删除本题`、学生错题库旧 PDF 清理与自动跳下一题。
- 已将生产机仓库里未入库的微信错题热修回收到本地仓库：包括新的错因顶层分类、`display_text` 返回字段、可跳过重复分类的创建接口入参，以及 `/api/wechat/reason-classifications` 接口。
- 当前主线是 `智能错题` 收口。
- notebook 弹窗左列已改成紧凑行，不再用卡片堆叠；当前每行只保留 `第几题 / 时间 / 掌握状态`。
- notebook 弹窗右侧顶部重复的 `错题档案` 区和下面两块切换小卡片已删除，只保留真正的详情与编辑区。
- 微信错题详情区已补上错题库 PDF 入口；当记录带有 `student_library_pdf_path` 时，会直接显示 `预览 PDF / 下载 PDF`，并自动带当前登录 token。
- 本轮已再次确认：错题库 PDF 不是占位入口，当前后端已实现学生错题库 PDF 重建与下载接口，前端也已接通 `预览 PDF / 下载 PDF`。
- 本轮排查补充确认：前端 PDF 按钮不是全局常驻入口，当前仅在 `source='wechat_mp'` 且记录带有 `student_library_pdf_path` 的错题详情卡片里显示。
- 本轮已完成 `删除本题` 设计收口：网站端将只对本地 `wechat_mp` 错题开放真删除，删除后必须先删旧学生错题库 PDF，再按剩余有效题决定重建或清空，避免磁盘残留。
- 本轮已落地：网站端微信错题详情支持 `删除本题`；点击后会真删除本地 `wechat_mp` 记录，先删旧学生错题库 PDF，再按剩余有效题决定重建或清空，前端会自动跳到同学生下一题；若没有下一题则收起右侧详情区。
- 微信错题里的 `AI 归类错因` 已改成老师可编辑下拉；打开记录时默认带入当前 AI 分类，老师调整后会随现有保存接口一起提交。
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
- 最近一次相关产品代码提交并已部署生产的是 `5ff8adb Merge branch 'develop'`。

### 下一步
- 最值得继续做的是拿一个真实学生错题库 PDF 手工看一遍，确认顶部标题里的老师名、每题正文节奏、分页和几何题图片在真实浏览器/打印预览里都符合老师预期。
- 最值得继续做的是把新的小程序包上传到微信开发者工具 / 真机，实际点一次错题本页顶部 `查看 PDF`，确认 `wx.downloadFile + wx.openDocument` 在真机里能正常打开网站 PDF。
- 最值得继续做的是把这轮本地恢复的 `/api/wechat/wrong-question-boxes` 和固定 prompt 按正常 release 流程发到线上，再用真机拿一张“有孩子手写痕迹的整页作业”实测一次 AI 框选，看是否明显减少误框答案区和草稿区。
- 最值得继续做的是拿真机在家长上传页拍一张横屏照片和一张竖屏照片各走一遍，再追加拍一张新图，确认四件事都成立：控制台里的 orientation 返回值合理、预览方向正确、框选区默认切到新拍那张、最终提交到老师端的图片方向一致；如果某些真机仍回 `orientation='up'` 但画面横着，优先走页面里的 `顺时针旋转` 兜底。
- 如果继续跟这条小程序旋转问题，最值得做的是在微信开发者工具和真机上各拿一张大图手工点一次 `顺时针旋转`，确认页面预览、后续裁切导出和最终提交到老师端都不再出现整张黑图或黑底。
- 最值得继续做的是拿一个真实已绑定家长账号在小程序里手工点一次 `查看错题本`，确认现在展示的是孩子错题列表或业务空态，而不是路由缺失兜底文案。
- 如果继续咨询记录这一项，最值得做的是用一段真实批量整理文案在页面里手工跑一次 `AI 批量整理`，确认非法状态会被 warning 掉、草稿里只保留合法字段，避免只靠单测判断 UI 呈现。
- 最值得继续做的是打开真实咨询记录页做一次人工 smoke check，确认有备注和无备注的记录在桌面端、移动端下都保持统一节奏，并确认备注没有把操作区和状态 badge 挤乱。
- 如果继续发版，当前可以直接按 `docs/deploy-release.md` 的标准路径做 `develop -> master -> 部署`；这轮之前卡住的微信错题上传 release blocker 已经修掉。
- 最值得继续做的是打开真实首页做一次手工 smoke check，确认新的 grainient 背景在桌面端、移动端和夜间模式下都不会压低首屏文案与按钮可读性。
- 如果下次再做 release，直接按 `docs/deploy-release.md` 执行；重点是正常路径只走 `develop -> master -> 部署`，先走服务器 SSH 直拉，只有 SSH over 443 也失败时才切 `bundle`。
- 如果继续收智能错题 notebook 体验，可以再决定是否把 PDF 入口上提到弹窗头部，或在学生卡片层显示“已生成错题库 PDF”状态；当前仅在右侧详情区显示入口。
- 当前最值得继续做的是打开真实页面做一次手工 smoke check，确认生产环境下删除本题后二次确认文案、跳下一题、最后一题删完后右侧详情收起，以及 PDF 入口都符合预期。
- 最值得继续做的是打开真实页面做一轮人工 smoke check，确认 staff 视角下“老师 -> 班级 -> 学生”联动和 notebook 区交互符合预期，然后再决定是否跟随下一次 release 一起部署。
- 这 3 条后端失败修完后，下一步就是按 release 流程重新做一次 `develop -> push -> merge master -> 部署`，不需要再先卡在这 3 条上。
- 最适合继续做的是确认这轮命名收口是否要继续扩到更多历史文档文件名，当前先只改了内容和活代码命名，没有批量重命名 `docs/superpowers/*` 的历史文件路径。
- 优先处理：
  - 如果还要继续收口，可以单独决定是否把 `teacher_comment` / `status='reviewed'` 这类兼容旧列也进一步包到更显式的 legacy helper 里
  - 如果还要继续清历史材料，可以再扫 `docs/` 非 `superpowers` 目录和外部备份仓库里是否还保留旧口径
- 这一步仍适合直接在 `develop` 做，小改动即可，不需要并行开第二条错题链路。

### 风险
- 这轮 `AI 框选` 提示词优化目前只在本地代码和单测里验证过，还没在线上真机图片上确认收益；如果 provider 实际对提示词不敏感，后续仍可能需要继续叠加坐标过滤或示例图策略。
- 当前拍照自动旋正仍依赖 `wx.getImageInfo().orientation` 和小程序 canvas 预处理；这轮虽然改成优先拿 `original` 原图来保留方向信息，并补了手动旋转兜底，但还没有在真实 iPhone / Android 真机上逐台确认所有相机输出都一致，且原图会让 AI 框选阶段的单张本地图片更大。
- 内嵌小程序快照这轮是按“白底 canvas + 显式画布尺寸 + 导出前等待一拍”来止黑图；这在微信 canvas 常见问题里通常有效，但还没有拿真机长图/超大图把旋转和裁切都走完一遍。
- 当前这次只收口了咨询 `AI 批量整理` 链路；常规 `/api/consultations` create/update 仍没有在后端对白名单状态做硬校验，现阶段还是主要依赖前端下拉不让人手工写出非法状态。
- 咨询记录页备注展示方案当前成立的前提是“备注通常不会太长”；如果后续真实数据出现长段落，仍需要单独决定是否加录入约束或二级查看。
- 当前 grainient 背景是本地复刻版，不是直接复用 reactbits 原实现；视觉方向已经对齐，但如果后面要追求更接近原站的 shader 波纹细节，还需要再单独设计一轮。
- 生产机虽然已经改成 GitHub SSH over 443，但这条链路仍依赖服务器里的 deploy key 和 `~/.ssh/config` alias；如果后续被误删，部署会重新退化成 bundle 场景。
- 旧的零散部署口径已经开始收口，但历史对话、旧提交和个别旧文档里仍可能残留“直接发 develop”或“先看 master 再说”的过期说法；下一轮如果有人只看旧记录，不看 `docs/deploy-release.md`，仍可能误判流程。
- 当前错误类型下拉为了兼容现有错题记录，同时保留了固定错因和已出现过的 legacy downstream 分类；在真正统一错题后端分类口径前，这里仍是“固定列表 + 兼容旧值”的过渡态。
- 当前最大风险不是功能坏掉，而是“语义看起来像统一了，其实没有”。
- `monthly` 现在已经改成“PDF 成功后再扣费”，但单节 `review plan` worker 仍是 AI 成功后立即扣费；如果后面也要求单节 PDF 失败不扣费，这一块语义还没有跟上。
- `wechat_mp` 和 `downstream` 仍是两套字段语义；在真正统一后端契约前，不要只在共享前端类型上继续顺手收口字段。
- `wrong_question_submissions` 里这轮已经清掉 `parent_note / teacher_comment` 两个旧备注列，但 `wechat_mp` 和 `downstream` 仍是双语义模型；后续如果继续收口共享前端类型或代理 payload，仍要先确认不要误伤 downstream 契约。
- `smart_wrong_questions.py` 下游代理链还在，运行时仍是“本地微信错题 + downstream 服务”双来源模型。
- “删除本题” 这一轮如果前端没严格限制到 `wechat_mp`，就有误删 downstream 语义或误调用本地删除接口的风险。
- 当前 `删除本题` 仍是网站本地微信错题专属能力；如果后续要给 downstream 或微信端接同名按钮，必须继续保持“本地真删 / 下游自实现”边界，不要共用错误接口。
- 生产上 `pm2 restart xingrun` 后第一下即时健康检查偶尔会短暂失败，但随后会恢复到根路由 `302`；这是已知现象，当前未继续深挖。

### 已删除但仍有残留
- 这轮已把活代码里的旧智能错题口径收口成 `错题跟进 / 跟进记录 / 保存跟进记录 / 题目整理 / 教学素材 / 错因整理`。
- 这轮已把课堂反馈存储命名统一成 `lesson_class_feedbacks`、`save_lesson_class_feedback()`、`get_lesson_class_feedback()`、`build_lesson_class_feedback_editor_state()`，并补了旧表自动迁移测试。
- `app.py` 里对旧 helper 的未用导入已经删除。
- `docs/superpowers/*` 与本文件历史条目里的旧课堂反馈 / 已删除 helper 上下文已经同步改成 legacy 口径，避免下一轮把历史流水误判成当前实现。

### 最近相关提交
- `5ff8adb` `Merge branch 'develop'`
- `d6aedf9` `feat: add hard delete for local wrong questions`
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
