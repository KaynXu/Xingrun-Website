import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { renderToStaticMarkup } from 'react-dom/server';

import {
  buildClassFeedbackPeriodPreview,
  buildCreateClassFeedbackTaskRequest,
  buildClassFeedbackConfirmPayload,
  defaultStageLabelGroups,
  formatClassFeedbackStudentCopyText,
  hasCompleteClassFeedbackGeneratedContent,
  isClassFeedbackTaskGenerating,
  normalizeClassFeedbackTaskResponse,
  type ClassFeedbackStudentCard,
} from './classFeedbackGeneration';
import { ClassFeedbackGenerationWorkspace } from './ClassFeedbackGenerationWorkspace';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');
const workspacePageContentSource = readFileSync(new URL('./features/navigation/WorkspacePageContent.tsx', import.meta.url), 'utf8');
const classFeedbackPageSource = readFileSync(new URL('./features/class-feedback/ClassFeedbackGenerationPage.tsx', import.meta.url), 'utf8');

function sourceBetween(source: string, startMarker: string, endMarker: string): string {
  const start = source.indexOf(startMarker);
  assert.notEqual(start, -1, `missing start marker: ${startMarker}`);
  const end = source.indexOf(endMarker, start);
  assert.notEqual(end, -1, `missing end marker: ${endMarker}`);
  return source.slice(start, end);
}

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

test('normalizeClassFeedbackTaskResponse keeps malformed async task payloads recoverable', () => {
  assert.equal(normalizeClassFeedbackTaskResponse({ id: 'bad' }), null);

  const task = normalizeClassFeedbackTaskResponse({
    id: 21,
    class_id: 7,
    teacher_user_id: null,
    teacher_name_snapshot: '王老师',
    start_date: '2026-05-01',
    end_date: '2026-05-07',
    period_length_days: 7,
    period_granularity: 'weekly',
    status: 'generating',
    class_summary_ai_draft: null,
    class_summary_final_text: null,
    class_status_tags: 'bad',
    class_status_note: null,
    parent_feedback_note: null,
    teaching_focus_note: null,
    next_stage_preview_note: null,
    student_highlights: null,
    student_entries: 'bad',
  });

  assert.ok(task);
  assert.equal(task.id, 21);
  assert.equal(task.class_summary_ai_draft, '');
  assert.deepEqual(task.student_entries, []);
  assert.deepEqual(task.student_highlights, []);
  assert.equal(isClassFeedbackTaskGenerating(task), true);
  assert.equal(hasCompleteClassFeedbackGeneratedContent(task, 1), false);

  const pendingTask = normalizeClassFeedbackTaskResponse(
    { id: 23, status: 'pending' },
    { fallbackClassId: 7 },
  );
  assert.ok(pendingTask);
  assert.equal(pendingTask.class_id, 7);
  assert.equal(isClassFeedbackTaskGenerating(pendingTask), true);
});

test('hasCompleteClassFeedbackGeneratedContent requires summary and every student output before success copy', () => {
  const task = normalizeClassFeedbackTaskResponse({
    id: 22,
    class_id: 7,
    teacher_user_id: null,
    teacher_name_snapshot: '王老师',
    start_date: '2026-05-01',
    end_date: '2026-05-07',
    period_length_days: 7,
    period_granularity: 'weekly',
    status: 'draft',
    class_summary_ai_draft: '本周整体进入状态更快。',
    class_summary_final_text: '',
    class_status_tags: [],
    class_status_note: '',
    parent_feedback_note: '',
    teaching_focus_note: '',
    next_stage_preview_note: '',
    student_highlights: [],
    student_entries: [
      { student_id: 1, student_name_snapshot: '学生甲', ai_draft: '表达更完整。', final_text: '' },
      { student_id: 2, student_name_snapshot: '学生乙', ai_draft: '', final_text: '计算更稳。' },
    ],
  });

  assert.ok(task);
  const missingStudentOutputTask = normalizeClassFeedbackTaskResponse({
    ...task,
    student_entries: [
      { student_id: 1, student_name_snapshot: '学生甲', ai_draft: '表达更完整。', final_text: '' },
      { student_id: 2, student_name_snapshot: '学生乙', ai_draft: '', final_text: '' },
    ],
  });

  assert.equal(hasCompleteClassFeedbackGeneratedContent(task, 2), true);
  assert.ok(missingStudentOutputTask);
  assert.equal(hasCompleteClassFeedbackGeneratedContent(missingStudentOutputTask, 2), false);
});

