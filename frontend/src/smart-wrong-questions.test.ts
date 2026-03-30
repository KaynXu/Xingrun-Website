import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { JSDOM } from 'jsdom';

import {
  applyWrongQuestionReviewDraft,
  buildWrongQuestionDetailPath,
  buildWrongQuestionQuery,
  buildWrongQuestionReviewDraft,
  buildWrongQuestionReviewPath,
  buildWrongQuestionSummaryExportPath,
  downloadWrongQuestionSummary,
  hydrateWrongQuestionReviewDraftFromDetail,
  normalizeWrongQuestionRecord,
  normalizeWrongQuestionListResponse,
  resolveSavedWrongQuestionRecord,
  summarizeWrongQuestionRecords,
  type WrongQuestionRecord,
} from './smartWrongQuestions';
import { SmartWrongQuestionsPage } from './SmartWrongQuestionsPage';

const currentDir = dirname(fileURLToPath(import.meta.url));

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
    setGlobalValue('HTMLTextAreaElement', dom.window.HTMLTextAreaElement),
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

test('summarizeWrongQuestionRecords derives the overview card counts from loaded records', () => {
  const records: WrongQuestionRecord[] = [
    {
      id: 'record-1',
      studentName: 'Alice',
      className: '六年级 1 班',
      classNameSnapshot: '六年级 1 班',
      classId: null,
      subject: '数学',
      teacherName: '雷文浩',
      teacherNameSnapshot: '雷文浩',
      teacherUserId: null,
      mappingStatus: 'mapped',
      createdAt: '2026-03-29T08:00:00Z',
      analysis: {
        questionCategory: '计算',
        errorType: '计算错误',
        knowledgePoints: ['分数运算'],
        isRepeatedMistake: '是',
        teacherPriority: '高',
      },
    },
    {
      id: 'record-2',
      studentName: 'Bob',
      className: '初一 2 班',
      classNameSnapshot: '初一 2 班',
      classId: null,
      subject: '英语',
      teacherName: '王老师',
      teacherNameSnapshot: '王老师',
      teacherUserId: null,
      mappingStatus: 'mapped',
      createdAt: '2026-03-29T09:00:00Z',
      analysis: {
        questionCategory: '阅读',
        errorType: '定位错误',
        knowledgePoints: ['细节定位'],
        isRepeatedMistake: '否',
        teacherPriority: '中',
        selectedErrorType: '定位错误',
      },
    },
    {
      id: 'record-3',
      studentName: 'Cathy',
      className: '高一 3 班',
      classNameSnapshot: '高一 3 班',
      classId: null,
      subject: '物理',
      teacherName: '李老师',
      teacherNameSnapshot: '李老师',
      teacherUserId: null,
      mappingStatus: 'mapped',
      createdAt: '2026-03-29T10:00:00Z',
      analysis: {
        questionCategory: '受力',
        errorType: '模型错误',
        knowledgePoints: ['受力分析'],
        isRepeatedMistake: '待确认',
        teacherPriority: '高',
      },
    },
  ];

  assert.deepEqual(summarizeWrongQuestionRecords(records), {
    totalCount: 3,
    repeatedMistakeCount: 2,
    highPriorityCount: 2,
    pendingReviewCount: 2,
  });
});

test('buildWrongQuestionQuery serializes only non-empty trimmed filters', () => {
  assert.equal(
    buildWrongQuestionQuery({
      studentName: ' Alice ',
      className: ' 六年级 1 班 ',
      subject: ' 数学 ',
      teacherName: '',
      errorType: '  ',
      onlyPendingReview: true,
    }),
    '?studentName=Alice&className=%E5%85%AD%E5%B9%B4%E7%BA%A7%201%20%E7%8F%AD&subject=%E6%95%B0%E5%AD%A6&onlyPendingReview=true',
  );

  assert.equal(buildWrongQuestionQuery({ studentName: '   ', onlyPendingReview: false }), '');
});

test('buildWrongQuestionSummaryExportPath reuses the normalized filter query', () => {
  assert.equal(
    buildWrongQuestionSummaryExportPath({
      studentName: ' Alice ',
      className: ' 六年级 1 班 ',
      onlyPendingReview: true,
    }),
    '/api/wrong-questions/summary/export?studentName=Alice&className=%E5%85%AD%E5%B9%B4%E7%BA%A7%201%20%E7%8F%AD&onlyPendingReview=true',
  );
});

