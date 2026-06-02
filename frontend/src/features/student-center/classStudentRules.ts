export type ClassStudent = {
  id: number;
  name: string;
  source?: string;
  parent_contact?: string;
  created_at?: string;
  study_status?: string;
  study_duration_label?: string;
  first_lesson_date?: string | null;
  last_lesson_date?: string | null;
  study_records?: StudentStudyRecord[];
  history_items?: StudentClassHistoryItem[];
};

export type StudentStudyRecord = {
  class_id: number;
  class_name?: string;
  class_type?: string;
  subject?: string;
  stage?: string;
  current_grade?: string;
  grade?: string;
  teacher_name?: string;
  lesson_count?: number;
  first_lesson_date?: string | null;
  last_lesson_date?: string | null;
};

export type StudentClassHistoryItem = {
  id?: number;
  class_id?: number;
  class_name?: string;
  action?: string;
  created_at?: string;
  note?: string;
};

export type ClassStudentMap = Record<number, ClassStudent[]>;
export type StudentProfileDraft = {
  name: string;
  source: string;
  parent_contact: string;
};

type ListClassStudents = (classId: number) => Promise<{ students: ClassStudent[] }>;
type CreateClassStudent = (classId: number, studentId: number) => Promise<{ student: ClassStudent; deduplicated: boolean }>;
type DeleteClassStudent = (classId: number, studentId: number) => Promise<{ ok: boolean; removed: boolean }>;
type CreateStudentProfile = (path: string, init: { method: 'POST'; body: string }) => Promise<{ student: ClassStudent }>;
type UpdateStudentProfile = (path: string, init: { method: 'PUT'; body: string }) => Promise<{ student: ClassStudent }>;
type GetStudentProfile = (path: string) => Promise<{ student: ClassStudent }>;

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
  studentId: number,
  createClassStudent: CreateClassStudent,
): Promise<{ student: ClassStudent; deduplicated: boolean }> {
  return createClassStudent(classId, studentId);
}

export async function executeClassStudentDeleteRequest(
  classId: number,
  studentId: number,
  deleteClassStudent: DeleteClassStudent,
): Promise<{ ok: boolean; removed: boolean }> {
  return deleteClassStudent(classId, studentId);
}

export function buildStudentProfileSavePayload(draft: StudentProfileDraft): StudentProfileDraft {
  return {
    name: (draft.name || '').trim(),
    source: (draft.source || '').trim(),
    parent_contact: (draft.parent_contact || '').trim(),
  };
}

export function validateStudentProfileDraft(draft: StudentProfileDraft): string | null {
  return buildStudentProfileSavePayload(draft).name ? null : '请输入学员姓名';
}

export function resolveStudentProfileDraftDirty(
  currentDraft: StudentProfileDraft,
  savedDraft: StudentProfileDraft | null,
): boolean {
  if (!savedDraft) {
    return Boolean(buildStudentProfileSavePayload(currentDraft).name);
  }
  return JSON.stringify(buildStudentProfileSavePayload(currentDraft)) !== JSON.stringify(buildStudentProfileSavePayload(savedDraft));
}

export async function executeStudentProfileCreateRequest(
  payload: StudentProfileDraft,
  apiFetch: CreateStudentProfile,
): Promise<{ student: ClassStudent }> {
  return apiFetch('/api/students', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function executeStudentProfileUpdateRequest(
  studentId: number,
  payload: StudentProfileDraft,
  apiFetch: UpdateStudentProfile,
): Promise<{ student: ClassStudent }> {
  return apiFetch(`/api/students/${studentId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function executeStudentProfileGetRequest(
  studentId: number,
  apiFetch: GetStudentProfile,
): Promise<{ student: ClassStudent }> {
  return apiFetch(`/api/students/${studentId}`);
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
    [classId]: (current[classId] || []).some((item) => item.id === student.id)
      ? current[classId]
      : [...(current[classId] || []), student],
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
