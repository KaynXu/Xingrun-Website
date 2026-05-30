export type ClassStudent = {
  id: number;
  name: string;
};

export type ClassStudentMap = Record<number, ClassStudent[]>;

type ListClassStudents = (classId: number) => Promise<{ students: ClassStudent[] }>;
type CreateClassStudent = (classId: number, name: string) => Promise<{ student: ClassStudent; deduplicated: boolean }>;
type DeleteClassStudent = (classId: number, studentId: number) => Promise<{ ok: boolean; removed: boolean }>;

export function resolveClassStudentDraftName(rawName: string | undefined): string {
  return (rawName || '').trim();
}

export function validateClassStudentDraftName(rawName: string | undefined): string {
  return resolveClassStudentDraftName(rawName) ? '' : '请输入学生姓名';
}

export async function executeClassStudentListRequest(
  classId: number,
  listClassStudents: ListClassStudents,
): Promise<{ students: ClassStudent[] }> {
  return listClassStudents(classId);
}

export async function executeClassStudentCreateRequest(
  classId: number,
  draftName: string,
  createClassStudent: CreateClassStudent,
): Promise<{ student: ClassStudent; deduplicated: boolean }> {
  return createClassStudent(classId, draftName);
}

export async function executeClassStudentDeleteRequest(
  classId: number,
  studentId: number,
  deleteClassStudent: DeleteClassStudent,
): Promise<{ ok: boolean; removed: boolean }> {
  return deleteClassStudent(classId, studentId);
}

export function resolveClassStudentSavingStartState(
  current: Record<number, boolean>,
  classId: number,
): Record<number, boolean> {
  return { ...current, [classId]: true };
}

export function resolveClassStudentSavingEndState(
  current: Record<number, boolean>,
  classId: number,
): Record<number, boolean> {
  return { ...current, [classId]: false };
}

export function resolveClassStudentErrorMessage(
  err: unknown,
  action: 'load' | 'create' | 'delete',
): string {
  if (err instanceof Error) {
    return err.message;
  }
  if (action === 'load') {
    return '学生列表加载失败';
  }
  if (action === 'create') {
    return '新增学生失败，请重试。';
  }
  return '删除学生失败，请重试。';
}

export function resolveClassStudentsAfterLoad(
  current: ClassStudentMap,
  classId: number,
  students: ClassStudent[],
): ClassStudentMap {
  return { ...current, [classId]: students };
}

export function resolveClassStudentsAfterCreate(
  current: ClassStudentMap,
  classId: number,
  student: ClassStudent,
): ClassStudentMap {
  return {
    ...current,
    [classId]: [...(current[classId] || []), student],
  };
}

export function resolveClassStudentsAfterDelete(
  current: ClassStudentMap,
  classId: number,
  studentId: number,
): ClassStudentMap {
  return {
    ...current,
    [classId]: (current[classId] || []).filter((student) => student.id !== studentId),
  };
}

export function resolveClassStudentDraftAfterCreate(
  current: Record<number, string>,
  classId: number,
): Record<number, string> {
  return { ...current, [classId]: '' };
}
