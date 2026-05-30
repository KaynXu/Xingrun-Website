import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildOverviewFilterItems,
  buildOverviewFilterSummary,
  resolveOverviewFilterOptions,
  resolveOverviewFilteredClasses,
  resolveOverviewSummaryItems,
  type OverviewFilterState,
} from './overviewFilterRules';
import type { ClassItem, CurrentUser, UserItem } from './model';

const subjectOptions = ['数学', '物理', '国际数学'];
const stageOptions = ['小奥', '初中', '高中'];
const gradeOptions = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '七年级', '八年级', '九年级', '高一', '高二', '高三'];
const gradeGroups: Record<string, string[]> = {
  小奥: ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级'],
  初中: ['七年级', '八年级', '九年级'],
  高中: ['高一', '高二', '高三'],
};

const teachers: UserItem[] = [
  { id: 1, name: '曹老师', org: '星润', role: 'member' },
  { id: 2, name: '李老师', org: '星润', role: 'member' },
  { id: 3, name: '王老师', org: '星润', role: 'member' },
];

const classes: ClassItem[] = [
  {
    id: 11,
    name: '四年级 1 班',
    subject: '数学',
    grade: '四年级',
    current_grade: '四年级',
    stage: '小奥',
    teacher_user_id: 1,
    teacher_name: '曹老师',
    student_count: 12,
    lesson_count: 5,
  },
  {
    id: 12,
    name: '七年级 2 班',
    subject: '物理',
    grade: '七年级',
    current_grade: '七年级',
    stage: '初中',
    teacher_user_id: 2,
    teacher_name: '李老师',
    student_count: 18,
    lesson_count: 8,
  },
  {
    id: 13,
    name: '八年级 3 班',
    subject: '',
    grade: '八年级',
    current_grade: '八年级',
    stage: '初中',
    teacher_user_id: 2,
    teacher_name: '李老师',
    student_count: 9,
    lesson_count: 4,
  },
];

const allFilters: OverviewFilterState = {
  subjectFilter: '全部学科',
  teacherFilter: 'all',
  stageFilter: '全部学段',
  gradeFilter: '全部',
};

const currentUser: CurrentUser = {
  id: 1,
  username: 'cao',
  display_name: '曹老师',
  role: 'member',
  status: 'active',
  organization_id: 1,
  organization_name: '星润',
  created_at: '',
};

test('resolveOverviewFilteredClasses applies subject, teacher, stage, and grade filters with teacher subject fallback', () => {
  assert.deepEqual(
    resolveOverviewFilteredClasses({
      classes,
      teacherBindingByClassId: {},
      subjectOptions,
      filters: { ...allFilters, subjectFilter: '物理' },
    }).map((item) => item.id),
    [12, 13],
  );
  assert.deepEqual(
    resolveOverviewFilteredClasses({
      classes,
      teacherBindingByClassId: {},
      subjectOptions,
      filters: { ...allFilters, teacherFilter: 1 },
    }).map((item) => item.id),
    [11],
  );
  assert.deepEqual(
    resolveOverviewFilteredClasses({
      classes,
      teacherBindingByClassId: {},
      subjectOptions,
      filters: { ...allFilters, stageFilter: '初中', gradeFilter: '八年级' },
    }).map((item) => item.id),
    [13],
  );
});

test('resolveOverviewFilterOptions cascades options while ignoring the active layer', () => {
  const options = resolveOverviewFilterOptions({
    classes,
    users: teachers,
    teacherBindingByClassId: {},
    subjectOptions,
    stageOptions,
    gradeOptions,
    gradeGroups,
    filters: { ...allFilters, subjectFilter: '物理', stageFilter: '初中' },
  });

  assert.deepEqual(options.subjectOptions, subjectOptions);
  assert.deepEqual(options.teacherOptions.map((teacher) => teacher.id), [2]);
  assert.deepEqual(options.stageOptions, ['初中']);
  assert.deepEqual(options.gradeOptions, ['七年级', '八年级']);
});

test('overview summary and cards keep owner and teacher views distinct', () => {
  const filteredClasses = resolveOverviewFilteredClasses({
    classes,
    teacherBindingByClassId: {},
    subjectOptions,
    filters: { ...allFilters, subjectFilter: '物理' },
  });

  assert.equal(buildOverviewFilterSummary({ ...allFilters, subjectFilter: '物理', teacherFilter: 2 }, teachers), '教师：李老师 / 科目：物理');
  assert.deepEqual(buildOverviewFilterItems({ ...allFilters, subjectFilter: '物理' }, true).map((item) => item.key), ['subject', 'teacher', 'stage', 'grade']);
  assert.deepEqual(buildOverviewFilterItems(allFilters, false).map((item) => item.key), ['subject', 'stage', 'grade']);
  assert.deepEqual(
    resolveOverviewSummaryItems({
      filteredClasses,
      currentUser,
      canUseOrganizationScope: true,
      teacherBindingByClassId: {},
    }),
    [
      { label: '教师人数', value: 1 },
      { label: '学员人数', value: 27 },
      { label: '班级数量', value: 2 },
      { label: '小课数量', value: 12 },
    ],
  );
  assert.deepEqual(
    resolveOverviewSummaryItems({
      filteredClasses: [classes[0]],
      currentUser,
      canUseOrganizationScope: false,
      teacherBindingByClassId: {},
    })[0],
    { label: '主讲教师', value: '曹老师' },
  );
});
