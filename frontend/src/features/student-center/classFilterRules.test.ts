import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildClassFilterItems,
  buildClassFilterSummary,
  getClassInfoIssues,
  resolveActiveClassFilterOptions,
  resolveClassFilterOptions,
  resolveFilteredClasses,
  type ClassFilterState,
} from './classFilterRules';
import type { ClassItem, UserItem } from './model';

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
];

const classes: ClassItem[] = [
  {
    id: 11,
    name: '四年级 1 班',
    subject: '数学',
    grade: '四年级',
    current_grade: '四年级',
    stage: '小奥',
    class_number: '1',
    teacher_user_id: 1,
    teacher_name: '曹老师',
  },
  {
    id: 12,
    name: '七年级 2 班',
    subject: '物理',
    grade: '七年级',
    current_grade: '七年级',
    stage: '初中',
    class_number: '2',
    teacher_user_id: 2,
    teacher_name: '李老师',
  },
  {
    id: 13,
    name: '八年级 3 班',
    subject: '',
    grade: '八年级',
    current_grade: '八年级',
    stage: '初中',
    class_number: '3',
    teacher_user_id: 2,
    teacher_name: '李老师',
  },
  {
    id: 14,
    name: '信息不完整班级',
    subject: '',
    grade: '',
    current_grade: '',
    stage: '',
    class_number: '',
    teacher_user_id: null,
    teacher_name: '',
  },
];

const allFilters: ClassFilterState = {
  subjectFilter: '全部学科',
  teacherFilter: 'all',
  stageFilter: '全部学段',
  gradeFilter: '全部',
};

test('resolveFilteredClasses filters class cards and sorts incomplete cards first', () => {
  assert.deepEqual(
    resolveFilteredClasses({
      classes,
      subjectLookupClasses: classes,
      teacherBindingByClassId: {},
      subjectOptions,
      filters: { ...allFilters, subjectFilter: '物理' },
    }).map((item) => item.id),
    [13, 12],
  );
  assert.deepEqual(
    resolveFilteredClasses({
      classes,
      subjectLookupClasses: classes,
      teacherBindingByClassId: {},
      subjectOptions,
      filters: allFilters,
    }).map((item) => item.id),
    [13, 14, 11, 12],
  );
});

test('resolveClassFilterOptions cascades options while ignoring the active layer', () => {
  const options = resolveClassFilterOptions({
    classes,
    subjectLookupClasses: classes,
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

test('resolveFilteredClasses applies teacher stage and grade filters as behavior', () => {
  assert.deepEqual(
    resolveFilteredClasses({
      classes,
      subjectLookupClasses: classes,
      teacherBindingByClassId: {},
      subjectOptions,
      filters: { ...allFilters, teacherFilter: 2 },
    }).map((item) => item.id),
    [13, 12],
  );
  assert.deepEqual(
    resolveFilteredClasses({
      classes,
      subjectLookupClasses: classes,
      teacherBindingByClassId: {},
      subjectOptions,
      filters: { ...allFilters, stageFilter: '初中', gradeFilter: '七年级' },
    }).map((item) => item.id),
    [12],
  );
});

test('class filter display helpers build summary, tags, options, and info issues', () => {
  const filters: ClassFilterState = {
    subjectFilter: '物理',
    teacherFilter: 2,
    stageFilter: '初中',
    gradeFilter: '七年级',
  };
  const options = resolveClassFilterOptions({
    classes,
    subjectLookupClasses: classes,
    users: teachers,
    teacherBindingByClassId: {},
    subjectOptions,
    stageOptions,
    gradeOptions,
    gradeGroups,
    filters,
  });

  assert.equal(buildClassFilterSummary(filters, teachers), '李老师 / 物理 / 初中 / 七年级');
  assert.deepEqual(buildClassFilterItems(filters, teachers).map((item) => [item.key, item.label, item.selected]), [
    ['subject', '科目：物理', true],
    ['teacher', '李老师', true],
    ['stage', '初中', true],
    ['grade', '七年级', true],
  ]);
  assert.deepEqual(resolveActiveClassFilterOptions('teacher', filters, options).map((item) => item.id), [2]);
  assert.deepEqual(getClassInfoIssues(classes[3], {}, subjectOptions), ['缺科目', '缺学段', '缺年级', '缺班号', '缺负责教师']);
});

test('small classes do not require class number in info issue checks', () => {
  assert.deepEqual(
    getClassInfoIssues({
      id: 21,
      name: '何晨煜·1v1·四年级',
      subject: '数学',
      grade: '四年级',
      current_grade: '四年级',
      stage: '小奥',
      class_type: '1v1',
      class_number: '',
      teacher_user_id: 1,
      teacher_name: '曹老师',
    }, {}, subjectOptions),
    [],
  );
});

test('resolveFilteredClasses sorts small classes before group classes then low grade to high grade', () => {
  const ordered = resolveFilteredClasses({
    classes: [
      {
        id: 31,
        name: '班课八年级',
        class_type: 'group',
        subject: '数学',
        grade: '八年级',
        current_grade: '八年级',
        stage: '初中',
        class_number: '2',
        teacher_user_id: 1,
        teacher_name: '曹老师',
      },
      {
        id: 32,
        name: '小课五年级',
        class_type: '1v1',
        subject: '数学',
        grade: '五年级',
        current_grade: '五年级',
        stage: '小奥',
        class_number: '',
        teacher_user_id: 1,
        teacher_name: '曹老师',
      },
      {
        id: 33,
        name: '小课九年级',
        class_type: '1v1',
        subject: '数学',
        grade: '九年级',
        current_grade: '九年级',
        stage: '初中',
        class_number: '',
        teacher_user_id: 1,
        teacher_name: '曹老师',
      },
      {
        id: 34,
        name: '班课七年级',
        class_type: 'group',
        subject: '数学',
        grade: '七年级',
        current_grade: '七年级',
        stage: '初中',
        class_number: '1',
        teacher_user_id: 1,
        teacher_name: '曹老师',
      },
    ],
    subjectLookupClasses: [],
    teacherBindingByClassId: {},
    subjectOptions,
    filters: allFilters,
  }).map((item) => item.id);

  assert.deepEqual(ordered, [32, 33, 34, 31]);
});
