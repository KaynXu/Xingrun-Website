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
      role: 'super_owner' | 'owner' | 'member';
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
        role: 'super_owner',
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
      role: 'super_owner' | 'owner' | 'member';
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
        role: 'super_owner',
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
  assert.match(source, /mobile\s*\?\s*'h-full w-full overflow-y-auto overscroll-y-auto \[-webkit-overflow-scrolling:touch\][^\']*dark:shadow-\[18px_0_48px_rgba\(2,6,23,0\.48\)\]'/);
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

test('assignment rollback helper restores previous ids when optimistic state is still current', () => {
  const resolveAssignmentRollbackClassIds = (AppModule as {
    resolveAssignmentRollbackClassIds?: (
      currentClassIds: number[],
      previousClassIds: number[],
      failedNextClassIds: number[],
    ) => number[];
  }).resolveAssignmentRollbackClassIds;

  assert.equal(typeof resolveAssignmentRollbackClassIds, 'function');
  assert.deepEqual(resolveAssignmentRollbackClassIds!([2, 4], [2], [2, 4]), [2]);
});

test('assignment rollback helper preserves fresher ids after state changed again', () => {
  const resolveAssignmentRollbackClassIds = (AppModule as {
    resolveAssignmentRollbackClassIds?: (
      currentClassIds: number[],
      previousClassIds: number[],
      failedNextClassIds: number[],
    ) => number[];
  }).resolveAssignmentRollbackClassIds;

  assert.equal(typeof resolveAssignmentRollbackClassIds, 'function');
  assert.deepEqual(resolveAssignmentRollbackClassIds!([1, 3], [2], [2, 4]), [1, 3]);
});

test('teacher binding map rollback helper restores previous id when optimistic binding is still current', () => {
  const resolveTeacherBindingRollbackTeacherBindings = (AppModule as {
    resolveTeacherBindingRollbackTeacherBindings?: (
      currentTeacherBindingByClassId: Record<number, number | null>,
      classId: number,
      previousTeacherUserId: number | null,
      failedNextTeacherUserId: number,
    ) => Record<number, number | null>;
  }).resolveTeacherBindingRollbackTeacherBindings;

  assert.equal(typeof resolveTeacherBindingRollbackTeacherBindings, 'function');
  assert.deepEqual(
    resolveTeacherBindingRollbackTeacherBindings!({ 7: 12, 9: 18 }, 7, null, 12),
    { 7: null, 9: 18 },
  );
});

test('teacher binding map rollback helper preserves fresher binding state after later updates', () => {
  const resolveTeacherBindingRollbackTeacherBindings = (AppModule as {
    resolveTeacherBindingRollbackTeacherBindings?: (
      currentTeacherBindingByClassId: Record<number, number | null>,
      classId: number,
      previousTeacherUserId: number | null,
      failedNextTeacherUserId: number,
    ) => Record<number, number | null>;
  }).resolveTeacherBindingRollbackTeacherBindings;

  assert.equal(typeof resolveTeacherBindingRollbackTeacherBindings, 'function');
  assert.deepEqual(
    resolveTeacherBindingRollbackTeacherBindings!({ 7: 18, 9: 18 }, 7, null, 12),
    { 7: 18, 9: 18 },
  );
});

test('teacher binding rollback helper restores exact previous teacher fields', () => {
  const resolveTeacherBindingRollbackClassItem = (AppModule as {
    resolveTeacherBindingRollbackClassItem?: (
      currentItem: {
        id: number;
        name: string;
        subject: string;
        grade: string;
        teacher_name?: string;
        teacher_user_id?: number | null;
      },
      failedNextTeacherUserId: number,
      previousTeacherUserId: number | null,
      previousTeacherName: string,
    ) => {
      id: number;
      name: string;
      subject: string;
      grade: string;
      teacher_name?: string;
      teacher_user_id?: number | null;
    };
  }).resolveTeacherBindingRollbackClassItem;

  assert.equal(typeof resolveTeacherBindingRollbackClassItem, 'function');
  assert.deepEqual(
    resolveTeacherBindingRollbackClassItem!(
      { id: 7, name: '六年级 2 班', subject: '数学', grade: '六年级', teacher_name: '新老师', teacher_user_id: 12 },
      12,
      null,
      '',
    ),
    { id: 7, name: '六年级 2 班', subject: '数学', grade: '六年级', teacher_name: '', teacher_user_id: null },
  );
});

