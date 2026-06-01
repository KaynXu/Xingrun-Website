import assert from 'node:assert/strict';
import test from 'node:test';
import type { ClassFormValues, ClassInviteInfo, ClassItem, UserItem } from './model';
import { buildClassEditorModalState } from './classEditorModalState';

const gradeGroups = {
  小奥: ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级'],
  初中: ['七年级', '八年级', '九年级'],
  高中: ['高一', '高二', '高三'],
};

const gradeOptions = [...gradeGroups.小奥, ...gradeGroups.初中, ...gradeGroups.高中];

const emptyForm: ClassFormValues = {
  name: '',
  subject: '',
  grade: '',
  teacher_name: '',
  stage: '小奥',
  current_grade: '一年级',
  class_number: '1',
  cohort_year: '',
  show_cohort_year: true,
  is_bridge: false,
  bridge_target: '小学衔接初中',
  content_track: '',
};

const newForm: ClassFormValues = {
  ...emptyForm,
  subject: '数学',
  current_grade: '四年级',
  class_number: '2',
  cohort_year: '2025',
};

const users: UserItem[] = [
  { id: 1, name: '曹老师', org: '星润', role: 'member' },
  { id: 2, name: '王老师', org: '星润', role: 'member' },
];

const classes: ClassItem[] = [
  {
    id: 8,
    name: '旧班级',
    subject: '物理',
    grade: '七年级',
    stage: '初中',
    current_grade: '七年级',
    class_number: '3',
    cohort_year: 2025,
    teacher_name: '王老师',
    teacher_user_id: 2,
  },
];

const inviteInfo: ClassInviteInfo = {
  id: 18,
  class_id: 8,
  invite_code: 'ABCD12',
  status: 'active',
  created_at: '2026-05-30 10:00:00',
};

test('buildClassEditorModalState assembles new class modal state from page state', () => {
  const state = buildClassEditorModalState({
    expandedClassId: 'new',
    classes,
    users,
    formByClassId: { new: newForm },
    emptyClassForm: emptyForm,
    teacherSearchByClassId: { new: '曹' },
    newClassTeacherUserId: 1,
    teacherBindingByClassId: {},
    teacherBindingSavingByClassId: {},
    inviteByClassId: {},
    inviteLoadingByClassId: {},
    inviteResettingByClassId: {},
    inviteErrorByClassId: {},
    studentsByClassId: {},
    allStudents: [],
    studentsLoadingByClassId: {},
    studentSavingByClassId: {},
    studentErrorByClassId: {},
    studentDraftNameByClassId: {},
    gradeGroups,
    gradeOptions,
    canEditTeacherBinding: true,
    classCardInteractionLocked: false,
    classInteractionLocked: false,
    assignmentRefreshLocked: false,
    saving: false,
    deleting: false,
    formError: '',
    assignmentError: '',
    academicSubjectOptions: ['数学', '物理', '国际数学'],
    studentCenterStageOptions: ['小奥', '初中', '高中'],
  });

  assert.deepEqual(state.locks, {
    classCardInteractionLocked: false,
    classInteractionLocked: false,
    assignmentRefreshLocked: false,
    saving: false,
    deleting: false,
  });
  assert.deepEqual(state.errors, {
    formError: '',
    assignmentError: '',
  });
  assert.deepEqual(state.options, {
    academicSubjectOptions: ['数学', '物理', '国际数学'],
    studentCenterStageOptions: ['小奥', '初中', '高中'],
  });
  assert.deepEqual(state.mode, {
    newClassExpanded: true,
    editingClass: null,
    editingFormState: null,
  });
  assert.equal(state.newClass.form, newForm);
  assert.equal(state.newClass.teacher?.name, '曹老师');
  assert.equal(state.newClass.teacherUserId, 1);
  assert.deepEqual(state.newClass.filteredUsers.map((user) => user.name), ['曹老师']);
  assert.deepEqual(state.newClass.gradeOptions, gradeGroups.小奥);
  assert.equal(state.newClass.displayNamePreview, '数学·2025级·四年级·2班');
});

test('buildClassEditorModalState assembles editing modal state and falls back to saved class form', () => {
  const state = buildClassEditorModalState({
    expandedClassId: 8,
    classes,
    users,
    formByClassId: { new: emptyForm },
    emptyClassForm: emptyForm,
    teacherSearchByClassId: { 8: '王' },
    newClassTeacherUserId: null,
    teacherBindingByClassId: { 8: 2 },
    teacherBindingSavingByClassId: { 8: true },
    inviteByClassId: { 8: inviteInfo },
    inviteLoadingByClassId: { 8: true },
    inviteResettingByClassId: { 8: false },
    inviteErrorByClassId: { 8: '邀请码加载失败' },
    studentsByClassId: { 8: [{ id: 3, name: '学生A' }] },
    allStudents: [],
    studentsLoadingByClassId: { 8: false },
    studentSavingByClassId: { 8: true },
    studentErrorByClassId: { 8: '新增失败' },
    studentDraftNameByClassId: { 8: '新学生' },
    gradeGroups,
    gradeOptions,
    canEditTeacherBinding: true,
    classCardInteractionLocked: true,
    classInteractionLocked: true,
    assignmentRefreshLocked: true,
    saving: true,
    deleting: false,
    formError: '保存失败',
    assignmentError: '负责老师刷新失败',
    academicSubjectOptions: ['数学', '物理', '国际数学'],
    studentCenterStageOptions: ['小奥', '初中', '高中'],
  });

  assert.deepEqual(state.locks, {
    classCardInteractionLocked: true,
    classInteractionLocked: true,
    assignmentRefreshLocked: true,
    saving: true,
    deleting: false,
  });
  assert.deepEqual(state.errors, {
    formError: '保存失败',
    assignmentError: '负责老师刷新失败',
  });
  assert.deepEqual(state.options, {
    academicSubjectOptions: ['数学', '物理', '国际数学'],
    studentCenterStageOptions: ['小奥', '初中', '高中'],
  });
  assert.equal(state.mode.newClassExpanded, false);
  assert.equal(state.mode.editingClass?.id, 8);
  assert.equal(state.mode.editingFormState?.current_grade, '七年级');
  assert.deepEqual(state.editing.gradeOptions, gradeGroups.初中);
  assert.equal(state.editing.displayNamePreview, '物理·2025级·七年级·3班');
  assert.equal(state.editing.teacherSearch, '王');
  assert.equal(state.editing.currentTeacherUserId, 2);
  assert.equal(state.editing.teacherSummary, '王老师');
  assert.equal(state.editing.teacherBindingSaving, true);
  assert.deepEqual(state.editing.filteredUsers.map((user) => user.name), ['王老师']);
  assert.equal(state.editing.inviteInfo, inviteInfo);
  assert.equal(state.editing.inviteLoading, true);
  assert.equal(state.editing.inviteResetting, false);
  assert.equal(state.editing.inviteError, '邀请码加载失败');
  assert.deepEqual(state.editing.students, [{ id: 3, name: '学生A' }]);
  assert.deepEqual(state.editing.allStudents, []);
  assert.equal(state.editing.studentsLoading, false);
  assert.equal(state.editing.studentSaving, true);
  assert.equal(state.editing.studentError, '新增失败');
  assert.equal(state.editing.studentDraftName, '新学生');
  assert.equal(state.editing.canEditTeacherBinding, true);
});
