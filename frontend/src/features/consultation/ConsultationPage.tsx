import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, CalendarDays, ChevronDown, Cpu, Eye, Pencil, PlusCircle, Search, Trash2, UsersRound, } from 'lucide-react';
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
import { ConsultationEnterClassDialog } from './ConsultationEnterClassDialog';
import { buildConsultationEnterClassPayload } from '../../domain/consultationEnterClass';
import {
  buildConsultationQuickClassSavePayload,
  validateConsultationQuickClassForm,
} from '../../domain/consultationStudentCenterClassAdapter';
import type { ClassFormValues, UserItem } from '../student-center/model';
import { ConsultationBatchModal } from './ConsultationBatchModal';
import {
  ConsultationCardExpandableText,
  ConsultationFlowBar,
  ConsultationFlowNodeDialog,
  applyConsultationFlowNodeDraft,
  buildConsultationFlowStageTeacherLabels,
  buildConsultationTeacherDirectory,
  clearConsultationFlowNodeContent,
  clearConsultationResultStage,
  completeConsultationOverValues,
  consultationFilterGroups,
  consultationFilterLabels,
  consultationProcessStages,
  getConsultationFilterKey,
  getConsultationFlowLightColor,
  getConsultationOver30SectionLabel,
  getConsultationSourceLabel,
  getConsultationTeacherName,
  isConsultationEnded,
  isConsultationResultStage,
  normalizeConsultationRecord,
  restoreConsultationValues,
  setConsultationResultStage,
  sortConsultationsForFilter,
  type ConsultationFlowNodeDraft,
} from './consultationShared';
import { workspaceCardClass, workspaceFieldClass, workspacePageClass, workspacePrimaryButtonClass, workspaceSecondaryButtonClass, workspaceSectionTextClass, workspaceSectionTitleClass, apiFetch, cn, getTodayIsoDate } from '../../workspaceShared';
import { hasOwnerAccess, hasStaffAccess } from '../navigation/workspaceAccess';

const consultationQuickClassGradeOptions = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三'];

