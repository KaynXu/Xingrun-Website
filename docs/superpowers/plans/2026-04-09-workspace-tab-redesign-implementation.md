# Workspace Tab Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current review-centric dashboard with a role-aware workspace homepage for `super_owner`, `owner/admin`, and `member/teacher`, while keeping the existing workspace shell intact.

**Architecture:** Keep the sidebar, header, and route shell in `frontend/src/App.tsx`, but replace the inline `Dashboard` body with a dedicated `WorkspaceDashboard` entry component that dispatches to three role-specific homepage components. Reuse existing frontend style helpers and existing backend endpoints only; where live data is missing, render real navigation entry cards instead of fake task or notification states.

**Tech Stack:** React 19, TypeScript, Vite, `tsx --test`, server-side markup tests with `react-dom/server`, existing workspace shell helpers from `frontend/src/App.tsx`.

---

### Task 1: Isolate The Medium Change In Its Own Worktree

**Files:**
- Modify: `handoff.md`
- Test: `frontend/src/account-card.test.tsx`
- Test: `frontend/src/course-calendar.test.tsx`
- Test: `frontend/src/class-feedback-generation.test.tsx`
- Test: `frontend/src/review-generation-async.test.tsx`
- Test: `frontend/src/app-storage-guard.test.tsx`

- [ ] **Step 1: Create the isolated feature worktree from `develop`**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
git worktree add .worktrees/workspace-tab-redesign -b feature/workspace-tab-redesign develop
```

- [ ] **Step 2: Install frontend dependencies inside the new worktree**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign/frontend
npm install
```

- [ ] **Step 3: Run the focused workspace-shell baseline tests before editing code**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign/frontend
npx tsx --test src/account-card.test.tsx src/course-calendar.test.tsx src/class-feedback-generation.test.tsx src/review-generation-async.test.tsx src/app-storage-guard.test.tsx
```

Expected: `pass 60` and `fail 0` on the clean worktree baseline.

- [ ] **Step 4: Record the isolated worktree path in `handoff.md` before implementation starts**

```md
## 工作台重写 implementation 已切到隔离 worktree（2026-04-09）

### 已完成
- 已创建隔离分支：`feature/workspace-tab-redesign`
- 已创建隔离 worktree：`/Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign`
- 已完成工作台相关前端基线测试：`pass 60 / fail 0`

### 下一步方向
- 按 implementation plan 从角色分发红测开始推进。
```


### Task 2: Replace The Inline Dashboard With A Role Dispatcher

**Files:**
- Create: `frontend/src/WorkspaceDashboard.tsx`
- Create: `frontend/src/workspace-dashboard.test.tsx`
- Modify: `frontend/src/App.tsx:45,68-109,1588-1695,8412-8416`

- [ ] **Step 1: Write the failing role-dispatch test**

```tsx
import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { WorkspaceDashboard } from './WorkspaceDashboard';

const baseUser = {
  id: 1,
  username: 'demo',
  display_name: '演示用户',
  role: 'member' as const,
  status: 'active',
  organization_id: 1,
  organization_name: '星润',
  created_at: '2026-04-09 10:00:00',
};

test('workspace dashboard dispatches role-specific homepage content', () => {
  const teacherMarkup = renderToStaticMarkup(
    <WorkspaceDashboard currentUser={baseUser} setActivePage={() => undefined} />,
  );
  const adminMarkup = renderToStaticMarkup(
    <WorkspaceDashboard currentUser={{ ...baseUser, role: 'admin' }} setActivePage={() => undefined} />,
  );
  const superOwnerMarkup = renderToStaticMarkup(
    <WorkspaceDashboard currentUser={{ ...baseUser, role: 'super_owner' }} setActivePage={() => undefined} />,
  );

  assert.match(teacherMarkup, /快速开始/);
  assert.doesNotMatch(teacherMarkup, /今日待办/);
  assert.match(adminMarkup, /机构运营概览/);
  assert.match(superOwnerMarkup, /平台总览/);
});
```

- [ ] **Step 2: Run the test to verify it fails because the new dashboard entry does not exist yet**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign/frontend
npx tsx --test src/workspace-dashboard.test.tsx
```

