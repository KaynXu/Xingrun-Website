import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  buildWrongQuestionQuery,
  buildWrongQuestionSummaryExportPath,
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
  assert.match(pageSource, /apiFetch<[^>]+>\(`\/api\/wrong-questions\/\$\{[^}]+\}`\)/);
  assert.match(pageSource, /setReviewDraftByRecordId\(\(current\) => \{/);
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
  assert.match(saveBlock[0], /apiFetch(?:<[^>]+>)?\(`\/api\/wrong-questions\/\$\{[^}]+\}\/review`, \{\s*method: 'PUT'/);
  assert.match(saveBlock[0], /catch \(saveReviewError\) \{\s*setSaveError\(/);
  assert.match(pageSource, /保存教师复盘/);
});

test('SmartWrongQuestionsPage reuses the current filter query for PDF export', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /const handleExportSummary = \(\) => \{/);
  assert.match(pageSource, /buildWrongQuestionSummaryExportPath\(filters\)/);
  assert.match(pageSource, /window\.open\(/);
  assert.match(pageSource, /导出 PDF 汇总/);
});