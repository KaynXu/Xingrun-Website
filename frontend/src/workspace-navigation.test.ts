import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

test('workspace navigation wires consultation and calendar pages into the shell', () => {
  assert.match(appSource, /type Page = 'dashboard' \| 'input' \| 'library' \| 'consultation' \| 'calendar' \| 'classes' \| 'accounts' \| 'settings';/);
  assert.match(appSource, /id: 'consultation'[\s\S]*label: '咨询记录'/);
  assert.match(appSource, /consultation: '咨询记录'/);
  assert.match(appSource, /activePage === 'consultation'[\s\S]*<ConsultationPage currentUser=\{currentUser\}/);
  assert.match(appSource, /id: 'calendar'[\s\S]*label: '课程日历'/);
  assert.match(appSource, /calendar: '课程日历'/);
  assert.match(appSource, /activePage === 'calendar'[\s\S]*<CourseCalendarPage/);

  assert.doesNotMatch(appSource, /题库浏览/);
  assert.doesNotMatch(appSource, /QuestionBank/);
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
  assert.match(classManagementBlock[0], /班级老师分配/);
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
  assert.match(classManagementBlock[0], /const gradeFilterOptions = \['全部', '一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三'\];/);
  assert.match(classManagementBlock[0], /const filteredClasses = classes\.filter\(\(item\) => \{/);
  assert.match(classManagementBlock[0], /if \(selectedGradeFilter === '全部'\) \{\s*return true;\s*\}/);
  assert.match(classManagementBlock[0], /\{filteredClasses\.length === 0 \?/);
  assert.match(classManagementBlock[0], /\{filteredClasses\.map\(\(item\) => \{/);
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
  assert.match(classManagementBlock[0], /\{isExpanded \? '收起管理' : '展开管理'\}/);
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

test('approval page source keeps member role controls separate from class assignment', () => {
  const approvalBlock = appSource.match(/const ApprovalPage = \([\s\S]*?\n\};\n\nconst SettingsPage/);

  assert.ok(approvalBlock);
  assert.match(approvalBlock[0], /成员权限/);
  assert.match(approvalBlock[0], /apiFetch<UserItem\[]>\('\/api\/admin\/users'\)/);
  assert.match(approvalBlock[0], /`\/api\/admin\/users\/\$\{userId\}\/role`/);
  assert.doesNotMatch(approvalBlock[0], /成员班级分配/);
});
