# Ricardo 治理路线

这个文件是网站治理工作的接力存档点。上下文中断、手动压缩、隔几天回来，或者换人继续时，先读这个文件。

## 唤醒口令

```text
继续 Ricardo 治理路线
```

听到这个口令后，先读取：

- `docs/refactor-roadmap.md`
- `docs/technical-debt.md`
- `docs/ricardo-components/USAGE_RULES.md`

然后先汇报当前进度、下一步计划和风险。除非 Ricardo 明确说“开始第 X 步”或“继续执行”，否则只停在汇报和对齐，不进入核心代码修改。

## 当前目标

治理网站代码结构，防止技术债继续堆积。原则是先立规矩，再抽业务规则，再拆页面，不做一次性大爆炸重构。

大前提：这个治理计划的目的，是持续解决代码里的脏乱问题，包括重复逻辑、业务规则散落、权限和展示混杂、页面文件过大、测试脆弱、后续容易误伤等。治理不是为了追求表面结构好看，而是为了让以后每次改需求更稳、更清楚、更不容易把旧功能改坏。

## 执行原则

- 每次继续治理路线时，先确认当前处于第几步。
- 文档治理、组件入库、业务规则抽取、页面拆分要分开做。
- 没有明确确认时，不提前进入下一步核心代码。
- 如果发现路线图状态和 Ricardo 的当前意图不一致，先更新路线图，不继续实现。
- 每一步完成后，要在本文件和 `docs/technical-debt.md` 中同步状态。
- 每次进入代码修改前，先估算当前上下文是否够完成一个可验证的小步骤；如果不够，先提醒 Ricardo 手动压缩上下文，不硬拆、不硬续。
- 如果上下文够用，也只做一个小步骤，完成后同步文档并验证，避免连续多刀导致接力不清。

## 分支抽屉规则

分支和 worktree 也属于治理范围。它们的目标不是越多越细，而是让每个改动知道自己属于哪个抽屉，避免几条 AI 线同时改同一片业务后互相覆盖。

权威硬规则见项目根目录 `AGENTS.md` 的 `Branch And Contribution Strategy` 和 `Multi-AI Branch Workflow`。本节只保留 Ricardo 接力时最容易用到的口径：

- `master`：主发布分支，只能由 `develop` 手动合入；不要直接在这里做功能开发。
- `develop`：默认集成分支，小改动可以在这里做，中型和大型改动完成后也先回到这里。
- `work/<任务名>`：短期工作分支，用来承载一个明确任务；任务完成、合入并验证后，应及时删除。
- `backup/<来源和时间>`：备份分支，只用于保留某个重要操作前的状态；不在上面继续开发。
- `integrate/<任务名>` 或 `release/<任务名>`：临时集成或发布分支，只在合并、移植、发布窗口使用；结束后应清理。

当前本地分支归类：

- `master`：主发布分支。
- `develop`：默认集成分支。
- `backup/develop-before-consultation-merge-20260522164356`：备份分支，命名合理。
- `work/consultation-card-info-layout`：工作分支，命名合理。
- `work/consultation-meeting-followup`：工作分支，命名合理；当前被另一个 worktree 占用，处理前要先确认对应 worktree 状态。

后续如果出现散落分支，优先按用途改名或归档，不先删。只有确认已合入、无未保存工作、Ricardo 明确同意后，才删除分支或移除 worktree。

## 总路线

1. 建技术债账本和 Ricardo 组件库章程。
2. 抽班级命名规则到统一领域文件。
3. 在学管中心建立权限判断层。
4. 拆学管中心页面。
5. 逐步升级测试方式。

## 当前进度

已完成：

