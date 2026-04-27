# Handoff

最后更新：2026-04-26

这份文件只保留当前仍然有效的状态、下一步、风险和工作区信息，不再追加历史流水。

## 当前状态
- 小程序子项目根目录是 `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram`，微信工程代码位于 `miniprogram/miniprogram/`，bridge 位于 `miniprogram/backend/`。
- 家长链路当前只保留 `绑定孩子 -> 家长首页 -> 上传错题 -> 查看错题本/PDF`。
- 家长上传最终提交已改成网站端 RQ + Redis 异步任务：小程序只上传题图和可选录音 URL，bridge 转发到网站 `/api/wechat/wrong-questions` 后拿到 `202 + task`；录音转写、错因归类、题图识别、错题入库和 PDF 重建都由网站 RQ worker 后台完成。
- 家长上传最终提交不再要求 `childReasonText` 或录音 URL 必填；只要有题图就能入队，错因缺失时服务器会用“待补充｜孩子暂未填写错因”占位，避免家长因为没填文字或录音上传失败被挡在提交前。
- 家长上传页提交后会轮询后台任务状态：`ready` 才提示“识别完成”，`failed` 会展示服务器返回的失败原因，不再把“任务已提交”误提示成最终上传成功。
- 家长首页绑定态已恢复 `绑定更多孩子` 入口，继续复用 `goBindMore()` 返回 `pages/parent-bind/index`。
- 家长错题本页已恢复学生级 `查看 PDF`，bridge 仍保留 `GET /wechat/parent/children/:studentId/wrong-question-library`。
- 家长错题本页的题目卡片现在已补上轻量 LaTeX 可读化：`pages/parent-wrongbook/latex-preview.js` 会把 `$...$`、`\frac`、`\sqrt`、`\mathbb{R}`、上下标等源码转成普通文本预览，避免小程序列表里直接显示公式源码；顶部 `查看 PDF` 仍是服务器上的正式版排版。
- 家长错题本页的 LaTeX 预处理 helper 这一版已改成更保守的小程序兼容写法，不再依赖 `Array.from` 或 `String.fromCharCode` 这类本项目此前未在小程序侧使用过的 API，优先避免微信运行时白屏。
- 家长上传页当前是手动补框模式：`补加框 / 删除当前 / 顺时针旋转`，每个题框可选填写文字或语音错因，再统一提交。
- 家长上传页裁切后上传前会把超大题图压到 `1280 x 1792` 以内并用 `quality=0.82` 导出，避免拍原图/整页图时触发服务器 `413 Request Entity Too Large`。
- 家长上传页语音转录已切到网站后端本地 `faster-whisper`，当前固定 `base + cpu + int8`，先自动识别语言，只有自动识别没出有效文本时才回退 `zh`，不再单独要求 OpenAI Whisper key；但语音转成文字后，错因归类仍走现有聊天类 AI provider，所以系统仍需要至少一个可用 provider key。
- 家长上传页顶部“拍照 / 继续选图”和底部“统一提交所有错题”按钮都已改为独立窄屏样式，避免被系统默认按钮宽度挤成两行。
- `AI 框选` 已从小程序页面、`parentApi.js`、bridge、website API 和 `smart_wrong_questions.py` 活代码里删除；`POST /wechat/parent/wrong-question-boxes` 与 `/api/wechat/wrong-question-boxes` 已不再是当前能力。

## 本轮完成
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

## 剩余问题
- 还没有在生产机启动真实 Redis + RQ worker 后，用真机完整走“录音 + 题图提交 -> 后台识别完成 -> 错题本/PDF 刷新”的端到端 smoke。
- 还没有在真实 4 核 + 4GB 服务器上拿一段“中文为主但夹英文字母/公式”的录音跑过本地 `faster-whisper`，首个请求模型下载、后续 CPU 时延、峰值内存和自动识别命中率都还需要人工 smoke。
- 这轮上传页布局修复目前主要用本地自动测试验证过，还没有在微信开发者工具或真机上实际看一次“继续拍照 / 继续选图”和“统一提交所有错题”在不同机型上的展示。
- 错题本页 `查看 PDF` 入口虽然已有自动测试覆盖，但还需要真机再点一次确认 `wx.downloadFile + wx.openDocument` 运行时行为。
- 错题本页这轮补的是“轻量可读化”，不是小程序内真正的公式排版；如果后续要求卡片里也像网页/PDF 一样完整排版，需要单独上更重的渲染方案。
- 这轮超大图片上传修复已用本地自动测试覆盖导出尺寸规划，但还没有让真实小课家长重新拍一张原图提交来确认线上不再触发 `413`。

## 下一步
- 在目标服务器上先安装新依赖并用一段“中文叙述 + 英文字母/公式”真实短录音走一遍家长上传转录，确认模型首次下载、常驻内存、自动识别结果和单次转录时延都能接受；如果 `base` 效果不够，再单独评估是否升到 `small`。
- 在微信开发者工具或真机打开家长上传页，确认顶部“拍照 / 继续选图”和底部“统一提交所有错题”在窄屏和长文案状态下都不再换行。
- 在微信开发者工具或真机手工走一次家长上传页：选图、补框、删除框、旋转、填写文字/语音错因、统一提交。
- 重新上传小程序包后，用一张大尺寸竖版原图走一次“补框 -> 填错因 -> 统一提交”，确认请求返回成功且生产 Nginx 不再出现 `413`。
- 在微信开发者工具或真机点一次家长首页的 `绑定更多孩子`，确认能返回绑定页且窄屏排版正常。
- 在微信开发者工具或真机点一次错题本页顶部 `查看 PDF`，确认 PDF 能正常下载和打开。
- 在微信开发者工具或真机打开一次家长错题本页，拿含公式的真实题目看一眼卡片预览，确认多行换行、长公式断行和顶部 PDF 入口组合体验都符合预期。

## 风险
- 部署时如果只更新 Flask/bridge 而没有安装 Redis、启动 Redis 服务和 RQ worker，上传任务会停在 `pending` 或直接入队失败；需要把 worker 纳入 PM2/systemd 管理。
- 本地 `faster-whisper` 现在固定走 `base + cpu + int8`，并采用“自动识别优先、空结果再回退 `zh`”；这对中文短录音和夹少量英文字母通常更平衡，但在口音重、环境噪声大或服务器并发高时，识别质量和延迟仍可能不如云端 Whisper。
- 这轮 AI 框选删除后，上传页完全依赖手动补框；如果老师或家长之前习惯用 AI，需要同步确认产品预期。
- 当前拍照自动旋正和本地 canvas 旋转链路仍未做真机全量 smoke，尤其是大图、横屏照片和连续追加图片场景。
- 这轮只在小程序端压缩上传裁切图，没有改服务器 `client_max_body_size`；如果家长直接上传的裁切区域仍异常超长，仍需结合真实照片再决定是否继续降尺寸或调整 Nginx 限制。
- 上传页长文案按钮现在依赖 `width: 100% + white-space: nowrap` 保持单行，若后续再改更长文案，需要一起复查窄屏排版。
- 当前错题本页的 LaTeX 方案是纯文本可读化，不是真正数学排版；复杂矩阵、对齐公式或非常长的嵌套公式在小程序卡片里仍可能退化，精确显示仍要依赖顶部 PDF。

## 当前工作区
- 当前分支：`develop`
- 小程序相关活代码和活文档里不应再保留 `wrong-question-boxes` 或 `AI 框选` 作为当前能力描述。
