import { getAcademicStageFromGrade, normalizeAcademicGradeLabel } from './classNaming';
import {
  resolveFilteredClasses,
  type ClassFilterState,
} from '../features/student-center/classFilterRules';
import {
  buildClassSavePayload,
  type ClassSavePayload,
  validateClassSaveDraft,
} from '../features/student-center/classSaveRules';
import {
  createEmptyClassForm,
  type ClassFormValues,
  type ClassItem,
  type UserItem,
} from '../features/student-center/model';

export type ConsultationClassTypeFilter = 'all' | 'small' | 'group';

export type ConsultationClassFilterState = ClassFilterState & {
  classTypeFilter: ConsultationClassTypeFilter;
};

type AdapterClassItem = ClassItem;

export function buildConsultationClassFilterDefaults({
  consultationSubject,
  consultationGrade,
  teachingTeacherUserId,
  subjectOptions,
}: {
  consultationSubject: string;
  consultationGrade: string;
  teachingTeacherUserId?: number | null;
  subjectOptions: string[];
}): ConsultationClassFilterState {
  const normalizedGrade = normalizeAcademicGradeLabel(consultationGrade || '');
  const stage = getAcademicStageFromGrade(normalizedGrade);

  return {
    subjectFilter: consultationSubject && subjectOptions.includes(consultationSubject) ? consultationSubject : '全部学科',
    teacherFilter: teachingTeacherUserId ?? 'all',
    stageFilter: stage || '全部学段',
    gradeFilter: normalizedGrade || '全部',
    classTypeFilter: 'all',
  };
}

export function filterConsultationStudentCenterClasses<TClass extends AdapterClassItem>({
  classes,
  subjectOptions,
  teacherBindingByClassId,
  filters,
}: {
  classes: TClass[];
  subjectOptions: string[];
  teacherBindingByClassId: Record<number, number | null>;
  filters: ConsultationClassFilterState;
}): TClass[] {
  const classTypeFiltered = classes.filter((item) => {
    if (filters.classTypeFilter === 'small') {
      return item.class_type && item.class_type !== 'group';
    }
    if (filters.classTypeFilter === 'group') {
      return !item.class_type || item.class_type === 'group';
    }
    return true;
  });

  return resolveFilteredClasses({
    classes: classTypeFiltered,
    subjectLookupClasses: classes,
    teacherBindingByClassId,
    subjectOptions,
    filters,
  }) as TClass[];
}

export function buildConsultationQuickClassForm({
  consultationSubject,
  consultationGrade,
  subjectOptions,
}: {
  consultationSubject: string;
  consultationGrade: string;
  subjectOptions: string[];
}): ClassFormValues {
  const normalizedGrade = normalizeAcademicGradeLabel(consultationGrade || '');

  return {
    ...createEmptyClassForm(),
    subject: consultationSubject && subjectOptions.includes(consultationSubject) ? consultationSubject : subjectOptions[0] || '',
    grade: normalizedGrade || '一年级',
    stage: getAcademicStageFromGrade(normalizedGrade) || '小奥',
    current_grade: normalizedGrade || '一年级',
  };
}

export function buildConsultationQuickClassSavePayload({
  form,
  selectedTeacher,
  selectedTeacherUserId,
}: {
  form: ClassFormValues;
  selectedTeacher?: UserItem;
  selectedTeacherUserId: number | null;
}): ClassSavePayload {
  return buildClassSavePayload({
    classId: 'new',
    form,
    selectedTeacher,
    selectedTeacherUserId,
  });
}

export function validateConsultationQuickClassForm({
  form,
  selectedTeacher,
  selectedTeacherUserId,
  gradeOptions,
}: {
  form: ClassFormValues;
  selectedTeacher?: UserItem;
  selectedTeacherUserId: number | null;
  gradeOptions: string[];
}): string | null {
  const payload = buildConsultationQuickClassSavePayload({
    form,
    selectedTeacher,
    selectedTeacherUserId,
  });

  return validateClassSaveDraft({
    classId: 'new',
    selectedTeacherUserId,
    payload,
    gradeOptions,
  });
}
