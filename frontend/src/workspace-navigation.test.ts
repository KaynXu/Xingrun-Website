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

  assert.match(appSource, /type Page = 'dashboard' \| 'review-generation' \| 'consultation' \| 'calendar' \| 'smartWrongQuestions' \| 'classes' \| 'accounts' \| 'settings';/);
  assert.match(sidebarBlock, /id: 'consultation'[\s\S]*label: '咨询记录'/);
  assert.match(appSource, /consultation: '咨询记录'/);
  assert.match(appSource, /activePage === 'consultation'[\s\S]*<ConsultationPage currentUser=\{currentUser\}/);
  assert.match(sidebarBlock, /id: 'calendar'[\s\S]*label: '课程日历'/);
  assert.match(appSource, /calendar: '课程日历'/);
  assert.match(appSource, /activePage === 'calendar'[\s\S]*<CourseCalendarPage/);
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
  assert.match(reviewGenerationBlock, /<ReviewDocumentHistory refreshToken=\{historyRefreshToken\} onContinueFeedback=\{handleStartEditingFeedback\} \/>/);
});

test('review generation source keeps the shared composer open after successful generation so feedback editing can continue inline', () => {
  const reviewGenerationBlock = requireMatch(/const ReviewGenerationPage = \(\{[\s\S]*?\n};/);

  assert.match(reviewGenerationBlock, /const \[selectedLessonForFeedback, setSelectedLessonForFeedback\] = useState<Lesson \| null>\(null\);/);
  assert.match(reviewGenerationBlock, /const handleFormSuccess = \(\) => \{\s*setSelectedLessonForFeedback\(null\);\s*setComposerOpen\(true\);\s*setHistoryRefreshToken\(\(current\) => current \+ 1\);\s*onSuccess\(\);\s*\};/);
  assert.doesNotMatch(reviewGenerationBlock, /setComposerOpen\(false\);\s*onSuccess\(\);/);
  assert.doesNotMatch(reviewGenerationBlock, /setActivePage\('library'\)/);
});

test('review generation source lets history rows reopen the shared composer for continuing teacher feedback', () => {
  const reviewGenerationBlock = requireMatch(/const ReviewGenerationPage = \(\{[\s\S]*?\n};/);
  const historyBlock = requireMatch(/const ReviewDocumentHistory = \(\{[\s\S]*?\n};/);

  assert.match(reviewGenerationBlock, /const handleStartEditingFeedback = \(lesson: Lesson\) => \{\s*setSelectedLessonForFeedback\(lesson\);\s*setComposerOpen\(true\);\s*\};/);
  assert.match(reviewGenerationBlock, /selectedLessonForFeedback \? '继续编辑课后反馈' : '生成复习文档'/);
  assert.match(historyBlock, /title=\{lesson\.class_id \? '继续编辑反馈' : '未关联班级，暂无法编辑反馈'\}/);
  assert.match(historyBlock, /onClick=\{\(\) => onContinueFeedback\?\.\(lesson\)\}/);
});

test('lesson input source keeps subject class and date controls in a fluid grid without fixed width clashes', () => {
  const lessonInputBlock = requireMatch(/const LessonInput = \(\{[\s\S]*?initialLesson\?: Lesson \| null;[\s\S]*?\n};/);
  const subjectComboboxBlock = requireMatch(/const SubjectCombobox = \([\s\S]*?\n};/);

  assert.match(lessonInputBlock, /className="grid gap-3 md:grid-cols-\[minmax\(0,1\.4fr\)_minmax\(0,1fr\)_minmax\(0,0\.9fr\)\]"/);
  assert.match(lessonInputBlock, /className=\{`\$\{workspaceFieldClass\} w-full`\}/);
  assert.doesNotMatch(lessonInputBlock, /sm:w-40/);
  assert.doesNotMatch(subjectComboboxBlock, /sm:w-32/);
});

test('review generation source requires class selection before generation and carries currentUser plus initialLesson into LessonInput', () => {
  const lessonInputBlock = requireMatch(/const LessonInput = \(\{[\s\S]*?initialLesson\?: Lesson \| null;[\s\S]*?\n};/);
  const reviewGenerationBlock = requireMatch(/const ReviewGenerationPage = \(\{[\s\S]*?\n};/);

  assert.match(lessonInputBlock, /if \(!classId\) \{\s*setError\('请选择班级后再生成复习记录'\);\s*return;\s*\}/);
  assert.match(reviewGenerationBlock, /<LessonInput[\s\S]*onSuccess=\{handleFormSuccess\}[\s\S]*currentUser=\{currentUser\}[\s\S]*initialLesson=\{selectedLessonForFeedback\}[\s\S]*\/>/);
  assert.match(appSource, /activePage === 'review-generation'[\s\S]*<ReviewGenerationPage[\s\S]*onSuccess=\{handleReviewGenerationSuccess\}[\s\S]*currentUser=\{currentUser\}/);
});

test('lesson input source refreshes assignable classes when the signed-in user changes so stale class options cannot trigger forbidden', () => {
  const lessonInputBlock = requireMatch(/const LessonInput = \(\{[\s\S]*?initialLesson\?: Lesson \| null;[\s\S]*?\n};/);

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

test('workspace navigation source reserves classes management for owner and admin shells', () => {
  const classManagementBlock = requireMatch(/const ClassManagementPage = \(\{ currentUser \}: \{ currentUser: CurrentUser \}\) => \{[\s\S]*?\n};/);

  assert.match(appSource, /type Page = [^;]*'classes'[^;]*;/);
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
  assert.match(appSource, /const gradeFilterOptions\s*=\s*\['全部'\s*,\s*\.\.\.gradeOptions\s*\];/);
  assert.match(classManagementBlock, /const filteredClasses = classes\.filter\(\(item\) => \{/);
  assert.match(classManagementBlock, /if \(selectedGradeFilter === '全部'\) \{\s*return true;\s*\}/);
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
  assert.match(classManagementBlock, /type="radio"/);
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
  assert.doesNotMatch(approvalBlock, /成员班级分配/);
});
