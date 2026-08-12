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

const gradeNineBooks = [
  { id: 91, version_id: 3, upstream_id: 'book-9-first', canonical_name: '九年级上册', stage_key: 'junior', grade_key: 'grade_9', semester_key: 'first', knowledge_point_count: 115 },
  { id: 92, version_id: 3, upstream_id: 'book-9-second', canonical_name: '九年级下册', stage_key: 'junior', grade_key: 'grade_9', semester_key: 'second', knowledge_point_count: 57 },
];

function createGradeNineScope(mode: 'auto' | 'manual' | 'needs_review' = 'auto') {
  return {
    schema_version: 'class_curriculum_scope.v2',
    class_id: 907,
    class_name: '数学·九年级·7班',
    organization_id: 2,
    subject_key: 'math',
    assignment_mode: mode,
    inferred_grade: mode === 'needs_review' ? '' : '九年级',
    inferred_grade_key: mode === 'needs_review' ? '' : 'grade_9',
    inference_source: mode === 'needs_review' ? '' : 'classes.current_grade',
    needs_review_reason: mode === 'needs_review' ? '班级年级无法安全识别, 请手动设置教材' : '',
    version_id: 3,
    version_key: version.version_key,
    version_status: 'active',
    books: mode === 'needs_review' ? [] : gradeNineBooks.map((book) => ({
      assignment_id: mode === 'manual' ? book.id + 1000 : null,
      book_node_id: book.id,
      book_name: book.canonical_name,
      book_upstream_id: book.upstream_id,
      stage_key: book.stage_key,
      grade_key: book.grade_key,
      semester_key: book.semester_key,
      version_id: book.version_id,
      knowledge_point_count: book.knowledge_point_count,
    })),
    primary_book_node_id: mode === 'needs_review' ? null : 91,
    cas_token: `cas-${mode}`,
  };
}

