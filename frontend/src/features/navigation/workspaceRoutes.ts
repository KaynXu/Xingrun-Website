import type { WorkspacePage } from '../../appTypes';

const workspacePagePathMap: Record<WorkspacePage, string> = {
  dashboard: '/workspace',
  'review-generation': '/workspace/review-generation',
  'class-feedback-generation': '/workspace/class-feedback-generation',
  consultation: '/workspace/consultation',
  calendar: '/workspace/calendar',
  smartWrongQuestions: '/workspace/smart-wrong-questions',
  'curriculum-knowledge': '/workspace/curriculum-knowledge',
  classes: '/workspace/classes',
  accounts: '/workspace/accounts',
  credit: '/workspace/credit',
  settings: '/workspace/settings',
};

const workspacePagePathAliases: Array<{ page: WorkspacePage; path: string }> = [
  { page: 'dashboard', path: '/workspace' },
  { page: 'dashboard', path: '/workspace/dashboard' },
  { page: 'review-generation', path: '/workspace/review-generation' },
  { page: 'class-feedback-generation', path: '/workspace/class-feedback-generation' },
  { page: 'consultation', path: '/workspace/consultation' },
  { page: 'calendar', path: '/workspace/calendar' },
  { page: 'smartWrongQuestions', path: '/workspace/smart-wrong-questions' },
  { page: 'curriculum-knowledge', path: '/workspace/curriculum-knowledge' },
  { page: 'classes', path: '/workspace/classes' },
  { page: 'accounts', path: '/workspace/accounts' },
  { page: 'credit', path: '/workspace/credit' },
  { page: 'settings', path: '/workspace/settings' },
];

export function normalizeWorkspacePathname(pathname: string): string {
  const trimmed = pathname.trim();
  if (!trimmed) {
    return '/';
  }
  const withLeadingSlash = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
  const normalized = withLeadingSlash.replace(/\/+$/, '');
  return normalized || '/';
}

export function getWorkspacePath(page: WorkspacePage): string {
  return workspacePagePathMap[page];
}

export function getWorkspacePageFromPathname(pathname: string): WorkspacePage | null {
  const normalizedPathname = normalizeWorkspacePathname(pathname);
  const matched = workspacePagePathAliases.find((item) => item.path === normalizedPathname);
  return matched?.page ?? null;
}

export function isWorkspacePathname(pathname: string): boolean {
  return getWorkspacePageFromPathname(pathname) !== null;
}
