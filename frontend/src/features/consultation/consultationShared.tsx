import { useEffect, useRef, useState, type MouseEvent } from 'react';
import { ArrowRight, CheckCircle2, ChevronDown } from 'lucide-react';

import type {
  ConsultationFilterKey,
  ConsultationFormValues,
  ConsultationRecord,
  ConsultationResultStage,
  ConsultationTeacherOption,
} from './consultationTypes';
import { cn } from '../../workspaceShared';
import {
  calculateConsultationFlowLights,
  cancelConsultationStage as cancelConsultationFlowStage,
  cancelConsultationOver,
  completeConsultationOver,
  completeConsultationStage as completeConsultationFlowStage,
  consultationOverStage,
  consultationProcessStages as consultationDomainProcessStages,
  createConsultationFlowState,
  setConsultationCurrentStage as setConsultationFlowCurrentStage,
  type ConsultationProcessStage,
} from '../../domain/consultationFlow';
import {
  filterConsultationTeacherOptionsForStage,
  getConsultationFlowNodeRecommendedTeacher,
  searchConsultationTeacherOptions,
} from '../../domain/consultationTeacherSelection';

export const consultationFlowStages = ['已加小客服微信', '已加对应教师微信', '正在沟通细节', '待测试', '待试听', '成功进班', '试听失败', '咨询结束'];
export const consultationProcessStages = ['已加小客服微信', '已加对应教师微信', '正在沟通细节', '待测试', '待试听'];
const consultationResultStages: ConsultationResultStage[] = ['成功进班', '试听失败'];
export const consultationMeetingVersion = 'V2.0';

export interface ConsultationFlowNodeDraft {
  teacherId: string;
  teacherName: string;
  note: string;
}

function isConsultationProcessStage(stage: string): stage is ConsultationProcessStage {
  return consultationDomainProcessStages.includes(stage as ConsultationProcessStage);
}

export const consultationFilterGroups: Array<{
  title: string;
  items: Array<{ key: ConsultationFilterKey; label: string }>;
}> = [
  {
    title: '待咨询',
    items: [
      { key: 'pending-7', label: '一周内' },
      { key: 'pending-30', label: '一月内' },
      { key: 'pending-over30', label: '30天+' },
    ],
  },
  {
    title: '已结束',
    items: [
      { key: 'ended-success', label: '咨询成功' },
      { key: 'ended-unsuccessful', label: '咨询失败' },
    ],
  },
];

export const consultationFilterLabels = consultationFilterGroups
  .flatMap((group) => group.items)
  .reduce((labels, item) => ({ ...labels, [item.key]: item.label }), {} as Record<ConsultationFilterKey, string>);

function deriveConsultationDisplayStatus(stage: string): string {
  if (stage === '成功进班' || stage === '咨询结束') return '完成';
  if (stage === '已加小客服微信' || stage === '已加对应教师微信') return '待跟进';
  return '正在跟进';
}

export function isConsultationEnded(stage: string): boolean {
  return stage === '咨询结束';
}

export function isConsultationResultStage(stage: string): stage is ConsultationResultStage {
  return consultationResultStages.includes(stage as ConsultationResultStage);
}

function getConsultationRecordDateTime(record: ConsultationRecord): number {
  const parsed = Date.parse(`${record.date || ''}T12:00:00`);
  return Number.isFinite(parsed) ? parsed : Number.POSITIVE_INFINITY;
}

