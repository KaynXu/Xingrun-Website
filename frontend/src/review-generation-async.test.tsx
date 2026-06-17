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
  assert.match(reviewGenerationSource, /\.then\(\(payload\) => setLessons\(normalizeReviewLessonsResponse\(payload\)\)\)/);
});

test('review history source exposes regenerate action and immediate progress feedback', () => {
  assert.match(reviewGenerationSource, /\/api\/review-plans\/\$\{lesson\.id\}\/regenerate/);
  assert.match(reviewGenerationSource, /确定重新生成《\$\{getLessonTitle\(lesson\)\}》吗/);
  assert.match(reviewGenerationSource, /record_status: nextStatus, generation_error: ''/);
  assert.match(reviewGenerationSource, /title="重新生成"/);
});

test('review generation source synchronizes member class selection against accessible classes', () => {
  assert.match(lessonInputSource, /function syncMemberScopedClassSelection\(/);
  assert.match(lessonInputSource, /if \(role !== 'member'\) \{\s*return selectedClassId;/);
  assert.match(lessonInputSource, /if \(classes.length === 1\) \{\s*return classes\[0\]\?\.id \?\? null;/);
  assert.match(lessonInputSource, /setClassId\(\(current\) => syncMemberScopedClassSelection\(currentUser\.role, classes, current\)\);/);
  assert.match(appSource, /import \{ WorkspacePageContent \} from '\.\/features\/navigation\/WorkspacePageContent';/);
  assert.match(workspacePageContentSource, /import \{ LessonInput \} from '\.\.\/review-generation\/LessonInput';/);
});
