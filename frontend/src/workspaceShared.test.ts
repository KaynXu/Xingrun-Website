import { strict as assert } from 'node:assert';
import { afterEach, test } from 'node:test';

import {
  buildAuthedPath,
  getToken,
  readLocalStorageItem,
  removeLocalStorageItem,
  writeLocalStorageItem,
  workspaceCardClass,
  workspaceSoftCardClass,
} from './workspaceShared';

const originalLocalStorage = globalThis.localStorage;

function setToken(token: string | null): void {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => (key === 'xr_token' ? token : null),
    },
  });
}

afterEach(() => {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: originalLocalStorage,
  });
});

test('buildAuthedPath leaves paths unchanged when no auth token exists', () => {
  setToken(null);

  assert.equal(buildAuthedPath('/api/pdf/12'), '/api/pdf/12');
});

test('buildAuthedPath appends encoded token with the correct query separator', () => {
  setToken('abc 123');

  assert.equal(buildAuthedPath('/api/pdf/12'), '/api/pdf/12?token=abc%20123');
  assert.equal(buildAuthedPath('/api/pdf/12?download=1'), '/api/pdf/12?download=1&token=abc%20123');
});

test('getToken reads the shared auth token key through the storage wrapper', () => {
  setToken('token-123');

  assert.equal(getToken(), 'token-123');
});

test('storage helpers tolerate unavailable localStorage APIs', () => {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
      removeItem: () => {
        throw new Error('blocked');
      },
    },
  });

  assert.equal(readLocalStorageItem('xr_token'), '');
  assert.doesNotThrow(() => writeLocalStorageItem('xr_token', 'token-123'));
  assert.doesNotThrow(() => removeLocalStorageItem('xr_token'));
});

test('workspace shared card surfaces include dark-mode classes', () => {
  assert.match(workspaceCardClass, /dark:border-white\/10/);
  assert.match(workspaceCardClass, /dark:bg-slate-950\/78/);
  assert.match(workspaceSoftCardClass, /dark:border-white\/10/);
  assert.match(
    workspaceSoftCardClass,
    /dark:bg-\[linear-gradient\(180deg,rgba\(15,23,42,0\.96\)_0%,rgba\(15,23,42,0\.9\)_100%\)\]/,
  );
});
