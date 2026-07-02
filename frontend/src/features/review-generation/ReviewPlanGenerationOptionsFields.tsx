import { CalendarDays, ListChecks, MessageSquareText } from 'lucide-react';

import { cn, workspaceFieldClass } from '../../workspaceShared';
import type { ReviewPlanGenerationOptionsFormValue, ReviewPlanScheduleMode } from './reviewPlanGenerationOptions';
import { getGenerationOptionsFormSummary, getGenerationOptionsValidationError, parseCustomReviewDays } from './reviewPlanGenerationOptions';

const scheduleModes: Array<{ value: ReviewPlanScheduleMode; label: string }> = [
  { value: 'standard', label: '5次间隔复习' },
  { value: 'compressed', label: '当天课后复习' },
  { value: 'daily', label: '每日连续复习' },
  { value: 'custom', label: '自定义日期' },
];

export function ReviewPlanGenerationOptionsFields({
  value,
  onChange,
  showUserRequirements = true,
}: {
  value: ReviewPlanGenerationOptionsFormValue;
  onChange: (value: ReviewPlanGenerationOptionsFormValue) => void;
  showUserRequirements?: boolean;
}) {
  const update = (patch: Partial<ReviewPlanGenerationOptionsFormValue>) => {
    onChange({ ...value, ...patch });
  };
  const customDayCount = parseCustomReviewDays(value.customDays).length;
  const validationError = getGenerationOptionsValidationError(value);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-white">
          <CalendarDays size={16} className="text-sky-500" />
          生成设置
        </div>
        <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
          {getGenerationOptionsFormSummary(value)}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {scheduleModes.map((mode) => (
          <button
            key={mode.value}
            type="button"
            onClick={() => update({ scheduleMode: mode.value })}
            className={cn(
              'h-10 rounded-xl border px-3 text-sm font-medium transition-colors',
              value.scheduleMode === mode.value
                ? 'border-slate-900 bg-slate-900 text-white dark:border-white dark:bg-white dark:text-slate-950'
                : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white',
            )}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {value.scheduleMode === 'daily' && (
        <label className="block">
          <span className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
            <ListChecks size={14} />
            天数
          </span>
          <input
            type="number"
            min={1}
            max={30}
            value={value.dailyCount}
            onChange={(event) => update({ dailyCount: Math.max(1, Math.min(30, Number(event.target.value) || 1)) })}
            className={`${workspaceFieldClass} w-full border-slate-200 focus:border-slate-300 focus:ring-slate-100`}
          />
        </label>
      )}

      {value.scheduleMode === 'custom' && (
        <label className="block">
          <span className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
            <ListChecks size={14} />
            日期点
          </span>
          <input
            type="text"
            value={value.customDays}
            onChange={(event) => update({ customDays: event.target.value })}
            placeholder="1,3,7"
            required
            aria-invalid={!customDayCount}
            className={`${workspaceFieldClass} w-full border-slate-200 focus:border-slate-300 focus:ring-slate-100`}
          />
          {validationError && (
            <span className="mt-2 block text-xs font-medium text-rose-600 dark:text-rose-300">
              {validationError}
            </span>
          )}
        </label>
      )}

      {showUserRequirements && (
        <label className="block">
          <span className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
            <MessageSquareText size={14} />
            本次要求
          </span>
          <textarea
            value={value.userRequirements}
            onChange={(event) => update({ userRequirements: event.target.value })}
            rows={3}
            maxLength={1000}
            placeholder="题量、题型、难度"
            className={`${workspaceFieldClass} resize-none border-slate-200 focus:border-slate-300 focus:ring-slate-100`}
          />
        </label>
      )}
    </div>
  );
}
