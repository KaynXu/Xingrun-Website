import {
  apiFetch,
  apiUploadFormWithProgress,
  readLocalStorageItem,
  writeLocalStorageItem,
} from './workspaceShared';

export type ClassCommentaryStatus = 'uploaded' | 'transcribing' | 'transcribed' | 'generating' | 'ready' | 'failed';
export type ClassCommentaryFailureStage = '' | 'transcription' | 'generation';

export type ClassCommentarySkill = {
  id: string;
  registry_id?: number;
  name: string;
  filename: string;
  updated_at: string;
};

export type ClassCommentaryCapabilities = {
  memory_learning_enabled: boolean;
  skill_evolution_enabled: boolean;
};

export type ClassCommentaryTask = {
  id: number;
  organization_id: number;
  class_id: number;
  class_name: string;
  teacher_user_id: number;
  status: ClassCommentaryStatus;
  failure_stage: ClassCommentaryFailureStage;
  audio_filename: string;
  transcript_text: string;
  confirmed_transcript_text: string;
  confirmed_transcript_version: number;
  transcribed_at: string;
  skill_id: string;
  skill_name: string;
  skill_filename: string;
  feedback_text: string;
  final_feedback_text: string;
  latest_generation_id: number | null;
  latest_revision_id: number | null;
  generation_seq: number;
  feedback_revision_no: number;
  feedback_confirmed_at: string;
  transcription_error: string;
  generation_error: string;
  created_at: string;
  updated_at: string;
};

export type ClassCommentaryGenerationStatus = 'generating' | 'succeeded' | 'failed';

export type ClassCommentaryGeneration = {
  id: number;
  generation_id: number;
  task_id: number;
  generation_no: number;
  generation_request_id: string;
  status: ClassCommentaryGenerationStatus;
  origin: 'runtime' | 'legacy_migration';
  snapshot_completeness: 'complete' | 'partial';
  skill_id: string;
  model_name: string;
  generated_feedback_text: string;
  missing_snapshot_fields: string[];
  confirmed_transcript_version: number;
  confirmed_transcript_snapshot: string;
  attending_roster_snapshot: Array<{ student_id: number; student_name: string }>;
  skill_content_snapshot: string;
  model_parameters: Record<string, unknown>;
  prompt_payload_snapshot: Record<string, unknown>;
  memory_context_snapshot: Record<string, unknown>;
  error_code: string;
  created_at: string;
  completed_at: string;
  is_latest: boolean;
  latest_revision_id: number | null;
  has_draft: boolean;
  draft_version: number;
};

export type ClassCommentaryFeedbackDraft = {
  id: number;
  task_id: number;
  generation_id: number;
  teacher_user_id: number;
  based_on_revision_id: number | null;
  feedback_text: string;
  content_hash: string;
  draft_version: number;
  created_at: string;
  updated_at: string;
};

export type ClassCommentaryFeedbackRevision = {
  id: number;
  task_id: number;
  generation_id: number;
  revision_no: number;
  previous_revision_id: number | null;
  final_feedback_text: string;
  learn_requested: boolean;
  accepted_without_edit: boolean;
  unchanged_from_previous_revision: boolean;
  learning_evidence_completeness: string;
  generation_diff: Record<string, unknown>;
  previous_revision_diff: Record<string, unknown> | null;
  confirmed_at: string;
  draft_version: number;
};

export type ClassCommentaryGenerationResult = {
  task: ClassCommentaryTask;
  generation: ClassCommentaryGeneration;
};

export type ClassCommentaryConfirmationResult = {
  revision: ClassCommentaryFeedbackRevision;
  draft: ClassCommentaryFeedbackDraft;
};

type ClassCommentaryFeedbackScopeRecord = {
  task_id: number;
  generation_id: number;
};

type ClassCommentarySkillPreferenceUser = {
  id?: number | string | null;
  organization_id?: number | string | null;
};

