import type { ClassFormValues, ClassItem, ClassStudentOption, UserItem } from './model';
import { toClassFormValues } from './model';
import type { ExpandedClassId } from './classDeleteRules';

type ApiFetch = <T>(endpoint: string, init?: RequestInit) => Promise<T>;

export async function executeStudentCenterLoadRequest(
  apiFetch: ApiFetch,
  permissions: {
    canLoadStaffMembers: boolean;
    canLoadStudentProfiles: boolean;
  },
): Promise<{
  classItems: ClassItem[];
  userItems: UserItem[];
  allStudents: ClassStudentOption[];
  teacherBindingData: { teacher_bindings: Record<number, number | null> };
}> {
  const [classItems, userItems, teacherBindingData, studentData] = await Promise.all([
    apiFetch<ClassItem[]>('/api/classes'),
    permissions.canLoadStaffMembers
      ? apiFetch<UserItem[]>('/api/admin/users')
      : Promise.resolve([] as UserItem[]),
    permissions.canLoadStaffMembers
      ? apiFetch<{ teacher_bindings: Record<number, number | null> }>('/api/classes/teacher-bindings')
      : Promise.resolve({ teacher_bindings: {} as Record<number, number | null> }),
    permissions.canLoadStudentProfiles
      ? apiFetch<{ students: ClassStudentOption[] }>('/api/students')
      : Promise.resolve({ students: [] as ClassStudentOption[] }),
  ]);

  return { classItems, userItems, teacherBindingData, allStudents: studentData.students };
}

export function resolveClassLoadStartState(currentRequestVersion: number): {
  requestVersion: number;
  loading: true;
  pageError: '';
} {
  return {
    requestVersion: currentRequestVersion + 1,
    loading: true,
    pageError: '',
  };
}

export function isCurrentClassLoadRequest(
  requestVersion: number,
  currentRequestVersion: number,
): boolean {
  return requestVersion === currentRequestVersion;
}

export function buildClassLoadSuccessState({
  classItems,
  userItems,
  allStudents,
  rawTeacherBindings,
  currentFormByClassId,
  currentExpandedClassId,
  preferredExpandedClassId,
  emptyClassForm,
}: {
  classItems: ClassItem[];
  userItems: UserItem[];
  allStudents: ClassStudentOption[];
  rawTeacherBindings: Record<number, number | null>;
  currentFormByClassId: Record<string, ClassFormValues>;
  currentExpandedClassId: ExpandedClassId;
  preferredExpandedClassId: ExpandedClassId | undefined;
  emptyClassForm: ClassFormValues;
}): {
  classes: ClassItem[];
  users: UserItem[];
  allStudents: ClassStudentOption[];
  teacherBindingByClassId: Record<number, number | null>;
  formByClassId: Record<string, ClassFormValues>;
  expandedClassId: ExpandedClassId;
} {
  const teacherBindingByClassId = normalizeTeacherBindings(rawTeacherBindings);
  return {
    classes: classItems,
    users: userItems,
    allStudents,
    teacherBindingByClassId,
    formByClassId: resolveFormsAfterClassLoad(currentFormByClassId, classItems, emptyClassForm),
    expandedClassId: resolveExpandedClassAfterLoad(currentExpandedClassId, preferredExpandedClassId, classItems),
  };
}

export function buildClassLoadFailureState(
  emptyClassForm: ClassFormValues,
): {
  classes: ClassItem[];
  users: UserItem[];
  allStudents: ClassStudentOption[];
  teacherBindingByClassId: Record<number, number | null>;
  formByClassId: Record<string, ClassFormValues>;
  newClassTeacherUserId: null;
  expandedClassId: null;
} {
  return {
    classes: [],
    users: [],
    allStudents: [],
    teacherBindingByClassId: {},
    formByClassId: resolveFormsAfterClassLoadFailure(emptyClassForm),
    newClassTeacherUserId: resolveNewClassTeacherAfterClassLoadFailure(),
    expandedClassId: resolveExpandedClassAfterLoadFailure(),
  };
}

export function normalizeTeacherBindings(
  rawTeacherBindings: Record<number, number | null>,
): Record<number, number | null> {
  return Object.fromEntries(
    Object.entries(rawTeacherBindings).map(([classId, teacherUserId]) => [Number(classId), teacherUserId]),
  ) as Record<number, number | null>;
}

export function resolveFormsAfterClassLoad(
  currentFormByClassId: Record<string, ClassFormValues>,
  loadedClasses: ClassItem[],
  emptyClassForm: ClassFormValues,
): Record<string, ClassFormValues> {
  const nextForms: Record<string, ClassFormValues> = {
    new: currentFormByClassId.new || emptyClassForm,
  };
  loadedClasses.forEach((item) => {
    nextForms[String(item.id)] = toClassFormValues(item);
  });
  return nextForms;
}

export function resolveExpandedClassAfterLoad(
  currentExpandedClassId: ExpandedClassId,
  preferredExpandedClassId: ExpandedClassId | undefined,
  loadedClasses: ClassItem[],
): ExpandedClassId {
  const requestedExpansion = preferredExpandedClassId === undefined ? currentExpandedClassId : preferredExpandedClassId;
  if (requestedExpansion === 'new') {
    return 'new';
  }
  if (typeof requestedExpansion === 'number' && loadedClasses.some((item) => item.id === requestedExpansion)) {
    return requestedExpansion;
  }
  return null;
}

export function resolveClassLoadError(error: unknown): Error {
  return error instanceof Error ? error : new Error('班级管理数据加载失败');
}

export function resolveFormsAfterClassLoadFailure(
  emptyClassForm: ClassFormValues,
): Record<string, ClassFormValues> {
  return { new: emptyClassForm };
}

export function resolveNewClassTeacherAfterClassLoadFailure(): null {
  return null;
}

export function resolveExpandedClassAfterLoadFailure(): null {
  return null;
}
