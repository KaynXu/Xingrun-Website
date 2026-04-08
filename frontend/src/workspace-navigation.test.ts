import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

const fixedGradeValues = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三'];
const sharedGradeOptionsPattern = new RegExp(
  `const gradeOptions\\s*=\\s*\\[\\s*${fixedGradeValues.map((value) => `'${value}'`).join('\\s*,\\s*')}\\s*\\];`,
);

function requireMatch(pattern: RegExp): string {
  const match = appSource.match(pattern);
  assert.ok(match);
  return match[0];
}

test('workspace navigation wires consultation and calendar pages into the shell', () => {
  const sidebarBlock = requireMatch(/const menuItems = \[[\s\S]*?\n  \];/);

  assert.match(appSource, /type Page =[\s\S]*'dashboard'[\s\S]*'review-generation'[\s\S]*'class-feedback-generation'[\s\S]*'consultation'[\s\S]*'calendar'[\s\S]*'smartWrongQuestions'[\s\S]*'masterDataMappings'[\s\S]*'classes'[\s\S]*'accounts'[\s\S]*'credit'[\s\S]*'settings';/);
  assert.match(sidebarBlock, /id: 'class-feedback-generation'[\s\S]*label: '班级反馈生成'/);
  assert.match(appSource, /'class-feedback-generation': '班级反馈生成'/);
  assert.match(sidebarBlock, /id: 'consultation'[\s\S]*label: '咨询记录'/);
  assert.match(appSource, /consultation: '咨询记录'/);
  assert.match(appSource, /activePage === 'consultation'[\s\S]*<ConsultationPage currentUser=\{currentUser\}/);
  assert.match(sidebarBlock, /id: 'calendar'[\s\S]*label: '课程日历'/);
  assert.match(appSource, /calendar: '课程日历'/);
  assert.match(appSource, /activePage === 'calendar'[\s\S]*<CourseCalendarPage/);
  assert.match(sidebarBlock, /id: 'masterDataMappings'[\s\S]*label: '老师与班级匹配'/);
  assert.match(appSource, /masterDataMappings: '老师与班级匹配'/);
  assert.match(appSource, /activePage === 'masterDataMappings'[\s\S]*<MasterDataMappingsPage currentUser=\{currentUser\} focusUserId=\{masterDataFocusUserId\} \/>/);
  assert.doesNotMatch(appSource, /QuestionBank/);
});

test('review generation source replaces separate lesson input and library pages with one review-generation workspace page', () => {
  const sidebarBlock = requireMatch(/const menuItems = \[[\s\S]*?\n  \];/);

  assert.match(sidebarBlock, /id: 'review-generation'[\s\S]*label: '复习生成'/);
  assert.doesNotMatch(sidebarBlock, /id: 'input'[\s\S]*label:/);
  assert.doesNotMatch(sidebarBlock, /id: 'library'[\s\S]*label:/);
  assert.match(appSource, /'review-generation': '复习生成'/);
  assert.match(appSource, /activePage === 'review-generation'[\s\S]*<ReviewGenerationPage[\s\S]*onSuccess=\{handleReviewGenerationSuccess\}[\s\S]*currentUser=\{currentUser\}/);
  assert.doesNotMatch(appSource, /activePage === 'input'/);
  assert.doesNotMatch(appSource, /activePage === 'library'/);
});

