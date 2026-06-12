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
  buildConsultationBatchCreatePayload,
  ConsultationModal,
  normalizeConsultationTeacherOption,
  parseConsultationQuickEntry,
  toConsultationFormValues,
} from './features/consultation/ConsultationModal';
import {
  ConsultationCardExpandableText,
  ConsultationFlowBar,
  ConsultationStatusLamp,
  buildConsultationTeacherDirectory,
  clearConsultationResultStage,
  consultationFilterGroups,
  consultationFilterLabels,
  consultationFlowStages,
  consultationInputClass,
  consultationLabelClass,
  consultationMeetingVersion,
  consultationPanelClass,
  consultationProcessStages,
  consultationResultShortLabel,
  consultationStageDisplayLabel,
  consultationStageShortLabel,
  consultationSurfaceClass,
  consultationValueClass,
  endConsultationValues,
  getConsultationFilterKey,
  getConsultationOver30SectionLabel,
  getConsultationSourceLabel,
  getConsultationTeacherName,
  isConsultationEnded,
  isConsultationResultStage,
  moveConsultationStage,
  normalizeConsultationRecord,
  restoreConsultationValues,
  setConsultationResultStage,
  sortConsultationsForFilter,
  toggleConsultationStageLight,
} from './features/consultation/consultationShared';

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
export type ConsultationResultStage = '成功进班' | '试听失败';
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

export type ConsultationFilterKey =
  | 'pending-7'
  | 'pending-30'
  | 'pending-over30'
  | 'ended-success'
  | 'ended-unsuccessful';

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
  parseConsultationQuickEntry,
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
      <div className="relative min-h-[100svh] overflow-x-hidden bg-[#f5f8fc] text-slate-900 sm:min-h-screen dark:bg-[#020617] dark:text-slate-100">
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
