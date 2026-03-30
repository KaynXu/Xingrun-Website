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
  buildWrongQuestionDetailPath,
  buildWrongQuestionReviewDraft,
  buildWrongQuestionQuery,
  buildWrongQuestionReviewPayload,
  buildWrongQuestionReviewPath,
  downloadWrongQuestionSummary,
  hydrateWrongQuestionReviewDraftFromDetail,
  normalizeWrongQuestionRecord,
  normalizeWrongQuestionListResponse,
  resolveSavedWrongQuestionRecord,
  summarizeWrongQuestionRecords,
  type WrongQuestionFilters,
  type WrongQuestionMappingStatus,
  type WrongQuestionListApiResponse,
  type WrongQuestionRecord,
  type WrongQuestionReviewDraft,
  type WrongQuestionSummary,
} from './smartWrongQuestions';

type SmartWrongQuestionsPageProps = {
  currentUser: {
    display_name: string;
    organization_name: string;
  };
};

type WrongQuestionClassFilterOption = {
  id: number;
  name: string;
  subject: string;
};

type WrongQuestionTeacherFilterOption = {
  id: number;
  name: string;
};

const initialFilters: WrongQuestionFilters = {
  studentName: '',
  className: '',
  subject: '',
  teacherName: '',
  errorType: '',
  onlyPendingReview: false,
};

function formatWrongQuestionMappingStatus(status: WrongQuestionMappingStatus): string {
  switch (status) {
    case 'mapped':
      return '已映射';
    case 'ambiguous':
      return '映射有歧义';
    case 'needs_review':
      return '待确认映射';
    case 'unmapped':
    default:
      return '未映射';
  }
}

function hasSnapshotDifference(canonicalValue: string, snapshotValue: string): boolean {
  const canonical = canonicalValue.trim();
  const snapshot = snapshotValue.trim();
  return Boolean(snapshot) && snapshot !== canonical;
}

