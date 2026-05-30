import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildStudentFilterItems,
  buildStudentFilterSummary,
  buildStudentRows,
  resolveActiveStudentFilterOptions,
  resolveFilteredStudentRows,
  resolveStudentFilterOptions,
  type StudentFilterState,
} from './studentFilterRules';
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
];

const studentsByClassId = {
  11: [
    { id: 101, name: '陈一' },
    { id: 102, name: '安安' },
  ],
  12: [
    { id: 201, name: '李物理' },
  ],
  13: [
    { id: 301, name: '王物理' },
  ],
};

const allFilters: StudentFilterState = {
  subjectFilter: '全部学科',
  teacherFilter: 'all',
  stageFilter: '全部学段',
  gradeFilter: '全部',
  classFilter: 'all',
  nameFilter: '',
};

test('buildStudentRows and resolveFilteredStudentRows keep existing filtering and sorting behavior', () => {
  const rows = buildStudentRows({
    classes,
    studentsByClassId,
    teacherBindingByClassId: { 13: 2 },
  });

  assert.deepEqual(rows.map((item) => [item.id, item.classItem.id, item.teacherUserId]), [
    [101, 11, 1],
    [102, 11, 1],
    [201, 12, 2],
    [301, 13, 2],
  ]);

  assert.deepEqual(
    resolveFilteredStudentRows({
      rows,
      classes,
      teacherBindingByClassId: { 13: 2 },
      subjectOptions,
      filters: { ...allFilters, subjectFilter: '物理' },
    }).map((item) => item.id),
    [201, 301],
  );

  assert.deepEqual(
    resolveFilteredStudentRows({
      rows,
      classes,
      teacherBindingByClassId: { 13: 2 },
      subjectOptions,
      filters: allFilters,
    }).map((item) => item.id),
    [102, 101, 201, 301],
  );
});

test('resolveStudentFilterOptions cascades options while ignoring the active layer', () => {
  const rows = buildStudentRows({
    classes,
    studentsByClassId,
    teacherBindingByClassId: { 13: 2 },
  });

  const options = resolveStudentFilterOptions({
    rows,
    classes,
    scopedClasses: classes,
    users: teachers,
    teacherBindingByClassId: { 13: 2 },
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
  assert.deepEqual(options.classOptions.map((classItem) => classItem.id), [12, 13]);
});

test('student filter display helpers build summary, tags, and active options', () => {
  const rows = buildStudentRows({
    classes,
    studentsByClassId,
    teacherBindingByClassId: { 13: 2 },
  });
  const filters: StudentFilterState = {
    subjectFilter: '物理',
    teacherFilter: 2,
    stageFilter: '初中',
    gradeFilter: '七年级',
    classFilter: 12,
    nameFilter: '李',
  };
  const options = resolveStudentFilterOptions({
    rows,
    classes,
    scopedClasses: classes,
    users: teachers,
    teacherBindingByClassId: { 13: 2 },
    subjectOptions,
    stageOptions,
    gradeOptions,
    gradeGroups,
    filters,
  });

  assert.equal(buildStudentFilterSummary(filters, teachers, classes), '李老师 / 物理 / 初中 / 七年级 / 七年级·2班 / 李');
  assert.deepEqual(buildStudentFilterItems(filters, teachers, classes).map((item) => [item.key, item.label, item.selected]), [
    ['subject', '科目：物理', true],
    ['teacher', '李老师', true],
    ['stage', '初中', true],
    ['grade', '七年级', true],
    ['class', '七年级·2班', true],
  ]);
  assert.deepEqual(resolveActiveStudentFilterOptions('class', filters, options).map((item) => item.id), [12]);
});
