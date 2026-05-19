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
  buildMemberStudentNotebookSummaries,
  buildWeeklyWrongQuestionActivitySummaryPath,
  buildWeeklyWrongQuestionFollowupArchivePath,
  buildWeeklyWrongQuestionFollowupMessagePath,
  buildWrongQuestionPracticePackCreatePath,
  buildWrongQuestionPracticePackDetailPath,
  buildWrongQuestionPracticePackDownloadPath,
  buildWeeklyWrongQuestionFollowupPracticeSheetBatchPath,
  buildWeeklyWrongQuestionFollowupPracticeSheetPath,
  buildWeeklyWrongQuestionFollowupsPath,
  buildWrongQuestionDetailPath,
  buildWrongQuestionQuery,
  buildWrongQuestionReviewDraft,
  buildWrongQuestionReviewPayload,
  buildWrongQuestionReviewPath,
  buildWrongQuestionTopicSummaries,
  filterWrongQuestionRecordsForMemberNotebook,
  getWrongQuestionSemanticModel,
  getWrongQuestionSourceLabel,
  hydrateWrongQuestionReviewDraftFromDetail,
  isDownstreamWrongQuestionRecord,
  isWechatMiniProgramWrongQuestionRecord,
  normalizeWeeklyWrongQuestionActivitySummaryResponse,
  normalizeWeeklyWrongQuestionFollowupResponse,
  normalizeWrongQuestionPracticePackJobResponse,
  normalizeWrongQuestionRecord,
  normalizeWrongQuestionListResponse,
  resolveSavedWrongQuestionRecord,
  summarizeWrongQuestionRecords,
  filterWrongQuestionRecordsByTopic,
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

function createDeferred<T>(): {
  promise: Promise<T>;
  reject: (reason?: unknown) => void;
  resolve: (value: T) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
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

function findLastFetchCall(
  calls: Array<{ input: RequestInfo | URL; init?: RequestInit }>,
  predicate: (call: { input: RequestInfo | URL; init?: RequestInit }) => boolean,
): { input: RequestInfo | URL; init?: RequestInit } | undefined {
  for (let index = calls.length - 1; index >= 0; index -= 1) {
    const call = calls[index];
    if (predicate(call)) {
      return call;
    }
  }

  return undefined;
}

function getNotebookClassSelect(container: ParentNode): HTMLSelectElement | null {
  const classSelects = Array.from(container.querySelectorAll('select[aria-label="班级"]'));
  const notebookClassSelect = classSelects[classSelects.length - 1];
  return notebookClassSelect instanceof HTMLSelectElement ? notebookClassSelect : null;
}

async function selectNotebookClass(container: ParentNode, classId: string): Promise<void> {
  const classSelect = getNotebookClassSelect(container);
  assert.ok(classSelect instanceof HTMLSelectElement);

  await act(async () => {
    classSelect.value = classId;
    classSelect.dispatchEvent(new Event('change', { bubbles: true }));
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
  });
}

function setDateInputValue(input: HTMLInputElement, value: string): void {
  const valueSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  valueSetter?.call(input, value);
}

async function openNotebookStudent(container: ParentNode, studentName: string): Promise<void> {
  await waitForAssertion(() => {
    const studentButton = Array.from(container.querySelectorAll('button')).find((button) => button.textContent?.includes(studentName));
    assert.ok(studentButton instanceof HTMLButtonElement);
  });

  const studentButton = Array.from(container.querySelectorAll('button')).find((button) => button.textContent?.includes(studentName));
  assert.ok(studentButton instanceof HTMLButtonElement);

  await act(async () => {
    studentButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
  });
}

function setupDomEnvironment(): {
  cleanup: () => void;
  container: HTMLDivElement;
} {
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    url: 'http://localhost/',
  });
  Object.defineProperty(dom.window.navigator, 'clipboard', {
    configurable: true,
    value: {
      writeText: async () => undefined,
    },
  });
  const restoreCallbacks = [
    setGlobalValue('window', dom.window),
    setGlobalValue('document', dom.window.document),
    setGlobalValue('navigator', dom.window.navigator),
    setGlobalValue('HTMLElement', dom.window.HTMLElement),
    setGlobalValue('HTMLButtonElement', dom.window.HTMLButtonElement),
    setGlobalValue('HTMLInputElement', dom.window.HTMLInputElement),
    setGlobalValue('HTMLSelectElement', dom.window.HTMLSelectElement),
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

function makeWrongQuestionRecord(overrides: Partial<WrongQuestionRecord>): WrongQuestionRecord {
  return {
    id: 'record-default',
    roomId: '',
    source: 'downstream',
    studentName: 'Alice',
    className: '六年级 1 班',
    classNameSnapshot: '六年级 1 班',
    classId: 101,
    subject: '数学',
    teacherName: '成员老师',
    teacherNameSnapshot: '成员老师',
    teacherUserId: 7,
    mappingStatus: 'mapped',
    createdAt: '2026-03-29T08:00:00Z',
    parentNote: '',
    teacherComment: '',
    reviewStatus: '',
    analysis: {
      questionCategory: '计算',
      errorType: '计算错误',
      knowledgePoints: ['分数运算'],
    },
    ...overrides,
  };
}

type SmartWrongQuestionFetchCall = { input: RequestInfo | URL; init?: RequestInit };

function makeNotebookApiRecord(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'notebook-record-a',
    source: 'wechat_mp',
    student_id: 501,
    student_name: 'Alice',
    class_display_name: '六年级 1 班',
    class_id: 42,
    subject: '数学',
    teacher_display_name: 'Kayn',
    teacher_user_id: 7,
    created_at: '2026-03-29T09:00:00Z',
    child_raw_reason_text: '我把乘法优先级看漏了',
    primary_error_type: '方法问题',
    secondary_error_summary: '步骤检查不完整',
    recognition_status: 'recognized',
    is_geometry: 0,
    question_text: '计算 $2+3\\\\times4$ 的结果。',
    question_text_source: 'ai',
    student_library_pdf_path: '/api/wechat/student-libraries/501',
    topic_category: '未分类',
    archive_status: 'active',
    status: 'pending',
    analysis: {
      question_category: '计算',
      error_type: '方法问题',
      knowledge_points: ['运算顺序'],
      student_note: '步骤检查不完整',
    },
    ...overrides,
  };
}

function createNotebookFetch(
  fetchCalls: SmartWrongQuestionFetchCall[],
  options: {
    record?: Record<string, unknown>;
    detailRecord?: Record<string, unknown>;
    detailResponse?: Response;
    saveResponse?: Response;
    pdfRefreshResponse?: Response;
    deleteResponse?: Response;
    practiceCreateResponse?: Response;
    practiceHistoryItems?: unknown[];
  } = {},
): typeof fetch {
  const record = options.record ?? makeNotebookApiRecord();
  const detailRecord = options.detailRecord ?? record;
  const recordId = String(record.id ?? 'notebook-record-a');
  const studentId = Number(record.student_id ?? 501);

  return (async (input: RequestInfo | URL, init?: RequestInit) => {
    fetchCalls.push({ input, init });

    if (input === '/api/classes') {
      return createJsonResponse([{ id: 42, name: '六年级 1 班', subject: '数学', teacher_user_id: 7 }]);
    }

    if (input === '/api/classes/42/students') {
      return createJsonResponse({
        students: [{ id: studentId, name: 'Alice' }],
      });
    }

    if (input === '/api/admin/users') {
      return createJsonResponse([{ id: 7, name: 'Kayn' }]);
    }

    if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
      return createJsonResponse({
        items: [record],
        summary: {
          total_count: 1,
          repeated_mistake_count: 0,
          high_priority_count: 0,
          pending_review_count: 1,
          unique_class_count: 1,
          unique_student_count: 1,
        },
      });
    }

    if (input === `/api/wrong-questions/${encodeURIComponent(recordId)}` && (!init?.method || init.method === 'GET')) {
      return options.detailResponse ?? createJsonResponse(detailRecord);
    }

    if (input === `/api/wrong-questions/${encodeURIComponent(recordId)}/review` && init?.method === 'PUT') {
      return options.saveResponse ?? createJsonResponse({ ok: true, record: detailRecord });
    }

    if (input === `/api/wrong-questions/${encodeURIComponent(recordId)}` && init?.method === 'DELETE') {
      return options.deleteResponse ?? createJsonResponse({ ok: true, deleted_record_id: recordId });
    }

    if (input === `/api/wrong-question-student-libraries/${encodeURIComponent(String(studentId))}/refresh` && init?.method === 'POST') {
      return options.pdfRefreshResponse ?? createJsonResponse({
        ok: true,
        student_id: studentId,
        student_library_pdf_path: `/api/wechat/student-libraries/${studentId}`,
      });
    }

    if (input === `/api/wrong-question-practice-sheets?student_id=${encodeURIComponent(String(studentId))}` && (!init?.method || init.method === 'GET')) {
      return createJsonResponse({ items: options.practiceHistoryItems ?? [], total: options.practiceHistoryItems?.length ?? 0 });
    }

    if (input === '/api/wrong-question-practice-sheets' && init?.method === 'POST') {
      return options.practiceCreateResponse ?? createJsonResponse({ id: 12, status: 'pending' }, 202);
    }

    throw new Error(`Unexpected fetch: ${String(input)}`);
  }) as typeof fetch;
}

async function renderNotebookForAlice(container: ParentNode, root: Root | null): Promise<void> {
  await act(async () => {
    root?.render(
      React.createElement(SmartWrongQuestionsPage, {
        currentUser: {
          display_name: '管理员',
          organization_name: '星润Starain',
          role: 'owner',
        },
      }),
    );
  });

  await selectNotebookClass(container, '42');
  await openNotebookStudent(container, 'Alice');
}

test('summarizeWrongQuestionRecords derives the overview card counts from loaded records', () => {
  const records: WrongQuestionRecord[] = [
    {
      id: 'record-1',
      roomId: '',
      source: 'downstream',
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
      parentNote: '',
      teacherComment: '',
      reviewStatus: '',
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
      roomId: '',
      source: 'downstream',
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
      parentNote: '',
      teacherComment: '',
      reviewStatus: '',
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
      roomId: '',
      source: 'downstream',
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
      parentNote: '',
      teacherComment: '',
      reviewStatus: '',
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
    uniqueClassCount: 3,
    uniqueStudentCount: 3,
  });
});

test('buildMemberStudentNotebookSummaries groups current-class records by student', () => {
  const summaries = buildMemberStudentNotebookSummaries([
    makeWrongQuestionRecord({ id: 'a', source: 'wechat_mp', classId: 101, className: '六年级 1 班', studentName: 'Alice', createdAt: '2026-03-29T08:00:00Z' }),
    makeWrongQuestionRecord({ id: 'b', source: 'wechat_mp', classId: 101, className: '六年级 1 班', studentName: 'Alice', createdAt: '2026-03-29T09:00:00Z', isMastered: true }),
    makeWrongQuestionRecord({ id: 'c', source: 'wechat_mp', classId: 101, className: '六年级 1 班', studentName: 'Bob', createdAt: '2026-03-29T07:00:00Z' }),
    makeWrongQuestionRecord({ id: 'd', classId: 202, className: '初一 2 班', studentName: 'Alice', createdAt: '2026-03-29T10:00:00Z' }),
  ], 101);

  assert.deepEqual(summaries, [
    {
      studentName: 'Alice',
      classId: 101,
      className: '六年级 1 班',
      totalCount: 2,
      pendingReviewCount: 1,
      hasTeacherFollowUp: true,
      latestCreatedAt: '2026-03-29T09:00:00Z',
    },
    {
      studentName: 'Bob',
      classId: 101,
      className: '六年级 1 班',
      totalCount: 1,
      pendingReviewCount: 1,
      hasTeacherFollowUp: false,
      latestCreatedAt: '2026-03-29T07:00:00Z',
    },
  ]);
});

test('filterWrongQuestionRecordsForMemberNotebook keeps only the selected class and student records in upload order for display', () => {
  const records = [
    makeWrongQuestionRecord({ id: 'a', classId: 101, studentName: 'Alice', createdAt: '2026-03-29T09:00:00Z' }),
    makeWrongQuestionRecord({ id: 'b', classId: 101, studentName: 'Bob', createdAt: '2026-03-29T08:00:00Z' }),
    makeWrongQuestionRecord({ id: 'c', classId: 101, studentName: 'Alice', createdAt: '2026-03-27T10:00:00Z' }),
    makeWrongQuestionRecord({ id: 'd', classId: 202, studentName: 'Alice', createdAt: '2026-03-29T10:00:00Z' }),
  ];

  assert.deepEqual(
    filterWrongQuestionRecordsForMemberNotebook(records, 101, 'Alice').map((item) => item.id),
    ['c', 'a'],
  );
});

test('topic helpers summarize and filter primary wrong question topics', () => {
  const records = [
    makeWrongQuestionRecord({ id: 'a', source: 'wechat_mp', classId: 101, studentName: 'Alice', topicCategory: '行程' }),
    makeWrongQuestionRecord({ id: 'b', source: 'wechat_mp', classId: 101, studentName: 'Alice', topicCategory: '周期问题' }),
    makeWrongQuestionRecord({ id: 'c', source: 'wechat_mp', classId: 101, studentName: 'Alice', topicCategory: '' }),
    makeWrongQuestionRecord({ id: 'd', source: 'wechat_mp', classId: 101, studentName: 'Bob', topicCategory: '行程' }),
  ];

  assert.deepEqual(buildWrongQuestionTopicSummaries(records.slice(0, 3)), [
    { topicCategory: '全部', count: 3 },
    { topicCategory: '未分类', count: 1 },
    { topicCategory: '行程', count: 1 },
    { topicCategory: '周期问题', count: 1 },
  ]);
  assert.deepEqual(filterWrongQuestionRecordsByTopic(records, '行程').map((item) => item.id), ['a', 'd']);
  assert.deepEqual(filterWrongQuestionRecordsByTopic(records, '未分类').map((item) => item.id), ['c']);
});

test('SmartWrongQuestionsPage wires primary topic summaries and topic category saving', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /buildWrongQuestionTopicSummaries/);
  assert.match(pageSource, /filterWrongQuestionRecordsByTopic/);
  assert.match(pageSource, /notebookTopicFilter/);
  assert.match(pageSource, /小学专题/);
  assert.match(pageSource, /\/api\/wrong-questions\/\$\{encodeURIComponent\(selectedRecord\.id\)\}\/topic-category/);
});

test('SmartWrongQuestionsPage wires weekly followup UI only into the web smart wrong question page', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /每周练习跟进/);
  assert.match(pageSource, /buildWeeklyWrongQuestionFollowupArchivePath/);
  assert.match(pageSource, /buildWeeklyWrongQuestionFollowupPracticeSheetPath/);
  assert.match(pageSource, /extractGeneratedWeeklyFollowupMessage/);
  assert.doesNotMatch(pageSource, /extractWeeklyFollowupItem/);
  assert.doesNotMatch(pageSource, /小程序老师端/);
});

test('SmartWrongQuestionsPage wires super owner weekly activity summary without strong ranking copy', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /本周数据总结/);
  assert.match(pageSource, /buildWeeklyWrongQuestionActivitySummaryPath/);
  assert.match(pageSource, /normalizeWeeklyWrongQuestionActivitySummaryResponse/);
  assert.match(pageSource, /currentUser\.role === 'super_owner'/);
  assert.match(pageSource, /本周活跃班级/);
  assert.match(pageSource, /本周活跃老师/);
  assert.match(pageSource, /本周活跃学生/);
  assert.doesNotMatch(pageSource, /第 1 名|榜首|冠军/);
});

