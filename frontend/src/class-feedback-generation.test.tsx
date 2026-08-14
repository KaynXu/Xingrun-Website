import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('./features/class-feedback/ClassFeedbackGenerationPage.tsx', import.meta.url), 'utf8');
const learningGraphDialogSource = readFileSync(
  new URL('./features/class-feedback/StudentLearningGraphDialog.tsx', import.meta.url),
  'utf8',
);
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
  assert.match(source, /generationRequest = claimClassCommentaryRequest\([\s\S]*'generation',[\s\S]*await generateClassCommentaryFeedback\(\s*savedTask\.id,\s*selectedSkillId,\s*attendingStudentIds,\s*generationRequest\.requestId,\s*\)/);
});

test('class feedback generation page does not trim undefined persisted transcript', () => {
  assert.match(source, /const persistedTranscript = \(task\?\.confirmed_transcript_text \|\| task\?\.transcript_text \|\| ''\)\.trim\(\);/);
});

test('class feedback generation page allows manual transcript generation without audio task', () => {
  assert.match(source, /const canCreateManualTextTask = !task \|\| task\.status === 'uploaded' \|\| task\.status === 'transcribing';/);
  assert.match(source, /const attendanceReadyForGeneration = capabilities\.structured_feedback_enabled[\s\S]*\? attendingStudentIds\.length > 0[\s\S]*: !classStudents\.length \|\| attendingStudentIds\.length > 0;/);
  assert.match(source, /const canGenerate = capabilitiesState === 'ready'[\s\S]*uncertainStudentRetryGenerationId === null[\s\S]*!isTaskReadOnly[\s\S]*attendanceReadyForGeneration;/);
  assert.match(source, /disabled=\{loadingInitial \|\| isTaskReadOnly\}/);
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

test('batch-isolated generation shows one class call and blocks unavailable context', () => {
  const uploadCard = cardSource('上传与任务');

  assertSourceMatches(source, /batch_isolated_v3_enabled: false/, 'batch-isolated generation capability must fail closed by default');
  assertSourceMatches(source, /const classGenerationCallCount = attendingStudentIds\.length > 0[\s\S]*\? capabilities\.class_commentary_generation_call_count[\s\S]*: 0;/, 'one class generation must use the server capability');
  assertSourceMatches(source, /classGenerationMaxCredits[\s\S]*student_history_memory_v2_max_credits_per_student/, 'maximum credit impact must use the server capability');
  assertSourceMatches(uploadCard, /data-testid="generation-cost-impact"[\s\S]*1 次整班生成[\s\S]*一次返回全部到课学生点评[\s\S]*点额度/, 'generation cost impact must explain the single class call before the action');
  assertSourceMatches(uploadCard, /capabilitiesState === 'unavailable'[\s\S]*额度与调用次数暂不可用, 当前不能发起生成/, 'unavailable capabilities must show unknown cost instead of a fabricated one-call estimate');
  assertSourceMatches(source, /getClassCommentaryBatchGenerationUnavailableReason\(capabilities\)/, 'generation readiness must use the shared batch capability contract');
  assertSourceMatches(uploadCard, /batchGenerationUnavailableReason[\s\S]*本次将发起/, 'the disabled reason must replace the normal one-call impact message');
  assertSourceMatches(source, /const \[capabilitiesState, setCapabilitiesState\] = useState<ClassCommentaryCapabilitiesState>\('loading'\)/, 'capability loading state must be explicit');
  assertSourceMatches(source, /const canGenerate = capabilitiesState === 'ready' && generationContextReady/, 'generation must stay disabled until capability and isolated context are ready');
  assertSourceMatches(uploadCard, /data-testid="student-generation-progress"[\s\S]*总计[\s\S]*等待[\s\S]*生成中[\s\S]*已完成[\s\S]*失败/, 'aggregate student run progress must remain class-level');
  assertSourceExcludes(uploadCard, /memory_context|prompt_payload|historical/i, 'the progress surface must not expose private prompt or memory context');
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
  assert.match(source, /<Select value=\{selectedSkillId\} onValueChange=\{handleSkillChange\}>/);
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
  assertSourceMatches(feedbackCard, /<Textarea[\s\S]*value=\{previewRevision \? previewRevision\.final_feedback_text : feedbackEditorText\}[\s\S]*handlePlainFeedbackChange/, 'legacy feedback must keep the shadcn Textarea editor');
  assertSourceMatches(feedbackCard, /showStructuredFeedbackEditor[\s\S]*structuredFeedbackAccordion/, 'supported structured feedback must render in the same Card');
  assertSourceMatches(source, /@\/components\/ui\/accordion/, 'structured feedback must use the project shadcn Accordion');
  assertSourceMatches(feedbackCard, /<Select value=\{selectedGenerationId\} onValueChange=\{handleGenerationChange\} disabled=\{busy \|\| generationLoading\}>/, 'feedback result Card must use a controlled shadcn Select and block switching during mutations and generation loads');
  assertSourceMatches(feedbackCard, /generations\.map\(\(generation\) => \(/, 'generation Select options are missing');
  assertSourceMatches(feedbackCard, /<SelectItem key=\{generation\.id\} value=\{String\(generation\.id\)\}>/, 'generation options must use shadcn SelectItem');
});

test('class feedback result actions use shadcn buttons and gate learning from server capability', () => {
  const feedbackCard = cardSource('反馈结果');

  assertSourceMatches(source, /loadClassCommentaryCapabilities/, 'capability client is not imported');
  assertSourceMatches(source, /const \[capabilities, setCapabilities\] = useState/, 'server capability state is missing');
  assertSourceMatches(source, /loadClassCommentaryCapabilities\(\)/, 'server capabilities are not fetched');
  assertSourceMatches(source, /loadClassCommentaryCapabilities\(\)[\s\S]*setCapabilitiesState\(nextCapabilitiesResult\.state\)/, 'capability failure must remain distinguishable from a disabled server feature');
  assertSourceMatches(feedbackCard, /<Button type="button" variant="outline" onClick=\{handleSaveFeedbackDraft\} disabled=\{!canSaveFeedbackDraft\}>\s*保存草稿\s*<\/Button>/, 'save draft must be a shadcn Button');
  assertSourceMatches(feedbackCard, /<Button type="button" variant="outline" onClick=\{\(\) => handleConfirmFeedback\(false\)\} disabled=\{!canConfirmFeedback\}>\s*确认但不学习\s*<\/Button>/, 'confirm without learning must be a shadcn Button independent of memory capability');
  assertSourceMatches(feedbackCard, /disabled=\{!canConfirmFeedback \|\| !capabilities\.memory_learning_enabled\}[\s\S]*确认并让 AI 学习修改/, 'confirm and learn must keep the Mem0 learning prerequisite');
  assertSourceMatches(source, /saveClassCommentaryFeedbackDraft\(/, 'save draft client is not used');
  assertSourceMatches(source, /confirmClassCommentaryFeedback\(/, 'confirmation client is not used');
});

test('supported structured feedback is editable while unsupported and invalid schemas fail closed', () => {
  const feedbackCard = cardSource('反馈结果');

  assertSourceMatches(source, /const taskLatestRevision = feedbackRevisions\.find\(\(item\) => item\.id === task\?\.latest_revision_id\) \|\| null;/, 'task-level latest revision must gate legacy editing even when another generation is selected');
  assertSourceMatches(source, /taskLatestRevision\?\.feedback_schema_status/, 'task latest revision status must participate in the fail-closed gate');
  assertSourceMatches(source, /isClassCommentaryTaskLatestSchemaCompatible\(/, 'task latest revision schema must use the asymmetric compatibility gate');
  assertSourceMatches(source, /status === 'unsupported' \|\| status === 'invalid'/, 'unknown and invalid schemas must remain read-only');
  assertSourceMatches(source, /const structuredFeedbackMode = selectedGeneration\?\.feedback_schema_status === 'supported'/, 'known v1 generations must enter structured mode');
  assertSourceMatches(source, /const canSaveFeedbackDraft = !isTaskReadOnly\s*&& !feedbackSchemaReadOnly/, 'schema read-only mode must block draft writes');
  assertSourceMatches(source, /const canConfirmFeedback = !isTaskReadOnly\s*&& !feedbackSchemaReadOnly/, 'schema read-only mode must block confirmation writes');
  assertSourceMatches(feedbackCard, /readOnly=\{Boolean\(revisionPreview\) \|\| isTaskReadOnly \|\| feedbackSchemaReadOnly\}/, 'compatibility text must remain selectable without becoming editable');
  assertSourceMatches(source, /当前版本暂不支持编辑, 可查看和复制现有内容\./, 'unsupported feedback needs an actionable notice');
  assertSourceMatches(source, /!nextEditor\.feedbackText && !generationDetail\.feedback_schema_version/, 'structured nonterminal generations must not inherit another generation text');
  assertSourceMatches(source, /反馈结构校验失败[\s\S]*本次额度占用已释放[\s\S]*请重新生成/, 'invalid structured generation errors must be actionable');
});

test('generation failures consume the complete envelope and localize reservation errors', () => {
  const generationErrorHelper = functionSource('getClassCommentaryGenerationErrorMessage', 'formatClassCommentaryTime');
  const providerErrorHelper = functionSource('classCommentaryProviderFailureMessage', 'classCommentaryGenerationValidationMessage');
  const validationErrorHelper = functionSource('classCommentaryGenerationValidationMessage', 'getTaskErrorMessage');
  const generationHandler = functionSource('handleGenerate', 'handleCopy');

  assertSourceMatches(generationHandler, /normalizeClassCommentaryTask\([\s\S]*normalizeClassCommentaryGeneration\(/, 'failed generation responses must normalize both task and generation records');
  assertSourceMatches(generationHandler, /setTask\(failedTask\);[\s\S]*setGenerations\([\s\S]*failedGeneration/, 'the complete failed envelope must replace the visible task and generation state');
  assertSourceMatches(generationHandler, /nextGeneration\.status === 'failed'[\s\S]*setFeedbackEditorText\(''\)[\s\S]*setGenerationProgressError\([\s\S]*classCommentaryStudentGenerationFailureMessage/, 'HTTP 200 terminal failures must show the localized provider failure instead of opening an empty editor');
  assertSourceMatches(generationHandler, /setErrorMessage\(getClassCommentaryGenerationErrorMessage\(error\)\);/, 'generation errors must use the localized mapper');
  assertSourceMatches(validationErrorHelper, /structured_feedback_invalid[\s\S]*反馈结构校验失败[\s\S]*本次额度占用已释放[\s\S]*请重新生成/, 'invalid structured output must keep its stable actionable message');
  assertSourceMatches(validationErrorHelper, /student_feedback_missing_skill_emoji[\s\S]*没有遵循所选同事的表情风格[\s\S]*本次额度占用已释放/, 'Skill emoji failures must expose the real quality-gate reason');
  assertSourceMatches(generationErrorHelper, /attending_student_ids is required[\s\S]*请至少选择一名到课学生后重新生成/, 'an empty explicit attendance request must stay localized');
  assertSourceMatches(generationErrorHelper, /student_feedback_no_eligible_students[\s\S]*没有可生成的到课学生, 请检查到课名单后重新生成/, 'an empty eligible scope must explain how to correct the attendance roster');
  assertSourceMatches(generationErrorHelper, /student_roster_name_ambiguous[\s\S]*到课名单存在无法区分的重名, 请调整到课名单后重新生成/, 'ambiguous roster names must explain how to correct the attendance scope');
  assertSourceMatches(providerErrorHelper, /provider_timeout[\s\S]*系统未自动重复调用[\s\S]*本次额度占用已释放/, 'provider timeouts must explain the no-replay and released-hold safety behavior');
  assertSourceMatches(providerErrorHelper, /provider_dispatch_interrupted[\s\S]*避免重复扣费[\s\S]*系统未自动重发/, 'interrupted provider dispatches must explain why automatic replay is blocked');
});

test('isolated generation polling publishes only terminal complete output and safely retries failed runs', () => {
  const feedbackCard = cardSource('反馈结果');
  const retryHandler = functionSource('handleRetryFailedStudentRuns', 'handleCopy');

  assertSourceMatches(source, /const activeStudentGeneration = generations\.find\(\(generation\) => \([\s\S]*generation\.status === 'generating'[\s\S]*generation\.student_history_memory_mode === 'isolated_v2'/, 'only frozen isolated generations should use student-run polling');
  assertSourceMatches(source, /fetchClassCommentaryGeneration\([\s\S]*nextGeneration\.status !== 'generating'[\s\S]*fetchClassCommentaryTask/, 'polling must wait for a terminal generation before publishing task state');
  assertSourceMatches(source, /if \(nextGeneration\.status === 'failed'\) \{[\s\S]*setFeedbackEditorText\(''\);[\s\S]*return;/, 'failed aggregate generations must clear partial feedback');
  assertSourceMatches(source, /const nextEditor = createGenerationEditorState\([\s\S]*setFeedbackEditorText\(nextEditor\.feedbackText\)/, 'only successful terminal generations may populate the editor');
  assertSourceMatches(source, /const failedStudentRunIds =[\s\S]*\.filter\(\(run\) => run\.status === 'failed'\)/, 'only failed student runs may enter the retry set');
  assertSourceMatches(retryHandler, /selectedGeneration\.status !== 'failed'[\s\S]*retryStudentIds = \[\.\.\.failedStudentRunIds\][\s\S]*retryClassCommentaryStudentGenerationRuns\(/, 'retry must target the frozen failed-run set only');
  assertSourceMatches(retryHandler, /claimClassCommentaryRequest\([\s\S]*'student-generation-retry'[\s\S]*retryRequest\.requestId/, 'student-run retry must reuse a stable request id across transport failures');
  assertSourceMatches(retryHandler, /isClassCommentaryMutationOutcomeAmbiguous\(error\)[\s\S]*fetchClassCommentaryGeneration\(\s*retryTaskId,\s*retryGenerationId,[\s\S]*setGenerations\([\s\S]*canonicalGeneration/, 'an ambiguous retry response must reconcile the exact generation into canonical state');
  assertSourceMatches(retryHandler, /canonicalGeneration\.status !== 'failed'[\s\S]*settleClassCommentaryRequest\([\s\S]*setUncertainStudentRetryGenerationId\(null\)/, 'a retry id may clear only after canonical state proves the mutation progressed');
  assertSourceMatches(source, /uncertainStudentRetryGenerationId === null[\s\S]*!generations\.some\(\(generation\) => generation\.status === 'generating'/, 'new generation must stay blocked while retry outcome is unknown or an isolated generation is active');
  assertSourceMatches(feedbackCard, /data-testid="student-generation-partial-failure"[\s\S]*反馈包未发布[\s\S]*不会被当成完整反馈包[\s\S]*安全重试失败学生/, 'partial success must be visibly blocked and safely retryable');
  assertSourceExcludes(feedbackCard, /prompt_payload_snapshot|memory_context_snapshot/, 'the result card must never expose internal snapshots');
});

test('generation request ids survive ambiguous proxy failures', () => {
  const generationHandler = functionSource('handleGenerate', 'handleRetryFailedStudentRuns');

  assertSourceMatches(generationHandler, /isClassCommentaryMutationOutcomeAmbiguous\(error\)/, 'generation errors must classify proxy outcomes before clearing request identity');
  assertSourceMatches(generationHandler, /validatedTerminalResponse[\s\S]*settleClassCommentaryRequest\([\s\S]*validatedTerminalResponse/, 'generation request identity must clear only for a validated terminal response');
  assertSourceMatches(generationHandler, /throw new Error\('生成响应范围不一致'\);[\s\S]*settleClassCommentaryRequest\(/, 'success must validate task and generation scope before clearing request identity');
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

test('student growth entry stays inside each student editor and uses one shared dialog', () => {
  const accordionStart = source.indexOf('const structuredFeedbackAccordion');
  const accordionEnd = source.indexOf('\n  return (\n    <div', accordionStart);
  const accordionSource = source.slice(accordionStart, accordionEnd);

  assertSourceMatches(source, /StudentLearningGraphDialog/, 'the shared student growth dialog must be mounted once');
  assertSourceMatches(accordionSource, /<AccordionContent[\s\S]*学生成长轨迹[\s\S]*<\/AccordionContent>/, 'the growth entry must stay in the expanded student content');
  assertSourceExcludes(accordionSource.match(/<AccordionTrigger>[\s\S]*?<\/AccordionTrigger>/)?.[0] || '', /<Button/, 'the accordion trigger must not contain a nested button');
  assertSourceMatches(accordionSource, /handleOpenStudentLearningGraph\(item\)/, 'the entry must use the server-owned student item');
  assertSourceMatches(accordionSource, /capabilities\.graph_enabled/, 'the graph entry must be capability gated');
  assertSourceExcludes(source, /api\/class-feedback/, 'the new flow must remain in the class-commentary namespace');
});

test('student growth dialog covers safe product states without exposing graph internals', () => {
  for (const stateTestId of [
    'student-learning-graph-loading',
    'student-learning-graph-empty',
    'student-learning-graph-unavailable',
    'student-learning-graph-needs-mapping',
    'student-learning-graph-failed',
  ]) {
    assertSourceMatches(
      learningGraphDialogSource,
      new RegExp(`data-testid="${stateTestId}"`),
      `${stateTestId} is missing`,
    );
  }
  assertSourceMatches(learningGraphDialogSource, /pending: '学习中'/, 'pending status needs product copy');
  assertSourceMatches(learningGraphDialogSource, /learned: '已学习'/, 'learned status needs product copy');
  assertSourceMatches(learningGraphDialogSource, /needs_mapping: '待匹配知识点'/, 'needs-mapping status needs product copy');
  assertSourceMatches(learningGraphDialogSource, /failed: '学习失败'/, 'failed status needs product copy');
  assertSourceMatches(learningGraphDialogSource, /当前知识点状态/, 'current states are missing');
  assertSourceMatches(learningGraphDialogSource, /状态变化/, 'timeline is missing');
  assertSourceMatches(learningGraphDialogSource, /查看第 \{event\.evidence\.revision_no\} 次已确认反馈证据/, 'evidence provenance is missing');
  assertSourceMatches(learningGraphDialogSource, /本次使用的教学方法/, 'teaching methods are missing');
  assertSourceMatches(learningGraphDialogSource, /下一步建议/, 'next steps are missing');
  assertSourceMatches(learningGraphDialogSource, /本次生成参考了/, 'used evidence is missing');
  assertSourceExcludes(learningGraphDialogSource, />[^<]*(?:Semantica|node id|edge id|Cypher|SPARQL)[^<]*</i, 'teacher-facing copy must hide graph implementation terms');
  assertSourceExcludes(learningGraphDialogSource, /\b\d+%\b/, 'the UI must not fabricate mastery percentages');
});

test('student growth requests fail closed on stale student task or subject responses', () => {
  assertSourceMatches(
    learningGraphDialogSource,
    /currentScopeKeyRef\.current !== scopeKey/,
    'stale student responses must be ignored',
  );
  assertSourceMatches(
    learningGraphDialogSource,
    /retryToken !== retryRequestTokenRef\.current/,
    'stale retry responses must be ignored after the dialog scope changes',
  );
  assertSourceMatches(
    learningGraphDialogSource,
    /!subjectKey\.trim\(\)[\s\S]*课程科目范围缺失/,
    'a missing subject scope must fail closed before rendering graph data',
  );
  assertSourceMatches(
    learningGraphDialogSource,
    /isClassCommentaryStudentLearningGraphSummaryInScope\([\s\S]*taskId,[\s\S]*studentId,[\s\S]*subjectKey/,
    'task student and subject scope must be checked before rendering',
  );
  assertSourceMatches(
    learningGraphDialogSource,
    /nextSummary\.sync_status === 'pending'[\s\S]*window\.setTimeout\(loadSummary/,
    'pending graph learning must poll automatically',
  );
  assertSourceMatches(
    learningGraphDialogSource,
    /isClassCommentaryMutationOutcomeAmbiguous\(error\)/,
    'retry request identity must survive ambiguous outcomes',
  );
  const confirmationHandler = functionSource('handleConfirmFeedback', 'handleRetryRevisionMemory');
  assertSourceExcludes(confirmationHandler, /LearningGraph|graph-retry|learning-graph/, 'confirmation must not start graph work from the browser');
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
  assertSourceMatches(feedbackCard, /有效修改 \$\{skillEvolution\.eligibility\.effective_task_count\}\/\$\{skillEvolution\.eligibility\.min_effective_tasks\}/, 'the dialog must show the current real-change count and threshold');
  assertSourceMatches(feedbackCard, /每个课堂只计最新一次确认并学习的真实修改, 原样确认不计入\./, 'the five-change counting rule must be visible');
  assertSourceExcludes(source, /<CardTitle>反馈风格版本<\/CardTitle>/, 'skill evolution must not add another page-level Card');
});

test('skill evolution shows human-readable changes before using or restoring a version', () => {
  const feedbackCard = cardSource('反馈结果');

  assertSourceMatches(feedbackCard, /<Select value=\{selectedSkillVersionId\} onValueChange=\{setSelectedSkillVersionId\}>/, 'version selection must use the controlled shadcn Select');
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
  const editorWritePosition = generationChangeHandler.indexOf('setFeedbackEditorText(nextEditor.feedbackText)');
  assert.ok(awaitPosition >= 0, 'generation detail and draft must load asynchronously');
  assert.ok(tokenGuardPosition > awaitPosition, 'stale request token must be checked after the async load');
  assert.ok(generationGuardPosition > awaitPosition, 'the requested generation must still be selected after the async load');
  assert.ok(editorWritePosition > tokenGuardPosition && editorWritePosition > generationGuardPosition, 'generation state must only update after both stale-response guards');
});

test('draft conflicts retain local editor text in a shadcn dialog with explicit recovery actions', () => {
  const loadServerDraftHandler = functionSource('handleLoadServerDraft', 'handleCopyLocalDraft');

  assertSourceMatches(source, /type StructuredDraftConflict = \{[\s\S]*workspaceKey: string;[\s\S]*localItems: ClassCommentaryStudentFeedbackItem\[];[\s\S]*serverDraft: ClassCommentaryFeedbackDraft;/, 'draft conflict state must retain scoped local items and the server draft');
  assertSourceMatches(source, /error instanceof ApiFetchError && error\.status === 409 && error\.payload\?\.error === 'draft_version_conflict'/, 'draft CAS conflicts are not detected from the API response');
  assertSourceMatches(source, /setDraftConflict\(\{[\s\S]*workspaceKey: mutationWorkspaceKey,[\s\S]*localItems: mutationItems,[\s\S]*serverDraft: currentDraft,[\s\S]*attemptedExpectedDraftVersion: expectedDraftVersion,/, 'draft conflict handling must retain the complete local snapshot');
  assertSourceMatches(source, /<Dialog open=\{Boolean\(draftConflict\)\} onOpenChange=\{handleDraftConflictOpenChange\}>/, 'draft conflict must use the shadcn Dialog');
  assertSourceMatches(source, /<DialogTitle>草稿版本冲突<\/DialogTitle>/, 'draft conflict dialog title is missing');
  assertSourceMatches(source, /onClick=\{handleLoadServerDraft\}[\s\S]*加载服务器版本/, 'load server draft action is missing');
  assertSourceMatches(source, /onClick=\{handleCopyLocalDraft\}[\s\S]*复制本地内容/, 'copy local draft action is missing');
  assertSourceMatches(loadServerDraftHandler, /const conflictGenerationId = draftConflict\.serverDraft\.generation_id;/, 'conflict recovery must use the server draft generation');
  assertSourceMatches(loadServerDraftHandler, /conflictWorkspaceKey !== draftConflict\.workspaceKey/, 'conflict recovery must verify the task generation workspace key');
  assertSourceMatches(loadServerDraftHandler, /\[conflictWorkspaceKey\]: \{/, 'the recovered draft must be cached under its exact workspace key');
  assertSourceMatches(
    loadServerDraftHandler,
    /currentTaskIdRef\.current === draftConflict\.serverDraft\.task_id[\s\S]*selectedGenerationIdRef\.current === String\(conflictGenerationId\)[\s\S]*setFeedbackEditorText\(serverText\);[\s\S]*setFeedbackDraft\(draftConflict\.serverDraft\);/,
    'server text may replace the visible editor only when its generation is still selected',
  );
  assertSourceMatches(source, /deriveClassCommentaryStructuredFeedbackText\(draftConflict\.localItems\)/, 'copy local action must use the retained structured local items');
});

test('revision history opens immutable previews while copy uses current editor text', () => {
  const feedbackCard = cardSource('反馈结果');
  const taskLatestRevisionStart = source.indexOf('const taskLatestRevision =');
  const taskLatestRevisionEnd = source.indexOf(';', taskLatestRevisionStart);
  const taskLatestRevisionSource = source.slice(taskLatestRevisionStart, taskLatestRevisionEnd + 1);
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
  assertSourceMatches(taskLatestRevisionSource, /item\.id === task\?\.latest_revision_id/, 'copy may only use the task current effective revision');
  assertSourceMatches(selectedRevisionSource, /taskLatestRevision\?\.generation_id === selectedGeneration\?\.id/, 'the effective revision must belong to the selected generation');
  assertSourceMatches(feedbackCard, /onClick=\{\(\) => handleOpenRevisionPreview\(revision\)\}/, 'revision rows must be selectable');
  assertSourceMatches(source, /revisionPreviewKey: buildClassCommentaryRevisionPreviewKey\(task\.id, revision\.id\)/, 'revision preview state must be isolated from the generation editor');
  assertSourceMatches(feedbackCard, /返回当前编辑/, 'immutable preview must provide a return action');
  assertSourceMatches(source, /deriveClassCommentaryStructuredFeedbackText\(displayedStudentFeedbackItems\)/, 'copy all must derive from current visible student items');
  assertSourceMatches(copyHandler, /if \(generationLoading \|\| !copyText\) \{\s*return;/, 'copy must be blocked while generation data is loading');
  assertSourceMatches(copyHandler, /navigator\.clipboard\.writeText\(copyText\)/, 'copy action must write the resolved saved text');
});

test('copy always follows visible editor text and announces a transient confirmation', () => {
  const feedbackCard = cardSource('反馈结果');
  const copyResolution = source.slice(
    source.indexOf('const persistedCopyText ='),
    source.indexOf('const currentContentConfirmed ='),
  );
  const copyNoticeHelper = functionSource('showCopyNotice', 'resetFeedbackVersionState');

  assertSourceMatches(copyResolution, /: feedbackEditorText \|\| persistedCopyText;/, 'plain and fail-closed copy must prefer the text visible in the editor');
  assertSourceExcludes(copyResolution, /feedbackSchemaReadOnly\s*\?\s*persistedCopyText/, 'schema conflicts must not copy hidden persisted text over the visible editor');
  assertSourceMatches(copyNoticeHelper, /window\.clearTimeout\(copyNoticeTimerRef\.current\);[\s\S]*window\.setTimeout\([\s\S]*setCopyNotice\(''\);[\s\S]*2400/, 'copy notices must restart and clear after a bounded delay');
  assertSourceMatches(feedbackCard, /<Alert[\s\S]*role="status"[\s\S]*aria-live="polite"[\s\S]*data-testid="copy-notice-toast"[\s\S]*className="fixed [^"]*z-50[^"]*"/, 'copy confirmation must be a visible viewport toast with a polite live region');
  assertSourceMatches(feedbackCard, /<AlertTitle>复制成功<\/AlertTitle>[\s\S]*<AlertDescription>\{copyNotice\}<\/AlertDescription>/, 'the toast must present the confirmation message');
});

test('generation loading uses a safe empty state and restores the prior selection on failure', () => {
  const generationChangeHandler = functionSource('handleGenerationChange', 'handleSaveFeedbackDraft');
  const feedbackCard = cardSource('反馈结果');

  assertSourceMatches(generationChangeHandler, /setSelectedGenerationId\(nextGenerationId\);[\s\S]*setFeedbackEditorText\(''\);[\s\S]*setFeedbackDraft\(null\);[\s\S]*setLoadingGenerationId\(numericGenerationId\);/, 'uncached generation loads must clear visible feedback before awaiting the API');
  assertSourceMatches(generationChangeHandler, /selectedGenerationIdRef\.current = previousGenerationId;[\s\S]*setSelectedGenerationId\(previousGenerationId\);[\s\S]*setFeedbackEditorText\(previousEditorText\);[\s\S]*setFeedbackDraft\(previousDraft\);/, 'failed generation loads must restore the prior scoped state');
  assertSourceMatches(generationChangeHandler, /isClassCommentaryFeedbackRecordInScope\(generation, taskId, numericGenerationId\)/, 'generation responses must be checked against the requested scope');
  assertSourceMatches(generationChangeHandler, /draft && !isClassCommentaryFeedbackRecordInScope\(draft, taskId, numericGenerationId\)/, 'draft responses must be checked against the requested scope');
  assertSourceMatches(feedbackCard, /disabled=\{generationLoading \|\| !copyText\}/, 'copy must be disabled during generation loading');
  assertSourceMatches(feedbackCard, /readOnly=\{Boolean\(revisionPreview\) \|\| isTaskReadOnly \|\| feedbackSchemaReadOnly\}/, 'privileged and schema compatibility access must keep the editor read-only');
  assertSourceMatches(feedbackCard, /disabled=\{!isTaskReadOnly && !revisionPreview && \(busy \|\| generationLoading \|\| !selectedGeneration \|\| selectedGeneration\.status !== 'succeeded'\)\}/, 'owner legacy editor must be disabled during generation loading without disabling super-owner text');
});

test('super owner history access stays read-only in the class feedback page', () => {
  assertSourceMatches(source, /const isTaskReadOnly = Boolean\(task && task\.teacher_user_id !== currentUser\.id\);/, 'read-only task ownership state is missing');
  assertSourceMatches(source, /const canSaveTranscript = !isTaskReadOnly/, 'read-only history must block transcript writes');
  assertSourceMatches(source, /const canGenerate =[\s\S]*!isTaskReadOnly/, 'read-only history must block regeneration');
  assertSourceMatches(source, /const canSaveFeedbackDraft = !isTaskReadOnly/, 'read-only history must block draft writes');
  assertSourceMatches(source, /const canConfirmFeedback = !isTaskReadOnly/, 'read-only history must block confirmation and learning');
  assertSourceMatches(source, /<AlertTitle>只读查看<\/AlertTitle>/, 'read-only history must explain the permission boundary');
  assertSourceMatches(source, /修改和 AI 学习仍由原老师完成\./, 'read-only notice must identify teacher-owned mutations');
  assertSourceMatches(source, /if \(isTaskReadOnly \|\| !capabilities\.memory_learning_enabled/, 'read-only history must not request teacher-owned memory details');
});

test('task switching invalidates requests but preserves scoped editors behind a dirty guard', () => {
  const resetHandler = functionSource('resetFeedbackVersionState', 'isCurrentFeedbackMutation');

  assertSourceMatches(resetHandler, /generationLoadRequestTokenRef\.current \+= 1;/, 'task reset must invalidate generation reads');
  assertSourceMatches(resetHandler, /feedbackMutationActiveRef\.current = false;/, 'task reset must release obsolete mutation ownership');
  assertSourceMatches(resetHandler, /feedbackMutationTokenRef\.current \+= 1;/, 'task reset must invalidate mutations');
  assertSourceMatches(resetHandler, /currentTaskIdRef\.current = nextTaskId;/, 'task reset must publish the new task identity first');
  assertSourceMatches(resetHandler, /setGenerations\(\[]\);[\s\S]*setSelectedGenerationId\(''\);[\s\S]*setFeedbackEditorText\(''\);[\s\S]*setFeedbackDraft\(null\);[\s\S]*setFeedbackRevisions\(\[]\);/, 'task reset must clear all old generation state');
  assertSourceMatches(resetHandler, /if \(releaseBusy\) \{\s*setBusy\(false\);/, 'explicit task navigation must release obsolete busy state');
  assertSourceExcludes(resetHandler, /setGenerationEditors\(\{\}\)/, 'task reset must not destroy other task generation editor snapshots');
  assertSourceMatches(source, /if \(feedbackDirty && !skipDirtyGuard\) \{\s*setHistoryDialogOpen\(false\);\s*setPendingFeedbackTransition\(\{ kind: 'task', task: nextTask \}\);/, 'dirty task navigation must be deferred');
  assertSourceMatches(source, /function selectHistoryTask\(nextTask: ClassCommentaryTask\) \{[\s\S]*resetFeedbackVersionState\(nextTask\.id, true\);[\s\S]*setTask\(nextTask\);/, 'confirmed task navigation must reset only visible version state');
  assertSourceMatches(source, /onClick=\{\(\) => handleSelectHistoryTask\(historyTask\)\}\s*disabled=\{busy \|\| generationLoading\}/, 'history rows must be disabled while work is in flight');
});

test('draft and confirmation mutations are scoped to their captured task and generation', () => {
  const saveHandler = functionSource('handleSaveFeedbackDraft', 'handleConfirmFeedback');
  const confirmationHandler = functionSource('handleConfirmFeedback', 'handleRetryRevisionMemory');

  for (const handler of [saveHandler, confirmationHandler]) {
    assertSourceMatches(handler, /const mutationTaskId = task\.id;/, 'mutation must capture its task');
    assertSourceMatches(handler, /const mutationGenerationId = selectedGeneration\.id;/, 'mutation must capture its generation');
    assertSourceMatches(handler, /const mutationToken = \+\+feedbackMutationTokenRef\.current;/, 'mutation must capture an operation token');
    assertSourceMatches(handler, /if \(!isCurrentFeedbackMutation\(mutationTaskId, mutationGenerationId, mutationToken\)\) \{\s*return(?: false)?;/, 'mutation response must be ignored after scope changes');
    assertSourceMatches(handler, /finally \{\s*if \(isCurrentFeedbackMutation\(mutationTaskId, mutationGenerationId, mutationToken\)\) \{\s*feedbackMutationActiveRef\.current = false;\s*setBusy\(false\);/, 'obsolete mutation finally blocks must not own current busy state');
  }
  assertSourceMatches(saveHandler, /isClassCommentaryFeedbackRecordInScope\(nextDraft, mutationTaskId, mutationGenerationId\)/, 'saved draft responses must match mutation scope');
  assertSourceMatches(confirmationHandler, /isClassCommentaryFeedbackRecordInScope\(revision, mutationTaskId, mutationGenerationId\)/, 'revision responses must match mutation scope');
  assertSourceMatches(confirmationHandler, /isClassCommentaryFeedbackRecordInScope\(nextDraft, mutationTaskId, mutationGenerationId\)/, 'transaction-bound draft responses must match mutation scope');
  assertSourceMatches(source, /if \(feedbackMutationActiveRef\.current\) \{\s*return;\s*\}\s*targetGenerationId = targetGeneration\.id;/, 'automatic generation selection must not invalidate an active mutation');
});

test('structured student editor provides per-student copy, accessibility, and bounded scrolling', () => {
  const feedbackCard = cardSource('反馈结果');

  assertSourceMatches(source, /<Accordion[\s\S]*type="multiple"[\s\S]*value=\{expandedStudentIds\}/, 'student editor must use a controlled shadcn Accordion');
  assertSourceMatches(source, /<label htmlFor=\{textareaId\}[\s\S]*\{item\.student_name\}反馈内容/, 'each student textarea needs a visible associated label');
  assertSourceMatches(source, /aria-invalid=\{Boolean\(itemError\)\}[\s\S]*aria-describedby=\{itemError \? errorId : undefined\}/, 'student validation errors need accessible field wiring');
  assertSourceMatches(source, /setExpandedStudentIds[\s\S]*requestAnimationFrame[\s\S]*textarea\?\.focus\(\)/, 'student-specific errors must expand and focus the failing textarea');
  assertSourceMatches(source, /readOnly=\{Boolean\(revisionPreview\) \|\| isTaskReadOnly \|\| busy\}/, 'super-owner structured textareas must be readOnly, not disabled');
  assertSourceMatches(feedbackCard, /displayedStudentFeedbackItems\.length >= 5[\s\S]*h-\[clamp\(280px,55vh,480px\)\][\s\S]*sm:h-\[clamp\(320px,60vh,560px\)\]/, 'five or more students need the bounded responsive ScrollArea');
  assertSourceMatches(source, /复制该学生/, 'each student needs a local copy action');
  assertSourceMatches(feedbackCard, /showStructuredFeedbackEditor \? '复制全部' : '复制结果'/, 'structured mode must retain copy all');
});

test('structured student feedback views default to all students collapsed', () => {
  const generationChangeHandler = functionSource('handleGenerationChange', 'handleStudentFeedbackApiError');
  const serverDraftHandler = functionSource('handleLoadServerDraft', 'handleCopyLocalDraft');
  const generationChangeCollapseCalls = generationChangeHandler.match(/setExpandedStudentIds\(\[\]\);/g) || [];

  assertSourceExcludes(source, /studentOrder\[0\] \? \[String/, 'generation editors must not default the first student open');
  assertSourceExcludes(source, /serverItems\[0\] \? \[String/, 'server draft recovery must not default the first student open');
  assertSourceExcludes(source, /student_feedback_items\[0\]/, 'revision previews must not default the first student open');
  assertSourceMatches(source, /setRevisionPreview\(null\);\s*setExpandedStudentIds\(\[\]\);/, 'a successful generation must start fully collapsed');
  assert.equal(generationChangeCollapseCalls.length, 2, 'cached and fetched generation switches must both start fully collapsed');
  assertSourceMatches(serverDraftHandler, /setFeedbackDraft\(draftConflict\.serverDraft\);\s*setExpandedStudentIds\(\[\]\);/, 'server draft recovery must start fully collapsed');
  assertSourceMatches(source, /function handleOpenRevisionPreview[\s\S]*setRevisionPreview\([\s\S]*setExpandedStudentIds\(\[\]\);/, 'revision previews must start fully collapsed');
  assertSourceMatches(source, /function handleReturnFromRevisionPreview\(\) \{\s*setRevisionPreview\(null\);\s*setExpandedStudentIds\(\[\]\);/, 'returning to the editor must start fully collapsed');
});

test('dirty transitions cover generation task revision route and reload with the same recovery dialog', () => {
  assertSourceMatches(source, /CLASS_COMMENTARY_NAVIGATION_REQUEST_EVENT/, 'workspace route changes must use the shared cancelable event');
  assertSourceMatches(source, /event\.preventDefault\(\);[\s\S]*kind: 'route',[\s\S]*proceed: event\.detail\.proceed/, 'dirty route changes must retain a deferred proceed callback');
  assertSourceMatches(source, /window\.addEventListener\('beforeunload', handleBeforeUnload\)/, 'dirty browser reload and close need the native guard');
  assertSourceMatches(source, /setPendingFeedbackTransition\(\{ kind: 'generation', generationId: nextGenerationId \}\)/, 'generation switching must be guarded');
  assertSourceMatches(source, /setPendingFeedbackTransition\(\{ kind: 'revision', revision \}\)/, 'revision preview must be guarded');
  assertSourceMatches(source, /<DialogTitle>有未保存的反馈修改<\/DialogTitle>[\s\S]*取消[\s\S]*复制本地内容[\s\S]*放弃并切换[\s\S]*保存草稿/, 'dirty transitions need the four explicit recovery actions');
});

test('workspace editor keys and revision conflict recovery preserve local student items', () => {
  assertSourceMatches(source, /Record<string, GenerationEditorState>/, 'generation editors must be keyed by task generation workspace key');
  assertSourceMatches(source, /itemsByStudentId: Record<number, ClassCommentaryStudentFeedbackItem>/, 'each workspace needs student-id keyed current items');
  assertSourceMatches(source, /savedItemsByStudentId: Record<number, ClassCommentaryStudentFeedbackItem>/, 'each workspace needs a separate saved snapshot');
  assertSourceMatches(source, /currentLatestRevision && currentLatestRevision\.task_id !== mutationTaskId/, 'revision conflicts must validate task scope');
  assertSourceMatches(source, /\[revisionConflict\.workspaceKey\]: \{[\s\S]*latestRevisionIdAtLoad: revisionConflict\.currentLatestRevisionId/, 'revision rebase must update only the conflicted workspace CAS pointer');
  assertSourceMatches(source, /同步版本并保留本地修改/, 'revision conflicts need an explicit acknowledge and retry path');
  assertSourceMatches(source, /本地修改仍保留\. 请重新确认\./, 'revision recovery must explain that local items were preserved');
});

test('dirty navigation from revision preview copies and saves the preserved editor, not preview text', () => {
  const saveAndContinue = functionSource('handleSaveAndContinueTransition', 'handleCopyPendingLocalContent');
  const copyPending = functionSource('handleCopyPendingLocalContent', 'handleDiscardAndContinueTransition');

  assertSourceMatches(source, /const localEditorCopyText = selectedEditorState[\s\S]*orderedStudentFeedbackItems\(selectedEditorState\)/, 'pending copy text must derive from the preserved generation editor');
  assertSourceMatches(copyPending, /navigator\.clipboard\.writeText\(localEditorCopyText\)/, 'preview dirty dialog must never copy global preview copyText');
  assertSourceExcludes(copyPending, /writeText\(copyText\)/, 'preview text must not replace the local editor snapshot');
  assertSourceMatches(saveAndContinue, /if \(revisionPreview\) \{\s*setRevisionPreview\(null\);/, 'saving from a preview guard must return to the current editor first');
  assertSourceMatches(source, /disabled=\{!canSavePendingFeedbackTransition\}/, 'preview guard must allow saving the preserved dirty editor');
});

test('class feedback page adds no raw controls, custom modal, or custom stylesheet', () => {
  const classFeedbackFiles = readdirSync(new URL('./features/class-feedback/', import.meta.url));

  assertSourceExcludes(source, /<(?:button|select|textarea)\b/, 'page must not use raw button, select, or textarea controls');
  assertSourceExcludes(source, /role=["']dialog["']/, 'page must not implement a custom dialog role');
  assertSourceExcludes(source, /createPortal/, 'page must not create a custom modal portal');
  assertSourceExcludes(source, /import\s+['"][^'"]+\.(?:css|less|sass|scss)['"]/, 'page must not import a custom stylesheet');
  assert.deepEqual(classFeedbackFiles.filter((name) => /\.(?:css|less|sass|scss)$/.test(name)), []);
});
