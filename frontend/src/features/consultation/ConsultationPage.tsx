import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, CalendarDays, ChevronDown, Cpu, Eye, Pencil, PlusCircle, RefreshCw, Search, Trash2, } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';

import type {
  ClassItem,
  CurrentUser,
} from '../../appTypes';
import type {
  ConsultationFilterKey, ConsultationFormValues, ConsultationRecord, ConsultationResultStage, ConsultationTeacherOption,
} from './consultationTypes';
import {
  ConsultationModal,
  normalizeConsultationTeacherOption,
  toConsultationFormValues,
} from './ConsultationModal';
import { ConsultationBatchModal } from './ConsultationBatchModal';
import {
  ConsultationCardExpandableText,
  ConsultationFlowBar,
  ConsultationStatusLamp,
  buildConsultationTeacherDirectory,
  clearConsultationResultStage,
  consultationFilterGroups,
  consultationFilterLabels,
  consultationFlowStages,
  consultationProcessStages,
  consultationResultShortLabel,
  consultationStageShortLabel,
  endConsultationValues,
  getConsultationFilterKey,
  getConsultationOver30SectionLabel,
  getConsultationSourceLabel,
  getConsultationTeacherName,
  isConsultationEnded,
  isConsultationResultStage,
  moveConsultationStage,
  normalizeConsultationRecord,
  restoreConsultationValues,
  setConsultationResultStage,
  sortConsultationsForFilter,
  toggleConsultationStageLight,
} from './consultationShared';
import { workspaceCardClass, workspaceFieldClass, workspacePageClass, workspacePrimaryButtonClass, workspaceSecondaryButtonClass, workspaceSectionTextClass, workspaceSectionTitleClass, apiFetch, getTodayIsoDate } from '../../workspaceShared';
import { hasStaffAccess } from '../navigation/workspaceAccess';

