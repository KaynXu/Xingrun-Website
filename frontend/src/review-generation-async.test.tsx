import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

test('review generation source tracks async lesson status fields', () => {
  assert.match(appSource, /record_status\?: string;/);
  assert.match(appSource, /generation_error\?: string;/);
});

test('review history source polls review plans while pending lessons exist', () => {
  assert.match(appSource, /const hasPendingLesson = lessons\.some\(isReviewLessonPending\);/);
  assert.match(appSource, /const timer = window\.setInterval\(\(\) => \{\s*void load\(true\);\s*\}, 3000\);/);
  assert.match(appSource, /return \(\) => window\.clearInterval\(timer\);/);
});

test('review history source normalizes malformed task polling responses', () => {
  assert.match(appSource, /apiFetch<unknown>\('\/api\/review-plans'\)/);
  assert.match(appSource, /\.then\(\(payload\) => setLessons\(normalizeReviewLessonsResponse\(payload\)\)\)/);
});

test('review history source renders pending and failed status copy', () => {
  assert.match(appSource, /const taskState = getReviewLessonTaskState\(lesson\);/);
  assert.match(appSource, /lesson\.record_status === 'transcribing'\s*\?\s*'转写中'/);
  assert.match(appSource, /taskState === 'pending'\s*\?\s*'生成中'/);
  assert.match(appSource, /taskState === 'failed'/);
  assert.match(appSource, /'生成失败'/);
  assert.match(appSource, /getReviewLessonTaskMessage\(lesson\)/);
  assert.match(appSource, /正在生成复习计划，可离开页面/);
  assert.match(appSource, /getReviewLessonTaskProgress\(lesson\)/);
});

test('review history source hides PDF actions until a completed lesson has output', () => {
  assert.match(appSource, /hasReviewLessonOutput\(lesson\) &&/);
  assert.doesNotMatch(appSource, /lesson\.pdf_path && \(/);
});

test('review generation page closes composer after async creation succeeds', () => {
  assert.match(appSource, /const handleFormSuccess = \(\) => \{\s*setComposerOpen\(false\);/);
});

test('review generation source synchronizes member class selection against accessible classes', () => {
  assert.match(appSource, /function syncMemberScopedClassSelection\(/);
  assert.match(appSource, /if \(role !== 'member'\) \{\s*return selectedClassId;/);
  assert.match(appSource, /if \(classes.length === 1\) \{\s*return classes\[0\]\?\.id \?\? null;/);
  assert.match(appSource, /setClassId\(\(current\) => syncMemberScopedClassSelection\(currentUser\.role, classes, current\)\);/);
});
