export interface StageLabelGroup {
  group: string;
  labels: string[];
}

export interface ClassFeedbackStageNotes {
  classStatusNote: string;
  parentFeedbackNote: string;
  teachingFocusNote: string;
  nextStagePreviewNote: string;
}

export interface ClassFeedbackStudentCard {
  studentId: number;
  name: string;
  aiDraft: string;
  finalText: string;
  checked: boolean;
  sourceSummary: string;
  highlightLabels: string[];
  highlightNote: string;
}

export interface ClassFeedbackTask {
  id: number;
  class_id: number;
  teacher_user_id: number | null;
  teacher_name_snapshot: string;
  start_date: string;
  end_date: string;
  period_length_days: number;
  period_granularity: string;
  status: string;
  class_summary_ai_draft: string;
  class_summary_final_text: string;
  class_status_tags: string[];
  class_status_note: string;
  parent_feedback_note: string;
  teaching_focus_note: string;
  next_stage_preview_note: string;
  student_highlights: Array<{
    student_id: number;
    labels: string[];
    note: string;
  }>;
  student_entries: Array<{
    id?: number;
    task_id?: number;
    student_id: number;
    student_name_snapshot: string;
    ai_draft: string;
    final_text: string;
    checked_at?: string | null;
    updated_at?: string | null;
  }>;
}

export const defaultStageLabelGroups: StageLabelGroup[] = [
  { group: '课堂状态', labels: ['进入状态快', '注意力更集中', '注意力波动', '开口更主动', '开口偏少'] },
  { group: '学习表现', labels: ['基础更稳', '知识点仍卡住', '纠错后保持更好', '完整表达有进步', '应用时还不稳定'] },
  { group: '课后执行', labels: ['作业完成更稳', '作业拖延', '复习配合度提升', '家长跟进较积极', '家庭练习不足'] },
  { group: '阶段变化', labels: ['进步明显', '有点回落', '变化不大', '情绪更稳定', '需要下阶段重点关注'] },
];

export function buildClassFeedbackConfirmPayload(input: {
  classSummaryFinalText: string;
  students: ClassFeedbackStudentCard[];
}) {
  const studentEntries = input.students.map((student) => {
    if (!student.checked) {
      throw new Error('all students must be checked before confirm');
    }
    const finalText = student.finalText.trim();
    if (!finalText) {
      throw new Error('student final text is required before confirm');
    }
    return {
      student_id: student.studentId,
      final_text: finalText,
      checked_at: 'CHECKED_ON_CONFIRM',
    };
  });

  return {
    class_summary_final_text: input.classSummaryFinalText.trim(),
    student_entries: studentEntries,
  };
}

async function callApiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const { apiFetch } = await import('./App');
  return apiFetch<T>(path, options);
}

export const loadClassFeedbackLabels = () =>
  callApiFetch<{ groups: StageLabelGroup[] }>('/api/class-feedback/labels');

export const saveClassFeedbackLabels = (groups: StageLabelGroup[]) =>
  callApiFetch<{ groups: StageLabelGroup[] }>('/api/class-feedback/labels', {
    method: 'PUT',
    body: JSON.stringify({ groups }),
  });

export const createClassFeedbackTask = (payload: {
  classId: number;
  startDate: string;
  endDate: string;
}) =>
  callApiFetch<ClassFeedbackTask>('/api/class-feedback/tasks', {
    method: 'POST',
    body: JSON.stringify({
      class_id: payload.classId,
      start_date: payload.startDate,
      end_date: payload.endDate,
    }),
  });

export const loadClassFeedbackTask = (taskId: number) =>
  callApiFetch<ClassFeedbackTask>(`/api/class-feedback/tasks/${taskId}`);

export const buildClassFeedbackStudentCards = (input: {
  roster: Array<{ id: number; name: string }>;
  task: ClassFeedbackTask;
}): ClassFeedbackStudentCard[] => {
  const entriesByStudentId = new Map(input.task.student_entries.map((item) => [item.student_id, item]));
  const highlightsByStudentId = new Map(
    input.task.student_highlights.map((item) => [item.student_id, item]),
  );

  return input.roster.map((student) => {
    const entry = entriesByStudentId.get(student.id);
    const highlight = highlightsByStudentId.get(student.id);
    const aiDraft = entry?.ai_draft ?? '';
    const finalText = entry?.final_text?.trim() ? entry.final_text : aiDraft;
    return {
      studentId: student.id,
      name: student.name,
      aiDraft,
      finalText,
      checked: Boolean(entry?.checked_at),
      sourceSummary: input.task.student_entries.length > 0 ? '已汇总本阶段素材' : '等待生成本阶段草稿',
      highlightLabels: highlight?.labels ?? [],
      highlightNote: highlight?.note ?? '',
    };
  });
};

export const generateClassFeedbackTask = (
  taskId: number,
  payload: {
    classStatusTags: string[];
    classStatusNote: string;
    parentFeedbackNote: string;
    teachingFocusNote: string;
    nextStagePreviewNote: string;
    studentHighlights: Array<{ studentId: number; labels: string[]; note: string }>;
  },
) =>
  callApiFetch<ClassFeedbackTask>(`/api/class-feedback/tasks/${taskId}/generate`, {
    method: 'POST',
    body: JSON.stringify({
      class_status_tags: payload.classStatusTags,
      class_status_note: payload.classStatusNote,
      parent_feedback_note: payload.parentFeedbackNote,
      teaching_focus_note: payload.teachingFocusNote,
      next_stage_preview_note: payload.nextStagePreviewNote,
      student_highlights: payload.studentHighlights.map((item) => ({
        student_id: item.studentId,
        labels: item.labels,
        note: item.note,
      })),
    }),
  });

export const confirmClassFeedbackTask = (
  taskId: number,
  payload: ReturnType<typeof buildClassFeedbackConfirmPayload>,
) =>
  callApiFetch<ClassFeedbackTask>(`/api/class-feedback/tasks/${taskId}/confirm`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
