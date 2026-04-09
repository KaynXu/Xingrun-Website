import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { WorkspaceDashboard } from './WorkspaceDashboard';

type DashboardRole = 'super_owner' | 'owner' | 'admin' | 'member';

const workspaceSource = readFileSync(resolve(process.cwd(), 'src/WorkspaceDashboard.tsx'), 'utf8');
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
    />,
  );
}

test('workspace dashboard shows member quick start instead of today todo', () => {
  const markup = renderDashboard('member');

  assert.match(markup, /快速开始/);
  assert.doesNotMatch(markup, /今日待办/);
});

test('workspace dashboard shows admin operations overview', () => {
  const markup = renderDashboard('admin');

  assert.match(markup, /机构运营概览/);
});

test('workspace dashboard shows owner operations overview', () => {
  const markup = renderDashboard('owner');

  assert.match(markup, /机构运营概览/);
});

test('workspace dashboard shows super owner platform overview', () => {
  const markup = renderDashboard('super_owner');

  assert.match(markup, /平台总览/);
});

test('app source routes the dashboard page through WorkspaceDashboard', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /import \{ WorkspaceDashboard \} from '\.\/WorkspaceDashboard';/);
  assert.match(source, /\{activePage === 'dashboard' && \([\s\S]*<WorkspaceDashboard[\s\S]*currentUser=\{currentUser\}[\s\S]*setActivePage=\{setActivePage\}[\s\S]*styles=\{/);
  assert.doesNotMatch(source, /\{activePage === 'dashboard' && \(\s*<Dashboard/);
  assert.doesNotMatch(source, /const Dashboard = \(/);
});

test('workspace dashboard source does not import shared styles from App directly', () => {
  assert.doesNotMatch(workspaceSource, /from '\.\/App'/);
});