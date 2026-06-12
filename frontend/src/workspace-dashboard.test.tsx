import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import React from 'react';
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

  assert.match(markup, /快速开始/);
  assert.match(markup, /复习生成/);
  assert.match(markup, /课堂反馈/);
  assert.match(markup, /课程日历/);
  assert.match(markup, /智能错题/);
  assert.match(markup, /我的教学概览/);
  assert.match(markup, /最近工作/);
  assert.doesNotMatch(markup, /今日待办/);
  assert.doesNotMatch(markup, /通知中心/);
});

test('workspace dashboard shows admin operations overview', () => {
  const markup = renderDashboard('admin');

  assert.match(markup, /机构运营概览/);
  assert.match(markup, /班级管理/);
  assert.match(markup, /账号审批/);
  assert.match(markup, /课堂反馈/);
  assert.match(markup, /智能错题/);
  assert.doesNotMatch(markup, /咨询记录/);
  assert.doesNotMatch(markup, /新建复习文档/);
});

test('workspace dashboard shows owner operations overview', () => {
  const markup = renderDashboard('owner');

  assert.match(markup, /机构运营概览/);
  assert.match(markup, /班级管理/);
  assert.match(markup, /账号审批/);
  assert.match(markup, /课堂反馈/);
  assert.match(markup, /智能错题/);
  assert.doesNotMatch(markup, /新建复习文档/);
});

test('workspace dashboard shows super owner platform overview', () => {
  const markup = renderDashboard('super_owner');

  assert.match(markup, /平台总览/);
  assert.doesNotMatch(markup, /查看机构工作区/);
  assert.doesNotMatch(markup, /进入审批/);
  assert.doesNotMatch(markup, /打开设置/);
  assert.doesNotMatch(markup, /机构运营概览/);
  assert.doesNotMatch(markup, /新建复习文档/);
});

test('workspace dashboard copy keeps AI labels and material-generation copy', () => {
  const memberMarkup = renderDashboard('member');
  const ownerMarkup = renderDashboard('owner');
  const superOwnerMarkup = renderDashboard('super_owner');

  assert.match(memberMarkup, /AI 复习生成/);
  assert.match(ownerMarkup, /AI 教学入口/);
  assert.match(superOwnerMarkup, /AI 平台/);
});

test('super owner platform cards are removed from the dashboard', () => {
  const markup = renderDashboard('super_owner');

  assert.doesNotMatch(markup, /查看机构工作区/);
  assert.doesNotMatch(markup, /进入审批/);
  assert.doesNotMatch(markup, /打开设置/);
});

test('app source routes the dashboard page through WorkspaceDashboard', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /import \{ WorkspaceDashboard \} from '\.\/WorkspaceDashboard';/);
  assert.match(source, /\{activeWorkspacePage === 'dashboard' && \([\s\S]*<WorkspaceDashboard[\s\S]*currentUser=\{currentUser\}[\s\S]*setActivePage=\{navigateWorkspacePage\}[\s\S]*styles=\{/);
  assert.match(source, /canOpenAccounts=\{hasStaffAccess\(currentUser\.role\)\}/);
  assert.doesNotMatch(source, /\{activeWorkspacePage === 'dashboard' && \(\s*<Dashboard/);
  assert.doesNotMatch(source, /const Dashboard = \(/);
});

test('workspace dashboard uses styles passed by the shell instead of owning shared style imports', () => {
  const markup = renderDashboard('member');

  assert.match(markup, /workspace-page/);
  assert.match(markup, /workspace-card/);
  assert.match(markup, /workspace-primary/);
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