const validStatuses = new Set<ClassCommentaryStatus>([
  'uploaded',
  'transcribing',
  'transcribed',
  'generating',
  'ready',
  'failed',
]);
const validFailureStages = new Set<ClassCommentaryFailureStage>(['', 'transcription', 'generation']);

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function numberValue(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : Number(value || 0) || 0;
}

function booleanValue(value: unknown): boolean {
  return value === true || value === 1;
}

function nullableNumberValue(value: unknown): number | null {
  const normalized = numberValue(value);
  return normalized > 0 ? normalized : null;
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {};
}

function stringArrayValue(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => stringValue(item)).filter(Boolean) : [];
}

function storageKeyPart(value: unknown, fallback: string): string {
  const normalized = String(value ?? '').trim();
  return normalized || fallback;
}

export function buildClassCommentarySkillPreferenceKey(user: ClassCommentarySkillPreferenceUser | null | undefined): string {
  return `xr_class_commentary_skill:${storageKeyPart(user?.organization_id, '0')}:${storageKeyPart(user?.id, '0')}`;
}

export function readClassCommentarySkillPreference(
  user: ClassCommentarySkillPreferenceUser | null | undefined,
  skills: ClassCommentarySkill[],
): string {
  const savedSkillId = readLocalStorageItem(buildClassCommentarySkillPreferenceKey(user)).trim();
  if (!savedSkillId) {
    return '';
  }
  return skills.some((item) => item.id === savedSkillId) ? savedSkillId : '';
}

export function writeClassCommentarySkillPreference(
  user: ClassCommentarySkillPreferenceUser | null | undefined,
  skillId: string,
): void {
  const normalizedSkillId = skillId.trim();
  if (!normalizedSkillId) {
    return;
  }
  writeLocalStorageItem(buildClassCommentarySkillPreferenceKey(user), normalizedSkillId);
}

export function normalizeClassCommentaryTask(source: Record<string, unknown>): ClassCommentaryTask {
  const status = stringValue(source.status) as ClassCommentaryStatus;
  const failureStage = stringValue(source.failure_stage) as ClassCommentaryFailureStage;
  return {
    id: numberValue(source.id),
    organization_id: numberValue(source.organization_id),
    class_id: numberValue(source.class_id),
    class_name: stringValue(source.class_name),
    teacher_user_id: numberValue(source.teacher_user_id),
    status: validStatuses.has(status) ? status : 'uploaded',
    failure_stage: validFailureStages.has(failureStage) ? failureStage : '',
    audio_filename: stringValue(source.audio_filename),
    transcript_text: stringValue(source.transcript_text),
    confirmed_transcript_text: stringValue(source.confirmed_transcript_text),
    confirmed_transcript_version: numberValue(source.confirmed_transcript_version),
    transcribed_at: stringValue(source.transcribed_at),
    skill_id: stringValue(source.skill_id),
    skill_name: stringValue(source.skill_name),
    skill_filename: stringValue(source.skill_filename),
    feedback_text: stringValue(source.feedback_text),
    final_feedback_text: stringValue(source.final_feedback_text),
    latest_generation_id: nullableNumberValue(source.latest_generation_id),
    latest_revision_id: nullableNumberValue(source.latest_revision_id),
    generation_seq: numberValue(source.generation_seq),
    feedback_revision_no: numberValue(source.feedback_revision_no),
    feedback_confirmed_at: stringValue(source.feedback_confirmed_at),
    transcription_error: stringValue(source.transcription_error),
    generation_error: stringValue(source.generation_error),
    created_at: stringValue(source.created_at),
    updated_at: stringValue(source.updated_at),
  };
}

export function shouldPollClassCommentaryTask(status: ClassCommentaryStatus): boolean {
  return status === 'uploaded' || status === 'transcribing' || status === 'generating';
}

export function classCommentaryStatusLabel(status: ClassCommentaryStatus): string {
  return {
    uploaded: '已上传',
    transcribing: '转写中',
    transcribed: '待确认',
    generating: '生成中',
    ready: '已生成',
    failed: '失败',
  }[status];
}

export function buildClassCommentaryTaskPath(taskId: number): string {
  return `/api/class-commentary/tasks/${encodeURIComponent(String(taskId))}`;
}

