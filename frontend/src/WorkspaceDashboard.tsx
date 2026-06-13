import { ArrowRight, CalendarDays, CheckCircle2, Clock3, FileStack, PlusCircle, Sparkles } from 'lucide-react';

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
            <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">今天先做这几件事</p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">把复习资料、课堂反馈和错题跟进接上，不用来回找页面。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {quickActions.map((action) => {
              const Icon = action.icon;
              return (
                <button
                  key={action.page}
                  type="button"
                  onClick={() => setActivePage(action.page)}
                  className={`${styles.secondaryButtonClass} px-4 py-2.5 text-sm`}
                >
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
                <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:bg-sky-500/10 dark:text-sky-300">
                  {todayQueue.length} 项
                </span>
              </div>
            </div>
            <div className="divide-y divide-slate-200/70 dark:divide-white/10">
              {todayQueue.map((item) => (
                <div key={item.title} className="flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 size={16} className="shrink-0 text-sky-500 dark:text-sky-300" />
                      <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{item.title}</p>
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600 dark:bg-white/10 dark:text-slate-300">
                        {item.status}
                      </span>
                    </div>
                    <p className="mt-1 pl-6 text-sm text-slate-500 dark:text-slate-400">{item.meta}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActivePage(item.page)}
                    className="inline-flex items-center gap-2 self-start text-sm font-medium text-sky-600 transition hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300 md:self-center"
                  >
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
                      <button
                        type="button"
                        onClick={() => setActivePage(item.page)}
                        className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-sky-600 transition hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300"
                      >
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

function PlatformWorkspace({ styles }: WorkspaceDashboardProps) {
  return (
    <div className={`${styles.pageClass} space-y-6`}>
      <section className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">Platform command</p>
        <h3 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">平台总览</h3>
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
  const managementEntries = getOrganizationManagementEntries(canOpenAccounts)
    .filter((entry) => canOpenDashboardPage(currentUser, entry.page));

  return (
    <div className={`${styles.pageClass} space-y-6`}>
      <section className="rounded-[2rem] border border-sky-100 bg-[radial-gradient(circle_at_top_left,_rgba(34,199,232,0.18),_transparent_32%),linear-gradient(135deg,_rgba(255,255,255,0.98)_0%,_rgba(236,246,255,0.92)_52%,_rgba(223,241,255,0.96)_100%)] p-6 shadow-[0_24px_72px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.15),_transparent_30%),linear-gradient(135deg,_rgba(15,23,42,0.98)_0%,_rgba(17,24,39,0.95)_52%,_rgba(30,41,59,0.96)_100%)] dark:shadow-[0_28px_80px_rgba(2,6,23,0.36)] md:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">Operations focus</p>
        <div className="mt-4 space-y-3">
          <h3 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">机构运营概览</h3>
          <p className="max-w-3xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">
            已开放机构管理、运营观察和 AI 教学入口。
          </p>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-4">
        <div className={`${styles.cardClass} min-h-28 p-5`}>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">Overview</p>
          <p className="mt-3 text-lg font-semibold text-slate-900 dark:text-slate-100">机构运营概览</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">汇总组织级运营指标。</p>
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
            {canOpenAccounts ? '处理成员开通与组织归属。' : '查看咨询记录与跟进状态。'}
          </p>
        </div>
        <div className={`${styles.cardClass} min-h-28 p-5`}>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">Teaching</p>
          <p className="mt-3 text-lg font-semibold text-slate-900 dark:text-slate-100">课堂反馈</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">汇总课堂反馈和错题跟进入口。</p>
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
