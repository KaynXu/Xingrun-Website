/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Home,
  PlusCircle,
  Database,
  CalendarDays,
  Settings,
  Search,
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
  Filter,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  ShieldCheck,
  Moon,
  Sun,
  X,
  ChevronDown,
  ChevronRight,
  Info,
  Save,
} from 'lucide-react';
import type { CourseCalendarCustomItemRecord, CourseCalendarCustomScheduleRecord, CourseCalendarScheduleRecord, CourseCalendarTimeBlock } from './courseCalendarData';
import { getCurrentWeekTuesday } from './courseCalendarData';
import { motion, AnimatePresence, useReducedMotion } from 'motion/react';
export {
  resolveTeacherBindingRollbackClassItem,
  resolveTeacherBindingRollbackTeacherBindings,
} from './features/student-center/teacherBindingRules';
import { WorkspacePageContent } from './features/navigation/WorkspacePageContent';
import { WorkspaceShellLayout } from './features/navigation/WorkspaceShellLayout';
import { ConsultationMeetingWorkbench } from './features/consultation/ConsultationMeetingWorkbench';
import { ConsultationPage } from './features/consultation/ConsultationPage';
import {
  canAccessSmartWrongQuestions,
  canOpenWorkspacePage,
  configurableWorkspacePages,
  getWorkspacePageFallback,
  hasOwnerAccess,
  hasStaffAccess,
} from './features/navigation/workspaceAccess';
import { FloatingFilterBar, FloatingOverviewFilter } from './components/FloatingFilterBar';
import {
  academicGradeGroups,
  academicGradeOptions,
  academicStageOptions,
  buildClassDisplayName,
  formatClassDisplayName,
  getAcademicGradeRank,
  getAcademicStageFromGrade,
  inferAcademicCohortYear,
  normalizeAcademicGradeLabel,
  normalizeClassNameInput,
} from './domain/classNaming';
import { StudentPortalPage } from './StudentTodayTasksPage';
import {
  createClassStudent,
  deleteClassStudent,
} from './classFeedbackGeneration';
import {
  apiFetch,
  buildAuthedPath,
  cn,
  getToken,
  readLocalStorageItem,
  removeLocalStorageItem,
  workspaceCardClass,
  workspaceFieldClass,
  workspaceGhostButtonClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSectionTextClass,
  workspaceSectionTitleClass,
  workspaceSoftCardClass,
  writeLocalStorageItem,
} from './workspaceShared';

export {
  apiFetch,
  buildAuthedPath,
  cn,
  getToken,
  readLocalStorageItem,
  removeLocalStorageItem,
  workspaceCardClass,
  workspaceFieldClass,
  workspaceGhostButtonClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSectionTextClass,
  workspaceSectionTitleClass,
  workspaceSoftCardClass,
  writeLocalStorageItem,
} from './workspaceShared';
export { SidebarAccountSheet } from './features/navigation/Sidebar';

// --- Types ---

type Role = 'super_owner' | 'owner' | 'admin' | 'member';
type Page =
  | 'dashboard'
  | 'review-generation'
  | 'class-feedback-generation'
  | 'consultation'
  | 'calendar'
  | 'smartWrongQuestions'
  | 'classes'
  | 'accounts'
  | 'credit'
  | 'settings';
type LandingLegalDocumentKey = 'privacy' | 'terms';
type PublicAuthModal = 'login' | 'apply-organization' | 'join-organization' | 'password-reset';

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
  record_status?: string;
  generation_error?: string;
}

interface ReviewPlanCreateResponse {
  id: number;
  success?: boolean;
  status?: string;
  duplicate?: boolean;
}

interface ApiSettings {
  provider: string;
}

export interface ClassItem {
  id: number;
  name: string;
  subject: string;
  grade: string;
  stage?: string;
  current_grade?: string;
  class_number?: string;
  cohort_year?: number;
  show_cohort_year?: boolean | number;
  is_bridge?: boolean;
  bridge_target?: string;
  content_track?: string;
  last_promoted_at?: string;
  teacher_name?: string;
  teacher_email?: string;
  teacher_user_id?: number | null;
  lesson_count?: number;
  student_count?: number;
}

export interface ConsultationRecord {
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
  flow_stage: string;
  completed_stages: string[];
  test_taken: string;
  test_images: Array<{ url: string; filename: string }>;
  trial_taken: string;
  trial_time_slot: string;
  trial_class_id: number | null;
  trial_class_manual: string;
  trial_teacher: string;
  trial_feedback: string;
  success_class_id: number | null;
  success_class_manual: string;
  end_note: string;
  ended_at: string;
  created_at: string;
  updated_at: string;
}

export type ConsultationFormValues = Omit<ConsultationRecord, 'id' | 'created_at' | 'updated_at'>;
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

export interface ConsultationTeacherOption {
  teacher_id: string;
  display_name: string;
  aliases: string[];
}

interface ConsultationBatchDraftItem {
  action: 'create' | 'update';
  target_id: number | null;
  reason: string;
  fields: Partial<ConsultationFormValues>;
  warnings: string[];
}

interface ConsultationBatchParseResponse {
  items: ConsultationBatchDraftItem[];
  warnings: string[];
}

export interface CurrentUser {
  id: number;
  username: string;
  display_name: string;
  role: Role;
  status: string;
  organization_id: number;
  organization_name: string;
  created_at: string;
  visible_pages?: Page[];
  requires_class_claim?: boolean;
}

interface RegistrationRequestItem {
  id: number;
  username: string;
  display_name: string;
  organization_name: string;
  status: string;
  created_at: string;
}

interface OrganizationRequestItem {
  id: number;
  organization_name: string;
  username: string;
  display_name: string;
  status: string;
  created_at: string;
}

interface OrganizationInviteInfo {
  organization_name: string;
  invite_code: string;
  invite_link: string;
  join_path?: string;
}

interface OrganizationSummaryItem {
  id: number;
  name: string;
  created_at: string;
  member_count: number;
  owner_count: number;
  class_count: number;
  lesson_count: number;
}

export interface UserItem {
  id: number;
  name: string;
  org: string;
  role: Role;
  username?: string;
  last_login?: string | null;
  visible_pages?: Page[];
}

type MemberBindingSummaryStatus = 'healthy' | 'needs_review' | 'incomplete';

interface MemberBindingSummary {
  user_id: number;
  mini_teacher_bound: boolean;
  responsible_classes: Array<{
    id: number;
    name: string;
  }>;
  mapping_summary: {
    status: MemberBindingSummaryStatus;
    mapped_count: number;
    needs_review_count: number;
    unmapped_count: number;
    ambiguous_count: number;
  };
}

interface ApprovalPageProps {
  currentUser: CurrentUser;
  onOpenClassBinding: (target: ClassBindingTarget) => void;
}

export type ClassBindingTarget = {
  teacherUserId: number;
  teacherName: string;
};

function getCurrentClassDisplayName(item: ClassItem | null | undefined, showCohortYear = false): string {
  return formatClassDisplayName(item, { showCohortYear });
}

function getCurrentClassDisplayNameById(
  classes: ClassItem[],
  classId: number | null | undefined,
  fallbackName?: string | null,
  showCohortYear = false,
): string {
  const classItem = classId == null ? undefined : classes.find((item) => item.id === classId);
  return getCurrentClassDisplayName(classItem, showCohortYear) || fallbackName?.trim() || '';
}

const NORMALIZATION_EXAMPLES: Array<[string, string]> = [
  ['6年级2班', '六年级 2 班'],
  ['六年级二班', '六年级 2 班'],
  ['六年2班', '六年级 2 班'],
  ['七年级三班', '七年级 3 班'],
];