export function isClassCommentaryFeedbackRecordInScope(
  record: ClassCommentaryFeedbackScopeRecord | null | undefined,
  taskId: number,
  generationId: number,
): boolean {
  return taskId > 0
    && generationId > 0
    && record?.task_id === taskId
    && record.generation_id === generationId;
}

export function resolveClassCommentaryCopyText(
  draft: Pick<ClassCommentaryFeedbackDraft, 'feedback_text'> | null,
  revision: Pick<ClassCommentaryFeedbackRevision, 'final_feedback_text'> | null,
  generation: Pick<ClassCommentaryGeneration, 'generated_feedback_text'> | null,
  blocked = false,
): string {
  if (blocked) {
    return '';
  }
  return draft?.feedback_text
    || revision?.final_feedback_text
    || generation?.generated_feedback_text
    || '';
}

function normalizeClassCommentarySkill(item: unknown): ClassCommentarySkill {
  const record = item && typeof item === 'object' ? (item as Record<string, unknown>) : {};
  return {
    id: stringValue(record.id),
    registry_id: numberValue(record.registry_id),
    name: stringValue(record.name),
    filename: stringValue(record.filename),
    updated_at: stringValue(record.updated_at),
  };
}

export function normalizeClassCommentaryGeneration(source: Record<string, unknown>): ClassCommentaryGeneration {
  const rawStatus = stringValue(source.status);
  const status: ClassCommentaryGenerationStatus = rawStatus === 'succeeded' || rawStatus === 'failed'
    ? rawStatus
    : 'generating';
  return {
    id: numberValue(source.id || source.generation_id),
    generation_id: numberValue(source.generation_id || source.id),
    task_id: numberValue(source.task_id),
    generation_no: numberValue(source.generation_no),
    generation_request_id: stringValue(source.generation_request_id),
    status,
    origin: stringValue(source.origin) === 'legacy_migration' ? 'legacy_migration' : 'runtime',
    snapshot_completeness: stringValue(source.snapshot_completeness) === 'partial' ? 'partial' : 'complete',
    skill_id: stringValue(source.skill_id),
    model_name: stringValue(source.model_name),
    generated_feedback_text: stringValue(source.generated_feedback_text),
    missing_snapshot_fields: stringArrayValue(source.missing_snapshot_fields),
    confirmed_transcript_version: numberValue(source.confirmed_transcript_version),
    confirmed_transcript_snapshot: stringValue(source.confirmed_transcript_snapshot),
    attending_roster_snapshot: Array.isArray(source.attending_roster_snapshot)
      ? source.attending_roster_snapshot.map((item) => {
        const record = recordValue(item);
        return {
          student_id: numberValue(record.student_id),
          student_name: stringValue(record.student_name),
        };
      })
      : [],
    skill_content_snapshot: stringValue(source.skill_content_snapshot),
    model_parameters: recordValue(source.model_parameters),
    prompt_payload_snapshot: recordValue(source.prompt_payload_snapshot),
    memory_context_snapshot: recordValue(source.memory_context_snapshot),
    error_code: stringValue(source.error_code),
    created_at: stringValue(source.created_at),
    completed_at: stringValue(source.completed_at),
    is_latest: booleanValue(source.is_latest),
    latest_revision_id: nullableNumberValue(source.latest_revision_id),
    has_draft: booleanValue(source.has_draft),
    draft_version: numberValue(source.draft_version),
  };
}

function normalizeClassCommentaryFeedbackDraft(source: Record<string, unknown>): ClassCommentaryFeedbackDraft {
  return {
    id: numberValue(source.id),
    task_id: numberValue(source.task_id),
    generation_id: numberValue(source.generation_id),
    teacher_user_id: numberValue(source.teacher_user_id),
    based_on_revision_id: nullableNumberValue(source.based_on_revision_id),
    feedback_text: stringValue(source.feedback_text),
    content_hash: stringValue(source.content_hash),
    draft_version: numberValue(source.draft_version),
    created_at: stringValue(source.created_at),
    updated_at: stringValue(source.updated_at),
  };
}

