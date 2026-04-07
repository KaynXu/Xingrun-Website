export interface TeacherFeedbackTemplate {
  id: string;
  label: string;
  guidance: string;
  isCustom?: boolean;
}

export interface TeacherFeedbackStudentDraft {
  studentId: number;
  name: string;
  selectedTemplateId: string;
  remark: string;
}

export interface LessonFeedbackDocument {
  lesson_id: number;
  class_id: number | null;
  merged_text: string;
  student_index: Array<{ student_id: number; name: string }>;
  students: Array<{ student_id: number; name: string; selected_template_id: string; remark: string }>;
  custom_templates: TeacherFeedbackTemplate[];
  updated_at?: string | null;
}

export interface TeacherFeedbackSavePayload {
  merged_text: string;
  student_index: Array<{ student_id: number; name: string }>;
  students: Array<{ student_id: number; name: string; selected_template_id: string; remark: string }>;
  custom_templates: Array<{ id: string; label: string; guidance: string }>;
}

export interface LessonFeedbackDraftResponse {
  lesson_id: number;
  merged_text: string;
  students_included: number;
  students_skipped: number;
}

export const defaultTeacherFeedbackTemplates: TeacherFeedbackTemplate[] = [
  {
    id: 'active',
    label: '积极参与，状态很好',
    guidance: '上课积极回答问题，理解和表达都比较顺畅。',
  },
  {
    id: 'steady',
    label: '状态稳定，吸收较快',
    guidance: '课堂理解比较稳定，但还需要课后再巩固一轮。',
  },
  {
    id: 'review-soon',
    label: '精神一般，回家及时复习',
    guidance: '建议回家马上结合复习计划回忆课堂内容，避免遗忘。',
  },
  {
    id: 'needs-support',
    label: '当前吃力，需要家校配合',
    guidance: '需要家长帮助孩子尽快回顾课堂内容，并完成基础练习。',
  },
];

export function mergeRosterWithFeedbackDraft(input: {
  roster: Array<{ id: number; name: string }>;
  savedStudents: Array<{ student_id: number; name: string; selected_template_id: string; remark: string }>;
}): TeacherFeedbackStudentDraft[] {
  const savedById = new Map(input.savedStudents.map((item) => [item.student_id, item]));
  return input.roster.map((student) => {
    const restored = savedById.get(student.id);
    return {
      studentId: student.id,
      name: student.name,
      selectedTemplateId: restored?.selected_template_id ?? '',
      remark: restored?.remark ?? '',
    };
  });
}

export function buildTeacherFeedbackSavePayload(input: {
  mergedText: string;
  students: TeacherFeedbackStudentDraft[];
  customTemplates: TeacherFeedbackTemplate[];
}): TeacherFeedbackSavePayload {
  return {
    merged_text: input.mergedText,
    student_index: input.students.map((item) => ({
      student_id: item.studentId,
      name: item.name,
    })),
    students: input.students.map((item) => ({
      student_id: item.studentId,
      name: item.name,
      selected_template_id: item.selectedTemplateId,
      remark: item.remark,
    })),
    custom_templates: input.customTemplates
      .filter((item) => item.isCustom)
      .map((item) => ({
        id: item.id,
        label: item.label,
        guidance: item.guidance,
      })),
  };
}

async function callApiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const { apiFetch } = await import('./App');
  return apiFetch<T>(path, options);
}

export const listClassStudents = (classId: number) =>
  callApiFetch<{ students: Array<{ id: number; name: string }> }>(`/api/classes/${classId}/students`);

export const createClassStudent = (classId: number, name: string) =>
  callApiFetch<{ student: { id: number; name: string }; deduplicated: boolean }>(`/api/classes/${classId}/students`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  });

export const deleteClassStudent = (classId: number, studentId: number) =>
  callApiFetch<{ ok: boolean }>(`/api/classes/${classId}/students/${studentId}`, {
    method: 'DELETE',
  });

export const loadLessonFeedback = (lessonId: number) =>
  callApiFetch<LessonFeedbackDocument>(`/api/lessons/${lessonId}/feedback`);

export const saveLessonFeedback = (lessonId: number, payload: TeacherFeedbackSavePayload) =>
  callApiFetch<LessonFeedbackDocument>(`/api/lessons/${lessonId}/feedback`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });

export const generateLessonFeedbackDraft = (
  lessonId: number,
  payload: Omit<TeacherFeedbackSavePayload, 'merged_text' | 'student_index'>,
) =>
  callApiFetch<LessonFeedbackDraftResponse>(`/api/lessons/${lessonId}/feedback/draft`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
