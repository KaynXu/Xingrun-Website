import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';
import {
  buildConsultationClassFilterDefaults,
  buildConsultationQuickClassForm,
  buildConsultationQuickClassSavePayload,
  filterConsultationStudentCenterClasses,
  validateConsultationQuickClassForm,
} from './consultationStudentCenterClassAdapter';
import {
  buildRecommendedConsultationClassFilters,
  buildConsultationEnterClassPayload,
  filterConsultationEnterClassOptions,
  type ConsultationEnterClassDraft,
} from './consultationEnterClass';

const modalSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationModal.tsx'), 'utf8');
const enterClassDialogSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationEnterClassDialog.tsx'), 'utf8');

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

test('buildConsultationEnterClassPayload keeps quick_new_class API compatibility without owning naming', () => {
  const payload = buildConsultationEnterClassPayload({ mode: 'quick-create', quickClassDraft: quickDraft });

  assert.equal(payload.mode, 'quick_new_class');
  assert.equal(payload.class_name, '');
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

test('quick-create payload no longer owns student-center class naming rules', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/domain/consultationEnterClass.ts'), 'utf8');
  assert.doesNotMatch(source, /buildClassDisplayName/);
  assert.match(source, /mode: 'quick_new_class'/);
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

test('consultation class filter defaults recommend subject grade and teacher without locking them', () => {
  assert.deepEqual(buildConsultationClassFilterDefaults({
    consultationSubject: '数学',
    consultationGrade: '六年级',
    teachingTeacherUserId: 8,
    subjectOptions: ['数学', '物理'],
  }), {
    subjectFilter: '数学',
    teacherFilter: 8,
    stageFilter: '小奥',
    gradeFilter: '六年级',
    classTypeFilter: 'all',
  });
});

test('consultation class filter defaults stay editable when consultation fields are missing', () => {
  assert.deepEqual(buildConsultationClassFilterDefaults({
    consultationSubject: '',
    consultationGrade: '',
    subjectOptions: ['数学', '物理'],
  }), {
    subjectFilter: '全部学科',
    teacherFilter: 'all',
    stageFilter: '全部学段',
    gradeFilter: '全部',
    classTypeFilter: 'all',
  });
});

test('consultation existing class filter reuses student-center class ordering and class type filter', () => {
  const classes = [
    { id: 3, name: '数学·七年级·3班', class_type: 'group', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '3', teacher_user_id: 8 },
    { id: 2, name: '数学·三年级·1班', class_type: 'group', subject: '数学', grade: '三年级', stage: '小奥', current_grade: '三年级', class_number: '1', teacher_user_id: 8 },
    { id: 1, name: '数学·七年级·1v1', class_type: '1v1', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '', teacher_user_id: 8 },
    { id: 4, name: '数学·七年级·2班', class_type: 'group', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '2', teacher_user_id: 9 },
  ];

  const filtered = filterConsultationStudentCenterClasses({
    classes,
    subjectOptions: ['数学'],
    teacherBindingByClassId: {},
    filters: {
      subjectFilter: '数学',
      teacherFilter: 8,
      stageFilter: '初中',
      gradeFilter: '七年级',
      classTypeFilter: 'all',
    },
  });

  assert.deepEqual(filtered.map((item) => item.id), [1, 3]);
});

test('consultation existing class filter can narrow to group classes', () => {
  const classes = [
    { id: 1, name: '数学·七年级·1v1', class_type: '1v1', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '', teacher_user_id: 8 },
    { id: 2, name: '数学·七年级·2班', class_type: 'group', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '2', teacher_user_id: 8 },
  ];

  const filtered = filterConsultationStudentCenterClasses({
    classes,
    subjectOptions: ['数学'],
    teacherBindingByClassId: {},
    filters: {
      subjectFilter: '数学',
      teacherFilter: 8,
      stageFilter: '初中',
      gradeFilter: '七年级',
      classTypeFilter: 'group',
    },
  });

  assert.deepEqual(filtered.map((item) => item.id), [2]);
});

test('consultation existing class filter can narrow to small classes', () => {
  const classes = [
    { id: 1, name: '数学·七年级·1v1', class_type: '1v1', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '', teacher_user_id: 8 },
    { id: 2, name: '数学·七年级·1v2', class_type: '1v2', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '', teacher_user_id: 8 },
    { id: 3, name: '数学·七年级·2班', class_type: 'group', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '2', teacher_user_id: 8 },
    { id: 4, name: '数学·七年级·3班', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '3', teacher_user_id: 8 },
  ];

  const filtered = filterConsultationStudentCenterClasses({
    classes,
    subjectOptions: ['数学'],
    teacherBindingByClassId: {},
    filters: {
      subjectFilter: '数学',
      teacherFilter: 8,
      stageFilter: '初中',
      gradeFilter: '七年级',
      classTypeFilter: 'small',
    },
  });

  assert.deepEqual(filtered.map((item) => item.id), [1, 2]);
});

test('consultation quick class form starts from student-center empty form and consultation recommendations', () => {
  assert.deepEqual(buildConsultationQuickClassForm({
    consultationSubject: '数学',
    consultationGrade: '六年级',
    subjectOptions: ['数学', '物理'],
  }), {
    name: '',
    class_type: 'group',
    subject: '数学',
    grade: '六年级',
    teacher_name: '',
    stage: '小奥',
    current_grade: '六年级',
    class_number: '1',
    cohort_year: '',
    show_cohort_year: false,
    is_bridge: false,
    bridge_target: '小学衔接初中',
    content_track: '',
    selected_student_ids: [],
  });
});

test('consultation quick class payload is generated by student-center save rules', () => {
  const form = buildConsultationQuickClassForm({
    consultationSubject: '数学',
    consultationGrade: '七年级',
    subjectOptions: ['数学'],
  });

  const payload = buildConsultationQuickClassSavePayload({
    form: {
      ...form,
      stage: '初中',
      class_number: '2',
      is_bridge: true,
      bridge_target: '初中衔接高中',
    },
    selectedTeacher: { id: 8, name: '何老师', username: 'he', role: 'member', org: '星润' },
    selectedTeacherUserId: 8,
  });

  assert.equal(payload.subject, '数学');
  assert.equal(payload.stage, '初中');
  assert.equal(payload.current_grade, '七年级');
  assert.equal(payload.class_number, '2');
  assert.equal(payload.teacher_user_id, 8);
  assert.equal(payload.teacher_name, '何老师');
  assert.equal(payload.is_bridge, true);
  assert.equal(payload.bridge_target, '初中衔接高中');
});

test('consultation quick class validation reuses student-center teacher requirement', () => {
  const form = buildConsultationQuickClassForm({
    consultationSubject: '数学',
    consultationGrade: '七年级',
    subjectOptions: ['数学'],
  });

  assert.equal(validateConsultationQuickClassForm({
    form,
    selectedTeacherUserId: null,
    gradeOptions: ['七年级'],
  }), '请先选择负责老师账号');
});

test('consultation quick class validation reuses student-center class number requirement', () => {
  const form = buildConsultationQuickClassForm({
    consultationSubject: '数学',
    consultationGrade: '七年级',
    subjectOptions: ['数学'],
  });

  assert.equal(validateConsultationQuickClassForm({
    form: {
      ...form,
      class_number: '',
    },
    selectedTeacher: { id: 8, name: '何老师', username: 'he', role: 'member', org: '星润' },
    selectedTeacherUserId: 8,
    gradeOptions: ['七年级'],
  }), '请选择班号');
});

test('existing class dialog treats consultation subject and grade as editable recommendations, not locks', () => {
  assert.match(enterClassDialogSource, /buildConsultationClassFilterDefaults/);
  assert.match(enterClassDialogSource, /filterConsultationStudentCenterClasses/);
  assert.match(enterClassDialogSource, /FloatingFilterBar/);
  assert.match(enterClassDialogSource, /existingClassFilterItems/);
  assert.match(enterClassDialogSource, /existingClassFilterSummary/);
  assert.match(enterClassDialogSource, /subjectFilter/);
  assert.match(enterClassDialogSource, /teacherFilter/);
  assert.match(enterClassDialogSource, /classTypeFilter/);
  assert.match(enterClassDialogSource, /setSubjectFilter\(String\(value\)\)/);
  assert.match(enterClassDialogSource, /setTeacherFilter\(Number\(value\)\)/);
  assert.match(enterClassDialogSource, /setGradeFilter\(String\(value\)\)/);
  assert.match(enterClassDialogSource, /setClassTypeFilter\(value as ConsultationClassTypeFilter\)/);
  assert.doesNotMatch(enterClassDialogSource, /<select value=\{subjectFilter\}/);
  assert.doesNotMatch(enterClassDialogSource, /<select value=\{teacherFilter\}/);
  assert.doesNotMatch(enterClassDialogSource, /<select value=\{gradeFilter\}/);
  assert.doesNotMatch(enterClassDialogSource, /<select value=\{classTypeFilter\}/);
  assert.doesNotMatch(enterClassDialogSource, /resolveConsultationAssignableClasses/);
  assert.doesNotMatch(enterClassDialogSource, /sourceStructureCompatibility/);
  assert.doesNotMatch(enterClassDialogSource, /disabled=\{true\}[^>]*value=\{subjectFilter\}/);
  assert.doesNotMatch(enterClassDialogSource, /disabled=\{true\}[^>]*value=\{gradeFilter\}/);
});
