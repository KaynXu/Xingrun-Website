import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');
const sidebarSource = readFileSync(new URL('./features/navigation/Sidebar.tsx', import.meta.url), 'utf8');
const headerSource = readFileSync(new URL('./features/navigation/Header.tsx', import.meta.url), 'utf8');
const shellSource = readFileSync(new URL('./features/navigation/WorkspaceShellLayout.tsx', import.meta.url), 'utf8');
const contentSource = readFileSync(new URL('./features/navigation/WorkspacePageContent.tsx', import.meta.url), 'utf8');
const accessSource = readFileSync(new URL('./features/navigation/workspaceAccess.ts', import.meta.url), 'utf8');
const appDisplaySource = readFileSync(new URL('./appDisplay.ts', import.meta.url), 'utf8');
const appTypesSource = readFileSync(new URL('./appTypes.ts', import.meta.url), 'utf8');
const workspaceRoutesSource = readFileSync(new URL('./features/navigation/workspaceRoutes.ts', import.meta.url), 'utf8');
const reviewGenerationSource = readFileSync(new URL('./features/review-generation/ReviewGenerationPage.tsx', import.meta.url), 'utf8');
const lessonInputSource = readFileSync(new URL('./features/review-generation/LessonInput.tsx', import.meta.url), 'utf8');
const creditCenterSource = readFileSync(new URL('./features/credits/CreditCenterPage.tsx', import.meta.url), 'utf8');
const settingsSource = readFileSync(new URL('./features/settings/SettingsPage.tsx', import.meta.url), 'utf8');
const approvalPageSource = readFileSync(new URL('./features/approval/ApprovalPage.tsx', import.meta.url), 'utf8');
const authHookSource = readFileSync(new URL('./features/auth/useWorkspaceAuthState.ts', import.meta.url), 'utf8');
const consultationPageSource = readFileSync(new URL('./features/consultation/ConsultationPage.tsx', import.meta.url), 'utf8');
const consultationModalSource = readFileSync(new URL('./features/consultation/ConsultationModal.tsx', import.meta.url), 'utf8');
const consultationSharedSource = readFileSync(new URL('./features/consultation/consultationShared.tsx', import.meta.url), 'utf8');
const calendarWorkspaceSource = readFileSync(new URL('./features/calendar/CalendarWorkspacePage.tsx', import.meta.url), 'utf8');
const studentCenterSource = readFileSync(new URL('./features/student-center/StudentCenterPage.tsx', import.meta.url), 'utf8');
const classManagementTabSource = readFileSync(new URL('./features/student-center/ClassManagementTab.tsx', import.meta.url), 'utf8');
const classEditorModalSource = readFileSync(new URL('./features/student-center/ClassEditorModal.tsx', import.meta.url), 'utf8');

function requireMatch(source: string, pattern: RegExp): string {
  const match = source.match(pattern);
  assert.ok(match);
  return match[0];
}

test('workspace navigation wires consultation and calendar pages into the shell', () => {
  const sidebarBlock = sidebarSource;

  assert.match(appSource, /type Page = WorkspacePage;/);
  assert.match(sidebarBlock, /id: 'class-feedback-generation'[\s\S]*label: '课堂反馈'/);
  assert.match(appSource, /'class-feedback-generation': '课堂反馈'/);
  assert.doesNotMatch(sidebarBlock, /id: 'student-tasks'/);
  assert.doesNotMatch(appSource, /'student-tasks': '学生端今日任务'/);
  assert.doesNotMatch(appSource, /activeWorkspacePage === 'student-tasks'/);
  assert.match(sidebarBlock, /id: 'consultation'[\s\S]*label: '咨询记录'/);
  assert.match(appSource, /consultation: '咨询记录'/);
  assert.match(contentSource, /activeWorkspacePage === 'consultation'[\s\S]*<ConsultationPageComponent currentUser=\{currentUser\}/);
  assert.match(sidebarBlock, /id: 'calendar'[\s\S]*label: '课程日历'/);
  assert.match(appSource, /calendar: '课程日历'/);
  assert.match(contentSource, /import \{ CalendarWorkspacePage \} from '\.\.\/calendar\/CalendarWorkspacePage';/);
  assert.match(contentSource, /activeWorkspacePage === 'calendar'[\s\S]*<CalendarWorkspacePage currentUser=\{currentUser\} \/>/);
  assert.match(calendarWorkspaceSource, /export function CalendarWorkspacePage\(\{ currentUser \}: \{ currentUser: CurrentUser \}\)/);
  assert.doesNotMatch(appSource, /QuestionBank/);
});

