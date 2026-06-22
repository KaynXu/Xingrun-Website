import assert from 'node:assert/strict';
import test from 'node:test';

import { getStudentCenterPermissions, type StudentCenterRole } from './permissions';

const roles: StudentCenterRole[] = ['super_owner', 'owner', 'admin', 'member'];

test('student center permissions keep the existing role scope behavior', () => {
  const permissionsByRole = Object.fromEntries(
    roles.map((role) => [role, getStudentCenterPermissions({ role })]),
  );

  assert.equal(permissionsByRole.super_owner.canUseOrganizationScope, true);
  assert.equal(permissionsByRole.owner.canUseOrganizationScope, true);
  assert.equal(permissionsByRole.admin.canUseOrganizationScope, true);
  assert.equal(permissionsByRole.member.canUseOrganizationScope, false);

  assert.equal(permissionsByRole.super_owner.isTeacherScoped, false);
  assert.equal(permissionsByRole.owner.isTeacherScoped, false);
  assert.equal(permissionsByRole.admin.isTeacherScoped, false);
  assert.equal(permissionsByRole.member.isTeacherScoped, true);
});

test('student center permissions centralize staff-only class management actions', () => {
  const superOwner = getStudentCenterPermissions({ role: 'super_owner' });
  const owner = getStudentCenterPermissions({ role: 'owner' });
  const admin = getStudentCenterPermissions({ role: 'admin' });
  const member = getStudentCenterPermissions({ role: 'member' });

  for (const permissions of [superOwner, owner, admin]) {
    assert.equal(permissions.canLoadStaffMembers, true);
    assert.equal(permissions.canCreateClass, true);
    assert.equal(permissions.canManageClassTeachers, true);
    assert.equal(permissions.canManageStudents, true);
    assert.equal(permissions.canEditTeacherBinding, true);
  }

  assert.equal(member.canLoadStaffMembers, false);
  assert.equal(member.canCreateClass, false);
  assert.equal(member.canManageClassTeachers, false);
  assert.equal(member.canManageStudents, false);
  assert.equal(member.canEditTeacherBinding, false);
});

test('student center permissions provide display labels for scoped filters', () => {
  assert.equal(getStudentCenterPermissions({ role: 'super_owner' }).classScopeLabel, '全校区班级');
  assert.equal(getStudentCenterPermissions({ role: 'owner' }).studentScopeLabel, '全校区学员');
  assert.equal(getStudentCenterPermissions({ role: 'admin' }).classScopeLabel, '全校区班级');
  assert.equal(getStudentCenterPermissions({ role: 'member' }).studentScopeLabel, '仅本人学员');
});

test('member permissions are read-only in the student center flow', () => {
  const member = getStudentCenterPermissions({ role: 'member' });

  assert.equal(member.canLoadStaffMembers, false);
  assert.equal(member.canManageClassTeachers, false);
  assert.equal(member.canCreateClass, false);
  assert.equal(member.canManageStudents, false);
  assert.equal(member.canEditTeacherBinding, false);
  assert.equal(member.canUseOrganizationScope, false);
  assert.equal(member.isTeacherScoped, true);
});
