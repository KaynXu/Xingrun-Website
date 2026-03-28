/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
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
  Filter,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  ShieldCheck,
  Moon,
  Sun,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { CourseCalendarPage } from './CourseCalendarPage';

// --- Types ---

type Role = 'owner' | 'member';
type Page = 'dashboard' | 'input' | 'library' | 'consultation' | 'calendar' | 'accounts' | 'settings';
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
  consultation_subject: string;
  need_detail: string;
  source_channel: string;
  screenshot: string;
  follow_up_status: string;
  follow_up_note: string;
  created_at: string;
  updated_at: string;
}

type ConsultationFormValues = Omit<ConsultationRecord, 'id' | 'created_at' | 'updated_at'>;

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

function getRoleLabel(role: Role): string {
  return role === 'owner' ? '最高权限账号' : '机构成员';
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

const consultationStatusOptions = ['待跟进', '跟进中', '已跟进', '已完成'];

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
    screenshot: record.screenshot ?? '',
    follow_up_status: record.follow_up_status ?? '',
    follow_up_note: record.follow_up_note ?? '',
    created_at: record.created_at ?? '',
    updated_at: record.updated_at ?? '',
  };
}

const workspacePageClass = 'px-6 py-6 md:px-8 md:py-8 xl:px-10 xl:py-10';
const workspaceCardClass =
  'rounded-[1.75rem] border border-sky-100/90 bg-white/88 shadow-[0_22px_54px_rgba(47,128,237,0.08)] backdrop-blur-sm dark:border-white/10 dark:bg-slate-800/88 dark:shadow-[0_24px_60px_rgba(2,6,23,0.42)]';
const workspaceSoftCardClass =
  'rounded-[1.5rem] border border-sky-100 bg-[linear-gradient(180deg,rgba(255,255,255,0.94)_0%,rgba(239,248,255,0.78)_100%)] shadow-[0_14px_36px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-slate-800/72 dark:shadow-[0_18px_40px_rgba(2,6,23,0.34)]';
const workspaceFieldClass =
  'w-full rounded-xl border border-sky-200 bg-white/92 px-4 py-2.5 text-sm text-slate-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)] outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100 placeholder:text-slate-400 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100 dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] dark:focus:border-sky-500 dark:focus:ring-sky-500/15 dark:placeholder:text-slate-500';
const workspacePrimaryButtonClass =
  'inline-flex items-center justify-center gap-2 rounded-xl bg-sky-600 px-5 py-3 font-semibold text-white shadow-[0_16px_40px_rgba(34,199,232,0.24)] transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-60';
const workspaceSecondaryButtonClass =
  'inline-flex items-center justify-center gap-2 rounded-xl border border-sky-200 bg-white px-5 py-3 font-semibold text-slate-700 shadow-sm transition hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:hover:bg-white/10';
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
}: {
  currentUser: CurrentUser;
  open: boolean;
  onClose: () => void;
  onLogout: () => void;
  onOpenSettings: () => void;
}) => {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-40" onClick={onClose}>
      <div className="absolute inset-0 bg-slate-900/18 backdrop-blur-[4px]" />
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
        </div>
      </div>
    </div>
  );
};