test('teacher binding rollback helper preserves fresher teacher state after later updates', () => {
  const resolveTeacherBindingRollbackClassItem = (AppModule as {
    resolveTeacherBindingRollbackClassItem?: (
      currentItem: {
        id: number;
        name: string;
        subject: string;
        grade: string;
        teacher_name?: string;
        teacher_user_id?: number | null;
      },
      failedNextTeacherUserId: number,
      previousTeacherUserId: number | null,
      previousTeacherName: string,
    ) => {
      id: number;
      name: string;
      subject: string;
      grade: string;
      teacher_name?: string;
      teacher_user_id?: number | null;
    };
  }).resolveTeacherBindingRollbackClassItem;

  assert.equal(typeof resolveTeacherBindingRollbackClassItem, 'function');
  assert.deepEqual(
    resolveTeacherBindingRollbackClassItem!(
      { id: 7, name: '六年级 2 班', subject: '数学', grade: '六年级', teacher_name: '更新后的老师', teacher_user_id: 18 },
      12,
      null,
      '',
    ),
    { id: 7, name: '六年级 2 班', subject: '数学', grade: '六年级', teacher_name: '更新后的老师', teacher_user_id: 18 },
  );
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
  assert.match(appSource, /负责老师<\/h4>[\s\S]*dark:text-white/);
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
  assert.match(classManagementBlock[0], /负责老师/);
  assert.doesNotMatch(classManagementBlock[0], /班级老师分配/);
  assert.doesNotMatch(classManagementBlock[0], /成员班级分配/);
  assert.match(classManagementBlock[0], /apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(classManagementBlock[0], /apiFetch<UserItem\[]>\('\/api\/admin\/users'\)/);
  assert.doesNotMatch(classManagementBlock[0], /升为管理员/);
});

test('approval page source loads and renders member teaching binding summaries', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const approvalBlock = source.match(/const ApprovalPage = \([\s\S]*?\n};\n\nconst SettingsPage/);

  assert.ok(approvalBlock);
  assert.match(approvalBlock[0], /apiFetch<\{ items: MemberBindingSummary\[] \}>\('\/api\/admin\/member-binding-summary'\)/);
  assert.match(approvalBlock[0], /教学绑定/);
  assert.match(approvalBlock[0], /小程序老师/);
  assert.match(approvalBlock[0], /负责班级/);
  assert.match(approvalBlock[0], /映射状态/);
  assert.match(approvalBlock[0], /教学绑定摘要加载失败/);
  assert.match(approvalBlock[0], /bindingSummaryByUserId\[user\.id\]/);
  assert.match(approvalBlock[0], /responsible_classes/);
  assert.match(approvalBlock[0], /mini_teacher_bound/);
});

test('class management source shows current teacher summary and removes multi-teacher count copy', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(source, /teacher_user_id\?: number \| null;/);
  assert.match(classManagementBlock[0], /当前负责老师：/);
  assert.match(classManagementBlock[0], /teacherSummary = currentTeacher\?\.name \|\| item\.teacher_name \|\| '未分配老师';/);
  assert.doesNotMatch(classManagementBlock[0], /已分配 \{selectedTeacherIds\.length\} 位老师/);
  assert.doesNotMatch(classManagementBlock[0], /selectedTeacherNames/);
});

test('class management source uses one 负责老师 concept instead of separate 班级老师分配 wording', () => {
  const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /<h4\b[^>]*>\s*负责老师\s*<\/h4>/);
  assert.doesNotMatch(classManagementBlock[0], /班级老师分配/);
  assert.doesNotMatch(classManagementBlock[0], /<span\b[^>]*>\s*负责老师\s*<\/span>\s*<div\b[^>]*>\s*\{teacherSummary\}\s*<\/div>/);
});

