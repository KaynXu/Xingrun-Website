import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('./features/class-feedback/ClassFeedbackGenerationPage.tsx', import.meta.url), 'utf8');
const alertDialogSource = readFileSync(new URL('../components/ui/alert-dialog.tsx', import.meta.url), 'utf8');

function cardSource(title: string): string {
  const start = source.indexOf(`<CardTitle>${title}</CardTitle>`);
  if (start < 0) {
    return '';
  }
  const end = source.indexOf('</Card>', start);
  return end < 0 ? source.slice(start) : source.slice(start, end + '</Card>'.length);
}

function functionSource(name: string, nextName: string): string {
  const start = source.indexOf(`function ${name}(`);
  if (start < 0) {
    return '';
  }
  const end = source.indexOf(`function ${nextName}(`, start);
  return end < 0 ? source.slice(start) : source.slice(start, end);
}

function assertSourceMatches(value: string, pattern: RegExp, message: string): void {
  assert.ok(pattern.test(value), message);
}

function assertSourceExcludes(value: string, pattern: RegExp, message: string): void {
  assert.ok(!pattern.test(value), message);
}

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
  assert.doesNotMatch(source, /@\/components\/ui\/table/);
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
  assert.match(source, /<Button type="button" variant="outline" disabled=\{busy \|\| generationLoading\}>/);
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
  assert.match(source, /await generateClassCommentaryFeedback\(\s*savedTask\.id,\s*selectedSkillId,\s*attendingStudentIds,\s*createClassCommentaryRequestId\('generation'\),\s*\)/);
});

test('class feedback generation page does not trim undefined persisted transcript', () => {
  assert.match(source, /const persistedTranscript = \(task\?\.confirmed_transcript_text \|\| task\?\.transcript_text \|\| ''\)\.trim\(\);/);
});

test('class feedback generation page allows manual transcript generation without audio task', () => {
  assert.match(source, /const canCreateManualTextTask = !task \|\| task\.status === 'uploaded' \|\| task\.status === 'transcribing';/);
  assert.match(source, /const canGenerate = !busy && !generationLoading && !loadingClassStudents && hasTranscriptText && Boolean\(selectedClassId && selectedSkillId\) && \(canUseTranscript \|\| canCreateManualTextTask\) && \(!classStudents\.length \|\| attendingStudentIds\.length > 0\);/);
  assert.match(source, /disabled=\{loadingInitial\}/);
  assert.doesNotMatch(source, /disabled=\{loadingInitial \|\| \(!task && !confirmedTranscript\)\}/);
});

test('transcript confirmation fills the upload task card without adding another page card', () => {
  const uploadCard = cardSource('上传与任务');

  assertSourceMatches(uploadCard, /<CardContent className="flex flex-1 flex-col gap-4">/, 'the upload Card content must fill the equal-height grid item');
  assertSourceMatches(uploadCard, /<p className="text-sm font-medium text-foreground">转写确认<\/p>/, 'transcript confirmation must stay inside the upload Card');
  assertSourceMatches(uploadCard, /<Badge variant="outline">\{transcriptStatusLabel\}<\/Badge>/, 'the transcript section must expose its current state');
  assertSourceMatches(uploadCard, /<Textarea\s+value=\{confirmedTranscript\}[\s\S]*className="min-h-56 flex-1 resize-none field-sizing-fixed"/, 'the transcript editor must absorb the remaining Card height and scroll internally');
  assertSourceExcludes(source, /<CardTitle>转写确认<\/CardTitle>/, 'transcript confirmation must not remain as a separate page-level Card');
});

test('completed tasks show completed progress and demote regeneration', () => {
  const uploadCard = cardSource('上传与任务');

  assertSourceMatches(source, /const hasSucceededGeneration = selectedGeneration\?\.status === 'succeeded';/, 'successful generation state must drive action hierarchy');
  assertSourceMatches(uploadCard, /转写 \{task\?\.status === 'transcribing' \? '进行中' : task\?\.status === 'transcribed' \|\| task\?\.status === 'generating' \|\| task\?\.status === 'ready' \? '已完成' : '未开始'\}/, 'transcription progress must finish after transcription');
  assertSourceMatches(uploadCard, /生成 \{task\?\.status === 'generating' \? '进行中' : task\?\.status === 'ready' \? '已完成' : '未开始'\}/, 'generation progress must finish when the task is ready');
  assertSourceMatches(uploadCard, /variant=\{hasSucceededGeneration \? 'outline' : 'default'\}[\s\S]*\{hasSucceededGeneration \? '重新生成' : '生成反馈包'\}/, 'regeneration must become secondary after a successful result');
});

test('class feedback generation creates a new text task when the selected task is still transcribing', () => {
  assert.match(source, /const savedTask = task && canUseTranscript\s*\?\s*\(transcriptDirty\s*\?\s*await saveClassCommentaryTranscript\(task\.id, trimmedConfirmedTranscript\)\s*:\s*task\)\s*:\s*await createClassCommentaryTextTask\(Number\(selectedClassId\), trimmedConfirmedTranscript\);/);
});

