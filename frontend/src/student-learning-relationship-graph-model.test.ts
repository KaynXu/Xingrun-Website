import assert from 'node:assert/strict';
import { test } from 'node:test';

import type { ClassCommentaryStudentLearningGraphSummary } from './classCommentary';
import { buildStudentLearningRelationshipGraphModel } from './features/class-feedback/StudentLearningRelationshipGraph';

function summaryFixture(): ClassCommentaryStudentLearningGraphSummary {
  return {
    task_id: 9,
    student_id: 11,
    subject_key: 'math',
    sync_status: 'learned',
    can_retry: false,
    error: '',
    curriculum_assignment: null,
    current_states: [{
      knowledge_point_key: 'quadratic-graphs',
      knowledge_point_name: '二次函数的图像和性质',
      state: 'developing',
      observed_at: '2026-08-11T10:00:00Z',
      curriculum: null,
    }],
    timeline: [{
      event_ref: 'event-weak',
      knowledge_point_key: 'quadratic-graphs',
      knowledge_point_name: '二次函数的图像和性质',
      state: 'weak',
      previous_state: null,
      trend: 'new_observation',
      observed_at: '2026-08-04T10:00:00Z',
      evidence: {
        evidence_ref: 'evidence-weak',
        quote: '对参数变化与图像平移的联系还不稳定.',
        lesson_id: 17,
        lesson_name: '第 17 次课程',
        revision_id: 51,
        revision_no: 1,
        confirmed_at: '2026-08-04T10:00:00Z',
      },
      teaching_methods: [],
      next_steps: [],
      curriculum: null,
    }, {
      event_ref: 'event-developing',
      knowledge_point_key: 'quadratic-graphs',
      knowledge_point_name: '二次函数的图像和性质',
      state: 'developing',
      previous_state: 'weak',
      trend: 'improved',
      observed_at: '2026-08-11T10:00:00Z',
      evidence: {
        evidence_ref: 'evidence-developing',
        quote: '已经能结合参数变化判断图像移动方向.',
        lesson_id: 18,
        lesson_name: '第 18 次课程',
        revision_id: 52,
        revision_no: 2,
        confirmed_at: '2026-08-11T10:00:00Z',
      },
      teaching_methods: ['图像与参数联动练习'],
      next_steps: ['继续练习顶点式与图像平移'],
      curriculum: null,
    }],
    used_graph_evidence_refs: ['evidence-developing'],
    used_graph_evidence: [],
  };
}

test('student relationship model is deterministic and keeps knowledge points deduplicated', () => {
  const summary = summaryFixture();
  const first = buildStudentLearningRelationshipGraphModel('示例学生', summary);
  const second = buildStudentLearningRelationshipGraphModel('示例学生', {
    ...summary,
    timeline: [...summary.timeline].reverse(),
  });

  assert.deepEqual(first, second);
  assert.equal(first.nodes.filter((node) => node.kind === 'knowledge_point').length, 1);
  assert.equal(first.nodes.filter((node) => node.kind === 'learning_event').length, 2);
  assert.equal(first.nodes.filter((node) => node.kind === 'learning_state').length, 2);
  assert.equal(first.nodes.filter((node) => node.kind === 'evidence').length, 2);
  assert.ok(first.nodes.every((node) => Number.isFinite(node.x) && Number.isFinite(node.y)));
});

test('student relationship model includes only response-provable relations', () => {
  const model = buildStudentLearningRelationshipGraphModel('示例学生', summaryFixture());
  const relations = new Set(model.edges.map((edge) => edge.relation));

  for (const expected of [
    'HAS_STATE',
    'ABOUT_KNOWLEDGE_POINT',
    'OBSERVED_IN',
    'SUPPORTED_BY',
    'FROM_REVISION',
    'FOR_STUDENT',
    'TAUGHT_WITH',
    'RECOMMENDS_NEXT',
  ]) {
    assert.ok(relations.has(expected), `missing ${expected}`);
  }
  assert.equal(relations.has('IMPROVED_FROM'), false);
  assert.equal(relations.has('SUPERSEDES'), false);
  assert.equal(relations.has('LED_TO'), false);
});

test('student relationship model does not leak another student fixture', () => {
  const model = buildStudentLearningRelationshipGraphModel('学生 A', summaryFixture());

  assert.ok(model.nodes.some((node) => node.label === '学生 A'));
  assert.equal(model.nodes.some((node) => node.label.includes('学生 B')), false);
  assert.equal(model.nodes.some((node) => node.label.includes('70%')), false);
});
