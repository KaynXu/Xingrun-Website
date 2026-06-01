import assert from 'node:assert/strict';
import test from 'node:test';
import {
  executeClassStudentCreateRequest,
  executeClassStudentDeleteRequest,
  executeClassStudentListRequest,
  resolveClassStudentDraftName,
  resolveClassStudentErrorMessage,
  resolveClassStudentsAfterCreate,
  resolveClassStudentsAfterDelete,
  resolveClassStudentsAfterLoad,
  resolveClassStudentSavingEndState,
  resolveClassStudentSavingStartState,
  resolveClassStudentDraftAfterCreate,
  validateClassStudentDraftName,
} from './classStudentRules';

const studentsByClassId = {
  11: [
    { id: 101, name: '陈一' },
  ],
  12: [
    { id: 201, name: '李二' },
    { id: 202, name: '王三' },
  ],
};

test('class student request executors call the existing class student API helpers', async () => {
  const calls: string[] = [];

  const listResult = await executeClassStudentListRequest(11, async (classId) => {
    calls.push(`list:${classId}`);
    return { students: studentsByClassId[11] };
  });
  const createResult = await executeClassStudentCreateRequest(11, 102, async (classId, studentId) => {
    calls.push(`create:${classId}:${studentId}`);
    return { student: { id: studentId, name: '新学生' }, deduplicated: false };
  });
  const deleteResult = await executeClassStudentDeleteRequest(11, 101, async (classId, studentId) => {
    calls.push(`delete:${classId}:${studentId}`);
    return { ok: true, removed: true };
  });

  assert.deepEqual(listResult.students, studentsByClassId[11]);
  assert.deepEqual(createResult.student, { id: 102, name: '新学生' });
  assert.deepEqual(deleteResult, { ok: true, removed: true });
  assert.deepEqual(calls, ['list:11', 'create:11:102', 'delete:11:101']);
});

test('class student rules preserve local loading state and error fallback copy', () => {
  assert.deepEqual(resolveClassStudentSavingStartState({ 11: false }, 12), { 11: false, 12: true });
  assert.deepEqual(resolveClassStudentSavingEndState({ 11: true, 12: true }, 12), { 11: true, 12: false });
  assert.equal(resolveClassStudentErrorMessage(new Error('学生重复'), 'create'), '学生重复');
  assert.equal(resolveClassStudentErrorMessage('boom', 'load'), '学生列表加载失败');
  assert.equal(resolveClassStudentErrorMessage('boom', 'create'), '新增学生失败，请重试。');
  assert.equal(resolveClassStudentErrorMessage('boom', 'delete'), '删除学生失败，请重试。');
});

test('class student rules update class student cache and draft state', () => {
  assert.equal(resolveClassStudentDraftName('  新学生  '), '新学生');
  assert.equal(validateClassStudentDraftName(''), '请输入学生姓名');
  assert.equal(validateClassStudentDraftName('  新学生  '), '');

  assert.deepEqual(resolveClassStudentsAfterLoad(studentsByClassId, 11, [{ id: 103, name: '加载后' }]), {
    ...studentsByClassId,
    11: [{ id: 103, name: '加载后' }],
  });
  assert.deepEqual(resolveClassStudentsAfterCreate(studentsByClassId, 11, { id: 102, name: '新学生' }), {
    ...studentsByClassId,
    11: [
      { id: 101, name: '陈一' },
      { id: 102, name: '新学生' },
    ],
  });
  assert.deepEqual(resolveClassStudentsAfterDelete(studentsByClassId, 12, 201), {
    ...studentsByClassId,
    12: [{ id: 202, name: '王三' }],
  });
  assert.deepEqual(resolveClassStudentDraftAfterCreate({ 11: '新学生', 12: '保留' }, 11), {
    11: '',
    12: '保留',
  });
});
