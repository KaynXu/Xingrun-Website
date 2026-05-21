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
  assert.match(source, /<main className=\{cn\('flex min-w-0 flex-1 flex-col', activeWorkspacePage === 'calendar' \|\| activeWorkspacePage === 'consultation' \? 'lg:pl-24' : 'lg:pl-72'\)\}>/);
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
  assert.match(source, /<main className=\{cn\('flex min-w-0 flex-1 flex-col', activeWorkspacePage === 'calendar' \|\| activeWorkspacePage === 'consultation' \? 'lg:pl-24' : 'lg:pl-72'\)\}>/);
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

test('consultation page V2.0 exposes owner-only meeting workbench instead of refresh', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);
  const appBlock = source.match(/export default function App\(\) \{[\s\S]*?\n}/);

  assert.ok(consultationPageBlock);
  assert.ok(appBlock);
  assert.match(source, /const consultationMeetingVersion = 'V2\.0';/);
  assert.match(consultationPageBlock[0], /const canOpenMeetingWorkbench = hasOwnerAccess\(currentUser\.role\);/);
  assert.match(consultationPageBlock[0], /openConsultationMeetingWorkbench/);
  assert.match(consultationPageBlock[0], /面对面模式/);
  assert.match(consultationPageBlock[0], /!canOpenMeetingWorkbench && \(/);
  assert.match(source, /consultationMeeting'\) === '1'/);
  assert.match(source, /<ConsultationMeetingWorkbench currentUser=\{currentUser\}/);
});

test('consultation modal keeps save beside close and supports keyboard save shortcuts', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);

  assert.ok(modalBlock);
  assert.match(source, /Save,/);
  assert.match(modalBlock[0], /const saveButtonLabel = submitting \? '保存中\.\.\.' : mode === 'create' \? '创建记录' : '保存修改';/);
  assert.match(modalBlock[0], /const handleSaveShortcut = \(event: KeyboardEvent\) => \{/);
  assert.match(modalBlock[0], /\(event\.metaKey \|\| event\.altKey\) && event\.key\.toLowerCase\(\) === 's'/);
  assert.match(modalBlock[0], /event\.preventDefault\(\);/);
  assert.match(modalBlock[0], /formScrollRef\.current\?\.requestSubmit\(\);/);
  assert.match(modalBlock[0], /title="Command\+S \/ Alt\+S"/);
  assert.match(modalBlock[0], /<Save size=\{15\} \/>/);
  assert.match(modalBlock[0], /aria-label="关闭咨询记录窗口"[\s\S]*<form ref=\{formScrollRef\}/);
  assert.doesNotMatch(modalBlock[0], /<button type="submit" className=\{`\$\{workspacePrimaryButtonClass\} w-full sm:w-auto`\}/);
});

test('consultation meeting workbench keeps local drafts until final save', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const workbenchBlock = source.match(/const ConsultationMeetingWorkbench = \([\s\S]*?\n};/);

  assert.ok(workbenchBlock);
  assert.match(workbenchBlock[0], /const \[draftsById, setDraftsById\] = useState<Record<number, ConsultationFormValues>>\(\{\}\);/);
  assert.match(workbenchBlock[0], /const \[processedIds, setProcessedIds\] = useState<Set<number>>\(\(\) => new Set\(\)\);/);
  assert.match(workbenchBlock[0], /setDraftsById\(\(current\) => \(\{ \.\.\.current, \[selectedRecord\.id\]: values \}\)\);/);
  assert.match(workbenchBlock[0], /setProcessedIds\(\(current\) => new Set\(current\)\.add\(selectedRecord\.id\)\);/);
  assert.match(workbenchBlock[0], /const pendingRecords = /);
  assert.match(workbenchBlock[0], /const processedActiveRecords = /);
  assert.match(workbenchBlock[0], /const processedEndedRecords = /);
  assert.match(workbenchBlock[0], /const \[workbenchTab, setWorkbenchTab\] = useState<'pending' \| 'processed'>\('pending'\);/);
  assert.match(workbenchBlock[0], /const \[processedWorkbenchTab, setProcessedWorkbenchTab\] = useState<'active' \| 'ended'>\('active'\);/);
  assert.match(workbenchBlock[0], /setWorkbenchTab\('processed'\);/);
  assert.match(workbenchBlock[0], /setProcessedWorkbenchTab\(isConsultationEnded\(values\.flow_stage\) \|\| isConsultationResultStage\(values\.flow_stage\) \? 'ended' : 'active'\);/);
  assert.match(workbenchBlock[0], /workbenchTab === 'pending'/);
  assert.match(workbenchBlock[0], /processedWorkbenchTab === 'active'/);
  assert.match(workbenchBlock[0], /onClick=\{\(\) => setWorkbenchTab\('pending'\)\}/);
  assert.match(workbenchBlock[0], /onClick=\{\(\) => setWorkbenchTab\('processed'\)\}/);
  assert.match(workbenchBlock[0], /onClick=\{\(\) => setProcessedWorkbenchTab\('active'\)\}/);
  assert.match(workbenchBlock[0], /onClick=\{\(\) => setProcessedWorkbenchTab\('ended'\)\}/);
  assert.match(workbenchBlock[0], /待处理/);
  assert.match(workbenchBlock[0], /待咨询/);
  assert.match(workbenchBlock[0], /已结束/);
});

