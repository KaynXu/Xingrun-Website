import React, { useEffect, useMemo, useState } from 'react';
import { MoreVertical, Pencil, PlusCircle, RefreshCw, Save, Trash2 } from 'lucide-react';
import type { ClassBindingTarget, ClassItem, CurrentUser, UserItem } from '../../App';
import { formatClassDisplayName } from '../../domain/classNaming';
import {
  apiFetch,
  cn,
  workspaceCardClass,
  workspaceFieldClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
} from '../../workspaceShared';

type Role = 'super_owner' | 'owner' | 'admin' | 'member';
type Page =
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

interface RegistrationRequestItem {
  id: number;
  username: string;
  display_name: string;
  organization_name: string;
  status: string;
  created_at: string;
}

interface OrganizationRequestItem {
  id: number;
  organization_name: string;
  username: string;
  display_name: string;
  status: string;
  created_at: string;
}

interface OrganizationInviteInfo {
  organization_name: string;
  invite_code: string;
  invite_link: string;
  join_path?: string;
}

interface OrganizationSummaryItem {
  id: number;
  name: string;
  created_at: string;
  member_count: number;
  owner_count: number;
  class_count: number;
  lesson_count: number;
}

type MemberBindingSummaryStatus = 'healthy' | 'needs_review' | 'incomplete';

interface MemberBindingSummary {
  user_id: number;
  mini_teacher_bound: boolean;
  responsible_classes: Array<{
    id: number;
    name: string;
  }>;
  mapping_summary: {
    status: MemberBindingSummaryStatus;
    mapped_count: number;
    needs_review_count: number;
    unmapped_count: number;
    ambiguous_count: number;
  };
}

interface TeacherAliasEntry {
  wecom_userid: string;
  alias_names: string[];
  updated_at?: string | null;
}

interface TeacherAliasEditingState {
  wecom_userid: string;
  alias_names: string;
}

const configurableWorkspacePages: Array<{ id: Page; label: string }> = [
  { id: 'review-generation', label: '复习生成' },
  { id: 'class-feedback-generation', label: '课堂反馈' },
  { id: 'consultation', label: '咨询记录' },
  { id: 'calendar', label: '课程日历' },
  { id: 'smartWrongQuestions', label: '智能错题' },
  { id: 'classes', label: '学管中心' },
];
const configurableWorkspacePageIds = new Set(configurableWorkspacePages.map((item) => item.id));

function getRoleLabel(role: Role): string {
  if (role === 'super_owner') return '超级管理员';
  if (role === 'owner') return '机构负责人';
  if (role === 'admin') return '管理员';
  return '机构成员';
}

function canManageOwnerRole(role: Role): boolean {
  return role === 'super_owner';
}

function getVisibleWorkspacePages(user: Pick<CurrentUser, 'visible_pages'> | UserItem): Page[] {
  if (!user.visible_pages || user.visible_pages.length === 0) {
    return configurableWorkspacePages.map((item) => item.id);
  }
  const visiblePageSet = new Set(user.visible_pages.filter((page) => configurableWorkspacePageIds.has(page)));
  return configurableWorkspacePages.filter((item) => visiblePageSet.has(item.id)).map((item) => item.id);
}

function getCurrentClassDisplayName(item: ClassItem | null | undefined, showCohortYear = false): string {
  return formatClassDisplayName(item, { showCohortYear });
}

function getMemberBindingStatusLabel(status: MemberBindingSummaryStatus): string {
  if (status === 'healthy') return '正常';
  if (status === 'needs_review') return '待处理';
  return '未完成';
}

function getMemberBindingStatusTone(status: MemberBindingSummaryStatus): string {
  if (status === 'healthy') return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300';
  if (status === 'needs_review') return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300';
  return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300';
}

type ApprovalPageProps = {
  currentUser: CurrentUser;
  onOpenClassBinding: (target: ClassBindingTarget) => void;
};

