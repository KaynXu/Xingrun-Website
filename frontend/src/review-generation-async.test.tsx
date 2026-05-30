import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

test('review history source polls review plans while pending lessons exist', () => {
  assert.match(appSource, /const hasPendingLesson = lessons\.some\(isReviewLessonPending\);/);
  assert.match(appSource, /const timer = window\.setInterval\(\(\) => \{\s*void load\(true\);\s*\}, 3000\);/);
  assert.match(appSource, /return \(\) => window\.clearInterval\(timer\);/);
});

test('review history source normalizes malformed task polling responses', () => {
  assert.match(appSource, /apiFetch<unknown>\('\/api\/review-plans'\)/);
  assert.match(appSource, /\.then\(\(payload\) => setLessons\(normalizeReviewLessonsResponse\(payload\)\)\)/);
});

test('review generation source synchronizes member class selection against accessible classes', () => {
  assert.match(appSource, /function syncMemberScopedClassSelection\(/);
  assert.match(appSource, /if \(role !== 'member'\) \{\s*return selectedClassId;/);
  assert.match(appSource, /if \(classes.length === 1\) \{\s*return classes\[0\]\?\.id \?\? null;/);
  assert.match(appSource, /setClassId\(\(current\) => syncMemberScopedClassSelection\(currentUser\.role, classes, current\)\);/);
});
