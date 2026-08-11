import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { afterEach, test } from 'node:test';
import {
  areClassCommentaryStudentFeedbackItemsEqual,
  buildClassCommentaryFeedbackWorkspaceKey,
  buildClassCommentaryRevisionPreviewKey,
  buildClassCommentarySkillPreferenceKey,
  buildClassCommentaryStudentLearningGraphPath,
  buildClassCommentaryTaskPath,
  classCommentaryStatusLabel,
  activateClassCommentarySkillVersion,
  confirmClassCommentaryFeedback,
  createClassCommentarySkillCandidate,
  fetchClassCommentaryCapabilities,
  fetchClassCommentaryTasks,
  fetchClassCommentaryFeedbackDraft,
  fetchClassCommentaryFeedbackRevisions,
  fetchClassCommentaryRevisionMemories,
  fetchClassCommentaryStudentLearningGraph,
  fetchClassCommentarySkillEvolution,
  fetchClassCommentaryGeneration,
  fetchClassCommentaryGenerations,
  createClassCommentaryTextTask,
  deriveClassCommentaryStructuredFeedbackText,
  formatClassCommentaryStudentFeedback,
  generateClassCommentaryFeedback,
  isClassCommentaryFeedbackRecordInScope,
  isClassCommentaryMutationOutcomeAmbiguous,
  isClassCommentaryTaskLatestSchemaCompatible,
  isClassCommentaryStudentLearningGraphSummaryInScope,
  loadClassCommentaryCapabilities,
  normalizeClassCommentaryGeneration,
  normalizeClassCommentaryStudentLearningGraphSummary,
  normalizeClassCommentaryStudentGenerationProgress,
  normalizeClassCommentaryTask,
  readClassCommentarySkillPreference,
  rollbackClassCommentarySkillVersion,
  retryClassCommentaryRevisionMemory,
  retryClassCommentaryRevisionLearningGraph,
  retryClassCommentaryStudentGenerationRuns,
  revokeClassCommentaryMemoryEvidence,
  resolveClassCommentaryCopyText,
  resolveClassCommentaryStudentFeedbackItems,
  saveClassCommentaryFeedbackDraft,
  shouldPollClassCommentaryTask,
  updateClassCommentaryScopedStudentFeedback,
  writeClassCommentarySkillPreference,
} from './classCommentary';
import { ApiFetchError } from './workspaceShared';

const source = readFileSync(new URL('./classCommentary.ts', import.meta.url), 'utf8');
const originalLocalStorage = globalThis.localStorage;
const originalFetch = globalThis.fetch;

test('mutation ambiguity keeps request identities for proxy and transport failures', () => {
  assert.equal(isClassCommentaryMutationOutcomeAmbiguous(new Error('network')), true);
  assert.equal(
    isClassCommentaryMutationOutcomeAmbiguous(new ApiFetchError(502, {}, 'bad gateway')),
    true,
  );
  assert.equal(
    isClassCommentaryMutationOutcomeAmbiguous(new ApiFetchError(504, {}, 'timeout')),
    true,
  );
  assert.equal(
    isClassCommentaryMutationOutcomeAmbiguous(new ApiFetchError(409, {}, 'conflict')),
    false,
  );
  assert.equal(
    isClassCommentaryMutationOutcomeAmbiguous(new ApiFetchError(402, {}, 'credits')),
    false,
  );
});

type MockFetchCall = {
  path: string;
  options: RequestInit | undefined;
};

function mockJsonFetch(payload: unknown, status = 200): MockFetchCall[] {
  const calls: MockFetchCall[] = [];
  Object.defineProperty(globalThis, 'fetch', {
    configurable: true,
    value: async (input: string | URL | Request, options?: RequestInit) => {
      calls.push({ path: String(input), options });
      return {
        ok: status >= 200 && status < 300,
        status,
        statusText: status === 409 ? 'Conflict' : 'OK',
        json: async () => payload,
      } as Response;
    },
  });
  return calls;
}

afterEach(() => {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: originalLocalStorage,
  });
  Object.defineProperty(globalThis, 'fetch', {
    configurable: true,
    value: originalFetch,
  });
});

test('normalizes missing task fields to empty strings', () => {
  const task = normalizeClassCommentaryTask({
    id: 1,
    organization_id: 2,
    class_id: 3,
    teacher_user_id: 4,
    status: 'transcribed',
  });

  assert.equal(task.class_name, '');
  assert.equal(task.failure_stage, '');
  assert.equal(task.audio_filename, '');
  assert.equal(task.feedback_text, '');
  assert.equal(task.transcription_error, '');
  assert.equal(task.generation_error, '');
});

