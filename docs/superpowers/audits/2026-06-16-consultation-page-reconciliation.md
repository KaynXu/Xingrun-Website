# 咨询页面对账收纳账本

日期：2026-06-16
触发词：`咨询对账收纳`

## 核心诉求

1. 流程必须可信：一张流程图最多一个当前灯；绿灯是做过，蓝灯是当前，红灯是失败结束。
2. 历史数据不能逼老师返工：旧咨询只做展示兼容，不在打开页面时自动改库。
3. 老师操作要轻：创建少填，节点补信息要快，推荐老师不等于确认保存。
4. 当前责任要清楚：转接给谁、现在谁负责、负责到哪一步要一眼看懂。
5. 结果闭环要明确：进班、待进班、失败、Over 都要有清楚路径。
6. 页面不能变成销售 CRM：留转化分析口子，但不强迫老师填大量商业化字段。
7. 代码必须可继续施工：规则进 domain，兼容进 helper，UI 能拆就拆。
8. 每次改完都要本地预览：管理员、普通教师、转接、历史咨询按需看。

## 工程护栏

- 历史数据只读兼容，不自动清洗。
- 本地数据、临时 token、测试咨询不能当成生产事实。
- 核心业务测试优先写 pure function / API test，源码字符串测试只做补充。
- UI 收纳只拆当前需求直接相关的小块。
- 后端字段 `completed_stages`、`flow_stage`、`closing_result`、`stage_teacher_ids` 改动前必须看后端测试。
- 移动端长按、轻点、流程灯尺寸必须单独预览。
- 权限不能只靠前端 disabled，后端必须继续拦。
- 提交前排除 `data/`、`output/`、本地数据库、上传文件。
- 每个节点完成后更新本账本。
- 咨询节点二次构建不混入学管中心权限和班级排序线。

## 6月9日到6月15日大事时间线

| 日期 | 主题 | 参考提交 |
| --- | --- | --- |
| 2026-06-09 | 学管中心教师权限对齐 | `d38cb4e fix: align student center teacher permissions` |
| 2026-06-09 | 轻量咨询字段、转化接班级、流程字段 | `2b1dffb`, `86401d3`, `43c082b` |
| 2026-06-09 | 咨询卡片流程图、节点弹窗、进班弹窗、自动 Over | `3f94ef2`, `aa5e758`, `289136d`, `c5e75e2` |
| 2026-06-09 | 状态同步、卡片流程恢复、右键/长按上下文操作 | `84a1da5`, `dfa407f`, `71c3f2a` |
| 2026-06-10 | 咨询主页收回到待处理主线，移除复杂工作台 | `ee2e0b3`, `163e2d6`, `07668dc` |
| 2026-06-11 | 写入咨询流程施工图 | `90ee723` |
| 2026-06-12 至 2026-06-13 | 从 App 拆出咨询页面、批量弹窗、类型等模块 | `74d03a6`, `3239101`, `a254f68`, `dd37c55`, `3c8a2b3` |
| 2026-06-15 | 重新推进节点构建与转接 handoff | `c20e43c`, `25e4b4e` |

## 细节参考账本

