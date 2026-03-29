/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import Hls from 'hls.js';
import {
  Home,
  LayoutDashboard,
  PlusCircle,
  Library,
  Database,
  CalendarDays,
  Settings,
  Search,
  Bell,
  User,
  MessageSquare,
  FileText,
  Download,
  Trash2,
  Eye,
  EyeOff,
  Pencil,
  Upload,
  Cpu,
  CheckCircle2,
  MoreVertical,
  Menu,
  Filter,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  ShieldCheck,
  Moon,
  Sun,
  X,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { CourseCalendarPage } from './CourseCalendarPage';

// --- Types ---

type Role = 'owner' | 'admin' | 'member';
type Page = 'dashboard' | 'review-generation' | 'consultation' | 'calendar' | 'classes' | 'accounts' | 'settings';
type LandingLegalDocumentKey = 'privacy' | 'terms';

interface Lesson {
  id: number;
  date: string;
  subject: string;
  grade: string;
  topic: string;
  summary: string;
  weak_points: string;
  pdf_path: string;
  class_id: number | null;
  created_at: string;
}

interface Stats {
  total_lessons: number;
  month_lessons: number;
  total_pdfs: number;
  total_questions: number;
}

interface ApiSettings {
  provider: string;
}

interface ClassItem {
  id: number;
  name: string;
  subject: string;
  grade: string;
  teacher_name?: string;
  teacher_email?: string;
  teacher_user_id?: number | null;
  lesson_count?: number;
}

interface ConsultationRecord {
  id: number;
  date: string;
  parent_wechat_name: string;
  child_name: string;
  grade: string;
  receiving_teacher: string;
  teacher_id: string;
  teacher_display_name?: string;
  consultation_subject: string;
  need_detail: string;
  source_channel: string;
  source_channel_note: string;
  screenshot: string;
  follow_up_status: string;
  follow_up_note: string;
  created_at: string;
  updated_at: string;
}

type ConsultationFormValues = Omit<ConsultationRecord, 'id' | 'created_at' | 'updated_at'>;

interface ConsultationTeacherOption {
  teacher_id: string;
  display_name: string;
  aliases: string[];
}

interface CurrentUser {
  id: number;
  username: string;
  display_name: string;
  role: Role;
  status: string;
  organization_id: number;
  organization_name: string;
  created_at: string;
}

interface RegistrationRequestItem {
  id: number;
  username: string;
  display_name: string;
  organization_name: string;
  status: string;
  created_at: string;
}

interface UserItem {
  id: number;
  name: string;
  org: string;
  role: Role;
}

interface ClassFormValues {
  name: string;
  subject: string;
  grade: string;
  teacher_name: string;
}

type LoadPageResult =
  | { status: 'success' }
  | { status: 'stale' }
  | { status: 'refresh-error'; error: Error };

const GRADE_NORMALIZATION_RULES: Array<[string, string]> = [
  ['一年级', '一年级'],
  ['二年级', '二年级'],
  ['三年级', '三年级'],
  ['四年级', '四年级'],
  ['五年级', '五年级'],
  ['六年级', '六年级'],
  ['初一', '初一'],
  ['初二', '初二'],
  ['初三', '初三'],
  ['高一', '高一'],
  ['高二', '高二'],
  ['高三', '高三'],
];

const NORMALIZATION_EXAMPLES: Array<[string, string]> = [
  ['6年级2班', '六年级 2 班'],
  ['六年级二班', '六年级 2 班'],
  ['六年2班', '六年级 2 班'],
];

function getRoleLabel(role: Role): string {
  if (role === 'owner') return '最高权限账号';
  if (role === 'admin') return '管理员';
  return '机构成员';
}

function createEmptyClassForm(): ClassFormValues {
  return {
    name: '',
    subject: '',
    grade: '',
    teacher_name: '',
  };
}

function toClassFormValues(item: ClassItem): ClassFormValues {
  return {
    name: item.name || '',
    subject: item.subject || '',
    grade: item.grade || '',
    teacher_name: item.teacher_name || '',
  };
}

const normalizeClassNameInput = (value: string): string => {
  const trimmed = value.trim();
  if (!trimmed) {
    return '';
  }

  const normalized = trimmed
    .replace(/\s+/g, '')
    .replace(/^6年级/, '六年级')
    .replace(/^5年级/, '五年级')
    .replace(/^4年级/, '四年级')
    .replace(/^3年级/, '三年级')
    .replace(/^2年级/, '二年级')
    .replace(/^1年级/, '一年级')
    .replace(/^六年(?=\d+班$)/, '六年级')
    .replace(/^五年(?=\d+班$)/, '五年级')
    .replace(/^四年(?=\d+班$)/, '四年级')
    .replace(/^三年(?=\d+班$)/, '三年级')
    .replace(/^二年(?=\d+班$)/, '二年级')
    .replace(/^一年(?=\d+班$)/, '一年级')
    .replace(/一班$/, '1班')
    .replace(/二班$/, '2班')
    .replace(/三班$/, '3班')
    .replace(/四班$/, '4班')
    .replace(/五班$/, '5班')
    .replace(/六班$/, '6班');

  const gradePrefix = GRADE_NORMALIZATION_RULES.find(([alias]) => normalized.startsWith(alias))?.[1];
  const match = normalized.match(/^(一年级|二年级|三年级|四年级|五年级|六年级|初一|初二|初三|高一|高二|高三)(\d+)班$/);
  if (!match || !gradePrefix) {
    return trimmed;
  }

  return `${gradePrefix} ${match[2]} 班`;
};

function areClassIdListsEqual(left: number[], right: number[]): boolean {
  if (left.length !== right.length) {
    return false;
  }

  return left.every((value, index) => value === right[index]);
}

export function resolveAssignmentRollbackClassIds(
  currentClassIds: number[],
  previousClassIds: number[],
  failedNextClassIds: number[],
): number[] {
  return areClassIdListsEqual(currentClassIds, failedNextClassIds) ? previousClassIds : currentClassIds;
}

export function resolveTeacherBindingRollbackClassItem(
  currentItem: ClassItem,
  failedNextTeacherUserId: number,
  previousTeacherUserId: number | null,
  previousTeacherName: string,
): ClassItem {
  if (currentItem.teacher_user_id !== failedNextTeacherUserId) {
    return currentItem;
  }

  return {
    ...currentItem,
    teacher_name: previousTeacherName,
    teacher_user_id: previousTeacherUserId,
  };
}

export function resolveTeacherBindingRollbackTeacherBindings(
  currentTeacherBindingByClassId: Record<number, number | null>,
  classId: number,
  previousTeacherUserId: number | null,
  failedNextTeacherUserId: number,
): Record<number, number | null> {
  if (currentTeacherBindingByClassId[classId] !== failedNextTeacherUserId) {
    return currentTeacherBindingByClassId;
  }

  return {
    ...currentTeacherBindingByClassId,
    [classId]: previousTeacherUserId,
  };
}

function getRoleBadgeClass(role: Role): string {
  if (role === 'owner') {
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300';
  }
  if (role === 'admin') {
    return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300';
  }
  return 'border-slate-200 bg-white text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300';
}

const LANDING_LEGAL_DOCUMENTS: Record<
  LandingLegalDocumentKey,
  {
    title: string;
    eyebrow: string;
    summary: string;
    updatedAt: string;
    sections: Array<{ title: string; paragraphs: string[] }>;
  }
> = {
  privacy: {
    title: '隐私政策',
    eyebrow: 'PRIVACY POLICY',
    summary:
      '本政策说明 Starain 在账号申请、课堂材料上传、AI 处理与教学交付过程中如何收集、使用、保存与保护相关信息。',
    updatedAt: '2026-03-27',
    sections: [
      {
        title: '我们如何收集和使用信息',
        paragraphs: [
          '当你申请注册、登录或使用机构账号时，我们会收集并使用你主动提交的账号信息、显示名称、机构名称以及必要的身份校验信息，用于完成账号开通、权限管理与服务支持。',
          '当你使用产品处理教学内容时，我们可能处理课堂录音、笔记、PDF、课程主题、题目素材以及对应的 AI 生成结果，用于生成课后复习资料、题库内容、讲义草稿和相关教学交付材料。',
        ],
      },
      {
        title: 'AI 处理与第三方服务',
        paragraphs: [
          '在你启用相关 AI 能力时，系统可能会将完成处理所必需的教学材料发送给当前配置的模型服务提供方，例如 OpenAI、DeepSeek 或其他经系统接入的服务，用于生成摘要、题目或结构化内容。',
          '我们会尽量控制发送范围，仅处理与你所选功能直接相关的内容，并要求相关服务链路遵循适用的数据保护与安全要求。',
        ],
      },
      {
        title: '信息保存与安全保护',
        paragraphs: [
          '你的账号信息、机构信息、课堂材料和生成结果可能被保存在本地数据库、文件存储或部署环境中，用于维持服务连续性、历史记录查看、结果下载以及后续教学复用。',
          '我们会采取访问控制、权限隔离、最小化暴露和必要的运维措施保护相关信息，但你也应避免上传与教学服务无关或超出授权范围的敏感内容。',
        ],
      },
      {
        title: '你的权利与联系我们',
        paragraphs: [
          '你可以基于适用法律和服务能力，申请查询、更正、删除相关账号信息，或就账号停用、机构权限和数据处理问题与我们联系。',
          '如果你对本政策或个人信息处理有疑问，可通过产品运营或机构对接渠道联系 Starain 团队，我们会在合理范围内进行说明与处理。',
        ],
      },
    ],
  },
  terms: {
    title: '服务条款',
    eyebrow: 'TERMS OF SERVICE',
    summary:
      '本条款用于说明你访问和使用 Starain 时的账号规则、服务边界、内容责任与争议处理方式。',
    updatedAt: '2026-03-27',
    sections: [
      {
        title: '账号注册与使用',
        paragraphs: [
          '你应确保注册、申请或机构开通时提供的信息真实、完整、可持续更新，并妥善保管账号、密码与登录凭证。因账号保管不当造成的风险与损失，由账号持有人或所属机构承担相应责任。',
          '未经授权，你不得冒用他人身份、共享受限账号、绕过审批流程或以任何方式干扰平台的正常使用秩序。',
        ],
      },
      {
        title: '服务内容与使用边界',
        paragraphs: [
          'Starain 当前提供并持续迭代的能力包括但不限于课后复习资料生成、题库沉淀、教学材料整理以及其他面向学校、机构和教学团队的 AI 教学交付支持能力。',
          '我们会持续优化产品功能，但不承诺所有展示中的方案模块都已在当前版本全面上线，也不保证服务在任何时间点都完全不中断。',
        ],
      },
      {
        title: '上传内容责任',
        paragraphs: [
          '你应确保上传、录入或提交的课堂录音、笔记、PDF、题目和其他材料具备合法来源，并已取得开展教学处理、内部使用或授权共享所需的权利。',
          '对于违反法律法规、侵犯第三方权利或明显超出教学使用场景的内容，我们有权拒绝处理、限制访问或采取其他必要措施。',
        ],
      },
      {
        title: 'AI 生成内容说明',
        paragraphs: [
          'AI 生成结果仅作为教学支持与效率工具，不当然构成专业、准确或适用于所有场景的最终结论。你应结合课程目标、学生情况和人工审阅进行必要校对后再对外使用。',
          '因模型局限、素材质量或上下文缺失导致的偏差、遗漏或不准确内容，平台将在合理范围内持续改进，但不对未经人工复核直接使用所引发的后果承担无限责任。',
        ],
      },
      {
        title: '争议解决',
        paragraphs: [
          '本条款的订立、履行与解释适用中华人民共和国相关法律法规。',
          '如因使用本服务发生争议，双方应优先友好协商；协商不成的，可向服务提供方所在地有管辖权的人民法院提起诉讼，或依双方另行签署的书面协议执行。',
        ],
      },
    ],
  },
};

export function getLandingLegalPageFromHash(hash: string): LandingLegalDocumentKey | null {
  if (hash === '#privacy-policy') {
    return 'privacy';
  }
  if (hash === '#terms-of-service') {
    return 'terms';
  }
  return null;
}

// --- API helper ---

function getToken(): string {
  return localStorage.getItem('xr_token') || '';
}

async function apiFetch<T = unknown>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const token = getToken();
  const res = await fetch(path, {
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { 'X-Auth-Token': token } : {}),
      ...(options?.headers ?? {}),
    },
    ...options,
  });
  if (res.status === 401) {
    localStorage.removeItem('xr_token');
    window.location.reload();
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error((err as { error?: string }).error || res.statusText);
  }
  return res.json() as Promise<T>;
}

function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

function getInitialDarkModePreference(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }

  try {
    const saved = window.localStorage?.getItem?.('xr_dark');
    if (saved !== null && saved !== undefined) {
      return saved === 'true';
    }
  } catch {
    // Ignore storage access issues and fall back to the system preference.
  }

  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
}

function getTodayIsoDate(): string {
  const now = new Date();
  const localDate = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return localDate.toISOString().slice(0, 10);
}

function shiftIsoDate(dateString: string, days: number): string {
  const base = new Date(`${dateString}T12:00:00`);
  base.setDate(base.getDate() + days);
  return base.toISOString().slice(0, 10);
}

function getLatestLessonDate(lessons: Lesson[]): string {
  if (lessons.length === 0) {
    return getTodayIsoDate();
  }

  return lessons.reduce((latest, lesson) => (lesson.date > latest ? lesson.date : latest), lessons[0].date);
}

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
): Record<string, string> {
  const parsed: Record<string, string> = {
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
      if (parsed.parent_wechat_name) {
        cleaned = cleaned.replace(parsed.parent_wechat_name, '');
      }
      if (parsed.child_name) {
        cleaned = cleaned.replace(parsed.child_name, '');
      }
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
      if (teacherOption) {
        for (const candidate of [teacherOption.display_name, teacherOption.teacher_id, ...teacherOption.aliases]) {
          cleaned = cleaned.replace(candidate, '');
        }
      }
      return cleaned.replace(/(接待|负责|咨询|家长微信|学生姓名|孩子姓名|来源渠道|来源|备注|妈妈|爸爸)[:：]?/g, '').trim();
    })
    .filter((segment) => segment && /想|要|补|提升|提高|咨询|规划|准备|薄弱|需要|跟进|联系/.test(segment));

  if (cleanedSegments.length > 0) {
    parsed.need_detail = cleanedSegments.join('，');
  }

  return parsed;
}

const consultationStatusOptions = ['待跟进', '跟进中', '已跟进', '已完成'];

function consultationStatusClass(status: string): string {
  if (status === '待跟进') return 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300';
  if (status === '跟进中') return 'bg-sky-50 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300';
  if (status === '已跟进') return 'bg-violet-50 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300';
  if (status === '已完成') return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300';
  return 'bg-slate-100 text-slate-500 dark:bg-white/5 dark:text-slate-400';
}
const consultationGradeOptions = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三'];
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
  校区到访: ['校区到访', '到访', '上门', '线下到访'],
  其他: ['其他'],
};
const consultationSubjectOptions = ['数学', '奥数', '语文', '英语', '物理', '化学', '生物', '科学'];
const gradeNumeralMap: Record<string, string> = {
  '1': '一',
  '2': '二',
  '3': '三',
  '4': '四',
  '5': '五',
  '6': '六',
  '7': '七',
  '8': '八',
  '9': '九',
  '10': '十',
  '11': '十一',
  '12': '十二',
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
  follow_up_status: '待跟进',
  follow_up_note: '',
};

