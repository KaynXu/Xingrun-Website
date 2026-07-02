import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildClassCreateRequest,
  buildOptimisticCreatedClassItem,
  buildClassSavePayload,
  buildClassUpdateRequest,
  executeClassCreateRequest,
  executeClassUpdateRequest,
  findDuplicateClass,
  resolveClassesAfterOptimisticCreate,
  resolveExpandedClassAfterOptimisticCreate,
  resolveClassFormDraftDirty,
  resolveFormsAfterClassDraftReset,
  resolveFormsAfterCreateDraftReset,
  resolveFormsAfterOptimisticCreate,
  resolveClassSaveFormWithCurrentStudents,
  resolveNewClassTeacherAfterDraftReset,
  resolveNewClassTeacherAfterCreate,
  resolveTeacherSearchAfterClassDraftReset,
  resolveTeacherBindingsAfterOptimisticCreate,
  resolveClassSaveErrorMessage,
  resolveClassSaveRefreshErrorMessage,
  resolveCreatedClassTeacherBindingErrorMessage,
  validateClassSaveDraft,
} from './classSaveRules';
import type { ClassFormValues, ClassItem, UserItem } from './model';

const baseForm: ClassFormValues = {
  name: '',
  class_type: 'group',
  subject: '数学',
  grade: '',
  teacher_name: '',
  stage: '小奥',
  current_grade: '四年级',
  class_number: '1',
  cohort_year: '2025',
  show_cohort_year: true,
  is_bridge: false,
  bridge_target: '小学衔接初中',
  content_track: '',
  selected_student_ids: [],
};

const teacher: UserItem = {
  id: 12,
  name: '曹老师',
  org: '星润',
  role: 'member',
};

test('buildClassSavePayload uses unified naming and teacher account for new classes', () => {
  const payload = buildClassSavePayload({
    classId: 'new',
    form: baseForm,
    selectedTeacher: teacher,
    selectedTeacherUserId: teacher.id,
  });

  assert.deepEqual(payload, {
    name: '数学·小2025级·四年级·1班',
    class_type: 'group',
    subject: '数学',
    grade: '四年级',
    teacher_name: '曹老师',
    teacher_email: '',
    stage: '小奥',
    current_grade: '四年级',
    class_number: '1',
    cohort_year: 2025,
    show_cohort_year: true,
    is_bridge: false,
    bridge_target: '小学衔接初中',
    content_track: '',
    student_ids: [],
    teacher_user_id: 12,
  });
});

test('buildClassSavePayload uses the same naming rules for existing class fixes without rebinding teacher', () => {
  const fixedForm: ClassFormValues = {
    ...baseForm,
    subject: '物理',
    stage: '初中',
    current_grade: '七年级',
    grade: '7年级',
    class_number: '3',
    cohort_year: '2025',
  };

  const payload = buildClassSavePayload({
    classId: 8,
    form: fixedForm,
    selectedTeacher: teacher,
    selectedTeacherUserId: teacher.id,
  });

  assert.deepEqual(payload, {
    name: '物理·初2025级·七年级·3班',
    class_type: 'group',
    subject: '物理',
    grade: '七年级',
    teacher_name: '曹老师',
    teacher_email: '',
    stage: '初中',
    current_grade: '七年级',
    class_number: '3',
    cohort_year: 2025,
    show_cohort_year: true,
    is_bridge: false,
    bridge_target: '小学衔接初中',
    content_track: '',
    student_ids: [],
    teacher_user_id: undefined,
  });
});