test('buildWrongQuestionQuery serializes only non-empty trimmed filters', () => {
  assert.equal(
    buildWrongQuestionQuery({
      studentName: ' Alice ',
      className: ' 六年级 1 班 ',
      subject: ' 数学 ',
      teacherName: '',
      errorType: '  ',
    }),
    '?studentName=Alice&className=%E5%85%AD%E5%B9%B4%E7%BA%A7%201%20%E7%8F%AD&subject=%E6%95%B0%E5%AD%A6',
  );

  assert.equal(buildWrongQuestionQuery({ studentName: '   ' }), '');
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

test('record detail and review paths keep roomId when the downstream contract requires it', () => {
  assert.equal(
    buildWrongQuestionDetailPath('record-1', 'ROOM A/1'),
    '/api/wrong-questions/record-1?roomId=ROOM%20A%2F1',
  );

  assert.equal(
    buildWrongQuestionReviewPath('record-1', 'ROOM A/1'),
    '/api/wrong-questions/record-1/review?roomId=ROOM%20A%2F1',
  );
});

test('weekly followup path builders keep the feature web-only', () => {
  assert.equal(
    buildWeeklyWrongQuestionFollowupsPath(42, '2026-05-04'),
    '/api/wrong-question-followups/weekly?class_id=42&week_start=2026-05-04',
  );

  assert.equal(
    buildWeeklyWrongQuestionFollowupArchivePath(42, '2026-05-04'),
    '/api/wrong-question-followups/weekly/class-pdf-archive?class_id=42&week_start=2026-05-04',
  );
  assert.equal(
    buildWeeklyWrongQuestionFollowupMessagePath(),
    '/api/wrong-question-followups/weekly/messages',
  );
  assert.equal(
    buildWeeklyWrongQuestionFollowupPracticeSheetPath(),
    '/api/wrong-question-followups/weekly/practice-sheets',
  );
  assert.equal(
    buildWeeklyWrongQuestionFollowupPracticeSheetBatchPath(),
    '/api/wrong-question-followups/weekly/practice-sheets/batch',
  );
});

test('practice pack path builders target the new practice pack API', () => {
  assert.equal(
    buildWrongQuestionPracticePackCreatePath(),
    '/api/wrong-question-practice-packs',
  );
  assert.equal(
    buildWrongQuestionPracticePackDetailPath(42),
    '/api/wrong-question-practice-packs/42',
  );
  assert.equal(
    buildWrongQuestionPracticePackDownloadPath(42),
    '/api/wrong-question-practice-packs/42/download',
  );
});

test('normalizeWrongQuestionPracticePackJobResponse converts snake_case job fields to camelCase', () => {
  const normalized = normalizeWrongQuestionPracticePackJobResponse({
    reused: true,
    job: {
      id: 42,
      status: 'ready',
      mode: 'reason',
      target: '去分母漏乘',
      volume: 'intensive',
      requested_question_count: 56,
      download_url: '/api/wrong-question-practice-packs/pack-42/download',
      generation_error: '',
      students: [
        {
          student_id: 501,
          student_name_snapshot: '王睿博',
          status: 'ready',
          requested_question_count: 8,
          real_question_count: 5,
          variant_question_count: 3,
          pdf_path: '/tmp/student-501.pdf',
          generation_error: '',
        },
      ],
    },
  });

  assert.equal(normalized.reused, true);
  assert.equal(normalized.job?.id, 42);
  assert.equal(normalized.job?.mode, 'reason');
  assert.equal(normalized.job?.volume, 'intensive');
  assert.equal(normalized.job?.requestedQuestionCount, 56);
  assert.equal(normalized.job?.downloadUrl, '/api/wrong-question-practice-packs/pack-42/download');
  assert.deepEqual(normalized.job?.students[0], {
    studentId: 501,
    studentNameSnapshot: '王睿博',
    status: 'ready',
    requestedQuestionCount: 8,
    realQuestionCount: 5,
    variantQuestionCount: 3,
    pdfPath: '/tmp/student-501.pdf',
    generationError: '',
  });
});

test('weekly activity summary path builder supports optional organization filtering', () => {
  assert.equal(
    buildWeeklyWrongQuestionActivitySummaryPath('2026-05-04'),
    '/api/admin/wrong-question-activity-summary?week_start=2026-05-04',
  );
  assert.equal(
    buildWeeklyWrongQuestionActivitySummaryPath('2026-05-04', 12),
    '/api/admin/wrong-question-activity-summary?week_start=2026-05-04&organization_id=12',
  );
});

test('normalizeWeeklyWrongQuestionFollowupResponse preserves cached messages', () => {
  const payload = normalizeWeeklyWrongQuestionFollowupResponse({
    class_id: 42,
    class_name: '六年级 1 班',
    week_start_date: '2026-05-04',
    week_end_date: '2026-05-10',
    total: 1,
    items: [
      {
        student_id: 501,
        student_name: '王睿博',
        wrong_question_count: 3,
        topic_categories: ['计算', '应用题'],
        primary_error_types: ['审题遗漏'],
        student_library_pdf_url: '/api/wechat/student-libraries/501',
        message: {
          id: 7,
          message_text: '王睿博妈妈，我刚看了下孩子这周错题。',
          source_record_ids: ['record-a', 'record-b'],
          created_at: '2026-05-04T08:00:00Z',
          updated_at: '2026-05-04T08:30:00Z',
        },
      },
    ],
  });

  assert.equal(payload.items[0]?.studentName, '王睿博');
  assert.equal(payload.items[0]?.message?.messageText, '王睿博妈妈，我刚看了下孩子这周错题。');
  assert.equal(payload.items[0]?.studentLibraryPdfUrl, '/api/wechat/student-libraries/501');
});

test('normalizeWeeklyWrongQuestionFollowupResponse falls back for malformed numeric fields', () => {
  const payload = normalizeWeeklyWrongQuestionFollowupResponse({
    class_id: 'not-a-class',
    total: 'not-a-total',
    items: [
      {
        student_id: 'not-a-student',
        student_name: '王睿博',
        weekly_question_count: 'not-a-count',
        total_active_question_count: 'not-active-count',
        message: {
          id: 'not-a-message',
          message_text: '本周继续稳住计算步骤。',
        },
      },
    ],
  });

  assert.equal(payload.classId, 0);
  assert.equal(payload.total, 1);
  assert.equal(payload.items[0]?.studentId, 0);
  assert.equal(payload.items[0]?.weeklyQuestionCount, 0);
  assert.equal(payload.items[0]?.totalActiveQuestionCount, 0);
  assert.equal(payload.items[0]?.message?.id, 0);
});

test('normalizeWeeklyWrongQuestionActivitySummaryResponse preserves class teacher and student lists', () => {
  const normalized = normalizeWeeklyWrongQuestionActivitySummaryResponse({
    week_start: '2026-05-04',
    week_end: '2026-05-10',
    class_items: [
      {
        organization_id: 1,
        organization_name: '星润',
        class_id: 15,
        class_name: '五年级3班',
        weekly_question_count: 18,
        uploading_student_count: 6,
        latest_created_at: '2026-05-04 18:32:00',
      },
    ],
    teacher_items: [
      {
        organization_id: 1,
        organization_name: '星润',
        teacher_user_id: 9,
        teacher_name: '王老师',
        class_count: 2,
        weekly_question_count: 31,
        involved_student_count: 12,
        pending_followup_count: 5,
      },
    ],
    student_items: [
      {
        organization_id: 1,
        organization_name: '星润',
        class_id: 15,
        class_name: '七年级5班',
        student_id: 76,
        student_name: '王睿博',
        weekly_question_count: 7,
        total_question_count: 24,
        topic_categories: ['几何', '计算'],
        latest_created_at: '2026-05-04 18:32:00',
      },
    ],
  });

  assert.equal(normalized.weekStart, '2026-05-04');
  assert.equal(normalized.weekEnd, '2026-05-10');
  assert.equal(normalized.classItems[0]?.className, '五年级3班');
  assert.equal(normalized.classItems[0]?.uploadingStudentCount, 6);
  assert.equal(normalized.teacherItems[0]?.pendingFollowupCount, 5);
  assert.equal(normalized.studentItems[0]?.topicCategories.join('、'), '几何、计算');
});

test('normalizeWrongQuestionListResponse converts backend object payloads into page-ready camelCase records', () => {
  const normalized = normalizeWrongQuestionListResponse({
    items: [
      {
        id: 123,
        room_id: 'ROOM-1',
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
    roomId: 'ROOM-1',
    source: 'downstream',
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
    parentNote: '',
    teacherComment: '',
    reviewStatus: '',
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
    roomId: '',
    source: 'downstream',
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
    parentNote: '',
    teacherComment: '',
    reviewStatus: '',
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
    uniqueClassCount: 2,
    uniqueStudentCount: 2,
  });
});

test('normalizeWrongQuestionRecord preserves canonical and snapshot identities side by side', () => {
  const normalized = normalizeWrongQuestionRecord({
    id: 'record-identity-1',
    room_id: 'ROOM-identity-1',
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
    roomId: 'ROOM-identity-1',
    source: 'downstream',
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
    parentNote: '',
    teacherComment: '',
    reviewStatus: '',
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
    roomId: '',
    source: 'downstream',
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
    parentNote: '',
    teacherComment: '',
    reviewStatus: '',
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
    roomId: '',
    source: 'downstream',
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
    parentNote: '',
    teacherComment: '',
    reviewStatus: '',
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
    teacherComment: '',
    reviewStatus: '',
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
    teacherComment: '',
    reviewStatus: '',
  });
});

test('resolveSavedWrongQuestionRecord preserves explicit clears and current mapping identity when save returns a legacy record payload', () => {
  const detailRecord: WrongQuestionRecord = {
    id: 'record-1',
    roomId: '',
    source: 'downstream',
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
    parentNote: '',
    teacherComment: '',
    reviewStatus: '',
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
    teacherComment: '',
    reviewStatus: '',
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
    teacherComment: '',
    reviewStatus: '',
  });
  assert.deepEqual(buildWrongQuestionReviewDraft(serverRecord), {
    selectedErrorType: '',
    selectedKnowledgePoints: [],
    selectedActions: ['重做同类题'],
    selectedReasons: ['单位遗漏'],
    studentNote: '需要复盘单位检查',
    teacherComment: '',
    reviewStatus: '',
  });
  assert.equal(serverRecord.className, '六年级 1 班');
  assert.equal(serverRecord.classNameSnapshot, '六年级一班（临时）');
  assert.equal(serverRecord.classId, 42);
  assert.equal(serverRecord.teacherName, 'Kayn');
  assert.equal(serverRecord.teacherNameSnapshot, 'Kayn 老师（代课）');
  assert.equal(serverRecord.teacherUserId, 7);
  assert.equal(serverRecord.mappingStatus, 'needs_review');
});

test('normalizeWrongQuestionRecord keeps wechat mini-program review fields for local uploads', () => {
  const normalized = normalizeWrongQuestionRecord({
    id: 'wechat-record-1',
    source: 'wechat_mp',
    student_name: 'Alice',
    class_display_name: '六年级 1 班',
    subject: '数学',
    teacher_display_name: 'Kayn',
    created_at: '2026-03-29T08:00:00Z',
    image_url: 'https://cdn.example.com/local-question.png',
    child_raw_reason_text: '我把单位换算漏掉了',
    primary_error_type: '审题问题',
    secondary_error_summary: '孩子忽略了题目里的单位换算要求。',
    child_reason_core_issue: '没有把单位条件和计算步骤连起来检查。',
    child_reason_key_omission: '漏掉了题目里先换算单位的要求。',
    child_reason_next_step: '下次先圈出单位，再统一单位后列式。',
    archive_status: 'archived',
    analysis: {
      error_type: '审题问题',
      student_note: '孩子忽略了题目里的单位换算要求。',
    },
  });

  assert.equal(normalized.source, 'wechat_mp');
  assert.equal(normalized.childReasonText, '我把单位换算漏掉了');
  assert.equal(normalized.primaryErrorType, '审题问题');
  assert.equal(normalized.causeNote, '孩子忽略了题目里的单位换算要求。');
  assert.equal(normalized.reasonCoreIssue, '没有把单位条件和计算步骤连起来检查。');
  assert.equal(normalized.reasonKeyOmission, '漏掉了题目里先换算单位的要求。');
  assert.equal(normalized.reasonNextStep, '下次先圈出单位，再统一单位后列式。');
  assert.equal(normalized.isMastered, true);
  assert.equal(getWrongQuestionSourceLabel(normalized.source), '微信小程序');
  assert.equal(isWechatMiniProgramWrongQuestionRecord(normalized), true);
});

test('normalizeWrongQuestionRecord keeps local recognition fields', () => {
  const normalized = normalizeWrongQuestionRecord({
    id: 'wechat-record-2',
    source: 'wechat_mp',
    recognition_status: 'recognized',
    is_geometry: 0,
    question_text: '计算 2+3×4 的结果。',
    question_text_source: 'ai',
    student_library_pdf_path: '/api/wechat/student-libraries/1',
  });

  assert.equal(normalized.recognitionStatus, 'recognized');
  assert.equal(normalized.isGeometry, false);
  assert.equal(normalized.questionText, '计算 2+3×4 的结果。');
  assert.equal(normalized.studentLibraryPdfPath, '/api/wechat/student-libraries/1');
});

test('SmartWrongQuestionsPage guards against stale list responses with a request version ref', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /useRef/);
  assert.match(pageSource, /const requestVersionRef = useRef\(0\);/);
  assert.match(pageSource, /const requestVersion = requestVersionRef\.current \+ 1;\s*requestVersionRef\.current = requestVersion;/);
  assert.match(pageSource, /if \(requestVersion !== requestVersionRef\.current\) \{\s*return;\s*\}/);
  assert.match(pageSource, /if \(requestVersion === requestVersionRef\.current\) \{\s*setLoading\(false\);\s*\}/);
});

test('smart wrong question page shows wechat mini-program source badge and local review copy', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /selectedRecord\.source === 'wechat_mp'/);
  assert.match(pageSource, /微信小程序/);
  assert.match(pageSource, /孩子自述错因/);
  assert.match(pageSource, /问题归类/);
  assert.match(pageSource, /aria-label="问题归类"/);
  assert.match(pageSource, /补充备注/);
  assert.match(pageSource, /是否掌握/);
});

test('SmartWrongQuestionsPage loads selected record detail into a review draft state', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /const \[detailLoading, setDetailLoading\] = useState\(false\);/);
  assert.match(pageSource, /const \[detailError, setDetailError\] = useState\(''\);/);
  assert.match(pageSource, /const \[reviewDraftByRecordId, setReviewDraftByRecordId\] = useState<Record<string, [^>]+>>\(\{\}\);/);
  assert.match(pageSource, /const \[reviewDraftDirtyByRecordId, setReviewDraftDirtyByRecordId\] = useState<Record<string, boolean>>\(\{\}\);/);
  assert.match(pageSource, /buildWrongQuestionDetailPath\(selectedId, selectedRecordForDetail\?\.roomId\)/);
  assert.match(pageSource, /setReviewDraftByRecordId\(\(current\) => \{/);
  assert.match(pageSource, /hydrateWrongQuestionReviewDraftFromDetail\(/);
  assert.match(pageSource, /最终问题归类/);
  assert.match(pageSource, /核心知识点/);
  assert.match(pageSource, /后续练习建议/);
  assert.match(pageSource, /原因分析/);
  assert.match(pageSource, /教师备注/);
});

test('SmartWrongQuestionsPage source exposes editable question text for local non-geometry records', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /题目文本/);
  assert.match(pageSource, /填写可直接进入错题库 PDF 的题目文本/);
  assert.match(pageSource, /公式预览/);
  assert.match(pageSource, /公式片段用/);
  assert.match(pageSource, /预览 PDF/);
  assert.match(pageSource, /下载 PDF/);
  assert.match(pageSource, /selectedRecord\.source === 'wechat_mp'/);
});

test('SmartWrongQuestionsPage source exposes a hard delete action for local wechat records', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /删除本题/);
  assert.match(pageSource, /method:\s*'DELETE'/);
  assert.match(pageSource, /selectedRecord\.source === 'wechat_mp'/);
});