function createMathClasses() {
  const items = Array.from({ length: 49 }, (_, index) => ({
    id: 1000 + index,
    name: `数学·${(index % 8) + 1}年级·${index + 1}班`,
    subject: '数学',
    subject_key: 'math',
    grade: `${(index % 8) + 1}年级`,
    current_grade: `${(index % 8) + 1}年级`,
    class_number: String(index + 1),
  }));
  items[6] = {
    id: 907,
    name: '数学·九年级·7班',
    subject: '数学',
    subject_key: 'math',
    grade: '九年级',
    current_grade: '九年级',
    class_number: '7',
    lifecycle_status: 'archived',
  };
  return [...items, { id: 5000, name: '英语·九年级·7班', subject: '英语', subject_key: 'english', grade: '九年级', current_grade: '九年级', class_number: '7' }];
}

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
  Object.defineProperty(dom.window.HTMLInputElement.prototype, 'attachEvent', { configurable: true, value: () => undefined });
  Object.defineProperty(dom.window.HTMLInputElement.prototype, 'detachEvent', { configurable: true, value: () => undefined });
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
      if (String(input).endsWith('/api/classes?scope=all')) return createJsonResponse([]);
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
      String(input).endsWith('/api/classes?scope=all') ? createJsonResponse([]) : createJsonResponse({ versions: [] })
    )) as typeof fetch,
    memberUser,
    (dom) => {
      assert.ok(dom.window.document.querySelector('[data-testid="curriculum-page-empty"]'));
      assert.match(dom.window.document.body.textContent || '', /尚未安装课程知识库/);
    },
  );

  await withRenderedPage(
    (async (input: string | URL | Request) => (
      String(input).endsWith('/api/classes?scope=all')
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
    if (path.endsWith('/api/classes?scope=all')) return createJsonResponse([]);
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

    const unmappedTab = Array.from(dom.window.document.querySelectorAll('[role="tab"]')) as HTMLButtonElement[];
    const selectedUnmappedTab = unmappedTab
      .find((button) => button.textContent?.includes('待匹配内容'));
    assert.ok(selectedUnmappedTab);
    await act(async () => {
      selectedUnmappedTab.click();
      await flushEffects();
    });
    assert.ok(dom.window.document.querySelector('[data-testid="curriculum-unmapped-success"]'));
    assert.match(dom.window.document.body.textContent || '', /倍数关系/);
    assert.match(dom.window.document.body.textContent || '', /第 2 次已确认反馈/);
    assert.equal(dom.window.document.querySelector('[data-testid="curriculum-proposal-review-section"]'), null);
    const proposeButton = (Array.from(dom.window.document.querySelectorAll('button')) as HTMLButtonElement[])
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
    const unmappedTab = (Array.from(dom.window.document.querySelectorAll('[role="tab"]')) as HTMLButtonElement[])
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

test('curriculum page finds all math classes without overwriting the automatic two-book scope', async () => {
  const writes: Array<Record<string, unknown>> = [];
  let scope = createGradeNineScope('auto');
  const fetchImpl = (async (input: string | URL | Request, options?: RequestInit) => {
    const path = String(input);
    if (path.endsWith('/api/classes?scope=all')) return createJsonResponse(createMathClasses());
    if (path.endsWith('/versions')) return createJsonResponse({ versions: [version] });
    if (path.includes('/books?')) return createJsonResponse({ books: gradeNineBooks });
    if (path.includes('/catalog?')) return createJsonResponse({ items: [], page: 1, page_size: 30, total: 0 });
    if (path.includes('/classes/907/assignment') && options?.method === 'PUT') {
      writes.push(JSON.parse(String(options.body || '{}')) as Record<string, unknown>);
      scope = { ...createGradeNineScope('manual'), cas_token: 'cas-saved' };
      return createJsonResponse({ assignment: scope });
    }
    if (path.includes('/classes/') && path.endsWith('/assignment')) return createJsonResponse({ assignment: scope });
    throw new Error(`Unexpected request: ${path}`);
  }) as typeof fetch;

  await withRenderedPage(fetchImpl, { ...memberUser, role: 'admin' }, async (dom) => {
    const document = dom.window.document;
    assert.match(document.body.textContent || '', /共 49 个数学班/);

    const classTrigger = document.querySelector<HTMLButtonElement>('[aria-controls="curriculum-class-listbox"]');
    assert.ok(classTrigger);
    await act(async () => {
      classTrigger.click();
      await flushEffects();
    });
    const search = document.querySelector<HTMLInputElement>('input[aria-label="搜索数学班级"]');
    assert.ok(search);
    await act(async () => {
      search.value = '九年级 7';
      search.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
      search.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
      await flushEffects();
    });
    const gradeNineGroup = document.querySelector('[role="group"][aria-labelledby="curriculum-class-grade-九年级"]');
    assert.ok(gradeNineGroup);
    const gradeNineClass = (Array.from(gradeNineGroup.querySelectorAll('[role="option"]')) as HTMLButtonElement[])
      .find((button) => button.textContent?.includes('九年级·7班'));
    assert.ok(gradeNineClass);
    assert.match(gradeNineClass.textContent || '', /历史/);
    assert.doesNotMatch(document.querySelector('[role="listbox"]')?.textContent || '', /英语/);
    await act(async () => {
      gradeNineClass.click();
      await flushEffects();
    });

    assert.match(document.body.textContent || '', /系统已按九年级自动启用: 九年级上册、九年级下册/);
    assert.match(document.body.textContent || '', /教材范围 · 已启用 2 册/);
    const checks = Array.from(document.querySelectorAll('[data-slot="checkbox"]')) as HTMLButtonElement[];
    assert.equal(checks.length, 2);
    assert.ok(checks.every((checkbox) => checkbox.getAttribute('data-state') === 'checked'));

    const save = (Array.from(document.querySelectorAll('button')) as HTMLButtonElement[])
      .find((button) => button.textContent?.includes('保存调整'));
    assert.ok(save);
    assert.equal(save.disabled, true);
    await act(async () => {
      save.click();
      await flushEffects();
    });
    assert.equal(writes.length, 0);

    await act(async () => {
      checks[1].click();
      await flushEffects();
    });
    assert.equal(save.disabled, false);
    await act(async () => {
      save.click();
      await flushEffects();
    });
    assert.equal(writes.length, 1);
    assert.deepEqual(writes[0].book_node_ids, [91]);
    assert.equal(writes[0].primary_book_node_id, 91);
    assert.equal(writes[0].expected_cas_token, 'cas-auto');
    assert.match(String(writes[0].request_id), /^curriculum-assignment-/);
  });
});

test('curriculum page distinguishes manual and needs-review assignments', async () => {
  for (const [mode, expected] of [
    ['manual', /当前手动范围: 九年级上册、九年级下册/],
    ['needs_review', /需要设置: 班级年级无法安全识别/],
  ] as const) {
    const fetchImpl = (async (input: string | URL | Request) => {
      const path = String(input);
      if (path.endsWith('/api/classes?scope=all')) return createJsonResponse(createMathClasses().filter((item) => item.id === 907));
      if (path.endsWith('/versions')) return createJsonResponse({ versions: [version] });
      if (path.includes('/books?')) return createJsonResponse({ books: gradeNineBooks });
      if (path.includes('/catalog?')) return createJsonResponse({ items: [], page: 1, page_size: 30, total: 0 });
      if (path.includes('/classes/907/assignment')) return createJsonResponse({ assignment: createGradeNineScope(mode) });
      throw new Error(`Unexpected request: ${path}`);
    }) as typeof fetch;
    await withRenderedPage(fetchImpl, { ...memberUser, role: 'admin' }, (dom) => {
      assert.match(dom.window.document.body.textContent || '', expected);
      if (mode === 'manual') assert.match(dom.window.document.body.textContent || '', /恢复按年级自动匹配/);
      if (mode === 'needs_review') assert.doesNotMatch(dom.window.document.body.textContent || '', /恢复按年级自动匹配/);
    });
  }
});

test('curriculum page keeps raw identifiers inside collapsed technical details', async () => {
  const fetchImpl = (async (input: string | URL | Request) => {
    const path = String(input);
    if (path.endsWith('/api/classes?scope=all')) return createJsonResponse([]);
    if (path.endsWith('/versions')) return createJsonResponse({ versions: [{
      ...version,
      source_dataset_revision: 'raw-revision-d8522c2b',
      source_sha256: 'raw-source-sha',
      content_hash: 'raw-content-hash',
    }] });
    if (path.includes('/books?')) return createJsonResponse({ books: gradeNineBooks });
    if (path.includes('/catalog?')) return createJsonResponse({ items: [], page: 1, page_size: 30, total: 0 });
    throw new Error(`Unexpected request: ${path}`);
  }) as typeof fetch;
  await withRenderedPage(fetchImpl, memberUser, async (dom) => {
    const document = dom.window.document;
    assert.match(document.body.textContent || '', /数学课程知识图谱/);
    assert.match(document.body.textContent || '', /许可说明: CC BY-NC-SA 4.0/);
    for (const rawValue of [version.version_key, 'raw-revision-d8522c2b', 'raw-source-sha', 'raw-content-hash']) {
      assert.doesNotMatch(document.body.textContent || '', new RegExp(rawValue.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    }
    const trigger = (Array.from(document.querySelectorAll('button')) as HTMLButtonElement[])
      .find((button) => button.textContent?.includes('技术详情'));
    assert.ok(trigger);
    assert.equal(trigger.getAttribute('aria-expanded'), 'false');
    await act(async () => {
      trigger.click();
      await flushEffects();
    });
    assert.equal(trigger.getAttribute('aria-expanded'), 'true');
    for (const rawValue of [version.version_key, 'raw-revision-d8522c2b', 'raw-source-sha', 'raw-content-hash']) {
      const rawNode = (Array.from(document.querySelectorAll('p')) as HTMLParagraphElement[]).find((node) => node.textContent?.includes(rawValue));
      assert.ok(rawNode?.closest('[data-slot="accordion-content"]'), `${rawValue} must stay inside technical details`);
    }
  });
});
