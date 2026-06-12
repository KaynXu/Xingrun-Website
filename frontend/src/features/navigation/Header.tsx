import { Bell, Home, Menu, Moon, Search, Sun } from 'lucide-react';

import { workspaceFieldClass } from '../../workspaceShared';

export function Header({
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
}) {
  void title;

  return (
    <header className="sticky top-0 z-10 flex h-20 items-center justify-end border-b border-sky-100/80 bg-white/92 px-4 sm:bg-white/78 sm:backdrop-blur-xl sm:px-6 md:px-8 dark:border-white/10 dark:bg-[#0f172a]/92 dark:sm:bg-[#0f172a]/88">
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
}
