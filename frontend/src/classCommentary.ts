import { apiFetch, apiUploadFormWithProgress } from './workspaceShared';

export type ClassCommentaryStatus = 'uploaded' | 'transcribing' | 'transcribed' | 'generating' | 'ready' | 'failed';
export type ClassCommentaryFailureStage = '' | 'transcription' | 'generation';

export type ClassCommentarySkill = {
  id: string;
  name: string;
  filename: string;
  updated_at: string;
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
  transcribed_at: string;
  skill_id: string;
  skill_name: string;
  skill_filename: string;
  feedback_text: string;
  transcription_error: string;
  generation_error: string;
  created_at: string;
  updated_at: string;
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
    transcribed_at: stringValue(source.transcribed_at),
    skill_id: stringValue(source.skill_id),
    skill_name: stringValue(source.skill_name),
    skill_filename: stringValue(source.skill_filename),
    feedback_text: stringValue(source.feedback_text),
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

function normalizeClassCommentarySkill(item: unknown): ClassCommentarySkill {
  const record = item && typeof item === 'object' ? (item as Record<string, unknown>) : {};
  return {
    id: stringValue(record.id),
    name: stringValue(record.name),
    filename: stringValue(record.filename),
    updated_at: stringValue(record.updated_at),
  };
}

export async function fetchClassCommentarySkills(): Promise<ClassCommentarySkill[]> {
  const payload = await apiFetch<{ skills?: unknown[] }>('/api/class-commentary/skills');
  const skills = Array.isArray(payload.skills) ? payload.skills : [];
  return skills.map((item) => normalizeClassCommentarySkill(item));
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

export async function generateClassCommentaryFeedback(taskId: number, skillId: string): Promise<ClassCommentaryTask> {
  const payload = await apiFetch<Record<string, unknown>>(`${buildClassCommentaryTaskPath(taskId)}/generate`, {
    method: 'POST',
    body: JSON.stringify({ skill_id: skillId }),
  });
  return normalizeClassCommentaryTask(payload);
}