function getConsultationUpdatedTime(record: ConsultationRecord): number {
  const normalized = (record.updated_at || '').replace(' ', 'T');
  const parsed = Date.parse(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function getConsultationAgeDays(record: ConsultationRecord, todayIso: string): number {
  const recordTime = getConsultationRecordDateTime(record);
  if (!Number.isFinite(recordTime)) {
    return Number.POSITIVE_INFINITY;
  }
  const todayTime = Date.parse(`${todayIso}T12:00:00`);
  return Math.max(0, Math.floor((todayTime - recordTime) / 86_400_000));
}

function consultationHasResult(record: ConsultationRecord, result: ConsultationResultStage): boolean {
  return record.flow_stage === result || (Array.isArray(record.completed_stages) && record.completed_stages.includes(result));
}

export function getConsultationFilterKey(record: ConsultationRecord, todayIso: string): ConsultationFilterKey {
  if (isConsultationEnded(record.flow_stage)) {
    if (consultationHasResult(record, '成功进班')) return 'ended-success';
    return 'ended-unsuccessful';
  }

  const ageDays = getConsultationAgeDays(record, todayIso);
  if (ageDays <= 7) return 'pending-7';
  if (ageDays <= 30) return 'pending-30';
  return 'pending-over30';
}

export function getConsultationOver30SectionLabel(record: ConsultationRecord, todayIso: string): string {
  const ageDays = getConsultationAgeDays(record, todayIso);
  if (ageDays <= 60) return '两月内';
  if (ageDays <= 180) return '半年内';
  return '半年以上';
}

export function sortConsultationsForFilter(records: ConsultationRecord[], filterKey: ConsultationFilterKey): ConsultationRecord[] {
  const sorted = [...records];
  if (filterKey.startsWith('pending-')) {
    return sorted.sort((a, b) => getConsultationRecordDateTime(a) - getConsultationRecordDateTime(b));
  }
  return sorted.sort((a, b) => getConsultationUpdatedTime(b) - getConsultationUpdatedTime(a));
}

export function toggleConsultationStageLight(values: ConsultationFormValues, stage: string): ConsultationFormValues {
  if (isConsultationEnded(values.flow_stage)) return values;
  if (!isConsultationProcessStage(stage)) return values;
  const state = createConsultationFlowState({
    flowStage: values.flow_stage,
    completedStages: values.completed_stages,
  });
  const nextState = state.completedStages.includes(stage)
    ? cancelConsultationFlowStage(state, stage)
    : completeConsultationFlowStage(state, stage);
  const preservedTerminalStages = (Array.isArray(values.completed_stages) ? values.completed_stages : [])
    .filter((item) => !isConsultationProcessStage(item) && item !== '咨询结束');
  return {
    ...values,
    flow_stage: nextState.flowStage === consultationOverStage ? '咨询结束' : nextState.flowStage,
    completed_stages: [...nextState.completedStages, ...preservedTerminalStages],
  };
}

export function moveConsultationStage(values: ConsultationFormValues, stage: string): ConsultationFormValues {
  if (isConsultationEnded(values.flow_stage)) return values;
  if (!isConsultationProcessStage(stage)) return values;
  const state = createConsultationFlowState({
    flowStage: values.flow_stage,
    completedStages: values.completed_stages,
  });
  const nextState = setConsultationFlowCurrentStage(state, stage);
  return {
    ...values,
    flow_stage: nextState.flowStage,
    completed_stages: nextState.completedStages,
  };
}

export function getConsultationFlowLightColor(values: ConsultationFormValues, stage: string): string {
  const state = createConsultationFlowState({
    flowStage: values.flow_stage,
    completedStages: values.completed_stages,
  });
  return calculateConsultationFlowLights(state).find((item) => item.stage === stage)?.color || 'white';
}

export function getConsultationTeacherInitial(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return '';
  const normalized = trimmed.replace(/老师$/, '').trim();
  if (!normalized) return '';
  const chineseMatch = normalized.match(/[\u4E00-\u9FFF]/);
  if (chineseMatch) return chineseMatch[0];
  return normalized.slice(0, 1).toUpperCase();
}

function getConsultationFlowNodeTitle(stage: string): string {
  if (stage === '已加小客服微信') return '客服微信';
  if (stage === '已加对应教师微信') return '沟通教师';
  if (stage === '正在沟通细节') return '沟通情况';
  if (stage === '待测试') return '测试';
  if (stage === '待试听') return '试听';
  return stage;
}

function getConsultationFlowNodeTeacherLabel(stage: string): string {
  if (stage === '已加小客服微信') return '客服老师';
  if (stage === '已加对应教师微信') return '沟通教师';
  if (stage === '正在沟通细节') return '沟通教师';
  if (stage === '待测试') return '测试教师';
  if (stage === '待试听') return '试听教师';
  return '负责教师';
}

export function getConsultationFlowNodeDraft(values: ConsultationFormValues, stage: string): ConsultationFlowNodeDraft {
  if (stage === '已加小客服微信') {
    return { teacherId: values.stage_teacher_ids[stage] || '', teacherName: values.customer_service_teacher, note: values.customer_service_note };
  }
  if (stage === '已加对应教师微信') {
    return { teacherId: values.stage_teacher_ids[stage] || '', teacherName: values.communication_teacher_added, note: values.communication_teacher_note };
  }
  if (stage === '正在沟通细节') {
    return { teacherId: values.stage_teacher_ids[stage] || values.teacher_id, teacherName: values.receiving_teacher, note: values.follow_up_note || values.need_detail };
  }
  if (stage === '待测试') {
    return { teacherId: values.stage_teacher_ids[stage] || '', teacherName: values.test_teacher, note: values.test_note };
  }
  if (stage === '待试听') {
    return { teacherId: values.stage_teacher_ids[stage] || '', teacherName: values.trial_teacher, note: values.trial_teacher_note };
  }
  return { teacherId: '', teacherName: '', note: '' };
}

export function buildConsultationFlowStageTeacherLabels(values: ConsultationFormValues): Record<string, string> {
  return consultationProcessStages.reduce((labels, stage) => {
    const draft = getConsultationFlowNodeDraft(values, stage);
    const teacherName = stage === '已加小客服微信'
      ? draft.teacherName || '雷老师'
      : draft.teacherName;
    return {
      ...labels,
      [stage]: getConsultationTeacherInitial(teacherName),
    };
  }, {} as Record<string, string>);
}

function applyConsultationFlowState(values: ConsultationFormValues, state: ReturnType<typeof createConsultationFlowState>): ConsultationFormValues {
  const terminalStages = (Array.isArray(values.completed_stages) ? values.completed_stages : [])
    .filter((item) => !isConsultationProcessStage(item) && item !== '咨询结束');
  return {
    ...values,
    flow_stage: state.flowStage === consultationOverStage ? '咨询结束' : state.flowStage,
    completed_stages: [...state.completedStages, ...terminalStages],
  };
}

function clearConsultationFlowNodeMappedFields(values: ConsultationFormValues, stage: string): ConsultationFormValues {
  if (!isConsultationProcessStage(stage)) return values;
  const nextValues: ConsultationFormValues = { ...values };
  if (stage === '已加小客服微信') {
    nextValues.customer_service_added = '';
    nextValues.customer_service_teacher = '';
    nextValues.customer_service_note = '';
  } else if (stage === '已加对应教师微信') {
    nextValues.communication_teacher_added = '';
    nextValues.communication_teacher_note = '';
  } else if (stage === '正在沟通细节') {
    nextValues.follow_up_note = '';
  } else if (stage === '待测试') {
    nextValues.test_taken = '';
    nextValues.test_teacher = '';
    nextValues.test_note = '';
  } else if (stage === '待试听') {
    nextValues.trial_teacher_added = '';
    nextValues.trial_teacher = '';
    nextValues.trial_teacher_note = '';
    nextValues.trial_taken = '';
  }
  const { [stage]: _removedTeacherId, ...remainingStageTeacherIds } = nextValues.stage_teacher_ids;
  nextValues.stage_teacher_ids = remainingStageTeacherIds;
  return nextValues;
}

function clearConsultationFlowNodeContentAfterStage(values: ConsultationFormValues, stage: string): ConsultationFormValues {
  if (!isConsultationProcessStage(stage)) return values;
  const targetIndex = consultationProcessStages.indexOf(stage);
  return consultationProcessStages.slice(targetIndex + 1).reduce(
    (nextValues, nextStage) => clearConsultationFlowNodeMappedFields(nextValues, nextStage),
    values,
  );
}

export function clearConsultationFlowNodeContent(values: ConsultationFormValues, stage: string): ConsultationFormValues {
  if (!isConsultationProcessStage(stage)) return values;
  const nextValues = clearConsultationFlowNodeMappedFields(values, stage);
  const state = createConsultationFlowState({
    flowStage: nextValues.flow_stage,
    completedStages: nextValues.completed_stages,
  });
  return applyConsultationFlowState(nextValues, cancelConsultationFlowStage(state, stage));
}

export function applyConsultationFlowNodeDraft(
  values: ConsultationFormValues,
  stage: string,
  draft: ConsultationFlowNodeDraft,
  setAsCurrent: boolean,
): ConsultationFormValues {
  if (!isConsultationProcessStage(stage)) return values;
  const existingDraft = getConsultationFlowNodeDraft(values, stage);
  const teacherName = draft.teacherName.trim();
  const nextValues: ConsultationFormValues = {
    ...values,
    stage_teacher_ids: {
      ...values.stage_teacher_ids,
      [stage]: draft.teacherId,
    },
  };
  if (stage === '已加小客服微信') {
    nextValues.customer_service_added = '已添加';
    nextValues.customer_service_teacher = teacherName;
    nextValues.customer_service_note = draft.note;
  } else if (stage === '已加对应教师微信') {
    nextValues.communication_teacher_added = teacherName;
    nextValues.communication_teacher_note = draft.note;
  } else if (stage === '正在沟通细节') {
    nextValues.teacher_id = draft.teacherId;
    nextValues.receiving_teacher = teacherName || values.receiving_teacher;
    nextValues.follow_up_status = '跟进中';
    nextValues.follow_up_note = draft.note;
  } else if (stage === '待测试') {
    nextValues.test_taken = '是';
    nextValues.test_teacher = teacherName;
    nextValues.test_note = draft.note;
  } else if (stage === '待试听') {
    nextValues.trial_teacher_added = teacherName ? '已添加' : nextValues.trial_teacher_added;
    nextValues.trial_teacher = teacherName;
    nextValues.trial_teacher_note = draft.note;
    nextValues.trial_taken = nextValues.trial_taken || '是';
  }
  if (existingDraft.teacherId && draft.teacherId && existingDraft.teacherId !== draft.teacherId) {
    nextValues.assignment_note = draft.note.trim() || `${existingDraft.teacherName || existingDraft.teacherId} 转交给 ${teacherName || draft.teacherId}`;
  }
  const cleanedValues = setAsCurrent ? clearConsultationFlowNodeContentAfterStage(nextValues, stage) : nextValues;
  const state = createConsultationFlowState({
    flowStage: cleanedValues.flow_stage,
    completedStages: cleanedValues.completed_stages,
  });
  const nextState = setAsCurrent
    ? setConsultationFlowCurrentStage(state, stage)
    : completeConsultationFlowStage(state, stage);
  return applyConsultationFlowState(cleanedValues, nextState);
}

export function setConsultationResultStage(values: ConsultationFormValues, stage: ConsultationResultStage): ConsultationFormValues {
  if (isConsultationEnded(values.flow_stage)) return values;
  const currentStages = Array.isArray(values.completed_stages) ? values.completed_stages : [];
  const withoutResult = currentStages.filter((item) => !isConsultationResultStage(item));
  return { ...values, flow_stage: stage, completed_stages: [...withoutResult, stage] };
}

export function clearConsultationResultStage(values: ConsultationFormValues): ConsultationFormValues {
  if (isConsultationEnded(values.flow_stage)) return values;
  const completed_stages = (Array.isArray(values.completed_stages) ? values.completed_stages : [])
    .filter((item) => !isConsultationResultStage(item));
  const flow_stage = isConsultationResultStage(values.flow_stage)
    ? completed_stages[completed_stages.length - 1] || consultationFlowStages[0]
    : values.flow_stage;
  return { ...values, flow_stage, completed_stages };
}

export function endConsultationValues(values: ConsultationFormValues): ConsultationFormValues {
  return completeConsultationOverValues(values, values.closing_result === 'success' ? 'success' : 'failed');
}

export function completeConsultationOverValues(values: ConsultationFormValues, result: 'success' | 'failed'): ConsultationFormValues {
  const preservedResultStages = (Array.isArray(values.completed_stages) ? values.completed_stages : [])
    .filter(isConsultationResultStage);
  const state = createConsultationFlowState({
    flowStage: isConsultationEnded(values.flow_stage) ? consultationOverStage : values.flow_stage,
    completedStages: values.completed_stages,
    closingResult: result,
  });
  const nextState = completeConsultationOver(state, result);
  const completed_stages = Array.from(new Set([...nextState.completedStages, ...preservedResultStages, '咨询结束']));
  return {
    ...values,
    flow_stage: '咨询结束',
    completed_stages,
    closing_result: result,
  };
}

export function restoreConsultationValues(values: ConsultationFormValues): ConsultationFormValues {
  const completed_stages = (Array.isArray(values.completed_stages) ? values.completed_stages : [])
    .filter((item) => item !== '咨询结束');
  const state = createConsultationFlowState({
    flowStage: consultationOverStage,
    completedStages: completed_stages,
    closingResult: values.closing_result,
  });
  const restoredState = cancelConsultationOver(state);
  const flow_stage = restoredState.flowStage === consultationOverStage
    ? completed_stages[completed_stages.length - 1] || consultationFlowStages[0]
    : restoredState.flowStage;
  return {
    ...values,
    flow_stage,
    completed_stages,
    closing_result: '',
    restore_from_end: true,
  } as ConsultationFormValues;
}

export function normalizeConsultationRecord(record: ConsultationRecord): ConsultationRecord {
  return {
    ...record,
    date: record.date ?? '',
    parent_wechat_name: record.parent_wechat_name ?? '',
    child_name: record.child_name ?? '',
    grade: record.grade ?? '',
    receiving_teacher: record.receiving_teacher ?? '',
    teacher_id: record.teacher_id ?? '',
    consultation_subject: record.consultation_subject ?? '',
    need_detail: record.need_detail ?? '',
    source_channel: record.source_channel ?? '',
    source_channel_note: record.source_channel_note ?? '',
    screenshot: record.screenshot ?? '',
    follow_up_status: record.follow_up_status ?? '',
    follow_up_note: record.follow_up_note ?? '',
    flow_stage: record.flow_stage || consultationFlowStages[0],
    completed_stages: Array.isArray(record.completed_stages) ? record.completed_stages : [],
    stage_teacher_ids: record.stage_teacher_ids && typeof record.stage_teacher_ids === 'object' ? record.stage_teacher_ids : {},
    assigned_stage: record.assigned_stage ?? '',
    assignment_note: record.assignment_note ?? '',
    is_transferred_consultation: Boolean(record.is_transferred_consultation),
    can_edit_consultation: record.can_edit_consultation !== false,
    transfer_marker: record.transfer_marker ?? '',
    current_responsibility: record.current_responsibility ?? '',
    customer_service_added: record.customer_service_added ?? '',
    customer_service_teacher: record.customer_service_teacher ?? '',
    customer_service_note: record.customer_service_note ?? '',
    communication_teacher_added: record.communication_teacher_added ?? '',
    communication_teacher_note: record.communication_teacher_note ?? '',
    test_taken: record.test_taken ?? '',
    test_teacher: record.test_teacher ?? '',
    test_note: record.test_note ?? '',
    test_images: Array.isArray(record.test_images) ? record.test_images : [],
    trial_teacher_added: record.trial_teacher_added ?? '',
    trial_teacher_note: record.trial_teacher_note ?? '',
    trial_taken: record.trial_taken ?? '',
    trial_time_slot: record.trial_time_slot ?? '',
    trial_class_id: record.trial_class_id ?? null,
    trial_class_manual: record.trial_class_manual ?? '',
    trial_teacher: record.trial_teacher ?? '',
    trial_feedback: record.trial_feedback ?? '',
    success_class_id: record.success_class_id ?? null,
    teaching_teacher_added: record.teaching_teacher_added ?? '',
    teaching_teacher: record.teaching_teacher ?? '',
    teaching_teacher_note: record.teaching_teacher_note ?? '',
    success_class_manual: record.success_class_manual ?? '',
    closing_result: record.closing_result ?? '',
    end_note: record.end_note ?? '',
    ended_at: record.ended_at ?? '',
    created_at: record.created_at ?? '',
    updated_at: record.updated_at ?? '',
  };
}

function normalizeTeacherLookupKey(value: string): string {
  return value.trim().toLowerCase();
}

function isTeacherDisplayName(value: string): boolean {
  const normalized = value.trim();
  if (!normalized) {
    return false;
  }
  if (/老师|主任|校长|顾问/.test(normalized)) {
    return true;
  }
  if (/[\u4e00-\u9fff]/.test(normalized)) {
    return true;
  }
  return !/^[a-z0-9_.-]{4,}$/i.test(normalized);
}

export function buildConsultationTeacherDirectory(records: ConsultationRecord[]): Record<string, string> {
  const directory: Record<string, string> = {};

  for (const record of records) {
    const receivingTeacher = record.receiving_teacher?.trim() || '';
    const teacherId = record.teacher_id?.trim() || '';
    const displayName = isTeacherDisplayName(receivingTeacher)
      ? receivingTeacher
      : isTeacherDisplayName(teacherId)
        ? teacherId
        : '';

    if (!displayName) {
      continue;
    }

    for (const key of [receivingTeacher, teacherId]) {
      const normalizedKey = normalizeTeacherLookupKey(key);
      if (normalizedKey) {
        directory[normalizedKey] = displayName;
      }
    }
  }

  return directory;
}

export function getConsultationTeacherName(record: ConsultationRecord, teacherDirectory: Record<string, string>): string {
  const teacherDisplayName = record.teacher_display_name?.trim() || '';
  const receivingTeacher = record.receiving_teacher?.trim() || '';
  const teacherId = record.teacher_id?.trim() || '';

  if (teacherDisplayName) {
    return teacherDisplayName;
  }

  for (const candidate of [receivingTeacher, teacherId]) {
    if (isTeacherDisplayName(candidate)) {
      return candidate;
    }
  }

  for (const candidate of [receivingTeacher, teacherId]) {
    const mappedName = teacherDirectory[normalizeTeacherLookupKey(candidate)];
    if (mappedName) {
      return mappedName;
    }
  }

  return receivingTeacher || teacherId || '待分配老师';
}

export function getConsultationSourceLabel(record: ConsultationRecord): string {
  const sourceChannel = record.source_channel || '未标注来源渠道';
  const trimmedSourceChannel = sourceChannel.trim();
  const sourceChannelNote = record.source_channel_note?.trim();
  if (trimmedSourceChannel === '未标注来源渠道') {
    return trimmedSourceChannel;
  }
  return sourceChannelNote ? `${trimmedSourceChannel} · ${sourceChannelNote}` : trimmedSourceChannel;
}

export const consultationSurfaceClass =
  'border border-[#D9EEF7] bg-white dark:border-white/10 dark:bg-slate-950/78';
export const consultationPanelClass =
  'rounded-[14px] border border-[#D9EEF7] bg-white dark:border-white/10 dark:bg-slate-950/72';
export const consultationLabelClass =
  'consultation-field-label text-[11px] font-bold leading-4 text-[#7188A6] dark:text-slate-300';
export const consultationValueClass =
  'consultation-field-value mt-0.5 min-w-0 break-words text-[13px] font-semibold leading-5 text-[#1F2A44] dark:text-slate-100';
export const consultationInputClass =
  'consultation-field-input w-full rounded-lg border border-[#BFE5F8] bg-white px-3 py-2 text-sm text-[#1F2A44] outline-none transition placeholder:text-[#9AAEC4] focus:border-[#0EA5E9] focus:ring-3 focus:ring-sky-100 disabled:bg-[#F6FAFD] disabled:text-[#7188A6] dark:border-white/10 dark:bg-slate-900/75 dark:text-slate-100 dark:focus:border-sky-400 dark:focus:ring-sky-500/15';

export const consultationStageDisplayLabel = (stage: string) => {
  if (stage === '已加小客服微信') return '客服微信✅';
  if (stage === '已加对应教师微信') return '教师微信✅';
  if (stage === '正在沟通细节') return '沟通ing';
  if (stage === '待测试') return '待测试';
  if (stage === '待试听') return '待试听';
  return stage;
};

export const consultationStageShortLabel = (stage: string) => {
  if (stage === '已加小客服微信') return '客服';
  if (stage === '已加对应教师微信') return '教师';
  if (stage === '正在沟通细节') return '沟通';
  if (stage === '待测试') return '测';
  if (stage === '待试听') return '听';
  return stage;
};

export const consultationResultShortLabel = (stage: string) => {
  if (stage === '成功进班') return '进';
  if (stage === '试听失败') return '败';
  return '';
};

export const ConsultationStatusLamp = ({ stage }: { stage: string }) => {
  const status = deriveConsultationDisplayStatus(stage);
  const lampClass = stage === '咨询结束'
    ? 'bg-rose-500'
    : status === '正在跟进'
      ? 'bg-emerald-500'
      : 'bg-slate-400';
  return <span className={`inline-block h-2 w-2 rounded-full ${lampClass}`} title={status} aria-label={status} />;
};

export const ConsultationFlowNodeDialog = ({
  open,
  stage,
  values,
  teacherOptions,
  setAsCurrent,
  onClose,
  onSave,
}: {
  open: boolean;
  stage: string;
  values: ConsultationFormValues;
  teacherOptions: ConsultationTeacherOption[];
  setAsCurrent: boolean;
  onClose: () => void;
  onSave: (draft: ConsultationFlowNodeDraft) => void;
}) => {
  const stageTeacherOptions = filterConsultationTeacherOptionsForStage(stage, teacherOptions);
  const savedDraft = getConsultationFlowNodeDraft(values, stage);
  const recommendedTeacher = getConsultationFlowNodeRecommendedTeacher(stage, values, stageTeacherOptions);
  const initialTeacherId = savedDraft.teacherId || recommendedTeacher.teacherId;
  const initialTeacherName = savedDraft.teacherName || recommendedTeacher.teacherName;
  const [selectedTeacherId, setSelectedTeacherId] = useState(initialTeacherId);
  const [teacherName, setTeacherName] = useState(initialTeacherName);
  const [note, setNote] = useState(savedDraft.note);
  const [teacherSearch, setTeacherSearch] = useState('');

  useEffect(() => {
    if (!open) return;
    setSelectedTeacherId(initialTeacherId);
    setTeacherName(initialTeacherName);
    setNote(savedDraft.note);
    setTeacherSearch('');
  }, [open, initialTeacherId, initialTeacherName, savedDraft.note]);

  if (!open) return null;

  const stageTitle = getConsultationFlowNodeTitle(stage);
  const teacherLabel = getConsultationFlowNodeTeacherLabel(stage);
  const studentSummary = `${values.child_name || '未填写学生'} / ${values.consultation_subject || '未填写科目'} / ${values.grade || '未填写年级'}`;
  const selectedTeacher = stageTeacherOptions.find((option) => option.teacher_id === selectedTeacherId);
  const displayTeacherName = teacherName || selectedTeacher?.display_name || '';
  const teacherSelected = Boolean(displayTeacherName.trim());
  const filteredTeacherOptions = searchConsultationTeacherOptions(stageTeacherOptions, teacherSearch);

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/35 px-4" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="w-full max-w-lg rounded-[18px] border border-[#D9EEF7] bg-white p-5 shadow-[0_24px_70px_rgba(31,42,68,0.22)] dark:border-white/10 dark:bg-slate-950">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.24em] text-[#0EA5E9]">Flow Node</p>
            <h3 className="mt-1 text-xl font-extrabold text-[#1F2A44] dark:text-white">{stageTitle}</h3>
            <p className="mt-1 text-sm text-[#7188A6] dark:text-slate-400">{studentSummary}</p>
          </div>
          <button type="button" onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-full bg-[#F1F9FE] text-[#7188A6] hover:bg-sky-100 dark:bg-white/5 dark:text-slate-300">
            ×
          </button>
        </div>

        {setAsCurrent ? (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-700 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-200">
            保存后会把后续阶段恢复为空白。
          </div>
        ) : null}

        <div className="mt-4 space-y-3">
          <div className={`rounded-xl border px-3 py-3 transition ${
            teacherSelected
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-300'
              : 'border-[#D9EEF7] bg-[#F9FDFF] text-[#7188A6] dark:border-white/10 dark:bg-white/[0.03] dark:text-slate-400'
          }`}>
            <div className="flex items-center justify-between gap-3">
              <p className="min-w-0 truncate text-sm font-extrabold">{teacherLabel}：{displayTeacherName || '未选择'}</p>
              {teacherSelected ? <CheckCircle2 size={18} className="shrink-0" /> : null}
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
              <input
                value={teacherSearch}
                onChange={(event) => setTeacherSearch(event.target.value)}
                className="rounded-lg border border-[#BFE5F8] bg-white px-3 py-2 text-sm outline-none focus:border-[#0EA5E9] dark:border-white/10 dark:bg-slate-900"
                placeholder="筛选老师"
              />
              <select
                value={selectedTeacherId}
                onChange={(event) => {
                  const selected = stageTeacherOptions.find((option) => option.teacher_id === event.target.value);
                  setSelectedTeacherId(event.target.value);
                  setTeacherName(selected?.display_name || '');
                }}
                className="rounded-lg border border-[#BFE5F8] bg-white px-3 py-2 text-sm outline-none focus:border-[#0EA5E9] dark:border-white/10 dark:bg-slate-900"
              >
                <option value="">请选择老师</option>
                {filteredTeacherOptions.map((option) => (
                  <option key={option.teacher_id} value={option.teacher_id}>{option.display_name}</option>
                ))}
              </select>
            </div>
          </div>

          <label className="block space-y-2">
            <span className="text-[11px] font-bold leading-4 text-[#7188A6] dark:text-slate-300">阶段备注</span>
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={4}
              className="w-full resize-none rounded-lg border border-[#BFE5F8] bg-white px-3 py-2 text-sm outline-none focus:border-[#0EA5E9] dark:border-white/10 dark:bg-slate-900"
              placeholder="记录这个环节的沟通情况、测试安排或试听反馈"
            />
          </label>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3">
          <button type="button" onClick={onClose} className="inline-flex items-center justify-center rounded-xl border border-[#D9EEF7] bg-white px-4 py-3 text-sm font-bold text-[#1F2A44] hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-100">
            取消
          </button>
          <button
            type="button"
            onClick={() => onSave({ teacherId: selectedTeacherId, teacherName: displayTeacherName, note })}
            className="inline-flex items-center justify-center rounded-xl bg-[#0EA5E9] px-4 py-3 text-sm font-bold text-white hover:bg-sky-500"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
};

export const ConsultationResultCapsule = ({
  stage,
  completedStages,
  blockedByCurrentProcess = false,
  compact = false,
  editable,
  onResultChange,
  onResultClick,
  onResultDoubleClick,
  showJumpAction = false,
  useResponsiveShortLabel = false,
  onJump,
}: {
  stage: string;
  completedStages: string[];
  blockedByCurrentProcess?: boolean;
  compact?: boolean;
  editable: boolean;
  onResultChange?: (stage: ConsultationResultStage) => void;
  onResultClick?: () => void;
  onResultDoubleClick?: () => void;
  showJumpAction?: boolean;
  useResponsiveShortLabel?: boolean;
  onJump?: () => void;
}) => {
  const completedResultStage = (completedStages || []).find(isConsultationResultStage) || '';
  const resultStage = isConsultationResultStage(stage) ? stage : completedResultStage;
  const active = isConsultationResultStage(stage);
  const completed = Boolean(completedResultStage) && !blockedByCurrentProcess;
  const resultLabel = resultStage === '试听失败' ? '😢 试听未成' : '☀️ 成功进班';
  const resultShortLabel = consultationResultShortLabel(resultStage);
  const useShortLabel = compact || useResponsiveShortLabel;
  return (
    <div
      title={resultStage || '成功进班'}
      className={`relative flex min-w-0 items-center overflow-hidden rounded-[10px] text-center font-extrabold leading-none transition ${compact ? 'h-8 text-[10px]' : 'h-[42px] text-xs'} ${editable ? 'hover:-translate-y-0.5' : ''} ${
        active
          ? 'bg-sky-500 text-white'
          : completed
            ? 'border border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200'
            : 'bg-slate-100 text-slate-400 dark:bg-white/5 dark:text-slate-500'
      }`}
    >
      <button
        type="button"
        disabled={!editable}
        onClick={onResultClick}
        onDoubleClick={onResultDoubleClick}
        className={`min-w-0 overflow-hidden text-ellipsis ${showJumpAction ? 'flex-[1_1_76%] pl-3 pr-1' : 'flex-1'} ${compact ? 'px-0.5' : 'px-2'} ${editable ? 'cursor-pointer' : 'cursor-default'}`}
      >
        {useShortLabel ? (
          <>
            <span className="hidden min-[720px]:inline">{resultLabel}</span>
            <span className="min-[720px]:hidden">{resultShortLabel}</span>
          </>
        ) : (
          resultLabel
        )}
      </button>
      {showJumpAction ? (
        <div className="flex h-full basis-[24%] shrink-0 items-stretch">
          <button
            type="button"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onJump?.();
            }}
            className="flex flex-1 items-center justify-center bg-white/60 text-slate-500 transition hover:bg-white hover:text-sky-600 dark:bg-slate-900/50 dark:text-slate-300 dark:hover:bg-slate-800"
            aria-label="跳转到结果编辑栏"
            title="跳转到结果编辑栏"
          >
            <ArrowRight size={compact ? 10 : 12} />
          </button>
          <div className="relative flex flex-1 items-center justify-center text-current opacity-80">
            <ChevronDown size={compact ? 11 : 13} className="pointer-events-none" />
            <select
              value={resultStage}
              disabled={!editable}
              onClick={(event) => event.stopPropagation()}
              onChange={(event) => {
                const value = event.target.value as ConsultationResultStage | '';
                if (value) onResultChange?.(value);
              }}
              className="absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-default"
              aria-label="选择咨询结果"
              title="选择咨询结果"
            >
              <option value="">未选择结果</option>
              <option value="成功进班">☀️ 成功进班</option>
              <option value="试听失败">😢 试听未成</option>
            </select>
          </div>
        </div>
      ) : (
        <div className={`absolute right-1 top-1/2 flex ${compact ? 'h-6 w-6' : 'h-8 w-8'} -translate-y-1/2 items-center justify-center text-current opacity-80`}>
          <ChevronDown size={compact ? 11 : 13} className="pointer-events-none" />
          <select
            value={resultStage}
            disabled={!editable}
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => {
              const value = event.target.value as ConsultationResultStage | '';
              if (value) onResultChange?.(value);
            }}
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-default"
            aria-label="选择咨询结果"
            title="选择咨询结果"
          >
            <option value="">未选择结果</option>
            <option value="成功进班">☀️ 成功进班</option>
            <option value="试听失败">😢 试听未成</option>
          </select>
        </div>
      )}
    </div>
  );
};

export const ConsultationFlowBar = ({
  stage,
  completedStages,
  mode = 'full',
  editable = false,
  showJumpActions = false,
  showOver = false,
  overDisabled = false,
  closingResult = '',
  stageTeacherLabels,
  onStageClick,
  onStageContextMenu,
  onStageLongPress,
  onResultChange,
  onResultClick,
  onResultDoubleClick,
  onStageJump,
  onOverClick,
  onOverDoubleClick,
}: {
  stage: string;
  completedStages: string[];
  mode?: 'list' | 'full';
  editable?: boolean;
  showJumpActions?: boolean;
  showOver?: boolean;
  overDisabled?: boolean;
  closingResult?: string;
  stageTeacherLabels?: Record<string, string>;
  onStageClick?: (stage: string) => void;
  onStageContextMenu?: (stage: string) => void;
  onStageLongPress?: (stage: string) => void;
  onResultChange?: (stage: ConsultationResultStage) => void;
  onResultClick?: () => void;
  onResultDoubleClick?: () => void;
  onStageJump?: (stage: string) => void;
  onOverClick?: () => void;
  onOverDoubleClick?: () => void;
}) => {
  const currentStage = stage || consultationFlowStages[0];
  const ended = isConsultationEnded(currentStage);
  const compact = mode === 'list';
  const longPressTimerRef = useRef<number | null>(null);
  const longPressTriggeredRef = useRef(false);
  const completedResultStage = (completedStages || []).find(isConsultationResultStage) || '';
  const resultStage = isConsultationResultStage(currentStage) ? currentStage : completedResultStage;
  const resultActive = isConsultationResultStage(currentStage);
  const flowStateStage = ended
    ? consultationOverStage
    : resultActive
      ? consultationOverStage
      : currentStage;
  const terminalClosingResult = closingResult === 'failed'
    ? 'failed'
    : closingResult === 'success' || currentStage === '成功进班'
      ? 'success'
      : ended || currentStage === '试听失败'
        ? 'failed'
        : '';
  const flowState = createConsultationFlowState({
    flowStage: flowStateStage,
    completedStages,
    closingResult: terminalClosingResult,
  });
  const lightByStage = Object.fromEntries(
    calculateConsultationFlowLights(flowState).map((light) => [light.stage, light.color]),
  );
  const currentProcessIndex = consultationProcessStages.indexOf(flowState.flowStage);
  const resultCompleted = Boolean(completedResultStage) && currentProcessIndex < 0;
  const resultLabel = resultStage === '试听失败' ? '咨询失败' : '进班';
  const resultShortLabel = consultationResultShortLabel(resultStage) || '进';
  const clearLongPressTimer = () => {
    if (longPressTimerRef.current !== null) {
      window.clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  };
  const flowNodes = [
    ...consultationProcessStages.map((item) => {
      const lightColor = lightByStage[item] || 'white';
      return {
        key: item,
        type: 'process' as const,
        label: consultationStageDisplayLabel(item).replace('微信✅', ''),
        shortLabel: consultationStageShortLabel(item),
        title: item,
        teacherLabel: stageTeacherLabels?.[item] || '',
        active: lightColor === 'blue',
        completed: lightColor === 'green',
        lightColor,
        disabled: !editable || ended,
      };
    }),
    {
      key: 'consultation-result',
      type: 'result' as const,
      label: resultLabel,
      shortLabel: resultShortLabel,
      title: resultStage || '成功进班',
      teacherLabel: '',
      active: resultActive,
      completed: resultCompleted,
      lightColor: resultActive ? lightByStage[consultationOverStage] || 'blue' : resultCompleted ? 'green' : 'white',
      disabled: !editable || ended,
    },
    ...(showOver ? [{
      key: 'consultation-over',
      type: 'over' as const,
      label: 'OVER',
      shortLabel: 'OVER',
      title: '咨询结束',
      teacherLabel: '',
      active: ended,
      completed: ended,
      lightColor: ended ? lightByStage[consultationOverStage] || 'blue' : 'white',
      disabled: overDisabled,
    }] : []),
  ];
  const gridClass = showOver
    ? compact
      ? 'grid-cols-[repeat(7,minmax(1.55rem,1fr))] min-[520px]:grid-cols-[repeat(7,minmax(2.9rem,1fr))]'
      : 'grid-cols-[repeat(7,minmax(0,1fr))]'
    : compact
      ? 'grid-cols-[repeat(6,minmax(1.75rem,1fr))] min-[520px]:grid-cols-[repeat(6,minmax(3.85rem,1fr))]'
      : 'grid-cols-[repeat(6,minmax(0,1fr))]';
  const getNodeCircleClass = (node: typeof flowNodes[number]) => {
    const lightColor = node.lightColor;
    if (lightColor === 'blue') {
      return 'border-[#0EA5E9] bg-[#0EA5E9] text-white';
    }
    if (lightColor === 'green') {
      return 'border-[#22B981] bg-[#22B981] text-white';
    }
    if (lightColor === 'red') {
      return 'border-[#E11D48] bg-[#E11D48] text-white shadow-md shadow-rose-200 ring-2 ring-rose-100 dark:ring-rose-400/20';
    }
    if (node.type === 'over') {
      return 'border-[#F43F5E]/60 bg-white text-transparent dark:bg-slate-950';
    }
    return 'border-[#C7DDEA] bg-white text-transparent dark:bg-slate-950';
  };
  const getNodeTextClass = (node: typeof flowNodes[number]) => {
    if (node.type === 'over') return node.active ? 'text-[#F45B7A]' : 'text-[#7188A6]';
    if (node.active) return 'text-[#0EA5E9]';
    if (node.completed) return 'text-[#0A8F65]';
    return 'text-[#7188A6]';
  };
  const getConnectorClass = (node: typeof flowNodes[number], next?: typeof flowNodes[number]) => {
    if (!next) return '';
    if (node.type === 'over' || next.type === 'over') {
      return ended ? 'bg-[#F45B7A]/55' : 'bg-[#D9EEF7]';
    }
    if (node.completed && next.completed) return 'bg-[#22B981]';
    if (node.completed && next.active) return 'bg-[#0EA5E9]';
    return 'bg-[#D9EEF7]';
  };
  return (
    <div className={`grid w-full min-w-0 ${gridClass} ${compact ? 'gap-0.5' : 'gap-1'}`}>
      {flowNodes.map((node, index) => {
        const nextNode = flowNodes[index + 1];
        const circleText = node.type === 'over'
          ? node.lightColor === 'red' ? '!' : ''
          : node.active || node.completed
            ? node.teacherLabel || (node.type === 'result' ? node.shortLabel : '')
            : '';
        const handlePrimaryClick = () => {
          if (longPressTriggeredRef.current) {
            longPressTriggeredRef.current = false;
            return;
          }
          if (node.type === 'process') onStageClick?.(node.key);
          if (node.type === 'result') onResultClick?.();
          if (node.type === 'over') onOverClick?.();
        };
        const handlePrimaryContextMenu = (event: MouseEvent<HTMLButtonElement>) => {
          if (node.disabled || node.type !== 'process') return;
          event.preventDefault();
          onStageContextMenu?.(node.key);
        };
        const handlePrimaryTouchStart = () => {
          if (node.disabled || node.type !== 'process') return;
          clearLongPressTimer();
          longPressTriggeredRef.current = false;
          longPressTimerRef.current = window.setTimeout(() => {
            longPressTriggeredRef.current = true;
            onStageLongPress?.(node.key);
          }, 550);
        };
        const handlePrimaryTouchEnd = () => {
          clearLongPressTimer();
        };
        return (
          <div key={node.key} className="group relative min-w-0">
            {nextNode && (
              <span
                className={`absolute left-1/2 right-[-50%] ${compact ? 'top-[0.58rem]' : 'top-[0.68rem]'} h-px ${getConnectorClass(node, nextNode)}`}
                aria-hidden="true"
              />
            )}
            <button
              type="button"
              disabled={node.disabled}
              onClick={handlePrimaryClick}
              onContextMenu={handlePrimaryContextMenu}
              onTouchStart={handlePrimaryTouchStart}
              onTouchEnd={handlePrimaryTouchEnd}
              onTouchCancel={clearLongPressTimer}
              title={node.title}
              className={`relative z-10 flex w-full min-w-0 flex-col items-center gap-0.5 rounded-lg ${compact ? 'min-h-9 py-0.5' : 'min-h-11 py-1'} text-center transition ${node.disabled ? 'cursor-default' : 'hover:bg-sky-50/70 dark:hover:bg-white/5'}`}
            >
              <span className={`${compact ? 'h-[18px] w-[18px] text-[10px]' : 'h-[21px] w-[21px] text-[11px]'} flex items-center justify-center rounded-full border font-extrabold leading-none ${getNodeCircleClass(node)}`}>
                {circleText}
              </span>
              <span className={`block w-full truncate whitespace-nowrap ${compact ? 'text-[10px]' : 'text-[11px]'} font-extrabold leading-4 ${getNodeTextClass(node)}`}>
                <>
                  <span className={compact ? 'hidden min-[520px]:inline' : 'hidden min-[720px]:inline'}>{node.label}</span>
                  <span className={compact ? 'min-[520px]:hidden' : 'min-[720px]:hidden'}>{node.shortLabel}</span>
                </>
              </span>
            </button>
            {node.type === 'result' && (
              <div className={`absolute right-0 top-0 z-20 flex ${compact ? 'h-5 w-5' : 'h-6 w-6'} items-center justify-center rounded-full bg-white/80 text-[#7188A6] dark:bg-slate-900/80`}>
                <ChevronDown size={compact ? 10 : 11} className="pointer-events-none" />
                <select
                  value={resultStage}
                  disabled={node.disabled}
                  onClick={(event) => event.stopPropagation()}
                  onChange={(event) => {
                    const value = event.target.value as ConsultationResultStage | '';
                    if (value) onResultChange?.(value);
                  }}
                  className="absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-default"
                  aria-label="选择咨询结果"
                  title="选择咨询结果"
                >
                  <option value="">未选择结果</option>
                  <option value="成功进班">☀️ 成功进班</option>
                  <option value="试听失败">😢 试听未成</option>
                </select>
              </div>
            )}
            {showJumpActions && node.type !== 'over' && (
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onStageJump?.(node.type === 'result' ? (isConsultationResultStage(currentStage) ? currentStage : '成功进班') : node.key);
                }}
                className="absolute left-1/2 top-0 z-20 flex h-4 w-4 -translate-x-1/2 -translate-y-1 items-center justify-center rounded-full bg-white text-[#7188A6] opacity-0 transition hover:text-[#0EA5E9] focus:opacity-100 group-hover:opacity-100 dark:bg-slate-900"
                aria-label={`跳转到${node.title}编辑栏`}
                title={`跳转到${node.title}编辑栏`}
              >
                <ArrowRight size={9} />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
};

export const ConsultationCardExpandableText = ({
  label,
  text,
  lines = 1,
}: {
  label: string;
  text?: string | null;
  lines?: 1 | 2;
}) => {
  const [expanded, setExpanded] = useState(false);
  const [canToggle, setCanToggle] = useState(false);
  const textRef = useRef<HTMLParagraphElement | null>(null);
  const content = text?.trim();

  useEffect(() => {
    setExpanded(false);
    setCanToggle(false);
  }, [content]);

  useEffect(() => {
    if (!content || expanded) return undefined;
    const element = textRef.current;
    if (!element) return undefined;
    let frame = window.requestAnimationFrame(() => {
      setCanToggle(element.scrollHeight > element.clientHeight + 1);
    });
    const measure = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        setCanToggle(element.scrollHeight > element.clientHeight + 1);
      });
    };
    window.addEventListener('resize', measure);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener('resize', measure);
    };
  }, [content, expanded, lines]);

  if (!content) return null;

  return (
    <div className="relative min-w-0">
      <p
        ref={textRef}
        className={cn(
          'min-w-0 whitespace-pre-wrap break-words text-[13px] leading-5 text-[#7188A6] dark:text-slate-400',
          canToggle ? 'pr-16' : '',
          !expanded ? (lines === 2 ? 'line-clamp-2' : 'line-clamp-1') : '',
        )}
      >
        <span className="font-semibold text-[#7188A6] dark:text-slate-300">{label}：</span>
        {content}
      </p>
      {canToggle && (
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="absolute bottom-0 right-0 bg-white pl-1 text-[11px] font-extrabold leading-5 text-[#0EA5E9] transition hover:text-sky-700 dark:bg-slate-950"
        >
          {expanded ? '收起' : '展开全文'}
        </button>
      )}
    </div>
  );
};
