import assert from 'node:assert/strict';
import { test } from 'node:test';
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { JSDOM } from 'jsdom';

import type { CurrentUser } from './appTypes';

type GlobalKey = keyof typeof globalThis;

function setGlobalValue<T>(key: GlobalKey, value: T): () => void {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, key);
  Object.defineProperty(globalThis, key, { configurable: true, writable: true, value });
  return () => {
    if (descriptor) {
      Object.defineProperty(globalThis, key, descriptor);
      return;
    }
    delete (globalThis as Record<string, unknown>)[key];
  };
}

function createJsonResponse(body: unknown, ok = true): Response {
  return {
    ok,
    status: ok ? 200 : 500,
    statusText: ok ? 'OK' : 'Server Error',
    json: async () => body,
  } as Response;
}

const memberUser: CurrentUser = {
  id: 7,
  username: 'teacher',
  display_name: '老师',
  role: 'member',
  status: 'active',
  organization_id: 2,
  organization_name: '测试机构',
  created_at: '2026-08-11T00:00:00Z',
};

const version = {
  id: 3,
  package_id: 2,
  package_key: 'pep-math-k12',
  curriculum_name: '数学课程知识图谱',
  subject_key: 'math',
  publisher_name: '课程数据集',
  edition_name: 'K12-KGraph',
  version_key: 'pep-math-k12@d8522c2b',
  registry_version: 1,
  status: 'active',
  source_dataset_revision: 'd8522c2b',
  data_license: 'CC BY-NC-SA 4.0',
  node_count: 2237,
  edge_count: 4007,
};

async function flushEffects(): Promise<void> {
  await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
  await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
  await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
}

async function withRenderedPage(
  fetchImpl: typeof fetch,
  user: CurrentUser,
  assertion: (dom: JSDOM) => void | Promise<void>,
): Promise<void> {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
    url: 'http://localhost/workspace/curriculum-knowledge',
    pretendToBeVisual: true,
  });
  const restoreCallbacks = [
    setGlobalValue('window', dom.window),
    setGlobalValue('document', dom.window.document),
    setGlobalValue('navigator', dom.window.navigator),
    setGlobalValue('HTMLElement', dom.window.HTMLElement),
    setGlobalValue('HTMLInputElement', dom.window.HTMLInputElement),
    setGlobalValue('HTMLButtonElement', dom.window.HTMLButtonElement),
    setGlobalValue('HTMLTextAreaElement', dom.window.HTMLTextAreaElement),
    setGlobalValue('HTMLSelectElement', dom.window.HTMLSelectElement),
    setGlobalValue('Element', dom.window.Element),
    setGlobalValue('SVGElement', dom.window.SVGElement),
    setGlobalValue('DocumentFragment', dom.window.DocumentFragment),
    setGlobalValue('Node', dom.window.Node),
    setGlobalValue('NodeFilter' as GlobalKey, dom.window.NodeFilter),
    setGlobalValue('Event', dom.window.Event),
    setGlobalValue('CustomEvent', dom.window.CustomEvent),
    setGlobalValue('MouseEvent', dom.window.MouseEvent),
    setGlobalValue('MutationObserver', dom.window.MutationObserver),
    setGlobalValue('getComputedStyle', dom.window.getComputedStyle.bind(dom.window)),
    setGlobalValue('requestAnimationFrame', dom.window.requestAnimationFrame.bind(dom.window)),
    setGlobalValue('cancelAnimationFrame', dom.window.cancelAnimationFrame.bind(dom.window)),
    setGlobalValue('IS_REACT_ACT_ENVIRONMENT' as GlobalKey, true),
    setGlobalValue('ResizeObserver' as GlobalKey, class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }),
    setGlobalValue('fetch', fetchImpl),
  ];
  const container = dom.window.document.getElementById('root');
  assert.ok(container);
  let root: Root | null = null;

  try {
    const { CurriculumKnowledgePage } = await import('./features/curriculum/CurriculumKnowledgePage');
    root = createRoot(container);
    await act(async () => {
      root?.render(<CurriculumKnowledgePage currentUser={user} />);
      await flushEffects();
    });
    await assertion(dom);
  } finally {
    if (root) {
      await act(async () => {
        root?.unmount();
        await flushEffects();
      });
    }
    for (const restore of restoreCallbacks.reverse()) restore();
    dom.window.close();
  }
}

test('curriculum page exposes a stable loading state while the version request is pending', async () => {
  await withRenderedPage(
    (async (input: string | URL | Request) => {
      if (String(input).endsWith('/api/classes')) return createJsonResponse([]);
      return await new Promise<Response>(() => {});
    }) as typeof fetch,
    memberUser,
    (dom) => {
      assert.ok(dom.window.document.querySelector('[data-testid="curriculum-page-loading"]'));
    },
  );
});

