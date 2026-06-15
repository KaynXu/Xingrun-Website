import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
const dialogBlock = source.match(/const ConsultationFlowNodeDialog = \([\s\S]*?\n};/);
const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);
const pageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);

test('ordinary consultation flow node dialog has the expected compact UI', () => {
  assert.ok(dialogBlock);
  assert.match(dialogBlock[0], /stageTitle/);
  assert.match(dialogBlock[0], /studentSummary/);
  assert.match(dialogBlock[0], /老师|教师|teacherLabel/);
  assert.match(dialogBlock[0], /阶段备注/);
  assert.match(dialogBlock[0], /保存/);
  assert.match(dialogBlock[0], /取消/);
  assert.match(dialogBlock[0], /CheckCircle2/);
  assert.match(dialogBlock[0], /selectedTeacherId/);
});

test('ordinary consultation flow node dialog warns when setting current stage clears later content', () => {
  assert.ok(dialogBlock);
  assert.match(dialogBlock[0], /setAsCurrent \?/);
  assert.match(dialogBlock[0], /保存后会把后续阶段恢复为空白/);
});

test('ordinary consultation flow node dialog filters teachers and preloads recommendations without saving', () => {
  assert.match(source, /from '\.\/domain\/consultationTeacherSelection'/);
  assert.ok(dialogBlock);
  assert.match(dialogBlock[0], /filterConsultationTeacherOptionsForStage\(stage, teacherOptions\)/);
  assert.match(dialogBlock[0], /getConsultationFlowNodeRecommendedTeacher\(stage, values, stageTeacherOptions\)/);
  assert.match(dialogBlock[0], /searchConsultationTeacherOptions\(stageTeacherOptions, teacherSearch\)/);
  assert.match(dialogBlock[0], /placeholder="筛选老师"/);
});

test('ordinary consultation flow node dialog maps stage content to existing consultation fields', () => {
  assert.match(source, /function getConsultationFlowNodeDraft\(values: ConsultationFormValues, stage: string\): ConsultationFlowNodeDraft/);
  assert.match(source, /function applyConsultationFlowNodeDraft\([\s\S]*?values: ConsultationFormValues,[\s\S]*?stage: string,[\s\S]*?draft: ConsultationFlowNodeDraft,[\s\S]*?setAsCurrent: boolean,[\s\S]*?\): ConsultationFormValues/);
  assert.match(source, /function clearConsultationFlowNodeContent\(values: ConsultationFormValues, stage: string\): ConsultationFormValues/);
  assert.match(source, /customer_service_teacher/);
  assert.match(source, /communication_teacher_added/);
  assert.match(source, /test_teacher/);
  assert.match(source, /trial_teacher/);
  assert.match(source, /follow_up_note/);
});

test('ordinary consultation flow node save writes assignment note when teacher changes', () => {
  assert.match(source, /const existingDraft = getConsultationFlowNodeDraft\(values, stage\);/);
  assert.match(source, /const stageTeacherChanged = Boolean\([\s\S]*?existingDraft\.teacherId[\s\S]*?draft\.teacherId[\s\S]*?existingDraft\.teacherId !== draft\.teacherId[\s\S]*?\);/);
  assert.match(source, /nextValues\.assignment_note = draft\.note\.trim\(\) \|\| `\$\{existingDraft\.teacherName \|\| existingDraft\.teacherId\} 转交给 \$\{teacherName \|\| draft\.teacherId\}`;/);
});

