import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { CheckCircle2, Download, Eye, FileText, PlusCircle, Trash2, X } from 'lucide-react';

import {
  getReviewLessonTaskMessage,
  getReviewLessonTaskProgress,
  getReviewLessonTaskState,
  hasReviewLessonOutput,
  isReviewLessonPending,
  normalizeReviewLessonsResponse,
  type ReviewLessonRecord,
} from '../../reviewGenerationAsync';
import {
  apiFetch,
  buildAuthedPath,
  buildDiceBearAvatarUrl,
  cn,
  workspaceCardClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSectionTitleClass,
} from '../../workspaceShared';

type ReviewPlanCreateResult = {
  id: number;
  duplicate?: boolean;
};

type ReviewGenerationPageProps = {
  onSuccess: () => void;
  renderLessonInput: (onSuccess: (result: ReviewPlanCreateResult) => void) => ReactNode;
};

type ReviewDocumentHistoryProps = {
  refreshToken?: number;
  highlightedLessonId?: number | null;
};

const REVIEW_HISTORY_PAGE_SIZE = 12;
const reviewHistoryPanelClass = `${workspaceCardClass} overflow-hidden`;

function ReviewHistorySkeleton() {
  return (
    <div className="p-5">
      <div className="space-y-3">
        {[0, 1, 2].map((item) => (
          <div key={item} className="rounded-2xl border border-slate-200/70 bg-white/80 p-4 dark:border-white/10 dark:bg-white/5">
            <div className="h-4 w-40 rounded-full bg-slate-200/80 dark:bg-white/10" />
            <div className="mt-3 h-3 w-64 rounded-full bg-slate-100 dark:bg-white/5" />
            <div className="mt-4 grid gap-2 sm:grid-cols-3">
              <div className="h-3 rounded-full bg-slate-100 dark:bg-white/5" />
              <div className="h-3 rounded-full bg-slate-100 dark:bg-white/5" />
              <div className="h-3 rounded-full bg-slate-100 dark:bg-white/5" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function getLessonTitle(lesson: ReviewLessonRecord): string {
  return lesson.topic || `${lesson.subject} 课程`;
}

function getLessonCreator(lesson: ReviewLessonRecord): string {
  return lesson.creator_display_name || lesson.creator_username || '-';
}

function getLessonCreatorAvatarUrl(lesson: ReviewLessonRecord): string {
  return buildDiceBearAvatarUrl({
    id: lesson.created_by_user_id ?? lesson.id,
    username: lesson.creator_username,
    display_name: lesson.creator_display_name,
  });
}

function getLessonStatusMeta(lesson: ReviewLessonRecord): {
  label: string;
  dotClassName: string;
  message: string;
  progress: number;
  state: ReturnType<typeof getReviewLessonTaskState>;
} {
  const state = getReviewLessonTaskState(lesson);
  const message = getReviewLessonTaskMessage(lesson);
  const progress = getReviewLessonTaskProgress(lesson);

  if (lesson.record_status === 'transcribing') {
    return {
      label: '转写中',
      dotClassName: 'bg-amber-500',
      message,
      progress,
      state,
    };
  }

  if (state === 'pending') {
    return {
      label: '生成中',
      dotClassName: 'bg-amber-500',
      message,
      progress,
      state,
    };
  }

  if (state === 'failed') {
    return {
      label: '生成失败',
      dotClassName: 'bg-rose-500',
      message: message || '生成失败',
      progress,
      state,
    };
  }

  if (state === 'missing-output') {
    return {
      label: '待刷新',
      dotClassName: 'bg-slate-300 dark:bg-slate-600',
      message,
      progress,
      state,
    };
  }

  if (hasReviewLessonOutput(lesson)) {
    return {
      label: '已生成',
      dotClassName: 'bg-emerald-500',
      message: '',
      progress: 100,
      state,
    };
  }

  return {
    label: '无 PDF',
    dotClassName: 'bg-slate-300 dark:bg-slate-600',
    message: '',
    progress,
    state,
  };
}

function ReviewDocumentHistory({
  refreshToken = 0,
  highlightedLessonId = null,
}: ReviewDocumentHistoryProps) {
  const [lessons, setLessons] = useState<ReviewLessonRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [historyPage, setHistoryPage] = useState(1);

  const load = useCallback((quiet = false) => {
    if (!quiet) {
      setLoading(true);
    }

    return apiFetch<unknown>('/api/review-plans')
      .then((payload) => setLessons(normalizeReviewLessonsResponse(payload)))
      .catch(console.error)
      .finally(() => {
        if (!quiet) {
          setLoading(false);
        }
      });
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshToken]);

  const hasPendingLesson = lessons.some(isReviewLessonPending);

  useEffect(() => {
    if (!hasPendingLesson) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      void load(true);
    }, 3000);

    return () => window.clearInterval(timer);
  }, [hasPendingLesson, load]);

  const totalHistoryPages = Math.max(1, Math.ceil(lessons.length / REVIEW_HISTORY_PAGE_SIZE));
  const currentHistoryPage = Math.min(historyPage, totalHistoryPages);
  const paginatedLessons = lessons.slice((currentHistoryPage - 1) * REVIEW_HISTORY_PAGE_SIZE, currentHistoryPage * REVIEW_HISTORY_PAGE_SIZE);

  useEffect(() => {
    if (highlightedLessonId) {
      const highlightedIndex = lessons.findIndex((lesson) => lesson.id === highlightedLessonId);
      if (highlightedIndex >= 0) {
        setHistoryPage(Math.floor(highlightedIndex / REVIEW_HISTORY_PAGE_SIZE) + 1);
        return;
      }
    }

    setHistoryPage(1);
  }, [highlightedLessonId, lessons]);

  const handleDelete = async (id: number) => {
    if (!window.confirm('确定删除此课程？相关 PDF 也会被删除。')) {
      return;
    }

    await apiFetch(`/api/review-plans/${id}`, { method: 'DELETE' });
    void load();
  };

  return (
    <div className={reviewHistoryPanelClass}>
      <div className="flex items-center justify-between border-b border-slate-200/70 px-5 py-4 dark:border-white/10 sm:px-6">
        <h3 className={workspaceSectionTitleClass}>历史文档</h3>
        <span className="text-xs font-medium text-slate-500 dark:text-slate-400">共 {lessons.length} 份</span>
      </div>
      {loading ? (
        <ReviewHistorySkeleton />
      ) : lessons.length === 0 ? (
        <div className="px-5 py-12 text-center sm:px-6">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-200/80 text-slate-500 dark:border-white/10 dark:text-slate-300">
            <FileText size={20} />
          </div>
          <p className="mt-4 text-base font-medium text-slate-900 dark:text-white">还没有复习文档</p>
        </div>
      ) : (
        <div className="p-4 sm:p-5">
          <div className="hidden border-b border-slate-200/70 px-2 pb-3 text-xs font-semibold tracking-[0.12em] text-slate-400 lg:grid lg:grid-cols-[minmax(0,2fr)_128px_132px_180px_112px_132px] lg:gap-4 dark:border-white/10 dark:text-slate-500">
            <span>文档</span>
            <span>生成人</span>
            <span>日期</span>
            <span>生成时间</span>
            <span>状态</span>
            <span className="text-right">操作</span>
          </div>

          <ul className="divide-y divide-slate-200/70 dark:divide-white/10">
            {paginatedLessons.map((lesson) => {
              const status = getLessonStatusMeta(lesson);

              return (
                <li
                  key={lesson.id}
                  className={cn(
                    'rounded-2xl px-2 py-4 transition-colors hover:bg-slate-50/90 dark:hover:bg-white/5',
                    highlightedLessonId === lesson.id && 'bg-emerald-50/80 dark:bg-emerald-500/10',
                  )}
                >
                  <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_128px_132px_180px_112px_132px] lg:items-start lg:gap-4">
                    <div className="min-w-0">
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center text-slate-500 dark:text-slate-300">
                          <FileText size={16} />
                        </div>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">{getLessonTitle(lesson)}</p>
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            {lesson.subject && (
                              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold tracking-[0.12em] text-slate-600 dark:bg-white/10 dark:text-slate-300">
                                {lesson.subject}
                              </span>
                            )}
                            {lesson.grade && (
                              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold tracking-[0.12em] text-slate-500 dark:bg-white/5 dark:text-slate-400">
                                {lesson.grade}
                              </span>
                            )}
                            <span className="inline-flex items-center gap-2 rounded-full bg-white px-2.5 py-1 text-[10px] font-semibold tracking-[0.12em] text-slate-500 dark:bg-white/5 dark:text-slate-400 lg:hidden">
                              <span className={cn('h-2 w-2 rounded-full', status.dotClassName)} />
                              {status.label}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center justify-between gap-4 text-sm lg:block">
                      <span className="text-xs font-medium uppercase tracking-[0.12em] text-slate-400 lg:hidden dark:text-slate-500">生成人</span>
                      <span className="inline-flex items-center gap-2 text-slate-700 dark:text-slate-200">
                        <img
                          src={getLessonCreatorAvatarUrl(lesson)}
                          alt={`${getLessonCreator(lesson)} 头像`}
                          className="h-6 w-6 shrink-0 rounded-full bg-slate-100 object-cover dark:bg-white/10"
                        />
                        <span className="truncate">{getLessonCreator(lesson)}</span>
                      </span>
                    </div>

                    <div className="flex items-center justify-between gap-4 text-sm lg:block">
                      <span className="text-xs font-medium uppercase tracking-[0.12em] text-slate-400 lg:hidden dark:text-slate-500">日期</span>
                      <span className="font-mono text-slate-700 dark:text-slate-200">{lesson.date || '-'}</span>
                    </div>

                    <div className="flex items-center justify-between gap-4 text-sm lg:block">
                      <span className="text-xs font-medium uppercase tracking-[0.12em] text-slate-400 lg:hidden dark:text-slate-500">生成时间</span>
                      <span className="text-slate-700 dark:text-slate-200">{new Date(lesson.created_at).toLocaleString('zh-CN')}</span>
                    </div>

                    <div className="hidden lg:flex lg:items-center lg:gap-2 lg:text-sm lg:text-slate-600 dark:lg:text-slate-300">
                      <span className={cn('h-2 w-2 rounded-full', status.dotClassName)} />
                      <span>{status.label}</span>
                    </div>

                    <div className="flex items-center justify-end gap-1">
                      {hasReviewLessonOutput(lesson) && (
                        <>
                          <a
                            href={buildAuthedPath(`/api/pdf/${lesson.id}`)}
                            target="_blank"
                            rel="noreferrer"
                            className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200/80 bg-white text-slate-500 transition-colors hover:border-slate-300 hover:text-slate-900 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white"
                            title="查看"
                          >
                            <Eye size={16} />
                          </a>
                          <a
                            href={buildAuthedPath(`/api/pdf/download/${lesson.id}`)}
                            className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200/80 bg-white text-slate-500 transition-colors hover:border-slate-300 hover:text-slate-900 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white"
                            title="下载"
                          >
                            <Download size={16} />
                          </a>
                        </>
                      )}
                      <button
                        type="button"
                        onClick={() => void handleDelete(lesson.id)}
                        className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200/80 bg-white text-slate-500 transition-colors hover:border-rose-200 hover:text-rose-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-rose-500/10 dark:hover:text-rose-300"
                        title="删除"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>

                    {(status.state === 'pending' || status.state === 'failed' || status.state === 'missing-output') && (
                      <div className="lg:col-span-5">
                        <div
                          className={cn(
                            'rounded-2xl px-3 py-2 text-sm',
                            status.state === 'pending' && 'border border-amber-200 bg-amber-50/90 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200',
                            status.state === 'failed' && 'border border-rose-200 bg-rose-50/90 text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-200',
                            status.state === 'missing-output' && 'border border-amber-200 bg-amber-50/90 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200',
                          )}
                        >
                          <div>{status.message || '生成状态更新中'}</div>
                          {status.state === 'pending' && (
                            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-amber-100 dark:bg-white/10">
                              <div className="h-full rounded-full bg-amber-500 transition-all" style={{ width: `${status.progress}%` }} />
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>

          <div className="mt-4 flex items-center justify-between border-t border-slate-200/70 pt-4 text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
            <span>
              第 {currentHistoryPage} / {totalHistoryPages} 页
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setHistoryPage((current) => Math.max(1, current - 1))}
                disabled={currentHistoryPage <= 1}
                className={workspaceSecondaryButtonClass}
              >
                上一页
              </button>
              <button
                type="button"
                onClick={() => setHistoryPage((current) => Math.min(totalHistoryPages, current + 1))}
                disabled={currentHistoryPage >= totalHistoryPages}
                className={workspaceSecondaryButtonClass}
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function ReviewGenerationPage({ onSuccess, renderLessonInput }: ReviewGenerationPageProps) {
  const [composerOpen, setComposerOpen] = useState(false);
  const [historyRefreshToken, setHistoryRefreshToken] = useState(0);
  const [reviewNotice, setReviewNotice] = useState('');
  const [highlightedLessonId, setHighlightedLessonId] = useState<number | null>(null);

  useEffect(() => {
    if (!composerOpen) {
      return undefined;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setComposerOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [composerOpen]);

  const handleFormSuccess = (result: ReviewPlanCreateResult) => {
    setComposerOpen(false);
    setHighlightedLessonId(result.id);
    if (result.duplicate) {
      setReviewNotice(`这份录音已处理过，已复用已有复习文档 #${result.id}。`);
    } else {
      setReviewNotice('');
    }
    setHistoryRefreshToken((current) => current + 1);
    onSuccess();
  };

  const handleToggleComposer = () => {
    if (composerOpen) {
      setComposerOpen(false);
      return;
    }
    setComposerOpen(true);
  };

  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-3xl font-semibold tracking-tight text-slate-950 dark:text-white">复习生成</h2>
        <button type="button" onClick={handleToggleComposer} className={`${workspacePrimaryButtonClass} shadow-none`}>
          <PlusCircle size={20} />
          新建复习文档
        </button>
      </div>

      {reviewNotice && (
        <div className="flex items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-200">
          <CheckCircle2 size={18} />
          <span className="text-sm">{reviewNotice}</span>
        </div>
      )}

      <ReviewDocumentHistory refreshToken={historyRefreshToken} highlightedLessonId={highlightedLessonId} />

      {composerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm sm:p-6">
          <div className="flex max-h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-[1.75rem] border border-slate-200 bg-[#ffffff] shadow-none">
            <div className="flex items-center justify-between border-b border-slate-200/70 bg-[#ffffff] px-5 py-4 sm:px-6">
              <h3 className="text-xl font-semibold text-slate-900">生成复习文档</h3>
              <button
                type="button"
                onClick={() => setComposerOpen(false)}
                className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
                aria-label="关闭"
              >
                <X size={18} />
              </button>
            </div>
            <div className="overflow-y-auto bg-[#ffffff] px-5 py-5 sm:px-6 sm:py-6">
              {renderLessonInput(handleFormSuccess)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