| 编号 | 需求细节 | 当前状态 | 代码位置 | 测试/预览 | 后续动作 |
| --- | --- | --- | --- | --- | --- |
| R1 | 创建咨询少填：学生姓名、咨询科目、咨询年级、家长诉求、接待教师；咨询时间默认创建时间 | 已完成 | 后端：`lesson_manager.py:create_consultation`；接口：`app.py:api_consultation_create`；前端：`ConsultationModal.tsx` 的 `consultationFormDefaults`、新增记录表单、`handleSubmit` | 后端测试：`tests.test_consultation_flow.ConsultationFlowTestCase.test_consultation_create_requires_lightweight_fields` 通过；本地预览：管理员新增记录弹窗字段存在，console 无错误 | 暂不收纳。R1 代码分布合理，后续若拆 modal，可把基础信息表单抽成组件 |
| R2 | 主页结构：待咨询 / 一周内 / 一月内 / 30天+ / 已结束 / 咨询成功 / 咨询失败，默认待咨询 | 已完成 | `consultationShared.tsx:consultationFilterGroups/getConsultationFilterKey/sortConsultationsForFilter`；`ConsultationPage.tsx:activeFilter/visibleRecords/顶部筛选 UI` | Source test：`cd frontend && npx tsx --test --test-name-pattern "defaults to pending" src/consultation-flow-wiring.test.ts` 通过；本地预览：管理员咨询页顶部 7 个标签存在，默认无具体标签高亮，列表进入待咨询总览，console error 为空 | 已收纳默认列表逻辑：`activeFilter = null` 时展示全部待咨询，不再混入已结束。旧“成功进班但未咨询结束”记录仍按历史兼容留在待咨询，归 R12 处理 |
| R3 | 流程交互：左键/轻点编辑，右键/长按设当前，保存才亮，推荐老师不自动确认 | 已完成 | `ConsultationPage.tsx:handleInlineStageClick/handleInlineStageCurrent/handleSaveInlineFlowNodeDialog`；`ConsultationModal.tsx:openFlowNodeDialog/handleSaveFlowNodeDialog`；`consultationShared.tsx:ConsultationFlowNodeDialog/applyConsultationFlowNodeDraft`；`consultationTeacherSelection.ts` | Tests：`cd frontend && npx tsx --test src/consultation-flow-node-dialog.test.ts src/consultation-flow-wiring.test.ts src/domain/consultationFlow.test.ts` 通过；`cd frontend && npx tsx --test src/domain/consultationTeacherSelection.test.ts` 通过；本地预览：右键打开设当前弹窗后取消，灯状态不变，console error 为空 | 无需功能收纳。当前逻辑为：已亮节点左键会立即取消并清内容；未亮节点左键开弹窗，保存才点亮；右键/长按开设当前弹窗，保存才变蓝；推荐老师只在弹窗中预填，保存后才确认 |
| R4 | 唯一当前灯：不能双蓝；失败 Over 红灯明显 | 已完成 | `consultationShared.tsx:ConsultationFlowBar`；`consultationFlow.ts:calculateConsultationFlowLights` | Tests：`cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts src/domain/consultationFlow.test.ts` 通过；本地预览：待咨询前 8 张卡每张流程图 1 个蓝灯；咨询失败前 8 张卡每张 0 蓝 + 1 个实心红 Over；console error 为空 | 已收纳：FlowBar 统一通过 domain light 计算终点状态；旧失败结束记录做只读显示兼容，不自动改库 |
| R5 | 节点弹窗：客服、沟通、测试、试听、带课教师可选老师并保存备注 | 已完成 | 普通节点：`consultationShared.tsx:getConsultationFlowNodeDraft/applyConsultationFlowNodeDraft/clearConsultationFlowNodeContent/ConsultationFlowNodeDialog`；老师推荐：`consultationTeacherSelection.ts`；带课教师：`consultationEnterClass.ts` + 后端 `/api/consultations/<id>/enter-class` | Tests：`cd frontend && npx tsx --test src/consultation-flow-node-dialog.test.ts src/domain/consultationTeacherSelection.test.ts` 通过；后端带课教师进班测试：`python3 -m unittest tests.test_consultation_flow.ConsultationFlowTestCase.test_consultation_enter_quick_new_class_uses_structured_class_fields -v` 通过；本地预览：右键待测试节点弹窗，老师筛选/下拉/阶段备注/保存/取消存在，取消后未写业务数据 | 普通流程节点已覆盖客服、沟通教师、沟通情况、测试、试听。带课教师不作为普通流程节点处理，而是在进班三卡片/enter-class 闭环里保存到 `teaching_teacher*` 和 `stage_teacher_ids["成功进班"]`；R6/R8 继续核对进班 UI |
| R6 | 进班三卡片：已有班级、快速建班、转化待进班 | 已完成 | 前端弹窗：`ConsultationModal.tsx:ConsultationEnterClassDialog`；进班 payload/filter 规则：`consultationEnterClass.ts`；后端闭环：`/api/consultations/<id>/enter-class` | Tests：`cd frontend && npx tsx --test src/domain/consultationEnterClass.test.ts` 通过；后端三种进班测试通过：existing class / converted without class / quick new class | 编辑弹窗里的三卡片已恢复：已有班级、快速建班、转化待进班。快速建班会创建班级，后端测试确认创建后能在 `/api/classes` 找到。主页卡片直接点“成功进班”仍只提示必须先选班，未打开三卡片，归 R8 继续补 |
| R7 | 学科/年级推荐不锁死；已有班级筛选接近学员中心筛选逻辑1，下拉选择 | 已完成 | 推荐/筛选规则：`consultationEnterClass.ts:buildRecommendedConsultationClassFilters/filterConsultationEnterClassOptions`；三卡片 UI：`ConsultationEnterClassDialog.tsx:subjectFilter/stageFilter/gradeFilter/resolveConsultationAssignableClasses`；主页已有班级回填：`ConsultationPage.tsx:handleInlineEnterExistingClass` | Tests：`cd frontend && npx tsx --test src/domain/consultationEnterClass.test.ts src/consultation-enter-class-dialog.test.ts` 通过；本地预览：打开主页进班三卡片，已有班级筛选里学科/学段/年级/班级下拉均可用，学科按咨询科目推荐，年级不锁死，console error 为空 | 已接轨当前版本。学科作为推荐值预填但可改；年级/学段保持可调整；选择已有班级后用所选班级科目/年级回填，避免咨询填 6 年级但实际进 7/8 年级时被锁死 |
| R8 | Over：手动先问成功/失败；成功走进班；失败红；成功进班自动 Over | 已完成 | 主页入口：`ConsultationPage.tsx:handleInlineResultChange/handleInlineResultClick/handleInlineOverSuccess/ConsultationEnterClassDialog`；共享弹窗：`ConsultationModal.tsx:ConsultationEnterClassDialog`；业务 payload：`consultationEnterClass.ts:buildConsultationEnterClassPayload`；后端闭环：`/api/consultations/<id>/enter-class` | Frontend：`cd frontend && npx tsx --test src/consultation-enter-class-dialog.test.ts src/domain/consultationEnterClass.test.ts src/consultation-flow-wiring.test.ts` 通过；Backend：existing class / converted without class / quick new class 三条 unittest 通过；本地预览：主页点可见进班入口出现三卡片，旧错误不出现，console error 为空 | 已补主页闭环。直接点成功进班或 Over 成功时，如未选班级，打开已有班级 / 快速建班 / 转化待进班三卡片；三种确认均走 `enter-class` 业务接口 |
| R9 | 转接替代推送：教师看到自建 + 转接咨询，卡片标咨询转接和当前责任 | 已完成 | 后端可见性：`lesson_manager.py:list_consultations_for_actor/_consultation_assignment_context_for_actor/_annotate_consultation_for_actor`；后端编辑限制：`lesson_manager.py:update_consultation_for_actor/_transferred_consultation_update_touches_prior_stage`；前端卡片：`ConsultationPage.tsx:getConsultationTransferBadge/canEditConsultationRecord/canEditConsultationStage`；前端守护：`consultation-transfer-scope.test.ts` | Frontend：`cd frontend && npx tsx --test src/consultation-transfer-scope.test.ts` 通过；Backend：自建可见、自建不标转接、转接标记/备注、企微别名转接、当前阶段编辑、前任可见不可编辑、同阶段转交等测试通过；本地预览：何姝健账号能看到自建/转接咨询，卡片有 `咨询转接` 和当前责任，console error 为空 | 已接轨。这里仍是“替代推送”：没有真实消息通知，但被选择为对应阶段老师后，该老师账号的咨询中心可见；转接卡片用浅黄色背景和 `咨询转接` 标记区分 |
| R10 | 查看/编辑阶段状态卡：`xx教师：x老师 ✓`、`客服微信：已添加 ✓` | 已完成 | 状态卡组件：`ConsultationStageStatusCards.tsx`；查看态接入：`ConsultationModal.tsx:ConsultationReadOnlyReport`；编辑态接入：`ConsultationModal.tsx` 基础信息/沟通与测试/试听/结果四区块；守护测试：`consultation-stage-status-cards.test.ts` | Tests：`cd frontend && npx tsx --test src/consultation-stage-status-cards.test.ts src/consultation-flow-node-dialog.test.ts src/consultation-enter-class-dialog.test.ts src/consultation-flow-wiring.test.ts` 通过；本地预览：查看弹窗和编辑弹窗均出现 `客服微信/客服老师/接待教师/沟通教师/测试教师/试听教师/带课教师/进班班级` 状态卡，console error 为空 | 已接轨。状态卡只做展示，不改变原输入控件和保存逻辑；后续若继续瘦身 Modal，可把 read-only report 或编辑分区继续拆出 |
| R11 | 使用提醒按设备显示：桌面左键/右键，Pad/手机轻点/长按 | 已完成 | `ConsultationPage.tsx` 顶部使用提醒；守护测试：`consultation-flow-wiring.test.ts` | Tests：`cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts src/consultation-stage-status-cards.test.ts` 通过；本地预览：1440px 桌面只显示 `左键编辑阶段状态，右键标记为当前阶段`；390px 手机只显示 `轻点编辑阶段状态，长按标记为当前阶段`；console error 为空 | 已接轨。采用响应式 CSS，不额外加 JS 设备状态 |
| R12 | 历史数据兼容：旧咨询不要求重改，展示自动解释，保存后规范写回 | 已完成 | 前端流程兼容：`consultationFlow.ts:createConsultationFlowState/calculateConsultationFlowLights`、`consultationShared.ts:ConsultationFlowBar/normalizeConsultationRecord`；后端旧状态映射：`lesson_manager.py:_normalize_consultation_flow_stage/_normalize_consultation_completed_stages/_serialize_consultation_row`；保存规范化：`lesson_manager.py:update_consultation` | Frontend：`cd frontend && npx tsx --test src/domain/consultationFlow.test.ts src/consultation-flow-wiring.test.ts` 通过；Backend：legacy follow-up 映射、legacy terminal 不补 ended_at、terminal ended_at 只记录一次三条 unittest 通过 | 已接轨。页面加载只做展示兼容，不自动清洗旧记录；用户保存/结束咨询时才按新字段规范写回 |

