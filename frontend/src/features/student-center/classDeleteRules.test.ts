import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildClassDeleteConfirmMessage,
  buildClassDeleteRequest,
  executeClassDeleteRequest,
  resolveClassesAfterDelete,
  resolveClassDeleteErrorMessage,
  resolveExpandedClassAfterDelete,
  resolveFormsAfterClassDelete,
  resolveTeacherBindingsAfterClassDelete,
  resolveTeacherSearchAfterClassDelete,
} from './classDeleteRules';
import type { ClassItem } from './model';

test('buildClassDeleteConfirmMessage keeps the existing confirmation copy', () => {
  assert.equal(
    buildClassDeleteConfirmMessage({ name: '数学四年级1班' }),
    '确定删除班级「数学四年级1班」吗？',
  );
});

test('resolveExpandedClassAfterDelete closes only the deleted class editor', () => {
  assert.equal(resolveExpandedClassAfterDelete(12, 12), null);
  assert.equal(resolveExpandedClassAfterDelete(13, 12), 13);
  assert.equal(resolveExpandedClassAfterDelete('new', 12), 'new');
  assert.equal(resolveExpandedClassAfterDelete(null, 12), null);
});

test('class delete rules clear deleted class local caches without touching new draft or other classes', () => {
  const classes: ClassItem[] = [
    { id: 12, name: '待删除班级', subject: '数学', grade: '四年级' },
    { id: 13, name: '保留班级', subject: '物理', grade: '七年级' },
  ];

  assert.deepEqual(resolveClassesAfterDelete(classes, 12), [classes[1]]);
  assert.deepEqual(resolveTeacherBindingsAfterClassDelete({ 12: 8, 13: 9 }, 12), { 13: 9 });
  assert.deepEqual(
    resolveFormsAfterClassDelete(
      {
        new: { name: '新建草稿' },
        12: { name: '删除班级草稿' },
        13: { name: '保留班级草稿' },
      },
      12,
    ),
    {
      new: { name: '新建草稿' },
      13: { name: '保留班级草稿' },
    },
  );
  assert.deepEqual(resolveTeacherSearchAfterClassDelete({ new: '新', 12: '删', 13: '留' }, 12), { new: '新', 13: '留' });
});

test('buildClassDeleteRequest keeps the delete endpoint centralized', () => {
  assert.deepEqual(
    buildClassDeleteRequest(12),
    {
      path: '/api/classes/12',
      init: { method: 'DELETE' },
    },
  );
});

test('executeClassDeleteRequest sends the centralized delete request through apiFetch', async () => {
  const calls: Array<{ path: string; init: { method: 'DELETE' } }> = [];

  await executeClassDeleteRequest(12, async (path, init) => {
    calls.push({ path, init });
  });

  assert.deepEqual(calls, [
    {
      path: '/api/classes/12',
      init: { method: 'DELETE' },
    },
  ]);
});

test('resolveClassDeleteErrorMessage preserves thrown error and fallback copy', () => {
  assert.equal(resolveClassDeleteErrorMessage(new Error('无权限删除')), '无权限删除');
  assert.equal(resolveClassDeleteErrorMessage('failed'), '班级删除失败');
});