test('normalizes feedback envelopes into plain, supported, unsupported, and invalid modes', () => {
  const plain = normalizeClassCommentaryGeneration({
    id: 1,
    generated_feedback_text: '历史纯文本',
    feedback_schema_version: '',
  });
  assert.equal(plain.feedback_schema_status, 'plain_text');
  assert.deepEqual(plain.student_feedback_items, []);
  assert.equal(plain.derived_feedback_text, '历史纯文本');
  assert.equal(plain.writable, true);

  const supported = normalizeClassCommentaryGeneration({
    id: 2,
    feedback_schema_version: 'class_commentary.student_feedback.v1',
    feedback_schema_status: 'supported',
    structured_feedback_hash: 'known-hash',
    derived_feedback_text: '小王:\n课堂计算更稳定.',
    used_graph_evidence_refs: ['evidence-11'],
    student_feedback_items: [{
      student_id: 11,
      student_name: '小王',
      feedback_text: '课堂计算更稳定.',
    }],
  });
  assert.equal(supported.feedback_schema_status, 'supported');
  assert.equal(supported.student_feedback_items[0].student_name, '小王');
  assert.equal(supported.generated_feedback_text, '小王:\n课堂计算更稳定.');
  assert.deepEqual(supported.used_graph_evidence_refs, ['evidence-11']);
  assert.equal(supported.writable, true);

  const unknown = normalizeClassCommentaryGeneration({
    id: 3,
    feedback_schema_version: 'future.student-feedback.v2',
    feedback_schema_status: 'plain_text',
    writable: true,
    derived_feedback_text: '未来版本兼容文本',
    student_feedback_items: [{ student_id: 11, student_name: '不应信任', feedback_text: '不应解析' }],
  });
  assert.equal(unknown.feedback_schema_status, 'unsupported');
  assert.deepEqual(unknown.student_feedback_items, []);
  assert.equal(unknown.derived_feedback_text, '未来版本兼容文本');
  assert.equal(unknown.writable, false);

  const whitespaceSchema = normalizeClassCommentaryGeneration({
    id: 4,
    feedback_schema_version: ' ',
    feedback_schema_status: 'plain_text',
    writable: true,
    derived_feedback_text: '空格版本也必须只读',
  });
  assert.equal(whitespaceSchema.feedback_schema_status, 'unsupported');
  assert.equal(whitespaceSchema.feedback_schema_version, ' ');
  assert.equal(whitespaceSchema.writable, false);

  const invalid = normalizeClassCommentaryGeneration({
    id: 5,
    feedback_schema_version: 'class_commentary.student_feedback.v1',
    feedback_schema_status: 'supported',
    structured_feedback_hash: 'known-hash',
    derived_feedback_text: '损坏的结构化反馈',
    student_feedback_items: [{ student_id: 0, student_name: '', feedback_text: '' }],
  });
  assert.equal(invalid.feedback_schema_status, 'invalid');
  assert.deepEqual(invalid.student_feedback_items, []);
  assert.equal(invalid.writable, false);

  const generating = normalizeClassCommentaryGeneration({
    id: 6,
    status: 'generating',
    feedback_schema_version: 'class_commentary.student_feedback.v1',
    feedback_schema_status: 'supported',
    structured_feedback_hash: '',
    derived_feedback_text: '',
    student_feedback_items: [],
    writable: false,
  });
  assert.equal(generating.feedback_schema_status, 'supported');
  assert.deepEqual(generating.student_feedback_items, []);
  assert.equal(generating.writable, false);
});

test('task latest schema compatibility is asymmetric for legacy to structured upgrades', () => {
  assert.equal(isClassCommentaryTaskLatestSchemaCompatible(
    'class_commentary.student_feedback.v1',
    '',
  ), true);
  assert.equal(isClassCommentaryTaskLatestSchemaCompatible(
    '',
    'class_commentary.student_feedback.v1',
  ), false);
  assert.equal(isClassCommentaryTaskLatestSchemaCompatible(
    'class_commentary.student_feedback.v1',
    'class_commentary.student_feedback.v1',
  ), true);
});

test('class commentary capabilities keep structured feedback disabled by default', async () => {
  mockJsonFetch({ memory_learning_enabled: true, skill_evolution_enabled: true });

  const capabilities = await fetchClassCommentaryCapabilities();

  assert.deepEqual(capabilities, {
    memory_learning_enabled: true,
    skill_evolution_enabled: true,
    structured_feedback_enabled: false,
    student_history_memory_v2_enabled: false,
    student_history_memory_v2_max_credits_per_student: 0,
    graph_enabled: false,
    graph_healthy: false,
    graph_degraded: false,
  });
});

test('normalizes isolated student generation progress without trusting unknown statuses', () => {
  const progress = normalizeClassCommentaryStudentGenerationProgress({
    total: 5,
    queued: 1,
    generating: 1,
    succeeded: 2,
    failed: 1,
    runs: [
      {
        id: 41,
        student_id: 11,
        student_name: '学生 A',
        status: 'succeeded',
        attempt_count: 1,
        memory_retrieval_status: 'ready',
        charge_status: 'charged',
      },
      {
        id: 42,
        student_id: 12,
        student_name: '学生 B',
        status: 'future_status',
        attempt_count: -1,
      },
    ],
  });

  assert.deepEqual(
    {
      total: progress.total,
      queued: progress.queued,
      generating: progress.generating,
      succeeded: progress.succeeded,
      failed: progress.failed,
    },
    { total: 5, queued: 1, generating: 1, succeeded: 2, failed: 1 },
  );
  assert.equal(progress.runs[0].status, 'succeeded');
  assert.equal(progress.runs[0].charge_status, 'charged');
  assert.equal(progress.runs[1].status, 'unknown');
  assert.equal(progress.runs[1].attempt_count, 0);
});

test('capabilities expose isolated generation call and credit impact', async () => {
  mockJsonFetch({
    memory_learning_enabled: true,
    skill_evolution_enabled: true,
    structured_feedback_enabled: true,
    student_history_memory_v2_enabled: true,
    student_history_memory_v2_max_credits_per_student: 10,
    graph_enabled: false,
    graph_healthy: false,
    graph_degraded: false,
  });

  assert.deepEqual(await fetchClassCommentaryCapabilities(), {
    memory_learning_enabled: true,
    skill_evolution_enabled: true,
    structured_feedback_enabled: true,
    student_history_memory_v2_enabled: true,
    student_history_memory_v2_max_credits_per_student: 10,
    graph_enabled: false,
    graph_healthy: false,
    graph_degraded: false,
  });
});

test('capability transport failures return unavailable instead of a zero-cost mode', async () => {
  mockJsonFetch({ error: 'bad gateway' }, 502);

  assert.deepEqual(await loadClassCommentaryCapabilities(), {
    state: 'unavailable',
    value: {
      memory_learning_enabled: false,
      skill_evolution_enabled: false,
      structured_feedback_enabled: false,
      student_history_memory_v2_enabled: false,
      student_history_memory_v2_max_credits_per_student: 0,
      graph_enabled: false,
      graph_healthy: false,
      graph_degraded: false,
    },
  });
});

