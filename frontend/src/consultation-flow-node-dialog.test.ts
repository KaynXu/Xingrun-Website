import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const sharedSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/consultationShared.tsx'), 'utf8');
const pageSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationPage.tsx'), 'utf8');
const modalSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationModal.tsx'), 'utf8');
const typesSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/consultationTypes.ts'), 'utf8');

test('modular ordinary flow node dialog has compact teacher and note UI', () => {
  assert.match(sharedSource, /export const ConsultationFlowNodeDialog/);
  assert.match(sharedSource, /stageTitle/);
  assert.match(sharedSource, /studentSummary/);
  assert.match(sharedSource, /teacherLabel/);
  assert.match(sharedSource, /阶段备注/);
  assert.match(sharedSource, /保存/);
  assert.match(sharedSource, /取消/);
  assert.match(sharedSource, /CheckCircle2/);
  assert.match(sharedSource, /selectedTeacherId/);
  assert.match(sharedSource, /setAsCurrent \?/);
  assert.match(sharedSource, /保存后会把后续阶段恢复为空白/);
});

test('modular flow node dialog filters and recommends teachers without saving', () => {
  assert.match(sharedSource, /from '\.\.\/\.\.\/domain\/consultationTeacherSelection'/);
  assert.match(sharedSource, /filterConsultationTeacherOptionsForStage\(stage, teacherOptions\)/);
  assert.match(sharedSource, /getConsultationFlowNodeRecommendedTeacher\(stage, values, stageTeacherOptions\)/);
  assert.match(sharedSource, /searchConsultationTeacherOptions\(stageTeacherOptions, teacherSearch\)/);
  assert.match(sharedSource, /placeholder="筛选老师"/);
});

test('modular flow node helpers map stage content to consultation fields and pure rules', () => {
  assert.match(sharedSource, /export function getConsultationFlowNodeDraft\(values: ConsultationFormValues, stage: string\): ConsultationFlowNodeDraft/);
  assert.match(sharedSource, /export function applyConsultationFlowNodeDraft/);
  assert.match(sharedSource, /export function clearConsultationFlowNodeContent\(values: ConsultationFormValues, stage: string\): ConsultationFormValues/);
  assert.match(sharedSource, /customer_service_teacher/);
  assert.match(sharedSource, /communication_teacher_added/);
  assert.match(sharedSource, /test_teacher/);
  assert.match(sharedSource, /trial_teacher/);
  assert.match(sharedSource, /follow_up_note/);
  assert.match(sharedSource, /completeConsultationFlowStage\(state, stage/);
  assert.match(sharedSource, /setConsultationFlowCurrentStage\(state, stage/);
  assert.match(sharedSource, /cancelConsultationFlowStage\(state, stage\)/);
});

test('modular consultation types include saved flow node and transfer metadata fields', () => {
  assert.match(typesSource, /stage_teacher_ids: Record<string, string>/);
  assert.match(typesSource, /customer_service_added: string/);
  assert.match(typesSource, /customer_service_teacher: string/);
  assert.match(typesSource, /customer_service_note: string/);
  assert.match(typesSource, /communication_teacher_added: string/);
  assert.match(typesSource, /communication_teacher_note: string/);
  assert.match(typesSource, /test_teacher: string/);
  assert.match(typesSource, /test_note: string/);
  assert.match(typesSource, /trial_teacher_added: string/);
  assert.match(typesSource, /trial_teacher_note: string/);
  assert.match(typesSource, /assignment_note: string/);
});

test('consultation edit modal opens ordinary node dialog and confirms before cancelling lit nodes', () => {
  assert.match(modalSource, /flowNodeDialog/);
  assert.match(modalSource, /openFlowNodeDialog/);
  assert.match(modalSource, /<ConsultationFlowNodeDialog/);
  assert.match(modalSource, /onStageClick=\{\(nextStage\) => openFlowNodeDialog\(nextStage, false\)\}/);
  assert.match(modalSource, /onStageContextMenu=\{\(nextStage\) => openFlowNodeDialog\(nextStage, true\)\}/);
  assert.match(modalSource, /onStageLongPress=\{\(nextStage\) => openFlowNodeDialog\(nextStage, true\)\}/);
  assert.match(modalSource, /getConsultationFlowLightColor\(form, stage\)/);
  assert.match(modalSource, /window\.confirm/);
  assert.match(modalSource, /是否取消该阶段状态/);
  assert.match(modalSource, /clearConsultationFlowNodeContent\(current, stage\)/);
});

test('consultation list cards open ordinary node dialog and confirm before cancelling lit nodes', () => {
  assert.match(pageSource, /flowNodeDialog/);
  assert.match(pageSource, /openInlineFlowNodeDialog/);
  assert.match(pageSource, /handleSaveInlineFlowNodeDialog/);
  assert.match(pageSource, /<ConsultationFlowNodeDialog/);
  assert.match(pageSource, /getConsultationFlowLightColor\(toConsultationFormValues\(record\), stage\)/);
  assert.match(pageSource, /window\.confirm/);
  assert.match(pageSource, /是否取消该阶段状态/);
  assert.match(pageSource, /clearConsultationFlowNodeContent\(toConsultationFormValues\(record\), stage\)/);
  assert.match(pageSource, /applyConsultationFlowNodeDraft\(toConsultationFormValues\(record\), stage, draft, setAsCurrent\)/);
});
