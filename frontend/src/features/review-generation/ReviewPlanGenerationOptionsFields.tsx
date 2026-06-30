import { CalendarDays, ListChecks, MessageSquareText } from 'lucide-react';

import { cn, workspaceFieldClass } from '../../workspaceShared';
import type { ReviewPlanGenerationOptionsFormValue, ReviewPlanScheduleMode } from './reviewPlanGenerationOptions';
import { getGenerationOptionsFormSummary } from './reviewPlanGenerationOptions';

const scheduleModes: Array<{ value: ReviewPlanScheduleMode; label: string }> = [
  { value: 'standard', label: '标准 5 次' },
  { value: 'compressed', label: '压缩 1 天' },
  { value: 'daily', label: '连续每日' },
  { value: 'custom', label: '自定义' },
];

export function ReviewPlanGenerationOptionsFields({
  value,
  onChange,
}: {
  value: ReviewPlanGenerationOptionsFormValue;
  onChange: (value: ReviewPlanGenerationOptionsFormValue) => void;
}) {
  const update = (patch: Partial<ReviewPlanGenerationOptionsFormValue>) => {
    onChange({ ...value, ...patch });
  };

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
            连续生成天数
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
            复习日期点
          </span>
          <input
            type="text"
            value={value.customDays}
            onChange={(event) => update({ customDays: event.target.value })}
            placeholder="例如：1,3,7"
            className={`${workspaceFieldClass} w-full border-slate-200 focus:border-slate-300 focus:ring-slate-100`}
          />
        </label>
      )}

      <label className="block">
        <span className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
          <MessageSquareText size={14} />
          老师本次要求
        </span>
        <textarea
          value={value.userRequirements}
          onChange={(event) => update({ userRequirements: event.target.value })}
          rows={3}
          maxLength={1000}
          placeholder="例如：明天考试前使用，题量少一点，多给选择题诊断。"
          className={`${workspaceFieldClass} resize-none border-slate-200 focus:border-slate-300 focus:ring-slate-100`}
        />
      </label>
    </div>
  );
}