test('capabilities expose graph health without enabling it by default', async () => {
  mockJsonFetch({
    graph_enabled: true,
    graph_healthy: false,
    graph_degraded: true,
  });

  const capabilities = await fetchClassCommentaryCapabilities();

  assert.equal(capabilities.graph_enabled, true);
  assert.equal(capabilities.graph_healthy, false);
  assert.equal(capabilities.graph_degraded, true);
  assert.equal(capabilities.memory_learning_enabled, false);
});

test('student learning graph normalizer validates scope enums and exact evidence fields', () => {
  const payload = {
    task_id: 9,
    student_id: 11,
    subject_key: 'math',
    sync_status: 'learned',
    can_retry: false,
    error: '',
    current_states: [{
      knowledge_point_key: 'quadratic-graphs',
      knowledge_point_name: '二次函数图像',
      state: 'developing',
      observed_at: '2026-08-11T10:00:00Z',
    }],
    timeline: [{
      event_ref: 'event-2',
      knowledge_point_key: 'quadratic-graphs',
      knowledge_point_name: '二次函数图像',
      state: 'developing',
      previous_state: 'weak',
      trend: 'improved',
      observed_at: '2026-08-11T10:00:00Z',
      evidence: {
        evidence_ref: 'evidence-2',
        quote: '已经能结合参数变化判断图像移动方向.',
        lesson_id: 18,
        lesson_name: '第 18 次课程',
        revision_id: 52,
        revision_no: 2,
        confirmed_at: '2026-08-11T10:00:00Z',
      },
      teaching_methods: ['图像与参数联动练习'],
      next_steps: ['继续练习顶点式与图像平移'],
    }],
    used_graph_evidence_refs: ['evidence-2'],
    used_graph_evidence: [],
  };

  const summary = normalizeClassCommentaryStudentLearningGraphSummary(payload);

  assert.equal(summary.current_states[0].state, 'developing');
  assert.equal(summary.timeline[0].previous_state, 'weak');
  assert.equal(summary.timeline[0].evidence.quote, '已经能结合参数变化判断图像移动方向.');
  assert.deepEqual(summary.timeline[0].teaching_methods, ['图像与参数联动练习']);
  assert.deepEqual(summary.used_graph_evidence_refs, ['evidence-2']);
  assert.equal(isClassCommentaryStudentLearningGraphSummaryInScope(summary, 9, 11, 'math'), true);
  assert.equal(isClassCommentaryStudentLearningGraphSummaryInScope(summary, 9, 12, 'math'), false);
  assert.equal(isClassCommentaryStudentLearningGraphSummaryInScope(summary, 9, 11, 'physics'), false);
  assert.equal(isClassCommentaryStudentLearningGraphSummaryInScope(summary, 9, 11, ''), false);
  assert.throws(
    () => normalizeClassCommentaryStudentLearningGraphSummary({ ...payload, subject_key: '' }),
    /subject_key/,
  );
  assert.throws(
    () => normalizeClassCommentaryStudentLearningGraphSummary({ ...payload, sync_status: 'complete' }),
    /sync_status/,
  );
  assert.throws(
    () => normalizeClassCommentaryStudentLearningGraphSummary({
      ...payload,
      timeline: [{ ...payload.timeline[0], state: '70%' }],
    }),
    /state/,
  );
  assert.throws(
    () => normalizeClassCommentaryStudentLearningGraphSummary({
      ...payload,
      timeline: [{
        ...payload.timeline[0],
        evidence: { ...payload.timeline[0].evidence, quote: '' },
      }],
    }),
    /evidence quote/,
  );
});

test('student learning graph API is task scoped and retry preserves the request id', async () => {
  const learningGraph = {
    task_id: 9,
    student_id: 11,
    subject_key: 'math',
    sync_status: 'pending',
    can_retry: false,
    error: '',
    current_states: [],
    timeline: [],
    used_graph_evidence_refs: [],
    used_graph_evidence: [],
  };
  const fetchCalls = mockJsonFetch({ learning_graph: learningGraph });

  const summary = await fetchClassCommentaryStudentLearningGraph(9, 11, 27);

  assert.equal(
    buildClassCommentaryStudentLearningGraphPath(9, 11, 27),
    '/api/class-commentary/tasks/9/students/11/learning-graph?generation_id=27',
  );
  assert.equal(fetchCalls[0].path, '/api/class-commentary/tasks/9/students/11/learning-graph?generation_id=27');
  assert.equal(fetchCalls[0].path.includes('organization'), false);
  assert.equal(summary.sync_status, 'pending');

  const retryCalls = mockJsonFetch({ graph_job: { id: 7, status: 'queued' } });
  await retryClassCommentaryRevisionLearningGraph(52, 'graph-retry-52');

  assert.equal(retryCalls[0].path, '/api/class-commentary/revisions/52/graph-retry');
  assert.deepEqual(JSON.parse(String(retryCalls[0].options?.body)), { request_id: 'graph-retry-52' });
});

test('polling is limited to async task states', () => {
  assert.equal(shouldPollClassCommentaryTask('uploaded'), true);
  assert.equal(shouldPollClassCommentaryTask('transcribing'), true);
  assert.equal(shouldPollClassCommentaryTask('generating'), true);
  assert.equal(shouldPollClassCommentaryTask('transcribed'), false);
  assert.equal(shouldPollClassCommentaryTask('ready'), false);
  assert.equal(shouldPollClassCommentaryTask('failed'), false);
});

test('uses class-commentary api namespace', () => {
  assert.equal(buildClassCommentaryTaskPath(9), '/api/class-commentary/tasks/9');
});

