import test from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { JSDOM } from 'jsdom';

import { MasterDataMappingsPage } from './MasterDataMappingsPage';
import { fetchWrongQuestionMappingQueue } from './masterDataMappings';

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
    statusText: status === 200 ? 'OK' : 'Error',
    json: async () => body,
    headers: {
      get() {
        return null;
      },
    },
  } as unknown as Response;
}

async function waitForAssertion(assertion: () => void, timeoutMs = 2_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastError: unknown;

  while (Date.now() < deadline) {
    try {
      assertion();
      return;
    } catch (error) {
      lastError = error;
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 10));
    }
  }

  throw lastError instanceof Error ? lastError : new Error('Timed out waiting for assertion');
}

function setupDomEnvironment(): {
  cleanup: () => void;
  container: HTMLDivElement;
} {
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    url: 'http://localhost/',
  });
  const restoreCallbacks = [
    setGlobalValue('window', dom.window),
    setGlobalValue('document', dom.window.document),
    setGlobalValue('navigator', dom.window.navigator),
    setGlobalValue('HTMLElement', dom.window.HTMLElement),
    setGlobalValue('HTMLButtonElement', dom.window.HTMLButtonElement),
    setGlobalValue('HTMLInputElement', dom.window.HTMLInputElement),
    setGlobalValue('HTMLSelectElement', dom.window.HTMLSelectElement),
    setGlobalValue('Node', dom.window.Node),
    setGlobalValue('Event', dom.window.Event),
    setGlobalValue('MouseEvent', dom.window.MouseEvent),
    setGlobalValue('localStorage', dom.window.localStorage),
    setGlobalValue('IS_REACT_ACT_ENVIRONMENT' as GlobalKey, true),
  ];
  const container = dom.window.document.createElement('div');
  dom.window.document.body.appendChild(container);

  return {
    container,
    cleanup: () => {
      dom.window.document.body.removeChild(container);
      for (const restore of restoreCallbacks.reverse()) {
        restore();
      }
      dom.window.close();
    },
  };
}

test('fetchWrongQuestionMappingQueue calls the master data queue endpoint', async () => {
  const originalFetch = globalThis.fetch;
  const originalLocalStorage = globalThis.localStorage;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];

  try {
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });
      return createJsonResponse({ items: [] });
    }) as typeof fetch;

    globalThis.localStorage = {
      getItem(key: string) {
        return key === 'xr_token' ? 'token-123' : null;
      },
      setItem() {},
      removeItem() {},
      clear() {},
      key() {
        return null;
      },
      length: 0,
    } as Storage;

    await fetchWrongQuestionMappingQueue();
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.localStorage = originalLocalStorage;
  }

  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0]?.input, '/api/master-data/mappings/wrong-questions');
  assert.equal((fetchCalls[0]?.init?.headers as Record<string, string>)['X-Auth-Token'], 'token-123');
});

test('master data mappings page fetches and renders unresolved queue items', async () => {
  const { container, cleanup } = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  let root: Root | null = null;

  try {
    globalThis.fetch = (async () => createJsonResponse({
      items: [
        {
          record_id: 'record-1',
          teacher_name_snapshot: '陈老师',
          class_name_snapshot: '六年级 2 班',
          subject_snapshot: '数学',
          mapping_status: 'needs_review',
          updated_at: '2026-03-31 10:00:00',
        },
      ],
    })) as typeof fetch;

    root = createRoot(container);
    await act(async () => {
      root!.render(
        <MasterDataMappingsPage
          currentUser={{
            display_name: 'Owner',
            organization_name: '星润Starain',
          }}
        />,
      );
    });

    await waitForAssertion(() => {
      const text = container.textContent || '';
      assert.match(text, /主数据映射/);
      assert.match(text, /陈老师/);
      assert.match(text, /六年级 2 班/);
      assert.match(text, /数学/);
    });
  } finally {
    if (root) {
      await act(async () => {
        root!.unmount();
      });
    }
    globalThis.fetch = originalFetch;
    cleanup();
  }
});

test('master data mappings page sends the expected PUT payload when resolving a record', async () => {
  const { container, cleanup } = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  let root: Root | null = null;

  try {
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (typeof input === 'string' && input === '/api/master-data/mappings/wrong-questions') {
        return createJsonResponse({
          items: [
            {
              record_id: 'record-1',
              teacher_name_snapshot: '陈老师',
              class_name_snapshot: '六年级 2 班',
              subject_snapshot: '数学',
              mapping_status: 'needs_review',
              updated_at: '2026-03-31 10:00:00',
            },
          ],
        });
      }

      return createJsonResponse({
        record_id: 'record-1',
        teacher_user_id: 12,
        class_id: 34,
        mapping_status: 'mapped',
        teacher_name_snapshot: '陈老师',
        class_name_snapshot: '六年级 2 班',
        subject_snapshot: '数学',
      });
    }) as typeof fetch;

    root = createRoot(container);
    await act(async () => {
      root!.render(
        <MasterDataMappingsPage
          currentUser={{
            display_name: 'Admin',
            organization_name: '星润Starain',
          }}
        />,
      );
    });

    await waitForAssertion(() => {
      assert.ok(container.querySelector('input[name="teacher_user_id"]'));
      assert.ok(container.querySelector('input[name="class_id"]'));
      assert.ok(container.querySelector('select[name="mapping_status"]'));
    });

    const teacherInput = container.querySelector('input[name="teacher_user_id"]') as HTMLInputElement;
    const classInput = container.querySelector('input[name="class_id"]') as HTMLInputElement;
    const statusSelect = container.querySelector('select[name="mapping_status"]') as HTMLSelectElement;
    const submitButton = container.querySelector('button[data-record-id="record-1"]') as HTMLButtonElement;

    await act(async () => {
      teacherInput.value = '12';
      teacherInput.dispatchEvent(new window.Event('input', { bubbles: true }));
      teacherInput.dispatchEvent(new window.Event('change', { bubbles: true }));
      classInput.value = '34';
      classInput.dispatchEvent(new window.Event('input', { bubbles: true }));
      classInput.dispatchEvent(new window.Event('change', { bubbles: true }));
      statusSelect.value = 'mapped';
      statusSelect.dispatchEvent(new window.Event('change', { bubbles: true }));
      submitButton.click();
    });

    await waitForAssertion(() => {
      assert.equal(fetchCalls.length, 2);
    });
  } finally {
    if (root) {
      await act(async () => {
        root!.unmount();
      });
    }
    globalThis.fetch = originalFetch;
    cleanup();
  }

  assert.equal(fetchCalls[1]?.input, '/api/master-data/mappings/wrong-questions/record-1');
  assert.equal(fetchCalls[1]?.init?.method, 'PUT');
  assert.deepEqual(JSON.parse(String(fetchCalls[1]?.init?.body)), {
    teacher_user_id: 12,
    class_id: 34,
    mapping_status: 'mapped',
  });
});