## 代码体量账本

| 文件 | 2026-06-16 行数 | 红线 | 判断 |
| --- | ---: | ---: | --- |
| `frontend/src/features/consultation/ConsultationModal.tsx` | 1545 | 1500 | 仍略超线，但已把进班三卡片和状态卡本体拆出，后续可继续拆 read-only report / edit sections |
| `frontend/src/features/consultation/ConsultationEnterClassDialog.tsx` | 227 | 800 | 新拆出的进班三卡片组件，体量健康 |
| `frontend/src/features/consultation/ConsultationStageStatusCards.tsx` | 83 | 500 | 新拆出的阶段状态卡组件，体量健康 |
| `frontend/src/features/consultation/consultationShared.tsx` | 1159 | 1000 | 超线，规则/helper/UI 需要继续分家 |
| `frontend/src/features/consultation/ConsultationPage.tsx` | 1047 | 1200 | 接近复杂区，新增弹窗前优先抽组件 |
| `frontend/src/domain/consultationFlow.ts` | 222 | 800 | 健康，流程规则优先放这里 |
| `tests/test_consultation_flow.py` | 1913 | 3000 | 可接受，后端咨询规则继续覆盖这里 |

## Git 基线

| 时间 | 命令 | 结果 | 判断 |
| --- | --- | --- | --- |
| 2026-06-16 | `git fetch origin develop` | 成功 | 可读取远端 `develop` 当前引用 |
| 2026-06-16 | `git rev-list --left-right --count HEAD...origin/develop` | `26 0` | 本地超前 26 个提交，当前不落后远端 |
| 2026-06-16 | `git status --short` | 多个咨询源文件/测试/文档已修改，且存在 `data/`、`output/` 未跟踪文件 | 后续提交必须只 add 源码、测试、文档，排除本地数据和输出文件 |
| 2026-06-17 | `git fetch origin develop` | 失败：连接 `github.com:443` 超时 75 秒 | 当前不能确认远端 ahead/behind，也不能安全 push；等网络恢复后先 fetch 再决定 pull/push |

