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

  assert.match(markup, /dark:bg-slate-950\/78/);
  assert.match(markup, /dark:border-white\/10/);
  assert.match(markup, /dark:text-slate-100/);
  assert.match(markup, /dark:bg-\[linear-gradient\(180deg,rgba\(15,23,42,0\.96\)_0%,rgba\(15,23,42,0\.9\)_100%\)\]/);
});

test('workspace shell source applies dark classes to sidebar header and dashboard panels', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /workspaceCardClass\s*=\s*'[^']*dark:border-white\/10[^']*dark:bg-slate-950\/78/);
  assert.match(source, /workspaceSoftCardClass\s*=\s*'[^']*dark:border-white\/10[^']*dark:bg-\[linear-gradient\(180deg,rgba\(15,23,42,0\.96\)_0%,rgba\(15,23,42,0\.9\)_100%\)\]/);
  assert.match(source, /mobile\s*\?\s*'h-full w-full overflow-y-auto overscroll-contain[^\']*dark:shadow-\[18px_0_48px_rgba\(2,6,23,0\.48\)\]'/);
  assert.match(source, /:\s*'h-screen w-72 shadow-\[18px_0_48px_rgba\(47,128,237,0\.06\)\][^\']*dark:shadow-\[18px_0_48px_rgba\(2,6,23,0\.38\)\]'/);
  assert.match(source, /<header className="sticky top-0 z-10 flex h-20 items-center justify-between[^\"]*dark:border-white\/10[^\"]*dark:bg-\[#0f172a\]\/88/);
  assert.match(source, /<div className="rounded-\[2rem\] border border-sky-100[^\"]*dark:border-white\/10[^\"]*dark:bg-\[radial-gradient/);
  assert.match(source, /<div className="fixed inset-y-0 left-0 z-30 hidden lg:block">/);
  assert.match(source, /<main className="flex min-w-0 flex-1 flex-col lg:pl-72">/);
});

test('sidebar account trigger stays anchored to the bottom edge of the visible sidebar shell', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /<div className="mt-auto border-t border-sky-100\/80 p-4 dark:border-white\/10">/);
});

test('sidebar account sheet renders above workspace content without relying on a fullscreen blur layer', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /import \{ createPortal \} from 'react-dom';/);
  assert.match(source, /<div className="fixed inset-0 z-\[70\]"/);
  assert.doesNotMatch(source, /backdrop-blur-\[4px\]/);
});

test('desktop workspace uses page-level scrolling instead of an inner scroll container beside the sidebar', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.doesNotMatch(source, /<div className="flex-1 overflow-y-auto">/);
  assert.match(source, /<main className="flex min-w-0 flex-1 flex-col lg:pl-72">/);
  assert.match(source, /<div className="relative min-h-screen overflow-x-hidden bg-\[linear-gradient\(180deg,#f8fbff_0%,#eef6ff_100%\)\] text-slate-900 dark:bg-\[linear-gradient\(180deg,#020617_0%,#0f172a_100%\)\] dark:text-slate-100">/);
});

test('consultation detail cards use darker dark-mode surfaces instead of translucent white overlays', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /rounded-2xl border border-sky-100 bg-white\/80 p-4 dark:border-white\/10 dark:bg-slate-950\/70/);
  assert.match(source, /rounded-2xl border border-sky-100 bg-white\/80 p-3 dark:border-white\/10 dark:bg-slate-950\/70/);
  assert.match(source, /workspaceSoftCardClass\} p-5/);
});

test('consultation modal source keeps the create and edit form concise', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.doesNotMatch(source, /placeholder="老师 ID"/);
  assert.doesNotMatch(source, />截图字段</);
  assert.doesNotMatch(source, />老师ID</);
  assert.match(source, /内部备注（可选）/);
});

test('consultation modal source supports quick parsing and structured source metadata confirmation', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /快速录入/);
  assert.match(source, /智能解析/);
  assert.match(source, /来源渠道备注/);
  assert.match(source, /consultationTeachers/);
  assert.match(source, /source_channel_note/);
});

test('quick consultation parser extracts normalized teacher and source metadata', () => {
  const parseConsultationQuickEntry = (AppModule as {
    parseConsultationQuickEntry?: (
      input: string,
      teacherOptions: Array<{ teacher_id: string; display_name: string; aliases: string[] }>,
    ) => Record<string, string>;
  }).parseConsultationQuickEntry;

  assert.equal(typeof parseConsultationQuickEntry, 'function');

  const parsed = parseConsultationQuickEntry!(
    '张妈妈，五年级数学，张裕空转介绍，雷文浩接待，想补基础',
    [{ teacher_id: 'KeChongDianDeAShiPiLing', display_name: '雷文浩', aliases: ['雷老师'] }],
  );

  assert.equal(parsed.parent_wechat_name, '张妈妈');
  assert.equal(parsed.grade, '五年级');
  assert.equal(parsed.consultation_subject, '数学');
  assert.equal(parsed.source_channel, '转介绍');
  assert.equal(parsed.source_channel_note, '张裕空');
  assert.equal(parsed.receiving_teacher, '雷文浩');
  assert.equal(parsed.teacher_id, 'KeChongDianDeAShiPiLing');
  assert.match(parsed.need_detail, /补基础/);
});

