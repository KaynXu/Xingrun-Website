import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import {
  buildClassFeedbackConfirmPayload,
  defaultStageLabelGroups,
  type ClassFeedbackStudentCard,
} from './classFeedbackGeneration';
import { ClassFeedbackGenerationWorkspace } from './ClassFeedbackGenerationWorkspace';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

test('defaultStageLabelGroups exposes the built-in grouped labels', () => {
  assert.equal(defaultStageLabelGroups.length, 4);
  assert.equal(defaultStageLabelGroups[0]?.group, '课堂状态');
  assert.match(defaultStageLabelGroups[3]?.labels.join(','), /进步明显/);
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
      sourceSummaryItems={['已命中 2 节课次记录', '1 名学生资料完整']}
      labelGroups={defaultStageLabelGroups}
      classStatusTags={['进入状态快']}
      students={students}
      classSummaryText="班级反馈草稿"
      statusMessage="已生成 1 名学生反馈"
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
      onAddStudent={() => undefined}
      onGenerate={() => undefined}
      onSaveDraft={() => undefined}
      onCopyClassSummary={() => undefined}
      onCopyAllStudents={() => undefined}
      onConfirm={() => undefined}
    />,
  );

  assert.match(markup, /班级反馈生成/);
  assert.match(markup, /资料摘要/);
  assert.match(markup, /阶段备注/);
  assert.match(markup, /班级状态标签/);
  assert.match(markup, /班级总评/);
  assert.match(markup, /张三/);
  assert.match(markup, /保存草稿/);
  assert.match(markup, /确认本次反馈/);
});

test('App source wires the standalone class feedback page and existing class student APIs', () => {
  assert.match(appSource, /const \[activeClassFeedbackTaskId, setActiveClassFeedbackTaskId\] = useState<number \| null>\(null\);/);
  assert.match(appSource, /apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(appSource, /await createClassFeedbackTask\(\{/);
  assert.match(appSource, /await saveClassFeedbackTaskDraft\(activeClassFeedbackTaskId, \{/);
  assert.match(appSource, /classStatusTags: classFeedbackStatusTags/);
  assert.match(appSource, /await createClassStudent\(selectedClassId, name\);/);
  assert.match(appSource, /await generateClassFeedbackTask\(activeClassFeedbackTaskId, \{/);
  assert.match(appSource, /await confirmClassFeedbackTask\(activeClassFeedbackTaskId, payload\);/);
  assert.match(appSource, /<ClassFeedbackGenerationWorkspace/);
});
