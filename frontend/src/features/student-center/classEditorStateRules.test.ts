import assert from 'node:assert/strict';
import test from 'node:test';
import type { ClassFormValues } from './model';
import {
  resolveClassEditorErrorsAfterToggle,
  resolveClassFormAfterFieldChange,
  resolveExpandedClassAfterToggle,
  resolveFormsAfterFieldChange,
  resolveTeacherSearchAfterChange,
} from './classEditorStateRules';

const baseForm: ClassFormValues = {
  name: '',
  subject: '数学',
  grade: '',
  teacher_name: '',
  stage: '小奥',
  current_grade: '四年级',
  class_number: '1',
  cohort_year: '2025',
  show_cohort_year: true,
  is_bridge: false,
  bridge_target: '小学衔接初中',
  content_track: '',
};

const emptyForm: ClassFormValues = {
  ...baseForm,
  subject: '',
  current_grade: '一年级',
  class_number: '1',
  cohort_year: '',
};

const gradeGroups = {
  小奥: ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级'],
  初中: ['七年级', '八年级', '九年级'],
  高中: ['高一', '高二', '高三'],
};

const allGrades = [...gradeGroups.小奥, ...gradeGroups.初中, ...gradeGroups.高中];

test('class editor field rules normalize grade input and reset invalid grade after stage changes', () => {
  assert.deepEqual(
    resolveClassFormAfterFieldChange(baseForm, 'current_grade', '4年级', gradeGroups, allGrades),
    {
      ...baseForm,
      current_grade: '四年级',
    },
  );

  assert.deepEqual(
    resolveClassFormAfterFieldChange(baseForm, 'stage', '初中', gradeGroups, allGrades),
    {
      ...baseForm,
      stage: '初中',
      current_grade: '七年级',
    },
  );

  assert.deepEqual(
    resolveClassFormAfterFieldChange({ ...baseForm, current_grade: '八年级' }, 'stage', '初中', gradeGroups, allGrades),
    {
      ...baseForm,
      stage: '初中',
      current_grade: '八年级',
    },
  );
});

test('class editor map rules update only the target form and preserve missing drafts with an empty form', () => {
  assert.deepEqual(
    resolveFormsAfterFieldChange(
      {
        new: baseForm,
        8: { ...baseForm, subject: '物理' },
      },
      8,
      'subject',
      '国际数学',
      emptyForm,
      gradeGroups,
      allGrades,
    ),
    {
      new: baseForm,
      8: { ...baseForm, subject: '国际数学' },
    },
  );

  assert.deepEqual(
    resolveFormsAfterFieldChange({}, 'new', 'class_number', '3', emptyForm, gradeGroups, allGrades),
    {
      new: { ...emptyForm, class_number: '3' },
    },
  );
});

test('class editor lightweight state rules keep local updates centralized', () => {
  assert.deepEqual(resolveTeacherSearchAfterChange({ new: '曹', 8: '王' }, 8, '李'), {
    new: '曹',
    8: '李',
  });

  assert.equal(resolveExpandedClassAfterToggle(null, 8, false), 8);
  assert.equal(resolveExpandedClassAfterToggle(8, 8, false), null);
  assert.equal(resolveExpandedClassAfterToggle(8, 'new', true), 8);

  assert.deepEqual(resolveClassEditorErrorsAfterToggle(), {
    formError: '',
    assignmentError: '',
  });
});