test('SmartWrongQuestionsPage shows canonical identities, snapshots, and an unresolved mapping warning', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (input === '/api/classes') {
        return createJsonResponse([{ id: 42, name: '六年级 1 班', subject: '数学' }]);
      }

      if (input === '/api/classes/42/students') {
        return createJsonResponse({
          students: [{ id: 1, name: 'Alice' }],
        });
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-identity-ui',
              room_id: 'ROOM-identity',
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

      if (input === '/api/wrong-questions/record-identity-ui?roomId=ROOM-identity' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-identity-ui',
          room_id: 'ROOM-identity',
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
            role: 'owner',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '42');
    await openNotebookStudent(domEnvironment.container, 'Alice');

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /老师与班级归属待确认/);
      assert.match(pageText, /请先在班级管理中确认负责班级；如果老师名称与系统成员姓名不一致，需要补充老师别名映射/);
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

      if (input === '/api/classes') {
        return createJsonResponse([{ id: 42, name: '六年级 1 班', subject: '数学' }]);
      }

      if (input === '/api/classes/42/students') {
        return createJsonResponse({
          students: [{ id: 1, name: 'Alice' }],
        });
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-1',
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 42,
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
          class_id: 42,
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
            role: 'owner',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '42');
    await openNotebookStudent(domEnvironment.container, 'Alice');

    await waitForAssertion(() => {
      assert.ok(fetchCalls.length >= 4);
      const selectedErrorTypeInput = domEnvironment.container.querySelector('select[aria-label="最终问题归类"]') as HTMLSelectElement | null;
      const selectedKnowledgePointsTextarea = domEnvironment.container.querySelector('textarea[placeholder="每行一个知识点"]') as HTMLTextAreaElement | null;

      assert.ok(selectedErrorTypeInput instanceof HTMLSelectElement);
      assert.ok(selectedKnowledgePointsTextarea instanceof HTMLTextAreaElement);
      assert.equal(selectedErrorTypeInput.value, '');
      assert.equal(selectedKnowledgePointsTextarea.value, '');
    });

    const saveButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('保存跟进记录'));

    assert.ok(saveButton instanceof HTMLButtonElement);

    await act(async () => {
      saveButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const saveCall = findLastFetchCall(fetchCalls, (call) => call.input === '/api/wrong-questions/record-1/review');
      assert.ok(saveCall);
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
      const rebuiltSelectedErrorTypeInput = domEnvironment.container.querySelector('select[aria-label="最终问题归类"]') as HTMLSelectElement | null;
      const rebuiltSelectedKnowledgePointsTextarea = domEnvironment.container.querySelector('textarea[placeholder="每行一个知识点"]') as HTMLTextAreaElement | null;
      assert.ok(rebuiltSelectedErrorTypeInput instanceof HTMLSelectElement);
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

test('SmartWrongQuestionsPage keeps unresolved mapping banner and snapshot identities after saving with a legacy response payload', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([{ id: 42, name: '六年级 1 班', subject: '数学' }]);
      }

      if (input === '/api/classes/42/students') {
        return createJsonResponse({
          students: [{ id: 1, name: 'Alice' }],
        });
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-save-legacy',
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
                knowledge_points: ['分数运算', '单位换算'],
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

      if (input === '/api/wrong-questions/record-save-legacy' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-save-legacy',
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
            knowledge_points: ['分数运算', '单位换算'],
          },
        });
      }

      if (input === '/api/wrong-questions/record-save-legacy/review' && init?.method === 'PUT') {
        return createJsonResponse({
          ok: true,
          record: {
            id: 'record-save-legacy',
            student_name: 'Alice',
            class_name: '六年级 1 班',
            subject: '数学',
            teacher_name: 'Kayn',
            created_at: '2026-03-29T08:00:00Z',
            analysis: {
              question_category: '计算',
              error_type: '计算错误',
              knowledge_points: ['分数运算', '单位换算'],
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
            role: 'owner',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '42');
    await openNotebookStudent(domEnvironment.container, 'Alice');

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /老师与班级归属待确认/);
      assert.match(pageText, /老师：Kayn/);
      assert.match(pageText, /原始老师：Kayn 老师（代课）/);
      assert.match(pageText, /原始班级：六年级一班（临时）/);
    });

    const saveButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('保存跟进记录'));

    assert.ok(saveButton instanceof HTMLButtonElement);

    await act(async () => {
      saveButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const saveCall = findLastFetchCall(fetchCalls, (call) => call.input === '/api/wrong-questions/record-save-legacy/review');
      assert.ok(saveCall);
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /老师与班级归属待确认/);
      assert.match(pageText, /老师：Kayn/);
      assert.match(pageText, /原始老师：Kayn 老师（代课）/);
      assert.match(pageText, /班级：六年级 1 班/);
      assert.match(pageText, /原始班级：六年级一班（临时）/);
      assert.doesNotMatch(pageText, /映射状态：/);
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

test('SmartWrongQuestionsPage lets teachers edit local non-geometry question text', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([{ id: 42, name: '六年级 1 班', subject: '数学' }]);
      }

      if (input === '/api/classes/42/students') {
        return createJsonResponse({
          students: [{ id: 1, name: 'Alice' }],
        });
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'wechat-record-edit',
              source: 'wechat_mp',
              student_id: 1,
              student_name: 'Alice',
              class_display_name: '六年级 1 班',
              class_id: 42,
              subject: '数学',
              teacher_display_name: 'Kayn',
              created_at: '2026-03-29T09:00:00Z',
              recognition_status: 'recognized',
              is_geometry: 0,
              question_text: '计算 $2+3\\\\times4$ 的结果。',
              question_text_source: 'ai',
              student_library_pdf_path: '/api/wechat/student-libraries/1',
              parent_note: '孩子订正后还是不会',
              teacher_comment: '',
              status: 'pending',
              analysis: {},
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

      if (input === '/api/wrong-questions/wechat-record-edit' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'wechat-record-edit',
          source: 'wechat_mp',
          student_id: 1,
          student_name: 'Alice',
          class_display_name: '六年级 1 班',
          class_id: 42,
          subject: '数学',
          teacher_display_name: 'Kayn',
          created_at: '2026-03-29T08:00:00Z',
          recognition_status: 'recognized',
          is_geometry: 0,
          question_text: '计算 $2+3\\\\times4$ 的结果。',
          question_text_source: 'ai',
          student_library_pdf_path: '/api/wechat/student-libraries/1',
          child_raw_reason_text: '我把乘法优先级看漏了',
          primary_error_type: '方法问题',
          secondary_error_summary: '孩子知道规则，但这道题没先算乘法。',
          archive_status: 'active',
          analysis: {
            error_type: '方法问题',
            student_note: '孩子知道规则，但这道题没先算乘法。',
          },
        });
      }

      if (input === '/api/wrong-questions/wechat-record-edit/review' && init?.method === 'PUT') {
        return createJsonResponse({
          ok: true,
          record: {
            id: 'wechat-record-edit',
            source: 'wechat_mp',
            student_id: 1,
            student_name: 'Alice',
            class_display_name: '六年级 1 班',
            subject: '数学',
            teacher_display_name: 'Kayn',
            created_at: '2026-03-29T08:00:00Z',
            recognition_status: 'recognized',
            is_geometry: 0,
            question_text: '老师修正后的题目文本：$2+3\\\\times4$',
            question_text_source: 'teacher',
            student_library_pdf_path: '/api/wechat/student-libraries/1',
            child_raw_reason_text: '我把乘法优先级看漏了',
            primary_error_type: '方法问题',
            secondary_error_summary: '孩子知道规则，但这道题没先算乘法。',
            archive_status: 'archived',
            analysis: {
              error_type: '方法问题',
              student_note: '孩子知道规则，但这道题没先算乘法。',
            },
          },
        });
      }

      if (input === '/api/wrong-question-student-libraries/1/refresh' && init?.method === 'POST') {
        return createJsonResponse({
          ok: true,
          student_id: 1,
          student_library_pdf_path: '/tmp/student-1.pdf',
          pdf_url: '/api/wechat/student-libraries/1',
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
            role: 'owner',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '42');
    await openNotebookStudent(domEnvironment.container, 'Alice');

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /题目文本/);
      assert.match(pageText, /公式预览/);
      assert.match(pageText, /预览 PDF/);
      assert.match(pageText, /下载 PDF/);
      assert.match(pageText, /重新生成 PDF/);
      assert.match(pageText, /孩子自述错因/);
      assert.match(pageText, /问题归类/);
      const textarea = domEnvironment.container.querySelector('textarea[placeholder="填写可直接进入错题库 PDF 的题目文本"]') as HTMLTextAreaElement | null;
      const errorTypeSelect = domEnvironment.container.querySelector('select[aria-label="问题归类"]') as HTMLSelectElement | null;
      const previewLink = Array.from(domEnvironment.container.querySelectorAll('a')).find((link) => link.textContent?.includes('预览 PDF')) ?? null;
      const downloadLink = Array.from(domEnvironment.container.querySelectorAll('a')).find((link) => link.textContent?.includes('下载 PDF')) ?? null;
      assert.ok(textarea instanceof HTMLTextAreaElement);
      assert.ok(errorTypeSelect instanceof HTMLSelectElement);
      assert.equal(errorTypeSelect.value, '方法问题');
      assert.equal(previewLink?.tagName, 'A');
      assert.equal(downloadLink?.tagName, 'A');
      assert.equal(previewLink?.getAttribute('href'), '/api/wechat/student-libraries/1?token=token-123');
      assert.equal(downloadLink?.getAttribute('href'), '/api/wechat/student-libraries/1?token=token-123');
      assert.equal(downloadLink?.getAttribute('download'), 'student-library.pdf');
      assert.equal(textarea.value, '计算 $2+3\\\\times4$ 的结果。');
      assert.ok(domEnvironment.container.querySelector('.xr-latex-preview .katex'));
    });

    const questionTextarea = domEnvironment.container.querySelector('textarea[placeholder="填写可直接进入错题库 PDF 的题目文本"]') as HTMLTextAreaElement | null;
    const errorTypeSelect = domEnvironment.container.querySelector('select[aria-label="问题归类"]') as HTMLSelectElement | null;
    const masteryCheckbox = domEnvironment.container.querySelector('input[type="checkbox"]') as HTMLInputElement | null;
    const saveButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('保存掌握情况'));
    const refreshPdfButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('重新生成 PDF'));

    assert.ok(questionTextarea instanceof HTMLTextAreaElement);
    assert.ok(errorTypeSelect instanceof HTMLSelectElement);
    assert.ok(masteryCheckbox instanceof HTMLInputElement);
    assert.ok(saveButton instanceof HTMLButtonElement);
    assert.ok(refreshPdfButton instanceof HTMLButtonElement);

    await act(async () => {
      refreshPdfButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const refreshCall = findLastFetchCall(fetchCalls, (call) => call.input === '/api/wrong-question-student-libraries/1/refresh');
      assert.ok(refreshCall);
      assert.equal(refreshCall.init?.method, 'POST');
      assert.match(domEnvironment.container.textContent || '', /PDF 已重新生成/);
    });

    await act(async () => {
      errorTypeSelect.value = '方法问题';
      errorTypeSelect.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const payload = buildWrongQuestionReviewPayload({
      selectedErrorType: '方法问题',
      selectedKnowledgePoints: [],
      selectedActions: [],
      selectedReasons: [],
      studentNote: '',
      teacherComment: '',
      reviewStatus: '',
      questionText: '老师修正后的题目文本：$2+3\\\\times4$',
      isMastered: true,
    });

    assert.equal(payload.question_text, '老师修正后的题目文本：$2+3\\\\times4$');
    assert.equal(payload.selectedErrorType, '方法问题');
    assert.equal(payload.is_mastered, true);

    await act(async () => {
      questionTextarea.value = '老师修正后的题目文本：$2+3\\\\times4$';
      questionTextarea.dispatchEvent(new Event('input', { bubbles: true }));
      questionTextarea.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      saveButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const saveCall = findLastFetchCall(fetchCalls, (call) => call.input === '/api/wrong-questions/wechat-record-edit/review');
      assert.ok(saveCall);
      const requestPayload = JSON.parse(String(saveCall?.init?.body));
      assert.equal(requestPayload.selectedErrorType, '方法问题');
      assert.equal(requestPayload.question_text, '老师修正后的题目文本：$2+3\\\\times4$');
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

test('SmartWrongQuestionsPage deletes a local wechat record and jumps to the next notebook question', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const originalConfirm = window.confirm;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    window.confirm = () => true;
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([{ id: 42, name: '六年级 1 班', subject: '数学' }]);
      }

      if (input === '/api/classes/42/students') {
        return createJsonResponse({
          students: [{ id: 1, name: 'Alice' }],
        });
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'wechat-delete-a',
              source: 'wechat_mp',
              student_name: 'Alice',
              class_display_name: '六年级 1 班',
              class_id: 42,
              subject: '数学',
              teacher_display_name: 'Kayn',
              created_at: '2026-03-29T08:00:00Z',
              recognition_status: 'recognized',
              is_geometry: 0,
              question_text: '第一题',
              question_text_source: 'ai',
              student_library_pdf_path: '/api/wechat/student-libraries/1',
              archive_status: 'active',
              analysis: {},
            },
            {
              id: 'wechat-delete-b',
              source: 'wechat_mp',
              student_name: 'Alice',
              class_display_name: '六年级 1 班',
              class_id: 42,
              subject: '数学',
              teacher_display_name: 'Kayn',
              created_at: '2026-03-29T09:00:00Z',
              recognition_status: 'recognized',
              is_geometry: 0,
              question_text: '第二题',
              question_text_source: 'ai',
              student_library_pdf_path: '/api/wechat/student-libraries/1',
              archive_status: 'active',
              analysis: {},
            },
          ],
          summary: {
            total_count: 2,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 2,
          },
        });
      }

      if (input === '/api/wrong-questions/wechat-delete-a' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'wechat-delete-a',
          source: 'wechat_mp',
          student_name: 'Alice',
          class_display_name: '六年级 1 班',
          class_id: 42,
          subject: '数学',
          teacher_display_name: 'Kayn',
          created_at: '2026-03-29T08:00:00Z',
          recognition_status: 'recognized',
          is_geometry: 0,
          question_text: '第一题',
          question_text_source: 'ai',
          student_library_pdf_path: '/api/wechat/student-libraries/1',
          child_raw_reason_text: '第一题原因',
          primary_error_type: '计算粗心',
          secondary_error_summary: '第一题备注',
          archive_status: 'active',
          analysis: {
            error_type: '计算粗心',
            student_note: '第一题备注',
          },
        });
      }

      if (input === '/api/wrong-questions/wechat-delete-b' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'wechat-delete-b',
          source: 'wechat_mp',
          student_name: 'Alice',
          class_display_name: '六年级 1 班',
          class_id: 42,
          subject: '数学',
          teacher_display_name: 'Kayn',
          created_at: '2026-03-29T09:00:00Z',
          recognition_status: 'recognized',
          is_geometry: 0,
          question_text: '第二题',
          question_text_source: 'ai',
          student_library_pdf_path: '/api/wechat/student-libraries/1',
          child_raw_reason_text: '第二题原因',
          primary_error_type: '方法错误',
          secondary_error_summary: '第二题备注',
          archive_status: 'active',
          analysis: {
            error_type: '方法错误',
            student_note: '第二题备注',
          },
        });
      }

      if (input === '/api/wrong-questions/wechat-delete-b' && init?.method === 'DELETE') {
        return createJsonResponse({
          ok: true,
          deleted_record_id: 'wechat-delete-b',
          student_id: 1,
          next_student_library_pdf_path: '/api/wechat/student-libraries/1',
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
            role: 'owner',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '42');
    await openNotebookStudent(domEnvironment.container, 'Alice');

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /第二题/);
      const deleteButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('删除本题'));
      assert.ok(deleteButton instanceof HTMLButtonElement);
    });

    const deleteButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('删除本题'));
    assert.ok(deleteButton instanceof HTMLButtonElement);

    await act(async () => {
      deleteButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const deleteCall = findLastFetchCall(fetchCalls, (call) => call.input === '/api/wrong-questions/wechat-delete-b' && call.init?.method === 'DELETE');
      assert.ok(deleteCall);
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /第一题/);
      assert.doesNotMatch(pageText, /第二题原因/);
    });
  } finally {
    window.confirm = originalConfirm;
    if (root) {
      await act(async () => {
        root?.unmount();
      });
    }
    globalThis.fetch = originalFetch;
    domEnvironment.cleanup();
  }
});

