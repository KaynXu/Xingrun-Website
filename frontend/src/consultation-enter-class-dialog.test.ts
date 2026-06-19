import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const modalSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationModal.tsx'), 'utf8');
const pageSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationPage.tsx'), 'utf8');
const enterClassDialogSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationEnterClassDialog.tsx'), 'utf8');

function extractConstHandler(source: string, handlerName: string): string {
  const start = source.indexOf(`const ${handlerName} =`);
  assert.notEqual(start, -1, `${handlerName} should exist`);
  const nextHandler = source.indexOf('\n\n  const ', start + 1);
  return source.slice(start, nextHandler === -1 ? undefined : nextHandler);
}

test('consultation enter class dialog restores the three card actions', () => {
  assert.match(enterClassDialogSource, /ConsultationEnterClassDialog/);
  assert.match(enterClassDialogSource, /已有班级/);
  assert.match(enterClassDialogSource, /快速建班/);
  assert.match(enterClassDialogSource, /转化待进班/);
  assert.match(modalSource, /setEnterClassDialogOpen\(true\)/);
});

test('consultation enter class dialog filters class select and uses student center create payload', () => {
  assert.match(enterClassDialogSource, /consultation_subject/);
  assert.match(enterClassDialogSource, /subjectFilter/);
  assert.match(enterClassDialogSource, /stageFilter/);
  assert.match(enterClassDialogSource, /gradeFilter/);
  assert.match(modalSource, /buildConsultationQuickClassSavePayload/);
  assert.doesNotMatch(modalSource, /buildClassSavePayload/);
  assert.match(modalSource, /apiFetch<ClassItem>\('\/api\/classes'/);
  assert.match(modalSource, /setLocalClasses\(\(current\) => \[/);
});

test('consultation enter class dialog uses student-center floating filters for existing classes', () => {
  assert.match(enterClassDialogSource, /buildConsultationClassFilterDefaults/);
  assert.match(enterClassDialogSource, /filterConsultationStudentCenterClasses/);
  assert.match(enterClassDialogSource, /FloatingFilterBar/);
  assert.match(enterClassDialogSource, /buildClassFilterItems/);
  assert.match(enterClassDialogSource, /resolveActiveClassFilterOptions/);
  assert.match(enterClassDialogSource, /existingClassFilterItems/);
  assert.match(enterClassDialogSource, /existingClassFilterSummary/);
  assert.match(enterClassDialogSource, /teacherFilter/);
  assert.match(enterClassDialogSource, /classTypeFilter/);
  assert.match(enterClassDialogSource, /类型：/);
  assert.match(enterClassDialogSource, /小课/);
  assert.match(enterClassDialogSource, /班课/);
  assert.doesNotMatch(enterClassDialogSource, /<select value=\{subjectFilter\}/);
  assert.doesNotMatch(enterClassDialogSource, /<select value=\{teacherFilter\}/);
  assert.doesNotMatch(enterClassDialogSource, /<select value=\{stageFilter\}/);
  assert.doesNotMatch(enterClassDialogSource, /<select value=\{gradeFilter\}/);
  assert.doesNotMatch(enterClassDialogSource, /<select value=\{classTypeFilter\}/);
});

test('consultation existing class picker uses a hoverable custom list only for class selection', () => {
  assert.match(enterClassDialogSource, /classPickerOpen/);
  assert.match(enterClassDialogSource, /role="listbox"/);
  assert.match(enterClassDialogSource, /hover:bg-sky-50/);
  assert.match(enterClassDialogSource, /没有匹配的班级/);
  assert.doesNotMatch(enterClassDialogSource, /<select value=\{selectedClassId\}/);
  assert.match(enterClassDialogSource, /if \(mode === 'create'\) void onCreateClass\(createDraft\);/);
  assert.match(enterClassDialogSource, /if \(mode === 'pending'\) onPending\(\);/);
});

test('consultation quick-create UI uses student-center class form field names', () => {
  assert.match(enterClassDialogSource, /createDraft\.class_type/);
  assert.match(enterClassDialogSource, /createDraft\.current_grade/);
  assert.match(enterClassDialogSource, /createDraft\.class_number/);
  assert.match(enterClassDialogSource, /createDraft\.is_bridge/);
  assert.match(enterClassDialogSource, /createDraft\.bridge_target/);
  assert.doesNotMatch(enterClassDialogSource, /createDraft\.currentGrade/);
  assert.doesNotMatch(enterClassDialogSource, /createDraft\.classType/);
  assert.doesNotMatch(enterClassDialogSource, /createDraft\.classNumber/);
  assert.doesNotMatch(enterClassDialogSource, /createDraft\.isBridge/);
  assert.doesNotMatch(enterClassDialogSource, /createDraft\.bridgeTarget/);
});

test('consultation modal recommends a real teacher id for enter-class filtering', () => {
  assert.match(modalSource, /consultationEnterClassTeacherUserId/);
  assert.match(modalSource, /teachingTeacherUserId=\{consultationEnterClassTeacherUserId\}/);
  assert.match(modalSource, /form\.teaching_teacher_user_id \?\? null/);
  assert.doesNotMatch(modalSource, /selectedTeachingTeacherUserId/);
  assert.doesNotMatch(modalSource, /consultationEnterClassTeacherUserId = [^;]*currentUser\.id/);
});

test('consultation modal passes the full class pool and only recommends teacher filtering', () => {
  assert.match(modalSource, /const successClassOptions = localClasses;/);
  assert.doesNotMatch(modalSource, /teachingTeacherMatchedClasses/);
  assert.doesNotMatch(modalSource, /localClasses\.filter\(\(item\) => item\.teacher_user_id === consultationEnterClassTeacherUserId\)/);
  assert.doesNotMatch(modalSource, /classes=\{teachingTeacherMatchedClasses\}/);
  assert.doesNotMatch(modalSource, /const successClassOptions = selectedTeachingTeacher \? teachingTeacherMatchedClasses : assignableClassOptions/);
});

test('consultation modal keeps quick-created class teacher id and name consistent', () => {
  assert.match(modalSource, /quickClassTeacherUserId/);
  assert.match(modalSource, /selectedTeacherUserId: quickClassTeacherUserId/);
  assert.doesNotMatch(modalSource, /buildConsultationClassUser\(currentUser, form\.teaching_teacher \|\| form\.trial_teacher \|\| form\.receiving_teacher\)/);
});

test('consultation quick-create validates through student-center adapter before posting classes', () => {
  const modalCreateHandlerSource = extractConstHandler(modalSource, 'handleCreateSuccessClass');
  const pageCreateHandlerSource = extractConstHandler(pageSource, 'handleInlineEnterCreateClass');

  assert.match(modalSource, /validateConsultationQuickClassForm/);
  assert.match(pageSource, /validateConsultationQuickClassForm/);
  assert.match(modalCreateHandlerSource, /validateConsultationQuickClassForm/);
  assert.match(modalCreateHandlerSource, /setSuccessClassCreateError\(validationError\)/);
  assert.match(pageCreateHandlerSource, /validateConsultationQuickClassForm/);
  assert.match(pageCreateHandlerSource, /setInlineEnterClassError\(validationError\)/);
});

test('consultation page inline quick-create creates a class through class API before entering existing class', () => {
  const pageCreateHandlerSource = extractConstHandler(pageSource, 'handleInlineEnterCreateClass');

  assert.match(pageSource, /buildConsultationQuickClassSavePayload/);
  assert.match(pageCreateHandlerSource, /apiFetch<ClassItem>\('\/api\/classes'/);
  assert.match(pageCreateHandlerSource, /setClasses\(\(current\) => \[createdClass/);
  assert.match(pageCreateHandlerSource, /buildConsultationEnterClassPayload\(\{\s*mode: 'existing'/);
  assert.doesNotMatch(pageCreateHandlerSource, /mode: 'quick-create'/);
  assert.doesNotMatch(pageCreateHandlerSource, /quickClassDraft/);
});

test('consultation page inline quick-create keeps fallback teacher id and name paired', () => {
  const pageCreateHandlerSource = extractConstHandler(pageSource, 'handleInlineEnterCreateClass');

  assert.match(pageCreateHandlerSource, /inlineEnterClassRecord\.teaching_teacher_user_id != null/);
  assert.match(pageCreateHandlerSource, /inlineEnterClassRecord\.teaching_teacher \|\| inlineEnterClassRecord\.trial_teacher \|\| inlineEnterClassRecord\.receiving_teacher/);
  assert.match(pageCreateHandlerSource, /currentUser\.display_name \|\| currentUser\.username/);
  assert.doesNotMatch(
    pageCreateHandlerSource,
    /name: inlineEnterClassRecord\.teaching_teacher \|\| inlineEnterClassRecord\.trial_teacher \|\| inlineEnterClassRecord\.receiving_teacher \|\| currentUser\.display_name \|\| currentUser\.username/,
  );
});

test('consultation enter class dialog reset depends on stable value fields', () => {
  assert.match(enterClassDialogSource, /values\.consultation_subject,\s*values\.grade,\s*values\.success_class_id/s);
  assert.doesNotMatch(enterClassDialogSource, /\[open, teachingTeacherUserId, values\]/);
  assert.doesNotMatch(enterClassDialogSource, /Legacy recommendation shape/);
  assert.doesNotMatch(enterClassDialogSource, /former resolveConsultationAssignableClasses/);
  assert.doesNotMatch(enterClassDialogSource, /sourceStructureCompatibility/);
});

test('consultation enter class success writes selected or created class into form and over result', () => {
  assert.match(modalSource, /handleConfirmExistingClass/);
  assert.match(modalSource, /handleCreateSuccessClass/);
  assert.match(modalSource, /handleMarkPendingSuccessClass/);
  assert.match(modalSource, /setConsultationResultStage\(next, '成功进班'\)/);
  assert.match(modalSource, /success_class_manual: '转化待进班'/);
});

test('consultation page result and over success open enter-class dialog instead of requiring a preselected class', () => {
  assert.match(pageSource, /inlineEnterClassRecord/);
  assert.match(pageSource, /<ConsultationEnterClassDialog/);
  assert.match(pageSource, /setInlineEnterClassRecord\(record\)/);
  assert.match(pageSource, /handleInlineEnterExistingClass/);
  assert.match(pageSource, /handleInlineEnterCreateClass/);
  assert.match(pageSource, /handleInlineEnterPendingClass/);
  assert.doesNotMatch(pageSource, /成功进班必须先选择或填写班级。/);
  assert.doesNotMatch(pageSource, /咨询成功必须先选择或填写班级。/);
});

test('consultation enter class dialog lives outside the oversized modal file', () => {
  assert.match(modalSource, /import \{ ConsultationEnterClassDialog \} from '\.\/ConsultationEnterClassDialog';/);
  assert.doesNotMatch(modalSource, /export const ConsultationEnterClassDialog =/);
});
