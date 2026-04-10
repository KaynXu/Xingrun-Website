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
  buildWrongQuestionDetailPath,
  buildWrongQuestionQuery,
  buildWrongQuestionReviewDraft,
  buildWrongQuestionReviewPayload,
  buildWrongQuestionReviewPath,
  filterWrongQuestionRecordsForMemberNotebook,
  getWrongQuestionSemanticModel,
  getWrongQuestionSourceLabel,
  hydrateWrongQuestionReviewDraftFromDetail,
  isDownstreamWrongQuestionRecord,
  isWechatMiniProgramWrongQuestionRecord,
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

test('filterWrongQuestionRecordsForMemberNotebook keeps only the selected class and student records', () => {
  const records = [
    makeWrongQuestionRecord({ id: 'a', classId: 101, studentName: 'Alice', createdAt: '2026-03-29T09:00:00Z' }),
    makeWrongQuestionRecord({ id: 'b', classId: 101, studentName: 'Bob', createdAt: '2026-03-29T08:00:00Z' }),
    makeWrongQuestionRecord({ id: 'c', classId: 202, studentName: 'Alice', createdAt: '2026-03-29T10:00:00Z' }),
  ];

  assert.deepEqual(
    filterWrongQuestionRecordsForMemberNotebook(records, 101, 'Alice').map((item) => item.id),
    ['a'],
  );
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
    primary_error_type: '审题不清',
    secondary_error_summary: '孩子忽略了题目里的单位换算要求。',
    archive_status: 'archived',
    analysis: {
      error_type: '审题不清',
      student_note: '孩子忽略了题目里的单位换算要求。',
    },
  });

  assert.equal(normalized.source, 'wechat_mp');
  assert.equal(normalized.childReasonText, '我把单位换算漏掉了');
  assert.equal(normalized.primaryErrorType, '审题不清');
  assert.equal(normalized.causeNote, '孩子忽略了题目里的单位换算要求。');
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

  assert.match(pageSource, /selectedRecord\?\.source === 'wechat_mp'/);
  assert.match(pageSource, /微信小程序/);
  assert.match(pageSource, /孩子自述错因/);
  assert.match(pageSource, /AI 归类错因/);
  assert.match(pageSource, /AI 备注/);
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
  assert.match(pageSource, /最终错误类型/);
  assert.match(pageSource, /核心知识点/);
  assert.match(pageSource, /后续练习建议/);
  assert.match(pageSource, /原因分析/);
  assert.match(pageSource, /教师备注/);
});

test('SmartWrongQuestionsPage source exposes editable question text for local non-geometry records', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /题目文本/);
  assert.match(pageSource, /填写可直接进入错题库 PDF 的题目文本/);
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
      const selectedErrorTypeInput = domEnvironment.container.querySelector('input[placeholder="填写教师最终确认的错误类型"]') as HTMLInputElement | null;
      const selectedKnowledgePointsTextarea = domEnvironment.container.querySelector('textarea[placeholder="每行一个知识点"]') as HTMLTextAreaElement | null;

      assert.ok(selectedErrorTypeInput instanceof HTMLInputElement);
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
      const saveCall = fetchCalls.findLast((call) => call.input === '/api/wrong-questions/record-1/review');
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
      const saveCall = fetchCalls.findLast((call) => call.input === '/api/wrong-questions/record-save-legacy/review');
      assert.ok(saveCall);
      const pageText = domEnvironment.container.textContent || '';
      assert.match(pageText, /老师与班级归属待确认/);
      assert.match(pageText, /老师：Kayn/);
      assert.match(pageText, /原始老师：Kayn 老师（代课）/);
      assert.match(pageText, /班级：六年级 1 班/);
      assert.match(pageText, /原始班级：六年级一班（临时）/);
      assert.match(pageText, /映射状态：待确认映射/);
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
              student_name: 'Alice',
              class_display_name: '六年级 1 班',
              class_id: 42,
              subject: '数学',
              teacher_display_name: 'Kayn',
              created_at: '2026-03-29T08:00:00Z',
              recognition_status: 'recognized',
              is_geometry: 0,
              question_text: '原始 AI 文本',
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
          student_name: 'Alice',
          class_display_name: '六年级 1 班',
          class_id: 42,
          subject: '数学',
          teacher_display_name: 'Kayn',
          created_at: '2026-03-29T08:00:00Z',
          recognition_status: 'recognized',
          is_geometry: 0,
          question_text: '原始 AI 文本',
          question_text_source: 'ai',
          student_library_pdf_path: '/api/wechat/student-libraries/1',
          child_raw_reason_text: '我把乘法优先级看漏了',
          primary_error_type: '计算粗心',
          secondary_error_summary: '孩子知道规则，但这道题没先算乘法。',
          archive_status: 'active',
          analysis: {
            error_type: '计算粗心',
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
            student_name: 'Alice',
            class_display_name: '六年级 1 班',
            subject: '数学',
            teacher_display_name: 'Kayn',
            created_at: '2026-03-29T08:00:00Z',
            recognition_status: 'recognized',
            is_geometry: 0,
            question_text: '老师修正后的题目文本',
            question_text_source: 'teacher',
            student_library_pdf_path: '/api/wechat/student-libraries/1',
            child_raw_reason_text: '我把乘法优先级看漏了',
            primary_error_type: '计算粗心',
            secondary_error_summary: '孩子知道规则，但这道题没先算乘法。',
            archive_status: 'archived',
            analysis: {
              error_type: '计算粗心',
              student_note: '孩子知道规则，但这道题没先算乘法。',
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
      assert.match(pageText, /题目文本/);
      assert.match(pageText, /孩子自述错因/);
      assert.match(pageText, /AI 归类错因/);
      const textarea = domEnvironment.container.querySelector('textarea[placeholder="填写可直接进入错题库 PDF 的题目文本"]') as HTMLTextAreaElement | null;
      assert.ok(textarea instanceof HTMLTextAreaElement);
      assert.equal(textarea.value, '原始 AI 文本');
    });

    const questionTextarea = domEnvironment.container.querySelector('textarea[placeholder="填写可直接进入错题库 PDF 的题目文本"]') as HTMLTextAreaElement | null;
    const masteryCheckbox = domEnvironment.container.querySelector('input[type="checkbox"]') as HTMLInputElement | null;
    const saveButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('保存掌握情况'));

    assert.ok(questionTextarea instanceof HTMLTextAreaElement);
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
      questionText: '老师修正后的题目文本',
      isMastered: true,
    });

    assert.equal(payload.question_text, '老师修正后的题目文本');
    assert.equal(payload.is_mastered, true);
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
      const saveCall = fetchCalls.findLast((call) => call.input === '/api/wrong-questions/record-save-top-level/review');
      assert.ok(saveCall);
      const pageText = domEnvironment.container.textContent || '';
      const selectedErrorTypeInput = domEnvironment.container.querySelector('input[placeholder="填写教师最终确认的错误类型"]') as HTMLInputElement | null;
      assert.ok(selectedErrorTypeInput instanceof HTMLInputElement);
      assert.equal(selectedErrorTypeInput.value, '服务端修正');
      assert.match(pageText, /老师与班级归属待确认/);
      assert.match(pageText, /老师：Kayn/);
      assert.match(pageText, /原始老师：Kayn 老师（代课）/);
      assert.match(pageText, /班级：六年级 1 班/);
      assert.match(pageText, /原始班级：六年级一班（临时）/);
      assert.match(pageText, /映射状态：待确认映射/);
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

