export interface WrongQuestionAnalysis {
  questionCategory: string;
  topicCategory?: string;
  errorType: string;
  knowledgePoints: string[];
  isRepeatedMistake?: string;
  teacherPriority?: string;
  selectedErrorType?: string;
  selectedKnowledgePoints?: string[];
  selectedActions?: string[];
  selectedReasons?: string[];
  studentNote?: string;
  coreIssue?: string;
  keyOmission?: string;
  nextStep?: string;
}

export interface WrongQuestionReviewDraft {
  selectedErrorType: string;
  selectedKnowledgePoints: string[];
  selectedActions: string[];
  selectedReasons: string[];
  studentNote: string;
  teacherComment: string;
  reviewStatus: string;
  topicCategory?: string;
  isMastered?: boolean;
  questionText?: string;
  needsTeacherConfirmation?: boolean;
  confirmationReasons?: string[];
}

export interface WrongQuestionReviewPayload {
  selectedErrorType: string;
  selectedKnowledgePoints: string[];
  selectedActions: string[];
  selectedReasons: string[];
  studentNote: string;
  teacherComment: string;
  reviewStatus: string;
  topicCategory?: string;
  is_mastered?: boolean;
  question_text?: string;
  needs_teacher_confirmation?: boolean;
  confirmation_reasons_json?: string[];
  confirmation_action?: string;
}

export type WrongQuestionMappingStatus = 'mapped' | 'unmapped' | 'ambiguous' | 'needs_review';

export interface WrongQuestionArchiveContext {
  source: string;
  ingestionRunId: string;
  ingestionRunUrl: string;
  chatSessionId: string;
  chatSessionUrl: string;
}

export interface WrongQuestionGenerationMetadata {
  schemaVersion: string;
  promptVersion: string;
  templateVersion: string;
  ruleVersion: string;
  provider: string;
  modelVersion: string;
  entrypoint: string;
  scope?: string;
  ingestionEntrypoint?: string;
  archiveSource?: string;
}

export interface WrongQuestionRecord {
  id: string;
  roomId: string;
  source: string;
  studentId?: number | null;
  recognitionStatus?: string;
  isGeometry?: boolean;
  questionText?: string;
  questionTextSource?: string;
  studentLibraryPdfPath?: string;
  studentName: string;
  className: string;
  classNameSnapshot: string;
  classId: number | null;
  subject: string;
  teacherName: string;
  teacherNameSnapshot: string;
  teacherUserId: number | null;
  mappingStatus: WrongQuestionMappingStatus;
  createdAt: string;
  imageUrl?: string;
  parentNote: string;
  childReasonText?: string;
  childReasonInputMode?: string;
  reasonCoreIssue?: string;
  reasonKeyOmission?: string;
  reasonNextStep?: string;
  topicCategory?: string;
  isPrimarySchool?: boolean;
  primaryErrorType?: string;
  causeNote?: string;
  isMastered?: boolean;
  teacherComment: string;
  reviewStatus: string;
  analysis: WrongQuestionAnalysis;
  detailUrl?: string;
  ingestionRunId?: string;
  chatSessionId?: string;
  archiveContext?: WrongQuestionArchiveContext;
  needsTeacherConfirmation?: boolean;
  confirmationReasons?: string[];
  confirmationStatus?: string;
  confirmationReviewedBy?: number | null;
  confirmationReviewedAt?: string;
  confirmationReviewerName?: string;
  generationMetadata?: WrongQuestionGenerationMetadata;
  linkedIngestionRun?: WrongQuestionIngestionRun;
  linkedChatSession?: WrongQuestionChatSession;
}

export interface WrongQuestionIngestionAsset {
  id: number;
  ingestionRunId: string;
  assetRole: string;
  storagePath: string;
  fileUrl: string;
  mimeType: string;
  pageNumber: number;
  width: number;
  height: number;
  metadataJson: string;
}

export interface WrongQuestionIngestionRun {
  id: string;
  source: string;
  status: string;
  currentStep: string;
  classId: number | null;
  studentId: number | null;
  teacherUserId: number | null;
  chatSessionId: string;
  originalFilename: string;
  mimeType: string;
  metadataJson: string;
  errorMessage: string;
  createdAt: string;
  detailUrl: string;
  assets: WrongQuestionIngestionAsset[];
  records: WrongQuestionRecord[];
}

export interface WrongQuestionChatMessage {
  id: number;
  sessionId: string;
  role: string;
  stage: string;
  content: string;
  createdAt: string;
}

export interface WrongQuestionChatSession {
  id: string;
  status: string;
  currentStage: string;
  summaryText: string;
  ingestionRunId: string;
  classId: number | null;
  studentId: number | null;
  teacherUserId: number | null;
  detailUrl: string;
  streamUrl: string;
  messages: WrongQuestionChatMessage[];
  records: WrongQuestionRecord[];
}

export interface WrongQuestionFilters {
  studentName?: string;
  className?: string;
  subject?: string;
  teacherName?: string;
  errorType?: string;
  confirmationState?: string;
}

export interface WrongQuestionTopicSummary {
  topicCategory: string;
  count: number;
}

export interface WrongQuestionSummary {
  totalCount: number;
  repeatedMistakeCount: number;
  highPriorityCount: number;
  pendingReviewCount: number;
  uniqueClassCount: number;
  uniqueStudentCount: number;
}

export interface WrongQuestionListApiResponse {
  items?: unknown[];
  summary?: unknown;
  total?: unknown;
}

export interface NormalizedWrongQuestionListResponse {
  items: WrongQuestionRecord[];
  summary: WrongQuestionSummary;
}

export interface MemberStudentNotebookSummary {
  studentName: string;
  classId: number;
  className: string;
  totalCount: number;
  pendingReviewCount: number;
  hasTeacherFollowUp: boolean;
  latestCreatedAt: string;
}

export interface WrongQuestionPracticeSheetSummary {
  id: number;
  studentId: number | null;
  classId: number | null;
  studentNameSnapshot: string;
  classNameSnapshot: string;
  teacherNameSnapshot: string;
  questionCount: number;
  status: string;
  createdAt: string;
  pdfPath?: string;
  pdfUrl?: string;
  downloadUrl?: string;
  generationError?: string;
}

export interface WrongQuestionPracticeSheetListApiResponse {
  items?: unknown[];
  total?: unknown;
}

export type WrongQuestionPracticePackMode = 'topic' | 'reason';
export type WrongQuestionPracticePackVolume = 'light' | 'standard' | 'intensive';

export interface WrongQuestionPracticePackStudent {
  studentId: number;
  studentNameSnapshot: string;
  status: string;
  requestedQuestionCount: number;
  realQuestionCount: number;
  variantQuestionCount: number;
  pdfPath?: string;
  generationError?: string;
}

export interface WrongQuestionPracticePackJob {
  id: number;
  status: string;
  mode: WrongQuestionPracticePackMode;
  target: string;
  volume: WrongQuestionPracticePackVolume;
  requestedQuestionCount: number;
  downloadUrl?: string;
  generationError?: string;
  students: WrongQuestionPracticePackStudent[];
}

export interface WrongQuestionPracticePackListApiResponse {
  items?: unknown[];
}

export type WeeklyWrongQuestionFollowupMessage = {
  id: number;
  messageText: string;
  sourceRecordIds: string[];
  sourceSheetId?: number | null;
};

export type WeeklyWrongQuestionFollowupItem = {
  studentId: number;
  studentName: string;
  status: string;
  practiceSheet: WrongQuestionPracticeSheetSummary | null;
  weeklyQuestionCount: number;
  totalActiveQuestionCount: number;
  candidateQuestionCount: number;
  candidateRecordIds: string[];
  recommendedCategory: string;
  recommendationReason: string;
  topicCategories: string[];
  representativeReasonSummaries: string[];
  sourceRecordIds: string[];
  sourceRecords: WrongQuestionRecord[];
  repeatedCategory: string;
  repeatedCategoryCount: number;
  studentLibraryPdfUrl: string;
  message: WeeklyWrongQuestionFollowupMessage | null;
};

export type WeeklyWrongQuestionFollowupResponse = {
  classId: number;
  className: string;
  weekStartDate: string;
  weekEndDate: string;
  total: number;
  items: WeeklyWrongQuestionFollowupItem[];
};

export interface WeeklyWrongQuestionActivityClassItem {
  organizationId: number;
  organizationName: string;
  classId: number;
  className: string;
  weeklyQuestionCount: number;
  uploadingStudentCount: number;
  latestCreatedAt: string;
}

export interface WeeklyWrongQuestionActivityTeacherItem {
  organizationId: number;
  organizationName: string;
  teacherUserId: number;
  teacherName: string;
  classCount: number;
  weeklyQuestionCount: number;
  involvedStudentCount: number;
  pendingFollowupCount: number;
}