const gradeOptions = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '七年级', '八年级', '九年级', '初一', '初二', '初三', '高一', '高二', '高三'];
const gradeFilterOptions = ['全部', ...gradeOptions, '未绑定'];
const academicSubjectOptions = ['数学', '物理', '国际数学'];
const academicSubjectFilterOptions = ['全部学科', ...academicSubjectOptions];
const studentCenterStageOptions = [...academicStageOptions];
const studentCenterGradeOptions = [...academicGradeOptions];
const studentCenterGradeGroups: Record<string, string[]> = academicGradeGroups;
function getRoleLabel(role: Role): string {
  if (role === 'super_owner') return '超级管理员';
  if (role === 'owner') return '机构负责人';
  if (role === 'admin') return '管理员';
  return '机构成员';
}

function canManageOwnerRole(role: Role): boolean {
  return role === 'super_owner';
}

function getMemberBindingStatusLabel(status: MemberBindingSummaryStatus): string {
  if (status === 'healthy') return '正常';
  if (status === 'needs_review') return '待复核';
  return '未完成';
}

function getMemberBindingStatusBadgeClass(status: MemberBindingSummaryStatus): string {
  if (status === 'healthy') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300';
  }
  if (status === 'needs_review') {
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300';
  }
  return 'border-slate-200 bg-slate-50 text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-slate-300';
}
function getRoleBadgeClass(role: Role): string {
  if (role === 'super_owner') {
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300';
  }
  if (role === 'owner') {
    return 'border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-500/30 dark:bg-orange-500/10 dark:text-orange-300';
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
          '当你申请注册、登录或使用机构账号时，我们会收集并使用你主动提交的账号信息、姓名、机构名称以及必要的身份校验信息，用于完成账号开通、权限管理与服务支持。',
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
          'Starain 当前提供并持续迭代的能力包括但不限于课后复习资料生成、题目整理、教学材料整理以及其他面向学校、机构和教学团队的 AI 教学交付支持能力。',
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

export function apiUploadFormWithProgress<T = unknown>(
  path: string,
  body: FormData,
  onProgress: (progress: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', path);
    const token = getToken();
    if (token) {
      xhr.setRequestHeader('X-Auth-Token', token);
    }
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || event.total <= 0) {
        return;
      }
      onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    };
    xhr.onload = () => {
      if (xhr.status === 401) {
        removeLocalStorageItem('xr_token');
        window.location.reload();
      }
      let payload: T & { error?: string };
      try {
        payload = JSON.parse(xhr.responseText || '{}') as T & { error?: string };
      } catch {
        payload = { error: xhr.statusText } as T & { error?: string };
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error(payload.error || xhr.statusText));
        return;
      }
      onProgress(100);
      resolve(payload);
    };
    xhr.onerror = () => reject(new Error('上传失败，请重试'));
    xhr.send(body);
  });
}

function getInitialDarkModePreference(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }

  try {
    const saved = readLocalStorageItem('xr_dark');
    if (saved !== null && saved !== undefined) {
      return saved === 'true';
    }
  } catch {
    // Ignore storage access issues and fall back to the system preference.
  }

  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
}

function getInitialMobileViewport(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }

  return window.matchMedia?.('(max-width: 1023px)').matches ?? false;
}

function getJoinInviteTokenFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/join\/([^/]+)$/);
  return match ? decodeURIComponent(match[1]) : null;
}

