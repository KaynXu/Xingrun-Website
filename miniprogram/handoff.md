# Handoff

最后更新：2026-05-03

这份文件只保留当前仍然有效的状态、下一步、风险和工作区信息，不再追加历史流水。

## 当前状态
- 2026-05-03 当前活跃 Ralph 队列为“小程序视觉正式版升级”：新的 `scripts/ralph/prd.json` 只聚焦微信小程序前端 `miniprogram/miniprogram/`，目标是让家长端页面更好看、更像正式产品，尤其锁定按钮位置、主次操作排列、底部操作区、小屏不换行/不重叠；旧“小程序家长上传 2.0 稳定性”PRD/进度已归档到 `scripts/ralph/archive/miniprogram_upload_2_stability_prd_20260503.json` 和 `scripts/ralph/archive/miniprogram_upload_2_stability_progress_20260503.txt`。`MP-VISUAL-001` 到 `MP-VISUAL-006` 已完成；共享视觉 primitives 已集中到 `miniprogram/miniprogram/app.wxss`，按钮层级已锁定为孩子卡片主操作优先、上传工具与删除隔离、成功态错题本/进度为主操作；家长首页已补星润家长端身份、无孩子空态、绑定数量、班级/老师信息和长文本窄屏规则；家长绑定页已补正式邀请码查询区、已绑定孩子卡片、班级结果卡、学生确认卡、空学生状态和长文本窄屏规则；家长上传页已拆成选图、当前图片、框题工具、错因/专题、进度和底部提交的正式流程区；`scripts/ralph/run_codex_ralph.sh --check` 当前下一条为 `MP-VISUAL-007`。
- 2026-05-03 “小程序家长上传 2.0 稳定性”Ralph PRD 已归档；`MP-UPLOAD-001` 到 `MP-UPLOAD-012` 已全部完成，本地自动验收已收口。
- 2026-05-03 `MP-UPLOAD-012` 已完成：新增最终验收脚本 `scripts/ralph/parent_upload_2_acceptance_guardrail_proof.sh`，显式检查选图、补框、文字/语音错因、裁切导出、提交、任务接收、ready/failed/pending 轮询、错题本刷新、PDF 未就绪、活代码无当前 AI 框选能力、PRD 全 story `passes=true`，并串起定向小程序/bridge/网站测试和共享基线 proof。
- 2026-05-03 `MP-UPLOAD-011` 已完成：新增生产上传链路 smoke runbook `docs/production-upload-pipeline-smoke-runbook.md` 和本地校验脚本 `scripts/ralph/production_upload_smoke_runbook_proof.sh`，覆盖 PM2、Redis/RQ worker、Flask、bridge、上传大小限制、任务状态、错题本/PDF 检查，以及 pending、enqueue 失败、413、PDF refresh 失败处理；自动 proof 只校验本地引用和基线，不访问生产。
- 2026-05-03 `MP-UPLOAD-010` 已完成：家长上传成功卡片新增“查看错题本 / 刷新进度”，会把已接收 task id 带到孩子错题本；家长错题本进入时先刷新 ready/failed/background 上传任务，再拉错题记录和 PDF 状态，识别失败或仍在处理的卡片不会展示 AI 成功题干，PDF 未就绪、缺 `pdf_url`、下载失败和打开失败都会给可恢复提示。
- 2026-05-03 `MP-UPLOAD-008` 已完成：网站上传任务 API 在入队失败时会持久化 `failed + retryable=1` task 并返回结构化 502；任务状态 payload 现在带 `state / retryable / is_stale / record_status / record_missing`，可区分 pending、stale pending、ready、failed 和 missing-record 状态。
- 小程序子项目根目录是 `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram`，微信工程代码位于 `miniprogram/miniprogram/`，bridge 位于 `miniprogram/backend/`。
- 家长链路当前只保留 `绑定孩子 -> 家长首页 -> 上传错题 -> 查看错题本/PDF`。
- 家长上传最终提交已改成网站端 RQ + Redis 异步任务：小程序只上传题图和可选录音 URL，bridge 转发到网站 `/api/wechat/wrong-questions` 后拿到 `202 + task`；录音转写、错因归类、题图识别、错题入库和 PDF 重建都由网站 RQ worker 后台完成。
- 家长上传最终提交不再要求 `childReasonText` 或录音 URL 必填；只要有题图就能入队，错因缺失时服务器会用“待补充｜孩子暂未填写错因”占位，避免家长因为没填文字或录音上传失败被挡在提交前。
- 家长上传页提交后会轮询后台任务状态：`ready` 才提示“识别完成”，`failed` 会展示服务器返回的失败原因，不再把“任务已提交”误提示成最终上传成功。
- 家长上传页会把已接收上传任务按 `xr_parent_upload_tasks_v1:<openId>:<bindingId>` 存入本机恢复记录，附带孩子和图片/题框元数据；页面重开后只恢复轮询任务状态，不重新上传裁切图，ready/failed 终态会从恢复记录清掉，损坏或不可读 storage 会显示可恢复提示。
- 家长首页绑定态已恢复 `绑定更多孩子` 入口，继续复用 `goBindMore()` 返回 `pages/parent-bind/index`。
- 家长错题本页已恢复学生级 `查看 PDF`，bridge 仍保留 `GET /wechat/parent/children/:studentId/wrong-question-library`。
- 家长错题本页的题目卡片现在已补上轻量 LaTeX 可读化：`pages/parent-wrongbook/latex-preview.js` 会把 `$...$`、`\frac`、`\sqrt`、`\mathbb{R}`、上下标等源码转成普通文本预览，避免小程序列表里直接显示公式源码；顶部 `查看 PDF` 仍是服务器上的正式版排版。
- 家长错题本页的 LaTeX 预处理 helper 这一版已改成更保守的小程序兼容写法，不再依赖 `Array.from` 或 `String.fromCharCode` 这类本项目此前未在小程序侧使用过的 API，优先避免微信运行时白屏。
- 家长上传页当前是手动补框模式：`补加框 / 顺时针旋转` 是同组普通工具，`删除当前题框` 已拆成独立 danger 操作；每个题框可选填写文字或语音错因，再统一提交。
- 家长上传页手动框选已补稳定性：大竖图/大横图会按预览区稳定布局，旋转后当前图片和小题框选中状态保持，删除当前框后选中同位置的下一框，裁切失败会标明第几题且保留草稿，裁切/旋转导出期间会锁住手势和重复提交。
- 家长上传页手动题框的最小缩放限制已从旧的 `72px`/`0.08` 归一化下限收小为 `16px` 预览尺寸；保存和旋转都不会再把家长调好的小题框强制放大，便于框单道小题或较窄题目。
- 家长上传页现在允许“切到语音错因但未成功录音”的题目继续提交：生成上传任务时只有存在 `voiceFilePath` 才保留 `voice` 模式，否则回退为 `text`/空错因，避免拿空音频路径调用 `/upload` 导致整批提交失败。
- 家长上传页裁切后上传前会把超大题图压到 `1280 x 1792` 以内并用 `quality=0.82` 导出，避免拍原图/整页图时触发服务器 `413 Request Entity Too Large`。
- 家长上传页现在对语音上传、压缩后题图任务提交和任务状态刷新使用专用短超时；压缩后仍 413 会提示草稿已保留并让家长缩小框选或重拍，5xx、网络失败和超时会提示保留草稿并可重新点“统一提交所有错题”重试。
- 家长上传页语音转录已切到网站后端本地 `faster-whisper`，当前固定 `base + cpu + int8`，先自动识别语言，只有自动识别没出有效文本时才回退 `zh`，不再单独要求 OpenAI Whisper key；但语音转成文字后，错因归类仍走现有聊天类 AI provider，所以系统仍需要至少一个可用 provider key。
- 家长上传页顶部“拍照 / 继续选图”和底部“统一提交所有错题”按钮都已改为独立窄屏样式，避免被系统默认按钮宽度挤成两行。
- `AI 框选` 已从小程序页面、`parentApi.js`、bridge、website API 和 `smart_wrong_questions.py` 活代码里删除；`POST /wechat/parent/wrong-question-boxes` 与 `/api/wechat/wrong-question-boxes` 已不再是当前能力。
- 家长首页、家长绑定页和家长错题本页的关键操作区已改成窄屏优先布局：孩子卡片、学生绑定卡片和错题库 PDF 入口不再横向挤压，操作按钮改为全宽单行，优先降低安卓/鸿蒙/微信容器窄屏下的换行和误触风险。

