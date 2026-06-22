import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const studentCenterSource = readFileSync(new URL('./features/student-center/StudentCenterPage.tsx', import.meta.url), 'utf8');
const campusOverviewSource = readFileSync(new URL('./features/student-center/CampusOverview.tsx', import.meta.url), 'utf8');
const classManagementTabSource = readFileSync(new URL('./features/student-center/ClassManagementTab.tsx', import.meta.url), 'utf8');
const studentManagementTabSource = readFileSync(new URL('./features/student-center/StudentManagementTab.tsx', import.meta.url), 'utf8');
const classEditorModalSource = readFileSync(new URL('./features/student-center/ClassEditorModal.tsx', import.meta.url), 'utf8');
const classEditorModalStateSource = readFileSync(new URL('./features/student-center/classEditorModalState.ts', import.meta.url), 'utf8');
const classSaveRulesSource = readFileSync(new URL('./features/student-center/classSaveRules.ts', import.meta.url), 'utf8');
const classInviteRulesSource = readFileSync(new URL('./features/student-center/classInviteRules.ts', import.meta.url), 'utf8');
const classFilterRulesSource = readFileSync(new URL('./features/student-center/classFilterRules.ts', import.meta.url), 'utf8');
const studentFilterRulesSource = readFileSync(new URL('./features/student-center/studentFilterRules.ts', import.meta.url), 'utf8');
const overviewFilterRulesSource = readFileSync(new URL('./features/student-center/overviewFilterRules.ts', import.meta.url), 'utf8');
const filterInteractionRulesSource = readFileSync(new URL('./features/student-center/filterInteractionRules.ts', import.meta.url), 'utf8');
const permissionsSource = readFileSync(new URL('./features/student-center/permissions.ts', import.meta.url), 'utf8');
const floatingFilterSource = readFileSync(new URL('./components/FloatingFilterBar.tsx', import.meta.url), 'utf8');
const studentCenterClassSource = `${studentCenterSource}\n${classManagementTabSource}\n${classEditorModalSource}\n${classEditorModalStateSource}\n${classSaveRulesSource}\n${classFilterRulesSource}`;
const studentCenterDisplaySource = `${studentCenterSource}\n${classManagementTabSource}\n${studentManagementTabSource}\n${classEditorModalSource}\n${studentFilterRulesSource}`;

test('class management fetches and resets class invite codes', () => {
  assert.match(studentCenterSource, /executeClassInviteLoadRequest\(classId, apiFetch\)/);
  assert.match(studentCenterSource, /executeClassInviteResetRequest\(classId, apiFetch\)/);
  assert.match(classInviteRulesSource, /apiFetch<ClassInviteInfo>\(request\.endpoint\)/);
  assert.match(classInviteRulesSource, /apiFetch<ClassInviteInfo>\(request\.endpoint, request\.init\)/);
  assert.match(classEditorModalSource, /邀请码：/);
  assert.match(classEditorModalSource, /getClassInviteCopyButtonLabel/);
  assert.match(classEditorModalSource, /actions\.onResetClassInvite/);
  assert.match(classEditorModalSource, /重置/);
});

test('class management uses scoped floating filters and compact clickable cards', () => {
  const classPageBlock = [studentCenterClassSource];
  assert.ok(classPageBlock);
  assert.match(studentCenterSource, /import \{ getStudentCenterPermissions \} from '\.\/permissions';/);
  assert.match(classPageBlock[0], /const studentCenterPermissions = getStudentCenterPermissions\(currentUser\);/);
  assert.match(classPageBlock[0], /const classFilterItems = buildClassFilterItems\(classFilters, users\);/);
  assert.match(classFilterRulesSource, /key: 'teacher',[\s\S]*defaultLabel: '教师'/);
  assert.doesNotMatch(classPageBlock[0], /\]\.filter\(\(item\) => canUseOrganizationClassFilters \|\| item\.key !== 'teacher'\)/);
  assert.match(classPageBlock[0], /onActivateClassFilter=\{setActiveClassFilterLayer\}/);
  assert.match(floatingFilterSource, /aria-label=\{`取消\$\{item\.defaultLabel\}筛选`\}/);
  assert.match(classPageBlock[0], /!studentCenterPermissions\.isTeacherScoped/);
  assert.match(classPageBlock[0], /handleClassCardClick/);
  assert.match(classManagementTabSource, /ChevronRight,/);
  assert.match(classPageBlock[0], /grid-cols-\[minmax\(14rem,1\.3fr\)_minmax\(18rem,1fr\)_auto\]/);
  assert.match(classPageBlock[0], /Command\+S \/ Ctrl\+S/);
});

