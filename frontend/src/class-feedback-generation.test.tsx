import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import {
  buildClassFeedbackPeriodPreview,
  buildCreateClassFeedbackTaskRequest,
  buildClassFeedbackConfirmPayload,
  defaultStageLabelGroups,
  formatClassFeedbackStudentCopyText,
  type ClassFeedbackStudentCard,
} from './classFeedbackGeneration';
import { ClassFeedbackGenerationWorkspace } from './ClassFeedbackGenerationWorkspace';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');
const workspaceSource = readFileSync(new URL('./ClassFeedbackGenerationWorkspace.tsx', import.meta.url), 'utf8');

test('defaultStageLabelGroups exposes the built-in grouped labels', () => {
  assert.equal(defaultStageLabelGroups.length, 4);
  assert.equal(defaultStageLabelGroups[0]?.group, '课堂状态');
  assert.match(defaultStageLabelGroups[3]?.labels.join(','), /进步明显/);
});

test('buildClassFeedbackPeriodPreview resolves daily weekly monthly and stage ranges', () => {
  assert.deepEqual(
    buildClassFeedbackPeriodPreview({
      periodGranularity: 'daily',
      anchorDate: '2026-04-09',
    }),
    {
      label: '2026-04-09',
      startDate: '2026-04-09',
      endDate: '2026-04-09',
      periodLengthDays: 1,
      periodGranularity: 'daily',
    },
  );

  assert.deepEqual(
    buildClassFeedbackPeriodPreview({
      periodGranularity: 'weekly',
      year: 2026,
      week: 15,
    }),
    {
      label: '2026第15周',
      startDate: '2026-04-06',
      endDate: '2026-04-12',
      periodLengthDays: 7,
      periodGranularity: 'weekly',
    },
  );

  assert.deepEqual(
    buildClassFeedbackPeriodPreview({
      periodGranularity: 'monthly',
      year: 2026,
      month: 3,
    }),
    {
      label: '2026三月',
      startDate: '2026-03-01',
      endDate: '2026-03-31',
      periodLengthDays: 31,
      periodGranularity: 'monthly',
    },
  );

  assert.deepEqual(
    buildClassFeedbackPeriodPreview({
      periodGranularity: 'stage',
      year: 2026,
      stageName: '春季',
    }),
    {
      label: '2026春季',
      startDate: '2026-03-01',
      endDate: '2026-05-31',
      periodLengthDays: 92,
      periodGranularity: 'stage',
    },
  );
});

test('buildCreateClassFeedbackTaskRequest emits structured backend period payloads', () => {
  assert.deepEqual(
    buildCreateClassFeedbackTaskRequest({
      classId: 8,
      periodGranularity: 'daily',
      anchorDate: '2026-04-09',
    }),
    {
      class_id: 8,
      period_granularity: 'daily',
      anchor_date: '2026-04-09',
    },
  );

  assert.deepEqual(
    buildCreateClassFeedbackTaskRequest({
      classId: 8,
      periodGranularity: 'weekly',
      year: 2026,
      week: 15,
    }),
    {
      class_id: 8,
      period_granularity: 'weekly',
      year: 2026,
      week: 15,
    },
  );

  assert.deepEqual(
    buildCreateClassFeedbackTaskRequest({
      classId: 8,
      periodGranularity: 'monthly',
      year: 2026,
      month: 3,
    }),
    {
      class_id: 8,
      period_granularity: 'monthly',
      year: 2026,
      month: 3,
    },
  );

  assert.deepEqual(
    buildCreateClassFeedbackTaskRequest({
      classId: 8,
      periodGranularity: 'stage',
      year: 2026,
      stageName: '春季',
    }),
    {
      class_id: 8,
      period_granularity: 'stage',
      year: 2026,
      stage_name: '春季',
    },
  );
});

test('buildClassFeedbackConfirmPayload keeps final class summary and checked student entries', () => {
  const payload = buildClassFeedbackConfirmPayload({
    classSummaryFinalText: '正式班级反馈',
    students: [
      {
        studentId: 1,
        name: '张三',
        aiDraft: '草稿',
        finalText: '正式反馈',
        checked: true,
        sourceSummary: '2 节课次记录 + 1 条阶段备注',
        highlightLabels: ['进步明显'],
        highlightNote: '开口更主动',
      },
    ],
  });

  assert.equal(payload.class_summary_final_text, '正式班级反馈');
  assert.deepEqual(payload.student_entries, [
    { student_id: 1, final_text: '正式反馈' },
  ]);
});

test('formatClassFeedbackStudentCopyText joins student feedback into a parent-friendly batch format', () => {
  const content = formatClassFeedbackStudentCopyText([
    {
      studentId: 1,
      name: '张三',
      aiDraft: '草稿反馈',
      finalText: '正式反馈',
      checked: true,
      sourceSummary: '已汇总本阶段素材',
      highlightLabels: [],
      highlightNote: '',
    },
    {
      studentId: 2,
      name: '李四',
      aiDraft: '待补充草稿',
      finalText: '',
      checked: false,
      sourceSummary: '已汇总本阶段素材',
      highlightLabels: [],
      highlightNote: '',
    },
  ]);

  assert.equal(content, '【张三】\n正式反馈\n\n【李四】\n待补充草稿');
});

