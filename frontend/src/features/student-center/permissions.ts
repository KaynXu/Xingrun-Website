export type StudentCenterRole = 'super_owner' | 'owner' | 'admin' | 'member';

export interface StudentCenterPermissionUser {
  role: StudentCenterRole;
}

export interface StudentCenterPermissions {
  canLoadStaffMembers: boolean;
  canManageClassTeachers: boolean;
  canCreateClass: boolean;
  canEditTeacherBinding: boolean;
  canUseOrganizationScope: boolean;
  isTeacherScoped: boolean;
  classScopeLabel: string;
  studentScopeLabel: string;
}

function hasOwnerAccess(role: StudentCenterRole): boolean {
  return role === 'super_owner' || role === 'owner';
}

function hasStaffAccess(role: StudentCenterRole): boolean {
  return hasOwnerAccess(role) || role === 'admin';
}

export function getStudentCenterPermissions(user: StudentCenterPermissionUser): StudentCenterPermissions {
  const canUseOrganizationScope = hasOwnerAccess(user.role);
  const canManageClassTeachers = hasStaffAccess(user.role);
  const isTeacherScoped = user.role === 'member';

  return {
    canLoadStaffMembers: canManageClassTeachers,
    canManageClassTeachers,
    canCreateClass: canManageClassTeachers,
    canEditTeacherBinding: canManageClassTeachers,
    canUseOrganizationScope,
    isTeacherScoped,
    classScopeLabel: canUseOrganizationScope ? '全机构班级' : '仅本人班级',
    studentScopeLabel: canUseOrganizationScope ? '全机构学员' : '仅本人学员',
  };
}
