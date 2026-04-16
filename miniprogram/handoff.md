# Handoff

最后更新：2026-04-16

这份文件只保留当前仍然有效的状态、下一步、风险和工作区信息，不再追加历史流水。

## 当前状态
- 小程序子项目根目录是 `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram`，微信工程代码位于 `miniprogram/miniprogram/`，bridge 位于 `miniprogram/backend/`。
- 家长链路当前只保留 `绑定孩子 -> 家长首页 -> 上传错题 -> 查看错题本/PDF`。
- 家长首页绑定态已恢复 `绑定更多孩子` 入口，继续复用 `goBindMore()` 返回 `pages/parent-bind/index`。
- 家长错题本页已恢复学生级 `查看 PDF`，bridge 仍保留 `GET /wechat/parent/children/:studentId/wrong-question-library`。
- 家长错题本页的题目卡片现在已补上轻量 LaTeX 可读化：`pages/parent-wrongbook/latex-preview.js` 会把 `$...$`、`\frac`、`\sqrt`、`\mathbb{R}`、上下标等源码转成普通文本预览，避免小程序列表里直接显示公式源码；顶部 `查看 PDF` 仍是服务器上的正式版排版。
- 家长错题本页的 LaTeX 预处理 helper 这一版已改成更保守的小程序兼容写法，不再依赖 `Array.from` 或 `String.fromCharCode` 这类本项目此前未在小程序侧使用过的 API，优先避免微信运行时白屏。
- 家长上传页当前是手动补框模式：`补加框 / 删除当前 / 顺时针旋转`，每个题框单独填写文字或语音错因，再统一提交。
- 家长上传页顶部“拍照 / 继续选图”和底部“统一提交所有错题”按钮都已改为独立窄屏样式，避免被系统默认按钮宽度挤成两行。
- `AI 框选` 已从小程序页面、`parentApi.js`、bridge、website API 和 `smart_wrong_questions.py` 活代码里删除；`POST /wechat/parent/wrong-question-boxes` 与 `/api/wechat/wrong-question-boxes` 已不再是当前能力。

## 本轮完成
- 家长上传页选图按钮和统一提交按钮都新增专用窄屏样式，宽度改为占满内容区，长文案保持单行显示。
- 小程序范围测试新增这两个按钮的布局约束校验，覆盖 class、宽度和不换行规则。
- 家长错题本页新增 `pages/parent-wrongbook/latex-preview.js`，现在会先把题干里的 LaTeX 源码做轻量可读化，再显示到列表卡片里。
- 新增 `pages/parent-wrongbook/latex-preview.test.js`，并更新 `parent-only-scope.test.js`，覆盖“题目卡片接入 LaTeX 预处理”和“`$...$ / \\frac / \\mathbb{R}` 转可读文本”的回归。
- LaTeX 预处理 helper 已进一步回退到更保守的 ES 运行时用法，去掉了 `Array.from` / `String.fromCharCode`，用于降低小程序真机或开发者工具白屏风险。

## 剩余问题
- 这轮上传页布局修复目前主要用本地自动测试验证过，还没有在微信开发者工具或真机上实际看一次“继续拍照 / 继续选图”和“统一提交所有错题”在不同机型上的展示。
- 错题本页 `查看 PDF` 入口虽然已有自动测试覆盖，但还需要真机再点一次确认 `wx.downloadFile + wx.openDocument` 运行时行为。
- 错题本页这轮补的是“轻量可读化”，不是小程序内真正的公式排版；如果后续要求卡片里也像网页/PDF 一样完整排版，需要单独上更重的渲染方案。

## 下一步
- 在微信开发者工具或真机打开家长上传页，确认顶部“拍照 / 继续选图”和底部“统一提交所有错题”在窄屏和长文案状态下都不再换行。
- 在微信开发者工具或真机手工走一次家长上传页：选图、补框、删除框、旋转、填写文字/语音错因、统一提交。
- 在微信开发者工具或真机点一次家长首页的 `绑定更多孩子`，确认能返回绑定页且窄屏排版正常。
- 在微信开发者工具或真机点一次错题本页顶部 `查看 PDF`，确认 PDF 能正常下载和打开。
- 在微信开发者工具或真机打开一次家长错题本页，拿含公式的真实题目看一眼卡片预览，确认多行换行、长公式断行和顶部 PDF 入口组合体验都符合预期。

## 风险
- 这轮 AI 框选删除后，上传页完全依赖手动补框；如果老师或家长之前习惯用 AI，需要同步确认产品预期。
- 当前拍照自动旋正和本地 canvas 旋转链路仍未做真机全量 smoke，尤其是大图、横屏照片和连续追加图片场景。
- 上传页长文案按钮现在依赖 `width: 100% + white-space: nowrap` 保持单行，若后续再改更长文案，需要一起复查窄屏排版。
- 当前错题本页的 LaTeX 方案是纯文本可读化，不是真正数学排版；复杂矩阵、对齐公式或非常长的嵌套公式在小程序卡片里仍可能退化，精确显示仍要依赖顶部 PDF。

## 当前工作区
- 当前分支：`develop`
- 小程序相关活代码和活文档里不应再保留 `wrong-question-boxes` 或 `AI 框选` 作为当前能力描述。
