import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, ArrowRight, ArrowUp, CheckCircle2, Cpu, Pencil, Save, Trash2, Upload } from 'lucide-react';
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
  ConsultationFlowBar,
  ConsultationStatusLamp,
  clearConsultationResultStage,
  consultationFlowStages,
  consultationInputClass,
  consultationLabelClass,
  consultationPanelClass,
  consultationSurfaceClass,
  endConsultationValues,
  isConsultationEnded,
  isConsultationResultStage,
  moveConsultationStage,
  normalizeConsultationRecord,
  restoreConsultationValues,
  setConsultationResultStage,
  toggleConsultationStageLight,
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
  'rounded-[18px] border bg-white p-4 shadow-[0_10px_28px_rgba(31,42,68,0.05)] transition-colors dark:border-white/10 dark:bg-slate-950/72',
  state === 'active'
    ? 'border-sky-300 bg-sky-50/70 shadow-[0_16px_36px_rgba(14,165,233,0.12)] dark:border-sky-400/40 dark:bg-sky-500/10'
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
  test_taken: '',
  test_images: [],
  trial_taken: '',
  trial_time_slot: '',
  trial_class_id: null,
  trial_class_manual: '',
  trial_teacher: '',
  trial_feedback: '',
  success_class_id: null,
  success_class_manual: '',
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
}: {
  form: ConsultationFormValues;
  record: ConsultationRecord | null;
  classes: ClassItem[];
}) => {
  const customerWechatDone = form.completed_stages.includes('已加小客服微信') || form.flow_stage === '已加小客服微信';
  const teacherWechatDone = form.completed_stages.includes('已加对应教师微信') || form.flow_stage === '已加对应教师微信';
  const sectionStates = getConsultationFlowSectionStates(form);
  const trialClassName = getCurrentClassDisplayNameById(classes, form.trial_class_id);
  const successClassName = getCurrentClassDisplayNameById(classes, form.success_class_id);
  const resultLabel = form.flow_stage === '成功进班'
    ? '咨询成功'
    : form.flow_stage === '试听失败' || form.flow_stage === '咨询结束'
      ? '咨询失败'
      : '尚未定论';
  const value = (text?: string | null) => text?.trim() || '—';
  const readOnlyTwoColumnGridClass = 'grid-cols-[minmax(0,0.78fr)_minmax(0,1.22fr)]';

  return (
    <section className="grid gap-3 md:grid-cols-2">
      <div className={cn(consultationFlowSectionClass(sectionStates.base), 'min-h-[14rem]')}>
        <p className={compactFlowTitleClass(sectionStates.base)}>基础信息</p>
        <div className={`grid gap-x-3 gap-y-2 text-sm ${readOnlyTwoColumnGridClass}`}>
          <div><p className={compactReadLabelClass}>客服微信</p><p className="mt-0.5 flex items-center gap-1 font-semibold text-emerald-700 dark:text-emerald-300">{customerWechatDone ? '已添加' : '未添加'}{customerWechatDone ? <CheckCircle2 size={14} /> : null}</p></div>
          <div><p className={compactReadLabelClass}>教师微信</p><p className="mt-0.5 flex items-center gap-1 font-semibold text-emerald-700 dark:text-emerald-300">{teacherWechatDone ? '已添加' : '未添加'}{teacherWechatDone ? <CheckCircle2 size={14} /> : null}</p></div>
          <div><p className={compactReadLabelClass}>咨询日期</p><p className={compactReadValueClass}>{value(form.date)}</p></div>
          <div><p className={compactReadLabelClass}>家长微信</p><p className={compactReadValueClass}>{value(form.parent_wechat_name)}</p></div>
          <div><p className={compactReadLabelClass}>学生</p><p className={compactReadValueClass}>{value(form.child_name)}</p></div>
          <div><p className={compactReadLabelClass}>年级</p><p className={compactReadValueClass}>{value(form.grade)}</p></div>
          <div><p className={compactReadLabelClass}>咨询老师</p><p className={compactReadValueClass}>{value(form.receiving_teacher)}</p></div>
          <div><p className={compactReadLabelClass}>科目</p><p className={compactReadValueClass}>{value(form.consultation_subject)}</p></div>
          <div className="sm:col-span-2"><p className={compactReadLabelClass}>来源</p><p className={compactReadValueClass}>{value([form.source_channel, form.source_channel_note].filter(Boolean).join(' · '))}</p></div>
        </div>
      </div>

      <div className={cn(consultationFlowSectionClass(sectionStates.communication), 'min-h-[14rem]')}>
        <p className={compactFlowTitleClass(sectionStates.communication)}>沟通与测试</p>
        <div className="grid gap-3">
          <div>
            <p className={compactReadLabelClass}>沟通ing：情况说明</p>
            <p className={compactReadValueClass}>{value(form.need_detail)}</p>
          </div>
          <div>
            <div className="grid grid-cols-2 gap-2">
              <div><p className={compactReadLabelClass}>是否测试</p><p className={compactReadValueClass}>{value(form.test_taken)}</p></div>
              <div><p className={compactReadLabelClass}>图片数量</p><p className={compactReadValueClass}>{form.test_images.length ? `${form.test_images.length} 张` : '暂无'}</p></div>
            </div>
            {form.test_images.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {form.test_images.map((image, index) => (
                  <a
                    key={`${image.url}-${index}`}
                    href={image.url}
                    target="_blank"
                    rel="noreferrer"
                    className="group block overflow-hidden rounded-xl border border-sky-100 bg-sky-50 dark:border-white/10 dark:bg-white/5"
                  >
                    <img src={image.url} alt={`测试情况图片 ${index + 1}`} className="h-14 w-20 object-cover transition group-hover:scale-105" />
                  </a>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className={cn(consultationFlowSectionClass(sectionStates.trial), 'min-h-[14rem]')}>
        <p className={compactFlowTitleClass(sectionStates.trial)}>试听</p>
        <div className={`grid gap-x-3 gap-y-2 text-sm ${readOnlyTwoColumnGridClass}`}>
          <div><p className={compactReadLabelClass}>是否试听</p><p className={compactReadValueClass}>{value(form.trial_taken)}</p></div>
          <div><p className={compactReadLabelClass}>试听教师</p><p className={compactReadValueClass}>{value(form.trial_teacher)}</p></div>
          <div><p className={compactReadLabelClass}>对应班课</p><p className={compactReadValueClass}>{value(trialClassName || form.trial_class_manual)}</p></div>
          <div><p className={compactReadLabelClass}>试听时间段</p><p className={compactReadValueClass}>{value(form.trial_time_slot)}</p></div>
        </div>
        <div className="mt-3 border-t border-sky-50 pt-3 dark:border-white/10">
          <p className={compactReadLabelClass}>试听反馈</p>
          <p className={compactReadValueClass}>{value(form.trial_feedback)}</p>
        </div>
      </div>

      <div className={cn(consultationFlowSectionClass(sectionStates.result), 'min-h-[14rem]')}>
        <p className={compactFlowTitleClass(sectionStates.result)}>结果与备注</p>
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
              <div><p className={compactReadLabelClass}>最后更新</p><p className={compactReadValueClass}>{record.updated_at || '—'}</p></div>
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
  const [successManualClassActive, setSuccessManualClassActive] = useState(false);
  const [highlightedJumpStage, setHighlightedJumpStage] = useState<string>('');
  const formScrollRef = useRef<HTMLFormElement | null>(null);
  const baseInfoRef = useRef<HTMLElement | null>(null);
  const contentRef = useRef<HTMLElement | null>(null);
  const testSectionRef = useRef<HTMLDivElement | null>(null);
  const trialSectionRef = useRef<HTMLDivElement | null>(null);
  const successSectionRef = useRef<HTMLDivElement | null>(null);
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
      setHighlightedJumpStage('');
      setTrialManualClassActive(Boolean(initialConsultationForm.trial_class_manual && !initialConsultationForm.trial_class_id));
      setSuccessManualClassActive(Boolean(initialConsultationForm.success_class_manual && !initialConsultationForm.success_class_id));
    }
  }, [open, mode, initialConsultationForm]);

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

  const handleSuccessManualChange = (value: string) => {
    setForm((current) => {
      const next = { ...current, success_class_manual: value };
      return deriveConsultationFlowFromFields(value.trim() ? setConsultationResultStage(next, '成功进班') : next);
    });
  };

  const selectedTeacher = teacherOptions.find((option) => option.teacher_id === form.teacher_id);
  const teacherMatchedClasses = classes.filter((item) => classMatchesAssignedTeacher(item, selectedTeacher, currentUser));
  const assignableClassOptions = selectedTeacher && teacherMatchedClasses.length > 0 ? teacherMatchedClasses : classes;
  const trialUsesManualClass = trialManualClassActive || Boolean(form.trial_class_manual.trim() && !form.trial_class_id);
  const successUsesManualClass = successManualClassActive || Boolean(form.success_class_manual.trim() && !form.success_class_id);
  const baseInfoHighlighted = highlightedJumpStage === '已加小客服微信' || highlightedJumpStage === '已加对应教师微信';
  const communicationHighlighted = highlightedJumpStage === '正在沟通细节';
  const testHighlighted = highlightedJumpStage === '待测试';
  const trialHighlighted = highlightedJumpStage === '待试听' || highlightedJumpStage === '试听失败';
  const successHighlighted = highlightedJumpStage === '成功进班';
  const endHighlighted = highlightedJumpStage === '咨询结束';

  const fieldClass = `${consultationInputClass} ${readOnly ? 'cursor-default' : ''}`;
  const sectionBoxClass = 'rounded-xl border border-[#D9EEF7] bg-[#F9FDFF] px-3 py-3 dark:border-white/10 dark:bg-white/[0.03]';
  const compactStatusClass = (active: boolean) => cn(
    'inline-flex min-h-10 w-full items-center justify-between gap-3 rounded-xl border px-3 py-2 text-sm font-semibold transition',
    active
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-300'
      : 'border-slate-200 bg-slate-50 text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400',
    readOnly || stageFrozen ? 'cursor-default' : 'hover:border-emerald-300 hover:bg-emerald-100/70 dark:hover:bg-emerald-500/15',
  );
  const customerWechatDone = form.completed_stages.includes('已加小客服微信') || form.flow_stage === '已加小客服微信';
  const teacherWechatDone = form.completed_stages.includes('已加对应教师微信') || form.flow_stage === '已加对应教师微信';
  const showTestFields = form.flow_stage === '待测试' || form.test_taken || form.test_images.length > 0;
  const showTrialFields = form.flow_stage === '待试听' || form.flow_stage === '试听失败' || form.trial_taken || form.trial_time_slot || form.trial_class_id || form.trial_class_manual || form.trial_teacher || form.trial_feedback;
  const showSuccessFields = form.flow_stage === '成功进班' || form.success_class_id || form.success_class_manual;
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
        <div className="flex items-start justify-between gap-4 border-b border-[#EAF6FC] bg-white px-4 py-3.5 sm:px-6 sm:py-4 dark:border-white/10 dark:bg-slate-950/80">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.24em] text-[#0EA5E9]">Consultation</p>
            <h3 className="mt-1.5 text-xl font-extrabold tracking-tight text-[#1F2A44] sm:text-2xl dark:text-white">{titleMap[mode]}</h3>
            <p className="mt-1 max-w-2xl text-sm text-[#7188A6] dark:text-slate-400">
              {readOnly ? '记录详情只读展示，管理员和机构负责人可以在这里进入编辑。' : '先用快速录入整理信息，再确认下方结构化字段。'}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {!readOnly && (
              <button
                type="button"
                onClick={() => formScrollRef.current?.requestSubmit()}
                className={`${workspacePrimaryButtonClass} h-10 px-4 text-sm`}
                disabled={!canSaveConsultationDraft}
                title="Command+S / Ctrl+S"
              >
                <Save size={15} />
                {saveButtonLabel}
              </button>
            )}
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
            'absolute right-4 z-20 flex h-9 w-9 items-center justify-center rounded-full border border-[#D9EEF7] bg-white text-[#0EA5E9] shadow-[0_8px_20px_rgba(14,165,233,0.16)] transition hover:bg-sky-50 dark:border-white/10 dark:bg-slate-800 dark:text-sky-300 dark:hover:bg-slate-700 sm:right-6',
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
                  {readOnly ? '当前咨询的完整流程位置。' : '点击阶段框更新当前流程，未经历阶段保持灰色。'}
                  <ConsultationStatusLamp stage={form.flow_stage} />
                </span>
              </div>
            </div>
            {confirmRestoreOpen && (
              <div className="rounded-2xl border border-sky-100 bg-white p-4 shadow-[0_18px_45px_rgba(15,23,42,0.08)] dark:border-white/10 dark:bg-slate-950">
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
                editable={!readOnly && !stageFrozen}
                showJumpActions={!readOnly}
                showOver
                overDisabled={readOnly}
                onStageClick={(stage) => setForm((current) => toggleConsultationStageLight(current, stage))}
                onStageDoubleClick={(stage) => setForm((current) => moveConsultationStage(current, stage))}
                onResultChange={(stage) => setForm((current) => setConsultationResultStage(current, stage))}
                onResultClick={() => {
                  setForm((current) => (
                    isConsultationResultStage(current.flow_stage)
                      ? clearConsultationResultStage(current)
                      : setConsultationResultStage(current, '成功进班')
                  ));
                }}
                onResultDoubleClick={() => setForm((current) => setConsultationResultStage(current, '成功进班'))}
                onStageJump={handleStageJump}
                onOverClick={() => {
                  if (readOnly) return;
                  if (stageFrozen) {
                    setConfirmRestoreOpen(true);
                    return;
                  }
                  setForm((current) => endConsultationValues(current));
                }}
              />
            </div>
          </section>

          {readOnly ? (
            <ConsultationReadOnlyReport form={form} record={record} classes={classes} />
          ) : (
            <>
          {!readOnly && (
            <section className={`${consultationPanelClass} mb-4 grid gap-3 p-3.5 lg:grid-cols-[8rem_minmax(0,1fr)_auto] lg:items-center sm:p-4`}>
              <div>
                <h4 className="text-sm font-extrabold text-[#1F2A44] dark:text-white">快速录入</h4>
                <p className="mt-1 text-xs text-[#7188A6] dark:text-slate-400">自然描述可一键解析。</p>
              </div>
              <textarea
                value={quickEntry}
                onChange={(e) => setQuickEntry(e.target.value)}
                rows={1}
                className={`${consultationInputClass} min-h-10 resize-none`}
                placeholder="例如：张妈妈，五年级数学，张裕空转介绍，雷文浩接待，想补基础"
              />
              <div className="flex flex-wrap gap-2 lg:justify-end">
                <button type="button" onClick={handleQuickParse} className={`${workspacePrimaryButtonClass} h-10 px-3 py-2 text-sm`}>
                  <Cpu size={15} />
                  智能解析
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setQuickEntry('');
                    setParseFeedback('');
                  }}
                  className={`${workspaceSecondaryButtonClass} h-10 px-3 py-2 text-sm`}
                >
                  清空
                </button>
              </div>
              <p className="text-xs text-[#7188A6] dark:text-slate-400 lg:col-span-3">
                {parseFeedback || '解析后可确认并保存。'}
              </p>
            </section>
          )}

          <datalist id="consultation-grade-options">
            {consultationGradeOptions.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>

          <div className="grid gap-3 md:grid-cols-2">
            <section ref={baseInfoRef} className={cn(consultationFlowSectionClass(sectionStates.base), 'min-h-[14rem] scroll-mt-6', baseInfoHighlighted && consultationJumpHighlightClass)}>
            <p className={compactFlowTitleClass(sectionStates.base)}>基础信息</p>
            <div className="grid grid-cols-[minmax(0,0.82fr)_minmax(0,1.18fr)] gap-2">
              <button
                type="button"
                onClick={() => setForm((current) => toggleConsultationStageLight(current, '已加小客服微信'))}
                disabled={readOnly || stageFrozen}
                className={cn(compactStatusClass(customerWechatDone), 'min-w-0 px-3')}
              >
                <span className="min-w-0 truncate">客服微信：{customerWechatDone ? '已添加' : '未添加'}</span>
                {customerWechatDone ? <CheckCircle2 size={18} className="shrink-0" /> : null}
              </button>
              <label className={cn(compactStatusClass(teacherWechatDone), 'relative min-w-0 p-0')}>
                <span className="pointer-events-none absolute inset-x-3 top-1/2 z-10 min-w-0 -translate-y-1/2 truncate text-center">
                  负责老师VX：{form.receiving_teacher || '未选择'}
                </span>
                <select
                  value={form.teacher_id}
                  onChange={(e) => handleTeacherChange(e.target.value)}
                  disabled={readOnly || stageFrozen}
                  className="h-full min-h-10 w-full cursor-pointer appearance-none rounded-2xl bg-transparent px-3 text-transparent outline-none"
                  aria-label="选择负责老师"
                >
                  <option value="">请选择老师</option>
                  {teacherOptions.map((option) => (
                    <option key={option.teacher_id} value={option.teacher_id}>{option.display_name}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className={`${compactFieldGridClass} mt-3`}>
              <label className="space-y-2 text-sm">
                <span className={compactEditLabelClass}>日期</span>
                <input type="date" value={form.date} onChange={(e) => updateField('date', e.target.value)} disabled={readOnly} className={fieldClass} />
              </label>
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
            </div>

            <div className={`${compactFieldGridClass} mt-3`}>
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

            <section ref={contentRef} className={cn(consultationFlowSectionClass(sectionStates.communication), 'min-h-[14rem] scroll-mt-6 space-y-3', communicationHighlighted && consultationJumpHighlightClass)}>
            <p className={compactFlowTitleClass(sectionStates.communication)}>沟通与测试</p>
            <label className="scroll-mt-6 space-y-2 text-sm">
              <span className={compactEditLabelClass}>沟通ing：情况说明</span>
              <textarea
                value={form.need_detail}
                onChange={(e) => updateField('need_detail', e.target.value)}
                disabled={readOnly}
                rows={5}
                className={`${fieldClass} resize-none`}
                placeholder="家长本次咨询目标、问题背景、正在沟通的细节"
              />
            </label>

            {(showTestFields || !readOnly) && (
              <div ref={testSectionRef} className={cn(sectionBoxClass, 'scroll-mt-6', testHighlighted && consultationJumpHighlightClass)}>
                <h5 className="text-sm font-bold tracking-tight text-slate-900 dark:text-white">测试</h5>
                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <label className="space-y-2 text-sm">
                    <span className={compactEditLabelClass}>是否测试</span>
                    <select value={form.test_taken} onChange={(e) => updateField('test_taken', e.target.value)} disabled={readOnly} className={fieldClass}>
                      <option value="">未记录</option>
                      <option value="是">是</option>
                      <option value="否">否</option>
                    </select>
                  </label>
                  <div className="space-y-2 text-sm">
                    <span className={compactEditLabelClass}>测试情况图片</span>
                    {!readOnly && record ? (
                      <label className={`${workspaceSecondaryButtonClass} w-full cursor-pointer justify-center`}>
                        <Upload size={17} />
                        添加图片
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
                    ) : (
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400">查看下方已上传图片</div>
                    )}
                  </div>
                </div>
                {form.test_images.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {form.test_images.map((image, index) => (
                      <a key={`${image.url}-${index}`} href={image.url} target="_blank" rel="noreferrer" className={workspaceSecondaryButtonClass}>
                        查看图片 {index + 1}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            )}

            </section>

            {(showTrialFields || !readOnly) && (
              <div ref={trialSectionRef} className={cn(consultationFlowSectionClass(sectionStates.trial), 'min-h-[14rem] scroll-mt-6', trialHighlighted && consultationJumpHighlightClass)}>
                <p className={compactFlowTitleClass(sectionStates.trial)}>试听</p>
                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <label className="space-y-2 text-sm">
                    <span className={compactEditLabelClass}>是否试听</span>
                    <select value={form.trial_taken} onChange={(e) => updateField('trial_taken', e.target.value)} disabled={readOnly} className={fieldClass}>
                      <option value="">未记录</option>
                      <option value="是">是</option>
                      <option value="否">否</option>
                    </select>
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className={compactEditLabelClass}>试听教师</span>
                    <select value={form.trial_teacher} onChange={(e) => updateField('trial_teacher', e.target.value)} disabled={readOnly} className={fieldClass}>
                      <option value="">请选择试听教师</option>
                      {teacherOptions.map((option) => (
                        <option key={option.teacher_id} value={option.display_name}>{option.display_name}</option>
                      ))}
                    </select>
                  </label>
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

            <section className={cn(consultationFlowSectionClass(sectionStates.result), 'min-h-[14rem] scroll-mt-6 space-y-3')}>
              <p className={compactFlowTitleClass(sectionStates.result)}>结果与备注</p>
            {(showSuccessFields || !readOnly) && (
              <div ref={successSectionRef} className={cn(sectionBoxClass, 'scroll-mt-6', successHighlighted && consultationJumpHighlightClass)}>
                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <label className="space-y-2 text-sm">
                    <span className={compactEditLabelClass}>班级</span>
                    <select
                      value={successUsesManualClass ? '__other__' : form.success_class_id ?? ''}
                      onChange={(e) => {
                        if (e.target.value === '__other__') {
                          setSuccessManualClassActive(true);
                          setForm((current) => deriveConsultationFlowFromFields(setConsultationResultStage({ ...current, success_class_id: null, success_class_manual: current.success_class_manual || '' }, '成功进班')));
                          return;
                        }
                        setSuccessManualClassActive(false);
                        handleSuccessClassChange(e.target.value);
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
                  {successUsesManualClass && (
                    <label className="space-y-2 text-sm">
                      <span className={compactEditLabelClass}>其他班级</span>
                      <input value={form.success_class_manual} onChange={(e) => handleSuccessManualChange(e.target.value)} disabled={readOnly} className={fieldClass} placeholder="其他：________" />
                    </label>
                  )}
                </div>
              </div>
            )}

            {(showEndFields || !readOnly) && (
              <label ref={endSectionRef} className={cn('scroll-mt-6 space-y-2 rounded-xl p-2 text-sm transition', endHighlighted && consultationJumpHighlightClass)}>
                <span className={compactEditLabelClass}>咨询结束备注</span>
                <textarea value={form.end_note} onChange={(e) => updateField('end_note', e.target.value)} disabled={readOnly} rows={4} className={`${fieldClass} resize-none`} placeholder="可以为空；用于说明为什么结束、后续是否还可能重新沟通" />
              </label>
            )}

            <label className="space-y-2 text-sm">
              <span className={compactEditLabelClass}>跟进备注（内部）</span>
              <textarea value={form.follow_up_note} onChange={(e) => updateField('follow_up_note', e.target.value)} disabled={readOnly} rows={3} className={`${fieldClass} resize-none`} placeholder="补充后续跟进安排或内部提醒" />
            </label>

            {record && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-slate-950/70">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">录入时间</p>
                  <p className="mt-2 text-sm font-medium text-slate-700 dark:text-slate-200">{record?.created_at || '—'}</p>
                </div>
                <div className="rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-slate-950/70">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">最后更新</p>
                  <p className="mt-2 text-sm font-medium text-slate-700 dark:text-slate-200">{record?.updated_at || '—'}</p>
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