## 本轮完成
- 2026-05-03 已完成 `MP-VISUAL-006`：家长上传页现在按正式工具流拆成选图、当前图片、手动框题、错因/专题、上传进度和底部提交区，提交面板保留 safe-area 间距，删除题框仍与最终提交分离；未改上传 JS 行为。`scripts/ralph/miniprogram_visual_polish_proof.sh` 和 `scripts/ralph/miniprogram_upload_stability_proof.sh` 已通过临时 proof `/tmp/xingrun_mp_visual_006_proof.sh`。
- 2026-05-03 已完成 `MP-VISUAL-005`：家长绑定页现在用正式邀请码查询面板、已绑定孩子卡片、班级结果卡、每个学生的绑定确认卡和无可绑定学生状态；长班级名/学生名会断行，不会把 `查看班级和学生` 或 `绑定这个孩子` 挤出窄屏。`scripts/ralph/miniprogram_visual_polish_proof.sh` 已新增绑定页结构检查，临时 proof `/tmp/xingrun_mp_visual_005_proof.sh` 串跑视觉 proof 和上传稳定性 proof 通过。
- 2026-05-03 已完成 `MP-VISUAL-004`：家长首页现在呈现星润家长端身份、无孩子状态的下一步提示、已绑定孩子数量、孩子卡片里的班级/任课老师信息和整理进度提示；`scripts/ralph/miniprogram_visual_polish_proof.sh` 已新增首页成品化结构检查，临时 proof `/tmp/xingrun_mp_visual_004_behavior_proof.sh` 串跑视觉 proof 和上传稳定性 proof 通过。
- 2026-05-03 已完成 `MP-VISUAL-003`：家长首页孩子卡片改为主操作 `上传错题` 在前、次操作 `查看错题本` 在后；上传页把 `补加框 / 顺时针旋转` 归为普通工具，把 `删除当前题框` 拆成独立 danger 操作；上传成功态把 `查看错题本 / 刷新进度` 设为主操作、`返回家长主页` 设为次操作。`scripts/ralph/miniprogram_visual_polish_proof.sh` 已新增对应结构检查，临时 proof `/tmp/xingrun_mp_visual_003_proof.sh` 串跑视觉 proof 和上传稳定性 proof 通过。
- 2026-05-03 已完成 `MP-VISUAL-002`：`app.wxss` 现在统一承载家长端页面背景、卡片、标题、主/次/icon 按钮、状态标签和 safe-area bottom action bar；页面 wxss 保留页面专属布局和上传裁切/画布规则，不再各自定义 `.primary-btn` / `.ghost-btn` 主色。`scripts/ralph/miniprogram_visual_polish_proof.sh` 已新增共享视觉 system 和按钮样式集中化检查。
- 2026-05-03 已完成 `MP-VISUAL-001`：新增 `scripts/ralph/miniprogram_visual_polish_proof.sh`，本地检查 parent-home、parent-bind、parent-upload、parent-wrongbook 的页面结构、主次按钮层级、删除动作隔离、底部提交/窄屏按钮规则和原型/调试类文案残留；该 proof 不依赖微信开发者工具、真机、生产数据、密钥、Redis/RQ 或 Flask。
- 2026-05-03 已完成 `MP-UPLOAD-012`：最终 guardrail `scripts/ralph/parent_upload_2_acceptance_guardrail_proof.sh` 会先检查验收覆盖清单和活代码 AI 框选残留，再运行上传页/错题本/parentApi、bridge、网站上传 API/worker 定向测试，并强制 PRD 全 story 为 `passes=true` 后才报告完成。
- 2026-05-01 已修复家长上传页手动框选最小尺寸过大问题：题框拖拽缩放和保存归一化改为复用 `buildBoxTouchFrame()` / `normalizeDisplayBoxFrame()`，最低保留 `16px` 可操作尺寸，旋转窄题框时不再回到 8% 宽高；新增模型回归测试覆盖缩小、保存和旋转窄框。
- 2026-05-03 已完成 `MP-UPLOAD-002`：家长上传页提交时会显示裁切题图、上传语音、上传题图/提交任务、任务已接收、服务器识别、后台继续识别、识别完成、部分失败和失败等阶段反馈；提交中会禁用会改动草稿的按钮/输入控件，失败或完成后释放。基线 proof 继续走 `scripts/ralph/miniprogram_upload_stability_proof.sh`。
- 2026-05-03 已完成 `MP-UPLOAD-003`：家长上传任务轮询不再因单个状态请求短暂失败而整批失败；缺 id 或非法状态的任务 payload 会按原 task id 保持 pending；ready/failed/pending 混合批次会继续轮询 pending 项，耗尽后明确提示仍在后台处理，并保留已接收 task id。
- 2026-05-03 已完成 `MP-UPLOAD-004`：家长上传页会持久化已接收 task id 和孩子/图片/题框元数据，重开页面后恢复轮询 pending 任务且不重新上传裁切图；ready/failed 终态会清理恢复记录，损坏或不可读 storage 会显示可恢复提示。
- 2026-05-03 已完成 `MP-UPLOAD-005`：新增手动框选交互回归，覆盖大竖图/大横图、旋转图、小题框、切换当前图片、删除当前框、多个题框导出和裁切失败；裁切失败按题号显示并保留草稿，旋转/失败/删除后选中状态稳定，裁切或旋转导出期间禁止冲突手势和重复提交。
- 2026-05-03 已完成 `MP-UPLOAD-006`：语音上传超时收为 20 秒，压缩后题图任务提交收为 30 秒，上传任务状态刷新收为 8 秒；新增回归覆盖超时、压缩后 413、5xx、网络失败和用户重试，失败后保留草稿，重试拿到任务后才清空。
- 2026-05-03 已完成 `MP-UPLOAD-007`：bridge 上传代理现在保留网站 `202` 接收任务 payload，即使缺少可选 task 字段也不本地判失败；网站 `400/413/502/timeout/malformed response` 会映射为结构化 bridge 响应并保留 `retryable` 和任务信息；小程序 `parentApi` 的错误对象会保留 bridge 返回的 `task/payload` 元数据。
- 2026-05-03 已完成 `MP-UPLOAD-009`：识别成功后如果 PDF 重建失败，任务会失败但保留已创建错题记录、题图和识别文本；失败任务状态现在提供 `parent_error_message` 给家长端展示，并保留 `maintainer_error_detail` 供维护排查。
- 2026-05-03 已完成 `MP-UPLOAD-010`：上传完成状态卡提供直接查看孩子错题本/刷新进度入口并保留 task id；错题本页会刷新 ready/failed/background 上传任务状态，诚实展示识别失败/后台处理中记录和 PDF 未就绪、缺失、下载失败、打开失败的恢复提示。
- 2026-05-01 已做小程序稳定性排查并修复语音错因空录音的提交失败风险：`buildUploadJobs()` 对没有录音文件的语音框回退到 `text` 模式，并新增回归测试。临时 proof `/tmp/xingrun_miniprogram_stability_proof.sh` 已通过 bridge 13 条测试、bridge `tsc` build、小程序 40 条测试、活代码陈旧 `AI 框选` 扫描和 `git diff --check`。
- 家长上传页最终提交不再先调用转写和错因归类接口，语音错因只先传 `/upload` 得到音频 URL，再随题图提交给服务器后台任务。
- bridge 的 `/wechat/parent/wrong-questions` 已改为接受 `childReasonAudioUrl` 并返回 `202 + task`，同时新增 `/wechat/parent/wrong-question-upload-tasks/:taskId` 状态查询代理。
- 小程序上传成功态文案已从“上传成功/进入老师工作区”改为“已提交/服务器正在识别”。
- 网站后端录音转文字实现从 OpenAI Whisper 改成了本地 `faster-whisper`，并新增后端单测锁定“自动识别优先、必要时回退中文”的行为；`requirements.txt` 已补入 `faster-whisper` 依赖。
- 家长上传页选图按钮和统一提交按钮都新增专用窄屏样式，宽度改为占满内容区，长文案保持单行显示。
- 小程序范围测试新增这两个按钮的布局约束校验，覆盖 class、宽度和不换行规则。
- 家长错题本页新增 `pages/parent-wrongbook/latex-preview.js`，现在会先把题干里的 LaTeX 源码做轻量可读化，再显示到列表卡片里。
- 新增 `pages/parent-wrongbook/latex-preview.test.js`，并更新 `parent-only-scope.test.js`，覆盖“题目卡片接入 LaTeX 预处理”和“`$...$ / \\frac / \\mathbb{R}` 转可读文本”的回归。
- LaTeX 预处理 helper 已进一步回退到更保守的 ES 运行时用法，去掉了 `Array.from` / `String.fromCharCode`，用于降低小程序真机或开发者工具白屏风险。
- 2026-04-26 排查“小课家长上传不了错题”时，生产 Nginx 日志确认历史上传失败里存在 `/wechat/parent/wrong-questions` `413`；小程序上传裁切导出已新增尺寸/质量上限，降低超大原图上传失败概率。临时 proof `/tmp/xingrun_parent_upload_oversize_proof.sh` 已跑通 32 条小程序上传/parent API/范围测试。
- 2026-04-28 已收口小程序家长端窄屏 UI：`parent-home` 的孩子卡片和按钮区、`parent-bind` 的学生卡片/已绑定入口、`parent-wrongbook` 的 PDF 入口都改为纵向堆叠；新增小程序范围测试锁定这些样式约束。