test('consultation meeting workbench final save and close guard are explicit', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const workbenchBlock = source.match(/const ConsultationMeetingWorkbench = \([\s\S]*?\n};/);

  assert.ok(workbenchBlock);
  assert.match(workbenchBlock[0], /beforeunload/);
  assert.match(workbenchBlock[0], /还有未最终保存的咨询修改，是否关闭？/);
  assert.match(workbenchBlock[0], /const handleFinalSave = async \(\) => \{/);
  assert.match(workbenchBlock[0], /await apiFetch\(`\/api\/consultations\/\$\{id\}`/);
  assert.match(workbenchBlock[0], /最终保存/);
  assert.match(workbenchBlock[0], /按教师查看/);
  assert.match(workbenchBlock[0], /xr_consultation_meeting_saved_at/);
  assert.match(workbenchBlock[0], /setDraftsById\(\{\}\);/);
  assert.match(workbenchBlock[0], /setProcessedIds\(new Set\(\)\);/);
  assert.match(source, /const handleMeetingWorkbenchSave = \(event: StorageEvent\) => \{/);
  assert.match(source, /event\.key === 'xr_consultation_meeting_saved_at'/);
});

test('consultation source renders approved v6 flow stage bars', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  assert.match(source, /consultationFlowStages/);
  assert.match(source, /ConsultationFlowBar/);
  assert.match(source, /ConsultationStatusLamp/);
  assert.match(source, /ConsultationResultCapsule/);
  assert.match(source, /客服微信✅/);
  assert.match(source, /教师微信✅/);
  assert.match(source, /沟通ing/);
  assert.match(source, /☀️ 成功进班/);
  assert.match(source, /😢 试听未成/);
  assert.match(source, /full/);
  assert.match(source, /已加小客服微信/);
  assert.match(source, /咨询结束/);
});

test('consultation modal source includes stage-specific test and trial fields', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);
  assert.ok(modalBlock);
  assert.match(modalBlock[0], /是否测试/);
  assert.match(modalBlock[0], /测试情况图片/);
  assert.match(modalBlock[0], /是否试听/);
  assert.match(modalBlock[0], /试听时间段/);
  assert.match(modalBlock[0], /其他：手动输入/);
  assert.match(modalBlock[0], /试听教师/);
  assert.match(modalBlock[0], /试听反馈/);
  assert.match(modalBlock[0], /成功进班必须选择或填写班级/);
});

test('consultation view mode uses a read-only report layout instead of disabled edit fields', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);

  assert.ok(modalBlock);
  assert.match(source, /const ConsultationReadOnlyReport = \(/);
  assert.match(modalBlock[0], /readOnly \? \(/);
  assert.match(modalBlock[0], /<ConsultationReadOnlyReport/);
  assert.match(source, /沟通ing：情况说明/);
  assert.match(source, /测试情况图片/);
  assert.match(source, /录入时间/);
  assert.match(source, /最后更新/);
});

test('consultation list and workbench cards expand long detail previews based on rendered overflow', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const expandableBlock = source.match(/const ConsultationCardExpandableText = \([\s\S]*?\n};/);
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);
  const workbenchBlock = source.match(/const ConsultationMeetingWorkbench = \([\s\S]*?\n};/);

  assert.ok(expandableBlock);
  assert.ok(consultationPageBlock);
  assert.ok(workbenchBlock);
  assert.match(expandableBlock[0], /textRef = useRef<HTMLParagraphElement \| null>\(null\)/);
  assert.match(expandableBlock[0], /element\.scrollHeight > element\.clientHeight \+ 1/);
  assert.match(expandableBlock[0], /window\.addEventListener\('resize', measure\)/);
  assert.match(expandableBlock[0], /展开全文/);
  assert.match(expandableBlock[0], /className="relative min-w-0"/);
  assert.match(expandableBlock[0], /absolute bottom-0 right-0/);
  assert.doesNotMatch(expandableBlock[0], /content\.length > \(lines === 2 \? 64 : 96\)/);
  assert.match(consultationPageBlock[0], /<ConsultationCardExpandableText label="咨询详情" text=\{needDetail\} lines=\{mobile \? 2 : 1\} \/>/);
  assert.match(consultationPageBlock[0], /<ConsultationCardExpandableText label="跟进" text=\{followUpNote\} \/>/);
  assert.match(workbenchBlock[0], /<ConsultationCardExpandableText label="咨询详情" text=\{record\.need_detail\} \/>/);
  assert.doesNotMatch(source, /<ConsultationExpandableText/);
});

