import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

test('class management fetches and resets class invite codes', () => {
  assert.match(appSource, /apiFetch<ClassInviteInfo>\(`\/api\/classes\/\$\{classId\}\/invite`\)/);
  assert.match(appSource, /apiFetch<ClassInviteInfo>\(`\/api\/classes\/\$\{classId\}\/invite\/reset`, \{/);
  assert.match(appSource, /家长绑定邀请码/);
  assert.match(appSource, /当前邀请码/);
  assert.match(appSource, /微信小程序里绑定该班级并选择对应学生/);
});
