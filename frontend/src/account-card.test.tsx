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
  const dashboardSource = readFileSync(resolve(process.cwd(), 'src/WorkspaceDashboard.tsx'), 'utf8');

  assert.match(source, /workspaceCardClass\s*=\s*'[^']*dark:border-white\/10[^']*dark:bg-slate-950\/78/);
  assert.match(source, /workspaceSoftCardClass\s*=\s*'[^']*dark:border-white\/10[^']*dark:bg-\[linear-gradient\(180deg,rgba\(15,23,42,0\.96\)_0%,rgba\(15,23,42,0\.9\)_100%\)\]/);
  assert.match(source, /mobile\s*\?\s*'h-full w-full overflow-y-auto overscroll-y-auto \[-webkit-overflow-scrolling:touch\][^\']*dark:shadow-\[18px_0_48px_rgba\(2,6,23,0\.48\)\]'/);
  assert.match(source, /:\s*'h-screen w-72 shadow-\[18px_0_48px_rgba\(47,128,237,0\.06\)\][^\']*dark:shadow-\[18px_0_48px_rgba\(2,6,23,0\.38\)\]'/);
  assert.match(source, /\?\s*'h-screen w-24 shadow-\[18px_0_48px_rgba\(47,128,237,0\.06\)\][^\']*dark:shadow-\[18px_0_48px_rgba\(2,6,23,0\.38\)\]'/);
  assert.match(source, /<header className="sticky top-0 z-10 flex h-20 items-center justify-between[^\"]*bg-white\/92[^\"]*sm:backdrop-blur-xl[^\"]*dark:border-white\/10[^\"]*dark:bg-\[#0f172a\]\/92[^\"]*dark:sm:bg-\[#0f172a\]\/88/);
  assert.match(dashboardSource, /rounded-\[2rem\] border border-sky-100[^\"]*dark:border-white\/10[^\"]*dark:bg-\[radial-gradient/);
  assert.match(source, /<div className="fixed inset-y-0 left-0 z-30 hidden lg:block">/);
  assert.match(source, /<main className=\{cn\('flex min-w-0 flex-1 flex-col', activeWorkspacePage === 'calendar' \? 'lg:pl-24' : 'lg:pl-72'\)\}>/);
});

test('sidebar account trigger stays anchored to the bottom edge of the visible sidebar shell', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /<div className=\{cn\('mt-auto border-t border-sky-100\/80 p-4 dark:border-white\/10', compact && !mobile && 'px-3'\)\}>/);
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
  assert.match(source, /<main className=\{cn\('flex min-w-0 flex-1 flex-col', activeWorkspacePage === 'calendar' \? 'lg:pl-24' : 'lg:pl-72'\)\}>/);
  assert.match(source, /<div className="relative min-h-\[100svh\] overflow-x-hidden bg-\[linear-gradient\(180deg,#f8fbff_0%,#eef6ff_100%\)\] text-slate-900 sm:min-h-screen dark:bg-\[linear-gradient\(180deg,#020617_0%,#0f172a_100%\)\] dark:text-slate-100">/);
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
  assert.match(source, /咨询详情/);
  assert.match(source, /跟进备注（内部）/);
  assert.doesNotMatch(source, /内部备注（可选）/);
});

test('consultation modal source supports quick parsing and structured source metadata confirmation', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /快速录入/);
  assert.match(source, /智能解析/);
  assert.match(source, /来源渠道备注/);
  assert.match(source, /consultationTeachers/);
  assert.match(source, /source_channel_note/);
});

test('consultation page source adds ai batch entry in the existing action area', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);

  assert.ok(consultationPageBlock);
  assert.match(consultationPageBlock[0], /AI 批量整理/);
  assert.match(consultationPageBlock[0], /onClick=\{openBatchModal\}/);
  assert.match(consultationPageBlock[0], /ConsultationBatchModal/);
});

test('consultation page source keeps consultation detail under teacher and follow-up notes in the consultation info block', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);

  assert.ok(consultationPageBlock);
  assert.match(consultationPageBlock[0], /const needDetail = record\.need_detail\?\.trim\(\);/);
  assert.match(consultationPageBlock[0], /const followUpNote = record\.follow_up_note\?\.trim\(\);/);
  assert.match(consultationPageBlock[0], /needDetail && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">咨询详情：\{needDetail\}<\/p>/);
  assert.match(consultationPageBlock[0], /<div className="min-h-\[72px\] space-y-1 text-sm text-slate-500 dark:text-slate-400">/);
  assert.match(consultationPageBlock[0], /followUpNote && <p>跟进：\{followUpNote\}<\/p>/);
  assert.doesNotMatch(consultationPageBlock[0], /备注：\{followUpNote\}/);
  assert.doesNotMatch(consultationPageBlock[0], /font-semibold whitespace-nowrap">备注<\/th>/);
  assert.doesNotMatch(consultationPageBlock[0], /overflow-x-auto/);
});