test('ClassFeedbackGenerationWorkspace renders source summary, stage notes, class summary, and student cards', () => {
  const students: ClassFeedbackStudentCard[] = [
    {
      studentId: 1,
      name: '张三',
      aiDraft: '草稿反馈',
      finalText: '草稿反馈',
      checked: false,
      sourceSummary: '2 节课次记录 + 1 条阶段备注',
      highlightLabels: ['进步明显'],
      highlightNote: '开口更主动',
    },
  ];

  const markup = renderToStaticMarkup(
    <ClassFeedbackGenerationWorkspace
      classNameLabel="S01A1"
      teacherNameLabel="王老师"
      controlBar={<div>控制栏占位</div>}
      headerAside={<div>右侧占位</div>}
      sourceSummaryItems={['已命中 2 节课次记录', '1 名学生资料完整']}
      labelGroups={defaultStageLabelGroups}
      classStatusTags={['进入状态快']}
      students={students}
      classSummaryText="班级反馈草稿"
      statusMessage="已生成 1 名学生反馈"
      draftStatusLabel="草稿已保存，可继续编辑。"
      stageNotes={{
        classStatusNote: '',
        parentFeedbackNote: '',
        teachingFocusNote: '',
        nextStagePreviewNote: '',
      }}
      isGenerating={false}
      isSaving={false}
      isConfirming={false}
      onClassSummaryChange={() => undefined}
      onStageNoteChange={() => undefined}
      onClassStatusTagToggle={() => undefined}
      onHighlightToggle={() => undefined}
      onHighlightNoteChange={() => undefined}
      onStudentFinalTextChange={() => undefined}
      onStudentCheckedChange={() => undefined}
      onGenerate={() => undefined}
      onSaveDraft={() => undefined}
      onCopyClassSummary={() => undefined}
      onCopyAllStudents={() => undefined}
      onConfirm={() => undefined}
    />,
  );

  assert.match(markup, /课堂反馈/);
  assert.match(markup, /控制栏占位/);
  assert.match(markup, /右侧占位/);
  assert.match(markup, /资料摘要/);
  assert.match(markup, /阶段备注/);
  assert.match(markup, /班级状态标签/);
  assert.match(markup, /班级总评/);
  assert.match(markup, /草稿已保存，可继续编辑/);
  assert.match(markup, /按未检查优先排序/);
  assert.match(markup, /张三/);
  assert.match(markup, /保存草稿/);
  assert.match(markup, /确认本次反馈/);
  assert.doesNotMatch(markup, /补充学生/);
  assert.doesNotMatch(markup, /新增学生/);
  assert.match(markup, /dark:text-white/);
  assert.match(markup, /bg-sky-600/);
  assert.match(markup, /dark:bg-slate-950\/78/);
});

test('ClassFeedbackGenerationWorkspace reuses shared workspace style helpers for surfaces, fields, and buttons', () => {
  assert.match(
    workspaceSource,
    /workspaceCardClass,\s*workspaceFieldClass,\s*workspacePrimaryButtonClass,\s*workspaceSecondaryButtonClass,\s*workspaceSoftCardClass/,
  );
  assert.match(workspaceSource, /const cardClass = `\$\{workspaceCardClass\} p-6`;/);
  assert.match(workspaceSource, /const softCardClass = `\$\{workspaceSoftCardClass\} p-4`;/);
  assert.match(workspaceSource, /const fieldClass = workspaceFieldClass;/);
  assert.match(workspaceSource, /props\.controlBar \? <div className="mt-4">\{props\.controlBar\}<\/div> : null/);
  assert.match(workspaceSource, /className=\{workspacePrimaryButtonClass\}/);
  assert.match(workspaceSource, /className=\{workspaceSecondaryButtonClass\}/);
});

