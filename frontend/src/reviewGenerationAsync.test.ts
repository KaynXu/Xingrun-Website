import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getReviewLessonTaskMessage,
  getReviewLessonTaskState,
  hasReviewLessonOutput,
  isReviewLessonPending,
  normalizeReviewLessonsResponse,
} from './reviewGenerationAsync';

test('normalizeReviewLessonsResponse drops malformed list payloads instead of crashing polling UI', () => {
  assert.deepEqual(normalizeReviewLessonsResponse({ items: [] }), []);
  assert.deepEqual(normalizeReviewLessonsResponse(null), []);

  const lessons = normalizeReviewLessonsResponse([
    {
      id: 12,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '一元一次方程',
      summary: '课堂摘要',
      weak_points: '移项',
      pdf_path: '/tmp/review.pdf',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      record_status: 'ready',
      generation_error: '',
    },
    { id: 'bad' },
  ]);

  assert.equal(lessons.length, 1);
  assert.equal(lessons[0]?.id, 12);
  assert.equal(lessons[0]?.pdf_path, '/tmp/review.pdf');
});

test('review lesson task state keeps pending polling and failed error copy distinct', () => {
  const pendingLesson = normalizeReviewLessonsResponse([
    {
      id: 13,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      pdf_path: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      record_status: 'pending',
      generation_error: '',
    },
  ])[0];
  const failedLesson = normalizeReviewLessonsResponse([
    {
      id: 14,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      pdf_path: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      record_status: 'failed',
      generation_error: 'AI 生成失败，请稍后重试',
    },
  ])[0];

  assert.ok(pendingLesson);
  assert.equal(getReviewLessonTaskState(pendingLesson), 'pending');
  assert.equal(isReviewLessonPending(pendingLesson), true);
  assert.equal(getReviewLessonTaskMessage(pendingLesson), '可离开页面，完成后会出现在列表中');

  assert.ok(failedLesson);
  assert.equal(getReviewLessonTaskState(failedLesson), 'failed');
  assert.equal(isReviewLessonPending(failedLesson), false);
  assert.equal(getReviewLessonTaskMessage(failedLesson), 'AI 生成失败，请稍后重试');
});

test('review lesson task state refuses completed output until a PDF path is present', () => {
  const incompleteReadyLesson = normalizeReviewLessonsResponse([
    {
      id: 15,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      pdf_path: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      record_status: 'ready',
      generation_error: '',
    },
  ])[0];
  const readyLesson = normalizeReviewLessonsResponse([
    {
      id: 16,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      pdf_path: '/tmp/ready.pdf',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      record_status: 'ready',
      generation_error: '',
    },
  ])[0];

  assert.ok(incompleteReadyLesson);
  assert.equal(getReviewLessonTaskState(incompleteReadyLesson), 'missing-output');
  assert.equal(hasReviewLessonOutput(incompleteReadyLesson), false);
  assert.equal(getReviewLessonTaskMessage(incompleteReadyLesson), '生成结果缺少 PDF，请刷新后重试');

  assert.ok(readyLesson);
  assert.equal(getReviewLessonTaskState(readyLesson), 'ready');
  assert.equal(hasReviewLessonOutput(readyLesson), true);
});