test('workspace source applies dark classes to lesson library approval settings and calendar pages', () => {
  const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const calendarSource = readFileSync(resolve(process.cwd(), 'src/CourseCalendarPage.tsx'), 'utf8');
  const indexCssSource = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');

  assert.match(appSource, /border border-rose-200 bg-rose-50 p-4 text-rose-600[^\n]*dark:border-rose-400\/20[^\n]*dark:bg-rose-500\/10[^\n]*dark:text-rose-300/);
  assert.match(appSource, /inline-flex gap-2 rounded-2xl border border-sky-100 bg-white\/85 p-1 shadow-sm[^\n]*dark:border-white\/10[^\n]*dark:bg-white\/5/);
  assert.match(appSource, /min-h-\[320px\][^\n]*border border-sky-100[^\n]*text-slate-700[^\n]*dark:border-white\/10[^\n]*dark:bg-slate-900\/70[^\n]*dark:text-slate-100/);
  assert.match(appSource, /<tr className="border-b border-sky-100\/80 text-xs uppercase tracking-wider text-slate-400[^\"]*dark:border-white\/10[^\"]*dark:text-slate-500"/);
  assert.match(appSource, /hover:bg-sky-50\/70[^\"]*dark:hover:bg-white\/5/);
  assert.match(appSource, /Owner<\/p>[\s\S]*账号审批[\s\S]*dark:text-white/);
  assert.match(appSource, /当前待审核注册申请/);
  assert.match(appSource, /mt-2 text-sm text-slate-500 dark:text-slate-400/);
  assert.match(appSource, /班级分配<\/h4>[\s\S]*dark:text-white/);
  assert.match(appSource, /text-sm font-semibold uppercase tracking-wider text-slate-500[^\"]*dark:text-slate-400/);
  assert.match(appSource, /当前账号<\/p>[\s\S]*dark:text-white/);
  assert.match(appSource, /calendar: '课程日历'/);
  assert.doesNotMatch(appSource, /题库浏览/);
  assert.match(appSource, /bg-cyan-200\/35 blur-\[130px\][^\n]*dark:bg-cyan-500\/10/);
  assert.match(appSource, /bg-blue-200\/30 blur-\[150px\][^\n]*dark:bg-blue-500\/10/);
  assert.match(appSource, /bg-white\/75 blur-\[120px\][^\n]*dark:bg-slate-900\/40/);
  assert.match(calendarSource, /<select className="[^"]*\[color-scheme:light\][^"]*dark:\[color-scheme:dark\][^"]*"/);
  assert.match(calendarSource, /dark:bg-\[radial-gradient\(circle_at_top_left,rgba\(34,211,238,0\.12\),transparent_24%\),radial-gradient\(circle_at_85%_15%,rgba\(59,130,246,0\.14\),transparent_22%\),linear-gradient\(180deg,#020617_0%,#0f172a_100%\)\]/);
  assert.match(calendarSource, /dark:border-white\/10 dark:bg-slate-900\/78/);
  assert.match(calendarSource, /dark:bg-\[linear-gradient\(180deg,rgba\(15,23,42,0\.96\)_0%,rgba\(15,23,42,0\.82\)_100%\)\]/);
  assert.match(indexCssSource, /html\.dark\s*\{[\s\S]*color-scheme:\s*dark;/);
  assert.match(indexCssSource, /html\.dark ::-webkit-scrollbar-thumb\s*\{[\s\S]*background:\s*#334155;/);
  assert.match(indexCssSource, /html\.dark ::-webkit-scrollbar-thumb:hover\s*\{[\s\S]*background:\s*#475569;/);
});

test('workspace source splits approval and class assignment responsibilities across separate pages', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const approvalBlock = source.match(/const ApprovalPage = \([\s\S]*?\n};\n\nconst SettingsPage/);
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.match(source, /账号审批/);
  assert.ok(approvalBlock);
  assert.match(approvalBlock[0], /成员权限/);
  assert.match(approvalBlock[0], /apiFetch<UserItem\[]>\('\/api\/admin\/users'\)/);
  assert.match(approvalBlock[0], /`\/api\/admin\/users\/\$\{userId\}\/role`/);
  assert.doesNotMatch(approvalBlock[0], /成员班级分配/);
  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /成员班级分配/);
  assert.match(classManagementBlock[0], /apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(classManagementBlock[0], /apiFetch<UserItem\[]>\('\/api\/admin\/users'\)/);
  assert.match(classManagementBlock[0], /apiFetch<\{ class_ids: number\[\] \}>\(`\/api\/admin\/users\/\$\{userId\}\/classes`\)/);
  assert.doesNotMatch(classManagementBlock[0], /升为管理员/);
});