test('App source wires the standalone class feedback page and existing class student APIs', () => {
  assert.match(appSource, /const \[activeClassFeedbackTaskId, setActiveClassFeedbackTaskId\] = useState<number \| null>\(null\);/);
  assert.match(appSource, /apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(appSource, /await createClassFeedbackTask\(\{/);
  assert.match(appSource, /const classFeedbackPeriodPreview = useMemo\(/);
  assert.match(appSource, /buildClassFeedbackPeriodPreview\(/);
  assert.match(appSource, /buildCreateClassFeedbackTaskRequest\(/);
  assert.match(appSource, /await saveClassFeedbackTaskDraft\(activeClassFeedbackTaskId, \{/);
  assert.match(appSource, /classStatusTags: classFeedbackStatusTags/);
  assert.doesNotMatch(appSource, /onAddStudent=\{handleAddStudent\}/);
  assert.match(appSource, /await generateClassFeedbackTask\(activeClassFeedbackTaskId, \{/);
  assert.match(appSource, /formatClassFeedbackStudentCopyText\(sortedClassFeedbackStudents\)/);
  assert.match(appSource, /const classFeedbackDraftStatusLabel = currentTaskStatus === 'confirmed'/);
  assert.match(appSource, /const sortedClassFeedbackStudents = useMemo/);
  assert.match(appSource, /已命中 \$\{matchedLessonCount\} 节课次记录/);
  assert.match(appSource, /反馈阶段：\$\{classFeedbackPeriodPreview\.label\}/);
  assert.match(appSource, /覆盖范围：\$\{classFeedbackPeriodPreview\.startDate\} 至 \$\{classFeedbackPeriodPreview\.endDate\}/);
  assert.match(appSource, /lesson\.date >= classFeedbackPeriodPreview\.startDate/);
  assert.match(appSource, /lesson\.date <= classFeedbackPeriodPreview\.endDate/);
  assert.match(appSource, /await confirmClassFeedbackTask\(activeClassFeedbackTaskId, payload\);/);
  assert.match(appSource, /<ClassFeedbackGenerationWorkspace/);
  assert.doesNotMatch(appSource, /反馈周期：\$\{classFeedbackPeriodPreview\.label\}/);
  assert.doesNotMatch(appSource, /时间范围：\$\{classFeedbackPeriodPreview\.startDate\} 至 \$\{classFeedbackPeriodPreview\.endDate\}/);
  assert.doesNotMatch(appSource, /请选择时间范围后创建反馈任务/);
});

test('App source no longer renders the class feedback intro hero section', () => {
  assert.doesNotMatch(appSource, /<p className="text-xs font-semibold uppercase tracking-\[0\.3em\] text-sky-600">Stage Feedback<\/p>/);
  assert.doesNotMatch(appSource, /<h3 className=\{`\$\{workspaceSectionTitleClass\} mt-3`\}>课堂反馈<\/h3>/);
  assert.doesNotMatch(appSource, /选择班级和时间范围后，汇总阶段素材并生成班级总评与学生个性化反馈。/);
});

test('App source injects the class feedback control bar into the workspace header instead of rendering it above the workspace', () => {
  assert.match(appSource, /const classFeedbackControlBar = \(/);
  assert.match(appSource, /const classFeedbackHeaderAside = \(/);
  assert.match(appSource, /<select[\s\S]*value=\{classFeedbackPeriodMode\}/);
  assert.match(appSource, /classFeedbackPeriodPreview\.label/);
  assert.doesNotMatch(appSource, /type="date"\s*\n\s*value=\{startDate\}/);
  assert.doesNotMatch(appSource, /type="date"\s*\n\s*value=\{endDate\}/);
  assert.doesNotMatch(appSource, /const \[startDate, setStartDate\]/);
  assert.doesNotMatch(appSource, /const \[endDate, setEndDate\]/);
  assert.match(appSource, /<ClassFeedbackGenerationWorkspace[\s\S]*controlBar=\{/);
  assert.match(appSource, /<ClassFeedbackGenerationWorkspace[\s\S]*headerAside=\{/);
  assert.doesNotMatch(appSource, /return \(\s*<div className=\{`\$\{workspacePageClass\} mx-auto max-w-7xl space-y-6`\}>\s*<div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">/);
});

test('App source anchors class feedback period preview to the top-right and task actions to the bottom-right', () => {
  assert.match(
    appSource,
    /return \(\s*<div className=\{`\$\{workspacePageClass\} space-y-6`\}>/,
  );
  assert.match(
    workspaceSource,
    /<header className=\{`\$\{cardClass\} grid gap-6 xl:grid-cols-\[minmax\(0,1fr\)_minmax\(19rem,20rem\)\] xl:items-stretch`\}>/,
  );
  assert.match(
    appSource,
    /<div className="grid gap-3 sm:grid-cols-2 xl:max-w-\[43rem\] xl:grid-cols-4">/,
  );
  assert.match(
    appSource,
    /<div className="grid gap-3 sm:grid-cols-2 xl:col-span-2 xl:grid-cols-2">/,
  );
  assert.match(
    appSource,
    /const classFeedbackHeaderAside = \(\s*<div className="flex flex-col gap-3 xl:min-h-\[10\.5rem\] xl:justify-between">/,
  );
  assert.match(
    workspaceSource,
    /\{props\.headerAside \? props\.headerAside : null\}/,
  );
  assert.match(
    appSource,
    /<div className="grid gap-3 sm:grid-cols-2">/,
  );
  assert.doesNotMatch(appSource, /<div className=\{`\$\{workspacePageClass\} mx-auto max-w-7xl space-y-6`\}>/);
});

test('App source synchronizes class feedback member selection against accessible classes', () => {
  assert.match(appSource, /function syncMemberScopedClassSelection\(/);
  assert.match(appSource, /setSelectedClassId\(\(current\) => syncMemberScopedClassSelection\(currentUser\.role, classItems, current\)\);/);
  assert.match(appSource, /setSelectedClassId\(\(current\) => syncMemberScopedClassSelection\(currentUser\.role, classes, current\)\);/);
});