test('record detail and review paths encode record ids consistently', () => {
  assert.equal(
    buildWrongQuestionDetailPath('record/with space?#x'),
    '/api/wrong-questions/record%2Fwith%20space%3F%23x',
  );

  assert.equal(
    buildWrongQuestionReviewPath('record/with space?#x'),
    '/api/wrong-questions/record%2Fwith%20space%3F%23x/review',
  );
});

test('downloadWrongQuestionSummary fetches the export with auth header and triggers a blob download', async () => {
  const originalFetch = globalThis.fetch;
  const originalDocument = globalThis.document;
  const originalLocalStorage = globalThis.localStorage;
  const originalUrl = globalThis.URL;

  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  const clickedHrefs: string[] = [];
  const appendCalls: unknown[] = [];
  const removeCalls: unknown[] = [];
  const revokeCalls: string[] = [];
  const anchor = {
    href: '',
    download: '',
    rel: '',
    style: { display: '' },
    click() {
      clickedHrefs.push(this.href);
    },
  };

  try {
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });
      return {
        ok: true,
        status: 200,
        statusText: 'OK',
        headers: {
          get(name: string) {
            return name.toLowerCase() === 'content-disposition'
              ? 'attachment; filename="smart-summary.pdf"'
              : null;
          },
        },
        blob: async () => new Blob(['pdf-bytes'], { type: 'application/pdf' }),
      } as Response;
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

    globalThis.document = {
      body: {
        appendChild(node: unknown) {
          appendCalls.push(node);
        },
        removeChild(node: unknown) {
          removeCalls.push(node);
        },
      },
      createElement(tagName: string) {
        assert.equal(tagName, 'a');
        return anchor as unknown as HTMLAnchorElement;
      },
    } as Document;

    globalThis.URL = {
      ...originalUrl,
      createObjectURL(blob: Blob) {
        assert.equal(blob.type, 'application/pdf');
        return 'blob:smart-summary';
      },
      revokeObjectURL(url: string) {
        revokeCalls.push(url);
      },
    } as typeof URL;

    await downloadWrongQuestionSummary({ studentName: ' Alice ', onlyPendingReview: true });
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.document = originalDocument;
    globalThis.localStorage = originalLocalStorage;
    globalThis.URL = originalUrl;
  }

  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0]?.input, '/api/wrong-questions/summary/export?studentName=Alice&onlyPendingReview=true');
  assert.equal((fetchCalls[0]?.init?.headers as Record<string, string>)['X-Auth-Token'], 'token-123');
  assert.equal(anchor.download, 'smart-summary.pdf');
  assert.equal(anchor.rel, 'noopener');
  assert.deepEqual(clickedHrefs, ['blob:smart-summary']);
  assert.equal(appendCalls.length, 1);
  assert.equal(removeCalls.length, 1);
  assert.deepEqual(revokeCalls, ['blob:smart-summary']);
});

test('normalizeWrongQuestionListResponse converts backend object payloads into page-ready camelCase records', () => {
  const normalized = normalizeWrongQuestionListResponse({
    items: [
      {
        id: 123,
        studentNickname: 'Alice',
        class_name: '六年级 1 班',
        subject: '数学',
        teacher_name: '雷文浩',
        created_at: '2026-03-29T08:00:00Z',
        image_url: 'https://cdn.example.com/question-1.png',
        analysis: {
          question_category: '计算',
          error_type: '计算错误',
          knowledge_points: ['分数运算'],
          is_repeated_mistake: '是',
          teacher_priority: '高',
        },
      },
      {
        id: 'record-2',
        student_name: 'Bob',
        className: '初一 2 班',
        teacherName: '王老师',
        createdAt: '2026-03-29T09:00:00Z',
      },
    ],
    summary: {
      total_count: 9,
      repeated_mistake_count: 4,
      high_priority_count: 2,
      pending_review_count: 5,
    },
    total: 12,
  });

  assert.deepEqual(normalized.items[0], {
    id: '123',
    studentName: 'Alice',
    className: '六年级 1 班',
    classNameSnapshot: '六年级 1 班',
    classId: null,
    subject: '数学',
    teacherName: '雷文浩',
    teacherNameSnapshot: '雷文浩',
    teacherUserId: null,
    mappingStatus: 'mapped',
    createdAt: '2026-03-29T08:00:00Z',
    imageUrl: 'https://cdn.example.com/question-1.png',
    analysis: {
      questionCategory: '计算',
      errorType: '计算错误',
      knowledgePoints: ['分数运算'],
      isRepeatedMistake: '是',
      teacherPriority: '高',
    },
  });

  assert.deepEqual(normalized.items[1], {
    id: 'record-2',
    studentName: 'Bob',
    className: '初一 2 班',
    classNameSnapshot: '初一 2 班',
    classId: null,
    subject: '',
    teacherName: '王老师',
    teacherNameSnapshot: '王老师',
    teacherUserId: null,
    mappingStatus: 'mapped',
    createdAt: '2026-03-29T09:00:00Z',
    imageUrl: '',
    analysis: {
      questionCategory: '',
      errorType: '',
      knowledgePoints: [],
    },
  });

  assert.deepEqual(normalized.summary, {
    totalCount: 12,
    repeatedMistakeCount: 4,
    highPriorityCount: 2,
    pendingReviewCount: 5,
  });
});

