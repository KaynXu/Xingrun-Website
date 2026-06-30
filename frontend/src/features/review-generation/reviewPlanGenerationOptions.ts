export type ReviewPlanScheduleMode = 'standard' | 'compressed' | 'daily' | 'custom';

export type ReviewPlanGenerationOptionsFormValue = {
  scheduleMode: ReviewPlanScheduleMode;
  dailyCount: number;
  customDays: string;
  userRequirements: string;
};

export type ReviewPlanGenerationOptionsPayload = {
  schedule_mode: ReviewPlanScheduleMode;
  review_days?: number[] | string;
  daily_count?: number | null;
  user_requirements: string;
};

export type StoredReviewPlanGenerationOptions = {
  schedule_mode?: string;
  review_days?: unknown;
  daily_count?: unknown;
  user_requirements?: unknown;
};

export const DEFAULT_REVIEW_PLAN_GENERATION_OPTIONS: ReviewPlanGenerationOptionsFormValue = {
  scheduleMode: 'standard',
  dailyCount: 7,
  customDays: '1,2,7,14,30',
  userRequirements: '',
};

export function formValueFromGenerationOptions(value: StoredReviewPlanGenerationOptions | null | undefined): ReviewPlanGenerationOptionsFormValue {
  if (!value) {
    return { ...DEFAULT_REVIEW_PLAN_GENERATION_OPTIONS };
  }
  const mode = (
    value.schedule_mode === 'compressed'
    || value.schedule_mode === 'daily'
    || value.schedule_mode === 'custom'
  ) ? value.schedule_mode : 'standard';
  const reviewDays = Array.isArray(value.review_days)
    ? value.review_days.filter((item): item is number => typeof item === 'number' && Number.isInteger(item) && item > 0)
    : [];
  const dailyCount = typeof value.daily_count === 'number' && Number.isInteger(value.daily_count) && value.daily_count > 0
    ? value.daily_count
    : Math.max(1, reviewDays.length || DEFAULT_REVIEW_PLAN_GENERATION_OPTIONS.dailyCount);

  return {
    scheduleMode: mode,
    dailyCount,
    customDays: reviewDays.length ? reviewDays.join(',') : DEFAULT_REVIEW_PLAN_GENERATION_OPTIONS.customDays,
    userRequirements: typeof value.user_requirements === 'string' ? value.user_requirements : '',
  };
}

export function buildGenerationOptionsPayload(value: ReviewPlanGenerationOptionsFormValue): ReviewPlanGenerationOptionsPayload {
  if (value.scheduleMode === 'compressed') {
    return {
      schedule_mode: 'compressed',
      daily_count: 1,
      user_requirements: value.userRequirements.trim(),
    };
  }
  if (value.scheduleMode === 'daily') {
    return {
      schedule_mode: 'daily',
      daily_count: value.dailyCount,
      user_requirements: value.userRequirements.trim(),
    };
  }
  if (value.scheduleMode === 'custom') {
    return {
      schedule_mode: 'custom',
      review_days: value.customDays,
      user_requirements: value.userRequirements.trim(),
    };
  }
  return {
    schedule_mode: 'standard',
    user_requirements: value.userRequirements.trim(),
  };
}

export function getGenerationOptionsFormSummary(value: ReviewPlanGenerationOptionsFormValue): string {
  if (value.scheduleMode === 'compressed') {
    return '压缩 1 天';
  }
  if (value.scheduleMode === 'daily') {
    return `连续 ${value.dailyCount} 天`;
  }
  if (value.scheduleMode === 'custom') {
    return `自定义 ${value.customDays.trim() || '未填写'}`;
  }
  return '标准 5 次';
}
