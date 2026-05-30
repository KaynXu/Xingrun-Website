import type { ClassItem } from './model';

export function buildTeacherBindingRefreshErrorMessage(error: Error): string {
  return `老师绑定已保存，但列表刷新失败：${error.message}`;
}

export function resolveTeacherBindingSaveErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '负责老师保存失败';
}

export function resolveTeacherBindingPreviousState(
  classId: number,
  classes: ClassItem[],
  teacherBindingByClassId: Record<number, number | null>,
): {
  previousClass: ClassItem | undefined;
  previousTeacherUserId: number | null;
  previousTeacherName: string;
} {
  const previousClass = classes.find((item) => item.id === classId);
  return {
    previousClass,
    previousTeacherUserId: teacherBindingByClassId[classId] ?? previousClass?.teacher_user_id ?? null,
    previousTeacherName: previousClass?.teacher_name || '',
  };
}

export function resolveTeacherBindingSavingStartState(
  currentSavingByClassId: Record<number, boolean>,
  classId: number,
): Record<number, boolean> {
  return {
    ...currentSavingByClassId,
    [classId]: true,
  };
}

export function resolveTeacherBindingSavingEndState(
  currentSavingByClassId: Record<number, boolean>,
  classId: number,
): Record<number, boolean> {
  const nextState = { ...currentSavingByClassId };
  delete nextState[classId];
  return nextState;
}

export function buildTeacherBindingRequest(classId: number, teacherUserId: number): {
  path: string;
  init: {
    method: 'PUT';
    body: string;
  };
} {
  return {
    path: `/api/classes/${classId}/teacher`,
    init: {
      method: 'PUT',
      body: JSON.stringify({ teacher_user_id: teacherUserId }),
    },
  };
}

export async function executeTeacherBindingRequest(
  classId: number,
  teacherUserId: number,
  apiFetch: (path: string, init: { method: 'PUT'; body: string }) => Promise<unknown>,
): Promise<void> {
  const request = buildTeacherBindingRequest(classId, teacherUserId);
  await apiFetch(request.path, request.init);
}

export function resolveTeacherBindingOptimisticClassItem(
  currentItem: ClassItem,
  selectedTeacher: { name: string } | undefined,
  nextTeacherUserId: number,
): ClassItem {
  return {
    ...currentItem,
    teacher_name: selectedTeacher?.name || currentItem.teacher_name,
    teacher_user_id: nextTeacherUserId,
  };
}

export function resolveClassesAfterTeacherBindingOptimisticUpdate(
  currentClasses: ClassItem[],
  classId: number,
  selectedTeacher: { name: string } | undefined,
  nextTeacherUserId: number,
): ClassItem[] {
  return currentClasses.map((item) => (
    item.id === classId
      ? resolveTeacherBindingOptimisticClassItem(item, selectedTeacher, nextTeacherUserId)
      : item
  ));
}

export function resolveTeacherBindingRollbackClassItem(
  currentItem: ClassItem,
  failedNextTeacherUserId: number,
  previousTeacherUserId: number | null,
  previousTeacherName: string,
): ClassItem {
  if (currentItem.teacher_user_id !== failedNextTeacherUserId) {
    return currentItem;
  }

  return {
    ...currentItem,
    teacher_name: previousTeacherName,
    teacher_user_id: previousTeacherUserId,
  };
}

export function resolveClassesAfterTeacherBindingRollback(
  currentClasses: ClassItem[],
  classId: number,
  failedNextTeacherUserId: number,
  previousTeacherUserId: number | null,
  previousTeacherName: string,
): ClassItem[] {
  return currentClasses.map((item) => (
    item.id === classId
      ? resolveTeacherBindingRollbackClassItem(item, failedNextTeacherUserId, previousTeacherUserId, previousTeacherName)
      : item
  ));
}

export function resolveTeacherBindingRollbackTeacherBindings(
  currentTeacherBindingByClassId: Record<number, number | null>,
  classId: number,
  previousTeacherUserId: number | null,
  failedNextTeacherUserId: number,
): Record<number, number | null> {
  if (currentTeacherBindingByClassId[classId] !== failedNextTeacherUserId) {
    return currentTeacherBindingByClassId;
  }

  return {
    ...currentTeacherBindingByClassId,
    [classId]: previousTeacherUserId,
  };
}