test('class management subject filters stay explicit and popover opens only after intent', () => {
  const classPageBlock = [studentCenterClassSource];
  assert.ok(classPageBlock);
  assert.match(classPageBlock[0], /useState<'subject' \| 'teacher' \| 'stage' \| 'grade' \| null>\(null\)/);
  assert.match(classPageBlock[0], /classFilterCloseTimerRef/);
  assert.match(classPageBlock[0], /handleClassFilterAreaLeave/);
  assert.match(classPageBlock[0], /const classFilterOptions = resolveClassFilterOptions\(\{/);
  assert.match(classPageBlock[0], /const classSubjectFilterOptions = classFilterOptions\.subjectOptions;/);
  assert.match(classPageBlock[0], /const getClassEffectiveSubject = \(item: ClassItem\) => resolveClassEffectiveSubject\(item, classes, teacherBindingByClassId, academicSubjectOptions\);/);
  assert.match(classFilterRulesSource, /subjectOptions: args\.subjectOptions/);
  assert.match(classFilterRulesSource, /getClassEffectiveSubject\(item, subjectLookupClasses \|\| classes, teacherBindingByClassId, subjectOptions\) !== filters\.subjectFilter/);
  assert.match(classPageBlock[0], /activeKey=\{activeClassFilterLayer\}/);
  assert.match(classPageBlock[0], /需填写科目/);
  assert.doesNotMatch(classPageBlock[0], /\{ id: 'all', label: '全部教师', selected: selectedClassTeacherFilter === 'all' \}/);
  assert.match(classEditorModalSource, /academicSubjectOptions\.map\(\(option\) =>/);
});

test('class management editor uses structured naming and duplicate protection', () => {
  const classPageBlock = [studentCenterClassSource];
  assert.ok(classPageBlock);
  assert.match(studentCenterSource, /academicGradeOptions/);
  assert.match(studentCenterSource, /const studentCenterGradeOptions = \[\.\.\.academicGradeOptions\]/);
  assert.match(classSaveRulesSource, /buildClassDisplayName\(\{ \.\.\.form, cohort_year: inferredCohortYear, selected_student_names: selectedStudentNames \}\)/);
  assert.match(classPageBlock[0], /findDuplicateClass\(classes, classId, payload\)/);
  assert.match(classPageBlock[0], /已存在相同学科、学段、年级、班号和入学年份的班级/);
  assert.match(classPageBlock[0], /入学年份/);
  assert.match(classEditorModalSource, /名称预览：\{editing\.displayNamePreview\}/);
  assert.match(classPageBlock[0], /保存更改/);
  assert.doesNotMatch(classPageBlock[0], /span className="text-slate-500 dark:text-slate-400">显示入学级<\/span>/);
});

test('class management editor confirms before closing dirty drafts', () => {
  const classPageBlock = [studentCenterClassSource];
  assert.ok(classPageBlock);
  assert.match(classPageBlock[0], /isClassFormDraftDirty/);
  assert.match(classPageBlock[0], /resetClassFormDraft/);
  assert.match(classPageBlock[0], /attemptCloseClassEditor/);
  assert.match(classPageBlock[0], /有未保存的修改，确定放弃并关闭吗？/);
  assert.match(classEditorModalSource, /onClick=\{\(e\) => e\.target === e\.currentTarget && !classCardInteractionLocked && actions\.onClose\(\)\}/);
});

test('class management summary uses campus overview filters and compact help without title teacher filter', () => {
  const classPageBlock = [`${studentCenterSource}\n${campusOverviewSource}\n${overviewFilterRulesSource}`];
  assert.ok(classPageBlock);
  assert.doesNotMatch(classPageBlock[0], /isClassTitleTeacherFilterOpen/);
  assert.doesNotMatch(classPageBlock[0], /classTitleTeacherSubjectFilter/);
  assert.doesNotMatch(classPageBlock[0], /classTitleTeacherFilterLabel/);
  assert.doesNotMatch(classPageBlock[0], /classTitleTeacherOpenedByHoverRef/);
  assert.doesNotMatch(classPageBlock[0], /handleToggleClassTitleTeacherFilter/);
  assert.doesNotMatch(classPageBlock[0], /titleTeacherFilterOptions/);
  assert.doesNotMatch(classPageBlock[0], /titleTeacherSubjectOptions/);
  assert.doesNotMatch(classPageBlock[0], /负责教师：/);
  assert.match(campusOverviewSource, /<h3 className=\{workspaceSectionTitleClass\}>\{overviewTitle\}<\/h3>/);
  assert.match(studentCenterSource, /overviewTitle=\{studentCenterPermissions\.overviewTitle\}/);
  assert.match(permissionsSource, /overviewTitle: canUseOrganizationScope \? '校区总览' : '教师总览'/);
  assert.match(classPageBlock[0], /activeOverviewFilterLayer/);
  assert.match(classPageBlock[0], /clickedOverviewFilterLayer/);
  assert.match(classPageBlock[0], /overviewFilterItems/);
  assert.match(classPageBlock[0], /selectedSummary=\{activeOverviewFilterSummary\}/);
  assert.match(classPageBlock[0], /const overviewFilterOptions = resolveOverviewFilterOptions\(\{/);
  assert.match(overviewFilterRulesSource, /subjectOptions: args\.subjectOptions/);
  assert.match(classPageBlock[0], /handleOverviewLayerLeave/);
  assert.match(classPageBlock[0], /resolveOverviewFilterItemClick\(\{/);
  assert.match(filterInteractionRulesSource, /activeLayer === targetLayer/);
  assert.match(classPageBlock[0], /activeKey=\{activeOverviewFilterLayer\}/);
  assert.doesNotMatch(classPageBlock[0], /第一层：筛选类型/);
  assert.doesNotMatch(classPageBlock[0], /第二层：具体选项/);
  assert.doesNotMatch(classPageBlock[0], /当前：\{activeOverviewFilterSummary\}。未筛选时显示全部统计。/);
  assert.match(classPageBlock[0], /onSelect=\{handleSelectOverviewFilterOption\}/);
  assert.match(floatingFilterSource, /aria-label="清空校区总览筛选"/);
  assert.match(classPageBlock[0], /const overviewFilteredClasses = resolveOverviewFilteredClasses\(\{/);
  assert.match(overviewFilterRulesSource, /export function resolveOverviewSummaryItems\(/);
  assert.match(classPageBlock[0], /label: '教师人数'[\s\S]*label: '学员人数'[\s\S]*label: '班级数量'[\s\S]*label: '小课数量'/);
  assert.match(classPageBlock[0], /label: '主讲教师', value: currentUser\.display_name \|\| currentUser\.username/);
  assert.match(classPageBlock[0], /const classSummaryItems = resolveOverviewSummaryItems\(\{/);
  assert.match(classPageBlock[0], /grid grid-cols-2 divide-x divide-y divide-slate-200 xl:grid-cols-4 xl:divide-y-0/);
  assert.match(classPageBlock[0], /activeClassHelpKey/);
  assert.match(campusOverviewSource, /\{overviewTitle\}说明/);
  assert.match(classPageBlock[0], /inline-flex h-8 w-8 items-center justify-center text-slate-400/);
  assert.match(classPageBlock[0], /const filteredClasses = resolveFilteredClasses\(\{/);
  assert.match(classFilterRulesSource, /isClassInfoIncomplete/);
  assert.match(classFilterRulesSource, /Number\(isClassInfoIncomplete\(right, args\.teacherBindingByClassId, args\.subjectOptions\)\) - Number\(isClassInfoIncomplete\(left, args\.teacherBindingByClassId, args\.subjectOptions\)\)/);
  assert.doesNotMatch(classPageBlock[0], /在这里统一管理 \{currentUser\.organization_name\} 的班级信息与负责老师安排。/);
});

test('student management mirrors class filter logic and keeps student name as a query field', () => {
  const classPageBlock = [studentCenterDisplaySource];
  assert.ok(classPageBlock);
  assert.match(studentCenterSource, /const classFilterItems = buildClassFilterItems\(classFilters, users\);/);
  assert.match(classFilterRulesSource, /defaultLabel: '科目'[\s\S]*defaultLabel: '教师'[\s\S]*defaultLabel: '学段'[\s\S]*defaultLabel: '年级'/);
  assert.match(studentCenterSource, /const studentFilterItems = buildStudentFilterItems\(studentFilters, users, scopedClassItems\);/);
  assert.match(studentFilterRulesSource, /defaultLabel: '科目'[\s\S]*defaultLabel: '教师'[\s\S]*defaultLabel: '学段'[\s\S]*defaultLabel: '年级'[\s\S]*defaultLabel: '班级'/);
  assert.doesNotMatch(classPageBlock[0], /defaultLabel: '学员姓名'/);
  assert.match(classPageBlock[0], /onStudentFilterAreaLeave=\{handleStudentFilterAreaLeave\}/);
  assert.match(classPageBlock[0], /onActivateStudentFilter=\{setActiveStudentFilterLayer\}/);
  assert.match(classPageBlock[0], /onClearStudentFilter=\{handleClearStudentFilter\}/);
  assert.match(classPageBlock[0], /onSelectStudentFilterOption=\{handleSelectStudentFilterOption\}/);
  assert.doesNotMatch(classPageBlock[0], /activeStudentFilterLayer === 'student'/);
  assert.match(classPageBlock[0], /placeholder="学员姓名查询"/);
  assert.match(classPageBlock[0], /aria-label="清空学员姓名查询"/);
  assert.match(classPageBlock[0], /studentNameFilter\.trim\(\)/);
  assert.match(studentCenterSource, /const filteredStudentRows = resolveFilteredStudentRows\(\{/);
  assert.match(studentFilterRulesSource, /args\.rows\.filter\(\(item\) => studentMatchesFilters\(\{ \.\.\.args, item \}\)\)\.sort/);
});

test('student center filter UI is reusable instead of handwritten per section', () => {
  const classPageBlock = [studentCenterDisplaySource];
  assert.ok(classPageBlock);
  assert.match(classManagementTabSource, /import \{ FloatingFilterBar/);
  assert.match(studentManagementTabSource, /import \{ FloatingFilterBar/);
  assert.match(campusOverviewSource, /import \{ FloatingOverviewFilter/);
  assert.match(campusOverviewSource, /<FloatingOverviewFilter/);
  assert.match(studentManagementTabSource, /<FloatingFilterBar[\s\S]*scopeLabel=\{studentScopeLabel\}/);
  assert.match(classManagementTabSource, /<FloatingFilterBar[\s\S]*scopeLabel=\{classScopeLabel\}/);
  assert.match(floatingFilterSource, /export function FloatingFilterBar/);
  assert.match(floatingFilterSource, /export function FloatingOverviewFilter/);
  assert.match(floatingFilterSource, /onMouseEnter/);
  assert.match(floatingFilterSource, /onMouseLeave/);
  assert.match(floatingFilterSource, /aria-label=\{`取消\$\{item\.defaultLabel\}筛选`\}/);
});
