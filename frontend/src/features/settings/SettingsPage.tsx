import type { CurrentUser } from '../../App';
import {
  workspaceCardClass,
  workspacePageClass,
  workspaceSecondaryButtonClass,
  workspaceSectionTitleClass,
} from '../../workspaceShared';

function getRoleLabel(role: CurrentUser['role']): string {
  if (role === 'super_owner') return '超级管理员';
  if (role === 'owner') return '机构负责人';
  if (role === 'admin') return '管理员';
  return '机构成员';
}

type SettingsPageProps = {
  currentUser: CurrentUser;
  onLogout: () => void;
};

export function SettingsPage({ currentUser, onLogout }: SettingsPageProps) {
  return (
    <div className={`${workspacePageClass} mx-auto max-w-3xl space-y-8`}>
      <h3 className={workspaceSectionTitleClass}>系统设置</h3>

      <section className="space-y-4">
        <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">账号</h4>
        <div className={`${workspaceCardClass} flex flex-col gap-5 p-6 md:flex-row md:items-center md:justify-between`}>
          <div>
            <p className="font-medium text-slate-900 dark:text-white">当前账号</p>
            <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">登出后需重新输入账号和密码。</p>
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
}
