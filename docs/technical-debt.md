# 技术债账本

这个文件记录网站当前比较明确的技术债。技术债不是马上全部修，而是编号、定级、逐步处理。

大前提：Ricardo 治理路线的核心目的，是把代码里已经出现或即将堆积的脏乱问题逐步拆出来、编号、排序、处理。判断一项治理是否值得做，不看它是否“看起来高级”，而看它是否减少重复、降低误伤、统一业务规则、隔离权限逻辑、让后续需求更容易继续。

## 状态说明

- `未处理`：已确认问题，但还没开始。
- `进行中`：当前正在处理。
- `部分处理`：已经拆掉一部分，但还没完全解决。
- `已处理`：已完成并验证。
- `暂缓`：确认存在，但当前不值得优先处理。

## 当前处理顺序

先处理会影响接力和全站一致性的债，不做一次性大拆。

1. `DEBT-002`：开始逐步替换源码字符串扫描测试。
2. `DEBT-001`：后续需要时继续拆学管中心内部结构。
3. `DEBT-004`：后续新增权限时继续扩大学管中心权限判断层覆盖范围。

已阶段完成，后续遇到新页面时继续按规则执行：

- `DEBT-005`：当前正式课程名统一走命名规则总入口，并按班型分发到班课/小课规则。

暂缓：

- `DEBT-006`：Ricardo Component Lab 先保持静态 HTML。

已建立治理规则，后续遇到问题再执行：

- `DEBT-008`：分支和 worktree 需要按抽屉规则管理。

## DEBT-001：`App.tsx` 过大

位置：

- `frontend/src/App.tsx`

问题：

- 文件承担了全局入口、页面展示、业务状态、API 调用、权限判断、筛选逻辑、弹窗和大量 UI。
- 后续每次改页面都容易误伤其他页面。

风险：

- 修改成本越来越高。
- 上下文很容易不够。
- 同一类业务规则容易散落多份。

建议解决方式：

