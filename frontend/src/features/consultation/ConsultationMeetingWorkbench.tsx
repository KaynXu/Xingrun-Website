import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, CalendarDays, CheckCircle2, ChevronDown, Eye, MessageSquare, Pencil, X } from 'lucide-react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';

import type { ClassItem, CurrentUser } from '../../appTypes';
import { hasOwnerAccess } from '../navigation/workspaceAccess';
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
  buildConsultationFlowStageTeacherLabels,
  buildConsultationTeacherDirectory,
  consultationInputClass,
  consultationMeetingVersion,
  consultationSurfaceClass,
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
  workspaceCardClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  writeLocalStorageItem,
} from '../../workspaceShared';

const meetingDayMs = 86_400_000;

function shiftMeetingIsoDate(isoDate: string, deltaDays: number): string {
  const time = Date.parse(`${isoDate}T12:00:00`);
  if (!Number.isFinite(time)) {
    return isoDate;
  }
  return new Date(time + deltaDays * meetingDayMs).toISOString().slice(0, 10);
}

function getMeetingRecordEndedDate(record: ConsultationRecord): string {
  return (record.ended_at || '').slice(0, 10);
}

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
  const [endedRangeMode, setEndedRangeMode] = useState<'week' | 'custom'>('week');
  const [customEndedStart, setCustomEndedStart] = useState(() => shiftMeetingIsoDate(getTodayIsoDate(), -7));
  const [customEndedEnd, setCustomEndedEnd] = useState(() => getTodayIsoDate());
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
  const getMeetingEndedAgeDays = (record: ConsultationRecord): number => {
    const endedDate = getMeetingRecordEndedDate(record);
    if (!endedDate) return Number.POSITIVE_INFINITY;
    const endedTime = Date.parse(`${endedDate}T12:00:00`);
    const todayTime = Date.parse(`${meetingTodayIso}T12:00:00`);
    if (!Number.isFinite(endedTime) || !Number.isFinite(todayTime)) return Number.POSITIVE_INFINITY;
    return Math.max(0, Math.floor((todayTime - endedTime) / meetingDayMs));
  };
  const isMeetingEndedInSelectedRange = (record: ConsultationRecord) => {
    const endedDate = getMeetingRecordEndedDate(record);
    if (!endedDate) return false;
    if (endedRangeMode === 'week') {
      return getMeetingEndedAgeDays(record) <= 7;
    }
    return (!customEndedStart || endedDate >= customEndedStart) && (!customEndedEnd || endedDate <= customEndedEnd);
  };

  const pendingRecords = filteredRecords.filter((record) => !processedIds.has(record.id));
  const processedRecords = filteredRecords.filter((record) => processedIds.has(record.id));
  const pendingEndedRecords = pendingRecords.filter(isMeetingEndedRecord);
  const pendingActiveRecords = pendingRecords.filter((record) => !isMeetingEndedRecord(record));
  const pendingVisibleRecords = [...pendingActiveRecords, ...pendingEndedRecords.filter(isMeetingEndedInSelectedRange)];
  const processedVisibleRecords = processedRecords;
  const pendingRangeCounts = {
    active: pendingActiveRecords.length,
    endedInRange: pendingEndedRecords.filter(isMeetingEndedInSelectedRange).length,
    endedTotal: pendingEndedRecords.length,
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
      closingResult={record.closing_result}
      stageTeacherLabels={buildConsultationFlowStageTeacherLabels(toConsultationFormValues(record))}
      editable={false}
      showOver
      overDisabled={false}
      onOverDoubleClick={() => handleMeetingOverDoubleClick(record)}
    />
  );

  const getMeetingRecordResultPill = (record: ConsultationRecord) => {
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

  const renderMeetingDesktopCard = (record: ConsultationRecord) => (
    <article className="overflow-hidden rounded-[14px] border border-[#D9EEF7] bg-white dark:border-white/10 dark:bg-slate-950/70">
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
    <article className="overflow-hidden rounded-[14px] border border-[#D9EEF7] bg-white dark:border-white/10 dark:bg-slate-950/70">
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
      <article className="relative space-y-3 rounded-[14px] border border-[#D9EEF7] bg-white p-3.5 dark:border-white/10 dark:bg-slate-950/70">
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

  const renderMeetingRangeFilter = () => (
    <div className="mb-4 flex flex-col gap-2 rounded-2xl border border-[#D9EEF7] bg-[#F9FDFF] px-3 py-3 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex h-8 items-center rounded-full border border-sky-100 bg-white px-3 text-xs font-bold text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
          待咨询
          <span className="ml-1 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500 dark:bg-white/10 dark:text-slate-300">
            全部 {pendingRangeCounts.active}
          </span>
        </span>
        <span className="inline-flex h-8 items-center rounded-full border border-sky-100 bg-white px-3 text-xs font-bold text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
          已结束
          <span className="ml-1 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500 dark:bg-white/10 dark:text-slate-300">
            {pendingRangeCounts.endedInRange}/{pendingRangeCounts.endedTotal}
          </span>
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2 pl-0 sm:pl-2">
        <button
          type="button"
          onClick={() => setEndedRangeMode('week')}
          className={cn(
            'h-7 rounded-full border px-2.5 text-[11px] font-bold transition',
            endedRangeMode === 'week'
              ? 'border-emerald-200 bg-emerald-500 text-white'
              : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300',
          )}
        >
          近1周
        </button>
        <button
          type="button"
          onClick={() => setEndedRangeMode('custom')}
          className={cn(
            'h-7 rounded-full border px-2.5 text-[11px] font-bold transition',
            endedRangeMode === 'custom'
              ? 'border-emerald-200 bg-emerald-500 text-white'
              : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300',
          )}
        >
          自定义日期
        </button>
        {endedRangeMode === 'custom' && (
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="date"
              value={customEndedStart}
              onChange={(event) => setCustomEndedStart(event.target.value)}
              className="h-8 rounded-full border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-600 outline-none focus:border-emerald-300 dark:border-white/10 dark:bg-white/5 dark:text-slate-200"
              aria-label="已结束开始日期"
            />
            <span className="text-xs font-bold text-slate-400">至</span>
            <input
              type="date"
              value={customEndedEnd}
              onChange={(event) => setCustomEndedEnd(event.target.value)}
              className="h-8 rounded-full border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-600 outline-none focus:border-emerald-300 dark:border-white/10 dark:bg-white/5 dark:text-slate-200"
              aria-label="已结束结束日期"
            />
          </div>
        )}
      </div>
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
                  className="absolute right-0 top-12 z-30 w-[min(22rem,calc(100vw-2rem))] rounded-2xl border border-[#D9EEF7] bg-white p-3 dark:border-white/10 dark:bg-slate-950"
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
                  ? 'bg-white text-[#0EA5E9] dark:bg-sky-400/15 dark:text-sky-100'
                  : 'text-[#7188A6] hover:text-[#1F2A44] dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              待处理
              <span className="rounded-full bg-sky-50 px-2 py-0.5 text-xs font-bold text-sky-600 dark:bg-sky-400/10 dark:text-sky-200">{pendingVisibleRecords.length}</span>
            </button>
            <button
              type="button"
              onClick={() => setWorkbenchTab('processed')}
              className={`flex h-10 items-center justify-center gap-2 rounded-xl text-sm font-extrabold transition ${
                workbenchTab === 'processed'
                  ? 'bg-white text-[#22B981] dark:bg-emerald-400/15 dark:text-emerald-100'
                  : 'text-[#7188A6] hover:text-[#1F2A44] dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              已处理
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-600 dark:bg-emerald-400/10 dark:text-emerald-200">{processedRecords.length}</span>
            </button>
          </div>

          {workbenchTab === 'pending' ? (
            <div>
              {renderMeetingRangeFilter()}
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
              <div className="grid gap-3">
                {processedVisibleRecords.length ? (
                  <AnimatePresence initial={false}>
                    {processedVisibleRecords.map(renderMeetingRecordCard)}
                  </AnimatePresence>
                ) : renderWorkbenchEmptyState('本次还没有已处理记录', '编辑、结束或直接标记核对后，记录会进入这里，最终保存后同步主咨询页。', '查看待处理', () => setWorkbenchTab('pending'))}
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