test('feedback records must match both task and generation scope', () => {
  const record = { task_id: 9, generation_id: 31 };

  assert.equal(isClassCommentaryFeedbackRecordInScope(record, 9, 31), true);
  assert.equal(isClassCommentaryFeedbackRecordInScope(record, 10, 31), false);
  assert.equal(isClassCommentaryFeedbackRecordInScope(record, 9, 32), false);
  assert.equal(isClassCommentaryFeedbackRecordInScope({ task_id: 9, generation_id: 0 }, 9, 0), false);
  assert.equal(isClassCommentaryFeedbackRecordInScope(null, 9, 31), false);
});

test('structured feedback helpers preserve frozen order and current visible text', () => {
  const generationItems = [
    { student_id: 11, student_name: '小王', feedback_text: 'AI 原稿' },
    { student_id: 12, student_name: '小李', feedback_text: '第二段' },
  ];
  const draftItems = [
    { student_id: 11, student_name: '小王', feedback_text: '未保存前的草稿' },
    { student_id: 12, student_name: '小李', feedback_text: '第二段草稿' },
  ];
  const resolved = resolveClassCommentaryStudentFeedbackItems(
    { feedback_schema_status: 'supported', student_feedback_items: draftItems },
    null,
    { feedback_schema_status: 'supported', student_feedback_items: generationItems },
  );

  assert.deepEqual(resolved, draftItems);
  assert.notEqual(resolved, draftItems);
  resolved[0].feedback_text = '当前界面未保存修改';
  assert.equal(
    deriveClassCommentaryStructuredFeedbackText(resolved),
    '小王:\n当前界面未保存修改\n\n小李:\n第二段草稿',
  );
  assert.equal(formatClassCommentaryStudentFeedback(resolved[0]), '小王:\n当前界面未保存修改');
  assert.equal(areClassCommentaryStudentFeedbackItemsEqual(resolved, draftItems), false);
  assert.deepEqual(resolveClassCommentaryStudentFeedbackItems(null, null, null, true), []);
});

test('task generation workspace keys isolate overlapping student ids', () => {
  const firstKey = buildClassCommentaryFeedbackWorkspaceKey(10, 25);
  const secondKey = buildClassCommentaryFeedbackWorkspaceKey(11, 25);
  const editors = {
    [firstKey]: {
      itemsByStudentId: {
        123: { student_id: 123, student_name: '同名 ID', feedback_text: '任务一' },
      },
    },
    [secondKey]: {
      itemsByStudentId: {
        123: { student_id: 123, student_name: '同名 ID', feedback_text: '任务二' },
      },
    },
  };

  const updated = updateClassCommentaryScopedStudentFeedback(editors, firstKey, 123, '只修改任务一');

  assert.equal(firstKey, '10:25');
  assert.equal(secondKey, '11:25');
  assert.equal(buildClassCommentaryRevisionPreviewKey(10, 7), '10:7');
  assert.equal(updated[firstKey].itemsByStudentId[123].feedback_text, '只修改任务一');
  assert.equal(updated[secondKey].itemsByStudentId[123].feedback_text, '任务二');
  assert.equal(updated[secondKey], editors[secondKey]);
});

test('copy text uses persisted precedence and is empty while generation data is blocked', () => {
  const draft = { feedback_text: '已保存草稿' };
  const revision = { final_feedback_text: '有效终稿' };
  const generation = { generated_feedback_text: 'AI 原稿' };

  assert.equal(resolveClassCommentaryCopyText(draft, revision, generation), '已保存草稿');
  assert.equal(resolveClassCommentaryCopyText(null, revision, generation), '有效终稿');
  assert.equal(resolveClassCommentaryCopyText(null, null, generation), 'AI 原稿');
  assert.equal(resolveClassCommentaryCopyText(draft, revision, generation, true), '');
});

test('status labels are user-facing and stable', () => {
  assert.equal(classCommentaryStatusLabel('transcribing'), '转写中');
  assert.equal(classCommentaryStatusLabel('transcribed'), '待确认');
  assert.equal(classCommentaryStatusLabel('ready'), '已生成');
  assert.equal(classCommentaryStatusLabel('failed'), '失败');
});

test('request helpers use workspaceShared auth instead of explicit token parameters', () => {
  assert.match(source, /apiFetch/);
  assert.match(source, /apiUploadFormWithProgress/);
  assert.match(source, /readLocalStorageItem/);
  assert.match(source, /writeLocalStorageItem/);
  assert.match(source, /from '\.\/workspaceShared';/);
  assert.match(source, /apiFetch<\{ skills\?: unknown\[] \}>/);
  assert.match(source, /apiFetch<\{ tasks\?: unknown\[] \}>/);
  assert.match(source, /apiFetch<Record<string, unknown>>\('\/api\/class-commentary\/tasks\/text'/);
  assert.match(source, /apiUploadFormWithProgress<Record<string, unknown>>/);
  assert.doesNotMatch(source, /X-Auth-Token/);
  assert.doesNotMatch(source, /currentUser\.token/);
  assert.doesNotMatch(source, /token: string/);
});

test('fetchClassCommentaryTasks exposes the class-commentary task list helper', () => {
  assert.equal(typeof fetchClassCommentaryTasks, 'function');
});

test('createClassCommentaryTextTask exposes the manual transcript task helper', () => {
  assert.equal(typeof createClassCommentaryTextTask, 'function');
});

test('class commentary skill preference is stored per organization teacher', () => {
  const values = new Map<string, string>();
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => {
        values.set(key, value);
      },
      removeItem: (key: string) => {
        values.delete(key);
      },
    },
  });

  const teacherA = { id: 7, organization_id: 2 };
  const teacherB = { id: 8, organization_id: 2 };
  const skills = [
    { id: 'cao-xi-lin', name: '曹曦临', filename: 'cao.md', updated_at: '' },
    { id: 'li-sen', name: '李森', filename: 'li.md', updated_at: '' },
  ];

  assert.equal(buildClassCommentarySkillPreferenceKey(teacherA), 'xr_class_commentary_skill:2:7');

  writeClassCommentarySkillPreference(teacherA, 'li-sen');
  writeClassCommentarySkillPreference(teacherB, 'cao-xi-lin');

  assert.equal(readClassCommentarySkillPreference(teacherA, skills), 'li-sen');
  assert.equal(readClassCommentarySkillPreference(teacherB, skills), 'cao-xi-lin');
  assert.equal(readClassCommentarySkillPreference(teacherA, skills.slice(0, 1)), '');
});