- 先从学管中心拆起。
- 按 feature 建目录，不做一次性全站大拆。
- 已完成第一小步：学管中心外壳页已抽到 `frontend/src/features/student-center/StudentCenterPage.tsx`，`App.tsx` 只负责挂载入口。
- 已同步抽出 `frontend/src/workspaceShared.ts`，避免新页面反向依赖 `App.tsx` 造成循环依赖。
- 已建立 `frontend/src/features/student-center/model.ts`，先收纳学管中心局部类型和表单工具。
- 已抽出 `frontend/src/features/student-center/CampusOverview.tsx`，先分离校区总览展示层。
- 已抽出 `frontend/src/features/student-center/ClassManagementTab.tsx`，先分离班级管理展示层。
- 已抽出 `frontend/src/features/student-center/StudentManagementTab.tsx`，先分离学员管理展示层。
- 已抽出 `frontend/src/features/student-center/ClassEditorModal.tsx`，先分离班级编辑弹窗展示层。
- 已将 `ClassEditorModal` 参数按 `mode / locks / errors / options / newClass / editing / actions` 分组，先减少父页面到弹窗的散乱传参。
- 后续继续拆 `StudentCenterPage.tsx` 内部：建议先复盘剩余职责，再选择一个小方向继续。总览、班级和学员筛选状态、派生数据、编辑弹窗动作和业务动作后续可再继续下沉。
- 已补充学管中心剩余职责地图：当前主要压力集中在数据加载、班级编辑动作、三套筛选派生数据、弹窗状态组装和页面级调度。
- 已新增 `frontend/src/features/student-center/useClassEditorModalActions.ts`，先把弹窗 action 组装从 JSX 中移出。
- 已新增并扩展 `frontend/src/features/student-center/classSaveRules.ts` 和 `classSaveRules.test.ts`，把班级保存 payload、保存请求、保存请求执行、保存提示文案、新建后的乐观班级项、本地班级列表、老师绑定表、表单缓存乐观更新、新建草稿重置、新建后展开状态、关闭编辑前脏检查、放弃草稿重置、保存前校验和重复班级判断抽为可测试规则，并补充旧班级修正信息时仍走同一命名规则的测试护栏。
- 已新增并扩展 `frontend/src/features/student-center/classDeleteRules.ts` 和 `classDeleteRules.test.ts`，把班级删除确认文案、删除请求、删除请求执行、删除失败文案、删除后弹窗关闭规则，以及删除成功后的本地班级列表、老师绑定表、表单缓存和老师搜索缓存清理抽为可测试规则。
- 已新增并扩展 `frontend/src/features/student-center/teacherBindingRules.ts` 和 `teacherBindingRules.test.ts`，把负责老师绑定前旧状态快照、绑定请求 endpoint/payload、绑定请求执行、绑定中状态、提示文案、班级项和班级列表乐观更新规则，以及绑定失败后的 teacher map、班级项和班级列表回滚规则从页面和 `App.tsx` 下沉到学管中心领域文件。
- 已新增 `frontend/src/features/student-center/classInviteRules.ts` 和 `classInviteRules.test.ts`，把班级邀请码加载/重置请求、loading map 更新和错误文案从页面下沉为可测试规则。
- 已新增 `frontend/src/features/student-center/classStudentRules.ts` 和 `classStudentRules.test.ts`，把班级学生列表加载、新增学生、删除学生的请求执行、loading/saving map 更新、错误文案、空姓名校验、学生列表本地更新和新增后草稿清空从页面下沉为可测试规则。
- 已新增 `frontend/src/features/student-center/classEditorStateRules.ts` 和 `classEditorStateRules.test.ts`，把班级编辑器字段变更、年级输入归一、阶段切换后的年级重置、老师搜索更新、展开切换和展开时错误清空从页面下沉为可测试规则。
- 已新增并扩展 `frontend/src/features/student-center/classEditorModalState.ts` 和 `classEditorModalState.test.ts`，把班级编辑弹窗的 `mode / locks / errors / options / newClass / editing` 状态组装从页面下沉为可测试规则。
- 已新增 `frontend/src/features/student-center/filterInteractionRules.ts` 和 `filterInteractionRules.test.ts`，把三套筛选浮层共用的关闭计时器取消、重排和回调后清空规则从页面下沉为可测试规则。
- 已继续扩展 `filterInteractionRules.ts` 和 `filterInteractionRules.test.ts`，把校区总览筛选入口开关、第一层 hover 和 click 的 active/clicked layer 选择规则从页面下沉为可测试规则。
- 已继续扩展 `frontend/src/features/student-center/loadPageRules.ts` 和 `loadPageRules.test.ts`，把学管中心页面加载时的班级、成员和老师绑定请求执行从页面下沉为 `executeStudentCenterLoadRequest`。
- 已继续扩展 `frontend/src/features/student-center/loadPageRules.ts` 和 `loadPageRules.test.ts`，把页面加载成功/失败后的状态结果包从页面下沉为 `buildClassLoadSuccessState` / `buildClassLoadFailureState`；页面仍负责请求版本号、防过期、`setState` 调度和错误提示。
- 已继续扩展 `frontend/src/features/student-center/loadPageRules.ts` 和 `loadPageRules.test.ts`，把页面加载开始状态和 stale/current 请求判断从页面下沉为 `resolveClassLoadStartState` / `isCurrentClassLoadRequest`；页面仍负责 ref 写入、请求调度、`setState` 调度和错误提示。
- 已新增并扩展 `frontend/src/features/student-center/loadPageRules.ts` 和 `loadPageRules.test.ts`，把页面刷新后的老师绑定 key 规范化、班级表单缓存重建、展开班级选择，以及刷新失败时的错误归一、表单缓存重置、新班级负责老师重置和展开班级重置从页面下沉为可测试规则。
- 已新增 `frontend/src/features/student-center/overviewFilterRules.ts` 和 `overviewFilterRules.test.ts`，把校区总览的班级过滤、联动筛选选项、筛选摘要、筛选标签和统计卡片计算从页面下沉为可测试规则。
- 已新增 `frontend/src/features/student-center/classFilterRules.ts` 和 `classFilterRules.test.ts`，把班级管理的班级筛选、联动筛选选项、筛选摘要、筛选标签、信息不完整判断和问题卡片优先排序从页面下沉为可测试规则。
- 已新增 `frontend/src/features/student-center/studentFilterRules.ts` 和 `studentFilterRules.test.ts`，把学员管理的学员行生成、筛选命中、联动筛选选项、筛选摘要、筛选标签、当前浮层选项和学员排序从页面下沉为可测试规则。
- 已完成第 4 步收尾审信：`StudentCenterPage.tsx` 仍约 1198 行，但剩余职责主要是页面级调度、筛选状态、弹窗动作触发、API 调用编排和 `setState` 写入；暂不为了拆而拆。
- 已修正默认测试脚本，让 `npm test` 递归执行 `src/**/*.test.ts` 和 `src/**/*.test.tsx`，避免 `features/student-center` 子目录测试被漏掉。
- 收尾审信中已修复 `getToken` 未导出导致的运行风险，并补齐 TypeScript lint 暴露的窄类型问题。下一步建议进入 `DEBT-002` 的测试升级。

