import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const sharedSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/consultationShared.tsx'), 'utf8');
const pageSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationPage.tsx'), 'utf8');
const modalSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationModal.tsx'), 'utf8');

test('modular consultation flow UI imports and uses pure flow transition helpers', () => {
  assert.match(sharedSource, /from '\.\.\/\.\.\/domain\/consultationFlow'/);
  assert.match(sharedSource, /completeConsultationStage as completeConsultationFlowStage/);
  assert.match(sharedSource, /cancelConsultationStage as cancelConsultationFlowStage/);
  assert.match(sharedSource, /setConsultationCurrentStage as setConsultationFlowCurrentStage/);
  assert.match(sharedSource, /calculateConsultationFlowLights/);
});

test('modular consultation flow bar uses right click and long press instead of double click', () => {
  assert.match(sharedSource, /onStageContextMenu/);
  assert.match(sharedSource, /onStageLongPress/);
  assert.match(sharedSource, /longPressTimerRef/);
  assert.match(sharedSource, /longPressTriggeredRef/);
  assert.match(sharedSource, /onContextMenu=\{handlePrimaryContextMenu\}/);
  assert.match(sharedSource, /onTouchStart=\{handlePrimaryTouchStart\}/);
  assert.match(sharedSource, /onTouchEnd=\{handlePrimaryTouchEnd\}/);
  assert.match(sharedSource, /onTouchCancel=\{clearLongPressTimer\}/);
  assert.doesNotMatch(sharedSource, /onStageDoubleClick/);
  assert.doesNotMatch(sharedSource, /onDoubleClick=\{handlePrimaryDoubleClick\}/);
});

test('consultation list cards wire stage click, right click, long press, and over handlers', () => {
  assert.match(pageSource, /handleInlineStageClick/);
  assert.match(pageSource, /handleInlineStageCurrent/);
  assert.match(pageSource, /onStageClick=\{\(stage\) => handleInlineStageClick\(record, stage\)\}/);
  assert.match(pageSource, /onStageContextMenu=\{\(stage\) => handleInlineStageCurrent\(record, stage\)\}/);
  assert.match(pageSource, /onStageLongPress=\{\(stage\) => handleInlineStageCurrent\(record, stage\)\}/);
  assert.match(pageSource, /onOverClick=\{\(\) => handleInlineEndConsultation\(record\)\}/);
  assert.doesNotMatch(pageSource, /onStageDoubleClick/);
});

test('consultation edit modal wires stage click, right click, and long press without double click', () => {
  assert.match(modalSource, /onStageClick=\{\(nextStage\) => openFlowNodeDialog\(nextStage, false\)\}/);
  assert.match(modalSource, /onStageContextMenu=\{\(nextStage\) => openFlowNodeDialog\(nextStage, true\)\}/);
  assert.match(modalSource, /onStageLongPress=\{\(nextStage\) => openFlowNodeDialog\(nextStage, true\)\}/);
  assert.match(modalSource, /getConsultationFlowLightColor\(form, stage\)/);
  assert.match(modalSource, /clearConsultationFlowNodeContent\(current, stage\)/);
  assert.doesNotMatch(modalSource, /onStageDoubleClick/);
});