export interface WeeklyWrongQuestionActivityStudentItem {
  organizationId: number;
  organizationName: string;
  classId: number;
  className: string;
  studentId: number;
  studentName: string;
  weeklyQuestionCount: number;
  totalQuestionCount: number;
  topicCategories: string[];
  latestCreatedAt: string;
}

export interface WeeklyWrongQuestionActivitySummary {
  weekStart: string;
  weekEnd: string;
  classItems: WeeklyWrongQuestionActivityClassItem[];
  teacherItems: WeeklyWrongQuestionActivityTeacherItem[];
  studentItems: WeeklyWrongQuestionActivityStudentItem[];
}

export function isWechatMiniProgramWrongQuestionRecord(record: WrongQuestionRecord): boolean {
  return record.source === 'wechat_mp';
}

export function isPrimarySchoolWrongQuestionRecord(record: WrongQuestionRecord): boolean {
  return isWechatMiniProgramWrongQuestionRecord(record) && record.isPrimarySchool === true;
}

export function isDownstreamWrongQuestionRecord(record: WrongQuestionRecord): boolean {
  return !isWechatMiniProgramWrongQuestionRecord(record);
}

export function getWrongQuestionSemanticModel(record: WrongQuestionRecord): 'wechat_mastery' | 'downstream_review' {
  return isWechatMiniProgramWrongQuestionRecord(record) ? 'wechat_mastery' : 'downstream_review';
}

export function getWrongQuestionSourceLabel(source: string): string {
  return source === 'wechat_mp' ? '微信小程序' : '智能错题服务';
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasOwnKey(source: Record<string, unknown>, keys: string[]): boolean {
  return keys.some((key) => Object.prototype.hasOwnProperty.call(source, key));
}

function pickStringValue(source: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = source[key];
    if (typeof value === 'string') {
      return value.trim();
    }
  }

  return '';
}

function pickNumberValue(source: Record<string, unknown>, keys: string[]): number | null {
  for (const key of keys) {
    const value = source[key];
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === 'string') {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }

  return null;
}

function pickBooleanValue(source: Record<string, unknown>, keys: string[]): boolean | null {
  for (const key of keys) {
    const value = source[key];
    if (typeof value === 'boolean') {
      return value;
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value !== 0;
    }
    if (typeof value === 'string') {
      const normalized = value.trim().toLowerCase();
      if (['1', 'true', 'yes', 'on'].includes(normalized)) {
        return true;
      }
      if (['0', 'false', 'no', 'off'].includes(normalized)) {
        return false;
      }
    }
  }

  return null;
}

function pickStringArrayValue(source: Record<string, unknown>, keys: string[]): string[] {
  for (const key of keys) {
    const value = source[key];
    if (!Array.isArray(value)) {
      continue;
    }

    return value
      .filter((item): item is string => typeof item === 'string')
      .map((item) => item.trim())
      .filter(Boolean);
  }

  return [];
}

function normalizeStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item ?? '').trim()).filter(Boolean) : [];
}

function normalizePossiblyJsonStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return normalizeStringList(value);
  }
  if (typeof value !== 'string') {
    return [];
  }
  try {
    return normalizeStringList(JSON.parse(value));
  } catch {
    return [];
  }
}

function normalizeWrongQuestionGenerationMetadata(rawMetadata: unknown): WrongQuestionGenerationMetadata | undefined {
  let source = rawMetadata;
  if (typeof rawMetadata === 'string') {
    try {
      source = JSON.parse(rawMetadata);
    } catch {
      source = null;
    }
  }
  if (!isObjectRecord(source)) {
    return undefined;
  }

  const metadata: WrongQuestionGenerationMetadata = {
    schemaVersion: pickStringValue(source, ['schemaVersion', 'schema_version']),
    promptVersion: pickStringValue(source, ['promptVersion', 'prompt_version']),
    templateVersion: pickStringValue(source, ['templateVersion', 'template_version']),
    ruleVersion: pickStringValue(source, ['ruleVersion', 'rule_version']),
    provider: pickStringValue(source, ['provider']),
    modelVersion: pickStringValue(source, ['modelVersion', 'model_version']),
    entrypoint: pickStringValue(source, ['entrypoint']),
  };

  const scope = pickStringValue(source, ['scope']);
  if (scope) {
    metadata.scope = scope;
  }

  const ingestionEntrypoint = pickStringValue(source, ['ingestionEntrypoint', 'ingestion_entrypoint']);
  if (ingestionEntrypoint) {
    metadata.ingestionEntrypoint = ingestionEntrypoint;
  }

  const archiveSource = pickStringValue(source, ['archiveSource', 'archive_source']);
  if (archiveSource) {
    metadata.archiveSource = archiveSource;
  }

  const hasValue = Object.values(metadata).some((value) => typeof value === 'string' ? value.trim() : Boolean(value));
  return hasValue ? metadata : undefined;
}

function normalizeWrongQuestionTopicCategory(value = ''): string {
  const normalized = value.trim();
  return normalized || '未分类';
}

const PRIMARY_GRADE_PATTERN = /(?:小学|小[一二三四五六123456]|[一二三四五六123456]年级)/;
const SECONDARY_GRADE_PATTERN = /(?:初中|高中|初[一二三123]|高[一二三123]|[七八九789]年级|十[一二]?年级|1[0-2]年级)/;

function isSecondarySchoolClassLabel(className: string, classNameSnapshot: string): boolean {
  return SECONDARY_GRADE_PATTERN.test(`${className} ${classNameSnapshot}`);
}

function inferPrimarySchoolClassLabel(className: string, classNameSnapshot: string): boolean {
  const text = `${className} ${classNameSnapshot}`;
  if (SECONDARY_GRADE_PATTERN.test(text)) {
    return false;
  }
  return PRIMARY_GRADE_PATTERN.test(text);
}

function normalizeWrongQuestionPrimarySchoolFlag(
  source: Record<string, unknown>,
  className: string,
  classNameSnapshot: string,
): boolean {
  const explicitValue = pickBooleanValue(source, ['isPrimarySchool', 'is_primary_school']);
  if (explicitValue !== null) {
    return explicitValue && !isSecondarySchoolClassLabel(className, classNameSnapshot);
  }
  return inferPrimarySchoolClassLabel(className, classNameSnapshot);
}

function normalizeWrongQuestionMappingStatus(value: string, fallback: WrongQuestionMappingStatus = 'mapped'): WrongQuestionMappingStatus {
  if (value === 'mapped' || value === 'unmapped' || value === 'ambiguous' || value === 'needs_review') {
    return value;
  }

  return fallback;
}

function pickWrongQuestionMappingStatusValue(
  source: Record<string, unknown>,
  keys: string[],
  fallback: WrongQuestionMappingStatus = 'mapped',
): WrongQuestionMappingStatus {
  for (const key of keys) {
    const value = source[key];
    if (typeof value === 'string') {
      return normalizeWrongQuestionMappingStatus(value.trim(), fallback);
    }
  }

  return fallback;
}

function normalizeWrongQuestionAnalysis(rawAnalysis: unknown): WrongQuestionAnalysis {
  const source = isObjectRecord(rawAnalysis) ? rawAnalysis : {};
  const selectedKnowledgePoints = pickStringArrayValue(source, ['selectedKnowledgePoints', 'selected_knowledge_points']);
  const selectedActions = pickStringArrayValue(source, ['selectedActions', 'selected_actions']);
  const selectedReasons = pickStringArrayValue(source, ['selectedReasons', 'selected_reasons']);
  const selectedErrorType = pickStringValue(source, ['selectedErrorType', 'selected_error_type']);
  const topicCategory = pickStringValue(source, ['topicCategory', 'topic_category']);
  const studentNote = pickStringValue(source, ['studentNote', 'student_note']);
  const coreIssue = pickStringValue(source, ['coreIssue', 'core_issue']);
  const keyOmission = pickStringValue(source, ['keyOmission', 'key_omission']);
  const nextStep = pickStringValue(source, ['nextStep', 'next_step']);

  const analysis: WrongQuestionAnalysis = {
    questionCategory: pickStringValue(source, ['questionCategory', 'question_category']),
    errorType: pickStringValue(source, ['errorType', 'error_type']),
    knowledgePoints: pickStringArrayValue(source, ['knowledgePoints', 'knowledge_points']),
  };

  if (topicCategory) {
    analysis.topicCategory = normalizeWrongQuestionTopicCategory(topicCategory);
  }

  const isRepeatedMistake = pickStringValue(source, ['isRepeatedMistake', 'is_repeated_mistake']);
  const teacherPriority = pickStringValue(source, ['teacherPriority', 'teacher_priority']);

  if (isRepeatedMistake) {
    analysis.isRepeatedMistake = isRepeatedMistake;
  }

  if (teacherPriority) {
    analysis.teacherPriority = teacherPriority;
  }

  if (selectedErrorType) {
    analysis.selectedErrorType = selectedErrorType;
  }

  if (selectedKnowledgePoints.length > 0) {
    analysis.selectedKnowledgePoints = selectedKnowledgePoints;
  }

  if (selectedActions.length > 0) {
    analysis.selectedActions = selectedActions;
  }

  if (selectedReasons.length > 0) {
    analysis.selectedReasons = selectedReasons;
  }

  if (studentNote) {
    analysis.studentNote = studentNote;
  }

  if (coreIssue) {
    analysis.coreIssue = coreIssue;
  }

  if (keyOmission) {
    analysis.keyOmission = keyOmission;
  }

  if (nextStep) {
    analysis.nextStep = nextStep;
  }

  return analysis;
}

