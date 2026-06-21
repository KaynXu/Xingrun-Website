import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, ArrowRight, ArrowUp, CheckCircle2, ChevronLeft, ChevronRight, Pencil, Save, Trash2, X } from 'lucide-react';
import { motion } from 'motion/react';

import type {
  ClassItem,
  CurrentUser,
} from '../../appTypes';
import { getCurrentClassDisplayName, getCurrentClassDisplayNameById } from '../../classDisplay';
import type {
  ConsultationFormValues,
  ConsultationRecord,
  ConsultationResultStage,
  ConsultationTeacherOption,
} from './consultationTypes';
import { apiFetch, cn, getTodayIsoDate, workspacePrimaryButtonClass, workspaceSecondaryButtonClass } from '../../workspaceShared';
import { hasStaffAccess } from '../navigation/workspaceAccess';
import {
  buildConsultationQuickClassSavePayload,
  validateConsultationQuickClassForm,
} from '../../domain/consultationStudentCenterClassAdapter';
import type { ClassFormValues, UserItem } from '../student-center/model';
import { ConsultationEnterClassDialog } from './ConsultationEnterClassDialog';
import { ConsultationStageStatusCards } from './ConsultationStageStatusCards';
import {
  ConsultationFlowNodeDialog,
  ConsultationFlowBar,
  ConsultationStatusLamp,
  applyConsultationFlowNodeDraft,
  buildConsultationFlowStageTeacherLabels,
  clearConsultationResultStage,
  clearConsultationFlowNodeContent,
  completeConsultationOverValues,
  consultationFlowStages,
  consultationInputClass,
  consultationLabelClass,
  consultationPanelClass,
  consultationProcessStages,
  consultationSurfaceClass,
  getConsultationFlowLightColor,
  isConsultationEnded,
  isConsultationResultStage,
  moveConsultationStage,
  normalizeConsultationRecord,
  restoreConsultationValues,
  setConsultationResultStage,
  toggleConsultationStageLight,
  type ConsultationFlowNodeDraft,
} from './consultationShared';

type ConsultationQuickParseKey = keyof Pick<
  ConsultationFormValues,
  | 'parent_wechat_name'
  | 'child_name'
  | 'grade'
  | 'receiving_teacher'
  | 'teacher_id'
  | 'consultation_subject'
  | 'need_detail'
  | 'source_channel'
  | 'source_channel_note'
>;

const academicSubjectOptions = ['数学', '物理', '国际数学'];

function compactConsultationText(value: string): string {
  return value.replace(/\s+/g, '').trim();
}

function normalizeConsultationGradeValue(rawValue: string): string {
  const raw = rawValue.trim();
  if (!raw) {
    return '';
  }
  const normalized = compactConsultationText(raw).replace(/[０-９]/g, (digit) =>
    String.fromCharCode(digit.charCodeAt(0) - 65248),
  );

  const chineseMatch = normalized.match(/[一二三四五六七八九十]{1,3}年级/);
  if (chineseMatch) {
    return chineseMatch[0];
  }

  const directChinese = normalized.match(/(^|[^a-z])(初|高)[一二三]($|[^a-z])/i);
  if (directChinese) {
    return `${directChinese[2]}${normalized.match(/(初|高)([一二三])/)?.[2] ?? ''}`;
  }

  const smallGradeMatch = normalized.match(/(?:小学|小)([1-6一二三四五六])/);
  if (smallGradeMatch) {
    const value = smallGradeMatch[1];
    return `${gradeNumeralMap[value] || value}年级`;
  }

  const numericGradeMatch = normalized.match(/([1-9]|10|11|12)年级?/);
  if (numericGradeMatch) {
    return `${gradeNumeralMap[numericGradeMatch[1]] || numericGradeMatch[1]}年级`;
  }

  const middleOrHighNumeric = normalized.match(/(初|高)([1-3])/);
  if (middleOrHighNumeric) {
    return `${middleOrHighNumeric[1]}${gradeNumeralMap[middleOrHighNumeric[2]] || middleOrHighNumeric[2]}`;
  }

  return raw;
}

function splitConsultationSourceNote(rawValue: string, matchedToken: string): string {
  return compactConsultationText(rawValue).replace(matchedToken, '').replace(/^[：:，,、/\\\-·()（）]+|[：:，,、/\\\-·()（）]+$/g, '');
}

function normalizeConsultationSourceValue(
  rawValue: string,
  parentWechatName = '',
  childName = '',
  sourceNote = '',
): { source_channel: string; source_channel_note: string } {
  const raw = rawValue.trim();
  const rawNote = sourceNote.trim();
  if (!raw) {
    return { source_channel: '', source_channel_note: rawNote };
  }

  const compact = compactConsultationText(raw);
  const parentCompact = compactConsultationText(parentWechatName);
  const childCompact = compactConsultationText(childName);
  if (compact && (compact === parentCompact || compact === childCompact)) {
    return { source_channel: '', source_channel_note: '' };
  }

  for (const [canonical, aliases] of Object.entries(consultationSourceAliasMap)) {
    if (compact === canonical || aliases.includes(compact)) {
      return { source_channel: canonical, source_channel_note: rawNote };
    }
  }

  for (const [canonical, aliases] of Object.entries(consultationSourceAliasMap)) {
    if (compact.includes(canonical)) {
      return {
        source_channel: canonical,
        source_channel_note: rawNote || splitConsultationSourceNote(raw, canonical),
      };
    }
    for (const alias of aliases) {
      if (alias && compact.includes(alias)) {
        return {
          source_channel: canonical,
          source_channel_note: rawNote || splitConsultationSourceNote(raw, alias),
        };
      }
    }
  }

  if (/^[\u4e00-\u9fff]{2,6}$/.test(compact) && !/(介绍|群|圈|私|号|到访)/.test(compact)) {
    return { source_channel: '', source_channel_note: '' };
  }
  if (/(妈妈|爸爸|家长|老师)/.test(compact)) {
    return { source_channel: '', source_channel_note: '' };
  }

  return { source_channel: raw, source_channel_note: rawNote };
}

function normalizeConsultationTeacherOption(option: ConsultationTeacherOption): ConsultationTeacherOption {
  const aliases = Array.from(new Set((option.aliases || []).map((alias) => alias.trim()).filter(Boolean)));
  return {
    teacher_id: option.teacher_id,
    display_name: option.display_name || aliases[0] || option.teacher_id,
    aliases,
  };
}

function findConsultationTeacherOption(input: string, teacherOptions: ConsultationTeacherOption[]): ConsultationTeacherOption | null {
  const compactInput = compactConsultationText(input);
  let match: ConsultationTeacherOption | null = null;
  let longestMatch = 0;

  for (const option of teacherOptions) {
    const candidates = Array.from(new Set([option.display_name, option.teacher_id, ...option.aliases].map((item) => item.trim()).filter(Boolean)));
    for (const candidate of candidates) {
      const compactCandidate = compactConsultationText(candidate);
      if (!compactCandidate || !compactInput.includes(compactCandidate)) {
        continue;
      }
      if (compactCandidate.length > longestMatch) {
        longestMatch = compactCandidate.length;
        match = option;
      }
    }
  }

  return match;
}