test('normalizeWrongQuestionRecord preserves canonical and snapshot identities side by side', () => {
  const normalized = normalizeWrongQuestionRecord({
    id: 'record-identity-1',
    student_name: 'Alice',
    class_display_name: '六年级 1 班',
    class_name_snapshot: '六年级一班（临时）',
    class_id: 42,
    subject: '数学',
    teacher_display_name: 'Kayn',
    teacher_name_snapshot: 'Kayn 老师（代课）',
    teacher_user_id: 7,
    mapping_status: 'needs_review',
    created_at: '2026-03-29T08:00:00Z',
    analysis: {
      question_category: '计算',
      error_type: '计算错误',
      knowledge_points: ['分数运算'],
    },
  });

  assert.deepEqual(normalized, {
    id: 'record-identity-1',
    studentName: 'Alice',
    className: '六年级 1 班',
    classNameSnapshot: '六年级一班（临时）',
    classId: 42,
    subject: '数学',
    teacherName: 'Kayn',
    teacherNameSnapshot: 'Kayn 老师（代课）',
    teacherUserId: 7,
    mappingStatus: 'needs_review',
    createdAt: '2026-03-29T08:00:00Z',
    imageUrl: '',
    analysis: {
      questionCategory: '计算',
      errorType: '计算错误',
      knowledgePoints: ['分数运算'],
    },
  });
});

test('hydrateWrongQuestionReviewDraftFromDetail replaces pristine drafts and preserves locally edited drafts', () => {
  const listRecord: WrongQuestionRecord = {
    id: 'record-1',
    studentName: 'Alice',
    className: '六年级 1 班',
    classNameSnapshot: '六年级 1 班',
    classId: null,
    subject: '数学',
    teacherName: '雷文浩',
    teacherNameSnapshot: '雷文浩',
    teacherUserId: null,
    mappingStatus: 'mapped',
    createdAt: '2026-03-29T08:00:00Z',
    analysis: {
      questionCategory: '计算',
      errorType: '计算错误',
      knowledgePoints: ['分数运算'],
    },
  };
  const detailRecord: WrongQuestionRecord = {
    ...listRecord,
    analysis: {
      ...listRecord.analysis,
      selectedErrorType: '审题错误',
      selectedKnowledgePoints: ['分数运算', '单位换算'],
      selectedActions: ['重做同类题'],
      selectedReasons: ['单位遗漏'],
      studentNote: '需要复盘单位检查',
    },
  };

  const pristineDraft = buildWrongQuestionReviewDraft(listRecord);
  const hydratedDraft = hydrateWrongQuestionReviewDraftFromDetail(detailRecord, pristineDraft, false);
  const editedDraft = hydrateWrongQuestionReviewDraftFromDetail(
    detailRecord,
    {
      ...pristineDraft,
      studentNote: '老师已手动修改',
    },
    true,
  );

  assert.deepEqual(hydratedDraft, buildWrongQuestionReviewDraft(detailRecord));
  assert.deepEqual(editedDraft, {
    ...pristineDraft,
    studentNote: '老师已手动修改',
  });
});

