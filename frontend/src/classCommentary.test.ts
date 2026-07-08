import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { afterEach, test } from 'node:test';
import {
  buildClassCommentarySkillPreferenceKey,
  buildClassCommentaryTaskPath,
  classCommentaryStatusLabel,
  fetchClassCommentaryTasks,
  createClassCommentaryTextTask,
  normalizeClassCommentaryTask,
  readClassCommentarySkillPreference,
  shouldPollClassCommentaryTask,
  writeClassCommentarySkillPreference,
} from './classCommentary';

const source = readFileSync(new URL('./classCommentary.ts', import.meta.url), 'utf8');
const originalLocalStorage = globalThis.localStorage;

afterEach(() => {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: originalLocalStorage,
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

test('generateClassCommentaryFeedback sends attending student ids to generation api', () => {
  assert.match(source, /export async function generateClassCommentaryFeedback\(taskId: number, skillId: string, attendingStudentIds: number\[]/);
  assert.match(source, /body: JSON\.stringify\(\{ skill_id: skillId, attending_student_ids: attendingStudentIds \}\)/);
});
