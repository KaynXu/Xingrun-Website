import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

test('class management fetches and resets class invite codes', () => {
  assert.match(appSource, /apiFetch<ClassInviteInfo>\(`\/api\/classes\/\$\{classId\}\/invite`\)/);
  assert.match(appSource, /apiFetch<ClassInviteInfo>\(`\/api\/classes\/\$\{classId\}\/invite\/reset`, \{/);
  assert.match(appSource, /家长绑定邀请码/);
  assert.match(appSource, /当前邀请码/);
  assert.match(appSource, /微信小程序里绑定该班级/);
});

test('class management uses scoped floating filters and compact clickable cards', () => {
  const classPageBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};\n\n\/\/ --- Login Modal ---/);
  assert.ok(classPageBlock);
  assert.match(classPageBlock[0], /const canUseOrganizationClassFilters = hasOwnerAccess\(currentUser\.role\);/);
  assert.match(classPageBlock[0], /key: 'teacher' as const,[\s\S]*defaultLabel: '教师'/);
  assert.doesNotMatch(classPageBlock[0], /\]\.filter\(\(item\) => canUseOrganizationClassFilters \|\| item\.key !== 'teacher'\)/);
  assert.match(classPageBlock[0], /onMouseEnter=\{\(\) => setActiveClassFilterLayer\(item\.key\)\}/);
  assert.match(classPageBlock[0], /aria-label=\{`取消\$\{item\.defaultLabel\}筛选`\}/);
  assert.match(classPageBlock[0], /currentUser\.role !== 'member'/);
  assert.match(classPageBlock[0], /handleClassCardClick/);
  assert.match(appSource, /ChevronRight,/);
  assert.match(classPageBlock[0], /grid-cols-\[minmax\(14rem,1\.25fr\)_minmax\(18rem,1fr\)_auto\]/);
  assert.match(classPageBlock[0], /Command\+S \/ Ctrl\+S/);
});

test('class management subject filters stay explicit and popover opens only after intent', () => {
  const classPageBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};\n\n\/\/ --- Login Modal ---/);
  assert.ok(classPageBlock);
  assert.match(classPageBlock[0], /useState<'subject' \| 'teacher' \| 'stage' \| 'grade' \| null>\(null\)/);
  assert.match(classPageBlock[0], /classFilterCloseTimerRef/);
  assert.match(classPageBlock[0], /handleClassFilterAreaLeave/);
  assert.match(classPageBlock[0], /const classSubjectFilterOptions = academicSubjectOptions;/);
  assert.match(classPageBlock[0], /const getClassEffectiveSubject = \(item: ClassItem\) =>/);
  assert.match(classPageBlock[0], /getClassEffectiveSubject\(item\) !== selectedSubjectFilter/);
  assert.match(classPageBlock[0], /activeClassFilterLayer && \(/);
  assert.match(classPageBlock[0], /需填写科目/);
  assert.doesNotMatch(classPageBlock[0], /\{ id: 'all', label: '全部教师', selected: selectedClassTeacherFilter === 'all' \}/);
  assert.match(classPageBlock[0], /academicSubjectOptions\.map\(\(option\) =>/);
});

test('class management editor uses structured naming and duplicate protection', () => {
  const classPageBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};\n\n\/\/ --- Login Modal ---/);
  assert.ok(classPageBlock);
  assert.match(appSource, /const studentCenterGradeOptions = \['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '七年级', '八年级', '九年级', '高一', '高二', '高三'\]/);
  assert.match(classPageBlock[0], /buildClassDisplayName\(currentForm\)/);
  assert.match(classPageBlock[0], /findDuplicateClass\(classId, payload\)/);
  assert.match(classPageBlock[0], /已存在相同学科、学段、年级、班号和入学级的班级/);
  assert.match(classPageBlock[0], /入学年级/);
  assert.match(classPageBlock[0], /2025级·四年级·1班/);
  assert.match(classPageBlock[0], /保存更改/);
  assert.doesNotMatch(classPageBlock[0], /span className="text-slate-500 dark:text-slate-400">显示入学级<\/span>/);
});

test('class management editor confirms before closing dirty drafts', () => {
  const classPageBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};\n\n\/\/ --- Login Modal ---/);
  assert.ok(classPageBlock);
  assert.match(classPageBlock[0], /isClassFormDraftDirty/);
  assert.match(classPageBlock[0], /resetClassFormDraft/);
  assert.match(classPageBlock[0], /attemptCloseClassEditor/);
  assert.match(classPageBlock[0], /有未保存的修改，确定放弃并关闭吗？/);
  assert.match(classPageBlock[0], /onClick=\{\(e\) => e\.target === e\.currentTarget && !classCardInteractionLocked && attemptCloseClassEditor\(\)\}/);
});

