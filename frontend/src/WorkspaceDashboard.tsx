import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowRight, CalendarDays, CheckCircle2, Clock3, FileStack, PlusCircle, Sparkles } from 'lucide-react';

import { apiFetch } from './workspaceShared';
import type {
  DashboardApiResponse,
  DashboardMemberData,
  DashboardOrganizationData,
  DashboardPage,
  DashboardPlatformData,
  DashboardQuickAction,
  DashboardPlatformPriorityItem,
} from './features/dashboard/dashboardTypes';

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
    id?: number;
    display_name: string;
    role: WorkspaceRole;
    visible_pages?: WorkspacePage[];
  };
  setActivePage: (page: WorkspacePage) => void;
  styles: WorkspaceStyles;
  canOpenAccounts: boolean;
};

type WorkspaceDataState = {
  loading: boolean;
  error: string | null;
  payload: DashboardApiResponse | null;
};

const dashboardQuickActionClass =
  'inline-flex items-center justify-center rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10 dark:hover:text-white';

const dashboardInlineActionClass =
  'inline-flex items-center gap-2 text-sm font-medium text-slate-700 transition hover:text-slate-900 dark:text-slate-200 dark:hover:text-white';

function getDashboardStatusBadgeClass(status: string): string {
  if (status === '已完成' || status === '已确认') {
    return 'rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20';
  }
  if (status === '转写中' || status === '生成中' || status === '排队中') {
    return 'rounded-full bg-sky-50 px-2.5 py-1 text-[11px] font-medium text-sky-700 ring-1 ring-inset ring-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/20';
  }
  if (status === '失败' || status === '低余额') {
    return 'rounded-full bg-rose-50 px-2.5 py-1 text-[11px] font-medium text-rose-700 ring-1 ring-inset ring-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/20';
  }
  if (status === '待处理' || status === '待审批' || status === '待跟进' || status === '待反馈' || status === '待咨询') {
    return 'rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700 ring-1 ring-inset ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/20';
  }
  return 'rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600 dark:bg-white/10 dark:text-slate-300';
}

function getPlatformAttentionTitle(item: DashboardPlatformData['attentionItems'][number]): string {
  if (item.page === 'class-feedback-generation') {
    return `${item.organization} · 课堂反馈`;
  }
  if (item.page === 'consultation') {
    return `${item.organization} · 咨询跟进`;
  }
  if (item.page === 'review-generation') {
    return `${item.organization} · 复习资料`;
  }
  if (item.page === 'accounts') {
    return `${item.organization} · 账号审批`;
  }
  if (item.page === 'credit') {
    return `${item.organization} · 积分余额`;
  }
  return `${item.organization} · ${item.status}`;
}

function getPlatformAttentionDetail(issue: string): string {
  return issue.replace(/^有\s+/, '');
}

function getPlatformPriorityTitle(item: DashboardPlatformPriorityItem): string {
  if (item.page === 'class-feedback-generation') {
    return '进入课堂反馈';
  }
  if (item.page === 'classes') {
    return '查看机构班级';
  }
  if (item.page === 'accounts') {
    return '处理账号审批';
  }
  if (item.page === 'consultation') {
    return '查看咨询记录';
  }
  if (item.page === 'credit') {
    return '查看积分余额';
  }
  if (item.page === 'settings') {
    return '进入系统设置';
  }
  return item.title;
}

const memberQuickActions: DashboardQuickAction[] = [
  { page: 'review-generation', label: '新建复习文档', icon: 'plus' },
  { page: 'class-feedback-generation', label: '补课堂反馈', icon: 'file' },
  { page: 'calendar', label: '查看课程日历', icon: 'calendar' },
  { page: 'smartWrongQuestions', label: '继续错题跟进', icon: 'sparkles' },
];

const platformQuickActions: DashboardQuickAction[] = [
  { page: 'accounts', label: '处理账号审批' },
];

const organizationQuickActions = {
  withAccounts: [
    { page: 'classes', label: '查看班级安排' },
    { page: 'class-feedback-generation', label: '补课堂反馈' },
    { page: 'accounts', label: '处理账号审批' },
  ] satisfies DashboardQuickAction[],
  withoutAccounts: [
    { page: 'classes', label: '查看班级安排' },
    { page: 'class-feedback-generation', label: '补课堂反馈' },
    { page: 'consultation', label: '查看咨询记录' },
  ] satisfies DashboardQuickAction[],
};

