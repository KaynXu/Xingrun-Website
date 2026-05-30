import type { ClassFormValues, ClassItem, UserItem } from './model';
import { toClassFormValues } from './model';
import type { ExpandedClassId } from './classDeleteRules';

type ApiFetch = <T>(endpoint: string, init?: RequestInit) => Promise<T>;

export async function executeStudentCenterLoadRequest(
  apiFetch: ApiFetch,
  canLoadStaffMembers: boolean,
): Promise<{
  classItems: ClassItem[];
  userItems: UserItem[];
  teacherBindingData: { teacher_bindings: Record<number, number | null> };
}> {
  const [classItems, userItems, teacherBindingData] = await Promise.all([
    apiFetch<ClassItem[]>('/api/classes'),
    canLoadStaffMembers
      ? apiFetch<UserItem[]>('/api/admin/users')
      : Promise.resolve([] as UserItem[]),
    canLoadStaffMembers
      ? apiFetch<{ teacher_bindings: Record<number, number | null> }>('/api/classes/teacher-bindings')
      : Promise.resolve({ teacher_bindings: {} as Record<number, number | null> }),
  ]);

  return { classItems, userItems, teacherBindingData };
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
  rawTeacherBindings,
  currentFormByClassId,
  currentExpandedClassId,
  preferredExpandedClassId,
  emptyClassForm,
}: {
  classItems: ClassItem[];
  userItems: UserItem[];
  rawTeacherBindings: Record<number, number | null>;
  currentFormByClassId: Record<string, ClassFormValues>;
  currentExpandedClassId: ExpandedClassId;
  preferredExpandedClassId: ExpandedClassId | undefined;
  emptyClassForm: ClassFormValues;
}): {
  classes: ClassItem[];
  users: UserItem[];
  teacherBindingByClassId: Record<number, number | null>;
  formByClassId: Record<string, ClassFormValues>;
  expandedClassId: ExpandedClassId;
} {
  const teacherBindingByClassId = normalizeTeacherBindings(rawTeacherBindings);
  return {
    classes: classItems,
    users: userItems,
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
  teacherBindingByClassId: Record<number, number | null>;
  formByClassId: Record<string, ClassFormValues>;
  newClassTeacherUserId: null;
  expandedClassId: null;
} {
  return {
    classes: [],
    users: [],
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
