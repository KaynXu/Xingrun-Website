import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('./features/class-feedback/ClassFeedbackGenerationPage.tsx', import.meta.url), 'utf8');

test('class feedback generation page uses class-commentary api client', () => {
  assert.match(source, /from '..\/..\/classCommentary'/);
  assert.match(source, /apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(source, /createClassCommentaryTask/);
  assert.match(source, /fetchClassCommentarySkills/);
  assert.match(source, /generateClassCommentaryFeedback/);
  assert.doesNotMatch(source, /api\/class-feedback/);
  assert.doesNotMatch(source, /currentUser\.token/);
});

test('class feedback generation page uses shadcn components for visible controls', () => {
  assert.match(source, /@\/components\/ui\/button/);
  assert.match(source, /@\/components\/ui\/card/);
  assert.match(source, /@\/components\/ui\/input/);
  assert.match(source, /@\/components\/ui\/progress/);
  assert.match(source, /@\/components\/ui\/select/);
  assert.match(source, /@\/components\/ui\/badge/);
  assert.match(source, /@\/components\/ui\/separator/);
  assert.match(source, /@\/components\/ui\/scroll-area/);
  assert.match(source, /@\/components\/ui\/skeleton/);
  assert.match(source, /@\/components\/ui\/textarea/);
  assert.match(source, /@\/components\/ui\/alert/);
  assert.doesNotMatch(source, /workspaceCardClass/);
  assert.doesNotMatch(source, /workspacePrimaryButtonClass/);
  assert.doesNotMatch(source, /workspaceSecondaryButtonClass/);
  assert.doesNotMatch(source, /workspaceFieldClass/);
});

test('class feedback generation page exposes upload transcript and copy result workflow', () => {
  assert.match(source, /type="file"/);
  assert.match(source, /audio\//);
  assert.match(source, /confirmedTranscript/);
  assert.match(source, /navigator\.clipboard\.writeText/);
  assert.match(source, /feedback_text/);
});

test('class feedback generation page saves transcript before generation', () => {
  assert.match(source, /if \(!trimmedConfirmedTranscript\) \{\s*setErrorMessage\('请先确认转写文本'\);/);
  assert.match(source, /const savedTask = transcriptDirty\s*\?\s*await saveClassCommentaryTranscript\(task\.id, trimmedConfirmedTranscript\)\s*:\s*task;/);
  assert.match(source, /await generateClassCommentaryFeedback\(savedTask\.id, selectedSkillId\)/);
});