export function ConsultationPage({ currentUser }: { currentUser: CurrentUser }) {
  const canManage = hasStaffAccess(currentUser.role);
  const canEditConsultations = canManage || currentUser.role === 'member';
  const [records, setRecords] = useState<ConsultationRecord[]>([]);
  const [consultationTeachers, setConsultationTeachers] = useState<ConsultationTeacherOption[]>([]);
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [batchModalOpen, setBatchModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'view' | 'create' | 'edit'>('view');
  const [selectedRecord, setSelectedRecord] = useState<ConsultationRecord | null>(null);
  const [activeFilter, setActiveFilter] = useState<ConsultationFilterKey | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [restoreConfirmRecord, setRestoreConfirmRecord] = useState<ConsultationRecord | null>(null);
  const loadRequestId = useRef(0);
  const teacherDirectory = buildConsultationTeacherDirectory(records);

  const load = useCallback(async (keyword: string) => {
    const requestId = ++loadRequestId.current;
    setLoading(true);
    setError('');
    try {
      const query = keyword.trim();
      const data = await apiFetch<ConsultationRecord[]>(`/api/consultations?q=${encodeURIComponent(query)}`);
      if (requestId !== loadRequestId.current) {
        return;
      }
      setRecords(data.map(normalizeConsultationRecord));
    } catch (err) {
      if (requestId !== loadRequestId.current) {
        return;
      }
      setError(err instanceof Error ? err.message : '咨询记录加载失败');
    } finally {
      if (requestId === loadRequestId.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    let active = true;
    apiFetch<ClassItem[]>('/api/classes')
      .then((items) => {
        if (active) setClasses(items);
      })
      .catch(() => {
        if (active) setClasses([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      load(search).catch(() => undefined);
    }, 250);

    return () => window.clearTimeout(timer);
  }, [load, search]);

  useEffect(() => {
    let active = true;
    apiFetch<ConsultationTeacherOption[]>('/api/consultation-teachers')
      .then((items) => {
        if (!active) {
          return;
        }
        setConsultationTeachers(items.map(normalizeConsultationTeacherOption));
      })
      .catch(() => {
        if (!active) {
          return;
        }
        setConsultationTeachers([]);
      });

    return () => {
      active = false;
    };
  }, []);

  const openCreateModal = () => {
    setSelectedRecord(null);
    setModalMode('create');
    setModalOpen(true);
    setError('');
  };

  const openBatchModal = () => {
    setBatchModalOpen(true);
    setError('');
  };

  const openViewModal = (record: ConsultationRecord) => {
    setSelectedRecord(record);
    setModalMode('view');
    setModalOpen(true);
    setError('');
  };

  const openEditModal = (record: ConsultationRecord) => {
    setSelectedRecord(record);
    setModalMode('edit');
    setModalOpen(true);
    setError('');
  };

  const closeModal = () => {
    setModalOpen(false);
    setSelectedRecord(null);
    setSubmitting(false);
  };

  const closeBatchModal = () => {
    setBatchModalOpen(false);
  };

  const handleSubmit = async (values: ConsultationFormValues) => {
    setSubmitting(true);
    setError('');
    try {
      if (modalMode === 'edit' && selectedRecord) {
        await apiFetch(`/api/consultations/${selectedRecord.id}`, {
          method: 'PUT',
          body: JSON.stringify(values),
        });
      } else {
        await apiFetch('/api/consultations', {
          method: 'POST',
          body: JSON.stringify(values),
        });
      }
      closeModal();
      await load(search);
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存咨询记录失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedRecord) {
      return;
    }
    if (!window.confirm('确定删除这条咨询记录吗？')) {
      return;
    }
    setDeletingId(selectedRecord.id);
    setError('');
    try {
      await apiFetch(`/api/consultations/${selectedRecord.id}`, { method: 'DELETE' });
      closeModal();
      await load(search);
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除咨询记录失败');
    } finally {
      setDeletingId(null);
    }
  };

  const isBusy = submitting || deletingId !== null;
  const consultationTodayIso = getTodayIsoDate();
  const consultationFilterCounts = useMemo(() => {
    const counts = consultationFilterGroups
      .flatMap((group) => group.items)
      .reduce((acc, item) => ({ ...acc, [item.key]: 0 }), {} as Record<ConsultationFilterKey, number>);
    for (const record of records) {
      counts[getConsultationFilterKey(record, consultationTodayIso)] += 1;
    }
    return counts;
  }, [records, consultationTodayIso]);
  const visibleRecords = useMemo(() => {
    if (!activeFilter) {
      return records;
    }
    return sortConsultationsForFilter(
      records.filter((record) => getConsultationFilterKey(record, consultationTodayIso) === activeFilter),
      activeFilter,
    );
  }, [records, consultationTodayIso, activeFilter]);
  const getVisibleRecordSectionLabel = (record: ConsultationRecord, index: number): string | null => {
    if (activeFilter !== 'pending-over30') {
      return null;
    }
    const label = getConsultationOver30SectionLabel(record, consultationTodayIso);
    const previousRecord = visibleRecords[index - 1];
    if (!previousRecord) {
      return label;
    }
    return getConsultationOver30SectionLabel(previousRecord, consultationTodayIso) === label ? null : label;
  };

  const handleInlineStageToggle = async (record: ConsultationRecord, stage: string) => {
    if (!canEditConsultations || isBusy || isConsultationEnded(record.flow_stage)) {
      return;
    }
    setError('');
    const values = toggleConsultationStageLight(toConsultationFormValues(record), stage);
    await saveInlineConsultationUpdate(record, values, '更新咨询流程失败');
  };

  const handleInlineStageMove = async (record: ConsultationRecord, stage: string) => {
    if (!canEditConsultations || isBusy || isConsultationEnded(record.flow_stage)) {
      return;
    }
    setError('');
    const values = moveConsultationStage(toConsultationFormValues(record), stage);
    await saveInlineConsultationUpdate(record, values, '更新咨询流程失败');
  };

  const handleInlineResultChange = async (record: ConsultationRecord, resultStage: ConsultationResultStage) => {
    if (!canEditConsultations || isBusy || isConsultationEnded(record.flow_stage)) {
      return;
    }
    if (resultStage === '成功进班' && !record.success_class_id && !record.success_class_manual.trim()) {
      setError('成功进班必须先选择或填写班级。');
      return;
    }
    setError('');
    const values = setConsultationResultStage(toConsultationFormValues(record), resultStage);
    await saveInlineConsultationUpdate(record, values, '更新咨询结果失败');
  };

  const handleInlineResultClick = async (record: ConsultationRecord) => {
    if (!canEditConsultations || isBusy || isConsultationEnded(record.flow_stage)) {
      return;
    }
    if (!isConsultationResultStage(record.flow_stage) && !record.success_class_id && !record.success_class_manual.trim()) {
      setError('成功进班必须先选择或填写班级。');
      return;
    }
    setError('');
    const formValues = toConsultationFormValues(record);
    const values = isConsultationResultStage(record.flow_stage)
      ? clearConsultationResultStage(formValues)
      : setConsultationResultStage(formValues, '成功进班');
    await saveInlineConsultationUpdate(record, values, '更新咨询结果失败');
  };

  const handleInlineEndConsultation = async (record: ConsultationRecord) => {
    if (!canEditConsultations || isBusy) {
      return;
    }
    if (isConsultationEnded(record.flow_stage)) {
      setRestoreConfirmRecord(record);
      return;
    }
    setError('');
    const values = endConsultationValues(toConsultationFormValues(record));
    await saveInlineConsultationUpdate(record, values, '结束咨询失败');
  };

  const handleConfirmRestoreConsultation = async () => {
    if (!restoreConfirmRecord) {
      return;
    }
    const record = restoreConfirmRecord;
    setRestoreConfirmRecord(null);
    setError('');
    const values = restoreConsultationValues(toConsultationFormValues(restoreConfirmRecord));
    await saveInlineConsultationUpdate(record, values, '恢复咨询失败');
  };

  const saveInlineConsultationUpdate = async (record: ConsultationRecord, values: ConsultationFormValues, fallbackError: string) => {
    const optimistic = normalizeConsultationRecord({ ...record, ...values });
    setRecords((current) => current.map((item) => (item.id === record.id ? optimistic : item)));
    try {
      const updated = await apiFetch<ConsultationRecord>(`/api/consultations/${record.id}`, {
        method: 'PUT',
        body: JSON.stringify(values),
      });
      setRecords((current) => current.map((item) => (item.id === record.id ? normalizeConsultationRecord(updated) : item)));
    } catch (err) {
      setError(err instanceof Error ? err.message : fallbackError);
      await load(search);
    }
  };

  const renderConsultationIconActions = (record: ConsultationRecord, busy: boolean, compact = false) => {
    const frozen = isConsultationEnded(record.flow_stage);
    const sizeClass = compact ? 'h-7 w-7' : 'h-8 w-8';
    const iconSize = compact ? 12 : 13;
    return (
      <div className="flex shrink-0 items-center justify-end gap-1">
        <button
          type="button"
          onClick={() => openViewModal(record)}
          className={`${sizeClass} flex items-center justify-center rounded-full border border-sky-100 bg-white/85 text-slate-600 transition hover:bg-sky-50 hover:text-sky-700 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10`}
          title="查看"
          aria-label="查看咨询"
        >
          <Eye size={iconSize} />
        </button>
        {canEditConsultations && (
          <button
            type="button"
            onClick={() => openEditModal(record)}
            className={`${sizeClass} flex items-center justify-center rounded-full border border-sky-100 bg-sky-50/85 text-sky-700 transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:bg-sky-400/10 dark:text-sky-200 dark:hover:bg-sky-400/20`}
            title={frozen ? '查看结束备注' : '编辑这条咨询'}
            aria-label="编辑咨询"
            disabled={busy}
          >
            <Pencil size={iconSize} />
          </button>
        )}
      </div>
    );
  };

  const renderInlineFlow = (record: ConsultationRecord, busy: boolean) => {
    const frozen = isConsultationEnded(record.flow_stage);
    return (
      <ConsultationFlowBar
        mode="list"
        stage={record.flow_stage}
        completedStages={record.completed_stages}
        editable={canEditConsultations && !busy && !frozen}
        showOver
        overDisabled={!canEditConsultations || busy}
        onStageClick={(stage) => handleInlineStageToggle(record, stage)}
        onStageDoubleClick={(stage) => handleInlineStageMove(record, stage)}
        onResultChange={(stage) => handleInlineResultChange(record, stage)}
        onResultClick={() => handleInlineResultClick(record)}
        onResultDoubleClick={() => handleInlineResultChange(record, '成功进班')}
        onOverClick={() => handleInlineEndConsultation(record)}
      />
    );
  };

  const renderB3MobileTimeline = (record: ConsultationRecord, busy: boolean) => {
    const currentStage = record.flow_stage || consultationFlowStages[0];
    const frozen = isConsultationEnded(currentStage);
    const completedSet = new Set(record.completed_stages || []);
    if (!frozen && consultationProcessStages.includes(currentStage)) {
      completedSet.add(currentStage);
    }
    const currentProcessIndex = consultationProcessStages.indexOf(currentStage);
    const resultStage = isConsultationResultStage(currentStage)
      ? currentStage
      : (record.completed_stages || []).find(isConsultationResultStage) || '';
    const resultActive = isConsultationResultStage(currentStage);
    const resultCompleted = Boolean(resultStage) && currentProcessIndex < 0;
    const timelineItems = [
      ...consultationProcessStages.map((stageItem) => {
        const stageIndex = consultationProcessStages.indexOf(stageItem);
        const isCurrent = stageItem === currentStage;
        const isAfterCurrentProcess = currentProcessIndex >= 0 && stageIndex > currentProcessIndex;
        return {
          key: stageItem,
          label: consultationStageShortLabel(stageItem),
          active: isCurrent,
          completed: completedSet.has(stageItem) && !isAfterCurrentProcess,
          disabled: frozen || busy || !canEditConsultations,
          onClick: () => handleInlineStageToggle(record, stageItem),
          onDoubleClick: () => handleInlineStageMove(record, stageItem),
        };
      }),
      {
        key: 'consultation-result',
        label: consultationResultShortLabel(resultStage) || '进',
        active: resultActive,
        completed: resultCompleted,
        disabled: frozen || busy || !canEditConsultations,
        onClick: () => handleInlineResultClick(record),
        onDoubleClick: () => handleInlineResultChange(record, '成功进班'),
      },
    ];

    return (
      <div className="min-w-0 pb-0.5">
        <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_minmax(2.9rem,3.75rem)] items-center gap-1.5">
          <div className="relative grid min-w-0 grid-cols-6 items-start gap-1 px-1 pt-1">
            <span className="absolute left-3 right-3 top-[0.68rem] h-px bg-[#D9EEF7]" aria-hidden="true" />
            {timelineItems.map((item) => (
              <button
                key={item.key}
                type="button"
                disabled={item.disabled}
                onClick={item.onClick}
                onDoubleClick={item.onDoubleClick}
                className="relative z-10 flex min-w-0 flex-col items-center gap-0.5 disabled:cursor-default"
                title={item.key === 'consultation-result' ? resultStage || '成功进班' : item.key}
              >
                <span
                  className={`flex h-[18px] w-[18px] items-center justify-center rounded-full border text-[10px] font-extrabold leading-none transition ${
                    item.active
                      ? 'border-[#0EA5E9] bg-[#0EA5E9] text-white'
                      : item.completed
                        ? 'border-[#22B981] bg-[#22B981] text-white'
                        : 'border-slate-300 bg-white text-transparent'
                  }`}
                >
                  {item.active ? (item.key === 'consultation-result' ? '☀' : item.label) : item.completed ? '✓' : ''}
                </span>
                <span className={`truncate text-[10px] font-bold leading-4 ${item.active ? 'text-[#0EA5E9]' : item.completed ? 'text-[#0A8F65]' : 'text-[#7188A6]'}`}>
                  {item.label}
                </span>
              </button>
            ))}
          </div>
          {renderOverButton(record, busy, 'h-8 px-1.5 text-[10px]')}
        </div>
      </div>
    );
  };

  const renderB3FlowStrip = (record: ConsultationRecord, busy: boolean, mobile = false) => {
    const frozen = isConsultationEnded(record.flow_stage);
    return (
      <div className={`min-w-0 overflow-visible ${frozen ? 'opacity-75' : ''}`}>
        {mobile ? renderB3MobileTimeline(record, busy) : renderInlineFlow(record, busy)}
      </div>
    );
  };

  const renderInfoCell = (label: string, value: string, className = '') => (
    <div className={`min-w-0 ${className}`}>
      <p className="truncate text-[11px] font-bold leading-4 text-[#7188A6]">{label}</p>
      <p className="mt-0.5 truncate whitespace-nowrap text-[13px] font-semibold leading-5 text-[#1F2A44] dark:text-white">{value || '—'}</p>
    </div>
  );

  const renderTimeRow = (record: ConsultationRecord, boxed = false) => (
    <div className={boxed
      ? 'grid grid-cols-2 overflow-hidden rounded-lg border border-[#D9EEF7] bg-white/80 dark:border-white/10 dark:bg-slate-950/70'
      : 'flex min-w-0 flex-wrap items-center gap-x-5 gap-y-1 text-[11px] text-[#7188A6] dark:text-slate-400'
    }>
      <div className={boxed ? 'min-w-0 border-r border-sky-100 p-3 dark:border-white/10' : 'inline-flex min-w-0 items-center gap-2'}>
        <CalendarDays size={boxed ? 0 : 13} className={boxed ? 'hidden' : 'text-slate-400'} />
        <p className={boxed ? 'text-[11px] font-bold tracking-[0.06em] text-slate-400' : 'whitespace-nowrap font-bold text-slate-400'}>录入时间</p>
        <p className={boxed ? 'mt-1 whitespace-pre-line text-sm font-semibold text-slate-700 dark:text-slate-200' : 'truncate'}>{record.created_at || '—'}</p>
      </div>
      <div className={boxed ? 'min-w-0 p-3' : 'inline-flex min-w-0 items-center gap-2'}>
        <CalendarDays size={boxed ? 0 : 13} className={boxed ? 'hidden' : 'text-slate-400'} />
        <p className={boxed ? 'text-[11px] font-bold tracking-[0.06em] text-slate-400' : 'whitespace-nowrap font-bold text-slate-400'}>更新时间</p>
        <p className={boxed ? 'mt-1 whitespace-pre-line text-sm font-semibold text-slate-700 dark:text-slate-200' : 'truncate'}>{record.updated_at || '—'}</p>
      </div>
    </div>
  );

  const renderConsultationDetail = (needDetail?: string, followUpNote?: string, mobile = false) => {
    if (!needDetail && !followUpNote) {
      return null;
    }
    return (
      <div className={`min-w-0 ${mobile ? 'space-y-1.5 border-y border-[#EEF7FC] py-2.5 dark:border-white/10' : 'space-y-1 border-t border-[#EEF7FC] pt-2 dark:border-white/10'}`}>
        {needDetail && <ConsultationCardExpandableText label="咨询详情" text={needDetail} lines={mobile ? 2 : 1} />}
        {followUpNote && <ConsultationCardExpandableText label="跟进" text={followUpNote} />}
      </div>
    );
  };

  const getRecordResultPill = (record: ConsultationRecord) => {
    if (record.flow_stage === '成功进班') {
      return { label: '☀️ 成功进班', className: 'bg-sky-500 text-white' };
    }
    if (record.flow_stage === '试听失败') {
      return { label: '😢 试听未成', className: 'bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-300' };
    }
    if (record.flow_stage === '咨询结束') {
      return { label: 'OVER', className: 'bg-rose-500 text-white' };
    }
    return { label: '未选择结果', className: 'bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-300' };
  };

  const renderOverButton = (record: ConsultationRecord, busy: boolean, className = '') => (
    <button
      type="button"
      onClick={() => handleInlineEndConsultation(record)}
      className={`inline-flex min-w-0 items-center justify-center whitespace-nowrap rounded-lg border border-rose-200 bg-rose-50 font-extrabold text-[#F45B7A] transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
      disabled={!canEditConsultations || busy}
    >
      OVER
    </button>
  );

  const renderDeleteButton = (record: ConsultationRecord, busy: boolean) => canManage ? (
    <button
      type="button"
      onClick={async () => {
        if (!window.confirm('确定删除这条咨询记录吗？')) {
          return;
        }
        setDeletingId(record.id);
        try {
          await apiFetch(`/api/consultations/${record.id}`, { method: 'DELETE' });
          await load(search);
        } catch (err) {
          setError(err instanceof Error ? err.message : '删除咨询记录失败');
        } finally {
          setDeletingId(null);
        }
      }}
      className="inline-flex h-8 w-full min-w-0 items-center justify-center gap-1 whitespace-nowrap rounded-lg border border-rose-200 bg-white px-3 text-xs font-semibold text-[#F45B7A] transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
      disabled={busy}
    >
      <Trash2 size={14} />
      删除
    </button>
  ) : null;

  const renderDesktopConsultationCard = (record: ConsultationRecord, index: number) => {
    const busy = isBusy && selectedRecord?.id === record.id;
    const needDetail = record.need_detail?.trim();
    const followUpNote = record.follow_up_note?.trim();
    const sectionLabel = getVisibleRecordSectionLabel(record, index);
    return (
      <React.Fragment key={record.id}>
        {sectionLabel && <div className="px-1 pt-1 text-[11px] font-bold tracking-[0.16em] text-slate-400">{sectionLabel}</div>}
        <article className="overflow-hidden rounded-[14px] border border-[#D9EEF7] bg-white dark:border-white/10 dark:bg-slate-950/70">
          <div className="grid grid-cols-[96px_88px_112px_minmax(120px,160px)_120px_132px_72px] items-center border-b border-[#EEF7FC] px-4 py-3 text-sm dark:border-white/10">
            {renderInfoCell('日期', record.date || '—')}
            {renderInfoCell('咨询老师', getConsultationTeacherName(record, teacherDirectory), 'border-l border-[#D9EEF7] pl-3 dark:border-white/10')}
            {renderInfoCell('科目 / 年级', `${record.consultation_subject || '未填写'} / ${record.grade || '—'}`, 'border-l border-[#D9EEF7] pl-3 dark:border-white/10')}
            {renderInfoCell('家长微信', record.parent_wechat_name || '—', 'border-l border-[#D9EEF7] pl-3 dark:border-white/10')}
            {renderInfoCell('学生姓名', record.child_name?.trim() || '待补充', 'border-l border-[#D9EEF7] pl-3 dark:border-white/10')}
            {renderInfoCell('来源', getConsultationSourceLabel(record), 'border-l border-[#D9EEF7] pl-3 dark:border-white/10')}
            <div className="border-l border-[#D9EEF7] pl-3 dark:border-white/10">{renderConsultationIconActions(record, busy, true)}</div>
          </div>
          <div className="space-y-2 px-4 py-2.5">
            {renderConsultationDetail(needDetail, followUpNote)}
            {renderTimeRow(record)}
          </div>
          <div className="grid grid-cols-[0.875rem_minmax(0,1fr)] items-center gap-2.5 border-t border-[#EEF7FC] bg-[#F9FDFF] px-4 py-3 dark:border-white/10 dark:bg-white/[0.03]">
            <ConsultationStatusLamp stage={record.flow_stage} />
            {renderB3FlowStrip(record, busy)}
          </div>
        </article>
      </React.Fragment>
    );
  };

  const renderPadConsultationCard = (record: ConsultationRecord, index: number) => {
    const busy = isBusy && selectedRecord?.id === record.id;
    const needDetail = record.need_detail?.trim();
    const followUpNote = record.follow_up_note?.trim();
    const sectionLabel = getVisibleRecordSectionLabel(record, index);
    return (
      <React.Fragment key={record.id}>
        {sectionLabel && <div className="px-1 pt-1 text-[11px] font-bold tracking-[0.16em] text-slate-400">{sectionLabel}</div>}
        <article className="overflow-hidden rounded-[14px] border border-[#D9EEF7] bg-white dark:border-white/10 dark:bg-slate-950/70">
          <div className="grid grid-cols-[0.82fr_1fr_1fr_3.6rem] items-center border-b border-[#EEF7FC] px-4 py-3 text-sm dark:border-white/10">
            {renderInfoCell('日期', record.date || '—')}
            {renderInfoCell('咨询老师', getConsultationTeacherName(record, teacherDirectory), 'border-l border-sky-100/80 pl-3 dark:border-white/10')}
            {renderInfoCell('科目 / 年级', `${record.consultation_subject || '未填写'} / ${record.grade || '—'}`, 'border-l border-sky-100/80 pl-3 dark:border-white/10')}
            <div className="border-l border-sky-100/80 pl-3 dark:border-white/10">{renderConsultationIconActions(record, busy, true)}</div>
          </div>
          <div className="grid grid-cols-[repeat(3,minmax(0,1fr))] border-b border-[#EEF7FC] px-4 py-2.5 text-sm dark:border-white/10">
            {renderInfoCell('家长微信', record.parent_wechat_name || '—')}
            {renderInfoCell('学生姓名', record.child_name?.trim() || '待补充', 'border-l border-sky-100/80 pl-3 dark:border-white/10')}
            {renderInfoCell('来源', getConsultationSourceLabel(record), 'border-l border-sky-100/80 pl-3 dark:border-white/10')}
          </div>
          <div className="space-y-2 px-4 py-2.5">
            {renderConsultationDetail(needDetail, followUpNote)}
            {renderTimeRow(record)}
          </div>
          <div className="grid grid-cols-[0.875rem_minmax(0,1fr)] items-center gap-2 border-t border-[#EEF7FC] bg-[#F9FDFF] px-4 py-3 dark:border-white/10 dark:bg-white/[0.03]">
            <ConsultationStatusLamp stage={record.flow_stage} />
            {renderB3FlowStrip(record, busy)}
          </div>
        </article>
      </React.Fragment>
    );
  };

  const renderMobileConsultationCard = (record: ConsultationRecord, index: number) => {
    const busy = isBusy && selectedRecord?.id === record.id;
    const needDetail = record.need_detail?.trim();
    const followUpNote = record.follow_up_note?.trim();
    const sectionLabel = getVisibleRecordSectionLabel(record, index);
    const resultPill = getRecordResultPill(record);
    const showTopResultPill = record.flow_stage !== '咨询结束';
    const mobileResultStage = isConsultationResultStage(record.flow_stage)
      ? record.flow_stage
      : (record.completed_stages || []).find(isConsultationResultStage) || '';
    return (
      <React.Fragment key={record.id}>
        {sectionLabel && <div className="px-1 text-[11px] font-bold tracking-[0.16em] text-slate-400">{sectionLabel}</div>}
        <article className="relative space-y-3 rounded-[14px] border border-[#D9EEF7] bg-white p-3.5 dark:border-white/10 dark:bg-slate-950/70">
          <div className="flex items-center justify-between gap-2 border-b border-sky-50 pb-2.5 dark:border-white/10">
            <p className="whitespace-nowrap font-mono text-sm font-semibold text-slate-900 dark:text-white">{record.date || '—'}</p>
            <div className="flex min-w-0 items-center gap-2">
              {showTopResultPill && (
                <div className={`relative inline-flex h-7 min-w-0 max-w-[7.5rem] items-center overflow-hidden rounded-lg text-[11px] font-extrabold ${resultPill.className}`}>
                  <span className="min-w-0 flex-1 truncate px-2.5 pr-1 text-center">{resultPill.label}</span>
                  <span className="relative flex h-full w-6 shrink-0 items-center justify-center border-l border-white/30 bg-white/20">
                    <ChevronDown size={12} className="pointer-events-none" />
                    <select
                      value={mobileResultStage}
                      disabled={!canEditConsultations || busy || isConsultationEnded(record.flow_stage)}
                      onClick={(event) => event.stopPropagation()}
                      onChange={(event) => {
                        const value = event.target.value as ConsultationResultStage | '';
                        if (value) handleInlineResultChange(record, value);
                      }}
                      className="absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-default"
                      aria-label="选择咨询结果"
                      title="选择咨询结果"
                    >
                      <option value="">未选择结果</option>
                      <option value="成功进班">☀️ 成功进班</option>
                      <option value="试听失败">😢 试听未成</option>
                    </select>
                  </span>
                </div>
              )}
              {renderConsultationIconActions(record, busy, true)}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-3">
            {renderInfoCell('咨询老师', getConsultationTeacherName(record, teacherDirectory))}
            {renderInfoCell('科目 / 年级', `${record.consultation_subject || '未填写'} / ${record.grade || '—'}`)}
            {renderInfoCell('家长微信', record.parent_wechat_name || '—')}
            {renderInfoCell('学生姓名', record.child_name?.trim() || '待补充')}
            {renderInfoCell('来源', getConsultationSourceLabel(record), 'col-span-2')}
          </div>
          {renderConsultationDetail(needDetail, followUpNote, true)}
          {renderTimeRow(record, true)}
          <div className="space-y-2.5">
            <div className="grid grid-cols-[1rem_minmax(0,1fr)] items-center gap-2">
              <ConsultationStatusLamp stage={record.flow_stage} />
              <div className="min-w-0 overflow-visible">{renderB3FlowStrip(record, busy, true)}</div>
            </div>
            {canEditConsultations && (
              <div className={canManage ? 'grid grid-cols-1 gap-2.5' : 'hidden'}>
                {renderDeleteButton(record, busy)}
              </div>
            )}
          </div>
        </article>
      </React.Fragment>
    );
  };

  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h3 className={`${workspaceSectionTitleClass} mt-3`}>咨询记录</h3>
          <p className={`${workspaceSectionTextClass} mt-2`}>
            记录咨询、跟进和备注，搜索后直接筛当前列表。
          </p>
        </div>
        <div className="flex w-full flex-col gap-3 lg:w-auto lg:items-end">
          <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-[22rem] xl:w-[24rem]">
            <label className="relative min-w-0 flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-400" size={18} />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索姓名、微信、老师、科目、咨询内容"
                className={`${workspaceFieldClass} w-full rounded-full py-2.5 pl-11 pr-4`}
              />
            </label>
          </div>
          <div className={`grid w-full gap-2 self-start lg:w-[22rem] lg:self-auto xl:w-[24rem] ${canManage ? 'grid-cols-3' : 'grid-cols-2'}`}>
            <button
              type="button"
              onClick={() => load(search).catch(() => undefined)}
              className={`${workspaceSecondaryButtonClass} h-10 w-full min-w-0 !gap-1 !px-1 !py-2 text-[11px] sm:text-xs`}
            >
              <RefreshCw size={14} />
              刷新
            </button>
            {canManage && (
              <button
                type="button"
                onClick={openBatchModal}
                className={`${workspaceSecondaryButtonClass} h-10 w-full min-w-0 !gap-1 !px-1 !py-2 text-[11px] sm:text-xs`}
              >
                <Cpu size={14} />
                AI 批量整理
              </button>
            )}
            <button
              type="button"
              onClick={openCreateModal}
              className={`${workspacePrimaryButtonClass} h-10 w-full min-w-0 !gap-1 !px-1 !py-2 text-[11px] sm:text-xs`}
            >
              <PlusCircle size={14} />
              新增记录
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div className={`${workspaceCardClass} p-3 sm:p-4`}>
        <div className="grid min-w-0 grid-cols-2 gap-2 min-[520px]:flex min-[520px]:items-center min-[520px]:gap-3 min-[520px]:overflow-hidden">
          {consultationFilterGroups.map((group) => (
            <div key={group.title} className="min-w-0 min-[520px]:flex min-[520px]:shrink-0 min-[520px]:items-center min-[520px]:gap-2">
              <p className="shrink-0 text-[11px] font-bold text-slate-400">{group.title}</p>
              <div className="mt-1 flex min-w-0 flex-wrap items-center gap-1 min-[520px]:mt-0 min-[520px]:flex-nowrap min-[520px]:gap-1.5">
                {group.items.map((item) => {
                  const active = activeFilter === item.key;
                  const count = consultationFilterCounts[item.key] || 0;
                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setActiveFilter((current) => (current === item.key ? null : item.key))}
                      className={`inline-flex h-7 shrink-0 items-center gap-0.5 rounded-full border px-1.5 text-[10px] font-bold transition min-[520px]:gap-1 min-[520px]:px-2 min-[520px]:text-[11px] ${
                        active
                          ? 'border-sky-200 bg-sky-500 text-white'
                          : 'border-sky-100 bg-white text-slate-600 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10'
                      }`}
                    >
                      <span className="whitespace-nowrap">{item.label}</span>
                      <span className={`rounded-full px-1 py-0.5 text-[10px] ${active ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-300'}`}>
                        {count}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className={`${workspaceCardClass} overflow-hidden`}>
        {loading ? (
          <div className="p-8 text-center text-slate-500 dark:text-slate-400">正在加载咨询记录...</div>
        ) : records.length === 0 ? (
          <div className="p-8 text-center text-slate-500 dark:text-slate-400">
            暂无咨询记录，点击「新增记录」开始录入。
          </div>
        ) : activeFilter && visibleRecords.length === 0 ? (
          <div className="p-8 text-center text-slate-500 dark:text-slate-400">
            当前分类「{consultationFilterLabels[activeFilter]}」暂无咨询记录。
          </div>
        ) : (
          <>
            <div className="grid gap-4 p-4 sm:p-5 md:hidden">
              {visibleRecords.map(renderMobileConsultationCard)}
            </div>

            <div className="hidden md:block xl:hidden">
              <div className="space-y-3 p-4">
                {visibleRecords.map(renderPadConsultationCard)}
              </div>
            </div>

            <div className="hidden xl:block">
              <div className="space-y-3 p-4">
                {visibleRecords.map(renderDesktopConsultationCard)}
              </div>
            </div>
          </>
        )}
      </div>

      <AnimatePresence>
        {batchModalOpen && canManage && (
          <ConsultationBatchModal
            open={batchModalOpen}
            onClose={closeBatchModal}
            onImported={async () => {
              await load(search);
            }}
          />
        )}
        {modalOpen && (
          <ConsultationModal
            open={modalOpen}
            mode={modalMode}
            record={selectedRecord}
            consultationTeachers={consultationTeachers}
            classes={classes}
            submitting={submitting}
            error={error}
            currentUser={currentUser}
            onClose={closeModal}
            onSubmit={handleSubmit}
            onDelete={canManage ? handleDelete : undefined}
            onRequestEdit={selectedRecord ? () => openEditModal(selectedRecord) : undefined}
          />
        )}
        {restoreConfirmRecord && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 px-4"
            onClick={(event) => event.target === event.currentTarget && setRestoreConfirmRecord(null)}
          >
            <div className="w-full max-w-sm rounded-3xl border border-sky-100 bg-white p-5 dark:border-white/10 dark:bg-slate-900">
              <p className="text-base font-bold text-slate-900 dark:text-white">是否恢复这个咨询？</p>
              <div className="mt-5 grid grid-cols-2 gap-3">
                <button type="button" onClick={handleConfirmRestoreConsultation} className={workspacePrimaryButtonClass}>
                  是
                </button>
                <button type="button" onClick={() => setRestoreConfirmRecord(null)} className={workspaceSecondaryButtonClass}>
                  否
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
