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
                  className="absolute right-3 top-3 z-10 flex h-10 w-10 touch-manipulation items-center justify-center rounded-full border border-sky-200 bg-white text-slate-500 shadow-sm transition-colors hover:bg-sky-50 hover:text-slate-800 dark:border-white/10 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
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
        <main className={cn('flex min-w-0 flex-1 flex-col', compactSidebar ? 'lg:pl-24' : 'lg:pl-56')}>
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