export function ConsultationPage({ currentUser }: { currentUser: CurrentUser }) {
  const canManage = hasStaffAccess(currentUser.role);
  const canOpenMeetingWorkbench = hasOwnerAccess(currentUser.role);
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
  const [overResultDialogRecord, setOverResultDialogRecord] = useState<ConsultationRecord | null>(null);
  const [inlineEnterClassRecord, setInlineEnterClassRecord] = useState<ConsultationRecord | null>(null);
  const [inlineEnterClassCreating, setInlineEnterClassCreating] = useState(false);
  const [inlineEnterClassError, setInlineEnterClassError] = useState('');
  const [flowNodeDialog, setFlowNodeDialog] = useState<{ record: ConsultationRecord; stage: string; setAsCurrent: boolean } | null>(null);
  const loadRequestId = useRef(0);
  const teacherDirectory = buildConsultationTeacherDirectory(records);
  const inlineEnterClassUsers = useMemo<UserItem[]>(() => {
    const usersById = new Map<number, UserItem>();
    const addUser = (id: number | null | undefined, name: string | null | undefined) => {
      if (id == null || usersById.has(id)) {
        return;
      }
      usersById.set(id, {
        id,
        name: name?.trim() || (id === currentUser.id ? currentUser.display_name || currentUser.username : '未命名老师'),
        org: currentUser.organization_name,
        role: id === currentUser.id ? currentUser.role as UserItem['role'] : 'member',
        username: id === currentUser.id ? currentUser.username : undefined,
      });
    };

    classes.forEach((item) => addUser(item.teacher_user_id, item.teacher_name));
    if (inlineEnterClassRecord) {
      addUser(
        (inlineEnterClassRecord as ConsultationRecord & { teaching_teacher_user_id?: number | null }).teaching_teacher_user_id,
        inlineEnterClassRecord.teaching_teacher || inlineEnterClassRecord.trial_teacher || inlineEnterClassRecord.receiving_teacher,
      );
    }

    return Array.from(usersById.values());
  }, [classes, currentUser.display_name, currentUser.id, currentUser.organization_name, currentUser.role, currentUser.username, inlineEnterClassRecord]);

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

  const openConsultationMeetingWorkbench = () => {
    window.location.assign('/workspace/consultation?consultationMeeting=1');
  };

  const openViewModal = (record: ConsultationRecord) => {
    setSelectedRecord(record);
    setModalMode('view');
    setModalOpen(true);
    setError('');
  };

  const openEditModal = (record: ConsultationRecord) => {
    if (!canEditConsultationRecord(record)) {
      return;
    }
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
      return sortConsultationsForFilter(
        records.filter((record) => getConsultationFilterKey(record, consultationTodayIso).startsWith('pending-')),
        'pending-7',
      );
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

  const canEditConsultationRecord = (record: ConsultationRecord): boolean => (
    canManage || (canEditConsultations && record.can_edit_consultation)
  );

  const canEditConsultationStage = (record: ConsultationRecord, stage: string): boolean => {
    if (!canEditConsultationRecord(record)) return false;
    if (canManage || !record.is_transferred_consultation || !record.assigned_stage) return true;
    const assignedIndex = consultationProcessStages.indexOf(record.assigned_stage);
    const stageIndex = consultationProcessStages.indexOf(stage);
    return assignedIndex < 0 || stageIndex < 0 || stageIndex >= assignedIndex;
  };

  const openInlineFlowNodeDialog = (record: ConsultationRecord, stage: string, setAsCurrent: boolean) => {
    if (!consultationProcessStages.includes(stage)) return;
    setFlowNodeDialog({ record, stage, setAsCurrent });
  };

  const openInlineEnterClassDialog = (record: ConsultationRecord) => {
    setOverResultDialogRecord(null);
    setInlineEnterClassError('');
    setError('');
    setInlineEnterClassRecord(record);
  };

  const handleInlineStageClick = async (record: ConsultationRecord, stage: string) => {
    if (!canEditConsultationRecord(record) || isBusy || isConsultationEnded(record.flow_stage)) {
      return;
    }
    if (!canEditConsultationStage(record, stage)) {
      setError('转接咨询只能编辑当前转接阶段及之后的流程。');
      return;
    }
    setError('');
    const lightColor = getConsultationFlowLightColor(toConsultationFormValues(record), stage);
    if (lightColor === 'green' || lightColor === 'blue') {
      const values = clearConsultationFlowNodeContent(toConsultationFormValues(record), stage);
      await saveInlineConsultationUpdate(record, values, '更新咨询流程失败');
      return;
    }
    openInlineFlowNodeDialog(record, stage, false);
  };

  const handleInlineStageCurrent = async (record: ConsultationRecord, stage: string) => {
    if (!canEditConsultationRecord(record) || isBusy || isConsultationEnded(record.flow_stage)) {
      return;
    }
    if (!canEditConsultationStage(record, stage)) {
      setError('转接咨询只能编辑当前转接阶段及之后的流程。');
      return;
    }
    setError('');
    openInlineFlowNodeDialog(record, stage, true);
  };

  const handleSaveInlineFlowNodeDialog = async (draft: ConsultationFlowNodeDraft) => {
    if (!flowNodeDialog) return;
    const { record, stage, setAsCurrent } = flowNodeDialog;
    const values = applyConsultationFlowNodeDraft(toConsultationFormValues(record), stage, draft, setAsCurrent);
    setFlowNodeDialog(null);
    await saveInlineConsultationUpdate(record, values, '更新咨询流程失败');
  };

  const handleInlineResultChange = async (record: ConsultationRecord, resultStage: ConsultationResultStage) => {
    if (!canEditConsultationRecord(record) || isBusy || isConsultationEnded(record.flow_stage)) {
      return;
    }
    if (resultStage === '成功进班' && !record.success_class_id && !record.success_class_manual.trim()) {
      openInlineEnterClassDialog(record);
      return;
    }
    setError('');
    const values = setConsultationResultStage(toConsultationFormValues(record), resultStage);
    await saveInlineConsultationUpdate(record, values, '更新咨询结果失败');
  };

  const handleInlineResultClick = async (record: ConsultationRecord) => {
    if (!canEditConsultationRecord(record) || isBusy || isConsultationEnded(record.flow_stage)) {
      return;
    }
    if (!isConsultationResultStage(record.flow_stage) && !record.success_class_id && !record.success_class_manual.trim()) {
      openInlineEnterClassDialog(record);
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
    if (!canEditConsultationRecord(record) || isBusy) {
      return;
    }
    if (isConsultationEnded(record.flow_stage)) {
      setRestoreConfirmRecord(record);
      return;
    }
    setError('');
    setOverResultDialogRecord(record);
  };

  const handleInlineOverSuccess = async () => {
    if (!overResultDialogRecord) {
      return;
    }
    const record = overResultDialogRecord;
    if (!record.success_class_id && !record.success_class_manual.trim()) {
      openInlineEnterClassDialog(record);
      return;
    }
    setOverResultDialogRecord(null);
    setError('');
    const values = completeConsultationOverValues(
      setConsultationResultStage(toConsultationFormValues(record), '成功进班'),
      'success',
    );
    await saveInlineConsultationUpdate(record, values, '结束咨询失败');
  };

  const handleInlineOverFailure = async () => {
    if (!overResultDialogRecord) {
      return;
    }
    const record = overResultDialogRecord;
    setOverResultDialogRecord(null);
    setError('');
    const values = completeConsultationOverValues(toConsultationFormValues(record), 'failed');
    await saveInlineConsultationUpdate(record, values, '结束咨询失败');
  };

  const refreshClasses = async () => {
    try {
      const updatedClasses = await apiFetch<ClassItem[]>('/api/classes');
      setClasses(updatedClasses);
    } catch {
      // The consultation was already updated; class refresh can recover on the next page load.
    }
  };

  const applyInlineEnterClassResult = async (result: { item?: ConsultationRecord; class_id?: number }) => {
    if (result.item) {
      const normalized = normalizeConsultationRecord(result.item);
      setRecords((current) => current.map((item) => (item.id === normalized.id ? normalized : item)));
      if (selectedRecord?.id === normalized.id) {
        setSelectedRecord(normalized);
      }
    }
    if (result.class_id) {
      await refreshClasses();
    }
    setInlineEnterClassRecord(null);
    setOverResultDialogRecord(null);
  };

  const postInlineEnterClass = async (payload: object) => {
    if (!inlineEnterClassRecord) return;
    setInlineEnterClassCreating(true);
    setInlineEnterClassError('');
    setError('');
    try {
      const result = await apiFetch<{ item?: ConsultationRecord; class_id?: number }>(
        `/api/consultations/${inlineEnterClassRecord.id}/enter-class`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      );
      await applyInlineEnterClassResult(result);
    } catch (err) {
      setInlineEnterClassError(err instanceof Error ? err.message : '进班处理失败');
    } finally {
      setInlineEnterClassCreating(false);
    }
  };

  const handleInlineEnterExistingClass = (classId: number) => {
    if (!inlineEnterClassRecord) return;
    const selectedClass = classes.find((item) => item.id === classId);
    void postInlineEnterClass(buildConsultationEnterClassPayload({
      mode: 'existing',
      existingClassId: classId,
      consultationSubject: selectedClass?.subject || inlineEnterClassRecord.consultation_subject,
      grade: selectedClass?.current_grade || selectedClass?.grade || inlineEnterClassRecord.grade,
    }));
  };

  const handleInlineEnterCreateClass = async (draft: ClassFormValues) => {
    if (!inlineEnterClassRecord) return;
    const hasReliableQuickClassTeacher = inlineEnterClassRecord.teaching_teacher_user_id != null;
    const quickClassTeacherUserId = hasReliableQuickClassTeacher
      ? inlineEnterClassRecord.teaching_teacher_user_id
      : currentUser.id;
    const quickClassTeacherName = hasReliableQuickClassTeacher
      ? inlineEnterClassRecord.teaching_teacher || inlineEnterClassRecord.trial_teacher || inlineEnterClassRecord.receiving_teacher || currentUser.display_name || currentUser.username
      : currentUser.display_name || currentUser.username;
    const selectedTeacher: UserItem = {
      id: quickClassTeacherUserId,
      name: quickClassTeacherName,
      org: currentUser.organization_name,
      role: currentUser.role,
      username: quickClassTeacherUserId === currentUser.id ? currentUser.username : undefined,
    };
    const quickClassForm = {
      ...draft,
      grade: draft.current_grade,
      class_number: draft.class_type === 'group' ? draft.class_number : '',
    };
    const validationError = validateConsultationQuickClassForm({
      form: quickClassForm,
      selectedTeacher,
      selectedTeacherUserId: quickClassTeacherUserId,
      gradeOptions: consultationQuickClassGradeOptions,
    });
    if (validationError) {
      setInlineEnterClassError(validationError);
      return;
    }

    setInlineEnterClassCreating(true);
    setInlineEnterClassError('');
    setError('');
    try {
      const payload = buildConsultationQuickClassSavePayload({
        form: quickClassForm,
        selectedTeacher,
        selectedTeacherUserId: quickClassTeacherUserId,
      });
      const createdClass = await apiFetch<ClassItem>('/api/classes', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setClasses((current) => [createdClass, ...current.filter((item) => item.id !== createdClass.id)]);
      await postInlineEnterClass(buildConsultationEnterClassPayload({
        mode: 'existing',
        existingClassId: createdClass.id,
        consultationSubject: createdClass.subject,
        grade: createdClass.current_grade || createdClass.grade,
      }));
    } catch (err) {
      setInlineEnterClassError(err instanceof Error ? err.message : '快速建班失败');
    } finally {
      setInlineEnterClassCreating(false);
    }
  };

  const handleInlineEnterPendingClass = () => {
    void postInlineEnterClass(buildConsultationEnterClassPayload({ mode: 'pending' }));
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
    const canEditRecord = canEditConsultationRecord(record);
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
        {canEditRecord && (
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
    const canEditRecord = canEditConsultationRecord(record);
    return (
      <ConsultationFlowBar
        mode="list"
        stage={record.flow_stage}
        completedStages={record.completed_stages}
        closingResult={record.closing_result}
        stageTeacherLabels={buildConsultationFlowStageTeacherLabels(toConsultationFormValues(record))}
        editable={canEditRecord && !busy && !frozen}
        showOver
        overDisabled={!canEditRecord || busy}
        onStageClick={(stage) => handleInlineStageClick(record, stage)}
        onStageContextMenu={(stage) => handleInlineStageCurrent(record, stage)}
        onStageLongPress={(stage) => handleInlineStageCurrent(record, stage)}
        onResultChange={(stage) => handleInlineResultChange(record, stage)}
        onResultClick={() => handleInlineResultClick(record)}
        onResultDoubleClick={() => handleInlineResultChange(record, '成功进班')}
        onOverClick={() => handleInlineEndConsultation(record)}
      />
    );
  };

  const renderB3FlowStrip = (record: ConsultationRecord, busy: boolean, mobile = false) => {
    if (mobile) return renderInlineFlow(record, busy);
    const frozen = isConsultationEnded(record.flow_stage);
    return (
      <div className={`min-w-0 overflow-visible ${frozen ? 'opacity-75' : ''}`}>
        {renderInlineFlow(record, busy)}
      </div>
    );
  };

  const getConsultationTransferBadge = (record: ConsultationRecord) => {
    if (!record.is_transferred_consultation) return null;
    return (
      <div className="flex min-w-0 flex-wrap items-center gap-2 rounded-lg border border-amber-100 bg-amber-50/70 px-3 py-2 text-xs font-bold text-amber-700 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-200">
        <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-amber-700 shadow-sm dark:bg-white/10 dark:text-amber-100">
          {record.transfer_marker || '咨询转接'}
        </span>
        {record.current_responsibility ? <span className="min-w-0 truncate">{record.current_responsibility}</span> : null}
        {record.assignment_note ? <span className="min-w-0 truncate text-amber-600/80 dark:text-amber-100/80">备注：{record.assignment_note}</span> : null}
        {!record.can_edit_consultation ? <span className="shrink-0 text-slate-400">仅查看</span> : null}
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
      disabled={!canEditConsultationRecord(record) || busy}
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
        <article className={cn('overflow-hidden rounded-[14px] border border-[#D9EEF7] bg-white dark:border-white/10 dark:bg-slate-950/70', record.is_transferred_consultation && 'bg-amber-50/30 dark:bg-amber-500/5')}>
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
            {getConsultationTransferBadge(record)}
            {renderConsultationDetail(needDetail, followUpNote)}
            {renderTimeRow(record)}
          </div>
          <div className="border-t border-[#EEF7FC] bg-[#F9FDFF] px-4 py-3 dark:border-white/10 dark:bg-white/[0.03]">
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
        <article className={cn('overflow-hidden rounded-[14px] border border-[#D9EEF7] bg-white dark:border-white/10 dark:bg-slate-950/70', record.is_transferred_consultation && 'bg-amber-50/30 dark:bg-amber-500/5')}>
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
            {getConsultationTransferBadge(record)}
            {renderConsultationDetail(needDetail, followUpNote)}
            {renderTimeRow(record)}
          </div>
          <div className="border-t border-[#EEF7FC] bg-[#F9FDFF] px-4 py-3 dark:border-white/10 dark:bg-white/[0.03]">
            {renderB3FlowStrip(record, busy)}
          </div>
        </article>
      </React.Fragment>
    );
  };

  const renderMobileConsultationCard = (record: ConsultationRecord, index: number) => {
    const busy = isBusy && selectedRecord?.id === record.id;
    const canEditRecord = canEditConsultationRecord(record);
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
        <article className={cn('relative space-y-3 rounded-[14px] border border-[#D9EEF7] bg-white p-3.5 dark:border-white/10 dark:bg-slate-950/70', record.is_transferred_consultation && 'bg-amber-50/30 dark:bg-amber-500/5')}>
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
                      disabled={!canEditRecord || busy || isConsultationEnded(record.flow_stage)}
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
          {getConsultationTransferBadge(record)}
          {renderConsultationDetail(needDetail, followUpNote, true)}
          {renderTimeRow(record, true)}
          <div className="space-y-2.5">
            <div className="min-w-0 overflow-visible">{renderB3FlowStrip(record, busy, true)}</div>
            {canEditRecord && (
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
            {canOpenMeetingWorkbench && (
              <button
                type="button"
                onClick={openConsultationMeetingWorkbench}
                className={`${workspaceSecondaryButtonClass} h-10 w-full min-w-0 !gap-1 !px-1 !py-2 text-[11px] sm:text-xs`}
              >
                <UsersRound size={14} />
                面对面模式
              </button>
            )}
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
        <div className="mt-3 flex items-center gap-2 rounded-xl bg-sky-50/70 px-3 py-2 text-[11px] font-semibold leading-5 text-[#55708D] dark:bg-sky-400/10 dark:text-sky-100">
          <AlertCircle size={14} className="shrink-0 text-[#0EA5E9]" />
          <span className="hidden xl:inline">主页卡片：流程操作会立即保存；左键编辑阶段状态，右键标记为当前阶段。</span>
          <span className="xl:hidden">主页卡片：流程操作会立即保存；轻点编辑阶段状态，长按标记为当前阶段。</span>
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
            onRequestEdit={selectedRecord && canEditConsultationRecord(selectedRecord) ? () => openEditModal(selectedRecord) : undefined}
          />
        )}
        {flowNodeDialog && (
          <ConsultationFlowNodeDialog
            open={Boolean(flowNodeDialog)}
            stage={flowNodeDialog.stage}
            values={toConsultationFormValues(flowNodeDialog.record)}
            teacherOptions={consultationTeachers}
            setAsCurrent={flowNodeDialog.setAsCurrent}
            onClose={() => setFlowNodeDialog(null)}
            onSave={handleSaveInlineFlowNodeDialog}
          />
        )}
        {inlineEnterClassRecord && (
          <ConsultationEnterClassDialog
            open={Boolean(inlineEnterClassRecord)}
            values={toConsultationFormValues(inlineEnterClassRecord)}
            classes={classes}
            users={inlineEnterClassUsers}
            teacherBindingByClassId={{}}
            teachingTeacherUserId={(inlineEnterClassRecord as ConsultationRecord & { teaching_teacher_user_id?: number | null }).teaching_teacher_user_id ?? null}
            creating={inlineEnterClassCreating}
            createError={inlineEnterClassError}
            onClose={() => setInlineEnterClassRecord(null)}
            onExistingClass={handleInlineEnterExistingClass}
            onCreateClass={handleInlineEnterCreateClass}
            onPending={handleInlineEnterPendingClass}
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
        {overResultDialogRecord && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 px-4"
            onClick={(event) => event.target === event.currentTarget && setOverResultDialogRecord(null)}
          >
            <div className="w-full max-w-md rounded-3xl border border-sky-100 bg-white p-5 shadow-2xl dark:border-white/10 dark:bg-slate-900">
              <p className="text-base font-bold text-slate-900 dark:text-white">结束咨询</p>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-300">
                请选择这条咨询的结束结果。咨询成功需要先有进班班级或待进班记录。
              </p>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={handleInlineOverSuccess}
                  className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-left text-sm font-bold text-emerald-700 transition hover:border-emerald-300 hover:bg-emerald-100 dark:border-emerald-400/30 dark:bg-emerald-400/10 dark:text-emerald-200"
                >
                  咨询成功
                </button>
                <button
                  type="button"
                  onClick={handleInlineOverFailure}
                  className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-left text-sm font-bold text-rose-700 transition hover:border-rose-300 hover:bg-rose-100 dark:border-rose-400/30 dark:bg-rose-400/10 dark:text-rose-200"
                >
                  咨询失败
                </button>
              </div>
              <button
                type="button"
                onClick={() => setOverResultDialogRecord(null)}
                className={cn(workspaceSecondaryButtonClass, 'mt-4 w-full')}
              >
                取消
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
