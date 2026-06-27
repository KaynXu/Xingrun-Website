import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const classFeedbackPageSource = readFileSync(new URL('./features/class-feedback/ClassFeedbackGenerationPage.tsx', import.meta.url), 'utf8');

test('ClassFeedbackGenerationPage renders an empty rebuild shell', () => {
  assert.match(classFeedbackPageSource, /export function ClassFeedbackGenerationPage/);
  assert.match(classFeedbackPageSource, /课堂反馈/);
  assert.match(classFeedbackPageSource, /重新设计中/);
  assert.doesNotMatch(classFeedbackPageSource, /创建反馈任务/);
  assert.doesNotMatch(classFeedbackPageSource, /生成阶段反馈草稿/);
  assert.doesNotMatch(classFeedbackPageSource, /保存草稿/);
  assert.doesNotMatch(classFeedbackPageSource, /确认本次反馈/);
  assert.doesNotMatch(classFeedbackPageSource, /班级总评/);
  assert.doesNotMatch(classFeedbackPageSource, /学生反馈/);
});

test('ClassFeedbackGenerationPage no longer depends on the old class feedback workflow code', () => {
  assert.doesNotMatch(classFeedbackPageSource, /ClassFeedbackGenerationWorkspace/);
  assert.doesNotMatch(classFeedbackPageSource, /classFeedbackGeneration/);
  assert.doesNotMatch(classFeedbackPageSource, /apiFetch/);
  assert.doesNotMatch(classFeedbackPageSource, /useEffect|useMemo|useCallback|useRef|useState/);
  assert.doesNotMatch(classFeedbackPageSource, /createClassFeedbackTask|generateClassFeedbackTask|saveClassFeedbackTaskDraft|confirmClassFeedbackTask/);
});
