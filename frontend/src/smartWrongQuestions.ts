export interface WrongQuestionAnalysis {
  questionCategory: string;
  errorType: string;
  knowledgePoints: string[];
  isRepeatedMistake?: string;
  teacherPriority?: string;
  selectedErrorType?: string;
  selectedKnowledgePoints?: string[];
  selectedActions?: string[];
  selectedReasons?: string[];
  studentNote?: string;
}

export interface WrongQuestionRecord {
  id: string;
  studentName: string;
  className: string;
  subject: string;
  teacherName: string;
  createdAt: string;
  imageUrl?: string;
  analysis: WrongQuestionAnalysis;
}

export interface WrongQuestionFilters {
  studentName?: string;
  className?: string;
  subject?: string;
  teacherName?: string;
  errorType?: string;
  onlyPendingReview?: boolean;
}

export interface WrongQuestionSummary {
  totalCount: number;
  repeatedMistakeCount: number;
  highPriorityCount: number;
  pendingReviewCount: number;
}

export interface WrongQuestionListApiResponse {
  items?: unknown[];
  summary?: unknown;
  total?: unknown;
}

export interface NormalizedWrongQuestionListResponse {
  items: WrongQuestionRecord[];
  summary: WrongQuestionSummary;
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function pickStringValue(source: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = source[key];
    if (typeof value === 'string') {
      return value.trim();
    }
  }

  return '';
}

function pickNumberValue(source: Record<string, unknown>, keys: string[]): number | null {
  for (const key of keys) {
    const value = source[key];
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === 'string') {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }

  return null;
}

function pickStringArrayValue(source: Record<string, unknown>, keys: string[]): string[] {
  for (const key of keys) {
    const value = source[key];
    if (!Array.isArray(value)) {
      continue;
    }

    return value
      .filter((item): item is string => typeof item === 'string')
      .map((item) => item.trim())
      .filter(Boolean);
  }

  return [];
}

function normalizeWrongQuestionAnalysis(rawAnalysis: unknown): WrongQuestionAnalysis {
  const source = isObjectRecord(rawAnalysis) ? rawAnalysis : {};
  const selectedKnowledgePoints = pickStringArrayValue(source, ['selectedKnowledgePoints', 'selected_knowledge_points']);
  const selectedActions = pickStringArrayValue(source, ['selectedActions', 'selected_actions']);
  const selectedReasons = pickStringArrayValue(source, ['selectedReasons', 'selected_reasons']);
  const selectedErrorType = pickStringValue(source, ['selectedErrorType', 'selected_error_type']);
  const studentNote = pickStringValue(source, ['studentNote', 'student_note']);

  const analysis: WrongQuestionAnalysis = {
    questionCategory: pickStringValue(source, ['questionCategory', 'question_category']),
    errorType: pickStringValue(source, ['errorType', 'error_type']),
    knowledgePoints: pickStringArrayValue(source, ['knowledgePoints', 'knowledge_points']),
  };

  const isRepeatedMistake = pickStringValue(source, ['isRepeatedMistake', 'is_repeated_mistake']);
  const teacherPriority = pickStringValue(source, ['teacherPriority', 'teacher_priority']);

  if (isRepeatedMistake) {
    analysis.isRepeatedMistake = isRepeatedMistake;
  }

  if (teacherPriority) {
    analysis.teacherPriority = teacherPriority;
  }

  if (selectedErrorType) {
    analysis.selectedErrorType = selectedErrorType;
  }

  if (selectedKnowledgePoints.length > 0) {
    analysis.selectedKnowledgePoints = selectedKnowledgePoints;
  }

  if (selectedActions.length > 0) {
    analysis.selectedActions = selectedActions;
  }

  if (selectedReasons.length > 0) {
    analysis.selectedReasons = selectedReasons;
  }

  if (studentNote) {
    analysis.studentNote = studentNote;
  }

  return analysis;
}

