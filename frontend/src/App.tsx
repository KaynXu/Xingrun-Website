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
import { ConsultationBatchModal } from './features/consultation/ConsultationBatchModal';
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
import type {
  ClassBindingTarget,
  CurrentUser,
  UserItem,
  WorkspacePage,
} from './appTypes';
import { getRoleLabel } from './appDisplay';
import {
  LandingLegalPage,
  LandingPage,
  getLandingLegalPageFromHash,
} from './features/landing/LandingPage';
import type { LandingLegalDocumentKey } from './features/landing/LandingPage';
import {
  ClassClaimPage,
  JoinOrganizationModal,
  LoginModal,
  OrganizationApplyModal,
  PasswordResetModal,
} from './features/auth/PublicAuthModals';
import {
  clearJoinInvitePathIfNeeded,
  getJoinInviteTokenFromPath,
} from './features/auth/authFlow';
import {
  backToLoginState,
  closePublicAuthState,
  openApplyOrganizationState,
  openJoinOrganizationState,
  openPasswordResetState,
} from './features/auth/authActions';
import {
  getInitialJoinInviteToken,
  getInitialPublicAuthModal,
} from './features/auth/authState';
import type { PublicAuthModal } from './features/auth/authState';
import {
  academicGradeGroups,
  academicGradeOptions,
  academicStageOptions,
  buildClassDisplayName,
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
  apiUploadFormWithProgress,
  buildAuthedPath,
  cn,
  getTodayIsoDate,
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
export type {
  ClassBindingTarget,
  ClassItem,
  CurrentUser,
  Role,
  UserItem,
  WorkspacePage as Page,
} from './appTypes';
export type {
  ConsultationBatchDraftItem,
  ConsultationBatchParseResponse,
  ConsultationFilterKey,
  ConsultationFormValues,
  ConsultationRecord,
  ConsultationResultStage,
  ConsultationTeacherOption,
} from './features/consultation/consultationTypes';

export {
  apiFetch,
  apiUploadFormWithProgress,
  buildAuthedPath,
  cn,
  getTodayIsoDate,
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
export { LandingLegalPage, LandingPage, getLandingLegalPageFromHash } from './features/landing/LandingPage';

// --- Types ---

type Page = WorkspacePage;

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
  const [publicAuthModal, setPublicAuthModal] = useState<PublicAuthModal | null>(() =>
    getInitialPublicAuthModal(typeof window === 'undefined' ? '' : window.location.pathname, Boolean(getToken())),
  );
  const [joinInviteToken, setJoinInviteToken] = useState<string | null>(() =>
    getInitialJoinInviteToken(typeof window === 'undefined' ? '' : window.location.pathname),
  );
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [activePage, setActivePage] = useState<Page>('dashboard');
  const [classBindingTarget, setClassBindingTarget] = useState<ClassBindingTarget | null>(null);
  const [showLanding, setShowLanding] = useState(false);
  const [landingHash, setLandingHash] = useState<string>(() =>
    typeof window === 'undefined' ? '' : window.location.hash,
  );

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
    const nextState = closePublicAuthState();
    setJoinInviteToken(nextState.joinInviteToken);
    setPublicAuthModal(nextState.publicAuthModal);
  };

  const openApplyOrganization = () => {
    const nextState = openApplyOrganizationState();
    setJoinInviteToken(nextState.joinInviteToken);
    setPublicAuthModal(nextState.publicAuthModal);
  };

  const openJoinOrganization = () => {
    const nextState = openJoinOrganizationState(typeof window === 'undefined' ? '' : window.location.pathname);
    setJoinInviteToken(nextState.joinInviteToken);
    setPublicAuthModal(nextState.publicAuthModal);
  };

  const openPasswordReset = () => {
    setPublicAuthModal(openPasswordResetState());
  };

  const backToLogin = () => {
    setPublicAuthModal(backToLoginState());
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
        classBindingTarget={classBindingTarget}
        handleClearClassBindingTarget={() => setClassBindingTarget(null)}
        handleOpenClassBinding={handleOpenClassBinding}
        handleLogout={handleLogout}
      />
    </WorkspaceShellLayout>
  );
}
