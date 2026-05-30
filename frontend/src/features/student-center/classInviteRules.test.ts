import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildClassInviteLoadRequest,
  buildClassInviteResetRequest,
  executeClassInviteLoadRequest,
  executeClassInviteResetRequest,
  resolveClassInviteErrorMessage,
  resolveInviteLoadingEndState,
  resolveInviteLoadingStartState,
} from './classInviteRules';
import type { ClassInviteInfo } from './model';

const invitePayload: ClassInviteInfo = {
  id: 1,
  class_id: 42,
  invite_code: 'XR2026',
  status: 'active',
  created_at: '2026-05-29T00:00:00.000Z',
};

test('class invite requests keep load and reset endpoints centralized', () => {
  assert.deepEqual(buildClassInviteLoadRequest(42), {
    endpoint: '/api/classes/42/invite',
  });
  assert.deepEqual(buildClassInviteResetRequest(42), {
    endpoint: '/api/classes/42/invite/reset',
    init: { method: 'POST' },
  });
});

test('class invite request executors send centralized requests through apiFetch', async () => {
  const calls: Array<{ endpoint: string; init?: RequestInit }> = [];
  const apiFetch = async <T>(endpoint: string, init?: RequestInit): Promise<T> => {
    calls.push({ endpoint, init });
    return invitePayload as T;
  };

  assert.deepEqual(await executeClassInviteLoadRequest(42, apiFetch), invitePayload);
  assert.deepEqual(await executeClassInviteResetRequest(42, apiFetch), invitePayload);
  assert.deepEqual(calls, [
    { endpoint: '/api/classes/42/invite', init: undefined },
    { endpoint: '/api/classes/42/invite/reset', init: { method: 'POST' } },
  ]);
});

test('class invite rules preserve loading maps and error fallback copy', () => {
  assert.deepEqual(resolveInviteLoadingStartState({ 1: false }, 42), { 1: false, 42: true });
  assert.deepEqual(resolveInviteLoadingEndState({ 1: true, 42: true }, 42), { 1: true, 42: false });
  assert.equal(resolveClassInviteErrorMessage(new Error('无效邀请码'), 'load'), '无效邀请码');
  assert.equal(resolveClassInviteErrorMessage('boom', 'load'), '邀请码加载失败');
  assert.equal(resolveClassInviteErrorMessage('boom', 'reset'), '邀请码重置失败');
});