test('SmartWrongQuestionsPage accepts a top-level saved record response without losing unresolved mapping identity', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([{ id: 42, name: '六年级 1 班', subject: '数学' }]);
      }

      if (input === '/api/classes/42/students') {
        return createJsonResponse({
          students: [{ id: 1, name: 'Alice' }],
        });
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-save-top-level',
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
                knowledge_points: ['分数运算', '单位换算'],
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

      if (input === '/api/wrong-questions/record-save-top-level' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-save-top-level',
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
            knowledge_points: ['分数运算', '单位换算'],
          },
        });
      }

      if (input === '/api/wrong-questions/record-save-top-level/review' && init?.method === 'PUT') {
        return createJsonResponse({
          id: 'record-save-top-level',
          student_name: 'Alice',
          class_name: '六年级 1 班',
          subject: '数学',
          teacher_name: 'Kayn',
          created_at: '2026-03-29T08:00:00Z',
          analysis: {
            question_category: '计算',
            error_type: '计算错误',
            knowledge_points: ['分数运算', '单位换算'],
            selected_error_type: '服务端修正',
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
            role: 'owner',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '42');
    await openNotebookStudent(domEnvironment.container, 'Alice');

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /老师与班级归属待确认/);
      assert.match(pageText, /原始老师：Kayn 老师（代课）/);
      assert.match(pageText, /原始班级：六年级一班（临时）/);
    });

    const saveButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('保存跟进记录'));

    assert.ok(saveButton instanceof HTMLButtonElement);

    await act(async () => {
      saveButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const saveCall = findLastFetchCall(fetchCalls, (call) => call.input === '/api/wrong-questions/record-save-top-level/review');
      assert.ok(saveCall);
      const pageText = domEnvironment.container.textContent || '';
      const selectedErrorTypeInput = domEnvironment.container.querySelector('select[aria-label="最终问题归类"]') as HTMLSelectElement | null;
      assert.ok(selectedErrorTypeInput instanceof HTMLSelectElement);
      assert.equal(selectedErrorTypeInput.value, '服务端修正');
      assert.match(pageText, /老师与班级归属待确认/);
      assert.match(pageText, /老师：Kayn/);
      assert.match(pageText, /原始老师：Kayn 老师（代课）/);
      assert.match(pageText, /班级：六年级 1 班/);
      assert.match(pageText, /原始班级：六年级一班（临时）/);
      assert.doesNotMatch(pageText, /映射状态：/);
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

test('SmartWrongQuestionsPage loads teacher and class filter options as selects instead of free text inputs', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 11, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
          { id: 12, name: '初一 2 班', subject: '英语', grade: '初一', teacher_user_id: 9 },
        ]);
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([
          { id: 7, name: 'Kayn', org: '星润Starain', role: 'owner' },
          { id: 9, name: '雷文浩', org: '星润Starain', role: 'admin' },
        ]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-filter-options',
              student_name: 'Alice',
              class_name: '六年级 1 班',
              subject: '数学',
              teacher_name: 'Kayn',
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
            pending_review_count: 0,
          },
        });
      }

      if (input === '/api/wrong-questions/record-filter-options' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-filter-options',
          student_name: 'Alice',
          class_name: '六年级 1 班',
          subject: '数学',
          teacher_name: 'Kayn',
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
            display_name: 'Kayn',
            organization_name: '星润Starain',
            role: 'owner',
          },
        }),
      );
    });

    await waitForAssertion(() => {
      const teacherSelect = domEnvironment.container.querySelector('select[aria-label="老师"]') as HTMLSelectElement | null;
      const classSelect = domEnvironment.container.querySelector('select[aria-label="班级"]') as HTMLSelectElement | null;

      assert.ok(classSelect);
      assert.ok(teacherSelect);
      assert.equal(classSelect.tagName, 'SELECT');
      assert.equal(teacherSelect.tagName, 'SELECT');
      assert.equal(classSelect.options.length, 3);
      assert.equal(teacherSelect.options.length, 3);
      assert.equal(classSelect.options[1]?.textContent?.trim(), '六年级 1 班 · 数学');
      assert.equal(teacherSelect.options[1]?.textContent?.trim(), 'Kayn');
      assert.equal(fetchCalls[0]?.input, '/api/classes');
      assert.equal(fetchCalls[1]?.input, '/api/admin/users');
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

test('SmartWrongQuestionsPage hides teacher filter and avoids admin user fetches for members', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 11, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-member-scope',
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 11,
              subject: '数学',
              teacher_name: '成员老师',
              teacher_user_id: 7,
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

      if (input === '/api/wrong-questions/record-member-scope' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-member-scope',
          student_name: 'Alice',
          class_name: '六年级 1 班',
          class_id: 11,
          subject: '数学',
          teacher_name: '成员老师',
          teacher_user_id: 7,
          created_at: '2026-03-29T08:00:00Z',
          analysis: {
            question_category: '计算',
            error_type: '计算错误',
            knowledge_points: ['分数运算'],
          },
        });
      }

      if (input === '/api/admin/users') {
        throw new Error('Members should not request admin user options');
      }

      throw new Error(`Unexpected fetch: ${String(input)}`);
    }) as typeof fetch;

    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        React.createElement(SmartWrongQuestionsPage, {
          currentUser: {
            display_name: '成员老师',
            organization_name: '星润Starain',
            role: 'member',
          },
        }),
      );
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      const teacherSelect = domEnvironment.container.querySelector('select[aria-label="老师"]');
      const classSelect = domEnvironment.container.querySelector('select[aria-label="班级"]') as HTMLSelectElement | null;

      assert.ok(classSelect);
      assert.equal(teacherSelect, null);
      assert.equal(fetchCalls.some((call) => call.input === '/api/admin/users'), false);
      assert.match(pageText, /查看负责范围内的错题记录/);
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

