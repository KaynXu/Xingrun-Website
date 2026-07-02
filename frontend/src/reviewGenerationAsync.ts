export interface ReviewLessonRecord {
  id: number;
  date: string;
  subject: string;
  grade: string;
  topic: string;
  summary: string;
  weak_points: string;
  class_id: number | null;
  created_at: string;
  updated_at?: string;
  created_by_user_id?: number | null;
  creator_display_name?: string;
  creator_username?: string;
  current_version_id: number | null;
  current_version_no: number | null;
  current_generated_at: string;
  current_pdf_url: string;
  current_download_url: string;
  current_status: string;
  has_version_generating: boolean;
  active_version_status: string;
  active_version_created_at: string;
  latest_generation_error: string;
  pdf_path: string;
  record_status?: string;
  generation_error?: string;
  review_generation_options?: Record<string, unknown> | null;
  review_generation_summary?: string;
}

export interface ReviewLessonsPage {
  items: ReviewLessonRecord[];
  total: number;
  page: number;
  page_size: number;
}

export type ReviewLessonTaskState = 'pending' | 'failed' | 'ready' | 'missing-output' | 'empty';

export type ReviewLessonProgressOptions = {
  nowMs?: number;
  startedAtMs?: number;
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

function pickBoolean(value: unknown): boolean {
  return value === true;
}

function pickRecord(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null;
}

function pickTaskStatus(lesson: Pick<ReviewLessonRecord, 'active_version_status' | 'record_status'>): string {
  return lesson.active_version_status.trim() || lesson.record_status?.trim() || '';
}

function normalizeReviewLessonItems(payload: unknown): ReviewLessonRecord[] {
  if (!Array.isArray(payload)) {
    return [];
  }

  return payload.flatMap((item) => {
    if (!isRecord(item) || typeof item.id !== 'number' || !Number.isFinite(item.id)) {
      return [];
    }

    return [{
      id: item.id,
      date: pickString(item.date),
      subject: pickString(item.subject),
      grade: pickString(item.grade),
      topic: pickString(item.topic),
      summary: pickString(item.summary),
      weak_points: pickString(item.weak_points),
      class_id: pickNullableNumber(item.class_id),
      created_at: pickString(item.created_at),
      updated_at: pickString(item.updated_at),
      created_by_user_id: pickNullableNumber(item.created_by_user_id),
      creator_display_name: pickString(item.creator_display_name),
      creator_username: pickString(item.creator_username),
      current_version_id: pickNullableNumber(item.current_version_id),
      current_version_no: pickNullableNumber(item.current_version_no),
      current_generated_at: pickString(item.current_generated_at),
      current_pdf_url: pickString(item.current_pdf_url),
      current_download_url: pickString(item.current_download_url),
      current_status: pickString(item.current_status),
      has_version_generating: pickBoolean(item.has_version_generating),
      active_version_status: pickString(item.active_version_status),
      active_version_created_at: pickString(item.active_version_created_at),
      latest_generation_error: pickString(item.latest_generation_error),
      pdf_path: pickString(item.pdf_path),
      record_status: pickString(item.record_status),
      generation_error: pickString(item.generation_error),
      review_generation_options: pickRecord(item.review_generation_options),
      review_generation_summary: pickString(item.review_generation_summary),
    }];
  });
}

export function normalizeReviewLessonsPageResponse(payload: unknown): ReviewLessonsPage {
  if (!isRecord(payload)) {
    const items = normalizeReviewLessonItems(payload);
    return {
      items,
      total: items.length,
      page: 1,
      page_size: items.length,
    };
  }

  const items = normalizeReviewLessonItems(payload.items);
  const total = typeof payload.total === 'number' && Number.isFinite(payload.total)
    ? Math.max(0, Math.floor(payload.total))
    : items.length;
  const page = typeof payload.page === 'number' && Number.isFinite(payload.page)
    ? Math.max(1, Math.floor(payload.page))
    : 1;
  const pageSize = typeof payload.page_size === 'number' && Number.isFinite(payload.page_size)
    ? Math.max(1, Math.floor(payload.page_size))
    : Math.max(1, items.length);

  return {
    items,
    total,
    page,
    page_size: pageSize,
  };
}

export function normalizeReviewLessonsResponse(payload: unknown): ReviewLessonRecord[] {
  return normalizeReviewLessonsPageResponse(payload).items;
}

export function hasReviewLessonOutput(
  lesson: Pick<ReviewLessonRecord, 'current_pdf_url' | 'current_download_url' | 'pdf_path'>,
): boolean {
  return Boolean(
    lesson.current_pdf_url.trim()
    || lesson.current_download_url.trim()
    || lesson.pdf_path.trim(),
  );
}

export function getReviewLessonTaskState(
  lesson: Pick<
    ReviewLessonRecord,
    'has_version_generating' | 'active_version_status' | 'record_status' | 'current_status' | 'current_pdf_url' | 'current_download_url' | 'pdf_path' | 'latest_generation_error' | 'generation_error'
  >,
): ReviewLessonTaskState {
  const status = pickTaskStatus(lesson);
  if (lesson.has_version_generating || ['pending', 'queued', 'processing', 'transcribing', 'generating'].includes(status)) {
    return 'pending';
  }
  if (hasReviewLessonOutput(lesson)) {
    return 'ready';
  }
  if (lesson.latest_generation_error.trim() || ['failed', 'expired'].includes(status) || lesson.generation_error?.trim()) {
    return 'failed';
  }
  if (lesson.current_status.trim() === 'ready') {
    return 'missing-output';
  }
  return 'empty';
}

export function isReviewLessonPending(
  lesson: Pick<
    ReviewLessonRecord,
    'has_version_generating' | 'active_version_status' | 'record_status' | 'current_status' | 'current_pdf_url' | 'current_download_url' | 'pdf_path' | 'latest_generation_error' | 'generation_error'
  >,
): boolean {
  return getReviewLessonTaskState(lesson) === 'pending';
}

export function getReviewLessonTaskMessage(
  lesson: Pick<
    ReviewLessonRecord,
    'has_version_generating' | 'active_version_status' | 'record_status' | 'current_status' | 'current_pdf_url' | 'current_download_url' | 'pdf_path' | 'latest_generation_error' | 'generation_error'
  >,
): string {
  const state = getReviewLessonTaskState(lesson);
  if (state === 'pending') {
    const status = pickTaskStatus(lesson);
    const hasCurrentOutput = hasReviewLessonOutput(lesson);
    if (status === 'transcribing') {
      return hasCurrentOutput ? '新版录音转写中，当前 PDF 可继续使用' : '录音已上传，正在转写';
    }
    if (hasCurrentOutput) {
      return '正在生成新版，当前 PDF 可继续使用';
    }
    return '正在生成复习计划，可离开页面';
  }
  if (state === 'failed') {
    if (lesson.record_status?.trim() === 'expired' && !lesson.latest_generation_error.trim()) {
      return '生成任务已过期，请重新生成';
    }
    return lesson.latest_generation_error.trim() || lesson.generation_error?.trim() || '生成失败';
  }
  if (state === 'missing-output') {
    return '生成结果缺少 PDF，请刷新后重试';
  }
  return '';
}

function clampProgress(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function progressBetween(start: number, end: number, elapsedMs: number, durationMs: number): number {
  if (elapsedMs <= 0) {
    return start;
  }
  const ratio = Math.min(1, elapsedMs / durationMs);
  return clampProgress(start + (end - start) * ratio);
}

function parseStartedAtMs(value: unknown): number | null {
  if (typeof value !== 'string' || !value.trim()) {
    return null;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function getReviewLessonTaskProgress(
  lesson: Pick<
    ReviewLessonRecord,
    'active_version_status' | 'record_status' | 'active_version_created_at' | 'has_version_generating' | 'current_pdf_url' | 'current_download_url' | 'pdf_path' | 'created_at' | 'latest_generation_error' | 'generation_error' | 'current_status'
  >,
  options: ReviewLessonProgressOptions = {},
): number {
  const status = pickTaskStatus(lesson);
  const state = getReviewLessonTaskState(lesson);
  if (state === 'ready') {
    return 100;
  }
  if (state === 'failed' || state === 'missing-output' || state === 'empty') {
    return 0;
  }

  const fixedProgress = (() => {
    if (status === 'transcribing') {
      return 45;
    }
    if (status === 'generating') {
      return 78;
    }
    if (['pending', 'queued', 'processing'].includes(status)) {
      return 68;
    }
    return 0;
  })();

  if (options.nowMs === undefined) {
    return fixedProgress;
  }

  const startedAtMs = options.startedAtMs ?? parseStartedAtMs(lesson.active_version_created_at || lesson.created_at);
  if (startedAtMs === null) {
    return fixedProgress;
  }

  const elapsedMs = Math.max(0, options.nowMs - startedAtMs);
  if (status === 'transcribing') {
    return progressBetween(14, 48, elapsedMs, 90_000);
  }
  if (status === 'generating') {
    return progressBetween(62, 94, elapsedMs, 240_000);
  }
  if (status === 'processing') {
    return progressBetween(46, 74, elapsedMs, 120_000);
  }
  if (['pending', 'queued'].includes(status)) {
    return progressBetween(18, 58, elapsedMs, 90_000);
  }
  return fixedProgress;
}
