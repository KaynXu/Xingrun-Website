import assert from 'node:assert/strict';
import test from 'node:test';

import {
  academicGradeGroups,
  academicGradeOptions,
  academicStageOptions,
  buildClassDisplayName,
  formatClassDisplayName,
  getAcademicGradeRank,
  getAcademicGradeRankFromText,
  getAcademicStageFromGrade,
  getCurrentSchoolYearStart,
  inferAcademicCohortYear,
  normalizeAcademicGradeLabel,
  normalizeClassNameInput,
} from './domain/classNaming';

test('normalizes grade labels to the unified Chinese display format', () => {
  assert.equal(normalizeAcademicGradeLabel('1年级'), '一年级');
  assert.equal(normalizeAcademicGradeLabel('初一'), '七年级');
  assert.equal(normalizeAcademicGradeLabel('初三'), '九年级');
  assert.equal(normalizeAcademicGradeLabel('高二'), '高二');
  assert.equal(normalizeAcademicGradeLabel('  7年级  '), '七年级');
});

test('keeps the stage and grade options in the student-center order', () => {
  assert.deepEqual(academicStageOptions, ['小奥', '初中', '高中']);
  assert.deepEqual(academicGradeGroups.小奥, ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级']);
  assert.deepEqual(academicGradeGroups.初中, ['七年级', '八年级', '九年级']);
  assert.deepEqual(academicGradeGroups.高中, ['高一', '高二', '高三']);
  assert.deepEqual(academicGradeOptions, [
    '一年级',
    '二年级',
    '三年级',
    '四年级',
    '五年级',
    '六年级',
    '七年级',
    '八年级',
    '九年级',
    '高一',
    '高二',
    '高三',
  ]);
});

test('infers stage and low-to-high grade rank from unified labels', () => {
  assert.equal(getAcademicStageFromGrade('六年级'), '小奥');
  assert.equal(getAcademicStageFromGrade('初二'), '初中');
  assert.equal(getAcademicStageFromGrade('高三'), '高中');
  assert.ok(getAcademicGradeRank('一年级') < getAcademicGradeRank('七年级'));
  assert.ok(getAcademicGradeRank('七年级') < getAcademicGradeRank('高一'));
  assert.equal(getAcademicGradeRank('未填写年级'), 999);
});

test('finds grade rank from class names used outside student center', () => {
  assert.equal(getAcademicGradeRankFromText('数学七年级1班'), 6);
  assert.equal(getAcademicGradeRankFromText('物理 9年级 2班'), 8);
  assert.equal(getAcademicGradeRankFromText('高中三班'), 11);
  assert.equal(getAcademicGradeRankFromText('小四创新班'), 3);
  assert.equal(getAcademicGradeRankFromText('未识别'), 999);
});

test('infers cohort year from the July school-year boundary', () => {
  assert.equal(getCurrentSchoolYearStart(new Date('2026-06-30T23:59:59+08:00')), 2025);
  assert.equal(getCurrentSchoolYearStart(new Date('2026-07-01T00:00:00+08:00')), 2026);
  assert.equal(inferAcademicCohortYear('七年级', new Date('2026-06-30T23:59:59+08:00')), 2025);
  assert.equal(inferAcademicCohortYear('八年级', new Date('2026-07-01T00:00:00+08:00')), 2025);
});

test('builds class display names with optional cohort and bridge suffix', () => {
  assert.equal(
    buildClassDisplayName({
      current_grade: '4年级',
      grade: '',
      class_number: '1',
      cohort_year: '2025',
      show_cohort_year: true,
      is_bridge: false,
    }),
    '2025级·四年级·1班',
  );
  assert.equal(
    buildClassDisplayName({
      current_grade: '四年级',
      grade: '',
      class_number: '1',
      cohort_year: '2025',
      show_cohort_year: false,
      is_bridge: true,
    }),
    '四年级·1班·衔接',
  );
});

test('formats current class display names for page and permission layers', () => {
  const classItem = {
    name: '旧数学四年级1班',
    current_grade: '4年级',
    grade: '',
    class_number: '1',
    cohort_year: '2025',
    is_bridge: false,
  };

  assert.equal(formatClassDisplayName(classItem), '四年级·1班');
  assert.equal(formatClassDisplayName(classItem, { showCohortYear: true }), '2025级·四年级·1班');
  assert.equal(formatClassDisplayName({ name: '历史手动班级' }), '历史手动班级');
});

test('normalizes handwritten class names for legacy invite matching', () => {
  assert.equal(normalizeClassNameInput('6年级2班'), '六年级 2 班');
  assert.equal(normalizeClassNameInput('六年级二班'), '六年级 2 班');
  assert.equal(normalizeClassNameInput('七年级三班'), '七年级 3 班');
  assert.equal(normalizeClassNameInput('随便写'), '随便写');
});
