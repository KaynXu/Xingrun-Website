## Handoff

最后更新：2026-04-14

### 当前状态
- `develop` 已包含 `parent voice` 相关改动：微信错题已统一到 `知识点问题 / 细节问题 / 方法问题 / 审题问题` 四类口径。
- 微信端错题链路当前分成三步：转写 `reason-transcriptions`、分类 `reason-classifications`、落库 `wrong-questions`；上传接口现在要求 caller 传 finalized 的 `primary_error_type` 和 `secondary_error_summary`。
- 智能错题老师侧页面文案已同步收口成 `问题归类 / 补充备注 / 最终问题归类`。
- `课堂反馈` 页头已改成全宽布局：页面不再额外收窄到 `max-w-7xl`，控制栏改成 `筛选区 / 当前周期 / 操作按钮` 三段式桌面布局。
- 咨询记录页当前保持 2026-04-14 的收口结果：`AI 批量整理` 只允许 `待邀约 / 跟进中 / 已报班 / 已劝退`，页面展示口径为 `咨询详情` + `跟进`，桌面端 `年级` 列已固定单行，并且桌面表格各列已统一顶对齐。
- 发布流程仍以 `docs/deploy-release.md` 为准；生产环境目前还没有这轮 `parent voice` 改动。

### 已完成
- `parent voice` 相关网站改动已经收进 `develop`。
- `课堂反馈` 页头布局已收口：筛选控件比例、当前周期卡片和任务按钮的桌面端分布已重新平衡，并补了对应前端测试。
- 交接摘要已改回只保留当前有效信息，不再记录过程细节。

### 剩余问题
- `parent voice` 还缺一次真实跨服务 smoke，确认语音转写、文本分类和 finalized 上传在真实链路里一致。
- `课堂反馈` 还缺一次真实页面人工检查，确认 1440px 以上宽屏下新的三段式页头视觉比例符合预期。
- 咨询记录页还缺一次真实页面人工检查，确认长文本不会重新挤坏桌面端布局。

### 下一步
- 如果继续收 `parent voice`，先做一次真实 `文本 + 语音` 上传 smoke。
- 如果准备发版，直接按 `docs/deploy-release.md` 走 `develop -> master -> 部署`。
- 如果继续收咨询记录，优先检查真实页面里的 `咨询详情 / 跟进 / 年级` 布局表现。

### 风险
- 旧 caller 如果还只传 `child_raw_reason_text`、不传 finalized 分类字段，`POST /api/wechat/wrong-questions` 会直接失败。
- `wechat_mp` 和 `downstream` 仍是双来源模型，不能误判成已经完全统一的一套后端契约。
- 常规 `/api/consultations` 的 create/update 仍没有在后端对白名单 `follow_up_status` 做硬校验。
- 错误类型下拉仍是“固定四类 + 兼容历史 legacy 值”的过渡态。
- 前端 `npm run lint` 目前仍有 `smart-wrong-questions` 相关基线报错，和本轮 `课堂反馈` 布局改动无关。

### 当前工作区状态
- 当前分支：`develop`
- 本地 `develop` 尚未 push。
- 工作区应保持干净，不保留运行时数据库、`__pycache__` 或临时验证文件。