test('consultation modal uses compact flow sections for both editing and viewing', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);

  assert.ok(modalBlock);
  assert.match(source, /compactFlowSectionClass/);
  assert.match(source, /compactFieldGridClass/);
  assert.match(source, /基础信息/);
  assert.match(source, /沟通与测试/);
  assert.match(source, />试听</);
  assert.match(source, /结果与备注/);
  assert.doesNotMatch(source, /shadow-\[0_14px_35px_rgba\(14,165,233,0\.06\)\]/);
});

test('consultation view modal keeps the title header and uses a two by two report grid', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);
  const reportBlock = source.match(/const ConsultationReadOnlyReport = \([\s\S]*?\n};/);

  assert.ok(modalBlock);
  assert.ok(reportBlock);
  assert.match(modalBlock[0], /记录详情只读展示，管理员和机构负责人可以在这里进入编辑。/);
  assert.doesNotMatch(modalBlock[0], /hiddenForViewHeaderClass/);
  assert.match(reportBlock[0], /md:grid-cols-2/);
  assert.match(reportBlock[0], /min-h-\[14rem\]/);
  assert.doesNotMatch(reportBlock[0], /lg:grid-cols-4/);
  assert.doesNotMatch(reportBlock[0], /<section className="grid gap-3 lg:grid-cols-2">/);
  assert.match(reportBlock[0], /grid-cols-\[minmax\(0,0\.78fr\)_minmax\(0,1\.22fr\)\]/);
  assert.match(reportBlock[0], />试听</);
});

test('consultation read only cards use two inner columns in narrow modal widths', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const reportBlock = source.match(/const ConsultationReadOnlyReport = \([\s\S]*?\n};/);

  assert.ok(reportBlock);
  assert.match(reportBlock[0], /readOnlyTwoColumnGridClass/);
  assert.match(reportBlock[0], /<div className=\{`grid gap-x-3 gap-y-2 text-sm \$\{readOnlyTwoColumnGridClass\}`\}>[\s\S]*客服微信/);
  assert.match(reportBlock[0], /<div className=\{`grid gap-x-3 gap-y-2 text-sm \$\{readOnlyTwoColumnGridClass\}`\}>[\s\S]*试听教师/);
  assert.match(reportBlock[0], /<div className=\{`grid gap-3 text-sm \$\{readOnlyTwoColumnGridClass\}`\}>[\s\S]*最后更新/);
  assert.doesNotMatch(reportBlock[0], /sm:grid-cols-2 lg:grid-cols-1/);
});

test('consultation edit modal uses the same two by two flow cards as the view modal', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);

  assert.ok(modalBlock);
  assert.match(modalBlock[0], /<div className="grid gap-3 md:grid-cols-2">/);
  assert.match(modalBlock[0], /<section ref=\{baseInfoRef\} className=\{cn\(compactFlowSectionClass, 'min-h-\[14rem\] scroll-mt-6'/);
  assert.match(modalBlock[0], /<section ref=\{contentRef\} className=\{cn\(compactFlowSectionClass, 'min-h-\[14rem\] scroll-mt-6 space-y-3'/);
  assert.match(modalBlock[0], /<div ref=\{trialSectionRef\} className=\{cn\(compactFlowSectionClass, 'min-h-\[14rem\] scroll-mt-6'/);
  assert.match(modalBlock[0], /<section className=\{`\$\{compactFlowSectionClass\} min-h-\[14rem\] scroll-mt-6 space-y-3`\}>[\s\S]*结果与备注/);
});

test('consultation edit form derives lit flow stages from edited fields', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);

  assert.match(source, /function deriveConsultationFlowFromFields\(values: ConsultationFormValues\): ConsultationFormValues/);
  assert.match(source, /values\.teacher_id \|\| values\.receiving_teacher/);
  assert.match(source, /values\.need_detail\.trim\(\)/);
  assert.match(source, /values\.test_taken \|\| values\.test_images\.length > 0/);
  assert.match(source, /values\.trial_taken \|\| values\.trial_time_slot \|\| values\.trial_class_id \|\| values\.trial_class_manual \|\| values\.trial_teacher \|\| values\.trial_feedback/);
  assert.match(source, /values\.flow_stage === '成功进班'/);
  assert.match(source, /const flow_stage = completed_stages\[completed_stages\.length - 1\] \|\| values\.flow_stage \|\| consultationFlowStages\[0\];/);
  assert.ok(modalBlock);
  assert.match(modalBlock[0], /setForm\(\(current\) => deriveConsultationFlowFromFields\(\{ \.\.\.current, \[key\]: value \}\)\);/);
  assert.match(modalBlock[0], /currentUser\.role === 'member'/);
  assert.match(modalBlock[0], /teacher_id: currentUser\.username/);
  assert.match(modalBlock[0], /setForm\(deriveConsultationFlowFromFields\(defaultAssignedValues\)\);/);
});

test('consultation edit form uses assignment teacher dropdown and scoped class options', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);

  assert.ok(modalBlock);
  assert.match(modalBlock[0], /const assignableClassOptions =/);
  assert.match(modalBlock[0], /classMatchesAssignedTeacher\(item, selectedTeacher, currentUser\)/);
  assert.match(modalBlock[0], /负责老师VX：/);
  assert.match(modalBlock[0], /aria-label="选择负责老师"/);
  assert.doesNotMatch(modalBlock[0], /分配老师\/负责老师/);
  assert.match(modalBlock[0], /其他：手动输入/);
  assert.match(modalBlock[0], /trialUsesManualClass/);
  assert.match(modalBlock[0], /successUsesManualClass/);
  assert.doesNotMatch(modalBlock[0], /若没找到对应班级，可以直接手动输入/);
});

