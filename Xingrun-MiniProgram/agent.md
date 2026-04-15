# Agent Workflow

## Branch Strategy

main（稳定） -> develop（日常集成） -> feature/xxx（功能开发） -> 合回 develop -> 最后进 main。

## Execution Rule

- 新功能从 develop 拉 feature 分支开发。
- 功能验证通过后先合回 develop。
- 由 develop 统一回归后再进入 main。
- main 保持可发布稳定状态。

## Cross-Repo Collaboration

- 本项目（`Xingrun-MiniProgram`）负责微信小程序前端、桥接后端（`backend/`）和微信侧上传/转发；`Xingrun-Website` 负责家长微信账号、班级邀请码、学生绑定、错题记录等 canonical 业务数据与 API。
- 两边联动开发默认走 `develop` 对 `develop`：本项目最终进 `main`，`Xingrun-Website` 最终进 `master`。小改动可各自直接进 `develop`，中高风险改动各自从 `develop` 拉 `feature/*` 再回 `develop`。
- 涉及微信家长链路时，以 `Xingrun-Website` 的 API 契约为准；本项目只做 bridge 和适配，不在本地重新定义业务主键、绑定关系或状态语义。
- 当前跨项目关键接口：`/api/wechat/login`、`/api/wechat/bind-class`、`/api/wechat/bind-student`、`/api/wechat/bindings`、`/api/wechat/wrong-questions`。
- 共享字段命名保持 website canonical 方案：`open_id`、`class_id`、`student_id`、`teacher_user_id`、`binding_id`、`source`；服务鉴权头保持 `X-Wechat-Service-Token`。
- 如果改动上述接口、字段或绑定流程，必须同步更新本项目的 `backend/src/parent-wechat-bridge.test.ts`，并在 `Xingrun-Website` 同步修改 API/测试后再联调。
- 跨项目任务结束后，两边仓库都要更新各自 `handoff.md`：本项目记录小程序/bridge 侧结论，`Xingrun-Website` 记录 API、后台或部署侧结论。
