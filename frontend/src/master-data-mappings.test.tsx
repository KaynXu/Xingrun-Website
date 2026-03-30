import test from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { JSDOM } from 'jsdom';

import { MasterDataMappingsPage } from './MasterDataMappingsPage';
import { fetchWrongQuestionMappingQueue } from './masterDataMappings';

type GlobalKey = keyof typeof globalThis;

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
};

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

function createDeferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return { promise, resolve, reject };
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

test('master data mappings page keeps a record visible when resolve succeeds with a non-final mapping status', async () => {
  const { container, cleanup } = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  let root: Root | null = null;

  try {
    globalThis.fetch = (async (input: RequestInfo | URL) => {
      if (typeof input === 'string' && input === '/api/master-data/mappings/wrong-questions') {
        return createJsonResponse({
          items: [
            {
              record_id: 'record-keep',
              teacher_name_snapshot: '陈老师',
              class_name_snapshot: '六年级 2 班',
              subject_snapshot: '数学',
              mapping_status: 'ambiguous',
              updated_at: '2026-03-31 10:00:00',
            },
          ],
        });
      }

      return createJsonResponse({
        record_id: 'record-keep',
        teacher_user_id: 12,
        class_id: 34,
        mapping_status: 'needs_review',
        teacher_name_snapshot: '陈老师',
        class_name_snapshot: '六年级 2 班',
        subject_snapshot: '数学',
        teacher_display_name: '陈老师（候选）',
        class_display_name: '六年级二班',
        updated_at: '2026-03-31 11:00:00',
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
      assert.ok(container.querySelector('button[data-record-id="record-keep"]'));
    });

    const statusSelect = container.querySelector('select[name="mapping_status"]') as HTMLSelectElement;
    const submitButton = container.querySelector('button[data-record-id="record-keep"]') as HTMLButtonElement;

    await act(async () => {
      statusSelect.value = 'needs_review';
      statusSelect.dispatchEvent(new window.Event('change', { bubbles: true }));
      submitButton.click();
    });

    await waitForAssertion(() => {
      const text = container.textContent || '';
      assert.match(text, /记录 ID: record-keep/);
      assert.match(text, /待复核/);
      assert.match(text, /当前老师映射: 陈老师（候选）/);
      assert.doesNotMatch(text, /当前没有待处理的错题映射记录。/);
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

test('master data mappings page keeps each row loading while overlapping saves are still in flight', async () => {
  const { container, cleanup } = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const firstSave = createDeferred<Response>();
  const secondSave = createDeferred<Response>();
  let root: Root | null = null;

  try {
    globalThis.fetch = (async (input: RequestInfo | URL) => {
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
            {
              record_id: 'record-2',
              teacher_name_snapshot: '王老师',
              class_name_snapshot: '六年级 3 班',
              subject_snapshot: '英语',
              mapping_status: 'needs_review',
              updated_at: '2026-03-31 10:05:00',
            },
          ],
        });
      }

      if (typeof input === 'string' && input.endsWith('/record-1')) {
        return firstSave.promise;
      }

      return secondSave.promise;
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
      assert.ok(container.querySelector('button[data-record-id="record-1"]'));
      assert.ok(container.querySelector('button[data-record-id="record-2"]'));
    });

    const recordOneButton = container.querySelector('button[data-record-id="record-1"]') as HTMLButtonElement;
    const recordTwoButton = container.querySelector('button[data-record-id="record-2"]') as HTMLButtonElement;

    await act(async () => {
      recordOneButton.click();
    });

    await waitForAssertion(() => {
      const button = container.querySelector('button[data-record-id="record-1"]') as HTMLButtonElement | null;
      assert.ok(button);
      assert.equal(button.textContent, '提交中...');
      assert.equal(button.disabled, true);
    });

    await act(async () => {
      recordTwoButton.click();
    });

    await waitForAssertion(() => {
      const firstButton = container.querySelector('button[data-record-id="record-1"]') as HTMLButtonElement | null;
      const secondButton = container.querySelector('button[data-record-id="record-2"]') as HTMLButtonElement | null;
      assert.ok(firstButton);
      assert.ok(secondButton);
      assert.equal(firstButton.textContent, '提交中...');
      assert.equal(secondButton.textContent, '提交中...');
      assert.equal(firstButton.disabled, true);
      assert.equal(secondButton.disabled, true);
    });

    await act(async () => {
      secondSave.resolve(
        createJsonResponse({
          record_id: 'record-2',
          teacher_user_id: 22,
          class_id: 33,
          mapping_status: 'mapped',
          teacher_name_snapshot: '王老师',
          class_name_snapshot: '六年级 3 班',
          subject_snapshot: '英语',
        }),
      );
      await Promise.resolve();
    });

    await waitForAssertion(() => {
      const firstButton = container.querySelector('button[data-record-id="record-1"]') as HTMLButtonElement | null;
      const secondButton = container.querySelector('button[data-record-id="record-2"]') as HTMLButtonElement | null;
      assert.ok(firstButton);
      assert.equal(firstButton.textContent, '提交中...');
      assert.equal(firstButton.disabled, true);
      assert.equal(secondButton, null);
    });

    await act(async () => {
      firstSave.resolve(
        createJsonResponse({
          record_id: 'record-1',
          teacher_user_id: 12,
          class_id: 34,
          mapping_status: 'mapped',
          teacher_name_snapshot: '陈老师',
          class_name_snapshot: '六年级 2 班',
          subject_snapshot: '数学',
        }),
      );
      await Promise.resolve();
    });

    await waitForAssertion(() => {
      assert.match(container.textContent || '', /当前没有待处理的错题映射记录。/);
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