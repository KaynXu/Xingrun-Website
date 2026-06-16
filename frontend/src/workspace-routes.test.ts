import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getWorkspacePageFromPathname,
  getWorkspacePath,
  normalizeWorkspacePathname,
} from './features/navigation/workspaceRoutes';

test('workspace route helper maps every workspace page to a stable path', () => {
  assert.equal(getWorkspacePath('dashboard'), '/workspace');
  assert.equal(getWorkspacePath('review-generation'), '/workspace/review-generation');
  assert.equal(getWorkspacePath('class-feedback-generation'), '/workspace/class-feedback-generation');
  assert.equal(getWorkspacePath('consultation'), '/workspace/consultation');
  assert.equal(getWorkspacePath('calendar'), '/workspace/calendar');
  assert.equal(getWorkspacePath('smartWrongQuestions'), '/workspace/smart-wrong-questions');
  assert.equal(getWorkspacePath('classes'), '/workspace/classes');
  assert.equal(getWorkspacePath('accounts'), '/workspace/accounts');
  assert.equal(getWorkspacePath('credit'), '/workspace/credit');
  assert.equal(getWorkspacePath('settings'), '/workspace/settings');
});

test('workspace route helper resolves canonical paths and aliases back to workspace pages', () => {
  assert.equal(getWorkspacePageFromPathname('/workspace'), 'dashboard');
  assert.equal(getWorkspacePageFromPathname('/workspace/dashboard'), 'dashboard');
  assert.equal(getWorkspacePageFromPathname('/workspace/review-generation'), 'review-generation');
  assert.equal(getWorkspacePageFromPathname('/workspace/class-feedback-generation'), 'class-feedback-generation');
  assert.equal(getWorkspacePageFromPathname('/workspace/consultation'), 'consultation');
  assert.equal(getWorkspacePageFromPathname('/workspace/calendar/'), 'calendar');
  assert.equal(getWorkspacePageFromPathname('/workspace/smart-wrong-questions'), 'smartWrongQuestions');
  assert.equal(getWorkspacePageFromPathname('/workspace/classes'), 'classes');
  assert.equal(getWorkspacePageFromPathname('/workspace/accounts'), 'accounts');
  assert.equal(getWorkspacePageFromPathname('/workspace/credit'), 'credit');
  assert.equal(getWorkspacePageFromPathname('/workspace/settings'), 'settings');
  assert.equal(getWorkspacePageFromPathname('/'), null);
  assert.equal(getWorkspacePageFromPathname('/join/demo-token'), null);
});

test('workspace route helper normalizes trailing slashes before matching', () => {
  assert.equal(normalizeWorkspacePathname('workspace/review-generation/'), '/workspace/review-generation');
  assert.equal(normalizeWorkspacePathname('/workspace//'), '/workspace');
  assert.equal(normalizeWorkspacePathname(''), '/');
});
