## Handoff

最后更新：2026-04-15

### 当前状态
- `develop` 现已纳入一个并置子目录 `Xingrun-MiniProgram/`，内容来自 `/Users/ark.mini/Desktop/Xingrun-MiniProgram` 当时的当前工作区快照。
- 这次复制带入了小程序仓库当时未提交的业务改动，但没有带入源仓库的 `.git`、`.worktrees`、`.venv`、`data/`、`uploads/` 等 git 内部或运行时目录。
- 网站主应用仍然是现有的 Flask + React 同仓结构；`Xingrun-MiniProgram/` 目前只是为了联动开发和 AI 协作方便而并置进来，还没有改造成统一构建、统一部署或自动同步。
- `develop` 已包含 `parent voice` 相关改动：微信错题已统一到 `知识点问题 / 细节问题 / 方法问题 / 审题问题` 四类口径。
- 微信端错题链路当前分成三步：转写 `reason-transcriptions`、分类 `reason-classifications`、落库 `wrong-questions`；上传接口现在要求 caller 传 finalized 的 `primary_error_type` 和 `secondary_error_summary`。
- 智能错题老师侧页面文案已同步收口成 `问题归类 / 补充备注 / 最终问题归类`。
- `课堂反馈` 页头已改成全宽双栏布局：页面不再额外收窄到 `max-w-7xl`，左侧保留筛选和状态信息，右侧独立竖栏上方显示 `当前周期`，下方固定任务按钮；桌面端 4 个筛选框已统一成等宽窄尺寸。
- 咨询记录页当前保持 2026-04-14 的收口结果：`AI 批量整理` 只允许 `待邀约 / 跟进中 / 已报班 / 已劝退`，页面展示口径为 `咨询详情` + `跟进`，桌面端 `年级` 列已固定单行，并且桌面表格各列已统一顶对齐。
- 发布流程仍以 `docs/deploy-release.md` 为准；生产环境目前还没有这轮 `parent voice` 改动。

### 已完成
- 已将 `Xingrun-MiniProgram` 当前工作区快照直接复制进 `Xingrun-Website/Xingrun-MiniProgram/`。
- 复制范围是源仓库里所有已跟踪文件和未忽略的本地文件；校验结果为 `source_count = 72`、`copied_count = 72`，逐文件内容一致。
- `parent voice` 相关网站改动已经收进 `develop`。
- `课堂反馈` 页头布局已进一步收口：header 已拆成 `左内容 + 右侧竖栏`，`当前周期` 固定在右上角、任务按钮固定在右下角；桌面端 `班级 / 粒度 / 年份 / 阶段` 4 个筛选框已统一等宽，并补了对应前端测试。
- 交接摘要已改回只保留当前有效信息，不再记录过程细节。

### 剩余问题
- 这是一次直接复制，不带自动同步；后续如果两边都继续改，源码会自然漂移。
- 网站的 README、部署脚本和本地开发脚本还没有接管 `Xingrun-MiniProgram/` 的启动、验证或发布流程。
- `parent voice` 还缺一次真实跨服务 smoke，确认语音转写、文本分类和 finalized 上传在真实链路里一致。
- `课堂反馈` 还缺一次真实页面人工检查，确认 1440px 以上宽屏下新的右侧竖栏比例、按钮落位，以及 4 个等宽筛选框的视觉密度符合预期。
- 咨询记录页还缺一次真实页面人工检查，确认长文本不会重新挤坏桌面端布局。

### 下一步
- 如果只是为了方便在 `website` 仓库里联动开发，现在可以直接在 `Xingrun-MiniProgram/` 下改代码。
- 如果希望把这里的改动反写回原始 `Xingrun-MiniProgram` 仓库，下一轮需要单独定义“回写/再同步”流程。
- 如果继续收 `parent voice`，先做一次真实 `文本 + 语音` 上传 smoke。
- 如果准备发版，直接按 `docs/deploy-release.md` 走 `develop -> master -> 部署`。
- 如果继续收咨询记录，优先检查真实页面里的 `咨询详情 / 跟进 / 年级` 布局表现。

### 风险
- 当前 `Xingrun-MiniProgram/` 是工作区快照，不是 git 子模块也不是 subtree；如果继续双边开发，最主要风险就是双份真相源。
- 这次复制包含了小程序仓库当时未提交的 WIP，后续如果源仓库又单独提交了不同版本，容易出现“website 里这份更像真相”的错觉。
- 旧 caller 如果还只传 `child_raw_reason_text`、不传 finalized 分类字段，`POST /api/wechat/wrong-questions` 会直接失败。
- `wechat_mp` 和 `downstream` 仍是双来源模型，不能误判成已经完全统一的一套后端契约。
- 常规 `/api/consultations` 的 create/update 仍没有在后端对白名单 `follow_up_status` 做硬校验。
- 错误类型下拉仍是“固定四类 + 兼容历史 legacy 值”的过渡态。
- 前端 `npm run lint` 目前仍有 `smart-wrong-questions` 相关基线报错，和本轮 `课堂反馈` 布局改动无关。

### 当前工作区状态
- 当前分支：`develop`
- 本地 `develop` 尚未 push。
- 当前工作区应在迁移提交合入后保持干净，不保留运行时数据库、`__pycache__` 或临时验证文件。
