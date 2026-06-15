import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
const flowBarBlock = source.match(/const ConsultationFlowBar = \([\s\S]*?\n};/);
const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);
const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);

test('consultation flow UI imports and uses pure flow transition helpers', () => {
  assert.match(source, /from '\.\/domain\/consultationFlow'/);
  assert.match(source, /completeConsultationStage as completeConsultationFlowStage/);
  assert.match(source, /cancelConsultationStage as cancelConsultationFlowStage/);
  assert.match(source, /setConsultationCurrentStage as setConsultationFlowCurrentStage/);
  assert.match(source, /function toggleConsultationFlowStageWithRules\(values: ConsultationFormValues, stage: string\): ConsultationFormValues/);
  assert.match(source, /function setConsultationFlowCurrentStageWithRules\(values: ConsultationFormValues, stage: string\): ConsultationFormValues/);
});

test('consultation flow bar distinguishes left click from right click and long press', () => {
  assert.ok(flowBarBlock);
  assert.match(flowBarBlock[0], /editableFromStage/);
  assert.match(flowBarBlock[0], /editableFromStageIndex/);
  assert.match(flowBarBlock[0], /stageIndex < editableFromStageIndex/);
  assert.match(flowBarBlock[0], /onStageContextMenu/);
  assert.match(flowBarBlock[0], /onStageLongPress/);
  assert.match(flowBarBlock[0], /const longPressTimerRef = useRef<ReturnType<typeof window\.setTimeout> \| null>\(null\);/);
  assert.match(flowBarBlock[0], /const longPressTriggeredRef = useRef\(false\);/);
  assert.match(flowBarBlock[0], /onContextMenu=\{\(event\) => \{/);
  assert.match(flowBarBlock[0], /event\.preventDefault\(\);/);
  assert.match(flowBarBlock[0], /onStageContextMenu\?\.\(node\.key\);/);
  assert.match(flowBarBlock[0], /window\.setTimeout\(\(\) => \{/);
  assert.match(flowBarBlock[0], /longPressTriggeredRef\.current = true;/);
  assert.match(flowBarBlock[0], /if \(longPressTriggeredRef\.current\) \{/);
  assert.match(flowBarBlock[0], /onStageLongPress\?\.\(node\.key\);/);
  assert.match(flowBarBlock[0], /onTouchStart=/);
  assert.match(flowBarBlock[0], /onTouchEnd=/);
  assert.doesNotMatch(flowBarBlock[0], /onStageDoubleClick/);
  assert.doesNotMatch(flowBarBlock[0], /onDoubleClick/);
});

test('consultation cards wire stage and over click handlers', () => {
  assert.ok(consultationPageBlock);
  assert.match(consultationPageBlock[0], /handleInlineStageClick/);
  assert.match(consultationPageBlock[0], /handleInlineStageCurrent/);
  assert.match(consultationPageBlock[0], /handleInlineEndConsultation/);
  assert.match(consultationPageBlock[0], /onStageClick=\{\(stage\) => handleInlineStageClick\(record, stage\)\}/);
  assert.match(consultationPageBlock[0], /onStageContextMenu=\{\(stage\) => handleInlineStageCurrent\(record, stage\)\}/);
  assert.match(consultationPageBlock[0], /onStageLongPress=\{\(stage\) => handleInlineStageCurrent\(record, stage\)\}/);
  assert.match(consultationPageBlock[0], /showOver/);
  assert.match(consultationPageBlock[0], /onOverClick=\{\(\) => handleInlineEndConsultation\(record\)\}/);
  assert.match(consultationPageBlock[0], /overResultDialogRecord/);
  assert.match(consultationPageBlock[0], /editableFromStage=\{record\.is_transferred_consultation \? record\.assigned_stage : ''\}/);
  assert.doesNotMatch(consultationPageBlock[0], /flowNodeActionRecord/);
});

test('consultation edit modal also limits transferred records to current responsibility stage onward', () => {
  assert.ok(modalBlock);
  assert.match(modalBlock[0], /const transferredEditableFromStage = record\?\.is_transferred_consultation && currentUser\.role === 'member' \? record\.assigned_stage : '';/);
  assert.match(modalBlock[0], /editableFromStage=\{transferredEditableFromStage\}/);
});

test('consultation flow bar colors over from closing result', () => {
  assert.ok(flowBarBlock);
  assert.match(flowBarBlock[0], /closingResult/);
  assert.match(flowBarBlock[0], /closingResult: closingResult === 'failed' \? 'failed' : ended \? 'success' : ''/);
  assert.match(flowBarBlock[0], /node\.type === 'over' && closingResult === 'failed'/);
  assert.match(flowBarBlock[0], /border-\[#0EA5E9\] bg-\[#0EA5E9\]/);
});

test('consultation flow bar can render light teacher initials inside process lamps', () => {
  assert.ok(flowBarBlock);
  assert.match(flowBarBlock[0], /stageTeacherMarkers/);
  assert.match(source, /function getConsultationTeacherInitial\(value: string\): string/);
  assert.match(flowBarBlock[0], /node\.teacherInitial/);
  assert.match(flowBarBlock[0], /const circleText = node\.type === 'process' \? node\.teacherInitial : node\.type === 'over' \? ''/);
  assert.doesNotMatch(flowBarBlock[0], /node\.active\s*\?\s*node\.shortLabel/);
  assert.match(flowBarBlock[0], /border-emerald-200 bg-emerald-50 text-emerald-700/);
  assert.match(flowBarBlock[0], /border-dashed border-teal-300 bg-white text-teal-700/);
  assert.match(flowBarBlock[0], /if \(node\.type === 'process' && node\.teacherInitial\) return 'border-slate-200 bg-white text-slate-500/);
  assert.match(consultationPageBlock?.[0] || '', /stageTeacherMarkers=\{buildConsultationStageTeacherMarkers\(record, teacherDirectory\)\}/);
});

test('consultation teacher initials use teacher directory and saved stage teacher names', () => {
  assert.match(source, /function buildConsultationTeacherDirectory\(\s*records: ConsultationRecord\[],\s*teacherOptions: ConsultationTeacherOption\[] = \[],/);
  assert.match(source, /for \(const option of teacherOptions\)/);
  assert.match(consultationPageBlock?.[0] || '', /const teacherDirectory = buildConsultationTeacherDirectory\(records, consultationTeachers\);/);
  assert.match(source, /function getConsultationStageTeacherName\(record: ConsultationRecord, stage: string\): string/);
  assert.match(source, /if \(stage === '待测试'\) return record\.test_teacher\?\.trim\(\) \|\| '';/);
  assert.match(source, /function getDefaultConsultationCustomerServiceTeacherName\(teacherDirectory: Record<string, string>\): string/);
  assert.match(source, /stage === '已加小客服微信'[\s\S]*getDefaultConsultationCustomerServiceTeacherName\(teacherDirectory\)/);
  assert.match(source, /for \(const stage of consultationProcessStages\)/);
  assert.match(source, /const teacherName = teacherDirectory\[normalizeTeacherLookupKey\(normalizedTeacherId\)\][\s\S]*\|\| stageTeacherName[\s\S]*\|\| normalizedTeacherId;/);
});

test('consultation customer-service initials keep temporary Lei fallback without teacher directory data', () => {
  assert.match(source, /function getDefaultConsultationCustomerServiceTeacherName\(teacherDirectory: Record<string, string>\): string/);
  assert.match(source, /teacherDirectory\[normalizeTeacherLookupKey\('雷老师'\)\][\s\S]*\|\| teacherDirectory\[normalizeTeacherLookupKey\('雷文浩'\)\][\s\S]*\|\| '雷老师'/);
});