test('generateClassCommentaryFeedback sends request id and normalizes nested task and generation', async () => {
  const calls = mockJsonFetch({
    task: {
      id: 9,
      organization_id: 2,
      class_id: 3,
      teacher_user_id: 4,
      status: 'ready',
      feedback_text: '兼容结果',
    },
    generation: {
      id: 27,
      task_id: 9,
      generation_no: 2,
      generation_request_id: 'generation-request-27',
      status: 'succeeded',
      generated_feedback_text: '第二版反馈',
      draft_version: 0,
    },
  });

  const result = await generateClassCommentaryFeedback(
    9,
    'teacher-style',
    [11, 12],
    'generation-request-27',
  );

  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, '/api/class-commentary/tasks/9/generate');
  assert.equal(calls[0].options?.method, 'POST');
  assert.deepEqual(JSON.parse(String(calls[0].options?.body)), {
    skill_id: 'teacher-style',
    attending_student_ids: [11, 12],
    request_id: 'generation-request-27',
  });
  assert.equal(result.task.id, 9);
  assert.equal(result.task.status, 'ready');
  assert.equal(result.task.class_name, '');
  assert.equal(result.generation.id, 27);
  assert.equal(result.generation.task_id, 9);
  assert.equal(result.generation.status, 'succeeded');
  assert.equal(result.generation.generated_feedback_text, '第二版反馈');
});

test('retryClassCommentaryStudentGenerationRuns retries only explicit failed students with one request id', async () => {
  const calls = mockJsonFetch({
    task: {
      id: 9,
      organization_id: 2,
      class_id: 3,
      teacher_user_id: 4,
      status: 'generating',
    },
    generation: {
      id: 27,
      task_id: 9,
      status: 'generating',
      student_history_memory_mode: 'isolated_v2',
      prompt_version: 'class-commentary-student-feedback-isolated-v2',
      student_run_progress: {
        total: 5,
        queued: 1,
        generating: 0,
        succeeded: 4,
        failed: 0,
        runs: [],
      },
    },
  });

  const result = await retryClassCommentaryStudentGenerationRuns(
    9,
    27,
    [12],
    'student-generation-retry-27',
  );

  assert.equal(calls[0].path, '/api/class-commentary/tasks/9/generations/27/student-runs/retry');
  assert.equal(calls[0].options?.method, 'POST');
  assert.deepEqual(JSON.parse(String(calls[0].options?.body)), {
    request_id: 'student-generation-retry-27',
    student_ids: [12],
  });
  assert.equal(result.generation.student_history_memory_mode, 'isolated_v2');
  assert.equal(result.generation.prompt_version, 'class-commentary-student-feedback-isolated-v2');
  assert.equal(result.generation.student_run_progress.total, 5);
});

test('fetchClassCommentaryGenerations normalizes the generation list', async () => {
  const calls = mockJsonFetch({
    generations: [{
      id: 31,
      task_id: 9,
      generation_no: 3,
      status: 'succeeded',
      generated_feedback_text: '第三版反馈',
      is_latest: true,
      has_draft: true,
      draft_version: 2,
    }],
  });

  const generations = await fetchClassCommentaryGenerations(9);

  assert.equal(calls[0].path, '/api/class-commentary/tasks/9/generations');
  assert.equal(generations.length, 1);
  assert.equal(generations[0].id, 31);
  assert.equal(generations[0].generation_no, 3);
  assert.equal(generations[0].is_latest, true);
  assert.equal(generations[0].has_draft, true);
  assert.equal(generations[0].draft_version, 2);
  assert.equal(generations[0].error_code, '');
});

test('fetchClassCommentaryGeneration normalizes the generation detail', async () => {
  const calls = mockJsonFetch({
    id: '31',
    task_id: '9',
    generation_no: '3',
    status: 'succeeded',
    origin: 'runtime',
    snapshot_completeness: 'complete',
    skill_id: 'teacher-style',
    generated_feedback_text: '第三版反馈',
  });

  const generation = await fetchClassCommentaryGeneration(9, 31);

  assert.equal(calls[0].path, '/api/class-commentary/tasks/9/generations/31');
  assert.equal(generation.id, 31);
  assert.equal(generation.task_id, 9);
  assert.equal(generation.generation_no, 3);
  assert.equal(generation.status, 'succeeded');
  assert.equal(generation.skill_id, 'teacher-style');
  assert.equal(generation.generated_feedback_text, '第三版反馈');
});

test('fetchClassCommentaryFeedbackDraft unwraps and normalizes the saved draft', async () => {
  const calls = mockJsonFetch({
    draft: {
      id: 41,
      task_id: 9,
      generation_id: 31,
      teacher_user_id: 4,
      based_on_revision_id: null,
      feedback_text: '老师草稿',
      draft_version: 2,
    },
    draft_version: 2,
  });

  const draft = await fetchClassCommentaryFeedbackDraft(9, 31);

  assert.equal(calls[0].path, '/api/class-commentary/tasks/9/generations/31/feedback-draft');
  assert.ok(draft);
  assert.equal(draft.id, 41);
  assert.equal(draft.feedback_text, '老师草稿');
  assert.equal(draft.draft_version, 2);
  assert.equal(draft.created_at, '');
  assert.equal(draft.feedback_schema_status, 'plain_text');
  assert.equal(draft.derived_feedback_text, '老师草稿');
});

