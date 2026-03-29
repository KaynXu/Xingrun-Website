import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, RefreshCw, Search } from 'lucide-react';

import {
  apiFetch,
  workspaceCardClass,
  workspaceFieldClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSoftCardClass,
} from './App';
import {
  buildWrongQuestionQuery,
  normalizeWrongQuestionListResponse,
  summarizeWrongQuestionRecords,
  type WrongQuestionFilters,
  type WrongQuestionListApiResponse,
  type WrongQuestionRecord,
  type WrongQuestionSummary,
} from './smartWrongQuestions';

type SmartWrongQuestionsPageProps = {
  currentUser: {
    display_name: string;
    organization_name: string;
  };
};

const initialFilters: WrongQuestionFilters = {
  studentName: '',
  className: '',
  subject: '',
  teacherName: '',
  errorType: '',
  onlyPendingReview: false,
};

export function SmartWrongQuestionsPage({ currentUser }: SmartWrongQuestionsPageProps) {
  const [filters, setFilters] = useState<WrongQuestionFilters>(initialFilters);
  const [records, setRecords] = useState<WrongQuestionRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [serverSummary, setServerSummary] = useState<WrongQuestionSummary | null>(null);
  const requestVersionRef = useRef(0);

  const summary = useMemo(() => serverSummary ?? summarizeWrongQuestionRecords(records), [records, serverSummary]);
  const selectedRecord = records.find((item) => item.id === selectedId) ?? records[0] ?? null;

  const loadList = useCallback(async (nextFilters: WrongQuestionFilters) => {
    const requestVersion = requestVersionRef.current + 1;
    requestVersionRef.current = requestVersion;
    setLoading(true);
    setError('');
    try {
      const response = await apiFetch<WrongQuestionListApiResponse>(`/api/wrong-questions${buildWrongQuestionQuery(nextFilters)}`);
      if (requestVersion !== requestVersionRef.current) {
        return;
      }

      const normalized = normalizeWrongQuestionListResponse(response);
      const nextRecords = normalized.items;
      setRecords(nextRecords);
      setServerSummary(normalized.summary);
      setSelectedId((current) => {
        if (current && nextRecords.some((item) => item.id === current)) {
          return current;
        }
        return nextRecords[0]?.id ?? null;
      });
    } catch (loadError) {
      if (requestVersion !== requestVersionRef.current) {
        return;
      }

      setError(loadError instanceof Error ? loadError.message : '智能错题列表加载失败');
      setRecords([]);
      setServerSummary(null);
      setSelectedId(null);
    } finally {
      if (requestVersion === requestVersionRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadList(initialFilters);
  }, [loadList]);

  const handleFilterChange = <K extends keyof WrongQuestionFilters>(key: K, value: WrongQuestionFilters[K]) => {
    setFilters((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void loadList(filters);
  };

  return (
    <div className={`${workspacePageClass} space-y-8`}>
      <section className={`${workspaceCardClass} space-y-4 p-6`}>
        <p className="text-sm uppercase tracking-[0.25em] text-sky-600">Wrong Question Workspace</p>
        <div>
          <h3 className="text-2xl font-bold text-slate-900 dark:text-white">智能错题</h3>
          <p className="mt-2 max-w-3xl text-sm text-slate-500 dark:text-slate-400">
            在 {currentUser.organization_name} 内部查看错题记录，筛选待跟进条目，并为后续教师复盘预留统一工作区。
          </p>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">当前操作人：{currentUser.display_name}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">记录总数</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{summary.totalCount}</p>
          </div>
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">重复错题</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{summary.repeatedMistakeCount}</p>
          </div>
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">高优先级</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{summary.highPriorityCount}</p>
          </div>
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">待教师跟进</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{summary.pendingReviewCount}</p>
          </div>
        </div>
      </section>

      {error && (
        <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <section className={`${workspaceCardClass} space-y-5 p-6`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h4 className="text-xl font-semibold text-slate-900 dark:text-white">筛选与列表</h4>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">本阶段只实现列表浏览和页面骨架，不包含保存跟进与导出。</p>
          </div>
          <button
            type="button"
            onClick={() => void loadList(filters)}
            disabled={loading}
            className={workspaceSecondaryButtonClass}
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            刷新列表
          </button>
        </div>

        <form className="grid gap-4 lg:grid-cols-3" onSubmit={handleSubmit}>
          <label className="space-y-2 text-sm">
            <span className="text-slate-500 dark:text-slate-400">学生姓名</span>
            <input
              type="text"
              value={filters.studentName ?? ''}
              onChange={(event) => handleFilterChange('studentName', event.target.value)}
              className={workspaceFieldClass}
              placeholder="如：Alice"
            />
          </label>
          <label className="space-y-2 text-sm">
            <span className="text-slate-500 dark:text-slate-400">班级</span>
            <input
              type="text"
              value={filters.className ?? ''}
              onChange={(event) => handleFilterChange('className', event.target.value)}
              className={workspaceFieldClass}
              placeholder="如：六年级 1 班"
            />
          </label>
          <label className="space-y-2 text-sm">
            <span className="text-slate-500 dark:text-slate-400">科目</span>
            <input
              type="text"
              value={filters.subject ?? ''}
              onChange={(event) => handleFilterChange('subject', event.target.value)}
              className={workspaceFieldClass}
              placeholder="如：数学"
            />
          </label>
          <label className="space-y-2 text-sm">
            <span className="text-slate-500 dark:text-slate-400">老师</span>
            <input
              type="text"
              value={filters.teacherName ?? ''}
              onChange={(event) => handleFilterChange('teacherName', event.target.value)}
              className={workspaceFieldClass}
              placeholder="如：雷文浩"
            />
          </label>
          <label className="space-y-2 text-sm">
            <span className="text-slate-500 dark:text-slate-400">错误类型</span>
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-400" size={18} />
              <input
                type="text"
                value={filters.errorType ?? ''}
                onChange={(event) => handleFilterChange('errorType', event.target.value)}
                className={`${workspaceFieldClass} pl-11`}
                placeholder="如：计算错误"
              />
            </div>
          </label>
          <label className="flex items-center gap-3 self-end rounded-2xl border border-sky-100 bg-sky-50/80 px-4 py-3 text-sm text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
            <input
              type="checkbox"
              checked={Boolean(filters.onlyPendingReview)}
              onChange={(event) => handleFilterChange('onlyPendingReview', event.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            只看待教师跟进
          </label>
          <div className="flex flex-wrap gap-3 lg:col-span-3 lg:justify-end">
            <button
              type="button"
              onClick={() => {
                setFilters(initialFilters);
                void loadList(initialFilters);
              }}
              disabled={loading}
              className={workspaceSecondaryButtonClass}
            >
              重置筛选
            </button>
            <button type="submit" disabled={loading} className={workspacePrimaryButtonClass}>
              应用筛选
            </button>
          </div>
        </form>

        {loading ? (
          <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
            正在加载智能错题列表...
          </div>
        ) : records.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
            当前筛选下暂无错题记录。
          </div>
        ) : (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(20rem,0.9fr)]">
            <div className="space-y-3">
              {records.map((item) => {
                const active = item.id === selectedRecord?.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setSelectedId(item.id)}
                    className={`${workspaceSoftCardClass} w-full p-4 text-left transition ${active ? 'border-sky-400 shadow-[0_18px_48px_rgba(47,128,237,0.12)]' : ''}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-base font-semibold text-slate-900 dark:text-white">{item.studentName}</p>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{item.className || '未标注班级'} · {item.subject || '未标注科目'}</p>
                      </div>
                      <span className="rounded-full border border-sky-200 bg-white/80 px-3 py-1 text-xs font-semibold text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                        {item.analysis.errorType || '待分析'}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                      <span>老师：{item.teacherName || '未标注'}</span>
                      <span>优先级：{item.analysis.teacherPriority || '待确认'}</span>
                      <span>{item.analysis.selectedErrorType ? '已跟进' : '待跟进'}</span>
                    </div>
                  </button>
                );
              })}
            </div>

            <div className={`${workspaceCardClass} space-y-5 p-5`}>
              <div>
                <h4 className="text-xl font-semibold text-slate-900 dark:text-white">记录详情</h4>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">后续教师勾选保存与导出将在后续任务补齐。</p>
              </div>

              {selectedRecord ? (
                <>
                  <div className={`${workspaceSoftCardClass} space-y-3 p-4`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-lg font-semibold text-slate-900 dark:text-white">{selectedRecord.studentName}</span>
                      <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                        {selectedRecord.subject || '未标注科目'}
                      </span>
                    </div>
                    <p className="text-sm text-slate-500 dark:text-slate-400">{selectedRecord.className || '未标注班级'} · {selectedRecord.teacherName || '未标注老师'}</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">记录时间：{selectedRecord.createdAt}</p>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className={`${workspaceSoftCardClass} p-4`}>
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">题型分类</p>
                      <p className="mt-2 text-base font-semibold text-slate-900 dark:text-white">{selectedRecord.analysis.questionCategory || '待识别'}</p>
                    </div>
                    <div className={`${workspaceSoftCardClass} p-4`}>
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">重复错题</p>
                      <p className="mt-2 text-base font-semibold text-slate-900 dark:text-white">{selectedRecord.analysis.isRepeatedMistake || '待确认'}</p>
                    </div>
                  </div>

                  <div className={`${workspaceSoftCardClass} space-y-3 p-4`}>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">知识点</p>
                    <div className="flex flex-wrap gap-2">
                      {selectedRecord.analysis.knowledgePoints.length > 0 ? selectedRecord.analysis.knowledgePoints.map((point) => (
                        <span
                          key={point}
                          className="rounded-full border border-sky-200 bg-white/80 px-3 py-1 text-xs font-semibold text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300"
                        >
                          {point}
                        </span>
                      )) : (
                        <span className="text-sm text-slate-500 dark:text-slate-400">暂无知识点标签</span>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                  请选择一条错题记录查看详情。
                </div>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}