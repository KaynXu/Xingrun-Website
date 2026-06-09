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
  ChevronRight,
  Info,
  Save,
} from 'lucide-react';
import { motion, AnimatePresence, useReducedMotion } from 'motion/react';
import { CourseCalendarPage } from './CourseCalendarPage';
import type { CourseCalendarCustomItemRecord, CourseCalendarCustomScheduleRecord, CourseCalendarScheduleRecord, CourseCalendarTimeBlock } from './courseCalendarData';
import { getCurrentWeekTuesday } from './courseCalendarData';
import { StudentCenterPage } from './features/student-center/StudentCenterPage';
export {
  resolveTeacherBindingRollbackClassItem,
  resolveTeacherBindingRollbackTeacherBindings,
} from './features/student-center/teacherBindingRules';
import { SmartWrongQuestionsPage } from './SmartWrongQuestionsPage';
import { ClassFeedbackGenerationWorkspace } from './ClassFeedbackGenerationWorkspace';
import { WorkspaceDashboard } from './WorkspaceDashboard';
import { FloatingFilterBar, FloatingOverviewFilter } from './components/FloatingFilterBar';
import {
  academicGradeGroups,
  academicGradeOptions,
  academicStageOptions,
  bridgeStageOptions,
  buildClassDisplayName,
  formatClassDisplayName,
  getAcademicGradeRank,
  getAcademicStageFromGrade,
  inferAcademicCohortYear,
  inferAcademicCohortYearForStage,
  parseBridgeTarget,
  normalizeAcademicGradeLabel,
  normalizeClassNameInput,
  serializeBridgeTarget,
} from './domain/classNaming';
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

export interface ClassItem {
  id: number;
  name: string;
  class_type?: string;
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
  customer_service_added: string;
  customer_service_note: string;
  communication_teacher_added: string;
  communication_teacher_note: string;
  test_taken: string;
  test_note: string;
  test_images: Array<{ url: string; filename: string }>;
  trial_teacher_added: string;
  trial_teacher_note: string;
  trial_taken: string;
  trial_time_slot: string;
  trial_class_id: number | null;
  trial_class_manual: string;
  trial_teacher: string;
  trial_feedback: string;
  success_class_id: number | null;
  teaching_teacher_added: string;
  teaching_teacher: string;
  teaching_teacher_note: string;
  success_class_manual: string;
  enrollment_handoff_note: string;
  student_profile_status: string;
  student_profile_note: string;
  failure_reason: string;
  failure_note: string;
  closing_result: string;
  closed_by_user_id: number | null;
  end_note: string;
  ended_at: string;
  created_at: string;
  updated_at: string;
}

