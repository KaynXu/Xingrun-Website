import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, Download, Eye, RefreshCw, RotateCcw } from 'lucide-react';

import { buildWrongQuestionLatexPreviewModel } from '../../wrongQuestionLatex.js';
import { apiFetch, cn, workspacePrimaryButtonClass, workspaceSecondaryButtonClass } from '../../workspaceShared';
import { ReviewPlanRegenerateDialog } from './ReviewPlanRegenerateDialog';
import {
  DEFAULT_REVIEW_PLAN_GENERATION_OPTIONS,
  formValueFromGenerationOptions,
  type ReviewPlanGenerationOptionsFormValue,
} from './reviewPlanGenerationOptions';
import {
  authedReviewPlanUrl,
  canMakeReviewPlanVersionCurrent,
  getReviewPlanVersionLabel,
  normalizeReviewPlanDetail,
  type ReviewPlanDetailRecord,
  type ReviewPlanPreviewMathBlock,
  type ReviewPlanVersionRecord,
} from './reviewPlanVersions';

type ReviewPlanDetailViewProps = {
  lessonId: number;
  onBack: () => void;
  onChanged: () => void;
  onRegenerate: (options: ReviewPlanGenerationOptionsFormValue) => Promise<void>;
};

function getDetailTitle(detail: ReviewPlanDetailRecord): string {
  return detail.topic || `${detail.subject || '复习'} 课程`;
}