- Ricardo 组件库初版已建立。
- `RCF-001` 浮层标签筛选器已入库。
- `RCF-002` 总览浮层筛选器已入库。
- 学管中心筛选 UI 已抽为 `FloatingFilterBar` 和 `FloatingOverviewFilter`。
- Ricardo Component Lab 初版已建立，可查看筛选组件使用效果。
- 本文件、技术债账本和组件库使用章程已建立。
- 第 1 步治理文档已完成。
- 第 2 步阶段完成：班级命名、年级、学段、入学年份规则已抽到 `frontend/src/domain/classNaming.ts`，并接入学管中心、课程日历、咨询页当前班级选择、班级认领、反馈页和账号审批负责班级摘要等当前正式班级展示位置。
- 第 3 步第一小步已完成：学管中心权限判断层已建立到 `frontend/src/features/student-center/permissions.ts`，并接入学管中心最集中的权限判断。
- 第 4 步第一小步已完成：学管中心外壳页已从 `frontend/src/App.tsx` 抽到 `frontend/src/features/student-center/StudentCenterPage.tsx`，公共工作台样式和 API 小工具已抽到 `frontend/src/workspaceShared.ts`，学管中心局部类型和表单工具已放入 `frontend/src/features/student-center/model.ts`。
- 第 4 步第二小步已完成：校区总览展示组件已抽到 `frontend/src/features/student-center/CampusOverview.tsx`，筛选计算和状态暂时仍留在 `StudentCenterPage.tsx`。
- 第 4 步第三小步已完成：班级管理展示组件已抽到 `frontend/src/features/student-center/ClassManagementTab.tsx`，班级筛选计算、数据加载、编辑弹窗和保存逻辑暂时仍留在 `StudentCenterPage.tsx`。
- 第 4 步第四小步已完成：学员管理展示组件已抽到 `frontend/src/features/student-center/StudentManagementTab.tsx`，学员筛选计算和姓名查询状态暂时仍留在 `StudentCenterPage.tsx`。
- 第 4 步第五小步已完成：班级编辑弹窗展示组件已抽到 `frontend/src/features/student-center/ClassEditorModal.tsx`，但新建、保存、删除、老师绑定、邀请码、学生编辑等业务逻辑仍留在 `StudentCenterPage.tsx`。
- 第 4 步第六小步已完成：`ClassEditorModal` 的传参已按 `mode / locks / errors / options / newClass / editing / actions` 分组，降低父页面和弹窗之间的散乱参数，但业务逻辑仍由 `StudentCenterPage.tsx` 管理。
- 第 4 步第七小步已完成：已补充学管中心剩余职责地图，并新增 `useClassEditorModalActions.ts`，先把弹窗 action 组装从 JSX 中移出。核心保存、删除、老师绑定、邀请码、学生维护业务处理暂时仍在 `StudentCenterPage.tsx`。
- 第 4 步第八小步已完成：新增 `classSaveRules.ts` 和 `classSaveRules.test.ts`，先把班级保存的 payload 生成、保存请求、保存提示文案、新建后的乐观班级项、本地班级列表、老师绑定表和表单缓存乐观更新、保存前校验和重复班级判断从 `StudentCenterPage.tsx` 抽为可测试规则。API 保存流程主体、老师绑定、刷新和 UI 暂时仍在 `StudentCenterPage.tsx`。
- 第 4 步第九小步已完成：新增 `classDeleteRules.ts` 和 `classDeleteRules.test.ts`，先把班级删除确认文案、删除请求、删除失败文案、删除后弹窗关闭规则和删除成功后的本地缓存清理规则从 `StudentCenterPage.tsx` 抽为可测试规则。实际 API 删除流程仍在 `StudentCenterPage.tsx`。
- 第 4 步第十小步已完成：新增 `teacherBindingRules.ts` 和 `teacherBindingRules.test.ts`，把负责老师绑定的旧状态快照、请求 endpoint/payload、绑定中状态、提示文案、乐观更新和失败回滚规则下沉到学管中心领域文件，并由 `App.tsx` re-export 兼容旧入口。实际老师绑定异步流程仍在 `StudentCenterPage.tsx`。
- 第 4 步第十一小步已完成：新增 `loadPageRules.ts` 和 `loadPageRules.test.ts`，把页面刷新后的老师绑定 key 规范化、班级表单缓存重建和展开班级选择规则从 `StudentCenterPage.tsx` 抽为可测试规则。实际 API 加载流程仍在 `StudentCenterPage.tsx`。
- 第 4 步第十二小步已完成：继续扩展 `loadPageRules.ts` 和 `loadPageRules.test.ts`，把页面刷新失败时的错误归一、表单缓存重置、新建班级负责老师重置和展开班级重置规则从 `StudentCenterPage.tsx` 抽为可测试规则。实际 API 加载流程仍在 `StudentCenterPage.tsx`。
- 第 4 步第十三小步已完成：继续扩展 `classDeleteRules.ts` 和 `classDeleteRules.test.ts`，把班级删除请求执行动作下沉为 `executeClassDeleteRequest`，页面不再直接拼装删除请求和调用 `apiFetch`。删除确认、删除后本地缓存清理和刷新流程仍由 `StudentCenterPage.tsx` 调度。
- 第 4 步第十四小步已完成：继续扩展 `teacherBindingRules.ts` 和 `teacherBindingRules.test.ts`，把负责老师绑定请求执行动作下沉为 `executeTeacherBindingRequest`，页面不再直接拼装老师绑定请求和调用 `apiFetch`。乐观更新、失败回滚和刷新流程仍由 `StudentCenterPage.tsx` 调度。
- 第 4 步第十五小步已完成：继续扩展 `classSaveRules.ts` 和 `classSaveRules.test.ts`，把班级新建和更新请求执行动作下沉为 `executeClassCreateRequest` / `executeClassUpdateRequest`，并在新建班级后复用 `executeTeacherBindingRequest` 绑定负责老师。保存校验、乐观更新、失败处理和刷新流程仍由 `StudentCenterPage.tsx` 调度。
- 第 4 步第十六小步第一刀已完成：新增 `overviewFilterRules.ts` 和 `overviewFilterRules.test.ts`，把校区总览的班级过滤、联动筛选选项、筛选摘要、筛选标签和统计卡片计算从 `StudentCenterPage.tsx` 下沉为可测试规则。校区总览浮层开关、hover/click 交互和筛选状态仍由页面管理。
- 第 4 步第十六小步第二刀已完成：新增 `classFilterRules.ts` 和 `classFilterRules.test.ts`，把班级管理的班级筛选、联动筛选选项、筛选摘要、筛选标签、信息不完整判断和问题卡片优先排序从 `StudentCenterPage.tsx` 下沉为可测试规则。班级管理筛选状态和 hover/click 浮层交互仍由页面管理。
- 第 4 步第十六小步第三刀已完成：新增 `studentFilterRules.ts` 和 `studentFilterRules.test.ts`，把学员管理的学员行生成、筛选命中、联动筛选选项、筛选摘要、筛选标签、当前浮层选项和学员排序从 `StudentCenterPage.tsx` 下沉为可测试规则。学员管理筛选状态、姓名查询输入和 hover/click 浮层交互仍由页面管理。
- 第 4 步第十七小步第一刀已完成：新增 `classInviteRules.ts` 和 `classInviteRules.test.ts`，把班级邀请码加载/重置请求、loading map 更新和错误文案从 `StudentCenterPage.tsx` 下沉为可测试规则。页面仍负责触发请求、写入邀请码缓存和弹窗状态组装。
- 第 4 步第十七小步第二刀已完成：新增 `classStudentRules.ts` 和 `classStudentRules.test.ts`，把班级学生列表加载、新增学生、删除学生的请求执行、loading/saving map 更新、错误文案、空姓名校验、学生列表本地更新和新增后草稿清空从 `StudentCenterPage.tsx` 下沉为可测试规则。页面仍负责触发动作和弹窗状态组装。
- 第 4 步第十七小步第三刀已完成：新增 `classEditorStateRules.ts` 和 `classEditorStateRules.test.ts`，把班级编辑器字段变更、阶段切换后的年级重置、老师搜索更新、展开切换和展开时错误清空规则从 `StudentCenterPage.tsx` 下沉为可测试规则。页面仍负责触发动作和弹窗状态组装。
- 第 4 步第十八小步第一刀已完成：新增 `classEditorModalState.ts` 和 `classEditorModalState.test.ts`，把 `ClassEditorModal` 的 `mode / newClass / editing` 状态组装从 `StudentCenterPage.tsx` 下沉为可测试规则。弹窗 UI、保存/删除/老师绑定/学生维护行为不变。
- 第 4 步第十八小步第二刀已完成：继续扩展 `classEditorModalState.ts` 和 `classEditorModalState.test.ts`，把 `ClassEditorModal` 的 `locks / errors / options` 参数组装也从 `StudentCenterPage.tsx` 下沉为可测试规则。弹窗 UI、按钮禁用、错误提示和选项内容不变。
- 第 4 步第十九小步第一刀已完成：新增 `filterInteractionRules.ts` 和 `filterInteractionRules.test.ts`，把校区总览、班级管理、学员管理三套筛选浮层共用的关闭计时器取消和重新安排规则从 `StudentCenterPage.tsx` 下沉为可测试规则。筛选 UI、hover/click 行为和 120ms 关闭延迟不变。
- 第 4 步第十九小步第二刀已完成：继续扩展 `filterInteractionRules.ts` 和 `filterInteractionRules.test.ts`，把校区总览筛选入口开关、第一层 hover 和第一层 click 的 active/clicked layer 选择规则从 `StudentCenterPage.tsx` 下沉为可测试规则。校区总览筛选 UI 和交互行为不变。
- 第 4 步第二十小步第一刀已完成：继续扩展 `loadPageRules.ts` 和 `loadPageRules.test.ts`，把学管中心页面加载时的班级、成员和老师绑定三条请求执行从 `StudentCenterPage.tsx` 下沉为 `executeStudentCenterLoadRequest`。页面仍负责请求版本号、防过期、状态写入和错误处理。
- 第 4 步第二十小步第二刀已完成：继续扩展 `loadPageRules.ts` 和 `loadPageRules.test.ts`，把页面加载成功/失败后的状态结果包下沉为 `buildClassLoadSuccessState` / `buildClassLoadFailureState`。页面仍负责请求版本号、防过期、`setState` 调度和错误提示。
- 第 4 步第二十小步第三刀已完成：继续扩展 `loadPageRules.ts` 和 `loadPageRules.test.ts`，把页面加载开始时的请求版本递增、loading 开启、错误清空，以及 stale/current 请求判断下沉为 `resolveClassLoadStartState` / `isCurrentClassLoadRequest`。页面仍负责 ref 写入、请求调度和 `setState` 调度。
- 第 4 步第二十一小步已完成：做第 4 步收尾审信，确认 `StudentCenterPage.tsx` 仍约 1198 行，剩余职责主要是页面级调度、筛选状态、弹窗动作触发、API 调用编排和 `setState` 写入；同步修正文档重复段落和过期提醒；把默认 `npm test` 改为递归执行子目录测试；修复递归测试暴露的 `getToken` 导出/接入问题；同步旧源码扫描测试到拆分后的文件；补齐 `npm run lint` 暴露的窄类型问题。
- 第 5 步已阶段收尾：测试升级已完成 30 刀，脆弱源码扫描已削减一轮；剩余测试不再按数量硬砍，后续要先抽规则/组件，再替换对应源码扫描。
- 分支抽屉规则已补入本文件：`master`、`develop`、`work/`、`backup/`、`integrate/`、`release/` 的用途和清理口径已对齐 `AGENTS.md`。

