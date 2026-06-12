import { useEffect, useRef, useState } from 'react';
import { ArrowRight, ChevronDown } from 'lucide-react';

import type {
  ConsultationFilterKey,
  ConsultationFormValues,
  ConsultationRecord,
  ConsultationResultStage,
} from '../../App';
import { cn } from '../../workspaceShared';

export const consultationFlowStages = ['已加小客服微信', '已加对应教师微信', '正在沟通细节', '待测试', '待试听', '成功进班', '试听失败', '咨询结束'];
export const consultationProcessStages = ['已加小客服微信', '已加对应教师微信', '正在沟通细节', '待测试', '待试听'];
const consultationResultStages: ConsultationResultStage[] = ['成功进班', '试听失败'];
export const consultationMeetingVersion = 'V2.0';

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
  const currentStages = Array.isArray(values.completed_stages) ? values.completed_stages : [];
  const exists = currentStages.includes(stage);
  const completed_stages = exists
    ? currentStages.filter((item) => item !== stage)
    : [...currentStages, stage];
  const flow_stage = exists && values.flow_stage === stage
    ? completed_stages[completed_stages.length - 1] || consultationFlowStages[0]
    : values.flow_stage || stage;
  return { ...values, flow_stage, completed_stages };
}

export function moveConsultationStage(values: ConsultationFormValues, stage: string): ConsultationFormValues {
  if (isConsultationEnded(values.flow_stage)) return values;
  const currentStages = Array.isArray(values.completed_stages) ? values.completed_stages : [];
  const completed_stages = currentStages.includes(stage) ? currentStages : [...currentStages, stage];
  return { ...values, flow_stage: stage, completed_stages };
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
  const currentStages = Array.isArray(values.completed_stages) ? values.completed_stages : [];
  const withCurrentStage = values.flow_stage && values.flow_stage !== '咨询结束' && !currentStages.includes(values.flow_stage)
    ? [...currentStages, values.flow_stage]
    : currentStages;
  return {
    ...values,
    flow_stage: '咨询结束',
    completed_stages: withCurrentStage.includes('咨询结束') ? withCurrentStage : [...withCurrentStage, '咨询结束'],
  };
}