function isMappedWrongQuestionRecord(status: WrongQuestionMappingStatus): boolean {
  return status === 'mapped';
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function extractSavedWrongQuestionResponseRecord(response: unknown): unknown {
  if (!isObjectRecord(response)) {
    return undefined;
  }

  if (Object.prototype.hasOwnProperty.call(response, 'record')) {
    return response.record;
  }

  if (
    Object.prototype.hasOwnProperty.call(response, 'id')
    || Object.prototype.hasOwnProperty.call(response, 'analysis')
    || Object.prototype.hasOwnProperty.call(response, 'student_name')
    || Object.prototype.hasOwnProperty.call(response, 'studentName')
  ) {
    return response;
  }

  return undefined;
}

export function SmartWrongQuestionsPage({ currentUser }: SmartWrongQuestionsPageProps) {
  const [filters, setFilters] = useState<WrongQuestionFilters>(initialFilters);
  const [records, setRecords] = useState<WrongQuestionRecord[]>([]);
  const [classOptions, setClassOptions] = useState<WrongQuestionClassFilterOption[]>([]);
  const [teacherOptions, setTeacherOptions] = useState<WrongQuestionTeacherFilterOption[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [savingReview, setSavingReview] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [reviewDraftByRecordId, setReviewDraftByRecordId] = useState<Record<string, WrongQuestionReviewDraft>>({});
  const [reviewDraftDirtyByRecordId, setReviewDraftDirtyByRecordId] = useState<Record<string, boolean>>({});
  const [serverSummary, setServerSummary] = useState<WrongQuestionSummary | null>(null);
  const requestVersionRef = useRef(0);
  const detailRequestVersionRef = useRef(0);
  const reviewDraftDirtyByRecordIdRef = useRef<Record<string, boolean>>({});

  const summary = useMemo(() => serverSummary ?? summarizeWrongQuestionRecords(records), [records, serverSummary]);
  const selectedRecord = records.find((item) => item.id === selectedId) ?? records[0] ?? null;
  const selectedDraft = selectedRecord ? reviewDraftByRecordId[selectedRecord.id] ?? buildWrongQuestionReviewDraft(selectedRecord) : null;

  const updateDraftDirtyState = useCallback((recordId: string, isDirty: boolean) => {
    reviewDraftDirtyByRecordIdRef.current = {
      ...reviewDraftDirtyByRecordIdRef.current,
      [recordId]: isDirty,
    };

    setReviewDraftDirtyByRecordId((current) => {
      if (current[recordId] === isDirty) {
        return current;
      }

      return {
        ...current,
        [recordId]: isDirty,
      };
    });
  }, []);

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
    let active = true;

    void (async () => {
      try {
        const [classItems, userItems] = await Promise.all([
          apiFetch<Array<{ id: number; name: string; subject?: string }>>('/api/classes'),
          apiFetch<Array<{ id: number; name: string }>>('/api/admin/users'),
        ]);

        if (!active) {
          return;
        }

        setClassOptions(classItems.map((item) => ({
          id: item.id,
          name: item.name,
          subject: item.subject?.trim() ?? '',
        })));
        setTeacherOptions(userItems.map((item) => ({
          id: item.id,
          name: item.name,
        })));
      } catch (loadOptionsError) {
        console.error(loadOptionsError);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    void loadList(initialFilters);
  }, [loadList]);

  useEffect(() => {
    if (!selectedRecord) {
      setDetailError('');
      setSaveError('');
      return;
    }

    if (reviewDraftDirtyByRecordId[selectedRecord.id] === undefined) {
      updateDraftDirtyState(selectedRecord.id, false);
    }

    setReviewDraftByRecordId((current) => {
      if (current[selectedRecord.id]) {
        return current;
      }

      return {
        ...current,
        [selectedRecord.id]: buildWrongQuestionReviewDraft(selectedRecord),
      };
    });
  }, [reviewDraftDirtyByRecordId, selectedRecord, updateDraftDirtyState]);

  useEffect(() => {
    if (!selectedId) {
      return;
    }

    const requestVersion = detailRequestVersionRef.current + 1;
    detailRequestVersionRef.current = requestVersion;
    setDetailLoading(true);
    setDetailError('');

    void (async () => {
      try {
        const response = await apiFetch<WrongQuestionRecord>(buildWrongQuestionDetailPath(selectedId));
        if (requestVersion !== detailRequestVersionRef.current) {
          return;
        }

        const detailRecord = normalizeWrongQuestionRecord(response);
        const hasLocalEdits = Boolean(reviewDraftDirtyByRecordIdRef.current[detailRecord.id]);
        setRecords((current) => current.map((item) => item.id === detailRecord.id ? detailRecord : item));
        setServerSummary(null);
        setReviewDraftByRecordId((current) => {
          return {
            ...current,
            [detailRecord.id]: hydrateWrongQuestionReviewDraftFromDetail(detailRecord, current[detailRecord.id], hasLocalEdits),
          };
        });
        if (!hasLocalEdits) {
          updateDraftDirtyState(detailRecord.id, false);
        }
      } catch (loadDetailError) {
        if (requestVersion !== detailRequestVersionRef.current) {
          return;
        }

        setDetailError(loadDetailError instanceof Error ? loadDetailError.message : '智能错题详情加载失败');
      } finally {
        if (requestVersion === detailRequestVersionRef.current) {
          setDetailLoading(false);
        }
      }
    })();
  }, [selectedId]);

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

  const handleDraftChange = <K extends keyof WrongQuestionReviewDraft>(key: K, value: WrongQuestionReviewDraft[K]) => {
    if (!selectedRecord) {
      return;
    }

    setReviewDraftByRecordId((current) => ({
      ...current,
      [selectedRecord.id]: {
        ...(current[selectedRecord.id] ?? buildWrongQuestionReviewDraft(selectedRecord)),
        [key]: value,
      },
    }));
    updateDraftDirtyState(selectedRecord.id, true);
  };

  const handleSaveReview = async () => {
    if (!selectedRecord || !selectedDraft) {
      return;
    }

    setSavingReview(true);
    setSaveError('');

    try {
      const payload = buildWrongQuestionReviewPayload(selectedDraft);
      const response = await apiFetch<unknown>(buildWrongQuestionReviewPath(selectedRecord.id), {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      const nextRecord = resolveSavedWrongQuestionRecord(
        selectedRecord,
        payload,
        extractSavedWrongQuestionResponseRecord(response),
      );

      setRecords((current) => current.map((item) => item.id === selectedRecord.id ? nextRecord : item));
      setServerSummary(null);
      setReviewDraftByRecordId((current) => ({
        ...current,
        [selectedRecord.id]: buildWrongQuestionReviewDraft(nextRecord),
      }));
      updateDraftDirtyState(selectedRecord.id, false);
    } catch (saveReviewError) {
      setSaveError(saveReviewError instanceof Error ? saveReviewError.message : '智能错题保存失败');
    } finally {
      setSavingReview(false);
    }
  };

  const handleExportSummary = () => {
    setError('');
    void downloadWrongQuestionSummary(filters).catch((downloadError) => {
      setError(downloadError instanceof Error ? downloadError.message : '智能错题导出失败');
    });
  };

  const selectedKnowledgePointText = selectedDraft?.selectedKnowledgePoints.join('\n') ?? '';
  const selectedActionsText = selectedDraft?.selectedActions.join('\n') ?? '';
  const selectedReasonsText = selectedDraft?.selectedReasons.join('\n') ?? '';

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
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">筛选错题、查看详情、保存教师复盘，并按当前筛选条件导出 PDF 汇总。</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={handleExportSummary} className={workspaceSecondaryButtonClass}>
              导出 PDF 汇总
            </button>
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
            <select
              aria-label="班级"
              value={filters.className ?? ''}
              onChange={(event) => handleFilterChange('className', event.target.value)}
              className={workspaceFieldClass}
            >
              <option value="">全部班级</option>
              {classOptions.map((item) => (
                <option key={item.id} value={item.name}>
                  {item.subject ? `${item.name} · ${item.subject}` : item.name}
                </option>
              ))}
            </select>
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
            <select
              aria-label="老师"
              value={filters.teacherName ?? ''}
              onChange={(event) => handleFilterChange('teacherName', event.target.value)}
              className={workspaceFieldClass}
            >
              <option value="">全部老师</option>
              {teacherOptions.map((item) => (
                <option key={item.id} value={item.name}>{item.name}</option>
              ))}
            </select>
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
                const showsTeacherSnapshot = hasSnapshotDifference(item.teacherName, item.teacherNameSnapshot);
                const showsClassSnapshot = hasSnapshotDifference(item.className, item.classNameSnapshot);
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
                        {showsClassSnapshot && (
                          <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">原始班级：{item.classNameSnapshot}</p>
                        )}
                      </div>
                      <span className="rounded-full border border-sky-200 bg-white/80 px-3 py-1 text-xs font-semibold text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                        {item.analysis.errorType || '待分析'}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                      <span>老师：{item.teacherName || '未标注'}</span>
                      {showsTeacherSnapshot && <span>原始老师：{item.teacherNameSnapshot}</span>}
                      <span>映射状态：{formatWrongQuestionMappingStatus(item.mappingStatus)}</span>
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
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">选中记录后会拉取详情，可直接保存教师复盘内容。</p>
              </div>

              {detailError && (
                <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                  <AlertCircle size={16} />
                  {detailError}
                </div>
              )}

              {saveError && (
                <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                  <AlertCircle size={16} />
                  {saveError}
                </div>
              )}

              {selectedRecord ? (
                <>
                  <div className={`${workspaceSoftCardClass} space-y-3 p-4`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-lg font-semibold text-slate-900 dark:text-white">{selectedRecord.studentName}</span>
                      <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                        {selectedRecord.subject || '未标注科目'}
                      </span>
                    </div>
                    <p className="text-sm text-slate-500 dark:text-slate-400">班级：{selectedRecord.className || '未标注班级'}</p>
                    {hasSnapshotDifference(selectedRecord.className, selectedRecord.classNameSnapshot) && (
                      <p className="text-sm text-amber-700 dark:text-amber-300">原始班级：{selectedRecord.classNameSnapshot}</p>
                    )}
                    <p className="text-sm text-slate-500 dark:text-slate-400">老师：{selectedRecord.teacherName || '未标注老师'}</p>
                    {hasSnapshotDifference(selectedRecord.teacherName, selectedRecord.teacherNameSnapshot) && (
                      <p className="text-sm text-amber-700 dark:text-amber-300">原始老师：{selectedRecord.teacherNameSnapshot}</p>
                    )}
                    <p className="text-sm text-slate-500 dark:text-slate-400">映射状态：{formatWrongQuestionMappingStatus(selectedRecord.mappingStatus)}</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">记录时间：{selectedRecord.createdAt}</p>
                  </div>

                  {!isMappedWrongQuestionRecord(selectedRecord.mappingStatus) && (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-200">
                      <div className="flex items-start gap-2">
                        <AlertCircle size={16} className="mt-0.5" />
                        <div>
                          <p className="font-semibold">主数据映射待处理</p>
                          <p className="mt-1">当前老师或班级仍在沿用原始快照，请先在“主数据映射”里确认 canonical 身份。</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {detailLoading && (
                    <div className="rounded-2xl border border-dashed border-sky-200 px-4 py-3 text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
                      正在加载记录详情...
                    </div>
                  )}

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

                  {selectedDraft && (
                    <div className={`${workspaceSoftCardClass} space-y-4 p-4`}>
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <p className="text-sm font-semibold text-slate-900 dark:text-white">教师复盘</p>
                          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">保存失败时会保留当前草稿，便于继续修改后重试。</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => void handleSaveReview()}
                          disabled={savingReview}
                          className={workspacePrimaryButtonClass}
                        >
                          保存教师复盘
                        </button>
                      </div>

                      <div className="grid gap-4 sm:grid-cols-2">
                        <label className="space-y-2 text-sm sm:col-span-2">
                          <span className="text-slate-500 dark:text-slate-400">selectedErrorType</span>
                          <input
                            type="text"
                            value={selectedDraft.selectedErrorType}
                            onChange={(event) => handleDraftChange('selectedErrorType', event.target.value)}
                            className={workspaceFieldClass}
                            placeholder="填写教师最终确认的错误类型"
                          />
                        </label>
                        <label className="space-y-2 text-sm">
                          <span className="text-slate-500 dark:text-slate-400">selectedKnowledgePoints</span>
                          <textarea
                            value={selectedKnowledgePointText}
                            onChange={(event) => handleDraftChange('selectedKnowledgePoints', event.target.value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                            className={`${workspaceFieldClass} min-h-28 resize-y`}
                            placeholder="每行一个知识点"
                          />
                        </label>
                        <label className="space-y-2 text-sm">
                          <span className="text-slate-500 dark:text-slate-400">selectedActions</span>
                          <textarea
                            value={selectedActionsText}
                            onChange={(event) => handleDraftChange('selectedActions', event.target.value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                            className={`${workspaceFieldClass} min-h-28 resize-y`}
                            placeholder="每行一个后续动作"
                          />
                        </label>
                        <label className="space-y-2 text-sm">
                          <span className="text-slate-500 dark:text-slate-400">selectedReasons</span>
                          <textarea
                            value={selectedReasonsText}
                            onChange={(event) => handleDraftChange('selectedReasons', event.target.value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                            className={`${workspaceFieldClass} min-h-28 resize-y`}
                            placeholder="每行一个原因"
                          />
                        </label>
                        <label className="space-y-2 text-sm">
                          <span className="text-slate-500 dark:text-slate-400">studentNote</span>
                          <textarea
                            value={selectedDraft.studentNote}
                            onChange={(event) => handleDraftChange('studentNote', event.target.value)}
                            className={`${workspaceFieldClass} min-h-28 resize-y`}
                            placeholder="补充学生当前表现或教师备注"
                          />
                        </label>
                      </div>
                    </div>
                  )}
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