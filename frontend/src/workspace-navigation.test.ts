import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');
const fixedGradeValues = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三'];
const sharedGradeOptionsPattern = new RegExp(
  `const gradeOptions\\s*=\\s*\\[\\s*${fixedGradeValues.map((value) => `'${value}'`).join('\\s*,\\s*')}\\s*\\];`,
);

test('workspace navigation wires consultation and calendar pages into the shell', () => {
  assert.match(appSource, /type Page = 'dashboard' \| 'review-generation' \| 'consultation' \| 'calendar' \| 'smartWrongQuestions' \| 'masterDataMappings' \| 'classes' \| 'accounts' \| 'settings';/);
  assert.match(appSource, /id: 'consultation'[\s\S]*label: '咨询记录'/);
  assert.match(appSource, /consultation: '咨询记录'/);
  assert.match(appSource, /activePage === 'consultation'[\s\S]*<ConsultationPage currentUser=\{currentUser\}/);
  assert.match(appSource, /id: 'calendar'[\s\S]*label: '课程日历'/);
  assert.match(appSource, /calendar: '课程日历'/);
  assert.match(appSource, /activePage === 'calendar'[\s\S]*<CourseCalendarPage/);

  assert.doesNotMatch(appSource, /题库浏览/);
  assert.doesNotMatch(appSource, /QuestionBank/);
});

test('review generation source replaces separate lesson input and library pages with one review-generation workspace page', () => {
  const sidebarBlock = appSource.match(/const menuItems = \[[\s\S]*?\n  \];/);

  assert.ok(sidebarBlock);
  assert.match(appSource, /type Page = 'dashboard' \| 'review-generation' \| 'consultation' \| 'calendar' \| 'smartWrongQuestions' \| 'masterDataMappings' \| 'classes' \| 'accounts' \| 'settings';/);
  assert.match(sidebarBlock[0], /id: 'review-generation'[\s\S]*label: '复习生成'/);
  assert.doesNotMatch(sidebarBlock[0], /id: 'input'[\s\S]*label: '添加课程'/);
  assert.doesNotMatch(sidebarBlock[0], /id: 'library'[\s\S]*label: '课程列表'/);
  assert.match(appSource, /'review-generation': '复习生成'/);
  assert.match(appSource, /activePage === 'review-generation'[\s\S]*<ReviewGenerationPage onSuccess=\{handleReviewGenerationSuccess\} \/>/);
  assert.doesNotMatch(appSource, /activePage === 'input'/);
  assert.doesNotMatch(appSource, /activePage === 'library'/);
});

test('review generation source defaults to 历史文档 and expands 生成复习文档 from 新建复习文档 CTA', () => {
  const reviewGenerationBlock = appSource.match(/const ReviewGenerationPage = \(\{ onSuccess \}: \{ onSuccess: \(\) => void \}\) => \{[\s\S]*?\n};/);

  assert.ok(reviewGenerationBlock);
  assert.match(reviewGenerationBlock[0], /const \[composerOpen, setComposerOpen\] = useState\(false\);/);
  assert.match(reviewGenerationBlock[0], /<h3 className=\{workspaceSectionTitleClass\}>历史文档<\/h3>/);
  assert.match(reviewGenerationBlock[0], /新建复习文档/);
  assert.match(reviewGenerationBlock[0], /生成复习文档/);
  assert.match(reviewGenerationBlock[0], /<ReviewDocumentHistory refreshToken=\{historyRefreshToken\} \/>/);
});

test('review generation source collapses the inline composer after successful generation', () => {
  const reviewGenerationBlock = appSource.match(/const ReviewGenerationPage = \(\{ onSuccess \}: \{ onSuccess: \(\) => void \}\) => \{[\s\S]*?\n};/);

  assert.ok(reviewGenerationBlock);
  assert.match(reviewGenerationBlock[0], /const handleComposerSuccess = \(\) => \{\s*setComposerOpen\(false\);\s*onSuccess\(\);\s*\};/);
  assert.doesNotMatch(reviewGenerationBlock[0], /setActivePage\('library'\)/);
});

