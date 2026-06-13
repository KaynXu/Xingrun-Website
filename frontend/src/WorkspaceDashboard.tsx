import { AlertTriangle, ArrowRight, CalendarDays, CheckCircle2, Clock3, FileStack, PlusCircle, Sparkles } from 'lucide-react';
import { memberDashboardData, organizationDashboardData, platformDashboardData } from './features/dashboard/dashboardMockData';

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
    visible_pages?: WorkspacePage[];
  };
  setActivePage: (page: WorkspacePage) => void;
  styles: WorkspaceStyles;
  canOpenAccounts: boolean;
};

const dashboardQuickActionClass =
  'inline-flex items-center justify-center rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10 dark:hover:text-white';

const dashboardInlineActionClass =
  'inline-flex items-center gap-2 text-sm font-medium text-slate-700 transition hover:text-slate-900 dark:text-slate-200 dark:hover:text-white';

function canOpenDashboardPage(currentUser: WorkspaceDashboardProps['currentUser'], page: WorkspacePage): boolean {
  if (page === 'dashboard' || page === 'settings') {
    return true;
  }
  if (!Array.isArray(currentUser.visible_pages)) {
    return true;
  }
  return currentUser.visible_pages.includes(page);
}

function MemberWorkspace({ currentUser, setActivePage, styles }: WorkspaceDashboardProps) {
  const quickActions = memberDashboardData.quickActions.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const todayQueue = memberDashboardData.todayQueue.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const recentOutputs = memberDashboardData.recentOutputs.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const weeklyStats = memberDashboardData.weeklyStats;
  const scheduleItems = memberDashboardData.schedule.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));

  return (
    <div className={`${styles.pageClass} space-y-5`}>
      <section className={`${styles.cardClass} p-5 md:p-6`}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">今日工作</p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">今天要处理的事都在这里。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {quickActions.map((action) => {
              const Icon =
                action.icon === 'plus'
                  ? PlusCircle
                  : action.icon === 'file'
                    ? FileStack
                    : action.icon === 'calendar'
                      ? CalendarDays
                      : Sparkles;
              return (
                <button key={action.page} type="button" onClick={() => setActivePage(action.page)} className={dashboardQuickActionClass}>
                  <Icon size={16} />
                  {action.label}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(300px,0.75fr)]">
        <div className="space-y-5">
          <section className={`${styles.cardClass} overflow-hidden p-0`}>
            <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-base font-semibold text-slate-900 dark:text-slate-100">今日待办</p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">先看今天还没收尾的事项。</p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-white/10 dark:text-slate-300">
                  {todayQueue.length} 项
                </span>
              </div>
            </div>
            <div className="divide-y divide-slate-200/70 dark:divide-white/10">
              {todayQueue.map((item) => (
                <div key={item.title} className="flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                    <CheckCircle2 size={16} className="shrink-0 text-emerald-500 dark:text-emerald-300" />
                      <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{item.title}</p>
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600 dark:bg-white/10 dark:text-slate-300">
                        {item.status}
                      </span>
                    </div>
                    <p className="mt-1 pl-6 text-sm text-slate-500 dark:text-slate-400">{item.meta}</p>
                  </div>
                  <button type="button" onClick={() => setActivePage(item.page)} className={`${dashboardInlineActionClass} self-start md:self-center`}>
                    {item.action}
                    <ArrowRight size={15} />
                  </button>
                </div>
              ))}
            </div>
          </section>

          <section className={`${styles.cardClass} overflow-hidden p-0`}>
            <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
              <p className="text-base font-semibold text-slate-900 dark:text-slate-100">最近产出</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">最近生成和整理过的内容。</p>
            </div>
            <div className="divide-y divide-slate-200/70 dark:divide-white/10">
              {recentOutputs.map((item) => (
                <button
                  key={item.title}
                  type="button"
                  onClick={() => setActivePage(item.page)}
                  className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-slate-50/80 dark:hover:bg-white/5"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{item.title}</p>
                    <p className="mt-1 truncate text-sm text-slate-500 dark:text-slate-400">{item.meta}</p>
                  </div>
                  <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600 dark:bg-white/10 dark:text-slate-300">
                    {item.status}
                  </span>
                </button>
              ))}
            </div>
          </section>
        </div>

        <div className="space-y-5">
          <section className={`${styles.cardClass} p-5`}>
            <p className="text-base font-semibold text-slate-900 dark:text-slate-100">本周进度</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
              {weeklyStats.map((item) => (
                <div key={item.label} className="rounded-2xl bg-slate-50 px-4 py-3 dark:bg-white/5">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">{item.label}</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">{item.value}</p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{item.note}</p>
                </div>
              ))}
            </div>
          </section>

          <section className={`${styles.cardClass} overflow-hidden p-0`}>
            <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
              <p className="text-base font-semibold text-slate-900 dark:text-slate-100">今天课程</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">今天的课和对应要做的事。</p>
            </div>
            <div className="divide-y divide-slate-200/70 dark:divide-white/10">
              {scheduleItems.map((item) => (
                <div key={`${item.time}-${item.title}`} className="px-5 py-4">
                  <div className="flex items-start gap-3">
                    <div className="flex min-w-12 items-center gap-1 pt-0.5 text-sm font-semibold text-slate-600 dark:text-slate-300">
                      <Clock3 size={14} />
                      {item.time}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{item.title}</p>
                      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{item.detail}</p>
                      <button type="button" onClick={() => setActivePage(item.page)} className={`mt-3 ${dashboardInlineActionClass}`}>
                        {item.action}
                        <ArrowRight size={15} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}

function PlatformWorkspace({ setActivePage, styles }: WorkspaceDashboardProps) {
  const quickActions = platformDashboardData.quickActions;
  const attentionItems = platformDashboardData.attentionItems;
  const platformStats = platformDashboardData.stats;
  const organizationRows = platformDashboardData.organizationRows;

  return (
    <div className={`${styles.pageClass} space-y-5`}>
      <section className={`${styles.cardClass} p-5 md:p-6`}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">机构观察</p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">积压、异常和机构动态。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {quickActions.map((action) => (
                <button key={action.page} type="button" onClick={() => setActivePage(action.page)} className={dashboardQuickActionClass}>
                  {action.label}
                </button>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <section className={`${styles.cardClass} overflow-hidden p-0`}>
          <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
            <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-base font-semibold text-slate-900 dark:text-slate-100">需要关注的机构</p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">今天需要处理和继续观察的机构。</p>
                </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-white/10 dark:text-slate-300">
                {attentionItems.length} 条提醒
              </span>
            </div>
          </div>
          <div className="divide-y divide-slate-200/70 dark:divide-white/10">
            {attentionItems.map((item) => (
              <div key={`${item.organization}-${item.issue}`} className="flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={16} className="shrink-0 text-amber-500 dark:text-amber-300" />
                    <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{item.organization}</p>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600 dark:bg-white/10 dark:text-slate-300">
                      {item.status}
                    </span>
                  </div>
                  <p className="mt-1 pl-6 text-sm text-slate-500 dark:text-slate-400">{item.issue}</p>
                </div>
                <button type="button" onClick={() => setActivePage(item.page)} className={`${dashboardInlineActionClass} self-start md:self-center`}>
                  {item.action}
                  <ArrowRight size={15} />
                </button>
              </div>
            ))}
          </div>
        </section>

        <div className="space-y-5">
          <section className={`${styles.cardClass} p-5`}>
            <p className="text-base font-semibold text-slate-900 dark:text-slate-100">平台运行状态</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              {platformStats.map((item) => (
                <div key={item.label} className="rounded-2xl bg-slate-50 px-4 py-3 dark:bg-white/5">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">{item.label}</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">{item.value}</p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{item.note}</p>
                </div>
              ))}
            </div>
          </section>

          <section className={`${styles.cardClass} overflow-hidden p-0`}>
            <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
              <p className="text-base font-semibold text-slate-900 dark:text-slate-100">今日处理顺序</p>
            </div>
            <div className="divide-y divide-slate-200/70 dark:divide-white/10">
              <button
                type="button"
                onClick={() => setActivePage('accounts')}
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-slate-50/80 dark:hover:bg-white/5"
              >
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">先清掉账号审批</p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">还有机构卡在开通环节。</p>
                </div>
                <ArrowRight size={15} className="shrink-0 text-slate-400 dark:text-slate-500" />
              </button>
              <button
                type="button"
                onClick={() => setActivePage('class-feedback-generation')}
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-slate-50/80 dark:hover:bg-white/5"
              >
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">再看课堂反馈积压</p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">先补今天下课后的反馈。</p>
                </div>
                <ArrowRight size={15} className="shrink-0 text-slate-400 dark:text-slate-500" />
              </button>
              <button
                type="button"
                onClick={() => setActivePage('review-generation')}
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-slate-50/80 dark:hover:bg-white/5"
              >
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">最后看低产出机构</p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">再看今天产出偏低的机构。</p>
                </div>
                <ArrowRight size={15} className="shrink-0 text-slate-400 dark:text-slate-500" />
              </button>
            </div>
          </section>
        </div>
      </section>

      <section className={`${styles.cardClass} overflow-hidden p-0`}>
        <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
          <p className="text-base font-semibold text-slate-900 dark:text-slate-100">机构动态</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">按机构看今天的活跃、产出和积压状态。</p>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[760px]">
            <div className="grid grid-cols-[1.5fr_0.8fr_0.8fr_0.8fr_1fr_120px] gap-4 border-b border-slate-200/70 px-5 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 dark:border-white/10 dark:text-slate-500">
              <span>机构</span>
              <span>活跃老师</span>
              <span>今日产出</span>
              <span>待审批</span>
              <span>状态</span>
              <span className="text-right">操作</span>
            </div>
            {organizationRows.map((row) => (
              <button
                key={row.organization}
                type="button"
                onClick={() => setActivePage(row.page)}
                className="grid w-full grid-cols-[1.5fr_0.8fr_0.8fr_0.8fr_1fr_120px] gap-4 border-b border-slate-200/70 px-5 py-4 text-left transition hover:bg-slate-50/80 last:border-b-0 dark:border-white/10 dark:hover:bg-white/5"
              >
                <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">{row.organization}</span>
                <span className="text-sm text-slate-600 dark:text-slate-300">{row.teachers}</span>
                <span className="text-sm text-slate-600 dark:text-slate-300">{row.outputs}</span>
                <span className="text-sm text-slate-600 dark:text-slate-300">{row.approvals}</span>
                <span className="text-sm text-slate-500 dark:text-slate-400">{row.status}</span>
                <span className="inline-flex items-center justify-end gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                  进入
                  <ArrowRight size={15} />
                </span>
              </button>
            ))}
          </div>
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
  const quickActions = (canOpenAccounts ? organizationDashboardData.quickActions.withAccounts : organizationDashboardData.quickActions.withoutAccounts)
    .filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const pendingItems = (canOpenAccounts ? organizationDashboardData.pendingItems.withAccounts : organizationDashboardData.pendingItems.withoutAccounts)
    .filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const progressStats = canOpenAccounts ? organizationDashboardData.stats.withAccounts : organizationDashboardData.stats.withoutAccounts;
  const classRows = organizationDashboardData.classRows;

  const sideList = getOrganizationManagementEntries(canOpenAccounts)
    .filter((entry) => canOpenDashboardPage(currentUser, entry.page));

  return (
    <div className={`${styles.pageClass} space-y-5`}>
      <section className={`${styles.cardClass} p-5 md:p-6`}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">机构工作台</p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">待处理事项和班级进度都在这里。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {quickActions.map((action) => (
                <button key={action.page} type="button" onClick={() => setActivePage(action.page)} className={dashboardQuickActionClass}>
                  {action.label}
                </button>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <div className="space-y-5">
          <section className={`${styles.cardClass} overflow-hidden p-0`}>
            <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-base font-semibold text-slate-900 dark:text-slate-100">待处理事项</p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">先看今天没收尾的事。</p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-white/10 dark:text-slate-300">
                  {pendingItems.length} 项
                </span>
              </div>
            </div>
            <div className="divide-y divide-slate-200/70 dark:divide-white/10">
              {pendingItems.map((item) => (
                <div key={item.title} className="flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                    <CheckCircle2 size={16} className="shrink-0 text-emerald-500 dark:text-emerald-300" />
                      <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{item.title}</p>
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600 dark:bg-white/10 dark:text-slate-300">
                        {item.status}
                      </span>
                    </div>
                    <p className="mt-1 pl-6 text-sm text-slate-500 dark:text-slate-400">{item.meta}</p>
                  </div>
                  <button type="button" onClick={() => setActivePage(item.page)} className={`${dashboardInlineActionClass} self-start md:self-center`}>
                    {item.action}
                    <ArrowRight size={15} />
                  </button>
                </div>
              ))}
            </div>
          </section>

          <section className={`${styles.cardClass} overflow-hidden p-0`}>
            <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
              <p className="text-base font-semibold text-slate-900 dark:text-slate-100">班级进度</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">今天上课班级的处理情况。</p>
            </div>
            <div className="overflow-x-auto">
              <div className="min-w-[620px]">
                <div className="grid grid-cols-[1.5fr_0.8fr_0.8fr_1fr_110px] gap-4 border-b border-slate-200/70 px-5 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 dark:border-white/10 dark:text-slate-500">
                  <span>班级</span>
                  <span>时间</span>
                  <span>老师</span>
                  <span>状态</span>
                  <span className="text-right">操作</span>
                </div>
                {classRows.map((row) => (
                  <button
                    key={row.name}
                    type="button"
                    onClick={() => setActivePage(row.page)}
                    className="grid w-full grid-cols-[1.5fr_0.8fr_0.8fr_1fr_110px] gap-4 border-b border-slate-200/70 px-5 py-4 text-left transition hover:bg-slate-50/80 last:border-b-0 dark:border-white/10 dark:hover:bg-white/5"
                  >
                    <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">{row.name}</span>
                    <span className="text-sm text-slate-600 dark:text-slate-300">{row.schedule}</span>
                    <span className="text-sm text-slate-600 dark:text-slate-300">{row.teacher}</span>
                    <span className="text-sm text-slate-500 dark:text-slate-400">{row.status}</span>
                    <span className="inline-flex items-center justify-end gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                      进入
                      <ArrowRight size={15} />
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </section>
        </div>

        <div className="space-y-5">
          <section className={`${styles.cardClass} p-5`}>
            <p className="text-base font-semibold text-slate-900 dark:text-slate-100">今日状态</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              {progressStats.map((item) => (
                <div key={item.label} className="rounded-2xl bg-slate-50 px-4 py-3 dark:bg-white/5">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">{item.label}</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">{item.value}</p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{item.note}</p>
                </div>
              ))}
            </div>
          </section>

          <section className={`${styles.cardClass} overflow-hidden p-0`}>
            <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
              <p className="text-base font-semibold text-slate-900 dark:text-slate-100">工作区入口</p>
            </div>
            <div className="divide-y divide-slate-200/70 dark:divide-white/10">
              {sideList.map((entry) => (
                <button
                  key={entry.title}
                  type="button"
                  onClick={() => setActivePage(entry.page)}
                  className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-slate-50/80 dark:hover:bg-white/5"
                >
                  <div>
                    <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{entry.title}</p>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{entry.description}</p>
                  </div>
                  <ArrowRight size={15} className="shrink-0 text-slate-400 dark:text-slate-500" />
                </button>
              ))}
            </div>
          </section>
        </div>
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
