export type StudentCenterRole = 'super_owner' | 'owner' | 'admin' | 'member';

export interface StudentCenterPermissionUser {
  role: StudentCenterRole;
}

export interface StudentCenterPermissions {
  canLoadStaffMembers: boolean;
  canLoadStudentProfiles: boolean;
  canManageClassTeachers: boolean;
  canCreateClass: boolean;
  canManageStudents: boolean;
  canEditTeacherBinding: boolean;
  canUseOrganizationScope: boolean;
  isTeacherScoped: boolean;
  overviewTitle: string;
  overviewScopeLabel: string;
  classScopeLabel: string;
  studentScopeLabel: string;
}

function hasStaffAccess(role: StudentCenterRole): boolean {
  return role === 'super_owner' || role === 'owner' || role === 'admin';
}

export function getStudentCenterPermissions(user: StudentCenterPermissionUser): StudentCenterPermissions {
  const canUseOrganizationScope = hasStaffAccess(user.role);
  const canManageClassTeachers = hasStaffAccess(user.role);
  const isTeacherScoped = user.role === 'member';

  return {
    canLoadStaffMembers: canManageClassTeachers,
    canLoadStudentProfiles: canManageClassTeachers,
    canManageClassTeachers,
    canCreateClass: canManageClassTeachers,
    canManageStudents: canManageClassTeachers,
    canEditTeacherBinding: canManageClassTeachers,
    canUseOrganizationScope,
    isTeacherScoped,
    overviewTitle: canUseOrganizationScope ? '校区总览' : '教师总览',
    overviewScopeLabel: canUseOrganizationScope ? '全校区' : '学生人数',
    classScopeLabel: canUseOrganizationScope ? '全校区班级' : '仅本人班级',
    studentScopeLabel: canUseOrganizationScope ? '全校区学员' : '仅本人学员',
  };
}