test('class save requests keep create and update endpoints centralized', () => {
  const payload = buildClassSavePayload({
    classId: 'new',
    form: baseForm,
    selectedTeacher: teacher,
    selectedTeacherUserId: teacher.id,
  });

  assert.deepEqual(
    buildClassCreateRequest(payload),
    {
      path: '/api/classes',
      init: {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    },
  );
  assert.deepEqual(
    buildClassUpdateRequest(8, payload),
    {
      path: '/api/classes/8',
      init: {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    },
  );
});

test('class save request executors send create and update requests through apiFetch', async () => {
  const payload = buildClassSavePayload({
    classId: 'new',
    form: baseForm,
    selectedTeacher: teacher,
    selectedTeacherUserId: teacher.id,
  });
  const calls: Array<{ path: string; init: { method: 'POST' | 'PUT'; body: string } }> = [];

  const created = await executeClassCreateRequest(payload, async (path, init) => {
    calls.push({ path, init });
    return { id: 8, name: '新班级' };
  });
  await executeClassUpdateRequest(8, payload, async (path, init) => {
    calls.push({ path, init });
  });

  assert.deepEqual(created, { id: 8, name: '新班级' });
  assert.deepEqual(calls, [
    {
      path: '/api/classes',
      init: {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    },
    {
      path: '/api/classes/8',
      init: {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    },
  ]);
});

test('buildOptimisticCreatedClassItem mirrors the newly created class with selected teacher fields', () => {
  const payload = buildClassSavePayload({
    classId: 'new',
    form: baseForm,
    selectedTeacher: teacher,
    selectedTeacherUserId: teacher.id,
  });

  assert.deepEqual(
    buildOptimisticCreatedClassItem({
      createdClassId: 8,
      payload,
      selectedTeacher: teacher,
      selectedTeacherUserId: teacher.id,
    }),
    {
      id: 8,
      name: '数学·小2025级·四年级·1班',
      class_type: 'group',
      subject: '数学',
      grade: '四年级',
      stage: '小奥',
      current_grade: '四年级',
      class_number: '1',
      cohort_year: 2025,
      show_cohort_year: true,
      is_bridge: false,
      bridge_target: '小学衔接初中',
      content_track: '',
      teacher_name: '曹老师',
      teacher_email: '',
      teacher_user_id: 12,
    },
  );
});

test('resolveClassesAfterOptimisticCreate replaces stale matching class and appends the created class', () => {
  const staleClass: ClassItem = {
    id: 8,
    name: '旧缓存班级',
    subject: '数学',
    grade: '四年级',
  };
  const existingClass: ClassItem = {
    id: 2,
    name: '保留班级',
    subject: '物理',
    grade: '七年级',
  };
  const createdClass = buildOptimisticCreatedClassItem({
    createdClassId: 8,
    payload: buildClassSavePayload({
      classId: 'new',
      form: baseForm,
      selectedTeacher: teacher,
      selectedTeacherUserId: teacher.id,
    }),
    selectedTeacher: teacher,
    selectedTeacherUserId: teacher.id,
  });

  assert.deepEqual(
    resolveClassesAfterOptimisticCreate([existingClass, staleClass], createdClass),
    [existingClass, createdClass],
  );
});

test('resolveTeacherBindingsAfterOptimisticCreate records the new class teacher without touching others', () => {
  assert.deepEqual(
    resolveTeacherBindingsAfterOptimisticCreate({ 2: 9 }, 8, 12),
    { 2: 9, 8: 12 },
  );
});

test('resolveFormsAfterOptimisticCreate stores the created class form without clearing other form drafts', () => {
  const createdForm: ClassFormValues = {
    ...baseForm,
    name: '数学·小2025级·四年级·1班',
  };

  assert.deepEqual(
    resolveFormsAfterOptimisticCreate(
      {
        new: baseForm,
        2: { ...baseForm, name: '保留编辑草稿' },
      },
      8,
      createdForm,
    ),
    {
      new: baseForm,
      2: { ...baseForm, name: '保留编辑草稿' },
      8: createdForm,
    },
  );
});

test('resolveFormsAfterCreateDraftReset clears only the new class draft', () => {
  const emptyForm: ClassFormValues = {
    ...baseForm,
    name: '',
    subject: '',
    current_grade: '',
    class_number: '',
  };
  const editingDraft: ClassFormValues = {
    ...baseForm,
    name: '保留编辑草稿',
  };

  assert.deepEqual(
    resolveFormsAfterCreateDraftReset(
      {
        new: { ...baseForm, name: '待清空的新建草稿' },
        2: editingDraft,
      },
      emptyForm,
    ),
    {
      new: emptyForm,
      2: editingDraft,
    },
  );
});

test('created class UI state rules reset new teacher and expand the created class', () => {
  assert.equal(resolveNewClassTeacherAfterCreate(), null);
  assert.equal(resolveExpandedClassAfterOptimisticCreate(8), 8);
});

test('resolveClassFormDraftDirty handles new and existing class drafts with one rule', () => {
  assert.equal(
    resolveClassFormDraftDirty({
      classId: 'new',
      currentForm: baseForm,
      savedForm: { ...baseForm },
      newClassTeacherUserId: null,
    }),
    false,
  );
  assert.equal(
    resolveClassFormDraftDirty({
      classId: 'new',
      currentForm: baseForm,
      savedForm: { ...baseForm },
      newClassTeacherUserId: 12,
    }),
    true,
  );
  assert.equal(
    resolveClassFormDraftDirty({
      classId: 8,
      currentForm: { ...baseForm, class_number: '2' },
      savedForm: baseForm,
      newClassTeacherUserId: null,
    }),
    true,
  );
  assert.equal(
    resolveClassFormDraftDirty({
      classId: 8,
      currentForm: baseForm,
      savedForm: null,
      newClassTeacherUserId: null,
    }),
    false,
  );
  assert.equal(
    resolveClassFormDraftDirty({
      classId: 8,
      currentForm: baseForm,
      savedForm: { ...baseForm },
      newClassTeacherUserId: null,
      currentTeacherUserId: 2,
      savedTeacherUserId: 1,
    }),
    true,
  );
  assert.equal(
    resolveClassFormDraftDirty({
      classId: 8,
      currentForm: baseForm,
      savedForm: { ...baseForm },
      newClassTeacherUserId: null,
      currentStudentIds: [3],
      savedStudentIds: [3, 4],
    }),
    true,
  );
  assert.equal(
    resolveClassFormDraftDirty({
      classId: 8,
      currentForm: baseForm,
      savedForm: { ...baseForm },
      newClassTeacherUserId: null,
      currentTeacherUserId: 1,
      savedTeacherUserId: 1,
      currentStudentIds: [4, 3],
      savedStudentIds: [3, 4],
    }),
    false,
  );
});

test('class draft reset rules reset new draft helpers and restore existing class drafts', () => {
  const emptyForm: ClassFormValues = {
    ...baseForm,
    name: '',
    subject: '',
    current_grade: '',
    class_number: '',
  };
  const savedExistingForm: ClassFormValues = {
    ...baseForm,
    name: '已保存旧班级',
    current_grade: '七年级',
  };

  assert.deepEqual(
    resolveFormsAfterClassDraftReset(
      {
        new: { ...baseForm, name: '待放弃的新建草稿' },
        8: { ...baseForm, name: '待放弃的旧班级草稿' },
      },
      'new',
      emptyForm,
    ),
    {
      new: emptyForm,
      8: { ...baseForm, name: '待放弃的旧班级草稿' },
    },
  );
  assert.deepEqual(
    resolveFormsAfterClassDraftReset(
      {
        new: emptyForm,
        8: { ...baseForm, name: '待放弃的旧班级草稿' },
      },
      8,
      savedExistingForm,
    ),
    {
      new: emptyForm,
      8: savedExistingForm,
    },
  );
  assert.equal(resolveNewClassTeacherAfterDraftReset('new', 12), null);
  assert.equal(resolveNewClassTeacherAfterDraftReset(8, 12), 12);
  assert.deepEqual(
    resolveTeacherSearchAfterClassDraftReset({ new: '曹', 8: '王' }, 'new'),
    { new: '', 8: '王' },
  );
  assert.deepEqual(
    resolveTeacherSearchAfterClassDraftReset({ new: '曹', 8: '王' }, 8),
    { new: '曹', 8: '王' },
  );
});

test('class save error messages preserve existing user-facing copy', () => {
  assert.equal(
    resolveClassSaveRefreshErrorMessage('new', new Error('网络超时')),
    '班级和负责老师已保存，但列表刷新失败：网络超时',
  );
  assert.equal(
    resolveClassSaveRefreshErrorMessage(8, new Error('网络超时')),
    '班级已保存，但列表刷新失败：网络超时',
  );
  assert.equal(resolveClassSaveErrorMessage(new Error('无权限')), '无权限');
  assert.equal(resolveClassSaveErrorMessage('failed'), '班级保存失败');
  assert.equal(
    resolveCreatedClassTeacherBindingErrorMessage(new Error('账号不可用')),
    '班级已创建，但负责老师绑定失败：账号不可用',
  );
  assert.equal(
    resolveCreatedClassTeacherBindingErrorMessage('failed'),
    '班级已创建，但负责老师绑定失败，请在班级卡片中重新选择老师',
  );
});

test('validateClassSaveDraft returns the same user-facing validation messages', () => {
  assert.equal(
    validateClassSaveDraft({ classId: 'new', selectedTeacherUserId: null, payload: buildClassSavePayload({ classId: 'new', form: baseForm, selectedTeacher: undefined, selectedTeacherUserId: null }), gradeOptions: ['四年级'] }),
    '请先选择负责老师账号',
  );

  assert.equal(
    validateClassSaveDraft({ classId: 1, selectedTeacherUserId: null, payload: { ...buildClassSavePayload({ classId: 1, form: baseForm, selectedTeacher: undefined, selectedTeacherUserId: null }), subject: '' }, gradeOptions: ['四年级'] }),
    '学科不能为空',
  );

  assert.equal(
    validateClassSaveDraft({ classId: 1, selectedTeacherUserId: null, payload: { ...buildClassSavePayload({ classId: 1, form: baseForm, selectedTeacher: undefined, selectedTeacherUserId: null }), current_grade: '未知年级' }, gradeOptions: ['四年级'] }),
    '请选择年级',
  );
});

test('small class save payload uses existing student names and validates required size', () => {
  const smallClassForm: ClassFormValues = {
    ...baseForm,
    class_type: '1v2',
    class_number: '',
    current_grade: '七年级',
    stage: '初中',
    selected_student_ids: [21, 22],
  };
  const payload = buildClassSavePayload({
    classId: 'new',
    form: smallClassForm,
    selectedTeacher: teacher,
    selectedTeacherUserId: teacher.id,
    existingStudents: [
      { id: 21, name: '张三' },
      { id: 22, name: '李四' },
    ],
  });

  assert.deepEqual({
    name: payload.name,
    class_type: payload.class_type,
    class_number: payload.class_number,
    student_ids: payload.student_ids,
  }, {
    name: '数学·1v2·初2025级·七年级·张李',
    class_type: '1v2',
    class_number: '',
    student_ids: [21, 22],
  });
  assert.equal(
    validateClassSaveDraft({
      classId: 'new',
      selectedTeacherUserId: teacher.id,
      payload: { ...payload, student_ids: [21] },
      gradeOptions: ['七年级'],
    }),
    '请选择2名学员',
  );
});

test('short-term drill class save payload does not require class number or selected students', () => {
  const payload = buildClassSavePayload({
    classId: 'new',
    form: {
      ...baseForm,
      class_type: 'short_term_drill',
      subject: '物理',
      stage: '初中',
      current_grade: '九年级',
      class_number: '',
      cohort_year: '2024',
      selected_student_ids: [],
    },
    selectedTeacher: { id: 24, name: '李一', org: '星润', role: 'member' },
    selectedTeacherUserId: 24,
    existingStudents: [],
  });

  assert.equal(payload.name, '物理·初2024级·九年级·短期刷题班');
  assert.equal(payload.class_type, 'short_term_drill');
  assert.equal(payload.class_number, '');
  assert.deepEqual(payload.student_ids, []);
  assert.equal(
    validateClassSaveDraft({
      classId: 'new',
      selectedTeacherUserId: 24,
      payload,
      gradeOptions: ['九年级'],
    }),
    null,
  );
});

test('existing class save form uses the currently loaded student list for small class validation', () => {
  const syncedForm = resolveClassSaveFormWithCurrentStudents({
    classId: 9,
    form: {
      ...baseForm,
      class_type: '1v1',
      selected_student_ids: [],
    },
    studentsByClassId: {
      9: [{ id: 88, name: '何晨煜' }],
    },
  });

  const payload = buildClassSavePayload({
    classId: 9,
    form: syncedForm,
    selectedTeacher: teacher,
    selectedTeacherUserId: teacher.id,
    existingStudents: [{ id: 88, name: '何晨煜' }],
  });

  assert.deepEqual(payload.student_ids, [88]);
  assert.equal(
    validateClassSaveDraft({
      classId: 9,
      selectedTeacherUserId: null,
      payload,
      gradeOptions: ['四年级'],
    }),
    null,
  );
});

test('findDuplicateClass ignores the class being edited and matches normalized grade identity', () => {
  const classes: ClassItem[] = [
    {
      id: 1,
      name: '旧名字',
      subject: '数学',
      grade: '4年级',
      stage: '小奥',
      current_grade: '4年级',
      class_number: '1',
      cohort_year: 2025,
      teacher_name: '曹老师',
      teacher_user_id: 12,
    },
    {
      id: 2,
      name: '物理四年级1班',
      subject: '物理',
      grade: '四年级',
      stage: '小奥',
      current_grade: '四年级',
      class_number: '1',
      cohort_year: 2025,
    },
  ];
  const payload = buildClassSavePayload({
    classId: 'new',
    form: baseForm,
    selectedTeacher: teacher,
    selectedTeacherUserId: teacher.id,
  });

  assert.equal(findDuplicateClass(classes, 1, payload), undefined);
  assert.equal(findDuplicateClass(classes, 'new', payload)?.id, 1);
});

test('findDuplicateClass allows the same class key for different teachers', () => {
  const classes: ClassItem[] = [
    {
      id: 1,
      name: '数学·初2026级·七年级·3班',
      subject: '数学',
      grade: '七年级',
      stage: '初中',
      current_grade: '七年级',
      class_number: '3',
      cohort_year: 2026,
      teacher_name: '曹老师',
      teacher_user_id: 23,
    },
  ];
  const payload = buildClassSavePayload({
    classId: 'new',
    form: {
      ...baseForm,
      stage: '初中',
      current_grade: '七年级',
      class_number: '3',
      cohort_year: '2026',
    },
    selectedTeacher: { id: 13, name: '李森', org: '星润', role: 'member' },
    selectedTeacherUserId: 13,
  });

  assert.equal(findDuplicateClass(classes, 'new', payload), undefined);
  assert.equal(
    findDuplicateClass(
      classes,
      'new',
      { ...payload, teacher_name: '曹老师', teacher_user_id: 23 },
    )?.id,
    1,
  );
});