test('consultation edit form keeps wechat status capsules compressed in one row without visible teacher chevron', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);

  assert.ok(modalBlock);
  assert.match(modalBlock[0], /grid grid-cols-\[minmax\(0,0\.82fr\)_minmax\(0,1\.18fr\)\] gap-2/);
  assert.match(modalBlock[0], /<span className="min-w-0 truncate">客服微信：/);
  assert.match(modalBlock[0], /<span className="pointer-events-none absolute inset-x-3 top-1\/2 z-10 min-w-0 -translate-y-1\/2 truncate text-center">/);
  assert.match(modalBlock[0], /className="h-full min-h-10 w-full cursor-pointer appearance-none rounded-2xl bg-transparent px-3 text-transparent outline-none"/);
  const teacherCapsuleBlock = modalBlock[0].match(/负责老师VX：[\s\S]*?aria-label="选择负责老师"[\s\S]*?<\/label>/);
  assert.ok(teacherCapsuleBlock);
  assert.doesNotMatch(teacherCapsuleBlock[0], /ChevronDown/);
});

test('consultation edit form highlights changed section titles and uses teacher dropdowns', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);

  assert.ok(modalBlock);
  assert.match(source, /const compactFlowTitleClass = \(active = false\)/);
  assert.match(modalBlock[0], /const baseSectionActive =/);
  assert.match(modalBlock[0], /const communicationSectionActive =/);
  assert.match(modalBlock[0], /const trialSectionActive =/);
  assert.match(modalBlock[0], /const resultSectionActive =/);
  assert.match(modalBlock[0], /compactFlowTitleClass\(baseSectionActive\)/);
  assert.match(modalBlock[0], /compactFlowTitleClass\(communicationSectionActive\)/);
  assert.match(modalBlock[0], /compactFlowTitleClass\(trialSectionActive\)/);
  assert.match(modalBlock[0], /compactFlowTitleClass\(resultSectionActive\)/);
  assert.match(modalBlock[0], /<select value=\{form\.trial_teacher\}/);
  assert.match(modalBlock[0], /onChange=\{\(e\) => updateField\('trial_teacher', e\.target\.value\)\}/);
  assert.match(source, /const compactEditLabelClass = consultationLabelClass;/);
});

test('consultation success result does not carry payment card status in the consultation form', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);
  const reportBlock = source.match(/const ConsultationReadOnlyReport = \([\s\S]*?\n};/);

  assert.ok(modalBlock);
  assert.ok(reportBlock);
  assert.doesNotMatch(source, /payment_card_status/);
  assert.doesNotMatch(source, /收费排卡/);
});

test('consultation flow display labels shorten test and trial stage wording', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const labelBlock = source.match(/const consultationStageDisplayLabel = \(stage: string\) => \{[\s\S]*?\n};/);

  assert.ok(labelBlock);
  assert.match(labelBlock[0], /if \(stage === '待测试'\) return '测试';/);
  assert.match(labelBlock[0], /if \(stage === '待试听'\) return '试听';/);
  assert.doesNotMatch(labelBlock[0], /return '待测试'/);
  assert.doesNotMatch(labelBlock[0], /return '待试听'/);
});