test('buildWrongQuestionReviewDraft keeps cleared teacher review fields empty after save and reload', () => {
  const detailRecord: WrongQuestionRecord = {
    id: 'record-1',
    studentName: 'Alice',
    className: '六年级 1 班',
    classNameSnapshot: '六年级 1 班',
    classId: null,
    subject: '数学',
    teacherName: '雷文浩',
    teacherNameSnapshot: '雷文浩',
    teacherUserId: null,
    mappingStatus: 'mapped',
    createdAt: '2026-03-29T08:00:00Z',
    analysis: {
      questionCategory: '计算',
      errorType: '计算错误',
      knowledgePoints: ['分数运算', '单位换算'],
      selectedErrorType: '审题错误',
      selectedKnowledgePoints: ['单位换算'],
      selectedActions: ['重做同类题'],
      selectedReasons: ['单位遗漏'],
      studentNote: '需要复盘单位检查',
    },
  };

  const clearedRecord = applyWrongQuestionReviewDraft(detailRecord, {
    selectedErrorType: '   ',
    selectedKnowledgePoints: [],
    selectedActions: ['重做同类题'],
    selectedReasons: ['单位遗漏'],
    studentNote: '需要复盘单位检查',
  });

  const rebuiltDraft = buildWrongQuestionReviewDraft(clearedRecord);

  assert.equal(clearedRecord.analysis.errorType, '计算错误');
  assert.deepEqual(clearedRecord.analysis.knowledgePoints, ['分数运算', '单位换算']);
  assert.equal(clearedRecord.analysis.selectedErrorType, undefined);
  assert.equal(clearedRecord.analysis.selectedKnowledgePoints, undefined);
  assert.deepEqual(rebuiltDraft, {
    selectedErrorType: '',
    selectedKnowledgePoints: [],
    selectedActions: ['重做同类题'],
    selectedReasons: ['单位遗漏'],
    studentNote: '需要复盘单位检查',
  });
});

test('resolveSavedWrongQuestionRecord preserves explicit clears through optimistic and server-returned save paths', () => {
  const detailRecord: WrongQuestionRecord = {
    id: 'record-1',
    studentName: 'Alice',
    className: '六年级 1 班',
    classNameSnapshot: '六年级 1 班',
    classId: null,
    subject: '数学',
    teacherName: '雷文浩',
    teacherNameSnapshot: '雷文浩',
    teacherUserId: null,
    mappingStatus: 'mapped',
    createdAt: '2026-03-29T08:00:00Z',
    analysis: {
      questionCategory: '计算',
      errorType: '计算错误',
      knowledgePoints: ['分数运算', '单位换算'],
      selectedErrorType: '审题错误',
      selectedKnowledgePoints: ['单位换算'],
      selectedActions: ['重做同类题'],
      selectedReasons: ['单位遗漏'],
      studentNote: '需要复盘单位检查',
    },
  };
  const clearedDraft = {
    selectedErrorType: '   ',
    selectedKnowledgePoints: [],
    selectedActions: ['重做同类题'],
    selectedReasons: ['单位遗漏'],
    studentNote: '需要复盘单位检查',
  };

  const optimisticRecord = resolveSavedWrongQuestionRecord(detailRecord, clearedDraft);
  const serverRecord = resolveSavedWrongQuestionRecord(
    detailRecord,
    clearedDraft,
    {
      id: 'record-1',
      student_name: 'Alice',
      class_name: '六年级 1 班',
      subject: '数学',
      teacher_name: '雷文浩',
      created_at: '2026-03-29T08:00:00Z',
      analysis: {
        question_category: '计算',
        error_type: '计算错误',
        knowledge_points: ['分数运算', '单位换算'],
        selected_actions: ['重做同类题'],
        selected_reasons: ['单位遗漏'],
        student_note: '需要复盘单位检查',
      },
    },
  );

  assert.deepEqual(buildWrongQuestionReviewDraft(optimisticRecord), {
    selectedErrorType: '',
    selectedKnowledgePoints: [],
    selectedActions: ['重做同类题'],
    selectedReasons: ['单位遗漏'],
    studentNote: '需要复盘单位检查',
  });
  assert.deepEqual(buildWrongQuestionReviewDraft(serverRecord), {
    selectedErrorType: '',
    selectedKnowledgePoints: [],
    selectedActions: ['重做同类题'],
    selectedReasons: ['单位遗漏'],
    studentNote: '需要复盘单位检查',
  });
  assert.deepEqual(serverRecord, normalizeWrongQuestionRecord({
    id: 'record-1',
    student_name: 'Alice',
    class_name: '六年级 1 班',
    subject: '数学',
    teacher_name: '雷文浩',
    created_at: '2026-03-29T08:00:00Z',
    analysis: {
      question_category: '计算',
      error_type: '计算错误',
      knowledge_points: ['分数运算', '单位换算'],
      selected_actions: ['重做同类题'],
      selected_reasons: ['单位遗漏'],
      student_note: '需要复盘单位检查',
    },
  }));
});