优先级：高

状态：部分处理

## DEBT-002：测试大量依赖源码字符串扫描

位置：

- `frontend/src/*.test.tsx`

问题：

- 许多测试通过正则匹配源码字符串来判断功能存在。
- 这种方式很快，但容易被重构影响，也不验证真实交互。

风险：

- 组件抽取后测试容易误报。
- 一些真实 UI 问题无法覆盖。

建议解决方式：

- 暂时保留旧测试。
- 新抽出来的纯规则先写规则测试。
- 新组件逐步补组件交互测试或浏览器测试。
- 默认 `npm test` 已改为递归执行子目录测试，避免规则测试写了但没有被跑到。
- 第 4 步收尾时已同步一批旧源码扫描测试到新文件位置，但这只是止血；第 5 步要开始把最高风险的源码扫描逐步替换成规则测试或交互测试。
- 已完成第 5 步第一刀：班级管理筛选测试不再盯 `classFilterRules.ts` 内部 if/变量写法，改由 `classFilterRules.test.ts` 验证教师、学段、年级筛选行为；页面级测试只保留接入守卫。
- 已完成第 5 步第二刀：账号/学管中心源码扫描测试不再盯 `loadPageRules.ts` 和 `teacherBindingRules.ts` 的 endpoint、payload、局部变量等内部写法；对应行为由规则测试覆盖，页面级测试保留接入关系。
- 已完成第 5 步第三刀：页面级源码扫描测试不再盯 `classSaveRules.ts` 的校验文案、刷新提示和命名导入写法；对应行为由 `classSaveRules.test.ts` 覆盖，页面级测试保留保存流程接入关系。
- 已完成第 5 步第四刀：页面级源码扫描测试不再盯 `classEditorStateRules.ts` 的展开/锁定内部实现写法；对应行为由 `classEditorStateRules.test.ts` 覆盖，页面级测试保留统一展开规则接入。
- 已完成第 5 步第五刀：结构/页面级源码扫描测试不再盯 `classEditorModalState.ts` 的 mode、locks、errors、options、教师和学生状态组装写法；对应行为由 `classEditorModalState.test.ts` 覆盖，页面级测试保留 builder 接入和弹窗分组传参。
- 已完成第 5 步第六刀：页面级源码扫描测试不再盯学生维护的内部导入和 `studentsByClassId` 精确 state 写法；对应行为由 `classStudentRules.test.ts` 覆盖，页面级测试保留编辑学生区域的 UI 接入。
- 已完成第 5 步第七刀：页面级源码扫描测试不再盯加载/老师绑定规则文件的内部 endpoint、导出函数名、回滚函数写法和刷新失败文案；对应行为由 `loadPageRules.test.ts` 和 `teacherBindingRules.test.ts` 覆盖，页面级测试不再把规则文件内容拼进学管中心页面源码块。
- 已完成第 5 步第八刀：页面级源码扫描测试不再盯 `classFilterRules.ts` 的导出函数名；班级筛选选项行为由 `classFilterRules.test.ts` 覆盖，页面级测试保留筛选规则接入和 UI 状态守卫。
- 已完成第 5 步第九刀：页面级源码扫描测试不再盯 `model.ts` 内部 `LoadPageResult` 类型别名；页面测试保留加载流程状态返回、非破坏性刷新和规则接入守卫。
- 已完成第 5 步第十刀：删除 `workspace-navigation.test.ts` 中重复的班级管理刷新调和源码扫描；非破坏性刷新和加载失败状态由 `account-card.test.tsx` 与 `loadPageRules.test.ts` 继续覆盖，导航测试保留页面入口和导航相关守卫。
- 已完成第 5 步第十一刀：删除 `workspace-navigation.test.ts` 中重复的班级维度老师绑定 state/选择器源码扫描；老师绑定请求、回滚、saving 状态和弹窗组装由 `teacherBindingRules.test.ts`、`classEditorModalState.test.ts` 与 `account-card.test.tsx` 继续覆盖。
- 已完成第 5 步第十二刀：删除 `workspace-navigation.test.ts` 中重复的班级保存/删除锁定期间防选择、防刷新源码扫描；异步锁定按钮接入由 `account-card.test.tsx` 继续覆盖，展开锁定和加载状态规则由 `classEditorStateRules.test.ts` 与 `loadPageRules.test.ts` 继续覆盖。
- 已完成第 5 步第十三刀：削减 `workspace-navigation.test.ts` 中紧凑卡片测试对 `loadPage` 请求版本实现写法的源码扫描；请求版本递增和 stale 判断由 `loadPageRules.test.ts` 继续覆盖，紧凑卡片外观壳暂时保留页面级守卫。
- 已完成第 5 步第十四刀：削减 `workspace-navigation.test.ts` 中班级筛选测试对筛选 state 名和 setter 写法的源码扫描；筛选行为、联动选项和问题卡片排序由 `classFilterRules.test.ts` 覆盖，页面测试只保留筛选规则接入、共享年级选项和弹窗年级控件守卫。
- 已完成第 5 步第十五刀：削减 `account-card.test.tsx` 中新建班级选老师测试对 `selectedTeacher` 局部变量写法的源码扫描；未选老师校验由 `classSaveRules.test.ts` 覆盖，老师绑定请求由 `teacherBindingRules.test.ts` 覆盖，页面测试只保留保存校验和新建后绑定接入。
- 已完成第 5 步第十六刀：削减 `account-card.test.tsx` 中老师绑定选择测试对 previous state、map 回滚和 class list 回滚实现串联的源码扫描；这些回滚行为由 `teacherBindingRules.test.ts` 覆盖，页面测试只保留选择框触发绑定、请求版本失效和绑定后刷新接入。
- 已完成第 5 步第十七刀：删除 `account-card.test.tsx` 中两条通过 `AppModule` 反查 `resolveTeacherBindingRollbackTeacherBindings` 的重复 map 回滚测试；map 回滚行为由 `teacherBindingRules.test.ts` 直接覆盖，页面测试不再依赖旧 re-export 入口验证同一行为。
- 已完成第 5 步第十八刀：删除 `account-card.test.tsx` 中两条通过 `AppModule` 反查 `resolveTeacherBindingRollbackClassItem` 的重复 class item 回滚测试；class item 回滚行为由 `teacherBindingRules.test.ts` 直接覆盖，页面测试不再依赖旧 re-export 入口验证同一行为。
- 已完成第 5 步第十九刀：删除 `account-card.test.tsx` 中两条只覆盖 `resolveAssignmentRollbackClassIds` 的旧测试，并同步删除 `App.tsx` 中仅供测试反查、生产代码未使用的 `resolveAssignmentRollbackClassIds` / `areClassIdListsEqual` 死代码。
- 已完成第 5 步第二十刀：新增 `workspaceShared.test.ts` 直接覆盖 `buildAuthedPath` 的真实 token 拼接行为，并削减 `workspace-navigation.test.ts` 对 `workspaceShared.ts` 内部 `getToken` 写法的源码盯梢；页面级测试只保留课程 PDF 链接接入守卫。
- 已完成第 5 步第二十一刀：继续扩展 `workspaceShared.test.ts` 直接覆盖 `getToken` 和 storage 包装函数容错行为，并削减 `app-storage-guard.test.tsx` 对 `workspaceShared.ts` 内部 storage 读法和导出写法的源码盯梢；App 守卫测试只保留不直接读写 auth storage 的边界。
- 已完成第 5 步第二十二刀：继续扩展 `workspaceShared.test.ts` 直接覆盖共享卡片 class 导出值的暗色模式样式，并删除 `account-card.test.tsx` 对 `workspaceShared.ts` 源码字符串的读取和正则盯梢；账号卡片测试只保留自身渲染和工作台壳层守卫。
- 已完成第 5 步第二十三刀：把 `workspace-dashboard.test.tsx` 中“不要从 App 导入共享样式”的源码正则，替换为组件真实渲染契约测试：`WorkspaceDashboard` 必须使用 shell 传入的 `styles.pageClass/cardClass/primaryButtonClass`；同时删除对 `WorkspaceDashboard.tsx` 源码文件的读取。
- 已完成第 5 步第二十四刀：削减 `workspace-dashboard.test.tsx` 中与当前组件无关的 App 源码文案盯梢；Dashboard 文案测试只检查 `WorkspaceDashboard` 自身真实渲染出的 AI 标签，不再顺手读取 `App.tsx` 检查复习生成页面文案。
- 已完成第 5 步第二十五刀：把 `landing-legal-pages.test.tsx` 中检查残留 `˜` 字符的源码扫描，改为检查 `LandingPage` 真实渲染出的 markup；同时删除该测试文件对 `App.tsx` 源码读取的依赖。
- 已完成第 5 步第二十六刀：先对 `organization-auth.test.tsx` 做降噪收拢，`App.tsx` 源码只读取一次，并抽出 `getApprovalPageSource()` 复用审批页源码块；当前覆盖面不变，后续再考虑把组织审批/邀请逻辑抽成规则测试。
- 已完成第 5 步第二十七刀：删除 `review-generation-async.test.tsx` 中 3 条重复源码盯梢；异步字段、pending/failed/转写文案、ready 必须有 PDF 的逻辑已由 `reviewGenerationAsync.test.ts` 真实规则测试覆盖，页面级测试保留轮询、归一化接入、创建成功和重复上传提示等接入守卫。
- 已完成第 5 步第二十八刀：继续删除 `review-generation-async.test.tsx` 中 2 条与 `workspace-navigation.test.ts` 重复的源码盯梢；创建成功关闭 composer/刷新历史、重复上传提示和高亮传参由导航测试覆盖，该文件只保留异步轮询、归一化接入和成员班级同步守卫。
- 已完成第 5 步第二十九刀：把 `class-feedback-generation.test.tsx` 中 `ClassFeedbackGenerationWorkspace` 共享样式 helper 的源码正则，改成真实渲染 markup 断言；现在检查卡片、软卡片、输入框、控制栏、主/次按钮样式和文案输出，减少对内部变量拼法的依赖。
- 已完成第 5 步第三十刀：继续削减 `class-feedback-generation.test.tsx` 对 `ClassFeedbackGenerationWorkspace.tsx` 的源码读取，把 header 布局和 `headerAside` 插槽断言改为真实渲染 markup 检查；该测试文件不再读取 `ClassFeedbackGenerationWorkspace.tsx` 源码。
- 第 5 步阶段审信：剩余源码扫描不再按数量硬砍，先分成三类处理。边界守卫类暂时保留；组织审批、复习生成、班级反馈、课程日历等业务编排类，需要先抽规则/组件再替换；`account-card.test.tsx`、`class-management-invite.test.tsx`、`smart-wrong-questions.test.ts` 等大页面测试，等页面继续拆分后再升级。