test('consultation flow bar renders a one-row B6 dot stepper with responsive labels', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const flowBarBlock = source.match(/const ConsultationFlowBar = \([\s\S]*?\n};/);

  assert.ok(flowBarBlock);
  assert.match(flowBarBlock[0], /flowNodes/);
  assert.match(flowBarBlock[0], /showOver/);
  assert.match(flowBarBlock[0], /grid-cols-\[repeat\(7,minmax\(1\.55rem,1fr\)\)\]/);
  assert.match(flowBarBlock[0], /min-\[720px\]:inline/);
  assert.match(flowBarBlock[0], /consultationStageShortLabel\(item\)/);
  assert.match(flowBarBlock[0], /border-\[#22B981\] bg-\[#22B981\] text-white/);
  assert.match(flowBarBlock[0], /border-\[#0EA5E9\] bg-\[#0EA5E9\] text-white/);
  assert.match(flowBarBlock[0], /border-\[#F45B7A\]/);
});

test('consultation result capsule matches stage widths and uses empty enter fail short labels', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const flowBarBlock = source.match(/const ConsultationFlowBar = \([\s\S]*?\n};/);
  const resultCapsuleBlock = source.match(/const ConsultationResultCapsule = \([\s\S]*?\n};/);

  assert.ok(flowBarBlock);
  assert.ok(resultCapsuleBlock);
  assert.match(source, /const consultationResultShortLabel = \(stage: string\) => \{/);
  assert.match(source, /if \(stage === '成功进班'\) return '进';/);
  assert.match(source, /if \(stage === '试听失败'\) return '败';/);
  assert.match(source, /return '';/);
  assert.match(flowBarBlock[0], /grid-cols-\[repeat\(6,minmax\(1\.75rem,1fr\)\)\]/);
  assert.match(flowBarBlock[0], /grid-cols-\[repeat\(6,minmax\(0,1fr\)\)\]/);
  assert.match(resultCapsuleBlock[0], /consultationResultShortLabel\(resultStage\)/);
  assert.doesNotMatch(resultCapsuleBlock[0], /成\/败/);
});

test('consultation flow treats result as the sixth dot node instead of a separate wide capsule', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const flowBarBlock = source.match(/const ConsultationFlowBar = \([\s\S]*?\n};/);

  assert.ok(flowBarBlock);
  assert.match(flowBarBlock[0], /key: 'consultation-result'/);
  assert.match(flowBarBlock[0], /type: 'result' as const/);
  assert.match(flowBarBlock[0], /const resultShortLabel = consultationResultShortLabel\(resultStage\) \|\| '进';/);
  assert.match(flowBarBlock[0], /h-\[18px\] w-\[18px\]/);
  assert.match(flowBarBlock[0], /h-\[21px\] w-\[21px\]/);
  assert.doesNotMatch(flowBarBlock[0], /h-\[42px\] text-xs/);
});

test('consultation modal jump controls are preserved on the dot stepper without widening nodes', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const flowBarBlock = source.match(/const ConsultationFlowBar = \([\s\S]*?\n};/);

  assert.ok(flowBarBlock);
  assert.match(flowBarBlock[0], /showJumpActions && node\.type !== 'over'/);
  assert.match(flowBarBlock[0], /onStageJump\?\./);
  assert.match(flowBarBlock[0], /absolute left-1\/2 top-0 z-20 flex h-4 w-4/);
  assert.match(flowBarBlock[0], /<ArrowRight size=\{9\} \/>/);
  assert.doesNotMatch(flowBarBlock[0], /basis-\[20%\]/);
  assert.doesNotMatch(flowBarBlock[0], /flex-\[1_1_80%\]/);
  assert.doesNotMatch(flowBarBlock[0], /h-7 w-4/);
});

test('consultation full flow bar avoids fixed minimum columns that can push the result capsule outside the modal', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const flowBarBlock = source.match(/const ConsultationFlowBar = \([\s\S]*?\n};/);

  assert.ok(flowBarBlock);
  assert.match(flowBarBlock[0], /'grid-cols-\[repeat\(7,minmax\(0,1fr\)\)\]'/);
  assert.doesNotMatch(flowBarBlock[0], /min-\[640px\]:grid-cols-\[repeat\(6,minmax\(5\.8rem,1fr\)\)\]/);
  assert.doesNotMatch(flowBarBlock[0], /grid-cols-\[minmax\(0,1fr\)_4\.5rem\]/);
  assert.match(flowBarBlock[0], /hidden min-\[720px\]:inline/);
  assert.match(flowBarBlock[0], /min-\[720px\]:hidden/);
});

test('consultation modal places flow subtitle and status lamp beside the title', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);

  assert.ok(modalBlock);
  assert.match(modalBlock[0], /flowHeaderMetaClass/);
  assert.match(modalBlock[0], /咨询流程<\/h4>[\s\S]*当前咨询的完整流程位置/);
  assert.match(modalBlock[0], /当前咨询的完整流程位置[\s\S]*<ConsultationStatusLamp stage=\{form\.flow_stage\} \/>/);
  assert.doesNotMatch(modalBlock[0], /<p className="mt-1 text-sm text-slate-500 dark:text-slate-400">\s*\{readOnly \? '当前咨询的完整流程位置。'/);
});

test('consultation modal flow uses the same compact one-row style as consultation cards', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);

  assert.ok(modalBlock);
  assert.match(modalBlock[0], /<ConsultationFlowBar[\s\S]*mode="list"/);
  assert.match(modalBlock[0], /showOver/);
  assert.match(modalBlock[0], /onOverClick=\{\(\) => \{/);
  assert.doesNotMatch(modalBlock[0], /mode="full"/);
});

test('consultation modal flow capsules jump to matching edit sections without changing stage state', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);
  const flowBarBlock = source.match(/const ConsultationFlowBar = \([\s\S]*?\n};/);

  assert.ok(modalBlock);
  assert.ok(flowBarBlock);
  assert.match(flowBarBlock[0], /showJumpActions/);
  assert.match(flowBarBlock[0], /onStageJump/);
  assert.match(flowBarBlock[0], /aria-label=\{`跳转到\$\{node\.title\}编辑栏`\}/);
  assert.match(modalBlock[0], /const baseInfoRef = useRef<HTMLElement \| null>\(null\);/);
  assert.match(modalBlock[0], /const testSectionRef = useRef<HTMLDivElement \| null>\(null\);/);
  assert.match(modalBlock[0], /const trialSectionRef = useRef<HTMLDivElement \| null>\(null\);/);
  assert.match(modalBlock[0], /const successSectionRef = useRef<HTMLDivElement \| null>\(null\);/);
  assert.match(modalBlock[0], /const handleStageJump = \(stage: string\) => \{/);
  assert.match(modalBlock[0], /target\?\.scrollIntoView\(\{ behavior: 'smooth', block: 'start' \}\);/);
  assert.match(modalBlock[0], /showJumpActions=\{!readOnly\}/);
  assert.match(modalBlock[0], /onStageJump=\{handleStageJump\}/);
});

