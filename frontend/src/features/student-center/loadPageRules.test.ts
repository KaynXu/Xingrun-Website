import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildClassLoadFailureState,
  buildClassLoadSuccessState,
  executeStudentCenterLoadRequest,
  isCurrentClassLoadRequest,
  normalizeTeacherBindings,
  resolveClassLoadError,
  resolveClassLoadStartState,
  resolveExpandedClassAfterLoadFailure,
  resolveExpandedClassAfterLoad,
  resolveFormsAfterClassLoadFailure,
  resolveFormsAfterClassLoad,
  resolveNewClassTeacherAfterClassLoadFailure,
} from './loadPageRules';
import type { ClassFormValues, ClassItem, UserItem } from './model';

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
  bridge_target: '默认下一学段',
  content_track: '',
};

const classes: ClassItem[] = [
  {
    id: 8,
    name: '2025级·四年级·1班',
    subject: '数学',
    grade: '四年级',
    stage: '小奥',
    current_grade: '四年级',
    class_number: '1',
    cohort_year: 2025,
  },
  {
    id: 9,
    name: '2025级·七年级·2班',
    subject: '物理',
    grade: '七年级',
    stage: '初中',
    current_grade: '七年级',
    class_number: '2',
    cohort_year: 2025,
  },
];

test('normalizeTeacherBindings converts API object keys to numeric class ids', () => {
  assert.deepEqual(
    normalizeTeacherBindings({ 8: 12, 9: null }),
    { 8: 12, 9: null },
  );
});

test('resolveFormsAfterClassLoad keeps the new draft and rebuilds loaded class forms', () => {
  const newDraft = { ...emptyForm, name: '保留的新建草稿', subject: '数学' };

  assert.deepEqual(
    resolveFormsAfterClassLoad(
      {
        new: newDraft,
        8: { ...emptyForm, name: '旧缓存' },
      },
      classes,
      emptyForm,
    ),
    {
      new: newDraft,
      8: {
        ...emptyForm,
        name: '2025级·四年级·1班',
        subject: '数学',
        grade: '四年级',
        stage: '小奥',
        current_grade: '四年级',
        class_number: '1',
        cohort_year: '2025',
      },
      9: {
        ...emptyForm,
        name: '2025级·七年级·2班',
        subject: '物理',
        grade: '七年级',
        stage: '初中',
        current_grade: '七年级',
        class_number: '2',
        cohort_year: '2025',
      },
    },
  );

  assert.deepEqual(resolveFormsAfterClassLoad({}, [], emptyForm), { new: emptyForm });
});

test('resolveExpandedClassAfterLoad preserves valid requested expansion and closes stale class ids', () => {
  assert.equal(resolveExpandedClassAfterLoad(8, undefined, classes), 8);
  assert.equal(resolveExpandedClassAfterLoad(8, 'new', classes), 'new');
  assert.equal(resolveExpandedClassAfterLoad(null, 9, classes), 9);
  assert.equal(resolveExpandedClassAfterLoad(8, 999, classes), null);
  assert.equal(resolveExpandedClassAfterLoad(999, undefined, classes), null);
});

test('resolveClassLoadError preserves real errors and falls back to the class management load message', () => {
  assert.equal(resolveClassLoadError(new Error('网络失败')).message, '网络失败');
  assert.equal(resolveClassLoadError('failed').message, '班级管理数据加载失败');
});

test('class load failure rules reset editor state to a clean new draft', () => {
  assert.deepEqual(resolveFormsAfterClassLoadFailure(emptyForm), { new: emptyForm });
  assert.equal(resolveNewClassTeacherAfterClassLoadFailure(), null);
  assert.equal(resolveExpandedClassAfterLoadFailure(), null);
});

test('executeStudentCenterLoadRequest loads classes, staff users, and teacher bindings when allowed', async () => {
  const requests: Array<{ endpoint: string; init?: RequestInit }> = [];
  const users: UserItem[] = [{ id: 3, name: '曹老师', org: '星润', role: 'member' }];
  const apiFetch = async <T>(endpoint: string, init?: RequestInit): Promise<T> => {
    requests.push({ endpoint, init });
    if (endpoint === '/api/classes') {
      return classes as T;
    }
    if (endpoint === '/api/admin/users') {
      return users as T;
    }
    return { teacher_bindings: { 8: 3, 9: null } } as T;
  };

  assert.deepEqual(await executeStudentCenterLoadRequest(apiFetch, true), {
    classItems: classes,
    userItems: users,
    teacherBindingData: { teacher_bindings: { 8: 3, 9: null } },
  });
  assert.deepEqual(requests, [
    { endpoint: '/api/classes', init: undefined },
    { endpoint: '/api/admin/users', init: undefined },
    { endpoint: '/api/classes/teacher-bindings', init: undefined },
  ]);
});

test('executeStudentCenterLoadRequest skips staff-only requests when not allowed', async () => {
  const requests: string[] = [];
  const apiFetch = async <T>(endpoint: string): Promise<T> => {
    requests.push(endpoint);
    return classes as T;
  };

  assert.deepEqual(await executeStudentCenterLoadRequest(apiFetch, false), {
    classItems: classes,
    userItems: [],
    teacherBindingData: { teacher_bindings: {} },
  });
  assert.deepEqual(requests, ['/api/classes']);
});

test('class load request lifecycle rules increment versions and identify stale requests', () => {
  assert.deepEqual(resolveClassLoadStartState(4), {
    requestVersion: 5,
    loading: true,
    pageError: '',
  });
  assert.equal(isCurrentClassLoadRequest(5, 5), true);
  assert.equal(isCurrentClassLoadRequest(4, 5), false);
});

test('buildClassLoadSuccessState bundles loaded classes, users, bindings, forms, and expansion', () => {
  const newDraft = { ...emptyForm, name: '保留的新建草稿', subject: '数学' };
  const users: UserItem[] = [{ id: 3, name: '曹老师', org: '星润', role: 'member' }];

  assert.deepEqual(buildClassLoadSuccessState({
    classItems: classes,
    userItems: users,
    rawTeacherBindings: { 8: 3 },
    currentFormByClassId: { new: newDraft, 8: { ...emptyForm, name: '旧缓存' } },
    currentExpandedClassId: 8,
    preferredExpandedClassId: 9,
    emptyClassForm: emptyForm,
  }), {
    classes,
    users,
    teacherBindingByClassId: { 8: 3 },
    formByClassId: {
      new: newDraft,
      8: {
        ...emptyForm,
        name: '2025级·四年级·1班',
        subject: '数学',
        grade: '四年级',
        stage: '小奥',
        current_grade: '四年级',
        class_number: '1',
        cohort_year: '2025',
      },
      9: {
        ...emptyForm,
        name: '2025级·七年级·2班',
        subject: '物理',
        grade: '七年级',
        stage: '初中',
        current_grade: '七年级',
        class_number: '2',
        cohort_year: '2025',
      },
    },
    expandedClassId: 9,
  });
});

test('buildClassLoadFailureState bundles reset state for non-preserved failures', () => {
  assert.deepEqual(buildClassLoadFailureState(emptyForm), {
    classes: [],
    users: [],
    teacherBindingByClassId: {},
    formByClassId: { new: emptyForm },
    newClassTeacherUserId: null,
    expandedClassId: null,
  });
});
