import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';
import {
  buildRecommendedConsultationClassFilters,
  buildConsultationEnterClassPayload,
  filterConsultationEnterClassOptions,
  type ConsultationEnterClassDraft,
} from './consultationEnterClass';

const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

const quickDraft: ConsultationEnterClassDraft = {
  class_type: 'group',
  subject: '数学',
  stage: '初中',
  current_grade: '七年级',
  class_number: '2',
  cohort_year: 2026,
  show_cohort_year: true,
  is_bridge: true,
  bridge_target: '初中->高中',
};

test('buildConsultationEnterClassPayload builds existing class payload', () => {
  assert.deepEqual(buildConsultationEnterClassPayload({ mode: 'existing', existingClassId: '12' }), {
    mode: 'existing',
    class_id: 12,
  });
});

test('buildConsultationEnterClassPayload includes teaching teacher handoff fields', () => {
  assert.deepEqual(buildConsultationEnterClassPayload({
    mode: 'existing',
    existingClassId: '12',
    teachingTeacherId: 'teacher_a',
    teachingTeacherName: '甲老师',
    teachingTeacherUserId: 8,
  }), {
    mode: 'existing',
    class_id: 12,
    teaching_teacher_id: 'teacher_a',
    teaching_teacher: '甲老师',
    teaching_teacher_user_id: 8,
  });
});

test('buildConsultationEnterClassPayload builds quick class payload from class naming fields', () => {
  const payload = buildConsultationEnterClassPayload({ mode: 'quick-create', quickClassDraft: quickDraft });

  assert.equal(payload.mode, 'quick_new_class');
  assert.equal(payload.class_name, '数学·高2026级·七年级·2班·初衔高');
  assert.equal(payload.subject, '数学');
  assert.equal(payload.grade, '七年级');
  assert.equal(payload.stage, '初中');
  assert.equal(payload.current_grade, '七年级');
  assert.equal(payload.class_number, '2');
  assert.equal(payload.cohort_year, 2026);
  assert.equal(payload.show_cohort_year, true);
  assert.equal(payload.is_bridge, true);
  assert.equal(payload.bridge_target, '初中->高中');
});

test('buildConsultationEnterClassPayload builds converted pending payload', () => {
  assert.deepEqual(buildConsultationEnterClassPayload({ mode: 'pending' }), {
    mode: 'converted_without_class',
  });
});

test('buildRecommendedConsultationClassFilters preselects consultation values as editable recommendations', () => {
  assert.deepEqual(buildRecommendedConsultationClassFilters({
    consultationSubject: '数学',
    consultationGrade: '六年级',
    subjectOptions: ['数学', '英语'],
  }), {
    subjectFilter: '数学',
    teacherFilter: 'all',
    stageFilter: '小奥',
    gradeFilter: '六年级',
  });
});

test('filterConsultationEnterClassOptions reuses class-management ordering for editable filters', () => {
  const classes = [
    { id: 3, name: '数学·七年级·3班', class_type: 'group', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '3' },
    { id: 2, name: '数学·三年级·1班', class_type: 'group', subject: '数学', grade: '三年级', stage: '小学', current_grade: '三年级', class_number: '1' },
    { id: 1, name: '数学·七年级·1v1', class_type: '1v1', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '1' },
    { id: 4, name: '英语·七年级·1班', class_type: 'group', subject: '英语', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '1' },
  ];

  const filtered = filterConsultationEnterClassOptions({
    classes,
    subjectOptions: ['数学', '英语'],
    filters: {
      subjectFilter: '数学',
      teacherFilter: 'all',
      stageFilter: '初中',
      gradeFilter: '七年级',
    },
  });

  assert.deepEqual(filtered.map((item) => item.id), [1, 3]);
});

test('filterConsultationEnterClassOptions can loosen recommended subject and grade filters', () => {
  const classes = [
    { id: 1, name: '数学·七年级·1班', class_type: 'group', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '1' },
    { id: 2, name: '物理·八年级·1班', class_type: 'group', subject: '物理', grade: '八年级', stage: '初中', current_grade: '八年级', class_number: '1' },
  ];

  const filtered = filterConsultationEnterClassOptions({
    classes,
    subjectOptions: ['数学', '物理'],
    filters: {
      subjectFilter: '物理',
      teacherFilter: 'all',
      stageFilter: '初中',
      gradeFilter: '八年级',
    },
  });

  assert.deepEqual(filtered.map((item) => item.id), [2]);
});

test('existing class submit treats consultation subject and grade as recommendations, not locks', () => {
  assert.match(appSource, /consultationSubject: selectedExistingClass\?\.subject \|\| \(existingClassFilters\.subjectFilter !== '全部学科' \? existingClassFilters\.subjectFilter : ''\) \|\| values\.consultation_subject/);
  assert.match(appSource, /grade: selectedExistingClass\?\.current_grade \|\| selectedExistingClass\?\.grade \|\| \(existingClassFilters\.gradeFilter !== '全部' \? existingClassFilters\.gradeFilter : ''\) \|\| values\.grade/);
  assert.doesNotMatch(appSource, /consultationSubject: values\.consultation_subject \|\| selectedExistingClass\?\.subject/);
  assert.doesNotMatch(appSource, /grade: values\.grade \|\| selectedExistingClass\?\.current_grade/);
});
