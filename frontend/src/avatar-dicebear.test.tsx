import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { SidebarAccountSheet } from './features/navigation/Sidebar';
import { buildDiceBearAvatarUrl } from './workspaceShared';

test('workspace user avatars use stable DiceBear Dylan URLs', () => {
  const avatarUrl = buildDiceBearAvatarUrl({ id: 7, username: 'teacher-a', display_name: 'Teacher A' });

  assert.equal(avatarUrl, 'https://api.dicebear.com/10.x/dylan/svg?seed=7-teacher-a-Teacher%20A');

  const markup = renderToStaticMarkup(
    <SidebarAccountSheet
      currentUser={{
        id: 7,
        username: 'teacher-a',
        display_name: 'Teacher A',
        role: 'member',
        status: 'active',
        organization_id: 1,
        organization_name: '星润Starain',
        created_at: '2026-03-27 00:00:00',
      }}
      open={true}
      onClose={() => undefined}
      onLogout={() => undefined}
      onOpenSettings={() => undefined}
    />,
  );

  assert.match(markup, /https:\/\/api\.dicebear\.com\/10\.x\/dylan\/svg\?seed=7-teacher-a-Teacher%20A/);
  assert.match(markup, /alt="Teacher A 头像"/);
});

test('workspace account surfaces share DiceBear avatars instead of initial badges', () => {
  const sidebarSource = readFileSync(resolve(process.cwd(), 'src/features/navigation/Sidebar.tsx'), 'utf8');
  const approvalSource = readFileSync(resolve(process.cwd(), 'src/features/approval/ApprovalPage.tsx'), 'utf8');
  const sharedSource = readFileSync(resolve(process.cwd(), 'src/workspaceShared.ts'), 'utf8');

  assert.match(sharedSource, /https:\/\/api\.dicebear\.com\/10\.x\/dylan\/svg\?seed=/);
  assert.equal((sidebarSource.match(/buildDiceBearAvatarUrl\(currentUser\)/g) || []).length, 2);
  assert.match(approvalSource, /buildDiceBearAvatarUrl\(currentUser\)/);
  assert.match(approvalSource, /buildDiceBearAvatarUrl\(user\)/);
  assert.doesNotMatch(sidebarSource, /display_name\.slice\(0, 1\)/);
});