当前准备对齐：

- 第 5 步后的下一轮治理入口。不要自动进核心代码；先根据当前需求选择：继续抽业务规则、继续拆大页面、补组件库章程，或针对某个页面做专项治理。

第 4 步剩余小步固定路线：

- 第 17 小步：班级编辑动作规则继续拆。状态：基本收尾，第一刀 `classInviteRules.ts` 已完成，第二刀 `classStudentRules.ts` 已完成，第三刀 `classEditorStateRules.ts` 已完成；下一步优先进入第 18 小步，除非复盘发现还有很小且纯的动作规则值得拆。
- 第 18 小步：班级编辑弹窗状态组装瘦身。状态：基本收尾，第一刀已下沉 `mode / newClass / editing`，第二刀已下沉 `locks / errors / options`；剩余 `users / teacherSearchByClassId / getClassDisplayName` 属于弹窗渲染依赖，暂不硬塞进 modal state。
- 第 19 小步：三套筛选交互状态整理。状态：基本收尾，第一刀已下沉浮层关闭计时器取消和重新安排规则，第二刀已下沉校区总览入口开关和 active/clicked layer 选择规则；班级/学员单层 active layer 暂不硬抽。
- 第 20 小步：页面加载流程继续拆。状态：基本收尾，第一刀已下沉页面加载请求执行，第二刀已下沉加载成功/失败后的状态结果包，第三刀已下沉加载开始状态和 stale/current 判断；页面仍负责 ref 写入、请求调度、`setState` 调度和错误提示。
- 第 21 小步：第 4 步收尾审信。状态：已完成；`npm test`、`npm run lint`、`npm run build` 已跑通，下一步进入第 5 步测试升级。

说明：

- 之前说的“16 步”只覆盖到筛选派生数据和前一阶段规则抽取，不代表第 4 步已经完全结束。
- 从第 17 小步开始属于第 4 步收尾拆分，原则仍然是一轮只做一刀，避免把页面调度、交互状态和测试升级混在一起。

下一步开始条件：

- Ricardo 明确说“继续拆”或“继续 Ricardo 治理路线并开始第 4 步下一小步”后，再进入核心代码修改。
- 进入下一小步前，先复述边界：小步拆分，不重写 UI，不改变筛选、权限、保存行为或数据库逻辑。

暂时不要做：

- 暂时不要整体拆 `frontend/src/App.tsx`。
- 暂时不要重写所有旧测试。
- 暂时不要把 Ricardo 组件库接入正式星润组件库。
- 暂时不要改数据库结构。

## 推荐执行顺序

### 第 1 步：治理文档

状态：已完成。

产物：

- `docs/refactor-roadmap.md`
- `docs/technical-debt.md`
- `docs/ricardo-components/USAGE_RULES.md`

完成标准：

Ricardo 打开文档后，能回答下面这些问题，就算完成：

- 我现在停在哪一步？
- 哪些东西只是已经建立，还没有确认完成？
- 下一句该怎么唤醒 AI？
- AI 会不会在我没确认时自动改核心代码？
- 下一步要做什么、暂时不要做什么？
- 哪些技术债先处理，哪些先放着？
- 我要调用筛选组件时，应该复制哪句口令？

本步骤已由 Ricardo 确认后进入第 2 步。

### 第 2 步：班级命名统一

状态：阶段完成。

建议产物：

- `frontend/src/domain/classNaming.ts`
- `frontend/src/classNaming.test.ts` 或同等规则测试文件。

目标：

- 全站班级显示名只走一套规则。
- 学管中心先改为调用统一规则。
- 咨询页面、班级认领、课表、反馈页等通过班级 ID 展示当前正式班级名的位置，逐步接入统一规则。

统一口径：

- 只要是通过班级 ID 调取到的当前正式班级，都走命名规则 1。
- 页面展示层默认只显示年级和班级，例如：`四年级·1班`。
- 权限判断层可以打开“入学年份”，例如：`2025级·四年级·1班`。
- “入学年份”是文案标准，不再使用“入学年级”作为该开关名称。
- 历史快照、手动填写文本、旧备注、别名匹配、小程序/家长端兼容展示等属于命名规则 2 或历史文本，暂时不碰。
- 学管中心修改当前班级信息后，所有通过班级 ID 展示的当前班级名应随之变化；历史文本不追改。

已完成：

- 新增 `frontend/src/domain/classNaming.ts`。
- 新增 `frontend/src/classNaming.test.ts`。
- 学管中心已调用统一年级、学段、入学年份和班级显示名规则。
- 课程日历已调用统一年级、学段和年级排序规则。
- 咨询页当前试听班、成功进班、班级下拉等通过班级 ID 展示的位置已接入统一班级显示名。
- 班级认领、反馈页和账号审批负责班级摘要等当前正式班级展示位置已接入统一班级显示名。

后续提醒：

- 以后只要遇到“通过班级 ID 展示当前正式班级名”的位置，默认继续接入命名规则 1。
- 历史快照、手动填写文本、旧备注、别名匹配、小程序/家长端兼容字段仍属于命名规则 2 或历史文本，暂时不碰。