export function ApprovalPage({ currentUser, onOpenClassBinding }: ApprovalPageProps) {
  const [items, setItems] = useState<RegistrationRequestItem[]>([]);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [organizations, setOrganizations] = useState<OrganizationSummaryItem[]>([]);
  const [bindingSummaryByUserId, setBindingSummaryByUserId] = useState<Record<number, MemberBindingSummary>>({});
  const [loading, setLoading] = useState(true);
  const [usersLoading, setUsersLoading] = useState(true);
  const [classesLoading, setClassesLoading] = useState(true);
  const [organizationsLoading, setOrganizationsLoading] = useState(currentUser.role === 'super_owner');
  const [bindingSummaryLoading, setBindingSummaryLoading] = useState(true);
  const [error, setError] = useState('');
  const [usersError, setUsersError] = useState('');
  const [classesError, setClassesError] = useState('');
  const [organizationsError, setOrganizationsError] = useState('');
  const [bindingSummaryError, setBindingSummaryError] = useState('');
  const [actingId, setActingId] = useState<number | null>(null);
  const [roleSavingUserId, setRoleSavingUserId] = useState<number | null>(null);
  const [visiblePageSavingUserId, setVisiblePageSavingUserId] = useState<number | null>(null);
  const [editingDisplayNameUserId, setEditingDisplayNameUserId] = useState<number | null>(null);
  const [pendingDisplayName, setPendingDisplayName] = useState('');
  const [displayNameSavingUserId, setDisplayNameSavingUserId] = useState<number | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<number | null>(null);
  const [confirmDeleteUserId, setConfirmDeleteUserId] = useState<number | null>(null);
  const [pendingRoleByUserId, setPendingRoleByUserId] = useState<Record<number, Role>>({});
  const [collapsedUserIds, setCollapsedUserIds] = useState<Set<number>>(new Set());
  const [organizationRequests, setOrganizationRequests] = useState<OrganizationRequestItem[]>([]);
  const [organizationRequestsLoading, setOrganizationRequestsLoading] = useState(currentUser.role === 'super_owner');
  const [organizationRequestsError, setOrganizationRequestsError] = useState('');
  const [organizationActingId, setOrganizationActingId] = useState<number | null>(null);
  const [organizationInvite, setOrganizationInvite] = useState<OrganizationInviteInfo | null>(null);
  const [organizationInviteLoading, setOrganizationInviteLoading] = useState(hasOwnerAccess(currentUser.role));
  const [organizationInviteError, setOrganizationInviteError] = useState('');
  const [organizationInviteResetting, setOrganizationInviteResetting] = useState(false);
  const [deletingOrgId, setDeletingOrgId] = useState<number | null>(null);
  const [confirmDeleteOrgId, setConfirmDeleteOrgId] = useState<number | null>(null);

  // Teacher alias mapping state
  const [teacherAliases, setTeacherAliases] = useState<TeacherAliasEntry[]>([]);
  const [teacherAliasLoading, setTeacherAliasLoading] = useState(true);
  const [teacherAliasError, setTeacherAliasError] = useState('');
  const [teacherAliasModalOpen, setTeacherAliasModalOpen] = useState(false);
  const [teacherAliasModalMode, setTeacherAliasModalMode] = useState<'create' | 'edit'>('create');
  const [teacherAliasEditingEntry, setTeacherAliasEditingEntry] = useState<TeacherAliasEntry | null>(null);
  const [taFormUserId, setTaFormUserId] = useState('');
  const [taFormDisplayName, setTaFormDisplayName] = useState('');
  const [taFormAliases, setTaFormAliases] = useState('');
  const [taLinkedUsername, setTaLinkedUsername] = useState('');
  const [taSubmitting, setTaSubmitting] = useState(false);
  const [taDeletingId, setTaDeletingId] = useState<string | null>(null);
  const teacherAliasMemberOptions = users.filter((user) => user.username && user.role !== 'super_owner');
  const organizationRequestRefreshLocked = organizationRequestsLoading || organizationActingId !== null;
  const organizationInviteRefreshLocked = organizationInviteLoading || organizationInviteResetting;
  const organizationListRefreshLocked = organizationsLoading || deletingOrgId !== null;
  const approvalRefreshLocked = loading || actingId !== null;
  const memberRefreshLocked = usersLoading || classesLoading || bindingSummaryLoading || roleSavingUserId !== null || visiblePageSavingUserId !== null || displayNameSavingUserId !== null || deletingUserId !== null;
  const teacherAliasActionLocked = taSubmitting || taDeletingId !== null;

  const loadItems = useCallback(async () => {
    if (!hasOwnerAccess(currentUser.role)) {
      setItems([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError('');
    try {
      const data = await apiFetch<{ items: RegistrationRequestItem[] }>('/api/admin/registration-requests');
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : '审批列表加载失败');
    } finally {
      setLoading(false);
    }
  }, [currentUser.role]);

  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    setUsersError('');
    try {
      const data = await apiFetch<UserItem[]>('/api/admin/users');
      setUsers(data);
      setCollapsedUserIds(new Set(data.map((item) => item.id)));
    } catch (err) {
      setUsersError(err instanceof Error ? err.message : '成员权限加载失败');
    } finally {
      setUsersLoading(false);
    }
  }, []);

  const loadClasses = useCallback(async () => {
    setClassesLoading(true);
    setClassesError('');
    try {
      const data = await apiFetch<ClassItem[]>('/api/classes');
      setClasses(data);
    } catch (err) {
      setClasses([]);
      setClassesError(err instanceof Error ? err.message : '班级列表加载失败');
    } finally {
      setClassesLoading(false);
    }
  }, []);

  const loadOrganizations = useCallback(async () => {
    if (currentUser.role !== 'super_owner') {
      setOrganizations([]);
      setOrganizationsLoading(false);
      return;
    }

    setOrganizationsLoading(true);
    setOrganizationsError('');
    try {
      const data = await apiFetch<{ items: OrganizationSummaryItem[] }>('/api/admin/organizations');
      setOrganizations(data.items);
    } catch (err) {
      setOrganizations([]);
      setOrganizationsError(err instanceof Error ? err.message : '已注册机构加载失败');
    } finally {
      setOrganizationsLoading(false);
    }
  }, [currentUser.role]);

  const loadBindingSummaries = useCallback(async () => {
    setBindingSummaryLoading(true);
    setBindingSummaryError('');
    try {
      const data = await apiFetch<{ items: MemberBindingSummary[] }>('/api/admin/member-binding-summary');
      setBindingSummaryByUserId(
        data.items.reduce<Record<number, MemberBindingSummary>>((accumulator, item) => {
          accumulator[item.user_id] = item;
          return accumulator;
        }, {}),
      );
    } catch (err) {
      setBindingSummaryByUserId({});
      setBindingSummaryError(err instanceof Error ? err.message : '教学绑定摘要加载失败');
    } finally {
      setBindingSummaryLoading(false);
    }
  }, []);

  const refreshApprovalMembers = useCallback(async () => {
    await Promise.all([
      loadUsers(),
      loadClasses(),
      loadBindingSummaries(),
    ]);
  }, [loadBindingSummaries, loadClasses, loadUsers]);

  const loadOrganizationRequests = useCallback(async () => {
    if (currentUser.role !== 'super_owner') {
      setOrganizationRequests([]);
      setOrganizationRequestsLoading(false);
      return;
    }

    setOrganizationRequestsLoading(true);
    setOrganizationRequestsError('');
    try {
      const data = await apiFetch<{ items: OrganizationRequestItem[] }>('/api/admin/organization-requests');
      setOrganizationRequests(data.items);
    } catch (err) {
      setOrganizationRequestsError(err instanceof Error ? err.message : '机构开通审批加载失败');
    } finally {
      setOrganizationRequestsLoading(false);
    }
  }, [currentUser.role]);

  const loadOrganizationInvite = useCallback(async () => {
    if (!hasOwnerAccess(currentUser.role)) {
      setOrganizationInvite(null);
      setOrganizationInviteLoading(false);
      return;
    }

    setOrganizationInviteLoading(true);
    setOrganizationInviteError('');
    try {
      const data = await apiFetch<OrganizationInviteInfo>('/api/organization/invite');
      setOrganizationInvite(data);
    } catch (err) {
      setOrganizationInvite(null);
      setOrganizationInviteError(err instanceof Error ? err.message : '机构邀请设置加载失败');
    } finally {
      setOrganizationInviteLoading(false);
    }
  }, [currentUser.role]);

  const loadTeacherAliases = useCallback(async () => {
    if (!hasOwnerAccess(currentUser.role)) {
      setTeacherAliases([]);
      setTeacherAliasLoading(false);
      return;
    }

    setTeacherAliasLoading(true);
    setTeacherAliasError('');
    try {
      const data = await apiFetch<TeacherAliasEntry[]>('/api/teacher-aliases');
      setTeacherAliases(data);
    } catch (err) {
      setTeacherAliasError(err instanceof Error ? err.message : '讲师映射加载失败');
    } finally {
      setTeacherAliasLoading(false);
    }
  }, [currentUser.role]);

  const openTeacherAliasCreate = () => {
    setTeacherAliasEditingEntry(null);
    setTaFormUserId('');
    setTaFormDisplayName('');
    setTaFormAliases('');
    setTaLinkedUsername('');
    setTeacherAliasModalMode('create');
    setTeacherAliasModalOpen(true);
  };

  const openTeacherAliasEdit = (entry: TeacherAliasEntry) => {
    setTeacherAliasEditingEntry(entry);
    setTaFormUserId(entry.wecom_userid);
    setTaFormDisplayName(entry.display_name);
    setTaFormAliases(entry.aliases.slice(1).join(', '));
    setTaLinkedUsername(entry.linked_username || '');
    setTeacherAliasModalMode('edit');
    setTeacherAliasModalOpen(true);
  };

  const handleTeacherAliasSubmit = async () => {
    setTaSubmitting(true);
    setTeacherAliasError('');
    try {
      const aliases = taFormAliases.split(/[,，]/).map(s => s.trim()).filter(Boolean);
      if (teacherAliasModalMode === 'create') {
        await apiFetch('/api/teacher-aliases', {
          method: 'POST',
          body: JSON.stringify({
            wecom_userid: taFormUserId.trim(),
            display_name: taFormDisplayName.trim(),
            linked_username: taLinkedUsername.trim(),
            aliases,
          }),
        });
      } else if (teacherAliasEditingEntry) {
        await apiFetch(`/api/teacher-aliases/${encodeURIComponent(teacherAliasEditingEntry.wecom_userid)}`, {
          method: 'PUT',
          body: JSON.stringify({
            display_name: taFormDisplayName.trim(),
            linked_username: taLinkedUsername.trim(),
            aliases,
          }),
        });
      }
      setTeacherAliasModalOpen(false);
      await loadTeacherAliases();
    } catch (err) {
      setTeacherAliasError(err instanceof Error ? err.message : '操作失败');
    } finally {
      setTaSubmitting(false);
    }
  };

  const handleTeacherAliasDelete = async (wecom_userid: string) => {
    if (!window.confirm(`确认删除 ${wecom_userid} 的映射？`)) return;
    setTaDeletingId(wecom_userid);
    try {
      await apiFetch(`/api/teacher-aliases/${encodeURIComponent(wecom_userid)}`, { method: 'DELETE' });
      await loadTeacherAliases();
    } catch (err) {
      setTeacherAliasError(err instanceof Error ? err.message : '删除失败');
    } finally {
      setTaDeletingId(null);
    }
  };

  useEffect(() => {
    loadItems().catch(() => undefined);
    loadUsers().catch(() => undefined);
    loadClasses().catch(() => undefined);
    loadOrganizations().catch(() => undefined);
    loadBindingSummaries().catch(() => undefined);
    loadOrganizationRequests().catch(() => undefined);
    loadOrganizationInvite().catch(() => undefined);
    loadTeacherAliases().catch(() => undefined);
  }, [loadItems, loadUsers, loadClasses, loadOrganizations, loadBindingSummaries, loadOrganizationInvite, loadOrganizationRequests, loadTeacherAliases]);

  useEffect(() => {
    const handleWindowFocus = () => {
      refreshApprovalMembers().catch(() => undefined);
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        refreshApprovalMembers().catch(() => undefined);
      }
    };

    window.addEventListener('focus', handleWindowFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      window.removeEventListener('focus', handleWindowFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [refreshApprovalMembers]);

  const handleDecision = async (requestId: number, action: 'approve' | 'reject') => {
    setActingId(requestId);
    setError('');
    try {
      await apiFetch(`/api/admin/registration-requests/${requestId}/${action}`, {
        method: 'POST',
      });
      setItems((current) => current.filter((item) => item.id !== requestId));
      refreshApprovalMembers().catch(() => undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : '审批操作失败');
    } finally {
      setActingId(null);
    }
  };

  const handleOrganizationRequestDecision = async (requestId: number, action: 'approve' | 'reject') => {
    setOrganizationActingId(requestId);
    setOrganizationRequestsError('');
    try {
      await apiFetch(`/api/admin/organization-requests/${requestId}/${action}`, {
        method: 'POST',
      });
      setOrganizationRequests((current) => current.filter((item) => item.id !== requestId));
      refreshApprovalMembers().catch(() => undefined);
      loadOrganizations().catch(() => undefined);
    } catch (err) {
      setOrganizationRequestsError(err instanceof Error ? err.message : '机构开通审批处理失败');
    } finally {
      setOrganizationActingId(null);
    }
  };

  const handleDeleteOrganization = async (orgId: number) => {
    setDeletingOrgId(orgId);
    setOrganizationsError('');
    try {
      await apiFetch(`/api/admin/organizations/${orgId}`, { method: 'DELETE' });
      setOrganizations((current) => current.filter((o) => o.id !== orgId));
      setConfirmDeleteOrgId(null);
    } catch (err) {
      setOrganizationsError(err instanceof Error ? err.message : '删除机构失败');
    } finally {
      setDeletingOrgId(null);
    }
  };

  const handleResetOrganizationInvite = async () => {    setOrganizationInviteResetting(true);
    setOrganizationInviteError('');
    try {
      const data = await apiFetch<OrganizationInviteInfo>('/api/organization/invite/reset', {
        method: 'POST',
      });
      setOrganizationInvite(data);
    } catch (err) {
      setOrganizationInviteError(err instanceof Error ? err.message : '机构邀请重置失败');
    } finally {
      setOrganizationInviteResetting(false);
    }
  };

  const handleRoleUpdate = async (userId: number, currentRole: Role, nextRole: Role) => {
    if (currentRole === nextRole) {
      return;
    }

    setRoleSavingUserId(userId);
    setUsersError('');
    setUsers((current) => current.map((user) => (user.id === userId ? { ...user, role: nextRole } : user)));

    try {
      await apiFetch(`/api/admin/users/${userId}/role`, {
        method: 'PUT',
        body: JSON.stringify({ role: nextRole }),
      });
    } catch (err) {
      setUsers((current) => current.map((user) => (user.id === userId ? { ...user, role: currentRole } : user)));
      setUsersError(err instanceof Error ? err.message : '成员权限更新失败');
    } finally {
      setRoleSavingUserId(null);
    }
  };

  const handleToggleVisiblePage = async (targetUser: UserItem, page: Page) => {
    if (visiblePageSavingUserId !== null || targetUser.role === 'super_owner') {
      return;
    }

    const currentVisiblePages = getVisibleWorkspacePages(targetUser);
    const nextVisiblePageSet = new Set(currentVisiblePages);
    if (nextVisiblePageSet.has(page)) {
      nextVisiblePageSet.delete(page);
    } else {
      nextVisiblePageSet.add(page);
    }
    const nextVisiblePages = configurableWorkspacePages
      .map((item) => item.id)
      .filter((item) => nextVisiblePageSet.has(item));

    setVisiblePageSavingUserId(targetUser.id);
    setUsersError('');
    setUsers((current) => current.map((user) => (user.id === targetUser.id ? { ...user, visible_pages: nextVisiblePages } : user)));

    try {
      const response = await apiFetch<{ ok: boolean; user: UserItem }>(`/api/admin/users/${targetUser.id}/visible-pages`, {
        method: 'PUT',
        body: JSON.stringify({ visible_pages: nextVisiblePages }),
      });
      setUsers((current) => current.map((user) => (user.id === targetUser.id ? { ...user, ...response.user } : user)));
    } catch (err) {
      setUsers((current) => current.map((user) => (user.id === targetUser.id ? { ...user, visible_pages: currentVisiblePages } : user)));
      setUsersError(err instanceof Error ? err.message : '可见页面更新失败');
    } finally {
      setVisiblePageSavingUserId(null);
    }
  };

  const getAssignableRoles = (targetUser: UserItem): Role[] => {
    if (targetUser.id === currentUser.id) {
      return [];
    }
    if (currentUser.role === 'super_owner') {
      if (targetUser.role === 'super_owner') {
        return [];
      }
      return ['super_owner', 'owner', 'admin', 'member'];
    }
    if (currentUser.role === 'owner') {
      if (targetUser.role === 'admin' || targetUser.role === 'member') {
        return ['admin', 'member'];
      }
      return [];
    }
    return [];
  };

  const handleStartDisplayNameEdit = (userId: number, currentName: string) => {
    setEditingDisplayNameUserId(userId);
    setPendingDisplayName(currentName);
    setUsersError('');
  };

  const handleCancelDisplayNameEdit = () => {
    setEditingDisplayNameUserId(null);
    setPendingDisplayName('');
  };

  const handleSaveDisplayName = async (userId: number) => {
    const nextDisplayName = pendingDisplayName.trim();
    if (!nextDisplayName) {
      setUsersError('姓名不能为空');
      return;
    }

    const currentName = users.find((user) => user.id === userId)?.name ?? '';
    setDisplayNameSavingUserId(userId);
    setUsersError('');
    setUsers((current) => current.map((user) => (user.id === userId ? { ...user, name: nextDisplayName } : user)));

    try {
      await apiFetch(`/api/admin/users/${userId}/profile`, {
        method: 'PUT',
        body: JSON.stringify({ display_name: nextDisplayName }),
      });
      setEditingDisplayNameUserId(null);
      setPendingDisplayName('');
    } catch (err) {
      setUsers((current) => current.map((user) => (user.id === userId ? { ...user, name: currentName } : user)));
      setUsersError(err instanceof Error ? err.message : '成员姓名更新失败');
    } finally {
      setDisplayNameSavingUserId(null);
    }
  };

  const handleDeleteUser = async (userId: number) => {
    setDeletingUserId(userId);
    setUsersError('');
    try {
      await apiFetch(`/api/admin/users/${userId}`, { method: 'DELETE' });
      setUsers((current) => current.filter((user) => user.id !== userId));
      setBindingSummaryByUserId((current) => {
        const next = { ...current };
        delete next[userId];
        return next;
      });
      if (editingDisplayNameUserId === userId) {
        setEditingDisplayNameUserId(null);
        setPendingDisplayName('');
      }
      setConfirmDeleteUserId(null);
    } catch (err) {
      setUsersError(err instanceof Error ? err.message : '成员删除失败');
    } finally {
      setDeletingUserId(null);
    }
  };

  return (
    <div className={`${workspacePageClass} space-y-8`}>
      {currentUser.role === 'super_owner' && (
        <section className={`${workspaceCardClass} p-6`}>
          <div className="flex flex-col gap-4 border-b border-sky-100/80 pb-5 sm:flex-row sm:items-start sm:justify-between dark:border-white/10">
            <div>
              <h4 className="text-xl font-semibold text-slate-900 dark:text-white">机构开通审批</h4>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                审核新机构的开通申请。通过后，申请人会自动成为该机构的首位管理员，并生成当前唯一有效的邀请码与邀请链接。
              </p>
            </div>
            <button
              onClick={() => loadOrganizationRequests().catch(() => undefined)}
              disabled={organizationRequestRefreshLocked}
              className={workspaceSecondaryButtonClass}
            >
              刷新机构申请
            </button>
          </div>

          {organizationRequestsError && (
            <div className="mt-5 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {organizationRequestsError}
            </div>
          )}

          {organizationRequestsLoading ? (
            <div className="py-10 text-center text-slate-500 dark:text-slate-400">正在加载机构开通申请...</div>
          ) : organizationRequests.length === 0 ? (
            <div className="mt-5 rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
              当前没有待处理的机构开通申请。
            </div>
          ) : (
            <div className="mt-5 space-y-4">
              {organizationRequests.map((item) => {
                const busy = organizationActingId === item.id;
                return (
                  <div key={item.id} className={`${workspaceSoftCardClass} p-5`}>
                    <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-lg font-semibold text-slate-900 dark:text-white">{item.organization_name}</span>
                          <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">
                            待审批
                          </span>
                        </div>
                        <div className="grid grid-cols-1 gap-3 text-sm text-slate-500 md:grid-cols-3 dark:text-slate-400">
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">首位管理员账号</p>
                            <p className="mt-1 text-slate-700 dark:text-slate-200">{item.username}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">负责人姓名</p>
                            <p className="mt-1 text-slate-700 dark:text-slate-200">{item.display_name}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">申请时间</p>
                            <p className="mt-1 text-slate-700 dark:text-slate-200">{item.created_at}</p>
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-3">
                        <button
                          onClick={() => handleOrganizationRequestDecision(item.id, 'reject')}
                          disabled={busy}
                          className={workspaceSecondaryButtonClass}
                        >
                          驳回
                        </button>
                        <button
                          onClick={() => handleOrganizationRequestDecision(item.id, 'approve')}
                          disabled={busy}
                          className={workspacePrimaryButtonClass}
                        >
                          {busy ? '处理中...' : '通过并开通机构'}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {hasOwnerAccess(currentUser.role) && (
        <section className={`${workspaceCardClass} p-6`}>
          <div className="flex flex-col gap-4 border-b border-sky-100/80 pb-5 sm:flex-row sm:items-start sm:justify-between dark:border-white/10">
            <div>
              <h4 className="text-xl font-semibold text-slate-900 dark:text-white">机构邀请设置</h4>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                当前机构仅保留一个有效邀请码。重置后，旧邀请码和旧邀请链接会立刻失效。
              </p>
            </div>
            <button
              onClick={() => loadOrganizationInvite().catch(() => undefined)}
              disabled={organizationInviteRefreshLocked}
              className={workspaceSecondaryButtonClass}
            >
              刷新邀请信息
            </button>
          </div>

          {organizationInviteError && (
            <div className="mt-5 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {organizationInviteError}
            </div>
          )}

          {organizationInviteLoading ? (
            <div className="py-10 text-center text-slate-500 dark:text-slate-400">正在加载邀请码...</div>
          ) : organizationInvite ? (
            <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
              <div className={`${workspaceSoftCardClass} grid gap-4 p-5 md:grid-cols-3`}>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">机构</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">{organizationInvite.organization_name}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">当前邀请码</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">{organizationInvite.invite_code}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">邀请链接</p>
                  <p className="mt-1 break-all text-sm text-slate-700 dark:text-slate-200">{organizationInvite.invite_link}</p>
                </div>
              </div>
              <button
                onClick={() => void handleResetOrganizationInvite()}
                disabled={organizationInviteRefreshLocked}
                className={workspacePrimaryButtonClass}
              >
                {organizationInviteResetting ? '重置中...' : '重置邀请码'}
              </button>
            </div>
          ) : (
            <div className="mt-5 rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
              当前没有可用的邀请码信息。
            </div>
          )}
        </section>
      )}

      {currentUser.role === 'super_owner' && (
        <section className={`${workspaceCardClass} p-6`}>
          <div className="flex flex-col gap-4 border-b border-sky-100/80 pb-5 sm:flex-row sm:items-start sm:justify-between dark:border-white/10">
            <div>
              <h4 className="text-xl font-semibold text-slate-900 dark:text-white">已注册机构</h4>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                查看已经开通的机构规模，快速确认负责人、成员和班级是否已正常落库。
              </p>
            </div>
            <button
              onClick={() => loadOrganizations().catch(() => undefined)}
              disabled={organizationListRefreshLocked}
              className={workspaceSecondaryButtonClass}
            >
              刷新机构列表
            </button>
          </div>

          {organizationsError && (
            <div className="mt-5 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {organizationsError}
            </div>
          )}

          {organizationsLoading ? (
            <div className="py-10 text-center text-slate-500 dark:text-slate-400">正在加载已注册机构...</div>
          ) : organizations.length === 0 ? (
            <div className="mt-5 rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
              当前还没有已开通机构。
            </div>
          ) : (
            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {organizations.map((organization) => (
                <div key={organization.id} className={`${workspaceSoftCardClass} p-5`}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h5 className="text-lg font-semibold text-slate-900 dark:text-white">{organization.name}</h5>
                      <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-400">开通时间</p>
                      <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{organization.created_at}</p>
                    </div>
                    <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">
                      已开通
                    </span>
                  </div>
                  <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-2xl border border-sky-100 bg-white/70 p-3 dark:border-white/10 dark:bg-slate-950/70">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">成员</p>
                      <p className="mt-2 text-xl font-semibold text-slate-900 dark:text-white">{organization.member_count}</p>
                    </div>
                    <div className="rounded-2xl border border-sky-100 bg-white/70 p-3 dark:border-white/10 dark:bg-slate-950/70">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">负责人</p>
                      <p className="mt-2 text-xl font-semibold text-slate-900 dark:text-white">{organization.owner_count}</p>
                    </div>
                    <div className="rounded-2xl border border-sky-100 bg-white/70 p-3 dark:border-white/10 dark:bg-slate-950/70">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">班级</p>
                      <p className="mt-2 text-xl font-semibold text-slate-900 dark:text-white">{organization.class_count}</p>
                    </div>
                    <div className="rounded-2xl border border-sky-100 bg-white/70 p-3 dark:border-white/10 dark:bg-slate-950/70">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">课程记录</p>
                      <p className="mt-2 text-xl font-semibold text-slate-900 dark:text-white">{organization.lesson_count}</p>
                    </div>
                  </div>
                  <div className="mt-4 border-t border-rose-100/60 pt-4 dark:border-rose-500/10">
                    {confirmDeleteOrgId === organization.id ? (
                      <div className="flex flex-col gap-2">
                        <p className="text-xs text-rose-600 dark:text-rose-400">确认删除「{organization.name}」？此操作将清空该机构下所有账号和数据，不可恢复。</p>
                        <div className="flex gap-2">
                          <button
                            onClick={() => void handleDeleteOrganization(organization.id)}
                            disabled={deletingOrgId === organization.id}
                            className="flex-1 rounded-xl border border-rose-300 bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-700 transition hover:bg-rose-100 disabled:opacity-50 dark:border-rose-500/30 dark:bg-rose-900/20 dark:text-rose-300"
                          >
                            {deletingOrgId === organization.id ? '删除中...' : '确认删除'}
                          </button>
                          <button
                            onClick={() => setConfirmDeleteOrgId(null)}
                            disabled={deletingOrgId === organization.id}
                            className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-50 dark:border-white/10 dark:bg-slate-800 dark:text-slate-300"
                          >
                            取消
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmDeleteOrgId(organization.id)}
                        className="w-full rounded-xl border border-rose-200 bg-rose-50/60 px-3 py-1.5 text-xs font-medium text-rose-600 transition hover:bg-rose-100 dark:border-rose-500/20 dark:bg-rose-900/10 dark:text-rose-400 dark:hover:bg-rose-900/30"
                      >
                        删除机构
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {hasOwnerAccess(currentUser.role) && (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,320px)_minmax(0,1fr)] gap-6">
          <section className={`${workspaceCardClass} space-y-5 p-6`}>
            <div>
              <p className="text-sm uppercase tracking-[0.25em] text-sky-600">账号审批与权限</p>
              <h3 className="mt-3 text-2xl font-bold text-slate-900 dark:text-white">账号审批</h3>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">超级管理员和机构负责人都可以审核注册申请，并为用户开通后台访问权限。</p>
            </div>
            <div className={`${workspaceSoftCardClass} p-5`}>
              <p className="text-xs uppercase tracking-[0.25em] text-sky-600">当前账号</p>
              <p className="mt-3 text-xl font-semibold text-slate-900 dark:text-white">{currentUser.display_name}</p>
              <div className="mt-4 space-y-2 text-sm">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-slate-500 dark:text-slate-400">账号</span>
                  <span className="text-slate-700 dark:text-slate-200">{currentUser.username}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-slate-500 dark:text-slate-400">权限</span>
                  <span className="text-slate-700 dark:text-slate-200">{getRoleLabel(currentUser.role)}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-slate-500 dark:text-slate-400">机构</span>
                  <span className="text-slate-700 dark:text-slate-200">{currentUser.organization_name}</span>
                </div>
              </div>
            </div>
            <div className={`${workspaceSoftCardClass} p-5`}>
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500 dark:text-slate-400">Queue</p>
              <p className="mt-3 text-4xl font-bold text-slate-900 dark:text-white">{items.length}</p>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">当前待审核注册申请</p>
            </div>
          </section>

          <section className={`${workspaceCardClass} p-6`}>
            <div className="flex items-center justify-between gap-4 mb-6">
              <div>
                <h4 className="text-xl font-semibold text-slate-900 dark:text-white">待审批申请</h4>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">新账号统一归属机构 {currentUser.organization_name}，通过后即可进入后台。</p>
              </div>
              <button
                onClick={() => loadItems().catch(() => undefined)}
                disabled={approvalRefreshLocked}
                className={workspaceSecondaryButtonClass}
              >
                刷新列表
              </button>
            </div>

            {error && (
              <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                <AlertCircle size={16} />
                {error}
              </div>
            )}

            {loading ? (
              <div className="p-8 text-center text-slate-500 dark:text-slate-400">正在读取审批队列...</div>
            ) : items.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                暂无待审批申请，新的注册请求会出现在这里。
              </div>
            ) : (
              <div className="space-y-4">
                {items.map((item) => {
                  const busy = actingId === item.id;
                  return (
                    <div key={item.id} className={`${workspaceSoftCardClass} p-5`}>
                      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-lg font-semibold text-slate-900 dark:text-white">{item.display_name}</span>
                            <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">
                              待审批
                            </span>
                          </div>
                          <div className="grid grid-cols-1 gap-3 text-sm text-slate-500 md:grid-cols-3 dark:text-slate-400">
                            <div>
                              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">账号</p>
                              <p className="mt-1 text-slate-700 dark:text-slate-200">{item.username}</p>
                            </div>
                            <div>
                              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">机构</p>
                              <p className="mt-1 text-slate-700 dark:text-slate-200">{item.organization_name}</p>
                            </div>
                            <div>
                              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">申请时间</p>
                              <p className="mt-1 text-slate-700 dark:text-slate-200">{item.created_at}</p>
                            </div>
                          </div>
                        </div>
                        <div className="flex gap-3">
                          <button
                            onClick={() => handleDecision(item.id, 'reject')}
                            disabled={busy}
                            className={workspaceSecondaryButtonClass}
                          >
                            拒绝
                          </button>
                          <button
                            onClick={() => handleDecision(item.id, 'approve')}
                            disabled={busy}
                            className={workspacePrimaryButtonClass}
                          >
                            {busy ? '处理中...' : '通过并开通'}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      )}

      {hasStaffAccess(currentUser.role) && (
        <section className={`${workspaceCardClass} p-6`}>
          <div className="flex flex-col gap-3 border-b border-sky-100/80 pb-5 sm:flex-row sm:items-start sm:justify-between dark:border-white/10">
            <div>
              <h4 className="text-xl font-semibold text-slate-900 dark:text-white">成员权限</h4>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                超级管理员可以设置或撤销机构负责人；机构负责人只可切换管理员与普通成员权限；管理员可调整成员可见页面。
              </p>
            </div>
            <button
              onClick={() => Promise.all([loadUsers(), loadBindingSummaries()]).catch(() => undefined)}
              disabled={memberRefreshLocked}
              className={workspaceSecondaryButtonClass}
            >
              刷新成员
            </button>
          </div>

          {usersError && (
            <div className="mt-5 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle size={16} />
              {usersError}
            </div>
          )}
          {classesError && (
            <div className="mt-5 flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-300">
              <AlertCircle size={16} />
              {classesError}，负责班级名称将暂时使用原始名称。
            </div>
          )}

          {usersLoading ? (
            <div className="py-10 text-center text-slate-500 dark:text-slate-400">正在加载成员权限...</div>
          ) : users.length === 0 ? (
            <div className="mt-5 rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
              当前暂无可管理成员。
            </div>
          ) : (
            <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {users.map((user) => {
                const busy = roleSavingUserId === user.id;
                const displayNameBusy = displayNameSavingUserId === user.id;
                const visiblePageSaving = visiblePageSavingUserId === user.id;
                const editingName = editingDisplayNameUserId === user.id;
                const deleting = deletingUserId === user.id;
                const bindingSummary = bindingSummaryByUserId[user.id];
                const visiblePages = getVisibleWorkspacePages(user);
                const responsibleClasses = bindingSummary?.responsible_classes ?? [];
                const bindingStatus = bindingSummary?.mapping_summary.status ?? 'incomplete';
                const visibleClassNames = responsibleClasses.slice(0, 3).map((item) =>
                  getCurrentClassDisplayNameById(classes, item.id, item.name),
                );
                const hiddenClassCount = Math.max(responsibleClasses.length - visibleClassNames.length, 0);
                const unresolvedCount = (bindingSummary?.mapping_summary.needs_review_count ?? 0)
                  + (bindingSummary?.mapping_summary.unmapped_count ?? 0)
                  + (bindingSummary?.mapping_summary.ambiguous_count ?? 0);
                const assignableRoles = getAssignableRoles(user);
                const roleFixed = assignableRoles.length === 0;
                const canDeleteUser = currentUser.role !== 'admin'
                  && user.role !== 'super_owner'
                  && user.id !== currentUser.id
                  && (canManageOwnerRole(currentUser.role) || user.role !== 'owner');
                const canEditVisiblePages = user.role !== 'super_owner'
                  && user.id !== currentUser.id
                  && (currentUser.role === 'super_owner'
                    || (currentUser.role === 'owner' && (user.role === 'admin' || user.role === 'member'))
                    || (currentUser.role === 'admin' && user.role === 'member'));
                const isCollapsed = collapsedUserIds.has(user.id);
                const toggleCollapse = () => setCollapsedUserIds((prev) => {
                  const next = new Set(prev);
                  if (next.has(user.id)) next.delete(user.id); else next.add(user.id);
                  return next;
                });
                return (
                  <div key={user.id} className={`${workspaceSoftCardClass} overflow-hidden`}>
                    <button
                      type="button"
                      onClick={toggleCollapse}
                      className="flex w-full items-center justify-between gap-3 p-4 text-left"
                    >
                      <div className="flex min-w-0 flex-col gap-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="truncate text-base font-semibold text-slate-900 dark:text-white">{user.name}</span>
                          <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${getRoleBadgeClass(user.role)}`}>
                            {getRoleLabel(user.role)}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">{user.org}</p>
                        {currentUser.role === 'super_owner' && (
                          <p className="text-xs text-slate-400 dark:text-slate-500">
                            <span className="font-mono">{user.username}</span>
                            {user.last_login
                              ? <span className="ml-2 text-slate-400">上次登录 {user.last_login}</span>
                              : <span className="ml-2 text-slate-300 dark:text-slate-600">未登录过</span>}
                          </p>
                        )}
                      </div>
                      <ChevronDown
                        size={16}
                        className={`shrink-0 text-slate-400 transition-transform duration-200 ${isCollapsed ? '' : 'rotate-180'}`}
                      />
                    </button>
                    {!isCollapsed && (
                      <div className="border-t border-sky-100/80 p-4 dark:border-white/10">
                        <div className="space-y-3">
                          {editingName ? (
                            <div className="flex flex-wrap items-center gap-2">
                              <input
                                value={pendingDisplayName}
                                onChange={(event) => setPendingDisplayName(event.target.value)}
                                className="min-w-[180px] rounded-xl border border-sky-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-950/70 dark:text-white dark:focus:border-sky-400 dark:focus:ring-sky-500/20"
                                placeholder="输入成员姓名"
                              />
                              <button
                                type="button"
                                onClick={() => void handleSaveDisplayName(user.id)}
                                disabled={displayNameBusy}
                                className={workspacePrimaryButtonClass}
                              >
                                {displayNameBusy ? '保存中...' : '保存姓名'}
                              </button>
                              <button
                                type="button"
                                onClick={handleCancelDisplayNameEdit}
                                disabled={displayNameBusy}
                                className={workspaceSecondaryButtonClass}
                              >
                                取消
                              </button>
                            </div>
                          ) : null}
                          <div className="rounded-2xl border border-sky-100 bg-white/80 p-3 dark:border-white/10 dark:bg-slate-950/70">
                            <div className="flex items-center justify-between gap-3">
                              <h5 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">教学绑定</h5>
                              <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${getMemberBindingStatusBadgeClass(bindingStatus)}`}>
                                {getMemberBindingStatusLabel(bindingStatus)}
                              </span>
                            </div>
                            <div className="mt-3 space-y-2">
                              <div className="flex items-center justify-between text-xs">
                                <span className="text-slate-400">小程序老师</span>
                                <span className="text-slate-700 dark:text-slate-200">
                                  {bindingSummaryLoading && !bindingSummary ? '加载中...' : bindingSummary?.mini_teacher_bound ? '已绑定' : '未绑定'}
                                </span>
                              </div>
                              <div className="flex items-center justify-between text-xs">
                                <span className="text-slate-400">负责班级</span>
                                <span className="text-slate-700 dark:text-slate-200">{responsibleClasses.length} 个班级</span>
                              </div>
                              {user.role !== 'super_owner' && canOpenWorkspacePage(currentUser, 'classes') && (
                                <div className="flex items-center justify-between gap-3 text-xs">
                                  <span className="text-slate-400">绑定班级</span>
                                  <button
                                    type="button"
                                    onClick={() => onOpenClassBinding({ teacherUserId: user.id, teacherName: user.name })}
                                    className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-white px-2.5 py-1 font-semibold text-sky-700 transition hover:bg-sky-50 dark:border-sky-500/30 dark:bg-slate-950/70 dark:text-sky-300 dark:hover:bg-sky-500/10"
                                  >
                                    去绑定班级
                                    <ArrowRight size={12} />
                                  </button>
                                </div>
                              )}
                              {visibleClassNames.length > 0 && (
                                <p className="text-xs text-slate-500 dark:text-slate-400">
                                  {visibleClassNames.join('、')}{hiddenClassCount > 0 ? ` +${hiddenClassCount}` : ''}
                                </p>
                              )}
                              <div className="flex items-center justify-between text-xs">
                                <span className="text-slate-400">映射状态</span>
                                <span className="text-slate-700 dark:text-slate-200">
                                  {bindingSummary
                                    ? `已映射 ${bindingSummary.mapping_summary.mapped_count} / 未完成 ${unresolvedCount}`
                                    : bindingSummaryLoading
                                      ? '加载中...'
                                      : '—'}
                                </span>
                              </div>
                            </div>
                            {bindingSummaryError && !bindingSummary && (
                              <p className="mt-2 text-xs text-rose-500 dark:text-rose-300">教学绑定摘要加载失败</p>
                            )}
                          </div>
                          <div className="rounded-2xl border border-sky-100 bg-white/80 p-3 dark:border-white/10 dark:bg-slate-950/70">
                            <div className="flex items-center justify-between gap-3">
                              <h5 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">可见页面</h5>
                              {visiblePageSaving && (
                                <span className="text-xs font-semibold text-sky-600 dark:text-sky-300">保存中...</span>
                              )}
                            </div>
                            <div className="mt-3 grid gap-2 sm:grid-cols-2">
                              {configurableWorkspacePages.map((pageOption) => {
                                const checked = visiblePages.includes(pageOption.id);
                                return (
                                  <button
                                    type="button"
                                    key={`${user.id}-visible-${pageOption.id}`}
                                    onClick={() => void handleToggleVisiblePage(user, pageOption.id)}
                                    disabled={!canEditVisiblePages || visiblePageSaving}
                                    className={cn(
                                      'rounded-xl border px-3 py-2 text-left text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-60',
                                      checked
                                        ? 'border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-400/40 dark:bg-sky-500/10 dark:text-sky-200'
                                        : 'border-slate-200 bg-white text-slate-500 hover:border-sky-200 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10',
                                    )}
                                  >
                                    {pageOption.label}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                        <div className="mt-3 space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            {currentUser.role !== 'admin' && user.role !== 'super_owner' && (
                              <button
                                type="button"
                                onClick={() => handleStartDisplayNameEdit(user.id, user.name)}
                                disabled={displayNameBusy || busy}
                                className={workspaceSecondaryButtonClass}
                              >
                                编辑姓名
                              </button>
                            )}
                            {canDeleteUser && (
                              confirmDeleteUserId === user.id ? (
                                <>
                                  <button
                                    type="button"
                                    onClick={() => void handleDeleteUser(user.id)}
                                    disabled={deleting || busy || displayNameBusy}
                                    className={`${workspaceSecondaryButtonClass} border-rose-300 bg-rose-50 text-rose-700 hover:bg-rose-100 dark:border-rose-500/30 dark:bg-rose-900/20 dark:text-rose-300 dark:hover:bg-rose-900/30`}
                                  >
                                    {deleting ? '删除中...' : '确认删除'}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setConfirmDeleteUserId(null)}
                                    disabled={deleting}
                                    className={workspaceSecondaryButtonClass}
                                  >
                                    取消
                                  </button>
                                </>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => setConfirmDeleteUserId(user.id)}
                                  disabled={busy || displayNameBusy}
                                  className={`${workspaceSecondaryButtonClass} border-rose-200 bg-rose-50/70 text-rose-600 hover:bg-rose-100 dark:border-rose-500/30 dark:bg-rose-900/20 dark:text-rose-300 dark:hover:bg-rose-900/30`}
                                >
                                  删除账号
                                </button>
                              )
                            )}
                          </div>
                          {roleFixed ? (
                            <span className="text-sm text-slate-500 dark:text-slate-400">
                              {user.id === currentUser.id
                                ? '当前登录账号不可在此处调整权限'
                                : user.role === 'super_owner'
                                  ? '超级管理员权限固定，不可调整'
                                  : '该成员权限不可调整'}
                            </span>
                          ) : (
                            <div className="flex items-center gap-2">
                              <select
                                value={pendingRoleByUserId[user.id] ?? user.role}
                                onChange={(event) => {
                                  setPendingRoleByUserId((current) => ({
                                    ...current,
                                    [user.id]: event.target.value as Role,
                                  }));
                                }}
                                disabled={busy}
                                className={`${workspaceFieldClass} min-w-0 flex-1`}
                              >
                                {assignableRoles.map((roleOption) => (
                                  <option key={`${user.id}-role-${roleOption}`} value={roleOption}>
                                    {getRoleLabel(roleOption)}
                                  </option>
                                ))}
                              </select>
                              <button
                                type="button"
                                onClick={() => {
                                  const nextRole = pendingRoleByUserId[user.id] ?? user.role;
                                  void handleRoleUpdate(user.id, user.role, nextRole);
                                }}
                                disabled={busy || (pendingRoleByUserId[user.id] ?? user.role) === user.role}
                                className={workspacePrimaryButtonClass}
                              >
                                {busy ? '保存中...' : '应用权限'}
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* Teacher Alias Mapping Section */}
      {hasOwnerAccess(currentUser.role) && (
        <section className={`${workspaceCardClass} mt-6 p-6`}>
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h4 className="text-xl font-semibold text-slate-900 dark:text-white">讲师映射</h4>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">管理企业微信 ID 到讲师中文名的映射（咨询助手自动识别用）</p>
          </div>
          <button
            type="button"
            className={workspacePrimaryButtonClass}
            disabled={teacherAliasActionLocked}
            onClick={openTeacherAliasCreate}
          >
            <PlusCircle className="h-4 w-4" />
            添加
          </button>
        </div>

        {teacherAliasError && <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300">{teacherAliasError}</div>}

        {teacherAliasLoading ? (
          <div className="flex items-center justify-center py-10 text-slate-400">
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            加载中...
          </div>
        ) : teacherAliases.length === 0 ? (
          <div className="py-10 text-center text-slate-400">暂无映射，点击「添加」创建</div>
        ) : (
          <div className={`${workspaceSoftCardClass} overflow-hidden`}>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-sky-100 dark:border-white/10">
                  <th className="px-5 py-3.5 font-semibold text-slate-500 dark:text-slate-400">企微 ID</th>
                  <th className="px-5 py-3.5 font-semibold text-slate-500 dark:text-slate-400">中文名</th>
                  <th className="px-5 py-3.5 font-semibold text-slate-500 dark:text-slate-400">网站成员</th>
                  <th className="px-5 py-3.5 font-semibold text-slate-500 dark:text-slate-400">别名</th>
                  <th className="px-5 py-3.5 text-right font-semibold text-slate-500 dark:text-slate-400">操作</th>
                </tr>
              </thead>
              <tbody>
                {teacherAliases.map((entry) => {
                  const linkedMember = teacherAliasMemberOptions.find((user) => user.username === entry.linked_username);
                  return (
                    <tr key={entry.wecom_userid} className="border-b border-sky-50 last:border-b-0 dark:border-white/5">
                      <td className="px-5 py-3 font-mono text-xs text-slate-600 dark:text-slate-300">{entry.wecom_userid}</td>
                      <td className="px-5 py-3 font-medium text-slate-800 dark:text-slate-100">{entry.display_name}</td>
                      <td className="px-5 py-3 text-slate-500 dark:text-slate-400">
                        {linkedMember ? `${linkedMember.name}（${linkedMember.username}）` : entry.linked_username || '—'}
                      </td>
                      <td className="px-5 py-3 text-slate-500 dark:text-slate-400">{entry.aliases.slice(1).join('、') || '—'}</td>
                      <td className="px-5 py-3 text-right">
                        <button
                          type="button"
                          className="mr-2 text-sky-600 hover:text-sky-500 disabled:opacity-40 dark:text-sky-400"
                          disabled={teacherAliasActionLocked}
                          onClick={() => openTeacherAliasEdit(entry)}
                        >
                          <Pencil className="inline h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          className="text-red-500 hover:text-red-400 disabled:opacity-40"
                          disabled={teacherAliasActionLocked || taDeletingId === entry.wecom_userid}
                          onClick={() => handleTeacherAliasDelete(entry.wecom_userid)}
                        >
                          <Trash2 className="inline h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        </section>
      )}

      <AnimatePresence>
        {teacherAliasModalOpen && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setTeacherAliasModalOpen(false)}
          >
            <motion.div
              className={`${workspaceCardClass} mx-4 w-full max-w-md p-6`}
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              onClick={(e: React.MouseEvent) => e.stopPropagation()}
            >
              <h3 className="mb-5 text-lg font-bold text-slate-900 dark:text-white">{teacherAliasModalMode === 'create' ? '添加讲师映射' : '编辑讲师映射'}</h3>
              <div className="space-y-4">
                {teacherAliasMemberOptions.length > 0 && (
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-300">关联网站成员（可选）</label>
                    <select
                      className={workspaceFieldClass}
                      value={taLinkedUsername}
                      onChange={(e) => setTaLinkedUsername(e.target.value)}
                    >
                      <option value="">不关联网站成员</option>
                      {teacherAliasMemberOptions.map((user) => (
                        <option key={user.id} value={user.username || ''}>
                          {user.name}{user.username ? `（${user.username}）` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-300">企微 ID（手动填写）</label>
                  <input
                    className={workspaceFieldClass}
                    value={taFormUserId}
                    onChange={(e) => setTaFormUserId(e.target.value)}
                    placeholder="例：XuJianYi"
                    disabled={teacherAliasModalMode === 'edit'}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-300">中文名（手动填写）</label>
                  <input
                    className={workspaceFieldClass}
                    value={taFormDisplayName}
                    onChange={(e) => setTaFormDisplayName(e.target.value)}
                    placeholder="例：徐健译"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-300">别名（逗号分隔，可选）</label>
                  <input
                    className={workspaceFieldClass}
                    value={taFormAliases}
                    onChange={(e) => setTaFormAliases(e.target.value)}
                    placeholder="例：小徐, 徐老师"
                  />
                </div>
              </div>
              <div className="mt-6 flex justify-end gap-3">
                <button type="button" className={workspaceSecondaryButtonClass} onClick={() => setTeacherAliasModalOpen(false)}>取消</button>
                <button
                  type="button"
                  className={workspacePrimaryButtonClass}
                  disabled={taSubmitting || !taFormUserId.trim() || !taFormDisplayName.trim()}
                  onClick={handleTeacherAliasSubmit}
                >{taSubmitting ? '保存中...' : '保存'}</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
