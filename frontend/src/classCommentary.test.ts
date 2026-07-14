import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { afterEach, test } from 'node:test';
import {
  buildClassCommentarySkillPreferenceKey,
  buildClassCommentaryTaskPath,
  classCommentaryStatusLabel,
  confirmClassCommentaryFeedback,
  fetchClassCommentaryTasks,
  fetchClassCommentaryFeedbackDraft,
  fetchClassCommentaryFeedbackRevisions,
  fetchClassCommentaryGeneration,
  fetchClassCommentaryGenerations,
  createClassCommentaryTextTask,
  generateClassCommentaryFeedback,
  isClassCommentaryFeedbackRecordInScope,
  normalizeClassCommentaryTask,
  readClassCommentarySkillPreference,
  resolveClassCommentaryCopyText,
  saveClassCommentaryFeedbackDraft,
  shouldPollClassCommentaryTask,
  writeClassCommentarySkillPreference,
} from './classCommentary';
import { ApiFetchError } from './workspaceShared';

const source = readFileSync(new URL('./classCommentary.ts', import.meta.url), 'utf8');
const originalLocalStorage = globalThis.localStorage;
const originalFetch = globalThis.fetch;

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