test('SmartWrongQuestionsPage guards against stale list responses with a request version ref', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /useRef/);
  assert.match(pageSource, /const requestVersionRef = useRef\(0\);/);
  assert.match(pageSource, /const requestVersion = requestVersionRef\.current \+ 1;\s*requestVersionRef\.current = requestVersion;/);
  assert.match(pageSource, /if \(requestVersion !== requestVersionRef\.current\) \{\s*return;\s*\}/);
  assert.match(pageSource, /if \(requestVersion === requestVersionRef\.current\) \{\s*setLoading\(false\);\s*\}/);
});

test('SmartWrongQuestionsPage loads selected record detail into a review draft state', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /const \[detailLoading, setDetailLoading\] = useState\(false\);/);
  assert.match(pageSource, /const \[detailError, setDetailError\] = useState\(''\);/);
  assert.match(pageSource, /const \[reviewDraftByRecordId, setReviewDraftByRecordId\] = useState<Record<string, [^>]+>>\(\{\}\);/);
  assert.match(pageSource, /const \[reviewDraftDirtyByRecordId, setReviewDraftDirtyByRecordId\] = useState<Record<string, boolean>>\(\{\}\);/);
  assert.match(pageSource, /apiFetch<[^>]+>\(buildWrongQuestionDetailPath\([^)]+\)\)/);
  assert.match(pageSource, /setReviewDraftByRecordId\(\(current\) => \{/);
  assert.match(pageSource, /hydrateWrongQuestionReviewDraftFromDetail\(/);
  assert.match(pageSource, /selectedErrorType/);
  assert.match(pageSource, /selectedKnowledgePoints/);
  assert.match(pageSource, /selectedActions/);
  assert.match(pageSource, /selectedReasons/);
  assert.match(pageSource, /studentNote/);
});

test('SmartWrongQuestionsPage shows canonical identities, snapshots, and an unresolved mapping warning', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-identity-ui',
              student_name: 'Alice',
              class_display_name: '六年级 1 班',
              class_name_snapshot: '六年级一班（临时）',
              class_id: 42,
              subject: '数学',
              teacher_display_name: 'Kayn',
              teacher_name_snapshot: 'Kayn 老师（代课）',
              teacher_user_id: 7,
              mapping_status: 'needs_review',
              created_at: '2026-03-29T08:00:00Z',
              analysis: {
                question_category: '计算',
                error_type: '计算错误',
                knowledge_points: ['分数运算'],
              },
            },
          ],
          summary: {
            total_count: 1,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 1,
          },
        });
      }

      if (input === '/api/wrong-questions/record-identity-ui' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-identity-ui',
          student_name: 'Alice',
          class_display_name: '六年级 1 班',
          class_name_snapshot: '六年级一班（临时）',
          class_id: 42,
          subject: '数学',
          teacher_display_name: 'Kayn',
          teacher_name_snapshot: 'Kayn 老师（代课）',
          teacher_user_id: 7,
          mapping_status: 'needs_review',
          created_at: '2026-03-29T08:00:00Z',
          analysis: {
            question_category: '计算',
            error_type: '计算错误',
            knowledge_points: ['分数运算'],
          },
        });
      }

      throw new Error(`Unexpected fetch: ${String(input)}`);
    }) as typeof fetch;

    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        React.createElement(SmartWrongQuestionsPage, {
          currentUser: {
            display_name: '管理员',
            organization_name: '星润Starain',
          },
        }),
      );
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /主数据映射待处理/);
      assert.match(pageText, /老师：Kayn/);
      assert.match(pageText, /原始老师：Kayn 老师（代课）/);
      assert.match(pageText, /班级：六年级 1 班/);
      assert.match(pageText, /原始班级：六年级一班（临时）/);
    });
  } finally {
    if (root) {
      await act(async () => {
        root?.unmount();
      });
    }
    globalThis.fetch = originalFetch;
    domEnvironment.cleanup();
  }
});

