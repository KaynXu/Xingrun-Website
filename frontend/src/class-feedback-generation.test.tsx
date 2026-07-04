import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('./features/class-feedback/ClassFeedbackGenerationPage.tsx', import.meta.url), 'utf8');

test('class feedback generation page uses class-commentary api client', () => {
  assert.match(source, /from '..\/..\/classCommentary'/);
  assert.match(source, /apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(source, /createClassCommentaryTask/);
  assert.match(source, /createClassCommentaryTextTask/);
  assert.match(source, /fetchClassCommentaryTasks/);
  assert.match(source, /fetchClassCommentarySkills/);
  assert.match(source, /generateClassCommentaryFeedback/);
  assert.doesNotMatch(source, /api\/class-feedback/);
  assert.doesNotMatch(source, /currentUser\.token/);
});

test('class feedback generation page uses shadcn components for visible controls', () => {
  assert.match(source, /@\/components\/ui\/button/);
  assert.match(source, /@\/components\/ui\/card/);
  assert.match(source, /@\/components\/ui\/checkbox/);
  assert.match(source, /@\/components\/ui\/input/);
  assert.match(source, /@\/components\/ui\/popover/);
  assert.match(source, /@\/components\/ui\/progress/);
  assert.match(source, /@\/components\/ui\/select/);
  assert.match(source, /@\/components\/ui\/badge/);
  assert.match(source, /@\/components\/ui\/dialog/);
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

test('class feedback generation page exposes generated task history', () => {
  assert.match(source, /const \[historyTasks, setHistoryTasks\] = useState<ClassCommentaryTask\[]>\(\[]\);/);
  assert.match(source, /<DialogTrigger asChild>/);
  assert.match(source, /<Button type="button" variant="outline">/);
  assert.match(source, /<DialogTitle>生成历史<\/DialogTitle>/);
  assert.match(source, /<DialogDescription>/);
  assert.match(source, /handleSelectHistoryTask/);
  assert.match(source, /historyTasks\.map/);
  assert.match(source, /最近还没有生成记录/);
  assert.doesNotMatch(source, /<CardTitle>生成历史<\/CardTitle>/);
});

test('class feedback generation page saves transcript before generation', () => {
  assert.match(source, /if \(!trimmedConfirmedTranscript\) \{\s*setErrorMessage\('请先确认转写文本'\);/);
  assert.match(source, /const savedTask = task && canUseTranscript\s*\?\s*\(transcriptDirty\s*\?\s*await saveClassCommentaryTranscript\(task\.id, trimmedConfirmedTranscript\)\s*:\s*task\)\s*:\s*await createClassCommentaryTextTask\(Number\(selectedClassId\), trimmedConfirmedTranscript\);/);
  assert.match(source, /await generateClassCommentaryFeedback\(savedTask\.id, selectedSkillId, attendingStudentIds\)/);
});

test('class feedback generation page does not trim undefined persisted transcript', () => {
  assert.match(source, /const persistedTranscript = \(task\?\.confirmed_transcript_text \|\| task\?\.transcript_text \|\| ''\)\.trim\(\);/);
});

test('class feedback generation page allows manual transcript generation without audio task', () => {
  assert.match(source, /const canCreateManualTextTask = !task \|\| task\.status === 'uploaded' \|\| task\.status === 'transcribing';/);
  assert.match(source, /const canGenerate = !busy && !loadingClassStudents && hasTranscriptText && Boolean\(selectedClassId && selectedSkillId\) && \(canUseTranscript \|\| canCreateManualTextTask\) && \(!classStudents\.length \|\| attendingStudentIds\.length > 0\);/);
  assert.match(source, /disabled=\{loadingInitial\}/);
  assert.doesNotMatch(source, /disabled=\{loadingInitial \|\| \(!task && !confirmedTranscript\)\}/);
});

test('class feedback generation creates a new text task when the selected task is still transcribing', () => {
  assert.match(source, /const savedTask = task && canUseTranscript\s*\?\s*\(transcriptDirty\s*\?\s*await saveClassCommentaryTranscript\(task\.id, trimmedConfirmedTranscript\)\s*:\s*task\)\s*:\s*await createClassCommentaryTextTask\(Number\(selectedClassId\), trimmedConfirmedTranscript\);/);
});

test('class feedback generation page loads class students and renders attendance selection', () => {
  assert.match(source, /type ClassFeedbackStudent = \{\s*id: number;\s*name: string;/);
  assert.match(source, /apiFetch<\{ students: ClassFeedbackStudent\[] \}>\(`\/api\/classes\/\$\{encodeURIComponent\(selectedClassId\)\}\/students`\)/);
  assert.match(source, /const \[attendingStudentIds, setAttendingStudentIds\] = useState<number\[]>\(\[]\);/);
  assert.match(source, /setAttendingStudentIds\(nextStudents\.map\(\(item\) => item\.id\)\);/);
  assert.match(source, /<PopoverTrigger asChild>/);
  assert.match(source, /<Button type="button" variant="outline" disabled=\{!selectedClassId \|\| busy\}>\s*到课学生\s*<\/Button>/);
  assert.match(source, /<PopoverTitle>到课学生<\/PopoverTitle>/);
  assert.match(source, /<Checkbox/);
  assert.match(source, /全选/);
  assert.doesNotMatch(source, /type="checkbox"/);
  assert.doesNotMatch(source, /rounded-lg border border-border\/70 px-3 py-3/);
});

test('class feedback generation class select uses popper content for stable scrolling', () => {
  assert.match(source, /<SelectContent position="popper" className="max-h-72">/);
});