test('class feedback generation page loads class students and renders attendance selection', () => {
  assert.match(source, /type ClassFeedbackStudent = \{\s*id: number;\s*name: string;/);
  assert.match(source, /apiFetch<\{ students: ClassFeedbackStudent\[] \}>\(`\/api\/classes\/\$\{encodeURIComponent\(selectedClassId\)\}\/students`\)/);
  assert.match(source, /const \[attendingStudentIds, setAttendingStudentIds\] = useState<number\[]>\(\[]\);/);
  assert.match(source, /setAttendingStudentIds\(nextStudents\.map\(\(item\) => item\.id\)\);/);
  assert.match(source, /const attendanceListHeight = Math\.min\(224, Math\.max\(32, classStudents\.length \* 40 - 8\)\);/);
  assert.match(source, /<PopoverTrigger asChild>/);
  assert.match(source, /<Button type="button" variant="outline" disabled=\{!selectedClassId \|\| busy\}>\s*到课学生\s*<\/Button>/);
  assert.match(source, /<PopoverTitle>到课学生<\/PopoverTitle>/);
  assert.match(source, /<ScrollArea className="max-h-56 overflow-hidden" style=\{\{ height: attendanceListHeight \}\}>/);
  assert.match(source, /<Checkbox/);
  assert.match(source, /全选/);
  assert.doesNotMatch(source, /type="checkbox"/);
  assert.doesNotMatch(source, /rounded-lg border border-border\/70 px-3 py-3/);
});

test('class feedback generation page remembers selected coworker style for the current teacher', () => {
  assert.match(source, /readClassCommentarySkillPreference/);
  assert.match(source, /writeClassCommentarySkillPreference/);
  assert.match(source, /setSelectedSkillId\(\(currentValue\) => currentValue \|\| readClassCommentarySkillPreference\(currentUser, nextSkills\) \|\| \(nextSkills\[0\]\?\.id \|\| ''\)\);/);
  assert.match(source, /function handleSkillChange\(nextSkillId: string\) \{\s*setSelectedSkillId\(nextSkillId\);\s*writeClassCommentarySkillPreference\(currentUser, nextSkillId\);/);
  assert.match(source, /<Select value=\{selectedSkillId \|\| undefined\} onValueChange=\{handleSkillChange\}>/);
  assert.match(source, /<p className="text-sm font-medium text-foreground">同事测评风格<\/p>/);
  assert.match(source, /<SelectValue placeholder="请选择同事" \/>/);
  assert.match(source, /\{skills\.map\(\(item\) => \([\s\S]*\{item\.name\}[\s\S]*\)\)\}/);
});

test('class feedback generation class select uses popper content for stable scrolling', () => {
  assert.match(source, /<SelectContent position="popper" className="max-h-72">/);
});

test('class feedback result stays in its current card with a shadcn editor and generation switcher', () => {
  const feedbackCard = cardSource('反馈结果');

  assert.ok(feedbackCard, 'the existing feedback result Card must remain');
  assertSourceMatches(source, /const \[feedbackEditorText, setFeedbackEditorText\] = useState\(''\);/, 'feedback editor state is missing');
  assertSourceMatches(source, /const \[selectedGenerationId, setSelectedGenerationId\] = useState\(''\);/, 'selected generation state is missing');
  assertSourceMatches(source, /fetchClassCommentaryGenerations/, 'generation list client is not used');
  assertSourceMatches(source, /fetchClassCommentaryGeneration/, 'generation detail client is not used');
  assertSourceMatches(source, /fetchClassCommentaryFeedbackDraft/, 'generation draft client is not used');
  assertSourceMatches(feedbackCard, /<Textarea\s+value=\{feedbackEditorText\}\s+onChange=\{\(event\) => setFeedbackEditorText\(event\.target\.value\)\}/, 'feedback result Card must use the shadcn Textarea as its editor');
  assertSourceMatches(feedbackCard, /<Select value=\{selectedGenerationId \|\| undefined\} onValueChange=\{handleGenerationChange\} disabled=\{busy \|\| generationLoading\}>/, 'feedback result Card must use the shadcn Select and block switching during mutations and generation loads');
  assertSourceMatches(feedbackCard, /generations\.map\(\(generation\) => \(/, 'generation Select options are missing');
  assertSourceMatches(feedbackCard, /<SelectItem key=\{generation\.id\} value=\{String\(generation\.id\)\}>/, 'generation options must use shadcn SelectItem');
});

test('class feedback result actions use shadcn buttons and gate learning from server capability', () => {
  const feedbackCard = cardSource('反馈结果');

  assertSourceMatches(source, /fetchClassCommentaryCapabilities/, 'capability client is not imported');
  assertSourceMatches(source, /const \[capabilities, setCapabilities\] = useState/, 'server capability state is missing');
  assertSourceMatches(source, /fetchClassCommentaryCapabilities\(\)/, 'server capabilities are not fetched');
  assertSourceMatches(source, /fetchClassCommentaryCapabilities\(\)\.catch\(\(\) => disabledClassCommentaryCapabilities\)/, 'memory capability failure must not block the core feedback page');
  assertSourceMatches(feedbackCard, /<Button type="button" variant="outline" onClick=\{handleSaveFeedbackDraft\} disabled=\{!canSaveFeedbackDraft\}>\s*保存草稿\s*<\/Button>/, 'save draft must be a shadcn Button');
  assertSourceMatches(feedbackCard, /<Button type="button" variant="outline" onClick=\{\(\) => handleConfirmFeedback\(false\)\} disabled=\{!canConfirmFeedback\}>\s*确认但不学习\s*<\/Button>/, 'confirm without learning must be a shadcn Button independent of memory capability');
  assertSourceMatches(feedbackCard, /<Button type="button" onClick=\{\(\) => handleConfirmFeedback\(true\)\} disabled=\{!canConfirmFeedback \|\| !capabilities\.memory_learning_enabled\}>\s*确认并让 AI 学习修改\s*<\/Button>/, 'confirm and learn must be disabled when the server capability is off');
  assertSourceMatches(source, /saveClassCommentaryFeedbackDraft\(/, 'save draft client is not used');
  assertSourceMatches(source, /confirmClassCommentaryFeedback\(/, 'confirmation client is not used');
});

test('memory learning stays inside the feedback card and reuses shadcn actions', () => {
  const feedbackCard = cardSource('反馈结果');

  assertSourceMatches(source, /@\/components\/ui\/alert-dialog/, 'memory revoke must import the official shadcn AlertDialog');
  assertSourceMatches(source, /fetchClassCommentaryRevisionMemories/, 'memory status client is not used');
  assertSourceMatches(source, /retryClassCommentaryRevisionMemory/, 'memory retry client is not used');
  assertSourceMatches(source, /revokeClassCommentaryMemoryEvidence/, 'memory revoke client is not used');
  assertSourceMatches(feedbackCard, /本次学到的内容/, 'memory results must remain inside the current feedback result Card');
  assertSourceMatches(feedbackCard, /`对 \$\{selectedSkill\?\.name \|\| '该同事'\}测评风格的调整`/, 'teacher-style memory must name the selected distilled colleague skill');
  assertSourceMatches(feedbackCard, /: '学生情况'/, 'student memory must use product language');
  assertSourceMatches(feedbackCard, /<Badge variant=\{revisionMemorySummary\.status === 'failed'/, 'memory status must use the existing shadcn Badge');
  assertSourceMatches(feedbackCard, /<Button[\s\S]*onClick=\{handleRetryRevisionMemory\}[\s\S]*重试学习[\s\S]*<\/Button>/, 'memory retry must use a shadcn Button');
  assertSourceMatches(feedbackCard, /<AlertDialogTrigger asChild>[\s\S]*<Button[\s\S]*撤销我的来源[\s\S]*<\/Button>[\s\S]*<\/AlertDialogTrigger>/, 'evidence revoke must use a shadcn Button as the AlertDialog trigger');
  assertSourceMatches(feedbackCard, /<AlertDialogTitle>撤销这条学习来源\?<\/AlertDialogTitle>/, 'evidence revoke confirmation title is missing');
  assertSourceMatches(feedbackCard, /<AlertDialogDescription>[\s\S]*撤销后,[\s\S]*<\/AlertDialogDescription>/, 'evidence revoke confirmation description is missing');
  assertSourceMatches(feedbackCard, /<AlertDialogAction[\s\S]*variant="destructive"[\s\S]*onClick=\{\(\) => handleRevokeMemoryEvidence\(memory\.evidence_id\)\}[\s\S]*确认撤销[\s\S]*<\/AlertDialogAction>/, 'evidence revoke must require the destructive AlertDialog action');
  assertSourceMatches(alertDialogSource, /AlertDialogPrimitive\.Root/, 'the official shadcn AlertDialog component is missing');
  assertSourceMatches(alertDialogSource, /AlertDialogPrimitive\.Action/, 'the official shadcn AlertDialog action is missing');
  assertSourceExcludes(source, /<CardTitle>记忆学习<\/CardTitle>/, 'memory learning must not add a new page-level Card');
  assertSourceExcludes(source, /<DialogTitle>记忆学习<\/DialogTitle>/, 'memory learning must not add a custom workflow Dialog');
});

test('confirmation retry and revoke keep idempotency keys after unknown network outcomes', () => {
  const requestHelpers = source.slice(
    source.indexOf('type PendingClassCommentaryRequest'),
    source.indexOf('function canUseTranscriptState'),
  );
  const confirmationHandler = functionSource('handleConfirmFeedback', 'handleRetryRevisionMemory');
  const retryHandler = functionSource('handleRetryRevisionMemory', 'handleRevokeMemoryEvidence');
  const revokeHandler = functionSource('handleRevokeMemoryEvidence', 'handleDraftConflictOpenChange');

  assertSourceMatches(requestHelpers, /if \(currentRequest\?\.scopeKey === scopeKey\) \{\s*return currentRequest;/, 'the same mutation payload must reuse its pending request id');
  assertSourceMatches(requestHelpers, /if \(!serverResponded \|\| currentRequest\?\.requestId !== requestId\) \{\s*return currentRequest;/, 'unknown network outcomes must preserve the pending request id');
  assertSourceMatches(source, /const confirmationRequestRef = useRef<PendingClassCommentaryRequest \| null>\(null\);/, 'confirmation request identity must survive renders');
  assertSourceMatches(source, /const memoryRetryRequestRef = useRef<PendingClassCommentaryRequest \| null>\(null\);/, 'memory retry request identity must survive renders');
  assertSourceMatches(source, /const memoryRevokeRequestRef = useRef<PendingClassCommentaryRequest \| null>\(null\);/, 'memory revoke request identity must survive renders');

  assertSourceMatches(confirmationHandler, /const confirmationRequest = claimClassCommentaryRequest\([\s\S]*'confirmation',[\s\S]*confirmationRequestRef\.current = confirmationRequest;/, 'confirmation must claim one request id for its exact payload');
  assertSourceMatches(confirmationHandler, /confirmClassCommentaryFeedback\([\s\S]*confirmationRequest\.requestId,[\s\S]*\);/, 'confirmation must send the claimed request id');
  assertSourceMatches(confirmationHandler, /settleClassCommentaryRequest\([\s\S]*confirmationRequest\.requestId,[\s\S]*true,[\s\S]*\);/, 'confirmation success must rotate its request id');
  assertSourceMatches(confirmationHandler, /catch \(error\) \{[\s\S]*settleClassCommentaryRequest\([\s\S]*error instanceof ApiFetchError,[\s\S]*\);/, 'confirmation may rotate after an explicit server error but not an unknown network error');

  assertSourceMatches(retryHandler, /const retryRequest = claimClassCommentaryRequest\([\s\S]*'memory-retry',[\s\S]*memoryRetryRequestRef\.current = retryRequest;/, 'memory retry must claim a stable request id');
  assertSourceMatches(retryHandler, /retryClassCommentaryRevisionMemory\([\s\S]*retryRequest\.requestId,[\s\S]*\);/, 'memory retry must send the claimed request id');
  assertSourceMatches(retryHandler, /catch \(error\) \{[\s\S]*settleClassCommentaryRequest\([\s\S]*error instanceof ApiFetchError,[\s\S]*\);/, 'memory retry may rotate only after a known server result');

  assertSourceMatches(revokeHandler, /const revokeRequest = claimClassCommentaryRequest\([\s\S]*'memory-revoke',[\s\S]*memoryRevokeRequestRef\.current = revokeRequest;/, 'memory revoke must claim a stable request id');
  assertSourceMatches(revokeHandler, /revokeClassCommentaryMemoryEvidence\([\s\S]*revokeRequest\.requestId,[\s\S]*\);/, 'memory revoke must send the claimed request id');
  assertSourceMatches(revokeHandler, /catch \(error\) \{[\s\S]*settleClassCommentaryRequest\([\s\S]*error instanceof ApiFetchError,[\s\S]*\);/, 'memory revoke may rotate only after a known server result');
});

test('memory polling and actions use independent request tokens', () => {
  const generationChangeHandler = functionSource('handleGenerationChange', 'handleSaveFeedbackDraft');
  const retryHandler = functionSource('handleRetryRevisionMemory', 'handleRevokeMemoryEvidence');
  const revokeHandler = functionSource('handleRevokeMemoryEvidence', 'handleDraftConflictOpenChange');

  assertSourceMatches(source, /const memoryLoadRequestTokenRef = useRef\(0\);\s*const memoryActionRequestTokenRef = useRef\(0\);/, 'memory load and action request tokens must be separate refs');
  assertSourceMatches(generationChangeHandler, /selectedGenerationIdRef\.current = nextGenerationId;\s*memoryLoadRequestTokenRef\.current \+= 1;\s*setRevisionMemorySummary\(null\);/, 'generation switching must invalidate the prior revision load immediately');
  assertSourceExcludes(generationChangeHandler, /memoryActionRequestTokenRef\.current \+= 1/, 'generation switching must leave the in-flight action token responsible for releasing its own lock');
  for (const handler of [retryHandler, revokeHandler]) {
    assertSourceMatches(handler, /const loadRequestToken = memoryLoadRequestTokenRef\.current;/, 'memory actions must snapshot the current load scope without taking it over');
    assertSourceMatches(handler, /const actionRequestToken = \+\+memoryActionRequestTokenRef\.current;/, 'memory actions must claim their own action token');
    assertSourceExcludes(handler, /\+\+memoryLoadRequestTokenRef\.current/, 'memory actions must not invalidate the revision load token');
    assertSourceMatches(handler, /finally \{\s*if \(actionRequestToken === memoryActionRequestTokenRef\.current\) \{\s*setMemoryActionKey\(''\);/, 'the action token must always release its own button lock after a revision switch');
  }
});

test('memory polling treats read failures as transient and retries with backoff', () => {
  const effectStart = source.indexOf('  useEffect(() => {', source.indexOf('const attendanceListHeight'));
  const memoryPollingEffect = source.slice(effectStart, source.indexOf('  async function handleCreateTask', effectStart));

  assertSourceMatches(memoryPollingEffect, /setMemoryLoadError\('学习状态暂时不可用, 正在重试'\);/, 'poll failures must show a temporary unavailable message');
  assertSourceMatches(memoryPollingEffect, /pollingDelayMs = Math\.min\(pollingDelayMs \* 2, 30000\);\s*pollTimer = window\.setTimeout\(loadMemorySummary, pollingDelayMs\);/, 'poll failures must continue with bounded exponential backoff');
  assertSourceExcludes(memoryPollingEffect, /status:\s*'failed'/, 'a read failure must not fabricate a terminal failed summary');
  assertSourceMatches(source, /memoryLoadError \? \(\s*<Badge variant="outline">暂不可用<\/Badge>/, 'the feedback card must distinguish transient unavailability from a server failed status');
});

test('skill evolution is capability-gated and stays inside the existing feedback card', () => {
  const feedbackCard = cardSource('反馈结果');

  assertSourceMatches(
    feedbackCard,
    /\{capabilities\.skill_evolution_enabled && selectedSkill \? \(/,
    'skill evolution must be hidden unless the server enables the capability',
  );
  assertSourceMatches(feedbackCard, /\{selectedSkill\.name\}的测评风格/, 'the version entry must show the real colleague name');
  assertSourceMatches(feedbackCard, /<Dialog open=\{skillEvolutionDialogOpen\} onOpenChange=\{handleSkillEvolutionOpenChange\}>/, 'version review must reuse the shadcn Dialog');
  assertSourceMatches(feedbackCard, /<DialogTrigger asChild>\s*<Button type="button" size="xs" variant="outline">查看风格更新<\/Button>/, 'the version entry must use a shadcn Button');
  assertSourceMatches(feedbackCard, /<DialogTitle>\{selectedSkill\.name\}的测评风格<\/DialogTitle>/, 'the version dialog needs an accessible shadcn title');
  assertSourceMatches(feedbackCard, /AI 会从大家使用这个同事测评风格时确认的修改中整理可复用的调整\./, 'the shared distilled-skill learning scope must be explicit');
  assertSourceMatches(feedbackCard, /更新不会自动使用/, 'the no-auto-use rule must be explicit in the UI');
  assertSourceExcludes(source, /<CardTitle>反馈风格版本<\/CardTitle>/, 'skill evolution must not add another page-level Card');
});

test('skill evolution shows human-readable changes before using or restoring a version', () => {
  const feedbackCard = cardSource('反馈结果');

  assertSourceMatches(feedbackCard, /<Select value=\{selectedSkillVersionId \|\| undefined\} onValueChange=\{setSelectedSkillVersionId\}>/, 'version selection must use the shadcn Select');
  assertSourceMatches(feedbackCard, /selectedSkillVersion\.evaluation\.change_summary\.map\(\(change\) => \(/, 'candidate review must show the worker change summary');
  assertSourceMatches(feedbackCard, /本次建议的调整/, 'candidate changes need a human-readable heading');
  assertSourceMatches(feedbackCard, /有 \{selectedSkillVersion\.evaluation\.failed_sample_count\} 条历史反馈检查未通过/, 'failed checks must be summarized without exposing sample ids');
  assertSourceExcludes(feedbackCard, /selectedSkillVersion\.content_diff/, 'raw diffs must not be exposed in the teacher workflow');
  assertSourceExcludes(feedbackCard, /selectedSkillEvaluationRows/, 'technical evaluation rows must not be exposed in the teacher workflow');
  assertSourceExcludes(feedbackCard, /<Table>/, 'technical metric tables must not be exposed in the teacher workflow');
  assertSourceExcludes(feedbackCard, /有效任务|支持任务|评测|激活|回滚/, 'technical evolution terms must not be visible to teachers');
  assertSourceMatches(feedbackCard, /<AlertDialogTitle>使用这次风格更新\?<\/AlertDialogTitle>/, 'using an update must require the shadcn AlertDialog');
  assertSourceMatches(feedbackCard, /onClick=\{\(\) => handleChangeSkillVersion\('activate'\)\}/, 'the activation action is missing');
  assertSourceMatches(feedbackCard, /<AlertDialogTitle>恢复使用这个历史版本\?<\/AlertDialogTitle>/, 'restoring a version must require the shadcn AlertDialog');
  assertSourceMatches(feedbackCard, /onClick=\{\(\) => handleChangeSkillVersion\('rollback'\)\}/, 'the rollback action is missing');
});

test('skill evolution polls builds and keeps mutation request ids after unknown outcomes', () => {
  const candidateHandler = functionSource('handleCreateSkillCandidate', 'handleChangeSkillVersion');
  const versionHandler = functionSource('handleChangeSkillVersion', 'handleDraftConflictOpenChange');
  const pollingStart = source.indexOf('const requestToken = ++skillEvolutionLoadRequestTokenRef.current;');
  const pollingEffect = source.slice(pollingStart, source.indexOf('async function handleCreateTask', pollingStart));

  assertSourceMatches(source, /const skillCandidateRequestRef = useRef<PendingClassCommentaryRequest \| null>\(null\);/, 'candidate request identity must survive renders');
  assertSourceMatches(source, /const skillActivateRequestRef = useRef<PendingClassCommentaryRequest \| null>\(null\);/, 'activation request identity must survive renders');
  assertSourceMatches(source, /const skillRollbackRequestRef = useRef<PendingClassCommentaryRequest \| null>\(null\);/, 'rollback request identity must survive renders');
  assertSourceMatches(candidateHandler, /const candidateRequest = claimClassCommentaryRequest\([\s\S]*'skill-candidate',[\s\S]*skillCandidateRequestRef\.current = candidateRequest;/, 'candidate creation must claim a stable request id');
  assertSourceMatches(candidateHandler, /createClassCommentarySkillCandidate\([\s\S]*candidateRequest\.requestId,[\s\S]*\);/, 'candidate creation must send the stable request id');
  assertSourceMatches(candidateHandler, /catch \(error\) \{[\s\S]*settleClassCommentaryRequest\([\s\S]*error instanceof ApiFetchError,[\s\S]*\);/, 'candidate creation must retain its id after an unknown network result');
  assertSourceMatches(versionHandler, /const versionRequest = claimClassCommentaryRequest\([\s\S]*`skill-\$\{action\}`,[\s\S]*requestRef\.current = versionRequest;/, 'activate and rollback must claim payload-scoped request ids');
  assertSourceMatches(versionHandler, /expectedActiveVersionId,[\s\S]*versionRequest\.requestId/, 'version changes must send the active-version CAS pointer and request id');
  assertSourceMatches(versionHandler, /catch \(error\) \{[\s\S]*settleClassCommentaryRequest\([\s\S]*error instanceof ApiFetchError,[\s\S]*\);/, 'version changes must retain ids after unknown network results');
  assertSourceMatches(pollingEffect, /fetchClassCommentarySkillEvolution\(selectedSkillId\)/, 'the dialog must load the current server version state');
  assertSourceMatches(pollingEffect, /candidate_builds\.some\(\(build\) => !build\.is_terminal\)/, 'non-terminal candidate builds must keep polling');
  assertSourceMatches(pollingEffect, /pollingDelayMs = Math\.min\(pollingDelayMs \* 2, 30000\);/, 'temporary polling failures must retry with bounded backoff');
});

test('confirmation consumes the transaction-bound draft without a second draft read', () => {
  const confirmationHandler = functionSource('handleConfirmFeedback', 'handleRetryRevisionMemory');

  assert.ok(confirmationHandler, 'confirmation handler is missing');
  assertSourceMatches(
    confirmationHandler,
    /const \{\s*revision,\s*draft: nextDraft\s*\} = await confirmClassCommentaryFeedback\(/,
    'confirmation must consume the revision and draft returned by the same transaction',
  );
  assertSourceExcludes(
    confirmationHandler,
    /fetchClassCommentaryFeedbackDraft\(/,
    'confirmation must not replace its transaction-bound draft with a later live read',
  );
});

test('generation switching ignores stale async responses', () => {
  const generationChangeHandler = functionSource('handleGenerationChange', 'handleSaveFeedbackDraft');

  assertSourceMatches(source, /import \{ useEffect, useRef, useState, type ChangeEvent \} from 'react';/, 'generation switching needs refs for current request identity');
  assertSourceMatches(source, /const generationLoadRequestTokenRef = useRef\(0\);/, 'generation load request token ref is missing');
  assertSourceMatches(source, /const selectedGenerationIdRef = useRef\(''\);/, 'current generation ref is missing');
  assertSourceMatches(generationChangeHandler, /const requestToken = \+\+generationLoadRequestTokenRef\.current;/, 'each generation load must claim a new request token');
  assertSourceMatches(generationChangeHandler, /selectedGenerationIdRef\.current = nextGenerationId;/, 'the current generation ref must update before loading');
  const awaitPosition = generationChangeHandler.indexOf('await Promise.all');
  const tokenGuardPosition = generationChangeHandler.indexOf('requestToken !== generationLoadRequestTokenRef.current');
  const generationGuardPosition = generationChangeHandler.indexOf('selectedGenerationIdRef.current !== nextGenerationId');
  const editorWritePosition = generationChangeHandler.indexOf('setFeedbackEditorText(nextText)');
  assert.ok(awaitPosition >= 0, 'generation detail and draft must load asynchronously');
  assert.ok(tokenGuardPosition > awaitPosition, 'stale request token must be checked after the async load');
  assert.ok(generationGuardPosition > awaitPosition, 'the requested generation must still be selected after the async load');
  assert.ok(editorWritePosition > tokenGuardPosition && editorWritePosition > generationGuardPosition, 'generation state must only update after both stale-response guards');
});

test('draft conflicts retain local editor text in a shadcn dialog with explicit recovery actions', () => {
  const loadServerDraftHandler = functionSource('handleLoadServerDraft', 'handleCopyLocalDraft');

  assertSourceMatches(source, /const \[draftConflict, setDraftConflict\] = useState<\{\s*localText: string;\s*serverDraft: ClassCommentaryFeedbackDraft;\s*\} \| null>\(null\);/, 'draft conflict state must retain both local text and the server draft');
  assertSourceMatches(source, /error instanceof ApiFetchError && error\.status === 409 && error\.payload\?\.error === 'draft_version_conflict'/, 'draft CAS conflicts are not detected from the API response');
  assertSourceMatches(source, /setDraftConflict\(\{\s*localText: mutationFeedbackText,\s*serverDraft: currentDraft,\s*\}\);/, 'draft conflict handling must retain the text captured for the mutation');
  assertSourceMatches(source, /<Dialog open=\{Boolean\(draftConflict\)\} onOpenChange=\{handleDraftConflictOpenChange\}>/, 'draft conflict must use the shadcn Dialog');
  assertSourceMatches(source, /<DialogTitle>草稿版本冲突<\/DialogTitle>/, 'draft conflict dialog title is missing');
  assertSourceMatches(source, /onClick=\{handleLoadServerDraft\}[\s\S]*加载服务器版本/, 'load server draft action is missing');
  assertSourceMatches(source, /onClick=\{handleCopyLocalDraft\}[\s\S]*复制本地内容/, 'copy local draft action is missing');
  assertSourceMatches(loadServerDraftHandler, /const conflictGenerationId = draftConflict\.serverDraft\.generation_id;/, 'conflict recovery must use the server draft generation');
  assertSourceMatches(loadServerDraftHandler, /\[conflictGenerationId\]: \{/, 'the recovered draft must be cached under its own generation');
  assertSourceExcludes(loadServerDraftHandler, /\[selectedGeneration\.id\]: \{/, 'conflict recovery must not attach a server draft to whichever generation is currently selected');
  assertSourceMatches(
    loadServerDraftHandler,
    /if \(selectedGenerationIdRef\.current === String\(conflictGenerationId\)\) \{[\s\S]*setFeedbackEditorText\(draftConflict\.serverDraft\.feedback_text\);[\s\S]*setFeedbackDraft\(draftConflict\.serverDraft\);[\s\S]*\}/,
    'server text may replace the visible editor only when its generation is still selected',
  );
  assertSourceMatches(source, /navigator\.clipboard\.writeText\(draftConflict\.localText\)/, 'copy local action must use the retained local text');
});

test('revision history stays lightweight and copy ignores unsaved editor text', () => {
  const feedbackCard = cardSource('反馈结果');
  const selectedRevisionStart = source.indexOf('const selectedRevision =');
  const selectedRevisionEnd = source.indexOf(';', selectedRevisionStart);
  const selectedRevisionSource = source.slice(selectedRevisionStart, selectedRevisionEnd + 1);
  const copyHandler = functionSource('handleCopy', 'handleGenerationChange');

  assertSourceMatches(source, /const \[feedbackRevisions, setFeedbackRevisions\] = useState<ClassCommentaryFeedbackRevision\[]>\(\[]\);/, 'revision history state is missing');
  assertSourceMatches(source, /fetchClassCommentaryFeedbackRevisions\(/, 'revision history client is not used');
  assertSourceMatches(feedbackCard, /修订记录/, 'lightweight revision history is missing from the result Card');
  assertSourceMatches(feedbackCard, /feedbackRevisions\.map\(\(revision\) => \(/, 'revision history entries are missing');
  assertSourceMatches(feedbackCard, /revision\.revision_no/, 'revision history must identify revisions');
  assertSourceExcludes(source, /<(?:Card|Dialog)Title>修订历史<\/(?:Card|Dialog)Title>/, 'revision history must not add a separate Card or Dialog');
  assertSourceMatches(selectedRevisionSource, /item\.id === task\?\.latest_revision_id/, 'copy may only use the task current effective revision');
  assertSourceMatches(selectedRevisionSource, /item\.generation_id === selectedGeneration\?\.id/, 'the effective revision must belong to the selected generation');
  assertSourceMatches(source, /const copyText = resolveClassCommentaryCopyText\(\s*feedbackDraft,\s*selectedRevision,\s*selectedGeneration,\s*generationLoading,\s*\);/, 'copy must resolve persisted text through the executable precedence helper');
  assertSourceMatches(copyHandler, /if \(generationLoading \|\| !copyText\) \{\s*return;/, 'copy must be blocked while generation data is loading');
  assertSourceExcludes(copyHandler, /feedbackEditorText/, 'copy must not use unsaved editor text');
  assertSourceMatches(copyHandler, /navigator\.clipboard\.writeText\(copyText\)/, 'copy action must write the resolved saved text');
});

test('generation loading uses a safe empty state and restores the prior selection on failure', () => {
  const generationChangeHandler = functionSource('handleGenerationChange', 'handleSaveFeedbackDraft');
  const feedbackCard = cardSource('反馈结果');

  assertSourceMatches(generationChangeHandler, /setSelectedGenerationId\(nextGenerationId\);[\s\S]*setFeedbackEditorText\(''\);[\s\S]*setFeedbackDraft\(null\);[\s\S]*setLoadingGenerationId\(numericGenerationId\);/, 'uncached generation loads must clear visible feedback before awaiting the API');
  assertSourceMatches(generationChangeHandler, /selectedGenerationIdRef\.current = previousGenerationId;[\s\S]*setSelectedGenerationId\(previousGenerationId\);[\s\S]*setFeedbackEditorText\(previousEditorText\);[\s\S]*setFeedbackDraft\(previousDraft\);/, 'failed generation loads must restore the prior scoped state');
  assertSourceMatches(generationChangeHandler, /isClassCommentaryFeedbackRecordInScope\(generation, taskId, numericGenerationId\)/, 'generation responses must be checked against the requested scope');
  assertSourceMatches(generationChangeHandler, /draft && !isClassCommentaryFeedbackRecordInScope\(draft, taskId, numericGenerationId\)/, 'draft responses must be checked against the requested scope');
  assertSourceMatches(feedbackCard, /disabled=\{generationLoading \|\| !copyText\}/, 'copy must be disabled during generation loading');
  assertSourceMatches(feedbackCard, /disabled=\{busy \|\| generationLoading \|\| !selectedGeneration \|\| selectedGeneration\.status !== 'succeeded'\}/, 'the editor must be disabled during generation loading');
});

test('task switching clears version state and invalidates in-flight work immediately', () => {
  const resetHandler = functionSource('resetFeedbackVersionState', 'isCurrentFeedbackMutation');
  const historyHandler = functionSource('handleSelectHistoryTask', 'handleSkillChange');

  assertSourceMatches(resetHandler, /generationLoadRequestTokenRef\.current \+= 1;/, 'task reset must invalidate generation reads');
  assertSourceMatches(resetHandler, /feedbackMutationActiveRef\.current = false;/, 'task reset must release obsolete mutation ownership');
  assertSourceMatches(resetHandler, /feedbackMutationTokenRef\.current \+= 1;/, 'task reset must invalidate mutations');
  assertSourceMatches(resetHandler, /currentTaskIdRef\.current = nextTaskId;/, 'task reset must publish the new task identity first');
  assertSourceMatches(resetHandler, /setGenerations\(\[]\);[\s\S]*setSelectedGenerationId\(''\);[\s\S]*setFeedbackEditorText\(''\);[\s\S]*setFeedbackDraft\(null\);[\s\S]*setFeedbackRevisions\(\[]\);/, 'task reset must clear all old generation state');
  assertSourceMatches(resetHandler, /if \(releaseBusy\) \{\s*setBusy\(false\);/, 'explicit task navigation must release obsolete busy state');
  assertSourceMatches(historyHandler, /resetFeedbackVersionState\(nextTask\.id, true\);[\s\S]*setTask\(nextTask\);/, 'history navigation must clear feedback state before selecting the task');
  assertSourceMatches(source, /onClick=\{\(\) => handleSelectHistoryTask\(historyTask\)\}\s*disabled=\{busy \|\| generationLoading\}/, 'history rows must be disabled while work is in flight');
});

test('draft and confirmation mutations are scoped to their captured task and generation', () => {
  const saveHandler = functionSource('handleSaveFeedbackDraft', 'handleConfirmFeedback');
  const confirmationHandler = functionSource('handleConfirmFeedback', 'handleRetryRevisionMemory');

  for (const handler of [saveHandler, confirmationHandler]) {
    assertSourceMatches(handler, /const mutationTaskId = task\.id;/, 'mutation must capture its task');
    assertSourceMatches(handler, /const mutationGenerationId = selectedGeneration\.id;/, 'mutation must capture its generation');
    assertSourceMatches(handler, /const mutationToken = \+\+feedbackMutationTokenRef\.current;/, 'mutation must capture an operation token');
    assertSourceMatches(handler, /if \(!isCurrentFeedbackMutation\(mutationTaskId, mutationGenerationId, mutationToken\)\) \{\s*return;/, 'mutation response must be ignored after scope changes');
    assertSourceMatches(handler, /finally \{\s*if \(isCurrentFeedbackMutation\(mutationTaskId, mutationGenerationId, mutationToken\)\) \{\s*feedbackMutationActiveRef\.current = false;\s*setBusy\(false\);/, 'obsolete mutation finally blocks must not own current busy state');
  }
  assertSourceMatches(saveHandler, /isClassCommentaryFeedbackRecordInScope\(nextDraft, mutationTaskId, mutationGenerationId\)/, 'saved draft responses must match mutation scope');
  assertSourceMatches(confirmationHandler, /isClassCommentaryFeedbackRecordInScope\(revision, mutationTaskId, mutationGenerationId\)/, 'revision responses must match mutation scope');
  assertSourceMatches(confirmationHandler, /isClassCommentaryFeedbackRecordInScope\(nextDraft, mutationTaskId, mutationGenerationId\)/, 'transaction-bound draft responses must match mutation scope');
  assertSourceMatches(source, /if \(feedbackMutationActiveRef\.current\) \{\s*return;\s*\}\s*targetGenerationId = targetGeneration\.id;/, 'automatic generation selection must not invalidate an active mutation');
});

test('class feedback page adds no raw controls, custom modal, or custom stylesheet', () => {
  const classFeedbackFiles = readdirSync(new URL('./features/class-feedback/', import.meta.url));

  assertSourceExcludes(source, /<(?:button|select|textarea)\b/, 'page must not use raw button, select, or textarea controls');
  assertSourceExcludes(source, /role=["']dialog["']/, 'page must not implement a custom dialog role');
  assertSourceExcludes(source, /createPortal/, 'page must not create a custom modal portal');
  assertSourceExcludes(source, /import\s+['"][^'"]+\.(?:css|less|sass|scss)['"]/, 'page must not import a custom stylesheet');
  assert.deepEqual(classFeedbackFiles.filter((name) => /\.(?:css|less|sass|scss)$/.test(name)), []);
});