test('review generation source replaces separate lesson input and library pages with one review-generation workspace page', () => {
  const sidebarBlock = sidebarSource;

  assert.match(sidebarBlock, /id: 'review-generation'[\s\S]*label: '复习生成'/);
  assert.doesNotMatch(sidebarBlock, /id: 'input'[\s\S]*label:/);
  assert.doesNotMatch(sidebarBlock, /id: 'library'[\s\S]*label:/);
  assert.match(appSource, /'review-generation': '复习生成'/);
  assert.match(appSource, /import \{ WorkspacePageContent \} from '\.\/features\/navigation\/WorkspacePageContent';/);
  assert.match(contentSource, /import \{ ReviewGenerationPage \} from '\.\.\/review-generation\/ReviewGenerationPage';/);
  assert.match(contentSource, /activeWorkspacePage === 'review-generation'[\s\S]*<ReviewGenerationPage[\s\S]*onSuccess=\{handleReviewGenerationSuccess\}[\s\S]*renderLessonInput=\{\(handleFormSuccess\) => \(/);
  assert.match(contentSource, /<LessonInput onSuccess=\{handleFormSuccess\} currentUser=\{currentUser\} \/>/);
  assert.doesNotMatch(appSource, /activePage === 'input'/);
  assert.doesNotMatch(appSource, /activePage === 'library'/);
});

test('review generation source defaults to history documents and expands the shared composer from the primary CTA', () => {
  assert.match(reviewGenerationSource, /const \[composerOpen, setComposerOpen\] = useState\(false\);/);
  assert.match(reviewGenerationSource, /<h3 className=\{workspaceSectionTitleClass\}>历史文档<\/h3>/);
  assert.match(reviewGenerationSource, /inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl bg-slate-950 px-5 py-3 font-semibold text-white shadow-none transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60/);
  assert.match(reviewGenerationSource, /新建/);
  assert.match(reviewGenerationSource, /生成复习文档/);
  assert.match(reviewGenerationSource, /<ReviewDocumentHistory refreshToken=\{historyRefreshToken\} highlightedLessonId=\{highlightedLessonId\} \/>/);
});

test('review generation source closes the shared composer after successful generation and refreshes history', () => {
  assert.match(reviewGenerationSource, /const handleFormSuccess = \(result: ReviewPlanCreateResult\) => \{\s*setComposerOpen\(false\);\s*setHighlightedLessonId\(result\.id\);[\s\S]*setHistoryRefreshToken\(\(current\) => current \+ 1\);\s*onSuccess\(\);\s*\};/);
  assert.match(reviewGenerationSource, /这份录音已处理过，已复用已有复习文档/);
  assert.doesNotMatch(reviewGenerationSource, /setActivePage\('library'\)/);
});

test('review generation source removes continue-edit-feedback entry points from composer and history actions', () => {
  assert.doesNotMatch(reviewGenerationSource, /selectedLessonForFeedback/);
  assert.doesNotMatch(reviewGenerationSource, /继续编辑课后反馈/);
  assert.doesNotMatch(reviewGenerationSource, /onContinueFeedback/);
  assert.doesNotMatch(reviewGenerationSource, /继续编辑反馈/);
  assert.doesNotMatch(reviewGenerationSource, /<Pencil size=\{16\} \/>/);
});

test('review generation source renders history as a paginated list with explicit generation time', () => {
  assert.match(reviewGenerationSource, /const REVIEW_HISTORY_PAGE_SIZE = 12;/);
  assert.match(reviewGenerationSource, /const \[historyPage, setHistoryPage\] = useState\(1\);/);
  assert.match(reviewGenerationSource, /const totalHistoryPages = Math\.max\(1, Math\.ceil\(lessons\.length \/ REVIEW_HISTORY_PAGE_SIZE\)\);/);
  assert.match(reviewGenerationSource, /const paginatedLessons = lessons\.slice\(\(currentHistoryPage - 1\) \* REVIEW_HISTORY_PAGE_SIZE, currentHistoryPage \* REVIEW_HISTORY_PAGE_SIZE\);/);
  assert.match(reviewGenerationSource, /if \(highlightedLessonId\) \{[\s\S]*setHistoryPage\(Math\.floor\(highlightedIndex \/ REVIEW_HISTORY_PAGE_SIZE\) \+ 1\);[\s\S]*setHistoryPage\(1\);[\s\S]*\}, \[highlightedLessonId, lessons\]\);/);
  assert.match(reviewGenerationSource, /highlightedLessonId === lesson\.id/);
  assert.match(reviewGenerationSource, /生成时间/);
  assert.match(reviewGenerationSource, /function getLessonCreatedTimeLabel\(lesson: ReviewLessonRecord\): string \{/);
  assert.match(reviewGenerationSource, /return createdAt\.toLocaleTimeString\('zh-CN', \{ hour12: false \}\);/);
  assert.match(reviewGenerationSource, /grid-cols-\[minmax\(0,2fr\)_128px_132px_180px_112px_132px\]/);
  assert.match(reviewGenerationSource, /<ul className="divide-y divide-slate-200\/70 dark:divide-white\/10">/);
  assert.match(reviewGenerationSource, /上一页/);
  assert.match(reviewGenerationSource, /下一页/);
  assert.doesNotMatch(reviewGenerationSource, /grid gap-4 lg:grid-cols-2 xl:grid-cols-3/);
  assert.doesNotMatch(reviewGenerationSource, /<article/);
});

test('lesson input source keeps subject class and date controls in a fluid grid without fixed width clashes', () => {
  assert.match(lessonInputSource, /className="grid gap-3 md:grid-cols-\[minmax\(0,1\.4fr\)_minmax\(0,1fr\)_minmax\(0,0\.9fr\)\]"/);
  assert.match(lessonInputSource, /reviewFormFieldClass = `\$\{workspaceFieldClass\} border-slate-200 focus:border-slate-300 focus:ring-slate-100`;/);
  assert.match(lessonInputSource, /className=\{`\$\{reviewFormFieldClass\} w-full`\}/);
  assert.doesNotMatch(lessonInputSource, /sm:w-40/);
  assert.doesNotMatch(appSource, /sm:w-32/);
});

test('review generation source requires class selection before generation and carries currentUser into LessonInput', () => {
  assert.match(lessonInputSource, /if \(!classId\) \{\s*setError\('请选择班级后再生成复习记录'\);\s*return;\s*\}/);
  assert.match(contentSource, /import \{ LessonInput \} from '\.\.\/review-generation\/LessonInput';/);
  assert.match(contentSource, /<LessonInput onSuccess=\{handleFormSuccess\} currentUser=\{currentUser\} \/>/);
  assert.doesNotMatch(reviewGenerationSource, /initialLesson=\{/);
  assert.match(contentSource, /activeWorkspacePage === 'review-generation'[\s\S]*<ReviewGenerationPage[\s\S]*onSuccess=\{handleReviewGenerationSuccess\}/);
});

test('review generation source submits same lesson supplemental materials', () => {
  assert.match(lessonInputSource, /sameLessonMaterials/);
  assert.match(lessonInputSource, /same_lesson_materials:\s*sameLessonMaterials/);
  assert.match(lessonInputSource, /同一节课补充材料/);
});

test('lesson input source refreshes assignable classes when the signed-in user changes so stale class options cannot trigger forbidden', () => {
  assert.match(lessonInputSource, /apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(lessonInputSource, /\}, \[currentUser\.id, currentUser\.role\]\);/);
});

test('review generation source appends auth token to lesson pdf links', () => {
  assert.match(reviewGenerationSource, /href=\{buildAuthedPath\(`\/api\/pdf\/\$\{lesson\.id\}`\)\}/);
  assert.match(reviewGenerationSource, /href=\{buildAuthedPath\(`\/api\/pdf\/download\/\$\{lesson\.id\}`\)\}/);
});

test('workspace navigation wires smart wrong questions into every authenticated role shell', () => {
  const sidebarBlock = sidebarSource;

  assert.match(accessSource, /export function canAccessSmartWrongQuestions\(role: WorkspaceRole\): boolean \{/);
  assert.match(accessSource, /return hasStaffAccess\(role\) \|\| role === 'member';/);
  assert.match(sidebarBlock, /showSmartWrongQuestions[\s\S]*id: 'smartWrongQuestions', icon: Cpu, label: '智能错题'/);
  assert.match(appSource, /smartWrongQuestions: '智能错题'/);
  assert.match(contentSource, /activeWorkspacePage === 'smartWrongQuestions'[\s\S]*canOpenWorkspacePage\(currentUser, 'smartWrongQuestions'\)[\s\S]*<SmartWrongQuestionsPage currentUser=\{currentUser\} \/>/);
});

test('workspace navigation removes the master data mappings page and keeps accounts focused on approval only', () => {
  const sidebarBlock = sidebarSource;

  assert.doesNotMatch(appSource, /MasterDataMappingsPage/);
  assert.doesNotMatch(appSource, /masterDataMappings/);
  assert.doesNotMatch(sidebarBlock, /老师与班级匹配/);
  assert.match(contentSource, /activeWorkspacePage === 'accounts'[\s\S]*<ApprovalPage currentUser=\{currentUser\}[\s\S]*\/>/);
  assert.doesNotMatch(appSource, /onStartBinding=\{handleStartMemberBinding\}/);
});

test('workspace navigation exposes a dedicated owner-only credit center page', () => {
  const sidebarBlock = sidebarSource;

  assert.match(sidebarBlock, /showCreditCenter[\s\S]*id: 'credit', icon: Bell, label: '积分中心'/);
  assert.match(appSource, /credit: '积分中心'/);
  assert.match(accessSource, /if \(page === 'credit'\) \{\s*return hasOwnerAccess\(user\.role\);\s*\}/);
  assert.match(contentSource, /activeWorkspacePage === 'credit' && hasOwnerAccess\(currentUser\.role\) && <CreditCenterPage currentUser=\{currentUser\} \/>/);
});

test('settings page source keeps account, avatar, and password sections without the old about block', () => {
  const settingsBlock = requireMatch(settingsSource, /export function SettingsPage\([\s\S]*?\n\}/);

  assert.match(settingsBlock, /<h3 className=\{workspaceSectionTitleClass\}>系统设置<\/h3>/);
  assert.match(settingsBlock, /更换头像/);
  assert.match(settingsBlock, /修改账号密码/);
  assert.match(settingsSource, /const avatarPresetNames = \[/);
  assert.match(settingsSource, /'stone'/);
  assert.match(settingsSource, /'clay'/);
  assert.match(settingsBlock, /xl:grid-cols-9/);
  assert.match(settingsBlock, /border-slate-300/);
  assert.match(settingsBlock, /settingsSecondaryButtonClass/);
  assert.match(settingsBlock, /settingsFieldClass/);
  assert.match(settingsBlock, /settingsPrimaryButtonClass/);
  assert.match(settingsBlock, /onCurrentUserUpdated/);
  assert.match(settingsBlock, /\/api\/profile\/avatar/);
  assert.match(settingsBlock, /\/api\/profile\/avatar-upload/);
  assert.match(settingsBlock, /\/api\/profile\/password/);
  assert.match(settingsBlock, /normalizeSettingsApiError/);
  assert.match(settingsSource, /本地后端还没更新到最新代码，请重启 5001 后端后再试/);
  assert.match(settingsBlock, /上传头像/);
  assert.doesNotMatch(settingsBlock, /退出登录/);
  assert.doesNotMatch(settingsBlock, /积分中心/);
  assert.doesNotMatch(settingsBlock, /关于/);
});

test('credit center page source supports member drilldown and ledger filtering', () => {
  const creditBlock = requireMatch(creditCenterSource, /export function CreditCenterPage\([\s\S]*?\n\}/);

  assert.match(creditBlock, /apiFetch<CreditOverview>\('\/api\/credits\/overview'\)/);
  assert.match(creditBlock, /apiFetch<\{ items: CreditLedgerItem\[] \}>\('\/api\/credits\/ledger\?limit=100'\)/);
  assert.match(creditBlock, /apiFetch<\{ items: CreditMemberUsageItem\[] \}>\('\/api\/credits\/member-usage'\)/);
  assert.match(creditBlock, /apiFetch<\{ items: CreditMemberUsageDetailItem\[] \}>\(`/);
  assert.match(creditBlock, /const \[selectedUsageUser, setSelectedUsageUser\] = useState<CreditMemberUsageItem \| null>\(null\);/);
  assert.match(creditCenterSource, /const CREDIT_USAGE_DETAIL_PAGE_SIZE = 5;/);
  assert.match(creditBlock, /const \[ledgerFilter, setLedgerFilter\] = useState<'all' \| 'credit' \| 'debit'>\('all'\);/);
  assert.match(creditCenterSource, /const CREDIT_LEDGER_PAGE_SIZE = 5;/);
  assert.match(creditBlock, /const \[usageDetailPage, setUsageDetailPage\] = useState\(1\);/);
  assert.match(creditBlock, /const \[ledgerPage, setLedgerPage\] = useState\(1\);/);
  assert.match(creditBlock, /const totalUsageDetailPages = Math\.max\(1, Math\.ceil\(usageDetailItems\.length \/ CREDIT_USAGE_DETAIL_PAGE_SIZE\)\);/);
  assert.match(creditBlock, /const currentUsageDetailPage = Math\.min\(usageDetailPage, totalUsageDetailPages\);/);
  assert.match(
    creditBlock,
    /const paginatedUsageDetailItems = usageDetailItems\.slice\(\s*\(currentUsageDetailPage - 1\) \* CREDIT_USAGE_DETAIL_PAGE_SIZE,\s*currentUsageDetailPage \* CREDIT_USAGE_DETAIL_PAGE_SIZE,\s*\);/,
  );
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

test('workspace navigation source exposes classes management through configurable page visibility', () => {
  const classManagementBlock = `${studentCenterSource}\n${classManagementTabSource}\n${classEditorModalSource}`;
  const sidebarBlock = sidebarSource;

  assert.match(appSource, /type Page =[\s\S]*'classes'[\s\S]*;/);
  assert.match(accessSource, /export const configurableWorkspacePages/);
  assert.match(accessSource, /export function canOpenWorkspacePage\(user: VisiblePageUser, page: WorkspacePage\): boolean \{/);
  assert.match(sidebarBlock, /\.filter\(\(item\) => canOpenPage\(item\.id\)\)/);
  assert.match(sidebarBlock, /id: 'classes'[\s\S]*label: '学管中心'/);
  assert.match(appSource, /classes: '学管中心'/);
  assert.match(accessSource, /return canOpenWorkspacePage\(user, page\) \? page : 'dashboard';/);
  assert.match(contentSource, /activeWorkspacePage === 'classes' && canOpenWorkspacePage\(currentUser, 'classes'\) &&[\s\S]*<StudentCenterPage currentUser=\{currentUser\}/);
  assert.match(classManagementBlock, /label: '班级管理'/);
  assert.match(classManagementBlock, /负责老师/);
  assert.doesNotMatch(classManagementBlock, /成员班级分配/);
});

test('workspace navigation falls back when the selected page is not allowed for the current role', () => {
  assert.match(accessSource, /export function getWorkspacePageFallback\(user: VisiblePageUser, page: WorkspacePage\): WorkspacePage \{/);
  assert.match(accessSource, /return canOpenWorkspacePage\(user, page\) \? page : 'dashboard';/);
  assert.match(appSource, /const activeWorkspacePage = currentUser \? getWorkspacePageFallback\(currentUser, activePage\) : activePage;/);
  assert.match(authHookSource, /setCurrentUser\(user\);/);
  assert.match(appSource, /const navigateWorkspacePage = useCallback\(\(page: Page\) => \{/);
  assert.match(appSource, /setActivePage\(getWorkspacePageFallback\(currentUser, page\)\);/);
  assert.match(shellSource, /setActivePage=\{onNavigatePage\}/);
  assert.match(appSource, /title=\{pageTitle\[activeWorkspacePage\]\}/);
  assert.match(contentSource, /key=\{activeWorkspacePage\}/);
  assert.match(contentSource, /activeWorkspacePage === 'review-generation' && canOpenWorkspacePage\(currentUser, 'review-generation'\)/);
  assert.match(contentSource, /activeWorkspacePage === 'class-feedback-generation' && canOpenWorkspacePage\(currentUser, 'class-feedback-generation'\)/);
  assert.match(contentSource, /activeWorkspacePage === 'consultation' && canOpenWorkspacePage\(currentUser, 'consultation'\)/);
  assert.match(contentSource, /activeWorkspacePage === 'calendar' && canOpenWorkspacePage\(currentUser, 'calendar'\)/);
});

test('workspace navigation source syncs authenticated tabs to pathname-based routes', () => {
  assert.match(workspaceRoutesSource, /dashboard: '\/workspace'/);
  assert.match(workspaceRoutesSource, /'review-generation': '\/workspace\/review-generation'/);
  assert.match(workspaceRoutesSource, /smartWrongQuestions: '\/workspace\/smart-wrong-questions'/);
  assert.match(workspaceRoutesSource, /export function getWorkspacePageFromPathname\(pathname: string\): WorkspacePage \| null \{/);
  assert.match(workspaceRoutesSource, /export function getWorkspacePath\(page: WorkspacePage\): string \{/);
  assert.match(appSource, /getWorkspacePageFromPathname/);
  assert.match(appSource, /window\.history\.pushState\(\{\}, '', nextPath\);/);
  assert.match(appSource, /window\.history\.replaceState\(\{\}, '', nextPath\);/);
  assert.match(appSource, /window\.addEventListener\('popstate', syncWorkspacePageFromHistory\);/);
});

test('workspace navigation keeps role and unauthenticated permission paths explicit', () => {
  assert.match(accessSource, /export function hasOwnerAccess\(role: WorkspaceRole\): boolean \{\s*return role === 'super_owner' \|\| role === 'owner';\s*\}/);
  assert.match(accessSource, /export function hasStaffAccess\(role: WorkspaceRole\): boolean \{\s*return hasOwnerAccess\(role\) \|\| role === 'admin';\s*\}/);
  assert.match(accessSource, /if \(page === 'credit'\) \{\s*return hasOwnerAccess\(user\.role\);\s*\}/);
  assert.match(accessSource, /if \(page === 'accounts'\) \{\s*return hasStaffAccess\(user\.role\);\s*\}/);
  assert.match(accessSource, /if \(page === 'smartWrongQuestions' && !canAccessSmartWrongQuestions\(user\.role\)\) \{\s*return false;\s*\}/);
  assert.match(appSource, /if \(!token \|\| !currentUser \|\| showLanding \|\| landingLegalPage\) \{/);
});

test('workspace navigation source exposes explicit super owner hierarchy for account controls', () => {
  assert.match(appSource, /import type \{[\s\S]*Role,[\s\S]*\} from '\.\/appTypes';/);
  assert.match(appTypesSource, /export type Role = 'super_owner' \| 'owner' \| 'admin' \| 'member';/);
  assert.match(appSource, /import \{ getRoleLabel \} from '\.\/appDisplay';/);
  assert.match(appDisplaySource, /if \(role === 'super_owner'\) return '超级管理员';/);
  assert.match(appDisplaySource, /if \(role === 'owner'\) return '机构负责人';/);
  assert.match(accessSource, /export function hasOwnerAccess\(role: WorkspaceRole\): boolean \{/);
  assert.match(approvalPageSource, /function canManageOwnerRole\(role: Role\): boolean \{/);
  assert.match(approvalPageSource, /超级管理员可以设置或撤销机构负责人；机构负责人只可切换管理员与普通成员权限；管理员可调整成员可见页面/);
});

test('class management source wires class filter rules and shared grade controls', () => {
  const classManagementBlock = studentCenterSource;

  assert.match(classManagementBlock, /const classSubjectFilterOptions = classFilterOptions\.subjectOptions;/);
  assert.match(studentCenterSource, /subjectOptions: academicSubjectOptions,/);
  assert.match(studentCenterSource, /const studentCenterGradeOptions = \[\.\.\.academicGradeOptions\];/);
  assert.match(classManagementBlock, /const filteredClasses = resolveFilteredClasses\(\{/);
  assert.match(classEditorModalSource, /value=\{newClass\.form\.current_grade\}/);
  assert.match(classEditorModalSource, /value=\{editingFormState\.current_grade \|\| editingFormState\.grade\}/);
  assert.doesNotMatch(appSource, /数学 3\.0/);
});

test('class management source keeps compact card single-expand shell', () => {
  const classManagementBlock = studentCenterSource;

  assert.match(classManagementBlock, /const \[expandedClassId, setExpandedClassId\] = useState<number \| 'new' \| null>/);
  assert.match(classManagementTabSource, /const isExpanded = expandedClassId === item\.id/);
  assert.match(classManagementTabSource, /grid gap-4 px-4 py-4 lg:grid-cols-\[minmax\(14rem,1\.25fr\)_minmax\(18rem,1fr\)_auto\]/);
  assert.match(classManagementTabSource, /`\$\{workspaceSoftCardClass\} overflow-hidden p-0 transition/);
});

test('consultation workspace source keeps adaptive layouts without a special compact sidebar mode', () => {
  const consultationBlock = consultationPageSource;

  assert.match(appSource, /mobileNavOpen/);
  assert.match(headerSource, /aria-label="打开导航"/);
  assert.match(shellSource, /className="fixed inset-0 z-40 lg:hidden"/);
  assert.match(consultationPageSource, /className="grid gap-4 p-4 sm:p-5 md:hidden"/);
  assert.match(consultationPageSource, /className="hidden md:block xl:hidden"/);
  assert.match(shellSource, /compact=\{false\}/);
  assert.doesNotMatch(shellSource, /const compactSidebar = activeWorkspacePage === 'calendar' \|\| activeWorkspacePage === 'consultation';/);
  assert.match(consultationPageSource, /className=\{`grid w-full gap-2 self-start lg:w-\[22rem\] lg:self-auto xl:w-\[24rem\] \$\{canManage \? 'grid-cols-3' : 'grid-cols-2'\}`\}/);
  assert.match(consultationPageSource, /className=\{`\$\{workspaceSecondaryButtonClass\} h-10 w-full min-w-0 !gap-1 !px-1 !py-2 text-\[11px\] sm:text-xs`\}/);
  assert.match(consultationPageSource, /className=\{`\$\{workspacePrimaryButtonClass\} h-10 w-full min-w-0 !gap-1 !px-1 !py-2 text-\[11px\] sm:text-xs`\}/);
  assert.match(consultationPageSource, /whitespace-nowrap/);
  assert.doesNotMatch(consultationBlock, /sm:min-w-\[126px\]/);
  assert.doesNotMatch(appSource, /overflow-x-auto/);
});

test('consultation workspace source shows source channel metadata and keeps the quick parse controls', () => {
  assert.match(consultationModalSource, /来源渠道主类/);
  assert.match(consultationSharedSource, /const sourceChannel = record\.source_channel \|\| '未标注来源渠道';/);
  assert.match(consultationPageSource, /record\.consultation_subject \|\| '未填写'/);
  assert.match(consultationModalSource, /快速录入/);
  assert.match(consultationModalSource, /智能解析/);
  assert.match(consultationModalSource, /来源渠道备注/);
  assert.match(consultationPageSource, /apiFetch<ConsultationTeacherOption\[]>\('\/api\/consultation-teachers'\)/);
});

test('consultation workspace source allows staff edits and uses the new follow-up status set', () => {
  assert.match(consultationModalSource, /follow_up_status: '待邀约',/);
  assert.match(accessSource, /export function hasStaffAccess\(role: WorkspaceRole\): boolean \{/);
  assert.match(consultationModalSource, /const canEdit = hasStaffAccess\(currentUser\.role\) \|\| currentUser\.role === 'member';/);
  assert.match(consultationModalSource, /\{readOnly && canEdit && \(/);
  assert.match(consultationPageSource, /const canManage = hasStaffAccess\(currentUser\.role\);/);
  assert.match(consultationPageSource, /const canEditConsultations = canManage \|\| currentUser\.role === 'member';/);
  assert.match(consultationPageSource, /onDelete=\{canManage \? handleDelete : undefined\}/);
});

test('approval page source keeps member role controls separate from class assignment', () => {
  const approvalBlock = requireMatch(approvalPageSource, /export function ApprovalPage\([\s\S]*?\n\}/);

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
