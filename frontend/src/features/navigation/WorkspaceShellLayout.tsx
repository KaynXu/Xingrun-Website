import type { ReactNode } from 'react';
import { X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';

import type { CurrentUser } from '../../App';
import { cn } from '../../workspaceShared';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

type WorkspaceShellPage =
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

export function WorkspaceShellLayout({
  activeWorkspacePage,
  currentUser,
  title,
  isDark,
  mobileNavOpen,
  onGoHome,
  onToggleDarkMode,
  onOpenSidebar,
  onCloseSidebar,
  onLogout,
  onNavigatePage,
  onProfileUpdated,
  showSmartWrongQuestions,
  showCreditCenter,
  showAccounts,
  canOpenPage,
  roleLabel,
  children,
}: {
  activeWorkspacePage: WorkspaceShellPage;
  currentUser: CurrentUser;
  title: string;
  isDark: boolean;
  mobileNavOpen: boolean;
  onGoHome: () => void;
  onToggleDarkMode: () => void;
  onOpenSidebar: () => void;
  onCloseSidebar: () => void;
  onLogout: () => void;
  onNavigatePage: (page: WorkspaceShellPage) => void;
  onProfileUpdated: (username: string, displayName: string) => void;
  showSmartWrongQuestions: boolean;
  showCreditCenter: boolean;
  showAccounts: boolean;
  canOpenPage: (page: WorkspaceShellPage) => boolean;
  roleLabel: string;
  children: ReactNode;
}) {
  const compactSidebar = activeWorkspacePage === 'calendar' || activeWorkspacePage === 'consultation';

  return (
    <div className="relative min-h-[100svh] overflow-x-hidden bg-[#f5f8fc] text-slate-900 sm:min-h-screen dark:bg-[#020617] dark:text-slate-100">
      <div className="relative flex min-h-[100svh] sm:min-h-screen">
        <div className="fixed inset-y-0 left-0 z-30 hidden lg:block">
          <Sidebar
            activePage={activeWorkspacePage}
            currentUser={currentUser}
            onLogout={onLogout}
            setActivePage={onNavigatePage}
            compact={compactSidebar}
            showSmartWrongQuestions={showSmartWrongQuestions}
            showCreditCenter={showCreditCenter}
            showAccounts={showAccounts}
            canOpenPage={canOpenPage}
            roleLabel={roleLabel}
            onProfileUpdated={onProfileUpdated}
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
              <div className="absolute inset-0 bg-slate-950/45 sm:backdrop-blur-sm" onClick={onCloseSidebar} />
              <motion.div
                initial={{ x: -24, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: -24, opacity: 0 }}
                transition={{ duration: 0.18 }}
                className="relative h-full w-[18.5rem] max-w-[86vw]"
              >
                <button
                  type="button"
                  onClick={onCloseSidebar}
                  className="absolute right-3 top-3 z-10 flex h-10 w-10 touch-manipulation items-center justify-center rounded-full border border-slate-200/70 bg-white/90 text-slate-500 shadow-sm transition-colors hover:bg-white hover:text-slate-900 dark:border-white/10 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                  aria-label="关闭导航"
                >
                  <X size={18} />
                </button>
                <Sidebar
                  activePage={activeWorkspacePage}
                  currentUser={currentUser}
                  onLogout={onLogout}
                  setActivePage={onNavigatePage}
                  onNavigate={onCloseSidebar}
                  mobile={true}
                  showSmartWrongQuestions={showSmartWrongQuestions}
                  showCreditCenter={showCreditCenter}
                  showAccounts={showAccounts}
                  canOpenPage={canOpenPage}
                  roleLabel={roleLabel}
                  onProfileUpdated={onProfileUpdated}
                />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
        <main className={cn('flex min-w-0 flex-1 flex-col', compactSidebar ? 'lg:pl-64' : 'lg:pl-[18.5rem]')}>
          <Header
            title={title}
            onGoHome={onGoHome}
            isDark={isDark}
            onToggleDarkMode={onToggleDarkMode}
            onOpenSidebar={onOpenSidebar}
          />
          <div className="flex-1">{children}</div>
        </main>
      </div>
    </div>
  );
}