## 收口验证

| 时间 | 命令 | 结果 | 判断 |
| --- | --- | --- | --- |
| 2026-06-17 | `cd frontend && npx tsx --test ...consultation...` | 前端咨询相关测试 `48/48 pass` | 咨询流程、进班、转接、状态卡、设备提醒、历史兼容相关守护通过 |
| 2026-06-17 | `python3 -m unittest ...10 tests...` | 后端咨询关键测试 `10/10 pass` | 创建、进班、转接、历史兼容关键路径通过 |
| 2026-06-17 | `cd frontend && npm run build` | Vite build 成功；仅有大包和动态/静态混用 warning | 可以本地构建。warning 非本轮新增阻断项 |
| 2026-06-17 | `git diff --check` | 无输出 | 当前 diff 无空白错误 |

## 风险账本

| 风险 | 当前判断 | 应对 |
| --- | --- | --- |
| 双蓝灯 | 已修复 | FlowBar 统一通过 domain light 计算终点状态；source test 覆盖 |
| 失败 Over 不明显 | 已修复 | 失败 Over 改为实心红灯并显示 `!`；旧失败结束记录只读兼容 |
| 主页 Over 成功不进三卡片 | 已发现 | 抽共享 enter-class dialog 或在页面接入同一闭环 |
| `ConsultationModal.tsx` 继续膨胀 | 高风险 | 新大块 UI 拆文件 |
| `consultationShared.tsx` 职责混杂 | 高风险 | 规则/helper/UI 分批拆出 |
| 远端同步不稳定 | 中风险 | 大节点前 fetch；不在大量未提交改动下硬 pull |
| 本地数据混入提交 | 高风险 | 提交前只 add 源码、测试、文档 |

