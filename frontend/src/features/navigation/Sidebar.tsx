import { useState } from 'react';
import { createPortal } from 'react-dom';
import {
  ArrowUp,
  Bell,
  CalendarDays,
  Cpu,
  FileText,
  Home,
  LayoutDashboard,
  Library,
  MessageSquare,
  MoreVertical,
  Settings,
  User,
  type LucideIcon,
} from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';

import type { CurrentUser } from '../../appTypes';
import {
  apiFetch,
  buildDiceBearAvatarUrl,
  cn,
  workspaceCardClass,
  workspaceFieldClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSoftCardClass,
} from '../../workspaceShared';

type SidebarPage =
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

type SidebarEntry = {
  id: SidebarPage;
  icon: LucideIcon;
  label: string;
};

function getFallbackRoleLabel(role: CurrentUser['role']): string {
  if (role === 'super_owner') return '超级管理员';
  if (role === 'owner') return '机构负责人';
  if (role === 'admin') return '管理员';
  return '成员老师';
}

export const SidebarAccountSheet = ({
  currentUser,
  open,
  onClose,
  onLogout,
  onOpenSettings,
  onProfileUpdated,
  roleLabel,
}: {
  currentUser: CurrentUser;
  open: boolean;
  onClose: () => void;
  onLogout: () => void;
  onOpenSettings: () => void;
  onProfileUpdated?: (username: string, displayName: string) => void;
  roleLabel?: string;
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

  const resolvedRoleLabel = roleLabel ?? getFallbackRoleLabel(currentUser.role);
  const shouldShowDisplayName = currentUser.display_name.trim() && currentUser.display_name !== currentUser.username;
  const avatarUrl = buildDiceBearAvatarUrl(currentUser);

  const sheet = (
    <div className="fixed inset-0 z-[70] pointer-events-none">
      <button
        type="button"
        aria-label="关闭账号面板"
        onClick={onClose}
        className="absolute inset-0 pointer-events-auto bg-transparent"
      />
      <div className="absolute bottom-4 left-4 w-[calc(100vw-2rem)] max-w-[22rem] pointer-events-auto" onClick={(e) => e.stopPropagation()}>
        <div className={`${workspaceCardClass} overflow-hidden rounded-[2rem] border border-slate-200/80 bg-white p-5 dark:border-white/10 dark:bg-slate-950/92`}>
          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 items-start gap-3">
              <img src={avatarUrl} alt={`${currentUser.display_name || currentUser.username} 头像`} className="h-12 w-12 shrink-0 rounded-xl bg-slate-100 object-cover dark:bg-white/10" />
              <div className="min-w-0 pt-0.5">
                <p className="truncate text-lg font-semibold text-slate-900 dark:text-slate-100">{currentUser.username}</p>
                {shouldShowDisplayName && (
                  <p className="truncate text-sm text-slate-500 dark:text-slate-400">{currentUser.display_name}</p>
                )}
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 dark:bg-white/10 dark:text-slate-300">
                    {resolvedRoleLabel}
                  </span>
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 dark:text-slate-500 dark:hover:bg-white/10 dark:hover:text-slate-200"
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
              <div className="mt-5 border-t border-slate-200/80 pt-3 dark:border-white/10">
                <div className="space-y-1">
                <button
                  type="button"
                  onClick={startEdit}
                  className="w-full rounded-xl px-4 py-3 text-left text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-100 dark:hover:bg-white/5"
                >
                  修改账号 / 姓名
                </button>
                <button
                  type="button"
                  onClick={onOpenSettings}
                  className="w-full rounded-xl px-4 py-3 text-left text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-100 dark:hover:bg-white/5"
                >
                  查看账号信息
                </button>
                <button
                  type="button"
                  onClick={onLogout}
                  className="w-full rounded-xl px-4 py-3 text-left text-sm font-medium text-rose-500 transition-colors hover:bg-rose-50/70 hover:text-rose-600 dark:text-rose-300 dark:hover:bg-rose-500/10 dark:hover:text-rose-200"
                >
                  退出登录
                </button>
                </div>
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

export function Sidebar({
  activePage,
  currentUser,
  onLogout,
  setActivePage,
  onNavigate,
  mobile,
  compact,
  onProfileUpdated,
  showSmartWrongQuestions,
  showCreditCenter,
  showAccounts,
  canOpenPage,
  roleLabel,
}: {
  activePage: SidebarPage;
  currentUser: CurrentUser;
  onLogout: () => void;
  setActivePage: (page: SidebarPage) => void;
  onNavigate?: () => void;
  mobile?: boolean;
  compact?: boolean;
  onProfileUpdated?: (username: string, displayName: string) => void;
  showSmartWrongQuestions: boolean;
  showCreditCenter: boolean;
  showAccounts: boolean;
  canOpenPage: (page: SidebarPage) => boolean;
  roleLabel?: string;
}) {
  const [accountSheetOpen, setAccountSheetOpen] = useState(false);
  const dashboardItems = ([
    { id: 'dashboard', icon: LayoutDashboard, label: '工作台' },
  ] satisfies SidebarEntry[]).filter((item) => canOpenPage(item.id));
  const teachingItems = ([
    { id: 'review-generation', icon: Library, label: '复习生成' },
    { id: 'class-feedback-generation', icon: FileText, label: '课堂反馈' },
    { id: 'consultation', icon: MessageSquare, label: '咨询记录' },
    { id: 'calendar', icon: CalendarDays, label: '课程日历' },
    ...(showSmartWrongQuestions
      ? [{ id: 'smartWrongQuestions', icon: Cpu, label: '智能错题' } satisfies SidebarEntry]
      : []),
  ] satisfies SidebarEntry[]).filter((item) => canOpenPage(item.id));
  const organizationManagementItems = ([
    { id: 'classes', icon: Home, label: '学管中心' },
    ...(showCreditCenter
      ? [{ id: 'credit', icon: Bell, label: '积分中心' } satisfies SidebarEntry]
      : []),
    ...(showAccounts
      ? [{ id: 'accounts', icon: User, label: '账号审批' } satisfies SidebarEntry]
      : []),
  ] satisfies SidebarEntry[]).filter((item) => canOpenPage(item.id));
  const systemItems = ([
    { id: 'settings', icon: Settings, label: '系统设置' },
  ] satisfies SidebarEntry[]).filter((item) => canOpenPage(item.id));
  const menuSections = [
    { label: '总览', items: dashboardItems },
    { label: '教学工作', items: teachingItems },
    { label: '机构管理', items: organizationManagementItems },
    { label: '系统', items: systemItems },
  ].filter((section) => section.items.length > 0);

  const resolvedRoleLabel = roleLabel ?? getFallbackRoleLabel(currentUser.role);
  const avatarUrl = buildDiceBearAvatarUrl(currentUser);

  return (
    <div
      className={cn(
        'flex flex-col overflow-hidden border-r border-slate-200/70 bg-[#fbfdff] dark:border-white/10 dark:bg-[#0b1220]',
        mobile
          ? 'h-full w-full overflow-y-auto overscroll-y-auto [-webkit-overflow-scrolling:touch]'
          : compact
            ? 'h-screen w-[15.5rem]'
            : 'h-screen w-[17.25rem]',
      )}
    >
      <div className={cn('flex h-[4.75rem] items-center border-b border-slate-200/70 dark:border-white/10', compact && !mobile ? 'px-4' : 'px-5')}>
        <div className={cn('flex items-center gap-3', compact && !mobile && 'justify-center')}>
          <img src="/logo.png" alt="星润 logo" className="h-9 w-9 object-contain" />
          <div className={cn(compact && !mobile && 'hidden')}>
            <h1 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">Starain 工作台</h1>
            <p className="mt-1 text-xs font-semibold uppercase tracking-[0.26em] text-slate-400 dark:text-slate-500">机构工作台</p>
          </div>
        </div>
      </div>

      <nav
        className={cn(
          'min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain py-3 pr-1 [scrollbar-gutter:stable] [-webkit-overflow-scrolling:touch]',
          compact && !mobile ? 'px-3' : 'px-3',
        )}
      >
        {menuSections.map((section) => (
          <div key={section.label} className="space-y-1">
            <p className={cn('px-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500', compact && !mobile && 'hidden')}>
              {section.label}
            </p>
            <div className="space-y-0.5 px-1">
              {section.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  title={compact && !mobile ? item.label : undefined}
                  onClick={() => {
                    setActivePage(item.id);
                    onNavigate?.();
                  }}
                  className={cn(
                    'group/nav-item relative flex w-full touch-manipulation items-center gap-2 rounded-xl px-2.5 py-2 text-left transition-all duration-200',
                    compact && !mobile && 'justify-center px-2',
                    activePage === item.id
                      ? 'bg-sky-50 text-slate-900 dark:bg-white/10 dark:text-slate-100'
                      : 'text-slate-500 hover:bg-white hover:text-slate-900 dark:text-slate-400 dark:hover:bg-white/5 dark:hover:text-slate-100',
                  )}
                >
                  <span
                    className={cn(
                      'flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-slate-500 transition-colors',
                      activePage === item.id
                        ? 'text-blue-600 dark:text-sky-300'
                        : 'group-hover/nav-item:text-slate-700 dark:text-slate-300',
                    )}
                  >
                    <item.icon size={16} />
                  </span>
                  <div className={cn('min-w-0 flex-1', compact && !mobile && 'hidden')}>
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">{item.label}</span>
                    </div>
                  </div>
                  {compact && !mobile && (
                    <span className="pointer-events-none absolute left-[calc(100%+0.5rem)] top-1/2 z-40 -translate-y-1/2 whitespace-nowrap rounded-lg border border-slate-200/70 bg-white px-2.5 py-1.5 text-xs font-bold text-slate-700 opacity-0 transition group-hover/nav-item:opacity-100 dark:border-white/10 dark:bg-slate-900 dark:text-slate-100">
                      {item.label}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className={cn('mt-auto p-3', compact && !mobile && 'px-3')}>
        <button
          type="button"
          onClick={() => setAccountSheetOpen(true)}
          className={cn('flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-slate-100/80 dark:hover:bg-white/5', compact && !mobile && 'justify-center')}
        >
          <img src={avatarUrl} alt={`${currentUser.display_name || currentUser.username} 头像`} className="h-10 w-10 shrink-0 rounded-full bg-slate-100 object-cover dark:bg-white/10" />
          <div className={cn('min-w-0 flex-1', compact && !mobile && 'hidden')}>
            <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">{currentUser.username}</p>
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">{resolvedRoleLabel}</p>
          </div>
          <MoreVertical size={16} className={cn('shrink-0 text-slate-400 dark:text-slate-500', compact && !mobile && 'hidden')} />
        </button>
      </div>

      <button
        type="button"
        onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
        className="fixed bottom-6 right-6 z-20 flex h-11 w-11 items-center justify-center rounded-full bg-slate-900 text-white transition hover:bg-slate-700 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200"
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
              roleLabel={resolvedRoleLabel}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
