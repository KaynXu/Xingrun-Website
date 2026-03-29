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
  assert.match(appSource, /type Page = [^;]*'classes'[^;]*;/);
  assert.match(appSource, /currentUser\.role === 'owner' \|\| currentUser\.role === 'admin'/);
  assert.match(appSource, /id: 'classes'[\s\S]*label: '班级管理'/);
  assert.match(appSource, /classes: '班级管理'/);
  assert.match(appSource, /activePage === 'classes'[\s\S]*<ClassManagementPage currentUser=\{currentUser\}/);
  assert.match(appSource, /const ClassManagementPage = \(\{ currentUser \}: \{ currentUser: CurrentUser \}\) => \{[\s\S]*?apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(appSource, /const ClassManagementPage = \(\{ currentUser \}: \{ currentUser: CurrentUser \}\) => \{[\s\S]*?apiFetch<UserItem\[]>\('\/api\/admin\/users'\)/);
  assert.match(appSource, /apiFetch<\{ class_ids: number\[\] \}>\(`\/api\/admin\/users\/\$\{userId\}\/classes`\)/);
  assert.match(appSource, /班级列表/);
  assert.match(appSource, /成员班级分配/);
  assert.doesNotMatch(appSource, /const ClassManagementPage = [\s\S]*升为管理员/);
});

test('class management source guards selection and refresh during class save delete locks', () => {
  assert.match(appSource, /const classInteractionLocked = saving \|\| deleting;/);
  assert.match(appSource, /const handleSelectClass = \(classId: number \| 'new'\) => \{\s*if \(classInteractionLocked\) \{\s*return;\s*\}\s*setSelectedClassId\(classId\);\s*setFormError\(''\);\s*\};/);
  assert.match(appSource, /onClick=\{\(\) => loadPage\(selectedClassId\)\.catch\(\(\) => undefined\)\}\s+disabled=\{classInteractionLocked\}\s+className=\{workspaceSecondaryButtonClass\}/);
  assert.match(appSource, /onClick=\{\(\) => handleSelectClass\('new'\)\}\s+disabled=\{classInteractionLocked\}\s+className=\{workspacePrimaryButtonClass\}/);
  assert.match(appSource, /onClick=\{\(\) => handleSelectClass\(item\.id\)\}[\s\S]*disabled=\{classInteractionLocked\}/);
  assert.match(appSource, /onClick=\{\(\) => handleSelectClass\('new'\)\}\s+disabled=\{classInteractionLocked\}\s+className=\{workspaceSecondaryButtonClass\}/);
});

test('class management source guards assignment refresh and checkboxes during conflicting async work', () => {
  assert.match(appSource, /const hasAssignmentSavingRows = Object\.values\(assignmentSavingByUserId\)\.some\(Boolean\);/);
  assert.match(appSource, /const assignmentRefreshLocked = classInteractionLocked \|\| hasAssignmentSavingRows;/);
  assert.match(appSource, /const handleToggleAssignment = async \(userId: number, classId: number, checked: boolean\) => \{\s*if \(classInteractionLocked \|\| assignmentSavingByUserId\[userId\]\) \{\s*return;\s*\}/);
  assert.match(appSource, /onClick=\{\(\) => loadPage\(selectedClassId\)\.catch\(\(\) => undefined\)\}\s+disabled=\{assignmentRefreshLocked\}\s+className=\{workspaceSecondaryButtonClass\}/);
  assert.match(appSource, /disabled=\{rowSaving \|\| classInteractionLocked\}/);
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
