import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  applyWrongQuestionReviewDraft,
  buildWrongQuestionDetailPath,
  buildWrongQuestionQuery,
  buildWrongQuestionReviewDraft,
  buildWrongQuestionReviewPath,
  buildWrongQuestionSummaryExportPath,
  downloadWrongQuestionSummary,
  hydrateWrongQuestionReviewDraftFromDetail,
  normalizeWrongQuestionListResponse,
  summarizeWrongQuestionRecords,
  type WrongQuestionRecord,
} from './smartWrongQuestions';

const currentDir = dirname(fileURLToPath(import.meta.url));

test('summarizeWrongQuestionRecords derives the overview card counts from loaded records', () => {
  const records: WrongQuestionRecord[] = [
    {
      id: 'record-1',
      studentName: 'Alice',
      className: '六年级 1 班',
      subject: '数学',
      teacherName: '雷文浩',
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
      subject: '英语',
      teacherName: '王老师',
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
      subject: '物理',
      teacherName: '李老师',
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
    subject: '数学',
    teacherName: '雷文浩',
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
    subject: '',
    teacherName: '王老师',
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

test('hydrateWrongQuestionReviewDraftFromDetail replaces pristine drafts and preserves locally edited drafts', () => {
  const listRecord: WrongQuestionRecord = {
    id: 'record-1',
    studentName: 'Alice',
    className: '六年级 1 班',
    subject: '数学',
    teacherName: '雷文浩',
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
    subject: '数学',
    teacherName: '雷文浩',
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

test('SmartWrongQuestionsPage saves review drafts and surfaces save failures without dropping edits', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');
  const saveBlock = pageSource.match(/const handleSaveReview = async \(\) => \{[\s\S]*?\n  \};/);

  assert.ok(saveBlock);
  assert.match(pageSource, /const \[saveError, setSaveError\] = useState\(''\);/);
  assert.match(pageSource, /const \[savingReview, setSavingReview\] = useState\(false\);/);
  assert.match(saveBlock[0], /apiFetch(?:<[^>]+>)?\(buildWrongQuestionReviewPath\([^)]+\), \{\s*method: 'PUT'/);
  assert.match(saveBlock[0], /catch \(saveReviewError\) \{\s*setSaveError\(/);
  assert.match(saveBlock[0], /updateDraftDirtyState\([^)]+false\)/);
  assert.match(pageSource, /保存教师复盘/);
});

test('SmartWrongQuestionsPage reuses the current filter query for PDF export', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /const handleExportSummary = \(\) => \{/);
  assert.match(pageSource, /downloadWrongQuestionSummary\(filters\)/);
  assert.match(pageSource, /导出 PDF 汇总/);
});