test('fetchClassCommentaryFeedbackDraft returns null when no draft exists', async () => {
  mockJsonFetch({ draft: null, draft_version: 0 });

  assert.equal(await fetchClassCommentaryFeedbackDraft(9, 31), null);
});

test('saveClassCommentaryFeedbackDraft sends CAS version and unwraps the draft', async () => {
  const calls = mockJsonFetch({
    draft: {
      id: 42,
      task_id: 9,
      generation_id: 31,
      teacher_user_id: 4,
      feedback_text: '保存后的草稿',
      draft_version: 3,
    },
  });

  const draft = await saveClassCommentaryFeedbackDraft(9, 31, '保存后的草稿', 2);

  assert.equal(calls[0].path, '/api/class-commentary/tasks/9/generations/31/feedback-draft');
  assert.equal(calls[0].options?.method, 'PUT');
  assert.deepEqual(JSON.parse(String(calls[0].options?.body)), {
    feedback_text: '保存后的草稿',
    expected_draft_version: 2,
  });
  assert.equal(draft.feedback_text, '保存后的草稿');
  assert.equal(draft.draft_version, 3);
});

test('structured draft save sends items as the only writable content source', async () => {
  const calls = mockJsonFetch({
    draft: {
      id: 43,
      task_id: 9,
      generation_id: 31,
      teacher_user_id: 4,
      based_on_revision_id: 8,
      feedback_schema_version: 'class_commentary.student_feedback.v1',
      feedback_schema_status: 'supported',
      student_feedback_items: [{ student_id: 11, student_name: '小王', feedback_text: '老师当前修改' }],
      structured_feedback_hash: 'draft-hash',
      derived_feedback_text: '小王:\n老师当前修改',
      feedback_text: '小王:\n老师当前修改',
      draft_version: 3,
    },
  });

  await saveClassCommentaryFeedbackDraft(
    9,
    31,
    {
      feedback_schema_version: 'class_commentary.student_feedback.v1',
      student_feedback_items: [{ student_id: 11, feedback_text: '老师当前修改' }],
    },
    2,
    8,
  );

  assert.deepEqual(JSON.parse(String(calls[0].options?.body)), {
    feedback_schema_version: 'class_commentary.student_feedback.v1',
    student_feedback_items: [{ student_id: 11, feedback_text: '老师当前修改' }],
    expected_draft_version: 2,
    based_on_revision_id: 8,
  });
  assert.doesNotMatch(String(calls[0].options?.body), /feedback_text":"小王:/);
});

test('confirmClassCommentaryFeedback returns the revision with its transaction-bound draft', async () => {
  const calls = mockJsonFetch({
    revision: {
      id: 51,
      task_id: 9,
      generation_id: 31,
      revision_no: 1,
      final_feedback_text: '老师终稿',
      learn_requested: false,
      draft_version: 3,
    },
    draft: {
      id: 42,
      task_id: 9,
      generation_id: 31,
      teacher_user_id: 4,
      based_on_revision_id: 51,
      feedback_text: '老师终稿',
      content_hash: 'confirmed-content-hash',
      draft_version: 3,
      created_at: '2026-07-14T11:00:00Z',
      updated_at: '2026-07-14T12:00:00Z',
    },
  });

  const result = await confirmClassCommentaryFeedback(
    9,
    31,
    '老师终稿',
    false,
    2,
    'confirmation-request-51',
  );

  assert.equal(calls[0].path, '/api/class-commentary/tasks/9/feedback-confirmations');
  assert.equal(calls[0].options?.method, 'POST');
  assert.deepEqual(JSON.parse(String(calls[0].options?.body)), {
    generation_id: 31,
    feedback_text: '老师终稿',
    learn: false,
    expected_draft_version: 2,
    request_id: 'confirmation-request-51',
  });
  assert.equal(result.revision.id, 51);
  assert.equal(result.revision.generation_id, 31);
  assert.equal(result.revision.final_feedback_text, '老师终稿');
  assert.equal(result.revision.learn_requested, false);
  assert.equal(result.revision.draft_version, 3);
  assert.equal(result.draft.id, 42);
  assert.equal(result.draft.generation_id, 31);
  assert.equal(result.draft.based_on_revision_id, 51);
  assert.equal(result.draft.feedback_text, '老师终稿');
  assert.equal(result.draft.draft_version, 3);
});

test('structured confirmation sends task revision CAS and keeps names response-only', async () => {
  const envelope = {
    feedback_schema_version: 'class_commentary.student_feedback.v1',
    feedback_schema_status: 'supported',
    student_feedback_items: [{ student_id: 11, student_name: '小王', feedback_text: '老师终稿' }],
    structured_feedback_hash: 'confirmed-hash',
    derived_feedback_text: '小王:\n老师终稿',
  };
  const calls = mockJsonFetch({
    revision: {
      id: 53,
      task_id: 9,
      generation_id: 31,
      revision_no: 2,
      final_feedback_text: '小王:\n老师终稿',
      confirmed_draft_version: 3,
      ...envelope,
    },
    draft: {
      id: 43,
      task_id: 9,
      generation_id: 31,
      teacher_user_id: 4,
      feedback_text: '小王:\n老师终稿',
      draft_version: 3,
      ...envelope,
    },
  });

  const result = await confirmClassCommentaryFeedback(
    9,
    31,
    {
      feedback_schema_version: 'class_commentary.student_feedback.v1',
      student_feedback_items: [{ student_id: 11, feedback_text: '老师终稿' }],
    },
    true,
    2,
    'confirmation-request-53',
    52,
  );

  assert.deepEqual(JSON.parse(String(calls[0].options?.body)), {
    generation_id: 31,
    feedback_schema_version: 'class_commentary.student_feedback.v1',
    student_feedback_items: [{ student_id: 11, feedback_text: '老师终稿' }],
    learn: true,
    expected_draft_version: 2,
    expected_latest_revision_id: 52,
    request_id: 'confirmation-request-53',
  });
  assert.equal(result.revision.confirmed_draft_version, 3);
  assert.equal(result.revision.student_feedback_items[0].student_name, '小王');
});