test('ordinary consultation flow node dialog keeps trial status separate from trial teacher name', () => {
  assert.match(source, /stage_teacher_ids/);
  assert.match(source, /stage_teacher_ids: \{\s*\.\.\.values\.stage_teacher_ids,/);
  assert.match(source, /if \(stage === '待试听'\) \{[\s\S]*teacherName: values\.trial_teacher,/);
  assert.doesNotMatch(source, /teacherName: values\.trial_teacher \|\| values\.trial_teacher_added/);
});

test('ordinary consultation flow node save and cancel use the pure flow rules', () => {
  assert.match(source, /completeConsultationFlowStage\(state, stage/);
  assert.match(source, /setConsultationFlowCurrentStage\(state, stage/);
  assert.match(source, /cancelConsultationFlowStage\(state, stage\)/);
  assert.match(source, /function clearConsultationFlowNodeContent\(values: ConsultationFormValues, stage: string\): ConsultationFormValues/);
  assert.match(source, /clearConsultationFlowNodeContent\(current, stage\)/);
  assert.match(source, /clearConsultationFlowNodeContent\(toConsultationFormValues\(record\), stage\)/);
});

test('default follow up status does not infer the communication stage as completed', () => {
  assert.match(source, /follow_up_status: '待邀约',/);
  assert.match(source, /function deriveConsultationFlowFromFields\(values: ConsultationFormValues\): ConsultationFormValues/);
  assert.match(source, /const hasSavedCommunicationStage = values\.completed_stages\.includes\('正在沟通细节'\) \|\| values\.flow_stage === '正在沟通细节';/);
  assert.match(source, /if \(hasSavedCommunicationStage \|\| values\.follow_up_note\.trim\(\)\) inferred\.add\('正在沟通细节'\);/);
  assert.doesNotMatch(source, /if \(values\.follow_up_status \|\| values\.follow_up_note\.trim\(\)\) inferred\.add\('正在沟通细节'\);/);
});

test('consultation read-only report shows receiving teacher as checked status text', () => {
  assert.match(source, /const ConsultationReadOnlyReport = \(/);
  assert.match(source, /接待教师：\{value\(form\.receiving_teacher\)\}/);
  assert.match(source, /receivingTeacherDone \? <CheckCircle2 size=\{14\}/);
  assert.doesNotMatch(source, /<p className=\{compactReadLabelClass\}>咨询老师<\/p><p className=\{compactReadValueClass\}>\{value\(form\.receiving_teacher\)\}<\/p>/);
});

test('consultation edit modal shows trial and teaching teacher status cards', () => {
  assert.ok(modalBlock);
  assert.match(modalBlock[0], /试听教师：\{form\.trial_teacher\.trim\(\) \|\| '未选择'\}/);
  assert.match(modalBlock[0], /form\.trial_teacher\.trim\(\) \? <CheckCircle2 size=\{16\}/);
  assert.match(modalBlock[0], /带课教师：\{form\.teaching_teacher\.trim\(\) \|\| '未选择'\}/);
  assert.match(modalBlock[0], /form\.teaching_teacher\.trim\(\) \? <CheckCircle2 size=\{16\}/);
});

test('consultation edit modal builds its own teacher directory for flow markers', () => {
  assert.ok(modalBlock);
  assert.match(modalBlock[0], /const teacherDirectory = buildConsultationTeacherDirectory\(record \? \[record\] : \[], consultationTeachers\);/);
  assert.match(modalBlock[0], /stageTeacherMarkers=\{buildConsultationStageTeacherMarkersFromValues\(form, teacherDirectory\)\}/);
});

test('setting an earlier current node clears later node form fields', () => {
  assert.match(source, /function clearConsultationFlowNodeMappedFields\(values: ConsultationFormValues, stage: string\): ConsultationFormValues/);
  assert.match(source, /function clearConsultationFlowNodeContentAfterStage\(values: ConsultationFormValues, stage: string\): ConsultationFormValues/);
  assert.match(source, /consultationProcessStages\.slice\(targetIndex \+ 1\)/);
  assert.match(source, /clearConsultationFlowNodeMappedFields\(nextValues, nextStage\)/);
  assert.match(source, /clearConsultationFlowNodeContentAfterStage\(nextValues, stage\)/);
});

test('setting an earlier current node clears stale later assignment metadata', () => {
  assert.match(source, /const assignedStageIndex = consultationProcessStages\.indexOf\(values\.assigned_stage as DomainConsultationProcessStage\);/);
  assert.match(source, /if \(assignedStageIndex > targetIndex\) \{/);
  assert.match(source, /clearedValues\.assigned_stage = '';/);
  assert.match(source, /clearedValues\.assignment_note = '';/);
});

test('consultation edit modal opens ordinary node dialog and restores over result dialog', () => {
  assert.ok(modalBlock);
  assert.match(modalBlock[0], /flowNodeDialog/);
  assert.match(modalBlock[0], /openFlowNodeDialog/);
  assert.match(modalBlock[0], /overResultDialogOpen/);
  assert.match(modalBlock[0], /<ConsultationFlowNodeDialog/);
  assert.match(modalBlock[0], /onStageClick=\{\(nextStage\) => openFlowNodeDialog\(nextStage, false\)\}/);
  assert.match(modalBlock[0], /onStageContextMenu=\{\(nextStage\) => openFlowNodeDialog\(nextStage, true\)\}/);
  assert.match(modalBlock[0], /setOverResultDialogOpen\(true\)/);
  assert.match(modalBlock[0], /applyConsultationOverFailureValues/);
  assert.doesNotMatch(modalBlock[0], /onStageDoubleClick/);
});

test('consultation cards open ordinary node dialog and directly cancel lit nodes', () => {
  assert.ok(pageBlock);
  assert.match(pageBlock[0], /flowNodeDialog/);
  assert.match(pageBlock[0], /openInlineFlowNodeDialog/);
  assert.match(pageBlock[0], /handleSaveInlineFlowNodeDialog/);
  assert.match(pageBlock[0], /overResultDialogRecord/);
  assert.match(pageBlock[0], /<ConsultationFlowNodeDialog/);
  assert.match(pageBlock[0], /getConsultationFlowLightColor\(toConsultationFormValues\(record\), stage\)/);
  assert.match(pageBlock[0], /clearConsultationFlowNodeContent\(toConsultationFormValues\(record\), stage\)/);
  assert.match(pageBlock[0], /applyConsultationOverFailureValues/);
});