### 第 3 步：学管中心权限判断层

状态：第一小步完成。

建议产物：

- `frontend/src/features/student-center/permissions.ts`
- 必要时新增 `frontend/src/features/student-center/permissions.test.ts`

目标：

- 学管中心页面不再散落 `hasOwnerAccess(...)`、`hasStaffAccess(...)` 和 `currentUser.role === ...`。
- 页面只读取统一权限对象。
- 先只抽权限判断层，不同时拆页面、不重写学管中心 UI。
- 权限判断层负责回答“当前用户能看什么、能操作什么、默认筛选范围是什么”；页面展示层只消费判断结果。

建议第一小步：

- 先盘点学管中心内现有角色判断。
- 再建立一个统一权限对象，例如 `getStudentCenterPermissions(currentUser)`。
- 最后只替换学管中心内最集中的权限判断，保留原视觉和交互不变。

已完成：

- 新增 `frontend/src/features/student-center/permissions.ts`。
- 新增 `frontend/src/features/student-center/permissions.test.ts`。
- 学管中心已接入 `getStudentCenterPermissions(currentUser)`。
- 已集中处理：成员/老师绑定数据加载权限、普通教师数据范围、全机构筛选范围、统计卡片分支、新建班级入口、负责老师编辑入口、班级/学员范围标签。

后续提醒：

- 以后学管中心新增“谁能看、谁能点、谁能改、默认看什么范围”时，先扩展权限判断层，不直接在页面里写角色判断。
- 本步骤尚未拆 `ClassManagementPage`，页面拆分属于第 4 步。

### 第 4 步：拆学管中心页面

状态：第一小步完成。

建议产物：

- `frontend/src/features/student-center/StudentCenterPage.tsx`
- `frontend/src/features/student-center/CampusOverview.tsx`
- `frontend/src/features/student-center/ClassManagementTab.tsx`
- `frontend/src/features/student-center/StudentManagementTab.tsx`
- `frontend/src/features/student-center/ClassEditorModal.tsx`
- `frontend/src/features/student-center/types.ts`

目标：

- `App.tsx` 只负责挂载学管中心页面，不继续承载完整学管中心实现。

已完成：

- 新增 `frontend/src/features/student-center/StudentCenterPage.tsx`。
- 新增 `frontend/src/features/student-center/StudentCenterPage.structure.test.ts`。
- 新增 `frontend/src/features/student-center/model.ts`。
- 新增 `frontend/src/features/student-center/CampusOverview.tsx`。
- 新增 `frontend/src/features/student-center/ClassManagementTab.tsx`。
- 新增 `frontend/src/features/student-center/StudentManagementTab.tsx`。
- 新增 `frontend/src/features/student-center/ClassEditorModal.tsx`。
- 新增 `frontend/src/features/student-center/useClassEditorModalActions.ts`。
- 新增 `frontend/src/features/student-center/classSaveRules.ts`。
- 新增 `frontend/src/features/student-center/classSaveRules.test.ts`。
- 新增 `frontend/src/features/student-center/classDeleteRules.ts`。
- 新增 `frontend/src/features/student-center/classDeleteRules.test.ts`。
- 新增 `frontend/src/features/student-center/teacherBindingRules.ts`。
- 新增 `frontend/src/features/student-center/teacherBindingRules.test.ts`。
- 新增 `frontend/src/features/student-center/loadPageRules.ts`。
- 新增 `frontend/src/features/student-center/loadPageRules.test.ts`。
- 新增 `frontend/src/features/student-center/overviewFilterRules.ts`。
- 新增 `frontend/src/features/student-center/overviewFilterRules.test.ts`。
- 新增 `frontend/src/features/student-center/classFilterRules.ts`。
- 新增 `frontend/src/features/student-center/classFilterRules.test.ts`。
- 新增 `frontend/src/features/student-center/studentFilterRules.ts`。
- 新增 `frontend/src/features/student-center/studentFilterRules.test.ts`。
- 新增 `frontend/src/features/student-center/classInviteRules.ts`。
- 新增 `frontend/src/features/student-center/classInviteRules.test.ts`。
- 新增 `frontend/src/features/student-center/classStudentRules.ts`。
- 新增 `frontend/src/features/student-center/classStudentRules.test.ts`。
- 新增 `frontend/src/features/student-center/classEditorStateRules.ts`。
- 新增 `frontend/src/features/student-center/classEditorStateRules.test.ts`。
- 新增 `frontend/src/features/student-center/classEditorModalState.ts`。
- 新增 `frontend/src/features/student-center/classEditorModalState.test.ts`。
- 新增 `frontend/src/features/student-center/filterInteractionRules.ts`。
- 新增 `frontend/src/features/student-center/filterInteractionRules.test.ts`。
- 新增 `frontend/src/workspaceShared.ts`，避免 `StudentCenterPage` 反向依赖 `App.tsx`。
- `App.tsx` 已改为只挂载 `<StudentCenterPage />`。
- 已同步旧源码扫描测试，让它们检查新的学管中心文件。
- 校区总览展示层已抽为 `CampusOverview`，校区总览筛选派生数据已下沉到 `overviewFilterRules.ts`；总览筛选状态和 hover/click 浮层交互仍由 `StudentCenterPage` 管理。
- 班级管理展示层已抽为 `ClassManagementTab`，班级筛选派生数据已下沉到 `classFilterRules.ts`；班级筛选状态、刷新、新建入口、卡片点击、编辑弹窗和保存逻辑仍由 `StudentCenterPage` 管理。
- 学员管理展示层已抽为 `StudentManagementTab`，学员筛选派生数据已下沉到 `studentFilterRules.ts`；学员筛选状态、姓名查询状态和 hover/click 浮层交互仍由 `StudentCenterPage` 管理。
- 班级编辑弹窗展示层已抽为 `ClassEditorModal`，弹窗参数已按职责分组，弹窗 action 组装已抽到 `useClassEditorModalActions`，但核心 API 动作仍由 `StudentCenterPage` 管理。
- 班级编辑弹窗的 `mode / locks / errors / options / newClass / editing` 状态组装已抽到 `classEditorModalState.ts`，覆盖弹窗开关状态、锁定状态、错误提示、基础选项、新建班级状态、编辑班级状态、老师搜索过滤、年级选项、显示名预览、邀请码状态和学生维护状态；弹窗 UI 与业务动作不变。
- 班级保存规则已抽到 `classSaveRules.ts`，覆盖保存 payload、保存请求、保存请求执行、保存提示文案、新建后的乐观班级项、本地班级列表、老师绑定表、表单缓存乐观更新、新建草稿重置、新建后展开状态、关闭编辑前脏检查、放弃草稿重置、保存前校验和重复班级判断；保存校验、乐观更新、失败处理和刷新流程仍由 `StudentCenterPage.tsx` 调度。
- 班级删除规则已抽到 `classDeleteRules.ts`，覆盖删除确认文案、删除请求、删除请求执行、删除失败文案、删除后弹窗关闭规则，以及删除成功后的本地班级列表、老师绑定表、表单缓存和老师搜索缓存清理；删除确认、删除后本地缓存清理和刷新流程仍由 `StudentCenterPage.tsx` 调度。
- 负责老师绑定规则已抽到 `teacherBindingRules.ts`，覆盖绑定前旧状态快照、绑定请求 endpoint/payload、绑定请求执行、绑定中状态、绑定提示文案、绑定时 class item 和 class list 乐观更新，以及绑定失败后的 teacher map、class item 和 class list 回滚；乐观更新、失败回滚和刷新流程仍由 `StudentCenterPage.tsx` 调度。
- 班级邀请码规则已抽到 `classInviteRules.ts`，覆盖邀请码加载/重置请求、loading map 更新和错误文案；页面仍负责触发请求、写入邀请码缓存和弹窗状态组装。
- 班级学生维护规则已抽到 `classStudentRules.ts`，覆盖学生列表加载、新增学生、删除学生的请求执行、loading/saving map 更新、错误文案、空姓名校验、学生列表本地更新和新增后草稿清空；页面仍负责触发动作和弹窗状态组装。
- 班级编辑器本地状态规则已抽到 `classEditorStateRules.ts`，覆盖字段变更、年级输入归一、阶段切换后的年级重置、老师搜索更新、展开切换和展开时错误清空；页面仍负责触发动作和弹窗状态组装。
- 页面刷新规则已抽到 `loadPageRules.ts`，覆盖页面加载请求执行、加载开始状态、stale/current 请求判断、加载成功/失败后的状态结果包、老师绑定 key 规范化、刷新后班级表单缓存重建、刷新后展开班级选择，以及刷新失败时的错误归一、表单缓存重置、新建班级负责老师重置和展开班级重置；ref 写入、请求调度、`setState` 调度和错误提示仍由 `StudentCenterPage.tsx` 管理。
- 筛选交互规则已抽到 `filterInteractionRules.ts`，覆盖浮层关闭 timer 的取消、重排和回调后清空，以及校区总览入口开关、hover/click active layer 选择；班级管理、学员管理仍由页面持有单层 active layer 和具体筛选状态。