function formatVersionTime(value: string): string {
  if (!value.trim()) {
    return '-';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function getVersionDotClass(version: ReviewPlanVersionRecord): string {
  if (version.status === 'ready') {
    return 'bg-sky-500';
  }
  if (version.status === 'failed') {
    return 'bg-rose-500';
  }
  return 'bg-amber-500';
}

function getActiveVersionLabel(detail: ReviewPlanDetailRecord): string {
  return detail.active_version_status === 'transcribing' ? '正在转写新版' : '正在生成新版';
}

function resolveReviewPlanMathText(text: string, mathBlocks: ReviewPlanPreviewMathBlock[]): string {
  if (!text.trim() || mathBlocks.length === 0) {
    return text;
  }
  const blockById = new Map(mathBlocks.map((block) => [block.id, block]));
  return text.replace(/\{\{math:([^}]+)\}\}/g, (raw, id: string) => {
    const block = blockById.get(id.trim());
    if (!block?.latex.trim()) {
      return raw;
    }
    return block.display ? `$$${block.latex}$$` : `$${block.latex}$`;
  });
}

function ReviewPlanLatexText({
  text,
  mathBlocks,
  empty = '-',
  className,
}: {
  text: string;
  mathBlocks: ReviewPlanPreviewMathBlock[];
  empty?: string;
  className?: string;
}) {
  const resolvedText = resolveReviewPlanMathText(text, mathBlocks);
  const preview = buildWrongQuestionLatexPreviewModel(resolvedText);

  return (
    <span
      className={cn('xr-latex-preview', className)}
      dangerouslySetInnerHTML={{ __html: preview.html || `<span class="xr-latex-empty">${empty}</span>` }}
    />
  );
}

export function ReviewPlanDetailView({
  lessonId,
  onBack,
  onChanged,
  onRegenerate,
}: ReviewPlanDetailViewProps) {
  const [detail, setDetail] = useState<ReviewPlanDetailRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [makingCurrentVersionId, setMakingCurrentVersionId] = useState<number | null>(null);
  const [rerenderingVersionId, setRerenderingVersionId] = useState<number | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [regenerateDialogOpen, setRegenerateDialogOpen] = useState(false);
  const [regenerateOptions, setRegenerateOptions] = useState<ReviewPlanGenerationOptionsFormValue>({
    ...DEFAULT_REVIEW_PLAN_GENERATION_OPTIONS,
  });

  const loadDetail = useCallback((quiet = false) => {
    if (!quiet) {
      setLoading(true);
    }
    setError('');

    return apiFetch<unknown>(`/api/review-plans/${lessonId}`)
      .then((payload) => {
        setDetail(normalizeReviewPlanDetail(payload));
      })
      .catch((caught) => {
        setError(caught instanceof Error ? caught.message : '详情加载失败');
      })
      .finally(() => {
        if (!quiet) {
          setLoading(false);
        }
      });
  }, [lessonId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    if (!detail?.has_version_generating) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      void loadDetail(true);
    }, 3000);

    return () => window.clearInterval(timer);
  }, [detail?.has_version_generating, loadDetail]);

  const handleMakeCurrent = async (version: ReviewPlanVersionRecord) => {
    if (!detail || !canMakeReviewPlanVersionCurrent(detail, version) || makingCurrentVersionId !== null) {
      return;
    }

    setMakingCurrentVersionId(version.id);
    setError('');
    try {
      await apiFetch<unknown>(`/api/review-plans/${lessonId}/versions/${version.id}/make-current`, {
        method: 'POST',
      });
      await loadDetail(true);
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '设为当前失败');
    } finally {
      setMakingCurrentVersionId(null);
    }
  };

  const handleRerenderPdf = async (version: ReviewPlanVersionRecord) => {
    if (!detail || version.status !== 'ready' || rerenderingVersionId !== null) {
      return;
    }

    setRerenderingVersionId(version.id);
    setError('');
    try {
      await apiFetch<unknown>(`/api/review-plans/${lessonId}/versions/${version.id}/rerender-pdf`, {
        method: 'POST',
      });
      await loadDetail(true);
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '重新渲染 PDF 失败');
    } finally {
      setRerenderingVersionId(null);
    }
  };

  const openRegenerateDialog = () => {
    if (!detail || regenerating) {
      return;
    }
    setRegenerateOptions(formValueFromGenerationOptions(detail.review_generation_options));
    setRegenerateDialogOpen(true);
  };

  const handleRegenerate = async () => {
    if (regenerating) {
      return;
    }

    setRegenerating(true);
    setError('');
    try {
      await onRegenerate(regenerateOptions);
      setRegenerateDialogOpen(false);
      await loadDetail(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '重新生成失败，请稍后重试');
    } finally {
      setRegenerating(false);
    }
  };

  const currentPdfUrl = detail?.current_pdf_url.trim() ? authedReviewPlanUrl(detail.current_pdf_url) : '';
  const currentDownloadUrl = detail?.current_download_url.trim() ? authedReviewPlanUrl(detail.current_download_url) : '';
  const currentPreview = detail?.current_plan_preview;
  const hasCurrentPreview = Boolean(
    currentPreview
    && (
      currentPreview.summary.trim()
      || currentPreview.math_blocks.length > 0
      || currentPreview.days.some((day) => day.questions.length > 0)
    ),
  );

  return (
    <div className="overflow-hidden rounded-[1.75rem] border border-sky-100/90 bg-white/88 dark:border-white/10 dark:bg-slate-950/78">
      <div className="flex flex-col gap-3 border-b border-slate-200/70 px-5 py-4 dark:border-white/10 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="min-w-0">
          <button
            type="button"
            onClick={onBack}
            className="inline-flex items-center gap-2 text-sm font-semibold text-slate-500 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
          >
            <ArrowLeft size={16} />
            返回历史
          </button>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <h3 className="truncate text-xl font-semibold text-slate-950 dark:text-white">
              {detail ? getDetailTitle(detail) : '复习计划详情'}
            </h3>
            {detail?.has_version_generating && (
              <span className="inline-flex items-center gap-2 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-500/10 dark:text-amber-200">
                <span className="h-2 w-2 rounded-full bg-amber-500" />
                {getActiveVersionLabel(detail)}
              </span>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={openRegenerateDialog}
          disabled={loading || regenerating}
          className={cn(workspacePrimaryButtonClass, 'h-10 px-4 py-2 text-sm')}
        >
          <RefreshCw size={16} className={cn(regenerating && 'animate-spin')} />
          重新生成
        </button>
      </div>

      {loading ? (
        <div className="space-y-4 p-5 sm:p-6">
          <div className="h-5 w-40 rounded-full bg-slate-100 dark:bg-white/10" />
          <div className="h-[70vh] min-h-[520px] rounded-2xl bg-slate-50 dark:bg-white/5 sm:h-[76vh] sm:min-h-[640px]" />
        </div>
      ) : !detail ? (
        <div className="px-5 py-12 text-center text-sm text-slate-500 dark:text-slate-400 sm:px-6">
          {error || '未找到复习计划'}
        </div>
      ) : (
        <div className="space-y-6 p-5 sm:p-6">
          {error && (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/25 dark:bg-rose-500/10 dark:text-rose-200">
              {error}
            </div>
          )}

          <section>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h4 className="text-sm font-semibold text-slate-900 dark:text-white">当前版本</h4>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  {detail.current_version_no ? `V${detail.current_version_no}` : '暂无版本'} · {formatVersionTime(detail.current_generated_at || detail.created_at)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {currentPdfUrl && (
                  <a
                    href={currentPdfUrl}
                    target="_blank"
                    rel="noreferrer"
                    className={cn(workspaceSecondaryButtonClass, 'h-10 px-4 py-2 text-sm')}
                  >
                    <Eye size={16} />
                    预览
                  </a>
                )}
                {currentDownloadUrl && (
                  <a
                    href={currentDownloadUrl}
                    className={cn(workspaceSecondaryButtonClass, 'h-10 px-4 py-2 text-sm')}
                  >
                    <Download size={16} />
                    下载
                  </a>
                )}
              </div>
            </div>

            {currentPdfUrl ? (
              <iframe
                src={currentPdfUrl}
                title="当前复习计划 PDF"
                className="mt-4 h-[82vh] min-h-[680px] w-full rounded-2xl border border-slate-200 bg-slate-50 dark:border-white/10 dark:bg-white/5"
              />
            ) : (
              <div className="mt-4 rounded-2xl border border-dashed border-slate-200 px-5 py-12 text-center text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
                当前版本暂无可预览 PDF。
              </div>
            )}
          </section>

          {hasCurrentPreview && currentPreview && (
            <section>
              <div className="flex items-center justify-between border-b border-slate-200/70 pb-3 dark:border-white/10">
                <h4 className="text-sm font-semibold text-slate-900 dark:text-white">结构预览</h4>
              </div>
              <div className="mt-4 space-y-4">
                {currentPreview.summary.trim() && (
                  <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-700 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-200">
                    <ReviewPlanLatexText text={currentPreview.summary} mathBlocks={currentPreview.math_blocks} />
                  </div>
                )}
                {currentPreview.math_blocks.length > 0 && (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {currentPreview.math_blocks.slice(0, 6).map((block) => (
                      <div key={block.id || block.latex} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-200">
                        <ReviewPlanLatexText text={block.display ? `$$${block.latex}$$` : `$${block.latex}$`} mathBlocks={[]} />
                      </div>
                    ))}
                  </div>
                )}
                {currentPreview.days.map((day, dayIndex) => (
                  <div key={`${day.day}-${day.label}-${dayIndex}`} className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-slate-950/60">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-slate-900 dark:text-white">{day.label || day.day || `第 ${dayIndex + 1} 天`}</span>
                      {day.focus && <span className="text-xs text-slate-500 dark:text-slate-400">{day.focus}</span>}
                    </div>
                    {day.goal && (
                      <div className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">
                        <ReviewPlanLatexText text={day.goal} mathBlocks={currentPreview.math_blocks} />
                      </div>
                    )}
                    {day.questions.length > 0 && (
                      <ol className="mt-3 space-y-3 text-sm text-slate-700 dark:text-slate-200">
                        {day.questions.map((question, questionIndex) => (
                          <li key={`${question.type}-${questionIndex}`} className="rounded-xl bg-slate-50 px-3 py-2 dark:bg-white/5">
                            <div className="flex gap-2">
                              <span className="shrink-0 font-semibold text-slate-400">{questionIndex + 1}.</span>
                              <div className="min-w-0 flex-1 space-y-1">
                                <ReviewPlanLatexText text={question.question} mathBlocks={currentPreview.math_blocks} />
                                {question.options.length > 0 && (
                                  <div className="grid gap-1 text-xs text-slate-500 dark:text-slate-400 sm:grid-cols-2">
                                    {question.options.map((option) => (
                                      <ReviewPlanLatexText key={option} text={option} mathBlocks={currentPreview.math_blocks} />
                                    ))}
                                  </div>
                                )}
                                {question.answer && (
                                  <div className="text-xs font-semibold text-sky-700 dark:text-sky-200">
                                    <ReviewPlanLatexText text={`答案：${question.answer}`} mathBlocks={currentPreview.math_blocks} />
                                  </div>
                                )}
                              </div>
                            </div>
                          </li>
                        ))}
                      </ol>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          <section>
            <div className="flex items-center justify-between border-b border-slate-200/70 pb-3 dark:border-white/10">
              <h4 className="text-sm font-semibold text-slate-900 dark:text-white">版本历史</h4>
              <span className="text-xs text-slate-500 dark:text-slate-400">共 {detail.versions.length} 个版本</span>
            </div>

            {detail.versions.length === 0 ? (
              <div className="py-8 text-sm text-slate-500 dark:text-slate-400">暂无版本记录。</div>
            ) : (
              <ul className="divide-y divide-slate-200/70 dark:divide-white/10">
                {detail.versions.map((version) => {
                  const isCurrent = version.id === detail.current_version_id;
                  const versionPdfUrl = version.pdf_available && version.pdf_url.trim() ? authedReviewPlanUrl(version.pdf_url) : '';
                  const versionDownloadUrl = version.pdf_available && version.download_url.trim() ? authedReviewPlanUrl(version.download_url) : '';
                  const canMakeCurrent = canMakeReviewPlanVersionCurrent(detail, version);

                  return (
                    <li key={version.id} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-semibold text-slate-900 dark:text-white">
                            V{version.version_no ?? version.id}
                          </span>
                          {isCurrent && (
                            <span className="rounded-full bg-sky-50 px-2 py-0.5 text-xs font-semibold text-sky-700 dark:bg-sky-500/10 dark:text-sky-200">
                              当前
                            </span>
                          )}
                          <span className="inline-flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                            <span className={cn('h-2 w-2 rounded-full', getVersionDotClass(version))} />
                            {getReviewPlanVersionLabel(version.status)}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                          {formatVersionTime(version.completed_at || version.created_at)}
                        </p>
                        {version.status === 'failed' && version.generation_error && (
                          <p className="mt-2 text-sm text-rose-600 dark:text-rose-300">{version.generation_error}</p>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                        {versionPdfUrl && (
                          <a
                            href={versionPdfUrl}
                            target="_blank"
                            rel="noreferrer"
                            className={cn(workspaceSecondaryButtonClass, 'h-9 px-3 py-2 text-xs')}
                          >
                            <Eye size={14} />
                            预览
                          </a>
                        )}
                        {versionDownloadUrl && (
                          <a
                            href={versionDownloadUrl}
                            className={cn(workspaceSecondaryButtonClass, 'h-9 px-3 py-2 text-xs')}
                          >
                            <Download size={14} />
                            下载
                          </a>
                        )}
                        {version.status === 'ready' && (
                          <button
                            type="button"
                            onClick={() => void handleRerenderPdf(version)}
                            disabled={rerenderingVersionId !== null}
                            className={cn(workspaceSecondaryButtonClass, 'h-9 px-3 py-2 text-xs')}
                          >
                            <RefreshCw size={14} className={cn(rerenderingVersionId === version.id && 'animate-spin')} />
                            重渲染PDF
                          </button>
                        )}
                        {canMakeCurrent && (
                          <button
                            type="button"
                            onClick={() => void handleMakeCurrent(version)}
                            disabled={makingCurrentVersionId !== null}
                            className={cn(workspaceSecondaryButtonClass, 'h-9 px-3 py-2 text-xs')}
                          >
                            <RotateCcw size={14} className={cn(makingCurrentVersionId === version.id && 'animate-spin')} />
                            设为当前
                          </button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>
      )}
      {regenerateDialogOpen && detail && (
        <ReviewPlanRegenerateDialog
          title={getDetailTitle(detail)}
          value={regenerateOptions}
          onChange={setRegenerateOptions}
          onCancel={() => setRegenerateDialogOpen(false)}
          onSubmit={() => void handleRegenerate()}
          submitting={regenerating}
        />
      )}
    </div>
  );
}