## 剩余问题
- 还没有在生产机启动真实 Redis + RQ worker 后，用真机完整走“录音 + 题图提交 -> 后台识别完成 -> 错题本/PDF 刷新”的端到端 smoke。
- 还没有在真实 4 核 + 4GB 服务器上拿一段“中文为主但夹英文字母/公式”的录音跑过本地 `faster-whisper`，首个请求模型下载、后续 CPU 时延、峰值内存和自动识别命中率都还需要人工 smoke。
- 这轮上传页布局修复目前主要用本地自动测试验证过，还没有在微信开发者工具或真机上实际看一次“继续拍照 / 继续选图”和“统一提交所有错题”在不同机型上的展示。
- 错题本页 `查看 PDF` 入口虽然已有自动测试覆盖，但还需要真机再点一次确认 `wx.downloadFile + wx.openDocument` 运行时行为。
- 错题本页这轮补的是“轻量可读化”，不是小程序内真正的公式排版；如果后续要求卡片里也像网页/PDF 一样完整排版，需要单独上更重的渲染方案。
- 这轮超大图片上传修复已用本地自动测试覆盖导出尺寸规划，但还没有让真实小课家长重新拍一张原图提交来确认线上不再触发 `413`。

## 下一步
- 当前 Ralph 下一条自动 story 是 `MP-VISUAL-007 Polish parent wrongbook and PDF entry`；后续视觉 story 必须同时跑 `scripts/ralph/miniprogram_visual_polish_proof.sh` 和 `scripts/ralph/miniprogram_upload_stability_proof.sh`。
- 下一步只做手工 smoke：微信开发者工具/真机上传、真实语音 + 题图走生产 Redis/RQ worker、错题本刷新和 PDF 打开。
- 在目标服务器上先安装新依赖并用一段“中文叙述 + 英文字母/公式”真实短录音走一遍家长上传转录，确认模型首次下载、常驻内存、自动识别结果和单次转录时延都能接受；如果 `base` 效果不够，再单独评估是否升到 `small`。
- 在微信开发者工具或真机打开家长上传页，确认顶部“拍照 / 继续选图”和底部“统一提交所有错题”在窄屏和长文案状态下都不再换行。
- 在微信开发者工具或真机打开家长首页、绑定页和错题本页，重点看长学生名/长班级名、`绑定更多孩子`、`绑定这个孩子` 和 `查看 PDF` 在安卓/鸿蒙窄屏下是否仍然清楚、可点。
- 在微信开发者工具或真机手工走一次家长上传页：选图、补框、删除框、旋转、填写文字/语音错因、统一提交。
- 在微信开发者工具或真机用整页题图把题框缩到单道小题/窄题附近，确认小题框可调、旋转后不变大、最终裁切范围符合家长预期。
- 在微信开发者工具或真机补一次“切到语音错因但不录音/录音失败后仍提交”的 smoke，确认不会再被空音频上传挡住。
- 重新上传小程序包后，用一张大尺寸竖版原图走一次“补框 -> 填错因 -> 统一提交”，确认请求返回成功且生产 Nginx 不再出现 `413`。
- 在微信开发者工具或真机点一次家长首页的 `绑定更多孩子`，确认能返回绑定页且窄屏排版正常。
- 在微信开发者工具或真机点一次错题本页顶部 `查看 PDF`，确认 PDF 能正常下载和打开。
- 在微信开发者工具或真机打开一次家长错题本页，拿含公式的真实题目看一眼卡片预览，确认多行换行、长公式断行和顶部 PDF 入口组合体验都符合预期。

