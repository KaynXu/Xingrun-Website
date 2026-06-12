import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
const authSource = readFileSync(resolve(process.cwd(), 'src/features/auth/PublicAuthModals.tsx'), 'utf8');
const accessSource = readFileSync(resolve(process.cwd(), 'src/features/navigation/workspaceAccess.ts'), 'utf8');
const approvalSource = readFileSync(resolve(process.cwd(), 'src/features/approval/ApprovalPage.tsx'), 'utf8');

function getApprovalPageSource(): string {
  return approvalSource;
}

test('landing and login source expose separate organization application and invite join entry points', () => {
  assert.match(appSource, /apply-organization/);
  assert.match(appSource, /join-organization/);
  assert.match(authSource, /申请开通机构/);
  assert.match(authSource, /加入已有机构/);
  assert.match(appSource, /getJoinInviteTokenFromPath/);
  assert.match(appSource, /publicAuthModal === 'join-organization'/);
  assert.match(authSource, /if \(!data\.token\)/);
  assert.match(appSource, /clearJoinInvitePathIfNeeded/);
  assert.doesNotMatch(authSource, /organization_name:\s*'星润Starain'/);
  assert.doesNotMatch(authSource, /\/api\/register-request/);
});

test('approval page source includes organization review and invite management sections', () => {
  const approvalSource = getApprovalPageSource();

  assert.match(approvalSource, /机构开通审批/);
  assert.match(approvalSource, /apiFetch<\{ items: OrganizationRequestItem\[] \}>\('\/api\/admin\/organization-requests'\)/);
  assert.match(approvalSource, /`\/api\/admin\/organization-requests\/\$\{requestId\}\/\$\{action\}`/);
  assert.match(approvalSource, /机构邀请设置/);
  assert.match(approvalSource, /apiFetch<OrganizationInviteInfo>\('\/api\/organization\/invite'\)/);
  assert.match(approvalSource, /apiFetch<OrganizationInviteInfo>\('\/api\/organization\/invite\/reset'/);
  assert.match(approvalSource, /apiFetch<\{ items: OrganizationSummaryItem\[] \}>\('\/api\/admin\/organizations'\)/);
  assert.match(approvalSource, /已注册机构/);
});

test('approval page source refreshes member login info after decisions and when the tab regains focus', () => {
  const approvalSource = getApprovalPageSource();

  assert.match(approvalSource, /const refreshApprovalMembers = useCallback\(async \(\) => \{/);
  assert.match(approvalSource, /await Promise\.all\(\[\s*loadUsers\(\),\s*loadClasses\(\),\s*loadBindingSummaries\(\),\s*\]\);/);
  assert.match(approvalSource, /refreshApprovalMembers\(\)\.catch\(\(\) => undefined\);/);
  assert.match(approvalSource, /window\.addEventListener\('focus', handleWindowFocus\)/);
  assert.match(approvalSource, /document\.addEventListener\('visibilitychange', handleVisibilityChange\)/);
  assert.match(approvalSource, /if \(document\.visibilityState === 'visible'\) \{\s*refreshApprovalMembers\(\)\.catch\(\(\) => undefined\);/);
});

test('approval page source lets managers edit member visible pages', () => {
  const approvalSource = getApprovalPageSource();

  assert.match(accessSource, /export const configurableWorkspacePages/);
  assert.match(approvalSource, /const \[visiblePageSavingUserId, setVisiblePageSavingUserId\] = useState<number \| null>\(null\);/);
  assert.match(approvalSource, /const handleToggleVisiblePage = async \(targetUser: UserItem, page: Page\) => \{/);
  assert.match(approvalSource, /apiFetch<\{ ok: boolean; user: UserItem \}>\(`\/api\/admin\/users\/\$\{targetUser\.id\}\/visible-pages`/);
  assert.match(approvalSource, /可见页面/);
  assert.match(approvalSource, /configurableWorkspacePages\.map/);
});

test('organization application success copy stays neutral and does not mention a specific reviewer name', () => {
  assert.match(authSource, /机构申请已提交，等待审核。/);
  assert.doesNotMatch(authSource, /等待 Kayn 审批/);
});