优先级：中

状态：阶段收尾

## DEBT-003：业务组件缺少调用章程

位置：

- `docs/ricardo-components/`
- `frontend/src/components/`

问题：

- 组件有名字，但如果没有调用规则，后续不同人或 AI 可能自由发挥。

风险：

- 同一类筛选组件被重复实现。
- UI 形态和交互口径逐渐分裂。

建议解决方式：

- 建立 Ricardo 组件库使用章程。
- 每个组件固定记录编号、中文名、英文名、使用效果、调用前必问问题、禁改点和已使用页面。

优先级：高

状态：部分处理

## DEBT-004：权限判断和展示逻辑混在一起

位置：

- 先聚焦 `frontend/src/App.tsx` 里的学管中心。

问题：

- 页面中直接出现 `hasOwnerAccess(...)`、`hasStaffAccess(...)`、`currentUser.role` 等判断。
- 展示层和权限层混在一起。

风险：

- 后续新增角色或调整权限时，需要到页面里到处找。
- 普通教师、机构负责人、超级管理员的视图差异容易漏。

建议解决方式：

- 先在学管中心建 `permissions.ts`。
- 页面只使用统一权限对象。
- 先只做权限判断层，不顺手拆页面、不重写 UI。
- 权限对象要覆盖普通教师、机构负责人、超级管理员的视图差异。
- 权限对象至少回答：统计卡片显示范围、班级/学员列表可见范围、筛选默认范围、按钮操作权限。
- 已完成第一小步：`frontend/src/features/student-center/permissions.ts` 和 `permissions.test.ts` 已建立。
- 已集中接入：成员/老师绑定数据加载权限、普通教师数据范围、全机构筛选范围、统计卡片分支、新建班级入口、负责老师编辑入口、班级/学员范围标签。
- 后续新增学管中心权限时，先扩展权限对象，不直接在页面写角色判断。