test('consultation page source keeps the desktop grade column on one line with tighter spacing before teacher details', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);

  assert.ok(consultationPageBlock);
  assert.match(consultationPageBlock[0], /<th className="pl-6 pr-3 py-4 font-semibold whitespace-nowrap w-24">年级<\/th>/);
  assert.match(consultationPageBlock[0], /<td className="pl-6 pr-3 py-4 align-top whitespace-nowrap text-sm text-slate-500 dark:text-slate-400">\{record\.grade \|\| '—'\}<\/td>/);
  assert.match(consultationPageBlock[0], /<th className="pl-3 pr-6 py-4 font-semibold whitespace-nowrap">咨询老师<\/th>/);
  assert.match(consultationPageBlock[0], /<td className="pl-3 pr-6 py-4 align-top">/);
});

test('consultation page source top-aligns desktop cells so the first text rows stay visually aligned', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);

  assert.ok(consultationPageBlock);
  assert.match(consultationPageBlock[0], /<td className="px-6 py-4 align-top font-mono text-sm text-slate-500 dark:text-slate-400">/);
  assert.match(consultationPageBlock[0], /<td className="px-6 py-4 align-top">/);
  assert.match(consultationPageBlock[0], /<td className="pl-6 pr-3 py-4 align-top whitespace-nowrap text-sm text-slate-500 dark:text-slate-400">/);
  assert.match(consultationPageBlock[0], /<td className="pl-3 pr-6 py-4 align-top">/);
  assert.match(consultationPageBlock[0], /<td className="px-6 py-4 align-top text-sm text-slate-500 dark:text-slate-400">/);
  assert.match(consultationPageBlock[0], /<td className="px-6 py-4 align-top text-right">/);
});