test('consultation modal uses dot-stepper jump buttons and flashes the jumped edit section', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);
  const flowBarBlock = source.match(/const ConsultationFlowBar = \([\s\S]*?\n};/);

  assert.ok(modalBlock);
  assert.ok(flowBarBlock);
  assert.match(source, /const consultationJumpHighlightClass = /);
  assert.match(modalBlock[0], /const \[highlightedJumpStage, setHighlightedJumpStage\] = useState<string>\(''\);/);
  assert.match(modalBlock[0], /const jumpHighlightTimerRef = useRef<number \| null>\(null\);/);
  assert.match(modalBlock[0], /setHighlightedJumpStage\(stage\);/);
  assert.match(modalBlock[0], /window\.setTimeout\(\(\) => setHighlightedJumpStage\(''\), 900\)/);
  assert.match(modalBlock[0], /highlightedJumpStage === '已加小客服微信'/);
  assert.match(modalBlock[0], /highlightedJumpStage === '正在沟通细节'/);
  assert.match(modalBlock[0], /highlightedJumpStage === '成功进班'/);
  assert.match(flowBarBlock[0], /absolute left-1\/2 top-0 z-20 flex h-4 w-4/);
  assert.match(flowBarBlock[0], /onStageJump\?\.\(node\.type === 'result'/);
  assert.doesNotMatch(flowBarBlock[0], /h-7 w-4/);
});