export function parseConsultationQuickEntry(
  input: string,
  teacherOptions: Array<{ teacher_id: string; display_name: string; aliases: string[] }>,
): Record<ConsultationQuickParseKey, string> {
  const parsed: Record<ConsultationQuickParseKey, string> = {
    parent_wechat_name: '',
    child_name: '',
    grade: '',
    receiving_teacher: '',
    teacher_id: '',
    consultation_subject: '',
    need_detail: '',
    source_channel: '',
    source_channel_note: '',
  };

  const normalizedInput = input.trim();
  if (!normalizedInput) {
    return parsed;
  }

  const normalizedTeachers = teacherOptions.map(normalizeConsultationTeacherOption);
  const segments = normalizedInput.split(/[，,\n；;]+/).map((segment) => segment.trim()).filter(Boolean);
  const remainingSegments = [...segments];

  const teacherOption = findConsultationTeacherOption(normalizedInput, normalizedTeachers);
  if (teacherOption) {
    parsed.receiving_teacher = teacherOption.display_name;
    parsed.teacher_id = teacherOption.teacher_id;
  }

  for (const segment of segments) {
    if (!parsed.parent_wechat_name && /(妈妈|爸爸|家长)/.test(segment) && !/(介绍|转介绍|群|圈|私信)/.test(segment)) {
      parsed.parent_wechat_name = segment.replace(/^(家长微信|家长|微信)[:：]?/, '').trim();
      continue;
    }
    if (!parsed.child_name) {
      const childMatch = segment.match(/(?:学生姓名|学生|孩子姓名|孩子)[:：]?\s*([\u4e00-\u9fffA-Za-z0-9·]{2,20})/);
      if (childMatch) {
        parsed.child_name = childMatch[1].trim();
      }
    }
  }

  for (const segment of segments) {
    if (!parsed.grade) {
      const grade = normalizeConsultationGradeValue(segment);
      if (grade && grade !== segment.trim()) {
        parsed.grade = grade;
      } else if (consultationGradeOptions.includes(grade)) {
        parsed.grade = grade;
      }
    }
    if (!parsed.consultation_subject) {
      const subject = consultationSubjectOptions.find((option) => segment.includes(option));
      if (subject) {
        parsed.consultation_subject = subject;
      }
    }
  }

  const sourceSegment = segments.find((segment) =>
    Object.entries(consultationSourceAliasMap).some(([canonical, aliases]) => segment.includes(canonical) || aliases.some((alias) => alias && segment.includes(alias))),
  );
  const normalizedSource = normalizeConsultationSourceValue(
    sourceSegment || normalizedInput,
    parsed.parent_wechat_name,
    parsed.child_name,
  );
  parsed.source_channel = normalizedSource.source_channel;
  parsed.source_channel_note = normalizedSource.source_channel_note;

  const cleanedSegments = remainingSegments
    .map((segment) => {
      let cleaned = segment;
      if (parsed.grade) {
        cleaned = cleaned.replace(parsed.grade, '');
      }
      if (parsed.consultation_subject) {
        cleaned = cleaned.replace(parsed.consultation_subject, '');
      }
      if (parsed.source_channel) {
        cleaned = cleaned.replace(parsed.source_channel, '');
      }
      if (parsed.source_channel_note) {
        cleaned = cleaned.replace(parsed.source_channel_note, '');
      }
      if (parsed.parent_wechat_name) {
        cleaned = cleaned.replace(parsed.parent_wechat_name, '');
      }
      if (parsed.child_name) {
        cleaned = cleaned.replace(parsed.child_name, '');
      }
      if (teacherOption) {
        for (const candidate of [teacherOption.display_name, teacherOption.teacher_id, ...teacherOption.aliases]) {
          cleaned = cleaned.replace(candidate, '');
        }
      }
      return cleaned.replace(/(接待|负责|咨询|家长微信|学生姓名|孩子姓名|来源渠道|来源|备注|妈妈|爸爸)[:：]?/g, '').trim();
    })
    .filter(Boolean);

  parsed.need_detail = cleanedSegments.join('，').trim();
  return parsed;
}

type ConsultationFlowSectionKey = 'base' | 'communication' | 'trial' | 'result';
type ConsultationFlowSectionState = 'pending' | 'active' | 'complete';

const consultationResultStages: ConsultationResultStage[] = ['成功进班', '试听失败'];
const consultationFlowSectionOrder: ConsultationFlowSectionKey[] = ['base', 'communication', 'trial', 'result'];
const consultationFlowStageToSection: Record<string, ConsultationFlowSectionKey> = {
  已加小客服微信: 'base',
  已加对应教师微信: 'base',
  正在沟通细节: 'communication',
  待测试: 'communication',
  待试听: 'trial',
  成功进班: 'result',
  试听失败: 'result',
  咨询结束: 'result',
};

function getConsultationFlowSectionStates(values: ConsultationFormValues): Record<ConsultationFlowSectionKey, ConsultationFlowSectionState> {
  const activeSection = consultationFlowStageToSection[values.flow_stage] || 'base';
  const activeIndex = consultationFlowSectionOrder.indexOf(activeSection);
  return consultationFlowSectionOrder.reduce((states, section, index) => {
    states[section] = index < activeIndex ? 'complete' : index == activeIndex ? 'active' : 'pending';
    return states;
  }, {} as Record<ConsultationFlowSectionKey, ConsultationFlowSectionState>);
}

const consultationFlowSectionClass = (state: ConsultationFlowSectionState) => cn(
  'rounded-[18px] border bg-white p-4 transition-colors dark:border-white/10 dark:bg-slate-950/72',
  state === 'active'
    ? 'border-sky-300 bg-sky-50/70 dark:border-sky-400/40 dark:bg-sky-500/10'
    : state === 'complete'
      ? 'border-emerald-200 bg-emerald-50/55 dark:border-emerald-400/20 dark:bg-emerald-500/8'
      : 'border-[#D9EEF7]',
);
const compactFlowTitleClass = (state: boolean | ConsultationFlowSectionState = false) => cn(
  'text-sm font-extrabold tracking-tight',
  state === 'active'
    ? 'text-sky-700 dark:text-sky-300'
    : state === 'complete'
      ? 'text-emerald-700 dark:text-emerald-300'
      : 'text-[#1F2A44] dark:text-white',
);
const compactReadLabelClass = 'text-[11px] font-bold uppercase tracking-[0.16em] text-[#8AA1BC] dark:text-slate-400';
const compactReadValueClass = 'mt-0.5 text-sm font-semibold leading-6 text-[#1F2A44] dark:text-slate-100';
const compactEditLabelClass = consultationLabelClass;
const compactFieldGridClass = 'grid gap-3 lg:grid-cols-2';
const consultationJumpHighlightClass = 'ring-2 ring-sky-300/85 shadow-[0_0_0_4px_rgba(14,165,233,0.12)] dark:ring-sky-400/70';

function deriveConsultationFlowFromFields(values: ConsultationFormValues): ConsultationFormValues {
  if (isConsultationEnded(values.flow_stage)) return values;
  const inferred = new Set(Array.isArray(values.completed_stages) ? values.completed_stages : []);
  if (values.teacher_id || values.receiving_teacher) inferred.add('已加对应教师微信');
  if (values.need_detail.trim()) inferred.add('正在沟通细节');
  if (values.test_taken || values.test_images.length > 0) inferred.add('待测试');
  if (values.trial_taken || values.trial_time_slot || values.trial_class_id || values.trial_class_manual || values.trial_teacher || values.trial_feedback) {
    inferred.add('待试听');
  }
  if (values.flow_stage === '成功进班' || values.success_class_id || values.success_class_manual) inferred.add('成功进班');
  if (values.flow_stage === '试听失败') inferred.add('试听失败');
  const completed_stages = consultationFlowStages
    .filter((stage) => inferred.has(stage))
    .concat(consultationResultStages.filter((stage) => inferred.has(stage)));
  const flow_stage = completed_stages[completed_stages.length - 1] || values.flow_stage || consultationFlowStages[0];
  return { ...values, flow_stage, completed_stages };
}

function classMatchesAssignedTeacher(
  classItem: ClassItem,
  teacher: ConsultationTeacherOption | undefined,
  currentUser: CurrentUser,
): boolean {
  if (!teacher) return true;
  const classTeacherName = (classItem.teacher_name || '').trim().toLowerCase();
  const teacherNames = [teacher.display_name, teacher.teacher_id, ...teacher.aliases]
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  if (classTeacherName && teacherNames.includes(classTeacherName)) return true;
  if (teacher.teacher_id === currentUser.username && classItem.teacher_user_id === currentUser.id) return true;
  return false;
}

function buildConsultationClassUser(currentUser: CurrentUser, teacherName: string): UserItem {
  return {
    id: currentUser.id,
    name: teacherName || currentUser.display_name || currentUser.username,
    org: currentUser.organization_name,
    role: currentUser.role,
    username: currentUser.username,
  };
}

function buildConsultationEnterClassUserOption({
  id,
  name,
  currentUser,
}: {
  id: number;
  name: string;
  currentUser: CurrentUser;
}): UserItem {
  return {
    id,
    name: name || currentUser.display_name || currentUser.username,
    org: currentUser.organization_name,
    role: currentUser.role,
    username: id === currentUser.id ? currentUser.username : undefined,
  };
}

const consultationGradeOptions = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三'];
const consultationSubjectOptions = [...academicSubjectOptions];
const consultationSourceOptions = ['转介绍', '朋友圈', '家长群', '私信', '公众号', '小红书', '抖音', '视频号', '校区到访', '其他'];
const consultationSourceAliasMap: Record<string, string[]> = {
  转介绍: ['转介绍', '介绍', '朋友介绍', '家长介绍', '熟人介绍', '亲友介绍', '老带新', '推荐介绍', '推荐'],
  朋友圈: ['朋友圈', '微信朋友圈', 'pyq'],
  家长群: ['家长群', '微信群', '班级群', '群里', '社群'],
  私信: ['私信', '微信私聊', '企微私聊', '单聊', '私聊'],
  公众号: ['公众号', '微信公众号'],
  小红书: ['小红书'],
  抖音: ['抖音'],
  视频号: ['视频号'],
  校区到访: ['校区到访', '到访', '线下到访', '上门咨询'],
  其他: ['其他'],
};
const gradeNumeralMap: Record<string, string> = {
  1: '一',
  2: '二',
  3: '三',
  4: '四',
  5: '五',
  6: '六',
  7: '七',
  8: '八',
  9: '九',
  10: '十',
  一: '一',
  二: '二',
  三: '三',
  四: '四',
  五: '五',
  六: '六',
};

