import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

test('landing and login source expose separate organization application and invite join entry points', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /apply-organization/);
  assert.match(source, /join-organization/);
  assert.match(source, /申请开通机构/);
  assert.match(source, /加入已有机构/);
  assert.match(source, /getJoinInviteTokenFromPath/);
  assert.match(source, /publicAuthModal === 'join-organization'/);
  assert.match(source, /if \(!data\.token\)/);
  assert.match(source, /clearJoinInvitePathIfNeeded/);
  assert.doesNotMatch(source, /organization_name:\s*'星润Starain'/);
  assert.doesNotMatch(source, /\/api\/register-request/);
});

test('approval page source includes organization review and invite management sections', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const approvalBlock = source.match(/const ApprovalPage = \([\s\S]*?\n};\n\nconst SettingsPage/);

  assert.ok(approvalBlock);
  assert.match(approvalBlock[0], /机构开通审批/);
  assert.match(approvalBlock[0], /apiFetch<\{ items: OrganizationRequestItem\[] \}>\('\/api\/admin\/organization-requests'\)/);
  assert.match(approvalBlock[0], /`\/api\/admin\/organization-requests\/\$\{requestId\}\/\$\{action\}`/);
  assert.match(approvalBlock[0], /机构邀请设置/);
  assert.match(approvalBlock[0], /apiFetch<OrganizationInviteInfo>\('\/api\/organization\/invite'\)/);
  assert.match(approvalBlock[0], /apiFetch<OrganizationInviteInfo>\('\/api\/organization\/invite\/reset'/);
  assert.match(approvalBlock[0], /apiFetch<\{ items: OrganizationSummaryItem\[] \}>\('\/api\/admin\/organizations'\)/);
  assert.match(approvalBlock[0], /已注册机构/);
});

test('approval page source refreshes member login info after decisions and when the tab regains focus', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const approvalBlock = source.match(/const ApprovalPage = \([\s\S]*?\n};\n\nconst SettingsPage/);

  assert.ok(approvalBlock);
  assert.match(approvalBlock[0], /const refreshApprovalMembers = useCallback\(async \(\) => \{/);
  assert.match(approvalBlock[0], /await Promise\.all\(\[\s*loadUsers\(\),\s*loadBindingSummaries\(\),\s*\]\);/);
  assert.match(approvalBlock[0], /refreshApprovalMembers\(\)\.catch\(\(\) => undefined\);/);
  assert.match(approvalBlock[0], /window\.addEventListener\('focus', handleWindowFocus\)/);
  assert.match(approvalBlock[0], /document\.addEventListener\('visibilitychange', handleVisibilityChange\)/);
  assert.match(approvalBlock[0], /if \(document\.visibilityState === 'visible'\) \{\s*refreshApprovalMembers\(\)\.catch\(\(\) => undefined\);/);
});
test('organization application success copy stays neutral and does not mention a specific reviewer name', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /申请已提交，等待审核(?:通过后即可登录后台。|。)/);
  assert.match(source, /机构申请已提交，等待审核。/);
  assert.doesNotMatch(source, /等待 Kayn 审批/);
});