test('fetchClassCommentaryFeedbackRevisions normalizes revision history', async () => {
  const calls = mockJsonFetch({
    revisions: [{
      id: 52,
      task_id: 9,
      generation_id: 31,
      revision_no: 2,
      previous_revision_id: 51,
      final_feedback_text: '再次确认的终稿',
      learn_requested: false,
      accepted_without_edit: false,
      unchanged_from_previous_revision: false,
      confirmed_at: '2026-07-14T12:00:00Z',
      draft_version: 4,
    }],
  });

  const revisions = await fetchClassCommentaryFeedbackRevisions(9);

  assert.equal(calls[0].path, '/api/class-commentary/tasks/9/feedback-revisions');
  assert.equal(revisions.length, 1);
  assert.equal(revisions[0].id, 52);
  assert.equal(revisions[0].revision_no, 2);
  assert.equal(revisions[0].previous_revision_id, 51);
  assert.equal(revisions[0].confirmed_at, '2026-07-14T12:00:00Z');
  assert.equal(revisions[0].feedback_schema_status, 'plain_text');
  assert.equal(revisions[0].derived_feedback_text, '再次确认的终稿');
});

test('memory helpers normalize status and preserve item-level evidence actions', async () => {
  const calls = mockJsonFetch({
    revision_id: 52,
    status: 'partial',
    retryable: true,
    extraction_status: 'extracted',
    error: 'one projection failed',
    memories: [{
      memory_record_id: 71,
      evidence_id: 81,
      memory_type: 'student_fact',
      memory_text: '绝对值分类讨论仍会遗漏边界条件.',
      student_id: 11,
      student_name: '小林',
      confidence: 0.87,
      evidence_status: 'active',
      active_evidence_count: 2,
      operation_status: 'failed',
      can_revoke: true,
    }],
  });

  const result = await fetchClassCommentaryRevisionMemories(52);

  assert.equal(calls[0].path, '/api/class-commentary/revisions/52/memories');
  assert.equal(result.status, 'partial');
  assert.equal(result.retryable, true);
  assert.equal(result.memories[0].id, 71);
  assert.equal(result.memories[0].evidence_id, 81);
  assert.equal(result.memories[0].memory_type, 'student_fact');
  assert.equal(result.memories[0].active_evidence_count, 2);
  assert.equal(result.memories[0].can_revoke, true);
});

test('memory retry and evidence revoke send stable request ids', async () => {
  const retryCalls = mockJsonFetch({
    memory: { revision_id: 52, status: 'queued', memories: [] },
  });
  const retried = await retryClassCommentaryRevisionMemory(52, 'memory-retry-52');

  assert.equal(retryCalls[0].path, '/api/class-commentary/revisions/52/memory-retry');
  assert.deepEqual(JSON.parse(String(retryCalls[0].options?.body)), {
    request_id: 'memory-retry-52',
  });
  assert.equal(retried.status, 'queued');

  const revokeCalls = mockJsonFetch({
    memory: { revision_id: 52, status: 'complete', memories: [] },
  });
  const revoked = await revokeClassCommentaryMemoryEvidence(81, 'memory-revoke-81');

  assert.equal(revokeCalls[0].path, '/api/class-commentary/memory-evidence/81/revoke');
  assert.deepEqual(JSON.parse(String(revokeCalls[0].options?.body)), {
    request_id: 'memory-revoke-81',
  });
  assert.equal(revoked.status, 'complete');
});

