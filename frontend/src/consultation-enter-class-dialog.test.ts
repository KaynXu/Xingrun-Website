import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
const enterClassBlock = source.match(/const ConsultationEnterClassDialog = \([\s\S]*?\n};/);
const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);
const pageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);

test('enter-class dialog restores the three-card shell and submits business payloads', () => {
  assert.ok(enterClassBlock);
  assert.match(enterClassBlock[0], /已有班级/);
  assert.match(enterClassBlock[0], /快速建班/);
  assert.match(enterClassBlock[0], /转化待进班/);
  assert.match(enterClassBlock[0], /enterClassMode/);
  assert.match(enterClassBlock[0], /onSubmit/);
  assert.match(enterClassBlock[0], /buildConsultationEnterClassPayload/);
  assert.match(enterClassBlock[0], /mode: 'existing'/);
  assert.match(enterClassBlock[0], /mode: 'quick-create'/);
  assert.match(enterClassBlock[0], /mode: 'pending'/);
});

test('enter-class dialog includes compact class creation fields and class-name preview', () => {
  assert.ok(enterClassBlock);
  assert.match(enterClassBlock[0], /class_type/);
  assert.match(enterClassBlock[0], /consultation_subject/);
  assert.match(enterClassBlock[0], /studentCenterStageOptions/);
  assert.match(enterClassBlock[0], /current_grade/);
  assert.match(enterClassBlock[0], /class_number/);
  assert.match(enterClassBlock[0], /is_bridge/);
  assert.match(enterClassBlock[0], /bridge_target/);
  assert.match(enterClassBlock[0], /修改之后的班名预览/);
  assert.match(enterClassBlock[0], /buildClassDisplayName/);
});

test('consultation result click opens enter-class dialog in edit modal and list card', () => {
  assert.ok(modalBlock);
  assert.match(modalBlock[0], /enterClassDialogOpen/);
  assert.match(modalBlock[0], /<ConsultationEnterClassDialog/);
  assert.match(modalBlock[0], /onResultClick=\{\(\) => \{/);
  assert.match(modalBlock[0], /setEnterClassDialogOpen\(true\)/);

  assert.ok(pageBlock);
  assert.match(pageBlock[0], /enterClassDialogRecord/);
  assert.match(pageBlock[0], /<ConsultationEnterClassDialog/);
  assert.match(pageBlock[0], /setEnterClassDialogRecord\(record\)/);
});

test('successful result dropdown uses the enter-class dialog instead of direct success save', () => {
  assert.ok(modalBlock);
  assert.match(modalBlock[0], /onResultChange=\{\(nextStage\) => \{/);
  assert.match(modalBlock[0], /if \(nextStage === '成功进班'\) \{[\s\S]*setEnterClassDialogOpen\(true\);[\s\S]*return;/);

  assert.ok(pageBlock);
  assert.match(pageBlock[0], /if \(resultStage === '成功进班'\) \{[\s\S]*setEnterClassDialogRecord\(record\);[\s\S]*return;/);
  assert.doesNotMatch(pageBlock[0], /resultStage === '成功进班' && !record\.success_class_id/);
});

test('enter-class dialog confirmation copy now claims business completion', () => {
  assert.ok(enterClassBlock);
  assert.match(enterClassBlock[0], /确认进班/);
});

test('consultation page submits enter-class selection through the dedicated business endpoint', () => {
  assert.ok(pageBlock);
  assert.match(pageBlock[0], /handleSubmitInlineEnterClass/);
  assert.match(pageBlock[0], /apiFetch<\{ item: ConsultationRecord; class_id/);
  assert.match(pageBlock[0], /`\/api\/consultations\/\$\{record\.id\}\/enter-class`/);
  assert.match(pageBlock[0], /setEnterClassDialogRecord\(null\)/);
  assert.match(pageBlock[0], /await load\(search\)/);
});

test('enter-class dialog keeps consultation subject and grade as editable recommendations', () => {
  assert.ok(enterClassBlock);
  assert.match(enterClassBlock[0], /buildRecommendedConsultationClassFilters/);
  assert.match(enterClassBlock[0], /existingClassFilters/);
  assert.match(enterClassBlock[0], /setExistingClassFilters/);
  assert.match(enterClassBlock[0], /全部学科/);
  assert.match(enterClassBlock[0], /全部学段/);
  assert.match(enterClassBlock[0], /放宽筛选/);
  assert.match(enterClassBlock[0], /filterConsultationEnterClassOptions\(\{[\s\S]*filters: existingClassFilters,[\s\S]*\}\);/);
});

test('enter-class dialog captures teaching teacher handoff in submitted payload', () => {
  assert.ok(enterClassBlock);
  assert.match(enterClassBlock[0], /teacherOptions/);
  assert.match(enterClassBlock[0], /teachingTeacherId/);
  assert.match(enterClassBlock[0], /带课教师/);
  assert.match(enterClassBlock[0], /teachingTeacherHandoff/);
  assert.match(enterClassBlock[0], /teachingTeacherName/);
  assert.match(enterClassBlock[0], /teachingTeacherUserId/);
  assert.match(modalBlock?.[0] || '', /teacherOptions=\{consultationTeachers\}/);
  assert.match(pageBlock?.[0] || '', /teacherOptions=\{consultationTeachers\}/);
});

test('create modal enter-class saves through real consultation then enter-class endpoint', () => {
  assert.ok(modalBlock);
  assert.match(modalBlock[0], /apiFetch<ConsultationRecord>\('\/api\/consultations'/);
  assert.match(modalBlock[0], /createdRecord\.id/);
  assert.match(modalBlock[0], /`\/api\/consultations\/\$\{createdRecord\.id\}\/enter-class`/);
  assert.match(modalBlock[0], /const normalized = normalizeConsultationRecord\(result\.item\)/);
  assert.match(modalBlock[0], /onEnteredClass\?\.\(normalized\)/);
});
