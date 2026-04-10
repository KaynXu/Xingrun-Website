import React from 'react';
import { ArrowRight, PlusCircle } from 'lucide-react';

type WorkspaceRole = 'super_owner' | 'owner' | 'admin' | 'member';
type WorkspacePage = 'dashboard' | 'review-generation' | 'class-feedback-generation' | 'consultation' | 'calendar' | 'smartWrongQuestions' | 'classes' | 'accounts' | 'credit' | 'settings';
type WorkspaceStyles = {
  pageClass: string;
  cardClass: string;
  primaryButtonClass: string;
  secondaryButtonClass: string;
};

type WorkspaceDashboardProps = {
  currentUser: {
    display_name: string;
    role: WorkspaceRole;
  };
  setActivePage: (page: WorkspacePage) => void;
  styles: WorkspaceStyles;
  canOpenAccounts: boolean;
};

function MemberWorkspace({ currentUser, setActivePage, styles }: WorkspaceDashboardProps) {
  return (
    <div className={`${styles.pageClass} space-y-6`}>
      <section className="rounded-[2rem] border border-sky-100 bg-[radial-gradient(circle_at_top_left,_rgba(34,199,232,0.18),_transparent_32%),linear-gradient(135deg,_rgba(255,255,255,0.98)_0%,_rgba(236,246,255,0.92)_52%,_rgba(223,241,255,0.96)_100%)] p-6 shadow-[0_24px_72px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.15),_transparent_30%),linear-gradient(135deg,_rgba(15,23,42,0.98)_0%,_rgba(17,24,39,0.95)_52%,_rgba(30,41,59,0.96)_100%)] dark:shadow-[0_28px_80px_rgba(2,6,23,0.36)] md:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">Teaching flow</p>
        <div className="mt-4 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="space-y-3">
            <h3 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">快速开始</h3>
            <p className="max-w-2xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">
              欢迎回来，{currentUser.display_name}。直接进入真实可用的教学动作，首页只放已经落地的工作入口和说明区。
            </p>
          </div>
          <button type="button" onClick={() => setActivePage('review-generation')} className={styles.primaryButtonClass}>
            <PlusCircle size={18} />
            新建复习文档
          </button>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <button type="button" onClick={() => setActivePage('review-generation')} className={`${styles.cardClass} flex min-h-32 flex-col items-start justify-between p-5 text-left`}>
          <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">复习生成</span>
          <span className="text-sm leading-relaxed text-slate-500 dark:text-slate-400">继续生成讲义、错题回顾和阶段复习资料。</span>
        </button>
        <button type="button" onClick={() => setActivePage('class-feedback-generation')} className={`${styles.cardClass} flex min-h-32 flex-col items-start justify-between p-5 text-left`}>
          <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">课堂反馈</span>
          <span className="text-sm leading-relaxed text-slate-500 dark:text-slate-400">进入班级反馈生成，整理本节课教学结论。</span>
        </button>
        <button type="button" onClick={() => setActivePage('calendar')} className={`${styles.cardClass} flex min-h-32 flex-col items-start justify-between p-5 text-left`}>
          <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">课程日历</span>
          <span className="text-sm leading-relaxed text-slate-500 dark:text-slate-400">查看课程安排，切换到本周和后续排课视图。</span>
        </button>
        <button type="button" onClick={() => setActivePage('smartWrongQuestions')} className={`${styles.cardClass} flex min-h-32 flex-col items-start justify-between p-5 text-left`}>
          <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">智能错题</span>
          <span className="text-sm leading-relaxed text-slate-500 dark:text-slate-400">查看学生错题，继续记录错因和掌握情况。</span>
        </button>
      </section>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(280px,0.85fr)]">
        <div className={`${styles.cardClass} p-6`}>
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">我的教学概览</p>
              <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">
                这里承接你自己的教学工作视角，首版先保留真实概览区，集中说明班级、反馈和复习资料入口。
              </p>
            </div>
            <ArrowRight size={18} className="shrink-0 text-sky-500 dark:text-sky-400" />
          </div>
        </div>

        <div className={`${styles.cardClass} p-6`}>
          <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">最近工作</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">
            这里会继续展示复习生成、课堂反馈和错题跟进的最近记录。当前阶段先保留真实说明，不伪造任务列表。
          </p>
        </div>
      </section>
    </div>
  );
}

