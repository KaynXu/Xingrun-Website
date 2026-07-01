import { RefreshCw, X } from 'lucide-react';

import { cn, workspacePrimaryButtonClass, workspaceSecondaryButtonClass } from '../../workspaceShared';
import { ReviewPlanGenerationOptionsFields } from './ReviewPlanGenerationOptionsFields';
import { getGenerationOptionsValidationError, type ReviewPlanGenerationOptionsFormValue } from './reviewPlanGenerationOptions';

type ReviewPlanRegenerateDialogProps = {
  title: string;
  value: ReviewPlanGenerationOptionsFormValue;
  onChange: (value: ReviewPlanGenerationOptionsFormValue) => void;
  onCancel: () => void;
  onSubmit: () => void;
  submitting: boolean;
};

export function ReviewPlanRegenerateDialog({
  title,
  value,
  onChange,
  onCancel,
  onSubmit,
  submitting,
}: ReviewPlanRegenerateDialogProps) {
  const validationError = getGenerationOptionsValidationError(value);

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/35 px-4 py-6 backdrop-blur-sm">
      <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-5 text-slate-900 dark:border-white/10 dark:bg-slate-950 dark:text-white">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200/70 pb-4 dark:border-white/10">
          <div>
            <h3 className="text-base font-semibold">重新生成设置</h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{title}</p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="flex h-9 w-9 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-white/10 dark:hover:text-slate-200"
            aria-label="关闭重新生成设置"
          >
            <X size={16} />
          </button>
        </div>
        <div className="py-4">
          <ReviewPlanGenerationOptionsFields value={value} onChange={onChange} />
          {validationError && (
            <p className="mt-3 text-sm font-medium text-rose-600 dark:text-rose-300">
              {validationError}
            </p>
          )}
        </div>
        <div className="flex flex-wrap justify-end gap-2 border-t border-slate-200/70 pt-4 dark:border-white/10">
          <button type="button" onClick={onCancel} className={workspaceSecondaryButtonClass}>
            取消
          </button>
          <button
            type="button"
            onClick={onSubmit}
            disabled={submitting || Boolean(validationError)}
            className={workspacePrimaryButtonClass}
          >
            <RefreshCw size={16} className={cn(submitting && 'animate-spin')} />
            开始重新生成
          </button>
        </div>
      </div>
    </div>
  );
}