export function normalizeWrongQuestionRecord(rawRecord: unknown, fallbackIndex = 0): WrongQuestionRecord {
  const source = isObjectRecord(rawRecord) ? rawRecord : {};
  const rawId = source.id;
  const className = pickStringValue(source, ['classDisplayName', 'class_display_name', 'className', 'class_name']);
  const classNameSnapshot = pickStringValue(source, ['classNameSnapshot', 'class_name_snapshot', 'className', 'class_name']) || className;
  const teacherName = pickStringValue(source, ['teacherDisplayName', 'teacher_display_name', 'teacherName', 'teacher_name']);
  const teacherNameSnapshot = pickStringValue(source, ['teacherNameSnapshot', 'teacher_name_snapshot', 'teacherName', 'teacher_name']) || teacherName;
  const normalizedSource = pickStringValue(source, ['source']) || 'downstream';
  const normalizedReviewStatus = pickStringValue(source, ['status']) || (normalizedSource === 'wechat_mp' ? 'pending' : '');
  const recognitionStatus = pickStringValue(source, ['recognitionStatus', 'recognition_status']);
  const questionText = pickStringValue(source, ['questionText', 'question_text']);
  const questionTextSource = pickStringValue(source, ['questionTextSource', 'question_text_source']);
  const studentLibraryPdfPath = pickStringValue(source, ['studentLibraryPdfPath', 'student_library_pdf_path']);
  const childReasonText = pickStringValue(source, ['childReasonText', 'child_reason_text', 'childRawReasonText', 'child_raw_reason_text']);
  const childReasonInputMode = pickStringValue(source, ['childReasonInputMode', 'child_reason_input_mode']);
  const reasonCoreIssue = pickStringValue(source, ['reasonCoreIssue', 'reason_core_issue', 'childReasonCoreIssue', 'child_reason_core_issue']);
  const reasonKeyOmission = pickStringValue(source, ['reasonKeyOmission', 'reason_key_omission', 'childReasonKeyOmission', 'child_reason_key_omission']);
  const reasonNextStep = pickStringValue(source, ['reasonNextStep', 'reason_next_step', 'childReasonNextStep', 'child_reason_next_step']);
  const topicCategory = pickStringValue(source, ['topicCategory', 'topic_category'])
    || normalizeWrongQuestionAnalysis(source.analysis).topicCategory
    || '';
  const primaryErrorType = pickStringValue(source, ['primaryErrorType', 'primary_error_type']);
  const causeNote = pickStringValue(source, ['causeNote', 'cause_note', 'secondaryErrorSummary', 'secondary_error_summary']);
  const archiveStatus = pickStringValue(source, ['archiveStatus', 'archive_status']);
  const rawIsGeometry = source.isGeometry ?? source.is_geometry;
  const isGeometry = typeof rawIsGeometry === 'boolean'
    ? rawIsGeometry
    : typeof rawIsGeometry === 'number'
      ? rawIsGeometry !== 0
      : typeof rawIsGeometry === 'string'
        ? ['1', 'true', 'yes'].includes(rawIsGeometry.trim().toLowerCase())
        : undefined;

  const record: WrongQuestionRecord = {
    id: typeof rawId === 'string' || typeof rawId === 'number' ? String(rawId) : `wrong-question-${fallbackIndex}`,
    roomId: pickStringValue(source, ['roomId', 'room_id']),
    source: normalizedSource,
    studentName: pickStringValue(source, ['studentName', 'student_name', 'studentNickname', 'student_nickname']),
    className,
    classNameSnapshot,
    classId: pickNumberValue(source, ['classId', 'class_id']),
    subject: pickStringValue(source, ['subject']),
    teacherName,
    teacherNameSnapshot,
    teacherUserId: pickNumberValue(source, ['teacherUserId', 'teacher_user_id']),
    mappingStatus: pickWrongQuestionMappingStatusValue(source, ['mappingStatus', 'mapping_status']),
    createdAt: pickStringValue(source, ['createdAt', 'created_at']),
    imageUrl: pickStringValue(source, ['imageUrl', 'image_url']),
    parentNote: pickStringValue(source, ['parentNote', 'parent_note']),
    teacherComment: pickStringValue(source, ['teacherComment', 'teacher_comment']),
    reviewStatus: normalizedReviewStatus,
    analysis: normalizeWrongQuestionAnalysis(source.analysis),
  };

  const studentId = pickNumberValue(source, ['studentId', 'student_id']);
  if (studentId !== null) {
    record.studentId = studentId;
  }

  if (recognitionStatus) {
    record.recognitionStatus = recognitionStatus;
  }

  if (normalizedSource === 'wechat_mp') {
    record.isPrimarySchool = normalizeWrongQuestionPrimarySchoolFlag(source, className, classNameSnapshot);

    if (childReasonText) {
      record.childReasonText = childReasonText;
    }

    if (childReasonInputMode) {
      record.childReasonInputMode = childReasonInputMode;
    }

    if (reasonCoreIssue) {
      record.reasonCoreIssue = reasonCoreIssue;
    } else if (record.analysis.coreIssue?.trim()) {
      record.reasonCoreIssue = record.analysis.coreIssue.trim();
    }

    if (reasonKeyOmission) {
      record.reasonKeyOmission = reasonKeyOmission;
    } else if (record.analysis.keyOmission?.trim()) {
      record.reasonKeyOmission = record.analysis.keyOmission.trim();
    }

    if (reasonNextStep) {
      record.reasonNextStep = reasonNextStep;
    } else if (record.analysis.nextStep?.trim()) {
      record.reasonNextStep = record.analysis.nextStep.trim();
    }

    record.topicCategory = normalizeWrongQuestionTopicCategory(topicCategory);

    if (primaryErrorType) {
      record.primaryErrorType = primaryErrorType;
    } else if (record.analysis.errorType.trim()) {
      record.primaryErrorType = record.analysis.errorType.trim();
    }

    if (causeNote) {
      record.causeNote = causeNote;
    } else if (record.analysis.studentNote?.trim()) {
      record.causeNote = record.analysis.studentNote.trim();
    }

    if (archiveStatus) {
      record.isMastered = archiveStatus === 'archived';
    }

    if (typeof source.is_mastered === 'boolean') {
      record.isMastered = source.is_mastered;
    }
  }

  if (typeof isGeometry === 'boolean') {
    record.isGeometry = isGeometry;
  }

  if (questionText) {
    record.questionText = questionText;
  }

  if (questionTextSource) {
    record.questionTextSource = questionTextSource;
  }

  if (studentLibraryPdfPath) {
    record.studentLibraryPdfPath = studentLibraryPdfPath;
  }

  const detailUrl = pickStringValue(source, ['detailUrl', 'detail_url']);
  if (detailUrl) {
    record.detailUrl = detailUrl;
  }

  const ingestionRunId = pickStringValue(source, ['ingestionRunId', 'ingestion_run_id']);
  if (ingestionRunId) {
    record.ingestionRunId = ingestionRunId;
  }

  const chatSessionId = pickStringValue(source, ['chatSessionId', 'chat_session_id']);
  if (chatSessionId) {
    record.chatSessionId = chatSessionId;
  }

  const needsTeacherConfirmation = pickBooleanValue(source, ['needsTeacherConfirmation', 'needs_teacher_confirmation']);
  if (needsTeacherConfirmation !== null) {
    record.needsTeacherConfirmation = needsTeacherConfirmation;
  }

  const confirmationReasons = normalizePossiblyJsonStringList(source.confirmation_reasons_json ?? source.confirmationReasonsJson);
  if (confirmationReasons.length > 0) {
    record.confirmationReasons = confirmationReasons;
  }

  const confirmationStatus = pickStringValue(source, ['confirmationStatus', 'confirmation_status']);
  if (confirmationStatus) {
    record.confirmationStatus = confirmationStatus;
  }

  const confirmationReviewedBy = pickNumberValue(source, ['confirmationReviewedBy', 'confirmation_reviewed_by']);
  if (confirmationReviewedBy !== null) {
    record.confirmationReviewedBy = confirmationReviewedBy;
  }

  const confirmationReviewedAt = pickStringValue(source, ['confirmationReviewedAt', 'confirmation_reviewed_at']);
  if (confirmationReviewedAt) {
    record.confirmationReviewedAt = confirmationReviewedAt;
  }

  const confirmationReviewerName = pickStringValue(source, ['confirmationReviewerName', 'confirmation_reviewer_name']);
  if (confirmationReviewerName) {
    record.confirmationReviewerName = confirmationReviewerName;
  }

  const generationMetadata = normalizeWrongQuestionGenerationMetadata(
    source.generation_metadata ?? source.generationMetadata ?? source.generation_metadata_json,
  );
  if (generationMetadata) {
    record.generationMetadata = generationMetadata;
  }

  const archiveContextCandidate = isObjectRecord(source.archive_context)
    ? source.archive_context
    : isObjectRecord(source.archiveContext)
      ? source.archiveContext
      : null;
  if (archiveContextCandidate) {
    record.archiveContext = {
      source: pickStringValue(archiveContextCandidate, ['source']),
      ingestionRunId: pickStringValue(archiveContextCandidate, ['ingestionRunId', 'ingestion_run_id']),
      ingestionRunUrl: pickStringValue(archiveContextCandidate, ['ingestionRunUrl', 'ingestion_run_url']),
      chatSessionId: pickStringValue(archiveContextCandidate, ['chatSessionId', 'chat_session_id']),
      chatSessionUrl: pickStringValue(archiveContextCandidate, ['chatSessionUrl', 'chat_session_url']),
    };
  }

  const linkedIngestionRunCandidate = isObjectRecord(source.linked_ingestion_run)
    ? source.linked_ingestion_run
    : isObjectRecord(source.linkedIngestionRun)
      ? source.linkedIngestionRun
      : null;
  if (linkedIngestionRunCandidate) {
    record.linkedIngestionRun = normalizeWrongQuestionIngestionRun(linkedIngestionRunCandidate);
  }

  const linkedChatSessionCandidate = isObjectRecord(source.linked_chat_session)
    ? source.linked_chat_session
    : isObjectRecord(source.linkedChatSession)
      ? source.linkedChatSession
      : null;
  if (linkedChatSessionCandidate) {
    record.linkedChatSession = normalizeWrongQuestionChatSession(linkedChatSessionCandidate);
  }

  return record;
}

