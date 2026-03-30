import React, { useCallback, useEffect, useState } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

import {
  workspaceCardClass,
  workspaceFieldClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSoftCardClass,
} from './App';
import {
  fetchWrongQuestionMappingQueue,
  resolveWrongQuestionMapping,
  type ResolveWrongQuestionMappingPayload,
  type WrongQuestionMappingQueueItem,
  type WrongQuestionMappingStatus,
} from './masterDataMappings';

type MasterDataMappingsPageProps = {
  currentUser: {
    display_name: string;
    organization_name: string;
  };
};

type MappingFormState = {
  teacherUserId: string;
  classId: string;
  mappingStatus: WrongQuestionMappingStatus;
};

const mappingStatusOptions: Array<{ value: WrongQuestionMappingStatus; label: string }> = [
  { value: 'mapped', label: '已映射' },
  { value: 'needs_review', label: '待复核' },
  { value: 'ambiguous', label: '有歧义' },
  { value: 'unmapped', label: '无法映射' },
];

function buildInitialFormState(item: WrongQuestionMappingQueueItem): MappingFormState {
  return {
    teacherUserId: item.teacherUserId === null ? '' : String(item.teacherUserId),
    classId: item.classId === null ? '' : String(item.classId),
    mappingStatus: item.mappingStatus,
  };
}

function parseOptionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function getStatusLabel(status: WrongQuestionMappingStatus): string {
  return mappingStatusOptions.find((option) => option.value === status)?.label || status;
}