## 风险
- 部署时如果只更新 Flask/bridge 而没有安装 Redis、启动 Redis 服务和 RQ worker，上传任务会停在 `pending` 或直接入队失败；需要把 worker 纳入 PM2/systemd 管理。
- 本地 `faster-whisper` 现在固定走 `base + cpu + int8`，并采用“自动识别优先、空结果再回退 `zh`”；这对中文短录音和夹少量英文字母通常更平衡，但在口音重、环境噪声大或服务器并发高时，识别质量和延迟仍可能不如云端 Whisper。
- 这轮 AI 框选删除后，上传页完全依赖手动补框；如果老师或家长之前习惯用 AI，需要同步确认产品预期。
- 当前拍照自动旋正和本地 canvas 旋转链路仍未做真机全量 smoke，尤其是大图、横屏照片和连续追加图片场景。
- 题框最小尺寸已明显放宽，但自动测试只能覆盖坐标计算；不同真机触摸精度、系统字体和图片缩放后的实际可操作手感仍需要微信开发者工具或真机确认。
- 这轮只在小程序端压缩上传裁切图，没有改服务器 `client_max_body_size`；如果家长直接上传的裁切区域仍异常超长，仍需结合真实照片再决定是否继续降尺寸或调整 Nginx 限制。
- 上传页长文案按钮现在依赖 `width: 100% + white-space: nowrap` 保持单行，若后续再改更长文案，需要一起复查窄屏排版。
- 当前错题本页的 LaTeX 方案是纯文本可读化，不是真正数学排版；复杂矩阵、对齐公式或非常长的嵌套公式在小程序卡片里仍可能退化，精确显示仍要依赖顶部 PDF。
- 这轮窄屏 UI 修复用自动测试锁定了 WXSS 约束，但还没有在微信开发者工具、安卓真机或鸿蒙真机里实际截图确认不同系统字体渲染。

## 当前工作区
- 当前分支：`develop`
- 小程序相关活代码和活文档里不应再保留 `wrong-question-boxes` 或 `AI 框选` 作为当前能力描述。