优先级：高

状态：部分处理

## DEBT-005：班级命名规则需要全站统一

位置：

- 当前主要散落在学管中心相关代码。
- 后续会影响咨询页面、班级认领、课表、反馈等页面。

问题：

- 班级显示名、年级、入学年份、学段、衔接班等规则是业务规则，不应该由各页面各自实现。

风险：

- 同一个班级在不同页面显示不一致。
- 暑期升年级、衔接班、毕业年级换老师等逻辑难以统一。

建议解决方式：

- 新建 `frontend/src/domain/classNaming.ts`。
- 全站逐步改为调用统一函数。
- 已完成阶段接入：学管中心、课程日历、咨询页当前班级选择、班级认领、反馈页和账号审批负责班级摘要等当前正式班级展示位置已接入统一规则。
- 后续遇到新页面或新展示位置时，先判断是否是“通过班级 ID 展示当前正式课程名”；如果是，按班型接入命名规则 1 或命名规则 2。

已确认口径：

- 命名规则 1：班课命名规则，用于多人班课，有班号。
- 命名规则 2：小课命名规则，用于 `1v1`、`1v2`、`1v3`，没有班号，用学生标识。
- 班课页面展示层：默认显示 `学科·年级·班号班`，例如 `数学·四年级·1班`。
- 班课权限判断层：可打开“入学年份”，显示 `学科·学段入学年份级·年级·班号班`，例如 `数学·小2025级·四年级·1班`。
- 小课页面展示层：默认显示 `学科·班型·年级·学生标识`，例如 `数学·1v2·七年级·张李`。
- 小课权限判断层：可打开“入学年份”，显示 `学科·班型·学段入学年份级·年级·学生标识`，例如 `数学·1v2·初2025级·七年级·张李`。
- 文案统一：该开关和说明统一叫“入学年份”，不叫“入学年级”。
- 历史文本：历史快照、手动填写班级名、旧备注、别名匹配、小程序/家长端兼容字段不自动改名，归入历史记录或兼容文本范围，暂不触碰。
- 数据联动：学管中心改了当前班级/小课信息后，所有通过班级 ID 展示的当前正式名称应自动跟随变化。