function toConsultationFormValues(record?: ConsultationRecord | null): ConsultationFormValues {
  if (!record) {
    return consultationFormDefaults;
  }

  return {
    date: record.date || consultationFormDefaults.date,
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
    follow_up_status: record.follow_up_status || consultationFormDefaults.follow_up_status,
    follow_up_note: record.follow_up_note ?? '',
  };
}

function normalizeConsultationRecord(record: ConsultationRecord): ConsultationRecord {
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

function buildConsultationTeacherDirectory(records: ConsultationRecord[]): Record<string, string> {
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

function getConsultationTeacherName(record: ConsultationRecord, teacherDirectory: Record<string, string>): string {
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

function getConsultationStudentMeta(record: ConsultationRecord): string {
  const childName = record.child_name?.trim();
  return childName ? `学生姓名：${childName}` : '学生姓名待补充';
}

function getConsultationSourceLabel(record: ConsultationRecord): string {
  const sourceChannel = record.source_channel || '未标注来源渠道';
  const trimmedSourceChannel = sourceChannel.trim();
  const sourceChannelNote = record.source_channel_note?.trim();
  if (trimmedSourceChannel === '未标注来源渠道') {
    return trimmedSourceChannel;
  }
  return sourceChannelNote ? `${trimmedSourceChannel} · ${sourceChannelNote}` : trimmedSourceChannel;
}

const workspacePageClass = 'px-6 py-6 md:px-8 md:py-8 xl:px-10 xl:py-10';
const workspaceCardClass =
  'rounded-[1.75rem] border border-sky-100/90 bg-white/88 shadow-[0_22px_54px_rgba(47,128,237,0.08)] backdrop-blur-sm dark:border-white/10 dark:bg-slate-950/78 dark:shadow-[0_24px_60px_rgba(2,6,23,0.52)]';
const workspaceSoftCardClass =
  'rounded-[1.5rem] border border-sky-100 bg-[linear-gradient(180deg,rgba(255,255,255,0.94)_0%,rgba(239,248,255,0.78)_100%)] shadow-[0_14px_36px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)] dark:shadow-[0_18px_40px_rgba(2,6,23,0.44)]';
const workspaceFieldClass =
  'w-full rounded-xl border border-sky-200 bg-white/92 px-4 py-2.5 text-sm text-slate-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)] outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100 placeholder:text-slate-400 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100 dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] dark:focus:border-sky-500 dark:focus:ring-sky-500/15 dark:placeholder:text-slate-500';
const workspacePrimaryButtonClass =
  'inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl bg-sky-600 px-5 py-3 font-semibold text-white shadow-[0_16px_40px_rgba(34,199,232,0.24)] transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-60';
const workspaceSecondaryButtonClass =
  'inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-sky-200 bg-white px-5 py-3 font-semibold text-slate-700 shadow-sm transition hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:hover:bg-white/10';
const workspaceGhostButtonClass =
  'inline-flex items-center justify-center gap-2 rounded-xl bg-sky-50/80 px-4 py-2.5 font-medium text-slate-600 transition hover:bg-sky-100 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10';
const workspaceSectionTitleClass = 'text-2xl font-bold tracking-tight text-slate-900 dark:text-white';
const workspaceSectionTextClass = 'text-sm leading-relaxed text-slate-500 dark:text-slate-400';
const landingHeroVideoStreamUrl =
  'https://stream.mux.com/ef2TghmWccnsK54qnxtFWjv36zXb01cK02CAfgDNQMgn4.m3u8';

function HeroBackgroundVideo() {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) {
      return;
    }

    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = landingHeroVideoStreamUrl;
      return () => {
        video.removeAttribute('src');
        video.load();
      };
    }

    if (!Hls.isSupported()) {
      return;
    }

    const hls = new Hls({
      enableWorker: true,
      lowLatencyMode: true,
    });

    hls.loadSource(landingHeroVideoStreamUrl);
    hls.attachMedia(video);

    return () => {
      hls.destroy();
      video.removeAttribute('src');
      video.load();
    };
  }, []);

  return (
    <div className="absolute inset-0">
      <video
        ref={videoRef}
        className="h-full w-full object-cover opacity-[0.32] saturate-[0.9] dark:opacity-[0.26]"
        autoPlay
        muted
        loop
        playsInline
        preload="metadata"
        aria-hidden="true"
        data-stream-src={landingHeroVideoStreamUrl}
      />
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(248,251,255,0.3)_0%,rgba(238,246,255,0.78)_58%,rgba(238,246,255,0.94)_100%)] dark:bg-[linear-gradient(180deg,rgba(2,6,23,0.28)_0%,rgba(15,23,42,0.72)_58%,rgba(15,23,42,0.9)_100%)]" />
    </div>
  );
}

// --- Components ---