export function restoreConsultationValues(values: ConsultationFormValues): ConsultationFormValues {
  const completed_stages = (Array.isArray(values.completed_stages) ? values.completed_stages : [])
    .filter((item) => item !== '咨询结束');
  const flow_stage = completed_stages[completed_stages.length - 1] || consultationFlowStages[0];
  return {
    ...values,
    flow_stage,
    completed_stages,
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
    test_taken: record.test_taken ?? '',
    test_images: Array.isArray(record.test_images) ? record.test_images : [],
    trial_taken: record.trial_taken ?? '',
    trial_time_slot: record.trial_time_slot ?? '',
    trial_class_id: record.trial_class_id ?? null,
    trial_class_manual: record.trial_class_manual ?? '',
    trial_teacher: record.trial_teacher ?? '',
    trial_feedback: record.trial_feedback ?? '',
    success_class_id: record.success_class_id ?? null,
    success_class_manual: record.success_class_manual ?? '',
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
  'border border-[#D9EEF7] bg-white shadow-[0_10px_28px_rgba(31,42,68,0.05)] dark:border-white/10 dark:bg-slate-950/78';
export const consultationPanelClass =
  'rounded-[14px] border border-[#D9EEF7] bg-white shadow-[0_8px_22px_rgba(31,42,68,0.04)] dark:border-white/10 dark:bg-slate-950/72';
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
    ? 'bg-rose-500 shadow-[0_0_0_3px_rgba(239,68,68,0.13),0_0_10px_rgba(239,68,68,0.34)]'
    : status === '正在跟进'
      ? 'bg-emerald-500 shadow-[0_0_0_3px_rgba(34,197,94,0.14),0_0_10px_rgba(34,197,94,0.42)]'
      : 'bg-slate-400 shadow-[0_0_0_3px_rgba(148,163,184,0.12)]';
  return <span className={`inline-block h-2 w-2 rounded-full ${lampClass}`} title={status} aria-label={status} />;
};

const ConsultationResultCapsule = ({
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
          ? 'bg-sky-500 text-white shadow-[0_0_0_3px_rgba(14,165,233,0.20),0_8px_24px_rgba(14,165,233,0.28)]'
          : completed
            ? 'border border-emerald-200 bg-emerald-50 text-emerald-700 shadow-[0_0_0_1px_rgba(16,185,129,0.16)] dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200'
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
  onStageClick,
  onStageDoubleClick,
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
  onStageClick?: (stage: string) => void;
  onStageDoubleClick?: (stage: string) => void;
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
  const completedSet = new Set(completedStages || []);
  if (!ended && consultationProcessStages.includes(currentStage)) {
    completedSet.add(currentStage);
  }
  const currentProcessIndex = consultationProcessStages.indexOf(currentStage);
  const completedResultStage = (completedStages || []).find(isConsultationResultStage) || '';
  const resultStage = isConsultationResultStage(currentStage) ? currentStage : completedResultStage;
  const resultActive = isConsultationResultStage(currentStage);
  const resultCompleted = Boolean(completedResultStage) && currentProcessIndex < 0;
  const resultLabel = resultStage === '试听失败' ? '咨询失败' : '进班';
  const resultShortLabel = consultationResultShortLabel(resultStage) || '进';
  const flowNodes = [
    ...consultationProcessStages.map((item) => {
      const stageIndex = consultationProcessStages.indexOf(item);
      const isCurrent = item === currentStage;
      const isAfterCurrentProcess = currentProcessIndex >= 0 && stageIndex > currentProcessIndex;
      return {
        key: item,
        type: 'process' as const,
        label: consultationStageDisplayLabel(item).replace('微信✅', ''),
        shortLabel: consultationStageShortLabel(item),
        title: item,
        active: isCurrent,
        completed: completedSet.has(item) && !isAfterCurrentProcess,
        disabled: !editable || ended,
      };
    }),
    {
      key: 'consultation-result',
      type: 'result' as const,
      label: resultLabel,
      shortLabel: resultShortLabel,
      title: resultStage || '成功进班',
      active: resultActive,
      completed: resultCompleted,
      disabled: !editable || ended,
    },
    ...(showOver ? [{
      key: 'consultation-over',
      type: 'over' as const,
      label: 'OVER',
      shortLabel: 'OVER',
      title: '咨询结束',
      active: ended,
      completed: ended,
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
    if (node.type === 'over') {
      return node.active
        ? 'border-[#F45B7A] bg-[#F45B7A] text-white shadow-[0_0_0_3px_rgba(244,91,122,0.14)]'
        : 'border-[#F45B7A] bg-white text-transparent dark:bg-slate-950';
    }
    if (node.active) {
      return 'border-[#0EA5E9] bg-[#0EA5E9] text-white shadow-[0_0_0_3px_rgba(14,165,233,0.16)]';
    }
    if (node.completed) {
      return 'border-[#22B981] bg-[#22B981] text-white';
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
    if (node.active || next.active) return 'bg-[#0EA5E9]';
    return 'bg-[#D9EEF7]';
  };
  return (
    <div className={`grid w-full min-w-0 ${gridClass} ${compact ? 'gap-0.5' : 'gap-1'}`}>
      {flowNodes.map((node, index) => {
        const nextNode = flowNodes[index + 1];
        const circleText = node.type === 'over'
          ? ''
          : node.active
            ? node.shortLabel
            : node.completed
              ? '✓'
              : '';
        const handlePrimaryClick = () => {
          if (node.type === 'process') onStageClick?.(node.key);
          if (node.type === 'result') onResultClick?.();
          if (node.type === 'over') onOverClick?.();
        };
        const handlePrimaryDoubleClick = () => {
          if (node.type === 'process') onStageDoubleClick?.(node.key);
          if (node.type === 'result') onResultDoubleClick?.();
          if (node.type === 'over') onOverDoubleClick?.();
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
              onDoubleClick={handlePrimaryDoubleClick}
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
              <div className={`absolute right-0 top-0 z-20 flex ${compact ? 'h-5 w-5' : 'h-6 w-6'} items-center justify-center rounded-full bg-white/80 text-[#7188A6] shadow-sm dark:bg-slate-900/80`}>
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
                className="absolute left-1/2 top-0 z-20 flex h-4 w-4 -translate-x-1/2 -translate-y-1 items-center justify-center rounded-full bg-white text-[#7188A6] opacity-0 shadow-sm transition hover:text-[#0EA5E9] focus:opacity-100 group-hover:opacity-100 dark:bg-slate-900"
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
