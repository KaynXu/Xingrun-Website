import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getReviewTaskDockLessons,
  getReviewLessonTaskMessage,
  getReviewLessonTaskProgress,
  getReviewLessonTaskState,
  hasReviewLessonOutput,
  isReviewLessonPending,
  normalizeReviewLessonsResponse,
  normalizeReviewLessonsPageResponse,
} from './reviewGenerationAsync';

test('review task dock keeps pending work but does not revive historical failures', () => {
  const lessons = normalizeReviewLessonsResponse([
    {
      id: 30,
      subject: '数学',
      active_version_status: 'generating',
      has_version_generating: true,
    },
    {
      id: 31,
      subject: '数学',
      record_status: 'failed',
      generation_error: '很久以前的失败',
    },
    {
      id: 32,
      subject: '数学',
      record_status: 'failed',
      generation_error: '本次任务失败',
    },
    {
      id: 33,
      subject: '数学',
      current_pdf_url: '/api/review-plans/33/pdf',
      current_status: 'ready',
    },
  ]);

  assert.deepEqual(getReviewTaskDockLessons(lessons, new Set()).map((lesson) => lesson.id), [30]);
  assert.deepEqual(getReviewTaskDockLessons(lessons, new Set([32])).map((lesson) => lesson.id), [30, 32]);
});

test('normalizeReviewLessonsResponse keeps current version and active generation fields', () => {
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
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      current_version_id: 31,
      current_version_no: 2,
      current_generated_at: '2026-05-02T12:30:00',
      current_pdf_url: '/api/review-plans/12/versions/31/pdf',
      current_download_url: '/api/review-plans/12/versions/31/download',
      current_status: 'ready',
      has_version_generating: true,
      active_version_status: 'generating',
      active_version_created_at: '2026-05-02T12:35:00',
      latest_generation_error: '',
    },
    { id: 'bad' },
  ]);

  assert.equal(lessons.length, 1);
  assert.equal(lessons[0]?.id, 12);
  assert.equal(lessons[0]?.current_version_id, 31);
  assert.equal(lessons[0]?.current_version_no, 2);
  assert.equal(lessons[0]?.current_generated_at, '2026-05-02T12:30:00');
  assert.equal(lessons[0]?.current_pdf_url, '/api/review-plans/12/versions/31/pdf');
  assert.equal(lessons[0]?.current_download_url, '/api/review-plans/12/versions/31/download');
  assert.equal(lessons[0]?.current_status, 'ready');
  assert.equal(lessons[0]?.has_version_generating, true);
  assert.equal(lessons[0]?.active_version_status, 'generating');
  assert.equal(lessons[0]?.active_version_created_at, '2026-05-02T12:35:00');
  assert.equal(lessons[0]?.latest_generation_error, '');
});

test('normalizeReviewLessonsPageResponse accepts paginated review plan lists', () => {
  const page = normalizeReviewLessonsPageResponse({
    items: [
      {
        id: 33,
        date: '2026-07-02',
        subject: '数学',
        grade: '六年级',
        topic: '勾股数',
      },
    ],
    total: 28,
    page: 2,
    page_size: 12,
  });

  assert.equal(page.items.length, 1);
  assert.equal(page.items[0]?.id, 33);
  assert.equal(page.total, 28);
  assert.equal(page.page, 2);
  assert.equal(page.page_size, 12);
  assert.deepEqual(normalizeReviewLessonsResponse({ items: [{ id: 33 }] }).map((item) => item.id), [33]);
});

test('review lesson state keeps current output available while a new version generates', () => {
  const lesson = normalizeReviewLessonsResponse([
    {
      id: 13,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      current_version_id: 41,
      current_version_no: 1,
      current_pdf_url: '/api/review-plans/13/versions/41/pdf',
      current_download_url: '/api/review-plans/13/versions/41/download',
      current_status: 'ready',
      has_version_generating: true,
      active_version_status: 'generating',
      active_version_created_at: '2026-05-02T12:20:00',
    },
  ])[0];

  assert.ok(lesson);
  assert.equal(hasReviewLessonOutput(lesson), true);
  assert.equal(getReviewLessonTaskState(lesson), 'pending');
  assert.equal(isReviewLessonPending(lesson), true);
  assert.equal(getReviewLessonTaskMessage(lesson), '正在生成新版，当前 PDF 可继续使用');
});

test('failed regeneration does not hide current output', () => {
  const lesson = normalizeReviewLessonsResponse([
    {
      id: 14,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      current_version_id: 41,
      current_version_no: 1,
      current_pdf_url: '/api/review-plans/14/versions/41/pdf',
      current_download_url: '/api/review-plans/14/versions/41/download',
      current_status: 'ready',
      has_version_generating: false,
      latest_generation_error: '第二版失败',
    },
  ])[0];

  assert.ok(lesson);
  assert.equal(getReviewLessonTaskState(lesson), 'ready');
  assert.equal(getReviewLessonTaskMessage(lesson), '');
  assert.equal(hasReviewLessonOutput(lesson), true);
});

