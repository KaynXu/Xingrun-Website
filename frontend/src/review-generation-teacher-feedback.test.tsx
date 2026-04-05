import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import {
  buildTeacherFeedbackSavePayload,
  defaultTeacherFeedbackTemplates,
  mergeRosterWithFeedbackDraft,
} from './reviewGenerationTeacherFeedback';
import { TeacherFeedbackWorkspace } from './TeacherFeedbackWorkspace';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

test('defaultTeacherFeedbackTemplates exposes the expected built-in template ids in order', () => {
  assert.deepEqual(
    defaultTeacherFeedbackTemplates.map((item) => item.id),
    ['active', 'steady', 'review-soon', 'needs-support'],
  );
});

test('mergeRosterWithFeedbackDraft restores saved selections for current students and leaves new roster entries blank', () => {
  const merged = mergeRosterWithFeedbackDraft({
    roster: [
      { id: 1, name: 'Alice' },
      { id: 3, name: 'Carol' },
    ],
    savedStudents: [
      { student_id: 1, name: 'Alice', selected_template_id: 'active', remark: 'Explains steps clearly.' },
      { student_id: 2, name: 'Bob', selected_template_id: 'review-soon', remark: '' },
    ],
  });

  assert.deepEqual(merged, [
    { studentId: 1, name: 'Alice', selectedTemplateId: 'active', remark: 'Explains steps clearly.' },
    { studentId: 3, name: 'Carol', selectedTemplateId: '', remark: '' },
  ]);
});

test('buildTeacherFeedbackSavePayload keeps merged text plus ordered student index and custom templates only', () => {
  const payload = buildTeacherFeedbackSavePayload({
    mergedText: 'Alice: edited feedback',
    students: [
      { studentId: 2, name: 'Bob', selectedTemplateId: 'review-soon', remark: 'Review again tonight.' },
      { studentId: 1, name: 'Alice', selectedTemplateId: 'active', remark: 'Explains steps clearly.' },
    ],
    customTemplates: [
      ...defaultTeacherFeedbackTemplates,
      { id: 'custom-1', label: 'Retell once after class', guidance: 'Retell before homework.', isCustom: true },
    ],
  });

  assert.deepEqual(payload.student_index, [
    { student_id: 2, name: 'Bob' },
    { student_id: 1, name: 'Alice' },
  ]);
  assert.deepEqual(payload.students, [
    {
      student_id: 2,
      name: 'Bob',
      selected_template_id: 'review-soon',
      remark: 'Review again tonight.',
    },
    {
      student_id: 1,
      name: 'Alice',
      selected_template_id: 'active',
      remark: 'Explains steps clearly.',
    },
  ]);
  assert.deepEqual(payload.custom_templates, [
    {
      id: 'custom-1',
      label: 'Retell once after class',
      guidance: 'Retell before homework.',
    },
  ]);
});

test('TeacherFeedbackWorkspace renders the student area, custom template entry, editable preview, and copy-all action', () => {
  const markup = renderToStaticMarkup(
    <TeacherFeedbackWorkspace
      students={[{ studentId: 1, name: 'Alice', selectedTemplateId: '', remark: '' }]}
      templates={defaultTeacherFeedbackTemplates}
      feedbackText={'Alice: focus this week is function graphs'}
      generateLabel={'生成复习文档及课后反馈'}
      isLoadingStudents={false}
      isGenerating={false}
      isSaving={false}
      statusMessage={'已生成 1 名学生反馈'}
      onSelectTemplate={() => undefined}
      onRemarkChange={() => undefined}
      onFeedbackTextChange={() => undefined}
      onAddTemplate={() => undefined}
      onAddStudent={() => undefined}
      onRemoveStudent={() => undefined}
      onGenerate={() => undefined}
      onCopyAll={() => undefined}
    />,
  );

  assert.match(markup, /学生区/);
  assert.match(markup, /状态模板池/);
  assert.match(markup, /新增模板/);
  assert.match(markup, /新增学生/);
  assert.match(markup, /课后反馈预览/);
  assert.match(markup, /复制全部/);
  assert.doesNotMatch(markup, /课程信息/);
  assert.doesNotMatch(markup, /重新生成/);
});

test('review generation source wires teacher feedback loading, autosave, and copy-before-save into the shared lesson editor', () => {
  assert.match(appSource, /const loadFeedbackWorkspace = useCallback\(async \(lessonId: number, targetClassId: number\) => \{/);
  assert.match(appSource, /const isContinuingFeedback = initialLesson !== null;/);
  assert.match(appSource, /await loadFeedbackWorkspace\(createdLesson\.id, classId\);/);
  assert.match(appSource, /const timer = window\.setTimeout\(\(\) => \{\s*void saveFeedbackWorkspace\(\);\s*\}, 2500\);/);
  assert.match(appSource, /await saveFeedbackWorkspace\(\);\s*await navigator\.clipboard\.writeText\(feedbackText\);/);
  assert.match(appSource, /!\s*isContinuingFeedback && \(/);
  assert.match(appSource, /<TeacherFeedbackWorkspace[\s\S]*onGenerate=\{handleGenerateFeedbackDraft\}[\s\S]*onCopyAll=\{handleCopyAllFeedback\}/);
});