Expected: FAIL with module-not-found or export-not-found for `./WorkspaceDashboard`.

- [ ] **Step 3: Add the minimal dispatcher component and wire `App.tsx` to use it**

```tsx
// frontend/src/WorkspaceDashboard.tsx
import React from 'react';
import {
  workspaceCardClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
} from './App';

type DashboardRole = 'super_owner' | 'owner' | 'admin' | 'member';
type DashboardPage =
  | 'dashboard'
  | 'review-generation'
  | 'class-feedback-generation'
  | 'consultation'
  | 'calendar'
  | 'smartWrongQuestions'
  | 'classes'
  | 'accounts'
  | 'credit'
  | 'settings';

interface DashboardUser {
  display_name: string;
  role: DashboardRole;
  organization_name: string;
}

interface WorkspaceDashboardProps {
  currentUser: DashboardUser;
  setActivePage: (page: DashboardPage) => void;
}

function TeacherHome({ setActivePage }: Pick<WorkspaceDashboardProps, 'setActivePage'>) {
  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <section className={`${workspaceCardClass} p-6`}>
        <h3 className="text-2xl font-bold text-slate-900 dark:text-white">快速开始</h3>
        <div className="mt-4 flex flex-wrap gap-3">
          <button className={workspacePrimaryButtonClass} onClick={() => setActivePage('review-generation')}>复习生成</button>
          <button className={workspaceSecondaryButtonClass} onClick={() => setActivePage('class-feedback-generation')}>课堂反馈</button>
        </div>
      </section>
    </div>
  );
}

function OrganizationHome() {
  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <section className={`${workspaceCardClass} p-6`}>
        <h3 className="text-2xl font-bold text-slate-900 dark:text-white">机构运营概览</h3>
      </section>
    </div>
  );
}

function SuperOwnerHome() {
  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <section className={`${workspaceCardClass} p-6`}>
        <h3 className="text-2xl font-bold text-slate-900 dark:text-white">平台总览</h3>
      </section>
    </div>
  );
}

export function WorkspaceDashboard(props: WorkspaceDashboardProps) {
  if (props.currentUser.role === 'super_owner') {
    return <SuperOwnerHome />;
  }
  if (props.currentUser.role === 'owner' || props.currentUser.role === 'admin') {
    return <OrganizationHome />;
  }
  return <TeacherHome setActivePage={props.setActivePage} />;
}
```

```tsx
// frontend/src/App.tsx
import { WorkspaceDashboard } from './WorkspaceDashboard';

// Replace the old dashboard render branch.
{activePage === 'dashboard' && (
  <WorkspaceDashboard
    currentUser={currentUser}
    setActivePage={setActivePage}
  />
)}
```

- [ ] **Step 4: Run the new role-dispatch test and the existing shell tests**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign/frontend
npx tsx --test src/workspace-dashboard.test.tsx src/account-card.test.tsx src/app-storage-guard.test.tsx
```

Expected: PASS for the new dispatcher test and no regression in shell-level tests.

- [ ] **Step 5: Commit the dispatcher extraction**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign
git add frontend/src/App.tsx frontend/src/WorkspaceDashboard.tsx frontend/src/workspace-dashboard.test.tsx handoff.md
git commit -m "feat: extract role-aware workspace dashboard entry"
```


### Task 3: Implement The Member And Teacher Workbench

**Files:**
- Modify: `frontend/src/WorkspaceDashboard.tsx`
- Modify: `frontend/src/workspace-dashboard.test.tsx`
- Test: `frontend/src/review-generation-async.test.tsx`

- [ ] **Step 1: Extend the test to require real quick actions, personal overview, and recent-work copy for `member`**

