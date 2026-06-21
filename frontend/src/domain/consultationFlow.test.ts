import assert from 'node:assert/strict';
import test from 'node:test';

import {
  cancelConsultationOver,
  cancelConsultationStage,
  calculateConsultationFlowLights,
  completeConsultationOver,
  completeConsultationStage,
  consultationProcessStages,
  createConsultationFlowState,
  setConsultationCurrentStage,
  type ConsultationFlowLight,
} from './consultationFlow';

function colors(lights: ConsultationFlowLight[]): Record<string, ConsultationFlowLight['color']> {
  return Object.fromEntries(lights.map((light) => [light.stage, light.color]));
}

test('nonlinear completed stages keep skipped middle stages white and last completed stage blue', () => {
  const state = createConsultationFlowState({
    completedStages: ['已加小客服微信', '已加对应教师微信', '待试听'],
    flowStage: '待试听',
  });

  assert.deepEqual(colors(calculateConsultationFlowLights(state)), {
    已加小客服微信: 'green',
    已加对应教师微信: 'green',
    正在沟通细节: 'white',
    待测试: 'white',
    待试听: 'blue',
    Over: 'white',
  });
});

test('saving a stage stores content and lights the last completed stage blue', () => {
  const state = completeConsultationStage(createConsultationFlowState(), '待测试', {
    teacherId: 'lei',
    note: '已安排测试',
  });

  assert.deepEqual(state.completedStages, ['待测试']);
  assert.equal(state.flowStage, '待测试');
  assert.deepEqual(state.stageContent['待测试'], { teacherId: 'lei', note: '已安排测试' });
  assert.equal(colors(calculateConsultationFlowLights(state)).待测试, 'blue');
});

test('canceling a green stage deletes that stage content and keeps the later current stage blue', () => {
  const state = createConsultationFlowState({
    completedStages: ['已加小客服微信', '已加对应教师微信', '待试听'],
    flowStage: '待试听',
    stageContent: {
      已加对应教师微信: { teacherId: 'cui', note: '已沟通' },
      待试听: { teacherId: 'lei', note: '已约试听' },
    },
  });

  const next = cancelConsultationStage(state, '已加对应教师微信');

  assert.deepEqual(next.completedStages, ['已加小客服微信', '待试听']);
  assert.equal(next.flowStage, '待试听');
  assert.equal(next.stageContent['已加对应教师微信'], undefined);
  assert.equal(next.stageContent['待试听']?.teacherId, 'lei');
  assert.deepEqual(colors(calculateConsultationFlowLights(next)), {
    已加小客服微信: 'green',
    已加对应教师微信: 'white',
    正在沟通细节: 'white',
    待测试: 'white',
    待试听: 'blue',
    Over: 'white',
  });
});

test('canceling a blue stage deletes it and moves blue to the previous completed stage', () => {
  const state = createConsultationFlowState({
    completedStages: ['已加小客服微信', '已加对应教师微信', '待试听'],
    flowStage: '待试听',
    stageContent: {
      已加对应教师微信: { teacherId: 'cui' },
      待试听: { teacherId: 'lei' },
    },
  });

  const next = cancelConsultationStage(state, '待试听');

  assert.deepEqual(next.completedStages, ['已加小客服微信', '已加对应教师微信']);
  assert.equal(next.flowStage, '已加对应教师微信');
  assert.equal(next.stageContent['待试听'], undefined);
  assert.deepEqual(colors(calculateConsultationFlowLights(next)), {
    已加小客服微信: 'green',
    已加对应教师微信: 'blue',
    正在沟通细节: 'white',
    待测试: 'white',
    待试听: 'white',
    Over: 'white',
  });
});

test('choosing an earlier current stage deletes later completed stages and their content', () => {
  const state = createConsultationFlowState({
    completedStages: ['已加小客服微信', '已加对应教师微信', '待试听'],
    flowStage: '待试听',
    stageContent: {
      已加小客服微信: { teacherId: 'ke' },
      已加对应教师微信: { teacherId: 'cui' },
      待试听: { teacherId: 'lei' },
    },
  });

  const next = setConsultationCurrentStage(state, '已加对应教师微信', {
    teacherId: 'hua',
    note: '回退到沟通教师',
  });

  assert.deepEqual(next.completedStages, ['已加小客服微信', '已加对应教师微信']);
  assert.equal(next.flowStage, '已加对应教师微信');
  assert.equal(next.stageContent['待试听'], undefined);
  assert.deepEqual(next.stageContent['已加对应教师微信'], {
    teacherId: 'hua',
    note: '回退到沟通教师',
  });
  assert.equal(colors(calculateConsultationFlowLights(next)).待试听, 'white');
});

test('failed Over is red and canceling it returns to the previous completed stage', () => {
  const failed = completeConsultationOver(
    createConsultationFlowState({
      completedStages: ['已加小客服微信', '待试听'],
      flowStage: '待试听',
    }),
    'failed',
    { note: '暂不进班' },
  );

  assert.equal(failed.flowStage, 'Over');
  assert.equal(failed.closingResult, 'failed');
  assert.equal(colors(calculateConsultationFlowLights(failed)).Over, 'red');

  const restored = cancelConsultationOver(failed);

  assert.equal(restored.flowStage, '待试听');
  assert.equal(restored.closingResult, '');
  assert.equal(restored.overContent, undefined);
  assert.equal(colors(calculateConsultationFlowLights(restored)).待试听, 'blue');
});

test('successful Over is blue without auto-completing skipped process stages', () => {
  const success = completeConsultationOver(
    createConsultationFlowState({
      completedStages: ['已加小客服微信', '待试听'],
      flowStage: '待试听',
      linkedClassId: 42,
      linkedStudentProfileId: 77,
    }),
    'success',
    { mode: 'existing-class' },
  );

  assert.equal(success.flowStage, 'Over');
  assert.equal(success.closingResult, 'success');
  assert.deepEqual(success.completedStages, ['已加小客服微信', '待试听']);
  assert.equal(colors(calculateConsultationFlowLights(success)).Over, 'blue');

  const restored = cancelConsultationOver(success);

  assert.equal(restored.flowStage, '待试听');
  assert.equal(restored.closingResult, '');
  assert.equal(restored.linkedClassId, 42);
  assert.equal(restored.linkedStudentProfileId, 77);
  assert.equal(restored.overContent, undefined);
  assert.equal(colors(calculateConsultationFlowLights(restored)).待试听, 'blue');
});
