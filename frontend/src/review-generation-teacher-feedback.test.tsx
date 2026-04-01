import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildTeacherFeedbackSavePayload,
  defaultTeacherFeedbackTemplates,
  mergeRosterWithFeedbackDraft,
} from './reviewGenerationTeacherFeedback';

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
