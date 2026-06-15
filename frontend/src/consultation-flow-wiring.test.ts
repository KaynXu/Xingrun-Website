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

test('consultation flow bar treats result-stage transfer as after all process nodes', () => {
  assert.ok(flowBarBlock);
  assert.match(flowBarBlock[0], /const editableFromStageIndex = editableFromStage/);
  assert.match(flowBarBlock[0], /isConsultationResultStage\(editableFromStage\)\s*\?\s*consultationProcessStages\.length/);
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
  assert.match(modalBlock[0], /const transferredLimitedEdit = Boolean\(transferredEditableFromStage\);/);
  assert.match(modalBlock[0], /const transferredEditableFromStageIndex = transferredEditableFromStage/);
  assert.match(modalBlock[0], /isConsultationResultStage\(transferredEditableFromStage\)\s*\?\s*consultationProcessStages\.length/);
  assert.match(modalBlock[0], /const isTransferredStageLockedBefore = \(stageName: string\) =>/);
  assert.match(modalBlock[0], /const canEditConsultationStageFields = \(stageName: string\) => !readOnly && !stageFrozen && !isTransferredStageLockedBefore\(stageName\);/);
  assert.match(modalBlock[0], /const baseFieldsDisabled = readOnly \|\| transferredLimitedEdit;/);
  assert.match(modalBlock[0], /const communicationFieldsDisabled = readOnly \|\| isTransferredStageLockedBefore\('正在沟通细节'\);/);
  assert.match(modalBlock[0], /const testFieldsDisabled = !canEditConsultationStageFields\('待测试'\);/);
  assert.match(modalBlock[0], /const trialFieldsDisabled = !canEditConsultationStageFields\('待试听'\);/);
  assert.match(modalBlock[0], /const successFieldsDisabled = !canEditConsultationStageFields\('成功进班'\);/);
  assert.match(modalBlock[0], /disabled=\{baseFieldsDisabled\}/);
  assert.match(modalBlock[0], /disabled=\{communicationFieldsDisabled\}/);
  assert.match(modalBlock[0], /disabled=\{testFieldsDisabled\}/);
  assert.match(modalBlock[0], /disabled=\{trialFieldsDisabled\}/);
  assert.match(modalBlock[0], /disabled=\{successFieldsDisabled\}/);
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
  assert.match(flowBarBlock[0], /\(lightColor === 'green' \|\| lightColor === 'blue'\) \? stageTeacherMarkers\[item\]\?\.initial \|\| '' : ''/);
  assert.doesNotMatch(flowBarBlock[0], /node\.active\s*\?\s*node\.shortLabel/);
  assert.match(flowBarBlock[0], /border-emerald-200 bg-emerald-50 text-emerald-700/);
  assert.match(flowBarBlock[0], /border-dashed border-teal-300 bg-white text-teal-700/);
  assert.doesNotMatch(flowBarBlock[0], /if \(node\.type === 'process' && node\.teacherInitial\) return 'border-slate-200 bg-white text-slate-500/);
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

test('consultation page shows device-specific flow usage reminder with centered icon', () => {
  assert.match(source, /使用提醒/);
  assert.match(source, /电脑端：左键编辑阶段状态，右键标记为当前阶段。/);
  assert.match(source, /Pad\/手机：轻点编辑阶段状态，长按标记为当前阶段。/);
  assert.match(source, /hidden md:inline/);
  assert.match(source, /md:hidden/);
  assert.match(source, /items-center gap-2/);
  assert.doesNotMatch(source, /使用提醒：点击卡片右侧图标查看或编辑咨询记录。/);
});

test('consultation filter group keys stay unique when group titles are hidden', () => {
  assert.match(source, /consultationFilterGroups\.map\(\(group, groupIndex\) =>/);
  assert.match(source, /key=\{group\.title \|\| `consultation-filter-group-\$\{groupIndex\}`\}/);
  assert.doesNotMatch(source, /key=\{group\.title\}/);
});

test('consultation page has optional self-created and transferred source filters', () => {
  assert.match(source, /type ConsultationSourceFilterKey = 'self' \| 'transferred';/);
  assert.match(source, /const consultationSourceFilterOptions: Array<\{ key: ConsultationSourceFilterKey; label: string \}>/);
  assert.match(source, /\{ key: 'self', label: '自建咨询' \}/);
  assert.match(source, /\{ key: 'transferred', label: '转接咨询' \}/);
  assert.match(consultationPageBlock?.[0] || '', /const \[activeSourceFilter, setActiveSourceFilter\] = useState<ConsultationSourceFilterKey \| ''>\(''\);/);
  assert.match(source, /function consultationMatchesSourceFilter\(record: ConsultationRecord, sourceFilter: ConsultationSourceFilterKey \| ''\): boolean/);
  assert.match(source, /if \(sourceFilter === 'self'\) return !record\.is_transferred_consultation;/);
  assert.match(source, /if \(sourceFilter === 'transferred'\) return record\.is_transferred_consultation;/);
  assert.match(consultationPageBlock?.[0] || '', /consultationMatchesSourceFilter\(record, activeSourceFilter\)/);
  assert.match(consultationPageBlock?.[0] || '', /setActiveSourceFilter\(\(current\) => current === item\.key \? '' : item\.key\)/);
});

test('consultation list cards render saved stage teacher status chips', () => {
  assert.match(source, /function getConsultationCardStageStatusItems\(record: ConsultationRecord\)/);
  assert.match(source, /客服微信：已添加/);
  assert.match(source, /沟通教师：\$\{record\.communication_teacher_added\}/);
  assert.match(source, /测试教师：\$\{record\.test_teacher\}/);
  assert.match(source, /试听教师：\$\{record\.trial_teacher\}/);
  assert.match(source, /带课教师：\$\{record\.teaching_teacher\}/);
  assert.match(source, /const renderConsultationStageStatusChips = \(record: ConsultationRecord\)/);
  assert.match(source, /getConsultationCardStageStatusItems\(record\)/);
  assert.match(source, /<CheckCircle2 size=\{12\}/);
  assert.match(source, /renderConsultationStageStatusChips\(record\)/);
});
