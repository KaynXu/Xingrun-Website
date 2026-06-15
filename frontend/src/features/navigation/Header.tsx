import { Bell, Home, Menu, Moon, Sun } from 'lucide-react';

const headerButtonClass =
  'flex h-11 w-11 items-center justify-center rounded-full border border-slate-200/70 bg-white/90 text-slate-500 transition-colors hover:bg-white hover:text-slate-900 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white';

export function Header({
  title: _title,
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
}) {
  return (
    <header className="sticky top-0 z-10 border-b border-slate-200/70 bg-[rgba(251,253,255,0.88)] backdrop-blur-xl dark:border-white/10 dark:bg-[#0f172a]/88">
      <div className="flex h-[4.75rem] items-center justify-end gap-4 px-4 sm:px-6 md:px-8">
        <div className="flex items-center gap-2 sm:gap-3">
          {onOpenSidebar && (
            <button
              type="button"
              onClick={onOpenSidebar}
              title="打开导航"
              aria-label="打开导航"
              className={`${headerButtonClass} touch-manipulation lg:hidden`}
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
              className={headerButtonClass}
            >
              {isDark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          )}
          {onGoHome && (
            <button
              type="button"
              onClick={onGoHome}
              title="返回首页"
              className={headerButtonClass}
            >
              <Home size={20} />
            </button>
          )}
          <button className={`${headerButtonClass} relative hidden md:flex`}>
            <Bell size={20} />
            <span className="absolute right-2 top-2 h-2.5 w-2.5 rounded-full border-2 border-white bg-rose-400 dark:border-slate-900" />
          </button>
        </div>
      </div>
    </header>
  );
}