function PlatformWorkspace({ currentUser, setActivePage, styles }: WorkspaceDashboardProps) {
  return (
    <div className={`${styles.pageClass} space-y-6`}>
      <section className="rounded-[2rem] border border-sky-100 bg-[radial-gradient(circle_at_top_left,_rgba(34,199,232,0.18),_transparent_32%),linear-gradient(135deg,_rgba(255,255,255,0.98)_0%,_rgba(236,246,255,0.92)_52%,_rgba(223,241,255,0.96)_100%)] p-6 shadow-[0_24px_72px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.15),_transparent_30%),linear-gradient(135deg,_rgba(15,23,42,0.98)_0%,_rgba(17,24,39,0.95)_52%,_rgba(30,41,59,0.96)_100%)] dark:shadow-[0_28px_80px_rgba(2,6,23,0.36)] md:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">Platform command</p>
        <div className="mt-4 space-y-3">
          <h3 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">平台总览</h3>
          <p className="max-w-3xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">
            欢迎回来，{currentUser.display_name}。这里聚焦跨机构观察、平台账号审批与系统级配置入口，不再沿用机构工作流首页。
          </p>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className={`${styles.cardClass} min-h-32 p-5`}>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">Overview</p>
          <p className="mt-3 text-lg font-semibold text-slate-900 dark:text-slate-100">平台总览</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">保留平台级概览壳层，后续承接跨机构运行指标和核心状态。</p>
        </div>
        <button type="button" onClick={() => setActivePage('classes')} className={`${styles.cardClass} flex min-h-32 flex-col items-start justify-between p-5 text-left`}>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">Organizations</p>
            <p className="mt-3 text-lg font-semibold text-slate-900 dark:text-slate-100">机构观察</p>
            <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">通过现有机构管理视图进入组织工作区，查看机构开通、活跃度和跨机构运营切面。</p>
          </div>
          <span className="inline-flex items-center gap-2 text-sm font-medium text-sky-600 dark:text-sky-400">
            查看机构工作区
            <ArrowRight size={16} />
          </span>
        </button>
        <button type="button" onClick={() => setActivePage('accounts')} className={`${styles.cardClass} flex min-h-32 flex-col items-start justify-between p-5 text-left`}>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">Approval</p>
            <p className="mt-3 text-lg font-semibold text-slate-900 dark:text-slate-100">账号审批</p>
            <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">处理跨机构账号开通、归属确认与审批入口。</p>
          </div>
          <span className="inline-flex items-center gap-2 text-sm font-medium text-sky-600 dark:text-sky-400">
            进入审批
            <ArrowRight size={16} />
          </span>
        </button>
        <button type="button" onClick={() => setActivePage('settings')} className={`${styles.cardClass} flex min-h-32 flex-col items-start justify-between p-5 text-left`}>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">Settings</p>
            <p className="mt-3 text-lg font-semibold text-slate-900 dark:text-slate-100">系统设置</p>
            <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">进入系统级配置，维护平台运行所需的全局参数。</p>
          </div>
          <span className="inline-flex items-center gap-2 text-sm font-medium text-sky-600 dark:text-sky-400">
            打开设置
            <ArrowRight size={16} />
          </span>
        </button>
      </section>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
        <div className={`${styles.cardClass} p-6`}>
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">机构观察</p>
              <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">
                这里保留跨机构观察区，承接组织状态、平台覆盖面和异常排查入口的真实壳层。
              </p>
            </div>
            <ArrowRight size={18} className="shrink-0 text-sky-500 dark:text-sky-400" />
          </div>
        </div>

        <div className={`${styles.cardClass} p-6`}>
          <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">系统设置</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">
            平台级设置入口已经可达，当前首页只保留真实入口说明，不添加虚构通知或任务系统。
          </p>
        </div>
      </section>
    </div>
  );
}

type OrganizationManagementEntry = {
  title: string;
  description: string;
  page: WorkspacePage;
};

export function getOrganizationManagementEntries(canOpenAccounts: boolean): OrganizationManagementEntry[] {
  return [
    {
      title: '班级管理',
      description: '查看班级结构、课程安排和成员协同入口。',
      page: 'classes',
    },
    ...(canOpenAccounts
      ? [
          {
            title: '账号审批',
            description: '处理老师与成员账号开通、状态确认和组织归属。',
            page: 'accounts' as WorkspacePage,
          },
        ]
      : [
          {
            title: '咨询记录',
            description: '进入咨询记录页，查看家长需求、跟进状态与来源信息。',
            page: 'consultation' as WorkspacePage,
          },
        ]),
    {
      title: '课堂反馈',
      description: '进入班级反馈工作区，跟进当周教学记录与产出。',
      page: 'class-feedback-generation',
    },
    {
      title: '智能错题',
      description: '查看学生错题，继续记录错因和掌握情况。',
      page: 'smartWrongQuestions',
    },
  ];
}