function normalizeDraftList(values: string[]): string[] {
  return values
    .map((value) => value.trim())
    .filter(Boolean);
}

export function buildWrongQuestionReviewDraft(record: WrongQuestionRecord): WrongQuestionReviewDraft {
  const draft: WrongQuestionReviewDraft = {
    selectedErrorType: record.analysis.selectedErrorType?.trim()
      || (isWechatMiniProgramWrongQuestionRecord(record)
        ? record.primaryErrorType?.trim() || record.analysis.errorType?.trim()
        : '')
      || '',
    selectedKnowledgePoints: normalizeDraftList(record.analysis.selectedKnowledgePoints ?? []),
    selectedActions: normalizeDraftList(record.analysis.selectedActions ?? []),
    selectedReasons: normalizeDraftList(record.analysis.selectedReasons ?? []),
    studentNote: record.analysis.studentNote?.trim() ?? '',
    teacherComment: record.teacherComment.trim(),
    reviewStatus: record.reviewStatus.trim() || (isWechatMiniProgramWrongQuestionRecord(record) ? 'pending' : ''),
  };

  if (isWechatMiniProgramWrongQuestionRecord(record) || record.source === 'ai_chat') {
    draft.isMastered = Boolean(record.isMastered);
  }
  if (isWechatMiniProgramWrongQuestionRecord(record)) {
    if (isPrimarySchoolWrongQuestionRecord(record)) {
      draft.topicCategory = normalizeWrongQuestionTopicCategory(record.topicCategory ?? record.analysis.topicCategory ?? '');
    }
  }

  if ((isWechatMiniProgramWrongQuestionRecord(record) && !record.isGeometry) || record.source === 'ai_chat') {
    draft.questionText = record.questionText?.trim() ?? '';
  }

  if (record.source === 'ai_chat') {
    draft.needsTeacherConfirmation = Boolean(record.needsTeacherConfirmation);
    draft.confirmationReasons = normalizeDraftList(record.confirmationReasons ?? []);
  }

  return draft;
}

export function buildWrongQuestionReviewPayload(draft: WrongQuestionReviewDraft): WrongQuestionReviewPayload {
  const payload: WrongQuestionReviewPayload = {
    selectedErrorType: draft.selectedErrorType.trim(),
    selectedKnowledgePoints: normalizeDraftList(draft.selectedKnowledgePoints),
    selectedActions: normalizeDraftList(draft.selectedActions),
    selectedReasons: normalizeDraftList(draft.selectedReasons),
    studentNote: draft.studentNote.trim(),
    teacherComment: draft.teacherComment.trim(),
    reviewStatus: draft.reviewStatus.trim(),
  };

  if (typeof draft.topicCategory === 'string') {
    payload.topicCategory = normalizeWrongQuestionTopicCategory(draft.topicCategory);
  }

  if (typeof draft.isMastered === 'boolean') {
    payload.is_mastered = draft.isMastered;
  }

  if (typeof draft.questionText === 'string') {
    payload.question_text = draft.questionText.trim();
  }

  if (typeof draft.needsTeacherConfirmation === 'boolean') {
    payload.needs_teacher_confirmation = draft.needsTeacherConfirmation;
    payload.confirmation_reasons_json = draft.needsTeacherConfirmation
      ? normalizeDraftList(draft.confirmationReasons ?? [])
      : [];
  }

  return payload;
}

export function hydrateWrongQuestionReviewDraftFromDetail(
  detailRecord: WrongQuestionRecord,
  currentDraft?: WrongQuestionReviewDraft,
  hasLocalEdits = false,
): WrongQuestionReviewDraft {
  if (currentDraft && hasLocalEdits) {
    return currentDraft;
  }

  return buildWrongQuestionReviewDraft(detailRecord);
}

export function applyWrongQuestionReviewDraft(record: WrongQuestionRecord, draft: WrongQuestionReviewDraft): WrongQuestionRecord {
  const payload = buildWrongQuestionReviewPayload(draft);
  const nextAnalysis: WrongQuestionAnalysis = {
    ...record.analysis,
  };

  if (payload.selectedErrorType) {
    nextAnalysis.selectedErrorType = payload.selectedErrorType;
  } else {
    delete nextAnalysis.selectedErrorType;
  }

  if (payload.selectedKnowledgePoints.length > 0) {
    nextAnalysis.selectedKnowledgePoints = payload.selectedKnowledgePoints;
  } else {
    delete nextAnalysis.selectedKnowledgePoints;
  }

  if (payload.selectedActions.length > 0) {
    nextAnalysis.selectedActions = payload.selectedActions;
  } else {
    delete nextAnalysis.selectedActions;
  }

  if (payload.selectedReasons.length > 0) {
    nextAnalysis.selectedReasons = payload.selectedReasons;
  } else {
    delete nextAnalysis.selectedReasons;
  }

  if (payload.studentNote) {
    nextAnalysis.studentNote = payload.studentNote;
  } else {
    delete nextAnalysis.studentNote;
  }

  if (payload.topicCategory) {
    nextAnalysis.topicCategory = payload.topicCategory;
  }

  const nextRecord: WrongQuestionRecord = {
    ...record,
    teacherComment: payload.teacherComment,
    reviewStatus: payload.reviewStatus || record.reviewStatus,
    isMastered: typeof payload.is_mastered === 'boolean' ? payload.is_mastered : record.isMastered,
    questionText: typeof payload.question_text === 'string' ? payload.question_text : record.questionText,
    needsTeacherConfirmation: typeof payload.needs_teacher_confirmation === 'boolean'
      ? payload.needs_teacher_confirmation
      : record.needsTeacherConfirmation,
    confirmationReasons: Array.isArray(payload.confirmation_reasons_json)
      ? payload.confirmation_reasons_json
      : record.confirmationReasons,
    analysis: nextAnalysis,
  };
  if (payload.topicCategory) {
    nextRecord.topicCategory = payload.topicCategory;
  }
  return nextRecord;
}

