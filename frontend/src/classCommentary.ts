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
  active_version_id?: number | null;
  can_manage_evolution?: boolean;
  name: string;
  filename: string;
  updated_at: string;
};

export type ClassCommentaryCapabilities = {
  memory_learning_enabled: boolean;
  skill_evolution_enabled: boolean;
  structured_feedback_enabled: boolean;
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

export const CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1 = 'class_commentary.student_feedback.v1';

export type ClassCommentaryStudentFeedbackItem = {
  student_id: number;
  student_name: string;
  feedback_text: string;
};

export type ClassCommentaryFeedbackReadEnvelope =
  | {
    feedback_schema_version: '';
    feedback_schema_status: 'plain_text';
    student_feedback_items: [];
    structured_feedback_hash: '';
    derived_feedback_text: string;
    writable: true;
  }
  | {
    feedback_schema_version: typeof CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1;
    feedback_schema_status: 'supported';
    student_feedback_items: ClassCommentaryStudentFeedbackItem[];
    structured_feedback_hash: string;
    derived_feedback_text: string;
    writable: true;
  }
  | {
    feedback_schema_version: string;
    feedback_schema_status: 'unsupported' | 'invalid';
    student_feedback_items: [];
    structured_feedback_hash: string;
    derived_feedback_text: string;
    writable: false;
  };

export type ClassCommentaryGeneration = ClassCommentaryFeedbackReadEnvelope & {
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

export type ClassCommentaryFeedbackDraft = ClassCommentaryFeedbackReadEnvelope & {
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

export type ClassCommentaryFeedbackRevision = ClassCommentaryFeedbackReadEnvelope & {
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

export type ClassCommentaryMemoryStatus =
  | 'not_requested'
  | 'queued'
  | 'extracting'
  | 'syncing'
  | 'complete'
  | 'partial'
  | 'failed'
  | 'obsolete';

export type ClassCommentaryLearnedMemory = {
  id: number;
  evidence_id: number;
  memory_type: 'teacher_style' | 'student_fact';
  memory_text: string;
  student_id: number | null;
  student_name: string;
  confidence: number;
  evidence_status: 'active' | 'revoked' | 'superseded';
  active_evidence_count: number;
  operation_status: string;
  can_revoke: boolean;
};

export type ClassCommentaryMemorySummary = {
  revision_id: number;
  status: ClassCommentaryMemoryStatus;
  retryable: boolean;
  extraction_status: string;
  error: string;
  memories: ClassCommentaryLearnedMemory[];
};

export type ClassCommentarySkillCandidateBuildStatus =
  | 'queued'
  | 'running'
  | 'retry_wait'
  | 'succeeded'
  | 'failed'
  | 'obsolete';

export type ClassCommentarySkillCandidateBuild = {
  id: number;
  expected_active_version_id: number;
  base_version_id: number;
  candidate_version_id: number | null;
  effective_task_count: number;
  supporting_task_count: number;
  min_effective_tasks: number;
  min_supporting_tasks: number;
  status: ClassCommentarySkillCandidateBuildStatus;
  error_message: string;
  can_retry: boolean;
  is_terminal: boolean;
  is_stale: boolean;
  stale_reason: string;
  source_cutoff_at: string;
  selection_policy_version: string;
  frozen_task_ids: number[];
  frozen_revision_ids: number[];
  frozen_evidence_ids: number[];
  frozen_memory_record_ids: number[];
  frozen_revision_count: number;
  frozen_evidence_count: number;
  created_at: string;
  started_at: string;
  completed_at: string;
};

export type ClassCommentarySkillEvaluation = {
  current_metrics: Record<string, unknown>;
  candidate_metrics: Record<string, unknown>;
  change_summary: string[];
  known_risks: string[];
  failed_samples: string[];
  failed_sample_count: number;
};

export type ClassCommentarySkillVersion = {
  id: number;
  version_no: number;
  version_kind: 'imported' | 'candidate';
  candidate_build_id: number | null;
  content: string;
  content_hash: string;
  content_diff: string;
  base_version_id: number | null;
  base_content: string;
  review_status: 'not_required' | 'pending' | 'approved' | 'rejected';
  is_active: boolean;
  is_stale: boolean;
  stale_reason: string;
  effective_task_count: number;
  supporting_task_count: number;
  frozen_revision_count: number;
  frozen_evidence_count: number;
  frozen_revision_ids: number[];
  frozen_evidence_ids: number[];
  evaluation: ClassCommentarySkillEvaluation;
  candidate_build: ClassCommentarySkillCandidateBuild | null;
  created_at: string;
  reviewed_at: string;
};

export type ClassCommentarySkillEligibility = {
  eligible: boolean;
  reason: string;
  effective_task_count: number;
  supporting_task_count: number;
  min_effective_tasks: number;
  min_supporting_tasks: number;
};

export type ClassCommentarySkillEvolution = {
  skill: ClassCommentarySkill & { active_version_id: number | null };
  versions: ClassCommentarySkillVersion[];
  candidate_builds: ClassCommentarySkillCandidateBuild[];
  eligibility: ClassCommentarySkillEligibility;
};

export type ClassCommentarySkillActivationEvent = {
  id: number;
  from_version_id: number | null;
  to_version_id: number;
  active_version_id: number | null;
  current_active_version_id: number | null;
  reason: 'initial_import' | 'candidate_approved' | 'rollback';
  created_at: string;
};

export type ClassCommentarySkillActivationResult = {
  skill: (ClassCommentarySkill & { active_version_id: number | null }) | null;
  version: ClassCommentarySkillVersion | null;
  activation_event: ClassCommentarySkillActivationEvent;
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

function numberArrayValue(value: unknown): number[] {
  return Array.isArray(value) ? value.map((item) => numberValue(item)).filter((item) => item > 0) : [];
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

function invalidClassCommentaryFeedbackEnvelope(
  schemaVersion: string,
  structuredHash: string,
  derivedText: string,
): ClassCommentaryFeedbackReadEnvelope {
  return {
    feedback_schema_version: schemaVersion,
    feedback_schema_status: 'invalid',
    student_feedback_items: [],
    structured_feedback_hash: structuredHash,
    derived_feedback_text: derivedText,
    writable: false,
  };
}

function normalizeClassCommentaryFeedbackEnvelope(
  source: Record<string, unknown>,
  legacyText: string,
): ClassCommentaryFeedbackReadEnvelope {
  const schemaVersion = stringValue(source.feedback_schema_version);
  const structuredHash = stringValue(source.structured_feedback_hash);
  const derivedText = stringValue(source.derived_feedback_text) || legacyText;
  if (!schemaVersion) {
    return {
      feedback_schema_version: '',
      feedback_schema_status: 'plain_text',
      student_feedback_items: [],
      structured_feedback_hash: '',
      derived_feedback_text: derivedText,
      writable: true,
    };
  }
  if (schemaVersion !== CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1) {
    return {
      feedback_schema_version: schemaVersion,
      feedback_schema_status: 'unsupported',
      student_feedback_items: [],
      structured_feedback_hash: structuredHash,
      derived_feedback_text: derivedText,
      writable: false,
    };
  }
  const schemaStatus = stringValue(source.feedback_schema_status);
  if (schemaStatus === 'unsupported') {
    return {
      feedback_schema_version: schemaVersion,
      feedback_schema_status: 'unsupported',
      student_feedback_items: [],
      structured_feedback_hash: structuredHash,
      derived_feedback_text: derivedText,
      writable: false,
    };
  }
  if (schemaStatus !== 'supported' || !Array.isArray(source.student_feedback_items)) {
    return invalidClassCommentaryFeedbackEnvelope(schemaVersion, structuredHash, derivedText);
  }
  const items: ClassCommentaryStudentFeedbackItem[] = [];
  const studentIds = new Set<number>();
  for (const rawItem of source.student_feedback_items) {
    const item = recordValue(rawItem);
    const studentId = item.student_id;
    const studentName = item.student_name;
    const feedbackText = item.feedback_text;
    if (
      typeof studentId !== 'number'
      || !Number.isInteger(studentId)
      || studentId <= 0
      || studentIds.has(studentId)
      || typeof studentName !== 'string'
      || !studentName.trim()
      || typeof feedbackText !== 'string'
      || !feedbackText.trim()
    ) {
      return invalidClassCommentaryFeedbackEnvelope(schemaVersion, structuredHash, derivedText);
    }
    studentIds.add(studentId);
    items.push({
      student_id: studentId,
      student_name: studentName,
      feedback_text: feedbackText,
    });
  }
  if (!items.length || !structuredHash || !derivedText) {
    return invalidClassCommentaryFeedbackEnvelope(schemaVersion, structuredHash, derivedText);
  }
  return {
    feedback_schema_version: CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
    feedback_schema_status: 'supported',
    student_feedback_items: items,
    structured_feedback_hash: structuredHash,
    derived_feedback_text: derivedText,
    writable: true,
  };
}

function normalizeClassCommentarySkill(item: unknown): ClassCommentarySkill {
  const record = item && typeof item === 'object' ? (item as Record<string, unknown>) : {};
  return {
    id: stringValue(record.id || record.skill_id),
    registry_id: numberValue(record.registry_id),
    active_version_id: nullableNumberValue(record.active_version_id),
    can_manage_evolution: record.can_manage_evolution === undefined
      ? undefined
      : booleanValue(record.can_manage_evolution),
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
  const generatedFeedbackText = stringValue(source.generated_feedback_text);
  const feedbackEnvelope = normalizeClassCommentaryFeedbackEnvelope(source, generatedFeedbackText);
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
    generated_feedback_text: generatedFeedbackText || feedbackEnvelope.derived_feedback_text,
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
    ...feedbackEnvelope,
  };
}

function normalizeClassCommentaryFeedbackDraft(source: Record<string, unknown>): ClassCommentaryFeedbackDraft {
  const feedbackText = stringValue(source.feedback_text);
  const feedbackEnvelope = normalizeClassCommentaryFeedbackEnvelope(source, feedbackText);
  return {
    id: numberValue(source.id),
    task_id: numberValue(source.task_id),
    generation_id: numberValue(source.generation_id),
    teacher_user_id: numberValue(source.teacher_user_id),
    based_on_revision_id: nullableNumberValue(source.based_on_revision_id),
    feedback_text: feedbackText || feedbackEnvelope.derived_feedback_text,
    content_hash: stringValue(source.content_hash),
    draft_version: numberValue(source.draft_version),
    created_at: stringValue(source.created_at),
    updated_at: stringValue(source.updated_at),
    ...feedbackEnvelope,
  };
}

function normalizeClassCommentaryFeedbackRevision(source: Record<string, unknown>): ClassCommentaryFeedbackRevision {
  const finalFeedbackText = stringValue(source.final_feedback_text);
  const feedbackEnvelope = normalizeClassCommentaryFeedbackEnvelope(source, finalFeedbackText);
  return {
    id: numberValue(source.id || source.revision_id),
    task_id: numberValue(source.task_id),
    generation_id: numberValue(source.generation_id),
    revision_no: numberValue(source.revision_no),
    previous_revision_id: nullableNumberValue(source.previous_revision_id),
    final_feedback_text: finalFeedbackText || feedbackEnvelope.derived_feedback_text,
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
    ...feedbackEnvelope,
  };
}

function normalizeClassCommentaryMemorySummary(source: Record<string, unknown>): ClassCommentaryMemorySummary {
  const rawStatus = stringValue(source.status);
  const validMemoryStatuses = new Set<ClassCommentaryMemoryStatus>([
    'not_requested',
    'queued',
    'extracting',
    'syncing',
    'complete',
    'partial',
    'failed',
    'obsolete',
  ]);
  return {
    revision_id: numberValue(source.revision_id),
    status: validMemoryStatuses.has(rawStatus as ClassCommentaryMemoryStatus)
      ? rawStatus as ClassCommentaryMemoryStatus
      : 'not_requested',
    retryable: booleanValue(source.retryable),
    extraction_status: stringValue(source.extraction_status),
    error: stringValue(source.error),
    memories: (Array.isArray(source.memories) ? source.memories : []).map((item) => {
      const record = recordValue(item);
      return {
        id: numberValue(record.id || record.memory_record_id),
        evidence_id: numberValue(record.evidence_id),
        memory_type: stringValue(record.memory_type) === 'student_fact' ? 'student_fact' : 'teacher_style',
        memory_text: stringValue(record.memory_text),
        student_id: nullableNumberValue(record.student_id),
        student_name: stringValue(record.student_name),
        confidence: Number(record.confidence || 0),
        evidence_status: stringValue(record.evidence_status) === 'revoked'
          ? 'revoked'
          : stringValue(record.evidence_status) === 'superseded'
            ? 'superseded'
            : 'active',
        active_evidence_count: numberValue(record.active_evidence_count),
        operation_status: stringValue(record.operation_status),
        can_revoke: booleanValue(record.can_revoke),
      };
    }),
  };
}

function normalizeClassCommentarySkillCandidateBuild(source: Record<string, unknown>): ClassCommentarySkillCandidateBuild {
  const rawStatus = stringValue(source.status);
  const validStatuses = new Set<ClassCommentarySkillCandidateBuildStatus>([
    'queued',
    'running',
    'retry_wait',
    'succeeded',
    'failed',
    'obsolete',
  ]);
  const status = validStatuses.has(rawStatus as ClassCommentarySkillCandidateBuildStatus)
    ? rawStatus as ClassCommentarySkillCandidateBuildStatus
    : 'failed';
  const terminalStatus = status === 'succeeded' || status === 'failed' || status === 'obsolete';
  return {
    id: numberValue(source.id),
    expected_active_version_id: numberValue(source.expected_active_version_id),
    base_version_id: numberValue(source.base_version_id),
    candidate_version_id: nullableNumberValue(source.candidate_version_id),
    effective_task_count: numberValue(source.effective_task_count),
    supporting_task_count: numberValue(source.supporting_task_count),
    min_effective_tasks: numberValue(source.min_effective_tasks),
    min_supporting_tasks: numberValue(source.min_supporting_tasks || source.min_support_tasks),
    status,
    error_message: stringValue(source.error_message || source.last_error),
    can_retry: source.can_retry === undefined ? status === 'failed' : booleanValue(source.can_retry),
    is_terminal: source.is_terminal === undefined ? terminalStatus : booleanValue(source.is_terminal),
    is_stale: booleanValue(source.is_stale),
    stale_reason: stringValue(source.stale_reason),
    source_cutoff_at: stringValue(source.source_cutoff_at),
    selection_policy_version: stringValue(source.selection_policy_version),
    frozen_task_ids: numberArrayValue(source.frozen_task_ids),
    frozen_revision_ids: numberArrayValue(source.frozen_revision_ids),
    frozen_evidence_ids: numberArrayValue(source.frozen_evidence_ids),
    frozen_memory_record_ids: numberArrayValue(source.frozen_memory_record_ids),
    frozen_revision_count: numberValue(source.frozen_revision_count),
    frozen_evidence_count: numberValue(source.frozen_evidence_count),
    created_at: stringValue(source.created_at),
    started_at: stringValue(source.started_at),
    completed_at: stringValue(source.completed_at),
  };
}

function normalizeClassCommentarySkillEvaluation(source: Record<string, unknown>): ClassCommentarySkillEvaluation {
  const metrics = recordValue(source.metrics);
  const failedSamples = stringArrayValue(source.failed_samples || source.failures);
  return {
    current_metrics: recordValue(source.current_metrics || source.current || metrics.current),
    candidate_metrics: recordValue(
      source.candidate_metrics || source.candidate || metrics.candidate || source.metrics || source,
    ),
    change_summary: stringArrayValue(source.change_summary || source.changes),
    known_risks: stringArrayValue(source.known_risks || source.risks),
    failed_samples: failedSamples,
    failed_sample_count: numberValue(source.failed_sample_count || source.failed_samples_count)
      || failedSamples.length,
  };
}

function normalizeClassCommentarySkillVersion(
  source: Record<string, unknown>,
  activeVersionId = 0,
): ClassCommentarySkillVersion {
  const rawReviewStatus = stringValue(source.review_status);
  const reviewStatus = rawReviewStatus === 'pending'
    || rawReviewStatus === 'approved'
    || rawReviewStatus === 'rejected'
    ? rawReviewStatus
    : 'not_required';
  const candidateBuildSource = recordValue(source.candidate_build);
  const candidateBuild = numberValue(candidateBuildSource.id) > 0
    ? normalizeClassCommentarySkillCandidateBuild(candidateBuildSource)
    : null;
  const evaluationSource = recordValue(source.evaluation_snapshot || source.evaluation);
  const diffSource = recordValue(source.content_diff || source.diff);
  return {
    id: numberValue(source.id),
    version_no: numberValue(source.version_no),
    version_kind: stringValue(source.version_kind) === 'candidate' ? 'candidate' : 'imported',
    candidate_build_id: nullableNumberValue(source.candidate_build_id),
    content: stringValue(source.content),
    content_hash: stringValue(source.content_hash),
    content_diff: stringValue(source.content_diff || source.unified_diff || diffSource.unified_diff || diffSource.text),
    base_version_id: nullableNumberValue(source.base_version_id),
    base_content: stringValue(source.base_content),
    review_status: reviewStatus,
    is_active: source.is_active === undefined
      ? numberValue(source.id) === activeVersionId
      : booleanValue(source.is_active),
    is_stale: booleanValue(source.is_stale),
    stale_reason: stringValue(source.stale_reason),
    effective_task_count: numberValue(source.effective_task_count || candidateBuild?.effective_task_count),
    supporting_task_count: numberValue(source.supporting_task_count || candidateBuild?.supporting_task_count),
    frozen_revision_count: numberValue(source.frozen_revision_count),
    frozen_evidence_count: numberValue(source.frozen_evidence_count),
    frozen_revision_ids: numberArrayValue(source.frozen_revision_ids),
    frozen_evidence_ids: numberArrayValue(source.frozen_evidence_ids),
    evaluation: normalizeClassCommentarySkillEvaluation(evaluationSource),
    candidate_build: candidateBuild,
    created_at: stringValue(source.created_at),
    reviewed_at: stringValue(source.reviewed_at),
  };
}

function normalizeClassCommentarySkillEligibility(source: Record<string, unknown>): ClassCommentarySkillEligibility {
  return {
    eligible: booleanValue(source.eligible),
    reason: stringValue(source.reason),
    effective_task_count: numberValue(source.effective_task_count),
    supporting_task_count: numberValue(source.supporting_task_count),
    min_effective_tasks: numberValue(source.min_effective_tasks),
    min_supporting_tasks: numberValue(source.min_supporting_tasks || source.min_support_tasks),
  };
}

function normalizeClassCommentarySkillEvolution(payload: unknown, skillId: string): ClassCommentarySkillEvolution {
  const payloadRecord = recordValue(payload);
  const source = recordValue(payloadRecord.evolution || payload);
  const skillSource = recordValue(source.skill);
  const activeVersionId = numberValue(skillSource.active_version_id || source.active_version_id);
  const rawVersions = Array.isArray(payload)
    ? payload
    : Array.isArray(source.versions)
      ? source.versions
      : [];
  const rawBuilds = Array.isArray(source.candidate_builds)
    ? source.candidate_builds
    : Array.isArray(source.builds)
      ? source.builds
      : [];
  const versions = rawVersions
    .map((item) => normalizeClassCommentarySkillVersion(recordValue(item), activeVersionId))
    .sort((left, right) => right.version_no - left.version_no);
  const candidateBuilds = rawBuilds
    .map((item) => normalizeClassCommentarySkillCandidateBuild(recordValue(item)))
    .sort((left, right) => right.id - left.id);
  const normalizedSkill = normalizeClassCommentarySkill({
    ...skillSource,
    id: stringValue(skillSource.id || skillSource.skill_id) || skillId,
    active_version_id: activeVersionId,
  });
  return {
    skill: {
      ...normalizedSkill,
      active_version_id: activeVersionId > 0 ? activeVersionId : null,
    },
    versions,
    candidate_builds: candidateBuilds,
    eligibility: normalizeClassCommentarySkillEligibility(recordValue(source.eligibility)),
  };
}

function normalizeClassCommentarySkillActivationEvent(source: Record<string, unknown>): ClassCommentarySkillActivationEvent {
  const rawReason = stringValue(source.reason);
  return {
    id: numberValue(source.id),
    from_version_id: nullableNumberValue(source.from_version_id),
    to_version_id: numberValue(source.to_version_id),
    active_version_id: nullableNumberValue(source.active_version_id || source.to_version_id),
    current_active_version_id: nullableNumberValue(
      source.current_active_version_id || source.active_version_id || source.to_version_id,
    ),
    reason: rawReason === 'rollback' || rawReason === 'initial_import' ? rawReason : 'candidate_approved',
    created_at: stringValue(source.created_at),
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
    structured_feedback_enabled: payload.structured_feedback_enabled === true,
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

export async function fetchClassCommentaryRevisionMemories(
  revisionId: number,
): Promise<ClassCommentaryMemorySummary> {
  const payload = await apiFetch<Record<string, unknown>>(
    `/api/class-commentary/revisions/${encodeURIComponent(String(revisionId))}/memories`,
  );
  return normalizeClassCommentaryMemorySummary(payload);
}

export async function retryClassCommentaryRevisionMemory(
  revisionId: number,
  requestId: string,
): Promise<ClassCommentaryMemorySummary> {
  const payload = await apiFetch<Record<string, unknown>>(
    `/api/class-commentary/revisions/${encodeURIComponent(String(revisionId))}/memory-retry`,
    {
      method: 'POST',
      body: JSON.stringify({ request_id: requestId }),
    },
  );
  return normalizeClassCommentaryMemorySummary(recordValue(payload.memory || payload));
}

export async function revokeClassCommentaryMemoryEvidence(
  evidenceId: number,
  requestId: string,
): Promise<ClassCommentaryMemorySummary> {
  const payload = await apiFetch<Record<string, unknown>>(
    `/api/class-commentary/memory-evidence/${encodeURIComponent(String(evidenceId))}/revoke`,
    {
      method: 'POST',
      body: JSON.stringify({ request_id: requestId }),
    },
  );
  return normalizeClassCommentaryMemorySummary(recordValue(payload.memory || payload));
}

function buildClassCommentarySkillPath(skillId: string): string {
  return `/api/class-commentary/skills/${encodeURIComponent(skillId)}`;
}

export async function fetchClassCommentarySkillEvolution(skillId: string): Promise<ClassCommentarySkillEvolution> {
  const payload = await apiFetch<unknown>(`${buildClassCommentarySkillPath(skillId)}/versions`);
  return normalizeClassCommentarySkillEvolution(payload, skillId);
}

export async function createClassCommentarySkillCandidate(
  skillId: string,
  expectedActiveVersionId: number,
  requestId: string,
): Promise<ClassCommentarySkillCandidateBuild> {
  const payload = await apiFetch<unknown>(`${buildClassCommentarySkillPath(skillId)}/candidates`, {
    method: 'POST',
    body: JSON.stringify({
      request_id: requestId,
      expected_active_version_id: expectedActiveVersionId,
    }),
  });
  const payloadRecord = recordValue(payload);
  return normalizeClassCommentarySkillCandidateBuild(recordValue(
    payloadRecord.build || payloadRecord.candidate || payload,
  ));
}

async function changeClassCommentarySkillVersion(
  action: 'activate' | 'rollback',
  skillId: string,
  versionId: number,
  expectedActiveVersionId: number,
  requestId: string,
): Promise<ClassCommentarySkillActivationResult> {
  const payload = await apiFetch<unknown>(
    `${buildClassCommentarySkillPath(skillId)}/versions/${encodeURIComponent(String(versionId))}/${action}`,
    {
      method: 'POST',
      body: JSON.stringify({
        request_id: requestId,
        expected_active_version_id: expectedActiveVersionId,
      }),
    },
  );
  const payloadRecord = recordValue(payload);
  const eventSource = recordValue(payloadRecord.activation_event || payloadRecord.event || payload);
  const activationEvent = normalizeClassCommentarySkillActivationEvent(eventSource);
  const skillSource = recordValue(payloadRecord.skill);
  const versionSource = recordValue(payloadRecord.version);
  const skill = Object.keys(skillSource).length
    ? normalizeClassCommentarySkill(skillSource)
    : null;
  return {
    skill: skill ? {
      ...skill,
      active_version_id: nullableNumberValue(
        skillSource.active_version_id || activationEvent.current_active_version_id,
      ),
    } : null,
    version: Object.keys(versionSource).length
      ? normalizeClassCommentarySkillVersion(versionSource, activationEvent.current_active_version_id || 0)
      : null,
    activation_event: activationEvent,
  };
}

export async function activateClassCommentarySkillVersion(
  skillId: string,
  versionId: number,
  expectedActiveVersionId: number,
  requestId: string,
): Promise<ClassCommentarySkillActivationResult> {
  return changeClassCommentarySkillVersion(
    'activate',
    skillId,
    versionId,
    expectedActiveVersionId,
    requestId,
  );
}

export async function rollbackClassCommentarySkillVersion(
  skillId: string,
  versionId: number,
  expectedActiveVersionId: number,
  requestId: string,
): Promise<ClassCommentarySkillActivationResult> {
  return changeClassCommentarySkillVersion(
    'rollback',
    skillId,
    versionId,
    expectedActiveVersionId,
    requestId,
  );
}
