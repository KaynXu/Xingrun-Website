/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
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
  ArrowUp,
  RefreshCw,
  AlertCircle,
  ShieldCheck,
  Moon,
  Sun,
  X,
  ChevronDown,
} from 'lucide-react';
import { motion, AnimatePresence, useReducedMotion } from 'motion/react';
import { CourseCalendarPage } from './CourseCalendarPage';
import type { CourseCalendarCustomItemRecord, CourseCalendarCustomScheduleRecord, CourseCalendarScheduleRecord, CourseCalendarTimeBlock } from './courseCalendarData';
import { getCurrentWeekTuesday } from './courseCalendarData';
import { SmartWrongQuestionsPage } from './SmartWrongQuestionsPage';
import { ClassFeedbackGenerationWorkspace } from './ClassFeedbackGenerationWorkspace';
import { WorkspaceDashboard } from './WorkspaceDashboard';
import {
  buildClassFeedbackPeriodPreview,
  buildCreateClassFeedbackTaskRequest,
  createClassStudent,
  deleteClassStudent,
  listClassStudents,
  buildClassFeedbackConfirmPayload,
  buildClassFeedbackStudentCards,
  confirmClassFeedbackTask,
  createClassFeedbackTask,
  defaultStageLabelGroups,
  formatClassFeedbackStudentCopyText,
  generateClassFeedbackTask,
  hasCompleteClassFeedbackGeneratedContent,
  isClassFeedbackTaskGenerating,
  loadClassFeedbackLabels,
  loadClassFeedbackTask,
  normalizeClassFeedbackTaskResponse,
  saveClassFeedbackTaskDraft,
  type ClassFeedbackStageNotes,
  type ClassFeedbackStudentCard,
  type ClassFeedbackPeriodGranularity,
  type ClassFeedbackPeriodSelection,
  type ClassFeedbackStageName,
  type StageLabelGroup,
} from './classFeedbackGeneration';
import {
  getReviewLessonTaskMessage,
  getReviewLessonTaskProgress,
  getReviewLessonTaskState,
  hasReviewLessonOutput,
  isReviewLessonPending,
  normalizeReviewLessonsResponse,
} from './reviewGenerationAsync';

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

interface CreditOverview {
  organization_id: number;
  credit_balance: number;
  total_recharged: number;
  total_consumed: number;
  updated_at: string;
}

interface CreditLedgerItem {
  id: number;
  direction: 'credit' | 'debit';
  amount: number;
  balance_after: number;
  source_type: string;
  source_id: string;
  note: string;
  operator_user_id: number | null;
  created_at: string;
}

interface CreditMemberUsageItem {
  user_id: number;
  display_name: string;
  credit_consumed: number;
  usage_count: number;
  last_used_at: string | null;
}

interface CreditMemberUsageDetailItem {
  id: number;
  user_id: number;
  feature_key: string;
  provider: string | null;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  credit_cost_final: number;
  source_record_type: string | null;
  source_record_id: number | string | null;
  request_id: string;
  created_at: string;
}

interface N1nModelPricingItem {
  quota_type: number;
  group_name: string;
  group_ratio: number;
  input_usd_per_m: number;
  output_usd_per_m: number;
  flat_model_price_usd: number;
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
  created_at: string;
  updated_at: string;
}

type ConsultationFormValues = Omit<ConsultationRecord, 'id' | 'created_at' | 'updated_at'>;

interface ConsultationTeacherOption {
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

interface CurrentUser {
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

interface ClassInviteInfo {
  id: number;
  class_id: number;
  invite_code: string;
  status: string;
  created_at: string;
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

interface UserItem {
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

type ClassBindingTarget = {
  teacherUserId: number;
  teacherName: string;
};

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
  ['七年级', '七年级'],
  ['八年级', '八年级'],
  ['九年级', '九年级'],
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
  ['七年级三班', '七年级 3 班'],
];

const gradeOptions = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '七年级', '八年级', '九年级', '初一', '初二', '初三', '高一', '高二', '高三'];
const gradeFilterOptions = ['全部', ...gradeOptions, '未绑定'];
const configurableWorkspacePages: Array<{ id: Page; label: string }> = [
  { id: 'review-generation', label: '复习生成' },
  { id: 'class-feedback-generation', label: '课堂反馈' },
  { id: 'consultation', label: '咨询记录' },
  { id: 'calendar', label: '课程日历' },
  { id: 'smartWrongQuestions', label: '智能错题' },
  { id: 'classes', label: '班级管理' },
];
const configurableWorkspacePageIds = new Set(configurableWorkspacePages.map((item) => item.id));

function getRoleLabel(role: Role): string {
  if (role === 'super_owner') return '超级管理员';
  if (role === 'owner') return '机构负责人';
  if (role === 'admin') return '管理员';
  return '机构成员';
}

function hasOwnerAccess(role: Role): boolean {
  return role === 'super_owner' || role === 'owner';
}

function hasStaffAccess(role: Role): boolean {
  return hasOwnerAccess(role) || role === 'admin';
}

function canAccessSmartWrongQuestions(role: Role): boolean {
  return hasStaffAccess(role) || role === 'member';
}

function getVisibleWorkspacePages(user: Pick<CurrentUser, 'visible_pages'> | UserItem): Page[] {
  if (!Array.isArray(user.visible_pages)) {
    return configurableWorkspacePages.map((item) => item.id);
  }
  const visiblePageSet = new Set(user.visible_pages.filter((page) => configurableWorkspacePageIds.has(page)));
  return configurableWorkspacePages.map((item) => item.id).filter((page) => visiblePageSet.has(page));
}

function canOpenWorkspacePage(user: CurrentUser, page: Page): boolean {
  if (page === 'dashboard' || page === 'settings') {
    return true;
  }
  if (page === 'credit') {
    return hasOwnerAccess(user.role);
  }
  if (page === 'accounts') {
    return hasStaffAccess(user.role);
  }
  if (page === 'smartWrongQuestions' && !canAccessSmartWrongQuestions(user.role)) {
    return false;
  }
  return getVisibleWorkspacePages(user).includes(page);
}

function getWorkspacePageFallback(user: CurrentUser, page: Page): Page {
  return canOpenWorkspacePage(user, page) ? page : 'dashboard';
}

function syncMemberScopedClassSelection(
  role: Role,
  classes: ClassItem[],
  selectedClassId: number | null,
): number | null {
  if (role !== 'member') {
    return selectedClassId;
  }

  if (selectedClassId !== null && classes.some((item) => item.id === selectedClassId)) {
    return selectedClassId;
  }

  if (classes.length === 1) {
    return classes[0]?.id ?? null;
  }

  return null;
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
    .replace(/^9年级/, '九年级')
    .replace(/^8年级/, '八年级')
    .replace(/^7年级/, '七年级')
    .replace(/^5年级/, '五年级')
    .replace(/^4年级/, '四年级')
    .replace(/^3年级/, '三年级')
    .replace(/^2年级/, '二年级')
    .replace(/^1年级/, '一年级')
    .replace(/^六年(?=\d+班$)/, '六年级')
    .replace(/^九年(?=\d+班$)/, '九年级')
    .replace(/^八年(?=\d+班$)/, '八年级')
    .replace(/^七年(?=\d+班$)/, '七年级')
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
  const match = normalized.match(/^(一年级|二年级|三年级|四年级|五年级|六年级|七年级|八年级|九年级|初一|初二|初三|高一|高二|高三)(\d+)班$/);
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

function readLocalStorageItem(key: string): string {
  try {
    return globalThis.localStorage?.getItem?.(key) || '';
  } catch {
    return '';
  }
}

function writeLocalStorageItem(key: string, value: string): void {
  try {
    globalThis.localStorage?.setItem?.(key, value);
  } catch {
    // Ignore storage access issues and keep the UI functional.
  }
}

function removeLocalStorageItem(key: string): void {
  try {
    globalThis.localStorage?.removeItem?.(key);
  } catch {
    // Ignore storage access issues and keep the UI functional.
  }
}

function getToken(): string {
  return readLocalStorageItem('xr_token');
}

function buildAuthedPath(path: string): string {
  const token = getToken();
  if (!token) {
    return path;
  }
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}token=${encodeURIComponent(token)}`;
}

interface ApiFetchOptions extends RequestInit {
  reloadOnUnauthorized?: boolean;
}

export async function apiFetch<T = unknown>(path: string, options?: ApiFetchOptions): Promise<T> {
  const { reloadOnUnauthorized = true, ...fetchOptions } = options ?? {};
  const isFormData = fetchOptions.body instanceof FormData;
  const token = getToken();
  const res = await fetch(path, {
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { 'X-Auth-Token': token } : {}),
      ...(fetchOptions.headers ?? {}),
    },
    ...fetchOptions,
  });
  if (res.status === 401) {
    removeLocalStorageItem('xr_token');
    if (reloadOnUnauthorized) {
      window.location.reload();
    }
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error((err as { error?: string }).error || res.statusText);
  }
  return res.json() as Promise<T>;
}

function apiUploadFormWithProgress<T = unknown>(
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

function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
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

function getIsoWeekParts(dateString: string): { year: number; week: number } {
  const base = new Date(`${dateString}T12:00:00`);
  const thursday = new Date(base.getTime());
  const weekday = thursday.getDay() || 7;
  thursday.setDate(thursday.getDate() + 4 - weekday);

  const year = thursday.getFullYear();
  const firstThursday = new Date(`${year}-01-04T12:00:00`);
  const firstWeekday = firstThursday.getDay() || 7;
  firstThursday.setDate(firstThursday.getDate() + 4 - firstWeekday);

  const diffDays = Math.round((thursday.getTime() - firstThursday.getTime()) / 86_400_000);
  return {
    year,
    week: Math.floor(diffDays / 7) + 1,
  };
}

function inferClassFeedbackStageName(dateString: string): ClassFeedbackStageName {
  const month = Number(dateString.slice(5, 7));
  if (month >= 3 && month <= 5) {
    return '春季';
  }
  if (month >= 7 && month <= 8) {
    return '暑假';
  }
  if (month >= 9 && month <= 11) {
    return '秋季';
  }
  return '寒假';
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

const consultationStatusOptions = ['待邀约', '跟进中', '已报班', '已劝退'];
const consultationFlowStages = ['已加小客服微信', '已加对应教师微信', '正在沟通细节', '待测试', '待试听', '成功进班', '试听失败', '咨询结束'];
const consultationProcessStages = ['已加小客服微信', '已加对应教师微信', '正在沟通细节', '待测试', '待试听'];
type ConsultationResultStage = '成功进班' | '试听失败';
const consultationResultStages: ConsultationResultStage[] = ['成功进班', '试听失败'];
type ConsultationFilterKey =
  | 'pending-7'
  | 'pending-30'
  | 'pending-60'
  | 'pending-over60'
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
      { key: 'pending-60', label: '两月内' },
      { key: 'pending-over60', label: '60天+' },
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
  if (ageDays <= 60) return 'pending-60';
  return 'pending-over60';
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

export const workspacePageClass = 'px-6 py-6 md:px-8 md:py-8 xl:px-10 xl:py-10';
export const workspaceCardClass =
  'rounded-[1.75rem] border border-sky-100/90 bg-white/88 shadow-[0_22px_54px_rgba(47,128,237,0.08)] backdrop-blur-sm dark:border-white/10 dark:bg-slate-950/78 dark:shadow-[0_24px_60px_rgba(2,6,23,0.52)]';
export const workspaceSoftCardClass =
  'rounded-[1.5rem] border border-sky-100 bg-[linear-gradient(180deg,rgba(255,255,255,0.94)_0%,rgba(239,248,255,0.78)_100%)] shadow-[0_14px_36px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)] dark:shadow-[0_18px_40px_rgba(2,6,23,0.44)]';
export const workspaceFieldClass =
  'w-full rounded-xl border border-sky-200 bg-white/92 px-4 py-2.5 text-sm text-slate-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)] outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100 placeholder:text-slate-400 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100 dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] dark:focus:border-sky-500 dark:focus:ring-sky-500/15 dark:placeholder:text-slate-500';
export const workspacePrimaryButtonClass =
  'inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl bg-sky-600 px-5 py-3 font-semibold text-white shadow-[0_16px_40px_rgba(34,199,232,0.24)] transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-60';
export const workspaceSecondaryButtonClass =
  'inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-sky-200 bg-white px-5 py-3 font-semibold text-slate-700 shadow-sm transition hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:hover:bg-white/10';
const workspaceGhostButtonClass =
  'inline-flex items-center justify-center gap-2 rounded-xl bg-sky-50/80 px-4 py-2.5 font-medium text-slate-600 transition hover:bg-sky-100 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10';
const workspaceSectionTitleClass = 'text-2xl font-bold tracking-tight text-slate-900 dark:text-white';
const workspaceSectionTextClass = 'text-sm leading-relaxed text-slate-500 dark:text-slate-400';

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
      setEditError('账号和姓名不能为空');
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
                <label className="text-xs text-slate-500 dark:text-slate-400">账号 <span className="text-slate-400 dark:text-slate-500">· 登录用</span></label>
                <input
                  type="text"
                  value={editUsername}
                  onChange={(e) => setEditUsername(e.target.value)}
                  className={`${workspaceFieldClass} w-full`}
                  placeholder="登录用"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-slate-500 dark:text-slate-400">姓名 <span className="text-slate-400 dark:text-slate-500">· 对外显示</span></label>
                <input
                  type="text"
                  value={editDisplayName}
                  onChange={(e) => setEditDisplayName(e.target.value)}
                  className={`${workspaceFieldClass} w-full`}
                  placeholder="对外显示的姓名"
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
                  修改账号 / 姓名
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
  compact,
  onProfileUpdated,
}: {
  activePage: Page;
  currentUser: CurrentUser;
  onLogout: () => void;
  setActivePage: (p: Page) => void;
  onNavigate?: () => void;
  mobile?: boolean;
  compact?: boolean;
  onProfileUpdated?: (username: string, displayName: string) => void;
}) => {
  const [accountSheetOpen, setAccountSheetOpen] = useState(false);
  const menuItems = [
    ...[
      { id: 'dashboard', icon: LayoutDashboard, label: '工作台' },
      { id: 'review-generation', icon: Library, label: '复习生成' },
      { id: 'class-feedback-generation', icon: FileText, label: '课堂反馈' },
      { id: 'consultation', icon: MessageSquare, label: '咨询记录' },
      { id: 'calendar', icon: CalendarDays, label: '课程日历' },
      ...(canAccessSmartWrongQuestions(currentUser.role)
        ? [{ id: 'smartWrongQuestions', icon: Cpu, label: '智能错题' }]
        : []),
      { id: 'classes', icon: Home, label: '班级管理' },
      ...(hasOwnerAccess(currentUser.role) ? [{ id: 'credit', icon: Bell, label: '积分中心' }] : []),
      ...(hasStaffAccess(currentUser.role) ? [{ id: 'accounts', icon: User, label: '账号审批' }] : []),
      { id: 'settings', icon: Settings, label: '系统设置' },
    ].filter((item) => canOpenWorkspacePage(currentUser, item.id as Page)),
  ];

  return (
    <div
      className={cn(
        'flex flex-col border-r border-sky-100/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96)_0%,rgba(239,248,255,0.92)_52%,rgba(231,243,255,0.96)_100%)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(8,15,30,0.98)_0%,rgba(15,23,42,0.96)_52%,rgba(17,24,39,0.98)_100%)]',
        mobile
          ? 'h-full w-full overflow-y-auto overscroll-y-auto [-webkit-overflow-scrolling:touch] shadow-[18px_0_48px_rgba(47,128,237,0.12)] dark:shadow-[18px_0_48px_rgba(2,6,23,0.48)]'
          : compact
            ? 'h-screen w-24 shadow-[18px_0_48px_rgba(47,128,237,0.06)] dark:shadow-[18px_0_48px_rgba(2,6,23,0.38)]'
            : 'h-screen w-72 shadow-[18px_0_48px_rgba(47,128,237,0.06)] dark:shadow-[18px_0_48px_rgba(2,6,23,0.38)]',
      )}
    >
      <div className={cn('border-b border-sky-100/80 py-6 dark:border-white/10', compact && !mobile ? 'px-4' : 'px-6')}>
        <div className={cn('flex items-center gap-3', compact && !mobile && 'justify-center')}>
        <img src="/logo.png" alt="星润 logo" className="w-10 h-10 object-contain" />
          <div className={cn(compact && !mobile && 'hidden')}>
            <h1 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">Starain 工作台</h1>
            <p className="mt-1 text-xs font-semibold uppercase tracking-[0.26em] text-sky-600">机构工作台</p>
          </div>
        </div>
      </div>

      <nav className={cn('flex-1 space-y-1 py-5', compact && !mobile ? 'px-3' : 'px-4')}>
        {menuItems.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => {
              setActivePage(item.id as Page);
              onNavigate?.();
            }}
            className={cn(
              'relative flex w-full touch-manipulation items-center gap-3 rounded-2xl px-4 py-3 text-left transition-all duration-200',
              compact && !mobile && 'justify-center px-3',
              activePage === item.id
                ? 'border border-sky-200 bg-white text-sky-700 shadow-[0_16px_36px_rgba(47,128,237,0.08)] dark:border-sky-500/30 dark:bg-white/10 dark:text-sky-300 dark:shadow-[0_16px_36px_rgba(2,6,23,0.35)]'
                : 'border border-transparent text-slate-500 hover:border-sky-100 hover:bg-white/75 hover:text-slate-800 dark:text-slate-400 dark:hover:border-white/10 dark:hover:bg-white/5 dark:hover:text-slate-100',
            )}
          >
            <item.icon size={20} />
            <span className={cn('font-medium', compact && !mobile && 'hidden')}>{item.label}</span>
            {activePage === item.id && (
              <motion.div
                layoutId="active-pill"
                className={cn('h-2 w-2 rounded-full bg-sky-500', compact && !mobile ? 'absolute right-2' : 'ml-auto')}
              />
            )}
          </button>
        ))}
      </nav>

      <div className={cn('mt-auto border-t border-sky-100/80 p-4 dark:border-white/10', compact && !mobile && 'px-3')}>
        <button
          type="button"
          onClick={() => setAccountSheetOpen(true)}
          className={cn('flex w-full items-center gap-3 rounded-2xl border border-sky-100 bg-white/80 p-3 text-left transition-colors hover:bg-white dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/10', compact && !mobile && 'justify-center')}
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-sky-500 via-cyan-500 to-blue-500 font-bold text-white">
            {currentUser.display_name.slice(0, 1).toUpperCase()}
          </div>
          <div className={cn('flex-1 min-w-0', compact && !mobile && 'hidden')}>
            <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">{currentUser.display_name}</p>
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">{getRoleLabel(currentUser.role)}</p>
          </div>
          <MoreVertical size={16} className={cn('shrink-0 text-slate-400 dark:text-slate-500', compact && !mobile && 'hidden')} />
        </button>
      </div>

      <button
        type="button"
        onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
        className="fixed bottom-6 right-6 z-20 flex h-11 w-11 items-center justify-center rounded-full bg-slate-900 text-white shadow-[0_18px_35px_rgba(15,23,42,0.25)] transition hover:bg-slate-700 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200"
        aria-label="回到顶部"
        title="回到顶部"
      >
        <ArrowUp size={20} />
      </button>

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
    <header className="sticky top-0 z-10 flex h-20 items-center justify-between border-b border-sky-100/80 bg-white/92 px-4 sm:bg-white/78 sm:backdrop-blur-xl sm:px-6 md:px-8 dark:border-white/10 dark:bg-[#0f172a]/92 dark:sm:bg-[#0f172a]/88">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">Workspace</p>
        <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-900 sm:text-2xl dark:text-white">{title}</h2>
      </div>
      <div className="flex items-center gap-2 sm:gap-4">
        {onOpenSidebar && (
          <button
            type="button"
            onClick={onOpenSidebar}
            title="打开导航"
            aria-label="打开导航"
            className="flex h-11 w-11 touch-manipulation items-center justify-center rounded-full border border-sky-200 bg-white text-slate-500 transition-colors hover:bg-sky-50 hover:text-slate-800 lg:hidden dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white"
          >
            <Menu size={20} />
          </button>
        )}
        {onToggleDarkMode && (
          <button
            type="button"
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
            type="button"
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

const WorkspaceLoading = ({ label = '正在处理中...' }: { label?: string }) => (
  <div className="flex flex-col items-center justify-center py-12 text-center">
    <div className="mb-4 h-8 w-8 animate-spin rounded-full border-2 border-sky-200 border-t-sky-500" />
    <p className="font-medium text-slate-700 dark:text-slate-200">{label}</p>
  </div>
);

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
        className={`${workspaceFieldClass} w-full`}
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

const LessonInput = ({
  onSuccess,
  currentUser,
}: {
  onSuccess: (result: ReviewPlanCreateResponse) => void;
  currentUser: CurrentUser;
}) => {
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [lessonDate, setLessonDate] = useState(new Date().toISOString().split('T')[0]);
  const [weakPoints, setWeakPoints] = useState('');
  const [summaryText, setSummaryText] = useState('');
  const [sameLessonMaterials, setSameLessonMaterials] = useState('');
  const [inputType, setInputType] = useState<'text' | 'file'>('text');
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [classesLoading, setClassesLoading] = useState(true);
  const [error, setError] = useState('');
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [classId, setClassId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    setClassesLoading(true);
    apiFetch<ClassItem[]>('/api/classes')
      .then((nextClasses) => {
        if (cancelled) {
          return;
        }
        setClasses(nextClasses);
      })
      .catch((fetchError) => {
        if (cancelled) {
          return;
        }
        setClasses([]);
        console.error(fetchError);
      })
      .finally(() => {
        if (!cancelled) {
          setClassesLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [currentUser.id, currentUser.role]);

  useEffect(() => {
    if (classesLoading || classId === null) {
      return;
    }
    if (classes.some((item) => item.id === classId)) {
      return;
    }
    setClassId(null);
  }, [classId, classes, classesLoading]);

  useEffect(() => {
    if (classesLoading || currentUser.role !== 'member') {
      return;
    }

    setClassId((current) => syncMemberScopedClassSelection(currentUser.role, classes, current));
  }, [classes, classesLoading, currentUser.role]);

  const hasNoAssignableClasses = currentUser.role === 'member' && !classesLoading && classes.length === 0;

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
    if (hasNoAssignableClasses) {
      setError('当前账号未分配负责班级，请先联系管理员分配班级');
      return;
    }
    if (!classId) {
      setError('请选择班级后再生成复习记录');
      return;
    }
    if (inputType === 'text' && !summaryText.trim()) {
      setError('请填写课堂笔记内容');
      return;
    }
    if (inputType === 'file' && !file) {
      setError('请选择上传文件');
      return;
    }

    setIsLoading(true);
    setUploadProgress(0);
    try {
      let result: ReviewPlanCreateResponse;
      if (inputType === 'text') {
        result = await apiFetch<ReviewPlanCreateResponse>('/api/review-plans', {
          method: 'POST',
          body: JSON.stringify({
            subject,
            class_id: classId ?? 0,
            topic,
            date: lessonDate,
            weak_points: weakPoints,
            summary_text: summaryText,
            same_lesson_materials: sameLessonMaterials,
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
        formData.append('same_lesson_materials', sameLessonMaterials);
        if (file) formData.append('upload_file', file);
        result = await apiUploadFormWithProgress<ReviewPlanCreateResponse>('/api/review-plans', formData, setUploadProgress);
      }
      onSuccess(result);
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
            <div className="w-full max-w-sm space-y-4">
              <WorkspaceLoading label={inputType === 'file' ? '正在上传课堂文件...' : '正在生成复习资料...'} />
              {inputType === 'file' && (
                <div className="space-y-2">
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-white/10">
                    <div
                      className="h-full rounded-full bg-sky-500 transition-all"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                  <p className="text-center text-xs text-slate-500 dark:text-slate-400">{uploadProgress}%</p>
                </div>
              )}
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="form"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-8"
          >
            <div className="space-y-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Lesson Intake</p>
                <h3 className={`${workspaceSectionTitleClass} mt-3`}>生成复习文档</h3>
                <p className={`${workspaceSectionTextClass} mt-2`}>
                  上传录音或粘贴笔记，生成 AI 复习资料和教学素材。
                </p>
              </div>
              <div className="grid gap-3 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,0.9fr)]">
                <SubjectCombobox
                  value={subject}
                  onChange={setSubject}
                  options={[...new Set<string>(classes.map((c: ClassItem) => c.subject).filter(Boolean))] as string[]}
                  className="w-full"
                />
                <select
                  value={classId ?? ''}
                  onChange={(e) => handleClassChange(Number(e.target.value))}
                  className={`${workspaceFieldClass} w-full`}
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
                  className={`${workspaceFieldClass} w-full`}
                />
              </div>
              {hasNoAssignableClasses && (
                <p className="text-sm text-amber-600 dark:text-amber-300">
                  当前账号未分配负责班级，请先联系管理员分配班级后再生成复习记录。
                </p>
              )}
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
                  <textarea
                    placeholder="同一节课补充材料（选填）：第二段录音纪要、飞书智能纪要或老师补充说明"
                    value={sameLessonMaterials}
                    onChange={(e) => setSameLessonMaterials(e.target.value)}
                    rows={5}
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

const ReviewDocumentHistory = ({
  refreshToken = 0,
  highlightedLessonId = null,
}: {
  refreshToken?: number;
  highlightedLessonId?: number | null;
}) => {
  const REVIEW_HISTORY_PAGE_SIZE = 12;
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [loading, setLoading] = useState(true);
  const [historyPage, setHistoryPage] = useState(1);

  const load = useCallback((quiet = false) => {
    if (!quiet) {
      setLoading(true);
    }
    return apiFetch<unknown>('/api/review-plans')
      .then((payload) => setLessons(normalizeReviewLessonsResponse(payload)))
      .catch(console.error)
      .finally(() => {
        if (!quiet) {
          setLoading(false);
        }
      });
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshToken]);

  const hasPendingLesson = lessons.some(isReviewLessonPending);

  useEffect(() => {
    if (!hasPendingLesson) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      void load(true);
    }, 3000);

    return () => window.clearInterval(timer);
  }, [hasPendingLesson, load]);

  const totalHistoryPages = Math.max(1, Math.ceil(lessons.length / REVIEW_HISTORY_PAGE_SIZE));
  const currentHistoryPage = Math.min(historyPage, totalHistoryPages);
  const paginatedLessons = lessons.slice((currentHistoryPage - 1) * REVIEW_HISTORY_PAGE_SIZE, currentHistoryPage * REVIEW_HISTORY_PAGE_SIZE);

  useEffect(() => {
    if (highlightedLessonId) {
      const highlightedIndex = lessons.findIndex((lesson) => lesson.id === highlightedLessonId);
      if (highlightedIndex >= 0) {
        setHistoryPage(Math.floor(highlightedIndex / REVIEW_HISTORY_PAGE_SIZE) + 1);
        return;
      }
    }
    setHistoryPage(1);
  }, [highlightedLessonId, lessons]);

  const handleDelete = async (id: number) => {
    if (!window.confirm('确定删除此课程？相关 PDF 也会被删除。')) return;
    await apiFetch(`/api/review-plans/${id}`, { method: 'DELETE' });
    load();
  };

  return (
    <div className={`${workspaceCardClass} overflow-hidden`}>
      {loading ? (
        <div className="p-8 text-center text-slate-500 dark:text-slate-400">加载中...</div>
      ) : lessons.length === 0 ? (
        <div className="p-8 text-center text-slate-500 dark:text-slate-400">还没有复习文档，点击「新建复习文档」开始生成</div>
      ) : (
        <div className="space-y-5 p-5 sm:p-6">
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {paginatedLessons.map((lesson) => (
              <article
                key={lesson.id}
                className={cn(
                  'group flex h-full flex-col rounded-2xl border border-sky-100/80 bg-white/90 p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-sky-200 hover:shadow-md dark:border-white/10 dark:bg-slate-900/70',
                  highlightedLessonId === lesson.id && 'border-emerald-300 ring-2 ring-emerald-200 dark:border-emerald-400/60 dark:ring-emerald-400/20',
                )}
              >
                {(() => {
                  const taskState = getReviewLessonTaskState(lesson);
                  const taskMessage = getReviewLessonTaskMessage(lesson);
                  const taskProgress = getReviewLessonTaskProgress(lesson);
                  const statusLabel = lesson.record_status === 'transcribing'
                    ? '转写中'
                    : taskState === 'pending'
                    ? '生成中'
                    : taskState === 'failed'
                      ? '生成失败'
                      : taskState === 'missing-output'
                        ? '待刷新'
                        : hasReviewLessonOutput(lesson)
                        ? '已生成'
                        : '无 PDF';
                  const statusDotClass = taskState === 'pending'
                    ? 'bg-amber-500'
                    : taskState === 'failed'
                      ? 'bg-rose-500'
                      : hasReviewLessonOutput(lesson)
                        ? 'bg-emerald-500'
                        : 'bg-slate-300 dark:bg-slate-600';

                  return (
                    <>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-sky-50 text-sky-600 dark:bg-white/5 dark:text-sky-300">
                            <FileText size={16} />
                          </div>
                          <p className="font-medium text-slate-900 dark:text-white">{lesson.topic || `${lesson.subject} 课程`}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className={cn('h-2 w-2 rounded-full', statusDotClass)} />
                          <span className="text-xs text-slate-500 dark:text-slate-400">{statusLabel}</span>
                        </div>
                      </div>

                      <div className="mt-4 flex flex-wrap gap-2">
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

                      <dl className="mt-4 space-y-2 text-sm">
                        <div className="flex items-center justify-between gap-3">
                          <dt className="text-slate-500 dark:text-slate-400">日期</dt>
                          <dd className="font-mono text-slate-700 dark:text-slate-200">{lesson.date}</dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <dt className="text-slate-500 dark:text-slate-400">生成时间</dt>
                          <dd className="text-slate-700 dark:text-slate-200">{new Date(lesson.created_at).toLocaleString('zh-CN')}</dd>
                        </div>
                      </dl>

                      {taskState === 'pending' && (
                        <div className="mt-4 space-y-2 rounded-2xl border border-amber-200 bg-amber-50/90 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
                          <div>{taskMessage || '正在生成复习计划，可离开页面'}</div>
                          <div className="h-1.5 overflow-hidden rounded-full bg-amber-100 dark:bg-white/10">
                            <div
                              className="h-full rounded-full bg-amber-500 transition-all"
                              style={{ width: `${taskProgress}%` }}
                            />
                          </div>
                        </div>
                      )}
                      {taskState === 'failed' && (
                        <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50/90 px-3 py-2 text-sm text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-200">
                          {taskMessage || '生成失败'}
                        </div>
                      )}
                      {taskState === 'missing-output' && (
                        <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50/90 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
                          {taskMessage}
                        </div>
                      )}

                      <div className="mt-4 flex flex-wrap justify-end gap-1">
                        {hasReviewLessonOutput(lesson) && (
                          <>
                            <a
                              href={buildAuthedPath(`/api/pdf/${lesson.id}`)}
                              target="_blank"
                              rel="noreferrer"
                              className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-500 transition-all hover:bg-sky-50 hover:text-sky-600 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-sky-300"
                              title="查看"
                            >
                              <Eye size={16} />
                            </a>
                            <a
                              href={buildAuthedPath(`/api/pdf/download/${lesson.id}`)}
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
                    </>
                  );
                })()}
              </article>
            ))}
          </div>

          <div className="flex items-center justify-between border-t border-sky-100/80 pt-4 text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
            <span>
              第 {currentHistoryPage} / {totalHistoryPages} 页
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setHistoryPage((current) => Math.max(1, current - 1))}
                disabled={currentHistoryPage <= 1}
                className={workspaceSecondaryButtonClass}
              >
                上一页
              </button>
              <button
                type="button"
                onClick={() => setHistoryPage((current) => Math.min(totalHistoryPages, current + 1))}
                disabled={currentHistoryPage >= totalHistoryPages}
                className={workspaceSecondaryButtonClass}
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const ReviewGenerationPage = ({
  onSuccess,
  currentUser,
}: {
  onSuccess: () => void;
  currentUser: CurrentUser;
}) => {
  const [composerOpen, setComposerOpen] = useState(false);
  const [historyRefreshToken, setHistoryRefreshToken] = useState(0);
  const [reviewNotice, setReviewNotice] = useState('');
  const [highlightedLessonId, setHighlightedLessonId] = useState<number | null>(null);

  const handleFormSuccess = (result: ReviewPlanCreateResponse) => {
    setComposerOpen(false);
    setHighlightedLessonId(result.id);
    if (result.duplicate) {
      setReviewNotice(`这份录音已处理过，已复用已有复习文档 #${result.id}。`);
    } else {
      setReviewNotice('');
    }
    setHistoryRefreshToken((current) => current + 1);
    onSuccess();
  };