export function resolveSavedWrongQuestionRecord(
  currentRecord: WrongQuestionRecord,
  draft: WrongQuestionReviewDraft,
  responseRecord?: unknown,
): WrongQuestionRecord {
  if (responseRecord) {
    const normalizedResponse = normalizeWrongQuestionRecord(responseRecord);
    const responseSource = isObjectRecord(responseRecord) ? responseRecord : {};
    const hasCanonicalTeacherName = hasOwnKey(responseSource, ['teacherDisplayName', 'teacher_display_name']);
    const hasTeacherSnapshot = hasOwnKey(responseSource, ['teacherNameSnapshot', 'teacher_name_snapshot']);
    const hasTeacherUserId = hasOwnKey(responseSource, ['teacherUserId', 'teacher_user_id']);
    const hasCanonicalClassName = hasOwnKey(responseSource, ['classDisplayName', 'class_display_name']);
    const hasClassSnapshot = hasOwnKey(responseSource, ['classNameSnapshot', 'class_name_snapshot']);
    const hasClassId = hasOwnKey(responseSource, ['classId', 'class_id']);
    const hasMappingStatus = hasOwnKey(responseSource, ['mappingStatus', 'mapping_status']);
    const hasSource = hasOwnKey(responseSource, ['source']);
    const hasParentNote = hasOwnKey(responseSource, ['parentNote', 'parent_note']);
    const hasTeacherComment = hasOwnKey(responseSource, ['teacherComment', 'teacher_comment']);
    const hasReviewStatus = hasOwnKey(responseSource, ['status']);
    const hasMastered = hasOwnKey(responseSource, ['is_mastered', 'archive_status', 'archiveStatus']);
    const hasTopicCategory = hasOwnKey(responseSource, ['topicCategory', 'topic_category']);
    const hasNeedsTeacherConfirmation = hasOwnKey(responseSource, ['needsTeacherConfirmation', 'needs_teacher_confirmation']);
    const hasConfirmationReasons = hasOwnKey(responseSource, ['confirmationReasons', 'confirmation_reasons_json', 'confirmationReasonsJson']);
    const hasConfirmationStatus = hasOwnKey(responseSource, ['confirmationStatus', 'confirmation_status']);
    const hasConfirmationReviewedBy = hasOwnKey(responseSource, ['confirmationReviewedBy', 'confirmation_reviewed_by']);
    const hasConfirmationReviewedAt = hasOwnKey(responseSource, ['confirmationReviewedAt', 'confirmation_reviewed_at']);
    const hasConfirmationReviewerName = hasOwnKey(responseSource, ['confirmationReviewerName', 'confirmation_reviewer_name']);
    const hasGenerationMetadata = hasOwnKey(responseSource, ['generationMetadata', 'generation_metadata', 'generation_metadata_json']);

    return {
      ...normalizedResponse,
      source: hasSource ? normalizedResponse.source : currentRecord.source,
      teacherName: hasCanonicalTeacherName
        ? normalizedResponse.teacherName || currentRecord.teacherName
        : currentRecord.teacherName || normalizedResponse.teacherName,
      teacherNameSnapshot: hasTeacherSnapshot
        ? normalizedResponse.teacherNameSnapshot || currentRecord.teacherNameSnapshot
        : currentRecord.teacherNameSnapshot || normalizedResponse.teacherNameSnapshot,
      teacherUserId: hasTeacherUserId ? normalizedResponse.teacherUserId : currentRecord.teacherUserId,
      className: hasCanonicalClassName
        ? normalizedResponse.className || currentRecord.className
        : currentRecord.className || normalizedResponse.className,
      classNameSnapshot: hasClassSnapshot
        ? normalizedResponse.classNameSnapshot || currentRecord.classNameSnapshot
        : currentRecord.classNameSnapshot || normalizedResponse.classNameSnapshot,
      classId: hasClassId ? normalizedResponse.classId : currentRecord.classId,
      mappingStatus: hasMappingStatus ? normalizedResponse.mappingStatus : currentRecord.mappingStatus,
      parentNote: hasParentNote ? normalizedResponse.parentNote : currentRecord.parentNote,
      teacherComment: hasTeacherComment ? normalizedResponse.teacherComment : currentRecord.teacherComment,
      reviewStatus: hasReviewStatus ? normalizedResponse.reviewStatus : currentRecord.reviewStatus,
      isMastered: hasMastered ? normalizedResponse.isMastered : currentRecord.isMastered,
      topicCategory: hasTopicCategory ? normalizedResponse.topicCategory : currentRecord.topicCategory,
      needsTeacherConfirmation: hasNeedsTeacherConfirmation
        ? normalizedResponse.needsTeacherConfirmation
        : currentRecord.needsTeacherConfirmation,
      confirmationReasons: hasConfirmationReasons
        ? normalizedResponse.confirmationReasons
        : currentRecord.confirmationReasons,
      confirmationStatus: hasConfirmationStatus
        ? normalizedResponse.confirmationStatus
        : currentRecord.confirmationStatus,
      confirmationReviewedBy: hasConfirmationReviewedBy
        ? normalizedResponse.confirmationReviewedBy
        : currentRecord.confirmationReviewedBy,
      confirmationReviewedAt: hasConfirmationReviewedAt
        ? normalizedResponse.confirmationReviewedAt
        : currentRecord.confirmationReviewedAt,
      confirmationReviewerName: hasConfirmationReviewerName
        ? normalizedResponse.confirmationReviewerName
        : currentRecord.confirmationReviewerName,
      generationMetadata: hasGenerationMetadata
        ? normalizedResponse.generationMetadata
        : currentRecord.generationMetadata,
    };
  }

  return applyWrongQuestionReviewDraft(currentRecord, draft);
}

function normalizeWrongQuestionSummary(rawSummary: unknown, fallback: WrongQuestionSummary, totalOverride: unknown): WrongQuestionSummary {
  const source = isObjectRecord(rawSummary) ? rawSummary : {};
  const normalizedTotalOverride = typeof totalOverride === 'number' && Number.isFinite(totalOverride)
    ? totalOverride
    : typeof totalOverride === 'string'
      ? Number(totalOverride)
      : null;

  return {
    totalCount: (normalizedTotalOverride !== null && Number.isFinite(normalizedTotalOverride)
      ? normalizedTotalOverride
      : pickNumberValue(source, ['totalCount', 'total_count'])) ?? fallback.totalCount,
    repeatedMistakeCount: pickNumberValue(source, ['repeatedMistakeCount', 'repeated_mistake_count']) ?? fallback.repeatedMistakeCount,
    highPriorityCount: pickNumberValue(source, ['highPriorityCount', 'high_priority_count']) ?? fallback.highPriorityCount,
    pendingReviewCount: pickNumberValue(source, ['pendingReviewCount', 'pending_review_count']) ?? fallback.pendingReviewCount,
    uniqueClassCount: pickNumberValue(source, ['uniqueClassCount', 'unique_class_count']) ?? fallback.uniqueClassCount,
    uniqueStudentCount: pickNumberValue(source, ['uniqueStudentCount', 'unique_student_count']) ?? fallback.uniqueStudentCount,
  };
}

export function normalizeWrongQuestionListResponse(payload: WrongQuestionListApiResponse | WrongQuestionRecord[]): NormalizedWrongQuestionListResponse {
  const source = Array.isArray(payload) ? { items: payload } : payload;
  const rawItems = Array.isArray(source.items) ? source.items : [];
  const items = rawItems.map((item, index) => normalizeWrongQuestionRecord(item, index));
  const fallbackSummary = summarizeWrongQuestionRecords(items);
  const hasWechatMiniProgramItems = items.some((item) => isWechatMiniProgramWrongQuestionRecord(item));

  return {
    items,
    summary: hasWechatMiniProgramItems
      ? fallbackSummary
      : normalizeWrongQuestionSummary(source.summary, fallbackSummary, source.total),
  };
}

function hasTeacherReview(record: WrongQuestionRecord): boolean {
  if (isWechatMiniProgramWrongQuestionRecord(record)) {
    return Boolean(record.isMastered);
  }

  return Boolean(record.analysis.selectedErrorType?.trim());
}

function isRepeatedMistake(value?: string): boolean {
  const normalized = value?.trim();
  return Boolean(normalized && normalized !== '否');
}