test('consultation flow bar derives green, blue, red, and white from pure light colors', () => {
  assert.match(sharedSource, /const flowState = createConsultationFlowState/);
  assert.match(sharedSource, /calculateConsultationFlowLights\(flowState\)/);
  assert.match(sharedSource, /lightByStage/);
  assert.match(sharedSource, /lightColor === 'blue'/);
  assert.match(sharedSource, /lightColor === 'green'/);
  assert.match(sharedSource, /lightColor === 'red'/);
  assert.match(sharedSource, /return 'border-\[#C7DDEA\] bg-white text-transparent/);
});

test('consultation page list cards let the flow bar be the only status light source', () => {
  assert.doesNotMatch(pageSource, /ConsultationStatusLamp/);
  assert.doesNotMatch(pageSource, /grid-cols-\[0\.875rem_minmax\(0,1fr\)\]/);
  assert.match(pageSource, /renderB3FlowStrip\(record, busy\)/);
  assert.match(pageSource, /renderB3FlowStrip\(record, busy, true\)/);
});

test('consultation flow connector only paints blue into the current stage from the completed left side', () => {
  assert.match(sharedSource, /if \(node\.completed && next\.active\) return 'bg-\[#0EA5E9\]';/);
  assert.doesNotMatch(sharedSource, /node\.active \|\| next\.active/);
});

test('consultation flow lamps use saved teacher initials instead of stage short labels', () => {
  assert.match(sharedSource, /buildConsultationFlowStageTeacherLabels/);
  assert.match(sharedSource, /getConsultationTeacherInitial/);
  assert.match(sharedSource, /stageTeacherLabels\?: Record<string, string>/);
  assert.match(sharedSource, /teacherLabel: stageTeacherLabels\?\.\[item\] \|\| ''/);
  assert.match(sharedSource, /const circleText = node\.type === 'over'/);
  assert.match(sharedSource, /node\.teacherLabel/);
  assert.doesNotMatch(sharedSource, /node\.active\s*\?\s*node\.shortLabel\s*:\s*node\.completed\s*\?\s*'✓'/);
  assert.match(pageSource, /stageTeacherLabels=\{buildConsultationFlowStageTeacherLabels\(toConsultationFormValues\(record\)\)\}/);
  assert.match(modalSource, /stageTeacherLabels=\{buildConsultationFlowStageTeacherLabels\(form\)\}/);
});

test('consultation flow surfaces explain card immediate save and modal draft save semantics', () => {
  assert.match(pageSource, /主页卡片：流程操作会立即保存/);
  assert.match(pageSource, /hidden xl:inline/);
  assert.match(pageSource, /左键编辑阶段状态，右键标记为当前阶段/);
  assert.match(pageSource, /xl:hidden/);
  assert.match(pageSource, /轻点编辑阶段状态，长按标记为当前阶段/);
  assert.doesNotMatch(pageSource, /电脑右键、Pad\/手机长按/);
  assert.match(pageSource, /saveInlineConsultationUpdate\(record, values, '更新咨询流程失败'\)/);
  assert.match(modalSource, /编辑弹窗：流程操作先进入草稿/);
  assert.match(modalSource, /setForm\(\(current\) => applyConsultationFlowNodeDraft\(current, flowNodeDialog\.stage, draft, flowNodeDialog\.setAsCurrent\)\)/);
  assert.match(modalSource, /formScrollRef\.current\?\.requestSubmit\(\)/);
});

test('consultation cards use the shared flow bar instead of legacy mobile timeline rendering', () => {
  assert.doesNotMatch(pageSource, /renderB3MobileTimeline/);
  assert.doesNotMatch(pageSource, /item\.active \? \(item\.key === 'consultation-result' \? '☀' : item\.label\) : item\.completed \? '✓' : ''/);
  assert.match(pageSource, /const renderB3FlowStrip = \(record: ConsultationRecord, busy: boolean, mobile = false\) =>/);
  assert.match(pageSource, /return renderInlineFlow\(record, busy\);/);
  assert.match(pageSource, /renderB3FlowStrip\(record, busy, true\)/);
});

test('consultation page defaults to pending consultations when no specific filter is selected', () => {
  assert.match(pageSource, /const \[activeFilter, setActiveFilter\] = useState<ConsultationFilterKey \| null>\(null\)/);
  assert.match(pageSource, /if \(!activeFilter\) \{\s*return sortConsultationsForFilter\(\s*records\.filter\(\(record\) => getConsultationFilterKey\(record, consultationTodayIso\)\.startsWith\('pending-'\)\),\s*'pending-7',\s*\);\s*\}/);
});

test('consultation over actions are explicit success or failure choices instead of silent close', () => {
  assert.match(sharedSource, /closing_result/);
  assert.match(sharedSource, /completeConsultationOver/);
  assert.match(sharedSource, /cancelConsultationOver/);
  assert.match(pageSource, /overResultDialogRecord/);
  assert.match(pageSource, /handleInlineOverSuccess/);
  assert.match(pageSource, /handleInlineOverFailure/);
  assert.match(modalSource, /overResultDialogOpen/);
  assert.match(modalSource, /咨询成功/);
  assert.match(modalSource, /咨询失败/);
  assert.doesNotMatch(modalSource, /setForm\(\(current\) => endConsultationValues\(current\)\)/);
});

test('consultation flow bar never renders two blue lights across process result and over nodes', () => {
  assert.match(sharedSource, /const flowStateStage = ended\s*\?\s*consultationOverStage/);
  assert.match(sharedSource, /resultActive\s*\?\s*consultationOverStage/);
  assert.match(sharedSource, /currentStage === '试听失败'[\s\S]*\? 'failed'/);
  assert.match(sharedSource, /lightColor === 'blue'[\s\S]*border-\[#0EA5E9\] bg-\[#0EA5E9\] text-white/);
  assert.match(sharedSource, /lightColor === 'red'[\s\S]*border-\[#E11D48\] bg-\[#E11D48\] text-white/);
  assert.match(sharedSource, /ring-2 ring-rose-100/);
  assert.doesNotMatch(sharedSource, /if \(lightColor === 'red'\) \{\s*return 'border-\[#F43F5E\] bg-white text-transparent/);
});
