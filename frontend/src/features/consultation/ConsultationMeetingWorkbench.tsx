import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CalendarDays, CheckCircle2, Eye, Pencil } from 'lucide-react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';

import type { ClassItem, CurrentUser } from '../../App';
import type { ConsultationFormValues, ConsultationRecord, ConsultationTeacherOption } from './consultationTypes';
import {
  ConsultationModal,
  normalizeConsultationTeacherOption,
  toConsultationFormValues,
} from './ConsultationModal';
import {
  ConsultationCardExpandableText,
  ConsultationFlowBar,
  ConsultationStatusLamp,
  buildConsultationTeacherDirectory,
  consultationFlowStages,
  consultationMeetingVersion,
  consultationProcessStages,
  consultationResultShortLabel,
  consultationStageDisplayLabel,
  consultationStageShortLabel,
  endConsultationValues,
  getConsultationSourceLabel,
  getConsultationTeacherName,
  isConsultationEnded,
  isConsultationResultStage,
  normalizeConsultationRecord,
} from './consultationShared';
import {
  apiFetch,
  cn,
  getTodayIsoDate,
  readLocalStorageItem,
  workspaceGhostButtonClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSectionTextClass,
  workspaceSectionTitleClass,
  workspaceSoftCardClass,
  writeLocalStorageItem,
} from '../../workspaceShared';