test('skill evolution versions normalize build status diff evaluation and eligibility', async () => {
  const calls = mockJsonFetch({
    skill: {
      id: 'teacher-style',
      registry_id: 7,
      active_version_id: 101,
      can_manage_evolution: true,
      name: '曹曦临',
    },
    versions: [{
      id: 102,
      version_no: 2,
      version_kind: 'candidate',
      candidate_build_id: 201,
      base_version_id: 101,
      base_content: '当前规则',
      content: '新版规则',
      content_diff: '@@ -1 +1 @@',
      review_status: 'pending',
      is_active: false,
      frozen_revision_count: 1,
      frozen_evidence_count: 1,
      frozen_revision_ids: [51],
      frozen_evidence_ids: [81],
      evaluation_snapshot: {
        current_metrics: { normalized_edit_distance: 0.4 },
        candidate_metrics: { normalized_edit_distance: 0.2 },
        change_summary: ['减少重复表述', '先说课堂表现'],
        known_risks: ['一条风险'],
        failed_samples: ['样本 9'],
        failed_sample_count: 1,
      },
      candidate_build: {
        id: 201,
        base_version_id: 101,
        expected_active_version_id: 101,
        candidate_version_id: 102,
        status: 'succeeded',
        effective_task_count: 6,
        supporting_task_count: 3,
      },
    }, {
      id: 101,
      version_no: 1,
      version_kind: 'imported',
      content: '当前规则',
      review_status: 'not_required',
      is_active: true,
    }],
    candidate_builds: [{
      id: 201,
      base_version_id: 101,
      expected_active_version_id: 101,
      candidate_version_id: 102,
      status: 'succeeded',
      effective_task_count: 6,
      supporting_task_count: 3,
      is_terminal: true,
      frozen_task_ids: [9],
      frozen_revision_ids: [51],
      frozen_evidence_ids: [81],
      frozen_memory_record_ids: [71],
      frozen_revision_count: 1,
      frozen_evidence_count: 1,
    }],
    eligibility: {
      eligible: true,
      reason: 'ready',
      effective_task_count: 6,
      supporting_task_count: 3,
      min_effective_tasks: 5,
      min_support_tasks: 3,
    },
  });

  const evolution = await fetchClassCommentarySkillEvolution('teacher-style');

  assert.equal(calls[0].path, '/api/class-commentary/skills/teacher-style/versions');
  assert.equal(evolution.skill.active_version_id, 101);
  assert.equal(evolution.skill.can_manage_evolution, true);
  assert.equal(evolution.skill.name, '曹曦临');
  assert.equal(evolution.versions[0].id, 102);
  assert.equal(evolution.versions[0].base_content, '当前规则');
  assert.equal(evolution.versions[0].content_diff, '@@ -1 +1 @@');
  assert.equal(evolution.versions[0].candidate_build?.status, 'succeeded');
  assert.equal(evolution.versions[0].effective_task_count, 6);
  assert.deepEqual(evolution.versions[0].frozen_revision_ids, [51]);
  assert.equal(evolution.versions[0].evaluation.current_metrics.normalized_edit_distance, 0.4);
  assert.deepEqual(evolution.versions[0].evaluation.change_summary, ['减少重复表述', '先说课堂表现']);
  assert.deepEqual(evolution.versions[0].evaluation.known_risks, ['一条风险']);
  assert.equal(evolution.versions[0].evaluation.failed_sample_count, 1);
  assert.equal(evolution.candidate_builds[0].is_terminal, true);
  assert.deepEqual(evolution.candidate_builds[0].frozen_revision_ids, [51]);
  assert.deepEqual(evolution.candidate_builds[0].frozen_evidence_ids, [81]);
  assert.equal(evolution.eligibility.min_supporting_tasks, 3);
});

test('skill candidate request sends expected active version and accepts a bare build', async () => {
  const calls = mockJsonFetch({
    id: 202,
    expected_active_version_id: 101,
    base_version_id: 101,
    status: 'queued',
    effective_task_count: 6,
    supporting_task_count: 3,
  });

  const build = await createClassCommentarySkillCandidate(
    'teacher/style',
    101,
    'skill-candidate-202',
  );

  assert.equal(calls[0].path, '/api/class-commentary/skills/teacher%2Fstyle/candidates');
  assert.equal(calls[0].options?.method, 'POST');
  assert.deepEqual(JSON.parse(String(calls[0].options?.body)), {
    request_id: 'skill-candidate-202',
    expected_active_version_id: 101,
  });
  assert.equal(build.id, 202);
  assert.equal(build.status, 'queued');
  assert.equal(build.is_terminal, false);
});

test('skill activate and rollback requests use CAS pointer and normalize envelopes', async () => {
  const activateCalls = mockJsonFetch({
    skill: { id: 'teacher-style', active_version_id: 102 },
    version: {
      id: 102,
      version_no: 2,
      version_kind: 'candidate',
      review_status: 'approved',
      is_active: true,
    },
    activation_event: {
      id: 301,
      from_version_id: 101,
      to_version_id: 102,
      active_version_id: 102,
      current_active_version_id: 102,
      reason: 'candidate_approved',
    },
  });

  const activated = await activateClassCommentarySkillVersion(
    'teacher-style',
    102,
    101,
    'skill-activate-301',
  );

  assert.equal(activateCalls[0].path, '/api/class-commentary/skills/teacher-style/versions/102/activate');
  assert.deepEqual(JSON.parse(String(activateCalls[0].options?.body)), {
    request_id: 'skill-activate-301',
    expected_active_version_id: 101,
  });
  assert.equal(activated.skill?.active_version_id, 102);
  assert.equal(activated.version?.is_active, true);
  assert.equal(activated.activation_event.reason, 'candidate_approved');
  assert.equal(activated.activation_event.current_active_version_id, 102);

  const rollbackCalls = mockJsonFetch({
    id: 302,
    from_version_id: 102,
    to_version_id: 101,
    active_version_id: 101,
    current_active_version_id: 102,
    reason: 'rollback',
  });
  const rolledBack = await rollbackClassCommentarySkillVersion(
    'teacher-style',
    101,
    102,
    'skill-rollback-302',
  );

  assert.equal(rollbackCalls[0].path, '/api/class-commentary/skills/teacher-style/versions/101/rollback');
  assert.deepEqual(JSON.parse(String(rollbackCalls[0].options?.body)), {
    request_id: 'skill-rollback-302',
    expected_active_version_id: 102,
  });
  assert.equal(rolledBack.activation_event.to_version_id, 101);
  assert.equal(rolledBack.activation_event.active_version_id, 101);
  assert.equal(rolledBack.activation_event.current_active_version_id, 102);
  assert.equal(rolledBack.activation_event.reason, 'rollback');
});

test('api fetch preserves 409 status and payload for draft conflict recovery', async () => {
  const payload = {
    error: 'draft_version_conflict',
    current_draft: {
      id: 42,
      task_id: 9,
      generation_id: 31,
      feedback_text: '服务器上的较新草稿',
      draft_version: 3,
    },
  };
  mockJsonFetch(payload, 409);

  await assert.rejects(
    () => saveClassCommentaryFeedbackDraft(9, 31, '旧标签页草稿', 2),
    (error: unknown) => {
      assert.ok(error instanceof ApiFetchError);
      assert.equal(error.status, 409);
      assert.deepEqual(error.payload, payload);
      assert.equal(error.message, 'draft_version_conflict');
      return true;
    },
  );
});