type ConsultationFormValues = Omit<ConsultationRecord, 'id' | 'created_at' | 'updated_at'>;
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
const configurableWorkspacePages: Array<{ id: Page; label: string }> = [
  { id: 'review-generation', label: '复习生成' },
  { id: 'class-feedback-generation', label: '课堂反馈' },
  { id: 'consultation', label: '咨询记录' },
  { id: 'calendar', label: '课程日历' },
  { id: 'smartWrongQuestions', label: '智能错题' },
  { id: 'classes', label: '学管中心' },
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
type ConsultationResultStage = '成功进班' | '试听失败';
const consultationResultStages: ConsultationResultStage[] = ['成功进班', '试听失败'];
const consultationMeetingVersion = 'V2.0';
type ConsultationFlowCardNodeKey =
  | 'customer-service'
  | 'communication-teacher'
  | 'teacher-communication'
  | 'test'
  | 'trial-teacher'
  | 'trial'
  | 'teaching-teacher'
  | 'enter-class'
  | 'over';
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
type ConsultationFilterKey =
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
  customer_service_added: '',
  customer_service_note: '',
  communication_teacher_added: '',
  communication_teacher_note: '',
  test_taken: '',
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
  enrollment_handoff_note: '',
  student_profile_status: '',
  student_profile_note: '',
  failure_reason: '',
  failure_note: '',
  closing_result: '',
  closed_by_user_id: null,
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
    customer_service_added: record.customer_service_added ?? '',
    customer_service_note: record.customer_service_note ?? '',
    communication_teacher_added: record.communication_teacher_added ?? '',
    communication_teacher_note: record.communication_teacher_note ?? '',
    test_taken: record.test_taken ?? '',
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
    enrollment_handoff_note: record.enrollment_handoff_note ?? '',
    student_profile_status: record.student_profile_status ?? '',
    student_profile_note: record.student_profile_note ?? '',
    failure_reason: record.failure_reason ?? '',
    failure_note: record.failure_note ?? '',
    closing_result: record.closing_result ?? '',
    closed_by_user_id: record.closed_by_user_id ?? null,
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
    customer_service_added: record.customer_service_added ?? '',
    customer_service_note: record.customer_service_note ?? '',
    communication_teacher_added: record.communication_teacher_added ?? '',
    communication_teacher_note: record.communication_teacher_note ?? '',
    test_taken: record.test_taken ?? '',
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
    enrollment_handoff_note: record.enrollment_handoff_note ?? '',
    student_profile_status: record.student_profile_status ?? '',
    student_profile_note: record.student_profile_note ?? '',
    failure_reason: record.failure_reason ?? '',
    failure_note: record.failure_note ?? '',
    closing_result: record.closing_result ?? '',
    closed_by_user_id: record.closed_by_user_id ?? null,
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
      { id: 'classes', icon: Home, label: '学管中心' },
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
            title={compact && !mobile ? item.label : undefined}
            onClick={() => {
              setActivePage(item.id as Page);
              onNavigate?.();
            }}
            className={cn(
              'group/nav-item relative flex w-full touch-manipulation items-center gap-3 rounded-2xl px-4 py-3 text-left transition-all duration-200',
              compact && !mobile && 'justify-center px-3',
              activePage === item.id
                ? 'border border-sky-200 bg-white text-sky-700 shadow-[0_16px_36px_rgba(47,128,237,0.08)] dark:border-sky-500/30 dark:bg-white/10 dark:text-sky-300 dark:shadow-[0_16px_36px_rgba(2,6,23,0.35)]'
                : 'border border-transparent text-slate-500 hover:border-sky-100 hover:bg-white/75 hover:text-slate-800 dark:text-slate-400 dark:hover:border-white/10 dark:hover:bg-white/5 dark:hover:text-slate-100',
            )}
          >
            <item.icon size={20} />
            <span className={cn('font-medium', compact && !mobile && 'hidden')}>{item.label}</span>
            {compact && !mobile && (
              <span className="pointer-events-none absolute left-[calc(100%+0.5rem)] top-1/2 z-40 -translate-y-1/2 whitespace-nowrap rounded-lg border border-sky-100 bg-white px-2.5 py-1.5 text-xs font-bold text-slate-700 opacity-0 shadow-[0_10px_24px_rgba(31,42,68,0.14)] transition group-hover/nav-item:opacity-100 dark:border-white/10 dark:bg-slate-900 dark:text-slate-100">
                {item.label}
              </span>
            )}
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

const SubjectSelect = ({
  value,
  onChange,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  className?: string;
}) => {
  return (
    <select
      aria-label="科目"
      value={academicSubjectOptions.includes(value) ? value : ''}
      onChange={(event) => onChange(event.target.value)}
      className={cn(workspaceFieldClass, 'w-full', className)}
    >
      <option value="">选择科目</option>
      {academicSubjectOptions.map((option) => (
        <option key={option} value={option}>{option}</option>
      ))}
    </select>
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
    if (cls?.subject && academicSubjectOptions.includes(cls.subject)) setSubject(cls.subject);
  };

  const handleAnalyze = async () => {
    if (!summaryText.trim()) return;
    setIsAnalyzing(true);
    try {
      const result = await apiFetch<{ subject: string; topic: string; weak_points: string }>('/api/analyze', {
        method: 'POST',
        body: JSON.stringify({ text: summaryText }),
      });
      if (result.subject) setSubject(academicSubjectOptions.includes(result.subject) ? result.subject : '');
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
                <SubjectSelect
                  value={subject}
                  onChange={setSubject}
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

  const selectedClassDisplayName = getCurrentClassDisplayName(selectedClass);
  const sourceSummaryItems = [
    selectedClassDisplayName ? `当前班级：${selectedClassDisplayName}` : '当前班级：未选择',
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
            {getCurrentClassDisplayName(item)}
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
        classNameLabel={selectedClassDisplayName || '未选择班级'}
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
  onStageContextAction,
  onResultContextAction,
  onOverContextAction,
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
  onStageContextAction?: (stage: string) => void;
  onResultContextAction?: () => void;
  onOverContextAction?: () => void;
}) => {
  const longPressTimerRef = useRef<number | null>(null);
  const longPressTriggeredRef = useRef(false);
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
  const clearLongPressTimer = () => {
    if (longPressTimerRef.current !== null) {
      window.clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  };
  useEffect(() => () => clearLongPressTimer(), []);
  const runContextAction = (node: typeof flowNodes[number]) => {
    if (node.disabled) return;
    if (node.type === 'process') onStageContextAction?.(node.key);
    if (node.type === 'result') onResultContextAction?.();
    if (node.type === 'over') onOverContextAction?.();
  };
  const handleContextAction = (event: React.MouseEvent<HTMLButtonElement>, node: typeof flowNodes[number]) => {
    event.preventDefault();
    runContextAction(node);
  };
  const handlePointerDown = (event: React.PointerEvent<HTMLButtonElement>, node: typeof flowNodes[number]) => {
    if (node.disabled || event.pointerType === 'mouse') return;
    longPressTriggeredRef.current = false;
    clearLongPressTimer();
    longPressTimerRef.current = window.setTimeout(() => {
      longPressTriggeredRef.current = true;
      runContextAction(node);
    }, 600);
  };
  const handlePointerEnd = () => clearLongPressTimer();
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
          if (longPressTriggeredRef.current) {
            longPressTriggeredRef.current = false;
            return;
          }
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
              onContextMenu={(event) => handleContextAction(event, node)}
              onPointerDown={(event) => handlePointerDown(event, node)}
              onPointerUp={handlePointerEnd}
              onPointerCancel={handlePointerEnd}
              onPointerLeave={handlePointerEnd}
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
                  接待教师：{form.receiving_teacher || '未选择'}
                </span>
                <select
                  value={form.teacher_id}
                  onChange={(e) => handleTeacherChange(e.target.value)}
                  disabled={readOnly || stageFrozen}
                  className="h-full min-h-10 w-full cursor-pointer appearance-none rounded-2xl bg-transparent px-3 text-transparent outline-none"
                  aria-label="选择接待教师"
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
                <span className={compactEditLabelClass}>学生姓名</span>
                <input value={form.child_name} onChange={(e) => updateField('child_name', e.target.value)} disabled={readOnly} className={fieldClass} placeholder="学生姓名" />
              </label>
              <label className="space-y-2 text-sm">
                <span className={compactEditLabelClass}>咨询年级</span>
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
              <span className={compactEditLabelClass}>家长诉求</span>
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

const ConsultationMeetingWorkbench = ({ currentUser }: { currentUser: CurrentUser }) => {
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

const ConsultationPage = ({ currentUser }: { currentUser: CurrentUser }) => {
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
  const [flowNodeActionRecord, setFlowNodeActionRecord] = useState<ConsultationRecord | null>(null);
  const [flowNodeActionKey, setFlowNodeActionKey] = useState<ConsultationFlowCardNodeKey | null>(null);
  const [flowNodeActionNote, setFlowNodeActionNote] = useState('');
  const [flowNodeActionTeacherId, setFlowNodeActionTeacherId] = useState('');
  const [flowNodeActionMoveCurrent, setFlowNodeActionMoveCurrent] = useState(false);
  const [overResultDialogRecord, setOverResultDialogRecord] = useState<ConsultationRecord | null>(null);
  const [enterClassRecord, setEnterClassRecord] = useState<ConsultationRecord | null>(null);
  const [enterClassMode, setEnterClassMode] = useState<'existing' | 'quick_new_class' | 'converted_without_class'>('existing');
  const [enterClassId, setEnterClassId] = useState('');
  const [enterClassNewType, setEnterClassNewType] = useState('group');
  const [enterClassNewSubject, setEnterClassNewSubject] = useState('');
  const [enterClassNewStage, setEnterClassNewStage] = useState('');
  const [enterClassNewGrade, setEnterClassNewGrade] = useState('');
  const [enterClassNewNumber, setEnterClassNewNumber] = useState('1');
  const [enterClassNewIsBridge, setEnterClassNewIsBridge] = useState(false);
  const [enterClassBridgeFrom, setEnterClassBridgeFrom] = useState('小学');
  const [enterClassBridgeTo, setEnterClassBridgeTo] = useState('初中');
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
    if (typeof window === 'undefined') {
      return undefined;
    }
    const handleMeetingWorkbenchSave = (event: StorageEvent) => {
      if (event.key === 'xr_consultation_meeting_saved_at') {
        load(search).catch(() => undefined);
      }
    };
    window.addEventListener('storage', handleMeetingWorkbenchSave);
    return () => window.removeEventListener('storage', handleMeetingWorkbenchSave);
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
    if (typeof window === 'undefined') {
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set('consultationMeeting', '1');
    window.open(url.toString(), '_blank', 'noopener,noreferrer');
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

  const addCompletedStage = (values: ConsultationFormValues, stage: string): ConsultationFormValues => {
    const currentStages = Array.isArray(values.completed_stages) ? values.completed_stages : [];
    return {
      ...values,
      completed_stages: currentStages.includes(stage) ? currentStages : [...currentStages, stage],
    };
  };

  const moveFlowNodeActionStage = (values: ConsultationFormValues, key: ConsultationFlowCardNodeKey): ConsultationFormValues => {
    const stageByKey: Partial<Record<ConsultationFlowCardNodeKey, string>> = {
      'customer-service': '已加小客服微信',
      'communication-teacher': '已加对应教师微信',
      'teacher-communication': '正在沟通细节',
      test: '待测试',
      'trial-teacher': '加试听教师',
      trial: '待试听',
      'teaching-teacher': '加带课教师',
    };
    const stage = stageByKey[key];
    if (!stage) {
      return values;
    }
    const currentStages = Array.isArray(values.completed_stages) ? values.completed_stages : [];
    return {
      ...values,
      flow_stage: stage,
      completed_stages: currentStages.includes(stage) ? currentStages : [...currentStages, stage],
    };
  };

  const getFlowNodeActionNote = (record: ConsultationRecord, key: ConsultationFlowCardNodeKey): string => {
    if (key === 'customer-service') return record.customer_service_note || '';
    if (key === 'communication-teacher') return record.communication_teacher_note || '';
    if (key === 'teacher-communication') return record.communication_teacher_note || record.follow_up_note || '';
    if (key === 'test') return record.test_note || '';
    if (key === 'trial-teacher') return record.trial_teacher_note || '';
    if (key === 'trial') return record.trial_feedback || '';
    if (key === 'teaching-teacher') return record.teaching_teacher_note || '';
    return '';
  };

  const consultationStageToFlowNodeKey = (stage: string): ConsultationFlowCardNodeKey => {
    if (stage === '已加小客服微信') return 'customer-service';
    if (stage === '已加对应教师微信') return 'communication-teacher';
    if (stage === '正在沟通细节') return 'teacher-communication';
    if (stage === '待测试') return 'test';
    if (stage === '加试听教师') return 'trial-teacher';
    if (stage === '待试听') return 'trial';
    if (stage === '加带课教师') return 'teaching-teacher';
    return 'teacher-communication';
  };

  const openConsultationFlowNode = (record: ConsultationRecord, key: ConsultationFlowCardNodeKey, moveCurrent = false) => {
    if (!canEditConsultations || isBusy) {
      openViewModal(record);
      return;
    }
    if (key === 'over') {
      if (isConsultationEnded(record.flow_stage)) {
        setRestoreConfirmRecord(record);
      } else {
        setOverResultDialogRecord(record);
      }
      return;
    }
    if (key === 'enter-class') {
      openEnterClassDialog(record);
      return;
    }
    setFlowNodeActionRecord(record);
    setFlowNodeActionKey(key);
    setFlowNodeActionMoveCurrent(moveCurrent);
    setFlowNodeActionNote(getFlowNodeActionNote(record, key));
    setFlowNodeActionTeacherId(
      key === 'communication-teacher'
        ? record.teacher_id || ''
        : key === 'trial-teacher'
          ? record.trial_teacher || ''
          : key === 'teaching-teacher'
            ? record.teaching_teacher || ''
            : '',
    );
    setError('');
  };

  const closeFlowNodeActionDialog = () => {
    setFlowNodeActionRecord(null);
    setFlowNodeActionKey(null);
    setFlowNodeActionNote('');
    setFlowNodeActionTeacherId('');
    setFlowNodeActionMoveCurrent(false);
  };

  const getEnterClassDefaults = (record: ConsultationRecord) => {
    const normalizedGrade = normalizeAcademicGradeLabel(record.grade || '');
    const stage = getAcademicStageFromGrade(normalizedGrade) || studentCenterStageOptions[0] || '';
    const gradeOptionsForStage = stage ? academicGradeGroups[stage as keyof typeof academicGradeGroups] || academicGradeOptions : academicGradeOptions;
    return {
      subject: academicSubjectOptions.includes(record.consultation_subject) ? record.consultation_subject : '',
      stage,
      grade: gradeOptionsForStage.includes(normalizedGrade) ? normalizedGrade : gradeOptionsForStage[0] || normalizedGrade,
      classNumber: '1',
      bridgeFrom: stage === '初中' || stage === '高中' ? stage : '小学',
      bridgeTo: stage === '高中' ? '高中' : '初中',
    };
  };

  const openEnterClassDialog = (record: ConsultationRecord) => {
    const defaults = getEnterClassDefaults(record);
    setEnterClassRecord(record);
    setEnterClassMode(record.success_class_id ? 'existing' : 'existing');
    setEnterClassId(record.success_class_id ? String(record.success_class_id) : '');
    setEnterClassNewType('group');
    setEnterClassNewSubject(defaults.subject);
    setEnterClassNewStage(defaults.stage);
    setEnterClassNewGrade(defaults.grade);
    setEnterClassNewNumber(defaults.classNumber);
    setEnterClassNewIsBridge(false);
    setEnterClassBridgeFrom(defaults.bridgeFrom);
    setEnterClassBridgeTo(defaults.bridgeTo);
    setError('');
  };

  const closeEnterClassDialog = () => {
    setEnterClassRecord(null);
    setEnterClassMode('existing');
    setEnterClassId('');
    setEnterClassNewType('group');
    setEnterClassNewSubject('');
    setEnterClassNewStage('');
    setEnterClassNewGrade('');
    setEnterClassNewNumber('1');
    setEnterClassNewIsBridge(false);
    setEnterClassBridgeFrom('小学');
    setEnterClassBridgeTo('初中');
  };

  const handleSaveFlowNodeAction = async () => {
    if (!flowNodeActionRecord || !flowNodeActionKey) {
      return;
    }
    const record = flowNodeActionRecord;
    const selectedTeacher = consultationTeachers.find((teacher) => teacher.teacher_id === flowNodeActionTeacherId || teacher.display_name === flowNodeActionTeacherId);
    let values = toConsultationFormValues(record);
    if (flowNodeActionKey === 'customer-service') {
      values = addCompletedStage({ ...values, customer_service_added: 'yes', customer_service_note: flowNodeActionNote }, '已加小客服微信');
    } else if (flowNodeActionKey === 'communication-teacher') {
      values = addCompletedStage({
        ...values,
        communication_teacher_added: 'yes',
        communication_teacher_note: flowNodeActionNote,
        teacher_id: selectedTeacher?.teacher_id || flowNodeActionTeacherId || values.teacher_id,
        receiving_teacher: selectedTeacher?.display_name || values.receiving_teacher,
      }, '已加对应教师微信');
    } else if (flowNodeActionKey === 'teacher-communication') {
      values = addCompletedStage({ ...values, communication_teacher_note: flowNodeActionNote, follow_up_note: flowNodeActionNote || values.follow_up_note }, '正在沟通细节');
    } else if (flowNodeActionKey === 'test') {
      values = addCompletedStage({ ...values, test_taken: '是', test_note: flowNodeActionNote }, '待测试');
    } else if (flowNodeActionKey === 'trial-teacher') {
      values = {
        ...values,
        trial_teacher_added: 'yes',
        trial_teacher: selectedTeacher?.display_name || flowNodeActionTeacherId || values.trial_teacher,
        trial_teacher_note: flowNodeActionNote,
      };
    } else if (flowNodeActionKey === 'trial') {
      values = addCompletedStage({ ...values, trial_taken: '是', trial_feedback: flowNodeActionNote }, '待试听');
    } else if (flowNodeActionKey === 'teaching-teacher') {
      values = {
        ...values,
        teaching_teacher_added: 'yes',
        teaching_teacher: selectedTeacher?.display_name || flowNodeActionTeacherId || values.teaching_teacher,
        teaching_teacher_note: flowNodeActionNote,
      };
    }
    if (flowNodeActionMoveCurrent) {
      values = moveFlowNodeActionStage(values, flowNodeActionKey);
    }
    closeFlowNodeActionDialog();
    await saveInlineConsultationUpdate(record, values, '更新咨询流程失败');
  };

  const handleCloseConsultationWithResult = async (record: ConsultationRecord, result: 'success' | 'failed') => {
    let values = toConsultationFormValues(record);
    if (result === 'success') {
      values = setConsultationResultStage({
        ...values,
        closing_result: 'success',
        success_class_manual: values.success_class_manual || (values.success_class_id ? '' : '班级待补充'),
        student_profile_status: values.student_profile_status || 'needs_completion',
      }, '成功进班');
    } else {
      values = {
        ...values,
        closing_result: 'failed',
        failure_reason: values.failure_reason || '暂未转化',
      };
    }
    setOverResultDialogRecord(null);
    await saveInlineConsultationUpdate(record, endConsultationValues(values), '结束咨询失败');
  };

  const handleSubmitEnterClass = async () => {
    if (!enterClassRecord) {
      return;
    }
    const record = enterClassRecord;
    const quickClassGradeOptions = enterClassNewStage
      ? academicGradeGroups[enterClassNewStage as keyof typeof academicGradeGroups] || academicGradeOptions
      : academicGradeOptions;
    const quickClassGrade = normalizeAcademicGradeLabel(enterClassNewGrade || record.grade || '');
    const quickClassBridgeTarget = serializeBridgeTarget(enterClassBridgeFrom, enterClassBridgeTo);
    const quickClassCohortStage = enterClassNewIsBridge ? parseBridgeTarget(quickClassBridgeTarget, enterClassNewStage || quickClassGrade).toStage : enterClassNewStage || getAcademicStageFromGrade(quickClassGrade) || '';
    const quickClassCohortYear = inferAcademicCohortYearForStage(quickClassGrade, quickClassCohortStage);
    const quickClassGeneratedName = buildClassDisplayName({
      class_type: enterClassNewType,
      subject: enterClassNewSubject || record.consultation_subject,
      stage: enterClassNewStage || getAcademicStageFromGrade(quickClassGrade),
      current_grade: quickClassGrade,
      grade: quickClassGrade,
      class_number: enterClassNewType === 'group' ? enterClassNewNumber : '',
      cohort_year: quickClassCohortYear,
      show_cohort_year: false,
      is_bridge: enterClassNewIsBridge,
      bridge_target: quickClassBridgeTarget,
      selected_student_names: record.child_name ? [record.child_name] : [],
    });
    const payload = enterClassMode === 'existing'
      ? { mode: enterClassMode, class_id: Number(enterClassId) }
      : enterClassMode === 'quick_new_class'
        ? {
          mode: enterClassMode,
          class_name: quickClassGeneratedName,
          subject: enterClassNewSubject || record.consultation_subject,
          grade: quickClassGrade,
          class_type: enterClassNewType,
          stage: enterClassNewStage || getAcademicStageFromGrade(quickClassGrade),
          current_grade: quickClassGradeOptions.includes(quickClassGrade) ? quickClassGrade : quickClassGradeOptions[0] || quickClassGrade,
          class_number: enterClassNewType === 'group' ? enterClassNewNumber : '',
          cohort_year: quickClassCohortYear,
          show_cohort_year: false,
          is_bridge: enterClassNewIsBridge,
          bridge_target: enterClassNewIsBridge ? quickClassBridgeTarget : '',
          content_track: '',
          teaching_teacher: record.teaching_teacher,
        }
        : { mode: enterClassMode };
    setSubmitting(true);
    setError('');
    try {
      const result = await apiFetch<{ item: ConsultationRecord }>(`/api/consultations/${record.id}/enter-class`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setRecords((current) => current.map((item) => (item.id === record.id ? normalizeConsultationRecord(result.item) : item)));
      if (enterClassMode === 'quick_new_class') {
        apiFetch<ClassItem[]>('/api/classes')
          .then((items) => setClasses(items))
          .catch(() => undefined);
      }
      closeEnterClassDialog();
    } catch (err) {
      setError(err instanceof Error ? err.message : '进班失败');
    } finally {
      setSubmitting(false);
    }
  };

  const renderConsultationIconActions = (record: ConsultationRecord, busy: boolean, compact = false) => {
    const frozen = isConsultationEnded(record.flow_stage);
    const sizeClass = compact ? 'h-7 w-7' : 'h-8 w-8';
    const iconSize = compact ? 12 : 13;
    return (
      <div className="flex shrink-0 items-center justify-end gap-1">
        <button
          type="button"
          onClick={() => openViewModal(record)}
          className={`${sizeClass} flex items-center justify-center rounded-full border border-sky-100 bg-white/85 text-slate-600 shadow-[0_4px_10px_rgba(14,165,233,0.10)] transition hover:bg-sky-50 hover:text-sky-700 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10`}
          title="查看"
          aria-label="查看咨询"
        >
          <Eye size={iconSize} />
        </button>
        {canEditConsultations && (
          <button
            type="button"
            onClick={() => openEditModal(record)}
            className={`${sizeClass} flex items-center justify-center rounded-full border border-sky-100 bg-sky-50/85 text-sky-700 shadow-[0_4px_10px_rgba(14,165,233,0.10)] transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:bg-sky-400/10 dark:text-sky-200 dark:hover:bg-sky-400/20`}
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
    return (
      <ConsultationFlowBar
        mode="list"
        stage={record.flow_stage}
        completedStages={record.completed_stages}
        editable={canEditConsultations && !busy && !frozen}
        showOver
        overDisabled={!canEditConsultations || busy}
        onStageClick={(stage) => openConsultationFlowNode(record, consultationStageToFlowNodeKey(stage), false)}
        onStageDoubleClick={(stage) => openConsultationFlowNode(record, consultationStageToFlowNodeKey(stage), true)}
        onStageContextAction={(stage) => openConsultationFlowNode(record, consultationStageToFlowNodeKey(stage), true)}
        onResultChange={(stage) => handleInlineResultChange(record, stage)}
        onResultClick={() => openConsultationFlowNode(record, 'enter-class', false)}
        onResultDoubleClick={() => openConsultationFlowNode(record, 'enter-class', true)}
        onResultContextAction={() => openConsultationFlowNode(record, 'enter-class', true)}
        onOverClick={() => openConsultationFlowNode(record, 'over', false)}
        onOverDoubleClick={() => openConsultationFlowNode(record, 'over', true)}
        onOverContextAction={() => openConsultationFlowNode(record, 'over', true)}
      />
    );
  };

  const renderB3MobileTimeline = (record: ConsultationRecord, busy: boolean) => {
    const currentStage = record.flow_stage || consultationFlowStages[0];
    const frozen = isConsultationEnded(currentStage);
    const completedSet = new Set(record.completed_stages || []);
    if (!frozen && consultationProcessStages.includes(currentStage)) {
      completedSet.add(currentStage);
    }
    const currentProcessIndex = consultationProcessStages.indexOf(currentStage);
    const resultStage = isConsultationResultStage(currentStage)
      ? currentStage
      : (record.completed_stages || []).find(isConsultationResultStage) || '';
    const resultActive = isConsultationResultStage(currentStage);
    const resultCompleted = Boolean(resultStage) && currentProcessIndex < 0;
    const timelineItems = [
      ...consultationProcessStages.map((stageItem) => {
        const stageIndex = consultationProcessStages.indexOf(stageItem);
        const isCurrent = stageItem === currentStage;
        const isAfterCurrentProcess = currentProcessIndex >= 0 && stageIndex > currentProcessIndex;
        return {
          key: stageItem,
          label: consultationStageShortLabel(stageItem),
          active: isCurrent,
          completed: completedSet.has(stageItem) && !isAfterCurrentProcess,
          disabled: frozen || busy || !canEditConsultations,
          onClick: () => handleInlineStageToggle(record, stageItem),
          onDoubleClick: () => handleInlineStageMove(record, stageItem),
        };
      }),
      {
        key: 'consultation-result',
        label: consultationResultShortLabel(resultStage) || '进',
        active: resultActive,
        completed: resultCompleted,
        disabled: frozen || busy || !canEditConsultations,
        onClick: () => handleInlineResultClick(record),
        onDoubleClick: () => handleInlineResultChange(record, '成功进班'),
      },
    ];

    return (
      <div className="min-w-0 pb-0.5">
        <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_minmax(2.9rem,3.75rem)] items-center gap-1.5">
          <div className="relative grid min-w-0 grid-cols-6 items-start gap-1 px-1 pt-1">
            <span className="absolute left-3 right-3 top-[0.68rem] h-px bg-[#D9EEF7]" aria-hidden="true" />
            {timelineItems.map((item) => (
              <button
                key={item.key}
                type="button"
                disabled={item.disabled}
                onClick={item.onClick}
                onDoubleClick={item.onDoubleClick}
                className="relative z-10 flex min-w-0 flex-col items-center gap-0.5 disabled:cursor-default"
                title={item.key === 'consultation-result' ? resultStage || '成功进班' : item.key}
              >
                <span
                  className={`flex h-[18px] w-[18px] items-center justify-center rounded-full border text-[10px] font-extrabold leading-none transition ${
                    item.active
                      ? 'border-[#0EA5E9] bg-[#0EA5E9] text-white shadow-[0_0_0_3px_rgba(14,165,233,0.16)]'
                      : item.completed
                        ? 'border-[#22B981] bg-[#22B981] text-white'
                        : 'border-slate-300 bg-white text-transparent'
                  }`}
                >
                  {item.active ? (item.key === 'consultation-result' ? '☀' : item.label) : item.completed ? '✓' : ''}
                </span>
                <span className={`truncate text-[10px] font-bold leading-4 ${item.active ? 'text-[#0EA5E9]' : item.completed ? 'text-[#0A8F65]' : 'text-[#7188A6]'}`}>
                  {item.label}
                </span>
              </button>
            ))}
          </div>
          {renderOverButton(record, busy, 'h-8 px-1.5 text-[10px]')}
        </div>
      </div>
    );
  };

  const renderB3FlowStrip = (record: ConsultationRecord, busy: boolean, mobile = false) => {
    const frozen = isConsultationEnded(record.flow_stage);
    return (
      <div className={`min-w-0 overflow-visible ${frozen ? 'opacity-75' : ''}`}>
        {renderInlineFlow(record, busy)}
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
    const endedAsSuccess = record.closing_result === 'success' || consultationHasResult(record, '成功进班');
    const endedAsFailed = record.closing_result === 'failed';
    if (record.flow_stage === '成功进班') {
      return { label: '☀️ 成功进班', className: 'bg-sky-500 text-white shadow-[0_8px_18px_rgba(14,165,233,0.22)]' };
    }
    if (record.flow_stage === '试听失败') {
      return { label: '😢 试听未成', className: 'bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-300' };
    }
    if (record.flow_stage === '咨询结束') {
      if (endedAsSuccess) {
        return { label: 'OVER', className: 'bg-emerald-500 text-white shadow-[0_8px_18px_rgba(34,197,94,0.22)]' };
      }
      if (endedAsFailed) {
        return { label: 'OVER', className: 'bg-rose-500 text-white shadow-[0_8px_18px_rgba(244,63,94,0.22)]' };
      }
      return { label: 'OVER', className: 'bg-rose-500 text-white shadow-[0_8px_18px_rgba(244,63,94,0.22)]' };
    }
    return { label: '未选择结果', className: 'bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-300' };
  };

  const renderOverButton = (record: ConsultationRecord, busy: boolean, className = '') => {
    const successOver = isConsultationEnded(record.flow_stage) && (record.closing_result === 'success' || consultationHasResult(record, '成功进班'));
    return (
      <button
        type="button"
        onClick={() => handleInlineEndConsultation(record)}
        className={`inline-flex min-w-0 items-center justify-center whitespace-nowrap rounded-lg border font-extrabold transition disabled:cursor-not-allowed disabled:opacity-60 ${
          successOver
            ? 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
            : 'border-rose-200 bg-rose-50 text-[#F45B7A] hover:bg-rose-100'
        } ${className}`}
        disabled={!canEditConsultations || busy}
      >
        OVER
      </button>
    );
  };

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
    const frozen = isConsultationEnded(record.flow_stage);
    const sectionLabel = getVisibleRecordSectionLabel(record, index);
    return (
      <React.Fragment key={record.id}>
        {sectionLabel && <div className="px-1 pt-1 text-[11px] font-bold tracking-[0.16em] text-slate-400">{sectionLabel}</div>}
        <article className="overflow-hidden rounded-[14px] border border-[#D9EEF7] bg-white shadow-[0_6px_18px_rgba(31,42,68,0.04)] dark:border-white/10 dark:bg-slate-950/70">
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
            {renderConsultationDetail(needDetail, followUpNote)}
            {renderTimeRow(record)}
          </div>
          <div className="grid grid-cols-[0.875rem_minmax(0,1fr)] items-center gap-2.5 border-t border-[#EEF7FC] bg-[#F9FDFF] px-4 py-3 dark:border-white/10 dark:bg-white/[0.03]">
            <ConsultationStatusLamp stage={record.flow_stage} />
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
    const frozen = isConsultationEnded(record.flow_stage);
    const sectionLabel = getVisibleRecordSectionLabel(record, index);
    return (
      <React.Fragment key={record.id}>
        {sectionLabel && <div className="px-1 pt-1 text-[11px] font-bold tracking-[0.16em] text-slate-400">{sectionLabel}</div>}
        <article className="overflow-hidden rounded-[14px] border border-[#D9EEF7] bg-white shadow-[0_6px_18px_rgba(31,42,68,0.04)] dark:border-white/10 dark:bg-slate-950/70">
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
            {renderConsultationDetail(needDetail, followUpNote)}
            {renderTimeRow(record)}
          </div>
          <div className="grid grid-cols-[0.875rem_minmax(0,1fr)] items-center gap-2 border-t border-[#EEF7FC] bg-[#F9FDFF] px-4 py-3 dark:border-white/10 dark:bg-white/[0.03]">
            <ConsultationStatusLamp stage={record.flow_stage} />
            {renderB3FlowStrip(record, busy)}
          </div>
        </article>
      </React.Fragment>
    );
  };

  const renderMobileConsultationCard = (record: ConsultationRecord, index: number) => {
    const busy = isBusy && selectedRecord?.id === record.id;
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
        <article className="relative space-y-3 rounded-[14px] border border-[#D9EEF7] bg-white p-3.5 shadow-[0_6px_18px_rgba(31,42,68,0.04)] dark:border-white/10 dark:bg-slate-950/70">
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
                      disabled={!canEditConsultations || busy || isConsultationEnded(record.flow_stage)}
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
          {renderConsultationDetail(needDetail, followUpNote, true)}
          {renderTimeRow(record, true)}
          <div className="space-y-2.5">
            <div className="grid grid-cols-[1rem_minmax(0,1fr)] items-center gap-2">
              <ConsultationStatusLamp stage={record.flow_stage} />
              <div className="min-w-0 overflow-visible">{renderB3FlowStrip(record, busy, true)}</div>
            </div>
            {canEditConsultations && (
              <div className={canManage ? 'grid grid-cols-1 gap-2.5' : 'hidden'}>
                {renderDeleteButton(record, busy)}
              </div>
            )}
          </div>
        </article>
      </React.Fragment>
    );
  };

  const flowNodeActionTitle =
    flowNodeActionKey === 'customer-service' ? '客服沟通情况'
    : flowNodeActionKey === 'communication-teacher' ? '选择沟通教师'
    : flowNodeActionKey === 'teacher-communication' ? '教师沟通情况'
    : flowNodeActionKey === 'test' ? '测试情况'
    : flowNodeActionKey === 'trial-teacher' ? '选择试听教师'
    : flowNodeActionKey === 'trial' ? '试听情况'
    : flowNodeActionKey === 'teaching-teacher' ? '选择带课教师'
    : '';
  const flowNodeActionNeedsTeacher =
    flowNodeActionKey === 'communication-teacher'
    || flowNodeActionKey === 'trial-teacher'
    || flowNodeActionKey === 'teaching-teacher';
  const enterClassNewGradeOptions = enterClassNewStage
    ? academicGradeGroups[enterClassNewStage as keyof typeof academicGradeGroups] || academicGradeOptions
    : academicGradeOptions;
  const enterClassNormalizedGrade = normalizeAcademicGradeLabel(enterClassNewGrade || enterClassRecord?.grade || '');
  const enterClassBridgeTarget = serializeBridgeTarget(enterClassBridgeFrom, enterClassBridgeTo);
  const enterClassCohortStage = enterClassNewIsBridge ? parseBridgeTarget(enterClassBridgeTarget, enterClassNewStage || enterClassNormalizedGrade).toStage : enterClassNewStage || getAcademicStageFromGrade(enterClassNormalizedGrade) || '';
  const enterClassPreviewName = enterClassRecord ? buildClassDisplayName({
    class_type: enterClassNewType,
    subject: enterClassNewSubject || enterClassRecord.consultation_subject,
    stage: enterClassNewStage || getAcademicStageFromGrade(enterClassNormalizedGrade),
    current_grade: enterClassNormalizedGrade,
    grade: enterClassNormalizedGrade,
    class_number: enterClassNewType === 'group' ? enterClassNewNumber : '',
    cohort_year: inferAcademicCohortYearForStage(enterClassNormalizedGrade, enterClassCohortStage),
    show_cohort_year: false,
    is_bridge: enterClassNewIsBridge,
    bridge_target: enterClassBridgeTarget,
    selected_student_names: enterClassRecord.child_name ? [enterClassRecord.child_name] : [],
  }) : '';
  const enterClassModeCards: Array<{
    mode: typeof enterClassMode;
    label: string;
    description: string;
    icon: React.ReactNode;
    tone: string;
  }> = [
    {
      mode: 'existing',
      label: '已有班级',
      description: '从当前班级列表选择，立即建立学员档案。',
      icon: <Library size={15} />,
      tone: 'text-sky-600 bg-sky-50 dark:bg-sky-400/10 dark:text-sky-200',
    },
    {
      mode: 'quick_new_class',
      label: '快速建班',
      description: '沿用学员中心规则生成班名，再完成进班。',
      icon: <PlusCircle size={15} />,
      tone: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-400/10 dark:text-emerald-200',
    },
    {
      mode: 'converted_without_class',
      label: '转化待进班',
      description: '先记为成功，班级和档案稍后补齐。',
      icon: <AlertCircle size={15} />,
      tone: 'text-amber-600 bg-amber-50 dark:bg-amber-400/10 dark:text-amber-100',
    },
  ];
  const handleEnterClassStageChange = (stage: string) => {
    const nextGradeOptions = academicGradeGroups[stage as keyof typeof academicGradeGroups] || academicGradeOptions;
    setEnterClassNewStage(stage);
    setEnterClassNewGrade((current) => nextGradeOptions.includes(normalizeAcademicGradeLabel(current)) ? normalizeAcademicGradeLabel(current) : nextGradeOptions[0] || '');
    setEnterClassBridgeFrom(stage === '初中' || stage === '高中' ? stage : '小学');
    setEnterClassBridgeTo(stage === '高中' ? '高中' : '初中');
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
            {canOpenMeetingWorkbench ? (
              <button
                type="button"
                onClick={openConsultationMeetingWorkbench}
                className={`${workspaceSecondaryButtonClass} h-10 w-full min-w-0 !gap-1 !px-1 !py-2 text-[11px] sm:text-xs`}
              >
                <ShieldCheck size={14} />
                面对面模式
              </button>
            ) : (
              !canOpenMeetingWorkbench && (
                <button
                  type="button"
                  onClick={() => load(search).catch(() => undefined)}
                  className={`${workspaceSecondaryButtonClass} h-10 w-full min-w-0 !gap-1 !px-1 !py-2 text-[11px] sm:text-xs`}
                >
                  <RefreshCw size={14} />
                  刷新
                </button>
              )
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
            onRequestEdit={selectedRecord ? () => openEditModal(selectedRecord) : undefined}
          />
        )}
        {flowNodeActionRecord && flowNodeActionKey && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 px-4"
            onClick={(event) => event.target === event.currentTarget && closeFlowNodeActionDialog()}
          >
            <div className="w-full max-w-md rounded-3xl border border-sky-100 bg-white p-5 shadow-[0_28px_80px_rgba(15,23,42,0.22)] dark:border-white/10 dark:bg-slate-900">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-base font-extrabold text-slate-900 dark:text-white">{flowNodeActionTitle}</p>
                  <p className="mt-1 text-xs font-semibold text-slate-400">
                    {flowNodeActionRecord.child_name || '未命名学生'}
                    {flowNodeActionMoveCurrent ? ' · 保存后设为当前阶段' : ' · 仅补充信息'}
                  </p>
                </div>
                <button type="button" onClick={closeFlowNodeActionDialog} className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 text-slate-400 hover:bg-slate-50 dark:border-white/10 dark:hover:bg-white/10">
                  <X size={15} />
                </button>
              </div>
              <div className="mt-4 space-y-3">
                {flowNodeActionNeedsTeacher && (
                  <label className="block">
                    <span className="text-xs font-bold text-slate-500 dark:text-slate-300">
                      {flowNodeActionKey === 'communication-teacher' ? '选择沟通教师' : flowNodeActionKey === 'trial-teacher' ? '选择试听教师' : '选择带课教师'}
                    </span>
                    <select
                      value={flowNodeActionTeacherId}
                      onChange={(event) => setFlowNodeActionTeacherId(event.target.value)}
                      className={`${workspaceFieldClass} mt-1 w-full rounded-xl px-3 py-2`}
                    >
                      <option value="">可先不选</option>
                      {consultationTeachers.map((teacher) => (
                        <option key={teacher.teacher_id} value={teacher.teacher_id}>{teacher.display_name}</option>
                      ))}
                    </select>
                  </label>
                )}
                <label className="block">
                  <span className="text-xs font-bold text-slate-500 dark:text-slate-300">
                    {flowNodeActionKey === 'customer-service' ? '客服沟通情况'
                      : flowNodeActionKey === 'teacher-communication' ? '教师沟通情况'
                      : flowNodeActionKey === 'test' ? '测试情况'
                      : flowNodeActionKey === 'trial' ? '试听情况'
                      : '补充情况'}
                  </span>
                  <textarea
                    value={flowNodeActionNote}
                    onChange={(event) => setFlowNodeActionNote(event.target.value)}
                    rows={4}
                    className={`${workspaceFieldClass} mt-1 min-h-[6rem] w-full rounded-xl px-3 py-2`}
                    placeholder="可以只写一句关键进展，也可以先留空。"
                  />
                </label>
              </div>
              <div className="mt-5 grid grid-cols-2 gap-3">
                <button type="button" onClick={handleSaveFlowNodeAction} className={workspacePrimaryButtonClass}>
                  保存
                </button>
                <button type="button" onClick={closeFlowNodeActionDialog} className={workspaceSecondaryButtonClass}>
                  取消
                </button>
              </div>
            </div>
          </motion.div>
        )}
        {enterClassRecord && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 px-4"
            onClick={(event) => event.target === event.currentTarget && closeEnterClassDialog()}
          >
            <div className="w-full max-w-lg rounded-3xl border border-sky-100 bg-white p-5 shadow-[0_28px_80px_rgba(15,23,42,0.22)] dark:border-white/10 dark:bg-slate-900">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-base font-extrabold text-slate-900 dark:text-white">进班与学员档案</p>
                  <p className="mt-1 text-xs font-semibold text-slate-400">{enterClassRecord.child_name || '未命名学生'} · {enterClassRecord.consultation_subject || '未填科目'} / {enterClassRecord.grade || '未填年级'}</p>
                </div>
                <button type="button" onClick={closeEnterClassDialog} className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 text-slate-400 hover:bg-slate-50 dark:border-white/10 dark:hover:bg-white/10">
                  <X size={15} />
                </button>
              </div>

              <div className="mt-4 grid gap-2 sm:grid-cols-3">
                {enterClassModeCards.map((item) => (
                  <button
                    key={item.mode}
                    type="button"
                    onClick={() => setEnterClassMode(item.mode)}
                    className={cn(
                      'min-h-[5.25rem] rounded-2xl border px-3 py-2.5 text-left transition',
                      enterClassMode === item.mode
                        ? 'border-sky-300 bg-sky-50 text-slate-900 shadow-[0_10px_24px_rgba(14,165,233,0.14)] ring-1 ring-sky-100 dark:border-sky-300/40 dark:bg-sky-400/10 dark:text-white dark:ring-sky-400/10'
                        : 'border-slate-200 bg-white text-slate-500 hover:border-sky-200 hover:bg-sky-50/50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10',
                    )}
                  >
                    <span className="flex items-center gap-2">
                      <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-xl ${item.tone}`}>
                        {item.icon}
                      </span>
                      <span className="text-sm font-extrabold">{item.label}</span>
                    </span>
                    <span className="mt-2 block text-[11px] font-semibold leading-4 text-slate-500 dark:text-slate-300">
                      {item.description}
                    </span>
                  </button>
                ))}
              </div>

              <div className="mt-4 space-y-3">
                {enterClassMode === 'existing' && (
                  <label className="block rounded-2xl border border-sky-100 bg-sky-50/55 p-3 dark:border-sky-400/15 dark:bg-sky-400/10">
                    <span className="text-xs font-bold text-slate-500 dark:text-slate-300">已有班级</span>
                    <select
                      value={enterClassId}
                      onChange={(event) => setEnterClassId(event.target.value)}
                      className={`${workspaceFieldClass} mt-1 w-full rounded-xl px-3 py-2`}
                    >
                      <option value="">请选择班级</option>
                      {classes.map((item) => (
                        <option key={item.id} value={item.id}>{getCurrentClassDisplayName(item, true)}</option>
                      ))}
                    </select>
                  </label>
                )}
                {enterClassMode === 'quick_new_class' && (
                  <div className="rounded-2xl border border-emerald-100 bg-emerald-50/45 p-3 dark:border-emerald-400/15 dark:bg-emerald-400/10">
                    <p className="mb-3 text-xs font-extrabold text-emerald-700 dark:text-emerald-100">快速建班</p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      <label className="block">
                        <span className="text-xs font-bold text-slate-500 dark:text-slate-300">班型</span>
                        <select
                          value={enterClassNewType}
                          onChange={(event) => setEnterClassNewType(event.target.value)}
                          className={`${workspaceFieldClass} mt-1 min-h-10 w-full rounded-xl px-3 py-2 text-sm leading-5`}
                        >
                          <option value="group">多人班课</option>
                          <option value="1v1">1v1 小课</option>
                          <option value="1v2">1v2 小课</option>
                          <option value="1v3">1v3 小课</option>
                        </select>
                      </label>
                      <label className="block">
                        <span className="text-xs font-bold text-slate-500 dark:text-slate-300">学科</span>
                        <select
                          value={academicSubjectOptions.includes(enterClassNewSubject) ? enterClassNewSubject : ''}
                          onChange={(event) => setEnterClassNewSubject(event.target.value)}
                          className={`${workspaceFieldClass} mt-1 min-h-10 w-full rounded-xl px-3 py-2 text-sm leading-5`}
                        >
                          <option value="">请选择学科</option>
                          {academicSubjectOptions.map((option) => (
                            <option key={option} value={option}>{option}</option>
                          ))}
                        </select>
                      </label>
                      <label className="block">
                        <span className="text-xs font-bold text-slate-500 dark:text-slate-300">学段</span>
                        <select
                          value={enterClassNewStage}
                          onChange={(event) => handleEnterClassStageChange(event.target.value)}
                          className={`${workspaceFieldClass} mt-1 min-h-10 w-full rounded-xl px-3 py-2 text-sm leading-5`}
                        >
                          {studentCenterStageOptions.map((option) => (
                            <option key={option} value={option}>{option}</option>
                          ))}
                        </select>
                      </label>
                      <label className="block">
                        <span className="text-xs font-bold text-slate-500 dark:text-slate-300">年级</span>
                        <select
                          value={enterClassNewGradeOptions.includes(enterClassNormalizedGrade) ? enterClassNormalizedGrade : ''}
                          onChange={(event) => setEnterClassNewGrade(event.target.value)}
                          className={`${workspaceFieldClass} mt-1 min-h-10 w-full rounded-xl px-3 py-2 text-sm leading-5`}
                        >
                          {enterClassNewGradeOptions.map((option) => (
                            <option key={option} value={option}>{option}</option>
                          ))}
                        </select>
                      </label>
                      {enterClassNewType === 'group' && (
                        <label className="block">
                          <span className="text-xs font-bold text-slate-500 dark:text-slate-300">班号</span>
                          <input
                            type="number"
                            min="1"
                            value={enterClassNewNumber}
                            onChange={(event) => setEnterClassNewNumber(event.target.value)}
                            className={`${workspaceFieldClass} mt-1 min-h-10 w-full rounded-xl px-3 py-2 text-sm leading-5`}
                          />
                        </label>
                      )}
                      <div className={enterClassNewType === 'group' ? 'space-y-2' : 'space-y-2 sm:col-span-2'}>
                        <label className="flex min-h-10 items-center gap-2 rounded-xl border border-white/70 bg-white/75 px-3 text-sm font-bold text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-200">
                          <input
                            type="checkbox"
                            checked={enterClassNewIsBridge}
                            onChange={(event) => setEnterClassNewIsBridge(event.target.checked)}
                          />
                          衔接班
                        </label>
                        {enterClassNewIsBridge && (
                          <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2">
                            <select
                              value={enterClassBridgeFrom}
                              onChange={(event) => setEnterClassBridgeFrom(event.target.value)}
                              className={`${workspaceFieldClass} min-h-10 w-full rounded-xl px-3 py-2 text-sm leading-5`}
                            >
                              {bridgeStageOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                            </select>
                            <span className="text-xs font-extrabold text-slate-400">衔</span>
                            <select
                              value={enterClassBridgeTo}
                              onChange={(event) => setEnterClassBridgeTo(event.target.value)}
                              className={`${workspaceFieldClass} min-h-10 w-full rounded-xl px-3 py-2 text-sm leading-5`}
                            >
                              {bridgeStageOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                            </select>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
                {enterClassMode === 'converted_without_class' && (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-100">
                    会先把咨询标记为转化成功，并把学员档案状态设为“待补充”；班级之后再回填。
                  </div>
                )}
                {enterClassMode === 'quick_new_class' && (
                  <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-xs font-semibold text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-100">
                    修改后班名预览：{enterClassPreviewName || '补完字段后自动生成'}
                  </div>
                )}
              </div>

              <div className="mt-5 grid grid-cols-2 gap-3">
                <button type="button" onClick={handleSubmitEnterClass} disabled={submitting} className={`${workspacePrimaryButtonClass} disabled:cursor-not-allowed disabled:opacity-60`}>
                  确认进班
                </button>
                <button type="button" onClick={closeEnterClassDialog} className={workspaceSecondaryButtonClass}>
                  取消
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
            <div className="w-full max-w-md rounded-3xl border border-sky-100 bg-white p-5 shadow-[0_28px_80px_rgba(15,23,42,0.22)] dark:border-white/10 dark:bg-slate-900">
              <p className="text-base font-extrabold text-slate-900 dark:text-white">这次咨询算什么结果？</p>
              <p className="mt-1 text-xs font-semibold text-slate-400">{overResultDialogRecord.child_name || '未命名学生'} · 点击后会记录 closing_result 并结束咨询</p>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => handleCloseConsultationWithResult(overResultDialogRecord, 'success')}
                  className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-5 text-left text-emerald-800 transition hover:bg-emerald-100 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-100"
                >
                  <span className="block text-base font-extrabold">咨询成功</span>
                  <span className="mt-1 block text-xs font-semibold text-emerald-600 dark:text-emerald-200">已经进班或确认转化</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleCloseConsultationWithResult(overResultDialogRecord, 'failed')}
                  className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-5 text-left text-rose-800 transition hover:bg-rose-100 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-100"
                >
                  <span className="block text-base font-extrabold">咨询失败</span>
                  <span className="mt-1 block text-xs font-semibold text-rose-600 dark:text-rose-200">暂时没有进入班级</span>
                </button>
              </div>
              <button type="button" onClick={() => setOverResultDialogRecord(null)} className={`${workspaceSecondaryButtonClass} mt-4 w-full`}>
                先不结束
              </button>
            </div>
          </motion.div>
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
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [organizations, setOrganizations] = useState<OrganizationSummaryItem[]>([]);
  const [bindingSummaryByUserId, setBindingSummaryByUserId] = useState<Record<number, MemberBindingSummary>>({});
  const [loading, setLoading] = useState(true);
  const [usersLoading, setUsersLoading] = useState(true);
  const [classesLoading, setClassesLoading] = useState(true);
  const [organizationsLoading, setOrganizationsLoading] = useState(currentUser.role === 'super_owner');
  const [bindingSummaryLoading, setBindingSummaryLoading] = useState(true);
  const [error, setError] = useState('');
  const [usersError, setUsersError] = useState('');
  const [classesError, setClassesError] = useState('');
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
  const memberRefreshLocked = usersLoading || classesLoading || bindingSummaryLoading || roleSavingUserId !== null || visiblePageSavingUserId !== null || displayNameSavingUserId !== null || deletingUserId !== null;
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

  const loadClasses = useCallback(async () => {
    setClassesLoading(true);
    setClassesError('');
    try {
      const data = await apiFetch<ClassItem[]>('/api/classes');
      setClasses(data);
    } catch (err) {
      setClasses([]);
      setClassesError(err instanceof Error ? err.message : '班级列表加载失败');
    } finally {
      setClassesLoading(false);
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
      loadClasses(),
      loadBindingSummaries(),
    ]);
  }, [loadBindingSummaries, loadClasses, loadUsers]);

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
    loadClasses().catch(() => undefined);
    loadOrganizations().catch(() => undefined);
    loadBindingSummaries().catch(() => undefined);
    loadOrganizationRequests().catch(() => undefined);
    loadOrganizationInvite().catch(() => undefined);
    loadTeacherAliases().catch(() => undefined);
  }, [loadItems, loadUsers, loadClasses, loadOrganizations, loadBindingSummaries, loadOrganizationInvite, loadOrganizationRequests, loadTeacherAliases]);

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
          {classesError && (
            <div className="mt-5 flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-300">
              <AlertCircle size={16} />
              {classesError}，负责班级名称将暂时使用原始名称。
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
                const visibleClassNames = responsibleClasses.slice(0, 3).map((item) =>
                  getCurrentClassDisplayNameById(classes, item.id, item.name),
                );
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
                  <StudentCenterPage currentUser={currentUser} classBindingTarget={classBindingTarget} onClearClassBindingTarget={() => setClassBindingTarget(null)} />
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