test('class management source requires selecting one teacher when creating a class', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /if \(classId === 'new' && !selectedTeacherUserId\) \{\s*setFormError\('请先选择负责老师账号'\);\s*return;\s*\}/);
  assert.match(classManagementBlock[0], /const selectedTeacher = typeof selectedTeacherUserId === 'number' \? users\.find\(\(user\) => user\.id === selectedTeacherUserId\) : undefined;/);
  assert.match(classManagementBlock[0], /teacher_name: selectedTeacher\?\.name \|\| '',/);
  assert.match(classManagementBlock[0], /await apiFetch\(`\/api\/classes\/\$\{created\.id\}\/teacher`, \{/);
});

test('class management source keeps teacher binding selection scoped per class card', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const currentTeacherUserId = teacherBindingByClassId\[item\.id\] \?\? item\.teacher_user_id \?\? null;/);
  assert.match(classManagementBlock[0], /const currentTeacher = currentTeacherUserId == null \? undefined : users\.find\(\(user\) => user\.id === currentTeacherUserId\);/);
  assert.match(classManagementBlock[0], /const teacherBindingSaving = Boolean\(teacherBindingSavingByClassId\[item\.id\]\);/);
  assert.match(classManagementBlock[0], /onChange=\{\(\) => handleSelectTeacherForClass\(item\.id, user\.id\)\}/);
  assert.match(classManagementBlock[0], /const previousTeacherName = previousClass\?\.teacher_name \|\| '';/);
  assert.match(source, /export function resolveTeacherBindingRollbackTeacherBindings\(/);
  assert.match(classManagementBlock[0], /loadPageRequestVersionRef\.current \+= 1;/);
  assert.match(classManagementBlock[0], /setTeacherBindingByClassId\(\(current\) => resolveTeacherBindingRollbackTeacherBindings\(current, classId, previousTeacherUserId, teacherUserId\)\);/);
  assert.match(classManagementBlock[0], /resolveTeacherBindingRollbackClassItem\(item, teacherUserId, previousTeacherUserId, previousTeacherName\)/);
  assert.match(classManagementBlock[0], /const refreshResult = await loadPage\(classId, \{ preserveStateOnError: true \}\);/);
  assert.match(classManagementBlock[0], /let createdClassId: number \| null = null;/);
  assert.match(classManagementBlock[0], /班级已创建，但负责老师绑定失败/);
});