后续提醒：

- 下一步不要直接大拆整个 `StudentCenterPage.tsx`。
- 第 4 步已经完成收尾审信，下一步进入第 5 步测试升级；不要为了拆而拆。

#### 学管中心剩余职责地图

当前 `StudentCenterPage.tsx` 仍然保留这些职责：

- 数据加载和刷新：班级、成员、老师绑定、邀请码、班级学生列表；其中班级页面刷新请求执行、加载开始状态、stale/current 判断、成功和失败后的状态结果包已下沉到 `loadPageRules.ts`。
- 班级编辑动作：新建、保存、删除、关闭确认、表单脏检查、老师绑定、邀请码、学生增删。
- 筛选状态和派生数据：校区总览、班级管理和学员管理筛选派生数据已下沉；三套筛选交互状态仍在页面内。
- 弹窗状态组装：把新建班级、编辑班级、锁定状态、错误状态和回调动作组装给 `ClassEditorModal`。
- 页面级展示调度：校区总览、主标签切换、班级管理、学员管理和错误提示。

已从 `StudentCenterPage.tsx` 下沉的班级保存规则：

- `buildClassSavePayload`：统一生成保存接口需要的班级 payload。
- `buildClassCreateRequest` / `buildClassUpdateRequest`：统一生成新建和更新班级的接口路径与请求参数。
- `executeClassCreateRequest` / `executeClassUpdateRequest`：统一执行新建和更新班级请求，页面不再直接拼装班级保存请求和调用 `apiFetch`。
- `resolveClassSaveRefreshErrorMessage`：统一生成班级保存成功但列表刷新失败的提示文案。
- `resolveClassSaveErrorMessage`：统一生成班级保存失败提示文案。
- `resolveCreatedClassTeacherBindingErrorMessage`：统一生成新建班级成功但负责老师绑定失败的提示文案。
- `buildOptimisticCreatedClassItem`：统一生成新建班级后本地列表需要展示的乐观班级项。
- `resolveClassesAfterOptimisticCreate`：统一处理新建成功后本地班级列表替换同 ID 旧项并追加新项。
- `resolveTeacherBindingsAfterOptimisticCreate`：统一处理新建成功后本地负责老师绑定表写入新班级老师。
- `resolveFormsAfterOptimisticCreate`：统一处理新建成功后本地表单缓存写入新班级表单。
- `resolveFormsAfterCreateDraftReset`：统一处理新建班级成功后清空 `new` 草稿，但保留其他旧班级编辑草稿。
- `resolveNewClassTeacherAfterCreate`：统一处理新建班级成功后清空新班级负责老师选择。
- `resolveExpandedClassAfterOptimisticCreate`：统一处理新建班级成功后展开刚创建的班级。
- `resolveClassFormDraftDirty`：统一判断新班级和旧班级编辑草稿是否有未保存修改。
- `resolveFormsAfterClassDraftReset`：统一处理放弃编辑时，新班级回到空草稿、旧班级回到已保存表单。
- `resolveNewClassTeacherAfterDraftReset`：统一处理放弃新建班级时清空新班级老师选择，旧班级不受影响。
- `resolveTeacherSearchAfterClassDraftReset`：统一处理放弃新建班级时清空新班级老师搜索，旧班级不受影响。
- `validateClassSaveDraft`：统一返回保存前校验文案。
- `findDuplicateClass`：统一判断同学科、学段、年级、班号、入学年份的重复班级。

已从 `StudentCenterPage.tsx` 下沉的班级删除规则：

- `buildClassDeleteConfirmMessage`：统一生成删除确认文案。
- `buildClassDeleteRequest`：统一生成删除班级接口路径和请求参数。
- `executeClassDeleteRequest`：统一执行删除班级请求，页面不再直接拼装删除请求和调用 `apiFetch`。
- `resolveClassDeleteErrorMessage`：统一生成删除失败提示文案。
- `resolveExpandedClassAfterDelete`：统一判断删除后当前编辑弹窗是否关闭。
- `resolveClassesAfterDelete`：统一处理删除成功后的本地班级列表清理。
- `resolveTeacherBindingsAfterClassDelete`：统一处理删除成功后的本地老师绑定表清理。
- `resolveFormsAfterClassDelete`：统一处理删除成功后的本地表单缓存清理，并保留 `new` 草稿和其他班级草稿。
- `resolveTeacherSearchAfterClassDelete`：统一处理删除成功后的本地老师搜索缓存清理。

