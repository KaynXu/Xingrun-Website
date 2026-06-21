export interface ReviewLessonRecord {
  id: number;
  date: string;
  subject: string;
  grade: string;
  topic: string;
  summary: string;
  weak_points: string;
  pdf_path: string;
  class_id: number | null;
  created_at: string;
  created_by_user_id?: number | null;
  creator_display_name?: string;
  creator_username?: string;
  record_status?: string;
  generation_error?: string;
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

export function normalizeReviewLessonsResponse(payload: unknown): ReviewLessonRecord[] {
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
      pdf_path: pickString(item.pdf_path),
      class_id: pickNullableNumber(item.class_id),
      created_at: pickString(item.created_at),
      created_by_user_id: pickNullableNumber(item.created_by_user_id),
      creator_display_name: pickString(item.creator_display_name),
      creator_username: pickString(item.creator_username),
      record_status: pickString(item.record_status),
      generation_error: pickString(item.generation_error),
    }];
  });
}

export function hasReviewLessonOutput(lesson: Pick<ReviewLessonRecord, 'pdf_path'>): boolean {
  return lesson.pdf_path.trim().length > 0;
}

export function getReviewLessonTaskState(
  lesson: Pick<ReviewLessonRecord, 'record_status' | 'pdf_path'>,
): ReviewLessonTaskState {
  const status = lesson.record_status?.trim() ?? '';
  if (['pending', 'queued', 'processing', 'transcribing', 'generating'].includes(status)) {
    return 'pending';
  }
  if (status === 'failed' || status === 'expired') {
    return 'failed';
  }
  if (hasReviewLessonOutput(lesson)) {
    return 'ready';
  }
  if (status === 'ready') {
    return 'missing-output';
  }
  return 'empty';
}

export function isReviewLessonPending(lesson: Pick<ReviewLessonRecord, 'record_status' | 'pdf_path'>): boolean {
  return getReviewLessonTaskState(lesson) === 'pending';
}

export function getReviewLessonTaskMessage(
  lesson: Pick<ReviewLessonRecord, 'record_status' | 'generation_error' | 'pdf_path'>,
): string {
  const state = getReviewLessonTaskState(lesson);
  if (state === 'pending') {
    const status = lesson.record_status?.trim() ?? '';
    if (status === 'transcribing') {
      return '录音已上传，正在转写';
    }
    if (status === 'generating') {
      return '转写完成，正在生成复习计划';
    }
    return '正在生成复习计划，可离开页面';
  }
  if (state === 'failed') {
    if (lesson.record_status === 'expired') {
      return '生成任务已过期，请重新生成';
    }
    return lesson.generation_error?.trim() || '生成失败';
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
  lesson: Pick<ReviewLessonRecord, 'record_status' | 'pdf_path' | 'created_at'>,
  options: ReviewLessonProgressOptions = {},
): number {
  const status = lesson.record_status?.trim() ?? '';
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

  const startedAtMs = options.startedAtMs ?? parseStartedAtMs(lesson.created_at);
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