export const ConsultationMeetingWorkbench = ({ currentUser }: { currentUser: CurrentUser }) => {
  const [records, setRecords] = useState<ConsultationRecord[]>([]);
  const [consultationTeachers, setConsultationTeachers] = useState<ConsultationTeacherOption[]>([]);
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [draftsById, setDraftsById] = useState<Record<number, ConsultationFormValues>>({});
  const [processedIds, setProcessedIds] = useState<Set<number>>(() => new Set());
  const [teacherFilter, setTeacherFilter] = useState('');
  const [teacherFilterOpen, setTeacherFilterOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'view' | 'edit'>('view');
  const [selectedRecord, setSelectedRecord] = useState<ConsultationRecord | null>(null);
  const [workbenchTab, setWorkbenchTab] = useState<'pending' | 'processed'>('pending');
  const [pendingStatusFilter, setPendingStatusFilter] = useState<'active' | 'ended'>('active');
  const [pendingEndedAgeFilter, setPendingEndedAgeFilter] = useState<'7' | '30' | 'over30'>('over30');
  const [processedStatusFilter, setProcessedStatusFilter] = useState<'active' | 'ended'>('active');
  const [processedEndedAgeFilter, setProcessedEndedAgeFilter] = useState<'7' | '30' | 'over30'>('over30');
  const teacherDirectory = buildConsultationTeacherDirectory(records);
  const hasUncommittedChanges = Object.keys(draftsById).length > 0;
  const meetingTodayIso = getTodayIsoDate();
  const prefersReducedMotion = useReducedMotion();
  const groupedMeetingTeachers = useMemo(() => {
    const teacherSubjects = new Map<string, Set<string>>();
    records.forEach((record) => {
      const teacherId = record.teacher_id || record.receiving_teacher;
      if (!teacherId) return;
      const subjects = teacherSubjects.get(teacherId) ?? new Set<string>();
      if (record.consultation_subject?.includes('物理')) subjects.add('物理');
      if (record.consultation_subject?.includes('数学')) subjects.add('数学');
      teacherSubjects.set(teacherId, subjects);
    });
    return {
      数学: consultationTeachers.filter((teacher) => !teacherSubjects.get(teacher.teacher_id)?.has('物理')),
      物理: consultationTeachers.filter((teacher) => teacherSubjects.get(teacher.teacher_id)?.has('物理')),
    };
  }, [consultationTeachers, records]);
  const selectedMeetingTeacherLabel = teacherFilter
    ? consultationTeachers.find((teacher) => teacher.teacher_id === teacherFilter)?.display_name || teacherFilter
    : '全部';

  const loadWorkbench = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [consultations, classItems, teacherItems] = await Promise.all([
        apiFetch<ConsultationRecord[]>('/api/consultations?q='),
        apiFetch<ClassItem[]>('/api/classes').catch(() => [] as ClassItem[]),
        apiFetch<ConsultationTeacherOption[]>('/api/consultation-teachers').catch(() => [] as ConsultationTeacherOption[]),
      ]);
      setRecords(consultations.map(normalizeConsultationRecord));
      setClasses(classItems);
      setConsultationTeachers(teacherItems.map(normalizeConsultationTeacherOption));
    } catch (err) {
      setError(err instanceof Error ? err.message : '面对面工作台加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWorkbench().catch(() => undefined);
  }, [loadWorkbench]);

  useEffect(() => {
    if (!hasUncommittedChanges) {
      return undefined;
    }
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '还有未最终保存的咨询修改，是否关闭？';
      return '还有未最终保存的咨询修改，是否关闭？';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUncommittedChanges]);

  const getDraftRecord = useCallback((record: ConsultationRecord): ConsultationRecord => {
    const draft = draftsById[record.id];
    return draft ? normalizeConsultationRecord({ ...record, ...draft }) : record;
  }, [draftsById]);

  const filteredRecords = useMemo(() => records
    .map(getDraftRecord)
    .filter((record) => {
      if (!teacherFilter) return true;
      return record.teacher_id === teacherFilter
        || record.receiving_teacher === teacherFilter
        || getConsultationTeacherName(record, teacherDirectory) === teacherFilter;
    }), [getDraftRecord, records, teacherDirectory, teacherFilter]);

  const isMeetingEndedRecord = (record: ConsultationRecord) => isConsultationEnded(record.flow_stage) || isConsultationResultStage(record.flow_stage);
  const getMeetingEndedAgeBucket = (record: ConsultationRecord): '7' | '30' | 'over30' => {
    const endedAt = (record.ended_at || '').trim();
    if (!endedAt) return 'over30';
    const endedDate = endedAt.slice(0, 10);
    const endedTime = Date.parse(`${endedDate}T12:00:00`);
    const todayTime = Date.parse(`${meetingTodayIso}T12:00:00`);
    if (!Number.isFinite(endedTime) || !Number.isFinite(todayTime)) return 'over30';
    const ageDays = Math.max(0, Math.floor((todayTime - endedTime) / 86_400_000));
    if (ageDays <= 7) return '7';
    if (ageDays <= 30) return '30';
    return 'over30';
  };

  const pendingRecords = filteredRecords.filter((record) => !processedIds.has(record.id));
  const processedRecords = filteredRecords.filter((record) => processedIds.has(record.id));
  const pendingEndedRecords = pendingRecords.filter(isMeetingEndedRecord);
  const pendingActiveRecords = pendingRecords.filter((record) => !isMeetingEndedRecord(record));
  const processedEndedRecords = processedRecords.filter(isMeetingEndedRecord);
  const processedActiveRecords = processedRecords.filter((record) => !isMeetingEndedRecord(record));
  const pendingVisibleRecords = pendingStatusFilter === 'active'
    ? pendingActiveRecords
    : pendingEndedRecords.filter((record) => getMeetingEndedAgeBucket(record) === pendingEndedAgeFilter);
  const processedVisibleRecords = processedStatusFilter === 'active'
    ? processedActiveRecords
    : processedEndedRecords.filter((record) => getMeetingEndedAgeBucket(record) === processedEndedAgeFilter);

  const buildMeetingFilterCounts = (activeRecords: ConsultationRecord[], endedRecords: ConsultationRecord[]) => ({
    active: activeRecords.length,
    ended: endedRecords.length,
    ended7: endedRecords.filter((record) => getMeetingEndedAgeBucket(record) === '7').length,
    ended30: endedRecords.filter((record) => getMeetingEndedAgeBucket(record) === '30').length,
    endedOver30: endedRecords.filter((record) => getMeetingEndedAgeBucket(record) === 'over30').length,
  });
  const pendingFilterCounts = buildMeetingFilterCounts(pendingActiveRecords, pendingEndedRecords);
  const processedFilterCounts = buildMeetingFilterCounts(processedActiveRecords, processedEndedRecords);

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
  };

  const handleLocalSubmit = async (values: ConsultationFormValues) => {
    if (!selectedRecord) {
      return;
    }
    const isTerminal = isConsultationEnded(values.flow_stage) || isConsultationResultStage(values.flow_stage);
    const nextValues = {
      ...values,
      ended_at: isTerminal ? values.ended_at || new Date().toISOString() : '',
    };
    setDraftsById((current) => ({ ...current, [selectedRecord.id]: nextValues }));
    setProcessedIds((current) => new Set(current).add(selectedRecord.id));
    closeModal();
  };

  const handleDirectProcess = (record: ConsultationRecord) => {
    setProcessedIds((current) => new Set(current).add(record.id));
  };

  const handleMeetingOverDoubleClick = (record: ConsultationRecord) => {
    const values = endConsultationValues(toConsultationFormValues(record));
    setDraftsById((current) => ({ ...current, [record.id]: { ...values, ended_at: values.ended_at || new Date().toISOString() } }));
    setProcessedIds((current) => new Set(current).add(record.id));
  };

  const handleFinalSave = async () => {
    setSaving(true);
    setError('');
    try {
      for (const [rawId, values] of Object.entries(draftsById)) {
        const id = Number(rawId);
        await apiFetch(`/api/consultations/${id}`, {
          method: 'PUT',
          body: JSON.stringify(values),
        });
      }
      setDraftsById({});
      setProcessedIds(new Set());
      await loadWorkbench();
      writeLocalStorageItem('xr_consultation_meeting_saved_at', String(Date.now()));
    } catch (err) {
      setError(err instanceof Error ? err.message : '最终保存失败，请重试');
    } finally {
      setSaving(false);
    }
  };

  const handleCloseWorkbench = () => {
    if (hasUncommittedChanges && !window.confirm('还有未最终保存的咨询修改，是否关闭？')) {
      return;
    }
    window.close();
  };

  const renderMeetingInfoCell = (label: string, value: string, className = '') => (
    <div className={`min-w-0 ${className}`} title={value}>
      <p className="truncate text-[11px] font-bold leading-4 text-[#7188A6]">{label}</p>
      <p className="mt-0.5 truncate whitespace-nowrap text-[13px] font-semibold leading-5 text-[#1F2A44] dark:text-white">{value || '—'}</p>
    </div>
  );

  const renderMeetingIconActions = (record: ConsultationRecord) => (
    <div className="flex shrink-0 items-center justify-end gap-1">
      <button type="button" onClick={() => openViewModal(record)} className="flex h-8 w-8 items-center justify-center rounded-full border border-[#D9EEF7] bg-white text-[#1F2A44] transition hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300" aria-label="查看咨询">
        <Eye size={13} />
      </button>
      <button type="button" onClick={() => openEditModal(record)} className="flex h-8 w-8 items-center justify-center rounded-full border border-[#D9EEF7] bg-sky-50 text-[#0EA5E9] transition hover:bg-sky-100 dark:border-white/10 dark:bg-sky-400/10 dark:text-sky-200" aria-label="编辑咨询">
        <Pencil size={13} />
      </button>
      <button type="button" onClick={() => handleDirectProcess(record)} className="flex h-9 w-9 items-center justify-center rounded-full border border-emerald-100 bg-emerald-50 text-[#22B981] transition hover:bg-emerald-100 dark:border-white/10 dark:bg-emerald-400/10 dark:text-emerald-200" title="直接进入已处理" aria-label="直接进入已处理">
        <CheckCircle2 size={15} />
      </button>
    </div>
  );

  const renderMeetingTimeRow = (record: ConsultationRecord, boxed = false) => (
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

  const renderMeetingDetail = (record: ConsultationRecord, mobile = false) => {
    const needDetail = record.need_detail?.trim();
    const followUpNote = record.follow_up_note?.trim();
    if (!needDetail && !followUpNote) return null;
    return (
      <div className={`min-w-0 ${mobile ? 'space-y-1.5 border-y border-[#EEF7FC] py-2.5 dark:border-white/10' : 'space-y-1 border-t border-[#EEF7FC] pt-2 dark:border-white/10'}`}>
        {needDetail && <ConsultationCardExpandableText label="咨询详情" text={needDetail} lines={mobile ? 2 : 1} />}
        {followUpNote && <ConsultationCardExpandableText label="跟进" text={followUpNote} />}
      </div>
    );
  };

  const renderMeetingFlowStrip = (record: ConsultationRecord) => (
    <ConsultationFlowBar
      mode="list"
      stage={record.flow_stage}
      completedStages={record.completed_stages}
      editable={false}
      showOver
      overDisabled={false}
      onOverDoubleClick={() => handleMeetingOverDoubleClick(record)}
    />
  );

  const getMeetingRecordResultPill = (record: ConsultationRecord) => {
    if (record.flow_stage === '成功进班') {
      return { label: '☀️ 成功进班', className: 'bg-sky-500 text-white shadow-[0_8px_18px_rgba(14,165,233,0.22)]' };
    }
    if (record.flow_stage === '试听失败') {
      return { label: '😢 试听未成', className: 'bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-300' };
    }
    if (record.flow_stage === '咨询结束') {
      return { label: 'OVER', className: 'bg-rose-500 text-white shadow-[0_8px_18px_rgba(244,63,94,0.22)]' };
    }
    return { label: '未选择结果', className: 'bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-300' };
  };

  const renderMeetingDesktopCard = (record: ConsultationRecord) => (
    <article className="overflow-hidden rounded-[14px] border border-[#D9EEF7] bg-white shadow-[0_6px_18px_rgba(31,42,68,0.04)] dark:border-white/10 dark:bg-slate-950/70">
      <div className="grid grid-cols-[96px_88px_112px_minmax(120px,160px)_120px_132px_96px] items-center border-b border-[#EEF7FC] px-4 py-3 text-sm dark:border-white/10">
        {renderMeetingInfoCell('日期', record.date || '—')}
        {renderMeetingInfoCell('咨询老师', getConsultationTeacherName(record, teacherDirectory), 'border-l border-[#D9EEF7] pl-3 dark:border-white/10')}
        {renderMeetingInfoCell('科目 / 年级', `${record.consultation_subject || '未填写'} / ${record.grade || '—'}`, 'border-l border-[#D9EEF7] pl-3 dark:border-white/10')}
        {renderMeetingInfoCell('家长微信', record.parent_wechat_name || '—', 'border-l border-[#D9EEF7] pl-3 dark:border-white/10')}
        {renderMeetingInfoCell('学生姓名', record.child_name?.trim() || '待补充', 'border-l border-[#D9EEF7] pl-3 dark:border-white/10')}
        {renderMeetingInfoCell('来源', getConsultationSourceLabel(record), 'border-l border-[#D9EEF7] pl-3 dark:border-white/10')}
        <div className="border-l border-[#D9EEF7] pl-3 dark:border-white/10">{renderMeetingIconActions(record)}</div>
      </div>
      <div className="space-y-2 px-4 py-2.5">
        {renderMeetingDetail(record)}
        {renderMeetingTimeRow(record)}
      </div>
      <div className="grid grid-cols-[0.875rem_minmax(0,1fr)] items-center gap-2.5 border-t border-[#EEF7FC] bg-[#F9FDFF] px-4 py-3 dark:border-white/10 dark:bg-white/[0.03]">
        <ConsultationStatusLamp stage={record.flow_stage} />
        {renderMeetingFlowStrip(record)}
      </div>
    </article>
  );

  const renderMeetingPadCard = (record: ConsultationRecord) => (
    <article className="overflow-hidden rounded-[14px] border border-[#D9EEF7] bg-white shadow-[0_6px_18px_rgba(31,42,68,0.04)] dark:border-white/10 dark:bg-slate-950/70">
      <div className="grid grid-cols-[0.82fr_1fr_1fr_5.8rem] items-center border-b border-[#EEF7FC] px-4 py-3 text-sm dark:border-white/10">
        {renderMeetingInfoCell('日期', record.date || '—')}
        {renderMeetingInfoCell('咨询老师', getConsultationTeacherName(record, teacherDirectory), 'border-l border-sky-100/80 pl-3 dark:border-white/10')}
        {renderMeetingInfoCell('科目 / 年级', `${record.consultation_subject || '未填写'} / ${record.grade || '—'}`, 'border-l border-sky-100/80 pl-3 dark:border-white/10')}
        <div className="border-l border-sky-100/80 pl-3 dark:border-white/10">{renderMeetingIconActions(record)}</div>
      </div>
      <div className="grid grid-cols-[repeat(3,minmax(0,1fr))] border-b border-[#EEF7FC] px-4 py-2.5 text-sm dark:border-white/10">
        {renderMeetingInfoCell('家长微信', record.parent_wechat_name || '—')}
        {renderMeetingInfoCell('学生姓名', record.child_name?.trim() || '待补充', 'border-l border-sky-100/80 pl-3 dark:border-white/10')}
        {renderMeetingInfoCell('来源', getConsultationSourceLabel(record), 'border-l border-sky-100/80 pl-3 dark:border-white/10')}
      </div>
      <div className="space-y-2 px-4 py-2.5">
        {renderMeetingDetail(record)}
        {renderMeetingTimeRow(record)}
      </div>
      <div className="grid grid-cols-[0.875rem_minmax(0,1fr)] items-center gap-2 border-t border-[#EEF7FC] bg-[#F9FDFF] px-4 py-3 dark:border-white/10 dark:bg-white/[0.03]">
        <ConsultationStatusLamp stage={record.flow_stage} />
        {renderMeetingFlowStrip(record)}
      </div>
    </article>
  );

  const renderMeetingMobileCard = (record: ConsultationRecord) => {
    const resultPill = getMeetingRecordResultPill(record);
    return (
      <article className="relative space-y-3 rounded-[14px] border border-[#D9EEF7] bg-white p-3.5 shadow-[0_6px_18px_rgba(31,42,68,0.04)] dark:border-white/10 dark:bg-slate-950/70">
        <div className="flex items-center justify-between gap-2 border-b border-sky-50 pb-2.5 dark:border-white/10">
          <p className="whitespace-nowrap font-mono text-sm font-semibold text-slate-900 dark:text-white">{record.date || '—'}</p>
          <div className="flex min-w-0 items-center gap-2">
            {record.flow_stage !== '咨询结束' && (
              <div className={`relative inline-flex h-7 min-w-0 max-w-[7.5rem] items-center overflow-hidden rounded-lg px-2.5 text-[11px] font-extrabold ${resultPill.className}`}>
                <span className="min-w-0 flex-1 truncate text-center">{resultPill.label}</span>
              </div>
            )}
            {renderMeetingIconActions(record)}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-3">
          {renderMeetingInfoCell('咨询老师', getConsultationTeacherName(record, teacherDirectory))}
          {renderMeetingInfoCell('科目 / 年级', `${record.consultation_subject || '未填写'} / ${record.grade || '—'}`)}
          {renderMeetingInfoCell('家长微信', record.parent_wechat_name || '—')}
          {renderMeetingInfoCell('学生姓名', record.child_name?.trim() || '待补充')}
          {renderMeetingInfoCell('来源', getConsultationSourceLabel(record), 'col-span-2')}
        </div>
        {renderMeetingDetail(record, true)}
        {renderMeetingTimeRow(record, true)}
        <div className="grid grid-cols-[1rem_minmax(0,1fr)] items-center gap-2">
          <ConsultationStatusLamp stage={record.flow_stage} />
          <div className="min-w-0 overflow-visible">{renderMeetingFlowStrip(record)}</div>
        </div>
      </article>
    );
  };

  const renderMeetingRecordCard = (record: ConsultationRecord) => (
    <motion.div
      key={record.id}
      layout
      initial={{ opacity: 0, scale: prefersReducedMotion ? 1 : 0.98, y: prefersReducedMotion ? 0 : 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: prefersReducedMotion ? 1 : 0.96, y: prefersReducedMotion ? 0 : 10 }}
      transition={{ duration: prefersReducedMotion ? 0 : 0.18, ease: 'easeOut' }}
    >
      <div className="block md:hidden">{renderMeetingMobileCard(record)}</div>
      <div className="hidden md:block xl:hidden">{renderMeetingPadCard(record)}</div>
      <div className="hidden xl:block">{renderMeetingDesktopCard(record)}</div>
    </motion.div>
  );

  const renderMeetingSecondaryFilters = (
    statusValue: 'active' | 'ended',
    setStatusValue: (value: 'active' | 'ended') => void,
    ageValue: '7' | '30' | 'over30',
    setAgeValue: (value: '7' | '30' | 'over30') => void,
    counts: { active: number; ended: number; ended7: number; ended30: number; endedOver30: number },
  ) => (
    <div className="mb-4 flex flex-col gap-2 rounded-2xl border border-[#D9EEF7] bg-[#F9FDFF] px-3 py-3 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="flex flex-wrap items-center gap-2">
        {[
          { key: 'active' as const, label: '待咨询', count: counts.active },
          { key: 'ended' as const, label: '已结束', count: counts.ended },
        ].map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setStatusValue(item.key)}
            className={cn(
              'h-8 rounded-full border px-3 text-xs font-bold transition',
              statusValue === item.key
                ? 'border-sky-200 bg-sky-500 text-white shadow-[0_8px_18px_rgba(14,165,233,0.16)]'
                : 'border-sky-100 bg-white text-slate-600 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300',
            )}
          >
            {item.label}
            <span className={cn('ml-1 rounded-full px-1.5 py-0.5 text-[10px]', statusValue === item.key ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-300')}>
              {item.count}
            </span>
          </button>
        ))}
      </div>
      {statusValue === 'ended' && (
        <div className="flex flex-wrap items-center gap-2 pl-0 sm:pl-2">
          {[
            { key: '7' as const, label: '一周内', count: counts.ended7 },
            { key: '30' as const, label: '一月内', count: counts.ended30 },
            { key: 'over30' as const, label: '30天+', count: counts.endedOver30 },
          ].map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setAgeValue(item.key)}
              className={cn(
                'h-7 rounded-full border px-2.5 text-[11px] font-bold transition',
                ageValue === item.key
                  ? 'border-emerald-200 bg-emerald-500 text-white shadow-[0_8px_18px_rgba(34,197,94,0.16)]'
                  : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300',
              )}
            >
              {item.label}
              <span className={cn('ml-1 rounded-full px-1 py-0.5 text-[10px]', ageValue === item.key ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-300')}>
                {item.count}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );

  const renderWorkbenchEmptyState = (title: string, description: string, primaryLabel: string, onPrimary: () => void) => (
    <div className="col-span-full flex min-h-[18rem] flex-col items-center justify-center rounded-[16px] border border-dashed border-[#D9EEF7] bg-[#F9FDFF] px-6 py-10 text-center dark:border-white/10 dark:bg-white/[0.03]">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-50 text-[#0EA5E9] dark:bg-sky-400/10 dark:text-sky-200">
        <MessageSquare size={28} />
      </div>
      <h4 className="mt-4 text-lg font-extrabold text-[#1F2A44] dark:text-white">{title}</h4>
      <p className="mt-2 max-w-md text-sm leading-6 text-[#7188A6] dark:text-slate-400">{description}</p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        <button type="button" onClick={onPrimary} className={`${workspaceSecondaryButtonClass} h-10 px-4 py-2 text-sm`}>
          {primaryLabel}
        </button>
        {teacherFilter && (
          <button type="button" onClick={() => setTeacherFilter('')} className={`${workspaceSecondaryButtonClass} h-10 px-4 py-2 text-sm`}>
            清空筛选
          </button>
        )}
      </div>
    </div>
  );

  if (!hasOwnerAccess(currentUser.role)) {
    return (
      <div className={`${workspacePageClass} min-h-[100svh]`}>
        <div className={`${workspaceCardClass} p-8 text-center text-slate-500 dark:text-slate-400`}>当前账号没有面对面沟通模式权限。</div>
      </div>
    );
  }

  return (
    <div className={`${workspacePageClass} min-h-[100svh] space-y-5 bg-[#F5FAFD] dark:bg-slate-950`}>
      <div className={`sticky top-0 z-20 -mx-3 flex flex-col gap-4 rounded-[18px] ${consultationSurfaceClass} px-3 py-3 sm:mx-0 sm:px-4 lg:grid lg:grid-cols-[minmax(18rem,1fr)_minmax(28rem,36rem)] lg:items-center`}>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.24em] text-[#0EA5E9]">Consultation Meeting · {consultationMeetingVersion}</p>
          <h3 className="mt-1 text-xl font-extrabold tracking-tight text-[#1F2A44] dark:text-white">面对面沟通工作台</h3>
          <p className="mt-1 text-sm text-[#7188A6] dark:text-slate-400">本页保存先进入已处理，最终保存后同步主咨询页。</p>
        </div>
        <div className="grid gap-2 sm:grid-cols-3 lg:w-[32rem]">
          <div className="relative sm:col-span-1">
            <button
              type="button"
              onClick={() => setTeacherFilterOpen((current) => !current)}
              className={`${consultationInputClass} flex h-10 w-full items-center justify-between gap-2 px-3 text-left text-sm`}
            >
              <span className="min-w-0 truncate">按教师查看：{selectedMeetingTeacherLabel}</span>
              <ChevronDown size={14} className={cn('shrink-0 transition', teacherFilterOpen && 'rotate-180')} />
            </button>
            <AnimatePresence>
              {teacherFilterOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -4, scale: 0.98 }}
                  transition={{ duration: 0.14 }}
                  className="absolute right-0 top-12 z-30 w-[min(22rem,calc(100vw-2rem))] rounded-2xl border border-[#D9EEF7] bg-white p-3 shadow-[0_18px_42px_rgba(31,42,68,0.14)] dark:border-white/10 dark:bg-slate-950"
                >
                  <button
                    type="button"
                    onClick={() => {
                      setTeacherFilter('');
                      setTeacherFilterOpen(false);
                    }}
                    className={cn(
                      'mb-2 flex h-8 w-full items-center justify-between rounded-xl px-3 text-sm font-bold transition',
                      !teacherFilter ? 'bg-sky-500 text-white' : 'bg-sky-50 text-slate-600 hover:bg-sky-100 dark:bg-white/5 dark:text-slate-300',
                    )}
                  >
                    全部教师
                    <span className="text-xs">{consultationTeachers.length}</span>
                  </button>
                  {(['数学', '物理'] as const).map((subject) => (
                    <div key={subject} className="mt-2">
                      <p className="px-1 text-[11px] font-extrabold text-slate-400">{subject}</p>
                      <div className="mt-1 grid grid-cols-2 gap-1.5">
                        {groupedMeetingTeachers[subject].length ? groupedMeetingTeachers[subject].map((teacher) => (
                          <button
                            key={`${subject}-${teacher.teacher_id}`}
                            type="button"
                            onClick={() => {
                              setTeacherFilter(teacher.teacher_id);
                              setTeacherFilterOpen(false);
                            }}
                            className={cn(
                              'min-w-0 rounded-xl border px-2.5 py-2 text-left text-xs font-bold transition',
                              teacherFilter === teacher.teacher_id
                                ? 'border-sky-200 bg-sky-500 text-white'
                                : 'border-sky-100 bg-white text-slate-600 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300',
                            )}
                          >
                            <span className="block truncate">{teacher.display_name}</span>
                          </button>
                        )) : (
                          <p className="col-span-2 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-400 dark:bg-white/5">暂无教师</p>
                        )}
                      </div>
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          <button type="button" onClick={handleFinalSave} disabled={!hasUncommittedChanges || saving} className={`${workspacePrimaryButtonClass} h-10 px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50`}>
            <CheckCircle2 size={15} />
            最终保存
          </button>
          <button type="button" onClick={handleCloseWorkbench} className={`${workspaceSecondaryButtonClass} h-10 px-4 py-2 text-sm`}>
            <X size={15} />
            关闭
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {loading ? (
        <div className={`${workspaceCardClass} p-8 text-center text-slate-500 dark:text-slate-400`}>正在加载面对面沟通工作台...</div>
      ) : (
        <section className={`rounded-[18px] ${consultationSurfaceClass} p-3 sm:p-4`}>
          <div className="mb-4 grid grid-cols-2 gap-2 rounded-xl bg-[#EAF6FC] p-1 dark:bg-white/5">
            <button
              type="button"
              onClick={() => setWorkbenchTab('pending')}
              className={`flex h-10 items-center justify-center gap-2 rounded-xl text-sm font-extrabold transition ${
                workbenchTab === 'pending'
                  ? 'bg-white text-[#0EA5E9] shadow-sm dark:bg-sky-400/15 dark:text-sky-100'
                  : 'text-[#7188A6] hover:text-[#1F2A44] dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              待处理
              <span className="rounded-full bg-sky-50 px-2 py-0.5 text-xs font-bold text-sky-600 dark:bg-sky-400/10 dark:text-sky-200">{pendingRecords.length}</span>
            </button>
            <button
              type="button"
              onClick={() => setWorkbenchTab('processed')}
              className={`flex h-10 items-center justify-center gap-2 rounded-xl text-sm font-extrabold transition ${
                workbenchTab === 'processed'
                  ? 'bg-white text-[#22B981] shadow-sm dark:bg-emerald-400/15 dark:text-emerald-100'
                  : 'text-[#7188A6] hover:text-[#1F2A44] dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              已处理
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-600 dark:bg-emerald-400/10 dark:text-emerald-200">{processedRecords.length}</span>
            </button>
          </div>

          {workbenchTab === 'pending' ? (
            <div>
              {renderMeetingSecondaryFilters(
                pendingStatusFilter,
                setPendingStatusFilter,
                pendingEndedAgeFilter,
                setPendingEndedAgeFilter,
                pendingFilterCounts,
              )}
              <div className="grid gap-3">
                {pendingVisibleRecords.length ? (
                  <AnimatePresence initial={false}>
                    {pendingVisibleRecords.map(renderMeetingRecordCard)}
                  </AnimatePresence>
                ) : renderWorkbenchEmptyState('当前筛选下暂无待处理记录', '可以切到已处理查看刚核对过的咨询，或调整负责教师筛选。', '查看已处理', () => setWorkbenchTab('processed'))}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {renderMeetingSecondaryFilters(
                processedStatusFilter,
                setProcessedStatusFilter,
                processedEndedAgeFilter,
                setProcessedEndedAgeFilter,
                processedFilterCounts,
              )}
              <div className="grid gap-3">
                {processedVisibleRecords.length ? (
                  <AnimatePresence initial={false}>
                    {processedVisibleRecords.map(renderMeetingRecordCard)}
                  </AnimatePresence>
                ) : renderWorkbenchEmptyState(
                  processedStatusFilter === 'active' ? '当前筛选下暂无待咨询' : '当前筛选下暂无已结束记录',
                  processedStatusFilter === 'active' ? '可以查看待处理队列继续核对，或切换到已结束查看完成记录。' : '咨询成功、咨询失败或中途结束的记录会在这里集中查看。',
                  '查看待处理',
                  () => setWorkbenchTab('pending'),
                )}
              </div>
            </div>
          )}
        </section>
      )}

      <AnimatePresence>
        {modalOpen && selectedRecord && (
          <ConsultationModal
            open={modalOpen}
            mode={modalMode}
            record={getDraftRecord(selectedRecord)}
            consultationTeachers={consultationTeachers}
            classes={classes}
            submitting={false}
            error={error}
            currentUser={currentUser}
            onClose={closeModal}
            onSubmit={handleLocalSubmit}
            onRequestEdit={selectedRecord ? () => setModalMode('edit') : undefined}
          />
        )}
      </AnimatePresence>
    </div>
  );
};


// --- Login Modal ---

type RecoveryMethod = 'phone' | 'security';

const authInputClass = 'w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors';

function buildRecoveryPayload(
  recoveryMethod: RecoveryMethod,
  recoveryPhone: string,
  securityQuestion: string,
  securityAnswer: string,
) {
  if (recoveryMethod === 'phone') {
    return { recovery_phone: recoveryPhone };
  }
  return { security_question: securityQuestion, security_answer: securityAnswer };
}

const RecoverySetupFields = ({
  recoveryMethod,
  setRecoveryMethod,
  recoveryPhone,
  setRecoveryPhone,
  securityQuestion,
  setSecurityQuestion,
  securityAnswer,
  setSecurityAnswer,
}: {
  recoveryMethod: RecoveryMethod;
  setRecoveryMethod: (method: RecoveryMethod) => void;
  recoveryPhone: string;
  setRecoveryPhone: (value: string) => void;
  securityQuestion: string;
  setSecurityQuestion: (value: string) => void;
  securityAnswer: string;
  setSecurityAnswer: (value: string) => void;
}) => (
  <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
    <div className="grid grid-cols-2 gap-2 rounded-xl bg-black p-1">
      <button
        type="button"
        onClick={() => setRecoveryMethod('phone')}
        className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
          recoveryMethod === 'phone' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
        }`}
      >
        电话号码
      </button>
      <button
        type="button"
        onClick={() => setRecoveryMethod('security')}
        className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
          recoveryMethod === 'security' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
        }`}
      >
        密保问题
      </button>
    </div>

    {recoveryMethod === 'phone' ? (
      <div className="space-y-1.5">
        <label className="text-sm text-gray-400">找回密码电话</label>
        <input
          type="tel"
          value={recoveryPhone}
          onChange={(e) => setRecoveryPhone(e.target.value)}
          required
          placeholder="输入电话号码即可验证"
          className={authInputClass}
        />
      </div>
    ) : (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="space-y-1.5">
          <label className="text-sm text-gray-400">密保问题</label>
          <input
            type="text"
            value={securityQuestion}
            onChange={(e) => setSecurityQuestion(e.target.value)}
            required
            placeholder="例如：我的入职年份？"
            className={authInputClass}
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-sm text-gray-400">密保答案</label>
          <input
            type="text"
            value={securityAnswer}
            onChange={(e) => setSecurityAnswer(e.target.value)}
            required
            placeholder="请输入答案"
            className={authInputClass}
          />
        </div>
      </div>
    )}
  </div>
);

const ClassClaimPage = ({
  currentUser,
  onClaimed,
  onLogout,
}: {
  currentUser: CurrentUser;
  onClaimed: (user: CurrentUser) => void;
  onLogout: () => void;
}) => {
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [selectedClassIds, setSelectedClassIds] = useState<number[]>([]);
  const [selectedGradeFilter, setSelectedGradeFilter] = useState<string>('全部');
  const [selectedStageFilter, setSelectedStageFilter] = useState<string>('全部学段');
  const [selectedSubjectFilter, setSelectedSubjectFilter] = useState<string>('全部学科');
  const [activeClaimFilterLayer, setActiveClaimFilterLayer] = useState<'subject' | 'stage' | 'grade'>('subject');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiFetch<{ items: ClassItem[] }>('/api/me/unbound-classes')
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setClasses(payload.items);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '班级加载失败');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleClass = (classId: number) => {
    setSelectedClassIds((current) =>
      current.includes(classId) ? current.filter((id) => id !== classId) : [...current, classId],
    );
  };

  const claimGradeFilterOptions = ['全部', ...studentCenterGradeOptions.filter((grade) => {
    if (selectedStageFilter !== '全部学段' && !studentCenterGradeGroups[selectedStageFilter]?.includes(grade)) {
      return false;
    }
    return classes.some((item) => normalizeAcademicGradeLabel(item.current_grade || item.grade || '') === grade);
  })];
  const claimSubjectFilterOptions = academicSubjectFilterOptions;
  const claimFilterSummary = [
    selectedSubjectFilter !== '全部学科' ? selectedSubjectFilter : '',
    selectedStageFilter !== '全部学段' ? selectedStageFilter : '',
    selectedGradeFilter !== '全部' ? selectedGradeFilter : '',
  ].filter(Boolean).join(' / ') || '全部';
  const filteredClasses = classes.filter((item) => {
    if (selectedSubjectFilter !== '全部学科' && item.subject !== selectedSubjectFilter) {
      return false;
    }
    if (selectedStageFilter !== '全部学段' && (item.stage || getAcademicStageFromGrade(item.current_grade || item.grade || '')) !== selectedStageFilter) {
      return false;
    }
    if (selectedGradeFilter === '全部') {
      return true;
    }
    return normalizeAcademicGradeLabel(item.current_grade || item.grade || '') === selectedGradeFilter;
  }).sort((left, right) => {
    const gradeDelta = getAcademicGradeRank(left.current_grade || left.grade || '') - getAcademicGradeRank(right.current_grade || right.grade || '');
    return gradeDelta || `${left.subject}${left.name}`.localeCompare(`${right.subject}${right.name}`, 'zh-CN') || left.id - right.id;
  });

  const handleClaim = async () => {
    setError('');
    if (classes.length > 0 && selectedClassIds.length === 0) {
      setError('请选择需要绑定的班级');
      return;
    }
    setSaving(true);
    try {
      const payload = await apiFetch<{ ok: boolean; user: CurrentUser }>('/api/me/claim-classes', {
        method: 'POST',
        body: JSON.stringify({ class_ids: selectedClassIds }),
      });
      onClaimed(payload.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : '班级认领失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="relative flex min-h-[100svh] items-center justify-center overflow-hidden bg-[linear-gradient(180deg,#f8fbff_0%,#eef6ff_100%)] px-4 py-8 text-slate-900 dark:bg-[linear-gradient(180deg,#020617_0%,#0f172a_100%)] dark:text-slate-100">
      <div className={`${workspaceCardClass} relative w-full max-w-3xl p-6 md:p-8`}>
        <div className="flex flex-col gap-3 border-b border-sky-100 pb-5 dark:border-white/10">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-medium text-sky-600 dark:text-sky-300">首次登录</p>
              <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">认领你的班级</h1>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                {currentUser.display_name}，请选择需要绑定到你账号下的未绑定班级。
              </p>
            </div>
            <button type="button" onClick={onLogout} className={workspaceSecondaryButtonClass}>
              退出登录
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-5 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {!loading && classes.length > 0 ? (
          <div className="mt-5 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-slate-500 dark:text-slate-400">筛选：{claimFilterSummary}</span>
              {[
                { key: 'subject' as const, label: selectedSubjectFilter },
                { key: 'stage' as const, label: selectedStageFilter },
                { key: 'grade' as const, label: selectedGradeFilter === '全部' ? '全部年级' : selectedGradeFilter },
              ].map((item) => (
                <button key={item.key} type="button" onClick={() => setActiveClaimFilterLayer(item.key)} className={cn('rounded-full border px-3 py-2 text-sm font-semibold transition', activeClaimFilterLayer === item.key ? 'border-sky-500 bg-sky-500 text-white' : 'border-sky-100 bg-white text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300')}>{item.label}</button>
              ))}
            </div>
            <div className="rounded-2xl border border-sky-100 bg-sky-50/60 p-3 dark:border-white/10 dark:bg-white/5">
              {activeClaimFilterLayer === 'subject' && (
                <div className="flex flex-wrap gap-2">
                  {claimSubjectFilterOptions.map((option) => (
                    <button key={option} type="button" onClick={() => {
                      setSelectedSubjectFilter(option);
                      setSelectedStageFilter('全部学段');
                      setSelectedGradeFilter('全部');
                    }} className={cn('rounded-full border px-3 py-2 text-sm font-semibold', selectedSubjectFilter === option ? 'border-sky-500 bg-sky-500 text-white' : 'border-sky-100 bg-white text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300')}>{option}</button>
                  ))}
                </div>
              )}
              {activeClaimFilterLayer === 'stage' && (
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => {
                    setSelectedStageFilter('全部学段');
                    setSelectedGradeFilter('全部');
                  }} className={cn('rounded-full border px-3 py-2 text-sm font-semibold', selectedStageFilter === '全部学段' ? 'border-sky-500 bg-sky-500 text-white' : 'border-sky-100 bg-white text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300')}>全部学段</button>
                  {studentCenterStageOptions.map((stage) => (
                    <button key={stage} type="button" onClick={() => {
                      setSelectedStageFilter(stage);
                      setSelectedGradeFilter('全部');
                    }} className={cn('rounded-full border px-3 py-2 text-sm font-semibold', selectedStageFilter === stage ? 'border-sky-500 bg-sky-500 text-white' : 'border-sky-100 bg-white text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300')}>{stage}</button>
                  ))}
                </div>
              )}
              {activeClaimFilterLayer === 'grade' && (
                <div className="flex flex-wrap gap-2">
                  {claimGradeFilterOptions.map((option) => (
                    <button key={option} type="button" onClick={() => setSelectedGradeFilter(option)} className={cn('rounded-full border px-3 py-2 text-sm font-semibold', selectedGradeFilter === option ? 'border-sky-500 bg-sky-500 text-white' : 'border-sky-100 bg-white text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300')}>{option === '全部' ? '全部年级' : option}</button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}

        <div className="mt-5 space-y-3">
          {loading ? (
            <WorkspaceLoading label="正在加载未绑定班级..." />
          ) : classes.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
              当前没有未绑定班级。
            </div>
          ) : filteredClasses.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
              {`当前筛选“${claimFilterSummary}”下暂无未绑定班级。`}
            </div>
          ) : (
            filteredClasses.map((item) => {
              const checked = selectedClassIds.includes(item.id);
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => toggleClass(item.id)}
                  className={`flex w-full items-center justify-between gap-4 rounded-2xl border px-4 py-4 text-left transition ${
                    checked
                      ? 'border-sky-300 bg-sky-50 text-slate-900 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-white'
                      : 'border-sky-100 bg-white/70 text-slate-700 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10'
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">{getCurrentClassDisplayName(item)}</span>
                    <span className="mt-1 block text-sm text-slate-500 dark:text-slate-400">
                      {[item.grade, item.subject].filter(Boolean).join(' · ') || '未设置年级科目'}
                    </span>
                  </span>
                  <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
                    checked ? 'border-sky-500 bg-sky-500 text-white' : 'border-slate-300 dark:border-slate-600'
                  }`}>
                    {checked ? <CheckCircle2 size={14} /> : null}
                  </span>
                </button>
              );
            })
          )}
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={() => void handleClaim()}
            disabled={loading || saving}
            className={workspacePrimaryButtonClass}
          >
            {saving ? '绑定中...' : classes.length === 0 ? '完成' : '绑定所选班级'}
          </button>
        </div>
      </div>
    </div>
  );
};

const LoginModal = ({
  onLogin,
  onClose,
  onOpenApplyOrganization,
  onOpenJoinOrganization,
  onOpenPasswordReset,
}: {
  onLogin: (token: string) => void;
  onClose: () => void;
  onOpenApplyOrganization: () => void;
  onOpenJoinOrganization: () => void;
  onOpenPasswordReset: () => void;
}) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const raw = await res.text();
      const data = raw ? JSON.parse(raw) as { error?: string; token?: string } : {};
      if (!res.ok) {
        throw new Error(data.error || '登录服务不可用，请确认后端已启动');
      }
      if (!data.token) {
        throw new Error('登录响应缺少令牌，请稍后再试');
      }
      onLogin(data.token);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.2 }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="bg-[#0a0a0a] border border-white/10 rounded-3xl p-8 shadow-2xl text-white">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold">登录账号</h2>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-white transition-colors text-2xl leading-none"
            >
              ×
            </button>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 mb-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm text-gray-400">账号</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                placeholder="请输入账号"
                className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between gap-3">
                <label className="text-sm text-gray-400">密码</label>
                <button
                  type="button"
                  onClick={onOpenPasswordReset}
                  className="text-sm font-medium text-sky-300 transition-colors hover:text-sky-100"
                >
                  找回密码
                </button>
              </div>
              <div className="relative">
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="请输入密码"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 pr-11 focus:outline-none focus:border-blue-500 transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(!showPwd)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                >
                  {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white py-3 rounded-xl font-semibold transition-all shadow-lg shadow-blue-600/20 mt-2"
            >
              {loading ? '登录中...' : '登录'}
            </button>
          </form>

          <div className="mt-4 space-y-3">
            <button
              type="button"
              onClick={onOpenApplyOrganization}
              className="w-full py-3 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-sm font-medium transition-colors"
            >
              申请开通机构
            </button>
            <button
              type="button"
              onClick={onOpenJoinOrganization}
              className="w-full py-3 rounded-xl border border-sky-500/30 bg-sky-500/10 hover:bg-sky-500/20 text-sm font-medium text-sky-100 transition-colors"
            >
              加入已有机构
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};

const RegisterRequestModal = ({ onClose }: { onClose: () => void }) => <OrganizationApplyModal onClose={onClose} />;

const PasswordResetModal = ({
  onClose,
  onBackToLogin,
}: {
  onClose: () => void;
  onBackToLogin: () => void;
}) => {
  const [username, setUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [recoveryMethod, setRecoveryMethod] = useState<RecoveryMethod>('phone');
  const [recoveryPhone, setRecoveryPhone] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (newPassword !== confirmPassword) {
      setError('两次输入的新密码不一致');
      return;
    }
    setLoading(true);
    try {
      await apiFetch<{ ok: boolean }>('/api/password-reset', {
        method: 'POST',
        body: JSON.stringify({
          username,
          new_password: newPassword,
          ...buildRecoveryPayload(recoveryMethod, recoveryPhone, securityQuestion, securityAnswer),
        }),
      });
      setSuccess('密码已重置，请使用新密码登录。');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '密码重置失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.2 }}
        className="relative z-10 w-full max-w-lg"
      >
        <div className="bg-[#0a0a0a] border border-white/10 rounded-3xl p-8 shadow-2xl text-white">
          <div className="mb-6 flex items-center justify-between">
            <h2 className="text-xl font-semibold">找回密码</h2>
            <button onClick={onClose} className="text-2xl leading-none text-gray-500 transition-colors hover:text-white">×</button>
          </div>

          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400">
              <AlertCircle size={16} />
              {error}
            </div>
          )}
          {success && (
            <div className="mb-4 flex items-center gap-2 rounded-xl border border-green-500/20 bg-green-500/10 p-3 text-sm text-green-300">
              <CheckCircle2 size={16} />
              {success}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm text-gray-400">账号</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                placeholder="请输入账号"
                className={authInputClass}
              />
            </div>

            <RecoverySetupFields
              recoveryMethod={recoveryMethod}
              setRecoveryMethod={setRecoveryMethod}
              recoveryPhone={recoveryPhone}
              setRecoveryPhone={setRecoveryPhone}
              securityQuestion={securityQuestion}
              setSecurityQuestion={setSecurityQuestion}
              securityAnswer={securityAnswer}
              setSecurityAnswer={setSecurityAnswer}
            />

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">新密码</label>
                <div className="relative">
                  <input
                    type={showPwd ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    minLength={6}
                    placeholder="至少 6 位"
                    className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 pr-11 focus:outline-none focus:border-blue-500 transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd(!showPwd)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                  >
                    {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">确认新密码</label>
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={6}
                  placeholder="再次输入新密码"
                  className={authInputClass}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-blue-600 py-3 font-semibold text-white shadow-lg shadow-blue-600/20 transition-all hover:bg-blue-500 disabled:opacity-50"
            >
              {loading ? '重置中...' : '重置密码'}
            </button>
            <button
              type="button"
              onClick={onBackToLogin}
              className="w-full rounded-xl border border-white/10 bg-white/5 py-3 text-sm font-medium transition-colors hover:bg-white/10"
            >
              返回登录
            </button>
          </form>
        </div>
      </motion.div>
    </motion.div>
  );
};

const LegacyRegisterRequestModal = ({ onClose }: { onClose: () => void }) => {
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [recoveryMethod, setRecoveryMethod] = useState<RecoveryMethod>('phone');
  const [recoveryPhone, setRecoveryPhone] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch('/api/organization-requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          organization_name: displayName || username,
          username,
          display_name: displayName,
          password,
          ...buildRecoveryPayload(recoveryMethod, recoveryPhone, securityQuestion, securityAnswer),
        }),
      });
      const raw = await res.text();
      const data = raw ? JSON.parse(raw) as { error?: string } : {};
      if (!res.ok) {
        throw new Error(data.error || '注册申请提交失败');
      }
      setSuccess('申请已提交，等待审核通过后即可登录后台。');
      setUsername('');
      setDisplayName('');
      setPassword('');
      setConfirmPassword('');
      setRecoveryPhone('');
      setSecurityQuestion('');
      setSecurityAnswer('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '注册申请提交失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.2 }}
        className="relative z-10 w-full max-w-lg"
      >
        <div className="bg-[#0a0a0a] border border-white/10 rounded-3xl p-8 shadow-2xl text-white">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-semibold">申请开通机构</h2>
              <p className="text-sm text-gray-500 mt-1">旧注册入口已切换为机构申请，建议从新的机构开通流程提交完整信息。</p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-white transition-colors text-2xl leading-none"
            >
              ×
            </button>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 mb-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          {success && (
            <div className="flex items-center gap-2 p-3 mb-4 bg-green-500/10 border border-green-500/20 rounded-xl text-green-300 text-sm">
              <CheckCircle2 size={16} />
              {success}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">账号 <span className="text-gray-600 font-normal">· 登录用</span></label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  placeholder="用于登录，提交后不可修改"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">姓名 <span className="text-gray-600 font-normal">· 对外显示</span></label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  required
                  placeholder="对外显示的姓名，可修改"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">密码</label>
                <div className="relative">
                  <input
                    type={showPwd ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={6}
                    placeholder="至少 6 位"
                    className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 pr-11 focus:outline-none focus:border-blue-500 transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd(!showPwd)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                  >
                    {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">确认密码</label>
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={6}
                  placeholder="再次输入密码"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
            </div>

            <RecoverySetupFields
              recoveryMethod={recoveryMethod}
              setRecoveryMethod={setRecoveryMethod}
              recoveryPhone={recoveryPhone}
              setRecoveryPhone={setRecoveryPhone}
              securityQuestion={securityQuestion}
              setSecurityQuestion={setSecurityQuestion}
              securityAnswer={securityAnswer}
              setSecurityAnswer={setSecurityAnswer}
            />

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white py-3 rounded-xl font-semibold transition-all shadow-lg shadow-blue-600/20 mt-2"
            >
              {loading ? '提交中...' : '提交注册申请'}
            </button>
          </form>
        </div>
      </motion.div>
    </motion.div>
  );
};

const OrganizationApplyModal = ({ onClose }: { onClose: () => void }) => {
  const [organizationName, setOrganizationName] = useState('');
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [recoveryMethod, setRecoveryMethod] = useState<RecoveryMethod>('phone');
  const [recoveryPhone, setRecoveryPhone] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    setLoading(true);
    try {
      await apiFetch<{ id: number; status: string }>('/api/organization-requests', {
        method: 'POST',
        body: JSON.stringify({
          organization_name: organizationName,
          username,
          display_name: displayName,
          password,
          ...buildRecoveryPayload(recoveryMethod, recoveryPhone, securityQuestion, securityAnswer),
        }),
      });
      setSuccess('机构申请已提交，等待审核。');
      setOrganizationName('');
      setUsername('');
      setDisplayName('');
      setPassword('');
      setConfirmPassword('');
      setRecoveryPhone('');
      setSecurityQuestion('');
      setSecurityAnswer('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '机构申请提交失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.2 }}
        className="relative z-10 w-full max-w-xl"
      >
        <div className="bg-[#0a0a0a] border border-white/10 rounded-3xl p-8 shadow-2xl text-white">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-semibold">申请开通机构</h2>
            </div>
            <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors text-2xl leading-none">×</button>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 mb-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
              <AlertCircle size={16} />
              {error}
            </div>
          )}
          {success && (
            <div className="flex items-center gap-2 p-3 mb-4 bg-green-500/10 border border-green-500/20 rounded-xl text-green-300 text-sm">
              <CheckCircle2 size={16} />
              {success}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm text-gray-400">机构名称</label>
              <input
                type="text"
                value={organizationName}
                onChange={(e) => setOrganizationName(e.target.value)}
                required
                placeholder="例如：北辰实验学校"
                className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">账号</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  placeholder="首位管理员登录账号"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">姓名</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  required
                  placeholder="对外显示的姓名"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">密码</label>
                <div className="relative">
                  <input
                    type={showPwd ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={6}
                    placeholder="至少 6 位"
                    className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 pr-11 focus:outline-none focus:border-blue-500 transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd(!showPwd)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                  >
                    {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">确认密码</label>
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={6}
                  placeholder="再次输入密码"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
            </div>

            <RecoverySetupFields
              recoveryMethod={recoveryMethod}
              setRecoveryMethod={setRecoveryMethod}
              recoveryPhone={recoveryPhone}
              setRecoveryPhone={setRecoveryPhone}
              securityQuestion={securityQuestion}
              setSecurityQuestion={setSecurityQuestion}
              securityAnswer={securityAnswer}
              setSecurityAnswer={setSecurityAnswer}
            />

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white py-3 rounded-xl font-semibold transition-all shadow-lg shadow-blue-600/20 mt-2"
            >
              {loading ? '提交中...' : '提交机构申请'}
            </button>
          </form>
        </div>
      </motion.div>
    </motion.div>
  );
};

const JoinOrganizationModal = ({
  onClose,
  inviteToken,
}: {
  onClose: () => void;
  inviteToken?: string | null;
}) => {
  const [inviteCode, setInviteCode] = useState('');
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [recoveryMethod, setRecoveryMethod] = useState<RecoveryMethod>('phone');
  const [recoveryPhone, setRecoveryPhone] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [organizationName, setOrganizationName] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setError('');
    setSuccess('');
    if (!inviteToken) {
      setOrganizationName('');
      return;
    }
    let cancelled = false;
    setPreviewLoading(true);
    apiFetch<{ organization_name: string }>(`/api/invite/${inviteToken}`)
      .then((payload) => {
        if (!cancelled) {
          setOrganizationName(payload.organization_name);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setOrganizationName('');
          setError(err instanceof Error ? err.message : '邀请链接已失效');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setPreviewLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [inviteToken]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    setLoading(true);
    try {
      const path = inviteToken ? `/api/join-by-invite-link/${inviteToken}` : '/api/join-by-invite-code';
      const payload = await apiFetch<{ user: CurrentUser }>(path, {
        method: 'POST',
        body: inviteToken
          ? JSON.stringify({
            username,
            display_name: displayName,
            password,
            ...buildRecoveryPayload(recoveryMethod, recoveryPhone, securityQuestion, securityAnswer),
          })
          : JSON.stringify({
            invite_code: inviteCode,
            username,
            display_name: displayName,
            password,
            ...buildRecoveryPayload(recoveryMethod, recoveryPhone, securityQuestion, securityAnswer),
          }),
      });
      setSuccess(`已加入 ${payload.user.organization_name}，现在可以使用新账号登录。`);
      setInviteCode('');
      setUsername('');
      setDisplayName('');
      setPassword('');
      setConfirmPassword('');
      setRecoveryPhone('');
      setSecurityQuestion('');
      setSecurityAnswer('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '加入机构失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.2 }}
        className="relative z-10 w-full max-w-xl"
      >
        <div className="bg-[#0a0a0a] border border-white/10 rounded-3xl p-8 shadow-2xl text-white">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-semibold">加入已有机构</h2>
              <p className="text-sm text-gray-400 mt-1">通过邀请码或邀请链接加入机构，成功后即可直接登录。</p>
            </div>
            <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors text-2xl leading-none">×</button>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 mb-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
              <AlertCircle size={16} />
              {error}
            </div>
          )}
          {success && (
            <div className="flex items-center gap-2 p-3 mb-4 bg-green-500/10 border border-green-500/20 rounded-xl text-green-300 text-sm">
              <CheckCircle2 size={16} />
              {success}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {inviteToken ? (
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">邀请链接目标机构</label>
                <div className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-gray-200">
                  {previewLoading ? '正在识别机构...' : organizationName || '邀请链接已失效'}
                </div>
              </div>
            ) : (
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">邀请码</label>
                <input
                  type="text"
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)}
                  required
                  placeholder="输入机构邀请码"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">账号</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  placeholder="用于登录"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">姓名</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  required
                  placeholder="对外显示的姓名"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">密码</label>
                <div className="relative">
                  <input
                    type={showPwd ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={6}
                    placeholder="至少 6 位"
                    className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 pr-11 focus:outline-none focus:border-blue-500 transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd(!showPwd)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                  >
                    {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">确认密码</label>
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={6}
                  placeholder="再次输入密码"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
            </div>

            <RecoverySetupFields
              recoveryMethod={recoveryMethod}
              setRecoveryMethod={setRecoveryMethod}
              recoveryPhone={recoveryPhone}
              setRecoveryPhone={setRecoveryPhone}
              securityQuestion={securityQuestion}
              setSecurityQuestion={setSecurityQuestion}
              securityAnswer={securityAnswer}
              setSecurityAnswer={setSecurityAnswer}
            />

            <button
              type="submit"
              disabled={loading || previewLoading || (Boolean(inviteToken) && !organizationName)}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white py-3 rounded-xl font-semibold transition-all shadow-lg shadow-blue-600/20 mt-2"
            >
              {loading ? '提交中...' : '加入机构'}
            </button>
          </form>
        </div>
      </motion.div>
    </motion.div>
  );
};

// --- Landing Page ---

export const LandingLegalPage = ({
  documentKey,
}: {
  documentKey: LandingLegalDocumentKey;
}) => {
  const document = LANDING_LEGAL_DOCUMENTS[documentKey];

  return (
    <div className="min-h-screen bg-[#F6FBFF] text-slate-900 selection:bg-sky-200/70 dark:bg-[#0d1220] dark:text-slate-100">
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-[-12%] left-[-8%] h-[28rem] w-[28rem] rounded-full bg-sky-200/45 blur-[120px]" />
        <div className="absolute right-[-10%] top-[10%] h-[24rem] w-[24rem] rounded-full bg-cyan-200/40 blur-[110px]" />
        <div className="absolute bottom-[-12%] left-[18%] h-[22rem] w-[22rem] rounded-full bg-blue-100/70 blur-[120px]" />
      </div>

      <nav className="sticky top-0 z-50 border-b border-sky-100/80 bg-white/80 backdrop-blur-xl dark:border-white/8 dark:bg-[#0d1220]/95">
        <div className="max-w-5xl mx-auto px-6 h-20 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <img src="/logo.png" alt="Starain logo" className="w-11 h-11 object-contain" />
            <div className="min-w-0">
              <p className="text-lg font-bold tracking-tight truncate dark:text-white">Starain</p>
              <p className="text-xs text-sky-700 tracking-[0.28em]">学习全流程 AI 平台</p>
            </div>
          </div>
          <a
            href="#"
            className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
          >
            <Home size={16} />
            返回首页
          </a>
        </div>
      </nav>

      <main className="relative z-10 max-w-5xl mx-auto px-6 py-16 md:py-24">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="rounded-[2rem] border border-sky-100 bg-white/85 p-8 md:p-12 shadow-[0_30px_90px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-slate-800/80"
        >
          <div className="flex flex-col gap-5 border-b border-sky-100 pb-8 dark:border-white/10">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-4 py-2 text-xs font-semibold tracking-[0.24em] text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">
              <ShieldCheck size={14} />
              法律文件
            </div>
            <div className="space-y-4">
              <h1 className="text-4xl md:text-5xl font-black tracking-tight dark:text-white">{document.title}</h1>
              <p className="max-w-3xl text-base md:text-lg text-slate-600 leading-8 dark:text-slate-300">{document.summary}</p>
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400">最近更新：{document.updatedAt}</p>
          </div>

          <div className="mt-10 space-y-8">
            {document.sections.map((section) => (
              <section
                key={section.title}
                className="rounded-[1.5rem] border border-sky-100 bg-white/90 p-6 md:p-7 shadow-[0_16px_48px_rgba(47,128,237,0.06)] dark:border-white/10 dark:bg-slate-800/75"
              >
                <h2 className="text-2xl font-bold tracking-tight dark:text-white">{section.title}</h2>
                <div className="mt-4 space-y-4 text-sm md:text-base leading-8 text-slate-600 dark:text-slate-300">
                  {section.paragraphs.map((paragraph) => (
                    <p key={paragraph}>{paragraph}</p>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </motion.div>
      </main>

      <footer className="relative z-10 border-t border-sky-100/80 py-10 dark:border-white/8">
        <div className="max-w-5xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-5 text-sm text-slate-500 dark:text-slate-400">
          <p>© 2026 Starain. 保留所有权利。</p>
          <div className="flex items-center gap-6">
            <a href="#privacy-policy" className="transition-colors hover:text-slate-900 dark:hover:text-white">隐私政策</a>
            <a href="#terms-of-service" className="transition-colors hover:text-slate-900 dark:hover:text-white">服务条款</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export const LandingPage = ({
  onLogin,
  onApplyOrganization,
  onJoinOrganization,
  activeLegalPage,
  isDark = false,
  onToggleDarkMode,
}: {
  onLogin: () => void;
  onApplyOrganization: () => void;
  onJoinOrganization: () => void;
  activeLegalPage?: LandingLegalDocumentKey | null;
  isDark?: boolean;
  onToggleDarkMode?: () => void;
}) => {
  const [hashLegalPage, setHashLegalPage] = useState<LandingLegalDocumentKey | null>(() =>
    typeof window === 'undefined' ? null : getLandingLegalPageFromHash(window.location.hash),
  );

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const syncLandingLegalPage = () => {
      setHashLegalPage(getLandingLegalPageFromHash(window.location.hash));
    };

    syncLandingLegalPage();
    window.addEventListener('hashchange', syncLandingLegalPage);
    return () => window.removeEventListener('hashchange', syncLandingLegalPage);
  }, []);

  const legalPage = activeLegalPage ?? hashLegalPage;

  if (legalPage) {
    return <LandingLegalPage documentKey={legalPage} />;
  }

  return (
    <div className="min-h-screen bg-[#F6FBFF] text-slate-900 selection:bg-sky-200/70 dark:bg-[#0d1220] dark:text-slate-100">
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 border-b border-sky-100/80 bg-white/80 backdrop-blur-xl dark:bg-[#0d1220]/95 dark:border-white/8">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="Starain logo" className="w-12 h-12 object-contain" />
            <span className="text-xl font-bold tracking-tight">星润Starain</span>
            <span className="hidden sm:block text-xs font-semibold uppercase tracking-[0.32em] text-sky-600">
              学习全流程 AI 平台
            </span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-500 dark:text-slate-400">
            <a href="#features" className="transition-colors hover:text-slate-900 dark:hover:text-white">核心方案</a>
            <a href="#about" className="transition-colors hover:text-slate-900 dark:hover:text-white">关于 Starain</a>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onToggleDarkMode}
              className="rounded-full p-2.5 text-slate-500 hover:bg-sky-50 dark:text-slate-400 dark:hover:bg-white/10 transition-colors"
              aria-label="切换夜间模式"
            >
              {isDark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <button
              onClick={onApplyOrganization}
              className="hidden sm:inline-flex rounded-full border border-sky-200 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition-all hover:bg-sky-50 active:scale-95 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
            >
              申请开通机构
            </button>
            <button
              onClick={onLogin}
              className="rounded-full bg-sky-600 px-6 py-2.5 text-sm font-bold text-white shadow-[0_16px_40px_rgba(34,199,232,0.28)] transition-all hover:bg-sky-500 active:scale-95"
            >
              立即登录
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative min-h-screen overflow-hidden bg-[#F8FBFF] dark:bg-[#0f172a]">
        <HeroBackgroundGrainient />

        <div className="max-w-7xl mx-auto px-6 relative z-10 flex min-h-screen items-end py-24 md:py-32 lg:py-36">
          <div className="grid w-full gap-10 lg:grid-cols-[minmax(0,1.12fr)_360px] lg:items-end">
            <motion.div
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.85, ease: [0.16, 1, 0.3, 1] }}
              className="max-w-3xl"
            >
              <motion.span
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.08, duration: 0.5 }}
                className="inline-flex items-center rounded-full border border-white/50 bg-white/55 px-4 py-1.5 text-[11px] font-semibold tracking-[0.32em] text-slate-700 backdrop-blur-md dark:border-white/12 dark:bg-slate-950/35 dark:text-sky-200"
              >
                服务学校与机构的 AI 教育平台
              </motion.span>
              <motion.h1
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.18, duration: 0.72, ease: [0.16, 1, 0.3, 1] }}
                className="mt-8 max-w-4xl text-4xl font-black leading-[1.02] tracking-tight text-slate-950 sm:text-6xl md:text-7xl dark:text-white"
              >
                用ai创造教育
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.32, duration: 0.78 }}
                className="mt-7 max-w-2xl text-base leading-8 text-slate-700 sm:text-lg md:text-xl dark:text-slate-200"
              >
                从复习资料生成，到错题跟进、讲义整理与教师协作，Starain 正在把日常教学里最常重复的工作整理进同一套平台流程。
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.46, duration: 0.78 }}
                className="mt-8 space-y-3"
              >
                {[
                  ['复习资料生成', '把课堂内容快速整理成学生可直接使用的复习材料。'],
                  ['错题跟进与复习安排', '围绕错题记录、老师备注和掌握状态，持续安排后续跟进。'],
                  ['教师协作交付', '让教师、教研与机构团队在同一平台里完成整理、复核与交付。'],
                ].map(([label, description]) => (
                  <div
                    key={label}
                    className="flex items-start gap-3 text-left"
                  >
                    <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-sky-500 shadow-[0_0_20px_rgba(14,165,233,0.5)]" />
                    <div>
                      <p className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-700 dark:text-sky-200">{label}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">{description}</p>
                    </div>
                  </div>
                ))}
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.58, duration: 0.78 }}
                className="mt-10 flex flex-col gap-4 sm:flex-row sm:flex-wrap"
              >
                <a
                  href="#features"
                  className="inline-flex items-center justify-center gap-2 rounded-2xl bg-sky-600 px-8 py-4 text-base font-bold text-white shadow-[0_24px_60px_rgba(34,199,232,0.28)] transition-all hover:bg-sky-500 active:scale-95"
                >
                  查看平台方案
                  <ArrowRight size={18} />
                </a>
                <button
                  onClick={onApplyOrganization}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-white/55 bg-white/55 px-8 py-4 text-base font-bold text-slate-800 backdrop-blur-md transition-all hover:bg-white/72 active:scale-95 dark:border-white/12 dark:bg-slate-950/30 dark:text-slate-100 dark:hover:bg-slate-950/42"
                >
                  <User size={18} />
                  申请开通机构
                </button>
                <button
                  onClick={onJoinOrganization}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-sky-200/70 bg-sky-50/85 px-8 py-4 text-base font-bold text-sky-900 transition-all hover:bg-sky-100 active:scale-95 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-100 dark:hover:bg-sky-500/20"
                >
                  <ArrowRight size={18} />
                  加入已有机构
                </button>
              </motion.div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 28, y: 20 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              transition={{ delay: 0.34, duration: 0.85, ease: [0.16, 1, 0.3, 1] }}
              className="lg:justify-self-end"
            >
              <div className="overflow-hidden rounded-[2rem] border border-white/55 bg-[linear-gradient(180deg,rgba(255,255,255,0.72)_0%,rgba(255,255,255,0.38)_100%)] p-5 shadow-[0_24px_80px_rgba(15,23,42,0.12)] backdrop-blur-xl dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(2,6,23,0.42)_0%,rgba(15,23,42,0.7)_100%)] dark:shadow-[0_24px_80px_rgba(2,6,23,0.35)]">
                <div className="flex items-center justify-between gap-4 border-b border-slate-200/70 pb-4 dark:border-white/10">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500 dark:text-slate-400">平台概览</p>
                    <p className="mt-2 text-lg font-semibold text-slate-900 dark:text-white">面向学习全流程的 AI 教育平台</p>
                  </div>
                  <div className="shrink-0 rounded-full border border-emerald-200/80 bg-emerald-50/80 px-4 py-1.5 text-xs font-semibold tracking-[0.18em] text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300 sm:px-5 sm:py-2 sm:text-sm">
                    已上线
                  </div>
                </div>

                <div className="mt-5 space-y-3">
                  {[
                    { icon: Upload, title: '复习资料', body: '课堂内容生成讲义、总结与学生复习材料' },
                    { icon: CheckCircle2, title: '错题跟进', body: '记录题目、错因与掌握状态，方便老师持续跟进' },
                    { icon: FileText, title: '教学交付', body: '把课堂内容整理成教师与机构团队都能直接使用的交付材料' },
                  ].map((item, index) => (
                    <motion.div
                      key={item.title}
                      initial={{ opacity: 0, y: 18 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.52 + index * 0.1, duration: 0.55 }}
                      className="rounded-[1.5rem] border border-white/60 bg-white/60 p-4 backdrop-blur-md dark:border-white/10 dark:bg-slate-950/34"
                    >
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-sky-600 text-white shadow-[0_14px_30px_rgba(14,165,233,0.28)]">
                          <item.icon size={18} />
                        </div>
                        <div>
                          <p className="text-sm font-semibold tracking-[0.18em] text-slate-800 dark:text-slate-100">{item.title}</p>
                          <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">{item.body}</p>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Feature Bento Grid */}
      <section id="features" className="border-t border-sky-100/80 py-24 dark:border-white/8">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            className="mb-16"
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-4 dark:text-white">把真实教学流程整理成可复用的 AI 能力</h2>
            <p className="text-slate-600 text-lg dark:text-slate-300">不是堆叠功能点，而是把一条已经跑通的教育工作流产品化。</p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Large Card */}
            <motion.div
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
              className="group relative overflow-hidden rounded-[2.5rem] border border-sky-100 bg-white/85 p-6 md:p-10 shadow-[0_24px_70px_rgba(47,128,237,0.06)] md:col-span-2 dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)]"
            >
              <div className="absolute right-0 top-0 p-8 opacity-10 transition-opacity group-hover:opacity-20">
                <FileText size={200} />
              </div>
              <div className="relative z-10 h-full flex flex-col justify-between">
                <div>
                  <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-600 text-white">
                    <FileText size={24} />
                  </div>
                  <h3 className="text-3xl font-bold mb-4 text-slate-900 dark:text-white">从课堂素材到复习交付</h3>
                  <p className="text-slate-600 text-lg max-w-2xl dark:text-slate-300">
                    课堂录音、笔记与教学内容进入平台后，被整理成结构化复习资料、练习内容与更稳定的教学交付材料。
                  </p>
                </div>
                <div className="mt-12 flex flex-wrap gap-4">
                  <div className="rounded-full border border-sky-100 bg-sky-50 px-4 py-2 text-xs font-mono text-sky-700 dark:bg-sky-900/40 dark:border-sky-500/30 dark:text-sky-300">课堂分析</div>
                  <div className="rounded-full border border-sky-100 bg-sky-50 px-4 py-2 text-xs font-mono text-sky-700 dark:bg-sky-900/40 dark:border-sky-500/30 dark:text-sky-300">复习资料生成</div>
                  <div className="rounded-full border border-sky-100 bg-sky-50 px-4 py-2 text-xs font-mono text-sky-700 dark:bg-sky-900/40 dark:border-sky-500/30 dark:text-sky-300">教学交付</div>
                </div>
              </div>
            </motion.div>

            {/* Small Card */}
            <motion.div
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
              className="flex flex-col justify-between rounded-[2.5rem] border border-sky-100 bg-[linear-gradient(180deg,_rgba(255,255,255,0.92)_0%,_rgba(239,248,255,0.92)_100%)] p-6 md:p-10 shadow-[0_20px_60px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)]"
            >
              <div>
                <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-500 text-white">
                  <AlertCircle size={24} />
                </div>
                <h3 className="text-2xl font-bold mb-4 text-slate-900 dark:text-white">把错误整理成可持续跟进记录</h3>
                <p className="text-slate-600 dark:text-slate-300">
                  不是一次性纠错，而是持续记录高频错误、薄弱点与个性化复习路径。
                </p>
              </div>
              <div className="mt-8 flex flex-wrap gap-2">
                <span className="rounded-full bg-cyan-50 px-3 py-1 text-[10px] font-bold tracking-widest text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300">错因整理</span>
                <span className="rounded-full bg-cyan-50 px-3 py-1 text-[10px] font-bold tracking-widest text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300">薄弱点追踪</span>
                <span className="rounded-full bg-cyan-50 px-3 py-1 text-[10px] font-bold tracking-widest text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300">个性化复习</span>
              </div>
            </motion.div>

            {/* Small Card */}
            <motion.div
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
              className="flex flex-col justify-between rounded-[2.5rem] border border-sky-100 bg-white/85 p-6 md:p-10 shadow-[0_20px_60px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)]"
            >
              <div>
                <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-500 text-white">
                  <Database size={24} />
                </div>
                <h3 className="text-2xl font-bold mb-4 text-slate-900 dark:text-white">把题目整理成可复用的教学素材</h3>
                <p className="text-slate-600 dark:text-slate-300">
                  围绕课堂练习、作业和错题记录，帮助老师逐步整理出更稳定的讲义与练习素材。
                </p>
              </div>
              <div className="mt-8 flex items-center gap-2 text-blue-600 font-bold text-sm dark:text-blue-400">
                <span>题目整理</span>
                <ArrowRight size={14} />
              </div>
            </motion.div>

            {/* Medium Card */}
            <motion.div
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="flex flex-col items-center gap-10 rounded-[2.5rem] border border-sky-100 bg-white/85 p-6 md:p-10 shadow-[0_24px_70px_rgba(47,128,237,0.06)] md:col-span-2 md:flex-row dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)]"
            >
              <div className="flex-1">
                <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-800 text-white">
                  <FileText size={24} />
                </div>
                <h3 className="text-3xl font-bold mb-4 text-slate-900 dark:text-white">把课程目标转化为讲义与教研交付</h3>
                <p className="text-slate-600 text-lg dark:text-slate-300">
                  从课程目标到讲义、课堂提纲和教研素材，减少教师重复整理工作。
                </p>
              </div>
              <div className="flex w-full flex-col gap-3 rounded-3xl border border-sky-100 bg-[linear-gradient(180deg,_rgba(255,255,255,0.96)_0%,_rgba(234,245,255,0.96)_100%)] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)] md:w-72 dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.92)_0%,rgba(30,41,59,0.88)_100%)]">
                {[
                  { label: '讲义大纲', tone: 'bg-orange-500', width: '72%' },
                  { label: '课堂提纲', tone: 'bg-orange-400', width: '58%' },
                  { label: '教研材料', tone: 'bg-orange-300', width: '33%' },
                ].map((item, index) => (
                  <motion.div
                    key={item.label}
                    initial={{ opacity: 0, y: 14 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.55, delay: 0.15 + index * 0.12, ease: [0.16, 1, 0.3, 1] }}
                    className="rounded-2xl border border-sky-100 bg-white/90 p-4 shadow-[0_14px_34px_rgba(47,128,237,0.07)] dark:border-white/10 dark:bg-slate-900/88"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm font-medium text-slate-900 dark:text-white">{item.label}</span>
                      <span className="text-[10px] rounded-full border border-sky-100 bg-sky-50 px-2 py-1 text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/50 dark:text-sky-300">
                        AI Draft
                      </span>
                    </div>
                    <div className="space-y-2">
                      <div className="h-2 overflow-hidden rounded-full bg-sky-100 dark:bg-slate-600">
                        <motion.div
                          initial={{ width: '0%' }}
                          whileInView={{ width: item.width }}
                          viewport={{ once: true }}
                          transition={{ duration: 0.9, delay: 0.35 + index * 0.15, ease: [0.16, 1, 0.3, 1] }}
                          className={`h-full ${item.tone}`}
                        />
                      </div>
                      <div className="h-2 w-3/4 rounded-full bg-sky-100 dark:bg-slate-600" />
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* About Section */}
      <section id="about" className="border-t border-sky-100/80 py-24 dark:border-white/8">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] gap-10 items-start">
            <motion.div
              className="space-y-6"
              initial={{ opacity: 0, y: 28 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            >
              <span className="inline-flex items-center rounded-full border border-slate-200 bg-white/80 px-4 py-1.5 text-xs font-semibold tracking-[0.28em] text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400">
                ABOUT STARAIN
              </span>
              <div>
                <h2 className="text-4xl md:text-5xl font-bold mb-4 text-slate-900 dark:text-white">关于 Starain</h2>
                <p className="max-w-2xl text-lg text-slate-600 leading-relaxed dark:text-slate-300">
                  Starain 不是从 PPT 里想出来的，而是从真实教学现场长出来的。
                </p>
              </div>
              <p className="max-w-2xl text-sm md:text-base text-slate-500 leading-relaxed dark:text-slate-400">
                我们先在自己的教育机构中解决复习资料、错题跟进、讲义整理与教师协作问题，再把这套已经跑通的流程产品化，服务更多同行团队。
              </p>
            </motion.div>

            <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-1 gap-4">
              {[
                {
                  title: '已验证流程',
                  body: '课堂素材到复习交付的链路已经在真实教学里跑通。',
                },
                {
                  title: '能力模块化',
                  body: '错题跟进、复习安排与讲义整理可以在同一条教学链路里持续复用。',
                },
                {
                  title: '服务对象',
                  body: '聚焦学校、培训机构、国际课程团队与教研运营场景。',
                },
              ].map((item, i) => (
                <motion.div
                  key={item.title}
                  initial={{ opacity: 0, y: 24 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.5, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
                  className="rounded-[2rem] border border-sky-100 bg-white/85 p-6 shadow-[0_20px_60px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-slate-800/80"
                >
                  <p className="mb-2 text-sm font-semibold text-slate-900 dark:text-white">{item.title}</p>
                  <p className="text-sm leading-relaxed text-slate-500 dark:text-slate-400">{item.body}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-sky-100/80 py-20 dark:border-white/8">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-8">
          <div className="flex flex-col items-center md:items-start gap-3">
            <div className="flex items-center gap-3">
              <img src="/logo.png" alt="Starain logo" className="w-10 h-10 object-contain" />
              <span className="text-lg font-bold tracking-tight dark:text-white">星润Starain</span>
              <span className="text-xs font-semibold uppercase tracking-[0.32em] text-sky-600">
                学习全流程 AI 平台
              </span>
            </div>
            <p className="max-w-md text-sm text-gray-500 text-center md:text-left dark:text-slate-400">
              面向学校、机构与教学团队，构建从内容生成到教学交付的 AI 能力底座。
            </p>
          </div>
          <div className="flex flex-col items-center md:items-start gap-2 text-sm text-slate-500 dark:text-slate-400">
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-1">导航</p>
            <a href="#features" className="transition-colors hover:text-slate-900 dark:hover:text-white">核心方案</a>
            <a href="#about" className="transition-colors hover:text-slate-900 dark:hover:text-white">关于 Starain</a>
          </div>
          <div className="flex flex-col items-center md:items-start gap-2 text-sm text-slate-500 dark:text-slate-400">
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-1">法律</p>
            <a href="#privacy-policy" className="transition-colors hover:text-slate-900 dark:hover:text-white">隐私政策</a>
            <a href="#terms-of-service" className="transition-colors hover:text-slate-900 dark:hover:text-white">服务条款</a>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">© 2026 Starain. 保留所有权利。</p>
        </div>
      </footer>
    </div>
  );
};

// --- Main App ---
