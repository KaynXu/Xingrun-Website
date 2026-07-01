/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect, useCallback } from 'react';
import { AnimatePresence } from 'motion/react';
export {
  resolveTeacherBindingRollbackClassItem,
  resolveTeacherBindingRollbackTeacherBindings,
} from './features/student-center/teacherBindingRules';
import { WorkspacePageContent } from './features/navigation/WorkspacePageContent';
import { WorkspaceShellLayout } from './features/navigation/WorkspaceShellLayout';
import {
  getWorkspacePageFromPathname,
  getWorkspacePath,
  normalizeWorkspacePathname,
} from './features/navigation/workspaceRoutes';
import { ConsultationPage } from './features/consultation/ConsultationPage';

import {
  canAccessSmartWrongQuestions,
  canOpenWorkspacePage,
  getWorkspacePageFallback,
  hasOwnerAccess,
  hasStaffAccess,
} from './features/navigation/workspaceAccess';
import type {
  ClassBindingTarget,
  WorkspacePage,
} from './appTypes';
import { getRoleLabel } from './appDisplay';
import {
  LandingPage,
  getLandingLegalPageFromHash,
} from './features/landing/LandingPage';
import {
  ClassClaimPage,
  JoinOrganizationModal,
  LoginModal,
  OrganizationApplyModal,
  PasswordResetModal,
} from './features/auth/PublicAuthModals';
import { useWorkspaceAuthState } from './features/auth/useWorkspaceAuthState';
import { StudentPortalPage } from './StudentTodayTasksPage';
import {
  getTodayIsoDate,
  readLocalStorageItem,
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

export default function App() {
  const studentPortalMode = typeof window !== 'undefined' && window.location.pathname.startsWith('/student');
  if (studentPortalMode) {
    return <StudentPortalPage today={getTodayIsoDate()} />;
  }

  const {
    token,
    currentUser,
    setCurrentUser,
    authReady,
    publicAuthModal,
    joinInviteToken,
    handleLogin: persistLogin,
    handleLogout: clearWorkspaceAuth,
    closePublicAuthModal,
    openApplyOrganization,
    openJoinOrganization,
    openPasswordReset,
    backToLogin,
  } = useWorkspaceAuthState();
  const [isDark, setIsDark] = useState<boolean>(getInitialDarkModePreference);
  const [isMobileViewport, setIsMobileViewport] = useState(getInitialMobileViewport);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [activePage, setActivePage] = useState<Page>(() =>
    typeof window === 'undefined' ? 'dashboard' : getWorkspacePageFromPathname(window.location.pathname) ?? 'dashboard',
  );
  const [classBindingTarget, setClassBindingTarget] = useState<ClassBindingTarget | null>(null);
  const [reviewTaskDockDismissed, setReviewTaskDockDismissed] = useState(false);
  const [reviewTaskDockAvailable, setReviewTaskDockAvailable] = useState(false);
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
    if (!currentUser) {
      setActivePage(typeof window === 'undefined' ? 'dashboard' : getWorkspacePageFromPathname(window.location.pathname) ?? 'dashboard');
      return;
    }
    setActivePage((page) => {
      const routePage = typeof window === 'undefined' ? null : getWorkspacePageFromPathname(window.location.pathname);
      return getWorkspacePageFallback(currentUser, routePage ?? page);
    });
  }, [currentUser]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const syncWorkspacePageFromHistory = () => {
      const routePage = getWorkspacePageFromPathname(window.location.pathname);
      if (routePage) {
        setActivePage(routePage);
        setShowLanding(false);
        return;
      }
      setShowLanding(true);
    };

    window.addEventListener('popstate', syncWorkspacePageFromHistory);
    return () => window.removeEventListener('popstate', syncWorkspacePageFromHistory);
  }, []);

  const handleLogin = (t: string) => {
    persistLogin(t);
    setShowLanding(false);
  };

  const handleLogout = () => {
    clearWorkspaceAuth();
    setShowLanding(false);
    setActivePage('dashboard');
    setMobileNavOpen(false);
    setReviewTaskDockDismissed(false);
    setReviewTaskDockAvailable(false);
    if (typeof window !== 'undefined' && normalizeWorkspacePathname(window.location.pathname) !== '/') {
      window.history.pushState({}, '', '/');
    }
  };

  const navigateWorkspacePage = useCallback((page: Page) => {
    const nextPage = currentUser ? getWorkspacePageFallback(currentUser, page) : 'dashboard';
    if (!currentUser) {
      setActivePage('dashboard');
    } else {
      setActivePage(getWorkspacePageFallback(currentUser, page));
    }
    setShowLanding(false);
    if (typeof window !== 'undefined') {
      const nextPath = getWorkspacePath(nextPage);
      if (normalizeWorkspacePathname(window.location.pathname) !== nextPath) {
        window.history.pushState({}, '', nextPath);
      }
    }
  }, [currentUser]);

  const handleReviewGenerationSuccess = () => {
    navigateWorkspacePage('review-generation');
  };

  const handleOpenClassBinding = (target: ClassBindingTarget) => {
    setClassBindingTarget(target);
    navigateWorkspacePage('classes');
    setMobileNavOpen(false);
  };

  const handleOpenWorkspaceHome = useCallback(() => {
    setShowLanding(false);
    if (typeof window !== 'undefined') {
      const nextPath = getWorkspacePath(currentUser ? getWorkspacePageFallback(currentUser, activePage) : activePage);
      if (normalizeWorkspacePathname(window.location.pathname) !== nextPath) {
        window.history.pushState({}, '', nextPath);
      }
    }
  }, [activePage, currentUser]);

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

  const activeWorkspacePage = currentUser ? getWorkspacePageFallback(currentUser, activePage) : activePage;

  useEffect(() => {
    if (typeof window === 'undefined' || !token || !currentUser || showLanding || landingLegalPage) {
      return;
    }

    const nextPath = getWorkspacePath(activeWorkspacePage);
    if (normalizeWorkspacePathname(window.location.pathname) !== nextPath) {
      window.history.replaceState({}, '', nextPath);
    }
  }, [activeWorkspacePage, currentUser, landingLegalPage, showLanding, token]);

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
          onLogin={token ? handleOpenWorkspaceHome : backToLogin}
          onApplyOrganization={() => {
            if (token) {
              handleOpenWorkspaceHome();
              return;
            }
            openApplyOrganization();
          }}
          onJoinOrganization={() => {
            if (token) {
              handleOpenWorkspaceHome();
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

  return (
    <WorkspaceShellLayout
      activeWorkspacePage={activeWorkspacePage}
      currentUser={currentUser}
      title={pageTitle[activeWorkspacePage]}
      isDark={isDark}
      mobileNavOpen={mobileNavOpen}
      onGoHome={() => {
        setShowLanding(true);
        if (typeof window !== 'undefined' && normalizeWorkspacePathname(window.location.pathname) !== '/') {
          window.history.pushState({}, '', '/');
        }
      }}
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
      showReviewTaskLauncher={reviewTaskDockDismissed && reviewTaskDockAvailable}
      onOpenReviewTaskDock={() => setReviewTaskDockDismissed(false)}
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
        onCurrentUserUpdated={(user) => setCurrentUser(user)}
        reviewTaskDockDismissed={reviewTaskDockDismissed}
        setReviewTaskDockDismissed={setReviewTaskDockDismissed}
        onReviewTaskDockAvailableChange={setReviewTaskDockAvailable}
      />
    </WorkspaceShellLayout>
  );
}