test('SmartWrongQuestionsPage source no longer exposes export or pending-review controls in the notebook view', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');
  const helperSource = readFileSync(resolve(currentDir, 'smartWrongQuestions.ts'), 'utf8');

  assert.doesNotMatch(pageSource, /downloadWrongQuestionSummary\(filters\)/);
  assert.doesNotMatch(pageSource, /导出汇总/);
  assert.doesNotMatch(pageSource, /只看待教师跟进/);
  assert.match(pageSource, /未掌握/);
  assert.doesNotMatch(helperSource, /onlyPendingReview\?: boolean/);
  assert.doesNotMatch(helperSource, /buildWrongQuestionSummaryExportPath/);
  assert.doesNotMatch(helperSource, /downloadWrongQuestionSummary/);
  assert.doesNotMatch(helperSource, /summary\/export/);
});

test('SmartWrongQuestionsPage copy avoids conversational guidance text', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.doesNotMatch(pageSource, /老师这里只保留是否掌握的勾选/);
  assert.doesNotMatch(pageSource, /保存失败时会保留当前草稿，便于继续修改后重试/);
  assert.doesNotMatch(pageSource, /把当前题目按错题库文档方式展开/);
  assert.doesNotMatch(pageSource, /查看这个孩子当前记录，并直接保存跟进内容/);
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
      assert.match(pageText, /2 题/);
      assert.match(pageText, /1 题/);
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
      assert.match(pageText, /1 题/);
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
            primary_error_type: '审题不清',
            secondary_error_summary: '孩子忽略了题目里的单位换算要求。',
            archive_status: 'archived',
            analysis: {
              question_category: '计算',
              error_type: '审题不清',
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
      assert.match(pageText, /第 1 题/);
      assert.match(pageText, /第 2 题/);
      assert.match(pageText, /错题目录/);
      assert.match(pageText, /2026-03-27T09:00:00Z/);
      assert.match(pageText, /已掌握/);
      assert.doesNotMatch(pageText, /第二题还是错/);
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
      assert.match(pageText, /错题详情/);
      assert.doesNotMatch(pageText, /错题档案/);
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
              primary_error_type: '计算粗心',
              secondary_error_summary: '孩子知道规则，但这道题没先算乘法。',
              archive_status: 'active',
              analysis: {
                question_category: '计算',
                error_type: '计算粗心',
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
      assert.match(pageText, /AI 归类错因/);
      assert.match(pageText, /AI 备注/);
      assert.match(pageText, /是否掌握/);
      assert.doesNotMatch(pageText, /重复错题/);
      assert.doesNotMatch(pageText, /知识点/);
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