export function summarizeWrongQuestionRecords(records: WrongQuestionRecord[]): WrongQuestionSummary {
  const classes = new Set<string>();
  const students = new Set<string>();

  const base = records.reduce<Omit<WrongQuestionSummary, 'uniqueClassCount' | 'uniqueStudentCount'>>((summary, record) => {
    const nextSummary = {
      ...summary,
      totalCount: summary.totalCount + 1,
    };

    if (isRepeatedMistake(record.analysis.isRepeatedMistake)) {
      nextSummary.repeatedMistakeCount += 1;
    }

    if (record.analysis.teacherPriority?.trim() === '高') {
      nextSummary.highPriorityCount += 1;
    }

    if (!hasTeacherReview(record)) {
      nextSummary.pendingReviewCount += 1;
    }

    if (record.className.trim()) classes.add(record.className.trim());
    if (record.studentName.trim()) students.add(record.studentName.trim());

    return nextSummary;
  }, {
    totalCount: 0,
    repeatedMistakeCount: 0,
    highPriorityCount: 0,
    pendingReviewCount: 0,
  });

  return { ...base, uniqueClassCount: classes.size, uniqueStudentCount: students.size };
}

export function filterWrongQuestionRecordsForMemberNotebook(
  records: WrongQuestionRecord[],
  classId: number | null,
  studentName: string | null,
): WrongQuestionRecord[] {
  return records
    .filter((item) => classId === null || item.classId === classId)
    .filter((item) => !studentName || item.studentName === studentName)
    .sort((left, right) => left.createdAt.localeCompare(right.createdAt));
}

export function filterWrongQuestionRecordsByTopic(
  records: WrongQuestionRecord[],
  topicCategory: string,
): WrongQuestionRecord[] {
  const normalizedTopic = normalizeWrongQuestionTopicCategory(topicCategory);
  if (!normalizedTopic || normalizedTopic === '全部') {
    return records;
  }
  return records.filter((record) => normalizeWrongQuestionTopicCategory(record.topicCategory ?? '') === normalizedTopic);
}

export function buildWrongQuestionTopicSummaries(records: WrongQuestionRecord[]): WrongQuestionTopicSummary[] {
  const counts = new Map<string, number>();
  for (const record of records) {
    const topicCategory = normalizeWrongQuestionTopicCategory(record.topicCategory ?? '');
    counts.set(topicCategory, (counts.get(topicCategory) ?? 0) + 1);
  }

  const topicItems = Array.from(counts.entries())
    .sort(([left], [right]) => {
      if (left === '未分类') {
        return -1;
      }
      if (right === '未分类') {
        return 1;
      }
      return left.localeCompare(right, 'zh-Hans-CN');
    })
    .map(([topicCategory, count]) => ({ topicCategory, count }));

  return [{ topicCategory: '全部', count: records.length }, ...topicItems];
}

export function buildMemberStudentNotebookSummaries(
  records: WrongQuestionRecord[],
  classId: number | null,
): MemberStudentNotebookSummary[] {
  const buckets = new Map<string, MemberStudentNotebookSummary>();

  for (const record of filterWrongQuestionRecordsForMemberNotebook(records, classId, null)) {
    const normalizedStudentName = record.studentName.trim();
    const normalizedClassName = record.className.trim();
    const normalizedClassId = record.classId ?? 0;
    const bucketKey = `${normalizedClassId}::${normalizedStudentName}`;
    const pendingReviewCount = isWechatMiniProgramWrongQuestionRecord(record)
      ? (record.isMastered ? 0 : 1)
      : (record.reviewStatus.trim() === 'pending' ? 1 : 0);
    const hasTeacherFollowUp = isWechatMiniProgramWrongQuestionRecord(record)
      ? Boolean(record.isMastered)
      : (hasTeacherReview(record) || Boolean(record.teacherComment.trim()));
    const current = buckets.get(bucketKey);

    if (!current) {
      buckets.set(bucketKey, {
        studentName: normalizedStudentName,
        classId: normalizedClassId,
        className: normalizedClassName,
        totalCount: 1,
        pendingReviewCount,
        hasTeacherFollowUp,
        latestCreatedAt: record.createdAt,
      });
      continue;
    }

    current.totalCount += 1;
    current.pendingReviewCount += pendingReviewCount;
    current.hasTeacherFollowUp = current.hasTeacherFollowUp || hasTeacherFollowUp;
    if (record.createdAt.localeCompare(current.latestCreatedAt) > 0) {
      current.latestCreatedAt = record.createdAt;
    }
  }

  return Array.from(buckets.values()).sort((left, right) => right.latestCreatedAt.localeCompare(left.latestCreatedAt));
}

export function normalizeWrongQuestionIngestionAsset(rawAsset: unknown): WrongQuestionIngestionAsset {
  const source = isObjectRecord(rawAsset) ? rawAsset : {};
  return {
    id: pickNumberValue(source, ['id']) ?? 0,
    ingestionRunId: pickStringValue(source, ['ingestionRunId', 'ingestion_run_id']),
    assetRole: pickStringValue(source, ['assetRole', 'asset_role']),
    storagePath: pickStringValue(source, ['storagePath', 'storage_path']),
    fileUrl: pickStringValue(source, ['fileUrl', 'file_url']),
    mimeType: pickStringValue(source, ['mimeType', 'mime_type']),
    pageNumber: pickNumberValue(source, ['pageNumber', 'page_number']) ?? 0,
    width: pickNumberValue(source, ['width']) ?? 0,
    height: pickNumberValue(source, ['height']) ?? 0,
    metadataJson: pickStringValue(source, ['metadataJson', 'metadata_json']),
  };
}

export function normalizeWrongQuestionIngestionRun(rawRun: unknown): WrongQuestionIngestionRun {
  const source = isObjectRecord(rawRun) ? rawRun : {};
  return {
    id: pickStringValue(source, ['id']),
    source: pickStringValue(source, ['source']),
    status: pickStringValue(source, ['status']),
    currentStep: pickStringValue(source, ['currentStep', 'current_step']),
    classId: pickNumberValue(source, ['classId', 'class_id']),
    studentId: pickNumberValue(source, ['studentId', 'student_id']),
    teacherUserId: pickNumberValue(source, ['teacherUserId', 'teacher_user_id']),
    chatSessionId: pickStringValue(source, ['chatSessionId', 'chat_session_id']),
    originalFilename: pickStringValue(source, ['originalFilename', 'original_filename']),
    mimeType: pickStringValue(source, ['mimeType', 'mime_type']),
    metadataJson: pickStringValue(source, ['metadataJson', 'metadata_json']),
    errorMessage: pickStringValue(source, ['errorMessage', 'error_message']),
    createdAt: pickStringValue(source, ['createdAt', 'created_at']),
    detailUrl: pickStringValue(source, ['detailUrl', 'detail_url']),
    assets: Array.isArray(source.assets) ? source.assets.map((item) => normalizeWrongQuestionIngestionAsset(item)) : [],
    records: Array.isArray(source.records) ? source.records.map((item, index) => normalizeWrongQuestionRecord(item, index)) : [],
  };
}

export function normalizeWrongQuestionChatMessage(rawMessage: unknown): WrongQuestionChatMessage {
  const source = isObjectRecord(rawMessage) ? rawMessage : {};
  return {
    id: pickNumberValue(source, ['id']) ?? 0,
    sessionId: pickStringValue(source, ['sessionId', 'session_id']),
    role: pickStringValue(source, ['role']),
    stage: pickStringValue(source, ['stage']),
    content: pickStringValue(source, ['content']),
    createdAt: pickStringValue(source, ['createdAt', 'created_at']),
  };
}

export function normalizeWrongQuestionChatSession(rawSession: unknown): WrongQuestionChatSession {
  const source = isObjectRecord(rawSession) ? rawSession : {};
  return {
    id: pickStringValue(source, ['id']),
    status: pickStringValue(source, ['status']),
    currentStage: pickStringValue(source, ['currentStage', 'current_stage']),
    summaryText: pickStringValue(source, ['summaryText', 'summary_text']),
    ingestionRunId: pickStringValue(source, ['ingestionRunId', 'ingestion_run_id']),
    classId: pickNumberValue(source, ['classId', 'class_id']),
    studentId: pickNumberValue(source, ['studentId', 'student_id']),
    teacherUserId: pickNumberValue(source, ['teacherUserId', 'teacher_user_id']),
    detailUrl: pickStringValue(source, ['detailUrl', 'detail_url']),
    streamUrl: pickStringValue(source, ['streamUrl', 'stream_url']),
    messages: Array.isArray(source.messages) ? source.messages.map((item) => normalizeWrongQuestionChatMessage(item)) : [],
    records: Array.isArray(source.records) ? source.records.map((item, index) => normalizeWrongQuestionRecord(item, index)) : [],
  };
}