test('curriculum page renders empty and error states without leaking internal payloads', async () => {
  await withRenderedPage(
    (async (input: string | URL | Request) => (
      String(input).endsWith('/api/classes') ? createJsonResponse([]) : createJsonResponse({ versions: [] })
    )) as typeof fetch,
    memberUser,
    (dom) => {
      assert.ok(dom.window.document.querySelector('[data-testid="curriculum-page-empty"]'));
      assert.match(dom.window.document.body.textContent || '', /尚未安装课程知识库/);
    },
  );

  await withRenderedPage(
    (async (input: string | URL | Request) => (
      String(input).endsWith('/api/classes')
        ? createJsonResponse([])
        : createJsonResponse({ error: '课程服务暂时不可用' }, false)
    )) as typeof fetch,
    memberUser,
    (dom) => {
      assert.ok(dom.window.document.querySelector('[data-testid="curriculum-page-error"]'));
      assert.match(dom.window.document.body.textContent || '', /课程服务暂时不可用/);
    },
  );
});

test('curriculum page renders catalog success, unmapped success, and role-gated lifecycle controls', async () => {
  const fetchImpl = (async (input: string | URL | Request) => {
    const path = String(input);
    if (path.endsWith('/api/classes')) return createJsonResponse([]);
    if (path.endsWith('/versions')) return createJsonResponse({ versions: [version] });
    if (path.includes('/books?')) return createJsonResponse({ books: [{ id: 8, version_id: 3, upstream_id: 'book-3a', canonical_name: '三年级上册', stage_key: 'primary', grade_key: '3', semester_key: 'first', knowledge_point_count: 99 }] });
    if (path.includes('/catalog?')) return createJsonResponse({ items: [{ id: 11, version_id: 3, node_key: 'kp-11', upstream_id: 'concept-11', node_type: 'Concept', subject_key: 'math', canonical_name: '倍的认识', aliases: ['倍数'], stage_key: 'primary', grade_key: '3', book_upstream_id: 'book-3a' }], page: 1, page_size: 30, total: 1 });
    if (path.includes('/unmapped?')) return createJsonResponse({ items: [{ candidate_id: 'candidate-1', candidate_text: '倍数关系', status: 'pending', revision_id: 41, revision_no: 2, curriculum_version_id: 3, curriculum_book_node_id: 8, curriculum_assignment: { book_name: '三年级上册', version_key: 'pep-math-k12@d8522c2b', book_upstream_id: 'book-3a' }, created_at: '2026-08-11T10:00:00Z' }], page: 1, page_size: 30, total: 1 });
    if (path.includes('/proposals?')) return createJsonResponse({ items: [{ id: 4, canonical_name: '倍数关系新知识点', status: 'proposed', book_name: '三年级上册', version_key: 'pep-math-k12@d8522c2b' }] });
    throw new Error(`Unexpected request: ${path}`);
  }) as typeof fetch;

  await withRenderedPage(fetchImpl, memberUser, async (dom) => {
    assert.ok(dom.window.document.querySelector('[data-testid="curriculum-catalog-success"]'));
    assert.match(dom.window.document.body.textContent || '', /倍的认识/);
    assert.match(dom.window.document.body.textContent || '', /第三方 K12-KGraph/);
    assert.equal(dom.window.document.querySelector('[data-testid="curriculum-lifecycle-controls"]'), null);
    assert.doesNotMatch(dom.window.document.body.textContent || '', /保存分配/);

    const unmappedTab = Array.from(dom.window.document.querySelectorAll<HTMLButtonElement>('[role="tab"]'))
      .find((button) => button.textContent?.includes('待匹配内容'));
    assert.ok(unmappedTab);
    await act(async () => {
      unmappedTab.click();
      await flushEffects();
    });
    assert.ok(dom.window.document.querySelector('[data-testid="curriculum-unmapped-success"]'));
    assert.match(dom.window.document.body.textContent || '', /倍数关系/);
    assert.match(dom.window.document.body.textContent || '', /第 2 次已确认反馈/);
    assert.equal(dom.window.document.querySelector('[data-testid="curriculum-proposal-review-section"]'), null);
    const proposeButton = Array.from(dom.window.document.querySelectorAll<HTMLButtonElement>('button'))
      .find((button) => button.textContent?.includes('提议知识点'));
    assert.ok(proposeButton);
    await act(async () => {
      proposeButton.click();
      await flushEffects();
    });
    assert.ok(dom.window.document.querySelector('[data-testid="curriculum-mapping-dialog"]'));
    assert.match(dom.window.document.body.textContent || '', /提议新知识点/);
    assert.doesNotMatch(dom.window.document.body.textContent || '', /匹配到知识点/);
  });

  await withRenderedPage(fetchImpl, { ...memberUser, role: 'super_owner' }, async (dom) => {
    assert.ok(dom.window.document.querySelector('[data-testid="curriculum-lifecycle-controls"]'));
    const unmappedTab = Array.from(dom.window.document.querySelectorAll<HTMLButtonElement>('[role="tab"]'))
      .find((button) => button.textContent?.includes('待匹配内容'));
    assert.ok(unmappedTab);
    await act(async () => {
      unmappedTab.click();
      await flushEffects();
    });
    assert.ok(dom.window.document.querySelector('[data-testid="curriculum-proposal-review-section"]'));
    assert.match(dom.window.document.body.textContent || '', /倍数关系新知识点/);
  });
});
