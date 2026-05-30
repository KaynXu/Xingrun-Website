export type ExpandedClassId = number | 'new' | null;

type IdentifiedClass = {
  id: number;
};

export function buildClassDeleteConfirmMessage(targetClass: { name: string }): string {
  return `确定删除班级「${targetClass.name}」吗？`;
}

export function buildClassDeleteRequest(classId: number): {
  path: string;
  init: { method: 'DELETE' };
} {
  return {
    path: `/api/classes/${classId}`,
    init: { method: 'DELETE' },
  };
}

export async function executeClassDeleteRequest(
  classId: number,
  apiFetch: (path: string, init: { method: 'DELETE' }) => Promise<unknown>,
): Promise<void> {
  const request = buildClassDeleteRequest(classId);
  await apiFetch(request.path, request.init);
}

export function resolveClassDeleteErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '班级删除失败';
}

export function resolveExpandedClassAfterDelete(current: ExpandedClassId, deletedClassId: number): ExpandedClassId {
  return current === deletedClassId ? null : current;
}

export function resolveClassesAfterDelete<T extends IdentifiedClass>(currentClasses: T[], deletedClassId: number): T[] {
  return currentClasses.filter((item) => item.id !== deletedClassId);
}

export function resolveTeacherBindingsAfterClassDelete(
  currentTeacherBindingByClassId: Record<number, number | null>,
  deletedClassId: number,
): Record<number, number | null> {
  const nextState = { ...currentTeacherBindingByClassId };
  delete nextState[deletedClassId];
  return nextState;
}

export function resolveFormsAfterClassDelete<T>(
  currentFormByClassId: Record<string, T>,
  deletedClassId: number,
): Record<string, T> {
  const nextState = { ...currentFormByClassId };
  delete nextState[String(deletedClassId)];
  return nextState;
}

export function resolveTeacherSearchAfterClassDelete(
  currentTeacherSearchByClassId: Record<string, string>,
  deletedClassId: number,
): Record<string, string> {
  const nextState = { ...currentTeacherSearchByClassId };
  delete nextState[String(deletedClassId)];
  return nextState;
}
