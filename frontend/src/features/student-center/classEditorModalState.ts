import { buildClassDisplayName } from '../../domain/classNaming';
import type {
  ClassEditorEditingState,
  ClassEditorModalErrors,
  ClassEditorModalLocks,
  ClassEditorModalMode,
  ClassEditorModalOptions,
  ClassEditorNewClassState,
} from './ClassEditorModal';
import {
  toClassFormValues,
  type ClassFormValues,
  type ClassInviteInfo,
  type ClassItem,
  type UserItem,
} from './model';
import type { ClassStudent } from './classStudentRules';

type ExpandedClassId = number | 'new' | null;
type GradeGroups = Readonly<Record<string, readonly string[]>>;

export type ClassEditorModalState = {
  mode: ClassEditorModalMode;
  locks: ClassEditorModalLocks;
  errors: ClassEditorModalErrors;
  options: ClassEditorModalOptions;
  newClass: ClassEditorNewClassState;
  editing: ClassEditorEditingState;
};

export function filterUsersByKeyword(
  users: UserItem[],
  keyword: string,
  alwaysIncludedUserId: number | null,
): UserItem[] {
  const normalizedKeyword = keyword.trim().toLowerCase();
  return users.filter((user) => {
    if (alwaysIncludedUserId === user.id) {
      return true;
    }
    if (!normalizedKeyword) {
      return true;
    }
    return user.name.toLowerCase().includes(normalizedKeyword);
  });
}

export function buildClassEditorModalState({
  expandedClassId,
  classes,
  users,
  formByClassId,
  emptyClassForm,
  teacherSearchByClassId,
  newClassTeacherUserId,
  teacherBindingByClassId,
  teacherBindingSavingByClassId,
  inviteByClassId,
  inviteLoadingByClassId,
  inviteResettingByClassId,
  inviteErrorByClassId,
  studentsByClassId,
  studentsLoadingByClassId,
  studentSavingByClassId,
  studentErrorByClassId,
  studentDraftNameByClassId,
  gradeGroups,
  gradeOptions,
  canEditTeacherBinding,
  classCardInteractionLocked,
  classInteractionLocked,
  assignmentRefreshLocked,
  saving,
  deleting,
  formError,
  assignmentError,
  academicSubjectOptions,
  studentCenterStageOptions,
}: {
  expandedClassId: ExpandedClassId;
  classes: ClassItem[];
  users: UserItem[];
  formByClassId: Record<string, ClassFormValues>;
  emptyClassForm: ClassFormValues;
  teacherSearchByClassId: Record<string, string>;
  newClassTeacherUserId: number | null;
  teacherBindingByClassId: Record<number, number | null>;
  teacherBindingSavingByClassId: Record<number, boolean>;
  inviteByClassId: Record<number, ClassInviteInfo>;
  inviteLoadingByClassId: Record<number, boolean>;
  inviteResettingByClassId: Record<number, boolean>;
  inviteErrorByClassId: Record<number, string>;
  studentsByClassId: Record<number, ClassStudent[]>;
  studentsLoadingByClassId: Record<number, boolean>;
  studentSavingByClassId: Record<number, boolean>;
  studentErrorByClassId: Record<number, string>;
  studentDraftNameByClassId: Record<number, string>;
  gradeGroups: GradeGroups;
  gradeOptions: readonly string[];
  canEditTeacherBinding: boolean;
  classCardInteractionLocked: boolean;
  classInteractionLocked: boolean;
  assignmentRefreshLocked: boolean;
  saving: boolean;
  deleting: boolean;
  formError: string;
  assignmentError: string;
  academicSubjectOptions: string[];
  studentCenterStageOptions: string[];
}): ClassEditorModalState {
  const newClassForm = formByClassId.new || emptyClassForm;
  const newClassTeacher = newClassTeacherUserId == null
    ? undefined
    : users.find((user) => user.id === newClassTeacherUserId);
  const newClassGradeOptions = [...(gradeGroups[newClassForm.stage] || gradeOptions)];
  const newClassDisplayNamePreview = buildClassDisplayName({ ...newClassForm, show_cohort_year: true }) || '2025级·四年级·1班';

  const editingClass = typeof expandedClassId === 'number'
    ? classes.find((item) => item.id === expandedClassId) ?? null
    : null;
  const editingFormState = editingClass
    ? (formByClassId[String(editingClass.id)] || toClassFormValues(editingClass))
    : null;
  const editingCurrentTeacherUserId = editingClass
    ? (teacherBindingByClassId[editingClass.id] ?? editingClass.teacher_user_id ?? null)
    : null;
  const editingCurrentTeacher = editingCurrentTeacherUserId == null
    ? undefined
    : users.find((user) => user.id === editingCurrentTeacherUserId);
  const editingTeacherSearch = editingClass ? (teacherSearchByClassId[String(editingClass.id)] || '') : '';

  return {
    mode: {
      newClassExpanded: expandedClassId === 'new',
      editingClass,
      editingFormState,
    },
    locks: {
      classCardInteractionLocked,
      classInteractionLocked,
      assignmentRefreshLocked,
      saving,
      deleting,
    },
    errors: {
      formError,
      assignmentError,
    },
    options: {
      academicSubjectOptions,
      studentCenterStageOptions,
    },
    newClass: {
      form: newClassForm,
      teacher: newClassTeacher,
      teacherUserId: newClassTeacherUserId,
      filteredUsers: filterUsersByKeyword(users, teacherSearchByClassId.new || '', newClassTeacherUserId),
      gradeOptions: newClassGradeOptions,
      displayNamePreview: newClassDisplayNamePreview,
    },
    editing: {
      canEditTeacherBinding,
      gradeOptions: editingFormState ? [...(gradeGroups[editingFormState.stage] || gradeOptions)] : [...gradeOptions],
      displayNamePreview: editingFormState ? buildClassDisplayName({ ...editingFormState, show_cohort_year: true }) || '2025级·四年级·1班' : '',
      teacherSearch: editingTeacherSearch,
      currentTeacherUserId: editingCurrentTeacherUserId,
      teacherSummary: editingCurrentTeacher?.name || editingClass?.teacher_name || '未分配老师',
      teacherBindingSaving: editingClass ? Boolean(teacherBindingSavingByClassId[editingClass.id]) : false,
      filteredUsers: editingClass ? filterUsersByKeyword(users, editingTeacherSearch, editingCurrentTeacherUserId) : [],
      inviteInfo: editingClass ? inviteByClassId[editingClass.id] : undefined,
      inviteLoading: editingClass ? Boolean(inviteLoadingByClassId[editingClass.id]) : false,
      inviteResetting: editingClass ? Boolean(inviteResettingByClassId[editingClass.id]) : false,
      inviteError: editingClass ? (inviteErrorByClassId[editingClass.id] || '') : '',
      students: editingClass ? (studentsByClassId[editingClass.id] || []) : [],
      studentsLoading: editingClass ? Boolean(studentsLoadingByClassId[editingClass.id]) : false,
      studentSaving: editingClass ? Boolean(studentSavingByClassId[editingClass.id]) : false,
      studentError: editingClass ? (studentErrorByClassId[editingClass.id] || '') : '',
      studentDraftName: editingClass ? (studentDraftNameByClassId[editingClass.id] || '') : '',
    },
  };
}