const consultationFormDefaults: ConsultationFormValues = {
  date: getTodayIsoDate(),
  parent_wechat_name: '',
  child_name: '',
  grade: '',
  receiving_teacher: '',
  teacher_id: '',
  consultation_subject: '',
  need_detail: '',
  source_channel: '',
  source_channel_note: '',
  screenshot: '',
  follow_up_status: '待邀约',
  follow_up_note: '',
  flow_stage: '已加小客服微信',
  completed_stages: ['已加小客服微信'],
  stage_teacher_ids: {},
  assigned_stage: '',
  assignment_note: '',
  is_transferred_consultation: false,
  can_edit_consultation: true,
  transfer_marker: '',
  current_responsibility: '',
  customer_service_added: '',
  customer_service_teacher: '',
  customer_service_note: '',
  communication_teacher_added: '',
  communication_teacher_note: '',
  test_taken: '',
  test_teacher: '',
  test_note: '',
  test_images: [],
  trial_teacher_added: '',
  trial_teacher_note: '',
  trial_taken: '',
  trial_time_slot: '',
  trial_class_id: null,
  trial_class_manual: '',
  trial_teacher: '',
  trial_feedback: '',
  success_class_id: null,
  teaching_teacher_added: '',
  teaching_teacher: '',
  teaching_teacher_note: '',
  success_class_manual: '',
  closing_result: '',
  end_note: '',
  ended_at: '',
};

function buildConsultationBatchCreatePayload(fields: Partial<ConsultationFormValues>): ConsultationFormValues {
  return {
    ...consultationFormDefaults,
    ...fields,
    date: fields.date?.trim() || getTodayIsoDate(),
    follow_up_status: fields.follow_up_status?.trim() || consultationFormDefaults.follow_up_status,
  };
}

function toConsultationFormValues(record?: ConsultationRecord | null): ConsultationFormValues {
  if (!record) {
    return {
      ...consultationFormDefaults,
      completed_stages: [...consultationFormDefaults.completed_stages],
      test_images: [],
    };
  }

  const normalized = normalizeConsultationRecord(record);
  return {
    ...consultationFormDefaults,
    ...normalized,
    completed_stages: Array.isArray(normalized.completed_stages) && normalized.completed_stages.length > 0
      ? [...normalized.completed_stages]
      : [...consultationFormDefaults.completed_stages],
    test_images: Array.isArray(normalized.test_images) ? [...normalized.test_images] : [],
  };
}

const ConsultationReadOnlyReport = ({
  form,
  record,
  classes,
  onPreviewImage,
}: {
  form: ConsultationFormValues;
  record: ConsultationRecord | null;
  classes: ClassItem[];
  onPreviewImage: (index: number) => void;
}) => {
  const sectionStates = getConsultationFlowSectionStates(form);
  const trialClassName = getCurrentClassDisplayNameById(classes, form.trial_class_id);
  const successClassName = getCurrentClassDisplayNameById(classes, form.success_class_id);
  const resultLabel = form.flow_stage === '成功进班'
    ? '咨询成功'
    : form.flow_stage === '试听失败' || form.flow_stage === '咨询结束'
      ? '咨询失败'
      : '尚未定论';
  const value = (text?: string | null) => text?.trim() || '—';
  const followUpLines = form.follow_up_note.split('\n');
  const readOnlyBoxClass = 'rounded-xl border border-[#D9EEF7] bg-[#F9FDFF] px-3 py-3 dark:border-white/10 dark:bg-white/[0.03]';
  const readOnlyTwoColumnGridClass = 'grid-cols-2';

  return (
    <section className="grid gap-3 md:grid-cols-2">
      <div className={cn(consultationFlowSectionClass(sectionStates.base), 'min-h-[14rem] md:order-1')}>
        <p className={compactFlowTitleClass(sectionStates.base)}>基础信息</p>
        <ConsultationStageStatusCards values={form} classes={classes} section="base" />
        <div className={`mt-3 grid gap-x-3 gap-y-3 text-sm ${readOnlyTwoColumnGridClass}`}>
          <div><p className={compactReadLabelClass}>家长微信名</p><p className={compactReadValueClass}>{value(form.parent_wechat_name)}</p></div>
          <div><p className={compactReadLabelClass}>孩子姓名</p><p className={compactReadValueClass}>{value(form.child_name)}</p></div>
          <div><p className={compactReadLabelClass}>年级</p><p className={compactReadValueClass}>{value(form.grade)}</p></div>
          <div><p className={compactReadLabelClass}>咨询科目</p><p className={compactReadValueClass}>{value(form.consultation_subject)}</p></div>
          <div><p className={compactReadLabelClass}>来源渠道主类</p><p className={compactReadValueClass}>{value(form.source_channel)}</p></div>
          <div><p className={compactReadLabelClass}>来源渠道备注</p><p className={compactReadValueClass}>{value(form.source_channel_note)}</p></div>
        </div>
      </div>

      <div className={cn(consultationFlowSectionClass(sectionStates.communication), 'min-h-[14rem] space-y-2 md:order-3')}>
        <p className={compactFlowTitleClass(sectionStates.communication)}>沟通与测试</p>
        <ConsultationStageStatusCards values={form} classes={classes} section="communication" />
        <div className="mt-2 grid items-stretch gap-2 sm:grid-cols-2">
          <div className={cn(readOnlyBoxClass, 'flex h-full flex-col space-y-2')}>
            <div className="min-h-0 flex-1">
              <p className={compactReadLabelClass}>沟通情况</p>
              <p className={cn(compactReadValueClass, 'whitespace-pre-wrap')}>{value(form.need_detail)}</p>
            </div>
            <div className="grid shrink-0 gap-2">
              <div><p className={compactReadLabelClass}>跟进 1</p><p className={compactReadValueClass}>{value(followUpLines[0])}</p></div>
              <div><p className={compactReadLabelClass}>跟进 2</p><p className={compactReadValueClass}>{value(followUpLines.slice(1).join('\n'))}</p></div>
            </div>
          </div>
          <div className={cn(readOnlyBoxClass, 'flex h-full flex-col space-y-2')}>
            <p className={compactReadLabelClass}>测试情况</p>
            {form.test_images.length > 0 ? (
              <div className="grid min-h-0 flex-1 grid-cols-2 grid-rows-2 gap-2 overflow-hidden">
                {form.test_images.slice(0, 4).map((image, index) => (
                  <button
                    type="button"
                    key={`${image.url}-${index}`}
                    onClick={() => onPreviewImage(index)}
                    className="group block min-h-0 overflow-hidden rounded-xl border border-sky-100 bg-sky-50 text-left dark:border-white/10 dark:bg-white/5"
                    aria-label={`查看测试情况图片 ${index + 1}`}
                  >
                    <img src={image.url} alt={`测试情况图片 ${index + 1}`} className="h-full w-full object-cover transition group-hover:scale-105" />
                  </button>
                ))}
              </div>
            ) : (
              <p className={compactReadValueClass}>暂无</p>
            )}
          </div>
        </div>
      </div>

      <div className={cn(consultationFlowSectionClass(sectionStates.trial), 'min-h-[14rem] md:order-2')}>
        <p className={compactFlowTitleClass(sectionStates.trial)}>试听</p>
        <ConsultationStageStatusCards values={form} classes={classes} section="trial" />
        <div className={`mt-3 grid gap-x-3 gap-y-2 text-sm ${readOnlyTwoColumnGridClass}`}>
          <div><p className={compactReadLabelClass}>对应班课</p><p className={compactReadValueClass}>{value(trialClassName || form.trial_class_manual)}</p></div>
          <div><p className={compactReadLabelClass}>试听时间段</p><p className={compactReadValueClass}>{value(form.trial_time_slot)}</p></div>
        </div>
        <div className="mt-3 border-t border-sky-50 pt-3 dark:border-white/10">
          <p className={compactReadLabelClass}>试听反馈</p>
          <p className={compactReadValueClass}>{value(form.trial_feedback)}</p>
        </div>
      </div>

      <div className={cn(consultationFlowSectionClass(sectionStates.result), 'min-h-[14rem] space-y-3 md:order-4')}>
        <p className={compactFlowTitleClass(sectionStates.result)}>结果与备注</p>
        <ConsultationStageStatusCards values={form} classes={classes} section="result" />
        <div className={`grid gap-3 text-sm ${readOnlyTwoColumnGridClass}`}>
          <div>
            <p className={compactReadLabelClass}>结果</p>
            <p className={cn(
              'mt-0.5 inline-flex rounded-full px-2.5 py-1 text-xs font-bold',
              resultLabel === '咨询成功'
                ? 'bg-amber-50 text-amber-700 dark:bg-amber-400/10 dark:text-amber-300'
                : resultLabel === '咨询失败'
                  ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-300'
                  : 'bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-300',
            )}>
              {resultLabel}
            </p>
          </div>
          <div>
            <p className={compactReadLabelClass}>班级</p>
            <p className={compactReadValueClass}>{value(successClassName || form.success_class_manual)}</p>
          </div>
          {record && (
            <>
              <div><p className={compactReadLabelClass}>录入时间</p><p className={compactReadValueClass}>{record.created_at || '—'}</p></div>
              <div><p className={compactReadLabelClass}>结束时间</p><p className={compactReadValueClass}>{record.ended_at || record.updated_at || '—'}</p></div>
            </>
          )}
        </div>
        <div className="mt-3 border-t border-sky-50 pt-3 dark:border-white/10">
          <div className="grid gap-3 md:grid-cols-2">
            <div><p className={compactReadLabelClass}>咨询结束备注</p><p className={compactReadValueClass}>{value(form.end_note)}</p></div>
            <div><p className={compactReadLabelClass}>跟进备注（内部）</p><p className={compactReadValueClass}>{value(form.follow_up_note)}</p></div>
          </div>
        </div>
      </div>
    </section>
  );
};