## 本地预览记录

| 节点 | 视角 | 预览内容 | 结果 |
| --- | --- | --- | --- |
| 初始审计 | 管理员 | 咨询主页、流程灯、Over 弹窗 | 已由 R2/R4/R8/R10/R11 分项预览覆盖 |
| 初始审计 | 何姝健 | 自建/转接咨询、咨询转接标记、当前责任 | 已由 R9 分项预览覆盖 |
| R1 | 管理员 | 打开新增记录弹窗，检查快速录入、日期、孩子姓名、年级、咨询科目、负责老师、沟通ing/家长诉求、来源字段 | 通过。页面能打开；字段存在；来源为可选字段；console error 为空；未提交表单，未写业务数据 |
| R2 | 管理员 | 打开咨询主页，检查顶部 `待咨询 / 一周内 / 一月内 / 30天+ / 已结束 / 咨询成功 / 咨询失败`，默认态不选具体标签 | 通过。7 个标签存在；默认态为待咨询总览；console error 为空；未提交表单，未写业务数据 |
| R3 | 管理员 | 咨询主页流程节点交互：右键节点打开设当前弹窗后取消 | 通过。弹窗包含后续阶段清空提示、阶段备注、保存/取消；取消后流程灯状态不变；console error 为空。预览时误点一次已绿节点，已用本地 API 恢复 id=2 的客服节点 |
| R4 | 管理员 | 咨询主页流程灯；切换到咨询失败分类检查 Over 红灯 | 通过。待咨询抽样每张卡仅 1 个蓝灯；咨询失败抽样每张卡 1 个实心红 Over 且无蓝灯；console error 为空 |
| R5 | 管理员 | 咨询主页右键待测试节点，检查节点弹窗字段 | 通过。弹窗提供老师筛选、老师下拉、阶段备注、保存/取消；取消后未写业务数据；console error 为空 |
| R6 | 管理员 | 尝试从咨询主页进入进班三卡片 | 部分预览。源码和测试确认编辑弹窗三卡片存在；主页卡片直接点“进班/成功进班”仍显示“成功进班必须先选择或填写班级”，未打开三卡片。该入口归 R8 补 |
| R7 | 管理员 | 打开主页进班三卡片，检查已有班级筛选 | 通过。三卡片可见；已有班级区域的学科/学段/年级/班级下拉均 enabled；学科按咨询科目推荐到 `数学`；年级为可调整的 `全部`；console error 为空 |
| R8 | 管理员 | 咨询主页直接点可见的进班 / 成功进班入口 | 通过。主页能打开；顶部 7 个标签存在；可见进班入口数量 35；点击后出现 `已有班级 / 快速建班 / 转化待进班` 三卡片；旧错误 `必须先选择或填写班级` 不出现；console error 为空 |
| R9 | 何姝健 | 以何姝健本地 session 打开咨询页，检查自建/转接可见性和卡片标记 | 通过。咨询页可打开；能看到 `咨询转接`；能看到 `带课教师：何姝健`、`试听教师：何姝健`、`测试教师：何姝健` 等当前责任；转接预览卡片存在；console error 为空 |
| R10 | 管理员 | 打开咨询查看弹窗和编辑弹窗，检查阶段状态卡 | 通过。查看态和编辑态均可见 `客服微信：`、`客服老师：`、`接待教师：`、`沟通教师：`、`测试教师：`、`试听教师：`、`带课教师：`、`进班班级：`；未保存任何表单；console error 为空 |
| R11 | 管理员 | 分别用桌面宽度和手机宽度打开咨询主页，检查使用提醒 | 通过。1440px 只显示电脑端 `左键/右键` 提醒；390px 只显示移动端 `轻点/长按` 提醒；两端 console error 均为空 |
| R12 | 自动化兼容检查 | 旧咨询/旧终态兼容测试 | 通过。旧 `跟进状态=已报班` 映射到新流程展示但不点亮未知步骤；旧终态缺 `ended_at` 的 GET 保持空；真实结束只记录一次 `ended_at` |

