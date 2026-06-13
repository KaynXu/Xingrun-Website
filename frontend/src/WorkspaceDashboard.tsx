import { AlertTriangle, ArrowRight, CalendarDays, CheckCircle2, Clock3, FileStack, PlusCircle, Sparkles } from 'lucide-react';

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
  const quickActions = [
    {
      page: 'review-generation' as WorkspacePage,
      label: '新建复习文档',
      icon: PlusCircle,
    },
    {
      page: 'class-feedback-generation' as WorkspacePage,
      label: '补课堂反馈',
      icon: FileStack,
    },
    {
      page: 'calendar' as WorkspacePage,
      label: '查看课程日历',
      icon: CalendarDays,
    },
    {
      page: 'smartWrongQuestions' as WorkspacePage,
      label: '继续错题跟进',
      icon: Sparkles,
    },
  ].filter((entry) => canOpenDashboardPage(currentUser, entry.page));

  const todayQueue = [
    {
      page: 'review-generation' as WorkspacePage,
      title: '生成高二数学复习资料',
      meta: '课堂录音和补充笔记已上传',
      status: '待处理',
      action: '去生成',
    },
    {
      page: 'class-feedback-generation' as WorkspacePage,
      title: '补 2 节课堂反馈',
      meta: '周三、周四课程还未整理',
      status: '今天处理',
      action: '去反馈',
    },
    {
      page: 'smartWrongQuestions' as WorkspacePage,
      title: '跟进 5 条错题',
      meta: '高一英语衔接班 · 需要补掌握状态',
      status: '待跟进',
      action: '去跟进',
    },
  ].filter((entry) => canOpenDashboardPage(currentUser, entry.page));

  const recentOutputs = [
    {
      page: 'review-generation' as WorkspacePage,
      title: '高一英语语法复习单',
      meta: '今天 14:20 · 已导出 PDF',
      status: '已完成',
    },
    {
      page: 'class-feedback-generation' as WorkspacePage,
      title: '七年级数学课堂反馈',
      meta: '今天 11:40 · 待补老师备注',
      status: '草稿',
    },
    {
      page: 'review-generation' as WorkspacePage,
      title: '立体几何阶段复习',
      meta: '昨天 18:05 · 已发送家长群',
      status: '已完成',
    },
  ].filter((entry) => canOpenDashboardPage(currentUser, entry.page));

  const scheduleItems = [
    {
      time: '16:30',
      title: '高一英语衔接班',
      detail: '课前需要打开上次错题记录',
      page: 'smartWrongQuestions' as WorkspacePage,
      action: '查看错题',
    },
    {
      time: '19:00',
      title: '高二数学提高班',
      detail: '下课后直接进入复习生成',
      page: 'review-generation' as WorkspacePage,
      action: '打开生成',
    },
  ].filter((entry) => canOpenDashboardPage(currentUser, entry.page));

  return (
    <div className={`${styles.pageClass} space-y-5`}>
      <section className={`${styles.cardClass} p-5 md:p-6`}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">今日工作</p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">待处理、最近产出和今天课程都在这里。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {quickActions.map((action) => {
              const Icon = action.icon;
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
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">先处理会影响今天上课和课后交付的任务。</p>
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
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">刚做完和还没收尾的文档都放在这里。</p>
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
              <div className="rounded-2xl bg-slate-50 px-4 py-3 dark:bg-white/5">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">复习资料</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">6</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">本周已生成</p>
              </div>
              <div className="rounded-2xl bg-slate-50 px-4 py-3 dark:bg-white/5">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">课堂反馈</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">2</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">待补记录</p>
              </div>
              <div className="rounded-2xl bg-slate-50 px-4 py-3 dark:bg-white/5">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">错题跟进</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">5</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">今天要处理</p>
              </div>
            </div>
          </section>

          <section className={`${styles.cardClass} overflow-hidden p-0`}>
            <div className="border-b border-slate-200/70 px-5 py-4 dark:border-white/10">
              <p className="text-base font-semibold text-slate-900 dark:text-slate-100">今天课程</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">课前和课后要接的动作直接挂在课程后面。</p>
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
  const quickActions = [
    {
      page: 'accounts' as WorkspacePage,
      label: '处理账号审批',
    },
    {
      page: 'classes' as WorkspacePage,
      label: '查看机构班级',
    },
    {
      page: 'settings' as WorkspacePage,
      label: '进入系统设置',
    },
  ];

  const attentionItems = [
    {
      organization: '星润 Starain',
      issue: '账号审批积压 4 条，今天还没有处理。',
      status: '优先处理',
      page: 'accounts' as WorkspacePage,
      action: '去审批',
    },
    {
      organization: '青禾校区',
      issue: '今天 6 节课里还有 3 节没有课堂反馈。',
      status: '待跟进',
      page: 'class-feedback-generation' as WorkspacePage,
      action: '看反馈',
    },
    {
      organization: '城南教学点',
      issue: '近 3 天复习文档产出偏低，需要确认老师是否正常使用。',
      status: '需要观察',
      page: 'review-generation' as WorkspacePage,
      action: '看生成',
    },
  ];

  const platformStats = [
    { label: '今日活跃机构', value: '12', note: '较昨天 +2' },
    { label: '今日生成文档', value: '28', note: '复习资料 / 讲义 / 清单' },
    { label: '待处理审批', value: '7', note: '2 个机构有积压' },
    { label: '待补课堂反馈', value: '9', note: '优先看今天已下课班级' },
  ];

  const organizationRows = [
    {
      organization: '星润 Starain',
      teachers: '8',
      outputs: '11',
      approvals: '4',
      status: '审批积压',
      page: 'accounts' as WorkspacePage,
    },
    {
      organization: '青禾校区',
      teachers: '6',
      outputs: '7',
      approvals: '0',
      status: '反馈未补',
      page: 'class-feedback-generation' as WorkspacePage,
    },
    {
      organization: '城南教学点',
      teachers: '4',
      outputs: '2',
      approvals: '1',
      status: '产出偏低',
      page: 'review-generation' as WorkspacePage,
    },
    {
      organization: '北辰项目组',
      teachers: '5',
      outputs: '8',
      approvals: '0',
      status: '运行正常',
      page: 'classes' as WorkspacePage,
    },
  ];

  return (
    <div className={`${styles.pageClass} space-y-5`}>
      <section className={`${styles.cardClass} p-5 md:p-6`}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">机构观察</p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">今天的积压、异常和机构动态。</p>
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
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">优先看今天积压、漏处理和异常偏低的机构。</p>
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
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">今天有 2 个机构还卡在开通环节。</p>
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
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">优先处理今天已经下课但还没整理的班级。</p>
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
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">确认老师是否正常在生成复习资料和讲义。</p>
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
  const quickActions = [
    {
      page: 'classes' as WorkspacePage,
      label: '查看班级安排',
    },
    {
      page: 'class-feedback-generation' as WorkspacePage,
      label: '补课堂反馈',
    },
    {
      page: canOpenAccounts ? ('accounts' as WorkspacePage) : ('consultation' as WorkspacePage),
      label: canOpenAccounts ? '处理账号审批' : '查看咨询记录',
    },
  ].filter((entry) => canOpenDashboardPage(currentUser, entry.page));

  const pendingItems = [
    {
      page: 'class-feedback-generation' as WorkspacePage,
      title: '今天还有 3 节课没补课堂反馈',
      meta: '优先处理已下课班级，避免教务继续催收集。',
      status: '优先处理',
      action: '去反馈',
    },
    {
      page: 'classes' as WorkspacePage,
      title: '2 个班级本周排课还没确认',
      meta: '周六衔接班和高二数学班需要确认老师安排。',
      status: '待确认',
      action: '看班级',
    },
    {
      page: canOpenAccounts ? ('accounts' as WorkspacePage) : ('consultation' as WorkspacePage),
      title: canOpenAccounts ? '4 条账号审批待处理' : '5 条家长咨询还没跟进',
      meta: canOpenAccounts ? '今天新加入的老师还没完成开通。' : '有 2 条是今天新增咨询，建议优先回。',
      status: canOpenAccounts ? '待审批' : '待回访',
      action: canOpenAccounts ? '去审批' : '去咨询',
    },
  ].filter((entry) => canOpenDashboardPage(currentUser, entry.page));

  const progressStats = [
    { label: '今日上课班级', value: '9', note: '其中 6 节已下课' },
    { label: '课堂反馈完成', value: '6/9', note: '还差 3 节待补' },
    { label: '复习资料产出', value: '8', note: '较昨天正常' },
    { label: canOpenAccounts ? '待审批账号' : '待跟进咨询', value: canOpenAccounts ? '4' : '5', note: canOpenAccounts ? '2 位老师急用' : '2 条今日新增' },
  ];

  const classRows = [
    {
      name: '高二数学提高班',
      schedule: '19:00',
      teacher: '周老师',
      status: '待复习资料',
      page: 'review-generation' as WorkspacePage,
    },
    {
      name: '七年级英语衔接班',
      schedule: '16:30',
      teacher: '王老师',
      status: '待课堂反馈',
      page: 'class-feedback-generation' as WorkspacePage,
    },
    {
      name: '高一语文写作班',
      schedule: '18:00',
      teacher: '李老师',
      status: '运行正常',
      page: 'classes' as WorkspacePage,
    },
  ];

  const sideList = getOrganizationManagementEntries(canOpenAccounts)
    .filter((entry) => canOpenDashboardPage(currentUser, entry.page));

  return (
    <div className={`${styles.pageClass} space-y-5`}>
      <section className={`${styles.cardClass} p-5 md:p-6`}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">机构工作台</p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">待处理事项、班级进度和今日状态。</p>
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
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">今天最容易卡住教务和老师协同的事情放前面。</p>
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
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">今天上课的班级，重点看还没收尾的那几节。</p>
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
