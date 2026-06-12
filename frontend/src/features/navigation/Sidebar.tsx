import React, { useState } from 'react';
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
} from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';

import type { CurrentUser } from '../../App';
import {
  apiFetch,
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

  const sheet = (
    <div className="fixed inset-0 z-[70]" onClick={onClose}>
      <div className="absolute inset-0 bg-slate-950/28" />
      <div className="absolute bottom-4 left-4 w-[calc(100vw-2rem)] max-w-sm" onClick={(e) => e.stopPropagation()}>
        <div className={`${workspaceCardClass} p-6`}>
          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 items-center gap-4">
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
                  <span className="dark:text-slate-100">{resolvedRoleLabel}</span>
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
  const menuItems = [
    ...[
      { id: 'dashboard', icon: LayoutDashboard, label: '工作台' },
      { id: 'review-generation', icon: Library, label: '复习生成' },
      { id: 'class-feedback-generation', icon: FileText, label: '课堂反馈' },
      { id: 'consultation', icon: MessageSquare, label: '咨询记录' },
      { id: 'calendar', icon: CalendarDays, label: '课程日历' },
      ...(showSmartWrongQuestions
        ? [{ id: 'smartWrongQuestions', icon: Cpu, label: '智能错题' }]
        : []),
      { id: 'classes', icon: Home, label: '学管中心' },
      ...(showCreditCenter ? [{ id: 'credit', icon: Bell, label: '积分中心' }] : []),
      ...(showAccounts ? [{ id: 'accounts', icon: User, label: '账号审批' }] : []),
      { id: 'settings', icon: Settings, label: '系统设置' },
    ].filter((item) => canOpenPage(item.id as SidebarPage)),
  ];

  const resolvedRoleLabel = roleLabel ?? getFallbackRoleLabel(currentUser.role);

  return (
    <div
      className={cn(
        'flex flex-col border-r border-sky-100/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96)_0%,rgba(239,248,255,0.92)_52%,rgba(231,243,255,0.96)_100%)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(8,15,30,0.98)_0%,rgba(15,23,42,0.96)_52%,rgba(17,24,39,0.98)_100%)]',
        mobile
          ? 'h-full w-full overflow-y-auto overscroll-y-auto [-webkit-overflow-scrolling:touch] shadow-[18px_0_48px_rgba(47,128,237,0.12)] dark:shadow-[18px_0_48px_rgba(2,6,23,0.48)]'
          : compact
            ? 'h-screen w-24 shadow-[18px_0_48px_rgba(47,128,237,0.06)] dark:shadow-[18px_0_48px_rgba(2,6,23,0.38)]'
            : 'h-screen w-56 shadow-[18px_0_48px_rgba(47,128,237,0.06)] dark:shadow-[18px_0_48px_rgba(2,6,23,0.38)]',
      )}
    >
      <div className={cn('border-b border-sky-100/80 py-6 dark:border-white/10', compact && !mobile ? 'px-4' : 'px-6')}>
        <div className={cn('flex items-center gap-3', compact && !mobile && 'justify-center')}>
          <img src="/logo.png" alt="星润 logo" className="h-10 w-10 object-contain" />
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
              setActivePage(item.id as SidebarPage);
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
          <div className={cn('min-w-0 flex-1', compact && !mobile && 'hidden')}>
            <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">{currentUser.display_name}</p>
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">{resolvedRoleLabel}</p>
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
              roleLabel={resolvedRoleLabel}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