test('SmartWrongQuestionsPage rebuilds empty review fields from a successful save response', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-1',
              student_name: 'Alice',
              class_name: '六年级 1 班',
              subject: '数学',
              teacher_name: '雷文浩',
              created_at: '2026-03-29T08:00:00Z',
              analysis: {
                question_category: '计算',
                error_type: '计算错误',
                knowledge_points: ['分数运算', '单位换算'],
                selected_actions: ['重做同类题'],
                selected_reasons: ['单位遗漏'],
                student_note: '需要复盘单位检查',
              },
            },
          ],
          summary: {
            total_count: 1,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 0,
          },
        });
      }

      if (input === '/api/wrong-questions/record-1' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-1',
          student_name: 'Alice',
          class_name: '六年级 1 班',
          subject: '数学',
          teacher_name: '雷文浩',
          created_at: '2026-03-29T08:00:00Z',
          analysis: {
            question_category: '计算',
            error_type: '计算错误',
            knowledge_points: ['分数运算', '单位换算'],
            selected_actions: ['重做同类题'],
            selected_reasons: ['单位遗漏'],
            student_note: '需要复盘单位检查',
          },
        });
      }

      if (input === '/api/wrong-questions/record-1/review' && init?.method === 'PUT') {
        return createJsonResponse({
          ok: true,
          record: {
            id: 'record-1',
            student_name: 'Alice',
            class_name: '六年级 1 班',
            subject: '数学',
            teacher_name: '雷文浩',
            created_at: '2026-03-29T08:00:00Z',
            analysis: {
              question_category: '计算',
              error_type: '计算错误',
              knowledge_points: ['分数运算', '单位换算'],
              selected_actions: ['重做同类题'],
              selected_reasons: ['单位遗漏'],
              student_note: '需要复盘单位检查',
            },
          },
        });
      }

      throw new Error(`Unexpected fetch: ${String(input)}`);
    }) as typeof fetch;

    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        React.createElement(SmartWrongQuestionsPage, {
          currentUser: {
            display_name: '管理员',
            organization_name: '星润Starain',
          },
        }),
      );
    });

    await waitForAssertion(() => {
      assert.equal(fetchCalls.length, 2);
      const selectedErrorTypeInput = domEnvironment.container.querySelector('input[placeholder="填写教师最终确认的错误类型"]') as HTMLInputElement | null;
      const selectedKnowledgePointsTextarea = domEnvironment.container.querySelector('textarea[placeholder="每行一个知识点"]') as HTMLTextAreaElement | null;

      assert.ok(selectedErrorTypeInput instanceof HTMLInputElement);
      assert.ok(selectedKnowledgePointsTextarea instanceof HTMLTextAreaElement);
      assert.equal(selectedErrorTypeInput.value, '');
      assert.equal(selectedKnowledgePointsTextarea.value, '');
    });

    const saveButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('保存教师复盘'));

    assert.ok(saveButton instanceof HTMLButtonElement);

    await act(async () => {
      saveButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      assert.equal(fetchCalls.length, 3);
      const saveCall = fetchCalls[2];
      assert.equal(saveCall?.input, '/api/wrong-questions/record-1/review');
      assert.equal(saveCall?.init?.method, 'PUT');

      const payload = JSON.parse(String(saveCall?.init?.body));
      assert.equal(payload.selectedErrorType, '');
      assert.deepEqual(payload.selectedKnowledgePoints, []);
      assert.deepEqual(payload.selectedActions, ['重做同类题']);
      assert.deepEqual(payload.selectedReasons, ['单位遗漏']);
      assert.equal(payload.studentNote, '需要复盘单位检查');
    });

    await act(async () => {
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const rebuiltSelectedErrorTypeInput = domEnvironment.container.querySelector('input[placeholder="填写教师最终确认的错误类型"]') as HTMLInputElement | null;
      const rebuiltSelectedKnowledgePointsTextarea = domEnvironment.container.querySelector('textarea[placeholder="每行一个知识点"]') as HTMLTextAreaElement | null;
      assert.ok(rebuiltSelectedErrorTypeInput instanceof HTMLInputElement);
      assert.ok(rebuiltSelectedKnowledgePointsTextarea instanceof HTMLTextAreaElement);
      assert.equal(rebuiltSelectedErrorTypeInput.value, '');
      assert.equal(rebuiltSelectedKnowledgePointsTextarea.value, '');
    });
  } finally {
    if (root) {
      await act(async () => {
        root?.unmount();
      });
    }
    globalThis.fetch = originalFetch;
    domEnvironment.cleanup();
  }
});

test('SmartWrongQuestionsPage reuses the current filter query for PDF export', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /const handleExportSummary = \(\) => \{/);
  assert.match(pageSource, /downloadWrongQuestionSummary\(filters\)/);
  assert.match(pageSource, /导出 PDF 汇总/);
});