```tsx
test('member workspace prioritizes quick actions and personal work context', () => {
  const markup = renderToStaticMarkup(
    <WorkspaceDashboard currentUser={baseUser} setActivePage={() => undefined} />,
  );

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
```

- [ ] **Step 2: Run the test and verify it fails on the still-minimal teacher home**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign/frontend
npx tsx --test src/workspace-dashboard.test.tsx
```

Expected: FAIL because `我的教学概览` and `最近工作` are not rendered yet.

- [ ] **Step 3: Flesh out the teacher homepage using existing actions and real summary sections only**

```tsx
function TeacherHome({ currentUser, setActivePage }: WorkspaceDashboardProps) {
  return (
    <div className={`${workspacePageClass} space-y-8`}>
      <section className={`${workspaceCardClass} p-6`}>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Workbench</p>
        <h3 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 dark:text-white">今天从这里开始</h3>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600 dark:text-slate-300">
          不做伪待办，直接进入真实可用的教学动作与最近工作内容。
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <button className={`${workspaceCardClass} p-5 text-left`} onClick={() => setActivePage('review-generation')}>复习生成</button>
        <button className={`${workspaceCardClass} p-5 text-left`} onClick={() => setActivePage('class-feedback-generation')}>课堂反馈</button>
        <button className={`${workspaceCardClass} p-5 text-left`} onClick={() => setActivePage('calendar')}>课程日历</button>
        <button className={`${workspaceCardClass} p-5 text-left`} onClick={() => setActivePage('smartWrongQuestions')}>智能错题</button>
      </section>

      <section className={`${workspaceCardClass} p-6`}>
        <h4 className="text-lg font-semibold text-slate-900 dark:text-white">我的教学概览</h4>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">显示我负责的班级、学生和最近教学产出。</p>
      </section>

      <section className={`${workspaceCardClass} p-6`}>
        <h4 className="text-lg font-semibold text-slate-900 dark:text-white">最近工作</h4>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Re-run the focused member-home test and the existing async review test**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign/frontend
npx tsx --test src/workspace-dashboard.test.tsx src/review-generation-async.test.tsx
```

Expected: PASS with no reintroduction of fake task-oriented copy.

- [ ] **Step 5: Commit the member-teacher workbench**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign
git add frontend/src/WorkspaceDashboard.tsx frontend/src/workspace-dashboard.test.tsx
git commit -m "feat: add member workspace workbench"
```


### Task 4: Implement The Owner And Admin Organization Overview

**Files:**
- Modify: `frontend/src/WorkspaceDashboard.tsx`
- Modify: `frontend/src/workspace-dashboard.test.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Add the failing owner/admin assertions before implementing the richer overview**

```tsx
test('owner and admin workspace centers organization operations instead of review creation', () => {
  const markup = renderToStaticMarkup(
    <WorkspaceDashboard currentUser={{ ...baseUser, role: 'owner' }} setActivePage={() => undefined} />,
  );

  const adminMarkup = renderToStaticMarkup(
    <WorkspaceDashboard currentUser={{ ...baseUser, role: 'admin' }} setActivePage={() => undefined} />,
  );

  assert.match(markup, /机构运营概览/);
  assert.match(markup, /班级管理/);
  assert.match(markup, /账号审批/);
  assert.match(markup, /课堂反馈/);
  assert.match(markup, /智能错题/);
  assert.doesNotMatch(markup, /新建复习文档/);
  assert.match(adminMarkup, /机构运营概览/);
  assert.match(adminMarkup, /班级管理/);
  assert.match(adminMarkup, /咨询记录/);
  assert.match(adminMarkup, /课堂反馈/);
  assert.match(adminMarkup, /智能错题/);
  assert.doesNotMatch(adminMarkup, /账号审批/);
  assert.doesNotMatch(adminMarkup, /新建复习文档/);
});
```

- [ ] **Step 2: Run the test and verify it fails because the organization home is still only a heading**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign/frontend
npx tsx --test src/workspace-dashboard.test.tsx
```

Expected: FAIL on missing management entry cards.

- [ ] **Step 3: Implement the organization overview layout with real management entry points**

```tsx
function OrganizationHome({ currentUser, setActivePage, canOpenAccounts }: WorkspaceDashboardProps) {
  return (
    <div className={`${workspacePageClass} space-y-8`}>
      <section className={`${workspaceCardClass} p-6`}>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Organization</p>
        <h3 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 dark:text-white">机构运营概览</h3>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600 dark:text-slate-300">
          优先查看机构运行状态、内容产出与管理入口，而不是继续把首页做成复习资料启动页。
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className={`${workspaceCardClass} p-5`}><p className="text-sm text-slate-500 dark:text-slate-400">班级数</p></div>
        <div className={`${workspaceCardClass} p-5`}><p className="text-sm text-slate-500 dark:text-slate-400">内容产出</p></div>
        <div className={`${workspaceCardClass} p-5`}><p className="text-sm text-slate-500 dark:text-slate-400">最近反馈</p></div>
        <div className={`${workspaceCardClass} p-5`}><p className="text-sm text-slate-500 dark:text-slate-400">机构状态</p></div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <button className={`${workspaceCardClass} p-5 text-left`} onClick={() => setActivePage('classes')}>班级管理</button>
        {canOpenAccounts ? (
          <button className={`${workspaceCardClass} p-5 text-left`} onClick={() => setActivePage('accounts')}>账号审批</button>
        ) : (
          <button className={`${workspaceCardClass} p-5 text-left`} onClick={() => setActivePage('consultation')}>咨询记录</button>
        )}
        <button className={`${workspaceCardClass} p-5 text-left`} onClick={() => setActivePage('class-feedback-generation')}>课堂反馈</button>
        <button className={`${workspaceCardClass} p-5 text-left`} onClick={() => setActivePage('smartWrongQuestions')}>智能错题</button>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Run the organization-home test plus the broad workspace shell suite**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign/frontend
npx tsx --test src/workspace-dashboard.test.tsx src/account-card.test.tsx src/course-calendar.test.tsx
```

Expected: PASS for organization overview assertions and no regression in shared workspace shell tests.

- [ ] **Step 5: Commit the organization overview work**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign
git add frontend/src/WorkspaceDashboard.tsx frontend/src/workspace-dashboard.test.tsx
git commit -m "feat: add organization workspace overview"
```


### Task 5: Implement The Super Owner Platform Overview And Final App Cleanup

**Files:**
- Modify: `frontend/src/WorkspaceDashboard.tsx`
- Modify: `frontend/src/workspace-dashboard.test.tsx`
- Modify: `frontend/src/App.tsx:1588-1695,8412-8416`

- [ ] **Step 1: Add the failing super-owner assertions before finishing the platform view**

```tsx
test('super owner workspace presents a platform-wide overview instead of institution workflow cards', () => {
  const markup = renderToStaticMarkup(
    <WorkspaceDashboard currentUser={{ ...baseUser, role: 'super_owner' }} setActivePage={() => undefined} />,
  );

  assert.match(markup, /平台总览/);
  assert.match(markup, /机构观察/);
  assert.match(markup, /账号审批/);
  assert.match(markup, /系统设置/);
  assert.doesNotMatch(markup, /新建复习文档/);
});
```

- [ ] **Step 2: Run the test and confirm the missing platform modules fail first**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign/frontend
npx tsx --test src/workspace-dashboard.test.tsx
```

Expected: FAIL because the super-owner home only renders the title.

- [ ] **Step 3: Implement the platform overview and remove the old inline dashboard body from `App.tsx`**

```tsx
function SuperOwnerHome({ setActivePage }: Pick<WorkspaceDashboardProps, 'setActivePage'>) {
  return (
    <div className={`${workspacePageClass} space-y-8`}>
      <section className={`${workspaceCardClass} p-6`}>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Platform</p>
        <h3 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 dark:text-white">平台总览</h3>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className={`${workspaceCardClass} p-5`}><p className="text-sm text-slate-500 dark:text-slate-400">机构总数</p></div>
        <div className={`${workspaceCardClass} p-5`}><p className="text-sm text-slate-500 dark:text-slate-400">活跃账号</p></div>
        <div className={`${workspaceCardClass} p-5`}><p className="text-sm text-slate-500 dark:text-slate-400">内容生成量</p></div>
        <div className={`${workspaceCardClass} p-5`}><p className="text-sm text-slate-500 dark:text-slate-400">近 7 天趋势</p></div>
      </section>

      <section className={`${workspaceCardClass} p-6`}>
        <h4 className="text-lg font-semibold text-slate-900 dark:text-white">机构观察</h4>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <button className={`${workspaceCardClass} p-5 text-left`} onClick={() => setActivePage('accounts')}>账号审批</button>
        <button className={`${workspaceCardClass} p-5 text-left`} onClick={() => setActivePage('classes')}>机构查看</button>
        <button className={`${workspaceCardClass} p-5 text-left`} onClick={() => setActivePage('settings')}>系统设置</button>
      </section>
    </div>
  );
}

// frontend/src/App.tsx
// Remove the old inline Dashboard component body entirely after WorkspaceDashboard is stable.
```

- [ ] **Step 4: Run the full targeted regression set for the workspace rewrite**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign/frontend
npx tsx --test src/workspace-dashboard.test.tsx src/account-card.test.tsx src/course-calendar.test.tsx src/class-feedback-generation.test.tsx src/review-generation-async.test.tsx src/app-storage-guard.test.tsx
```

Expected: PASS with the new workspace dashboard coverage added and existing workspace-shell behavior preserved.

- [ ] **Step 5: Commit the completed dashboard rewrite**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign
git add frontend/src/App.tsx frontend/src/WorkspaceDashboard.tsx frontend/src/workspace-dashboard.test.tsx
git commit -m "feat: rewrite workspace dashboard by role"
```


### Task 6: Final Verification, Documentation, And Handoff

**Files:**
- Modify: `handoff.md`
- Test: `frontend/src/workspace-dashboard.test.tsx`
- Test: `frontend/src/account-card.test.tsx`
- Test: `frontend/src/course-calendar.test.tsx`
- Test: `frontend/src/class-feedback-generation.test.tsx`
- Test: `frontend/src/review-generation-async.test.tsx`
- Test: `frontend/src/app-storage-guard.test.tsx`

- [ ] **Step 1: Run the final proof command from the isolated worktree**

Run:

```bash
tmp_script="/tmp/xingrun-workspace-tab-redesign-proof-20260409.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign/frontend
npx tsx --test src/workspace-dashboard.test.tsx src/account-card.test.tsx src/course-calendar.test.tsx src/class-feedback-generation.test.tsx src/review-generation-async.test.tsx src/app-storage-guard.test.tsx
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected: all targeted workspace tests pass with `fail 0`.

- [ ] **Step 2: Update `handoff.md` with the branch, worktree, proof command, and remaining follow-up items**

```md
## 工作台角色驾驶舱重写已完成（2026-04-09）

### 已完成
- 已在隔离分支 `feature/workspace-tab-redesign` 中重写工作台 tab。
- 已以角色驾驶舱方案替换旧 review-centric dashboard。
- 已完成三套首页：`super_owner`、`owner/admin`、`member/teacher`。
- `App.tsx` 不再内联旧 dashboard 主体。

### proof
- 临时脚本：`/tmp/xingrun-workspace-tab-redesign-proof-20260409.sh`
- 完整输出结论：`tests <N>` / `pass <N>` / `fail 0`

### 剩余问题
- 若后续需要更细的运营指标，优先新增真实后端数据后再补首页卡片。

### 下一步方向
- 进入代码审查与分支收尾。
```

- [ ] **Step 3: Commit the handoff update**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/workspace-tab-redesign
git add handoff.md
git commit -m "docs: record workspace dashboard rewrite handoff"
```