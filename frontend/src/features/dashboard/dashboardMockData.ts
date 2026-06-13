export type DashboardPage =
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

export type DashboardQuickAction = {
  page: DashboardPage;
  label: string;
  icon?: 'plus' | 'file' | 'calendar' | 'sparkles';
};

export type DashboardTaskItem = {
  page: DashboardPage;
  title: string;
  meta: string;
  status: string;
  action: string;
};

export type DashboardRecentItem = {
  page: DashboardPage;
  title: string;
  meta: string;
  status: string;
};

export type DashboardScheduleItem = {
  time: string;
  title: string;
  detail: string;
  page: DashboardPage;
  action: string;
};

export type DashboardStat = {
  label: string;
  value: string;
  note: string;
};

export type PlatformAttentionItem = {
  organization: string;
  issue: string;
  status: string;
  page: DashboardPage;
  action: string;
};

export type PlatformOrganizationRow = {
  organization: string;
  teachers: string;
  outputs: string;
  approvals: string;
  status: string;
  page: DashboardPage;
};

export type OrganizationClassRow = {
  name: string;
  schedule: string;
  teacher: string;
  status: string;
  page: DashboardPage;
};

export const memberDashboardData = {
  quickActions: [
    { page: 'review-generation', label: '新建复习文档', icon: 'plus' },
    { page: 'class-feedback-generation', label: '补课堂反馈', icon: 'file' },
    { page: 'calendar', label: '查看课程日历', icon: 'calendar' },
    { page: 'smartWrongQuestions', label: '继续错题跟进', icon: 'sparkles' },
  ] satisfies DashboardQuickAction[],
  todayQueue: [
    { page: 'review-generation', title: '高二数学提高班复习资料', meta: '录音和笔记已上传，待整理', status: '待生成', action: '进入' },
    { page: 'class-feedback-generation', title: '周三课堂反馈补录', meta: '还有 2 节课没整理', status: '待补录', action: '进入' },
    { page: 'smartWrongQuestions', title: '高一英语错题状态更新', meta: '5 条题目还没标记掌握情况', status: '待更新', action: '进入' },
  ] satisfies DashboardTaskItem[],
  recentOutputs: [
    { page: 'review-generation', title: '高一英语语法复习单', meta: '今天 14:20 · 已完成', status: '已完成' },
    { page: 'class-feedback-generation', title: '七年级数学课堂反馈', meta: '今天 11:40 · 草稿', status: '草稿' },
    { page: 'review-generation', title: '立体几何阶段复习', meta: '昨天 18:05 · 已完成', status: '已完成' },
  ] satisfies DashboardRecentItem[],
  weeklyStats: [
    { label: '复习资料', value: '6', note: '本周已生成' },
    { label: '课堂反馈', value: '2', note: '待补记录' },
    { label: '错题跟进', value: '5', note: '今天要处理' },
  ] satisfies DashboardStat[],
  schedule: [
    { time: '16:30', title: '高一英语衔接班', detail: '课前先看上次错题记录', page: 'smartWrongQuestions', action: '查看错题' },
    { time: '19:00', title: '高二数学提高班', detail: '下课后补复习资料', page: 'review-generation', action: '打开生成' },
  ] satisfies DashboardScheduleItem[],
};

export const platformDashboardData = {
  quickActions: [
    { page: 'accounts', label: '处理账号审批' },
    { page: 'classes', label: '查看机构班级' },
    { page: 'settings', label: '进入系统设置' },
  ] satisfies DashboardQuickAction[],
  attentionItems: [
    { organization: '星润 Starain', issue: '4 条账号审批还没处理。', status: '优先处理', page: 'accounts', action: '进入' },
    { organization: '青禾校区', issue: '今天还有 3 节课没补课堂反馈。', status: '待跟进', page: 'class-feedback-generation', action: '进入' },
    { organization: '城南教学点', issue: '近 3 天复习资料产出偏低。', status: '需要观察', page: 'review-generation', action: '进入' },
  ] satisfies PlatformAttentionItem[],
  stats: [
    { label: '今日活跃机构', value: '12', note: '较昨天 +2' },
    { label: '今日生成文档', value: '28', note: '复习资料 / 讲义 / 清单' },
    { label: '待处理审批', value: '7', note: '2 个机构有积压' },
    { label: '待补课堂反馈', value: '9', note: '优先看今天已下课班级' },
  ] satisfies DashboardStat[],
  organizationRows: [
    { organization: '星润 Starain', teachers: '8', outputs: '11', approvals: '4', status: '审批积压', page: 'accounts' },
    { organization: '青禾校区', teachers: '6', outputs: '7', approvals: '0', status: '反馈未补', page: 'class-feedback-generation' },
    { organization: '城南教学点', teachers: '4', outputs: '2', approvals: '1', status: '产出偏低', page: 'review-generation' },
    { organization: '北辰项目组', teachers: '5', outputs: '8', approvals: '0', status: '运行正常', page: 'classes' },
  ] satisfies PlatformOrganizationRow[],
};

export const organizationDashboardData = {
  quickActions: {
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
  },
  pendingItems: {
    withAccounts: [
      { page: 'class-feedback-generation', title: '今天还有 3 节课没补课堂反馈', meta: '优先处理今天已下课的班级。', status: '优先处理', action: '进入' },
      { page: 'classes', title: '2 个班级本周排课还没确认', meta: '周六衔接班和高二数学班待确认。', status: '待确认', action: '进入' },
      { page: 'accounts', title: '4 条账号审批待处理', meta: '今天新增老师还没完成开通。', status: '待审批', action: '进入' },
    ] satisfies DashboardTaskItem[],
    withoutAccounts: [
      { page: 'class-feedback-generation', title: '今天还有 3 节课没补课堂反馈', meta: '优先处理今天已下课的班级。', status: '优先处理', action: '进入' },
      { page: 'classes', title: '2 个班级本周排课还没确认', meta: '周六衔接班和高二数学班待确认。', status: '待确认', action: '进入' },
      { page: 'consultation', title: '5 条家长咨询还没跟进', meta: '今天新增咨询还没回访。', status: '待回访', action: '进入' },
    ] satisfies DashboardTaskItem[],
  },
  stats: {
    withAccounts: [
      { label: '今日上课班级', value: '9', note: '其中 6 节已下课' },
      { label: '课堂反馈完成', value: '6/9', note: '还差 3 节待补' },
      { label: '复习资料产出', value: '8', note: '较昨天正常' },
      { label: '待审批账号', value: '4', note: '2 位老师急用' },
    ] satisfies DashboardStat[],
    withoutAccounts: [
      { label: '今日上课班级', value: '9', note: '其中 6 节已下课' },
      { label: '课堂反馈完成', value: '6/9', note: '还差 3 节待补' },
      { label: '复习资料产出', value: '8', note: '较昨天正常' },
      { label: '待跟进咨询', value: '5', note: '2 条今日新增' },
    ] satisfies DashboardStat[],
  },
  classRows: [
    { name: '高二数学提高班', schedule: '19:00', teacher: '周老师', status: '待复习资料', page: 'review-generation' },
    { name: '七年级英语衔接班', schedule: '16:30', teacher: '王老师', status: '待课堂反馈', page: 'class-feedback-generation' },
    { name: '高一语文写作班', schedule: '18:00', teacher: '李老师', status: '运行正常', page: 'classes' },
  ] satisfies OrganizationClassRow[],
};