function OrganizationWorkspace({ currentUser, setActivePage, styles, canOpenAccounts }: WorkspaceDashboardProps) {
  const managementEntries = getOrganizationManagementEntries(canOpenAccounts);

  return (
    <div className={`${styles.pageClass} space-y-6`}>
      <section className="rounded-[2rem] border border-sky-100 bg-[radial-gradient(circle_at_top_left,_rgba(34,199,232,0.18),_transparent_32%),linear-gradient(135deg,_rgba(255,255,255,0.98)_0%,_rgba(236,246,255,0.92)_52%,_rgba(223,241,255,0.96)_100%)] p-6 shadow-[0_24px_72px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.15),_transparent_30%),linear-gradient(135deg,_rgba(15,23,42,0.98)_0%,_rgba(17,24,39,0.95)_52%,_rgba(30,41,59,0.96)_100%)] dark:shadow-[0_28px_80px_rgba(2,6,23,0.36)] md:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">Operations focus</p>
        <div className="mt-4 space-y-3">
          <h3 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">机构运营概览</h3>
          <p className="max-w-3xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">
            欢迎回来，{currentUser.display_name}。首页聚焦已经可用的机构管理入口和当前运营观察区，不继续把复习生成放在页面中心。
          </p>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-4">
        <div className={`${styles.cardClass} min-h-28 p-5`}>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">Overview</p>
          <p className="mt-3 text-lg font-semibold text-slate-900 dark:text-slate-100">机构运营概览</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">保留真实概览壳层，后续承接组织级运营指标。</p>
        </div>
        <div className={`${styles.cardClass} min-h-28 p-5`}>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">Classes</p>
          <p className="mt-3 text-lg font-semibold text-slate-900 dark:text-slate-100">班级管理</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">围绕班级和排课组织日常协同。</p>
        </div>
        <div className={`${styles.cardClass} min-h-28 p-5`}>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">{canOpenAccounts ? 'Approval' : 'Consultation'}</p>
          <p className="mt-3 text-lg font-semibold text-slate-900 dark:text-slate-100">{canOpenAccounts ? '账号审批' : '咨询记录'}</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">
            {canOpenAccounts ? '成员开通与组织归属在这里集中处理。' : '已落地的咨询记录入口可以作为机构运营协同补位。'}
          </p>
        </div>
        <div className={`${styles.cardClass} min-h-28 p-5`}>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">Teaching</p>
          <p className="mt-3 text-lg font-semibold text-slate-900 dark:text-slate-100">课堂反馈</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">教学记录和错题跟进从这里继续推进。</p>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {managementEntries.map((entry) => (
          <button
            key={entry.title}
            type="button"
            onClick={() => setActivePage(entry.page)}
            className={`${styles.cardClass} flex min-h-36 flex-col items-start justify-between p-5 text-left`}
          >
            <div>
              <p className="text-base font-semibold text-slate-900 dark:text-slate-100">{entry.title}</p>
              <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">{entry.description}</p>
            </div>
            <span className="inline-flex items-center gap-2 text-sm font-medium text-sky-600 dark:text-sky-400">
              进入工作区
              <ArrowRight size={16} />
            </span>
          </button>
        ))}
      </section>
    </div>
  );
}

export function WorkspaceDashboard({ currentUser, setActivePage, styles, canOpenAccounts }: WorkspaceDashboardProps) {
  if (currentUser.role === 'member') {
    return <MemberWorkspace currentUser={currentUser} setActivePage={setActivePage} styles={styles} canOpenAccounts={canOpenAccounts} />;
  }

  if (currentUser.role === 'owner' || currentUser.role === 'admin') {
    return <OrganizationWorkspace currentUser={currentUser} setActivePage={setActivePage} styles={styles} canOpenAccounts={canOpenAccounts} />;
  }

  return <PlatformWorkspace currentUser={currentUser} setActivePage={setActivePage} styles={styles} canOpenAccounts={canOpenAccounts} />;
}