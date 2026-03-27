import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import * as AppModule from './App';

test('sidebar account sheet shows account info and logout actions', () => {
  const SidebarAccountSheet = (AppModule as { SidebarAccountSheet?: React.ComponentType<{
    currentUser: {
      id: number;
      username: string;
      display_name: string;
      role: 'owner' | 'member';
      status: string;
      organization_id: number;
      organization_name: string;
      created_at: string;
    };
    open: boolean;
    onClose: () => void;
    onLogout: () => void;
    onOpenSettings: () => void;
  }> }).SidebarAccountSheet;

  assert.equal(typeof SidebarAccountSheet, 'function');

  const markup = renderToStaticMarkup(
    <SidebarAccountSheet
      currentUser={{
        id: 1,
        username: 'Kayn',
        display_name: 'Kayn',
        role: 'owner',
        status: 'active',
        organization_id: 1,
        organization_name: '星润Starain',
        created_at: '2026-03-27 00:00:00',
      }}
      open={true}
      onClose={() => undefined}
      onLogout={() => undefined}
      onOpenSettings={() => undefined}
    />,
  );

  assert.match(markup, /查看账号信息/);
  assert.match(markup, /退出登录/);
  assert.match(markup, /星润Starain/);
});

test('sidebar account sheet includes dark theme surface classes', () => {
  const SidebarAccountSheet = (AppModule as { SidebarAccountSheet?: React.ComponentType<{
    currentUser: {
      id: number;
      username: string;
      display_name: string;
      role: 'owner' | 'member';
      status: string;
      organization_id: number;
      organization_name: string;
      created_at: string;
    };
    open: boolean;
    onClose: () => void;
    onLogout: () => void;
    onOpenSettings: () => void;
  }> }).SidebarAccountSheet;

  assert.equal(typeof SidebarAccountSheet, 'function');

  const markup = renderToStaticMarkup(
    <SidebarAccountSheet
      currentUser={{
        id: 1,
        username: 'Kayn',
        display_name: 'Kayn',
        role: 'owner',
        status: 'active',
        organization_id: 1,
        organization_name: '星润Starain',
        created_at: '2026-03-27 00:00:00',
      }}
      open={true}
      onClose={() => undefined}
      onLogout={() => undefined}
      onOpenSettings={() => undefined}
    />,
  );

  assert.match(markup, /dark:bg-slate-800\/88/);
  assert.match(markup, /dark:border-white\/10/);
  assert.match(markup, /dark:text-slate-100/);
  assert.match(markup, /dark:bg-slate-800\/72/);
});

test('workspace shell source applies dark classes to sidebar header and dashboard panels', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /workspaceCardClass\s*=\s*'[^']*dark:border-white\/10[^']*dark:bg-slate-800\/88/);
  assert.match(source, /workspaceSoftCardClass\s*=\s*'[^']*dark:border-white\/10[^']*dark:bg-slate-800\/72/);
  assert.match(source, /<div className="sticky top-0 flex h-screen w-72 flex-col[^\"]*dark:border-white\/10[^\"]*dark:bg-\[linear-gradient/);
  assert.match(source, /<header className="sticky top-0 z-10 flex h-20 items-center justify-between[^\"]*dark:border-white\/10[^\"]*dark:bg-\[#0f172a\]\/88/);
  assert.match(source, /<div className="rounded-\[2rem\] border border-sky-100[^\"]*dark:border-white\/10[^\"]*dark:bg-\[radial-gradient/);
});

test('workspace source applies dark classes to lesson library approval and settings pages', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /border border-rose-200 bg-rose-50 p-4 text-rose-600[^\n]*dark:border-rose-400\/20[^\n]*dark:bg-rose-500\/10[^\n]*dark:text-rose-300/);
  assert.match(source, /inline-flex gap-2 rounded-2xl border border-sky-100 bg-white\/85 p-1 shadow-sm[^\n]*dark:border-white\/10[^\n]*dark:bg-white\/5/);
  assert.match(source, /min-h-\[320px\][^\n]*border border-sky-100[^\n]*text-slate-700[^\n]*dark:border-white\/10[^\n]*dark:bg-slate-900\/70[^\n]*dark:text-slate-100/);
  assert.match(source, /<tr className="border-b border-sky-100\/80 text-xs uppercase tracking-wider text-slate-400[^\"]*dark:border-white\/10[^\"]*dark:text-slate-500"/);
  assert.match(source, /hover:bg-sky-50\/70[^\"]*dark:hover:bg-white\/5/);
  assert.match(source, /rounded-full bg-sky-50 px-2\.5 py-1 text-xs font-bold text-sky-700[^\"]*dark:bg-sky-900\/40[^\"]*dark:text-sky-300/);
  assert.match(source, /Owner<\/p>[\s\S]*账号审批[\s\S]*dark:text-white/);
  assert.match(source, /当前待审核注册申请/);
  assert.match(source, /mt-2 text-sm text-slate-500 dark:text-slate-400/);
  assert.match(source, /班级分配<\/h4>[\s\S]*dark:text-white/);
  assert.match(source, /text-sm font-semibold uppercase tracking-wider text-slate-500[^\"]*dark:text-slate-400/);
  assert.match(source, /当前账号<\/p>[\s\S]*dark:text-white/);
});
