export interface WrongQuestionAnalysis {
  questionCategory: string;
  errorType: string;
  knowledgePoints: string[];
  isRepeatedMistake?: string;
  teacherPriority?: string;
  selectedErrorType?: string;
  selectedKnowledgePoints?: string[];
  selectedActions?: string[];
  selectedReasons?: string[];
  studentNote?: string;
}

export interface WrongQuestionReviewDraft {
  selectedErrorType: string;
  selectedKnowledgePoints: string[];
  selectedActions: string[];
  selectedReasons: string[];
  studentNote: string;
  teacherComment: string;
  reviewStatus: string;
  questionText?: string;
}

export interface WrongQuestionReviewPayload {
  selectedErrorType: string;
  selectedKnowledgePoints: string[];
  selectedActions: string[];
  selectedReasons: string[];
  studentNote: string;
  teacherComment: string;
  reviewStatus: string;
  question_text?: string;
}

export type WrongQuestionMappingStatus = 'mapped' | 'unmapped' | 'ambiguous' | 'needs_review';

export interface WrongQuestionRecord {
  id: string;
  roomId: string;
  source: string;
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
  teacherComment: string;
  reviewStatus: string;
  analysis: WrongQuestionAnalysis;
}

export interface WrongQuestionFilters {
  studentName?: string;
  className?: string;
  subject?: string;
  teacherName?: string;
  errorType?: string;
  onlyPendingReview?: boolean;
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

export function isWechatMiniProgramWrongQuestionRecord(record: WrongQuestionRecord): boolean {
  return record.source === 'wechat_mp';
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
  const studentNote = pickStringValue(source, ['studentNote', 'student_note']);

  const analysis: WrongQuestionAnalysis = {
    questionCategory: pickStringValue(source, ['questionCategory', 'question_category']),
    errorType: pickStringValue(source, ['errorType', 'error_type']),
    knowledgePoints: pickStringArrayValue(source, ['knowledgePoints', 'knowledge_points']),
  };

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

  if (recognitionStatus) {
    record.recognitionStatus = recognitionStatus;
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

  return record;
}

function normalizeDraftList(values: string[]): string[] {
  return values
    .map((value) => value.trim())
    .filter(Boolean);
}

export function buildWrongQuestionReviewDraft(record: WrongQuestionRecord): WrongQuestionReviewDraft {
  const draft: WrongQuestionReviewDraft = {
    selectedErrorType: record.analysis.selectedErrorType?.trim() ?? '',
    selectedKnowledgePoints: normalizeDraftList(record.analysis.selectedKnowledgePoints ?? []),
    selectedActions: normalizeDraftList(record.analysis.selectedActions ?? []),
    selectedReasons: normalizeDraftList(record.analysis.selectedReasons ?? []),
    studentNote: record.analysis.studentNote?.trim() ?? '',
    teacherComment: record.teacherComment.trim(),
    reviewStatus: record.reviewStatus.trim() || (isWechatMiniProgramWrongQuestionRecord(record) ? 'pending' : ''),
  };

  if (isWechatMiniProgramWrongQuestionRecord(record) && !record.isGeometry) {
    draft.questionText = record.questionText?.trim() ?? '';
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

  if (typeof draft.questionText === 'string') {
    payload.question_text = draft.questionText.trim();
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

  return {
    ...record,
    teacherComment: payload.teacherComment,
    reviewStatus: payload.reviewStatus || record.reviewStatus,
    questionText: typeof payload.question_text === 'string' ? payload.question_text : record.questionText,
    analysis: nextAnalysis,
  };
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
    return record.reviewStatus.trim() === 'reviewed' || Boolean(record.teacherComment.trim());
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

export function buildWrongQuestionSummaryExportPath(filters: WrongQuestionFilters): string {
  return `/api/wrong-questions/summary/export${buildWrongQuestionQuery(filters)}`;
}

function getWrongQuestionAuthToken(): string {
  if (typeof localStorage === 'undefined') {
    return '';
  }

  return localStorage.getItem('xr_token') || '';
}

function getDownloadFileName(contentDisposition: string | null, fallbackFileName: string): string {
  if (!contentDisposition) {
    return fallbackFileName;
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const basicMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  return basicMatch?.[1] || fallbackFileName;
}

async function getResponseErrorMessage(response: Response, fallbackMessage: string): Promise<string> {
  const errorPayload = await response.json().catch(() => ({ error: response.statusText }));
  if (typeof errorPayload === 'object' && errorPayload && 'error' in errorPayload && typeof errorPayload.error === 'string') {
    return errorPayload.error;
  }

  return fallbackMessage;
}

export async function downloadWrongQuestionSummary(filters: WrongQuestionFilters): Promise<void> {
  if (typeof document === 'undefined') {
    throw new Error('当前环境不支持导出下载');
  }

  const token = getWrongQuestionAuthToken();
  const response = await fetch(buildWrongQuestionSummaryExportPath(filters), {
    headers: token ? { 'X-Auth-Token': token } : {},
  });

  if (response.status === 401) {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('xr_token');
    }
    if (typeof window !== 'undefined') {
      window.location.reload();
    }
    throw new Error('登录已过期，请重新登录');
  }

  if (!response.ok) {
    throw new Error(await getResponseErrorMessage(response, '智能错题导出失败'));
  }

  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  const fileName = getDownloadFileName(response.headers.get('content-disposition'), 'wrong-questions-summary.pdf');

  link.href = downloadUrl;
  link.download = fileName;
  link.rel = 'noopener';
  link.style.display = 'none';
  document.body.appendChild(link);

  try {
    link.click();
  } finally {
    document.body.removeChild(link);
    URL.revokeObjectURL(downloadUrl);
  }
}