test('failed generation without current output shows the latest error', () => {
  const lesson = normalizeReviewLessonsResponse([
    {
      id: 20,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      current_pdf_url: '',
      current_download_url: '',
      has_version_generating: false,
      latest_generation_error: 'AI 生成失败，请稍后重试',
    },
  ])[0];

  assert.ok(lesson);
  assert.equal(hasReviewLessonOutput(lesson), false);
  assert.equal(getReviewLessonTaskState(lesson), 'failed');
  assert.equal(isReviewLessonPending(lesson), false);
  assert.equal(getReviewLessonTaskMessage(lesson), 'AI 生成失败，请稍后重试');
});

test('legacy generating record status still shows a pending task', () => {
  const lesson = normalizeReviewLessonsResponse([
    {
      id: 21,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      record_status: 'generating',
    },
  ])[0];

  assert.ok(lesson);
  assert.equal(hasReviewLessonOutput(lesson), false);
  assert.equal(getReviewLessonTaskState(lesson), 'pending');
  assert.equal(isReviewLessonPending(lesson), true);
  assert.equal(getReviewLessonTaskMessage(lesson), '正在生成复习计划，可离开页面');
  assert.equal(getReviewLessonTaskProgress(lesson), 78);
});

test('legacy failed record status still shows the generation error', () => {
  const lesson = normalizeReviewLessonsResponse([
    {
      id: 22,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      record_status: 'failed',
      generation_error: 'AI 生成失败，请稍后重试',
    },
  ])[0];

  assert.ok(lesson);
  assert.equal(hasReviewLessonOutput(lesson), false);
  assert.equal(getReviewLessonTaskState(lesson), 'failed');
  assert.equal(isReviewLessonPending(lesson), false);
  assert.equal(getReviewLessonTaskMessage(lesson), 'AI 生成失败，请稍后重试');
});

test('review lesson task progress distinguishes audio transcription from plan generation', () => {
  const transcribingLesson = normalizeReviewLessonsResponse([
    {
      id: 17,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '',
      weak_points: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      has_version_generating: true,
      active_version_status: 'transcribing',
      active_version_created_at: '2026-05-02T12:00:00',
    },
  ])[0];
  const generatingLesson = normalizeReviewLessonsResponse([
    {
      id: 18,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      has_version_generating: true,
      active_version_status: 'generating',
      active_version_created_at: '2026-05-02T12:00:00',
    },
  ])[0];

  assert.ok(transcribingLesson);
  assert.equal(getReviewLessonTaskState(transcribingLesson), 'pending');
  assert.equal(getReviewLessonTaskMessage(transcribingLesson), '录音已上传，正在转写');
  assert.equal(getReviewLessonTaskProgress(transcribingLesson), 45);

  assert.ok(generatingLesson);
  assert.equal(getReviewLessonTaskMessage(generatingLesson), '正在生成复习计划，可离开页面');
  assert.equal(getReviewLessonTaskProgress(generatingLesson), 78);
});

test('review lesson task progress can estimate moving progress while generation is active', () => {
  const generatingLesson = normalizeReviewLessonsResponse([
    {
      id: 19,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00.000Z',
      has_version_generating: true,
      active_version_status: 'generating',
      active_version_created_at: '2026-05-02T12:00:00.000Z',
    },
  ])[0];

  assert.ok(generatingLesson);
  assert.equal(getReviewLessonTaskProgress(generatingLesson, { nowMs: Date.parse('2026-05-02T12:00:00.000Z') }), 62);
  assert.equal(getReviewLessonTaskProgress(generatingLesson, { nowMs: Date.parse('2026-05-02T12:02:00.000Z') }), 78);
  assert.equal(getReviewLessonTaskProgress(generatingLesson, { nowMs: Date.parse('2026-05-02T12:10:00.000Z') }), 94);
});

test('review lesson task state refuses completed output until a current PDF url is present', () => {
  const incompleteReadyLesson = normalizeReviewLessonsResponse([
    {
      id: 15,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      current_version_id: 51,
      current_version_no: 1,
      current_pdf_url: '',
      current_download_url: '',
      current_status: 'ready',
      latest_generation_error: '',
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
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      current_version_id: 52,
      current_version_no: 1,
      current_pdf_url: '/api/review-plans/16/versions/52/pdf',
      current_download_url: '/api/review-plans/16/versions/52/download',
      current_status: 'ready',
      latest_generation_error: '',
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
