import { buildAuthedPath } from '../../workspaceShared';
import type { StoredReviewPlanGenerationOptions } from './reviewPlanGenerationOptions';

export type ReviewPlanVersionStatus =
  | ''
  | 'pending'
  | 'queued'
  | 'processing'
  | 'transcribing'
  | 'generating'
  | 'ready'
  | 'failed'
  | 'expired';

export type ReviewPlanVersionRecord = {
  id: number;
  lesson_id: number | null;
  version_no: number | null;
  status: ReviewPlanVersionStatus;
  pdf_available: boolean;
  pdf_url: string;
  download_url: string;
  generation_error: string;
  generation_options: StoredReviewPlanGenerationOptions | null;
  generation_summary: string;
  created_at: string;
  updated_at: string;
  completed_at: string;
};

export type ReviewPlanPreviewMathBlock = {
  id: string;
  latex: string;
  display: boolean;
};

export type ReviewPlanPreviewQuestion = {
  type: string;
  question: string;
  options: string[];
  answer: string;
};

export type ReviewPlanPreviewDay = {
  day: string;
  label: string;
  goal: string;
  focus: string;
  questions: ReviewPlanPreviewQuestion[];
};

export type ReviewPlanPreviewRecord = {
  title: string;
  summary: string;
  math_blocks: ReviewPlanPreviewMathBlock[];
  days: ReviewPlanPreviewDay[];
};

export type ReviewPlanDetailRecord = {
  id: number;
  date: string;
  subject: string;
  grade: string;
  topic: string;
  summary: string;
  weak_points: string;
  created_at: string;
  current_version_id: number | null;
  current_version_no: number | null;
  current_generated_at: string;
  current_pdf_url: string;
  current_download_url: string;
  current_status: ReviewPlanVersionStatus;
  has_version_generating: boolean;
  active_version_status: ReviewPlanVersionStatus;
  latest_generation_error: string;
  review_generation_options: StoredReviewPlanGenerationOptions | null;
  review_generation_summary: string;
  current_plan_preview: ReviewPlanPreviewRecord;
  versions: ReviewPlanVersionRecord[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function pickString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function pickNullableNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function pickStatus(value: unknown): ReviewPlanVersionStatus {
  const status = pickString(value);
  if (
    status === 'pending'
    || status === 'queued'
    || status === 'processing'
    || status === 'transcribing'
    || status === 'generating'
    || status === 'ready'
    || status === 'failed'
    || status === 'expired'
  ) {
    return status;
  }
  return '';
}

function pickRecord(value: unknown): StoredReviewPlanGenerationOptions | null {
  return isRecord(value) ? value : null;
}

function normalizePlanPreview(payload: unknown): ReviewPlanPreviewRecord {
  if (!isRecord(payload)) {
    return { title: '', summary: '', math_blocks: [], days: [] };
  }

  const mathBlocks = Array.isArray(payload.math_blocks)
    ? payload.math_blocks.flatMap((item) => {
      if (!isRecord(item)) {
        return [];
      }
      const latex = pickString(item.latex);
      if (!latex.trim()) {
        return [];
      }
      return [{
        id: pickString(item.id),
        latex,
        display: item.display === true,
      }];
    })
    : [];

  const days = Array.isArray(payload.days)
    ? payload.days.flatMap((item) => {
      if (!isRecord(item)) {
        return [];
      }
      const questions = Array.isArray(item.questions)
        ? item.questions.flatMap((question) => {
          if (!isRecord(question)) {
            return [];
          }
          return [{
            type: pickString(question.type),
            question: pickString(question.question),
            options: Array.isArray(question.options) ? question.options.map(pickString).filter(Boolean) : [],
            answer: pickString(question.answer),
          }];
        })
        : [];
      return [{
        day: pickString(item.day),
        label: pickString(item.label),
        goal: pickString(item.goal),
        focus: pickString(item.focus),
        questions,
      }];
    })
    : [];

  return {
    title: pickString(payload.title),
    summary: pickString(payload.summary),
    math_blocks: mathBlocks,
    days,
  };
}

function normalizeReviewPlanVersion(item: unknown): ReviewPlanVersionRecord | null {
  if (!isRecord(item) || typeof item.id !== 'number' || !Number.isFinite(item.id)) {
    return null;
  }

  return {
    id: item.id,
    lesson_id: pickNullableNumber(item.lesson_id),
    version_no: pickNullableNumber(item.version_no),
    status: pickStatus(item.status),
    pdf_available: item.pdf_available === true,
    pdf_url: pickString(item.pdf_url),
    download_url: pickString(item.download_url),
    generation_error: pickString(item.generation_error),
    generation_options: pickRecord(item.generation_options),
    generation_summary: pickString(item.generation_summary),
    created_at: pickString(item.created_at),
    updated_at: pickString(item.updated_at),
    completed_at: pickString(item.completed_at),
  };
}

export function normalizeReviewPlanDetail(payload: unknown): ReviewPlanDetailRecord | null {
  if (!isRecord(payload) || typeof payload.id !== 'number' || !Number.isFinite(payload.id)) {
    return null;
  }

  const versions = Array.isArray(payload.versions)
    ? payload.versions.flatMap((item) => {
      const version = normalizeReviewPlanVersion(item);
      return version ? [version] : [];
    })
    : [];

  return {
    id: payload.id,
    date: pickString(payload.date),
    subject: pickString(payload.subject),
    grade: pickString(payload.grade),
    topic: pickString(payload.topic),
    summary: pickString(payload.summary),
    weak_points: pickString(payload.weak_points),
    created_at: pickString(payload.created_at),
    current_version_id: pickNullableNumber(payload.current_version_id),
    current_version_no: pickNullableNumber(payload.current_version_no),
    current_generated_at: pickString(payload.current_generated_at),
    current_pdf_url: pickString(payload.current_pdf_url),
    current_download_url: pickString(payload.current_download_url),
    current_status: pickStatus(payload.current_status),
    has_version_generating: payload.has_version_generating === true,
    active_version_status: pickStatus(payload.active_version_status),
    latest_generation_error: pickString(payload.latest_generation_error),
    review_generation_options: pickRecord(payload.review_generation_options),
    review_generation_summary: pickString(payload.review_generation_summary),
    current_plan_preview: normalizePlanPreview(payload.current_plan_preview),
    versions,
  };
}

export function getReviewPlanVersionLabel(status: ReviewPlanVersionStatus): string {
  if (status === 'ready') {
    return '已生成';
  }
  if (status === 'failed') {
    return '失败';
  }
  if (status === 'transcribing') {
    return '转写中';
  }
  return '生成中';
}

export function canMakeReviewPlanVersionCurrent(
  detail: ReviewPlanDetailRecord,
  version: ReviewPlanVersionRecord,
): boolean {
  return version.status === 'ready' && version.pdf_available === true && version.id !== detail.current_version_id;
}

export function authedReviewPlanUrl(path: string): string {
  return buildAuthedPath(path);
}