const Sidebar = ({
  activePage,
  currentUser,
  onLogout,
  setActivePage,
}: {
  activePage: Page;
  currentUser: CurrentUser;
  onLogout: () => void;
  setActivePage: (p: Page) => void;
}) => {
  const [accountSheetOpen, setAccountSheetOpen] = useState(false);
  const menuItems = [
    { id: 'dashboard', icon: LayoutDashboard, label: '工作台' },
    { id: 'input', icon: PlusCircle, label: '添加课程' },
    { id: 'library', icon: Library, label: '课程列表' },
    { id: 'consultation', icon: MessageSquare, label: '咨询记录' },
    { id: 'calendar', icon: CalendarDays, label: '课程日历' },
    ...(currentUser.role === 'owner' ? [{ id: 'accounts', icon: User, label: '账号审批' }] : []),
    { id: 'settings', icon: Settings, label: '系统设置' },
  ];

  return (
    <div className="sticky top-0 flex h-screen w-72 flex-col border-r border-sky-100/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96)_0%,rgba(239,248,255,0.92)_52%,rgba(231,243,255,0.96)_100%)] shadow-[18px_0_48px_rgba(47,128,237,0.06)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(8,15,30,0.98)_0%,rgba(15,23,42,0.96)_52%,rgba(17,24,39,0.98)_100%)] dark:shadow-[18px_0_48px_rgba(2,6,23,0.38)]">
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
            onClick={() => setActivePage(item.id as Page)}
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
              }}
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
}: {
  title: string;
  onGoHome?: () => void;
  isDark?: boolean;
  onToggleDarkMode?: () => void;
}) => {
  return (
    <header className="sticky top-0 z-10 flex h-20 items-center justify-between border-b border-sky-100/80 bg-white/78 px-6 backdrop-blur-xl md:px-8 dark:border-white/10 dark:bg-[#0f172a]/88">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">Workspace</p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">{title}</h2>
      </div>
      <div className="flex items-center gap-4">
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
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-400" size={18} />
          <input
            type="text"
            placeholder="搜索课程、班级..."
            className={`${workspaceFieldClass} w-64 rounded-full py-2 pl-10 pr-4`}
          />
        </div>
        <button className="relative flex h-11 w-11 items-center justify-center rounded-full border border-sky-200 bg-white text-slate-500 transition-colors hover:bg-sky-50 hover:text-slate-800 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white">
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
            <button onClick={() => setActivePage('input')} className={workspacePrimaryButtonClass}>
              <PlusCircle size={20} />
              添加新课程
            </button>
            <button onClick={() => setActivePage('library')} className={workspaceSecondaryButtonClass}>
              <Library size={20} />
              查看课程列表
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
          <button onClick={() => setActivePage('library')} className="text-sm font-medium text-sky-600 transition-colors hover:text-sky-500 dark:text-sky-400 dark:hover:text-sky-300">
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
                      href={`/pdf/download/${lesson.id}`}
                      className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-slate-500 transition-all hover:bg-sky-100 hover:text-sky-600 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-sky-300"
                      title="下载"
                    >
                      <Download size={18} />
                    </a>
                    <a
                      href={`/pdf/${lesson.id}`}
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
                <h3 className={`${workspaceSectionTitleClass} mt-3`}>添加新课程</h3>
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
                  生成复习资料 PDF
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

const LibraryPage = () => {
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
  }, [load]);

  const handleDelete = async (id: number) => {
    if (!window.confirm('确定删除此课程？相关 PDF 也会被删除。')) return;
    await apiFetch(`/api/lessons/${id}`, { method: 'DELETE' });
    load();
  };

  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <div className="flex items-center justify-between">
        <div>
          <h3 className={workspaceSectionTitleClass}>课程列表</h3>
          <p className={`${workspaceSectionTextClass} mt-2`}>按课程、日期与 PDF 生成状态查看教学记录。</p>
        </div>
        <div className="flex gap-2">
          <button className="flex h-11 w-11 items-center justify-center rounded-xl border border-sky-200 bg-white text-slate-500 transition-all hover:bg-sky-50 hover:text-sky-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-sky-300">
            <Filter size={20} />
          </button>
        </div>
      </div>

      <div className={`${workspaceCardClass} overflow-hidden`}>
        {loading ? (
          <div className="p-8 text-center text-slate-500 dark:text-slate-400">加载中...</div>
        ) : lessons.length === 0 ? (
          <div className="p-8 text-center text-slate-500 dark:text-slate-400">暂无课程，点击「添加课程」开始记录。</div>
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
                            href={`/pdf/${lesson.id}`}
                            target="_blank"
                            rel="noreferrer"
                            className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-500 transition-all hover:bg-sky-50 hover:text-sky-600 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-sky-300"
                            title="查看"
                          >
                            <Eye size={16} />
                          </a>
                          <a
                            href={`/pdf/download/${lesson.id}`}
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
    </div>
  );
};

const ConsultationModal = ({
  open,
  mode,
  record,
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
  submitting: boolean;
  error: string;
  currentUser: CurrentUser;
  onClose: () => void;
  onSubmit: (values: ConsultationFormValues) => Promise<void>;
  onDelete?: () => Promise<void>;
  onRequestEdit?: () => void;
}) => {
  const [form, setForm] = useState<ConsultationFormValues>(toConsultationFormValues(record));

  useEffect(() => {
    if (open) {
      setForm(toConsultationFormValues(record));
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (readOnly) {
      return;
    }
    await onSubmit(form);
  };

  const fieldClass = `${workspaceFieldClass} ${readOnly ? 'cursor-default' : ''}`;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center px-4 py-6"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="absolute inset-0 bg-black/45 backdrop-blur-[6px]" />
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: 18 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.97, y: 18 }}
        transition={{ duration: 0.2 }}
        className="relative z-10 flex w-full max-w-5xl max-h-[calc(100vh-3rem)] flex-col overflow-hidden rounded-[2rem] border border-sky-100 bg-white shadow-[0_30px_90px_rgba(15,23,42,0.18)] dark:border-white/10 dark:bg-slate-900 dark:shadow-[0_30px_90px_rgba(2,6,23,0.55)]"
      >
        <div className="flex items-start justify-between gap-4 border-b border-sky-100/80 px-6 py-5 dark:border-white/10">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Consultation</p>
            <h3 className="mt-2 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">{titleMap[mode]}</h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {readOnly ? '记录详情只读展示，owner 可以在这里进入编辑或删除。' : '按工作台原有模式录入和维护咨询信息。'}
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

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-6 py-5">
          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <div className="grid gap-5 lg:grid-cols-2">
            <section className={`${workspaceSoftCardClass} space-y-4 p-5`}>
              <div>
                <h4 className="font-semibold text-slate-900 dark:text-white">基础信息</h4>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">日期、对象和接待老师信息。</p>
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
                  <span className="text-slate-500 dark:text-slate-400">接待老师</span>
                  <input
                    type="text"
                    value={form.receiving_teacher}
                    onChange={(e) => updateField('receiving_teacher', e.target.value)}
                    disabled={readOnly}
                    className={fieldClass}
                    placeholder="接待老师"
                  />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">老师ID</span>
                  <input
                    type="text"
                    value={form.teacher_id}
                    onChange={(e) => updateField('teacher_id', e.target.value)}
                    disabled={readOnly}
                    className={fieldClass}
                    placeholder="老师 ID"
                  />
                </label>
              </div>
            </section>

            <section className={`${workspaceSoftCardClass} space-y-4 p-5`}>
              <div>
                <h4 className="font-semibold text-slate-900 dark:text-white">咨询内容</h4>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">咨询主题、需求、来源和截图。</p>
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
                  <span className="text-slate-500 dark:text-slate-400">来源渠道</span>
                  <input
                    type="text"
                    value={form.source_channel}
                    onChange={(e) => updateField('source_channel', e.target.value)}
                    disabled={readOnly}
                    className={fieldClass}
                    placeholder="如：朋友圈 / 转介绍 / 私信"
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
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">截图</span>
                  <textarea
                    value={form.screenshot}
                    onChange={(e) => updateField('screenshot', e.target.value)}
                    disabled={readOnly}
                    rows={3}
                    className={`${fieldClass} resize-none`}
                    placeholder="截图地址或说明"
                  />
                </label>
              </div>
            </section>

            <section className={`${workspaceSoftCardClass} space-y-4 p-5 lg:col-span-2`}>
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
                  <span className="text-slate-500 dark:text-slate-400">跟进备注</span>
                  <textarea
                    value={form.follow_up_note}
                    onChange={(e) => updateField('follow_up_note', e.target.value)}
                    disabled={readOnly}
                    rows={5}
                    className={`${fieldClass} resize-none`}
                    placeholder="后续跟进记录"
                  />
                </label>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-white/5">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">录入时间</p>
                  <p className="mt-2 text-sm font-medium text-slate-700 dark:text-slate-200">{record?.created_at || '—'}</p>
                </div>
                <div className="rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-white/5">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">最后更新</p>
                  <p className="mt-2 text-sm font-medium text-slate-700 dark:text-slate-200">{record?.updated_at || '—'}</p>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-white/5">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">当前权限</p>
                  <p className="mt-2 text-sm font-medium text-slate-700 dark:text-slate-200">{getRoleLabel(currentUser.role)}</p>
                </div>
                <div className="rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-white/5">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">截图字段</p>
                  <p className="mt-2 text-sm font-medium text-slate-700 dark:text-slate-200">{form.screenshot ? '已填写' : '未填写'}</p>
                </div>
                <div className="rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-white/5">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">记录状态</p>
                  <p className="mt-2 text-sm font-medium text-slate-700 dark:text-slate-200">{form.follow_up_status || '—'}</p>
                </div>
              </div>
            </section>
          </div>

          <div className="mt-6 flex flex-col gap-3 border-t border-sky-100/80 pt-5 sm:flex-row sm:items-center sm:justify-between dark:border-white/10">
            <div className="text-sm text-slate-500 dark:text-slate-400">
              {readOnly ? '查看模式下可直接切换到编辑或删除记录。' : '保存后会刷新列表，不需要跳转到其他页面。'}
            </div>
            <div className="flex flex-wrap justify-end gap-3">
              {readOnly && currentUser.role === 'owner' && (
                <>
                  <button
                    type="button"
                    onClick={onRequestEdit}
                    className={workspaceSecondaryButtonClass}
                  >
                    <Pencil size={18} />
                    编辑
                  </button>
                  <button
                    type="button"
                    onClick={onDelete}
                    disabled={submitting}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-5 py-3 font-semibold text-rose-600 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
                  >
                    <Trash2 size={18} />
                    删除
                  </button>
                </>
              )}
              {readOnly ? (
                <button type="button" onClick={onClose} className={workspacePrimaryButtonClass}>
                  关闭
                </button>
              ) : (
                <>
                  <button type="button" onClick={onClose} className={workspaceSecondaryButtonClass} disabled={submitting}>
                    取消
                  </button>
                  <button type="submit" className={workspacePrimaryButtonClass} disabled={submitting}>
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
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'view' | 'create' | 'edit'>('view');
  const [selectedRecord, setSelectedRecord] = useState<ConsultationRecord | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const loadRequestId = useRef(0);

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
      <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Consultation Log</p>
          <h3 className={`${workspaceSectionTitleClass} mt-3`}>咨询记录</h3>
          <p className={`${workspaceSectionTextClass} mt-2`}>
            记录家长咨询、跟进状态和后续备注，搜索后会直接按关键词过滤当前列表。
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-400" size={18} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索日期、家长微信名、孩子姓名、老师或科目"
              className={`${workspaceFieldClass} w-full rounded-full py-2.5 pl-11 pr-4 sm:w-[26rem]`}
            />
          </label>
          <button
            type="button"
            onClick={() => load(search).catch(() => undefined)}
            className={workspaceSecondaryButtonClass}
          >
            <RefreshCw size={18} />
            刷新
          </button>
          <button type="button" onClick={openCreateModal} className={workspacePrimaryButtonClass}>
            <PlusCircle size={18} />
            新增记录
          </button>
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
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-sky-100/80 text-xs uppercase tracking-wider text-slate-400 dark:border-white/10 dark:text-slate-500">
                <th className="px-6 py-4 font-semibold">日期</th>
                <th className="px-6 py-4 font-semibold">家长 / 孩子</th>
                <th className="px-6 py-4 font-semibold">年级</th>
                <th className="px-6 py-4 font-semibold">接待老师</th>
                <th className="px-6 py-4 font-semibold">咨询科目</th>
                <th className="px-6 py-4 font-semibold">跟进状态</th>
                <th className="px-6 py-4 font-semibold">录入 / 更新</th>
                <th className="px-6 py-4 text-right font-semibold">操作</th>
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
                          {record.child_name || '—'}
                        </p>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500 dark:text-slate-400">{record.grade || '—'}</td>
                    <td className="px-6 py-4">
                      <div className="space-y-1 text-sm">
                        <p className="text-slate-700 dark:text-slate-200">{record.receiving_teacher || '—'}</p>
                        <p className="text-slate-400 dark:text-slate-500">ID: {record.teacher_id || '—'}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500 dark:text-slate-400">{record.consultation_subject || '—'}</td>
                    <td className="px-6 py-4">
                      <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">
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
                      <div className="flex justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
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
        )}
      </div>

      <AnimatePresence>
        {modalOpen && (
          <ConsultationModal
            open={modalOpen}
            mode={modalMode}
            record={selectedRecord}
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actingId, setActingId] = useState<number | null>(null);

  const [users, setUsers] = useState<UserItem[]>([]);
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [userClassIds, setUserClassIds] = useState<Record<number, number[]>>({});
  const [savingUserId, setSavingUserId] = useState<number | null>(null);

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

  useEffect(() => {
    loadItems().catch(() => undefined);
  }, [loadItems]);

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

  useEffect(() => {
    Promise.all([
      apiFetch<UserItem[]>('/api/admin/users'),
      apiFetch<ClassItem[]>('/api/classes'),
    ]).then(([u, c]) => {
      setUsers(u);
      setClasses(c);
      return Promise.all(
        u.map((user) =>
          apiFetch<{ class_ids: number[] }>(`/api/admin/users/${user.id}/classes`).then((d) => ({
            id: user.id,
            class_ids: d.class_ids,
          }))
        )
      );
    }).then((results) => {
      const map: Record<number, number[]> = {};
      results.forEach(({ id, class_ids }) => { map[id] = class_ids; });
      setUserClassIds(map);
    }).catch(console.error);
  }, []);

  const handleClassToggle = async (userId: number, classId: number, checked: boolean) => {
    const prev = userClassIds[userId] ?? [];
    const next = checked ? [...prev, classId] : prev.filter((id) => id !== classId);
    setUserClassIds((m) => ({ ...m, [userId]: next }));
    setSavingUserId(userId);
    try {
      await apiFetch(`/api/admin/users/${userId}/classes`, {
        method: 'PUT',
        body: JSON.stringify({ class_ids: next }),
      });
    } catch (err) {
      setUserClassIds((m) => ({ ...m, [userId]: prev }));
      setError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSavingUserId(null);
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

      <section className={`${workspaceCardClass} space-y-5 p-6`}>
        <div>
          <h4 className="text-xl font-semibold text-slate-900 dark:text-white">班级分配</h4>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">为每位成员指定可访问的班级。</p>
        </div>
        {users.length === 0 ? (
          <div className="p-8 text-center text-slate-500 dark:text-slate-400">暂无成员数据</div>
        ) : (
          <div className="space-y-4">
            {users.map((user) => {
              const assigned = userClassIds[user.id] ?? [];
              const saving = savingUserId === user.id;
              return (
                <div key={user.id} className={`${workspaceSoftCardClass} p-5`}>
                  <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                    <div>
                        <span className="font-semibold text-slate-900 dark:text-white">{user.name}</span>
                        <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">{user.org}</span>
                      {saving && <span className="ml-2 text-xs text-sky-600">保存中...</span>}
                    </div>
                    {classes.length === 0 ? (
                        <span className="text-xs text-slate-500 dark:text-slate-400">暂无班级</span>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {classes.map((cls) => {
                          const checked = assigned.includes(cls.id);
                          return (
                              <label key={cls.id} className="flex cursor-pointer select-none items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300">
                              <input
                                type="checkbox"
                                checked={checked}
                                disabled={saving}
                                onChange={(e) => handleClassToggle(user.id, cls.id, e.target.checked)}
                                className="accent-sky-500"
                              />
                              <span className={checked ? 'text-slate-900 dark:text-white' : 'text-slate-500 dark:text-slate-400'}>{cls.name}</span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
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
                <label className="text-sm text-gray-400">用户名</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  placeholder="登录时使用"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">显示名</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  required
                  placeholder="后台展示名称"
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
            className="absolute left-[-6%] top-[8%] h-72 w-72 rounded-full bg-cyan-200/50 blur-[120px]"
          />
          <motion.div
            animate={{ scale: [1, 1.1, 1], opacity: [0.4, 0.55, 0.4] }}
            transition={{ duration: 9, repeat: Infinity, ease: "easeInOut", delay: 2 }}
            className="absolute right-[-8%] top-[18%] h-80 w-80 rounded-full bg-blue-200/40 blur-[140px]"
          />
          <motion.div
            animate={{ scale: [1, 1.15, 1], opacity: [0.7, 0.85, 0.7] }}
            transition={{ duration: 11, repeat: Infinity, ease: "easeInOut", delay: 4 }}
            className="absolute bottom-[-12%] left-[25%] h-96 w-96 rounded-full bg-white/70 blur-[100px]"
          />
        </div>

        <div className="max-w-7xl mx-auto px-6 relative z-10 flex min-h-screen items-center justify-center py-20 md:py-32 text-center">
          <motion.div
            initial={{ opacity: 0, scale: 2, y: -100 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="rounded-[2rem] border border-sky-100 bg-white/85 p-5 sm:p-8 md:p-12 shadow-[0_30px_90px_rgba(47,128,237,0.08)] dark:bg-slate-800/80 dark:border-white/10">
              <motion.span
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1, duration: 0.5 }}
                className="mb-6 inline-flex items-center rounded-full border border-sky-200 bg-white px-4 py-1.5 text-xs font-semibold tracking-[0.3em] text-sky-700 dark:bg-slate-700/80 dark:border-sky-500/30 dark:text-sky-300"
              >
                BUILT FROM REAL TEACHING PRACTICE
              </motion.span>
              <motion.h1
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="mt-6 text-3xl sm:text-5xl font-black leading-[1.05] sm:leading-[0.95] tracking-tight text-slate-900 md:text-7xl dark:text-white"
              >
                教育工作流终于被 AI 重新组织好了
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4, duration: 0.8 }}
                className="mx-auto mb-12 mt-8 max-w-3xl text-lg leading-relaxed text-slate-600 md:text-xl dark:text-slate-300"
              >
                Starain 起源于真实教学场景。我们先为自己的机构解决复习资料、题库沉淀、讲义生成与教学协同的问题，
                再把这套已验证的工作流产品化，帮助更多教育团队完成 AI 化升级。
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6, duration: 0.8 }}
                className="flex flex-col items-center justify-center gap-4 sm:flex-row"
              >
                <a
                  href="#features"
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-sky-600 px-10 py-5 text-lg font-bold text-white shadow-[0_24px_60px_rgba(34,199,232,0.28)] transition-all hover:bg-sky-500 active:scale-95 sm:w-auto"
                >
                  查看平台方案
                  <ArrowRight size={20} />
                </a>
                <button
                  onClick={onRegister}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl border border-sky-200 bg-white px-10 py-5 text-lg font-bold text-slate-700 transition-all hover:bg-sky-50 active:scale-95 sm:w-auto dark:border-white/15 dark:bg-white/8 dark:text-slate-200 dark:hover:bg-white/15"
                >
                  <User size={20} />
                  申请试用
                </button>
              </motion.div>
            </div>
          </motion.div>
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
              className="group relative overflow-hidden rounded-[2.5rem] border border-sky-100 bg-white/85 p-6 md:p-10 shadow-[0_24px_70px_rgba(47,128,237,0.06)] md:col-span-2 dark:bg-slate-800/80 dark:border-white/10"
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
              className="flex flex-col justify-between rounded-[2.5rem] border border-sky-100 bg-[linear-gradient(180deg,_rgba(255,255,255,0.92)_0%,_rgba(239,248,255,0.92)_100%)] p-6 md:p-10 shadow-[0_20px_60px_rgba(47,128,237,0.05)] dark:bg-slate-800/80 dark:border-white/10"
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
              className="flex flex-col justify-between rounded-[2.5rem] border border-sky-100 bg-white/85 p-6 md:p-10 shadow-[0_20px_60px_rgba(47,128,237,0.05)] dark:bg-slate-800/80 dark:border-white/10"
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
              className="flex flex-col items-center gap-10 rounded-[2.5rem] border border-sky-100 bg-white/85 p-6 md:p-10 shadow-[0_24px_70px_rgba(47,128,237,0.06)] md:col-span-2 md:flex-row dark:bg-slate-800/80 dark:border-white/10"
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
              <div className="flex w-full flex-col gap-3 rounded-3xl border border-sky-100 bg-[linear-gradient(180deg,_rgba(255,255,255,0.96)_0%,_rgba(234,245,255,0.96)_100%)] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)] md:w-72 dark:border-white/10 dark:bg-slate-700/50">
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
                    className="rounded-2xl border border-sky-100 bg-white/90 p-4 shadow-[0_14px_34px_rgba(47,128,237,0.07)] dark:border-white/10 dark:bg-slate-600/50"
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
        setActivePage((page) => (page === 'accounts' && user.role !== 'owner' ? 'dashboard' : page));
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
  };

  const handleLessonSuccess = () => {
    setActivePage('library');
  };

  const handlePreviousCalendarWeek = () => {
    setCalendarAnchorDate((current) => shiftIsoDate(current, -7));
  };

  const handleNextCalendarWeek = () => {
    setCalendarAnchorDate((current) => shiftIsoDate(current, 7));
  };

  const pageTitle: Record<Page, string> = {
    dashboard: '工作台',
    input: '添加课程',
    library: '课程列表',
    consultation: '咨询记录',
    calendar: '课程日历',
    accounts: '账号审批',
    settings: '系统设置',
  };

  if (token && !authReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[linear-gradient(180deg,#f8fbff_0%,#eef6ff_100%)] px-6 text-slate-900 dark:bg-[linear-gradient(180deg,#020617_0%,#0f172a_100%)] dark:text-slate-100">
        <div className={`${workspaceCardClass} w-full max-w-xl p-8`}>
          <XiaojimaoLoading label="正在验证账号权限..." />
        </div>
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
    <div className="relative min-h-screen overflow-hidden bg-[linear-gradient(180deg,#f8fbff_0%,#eef6ff_100%)] text-slate-900 dark:bg-[linear-gradient(180deg,#020617_0%,#0f172a_100%)] dark:text-slate-100">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[-8%] top-[8%] h-80 w-80 rounded-full bg-cyan-200/35 blur-[130px] dark:bg-cyan-500/10" />
        <div className="absolute right-[-10%] top-[12%] h-96 w-96 rounded-full bg-blue-200/30 blur-[150px] dark:bg-blue-500/10" />
        <div className="absolute bottom-[-14%] left-[28%] h-[28rem] w-[28rem] rounded-full bg-white/75 blur-[120px] dark:bg-slate-900/40" />
      </div>
      <div className="relative flex min-h-screen">
        <Sidebar
          activePage={activePage}
          currentUser={currentUser}
          onLogout={handleLogout}
          setActivePage={setActivePage}
        />
        <main className="flex min-w-0 flex-1 flex-col">
          <Header
            title={pageTitle[activePage]}
            onGoHome={() => setShowLanding(true)}
            isDark={isDark}
            onToggleDarkMode={() => setIsDark((current) => !current)}
          />
          <div className="flex-1 overflow-y-auto">
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
                {activePage === 'input' && <LessonInput onSuccess={handleLessonSuccess} />}
                {activePage === 'library' && <LibraryPage />}
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
