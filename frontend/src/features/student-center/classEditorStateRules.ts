import { normalizeAcademicGradeLabel } from '../../domain/classNaming';
import type { ClassFormValues } from './model';
import type { ExpandedClassId } from './classDeleteRules';

type GradeGroups = Readonly<Record<string, readonly string[]>>;

export function resolveClassFormAfterFieldChange(
  currentForm: ClassFormValues,
  field: keyof ClassFormValues,
  value: string,
  gradeGroups: GradeGroups,
  fallbackGradeOptions: readonly string[],
): ClassFormValues {
  const nextForm: ClassFormValues = {
    ...currentForm,
    [field]: field === 'current_grade' ? normalizeAcademicGradeLabel(value) : value,
  };

  if (field === 'stage') {
    const gradeOptionsForStage = gradeGroups[value] || fallbackGradeOptions;
    if (!gradeOptionsForStage.includes(nextForm.current_grade)) {
      nextForm.current_grade = gradeOptionsForStage[0] || '';
    }
  }

  return nextForm;
}

export function resolveFormsAfterFieldChange(
  currentFormByClassId: Record<string, ClassFormValues>,
  classId: number | 'new',
  field: keyof ClassFormValues,
  value: string,
  emptyClassForm: ClassFormValues,
  gradeGroups: GradeGroups,
  fallbackGradeOptions: readonly string[],
): Record<string, ClassFormValues> {
  const stateKey = String(classId);
  const currentForm = currentFormByClassId[stateKey] || emptyClassForm;
  return {
    ...currentFormByClassId,
    [stateKey]: resolveClassFormAfterFieldChange(currentForm, field, value, gradeGroups, fallbackGradeOptions),
  };
}

export function resolveTeacherSearchAfterChange(
  currentTeacherSearchByClassId: Record<string, string>,
  classId: number | 'new',
  value: string,
): Record<string, string> {
  return {
    ...currentTeacherSearchByClassId,
    [String(classId)]: value,
  };
}

export function resolveExpandedClassAfterToggle(
  currentExpandedClassId: ExpandedClassId,
  classId: number | 'new',
  locked: boolean,
): ExpandedClassId {
  if (locked) {
    return currentExpandedClassId;
  }
  return currentExpandedClassId === classId ? null : classId;
}

export function resolveClassEditorErrorsAfterToggle(): {
  formError: string;
  assignmentError: string;
} {
  return {
    formError: '',
    assignmentError: '',
  };
}
