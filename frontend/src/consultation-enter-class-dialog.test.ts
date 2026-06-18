import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const modalSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationModal.tsx'), 'utf8');
const pageSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationPage.tsx'), 'utf8');
const enterClassDialogSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationEnterClassDialog.tsx'), 'utf8');

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
  assert.match(modalSource, /buildClassSavePayload/);
  assert.match(modalSource, /apiFetch<ClassItem>\('\/api\/classes'/);
  assert.match(modalSource, /setLocalClasses\(\(current\) => \[/);
});

test('consultation enter class dialog exposes student-center style filters for existing classes', () => {
  assert.match(enterClassDialogSource, /buildConsultationClassFilterDefaults/);
  assert.match(enterClassDialogSource, /filterConsultationStudentCenterClasses/);
  assert.match(enterClassDialogSource, /teacherFilter/);
  assert.match(enterClassDialogSource, /classTypeFilter/);
  assert.match(enterClassDialogSource, /全部老师/);
  assert.match(enterClassDialogSource, /全部类型/);
  assert.match(enterClassDialogSource, /小课/);
  assert.match(enterClassDialogSource, /班课/);
});

test('consultation modal recommends a real teacher id for enter-class filtering', () => {
  assert.match(modalSource, /consultationEnterClassTeacherUserId/);
  assert.match(modalSource, /teachingTeacherUserId=\{consultationEnterClassTeacherUserId\}/);
  assert.match(modalSource, /form\.teaching_teacher_user_id \?\? null/);
  assert.doesNotMatch(modalSource, /selectedTeachingTeacherUserId/);
  assert.doesNotMatch(modalSource, /consultationEnterClassTeacherUserId = [^;]*currentUser\.id/);
});

test('consultation modal only prefilters success classes when teacher user id is reliable', () => {
  assert.match(modalSource, /const successClassOptions = consultationEnterClassTeacherUserId != null/);
  assert.match(modalSource, /\? teachingTeacherMatchedClasses/);
  assert.match(modalSource, /: assignableClassOptions/);
  assert.doesNotMatch(modalSource, /const successClassOptions = selectedTeachingTeacher \? teachingTeacherMatchedClasses : assignableClassOptions/);
});

test('consultation modal keeps quick-created class teacher id and name consistent', () => {
  assert.match(modalSource, /quickClassTeacherUserId/);
  assert.match(modalSource, /selectedTeacherUserId: quickClassTeacherUserId/);
  assert.doesNotMatch(modalSource, /buildConsultationClassUser\(currentUser, form\.teaching_teacher \|\| form\.trial_teacher \|\| form\.receiving_teacher\)/);
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