test('App source handles pending and incomplete class feedback generation responses through refresh path', () => {
  const generateHandler = sourceBetween(
    classFeedbackPageSource,
    'const handleGenerateClassFeedback = useCallback(async () => {',
    'const handleCopyClassFeedbackSummary = async () => {',
  );
  const hydrateHandler = sourceBetween(
    classFeedbackPageSource,
    'const hydrateClassFeedbackTask = useCallback(',
    'useEffect(() => {',
  );

  assert.match(hydrateHandler, /normalizeClassFeedbackTaskResponse\(rawTask\)/);
  assert.match(hydrateHandler, /isClassFeedbackTaskGenerating\(task\)/);
  assert.match(generateHandler, /const hydratedTask = await hydrateClassFeedbackTask\(generated\.id, selectedClassId\);/);
  assert.match(generateHandler, /hasCompleteClassFeedbackGeneratedContent\(hydratedTask, classFeedbackStudents\.length\)/);
  assert.match(generateHandler, /课堂反馈仍在生成中，请稍后点击刷新任务。/);
  assert.match(generateHandler, /反馈任务已返回，但生成内容不完整，请点击刷新任务确认。/);
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
  const markup = renderToStaticMarkup(
    <ClassFeedbackGenerationWorkspace
      classNameLabel="S01A1"
      teacherNameLabel="王老师"
      controlBar={<div>控制栏占位</div>}
      headerAside={<div>右侧占位</div>}
      sourceSummaryItems={['已命中 2 节课次记录']}
      labelGroups={defaultStageLabelGroups}
      classStatusTags={['进入状态快']}
      students={[]}
      classSummaryText="班级反馈草稿"
      statusMessage="已生成 0 名学生反馈"
      draftStatusLabel="草稿已保存。"
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

  assert.match(markup, /rounded-\[1\.75rem\][^"]*p-6/);
  assert.match(markup, /rounded-\[1\.5rem\][^"]*p-4/);
  assert.match(markup, /w-full rounded-xl border border-sky-200/);
  assert.match(markup, /class="mt-4"><div>控制栏占位<\/div>/);
  assert.match(markup, /bg-sky-600/);
  assert.match(markup, /border border-sky-200/);
  assert.match(markup, /保存草稿/);
  assert.match(markup, /确认本次反馈/);
});

test('App source wires the standalone class feedback page and existing class student APIs', () => {
  assert.match(appSource, /import \{ WorkspacePageContent \} from '\.\/features\/navigation\/WorkspacePageContent';/);
  assert.match(workspacePageContentSource, /import \{ ClassFeedbackGenerationPage \} from '\.\.\/class-feedback\/ClassFeedbackGenerationPage';/);
  assert.match(workspacePageContentSource, /activeWorkspacePage === 'class-feedback-generation' && canOpenWorkspacePage\(currentUser, 'class-feedback-generation'\) && <ClassFeedbackGenerationPage currentUser=\{currentUser\} \/>/);
  assert.match(classFeedbackPageSource, /const \[activeClassFeedbackTaskId, setActiveClassFeedbackTaskId\] = useState<number \| null>\(null\);/);
  assert.match(classFeedbackPageSource, /apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(classFeedbackPageSource, /await createClassFeedbackTask\(\{/);
  assert.match(classFeedbackPageSource, /const classFeedbackPeriodPreview = useMemo\(/);
  assert.match(classFeedbackPageSource, /buildClassFeedbackPeriodPreview\(/);
  assert.match(classFeedbackPageSource, /buildCreateClassFeedbackTaskRequest\(/);
  assert.match(classFeedbackPageSource, /await saveClassFeedbackTaskDraft\(activeClassFeedbackTaskId, \{/);
  assert.match(classFeedbackPageSource, /classStatusTags: classFeedbackStatusTags/);
  assert.doesNotMatch(classFeedbackPageSource, /onAddStudent=\{handleAddStudent\}/);
  assert.match(classFeedbackPageSource, /await generateClassFeedbackTask\(activeClassFeedbackTaskId, \{/);
  assert.match(classFeedbackPageSource, /formatClassFeedbackStudentCopyText\(sortedClassFeedbackStudents\)/);
  assert.match(classFeedbackPageSource, /const classFeedbackDraftStatusLabel = currentTaskStatus === 'confirmed'/);
  assert.match(classFeedbackPageSource, /const sortedClassFeedbackStudents = useMemo/);
  assert.match(classFeedbackPageSource, /已命中 \$\{matchedLessonCount\} 节课次记录/);
  assert.match(classFeedbackPageSource, /反馈阶段：\$\{classFeedbackPeriodPreview\.label\}/);
  assert.match(classFeedbackPageSource, /覆盖范围：\$\{classFeedbackPeriodPreview\.startDate\} 至 \$\{classFeedbackPeriodPreview\.endDate\}/);
  assert.match(classFeedbackPageSource, /lesson\.date >= classFeedbackPeriodPreview\.startDate/);
  assert.match(classFeedbackPageSource, /lesson\.date <= classFeedbackPeriodPreview\.endDate/);
  assert.match(classFeedbackPageSource, /await confirmClassFeedbackTask\(activeClassFeedbackTaskId, payload\);/);
  assert.match(classFeedbackPageSource, /<ClassFeedbackGenerationWorkspace/);
  assert.doesNotMatch(classFeedbackPageSource, /反馈周期：\$\{classFeedbackPeriodPreview\.label\}/);
  assert.doesNotMatch(classFeedbackPageSource, /时间范围：\$\{classFeedbackPeriodPreview\.startDate\} 至 \$\{classFeedbackPeriodPreview\.endDate\}/);
  assert.doesNotMatch(classFeedbackPageSource, /请选择时间范围后创建反馈任务/);
});

test('App source no longer renders the class feedback intro hero section', () => {
  assert.doesNotMatch(classFeedbackPageSource, /<p className="text-xs font-semibold uppercase tracking-\[0\.3em\] text-sky-600">Stage Feedback<\/p>/);
  assert.doesNotMatch(classFeedbackPageSource, /<h3 className=\{`\$\{workspaceSectionTitleClass\} mt-3`\}>课堂反馈<\/h3>/);
  assert.doesNotMatch(classFeedbackPageSource, /选择班级和时间范围后，汇总阶段素材并生成班级总评与学生个性化反馈。/);
});

test('App source injects the class feedback control bar into the workspace header instead of rendering it above the workspace', () => {
  assert.match(classFeedbackPageSource, /const classFeedbackControlBar = \(/);
  assert.match(classFeedbackPageSource, /const classFeedbackHeaderAside = \(/);
  assert.match(classFeedbackPageSource, /<select[\s\S]*value=\{classFeedbackPeriodMode\}/);
  assert.match(classFeedbackPageSource, /classFeedbackPeriodPreview\.label/);
  assert.doesNotMatch(classFeedbackPageSource, /type="date"\s*\n\s*value=\{startDate\}/);
  assert.doesNotMatch(classFeedbackPageSource, /type="date"\s*\n\s*value=\{endDate\}/);
  assert.doesNotMatch(classFeedbackPageSource, /const \[startDate, setStartDate\]/);
  assert.doesNotMatch(classFeedbackPageSource, /const \[endDate, setEndDate\]/);
  assert.match(classFeedbackPageSource, /<ClassFeedbackGenerationWorkspace[\s\S]*controlBar=\{/);
  assert.match(classFeedbackPageSource, /<ClassFeedbackGenerationWorkspace[\s\S]*headerAside=\{/);
  assert.doesNotMatch(classFeedbackPageSource, /return \(\s*<div className=\{`\$\{workspacePageClass\} mx-auto max-w-7xl space-y-6`\}>\s*<div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">/);
});

test('App source anchors class feedback period preview to the top-right and task actions to the bottom-right', () => {
  const workspaceMarkup = renderToStaticMarkup(
    <ClassFeedbackGenerationWorkspace
      classNameLabel="S01A1"
      teacherNameLabel="王老师"
      headerAside={<div>右侧操作区</div>}
      sourceSummaryItems={['已命中 2 节课次记录']}
      labelGroups={defaultStageLabelGroups}
      classStatusTags={[]}
      students={[]}
      classSummaryText=""
      statusMessage="待生成"
      draftStatusLabel="草稿"
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

  assert.match(
    classFeedbackPageSource,
    /return \(\s*<div className=\{`\$\{workspacePageClass\} space-y-6`\}>/,
  );
  assert.match(
    workspaceMarkup,
    /grid gap-6 xl:grid-cols-\[minmax\(0,1fr\)_minmax\(19rem,20rem\)\] xl:items-stretch/,
  );
  assert.match(
    classFeedbackPageSource,
    /<div className="grid gap-3 sm:grid-cols-2 xl:max-w-\[43rem\] xl:grid-cols-4">/,
  );
  assert.match(
    classFeedbackPageSource,
    /<div className="grid gap-3 sm:grid-cols-2 xl:col-span-2 xl:grid-cols-2">/,
  );
  assert.match(
    classFeedbackPageSource,
    /const classFeedbackHeaderAside = \(\s*<div className="flex flex-col gap-3 xl:min-h-\[10\.5rem\] xl:justify-between">/,
  );
  assert.match(
    workspaceMarkup,
    /右侧操作区/,
  );
  assert.match(
    classFeedbackPageSource,
    /<div className="grid gap-3 sm:grid-cols-2">/,
  );
  assert.doesNotMatch(classFeedbackPageSource, /<div className=\{`\$\{workspacePageClass\} mx-auto max-w-7xl space-y-6`\}>/);
});

test('App source synchronizes class feedback member selection against accessible classes', () => {
  const memberSelectionEffect = sourceBetween(
    classFeedbackPageSource,
    "if (classesLoading || currentUser.role !== 'member')",
    "if (classesLoading || currentUser.role === 'member' || selectedClassId === null)",
  );
  const staffSelectionEffect = sourceBetween(
    classFeedbackPageSource,
    "if (classesLoading || currentUser.role === 'member' || selectedClassId === null)",
    "if (!selectedClassId) {",
  );

  assert.match(classFeedbackPageSource, /function syncMemberScopedClassSelection\(/);
  assert.match(classFeedbackPageSource, /const resetClassFeedbackWorkspaceState = useCallback\(/);
  assert.match(classFeedbackPageSource, /resetClassFeedbackWorkspaceState\('班级权限已变化，请重新同步反馈任务。'\);/);
  assert.match(classFeedbackPageSource, /setActiveClassFeedbackTaskId\(null\);/);
  assert.match(classFeedbackPageSource, /setClassFeedbackSummary\(''\);/);
  assert.match(classFeedbackPageSource, /setClassFeedbackStudents\(\[\]\);/);
  assert.match(memberSelectionEffect, /const nextClassId = syncMemberScopedClassSelection\(currentUser\.role, classes, selectedClassId\);/);
  assert.match(memberSelectionEffect, /if \(nextClassId === selectedClassId\)/);
  assert.match(memberSelectionEffect, /resetClassFeedbackWorkspaceState\('班级权限已变化，请重新同步反馈任务。'\);/);
  assert.match(memberSelectionEffect, /setSelectedClassId\(nextClassId\);/);
  assert.match(staffSelectionEffect, /resetClassFeedbackWorkspaceState\('班级权限已变化，请重新同步反馈任务。'\);/);
  assert.match(staffSelectionEffect, /setSelectedClassId\(null\);/);
});

test('App source clears class feedback busy states and preserves drafts after failed actions', () => {
  const saveHandler = sourceBetween(
    classFeedbackPageSource,
    'const saveCurrentClassFeedbackDraft = useCallback(async () => {',
    'useEffect(() => {',
  );
  const generateHandler = sourceBetween(
    classFeedbackPageSource,
    'const handleGenerateClassFeedback = useCallback(async () => {',
    'const handleCopyClassFeedbackSummary = async () => {',
  );
  const confirmHandler = sourceBetween(
    classFeedbackPageSource,
    'const handleConfirmClassFeedback = useCallback(async () => {',
    'const checkedStudentCount = useMemo(',
  );
  const failureHandlers = [
    {
      source: saveHandler,
      busySetter: /setIsSavingClassFeedback\(false\);/,
      fallback: /'保存课堂反馈草稿失败，请重试。'/,
    },
    {
      source: generateHandler,
      busySetter: /setIsGeneratingClassFeedback\(false\);/,
      fallback: /'生成课堂反馈失败，请重试。'/,
    },
    {
      source: confirmHandler,
      busySetter: /setIsConfirmingClassFeedback\(false\);/,
      fallback: /'确认课堂反馈失败，请重试。'/,
    },
  ];

  for (const handler of failureHandlers) {
    assert.match(handler.source, /catch \(error\) \{/);
    assert.match(handler.source, handler.fallback);
    assert.match(handler.source, /finally \{/);
    assert.match(handler.source, handler.busySetter);
    assert.doesNotMatch(handler.source, /catch \(error\) \{[\s\S]*(setClassFeedbackSummary\(''\)|setClassFeedbackStudents\(\[\]\)|classFeedbackDraftSnapshotRef\.current = '')/);
  }
});