## 已完成收纳记录

| 节点 | 收纳动作 | 结果 |
| --- | --- | --- |
| Task 0 | 建立总计划、工程护栏、代码红线、Git 基线 | 已完成。未改功能代码 |
| R1 | 对账创建咨询少填字段 | 无需功能收纳；记录为已完成，后续拆 modal 时可抽基础信息表单 |
| R2 | 对账咨询主页筛选结构和默认列表 | 小收纳完成：默认未选具体筛选时只展示待咨询记录。未改变顶部视觉结构 |
| R3 | 对账流程节点左键/右键/长按和推荐老师规则 | 无需功能收纳；测试和预览已确认当前逻辑符合施工图 |
| R4 | 对账并修复唯一当前灯和失败 Over 显示 | 小收纳完成：结果/Over 统一走 domain 灯色，规避 result + over 双蓝；失败 Over 改为实心红并显示 `!` |
| R5 | 对账普通节点弹窗字段映射和老师推荐 | 无需功能收纳；普通节点映射已对齐。带课教师进入 R6/R8 的进班闭环继续核对 |
| R6 | 对账进班三卡片和快速建班闭环 | 小收纳完成：把旧 `App.tsx` source test 迁移到 `ConsultationModal.tsx`/domain 新结构；后端确认快速建班后班级可查 |
| R7 | 对账已有班级筛选推荐逻辑 | 无需功能收纳；当前组件已做到学科推荐但不锁死，年级/学段可自由调整，选择已有班级时以后选班级信息回填 |
| R8 | 补齐主页 Over / 成功进班闭环 | 小收纳完成：主页复用 `ConsultationEnterClassDialog`，三种进班确认统一走 `/enter-class` API；不再在主页直接报“必须先选择或填写班级” |
| R8 收纳 | 拆出进班三卡片组件 | 小收纳完成：`ConsultationEnterClassDialog` 从 `ConsultationModal.tsx` 拆到独立文件；Modal 从 1753 行降到 1536 行；主页和编辑弹窗共用同一个组件 |
| R9 | 对账转接替代推送 | 无需功能收纳；后端已按自建 + 转接过滤普通教师可见咨询，前端已显示转接背景、标记、当前责任和备注；真实消息推送继续延后 |
| R10 | 补齐查看/编辑阶段状态卡 | 小收纳完成：新增 `ConsultationStageStatusCards.tsx`，查看态和编辑态共用同一套状态展示；Modal 仅增加调用点，不承载状态卡内部逻辑 |
| R11 | 设备化使用提醒 | 小收纳完成：咨询主页提醒拆成桌面版和移动版两段响应式文本，避免同时提示电脑和 Pad/手机操作 |
| R12 | 历史数据兼容对账 | 无需功能收纳；现有前后端兼容和测试已覆盖，不做自动迁移、不要求老师返工 |
