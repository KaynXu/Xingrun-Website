import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { JSDOM } from 'jsdom';

import { WorkspaceDashboard, getOrganizationManagementEntries } from './WorkspaceDashboard';

type DashboardRole = 'super_owner' | 'owner' | 'admin' | 'member';

const workspaceSource = readFileSync(resolve(process.cwd(), 'src/WorkspaceDashboard.tsx'), 'utf8');
const defaultStyles = {
  pageClass: 'workspace-page',
  cardClass: 'workspace-card',
  primaryButtonClass: 'workspace-primary',
  secondaryButtonClass: 'workspace-secondary',
};

type GlobalKey = keyof typeof globalThis;

function setGlobalValue<T>(key: GlobalKey, value: T): () => void {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, key);
  Object.defineProperty(globalThis, key, {
    configurable: true,
    writable: true,
    value,
  });

  return () => {
    if (descriptor) {
      Object.defineProperty(globalThis, key, descriptor);
      return;
    }

    delete (globalThis as Record<string, unknown>)[key];
  };
}

function setupDomEnvironment(): {
  cleanup: () => void;
  container: HTMLDivElement;
  mouseEvent: typeof MouseEvent;
} {
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    url: 'http://localhost/',
  });
  const restoreCallbacks = [
    setGlobalValue('window', dom.window),
    setGlobalValue('document', dom.window.document),
    setGlobalValue('navigator', dom.window.navigator),
    setGlobalValue('HTMLElement', dom.window.HTMLElement),
    setGlobalValue('HTMLButtonElement', dom.window.HTMLButtonElement),
    setGlobalValue('Node', dom.window.Node),
    setGlobalValue('Event', dom.window.Event),
    setGlobalValue('MouseEvent', dom.window.MouseEvent),
    setGlobalValue('IS_REACT_ACT_ENVIRONMENT' as GlobalKey, true),
  ];
  const container = dom.window.document.createElement('div');
  dom.window.document.body.appendChild(container);

  return {
    container,
    mouseEvent: dom.window.MouseEvent,
    cleanup: () => {
      dom.window.document.body.removeChild(container);
      for (const restore of restoreCallbacks.reverse()) {
        restore();
      }
      dom.window.close();
    },
  };
}

function renderDashboard(role: DashboardRole): string {
  return renderToStaticMarkup(
    <WorkspaceDashboard
      currentUser={{
        display_name: '测试用户',
        role,
      }}
      setActivePage={() => undefined}
      styles={defaultStyles}
      canOpenAccounts={role === 'owner'}
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
  assert.match(markup, /咨询记录/);
  assert.match(markup, /课堂反馈/);
  assert.match(markup, /智能错题/);
  assert.doesNotMatch(markup, /账号审批/);
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
  assert.match(markup, /机构观察/);
  assert.match(markup, /账号审批/);
  assert.match(markup, /系统设置/);
  assert.doesNotMatch(markup, /机构运营概览/);
  assert.doesNotMatch(markup, /新建复习文档/);
});

test('workspace dashboard copy avoids conversational welcome and placeholder narration', () => {
  const memberMarkup = renderDashboard('member');
  const ownerMarkup = renderDashboard('owner');
  const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.doesNotMatch(memberMarkup, /欢迎回来/);
  assert.doesNotMatch(memberMarkup, /直接进入真实可用的教学动作/);
  assert.doesNotMatch(memberMarkup, /不伪造任务列表/);
  assert.doesNotMatch(ownerMarkup, /欢迎回来/);
  assert.doesNotMatch(ownerMarkup, /首页聚焦已经可用的机构管理入口/);
  assert.doesNotMatch(workspaceSource, /欢迎回来/);
  assert.doesNotMatch(workspaceSource, /不伪造任务列表/);
  assert.doesNotMatch(workspaceSource, /保留真实概览壳层/);
  assert.doesNotMatch(workspaceSource, /当前首页只保留真实入口说明/);
  assert.doesNotMatch(appSource, /AI 会整理成统一的复习资料与后续教学素材/);
  assert.doesNotMatch(appSource, /系统会先帮你整理字段/);
  assert.doesNotMatch(appSource, /让 AI 只做解析和预览/);
  assert.doesNotMatch(appSource, /还没有草稿。先粘贴原始文本，再点击“开始解析”。/);
});

test('super owner platform cards navigate to real platform and organization views', async () => {
  const domEnvironment = setupDomEnvironment();
  let root: Root | null = null;
  const navigatedPages: string[] = [];

  try {
    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        <WorkspaceDashboard
          currentUser={{
            display_name: '测试用户',
            role: 'super_owner',
          }}
          setActivePage={(page) => {
            navigatedPages.push(page);
          }}
          styles={defaultStyles}
          canOpenAccounts={true}
        />,
      );
    });

    const buttons = Array.from(domEnvironment.container.querySelectorAll('button'));
    const organizationButton = buttons.find((button) => button.textContent?.includes('机构观察'));
    const approvalButton = buttons.find((button) => button.textContent?.includes('账号审批'));
    const settingsButton = buttons.find((button) => button.textContent?.includes('系统设置'));

    assert.ok(organizationButton);
    assert.ok(approvalButton);
    assert.ok(settingsButton);

    await act(async () => {
      organizationButton?.dispatchEvent(new domEnvironment.mouseEvent('click', { bubbles: true }));
      approvalButton?.dispatchEvent(new domEnvironment.mouseEvent('click', { bubbles: true }));
      settingsButton?.dispatchEvent(new domEnvironment.mouseEvent('click', { bubbles: true }));
    });

    assert.deepEqual(navigatedPages, ['classes', 'accounts', 'settings']);
  } finally {
    if (root) {
      await act(async () => {
        root?.unmount();
      });
    }
    domEnvironment.cleanup();
  }
});

test('app source routes the dashboard page through WorkspaceDashboard', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /import \{ WorkspaceDashboard \} from '\.\/WorkspaceDashboard';/);
  assert.match(source, /\{activePage === 'dashboard' && \([\s\S]*<WorkspaceDashboard[\s\S]*currentUser=\{currentUser\}[\s\S]*setActivePage=\{setActivePage\}[\s\S]*styles=\{/);
  assert.match(source, /canOpenAccounts=\{hasOwnerAccess\(currentUser\.role\)\}/);
  assert.doesNotMatch(source, /\{activePage === 'dashboard' && \(\s*<Dashboard/);
  assert.doesNotMatch(source, /const Dashboard = \(/);
});

test('workspace dashboard source does not import shared styles from App directly', () => {
  assert.doesNotMatch(workspaceSource, /from '\.\/App'/);
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