test('consultation batch modal source parses text, previews drafts, and reuses consultation write endpoints', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const batchModalBlock = source.match(/const ConsultationBatchModal = \([\s\S]*?\n};/);

  assert.ok(batchModalBlock);
  assert.match(batchModalBlock[0], /apiFetch<ConsultationBatchParseResponse>\('\/api\/consultations\/ai-parse'/);
  assert.match(batchModalBlock[0], /raw_text: rawText\.trim\(\)/);
  assert.match(batchModalBlock[0], /预览草稿/);
  assert.match(batchModalBlock[0], /确认导入/);
  assert.match(batchModalBlock[0], /只有文本里写了明确记录 ID（如 ID 182、记录182、#182）时，才会覆盖旧记录/);
  assert.match(batchModalBlock[0], /draft\.action === 'update' && draft\.target_id/);
  assert.match(batchModalBlock[0], /await apiFetch\(`\/api\/consultations\/\$\{draft\.target_id\}`/);
  assert.match(batchModalBlock[0], /await apiFetch\('\/api\/consultations'/);
});

test('consultation batch modal source keeps refresh failure separate after successful writes', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const batchModalBlock = source.match(/const ConsultationBatchModal = \([\s\S]*?\n};/);

  assert.ok(batchModalBlock);
  assert.match(batchModalBlock[0], /let importSucceeded = false;/);
  assert.match(batchModalBlock[0], /importSucceeded = true;/);
  assert.match(batchModalBlock[0], /try \{[\s\S]*await onImported\(\);[\s\S]*\} catch \(err\) \{/);
  assert.match(batchModalBlock[0], /导入已完成，但刷新咨询记录失败，请手动刷新列表确认结果。/);
});

test('consultation batch modal source blocks dismissal while parsing or importing', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const batchModalBlock = source.match(/const ConsultationBatchModal = \([\s\S]*?\n};/);

  assert.ok(batchModalBlock);
  assert.match(batchModalBlock[0], /const busy = parsing \|\| importing;/);
  assert.match(batchModalBlock[0], /onClick=\{\(e\) => e\.target === e\.currentTarget && !busy && onClose\(\)\}/);
  assert.match(batchModalBlock[0], /disabled=\{busy\}/);
});

test('consultation batch modal source previews key written fields before confirm', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const batchModalBlock = source.match(/const ConsultationBatchModal = \([\s\S]*?\n};/);

  assert.ok(batchModalBlock);
  assert.match(batchModalBlock[0], /const dateLabel = draft\.fields\.date\?\.trim\(\) \|\| '未填写咨询日期';/);
  assert.match(batchModalBlock[0], /const childLabel = draft\.fields\.child_name\?\.trim\(\) \|\| '未填写学生姓名';/);
  assert.match(batchModalBlock[0], /const sourceNoteLabel = draft\.fields\.source_channel_note\?\.trim\(\);/);
  assert.match(batchModalBlock[0], /const followUpNoteLabel = draft\.fields\.follow_up_note\?\.trim\(\);/);
  assert.match(batchModalBlock[0], /咨询日期 \/ 学生/);
  assert.match(batchModalBlock[0], /来源备注 \/ 跟进备注/);
});

test('consultation batch modal source lets users remove individual drafts before import', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const batchModalBlock = source.match(/const ConsultationBatchModal = \([\s\S]*?\n};/);

  assert.ok(batchModalBlock);
  assert.match(batchModalBlock[0], /const handleRemoveDraft = \(draftIndex: number\) => \{/);
  assert.match(batchModalBlock[0], /setDrafts\(\(current\) => current\.filter\(\(_draft, index\) => index !== draftIndex\)\);/);
  assert.match(batchModalBlock[0], /onClick=\{\(\) => handleRemoveDraft\(index\)\}/);
  assert.match(batchModalBlock[0], /移除这条草稿/);
});

test('consultation batch modal source attributes write failures to a specific draft and always clears importing', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const batchModalBlock = source.match(/const ConsultationBatchModal = \([\s\S]*?\n};/);

  assert.ok(batchModalBlock);
  assert.match(batchModalBlock[0], /for \(const \[index, draft\] of drafts\.entries\(\)\) \{/);
  assert.match(batchModalBlock[0], /const draftLabel = draft\.fields\.child_name\?\.trim\(\) \|\| \(draft\.action === 'update' && draft\.target_id \? `ID \$\{draft\.target_id\}` : `第 \$\{index \+ 1\} 条草稿`\);/);
  assert.match(batchModalBlock[0], /setError\(`\$\{draftLabel\}导入失败：\$\{message\}`\);/);
  assert.match(batchModalBlock[0], /setImporting\(true\);[\s\S]*try \{[\s\S]*for \(const \[index, draft\] of drafts\.entries\(\)\)[\s\S]*\} catch \(err\) \{[\s\S]*\} finally \{\s*setImporting\(false\);\s*\}/);
});

test('approval page source supports editing member display names inline', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const approvalBlock = source.match(/const ApprovalPage = \([\s\S]*?\n};\n\nconst SettingsPage/);

  assert.ok(approvalBlock);
  assert.match(approvalBlock[0], /编辑姓名/);
  assert.match(approvalBlock[0], /apiFetch\(`\/api\/admin\/users\/\$\{userId\}\/profile`, \{/);
});

test('consultation batch modal source keeps only remaining drafts after a partial import failure', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const batchModalBlock = source.match(/const ConsultationBatchModal = \([\s\S]*?\n};/);

  assert.ok(batchModalBlock);
  assert.match(batchModalBlock[0], /const remainingDrafts = \[\.\.\.drafts\];/);
  assert.match(batchModalBlock[0], /for \(const \[index, draft\] of drafts\.entries\(\)\) \{/);
  assert.match(batchModalBlock[0], /if \(draft\.action === 'update' && draft\.target_id\) \{\s*await apiFetch\(`\/api\/consultations\/\$\{draft\.target_id\}`,[\s\S]*?\}\s*else \{\s*await apiFetch\('\/api\/consultations',[\s\S]*?\}/);
  assert.match(batchModalBlock[0], /remainingDrafts\.shift\(\);\s*setImportedDrafts\(\(current\) => \[\.\.\.current, draft\]\);\s*setDrafts\(\[\.\.\.remainingDrafts\]\);/);
  assert.doesNotMatch(batchModalBlock[0], /continue;/);
  assert.match(batchModalBlock[0], /setError\(`\$\{draftLabel\}导入失败：\$\{message\}`\);\s*setDrafts\(\[\.\.\.remainingDrafts\]\);/);
});

test('consultation batch modal source preserves the current preview when parsing fails', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const batchModalBlock = source.match(/const ConsultationBatchModal = \([\s\S]*?\n};/);

  assert.ok(batchModalBlock);
  const parseCatchBlock = batchModalBlock[0].match(/const handleParse = async \(\) => \{[\s\S]*?\} catch \(err\) \{([\s\S]*?)\}\s*finally \{/);

  assert.ok(parseCatchBlock);
  assert.doesNotMatch(parseCatchBlock[1], /setDrafts\(\[\]\);/);
  assert.doesNotMatch(parseCatchBlock[1], /setWarnings\(\[\]\);/);
  assert.match(parseCatchBlock[1], /setError\(err instanceof Error \? err\.message : 'AI 批量解析失败'\);/);
});

test('consultation batch modal source keeps imported drafts visible while retries only include unsaved drafts', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const batchModalBlock = source.match(/const ConsultationBatchModal = \([\s\S]*?\n};/);

  assert.ok(batchModalBlock);
  assert.match(batchModalBlock[0], /const \[importedDrafts, setImportedDrafts\] = useState<ConsultationBatchDraftItem\[\]>\(\[\]\);/);
  assert.match(batchModalBlock[0], /setImportedDrafts\(\[\]\);/);
  assert.match(batchModalBlock[0], /remainingDrafts\.shift\(\);\s*setImportedDrafts\(\(current\) => \[\.\.\.current, draft\]\);\s*setDrafts\(\[\.\.\.remainingDrafts\]\);/);
  assert.match(batchModalBlock[0], /already-saved|已导入草稿|已保存草稿/);
  assert.match(batchModalBlock[0], /importedDrafts\.length > 0/);
  assert.match(batchModalBlock[0], /共 \{importedDrafts\.length\} 条/);
  assert.match(batchModalBlock[0], /共 \{drafts\.length\} 条/);
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
  const dashboardSource = readFileSync(resolve(process.cwd(), 'src/WorkspaceDashboard.tsx'), 'utf8');
  const indexCssSource = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');

  assert.match(appSource, /border border-rose-200 bg-rose-50 p-4 text-rose-600[^\n]*dark:border-rose-400\/20[^\n]*dark:bg-rose-500\/10[^\n]*dark:text-rose-300/);
  assert.match(appSource, /inline-flex gap-2 rounded-2xl border border-sky-100 bg-white\/85 p-1 shadow-sm[^\n]*dark:border-white\/10[^\n]*dark:bg-white\/5/);
  assert.match(appSource, /min-h-\[320px\][^\n]*border border-sky-100[^\n]*text-slate-700[^\n]*dark:border-white\/10[^\n]*dark:bg-slate-900\/70[^\n]*dark:text-slate-100/);
  assert.match(appSource, /<tr className="border-b border-sky-100\/80 text-xs uppercase tracking-wider text-slate-400[^\"]*dark:border-white\/10[^\"]*dark:text-slate-500"/);
  assert.match(appSource, /hover:bg-sky-50\/70[^\"]*dark:hover:bg-white\/5/);
  assert.match(dashboardSource, /rounded-\[2rem\] border border-sky-100[^"]*dark:border-white\/10[^"]*dark:bg-\[radial-gradient/);
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
  assert.match(calendarSource, /<select[\s\S]*className="[^"]*\[color-scheme:light\][^"]*dark:\[color-scheme:dark\][^"]*"/);
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

test('teacher alias mapping source links website members without guessing the external id', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const approvalBlock = source.match(/const ApprovalPage = \([\s\S]*?\n};\n\nconst SettingsPage/);

  assert.ok(approvalBlock);
  assert.match(approvalBlock[0], /const \[taLinkedUsername, setTaLinkedUsername\] = useState\(''\);/);
  assert.match(approvalBlock[0], /const teacherAliasMemberOptions = users\.filter/);
  assert.match(approvalBlock[0], /linked_username: taLinkedUsername\.trim\(\)/);
  assert.match(approvalBlock[0], />关联网站成员（可选）<\/label>/);
  assert.match(approvalBlock[0], /onChange=\{\(e\) => setTaLinkedUsername\(e\.target\.value\)\}/);
  assert.doesNotMatch(approvalBlock[0], /setTaFormUserId\(selectedUser\.username \|\| ''\);/);
  assert.doesNotMatch(approvalBlock[0], /setTaFormDisplayName\(selectedUser\.name\);/);
});

test('approval page source removes the start binding action from member cards', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const approvalBlock = source.match(/const ApprovalPage = \([\s\S]*?\n};\n\nconst SettingsPage/);

  assert.ok(approvalBlock);
  assert.doesNotMatch(approvalBlock[0], /开始绑定/);
  assert.doesNotMatch(approvalBlock[0], /onStartBinding\(user\.id\)/);
});

test('approval member cards link teacher class binding into class management', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const approvalBlock = source.match(/const ApprovalPage = \([\s\S]*?\n};\n\nconst SettingsPage/);
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(approvalBlock);
  assert.ok(classManagementBlock);
  assert.match(approvalBlock[0], /绑定班级/);
  assert.match(approvalBlock[0], /onOpenClassBinding\(\{ teacherUserId: user\.id, teacherName: user\.name \}\)/);
  assert.match(source, /const \[classBindingTarget, setClassBindingTarget\] = useState<ClassBindingTarget \| null>\(null\);/);
  assert.match(source, /setClassBindingTarget\(target\);\s*navigateWorkspacePage\('classes'\);/);
  assert.match(source, /<ApprovalPage currentUser=\{currentUser\} onOpenClassBinding=\{handleOpenClassBinding\} \/>/);
  assert.match(source, /<ClassManagementPage currentUser=\{currentUser\} classBindingTarget=\{classBindingTarget\} onClearClassBindingTarget=\{\(\) => setClassBindingTarget\(null\)\} \/>/);
  assert.match(classManagementBlock[0], /classBindingTarget\?\.teacherName/);
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
  assert.match(classManagementBlock[0], /const editingCurrentTeacherUserId = editingClass[\s\S]*teacherBindingByClassId\[editingClass\.id\] \?\? editingClass\.teacher_user_id \?\? null/);
  assert.match(classManagementBlock[0], /const editingCurrentTeacher = editingCurrentTeacherUserId == null \? undefined : users\.find\(\(user\) => user\.id === editingCurrentTeacherUserId\);/);
  assert.match(classManagementBlock[0], /const editingTeacherBindingSaving = editingClass \? Boolean\(teacherBindingSavingByClassId\[editingClass\.id\]\) : false;/);
  assert.match(classManagementBlock[0], /onChange=\{\(event\) => \{\s*const nextTeacherUserId = Number\(event\.target\.value\);/);
  assert.match(classManagementBlock[0], /void handleSelectTeacherForClass\(editingClass\.id, nextTeacherUserId\);/);
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
  assert.match(classManagementBlock[0], /disabled=\{editingTeacherBindingSaving \|\| classInteractionLocked \|\| editingFilteredUsers\.length === 0\}/);
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
  assert.match(source, /\['七年级三班', '七年级 3 班'\]/);
  assert.match(classManagementBlock[0], /placeholder="搜索老师"/);
  assert.match(classManagementBlock[0], /<select[\s\S]*value=\{newClassTeacherUserId == null \? '' : String\(newClassTeacherUserId\)\}/);
  assert.match(classManagementBlock[0], /<select[\s\S]*value=\{editingCurrentTeacherUserId == null \? '' : String\(editingCurrentTeacherUserId\)\}/);
  assert.match(classManagementBlock[0], /<option value="">请选择负责老师<\/option>/);
  assert.match(classManagementBlock[0], /当前负责老师：\{editingTeacherSummary\}/);
  assert.match(classManagementBlock[0], /newClassFilteredUsers\.map\(\(user\) => \(/);
  assert.match(classManagementBlock[0], /editingFilteredUsers\.map\(\(user\) => \(/);
  assert.match(classManagementBlock[0], /filteredClasses\.map\(\(item\) => \{[\s\S]*负责老师/);
  assert.doesNotMatch(classManagementBlock[0], /type="radio"/);
  assert.doesNotMatch(classManagementBlock[0], /班级老师分配/);
});

test('class management source opens both existing and new class editors in a modal instead of inline cards', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const newClassExpanded = expandedClassId === 'new';/);
  assert.match(classManagementBlock[0], /const editingClass = typeof expandedClassId === 'number' \? classes\.find\(\(item\) => item\.id === expandedClassId\) \?\? null : null;/);
  assert.match(classManagementBlock[0], /<AnimatePresence>/);
  assert.match(classManagementBlock[0], /className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto px-3 py-3 sm:items-center sm:px-4 sm:py-6"/);
  assert.match(classManagementBlock[0], /onClick=\{\(e\) => e\.target === e\.currentTarget && !classCardInteractionLocked && setExpandedClassId\(null\)\}/);
  assert.match(classManagementBlock[0], /编辑班级：/);
  assert.match(classManagementBlock[0], /关闭班级编辑窗口/);
  assert.doesNotMatch(classManagementBlock[0], /在弹窗里维护班级基础信息、负责老师和家长绑定邀请码。/);
  assert.doesNotMatch(classManagementBlock[0], /\{isExpanded && \(/);
});

test('class management source explains structured class naming without development examples', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /在这里统一管理 \{currentUser\.organization_name\} 的班级信息与负责老师安排。[\s\S]*班级命名规则/);
  assert.match(classManagementBlock[0], /按「学科 \+ 年级 \+ 班级」维护班级信息，例如：数学七年级三班、物理七年级二班。/);
  assert.match(classManagementBlock[0], /请分别填写学科、年级和班级名称，系统按「学科 \+ 年级 \+ 班级」理解班级，例如：数学七年级三班。/);
  assert.match(classManagementBlock[0], /placeholder="如：数学"/);
  assert.doesNotMatch(classManagementBlock[0], /数学 3\.0/);
  assert.equal((classManagementBlock[0].match(/班级命名规则/g) || []).length, 1);
});

test('class management source adds a side-by-side student editor card next to the teacher card', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(source, /deleteClassStudent,/);
  assert.match(classManagementBlock[0], /const \[studentsByClassId, setStudentsByClassId\] = useState<Record<number, Array<\{ id: number; name: string \}>>>\(\{\}\);/);
  assert.match(classManagementBlock[0], /const editingStudents = editingClass \? \(studentsByClassId\[editingClass\.id\] \|\| \[\]\) : \[\];/);
  assert.match(classManagementBlock[0], /const editingStudentsLoading = editingClass \? Boolean\(studentsLoadingByClassId\[editingClass\.id\]\) : false;/);
  assert.match(classManagementBlock[0], /const editingStudentDraftName = editingClass \? \(studentDraftNameByClassId\[editingClass\.id\] \|\| ''\) : '';/);
  assert.match(classManagementBlock[0], /className="grid gap-4 lg:grid-cols-2 lg:items-start"/);
  assert.match(classManagementBlock[0], /<h4 className="text-lg font-semibold text-slate-900 dark:text-white">家长绑定邀请码<\/h4>/);
  assert.match(classManagementBlock[0], /<h4 className="text-xl font-semibold text-slate-900 dark:text-white">负责老师<\/h4>/);
  assert.match(classManagementBlock[0], /<h4 className="text-xl font-semibold text-slate-900 dark:text-white">编辑学生<\/h4>/);
  assert.match(classManagementBlock[0], /placeholder="输入学生姓名"/);
  assert.match(classManagementBlock[0], /删除学生/);
});

test('class management source removes click-to-edit helper copy from class cards', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.doesNotMatch(classManagementBlock[0], /点击后弹窗编辑/);
});

test('class management source keeps delete and save buttons inside the teacher card footer', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /<div className=\{`\$\{workspaceCardClass\} space-y-5 p-5`\}>[\s\S]*删除当前班级[\s\S]*保存班级/);
  assert.doesNotMatch(classManagementBlock[0], /<div className="flex flex-col gap-3 border-t border-sky-100\/80 pt-5 sm:flex-row sm:items-center sm:justify-between dark:border-white\/10">[\s\S]*删除当前班级[\s\S]*保存班级/);
});

test('login source includes password reset and first-login class claim entry points', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classClaimBlock = source.match(/const ClassClaimPage = \([\s\S]*?const LoginModal = \(/);

  assert.match(source, /type PublicAuthModal = 'login' \| 'apply-organization' \| 'join-organization' \| 'password-reset'/);
  assert.match(source, /\/api\/password-reset/);
  assert.match(source, /recovery_phone/);
  assert.match(source, /const ClassClaimPage = \(/);
  assert.match(source, /\/api\/me\/unbound-classes/);
  assert.match(source, /\/api\/me\/claim-classes/);
  assert.ok(classClaimBlock);
  assert.match(classClaimBlock[0], /const \[selectedGradeFilter, setSelectedGradeFilter\] = useState<string>\('全部'\)/);
  assert.match(classClaimBlock[0], /const \[selectedSubjectFilter, setSelectedSubjectFilter\] = useState<string>\('全部学科'\)/);
  assert.match(classClaimBlock[0], /const filteredClasses = classes\.filter\(\(item\) => \{/);
  assert.match(classClaimBlock[0], /if \(selectedSubjectFilter !== '全部学科' && item\.subject !== selectedSubjectFilter\) \{\s*return false;\s*\}/);
});