export function buildWrongQuestionQuery(filters: WrongQuestionFilters): string {
  const parts: string[] = [];

  for (const [key, value] of Object.entries(filters)) {
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (trimmed) {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(trimmed)}`);
      }
      continue;
    }

    if (value === true) {
      parts.push(`${encodeURIComponent(key)}=true`);
    }
  }

  return parts.length > 0 ? `?${parts.join('&')}` : '';
}

function buildWrongQuestionRoomQuery(roomId?: string): string {
  const normalizedRoomId = roomId?.trim();
  if (!normalizedRoomId) {
    return '';
  }
  return `?roomId=${encodeURIComponent(normalizedRoomId)}`;
}

export function buildWrongQuestionDetailPath(recordId: string, roomId?: string): string {
  return `/api/wrong-questions/${encodeURIComponent(recordId)}${buildWrongQuestionRoomQuery(roomId)}`;
}

export function buildWrongQuestionReviewPath(recordId: string, roomId?: string): string {
  return `/api/wrong-questions/${encodeURIComponent(recordId)}/review${buildWrongQuestionRoomQuery(roomId)}`;
}

export function buildWrongQuestionIngestionListPath(params: {
  source?: string;
  status?: string;
  classId?: number | null;
  studentId?: number | null;
  chatSessionId?: string;
  limit?: number;
}): string {
  const search = new URLSearchParams();
  if (params.source?.trim()) {
    search.set('source', params.source.trim());
  }
  if (params.status?.trim()) {
    search.set('status', params.status.trim());
  }
  if (typeof params.classId === 'number' && Number.isFinite(params.classId) && params.classId > 0) {
    search.set('class_id', String(params.classId));
  }
  if (typeof params.studentId === 'number' && Number.isFinite(params.studentId) && params.studentId > 0) {
    search.set('student_id', String(params.studentId));
  }
  if (params.chatSessionId?.trim()) {
    search.set('chat_session_id', params.chatSessionId.trim());
  }
  if (typeof params.limit === 'number' && Number.isFinite(params.limit) && params.limit > 0) {
    search.set('limit', String(params.limit));
  }
  const query = search.toString();
  return query ? `/api/wrong-question-ingestions?${query}` : '/api/wrong-question-ingestions';
}

export function buildWrongQuestionIngestionCreatePath(): string {
  return '/api/wrong-question-ingestions';
}

export function buildWrongQuestionIngestionAssetUploadPath(runId: string): string {
  return `/api/wrong-question-ingestions/${encodeURIComponent(runId)}/assets/upload`;
}

export function buildWrongQuestionChatDetailPath(sessionId: string): string {
  return `/api/wrong-question-chats/${encodeURIComponent(sessionId)}`;
}

export function buildWrongQuestionChatStreamPath(sessionId: string): string {
  return `/api/wrong-question-chats/${encodeURIComponent(sessionId)}/stream`;
}

export function buildWrongQuestionChatReopenPath(recordId: string): string {
  return `/api/wrong-questions/${encodeURIComponent(recordId)}/reopen-chat`;
}

export function normalizeWeeklyWrongQuestionFollowupResponse(payload: unknown): WeeklyWrongQuestionFollowupResponse {
  const source = isObjectRecord(payload) ? payload : {};
  const rawItems = Array.isArray(source.items) ? source.items : [];
  return {
    classId: pickNumberValue(source, ['class_id', 'classId']) ?? 0,
    className: String(source.class_name ?? source.className ?? ''),
    weekStartDate: String(source.week_start_date ?? source.weekStartDate ?? ''),
    weekEndDate: String(source.week_end_date ?? source.weekEndDate ?? ''),
    total: pickNumberValue(source, ['total']) ?? rawItems.length,
    items: rawItems.filter(isObjectRecord).map((item) => {
      const rawMessage = isObjectRecord(item.message) ? item.message : null;
      return {
        studentId: pickNumberValue(item, ['student_id', 'studentId']) ?? 0,
        studentName: String(item.student_name ?? item.studentName ?? ''),
        status: String(item.status ?? 'no_practice_needed'),
        practiceSheet: isObjectRecord(item.practice_sheet ?? item.practiceSheet)
          ? normalizeWrongQuestionPracticeSheetSummary(item.practice_sheet ?? item.practiceSheet)
          : null,
        weeklyQuestionCount: pickNumberValue(item, ['weekly_question_count', 'weeklyQuestionCount']) ?? 0,
        totalActiveQuestionCount: pickNumberValue(item, ['total_active_question_count', 'totalActiveQuestionCount']) ?? 0,
        candidateQuestionCount: pickNumberValue(item, ['candidate_question_count', 'candidateQuestionCount']) ?? 0,
        candidateRecordIds: normalizeStringList(item.candidate_record_ids ?? item.candidateRecordIds),
        recommendedCategory: String(item.recommended_category ?? item.recommendedCategory ?? ''),
        recommendationReason: String(item.recommendation_reason ?? item.recommendationReason ?? ''),
        topicCategories: normalizeStringList(item.topic_categories ?? item.topicCategories),
        representativeReasonSummaries: normalizeStringList(item.representative_reason_summaries ?? item.representativeReasonSummaries),
        sourceRecordIds: normalizeStringList(item.source_record_ids ?? item.sourceRecordIds),
        sourceRecords: Array.isArray(item.source_records ?? item.sourceRecords)
          ? (item.source_records ?? item.sourceRecords).map((record, index) => normalizeWrongQuestionRecord(record, index))
          : [],
        repeatedCategory: String(item.repeated_category ?? item.repeatedCategory ?? ''),
        repeatedCategoryCount: pickNumberValue(item, ['repeated_category_count', 'repeatedCategoryCount']) ?? 0,
        studentLibraryPdfUrl: String(item.student_library_pdf_url ?? item.studentLibraryPdfUrl ?? ''),
        message: rawMessage
          ? {
              id: pickNumberValue(rawMessage, ['id']) ?? 0,
              messageText: String(rawMessage.message_text ?? rawMessage.messageText ?? ''),
              sourceRecordIds: normalizeStringList(rawMessage.source_record_ids ?? rawMessage.sourceRecordIds),
              sourceSheetId: pickNumberValue(rawMessage, ['source_sheet_id', 'sourceSheetId']),
            }
          : null,
      };
    }),
  };
}

export function buildWeeklyWrongQuestionFollowupsPath(classId: number, weekStartDate: string): string {
  return `/api/wrong-question-followups/weekly?class_id=${encodeURIComponent(String(classId))}&week_start=${encodeURIComponent(weekStartDate)}`;
}

export function buildWeeklyWrongQuestionFollowupArchivePath(classId: number, weekStartDate: string): string {
  return `/api/wrong-question-followups/weekly/class-pdf-archive?class_id=${encodeURIComponent(String(classId))}&week_start=${encodeURIComponent(weekStartDate)}`;
}

export function buildWeeklyWrongQuestionFollowupMessagePath(): string {
  return '/api/wrong-question-followups/weekly/messages';
}

export function buildWeeklyWrongQuestionFollowupPracticeSheetPath(): string {
  return '/api/wrong-question-followups/weekly/practice-sheets';
}

export function buildWeeklyWrongQuestionFollowupPracticeSheetBatchPath(): string {
  return '/api/wrong-question-followups/weekly/practice-sheets/batch';
}

export function buildWeeklyWrongQuestionActivitySummaryPath(weekStartDate: string, organizationId?: number | null): string {
  const params = new URLSearchParams({ week_start: weekStartDate });
  if (typeof organizationId === 'number' && Number.isFinite(organizationId) && organizationId > 0) {
    params.set('organization_id', String(organizationId));
  }
  return `/api/admin/wrong-question-activity-summary?${params.toString()}`;
}

export function normalizeWeeklyWrongQuestionActivitySummaryResponse(payload: unknown): WeeklyWrongQuestionActivitySummary {
  const source = isObjectRecord(payload) ? payload : {};
  const rawClassItems = Array.isArray(source.class_items) ? source.class_items : Array.isArray(source.classItems) ? source.classItems : [];
  const rawTeacherItems = Array.isArray(source.teacher_items) ? source.teacher_items : Array.isArray(source.teacherItems) ? source.teacherItems : [];
  const rawStudentItems = Array.isArray(source.student_items) ? source.student_items : Array.isArray(source.studentItems) ? source.studentItems : [];
  return {
    weekStart: String(source.week_start ?? source.weekStart ?? ''),
    weekEnd: String(source.week_end ?? source.weekEnd ?? ''),
    classItems: rawClassItems.filter(isObjectRecord).map((item) => ({
      organizationId: pickNumberValue(item, ['organization_id', 'organizationId']) ?? 0,
      organizationName: String(item.organization_name ?? item.organizationName ?? ''),
      classId: pickNumberValue(item, ['class_id', 'classId']) ?? 0,
      className: String(item.class_name ?? item.className ?? ''),
      weeklyQuestionCount: pickNumberValue(item, ['weekly_question_count', 'weeklyQuestionCount']) ?? 0,
      uploadingStudentCount: pickNumberValue(item, ['uploading_student_count', 'uploadingStudentCount']) ?? 0,
      latestCreatedAt: String(item.latest_created_at ?? item.latestCreatedAt ?? ''),
    })),
    teacherItems: rawTeacherItems.filter(isObjectRecord).map((item) => ({
      organizationId: pickNumberValue(item, ['organization_id', 'organizationId']) ?? 0,
      organizationName: String(item.organization_name ?? item.organizationName ?? ''),
      teacherUserId: pickNumberValue(item, ['teacher_user_id', 'teacherUserId']) ?? 0,
      teacherName: String(item.teacher_name ?? item.teacherName ?? ''),
      classCount: pickNumberValue(item, ['class_count', 'classCount']) ?? 0,
      weeklyQuestionCount: pickNumberValue(item, ['weekly_question_count', 'weeklyQuestionCount']) ?? 0,
      involvedStudentCount: pickNumberValue(item, ['involved_student_count', 'involvedStudentCount']) ?? 0,
      pendingFollowupCount: pickNumberValue(item, ['pending_followup_count', 'pendingFollowupCount']) ?? 0,
    })),
    studentItems: rawStudentItems.filter(isObjectRecord).map((item) => ({
      organizationId: pickNumberValue(item, ['organization_id', 'organizationId']) ?? 0,
      organizationName: String(item.organization_name ?? item.organizationName ?? ''),
      classId: pickNumberValue(item, ['class_id', 'classId']) ?? 0,
      className: String(item.class_name ?? item.className ?? ''),
      studentId: pickNumberValue(item, ['student_id', 'studentId']) ?? 0,
      studentName: String(item.student_name ?? item.studentName ?? ''),
      weeklyQuestionCount: pickNumberValue(item, ['weekly_question_count', 'weeklyQuestionCount']) ?? 0,
      totalQuestionCount: pickNumberValue(item, ['total_question_count', 'totalQuestionCount']) ?? 0,
      topicCategories: normalizeStringList(item.topic_categories ?? item.topicCategories),
      latestCreatedAt: String(item.latest_created_at ?? item.latestCreatedAt ?? ''),
    })),
  };
}

export function normalizeWrongQuestionPracticeSheetSummary(rawSheet: unknown): WrongQuestionPracticeSheetSummary {
  const source = isObjectRecord(rawSheet) ? rawSheet : {};
  const pdfPath = pickStringValue(source, ['pdfPath', 'pdf_path']);
  const pdfUrl = pickStringValue(source, ['pdfUrl', 'pdf_url']);
  const downloadUrl = pickStringValue(source, ['downloadUrl', 'download_url']);
  const generationError = pickStringValue(source, ['generationError', 'generation_error']);
  const sheet: WrongQuestionPracticeSheetSummary = {
    id: pickNumberValue(source, ['id']) ?? 0,
    studentId: pickNumberValue(source, ['studentId', 'student_id']),
    classId: pickNumberValue(source, ['classId', 'class_id']),
    studentNameSnapshot: pickStringValue(source, ['studentNameSnapshot', 'student_name_snapshot']),
    classNameSnapshot: pickStringValue(source, ['classNameSnapshot', 'class_name_snapshot']),
    teacherNameSnapshot: pickStringValue(source, ['teacherNameSnapshot', 'teacher_name_snapshot']),
    questionCount: pickNumberValue(source, ['questionCount', 'question_count']) ?? 0,
    status: pickStringValue(source, ['status']) || 'pending',
    createdAt: pickStringValue(source, ['createdAt', 'created_at']),
  };

  if (pdfPath) {
    sheet.pdfPath = pdfPath;
  }

  if (pdfUrl) {
    sheet.pdfUrl = pdfUrl;
  }

  if (downloadUrl) {
    sheet.downloadUrl = downloadUrl;
  }

  if (generationError) {
    sheet.generationError = generationError;
  }

  return sheet;
}

export function normalizeWrongQuestionPracticeSheetListResponse(
  payload: WrongQuestionPracticeSheetListApiResponse | WrongQuestionPracticeSheetSummary[],
): WrongQuestionPracticeSheetSummary[] {
  const source = Array.isArray(payload) ? { items: payload } : payload;
  const rawItems = Array.isArray(source.items) ? source.items : [];

  return rawItems
    .map((item) => normalizeWrongQuestionPracticeSheetSummary(item))
    .filter((item) => item.id > 0)
    .sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export function buildWrongQuestionPracticeSheetsPath(studentId: number): string {
  return `/api/wrong-question-practice-sheets?student_id=${encodeURIComponent(String(studentId))}`;
}

function normalizeWrongQuestionPracticePackMode(value: string): WrongQuestionPracticePackMode {
  return value === 'reason' ? 'reason' : 'topic';
}

function normalizeWrongQuestionPracticePackVolume(value: string): WrongQuestionPracticePackVolume {
  if (value === 'light' || value === 'intensive') {
    return value;
  }
  return 'standard';
}

function normalizeWrongQuestionPracticePackStudent(rawStudent: unknown): WrongQuestionPracticePackStudent {
  const source = isObjectRecord(rawStudent) ? rawStudent : {};
  const pdfPath = pickStringValue(source, ['pdfPath', 'pdf_path']);
  const generationError = pickStringValue(source, ['generationError', 'generation_error']);
  const student: WrongQuestionPracticePackStudent = {
    studentId: pickNumberValue(source, ['studentId', 'student_id']) ?? 0,
    studentNameSnapshot: pickStringValue(source, ['studentNameSnapshot', 'student_name_snapshot']),
    status: pickStringValue(source, ['status']) || 'pending',
    requestedQuestionCount: pickNumberValue(source, ['requestedQuestionCount', 'requested_question_count']) ?? 0,
    realQuestionCount: pickNumberValue(source, ['realQuestionCount', 'real_question_count']) ?? 0,
    variantQuestionCount: pickNumberValue(source, ['variantQuestionCount', 'variant_question_count']) ?? 0,
    generationError,
  };

  if (pdfPath) {
    student.pdfPath = pdfPath;
  }

  return student;
}

export function normalizeWrongQuestionPracticePackJobResponse(payload: unknown): {
  job: WrongQuestionPracticePackJob | null;
  reused: boolean;
} {
  const source = isObjectRecord(payload) ? payload : {};
  const rawJob = isObjectRecord(source.job) ? source.job : null;
  if (!rawJob) {
    return { job: null, reused: source.reused === true };
  }

  const downloadUrl = pickStringValue(rawJob, ['downloadUrl', 'download_url']);
  const generationError = pickStringValue(rawJob, ['generationError', 'generation_error']);
  const job: WrongQuestionPracticePackJob = {
    id: pickNumberValue(rawJob, ['id']) ?? 0,
    status: pickStringValue(rawJob, ['status']) || 'pending',
    mode: normalizeWrongQuestionPracticePackMode(pickStringValue(rawJob, ['mode'])),
    target: pickStringValue(rawJob, ['target']),
    volume: normalizeWrongQuestionPracticePackVolume(pickStringValue(rawJob, ['volume'])),
    requestedQuestionCount: pickNumberValue(rawJob, ['requestedQuestionCount', 'requested_question_count']) ?? 0,
    students: Array.isArray(rawJob.students)
      ? rawJob.students.map((item) => normalizeWrongQuestionPracticePackStudent(item))
      : [],
  };

  if (downloadUrl) {
    job.downloadUrl = downloadUrl;
  }

  if (generationError) {
    job.generationError = generationError;
  }

  return { job, reused: source.reused === true };
}

export function normalizeWrongQuestionPracticePackListResponse(payload: unknown): WrongQuestionPracticePackJob[] {
  const source = isObjectRecord(payload) ? payload : {};
  const items = Array.isArray(source.items) ? source.items : [];
  return items
    .map((item) => normalizeWrongQuestionPracticePackJobResponse({ job: item }).job)
    .filter((item): item is WrongQuestionPracticePackJob => item !== null);
}

export function buildWrongQuestionPracticePackCreatePath(): string {
  return '/api/wrong-question-practice-packs';
}

export function buildWrongQuestionPracticePackListPath(classId: number): string {
  return `/api/wrong-question-practice-packs?class_id=${encodeURIComponent(String(classId))}`;
}

export function buildWrongQuestionPracticePackDetailPath(jobId: number): string {
  return `/api/wrong-question-practice-packs/${encodeURIComponent(String(jobId))}`;
}

export function buildWrongQuestionPracticePackDownloadPath(jobId: number): string {
  return `/api/wrong-question-practice-packs/${encodeURIComponent(String(jobId))}/download`;
}