function clearJoinInvitePathIfNeeded(): void {
  if (typeof window === 'undefined') {
    return;
  }
  if (!getJoinInviteTokenFromPath(window.location.pathname)) {
    return;
  }
  window.history.replaceState({}, '', '/');
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

const consultationStatusOptions = ['待邀约', '跟进中', '已报班', '已劝退'];
const consultationFlowStages = ['已加小客服微信', '已加对应教师微信', '正在沟通细节', '待测试', '待试听', '成功进班', '试听失败', '咨询结束'];
const consultationProcessStages = ['已加小客服微信', '已加对应教师微信', '正在沟通细节', '待测试', '待试听'];
export type ConsultationResultStage = '成功进班' | '试听失败';
const consultationResultStages: ConsultationResultStage[] = ['成功进班', '试听失败'];
const consultationMeetingVersion = 'V2.0';
type ConsultationFlowSectionKey = 'base' | 'communication' | 'trial' | 'result';
type ConsultationFlowSectionState = { active: boolean; current: boolean };
const consultationFlowSectionOrder: ConsultationFlowSectionKey[] = ['base', 'communication', 'trial', 'result'];
const consultationFlowStageToSection: Record<string, ConsultationFlowSectionKey> = {
  '已加小客服微信': 'base',
  '已加对应教师微信': 'base',
  '正在沟通细节': 'communication',
  '待测试': 'communication',
  '待试听': 'trial',
  '成功进班': 'result',
  '试听失败': 'result',
  '咨询结束': 'result',
};
export type ConsultationFilterKey =
  | 'pending-7'
  | 'pending-30'
  | 'pending-over30'
  | 'ended-success'
  | 'ended-unsuccessful';

const consultationFilterGroups: Array<{
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

const consultationFilterLabels = consultationFilterGroups
  .flatMap((group) => group.items)
  .reduce((labels, item) => ({ ...labels, [item.key]: item.label }), {} as Record<ConsultationFilterKey, string>);

function consultationStatusClass(status: string): string {
  if (status === '待邀约' || status === '待跟进') return 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300';
  if (status === '跟进中' || status === '正在跟进') return 'bg-sky-50 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300';
  if (status === '已报班' || status === '完成') return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300';
  if (status === '已劝退') return 'bg-slate-100 text-slate-600 dark:bg-white/10 dark:text-slate-300';
  return 'bg-slate-100 text-slate-500 dark:bg-white/5 dark:text-slate-400';
}

function deriveConsultationDisplayStatus(stage: string): string {
  if (stage === '成功进班' || stage === '咨询结束') return '完成';
  if (stage === '已加小客服微信' || stage === '已加对应教师微信') return '待跟进';
  return '正在跟进';
}

function isConsultationEnded(stage: string): boolean {
  return stage === '咨询结束';
}

function isConsultationResultStage(stage: string): stage is ConsultationResultStage {
  return consultationResultStages.includes(stage as ConsultationResultStage);
}

function getConsultationFlowSectionStates(form: ConsultationFormValues): Record<ConsultationFlowSectionKey, ConsultationFlowSectionState> {
  const stages = [
    ...(Array.isArray(form.completed_stages) ? form.completed_stages : []),
    form.flow_stage,
  ].filter(Boolean);
  const currentSection = consultationFlowStageToSection[form.flow_stage] || 'base';
  const furthestSectionIndex = Math.max(
    consultationFlowSectionOrder.indexOf(currentSection),
    ...stages.map((stage) => consultationFlowSectionOrder.indexOf(consultationFlowStageToSection[stage] || 'base')),
  );
  return consultationFlowSectionOrder.reduce((states, section, index) => ({
    ...states,
    [section]: {
      active: index <= furthestSectionIndex,
      current: section === currentSection,
    },
  }), {} as Record<ConsultationFlowSectionKey, ConsultationFlowSectionState>);
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

function getConsultationFilterKey(record: ConsultationRecord, todayIso: string): ConsultationFilterKey {
  if (isConsultationEnded(record.flow_stage)) {
    if (consultationHasResult(record, '成功进班')) return 'ended-success';
    return 'ended-unsuccessful';
  }

  const ageDays = getConsultationAgeDays(record, todayIso);
  if (ageDays <= 7) return 'pending-7';
  if (ageDays <= 30) return 'pending-30';
  return 'pending-over30';
}

function getConsultationOver30SectionLabel(record: ConsultationRecord, todayIso: string): string {
  const ageDays = getConsultationAgeDays(record, todayIso);
  if (ageDays <= 60) return '两月内';
  if (ageDays <= 180) return '半年内';
  return '半年以上';
}

function sortConsultationsForFilter(records: ConsultationRecord[], filterKey: ConsultationFilterKey): ConsultationRecord[] {
  const sorted = [...records];
  if (filterKey.startsWith('pending-')) {
    return sorted.sort((a, b) => getConsultationRecordDateTime(a) - getConsultationRecordDateTime(b));
  }
  return sorted.sort((a, b) => getConsultationUpdatedTime(b) - getConsultationUpdatedTime(a));
}

function toggleConsultationStage(form: ConsultationFormValues, stage: string): ConsultationFormValues {
  if (isConsultationEnded(form.flow_stage)) return form;
  const currentStages = Array.isArray(form.completed_stages) ? form.completed_stages : [];
  const exists = currentStages.includes(stage);
  if (form.flow_stage === stage) return form;
  return { ...form, flow_stage: stage, completed_stages: exists ? currentStages : [...currentStages, stage] };
}

function toggleConsultationStageLight(values: ConsultationFormValues, stage: string): ConsultationFormValues {
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

function moveConsultationStage(values: ConsultationFormValues, stage: string): ConsultationFormValues {
  if (isConsultationEnded(values.flow_stage)) return values;
  const currentStages = Array.isArray(values.completed_stages) ? values.completed_stages : [];
  const completed_stages = currentStages.includes(stage) ? currentStages : [...currentStages, stage];
  return { ...values, flow_stage: stage, completed_stages };
}

function setConsultationResultStage(values: ConsultationFormValues, stage: ConsultationResultStage): ConsultationFormValues {
  if (isConsultationEnded(values.flow_stage)) return values;
  const currentStages = Array.isArray(values.completed_stages) ? values.completed_stages : [];
  const withoutResult = currentStages.filter((item) => !isConsultationResultStage(item));
  return { ...values, flow_stage: stage, completed_stages: [...withoutResult, stage] };
}

function clearConsultationResultStage(values: ConsultationFormValues): ConsultationFormValues {
  if (isConsultationEnded(values.flow_stage)) return values;
  const completed_stages = (Array.isArray(values.completed_stages) ? values.completed_stages : [])
    .filter((item) => !isConsultationResultStage(item));
  const flow_stage = isConsultationResultStage(values.flow_stage)
    ? completed_stages[completed_stages.length - 1] || consultationFlowStages[0]
    : values.flow_stage;
  return { ...values, flow_stage, completed_stages };
}

function endConsultationValues(values: ConsultationFormValues): ConsultationFormValues {
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

function restoreConsultationValues(values: ConsultationFormValues): ConsultationFormValues {
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
    flow_stage: record.flow_stage || consultationFormDefaults.flow_stage,
    completed_stages: Array.isArray(record.completed_stages) ? record.completed_stages : consultationFormDefaults.completed_stages,
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
    flow_stage: record.flow_stage || consultationFormDefaults.flow_stage,
    completed_stages: Array.isArray(record.completed_stages) ? record.completed_stages : consultationFormDefaults.completed_stages,
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

const consultationSurfaceClass =
  'border border-[#D9EEF7] bg-white shadow-[0_10px_28px_rgba(31,42,68,0.05)] dark:border-white/10 dark:bg-slate-950/78';
const consultationPanelClass =
  'rounded-[14px] border border-[#D9EEF7] bg-white shadow-[0_8px_22px_rgba(31,42,68,0.04)] dark:border-white/10 dark:bg-slate-950/72';
const consultationLabelClass =
  'consultation-field-label text-[11px] font-bold leading-4 text-[#7188A6] dark:text-slate-300';
const consultationValueClass =
  'consultation-field-value mt-0.5 min-w-0 break-words text-[13px] font-semibold leading-5 text-[#1F2A44] dark:text-slate-100';
const consultationInputClass =
  'consultation-field-input w-full rounded-lg border border-[#BFE5F8] bg-white px-3 py-2 text-sm text-[#1F2A44] outline-none transition placeholder:text-[#9AAEC4] focus:border-[#0EA5E9] focus:ring-3 focus:ring-sky-100 disabled:bg-[#F6FAFD] disabled:text-[#7188A6] dark:border-white/10 dark:bg-slate-900/75 dark:text-slate-100 dark:focus:border-sky-400 dark:focus:ring-sky-500/15';
function HeroBackgroundGrainient() {
  const reduceMotion = useReducedMotion();

  return (
    <div
      className="absolute inset-0 overflow-hidden"
      aria-hidden="true"
      data-background="grainient"
      data-grainient-palette="sky-cyan"
      data-grainient-motion="pronounced"
      data-grainient-style="flow-bands"
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_18%,rgba(34,199,232,0.54),transparent_24%),radial-gradient(circle_at_84%_16%,rgba(47,128,237,0.42),transparent_22%),radial-gradient(circle_at_52%_58%,rgba(255,255,255,0.52),transparent_24%),linear-gradient(135deg,rgba(240,249,255,0.99)_0%,rgba(214,239,255,0.97)_42%,rgba(197,228,255,0.95)_100%)] dark:bg-[radial-gradient(circle_at_12%_18%,rgba(34,199,232,0.24),transparent_24%),radial-gradient(circle_at_84%_16%,rgba(47,128,237,0.28),transparent_22%),radial-gradient(circle_at_52%_58%,rgba(125,211,252,0.12),transparent_24%),linear-gradient(135deg,rgba(7,14,25,0.99)_0%,rgba(10,22,38,0.97)_42%,rgba(16,32,54,0.95)_100%)]" />
      <motion.div
        className="absolute left-[-14%] top-[-18%] h-[32rem] w-[32rem] rounded-full bg-[radial-gradient(circle,rgba(34,199,232,0.72)_0%,rgba(34,199,232,0.28)_34%,transparent_72%)] opacity-90 blur-[72px] dark:bg-[radial-gradient(circle,rgba(34,199,232,0.42)_0%,rgba(34,199,232,0.16)_34%,transparent_72%)] dark:opacity-95"
        animate={reduceMotion ? undefined : { x: [0, 88, -52, 0], y: [0, 34, -58, 0], scale: [1, 1.16, 0.9, 1], rotate: [0, 14, -10, 0] }}
        transition={reduceMotion ? undefined : { duration: 10, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute right-[-10%] top-[4%] h-[30rem] w-[30rem] rounded-full bg-[radial-gradient(circle,rgba(47,128,237,0.52)_0%,rgba(47,128,237,0.22)_36%,transparent_72%)] opacity-90 blur-[84px] dark:bg-[radial-gradient(circle,rgba(47,128,237,0.34)_0%,rgba(47,128,237,0.16)_36%,transparent_72%)]"
        animate={reduceMotion ? undefined : { x: [0, -72, 46, 0], y: [0, 40, -34, 0], scale: [1, 0.92, 1.12, 1], rotate: [0, -12, 8, 0] }}
        transition={reduceMotion ? undefined : { duration: 11, repeat: Infinity, ease: 'easeInOut', delay: 0.8 }}
      />
      <motion.div
        className="absolute bottom-[-18%] left-[18%] h-[30rem] w-[36rem] rounded-full bg-[radial-gradient(circle,rgba(249,115,22,0.24)_0%,rgba(255,255,255,0.1)_36%,transparent_72%)] opacity-75 blur-[92px] dark:bg-[radial-gradient(circle,rgba(249,115,22,0.18)_0%,rgba(34,197,94,0.08)_36%,transparent_72%)]"
        animate={reduceMotion ? undefined : { x: [0, 64, -40, 0], y: [0, -54, 30, 0], scale: [1, 1.14, 0.94, 1] }}
        transition={reduceMotion ? undefined : { duration: 12, repeat: Infinity, ease: 'easeInOut', delay: 1.2 }}
      />
      <motion.div
        className="absolute inset-[-18%] opacity-[0.34] mix-blend-multiply blur-[18px] dark:opacity-[0.16] dark:mix-blend-screen"
        style={{
          backgroundImage:
            'repeating-linear-gradient(116deg, rgba(34,199,232,0) 0px, rgba(34,199,232,0) 38px, rgba(34,199,232,0.24) 38px, rgba(34,199,232,0.24) 52px, rgba(255,255,255,0) 52px, rgba(255,255,255,0) 92px, rgba(47,128,237,0.2) 92px, rgba(47,128,237,0.2) 108px, rgba(255,255,255,0) 108px, rgba(255,255,255,0) 156px)',
          backgroundSize: '220px 220px',
        }}
        animate={reduceMotion ? undefined : { x: [0, 148, -96, 0], y: [0, -44, 68, 0], opacity: [0.24, 0.38, 0.28, 0.24] }}
        transition={reduceMotion ? undefined : { duration: 7, repeat: Infinity, ease: 'linear' }}
      />
      <motion.div
        className="absolute inset-[-10%] opacity-[0.22] mix-blend-soft-light dark:opacity-[0.12]"
        style={{
          backgroundImage:
            'repeating-linear-gradient(180deg, rgba(255,255,255,0) 0px, rgba(255,255,255,0) 24px, rgba(255,255,255,0.34) 24px, rgba(255,255,255,0.34) 28px, rgba(255,255,255,0) 28px, rgba(255,255,255,0) 58px)',
          backgroundSize: '100% 120px',
        }}
        animate={reduceMotion ? undefined : { y: [0, -64, 0], opacity: [0.16, 0.28, 0.16] }}
        transition={reduceMotion ? undefined : { duration: 5.2, repeat: Infinity, ease: 'linear' }}
      />
      <motion.div
        className="absolute inset-[-12%] opacity-45 mix-blend-soft-light blur-3xl dark:opacity-20"
        style={{
          backgroundImage:
            'linear-gradient(128deg, rgba(255,255,255,0.82) 0%, rgba(34,199,232,0.24) 26%, rgba(47,128,237,0.14) 54%, rgba(249,115,22,0.14) 100%)',
        }}
        animate={reduceMotion ? undefined : { rotate: [0, 7, -5, 0], scale: [1, 1.08, 0.97, 1], x: [0, 40, -26, 0], y: [0, -24, 18, 0] }}
        transition={reduceMotion ? undefined : { duration: 9, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute inset-0 opacity-[0.18] mix-blend-soft-light dark:opacity-[0.08]"
        style={{
          backgroundImage:
            'radial-gradient(rgba(255,255,255,0.9) 0.7px, transparent 0.7px), radial-gradient(rgba(14,165,233,0.3) 0.5px, transparent 0.5px)',
          backgroundPosition: '0 0, 12px 14px',
          backgroundSize: '18px 18px, 22px 22px',
        }}
        animate={reduceMotion ? undefined : { x: [0, 24, -18, 0], y: [0, -14, 10, 0], opacity: [0.14, 0.24, 0.16, 0.14] }}
        transition={reduceMotion ? undefined : { duration: 6, repeat: Infinity, ease: 'linear' }}
      />
      <motion.div
        className="absolute inset-[-18%] bg-[conic-gradient(from_180deg_at_50%_50%,rgba(34,199,232,0.04)_0deg,rgba(47,128,237,0.18)_96deg,rgba(255,255,255,0.02)_180deg,rgba(249,115,22,0.16)_260deg,rgba(34,199,232,0.04)_360deg)] opacity-60 blur-[86px] dark:opacity-30"
        animate={reduceMotion ? undefined : { rotate: [0, 18, -12, 0], scale: [1, 1.05, 0.98, 1] }}
        transition={reduceMotion ? undefined : { duration: 8, repeat: Infinity, ease: 'easeInOut' }}
      />
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(248,251,255,0.08)_0%,rgba(238,246,255,0.14)_46%,rgba(238,246,255,0.72)_100%)] dark:bg-[linear-gradient(180deg,rgba(2,6,23,0.06)_0%,rgba(10,20,35,0.22)_46%,rgba(8,15,27,0.72)_100%)]" />
    </div>
  );
}

// --- Components ---

const WorkspaceLoading = ({ label = '正在处理中...' }: { label?: string }) => (
  <div className="flex flex-col items-center justify-center py-12 text-center">
    <div className="mb-4 h-8 w-8 animate-spin rounded-full border-2 border-sky-200 border-t-sky-500" />
    <p className="font-medium text-slate-700 dark:text-slate-200">{label}</p>
  </div>
);

const consultationStageDisplayLabel = (stage: string) => {
  if (stage === '已加小客服微信') return '客服微信✅';
  if (stage === '已加对应教师微信') return '教师微信✅';
  if (stage === '正在沟通细节') return '沟通ing';
  if (stage === '待测试') return '测试';
  if (stage === '待试听') return '试听';
  return stage;
};

const consultationStageShortLabel = (stage: string) => {
  if (stage === '已加小客服微信') return '客';
  if (stage === '已加对应教师微信') return '教';
  if (stage === '正在沟通细节') return '沟';
  if (stage === '待测试') return '测';
  if (stage === '待试听') return '听';
  return stage;
};

const consultationResultShortLabel = (stage: string) => {
  if (stage === '成功进班') return '进';
  if (stage === '试听失败') return '败';
  return '';
};

const ConsultationStatusLamp = ({ stage }: { stage: string }) => {
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

const ConsultationFlowBar = ({
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

const compactFlowSectionClass = `${consultationPanelClass} px-3.5 py-3`;
const consultationJumpHighlightClass = 'ring-2 ring-sky-300 bg-sky-50/80 shadow-[0_0_0_4px_rgba(14,165,233,0.12)] dark:bg-sky-400/10 dark:ring-sky-400/50';
const compactFieldGridClass = 'grid gap-x-3 gap-y-2 text-sm sm:grid-cols-2';
function consultationFlowSectionClass(state: ConsultationFlowSectionState): string {
  return cn(
    compactFlowSectionClass,
    'transition-colors duration-200',
    state.current
      ? 'border-[#A7DDF8] border-l-4 border-l-[#0EA5E9] bg-[#F0FAFF] ring-1 ring-sky-100 dark:border-sky-400/40 dark:bg-sky-400/10 dark:ring-sky-400/10'
      : state.active
        ? 'border-[#D9EEF7] bg-white dark:border-white/10 dark:bg-slate-950/72'
        : 'border-[#E5ECF3] bg-[#F7FAFC] shadow-none [&_.consultation-field-input]:border-[#D7E4EE] [&_.consultation-field-input]:bg-white/85 [&_.consultation-field-input]:text-[#4F6178] [&_.consultation-field-input]:placeholder:text-[#9AABBF] [&_.consultation-field-label]:text-[#8EA0B8] [&_.consultation-field-value]:text-[#4F6178] dark:border-white/8 dark:bg-slate-900/45',
  );
}
const compactFlowTitleClass = (state: boolean | ConsultationFlowSectionState = false) => {
  const active = typeof state === 'boolean' ? state : state.active;
  const current = typeof state === 'boolean' ? false : state.current;
  return cn(
    'mb-3 border-b border-[#EAF6FC] pb-2 text-[13px] transition-colors dark:border-white/10',
    current
      ? 'font-bold text-[#0EA5E9] dark:text-sky-300'
      : active
        ? 'font-semibold text-[#1F2A44] dark:text-slate-100'
        : 'font-medium text-[#8EA0B8] dark:text-slate-400',
  );
};
const compactReadLabelClass = consultationLabelClass;
const compactEditLabelClass = consultationLabelClass;
const compactReadValueClass = consultationValueClass;

const ConsultationCardExpandableText = ({
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
                onStageClick={(stage) => setForm((current) => toggleConsultationStage(current, stage))}
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

const ConsultationBatchModal = ({
  open,
  onClose,
  onImported,
}: {
  open: boolean;
  onClose: () => void;
  onImported: () => Promise<void>;
}) => {
  const [rawText, setRawText] = useState('');
  const [drafts, setDrafts] = useState<ConsultationBatchDraftItem[]>([]);
  const [importedDrafts, setImportedDrafts] = useState<ConsultationBatchDraftItem[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [parsing, setParsing] = useState(false);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }
    setRawText('');
    setDrafts([]);
    setImportedDrafts([]);
    setWarnings([]);
    setError('');
    setParsing(false);
    setImporting(false);
  }, [open]);

  if (!open) {
    return null;
  }

  const busy = parsing || importing;

  const handleRemoveDraft = (draftIndex: number) => {
    setDrafts((current) => current.filter((_draft, index) => index !== draftIndex));
    setError('');
  };

  const handleParse = async () => {
    if (!rawText.trim()) {
      setError('先粘贴一段原始咨询文本，再进行 AI 解析。');
      return;
    }

    setParsing(true);
    setError('');
    try {
      const response = await apiFetch<ConsultationBatchParseResponse>('/api/consultations/ai-parse', {
        method: 'POST',
        body: JSON.stringify({ raw_text: rawText.trim() }),
      });
      setImportedDrafts([]);
      setDrafts(response.items || []);
      setWarnings(response.warnings || []);
      if (!response.items || response.items.length === 0) {
        setError('AI 没有解析出可导入的草稿，请补充更明确的家长、科目或记录 ID。');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI 批量解析失败');
    } finally {
      setParsing(false);
    }
  };

  const handleImport = async () => {
    if (drafts.length === 0) {
      setError('请先完成解析并确认预览草稿。');
      return;
    }

    setImporting(true);
    setError('');
    let importSucceeded = false;
    const remainingDrafts = [...drafts];
    try {
      for (const [index, draft] of drafts.entries()) {
        const draftLabel = draft.fields.child_name?.trim() || (draft.action === 'update' && draft.target_id ? `ID ${draft.target_id}` : `第 ${index + 1} 条草稿`);
        try {
          if (draft.action === 'update' && draft.target_id) {
            await apiFetch(`/api/consultations/${draft.target_id}`, {
              method: 'PUT',
              body: JSON.stringify(draft.fields),
            });
          } else {
            await apiFetch('/api/consultations', {
              method: 'POST',
              body: JSON.stringify(buildConsultationBatchCreatePayload(draft.fields)),
            });
          }
        } catch (err) {
          const message = err instanceof Error ? err.message : '批量导入失败';
          setError(`${draftLabel}导入失败：${message}`);
          setDrafts([...remainingDrafts]);
          return;
        }

        remainingDrafts.shift();
        setImportedDrafts((current) => [...current, draft]);
        setDrafts([...remainingDrafts]);
      }
      importSucceeded = true;

      let refreshSucceeded = false;
      try {
        await onImported();
        refreshSucceeded = true;
      } catch (err) {
        if (importSucceeded) {
          setError('导入已完成，但刷新咨询记录失败，请手动刷新列表确认结果。');
        }
      }

      if (refreshSucceeded) {
        onClose();
      }
    } finally {
      setImporting(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto px-3 py-3 sm:items-center sm:px-4 sm:py-6"
      onClick={(e) => e.target === e.currentTarget && !busy && onClose()}
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
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Consultation Batch</p>
            <h3 className="mt-2 text-xl font-bold tracking-tight text-slate-900 sm:text-2xl dark:text-white">AI 批量整理</h3>
            <p className="mt-1 max-w-2xl text-sm text-slate-500 dark:text-slate-400">
              粘贴原始文本后生成解析预览；确认后按现有咨询记录接口逐条写入。
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              if (busy) {
                return;
              }
              onClose();
            }}
            disabled={busy}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-50 text-slate-500 transition-colors hover:bg-sky-100 hover:text-slate-800 dark:bg-white/5 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-white"
            aria-label="关闭 AI 批量整理窗口"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <section className={`${workspaceSoftCardClass} space-y-4 p-4 sm:p-5`}>
            <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h4 className="font-semibold text-slate-900 dark:text-white">原始文本</h4>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  支持直接粘贴微信合并转发内容、多条自然语言描述，或混合新增与修改指令。
                </p>
              </div>
              <button
                type="button"
                onClick={handleParse}
                disabled={busy}
                className={workspacePrimaryButtonClass}
              >
                <Cpu size={18} />
                {parsing ? '解析中...' : '开始解析'}
              </button>
            </div>
            <textarea
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              rows={8}
              className={`${workspaceFieldClass} min-h-[220px] resize-y`}
              placeholder="例如：新增：张妈妈，五年级数学，转介绍，想补基础。修改 ID 182：改成跟进中，备注已约周四试听。"
            />
            <div className="rounded-2xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-700 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-200">
              只有文本里写了明确记录 ID（如 ID 182、记录182、#182）时，才会覆盖旧记录。未写明确 ID 的内容一律按新增处理。
            </div>
          </section>

          <section className={`${workspaceSoftCardClass} mt-5 space-y-4 p-4 sm:p-5`}>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h4 className="font-semibold text-slate-900 dark:text-white">预览草稿</h4>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  解析结果不会直接落库。先检查 action、目标记录和字段，再确认导入。
                </p>
              </div>
              <div className="text-sm text-slate-500 dark:text-slate-400">共 {drafts.length} 条</div>
            </div>

            {importedDrafts.length > 0 && (
              <div className="space-y-3 rounded-2xl border border-emerald-200 bg-emerald-50/80 p-4 dark:border-emerald-400/20 dark:bg-emerald-500/10">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-semibold text-slate-900 dark:text-white">已保存草稿</p>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                      这些草稿已经成功写入，不会再进入下一次重试队列。
                    </p>
                  </div>
                  <div className="text-sm text-slate-500 dark:text-slate-400">共 {importedDrafts.length} 条</div>
                </div>
                <div className="space-y-2">
                  {importedDrafts.map((draft, index) => {
                    const importedDateLabel = draft.fields.date?.trim() || '未填写咨询日期';
                    const importedChildLabel = draft.fields.child_name?.trim() || '未填写学生姓名';
                    const importedTeacherLabel = draft.fields.receiving_teacher?.trim() || draft.fields.teacher_id?.trim() || '待确认老师';
                    return (
                      <article
                        key={`imported-${draft.action}-${draft.target_id ?? 'create'}-${index}`}
                        className="rounded-2xl border border-emerald-200 bg-white/90 p-4 dark:border-emerald-400/20 dark:bg-slate-950/70"
                      >
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="inline-flex items-center justify-center rounded-full bg-emerald-100 px-3 py-1 text-[11px] font-semibold tracking-[0.08em] text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                                已导入草稿
                              </span>
                              <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                                {draft.action === 'update' && draft.target_id ? `目标记录 ID ${draft.target_id}` : '新建咨询记录'}
                              </span>
                            </div>
                            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{draft.reason || '已成功写入咨询记录'}</p>
                          </div>
                          <div className="text-sm text-slate-500 dark:text-slate-400">第 {index + 1} 条</div>
                        </div>
                        <div className="mt-4 grid gap-3 sm:grid-cols-3">
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">咨询日期</p>
                            <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">{importedDateLabel}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">学生</p>
                            <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">{importedChildLabel}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">老师</p>
                            <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">{importedTeacherLabel}</p>
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </div>
            )}

            {warnings.length > 0 && (
              <div className="space-y-2 rounded-2xl border border-sky-100 bg-white/80 p-4 text-sm text-slate-600 dark:border-white/10 dark:bg-slate-950/70 dark:text-slate-300">
                <p className="font-semibold text-slate-900 dark:text-white">解析提醒</p>
                {warnings.map((warning, index) => (
                  <p key={`${warning}-${index}`}>{warning}</p>
                ))}
              </div>
            )}

            {drafts.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-sky-200 bg-white/60 px-4 py-6 text-sm text-slate-500 dark:border-white/10 dark:bg-slate-950/50 dark:text-slate-400">
                暂无草稿。粘贴原始文本后点击“开始解析”。
              </div>
            ) : (
              <div className="space-y-3">
                {drafts.map((draft, index) => {
                  const dateLabel = draft.fields.date?.trim() || '未填写咨询日期';
                  const childLabel = draft.fields.child_name?.trim() || '未填写学生姓名';
                  const subjectLabel = draft.fields.consultation_subject?.trim() || '未填写咨询科目';
                  const parentLabel = draft.fields.parent_wechat_name?.trim() || '未填写家长微信';
                  const statusLabel = draft.fields.follow_up_status?.trim() || '待确认跟进状态';
                  const teacherLabel = draft.fields.receiving_teacher?.trim() || draft.fields.teacher_id?.trim() || '待确认老师';
                  const sourceLabel = draft.fields.source_channel?.trim() || '未标注来源渠道';
                  const sourceNoteLabel = draft.fields.source_channel_note?.trim();
                  const followUpNoteLabel = draft.fields.follow_up_note?.trim();
                  return (
                    <article key={`${draft.action}-${draft.target_id ?? 'create'}-${index}`} className="rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-slate-950/70">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={cn(
                              'inline-flex items-center justify-center rounded-full px-3 py-1 text-[11px] font-semibold tracking-[0.08em]',
                              draft.action === 'update'
                                ? 'bg-sky-50 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300'
                                : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
                            )}>
                              {draft.action === 'update' ? '更新' : '新增'}
                            </span>
                            <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                              {draft.action === 'update' && draft.target_id ? `目标记录 ID ${draft.target_id}` : '新建咨询记录'}
                            </span>
                          </div>
                          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{draft.reason || '等待人工确认'}</p>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="text-sm text-slate-500 dark:text-slate-400">第 {index + 1} 条</div>
                          <button
                            type="button"
                            onClick={() => handleRemoveDraft(index)}
                            disabled={busy}
                            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-sky-100 bg-white text-slate-500 transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:border-rose-400/30 dark:hover:bg-rose-500/10 dark:hover:text-rose-200"
                            aria-label="移除这条草稿"
                            title="移除这条草稿"
                          >
                            <X size={16} />
                          </button>
                        </div>
                      </div>

                      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        <div>
                          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">咨询日期 / 学生</p>
                          <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">{dateLabel}</p>
                          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{childLabel}</p>
                        </div>
                        <div>
                          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">家长微信 / 科目</p>
                          <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">{parentLabel}</p>
                          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{subjectLabel}</p>
                        </div>
                        <div>
                          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">老师 / 跟进状态</p>
                          <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">{teacherLabel}</p>
                          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{statusLabel}</p>
                        </div>
                        <div>
                          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">来源 / 年级</p>
                          <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">{sourceLabel}</p>
                          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{draft.fields.grade?.trim() || '未填写年级'}</p>
                        </div>
                      </div>

                      {(sourceNoteLabel || followUpNoteLabel) && (
                        <div className="mt-4 rounded-2xl border border-sky-100 bg-sky-50/50 p-3 text-sm text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">来源备注 / 跟进备注</p>
                          {sourceNoteLabel && <p className="mt-2">来源备注：{sourceNoteLabel}</p>}
                          {followUpNoteLabel && <p className={sourceNoteLabel ? 'mt-1' : 'mt-2'}>跟进备注：{followUpNoteLabel}</p>}
                        </div>
                      )}

                      {draft.fields.need_detail?.trim() && (
                        <div className="mt-4 rounded-2xl border border-sky-100 bg-sky-50/50 p-3 text-sm text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                          {draft.fields.need_detail}
                        </div>
                      )}

                      {draft.warnings.length > 0 && (
                        <div className="mt-4 space-y-1 text-sm text-amber-700 dark:text-amber-200">
                          {draft.warnings.map((warning, warningIndex) => (
                            <p key={`${warning}-${warningIndex}`}>{warning}</p>
                          ))}
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        <div className="flex flex-col gap-3 border-t border-sky-100/80 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 sm:py-5 dark:border-white/10">
          <div className="text-sm text-slate-500 dark:text-slate-400">确认导入时会逐条调用现有新增与编辑接口，不会跳到新页面。</div>
          <div className="grid gap-3 sm:flex sm:flex-wrap sm:justify-end">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className={`${workspaceSecondaryButtonClass} w-full sm:w-auto`}
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleImport}
              disabled={drafts.length === 0 || busy}
              className={`${workspacePrimaryButtonClass} w-full sm:w-auto`}
            >
              {importing ? '导入中...' : '确认导入'}
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};

export {
  ConsultationBatchModal,
  ConsultationCardExpandableText,
  ConsultationFlowBar,
  ConsultationModal,
  ConsultationStatusLamp,
  buildConsultationTeacherDirectory,
  clearConsultationResultStage,
  consultationFilterGroups,
  consultationFilterLabels,
  consultationFlowStages,
  consultationMeetingVersion,
  consultationProcessStages,
  consultationResultShortLabel,
  consultationStageDisplayLabel,
  consultationStageShortLabel,
  endConsultationValues,
  getConsultationFilterKey,
  getConsultationOver30SectionLabel,
  getConsultationSourceLabel,
  getConsultationTeacherName,
  getTodayIsoDate,
  isConsultationEnded,
  isConsultationResultStage,
  moveConsultationStage,
  normalizeConsultationRecord,
  normalizeConsultationTeacherOption,
  restoreConsultationValues,
  setConsultationResultStage,
  sortConsultationsForFilter,
  toConsultationFormValues,
  toggleConsultationStageLight,
};

export default function App() {
  const studentPortalMode = typeof window !== 'undefined' && window.location.pathname.startsWith('/student');
  if (studentPortalMode) {
    return <StudentPortalPage today={getTodayIsoDate()} />;
  }

  const [token, setToken] = useState<string>(() => getToken());
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [authReady, setAuthReady] = useState<boolean>(() => !Boolean(getToken()));
  const [isDark, setIsDark] = useState<boolean>(getInitialDarkModePreference);
  const [isMobileViewport, setIsMobileViewport] = useState(getInitialMobileViewport);
  const [publicAuthModal, setPublicAuthModal] = useState<PublicAuthModal | null>(() => {
    if (typeof window === 'undefined') {
      return null;
    }
    if (getToken()) {
      return null;
    }
    return getJoinInviteTokenFromPath(window.location.pathname) ? 'join-organization' : null;
  });
  const [joinInviteToken, setJoinInviteToken] = useState<string | null>(() => {
    if (typeof window === 'undefined') {
      return null;
    }
    return getJoinInviteTokenFromPath(window.location.pathname);
  });
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [activePage, setActivePage] = useState<Page>('dashboard');
  const [classBindingTarget, setClassBindingTarget] = useState<ClassBindingTarget | null>(null);
  const [showLanding, setShowLanding] = useState(false);
  const [landingHash, setLandingHash] = useState<string>(() =>
    typeof window === 'undefined' ? '' : window.location.hash,
  );
  const [calendarClasses, setCalendarClasses] = useState<ClassItem[]>([]);
  const [calendarSchedules, setCalendarSchedules] = useState<CourseCalendarScheduleRecord[]>([]);
  const [calendarCustomItems, setCalendarCustomItems] = useState<CourseCalendarCustomItemRecord[]>([]);
  const [calendarCustomSchedules, setCalendarCustomSchedules] = useState<CourseCalendarCustomScheduleRecord[]>([]);
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [calendarError, setCalendarError] = useState('');
  const [calendarAnchorDate, setCalendarAnchorDate] = useState<string>(() => getCurrentWeekTuesday(getTodayIsoDate()));
  const [calendarPageStepDays, setCalendarPageStepDays] = useState(6);

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    document.documentElement.classList.toggle('dark', isDark);
    try {
      writeLocalStorageItem('xr_dark', String(isDark));
    } catch {
      // Ignore storage access issues and keep the UI functional.
    }
  }, [isDark]);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return undefined;
    }

    const mediaQuery = window.matchMedia('(max-width: 1023px)');
    const syncViewport = () => {
      setIsMobileViewport(mediaQuery.matches);
    };

    syncViewport();

    if (typeof mediaQuery.addEventListener === 'function') {
      mediaQuery.addEventListener('change', syncViewport);
      return () => mediaQuery.removeEventListener('change', syncViewport);
    }

    mediaQuery.addListener(syncViewport);
    return () => mediaQuery.removeListener(syncViewport);
  }, []);

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
    if (typeof window === 'undefined') {
      return undefined;
    }

    const syncInvitePath = () => {
      if (token) {
        clearJoinInvitePathIfNeeded();
        setJoinInviteToken(null);
        setPublicAuthModal(null);
        return;
      }

      const nextToken = getJoinInviteTokenFromPath(window.location.pathname);
      setJoinInviteToken(nextToken);
      if (nextToken && !token) {
        setPublicAuthModal('join-organization');
        return;
      }
      setPublicAuthModal((current) => (current === 'join-organization' ? null : current));
    };

    syncInvitePath();
    window.addEventListener('popstate', syncInvitePath);
    return () => window.removeEventListener('popstate', syncInvitePath);
  }, [token]);

  useEffect(() => {
    if (!token) {
      setCurrentUser(null);
      setAuthReady(true);
      return;
    }

    let cancelled = false;
    setAuthReady(false);

    apiFetch<CurrentUser>('/api/me', { reloadOnUnauthorized: false })
      .then((user) => {
        if (cancelled) {
          return;
        }
        setCurrentUser(user);
        setActivePage((page) => getWorkspacePageFallback(user, page));
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        removeLocalStorageItem('xr_token');
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
      setCalendarSchedules([]);
      setCalendarCustomItems([]);
      setCalendarCustomSchedules([]);
      setCalendarLoading(false);
      setCalendarError('');
      setCalendarAnchorDate(getCurrentWeekTuesday(getTodayIsoDate()));
      return;
    }

    if (!authReady) {
      return;
    }

    let cancelled = false;
    setCalendarLoading(true);
    setCalendarError('');

    Promise.all([
      apiFetch<ClassItem[]>('/api/classes'),
      apiFetch<{ items: CourseCalendarScheduleRecord[] }>('/api/course-calendar/schedules'),
      apiFetch<{ items: CourseCalendarCustomItemRecord[] }>('/api/course-calendar/custom-items'),
      apiFetch<{ items: CourseCalendarCustomScheduleRecord[] }>('/api/course-calendar/custom-schedules'),
    ])
      .then(([classes, schedulePayload, customItemPayload, customSchedulePayload]) => {
        if (cancelled) {
          return;
        }
        setCalendarClasses(classes);
        setCalendarSchedules(schedulePayload.items);
        setCalendarCustomItems(customItemPayload.items);
        setCalendarCustomSchedules(customSchedulePayload.items);
        setCalendarAnchorDate(getCurrentWeekTuesday(getTodayIsoDate()));
      })
      .catch((error) => {
        console.error(error);
        if (!cancelled) {
          setCalendarError(error instanceof Error ? error.message : '课程日历加载失败，请刷新重试。');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCalendarLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [authReady, currentUser, token]);

  useEffect(() => {
    if (!currentUser) {
      setActivePage('dashboard');
      return;
    }
    setActivePage((page) => getWorkspacePageFallback(currentUser, page));
  }, [currentUser]);

  const handleLogin = (t: string) => {
    clearJoinInvitePathIfNeeded();
    writeLocalStorageItem('xr_token', t);
    setToken(t);
    setPublicAuthModal(null);
    setJoinInviteToken(null);
    setShowLanding(false);
  };

  const handleLogout = () => {
    clearJoinInvitePathIfNeeded();
    removeLocalStorageItem('xr_token');
    setToken('');
    setCurrentUser(null);
    setPublicAuthModal(null);
    setJoinInviteToken(null);
    setShowLanding(false);
    setActivePage('dashboard');
    setMobileNavOpen(false);
  };

  const closePublicAuthModal = () => {
    clearJoinInvitePathIfNeeded();
    setJoinInviteToken(null);
    setPublicAuthModal(null);
  };

  const openApplyOrganization = () => {
    setJoinInviteToken(null);
    setPublicAuthModal('apply-organization');
  };

  const openJoinOrganization = () => {
    const nextToken = typeof window === 'undefined' ? null : getJoinInviteTokenFromPath(window.location.pathname);
    setJoinInviteToken(nextToken);
    setPublicAuthModal('join-organization');
  };

  const openPasswordReset = () => {
    setPublicAuthModal('password-reset');
  };

  const backToLogin = () => {
    setPublicAuthModal('login');
  };

  const navigateWorkspacePage = useCallback((page: Page) => {
    if (!currentUser) {
      setActivePage('dashboard');
      return;
    }
    setActivePage(getWorkspacePageFallback(currentUser, page));
  }, [currentUser]);

  const handleReviewGenerationSuccess = () => {
    navigateWorkspacePage('review-generation');
  };

  const handleOpenClassBinding = (target: ClassBindingTarget) => {
    setClassBindingTarget(target);
    navigateWorkspacePage('classes');
    setMobileNavOpen(false);
  };

  const handlePreviousCalendarPage = (dayCount: number) => {
    setCalendarAnchorDate((current) => shiftIsoDate(current, -dayCount));
  };

  const handleNextCalendarPage = (dayCount: number) => {
    setCalendarAnchorDate((current) => shiftIsoDate(current, dayCount));
  };

  const handleCalendarPageStepDaysChange = (dayCount: number) => {
    setCalendarPageStepDays(Math.max(1, Math.min(14, Math.trunc(dayCount) || 6)));
  };

  const handleScheduleCalendarClass = (classId: number, date: string, timeBlock: CourseCalendarTimeBlock, startOffsetMinutes = 0) => {
    apiFetch<{ item: CourseCalendarScheduleRecord }>('/api/course-calendar/schedules', {
      method: 'POST',
      body: JSON.stringify({
        class_id: classId,
        date,
        time_block: timeBlock,
        start_offset_minutes: startOffsetMinutes,
      }),
    })
      .then(({ item }) => {
        setCalendarSchedules((current) => [
          ...current.filter(
            (schedule) =>
              schedule.id !== item.id
              && !(schedule.class_id === item.class_id && schedule.date === item.date && schedule.time_block === item.time_block),
          ),
          item,
        ]);
      })
      .catch((error) => {
        console.error(error);
        if (typeof window !== 'undefined') {
          window.alert(error instanceof Error ? error.message : '新增课程排期失败');
        }
      });
  };

  const handleDeleteCalendarSchedule = (scheduleId: number) => {
    apiFetch<{ ok: boolean; removed: boolean }>(`/api/course-calendar/schedules/${scheduleId}`, {
      method: 'DELETE',
    })
      .then(() => {
        setCalendarSchedules((current) => current.filter((schedule) => schedule.id !== scheduleId));
      })
      .catch((error) => {
        console.error(error);
        if (typeof window !== 'undefined') {
          window.alert(error instanceof Error ? error.message : '删除课程排期失败');
        }
      });
  };

  const handleCreateCalendarCustomItem = (item: { title: string; time_range: string; note: string; visibility: 'private' | 'organization' }) => {
    return apiFetch<{ item: CourseCalendarCustomItemRecord }>('/api/course-calendar/custom-items', {
      method: 'POST',
      body: JSON.stringify(item),
    })
      .then(({ item: createdItem }) => {
        setCalendarCustomItems((current) => [createdItem, ...current.filter((existing) => existing.id !== createdItem.id)]);
        return createdItem;
      })
      .catch((error) => {
        console.error(error);
        throw error;
      });
  };

  const handleDeleteCalendarCustomItem = (itemId: number) => {
    apiFetch<{ ok: boolean; removed: boolean }>(`/api/course-calendar/custom-items/${itemId}`, {
      method: 'DELETE',
    })
      .then(() => {
        setCalendarCustomItems((current) => current.filter((item) => item.id !== itemId));
        setCalendarCustomSchedules((current) => current.filter((schedule) => schedule.custom_item_id !== itemId));
      })
      .catch((error) => {
        console.error(error);
        if (typeof window !== 'undefined') {
          window.alert(error instanceof Error ? error.message : '删除自定义事项失败');
        }
      });
  };

  const handleScheduleCalendarCustomItem = (customItemId: number, date: string, timeBlock: CourseCalendarTimeBlock, startOffsetMinutes = 0) => {
    apiFetch<{ item: CourseCalendarCustomScheduleRecord }>('/api/course-calendar/custom-schedules', {
      method: 'POST',
      body: JSON.stringify({
        custom_item_id: customItemId,
        date,
        time_block: timeBlock,
        start_offset_minutes: startOffsetMinutes,
      }),
    })
      .then(({ item }) => {
        setCalendarCustomSchedules((current) => [
          ...current.filter(
            (schedule) =>
              schedule.id !== item.id
              && !(schedule.custom_item_id === item.custom_item_id && schedule.date === item.date && schedule.time_block === item.time_block),
          ),
          item,
        ]);
      })
      .catch((error) => {
        console.error(error);
        if (typeof window !== 'undefined') {
          window.alert(error instanceof Error ? error.message : '新增自定义事项排期失败');
        }
      });
  };

  const handleDeleteCalendarCustomSchedule = (scheduleId: number) => {
    apiFetch<{ ok: boolean; removed: boolean }>(`/api/course-calendar/custom-schedules/${scheduleId}`, {
      method: 'DELETE',
    })
      .then(() => {
        setCalendarCustomSchedules((current) => current.filter((schedule) => schedule.id !== scheduleId));
      })
      .catch((error) => {
        console.error(error);
        if (typeof window !== 'undefined') {
          window.alert(error instanceof Error ? error.message : '删除自定义事项排期失败');
        }
      });
  };

  const pageTitle: Record<Page, string> = {
    dashboard: '工作台',
    'review-generation': '复习生成',
    'class-feedback-generation': '课堂反馈',
    consultation: '咨询记录',
    calendar: '课程日历',
    smartWrongQuestions: '智能错题',
    classes: '学管中心',
    accounts: '账号审批',
    credit: '积分中心',
    settings: '系统设置',
  };

  if (token && !authReady) {
    return (
      <div className="flex min-h-[100svh] items-center justify-center bg-[linear-gradient(180deg,#f8fbff_0%,#eef6ff_100%)] sm:min-h-screen dark:bg-[linear-gradient(180deg,#020617_0%,#0f172a_100%)]">
        <p className="text-sm text-slate-400 dark:text-slate-500">正在验证账号权限...</p>
      </div>
    );
  }

  if (!token || !currentUser || showLanding || landingLegalPage) {
    return (
      <>
        <LandingPage
          onLogin={token ? () => setShowLanding(false) : () => setPublicAuthModal('login')}
          onApplyOrganization={() => {
            if (token) {
              setShowLanding(false);
              return;
            }
            openApplyOrganization();
          }}
          onJoinOrganization={() => {
            if (token) {
              setShowLanding(false);
              return;
            }
            openJoinOrganization();
          }}
          activeLegalPage={landingLegalPage}
          isDark={isDark}
          onToggleDarkMode={() => setIsDark((current) => !current)}
        />
        <AnimatePresence>
          {publicAuthModal === 'login' && (
            <LoginModal
              onLogin={handleLogin}
              onClose={closePublicAuthModal}
              onOpenApplyOrganization={openApplyOrganization}
              onOpenJoinOrganization={openJoinOrganization}
              onOpenPasswordReset={openPasswordReset}
            />
          )}
          {publicAuthModal === 'password-reset' && (
            <PasswordResetModal onClose={closePublicAuthModal} onBackToLogin={backToLogin} />
          )}
          {publicAuthModal === 'apply-organization' && (
            <OrganizationApplyModal onClose={closePublicAuthModal} />
          )}
          {publicAuthModal === 'join-organization' && (
            <JoinOrganizationModal onClose={closePublicAuthModal} inviteToken={joinInviteToken} />
          )}
        </AnimatePresence>
      </>
    );
  }

  if (currentUser.requires_class_claim) {
    return (
      <ClassClaimPage
        currentUser={currentUser}
        onClaimed={(user) => {
          setCurrentUser(user);
          setActivePage('dashboard');
        }}
        onLogout={handleLogout}
      />
    );
  }

  const consultationMeetingMode = typeof window !== 'undefined'
    && new URLSearchParams(window.location.search).get('consultationMeeting') === '1';

  if (consultationMeetingMode) {
    return (
      <div className="relative min-h-[100svh] overflow-x-hidden bg-[linear-gradient(180deg,#f8fbff_0%,#eef6ff_100%)] text-slate-900 sm:min-h-screen dark:bg-[linear-gradient(180deg,#020617_0%,#0f172a_100%)] dark:text-slate-100">
        <ConsultationMeetingWorkbench currentUser={currentUser} />
      </div>
    );
  }

  const activeWorkspacePage = getWorkspacePageFallback(currentUser, activePage);

  return (
    <WorkspaceShellLayout
      activeWorkspacePage={activeWorkspacePage}
      currentUser={currentUser}
      title={pageTitle[activeWorkspacePage]}
      isDark={isDark}
      mobileNavOpen={mobileNavOpen}
      onGoHome={() => setShowLanding(true)}
      onToggleDarkMode={() => setIsDark((current) => !current)}
      onOpenSidebar={() => setMobileNavOpen(true)}
      onCloseSidebar={() => setMobileNavOpen(false)}
      onLogout={handleLogout}
      onNavigatePage={navigateWorkspacePage}
      onProfileUpdated={(u, d) => setCurrentUser((c) => c ? { ...c, username: u, display_name: d } : c)}
      showSmartWrongQuestions={canAccessSmartWrongQuestions(currentUser.role)}
      showCreditCenter={hasOwnerAccess(currentUser.role)}
      showAccounts={hasStaffAccess(currentUser.role)}
      canOpenPage={(page) => canOpenWorkspacePage(currentUser, page)}
      roleLabel={getRoleLabel(currentUser.role)}
    >
      <WorkspacePageContent
        activeWorkspacePage={activeWorkspacePage}
        currentUser={currentUser}
        isMobileViewport={isMobileViewport}
        canOpenWorkspacePage={canOpenWorkspacePage}
        hasOwnerAccess={hasOwnerAccess}
        hasStaffAccess={hasStaffAccess}
        navigateWorkspacePage={navigateWorkspacePage}
        handleReviewGenerationSuccess={handleReviewGenerationSuccess}
        ConsultationPageComponent={ConsultationPage}
        calendarLoading={calendarLoading}
        calendarError={calendarError}
        calendarAnchorDate={calendarAnchorDate}
        getTodayIsoDate={getTodayIsoDate}
        calendarClasses={calendarClasses}
        calendarSchedules={calendarSchedules}
        calendarCustomItems={calendarCustomItems}
        calendarCustomSchedules={calendarCustomSchedules}
        calendarPageStepDays={calendarPageStepDays}
        handleCalendarPageStepDaysChange={handleCalendarPageStepDaysChange}
        handlePreviousCalendarPage={handlePreviousCalendarPage}
        handleNextCalendarPage={handleNextCalendarPage}
        handleScheduleCalendarClass={handleScheduleCalendarClass}
        handleScheduleCalendarCustomItem={handleScheduleCalendarCustomItem}
        handleCreateCalendarCustomItem={handleCreateCalendarCustomItem}
        handleDeleteCalendarCustomItem={handleDeleteCalendarCustomItem}
        handleDeleteCalendarSchedule={handleDeleteCalendarSchedule}
        handleDeleteCalendarCustomSchedule={handleDeleteCalendarCustomSchedule}
        WorkspaceLoadingComponent={WorkspaceLoading}
        classBindingTarget={classBindingTarget}
        handleClearClassBindingTarget={() => setClassBindingTarget(null)}
        handleOpenClassBinding={handleOpenClassBinding}
        handleLogout={handleLogout}
      />
    </WorkspaceShellLayout>
  );
}