function normalizeClassCommentaryFeedbackRevision(source: Record<string, unknown>): ClassCommentaryFeedbackRevision {
  return {
    id: numberValue(source.id || source.revision_id),
    task_id: numberValue(source.task_id),
    generation_id: numberValue(source.generation_id),
    revision_no: numberValue(source.revision_no),
    previous_revision_id: nullableNumberValue(source.previous_revision_id),
    final_feedback_text: stringValue(source.final_feedback_text),
    learn_requested: booleanValue(source.learn_requested),
    accepted_without_edit: booleanValue(source.accepted_without_edit),
    unchanged_from_previous_revision: booleanValue(source.unchanged_from_previous_revision),
    learning_evidence_completeness: stringValue(source.learning_evidence_completeness),
    generation_diff: recordValue(source.generation_diff),
    previous_revision_diff: source.previous_revision_diff === null || source.previous_revision_diff === undefined
      ? null
      : recordValue(source.previous_revision_diff),
    confirmed_at: stringValue(source.confirmed_at),
    draft_version: numberValue(source.draft_version),
  };
}

export async function fetchClassCommentarySkills(): Promise<ClassCommentarySkill[]> {
  const payload = await apiFetch<{ skills?: unknown[] }>('/api/class-commentary/skills');
  const skills = Array.isArray(payload.skills) ? payload.skills : [];
  return skills.map((item) => normalizeClassCommentarySkill(item));
}

export async function fetchClassCommentaryCapabilities(): Promise<ClassCommentaryCapabilities> {
  const payload = await apiFetch<Partial<ClassCommentaryCapabilities>>('/api/class-commentary/capabilities');
  return {
    memory_learning_enabled: payload.memory_learning_enabled === true,
    skill_evolution_enabled: payload.skill_evolution_enabled === true,
  };
}

export async function fetchClassCommentaryTasks(): Promise<ClassCommentaryTask[]> {
  const payload = await apiFetch<{ tasks?: unknown[] }>('/api/class-commentary/tasks');
  const tasks = Array.isArray(payload.tasks) ? payload.tasks : [];
  return tasks.map((item) => normalizeClassCommentaryTask(item && typeof item === 'object' ? item as Record<string, unknown> : {}));
}

export async function createClassCommentaryTask(
  classId: number,
  audio: File,
  onProgress: (progress: number) => void = () => {},
): Promise<ClassCommentaryTask> {
  const body = new FormData();
  body.append('class_id', String(classId));
  body.append('audio', audio);
  const payload = await apiUploadFormWithProgress<Record<string, unknown>>(
    '/api/class-commentary/tasks',
    body,
    onProgress,
  );
  return normalizeClassCommentaryTask(payload);
}

export async function createClassCommentaryTextTask(classId: number, text: string): Promise<ClassCommentaryTask> {
  const payload = await apiFetch<Record<string, unknown>>('/api/class-commentary/tasks/text', {
    method: 'POST',
    body: JSON.stringify({ class_id: classId, confirmed_transcript_text: text }),
  });
  return normalizeClassCommentaryTask(payload);
}

export async function fetchClassCommentaryTask(taskId: number): Promise<ClassCommentaryTask> {
  return normalizeClassCommentaryTask(await apiFetch<Record<string, unknown>>(buildClassCommentaryTaskPath(taskId)));
}

export async function saveClassCommentaryTranscript(taskId: number, text: string): Promise<ClassCommentaryTask> {
  const payload = await apiFetch<Record<string, unknown>>(`${buildClassCommentaryTaskPath(taskId)}/transcript`, {
    method: 'PUT',
    body: JSON.stringify({ confirmed_transcript_text: text }),
  });
  return normalizeClassCommentaryTask(payload);
}