const emptyMemberData: DashboardMemberData = {
  todayQueue: [],
  recentOutputs: [],
  weeklyStats: [],
  schedule: [],
};

const emptyOrganizationData: DashboardOrganizationData = {
  pendingItems: [],
  stats: [],
  classRows: [],
};

const emptyPlatformData: DashboardPlatformData = {
  attentionItems: [],
  stats: [],
  organizationRows: [],
  priorityItems: [],
};

function canOpenDashboardPage(currentUser: WorkspaceDashboardProps['currentUser'], page: WorkspacePage): boolean {
  if (page === 'dashboard' || page === 'settings') {
    return true;
  }
  if (!Array.isArray(currentUser.visible_pages)) {
    return true;
  }
  return currentUser.visible_pages.includes(page);
}

function DashboardFetchState({ loading, error }: { loading: boolean; error: string | null }) {
  if (loading) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">正在同步工作台数据...</p>;
  }
  if (error) {
    return (
      <p className="text-sm text-amber-600 dark:text-amber-300">
        {error === 'NOT FOUND' ? '工作台数据暂时不可用，请稍后刷新。' : error}
      </p>
    );
  }
  return null;
}

function DashboardEmptyState({ message }: { message: string }) {
  return <div className="px-5 py-8 text-sm text-slate-500 dark:text-slate-400">{message}</div>;
}

function getDashboardGreetingLabel(now = new Date()): string {
  const hour = now.getHours();
  if (hour < 12) {
    return '早上好';
  }
  if (hour < 18) {
    return '下午好';
  }
  return '晚上好';
}

const platformDashboardMottos = [
  'Small steps, steady progress.',
  'Make today a little lighter.',
  'Keep going. The work will meet you halfway.',
  'One calm move at a time.',
  'Good things compound quietly.',
];

function getRandomPlatformDashboardMotto(): string {
  return platformDashboardMottos[Math.floor(Math.random() * platformDashboardMottos.length)] ?? platformDashboardMottos[0];
}

function DashboardGreeting({
  currentUser,
  label,
  detail,
}: {
  currentUser: WorkspaceDashboardProps['currentUser'];
  label: string;
  detail: string;
}) {
  const displayName = currentUser.display_name?.trim() || '老师';
  const greetingDetail = useMemo(
    () => (detail === 'random-platform-motto' ? getRandomPlatformDashboardMotto() : detail),
    [detail],
  );

  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950 dark:text-slate-100">
        {getDashboardGreetingLabel()}，{displayName}
      </p>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{greetingDetail}</p>
    </div>
  );
}

function DashboardMascot() {
  return (
    <div className="pointer-events-none flex shrink-0 justify-center">
      <img
        src="/xiaoxing.png"
        alt="小星"
        className="h-20 w-auto object-contain sm:h-24 xl:h-28"
        loading="eager"
      />
    </div>
  );
}

function useDashboardData(currentUser: WorkspaceDashboardProps['currentUser']): WorkspaceDataState {
  const [state, setState] = useState<WorkspaceDataState>({
    loading: true,
    error: null,
    payload: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState((previous) => ({ ...previous, loading: true, error: null }));

    apiFetch<DashboardApiResponse>('/api/dashboard')
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setState({ loading: false, error: null, payload });
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        const message = error instanceof Error && error.message ? error.message : '工作台数据加载失败';
        setState({ loading: false, error: message, payload: null });
      });

    return () => {
      cancelled = true;
    };
  }, [currentUser.id, currentUser.role]);

  return state;
}