const ConsultationModal = ({
  open,
  mode,
  record,
  consultationTeachers,
  classes,
  submitting,
  error,
  currentUser,
  onClose,
  onSubmit,
  onDelete,
  onRequestEdit,
}: {
  open: boolean;
  mode: 'view' | 'create' | 'edit';
  record: ConsultationRecord | null;
  consultationTeachers: ConsultationTeacherOption[];
  classes: ClassItem[];
  submitting: boolean;
  error: string;
  currentUser: CurrentUser;
  onClose: () => void;
  onSubmit: (values: ConsultationFormValues) => Promise<void>;
  onDelete?: () => Promise<void>;
  onRequestEdit?: () => void;
}) => {
  const [form, setForm] = useState<ConsultationFormValues>(toConsultationFormValues(record));
  const [quickEntry, setQuickEntry] = useState('');
  const [parseFeedback, setParseFeedback] = useState('');
  const [confirmRestoreOpen, setConfirmRestoreOpen] = useState(false);
  const [trialManualClassActive, setTrialManualClassActive] = useState(false);
  const [highlightedJumpStage, setHighlightedJumpStage] = useState<string>('');
  const [flowNodeDialog, setFlowNodeDialog] = useState<{ stage: string; setAsCurrent: boolean } | null>(null);
  const [enterClassDialogOpen, setEnterClassDialogOpen] = useState(false);
  const [overResultDialogOpen, setOverResultDialogOpen] = useState(false);
  const [creatingSuccessClass, setCreatingSuccessClass] = useState(false);
  const [successClassCreateError, setSuccessClassCreateError] = useState('');
  const [localClasses, setLocalClasses] = useState<ClassItem[]>(classes);
  const [deletingTestImageIndex, setDeletingTestImageIndex] = useState<number | null>(null);
  const [previewImageIndex, setPreviewImageIndex] = useState<number | null>(null);
  const previewImageCount = form.test_images.length;
  const formScrollRef = useRef<HTMLFormElement | null>(null);
  const baseInfoRef = useRef<HTMLElement | null>(null);
  const contentRef = useRef<HTMLElement | null>(null);
  const testSectionRef = useRef<HTMLDivElement | null>(null);
  const trialSectionRef = useRef<HTMLDivElement | null>(null);
  const successSectionRef = useRef<HTMLElement | null>(null);
  const endSectionRef = useRef<HTMLLabelElement | null>(null);
  const jumpHighlightTimerRef = useRef<number | null>(null);
  const initialConsultationForm = useMemo(() => {
    const initialValues = toConsultationFormValues(record);
    const defaultAssignedValues = !record && currentUser.role === 'member'
      ? {
          ...initialValues,
          teacher_id: currentUser.username,
          receiving_teacher: currentUser.display_name || currentUser.username,
        }
      : initialValues;
    return deriveConsultationFlowFromFields(defaultAssignedValues);
  }, [record, currentUser.role, currentUser.username, currentUser.display_name]);
  const readOnly = mode === 'view';
  const hasConsultationFormChanges = JSON.stringify(form) !== JSON.stringify(initialConsultationForm);
  const canSaveConsultationDraft = !readOnly && !submitting && (mode === 'create' || hasConsultationFormChanges);

  useEffect(() => {
    if (open) {
      setForm(initialConsultationForm);
      setQuickEntry('');
      setParseFeedback('');
      setConfirmRestoreOpen(false);
      setFlowNodeDialog(null);
      setEnterClassDialogOpen(false);
      setOverResultDialogOpen(false);
      setCreatingSuccessClass(false);
      setSuccessClassCreateError('');
      setLocalClasses(classes);
      setDeletingTestImageIndex(null);
      setPreviewImageIndex(null);
      setHighlightedJumpStage('');
      setTrialManualClassActive(Boolean(initialConsultationForm.trial_class_manual && !initialConsultationForm.trial_class_id));
    }
  }, [open, mode, initialConsultationForm, classes]);

  useEffect(() => () => {
    if (jumpHighlightTimerRef.current !== null) {
      window.clearTimeout(jumpHighlightTimerRef.current);
    }
  }, []);

  useEffect(() => {
    if (!open || mode === 'view') {
      return undefined;
    }
    const handleSaveShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        if (canSaveConsultationDraft) {
          formScrollRef.current?.requestSubmit();
        }
      }
    };
    window.addEventListener('keydown', handleSaveShortcut);
    return () => window.removeEventListener('keydown', handleSaveShortcut);
  }, [open, mode, canSaveConsultationDraft]);

  useEffect(() => {
    if (previewImageIndex === null) {
      return undefined;
    }
    const handleImagePreviewKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setPreviewImageIndex(null);
      }
      if (event.key === 'ArrowLeft') {
        setPreviewImageIndex((current) => {
          if (current === null || previewImageCount === 0) return current;
          return (current - 1 + previewImageCount) % previewImageCount;
        });
      }
      if (event.key === 'ArrowRight') {
        setPreviewImageIndex((current) => {
          if (current === null || previewImageCount === 0) return current;
          return (current + 1) % previewImageCount;
        });
      }
    };
    window.addEventListener('keydown', handleImagePreviewKeydown);
    return () => window.removeEventListener('keydown', handleImagePreviewKeydown);
  }, [previewImageCount, previewImageIndex]);

  useEffect(() => {
    if (previewImageIndex !== null && previewImageIndex >= previewImageCount) {
      setPreviewImageIndex(previewImageCount > 0 ? previewImageCount - 1 : null);
    }
  }, [previewImageCount, previewImageIndex]);

  if (!open) {
    return null;
  }

  const stageFrozen = isConsultationEnded(form.flow_stage);
  const canEdit = hasStaffAccess(currentUser.role) || currentUser.role === 'member';
  const saveButtonLabel = submitting ? '保存中...' : mode === 'create' ? '创建记录' : '保存修改';
  const titleMap = {
    view: '查看咨询记录',
    create: '新增咨询记录',
    edit: '编辑咨询记录',
  } as const;

  const updateField = <K extends keyof ConsultationFormValues>(key: K, value: ConsultationFormValues[K]) => {
    setForm((current) => deriveConsultationFlowFromFields({ ...current, [key]: value }));
  };

  const followUpLines = useMemo(() => {
    const lines = form.follow_up_note.split('\n');
    return [lines[0] || '', lines.slice(1).join('\n') || ''];
  }, [form.follow_up_note]);
  const testImagePages = useMemo(() => {
    const tiles: Array<
      | { type: 'image'; image: ConsultationFormValues['test_images'][number]; index: number }
      | { type: 'upload' }
      | { type: 'pending-upload' }
    > = form.test_images.map((image, index) => ({ type: 'image', image, index }));
    if (!readOnly) {
      tiles.push(record ? { type: 'upload' } : { type: 'pending-upload' });
    }
    const pageSize = 4;
    const pages = [];
    for (let index = 0; index < tiles.length; index += pageSize) {
      pages.push(tiles.slice(index, index + pageSize));
    }
    return pages;
  }, [form.test_images, readOnly, record]);
  const previewImage = previewImageIndex === null ? null : form.test_images[previewImageIndex] || null;
  const closeImagePreview = () => setPreviewImageIndex(null);
  const showPreviousImage = () => {
    setPreviewImageIndex((current) => {
      if (current === null || previewImageCount === 0) return current;
      return (current - 1 + previewImageCount) % previewImageCount;
    });
  };
  const showNextImage = () => {
    setPreviewImageIndex((current) => {
      if (current === null || previewImageCount === 0) return current;
      return (current + 1) % previewImageCount;
    });
  };

  const updateFollowUpLine = (lineIndex: 0 | 1, value: string) => {
    const nextLines = [...followUpLines];
    nextLines[lineIndex] = value;
    updateField('follow_up_note', nextLines.join('\n').trimEnd());
  };

  const teacherOptions = (() => {
    if (!form.teacher_id || consultationTeachers.some((option) => option.teacher_id === form.teacher_id)) {
      return consultationTeachers;
    }
    return [
      {
        teacher_id: form.teacher_id,
        display_name: form.receiving_teacher || form.teacher_id,
        aliases: [],
      },
      ...consultationTeachers,
    ];
  })();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSaveConsultationDraft) {
      return;
    }
    if (form.flow_stage === '成功进班' && !form.success_class_id && !form.success_class_manual.trim()) {
      setParseFeedback('成功进班必须选择或填写班级。');
      return;
    }
    await onSubmit(form);
  };

  const handleTeacherChange = (teacherId: string) => {
    const selectedTeacher = teacherOptions.find((option) => option.teacher_id === teacherId);
    if (!selectedTeacher) {
      setForm((current) => deriveConsultationFlowFromFields({ ...current, teacher_id: teacherId, receiving_teacher: teacherId ? current.receiving_teacher : '' }));
      return;
    }
    setForm((current) => deriveConsultationFlowFromFields({
      ...current,
      teacher_id: selectedTeacher.teacher_id,
      receiving_teacher: selectedTeacher.display_name,
    }));
  };

  const handleStageStatusTeacherChange = (
    field: 'teacher_id' | 'communication_teacher_added' | 'test_teacher' | 'trial_teacher' | 'teaching_teacher',
    value: string,
  ) => {
    if (field === 'teacher_id') {
      handleTeacherChange(value);
      return;
    }
    if (field === 'teaching_teacher') {
      const nextTeacher = teacherOptions.find((option) => option.display_name === value);
      const currentSuccessClass = localClasses.find((item) => item.id === form.success_class_id);
      const successClassStillMatches = !currentSuccessClass || classMatchesAssignedTeacher(currentSuccessClass, nextTeacher, currentUser);
      setForm((current) => deriveConsultationFlowFromFields({
        ...current,
        teaching_teacher: value,
        success_class_id: successClassStillMatches ? current.success_class_id : null,
      }));
      return;
    }
    updateField(field, value);
  };

  const handleDeleteTestImage = async (index: number) => {
    if (!record) return;
    setDeletingTestImageIndex(index);
    setParseFeedback('');
    setForm((current) => deriveConsultationFlowFromFields({
      ...current,
      test_images: current.test_images.filter((_, imageIndex) => imageIndex !== index),
    }));
    try {
      const deleted = await apiFetch<{ item: ConsultationRecord }>(`/api/consultations/${record.id}/test-images/${index}`, {
        method: 'DELETE',
      });
      setForm(deriveConsultationFlowFromFields(toConsultationFormValues(normalizeConsultationRecord(deleted.item))));
    } catch (err) {
      const message = err instanceof Error ? err.message : '删除测试图片失败';
      setParseFeedback(`${message}；已先从当前编辑中移除，点击保存后写入记录。`);
    } finally {
      setDeletingTestImageIndex(null);
    }
  };

  const openFlowNodeDialog = (stage: string, setAsCurrent: boolean) => {
    if (!consultationProcessStages.includes(stage)) return;
    if (!setAsCurrent) {
      const lightColor = getConsultationFlowLightColor(form, stage);
      if (lightColor === 'green' || lightColor === 'blue') {
        if (!window.confirm('是否取消该阶段状态？取消后会删除这个阶段已填写的内容。')) {
          return;
        }
        setForm((current) => clearConsultationFlowNodeContent(current, stage));
        return;
      }
    }
    setFlowNodeDialog({ stage, setAsCurrent });
  };

  const handleSaveFlowNodeDialog = (draft: ConsultationFlowNodeDraft) => {
    if (!flowNodeDialog) return;
    setForm((current) => applyConsultationFlowNodeDraft(current, flowNodeDialog.stage, draft, flowNodeDialog.setAsCurrent));
    setFlowNodeDialog(null);
  };

  const handleQuickParse = () => {
    if (!quickEntry.trim()) {
      setParseFeedback('先输入一段咨询描述，再进行智能解析。');
      return;
    }

    const parsed = parseConsultationQuickEntry(quickEntry, consultationTeachers);
    const nextForm: ConsultationFormValues = { ...form };

    Object.entries(parsed).forEach(([key, value]) => {
      if (value) {
        nextForm[key as ConsultationQuickParseKey] = value;
      }
    });

    if (nextForm.grade) {
      nextForm.grade = normalizeConsultationGradeValue(nextForm.grade);
    }

    const normalizedSource = normalizeConsultationSourceValue(
      nextForm.source_channel,
      nextForm.parent_wechat_name,
      nextForm.child_name,
      nextForm.source_channel_note,
    );
    nextForm.source_channel = normalizedSource.source_channel;
    nextForm.source_channel_note = normalizedSource.source_channel_note;

    setForm(deriveConsultationFlowFromFields(nextForm));
    setParseFeedback(
      parsed.parent_wechat_name || parsed.grade || parsed.consultation_subject || parsed.source_channel || parsed.receiving_teacher
        ? '已根据快速录入内容回填字段，请检查后保存。'
        : '这段描述还不够明确，建议补充老师、年级或来源关键词后再试。',
    );
  };

  const handleStageJump = (stage: string) => {
    const target = stage === '待测试'
      ? testSectionRef.current
      : stage === '待试听' || stage === '试听失败'
        ? trialSectionRef.current
        : stage === '成功进班'
          ? successSectionRef.current
          : stage === '咨询结束'
            ? endSectionRef.current
            : stage === '正在沟通细节'
              ? contentRef.current
              : baseInfoRef.current;
    if (jumpHighlightTimerRef.current !== null) {
      window.clearTimeout(jumpHighlightTimerRef.current);
    }
    setHighlightedJumpStage(stage);
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    jumpHighlightTimerRef.current = window.setTimeout(() => setHighlightedJumpStage(''), 900);
  };

  const handleSuccessClassChange = (value: string) => {
    const classId = value ? Number(value) : null;
    setForm((current) => {
      const next = { ...current, success_class_id: classId, success_class_manual: classId ? '' : current.success_class_manual };
      return deriveConsultationFlowFromFields(classId ? setConsultationResultStage(next, '成功进班') : next);
    });
  };

  const handleConfirmExistingClass = (classId: number) => {
    setForm((current) => {
      const next = { ...current, success_class_id: classId, success_class_manual: '' };
      return deriveConsultationFlowFromFields(completeConsultationOverValues(setConsultationResultStage(next, '成功进班'), 'success'));
    });
    setEnterClassDialogOpen(false);
  };

  const handleCreateSuccessClass = async (draft: ClassFormValues) => {
    setCreatingSuccessClass(true);
    setSuccessClassCreateError('');
    try {
      const quickClassTeacherUserId = form.teaching_teacher_user_id ?? currentUser.id;
      const selectedTeacher = form.teaching_teacher_user_id != null
        ? buildConsultationEnterClassUserOption({
          id: form.teaching_teacher_user_id,
          name: form.teaching_teacher || form.trial_teacher || form.receiving_teacher,
          currentUser,
        })
        : buildConsultationClassUser(currentUser, currentUser.display_name || currentUser.username);
      const validationError = validateConsultationQuickClassForm({
        form: {
          ...draft,
          grade: draft.current_grade,
          class_number: draft.class_type === 'group' ? draft.class_number : '',
        },
        selectedTeacher,
        selectedTeacherUserId: quickClassTeacherUserId,
        gradeOptions: consultationGradeOptions,
      });
      if (validationError) {
        setSuccessClassCreateError(validationError);
        return;
      }
      const payload = buildConsultationQuickClassSavePayload({
        form: {
          ...draft,
          grade: draft.current_grade,
          class_number: draft.class_type === 'group' ? draft.class_number : '',
        },
        selectedTeacher,
        selectedTeacherUserId: quickClassTeacherUserId,
      });
      const createdClass = await apiFetch<ClassItem>('/api/classes', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setLocalClasses((current) => [createdClass, ...current.filter((item) => item.id !== createdClass.id)]);
      handleConfirmExistingClass(createdClass.id);
    } catch (err) {
      setSuccessClassCreateError(err instanceof Error ? err.message : '快速建班失败');
    } finally {
      setCreatingSuccessClass(false);
    }
  };

  const handleMarkPendingSuccessClass = () => {
    setForm((current) => {
      const next = { ...current, success_class_id: null, success_class_manual: '转化待进班' };
      return deriveConsultationFlowFromFields(completeConsultationOverValues(setConsultationResultStage(next, '成功进班'), 'success'));
    });
    setEnterClassDialogOpen(false);
  };

  const handleOverSuccess = () => {
    setOverResultDialogOpen(false);
    setEnterClassDialogOpen(true);
  };

  const handleOverFailure = () => {
    setForm((current) => completeConsultationOverValues(current, 'failed'));
    setOverResultDialogOpen(false);
  };

  const selectedTeacher = teacherOptions.find((option) => option.teacher_id === form.teacher_id);
  const teacherMatchedClasses = localClasses.filter((item) => classMatchesAssignedTeacher(item, selectedTeacher, currentUser));
  const assignableClassOptions = selectedTeacher && teacherMatchedClasses.length > 0 ? teacherMatchedClasses : localClasses;
  const selectedTeachingTeacher = teacherOptions.find((option) => option.display_name === form.teaching_teacher);
  const consultationEnterClassTeacherUserId = form.teaching_teacher_user_id ?? null;
  const successClassOptions = localClasses;
  const consultationEnterClassUsers = consultationEnterClassTeacherUserId == null ? [] : [
    buildConsultationEnterClassUserOption({
      id: consultationEnterClassTeacherUserId,
      name: consultationEnterClassTeacherUserId === currentUser.id
        ? currentUser.display_name || currentUser.username
        : selectedTeachingTeacher?.display_name || form.teaching_teacher,
      currentUser,
    }),
  ];
  const trialUsesManualClass = trialManualClassActive || Boolean(form.trial_class_manual.trim() && !form.trial_class_id);
  const baseInfoHighlighted = highlightedJumpStage === '已加小客服微信' || highlightedJumpStage === '已加对应教师微信';
  const communicationHighlighted = highlightedJumpStage === '正在沟通细节';
  const testHighlighted = highlightedJumpStage === '待测试';
  const trialHighlighted = highlightedJumpStage === '待试听' || highlightedJumpStage === '试听失败';
  const successHighlighted = highlightedJumpStage === '成功进班';
  const endHighlighted = highlightedJumpStage === '咨询结束';

  const fieldClass = `${consultationInputClass} ${readOnly ? 'cursor-default' : ''}`;
  const sectionBoxClass = 'rounded-xl border border-[#D9EEF7] bg-[#F9FDFF] px-3 py-3 dark:border-white/10 dark:bg-white/[0.03]';
  const showTestFields = form.flow_stage === '待测试' || form.test_taken || form.test_images.length > 0;
  const showTrialFields = form.flow_stage === '待试听' || form.flow_stage === '试听失败' || form.trial_taken || form.trial_time_slot || form.trial_class_id || form.trial_class_manual || form.trial_teacher || form.trial_feedback;
  const showEndFields = form.flow_stage === '咨询结束' || form.end_note;
  const sectionStates = getConsultationFlowSectionStates(form);
  const flowHeaderMetaClass = 'inline-flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400';

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#F5FAFD]/25 px-3 py-3 sm:items-center sm:px-4 sm:py-6"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="absolute inset-0 bg-slate-950/38 backdrop-blur-[6px]" />
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: 18 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.97, y: 18 }}
        transition={{ duration: 0.2 }}
        className={`relative z-10 my-auto flex w-full max-w-5xl flex-col overflow-hidden rounded-[18px] ${consultationSurfaceClass} max-sm:min-h-[calc(100dvh-1.5rem)] max-sm:max-h-[calc(100dvh-1.5rem)] sm:max-h-[calc(100dvh-3rem)]`}
      >
        <div className="relative grid gap-4 border-b border-[#EAF6FC] bg-white px-4 py-3.5 sm:px-6 sm:py-4 lg:grid-cols-2 lg:items-start dark:border-white/10 dark:bg-slate-950/80">
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-[0.24em] text-[#0EA5E9]">Consultation</p>
            <h3 className="mt-1.5 text-xl font-extrabold tracking-tight text-[#1F2A44] sm:text-2xl dark:text-white">{titleMap[mode]}</h3>
          </div>
          {!readOnly ? (
            <div className="min-w-0 rounded-xl border border-[#D9EEF7] bg-[#F8FCFE] p-2.5 dark:border-white/10 dark:bg-white/[0.03]">
              <div className="grid gap-2 sm:grid-cols-[minmax(13rem,1fr)_4.75rem_3.75rem_auto_auto] sm:items-center">
                <textarea
                  value={quickEntry}
                  onChange={(e) => setQuickEntry(e.target.value)}
                  rows={1}
                  aria-label="快速录入咨询描述"
                  className={`${consultationInputClass} min-h-10 resize-none bg-white`}
                  placeholder="快速录入"
                />
                <button type="button" onClick={handleQuickParse} className={`${workspacePrimaryButtonClass} h-10 min-w-0 gap-0 px-1 py-2 text-xs`}>
                  智能解析
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setQuickEntry('');
                    setParseFeedback('');
                  }}
                  className={`${workspaceSecondaryButtonClass} h-10 min-w-0 gap-1 px-1.5 py-2 text-xs`}
                >
                  清空
                </button>
                <button
                  type="button"
                  onClick={() => formScrollRef.current?.requestSubmit()}
                  className={`${workspacePrimaryButtonClass} inline-flex h-10 w-10 items-center justify-center px-0`}
                  disabled={!canSaveConsultationDraft}
                  title={`${saveButtonLabel} · Command+S / Ctrl+S`}
                  aria-label="保存咨询记录"
                >
                  <Save size={20} strokeWidth={2.5} className="shrink-0" />
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#F1F9FE] text-[#7188A6] transition-colors hover:bg-sky-100 hover:text-[#1F2A44] dark:bg-white/5 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-white"
                  aria-label="关闭咨询记录窗口"
                >
                  ×
                </button>
              </div>
            </div>
          ) : (
            <div className="hidden lg:block" />
          )}
          <div className={cn('absolute right-4 top-3.5 flex shrink-0 items-center justify-end gap-2 sm:right-6 sm:top-4', !readOnly && 'hidden')}>
            <button
              type="button"
              onClick={onClose}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-[#F1F9FE] text-[#7188A6] transition-colors hover:bg-sky-100 hover:text-[#1F2A44] dark:bg-white/5 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-white"
              aria-label="关闭咨询记录窗口"
            >
              ×
            </button>
          </div>
        </div>
        <button
          type="button"
          onClick={() => formScrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' })}
          className={cn(
            'absolute right-4 z-20 flex h-9 w-9 items-center justify-center rounded-full border border-[#D9EEF7] bg-white text-[#0EA5E9] transition hover:bg-sky-50 dark:border-white/10 dark:bg-slate-800 dark:text-sky-300 dark:hover:bg-slate-700 sm:right-6',
            readOnly ? 'top-16 sm:top-16' : 'top-20 sm:top-24',
          )}
          title="回到顶部"
          aria-label="回到顶部"
        >
          <ArrowUp size={18} />
        </button>

        <form ref={formScrollRef} onSubmit={handleSubmit} className="flex-1 overflow-y-auto bg-[#F8FCFE] px-4 py-4 sm:px-6 sm:py-5 dark:bg-slate-900/80">
          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <section className={`${consultationPanelClass} mb-4 space-y-3 p-3.5 sm:p-4`}>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <h4 className="font-extrabold text-[#1F2A44] dark:text-white">咨询流程</h4>
                <span className={flowHeaderMetaClass}>
                  <ConsultationStatusLamp stage={form.flow_stage} />
                </span>
              </div>
            </div>
            {confirmRestoreOpen && (
              <div className="rounded-2xl border border-sky-100 bg-white p-4 dark:border-white/10 dark:bg-slate-950">
                <p className="text-sm font-semibold text-slate-900 dark:text-white">是否恢复这个咨询？</p>
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setForm((current) => restoreConsultationValues(current));
                      setConfirmRestoreOpen(false);
                    }}
                    className={workspacePrimaryButtonClass}
                  >
                    是
                  </button>
                  <button type="button" onClick={() => setConfirmRestoreOpen(false)} className={workspaceSecondaryButtonClass}>
                    否
                  </button>
                </div>
              </div>
            )}
            <div className="min-w-0">
              <ConsultationFlowBar
                mode="list"
                stage={form.flow_stage}
                completedStages={form.completed_stages}
                closingResult={form.closing_result}
                stageTeacherLabels={buildConsultationFlowStageTeacherLabels(form)}
                editable={!readOnly && !stageFrozen}
                showJumpActions={!readOnly}
                showOver
                overDisabled={readOnly}
                onStageClick={(nextStage) => openFlowNodeDialog(nextStage, false)}
                onStageContextMenu={(nextStage) => openFlowNodeDialog(nextStage, true)}
                onStageLongPress={(nextStage) => openFlowNodeDialog(nextStage, true)}
                onResultChange={(stage) => {
                  if (stage === '成功进班') {
                    setEnterClassDialogOpen(true);
                    return;
                  }
                  setForm((current) => setConsultationResultStage(current, stage));
                }}
                onResultClick={() => {
                  if (isConsultationResultStage(form.flow_stage)) {
                    setForm((current) => clearConsultationResultStage(current));
                    return;
                  }
                  setEnterClassDialogOpen(true);
                }}
                onResultDoubleClick={() => setEnterClassDialogOpen(true)}
                onStageJump={handleStageJump}
                onOverClick={() => {
                  if (readOnly) return;
                  if (stageFrozen) {
                    setConfirmRestoreOpen(true);
                    return;
                  }
                  setOverResultDialogOpen(true);
                }}
              />
            </div>
          </section>

          {readOnly ? (
            <ConsultationReadOnlyReport form={form} record={record} classes={classes} onPreviewImage={setPreviewImageIndex} />
          ) : (
            <>
          <datalist id="consultation-grade-options">
            {consultationGradeOptions.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>

          <div className="grid gap-3 md:grid-cols-2">
            <section ref={baseInfoRef} className={cn(consultationFlowSectionClass(sectionStates.base), 'min-h-[14rem] scroll-mt-6 md:order-1', baseInfoHighlighted && consultationJumpHighlightClass)}>
            <p className={compactFlowTitleClass(sectionStates.base)}>基础信息</p>
            <ConsultationStageStatusCards
              values={form}
              classes={localClasses}
              section="base"
              teacherOptions={teacherOptions}
              onTeacherChange={handleStageStatusTeacherChange}
            />

            <div className={`${compactFieldGridClass} mt-3`}>
              <label className="space-y-2 text-sm">
                <span className={compactEditLabelClass}>家长微信名</span>
                <input value={form.parent_wechat_name} onChange={(e) => updateField('parent_wechat_name', e.target.value)} disabled={readOnly} className={fieldClass} placeholder="家长微信昵称" />
              </label>
              <label className="space-y-2 text-sm">
                <span className={compactEditLabelClass}>孩子姓名</span>
                <input value={form.child_name} onChange={(e) => updateField('child_name', e.target.value)} disabled={readOnly} className={fieldClass} placeholder="孩子姓名" />
              </label>
              <label className="space-y-2 text-sm">
                <span className={compactEditLabelClass}>年级</span>
                <input value={form.grade} onChange={(e) => updateField('grade', e.target.value)} disabled={readOnly} list="consultation-grade-options" className={fieldClass} placeholder="如：三年级" />
              </label>
              <label className="space-y-2 text-sm">
                <span className={compactEditLabelClass}>咨询科目</span>
                <select value={academicSubjectOptions.includes(form.consultation_subject) ? form.consultation_subject : ''} onChange={(e) => updateField('consultation_subject', e.target.value)} disabled={readOnly} className={fieldClass}>
                  <option value="">请选择咨询科目</option>
                  {academicSubjectOptions.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm">
                <span className={compactEditLabelClass}>来源渠道主类</span>
                <select value={form.source_channel} onChange={(e) => updateField('source_channel', e.target.value)} disabled={readOnly} className={fieldClass}>
                  <option value="">请选择来源渠道</option>
                  {!consultationSourceOptions.includes(form.source_channel) && form.source_channel ? (
                    <option value={form.source_channel}>{form.source_channel}</option>
                  ) : null}
                  {consultationSourceOptions.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm">
                <span className={compactEditLabelClass}>来源渠道备注</span>
                <input value={form.source_channel_note} onChange={(e) => updateField('source_channel_note', e.target.value)} disabled={readOnly} className={fieldClass} placeholder="例如：张妈妈转介绍" />
              </label>
            </div>
          </section>

            <section ref={contentRef} className={cn(consultationFlowSectionClass(sectionStates.communication), 'min-h-[14rem] scroll-mt-6 space-y-2 md:order-3', communicationHighlighted && consultationJumpHighlightClass)}>
            <p className={compactFlowTitleClass(sectionStates.communication)}>沟通与测试</p>
            <ConsultationStageStatusCards
              values={form}
              classes={localClasses}
              section="communication"
              teacherOptions={teacherOptions}
              onTeacherChange={handleStageStatusTeacherChange}
            />
            <div className="mt-2 grid items-stretch gap-2 sm:grid-cols-2">
              <div className={cn(sectionBoxClass, 'flex h-full flex-col space-y-2')}>
                <label className="flex min-h-0 flex-1 scroll-mt-6 flex-col space-y-2 text-sm">
                  <span className={compactEditLabelClass}>沟通情况</span>
                  <textarea
                    value={form.need_detail}
                    onChange={(e) => updateField('need_detail', e.target.value)}
                    disabled={readOnly}
                    rows={6}
                    className={`${fieldClass} min-h-[8rem] flex-1 resize-none`}
                    placeholder="家长本次咨询目标、问题背景、正在沟通的细节"
                  />
                </label>
                <div className="grid shrink-0 gap-2">
                  <label className="space-y-2 text-sm">
                    <span className={compactEditLabelClass}>跟进 1</span>
                    <input
                      value={followUpLines[0]}
                      onChange={(e) => updateFollowUpLine(0, e.target.value)}
                      disabled={readOnly}
                      className={fieldClass}
                      placeholder="下一步跟进安排"
                    />
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className={compactEditLabelClass}>跟进 2</span>
                    <input
                      value={followUpLines[1]}
                      onChange={(e) => updateFollowUpLine(1, e.target.value)}
                      disabled={readOnly}
                      className={fieldClass}
                      placeholder="补充跟进备注"
                    />
                  </label>
                </div>
              </div>

              {(showTestFields || !readOnly) && (
                <div ref={testSectionRef} className={cn(sectionBoxClass, 'scroll-mt-6', testHighlighted && consultationJumpHighlightClass)}>
                  <div className="flex h-full flex-col space-y-2 text-sm">
                    <span className={compactEditLabelClass}>测试情况</span>
                    <div className="min-h-0 flex-1 overflow-hidden">
                      <div className="flex h-full snap-x snap-mandatory overflow-x-auto overscroll-x-contain pb-1 [scrollbar-width:thin]">
                        {testImagePages.map((page, pageIndex) => (
                          <div key={`test-image-page-${pageIndex}`} className="grid h-full min-w-full snap-start grid-cols-2 grid-rows-2 gap-2 pr-2">
                            {page.map((tile) => {
                              if (tile.type === 'image') {
                                return (
                                  <div key={`${tile.image.url}-${tile.index}`} className="group relative min-h-0 overflow-hidden rounded-xl border border-sky-100 bg-white shadow-sm dark:border-white/10 dark:bg-white/5">
                                    <button
                                      type="button"
                                      onClick={() => setPreviewImageIndex(tile.index)}
                                      className="block h-full w-full text-left"
                                      title={tile.image.filename || `测试情况图片 ${tile.index + 1}`}
                                      aria-label={`查看测试情况图片 ${tile.index + 1}`}
                                    >
                                      <img src={tile.image.url} alt={`测试情况图片 ${tile.index + 1}`} className="h-full w-full object-cover transition group-hover:scale-105" />
                                    </button>
                                    {!readOnly && record && (
                                      <button
                                        type="button"
                                        onClick={(event) => {
                                          event.preventDefault();
                                          event.stopPropagation();
                                          void handleDeleteTestImage(tile.index);
                                        }}
                                        disabled={deletingTestImageIndex === tile.index}
                                        className="absolute right-1 top-1 z-10 flex h-6 w-6 items-center justify-center rounded-full bg-rose-500 text-white shadow-md transition hover:bg-rose-600 disabled:cursor-wait disabled:opacity-60"
                                        aria-label={`删除测试情况图片 ${tile.index + 1}`}
                                      >
                                        <X size={13} strokeWidth={2.5} />
                                      </button>
                                    )}
                                  </div>
                                );
                              }
                              if (tile.type === 'upload') {
                                return (
                                  <label key={`test-image-upload-${pageIndex}`} className="flex min-h-0 cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-sky-200 bg-white/80 text-xs font-semibold text-sky-600 transition hover:border-sky-300 hover:bg-sky-50 dark:border-sky-400/20 dark:bg-white/5 dark:text-sky-300 dark:hover:bg-sky-400/10" aria-label="添加测试情况图片">
                                    <span className="flex h-9 w-9 items-center justify-center rounded-full border border-sky-200 bg-sky-50 text-lg leading-none text-sky-600 dark:border-sky-400/30 dark:bg-sky-400/10 dark:text-sky-300">
                                      +
                                    </span>
                                    <span>添加图片</span>
                                    <input
                                      type="file"
                                      accept="image/png,image/jpeg,image/webp"
                                      className="hidden"
                                      onChange={async (event) => {
                                        const file = event.target.files?.[0];
                                        if (!file || !record) return;
                                        const payload = new FormData();
                                        payload.append('image', file);
                                        const uploaded = await apiFetch<{ item: ConsultationRecord }>(`/api/consultations/${record.id}/test-images`, {
                                          method: 'POST',
                                          body: payload,
                                        });
                                        setForm(deriveConsultationFlowFromFields(toConsultationFormValues(normalizeConsultationRecord(uploaded.item))));
                                        event.currentTarget.value = '';
                                      }}
                                    />
                                  </label>
                                );
                              }
                              return (
                                <div key={`test-image-pending-upload-${pageIndex}`} className="flex min-h-0 items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 px-2 text-center text-xs font-semibold text-slate-400 dark:border-white/10 dark:bg-white/5 dark:text-slate-500">
                                  保存后添加
                                </div>
                              );
                            })}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            </section>

            {(showTrialFields || !readOnly) && (
              <div ref={trialSectionRef} className={cn(consultationFlowSectionClass(sectionStates.trial), 'min-h-[14rem] scroll-mt-6 md:order-2', trialHighlighted && consultationJumpHighlightClass)}>
                <p className={compactFlowTitleClass(sectionStates.trial)}>试听</p>
                <ConsultationStageStatusCards
                  values={form}
                  classes={localClasses}
                  section="trial"
                  teacherOptions={teacherOptions}
                  onTeacherChange={handleStageStatusTeacherChange}
                />
                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <label className="space-y-2 text-sm">
                    <span className={compactEditLabelClass}>对应班课</span>
                    <select
                      value={trialUsesManualClass ? '__other__' : form.trial_class_id ?? ''}
                      onChange={(e) => {
                        if (e.target.value === '__other__') {
                          setTrialManualClassActive(true);
                          setForm((current) => deriveConsultationFlowFromFields(moveConsultationStage({ ...current, trial_class_id: null, trial_class_manual: current.trial_class_manual || '' }, '待试听')));
                          return;
                        }
                        setTrialManualClassActive(false);
                        setForm((current) => deriveConsultationFlowFromFields({ ...current, trial_class_id: e.target.value ? Number(e.target.value) : null, trial_class_manual: '' }));
                      }}
                      disabled={readOnly}
                      className={fieldClass}
                    >
                      <option value="">请选择系统班级</option>
                      {assignableClassOptions.map((item) => (
                        <option key={item.id} value={item.id}>{getCurrentClassDisplayName(item)}</option>
                      ))}
                      <option value="__other__">其他：手动输入</option>
                    </select>
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className={compactEditLabelClass}>试听时间段</span>
                    <div className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-3">
                      <ArrowRight size={18} className="text-slate-400" />
                      <input value={form.trial_time_slot} onChange={(e) => updateField('trial_time_slot', e.target.value)} disabled={readOnly} className={fieldClass} placeholder="如：周六 10:00-12:00" />
                    </div>
                  </label>
                  {trialUsesManualClass && (
                    <label className="space-y-2 text-sm lg:col-span-2">
                      <span className={compactEditLabelClass}>其他班级</span>
                      <input value={form.trial_class_manual} onChange={(e) => updateField('trial_class_manual', e.target.value)} disabled={readOnly} className={fieldClass} placeholder="其他：________" />
                    </label>
                  )}
                  <label className="space-y-2 text-sm lg:col-span-2">
                    <span className={compactEditLabelClass}>试听反馈</span>
                    <textarea value={form.trial_feedback} onChange={(e) => updateField('trial_feedback', e.target.value)} disabled={readOnly} rows={4} className={`${fieldClass} resize-none`} placeholder="记录试听反馈、适配程度、下一步安排" />
                  </label>
                </div>
              </div>
            )}

            <section ref={successSectionRef} className={cn(consultationFlowSectionClass(sectionStates.result), 'min-h-[14rem] scroll-mt-6 space-y-3 md:order-4', successHighlighted && consultationJumpHighlightClass)}>
              <p className={compactFlowTitleClass(sectionStates.result)}>结果与备注</p>
            <ConsultationStageStatusCards
              values={form}
              classes={successClassOptions}
              section="result"
              teacherOptions={teacherOptions}
              onTeacherChange={handleStageStatusTeacherChange}
              onClassChange={(classId) => {
                handleSuccessClassChange(classId ? String(classId) : '');
              }}
            />
            {(showEndFields || !readOnly) && (
              <label ref={endSectionRef} className={cn('scroll-mt-6 space-y-2 rounded-xl p-2 text-sm transition', endHighlighted && consultationJumpHighlightClass)}>
                <span className={compactEditLabelClass}>咨询结束备注</span>
                <textarea value={form.end_note} onChange={(e) => updateField('end_note', e.target.value)} disabled={readOnly} rows={4} className={`${fieldClass} resize-none`} placeholder="可以为空；用于说明为什么结束、后续是否还可能重新沟通" />
              </label>
            )}

            {record && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-slate-950/70">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">录入时间</p>
                  <p className="mt-2 text-sm font-medium text-slate-700 dark:text-slate-200">{record?.created_at || '—'}</p>
                </div>
                <div className="rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-slate-950/70">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">结束时间</p>
                  <p className="mt-2 text-sm font-medium text-slate-700 dark:text-slate-200">{record?.ended_at || record?.updated_at || '—'}</p>
                </div>
              </div>
            )}
            </section>
          </div>
            </>
          )}

          <div className="mt-5 flex flex-col gap-3 border-t border-sky-100/80 pt-4 sm:mt-6 sm:flex-row sm:items-center sm:justify-between sm:pt-5 dark:border-white/10">
            <div className="text-sm text-slate-500 dark:text-slate-400">
              {readOnly ? '查看模式下可直接切换到编辑或删除。' : '保存后会刷新列表，不需要跳转到其他页面。'}
            </div>
            <div className="grid gap-3 sm:flex sm:flex-wrap sm:justify-end">
              {readOnly && canEdit && (
                <>
                  <button
                    type="button"
                    onClick={onRequestEdit}
                    className={`${workspaceSecondaryButtonClass} w-full sm:w-auto`}
                  >
                    <Pencil size={18} />
                    编辑
                  </button>
                  {onDelete && (
                    <button
                      type="button"
                      onClick={onDelete}
                      disabled={submitting}
                      className="inline-flex w-full items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-rose-200 bg-rose-50 px-5 py-3 font-semibold text-rose-600 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
                    >
                      <Trash2 size={18} />
                      删除
                    </button>
                  )}
                </>
              )}
              {readOnly ? (
                <button type="button" onClick={onClose} className={`${workspacePrimaryButtonClass} w-full sm:w-auto`}>
                  关闭
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={onClose}
                    className={`${workspaceSecondaryButtonClass} w-full sm:w-auto`}
                    disabled={submitting}
                  >
                    取消
                  </button>
                </>
              )}
            </div>
          </div>
        </form>
        {flowNodeDialog && (
          <ConsultationFlowNodeDialog
            open={Boolean(flowNodeDialog)}
            stage={flowNodeDialog.stage}
            values={form}
            teacherOptions={teacherOptions}
            setAsCurrent={flowNodeDialog.setAsCurrent}
            onClose={() => setFlowNodeDialog(null)}
            onSave={handleSaveFlowNodeDialog}
          />
        )}
        {enterClassDialogOpen && (
          <ConsultationEnterClassDialog
            open={enterClassDialogOpen}
            values={form}
            classes={successClassOptions}
            users={consultationEnterClassUsers}
            teacherBindingByClassId={{}}
            teachingTeacherUserId={consultationEnterClassTeacherUserId}
            creating={creatingSuccessClass}
            createError={successClassCreateError}
            onClose={() => setEnterClassDialogOpen(false)}
            onExistingClass={handleConfirmExistingClass}
            onCreateClass={handleCreateSuccessClass}
            onPending={handleMarkPendingSuccessClass}
          />
        )}
        {overResultDialogOpen && (
          <div className="fixed inset-0 z-[72] flex items-center justify-center bg-slate-950/35 px-4" onClick={(event) => event.target === event.currentTarget && setOverResultDialogOpen(false)}>
            <div className="w-full max-w-md rounded-[18px] border border-[#D9EEF7] bg-white p-5 shadow-[0_24px_70px_rgba(31,42,68,0.22)] dark:border-white/10 dark:bg-slate-950">
              <h3 className="text-lg font-extrabold text-[#1F2A44] dark:text-white">结束咨询</h3>
              <p className="mt-1 text-sm text-[#7188A6] dark:text-slate-400">选择这次咨询的结果。</p>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <button type="button" onClick={handleOverSuccess} className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-left text-sm font-extrabold text-emerald-700 transition hover:bg-emerald-100 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-200">
                  咨询成功
                </button>
                <button type="button" onClick={handleOverFailure} className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-left text-sm font-extrabold text-rose-700 transition hover:bg-rose-100 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-200">
                  咨询失败
                </button>
              </div>
              <button type="button" onClick={() => setOverResultDialogOpen(false)} className={`${workspaceSecondaryButtonClass} mt-4 w-full`}>
                取消
              </button>
            </div>
          </div>
        )}
        {previewImage && (
          <div
            className="fixed inset-0 z-[76] flex items-center justify-center bg-slate-950/78 px-4 py-6"
            onClick={(event) => event.target === event.currentTarget && closeImagePreview()}
          >
            <div className="relative flex h-full max-h-[88vh] w-full max-w-5xl items-center justify-center">
              <button
                type="button"
                onClick={closeImagePreview}
                className="absolute right-0 top-0 z-20 flex h-10 w-10 items-center justify-center rounded-full bg-white/95 text-slate-600 shadow-lg transition hover:bg-white hover:text-slate-900 dark:bg-slate-900/90 dark:text-slate-100"
                aria-label="关闭图片预览"
              >
                <X size={20} />
              </button>
              {previewImageCount > 1 && (
                <>
                  <button
                    type="button"
                    onClick={showPreviousImage}
                    className="absolute left-0 top-1/2 z-20 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-white/92 text-slate-700 shadow-lg transition hover:bg-white hover:text-slate-950 dark:bg-slate-900/90 dark:text-slate-100"
                    aria-label="上一张测试情况图片"
                  >
                    <ChevronLeft size={24} />
                  </button>
                  <button
                    type="button"
                    onClick={showNextImage}
                    className="absolute right-0 top-1/2 z-20 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-white/92 text-slate-700 shadow-lg transition hover:bg-white hover:text-slate-950 dark:bg-slate-900/90 dark:text-slate-100"
                    aria-label="下一张测试情况图片"
                  >
                    <ChevronRight size={24} />
                  </button>
                </>
              )}
              <figure className="flex h-full w-full flex-col items-center justify-center gap-3 px-12">
                <img
                  src={previewImage.url}
                  alt={previewImage.filename || `测试情况图片 ${(previewImageIndex ?? 0) + 1}`}
                  className="max-h-full max-w-full rounded-2xl bg-white object-contain shadow-[0_24px_80px_rgba(0,0,0,0.35)]"
                />
                <figcaption className="rounded-full bg-slate-950/55 px-3 py-1 text-xs font-semibold text-white">
                  {(previewImageIndex ?? 0) + 1} / {previewImageCount}
                </figcaption>
              </figure>
            </div>
          </div>
        )}
      </motion.div>
    </motion.div>
  );
};

export {
  buildConsultationBatchCreatePayload,
  ConsultationModal,
  normalizeConsultationTeacherOption,
  toConsultationFormValues,
};
