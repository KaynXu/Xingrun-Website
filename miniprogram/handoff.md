# Handoff

最后更新：2026-04-16

这份文件只保留当前仍然有效的状态、下一步、风险和工作区信息，不再追加历史流水。

## 当前状态
- 小程序子项目根目录是 `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram`，微信工程代码位于 `miniprogram/miniprogram/`，bridge 位于 `miniprogram/backend/`。
- 家长链路当前只保留 `绑定孩子 -> 家长首页 -> 上传错题 -> 查看错题本/PDF`。
- 家长首页绑定态已恢复 `绑定更多孩子` 入口，继续复用 `goBindMore()` 返回 `pages/parent-bind/index`。
- 家长错题本页已恢复学生级 `查看 PDF`，bridge 仍保留 `GET /wechat/parent/children/:studentId/wrong-question-library`。
- 家长上传页当前是手动补框模式：`补加框 / 删除当前 / 顺时针旋转`，每个题框单独填写文字或语音错因，再统一提交。
- `AI 框选` 已从小程序页面、`parentApi.js`、bridge、website API 和 `smart_wrong_questions.py` 活代码里删除；`POST /wechat/parent/wrong-question-boxes` 与 `/api/wechat/wrong-question-boxes` 已不再是当前能力。

## 本轮完成
- 删除小程序上传页里的 `AI 框选` 按钮、缩略图状态点、AI 状态文案和相关前端 helper。
- 删除 `miniprogram/backend/src/index.ts` 与 `website-client.ts` 里的 `wrong-question-boxes` bridge 链路。
- 删除 website 侧 `app.py` 和 `smart_wrong_questions.py` 里的 `wrong-question-boxes` 活接口与实现。
- 回归测试已改成“AI 框选不存在”的口径，活文档 `README.md`、`CLOUD_HOSTING_SETUP.md` 与本 handoff 已同步清理。

## 剩余问题
- 这轮删除目前主要用本地自动测试验证过，还没有在微信开发者工具或真机上完整手工走一遍“选图 -> 手动补框 -> 填错因 -> 提交”。
- 错题本页 `查看 PDF` 入口虽然已有自动测试覆盖，但还需要真机再点一次确认 `wx.downloadFile + wx.openDocument` 运行时行为。

## 下一步
- 在微信开发者工具或真机手工走一次家长上传页：选图、补框、删除框、旋转、填写文字/语音错因、统一提交。
- 在微信开发者工具或真机点一次家长首页的 `绑定更多孩子`，确认能返回绑定页且窄屏排版正常。
- 在微信开发者工具或真机点一次错题本页顶部 `查看 PDF`，确认 PDF 能正常下载和打开。

## 风险
- 这轮 AI 框选删除后，上传页完全依赖手动补框；如果老师或家长之前习惯用 AI，需要同步确认产品预期。
- 当前拍照自动旋正和本地 canvas 旋转链路仍未做真机全量 smoke，尤其是大图、横屏照片和连续追加图片场景。

## 当前工作区
- 当前分支：`develop`
- 小程序相关活代码和活文档里不应再保留 `wrong-question-boxes` 或 `AI 框选` 作为当前能力描述。
