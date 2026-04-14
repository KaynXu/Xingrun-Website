## Handoff

最后更新：2026-04-14

### 当前状态
- `develop` 已收进 `parent voice` 这条链路：
  - 后端新增 `POST /api/wechat/reason-transcriptions`
  - `POST /api/wechat/wrong-questions` 现在直接落 caller 提供的 finalized `primary_error_type` / `secondary_error_summary`，不再在创建时重复重分类
  - `POST /api/wechat/reason-classifications` 仍保留，用于把孩子自述整理成四类问题和补充备注
  - 微信错题顶层问题口径统一为 `知识点问题 / 细节问题 / 方法问题 / 审题问题`
  - `SmartWrongQuestionsPage` 老师侧文案已同步收口成 `问题归类 / 补充备注 / 最终问题归类`
- 咨询记录这条链路仍保持 2026-04-14 的收口结果：
  - `AI 批量整理` 只允许 `待邀约 / 跟进中 / 已报班 / 已劝退`
  - 咨询记录页已改成 `咨询详情` + `跟进` 展示方案
  - 桌面端 `年级` 列已固定单行并收紧与“咨询老师”列之间的间距
- 发布流程权威文档仍是 `docs/deploy-release.md`。
- 生产环境最新已部署提交仍是 `5ff8adb Merge branch 'develop'`；本轮 `parent voice` 合并还没有发版。

### 已完成
- `feature/parent-voice-reason-website` 已 rebase 到最新 `develop` 并合入主线。
- 相关 worktree 和 feature branch 已删除，没有继续占用工作区。
- 本轮在 `develop` 已重新验证通过：
  - `/Users/ark.mini/Desktop/Xingrun-Website/.venv/bin/python -m unittest tests.test_wechat_parent_upload_api -v`
  - `cd frontend && npm test -- src/smart-wrong-questions.test.ts`

### 剩余问题
- 这条 `parent voice` 新链路还缺一次真实跨服务 smoke：
  - 语音转写
  - 文本分类
  - finalized 字段上传
  - Website 侧落库查看
- 咨询记录页目前主要是测试和源码断言通过，仍值得再用真实数据做一次桌面端 / 移动端人工检查。

### 下一步
- 如果要继续收 `parent voice`，优先做一次真实 `文本 + 语音` 上传 smoke，确认旧 caller 不会误走到新契约。
- 如果要发版，直接按 `docs/deploy-release.md` 走 `develop -> master -> 部署`，不要现场重猜流程。
- 如果继续咨询记录这一项，优先做一次真实页面手工检查，确认 `咨询详情 / 跟进 / 年级` 的布局节奏没有被长文本重新挤坏。

### 风险
- `POST /api/wechat/wrong-questions` 现在依赖 caller 先拿到 finalized `primary_error_type` / `secondary_error_summary`；旧 caller 如果还只传 `child_raw_reason_text`，会直接失败。
- `wechat_mp` 和 `downstream` 仍是双来源双语义模型，不能把它们误当成已经完全统一的一套后端契约。
- 咨询常规 `/api/consultations` create/update 仍没有在后端对白名单 `follow_up_status` 做硬校验，目前主要依赖前端下拉约束。
- 当前错误类型下拉仍是“固定四类 + 兼容历史 legacy 值”的过渡态，后续继续收口时要防止把旧值误写回主流程。

### 当前工作区状态
- 当前分支：`develop`
- `develop` 已包含 `parent voice` 两条功能提交，尚未 push。
- 工作区应保持干净；不要把运行时数据库、`__pycache__` 或临时验证文件带进后续提交。