test('class management summary uses campus overview filters and compact help without title teacher filter', () => {
  const classPageBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};\n\n\/\/ --- Login Modal ---/);
  assert.ok(classPageBlock);
  assert.doesNotMatch(classPageBlock[0], /isClassTitleTeacherFilterOpen/);
  assert.doesNotMatch(classPageBlock[0], /classTitleTeacherSubjectFilter/);
  assert.doesNotMatch(classPageBlock[0], /classTitleTeacherFilterLabel/);
  assert.doesNotMatch(classPageBlock[0], /classTitleTeacherOpenedByHoverRef/);
  assert.doesNotMatch(classPageBlock[0], /handleToggleClassTitleTeacherFilter/);
  assert.doesNotMatch(classPageBlock[0], /titleTeacherFilterOptions/);
  assert.doesNotMatch(classPageBlock[0], /titleTeacherSubjectOptions/);
  assert.doesNotMatch(classPageBlock[0], /负责教师：/);
  assert.match(classPageBlock[0], />校区总览<\/h3>/);
  assert.match(classPageBlock[0], /activeOverviewFilterLayer/);
  assert.match(classPageBlock[0], /clickedOverviewFilterLayer/);
  assert.match(classPageBlock[0], /overviewFilterItems/);
  assert.match(classPageBlock[0], /全校区：\$\{activeOverviewFilterSummary\}/);
  assert.match(classPageBlock[0], /const overviewSubjectFilterOptions = academicSubjectOptions;/);
  assert.match(classPageBlock[0], /handleOverviewLayerLeave/);
  assert.match(classPageBlock[0], /activeOverviewFilterLayer === item\.key/);
  assert.match(classPageBlock[0], /activeOverviewFilterLayer && \(/);
  assert.doesNotMatch(classPageBlock[0], /第一层：筛选类型/);
  assert.doesNotMatch(classPageBlock[0], /第二层：具体选项/);
  assert.doesNotMatch(classPageBlock[0], /当前：\{activeOverviewFilterSummary\}。未筛选时显示全部统计。/);
  assert.match(classPageBlock[0], /handleSelectOverviewFilterOption\(option\.id\)/);
  assert.match(classPageBlock[0], /aria-label="清空校区总览筛选"/);
  assert.match(classPageBlock[0], /const overviewFilteredClasses = scopedClassItems\.filter\(\(item\) => overviewMatchesSelectedFilters\(item\)\);/);
  assert.match(classPageBlock[0], /const classOwnerSummaryItems = \[/);
  assert.match(classPageBlock[0], /label: '教师人数'[\s\S]*label: '学员人数'[\s\S]*label: '班级数量'[\s\S]*label: '小课数量'/);
  assert.match(classPageBlock[0], /label: '主讲教师', value: currentUser\.display_name \|\| currentUser\.username/);
  assert.match(classPageBlock[0], /canUseOrganizationClassFilters \? classOwnerSummaryItems : classTeacherSummaryItems/);
  assert.match(classPageBlock[0], /grid grid-cols-2 gap-4 xl:grid-cols-4/);
  assert.match(classPageBlock[0], /activeClassHelpKey/);
  assert.match(classPageBlock[0], /校区总览说明/);
  assert.match(classPageBlock[0], /inline-flex h-8 w-8 items-center justify-center text-sky-600/);
  assert.match(classPageBlock[0], /isClassInfoIncomplete/);
  assert.match(classPageBlock[0], /Number\(isClassInfoIncomplete\(right\)\) - Number\(isClassInfoIncomplete\(left\)\)/);
  assert.doesNotMatch(classPageBlock[0], /在这里统一管理 \{currentUser\.organization_name\} 的班级信息与负责老师安排。/);
});

test('student management mirrors class filter logic and keeps student name as a query field', () => {
  const classPageBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};\n\n\/\/ --- Login Modal ---/);
  assert.ok(classPageBlock);
  assert.match(classPageBlock[0], /const classFilterItems = \[[\s\S]*defaultLabel: '科目'[\s\S]*defaultLabel: '教师'[\s\S]*defaultLabel: '学段'[\s\S]*defaultLabel: '年级'/);
  assert.match(classPageBlock[0], /const studentFilterItems = \[/);
  assert.match(classPageBlock[0], /const studentFilterItems = \[[\s\S]*defaultLabel: '科目'[\s\S]*defaultLabel: '教师'[\s\S]*defaultLabel: '学段'[\s\S]*defaultLabel: '年级'[\s\S]*defaultLabel: '班级'/);
  assert.doesNotMatch(classPageBlock[0], /defaultLabel: '学员姓名'/);
  assert.match(classPageBlock[0], /onMouseEnter=\{\(\) => setActiveStudentFilterLayer\(item\.key\)\}/);
  assert.match(classPageBlock[0], /onMouseLeave=\{handleStudentFilterAreaLeave\}/);
  assert.match(classPageBlock[0], /handleClearStudentFilter\(item\.key\)/);
  assert.match(classPageBlock[0], /handleSelectStudentFilterOption\(option\.id\)/);
  assert.doesNotMatch(classPageBlock[0], /activeStudentFilterLayer === 'student'/);
  assert.match(classPageBlock[0], /placeholder="学员姓名查询"/);
  assert.match(classPageBlock[0], /aria-label="清空学员姓名查询"/);
  assert.match(classPageBlock[0], /studentNameFilter\.trim\(\)/);
  assert.match(classPageBlock[0], /const filteredStudentRows = studentRows\.filter\(\(item\) => studentMatchesSelectedFilters\(item\)\)\.sort/);
});
