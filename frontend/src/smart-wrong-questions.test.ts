import test from 'node:test';
import assert from 'node:assert/strict';

import { buildWrongQuestionQuery, summarizeWrongQuestionRecords, type WrongQuestionRecord } from './smartWrongQuestions';

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