test('lesson input source keeps subject class and date controls in a fluid grid without fixed width clashes', () => {
  const lessonInputBlock = appSource.match(/const LessonInput = \(\{ onSuccess \}: \{ onSuccess: \(\) => void \}\) => \{[\s\S]*?\n};/);
  const subjectComboboxBlock = appSource.match(/const SubjectCombobox = \([\s\S]*?\n};/);

  assert.ok(lessonInputBlock);
  assert.ok(subjectComboboxBlock);
  assert.match(lessonInputBlock[0], /className="grid gap-3 md:grid-cols-\[minmax\(0,1\.4fr\)_minmax\(0,1fr\)_minmax\(0,0\.9fr\)\]"/);
  assert.match(lessonInputBlock[0], /className=\{`\$\{workspaceFieldClass\} w-full`\}/);
  assert.doesNotMatch(lessonInputBlock[0], /sm:w-40/);
  assert.doesNotMatch(subjectComboboxBlock[0], /sm:w-32/);
});

test('workspace navigation wires smart wrong questions into the owner admin shell only', () => {
  const sidebarBlock = appSource.match(/const menuItems = \[[\s\S]*?\n  \];/);

  assert.ok(sidebarBlock);
  assert.match(appSource, /type Page = 'dashboard' \| 'review-generation' \| 'consultation' \| 'calendar' \| 'smartWrongQuestions' \| 'masterDataMappings' \| 'classes' \| 'accounts' \| 'settings';/);
  assert.match(sidebarBlock[0], /currentUser\.role === 'owner' \|\| currentUser\.role === 'admin'[\s\S]*\{ id: 'smartWrongQuestions', icon: Cpu, label: '智能错题' \}/);
  assert.match(appSource, /smartWrongQuestions: '智能错题'/);
  assert.match(appSource, /activePage === 'smartWrongQuestions'[\s\S]*<SmartWrongQuestionsPage currentUser=\{currentUser\} \/>/);
});

test('workspace navigation wires master data mappings into the owner admin shell only', () => {
  const sidebarBlock = appSource.match(/const menuItems = \[[\s\S]*?\n  \];/);

  assert.ok(sidebarBlock);
  assert.match(appSource, /type Page = 'dashboard' \| 'review-generation' \| 'consultation' \| 'calendar' \| 'smartWrongQuestions' \| 'masterDataMappings' \| 'classes' \| 'accounts' \| 'settings';/);
  assert.match(sidebarBlock[0], /currentUser\.role === 'owner' \|\| currentUser\.role === 'admin'[\s\S]*\{ id: 'masterDataMappings', icon: Database, label: '主数据映射' \}/);
  assert.match(appSource, /masterDataMappings: '主数据映射'/);
  assert.match(appSource, /activePage === 'masterDataMappings'[\s\S]*<MasterDataMappingsPage currentUser=\{currentUser\} \/>/);
});

