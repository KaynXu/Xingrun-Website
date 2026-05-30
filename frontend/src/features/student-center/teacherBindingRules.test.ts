import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildTeacherBindingRefreshErrorMessage,
  buildTeacherBindingRequest,
  executeTeacherBindingRequest,
  resolveTeacherBindingSaveErrorMessage,
  resolveTeacherBindingPreviousState,
  resolveTeacherBindingSavingEndState,
  resolveTeacherBindingSavingStartState,
  resolveClassesAfterTeacherBindingOptimisticUpdate,
  resolveClassesAfterTeacherBindingRollback,
  resolveTeacherBindingOptimisticClassItem,
  resolveTeacherBindingRollbackClassItem,
  resolveTeacherBindingRollbackTeacherBindings,
} from './teacherBindingRules';
import type { ClassItem } from './model';

test('teacher binding map rollback restores previous id only when optimistic binding is still current', () => {
  assert.deepEqual(
    resolveTeacherBindingRollbackTeacherBindings({ 7: 12, 9: 18 }, 7, null, 12),
    { 7: null, 9: 18 },
  );
  assert.deepEqual(
    resolveTeacherBindingRollbackTeacherBindings({ 7: 18, 9: 18 }, 7, null, 12),
    { 7: 18, 9: 18 },
  );
});

test('buildTeacherBindingRequest keeps the teacher binding endpoint and payload centralized', () => {
  assert.deepEqual(
    buildTeacherBindingRequest(7, 12),
    {
      path: '/api/classes/7/teacher',
      init: {
        method: 'PUT',
        body: JSON.stringify({ teacher_user_id: 12 }),
      },
    },
  );
});

test('executeTeacherBindingRequest sends the centralized teacher binding request through apiFetch', async () => {
  const calls: Array<{ path: string; init: { method: 'PUT'; body: string } }> = [];

  await executeTeacherBindingRequest(7, 12, async (path, init) => {
    calls.push({ path, init });
  });

  assert.deepEqual(calls, [
    {
      path: '/api/classes/7/teacher',
      init: {
        method: 'PUT',
        body: JSON.stringify({ teacher_user_id: 12 }),
      },
    },
  ]);
});

test('teacher binding refresh error message keeps saved-but-refresh-failed copy centralized', () => {
  assert.equal(
    buildTeacherBindingRefreshErrorMessage(new Error('网络超时')),
    '老师绑定已保存，但列表刷新失败：网络超时',
  );
});

test('teacher binding save error message preserves thrown error and default fallback copy', () => {
  assert.equal(resolveTeacherBindingSaveErrorMessage(new Error('无权限')), '无权限');
  assert.equal(resolveTeacherBindingSaveErrorMessage('failed'), '负责老师保存失败');
});

test('teacher binding previous state prefers binding map and falls back to class teacher fields', () => {
  const classes: ClassItem[] = [
    {
      id: 7,
      name: '六年级 2 班',
      subject: '数学',
      grade: '六年级',
      teacher_name: '班级老师',
      teacher_user_id: 12,
    },
    {
      id: 9,
      name: '七年级 1 班',
      subject: '物理',
      grade: '七年级',
      teacher_name: '',
      teacher_user_id: null,
    },
  ];

  assert.deepEqual(
    resolveTeacherBindingPreviousState(7, classes, { 7: 18 }),
    {
      previousClass: classes[0],
      previousTeacherUserId: 18,
      previousTeacherName: '班级老师',
    },
  );
  assert.deepEqual(
    resolveTeacherBindingPreviousState(9, classes, {}),
    {
      previousClass: classes[1],
      previousTeacherUserId: null,
      previousTeacherName: '',
    },
  );
});

test('teacher binding saving state starts and ends per class without touching other rows', () => {
  assert.deepEqual(
    resolveTeacherBindingSavingStartState({ 9: true }, 7),
    { 7: true, 9: true },
  );
  assert.deepEqual(
    resolveTeacherBindingSavingEndState({ 7: true, 9: true }, 7),
    { 9: true },
  );
});

test('teacher binding optimistic class item updates teacher id and keeps fallback name', () => {
  const classItem: ClassItem = {
    id: 7,
    name: '六年级 2 班',
    subject: '数学',
    grade: '六年级',
    teacher_name: '原老师',
    teacher_user_id: 12,
  };

  assert.deepEqual(
    resolveTeacherBindingOptimisticClassItem(classItem, { name: '新老师' }, 18),
    { ...classItem, teacher_name: '新老师', teacher_user_id: 18 },
  );
  assert.deepEqual(
    resolveTeacherBindingOptimisticClassItem(classItem, undefined, 18),
    { ...classItem, teacher_name: '原老师', teacher_user_id: 18 },
  );
});

test('teacher binding optimistic class list update only changes the target class', () => {
  const classes: ClassItem[] = [
    {
      id: 7,
      name: '六年级 2 班',
      subject: '数学',
      grade: '六年级',
      teacher_name: '原老师',
      teacher_user_id: 12,
    },
    {
      id: 9,
      name: '七年级 1 班',
      subject: '物理',
      grade: '七年级',
      teacher_name: '保留老师',
      teacher_user_id: 22,
    },
  ];

  assert.deepEqual(
    resolveClassesAfterTeacherBindingOptimisticUpdate(classes, 7, { name: '新老师' }, 18),
    [
      { ...classes[0], teacher_name: '新老师', teacher_user_id: 18 },
      classes[1],
    ],
  );
});

test('teacher binding class item rollback restores previous teacher only when optimistic binding is still current', () => {
  const optimisticClass: ClassItem = {
    id: 7,
    name: '六年级 2 班',
    subject: '数学',
    grade: '六年级',
    teacher_name: '新老师',
    teacher_user_id: 12,
  };

  assert.deepEqual(
    resolveTeacherBindingRollbackClassItem(optimisticClass, 12, null, ''),
    { ...optimisticClass, teacher_name: '', teacher_user_id: null },
  );
  assert.deepEqual(
    resolveTeacherBindingRollbackClassItem({ ...optimisticClass, teacher_name: '更新后的老师', teacher_user_id: 18 }, 12, null, ''),
    { ...optimisticClass, teacher_name: '更新后的老师', teacher_user_id: 18 },
  );
});

test('teacher binding class list rollback only restores the target stale optimistic class', () => {
  const classes: ClassItem[] = [
    {
      id: 7,
      name: '六年级 2 班',
      subject: '数学',
      grade: '六年级',
      teacher_name: '新老师',
      teacher_user_id: 18,
    },
    {
      id: 9,
      name: '七年级 1 班',
      subject: '物理',
      grade: '七年级',
      teacher_name: '保留老师',
      teacher_user_id: 22,
    },
  ];

  assert.deepEqual(
    resolveClassesAfterTeacherBindingRollback(classes, 7, 18, 12, '原老师'),
    [
      { ...classes[0], teacher_name: '原老师', teacher_user_id: 12 },
      classes[1],
    ],
  );
  assert.deepEqual(
    resolveClassesAfterTeacherBindingRollback(
      [{ ...classes[0], teacher_user_id: 33, teacher_name: '后续选择老师' }, classes[1]],
      7,
      18,
      12,
      '原老师',
    ),
    [{ ...classes[0], teacher_user_id: 33, teacher_name: '后续选择老师' }, classes[1]],
  );
});
