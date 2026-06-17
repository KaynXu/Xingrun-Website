import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const reviewGenerationSource = readFileSync(new URL('./features/review-generation/ReviewGenerationPage.tsx', import.meta.url), 'utf8');
const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');
const workspacePageContentSource = readFileSync(new URL('./features/navigation/WorkspacePageContent.tsx', import.meta.url), 'utf8');
const lessonInputSource = readFileSync(new URL('./features/review-generation/LessonInput.tsx', import.meta.url), 'utf8');

test('review history source polls review plans while pending lessons exist', () => {
  assert.match(reviewGenerationSource, /const hasPendingLesson = lessons\.some\(isReviewLessonPending\);/);
  assert.match(reviewGenerationSource, /const timer = window\.setInterval\(\(\) => \{\s*void load\(true\);\s*\}, 3000\);/);
  assert.match(reviewGenerationSource, /return \(\) => window\.clearInterval\(timer\);/);
});

test('review history source normalizes malformed task polling responses', () => {
  assert.match(reviewGenerationSource, /apiFetch<unknown>\('\/api\/review-plans'\)/);
  assert.match(reviewGenerationSource, /const nextLessons = normalizeReviewLessonsResponse\(payload\);/);
  assert.match(reviewGenerationSource, /setLessons\(nextLessons\);/);
  assert.match(reviewGenerationSource, /onLessonsChange\(nextLessons\);/);
});

test('review history source exposes regenerate action and immediate progress feedback', () => {
  assert.match(reviewGenerationSource, /\/api\/review-plans\/\$\{lesson\.id\}\/regenerate/);
  assert.match(reviewGenerationSource, /确定重新生成《\$\{getLessonTitle\(lesson\)\}》吗/);
  assert.match(reviewGenerationSource, /onTaskStarted\(lesson\.id, startedAtMs\);/);
  assert.match(reviewGenerationSource, /onFloatingNotice\(\{ type: 'info', text: `《\$\{getLessonTitle\(lesson\)\}》已开始重新生成。` \}\);/);
  assert.match(reviewGenerationSource, /record_status: nextStatus, generation_error: ''/);
  assert.match(reviewGenerationSource, /title="重新生成"/);
});

test('review generation source keeps progress feedback in a bottom-right dock instead of inline color banners', () => {
  assert.match(reviewGenerationSource, /function ReviewGenerationTaskDock\(/);
  assert.match(reviewGenerationSource, /createPortal\(dock, document\.body\)/);
  assert.match(reviewGenerationSource, /fixed bottom-5 right-5/);
  assert.match(reviewGenerationSource, /复习计划生成/);
  assert.match(workspacePageContentSource, /<ReviewGenerationTaskDock[\s\S]*lessons=\{reviewLatestLessons\}[\s\S]*notice=\{reviewFloatingNotice\}/);
  assert.match(workspacePageContentSource, /setReviewProgressNow\(Date\.now\(\)\);/);
  assert.match(workspacePageContentSource, /activeWorkspacePage === 'review-generation' \? 6000 : 3000/);
  assert.doesNotMatch(reviewGenerationSource, /border-emerald-200 bg-emerald-50/);
  assert.doesNotMatch(reviewGenerationSource, /bg-amber-50/);
});

test('review generation source synchronizes member class selection against accessible classes', () => {
  assert.match(lessonInputSource, /function syncMemberScopedClassSelection\(/);
  assert.match(lessonInputSource, /if \(role !== 'member'\) \{\s*return selectedClassId;/);
  assert.match(lessonInputSource, /if \(classes.length === 1\) \{\s*return classes\[0\]\?\.id \?\? null;/);
  assert.match(lessonInputSource, /setClassId\(\(current\) => syncMemberScopedClassSelection\(currentUser\.role, classes, current\)\);/);
  assert.match(appSource, /import \{ WorkspacePageContent \} from '\.\/features\/navigation\/WorkspacePageContent';/);
  assert.match(workspacePageContentSource, /import \{ LessonInput \} from '\.\.\/review-generation\/LessonInput';/);
});