test('SmartWrongQuestionsPage renders member student cards for the selected class', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 101, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-a',
              source: 'wechat_mp',
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: '成员老师',
              teacher_user_id: 7,
              created_at: '2026-03-29T09:00:00Z',
              parent_note: '第一题又错了',
              image_url: 'https://cdn.example.com/a.png',
              status: 'pending',
              analysis: {
                question_category: '计算',
                error_type: '计算错误',
                knowledge_points: ['分数运算'],
              },
            },
            {
              id: 'record-b',
              source: 'wechat_mp',
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: '成员老师',
              teacher_user_id: 7,
              created_at: '2026-03-29T08:00:00Z',
              parent_note: '第二题订正后还不会',
              status: 'reviewed',
              teacher_comment: '已讲解',
              analysis: {
                question_category: '应用题',
                error_type: '审题错误',
                knowledge_points: ['数量关系'],
              },
            },
            {
              id: 'record-c',
              source: 'wechat_mp',
              student_name: 'Bob',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: '成员老师',
              teacher_user_id: 7,
              created_at: '2026-03-29T07:00:00Z',
              parent_note: '第三题不会',
              status: 'pending',
              analysis: {
                question_category: '几何',
                error_type: '图形理解错误',
                knowledge_points: ['面积'],
              },
            },
          ],
          summary: {
            total_count: 3,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 2,
            unique_class_count: 1,
            unique_student_count: 2,
          },
        });
      }

      if (input === '/api/wrong-questions/record-a' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-a',
          source: 'wechat_mp',
          student_name: 'Alice',
          class_name: '六年级 1 班',
          class_id: 101,
          subject: '数学',
          teacher_name: '成员老师',
          teacher_user_id: 7,
          created_at: '2026-03-29T09:00:00Z',
          parent_note: '第一题又错了',
          image_url: 'https://cdn.example.com/a.png',
          status: 'pending',
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
            display_name: '成员老师',
            organization_name: '星润Starain',
            role: 'member',
          },
        }),
      );
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /学生错题本/);
      assert.match(pageText, /请选择班级查看学生错题本/);
      assert.doesNotMatch(pageText, /筛选与列表/);
    });

    const classSelect = domEnvironment.container.querySelector('select[aria-label="班级"]') as HTMLSelectElement | null;
    assert.ok(classSelect);

    await act(async () => {
      classSelect.value = '101';
      classSelect.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /Alice/);
      assert.match(pageText, /Bob/);
      assert.match(pageText, /2题/);
      assert.match(pageText, /1题/);
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

test('SmartWrongQuestionsPage renders class-based student notebooks for owner accounts while keeping staff controls', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 101, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
          { id: 102, name: '六年级 2 班', subject: '数学', grade: '六年级', teacher_user_id: 8 },
        ]);
      }

      if (input === '/api/classes/101/students') {
        return createJsonResponse({
          students: [
            { id: 1, name: 'Alice' },
            { id: 2, name: 'Bob' },
          ],
        });
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([
          { id: 7, name: 'Kayn' },
          { id: 8, name: 'Luna' },
        ]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'staff-record-a',
              source: 'wechat_mp',
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: 'Kayn',
              teacher_user_id: 7,
              created_at: '2026-03-29T09:00:00Z',
              status: 'pending',
              child_raw_reason_text: '第一题把符号抄错了',
              primary_error_type: '计算错误',
              analysis: {
                question_category: '计算',
                error_type: '计算错误',
                knowledge_points: ['分数运算'],
              },
            },
            {
              id: 'staff-record-b',
              source: 'wechat_mp',
              student_name: 'Bob',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: 'Kayn',
              teacher_user_id: 7,
              created_at: '2026-03-29T08:00:00Z',
              status: 'reviewed',
              archive_status: 'archived',
              child_raw_reason_text: '第二题没看清单位',
              primary_error_type: '审题错误',
              analysis: {
                question_category: '应用题',
                error_type: '审题错误',
                knowledge_points: ['单位换算'],
              },
            },
          ],
          summary: {
            total_count: 2,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 1,
            unique_class_count: 1,
            unique_student_count: 2,
          },
        });
      }

      if (input === '/api/wrong-questions/staff-record-a' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'staff-record-a',
          source: 'wechat_mp',
          student_name: 'Alice',
          class_name: '六年级 1 班',
          class_id: 101,
          subject: '数学',
          teacher_name: 'Kayn',
          teacher_user_id: 7,
          created_at: '2026-03-29T09:00:00Z',
          status: 'pending',
          child_raw_reason_text: '第一题把符号抄错了',
          primary_error_type: '计算错误',
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
            display_name: '机构负责人',
            organization_name: '星润Starain',
            role: 'owner',
          },
        }),
      );
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      const classSelect = getNotebookClassSelect(domEnvironment.container);
      const teacherSelect = domEnvironment.container.querySelector('select[aria-label="老师"]') as HTMLSelectElement | null;

      assert.ok(classSelect);
      assert.ok(teacherSelect);
      assert.match(pageText, /学生错题本/);
      assert.match(pageText, /未掌握/);
      assert.doesNotMatch(pageText, /筛选与列表/);
      assert.equal(fetchCalls.some((call) => call.input === '/api/admin/users'), true);
    });

    const classSelect = getNotebookClassSelect(domEnvironment.container);
    assert.ok(classSelect);

    await act(async () => {
      classSelect.value = '101';
      classSelect.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /Alice/);
      assert.match(pageText, /Bob/);
      assert.match(pageText, /1题/);
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

test('SmartWrongQuestionsPage loads weekly followup items from the web API for the selected class and week', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: SmartWrongQuestionFetchCall[] = [];
  const openedPaths: string[] = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    Object.defineProperty(domEnvironment.container.ownerDocument.defaultView, 'open', {
      configurable: true,
      value: (path: string) => {
        openedPaths.push(path);
        return null;
      },
    });
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 42, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
          { id: 43, name: '六年级 2 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/classes/42/students') {
        return createJsonResponse({
          students: [{ id: 501, name: '王睿博' }],
        });
      }

      if (input === '/api/classes/43/students') {
        return createJsonResponse({
          students: [{ id: 601, name: '李同学' }],
        });
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([{ id: 7, name: 'Kayn' }]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            makeNotebookApiRecord({
              id: 'weekly-record-a',
              student_id: 501,
              student_name: '王睿博',
              class_id: 42,
              class_display_name: '六年级 1 班',
              teacher_user_id: 7,
              teacher_display_name: 'Kayn',
            }),
          ],
          summary: {
            total_count: 1,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 1,
            unique_class_count: 1,
            unique_student_count: 1,
          },
        });
      }

      if (input === '/api/wrong-questions/weekly-record-a' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse(makeNotebookApiRecord({
          id: 'weekly-record-a',
          student_id: 501,
          student_name: '王睿博',
          class_id: 42,
          class_display_name: '六年级 1 班',
          teacher_user_id: 7,
          teacher_display_name: 'Kayn',
        }));
      }

      if (input === '/api/wrong-question-followups/weekly?class_id=42&week_start=2026-05-04') {
        return createJsonResponse({
          class_id: 42,
          class_name: '六年级 1 班',
          week_start_date: '2026-05-04',
          week_end_date: '2026-05-10',
          total: 1,
          items: [
            {
              student_id: 501,
              student_name: '王睿博',
              status: 'has_practice_sheet',
              practice_sheet: {
                id: 88,
                status: 'ready',
                question_count: 3,
                pdf_path: '/tmp/wrb.pdf',
                pdf_url: '/api/wrong-question-practice-sheets/88/pdf',
              },
              weekly_question_count: 3,
              total_active_question_count: 5,
              topic_categories: ['计算'],
              representative_reason_summaries: ['审题遗漏'],
              source_record_ids: ['weekly-record-a'],
              message: {
                id: 7,
                message_text: '王睿博妈妈，我刚看了下孩子这周错题。',
                source_record_ids: ['weekly-record-a'],
              },
            },
            {
              student_id: 502,
              student_name: '毛同学',
              status: 'needs_practice_sheet',
              weekly_question_count: 2,
              candidate_question_count: 2,
              recommended_category: '几何',
              recommendation_reason: '几何可练错题2道，且最近一周没有练过。',
              topic_categories: ['几何'],
              representative_reason_summaries: ['角度关系遗漏'],
              source_record_ids: ['weekly-record-b'],
              candidate_record_ids: ['weekly-record-b'],
              message: null,
            },
          ],
        });
      }

      if (typeof input === 'string' && input.startsWith('/api/wrong-question-followups/weekly?class_id=42&week_start=')) {
        return createJsonResponse({
          class_id: 42,
          class_name: '六年级 1 班',
          week_start_date: '2026-05-18',
          week_end_date: '2026-05-24',
          total: 2,
          items: [
            {
              student_id: 501,
              student_name: '王睿博',
              status: 'has_practice_sheet',
              practice_sheet: {
                id: 88,
                status: 'ready',
                question_count: 3,
                pdf_path: '/tmp/wrb.pdf',
                pdf_url: '/api/wrong-question-practice-sheets/88/pdf',
              },
              weekly_question_count: 3,
              total_active_question_count: 5,
              topic_categories: ['计算'],
              representative_reason_summaries: ['审题遗漏'],
              source_record_ids: ['weekly-record-a'],
              message: {
                id: 7,
                message_text: '王睿博妈妈，我刚看了下孩子这周错题。',
                source_record_ids: ['weekly-record-a'],
              },
            },
            {
              student_id: 502,
              student_name: '毛同学',
              status: 'needs_practice_sheet',
              weekly_question_count: 2,
              candidate_question_count: 2,
              recommended_category: '几何',
              recommendation_reason: '几何可练错题2道，且最近一周没有练过。',
              topic_categories: ['几何'],
              representative_reason_summaries: ['角度关系遗漏'],
              source_record_ids: ['weekly-record-b'],
              candidate_record_ids: ['weekly-record-b'],
              message: null,
            },
          ],
        });
      }

      if (input === '/api/wrong-question-practice-packs' && init?.method === 'POST') {
        return createJsonResponse({
          reused: false,
          job: {
            id: 42,
            status: 'ready',
            mode: 'reason',
            target: '去分母漏乘',
            volume: 'intensive',
            requested_question_count: 16,
            download_url: '/api/wrong-question-practice-packs/42/download',
            generation_error: '',
            students: [
              {
                student_id: 501,
                student_name_snapshot: '王睿博',
                status: 'ready',
                requested_question_count: 8,
                real_question_count: 5,
                variant_question_count: 3,
                pdf_path: '/tmp/student-501.pdf',
                generation_error: '',
              },
            ],
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
            display_name: '机构负责人',
            organization_name: '星润Starain',
            role: 'owner',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '42');

    await waitForAssertion(() => {
      const followupButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('每周练习跟进'));
      assert.ok(followupButton instanceof HTMLButtonElement);
    });

    const followupButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('每周练习跟进'));
    assert.ok(followupButton instanceof HTMLButtonElement);

    await act(async () => {
      followupButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const weekInput = domEnvironment.container.querySelector('input[aria-label="周次"]') as HTMLInputElement | null;
    assert.ok(weekInput instanceof HTMLInputElement);

    await act(async () => {
      setDateInputValue(weekInput, '2026-05-04');
      weekInput.dispatchEvent(new Event('input', { bubbles: true }));
      weekInput.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const loadButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('查看跟进清单'));
    assert.ok(loadButton instanceof HTMLButtonElement);

    await act(async () => {
      loadButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /网页智能错题/);
      assert.match(pageText, /让 AI 生成练习/);
      assert.match(pageText, /生成并下载一周练习包/);
      assert.doesNotMatch(pageText, /批量生成未生成学生练习/);
      assert.doesNotMatch(pageText, /下载本周练习合集/);
      assert.match(pageText, /王睿博妈妈，我刚看了下孩子这周错题。/);
      assert.ok(fetchCalls.some((call) => typeof call.input === 'string' && call.input.startsWith('/api/wrong-question-followups/weekly?class_id=42&week_start=')));
    });

    const modeSelect = domEnvironment.container.querySelector('select[aria-label="练习包模式"]') as HTMLSelectElement | null;
    const targetInput = domEnvironment.container.querySelector('input[aria-label="练习包方向"]') as HTMLInputElement | null;
    const volumeSelect = domEnvironment.container.querySelector('select[aria-label="练习包题量"]') as HTMLSelectElement | null;
    const generatePackButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('生成并下载一周练习包'));
    assert.ok(modeSelect instanceof HTMLSelectElement);
    assert.ok(targetInput instanceof HTMLInputElement);
    assert.ok(volumeSelect instanceof HTMLSelectElement);
    assert.ok(generatePackButton instanceof HTMLButtonElement);

    await act(async () => {
      modeSelect.value = 'reason';
      modeSelect.dispatchEvent(new Event('change', { bubbles: true }));
      setDateInputValue(targetInput, '去分母漏乘');
      targetInput.dispatchEvent(new Event('input', { bubbles: true }));
      targetInput.dispatchEvent(new Event('change', { bubbles: true }));
      volumeSelect.value = 'intensive';
      volumeSelect.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await act(async () => {
      generatePackButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const createCall = findLastFetchCall(fetchCalls, (call) => call.input === '/api/wrong-question-practice-packs' && call.init?.method === 'POST');
      assert.ok(createCall);
      assert.deepEqual(JSON.parse(String(createCall.init?.body)), {
        class_id: 42,
        mode: 'reason',
        target: '去分母漏乘',
        volume: 'intensive',
      });
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /练习包已生成，正在打开下载/);
      assert.match(pageText, /去分母漏乘/);
      assert.match(pageText, /ready/);
      assert.match(pageText, /16题/);
      assert.match(pageText, /下载练习包/);
      assert.deepEqual(openedPaths, ['/api/wrong-question-practice-packs/42/download?token=token-123']);
    });

    await selectNotebookClass(domEnvironment.container, '43');

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.doesNotMatch(pageText, /王睿博妈妈，我刚看了下孩子这周错题。/);
      assert.doesNotMatch(pageText, /重新生成话术/);
      assert.equal(fetchCalls.some((call) => call.input === '/api/wrong-question-followups/weekly/messages' && call.init?.method === 'POST'), false);
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

test('SmartWrongQuestionsPage ignores stale weekly followup list responses after class changes', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const firstFollowupResponse = createDeferred<Response>();
  let root: Root | null = null;

  try {
    globalThis.fetch = (async (input: RequestInfo | URL) => {
      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 42, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
          { id: 43, name: '六年级 2 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/classes/42/students') {
        return createJsonResponse({ students: [{ id: 501, name: '王睿博' }] });
      }

      if (input === '/api/classes/43/students') {
        return createJsonResponse({ students: [{ id: 601, name: '李同学' }] });
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([{ id: 7, name: 'Kayn' }]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [],
          summary: {
            total_count: 0,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 0,
            unique_class_count: 0,
            unique_student_count: 0,
          },
        });
      }

      if (typeof input === 'string' && input.startsWith('/api/wrong-question-followups/weekly?class_id=42&week_start=')) {
        return firstFollowupResponse.promise;
      }

      throw new Error(`Unexpected fetch: ${String(input)}`);
    }) as typeof fetch;

    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        React.createElement(SmartWrongQuestionsPage, {
          currentUser: {
            display_name: '机构负责人',
            organization_name: '星润Starain',
            role: 'owner',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '42');

    await waitForAssertion(() => {
      const followupButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('每周练习跟进'));
      assert.ok(followupButton instanceof HTMLButtonElement);
    });

    const followupButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('每周练习跟进'));
    assert.ok(followupButton instanceof HTMLButtonElement);

    await act(async () => {
      followupButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const loadButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('查看跟进清单'));
    assert.ok(loadButton instanceof HTMLButtonElement);

    await act(async () => {
      loadButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await selectNotebookClass(domEnvironment.container, '43');

    await act(async () => {
      firstFollowupResponse.resolve(createJsonResponse({
        class_id: 42,
        class_name: '六年级 1 班',
        total: 1,
        items: [
          {
            student_id: 501,
            student_name: '王睿博',
            status: 'needs_practice_sheet',
            candidate_question_count: 2,
            weekly_question_count: 2,
          },
        ],
      }));
      await firstFollowupResponse.promise;
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.doesNotMatch(pageText, /王睿博/);
      assert.doesNotMatch(pageText, /已加载 1 名学生/);
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

test('SmartWrongQuestionsPage ignores stale practice pack create responses after class changes', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const createPackResponse = createDeferred<Response>();
  const openedPaths: string[] = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    Object.defineProperty(domEnvironment.container.ownerDocument.defaultView, 'open', {
      configurable: true,
      value: (path: string) => {
        openedPaths.push(path);
        return null;
      },
    });
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 42, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
          { id: 43, name: '六年级 2 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/classes/42/students') {
        return createJsonResponse({ students: [{ id: 501, name: '王睿博' }] });
      }

      if (input === '/api/classes/43/students') {
        return createJsonResponse({ students: [{ id: 601, name: '李同学' }] });
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([{ id: 7, name: 'Kayn' }]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [],
          summary: {
            total_count: 0,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 0,
            unique_class_count: 0,
            unique_student_count: 0,
          },
        });
      }

      if (input === '/api/wrong-question-practice-packs' && init?.method === 'POST') {
        return createPackResponse.promise;
      }

      throw new Error(`Unexpected fetch: ${String(input)}`);
    }) as typeof fetch;

    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        React.createElement(SmartWrongQuestionsPage, {
          currentUser: {
            display_name: '机构负责人',
            organization_name: '星润Starain',
            role: 'owner',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '42');

    await waitForAssertion(() => {
      const followupButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('每周练习跟进'));
      assert.ok(followupButton instanceof HTMLButtonElement);
    });

    const followupButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('每周练习跟进'));
    assert.ok(followupButton instanceof HTMLButtonElement);

    await act(async () => {
      followupButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const targetInput = domEnvironment.container.querySelector('input[aria-label="练习包方向"]') as HTMLInputElement | null;
    const generatePackButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('生成并下载一周练习包'));
    assert.ok(targetInput instanceof HTMLInputElement);
    assert.ok(generatePackButton instanceof HTMLButtonElement);

    await act(async () => {
      setDateInputValue(targetInput, '去分母漏乘');
      targetInput.dispatchEvent(new Event('input', { bubbles: true }));
      targetInput.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await act(async () => {
      generatePackButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await act(async () => {
      const classSelect = getNotebookClassSelect(domEnvironment.container);
      assert.ok(classSelect instanceof HTMLSelectElement);
      classSelect.value = '43';
      classSelect.dispatchEvent(new Event('change', { bubbles: true }));
      createPackResponse.resolve(createJsonResponse({
        reused: false,
        job: {
          id: 42,
          status: 'ready',
          mode: 'reason',
          target: '去分母漏乘',
          volume: 'standard',
          requested_question_count: 10,
          download_url: '/api/wrong-question-practice-packs/42/download',
          students: [],
        },
      }));
      await createPackResponse.promise;
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.doesNotMatch(pageText, /练习包已生成，正在打开下载/);
      assert.doesNotMatch(pageText, /去分母漏乘/);
      assert.deepEqual(openedPaths, []);
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

test('SmartWrongQuestionsPage ignores stale practice pack refresh responses after class changes', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const refreshPackResponse = createDeferred<Response>();
  let root: Root | null = null;

  try {
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 42, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
          { id: 43, name: '六年级 2 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/classes/42/students') {
        return createJsonResponse({ students: [{ id: 501, name: '王睿博' }] });
      }

      if (input === '/api/classes/43/students') {
        return createJsonResponse({ students: [{ id: 601, name: '李同学' }] });
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([{ id: 7, name: 'Kayn' }]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [],
          summary: {
            total_count: 0,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 0,
            unique_class_count: 0,
            unique_student_count: 0,
          },
        });
      }

      if (input === '/api/wrong-question-practice-packs' && init?.method === 'POST') {
        return createJsonResponse({
          reused: false,
          job: {
            id: 42,
            status: 'processing',
            mode: 'reason',
            target: '去分母漏乘',
            volume: 'standard',
            requested_question_count: 10,
            students: [],
          },
        });
      }

      if (input === '/api/wrong-question-practice-packs/42') {
        return refreshPackResponse.promise;
      }

      throw new Error(`Unexpected fetch: ${String(input)}`);
    }) as typeof fetch;

    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        React.createElement(SmartWrongQuestionsPage, {
          currentUser: {
            display_name: '机构负责人',
            organization_name: '星润Starain',
            role: 'owner',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '42');

    await waitForAssertion(() => {
      const followupButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('每周练习跟进'));
      assert.ok(followupButton instanceof HTMLButtonElement);
    });

    const followupButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('每周练习跟进'));
    assert.ok(followupButton instanceof HTMLButtonElement);

    await act(async () => {
      followupButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const targetInput = domEnvironment.container.querySelector('input[aria-label="练习包方向"]') as HTMLInputElement | null;
    const generatePackButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('生成并下载一周练习包'));
    assert.ok(targetInput instanceof HTMLInputElement);
    assert.ok(generatePackButton instanceof HTMLButtonElement);

    await act(async () => {
      setDateInputValue(targetInput, '去分母漏乘');
      targetInput.dispatchEvent(new Event('input', { bubbles: true }));
      targetInput.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await act(async () => {
      generatePackButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /去分母漏乘/);
      assert.match(pageText, /processing/);
    });

    const refreshButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('刷新状态'));
    assert.ok(refreshButton instanceof HTMLButtonElement);

    await act(async () => {
      refreshButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await selectNotebookClass(domEnvironment.container, '43');

    await act(async () => {
      refreshPackResponse.resolve(createJsonResponse({
        job: {
          id: 42,
          status: 'ready',
          mode: 'reason',
          target: '去分母漏乘',
          volume: 'standard',
          requested_question_count: 10,
          download_url: '/api/wrong-question-practice-packs/42/download',
          students: [],
        },
      }));
      await refreshPackResponse.promise;
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.doesNotMatch(pageText, /练习包状态已刷新/);
      assert.doesNotMatch(pageText, /去分母漏乘/);
      assert.doesNotMatch(pageText, /下载练习包/);
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

test('SmartWrongQuestionsPage updates one weekly followup card after generating a message response', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: SmartWrongQuestionFetchCall[] = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 42, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/classes/42/students') {
        return createJsonResponse({
          students: [{ id: 501, name: '王睿博' }],
        });
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([{ id: 7, name: 'Kayn' }]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            makeNotebookApiRecord({
              id: 'weekly-record-a',
              student_id: 501,
              student_name: '王睿博',
              class_id: 42,
              class_display_name: '六年级 1 班',
              teacher_user_id: 7,
              teacher_display_name: 'Kayn',
            }),
          ],
          summary: {
            total_count: 1,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 1,
            unique_class_count: 1,
            unique_student_count: 1,
          },
        });
      }

      if (input === '/api/wrong-questions/weekly-record-a' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse(makeNotebookApiRecord({
          id: 'weekly-record-a',
          student_id: 501,
          student_name: '王睿博',
          class_id: 42,
          class_display_name: '六年级 1 班',
          teacher_user_id: 7,
          teacher_display_name: 'Kayn',
        }));
      }

      if (input === '/api/wrong-question-followups/weekly?class_id=42&week_start=2026-05-04') {
        return createJsonResponse({
          class_id: 42,
          class_name: '六年级 1 班',
          week_start_date: '2026-05-04',
          week_end_date: '2026-05-10',
          total: 1,
          items: [
            {
              student_id: 501,
              student_name: '王睿博',
              status: 'has_practice_sheet',
              practice_sheet: {
                id: 89,
                status: 'ready',
                question_count: 3,
                pdf_path: '/tmp/wrb-2.pdf',
                pdf_url: '/api/wrong-question-practice-sheets/89/pdf',
              },
              weekly_question_count: 3,
              total_active_question_count: 5,
              topic_categories: ['计算'],
              representative_reason_summaries: ['审题遗漏'],
              source_record_ids: ['weekly-record-a'],
              message: null,
            },
          ],
        });
      }

      if (typeof input === 'string' && input.startsWith('/api/wrong-question-followups/weekly?class_id=42&week_start=')) {
        return createJsonResponse({
          class_id: 42,
          class_name: '六年级 1 班',
          week_start_date: '2026-05-18',
          week_end_date: '2026-05-24',
          total: 1,
          items: [
            {
              student_id: 501,
              student_name: '王睿博',
              status: 'has_practice_sheet',
              practice_sheet: {
                id: 89,
                status: 'ready',
                question_count: 3,
                pdf_path: '/tmp/wrb-2.pdf',
                pdf_url: '/api/wrong-question-practice-sheets/89/pdf',
              },
              weekly_question_count: 3,
              total_active_question_count: 5,
              topic_categories: ['计算'],
              representative_reason_summaries: ['审题遗漏'],
              source_record_ids: ['weekly-record-a'],
              message: null,
            },
          ],
        });
      }

      if (input === '/api/wrong-question-followups/weekly/messages' && init?.method === 'POST') {
        return createJsonResponse({
          ok: true,
          message: {
            id: 8,
            message_text: '王睿博妈妈，这周我会重点盯一下计算步骤。',
            source_record_ids: [501, 'weekly-record-a'],
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
            display_name: '机构负责人',
            organization_name: '星润Starain',
            role: 'owner',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '42');

    await waitForAssertion(() => {
      const button = Array.from(domEnvironment.container.querySelectorAll('button')).find((candidate) => candidate.textContent?.includes('每周练习跟进'));
      assert.ok(button instanceof HTMLButtonElement);
    });

    const followupButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('每周练习跟进'));
    assert.ok(followupButton instanceof HTMLButtonElement);

    await act(async () => {
      followupButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const weekInput = domEnvironment.container.querySelector('input[aria-label="周次"]') as HTMLInputElement | null;
    assert.ok(weekInput instanceof HTMLInputElement);

    await act(async () => {
      setDateInputValue(weekInput, '2026-05-04');
      weekInput.dispatchEvent(new Event('input', { bubbles: true }));
      weekInput.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const loadButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('查看跟进清单'));
    assert.ok(loadButton instanceof HTMLButtonElement);

    await act(async () => {
      loadButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /生成话术/);
      assert.doesNotMatch(pageText, /王睿博妈妈，这周我会重点盯一下计算步骤。/);
    });

    const generateButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('生成话术'));
    assert.ok(generateButton instanceof HTMLButtonElement);

    await act(async () => {
      generateButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /王睿博妈妈，这周我会重点盯一下计算步骤。/);
      assert.ok(fetchCalls.some((call) => call.input === '/api/wrong-question-followups/weekly/messages' && call.init?.method === 'POST'));
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

test('SmartWrongQuestionsPage loads super owner weekly activity summary with organization filtering', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: SmartWrongQuestionFetchCall[] = [];
  const firstSummaryResponse = {
    promise: createJsonResponse({
      week_start: '2026-05-18',
      week_end: '2026-05-24',
      class_items: [],
      teacher_items: [],
      student_items: [],
    }),
  };
  const secondSummaryResponse = {
    promise: createJsonResponse({
      week_start: '2026-05-18',
      week_end: '2026-05-24',
      class_items: [
        {
          organization_id: 11,
          organization_name: '星润一号机构',
          class_id: 42,
          class_name: '六年级 1 班',
          weekly_question_count: 4,
          uploading_student_count: 2,
          latest_created_at: '2026-05-06T09:00:00Z',
        },
      ],
      teacher_items: [
        {
          organization_id: 11,
          organization_name: '星润一号机构',
          teacher_user_id: 7,
          teacher_name: 'Kayn',
          class_count: 1,
          weekly_question_count: 4,
          involved_student_count: 2,
          pending_followup_count: 3,
        },
      ],
      student_items: [
        {
          organization_id: 11,
          organization_name: '星润一号机构',
          class_id: 42,
          class_name: '六年级 1 班',
          student_id: 501,
          student_name: '王睿博',
          weekly_question_count: 3,
          total_question_count: 8,
          topic_categories: ['计算'],
          latest_created_at: '2026-05-06T09:00:00Z',
        },
      ],
    }),
  };
  let root: Root | null = null;

  try {
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([]);
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([]);
      }

      if (input === '/api/admin/organizations') {
        return createJsonResponse({
          items: [{ id: 11, name: '星润一号机构' }],
        });
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [],
          summary: {
            total_count: 0,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 0,
            unique_class_count: 0,
            unique_student_count: 0,
          },
        });
      }

      if (input === '/api/admin/wrong-question-activity-summary?week_start=2026-05-04') {
        return createJsonResponse({
          week_start: '2026-05-04',
          week_end: '2026-05-10',
          class_items: [],
          teacher_items: [],
          student_items: [],
        });
      }

      if (input === '/api/admin/wrong-question-activity-summary?week_start=2026-05-04&organization_id=11') {
        return createJsonResponse({
          week_start: '2026-05-04',
          week_end: '2026-05-10',
          class_items: [
            {
              organization_id: 11,
              organization_name: '星润一号机构',
              class_id: 42,
              class_name: '六年级 1 班',
              weekly_question_count: 4,
              uploading_student_count: 2,
              latest_created_at: '2026-05-06T09:00:00Z',
            },
          ],
          teacher_items: [
            {
              organization_id: 11,
              organization_name: '星润一号机构',
              teacher_user_id: 7,
              teacher_name: 'Kayn',
              class_count: 1,
              weekly_question_count: 4,
              involved_student_count: 2,
              pending_followup_count: 3,
            },
          ],
          student_items: [
            {
              organization_id: 11,
              organization_name: '星润一号机构',
              class_id: 42,
              class_name: '六年级 1 班',
              student_id: 501,
              student_name: '王睿博',
              weekly_question_count: 3,
              total_question_count: 8,
              topic_categories: ['计算'],
              latest_created_at: '2026-05-06T09:00:00Z',
            },
          ],
        });
      }

      if (typeof input === 'string' && input.startsWith('/api/admin/wrong-question-activity-summary?week_start=') && input.includes('organization_id=11')) {
        return createJsonResponse({
          week_start: '2026-05-18',
          week_end: '2026-05-24',
          class_items: [
            {
              organization_id: 11,
              organization_name: '星润一号机构',
              class_id: 42,
              class_name: '六年级 1 班',
              weekly_question_count: 4,
              uploading_student_count: 2,
              latest_created_at: '2026-05-06T09:00:00Z',
            },
          ],
          teacher_items: [
            {
              organization_id: 11,
              organization_name: '星润一号机构',
              teacher_user_id: 7,
              teacher_name: 'Kayn',
              class_count: 1,
              weekly_question_count: 4,
              involved_student_count: 2,
              pending_followup_count: 3,
            },
          ],
          student_items: [
            {
              organization_id: 11,
              organization_name: '星润一号机构',
              class_id: 42,
              class_name: '六年级 1 班',
              student_id: 501,
              student_name: '王睿博',
              weekly_question_count: 3,
              total_question_count: 8,
              topic_categories: ['计算'],
              latest_created_at: '2026-05-06T09:00:00Z',
            },
          ],
        });
      }

      if (typeof input === 'string' && input.startsWith('/api/admin/wrong-question-activity-summary?week_start=') && input.includes('organization_id=11')) {
        return createJsonResponse({
          week_start: '2026-05-18',
          week_end: '2026-05-24',
          class_items: [
            {
              organization_id: 11,
              organization_name: '星润一号机构',
              class_id: 42,
              class_name: '六年级 1 班',
              weekly_question_count: 4,
              uploading_student_count: 2,
              latest_created_at: '2026-05-06T09:00:00Z',
            },
          ],
          teacher_items: [
            {
              organization_id: 11,
              organization_name: '星润一号机构',
              teacher_user_id: 7,
              teacher_name: 'Kayn',
              class_count: 1,
              weekly_question_count: 4,
              involved_student_count: 2,
              pending_followup_count: 3,
            },
          ],
          student_items: [
            {
              organization_id: 11,
              organization_name: '星润一号机构',
              class_id: 42,
              class_name: '六年级 1 班',
              student_id: 501,
              student_name: '王睿博',
              weekly_question_count: 3,
              total_question_count: 8,
              topic_categories: ['计算'],
              latest_created_at: '2026-05-06T09:00:00Z',
            },
          ],
        });
      }

      if (typeof input === 'string' && input.startsWith('/api/admin/wrong-question-activity-summary?week_start=') && input.includes('organization_id=11')) {
        return createJsonResponse({
          week_start: '2026-05-18',
          week_end: '2026-05-24',
          class_items: [
            {
              organization_id: 11,
              organization_name: '星润一号机构',
              class_id: 42,
              class_name: '六年级 1 班',
              weekly_question_count: 4,
              uploading_student_count: 2,
              latest_created_at: '2026-05-06T09:00:00Z',
            },
          ],
          teacher_items: [
            {
              organization_id: 11,
              organization_name: '星润一号机构',
              teacher_user_id: 7,
              teacher_name: 'Kayn',
              class_count: 1,
              weekly_question_count: 4,
              involved_student_count: 2,
              pending_followup_count: 3,
            },
          ],
          student_items: [
            {
              organization_id: 11,
              organization_name: '星润一号机构',
              class_id: 42,
              class_name: '六年级 1 班',
              student_id: 501,
              student_name: '王睿博',
              weekly_question_count: 3,
              total_question_count: 8,
              topic_categories: ['计算'],
              latest_created_at: '2026-05-06T09:00:00Z',
            },
          ],
        });
      }

      if (typeof input === 'string' && input.startsWith('/api/admin/wrong-question-activity-summary?week_start=') && input.includes('organization_id=11')) {
        return secondSummaryResponse.promise;
      }

      if (typeof input === 'string' && input.startsWith('/api/admin/wrong-question-activity-summary?week_start=')) {
        return firstSummaryResponse.promise;
      }

      throw new Error(`Unexpected fetch: ${String(input)}`);
    }) as typeof fetch;

    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        React.createElement(SmartWrongQuestionsPage, {
          currentUser: {
            display_name: '超级管理员',
            organization_name: '星润Starain',
            role: 'super_owner',
          },
        }),
      );
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      assert.ok(fetchCalls.some((call) => call.input === '/api/admin/organizations'));
      const summaryButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('本周数据总结'));
      assert.ok(summaryButton instanceof HTMLButtonElement);
    });

    const summaryButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('本周数据总结'));
    assert.ok(summaryButton instanceof HTMLButtonElement);

    await act(async () => {
      summaryButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const weekInput = domEnvironment.container.querySelector('input[aria-label="数据总结周次"]') as HTMLInputElement | null;
    assert.ok(weekInput instanceof HTMLInputElement);

    await act(async () => {
      setDateInputValue(weekInput, '2026-05-04');
      weekInput.dispatchEvent(new Event('input', { bubbles: true }));
      weekInput.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const loadButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('加载总结'));
    assert.ok(loadButton instanceof HTMLButtonElement);

    await act(async () => {
      loadButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /本周暂无错题活跃数据/);
      assert.ok(fetchCalls.some((call) => typeof call.input === 'string' && call.input.startsWith('/api/admin/wrong-question-activity-summary?week_start=') && !call.input.includes('organization_id=')));
    });

    const organizationSelect = domEnvironment.container.querySelector('select[aria-label="机构"]') as HTMLSelectElement | null;
    assert.ok(organizationSelect instanceof HTMLSelectElement);

    await act(async () => {
      organizationSelect.value = '11';
      organizationSelect.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await act(async () => {
      loadButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /本周活跃班级/);
      assert.match(pageText, /六年级 1 班/);
      assert.match(pageText, /Kayn/);
      assert.match(pageText, /王睿博/);
      assert.doesNotMatch(pageText, /本周暂无错题活跃数据/);
      assert.ok(fetchCalls.some((call) => typeof call.input === 'string' && call.input.startsWith('/api/admin/wrong-question-activity-summary?week_start=') && call.input.includes('organization_id=11')));
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

test('SmartWrongQuestionsPage ignores stale weekly activity summary responses', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: SmartWrongQuestionFetchCall[] = [];
  const firstSummaryResponse = createDeferred<Response>();
  const secondSummaryResponse = createDeferred<Response>();
  let root: Root | null = null;

  try {
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([]);
      }

      if (input === '/api/admin/users') {
        return createJsonResponse([]);
      }

      if (input === '/api/admin/organizations') {
        return createJsonResponse({
          items: [{ id: 11, name: '星润一号机构' }],
        });
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [],
          summary: {
            total_count: 0,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 0,
            unique_class_count: 0,
            unique_student_count: 0,
          },
        });
      }

      if (input === '/api/admin/wrong-question-activity-summary?week_start=2026-05-04') {
        return firstSummaryResponse.promise;
      }

      if (input === '/api/admin/wrong-question-activity-summary?week_start=2026-05-04&organization_id=11') {
        return secondSummaryResponse.promise;
      }

      if (typeof input === 'string' && input.startsWith('/api/admin/wrong-question-activity-summary?week_start=') && input.includes('organization_id=11')) {
        return secondSummaryResponse.promise;
      }

      if (typeof input === 'string' && input.startsWith('/api/admin/wrong-question-activity-summary?week_start=')) {
        return createJsonResponse({
          week_start: '2026-05-18',
          week_end: '2026-05-24',
          class_items: [],
          teacher_items: [],
          student_items: [],
        });
      }

      throw new Error(`Unexpected fetch: ${String(input)}`);
    }) as typeof fetch;

    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        React.createElement(SmartWrongQuestionsPage, {
          currentUser: {
            display_name: '超级管理员',
            organization_name: '星润Starain',
            role: 'super_owner',
          },
        }),
      );
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const summaryButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('本周数据总结'));
      assert.ok(summaryButton instanceof HTMLButtonElement);
    });

    const summaryButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('本周数据总结'));
    assert.ok(summaryButton instanceof HTMLButtonElement);

    await act(async () => {
      summaryButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const weekInput = domEnvironment.container.querySelector('input[aria-label="数据总结周次"]') as HTMLInputElement | null;
    const organizationSelect = domEnvironment.container.querySelector('select[aria-label="机构"]') as HTMLSelectElement | null;
    const loadButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('加载总结'));
    assert.ok(weekInput instanceof HTMLInputElement);
    assert.ok(organizationSelect instanceof HTMLSelectElement);
    assert.ok(loadButton instanceof HTMLButtonElement);

    await waitForAssertion(() => {
      assert.ok(Array.from(organizationSelect.options).some((option) => option.value === '11'));
    });

    await act(async () => {
      setDateInputValue(weekInput, '2026-05-04');
      weekInput.dispatchEvent(new Event('input', { bubbles: true }));
      weekInput.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await act(async () => {
      loadButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      assert.ok(fetchCalls.some((call) => typeof call.input === 'string' && call.input.startsWith('/api/admin/wrong-question-activity-summary?week_start=') && !call.input.includes('organization_id=')));
    });

    await act(async () => {
      organizationSelect.value = '11';
      organizationSelect.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const currentLoadButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('加载总结'));
      assert.ok(currentLoadButton instanceof HTMLButtonElement);
      assert.equal(currentLoadButton.disabled, false);
    });

    const unlockedLoadButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('加载总结'));
    assert.ok(unlockedLoadButton instanceof HTMLButtonElement);

    await act(async () => {
      unlockedLoadButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      assert.ok(
        fetchCalls.some((call) => typeof call.input === 'string' && call.input.startsWith('/api/admin/wrong-question-activity-summary?week_start=') && call.input.includes('organization_id=11')),
        fetchCalls.map((call) => String(call.input)).join('\n'),
      );
    });

    await act(async () => {
      secondSummaryResponse.resolve(createJsonResponse({
        week_start: '2026-05-04',
        week_end: '2026-05-10',
        class_items: [
          {
            organization_id: 11,
            organization_name: '星润一号机构',
            class_id: 42,
            class_name: '新鲜班级',
            weekly_question_count: 5,
            uploading_student_count: 2,
            latest_created_at: '2026-05-12T09:00:00Z',
          },
        ],
        teacher_items: [],
        student_items: [],
      }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /新鲜班级/);
    });

    await act(async () => {
      firstSummaryResponse.resolve(createJsonResponse({
        week_start: '2026-05-04',
        week_end: '2026-05-10',
        class_items: [
          {
            organization_id: 0,
            organization_name: '过期机构',
            class_id: 99,
            class_name: '过期班级',
            weekly_question_count: 99,
            uploading_student_count: 9,
            latest_created_at: '2026-05-05T09:00:00Z',
          },
        ],
        teacher_items: [],
        student_items: [],
      }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /新鲜班级/);
      assert.doesNotMatch(pageText, /过期班级/);
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

test('SmartWrongQuestionsPage saves review content only for the selected member notebook record set', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const reviewRequests: Array<{ url: string; body: string }> = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 101, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-a',
              source: 'wechat_mp',
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: '成员老师',
              teacher_user_id: 7,
              created_at: '2026-03-29T09:00:00Z',
              parent_note: '第一题又错了',
              status: 'pending',
              analysis: {
                question_category: '计算',
                error_type: '计算错误',
                knowledge_points: ['分数运算'],
              },
            },
            {
              id: 'record-c',
              source: 'wechat_mp',
              student_name: 'Bob',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: '成员老师',
              teacher_user_id: 7,
              created_at: '2026-03-29T07:00:00Z',
              parent_note: '第三题不会',
              status: 'pending',
              analysis: {
                question_category: '几何',
                error_type: '图形理解错误',
                knowledge_points: ['面积'],
              },
            },
          ],
          summary: {
            total_count: 2,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 2,
            unique_class_count: 1,
            unique_student_count: 2,
          },
        });
      }

      if (input === '/api/wrong-questions/record-a' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-a',
          source: 'wechat_mp',
          student_name: 'Alice',
          class_name: '六年级 1 班',
          class_id: 101,
          subject: '数学',
          teacher_name: '成员老师',
          teacher_user_id: 7,
          created_at: '2026-03-29T09:00:00Z',
          parent_note: '第一题又错了',
          status: 'pending',
          analysis: {
            question_category: '计算',
            error_type: '计算错误',
            knowledge_points: ['分数运算'],
          },
        });
      }

      if (input === '/api/wrong-questions/record-c' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-c',
          source: 'wechat_mp',
          student_name: 'Bob',
          class_name: '六年级 1 班',
          class_id: 101,
          subject: '数学',
          teacher_name: '成员老师',
          teacher_user_id: 7,
          created_at: '2026-03-29T07:00:00Z',
          parent_note: '第三题不会',
          status: 'pending',
          analysis: {
            question_category: '几何',
            error_type: '图形理解错误',
            knowledge_points: ['面积'],
          },
        });
      }

      if (input === '/api/wrong-questions/record-a/review' && init?.method === 'PUT') {
        reviewRequests.push({ url: String(input), body: String(init.body ?? '') });
        return createJsonResponse({
          record: {
            id: 'record-a',
            source: 'wechat_mp',
            student_name: 'Alice',
            class_name: '六年级 1 班',
            class_id: 101,
            subject: '数学',
            teacher_name: '成员老师',
            teacher_user_id: 7,
            created_at: '2026-03-29T09:00:00Z',
            child_raw_reason_text: '我把单位换算漏掉了',
            primary_error_type: '审题问题',
            secondary_error_summary: '孩子忽略了题目里的单位换算要求。',
            archive_status: 'archived',
            analysis: {
              question_category: '计算',
              error_type: '审题问题',
              knowledge_points: ['分数运算'],
              student_note: '孩子忽略了题目里的单位换算要求。',
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
            display_name: '成员老师',
            organization_name: '星润Starain',
            role: 'member',
          },
        }),
      );
    });

    await waitForAssertion(() => {
      const classSelect = domEnvironment.container.querySelector('select[aria-label="班级"]') as HTMLSelectElement | null;
      assert.ok(classSelect);
    });

    const classSelect = domEnvironment.container.querySelector('select[aria-label="班级"]') as HTMLSelectElement | null;
    assert.ok(classSelect);

    await act(async () => {
      classSelect.value = '101';
      classSelect.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const aliceButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('Alice'));
      assert.ok(aliceButton instanceof HTMLButtonElement);
    });

    const aliceButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('Alice'));
    assert.ok(aliceButton instanceof HTMLButtonElement);

    await act(async () => {
      aliceButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const masteryCheckbox = domEnvironment.container.querySelector('input[type="checkbox"]') as HTMLInputElement | null;
      const saveButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('保存掌握情况'));
      assert.ok(masteryCheckbox instanceof HTMLInputElement);
      assert.ok(saveButton instanceof HTMLButtonElement);
    });

    const masteryCheckbox = domEnvironment.container.querySelector('input[type="checkbox"]') as HTMLInputElement;
    const saveButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('保存掌握情况')) as HTMLButtonElement;

    assert.ok(masteryCheckbox instanceof HTMLInputElement);
    assert.ok(saveButton instanceof HTMLButtonElement);

    const payload = buildWrongQuestionReviewPayload({
      selectedErrorType: '',
      selectedKnowledgePoints: [],
      selectedActions: [],
      selectedReasons: [],
      studentNote: '',
      teacherComment: '',
      reviewStatus: '',
      isMastered: true,
    });

    assert.equal(payload.is_mastered, true);
    assert.equal(reviewRequests.length, 0);
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

test('SmartWrongQuestionsPage opens a member notebook modal after clicking a student card', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 101, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-a',
              source: 'wechat_mp',
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: '成员老师',
              teacher_user_id: 7,
              created_at: '2026-03-29T09:00:00Z',
              parent_note: '第一题又错了',
              status: 'pending',
              analysis: {
                question_category: '计算',
                error_type: '计算错误',
                knowledge_points: ['分数运算'],
              },
            },
            {
              id: 'record-b',
              source: 'wechat_mp',
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: '成员老师',
              teacher_user_id: 7,
              created_at: '2026-03-27T09:00:00Z',
              archive_status: 'archived',
              parent_note: '第二题还是错',
              status: 'reviewed',
              analysis: {
                question_category: '应用题',
                error_type: '审题错误',
                knowledge_points: ['分数应用'],
              },
            },
          ],
          summary: {
            total_count: 2,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 1,
            unique_class_count: 1,
            unique_student_count: 1,
          },
        });
      }

      if (input === '/api/wrong-questions/record-a' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-a',
          source: 'wechat_mp',
          student_name: 'Alice',
          class_name: '六年级 1 班',
          class_id: 101,
          subject: '数学',
          teacher_name: '成员老师',
          teacher_user_id: 7,
          created_at: '2026-03-29T09:00:00Z',
          parent_note: '第一题又错了',
          status: 'pending',
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
            display_name: '成员老师',
            organization_name: '星润Starain',
            role: 'member',
          },
        }),
      );
    });

    const classSelect = domEnvironment.container.querySelector('select[aria-label="班级"]') as HTMLSelectElement | null;
    assert.ok(classSelect);

    await act(async () => {
      classSelect.value = '101';
      classSelect.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const aliceButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('Alice'));
    assert.ok(aliceButton instanceof HTMLButtonElement);

    await act(async () => {
      aliceButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /Alice 的错题库/);
      assert.match(pageText, /错题目录/);
      assert.match(pageText, /关闭错题库/);
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

test('SmartWrongQuestionsPage renders member notebook records as compact rows inside the modal', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 101, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-a',
              source: 'wechat_mp',
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: '成员老师',
              teacher_user_id: 7,
              created_at: '2026-03-29T09:00:00Z',
              parent_note: '第一题又错了',
              status: 'pending',
              analysis: {
                question_category: '计算',
                error_type: '计算错误',
                knowledge_points: ['分数运算'],
              },
            },
            {
              id: 'record-b',
              source: 'wechat_mp',
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: '成员老师',
              teacher_user_id: 7,
              created_at: '2026-03-27T09:00:00Z',
              parent_note: '第二题还是错',
              status: 'reviewed',
              analysis: {
                question_category: '应用题',
                error_type: '审题错误',
                knowledge_points: ['分数应用'],
              },
            },
          ],
          summary: {
            total_count: 2,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 1,
            unique_class_count: 1,
            unique_student_count: 1,
          },
        });
      }

      if (input === '/api/wrong-questions/record-a' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-a',
          source: 'wechat_mp',
          student_name: 'Alice',
          class_name: '六年级 1 班',
          class_id: 101,
          subject: '数学',
          teacher_name: '成员老师',
          teacher_user_id: 7,
          created_at: '2026-03-29T09:00:00Z',
          parent_note: '第一题又错了',
          status: 'pending',
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
            display_name: '成员老师',
            organization_name: '星润Starain',
            role: 'member',
          },
        }),
      );
    });

    const classSelect = domEnvironment.container.querySelector('select[aria-label="班级"]') as HTMLSelectElement | null;
    assert.ok(classSelect);

    await act(async () => {
      classSelect.value = '101';
      classSelect.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const aliceButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('Alice'));
    assert.ok(aliceButton instanceof HTMLButtonElement);

    await act(async () => {
      aliceButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      const questionButtons = Array.from(domEnvironment.container.querySelectorAll('button')).filter((button) => button.textContent?.includes('第 ') && button.textContent?.includes('2026-03-'));

      assert.match(pageText, /第 1 题/);
      assert.match(pageText, /第 2 题/);
      assert.match(pageText, /错题目录/);
      assert.match(pageText, /最新上传的题目排在最上方/);
      assert.match(pageText, /2026-03-27T09:00:00Z/);
      assert.match(pageText, /已掌握/);
      assert.equal(questionButtons[0]?.textContent?.includes('第 2 题'), true);
      assert.equal(questionButtons[0]?.textContent?.includes('2026-03-29T09:00:00Z'), true);
      assert.equal(questionButtons[1]?.textContent?.includes('第 1 题'), true);
      assert.equal(questionButtons[1]?.textContent?.includes('2026-03-27T09:00:00Z'), true);
      assert.doesNotMatch(pageText, /第二题还是错/);
      assert.doesNotMatch(pageText, /按上传时间倒序查看/);
      assert.doesNotMatch(pageText, /左侧是紧凑错题目录/);
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

test('SmartWrongQuestionsPage presents the modal detail pane like a notebook document', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 101, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-a',
              source: 'wechat_mp',
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '',
              teacher_name: '成员老师',
              teacher_user_id: 7,
              created_at: '2026-03-29T09:00:00Z',
              parent_note: '第一题又错了',
              question_text: '计算 2+3×4 的结果。',
              child_raw_reason_text: '我把乘法优先级看漏了',
              status: 'pending',
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
            unique_class_count: 1,
            unique_student_count: 1,
          },
        });
      }

      if (input === '/api/wrong-questions/record-a' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-a',
          source: 'wechat_mp',
          student_name: 'Alice',
          class_name: '六年级 1 班',
          class_id: 101,
          subject: '',
          teacher_name: '成员老师',
          teacher_user_id: 7,
          created_at: '2026-03-29T09:00:00Z',
          parent_note: '第一题又错了',
          question_text: '计算 2+3×4 的结果。',
          child_raw_reason_text: '我把乘法优先级看漏了',
          status: 'pending',
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
            display_name: '成员老师',
            organization_name: '星润Starain',
            role: 'member',
          },
        }),
      );
    });

    const classSelect = domEnvironment.container.querySelector('select[aria-label="班级"]') as HTMLSelectElement | null;
    assert.ok(classSelect);

    await act(async () => {
      classSelect.value = '101';
      classSelect.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const aliceButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('Alice'));
    assert.ok(aliceButton instanceof HTMLButtonElement);

    await act(async () => {
      aliceButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /错题详情/);
      assert.match(pageText, /题目文本/);
      assert.match(pageText, /孩子自述错因/);
      assert.ok(pageText.indexOf('题目文本') < pageText.indexOf('孩子自述错因'));
      assert.doesNotMatch(pageText, /孩子上传记录/);
      assert.doesNotMatch(pageText, /错题档案/);
      assert.doesNotMatch(pageText, /映射状态：/);
      assert.doesNotMatch(pageText, /未标注科目/);
      assert.doesNotMatch(pageText, /题目记录/);
      assert.doesNotMatch(pageText, /教师跟进区/);
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

test('SmartWrongQuestionsPage member notebook keeps wechat records on error-cause semantics only', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL) => {
      if (input === '/api/classes') {
        return createJsonResponse([
          {
            id: 101,
            name: '六年级 1 班',
            subject: '数学',
          },
        ]);
      }

      if (typeof input === 'string' && input.startsWith('/api/wrong-questions')) {
        return createJsonResponse({
          items: [
            {
              id: 'member-wechat-record-1',
              source: 'wechat_mp',
              student_name: 'Alice',
              class_display_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_display_name: '成员老师',
              created_at: '2026-03-29T08:00:00Z',
              recognition_status: 'recognized',
              is_geometry: 0,
              question_text: '计算 2+3×4 的结果。',
              child_raw_reason_text: '我把乘法优先级看漏了',
              primary_error_type: '方法问题',
              secondary_error_summary: '孩子知道规则，但这道题没先算乘法。',
              archive_status: 'active',
              analysis: {
                question_category: '计算',
                error_type: '方法问题',
                knowledge_points: ['运算顺序'],
                is_repeated_mistake: '是',
                student_note: '孩子知道规则，但这道题没先算乘法。',
              },
            },
          ],
          summary: {
            total_count: 1,
            repeated_mistake_count: 1,
            high_priority_count: 0,
            pending_review_count: 1,
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
            display_name: '成员老师',
            organization_name: '星润Starain',
            role: 'member',
          },
        }),
      );
    });

    const classSelect = domEnvironment.container.querySelector('select[aria-label="班级"]') as HTMLSelectElement | null;
    assert.ok(classSelect);

    await act(async () => {
      classSelect.value = '101';
      classSelect.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const aliceButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('Alice'));
    assert.ok(aliceButton instanceof HTMLButtonElement);

    await act(async () => {
      aliceButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /孩子自述错因/);
      assert.match(pageText, /问题归类/);
      assert.match(pageText, /补充备注/);
      assert.match(pageText, /是否掌握/);
      assert.doesNotMatch(pageText, /重复错题/);
      assert.doesNotMatch(pageText, /核心知识点/);
      assert.doesNotMatch(pageText, /后续练习建议/);
      assert.doesNotMatch(pageText, /原因分析/);
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

test('SmartWrongQuestionsPage creates a wrong-question practice sheet from selected notebook records', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 101, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-a',
              source: 'wechat_mp',
              student_id: 501,
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: '成员老师',
              teacher_user_id: 7,
              created_at: '2026-03-29T09:00:00Z',
              child_raw_reason_text: '我把乘法优先级看漏了',
              primary_error_type: '细节问题',
              secondary_error_summary: '步骤检查不完整',
              recognition_status: 'recognized',
              is_geometry: 0,
              question_text: '计算 $2+3\\times4$ 的结果。',
              archive_status: 'active',
              status: 'pending',
              analysis: {
                question_category: '计算',
                error_type: '细节问题',
                knowledge_points: ['运算顺序'],
              },
            },
          ],
          summary: {
            total_count: 1,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 1,
            unique_class_count: 1,
            unique_student_count: 1,
          },
        });
      }

      if (input === '/api/wrong-questions/record-a' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-a',
          source: 'wechat_mp',
          student_id: 501,
          student_name: 'Alice',
          class_name: '六年级 1 班',
          class_id: 101,
          subject: '数学',
          teacher_name: '成员老师',
          teacher_user_id: 7,
          created_at: '2026-03-29T09:00:00Z',
          child_raw_reason_text: '我把乘法优先级看漏了',
          primary_error_type: '细节问题',
          secondary_error_summary: '步骤检查不完整',
          recognition_status: 'recognized',
          is_geometry: 0,
          question_text: '计算 $2+3\\times4$ 的结果。',
          archive_status: 'active',
          status: 'pending',
          analysis: {
            question_category: '计算',
            error_type: '细节问题',
            knowledge_points: ['运算顺序'],
          },
        });
      }

      if (input === '/api/wrong-question-practice-sheets?student_id=501' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({ items: [], total: 0 });
      }

      if (input === '/api/wrong-question-practice-sheets' && init?.method === 'POST') {
        return createJsonResponse({ id: 12, status: 'pending' }, 202);
      }

      throw new Error(`Unexpected fetch: ${String(input)}`);
    }) as typeof fetch;

    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        React.createElement(SmartWrongQuestionsPage, {
          currentUser: {
            display_name: '成员老师',
            organization_name: '星润Starain',
            role: 'member',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '101');
    await openNotebookStudent(domEnvironment.container, 'Alice');

    await waitForAssertion(() => {
      const checkbox = domEnvironment.container.querySelector('input[aria-label="选择第 1 题"]');
      assert.ok(checkbox instanceof HTMLInputElement);
    });

    const checkbox = domEnvironment.container.querySelector('input[aria-label="选择第 1 题"]') as HTMLInputElement | null;
    assert.ok(checkbox instanceof HTMLInputElement);

    await act(async () => {
      checkbox.checked = true;
      checkbox.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const generateButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('生成错题练习'));
    assert.ok(generateButton instanceof HTMLButtonElement);

    await act(async () => {
      generateButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    const practiceCreateCall = findLastFetchCall(
      fetchCalls,
      (call) => call.input === '/api/wrong-question-practice-sheets' && call.init?.method === 'POST',
    );
    assert.ok(practiceCreateCall);
    assert.equal(practiceCreateCall?.init?.body, JSON.stringify({
      student_id: 501,
      wrong_question_ids: ['record-a'],
    }));
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

test('SmartWrongQuestionsPage shows wrong-question practice history inside the notebook modal', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 101, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-a',
              source: 'wechat_mp',
              student_id: 501,
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: '成员老师',
              teacher_user_id: 7,
              created_at: '2026-03-29T09:00:00Z',
              child_raw_reason_text: '我把乘法优先级看漏了',
              primary_error_type: '细节问题',
              secondary_error_summary: '步骤检查不完整',
              recognition_status: 'recognized',
              is_geometry: 0,
              question_text: '计算 $2+3\\times4$ 的结果。',
              archive_status: 'active',
              status: 'pending',
              analysis: {
                question_category: '计算',
                error_type: '细节问题',
                knowledge_points: ['运算顺序'],
              },
            },
          ],
          summary: {
            total_count: 1,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 1,
            unique_class_count: 1,
            unique_student_count: 1,
          },
        });
      }

      if (input === '/api/wrong-questions/record-a' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-a',
          source: 'wechat_mp',
          student_id: 501,
          student_name: 'Alice',
          class_name: '六年级 1 班',
          class_id: 101,
          subject: '数学',
          teacher_name: '成员老师',
          teacher_user_id: 7,
          created_at: '2026-03-29T09:00:00Z',
          child_raw_reason_text: '我把乘法优先级看漏了',
          primary_error_type: '细节问题',
          secondary_error_summary: '步骤检查不完整',
          recognition_status: 'recognized',
          is_geometry: 0,
          question_text: '计算 $2+3\\times4$ 的结果。',
          archive_status: 'active',
          status: 'pending',
          analysis: {
            question_category: '计算',
            error_type: '细节问题',
            knowledge_points: ['运算顺序'],
          },
        });
      }

      if (input === '/api/wrong-question-practice-sheets?student_id=501' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          items: [
            {
              id: 12,
              student_id: 501,
              class_id: 101,
              student_name_snapshot: 'Alice',
              class_name_snapshot: '六年级 1 班',
              teacher_name_snapshot: '成员老师',
              question_count: 1,
              status: 'ready',
              pdf_url: '/api/wrong-question-practice-sheets/12/pdf',
              download_url: '/api/wrong-question-practice-sheets/12/pdf/download',
              created_at: '2026-04-20 10:00:00',
            },
          ],
          total: 1,
        });
      }

      throw new Error(`Unexpected fetch: ${String(input)}`);
    }) as typeof fetch;

    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        React.createElement(SmartWrongQuestionsPage, {
          currentUser: {
            display_name: '成员老师',
            organization_name: '星润Starain',
            role: 'member',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '101');
    await openNotebookStudent(domEnvironment.container, 'Alice');

    const historyTab = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('错题练习记录'));
    assert.ok(historyTab instanceof HTMLButtonElement);

    await act(async () => {
      historyTab.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /错题练习记录/);
      assert.match(pageText, /2026-04-20 10:00:00/);
      assert.match(pageText, /练习单 #1/);
      assert.match(pageText, /1题/);
      assert.match(pageText, /预览 PDF/);
      assert.match(pageText, /下载 PDF/);
      const downloadLink = Array.from(domEnvironment.container.querySelectorAll('a')).find((link) => link.textContent?.includes('下载 PDF')) ?? null;
      assert.equal(downloadLink?.tagName, 'A');
      assert.equal(downloadLink?.getAttribute('download'), null);
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

test('SmartWrongQuestionsPage deletes a wrong-question practice sheet from practice history', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const originalConfirm = window.confirm;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    window.confirm = () => true;
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([
          { id: 101, name: '六年级 1 班', subject: '数学', grade: '六年级', teacher_user_id: 7 },
        ]);
      }

      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            {
              id: 'record-a',
              source: 'wechat_mp',
              student_id: 501,
              student_name: 'Alice',
              class_name: '六年级 1 班',
              class_id: 101,
              subject: '数学',
              teacher_name: '成员老师',
              teacher_user_id: 7,
              created_at: '2026-03-29T09:00:00Z',
              child_raw_reason_text: '我把乘法优先级看漏了',
              primary_error_type: '细节问题',
              secondary_error_summary: '步骤检查不完整',
              recognition_status: 'recognized',
              is_geometry: 0,
              question_text: '计算 $2+3\\times4$ 的结果。',
              archive_status: 'active',
              status: 'pending',
              analysis: {
                question_category: '计算',
                error_type: '细节问题',
                knowledge_points: ['运算顺序'],
              },
            },
          ],
          summary: {
            total_count: 1,
            repeated_mistake_count: 0,
            high_priority_count: 0,
            pending_review_count: 1,
            unique_class_count: 1,
            unique_student_count: 1,
          },
        });
      }

      if (input === '/api/wrong-questions/record-a' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          id: 'record-a',
          source: 'wechat_mp',
          student_id: 501,
          student_name: 'Alice',
          class_name: '六年级 1 班',
          class_id: 101,
          subject: '数学',
          teacher_name: '成员老师',
          teacher_user_id: 7,
          created_at: '2026-03-29T09:00:00Z',
          child_raw_reason_text: '我把乘法优先级看漏了',
          primary_error_type: '细节问题',
          secondary_error_summary: '步骤检查不完整',
          recognition_status: 'recognized',
          is_geometry: 0,
          question_text: '计算 $2+3\\times4$ 的结果。',
          archive_status: 'active',
          status: 'pending',
          analysis: {
            question_category: '计算',
            error_type: '细节问题',
            knowledge_points: ['运算顺序'],
          },
        });
      }

      if (input === '/api/wrong-question-practice-sheets?student_id=501' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({
          items: [
            {
              id: 10,
              student_id: 501,
              class_id: 101,
              student_name_snapshot: 'Alice',
              class_name_snapshot: '六年级 1 班',
              teacher_name_snapshot: '成员老师',
              question_count: 2,
              status: 'ready',
              pdf_url: '/api/wrong-question-practice-sheets/10/pdf',
              download_url: '/api/wrong-question-practice-sheets/10/pdf/download',
              created_at: '2026-04-20 09:00:00',
            },
            {
              id: 12,
              student_id: 501,
              class_id: 101,
              student_name_snapshot: 'Alice',
              class_name_snapshot: '六年级 1 班',
              teacher_name_snapshot: '成员老师',
              question_count: 1,
              status: 'ready',
              pdf_url: '/api/wrong-question-practice-sheets/12/pdf',
              download_url: '/api/wrong-question-practice-sheets/12/pdf/download',
              created_at: '2026-04-20 10:00:00',
            },
          ],
          total: 1,
        });
      }

      if (input === '/api/wrong-question-practice-sheets/12' && init?.method === 'DELETE') {
        return createJsonResponse({
          ok: true,
          deleted_sheet_id: 12,
        });
      }

      throw new Error(`Unexpected fetch: ${String(input)}`);
    }) as typeof fetch;

    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        React.createElement(SmartWrongQuestionsPage, {
          currentUser: {
            display_name: '成员老师',
            organization_name: '星润Starain',
            role: 'member',
          },
        }),
      );
    });

    await selectNotebookClass(domEnvironment.container, '101');
    await openNotebookStudent(domEnvironment.container, 'Alice');

    const historyTab = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('错题练习记录'));
    assert.ok(historyTab instanceof HTMLButtonElement);

    await act(async () => {
      historyTab.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /练习单 #2/);
      assert.match(pageText, /练习单 #1/);
      assert.doesNotMatch(pageText, /练习单 #12|练习单 #10/);
      const deleteButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('删除练习'));
      assert.ok(deleteButton instanceof HTMLButtonElement);
    });

    const deleteButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('删除练习'));
    assert.ok(deleteButton instanceof HTMLButtonElement);

    await act(async () => {
      deleteButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const deleteCall = findLastFetchCall(fetchCalls, (call) => call.input === '/api/wrong-question-practice-sheets/12' && call.init?.method === 'DELETE');
      assert.ok(deleteCall);
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /练习单 #1/);
      assert.doesNotMatch(pageText, /练习单 #2|练习单 #12|练习单 #10/);
    });
  } finally {
    window.confirm = originalConfirm;
    if (root) {
      await act(async () => {
        root?.unmount();
      });
    }
    globalThis.fetch = originalFetch;
    domEnvironment.cleanup();
  }
});

