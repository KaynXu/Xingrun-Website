import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import * as AppModule from './App';

test('sidebar account sheet shows account info and logout actions', () => {
  const SidebarAccountSheet = (AppModule as { SidebarAccountSheet?: React.ComponentType<{
    currentUser: {
      id: number;
      username: string;
      display_name: string;
      role: 'owner' | 'member';
      status: string;
      organization_id: number;
      organization_name: string;
      created_at: string;
    };
    open: boolean;
    onClose: () => void;
    onLogout: () => void;
    onOpenSettings: () => void;
  }> }).SidebarAccountSheet;

  assert.equal(typeof SidebarAccountSheet, 'function');

  const markup = renderToStaticMarkup(
    <SidebarAccountSheet
      currentUser={{
        id: 1,
        username: 'Kayn',
        display_name: 'Kayn',
        role: 'owner',
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

  assert.match(markup, /查看账号信息/);
  assert.match(markup, /退出登录/);
  assert.match(markup, /星润Starain/);
});
