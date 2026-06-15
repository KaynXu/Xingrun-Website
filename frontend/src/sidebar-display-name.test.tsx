import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { SidebarAccountSheet } from './features/navigation/Sidebar';

test('sidebar account surfaces prefer display names over login usernames', () => {
  const markup = renderToStaticMarkup(
    <SidebarAccountSheet
      currentUser={{
        id: 7,
        username: 'dxiaodi',
        display_name: '华老师',
        role: 'super_owner',
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

  assert.match(markup, /华老师/);
  assert.doesNotMatch(markup, />dxiaodi</);
});

test('sidebar source derives footer and account sheet labels from display names first', () => {
  const sidebarSource = readFileSync(resolve(process.cwd(), 'src/features/navigation/Sidebar.tsx'), 'utf8');

  assert.match(sidebarSource, /function getPreferredUserLabel/);
  assert.match(sidebarSource, /return user\.display_name\.trim\(\) \|\| user\.username;/);
  assert.match(sidebarSource, /const preferredUserLabel = getPreferredUserLabel\(currentUser\);/);
  assert.match(sidebarSource, /<div className="flex flex-wrap items-center gap-2">/);
  assert.match(sidebarSource, /<p className="truncate text-lg font-semibold text-slate-900 dark:text-slate-100">\{preferredUserLabel\}<\/p>/);
});
