import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { JSDOM } from 'jsdom';

import App from './App';

type GlobalKey = keyof typeof globalThis;

function setGlobalValue<T>(key: GlobalKey, value: T): () => void {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, key);
  Object.defineProperty(globalThis, key, {
    configurable: true,
    writable: true,
    value,
  });

  return () => {
    if (descriptor) {
      Object.defineProperty(globalThis, key, descriptor);
      return;
    }

    delete (globalThis as Record<string, unknown>)[key];
  };
}

function createJsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Unauthorized',
    json: async () => body,
  } as unknown as Response;
}

async function flushEffects(): Promise<void> {
  await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
  await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
}

test('app still renders when auth storage access throws', () => {
  const originalLocalStorage = globalThis.localStorage;

  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem() {
        throw new Error('storage blocked');
      },
      setItem() {
        throw new Error('storage blocked');
      },
      removeItem() {
        throw new Error('storage blocked');
      },
    },
  });

  try {
    const markup = renderToStaticMarkup(<App />);
    assert.match(markup, /Starain/);
  } finally {
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: originalLocalStorage,
    });
  }
});

test('app falls back to login entry when a stale token cannot be removed from storage', async () => {
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    url: 'http://localhost/',
  });
  let reloadCalls = 0;
  const windowProxy = new Proxy(dom.window, {
    get(target, property, receiver) {
      if (property === 'location') {
        return {
          hash: '',
          pathname: '/',
          reload() {
            reloadCalls += 1;
          },
        };
      }
      const value = Reflect.get(target, property, receiver);
      return typeof value === 'function' ? value.bind(target) : value;
    },
  });
  const restoreCallbacks = [
    setGlobalValue('window', windowProxy),
    setGlobalValue('document', dom.window.document),
    setGlobalValue('navigator', dom.window.navigator),
    setGlobalValue('HTMLElement', dom.window.HTMLElement),
    setGlobalValue('Node', dom.window.Node),
    setGlobalValue('Event', dom.window.Event),
    setGlobalValue('MouseEvent', dom.window.MouseEvent),
    setGlobalValue('IS_REACT_ACT_ENVIRONMENT' as GlobalKey, true),
    setGlobalValue('IntersectionObserver' as GlobalKey, class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }),
    setGlobalValue('localStorage', {
      getItem(key: string) {
        return key === 'xr_token' ? 'stale-token' : null;
      },
      setItem() {
        throw new Error('storage blocked');
      },
      removeItem() {
        throw new Error('storage blocked');
      },
    }),
    setGlobalValue('fetch', async () => createJsonResponse({ error: 'unauthorized' }, 401)),
  ];
  const container = dom.window.document.createElement('div');
  dom.window.document.body.appendChild(container);
  let root: Root | null = null;

  try {
    root = createRoot(container);
    await act(async () => {
      root?.render(<App />);
      await flushEffects();
    });

    await act(async () => {
      await flushEffects();
    });

    assert.equal(reloadCalls, 0);
    assert.match(container.textContent ?? '', /登录/);
    assert.doesNotMatch(container.textContent ?? '', /正在验证账号权限/);
  } finally {
    if (root) {
      await act(async () => {
        root?.unmount();
      });
    }
    dom.window.document.body.removeChild(container);
    for (const restore of restoreCallbacks.reverse()) {
      restore();
    }
    dom.window.close();
  }
});

test('app source avoids direct auth token reads from localStorage during bootstrap', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.doesNotMatch(source, /window\.localStorage\?\.\s*getItem\?\.\('xr_token'\)/);
  assert.equal(source.match(/localStorage\?\.\s*getItem\?\./g)?.length ?? 0, 1);
  assert.doesNotMatch(source, /window\.localStorage\./);
  assert.doesNotMatch(source, /sessionStorage\./);
});
