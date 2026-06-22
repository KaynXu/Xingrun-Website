import assert from 'node:assert/strict';
import test from 'node:test';

import {
  filterConsultationTeacherOptionsForStage,
  getConsultationFlowNodeRecommendedTeacher,
  searchConsultationTeacherOptions,
} from './consultationTeacherSelection';

const teacherOptions = [
  { teacher_id: 'service-a', display_name: '未知客服', aliases: ['客服老师'] },
  { teacher_id: 'hua', display_name: '华老师', aliases: ['华奥鑫'] },
  { teacher_id: 'lei', display_name: '雷老师', aliases: ['雷文浩'] },
];

test('customer-service stage only offers the temporary default Lei teacher', () => {
  const options = filterConsultationTeacherOptionsForStage('已加小客服微信', teacherOptions);

  assert.deepEqual(options.map((item) => item.teacher_id), ['lei']);
});

test('customer-service stage does not fall back to unknown service teachers when Lei is absent', () => {
  const options = filterConsultationTeacherOptionsForStage('已加小客服微信', teacherOptions.slice(0, 2));

  assert.deepEqual(options, []);
});

test('customer-service stage recommends Lei by default without completing the node', () => {
  const recommendation = getConsultationFlowNodeRecommendedTeacher('已加小客服微信', {}, teacherOptions);

  assert.equal(recommendation.teacherId, 'lei');
  assert.equal(recommendation.teacherName, '雷老师');
});

test('customer-service teacher is not used as the next teacher recommendation', () => {
  const recommendation = getConsultationFlowNodeRecommendedTeacher('已加对应教师微信', {
    completed_stages: ['已加小客服微信'],
    customer_service_teacher: '小客服A',
  }, teacherOptions);

  assert.equal(recommendation.teacherId, '');
  assert.equal(recommendation.teacherName, '');
});

test('communication onward recommends the previous saved non-service teacher without completing the node', () => {
  const recommendation = getConsultationFlowNodeRecommendedTeacher('待测试', {
    completed_stages: ['正在沟通细节'],
    teacher_id: 'hua',
    receiving_teacher: '华老师',
  }, teacherOptions);

  assert.equal(recommendation.teacherId, 'hua');
  assert.equal(recommendation.teacherName, '华老师');
});

test('teacher search matches display names, ids, and aliases', () => {
  const options = searchConsultationTeacherOptions(teacherOptions, '文浩');

  assert.deepEqual(options.map((item) => item.teacher_id), ['lei']);
});