已下沉到学管中心领域文件的老师绑定规则：

- `buildTeacherBindingRefreshErrorMessage`：统一生成绑定已保存但列表刷新失败的提示文案。
- `resolveTeacherBindingSaveErrorMessage`：统一生成负责老师保存失败的提示文案。
- `buildTeacherBindingRequest`：统一生成负责老师绑定接口路径和请求体。
- `executeTeacherBindingRequest`：统一执行负责老师绑定请求，页面不再直接拼装绑定请求和调用 `apiFetch`。
- `resolveTeacherBindingSavingStartState` / `resolveTeacherBindingSavingEndState`：统一维护负责老师绑定中的行级 loading 状态。
- `resolveTeacherBindingOptimisticClassItem`：统一生成负责老师绑定时的班级乐观更新结果。
- `resolveClassesAfterTeacherBindingOptimisticUpdate`：统一处理负责老师绑定时的班级列表乐观更新，只修改目标班级。
- `resolveTeacherBindingRollbackTeacherBindings`：绑定失败时，如果当前仍是失败的乐观值，则恢复旧老师 ID。
- `resolveTeacherBindingRollbackClassItem`：绑定失败时，如果当前班级仍是失败的乐观老师，则恢复旧老师名称和 ID。
- `resolveClassesAfterTeacherBindingRollback`：统一处理负责老师绑定失败后的班级列表回滚，只恢复目标班级且避免覆盖后续更新。

已从 `StudentCenterPage.tsx` 下沉的班级邀请码规则：

- `buildClassInviteLoadRequest` / `buildClassInviteResetRequest`：统一生成邀请码加载和重置接口路径与请求参数。
- `executeClassInviteLoadRequest` / `executeClassInviteResetRequest`：统一执行邀请码加载和重置请求，页面不再直接拼装邀请码请求和调用 `apiFetch`。
- `resolveInviteLoadingStartState` / `resolveInviteLoadingEndState`：统一维护邀请码加载/重置中的行级 loading 状态。
- `resolveClassInviteErrorMessage`：统一生成邀请码加载失败和重置失败文案。

已从 `StudentCenterPage.tsx` 下沉的班级学生维护规则：

- `executeClassStudentListRequest` / `executeClassStudentCreateRequest` / `executeClassStudentDeleteRequest`：统一执行学生列表加载、新增学生和删除学生请求，页面不再直接调用学生维护 API helper。
- `resolveClassStudentSavingStartState` / `resolveClassStudentSavingEndState`：统一维护学生加载/保存中的行级 loading 状态。
- `resolveClassStudentErrorMessage`：统一生成学生列表加载、新增学生和删除学生失败文案。
- `resolveClassStudentDraftName` / `validateClassStudentDraftName`：统一处理学生姓名草稿 trim 和空姓名校验。
- `resolveClassStudentsAfterLoad` / `resolveClassStudentsAfterCreate` / `resolveClassStudentsAfterDelete`：统一处理班级学生列表本地缓存更新。
- `resolveClassStudentDraftAfterCreate`：统一处理新增学生成功后清空当前班级学生姓名草稿。

已从 `StudentCenterPage.tsx` 下沉的班级编辑器本地状态规则：

- `resolveClassFormAfterFieldChange`：统一处理班级编辑器字段变更，包含年级输入归一和阶段切换后的年级重置。
- `resolveFormsAfterFieldChange`：统一处理表单缓存中某个班级草稿的字段更新。
- `resolveTeacherSearchAfterChange`：统一处理班级维度的老师搜索词更新。
- `resolveExpandedClassAfterToggle`：统一处理班级卡片展开/收起，并尊重锁定状态。
- `resolveClassEditorErrorsAfterToggle`：统一处理展开编辑器时清空表单错误和老师绑定错误。

已从 `StudentCenterPage.tsx` 下沉的班级编辑弹窗状态组装规则：

- `buildClassEditorModalState`：统一组装 `ClassEditorModal` 的 `mode / locks / errors / options / newClass / editing` 参数。
- `filterUsersByKeyword`：统一处理老师搜索过滤，并保证当前选中的老师始终保留在选项中。
- `classEditorModalState.ts` 目前只处理弹窗数据和轻量参数组装，不处理保存、删除、老师绑定、邀请码或学生维护动作。

已从 `StudentCenterPage.tsx` 下沉的页面刷新规则：

- `executeStudentCenterLoadRequest`：统一执行学管中心页面加载所需的班级、成员和老师绑定请求；普通教师视角会跳过成员和老师绑定请求并返回空数据。
- `normalizeTeacherBindings`：统一把 API 返回的老师绑定对象 key 转成数字班级 ID。
- `resolveFormsAfterClassLoad`：统一处理刷新后班级表单缓存重建，并保留 `new` 草稿。
- `resolveExpandedClassAfterLoad`：统一处理刷新后应该展开哪个班级，避免继续展开已经不存在的班级。
- `resolveClassLoadStartState`：统一处理刷新开始时的请求版本递增、loading 开启和页面错误清空。
- `isCurrentClassLoadRequest`：统一判断当前请求是否仍是最新请求，避免旧请求覆盖新请求。
- `resolveClassLoadError`：统一处理刷新失败时的错误对象，非 Error 值回退为“班级管理数据加载失败”。
- `resolveFormsAfterClassLoadFailure`：统一处理刷新失败且不保留旧状态时的表单缓存重置。
- `resolveNewClassTeacherAfterClassLoadFailure`：统一处理刷新失败且不保留旧状态时的新班级负责老师重置。
- `resolveExpandedClassAfterLoadFailure`：统一处理刷新失败且不保留旧状态时的展开班级重置。

已从 `StudentCenterPage.tsx` 下沉的校区总览筛选规则：

- `resolveOverviewFilteredClasses`：统一处理校区总览当前筛选下的班级列表。
- `resolveOverviewFilterOptions`：统一处理校区总览科目、教师、学段、年级的联动选项。
- `buildOverviewFilterSummary`：统一生成校区总览筛选摘要文案。
- `buildOverviewFilterItems`：统一生成校区总览筛选标签和选中状态。
- `resolveOverviewSummaryItems`：统一生成负责人/超级管理员和普通教师不同视角的统计卡片。

已从 `StudentCenterPage.tsx` 下沉的班级管理筛选规则：

