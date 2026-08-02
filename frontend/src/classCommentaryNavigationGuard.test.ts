import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import {
  CLASS_COMMENTARY_NAVIGATION_REQUEST_EVENT,
  requestClassCommentaryNavigation,
  type ClassCommentaryNavigationRequestDetail,
} from './classCommentaryNavigationGuard';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

test('class commentary navigation request is cancelable and carries the deferred transition', () => {
  const previousWindow = globalThis.window;
  const target = new EventTarget();
  Object.assign(globalThis, { window: target });
  let deferred: (() => void) | null = null;
  let proceeded = false;
  target.addEventListener(CLASS_COMMENTARY_NAVIGATION_REQUEST_EVENT, (rawEvent) => {
    const event = rawEvent as CustomEvent<ClassCommentaryNavigationRequestDetail>;
    deferred = event.detail.proceed;
    event.preventDefault();
  });

  try {
    const allowed = requestClassCommentaryNavigation(() => {
      proceeded = true;
    });
    assert.equal(allowed, false);
    assert.equal(proceeded, false);
    assert.ok(deferred);
    (deferred as () => void)();
    assert.equal(proceeded, true);
  } finally {
    Object.assign(globalThis, { window: previousWindow });
  }
});

test('workspace route, history, home, and logout transitions use the shared guard', () => {
  assert.match(appSource, /const syncWorkspacePageFromHistory = \(\) => \{[\s\S]*requestClassCommentaryNavigation\(proceed\)/);
  assert.match(appSource, /const handleLogout = \(\) => \{[\s\S]*requestClassCommentaryNavigation\(proceed\)/);
  assert.match(appSource, /const navigateWorkspacePage = useCallback[\s\S]*requestClassCommentaryNavigation\(proceed\)/);
  assert.match(appSource, /const handleGoHome = useCallback[\s\S]*requestClassCommentaryNavigation\(proceed\)/);
});
