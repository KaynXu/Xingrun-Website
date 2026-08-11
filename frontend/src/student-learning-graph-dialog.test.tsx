import assert from 'node:assert/strict';
import { test } from 'node:test';
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { JSDOM } from 'jsdom';

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

function createJsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => body,
  } as Response;
}

function learningGraphPayload(studentId: number, knowledgePointName: string) {
  return {
    learning_graph: {
      task_id: 9,
      student_id: studentId,
      subject_key: 'math',
      sync_status: 'learned',
      can_retry: false,
      error: '',
      curriculum_assignment: {
        id: 6,
        class_id: 3,
        version_id: 2,
        version_key: 'pep-math-k12@d8522c2b',
        version_status: 'active',
        book_node_id: 8,
        book_name: '三年级上册',
        curriculum_name: '数学课程知识图谱',
        publisher_name: '课程数据集',
        edition_name: 'K12-KGraph',
        source_dataset_revision: 'd8522c2b',
        data_license: 'CC BY-NC-SA 4.0',
      },
      current_states: [{
        knowledge_point_key: `kp-${studentId}`,
        knowledge_point_name: knowledgePointName,
        state: 'developing',
        observed_at: '2026-08-11T10:00:00Z',
        curriculum: {
          path: [
            { node_key: 'book-3a', node_type: 'Book', name: '三年级上册' },
            { node_key: 'chapter-5', node_type: 'Chapter', name: '第五章' },
            { node_key: `kp-${studentId}`, node_type: 'Concept', name: knowledgePointName },
          ],
          prerequisites: [{ node_key: 'kp-before', node_type: 'Concept', canonical_name: '数的认识' }],
          follow_ups: [{ node_key: 'kp-after', node_type: 'Skill', canonical_name: '综合应用' }],
          source: { version_key: 'pep-math-k12@d8522c2b', dataset_revision: 'd8522c2b', license: 'CC BY-NC-SA 4.0' },
        },
      }],
      timeline: [{
        event_ref: `event-${studentId}`,
        knowledge_point_key: `kp-${studentId}`,
        knowledge_point_name: knowledgePointName,
        state: 'developing',
        previous_state: 'weak',
        trend: 'improved',
        observed_at: '2026-08-11T10:00:00Z',
        evidence: {
          evidence_ref: `evidence-${studentId}`,
          quote: `${knowledgePointName}的确认反馈证据.`,
          lesson_id: 18,
          lesson_name: '第 18 次课程',
          revision_id: 52,
          revision_no: 2,
          confirmed_at: '2026-08-11T10:00:00Z',
        },
        teaching_methods: ['图像与参数联动练习'],
        next_steps: ['继续练习'],
        curriculum: {
          path: [
            { node_key: 'book-3a', node_type: 'Book', name: '三年级上册' },
            { node_key: 'chapter-5', node_type: 'Chapter', name: '第五章' },
            { node_key: `kp-${studentId}`, node_type: 'Concept', name: knowledgePointName },
          ],
          prerequisites: [{ node_key: 'kp-before', node_type: 'Concept', canonical_name: '数的认识' }],
          follow_ups: [{ node_key: 'kp-after', node_type: 'Skill', canonical_name: '综合应用' }],
          source: { version_key: 'pep-math-k12@d8522c2b', dataset_revision: 'd8522c2b', license: 'CC BY-NC-SA 4.0' },
        },
      }],
      used_graph_evidence_refs: [`evidence-${studentId}`],
      used_graph_evidence: [],
    },
  };
}

async function flushEffects(): Promise<void> {
  await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
  await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
}

test('student learning graph dialog ignores stale cross-student responses', async () => {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
    url: 'http://localhost/',
    pretendToBeVisual: true,
  });
  let resolveStudentA: ((response: Response) => void) | null = null;
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
    setGlobalValue('fetch', async (input: string | URL | Request) => {
      if (String(input).includes('/students/11/')) {
        return await new Promise<Response>((resolvePromise) => {
          resolveStudentA = resolvePromise;
        });
      }
      return createJsonResponse(learningGraphPayload(12, '导数基础'));
    }),
  ];
  const container = dom.window.document.getElementById('root');
  assert.ok(container);
  let root: Root | null = null;

  try {
    const { StudentLearningGraphDialog } = await import('./features/class-feedback/StudentLearningGraphDialog');
    root = createRoot(container);
    await act(async () => {
      root?.render(
        <StudentLearningGraphDialog
          open
          onOpenChange={() => {}}
          taskId={9}
          generationId={27}
          revisionId={52}
          subjectKey="math"
          student={{ id: 11, name: '学生 A' }}
          graphHealthy
          graphDegraded={false}
          usedGraphEvidenceRefs={['evidence-11']}
        />,
      );
      await flushEffects();
    });

    assert.ok(dom.window.document.querySelector('[data-testid="student-learning-graph-loading"]'));

    await act(async () => {
      root?.render(
        <StudentLearningGraphDialog
          open
          onOpenChange={() => {}}
          taskId={9}
          generationId={27}
          revisionId={52}
          subjectKey="math"
          student={{ id: 12, name: '学生 B' }}
          graphHealthy
          graphDegraded={false}
          usedGraphEvidenceRefs={['evidence-12']}
        />,
      );
      await flushEffects();
    });

    assert.match(dom.window.document.body.textContent || '', /学生 B的学生成长轨迹/);
    assert.match(dom.window.document.body.textContent || '', /导数基础/);
    assert.match(dom.window.document.body.textContent || '', /三年级上册/);
    assert.match(dom.window.document.body.textContent || '', /前置知识: 数的认识/);
    assert.match(dom.window.document.body.textContent || '', /后续知识: 综合应用/);
    assert.match(dom.window.document.body.textContent || '', /课程版本: pep-math-k12@d8522c2b/);
    assert.doesNotMatch(dom.window.document.body.textContent || '', /二次函数图像/);

    await act(async () => {
      resolveStudentA?.(createJsonResponse(learningGraphPayload(11, '二次函数图像')));
      await flushEffects();
    });

    assert.match(dom.window.document.body.textContent || '', /导数基础/);
    assert.doesNotMatch(dom.window.document.body.textContent || '', /二次函数图像/);
  } finally {
    if (root) {
      await act(async () => {
        root?.unmount();
        await flushEffects();
        await new Promise<void>((resolvePromise) => {
          dom.window.requestAnimationFrame(() => {
            dom.window.requestAnimationFrame(() => resolvePromise());
          });
        });
      });
    }
    for (const restore of restoreCallbacks.reverse()) {
      restore();
    }
    dom.window.close();
  }
});