export async function generateClassCommentaryFeedback(
  taskId: number,
  skillId: string,
  attendingStudentIds: number[],
  requestId: string,
): Promise<ClassCommentaryGenerationResult> {
  const payload = await apiFetch<Record<string, unknown>>(`${buildClassCommentaryTaskPath(taskId)}/generate`, {
    method: 'POST',
    body: JSON.stringify({
      request_id: requestId,
      skill_id: skillId,
      attending_student_ids: attendingStudentIds,
    }),
  });
  return {
    task: normalizeClassCommentaryTask(recordValue(payload.task || payload)),
    generation: normalizeClassCommentaryGeneration(recordValue(payload.generation || payload)),
  };
}

export async function fetchClassCommentaryGenerations(taskId: number): Promise<ClassCommentaryGeneration[]> {
  const payload = await apiFetch<{ generations?: unknown[] }>(`${buildClassCommentaryTaskPath(taskId)}/generations`);
  return (Array.isArray(payload.generations) ? payload.generations : [])
    .map((item) => normalizeClassCommentaryGeneration(recordValue(item)));
}

export async function fetchClassCommentaryGeneration(
  taskId: number,
  generationId: number,
): Promise<ClassCommentaryGeneration> {
  const payload = await apiFetch<Record<string, unknown>>(
    `${buildClassCommentaryTaskPath(taskId)}/generations/${encodeURIComponent(String(generationId))}`,
  );
  return normalizeClassCommentaryGeneration(recordValue(payload.generation || payload));
}

function buildClassCommentaryDraftPath(taskId: number, generationId: number): string {
  return `${buildClassCommentaryTaskPath(taskId)}/generations/${encodeURIComponent(String(generationId))}/feedback-draft`;
}

export async function fetchClassCommentaryFeedbackDraft(
  taskId: number,
  generationId: number,
): Promise<ClassCommentaryFeedbackDraft | null> {
  const payload = await apiFetch<Record<string, unknown>>(buildClassCommentaryDraftPath(taskId, generationId));
  return payload.draft ? normalizeClassCommentaryFeedbackDraft(recordValue(payload.draft)) : null;
}

export async function saveClassCommentaryFeedbackDraft(
  taskId: number,
  generationId: number,
  feedbackText: string,
  expectedDraftVersion: number,
  basedOnRevisionId: number | null = null,
): Promise<ClassCommentaryFeedbackDraft> {
  const payload = await apiFetch<Record<string, unknown>>(buildClassCommentaryDraftPath(taskId, generationId), {
    method: 'PUT',
    body: JSON.stringify({
      feedback_text: feedbackText,
      expected_draft_version: expectedDraftVersion,
      ...(basedOnRevisionId === null ? {} : { based_on_revision_id: basedOnRevisionId }),
    }),
  });
  return normalizeClassCommentaryFeedbackDraft(recordValue(payload.draft || payload));
}

export async function confirmClassCommentaryFeedback(
  taskId: number,
  generationId: number,
  feedbackText: string,
  learn: boolean,
  expectedDraftVersion: number,
  requestId: string,
): Promise<ClassCommentaryConfirmationResult> {
  const payload = await apiFetch<Record<string, unknown>>(
    `${buildClassCommentaryTaskPath(taskId)}/feedback-confirmations`,
    {
      method: 'POST',
      body: JSON.stringify({
        generation_id: generationId,
        feedback_text: feedbackText,
        learn,
        expected_draft_version: expectedDraftVersion,
        request_id: requestId,
      }),
    },
  );
  return {
    revision: normalizeClassCommentaryFeedbackRevision(recordValue(payload.revision || payload)),
    draft: normalizeClassCommentaryFeedbackDraft(recordValue(payload.draft)),
  };
}

export async function fetchClassCommentaryFeedbackRevisions(
  taskId: number,
): Promise<ClassCommentaryFeedbackRevision[]> {
  const payload = await apiFetch<{ revisions?: unknown[] }>(
    `${buildClassCommentaryTaskPath(taskId)}/feedback-revisions`,
  );
  return (Array.isArray(payload.revisions) ? payload.revisions : [])
    .map((item) => normalizeClassCommentaryFeedbackRevision(recordValue(item)));
}