test('workspace navigation source reserves classes management for owner and admin shells', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \(\{ currentUser \}: \{ currentUser: CurrentUser \}\) => \{[\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(appSource, /type Page = [^;]*'classes'[^;]*;/);
  assert.match(appSource, /currentUser\.role === 'owner' \|\| currentUser\.role === 'admin'/);
  assert.match(appSource, /id: 'classes'[\s\S]*label: '班级管理'/);
  assert.match(appSource, /classes: '班级管理'/);
  assert.match(appSource, /activePage === 'classes'[\s\S]*<ClassManagementPage currentUser=\{currentUser\}/);
  assert.match(appSource, /const ClassManagementPage = \(\{ currentUser \}: \{ currentUser: CurrentUser \}\) => \{[\s\S]*?apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(appSource, /const ClassManagementPage = \(\{ currentUser \}: \{ currentUser: CurrentUser \}\) => \{[\s\S]*?apiFetch<UserItem\[]>\('\/api\/admin\/users'\)/);
  assert.match(classManagementBlock[0], /在这里统一管理 \{currentUser\.organization_name\} 的班级信息与负责老师安排。/);
  assert.match(classManagementBlock[0], /负责老师/);
  assert.doesNotMatch(classManagementBlock[0], /班级老师分配/);
  assert.doesNotMatch(classManagementBlock[0], /成员班级分配/);
  assert.doesNotMatch(appSource, /const ClassManagementPage = [\s\S]*升为管理员/);
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

test('class management source adds a specific grade filter and renders filtered classes only', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const \[selectedGradeFilter, setSelectedGradeFilter\] = useState<string>\('全部'\)/);
  assert.match(appSource, sharedGradeOptionsPattern);
  assert.match(appSource, /const gradeFilterOptions\s*=\s*\['全部'\s*,\s*\.\.\.gradeOptions\s*\];/);
  assert.match(classManagementBlock[0], /const filteredClasses = classes\.filter\(\(item\) => \{/);
  assert.match(classManagementBlock[0], /if \(selectedGradeFilter === '全部'\) \{\s*return true;\s*\}/);
  assert.match(classManagementBlock[0], /\{filteredClasses\.length === 0 \?/);
  assert.match(classManagementBlock[0], /\{filteredClasses\.map\(\(item\) => \{/);
});

test('class management source reuses fixed grade options for form selection', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(appSource, sharedGradeOptionsPattern);
  assert.match(appSource, /const gradeFilterOptions\s*=\s*\[\s*'全部'\s*,\s*\.\.\.gradeOptions\s*\];/);
  assert.match(classManagementBlock[0], /<select[\s\S]*?value=\{newClassForm\.grade\}[\s\S]*?onChange=\{\(e\) => handleFieldChange\('new', 'grade', e\.target\.value\)\}/);
  assert.match(classManagementBlock[0], /<select[\s\S]*?value=\{formState\.grade\}[\s\S]*?onChange=\{\(e\) => handleFieldChange\(item\.id, 'grade', e\.target\.value\)\}/);
  assert.doesNotMatch(classManagementBlock[0], /<input[\s\S]*?value=\{newClassForm\.grade\}[\s\S]*?placeholder="如：六年级"/);
  assert.doesNotMatch(classManagementBlock[0], /<input[\s\S]*?value=\{formState\.grade\}[\s\S]*?placeholder="如：六年级"/);
});

test('class management source validates saves against the shared fixed grade options', () => {
  assert.match(appSource, sharedGradeOptionsPattern);
  assert.match(appSource, /gradeOptions\.includes\(\s*[^)]*grade[^)]*\)/);
  assert.match(appSource, /请选择年级/);
});

test('class management source uses class-centric teacher binding instead of user checkbox matrices', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /apiFetch<\{ teacher_bindings: Record<number, number \| null> \}>\('\/api\/classes\/teacher-bindings'\)/);
  assert.match(classManagementBlock[0], /const \[teacherBindingByClassId, setTeacherBindingByClassId\] = useState<Record<number, number \| null>>\(\{\}\);/);
  assert.match(classManagementBlock[0], /const \[teacherBindingSavingByClassId, setTeacherBindingSavingByClassId\] = useState<Record<number, boolean>>\(\{\}\);/);
  assert.match(classManagementBlock[0], /const handleSelectTeacherForClass = async \(classId: number, teacherUserId: number\) => \{/);
  assert.match(classManagementBlock[0], /apiFetch\(`\/api\/classes\/\$\{classId\}\/teacher`, \{/);
  assert.doesNotMatch(classManagementBlock[0], /apiFetch<\{ class_ids: number\[\] \}>\(`\/api\/admin\/users\/\$\{userId\}\/classes`\)/);
  assert.doesNotMatch(classManagementBlock[0], /type="checkbox"/);
  assert.match(classManagementBlock[0], /type="radio"/);
});

test('class management source keeps interaction locks while switching to single-teacher binding saves', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const hasTeacherBindingSavingRows = Object\.values\(teacherBindingSavingByClassId\)\.some\(Boolean\);/);
  assert.match(classManagementBlock[0], /const classCardInteractionLocked = classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(classManagementBlock[0], /const pageRefreshLocked = classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(classManagementBlock[0], /const assignmentRefreshLocked = classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(classManagementBlock[0], /if \(classInteractionLocked \|\| teacherBindingSavingByClassId\[classId\]\) \{\s*return;\s*\}/);
  assert.match(classManagementBlock[0], /loadPageRequestVersionRef\.current \+= 1;/);
  assert.match(classManagementBlock[0], /if \(classCardInteractionLocked\) \{\s*return;\s*\}[\s\S]*setExpandedClassId\(/);
  assert.match(classManagementBlock[0], /const refreshResult = await loadPage\(classId, \{ preserveStateOnError: true \}\);/);
  assert.match(classManagementBlock[0], /disabled=\{teacherBindingSaving \|\| classInteractionLocked\}/);
  assert.match(classManagementBlock[0], /disabled=\{assignmentRefreshLocked\}/);
  assert.match(classManagementBlock[0], /disabled=\{classCardInteractionLocked\}[\s\S]*保存班级/);
  assert.match(classManagementBlock[0], /disabled=\{classCardInteractionLocked\}[\s\S]*删除当前班级/);
});

test('class management source keeps refresh reconciliation non-destructive after successful mutations', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(appSource, /type LoadPageResult =/);
  assert.match(classManagementBlock[0], /const preserveStateOnError = options\?\.preserveStateOnError \?\? false;/);
  assert.match(classManagementBlock[0], /return \{ status: 'stale' \};/);
  assert.match(classManagementBlock[0], /return \{ status: 'success' \};/);
  assert.match(classManagementBlock[0], /return \{ status: 'refresh-error', error \};/);
  assert.match(classManagementBlock[0], /if \(!preserveStateOnError\) \{[\s\S]*setClasses\(\[\]\);[\s\S]*setUsers\(\[\]\);[\s\S]*setTeacherBindingByClassId\(\{\}\);/);
  assert.match(classManagementBlock[0], /const refreshResult = await loadPage\(classId, \{ preserveStateOnError: true \}\);/);
  assert.match(classManagementBlock[0], /const refreshResult = await loadPage\(created\.id, \{ preserveStateOnError: true \}\);/);
  assert.match(classManagementBlock[0], /if \(refreshResult\.status === 'refresh-error'\) \{[\s\S]*老师绑定已保存，但列表刷新失败/);
  assert.match(classManagementBlock[0], /if \(refreshResult\.status === 'refresh-error'\) \{[\s\S]*班级和负责老师已保存，但列表刷新失败/);
});

test('class management source adds compact card single-expand state via expandedClassId', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const \[expandedClassId, setExpandedClassId\] = useState<number \| 'new' \| null>/);
  assert.match(classManagementBlock[0], /const isExpanded = expandedClassId === item\.id/);
  assert.match(classManagementBlock[0], /setExpandedClassId\(\(current\) => current === classId \? null : classId\)/);
  assert.match(classManagementBlock[0], /className=\{`\$\{workspaceSoftCardClass\} overflow-hidden p-5`\}/);
  assert.match(classManagementBlock[0], /onClick=\{\(\) => handleToggleExpandedClass\('new'\)\}/);
  assert.match(classManagementBlock[0], /onClick=\{\(\) => handleToggleExpandedClass\(item\.id\)\}/);
  assert.doesNotMatch(classManagementBlock[0], /展开管理/);
  assert.doesNotMatch(classManagementBlock[0], /收起管理/);
  assert.doesNotMatch(classManagementBlock[0], /当前展开/);
  assert.doesNotMatch(classManagementBlock[0], /每次只展开一个班级卡片，在卡片内部完成基础信息维护和班级老师分配。/);
});

test('class management source guards loadPage responses with a request version ref', () => {
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

test('consultation workspace source shows source channel alongside normalized grade-focused metadata', () => {
  assert.match(appSource, /来源渠道/);
  assert.match(appSource, /record\.source_channel \|\| '未标注来源渠道'/);
  assert.match(appSource, /record\.consultation_subject \|\| '未填写咨询科目'/);
});

test('consultation modal source exposes quick parsing and structured confirmation controls', () => {
  assert.match(appSource, /快速录入/);
  assert.match(appSource, /智能解析/);
  assert.match(appSource, /来源渠道备注/);
  assert.match(appSource, /apiFetch<ConsultationTeacherOption\[]>\('\/api\/consultation-teachers'\)/);
});

test('consultation workspace source allows admins to edit and delete records and uses the new follow-up status set', () => {
  assert.match(appSource, /const consultationStatusOptions = \['待邀约', '跟进中', '已报班', '已劝退'\];/);
  assert.match(appSource, /follow_up_status: '待邀约',/);
  assert.match(appSource, /currentUser\.role === 'owner' \|\| currentUser\.role === 'admin'/);
  assert.match(appSource, /\{readOnly && \(currentUser\.role === 'owner' \|\| currentUser\.role === 'admin'\) && \(/);
  assert.match(appSource, /const canManage = currentUser\.role === 'owner' \|\| currentUser\.role === 'admin';/);
  assert.match(appSource, /\{canManage && \(/);
  assert.match(appSource, /onDelete=\{canManage \? handleDelete : undefined\}/);
});

test('approval page source keeps member role controls separate from class assignment', () => {
  const approvalBlock = appSource.match(/const ApprovalPage = \([\s\S]*?\n\};\n\nconst SettingsPage/);

  assert.ok(approvalBlock);
  assert.match(approvalBlock[0], /成员权限/);
  assert.match(approvalBlock[0], /apiFetch<UserItem\[]>\('\/api\/admin\/users'\)/);
  assert.match(approvalBlock[0], /`\/api\/admin\/users\/\$\{userId\}\/role`/);
  assert.doesNotMatch(approvalBlock[0], /成员班级分配/);
});