- `getClassTeacherUserId`：统一读取班级负责老师 ID，优先使用老师绑定表。
- `getClassEffectiveSubject`：统一识别班级筛选用科目，班级缺科目时可从负责老师绑定的科目推断。
- `classMatchesFilters`：统一判断班级是否命中科目、教师、学段、年级筛选。
- `resolveClassFilterOptions`：统一生成班级管理科目、教师、学段、年级的联动筛选选项。
- `buildClassFilterSummary`：统一生成班级管理筛选摘要文案。
- `buildClassFilterItems`：统一生成班级管理筛选标签和选中状态。
- `resolveActiveClassFilterOptions`：统一返回当前浮层应该展示的筛选项。
- `getClassInfoIssues` / `isClassInfoIncomplete`：统一判断班级缺学科或缺负责老师等问题。
- `resolveFilteredClasses`：统一处理班级筛选结果，并保证信息不完整的班级排在最前面，其余按年级从低到高排列。

已从 `StudentCenterPage.tsx` 下沉的学员管理筛选规则：

- `buildStudentRows`：统一把班级列表和班级学员表合并成学员管理行，并补上负责老师 ID。
- `studentMatchesFilters`：统一判断学员行是否命中科目、教师、学段、年级、班级和姓名查询。
- `resolveStudentFilterOptions`：统一生成学员管理科目、教师、学段、年级、班级的联动筛选选项。
- `resolveFilteredStudentRows`：统一处理学员筛选结果，并按年级、班级名、学员姓名和学员 ID 排序。
- `buildStudentFilterSummary`：统一生成学员管理筛选摘要文案。
- `buildStudentFilterItems`：统一生成学员管理筛选标签和选中状态。
- `resolveActiveStudentFilterOptions`：统一返回当前浮层应该展示的筛选项。

已从 `StudentCenterPage.tsx` 下沉的筛选交互规则：

- `cancelFilterCloseTimer`：统一取消筛选浮层关闭计时器，并清空 timer ref。
- `scheduleFilterClose`：统一重新安排筛选浮层关闭计时器，执行关闭回调后清空 timer ref。
- `resolveOverviewFilterTriggerClick`：统一处理校区总览筛选入口点击后的开关状态和 layer 清空。
- `resolveOverviewFilterItemHover`：统一处理校区总览第一层 hover 后打开对应第二层，并取消 clicked layer。
- `resolveOverviewFilterItemClick`：统一处理校区总览第一层 click 后固定或关闭对应第二层。

建议继续拆解顺序：

1. 进入第 5 步测试升级，把当前容易碎的源码字符串扫描逐步换成更真实的规则测试或交互测试。
2. 第 5 步仍然一小刀一小刀做，优先挑最容易误报、且已经有规则文件承接的测试。

暂缓：

- 暂不拆数据库结构。
- 暂不改学管中心 UI。
- 暂不一次性把所有 state 都搬进 hook。

### 第 5 步：测试升级

状态：阶段收尾。

目标：

- 新规则优先写规则测试。
- 新组件优先写组件交互测试。
- 旧的源码扫描测试暂时保留，逐步替换。

已完成：