export const SidebarAccountSheet = ({
  currentUser,
  open,
  onClose,
  onLogout,
  onOpenSettings,
  onProfileUpdated,
}: {
  currentUser: CurrentUser;
  open: boolean;
  onClose: () => void;
  onLogout: () => void;
  onOpenSettings: () => void;
  onProfileUpdated?: (username: string, displayName: string) => void;
}) => {
  const [editing, setEditing] = useState(false);
  const [editUsername, setEditUsername] = useState('');
  const [editDisplayName, setEditDisplayName] = useState('');
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState('');

  const startEdit = () => {
    setEditUsername(currentUser.username);
    setEditDisplayName(currentUser.display_name);
    setEditError('');
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditError('');
  };

  const saveEdit = async () => {
    if (!editUsername.trim() || !editDisplayName.trim()) {
      setEditError('用户名和昵称不能为空');
      return;
    }
    setSaving(true);
    setEditError('');
    try {
      await apiFetch('/api/profile', {
        method: 'PUT',
        body: JSON.stringify({ username: editUsername.trim(), display_name: editDisplayName.trim() }),
      });
      onProfileUpdated?.(editUsername.trim(), editDisplayName.trim());
      setEditing(false);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return null;
  }

  const sheet = (
    <div className="fixed inset-0 z-[70]" onClick={onClose}>
      <div className="absolute inset-0 bg-slate-950/28" />
      <div className="absolute left-4 bottom-4 w-[calc(100vw-2rem)] max-w-sm" onClick={(e) => e.stopPropagation()}>
        <div className={`${workspaceCardClass} p-6`}>
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-4 min-w-0">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 via-cyan-500 to-blue-500 text-xl font-bold text-white shadow-[0_16px_32px_rgba(34,199,232,0.25)]">
                {currentUser.display_name.slice(0, 1).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="truncate text-xl font-semibold text-slate-900 dark:text-slate-100">{currentUser.display_name}</p>
                <p className="truncate text-sm text-slate-500 dark:text-slate-400">@{currentUser.username}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-sky-50 text-slate-500 transition-colors hover:bg-sky-100 hover:text-slate-700 dark:bg-white/5 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-slate-200"
              aria-label="关闭账号面板"
            >
              ×
            </button>
          </div>

          {editing ? (
            <div className="mt-5 space-y-3">
              <div className="space-y-1.5">
                <label className="text-xs text-slate-500 dark:text-slate-400">用户名 <span className="text-slate-400 dark:text-slate-500">· 登录用</span></label>
                <input
                  type="text"
                  value={editUsername}
                  onChange={(e) => setEditUsername(e.target.value)}
                  className={`${workspaceFieldClass} w-full`}
                  placeholder="登录用"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-slate-500 dark:text-slate-400">昵称 <span className="text-slate-400 dark:text-slate-500">· 显示用</span></label>
                <input
                  type="text"
                  value={editDisplayName}
                  onChange={(e) => setEditDisplayName(e.target.value)}
                  className={`${workspaceFieldClass} w-full`}
                  placeholder="后台显示的名字"
                />
              </div>
              {editError && (
                <p className="text-xs text-rose-500 dark:text-rose-400">{editError}</p>
              )}
              <div className="grid grid-cols-2 gap-2">
                <button type="button" onClick={cancelEdit} className={workspaceSecondaryButtonClass}>取消</button>
                <button type="button" onClick={saveEdit} disabled={saving} className={workspacePrimaryButtonClass}>
                  {saving ? '保存中...' : '保存'}
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className={`${workspaceSoftCardClass} mt-5 space-y-3 p-4`}>
                <div className="flex items-center justify-between gap-4 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">权限</span>
                  <span className="dark:text-slate-100">{getRoleLabel(currentUser.role)}</span>
                </div>
                <div className="flex items-center justify-between gap-4 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">机构</span>
                  <span className="dark:text-slate-100">{currentUser.organization_name}</span>
                </div>
                <div className="flex items-center justify-between gap-4 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">状态</span>
                  <span className="dark:text-slate-100">{currentUser.status === 'active' ? '正常' : currentUser.status}</span>
                </div>
              </div>

              <div className="mt-5 grid grid-cols-1 gap-3">
                <button
                  type="button"
                  onClick={startEdit}
                  className="w-full rounded-2xl border border-sky-200 bg-white px-4 py-3 text-left font-medium text-slate-700 transition-colors hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:hover:bg-white/10"
                >
                  修改用户名 / 昵称
                </button>
                <button
                  type="button"
                  onClick={onOpenSettings}
                  className="w-full rounded-2xl border border-sky-200 bg-white px-4 py-3 text-left font-medium text-slate-700 transition-colors hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:hover:bg-white/10"
                >
                  查看账号信息
                </button>
                <button
                  type="button"
                  onClick={onLogout}
                  className="w-full rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-left font-medium text-rose-600 transition-colors hover:bg-rose-100 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
                >
                  退出登录
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );

  if (typeof document === 'undefined') {
    return sheet;
  }

  return createPortal(sheet, document.body);
};

const Sidebar = ({
  activePage,
  currentUser,
  onLogout,
  setActivePage,
  onNavigate,
  mobile,
  onProfileUpdated,
}: {
  activePage: Page;
  currentUser: CurrentUser;
  onLogout: () => void;
  setActivePage: (p: Page) => void;
  onNavigate?: () => void;
  mobile?: boolean;
  onProfileUpdated?: (username: string, displayName: string) => void;
}) => {
  const [accountSheetOpen, setAccountSheetOpen] = useState(false);
  const menuItems = [
    { id: 'dashboard', icon: LayoutDashboard, label: '工作台' },
    { id: 'review-generation', icon: Library, label: '复习生成' },
    { id: 'consultation', icon: MessageSquare, label: '咨询记录' },
    { id: 'calendar', icon: CalendarDays, label: '课程日历' },
    ...(currentUser.role === 'owner' || currentUser.role === 'admin'
      ? [{ id: 'classes', icon: Home, label: '班级管理' }]
      : []),
    ...(currentUser.role === 'owner' ? [{ id: 'accounts', icon: User, label: '账号审批' }] : []),
    { id: 'settings', icon: Settings, label: '系统设置' },
  ];

  return (
    <div
      className={cn(
        'flex flex-col border-r border-sky-100/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96)_0%,rgba(239,248,255,0.92)_52%,rgba(231,243,255,0.96)_100%)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(8,15,30,0.98)_0%,rgba(15,23,42,0.96)_52%,rgba(17,24,39,0.98)_100%)]',
        mobile
          ? 'h-full w-full overflow-y-auto overscroll-y-auto [-webkit-overflow-scrolling:touch] shadow-[18px_0_48px_rgba(47,128,237,0.12)] dark:shadow-[18px_0_48px_rgba(2,6,23,0.48)]'
          : 'h-screen w-72 shadow-[18px_0_48px_rgba(47,128,237,0.06)] dark:shadow-[18px_0_48px_rgba(2,6,23,0.38)]',
      )}
    >
      <div className="border-b border-sky-100/80 px-6 py-6 dark:border-white/10">
        <div className="flex items-center gap-3">
        <img src="/logo.png" alt="星润 logo" className="w-10 h-10 object-contain" />
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">Starain 工作台</h1>
            <p className="mt-1 text-xs font-semibold uppercase tracking-[0.26em] text-sky-600">AI EDU PLATFORM</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-4 py-5">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => {
              setActivePage(item.id as Page);
              onNavigate?.();
            }}
            className={cn(
              'flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left transition-all duration-200',
              activePage === item.id
                ? 'border border-sky-200 bg-white text-sky-700 shadow-[0_16px_36px_rgba(47,128,237,0.08)] dark:border-sky-500/30 dark:bg-white/10 dark:text-sky-300 dark:shadow-[0_16px_36px_rgba(2,6,23,0.35)]'
                : 'border border-transparent text-slate-500 hover:border-sky-100 hover:bg-white/75 hover:text-slate-800 dark:text-slate-400 dark:hover:border-white/10 dark:hover:bg-white/5 dark:hover:text-slate-100',
            )}
          >
            <item.icon size={20} />
            <span className="font-medium">{item.label}</span>
            {activePage === item.id && (
              <motion.div
                layoutId="active-pill"
                className="ml-auto h-2 w-2 rounded-full bg-sky-500"
              />
            )}
          </button>
        ))}
      </nav>

      <div className="mt-auto border-t border-sky-100/80 p-4 dark:border-white/10">
        <button
          type="button"
          onClick={() => setAccountSheetOpen(true)}
          className="flex w-full items-center gap-3 rounded-2xl border border-sky-100 bg-white/80 p-3 text-left transition-colors hover:bg-white dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/10"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-sky-500 via-cyan-500 to-blue-500 font-bold text-white">
            {currentUser.display_name.slice(0, 1).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">{currentUser.display_name}</p>
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">{getRoleLabel(currentUser.role)}</p>
          </div>
          <MoreVertical size={16} className="shrink-0 text-slate-400 dark:text-slate-500" />
        </button>
      </div>

      <AnimatePresence>
        {accountSheetOpen && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <SidebarAccountSheet
              currentUser={currentUser}
              open={accountSheetOpen}
              onClose={() => setAccountSheetOpen(false)}
              onLogout={onLogout}
              onOpenSettings={() => {
                setAccountSheetOpen(false);
                setActivePage('settings');
                onNavigate?.();
              }}
              onProfileUpdated={onProfileUpdated}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

const Header = ({
  title,
  onGoHome,
  isDark,
  onToggleDarkMode,
  onOpenSidebar,
}: {
  title: string;
  onGoHome?: () => void;
  isDark?: boolean;
  onToggleDarkMode?: () => void;
  onOpenSidebar?: () => void;
}) => {
  return (
    <header className="sticky top-0 z-10 flex h-20 items-center justify-between border-b border-sky-100/80 bg-white/78 px-4 backdrop-blur-xl sm:px-6 md:px-8 dark:border-white/10 dark:bg-[#0f172a]/88">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">Workspace</p>
        <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-900 sm:text-2xl dark:text-white">{title}</h2>
      </div>
      <div className="flex items-center gap-2 sm:gap-4">
        {onOpenSidebar && (
          <button
            onClick={onOpenSidebar}
            title="打开导航"
            aria-label="打开导航"
            className="flex h-11 w-11 items-center justify-center rounded-full border border-sky-200 bg-white text-slate-500 transition-colors hover:bg-sky-50 hover:text-slate-800 lg:hidden dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white"
          >
            <Menu size={20} />
          </button>
        )}
        {onToggleDarkMode && (
          <button
            onClick={onToggleDarkMode}
            title="切换夜间模式"
            aria-label="切换夜间模式"
            className="flex h-11 w-11 items-center justify-center rounded-full border border-sky-200 bg-white text-slate-500 transition-colors hover:bg-sky-50 hover:text-slate-800 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white"
          >
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        )}
        {onGoHome && (
          <button
            onClick={onGoHome}
            title="返回首页"
            className="flex h-11 w-11 items-center justify-center rounded-full border border-sky-200 bg-white text-slate-500 transition-colors hover:bg-sky-50 hover:text-slate-800 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white"
          >
            <Home size={20} />
          </button>
        )}
        <div className="relative hidden xl:block">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-400" size={18} />
          <input
            type="text"
            placeholder="搜索课程、班级..."
            className={`${workspaceFieldClass} w-64 rounded-full py-2 pl-10 pr-4`}
          />
        </div>
        <button className="relative hidden h-11 w-11 items-center justify-center rounded-full border border-sky-200 bg-white text-slate-500 transition-colors hover:bg-sky-50 hover:text-slate-800 md:flex dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white">
          <Bell size={20} />
          <span className="absolute right-2 top-2 h-2.5 w-2.5 rounded-full border-2 border-white bg-rose-400 dark:border-slate-900" />
        </button>
      </div>
    </header>
  );
};

const XiaojimaoLoading = ({ label = '小吉猫正在思考中...' }: { label?: string }) => (
  <div className="flex flex-col items-center justify-center py-12 text-center">
    <motion.div
      animate={{
        y: [0, -4, 0],
      }}
      transition={{
        duration: 2.4,
        repeat: Infinity,
        ease: 'easeInOut',
      }}
      className="relative mb-4 flex h-24 w-24 items-center justify-center rounded-full bg-sky-100"
    >
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-cyan-500 shadow-[0_18px_36px_rgba(34,199,232,0.22)]">
        <span className="text-white text-3xl">🐱</span>
      </div>
      <div className="absolute -right-1 -top-1 flex h-6 w-6 items-center justify-center rounded-full bg-white text-[10px] font-bold text-sky-600 shadow-lg">
        AI
      </div>
    </motion.div>
    <p className="font-medium text-slate-700 dark:text-slate-200">{label}</p>
    <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">正在为您生成结构化复习资料</p>
  </div>
);

// --- Pages ---

const Dashboard = ({
  currentUser,
  setActivePage,
  activeClassCount,
}: {
  currentUser: CurrentUser;
  setActivePage: (p: Page) => void;
  activeClassCount: number;
}) => {
  const [stats, setStats] = useState<Stats | null>(null);
  const [recentLessons, setRecentLessons] = useState<Lesson[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([apiFetch<Stats>('/api/stats'), apiFetch<Lesson[]>('/api/lessons')])
      .then(([s, lessons]) => {
        setStats(s);
        setRecentLessons(lessons.slice(0, 5));
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const statCards = [
    { label: '本月课程', value: stats?.month_lessons ?? '—', icon: FileText, color: 'text-blue-500' },
    { label: '累计课程', value: stats?.total_lessons ?? '—', icon: Library, color: 'text-green-500' },
    { label: '已生成 PDF', value: stats?.total_pdfs ?? '—', icon: Download, color: 'text-purple-500' },
    { label: '活跃班级', value: activeClassCount, icon: CalendarDays, color: 'text-cyan-500' },
  ];

  return (
    <div className={`${workspacePageClass} space-y-8`}>
      <div className="grid gap-8 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.75fr)]">
        <div className="rounded-[2rem] border border-sky-100 bg-[radial-gradient(circle_at_top_left,_rgba(34,199,232,0.18),_transparent_32%),linear-gradient(135deg,_rgba(255,255,255,0.98)_0%,_rgba(236,246,255,0.92)_52%,_rgba(223,241,255,0.96)_100%)] p-8 shadow-[0_24px_72px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.15),_transparent_30%),linear-gradient(135deg,_rgba(15,23,42,0.98)_0%,_rgba(17,24,39,0.95)_52%,_rgba(30,41,59,0.96)_100%)] dark:shadow-[0_28px_80px_rgba(2,6,23,0.36)]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.32em] text-sky-600">Today at Starain</p>
            <h3 className="mt-4 text-3xl font-bold tracking-tight text-slate-900 dark:text-white">欢迎回来，{currentUser.display_name}</h3>
            <p className="mt-3 max-w-xl text-base leading-relaxed text-slate-600 dark:text-slate-300">
              {loading
                ? '正在加载你的课堂数据与教学资产。'
                : `本月已记录 ${stats?.month_lessons ?? 0} 节课，累计生成 ${stats?.total_pdfs ?? 0} 份 PDF 复习资料。`}
            </p>
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <button onClick={() => setActivePage('review-generation')} className={workspacePrimaryButtonClass}>
              <PlusCircle size={20} />
              新建复习文档
            </button>
            <button onClick={() => setActivePage('review-generation')} className={workspaceSecondaryButtonClass}>
              <Library size={20} />
              查看历史文档
            </button>
          </div>
        </div>

        <div className={`${workspaceSoftCardClass} p-6`}>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">Account</p>
          <div className="mt-5 flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 via-cyan-500 to-blue-500 text-xl font-bold text-white shadow-[0_16px_32px_rgba(34,199,232,0.25)]">
              {currentUser.display_name.slice(0, 1).toUpperCase()}
            </div>
            <div>
              <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">{currentUser.display_name}</p>
              <p className="text-sm text-slate-500 dark:text-slate-400">{getRoleLabel(currentUser.role)}</p>
            </div>
          </div>
          <div className="mt-6 space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500 dark:text-slate-400">机构</span>
              <span className="font-medium text-slate-700 dark:text-slate-200">{currentUser.organization_name}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500 dark:text-slate-400">账号状态</span>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300">
                {currentUser.status === 'active' ? '正常' : currentUser.status}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
        {statCards.map((stat, i) => (
          <div key={i} className={`${workspaceCardClass} group p-6`}>
            <div className="mb-4 flex items-center justify-between">
              <div className={`rounded-2xl bg-sky-50 p-3 dark:bg-white/5 ${stat.color}`}>
                <stat.icon size={20} />
              </div>
              <ArrowRight size={16} className="text-slate-300 transition-colors group-hover:text-sky-500 dark:text-slate-600 dark:group-hover:text-sky-400" />
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400">{stat.label}</p>
            <p className="mt-1 text-3xl font-bold tracking-tight text-slate-900 dark:text-white">{stat.value}</p>
          </div>
        ))}
      </div>

      <div className={`${workspaceCardClass} overflow-hidden`}>
        <div className="flex items-center justify-between border-b border-sky-100/80 p-6 dark:border-white/10">
          <div>
            <h4 className="font-semibold text-slate-900 dark:text-white">最近课程</h4>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">最近录入的课堂内容会优先出现在这里。</p>
          </div>
          <button onClick={() => setActivePage('review-generation')} className="text-sm font-medium text-sky-600 transition-colors hover:text-sky-500 dark:text-sky-400 dark:hover:text-sky-300">
            查看全部
          </button>
        </div>
        {loading ? (
          <div className="p-8 text-center text-slate-500 dark:text-slate-400">加载中...</div>
        ) : recentLessons.length === 0 ? (
          <div className="p-8 text-center text-slate-500 dark:text-slate-400">暂无课程记录</div>
        ) : (
          <div className="divide-y divide-sky-100/80 dark:divide-white/10">
            {recentLessons.map((lesson) => (
              <div key={lesson.id} className="flex items-center gap-4 p-4 transition-colors hover:bg-sky-50/70 dark:hover:bg-white/5">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-50 text-sky-600 dark:bg-white/5 dark:text-sky-300">
                  <FileText size={22} />
                </div>
                <div className="flex-1">
                  <p className="font-medium text-slate-900 dark:text-slate-100">{lesson.topic || `${lesson.subject} 课程`}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {lesson.date} • {lesson.subject} • {lesson.grade}
                  </p>
                </div>
                {lesson.pdf_path && (
                  <div className="flex gap-2">
                    <a
                      href={`/api/pdf/download/${lesson.id}`}
                      className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-slate-500 transition-all hover:bg-sky-100 hover:text-sky-600 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-sky-300"
                      title="下载"
                    >
                      <Download size={18} />
                    </a>
                    <a
                      href={`/api/pdf/${lesson.id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-slate-500 transition-all hover:bg-sky-100 hover:text-sky-600 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-sky-300"
                      title="查看"
                    >
                      <Eye size={18} />
                    </a>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const SubjectCombobox = ({
  value,
  onChange,
  options,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
  className?: string;
}) => {
  const [open, setOpen] = useState(false);
  const filtered = options.filter(
    (o) => o && (!value || o.toLowerCase().includes(value.toLowerCase()))
  );

  return (
    <div className={cn('relative', className)}>
      <input
        type="text"
        placeholder="科目"
        value={value}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className={`${workspaceFieldClass} sm:w-32`}
      />
      {open && filtered.length > 0 && (
        <div className="absolute left-0 top-full z-20 mt-1 w-full min-w-[8rem] overflow-hidden rounded-xl border border-sky-200 bg-white shadow-xl dark:border-white/10 dark:bg-slate-900">
          {filtered.map((opt) => (
            <button
              key={opt}
              type="button"
              onMouseDown={() => {
                onChange(opt);
                setOpen(false);
              }}
              className="w-full px-4 py-2 text-left text-sm text-slate-700 transition-colors hover:bg-sky-50 dark:text-slate-200 dark:hover:bg-white/10"
            >
              {opt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const LessonInput = ({ onSuccess }: { onSuccess: () => void }) => {
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [lessonDate, setLessonDate] = useState(new Date().toISOString().split('T')[0]);
  const [weakPoints, setWeakPoints] = useState('');
  const [summaryText, setSummaryText] = useState('');
  const [inputType, setInputType] = useState<'text' | 'file'>('text');
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [classId, setClassId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    apiFetch<ClassItem[]>('/api/classes').then(setClasses).catch(console.error);
  }, []);

  const handleClassChange = (id: number) => {
    setClassId(id);
    const cls = classes.find((c) => c.id === id);
    if (cls?.subject) setSubject(cls.subject);
  };

  const handleAnalyze = async () => {
    if (!summaryText.trim()) return;
    setIsAnalyzing(true);
    try {
      const result = await apiFetch<{ subject: string; topic: string; weak_points: string }>('/api/analyze', {
        method: 'POST',
        body: JSON.stringify({ text: summaryText }),
      });
      if (result.subject) setSubject(result.subject);
      if (result.topic) setTopic(result.topic);
      if (result.weak_points) setWeakPoints(result.weak_points);
    } catch (e) {
      setError(e instanceof Error ? e.message : '识别失败，请重试');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleGenerate = async () => {
    setError('');
    if (inputType === 'text' && !summaryText.trim()) {
      setError('请填写课堂笔记内容');
      return;
    }
    if (inputType === 'file' && !file) {
      setError('请选择上传文件');
      return;
    }

    setIsLoading(true);
    try {
      if (inputType === 'text') {
        await apiFetch('/api/lessons', {
          method: 'POST',
          body: JSON.stringify({
            subject,
            class_id: classId ?? 0,
            topic,
            date: lessonDate,
            weak_points: weakPoints,
            summary_text: summaryText,
          }),
        });
      } else {
        const formData = new FormData();
        formData.append('input_type', 'file');
        formData.append('subject', subject);
        formData.append('class_id', classId ? String(classId) : '0');
        formData.append('topic', topic);
        formData.append('date', lessonDate);
        formData.append('weak_points', weakPoints);
        if (file) formData.append('upload_file', file);
        const res = await fetch('/api/lessons', { method: 'POST', body: formData });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ error: res.statusText }));
          throw new Error((err as { error?: string }).error || res.statusText);
        }
      }
      onSuccess();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '提交失败，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={`${workspacePageClass} mx-auto max-w-6xl`}>
      <AnimatePresence mode="wait">
        {isLoading ? (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className={`${workspaceCardClass} flex min-h-[60vh] items-center justify-center p-8`}
          >
            <XiaojimaoLoading label="小吉猫正在生成复习资料..." />
          </motion.div>
        ) : (
          <motion.div
            key="form"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-8"
          >
            <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Lesson Intake</p>
                <h3 className={`${workspaceSectionTitleClass} mt-3`}>生成复习文档</h3>
                <p className={`${workspaceSectionTextClass} mt-2`}>
                  上传录音或粘贴笔记，AI 会整理成统一的复习资料与后续题库资产。
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <SubjectCombobox
                  value={subject}
                  onChange={setSubject}
                  options={[...new Set<string>(classes.map((c: ClassItem) => c.subject).filter(Boolean))] as string[]}
                  className="w-full"
                />
                <select
                  value={classId ?? ''}
                  onChange={(e) => handleClassChange(Number(e.target.value))}
                  className={`${workspaceFieldClass} w-full sm:w-40`}
                >
                  <option value="">选择班级</option>
                  {classes.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <input
                  type="date"
                  value={lessonDate}
                  onChange={(e) => setLessonDate(e.target.value)}
                  className={`${workspaceFieldClass} w-full sm:w-40`}
                />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                <AlertCircle size={18} />
                <span className="text-sm">{error}</span>
              </div>
            )}

            <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)]">
              <div className="space-y-6">
                <div className="inline-flex gap-2 rounded-2xl border border-sky-100 bg-white/85 p-1 shadow-sm dark:border-white/10 dark:bg-white/5">
                  <button
                    onClick={() => setInputType('text')}
                    className={cn(
                      'rounded-xl px-4 py-2 text-sm font-medium transition-all',
                      inputType === 'text' ? 'bg-sky-600 text-white shadow-sm' : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100',
                    )}
                  >
                    文字笔记
                  </button>
                  <button
                    onClick={() => setInputType('file')}
                    className={cn(
                      'rounded-xl px-4 py-2 text-sm font-medium transition-all',
                      inputType === 'file' ? 'bg-sky-600 text-white shadow-sm' : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100',
                    )}
                  >
                    上传文件
                  </button>
                </div>

                {inputType === 'file' ? (
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className={`${workspaceCardClass} cursor-pointer p-12 text-center transition-all hover:border-sky-200 hover:shadow-[0_24px_64px_rgba(47,128,237,0.1)] dark:hover:border-white/15 dark:hover:shadow-[0_28px_72px_rgba(2,6,23,0.4)]`}
                  >
                    <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-50 text-sky-600 transition-transform hover:scale-105 dark:bg-white/5 dark:text-sky-300">
                      <Upload size={32} />
                    </div>
                    <h4 className="font-semibold text-slate-900 dark:text-white">{file ? file.name : '上传课后录音或文本'}</h4>
                    <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">支持 m4a, mp3, wav, txt, md 格式</p>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".mp3,.m4a,.mp4,.wav,.ogg,.webm,.flac,.txt,.md"
                      className="hidden"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    />
                  </div>
                ) : null}

                <div className={`${workspaceCardClass} space-y-4 p-6`}>
                  <h4 className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
                    <CheckCircle2 size={18} className="text-sky-500" />
                    课程信息
                  </h4>
                  <input
                    type="text"
                    placeholder="课程主题（选填）"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    className={workspaceFieldClass}
                  />
                  <textarea
                    placeholder="薄弱点（选填）"
                    value={weakPoints}
                    onChange={(e) => setWeakPoints(e.target.value)}
                    rows={3}
                    className={`${workspaceFieldClass} resize-none`}
                  />
                </div>
              </div>

              <div className="flex flex-col">
                {inputType === 'text' && (
                  <div className={`${workspaceCardClass} flex flex-1 flex-col p-6`}>
                    <div className="mb-4 flex items-center justify-between gap-4">
                      <div>
                        <h4 className="font-semibold text-slate-900 dark:text-white">课堂笔记</h4>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">支持长段文本、结构化大纲与老师备注。</p>
                      </div>
                      <button
                        onClick={handleAnalyze}
                        disabled={!summaryText.trim() || isAnalyzing}
                        className={workspaceGhostButtonClass}
                      >
                        <Cpu size={13} className={isAnalyzing ? 'text-sky-500' : 'text-slate-500 dark:text-slate-400'} />
                        {isAnalyzing ? '识别中...' : '识别'}
                      </button>
                    </div>
                    <textarea
                      placeholder="在此处粘贴您的课堂笔记或结构化大纲..."
                      value={summaryText}
                      onChange={(e) => setSummaryText(e.target.value)}
                      className="min-h-[320px] flex-1 resize-none rounded-2xl border border-sky-100 bg-[linear-gradient(180deg,rgba(249,252,255,0.98)_0%,rgba(240,248,255,0.95)_100%)] px-5 py-4 text-sm leading-relaxed text-slate-700 outline-none transition focus:border-sky-200 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100 dark:focus:border-sky-500 dark:focus:ring-sky-500/15"
                    />
                  </div>
                )}
                <button onClick={handleGenerate} className={`${workspacePrimaryButtonClass} mt-6 w-full py-4 text-lg font-bold`}>
                  生成复习文档
                  <ArrowRight size={20} />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

const ReviewDocumentHistory = ({ refreshToken = 0 }: { refreshToken?: number }) => {
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    apiFetch<Lesson[]>('/api/lessons')
      .then(setLessons)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshToken]);

  const handleDelete = async (id: number) => {
    if (!window.confirm('确定删除此课程？相关 PDF 也会被删除。')) return;
    await apiFetch(`/api/lessons/${id}`, { method: 'DELETE' });
    load();
  };

  return (
    <div className={`${workspaceCardClass} overflow-hidden`}>
      {loading ? (
        <div className="p-8 text-center text-slate-500 dark:text-slate-400">加载中...</div>
      ) : lessons.length === 0 ? (
        <div className="p-8 text-center text-slate-500 dark:text-slate-400">还没有复习文档，点击「新建复习文档」开始生成</div>
      ) : (
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-sky-100/80 text-xs uppercase tracking-wider text-slate-400 dark:border-white/10 dark:text-slate-500">
              <th className="px-6 py-4 font-semibold">课程名称</th>
              <th className="px-6 py-4 font-semibold">科目 / 年级</th>
              <th className="px-6 py-4 font-semibold">日期</th>
              <th className="px-6 py-4 font-semibold">PDF</th>
              <th className="px-6 py-4 text-right font-semibold">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-sky-100/80 dark:divide-white/10">
            {lessons.map((lesson) => (
              <tr key={lesson.id} className="group transition-colors hover:bg-sky-50/70 dark:hover:bg-white/5">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-50 text-sky-600 dark:bg-white/5 dark:text-sky-300">
                      <FileText size={16} />
                    </div>
                    <span className="font-medium text-slate-900 dark:text-white">{lesson.topic || `${lesson.subject} 课程`}</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex gap-2">
                    {lesson.subject && (
                      <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">
                        {lesson.subject}
                      </span>
                    )}
                    {lesson.grade && (
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500 dark:bg-white/5 dark:text-slate-400">
                        {lesson.grade}
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-6 py-4 font-mono text-sm text-slate-500 dark:text-slate-400">{lesson.date}</td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2">
                    <div className={cn('h-2 w-2 rounded-full', lesson.pdf_path ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600')} />
                    <span className="text-sm text-slate-500 dark:text-slate-400">{lesson.pdf_path ? '已生成' : '无'}</span>
                  </div>
                </td>
                <td className="px-6 py-4 text-right">
                  <div className="flex justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    {lesson.pdf_path && (
                      <>
                        <a
                          href={`/api/pdf/${lesson.id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-500 transition-all hover:bg-sky-50 hover:text-sky-600 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-sky-300"
                          title="查看"
                        >
                          <Eye size={16} />
                        </a>
                        <a
                          href={`/api/pdf/download/${lesson.id}`}
                          className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-500 transition-all hover:bg-sky-50 hover:text-sky-600 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-sky-300"
                          title="下载"
                        >
                          <Download size={16} />
                        </a>
                      </>
                    )}
                    <button
                      onClick={() => handleDelete(lesson.id)}
                      className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-500 transition-all hover:bg-rose-50 hover:text-rose-600 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-rose-500/10 dark:hover:text-rose-300"
                      title="删除"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

const ReviewGenerationPage = ({ onSuccess }: { onSuccess: () => void }) => {
  const [composerOpen, setComposerOpen] = useState(false);
  const [historyRefreshToken, setHistoryRefreshToken] = useState(0);

  const handleComposerSuccess = () => {
    setComposerOpen(false);
    onSuccess();
  };

  const handleFormSuccess = () => {
    handleComposerSuccess();
    setHistoryRefreshToken((current) => current + 1);
  };

  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className={workspaceSectionTitleClass}>历史文档</h3>
          <p className={`${workspaceSectionTextClass} mt-2`}>查看已生成的复习文档，支持下载、预览与删除。</p>
        </div>
        <button onClick={() => setComposerOpen((current) => !current)} className={workspacePrimaryButtonClass}>
          <PlusCircle size={20} />
          新建复习文档
        </button>
      </div>

      {composerOpen && (
        <div className={`${workspaceSoftCardClass} p-4 sm:p-6`}>
          <div className="mb-4">
            <h4 className="text-xl font-semibold text-slate-900 dark:text-white">生成复习文档</h4>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">上传课堂内容并生成新的复习文档。</p>
          </div>
          <LessonInput onSuccess={handleFormSuccess} />
        </div>
      )}

      <ReviewDocumentHistory refreshToken={historyRefreshToken} />
    </div>
  );
};

const ConsultationModal = ({
  open,
  mode,
  record,
  consultationTeachers,
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

  useEffect(() => {
    if (open) {
      setForm(toConsultationFormValues(record));
      setQuickEntry('');
      setParseFeedback('');
    }
  }, [open, mode, record]);

  if (!open) {
    return null;
  }

  const readOnly = mode === 'view';
  const titleMap = {
    view: '查看咨询记录',
    create: '新增咨询记录',
    edit: '编辑咨询记录',
  } as const;

  const updateField = <K extends keyof ConsultationFormValues>(key: K, value: ConsultationFormValues[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
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
    if (readOnly) {
      return;
    }
    await onSubmit(form);
  };

  const handleTeacherChange = (teacherId: string) => {
    const selectedTeacher = teacherOptions.find((option) => option.teacher_id === teacherId);
    if (!selectedTeacher) {
      updateField('teacher_id', teacherId);
      return;
    }
    setForm((current) => ({
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

    (Object.entries(parsed) as Array<[keyof ConsultationFormValues, string]>).forEach(([key, value]) => {
      if (value) {
        nextForm[key] = value as ConsultationFormValues[keyof ConsultationFormValues];
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

    setForm(nextForm);
    setParseFeedback(
      parsed.parent_wechat_name || parsed.grade || parsed.consultation_subject || parsed.source_channel || parsed.receiving_teacher
        ? '已根据快速录入内容回填字段，请检查后保存。'
        : '这段描述还不够明确，建议补充老师、年级或来源关键词后再试。',
    );
  };

  const fieldClass = `${workspaceFieldClass} ${readOnly ? 'cursor-default' : ''}`;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto px-3 py-3 sm:items-center sm:px-4 sm:py-6"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="absolute inset-0 bg-black/45 backdrop-blur-[6px]" />
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: 18 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.97, y: 18 }}
        transition={{ duration: 0.2 }}
        className="relative z-10 my-auto flex w-full max-w-5xl flex-col overflow-hidden rounded-[1.5rem] border border-sky-100 bg-white shadow-[0_30px_90px_rgba(15,23,42,0.18)] max-sm:min-h-[calc(100dvh-1.5rem)] max-sm:max-h-[calc(100dvh-1.5rem)] sm:max-h-[calc(100dvh-3rem)] sm:rounded-[2rem] dark:border-white/10 dark:bg-slate-900 dark:shadow-[0_30px_90px_rgba(2,6,23,0.55)]"
      >
        <div className="flex items-start justify-between gap-4 border-b border-sky-100/80 px-4 py-4 sm:px-6 sm:py-5 dark:border-white/10">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Consultation</p>
            <h3 className="mt-2 text-xl font-bold tracking-tight text-slate-900 sm:text-2xl dark:text-white">{titleMap[mode]}</h3>
            <p className="mt-1 max-w-2xl text-sm text-slate-500 dark:text-slate-400">
              {readOnly ? '记录详情只读展示，owner 可以在这里进入编辑或删除。' : '先用快速录入整理信息，再确认下方结构化字段。'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-50 text-slate-500 transition-colors hover:bg-sky-100 hover:text-slate-800 dark:bg-white/5 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-white"
            aria-label="关闭咨询记录窗口"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          {!readOnly && (
            <section className={`${workspaceSoftCardClass} mb-5 space-y-4 p-4 sm:p-5`}>
              <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <h4 className="font-semibold text-slate-900 dark:text-white">快速录入</h4>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    先写一句自然描述，手动点“智能解析”后回填到下方字段。
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={handleQuickParse} className={workspacePrimaryButtonClass}>
                    <Cpu size={18} />
                    智能解析
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setQuickEntry('');
                      setParseFeedback('');
                    }}
                    className={workspaceSecondaryButtonClass}
                  >
                    清空
                  </button>
                </div>
              </div>
              <textarea
                value={quickEntry}
                onChange={(e) => setQuickEntry(e.target.value)}
                rows={3}
                className={`${workspaceFieldClass} resize-none`}
                placeholder="例如：张妈妈，五年级数学，张裕空转介绍，雷文浩接待，想补基础"
              />
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {parseFeedback || '系统会先帮你整理字段，你再确认后保存。'}
              </p>
            </section>
          )}

          <div className="grid gap-5 lg:grid-cols-2">
            <section className={`${workspaceSoftCardClass} space-y-4 p-4 sm:p-5`}>
              <div>
                <h4 className="font-semibold text-slate-900 dark:text-white">基础信息</h4>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">日期、家长微信和咨询老师信息。</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">日期</span>
                  <input
                    type="date"
                    value={form.date}
                    onChange={(e) => updateField('date', e.target.value)}
                    disabled={readOnly}
                    className={fieldClass}
                  />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">年级</span>
                  <input
                    type="text"
                    value={form.grade}
                    onChange={(e) => updateField('grade', e.target.value)}
                    disabled={readOnly}
                    list="consultation-grade-options"
                    className={fieldClass}
                    placeholder="如：三年级"
                  />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">家长微信名</span>
                  <input
                    type="text"
                    value={form.parent_wechat_name}
                    onChange={(e) => updateField('parent_wechat_name', e.target.value)}
                    disabled={readOnly}
                    className={fieldClass}
                    placeholder="家长微信昵称"
                  />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">孩子姓名</span>
                  <input
                    type="text"
                    value={form.child_name}
                    onChange={(e) => updateField('child_name', e.target.value)}
                    disabled={readOnly}
                    className={fieldClass}
                    placeholder="孩子姓名"
                  />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">咨询老师</span>
                  <select
                    value={form.teacher_id}
                    onChange={(e) => handleTeacherChange(e.target.value)}
                    disabled={readOnly}
                    className={fieldClass}
                  >
                    <option value="">请选择老师</option>
                    {teacherOptions.map((option) => (
                      <option key={option.teacher_id} value={option.teacher_id}>
                        {option.display_name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </section>

            <section className={`${workspaceSoftCardClass} space-y-4 p-4 sm:p-5`}>
              <div>
                <h4 className="font-semibold text-slate-900 dark:text-white">咨询内容</h4>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">咨询主题、需求和跟进状态。</p>
              </div>
              <div className="space-y-4">
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">咨询科目</span>
                  <input
                    type="text"
                    value={form.consultation_subject}
                    onChange={(e) => updateField('consultation_subject', e.target.value)}
                    disabled={readOnly}
                    className={fieldClass}
                    placeholder="咨询科目"
                  />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">来源渠道主类</span>
                  <select
                    value={form.source_channel}
                    onChange={(e) => updateField('source_channel', e.target.value)}
                    disabled={readOnly}
                    className={fieldClass}
                  >
                    <option value="">请选择来源渠道</option>
                    {!consultationSourceOptions.includes(form.source_channel) && form.source_channel ? (
                      <option value={form.source_channel}>{form.source_channel}</option>
                    ) : null}
                    {consultationSourceOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">来源渠道备注</span>
                  <input
                    type="text"
                    value={form.source_channel_note}
                    onChange={(e) => updateField('source_channel_note', e.target.value)}
                    disabled={readOnly}
                    className={fieldClass}
                    placeholder="例如：张妈妈转介绍 / 家长群看到后私聊"
                  />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">跟进状态</span>
                  <select
                    value={form.follow_up_status}
                    onChange={(e) => updateField('follow_up_status', e.target.value)}
                    disabled={readOnly}
                    className={fieldClass}
                  >
                    {consultationStatusOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </section>

            <datalist id="consultation-grade-options">
              {consultationGradeOptions.map((option) => (
                <option key={option} value={option} />
              ))}
            </datalist>

            <section className={`${workspaceSoftCardClass} space-y-4 p-4 sm:p-5 lg:col-span-2`}>
              <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">具体需求</span>
                  <textarea
                    value={form.need_detail}
                    onChange={(e) => updateField('need_detail', e.target.value)}
                    disabled={readOnly}
                    rows={5}
                    className={`${fieldClass} resize-none`}
                    placeholder="家长具体咨询需求"
                  />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">内部备注（可选）</span>
                  <textarea
                    value={form.follow_up_note}
                    onChange={(e) => updateField('follow_up_note', e.target.value)}
                    disabled={readOnly}
                    rows={5}
                    className={`${fieldClass} resize-none`}
                    placeholder="补充内部跟进说明"
                  />
                </label>
              </div>
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

          <div className="mt-5 flex flex-col gap-3 border-t border-sky-100/80 pt-4 sm:mt-6 sm:flex-row sm:items-center sm:justify-between sm:pt-5 dark:border-white/10">
            <div className="text-sm text-slate-500 dark:text-slate-400">
              {readOnly ? '查看模式下可直接切换到编辑或删除记录。' : '保存后会刷新列表，不需要跳转到其他页面。'}
            </div>
            <div className="grid gap-3 sm:flex sm:flex-wrap sm:justify-end">
              {readOnly && currentUser.role === 'owner' && (
                <>
                  <button
                    type="button"
                    onClick={onRequestEdit}
                    className={`${workspaceSecondaryButtonClass} w-full sm:w-auto`}
                  >
                    <Pencil size={18} />
                    编辑
                  </button>
                  <button
                    type="button"
                    onClick={onDelete}
                    disabled={submitting}
                    className="inline-flex w-full items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-rose-200 bg-rose-50 px-5 py-3 font-semibold text-rose-600 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
                  >
                    <Trash2 size={18} />
                    删除
                  </button>
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
                  <button type="submit" className={`${workspacePrimaryButtonClass} w-full sm:w-auto`} disabled={submitting}>
                    {submitting ? '保存中...' : mode === 'create' ? '创建记录' : '保存修改'}
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

const ConsultationPage = ({ currentUser }: { currentUser: CurrentUser }) => {
  const isOwner = currentUser.role === 'owner';
  const [records, setRecords] = useState<ConsultationRecord[]>([]);
  const [consultationTeachers, setConsultationTeachers] = useState<ConsultationTeacherOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'view' | 'create' | 'edit'>('view');
  const [selectedRecord, setSelectedRecord] = useState<ConsultationRecord | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
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

  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Consultation Log</p>
          <h3 className={`${workspaceSectionTitleClass} mt-3`}>咨询记录</h3>
          <p className={`${workspaceSectionTextClass} mt-2`}>
            记录家长咨询、跟进状态和后续备注，搜索后会直接按关键词过滤当前列表。
          </p>
        </div>
        <div className="flex w-full flex-col gap-3 lg:w-auto lg:items-end">
          <label className="relative w-full lg:w-[22rem] xl:w-[24rem]">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-400" size={18} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索日期、家长微信名、孩子姓名、老师或科目"
              className={`${workspaceFieldClass} w-full rounded-full py-2.5 pl-11 pr-4`}
            />
          </label>
          <div className="flex flex-wrap items-center gap-3 self-start lg:self-auto">
            <button
              type="button"
              onClick={() => load(search).catch(() => undefined)}
              className={`${workspaceSecondaryButtonClass} w-full sm:w-auto sm:min-w-[126px]`}
            >
              <RefreshCw size={18} />
              刷新
            </button>
            <button
              type="button"
              onClick={openCreateModal}
              className={`${workspacePrimaryButtonClass} w-full sm:w-auto sm:min-w-[126px]`}
            >
              <PlusCircle size={18} />
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

      <div className={`${workspaceCardClass} overflow-hidden`}>
        {loading ? (
          <div className="p-8 text-center text-slate-500 dark:text-slate-400">正在加载咨询记录...</div>
        ) : records.length === 0 ? (
          <div className="p-8 text-center text-slate-500 dark:text-slate-400">
            暂无咨询记录，点击「新增记录」开始录入。
          </div>
        ) : (
          <>
            <div className="grid gap-4 p-4 sm:p-5 lg:grid-cols-2 2xl:hidden">
              {records.map((record) => {
                const busy = isBusy && selectedRecord?.id === record.id;
                return (
                  <article key={record.id} className={`${workspaceSoftCardClass} space-y-4 p-4`}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">咨询日期</p>
                        <p className="mt-2 font-mono text-sm text-slate-600 dark:text-slate-300">{record.date || '—'}</p>
                      </div>
                      <span className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-full px-3 py-1 text-[11px] font-semibold tracking-[0.08em] ${consultationStatusClass(record.follow_up_status || '')}`}>
                        {record.follow_up_status || '—'}
                      </span>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">家长微信</p>
                        <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">{record.parent_wechat_name || '—'}</p>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{getConsultationStudentMeta(record)}</p>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">咨询老师</p>
                        <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">
                          {getConsultationTeacherName(record, teacherDirectory)}
                        </p>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{record.consultation_subject || '未填写咨询科目'}</p>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{getConsultationSourceLabel(record)}</p>
                      </div>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="rounded-2xl border border-sky-100 bg-white/80 p-3 dark:border-white/10 dark:bg-slate-950/70">
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">录入时间</p>
                        <p className="mt-2 text-sm text-slate-700 dark:text-slate-200">{record.created_at || '—'}</p>
                      </div>
                      <div className="rounded-2xl border border-sky-100 bg-white/80 p-3 dark:border-white/10 dark:bg-slate-950/70">
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">最后更新</p>
                        <p className="mt-2 text-sm text-slate-700 dark:text-slate-200">{record.updated_at || '—'}</p>
                      </div>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                      <button
                        type="button"
                        onClick={() => openViewModal(record)}
                        className={`${workspaceSecondaryButtonClass} w-full`}
                      >
                        <Eye size={16} />
                        查看
                      </button>
                      {isOwner && (
                        <>
                          <button
                            type="button"
                            onClick={() => openEditModal(record)}
                            className={`${workspaceSecondaryButtonClass} w-full`}
                            disabled={busy}
                          >
                            <Pencil size={16} />
                            编辑
                          </button>
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
                            className="inline-flex w-full items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-rose-200 bg-rose-50 px-5 py-3 font-semibold text-rose-600 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
                            disabled={busy}
                          >
                            <Trash2 size={16} />
                            删除
                          </button>
                        </>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="hidden 2xl:block">
              <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-sky-100/80 text-xs uppercase tracking-wider text-slate-400 dark:border-white/10 dark:text-slate-500">
                <th className="px-6 py-4 font-semibold whitespace-nowrap">日期</th>
                <th className="px-6 py-4 font-semibold whitespace-nowrap">家长微信 / 学生姓名</th>
                <th className="px-6 py-4 font-semibold whitespace-nowrap">年级</th>
                <th className="px-6 py-4 font-semibold whitespace-nowrap">咨询老师</th>
                <th className="px-6 py-4 font-semibold whitespace-nowrap">咨询科目 / 来源渠道</th>
                <th className="px-6 py-4 font-semibold whitespace-nowrap">跟进状态</th>
                <th className="px-6 py-4 font-semibold whitespace-nowrap">录入 / 更新</th>
                <th className="px-6 py-4 text-right font-semibold whitespace-nowrap">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sky-100/80 dark:divide-white/10">
              {records.map((record) => {
                const busy = isBusy && selectedRecord?.id === record.id;
                return (
                  <tr key={record.id} className="group transition-colors hover:bg-sky-50/70 dark:hover:bg-white/5">
                    <td className="px-6 py-4 font-mono text-sm text-slate-500 dark:text-slate-400">{record.date || '—'}</td>
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        <p className="font-medium text-slate-900 dark:text-white">
                          {record.parent_wechat_name || '—'}
                        </p>
                        <p className="text-sm text-slate-500 dark:text-slate-400">
                          {getConsultationStudentMeta(record)}
                        </p>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500 dark:text-slate-400">{record.grade || '—'}</td>
                    <td className="px-6 py-4">
                      <p className="text-sm text-slate-700 dark:text-slate-200">
                        {getConsultationTeacherName(record, teacherDirectory)}
                      </p>
                    </td>
                    <td className="px-6 py-4">
                      <div className="space-y-1 text-sm text-slate-500 dark:text-slate-400">
                        <p>{record.consultation_subject || '未填写咨询科目'}</p>
                        <p>{getConsultationSourceLabel(record)}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-full px-3 py-1 text-[11px] font-semibold tracking-[0.08em] ${consultationStatusClass(record.follow_up_status || '')}`}>
                        {record.follow_up_status || '—'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500 dark:text-slate-400">
                      <div className="space-y-1">
                        <p>{record.created_at || '—'}</p>
                        <p>{record.updated_at || '—'}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex justify-end gap-1 opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100">
                        <button
                          type="button"
                          onClick={() => openViewModal(record)}
                          className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-500 transition-all hover:bg-sky-50 hover:text-sky-600 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-sky-300"
                          title="查看"
                        >
                          <Eye size={16} />
                        </button>
                        {isOwner && (
                          <>
                            <button
                              type="button"
                              onClick={() => openEditModal(record)}
                              className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-500 transition-all hover:bg-sky-50 hover:text-sky-600 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-sky-300"
                              title="编辑"
                              disabled={busy}
                            >
                              <Pencil size={16} />
                            </button>
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
                              className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-500 transition-all hover:bg-rose-50 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-rose-500/10 dark:hover:text-rose-300"
                              title="删除"
                              disabled={busy}
                            >
                              <Trash2 size={16} />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
            </div>
          </>
        )}
      </div>

      <AnimatePresence>
        {modalOpen && (
          <ConsultationModal
            open={modalOpen}
            mode={modalMode}
            record={selectedRecord}
            consultationTeachers={consultationTeachers}
            submitting={submitting}
            error={error}
            currentUser={currentUser}
            onClose={closeModal}
            onSubmit={handleSubmit}
            onDelete={isOwner ? handleDelete : undefined}
            onRequestEdit={selectedRecord ? () => openEditModal(selectedRecord) : undefined}
          />
        )}
      </AnimatePresence>
    </div>
  );
};

const ApprovalPage = ({ currentUser }: { currentUser: CurrentUser }) => {
  const [items, setItems] = useState<RegistrationRequestItem[]>([]);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [usersLoading, setUsersLoading] = useState(true);
  const [error, setError] = useState('');
  const [usersError, setUsersError] = useState('');
  const [actingId, setActingId] = useState<number | null>(null);
  const [roleSavingUserId, setRoleSavingUserId] = useState<number | null>(null);

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiFetch<{ items: RegistrationRequestItem[] }>('/api/admin/registration-requests');
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : '审批列表加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    setUsersError('');
    try {
      const data = await apiFetch<UserItem[]>('/api/admin/users');
      setUsers(data);
    } catch (err) {
      setUsersError(err instanceof Error ? err.message : '成员权限加载失败');
    } finally {
      setUsersLoading(false);
    }
  }, []);

  useEffect(() => {
    loadItems().catch(() => undefined);
    loadUsers().catch(() => undefined);
  }, [loadItems, loadUsers]);

  const handleDecision = async (requestId: number, action: 'approve' | 'reject') => {
    setActingId(requestId);
    setError('');
    try {
      await apiFetch(`/api/admin/registration-requests/${requestId}/${action}`, {
        method: 'POST',
      });
      setItems((current) => current.filter((item) => item.id !== requestId));
    } catch (err) {
      setError(err instanceof Error ? err.message : '审批操作失败');
    } finally {
      setActingId(null);
    }
  };

  const handleRoleToggle = async (userId: number, currentRole: Role) => {
    if (currentRole === 'owner') {
      return;
    }

    const nextRole: Exclude<Role, 'owner'> = currentRole === 'admin' ? 'member' : 'admin';
    setRoleSavingUserId(userId);
    setUsersError('');
    setUsers((current) => current.map((user) => (user.id === userId ? { ...user, role: nextRole } : user)));

    try {
      await apiFetch(`/api/admin/users/${userId}/role`, {
        method: 'PUT',
        body: JSON.stringify({ role: nextRole }),
      });
    } catch (err) {
      setUsers((current) => current.map((user) => (user.id === userId ? { ...user, role: currentRole } : user)));
      setUsersError(err instanceof Error ? err.message : '成员权限更新失败');
    } finally {
      setRoleSavingUserId(null);
    }
  };

  return (
    <div className={`${workspacePageClass} space-y-8`}>
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,320px)_minmax(0,1fr)] gap-6">
        <section className={`${workspaceCardClass} space-y-5 p-6`}>
          <div>
            <p className="text-sm uppercase tracking-[0.25em] text-sky-600">Owner</p>
            <h3 className="mt-3 text-2xl font-bold text-slate-900 dark:text-white">账号审批</h3>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">只有最高权限账号可以审核注册申请，并为用户开通后台访问权限。</p>
          </div>
          <div className={`${workspaceSoftCardClass} p-5`}>
            <p className="text-xs uppercase tracking-[0.25em] text-sky-600">Current Account</p>
            <p className="mt-3 text-xl font-semibold text-slate-900 dark:text-white">{currentUser.display_name}</p>
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-500 dark:text-slate-400">用户名</span>
                <span className="text-slate-700 dark:text-slate-200">{currentUser.username}</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-500 dark:text-slate-400">权限</span>
                <span className="text-slate-700 dark:text-slate-200">{getRoleLabel(currentUser.role)}</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-500 dark:text-slate-400">机构</span>
                <span className="text-slate-700 dark:text-slate-200">{currentUser.organization_name}</span>
              </div>
            </div>
          </div>
          <div className={`${workspaceSoftCardClass} p-5`}>
            <p className="text-xs uppercase tracking-[0.25em] text-slate-500 dark:text-slate-400">Queue</p>
            <p className="mt-3 text-4xl font-bold text-slate-900 dark:text-white">{items.length}</p>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">当前待审核注册申请</p>
          </div>
        </section>

        <section className={`${workspaceCardClass} p-6`}>
          <div className="flex items-center justify-between gap-4 mb-6">
            <div>
              <h4 className="text-xl font-semibold text-slate-900 dark:text-white">待审批申请</h4>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">新账号统一归属机构 {currentUser.organization_name}，通过后即可进入后台。</p>
            </div>
            <button
              onClick={() => loadItems().catch(() => undefined)}
              className={workspaceSecondaryButtonClass}
            >
              刷新列表
            </button>
          </div>

          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          {loading ? (
            <div className="p-8 text-center text-slate-500 dark:text-slate-400">正在读取审批队列...</div>
          ) : items.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
              暂无待审批申请，新的注册请求会出现在这里。
            </div>
          ) : (
            <div className="space-y-4">
              {items.map((item) => {
                const busy = actingId === item.id;
                return (
                  <div key={item.id} className={`${workspaceSoftCardClass} p-5`}>
                    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-lg font-semibold text-slate-900 dark:text-white">{item.display_name}</span>
                          <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">
                            待审批
                          </span>
                        </div>
                        <div className="grid grid-cols-1 gap-3 text-sm text-slate-500 md:grid-cols-3 dark:text-slate-400">
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">用户名</p>
                            <p className="mt-1 text-slate-700 dark:text-slate-200">{item.username}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">机构</p>
                            <p className="mt-1 text-slate-700 dark:text-slate-200">{item.organization_name}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">申请时间</p>
                            <p className="mt-1 text-slate-700 dark:text-slate-200">{item.created_at}</p>
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-3">
                        <button
                          onClick={() => handleDecision(item.id, 'reject')}
                          disabled={busy}
                          className={workspaceSecondaryButtonClass}
                        >
                          拒绝
                        </button>
                        <button
                          onClick={() => handleDecision(item.id, 'approve')}
                          disabled={busy}
                          className={workspacePrimaryButtonClass}
                        >
                          {busy ? '处理中...' : '通过并开通'}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {currentUser.role === 'owner' && (
        <section className={`${workspaceCardClass} p-6`}>
          <div className="flex flex-col gap-3 border-b border-sky-100/80 pb-5 sm:flex-row sm:items-start sm:justify-between dark:border-white/10">
            <div>
              <h4 className="text-xl font-semibold text-slate-900 dark:text-white">成员权限</h4>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                只有 owner 可以在这里切换管理员与普通成员权限，班级分配不再放在审批页。
              </p>
            </div>
            <button onClick={() => loadUsers().catch(() => undefined)} className={workspaceSecondaryButtonClass}>
              刷新成员
            </button>
          </div>

          {usersError && (
            <div className="mt-5 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {usersError}
            </div>
          )}

          {usersLoading ? (
            <div className="py-10 text-center text-slate-500 dark:text-slate-400">正在加载成员权限...</div>
          ) : users.length === 0 ? (
            <div className="mt-5 rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
              当前暂无可管理成员。
            </div>
          ) : (
            <div className="mt-5 space-y-4">
              {users.map((user) => {
                const busy = roleSavingUserId === user.id;
                const isOwner = user.role === 'owner';
                return (
                  <div key={user.id} className={`${workspaceSoftCardClass} p-5`}>
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-lg font-semibold text-slate-900 dark:text-white">{user.name}</span>
                          <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${getRoleBadgeClass(user.role)}`}>
                            {getRoleLabel(user.role)}
                          </span>
                        </div>
                        <p className="text-sm text-slate-500 dark:text-slate-400">所属机构：{user.org}</p>
                      </div>
                      {isOwner ? (
                        <span className="text-sm text-slate-500 dark:text-slate-400">Owner 权限固定，不可调整</span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleRoleToggle(user.id, user.role)}
                          disabled={busy}
                          className={workspaceSecondaryButtonClass}
                        >
                          {busy ? '保存中...' : user.role === 'admin' ? '降为成员' : '设为管理员'}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}
    </div>
  );
};

const SettingsPage = ({ currentUser, onLogout }: { currentUser: CurrentUser; onLogout: () => void }) => {
  return (
    <div className={`${workspacePageClass} mx-auto max-w-3xl space-y-8`}>
      <h3 className={workspaceSectionTitleClass}>系统设置</h3>

      <section className="space-y-4">
        <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">账号</h4>
        <div className={`${workspaceCardClass} flex flex-col gap-5 p-6 md:flex-row md:items-center md:justify-between`}>
          <div>
            <p className="font-medium text-slate-900 dark:text-white">当前账号</p>
            <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">登出后需重新输入用户名和密码。</p>
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">
                {currentUser.display_name}
              </span>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                {getRoleLabel(currentUser.role)}
              </span>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                {currentUser.organization_name}
              </span>
            </div>
          </div>
          <button onClick={onLogout} className={workspaceSecondaryButtonClass}>
            退出登录
          </button>
        </div>
      </section>

      <section className="space-y-4">
        <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">关于</h4>
        <div className={`${workspaceCardClass} space-y-3 p-6`}>
          <div className="flex justify-between text-sm">
            <span className="text-slate-500 dark:text-slate-400">产品</span>
            <span className="text-slate-700 dark:text-slate-200">星润课后复习系统</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-500 dark:text-slate-400">版本</span>
            <span className="font-mono text-slate-700 dark:text-slate-200">v1.0.0</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-500 dark:text-slate-400">AI 引擎</span>
            <span className="text-slate-700 dark:text-slate-200">由星润提供</span>
          </div>
        </div>
      </section>
    </div>
  );
};

const ClassManagementPage = ({ currentUser }: { currentUser: CurrentUser }) => {
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [teacherBindingByClassId, setTeacherBindingByClassId] = useState<Record<number, number | null>>({});
  const [expandedClassId, setExpandedClassId] = useState<number | 'new' | null>(null);
  const [formByClassId, setFormByClassId] = useState<Record<string, ClassFormValues>>(() => ({
    new: createEmptyClassForm(),
  }));
  const [selectedGradeFilter, setSelectedGradeFilter] = useState<string>('全部');
  const [newClassTeacherUserId, setNewClassTeacherUserId] = useState<number | null>(null);
  const [teacherSearchByClassId, setTeacherSearchByClassId] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState('');
  const [formError, setFormError] = useState('');
  const [assignmentError, setAssignmentError] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [teacherBindingSavingByClassId, setTeacherBindingSavingByClassId] = useState<Record<number, boolean>>({});
  const loadPageRequestVersionRef = useRef(0);
  const classInteractionLocked = saving || deleting;
  const hasTeacherBindingSavingRows = Object.values(teacherBindingSavingByClassId).some(Boolean);
  const classCardInteractionLocked = classInteractionLocked || hasTeacherBindingSavingRows;
  const pageRefreshLocked = classInteractionLocked || hasTeacherBindingSavingRows;
  const assignmentRefreshLocked = classInteractionLocked || hasTeacherBindingSavingRows;
  const gradeFilterOptions = ['全部', '一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三'];

  const getClassStateKey = (classId: number | 'new') => String(classId);

  const loadPage = useCallback(async (preferredExpandedClassId?: number | 'new' | null, options?: { preserveStateOnError?: boolean }): Promise<LoadPageResult> => {
    const preserveStateOnError = options?.preserveStateOnError ?? false;
    const requestVersion = ++loadPageRequestVersionRef.current;
    setLoading(true);
    setPageError('');
    try {
      const [classItems, userItems, teacherBindingData] = await Promise.all([
        apiFetch<ClassItem[]>('/api/classes'),
        apiFetch<UserItem[]>('/api/admin/users'),
        apiFetch<{ teacher_bindings: Record<number, number | null> }>('/api/classes/teacher-bindings'),
      ]);

      if (requestVersion !== loadPageRequestVersionRef.current) {
        return { status: 'stale' };
      }

      const normalizedTeacherBindings = Object.fromEntries(
        Object.entries(teacherBindingData.teacher_bindings).map(([classId, teacherUserId]) => [Number(classId), teacherUserId]),
      ) as Record<number, number | null>;

      setClasses(classItems);
      setUsers(userItems);
      setTeacherBindingByClassId(normalizedTeacherBindings);
      setFormByClassId((current) => {
        const nextForms: Record<string, ClassFormValues> = {
          new: current.new || createEmptyClassForm(),
        };
        classItems.forEach((item) => {
          nextForms[getClassStateKey(item.id)] = toClassFormValues(item);
        });
        return nextForms;
      });
      setExpandedClassId((current) => {
        const requestedExpansion = preferredExpandedClassId === undefined ? current : preferredExpandedClassId;
        if (requestedExpansion === 'new') {
          return 'new';
        }
        if (typeof requestedExpansion === 'number' && classItems.some((item) => item.id === requestedExpansion)) {
          return requestedExpansion;
        }
        return null;
      });
      return { status: 'success' };
    } catch (err) {
      if (requestVersion !== loadPageRequestVersionRef.current) {
        return { status: 'stale' };
      }

      const error = err instanceof Error ? err : new Error('班级管理数据加载失败');
      setPageError(error.message);
      if (!preserveStateOnError) {
        setClasses([]);
        setUsers([]);
        setTeacherBindingByClassId({});
        setFormByClassId({ new: createEmptyClassForm() });
        setNewClassTeacherUserId(null);
        setExpandedClassId(null);
      }
      return { status: 'refresh-error', error };
    } finally {
      if (requestVersion === loadPageRequestVersionRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadPage().catch(() => undefined);
  }, [loadPage]);

  const handleFieldChange = (classId: number | 'new', field: keyof ClassFormValues, value: string) => {
    const stateKey = getClassStateKey(classId);
    setFormByClassId((current) => ({
      ...current,
      [stateKey]: {
        ...(current[stateKey] || createEmptyClassForm()),
        [field]: value,
      },
    }));
  };

  const handleTeacherSearchChange = (classId: number | 'new', value: string) => {
    setTeacherSearchByClassId((current) => ({
      ...current,
      [getClassStateKey(classId)]: value,
    }));
  };

  const handleToggleExpandedClass = (classId: number | 'new') => {
    if (classCardInteractionLocked) {
      return;
    }
    setExpandedClassId((current) => current === classId ? null : classId);
    setFormError('');
    setAssignmentError('');
  };

  const handleSaveClass = async (classId: number | 'new') => {
    const currentForm = formByClassId[getClassStateKey(classId)] || createEmptyClassForm();
    const selectedTeacherUserId = classId === 'new'
      ? newClassTeacherUserId
      : (teacherBindingByClassId[classId] ?? classes.find((item) => item.id === classId)?.teacher_user_id ?? null);
    if (classId === 'new' && !selectedTeacherUserId) {
      setFormError('请先选择负责老师账号');
      return;
    }
    const selectedTeacher = typeof selectedTeacherUserId === 'number' ? users.find((user) => user.id === selectedTeacherUserId) : undefined;
    const payload = {
      name: normalizeClassNameInput(currentForm.name),
      subject: currentForm.subject.trim(),
      grade: currentForm.grade.trim(),
      teacher_name: selectedTeacher?.name || '',
      teacher_email: '',
    };

    if (!payload.name) {
      setFormError('班级名称不能为空');
      return;
    }

    setSaving(true);
    setFormError('');

    let createdClassId: number | null = null;
    let teacherBindingSucceeded = false;

    try {
      if (classId === 'new') {
        const created = await apiFetch<{ id: number; name: string }>('/api/classes', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        createdClassId = created.id;
        setFormByClassId((current) => ({
          ...current,
          new: createEmptyClassForm(),
        }));
        setNewClassTeacherUserId(null);
        loadPageRequestVersionRef.current += 1;
        await apiFetch(`/api/classes/${created.id}/teacher`, {
          method: 'PUT',
          body: JSON.stringify({ teacher_user_id: selectedTeacherUserId }),
        });
        teacherBindingSucceeded = true;
        const optimisticCreatedClass: ClassItem = {
          id: created.id,
          name: payload.name,
          subject: payload.subject,
          grade: payload.grade,
          teacher_name: selectedTeacher?.name || '',
          teacher_email: '',
          teacher_user_id: selectedTeacherUserId,
        };
        setClasses((current) => {
          const remaining = current.filter((item) => item.id !== created.id);
          return [...remaining, optimisticCreatedClass];
        });
        setTeacherBindingByClassId((current) => ({ ...current, [created.id]: selectedTeacherUserId }));
        setFormByClassId((current) => ({
          ...current,
          [getClassStateKey(created.id)]: toClassFormValues(optimisticCreatedClass),
        }));
        setExpandedClassId(created.id);
        const refreshResult = await loadPage(created.id, { preserveStateOnError: true });
        if (refreshResult.status === 'refresh-error') {
          setFormError(`班级和负责老师已保存，但列表刷新失败：${refreshResult.error.message}`);
        }
      } else {
        await apiFetch(`/api/classes/${classId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
        const refreshResult = await loadPage(classId, { preserveStateOnError: true });
        if (refreshResult.status === 'refresh-error') {
          setFormError(`班级已保存，但列表刷新失败：${refreshResult.error.message}`);
        }
      }
    } catch (err) {
      if (classId === 'new' && createdClassId != null && !teacherBindingSucceeded) {
        setFormError(err instanceof Error ? `班级已创建，但负责老师绑定失败：${err.message}` : '班级已创建，但负责老师绑定失败，请在班级卡片中重新选择老师');
        await loadPage(createdClassId, { preserveStateOnError: true });
        return;
      }
      setFormError(err instanceof Error ? err.message : '班级保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteClass = async (classId: number) => {
    const targetClass = classes.find((item) => item.id === classId);
    if (!targetClass) {
      return;
    }

    if (!window.confirm(`确定删除班级「${targetClass.name}」吗？`)) {
      return;
    }

    setDeleting(true);
    setFormError('');

    try {
      await apiFetch(`/api/classes/${classId}`, { method: 'DELETE' });
      setExpandedClassId((current) => current === classId ? null : current);
      await loadPage(null);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : '班级删除失败');
    } finally {
      setDeleting(false);
    }
  };

  const handleSelectTeacherForClass = async (classId: number, teacherUserId: number) => {
    if (classInteractionLocked || teacherBindingSavingByClassId[classId]) {
      return;
    }

    const previousClass = classes.find((item) => item.id === classId);
    const previousTeacherUserId = teacherBindingByClassId[classId] ?? previousClass?.teacher_user_id ?? null;
    const previousTeacherName = previousClass?.teacher_name || '';
    const selectedTeacher = users.find((user) => user.id === teacherUserId);

    setAssignmentError('');
    loadPageRequestVersionRef.current += 1;
    setTeacherBindingSavingByClassId((current) => ({ ...current, [classId]: true }));
    setTeacherBindingByClassId((current) => ({ ...current, [classId]: teacherUserId }));
    setClasses((current) => current.map((item) => (
      item.id === classId
        ? { ...item, teacher_name: selectedTeacher?.name || item.teacher_name, teacher_user_id: teacherUserId }
        : item
    )));

    try {
      await apiFetch(`/api/classes/${classId}/teacher`, {
        method: 'PUT',
        body: JSON.stringify({ teacher_user_id: teacherUserId }),
      });
      const refreshResult = await loadPage(classId, { preserveStateOnError: true });
      if (refreshResult.status === 'refresh-error') {
        setAssignmentError(`老师绑定已保存，但列表刷新失败：${refreshResult.error.message}`);
      }
    } catch (err) {
      setTeacherBindingByClassId((current) => resolveTeacherBindingRollbackTeacherBindings(current, classId, previousTeacherUserId, teacherUserId));
      setClasses((current) => current.map((item) => (
        item.id === classId
          ? resolveTeacherBindingRollbackClassItem(item, teacherUserId, previousTeacherUserId, previousTeacherName)
          : item
      )));
      setAssignmentError(err instanceof Error ? err.message : '班级老师分配保存失败');
    } finally {
      setTeacherBindingSavingByClassId((current) => {
        const nextState = { ...current };
        delete nextState[classId];
        return nextState;
      });
    }
  };

  const filteredClasses = classes.filter((item) => {
    if (selectedGradeFilter === '全部') {
      return true;
    }
    return item.grade === selectedGradeFilter;
  });

  const newClassForm = formByClassId.new || createEmptyClassForm();
  const newClassExpanded = expandedClassId === 'new';
  const newClassTeacher = newClassTeacherUserId == null ? undefined : users.find((user) => user.id === newClassTeacherUserId);
  const newClassFilteredUsers = users.filter((user) => {
    const keyword = (teacherSearchByClassId.new || '').trim().toLowerCase();
    if (!keyword) {
      return true;
    }
    return [user.name, user.org, getRoleLabel(user.role)]
      .some((value) => value.toLowerCase().includes(keyword));
  });

  return (
    <div className={`${workspacePageClass} space-y-8`}>
      <section className={`${workspaceCardClass} space-y-4 p-6`}>
        <p className="text-sm uppercase tracking-[0.25em] text-sky-600">Class Workspace</p>
        <div>
          <h3 className="text-2xl font-bold text-slate-900 dark:text-white">班级管理</h3>
          <p className="mt-2 max-w-3xl text-sm text-slate-500 dark:text-slate-400">
            在这里统一管理 {currentUser.organization_name} 的班级信息与负责老师安排。
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">班级数量</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{classes.length}</p>
          </div>
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">成员数量</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{users.length}</p>
          </div>
        </div>
      </section>

      {pageError && (
        <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
          <AlertCircle size={16} />
          {pageError}
        </div>
      )}

      <section className={`${workspaceCardClass} space-y-5 p-6`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h4 className="text-xl font-semibold text-slate-900 dark:text-white">班级卡片</h4>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => loadPage(expandedClassId).catch(() => undefined)}
              disabled={pageRefreshLocked}
              className={workspaceSecondaryButtonClass}
            >
              刷新列表
            </button>
            <button
              type="button"
              onClick={() => handleToggleExpandedClass('new')}
              disabled={classCardInteractionLocked}
              className={workspacePrimaryButtonClass}
            >
              <PlusCircle size={18} />
              新建班级
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 border-t border-sky-100/80 pt-4 dark:border-white/10">
          {gradeFilterOptions.map((option) => {
            const active = option === selectedGradeFilter;
            return (
              <button
                key={option}
                type="button"
                onClick={() => setSelectedGradeFilter(option)}
                className={cn(
                  'rounded-full border px-3 py-2 text-sm font-semibold transition',
                  active
                    ? 'border-sky-500 bg-sky-500 text-white shadow-sm dark:border-sky-400 dark:bg-sky-400 dark:text-slate-950'
                    : 'border-sky-100 bg-white/80 text-slate-600 hover:border-sky-200 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10',
                )}
              >
                {option}
              </button>
            );
          })}
        </div>

        {loading ? (
          <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
            正在加载班级数据...
          </div>
        ) : (
          <div className="grid gap-4">
            <div className={`${workspaceSoftCardClass} overflow-hidden p-5`}>
              <button
                type="button"
                onClick={() => handleToggleExpandedClass('new')}
                disabled={classCardInteractionLocked}
                className={cn(
                  'flex w-full flex-col gap-4 text-left lg:flex-row lg:items-center lg:justify-between',
                  classCardInteractionLocked ? 'cursor-not-allowed' : 'cursor-pointer',
                )}
              >
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-lg font-semibold text-slate-900 dark:text-white">新建班级</span>
                    <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                      NEW
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                    {newClassForm.subject.trim() ? (
                      <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:bg-sky-500/10 dark:text-sky-300">
                        {newClassForm.subject.trim()}
                      </span>
                    ) : null}
                    <span>当前老师：{newClassTeacher?.name || '待选择负责老师'}</span>
                    <span>创建时会直接绑定该老师账号</span>
                  </div>
                </div>
              </button>

              {newClassExpanded && (
                <div className="mt-5 space-y-5 border-t border-sky-100/80 pt-5 dark:border-white/10">
                  {formError && (
                    <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                      <AlertCircle size={16} />
                      {formError}
                    </div>
                  )}

                  <div className="grid gap-4 md:grid-cols-2">
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">班级名称</span>
                      <input
                        type="text"
                        value={newClassForm.name}
                        onChange={(e) => handleFieldChange('new', 'name', e.target.value)}
                        className={workspaceFieldClass}
                        placeholder="如：六年级数学冲刺班"
                      />
                    </label>
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">科目</span>
                      <input
                        type="text"
                        value={newClassForm.subject}
                        onChange={(e) => handleFieldChange('new', 'subject', e.target.value)}
                        className={workspaceFieldClass}
                        placeholder="如：数学"
                      />
                    </label>
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">年级</span>
                      <input
                        type="text"
                        value={newClassForm.grade}
                        onChange={(e) => handleFieldChange('new', 'grade', e.target.value)}
                        className={workspaceFieldClass}
                        placeholder="如：六年级"
                      />
                    </label>
                  </div>

                  <div className={`${workspaceSoftCardClass} space-y-3 p-4`}>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">命名统一规则</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">新建或编辑班级时会优先统一成“六年级 2 班 / 初一 3 班 / 高二 1 班”的格式。</p>
                  </div>

                  <div className={`${workspaceCardClass} space-y-5 p-5`}>
                    <div>
                      <h4 className="text-xl font-semibold text-slate-900 dark:text-white">负责老师</h4>
                      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">新建班级时必须选择一个负责老师账号，系统会同步老师姓名。</p>
                    </div>

                    <label className="relative block">
                      <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-400" size={18} />
                      <input
                        type="text"
                        value={teacherSearchByClassId.new || ''}
                        onChange={(e) => handleTeacherSearchChange('new', e.target.value)}
                        placeholder="搜索老师"
                        className={`${workspaceFieldClass} rounded-full py-2.5 pl-11 pr-4`}
                      />
                    </label>

                    {users.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                        当前暂无成员，成员通过审批后会出现在这里。
                      </div>
                    ) : newClassFilteredUsers.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                        没有匹配到老师，请调整搜索关键词。
                      </div>
                    ) : (
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        {newClassFilteredUsers.map((user) => {
                          const checked = newClassTeacherUserId === user.id;
                          return (
                            <label
                              key={`new-${user.id}`}
                              className={cn(
                                'flex items-start gap-3 rounded-2xl border border-sky-100 bg-white/75 p-4 text-sm transition-colors dark:border-white/10 dark:bg-slate-950/55',
                                classInteractionLocked && 'opacity-70',
                                checked && 'border-sky-300 bg-sky-50/80 dark:border-sky-400/40 dark:bg-sky-500/10',
                              )}
                            >
                              <input
                                type="radio"
                                name="class-teacher-new"
                                checked={checked}
                                disabled={classInteractionLocked}
                                onChange={() => setNewClassTeacherUserId(user.id)}
                                className="mt-1 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                              />
                              <span className="min-w-0">
                                <span className="flex flex-wrap items-center gap-2">
                                  <span className="font-semibold text-slate-900 dark:text-white">{user.name}</span>
                                  <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${getRoleBadgeClass(user.role)}`}>
                                    {getRoleLabel(user.role)}
                                  </span>
                                </span>
                                <span className="mt-1 block text-slate-500 dark:text-slate-400">所属机构：{user.org}</span>
                                <span className="mt-1 block text-slate-500 dark:text-slate-400">{checked ? '将作为创建后的负责老师' : '选择为负责老师'}</span>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col gap-3 border-t border-sky-100/80 pt-5 sm:flex-row sm:items-center sm:justify-end dark:border-white/10">
                    <button
                      type="button"
                      onClick={() => handleSaveClass('new')}
                      disabled={classCardInteractionLocked}
                      className={workspacePrimaryButtonClass}
                    >
                      {saving ? '保存中...' : '创建班级'}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {filteredClasses.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                {classes.length === 0 ? '暂无班级，展开上方新建卡片开始创建。' : `当前筛选“${selectedGradeFilter}”下暂无班级。`}
              </div>
            ) : null}

            {filteredClasses.map((item) => {
              const isExpanded = expandedClassId === item.id;
              const formState = formByClassId[getClassStateKey(item.id)] || toClassFormValues(item);
              const teacherSearch = teacherSearchByClassId[getClassStateKey(item.id)] || '';
              const currentTeacherUserId = teacherBindingByClassId[item.id] ?? item.teacher_user_id ?? null;
              const currentTeacher = currentTeacherUserId == null ? undefined : users.find((user) => user.id === currentTeacherUserId);
              const teacherSummary = currentTeacher?.name || item.teacher_name || '未分配老师';
              const teacherBindingSaving = Boolean(teacherBindingSavingByClassId[item.id]);
              const filteredUsers = users.filter((user) => {
                const keyword = teacherSearch.trim().toLowerCase();
                if (!keyword) {
                  return true;
                }
                return [user.name, user.org, getRoleLabel(user.role)]
                  .some((value) => value.toLowerCase().includes(keyword));
              });

              return (
                <div key={item.id} className={`${workspaceSoftCardClass} overflow-hidden p-5`}>
                  <button
                    type="button"
                    onClick={() => handleToggleExpandedClass(item.id)}
                    disabled={classCardInteractionLocked}
                    className={cn(
                      'flex w-full flex-col gap-4 text-left lg:flex-row lg:items-center lg:justify-between',
                      classCardInteractionLocked ? 'cursor-not-allowed' : 'cursor-pointer',
                    )}
                  >
                    <div className="space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-lg font-semibold text-slate-900 dark:text-white">{item.name}</span>
                        {item.subject && (
                          <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:bg-sky-500/10 dark:text-sky-300">
                            {item.subject}
                          </span>
                        )}
                      </div>
                      <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
                        <span>{item.grade || '未填写年级'}</span>
                        <span>当前老师：{teacherSummary}</span>
                      </div>
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="mt-5 space-y-5 border-t border-sky-100/80 pt-5 dark:border-white/10">
                      {formError && (
                        <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                          <AlertCircle size={16} />
                          {formError}
                        </div>
                      )}

                      <div className="grid gap-4 md:grid-cols-2">
                        <label className="space-y-2 text-sm">
                          <span className="text-slate-500 dark:text-slate-400">班级名称</span>
                          <input
                            type="text"
                            value={formState.name}
                            onChange={(e) => handleFieldChange(item.id, 'name', e.target.value)}
                            className={workspaceFieldClass}
                            placeholder="如：六年级数学冲刺班"
                          />
                        </label>
                        <label className="space-y-2 text-sm">
                          <span className="text-slate-500 dark:text-slate-400">科目</span>
                          <input
                            type="text"
                            value={formState.subject}
                            onChange={(e) => handleFieldChange(item.id, 'subject', e.target.value)}
                            className={workspaceFieldClass}
                            placeholder="如：数学"
                          />
                        </label>
                        <label className="space-y-2 text-sm">
                          <span className="text-slate-500 dark:text-slate-400">年级</span>
                          <input
                            type="text"
                            value={formState.grade}
                            onChange={(e) => handleFieldChange(item.id, 'grade', e.target.value)}
                            className={workspaceFieldClass}
                            placeholder="如：六年级"
                          />
                        </label>
                        <label className="space-y-2 text-sm">
                          <span className="text-slate-500 dark:text-slate-400">负责老师</span>
                          <div className={`${workspaceFieldClass} flex min-h-12 items-center`}>{teacherSummary}</div>
                        </label>
                      </div>

                      <div className={`${workspaceSoftCardClass} space-y-3 p-4`}>
                        <p className="text-sm font-semibold text-slate-900 dark:text-white">命名统一规则</p>
                        <p className="text-sm text-slate-500 dark:text-slate-400">新建或编辑班级时会优先统一成“六年级 2 班 / 初一 3 班 / 高二 1 班”的格式。</p>
                      </div>

                      <div className="flex flex-col gap-3 border-t border-sky-100/80 pt-5 sm:flex-row sm:items-center sm:justify-between dark:border-white/10">
                        <button
                          type="button"
                          onClick={() => handleDeleteClass(item.id)}
                          disabled={classCardInteractionLocked}
                          className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-rose-200 bg-rose-50 px-5 py-3 font-semibold text-rose-600 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
                        >
                          <Trash2 size={18} />
                          {deleting ? '删除中...' : '删除当前班级'}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSaveClass(item.id)}
                          disabled={classCardInteractionLocked}
                          className={workspacePrimaryButtonClass}
                        >
                          {saving ? '保存中...' : '保存班级'}
                        </button>
                      </div>

                      <div className={`${workspaceCardClass} space-y-5 p-5`}>
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <h4 className="text-xl font-semibold text-slate-900 dark:text-white">班级老师分配</h4>
                            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">当前老师：{teacherSummary}</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => loadPage(item.id).catch(() => undefined)}
                            disabled={assignmentRefreshLocked}
                            className={workspaceSecondaryButtonClass}
                          >
                            刷新分配
                          </button>
                        </div>

                        {assignmentError && (
                          <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                            <AlertCircle size={16} />
                            {assignmentError}
                          </div>
                        )}

                        <label className="relative block">
                          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-400" size={18} />
                          <input
                            type="text"
                            value={teacherSearch}
                            onChange={(e) => handleTeacherSearchChange(item.id, e.target.value)}
                            placeholder="搜索老师"
                            className={`${workspaceFieldClass} rounded-full py-2.5 pl-11 pr-4`}
                          />
                        </label>

                        {users.length === 0 ? (
                          <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                            当前暂无成员，成员通过审批后会出现在这里。
                          </div>
                        ) : filteredUsers.length === 0 ? (
                          <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                            没有匹配到老师，请调整搜索关键词。
                          </div>
                        ) : (
                          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                            {filteredUsers.map((user) => {
                              const checked = currentTeacherUserId === user.id;
                              return (
                                <label
                                  key={`${item.id}-${user.id}`}
                                  className={cn(
                                    'flex items-start gap-3 rounded-2xl border border-sky-100 bg-white/75 p-4 text-sm transition-colors dark:border-white/10 dark:bg-slate-950/55',
                                    (teacherBindingSaving || classInteractionLocked) && 'opacity-70',
                                    checked && 'border-sky-300 bg-sky-50/80 dark:border-sky-400/40 dark:bg-sky-500/10',
                                  )}
                                >
                                  <input
                                    type="radio"
                                    name={`class-teacher-${item.id}`}
                                    checked={checked}
                                    disabled={teacherBindingSaving || classInteractionLocked}
                                    onChange={() => handleSelectTeacherForClass(item.id, user.id)}
                                    className="mt-1 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                                  />
                                  <span className="min-w-0">
                                    <span className="flex flex-wrap items-center gap-2">
                                      <span className="font-semibold text-slate-900 dark:text-white">{user.name}</span>
                                      <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${getRoleBadgeClass(user.role)}`}>
                                        {getRoleLabel(user.role)}
                                      </span>
                                    </span>
                                    <span className="mt-1 block text-slate-500 dark:text-slate-400">所属机构：{user.org}</span>
                                    <span className="mt-1 block text-slate-500 dark:text-slate-400">{teacherBindingSaving ? '保存中...' : checked ? '当前负责老师' : '设为当前负责老师'}</span>
                                  </span>
                                </label>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};

// --- Login Modal ---

const LoginModal = ({
  onLogin,
  onClose,
  onOpenRegister,
}: {
  onLogin: (token: string) => void;
  onClose: () => void;
  onOpenRegister: () => void;
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
              <label className="text-sm text-gray-400">用户名</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                placeholder="请输入用户名"
                className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm text-gray-400">密码</label>
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

          <button
            type="button"
            onClick={onOpenRegister}
            className="w-full mt-4 py-3 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-sm font-medium transition-colors"
          >
            还没有账号？提交注册申请
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
};

const RegisterRequestModal = ({ onClose }: { onClose: () => void }) => {
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
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
      const res = await fetch('/api/register-request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          display_name: displayName,
          password,
          organization_name: '星润Starain',
        }),
      });
      const raw = await res.text();
      const data = raw ? JSON.parse(raw) as { error?: string } : {};
      if (!res.ok) {
        throw new Error(data.error || '注册申请提交失败');
      }
      setSuccess('申请已提交，等待 Kayn 审批通过后即可登录后台。');
      setUsername('');
      setDisplayName('');
      setPassword('');
      setConfirmPassword('');
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
              <h2 className="text-xl font-semibold">提交注册申请</h2>
              <p className="text-sm text-gray-500 mt-1">所有新账号默认加入机构 星润Starain，审批通过后才能进入后台。</p>
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
                <label className="text-sm text-gray-400">用户名 <span className="text-gray-600 font-normal">· 登录用</span></label>
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
                <label className="text-sm text-gray-400">昵称 <span className="text-gray-600 font-normal">· 显示用</span></label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  required
                  placeholder="后台显示的名字，可修改"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm text-gray-400">机构</label>
              <div className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-gray-200">
                星润Starain
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
              <p className="text-xs text-sky-700 tracking-[0.28em]">AI Edu Platform</p>
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
              LEGAL
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
          <p>© 2026 Starain. All rights reserved.</p>
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
  onRegister,
  activeLegalPage,
  isDark = false,
  onToggleDarkMode,
}: {
  onLogin: () => void;
  onRegister: () => void;
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
              AI Edu Platform
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
              onClick={onRegister}
              className="hidden sm:inline-flex rounded-full border border-sky-200 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition-all hover:bg-sky-50 active:scale-95 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
            >
              申请注册
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
      <section className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(34,199,232,0.18),_transparent_28%),radial-gradient(circle_at_85%_15%,_rgba(47,128,237,0.16),_transparent_24%),linear-gradient(180deg,_#F8FBFF_0%,_#EEF6FF_100%)] dark:bg-[#0f172a]">
        <HeroBackgroundVideo />
        <div className="absolute inset-x-0 top-0 h-full">
          <motion.div
            animate={{ scale: [1, 1.12, 1], opacity: [0.5, 0.65, 0.5] }}
            transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
            className="absolute left-[-6%] top-[8%] h-72 w-72 rounded-full bg-cyan-200/50 blur-[120px] dark:bg-cyan-500/10"
          />
          <motion.div
            animate={{ scale: [1, 1.1, 1], opacity: [0.4, 0.55, 0.4] }}
            transition={{ duration: 9, repeat: Infinity, ease: "easeInOut", delay: 2 }}
            className="absolute right-[-8%] top-[18%] h-80 w-80 rounded-full bg-blue-200/40 blur-[140px] dark:bg-blue-500/10"
          />
          <motion.div
            animate={{ scale: [1, 1.15, 1], opacity: [0.7, 0.85, 0.7] }}
            transition={{ duration: 11, repeat: Infinity, ease: "easeInOut", delay: 4 }}
            className="absolute bottom-[-12%] left-[25%] h-96 w-96 rounded-full bg-white/70 blur-[100px] dark:bg-slate-700/20"
          />
        </div>

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
                AI EDUCATION PLATFORM FOR INSTITUTIONS
              </motion.span>
              <motion.h1
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.18, duration: 0.72, ease: [0.16, 1, 0.3, 1] }}
                className="mt-8 max-w-4xl text-4xl font-black leading-[1.02] tracking-tight text-slate-950 sm:text-6xl md:text-7xl dark:text-white"
              >
                Starain，面向教育机构的 AI 教学平台
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.32, duration: 0.78 }}
                className="mt-7 max-w-2xl text-base leading-8 text-slate-700 sm:text-lg md:text-xl dark:text-slate-200"
              >
                从复习资料生成，到题库沉淀、讲义生成与教学协同，Starain 正在把分散的 AI 教学能力组织成一个真正可落地的平台。
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.46, duration: 0.78 }}
                className="mt-8 space-y-3"
              >
                {[
                  ['复习资料生成', '把课堂内容快速整理成学生可直接使用的复习材料。'],
                  ['题库与内容沉淀', '把题目、讲义与教学素材沉淀为可复用的内容资产。'],
                  ['教学协同交付', '让教师、教研与机构团队在同一平台里完成生产与交付。'],
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
                className="mt-10 flex flex-col gap-4 sm:flex-row"
              >
                <a
                  href="#features"
                  className="inline-flex items-center justify-center gap-2 rounded-2xl bg-sky-600 px-8 py-4 text-base font-bold text-white shadow-[0_24px_60px_rgba(34,199,232,0.28)] transition-all hover:bg-sky-500 active:scale-95"
                >
                  查看平台方案
                  <ArrowRight size={18} />
                </a>
                <button
                  onClick={onRegister}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-white/55 bg-white/55 px-8 py-4 text-base font-bold text-slate-800 backdrop-blur-md transition-all hover:bg-white/72 active:scale-95 dark:border-white/12 dark:bg-slate-950/30 dark:text-slate-100 dark:hover:bg-slate-950/42"
                >
                  <User size={18} />
                  申请试用
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
                    <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500 dark:text-slate-400">PLATFORM SNAPSHOT</p>
                    <p className="mt-2 text-lg font-semibold text-slate-900 dark:text-white">不止一个助手，而是一套持续扩展的 AI Edu Platform</p>
                  </div>
                  <div className="rounded-full border border-emerald-200/80 bg-emerald-50/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300">
                    Live
                  </div>
                </div>

                <div className="mt-5 space-y-3">
                  {[
                    { icon: Upload, title: '复习资料', body: '课堂内容生成讲义、总结与学生复习材料' },
                    { icon: CheckCircle2, title: '题库系统', body: '题目与知识点持续归档，支持后续调用与组织' },
                    { icon: FileText, title: '教学交付', body: '面向教师与机构团队沉淀可复用的教学资产' },
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
                    课堂录音、笔记与教学内容进入平台后，被整理成结构化复习资料、练习内容与可复用的交付资产。
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
                <h3 className="text-2xl font-bold mb-4 text-slate-900 dark:text-white">把错误沉淀成可追踪资产</h3>
                <p className="text-slate-600 dark:text-slate-300">
                  不是一次性纠错，而是持续记录高频错误、薄弱点与个性化复习路径。
                </p>
              </div>
              <div className="mt-8 flex flex-wrap gap-2">
                <span className="rounded-full bg-cyan-50 px-3 py-1 text-[10px] font-bold tracking-widest text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300">错因沉淀</span>
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
                <h3 className="text-2xl font-bold mb-4 text-slate-900 dark:text-white">把题目沉淀成可调用的题库系统</h3>
                <p className="text-slate-600 dark:text-slate-300">
                  面向 AP、A-Level、IB 等课程，把零散题目变成可标签化、可复用、可自动组卷的题库资产。
                </p>
              </div>
              <div className="mt-8 flex items-center gap-2 text-blue-600 font-bold text-sm dark:text-blue-400">
                <span>AP / A-Level / IB</span>
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
                我们先在自己的教育机构中解决复习资料、题库沉淀、讲义生成与教学协同问题，再把这套已经跑通的流程产品化，服务更多同行团队。
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
                  body: '错题沉淀、题库调用与讲义生成作为统一工作流持续复用。',
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
                AI Edu Platform
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
          <p className="text-sm text-slate-500 dark:text-slate-400">© 2026 Starain. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

// --- Main App ---

export default function App() {
  const [token, setToken] = useState<string>(() => localStorage.getItem('xr_token') || '');
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [authReady, setAuthReady] = useState<boolean>(() => !Boolean(localStorage.getItem('xr_token')));
  const [isDark, setIsDark] = useState<boolean>(getInitialDarkModePreference);
  const [showLogin, setShowLogin] = useState(false);
  const [showRegister, setShowRegister] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [activePage, setActivePage] = useState<Page>('dashboard');
  const [showLanding, setShowLanding] = useState(false);
  const [landingHash, setLandingHash] = useState<string>(() =>
    typeof window === 'undefined' ? '' : window.location.hash,
  );
  const [calendarClasses, setCalendarClasses] = useState<ClassItem[]>([]);
  const [calendarLessons, setCalendarLessons] = useState<Lesson[]>([]);
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [calendarAnchorDate, setCalendarAnchorDate] = useState<string>(() => getTodayIsoDate());

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    document.documentElement.classList.toggle('dark', isDark);

    try {
      window.localStorage?.setItem?.('xr_dark', String(isDark));
    } catch {
      // Ignore storage access issues and keep the UI functional.
    }
  }, [isDark]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const syncHash = () => {
      setLandingHash(window.location.hash);
    };

    syncHash();
    window.addEventListener('hashchange', syncHash);
    return () => window.removeEventListener('hashchange', syncHash);
  }, []);

  const landingLegalPage = getLandingLegalPageFromHash(landingHash);

  useEffect(() => {
    if (!token) {
      setCurrentUser(null);
      setAuthReady(true);
      return;
    }

    let cancelled = false;
    setAuthReady(false);

    apiFetch<CurrentUser>('/api/me')
      .then((user) => {
        if (cancelled) {
          return;
        }
        setCurrentUser(user);
        setActivePage((page) => {
          if (page === 'accounts' && user.role !== 'owner') {
            return 'dashboard';
          }
          if (page === 'classes' && user.role !== 'owner' && user.role !== 'admin') {
            return 'dashboard';
          }
          return page;
        });
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        localStorage.removeItem('xr_token');
        setToken('');
        setCurrentUser(null);
      })
      .finally(() => {
        if (!cancelled) {
          setAuthReady(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!token || !currentUser) {
      setCalendarClasses([]);
      setCalendarLessons([]);
      setCalendarLoading(false);
      setCalendarAnchorDate(getTodayIsoDate());
      return;
    }

    if (!authReady) {
      return;
    }

    let cancelled = false;
    setCalendarLoading(true);

    Promise.all([apiFetch<ClassItem[]>('/api/classes'), apiFetch<Lesson[]>('/api/lessons')])
      .then(([classes, lessons]) => {
        if (cancelled) {
          return;
        }
        setCalendarClasses(classes);
        setCalendarLessons(lessons);
        setCalendarAnchorDate(getLatestLessonDate(lessons));
      })
      .catch(console.error)
      .finally(() => {
        if (!cancelled) {
          setCalendarLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [authReady, currentUser, token]);

  const handleLogin = (t: string) => {
    localStorage.setItem('xr_token', t);
    setToken(t);
    setShowLogin(false);
    setShowLanding(false);
  };

  const handleLogout = () => {
    localStorage.removeItem('xr_token');
    setToken('');
    setCurrentUser(null);
    setShowLanding(false);
    setActivePage('dashboard');
    setMobileNavOpen(false);
  };

  const handleReviewGenerationSuccess = () => {
    setActivePage('review-generation');
  };

  const handlePreviousCalendarWeek = () => {
    setCalendarAnchorDate((current) => shiftIsoDate(current, -7));
  };

  const handleNextCalendarWeek = () => {
    setCalendarAnchorDate((current) => shiftIsoDate(current, 7));
  };

  const pageTitle: Record<Page, string> = {
    dashboard: '工作台',
    'review-generation': '复习生成',
    consultation: '咨询记录',
    calendar: '课程日历',
    classes: '班级管理',
    accounts: '账号审批',
    settings: '系统设置',
  };

  if (token && !authReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[linear-gradient(180deg,#f8fbff_0%,#eef6ff_100%)] dark:bg-[linear-gradient(180deg,#020617_0%,#0f172a_100%)]">
        <p className="text-sm text-slate-400 dark:text-slate-500">正在验证账号权限...</p>
      </div>
    );
  }

  if (!token || !currentUser || showLanding || landingLegalPage) {
    return (
      <>
        <LandingPage
          onLogin={token ? () => setShowLanding(false) : () => setShowLogin(true)}
          activeLegalPage={landingLegalPage}
          isDark={isDark}
          onToggleDarkMode={() => setIsDark((current) => !current)}
          onRegister={() => {
            if (token) {
              setShowLanding(false);
              return;
            }
            setShowRegister(true);
          }}
        />
        <AnimatePresence>
          {showLogin && (
            <LoginModal
              onLogin={handleLogin}
              onClose={() => setShowLogin(false)}
              onOpenRegister={() => {
                setShowLogin(false);
                setShowRegister(true);
              }}
            />
          )}
          {showRegister && (
            <RegisterRequestModal onClose={() => setShowRegister(false)} />
          )}
        </AnimatePresence>
      </>
    );
  }

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-[linear-gradient(180deg,#f8fbff_0%,#eef6ff_100%)] text-slate-900 dark:bg-[linear-gradient(180deg,#020617_0%,#0f172a_100%)] dark:text-slate-100">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[-8%] top-[8%] h-80 w-80 rounded-full bg-cyan-200/35 blur-[130px] dark:bg-cyan-500/10" />
        <div className="absolute right-[-10%] top-[12%] h-96 w-96 rounded-full bg-blue-200/30 blur-[150px] dark:bg-blue-500/10" />
        <div className="absolute bottom-[-14%] left-[28%] h-[28rem] w-[28rem] rounded-full bg-white/75 blur-[120px] dark:bg-slate-900/40" />
      </div>
      <div className="relative flex min-h-screen">
        <div className="fixed inset-y-0 left-0 z-30 hidden lg:block">
          <Sidebar
            activePage={activePage}
            currentUser={currentUser}
            onLogout={handleLogout}
            setActivePage={setActivePage}
            onProfileUpdated={(u, d) => setCurrentUser((c) => c ? { ...c, username: u, display_name: d } : c)}
          />
        </div>
        <AnimatePresence>
          {mobileNavOpen && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 lg:hidden"
            >
              <div className="absolute inset-0 bg-slate-950/45 backdrop-blur-sm" onClick={() => setMobileNavOpen(false)} />
              <motion.div
                initial={{ x: -24, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: -24, opacity: 0 }}
                transition={{ duration: 0.18 }}
                className="relative h-full w-[18.5rem] max-w-[86vw]"
              >
                <button
                  type="button"
                  onClick={() => setMobileNavOpen(false)}
                  className="absolute right-3 top-3 z-10 flex h-10 w-10 items-center justify-center rounded-full border border-sky-200 bg-white text-slate-500 shadow-sm transition-colors hover:bg-sky-50 hover:text-slate-800 dark:border-white/10 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                  aria-label="关闭导航"
                >
                  <X size={18} />
                </button>
                <Sidebar
                  activePage={activePage}
                  currentUser={currentUser}
                  onLogout={handleLogout}
                  setActivePage={setActivePage}
                  onNavigate={() => setMobileNavOpen(false)}
                  mobile={true}
                  onProfileUpdated={(u, d) => setCurrentUser((c) => c ? { ...c, username: u, display_name: d } : c)}
                />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
        <main className="flex min-w-0 flex-1 flex-col lg:pl-72">
          <Header
            title={pageTitle[activePage]}
            onGoHome={() => setShowLanding(true)}
            isDark={isDark}
            onToggleDarkMode={() => setIsDark((current) => !current)}
            onOpenSidebar={() => setMobileNavOpen(true)}
          />
          <div className="flex-1">
            <AnimatePresence mode="wait">
              <motion.div
                key={activePage}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.18 }}
              >
                {activePage === 'dashboard' && (
                  <Dashboard
                    currentUser={currentUser}
                    setActivePage={setActivePage}
                    activeClassCount={calendarClasses.length}
                  />
                )}
                {activePage === 'review-generation' && <ReviewGenerationPage onSuccess={handleReviewGenerationSuccess} />}
                {activePage === 'consultation' && <ConsultationPage currentUser={currentUser} />}
                {activePage === 'calendar' &&
                  (calendarLoading ? (
                    <div className={`${workspacePageClass}`}>
                      <div className={`${workspaceCardClass} p-8`}>
                        <XiaojimaoLoading label="正在整理课程日历..." />
                      </div>
                    </div>
                  ) : (
                    <CourseCalendarPage
                      anchorDate={calendarAnchorDate}
                      classes={calendarClasses}
                      lessons={calendarLessons}
                      onPreviousWeek={handlePreviousCalendarWeek}
                      onNextWeek={handleNextCalendarWeek}
                    />
                  ))}
                {activePage === 'classes' && (currentUser.role === 'owner' || currentUser.role === 'admin') && (
                  <ClassManagementPage currentUser={currentUser} />
                )}
                {activePage === 'accounts' && currentUser.role === 'owner' && <ApprovalPage currentUser={currentUser} />}
                {activePage === 'settings' && <SettingsPage currentUser={currentUser} onLogout={handleLogout} />}
              </motion.div>
            </AnimatePresence>
          </div>
        </main>
      </div>
    </div>
  );
}