  const handleToggleComposer = () => {
    if (composerOpen) {
      setComposerOpen(false);
      return;
    }
    setComposerOpen(true);
  };

  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className={workspaceSectionTitleClass}>历史文档</h3>
          <p className={`${workspaceSectionTextClass} mt-2`}>查看已生成的复习文档，支持下载、预览与删除。</p>
        </div>
        <button onClick={handleToggleComposer} className={workspacePrimaryButtonClass}>
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
          <LessonInput
            onSuccess={handleFormSuccess}
            currentUser={currentUser}
          />
        </div>
      )}

      {reviewNotice && (
        <div className="flex items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-200">
          <CheckCircle2 size={18} />
          <span className="text-sm">{reviewNotice}</span>
        </div>
      )}

      <ReviewDocumentHistory refreshToken={historyRefreshToken} highlightedLessonId={highlightedLessonId} />
    </div>
  );
};

function createEmptyClassFeedbackStageNotes(): ClassFeedbackStageNotes {
  return {
    classStatusNote: '',
    parentFeedbackNote: '',
    teachingFocusNote: '',
    nextStagePreviewNote: '',
  };
}

function createEmptyClassFeedbackStudentCards(roster: Array<{ id: number; name: string }>): ClassFeedbackStudentCard[] {
  return roster.map((student) => ({
    studentId: student.id,
    name: student.name,
    aiDraft: '',
    finalText: '',
    checked: false,
    sourceSummary: '等待生成本阶段草稿',
    highlightLabels: [],
    highlightNote: '',
  }));
}

function buildClassFeedbackDraftSnapshot(
  summary: string,
  students: ClassFeedbackStudentCard[],
): string {
  return JSON.stringify({
    classSummary: summary,
    students: students.map((student) => ({
      studentId: student.studentId,
      finalText: student.finalText,
    })),
  });
}

