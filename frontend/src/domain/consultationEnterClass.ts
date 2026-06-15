import {
  buildClassDisplayName,
  getAcademicStageFromGrade,
  normalizeAcademicGradeLabel,
} from './classNaming';
import { resolveFilteredClasses, type ClassFilterState } from '../features/student-center/classFilterRules';

export type ConsultationEnterClassMode = 'existing' | 'quick-create' | 'pending';

export type ConsultationEnterClassDraft = {
  class_type: string;
  subject: string;
  stage: string;
  current_grade: string;
  class_number: string;
  cohort_year: number | string;
  show_cohort_year: boolean;
  is_bridge: boolean;
  bridge_target: string;
};

export type ConsultationEnterClassPayload =
  | { mode: 'existing'; class_id: number; consultation_subject?: string; grade?: string; teaching_teacher_id?: string; teaching_teacher?: string; teaching_teacher_user_id?: number }
  | {
      mode: 'quick_new_class';
      class_name: string;
      subject: string;
      grade: string;
      class_type: string;
      stage: string;
      current_grade: string;
      class_number: string;
      cohort_year: number | null;
      show_cohort_year: boolean;
      is_bridge: boolean;
      bridge_target: string;
      content_track: string;
      teaching_teacher_id?: string;
      teaching_teacher?: string;
      teaching_teacher_user_id?: number;
    }
  | { mode: 'converted_without_class'; teaching_teacher_id?: string; teaching_teacher?: string; teaching_teacher_user_id?: number };

type ClassFilterItem = {
  id: number;
  name: string;
  class_type?: string;
  subject?: string;
  grade?: string;
  stage?: string;
  current_grade?: string;
  class_number?: string;
  teacher_user_id?: number | null;
  teacher_name?: string;
};

export function buildConsultationEnterClassPayload(args:
  | { mode: 'existing'; existingClassId: string | number; consultationSubject?: string; grade?: string; teachingTeacherId?: string; teachingTeacherName?: string; teachingTeacherUserId?: number }
  | { mode: 'quick-create'; quickClassDraft: ConsultationEnterClassDraft; teachingTeacherId?: string; teachingTeacherName?: string; teachingTeacherUserId?: number }
  | { mode: 'pending'; teachingTeacherId?: string; teachingTeacherName?: string; teachingTeacherUserId?: number }
): ConsultationEnterClassPayload {
  const teacherHandoff = {
    ...(args.teachingTeacherId ? { teaching_teacher_id: args.teachingTeacherId } : {}),
    ...(args.teachingTeacherName ? { teaching_teacher: args.teachingTeacherName } : {}),
    ...(args.teachingTeacherUserId ? { teaching_teacher_user_id: args.teachingTeacherUserId } : {}),
  };
  if (args.mode === 'existing') {
    const payload: ConsultationEnterClassPayload = {
      mode: 'existing',
      class_id: Number(args.existingClassId),
      ...teacherHandoff,
    };
    if (args.consultationSubject) payload.consultation_subject = args.consultationSubject;
    if (args.grade) payload.grade = args.grade;
    return payload;
  }
  if (args.mode === 'pending') {
    return { mode: 'converted_without_class', ...teacherHandoff };
  }
  const draft = args.quickClassDraft;
  const cohortYear = draft.cohort_year === '' ? null : Number(draft.cohort_year);
  return {
    mode: 'quick_new_class',
    class_name: buildClassDisplayName({
      subject: draft.subject,
      class_type: draft.class_type,
      stage: draft.stage,
      current_grade: draft.current_grade,
      grade: draft.current_grade,
      class_number: draft.class_number,
      cohort_year: draft.cohort_year,
      show_cohort_year: draft.show_cohort_year,
      is_bridge: draft.is_bridge,
      bridge_target: draft.bridge_target,
    }),
    subject: draft.subject,
    grade: draft.current_grade,
    class_type: draft.class_type,
    stage: draft.stage,
    current_grade: draft.current_grade,
    class_number: draft.class_number,
    cohort_year: Number.isFinite(cohortYear) ? cohortYear : null,
    show_cohort_year: draft.show_cohort_year,
    is_bridge: draft.is_bridge,
    bridge_target: draft.bridge_target,
    content_track: '',
    ...teacherHandoff,
  };
}

export function buildRecommendedConsultationClassFilters({
  consultationSubject,
  consultationGrade,
  subjectOptions,
}: {
  consultationSubject: string;
  consultationGrade: string;
  subjectOptions: string[];
}): ClassFilterState {
  const normalizedGrade = normalizeAcademicGradeLabel(consultationGrade || '');
  const stage = getAcademicStageFromGrade(normalizedGrade);
  return {
    subjectFilter: consultationSubject && subjectOptions.includes(consultationSubject) ? consultationSubject : '全部学科',
    teacherFilter: 'all',
    stageFilter: stage || '全部学段',
    gradeFilter: normalizedGrade || '全部',
  };
}

export function filterConsultationEnterClassOptions<TClass extends ClassFilterItem>({
  classes,
  subjectOptions,
  filters,
}: {
  classes: TClass[];
  subjectOptions: string[];
  filters: ClassFilterState;
}): TClass[] {
  return resolveFilteredClasses({
    classes,
    subjectLookupClasses: classes,
    teacherBindingByClassId: {},
    subjectOptions,
    filters,
  }) as TClass[];
}