优先级：高

状态：阶段完成

## DEBT-006：Ricardo Component Lab 是静态 HTML

位置：

- `docs/ricardo-components/lab/index.html`

问题：

- 当前 Lab 是静态 HTML 草稿，不是真实 React 组件渲染。

风险：

- 长期看可能和真实组件出现细微差异。

建议解决方式：

- 短期保留静态 Lab，方便 Ricardo 直接查看效果。
- 长期可以建立 React 版内部预览路由或 Storybook 类页面。

优先级：低

状态：暂缓

## DEBT-007：治理路线容易被自动跳步

位置：

- `docs/refactor-roadmap.md`
- 后续所有“继续 Ricardo 治理路线”的接力场景。

问题：

- 如果路线图只写“下一步”，AI 可能在读取后直接进入核心代码。
- Ricardo 的真实意图可能只是继续补文档、确认方案或复盘风险。

风险：

- 还没对齐就修改核心代码。
- 文档、规则、页面拆分混在同一轮里推进，后续更难接力。

建议解决方式：

- 路线图中明确“唤醒后先汇报，不自动执行”。
- 每一步都写状态、完成标准和开始条件。
- Ricardo 明确说“开始第 X 步”后，才进入对应代码修改。

优先级：高

状态：已处理

## DEBT-008：分支和 worktree 需要按抽屉规则管理

位置：

- 本地 git 分支。
- 本地 git worktree。
- `docs/refactor-roadmap.md`
- `AGENTS.md`

问题：

- 多个 AI 会话或多条工作线并行时，分支如果只靠临时记忆，很容易散落。
- 工作分支、备份分支、集成分支和发布分支如果用途混在一起，后续很难判断能不能删、能不能合、能不能继续开发。

风险：

- 在错误分支上继续开发。
- 把过期分支直接合回 `develop`，带回旧行为。
- 删除还被 worktree 占用或仍有价值的分支。

建议解决方式：

- 以 `AGENTS.md` 的分支策略作为硬规则。
- 在 `docs/refactor-roadmap.md` 中保留 Ricardo 接力版“分支抽屉规则”。
- 分支按用途进入固定前缀：`work/`、`backup/`、`integrate/`、`release/`。
- 清理分支前先确认是否已合入、是否有 worktree 占用、是否有未保存工作。

当前状态：

- `master` 和 `develop` 属于核心分支。
- `backup/develop-before-consultation-merge-20260522164356` 已按备份抽屉放置。
- `work/consultation-card-info-layout` 和 `work/consultation-meeting-followup` 已按工作抽屉放置。
- `work/consultation-meeting-followup` 当前被另一个 worktree 占用，处理前要先确认对应 worktree。

优先级：中

状态：已建立规则
