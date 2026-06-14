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

export type DashboardPlatformPriorityItem = {
  title: string;
  detail: string;
  page: DashboardPage;
};

export type DashboardMemberData = {
  todayQueue: DashboardTaskItem[];
  recentOutputs: DashboardRecentItem[];
  weeklyStats: DashboardStat[];
  schedule: DashboardScheduleItem[];
};

export type DashboardOrganizationData = {
  pendingItems: DashboardTaskItem[];
  stats: DashboardStat[];
  classRows: OrganizationClassRow[];
};

export type DashboardPlatformData = {
  attentionItems: PlatformAttentionItem[];
  stats: DashboardStat[];
  organizationRows: PlatformOrganizationRow[];
  priorityItems: DashboardPlatformPriorityItem[];
};

export type DashboardApiResponse = {
  role: 'super_owner' | 'owner' | 'admin' | 'member';
  member?: DashboardMemberData;
  organization?: DashboardOrganizationData;
  platform?: DashboardPlatformData;
};
