import {
  buildClassDisplayName,
  getAcademicStageFromGrade,
  inferAcademicCohortYear,
  inferAcademicCohortYearForStage,
  normalizeAcademicGradeLabel,
  normalizeClassNameInput,
  parseBridgeTarget,
  serializeBridgeTarget,
} from '../../domain/classNaming';
import type { ClassFormValues, ClassItem, UserItem } from './model';
import { getClassFormDirtySignature } from './model';

export type ExistingStudentOption = {
  id: number;
  name: string;
};

export type ClassSavePayload = {
  name: string;
  class_type: string;
  subject: string;
  grade: string;
  teacher_name: string;
  teacher_email: string;
  stage: string;
  current_grade: string;
  class_number: string;
  cohort_year: number;
  show_cohort_year: boolean;
  is_bridge: boolean;
  bridge_target: string;
  content_track: string;
  student_ids: number[];
  teacher_user_id?: number | null;
};

export function buildClassCreateRequest(payload: ClassSavePayload): {
  path: string;
  init: {
    method: 'POST';
    body: string;
  };
} {
  return {
    path: '/api/classes',
    init: {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  };
}

export function buildClassUpdateRequest(classId: number, payload: ClassSavePayload): {
  path: string;
  init: {
    method: 'PUT';
    body: string;
  };
} {
  return {
    path: `/api/classes/${classId}`,
    init: {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  };
}

export async function executeClassCreateRequest<TCreatedClass>(
  payload: ClassSavePayload,
  apiFetch: (path: string, init: { method: 'POST'; body: string }) => Promise<TCreatedClass>,
): Promise<TCreatedClass> {
  const request = buildClassCreateRequest(payload);
  return apiFetch(request.path, request.init);
}

export async function executeClassUpdateRequest(
  classId: number,
  payload: ClassSavePayload,
  apiFetch: (path: string, init: { method: 'PUT'; body: string }) => Promise<unknown>,
): Promise<void> {
  const request = buildClassUpdateRequest(classId, payload);
  await apiFetch(request.path, request.init);
}

export function resolveClassSaveRefreshErrorMessage(classId: number | 'new', error: Error): string {
  return classId === 'new'
    ? `班级和负责老师已保存，但列表刷新失败：${error.message}`
    : `班级已保存，但列表刷新失败：${error.message}`;
}

export function resolveClassSaveErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '班级保存失败';
}

export function resolveCreatedClassTeacherBindingErrorMessage(error: unknown): string {
  return error instanceof Error
    ? `班级已创建，但负责老师绑定失败：${error.message}`
    : '班级已创建，但负责老师绑定失败，请在班级卡片中重新选择老师';
}

export function buildOptimisticCreatedClassItem({
  createdClassId,
  payload,
  selectedTeacher,
  selectedTeacherUserId,
}: {
  createdClassId: number;
  payload: ClassSavePayload;
  selectedTeacher?: UserItem;
  selectedTeacherUserId: number | null;
}): ClassItem {
  return {
    id: createdClassId,
    name: payload.name,
    class_type: payload.class_type,
    subject: payload.subject,
    grade: payload.grade,
    stage: payload.stage,
    current_grade: payload.current_grade,
    class_number: payload.class_number,
    cohort_year: payload.cohort_year,
    show_cohort_year: payload.show_cohort_year,
    is_bridge: payload.is_bridge,
    bridge_target: payload.bridge_target,
    content_track: payload.content_track,
    teacher_name: selectedTeacher?.name || '',
    teacher_email: '',
    teacher_user_id: selectedTeacherUserId,
  };
}

export function resolveClassesAfterOptimisticCreate(
  currentClasses: ClassItem[],
  optimisticCreatedClass: ClassItem,
): ClassItem[] {
  const remaining = currentClasses.filter((item) => item.id !== optimisticCreatedClass.id);
  return [...remaining, optimisticCreatedClass];
}

export function resolveTeacherBindingsAfterOptimisticCreate(
  currentTeacherBindingByClassId: Record<number, number | null>,
  createdClassId: number,
  selectedTeacherUserId: number | null,
): Record<number, number | null> {
  return {
    ...currentTeacherBindingByClassId,
    [createdClassId]: selectedTeacherUserId,
  };
}

export function resolveFormsAfterOptimisticCreate(
  currentFormByClassId: Record<string, ClassFormValues>,
  createdClassId: number,
  createdClassForm: ClassFormValues,
): Record<string, ClassFormValues> {
  return {
    ...currentFormByClassId,
    [String(createdClassId)]: createdClassForm,
  };
}

export function resolveFormsAfterCreateDraftReset(
  currentFormByClassId: Record<string, ClassFormValues>,
  emptyClassForm: ClassFormValues,
): Record<string, ClassFormValues> {
  return {
    ...currentFormByClassId,
    new: emptyClassForm,
  };
}

export function resolveNewClassTeacherAfterCreate(): null {
  return null;
}

export function resolveExpandedClassAfterOptimisticCreate(createdClassId: number): number {
  return createdClassId;
}

export function resolveClassFormDraftDirty({
  classId,
  currentForm,
  savedForm,
  newClassTeacherUserId,
  currentTeacherUserId,
  savedTeacherUserId,
  currentStudentIds,
  savedStudentIds,
}: {
  classId: number | 'new';
  currentForm: ClassFormValues;
  savedForm: ClassFormValues | null;
  newClassTeacherUserId: number | null;
  currentTeacherUserId?: number | null;
  savedTeacherUserId?: number | null;
  currentStudentIds?: number[];
  savedStudentIds?: number[];
}): boolean {
  if (!savedForm) {
    return false;
  }
  if (getClassFormDirtySignature(currentForm) !== getClassFormDirtySignature(savedForm)) {
    return true;
  }
  if (classId === 'new') {
    return newClassTeacherUserId !== null;
  }
  if (currentTeacherUserId !== undefined || savedTeacherUserId !== undefined) {
    if ((currentTeacherUserId ?? null) !== (savedTeacherUserId ?? null)) {
      return true;
    }
  }
  if (currentStudentIds || savedStudentIds) {
    const normalizeIds = (ids: number[] | undefined) => [...(ids || [])].sort((left, right) => left - right).join(',');
    if (normalizeIds(currentStudentIds) !== normalizeIds(savedStudentIds)) {
      return true;
    }
  }
  return false;
}

export function resolveFormsAfterClassDraftReset(
  currentFormByClassId: Record<string, ClassFormValues>,
  classId: number | 'new',
  savedForm: ClassFormValues,
): Record<string, ClassFormValues> {
  return {
    ...currentFormByClassId,
    [String(classId)]: savedForm,
  };
}

export function resolveNewClassTeacherAfterDraftReset(classId: number | 'new', currentTeacherUserId: number | null): number | null {
  return classId === 'new' ? null : currentTeacherUserId;
}

export function resolveTeacherSearchAfterClassDraftReset(
  currentTeacherSearchByClassId: Record<string, string>,
  classId: number | 'new',
): Record<string, string> {
  if (classId !== 'new') {
    return currentTeacherSearchByClassId;
  }
  return {
    ...currentTeacherSearchByClassId,
    new: '',
  };
}

export function resolveClassSaveFormWithCurrentStudents({
  classId,
  form,
  studentsByClassId,
}: {
  classId: number | 'new';
  form: ClassFormValues;
  studentsByClassId: Record<number, Array<{ id: number; name: string }>>;
}): ClassFormValues {
  if (classId === 'new' || !Object.prototype.hasOwnProperty.call(studentsByClassId, classId)) {
    return form;
  }
  return {
    ...form,
    selected_student_ids: studentsByClassId[classId].map((student) => student.id),
  };
}

export function buildClassSavePayload({
  classId,
  form,
  selectedTeacher,
  selectedTeacherUserId,
  existingStudents = [],
}: {
  classId: number | 'new';
  form: ClassFormValues;
  selectedTeacher?: UserItem;
  selectedTeacherUserId: number | null;
  existingStudents?: ExistingStudentOption[];
}): ClassSavePayload {
  const selectedStudentIds = form.selected_student_ids || [];
  const selectedStudentNames = selectedStudentIds
    .map((studentId) => existingStudents.find((student) => student.id === studentId)?.name || '')
    .filter(Boolean);
  const classType = form.class_type || 'group';
  const parsedBridge = parseBridgeTarget(form.bridge_target, form.stage);
  const bridgeTarget = form.is_bridge ? serializeBridgeTarget(parsedBridge.fromStage, parsedBridge.toStage) : form.bridge_target;
  const bridgeContentTrack = form.is_bridge ? parsedBridge.toStage : form.content_track;
  const cohortStage = form.is_bridge ? parsedBridge.toStage : form.stage;
  const inferredCohortYear = Number(form.cohort_year) || inferAcademicCohortYearForStage(form.current_grade || form.grade, cohortStage) || inferAcademicCohortYear(form.current_grade || form.grade);
  const displayName = buildClassDisplayName({ ...form, cohort_year: inferredCohortYear, selected_student_names: selectedStudentNames });

  return {
    name: displayName || normalizeClassNameInput(form.name),
    class_type: classType,
    subject: form.subject.trim(),
    grade: (form.current_grade || form.grade).trim(),
    teacher_name: selectedTeacher?.name || '',
    teacher_email: '',
    stage: form.stage,
    current_grade: normalizeAcademicGradeLabel(form.current_grade || form.grade),
    class_number: classType === 'group' ? form.class_number.trim() : '',
    cohort_year: inferredCohortYear,
    show_cohort_year: form.show_cohort_year,
    is_bridge: form.is_bridge,
    bridge_target: bridgeTarget,
    content_track: bridgeContentTrack,
    student_ids: selectedStudentIds,
    teacher_user_id: classId === 'new' ? selectedTeacherUserId : undefined,
  };
}

export function validateClassSaveDraft({
  classId,
  selectedTeacherUserId,
  payload,
  gradeOptions,
}: {
  classId: number | 'new';
  selectedTeacherUserId: number | null;
  payload: ClassSavePayload;
  gradeOptions: string[];
}): string | null {
  if (classId === 'new' && !selectedTeacherUserId) {
    return '请先选择负责老师账号';
  }

  if (payload.class_type === 'group' && !payload.class_number) {
    return '请选择班号';
  }

  const smallClassSizeByType: Record<string, number> = {
    '1v1': 1,
    '1v2': 2,
    '1v3': 3,
  };
  const requiredStudentCount = smallClassSizeByType[payload.class_type];
  if (requiredStudentCount && payload.student_ids.length !== requiredStudentCount) {
    return `请选择${requiredStudentCount}名学员`;
  }

  if (!payload.subject) {
    return '学科不能为空';
  }

  if (!payload.current_grade || !gradeOptions.includes(payload.current_grade)) {
    return '请选择年级';
  }

  return null;
}

export function findDuplicateClass(
  classes: ClassItem[],
  classId: number | 'new',
  payload: Pick<ClassSavePayload, 'name' | 'class_type' | 'subject' | 'stage' | 'current_grade' | 'class_number' | 'cohort_year' | 'teacher_name' | 'teacher_user_id'>,
): ClassItem | undefined {
  return classes.find((item) => {
    if (classId !== 'new' && item.id === classId) {
      return false;
    }
    const itemClassType = item.class_type || 'group';
    const payloadClassType = payload.class_type || 'group';
    if (itemClassType !== payloadClassType) {
      return false;
    }
    const itemTeacherUserId = Number(item.teacher_user_id || 0);
    const payloadTeacherUserId = Number(payload.teacher_user_id || 0);
    const itemTeacherName = normalizeClassNameInput(item.teacher_name || '');
    const payloadTeacherName = normalizeClassNameInput(payload.teacher_name || '');
    const sameTeacher = itemTeacherUserId > 0 && payloadTeacherUserId > 0
      ? itemTeacherUserId === payloadTeacherUserId
      : itemTeacherName !== '' && itemTeacherName === payloadTeacherName;
    if (!sameTeacher) {
      return false;
    }
    if (payloadClassType !== 'group') {
      return item.subject === payload.subject
        && normalizeClassNameInput(item.name || '') === normalizeClassNameInput(payload.name || '');
    }
    const itemCohortYear = Number(item.cohort_year || 0);
    const payloadCohortYear = Number(payload.cohort_year || 0);
    return item.subject === payload.subject
      && (item.stage || getAcademicStageFromGrade(item.current_grade || item.grade || '')) === payload.stage
      && normalizeAcademicGradeLabel(item.current_grade || item.grade || '') === payload.current_grade
      && String(item.class_number || '').trim() === payload.class_number
      && itemCohortYear === payloadCohortYear;
  });
}