export function MasterDataMappingsPage({ currentUser }: MasterDataMappingsPageProps) {
  const [items, setItems] = useState<WrongQuestionMappingQueueItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [savingRecordId, setSavingRecordId] = useState<string | null>(null);
  const [saveErrorByRecordId, setSaveErrorByRecordId] = useState<Record<string, string>>({});
  const [formByRecordId, setFormByRecordId] = useState<Record<string, MappingFormState>>({});

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const nextItems = await fetchWrongQuestionMappingQueue();
      setItems(nextItems);
      setFormByRecordId((current) => {
        const nextState = { ...current };
        for (const item of nextItems) {
          nextState[item.recordId] = current[item.recordId] ?? buildInitialFormState(item);
        }
        return nextState;
      });
    } catch (loadError) {
      setItems([]);
      setError(loadError instanceof Error ? loadError.message : '主数据映射队列加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const updateFormField = (recordId: string, nextPartialState: Partial<MappingFormState>) => {
    setFormByRecordId((current) => ({
      ...current,
      [recordId]: {
        ...(current[recordId] ?? { teacherUserId: '', classId: '', mappingStatus: 'needs_review' }),
        ...nextPartialState,
      },
    }));
  };

  const handleResolve = async (recordId: string) => {
    const currentForm = formByRecordId[recordId] ?? { teacherUserId: '', classId: '', mappingStatus: 'needs_review' };
    const payload: ResolveWrongQuestionMappingPayload = {
      teacher_user_id: parseOptionalNumber(currentForm.teacherUserId),
      class_id: parseOptionalNumber(currentForm.classId),
      mapping_status: currentForm.mappingStatus,
    };

    setSavingRecordId(recordId);
    setSaveErrorByRecordId((current) => ({ ...current, [recordId]: '' }));

    try {
      const resolved = await resolveWrongQuestionMapping(recordId, payload);
      setItems((current) => current.filter((item) => item.recordId !== recordId));
      setFormByRecordId((current) => ({
        ...current,
        [recordId]: buildInitialFormState(resolved),
      }));
    } catch (saveError) {
      setSaveErrorByRecordId((current) => ({
        ...current,
        [recordId]: saveError instanceof Error ? saveError.message : '主数据映射保存失败',
      }));
    } finally {
      setSavingRecordId((current) => (current === recordId ? null : current));
    }
  };

  return (
    <div className={workspacePageClass}>
      <section className={`${workspaceCardClass} space-y-6 p-6 sm:p-7`}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-600">MASTER DATA</p>
            <div className="space-y-1">
              <h2 className="text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">主数据映射</h2>
              <p className="max-w-3xl text-sm leading-7 text-slate-500 dark:text-slate-400">
                仅供 {currentUser.organization_name} 管理员处理错题记录中的老师与班级主数据映射，当前登录账号为 {currentUser.display_name}。
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              void loadQueue();
            }}
            disabled={loading || savingRecordId !== null}
            className={workspaceSecondaryButtonClass}
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : undefined} />
            刷新队列
          </button>
        </div>

        {error && (
          <div className="flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
            <AlertCircle size={18} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className={`${workspaceSoftCardClass} p-5 text-sm text-slate-500 dark:text-slate-400`}>
            正在加载主数据映射队列...
          </div>
        ) : items.length === 0 ? (
          <div className={`${workspaceSoftCardClass} p-5 text-sm text-slate-500 dark:text-slate-400`}>
            当前没有待处理的错题映射记录。
          </div>
        ) : (
          <div className="space-y-4">
            {items.map((item) => {
              const form = formByRecordId[item.recordId] ?? buildInitialFormState(item);
              const saving = savingRecordId === item.recordId;

              return (
                <article key={item.recordId} className={`${workspaceSoftCardClass} space-y-5 p-5`}>
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold text-sky-700 dark:bg-sky-500/15 dark:text-sky-200">
                          {getStatusLabel(item.mappingStatus)}
                        </span>
                        <span className="text-xs text-slate-400 dark:text-slate-500">记录 ID: {item.recordId}</span>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-3">
                        <div className="rounded-2xl border border-sky-100 bg-white/75 p-4 dark:border-white/10 dark:bg-slate-950/70">
                          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">来源老师</p>
                          <p className="mt-2 text-sm font-medium text-slate-800 dark:text-slate-100">{item.sourceTeacherName}</p>
                        </div>
                        <div className="rounded-2xl border border-sky-100 bg-white/75 p-4 dark:border-white/10 dark:bg-slate-950/70">
                          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">来源班级</p>
                          <p className="mt-2 text-sm font-medium text-slate-800 dark:text-slate-100">{item.sourceClassName}</p>
                        </div>
                        <div className="rounded-2xl border border-sky-100 bg-white/75 p-4 dark:border-white/10 dark:bg-slate-950/70">
                          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">来源科目</p>
                          <p className="mt-2 text-sm font-medium text-slate-800 dark:text-slate-100">{item.sourceSubject}</p>
                        </div>
                      </div>
                    </div>

                    <div className="min-w-0 rounded-2xl border border-slate-200/80 bg-white/75 px-4 py-3 text-sm text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 lg:w-72">
                      <p>当前老师映射: {item.mappedTeacherName}</p>
                      <p className="mt-1">当前班级映射: {item.mappedClassName}</p>
                      <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">最近更新: {item.updatedAt || '暂无时间'}</p>
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.9fr)_auto]">
                    <label className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
                      <span>老师 ID</span>
                      <input
                        name="teacher_user_id"
                        type="number"
                        inputMode="numeric"
                        className={workspaceFieldClass}
                        value={form.teacherUserId}
                        onInput={(event) => updateFormField(item.recordId, { teacherUserId: (event.target as HTMLInputElement).value })}
                        onChange={(event) => updateFormField(item.recordId, { teacherUserId: event.target.value })}
                        placeholder="teacher_user_id"
                      />
                    </label>
                    <label className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
                      <span>班级 ID</span>
                      <input
                        name="class_id"
                        type="number"
                        inputMode="numeric"
                        className={workspaceFieldClass}
                        value={form.classId}
                        onInput={(event) => updateFormField(item.recordId, { classId: (event.target as HTMLInputElement).value })}
                        onChange={(event) => updateFormField(item.recordId, { classId: event.target.value })}
                        placeholder="class_id"
                      />
                    </label>
                    <label className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
                      <span>映射状态</span>
                      <select
                        name="mapping_status"
                        className={workspaceFieldClass}
                        value={form.mappingStatus}
                        onChange={(event) => updateFormField(item.recordId, { mappingStatus: event.target.value as WrongQuestionMappingStatus })}
                      >
                        {mappingStatusOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="flex items-end">
                      <button
                        type="button"
                        data-record-id={item.recordId}
                        disabled={saving}
                        onClick={() => {
                          void handleResolve(item.recordId);
                        }}
                        className={workspacePrimaryButtonClass}
                      >
                        {saving ? '提交中...' : '提交映射'}
                      </button>
                    </div>
                  </div>

                  {saveErrorByRecordId[item.recordId] && (
                    <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
                      {saveErrorByRecordId[item.recordId]}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}