test('SmartWrongQuestionsPage keeps notebook open and draft visible when detail loading fails', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: SmartWrongQuestionFetchCall[] = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = createNotebookFetch(fetchCalls, {
      detailResponse: createJsonResponse({ error: '详情接口失败' }, 500),
    });

    root = createRoot(domEnvironment.container);
    await renderNotebookForAlice(domEnvironment.container, root);

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /Alice 的错题库/);
      assert.match(pageText, /详情接口失败/);
      assert.match(pageText, /题目文本/);
      const textarea = domEnvironment.container.querySelector('textarea[placeholder="填写可直接进入错题库 PDF 的题目文本"]') as HTMLTextAreaElement | null;
      const saveButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('保存掌握情况'));
      assert.ok(textarea instanceof HTMLTextAreaElement);
      assert.equal(textarea.value, '计算 $2+3\\\\times4$ 的结果。');
      assert.ok(saveButton instanceof HTMLButtonElement);
      assert.equal(saveButton.disabled, false);
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

test('SmartWrongQuestionsPage keeps edited fields and releases save button when review saving fails', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: SmartWrongQuestionFetchCall[] = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = createNotebookFetch(fetchCalls, {
      saveResponse: createJsonResponse({ error: '保存接口失败' }, 500),
    });

    root = createRoot(domEnvironment.container);
    await renderNotebookForAlice(domEnvironment.container, root);

    await waitForAssertion(() => {
      const textarea = domEnvironment.container.querySelector('textarea[placeholder="填写可直接进入错题库 PDF 的题目文本"]') as HTMLTextAreaElement | null;
      assert.ok(textarea instanceof HTMLTextAreaElement);
    });

    const textarea = domEnvironment.container.querySelector('textarea[placeholder="填写可直接进入错题库 PDF 的题目文本"]') as HTMLTextAreaElement | null;
    const saveButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('保存掌握情况'));
    assert.ok(textarea instanceof HTMLTextAreaElement);
    assert.ok(saveButton instanceof HTMLButtonElement);

    await act(async () => {
      textarea.value = '老师本地改动未丢失';
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
      textarea.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      saveButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /保存接口失败/);
      assert.match(pageText, /Alice 的错题库/);
      assert.equal(textarea.value, '老师本地改动未丢失');
      assert.equal(saveButton.disabled, false);
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

test('SmartWrongQuestionsPage keeps PDF actions enabled and links stable when PDF refresh fails', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: SmartWrongQuestionFetchCall[] = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = createNotebookFetch(fetchCalls, {
      pdfRefreshResponse: createJsonResponse({ error: 'PDF 刷新失败' }, 500),
    });

    root = createRoot(domEnvironment.container);
    await renderNotebookForAlice(domEnvironment.container, root);

    await waitForAssertion(() => {
      const refreshButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('重新生成 PDF'));
      assert.ok(refreshButton instanceof HTMLButtonElement);
    });

    const refreshButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('重新生成 PDF'));
    const previewLink = Array.from(domEnvironment.container.querySelectorAll('a')).find((link) => link.textContent?.includes('预览 PDF')) ?? null;
    const downloadLink = Array.from(domEnvironment.container.querySelectorAll('a')).find((link) => link.textContent?.includes('下载 PDF')) ?? null;
    assert.ok(refreshButton instanceof HTMLButtonElement);
    assert.equal(previewLink?.getAttribute('href'), '/api/wechat/student-libraries/501?token=token-123');
    assert.equal(downloadLink?.getAttribute('href'), '/api/wechat/student-libraries/501?token=token-123');

    await act(async () => {
      refreshButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      assert.match(domEnvironment.container.textContent || '', /PDF 刷新失败/);
      assert.equal(refreshButton.disabled, false);
      assert.equal(previewLink?.getAttribute('href'), '/api/wechat/student-libraries/501?token=token-123');
      assert.equal(downloadLink?.getAttribute('href'), '/api/wechat/student-libraries/501?token=token-123');
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

test('SmartWrongQuestionsPage keeps selected notebook record when deleting it fails', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const originalConfirm = window.confirm;
  const fetchCalls: SmartWrongQuestionFetchCall[] = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    window.confirm = () => true;
    globalThis.fetch = createNotebookFetch(fetchCalls, {
      deleteResponse: createJsonResponse({ error: '删除接口失败' }, 500),
    });

    root = createRoot(domEnvironment.container);
    await renderNotebookForAlice(domEnvironment.container, root);

    await waitForAssertion(() => {
      const deleteButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('删除本题'));
      assert.ok(deleteButton instanceof HTMLButtonElement);
    });

    const deleteButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('删除本题'));
    assert.ok(deleteButton instanceof HTMLButtonElement);

    await act(async () => {
      deleteButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /删除接口失败/);
      assert.match(pageText, /计算 \$2\+3\\\\times4\$ 的结果。/);
      assert.match(pageText, /Alice 的错题库/);
      assert.equal(deleteButton.disabled, false);
    });
  } finally {
    window.confirm = originalConfirm;
    if (root) {
      await act(async () => {
        root?.unmount();
      });
    }
    globalThis.fetch = originalFetch;
    domEnvironment.cleanup();
  }
});