const ClassFeedbackGenerationPage = ({
  currentUser,
}: {
  currentUser: CurrentUser;
}) => {
  const todayIsoDate = getTodayIsoDate();
  const initialIsoWeek = getIsoWeekParts(todayIsoDate);
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [labelGroups, setLabelGroups] = useState<StageLabelGroup[]>(defaultStageLabelGroups);
  const [classesLoading, setClassesLoading] = useState(true);
  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [classFeedbackPeriodMode, setClassFeedbackPeriodMode] = useState<ClassFeedbackPeriodGranularity>('weekly');
  const [classFeedbackAnchorDate, setClassFeedbackAnchorDate] = useState(todayIsoDate);
  const [classFeedbackPeriodYear, setClassFeedbackPeriodYear] = useState(initialIsoWeek.year);
  const [classFeedbackPeriodWeek, setClassFeedbackPeriodWeek] = useState(initialIsoWeek.week);
  const [classFeedbackPeriodMonth, setClassFeedbackPeriodMonth] = useState(Number(todayIsoDate.slice(5, 7)));
  const [classFeedbackStageName, setClassFeedbackStageName] = useState<ClassFeedbackStageName>(
    inferClassFeedbackStageName(todayIsoDate),
  );
  const [activeClassFeedbackTaskId, setActiveClassFeedbackTaskId] = useState<number | null>(null);
  const [classFeedbackStudents, setClassFeedbackStudents] = useState<ClassFeedbackStudentCard[]>([]);
  const [classFeedbackSummary, setClassFeedbackSummary] = useState('');
  const [classFeedbackStatusMessage, setClassFeedbackStatusMessage] = useState(
    '先选择班级和反馈阶段，再汇总阶段素材。',
  );
  const [classFeedbackStageNotes, setClassFeedbackStageNotes] = useState<ClassFeedbackStageNotes>(
    createEmptyClassFeedbackStageNotes(),
  );
  const [classFeedbackStatusTags, setClassFeedbackStatusTags] = useState<string[]>([]);
  const [teacherNameLabel, setTeacherNameLabel] = useState(currentUser.display_name);
  const [currentTaskStatus, setCurrentTaskStatus] = useState<string>('draft');
  const [matchedLessonCount, setMatchedLessonCount] = useState(0);
  const [isRefreshingTask, setIsRefreshingTask] = useState(false);
  const [isGeneratingClassFeedback, setIsGeneratingClassFeedback] = useState(false);
  const [isSavingClassFeedback, setIsSavingClassFeedback] = useState(false);
  const [isConfirmingClassFeedback, setIsConfirmingClassFeedback] = useState(false);
  const classFeedbackDraftSnapshotRef = useRef('');

  const selectedClass = classes.find((item) => item.id === selectedClassId) ?? null;
  const classFeedbackPeriodSelection = useMemo<ClassFeedbackPeriodSelection>(() => {
    if (classFeedbackPeriodMode === 'daily') {
      return {
        periodGranularity: 'daily',
        anchorDate: classFeedbackAnchorDate,
      };
    }
    if (classFeedbackPeriodMode === 'weekly') {
      return {
        periodGranularity: 'weekly',
        year: classFeedbackPeriodYear,
        week: classFeedbackPeriodWeek,
      };
    }
    if (classFeedbackPeriodMode === 'monthly') {
      return {
        periodGranularity: 'monthly',
        year: classFeedbackPeriodYear,
        month: classFeedbackPeriodMonth,
      };
    }
    return {
      periodGranularity: 'stage',
      year: classFeedbackPeriodYear,
      stageName: classFeedbackStageName,
    };
  }, [
    classFeedbackAnchorDate,
    classFeedbackPeriodMode,
    classFeedbackPeriodMonth,
    classFeedbackPeriodWeek,
    classFeedbackPeriodYear,
    classFeedbackStageName,
  ]);
  const classFeedbackPeriodPreview = useMemo(
    () => buildClassFeedbackPeriodPreview(classFeedbackPeriodSelection),
    [classFeedbackPeriodSelection],
  );
  const classFeedbackPeriodYearOptions = useMemo(
    () => [classFeedbackPeriodYear - 1, classFeedbackPeriodYear, classFeedbackPeriodYear + 1],
    [classFeedbackPeriodYear],
  );

  const resetClassFeedbackWorkspaceState = useCallback((statusMessage = '先选择班级和反馈阶段，再汇总阶段素材。') => {
    setActiveClassFeedbackTaskId(null);
    setCurrentTaskStatus('draft');
    setTeacherNameLabel(currentUser.display_name);
    setClassFeedbackSummary('');
    setClassFeedbackStatusTags([]);
    setClassFeedbackStageNotes(createEmptyClassFeedbackStageNotes());
    setClassFeedbackStudents([]);
    setMatchedLessonCount(0);
    classFeedbackDraftSnapshotRef.current = '';
    setClassFeedbackStatusMessage(statusMessage);
  }, [currentUser.display_name]);

  const loadRosterOnly = useCallback(async (classId: number) => {
    const roster = await listClassStudents(classId);
    setClassFeedbackStudents(createEmptyClassFeedbackStudentCards(roster.students));
    return roster.students.length;
  }, []);

  const hydrateClassFeedbackTask = useCallback(
    async (taskId: number, classId: number) => {
    setIsRefreshingTask(true);
    try {
      const [rawTask, roster] = await Promise.all([
        loadClassFeedbackTask(taskId),
        listClassStudents(classId),
      ]);
      const task = normalizeClassFeedbackTaskResponse(rawTask);
      if (!task) {
        throw new Error('反馈任务响应格式异常，请刷新后重试。');
      }
      const hydratedStudents = buildClassFeedbackStudentCards({
        roster: roster.students,
        task,
      });
      const hydratedSummary =
        task.class_summary_final_text?.trim() ? task.class_summary_final_text : task.class_summary_ai_draft ?? '';
      setActiveClassFeedbackTaskId(task.id);
      setSelectedClassId(task.class_id);
      setTeacherNameLabel(task.teacher_name_snapshot || selectedClass?.teacher_name || currentUser.display_name);
      setClassFeedbackStatusTags(task.class_status_tags ?? []);
      setClassFeedbackStageNotes({
        classStatusNote: task.class_status_note ?? '',
        parentFeedbackNote: task.parent_feedback_note ?? '',
        teachingFocusNote: task.teaching_focus_note ?? '',
        nextStagePreviewNote: task.next_stage_preview_note ?? '',
      });
      setClassFeedbackStudents(hydratedStudents);
      setClassFeedbackSummary(hydratedSummary);
      setCurrentTaskStatus(task.status);
      classFeedbackDraftSnapshotRef.current = buildClassFeedbackDraftSnapshot(hydratedSummary, hydratedStudents);
      const isGeneratingTask = isClassFeedbackTaskGenerating(task);
      setClassFeedbackStatusMessage(
        isGeneratingTask
          ? '课堂反馈仍在生成中，请稍后点击刷新任务。'
          : task.status === 'confirmed'
          ? `已确认 ${roster.students.length} 名学生反馈，可直接复制内容。`
            : `已同步 ${roster.students.length} 名学生，可补充阶段备注并生成草稿。`,
        );
      return task;
      } finally {
        setIsRefreshingTask(false);
      }
    },
    [currentUser.display_name, selectedClass?.teacher_name],
  );

  useEffect(() => {
    let cancelled = false;
    setClassesLoading(true);
    Promise.all([apiFetch<ClassItem[]>('/api/classes'), loadClassFeedbackLabels()])
      .then(([classItems, labelResult]) => {
        if (cancelled) {
          return;
        }
        setClasses(classItems);
        setSelectedClassId((current) => syncMemberScopedClassSelection(currentUser.role, classItems, current));
        setLabelGroups(labelResult.groups?.length ? labelResult.groups : defaultStageLabelGroups);
      })
      .catch((error) => {
        if (!cancelled) {
          setClassFeedbackStatusMessage(error instanceof Error ? error.message : '课堂反馈初始化失败，请刷新重试。');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setClassesLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (classesLoading || currentUser.role !== 'member') {
      return;
    }

    const nextClassId = syncMemberScopedClassSelection(currentUser.role, classes, selectedClassId);
    if (nextClassId === selectedClassId) {
      return;
    }

    resetClassFeedbackWorkspaceState('班级权限已变化，请重新同步反馈任务。');
    setTeacherNameLabel(
      nextClassId
        ? classes.find((item) => item.id === nextClassId)?.teacher_name || currentUser.display_name
        : currentUser.display_name,
    );
    setSelectedClassId(nextClassId);
  }, [classes, classesLoading, currentUser.display_name, currentUser.role, resetClassFeedbackWorkspaceState, selectedClassId]);

  useEffect(() => {
    if (classesLoading || currentUser.role === 'member' || selectedClassId === null) {
      return;
    }

    if (classes.some((item) => item.id === selectedClassId)) {
      return;
    }

    resetClassFeedbackWorkspaceState('班级权限已变化，请重新同步反馈任务。');
    setSelectedClassId(null);
  }, [classes, classesLoading, currentUser.role, resetClassFeedbackWorkspaceState, selectedClassId]);

  useEffect(() => {
    if (!selectedClassId) {
      setMatchedLessonCount(0);
      return;
    }

    let cancelled = false;
    apiFetch<Lesson[]>('/api/review-plans')
      .then((lessons) => {
        if (cancelled) {
          return;
        }
        const count = lessons.filter(
          (lesson) =>
            lesson.class_id === selectedClassId &&
            lesson.date >= classFeedbackPeriodPreview.startDate &&
            lesson.date <= classFeedbackPeriodPreview.endDate,
        ).length;
        setMatchedLessonCount(count);
      })
      .catch(() => {
        if (!cancelled) {
          setMatchedLessonCount(0);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [classFeedbackPeriodPreview.endDate, classFeedbackPeriodPreview.startDate, selectedClassId]);

  const handleClassChange = async (nextClassId: number | null) => {
    setSelectedClassId(nextClassId);
    resetClassFeedbackWorkspaceState();
    setTeacherNameLabel(nextClassId ? classes.find((item) => item.id === nextClassId)?.teacher_name || currentUser.display_name : currentUser.display_name);

    if (!nextClassId) {
      return;
    }

    setIsRefreshingTask(true);
    try {
      const studentCount = await loadRosterOnly(nextClassId);
      setClassFeedbackStatusMessage(
        studentCount > 0
          ? `已同步 ${studentCount} 名学生，请选择反馈阶段后创建反馈任务。`
            : '当前班级还没有学生，请先到学生管理页面添加学生。',
      );
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '班级学生同步失败，请重试。');
    } finally {
      setIsRefreshingTask(false);
    }
  };

  const handleCreateClassFeedbackTask = useCallback(async () => {
    if (!selectedClassId) {
      setClassFeedbackStatusMessage('请先选择班级。');
      return;
    }

    setIsSavingClassFeedback(true);
    try {
      const created = await createClassFeedbackTask({
        ...buildCreateClassFeedbackTaskRequest({
          classId: selectedClassId,
          ...classFeedbackPeriodSelection,
        }),
      });
      await hydrateClassFeedbackTask(created.id, selectedClassId);
      setClassFeedbackStatusMessage(`已创建反馈任务，按 ${created.period_granularity} 粒度准备资料。`);
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '创建课堂反馈任务失败，请重试。');
    } finally {
      setIsSavingClassFeedback(false);
    }
  }, [classFeedbackPeriodSelection, hydrateClassFeedbackTask, selectedClassId]);

  const handleRefreshClassFeedbackTask = useCallback(async () => {
    if (!activeClassFeedbackTaskId || !selectedClassId) {
      return;
    }

    try {
      await hydrateClassFeedbackTask(activeClassFeedbackTaskId, selectedClassId);
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '刷新反馈任务失败，请重试。');
    }
  }, [activeClassFeedbackTaskId, hydrateClassFeedbackTask, selectedClassId]);

  const handleStageNoteChange = (key: keyof ClassFeedbackStageNotes, value: string) => {
    setClassFeedbackStageNotes((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const handleClassStatusTagToggle = (label: string) => {
    setClassFeedbackStatusTags((current) =>
      current.includes(label) ? current.filter((item) => item !== label) : [...current, label],
    );
  };

  const handleHighlightToggle = (studentId: number, label: string) => {
    setClassFeedbackStudents((current) =>
      current.map((student) => {
        if (student.studentId !== studentId) {
          return student;
        }
        const alreadySelected = student.highlightLabels.includes(label);
        return {
          ...student,
          highlightLabels: alreadySelected
            ? student.highlightLabels.filter((item) => item !== label)
            : [...student.highlightLabels, label],
        };
      }),
    );
  };

  const handleHighlightNoteChange = (studentId: number, value: string) => {
    setClassFeedbackStudents((current) =>
      current.map((student) => (student.studentId === studentId ? { ...student, highlightNote: value } : student)),
    );
  };

  const handleStudentFinalTextChange = (studentId: number, value: string) => {
    setClassFeedbackStudents((current) =>
      current.map((student) => (student.studentId === studentId ? { ...student, finalText: value } : student)),
    );
  };

  const handleStudentCheckedChange = (studentId: number, checked: boolean) => {
    setClassFeedbackStudents((current) =>
      current.map((student) => (student.studentId === studentId ? { ...student, checked } : student)),
    );
  };

  const saveCurrentClassFeedbackDraft = useCallback(async () => {
    if (!activeClassFeedbackTaskId || currentTaskStatus === 'confirmed') {
      return;
    }

    const nextSnapshot = buildClassFeedbackDraftSnapshot(classFeedbackSummary, classFeedbackStudents);
    if (nextSnapshot === classFeedbackDraftSnapshotRef.current) {
      return;
    }

    setIsSavingClassFeedback(true);
    try {
      const savedTask = await saveClassFeedbackTaskDraft(activeClassFeedbackTaskId, {
        classSummaryDraftText: classFeedbackSummary,
        studentEntries: classFeedbackStudents.map((student) => ({
          studentId: student.studentId,
          finalText: student.finalText,
        })),
      });
      const savedStudents = buildClassFeedbackStudentCards({
        roster: classFeedbackStudents.map((student) => ({
          id: student.studentId,
          name: student.name,
        })),
        task: savedTask,
      }).map((student) => {
        const currentCard = classFeedbackStudents.find((item) => item.studentId === student.studentId);
        return currentCard
          ? {
              ...student,
              checked: currentCard.checked,
              highlightLabels: currentCard.highlightLabels,
              highlightNote: currentCard.highlightNote,
            }
          : student;
      });
      setClassFeedbackSummary(savedTask.class_summary_ai_draft ?? '');
      setClassFeedbackStudents(savedStudents);
      classFeedbackDraftSnapshotRef.current = buildClassFeedbackDraftSnapshot(
        savedTask.class_summary_ai_draft ?? '',
        savedStudents,
      );
      setClassFeedbackStatusMessage('课堂反馈草稿已保存。');
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '保存课堂反馈草稿失败，请重试。');
    } finally {
      setIsSavingClassFeedback(false);
    }
  }, [activeClassFeedbackTaskId, classFeedbackStudents, classFeedbackSummary, currentTaskStatus]);

  useEffect(() => {
    if (!activeClassFeedbackTaskId || currentTaskStatus === 'confirmed' || isRefreshingTask || isGeneratingClassFeedback || isConfirmingClassFeedback) {
      return;
    }
    const nextSnapshot = buildClassFeedbackDraftSnapshot(classFeedbackSummary, classFeedbackStudents);
    if (nextSnapshot === classFeedbackDraftSnapshotRef.current) {
      return;
    }
    const timer = window.setTimeout(() => {
      void saveCurrentClassFeedbackDraft();
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [
    activeClassFeedbackTaskId,
    classFeedbackStudents,
    classFeedbackSummary,
    currentTaskStatus,
    isConfirmingClassFeedback,
    isGeneratingClassFeedback,
    isRefreshingTask,
    saveCurrentClassFeedbackDraft,
  ]);

  const handleGenerateClassFeedback = useCallback(async () => {
    if (!activeClassFeedbackTaskId) {
      setClassFeedbackStatusMessage('请先创建反馈任务。');
      return;
    }
    if (!selectedClassId) {
      setClassFeedbackStatusMessage('请先选择班级。');
      return;
    }

    setIsGeneratingClassFeedback(true);
    try {
      const rawGenerated = await generateClassFeedbackTask(activeClassFeedbackTaskId, {
        classStatusTags: classFeedbackStatusTags,
        classStatusNote: classFeedbackStageNotes.classStatusNote,
        parentFeedbackNote: classFeedbackStageNotes.parentFeedbackNote,
        teachingFocusNote: classFeedbackStageNotes.teachingFocusNote,
        nextStagePreviewNote: classFeedbackStageNotes.nextStagePreviewNote,
        studentHighlights: classFeedbackStudents.map((student) => ({
          studentId: student.studentId,
          labels: student.highlightLabels,
          note: student.highlightNote,
        })),
      });
      const generated = normalizeClassFeedbackTaskResponse(rawGenerated, { fallbackClassId: selectedClassId });
      if (!generated) {
        throw new Error('反馈任务响应格式异常，请刷新后重试。');
      }
      const hydratedTask = await hydrateClassFeedbackTask(generated.id, selectedClassId);
      if (isClassFeedbackTaskGenerating(hydratedTask)) {
        setClassFeedbackStatusMessage('课堂反馈仍在生成中，请稍后点击刷新任务。');
        return;
      }
      if (!hasCompleteClassFeedbackGeneratedContent(hydratedTask, classFeedbackStudents.length)) {
        setClassFeedbackStatusMessage('反馈任务已返回，但生成内容不完整，请点击刷新任务确认。');
        return;
      }
      setClassFeedbackStatusMessage(`已生成班级总评和 ${classFeedbackStudents.length} 名学生反馈草稿。`);
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '生成课堂反馈失败，请重试。');
    } finally {
      setIsGeneratingClassFeedback(false);
    }
  }, [
    activeClassFeedbackTaskId,
    classFeedbackStageNotes.classStatusNote,
    classFeedbackStageNotes.nextStagePreviewNote,
    classFeedbackStageNotes.parentFeedbackNote,
    classFeedbackStageNotes.teachingFocusNote,
    classFeedbackStatusTags,
    classFeedbackStudents,
    hydrateClassFeedbackTask,
    selectedClassId,
  ]);

  const handleCopyClassFeedbackSummary = async () => {
    if (!classFeedbackSummary.trim()) {
      setClassFeedbackStatusMessage('当前还没有可复制的班级总评。');
      return;
    }
    try {
      await navigator.clipboard.writeText(classFeedbackSummary.trim());
      setClassFeedbackStatusMessage('班级总评已复制到剪贴板。');
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '复制班级总评失败，请重试。');
    }
  };

  const handleCopyAllClassFeedbackStudents = async () => {
    const content = formatClassFeedbackStudentCopyText(sortedClassFeedbackStudents);
    if (!content) {
      setClassFeedbackStatusMessage('当前还没有可复制的学生反馈。');
      return;
    }
    try {
      await navigator.clipboard.writeText(content);
      setClassFeedbackStatusMessage('全部学生反馈已复制到剪贴板。');
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '复制学生反馈失败，请重试。');
    }
  };

  const handleConfirmClassFeedback = useCallback(async () => {
    if (!activeClassFeedbackTaskId) {
      setClassFeedbackStatusMessage('请先创建反馈任务。');
      return;
    }
    if (!selectedClassId) {
      setClassFeedbackStatusMessage('请先选择班级。');
      return;
    }

    setIsConfirmingClassFeedback(true);
    try {
      const payload = buildClassFeedbackConfirmPayload({
        classSummaryFinalText: classFeedbackSummary,
        students: classFeedbackStudents,
      });
      const confirmed = await confirmClassFeedbackTask(activeClassFeedbackTaskId, payload);
      await hydrateClassFeedbackTask(confirmed.id, selectedClassId);
      setClassFeedbackStatusMessage(`已确认 ${classFeedbackStudents.length} 名学生反馈，并写入后续积累。`);
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '确认课堂反馈失败，请重试。');
    } finally {
      setIsConfirmingClassFeedback(false);
    }
  }, [
    activeClassFeedbackTaskId,
    classFeedbackStudents,
    classFeedbackSummary,
    hydrateClassFeedbackTask,
    selectedClassId,
  ]);

  const checkedStudentCount = useMemo(
    () => classFeedbackStudents.filter((student) => student.checked).length,
    [classFeedbackStudents],
  );
  const uncheckedStudentCount = classFeedbackStudents.length - checkedStudentCount;
  const studentsWithHighlightsCount = useMemo(
    () =>
      classFeedbackStudents.filter(
        (student) => student.highlightLabels.length > 0 || student.highlightNote.trim(),
      ).length,
    [classFeedbackStudents],
  );
  const studentsAwaitingDraftCount = useMemo(
    () =>
      classFeedbackStudents.filter(
        (student) => !(student.finalText || student.aiDraft).trim(),
      ).length,
    [classFeedbackStudents],
  );
  const sortedClassFeedbackStudents = useMemo(
    () =>
      [...classFeedbackStudents].sort((left, right) => {
        if (left.checked !== right.checked) {
          return left.checked ? 1 : -1;
        }
        return left.name.localeCompare(right.name, 'zh-CN');
      }),
    [classFeedbackStudents],
  );
  const hasUnsavedDraftChanges =
    activeClassFeedbackTaskId !== null &&
    currentTaskStatus !== 'confirmed' &&
    buildClassFeedbackDraftSnapshot(classFeedbackSummary, classFeedbackStudents) !==
      classFeedbackDraftSnapshotRef.current;
  const classFeedbackDraftStatusLabel = currentTaskStatus === 'confirmed'
    ? '本次反馈已确认。'
    : !activeClassFeedbackTaskId
      ? '创建反馈任务后开始记录草稿。'
      : isSavingClassFeedback
        ? '正在保存草稿...'
        : hasUnsavedDraftChanges
          ? '有未保存修改，自动保存中。'
          : '草稿已保存。';

  const sourceSummaryItems = [
    selectedClass ? `当前班级：${selectedClass.name}` : '当前班级：未选择',
    `反馈阶段：${classFeedbackPeriodPreview.label}`,
    `覆盖范围：${classFeedbackPeriodPreview.startDate} 至 ${classFeedbackPeriodPreview.endDate}`,
    `已命中 ${matchedLessonCount} 节课次记录`,
    `学生人数：${classFeedbackStudents.length} 名`,
    `已检查 ${checkedStudentCount} 名，待检查 ${uncheckedStudentCount} 名`,
    `已标记 ${studentsWithHighlightsCount} 名学生的阶段变化`,
    `已选择 ${classFeedbackStatusTags.length} 个班级状态标签`,
    ...(studentsAwaitingDraftCount > 0
      ? [`仍有 ${studentsAwaitingDraftCount} 名学生等待生成或补充反馈`]
      : []),
    `任务状态：${currentTaskStatus === 'confirmed' ? '已确认' : activeClassFeedbackTaskId ? '草稿中' : '待创建'}`,
    ...(selectedClassId && matchedLessonCount <= 1
      ? ['当前阶段课次较少，建议补充阶段备注帮助生成更稳定。']
      : []),
  ];
  const classFeedbackControlBar = (
    <div className="grid gap-3 sm:grid-cols-2 xl:max-w-[43rem] xl:grid-cols-4">
      <select
        value={selectedClassId ?? ''}
        onChange={(event) => void handleClassChange(event.target.value ? Number(event.target.value) : null)}
        className={workspaceFieldClass}
        disabled={classesLoading || isRefreshingTask || isSavingClassFeedback}
      >
        <option value="">选择班级</option>
        {classes.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </select>
      <select
        value={classFeedbackPeriodMode}
        onChange={(event) => setClassFeedbackPeriodMode(event.target.value as ClassFeedbackPeriodGranularity)}
        className={workspaceFieldClass}
        disabled={isRefreshingTask || isSavingClassFeedback}
      >
        <option value="daily">按日</option>
        <option value="weekly">按周</option>
        <option value="monthly">按月</option>
        <option value="stage">按阶段</option>
      </select>
      {classFeedbackPeriodMode === 'daily' ? (
        <input
          type="date"
          value={classFeedbackAnchorDate}
          onChange={(event) => setClassFeedbackAnchorDate(event.target.value)}
          className={workspaceFieldClass}
          disabled={isRefreshingTask || isSavingClassFeedback}
        />
      ) : classFeedbackPeriodMode === 'weekly' ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:col-span-2 xl:grid-cols-2">
          <select
            value={classFeedbackPeriodYear}
            onChange={(event) => setClassFeedbackPeriodYear(Number(event.target.value))}
            className={workspaceFieldClass}
            disabled={isRefreshingTask || isSavingClassFeedback}
          >
            {classFeedbackPeriodYearOptions.map((year) => (
              <option key={year} value={year}>
                {year} 年
              </option>
            ))}
          </select>
          <select
            value={classFeedbackPeriodWeek}
            onChange={(event) => setClassFeedbackPeriodWeek(Number(event.target.value))}
            className={workspaceFieldClass}
            disabled={isRefreshingTask || isSavingClassFeedback}
          >
            {Array.from({ length: 53 }, (_, index) => index + 1).map((week) => (
              <option key={week} value={week}>
                第 {week} 周
              </option>
            ))}
          </select>
        </div>
      ) : classFeedbackPeriodMode === 'monthly' ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:col-span-2 xl:grid-cols-2">
          <select
            value={classFeedbackPeriodYear}
            onChange={(event) => setClassFeedbackPeriodYear(Number(event.target.value))}
            className={workspaceFieldClass}
            disabled={isRefreshingTask || isSavingClassFeedback}
          >
            {classFeedbackPeriodYearOptions.map((year) => (
              <option key={year} value={year}>
                {year} 年
              </option>
            ))}
          </select>
          <select
            value={classFeedbackPeriodMonth}
            onChange={(event) => setClassFeedbackPeriodMonth(Number(event.target.value))}
            className={workspaceFieldClass}
            disabled={isRefreshingTask || isSavingClassFeedback}
          >
            {Array.from({ length: 12 }, (_, index) => index + 1).map((month) => (
              <option key={month} value={month}>
                {month} 月
              </option>
            ))}
          </select>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:col-span-2 xl:grid-cols-2">
          <select
            value={classFeedbackPeriodYear}
            onChange={(event) => setClassFeedbackPeriodYear(Number(event.target.value))}
            className={workspaceFieldClass}
            disabled={isRefreshingTask || isSavingClassFeedback}
          >
            {classFeedbackPeriodYearOptions.map((year) => (
              <option key={year} value={year}>
                {year} 年
              </option>
            ))}
          </select>
          <select
            value={classFeedbackStageName}
            onChange={(event) => setClassFeedbackStageName(event.target.value as ClassFeedbackStageName)}
            className={workspaceFieldClass}
            disabled={isRefreshingTask || isSavingClassFeedback}
          >
            {(['春季', '暑假', '秋季', '寒假'] as ClassFeedbackStageName[]).map((stageName) => (
              <option key={stageName} value={stageName}>
                {stageName}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
  const classFeedbackHeaderAside = (
    <div className="flex flex-col gap-3 xl:min-h-[10.5rem] xl:justify-between">
      <div className="min-w-0 rounded-2xl border border-slate-200 bg-white/85 px-4 py-3 text-left shadow-sm dark:border-white/10 dark:bg-slate-950/55">
        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">当前周期</div>
        <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">{classFeedbackPeriodPreview.label}</div>
        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          {classFeedbackPeriodPreview.startDate} 至 {classFeedbackPeriodPreview.endDate}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => void handleCreateClassFeedbackTask()}
          disabled={!selectedClassId || isSavingClassFeedback}
          className={`${workspacePrimaryButtonClass} w-full justify-center`}
        >
          <PlusCircle size={18} />
          创建反馈任务
        </button>
        <button
          type="button"
          onClick={() => void handleRefreshClassFeedbackTask()}
          disabled={!activeClassFeedbackTaskId || isRefreshingTask}
          className={`${workspaceSecondaryButtonClass} w-full justify-center`}
        >
          <RefreshCw size={18} />
          刷新任务
        </button>
      </div>
    </div>
  );

  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <ClassFeedbackGenerationWorkspace
        classNameLabel={selectedClass?.name ?? '未选择班级'}
        teacherNameLabel={teacherNameLabel}
        controlBar={classFeedbackControlBar}
        headerAside={classFeedbackHeaderAside}
        sourceSummaryItems={sourceSummaryItems}
        labelGroups={labelGroups}
        classStatusTags={classFeedbackStatusTags}
        students={sortedClassFeedbackStudents}
        classSummaryText={classFeedbackSummary}
        statusMessage={classFeedbackStatusMessage}
        draftStatusLabel={classFeedbackDraftStatusLabel}
        stageNotes={classFeedbackStageNotes}
        isGenerating={isGeneratingClassFeedback}
        isSaving={isRefreshingTask || isSavingClassFeedback}
        isConfirming={isConfirmingClassFeedback}
        onClassSummaryChange={setClassFeedbackSummary}
        onStageNoteChange={handleStageNoteChange}
        onClassStatusTagToggle={handleClassStatusTagToggle}
        onHighlightToggle={handleHighlightToggle}
        onHighlightNoteChange={handleHighlightNoteChange}
        onStudentFinalTextChange={handleStudentFinalTextChange}
        onStudentCheckedChange={handleStudentCheckedChange}
        onGenerate={handleGenerateClassFeedback}
        onSaveDraft={saveCurrentClassFeedbackDraft}
        onCopyClassSummary={handleCopyClassFeedbackSummary}
        onCopyAllStudents={handleCopyAllClassFeedbackStudents}
        onConfirm={handleConfirmClassFeedback}
      />
    </div>
  );
};

const consultationStageDisplayLabel = (stage: string) => {
  if (stage === '已加小客服微信') return '客服微信✅';
  if (stage === '已加对应教师微信') return '教师微信✅';
  if (stage === '正在沟通细节') return '沟通ing';
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
  onJump?: () => void;
}) => {
  const completedResultStage = (completedStages || []).find(isConsultationResultStage) || '';
  const resultStage = isConsultationResultStage(stage) ? stage : completedResultStage;
  const active = isConsultationResultStage(stage);
  const completed = Boolean(completedResultStage) && !blockedByCurrentProcess;
  const resultLabel = resultStage === '试听失败' ? '😢 试听未成' : '☀️ 成功进班';
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
        className={`min-w-0 flex-1 overflow-hidden text-ellipsis ${showJumpAction ? 'pl-3 pr-1' : compact ? 'px-0.5' : 'px-2'} ${editable ? 'cursor-pointer' : 'cursor-default'}`}
      >
        {compact ? (
          <>
            <span className="hidden min-[520px]:inline">{resultLabel}</span>
            <span className="min-[520px]:hidden">成/败</span>
          </>
        ) : (
          resultLabel
        )}
      </button>
      <div className={`${showJumpAction ? 'mr-10' : 'mr-0.5'} relative flex ${compact ? 'h-6 w-6' : 'h-8 w-8'} shrink-0 items-center justify-center rounded-lg bg-white/70 text-slate-500 shadow-sm dark:bg-slate-900/70 dark:text-slate-300`}>
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
      {showJumpAction ? (
        <button
          type="button"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onJump?.();
          }}
          className="absolute right-1 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg bg-white/70 text-slate-500 shadow-sm transition hover:bg-white hover:text-sky-600 dark:bg-slate-900/70 dark:text-slate-300 dark:hover:bg-slate-800"
          aria-label="跳转到结果编辑栏"
          title="跳转到结果编辑栏"
        >
          <ArrowRight size={14} />
        </button>
      ) : null}
    </div>
  );
};

const ConsultationFlowBar = ({
  stage,
  completedStages,
  mode = 'full',
  editable = false,
  showJumpActions = false,
  onStageClick,
  onStageDoubleClick,
  onResultChange,
  onResultClick,
  onResultDoubleClick,
  onStageJump,
}: {
  stage: string;
  completedStages: string[];
  mode?: 'list' | 'full';
  editable?: boolean;
  showJumpActions?: boolean;
  onStageClick?: (stage: string) => void;
  onStageDoubleClick?: (stage: string) => void;
  onResultChange?: (stage: ConsultationResultStage) => void;
  onResultClick?: () => void;
  onResultDoubleClick?: () => void;
  onStageJump?: (stage: string) => void;
}) => {
  const currentStage = stage || consultationFlowStages[0];
  const ended = isConsultationEnded(currentStage);
  const compact = mode === 'list';
  const completedSet = new Set(completedStages || []);
  if (!ended && consultationProcessStages.includes(currentStage)) {
    completedSet.add(currentStage);
  }
  const currentProcessIndex = consultationProcessStages.indexOf(currentStage);
  return (
    <div className={compact
      ? 'grid w-full min-w-0 grid-cols-1 gap-1.5 min-[520px]:grid-cols-[repeat(5,minmax(3.85rem,1fr))_minmax(4.7rem,1fr)]'
      : 'grid w-full min-w-0 grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-[repeat(5,minmax(7rem,1fr))_minmax(8rem,1fr)]'
    }>
      {consultationProcessStages.map((item) => {
        const stageIndex = consultationProcessStages.indexOf(item);
        const isCurrent = item === currentStage;
        const isAfterCurrentProcess = currentProcessIndex >= 0 && stageIndex > currentProcessIndex;
        const isCompleted = completedSet.has(item) && !isAfterCurrentProcess;
        const stageClass = isCurrent
          ? 'bg-sky-500 text-white shadow-[0_0_0_3px_rgba(14,165,233,0.20),0_8px_24px_rgba(14,165,233,0.28)]'
          : isCompleted
            ? 'border border-emerald-200 bg-emerald-50 text-emerald-700 shadow-[0_0_0_1px_rgba(16,185,129,0.16)] dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200'
            : 'bg-slate-100 text-slate-400 dark:bg-white/5 dark:text-slate-500';
        return (
          <div
            key={item}
            title={item}
            className={`flex min-w-0 items-center justify-center overflow-hidden whitespace-nowrap rounded-[10px] text-center font-extrabold leading-none transition ${compact ? 'h-8 text-[10px]' : 'h-[42px] text-xs'} ${editable ? 'hover:-translate-y-0.5' : ''} ${ended ? 'opacity-60' : ''} ${stageClass}`}
          >
            <button
              type="button"
              disabled={!editable}
              onClick={() => onStageClick?.(item)}
              onDoubleClick={() => onStageDoubleClick?.(item)}
              className={`min-w-0 flex-1 overflow-hidden text-ellipsis ${showJumpActions ? 'pl-3 pr-1' : compact ? 'px-0.5' : 'px-2'} ${editable ? 'cursor-pointer' : 'cursor-default'}`}
            >
              {compact ? (
                <>
                  <span className="hidden min-[520px]:inline">{consultationStageDisplayLabel(item)}</span>
                  <span className="min-[520px]:hidden">{consultationStageShortLabel(item)}</span>
                </>
              ) : (
                consultationStageDisplayLabel(item)
              )}
            </button>
            {showJumpActions && (
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onStageJump?.(item);
                }}
                className="mr-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/70 text-slate-500 shadow-sm transition hover:bg-white hover:text-sky-600 dark:bg-slate-900/70 dark:text-slate-300 dark:hover:bg-slate-800"
                aria-label={`跳转到${item}编辑栏`}
                title={`跳转到${item}编辑栏`}
              >
                <ArrowRight size={14} />
              </button>
            )}
          </div>
        );
      })}
      <ConsultationResultCapsule
        stage={currentStage}
        completedStages={completedStages}
        blockedByCurrentProcess={currentProcessIndex >= 0}
        compact={compact}
        editable={editable && !ended}
        onResultChange={onResultChange}
        onResultClick={onResultClick}
        onResultDoubleClick={onResultDoubleClick}
        showJumpAction={showJumpActions}
        onJump={() => onStageJump?.(isConsultationResultStage(currentStage) ? currentStage : '成功进班')}
      />
    </div>
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
  const formScrollRef = useRef<HTMLFormElement | null>(null);
  const baseInfoRef = useRef<HTMLElement | null>(null);
  const contentRef = useRef<HTMLElement | null>(null);
  const testSectionRef = useRef<HTMLDivElement | null>(null);
  const trialSectionRef = useRef<HTMLDivElement | null>(null);
  const successSectionRef = useRef<HTMLDivElement | null>(null);
  const endSectionRef = useRef<HTMLLabelElement | null>(null);

  useEffect(() => {
    if (open) {
      setForm(toConsultationFormValues(record));
      setQuickEntry('');
      setParseFeedback('');
      setConfirmRestoreOpen(false);
    }
  }, [open, mode, record]);

  if (!open) {
    return null;
  }

  const readOnly = mode === 'view';
  const stageFrozen = isConsultationEnded(form.flow_stage);
  const canEdit = hasStaffAccess(currentUser.role) || currentUser.role === 'member';
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
    if (form.flow_stage === '成功进班' && !form.success_class_id && !form.success_class_manual.trim()) {
      setParseFeedback('成功进班必须选择或填写班级。');
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
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const handleSuccessClassChange = (value: string) => {
    const classId = value ? Number(value) : null;
    setForm((current) => {
      const next = { ...current, success_class_id: classId };
      return classId ? setConsultationResultStage(next, '成功进班') : next;
    });
  };

  const handleSuccessManualChange = (value: string) => {
    setForm((current) => {
      const next = { ...current, success_class_manual: value };
      return value.trim() ? setConsultationResultStage(next, '成功进班') : next;
    });
  };

  const fieldClass = `${workspaceFieldClass} ${readOnly ? 'cursor-default' : ''}`;
  const showTestFields = form.flow_stage === '待测试' || form.test_taken || form.test_images.length > 0;
  const showTrialFields = form.flow_stage === '待试听' || form.flow_stage === '试听失败' || form.trial_taken || form.trial_time_slot || form.trial_class_id || form.trial_class_manual || form.trial_teacher || form.trial_feedback;
  const showSuccessFields = form.flow_stage === '成功进班' || form.success_class_id || form.success_class_manual;
  const showEndFields = form.flow_stage === '咨询结束' || form.end_note;

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
              {readOnly ? '记录详情只读展示，管理员和机构负责人可以在这里进入编辑。' : '先用快速录入整理信息，再确认下方结构化字段。'}
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

        <button
          type="button"
          onClick={() => formScrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' })}
          className="absolute right-4 top-20 z-20 flex h-9 w-9 items-center justify-center rounded-full border border-sky-100 bg-white text-sky-600 shadow-lg transition hover:bg-sky-50 dark:border-white/10 dark:bg-slate-800 dark:text-sky-300 dark:hover:bg-slate-700 sm:right-6 sm:top-24"
          title="回到顶部"
          aria-label="回到顶部"
        >
          <ArrowUp size={18} />
        </button>

        <form ref={formScrollRef} onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <section className={`${workspaceSoftCardClass} mb-5 space-y-4 p-4 sm:p-5`}>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h4 className="font-semibold text-slate-900 dark:text-white">咨询流程</h4>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  {readOnly ? '当前咨询的完整流程位置。' : '点击阶段框更新当前流程，未经历阶段保持灰色。'}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <ConsultationStatusLamp stage={form.flow_stage} />
                {!readOnly && (
                  <button
                    type="button"
                    onClick={() => {
                      if (stageFrozen) {
                        setConfirmRestoreOpen(true);
                        return;
                      }
                      setForm((current) => endConsultationValues(current));
                    }}
                    className="inline-flex h-10 items-center justify-center whitespace-nowrap rounded-xl bg-rose-500 px-4 text-sm font-semibold text-white shadow-[0_10px_20px_rgba(239,68,68,0.18)] transition hover:bg-rose-600"
                  >
                    {stageFrozen ? '已结束' : '咨询结束'}
                  </button>
                )}
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
            <ConsultationFlowBar
              mode="full"
              stage={form.flow_stage}
              completedStages={form.completed_stages}
              editable={!readOnly && !stageFrozen}
              showJumpActions={!readOnly}
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
            />
          </section>

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
                {parseFeedback || '解析后可确认并保存。'}
              </p>
            </section>
          )}

          <div className="grid gap-5 lg:grid-cols-2">
            <section ref={baseInfoRef} className={`${workspaceSoftCardClass} scroll-mt-6 space-y-4 p-4 sm:p-5`}>
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

            <section ref={contentRef} className={`${workspaceSoftCardClass} scroll-mt-6 space-y-4 p-4 sm:p-5`}>
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
                  <span className="text-slate-500 dark:text-slate-400">咨询详情</span>
                  <textarea
                    value={form.need_detail}
                    onChange={(e) => updateField('need_detail', e.target.value)}
                    disabled={readOnly}
                    rows={5}
                    className={`${fieldClass} resize-none`}
                    placeholder="家长本次咨询目标或诉求"
                  />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">跟进备注（内部）</span>
                  <textarea
                    value={form.follow_up_note}
                    onChange={(e) => updateField('follow_up_note', e.target.value)}
                    disabled={readOnly}
                    rows={5}
                    className={`${fieldClass} resize-none`}
                    placeholder="补充后续跟进安排或内部提醒"
                  />
                </label>
              </div>
              {(showTestFields || !readOnly) && (
                <div ref={testSectionRef} className="scroll-mt-6 rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-slate-950/70">
                  <h5 className="font-semibold text-slate-900 dark:text-white">待测试</h5>
                  <div className="mt-3 grid gap-4 md:grid-cols-2">
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">是否测试</span>
                      <select value={form.test_taken} onChange={(e) => updateField('test_taken', e.target.value)} disabled={readOnly} className={fieldClass}>
                        <option value="">未记录</option>
                        <option value="是">是</option>
                        <option value="否">否</option>
                      </select>
                    </label>
                    {!readOnly && record && (
                      <label className="space-y-2 text-sm">
                        <span className="text-slate-500 dark:text-slate-400">测试情况图片</span>
                        <input
                          type="file"
                          accept="image/png,image/jpeg,image/webp"
                          className={workspaceFieldClass}
                          onChange={async (event) => {
                            const file = event.target.files?.[0];
                            if (!file || !record) return;
                            const payload = new FormData();
                            payload.append('image', file);
                            const uploaded = await apiFetch<{ item: ConsultationRecord }>(`/api/consultations/${record.id}/test-images`, {
                              method: 'POST',
                              body: payload,
                            });
                            setForm(toConsultationFormValues(normalizeConsultationRecord(uploaded.item)));
                            event.currentTarget.value = '';
                          }}
                        />
                      </label>
                    )}
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
              {(showTrialFields || !readOnly) && (
                <div ref={trialSectionRef} className="scroll-mt-6 rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-slate-950/70">
                  <h5 className="font-semibold text-slate-900 dark:text-white">待试听</h5>
                  <div className="mt-3 grid gap-4 md:grid-cols-2">
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">是否试听</span>
                      <select value={form.trial_taken} onChange={(e) => updateField('trial_taken', e.target.value)} disabled={readOnly} className={fieldClass}>
                        <option value="">未记录</option>
                        <option value="是">是</option>
                        <option value="否">否</option>
                      </select>
                    </label>
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">试听时间段</span>
                      <input value={form.trial_time_slot} onChange={(e) => updateField('trial_time_slot', e.target.value)} disabled={readOnly} className={fieldClass} placeholder="如：周六 10:00-12:00" />
                    </label>
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">对应班课</span>
                      <select value={form.trial_class_id ?? ''} onChange={(e) => updateField('trial_class_id', e.target.value ? Number(e.target.value) : null)} disabled={readOnly} className={fieldClass}>
                        <option value="">请选择系统班级</option>
                        {classes.map((item) => (
                          <option key={item.id} value={item.id}>{item.name}</option>
                        ))}
                      </select>
                    </label>
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">若没找到对应班级，可以直接手动输入</span>
                      <input value={form.trial_class_manual} onChange={(e) => updateField('trial_class_manual', e.target.value)} disabled={readOnly} className={fieldClass} placeholder="手动输入班课" />
                    </label>
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">试听教师</span>
                      <input value={form.trial_teacher} onChange={(e) => updateField('trial_teacher', e.target.value)} disabled={readOnly} className={fieldClass} />
                    </label>
                    <label className="space-y-2 text-sm md:col-span-2">
                      <span className="text-slate-500 dark:text-slate-400">试听反馈</span>
                      <textarea value={form.trial_feedback} onChange={(e) => updateField('trial_feedback', e.target.value)} disabled={readOnly} rows={3} className={`${fieldClass} resize-none`} />
                    </label>
                  </div>
                </div>
              )}
              {(showSuccessFields || !readOnly) && (
                <div ref={successSectionRef} className="scroll-mt-6 rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-slate-950/70">
                  <h5 className="font-semibold text-slate-900 dark:text-white">成功进班</h5>
                  <div className="mt-3 grid gap-4 md:grid-cols-2">
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">进班班级</span>
                      <select value={form.success_class_id ?? ''} onChange={(e) => handleSuccessClassChange(e.target.value)} disabled={readOnly} className={fieldClass}>
                        <option value="">请选择系统班级</option>
                        {classes.map((item) => (
                          <option key={item.id} value={item.id}>{item.name}</option>
                        ))}
                      </select>
                    </label>
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">若没找到对应班级，可以直接手动输入</span>
                      <input value={form.success_class_manual} onChange={(e) => handleSuccessManualChange(e.target.value)} disabled={readOnly} className={fieldClass} />
                    </label>
                  </div>
                </div>
              )}
              {(showEndFields || !readOnly) && (
                <label ref={endSectionRef} className="scroll-mt-6 space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">咨询结束备注</span>
                  <textarea value={form.end_note} onChange={(e) => updateField('end_note', e.target.value)} disabled={readOnly} rows={3} className={`${fieldClass} resize-none`} />
                </label>
              )}
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

const ConsultationPage = ({ currentUser }: { currentUser: CurrentUser }) => {
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
          <div className="grid w-full gap-3 self-start sm:grid-cols-2 lg:w-[22rem] lg:self-auto xl:w-[24rem] xl:grid-cols-3">
            <button
              type="button"
              onClick={() => load(search).catch(() => undefined)}
              className={`${workspaceSecondaryButtonClass} w-full`}
            >
              <RefreshCw size={18} />
              刷新
            </button>
            {canManage && (
              <button
                type="button"
                onClick={openBatchModal}
                className={`${workspaceSecondaryButtonClass} w-full`}
              >
                <Cpu size={18} />
                AI 批量整理
              </button>
            )}
            <button
              type="button"
              onClick={openCreateModal}
              className={`${workspacePrimaryButtonClass} w-full`}
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

      <div className={`${workspaceCardClass} p-3 sm:p-4`}>
        <select
          value={activeFilter || ''}
          onChange={(event) => setActiveFilter((event.target.value || null) as ConsultationFilterKey | null)}
          className="block h-9 w-full rounded-xl border border-sky-100 bg-white px-3 text-xs font-bold text-slate-700 shadow-sm outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-950 dark:text-slate-200 min-[520px]:hidden"
          aria-label="咨询分类筛选"
        >
          <option value="">全部咨询</option>
          {consultationFilterGroups.map((group) => (
            <optgroup key={group.title} label={group.title}>
              {group.items.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label}（{consultationFilterCounts[item.key] || 0}）
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <div className="hidden min-w-0 items-center gap-3 overflow-hidden min-[520px]:flex">
          {consultationFilterGroups.map((group) => (
            <div key={group.title} className="flex min-w-0 shrink-0 items-center gap-2">
              <p className="shrink-0 text-[11px] font-bold text-slate-400">{group.title}</p>
              <div className="flex min-w-0 items-center gap-1.5">
                {group.items.map((item) => {
                  const active = activeFilter === item.key;
                  const count = consultationFilterCounts[item.key] || 0;
                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setActiveFilter((current) => (current === item.key ? null : item.key))}
                      className={`inline-flex h-7 shrink-0 items-center gap-1 rounded-full border px-2 text-[11px] font-bold transition ${
                        active
                          ? 'border-sky-200 bg-sky-500 text-white shadow-[0_10px_22px_rgba(14,165,233,0.18)]'
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
              {visibleRecords.map((record) => {
                const busy = isBusy && selectedRecord?.id === record.id;
                const needDetail = record.need_detail?.trim();
                const followUpNote = record.follow_up_note?.trim();
                return (
                  <article key={record.id} className={`${workspaceSoftCardClass} relative space-y-4 p-4`}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">咨询日期</p>
                        <p className="mt-2 whitespace-nowrap font-mono text-sm text-slate-600 dark:text-slate-300">{record.date || '—'}</p>
                      </div>
                      <button type="button" onClick={() => openViewModal(record)} className={`${workspaceSecondaryButtonClass} h-9 px-3 text-xs`}>
                        <Eye size={14} />
                        查看
                      </button>
                    </div>
                    <div className="pb-1">
                      <ConsultationFlowBar
                        mode="list"
                        stage={record.flow_stage}
                        completedStages={record.completed_stages}
                        editable={canEditConsultations && !busy && !isConsultationEnded(record.flow_stage)}
                        onStageClick={(stage) => handleInlineStageToggle(record, stage)}
                        onStageDoubleClick={(stage) => handleInlineStageMove(record, stage)}
                        onResultChange={(stage) => handleInlineResultChange(record, stage)}
                        onResultClick={() => handleInlineResultClick(record)}
                        onResultDoubleClick={() => handleInlineResultChange(record, '成功进班')}
                      />
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">家长微信</p>
                        <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">{record.parent_wechat_name || '—'}</p>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{getConsultationStudentMeta(record)}</p>
                      </div>
                      <div className="min-h-[120px]">
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">咨询老师</p>
                        <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">
                          {getConsultationTeacherName(record, teacherDirectory)}
                        </p>
                        {needDetail && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">咨询详情：{needDetail}</p>}
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{record.consultation_subject || '未填写咨询科目'}</p>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{getConsultationSourceLabel(record)}</p>
                        {followUpNote && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">跟进：{followUpNote}</p>}
                      </div>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="rounded-2xl border border-sky-100 bg-white/80 p-3 dark:border-white/10 dark:bg-slate-950/70">
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">录入时间</p>
                        <p className="mt-2 whitespace-nowrap text-sm text-slate-700 dark:text-slate-200">{record.created_at || '—'}</p>
                      </div>
                      <div className="rounded-2xl border border-sky-100 bg-white/80 p-3 dark:border-white/10 dark:bg-slate-950/70">
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">最后更新</p>
                        <p className="mt-2 whitespace-nowrap text-sm text-slate-700 dark:text-slate-200">{record.updated_at || '—'}</p>
                      </div>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                      {canEditConsultations && (
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
                            onClick={() => handleInlineEndConsultation(record)}
                            className="inline-flex w-full items-center justify-center gap-2 whitespace-nowrap rounded-xl bg-rose-500 px-3 py-2.5 text-xs font-extrabold text-white transition hover:bg-rose-600 disabled:cursor-not-allowed disabled:bg-rose-300"
                            disabled={busy}
                          >
                            OVER
                          </button>
                          {canManage && (
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
                          )}
                        </>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="hidden md:block">
              <div className="space-y-3 p-4">
                {visibleRecords.map((record) => {
                  const busy = isBusy && selectedRecord?.id === record.id;
                  const needDetail = record.need_detail?.trim();
                  const followUpNote = record.follow_up_note?.trim();
                  const frozen = isConsultationEnded(record.flow_stage);
                  return (
                    <article key={record.id} className="relative overflow-hidden rounded-[18px] border border-sky-100 bg-white shadow-[0_18px_45px_rgba(15,23,42,0.06)] dark:border-white/10 dark:bg-slate-950/70">
                      <button type="button" onClick={() => openViewModal(record)} className={`${workspaceSecondaryButtonClass} absolute right-5 top-4 z-10 h-9 w-[7.25rem] px-3 text-xs`}>
                        <Eye size={14} />
                        查看
                      </button>
                      <div className="grid grid-cols-[repeat(auto-fit,minmax(7.25rem,1fr))] gap-x-4 gap-y-3 border-b border-sky-50 px-5 py-4 pr-36 text-sm dark:border-white/10">
                        <div className="min-w-0">
                          <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-slate-400">日期</p>
                          <p className="mt-2 whitespace-nowrap font-mono text-slate-600 dark:text-slate-300">{record.date || '—'}</p>
                        </div>
                        <div className="min-w-0">
                          <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-slate-400">家长微信 / 学生</p>
                          <p className="mt-2 truncate font-semibold text-slate-900 dark:text-white">{record.parent_wechat_name || '—'}</p>
                          <p className="mt-1 truncate text-slate-500 dark:text-slate-400">{getConsultationStudentMeta(record)}</p>
                        </div>
                        <div className="min-w-0">
                          <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-slate-400">年级</p>
                          <p className="mt-2 whitespace-nowrap font-semibold text-slate-700 dark:text-slate-200">{record.grade || '—'}</p>
                        </div>
                        <div className="min-w-0">
                          <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-slate-400">咨询老师</p>
                          <p className="mt-2 truncate font-semibold text-slate-700 dark:text-slate-200">{getConsultationTeacherName(record, teacherDirectory)}</p>
                          {needDetail && <p className="mt-1 line-clamp-2 text-slate-500 dark:text-slate-400">咨询详情：{needDetail}</p>}
                        </div>
                        <div className="min-w-0">
                          <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-slate-400">咨询科目 / 来源</p>
                          <p className="mt-2 truncate text-slate-600 dark:text-slate-300">{record.consultation_subject || '未填写咨询科目'}</p>
                          <p className="mt-1 truncate text-slate-500 dark:text-slate-400">{getConsultationSourceLabel(record)}</p>
                          {followUpNote && <p className="mt-1 truncate text-slate-500 dark:text-slate-400">跟进：{followUpNote}</p>}
                        </div>
                        <div className="min-w-0">
                          <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-slate-400">录入 / 更新</p>
                          <p className="mt-2 whitespace-nowrap text-xs text-slate-500 dark:text-slate-400">{record.created_at || '—'}</p>
                          <p className="mt-1 whitespace-nowrap text-xs text-slate-500 dark:text-slate-400">{record.updated_at || '—'}</p>
                        </div>
                      </div>
                      <div className={`grid grid-cols-[1rem_minmax(0,1fr)_3.75rem_2.25rem] items-center gap-2 bg-slate-50/60 px-5 py-4 dark:bg-white/[0.03] ${frozen ? 'opacity-75' : ''}`}>
                        <ConsultationStatusLamp stage={record.flow_stage} />
                        <div className="min-w-0 overflow-visible">
                          <ConsultationFlowBar
                            mode="list"
                            stage={record.flow_stage}
                            completedStages={record.completed_stages}
                            editable={canEditConsultations && !busy && !frozen}
                            onStageClick={(stage) => handleInlineStageToggle(record, stage)}
                            onStageDoubleClick={(stage) => handleInlineStageMove(record, stage)}
                            onResultChange={(stage) => handleInlineResultChange(record, stage)}
                            onResultClick={() => handleInlineResultClick(record)}
                            onResultDoubleClick={() => handleInlineResultChange(record, '成功进班')}
                          />
                        </div>
                        <button
                          type="button"
                          onClick={() => handleInlineEndConsultation(record)}
                          className="inline-flex h-8 items-center justify-center whitespace-nowrap rounded-[10px] bg-rose-500 px-1.5 text-[10px] font-extrabold text-white shadow-[0_10px_20px_rgba(239,68,68,0.18)] transition hover:bg-rose-600 disabled:cursor-not-allowed disabled:bg-rose-300"
                          disabled={!canEditConsultations || busy}
                        >
                          OVER
                        </button>
                        <button
                          type="button"
                          onClick={() => openEditModal(record)}
                          className="flex h-9 w-9 items-center justify-center rounded-full bg-sky-50 text-sky-700 transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-sky-400/10 dark:text-sky-200 dark:hover:bg-sky-400/20"
                          title={frozen ? '查看结束备注' : '编辑这条咨询'}
                          disabled={!canEditConsultations || busy}
                        >
                          <Pencil size={16} />
                        </button>
                      </div>
                    </article>
                  );
                })}
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
            <div className="w-full max-w-sm rounded-3xl border border-sky-100 bg-white p-5 shadow-[0_28px_80px_rgba(15,23,42,0.2)] dark:border-white/10 dark:bg-slate-900">
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
};

interface TeacherAliasEntry {
  wecom_userid: string;
  display_name: string;
  aliases: string[];
  linked_username?: string;
}

const ApprovalPage = ({ currentUser, onOpenClassBinding }: ApprovalPageProps) => {
  const [items, setItems] = useState<RegistrationRequestItem[]>([]);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [organizations, setOrganizations] = useState<OrganizationSummaryItem[]>([]);
  const [bindingSummaryByUserId, setBindingSummaryByUserId] = useState<Record<number, MemberBindingSummary>>({});
  const [loading, setLoading] = useState(true);
  const [usersLoading, setUsersLoading] = useState(true);
  const [organizationsLoading, setOrganizationsLoading] = useState(currentUser.role === 'super_owner');
  const [bindingSummaryLoading, setBindingSummaryLoading] = useState(true);
  const [error, setError] = useState('');
  const [usersError, setUsersError] = useState('');
  const [organizationsError, setOrganizationsError] = useState('');
  const [bindingSummaryError, setBindingSummaryError] = useState('');
  const [actingId, setActingId] = useState<number | null>(null);
  const [roleSavingUserId, setRoleSavingUserId] = useState<number | null>(null);
  const [visiblePageSavingUserId, setVisiblePageSavingUserId] = useState<number | null>(null);
  const [editingDisplayNameUserId, setEditingDisplayNameUserId] = useState<number | null>(null);
  const [pendingDisplayName, setPendingDisplayName] = useState('');
  const [displayNameSavingUserId, setDisplayNameSavingUserId] = useState<number | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<number | null>(null);
  const [confirmDeleteUserId, setConfirmDeleteUserId] = useState<number | null>(null);
  const [pendingRoleByUserId, setPendingRoleByUserId] = useState<Record<number, Role>>({});
  const [collapsedUserIds, setCollapsedUserIds] = useState<Set<number>>(new Set());
  const [organizationRequests, setOrganizationRequests] = useState<OrganizationRequestItem[]>([]);
  const [organizationRequestsLoading, setOrganizationRequestsLoading] = useState(currentUser.role === 'super_owner');
  const [organizationRequestsError, setOrganizationRequestsError] = useState('');
  const [organizationActingId, setOrganizationActingId] = useState<number | null>(null);
  const [organizationInvite, setOrganizationInvite] = useState<OrganizationInviteInfo | null>(null);
  const [organizationInviteLoading, setOrganizationInviteLoading] = useState(hasOwnerAccess(currentUser.role));
  const [organizationInviteError, setOrganizationInviteError] = useState('');
  const [organizationInviteResetting, setOrganizationInviteResetting] = useState(false);
  const [deletingOrgId, setDeletingOrgId] = useState<number | null>(null);
  const [confirmDeleteOrgId, setConfirmDeleteOrgId] = useState<number | null>(null);

  // Teacher alias mapping state
  const [teacherAliases, setTeacherAliases] = useState<TeacherAliasEntry[]>([]);
  const [teacherAliasLoading, setTeacherAliasLoading] = useState(true);
  const [teacherAliasError, setTeacherAliasError] = useState('');
  const [teacherAliasModalOpen, setTeacherAliasModalOpen] = useState(false);
  const [teacherAliasModalMode, setTeacherAliasModalMode] = useState<'create' | 'edit'>('create');
  const [teacherAliasEditingEntry, setTeacherAliasEditingEntry] = useState<TeacherAliasEntry | null>(null);
  const [taFormUserId, setTaFormUserId] = useState('');
  const [taFormDisplayName, setTaFormDisplayName] = useState('');
  const [taFormAliases, setTaFormAliases] = useState('');
  const [taLinkedUsername, setTaLinkedUsername] = useState('');
  const [taSubmitting, setTaSubmitting] = useState(false);
  const [taDeletingId, setTaDeletingId] = useState<string | null>(null);
  const teacherAliasMemberOptions = users.filter((user) => user.username && user.role !== 'super_owner');
  const organizationRequestRefreshLocked = organizationRequestsLoading || organizationActingId !== null;
  const organizationInviteRefreshLocked = organizationInviteLoading || organizationInviteResetting;
  const organizationListRefreshLocked = organizationsLoading || deletingOrgId !== null;
  const approvalRefreshLocked = loading || actingId !== null;
  const memberRefreshLocked = usersLoading || bindingSummaryLoading || roleSavingUserId !== null || visiblePageSavingUserId !== null || displayNameSavingUserId !== null || deletingUserId !== null;
  const teacherAliasActionLocked = taSubmitting || taDeletingId !== null;

  const loadItems = useCallback(async () => {
    if (!hasOwnerAccess(currentUser.role)) {
      setItems([]);
      setLoading(false);
      return;
    }

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
  }, [currentUser.role]);

  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    setUsersError('');
    try {
      const data = await apiFetch<UserItem[]>('/api/admin/users');
      setUsers(data);
      setCollapsedUserIds(new Set(data.map((item) => item.id)));
    } catch (err) {
      setUsersError(err instanceof Error ? err.message : '成员权限加载失败');
    } finally {
      setUsersLoading(false);
    }
  }, []);

  const loadOrganizations = useCallback(async () => {
    if (currentUser.role !== 'super_owner') {
      setOrganizations([]);
      setOrganizationsLoading(false);
      return;
    }

    setOrganizationsLoading(true);
    setOrganizationsError('');
    try {
      const data = await apiFetch<{ items: OrganizationSummaryItem[] }>('/api/admin/organizations');
      setOrganizations(data.items);
    } catch (err) {
      setOrganizations([]);
      setOrganizationsError(err instanceof Error ? err.message : '已注册机构加载失败');
    } finally {
      setOrganizationsLoading(false);
    }
  }, [currentUser.role]);

  const loadBindingSummaries = useCallback(async () => {
    setBindingSummaryLoading(true);
    setBindingSummaryError('');
    try {
      const data = await apiFetch<{ items: MemberBindingSummary[] }>('/api/admin/member-binding-summary');
      setBindingSummaryByUserId(
        data.items.reduce<Record<number, MemberBindingSummary>>((accumulator, item) => {
          accumulator[item.user_id] = item;
          return accumulator;
        }, {}),
      );
    } catch (err) {
      setBindingSummaryByUserId({});
      setBindingSummaryError(err instanceof Error ? err.message : '教学绑定摘要加载失败');
    } finally {
      setBindingSummaryLoading(false);
    }
  }, []);

  const refreshApprovalMembers = useCallback(async () => {
    await Promise.all([
      loadUsers(),
      loadBindingSummaries(),
    ]);
  }, [loadBindingSummaries, loadUsers]);

  const loadOrganizationRequests = useCallback(async () => {
    if (currentUser.role !== 'super_owner') {
      setOrganizationRequests([]);
      setOrganizationRequestsLoading(false);
      return;
    }

    setOrganizationRequestsLoading(true);
    setOrganizationRequestsError('');
    try {
      const data = await apiFetch<{ items: OrganizationRequestItem[] }>('/api/admin/organization-requests');
      setOrganizationRequests(data.items);
    } catch (err) {
      setOrganizationRequestsError(err instanceof Error ? err.message : '机构开通审批加载失败');
    } finally {
      setOrganizationRequestsLoading(false);
    }
  }, [currentUser.role]);

  const loadOrganizationInvite = useCallback(async () => {
    if (!hasOwnerAccess(currentUser.role)) {
      setOrganizationInvite(null);
      setOrganizationInviteLoading(false);
      return;
    }

    setOrganizationInviteLoading(true);
    setOrganizationInviteError('');
    try {
      const data = await apiFetch<OrganizationInviteInfo>('/api/organization/invite');
      setOrganizationInvite(data);
    } catch (err) {
      setOrganizationInvite(null);
      setOrganizationInviteError(err instanceof Error ? err.message : '机构邀请设置加载失败');
    } finally {
      setOrganizationInviteLoading(false);
    }
  }, [currentUser.role]);

  const loadTeacherAliases = useCallback(async () => {
    if (!hasOwnerAccess(currentUser.role)) {
      setTeacherAliases([]);
      setTeacherAliasLoading(false);
      return;
    }

    setTeacherAliasLoading(true);
    setTeacherAliasError('');
    try {
      const data = await apiFetch<TeacherAliasEntry[]>('/api/teacher-aliases');
      setTeacherAliases(data);
    } catch (err) {
      setTeacherAliasError(err instanceof Error ? err.message : '讲师映射加载失败');
    } finally {
      setTeacherAliasLoading(false);
    }
  }, [currentUser.role]);

  const openTeacherAliasCreate = () => {
    setTeacherAliasEditingEntry(null);
    setTaFormUserId('');
    setTaFormDisplayName('');
    setTaFormAliases('');
    setTaLinkedUsername('');
    setTeacherAliasModalMode('create');
    setTeacherAliasModalOpen(true);
  };

  const openTeacherAliasEdit = (entry: TeacherAliasEntry) => {
    setTeacherAliasEditingEntry(entry);
    setTaFormUserId(entry.wecom_userid);
    setTaFormDisplayName(entry.display_name);
    setTaFormAliases(entry.aliases.slice(1).join(', '));
    setTaLinkedUsername(entry.linked_username || '');
    setTeacherAliasModalMode('edit');
    setTeacherAliasModalOpen(true);
  };

  const handleTeacherAliasSubmit = async () => {
    setTaSubmitting(true);
    setTeacherAliasError('');
    try {
      const aliases = taFormAliases.split(/[,，]/).map(s => s.trim()).filter(Boolean);
      if (teacherAliasModalMode === 'create') {
        await apiFetch('/api/teacher-aliases', {
          method: 'POST',
          body: JSON.stringify({
            wecom_userid: taFormUserId.trim(),
            display_name: taFormDisplayName.trim(),
            linked_username: taLinkedUsername.trim(),
            aliases,
          }),
        });
      } else if (teacherAliasEditingEntry) {
        await apiFetch(`/api/teacher-aliases/${encodeURIComponent(teacherAliasEditingEntry.wecom_userid)}`, {
          method: 'PUT',
          body: JSON.stringify({
            display_name: taFormDisplayName.trim(),
            linked_username: taLinkedUsername.trim(),
            aliases,
          }),
        });
      }
      setTeacherAliasModalOpen(false);
      await loadTeacherAliases();
    } catch (err) {
      setTeacherAliasError(err instanceof Error ? err.message : '操作失败');
    } finally {
      setTaSubmitting(false);
    }
  };

  const handleTeacherAliasDelete = async (wecom_userid: string) => {
    if (!window.confirm(`确认删除 ${wecom_userid} 的映射？`)) return;
    setTaDeletingId(wecom_userid);
    try {
      await apiFetch(`/api/teacher-aliases/${encodeURIComponent(wecom_userid)}`, { method: 'DELETE' });
      await loadTeacherAliases();
    } catch (err) {
      setTeacherAliasError(err instanceof Error ? err.message : '删除失败');
    } finally {
      setTaDeletingId(null);
    }
  };

  useEffect(() => {
    loadItems().catch(() => undefined);
    loadUsers().catch(() => undefined);
    loadOrganizations().catch(() => undefined);
    loadBindingSummaries().catch(() => undefined);
    loadOrganizationRequests().catch(() => undefined);
    loadOrganizationInvite().catch(() => undefined);
    loadTeacherAliases().catch(() => undefined);
  }, [loadItems, loadUsers, loadOrganizations, loadBindingSummaries, loadOrganizationInvite, loadOrganizationRequests, loadTeacherAliases]);

  useEffect(() => {
    const handleWindowFocus = () => {
      refreshApprovalMembers().catch(() => undefined);
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        refreshApprovalMembers().catch(() => undefined);
      }
    };

    window.addEventListener('focus', handleWindowFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      window.removeEventListener('focus', handleWindowFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [refreshApprovalMembers]);

  const handleDecision = async (requestId: number, action: 'approve' | 'reject') => {
    setActingId(requestId);
    setError('');
    try {
      await apiFetch(`/api/admin/registration-requests/${requestId}/${action}`, {
        method: 'POST',
      });
      setItems((current) => current.filter((item) => item.id !== requestId));
      refreshApprovalMembers().catch(() => undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : '审批操作失败');
    } finally {
      setActingId(null);
    }
  };

  const handleOrganizationRequestDecision = async (requestId: number, action: 'approve' | 'reject') => {
    setOrganizationActingId(requestId);
    setOrganizationRequestsError('');
    try {
      await apiFetch(`/api/admin/organization-requests/${requestId}/${action}`, {
        method: 'POST',
      });
      setOrganizationRequests((current) => current.filter((item) => item.id !== requestId));
      refreshApprovalMembers().catch(() => undefined);
      loadOrganizations().catch(() => undefined);
    } catch (err) {
      setOrganizationRequestsError(err instanceof Error ? err.message : '机构开通审批处理失败');
    } finally {
      setOrganizationActingId(null);
    }
  };

  const handleDeleteOrganization = async (orgId: number) => {
    setDeletingOrgId(orgId);
    setOrganizationsError('');
    try {
      await apiFetch(`/api/admin/organizations/${orgId}`, { method: 'DELETE' });
      setOrganizations((current) => current.filter((o) => o.id !== orgId));
      setConfirmDeleteOrgId(null);
    } catch (err) {
      setOrganizationsError(err instanceof Error ? err.message : '删除机构失败');
    } finally {
      setDeletingOrgId(null);
    }
  };

  const handleResetOrganizationInvite = async () => {    setOrganizationInviteResetting(true);
    setOrganizationInviteError('');
    try {
      const data = await apiFetch<OrganizationInviteInfo>('/api/organization/invite/reset', {
        method: 'POST',
      });
      setOrganizationInvite(data);
    } catch (err) {
      setOrganizationInviteError(err instanceof Error ? err.message : '机构邀请重置失败');
    } finally {
      setOrganizationInviteResetting(false);
    }
  };

  const handleRoleUpdate = async (userId: number, currentRole: Role, nextRole: Role) => {
    if (currentRole === nextRole) {
      return;
    }

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

  const handleToggleVisiblePage = async (targetUser: UserItem, page: Page) => {
    if (visiblePageSavingUserId !== null || targetUser.role === 'super_owner') {
      return;
    }

    const currentVisiblePages = getVisibleWorkspacePages(targetUser);
    const nextVisiblePageSet = new Set(currentVisiblePages);
    if (nextVisiblePageSet.has(page)) {
      nextVisiblePageSet.delete(page);
    } else {
      nextVisiblePageSet.add(page);
    }
    const nextVisiblePages = configurableWorkspacePages
      .map((item) => item.id)
      .filter((item) => nextVisiblePageSet.has(item));

    setVisiblePageSavingUserId(targetUser.id);
    setUsersError('');
    setUsers((current) => current.map((user) => (user.id === targetUser.id ? { ...user, visible_pages: nextVisiblePages } : user)));

    try {
      const response = await apiFetch<{ ok: boolean; user: UserItem }>(`/api/admin/users/${targetUser.id}/visible-pages`, {
        method: 'PUT',
        body: JSON.stringify({ visible_pages: nextVisiblePages }),
      });
      setUsers((current) => current.map((user) => (user.id === targetUser.id ? { ...user, ...response.user } : user)));
    } catch (err) {
      setUsers((current) => current.map((user) => (user.id === targetUser.id ? { ...user, visible_pages: currentVisiblePages } : user)));
      setUsersError(err instanceof Error ? err.message : '可见页面更新失败');
    } finally {
      setVisiblePageSavingUserId(null);
    }
  };

  const getAssignableRoles = (targetUser: UserItem): Role[] => {
    if (targetUser.id === currentUser.id) {
      return [];
    }
    if (currentUser.role === 'super_owner') {
      if (targetUser.role === 'super_owner') {
        return [];
      }
      return ['super_owner', 'owner', 'admin', 'member'];
    }
    if (currentUser.role === 'owner') {
      if (targetUser.role === 'admin' || targetUser.role === 'member') {
        return ['admin', 'member'];
      }
      return [];
    }
    return [];
  };

  const handleStartDisplayNameEdit = (userId: number, currentName: string) => {
    setEditingDisplayNameUserId(userId);
    setPendingDisplayName(currentName);
    setUsersError('');
  };

  const handleCancelDisplayNameEdit = () => {
    setEditingDisplayNameUserId(null);
    setPendingDisplayName('');
  };

  const handleSaveDisplayName = async (userId: number) => {
    const nextDisplayName = pendingDisplayName.trim();
    if (!nextDisplayName) {
      setUsersError('姓名不能为空');
      return;
    }

    const currentName = users.find((user) => user.id === userId)?.name ?? '';
    setDisplayNameSavingUserId(userId);
    setUsersError('');
    setUsers((current) => current.map((user) => (user.id === userId ? { ...user, name: nextDisplayName } : user)));

    try {
      await apiFetch(`/api/admin/users/${userId}/profile`, {
        method: 'PUT',
        body: JSON.stringify({ display_name: nextDisplayName }),
      });
      setEditingDisplayNameUserId(null);
      setPendingDisplayName('');
    } catch (err) {
      setUsers((current) => current.map((user) => (user.id === userId ? { ...user, name: currentName } : user)));
      setUsersError(err instanceof Error ? err.message : '成员姓名更新失败');
    } finally {
      setDisplayNameSavingUserId(null);
    }
  };

  const handleDeleteUser = async (userId: number) => {
    setDeletingUserId(userId);
    setUsersError('');
    try {
      await apiFetch(`/api/admin/users/${userId}`, { method: 'DELETE' });
      setUsers((current) => current.filter((user) => user.id !== userId));
      setBindingSummaryByUserId((current) => {
        const next = { ...current };
        delete next[userId];
        return next;
      });
      if (editingDisplayNameUserId === userId) {
        setEditingDisplayNameUserId(null);
        setPendingDisplayName('');
      }
      setConfirmDeleteUserId(null);
    } catch (err) {
      setUsersError(err instanceof Error ? err.message : '成员删除失败');
    } finally {
      setDeletingUserId(null);
    }
  };

  return (
    <div className={`${workspacePageClass} space-y-8`}>
      {currentUser.role === 'super_owner' && (
        <section className={`${workspaceCardClass} p-6`}>
          <div className="flex flex-col gap-4 border-b border-sky-100/80 pb-5 sm:flex-row sm:items-start sm:justify-between dark:border-white/10">
            <div>
              <h4 className="text-xl font-semibold text-slate-900 dark:text-white">机构开通审批</h4>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                审核新机构的开通申请。通过后，申请人会自动成为该机构的首位管理员，并生成当前唯一有效的邀请码与邀请链接。
              </p>
            </div>
            <button
              onClick={() => loadOrganizationRequests().catch(() => undefined)}
              disabled={organizationRequestRefreshLocked}
              className={workspaceSecondaryButtonClass}
            >
              刷新机构申请
            </button>
          </div>

          {organizationRequestsError && (
            <div className="mt-5 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {organizationRequestsError}
            </div>
          )}

          {organizationRequestsLoading ? (
            <div className="py-10 text-center text-slate-500 dark:text-slate-400">正在加载机构开通申请...</div>
          ) : organizationRequests.length === 0 ? (
            <div className="mt-5 rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
              当前没有待处理的机构开通申请。
            </div>
          ) : (
            <div className="mt-5 space-y-4">
              {organizationRequests.map((item) => {
                const busy = organizationActingId === item.id;
                return (
                  <div key={item.id} className={`${workspaceSoftCardClass} p-5`}>
                    <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-lg font-semibold text-slate-900 dark:text-white">{item.organization_name}</span>
                          <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">
                            待审批
                          </span>
                        </div>
                        <div className="grid grid-cols-1 gap-3 text-sm text-slate-500 md:grid-cols-3 dark:text-slate-400">
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">首位管理员账号</p>
                            <p className="mt-1 text-slate-700 dark:text-slate-200">{item.username}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">负责人姓名</p>
                            <p className="mt-1 text-slate-700 dark:text-slate-200">{item.display_name}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">申请时间</p>
                            <p className="mt-1 text-slate-700 dark:text-slate-200">{item.created_at}</p>
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-3">
                        <button
                          onClick={() => handleOrganizationRequestDecision(item.id, 'reject')}
                          disabled={busy}
                          className={workspaceSecondaryButtonClass}
                        >
                          驳回
                        </button>
                        <button
                          onClick={() => handleOrganizationRequestDecision(item.id, 'approve')}
                          disabled={busy}
                          className={workspacePrimaryButtonClass}
                        >
                          {busy ? '处理中...' : '通过并开通机构'}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {hasOwnerAccess(currentUser.role) && (
        <section className={`${workspaceCardClass} p-6`}>
          <div className="flex flex-col gap-4 border-b border-sky-100/80 pb-5 sm:flex-row sm:items-start sm:justify-between dark:border-white/10">
            <div>
              <h4 className="text-xl font-semibold text-slate-900 dark:text-white">机构邀请设置</h4>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                当前机构仅保留一个有效邀请码。重置后，旧邀请码和旧邀请链接会立刻失效。
              </p>
            </div>
            <button
              onClick={() => loadOrganizationInvite().catch(() => undefined)}
              disabled={organizationInviteRefreshLocked}
              className={workspaceSecondaryButtonClass}
            >
              刷新邀请信息
            </button>
          </div>

          {organizationInviteError && (
            <div className="mt-5 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {organizationInviteError}
            </div>
          )}

          {organizationInviteLoading ? (
            <div className="py-10 text-center text-slate-500 dark:text-slate-400">正在加载邀请码...</div>
          ) : organizationInvite ? (
            <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
              <div className={`${workspaceSoftCardClass} grid gap-4 p-5 md:grid-cols-3`}>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">机构</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">{organizationInvite.organization_name}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">当前邀请码</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">{organizationInvite.invite_code}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">邀请链接</p>
                  <p className="mt-1 break-all text-sm text-slate-700 dark:text-slate-200">{organizationInvite.invite_link}</p>
                </div>
              </div>
              <button
                onClick={() => void handleResetOrganizationInvite()}
                disabled={organizationInviteRefreshLocked}
                className={workspacePrimaryButtonClass}
              >
                {organizationInviteResetting ? '重置中...' : '重置邀请码'}
              </button>
            </div>
          ) : (
            <div className="mt-5 rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
              当前没有可用的邀请码信息。
            </div>
          )}
        </section>
      )}

      {currentUser.role === 'super_owner' && (
        <section className={`${workspaceCardClass} p-6`}>
          <div className="flex flex-col gap-4 border-b border-sky-100/80 pb-5 sm:flex-row sm:items-start sm:justify-between dark:border-white/10">
            <div>
              <h4 className="text-xl font-semibold text-slate-900 dark:text-white">已注册机构</h4>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                查看已经开通的机构规模，快速确认负责人、成员和班级是否已正常落库。
              </p>
            </div>
            <button
              onClick={() => loadOrganizations().catch(() => undefined)}
              disabled={organizationListRefreshLocked}
              className={workspaceSecondaryButtonClass}
            >
              刷新机构列表
            </button>
          </div>

          {organizationsError && (
            <div className="mt-5 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {organizationsError}
            </div>
          )}

          {organizationsLoading ? (
            <div className="py-10 text-center text-slate-500 dark:text-slate-400">正在加载已注册机构...</div>
          ) : organizations.length === 0 ? (
            <div className="mt-5 rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
              当前还没有已开通机构。
            </div>
          ) : (
            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {organizations.map((organization) => (
                <div key={organization.id} className={`${workspaceSoftCardClass} p-5`}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h5 className="text-lg font-semibold text-slate-900 dark:text-white">{organization.name}</h5>
                      <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-400">开通时间</p>
                      <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{organization.created_at}</p>
                    </div>
                    <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">
                      已开通
                    </span>
                  </div>
                  <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-2xl border border-sky-100 bg-white/70 p-3 dark:border-white/10 dark:bg-slate-950/70">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">成员</p>
                      <p className="mt-2 text-xl font-semibold text-slate-900 dark:text-white">{organization.member_count}</p>
                    </div>
                    <div className="rounded-2xl border border-sky-100 bg-white/70 p-3 dark:border-white/10 dark:bg-slate-950/70">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">负责人</p>
                      <p className="mt-2 text-xl font-semibold text-slate-900 dark:text-white">{organization.owner_count}</p>
                    </div>
                    <div className="rounded-2xl border border-sky-100 bg-white/70 p-3 dark:border-white/10 dark:bg-slate-950/70">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">班级</p>
                      <p className="mt-2 text-xl font-semibold text-slate-900 dark:text-white">{organization.class_count}</p>
                    </div>
                    <div className="rounded-2xl border border-sky-100 bg-white/70 p-3 dark:border-white/10 dark:bg-slate-950/70">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">课程记录</p>
                      <p className="mt-2 text-xl font-semibold text-slate-900 dark:text-white">{organization.lesson_count}</p>
                    </div>
                  </div>
                  <div className="mt-4 border-t border-rose-100/60 pt-4 dark:border-rose-500/10">
                    {confirmDeleteOrgId === organization.id ? (
                      <div className="flex flex-col gap-2">
                        <p className="text-xs text-rose-600 dark:text-rose-400">确认删除「{organization.name}」？此操作将清空该机构下所有账号和数据，不可恢复。</p>
                        <div className="flex gap-2">
                          <button
                            onClick={() => void handleDeleteOrganization(organization.id)}
                            disabled={deletingOrgId === organization.id}
                            className="flex-1 rounded-xl border border-rose-300 bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-700 transition hover:bg-rose-100 disabled:opacity-50 dark:border-rose-500/30 dark:bg-rose-900/20 dark:text-rose-300"
                          >
                            {deletingOrgId === organization.id ? '删除中...' : '确认删除'}
                          </button>
                          <button
                            onClick={() => setConfirmDeleteOrgId(null)}
                            disabled={deletingOrgId === organization.id}
                            className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-50 dark:border-white/10 dark:bg-slate-800 dark:text-slate-300"
                          >
                            取消
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmDeleteOrgId(organization.id)}
                        className="w-full rounded-xl border border-rose-200 bg-rose-50/60 px-3 py-1.5 text-xs font-medium text-rose-600 transition hover:bg-rose-100 dark:border-rose-500/20 dark:bg-rose-900/10 dark:text-rose-400 dark:hover:bg-rose-900/30"
                      >
                        删除机构
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {hasOwnerAccess(currentUser.role) && (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,320px)_minmax(0,1fr)] gap-6">
          <section className={`${workspaceCardClass} space-y-5 p-6`}>
            <div>
              <p className="text-sm uppercase tracking-[0.25em] text-sky-600">账号审批与权限</p>
              <h3 className="mt-3 text-2xl font-bold text-slate-900 dark:text-white">账号审批</h3>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">超级管理员和机构负责人都可以审核注册申请，并为用户开通后台访问权限。</p>
            </div>
            <div className={`${workspaceSoftCardClass} p-5`}>
              <p className="text-xs uppercase tracking-[0.25em] text-sky-600">当前账号</p>
              <p className="mt-3 text-xl font-semibold text-slate-900 dark:text-white">{currentUser.display_name}</p>
              <div className="mt-4 space-y-2 text-sm">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-slate-500 dark:text-slate-400">账号</span>
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
                disabled={approvalRefreshLocked}
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
                              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">账号</p>
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
      )}

      {hasStaffAccess(currentUser.role) && (
        <section className={`${workspaceCardClass} p-6`}>
          <div className="flex flex-col gap-3 border-b border-sky-100/80 pb-5 sm:flex-row sm:items-start sm:justify-between dark:border-white/10">
            <div>
              <h4 className="text-xl font-semibold text-slate-900 dark:text-white">成员权限</h4>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                超级管理员可以设置或撤销机构负责人；机构负责人只可切换管理员与普通成员权限；管理员可调整成员可见页面。
              </p>
            </div>
            <button
              onClick={() => Promise.all([loadUsers(), loadBindingSummaries()]).catch(() => undefined)}
              disabled={memberRefreshLocked}
              className={workspaceSecondaryButtonClass}
            >
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
            <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {users.map((user) => {
                const busy = roleSavingUserId === user.id;
                const displayNameBusy = displayNameSavingUserId === user.id;
                const visiblePageSaving = visiblePageSavingUserId === user.id;
                const editingName = editingDisplayNameUserId === user.id;
                const deleting = deletingUserId === user.id;
                const bindingSummary = bindingSummaryByUserId[user.id];
                const visiblePages = getVisibleWorkspacePages(user);
                const responsibleClasses = bindingSummary?.responsible_classes ?? [];
                const bindingStatus = bindingSummary?.mapping_summary.status ?? 'incomplete';
                const visibleClassNames = responsibleClasses.slice(0, 3).map((item) => item.name);
                const hiddenClassCount = Math.max(responsibleClasses.length - visibleClassNames.length, 0);
                const unresolvedCount = (bindingSummary?.mapping_summary.needs_review_count ?? 0)
                  + (bindingSummary?.mapping_summary.unmapped_count ?? 0)
                  + (bindingSummary?.mapping_summary.ambiguous_count ?? 0);
                const assignableRoles = getAssignableRoles(user);
                const roleFixed = assignableRoles.length === 0;
                const canDeleteUser = currentUser.role !== 'admin'
                  && user.role !== 'super_owner'
                  && user.id !== currentUser.id
                  && (canManageOwnerRole(currentUser.role) || user.role !== 'owner');
                const canEditVisiblePages = user.role !== 'super_owner'
                  && user.id !== currentUser.id
                  && (currentUser.role === 'super_owner'
                    || (currentUser.role === 'owner' && (user.role === 'admin' || user.role === 'member'))
                    || (currentUser.role === 'admin' && user.role === 'member'));
                const isCollapsed = collapsedUserIds.has(user.id);
                const toggleCollapse = () => setCollapsedUserIds((prev) => {
                  const next = new Set(prev);
                  if (next.has(user.id)) next.delete(user.id); else next.add(user.id);
                  return next;
                });
                return (
                  <div key={user.id} className={`${workspaceSoftCardClass} overflow-hidden`}>
                    <button
                      type="button"
                      onClick={toggleCollapse}
                      className="flex w-full items-center justify-between gap-3 p-4 text-left"
                    >
                      <div className="flex min-w-0 flex-col gap-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="truncate text-base font-semibold text-slate-900 dark:text-white">{user.name}</span>
                          <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${getRoleBadgeClass(user.role)}`}>
                            {getRoleLabel(user.role)}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">{user.org}</p>
                        {currentUser.role === 'super_owner' && (
                          <p className="text-xs text-slate-400 dark:text-slate-500">
                            <span className="font-mono">{user.username}</span>
                            {user.last_login
                              ? <span className="ml-2 text-slate-400">上次登录 {user.last_login}</span>
                              : <span className="ml-2 text-slate-300 dark:text-slate-600">未登录过</span>}
                          </p>
                        )}
                      </div>
                      <ChevronDown
                        size={16}
                        className={`shrink-0 text-slate-400 transition-transform duration-200 ${isCollapsed ? '' : 'rotate-180'}`}
                      />
                    </button>
                    {!isCollapsed && (
                      <div className="border-t border-sky-100/80 p-4 dark:border-white/10">
                        <div className="space-y-3">
                          {editingName ? (
                            <div className="flex flex-wrap items-center gap-2">
                              <input
                                value={pendingDisplayName}
                                onChange={(event) => setPendingDisplayName(event.target.value)}
                                className="min-w-[180px] rounded-xl border border-sky-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-950/70 dark:text-white dark:focus:border-sky-400 dark:focus:ring-sky-500/20"
                                placeholder="输入成员姓名"
                              />
                              <button
                                type="button"
                                onClick={() => void handleSaveDisplayName(user.id)}
                                disabled={displayNameBusy}
                                className={workspacePrimaryButtonClass}
                              >
                                {displayNameBusy ? '保存中...' : '保存姓名'}
                              </button>
                              <button
                                type="button"
                                onClick={handleCancelDisplayNameEdit}
                                disabled={displayNameBusy}
                                className={workspaceSecondaryButtonClass}
                              >
                                取消
                              </button>
                            </div>
                          ) : null}
                          <div className="rounded-2xl border border-sky-100 bg-white/80 p-3 dark:border-white/10 dark:bg-slate-950/70">
                            <div className="flex items-center justify-between gap-3">
                              <h5 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">教学绑定</h5>
                              <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${getMemberBindingStatusBadgeClass(bindingStatus)}`}>
                                {getMemberBindingStatusLabel(bindingStatus)}
                              </span>
                            </div>
                            <div className="mt-3 space-y-2">
                              <div className="flex items-center justify-between text-xs">
                                <span className="text-slate-400">小程序老师</span>
                                <span className="text-slate-700 dark:text-slate-200">
                                  {bindingSummaryLoading && !bindingSummary ? '加载中...' : bindingSummary?.mini_teacher_bound ? '已绑定' : '未绑定'}
                                </span>
                              </div>
                              <div className="flex items-center justify-between text-xs">
                                <span className="text-slate-400">负责班级</span>
                                <span className="text-slate-700 dark:text-slate-200">{responsibleClasses.length} 个班级</span>
                              </div>
                              {user.role !== 'super_owner' && canOpenWorkspacePage(currentUser, 'classes') && (
                                <div className="flex items-center justify-between gap-3 text-xs">
                                  <span className="text-slate-400">绑定班级</span>
                                  <button
                                    type="button"
                                    onClick={() => onOpenClassBinding({ teacherUserId: user.id, teacherName: user.name })}
                                    className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-white px-2.5 py-1 font-semibold text-sky-700 transition hover:bg-sky-50 dark:border-sky-500/30 dark:bg-slate-950/70 dark:text-sky-300 dark:hover:bg-sky-500/10"
                                  >
                                    去绑定班级
                                    <ArrowRight size={12} />
                                  </button>
                                </div>
                              )}
                              {visibleClassNames.length > 0 && (
                                <p className="text-xs text-slate-500 dark:text-slate-400">
                                  {visibleClassNames.join('、')}{hiddenClassCount > 0 ? ` +${hiddenClassCount}` : ''}
                                </p>
                              )}
                              <div className="flex items-center justify-between text-xs">
                                <span className="text-slate-400">映射状态</span>
                                <span className="text-slate-700 dark:text-slate-200">
                                  {bindingSummary
                                    ? `已映射 ${bindingSummary.mapping_summary.mapped_count} / 未完成 ${unresolvedCount}`
                                    : bindingSummaryLoading
                                      ? '加载中...'
                                      : '—'}
                                </span>
                              </div>
                            </div>
                            {bindingSummaryError && !bindingSummary && (
                              <p className="mt-2 text-xs text-rose-500 dark:text-rose-300">教学绑定摘要加载失败</p>
                            )}
                          </div>
                          <div className="rounded-2xl border border-sky-100 bg-white/80 p-3 dark:border-white/10 dark:bg-slate-950/70">
                            <div className="flex items-center justify-between gap-3">
                              <h5 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">可见页面</h5>
                              {visiblePageSaving && (
                                <span className="text-xs font-semibold text-sky-600 dark:text-sky-300">保存中...</span>
                              )}
                            </div>
                            <div className="mt-3 grid gap-2 sm:grid-cols-2">
                              {configurableWorkspacePages.map((pageOption) => {
                                const checked = visiblePages.includes(pageOption.id);
                                return (
                                  <button
                                    type="button"
                                    key={`${user.id}-visible-${pageOption.id}`}
                                    onClick={() => void handleToggleVisiblePage(user, pageOption.id)}
                                    disabled={!canEditVisiblePages || visiblePageSaving}
                                    className={cn(
                                      'rounded-xl border px-3 py-2 text-left text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-60',
                                      checked
                                        ? 'border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-400/40 dark:bg-sky-500/10 dark:text-sky-200'
                                        : 'border-slate-200 bg-white text-slate-500 hover:border-sky-200 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10',
                                    )}
                                  >
                                    {pageOption.label}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                        <div className="mt-3 space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            {currentUser.role !== 'admin' && user.role !== 'super_owner' && (
                              <button
                                type="button"
                                onClick={() => handleStartDisplayNameEdit(user.id, user.name)}
                                disabled={displayNameBusy || busy}
                                className={workspaceSecondaryButtonClass}
                              >
                                编辑姓名
                              </button>
                            )}
                            {canDeleteUser && (
                              confirmDeleteUserId === user.id ? (
                                <>
                                  <button
                                    type="button"
                                    onClick={() => void handleDeleteUser(user.id)}
                                    disabled={deleting || busy || displayNameBusy}
                                    className={`${workspaceSecondaryButtonClass} border-rose-300 bg-rose-50 text-rose-700 hover:bg-rose-100 dark:border-rose-500/30 dark:bg-rose-900/20 dark:text-rose-300 dark:hover:bg-rose-900/30`}
                                  >
                                    {deleting ? '删除中...' : '确认删除'}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setConfirmDeleteUserId(null)}
                                    disabled={deleting}
                                    className={workspaceSecondaryButtonClass}
                                  >
                                    取消
                                  </button>
                                </>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => setConfirmDeleteUserId(user.id)}
                                  disabled={busy || displayNameBusy}
                                  className={`${workspaceSecondaryButtonClass} border-rose-200 bg-rose-50/70 text-rose-600 hover:bg-rose-100 dark:border-rose-500/30 dark:bg-rose-900/20 dark:text-rose-300 dark:hover:bg-rose-900/30`}
                                >
                                  删除账号
                                </button>
                              )
                            )}
                          </div>
                          {roleFixed ? (
                            <span className="text-sm text-slate-500 dark:text-slate-400">
                              {user.id === currentUser.id
                                ? '当前登录账号不可在此处调整权限'
                                : user.role === 'super_owner'
                                  ? '超级管理员权限固定，不可调整'
                                  : '该成员权限不可调整'}
                            </span>
                          ) : (
                            <div className="flex items-center gap-2">
                              <select
                                value={pendingRoleByUserId[user.id] ?? user.role}
                                onChange={(event) => {
                                  setPendingRoleByUserId((current) => ({
                                    ...current,
                                    [user.id]: event.target.value as Role,
                                  }));
                                }}
                                disabled={busy}
                                className={`${workspaceFieldClass} min-w-0 flex-1`}
                              >
                                {assignableRoles.map((roleOption) => (
                                  <option key={`${user.id}-role-${roleOption}`} value={roleOption}>
                                    {getRoleLabel(roleOption)}
                                  </option>
                                ))}
                              </select>
                              <button
                                type="button"
                                onClick={() => {
                                  const nextRole = pendingRoleByUserId[user.id] ?? user.role;
                                  void handleRoleUpdate(user.id, user.role, nextRole);
                                }}
                                disabled={busy || (pendingRoleByUserId[user.id] ?? user.role) === user.role}
                                className={workspacePrimaryButtonClass}
                              >
                                {busy ? '保存中...' : '应用权限'}
                              </button>
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
      )}

      {/* Teacher Alias Mapping Section */}
      {hasOwnerAccess(currentUser.role) && (
        <section className={`${workspaceCardClass} mt-6 p-6`}>
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h4 className="text-xl font-semibold text-slate-900 dark:text-white">讲师映射</h4>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">管理企业微信 ID 到讲师中文名的映射（咨询助手自动识别用）</p>
          </div>
          <button
            type="button"
            className={workspacePrimaryButtonClass}
            disabled={teacherAliasActionLocked}
            onClick={openTeacherAliasCreate}
          >
            <PlusCircle className="h-4 w-4" />
            添加
          </button>
        </div>

        {teacherAliasError && <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300">{teacherAliasError}</div>}

        {teacherAliasLoading ? (
          <div className="flex items-center justify-center py-10 text-slate-400">
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            加载中...
          </div>
        ) : teacherAliases.length === 0 ? (
          <div className="py-10 text-center text-slate-400">暂无映射，点击「添加」创建</div>
        ) : (
          <div className={`${workspaceSoftCardClass} overflow-hidden`}>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-sky-100 dark:border-white/10">
                  <th className="px-5 py-3.5 font-semibold text-slate-500 dark:text-slate-400">企微 ID</th>
                  <th className="px-5 py-3.5 font-semibold text-slate-500 dark:text-slate-400">中文名</th>
                  <th className="px-5 py-3.5 font-semibold text-slate-500 dark:text-slate-400">网站成员</th>
                  <th className="px-5 py-3.5 font-semibold text-slate-500 dark:text-slate-400">别名</th>
                  <th className="px-5 py-3.5 text-right font-semibold text-slate-500 dark:text-slate-400">操作</th>
                </tr>
              </thead>
              <tbody>
                {teacherAliases.map((entry) => {
                  const linkedMember = teacherAliasMemberOptions.find((user) => user.username === entry.linked_username);
                  return (
                    <tr key={entry.wecom_userid} className="border-b border-sky-50 last:border-b-0 dark:border-white/5">
                      <td className="px-5 py-3 font-mono text-xs text-slate-600 dark:text-slate-300">{entry.wecom_userid}</td>
                      <td className="px-5 py-3 font-medium text-slate-800 dark:text-slate-100">{entry.display_name}</td>
                      <td className="px-5 py-3 text-slate-500 dark:text-slate-400">
                        {linkedMember ? `${linkedMember.name}（${linkedMember.username}）` : entry.linked_username || '—'}
                      </td>
                      <td className="px-5 py-3 text-slate-500 dark:text-slate-400">{entry.aliases.slice(1).join('、') || '—'}</td>
                      <td className="px-5 py-3 text-right">
                        <button
                          type="button"
                          className="mr-2 text-sky-600 hover:text-sky-500 disabled:opacity-40 dark:text-sky-400"
                          disabled={teacherAliasActionLocked}
                          onClick={() => openTeacherAliasEdit(entry)}
                        >
                          <Pencil className="inline h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          className="text-red-500 hover:text-red-400 disabled:opacity-40"
                          disabled={teacherAliasActionLocked || taDeletingId === entry.wecom_userid}
                          onClick={() => handleTeacherAliasDelete(entry.wecom_userid)}
                        >
                          <Trash2 className="inline h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        </section>
      )}

      <AnimatePresence>
        {teacherAliasModalOpen && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setTeacherAliasModalOpen(false)}
          >
            <motion.div
              className={`${workspaceCardClass} mx-4 w-full max-w-md p-6`}
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              onClick={(e: React.MouseEvent) => e.stopPropagation()}
            >
              <h3 className="mb-5 text-lg font-bold text-slate-900 dark:text-white">{teacherAliasModalMode === 'create' ? '添加讲师映射' : '编辑讲师映射'}</h3>
              <div className="space-y-4">
                {teacherAliasMemberOptions.length > 0 && (
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-300">关联网站成员（可选）</label>
                    <select
                      className={workspaceFieldClass}
                      value={taLinkedUsername}
                      onChange={(e) => setTaLinkedUsername(e.target.value)}
                    >
                      <option value="">不关联网站成员</option>
                      {teacherAliasMemberOptions.map((user) => (
                        <option key={user.id} value={user.username || ''}>
                          {user.name}{user.username ? `（${user.username}）` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-300">企微 ID（手动填写）</label>
                  <input
                    className={workspaceFieldClass}
                    value={taFormUserId}
                    onChange={(e) => setTaFormUserId(e.target.value)}
                    placeholder="例：XuJianYi"
                    disabled={teacherAliasModalMode === 'edit'}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-300">中文名（手动填写）</label>
                  <input
                    className={workspaceFieldClass}
                    value={taFormDisplayName}
                    onChange={(e) => setTaFormDisplayName(e.target.value)}
                    placeholder="例：徐健译"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-300">别名（逗号分隔，可选）</label>
                  <input
                    className={workspaceFieldClass}
                    value={taFormAliases}
                    onChange={(e) => setTaFormAliases(e.target.value)}
                    placeholder="例：小徐, 徐老师"
                  />
                </div>
              </div>
              <div className="mt-6 flex justify-end gap-3">
                <button type="button" className={workspaceSecondaryButtonClass} onClick={() => setTeacherAliasModalOpen(false)}>取消</button>
                <button
                  type="button"
                  className={workspacePrimaryButtonClass}
                  disabled={taSubmitting || !taFormUserId.trim() || !taFormDisplayName.trim()}
                  onClick={handleTeacherAliasSubmit}
                >{taSubmitting ? '保存中...' : '保存'}</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
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
            <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">登出后需重新输入账号和密码。</p>
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

const CreditCenterPage = ({ currentUser }: { currentUser: CurrentUser }) => {
  const CREDIT_USAGE_DETAIL_PAGE_SIZE = 5;
  const CREDIT_LEDGER_PAGE_SIZE = 5;
  const [creditOverview, setCreditOverview] = useState<CreditOverview | null>(null);
  const [creditLedger, setCreditLedger] = useState<CreditLedgerItem[]>([]);
  const [creditUsage, setCreditUsage] = useState<CreditMemberUsageItem[]>([]);
  const [creditLoading, setCreditLoading] = useState(true);
  const [creditError, setCreditError] = useState('');
  const [redeemOrderId, setRedeemOrderId] = useState('');
  const [redeemPhoneSuffix, setRedeemPhoneSuffix] = useState('');
  const [redeemLoading, setRedeemLoading] = useState(false);
  const [redeemMessage, setRedeemMessage] = useState('');
  const [selectedUsageUser, setSelectedUsageUser] = useState<CreditMemberUsageItem | null>(null);
  const selectedUsageUserIdRef = useRef<number | null>(null);
  const [usageDetailItems, setUsageDetailItems] = useState<CreditMemberUsageDetailItem[]>([]);
  const [usageDetailLoading, setUsageDetailLoading] = useState(false);
  const [usageDetailError, setUsageDetailError] = useState('');
  const [usageDetailPage, setUsageDetailPage] = useState(1);
  const [ledgerFilter, setLedgerFilter] = useState<'all' | 'credit' | 'debit'>('all');
  const [ledgerPage, setLedgerPage] = useState(1);
  const canSeeSensitiveUsageMeta = currentUser.role === 'super_owner';
  const [n1nPricingByModel, setN1nPricingByModel] = useState<Record<string, N1nModelPricingItem>>({});
  const [n1nPricingCnyPerUsd, setN1nPricingCnyPerUsd] = useState(1);

  const loadSelectedUsageDetail = useCallback(async (userId: number) => {
    setUsageDetailLoading(true);
    setUsageDetailError('');
    try {
      const payload = await apiFetch<{ items: CreditMemberUsageDetailItem[] }>(`/api/credits/member-usage/${userId}`);
      setUsageDetailItems(payload.items);
    } catch (err) {
      setUsageDetailItems([]);
      setUsageDetailError(err instanceof Error ? err.message : '成员明细加载失败');
    } finally {
      setUsageDetailLoading(false);
    }
  }, []);

  const loadN1nPricingByModels = useCallback(async (models: string[]) => {
    const normalizedModels = Array.from(new Set(models.map((item) => item.trim()).filter(Boolean)));
    if (normalizedModels.length === 0) {
      return;
    }
    const missingModels = normalizedModels.filter((model) => !n1nPricingByModel[model]);
    if (missingModels.length === 0) {
      return;
    }
    try {
      const payload = await apiFetch<{ cny_per_usd: number; items: Record<string, N1nModelPricingItem> }>(
        `/api/credits/pricing/n1n?models=${encodeURIComponent(missingModels.join(','))}`,
      );
      setN1nPricingCnyPerUsd(Number(payload.cny_per_usd || 1));
      setN1nPricingByModel((previous) => ({ ...previous, ...(payload.items || {}) }));
    } catch {
      // Keep UI resilient when n1n pricing endpoint is temporarily unavailable.
    }
  }, [n1nPricingByModel]);

  useEffect(() => {
    selectedUsageUserIdRef.current = selectedUsageUser?.user_id ?? null;
  }, [selectedUsageUser]);

  const loadCredits = useCallback(async () => {
    setCreditLoading(true);
    setCreditError('');
    try {
      const [overview, ledgerPayload, usagePayload] = await Promise.all([
        apiFetch<CreditOverview>('/api/credits/overview'),
        apiFetch<{ items: CreditLedgerItem[] }>('/api/credits/ledger?limit=100'),
        apiFetch<{ items: CreditMemberUsageItem[] }>('/api/credits/member-usage'),
      ]);
      setCreditOverview(overview);
      setCreditLedger(ledgerPayload.items);
      setCreditUsage(usagePayload.items);

      if (selectedUsageUserIdRef.current !== null) {
        const refreshedSelectedUsageUser = usagePayload.items.find((item) => item.user_id === selectedUsageUserIdRef.current) ?? null;
        setSelectedUsageUser(refreshedSelectedUsageUser);
        if (refreshedSelectedUsageUser) {
          await loadSelectedUsageDetail(refreshedSelectedUsageUser.user_id);
        } else {
          setUsageDetailItems([]);
          setUsageDetailError('');
        }
      }
    } catch (err) {
      setCreditError(err instanceof Error ? err.message : '积分中心加载失败');
    } finally {
      setCreditLoading(false);
    }
  }, [loadSelectedUsageDetail]);

  useEffect(() => {
    void loadCredits();
  }, [loadCredits]);

  const handleRedeemSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setRedeemLoading(true);
    setRedeemMessage('');
    setCreditError('');
    try {
      const payload = await apiFetch<{ overview: CreditOverview }>('/api/credits/redeem/xhs', {
        method: 'POST',
        body: JSON.stringify({
          platform_order_id: redeemOrderId,
          phone_suffix: redeemPhoneSuffix,
        }),
      });
      setCreditOverview(payload.overview);
      setRedeemOrderId('');
      setRedeemPhoneSuffix('');
      setRedeemMessage('兑换成功，积分余额已更新。');
      await loadCredits();
    } catch (err) {
      setCreditError(err instanceof Error ? err.message : '订单兑换失败');
    } finally {
      setRedeemLoading(false);
    }
  };

  const handleSelectUsageUser = (item: CreditMemberUsageItem) => {
    setSelectedUsageUser(item);
    void loadSelectedUsageDetail(item.user_id);
  };

  const FEATURE_KEY_LABELS: Record<string, string> = {
    lesson_plan_generate: '复习计划生成',
    consultation_ai_parse: '咨询记录解析',
    audio_transcription: '音频转录',
    monthly_plan_generate: '月度计划生成',
  };
  const SOURCE_RECORD_TYPE_LABELS: Record<string, string> = {
    lesson: '课程记录',
    consultation: '咨询记录',
    monthly_plan: '月度计划',
    draft: '草稿',
  };
  const formatRequestId = (requestId: string) => (
    requestId.length > 20 ? `${requestId.slice(0, 10)}...${requestId.slice(-8)}` : requestId
  );

  const totalUsageDetailPages = Math.max(1, Math.ceil(usageDetailItems.length / CREDIT_USAGE_DETAIL_PAGE_SIZE));
  const currentUsageDetailPage = Math.min(usageDetailPage, totalUsageDetailPages);
  const paginatedUsageDetailItems = usageDetailItems.slice(
    (currentUsageDetailPage - 1) * CREDIT_USAGE_DETAIL_PAGE_SIZE,
    currentUsageDetailPage * CREDIT_USAGE_DETAIL_PAGE_SIZE,
  );
  const filteredLedger = creditLedger.filter((item) => ledgerFilter === 'all' || item.direction === ledgerFilter);
  const totalLedgerPages = Math.max(1, Math.ceil(filteredLedger.length / CREDIT_LEDGER_PAGE_SIZE));
  const currentLedgerPage = Math.min(ledgerPage, totalLedgerPages);
  const paginatedLedger = filteredLedger.slice((currentLedgerPage - 1) * CREDIT_LEDGER_PAGE_SIZE, currentLedgerPage * CREDIT_LEDGER_PAGE_SIZE);

  useEffect(() => {
    setUsageDetailPage(1);
  }, [selectedUsageUser, usageDetailItems]);

  useEffect(() => {
    setLedgerPage(1);
  }, [ledgerFilter, creditLedger]);

  useEffect(() => {
    const modelsInDetail = usageDetailItems
      .map((item) => String(item.model || '').trim())
      .filter(Boolean);
    void loadN1nPricingByModels(modelsInDetail);
  }, [usageDetailItems, loadN1nPricingByModels]);

  return (
    <div className={`${workspacePageClass} mx-auto max-w-6xl space-y-8`}>
      <section className={`${workspaceCardClass} overflow-hidden p-6`}>
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-sky-600">Credit Workspace</p>
            <h3 className={`${workspaceSectionTitleClass} mt-3`}>积分中心</h3>
            <p className={`${workspaceSectionTextClass} mt-2`}>
              管理 {currentUser.organization_name} 的积分余额、订单兑换、成员消耗和 AI 扣费流水。
            </p>
          </div>
          <button onClick={() => void loadCredits()} className={workspaceSecondaryButtonClass} type="button">
            刷新积分
          </button>
        </div>
      </section>

      {creditError && (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
          {creditError}
        </div>
      )}

      {redeemMessage && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300">
          {redeemMessage}
        </div>
      )}

      <section className="grid gap-4 md:grid-cols-3">
        <div className={`${workspaceCardClass} p-5`}>
          <p className="text-sm text-slate-500 dark:text-slate-400">当前余额</p>
          <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-white">{creditLoading ? '--' : creditOverview?.credit_balance ?? 0}</p>
        </div>
        <div className={`${workspaceCardClass} p-5`}>
          <p className="text-sm text-slate-500 dark:text-slate-400">累计充值</p>
          <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-white">{creditLoading ? '--' : creditOverview?.total_recharged ?? 0}</p>
        </div>
        <div className={`${workspaceCardClass} p-5`}>
          <p className="text-sm text-slate-500 dark:text-slate-400">累计消耗</p>
          <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-white">{creditLoading ? '--' : creditOverview?.total_consumed ?? 0}</p>
        </div>
      </section>

      <section className={`${workspaceCardClass} space-y-4 p-6`}>
        <div>
          <p className="font-medium text-slate-900 dark:text-white">小红书订单兑换</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">输入订单号和手机号后四位，将有效订单兑换到当前机构积分池。</p>
        </div>
        <form className="grid gap-3 md:grid-cols-[1fr_180px_auto]" onSubmit={handleRedeemSubmit}>
          <input
            value={redeemOrderId}
            onChange={(event) => setRedeemOrderId(event.target.value)}
            placeholder="小红书订单号"
            className={`${workspaceFieldClass} w-full`}
          />
          <input
            value={redeemPhoneSuffix}
            onChange={(event) => setRedeemPhoneSuffix(event.target.value.replace(/\D/g, '').slice(0, 4))}
            placeholder="手机号后四位"
            className={`${workspaceFieldClass} w-full`}
          />
          <button type="submit" disabled={redeemLoading} className={workspacePrimaryButtonClass}>
            {redeemLoading ? '兑换中...' : '兑换积分'}
          </button>
        </form>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <div className="space-y-6">
          <div className={`${workspaceCardClass} space-y-4 p-6`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-medium text-slate-900 dark:text-white">成员用量</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">按成员汇总 AI 功能的积分消耗，点击可查看成员明细。</p>
              </div>
              <span className="shrink-0 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                {creditUsage.length} 人
              </span>
            </div>
            <div className="space-y-3">
              {creditUsage.length === 0 ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">暂无成员用量记录。</p>
              ) : (
                creditUsage.map((item) => {
                  const selected = selectedUsageUser?.user_id === item.user_id;
                  return (
                    <button
                      key={item.user_id}
                      type="button"
                      onClick={() => handleSelectUsageUser(item)}
                      className={cn(
                        'flex w-full items-center justify-between rounded-2xl border px-4 py-4 text-left transition-all',
                        selected
                          ? 'border-sky-300 bg-sky-50/90 shadow-[0_18px_40px_rgba(47,128,237,0.12)] dark:border-sky-500/30 dark:bg-sky-500/10'
                          : 'border-slate-200/70 bg-white/70 hover:border-sky-200 hover:bg-sky-50/60 dark:border-white/10 dark:bg-white/5 dark:hover:border-white/15 dark:hover:bg-white/10',
                      )}
                    >
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">{item.display_name}</p>
                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                          调用 {item.usage_count} 次 · 最近使用 {item.last_used_at ? new Date(item.last_used_at).toLocaleString('zh-CN') : '暂无'}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-slate-900 dark:text-white">-{item.credit_consumed}</p>
                        <p className="mt-1 text-xs text-sky-600 dark:text-sky-300">查看明细</p>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          <div className={`${workspaceCardClass} space-y-4 p-6`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-medium text-slate-900 dark:text-white">成员明细</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">查看某位成员的 AI 使用与积分扣费细项。</p>
              </div>
              {selectedUsageUser && (
                <button
                  type="button"
                  onClick={() => {
                    setSelectedUsageUser(null);
                    setUsageDetailItems([]);
                    setUsageDetailError('');
                  }}
                  className={workspaceSecondaryButtonClass}
                >
                  清空选择
                </button>
              )}
            </div>

            {!selectedUsageUser ? (
              <div className={`${workspaceSoftCardClass} p-5 text-sm text-slate-500 dark:text-slate-400`}>
                先从上方成员列表选择一位成员，再查看成员明细。
              </div>
            ) : (
              <div className="space-y-4">
                <div className={`${workspaceSoftCardClass} grid gap-4 p-5 md:grid-cols-3`}>
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">成员</p>
                    <p className="mt-2 text-base font-semibold text-slate-900 dark:text-white">{selectedUsageUser.display_name}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">累计消耗</p>
                    <p className="mt-2 text-base font-semibold text-slate-900 dark:text-white">-{selectedUsageUser.credit_consumed}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">最近使用</p>
                    <p className="mt-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                      {selectedUsageUser.last_used_at ? new Date(selectedUsageUser.last_used_at).toLocaleString('zh-CN') : '暂无'}
                    </p>
                  </div>
                </div>

                {usageDetailError && (
                  <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
                    {usageDetailError}
                  </div>
                )}

                {usageDetailLoading ? (
                  <div className={`${workspaceSoftCardClass} p-5`}>
                    <WorkspaceLoading label="正在加载成员明细..." />
                  </div>
                ) : usageDetailItems.length === 0 ? (
                  <div className={`${workspaceSoftCardClass} p-5 text-sm text-slate-500 dark:text-slate-400`}>
                    该成员目前没有可展示的使用明细。
                  </div>
                ) : (
                  <div className="space-y-3">
                    {paginatedUsageDetailItems.map((item) => {
                      const featureLabel = FEATURE_KEY_LABELS[item.feature_key] ?? item.feature_key;
                      const sourceTypeLabel = item.source_record_type
                        ? (SOURCE_RECORD_TYPE_LABELS[item.source_record_type] ?? item.source_record_type)
                        : '未知';
                      const providerLabel = item.provider || 'AI';
                      const modelPricing = item.model ? n1nPricingByModel[item.model] : undefined;
                      const inputTokens = Math.max(0, Number(item.input_tokens ?? 0));
                      const outputTokens = Math.max(0, Number(item.output_tokens ?? 0));
                      const estimatedUsdCost = modelPricing && modelPricing.quota_type === 0
                        ? (inputTokens / 1_000_000) * Number(modelPricing.input_usd_per_m || 0)
                          + (outputTokens / 1_000_000) * Number(modelPricing.output_usd_per_m || 0)
                        : null;
                      const estimatedCnyCost = estimatedUsdCost !== null ? estimatedUsdCost * n1nPricingCnyPerUsd : null;
                      return (
                        <div key={item.id} className={`${workspaceSoftCardClass} space-y-3 p-4`}>
                          <div className="flex items-start justify-between gap-4">
                            <div>
                              <p className="font-medium text-slate-900 dark:text-white">{featureLabel}</p>
                              {canSeeSensitiveUsageMeta && (
                                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                  {providerLabel}{item.model ? ` · ${item.model}` : ''} · 请求编号 {formatRequestId(item.request_id)}
                                </p>
                              )}
                            </div>
                            <p className="text-sm font-semibold text-rose-600 dark:text-rose-300">-{item.credit_cost_final}</p>
                          </div>
                          <div className="grid gap-3 text-xs text-slate-500 dark:text-slate-400 md:grid-cols-3">
                            {canSeeSensitiveUsageMeta ? (
                              <p>来源：{sourceTypeLabel} #{item.source_record_id ?? '-'}</p>
                            ) : (
                              <p>来源：{sourceTypeLabel}</p>
                            )}
                            <p>Tokens：{item.total_tokens ?? 0}（输入 {item.input_tokens ?? 0} / 输出 {item.output_tokens ?? 0}）</p>
                            <p>时间：{new Date(item.created_at).toLocaleString('zh-CN')}</p>
                          </div>
                          {estimatedCnyCost !== null && (
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              预估花费：¥{estimatedCnyCost.toFixed(4)}（按 n1n 公开价格估算，1 美元按 {n1nPricingCnyPerUsd.toFixed(2)} 人民币换算）
                            </p>
                          )}
                        </div>
                      );
                    })}
                    {totalUsageDetailPages > 1 && (
                      <div className="flex items-center justify-between border-t border-sky-100/80 pt-3 text-sm dark:border-white/10">
                        <button
                          type="button"
                          onClick={() => setUsageDetailPage((page) => Math.max(1, page - 1))}
                          disabled={currentUsageDetailPage === 1}
                          className={workspaceSecondaryButtonClass}
                        >
                          上一页
                        </button>
                        <span className="text-slate-500 dark:text-slate-400">
                          第 {currentUsageDetailPage} / {totalUsageDetailPages} 页
                        </span>
                        <button
                          type="button"
                          onClick={() => setUsageDetailPage((page) => Math.min(totalUsageDetailPages, page + 1))}
                          disabled={currentUsageDetailPage === totalUsageDetailPages}
                          className={workspaceSecondaryButtonClass}
                        >
                          下一页
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className={`${workspaceCardClass} space-y-4 p-6`}>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="font-medium text-slate-900 dark:text-white">最近流水</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">最近 100 条积分变动记录，支持按类型筛选。</p>
            </div>
            <label className="space-y-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              流水筛选
              <select value={ledgerFilter} onChange={(event) => setLedgerFilter(event.target.value as 'all' | 'credit' | 'debit')} className={`${workspaceFieldClass} w-full`}>
                <option value="all">全部</option>
                <option value="credit">仅充值</option>
                <option value="debit">仅消耗</option>
              </select>
            </label>
          </div>

          <div className="space-y-3">
            {filteredLedger.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400">当前筛选条件下暂无积分流水。</p>
            ) : (
              paginatedLedger.map((item) => {
                const SOURCE_TYPE_LABELS: Record<string, string> = {
                  ai_usage: 'AI 功能消耗',
                  manual_adjustment: '人工充值',
                  xhs_order_redeem: '小红书订单兑换',
                  consultation_ai_parse: '咨询记录 AI 解析',
                  lesson_plan_generate: '复习计划生成',
                  audio_transcription: '音频转录',
                  monthly_plan_generate: '月度计划生成',
                };
                const AI_FEATURE_LABELS: Record<string, string> = {
                  lesson_plan_generate: '复习计划生成',
                  consultation_ai_parse: '咨询记录解析',
                  audio_transcription: '音频转录',
                  monthly_plan_generate: '月度计划生成',
                };
                const sourceLabel = SOURCE_TYPE_LABELS[item.source_type] ?? item.source_type;
                const rawNote = item.note || '';
                const isManualTopup = /^manual_topup/.test(rawNote);
                const noteLabel = isManualTopup ? '人工充值' : (rawNote || undefined);
                // For ai_usage entries the note field contains the feature key
                const featureLabel = item.source_type === 'ai_usage' ? (AI_FEATURE_LABELS[rawNote] ?? rawNote) : undefined;
                const displayTitle = featureLabel ?? sourceLabel;
                const displayNote = featureLabel ? undefined : noteLabel;
                return (
                  <div key={item.id} className="flex items-center justify-between rounded-2xl border border-slate-200/70 bg-white/70 px-4 py-4 text-sm dark:border-white/10 dark:bg-white/5">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">{displayTitle}</p>
                      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                        {[displayNote, `余额 ${item.balance_after}`, new Date(item.created_at).toLocaleString('zh-CN')].filter(Boolean).join(' · ')}
                      </p>
                    </div>
                    <p className={item.direction === 'credit' ? 'font-semibold text-emerald-600 dark:text-emerald-300' : 'font-semibold text-rose-600 dark:text-rose-300'}>
                      {item.direction === 'credit' ? '+' : '-'}{item.amount}
                    </p>
                  </div>
                );
              })
            )}
          </div>

          {totalLedgerPages > 1 && (
            <div className="flex items-center justify-between border-t border-sky-100/80 pt-3 text-sm dark:border-white/10">
              <button
                type="button"
                onClick={() => setLedgerPage((page) => Math.max(1, page - 1))}
                disabled={currentLedgerPage === 1}
                className={workspaceSecondaryButtonClass}
              >
                上一页
              </button>
              <span className="text-slate-500 dark:text-slate-400">
                第 {currentLedgerPage} / {totalLedgerPages} 页
              </span>
              <button
                type="button"
                onClick={() => setLedgerPage((page) => Math.min(totalLedgerPages, page + 1))}
                disabled={currentLedgerPage === totalLedgerPages}
                className={workspaceSecondaryButtonClass}
              >
                下一页
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
};

const ClassManagementPage = ({
  currentUser,
  classBindingTarget,
  onClearClassBindingTarget,
}: {
  currentUser: CurrentUser;
  classBindingTarget?: ClassBindingTarget | null;
  onClearClassBindingTarget?: () => void;
}) => {
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [teacherBindingByClassId, setTeacherBindingByClassId] = useState<Record<number, number | null>>({});
  const [inviteByClassId, setInviteByClassId] = useState<Record<number, ClassInviteInfo>>({});
  const [studentsByClassId, setStudentsByClassId] = useState<Record<number, Array<{ id: number; name: string }>>>({});
  const [expandedClassId, setExpandedClassId] = useState<number | 'new' | null>(null);
  const [formByClassId, setFormByClassId] = useState<Record<string, ClassFormValues>>(() => ({
    new: createEmptyClassForm(),
  }));
  const [selectedGradeFilter, setSelectedGradeFilter] = useState<string>('全部');
  const [selectedSubjectFilter, setSelectedSubjectFilter] = useState<string>('全部学科');
  const [newClassTeacherUserId, setNewClassTeacherUserId] = useState<number | null>(null);
  const [teacherSearchByClassId, setTeacherSearchByClassId] = useState<Record<string, string>>({});
  const [studentDraftNameByClassId, setStudentDraftNameByClassId] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState('');
  const [formError, setFormError] = useState('');
  const [assignmentError, setAssignmentError] = useState('');
  const [studentErrorByClassId, setStudentErrorByClassId] = useState<Record<number, string>>({});
  const [inviteErrorByClassId, setInviteErrorByClassId] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [teacherBindingSavingByClassId, setTeacherBindingSavingByClassId] = useState<Record<number, boolean>>({});
  const [studentsLoadingByClassId, setStudentsLoadingByClassId] = useState<Record<number, boolean>>({});
  const [studentSavingByClassId, setStudentSavingByClassId] = useState<Record<number, boolean>>({});
  const [inviteLoadingByClassId, setInviteLoadingByClassId] = useState<Record<number, boolean>>({});
  const [inviteResettingByClassId, setInviteResettingByClassId] = useState<Record<number, boolean>>({});
  const loadPageRequestVersionRef = useRef(0);
  const classInteractionLocked = saving || deleting;
  const hasTeacherBindingSavingRows = Object.values(teacherBindingSavingByClassId).some(Boolean);
  const classCardInteractionLocked = classInteractionLocked || hasTeacherBindingSavingRows;
  const pageRefreshLocked = loading || classInteractionLocked || hasTeacherBindingSavingRows;
  const assignmentRefreshLocked = loading || classInteractionLocked || hasTeacherBindingSavingRows;
  const canManageClassTeachers = hasStaffAccess(currentUser.role);

  const getClassStateKey = (classId: number | 'new') => String(classId);

  const loadPage = useCallback(async (preferredExpandedClassId?: number | 'new' | null, options?: { preserveStateOnError?: boolean }): Promise<LoadPageResult> => {
    const preserveStateOnError = options?.preserveStateOnError ?? false;
    const requestVersion = ++loadPageRequestVersionRef.current;
    setLoading(true);
    setPageError('');
    try {
      const [classItems, userItems, teacherBindingData] = await Promise.all([
        apiFetch<ClassItem[]>('/api/classes'),
        hasStaffAccess(currentUser.role)
          ? apiFetch<UserItem[]>('/api/admin/users')
          : Promise.resolve([] as UserItem[]),
        hasStaffAccess(currentUser.role)
          ? apiFetch<{ teacher_bindings: Record<number, number | null> }>('/api/classes/teacher-bindings')
          : Promise.resolve({ teacher_bindings: {} as Record<number, number | null> }),
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
  }, [currentUser.role]);

  useEffect(() => {
    loadPage().catch(() => undefined);
  }, [loadPage]);

  const handleLoadClassInvite = useCallback(async (classId: number) => {
    setInviteLoadingByClassId((current) => ({ ...current, [classId]: true }));
    setInviteErrorByClassId((current) => ({ ...current, [classId]: '' }));

    try {
      const payload = await apiFetch<ClassInviteInfo>(`/api/classes/${classId}/invite`);
      setInviteByClassId((current) => ({ ...current, [classId]: payload }));
    } catch (err) {
      setInviteErrorByClassId((current) => ({
        ...current,
        [classId]: err instanceof Error ? err.message : '邀请码加载失败',
      }));
    } finally {
      setInviteLoadingByClassId((current) => ({ ...current, [classId]: false }));
    }
  }, []);

  const handleResetClassInvite = useCallback(async (classId: number) => {
    setInviteResettingByClassId((current) => ({ ...current, [classId]: true }));
    setInviteErrorByClassId((current) => ({ ...current, [classId]: '' }));

    try {
      const payload = await apiFetch<ClassInviteInfo>(`/api/classes/${classId}/invite/reset`, {
        method: 'POST',
      });
      setInviteByClassId((current) => ({ ...current, [classId]: payload }));
    } catch (err) {
      setInviteErrorByClassId((current) => ({
        ...current,
        [classId]: err instanceof Error ? err.message : '邀请码重置失败',
      }));
    } finally {
      setInviteResettingByClassId((current) => ({ ...current, [classId]: false }));
    }
  }, []);

  const loadStudentsForClass = useCallback(async (classId: number) => {
    setStudentsLoadingByClassId((current) => ({ ...current, [classId]: true }));
    setStudentErrorByClassId((current) => ({ ...current, [classId]: '' }));

    try {
      const payload = await listClassStudents(classId);
      setStudentsByClassId((current) => ({ ...current, [classId]: payload.students }));
    } catch (err) {
      setStudentErrorByClassId((current) => ({
        ...current,
        [classId]: err instanceof Error ? err.message : '学生列表加载失败',
      }));
    } finally {
      setStudentsLoadingByClassId((current) => ({ ...current, [classId]: false }));
    }
  }, []);

  useEffect(() => {
    if (typeof expandedClassId !== 'number' || inviteByClassId[expandedClassId]) {
      return;
    }

    void handleLoadClassInvite(expandedClassId);
  }, [expandedClassId, handleLoadClassInvite, inviteByClassId]);

  useEffect(() => {
    if (typeof expandedClassId !== 'number') {
      return;
    }
    if (Object.prototype.hasOwnProperty.call(studentsByClassId, expandedClassId)) {
      return;
    }

    void loadStudentsForClass(expandedClassId);
  }, [expandedClassId, loadStudentsForClass, studentsByClassId]);

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

  const handleStudentDraftNameChange = (classId: number, value: string) => {
    setStudentDraftNameByClassId((current) => ({
      ...current,
      [classId]: value,
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

  useEffect(() => {
    if (!classBindingTarget || expandedClassId === null) {
      return;
    }

    const stateKey = getClassStateKey(expandedClassId);
    setTeacherSearchByClassId((current) => (
      current[stateKey]
        ? current
        : { ...current, [stateKey]: classBindingTarget.teacherName }
    ));
    if (expandedClassId === 'new') {
      setNewClassTeacherUserId(classBindingTarget.teacherUserId);
    }
  }, [classBindingTarget, expandedClassId]);

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

    if (!payload.subject) {
      setFormError('学科不能为空');
      return;
    }

    if (!payload.grade || !gradeOptions.includes(payload.grade)) {
      setFormError('请选择年级');
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
      setAssignmentError(err instanceof Error ? err.message : '负责老师保存失败');
    } finally {
      setTeacherBindingSavingByClassId((current) => {
        const nextState = { ...current };
        delete nextState[classId];
        return nextState;
      });
    }
  };

  const handleAddStudentToClass = async (classId: number) => {
    const draftName = (studentDraftNameByClassId[classId] || '').trim();
    if (!draftName) {
      setStudentErrorByClassId((current) => ({ ...current, [classId]: '请输入学生姓名' }));
      return;
    }

    setStudentSavingByClassId((current) => ({ ...current, [classId]: true }));
    setStudentErrorByClassId((current) => ({ ...current, [classId]: '' }));

    try {
      const payload = await createClassStudent(classId, draftName);
      setStudentsByClassId((current) => ({
        ...current,
        [classId]: [...(current[classId] || []), payload.student],
      }));
      setStudentDraftNameByClassId((current) => ({ ...current, [classId]: '' }));
    } catch (err) {
      setStudentErrorByClassId((current) => ({
        ...current,
        [classId]: err instanceof Error ? err.message : '新增学生失败，请重试。',
      }));
    } finally {
      setStudentSavingByClassId((current) => ({ ...current, [classId]: false }));
    }
  };

  const handleDeleteStudentFromClass = async (classId: number, studentId: number) => {
    setStudentSavingByClassId((current) => ({ ...current, [classId]: true }));
    setStudentErrorByClassId((current) => ({ ...current, [classId]: '' }));

    try {
      await deleteClassStudent(classId, studentId);
      setStudentsByClassId((current) => ({
        ...current,
        [classId]: (current[classId] || []).filter((student) => student.id !== studentId),
      }));
    } catch (err) {
      setStudentErrorByClassId((current) => ({
        ...current,
        [classId]: err instanceof Error ? err.message : '删除学生失败，请重试。',
      }));
    } finally {
      setStudentSavingByClassId((current) => ({ ...current, [classId]: false }));
    }
  };

  const classSubjectFilterOptions = ['全部学科', ...Array.from(new Set(classes.map((item) => item.subject.trim()).filter(Boolean))).map(String).sort((a, b) => a.localeCompare(b, 'zh-CN'))];
  const activeClassFilterSummary = [
    selectedGradeFilter !== '全部' ? selectedGradeFilter : '',
    selectedSubjectFilter !== '全部学科' ? selectedSubjectFilter : '',
  ].filter(Boolean).join(' / ') || '全部';
  const filteredClasses = classes.filter((item) => {
    if (selectedSubjectFilter !== '全部学科' && item.subject !== selectedSubjectFilter) {
      return false;
    }
    if (selectedGradeFilter === '全部') {
      return true;
    }
    if (selectedGradeFilter === '未绑定') {
      return item.teacher_user_id == null;
    }
    return item.grade === selectedGradeFilter;
  });

  const newClassForm = formByClassId.new || createEmptyClassForm();
  const newClassExpanded = expandedClassId === 'new';
  const newClassTeacher = newClassTeacherUserId == null ? undefined : users.find((user) => user.id === newClassTeacherUserId);
  const newClassFilteredUsers = users.filter((user) => {
    const keyword = (teacherSearchByClassId.new || '').trim().toLowerCase();
    if (newClassTeacherUserId === user.id) {
      return true;
    }
    if (!keyword) {
      return true;
    }
    return user.name.toLowerCase().includes(keyword);
  });
  const editingClass = typeof expandedClassId === 'number' ? classes.find((item) => item.id === expandedClassId) ?? null : null;
  const editingFormState = editingClass ? (formByClassId[getClassStateKey(editingClass.id)] || toClassFormValues(editingClass)) : null;
  const editingTeacherSearch = editingClass ? (teacherSearchByClassId[getClassStateKey(editingClass.id)] || '') : '';
  const editingCurrentTeacherUserId = editingClass
    ? (teacherBindingByClassId[editingClass.id] ?? editingClass.teacher_user_id ?? null)
    : null;
  const editingCurrentTeacher = editingCurrentTeacherUserId == null ? undefined : users.find((user) => user.id === editingCurrentTeacherUserId);
  const editingTeacherSummary = editingCurrentTeacher?.name || editingClass?.teacher_name || '未分配老师';
  const editingTeacherBindingSaving = editingClass ? Boolean(teacherBindingSavingByClassId[editingClass.id]) : false;
  const editingInviteInfo = editingClass ? inviteByClassId[editingClass.id] : undefined;
  const editingInviteLoading = editingClass ? Boolean(inviteLoadingByClassId[editingClass.id]) : false;
  const editingInviteResetting = editingClass ? Boolean(inviteResettingByClassId[editingClass.id]) : false;
  const editingInviteError = editingClass ? (inviteErrorByClassId[editingClass.id] || '') : '';
  const editingStudents = editingClass ? (studentsByClassId[editingClass.id] || []) : [];
  const editingStudentsLoading = editingClass ? Boolean(studentsLoadingByClassId[editingClass.id]) : false;
  const editingStudentSaving = editingClass ? Boolean(studentSavingByClassId[editingClass.id]) : false;
  const editingStudentError = editingClass ? (studentErrorByClassId[editingClass.id] || '') : '';
  const editingStudentDraftName = editingClass ? (studentDraftNameByClassId[editingClass.id] || '') : '';
  const editingFilteredUsers = editingClass
    ? users.filter((user) => {
        const keyword = editingTeacherSearch.trim().toLowerCase();
        if (editingCurrentTeacherUserId === user.id) {
          return true;
        }
        if (!keyword) {
          return true;
        }
        return user.name.toLowerCase().includes(keyword);
      })
    : [];

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
        {classBindingTarget && (
          <div className="flex flex-col gap-3 rounded-2xl border border-sky-200 bg-sky-50/80 p-4 sm:flex-row sm:items-center sm:justify-between dark:border-sky-500/30 dark:bg-sky-500/10">
            <div>
              <p className="text-xs uppercase tracking-[0.25em] text-sky-600 dark:text-sky-300">绑定班级</p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">目标老师：{classBindingTarget?.teacherName}</p>
            </div>
            {onClearClassBindingTarget && (
              <button
                type="button"
                onClick={onClearClassBindingTarget}
                className={workspaceSecondaryButtonClass}
              >
                清除目标
              </button>
            )}
          </div>
        )}
        <div className={`${workspaceSoftCardClass} space-y-3 p-4`}>
          <p className="text-sm font-semibold text-slate-900 dark:text-white">班级命名规则</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">按「学科 + 年级 + 班级」维护班级信息，例如：数学七年级三班、物理七年级二班。学科填写具体科目，班级名称填写“三班”这类班级序号。</p>
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
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">每次只展开一个班级卡片，在卡片内部完成基础信息维护和负责老师设置。</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => loadPage(expandedClassId, { preserveStateOnError: true }).catch(() => undefined)}
              disabled={pageRefreshLocked}
              className={workspaceSecondaryButtonClass}
            >
              刷新列表
            </button>
            {canManageClassTeachers && (
              <button
                type="button"
                onClick={() => handleToggleExpandedClass('new')}
                disabled={classCardInteractionLocked}
                className={workspacePrimaryButtonClass}
              >
                <PlusCircle size={18} />
                新建班级
              </button>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-3 border-t border-sky-100/80 pt-4 dark:border-white/10">
          <div className="flex flex-wrap gap-2">
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
          <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 sm:max-w-xs">
            学科筛选
            <select
              value={selectedSubjectFilter}
              onChange={(event) => setSelectedSubjectFilter(event.target.value)}
              className={`${workspaceFieldClass} w-full`}
            >
              {classSubjectFilterOptions.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
            正在加载班级数据...
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredClasses.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                {classes.length === 0 ? '暂无班级，点击右上角“新建班级”开始创建。' : `当前筛选“${activeClassFilterSummary}”下暂无班级。`}
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
              const inviteInfo = inviteByClassId[item.id];
              const inviteLoading = Boolean(inviteLoadingByClassId[item.id]);
              const inviteResetting = Boolean(inviteResettingByClassId[item.id]);
              const inviteError = inviteErrorByClassId[item.id] || '';
              const filteredUsers = users.filter((user) => {
                const keyword = teacherSearch.trim().toLowerCase();
                if (currentTeacherUserId === user.id) {
                  return true;
                }
                if (!keyword) {
                  return true;
                }
                return user.name.toLowerCase().includes(keyword);
              });

              return (
                <div key={item.id} className={`${workspaceSoftCardClass} overflow-hidden p-5`}>
                  <button
                    type="button"
                    onClick={() => handleToggleExpandedClass(item.id)}
                    disabled={classCardInteractionLocked}
                    className={cn(
                      'group flex w-full flex-col gap-4 text-left lg:flex-row lg:items-center lg:justify-between',
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
                        <span>当前负责老师：{teacherSummary}</span>
                      </div>
                    </div>
                    <ChevronDown
                      size={18}
                      className="text-slate-400 transition-transform duration-200 group-hover:text-slate-600 dark:text-slate-500 dark:group-hover:text-slate-300"
                    />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <AnimatePresence>
        {(newClassExpanded || editingClass) && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto px-3 py-3 sm:items-center sm:px-4 sm:py-6"
            onClick={(e) => e.target === e.currentTarget && !classCardInteractionLocked && setExpandedClassId(null)}
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
                  <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Class Management</p>
                  <h3 className="mt-2 text-xl font-bold tracking-tight text-slate-900 sm:text-2xl dark:text-white">
                    {newClassExpanded ? '新建班级' : `编辑班级：${editingClass?.name || ''}`}
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    if (classCardInteractionLocked) {
                      return;
                    }
                    setExpandedClassId(null);
                  }}
                  disabled={classCardInteractionLocked}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-50 text-slate-500 transition-colors hover:bg-sky-100 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white/5 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-white"
                  aria-label="关闭班级编辑窗口"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
                {formError && (
                  <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                    <AlertCircle size={16} />
                    {formError}
                  </div>
                )}

                {newClassExpanded ? (
                  <div className="space-y-5">
                    <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                      {newClassForm.subject.trim() ? (
                        <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:bg-sky-500/10 dark:text-sky-300">
                          {newClassForm.subject.trim()}
                        </span>
                      ) : null}
                      <span>当前负责老师：{newClassTeacher?.name || '待选择负责老师'}</span>
                      <span>创建时会直接绑定该老师账号</span>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                      <label className="space-y-2 text-sm">
                        <span className="text-slate-500 dark:text-slate-400">班级名称</span>
                        <input
                          type="text"
                          value={newClassForm.name}
                          onChange={(e) => handleFieldChange('new', 'name', e.target.value)}
                          className={workspaceFieldClass}
                          placeholder="如：三班"
                        />
                      </label>
                      <label className="space-y-2 text-sm">
                        <span className="text-slate-500 dark:text-slate-400">学科</span>
                        <input
                          type="text"
                          value={newClassForm.subject}
                          onChange={(e) => handleFieldChange('new', 'subject', e.target.value)}
                          className={workspaceFieldClass}
                          placeholder="如：数学"
                        />
                      </label>
                      <label className="space-y-2 text-sm md:col-span-2">
                        <span className="text-slate-500 dark:text-slate-400">年级</span>
                        <select
                          value={newClassForm.grade}
                          onChange={(e) => handleFieldChange('new', 'grade', e.target.value)}
                          className={workspaceFieldClass}
                        >
                          <option value="">请选择年级</option>
                          {gradeOptions.map((option) => (
                            <option key={option} value={option}>{option}</option>
                          ))}
                        </select>
                      </label>
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
                        <select
                          value={newClassTeacherUserId == null ? '' : String(newClassTeacherUserId)}
                          onChange={(event) => {
                            const nextTeacherUserId = Number(event.target.value);
                            setNewClassTeacherUserId(Number.isFinite(nextTeacherUserId) && nextTeacherUserId > 0 ? nextTeacherUserId : null);
                          }}
                          disabled={classInteractionLocked || newClassFilteredUsers.length === 0}
                          className={workspaceFieldClass}
                        >
                          <option value="">请选择负责老师</option>
                          {newClassFilteredUsers.map((user) => (
                            <option key={`new-${user.id}`} value={user.id}>{user.name}</option>
                          ))}
                        </select>
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
                ) : editingClass && editingFormState ? (
                  <div className="space-y-5">
                    <div className="grid gap-4 lg:grid-cols-[minmax(260px,0.92fr)_minmax(0,1.08fr)] lg:items-start">
                      <div className={`${workspaceCardClass} space-y-4 p-4 sm:p-5`}>
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <h4 className="text-lg font-semibold text-slate-900 dark:text-white">家长绑定邀请码</h4>
                            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">把邀请码发给家长后，家长就能在微信小程序里绑定该班级。</p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => void handleLoadClassInvite(editingClass.id)}
                              disabled={editingInviteLoading || editingInviteResetting}
                              className={workspaceSecondaryButtonClass}
                            >
                              {editingInviteLoading ? '加载中...' : '查看邀请码'}
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleResetClassInvite(editingClass.id)}
                              disabled={editingInviteLoading || editingInviteResetting}
                              className={workspacePrimaryButtonClass}
                            >
                              {editingInviteResetting ? '重置中...' : '重置邀请码'}
                            </button>
                          </div>
                        </div>

                        {editingInviteError ? (
                          <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                            <AlertCircle size={16} />
                            {editingInviteError}
                          </div>
                        ) : null}

                        <div className={`${workspaceSoftCardClass} p-4`}>
                          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">当前邀请码</p>
                          <p className="mt-3 font-mono text-2xl font-bold tracking-[0.3em] text-slate-900 dark:text-white">
                            {editingInviteInfo?.invite_code || (editingInviteLoading ? '加载中' : '未加载')}
                          </p>
                        </div>
                      </div>

                      <div className={`${workspaceCardClass} space-y-4 p-5`}>
                        <div>
                          <h4 className="text-xl font-semibold text-slate-900 dark:text-white">基础信息</h4>
                          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">请分别填写学科、年级和班级名称，系统按「学科 + 年级 + 班级」理解班级，例如：数学七年级三班。</p>
                        </div>

                        <div className="grid gap-4 md:grid-cols-2">
                          <label className="space-y-2 text-sm">
                            <span className="text-slate-500 dark:text-slate-400">班级名称</span>
                            <input
                              type="text"
                              value={editingFormState.name}
                              onChange={(e) => handleFieldChange(editingClass.id, 'name', e.target.value)}
                              className={workspaceFieldClass}
                              placeholder="如：三班"
                            />
                          </label>
                          <label className="space-y-2 text-sm">
                            <span className="text-slate-500 dark:text-slate-400">学科</span>
                            <input
                              type="text"
                              value={editingFormState.subject}
                              onChange={(e) => handleFieldChange(editingClass.id, 'subject', e.target.value)}
                              className={workspaceFieldClass}
                              placeholder="如：数学"
                            />
                          </label>
                          <label className="space-y-2 text-sm md:col-span-2">
                            <span className="text-slate-500 dark:text-slate-400">年级</span>
                            <select
                              value={editingFormState.grade}
                              onChange={(e) => handleFieldChange(editingClass.id, 'grade', e.target.value)}
                              className={workspaceFieldClass}
                            >
                              <option value="">请选择年级</option>
                              {gradeOptions.map((option) => (
                                <option key={option} value={option}>{option}</option>
                              ))}
                            </select>
                          </label>
                        </div>
                      </div>
                    </div>

                    <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
                      {canManageClassTeachers && (
                        <div className={`${workspaceCardClass} space-y-5 p-5`}>
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <h4 className="text-xl font-semibold text-slate-900 dark:text-white">负责老师</h4>
                            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">当前负责老师：{editingTeacherSummary}，可直接更换。</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => loadPage(editingClass.id, { preserveStateOnError: true }).catch(() => undefined)}
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
                            value={editingTeacherSearch}
                            onChange={(e) => handleTeacherSearchChange(editingClass.id, e.target.value)}
                            placeholder="搜索老师"
                            className={`${workspaceFieldClass} rounded-full py-2.5 pl-11 pr-4`}
                          />
                        </label>

                        {users.length === 0 ? (
                          <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                            当前暂无成员，成员通过审批后会出现在这里。
                          </div>
                        ) : editingFilteredUsers.length === 0 ? (
                          <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                            没有匹配到老师，请调整搜索关键词。
                          </div>
                        ) : (
                          <select
                            value={editingCurrentTeacherUserId == null ? '' : String(editingCurrentTeacherUserId)}
                            onChange={(event) => {
                              const nextTeacherUserId = Number(event.target.value);
                              if (!Number.isFinite(nextTeacherUserId) || nextTeacherUserId <= 0 || nextTeacherUserId === editingCurrentTeacherUserId) {
                                return;
                              }
                              void handleSelectTeacherForClass(editingClass.id, nextTeacherUserId);
                            }}
                            disabled={editingTeacherBindingSaving || classInteractionLocked || editingFilteredUsers.length === 0}
                            className={workspaceFieldClass}
                          >
                            <option value="">请选择负责老师</option>
                            {editingFilteredUsers.map((user) => (
                              <option key={`${editingClass.id}-${user.id}`} value={user.id}>{user.name}</option>
                            ))}
                          </select>
                        )}

                          <div className="grid gap-3 border-t border-sky-100/80 pt-5 sm:grid-cols-2 dark:border-white/10">
                            <button
                              type="button"
                              onClick={() => handleDeleteClass(editingClass.id)}
                              disabled={classCardInteractionLocked}
                              className="inline-flex w-full items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-rose-200 bg-rose-50 px-5 py-3 font-semibold text-rose-600 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
                            >
                              <Trash2 size={18} />
                              {deleting ? '删除中...' : '删除当前班级'}
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSaveClass(editingClass.id)}
                              disabled={classCardInteractionLocked}
                              className={`${workspacePrimaryButtonClass} w-full`}
                            >
                              {saving ? '保存中...' : '保存班级'}
                            </button>
                          </div>
                        </div>
                      )}

                      <div className={`${workspaceCardClass} space-y-4 p-5`}>
                        <div>
                          <h4 className="text-xl font-semibold text-slate-900 dark:text-white">编辑学生</h4>
                          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">在这里维护当前班级学生名单。</p>
                        </div>

                        {editingStudentError ? (
                          <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                            <AlertCircle size={16} />
                            {editingStudentError}
                          </div>
                        ) : null}

                        <div className="flex flex-col gap-3 sm:flex-row">
                          <input
                            type="text"
                            value={editingStudentDraftName}
                            onChange={(e) => handleStudentDraftNameChange(editingClass.id, e.target.value)}
                            placeholder="输入学生姓名"
                            className={workspaceFieldClass}
                          />
                          <button
                            type="button"
                            onClick={() => void handleAddStudentToClass(editingClass.id)}
                            disabled={editingStudentSaving}
                            className={workspacePrimaryButtonClass}
                          >
                            {editingStudentSaving ? '处理中...' : '新增学生'}
                          </button>
                        </div>

                        {editingStudentsLoading ? (
                          <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                            正在加载学生...
                          </div>
                        ) : editingStudents.length === 0 ? (
                          <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                            当前班级还没有学生。
                          </div>
                        ) : (
                          <div className="space-y-3">
                            {editingStudents.map((student) => (
                              <div
                                key={student.id}
                                className="flex items-center justify-between gap-3 rounded-2xl border border-sky-100 bg-sky-50/60 px-4 py-3 dark:border-white/10 dark:bg-white/5"
                              >
                                <span className="font-medium text-slate-900 dark:text-white">{student.name}</span>
                                <button
                                  type="button"
                                  onClick={() => void handleDeleteStudentFromClass(editingClass.id, student.id)}
                                  disabled={editingStudentSaving}
                                  className="inline-flex items-center justify-center whitespace-nowrap rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-600 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
                                >
                                  删除学生
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            </motion.div>
          </motion.div>
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
  const [selectedSubjectFilter, setSelectedSubjectFilter] = useState<string>('全部学科');
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

  const claimGradeFilterOptions = ['全部', ...gradeOptions.filter((option) => classes.some((item) => item.grade === option))];
  const claimSubjectFilterOptions = ['全部学科', ...Array.from(new Set(classes.map((item) => item.subject.trim()).filter(Boolean))).map(String).sort((a, b) => a.localeCompare(b, 'zh-CN'))];
  const claimFilterSummary = [
    selectedGradeFilter !== '全部' ? selectedGradeFilter : '',
    selectedSubjectFilter !== '全部学科' ? selectedSubjectFilter : '',
  ].filter(Boolean).join(' / ') || '全部';
  const filteredClasses = classes.filter((item) => {
    if (selectedSubjectFilter !== '全部学科' && item.subject !== selectedSubjectFilter) {
      return false;
    }
    if (selectedGradeFilter === '全部') {
      return true;
    }
    return item.grade === selectedGradeFilter;
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
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <label className="space-y-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              年级筛选
              <select
                value={selectedGradeFilter}
                onChange={(event) => setSelectedGradeFilter(event.target.value)}
                className={`${workspaceFieldClass} w-full`}
              >
                {claimGradeFilterOptions.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
            <label className="space-y-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              学科筛选
              <select
                value={selectedSubjectFilter}
                onChange={(event) => setSelectedSubjectFilter(event.target.value)}
                className={`${workspaceFieldClass} w-full`}
              >
                {claimSubjectFilterOptions.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
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
                    <span className="block truncate font-semibold">{item.name}</span>
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
                Starain，用 AI 赋能教育机构。
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

export default function App() {
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
    classes: '班级管理',
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

  const activeWorkspacePage = getWorkspacePageFallback(currentUser, activePage);

  return (
    <div className="relative min-h-[100svh] overflow-x-hidden bg-[linear-gradient(180deg,#f8fbff_0%,#eef6ff_100%)] text-slate-900 sm:min-h-screen dark:bg-[linear-gradient(180deg,#020617_0%,#0f172a_100%)] dark:text-slate-100">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[-8%] top-[8%] h-80 w-80 rounded-full bg-cyan-200/35 blur-[130px] dark:bg-cyan-500/10" />
        <div className="absolute right-[-10%] top-[12%] h-96 w-96 rounded-full bg-blue-200/30 blur-[150px] dark:bg-blue-500/10" />
        <div className="absolute bottom-[-14%] left-[28%] h-[28rem] w-[28rem] rounded-full bg-white/75 blur-[120px] dark:bg-slate-900/40" />
      </div>
      <div className="relative flex min-h-[100svh] sm:min-h-screen">
        <div className="fixed inset-y-0 left-0 z-30 hidden lg:block">
          <Sidebar
            activePage={activeWorkspacePage}
            currentUser={currentUser}
            onLogout={handleLogout}
            setActivePage={navigateWorkspacePage}
            compact={activeWorkspacePage === 'calendar' || activeWorkspacePage === 'consultation'}
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
              <div className="absolute inset-0 bg-slate-950/45 sm:backdrop-blur-sm" onClick={() => setMobileNavOpen(false)} />
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
                  className="absolute right-3 top-3 z-10 flex h-10 w-10 touch-manipulation items-center justify-center rounded-full border border-sky-200 bg-white text-slate-500 shadow-sm transition-colors hover:bg-sky-50 hover:text-slate-800 dark:border-white/10 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                  aria-label="关闭导航"
                >
                  <X size={18} />
                </button>
                <Sidebar
                  activePage={activeWorkspacePage}
                  currentUser={currentUser}
                  onLogout={handleLogout}
                  setActivePage={navigateWorkspacePage}
                  onNavigate={() => setMobileNavOpen(false)}
                  mobile={true}
                  onProfileUpdated={(u, d) => setCurrentUser((c) => c ? { ...c, username: u, display_name: d } : c)}
                />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
        <main className={cn('flex min-w-0 flex-1 flex-col', activeWorkspacePage === 'calendar' || activeWorkspacePage === 'consultation' ? 'lg:pl-24' : 'lg:pl-72')}>
          <Header
            title={pageTitle[activeWorkspacePage]}
            onGoHome={() => setShowLanding(true)}
            isDark={isDark}
            onToggleDarkMode={() => setIsDark((current) => !current)}
            onOpenSidebar={() => setMobileNavOpen(true)}
          />
          <div className="flex-1">
            <AnimatePresence mode={isMobileViewport ? undefined : 'wait'}>
              <motion.div
                key={activeWorkspacePage}
                initial={isMobileViewport ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={isMobileViewport ? { opacity: 1, y: 0 } : { opacity: 0, y: -6 }}
                transition={isMobileViewport ? { duration: 0 } : { duration: 0.18 }}
              >
                {activeWorkspacePage === 'dashboard' && (
                  <WorkspaceDashboard
                    currentUser={currentUser}
                    setActivePage={navigateWorkspacePage}
                    styles={{
                      pageClass: workspacePageClass,
                      cardClass: workspaceCardClass,
                      primaryButtonClass: workspacePrimaryButtonClass,
                      secondaryButtonClass: workspaceSecondaryButtonClass,
                    }}
                    canOpenAccounts={hasStaffAccess(currentUser.role)}
                  />
                )}
                {activeWorkspacePage === 'review-generation' && canOpenWorkspacePage(currentUser, 'review-generation') && (
                  <ReviewGenerationPage onSuccess={handleReviewGenerationSuccess} currentUser={currentUser} />
                )}
                {activeWorkspacePage === 'class-feedback-generation' && canOpenWorkspacePage(currentUser, 'class-feedback-generation') && <ClassFeedbackGenerationPage currentUser={currentUser} />}
                {activeWorkspacePage === 'consultation' && canOpenWorkspacePage(currentUser, 'consultation') && <ConsultationPage currentUser={currentUser} />}
                {activeWorkspacePage === 'calendar' && canOpenWorkspacePage(currentUser, 'calendar') &&
                  (calendarLoading ? (
                    <div className={`${workspacePageClass}`}>
                      <div className={`${workspaceCardClass} p-8`}>
                        <WorkspaceLoading label="正在整理课程日历..." />
                      </div>
                    </div>
                  ) : (
                    <>
                      {calendarError && (
                        <div className={`${workspacePageClass} pb-0`}>
                          <div className={`${workspaceCardClass} flex items-center gap-2 border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300`}>
                            <AlertCircle size={16} />
                            <span>课程日历加载失败：{calendarError}</span>
                          </div>
                        </div>
                      )}
                      <CourseCalendarPage
                        anchorDate={calendarAnchorDate}
                        today={getTodayIsoDate()}
                        currentUserId={currentUser.id}
                        currentUserRole={currentUser.role}
                        classes={calendarClasses}
                        schedules={calendarSchedules}
                        customItems={calendarCustomItems}
                        customSchedules={calendarCustomSchedules}
                        pageStepDays={calendarPageStepDays}
                        onPageStepDaysChange={handleCalendarPageStepDaysChange}
                        onPreviousPage={handlePreviousCalendarPage}
                        onNextPage={handleNextCalendarPage}
                        onScheduleClass={handleScheduleCalendarClass}
                        onScheduleCustomItem={handleScheduleCalendarCustomItem}
                        onCreateCustomItem={handleCreateCalendarCustomItem}
                        onDeleteCustomItem={handleDeleteCalendarCustomItem}
                        onDeleteSchedule={handleDeleteCalendarSchedule}
                        onDeleteCustomSchedule={handleDeleteCalendarCustomSchedule}
                      />
                    </>
                  ))}
                {activeWorkspacePage === 'smartWrongQuestions' &&
                  canOpenWorkspacePage(currentUser, 'smartWrongQuestions') &&
                  <SmartWrongQuestionsPage currentUser={currentUser} />}
                {activeWorkspacePage === 'classes' && canOpenWorkspacePage(currentUser, 'classes') && (
                  <ClassManagementPage currentUser={currentUser} classBindingTarget={classBindingTarget} onClearClassBindingTarget={() => setClassBindingTarget(null)} />
                )}
                {activeWorkspacePage === 'credit' && hasOwnerAccess(currentUser.role) && <CreditCenterPage currentUser={currentUser} />}
                {activeWorkspacePage === 'accounts' && hasStaffAccess(currentUser.role) && <ApprovalPage currentUser={currentUser} onOpenClassBinding={handleOpenClassBinding} />}
                {activeWorkspacePage === 'settings' && <SettingsPage currentUser={currentUser} onLogout={handleLogout} />}
              </motion.div>
            </AnimatePresence>
          </div>
        </main>
      </div>
    </div>
  );
}
