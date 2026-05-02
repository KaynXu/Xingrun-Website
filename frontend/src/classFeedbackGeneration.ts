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

export type ClassFeedbackPeriodGranularity = 'daily' | 'weekly' | 'monthly' | 'stage';

export type ClassFeedbackStageName = '春季' | '暑假' | '秋季' | '寒假';

export type ClassFeedbackPeriodSelection =
  | {
      periodGranularity: 'daily';
      anchorDate: string;
    }
  | {
      periodGranularity: 'weekly';
      year: number;
      week: number;
    }
  | {
      periodGranularity: 'monthly';
      year: number;
      month: number;
    }
  | {
      periodGranularity: 'stage';
      year: number;
      stageName: ClassFeedbackStageName;
    };

export type CreateClassFeedbackTaskRequest =
  | {
      class_id: number;
      period_granularity: 'daily';
      anchor_date: string;
    }
  | {
      class_id: number;
      period_granularity: 'weekly';
      year: number;
      week: number;
    }
  | {
      class_id: number;
      period_granularity: 'monthly';
      year: number;
      month: number;
    }
  | {
      class_id: number;
      period_granularity: 'stage';
      year: number;
      stage_name: ClassFeedbackStageName;
    };

export interface ClassFeedbackPeriodPreview {
  label: string;
  startDate: string;
  endDate: string;
  periodLengthDays: number;
  periodGranularity: ClassFeedbackPeriodGranularity;
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function pickString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function pickNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function pickStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

export function normalizeClassFeedbackTaskResponse(
  source: unknown,
  options: { fallbackClassId?: number } = {},
): ClassFeedbackTask | null {
  if (!isRecord(source)) {
    return null;
  }

  const id = pickNumber(source.id);
  const classId = pickNumber(source.class_id) ?? options.fallbackClassId ?? null;
  if (id === null || classId === null) {
    return null;
  }

  const studentHighlights = Array.isArray(source.student_highlights)
    ? source.student_highlights.flatMap((item) => {
        if (!isRecord(item)) {
          return [];
        }
        const studentId = pickNumber(item.student_id);
        if (studentId === null) {
          return [];
        }
        return [{
          student_id: studentId,
          labels: pickStringList(item.labels),
          note: pickString(item.note),
        }];
      })
    : [];
  const studentEntries = Array.isArray(source.student_entries)
    ? source.student_entries.flatMap((item) => {
        if (!isRecord(item)) {
          return [];
        }
        const studentId = pickNumber(item.student_id);
        if (studentId === null) {
          return [];
        }
        return [{
          id: pickNumber(item.id) ?? undefined,
          task_id: pickNumber(item.task_id) ?? undefined,
          student_id: studentId,
          student_name_snapshot: pickString(item.student_name_snapshot),
          ai_draft: pickString(item.ai_draft),
          final_text: pickString(item.final_text),
          checked_at: typeof item.checked_at === 'string' || item.checked_at === null ? item.checked_at : undefined,
          updated_at: typeof item.updated_at === 'string' || item.updated_at === null ? item.updated_at : undefined,
        }];
      })
    : [];

  return {
    id,
    class_id: classId,
    teacher_user_id: pickNumber(source.teacher_user_id),
    teacher_name_snapshot: pickString(source.teacher_name_snapshot),
    start_date: pickString(source.start_date),
    end_date: pickString(source.end_date),
    period_length_days: pickNumber(source.period_length_days) ?? 0,
    period_granularity: pickString(source.period_granularity),
    status: pickString(source.status) || 'draft',
    class_summary_ai_draft: pickString(source.class_summary_ai_draft),
    class_summary_final_text: pickString(source.class_summary_final_text),
    class_status_tags: pickStringList(source.class_status_tags),
    class_status_note: pickString(source.class_status_note),
    parent_feedback_note: pickString(source.parent_feedback_note),
    teaching_focus_note: pickString(source.teaching_focus_note),
    next_stage_preview_note: pickString(source.next_stage_preview_note),
    student_highlights: studentHighlights,
    student_entries: studentEntries,
  };
}

export function isClassFeedbackTaskGenerating(task: Pick<ClassFeedbackTask, 'status'>): boolean {
  return ['pending', 'queued', 'processing', 'generating'].includes(task.status);
}

export function hasCompleteClassFeedbackGeneratedContent(
  task: Pick<ClassFeedbackTask, 'class_summary_ai_draft' | 'class_summary_final_text' | 'student_entries'>,
  rosterSize: number,
): boolean {
  const summary = (task.class_summary_final_text.trim() || task.class_summary_ai_draft.trim());
  if (!summary || rosterSize <= 0) {
    return false;
  }

  const studentIdsWithOutput = new Set(
    task.student_entries
      .filter((item) => (item.final_text.trim() || item.ai_draft.trim()).length > 0)
      .map((item) => item.student_id),
  );
  return studentIdsWithOutput.size >= rosterSize;
}

export const defaultStageLabelGroups: StageLabelGroup[] = [
  { group: '课堂状态', labels: ['进入状态快', '注意力更集中', '注意力波动', '开口更主动', '开口偏少'] },
  { group: '学习表现', labels: ['基础更稳', '知识点仍卡住', '纠错后保持更好', '完整表达有进步', '应用时还不稳定'] },
  { group: '课后执行', labels: ['作业完成更稳', '作业拖延', '复习配合度提升', '家长跟进较积极', '家庭练习不足'] },
  { group: '阶段变化', labels: ['进步明显', '有点回落', '变化不大', '情绪更稳定', '需要下阶段重点关注'] },
];

const CLASS_FEEDBACK_MONTH_LABELS = ['', '一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'];

function parseIsoDate(value: string, fieldName: string): Date {
  const parsed = new Date(`${value}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error(`${fieldName} must be a valid ISO date`);
  }
  return parsed;
}

function formatIsoDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function getIsoWeekPartsForDate(value: Date): { year: number; week: number } {
  const thursday = new Date(value.getTime());
  const weekday = thursday.getDay() || 7;
  thursday.setDate(thursday.getDate() + 4 - weekday);

  const year = thursday.getFullYear();
  const firstThursday = new Date(`${year}-01-04T12:00:00`);
  const firstWeekday = firstThursday.getDay() || 7;
  firstThursday.setDate(firstThursday.getDate() + 4 - firstWeekday);

  const diffDays = Math.round((thursday.getTime() - firstThursday.getTime()) / 86_400_000);
  const week = Math.floor(diffDays / 7) + 1;
  return { year, week };
}

function getIsoWeekStartDate(year: number, week: number): Date {
  if (!Number.isInteger(year)) {
    throw new Error('year must be an integer');
  }
  if (!Number.isInteger(week) || week < 1 || week > 53) {
    throw new Error('week must be between 1 and 53');
  }

  const jan4 = new Date(`${year}-01-04T12:00:00`);
  const jan4Weekday = jan4.getDay() || 7;
  const weekOneMonday = new Date(jan4.getTime());
  weekOneMonday.setDate(jan4.getDate() - jan4Weekday + 1);

  const monday = new Date(weekOneMonday.getTime());
  monday.setDate(weekOneMonday.getDate() + (week - 1) * 7);

  const resolved = getIsoWeekPartsForDate(monday);
  if (resolved.year !== year || resolved.week !== week) {
    throw new Error('week is out of range for year');
  }
  return monday;
}

function getLastDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

function getStageRange(year: number, stageName: ClassFeedbackStageName): { startDate: string; endDate: string } {
  if (stageName === '春季') {
    return { startDate: `${year}-03-01`, endDate: `${year}-05-31` };
  }
  if (stageName === '暑假') {
    return { startDate: `${year}-07-01`, endDate: `${year}-08-31` };
  }
  if (stageName === '秋季') {
    return { startDate: `${year}-09-01`, endDate: `${year}-11-30` };
  }
  return {
    startDate: `${year}-01-01`,
    endDate: `${year}-02-${String(getLastDayOfMonth(year, 2)).padStart(2, '0')}`,
  };
}

export function buildClassFeedbackPeriodPreview(
  input: ClassFeedbackPeriodSelection,
): ClassFeedbackPeriodPreview {
  if (input.periodGranularity === 'daily') {
    const selectedDate = formatIsoDate(parseIsoDate(input.anchorDate, 'anchorDate'));
    return {
      label: selectedDate,
      startDate: selectedDate,
      endDate: selectedDate,
      periodLengthDays: 1,
      periodGranularity: 'daily',
    };
  }

  if (input.periodGranularity === 'weekly') {
    const monday = getIsoWeekStartDate(input.year, input.week);
    const sunday = new Date(monday.getTime());
    sunday.setDate(monday.getDate() + 6);
    return {
      label: `${input.year}第${input.week}周`,
      startDate: formatIsoDate(monday),
      endDate: formatIsoDate(sunday),
      periodLengthDays: 7,
      periodGranularity: 'weekly',
    };
  }

  if (input.periodGranularity === 'monthly') {
    if (!Number.isInteger(input.year)) {
      throw new Error('year must be an integer');
    }
    if (!Number.isInteger(input.month) || input.month < 1 || input.month > 12) {
      throw new Error('month must be between 1 and 12');
    }
    const startDate = `${input.year}-${String(input.month).padStart(2, '0')}-01`;
    const endDate = `${input.year}-${String(input.month).padStart(2, '0')}-${String(getLastDayOfMonth(input.year, input.month)).padStart(2, '0')}`;
    return {
      label: `${input.year}${CLASS_FEEDBACK_MONTH_LABELS[input.month]}`,
      startDate,
      endDate,
      periodLengthDays: getLastDayOfMonth(input.year, input.month),
      periodGranularity: 'monthly',
    };
  }

  const { startDate, endDate } = getStageRange(input.year, input.stageName);
  const start = parseIsoDate(startDate, 'stageStartDate');
  const end = parseIsoDate(endDate, 'stageEndDate');
  return {
    label: `${input.year}${input.stageName}`,
    startDate,
    endDate,
    periodLengthDays: Math.round((end.getTime() - start.getTime()) / 86_400_000) + 1,
    periodGranularity: 'stage',
  };
}

export function buildCreateClassFeedbackTaskRequest(
  input: { classId: number } & ClassFeedbackPeriodSelection,
): CreateClassFeedbackTaskRequest {
  if (input.periodGranularity === 'daily') {
    return {
      class_id: input.classId,
      period_granularity: 'daily',
      anchor_date: formatIsoDate(parseIsoDate(input.anchorDate, 'anchorDate')),
    };
  }

  if (input.periodGranularity === 'weekly') {
    getIsoWeekStartDate(input.year, input.week);
    return {
      class_id: input.classId,
      period_granularity: 'weekly',
      year: input.year,
      week: input.week,
    };
  }

  if (input.periodGranularity === 'monthly') {
    if (!Number.isInteger(input.month) || input.month < 1 || input.month > 12) {
      throw new Error('month must be between 1 and 12');
    }
    return {
      class_id: input.classId,
      period_granularity: 'monthly',
      year: input.year,
      month: input.month,
    };
  }

  return {
    class_id: input.classId,
    period_granularity: 'stage',
    year: input.year,
    stage_name: input.stageName,
  };
}

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
    };
  });

  return {
    class_summary_final_text: input.classSummaryFinalText.trim(),
    student_entries: studentEntries,
  };
}

export function formatClassFeedbackStudentCopyText(students: ClassFeedbackStudentCard[]): string {
  return students
    .map((student) => {
      const text = (student.finalText || student.aiDraft).trim();
      if (!text) {
        return '';
      }
      return `【${student.name}】\n${text}`;
    })
    .filter((item) => item.trim())
    .join('\n\n');
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
  callApiFetch<{ ok: boolean; removed: boolean }>(`/api/classes/${classId}/students/${studentId}`, {
    method: 'DELETE',
  });

export const loadClassFeedbackLabels = () =>
  callApiFetch<{ groups: StageLabelGroup[] }>('/api/class-feedback/labels');

export const saveClassFeedbackLabels = (groups: StageLabelGroup[]) =>
  callApiFetch<{ groups: StageLabelGroup[] }>('/api/class-feedback/labels', {
    method: 'PUT',
    body: JSON.stringify({ groups }),
  });

export const createClassFeedbackTask = (payload: CreateClassFeedbackTaskRequest) =>
  callApiFetch<ClassFeedbackTask>('/api/class-feedback/tasks', {
    method: 'POST',
    body: JSON.stringify(payload),
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

export const saveClassFeedbackTaskDraft = (
  taskId: number,
  payload: {
    classSummaryDraftText: string;
    studentEntries: Array<{ studentId: number; finalText: string }>;
  },
) =>
  callApiFetch<ClassFeedbackTask>(`/api/class-feedback/tasks/${taskId}/draft`, {
    method: 'POST',
    body: JSON.stringify({
      class_summary_draft_text: payload.classSummaryDraftText,
      student_entries: payload.studentEntries.map((item) => ({
        student_id: item.studentId,
        final_text: item.finalText,
      })),
    }),
  });
