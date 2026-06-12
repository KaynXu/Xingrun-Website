type WorkspaceRole = 'super_owner' | 'owner' | 'admin' | 'member';
type WorkspacePage =
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

type VisiblePageUser = {
  role: WorkspaceRole;
  visible_pages?: WorkspacePage[];
};

export const configurableWorkspacePages: Array<{ id: WorkspacePage; label: string }> = [
  { id: 'review-generation', label: '复习生成' },
  { id: 'class-feedback-generation', label: '课堂反馈' },
  { id: 'consultation', label: '咨询记录' },
  { id: 'calendar', label: '课程日历' },
  { id: 'smartWrongQuestions', label: '智能错题' },
  { id: 'classes', label: '学管中心' },
];

const configurableWorkspacePageIds = new Set(configurableWorkspacePages.map((item) => item.id));

export function hasOwnerAccess(role: WorkspaceRole): boolean {
  return role === 'super_owner' || role === 'owner';
}

export function hasStaffAccess(role: WorkspaceRole): boolean {
  return hasOwnerAccess(role) || role === 'admin';
}

export function canAccessSmartWrongQuestions(role: WorkspaceRole): boolean {
  return hasStaffAccess(role) || role === 'member';
}

export function getVisibleWorkspacePages(user: Pick<VisiblePageUser, 'visible_pages'>): WorkspacePage[] {
  if (!Array.isArray(user.visible_pages) || user.visible_pages.length === 0) {
    return configurableWorkspacePages.map((item) => item.id);
  }
  const visiblePageSet = new Set(user.visible_pages.filter((page) => configurableWorkspacePageIds.has(page)));
  return configurableWorkspacePages.map((item) => item.id).filter((page) => visiblePageSet.has(page));
}

export function canOpenWorkspacePage(user: VisiblePageUser, page: WorkspacePage): boolean {
  if (page === 'dashboard' || page === 'settings') {
    return true;
  }
  if (page === 'credit') {
    return hasOwnerAccess(user.role);
  }
  if (page === 'accounts') {
    return hasStaffAccess(user.role);
  }
  if (page === 'smartWrongQuestions' && !canAccessSmartWrongQuestions(user.role)) {
    return false;
  }
  return getVisibleWorkspacePages(user).includes(page);
}

export function getWorkspacePageFallback(user: VisiblePageUser, page: WorkspacePage): WorkspacePage {
  return canOpenWorkspacePage(user, page) ? page : 'dashboard';
}
