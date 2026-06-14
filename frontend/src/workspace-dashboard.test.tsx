import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { renderToStaticMarkup } from 'react-dom/server';
import { WorkspaceDashboard, getOrganizationManagementEntries } from './WorkspaceDashboard';

type DashboardRole = 'super_owner' | 'owner' | 'admin' | 'member';

const defaultStyles = {
  pageClass: 'workspace-page',
  cardClass: 'workspace-card',
  primaryButtonClass: 'workspace-primary',
  secondaryButtonClass: 'workspace-secondary',
};

function renderDashboard(role: DashboardRole): string {
  return renderToStaticMarkup(
    <WorkspaceDashboard
      currentUser={{
        display_name: '测试用户',
        role,
      }}
      setActivePage={() => undefined}
      styles={defaultStyles}
      canOpenAccounts={role !== 'member'}
    />,
  );
}

test('member workspace prioritizes quick actions and personal work context', () => {
  const markup = renderDashboard('member');

  assert.match(markup, /工作台/);
  assert.match(markup, /新建复习文档/);
  assert.match(markup, /补课堂反馈/);
  assert.match(markup, /查看课程日历/);
  assert.match(markup, /继续错题跟进/);
  assert.match(markup, /待处理/);
  assert.match(markup, /最近记录/);
  assert.doesNotMatch(markup, /快速开始/);
  assert.doesNotMatch(markup, /我的教学概览/);
});

test('workspace dashboard shows admin operations overview', () => {
  const markup = renderDashboard('admin');

  assert.match(markup, /机构工作台/);
  assert.match(markup, /查看班级安排/);
  assert.match(markup, /补课堂反馈/);
  assert.match(markup, /班级管理/);
  assert.match(markup, /处理账号审批/);
  assert.match(markup, /待处理事项/);
  assert.match(markup, /智能错题/);
  assert.doesNotMatch(markup, /新建复习文档/);
});

test('workspace dashboard shows owner operations overview', () => {
  const markup = renderDashboard('owner');

  assert.match(markup, /机构工作台/);
  assert.match(markup, /查看班级安排/);
  assert.match(markup, /待处理事项/);
  assert.match(markup, /账号审批/);
  assert.match(markup, /课堂反馈/);
  assert.match(markup, /智能错题/);
  assert.doesNotMatch(markup, /新建复习文档/);
});

test('workspace dashboard shows super owner platform overview', () => {
  const markup = renderDashboard('super_owner');

  assert.match(markup, /平台工作台/);
  assert.match(markup, /待处理事项/);
  assert.match(markup, /常用入口/);
  assert.match(markup, /机构列表/);
  assert.doesNotMatch(markup, /平台总览/);
  assert.doesNotMatch(markup, /机构运营概览/);
  assert.doesNotMatch(markup, /新建复习文档/);
});

test('workspace dashboard copy keeps direct task-oriented labels', () => {
  const memberMarkup = renderDashboard('member');
  const ownerMarkup = renderDashboard('owner');
  const superOwnerMarkup = renderDashboard('super_owner');

  assert.match(memberMarkup, /今天的记录和入口都在这里/);
  assert.match(ownerMarkup, /机构今天的记录和入口/);
  assert.match(superOwnerMarkup, /先看异常和积压，再进入具体页面处理/);
  assert.match(superOwnerMarkup, /处理账号审批/);
});

test('super owner platform cards are removed from the dashboard', () => {
  const markup = renderDashboard('super_owner');

  assert.doesNotMatch(markup, /查看机构工作区/);
  assert.doesNotMatch(markup, /进入审批/);
  assert.doesNotMatch(markup, /打开设置/);
});

test('app source routes the dashboard page through WorkspaceDashboard', () => {
  const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const pageContentSource = readFileSync(resolve(process.cwd(), 'src/features/navigation/WorkspacePageContent.tsx'), 'utf8');

  assert.match(appSource, /import \{ WorkspacePageContent \} from '\.\/features\/navigation\/WorkspacePageContent';/);
  assert.match(pageContentSource, /import \{ WorkspaceDashboard \} from '\.\.\/\.\.\/WorkspaceDashboard';/);
  assert.match(pageContentSource, /activeWorkspacePage === 'dashboard'[\s\S]*<WorkspaceDashboard[\s\S]*currentUser=\{currentUser\}[\s\S]*setActivePage=\{navigateWorkspacePage\}[\s\S]*styles=\{/);
  assert.match(pageContentSource, /canOpenAccounts=\{hasStaffAccess\(currentUser\.role\)\}/);
  assert.doesNotMatch(pageContentSource, /\{activeWorkspacePage === 'dashboard' && \(\s*<Dashboard/);
  assert.doesNotMatch(pageContentSource, /const Dashboard = \(/);
});

test('workspace dashboard uses styles passed by the shell instead of owning shared style imports', () => {
  const markup = renderDashboard('member');

  assert.match(markup, /workspace-page/);
  assert.match(markup, /workspace-card/);
  assert.doesNotMatch(markup, /workspacePrimaryButtonClass/);
});

test('organization management entries keep owner and admin routes inside their real access bounds', () => {
  assert.deepEqual(
    getOrganizationManagementEntries(true).map((entry) => entry.page),
    ['classes', 'accounts', 'class-feedback-generation', 'smartWrongQuestions'],
  );
  assert.deepEqual(
    getOrganizationManagementEntries(false).map((entry) => entry.page),
    ['classes', 'consultation', 'class-feedback-generation', 'smartWrongQuestions'],
  );
});