export function normalizeWrongQuestionRecord(rawRecord: unknown, fallbackIndex = 0): WrongQuestionRecord {
  const source = isObjectRecord(rawRecord) ? rawRecord : {};
  const rawId = source.id;

  return {
    id: typeof rawId === 'string' || typeof rawId === 'number' ? String(rawId) : `wrong-question-${fallbackIndex}`,
    studentName: pickStringValue(source, ['studentName', 'student_name', 'studentNickname', 'student_nickname']),
    className: pickStringValue(source, ['className', 'class_name']),
    subject: pickStringValue(source, ['subject']),
    teacherName: pickStringValue(source, ['teacherName', 'teacher_name']),
    createdAt: pickStringValue(source, ['createdAt', 'created_at']),
    imageUrl: pickStringValue(source, ['imageUrl', 'image_url']),
    analysis: normalizeWrongQuestionAnalysis(source.analysis),
  };
}

function normalizeWrongQuestionSummary(rawSummary: unknown, fallback: WrongQuestionSummary, totalOverride: unknown): WrongQuestionSummary {
  const source = isObjectRecord(rawSummary) ? rawSummary : {};
  const normalizedTotalOverride = typeof totalOverride === 'number' && Number.isFinite(totalOverride)
    ? totalOverride
    : typeof totalOverride === 'string'
      ? Number(totalOverride)
      : null;

  return {
    totalCount: (normalizedTotalOverride !== null && Number.isFinite(normalizedTotalOverride)
      ? normalizedTotalOverride
      : pickNumberValue(source, ['totalCount', 'total_count'])) ?? fallback.totalCount,
    repeatedMistakeCount: pickNumberValue(source, ['repeatedMistakeCount', 'repeated_mistake_count']) ?? fallback.repeatedMistakeCount,
    highPriorityCount: pickNumberValue(source, ['highPriorityCount', 'high_priority_count']) ?? fallback.highPriorityCount,
    pendingReviewCount: pickNumberValue(source, ['pendingReviewCount', 'pending_review_count']) ?? fallback.pendingReviewCount,
  };
}

export function normalizeWrongQuestionListResponse(payload: WrongQuestionListApiResponse | WrongQuestionRecord[]): NormalizedWrongQuestionListResponse {
  const source = Array.isArray(payload) ? { items: payload } : payload;
  const rawItems = Array.isArray(source.items) ? source.items : [];
  const items = rawItems.map((item, index) => normalizeWrongQuestionRecord(item, index));
  const fallbackSummary = summarizeWrongQuestionRecords(items);

  return {
    items,
    summary: normalizeWrongQuestionSummary(source.summary, fallbackSummary, source.total),
  };
}

function hasTeacherReview(analysis: WrongQuestionAnalysis): boolean {
  return Boolean(analysis.selectedErrorType?.trim());
}

function isRepeatedMistake(value?: string): boolean {
  const normalized = value?.trim();
  return Boolean(normalized && normalized !== '否');
}

export function summarizeWrongQuestionRecords(records: WrongQuestionRecord[]): WrongQuestionSummary {
  return records.reduce<WrongQuestionSummary>((summary, record) => {
    const nextSummary = {
      ...summary,
      totalCount: summary.totalCount + 1,
    };

    if (isRepeatedMistake(record.analysis.isRepeatedMistake)) {
      nextSummary.repeatedMistakeCount += 1;
    }

    if (record.analysis.teacherPriority?.trim() === '高') {
      nextSummary.highPriorityCount += 1;
    }

    if (!hasTeacherReview(record.analysis)) {
      nextSummary.pendingReviewCount += 1;
    }

    return nextSummary;
  }, {
    totalCount: 0,
    repeatedMistakeCount: 0,
    highPriorityCount: 0,
    pendingReviewCount: 0,
  });
}

export function buildWrongQuestionQuery(filters: WrongQuestionFilters): string {
  const parts: string[] = [];

  for (const [key, value] of Object.entries(filters)) {
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (trimmed) {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(trimmed)}`);
      }
      continue;
    }

    if (value === true) {
      parts.push(`${encodeURIComponent(key)}=true`);
    }
  }

  return parts.length > 0 ? `?${parts.join('&')}` : '';
}