test('consultation result capsule keeps the colored label full width while preserving the dropdown hit area', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const resultCapsuleBlock = source.match(/const ConsultationResultCapsule = \([\s\S]*?\n};/);

  assert.ok(resultCapsuleBlock);
  assert.match(resultCapsuleBlock[0], /className=\{`min-w-0 overflow-hidden text-ellipsis \$\{showJumpAction \? 'flex-\[1_1_76%\] pl-3 pr-1' : 'flex-1'\}/);
  assert.match(resultCapsuleBlock[0], /className="flex h-full basis-\[24%\] shrink-0 items-stretch"/);
  assert.match(resultCapsuleBlock[0], /className="relative flex flex-1 items-center justify-center text-current opacity-80"/);
  assert.match(resultCapsuleBlock[0], /className="absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-default"/);
  assert.doesNotMatch(resultCapsuleBlock[0], /right-5/);
});

test('consultation source restores ended records only after an explicit yes no confirmation', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);

  assert.ok(consultationPageBlock);
  assert.ok(modalBlock);
  assert.match(source, /function restoreConsultationValues\(values: ConsultationFormValues\): ConsultationFormValues/);
  assert.match(source, /restore_from_end: true/);
  assert.match(modalBlock[0], /confirmRestoreOpen/);
  assert.match(modalBlock[0], /是否恢复这个咨询？/);
  assert.match(modalBlock[0], /是\s*<\/button>/);
  assert.match(modalBlock[0], /否\s*<\/button>/);
  assert.match(modalBlock[0], /setForm\(\(current\) => restoreConsultationValues\(current\)\)/);
  assert.match(consultationPageBlock[0], /const \[restoreConfirmRecord, setRestoreConfirmRecord\] = useState<ConsultationRecord \| null>\(null\);/);
  assert.match(consultationPageBlock[0], /const handleConfirmRestoreConsultation = async \(\) =>/);
  assert.match(consultationPageBlock[0], /restoreConsultationValues\(toConsultationFormValues\(restoreConfirmRecord\)\)/);
  assert.match(consultationPageBlock[0], /是否恢复这个咨询？/);
});

test('consultation source keeps ai batch parse endpoint unchanged', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const batchModalBlock = source.match(/const ConsultationBatchModal = \([\s\S]*?\n};/);
  assert.ok(batchModalBlock);
  assert.match(batchModalBlock[0], /apiFetch<ConsultationBatchParseResponse>\('\/api\/consultations\/ai-parse'/);
  assert.doesNotMatch(batchModalBlock[0], /flow_stage/);
});

test('consultation page source keeps consultation detail under teacher and follow-up notes in the consultation info block', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);

  assert.ok(consultationPageBlock);
  assert.match(consultationPageBlock[0], /const needDetail = record\.need_detail\?\.trim\(\);/);
  assert.match(consultationPageBlock[0], /const followUpNote = record\.follow_up_note\?\.trim\(\);/);
  assert.match(consultationPageBlock[0], /const renderConsultationDetail = \(needDetail\?: string, followUpNote\?: string, mobile = false\) =>/);
  assert.match(consultationPageBlock[0], /label="咨询详情" text=\{needDetail\}/);
  assert.match(consultationPageBlock[0], /lines=\{mobile \? 2 : 1\}/);
  assert.match(consultationPageBlock[0], /label="跟进" text=\{followUpNote\}/);
  assert.doesNotMatch(consultationPageBlock[0], /备注：\{followUpNote\}/);
  assert.doesNotMatch(consultationPageBlock[0], /font-semibold whitespace-nowrap">备注<\/th>/);
  assert.match(consultationPageBlock[0], /grid-cols-\[minmax\(0,1fr\)_minmax\(2\.9rem,3\.75rem\)\]/);
});

test('consultation page source renders separate desktop pad and mobile consultation card layouts', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);

  assert.ok(consultationPageBlock);
  assert.match(consultationPageBlock[0], /const renderDesktopConsultationCard = \(record: ConsultationRecord, index: number\) =>/);
  assert.match(consultationPageBlock[0], /const renderPadConsultationCard = \(record: ConsultationRecord, index: number\) =>/);
  assert.match(consultationPageBlock[0], /const renderMobileConsultationCard = \(record: ConsultationRecord, index: number\) =>/);
  assert.match(consultationPageBlock[0], /grid-cols-\[96px_88px_112px_minmax\(120px,160px\)_120px_132px_72px\]/);
  assert.match(consultationPageBlock[0], /const renderB3FlowStrip = \(record: ConsultationRecord, busy: boolean, mobile = false\) =>/);
  assert.match(consultationPageBlock[0], /const renderB3MobileTimeline = \(record: ConsultationRecord, busy: boolean\) =>/);
  assert.match(consultationPageBlock[0], /grid-cols-\[minmax\(0,1fr\)_minmax\(2\.9rem,3\.75rem\)\]/);
  assert.doesNotMatch(consultationPageBlock[0], /min-w-\[31rem\]/);
  assert.match(consultationPageBlock[0], /showTopResultPill/);
  assert.match(consultationPageBlock[0], /hidden md:block xl:hidden/);
  assert.match(consultationPageBlock[0], /hidden xl:block/);
  assert.match(consultationPageBlock[0], /visibleRecords\.map\(renderDesktopConsultationCard\)/);
  assert.match(consultationPageBlock[0], /visibleRecords\.map\(renderPadConsultationCard\)/);
  assert.match(consultationPageBlock[0], /visibleRecords\.map\(renderMobileConsultationCard\)/);
});

test('consultation page source keeps desktop and tablet consultations as two-row cards', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);

  assert.ok(consultationPageBlock);
  assert.match(consultationPageBlock[0], /const handleInlineStageToggle = async \(record: ConsultationRecord, stage: string\) =>/);
  assert.match(consultationPageBlock[0], /const handleInlineResultChange = async \(record: ConsultationRecord, resultStage: ConsultationResultStage\) =>/);
  assert.match(consultationPageBlock[0], /const handleInlineEndConsultation = async \(record: ConsultationRecord\) =>/);
  assert.match(consultationPageBlock[0], /editable=\{canEditConsultations && !busy && !frozen\}/);
  assert.match(consultationPageBlock[0], /onStageClick=\{\(stage\) => handleInlineStageToggle\(record, stage\)\}/);
  assert.match(consultationPageBlock[0], /hidden md:block xl:hidden/);
  assert.match(consultationPageBlock[0], /hidden xl:block/);
  assert.match(consultationPageBlock[0], /md:hidden/);
  assert.match(consultationPageBlock[0], /onClick=\{\(\) => handleInlineEndConsultation\(record\)\}/);
  assert.match(source, /window\.scrollTo\(\{ top: 0, behavior: 'smooth' \}\)/);
  assert.match(consultationPageBlock[0], /const renderTimeRow = \(record: ConsultationRecord, boxed = false\) =>/);
  assert.match(consultationPageBlock[0], /\{record\.created_at \|\| '—'\}/);
  assert.match(consultationPageBlock[0], /\{record\.updated_at \|\| '—'\}/);
  assert.doesNotMatch(consultationPageBlock[0], /2xl:hidden/);
  assert.doesNotMatch(consultationPageBlock[0], /hidden 2xl:block/);

  const flowBarBlock = source.match(/const ConsultationFlowBar = \([\s\S]*?\n};/);
  assert.ok(flowBarBlock);
  assert.match(flowBarBlock[0], /grid-cols-\[repeat\(6,minmax\(1\.75rem,1fr\)\)\]/);
  assert.match(flowBarBlock[0], /grid-cols-\[repeat\(6,minmax\(0,1fr\)\)\]/);
  assert.match(flowBarBlock[0], /onStageDoubleClick/);
  assert.match(source, /activeWorkspacePage === 'calendar' \|\| activeWorkspacePage === 'consultation'/);
});

test('consultation mobile card keeps view edit icons in the top right and removes the bottom edit capsule', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);

  assert.ok(consultationPageBlock);
  const mobileCard = consultationPageBlock[0].match(/const renderMobileConsultationCard = \(record: ConsultationRecord, index: number\) => \{[\s\S]*?\n  \};/);
  assert.ok(mobileCard);
  assert.match(mobileCard[0], /getRecordResultPill\(record\)/);
  assert.match(mobileCard[0], /renderConsultationIconActions\(record, busy, true\)/);
  assert.match(mobileCard[0], /renderTimeRow\(record, true\)/);
  assert.match(mobileCard[0], /renderB3FlowStrip\(record, busy, true\)/);
  assert.doesNotMatch(mobileCard[0], /renderOverButton\(record, busy, 'h-9 px-3 text-xs'\)/);
  assert.match(mobileCard[0], /renderDeleteButton\(record, busy\)/);
  assert.match(consultationPageBlock[0], /aria-label="查看咨询"/);
  assert.match(consultationPageBlock[0], /aria-label="编辑咨询"/);
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
  assert.match(appSource, /rounded-\[14px\] border border-\[#D9EEF7\] bg-white shadow-\[0_6px_18px_rgba\(31,42,68,0\.04\)\] dark:border-white\/10 dark:bg-slate-950\/70/);
  assert.match(appSource, /bg-\[#F9FDFF\] px-4 py-3 dark:border-white\/10 dark:bg-white\/\[0\.03\]/);
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
  assert.match(classManagementBlock[0], /const pageRefreshLocked = loading \|\| classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(classManagementBlock[0], /const assignmentRefreshLocked = loading \|\| classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
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

test('class management source preserves expanded edit cards during manual refresh failures', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const pageRefreshLocked = loading \|\| classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(classManagementBlock[0], /const assignmentRefreshLocked = loading \|\| classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(classManagementBlock[0], /onClick=\{\(\) => loadPage\(expandedClassId, \{ preserveStateOnError: true \}\)\.catch\(\(\) => undefined\)\}/);
  assert.match(classManagementBlock[0], /onClick=\{\(\) => loadPage\(editingClass\.id, \{ preserveStateOnError: true \}\)\.catch\(\(\) => undefined\)\}/);
});

test('account administration source disables refresh and teacher alias actions while mutations run', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const approvalBlock = source.match(/const ApprovalPage = \([\s\S]*?\n};\n\nconst SettingsPage/);

  assert.ok(approvalBlock);
  assert.match(approvalBlock[0], /const organizationRequestRefreshLocked = organizationRequestsLoading \|\| organizationActingId !== null;/);
  assert.match(approvalBlock[0], /const organizationInviteRefreshLocked = organizationInviteLoading \|\| organizationInviteResetting;/);
  assert.match(approvalBlock[0], /const organizationListRefreshLocked = organizationsLoading \|\| deletingOrgId !== null;/);
  assert.match(approvalBlock[0], /const approvalRefreshLocked = loading \|\| actingId !== null;/);
  assert.match(approvalBlock[0], /const memberRefreshLocked = usersLoading \|\| bindingSummaryLoading \|\| roleSavingUserId !== null \|\| visiblePageSavingUserId !== null \|\| displayNameSavingUserId !== null \|\| deletingUserId !== null;/);
  assert.match(approvalBlock[0], /const teacherAliasActionLocked = taSubmitting \|\| taDeletingId !== null;/);
  assert.match(approvalBlock[0], /disabled=\{organizationRequestRefreshLocked\}[\s\S]*刷新机构申请/);
  assert.match(approvalBlock[0], /disabled=\{organizationInviteRefreshLocked\}[\s\S]*刷新邀请信息/);
  assert.match(approvalBlock[0], /disabled=\{organizationListRefreshLocked\}[\s\S]*刷新机构列表/);
  assert.match(approvalBlock[0], /disabled=\{approvalRefreshLocked\}[\s\S]*刷新列表/);
  assert.match(approvalBlock[0], /disabled=\{memberRefreshLocked\}[\s\S]*刷新成员/);
  assert.match(approvalBlock[0], /disabled=\{teacherAliasActionLocked\}[\s\S]*添加/);
  assert.match(approvalBlock[0], /disabled=\{teacherAliasActionLocked\}[\s\S]*openTeacherAliasEdit\(entry\)/);
  assert.match(approvalBlock[0], /disabled=\{teacherAliasActionLocked \|\| taDeletingId === entry\.wecom_userid\}[\s\S]*handleTeacherAliasDelete\(entry\.wecom_userid\)/);
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