test('SmartWrongQuestionsPage keeps practice selection and releases generate button when practice generation fails', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: SmartWrongQuestionFetchCall[] = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = createNotebookFetch(fetchCalls, {
      practiceCreateResponse: createJsonResponse({ error: '练习生成失败' }, 500),
    });

    root = createRoot(domEnvironment.container);
    await renderNotebookForAlice(domEnvironment.container, root);

    await waitForAssertion(() => {
      const checkbox = domEnvironment.container.querySelector('input[aria-label="选择第 1 题"]');
      const generateButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('生成错题练习'));
      assert.ok(checkbox instanceof HTMLInputElement);
      assert.ok(generateButton instanceof HTMLButtonElement);
    });

    const checkbox = domEnvironment.container.querySelector('input[aria-label="选择第 1 题"]') as HTMLInputElement | null;
    const generateButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('生成错题练习'));
    assert.ok(checkbox instanceof HTMLInputElement);
    assert.ok(generateButton instanceof HTMLButtonElement);
    assert.equal(checkbox.checked, true);

    await act(async () => {
      generateButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /练习生成失败/);
      assert.match(pageText, /错题目录/);
      assert.equal(checkbox.checked, true);
      assert.equal(generateButton.disabled, false);
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

test('SmartWrongQuestionsPage builds practice history PDF links from pdf_path with auth token', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: SmartWrongQuestionFetchCall[] = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = createNotebookFetch(fetchCalls, {
      practiceHistoryItems: [
        {
          id: 12,
          student_id: 501,
          class_id: 42,
          student_name_snapshot: 'Alice',
          class_name_snapshot: '六年级 1 班',
          teacher_name_snapshot: 'Kayn',
          question_count: 1,
          status: 'ready',
          pdf_path: '/api/wrong-question-practice-sheets/12/pdf',
          created_at: '2026-04-20 10:00:00',
        },
      ],
    });

    root = createRoot(domEnvironment.container);
    await renderNotebookForAlice(domEnvironment.container, root);

    const historyTab = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('错题练习记录'));
    assert.ok(historyTab instanceof HTMLButtonElement);

    await act(async () => {
      historyTab.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const previewLink = Array.from(domEnvironment.container.querySelectorAll('a')).find((link) => link.textContent?.includes('预览 PDF')) ?? null;
      const downloadLink = Array.from(domEnvironment.container.querySelectorAll('a')).find((link) => link.textContent?.includes('下载 PDF')) ?? null;
      assert.equal(previewLink?.getAttribute('href'), '/api/wrong-question-practice-sheets/12/pdf?token=token-123');
      assert.equal(downloadLink?.getAttribute('href'), '/api/wrong-question-practice-sheets/12/pdf?token=token-123');
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
