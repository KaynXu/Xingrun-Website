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