test('review generation source defaults to history documents and expands the shared composer from the primary CTA', () => {
  const reviewGenerationBlock = requireMatch(/const ReviewGenerationPage = \(\{[\s\S]*?\n};/);

  assert.match(reviewGenerationBlock, /const \[composerOpen, setComposerOpen\] = useState\(false\);/);
  assert.match(reviewGenerationBlock, /<h3 className=\{workspaceSectionTitleClass\}>历史文档<\/h3>/);
  assert.match(reviewGenerationBlock, /新建复习文档/);
  assert.match(reviewGenerationBlock, /生成复习文档/);
  assert.match(reviewGenerationBlock, /<ReviewDocumentHistory refreshToken=\{historyRefreshToken\} \/>/);
});

test('review generation source keeps the shared composer open after successful generation and refreshes history', () => {
  const reviewGenerationBlock = requireMatch(/const ReviewGenerationPage = \(\{[\s\S]*?\n};/);

  assert.match(reviewGenerationBlock, /const handleFormSuccess = \(\) => \{\s*setComposerOpen\(true\);\s*setHistoryRefreshToken\(\(current\) => current \+ 1\);\s*onSuccess\(\);\s*\};/);
  assert.doesNotMatch(reviewGenerationBlock, /setComposerOpen\(false\);\s*onSuccess\(\);/);
  assert.doesNotMatch(reviewGenerationBlock, /setActivePage\('library'\)/);
});

test('review generation source removes continue-edit-feedback entry points from composer and history actions', () => {
  const reviewGenerationBlock = requireMatch(/const ReviewGenerationPage = \(\{[\s\S]*?\n};/);
  const historyBlock = requireMatch(/const ReviewDocumentHistory = \(\{[\s\S]*?\n};/);

  assert.doesNotMatch(reviewGenerationBlock, /selectedLessonForFeedback/);
  assert.doesNotMatch(reviewGenerationBlock, /继续编辑课后反馈/);
  assert.doesNotMatch(historyBlock, /onContinueFeedback/);
  assert.doesNotMatch(historyBlock, /继续编辑反馈/);
  assert.doesNotMatch(historyBlock, /<Pencil size=\{16\} \/>/);
});

test('review generation source renders history as paginated cards with explicit generation time', () => {
  const historyBlock = requireMatch(/const ReviewDocumentHistory = \(\{[\s\S]*?\n};/);

  assert.match(historyBlock, /const REVIEW_HISTORY_PAGE_SIZE = 12;/);
  assert.match(historyBlock, /const \[historyPage, setHistoryPage\] = useState\(1\);/);
  assert.match(historyBlock, /const totalHistoryPages = Math\.max\(1, Math\.ceil\(lessons\.length \/ REVIEW_HISTORY_PAGE_SIZE\)\);/);
  assert.match(historyBlock, /const paginatedLessons = lessons\.slice\(\(currentHistoryPage - 1\) \* REVIEW_HISTORY_PAGE_SIZE, currentHistoryPage \* REVIEW_HISTORY_PAGE_SIZE\);/);
  assert.match(historyBlock, /useEffect\(\(\) => \{\s*setHistoryPage\(1\);\s*\}, \[lessons\]\);/);
  assert.match(historyBlock, /生成时间/);
  assert.match(historyBlock, /new Date\(lesson\.created_at\)\.toLocaleString\('zh-CN'\)/);
  assert.match(historyBlock, /className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3"/);
  assert.match(historyBlock, /上一页/);
  assert.match(historyBlock, /下一页/);
  assert.doesNotMatch(historyBlock, /<table className=/);
});

test('lesson input source keeps subject class and date controls in a fluid grid without fixed width clashes', () => {
  const lessonInputBlock = requireMatch(/const LessonInput = \(\{[\s\S]*?currentUser: CurrentUser;[\s\S]*?\n};/);
  const subjectComboboxBlock = requireMatch(/const SubjectCombobox = \([\s\S]*?\n};/);

  assert.match(lessonInputBlock, /className="grid gap-3 md:grid-cols-\[minmax\(0,1\.4fr\)_minmax\(0,1fr\)_minmax\(0,0\.9fr\)\]"/);
  assert.match(lessonInputBlock, /className=\{`\$\{workspaceFieldClass\} w-full`\}/);
  assert.doesNotMatch(lessonInputBlock, /sm:w-40/);
  assert.doesNotMatch(subjectComboboxBlock, /sm:w-32/);
});

test('review generation source requires class selection before generation and carries currentUser into LessonInput', () => {
  const lessonInputBlock = requireMatch(/const LessonInput = \(\{[\s\S]*?currentUser: CurrentUser;[\s\S]*?\n};/);
  const reviewGenerationBlock = requireMatch(/const ReviewGenerationPage = \(\{[\s\S]*?\n};/);

  assert.match(lessonInputBlock, /if \(!classId\) \{\s*setError\('请选择班级后再生成复习记录'\);\s*return;\s*\}/);
  assert.match(reviewGenerationBlock, /<LessonInput[\s\S]*onSuccess=\{handleFormSuccess\}[\s\S]*currentUser=\{currentUser\}[\s\S]*\/>/);
  assert.doesNotMatch(reviewGenerationBlock, /initialLesson=\{/);
  assert.match(appSource, /activePage === 'review-generation'[\s\S]*<ReviewGenerationPage[\s\S]*onSuccess=\{handleReviewGenerationSuccess\}[\s\S]*currentUser=\{currentUser\}/);
});

test('lesson input source refreshes assignable classes when the signed-in user changes so stale class options cannot trigger forbidden', () => {
  const lessonInputBlock = requireMatch(/const LessonInput = \(\{[\s\S]*?currentUser: CurrentUser;[\s\S]*?\n};/);

  assert.match(lessonInputBlock, /apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(lessonInputBlock, /\}, \[currentUser\.id, currentUser\.role\]\);/);
});

test('review generation source appends auth token to lesson pdf links', () => {
  assert.match(appSource, /function buildAuthedPath\(path: string\): string \{/);
  assert.match(appSource, /const token = getToken\(\);/);
  assert.match(appSource, /href=\{buildAuthedPath\(`\/api\/pdf\/\$\{lesson\.id\}`\)\}/);
  assert.match(appSource, /href=\{buildAuthedPath\(`\/api\/pdf\/download\/\$\{lesson\.id\}`\)\}/);
});

test('workspace navigation wires smart wrong questions into every authenticated role shell', () => {
  const sidebarBlock = requireMatch(/const menuItems = \[[\s\S]*?\n  \];/);

  assert.match(appSource, /function canAccessSmartWrongQuestions\(role: Role\): boolean \{/);
  assert.match(appSource, /return hasStaffAccess\(role\) \|\| role === 'member';/);
  assert.match(sidebarBlock, /canAccessSmartWrongQuestions\(currentUser\.role\)[\s\S]*\{ id: 'smartWrongQuestions', icon: Cpu, label: '智能错题' \}/);
  assert.match(appSource, /smartWrongQuestions: '智能错题'/);
  assert.match(appSource, /activePage === 'smartWrongQuestions'[\s\S]*canAccessSmartWrongQuestions\(currentUser\.role\)[\s\S]*<SmartWrongQuestionsPage currentUser=\{currentUser\} \/>/);
});

test('workspace navigation removes the master data mappings page and keeps accounts focused on approval only', () => {
  const sidebarBlock = requireMatch(/const menuItems = \[[\s\S]*?\n  \];/);

  assert.doesNotMatch(appSource, /MasterDataMappingsPage/);
  assert.doesNotMatch(appSource, /masterDataMappings/);
  assert.doesNotMatch(sidebarBlock, /老师与班级匹配/);
  assert.match(appSource, /activePage === 'accounts'[\s\S]*<ApprovalPage currentUser=\{currentUser\} \/>/);
  assert.doesNotMatch(appSource, /onStartBinding=\{handleStartMemberBinding\}/);
});

test('workspace navigation exposes a dedicated owner-only credit center page', () => {
  const sidebarBlock = requireMatch(/const menuItems = \[[\s\S]*?\n  \];/);

  assert.match(sidebarBlock, /hasOwnerAccess\(currentUser\.role\) \? \[\{ id: 'credit', icon: [^,]+, label: '积分中心' \}\] : \[]/);
  assert.match(appSource, /credit: '积分中心'/);
  assert.match(appSource, /if \(page === 'credit' && !hasOwnerAccess\(user\.role\)\) \{\s*return 'dashboard';\s*\}/);
  assert.match(appSource, /activePage === 'credit' && hasOwnerAccess\(currentUser\.role\) && <CreditCenterPage currentUser=\{currentUser\} \/>/);
});

test('settings page source keeps only account and about sections after credit center extraction', () => {
  const settingsBlock = requireMatch(/const SettingsPage = \(\{ currentUser, onLogout \}: \{ currentUser: CurrentUser; onLogout: \(\) => void \}\) => \{[\s\S]*?\n};/);

  assert.match(settingsBlock, /<h3 className=\{workspaceSectionTitleClass\}>系统设置<\/h3>/);
  assert.match(settingsBlock, /当前账号/);
  assert.match(settingsBlock, /关于/);
  assert.doesNotMatch(settingsBlock, /积分中心/);
  assert.doesNotMatch(settingsBlock, /小红书订单兑换/);
  assert.doesNotMatch(settingsBlock, /成员用量/);
  assert.doesNotMatch(settingsBlock, /最近流水/);
});

test('credit center page source supports member drilldown and ledger filtering', () => {
  const creditBlock = requireMatch(/const CreditCenterPage = \(\{ currentUser \}: \{ currentUser: CurrentUser \}\) => \{[\s\S]*?\n};/);

  assert.match(creditBlock, /apiFetch<CreditOverview>\('\/api\/credits\/overview'\)/);
  assert.match(creditBlock, /apiFetch<\{ items: CreditLedgerItem\[] \}>\('\/api\/credits\/ledger\?limit=100'\)/);
  assert.match(creditBlock, /apiFetch<\{ items: CreditMemberUsageItem\[] \}>\('\/api\/credits\/member-usage'\)/);
  assert.match(creditBlock, /apiFetch<\{ items: CreditMemberUsageDetailItem\[] \}>\(`/);
  assert.match(creditBlock, /const \[selectedUsageUser, setSelectedUsageUser\] = useState<CreditMemberUsageItem \| null>\(null\);/);
  assert.match(creditBlock, /const CREDIT_USAGE_DETAIL_PAGE_SIZE = 5;/);
  assert.match(creditBlock, /const \[ledgerFilter, setLedgerFilter\] = useState<'all' \| 'credit' \| 'debit'>\('all'\);/);
  assert.match(creditBlock, /const CREDIT_LEDGER_PAGE_SIZE = 5;/);
  assert.match(creditBlock, /const \[usageDetailPage, setUsageDetailPage\] = useState\(1\);/);
  assert.match(creditBlock, /const \[ledgerPage, setLedgerPage\] = useState\(1\);/);
  assert.match(creditBlock, /const totalUsageDetailPages = Math\.max\(1, Math\.ceil\(usageDetailItems\.length \/ CREDIT_USAGE_DETAIL_PAGE_SIZE\)\);/);
  assert.match(creditBlock, /const currentUsageDetailPage = Math\.min\(usageDetailPage, totalUsageDetailPages\);/);
  assert.match(creditBlock, /const paginatedUsageDetailItems = usageDetailItems\.slice\(\(currentUsageDetailPage - 1\) \* CREDIT_USAGE_DETAIL_PAGE_SIZE, currentUsageDetailPage \* CREDIT_USAGE_DETAIL_PAGE_SIZE\);/);
  assert.match(creditBlock, /const filteredLedger = creditLedger\.filter\(/);
  assert.match(creditBlock, /const totalLedgerPages = Math\.max\(1, Math\.ceil\(filteredLedger\.length \/ CREDIT_LEDGER_PAGE_SIZE\)\);/);
  assert.match(creditBlock, /const currentLedgerPage = Math\.min\(ledgerPage, totalLedgerPages\);/);
  assert.match(creditBlock, /const paginatedLedger = filteredLedger\.slice\(\(currentLedgerPage - 1\) \* CREDIT_LEDGER_PAGE_SIZE, currentLedgerPage \* CREDIT_LEDGER_PAGE_SIZE\);/);
  assert.match(creditBlock, /useEffect\(\(\) => \{\s*setUsageDetailPage\(1\);\s*\}, \[selectedUsageUser, usageDetailItems\]\);/);
  assert.match(creditBlock, /useEffect\(\(\) => \{\s*setLedgerPage\(1\);\s*\}, \[ledgerFilter, creditLedger\]\);/);
  assert.match(creditBlock, /paginatedUsageDetailItems\.map\(\(item\) => \{/);
  assert.match(creditBlock, /paginatedLedger\.map\(\(item\) => \{/);
  assert.match(creditBlock, /成员明细/);
  assert.match(creditBlock, /流水筛选/);
  assert.match(creditBlock, /totalUsageDetailPages > 1/);
  assert.match(creditBlock, /totalLedgerPages > 1/);
  assert.match(creditBlock, /上一页/);
  assert.match(creditBlock, /下一页/);
});

test('workspace navigation source reserves classes management for owner and admin shells', () => {
  const classManagementBlock = requireMatch(/const ClassManagementPage = \(\{ currentUser \}: \{ currentUser: CurrentUser \}\) => \{[\s\S]*?\n};/);

  assert.match(appSource, /type Page =[\s\S]*'classes'[\s\S]*;/);
  assert.match(appSource, /hasStaffAccess\(currentUser\.role\)/);
  assert.match(appSource, /id: 'classes'[\s\S]*label: '班级管理'/);
  assert.match(appSource, /classes: '班级管理'/);
  assert.match(appSource, /activePage === 'classes'[\s\S]*<ClassManagementPage currentUser=\{currentUser\}/);
  assert.match(classManagementBlock, /apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(classManagementBlock, /apiFetch<UserItem\[]>\('\/api\/admin\/users'\)/);
  assert.match(classManagementBlock, /在这里统一管理 \{currentUser\.organization_name\} 的班级信息与负责老师安排。/);
  assert.match(classManagementBlock, /负责老师/);
  assert.doesNotMatch(classManagementBlock, /成员班级分配/);
});

test('workspace navigation source exposes explicit super owner hierarchy for account controls', () => {
  assert.match(appSource, /type Role = 'super_owner' \| 'owner' \| 'admin' \| 'member';/);
  assert.match(appSource, /if \(role === 'super_owner'\) return '超级管理员';/);
  assert.match(appSource, /if \(role === 'owner'\) return '机构负责人';/);
  assert.match(appSource, /function hasOwnerAccess\(role: Role\): boolean \{/);
  assert.match(appSource, /function canManageOwnerRole\(role: Role\): boolean \{/);
  assert.match(appSource, /超级管理员可以设置或撤销机构负责人；机构负责人只可切换管理员与普通成员权限/);
});

test('class management source guards selection and refresh during class save delete locks', () => {
  assert.match(appSource, /const classInteractionLocked = saving \|\| deleting;/);
  assert.match(appSource, /const classCardInteractionLocked = classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(appSource, /const pageRefreshLocked = classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(appSource, /const \[expandedClassId, setExpandedClassId\] = useState<number \| 'new' \| null>/);
  assert.match(appSource, /const \[formByClassId, setFormByClassId\] = useState<Record<string, ClassFormValues>>/);
  assert.match(appSource, /const handleToggleExpandedClass = \(classId: number \| 'new'\) => \{\s*if \(classCardInteractionLocked\) \{\s*return;\s*\}\s*setExpandedClassId\(\(current\) => current === classId \? null : classId\);\s*setFormError\(''\);\s*setAssignmentError\(''\);\s*\};/);
  assert.match(appSource, /onClick=\{\(\) => loadPage\(expandedClassId\)\.catch\(\(\) => undefined\)\}\s+disabled=\{pageRefreshLocked\}\s+className=\{workspaceSecondaryButtonClass\}/);
  assert.match(appSource, /onClick=\{\(\) => handleToggleExpandedClass\('new'\)\}\s+disabled=\{classCardInteractionLocked\}\s+className=\{workspacePrimaryButtonClass\}/);
  assert.match(appSource, /onClick=\{\(\) => handleToggleExpandedClass\(item\.id\)\}[\s\S]*disabled=\{classCardInteractionLocked\}/);
});

test('class management source adds a specific grade filter and reuses the shared fixed grade options', () => {
  const classManagementBlock = requireMatch(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.match(classManagementBlock, /const \[selectedGradeFilter, setSelectedGradeFilter\] = useState<string>\('全部'\)/);
  assert.match(appSource, sharedGradeOptionsPattern);
  assert.match(appSource, /const gradeFilterOptions\s*=\s*\['全部'\s*,\s*\.\.\.gradeOptions\s*,\s*'未绑定'\s*\];/);
  assert.match(classManagementBlock, /const filteredClasses = classes\.filter\(\(item\) => \{/);
  assert.match(classManagementBlock, /if \(selectedGradeFilter === '全部'\) \{\s*return true;\s*\}/);
  assert.match(classManagementBlock, /if \(selectedGradeFilter === '未绑定'\) \{\s*return item\.teacher_user_id == null;\s*\}/);
  assert.match(classManagementBlock, /<select[\s\S]*?value=\{newClassForm\.grade\}[\s\S]*?onChange=\{\(e\) => handleFieldChange\('new', 'grade', e\.target\.value\)\}/);
  assert.match(classManagementBlock, /<select[\s\S]*?value=\{formState\.grade\}[\s\S]*?onChange=\{\(e\) => handleFieldChange\(item\.id, 'grade', e\.target\.value\)\}/);
  assert.match(appSource, /gradeOptions\.includes\(\s*[^)]*grade[^)]*\)/);
  assert.match(appSource, /请选择年级/);
});

test('class management source uses class-centric teacher binding instead of user checkbox matrices', () => {
  const classManagementBlock = requireMatch(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.match(classManagementBlock, /apiFetch<\{ teacher_bindings: Record<number, number \| null> \}>\('\/api\/classes\/teacher-bindings'\)/);
  assert.match(classManagementBlock, /const \[teacherBindingByClassId, setTeacherBindingByClassId\] = useState<Record<number, number \| null>>\(\{\}\);/);
  assert.match(classManagementBlock, /const \[teacherBindingSavingByClassId, setTeacherBindingSavingByClassId\] = useState<Record<number, boolean>>\(\{\}\);/);
  assert.match(classManagementBlock, /const handleSelectTeacherForClass = async \(classId: number, teacherUserId: number\) => \{/);
  assert.match(classManagementBlock, /apiFetch\(`\/api\/classes\/\$\{classId\}\/teacher`, \{/);
  assert.doesNotMatch(classManagementBlock, /type="checkbox"/);
  assert.match(classManagementBlock, /placeholder="搜索老师"/);
  assert.match(classManagementBlock, /<select/);
});

test('class management source keeps refresh reconciliation non-destructive after successful mutations', () => {
  const classManagementBlock = requireMatch(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.match(appSource, /type LoadPageResult =/);
  assert.match(classManagementBlock, /const preserveStateOnError = options\?\.preserveStateOnError \?\? false;/);
  assert.match(classManagementBlock, /return \{ status: 'stale' \};/);
  assert.match(classManagementBlock, /return \{ status: 'success' \};/);
  assert.match(classManagementBlock, /return \{ status: 'refresh-error', error \};/);
  assert.match(classManagementBlock, /if \(!preserveStateOnError\) \{[\s\S]*setClasses\(\[\]\);[\s\S]*setUsers\(\[\]\);[\s\S]*setTeacherBindingByClassId\(\{\}\);/);
  assert.match(classManagementBlock, /const refreshResult = await loadPage\(classId, \{ preserveStateOnError: true \}\);/);
  assert.match(classManagementBlock, /const refreshResult = await loadPage\(created\.id, \{ preserveStateOnError: true \}\);/);
  assert.match(classManagementBlock, /班级和负责老师已保存，但列表刷新失败：/);
  assert.match(classManagementBlock, /老师绑定已保存，但列表刷新失败：/);
});

test('class management source adds compact card single-expand state and guards loadPage responses with a request version ref', () => {
  const classManagementBlock = requireMatch(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.match(classManagementBlock, /const \[expandedClassId, setExpandedClassId\] = useState<number \| 'new' \| null>/);
  assert.match(classManagementBlock, /const isExpanded = expandedClassId === item\.id/);
  assert.match(classManagementBlock, /setExpandedClassId\(\(current\) => current === classId \? null : classId\)/);
  assert.match(classManagementBlock, /<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">/);
  assert.match(classManagementBlock, /className=\{`\$\{workspaceSoftCardClass\} overflow-hidden p-5`\}/);
  assert.match(appSource, /const loadPageRequestVersionRef = useRef\(0\);/);
  assert.match(appSource, /const requestVersion = \+\+loadPageRequestVersionRef\.current;/);
  assert.match(appSource, /if \(requestVersion !== loadPageRequestVersionRef\.current\) \{\s*return \{ status: 'stale' \};\s*\}/);
});

test('consultation workspace source uses adaptive layouts instead of horizontal scrolling hacks', () => {
  assert.match(appSource, /mobileNavOpen/);
  assert.match(appSource, /aria-label="打开导航"/);
  assert.match(appSource, /className="fixed inset-0 z-40 lg:hidden"/);
  assert.match(appSource, /className="grid gap-4 p-4 sm:p-5 lg:grid-cols-2 2xl:hidden"/);
  assert.match(appSource, /className="hidden 2xl:block"/);
  assert.match(appSource, /whitespace-nowrap/);
  assert.doesNotMatch(appSource, /overflow-x-auto/);
});

test('consultation workspace source shows source channel metadata and keeps the quick parse controls', () => {
  assert.match(appSource, /来源渠道主类/);
  assert.match(appSource, /record\.source_channel \|\| '未标注来源渠道'/);
  assert.match(appSource, /record\.consultation_subject \|\| '未填写咨询科目'/);
  assert.match(appSource, /快速录入/);
  assert.match(appSource, /智能解析/);
  assert.match(appSource, /来源渠道备注/);
  assert.match(appSource, /apiFetch<ConsultationTeacherOption\[]>\('\/api\/consultation-teachers'\)/);
});

test('consultation workspace source allows staff edits and uses the new follow-up status set', () => {
  assert.match(appSource, /const consultationStatusOptions = \['待邀约', '跟进中', '已报班', '已劝退'\];/);
  assert.match(appSource, /follow_up_status: '待邀约',/);
  assert.match(appSource, /function hasStaffAccess\(role: Role\): boolean \{/);
  assert.match(appSource, /\{readOnly && hasStaffAccess\(currentUser\.role\) && \(/);
  assert.match(appSource, /const canManage = hasStaffAccess\(currentUser\.role\);/);
  assert.match(appSource, /\{canManage && \(/);
  assert.match(appSource, /onDelete=\{canManage \? handleDelete : undefined\}/);
});

test('approval page source keeps member role controls separate from class assignment', () => {
  const approvalBlock = requireMatch(/const ApprovalPage = \([\s\S]*?\n\};\n\nconst SettingsPage/);

  assert.match(approvalBlock, /成员权限/);
  assert.match(approvalBlock, /apiFetch<UserItem\[]>\('\/api\/admin\/users'\)/);
  assert.match(approvalBlock, /`\/api\/admin\/users\/\$\{userId\}\/role`/);
  assert.match(approvalBlock, /<div className="mt-3 space-y-2">/);
  assert.match(approvalBlock, /<div className="flex flex-wrap items-center gap-2">/);
  assert.match(approvalBlock, /<div className="flex items-center gap-2">/);
  assert.match(approvalBlock, /className=\{`\$\{workspaceFieldClass\} min-w-0 flex-1`\}/);
  assert.match(approvalBlock, /应用权限/);
  assert.doesNotMatch(approvalBlock, /成员班级分配/);
});