- 第一刀：把班级管理筛选测试里对 `classFilterRules.ts` 内部实现细节的源码正则盯梢，替换为 `classFilterRules.test.ts` 的真实规则行为测试；页面级测试只保留筛选状态和规则接入的守卫。
- 第二刀：继续削减 `account-card.test.tsx` 对 `loadPageRules.ts`、`teacherBindingRules.ts` 内部 endpoint、payload 和局部变量写法的源码盯梢；这些行为改由对应规则测试承接，页面级测试只保留调度接入和提示文案守卫。
- 第三刀：继续削减 `workspace-navigation.test.ts` 和 `account-card.test.tsx` 对 `classSaveRules.ts` 内部校验文案、刷新提示和命名导入写法的源码盯梢；这些行为由 `classSaveRules.test.ts` 覆盖，页面级测试只保留保存流程接入。
- 第四刀：继续削减页面级测试对 `classEditorStateRules.ts` 内部展开/锁定实现写法的源码盯梢；这些行为由 `classEditorStateRules.test.ts` 覆盖，页面级测试只保留统一展开规则的接入。
- 第五刀：继续削减结构/页面级测试对 `classEditorModalState.ts` 内部 mode、locks、errors、options、教师和学生状态组装写法的源码盯梢；这些行为由 `classEditorModalState.test.ts` 覆盖，页面级测试只保留 builder 接入和弹窗分组传参。
- 第六刀：继续削减页面级测试对学生维护内部导入和 `studentsByClassId` 精确 state 写法的源码盯梢；学生列表加载、新增、删除和缓存更新行为由 `classStudentRules.test.ts` 覆盖，页面级测试只保留编辑学生区域的 UI 接入。
- 第七刀：继续削减页面级测试对加载/老师绑定规则文件的内部 endpoint、导出函数名、回滚函数写法和刷新失败文案的源码盯梢；这些行为由 `loadPageRules.test.ts` 和 `teacherBindingRules.test.ts` 覆盖，页面级测试不再把规则文件内容拼进学管中心页面源码块。
- 第八刀：继续削减 `workspace-navigation.test.ts` 对 `classFilterRules.ts` 导出函数名的源码盯梢；班级筛选选项行为由 `classFilterRules.test.ts` 覆盖，页面级测试只保留筛选规则接入和 UI 状态守卫。
- 第九刀：继续削减页面级测试对 `model.ts` 内部 `LoadPageResult` 类型别名的源码盯梢；页面测试只保留加载流程状态返回、非破坏性刷新和规则接入守卫。
- 第十刀：删除 `workspace-navigation.test.ts` 中重复的班级管理刷新调和源码扫描；非破坏性刷新和加载失败状态由 `account-card.test.tsx` 与 `loadPageRules.test.ts` 继续覆盖，导航测试只保留页面入口和导航相关守卫。
- 第十一刀：删除 `workspace-navigation.test.ts` 中重复的班级维度老师绑定 state/选择器源码扫描；老师绑定请求、回滚、saving 状态和弹窗组装由 `teacherBindingRules.test.ts`、`classEditorModalState.test.ts` 与 `account-card.test.tsx` 继续覆盖。
- 第十二刀：删除 `workspace-navigation.test.ts` 中重复的班级保存/删除锁定期间防选择、防刷新源码扫描；异步锁定按钮接入由 `account-card.test.tsx` 继续覆盖，展开锁定和加载状态规则由 `classEditorStateRules.test.ts` 与 `loadPageRules.test.ts` 继续覆盖。
- 第十三刀：削减 `workspace-navigation.test.ts` 中紧凑卡片测试对 `loadPage` 请求版本实现写法的源码扫描；请求版本递增和 stale 判断由 `loadPageRules.test.ts` 继续覆盖，紧凑卡片外观壳暂时保留页面级守卫。
- 第十四刀：削减 `workspace-navigation.test.ts` 中班级筛选测试对筛选 state 名和 setter 写法的源码扫描；筛选行为、联动选项和问题卡片排序由 `classFilterRules.test.ts` 覆盖，页面测试只保留筛选规则接入、共享年级选项和弹窗年级控件守卫。
- 第十五刀：削减 `account-card.test.tsx` 中新建班级选老师测试对 `selectedTeacher` 局部变量写法的源码扫描；未选老师校验由 `classSaveRules.test.ts` 覆盖，老师绑定请求由 `teacherBindingRules.test.ts` 覆盖，页面测试只保留保存校验和新建后绑定接入。
- 第十六刀：削减 `account-card.test.tsx` 中老师绑定选择测试对 previous state、map 回滚和 class list 回滚实现串联的源码扫描；这些回滚行为由 `teacherBindingRules.test.ts` 覆盖，页面测试只保留选择框触发绑定、请求版本失效和绑定后刷新接入。
- 第十七刀：删除 `account-card.test.tsx` 中两条通过 `AppModule` 反查 `resolveTeacherBindingRollbackTeacherBindings` 的重复 map 回滚测试；map 回滚行为由 `teacherBindingRules.test.ts` 直接覆盖，页面测试不再依赖旧 re-export 入口验证同一行为。
- 第十八刀：删除 `account-card.test.tsx` 中两条通过 `AppModule` 反查 `resolveTeacherBindingRollbackClassItem` 的重复 class item 回滚测试；class item 回滚行为由 `teacherBindingRules.test.ts` 直接覆盖，页面测试不再依赖旧 re-export 入口验证同一行为。
- 第十九刀：删除 `account-card.test.tsx` 中两条只覆盖 `resolveAssignmentRollbackClassIds` 的旧测试，并同步删除 `App.tsx` 中仅供测试反查、生产代码未使用的 `resolveAssignmentRollbackClassIds` / `areClassIdListsEqual` 死代码。
- 第二十刀：新增 `workspaceShared.test.ts` 直接覆盖 `buildAuthedPath` 无 token、带 token、已有 query 参数三种真实行为，并削减 `workspace-navigation.test.ts` 对 `workspaceShared.ts` 内部 `getToken` 写法的源码盯梢；页面级测试只保留课程 PDF 链接调用 `buildAuthedPath` 的接入守卫。
- 第二十一刀：继续扩展 `workspaceShared.test.ts`，直接覆盖 `getToken` 读取共享 token key，以及 storage 包装函数在 storage 不可用时的容错行为；同步削减 `app-storage-guard.test.tsx` 对 `workspaceShared.ts` 内部 `localStorage.getItem` 次数和 `getToken` 导出写法的源码盯梢，守卫测试只保留 App 不直接读写 auth storage 的边界。
- 第二十二刀：继续扩展 `workspaceShared.test.ts`，直接断言 `workspaceCardClass` / `workspaceSoftCardClass` 导出值包含暗色模式表面样式；同步删除 `account-card.test.tsx` 对 `workspaceShared.ts` 源码字符串的读取和正则盯梢，账号卡片测试只保留自身渲染和工作台壳层守卫。
- 第二十三刀：把 `workspace-dashboard.test.tsx` 中“不要从 App 导入共享样式”的源码正则，替换为组件真实渲染契约测试：`WorkspaceDashboard` 必须使用 shell 传入的 `styles.pageClass/cardClass/primaryButtonClass`。同时删除该测试对 `WorkspaceDashboard.tsx` 源码文件的读取。
- 第二十四刀：削减 `workspace-dashboard.test.tsx` 中与当前组件无关的 App 源码文案盯梢；Dashboard 文案测试只检查 `WorkspaceDashboard` 自身真实渲染出的 AI 标签，不再顺手读取 `App.tsx` 检查复习生成页面文案。
- 第二十五刀：把 `landing-legal-pages.test.tsx` 中检查残留 `˜` 字符的源码扫描，改为检查 `LandingPage` 真实渲染出的 markup；同时删除该测试文件对 `App.tsx` 源码读取的依赖。
- 第二十六刀：先对 `organization-auth.test.tsx` 做降噪收拢：`App.tsx` 源码只读取一次，并抽出 `getApprovalPageSource()` 复用审批页源码块，减少重复读取和重复截取，为后续把组织审批/邀请逻辑抽成规则测试留出口；当前覆盖面不变。
- 第二十七刀：删除 `review-generation-async.test.tsx` 中 3 条重复源码盯梢：异步字段、pending/failed/转写文案、ready 必须有 PDF 的逻辑已由 `reviewGenerationAsync.test.ts` 真实规则测试覆盖；页面级测试保留轮询、归一化接入、创建成功和重复上传提示等接入守卫。
- 第二十八刀：继续删除 `review-generation-async.test.tsx` 中 2 条与 `workspace-navigation.test.ts` 重复的源码盯梢：创建成功关闭 composer/刷新历史、重复上传提示和高亮传参已由导航测试覆盖；该文件只保留异步轮询、归一化接入和成员班级同步守卫。
- 第二十九刀：把 `class-feedback-generation.test.tsx` 中 `ClassFeedbackGenerationWorkspace` 共享样式 helper 的源码正则，改成真实渲染 markup 断言：检查卡片、软卡片、输入框、控制栏、主/次按钮样式和文案输出；减少对 `ClassFeedbackGenerationWorkspace.tsx` 内部变量拼法的依赖。
- 第三十刀：继续削减 `class-feedback-generation.test.tsx` 对 `ClassFeedbackGenerationWorkspace.tsx` 的源码读取，把 header 布局和 `headerAside` 插槽断言改为真实渲染 markup 检查；该测试文件不再读取 `ClassFeedbackGenerationWorkspace.tsx` 源码。

阶段审信：

- 第 5 步已经完成 30 刀，当前不再适合继续只按 `readFileSync` 数量硬砍；剩余源码扫描需要按性质分流处理。
- 可以暂时保留的守卫：全局边界、废代码扫描、移动端性能样式、App 不直接读写 auth storage、页面路由接入等。这类测试虽然也是源码扫描，但目标是守住边界，不急着替换。
- 需要先抽规则再替换的测试：组织审批/邀请、复习生成页面、班级反馈页面、课程日历等。它们现在还把业务编排藏在页面里，直接删源码扫描会丢覆盖。
- 需要等页面继续拆分后再升级的测试：`account-card.test.tsx`、`class-management-invite.test.tsx`、`smart-wrong-questions.test.ts` 这类大文件。它们还有大量页面级源码扫描，但下一步应先拆出更稳定的规则/组件，再改测试。
- 第 5 步可以阶段收尾；如果继续推进，优先做“先抽规则或组件，再替换对应源码扫描”，不要为了减少测试数量而删除守卫。

## 每次继续前的检查

继续执行前，先确认：

- 当前要做的是路线图里的哪一步。
- Ricardo 是否已经明确同意进入这一步。
- 是否会影响全站。
- 是否涉及权限差异。
- 是否涉及班级命名规则。
- 是否涉及筛选逻辑。
- 是否需要先更新 Ricardo 组件库或技术债账本。