function MemberWorkspace({
  currentUser,
  setActivePage,
  styles,
  data,
  loading,
  error,
}: WorkspaceDashboardProps & { data: DashboardMemberData; loading: boolean; error: string | null }) {
  const quickActions = memberQuickActions.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const todayQueue = data.todayQueue.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const recentOutputs = data.recentOutputs.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const scheduleItems = data.schedule.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const weeklyStats = data.weeklyStats;

  return (
    <div className={`${styles.pageClass} space-y-5`}>
      <section className={`${styles.cardClass} p-5 md:p-6`}>
        <div className="flex flex-col gap-5">
          <div className="flex items-center gap-10">
            <div className="min-w-0">
              <DashboardGreeting currentUser={currentUser} label="工作台" detail="今天的记录和入口都在这里。" />
              <div className="mt-2">
                <DashboardFetchState loading={loading} error={error} />
              </div>
            </div>
            <DashboardMascot />
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
                  <p className="text-base font-semibold text-slate-900 dark:text-slate-100">待处理</p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">现在还没收尾的记录。</p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-white/10 dark:text-slate-300">
                  {todayQueue.length} 项
                </span>
              </div>
            </div>
            <div className="divide-y divide-slate-200/70 dark:divide-white/10">
              {todayQueue.length === 0 ? (
                <DashboardEmptyState message="现在没有待处理记录。" />
              ) : (
                todayQueue.map((item) => (
                  <div key={`${item.page}-${item.title}`} className="flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 size={16} className="shrink-0 text-emerald-500 dark:text-emerald-300" />
                        <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{item.title}</p>
                        <span className={getDashboardStatusBadgeClass(item.status)}>
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
                ))
              )}
            </div>
          </section>

          <section className={`${styles.cardClass} overflow-hidden p-0`}>
            <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
              <p className="text-base font-semibold text-slate-900 dark:text-slate-100">最近记录</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">最近复习资料的状态流转。</p>
            </div>
            <div className="divide-y divide-slate-200/70 dark:divide-white/10">
              {recentOutputs.length === 0 ? (
                <DashboardEmptyState message="还没有复习资料记录。" />
              ) : (
                recentOutputs.map((item) => (
                  <button
                    key={`${item.page}-${item.title}`}
                    type="button"
                    onClick={() => setActivePage(item.page)}
                    className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-slate-50/80 dark:hover:bg-white/5"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{item.title}</p>
                      <p className="mt-1 truncate text-sm text-slate-500 dark:text-slate-400">{item.meta}</p>
                    </div>
                    <span className={`shrink-0 ${getDashboardStatusBadgeClass(item.status)}`}>
                      {item.status}
                    </span>
                  </button>
                ))
              )}
            </div>
          </section>
        </div>

        <div className="space-y-5">
          <section className={`${styles.cardClass} p-5`}>
            <p className="text-base font-semibold text-slate-900 dark:text-slate-100">本周统计</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
              {weeklyStats.length === 0 ? (
                <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-500 dark:bg-white/5 dark:text-slate-400">暂无统计。</div>
              ) : (
                weeklyStats.map((item) => (
                  <div key={item.label} className="rounded-2xl bg-slate-50 px-4 py-3 dark:bg-white/5">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">{item.label}</p>
                    <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">{item.value}</p>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{item.note}</p>
                  </div>
                ))
              )}
            </div>
          </section>

          <section className={`${styles.cardClass} overflow-hidden p-0`}>
            <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
              <p className="text-base font-semibold text-slate-900 dark:text-slate-100">今天课程</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">今天排课里的班级。</p>
            </div>
            <div className="divide-y divide-slate-200/70 dark:divide-white/10">
              {scheduleItems.length === 0 ? (
                <DashboardEmptyState message="今天还没有排课记录。" />
              ) : (
                scheduleItems.map((item) => (
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
                ))
              )}
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}

function PlatformWorkspace({
  currentUser,
  setActivePage,
  styles,
  data,
  loading,
  error,
}: WorkspaceDashboardProps & { data: DashboardPlatformData; loading: boolean; error: string | null }) {
  const quickActions = platformQuickActions.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const attentionItems = data.attentionItems.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const platformStats = data.stats.slice(0, 4);
  const organizationRows = data.organizationRows.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const priorityItems = data.priorityItems.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));

  return (
    <div className={`${styles.pageClass} space-y-5`}>
      <section className={`${styles.cardClass} p-5 md:p-6`}>
        <div className="flex flex-col gap-5">
          <div className="flex items-center gap-10">
            <div className="min-w-0">
              <DashboardGreeting currentUser={currentUser} label="平台工作台" detail="random-platform-motto" />
              <div className="mt-2 min-h-5">
                <DashboardFetchState loading={loading} error={error} />
              </div>
            </div>
            <DashboardMascot />
          </div>
          <div className="flex flex-wrap gap-2">
            {quickActions.map((action) => (
              <button key={action.page} type="button" onClick={() => setActivePage(action.page)} className={dashboardQuickActionClass}>
                {action.label}
              </button>
            ))}
          </div>
        </div>
        {platformStats.length > 0 && (
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {platformStats.map((item) => (
              <div key={item.label} className="rounded-2xl border border-slate-200/70 bg-slate-50/80 px-4 py-3 dark:border-white/10 dark:bg-white/5">
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{item.label}</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">{item.value}</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{item.note}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <section className={`${styles.cardClass} overflow-hidden p-0`}>
            <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-base font-semibold text-slate-900 dark:text-slate-100">待处理事项</p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">按优先级查看需要处理的反馈、咨询和资料异常。</p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-white/10 dark:text-slate-300">
                  {attentionItems.length} 项
                </span>
              </div>
            </div>
          <div className="divide-y divide-slate-200/70 dark:divide-white/10">
            {attentionItems.length === 0 ? (
              <DashboardEmptyState message="现在没有需要优先处理的事项。" />
            ) : (
              attentionItems.map((item) => (
                <div key={`${item.organization}-${item.issue}`} className="flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <AlertTriangle size={16} className="shrink-0 text-amber-500 dark:text-amber-300" />
                      <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{getPlatformAttentionTitle(item)}</p>
                      <span className={getDashboardStatusBadgeClass(item.status)}>
                        {item.status}
                      </span>
                    </div>
                    <p className="mt-1 pl-6 text-sm text-slate-500 dark:text-slate-400">{getPlatformAttentionDetail(item.issue)}</p>
                  </div>
                  <button type="button" onClick={() => setActivePage(item.page)} className={`${dashboardInlineActionClass} self-start md:self-center`}>
                    {item.action}
                    <ArrowRight size={15} />
                  </button>
                </div>
              ))
            )}
          </div>
        </section>

        <div className="space-y-5">
          <section className={`${styles.cardClass} overflow-hidden p-0`}>
            <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
              <p className="text-base font-semibold text-slate-900 dark:text-slate-100">常用入口</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">直接进入当前最常看的页面。</p>
            </div>
            <div className="divide-y divide-slate-200/70 dark:divide-white/10">
              {priorityItems.length === 0 ? (
                <DashboardEmptyState message="当前没有可显示的常用入口。" />
              ) : (
                priorityItems.map((item: DashboardPlatformPriorityItem) => (
                  <button
                    key={`${item.page}-${item.title}`}
                    type="button"
                    onClick={() => setActivePage(item.page)}
                    className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-slate-50/80 dark:hover:bg-white/5"
                  >
                    <div>
                      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{getPlatformPriorityTitle(item)}</p>
                      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{item.detail}</p>
                    </div>
                    <ArrowRight size={15} className="shrink-0 text-slate-400 dark:text-slate-500" />
                  </button>
                ))
              )}
            </div>
          </section>
        </div>
      </section>

      <section className={`${styles.cardClass} overflow-hidden p-0`}>
        <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
          <p className="text-base font-semibold text-slate-900 dark:text-slate-100">机构列表</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">直接看机构状态，再决定要进哪一页。</p>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[760px]">
            <div className="grid grid-cols-[1.5fr_0.8fr_0.8fr_0.8fr_1fr_120px] gap-4 border-b border-slate-200/70 px-5 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 dark:border-white/10 dark:text-slate-500">
              <span>机构</span>
              <span>成员</span>
              <span>今日资料</span>
              <span>待审批</span>
              <span>状态</span>
              <span className="text-right">操作</span>
            </div>
            {organizationRows.length === 0 ? (
              <DashboardEmptyState message="现在还没有可展示的机构数据。" />
            ) : (
              organizationRows.map((row) => (
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
              ))
            )}
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
      description: '查看班级结构和课程安排。',
      page: 'classes',
    },
    ...(canOpenAccounts
      ? [
          {
            title: '账号审批',
            description: '处理成员开通和账号状态。',
            page: 'accounts' as WorkspacePage,
          },
        ]
      : [
          {
            title: '咨询记录',
            description: '查看家长咨询和跟进状态。',
            page: 'consultation' as WorkspacePage,
          },
        ]),
    {
      title: '课堂反馈',
      description: '进入课堂反馈工作区。',
      page: 'class-feedback-generation',
    },
    {
      title: '智能错题',
      description: '查看学生错题和跟进记录。',
      page: 'smartWrongQuestions',
    },
  ];
}

function OrganizationWorkspace({
  currentUser,
  setActivePage,
  styles,
  canOpenAccounts,
  data,
  loading,
  error,
}: WorkspaceDashboardProps & { data: DashboardOrganizationData; loading: boolean; error: string | null }) {
  const quickActions = (canOpenAccounts ? organizationQuickActions.withAccounts : organizationQuickActions.withoutAccounts)
    .filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const pendingItems = data.pendingItems.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const progressStats = data.stats;
  const classRows = data.classRows.filter((entry) => canOpenDashboardPage(currentUser, entry.page as WorkspacePage));
  const sideList = getOrganizationManagementEntries(canOpenAccounts)
    .filter((entry) => canOpenDashboardPage(currentUser, entry.page));

  return (
    <div className={`${styles.pageClass} space-y-5`}>
      <section className={`${styles.cardClass} p-5 md:p-6`}>
        <div className="flex flex-col gap-5">
          <div className="flex items-center gap-10">
            <div className="min-w-0">
              <DashboardGreeting currentUser={currentUser} label="机构工作台" detail="机构今天的记录和入口。" />
              <div className="mt-2">
                <DashboardFetchState loading={loading} error={error} />
              </div>
            </div>
            <DashboardMascot />
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
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">根据当前真实记录汇总。</p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-white/10 dark:text-slate-300">
                  {pendingItems.length} 项
                </span>
              </div>
            </div>
            <div className="divide-y divide-slate-200/70 dark:divide-white/10">
              {pendingItems.length === 0 ? (
                <DashboardEmptyState message="现在没有待处理事项。" />
              ) : (
                pendingItems.map((item) => (
                  <div key={`${item.page}-${item.title}`} className="flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 size={16} className="shrink-0 text-emerald-500 dark:text-emerald-300" />
                        <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{item.title}</p>
                      <span className={getDashboardStatusBadgeClass(item.status)}>
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
                ))
              )}
            </div>
          </section>

          <section className={`${styles.cardClass} overflow-hidden p-0`}>
            <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
              <p className="text-base font-semibold text-slate-900 dark:text-slate-100">班级进度</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">今天排课里的班级。</p>
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
                {classRows.length === 0 ? (
                  <DashboardEmptyState message="今天还没有排课记录。" />
                ) : (
                  classRows.map((row) => (
                    <button
                      key={`${row.name}-${row.schedule}`}
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
                  ))
                )}
              </div>
            </div>
          </section>
        </div>

        <div className="space-y-5">
          <section className={`${styles.cardClass} p-5`}>
            <p className="text-base font-semibold text-slate-900 dark:text-slate-100">今日状态</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              {progressStats.length === 0 ? (
                <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-500 dark:bg-white/5 dark:text-slate-400">暂无统计。</div>
              ) : (
                progressStats.map((item) => (
                  <div key={item.label} className="rounded-2xl bg-slate-50 px-4 py-3 dark:bg-white/5">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">{item.label}</p>
                    <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">{item.value}</p>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{item.note}</p>
                  </div>
                ))
              )}
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
  const { loading, error, payload } = useDashboardData(currentUser);

  const memberData = useMemo(() => payload?.member ?? emptyMemberData, [payload]);
  const organizationData = useMemo(() => payload?.organization ?? emptyOrganizationData, [payload]);
  const platformData = useMemo(() => payload?.platform ?? emptyPlatformData, [payload]);

  if (currentUser.role === 'member') {
    return (
      <MemberWorkspace
        currentUser={currentUser}
        setActivePage={setActivePage}
        styles={styles}
        canOpenAccounts={canOpenAccounts}
        data={memberData}
        loading={loading}
        error={error}
      />
    );
  }

  if (currentUser.role === 'owner' || currentUser.role === 'admin') {
    return (
      <OrganizationWorkspace
        currentUser={currentUser}
        setActivePage={setActivePage}
        styles={styles}
        canOpenAccounts={canOpenAccounts}
        data={organizationData}
        loading={loading}
        error={error}
      />
    );
  }

  return (
    <PlatformWorkspace
      currentUser={currentUser}
      setActivePage={setActivePage}
      styles={styles}
      canOpenAccounts={canOpenAccounts}
      data={platformData}
      loading={loading}
      error={error}
    />
  );
}