test('class management source separates mutation success from best-effort refresh reconciliation', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(source, /type LoadPageResult =/);
  assert.match(classManagementBlock[0], /const loadPage = useCallback\(async \(preferredExpandedClassId\?: number \| 'new' \| null, options\?: \{ preserveStateOnError\?: boolean \}\): Promise<LoadPageResult> => \{/);
  assert.match(classManagementBlock[0], /const preserveStateOnError = options\?\.preserveStateOnError \?\? false;/);
  assert.match(classManagementBlock[0], /return \{ status: 'stale' \};/);
  assert.match(classManagementBlock[0], /return \{ status: 'success' \};/);
  assert.match(classManagementBlock[0], /return \{ status: 'refresh-error', error \};/);
  assert.doesNotMatch(classManagementBlock[0], /if \(requestVersion !== loadPageRequestVersionRef\.current\) \{\s*return;\s*\}/);
  assert.match(classManagementBlock[0], /if \(!preserveStateOnError\) \{[\s\S]*setClasses\(\[\]\);[\s\S]*setUsers\(\[\]\);[\s\S]*setTeacherBindingByClassId\(\{\}\);/);
  assert.match(classManagementBlock[0], /await apiFetch\(`\/api\/classes\/\$\{classId\}\/teacher`, \{[\s\S]*const refreshResult = await loadPage\(classId, \{ preserveStateOnError: true \}\);[\s\S]*if \(refreshResult\.status === 'refresh-error'\) \{[\s\S]*老师绑定已保存，但列表刷新失败/);
  assert.match(classManagementBlock[0], /let teacherBindingSucceeded = false;/);
  assert.match(classManagementBlock[0], /teacherBindingSucceeded = true;/);
  assert.match(classManagementBlock[0], /if \(classId === 'new' && createdClassId != null && !teacherBindingSucceeded\) \{/);
  assert.match(classManagementBlock[0], /const refreshResult = await loadPage\(created\.id, \{ preserveStateOnError: true \}\);[\s\S]*if \(refreshResult\.status === 'refresh-error'\) \{[\s\S]*班级和负责老师已保存，但列表刷新失败/);
});

test('class management source disables conflicting controls while async class or assignment work is in flight', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const classInteractionLocked = saving \|\| deleting;/);
  assert.match(classManagementBlock[0], /const hasTeacherBindingSavingRows = Object\.values\(teacherBindingSavingByClassId\)\.some\(Boolean\);/);
  assert.match(classManagementBlock[0], /const classCardInteractionLocked = classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(classManagementBlock[0], /const pageRefreshLocked = classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(classManagementBlock[0], /const assignmentRefreshLocked = classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(classManagementBlock[0], /if \(classCardInteractionLocked\) \{\s*return;\s*\}[\s\S]*setExpandedClassId\(/);
  assert.match(classManagementBlock[0], /disabled=\{pageRefreshLocked\}[\s\S]*刷新列表/);
  assert.match(classManagementBlock[0], /disabled=\{classCardInteractionLocked\}[\s\S]*新建班级/);
  assert.match(classManagementBlock[0], /onClick=\{\(\) => handleToggleExpandedClass\('new'\)\}[\s\S]*disabled=\{classCardInteractionLocked\}/);
  assert.match(classManagementBlock[0], /onClick=\{\(\) => handleToggleExpandedClass\(item\.id\)\}[\s\S]*disabled=\{classCardInteractionLocked\}/);
  assert.doesNotMatch(classManagementBlock[0], /展开管理/);
  assert.doesNotMatch(classManagementBlock[0], /收起管理/);
  assert.match(classManagementBlock[0], /disabled=\{classCardInteractionLocked\}[\s\S]*创建班级/);
  assert.match(classManagementBlock[0], /disabled=\{classCardInteractionLocked\}[\s\S]*删除当前班级/);
  assert.match(classManagementBlock[0], /disabled=\{classCardInteractionLocked\}[\s\S]*保存班级/);
  assert.match(classManagementBlock[0], /disabled=\{assignmentRefreshLocked\}[\s\S]*刷新分配/);
  assert.match(classManagementBlock[0], /disabled=\{teacherBindingSaving \|\| classInteractionLocked\}/);
});

test('class management source removes teacher-email UI and the standalone bottom assignment section', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.doesNotMatch(source, /interface ClassFormValues \{[\s\S]*teacher_email: string;/);
  assert.doesNotMatch(classManagementBlock[0], /teacher_email:\s*form\.teacher_email\.trim\(\)/);
  assert.doesNotMatch(classManagementBlock[0], /老师邮箱/);
  assert.doesNotMatch(classManagementBlock[0], /未填写邮箱/);
  assert.doesNotMatch(classManagementBlock[0], /<section className=\{`\$\{workspaceCardClass\} space-y-5 p-6`\}>[\s\S]*班级分配/);
  assert.match(classManagementBlock[0], /负责老师/);
  assert.doesNotMatch(classManagementBlock[0], /班级老师分配/);
});

test('class management source embeds teacher assignment inside each class card and normalizes common class names', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(source, /const normalizeClassNameInput = \(value: string\): string =>/);
  assert.match(source, /\['6年级2班', '六年级 2 班'\]/);
  assert.match(classManagementBlock[0], /placeholder="搜索老师"/);
  assert.match(classManagementBlock[0], /当前负责老师：\{teacherSummary\}/);
  assert.match(classManagementBlock[0], /filteredClasses\.map\(\(item\) => \{[\s\S]*负责老师/);
  assert.doesNotMatch(classManagementBlock[0], /班级老师分配/);
});
