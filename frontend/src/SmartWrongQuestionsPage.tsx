import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, MessageSquare, RefreshCw, Upload, X } from 'lucide-react';

import {
  apiFetch,
  apiUploadFormWithProgress,
  workspaceCardClass,
  workspaceFieldClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSoftCardClass,
} from './App';
import {
  buildMemberStudentNotebookSummaries,
  buildWeeklyWrongQuestionActivitySummaryPath,
  buildWeeklyWrongQuestionFollowupArchivePath,
  buildWeeklyWrongQuestionFollowupMessagePath,
  buildWrongQuestionPracticePackCreatePath,
  buildWrongQuestionPracticePackDetailPath,
  buildWrongQuestionPracticePackListPath,
  buildWeeklyWrongQuestionFollowupPracticeSheetBatchPath,
  buildWeeklyWrongQuestionFollowupPracticeSheetPath,
  buildWeeklyWrongQuestionFollowupsPath,
  buildWrongQuestionDetailPath,
  buildWrongQuestionPracticeSheetsPath,
  buildWrongQuestionReviewDraft,
  buildWrongQuestionQuery,
  buildWrongQuestionChatDetailPath,
  buildWrongQuestionChatFollowupPath,
  buildWrongQuestionChatReopenPath,
  buildWrongQuestionChatStreamPath,
  buildWrongQuestionIngestionAssetUploadPath,
  buildWrongQuestionIngestionCreatePath,
  buildWrongQuestionIngestionListPath,
  buildWrongQuestionReviewPayload,
  buildWrongQuestionReviewPath,
  buildWrongQuestionTopicSummaries,
  filterWrongQuestionRecordsByTopic,
  filterWrongQuestionRecordsForMemberNotebook,
  getWrongQuestionSemanticModel,
  getWrongQuestionSourceLabel,
  hydrateWrongQuestionReviewDraftFromDetail,
  isPrimarySchoolWrongQuestionRecord,
  isWechatMiniProgramWrongQuestionRecord,
  normalizeWeeklyWrongQuestionActivitySummaryResponse,
  normalizeWeeklyWrongQuestionFollowupResponse,
  normalizeWrongQuestionChatSession,
  normalizeWrongQuestionIngestionRun,
  normalizeWrongQuestionPracticePackJobResponse,
  normalizeWrongQuestionPracticePackListResponse,
  normalizeWrongQuestionPracticeSheetListResponse,
  normalizeWrongQuestionRecord,
  normalizeWrongQuestionListResponse,
  resolveSavedWrongQuestionRecord,
  summarizeWrongQuestionRecords,
  type MemberStudentNotebookSummary,
  type WeeklyWrongQuestionActivityStudentItem,
  type WeeklyWrongQuestionActivitySummary,
  type WeeklyWrongQuestionFollowupItem,
  type WrongQuestionChatSession,
  type WrongQuestionIngestionRun,
  type WrongQuestionPracticePackJob,
  type WrongQuestionPracticePackListApiResponse,
  type WrongQuestionPracticePackMode,
  type WrongQuestionPracticePackVolume,
  type WrongQuestionPracticeSheetListApiResponse,
  type WrongQuestionPracticeSheetSummary,
  type WrongQuestionFilters,
  type WrongQuestionGenerationMetadata,
  type WrongQuestionListApiResponse,
  type WrongQuestionRecord,
  type WrongQuestionReviewDraft,
  type WrongQuestionSummary,
} from './smartWrongQuestions';
import { buildWrongQuestionLatexPreviewModel } from './wrongQuestionLatex.js';

type SmartWrongQuestionsPageProps = {
  currentUser: {
    display_name: string;
    organization_name: string;
    role: 'super_owner' | 'owner' | 'admin' | 'member';
  };
};

type WrongQuestionClassFilterOption = {
  id: number;
  name: string;
  subject: string;
  teacherUserId: number | null;
};

type WrongQuestionTeacherFilterOption = {
  id: number;
  name: string;
};

type WrongQuestionStudentFilterOption = {
  id: number;
  name: string;
};

type WrongQuestionOrganizationOption = {
  id: number;
  name: string;
};

type NotebookModalView = 'questions' | 'practice_history';

type WrongQuestionChatDraftState = {
  questionText: string;
  topicCategory: string;
  knowledgeTagsText: string;
  followupOutcome: string;
  replyText: string;
};

type WrongQuestionChatLocalPreview = {
  name: string;
  url: string;
};

const WRONG_QUESTION_ERROR_TYPE_OPTIONS = [
  '知识点问题',
  '细节问题',
  '方法问题',
  '审题问题',
];

const WRONG_QUESTION_TOPIC_CATEGORY_OPTIONS = [
  '未分类',
  '计算',
  '经济',
  '浓度',
  '工程',
  '行程',
  '几何',
  '数论',
];

const WRONG_QUESTION_CHAT_STAGE_LABELS: Record<string, string> = {
  ask_why_wrong: '先说错因',
  ask_unknown_step: '定位卡点',
  ask_help_mode: '选择帮助方式',
  ready_to_archive: '已归档',
};

const WRONG_QUESTION_REFLECTION_MODE_LABELS: Record<string, string> = {
  archive_reflection: '归档反思',
  teacher_rework: '老师退回补充',
  mastery_followup: '掌握追问',
};

const WRONG_QUESTION_REFLECTION_STAGE_LABELS: Record<string, string> = {
  ask_why_wrong: '知道为什么错',
  ask_unknown_step: '具体卡点',
  ask_help_mode: '需要什么帮助',
};

const WRONG_QUESTION_CHAT_CONFIRMATION_REASON_LABELS: Record<string, string> = {
  missing_image_asset: '缺少原始图片',
  missing_question_text: '题目文本还不完整',
  knowledge_tags_unconfirmed: '知识点还没确认',
  student_confused_step: '学生卡点描述还不够清楚',
};

const WRONG_QUESTION_CONFIRMATION_STATUS_LABELS: Record<string, string> = {
  pending: '待老师复核',
  confirmed: '已确认',
  returned: '已退回',
  not_required: '无需复核',
};

const WRONG_QUESTION_INGESTION_ASSET_ROLE_LABELS: Record<string, string> = {
  original_upload: '原始上传',
  ocr_page_image: 'OCR 页图',
  split_preview: '切题预览',
};

const WRONG_QUESTION_GENERATION_METADATA_LABELS: Array<[keyof WrongQuestionGenerationMetadata, string]> = [
  ['schemaVersion', 'Schema'],
  ['promptVersion', 'Prompt'],
  ['templateVersion', 'Template'],
  ['ruleVersion', 'Rule'],
  ['provider', 'Provider'],
  ['modelVersion', 'Model'],
  ['entrypoint', 'Entrypoint'],
  ['ingestionEntrypoint', 'Ingestion'],
  ['archiveSource', 'Archive'],
];

const practicePackStatusLabels: Record<string, string> = {
  pending: '等待生成',
  running: '生成中',
  ready: '生成成功',
  partial_failed: '部分生成成功',
  failed: '生成失败',
  skipped: '已跳过',
};

const PRACTICE_PACK_REASON_TARGET_OPTIONS = [
  ...WRONG_QUESTION_ERROR_TYPE_OPTIONS,
  '计算错误',
];

const initialFilters: WrongQuestionFilters = {
  studentName: '',
  className: '',
  subject: '',
  teacherName: '',
  errorType: '',
  confirmationState: '',
};

function hasSnapshotDifference(canonicalValue: string, snapshotValue: string): boolean {
  const canonical = canonicalValue.trim();
  const snapshot = snapshotValue.trim();
  return Boolean(snapshot) && snapshot !== canonical;
}

function getWrongQuestionSourceBadgeClass(source: string): string {
  return source === 'wechat_mp'
    ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300'
    : 'border-sky-200 bg-white/80 text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300';
}

function normalizeWrongQuestionConfirmationStatus(record: WrongQuestionRecord | null): string {
  if (!record) {
    return 'not_required';
  }
  if (record.confirmationStatus && WRONG_QUESTION_CONFIRMATION_STATUS_LABELS[record.confirmationStatus]) {
    return record.confirmationStatus;
  }
  if (record.needsTeacherConfirmation) {
    return 'pending';
  }
  if (record.confirmationReviewedAt || typeof record.confirmationReviewedBy === 'number') {
    return 'confirmed';
  }
  return 'not_required';
}

function getWrongQuestionConfirmationStatusBadgeClass(status: string): string {
  switch (status) {
    case 'confirmed':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300';
    case 'returned':
      return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300';
    case 'pending':
      return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-400/30 dark:bg-amber-500/10 dark:text-amber-300';
    default:
      return 'border-slate-200 bg-white/80 text-slate-600 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-300';
  }
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function getPracticePackStatusLabel(status: string): string {
  const normalizedStatus = String(status || '').trim();
  return practicePackStatusLabels[normalizedStatus] || normalizedStatus || '未知';
}

function buildUniquePracticePackTargets(values: string[]): string[] {
  const seen = new Set<string>();
  const targets: string[] = [];
  for (const value of values) {
    const normalizedValue = value.trim();
    if (!normalizedValue || seen.has(normalizedValue)) {
      continue;
    }
    seen.add(normalizedValue);
    targets.push(normalizedValue);
  }
  return targets;
}

function canGenerateWrongQuestionPractice(record: WrongQuestionRecord): boolean {
  if (!Boolean(record.studentId) || record.recognitionStatus !== 'recognized' || record.isMastered) {
    return false;
  }
  if (record.source === 'wechat_mp') {
    return true;
  }
  if (record.source === 'ai_chat') {
    const confirmationStatus = normalizeWrongQuestionConfirmationStatus(record);
    return confirmationStatus === 'confirmed' || confirmationStatus === 'not_required';
  }
  return false;
}

function canStartWrongQuestionMasteryFollowup(record: WrongQuestionRecord | null): boolean {
  if (!record || record.source !== 'ai_chat') {
    return false;
  }
  const confirmationStatus = normalizeWrongQuestionConfirmationStatus(record);
  if (confirmationStatus !== 'confirmed' && confirmationStatus !== 'not_required') {
    return false;
  }
  const practiceSheetCount = record.masteryTracking?.practiceSheetCount ?? record.masteryAssessment?.practiceSheetCount ?? 0;
  if (practiceSheetCount <= 0) {
    return false;
  }
  const latestPracticeStatus = (record.masteryAssessment?.latestPracticeStatus ?? record.masteryTracking?.latestPracticeStatus ?? '').trim();
  return latestPracticeStatus !== 'pending' && latestPracticeStatus !== 'generating';
}

function getWrongQuestionPracticeStatusLabel(status: string): string {
  if (status === 'ready') {
    return '已完成';
  }
  if (status === 'failed') {
    return '生成失败';
  }
  return '生成中';
}

function getWrongQuestionMasterySuggestedActionLabel(action: string): string {
  if (action === 'continue_rework_chat') {
    return '继续 AI 补充';
  }
  if (action === 'continue_follow_up') {
    return '继续掌握追问';
  }
  if (action === 'teacher_review') {
    return '先完成老师复核';
  }
  if (action === 'create_practice') {
    return '先进入再练';
  }
  if (action === 'wait_practice') {
    return '等待练习生成';
  }
  if (action === 'retry_practice') {
    return '重新生成练习';
  }
  if (action === 'review_mastery') {
    return '结合再练结果确认是否掌握';
  }
  if (action === 'monitor') {
    return '继续观察后续表现';
  }
  return '继续跟进';
}

function getWrongQuestionMasteryFollowupOutcomeLabel(outcome: string): string {
  if (outcome === 'still_confused') {
    return '仍然没吃透';
  }
  if (outcome === 'needs_another_practice') {
    return '需要再练一轮';
  }
  if (outcome === 'likely_mastered') {
    return '大概率已掌握';
  }
  return '未记录';
}

function readWrongQuestionToken(): string {
  try {
    return globalThis.localStorage?.getItem?.('xr_token') || '';
  } catch {
    return '';
  }
}

function normalizeStudentLibraryPdfPath(path: string): string {
  const normalizedPath = path.trim();
  if (!normalizedPath) {
    return '';
  }
  if (/^(https?:\/\/|\/api\/)/.test(normalizedPath)) {
    return normalizedPath;
  }
  const studentLibraryMatch = normalizedPath.match(/(?:^|\/)student-(\d+)\.pdf$/i);
  if (studentLibraryMatch) {
    return `/api/wechat/student-libraries/${studentLibraryMatch[1]}`;
  }
  return normalizedPath;
}

function buildWrongQuestionAuthedPath(path: string): string {
  const normalizedPath = normalizeStudentLibraryPdfPath(path);
  if (!normalizedPath) {
    return '';
  }
  const token = readWrongQuestionToken();
  if (!token) {
    return normalizedPath;
  }
  const separator = normalizedPath.includes('?') ? '&' : '?';
  return `${normalizedPath}${separator}token=${encodeURIComponent(token)}`;
}

function getCurrentMondayDateInputValue(): string {
  const date = new Date();
  const day = date.getDay();
  const daysSinceMonday = day === 0 ? 6 : day - 1;
  date.setDate(date.getDate() - daysSinceMonday);
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const dayOfMonth = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${dayOfMonth}`;
}

function buildWrongQuestionChatSessionId(): string {
  const randomPart = Math.random().toString(36).slice(2, 8);
  return `wrong-question-chat-${Date.now()}-${randomPart}`;
}

function parseWrongQuestionAssetMetadata(value: string): Record<string, unknown> | null {
  if (!value.trim()) {
    return null;
  }
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

function buildWrongQuestionGenerationMetadataEntries(
  metadata?: WrongQuestionGenerationMetadata,
): Array<{ label: string; value: string }> {
  if (!metadata) {
    return [];
  }
  return WRONG_QUESTION_GENERATION_METADATA_LABELS
    .map(([key, label]) => ({ label, value: String(metadata[key] ?? '').trim() }))
    .filter((item) => item.value);
}

function parseWeeklyFollowupMessageId(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return 0;
}

function normalizeWeeklyFollowupSourceRecordIds(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => String(item ?? '').trim())
    .filter(Boolean);
}

function extractGeneratedWeeklyFollowupMessage(response: unknown): WeeklyWrongQuestionFollowupItem['message'] {
  if (!isObjectRecord(response) || !isObjectRecord(response.message)) {
    return null;
  }

  const message = response.message;
  const messageText = typeof message.message_text === 'string'
    ? message.message_text
    : typeof message.messageText === 'string'
      ? message.messageText
      : '';
  const sourceRecordIds = Object.prototype.hasOwnProperty.call(message, 'source_record_ids')
    ? normalizeWeeklyFollowupSourceRecordIds(message.source_record_ids)
    : normalizeWeeklyFollowupSourceRecordIds(message.sourceRecordIds);

  return {
    id: parseWeeklyFollowupMessageId(message.id),
    messageText,
    sourceRecordIds,
    sourceSheetId: typeof message.source_sheet_id === 'number'
      ? message.source_sheet_id
      : typeof message.sourceSheetId === 'number'
        ? message.sourceSheetId
        : null,
  };
}

function extractSavedWrongQuestionResponseRecord(response: unknown): unknown {
  if (!isObjectRecord(response)) {
    return undefined;
  }

  if (Object.prototype.hasOwnProperty.call(response, 'record')) {
    return response.record;
  }

  if (
    Object.prototype.hasOwnProperty.call(response, 'id')
    || Object.prototype.hasOwnProperty.call(response, 'analysis')
    || Object.prototype.hasOwnProperty.call(response, 'student_name')
    || Object.prototype.hasOwnProperty.call(response, 'studentName')
  ) {
    return response;
  }

  return undefined;
}

export function SmartWrongQuestionsPage({ currentUser }: SmartWrongQuestionsPageProps) {
  const hasStaffScope = currentUser.role === 'super_owner' || currentUser.role === 'owner' || currentUser.role === 'admin';
  const isMemberScope = currentUser.role === 'member';
  const usesStudentNotebook = true;
  const canViewWeeklyActivitySummary = currentUser.role === 'super_owner';
  const [filters, setFilters] = useState<WrongQuestionFilters>(initialFilters);
  const [records, setRecords] = useState<WrongQuestionRecord[]>([]);
  const [classOptions, setClassOptions] = useState<WrongQuestionClassFilterOption[]>([]);
  const [teacherOptions, setTeacherOptions] = useState<WrongQuestionTeacherFilterOption[]>([]);
  const [studentOptions, setStudentOptions] = useState<WrongQuestionStudentFilterOption[]>([]);
  const [organizationOptions, setOrganizationOptions] = useState<WrongQuestionOrganizationOption[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [selectedStudentName, setSelectedStudentName] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [savingReview, setSavingReview] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [pdfRefreshNotice, setPdfRefreshNotice] = useState('');
  const [refreshingLibraryPdf, setRefreshingLibraryPdf] = useState(false);
  const [reviewDraftByRecordId, setReviewDraftByRecordId] = useState<Record<string, WrongQuestionReviewDraft>>({});
  const [reviewDraftDirtyByRecordId, setReviewDraftDirtyByRecordId] = useState<Record<string, boolean>>({});
  const [serverSummary, setServerSummary] = useState<WrongQuestionSummary | null>(null);
  const requestVersionRef = useRef(0);
  const detailRequestVersionRef = useRef(0);
  const practiceHistoryRequestVersionRef = useRef(0);
  const weeklyActivityRequestVersionRef = useRef(0);
  const weeklyFollowupRequestVersionRef = useRef(0);
  const practicePackRequestVersionRef = useRef(0);
  const reviewDraftDirtyByRecordIdRef = useRef<Record<string, boolean>>({});
  const reviewDraftByRecordIdRef = useRef<Record<string, WrongQuestionReviewDraft>>({});
  const recordsRef = useRef(records);
  recordsRef.current = records;
  reviewDraftByRecordIdRef.current = reviewDraftByRecordId;
  const [notebookModalView, setNotebookModalView] = useState<NotebookModalView>('questions');
  const [notebookMasteryFilter, setNotebookMasteryFilter] = useState<'all' | 'pending' | 'mastered'>('all');
  const [notebookTopicFilter, setNotebookTopicFilter] = useState('全部');
  const [selectedPracticeRecordIds, setSelectedPracticeRecordIds] = useState<string[]>([]);
  const [practiceSelectionTouched, setPracticeSelectionTouched] = useState(false);
  const [practiceSheets, setPracticeSheets] = useState<WrongQuestionPracticeSheetSummary[]>([]);
  const [practiceHistoryLoading, setPracticeHistoryLoading] = useState(false);
  const [practiceHistoryError, setPracticeHistoryError] = useState('');
  const [creatingPractice, setCreatingPractice] = useState(false);
  const [practiceActionError, setPracticeActionError] = useState('');
  const [practiceActionNotice, setPracticeActionNotice] = useState('');
  const [weeklyActivityOpen, setWeeklyActivityOpen] = useState(false);
  const [weeklyActivityWeekStart, setWeeklyActivityWeekStart] = useState(getCurrentMondayDateInputValue);
  const [weeklyActivityOrganizationId, setWeeklyActivityOrganizationId] = useState<number | null>(null);
  const [weeklyActivitySummary, setWeeklyActivitySummary] = useState<WeeklyWrongQuestionActivitySummary | null>(null);
  const [weeklyActivityLoading, setWeeklyActivityLoading] = useState(false);
  const [weeklyActivityError, setWeeklyActivityError] = useState('');
  const [weeklyActivityNotice, setWeeklyActivityNotice] = useState('');
  const [weeklyFollowupOpen, setWeeklyFollowupOpen] = useState(false);
  const [weeklyFollowupWeekStart, setWeeklyFollowupWeekStart] = useState(getCurrentMondayDateInputValue);
  const [weeklyFollowupItems, setWeeklyFollowupItems] = useState<WeeklyWrongQuestionFollowupItem[]>([]);
  const [weeklyFollowupLoading, setWeeklyFollowupLoading] = useState(false);
  const [weeklyFollowupError, setWeeklyFollowupError] = useState('');
  const [weeklyFollowupNotice, setWeeklyFollowupNotice] = useState('');
  const [generatingWeeklyFollowupStudentId, setGeneratingWeeklyFollowupStudentId] = useState<number | null>(null);
  const [generatingWeeklyPracticeStudentId, setGeneratingWeeklyPracticeStudentId] = useState<number | null>(null);
  const [batchGeneratingWeeklyPractice, setBatchGeneratingWeeklyPractice] = useState(false);
  const [practicePackMode, setPracticePackMode] = useState<WrongQuestionPracticePackMode>('topic');
  const [practicePackTarget, setPracticePackTarget] = useState('');
  const [practicePackVolume, setPracticePackVolume] = useState<WrongQuestionPracticePackVolume>('standard');
  const [practicePackJobs, setPracticePackJobs] = useState<WrongQuestionPracticePackJob[]>([]);
  const [practicePackGenerating, setPracticePackGenerating] = useState(false);
  const [wrongQuestionChatRun, setWrongQuestionChatRun] = useState<WrongQuestionIngestionRun | null>(null);
  const [wrongQuestionChatSession, setWrongQuestionChatSession] = useState<WrongQuestionChatSession | null>(null);
  const [wrongQuestionChatDraft, setWrongQuestionChatDraft] = useState<WrongQuestionChatDraftState>({
    questionText: '',
    topicCategory: '',
    knowledgeTagsText: '',
    followupOutcome: '',
    replyText: '',
  });
  const [wrongQuestionChatFiles, setWrongQuestionChatFiles] = useState<File[]>([]);
  const [wrongQuestionChatLocalPreviews, setWrongQuestionChatLocalPreviews] = useState<WrongQuestionChatLocalPreview[]>([]);
  const [wrongQuestionChatLoading, setWrongQuestionChatLoading] = useState(false);
  const [wrongQuestionChatUploading, setWrongQuestionChatUploading] = useState(false);
  const [wrongQuestionChatSending, setWrongQuestionChatSending] = useState(false);
  const [wrongQuestionChatUploadProgress, setWrongQuestionChatUploadProgress] = useState(0);
  const [wrongQuestionChatError, setWrongQuestionChatError] = useState('');
  const [wrongQuestionChatNotice, setWrongQuestionChatNotice] = useState('');
  const wrongQuestionChatRequestVersionRef = useRef(0);
  const pendingNotebookMasteryFollowupRecordIdRef = useRef('');

  const summary = useMemo(() => {
    if (records.some((item) => isWechatMiniProgramWrongQuestionRecord(item))) {
      return summarizeWrongQuestionRecords(records);
    }

    return serverSummary ?? summarizeWrongQuestionRecords(records);
  }, [records, serverSummary]);
  const selectedTeacherId = useMemo(() => {
    const normalizedTeacherName = filters.teacherName?.trim() ?? '';
    if (!normalizedTeacherName) {
      return null;
    }

    return teacherOptions.find((item) => item.name === normalizedTeacherName)?.id ?? null;
  }, [filters.teacherName, teacherOptions]);
  const visibleClassOptions = useMemo(() => {
    if (!hasStaffScope || selectedTeacherId === null) {
      return classOptions;
    }

    return classOptions.filter((item) => item.teacherUserId === selectedTeacherId);
  }, [classOptions, hasStaffScope, selectedTeacherId]);
  const selectedStaffClassOption = useMemo(() => {
    const normalizedClassName = filters.className?.trim() ?? '';
    if (!normalizedClassName) {
      return null;
    }

    return visibleClassOptions.find((item) => item.name === normalizedClassName) ?? null;
  }, [filters.className, visibleClassOptions]);
  const subjectOptions = useMemo(() => {
    const optionSource = selectedStaffClassOption ? [selectedStaffClassOption] : visibleClassOptions;
    return Array.from(new Set(optionSource.map((item) => item.subject.trim()).filter(Boolean)));
  }, [selectedStaffClassOption, visibleClassOptions]);
  const activeNotebookClassId = hasStaffScope
    ? (selectedStaffClassOption?.id ?? null)
    : selectedClassId;
  const activeWeeklyFollowupClassId = selectedClassId ?? selectedStaffClassOption?.id ?? null;
  const memberNotebookSummaries = useMemo<MemberStudentNotebookSummary[]>(() => {
    if (!usesStudentNotebook) {
      return [];
    }
    return buildMemberStudentNotebookSummaries(records, activeNotebookClassId);
  }, [activeNotebookClassId, records, usesStudentNotebook]);
  const memberNotebookSummaryMasteryFollowupRecordByStudentName = useMemo(() => {
    if (!usesStudentNotebook) {
      return new Map<string, WrongQuestionRecord | null>();
    }
    return new Map(
      memberNotebookSummaries.map((item) => {
        const targetRecord = [...filterWrongQuestionRecordsForMemberNotebook(records, activeNotebookClassId, item.studentName)]
          .reverse()
          .find((record) => canStartWrongQuestionMasteryFollowup(record)) ?? null;
        return [item.studentName, targetRecord];
      }),
    );
  }, [activeNotebookClassId, memberNotebookSummaries, records, usesStudentNotebook]);
  const memberNotebookRecords = useMemo(() => {
    if (!usesStudentNotebook) {
      return [];
    }
    return filterWrongQuestionRecordsForMemberNotebook(records, activeNotebookClassId, selectedStudentName);
  }, [activeNotebookClassId, records, selectedStudentName, usesStudentNotebook]);
  const memberNotebookQuestionNumberById = useMemo(() => {
    return new Map(
      memberNotebookRecords.map((item, index) => [item.id, index + 1]),
    );
  }, [memberNotebookRecords]);
  const notebookTopicSummaries = useMemo(() => {
    return buildWrongQuestionTopicSummaries(memberNotebookRecords.filter(isPrimarySchoolWrongQuestionRecord));
  }, [memberNotebookRecords]);
  const showNotebookTopicCategory = notebookTopicSummaries.length > 1;
  const displayedNotebookRecords = useMemo(() => {
    const filtered = notebookMasteryFilter === 'mastered'
      ? memberNotebookRecords.filter((item) => item.isMastered === true)
      : notebookMasteryFilter === 'pending'
        ? memberNotebookRecords.filter((item) => item.isMastered !== true)
        : memberNotebookRecords;
    const topicFiltered = showNotebookTopicCategory
      ? filterWrongQuestionRecordsByTopic(filtered, notebookTopicFilter)
      : filtered;
    return [...topicFiltered].reverse();
  }, [memberNotebookRecords, notebookMasteryFilter, notebookTopicFilter, showNotebookTopicCategory]);
  const selectedNotebookStudentId = useMemo(() => {
    const matchedRecord = memberNotebookRecords.find((item) => typeof item.studentId === 'number' && item.studentId > 0);
    return matchedRecord?.studentId ?? null;
  }, [memberNotebookRecords]);
  const defaultPracticeRecordIds = useMemo(() => {
    const selectableRecords = memberNotebookRecords.filter((item) => canGenerateWrongQuestionPractice(item));
    return selectableRecords.length === 1 ? [selectableRecords[0].id] : [];
  }, [memberNotebookRecords]);
  const effectiveSelectedPracticeRecordIds = practiceSelectionTouched ? selectedPracticeRecordIds : defaultPracticeRecordIds;
  const selectedRecord = memberNotebookRecords.find((item) => item.id === selectedId) ?? null;
  const selectedRecordIsPrimarySchool = selectedRecord ? isPrimarySchoolWrongQuestionRecord(selectedRecord) : false;
  const selectedDraft = selectedRecord ? reviewDraftByRecordId[selectedRecord.id] ?? buildWrongQuestionReviewDraft(selectedRecord) : null;
  const selectedRecordConfirmationStatus = useMemo(() => {
    return normalizeWrongQuestionConfirmationStatus(selectedRecord);
  }, [selectedRecord]);
  const selectedRecordArchiveAssets = useMemo(() => {
    return selectedRecord?.linkedIngestionRun?.assets ?? [];
  }, [selectedRecord]);
  const selectedRecordArchiveOriginalAssets = useMemo(() => {
    return selectedRecordArchiveAssets.filter((item) => item.assetRole === 'original_upload');
  }, [selectedRecordArchiveAssets]);
  const selectedRecordArchiveTraceAssets = useMemo(() => {
    return selectedRecordArchiveAssets.filter((item) => item.assetRole !== 'original_upload');
  }, [selectedRecordArchiveAssets]);
  const selectedRecordGenerationMetadataEntries = useMemo(() => {
    return buildWrongQuestionGenerationMetadataEntries(selectedRecord?.generationMetadata);
  }, [selectedRecord?.generationMetadata]);
  const selectedRecordMasteryTracking = selectedRecord?.masteryTracking;
  const selectedRecordMasteryAssessment = selectedRecord?.masteryAssessment;
  const selectedRecordCanStartMasteryFollowup = useMemo(() => {
    return canStartWrongQuestionMasteryFollowup(selectedRecord);
  }, [selectedRecord]);
  const selectedRecordLatestPracticePreviewUrl = useMemo(() => {
    const sheetId = selectedRecordMasteryTracking?.latestPracticeSheetId;
    if (typeof sheetId !== 'number' || sheetId <= 0) {
      return '';
    }
    return buildWrongQuestionAuthedPath(`/api/wrong-question-practice-sheets/${sheetId}/pdf`);
  }, [selectedRecordMasteryTracking?.latestPracticeSheetId]);
  const selectedRecordLatestPracticeDownloadUrl = useMemo(() => {
    const sheetId = selectedRecordMasteryTracking?.latestPracticeSheetId;
    if (typeof sheetId !== 'number' || sheetId <= 0) {
      return '';
    }
    return buildWrongQuestionAuthedPath(`/api/wrong-question-practice-sheets/${sheetId}/pdf/download`);
  }, [selectedRecordMasteryTracking?.latestPracticeSheetId]);
  const selectedRecordReflectionSummary = selectedRecord?.reflectionSummary;
  const selectedRecordReflectionSummaryText = useMemo(() => {
    return selectedRecordReflectionSummary?.summaryText?.trim()
      || selectedRecord?.linkedChatSession?.summaryText?.trim()
      || '';
  }, [selectedRecord?.linkedChatSession?.summaryText, selectedRecordReflectionSummary?.summaryText]);
  const selectedRecordReflectionAnsweredStageLabels = useMemo(() => {
    return (selectedRecordReflectionSummary?.answeredStages ?? [])
      .map((stage) => WRONG_QUESTION_REFLECTION_STAGE_LABELS[stage] || stage)
      .filter(Boolean);
  }, [selectedRecordReflectionSummary?.answeredStages]);
  const selectedQuestionTextPreview = useMemo(() => {
    if (!selectedRecord || !selectedDraft || selectedRecord.isGeometry) {
      return null;
    }
    if (selectedRecord.source !== 'wechat_mp' && selectedRecord.source !== 'ai_chat') {
      return null;
    }

    return buildWrongQuestionLatexPreviewModel(selectedDraft.questionText ?? '');
  }, [selectedDraft, selectedRecord]);
  const finalErrorTypeOptions = useMemo(() => {
    return Array.from(new Set([
      ...WRONG_QUESTION_ERROR_TYPE_OPTIONS,
      selectedRecord?.analysis.errorType?.trim() ?? '',
      selectedDraft?.selectedErrorType?.trim() ?? '',
    ].filter(Boolean)));
  }, [selectedDraft?.selectedErrorType, selectedRecord?.analysis.errorType]);
  const topicCategoryOptions = useMemo(() => {
    if (!selectedRecordIsPrimarySchool) {
      return [];
    }
    return Array.from(new Set([
      ...WRONG_QUESTION_TOPIC_CATEGORY_OPTIONS,
      selectedRecord?.topicCategory?.trim() ?? '',
      selectedDraft?.topicCategory?.trim() ?? '',
    ].filter(Boolean)));
  }, [selectedDraft?.topicCategory, selectedRecord?.topicCategory, selectedRecordIsPrimarySchool]);
  const practicePackTargetRecords = useMemo(() => {
    return records.filter((record) => !activeWeeklyFollowupClassId || record.classId === activeWeeklyFollowupClassId);
  }, [activeWeeklyFollowupClassId, records]);
  const practicePackTargetOptions = useMemo(() => {
    if (practicePackMode === 'topic') {
      return buildUniquePracticePackTargets([
        ...WRONG_QUESTION_TOPIC_CATEGORY_OPTIONS.filter((item) => item !== '未分类'),
        ...practicePackTargetRecords.map((record) => record.topicCategory ?? ''),
        ...practicePackTargetRecords.map((record) => record.analysis.questionCategory ?? ''),
      ]);
    }

    return buildUniquePracticePackTargets([
      ...PRACTICE_PACK_REASON_TARGET_OPTIONS,
      ...practicePackTargetRecords.map((record) => record.primaryErrorType ?? ''),
      ...practicePackTargetRecords.map((record) => record.analysis.errorType ?? ''),
      ...practicePackTargetRecords.map((record) => {
        const causeNote = record.causeNote?.trim() ?? '';
        return causeNote.length <= 20 ? causeNote : '';
      }),
    ]);
  }, [practicePackMode, practicePackTargetRecords]);
  const wrongQuestionChatLastAssistantMessage = useMemo(() => {
    if (!wrongQuestionChatSession) {
      return null;
    }
    return [...wrongQuestionChatSession.messages].reverse().find((item) => item.role === 'assistant') ?? null;
  }, [wrongQuestionChatSession]);
  const wrongQuestionChatCurrentStageLabel = useMemo(() => {
    const stage = wrongQuestionChatSession?.currentStage?.trim() || 'ask_why_wrong';
    return WRONG_QUESTION_CHAT_STAGE_LABELS[stage] || '对话中';
  }, [wrongQuestionChatSession]);
  const wrongQuestionChatAssetPreviews = useMemo(() => {
    if (!wrongQuestionChatRun) {
      return [];
    }
    return wrongQuestionChatRun.assets
      .map((item) => item.fileUrl.trim())
      .filter(Boolean);
  }, [wrongQuestionChatRun]);
  const wrongQuestionChatArchivePreviewVisible = useMemo(() => {
    if (!wrongQuestionChatSession || wrongQuestionChatSession.status === 'archived') {
      return false;
    }
    return Boolean(
      wrongQuestionChatDraft.questionText.trim()
      || wrongQuestionChatDraft.topicCategory.trim()
      || wrongQuestionChatDraft.knowledgeTagsText.trim()
      || wrongQuestionChatSession.summaryText.trim()
      || wrongQuestionChatAssetPreviews.length > 0
      || wrongQuestionChatLocalPreviews.length > 0,
    );
  }, [
    wrongQuestionChatAssetPreviews.length,
    wrongQuestionChatDraft.knowledgeTagsText,
    wrongQuestionChatDraft.questionText,
    wrongQuestionChatDraft.topicCategory,
    wrongQuestionChatLocalPreviews.length,
    wrongQuestionChatSession,
  ]);
  const pendingTeacherConfirmationCount = useMemo(() => {
    return records.filter((record) => normalizeWrongQuestionConfirmationStatus(record) === 'pending').length;
  }, [records]);
  const returnedTeacherConfirmationCount = useMemo(() => {
    return records.filter((record) => normalizeWrongQuestionConfirmationStatus(record) === 'returned').length;
  }, [records]);
  const wrongQuestionChatKnowledgeTagList = useMemo(() => {
    return wrongQuestionChatDraft.knowledgeTagsText
      .split(/\n|,/)
      .map((item) => item.trim())
      .filter(Boolean);
  }, [wrongQuestionChatDraft.knowledgeTagsText]);
  const wrongQuestionChatPredictedConfirmationReasons = useMemo(() => {
    const reasons: string[] = [];
    const hasPreviewImage = wrongQuestionChatAssetPreviews.length > 0 || wrongQuestionChatLocalPreviews.length > 0;
    if (!hasPreviewImage) {
      reasons.push('missing_image_asset');
    }
    if (!wrongQuestionChatDraft.questionText.trim()) {
      reasons.push('missing_question_text');
    }
    if (wrongQuestionChatKnowledgeTagList.length === 0) {
      reasons.push('knowledge_tags_unconfirmed');
    }
    if (wrongQuestionChatSession && !wrongQuestionChatSession.summaryText.includes('卡点：')) {
      reasons.push('student_confused_step');
    }
    return reasons;
  }, [
    wrongQuestionChatAssetPreviews.length,
    wrongQuestionChatDraft.questionText,
    wrongQuestionChatKnowledgeTagList.length,
    wrongQuestionChatLocalPreviews.length,
    wrongQuestionChatSession,
  ]);
  const wrongQuestionChatConfirmationReasonLabels = useMemo(() => {
    const sourceReasons = wrongQuestionChatSession?.status === 'archived'
      ? (wrongQuestionChatSession.records[0]?.confirmationReasons ?? [])
      : wrongQuestionChatPredictedConfirmationReasons;
    return sourceReasons.map((reason) => WRONG_QUESTION_CHAT_CONFIRMATION_REASON_LABELS[reason] || reason);
  }, [wrongQuestionChatPredictedConfirmationReasons, wrongQuestionChatSession]);
  const wrongQuestionChatArchivedRecord = useMemo(() => {
    return wrongQuestionChatSession?.records[0] ?? null;
  }, [wrongQuestionChatSession]);
  const wrongQuestionChatArchivedRecordConfirmationStatus = useMemo(() => {
    return normalizeWrongQuestionConfirmationStatus(wrongQuestionChatArchivedRecord);
  }, [wrongQuestionChatArchivedRecord]);
  const wrongQuestionChatMode = useMemo(() => {
    if (!wrongQuestionChatSession?.metadataJson.trim()) {
      return 'archive';
    }
    try {
      const metadata = JSON.parse(wrongQuestionChatSession.metadataJson);
      if (typeof metadata !== 'object' || metadata === null || Array.isArray(metadata)) {
        return 'archive';
      }
      const entrypoint = String((metadata as { entrypoint?: unknown }).entrypoint || '').trim();
      if (entrypoint === 'wrong_question_chat_mastery_followup') {
        return 'mastery_followup';
      }
      if (entrypoint === 'wrong_question_chat_rework') {
        return 'rework';
      }
    } catch {
      return 'archive';
    }
    return 'archive';
  }, [wrongQuestionChatSession?.metadataJson]);
  const wrongQuestionChatIsMasteryFollowup = wrongQuestionChatMode === 'mastery_followup';

  const resetWrongQuestionChatState = useCallback(() => {
    setWrongQuestionChatRun(null);
    setWrongQuestionChatSession(null);
    setWrongQuestionChatDraft({
      questionText: '',
      topicCategory: '',
      knowledgeTagsText: '',
      followupOutcome: '',
      replyText: '',
    });
    setWrongQuestionChatFiles([]);
    setWrongQuestionChatLocalPreviews((current) => {
      current.forEach((item) => globalThis.URL?.revokeObjectURL?.(item.url));
      return [];
    });
    setWrongQuestionChatLoading(false);
    setWrongQuestionChatUploading(false);
    setWrongQuestionChatSending(false);
    setWrongQuestionChatUploadProgress(0);
    setWrongQuestionChatError('');
    setWrongQuestionChatNotice('');
  }, []);

  const hydrateWrongQuestionChatState = useCallback((session: WrongQuestionChatSession | null, run: WrongQuestionIngestionRun | null) => {
    setWrongQuestionChatSession(session);
    setWrongQuestionChatRun(run);
    const firstRecord = session?.records[0] ?? run?.records[0] ?? null;
    setWrongQuestionChatDraft((current) => ({
      questionText: firstRecord?.questionText?.trim() || current.questionText,
      topicCategory: firstRecord?.topicCategory?.trim() || current.topicCategory,
      knowledgeTagsText: firstRecord?.analysis.knowledgePoints?.join(', ') || current.knowledgeTagsText,
      followupOutcome: firstRecord?.masteryTracking?.latestFollowupOutcome?.trim() || '',
      replyText: '',
    }));
  }, []);

  const handleWrongQuestionChatFileChange = useCallback((fileList: FileList | null) => {
    const files = fileList ? Array.from(fileList).filter((item) => item.name) : [];
    setWrongQuestionChatFiles(files);
    setWrongQuestionChatLocalPreviews((current) => {
      current.forEach((item) => globalThis.URL?.revokeObjectURL?.(item.url));
      return files.map((file) => ({
        name: file.name,
        url: globalThis.URL?.createObjectURL?.(file) || '',
      }));
    });
    setWrongQuestionChatError('');
    setWrongQuestionChatNotice('');
  }, []);

  const loadLatestWrongQuestionChatSession = useCallback(async () => {
    if (pendingNotebookMasteryFollowupRecordIdRef.current) {
      return;
    }
    if (!activeNotebookClassId || !selectedNotebookStudentId || !selectedStudentName || notebookModalView !== 'questions') {
      resetWrongQuestionChatState();
      return;
    }
    const requestVersion = wrongQuestionChatRequestVersionRef.current + 1;
    wrongQuestionChatRequestVersionRef.current = requestVersion;
    setWrongQuestionChatLoading(true);
    setWrongQuestionChatError('');
    setWrongQuestionChatNotice('');
    try {
      const response = await apiFetch<{ items?: unknown[] }>(
        buildWrongQuestionIngestionListPath({
          source: 'ai_chat',
          classId: activeNotebookClassId,
          studentId: selectedNotebookStudentId,
          limit: 10,
        }),
      );
      if (requestVersion !== wrongQuestionChatRequestVersionRef.current) {
        return;
      }
      const runs = Array.isArray(response.items)
        ? response.items.map((item) => normalizeWrongQuestionIngestionRun(item))
        : [];
      const latestRun = runs.find((item) => item.chatSessionId) ?? null;
      if (!latestRun?.chatSessionId) {
        setWrongQuestionChatRun(null);
        setWrongQuestionChatSession(null);
        return;
      }
      const detail = await apiFetch<{ session?: unknown }>(buildWrongQuestionChatDetailPath(latestRun.chatSessionId));
      if (requestVersion !== wrongQuestionChatRequestVersionRef.current) {
        return;
      }
      const normalizedSession = detail.session ? normalizeWrongQuestionChatSession(detail.session) : null;
      hydrateWrongQuestionChatState(normalizedSession, latestRun);
      if (normalizedSession?.messages.length) {
        setWrongQuestionChatNotice(normalizedSession.status === 'archived' ? '已恢复最近一次错题归档记录。' : '已恢复最近一次错题对话。');
      }
    } catch (loadError) {
      if (requestVersion !== wrongQuestionChatRequestVersionRef.current) {
        return;
      }
      setWrongQuestionChatRun(null);
      setWrongQuestionChatSession(null);
      setWrongQuestionChatError(loadError instanceof Error ? loadError.message : '错题对话恢复失败');
    } finally {
      if (requestVersion === wrongQuestionChatRequestVersionRef.current) {
        setWrongQuestionChatLoading(false);
      }
    }
  }, [
    activeNotebookClassId,
    hydrateWrongQuestionChatState,
    notebookModalView,
    resetWrongQuestionChatState,
    selectedNotebookStudentId,
    selectedStudentName,
  ]);

  useEffect(() => {
    if (!showNotebookTopicCategory && notebookTopicFilter !== '全部') {
      setNotebookTopicFilter('全部');
    }
  }, [notebookTopicFilter, showNotebookTopicCategory]);

  useEffect(() => {
    setPracticePackTarget((currentTarget) => {
      const normalizedTarget = currentTarget.trim();
      if (normalizedTarget && practicePackTargetOptions.includes(normalizedTarget)) {
        return normalizedTarget;
      }
      return practicePackTargetOptions[0] ?? '';
    });
  }, [practicePackTargetOptions]);

  const updateDraftDirtyState = useCallback((recordId: string, isDirty: boolean) => {
    reviewDraftDirtyByRecordIdRef.current = {
      ...reviewDraftDirtyByRecordIdRef.current,
      [recordId]: isDirty,
    };

    setReviewDraftDirtyByRecordId((current) => {
      if (current[recordId] === isDirty) {
        return current;
      }

      return {
        ...current,
        [recordId]: isDirty,
      };
    });
  }, []);

  const loadList = useCallback(async (nextFilters: WrongQuestionFilters) => {
    const requestVersion = requestVersionRef.current + 1;
    requestVersionRef.current = requestVersion;
    setLoading(true);
    setError('');
    try {
      const response = await apiFetch<WrongQuestionListApiResponse>(`/api/wrong-questions${buildWrongQuestionQuery(nextFilters)}`);
      if (requestVersion !== requestVersionRef.current) {
        return;
      }

      const normalized = normalizeWrongQuestionListResponse(response);
      const nextRecords = normalized.items;
      setRecords(nextRecords);
      setServerSummary(normalized.summary);
      setSelectedId((current) => {
        if (current && nextRecords.some((item) => item.id === current)) {
          return current;
        }
        return nextRecords[0]?.id ?? null;
      });
    } catch (loadError) {
      if (requestVersion !== requestVersionRef.current) {
        return;
      }

      setError(loadError instanceof Error ? loadError.message : '智能错题列表加载失败');
      setRecords([]);
      setServerSummary(null);
      setSelectedId(null);
    } finally {
      if (requestVersion === requestVersionRef.current) {
        setLoading(false);
      }
    }
  }, []);

  const loadPracticeHistory = useCallback(async (studentId: number) => {
    const requestVersion = practiceHistoryRequestVersionRef.current + 1;
    practiceHistoryRequestVersionRef.current = requestVersion;
    setPracticeHistoryLoading(true);
    setPracticeHistoryError('');

    try {
      const response = await apiFetch<WrongQuestionPracticeSheetListApiResponse>(buildWrongQuestionPracticeSheetsPath(studentId));
      if (requestVersion !== practiceHistoryRequestVersionRef.current) {
        return;
      }

      setPracticeSheets(normalizeWrongQuestionPracticeSheetListResponse(response));
    } catch (loadError) {
      if (requestVersion !== practiceHistoryRequestVersionRef.current) {
        return;
      }

      setPracticeSheets([]);
      setPracticeHistoryError(loadError instanceof Error ? loadError.message : '错题练习记录加载失败');
    } finally {
      if (requestVersion === practiceHistoryRequestVersionRef.current) {
        setPracticeHistoryLoading(false);
      }
    }
  }, []);

  const handleStartWrongQuestionChat = useCallback(async () => {
    if (!activeNotebookClassId || !selectedNotebookStudentId) {
      setWrongQuestionChatError('请先选择学生。');
      setWrongQuestionChatNotice('');
      return;
    }
    if (wrongQuestionChatFiles.length === 0) {
      setWrongQuestionChatError('请先上传至少一张错题图片。');
      setWrongQuestionChatNotice('');
      return;
    }

    const sessionId = buildWrongQuestionChatSessionId();
    setWrongQuestionChatUploading(true);
    setWrongQuestionChatUploadProgress(0);
    setWrongQuestionChatError('');
    setWrongQuestionChatNotice('');
    try {
      const created = await apiFetch<{ run: unknown }>(buildWrongQuestionIngestionCreatePath(), {
        method: 'POST',
        body: JSON.stringify({
          source: 'ai_chat',
          class_id: activeNotebookClassId,
          student_id: selectedNotebookStudentId,
          chat_session_id: sessionId,
          original_filename: wrongQuestionChatFiles[0]?.name ?? 'wrong-question.png',
          mime_type: wrongQuestionChatFiles[0]?.type || 'image/png',
        }),
      });
      const createdRun = normalizeWrongQuestionIngestionRun(created.run);
      const uploadForm = new FormData();
      wrongQuestionChatFiles.forEach((file) => uploadForm.append('files', file));
      const uploaded = await apiUploadFormWithProgress<{ run: unknown }>(
        buildWrongQuestionIngestionAssetUploadPath(createdRun.id),
        uploadForm,
        setWrongQuestionChatUploadProgress,
      );
      const uploadedRun = normalizeWrongQuestionIngestionRun(uploaded.run);
      const opening = await apiFetch<{ session?: unknown }>(buildWrongQuestionChatStreamPath(sessionId), {
        method: 'POST',
        body: JSON.stringify({
          ingestion_run_id: uploadedRun.id,
          class_id: activeNotebookClassId,
          student_id: selectedNotebookStudentId,
        }),
      });
      const openedSession = opening.session ? normalizeWrongQuestionChatSession(opening.session) : null;
      hydrateWrongQuestionChatState(openedSession, uploadedRun);
      setWrongQuestionChatNotice('图片已上传，先说说你觉得这题错在哪里。');
    } catch (startError) {
      setWrongQuestionChatError(startError instanceof Error ? startError.message : '错题对话创建失败');
    } finally {
      setWrongQuestionChatUploading(false);
    }
  }, [
    activeNotebookClassId,
    hydrateWrongQuestionChatState,
    selectedNotebookStudentId,
    wrongQuestionChatFiles,
  ]);

  const handleWrongQuestionChatDraftChange = useCallback((key: keyof WrongQuestionChatDraftState, value: string) => {
    setWrongQuestionChatDraft((current) => ({
      ...current,
      [key]: value,
    }));
  }, []);

  const handleSendWrongQuestionChatMessage = useCallback(async (overrideMessage?: string) => {
    if (!wrongQuestionChatSession?.id) {
      setWrongQuestionChatError('请先上传错题图片并开启对话。');
      setWrongQuestionChatNotice('');
      return;
    }
    const message = (overrideMessage ?? wrongQuestionChatDraft.replyText).trim();
    if (!message) {
      setWrongQuestionChatError('请先输入你的回答。');
      setWrongQuestionChatNotice('');
      return;
    }
    if (
      wrongQuestionChatIsMasteryFollowup
      && wrongQuestionChatSession.currentStage === 'ask_help_mode'
      && !wrongQuestionChatDraft.followupOutcome.trim()
    ) {
      setWrongQuestionChatError('归档这轮掌握追问前，请先选择追问结果。');
      setWrongQuestionChatNotice('');
      return;
    }
    setWrongQuestionChatSending(true);
    setWrongQuestionChatError('');
    setWrongQuestionChatNotice('');
    try {
      const response = await apiFetch<{
        session?: unknown;
        archive?: { record?: unknown; created?: boolean; idempotent_reuse?: boolean } | null;
      }>(buildWrongQuestionChatStreamPath(wrongQuestionChatSession.id), {
        method: 'POST',
        body: JSON.stringify({
          message,
          archive_payload: {
            question_text: wrongQuestionChatDraft.questionText.trim(),
            topic_category: wrongQuestionChatDraft.topicCategory.trim(),
            knowledge_tags_json: wrongQuestionChatDraft.knowledgeTagsText
              .split(/\n|,/)
              .map((item) => item.trim())
              .filter(Boolean),
            mastery_followup_outcome: wrongQuestionChatDraft.followupOutcome.trim(),
          },
        }),
      });
      const nextSession = response.session ? normalizeWrongQuestionChatSession(response.session) : wrongQuestionChatSession;
      hydrateWrongQuestionChatState(nextSession, wrongQuestionChatRun);
      setWrongQuestionChatDraft((current) => ({
        ...current,
        replyText: '',
      }));

      const archivedRecord = response.archive?.record ? normalizeWrongQuestionRecord(response.archive.record) : null;
      if (archivedRecord) {
        setRecords((current) => {
          const exists = current.some((item) => item.id === archivedRecord.id);
          return exists
            ? current.map((item) => item.id === archivedRecord.id ? archivedRecord : item)
            : [...current, archivedRecord];
        });
        setSelectedId(archivedRecord.id);
        setWrongQuestionChatNotice(response.archive?.created ? '已归档到错题库，可以继续在右侧查看详情。' : '这次归档已经存在，已恢复到已有记录。');
      }
    } catch (sendError) {
      setWrongQuestionChatError(sendError instanceof Error ? sendError.message : '错题对话发送失败');
    } finally {
      setWrongQuestionChatSending(false);
    }
  }, [
    hydrateWrongQuestionChatState,
    wrongQuestionChatDraft.knowledgeTagsText,
    wrongQuestionChatDraft.followupOutcome,
    wrongQuestionChatDraft.questionText,
    wrongQuestionChatDraft.replyText,
    wrongQuestionChatDraft.topicCategory,
    wrongQuestionChatIsMasteryFollowup,
    wrongQuestionChatRun,
    wrongQuestionChatSession,
  ]);

  const handleReopenWrongQuestionChat = useCallback(async () => {
    if (!wrongQuestionChatArchivedRecord?.id) {
      setWrongQuestionChatError('当前没有可继续补充的归档记录。');
      setWrongQuestionChatNotice('');
      return;
    }
    setWrongQuestionChatSending(true);
    setWrongQuestionChatError('');
    setWrongQuestionChatNotice('');
    try {
      const response = await apiFetch<{ session?: unknown; run?: unknown }>(
        buildWrongQuestionChatReopenPath(wrongQuestionChatArchivedRecord.id),
        {
          method: 'POST',
          body: JSON.stringify({}),
        },
      );
      const nextSession = response.session ? normalizeWrongQuestionChatSession(response.session) : null;
      const nextRun = response.run ? normalizeWrongQuestionIngestionRun(response.run) : wrongQuestionChatRun;
      hydrateWrongQuestionChatState(nextSession, nextRun);
      setWrongQuestionChatNotice('已按老师意见重新开启这条对话，继续补充后会覆盖原归档。');
    } catch (reopenError) {
      setWrongQuestionChatError(reopenError instanceof Error ? reopenError.message : '重新开启错题对话失败');
    } finally {
      setWrongQuestionChatSending(false);
    }
  }, [
    hydrateWrongQuestionChatState,
    wrongQuestionChatArchivedRecord,
    wrongQuestionChatRun,
  ]);

  const openWrongQuestionRecordInNotebook = useCallback((
    record: WrongQuestionRecord,
    options: {
      classId?: number | null;
      studentName?: string;
      notice?: string;
    } = {},
  ) => {
    const targetStudentName = options.studentName?.trim() || record.studentName.trim();
    if (!targetStudentName) {
      setWeeklyFollowupError('当前来源错题缺少学生信息，暂时无法打开。');
      setWeeklyFollowupNotice('');
      return false;
    }
    if (!hasStaffScope) {
      const nextClassId = typeof options.classId === 'number' && options.classId > 0
        ? options.classId
        : typeof record.classId === 'number' && record.classId > 0
          ? record.classId
          : activeWeeklyFollowupClassId;
      if (nextClassId) {
        setSelectedClassId(nextClassId);
      }
    }
    setRecords((current) => {
      const exists = current.some((item) => item.id === record.id);
      return exists
        ? current.map((item) => item.id === record.id ? record : item)
        : [...current, record];
    });
    setSelectedStudentName(targetStudentName);
    setSelectedId(record.id);
    setNotebookModalView('questions');
    setSelectedPracticeRecordIds([]);
    setPracticeSelectionTouched(false);
    setWeeklyFollowupError('');
    setWeeklyFollowupNotice(options.notice ?? '已跳转到来源错题。');
    return true;
  }, [
    activeWeeklyFollowupClassId,
    hasStaffScope,
    setRecords,
  ]);

  const handleStartWrongQuestionMasteryFollowup = useCallback(async (recordOverride?: WrongQuestionRecord | null) => {
    const targetRecord = recordOverride ?? selectedRecord;
    if (!targetRecord?.id) {
      setWrongQuestionChatError('当前没有可继续追问的错题记录。');
      setWrongQuestionChatNotice('');
      return;
    }
    setWrongQuestionChatSending(true);
    setWrongQuestionChatError('');
    setWrongQuestionChatNotice('');
    try {
      const response = await apiFetch<{ session?: unknown; run?: unknown }>(
        buildWrongQuestionChatFollowupPath(targetRecord.id),
        {
          method: 'POST',
          body: JSON.stringify({}),
        },
      );
      const nextSession = response.session ? normalizeWrongQuestionChatSession(response.session) : null;
      const nextRun = response.run ? normalizeWrongQuestionIngestionRun(response.run) : wrongQuestionChatRun;
      hydrateWrongQuestionChatState(nextSession, nextRun);
      setWrongQuestionChatNotice('已开启这道题的掌握追问，后续归档会继续覆盖同一条错题记录。');
    } catch (followupError) {
      setWrongQuestionChatError(followupError instanceof Error ? followupError.message : '开启掌握追问失败');
    } finally {
      setWrongQuestionChatSending(false);
    }
  }, [
    hydrateWrongQuestionChatState,
    selectedRecord,
    wrongQuestionChatRun,
  ]);
  const scheduleNotebookMasteryFollowupStart = useCallback((record: WrongQuestionRecord) => {
    pendingNotebookMasteryFollowupRecordIdRef.current = record.id;
    globalThis.setTimeout(() => {
      void (async () => {
        try {
          await handleStartWrongQuestionMasteryFollowup(record);
        } finally {
          if (pendingNotebookMasteryFollowupRecordIdRef.current === record.id) {
            pendingNotebookMasteryFollowupRecordIdRef.current = '';
          }
        }
      })();
    }, 0);
  }, [handleStartWrongQuestionMasteryFollowup]);

  const resetWeeklyFollowupContext = useCallback(() => {
    weeklyFollowupRequestVersionRef.current += 1;
    practicePackRequestVersionRef.current += 1;
    setWeeklyFollowupItems([]);
    setWeeklyFollowupNotice('');
    setWeeklyFollowupError('');
    setWeeklyFollowupLoading(false);
    setGeneratingWeeklyFollowupStudentId(null);
    setPracticePackJobs([]);
    setPracticePackGenerating(false);
  }, []);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const [classItems, userItems] = await Promise.all([
          apiFetch<Array<{ id: number; name: string; subject?: string; teacher_user_id?: number | null }>>('/api/classes'),
          hasStaffScope ? apiFetch<Array<{ id: number; name: string }>>('/api/admin/users') : Promise.resolve([]),
        ]);

        if (!active) {
          return;
        }

        setClassOptions(classItems.map((item) => ({
          id: item.id,
          name: item.name,
          subject: item.subject?.trim() ?? '',
          teacherUserId: typeof item.teacher_user_id === 'number' ? item.teacher_user_id : null,
        })));
        setTeacherOptions(userItems.map((item) => ({
          id: item.id,
          name: item.name,
        })));
      } catch (loadOptionsError) {
        console.error(loadOptionsError);
      }
    })();

    return () => {
      active = false;
    };
  }, [hasStaffScope]);

  useEffect(() => {
    if (!canViewWeeklyActivitySummary) {
      setOrganizationOptions([]);
      return;
    }

    let active = true;

    void (async () => {
      try {
        const response = await apiFetch<{ items?: Array<{ id: number; name: string }> }>('/api/admin/organizations');
        if (!active) {
          return;
        }

        setOrganizationOptions((response.items ?? []).map((item) => ({
          id: item.id,
          name: item.name,
        })));
      } catch (loadOrganizationsError) {
        console.error(loadOrganizationsError);
        if (active) {
          setOrganizationOptions([]);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [canViewWeeklyActivitySummary]);

  useEffect(() => {
    void loadList(initialFilters);
  }, [loadList]);

  useEffect(() => {
    weeklyActivityRequestVersionRef.current += 1;
    setWeeklyActivitySummary(null);
    setWeeklyActivityError('');
    setWeeklyActivityNotice('');
    setWeeklyActivityLoading(false);
  }, [weeklyActivityWeekStart, weeklyActivityOrganizationId]);

  useEffect(() => {
    resetWeeklyFollowupContext();
  }, [activeWeeklyFollowupClassId, resetWeeklyFollowupContext, weeklyFollowupWeekStart]);

  useEffect(() => {
    if (!usesStudentNotebook || hasStaffScope) {
      return;
    }

    setSelectedClassId((current) => current && classOptions.some((item) => item.id === current) ? current : null);
  }, [classOptions, hasStaffScope, usesStudentNotebook]);

  useEffect(() => {
    if (!usesStudentNotebook || !selectedStudentName) {
      return;
    }

    if (!memberNotebookSummaries.some((item) => item.studentName === selectedStudentName)) {
      setSelectedStudentName(null);
      setSelectedId(null);
    }
  }, [memberNotebookSummaries, selectedStudentName, usesStudentNotebook]);

  useEffect(() => {
    setNotebookModalView('questions');
    setPracticeActionError('');
    setPracticeActionNotice('');
    resetWrongQuestionChatState();
  }, [resetWrongQuestionChatState, selectedStudentName]);

  useEffect(() => {
    void loadLatestWrongQuestionChatSession();
  }, [loadLatestWrongQuestionChatSession]);

  useEffect(() => {
    return () => {
      wrongQuestionChatLocalPreviews.forEach((item) => globalThis.URL?.revokeObjectURL?.(item.url));
    };
  }, [wrongQuestionChatLocalPreviews]);

  useEffect(() => {
    if (!selectedRecord) {
      setDetailError('');
      setSaveError('');
      return;
    }

    if (reviewDraftDirtyByRecordId[selectedRecord.id] === undefined) {
      updateDraftDirtyState(selectedRecord.id, false);
    }

    setReviewDraftByRecordId((current) => {
      if (current[selectedRecord.id]) {
        return current;
      }

      return {
        ...current,
        [selectedRecord.id]: buildWrongQuestionReviewDraft(selectedRecord),
      };
    });
  }, [reviewDraftDirtyByRecordId, selectedRecord, updateDraftDirtyState]);

  useEffect(() => {
    if (!selectedId) {
      return;
    }

    const selectedRecordForDetail = recordsRef.current.find((item) => item.id === selectedId);
    if (!selectedRecordForDetail) {
      return;
    }

    const requestVersion = detailRequestVersionRef.current + 1;
    detailRequestVersionRef.current = requestVersion;
    setDetailLoading(true);
    setDetailError('');

    void (async () => {
      try {
        const response = await apiFetch<WrongQuestionRecord>(
          buildWrongQuestionDetailPath(selectedId, selectedRecordForDetail?.roomId),
        );
        if (requestVersion !== detailRequestVersionRef.current) {
          return;
        }

        const detailRecord = normalizeWrongQuestionRecord(response);
        const hasLocalEdits = Boolean(reviewDraftDirtyByRecordIdRef.current[detailRecord.id]);
        setRecords((current) => current.map((item) => item.id === detailRecord.id ? detailRecord : item));
        setServerSummary(null);
        setReviewDraftByRecordId((current) => {
          return {
            ...current,
            [detailRecord.id]: hydrateWrongQuestionReviewDraftFromDetail(detailRecord, current[detailRecord.id], hasLocalEdits),
          };
        });
        if (!hasLocalEdits) {
          updateDraftDirtyState(detailRecord.id, false);
        }
      } catch (loadDetailError) {
        if (requestVersion !== detailRequestVersionRef.current) {
          return;
        }

        setDetailError(loadDetailError instanceof Error ? loadDetailError.message : '智能错题详情加载失败');
      } finally {
        if (requestVersion === detailRequestVersionRef.current) {
          setDetailLoading(false);
        }
      }
    })();
  }, [selectedId]);

  useEffect(() => {
    setSelectedPracticeRecordIds((current) => current.filter((recordId) => {
      const matchedRecord = memberNotebookRecords.find((item) => item.id === recordId);
      return Boolean(matchedRecord && canGenerateWrongQuestionPractice(matchedRecord));
    }));
  }, [memberNotebookRecords]);

  useEffect(() => {
    if (!selectedStudentName || !selectedNotebookStudentId) {
      practiceHistoryRequestVersionRef.current += 1;
      setPracticeSheets([]);
      setPracticeHistoryLoading(false);
      setPracticeHistoryError('');
      return;
    }

    void loadPracticeHistory(selectedNotebookStudentId);
  }, [loadPracticeHistory, selectedNotebookStudentId, selectedStudentName]);

  useEffect(() => {
    if (!hasStaffScope) {
      return;
    }

    setFilters((current) => {
      const normalizedClassName = current.className?.trim() ?? '';
      if (!normalizedClassName) {
        return current;
      }

      if (visibleClassOptions.some((item) => item.name === normalizedClassName)) {
        return current;
      }

      return {
        ...current,
        className: '',
        studentName: '',
      };
    });
  }, [hasStaffScope, visibleClassOptions]);

  useEffect(() => {
    if (!hasStaffScope) {
      return;
    }

    setFilters((current) => {
      const normalizedSubject = current.subject?.trim() ?? '';
      if (!normalizedSubject || subjectOptions.includes(normalizedSubject)) {
        return current;
      }

      return {
        ...current,
        subject: '',
      };
    });
  }, [hasStaffScope, subjectOptions]);

  useEffect(() => {
    if (!hasStaffScope) {
      return;
    }

    if (!selectedStaffClassOption) {
      setStudentOptions([]);
      return;
    }

    let active = true;

    void (async () => {
      try {
        const response = await apiFetch<{ students?: Array<{ id: number; name: string }> }>(`/api/classes/${selectedStaffClassOption.id}/students`);
        if (!active) {
          return;
        }

        setStudentOptions(
          Array.isArray(response.students)
            ? response.students.map((item) => ({
              id: item.id,
              name: String(item.name ?? '').trim(),
            })).filter((item) => item.name)
            : [],
        );
      } catch (loadStudentsError) {
        if (!active) {
          return;
        }

        console.error(loadStudentsError);
        setStudentOptions([]);
      }
    })();

    return () => {
      active = false;
    };
  }, [hasStaffScope, selectedStaffClassOption]);

  useEffect(() => {
    if (!hasStaffScope || !selectedStaffClassOption) {
      return;
    }

    setFilters((current) => {
      const normalizedStudentName = current.studentName?.trim() ?? '';
      if (!normalizedStudentName || studentOptions.some((item) => item.name === normalizedStudentName)) {
        return current;
      }

      return {
        ...current,
        studentName: '',
      };
    });
  }, [hasStaffScope, selectedStaffClassOption, studentOptions]);

  const handleFilterChange = <K extends keyof WrongQuestionFilters>(key: K, value: WrongQuestionFilters[K]) => {
    setFilters((current) => ({
      ...current,
      studentName: key === 'className' ? '' : current.studentName,
      [key]: value,
    }));
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void loadList(filters);
  };

  const handleDraftChange = <K extends keyof WrongQuestionReviewDraft>(key: K, value: WrongQuestionReviewDraft[K]) => {
    if (!selectedRecord) {
      return;
    }

    const nextDraft = {
      ...(reviewDraftByRecordIdRef.current[selectedRecord.id] ?? buildWrongQuestionReviewDraft(selectedRecord)),
      [key]: value,
    };
    reviewDraftByRecordIdRef.current = {
      ...reviewDraftByRecordIdRef.current,
      [selectedRecord.id]: nextDraft,
    };

    setReviewDraftByRecordId((current) => ({
      ...current,
      [selectedRecord.id]: nextDraft,
    }));
    updateDraftDirtyState(selectedRecord.id, true);
  };

  const handleSaveReview = async (action: 'save' | 'edit_then_confirm' | 'return_for_rework' = 'save') => {
    if (!selectedRecord) {
      return;
    }

    const latestDraft = reviewDraftByRecordIdRef.current[selectedRecord.id] ?? buildWrongQuestionReviewDraft(selectedRecord);

    setSavingReview(true);
    setSaveError('');

    try {
      const payload = buildWrongQuestionReviewPayload(latestDraft);
      if (action === 'edit_then_confirm') {
        payload.needs_teacher_confirmation = false;
        payload.confirmation_reasons_json = [];
        payload.confirmation_action = action;
      } else if (action === 'return_for_rework') {
        payload.needs_teacher_confirmation = true;
        payload.confirmation_reasons_json = payload.confirmation_reasons_json?.length
          ? payload.confirmation_reasons_json
          : (selectedRecord.confirmationReasons ?? []);
        payload.confirmation_action = action;
      }
      const response = await apiFetch<unknown>(buildWrongQuestionReviewPath(selectedRecord.id, selectedRecord.roomId), {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      let nextRecord = resolveSavedWrongQuestionRecord(
        selectedRecord,
        payload,
        extractSavedWrongQuestionResponseRecord(response),
      );
      const currentTopicCategory = (selectedRecord.topicCategory || selectedRecord.analysis.topicCategory || '未分类').trim() || '未分类';
      const nextTopicCategory = payload.topicCategory || '未分类';
      if (selectedRecord.source === 'wechat_mp' && selectedRecordIsPrimarySchool && nextTopicCategory !== currentTopicCategory) {
        const topicResponse = await apiFetch<unknown>(`/api/wrong-questions/${encodeURIComponent(selectedRecord.id)}/topic-category`, {
          method: 'PUT',
          body: JSON.stringify({ topic_category: nextTopicCategory }),
        });
        nextRecord = resolveSavedWrongQuestionRecord(
          nextRecord,
          payload,
          extractSavedWrongQuestionResponseRecord(topicResponse),
        );
      }

      setRecords((current) => current.map((item) => item.id === selectedRecord.id ? nextRecord : item));
      setServerSummary(null);
      setReviewDraftByRecordId((current) => ({
        ...current,
        [selectedRecord.id]: buildWrongQuestionReviewDraft(nextRecord),
      }));
      updateDraftDirtyState(selectedRecord.id, false);
    } catch (saveReviewError) {
      setSaveError(saveReviewError instanceof Error ? saveReviewError.message : '智能错题保存失败');
    } finally {
      setSavingReview(false);
    }
  };

  const handleDeleteRecord = async () => {
    if (!selectedRecord || selectedRecord.source !== 'wechat_mp') {
      return;
    }

    if (!globalThis.window?.confirm?.('确定删除这道错题吗？删除后会同步更新该学生错题库 PDF。')) {
      return;
    }

    setSaveError('');

    try {
      const selectedIndex = memberNotebookRecords.findIndex((item) => item.id === selectedRecord.id);
      const nextSelectedRecord = selectedIndex >= 0
        ? memberNotebookRecords[selectedIndex + 1] ?? memberNotebookRecords[selectedIndex - 1] ?? null
        : null;

      await apiFetch(`/api/wrong-questions/${encodeURIComponent(selectedRecord.id)}`, {
        method: 'DELETE',
      });

      setRecords((current) => current.filter((item) => item.id !== selectedRecord.id));
      setServerSummary(null);
      setDetailError('');
      setSelectedId(nextSelectedRecord?.id ?? null);
      setReviewDraftByRecordId((current) => {
        const next = { ...current };
        delete next[selectedRecord.id];
        return next;
      });
      setReviewDraftDirtyByRecordId((current) => {
        const next = { ...current };
        delete next[selectedRecord.id];
        return next;
      });
      reviewDraftByRecordIdRef.current = Object.fromEntries(
        Object.entries(reviewDraftByRecordIdRef.current).filter(([recordId]) => recordId !== selectedRecord.id),
      );
      reviewDraftDirtyByRecordIdRef.current = Object.fromEntries(
        Object.entries(reviewDraftDirtyByRecordIdRef.current).filter(([recordId]) => recordId !== selectedRecord.id),
      );
    } catch (deleteError) {
      setSaveError(deleteError instanceof Error ? deleteError.message : '删除错题失败');
    }
  };

  const handleRefreshStudentLibraryPdf = async () => {
    if (!selectedRecord || selectedRecord.source !== 'wechat_mp' || !selectedRecord.studentId) {
      return;
    }

    setRefreshingLibraryPdf(true);
    setSaveError('');
    setPdfRefreshNotice('');

    try {
      const response = await apiFetch<{
        pdf_url?: string;
        student_library_pdf_path?: string;
      }>(`/api/wrong-question-student-libraries/${encodeURIComponent(String(selectedRecord.studentId))}/refresh`, {
        method: 'POST',
      });
      const nextPdfPath = String(response.pdf_url || response.student_library_pdf_path || selectedRecord.studentLibraryPdfPath || '').trim();
      if (nextPdfPath) {
        setRecords((current) => current.map((item) => (
          item.studentId === selectedRecord.studentId
            ? { ...item, studentLibraryPdfPath: nextPdfPath }
            : item
        )));
      }
      setPdfRefreshNotice('PDF 已重新生成。');
    } catch (refreshError) {
      setSaveError(refreshError instanceof Error ? refreshError.message : '重新生成 PDF 失败');
    } finally {
      setRefreshingLibraryPdf(false);
    }
  };

  const handlePracticeRecordCheckedChange = (recordId: string, checked: boolean) => {
    setPracticeSelectionTouched(true);
    setSelectedPracticeRecordIds((current) => {
      if (checked) {
        return current.includes(recordId) ? current : [...current, recordId];
      }

      return current.filter((item) => item !== recordId);
    });
  };

  const handleCreatePracticeSheet = async () => {
    if (!selectedNotebookStudentId || effectiveSelectedPracticeRecordIds.length === 0) {
      return;
    }

    setCreatingPractice(true);
    setPracticeActionError('');
    setPracticeActionNotice('');

    try {
      await apiFetch('/api/wrong-question-practice-sheets', {
        method: 'POST',
        body: JSON.stringify({
          student_id: selectedNotebookStudentId,
          wrong_question_ids: effectiveSelectedPracticeRecordIds,
        }),
      });
      setSelectedPracticeRecordIds([]);
      setPracticeSelectionTouched(false);
      setNotebookModalView('practice_history');
      setPracticeActionNotice('已提交错题练习生成任务，可在错题练习记录里查看 PDF。');
      await loadPracticeHistory(selectedNotebookStudentId);
    } catch (createError) {
      setPracticeActionError(createError instanceof Error ? createError.message : '错题练习生成失败');
    } finally {
      setCreatingPractice(false);
    }
  };

  const handleDeletePracticeSheet = async (sheet: WrongQuestionPracticeSheetSummary) => {
    if (!globalThis.window?.confirm?.('确定删除这份错题练习吗？删除后将无法再预览或下载这份 PDF。')) {
      return;
    }

    setPracticeActionError('');
    setPracticeActionNotice('');

    try {
      await apiFetch(`/api/wrong-question-practice-sheets/${encodeURIComponent(String(sheet.id))}`, {
        method: 'DELETE',
      });
      setPracticeSheets((current) => current.filter((item) => item.id !== sheet.id));
      setPracticeActionNotice('已删除这份错题练习。');
    } catch (deleteError) {
      setPracticeActionError(deleteError instanceof Error ? deleteError.message : '删除错题练习失败');
    }
  };

  const handleLoadWeeklyActivitySummary = async () => {
    const requestVersion = weeklyActivityRequestVersionRef.current + 1;
    weeklyActivityRequestVersionRef.current = requestVersion;
    setWeeklyActivityLoading(true);
    setWeeklyActivityError('');
    setWeeklyActivityNotice('');

    try {
      const response = await apiFetch<unknown>(
        buildWeeklyWrongQuestionActivitySummaryPath(weeklyActivityWeekStart, weeklyActivityOrganizationId),
      );
      const normalized = normalizeWeeklyWrongQuestionActivitySummaryResponse(response);
      const itemCount = normalized.classItems.length + normalized.teacherItems.length + normalized.studentItems.length;
      if (requestVersion !== weeklyActivityRequestVersionRef.current) {
        return;
      }

      setWeeklyActivitySummary(normalized);
      setWeeklyActivityNotice(itemCount > 0 ? '已加载本周数据总结。' : '');
    } catch (loadActivityError) {
      if (requestVersion !== weeklyActivityRequestVersionRef.current) {
        return;
      }

      setWeeklyActivitySummary(null);
      setWeeklyActivityError(loadActivityError instanceof Error ? loadActivityError.message : '本周数据总结加载失败');
    } finally {
      if (requestVersion === weeklyActivityRequestVersionRef.current) {
        setWeeklyActivityLoading(false);
      }
    }
  };

  const handleLoadWeeklyFollowups = async () => {
    if (!activeWeeklyFollowupClassId) {
      setWeeklyFollowupError('请选择班级。');
      setWeeklyFollowupNotice('');
      return;
    }

    const requestVersion = weeklyFollowupRequestVersionRef.current + 1;
    weeklyFollowupRequestVersionRef.current = requestVersion;
    setWeeklyFollowupLoading(true);
    setWeeklyFollowupError('');
    setWeeklyFollowupNotice('');

    try {
      const response = await apiFetch<unknown>(
        buildWeeklyWrongQuestionFollowupsPath(activeWeeklyFollowupClassId, weeklyFollowupWeekStart),
      );
      const normalized = normalizeWeeklyWrongQuestionFollowupResponse(response);
      if (requestVersion !== weeklyFollowupRequestVersionRef.current) {
        return;
      }
      setWeeklyFollowupItems(normalized.items);
      setWeeklyFollowupNotice(normalized.items.length > 0 ? `已加载 ${normalized.items.length} 名学生。` : '本周暂无待跟进学生。');
    } catch (loadWeeklyError) {
      if (requestVersion !== weeklyFollowupRequestVersionRef.current) {
        return;
      }
      setWeeklyFollowupItems([]);
      setWeeklyFollowupError(loadWeeklyError instanceof Error ? loadWeeklyError.message : '每周跟进清单加载失败');
    } finally {
      if (requestVersion === weeklyFollowupRequestVersionRef.current) {
        setWeeklyFollowupLoading(false);
      }
    }
  };

  const handleLoadPracticePackJobs = useCallback(async () => {
    if (!activeWeeklyFollowupClassId) {
      setPracticePackJobs([]);
      return;
    }

    const requestVersion = practicePackRequestVersionRef.current + 1;
    practicePackRequestVersionRef.current = requestVersion;
    setWeeklyFollowupError('');

    try {
      const response = await apiFetch<WrongQuestionPracticePackListApiResponse>(
        buildWrongQuestionPracticePackListPath(activeWeeklyFollowupClassId),
      );
      if (requestVersion !== practicePackRequestVersionRef.current) {
        return;
      }
      setPracticePackJobs(normalizeWrongQuestionPracticePackListResponse(response));
    } catch (loadPackError) {
      if (requestVersion !== practicePackRequestVersionRef.current) {
        return;
      }
      setPracticePackJobs([]);
      setWeeklyFollowupError(loadPackError instanceof Error ? loadPackError.message : '练习包列表加载失败');
    }
  }, [activeWeeklyFollowupClassId]);

  useEffect(() => {
    if (!weeklyFollowupOpen || !activeWeeklyFollowupClassId) {
      return;
    }

    void handleLoadPracticePackJobs();
  }, [activeWeeklyFollowupClassId, handleLoadPracticePackJobs, weeklyFollowupOpen]);

  const handleGenerateWeeklyFollowupMessage = async (studentId: number) => {
    if (!activeWeeklyFollowupClassId) {
      setWeeklyFollowupError('请选择班级。');
      setWeeklyFollowupNotice('');
      return;
    }

    setGeneratingWeeklyFollowupStudentId(studentId);
    setWeeklyFollowupError('');
    setWeeklyFollowupNotice('');

    try {
      const response = await apiFetch<unknown>(buildWeeklyWrongQuestionFollowupMessagePath(), {
        method: 'POST',
        body: JSON.stringify({
          class_id: activeWeeklyFollowupClassId,
          week_start: weeklyFollowupWeekStart,
          student_id: studentId,
        }),
      });
      const responseMessage = extractGeneratedWeeklyFollowupMessage(response);
      if (responseMessage) {
        setWeeklyFollowupItems((current) => current.map((item) => {
          if (item.studentId !== studentId) {
            return item;
          }
          return {
            ...item,
            message: responseMessage,
          };
        }));
      }
      setWeeklyFollowupNotice('已生成家长沟通话术。');
    } catch (generateError) {
      setWeeklyFollowupError(generateError instanceof Error ? generateError.message : '家长沟通话术生成失败');
    } finally {
      setGeneratingWeeklyFollowupStudentId(null);
    }
  };

  const handleGenerateWeeklyPracticeSheet = async (studentId: number) => {
    if (!activeWeeklyFollowupClassId) {
      setWeeklyFollowupError('请选择班级。');
      setWeeklyFollowupNotice('');
      return;
    }

    setGeneratingWeeklyPracticeStudentId(studentId);
    setWeeklyFollowupError('');
    setWeeklyFollowupNotice('');

    try {
      await apiFetch(buildWeeklyWrongQuestionFollowupPracticeSheetPath(), {
        method: 'POST',
        body: JSON.stringify({
          class_id: activeWeeklyFollowupClassId,
          week_start: weeklyFollowupWeekStart,
          student_id: studentId,
        }),
      });
      setWeeklyFollowupNotice('已提交错题练习生成任务。');
      await handleLoadWeeklyFollowups();
    } catch (generateError) {
      setWeeklyFollowupError(generateError instanceof Error ? generateError.message : '错题练习生成失败');
    } finally {
      setGeneratingWeeklyPracticeStudentId(null);
    }
  };

  const handleBatchGenerateWeeklyPracticeSheets = async () => {
    if (!activeWeeklyFollowupClassId) {
      setWeeklyFollowupError('请选择班级。');
      setWeeklyFollowupNotice('');
      return;
    }

    setBatchGeneratingWeeklyPractice(true);
    setWeeklyFollowupError('');
    setWeeklyFollowupNotice('');

    try {
      const response = await apiFetch<{ created_count?: unknown }>(buildWeeklyWrongQuestionFollowupPracticeSheetBatchPath(), {
        method: 'POST',
        body: JSON.stringify({
          class_id: activeWeeklyFollowupClassId,
          week_start: weeklyFollowupWeekStart,
        }),
      });
      const createdCount = typeof response.created_count === 'number' ? response.created_count : 0;
      setWeeklyFollowupNotice(`已提交 ${createdCount} 份错题练习生成任务。`);
      await handleLoadWeeklyFollowups();
    } catch (generateError) {
      setWeeklyFollowupError(generateError instanceof Error ? generateError.message : '批量生成错题练习失败');
    } finally {
      setBatchGeneratingWeeklyPractice(false);
    }
  };

  const handleGeneratePracticePack = async () => {
    if (!activeWeeklyFollowupClassId) {
      setWeeklyFollowupError('请选择班级。');
      setWeeklyFollowupNotice('');
      return;
    }

    const target = practicePackTarget.trim();
    if (!target) {
      setWeeklyFollowupError('请填写练习包方向。');
      setWeeklyFollowupNotice('');
      return;
    }

    const requestVersion = practicePackRequestVersionRef.current + 1;
    practicePackRequestVersionRef.current = requestVersion;
    setPracticePackGenerating(true);
    setWeeklyFollowupError('');
    setWeeklyFollowupNotice('');

    try {
      const response = await apiFetch<unknown>(buildWrongQuestionPracticePackCreatePath(), {
        method: 'POST',
        body: JSON.stringify({
          class_id: activeWeeklyFollowupClassId,
          mode: practicePackMode,
          target,
          volume: practicePackVolume,
        }),
      });
      const normalized = normalizeWrongQuestionPracticePackJobResponse(response);
      if (requestVersion !== practicePackRequestVersionRef.current) {
        return;
      }
      const nextJob = normalized.job;
      if (nextJob) {
        setPracticePackJobs((current) => [
          nextJob,
          ...current.filter((item) => item.id !== nextJob.id),
        ]);
      }
      if (normalized.job?.downloadUrl) {
        globalThis.window?.open?.(buildWrongQuestionAuthedPath(normalized.job.downloadUrl), '_blank', 'noopener,noreferrer');
        setWeeklyFollowupNotice('练习包已生成，正在打开下载。');
      } else {
        setWeeklyFollowupNotice(normalized.reused ? '已有同条件练习包正在生成，完成后可下载。' : '正在生成，完成后可下载。');
      }
    } catch (generateError) {
      if (requestVersion !== practicePackRequestVersionRef.current) {
        return;
      }
      setWeeklyFollowupError(generateError instanceof Error ? generateError.message : '练习包生成失败');
    } finally {
      if (requestVersion === practicePackRequestVersionRef.current) {
        setPracticePackGenerating(false);
      }
    }
  };

  const handleRefreshPracticePackJob = async (jobId: number) => {
    if (!jobId) {
      return;
    }

    const requestVersion = practicePackRequestVersionRef.current + 1;
    practicePackRequestVersionRef.current = requestVersion;
    setWeeklyFollowupError('');
    setWeeklyFollowupNotice('');

    try {
      const response = await apiFetch<unknown>(buildWrongQuestionPracticePackDetailPath(jobId));
      const normalized = normalizeWrongQuestionPracticePackJobResponse(response);
      if (requestVersion !== practicePackRequestVersionRef.current) {
        return;
      }
      const nextJob = normalized.job;
      if (nextJob) {
        setPracticePackJobs((current) => current.map((item) => (
          item.id === nextJob.id ? nextJob : item
        )));
      }
      setWeeklyFollowupNotice('练习包状态已刷新。');
    } catch (refreshError) {
      if (requestVersion !== practicePackRequestVersionRef.current) {
        return;
      }
      setWeeklyFollowupError(refreshError instanceof Error ? refreshError.message : '练习包状态刷新失败');
    }
  };

  const handleCopyWeeklyFollowupMessage = async (messageText: string) => {
    const clipboard = globalThis.navigator?.clipboard;
    if (!clipboard?.writeText) {
      setWeeklyFollowupError('当前浏览器不支持复制。');
      setWeeklyFollowupNotice('');
      return;
    }

    try {
      await clipboard.writeText(messageText);
      setWeeklyFollowupError('');
      setWeeklyFollowupNotice('已复制。');
    } catch (copyError) {
      setWeeklyFollowupError(copyError instanceof Error ? copyError.message : '复制失败');
      setWeeklyFollowupNotice('');
    }
  };

  const handleOpenWeeklyFollowupArchive = () => {
    if (!activeWeeklyFollowupClassId) {
      setWeeklyFollowupError('请选择班级。');
      setWeeklyFollowupNotice('');
      return;
    }

    const archivePath = buildWrongQuestionAuthedPath(
      buildWeeklyWrongQuestionFollowupArchivePath(activeWeeklyFollowupClassId, weeklyFollowupWeekStart),
    );
    globalThis.window?.open?.(archivePath, '_blank', 'noopener,noreferrer');
  };

  const selectedKnowledgePointText = selectedDraft?.selectedKnowledgePoints.join('\n') ?? '';
  const selectedActionsText = selectedDraft?.selectedActions.join('\n') ?? '';
  const selectedReasonsText = selectedDraft?.selectedReasons.join('\n') ?? '';
  const selectedRecordLibraryPdfPath = selectedRecord?.studentLibraryPdfPath
    ? buildWrongQuestionAuthedPath(selectedRecord.studentLibraryPdfPath)
    : '';
  const selectedPracticeCount = effectiveSelectedPracticeRecordIds.length;
  const weeklyActivityHasItems = Boolean(weeklyActivitySummary && (
    weeklyActivitySummary.classItems.length > 0
    || weeklyActivitySummary.teacherItems.length > 0
    || weeklyActivitySummary.studentItems.length > 0
  ));
  const detailHeader = selectedRecord ? (
    <div className="mb-5 border-b border-slate-200/80 pb-5 dark:border-white/10">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-xl font-semibold text-slate-900 dark:text-white">错题详情</h4>
            <span className="text-base font-medium text-slate-900 dark:text-white">{selectedRecord.studentName}</span>
            {selectedRecord.source === 'wechat_mp' ? (
              <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300">
                微信小程序
              </span>
            ) : (
              <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${getWrongQuestionSourceBadgeClass(selectedRecord.source)}`}>
                {getWrongQuestionSourceLabel(selectedRecord.source)}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-500 dark:text-slate-400">
            <span>班级：{selectedRecord.className || '未标注班级'}</span>
            <span>老师：{selectedRecord.teacherName || '未标注老师'}</span>
            <span>记录时间：{selectedRecord.createdAt}</span>
          </div>
          {hasSnapshotDifference(selectedRecord.className, selectedRecord.classNameSnapshot) && (
            <p className="text-sm text-amber-700 dark:text-amber-300">原始班级：{selectedRecord.classNameSnapshot}</p>
          )}
          {hasSnapshotDifference(selectedRecord.teacherName, selectedRecord.teacherNameSnapshot) && (
            <p className="text-sm text-amber-700 dark:text-amber-300">原始老师：{selectedRecord.teacherNameSnapshot}</p>
          )}
        </div>
        {selectedRecord.source === 'wechat_mp' && selectedRecordLibraryPdfPath ? (
          <div className="flex flex-wrap gap-3">
            <a
              href={selectedRecordLibraryPdfPath}
              target="_blank"
              rel="noreferrer"
              className={workspaceSecondaryButtonClass}
            >
              预览 PDF
            </a>
            <a
              href={selectedRecordLibraryPdfPath}
              download="student-library.pdf"
              className={workspacePrimaryButtonClass}
            >
              下载 PDF
            </a>
            <button
              type="button"
              onClick={() => void handleRefreshStudentLibraryPdf()}
              disabled={refreshingLibraryPdf}
              className={workspaceSecondaryButtonClass}
            >
              {refreshingLibraryPdf ? '正在生成 PDF' : '重新生成 PDF'}
            </button>
          </div>
        ) : null}
      </div>
    </div>
  ) : (
    <div className="mb-5">
      <h4 className="text-xl font-semibold text-slate-900 dark:text-white">错题详情</h4>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">查看当前题目并保存跟进内容。</p>
    </div>
  );
  const handleMemberClassChange = (value: string) => {
    resetWeeklyFollowupContext();
    const nextClassId = value ? Number(value) : null;
    setSelectedClassId(Number.isFinite(nextClassId) ? nextClassId : null);
    setSelectedStudentName(null);
    setSelectedId(null);
  };
  const handleStaffClassChange = (value: string) => {
    resetWeeklyFollowupContext();
    const nextClassId = value ? Number(value) : null;
    const nextClassOption = Number.isFinite(nextClassId)
      ? visibleClassOptions.find((item) => item.id === nextClassId) ?? null
      : null;
    handleFilterChange('className', nextClassOption?.name ?? '');
  };
  const handleCloseMemberNotebook = () => {
    setSelectedStudentName(null);
    setSelectedId(null);
    setDetailError('');
    setSaveError('');
    setPdfRefreshNotice('');
    setNotebookModalView('questions');
    setSelectedPracticeRecordIds([]);
    setPracticeSelectionTouched(false);
    setPracticeSheets([]);
    setPracticeHistoryError('');
    setPracticeActionError('');
    setPracticeActionNotice('');
  };
  const handleOpenMemberNotebook = (studentName: string) => {
    const nextRecords = filterWrongQuestionRecordsForMemberNotebook(records, activeNotebookClassId, studentName);
    setSelectedStudentName(studentName);
    setSelectedId(nextRecords.length > 0 ? nextRecords[nextRecords.length - 1].id : null);
    setNotebookModalView('questions');
    setSelectedPracticeRecordIds([]);
    setPracticeSelectionTouched(false);
  };
  const handleOpenWeeklyFollowupSourceRecord = (item: WeeklyWrongQuestionFollowupItem, preferredRecordId = '') => {
    const preferredSourceRecord = preferredRecordId.trim()
      ? item.sourceRecords.find((record) => record.id === preferredRecordId.trim()) ?? null
      : null;
    const targetSourceRecord = preferredSourceRecord
      ?? item.sourceRecords[0]
      ?? null;
    const targetRecordId = targetSourceRecord?.id
      || item.candidateRecordIds[0]
      || item.sourceRecordIds[0]
      || '';
    if (!targetRecordId) {
      setWeeklyFollowupError('当前学生还没有可打开的来源错题。');
      setWeeklyFollowupNotice('');
      return;
    }
    const targetRecord = targetSourceRecord ?? records.find((record) => record.id === targetRecordId) ?? null;
    if (!targetRecord) {
      setWeeklyFollowupError('当前列表还没有加载这条来源错题，请先刷新列表。');
      setWeeklyFollowupNotice('');
      return;
    }
    openWrongQuestionRecordInNotebook(targetRecord, {
      classId: activeWeeklyFollowupClassId,
      studentName: item.studentName,
      notice: '已跳转到来源错题。',
    });
  };
  const handleStartWeeklyFollowupMasteryFollowup = useCallback(async (
    item: WeeklyWrongQuestionFollowupItem,
    sourceRecord: WrongQuestionRecord,
  ) => {
    const opened = openWrongQuestionRecordInNotebook(sourceRecord, {
      classId: activeWeeklyFollowupClassId,
      studentName: item.studentName,
      notice: '已跳转到 AI 归档，并准备开启掌握追问。',
    });
    if (!opened) {
      return;
    }
    scheduleNotebookMasteryFollowupStart(sourceRecord);
  }, [
    activeWeeklyFollowupClassId,
    openWrongQuestionRecordInNotebook,
    scheduleNotebookMasteryFollowupStart,
  ]);

  const handleStartNotebookDirectoryMasteryFollowup = useCallback(async (record: WrongQuestionRecord) => {
    setSelectedId(record.id);
    setNotebookModalView('questions');
    await handleStartWrongQuestionMasteryFollowup(record);
  }, [handleStartWrongQuestionMasteryFollowup]);
  const handleStartMemberNotebookSummaryMasteryFollowup = useCallback((record: WrongQuestionRecord) => {
    const opened = openWrongQuestionRecordInNotebook(record, {
      classId: activeNotebookClassId,
      studentName: record.studentName,
      notice: '已打开这位学生的 AI 归档，并准备开启掌握追问。',
    });
    if (!opened) {
      return;
    }
    scheduleNotebookMasteryFollowupStart(record);
  }, [
    activeNotebookClassId,
    openWrongQuestionRecordInNotebook,
    scheduleNotebookMasteryFollowupStart,
  ]);
  const handleStartWeeklyActivitySummaryMasteryFollowup = useCallback(async (
    item: WeeklyWrongQuestionActivityStudentItem,
    record: WrongQuestionRecord | null,
  ) => {
    const preferredRecordId = record?.id || item.sourceRecordIds[0] || '';
    let targetRecord = record ?? records.find((candidate) => candidate.id === preferredRecordId) ?? null;
    if (!targetRecord && preferredRecordId) {
      try {
        const detail = await apiFetch<unknown>(buildWrongQuestionDetailPath(preferredRecordId));
        targetRecord = normalizeWrongQuestionRecord(detail);
      } catch (detailError) {
        setWeeklyFollowupError(detailError instanceof Error ? detailError.message : '来源错题加载失败');
        setWeeklyFollowupNotice('');
        return;
      }
    }
    if (!targetRecord) {
      setWeeklyFollowupError('当前学生还没有可继续追问的 AI 归档。');
      setWeeklyFollowupNotice('');
      return;
    }
    const opened = openWrongQuestionRecordInNotebook(targetRecord, {
      classId: item.classId,
      studentName: item.studentName,
      notice: '已打开这位学生的 AI 归档，并准备开启掌握追问。',
    });
    if (!opened) {
      return;
    }
    scheduleNotebookMasteryFollowupStart(targetRecord);
  }, [
    openWrongQuestionRecordInNotebook,
    records,
    scheduleNotebookMasteryFollowupStart,
  ]);
  const practiceHistoryMasteryFollowupRecordBySheetId = useMemo(() => {
    const recordById = new Map(records.map((item) => [item.id, item]));
    return new Map(
      practiceSheets.map((sheet) => {
        const linkedRecord = sheet.sourceRecordIds
          .map((recordId) => recordById.get(recordId) ?? null)
          .find((record) => canStartWrongQuestionMasteryFollowup(record)) ?? null;
        return [sheet.id, linkedRecord];
      }),
    );
  }, [practiceSheets, records]);

  const practiceHistoryPanel = (
    <>
      <div className="mb-5 border-b border-slate-200/80 pb-5 dark:border-white/10">
        <h4 className="text-xl font-semibold text-slate-900 dark:text-white">错题练习记录</h4>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">老师生成后的练习单会保存在这里，生成完成后可直接预览或下载 PDF。</p>
      </div>

      {practiceHistoryLoading ? (
        <div className="rounded-2xl border border-dashed border-sky-200 px-4 py-6 text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
          正在加载错题练习记录...
        </div>
      ) : practiceSheets.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-sky-200 px-4 py-6 text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
          还没有生成过错题练习。
        </div>
      ) : (
        <div className="space-y-4">
          {practiceSheets.map((sheet, index) => {
            const displaySheetNumber = practiceSheets.length - index;
            const previewPath = sheet.pdfUrl || sheet.pdfPath || sheet.downloadUrl || '';
            const downloadPath = sheet.downloadUrl || sheet.pdfUrl || sheet.pdfPath || '';
            const previewUrl = previewPath ? buildWrongQuestionAuthedPath(previewPath) : '';
            const downloadUrl = downloadPath ? buildWrongQuestionAuthedPath(downloadPath) : previewUrl;
            const linkedFollowupRecord = practiceHistoryMasteryFollowupRecordBySheetId.get(sheet.id) ?? null;
            return (
              <article key={sheet.id} className={`${workspaceSoftCardClass} space-y-4 p-4`}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-base font-semibold text-slate-900 dark:text-white">练习单 #{displaySheetNumber}</span>
                      <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${sheet.status === 'ready' ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300' : sheet.status === 'failed' ? 'border-rose-200 bg-rose-50 text-rose-600 dark:border-rose-400/30 dark:bg-rose-500/10 dark:text-rose-300' : 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300'}`}>
                        {getWrongQuestionPracticeStatusLabel(sheet.status)}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-500 dark:text-slate-400">
                      <span>{sheet.createdAt || '未记录时间'}</span>
                      <span className="whitespace-nowrap">{sheet.questionCount}题</span>
                      <span>{sheet.teacherNameSnapshot || '未记录老师'}</span>
                    </div>
                    {sheet.generationError ? (
                      <p className="text-sm text-rose-600 dark:text-rose-300">{sheet.generationError}</p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap gap-3">
                    {linkedFollowupRecord ? (
                      <button
                        type="button"
                        aria-label={`从练习单 #${displaySheetNumber} 开启掌握追问`}
                        onClick={() => void handleStartNotebookDirectoryMasteryFollowup(linkedFollowupRecord)}
                        disabled={wrongQuestionChatSending}
                        className={workspacePrimaryButtonClass}
                      >
                        开启掌握追问
                      </button>
                    ) : null}
                    {previewUrl ? (
                      <>
                        <a
                          href={previewUrl}
                          target="_blank"
                          rel="noreferrer"
                          className={workspaceSecondaryButtonClass}
                        >
                          预览 PDF
                        </a>
                        <a
                          href={downloadUrl}
                          className={workspacePrimaryButtonClass}
                        >
                          下载 PDF
                        </a>
                      </>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => void handleDeletePracticeSheet(sheet)}
                      className="inline-flex items-center justify-center rounded-full border border-rose-200 bg-white px-4 py-2 text-sm font-semibold text-rose-600 transition hover:bg-rose-50 dark:border-rose-400/30 dark:bg-slate-950/70 dark:text-rose-300 dark:hover:bg-rose-500/10"
                    >
                      删除练习
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </>
  );
  const wrongQuestionChatPanel = (
    <section className={`${workspaceSoftCardClass} mb-5 space-y-4 p-4`}>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
              <MessageSquare size={16} />
            </span>
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-white">AI 对话归档</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">上传错题图，先问错因，再整理进错题库。</p>
            </div>
          </div>
          {wrongQuestionChatSession ? (
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 font-semibold text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                {wrongQuestionChatCurrentStageLabel}
              </span>
              <span>会话：{wrongQuestionChatSession.id}</span>
              {wrongQuestionChatRun?.assets.length ? <span>{wrongQuestionChatRun.assets.length} 张图片</span> : null}
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {wrongQuestionChatSession?.status === 'archived' && canStartWrongQuestionMasteryFollowup(wrongQuestionChatArchivedRecord) ? (
            <button
              type="button"
              onClick={() => void handleStartWrongQuestionMasteryFollowup(wrongQuestionChatArchivedRecord)}
              disabled={wrongQuestionChatSending}
              className={workspacePrimaryButtonClass}
            >
              开启掌握追问
            </button>
          ) : null}
          {wrongQuestionChatSession?.status === 'archived' && wrongQuestionChatArchivedRecordConfirmationStatus === 'returned' ? (
            <button
              type="button"
              onClick={() => void handleReopenWrongQuestionChat()}
              disabled={wrongQuestionChatSending}
              className={workspacePrimaryButtonClass}
            >
              按老师意见继续补充
            </button>
          ) : null}
          {wrongQuestionChatSession?.status === 'archived' ? (
            <button
              type="button"
              onClick={resetWrongQuestionChatState}
              className={workspaceSecondaryButtonClass}
            >
              开始新对话
            </button>
          ) : null}
          {wrongQuestionChatSession?.detailUrl ? (
            <a
              href={buildWrongQuestionAuthedPath(wrongQuestionChatSession.detailUrl)}
              target="_blank"
              rel="noreferrer"
              className={workspaceSecondaryButtonClass}
            >
              打开会话详情
            </a>
          ) : null}
        </div>
      </div>

      {wrongQuestionChatError ? (
        <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
          <AlertCircle size={16} />
          {wrongQuestionChatError}
        </div>
      ) : null}

      {wrongQuestionChatNotice ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-300">
          {wrongQuestionChatNotice}
        </div>
      ) : null}

      {wrongQuestionChatLoading ? (
        <div className="rounded-2xl border border-dashed border-sky-200 px-4 py-6 text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
          正在恢复最近一次错题对话...
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <div className="space-y-4">
          <label className={`${workspaceCardClass} flex cursor-pointer flex-col gap-3 border-dashed p-4 transition hover:border-sky-300 dark:hover:border-sky-400/30`}>
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-white">
              <Upload size={16} />
              上传错题图片
            </div>
            <p className="text-xs leading-6 text-slate-500 dark:text-slate-400">支持一次选多张，先保存在同一条归档 run 里。</p>
            <input
              type="file"
              accept="image/png,image/jpeg,image/jpg,image/webp"
              multiple
              onChange={(event) => handleWrongQuestionChatFileChange((event.target as HTMLInputElement).files)}
              className="hidden"
            />
            <span className={workspaceSecondaryButtonClass}>选择图片</span>
          </label>

          {wrongQuestionChatUploading ? (
            <div className={`${workspaceCardClass} space-y-3 p-4`}>
              <div className="flex items-center justify-between gap-3 text-sm text-slate-600 dark:text-slate-300">
                <span>上传进度</span>
                <span>{wrongQuestionChatUploadProgress}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                <div
                  className="h-full rounded-full bg-sky-500 transition-all"
                  style={{ width: `${wrongQuestionChatUploadProgress}%` }}
                />
              </div>
            </div>
          ) : null}

          {wrongQuestionChatLocalPreviews.length > 0 || wrongQuestionChatAssetPreviews.length > 0 ? (
            <div className={`${workspaceCardClass} space-y-3 p-4`}>
              <p className="text-sm font-semibold text-slate-900 dark:text-white">当前图片</p>
              <div className="grid grid-cols-2 gap-3">
                {(wrongQuestionChatAssetPreviews.length > 0
                  ? wrongQuestionChatAssetPreviews.map((url, index) => ({ name: `已上传图片 ${index + 1}`, url }))
                  : wrongQuestionChatLocalPreviews
                ).map((item) => (
                  <a
                    key={`${item.name}-${item.url}`}
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white dark:border-white/10 dark:bg-slate-950/70"
                  >
                    <img src={item.url} alt={item.name} className="h-28 w-full object-cover" />
                    <div className="border-t border-slate-200/80 px-3 py-2 text-xs text-slate-500 dark:border-white/10 dark:text-slate-400">{item.name}</div>
                  </a>
                ))}
              </div>
            </div>
          ) : null}

          <div className={`${workspaceCardClass} space-y-3 p-4`}>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">题目文本</span>
              <textarea
                value={wrongQuestionChatDraft.questionText}
                onChange={(event) => handleWrongQuestionChatDraftChange('questionText', event.target.value)}
                className={`${workspaceFieldClass} min-h-24 resize-y`}
                placeholder="可先手动补上题干，归档时会一起保存。"
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-2 text-sm">
                <span className="text-slate-500 dark:text-slate-400">专题</span>
                <input
                  value={wrongQuestionChatDraft.topicCategory}
                  onChange={(event) => handleWrongQuestionChatDraftChange('topicCategory', event.target.value)}
                  className={workspaceFieldClass}
                  placeholder="如：一元一次方程"
                />
              </label>
              <label className="space-y-2 text-sm">
                <span className="text-slate-500 dark:text-slate-400">知识点</span>
                <input
                  value={wrongQuestionChatDraft.knowledgeTagsText}
                  onChange={(event) => handleWrongQuestionChatDraftChange('knowledgeTagsText', event.target.value)}
                  className={workspaceFieldClass}
                  placeholder="逗号分隔，如：移项, 方程"
                />
              </label>
            </div>
            {!wrongQuestionChatSession ? (
              <button
                type="button"
                onClick={() => void handleStartWrongQuestionChat()}
                disabled={wrongQuestionChatUploading || wrongQuestionChatFiles.length === 0}
                className={workspacePrimaryButtonClass}
              >
                {wrongQuestionChatUploading ? '正在创建对话...' : '开始 AI 追问'}
              </button>
            ) : null}
          </div>
        </div>

        <div className={`${workspaceCardClass} flex min-h-[24rem] flex-col p-4`}>
          <div className="flex items-center justify-between gap-3 border-b border-slate-200/80 pb-3 dark:border-white/10">
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-white">对话过程</p>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">按三步走：错因、卡点、帮助方式。</p>
            </div>
            {wrongQuestionChatSession?.status === 'archived' ? (
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-300">
                已归档
              </span>
            ) : null}
          </div>

          {wrongQuestionChatArchivePreviewVisible ? (
            <div className="mt-4 space-y-3 rounded-2xl border border-slate-200/80 bg-slate-50/80 p-4 dark:border-white/10 dark:bg-slate-950/50">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900 dark:text-white">归档预览</p>
                <span className="text-xs text-slate-500 dark:text-slate-400">最终保存前会按这里的内容归档</span>
              </div>
              {wrongQuestionChatAssetPreviews.length > 0 || wrongQuestionChatLocalPreviews.length > 0 ? (
                <div className="grid grid-cols-3 gap-2">
                  {(wrongQuestionChatAssetPreviews.length > 0
                    ? wrongQuestionChatAssetPreviews.map((url, index) => ({ name: `已上传图片 ${index + 1}`, url }))
                    : wrongQuestionChatLocalPreviews
                  ).map((item) => (
                    <a
                      key={`archive-preview-${item.name}-${item.url}`}
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white dark:border-white/10 dark:bg-slate-950/70"
                    >
                      <img src={item.url} alt={item.name} className="h-20 w-full object-cover" />
                    </a>
                  ))}
                </div>
              ) : null}
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">题目文本</p>
                  <p className="text-sm leading-6 text-slate-700 dark:text-slate-200">{wrongQuestionChatDraft.questionText.trim() || '待补充'}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">专题 / 知识点</p>
                  <p className="text-sm leading-6 text-slate-700 dark:text-slate-200">
                    {wrongQuestionChatDraft.topicCategory.trim() || '未填写'}
                    {wrongQuestionChatKnowledgeTagList.length > 0 ? ` / ${wrongQuestionChatKnowledgeTagList.join('、')}` : ' / 待确认'}
                  </p>
                </div>
              </div>
              {wrongQuestionChatSession?.summaryText.trim() ? (
                <div className="space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">归档摘要（仅归档）</p>
                  <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">{wrongQuestionChatSession.summaryText.trim()}</p>
                </div>
              ) : null}
            </div>
          ) : null}

          {wrongQuestionChatSession && wrongQuestionChatSession.status !== 'archived' && wrongQuestionChatConfirmationReasonLabels.length > 0 ? (
            <div className="mt-4 flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-200">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <div>
                <p className="font-semibold">当前信息不足，归档后会进入老师复核</p>
                <p className="mt-1 leading-6">{wrongQuestionChatConfirmationReasonLabels.join('、')}</p>
              </div>
            </div>
          ) : null}

          {wrongQuestionChatIsMasteryFollowup && wrongQuestionChatSession && wrongQuestionChatSession.status !== 'archived' ? (
            <div className="mt-4 rounded-2xl border border-sky-200/80 bg-sky-50/80 p-4 dark:border-sky-500/20 dark:bg-sky-500/10">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-700 dark:text-sky-200">掌握追问结果</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {[
                  { value: 'still_confused', label: '仍然没吃透' },
                  { value: 'needs_another_practice', label: '需要再练一轮' },
                  { value: 'likely_mastered', label: '大概率已掌握' },
                ].map((option) => {
                  const isActive = wrongQuestionChatDraft.followupOutcome === option.value;
                  return (
                    <button
                      key={`followup-outcome-${option.value}`}
                      type="button"
                      onClick={() => handleWrongQuestionChatDraftChange('followupOutcome', option.value)}
                      className={isActive ? workspacePrimaryButtonClass : workspaceSecondaryButtonClass}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
              <p className="mt-3 text-xs leading-6 text-sky-700/80 dark:text-sky-100/80">
                归档这轮掌握追问时，系统会把这个结果写回同一条错题记录，后面继续据此判断是再练、再追问，还是准备确认掌握。
              </p>
            </div>
          ) : null}

          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto py-4">
            {!wrongQuestionChatSession ? (
              <div className="rounded-2xl border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
                先上传错题图并开启对话，AI 会先问学生为什么错。
              </div>
            ) : wrongQuestionChatSession.messages.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
                正在等待第一条追问。
              </div>
            ) : (
              wrongQuestionChatSession.messages.map((item) => {
                const isAssistant = item.role === 'assistant';
                return (
                  <article
                    key={`${item.id}-${item.createdAt}`}
                    className={`max-w-[92%] rounded-2xl px-4 py-3 text-sm leading-6 ${isAssistant ? 'mr-auto border border-sky-100 bg-sky-50/80 text-slate-700 dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-slate-100' : 'ml-auto border border-slate-200 bg-white text-slate-700 dark:border-white/10 dark:bg-slate-900 dark:text-slate-100'}`}
                  >
                    <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                      <span>{isAssistant ? 'AI' : '学生'}</span>
                      <span>{WRONG_QUESTION_CHAT_STAGE_LABELS[item.stage] || item.stage}</span>
                    </div>
                    <p className="whitespace-pre-wrap">{item.content}</p>
                  </article>
                );
              })
            )}
          </div>

          {wrongQuestionChatArchivedRecord ? (
            <div className="mb-4 rounded-2xl border border-emerald-200 bg-emerald-50/80 p-4 dark:border-emerald-400/20 dark:bg-emerald-500/10">
              <div className="flex items-start gap-3">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-emerald-200 bg-white text-emerald-600 dark:border-emerald-400/20 dark:bg-slate-950 dark:text-emerald-300">
                  <CheckCircle2 size={16} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-emerald-700 dark:text-emerald-300">已归档到错题库</p>
                  <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{wrongQuestionChatArchivedRecord.questionText || '题目文本待老师补充'}</p>
                  {wrongQuestionChatArchivedRecord.needsTeacherConfirmation ? (
                    <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                      需要老师复核：{(wrongQuestionChatArchivedRecord.confirmationReasons ?? []).join('、') || '信息不完整'}
                    </p>
                  ) : null}
                  {wrongQuestionChatArchivedRecordConfirmationStatus === 'returned' ? (
                    <p className="mt-2 text-xs text-sky-700 dark:text-sky-300">
                      老师已退回这条归档，补充完成后会覆盖原错题记录。
                    </p>
                  ) : null}
                  <div className="mt-3 flex flex-wrap gap-2">
                    {wrongQuestionChatArchivedRecord.detailUrl ? (
                      <a
                        href={buildWrongQuestionAuthedPath(wrongQuestionChatArchivedRecord.detailUrl)}
                        target="_blank"
                        rel="noreferrer"
                        className={workspaceSecondaryButtonClass}
                      >
                        打开错题详情
                      </a>
                    ) : null}
                    {wrongQuestionChatArchivedRecordConfirmationStatus === 'returned' ? (
                      <button
                        type="button"
                        onClick={() => void handleReopenWrongQuestionChat()}
                        disabled={wrongQuestionChatSending}
                        className={workspaceSecondaryButtonClass}
                      >
                        按老师意见继续补充
                      </button>
                    ) : null}
                    {wrongQuestionChatArchivedRecord.archiveContext?.ingestionRunUrl ? (
                      <a
                        href={buildWrongQuestionAuthedPath(wrongQuestionChatArchivedRecord.archiveContext.ingestionRunUrl)}
                        target="_blank"
                        rel="noreferrer"
                        className={workspaceSecondaryButtonClass}
                      >
                        打开处理链路
                      </a>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          <div className="border-t border-slate-200/80 pt-3 dark:border-white/10">
            {wrongQuestionChatLastAssistantMessage ? (
              <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
                当前提示：{wrongQuestionChatLastAssistantMessage.content}
              </p>
            ) : null}
            {wrongQuestionChatSession?.currentStage === 'ask_help_mode' && wrongQuestionChatSession.status !== 'archived' ? (
              <div className="mb-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void handleSendWrongQuestionChatMessage('先给我一点提示，我想自己再试试。')}
                  disabled={wrongQuestionChatSending}
                  className={workspaceSecondaryButtonClass}
                >
                  先看提示
                </button>
                <button
                  type="button"
                  onClick={() => void handleSendWrongQuestionChatMessage('请带我完整复盘一遍这道题。')}
                  disabled={wrongQuestionChatSending}
                  className={workspaceSecondaryButtonClass}
                >
                  完整复盘
                </button>
              </div>
            ) : null}
            <textarea
              value={wrongQuestionChatDraft.replyText}
              onChange={(event) => handleWrongQuestionChatDraftChange('replyText', event.target.value)}
              className={`${workspaceFieldClass} min-h-24 resize-y`}
              placeholder={wrongQuestionChatSession?.status === 'archived' ? '这条对话已经归档完成。可以开始新的对话。' : '输入学生回答，继续这条错题追问。'}
              disabled={!wrongQuestionChatSession || wrongQuestionChatSession.status === 'archived'}
            />
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                onClick={() => void handleSendWrongQuestionChatMessage()}
                disabled={!wrongQuestionChatSession || wrongQuestionChatSession.status === 'archived' || wrongQuestionChatSending}
                className={workspacePrimaryButtonClass}
              >
                {wrongQuestionChatSending ? '发送中...' : '发送回答'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
  const detailPanel = selectedRecord ? (
    <>
      {selectedDraft && (selectedRecord.source === 'wechat_mp' || selectedRecord.source === 'ai_chat') && !selectedRecord.isGeometry && (
        <div className={`${workspaceSoftCardClass} space-y-3 p-4`}>
          <label className="space-y-2 text-sm">
            <span className="text-slate-500 dark:text-slate-400">题目文本</span>
            <textarea
              value={selectedDraft.questionText ?? ''}
              onChange={(event) => handleDraftChange('questionText', event.target.value)}
              onInput={(event) => handleDraftChange('questionText', (event.target as HTMLTextAreaElement).value)}
              className={`${workspaceFieldClass} min-h-28 resize-y`}
              placeholder="填写可直接进入错题库 PDF 的题目文本"
            />
          </label>
          <p className="text-xs leading-6 text-slate-500 dark:text-slate-400">
            正文直接写，公式片段用 <code>$...$</code> 或 <code>$$...$$</code>。保存不会拦截公式错误，但下面会提示渲染失败的位置。
          </p>
          <div className="rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-slate-950/70">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">公式预览</span>
              {selectedQuestionTextPreview && selectedQuestionTextPreview.errors.length > 0 ? (
                <span className="rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-600 dark:border-rose-400/30 dark:bg-rose-500/10 dark:text-rose-300">
                  {selectedQuestionTextPreview.errors.length} 处渲染失败
                </span>
              ) : (
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-600 dark:border-emerald-400/30 dark:bg-emerald-500/10 dark:text-emerald-300">
                  预览正常
                </span>
              )}
            </div>
            <div
              className="xr-latex-preview mt-3 rounded-2xl border border-slate-200/80 bg-white px-4 py-3 text-[15px] text-slate-700 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100"
              dangerouslySetInnerHTML={{
                __html: selectedQuestionTextPreview?.html || '<span class="xr-latex-empty">暂无题目文本</span>',
              }}
            />
            {selectedQuestionTextPreview && selectedQuestionTextPreview.errors.length > 0 ? (
              <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs leading-6 text-rose-700 dark:border-rose-400/30 dark:bg-rose-500/10 dark:text-rose-300">
                {selectedQuestionTextPreview.errors.map((error) => (
                  <div key={`${error.type}-${error.source}`}>
                    {error.message}：{error.source}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      )}

      {selectedRecord.source === 'wechat_mp' && (
        <div className={`${workspaceSoftCardClass} space-y-4 p-4`}>
          {selectedRecord.imageUrl ? (
            <a
              href={selectedRecord.imageUrl}
              target="_blank"
              rel="noreferrer"
              className="block overflow-hidden rounded-2xl border border-sky-100 bg-white/80 dark:border-white/10 dark:bg-slate-950/70"
            >
              <img
                src={selectedRecord.imageUrl}
                alt={`${selectedRecord.studentName} 的错题图片`}
                className="max-h-72 w-full object-cover"
              />
            </a>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div className={`${workspaceCardClass} p-4`}>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">孩子自述错因</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600 dark:text-slate-300">{selectedRecord.childReasonText || '孩子还没有填写错因描述。'}</p>
            </div>
            {selectedRecordIsPrimarySchool ? (
              <div className={`${workspaceCardClass} p-4`}>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">小学专题</p>
                {selectedDraft ? (
                  <div className="mt-2 space-y-2">
                    <select
                      aria-label="小学专题"
                      value={topicCategoryOptions.includes(selectedDraft.topicCategory ?? '') ? selectedDraft.topicCategory : '自定义'}
                      onChange={(event) => handleDraftChange('topicCategory', event.target.value === '自定义' ? '' : event.target.value)}
                      className={workspaceFieldClass}
                    >
                      {topicCategoryOptions.map((item) => (
                        <option key={item} value={item}>{item}</option>
                      ))}
                      <option value="自定义">自定义</option>
                    </select>
                    <input
                      aria-label="自定义小学专题"
                      value={selectedDraft.topicCategory ?? '未分类'}
                      onChange={(event) => handleDraftChange('topicCategory', event.target.value)}
                      className={workspaceFieldClass}
                      placeholder="如：周期问题"
                    />
                  </div>
                ) : (
                  <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">{selectedRecord.topicCategory || '未分类'}</p>
                )}
              </div>
            ) : null}
            <div className={`${workspaceCardClass} p-4`}>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">问题归类</p>
              {selectedDraft ? (
                <select
                  aria-label="问题归类"
                  value={selectedDraft.selectedErrorType}
                  onChange={(event) => handleDraftChange('selectedErrorType', event.target.value)}
                  className={`${workspaceFieldClass} mt-2`}
                >
                  <option value="">请选择问题归类</option>
                  {finalErrorTypeOptions.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              ) : (
                <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">{selectedRecord.primaryErrorType || selectedRecord.analysis.errorType || '待归类'}</p>
              )}
            </div>
            <div className={`${workspaceCardClass} p-4`}>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">补充备注</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-500 dark:text-slate-400">{selectedRecord.causeNote || selectedRecord.analysis.studentNote || '暂无备注'}</p>
            </div>
          </div>
          {(selectedRecord.reasonCoreIssue || selectedRecord.reasonKeyOmission || selectedRecord.reasonNextStep) ? (
            <div className={`${workspaceCardClass} p-4`}>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">AI 错因分析</p>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">核心错因</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">{selectedRecord.reasonCoreIssue || '暂无'}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">关键遗漏</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">{selectedRecord.reasonKeyOmission || '暂无'}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">后续操作</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">{selectedRecord.reasonNextStep || '暂无'}</p>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {selectedRecord.mappingStatus !== 'mapped' && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-200">
          <div className="flex items-start gap-2">
            <AlertCircle size={16} className="mt-0.5" />
            <div>
              <p className="font-semibold">老师与班级归属待确认</p>
              <p className="mt-1">
                {hasStaffScope
                  ? '当前老师或班级仍在沿用原始信息。请先在班级管理中确认负责班级；如果老师名称与系统成员姓名不一致，需要补充老师别名映射。'
                  : '当前老师或班级仍在沿用原始信息，请联系机构负责人在班级管理中确认负责班级，并补充老师别名映射。'}
              </p>
            </div>
          </div>
        </div>
      )}

      {detailLoading && (
        <div className="rounded-2xl border border-dashed border-sky-200 px-4 py-3 text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
          正在加载记录详情...
        </div>
      )}

      {selectedRecord.source !== 'wechat_mp' && (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className={`${workspaceSoftCardClass} p-4`}>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">题型分类</p>
              <p className="mt-2 text-base font-semibold text-slate-900 dark:text-white">{selectedRecord.analysis.questionCategory || '待识别'}</p>
            </div>
            <div className={`${workspaceSoftCardClass} p-4`}>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">重复错题</p>
              <p className="mt-2 text-base font-semibold text-slate-900 dark:text-white">{selectedRecord.analysis.isRepeatedMistake || '待确认'}</p>
            </div>
          </div>

          <div className={`${workspaceSoftCardClass} space-y-3 p-4`}>
            <p className="text-sm font-semibold text-slate-900 dark:text-white">知识点</p>
            <div className="flex flex-wrap gap-2">
              {selectedRecord.analysis.knowledgePoints.length > 0 ? selectedRecord.analysis.knowledgePoints.map((point) => (
                <span
                  key={point}
                  className="rounded-full border border-sky-200 bg-white/80 px-3 py-1 text-xs font-semibold text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300"
                >
                  {point}
                </span>
              )) : (
                <span className="text-sm text-slate-500 dark:text-slate-400">暂无知识点标签</span>
              )}
            </div>
          </div>

          {selectedRecord.source === 'ai_chat' && (
            <div className={`${workspaceSoftCardClass} space-y-4 p-4`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-white">归档来源</p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    {selectedRecord.archiveContext?.source || selectedRecord.linkedIngestionRun?.source || 'ai_chat'}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {selectedRecord.linkedIngestionRun?.detailUrl ? (
                    <a
                      href={buildWrongQuestionAuthedPath(selectedRecord.linkedIngestionRun.detailUrl)}
                      target="_blank"
                      rel="noreferrer"
                      className={workspaceSecondaryButtonClass}
                    >
                      打开处理链路
                    </a>
                  ) : null}
                  {selectedRecord.linkedChatSession?.detailUrl ? (
                    <a
                      href={buildWrongQuestionAuthedPath(selectedRecord.linkedChatSession.detailUrl)}
                      target="_blank"
                      rel="noreferrer"
                      className={workspaceSecondaryButtonClass}
                    >
                      打开对话归档
                    </a>
                  ) : null}
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                <div className={`${workspaceCardClass} space-y-3 p-4`}>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">老师复核原因</p>
                  <div className="flex flex-wrap gap-2">
                    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${getWrongQuestionConfirmationStatusBadgeClass(selectedRecordConfirmationStatus)}`}>
                      {WRONG_QUESTION_CONFIRMATION_STATUS_LABELS[selectedRecordConfirmationStatus] || selectedRecordConfirmationStatus}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(selectedDraft?.confirmationReasons ?? selectedRecord.confirmationReasons ?? []).length > 0 ? (
                      (selectedDraft?.confirmationReasons ?? selectedRecord.confirmationReasons ?? []).map((reason) => (
                        <span
                          key={reason}
                          className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700 dark:border-amber-400/30 dark:bg-amber-500/10 dark:text-amber-300"
                        >
                          {WRONG_QUESTION_CHAT_CONFIRMATION_REASON_LABELS[reason] || reason}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500 dark:text-slate-400">当前没有待复核原因</span>
                    )}
                  </div>
                  {selectedRecord.confirmationReviewerName || selectedRecord.confirmationReviewedAt ? (
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      最近处理：{selectedRecord.confirmationReviewerName || '未记录老师'}
                      {selectedRecord.confirmationReviewedAt ? ` · ${selectedRecord.confirmationReviewedAt}` : ''}
                    </p>
                  ) : null}
                  {selectedRecord.needsTeacherConfirmation ? (
                    <p className="text-sm text-slate-500 dark:text-slate-400">这条记录目前仍会出现在老师复核链路里。</p>
                  ) : (
                    <p className="text-sm text-slate-500 dark:text-slate-400">这条记录当前已经可以直接进入后续练习链路。</p>
                  )}
                </div>

                <div className={`${workspaceCardClass} space-y-3 p-4`}>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">学生反思</p>
                  <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">
                    {selectedRecordReflectionSummaryText || '暂无结构化反思摘要'}
                  </p>
                  <div className="grid gap-3 md:grid-cols-3">
                    <div>
                      <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">为什么错</p>
                      {selectedDraft ? (
                        <textarea
                          aria-label="学生反思：为什么错"
                          value={selectedDraft.reflectionWhyWrong ?? ''}
                          onChange={(event) => handleDraftChange('reflectionWhyWrong', event.target.value)}
                          className={`${workspaceFieldClass} mt-1 min-h-24`}
                          placeholder="老师可补充学生真正的错因表达"
                        />
                      ) : (
                        <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">
                          {selectedRecordReflectionSummary?.whyWrong || selectedRecord.childReasonText || '暂无'}
                        </p>
                      )}
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">不理解的步骤</p>
                      {selectedDraft ? (
                        <textarea
                          aria-label="学生反思：不理解的步骤"
                          value={selectedDraft.reflectionUnknownStep ?? ''}
                          onChange={(event) => handleDraftChange('reflectionUnknownStep', event.target.value)}
                          className={`${workspaceFieldClass} mt-1 min-h-24`}
                          placeholder="老师可补充学生卡住的具体步骤"
                        />
                      ) : (
                        <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">
                          {selectedRecordReflectionSummary?.unknownStep || selectedRecord.reasonCoreIssue || '暂无'}
                        </p>
                      )}
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">希望怎么帮助</p>
                      {selectedDraft ? (
                        <textarea
                          aria-label="学生反思：希望怎么帮助"
                          value={selectedDraft.reflectionHelpPreference ?? ''}
                          onChange={(event) => handleDraftChange('reflectionHelpPreference', event.target.value)}
                          className={`${workspaceFieldClass} mt-1 min-h-24`}
                          placeholder="老师可补充更合适的引导方式"
                        />
                      ) : (
                        <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">
                          {selectedRecordReflectionSummary?.helpPreference || selectedRecord.reasonNextStep || '暂无'}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                    <span>反思模式：{WRONG_QUESTION_REFLECTION_MODE_LABELS[selectedRecordReflectionSummary?.mode || ''] || selectedRecordReflectionSummary?.mode || '未记录'}</span>
                    {selectedRecord.linkedChatSession ? (
                      <>
                        <span>阶段：{WRONG_QUESTION_CHAT_STAGE_LABELS[selectedRecord.linkedChatSession.currentStage] || selectedRecord.linkedChatSession.currentStage || '未记录'}</span>
                        <span>消息数：{selectedRecord.linkedChatSession.messages.length}</span>
                      </>
                    ) : null}
                  </div>
                  {selectedRecordReflectionAnsweredStageLabels.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {selectedRecordReflectionAnsweredStageLabels.map((label) => (
                        <span
                          key={label}
                          className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600 dark:border-white/10 dark:bg-slate-900 dark:text-slate-300"
                        >
                          {label}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>

                <div className={`${workspaceCardClass} space-y-3 p-4`}>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">对话归档摘要</p>
                  <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">
                    {selectedRecordReflectionSummaryText || '暂无对话摘要'}
                  </p>
                  {selectedRecord.linkedChatSession ? (
                    <div className="flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                      <span>阶段：{WRONG_QUESTION_CHAT_STAGE_LABELS[selectedRecord.linkedChatSession.currentStage] || selectedRecord.linkedChatSession.currentStage || '未记录'}</span>
                      <span>消息数：{selectedRecord.linkedChatSession.messages.length}</span>
                    </div>
                  ) : null}
                </div>
              </div>

              <div className={`${workspaceCardClass} space-y-3 p-4`}>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">生成版本</p>
                {selectedRecordGenerationMetadataEntries.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {selectedRecordGenerationMetadataEntries.map((item) => (
                      <span
                        key={`${item.label}-${item.value}`}
                        className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600 dark:border-white/10 dark:bg-slate-900 dark:text-slate-300"
                      >
                        {item.label}: {item.value}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500 dark:text-slate-400">当前还没有记录生成版本信息。</p>
                )}
              </div>

              <div className={`${workspaceCardClass} space-y-3 p-4`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">再练闭环</p>
                    <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">
                      {selectedRecordMasteryTracking?.practiceSheetCount
                        ? `已生成 ${selectedRecordMasteryTracking.practiceSheetCount} 次练习`
                        : '这题还没有进入再练链路'}
                    </p>
                  </div>
                  {selectedRecordLatestPracticePreviewUrl ? (
                    <div className="flex flex-wrap gap-2">
                      <a
                        href={selectedRecordLatestPracticePreviewUrl}
                        target="_blank"
                        rel="noreferrer"
                        className={workspaceSecondaryButtonClass}
                      >
                        打开最近练习
                      </a>
                      {selectedRecordLatestPracticeDownloadUrl ? (
                        <a
                          href={selectedRecordLatestPracticeDownloadUrl}
                          className={workspaceSecondaryButtonClass}
                        >
                          下载最近练习
                        </a>
                      ) : null}
                    </div>
                  ) : null}
                </div>
                {selectedRecordMasteryTracking?.practiceSheetCount ? (
                  <div className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
                    <p>
                      最近练习：{getWrongQuestionPracticeStatusLabel(selectedRecordMasteryTracking.latestPracticeStatus || '')}
                      {selectedRecordMasteryTracking.latestPracticeCreatedAt ? ` · ${selectedRecordMasteryTracking.latestPracticeCreatedAt}` : ''}
                    </p>
                    {selectedRecordMasteryTracking.latestFollowupOutcome ? (
                      <p>
                        最近追问：{getWrongQuestionMasteryFollowupOutcomeLabel(selectedRecordMasteryTracking.latestFollowupOutcome)}
                        {selectedRecordMasteryTracking.latestFollowupCompletedAt ? ` · ${selectedRecordMasteryTracking.latestFollowupCompletedAt}` : ''}
                      </p>
                    ) : null}
                    <div className="flex flex-wrap gap-2">
                      {selectedRecordMasteryTracking.relatedTopicCategories.map((topic) => (
                        <span
                          key={`mastery-topic-${topic}`}
                          className="rounded-full border border-sky-100 bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700 dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-sky-300"
                        >
                          {topic}
                        </span>
                      ))}
                      {selectedRecordMasteryTracking.relatedErrorTypes.map((errorType) => (
                        <span
                          key={`mastery-error-${errorType}`}
                          className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600 dark:border-white/10 dark:bg-slate-900 dark:text-slate-300"
                        >
                          {errorType}
                        </span>
                      ))}
                    </div>
                    {selectedRecordMasteryTracking.latestFollowupSummary ? (
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        最近追问摘要：{selectedRecordMasteryTracking.latestFollowupSummary}
                      </p>
                    ) : null}
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      这层记录会继续作为后续掌握评级和相似错因复发判断的基础信号。
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-slate-500 dark:text-slate-400">确认后的 AI 归档题后续一旦进入练习，这里会直接显示最新再练状态。</p>
                )}
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                <div className={`${workspaceCardClass} space-y-3 p-4`}>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">来源素材</p>
                  {selectedRecordArchiveOriginalAssets.length > 0 ? (
                    <div className="grid gap-3 sm:grid-cols-2">
                      {selectedRecordArchiveOriginalAssets.map((asset) => {
                        const assetUrl = buildWrongQuestionAuthedPath(asset.fileUrl || asset.storagePath);
                        return (
                          <div key={`${asset.id}-${asset.assetRole}`} className="space-y-2 rounded-2xl border border-slate-200/80 bg-white/80 p-3 dark:border-white/10 dark:bg-slate-950/60">
                            {assetUrl ? (
                              <a href={assetUrl} target="_blank" rel="noreferrer" className="block overflow-hidden rounded-2xl border border-slate-200/80 dark:border-white/10">
                                <img src={assetUrl} alt={WRONG_QUESTION_INGESTION_ASSET_ROLE_LABELS[asset.assetRole] || asset.assetRole} className="max-h-44 w-full object-cover" />
                              </a>
                            ) : null}
                            <div className="text-xs text-slate-500 dark:text-slate-400">
                              <p className="font-semibold text-slate-700 dark:text-slate-200">{WRONG_QUESTION_INGESTION_ASSET_ROLE_LABELS[asset.assetRole] || asset.assetRole}</p>
                              <p>第 {asset.pageNumber || 1} 页</p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500 dark:text-slate-400">暂无来源素材</p>
                  )}
                </div>

                <div className={`${workspaceCardClass} space-y-3 p-4`}>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">OCR / 切题轨迹</p>
                  <div className="space-y-3">
                    <div className="rounded-2xl border border-slate-200/80 bg-white/80 p-3 text-sm text-slate-600 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-300">
                      当前步骤：{selectedRecord.linkedIngestionRun?.currentStep || '未记录'}
                    </div>
                    {selectedRecordArchiveTraceAssets.length > 0 ? selectedRecordArchiveTraceAssets.map((asset) => {
                      const metadata = parseWrongQuestionAssetMetadata(asset.metadataJson);
                      const assetUrl = buildWrongQuestionAuthedPath(asset.fileUrl || asset.storagePath);
                      return (
                        <div key={`${asset.id}-${asset.assetRole}`} className="rounded-2xl border border-slate-200/80 bg-white/80 p-3 dark:border-white/10 dark:bg-slate-950/60">
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div>
                              <p className="text-sm font-semibold text-slate-900 dark:text-white">{WRONG_QUESTION_INGESTION_ASSET_ROLE_LABELS[asset.assetRole] || asset.assetRole}</p>
                              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">第 {asset.pageNumber || 1} 页 · {asset.mimeType || '未知类型'}</p>
                            </div>
                            {assetUrl ? (
                              <a href={assetUrl} target="_blank" rel="noreferrer" className={workspaceSecondaryButtonClass}>查看素材</a>
                            ) : null}
                          </div>
                          {metadata ? (
                            <div className="mt-2 flex flex-wrap gap-2">
                              {Object.entries(metadata).map(([key, value]) => (
                                <span
                                  key={`${asset.id}-${key}`}
                                  className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600 dark:border-white/10 dark:bg-slate-900 dark:text-slate-300"
                                >
                                  {key}: {typeof value === 'string' || typeof value === 'number' ? String(value) : JSON.stringify(value)}
                                </span>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      );
                    }) : (
                      <p className="text-sm text-slate-500 dark:text-slate-400">还没有 OCR / 切题轨迹。</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {selectedDraft && selectedRecordMasteryAssessment ? (
        <div className={`${workspaceSoftCardClass} space-y-4 p-4`}>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-white">掌握证据</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">系统会结合老师确认、再练记录和同专题 / 同错因复发情况给出当前判断。</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-sky-100 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-sky-300">
                系统判断：{selectedRecordMasteryAssessment.label || '继续跟进'}
              </span>
              <span className="text-xs text-slate-500 dark:text-slate-400">证据评分 {selectedRecordMasteryAssessment.score}/4</span>
              {selectedRecordCanStartMasteryFollowup ? (
                <button
                  type="button"
                  onClick={() => void handleStartWrongQuestionMasteryFollowup()}
                  disabled={wrongQuestionChatSending}
                  className={workspaceSecondaryButtonClass}
                >
                  开启掌握追问
                </button>
              ) : null}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-slate-200/80 bg-white/80 p-3 dark:border-white/10 dark:bg-slate-950/60">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">建议下一步</p>
              <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">
                {getWrongQuestionMasterySuggestedActionLabel(selectedRecordMasteryAssessment.suggestedAction)}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200/80 bg-white/80 p-3 dark:border-white/10 dark:bg-slate-950/60">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">同专题未掌握</p>
              <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">
                {selectedRecordMasteryAssessment.sameTopicActiveCount} 条
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200/80 bg-white/80 p-3 dark:border-white/10 dark:bg-slate-950/60">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">同错因未掌握</p>
              <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">
                {selectedRecordMasteryAssessment.sameErrorActiveCount} 条
              </p>
            </div>
          </div>

          <div className="space-y-2 rounded-2xl border border-slate-200/80 bg-white/80 p-4 dark:border-white/10 dark:bg-slate-950/60">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">证据说明</p>
            {selectedRecordMasteryAssessment.evidence.length > 0 ? (
              <div className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
                {selectedRecordMasteryAssessment.evidence.map((item) => (
                  <p key={`mastery-evidence-${item}`}>{item}</p>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500 dark:text-slate-400">当前还没有足够证据，先保留老师判断。</p>
            )}
          </div>
        </div>
      ) : null}

      {selectedDraft && selectedRecord.source === 'wechat_mp' && (
        <div className={`${workspaceSoftCardClass} space-y-4 p-4`}>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-white">掌握情况</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">系统会先给出证据判断，老师仍可手动确认掌握状态。标记为已掌握后，后续错题练习会自动排除。</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void handleDeleteRecord()}
                disabled={savingReview}
                className="inline-flex items-center justify-center rounded-full border border-rose-200 bg-white px-4 py-2 text-sm font-semibold text-rose-600 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-400/30 dark:bg-slate-950/70 dark:text-rose-300 dark:hover:bg-rose-500/10"
              >
                删除本题
              </button>
              <button
                type="button"
                onClick={() => void handleSaveReview()}
                disabled={savingReview}
                className={workspacePrimaryButtonClass}
              >
                保存掌握情况
              </button>
            </div>
          </div>

          <label className="flex items-center gap-3 rounded-2xl border border-sky-100 bg-white/80 px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-slate-950/70 dark:text-slate-200">
            <input
              type="checkbox"
              checked={Boolean(selectedDraft.isMastered)}
              onChange={(event) => handleDraftChange('isMastered', (event.target as HTMLInputElement).checked)}
              className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            <span>是否掌握</span>
          </label>
        </div>
      )}

      {selectedDraft && selectedRecord.source !== 'wechat_mp' && (
        <div className={`${workspaceSoftCardClass} space-y-4 p-4`}>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-white">跟进记录</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">系统证据会和老师处理结果一起保留；保存失败后当前草稿不会丢。</p>
            </div>
            <div className="flex flex-wrap gap-3">
              {selectedRecord.source === 'ai_chat' ? (
                <>
                  <button
                    type="button"
                    onClick={() => void handleSaveReview('return_for_rework')}
                    disabled={savingReview}
                    className={workspaceSecondaryButtonClass}
                  >
                    退回待补充
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleSaveReview('edit_then_confirm')}
                    disabled={savingReview}
                    className={workspacePrimaryButtonClass}
                  >
                    编辑后确认
                  </button>
                </>
              ) : null}
              <button
                type="button"
                onClick={() => void handleSaveReview()}
                disabled={savingReview}
                className={workspaceSecondaryButtonClass}
              >
                保存跟进记录
              </button>
            </div>
          </div>

          {selectedRecord.source === 'ai_chat' ? (
            <label className="flex items-center gap-3 rounded-2xl border border-sky-100 bg-white/80 px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-slate-950/70 dark:text-slate-200">
              <input
                type="checkbox"
                checked={Boolean(selectedDraft.isMastered)}
                onChange={(event) => handleDraftChange('isMastered', (event.target as HTMLInputElement).checked)}
                className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
              />
              <span>本题已掌握，后续周跟进可不再优先推送</span>
            </label>
          ) : null}

          {selectedRecord.source === 'ai_chat' ? (
            <label className="flex items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-800 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-200">
              <input
                type="checkbox"
                checked={Boolean(selectedDraft.needsTeacherConfirmation)}
                onChange={(event) => handleDraftChange('needsTeacherConfirmation', (event.target as HTMLInputElement).checked)}
                className="h-4 w-4 rounded border-amber-300 text-amber-600 focus:ring-amber-500"
              />
              <span>仍需老师复核</span>
            </label>
          ) : null}

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-2 text-sm sm:col-span-2">
              <span className="text-slate-500 dark:text-slate-400">最终问题归类</span>
              <select
                aria-label="最终问题归类"
                value={selectedDraft.selectedErrorType}
                onChange={(event) => handleDraftChange('selectedErrorType', event.target.value)}
                className={workspaceFieldClass}
              >
                <option value="">请选择问题归类</option>
                {finalErrorTypeOptions.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">核心知识点</span>
              <textarea
                value={selectedKnowledgePointText}
                onChange={(event) => handleDraftChange('selectedKnowledgePoints', event.target.value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                onInput={(event) => handleDraftChange('selectedKnowledgePoints', (event.target as HTMLTextAreaElement).value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                className={`${workspaceFieldClass} min-h-28 resize-y`}
                placeholder="每行一个知识点"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">后续练习建议</span>
              <textarea
                value={selectedActionsText}
                onChange={(event) => handleDraftChange('selectedActions', event.target.value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                onInput={(event) => handleDraftChange('selectedActions', (event.target as HTMLTextAreaElement).value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                className={`${workspaceFieldClass} min-h-28 resize-y`}
                placeholder="每行一个后续动作"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">原因分析</span>
              <textarea
                value={selectedReasonsText}
                onChange={(event) => handleDraftChange('selectedReasons', event.target.value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                onInput={(event) => handleDraftChange('selectedReasons', (event.target as HTMLTextAreaElement).value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                className={`${workspaceFieldClass} min-h-28 resize-y`}
                placeholder="每行一个原因"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">教师备注</span>
              <textarea
                value={selectedDraft.studentNote}
                onChange={(event) => handleDraftChange('studentNote', event.target.value)}
                onInput={(event) => handleDraftChange('studentNote', (event.target as HTMLTextAreaElement).value)}
                className={`${workspaceFieldClass} min-h-28 resize-y`}
                placeholder="补充学生当前表现或教师备注"
              />
            </label>
          </div>
        </div>
      )}
    </>
  ) : (
    <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
      请先选择学生查看这个孩子的错题本。
    </div>
  );

  return (
    <div className={`${workspacePageClass} space-y-8`}>
      <section className={`${workspaceCardClass} space-y-4 p-6`}>
        <p className="text-sm uppercase tracking-[0.25em] text-sky-600">错题跟进</p>
        <div>
          <h3 className="text-2xl font-bold text-slate-900 dark:text-white">智能错题</h3>
          <p className="mt-2 max-w-3xl text-sm text-slate-500 dark:text-slate-400">
            {hasStaffScope ? '按班级或学生查看错题本。' : '查看负责范围内错题。'}
          </p>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{currentUser.display_name}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">错题总数</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{summary.totalCount}</p>
          </div>
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">未掌握</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{summary.pendingReviewCount}</p>
          </div>
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">负责班级</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{summary.uniqueClassCount}</p>
          </div>
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">负责学生</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{summary.uniqueStudentCount}</p>
          </div>
        </div>
      </section>

      {error && (
        <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <section className={`${workspaceCardClass} space-y-5 p-6`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h4 className="text-xl font-semibold text-slate-900 dark:text-white">学生错题本</h4>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {hasStaffScope
                ? '先按筛选条件缩小范围，再选择班级并打开学生卡片查看错题本。'
                : '先选择班级，再打开学生卡片查看这个孩子的错题库。'}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            {canViewWeeklyActivitySummary && (
              <button
                type="button"
                onClick={() => setWeeklyActivityOpen((current) => !current)}
                className={workspaceSecondaryButtonClass}
              >
                本周数据总结
              </button>
            )}
            <button
              type="button"
              onClick={() => setWeeklyFollowupOpen((current) => !current)}
              className={workspaceSecondaryButtonClass}
            >
              每周练习跟进
            </button>
            <button
              type="button"
              onClick={() => void loadList(filters)}
              disabled={loading}
              className={workspaceSecondaryButtonClass}
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              刷新列表
            </button>
          </div>
        </div>

        {canViewWeeklyActivitySummary && weeklyActivityOpen && (
          <div className={`${workspaceSoftCardClass} space-y-4 p-4`}>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">本周数据总结</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">按周查看错题活跃情况</p>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">周次</span>
                  <input
                    aria-label="数据总结周次"
                    type="date"
                    value={weeklyActivityWeekStart}
                    onChange={(event) => setWeeklyActivityWeekStart(event.target.value)}
                    className={workspaceFieldClass}
                  />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">机构</span>
                  <select
                    aria-label="机构"
                    value={weeklyActivityOrganizationId ?? ''}
                    onChange={(event) => {
                      const nextValue = Number(event.target.value);
                      setWeeklyActivityOrganizationId(Number.isFinite(nextValue) && nextValue > 0 ? nextValue : null);
                    }}
                    className={workspaceFieldClass}
                  >
                    <option value="">全部机构</option>
                    {organizationOptions.map((item) => (
                      <option key={item.id} value={item.id}>{item.name}</option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() => void handleLoadWeeklyActivitySummary()}
                  disabled={weeklyActivityLoading}
                  className={workspacePrimaryButtonClass}
                >
                  {weeklyActivityLoading ? '正在加载' : '加载总结'}
                </button>
              </div>
            </div>

            {weeklyActivityError && (
              <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                <AlertCircle size={16} />
                {weeklyActivityError}
              </div>
            )}

            {weeklyActivityNotice && (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-300">
                {weeklyActivityNotice}
              </div>
            )}

            {weeklyActivitySummary && !weeklyActivityHasItems && (
              <p className="rounded-xl border border-dashed border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-400">
                本周暂无错题活跃数据
              </p>
            )}

            {weeklyActivityHasItems && weeklyActivitySummary && (
              <div className="grid gap-3 xl:grid-cols-3">
                <section className="space-y-2">
                  <h5 className="text-sm font-semibold text-slate-900 dark:text-white">本周活跃班级</h5>
                  {weeklyActivitySummary.classItems.length === 0 ? (
                    <p className="rounded-xl border border-dashed border-slate-200 bg-white px-4 py-5 text-sm text-slate-500 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-400">暂无班级数据</p>
                  ) : (
                    weeklyActivitySummary.classItems.map((item) => (
                      <article key={`${item.organizationId}-${item.classId}`} className="min-w-0 rounded-xl border border-slate-200/80 bg-white p-3 dark:border-white/10 dark:bg-slate-950/60">
                        <p className="min-w-0 break-words text-sm font-semibold text-slate-900 dark:text-white">{item.className || '未命名班级'}</p>
                        <p className="mt-1 min-w-0 break-words text-xs text-slate-500 dark:text-slate-400">{item.organizationName || '未标注机构'}</p>
                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                          <span>{item.weeklyQuestionCount}题</span>
                          <span>{item.uploadingStudentCount}名学生</span>
                        </div>
                      </article>
                    ))
                  )}
                </section>

                <section className="space-y-2">
                  <h5 className="text-sm font-semibold text-slate-900 dark:text-white">本周活跃老师</h5>
                  {weeklyActivitySummary.teacherItems.length === 0 ? (
                    <p className="rounded-xl border border-dashed border-slate-200 bg-white px-4 py-5 text-sm text-slate-500 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-400">暂无老师数据</p>
                  ) : (
                    weeklyActivitySummary.teacherItems.map((item) => (
                      <article key={`${item.organizationId}-${item.teacherUserId}`} className="min-w-0 rounded-xl border border-slate-200/80 bg-white p-3 dark:border-white/10 dark:bg-slate-950/60">
                        <p className="min-w-0 break-words text-sm font-semibold text-slate-900 dark:text-white">{item.teacherName || '未标注老师'}</p>
                        <p className="mt-1 min-w-0 break-words text-xs text-slate-500 dark:text-slate-400">{item.organizationName || '未标注机构'}</p>
                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                          <span>{item.weeklyQuestionCount}题</span>
                          <span>{item.classCount}个班级</span>
                          <span>{item.involvedStudentCount}名学生</span>
                          <span>{item.pendingFollowupCount}待跟进</span>
                        </div>
                      </article>
                    ))
                  )}
                </section>

                <section className="space-y-2">
                  <h5 className="text-sm font-semibold text-slate-900 dark:text-white">本周活跃学生</h5>
                  {weeklyActivitySummary.studentItems.length === 0 ? (
                    <p className="rounded-xl border border-dashed border-slate-200 bg-white px-4 py-5 text-sm text-slate-500 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-400">暂无学生数据</p>
                  ) : (
                    weeklyActivitySummary.studentItems.map((item) => {
                      const activitySummaryFollowupRecord = item.sourceRecords[0] ?? null;
                      const canStartActivitySummaryFollowup = Boolean(activitySummaryFollowupRecord || item.sourceRecordIds[0]);
                      return (
                        <article key={`${item.organizationId}-${item.classId}-${item.studentId}`} className="min-w-0 rounded-xl border border-slate-200/80 bg-white p-3 dark:border-white/10 dark:bg-slate-950/60">
                          <p className="min-w-0 break-words text-sm font-semibold text-slate-900 dark:text-white">{item.studentName || '未命名学生'}</p>
                          <p className="mt-1 min-w-0 break-words text-xs text-slate-500 dark:text-slate-400">{item.className || '未标注班级'} · {item.organizationName || '未标注机构'}</p>
                          <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                            <span>本周{item.weeklyQuestionCount}题</span>
                            <span>累计{item.totalQuestionCount}题</span>
                            {item.topicCategories.slice(0, 3).map((topic) => (
                              <span key={topic} className="rounded-full border border-sky-100 bg-sky-50 px-2 py-0.5 font-semibold text-sky-700 dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-sky-300">
                                {topic}
                              </span>
                            ))}
                          </div>
                          {canStartActivitySummaryFollowup ? (
                            <span className="mt-3 flex">
                              <button
                                type="button"
                                aria-label={`为本周活跃学生 ${item.studentName} 开启掌握追问`}
                                onClick={() => void handleStartWeeklyActivitySummaryMasteryFollowup(item, activitySummaryFollowupRecord)}
                                disabled={wrongQuestionChatSending}
                                className={workspacePrimaryButtonClass}
                              >
                                开启掌握追问
                              </button>
                            </span>
                          ) : null}
                        </article>
                      );
                    })
                  )}
                </section>
              </div>
            )}
          </div>
        )}

        {weeklyFollowupOpen && (
          <div className={`${workspaceSoftCardClass} space-y-4 p-4`}>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">网页智能错题</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">每周练习跟进</p>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">周次</span>
                  <input
                    aria-label="周次"
                    type="date"
                    value={weeklyFollowupWeekStart}
                    onChange={(event) => {
                      resetWeeklyFollowupContext();
                      setWeeklyFollowupWeekStart(event.target.value);
                    }}
                    className={workspaceFieldClass}
                  />
                </label>
                <button
                  type="button"
                  onClick={() => void handleLoadWeeklyFollowups()}
                  disabled={weeklyFollowupLoading}
                  className={workspacePrimaryButtonClass}
                >
                  {weeklyFollowupLoading ? '正在加载' : '查看跟进清单'}
                </button>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">方式</span>
                  <select
                    aria-label="练习包模式"
                    value={practicePackMode}
                    onChange={(event) => setPracticePackMode(event.target.value === 'reason' ? 'reason' : 'topic')}
                    className={workspaceFieldClass}
                  >
                    <option value="topic">按专题</option>
                    <option value="reason">按错因</option>
                  </select>
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">方向</span>
                  <select
                    aria-label="练习包方向"
                    value={practicePackTarget}
                    onChange={(event) => setPracticePackTarget(event.target.value)}
                    className={workspaceFieldClass}
                  >
                    {practicePackTargetOptions.length > 0 ? (
                      practicePackTargetOptions.map((item) => (
                        <option key={item} value={item}>{item}</option>
                      ))
                    ) : (
                      <option value="">暂无可选方向</option>
                    )}
                  </select>
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">题量</span>
                  <select
                    aria-label="练习包题量"
                    value={practicePackVolume}
                    onChange={(event) => {
                      const nextVolume = event.target.value;
                      setPracticePackVolume(nextVolume === 'light' || nextVolume === 'intensive' ? nextVolume : 'standard');
                    }}
                    className={workspaceFieldClass}
                  >
                    <option value="light">轻量</option>
                    <option value="standard">标准</option>
                    <option value="intensive">强化</option>
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() => void handleGeneratePracticePack()}
                  disabled={practicePackGenerating}
                  className={workspaceSecondaryButtonClass}
                >
                  {practicePackGenerating ? '正在生成' : '生成并下载一周练习包'}
                </button>
              </div>
            </div>

            {weeklyFollowupError && (
              <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                <AlertCircle size={16} />
                {weeklyFollowupError}
              </div>
            )}

            {weeklyFollowupNotice && (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-300">
                {weeklyFollowupNotice}
              </div>
            )}

            {practicePackJobs.length > 0 && (
              <div className="space-y-3">
                <p className="text-sm font-semibold text-slate-900 dark:text-white">已生成练习包</p>
                {practicePackJobs.map((practicePackJob) => {
                  const practicePackDownloadUrl = practicePackJob.downloadUrl
                    ? buildWrongQuestionAuthedPath(practicePackJob.downloadUrl)
                    : '';
                  return (
                    <div key={practicePackJob.id} className="rounded-xl border border-slate-200/80 bg-white p-4 dark:border-white/10 dark:bg-slate-950/60">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <p className="text-sm font-semibold text-slate-900 dark:text-white">{practicePackJob.target || '未命名练习包'}</p>
                          <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500 dark:text-slate-400">
                            <span>状态：{getPracticePackStatusLabel(practicePackJob.status)}</span>
                            <span>{practicePackJob.requestedQuestionCount}题</span>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-3">
                          <button
                            type="button"
                            onClick={() => void handleRefreshPracticePackJob(practicePackJob.id)}
                            className={workspaceSecondaryButtonClass}
                          >
                            刷新状态
                          </button>
                          {practicePackDownloadUrl ? (
                            <a
                              href={practicePackDownloadUrl}
                              target="_blank"
                              rel="noreferrer"
                              className={workspacePrimaryButtonClass}
                            >
                              下载练习包
                            </a>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {weeklyFollowupItems.length > 0 && (
              <div className="grid gap-3 md:grid-cols-2">
                {weeklyFollowupItems.map((item) => {
                  const messageText = item.message?.messageText.trim() ?? '';
                  const practicePdfUrl = item.practiceSheet?.pdfUrl
                    ? buildWrongQuestionAuthedPath(item.practiceSheet.pdfUrl)
                    : item.practiceSheet?.downloadUrl
                      ? buildWrongQuestionAuthedPath(item.practiceSheet.downloadUrl)
                      : '';
                  const isReadyPractice = item.status === 'has_practice_sheet' && item.practiceSheet?.status === 'ready';
                  const needsPractice = item.status === 'needs_practice_sheet';
                  const latestSourceRecord = item.sourceRecords[0] ?? null;
                  const latestAiChatSourceRecord = item.sourceRecords.find((record) => record.source === 'ai_chat') ?? null;
                  const hasAiChatSource = Boolean(latestAiChatSourceRecord);
                  return (
                    <article key={item.studentId} className="rounded-2xl border border-slate-200/80 bg-white p-4 dark:border-white/10 dark:bg-slate-950/60">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-base font-semibold text-slate-900 dark:text-white">{item.studentName}</p>
                          <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                            <span>
                              {isReadyPractice ? `本周练习 ${item.weeklyQuestionCount}题` : needsPractice ? `可练 ${item.candidateQuestionCount}题` : '暂无可练错题'}
                            </span>
                            {needsPractice && item.recommendedCategory ? <span>建议：{item.recommendedCategory}</span> : null}
                            {item.repeatedCategoryCount > 1 && item.repeatedCategory ? <span>复发：{item.repeatedCategory} {item.repeatedCategoryCount}次</span> : null}
                            {hasAiChatSource ? (
                              <span className="rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 font-semibold text-violet-700 dark:border-violet-500/20 dark:bg-violet-500/10 dark:text-violet-300">
                                AI 对话归档
                              </span>
                            ) : null}
                            {item.topicCategories.slice(0, 3).map((topic) => (
                              <span key={topic} className="rounded-full border border-sky-100 bg-sky-50 px-2 py-0.5 font-semibold text-sky-700 dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-sky-300">
                                {topic}
                              </span>
                            ))}
                          </div>
                          {needsPractice && item.recommendationReason ? (
                            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{item.recommendationReason}</p>
                          ) : null}
                        </div>
                        {practicePdfUrl && (
                          <a
                            href={practicePdfUrl}
                            target="_blank"
                            rel="noreferrer"
                            className={workspaceSecondaryButtonClass}
                          >
                            打开练习 PDF
                          </a>
                        )}
                      </div>
                      {messageText ? (
                        <p className="mt-4 whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-200">
                          {messageText}
                        </p>
                      ) : null}
                      <div className="mt-4 flex flex-wrap gap-3">
                        {needsPractice ? (
                          <button
                            type="button"
                            onClick={() => void handleGenerateWeeklyPracticeSheet(item.studentId)}
                            disabled={generatingWeeklyPracticeStudentId === item.studentId}
                            className={workspacePrimaryButtonClass}
                          >
                            {generatingWeeklyPracticeStudentId === item.studentId ? '正在提交' : '让 AI 生成练习'}
                          </button>
                        ) : null}
                        {latestSourceRecord ? (
                          <button
                            type="button"
                            onClick={() => handleOpenWeeklyFollowupSourceRecord(item)}
                            className={workspaceSecondaryButtonClass}
                          >
                            打开最近归档
                          </button>
                        ) : null}
                        {latestAiChatSourceRecord ? (
                          <button
                            type="button"
                            onClick={() => handleOpenWeeklyFollowupSourceRecord(item, latestAiChatSourceRecord.id)}
                            className={workspaceSecondaryButtonClass}
                          >
                            打开 AI 归档
                          </button>
                        ) : null}
                        {latestAiChatSourceRecord && canStartWrongQuestionMasteryFollowup(latestAiChatSourceRecord) ? (
                          <button
                            type="button"
                            onClick={() => void handleStartWeeklyFollowupMasteryFollowup(item, latestAiChatSourceRecord)}
                            disabled={wrongQuestionChatSending}
                            className={workspaceSecondaryButtonClass}
                          >
                            开启掌握追问
                          </button>
                        ) : null}
                        {isReadyPractice ? (
                          <button
                            type="button"
                            onClick={() => void handleGenerateWeeklyFollowupMessage(item.studentId)}
                            disabled={generatingWeeklyFollowupStudentId === item.studentId}
                            className={workspacePrimaryButtonClass}
                          >
                            {generatingWeeklyFollowupStudentId === item.studentId ? '正在生成' : messageText ? '重新生成话术' : '生成话术'}
                          </button>
                        ) : null}
                        {messageText ? (
                          <button
                            type="button"
                            onClick={() => void handleCopyWeeklyFollowupMessage(messageText)}
                            className={workspaceSecondaryButtonClass}
                          >
                            复制
                          </button>
                        ) : null}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {hasStaffScope && (
          <form className="grid gap-4 lg:grid-cols-3" onSubmit={handleSubmit}>
            <div className="flex flex-wrap gap-3 lg:col-span-3">
              <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700 dark:border-amber-400/30 dark:bg-amber-500/10 dark:text-amber-300">
                待老师复核 {pendingTeacherConfirmationCount}
              </span>
              <span className="inline-flex items-center rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
                已退回 {returnedTeacherConfirmationCount}
              </span>
            </div>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">学生姓名</span>
              {selectedStaffClassOption ? (
                <select
                  aria-label="学生姓名"
                  value={filters.studentName ?? ''}
                  onChange={(event) => handleFilterChange('studentName', event.target.value)}
                  className={workspaceFieldClass}
                >
                  <option value="">全部学生</option>
                  {studentOptions.map((item) => (
                    <option key={item.id} value={item.name}>{item.name}</option>
                  ))}
                </select>
              ) : (
                <input
                  aria-label="学生姓名"
                  type="text"
                  value={filters.studentName ?? ''}
                  onChange={(event) => handleFilterChange('studentName', event.target.value)}
                  className={workspaceFieldClass}
                  placeholder="如：Alice"
                />
              )}
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">班级</span>
              <select
                aria-label="班级"
                value={selectedStaffClassOption ? String(selectedStaffClassOption.id) : ''}
                onChange={(event) => handleStaffClassChange(event.target.value)}
                className={workspaceFieldClass}
              >
                <option value="">全部班级</option>
                {visibleClassOptions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.subject ? `${item.name} · ${item.subject}` : item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">科目</span>
              <select
                aria-label="科目"
                value={filters.subject ?? ''}
                onChange={(event) => handleFilterChange('subject', event.target.value)}
                className={workspaceFieldClass}
              >
                <option value="">全部科目</option>
                {subjectOptions.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">老师</span>
              <select
                aria-label="老师"
                value={filters.teacherName ?? ''}
                onChange={(event) => handleFilterChange('teacherName', event.target.value)}
                className={workspaceFieldClass}
              >
                <option value="">全部老师</option>
                {teacherOptions.map((item) => (
                  <option key={item.id} value={item.name}>{item.name}</option>
                ))}
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">问题归类</span>
              <select
                aria-label="问题归类筛选"
                value={filters.errorType ?? ''}
                onChange={(event) => handleFilterChange('errorType', event.target.value)}
                className={workspaceFieldClass}
              >
                <option value="">全部问题归类</option>
                {WRONG_QUESTION_ERROR_TYPE_OPTIONS.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">老师复核</span>
              <select
                aria-label="老师复核"
                value={filters.confirmationState ?? ''}
                onChange={(event) => handleFilterChange('confirmationState', event.target.value)}
                className={workspaceFieldClass}
              >
                <option value="">全部状态</option>
                <option value="pending">待老师复核</option>
                <option value="returned">已退回</option>
                <option value="confirmed">已确认</option>
              </select>
            </label>
            <div className="flex flex-wrap gap-3 lg:col-span-3 lg:justify-end">
              <button
                type="button"
                onClick={() => {
                  setFilters(initialFilters);
                  void loadList(initialFilters);
                }}
                disabled={loading}
                className={workspaceSecondaryButtonClass}
              >
                重置筛选
              </button>
              <button type="submit" disabled={loading} className={workspacePrimaryButtonClass}>
                应用筛选
              </button>
            </div>
          </form>
        )}

        {!hasStaffScope && (
          <label className="space-y-2 text-sm">
            <span className="text-slate-500 dark:text-slate-400">班级</span>
            <select
              aria-label="班级"
              value={selectedClassId ? String(selectedClassId) : ''}
              onChange={(event) => handleMemberClassChange(event.target.value)}
              className={workspaceFieldClass}
            >
              <option value="">请选择班级</option>
              {classOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.subject ? `${item.name} · ${item.subject}` : item.name}
                </option>
              ))}
            </select>
          </label>
        )}

        {!activeNotebookClassId ? (
          <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
            请选择班级查看学生错题本。
          </div>
        ) : loading ? (
          <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
            正在加载学生错题本...
          </div>
        ) : memberNotebookSummaries.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
            当前班级下暂无错题记录。
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {memberNotebookSummaries.map((item) => {
              const isActive = item.studentName === selectedStudentName;
              const summaryFollowupRecord = memberNotebookSummaryMasteryFollowupRecordByStudentName.get(item.studentName) ?? null;
              return (
                <article
                  key={`${item.classId}-${item.studentName}`}
                  className={`${workspaceSoftCardClass} w-full p-5 text-left transition ${isActive ? 'border-sky-400 shadow-[0_18px_48px_rgba(47,128,237,0.12)]' : ''}`}
                >
                  <button
                    type="button"
                    onClick={() => handleOpenMemberNotebook(item.studentName)}
                    className="w-full text-left"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-lg font-semibold text-slate-900 dark:text-white">{item.studentName}</p>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{item.className}</p>
                      </div>
                      {item.hasTeacherFollowUp ? (
                        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300">
                          已掌握
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-4 flex flex-wrap gap-3 text-sm text-slate-500 dark:text-slate-400">
                      <span className="whitespace-nowrap">{item.totalCount}题</span>
                      <span className="whitespace-nowrap">{item.pendingReviewCount}未掌握</span>
                    </div>
                  </button>
                  {summaryFollowupRecord ? (
                    <span className="mt-4 flex">
                      <button
                        type="button"
                        aria-label={`为 ${item.studentName} 开启掌握追问`}
                        onClick={() => void handleStartMemberNotebookSummaryMasteryFollowup(summaryFollowupRecord)}
                        disabled={wrongQuestionChatSending}
                        className={workspacePrimaryButtonClass}
                      >
                        开启掌握追问
                      </button>
                    </span>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </section>

      {selectedStudentName && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4 py-6 backdrop-blur-sm"
          onClick={(event) => event.target === event.currentTarget && handleCloseMemberNotebook()}
        >
          <div className="flex max-h-[92vh] w-full max-w-7xl flex-col overflow-hidden rounded-[28px] border border-sky-100 bg-white shadow-[0_32px_90px_rgba(15,23,42,0.22)] dark:border-white/10 dark:bg-slate-950">
            <div className="flex items-start justify-between gap-4 border-b border-slate-200/80 px-6 py-5 dark:border-white/10">
              <div>
                <h4 className="text-2xl font-semibold text-slate-900 dark:text-white">{selectedStudentName} 的错题库</h4>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">左侧最新上传的题目排在最上方，题号保持原始上传顺序。</p>
              </div>
              <button
                type="button"
                onClick={handleCloseMemberNotebook}
                className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 text-slate-500 transition hover:border-slate-300 hover:text-slate-900 dark:border-white/10 dark:text-slate-400 dark:hover:text-white"
                aria-label="关闭错题库"
              >
                <X size={18} />
                <span className="sr-only">关闭错题库</span>
              </button>
            </div>

            <div className="grid min-h-0 flex-1 gap-0 xl:grid-cols-[minmax(20rem,25rem)_minmax(0,1fr)]">
              <div className="min-h-0 overflow-y-auto border-b border-slate-200/80 p-5 dark:border-white/10 xl:border-b-0 xl:border-r">
                <div className="mb-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setNotebookModalView('questions')}
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition ${notebookModalView === 'questions' ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-950' : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-300 dark:hover:text-white'}`}
                  >
                    错题目录
                  </button>
                  <button
                    type="button"
                    onClick={() => setNotebookModalView('practice_history')}
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition ${notebookModalView === 'practice_history' ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-950' : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-300 dark:hover:text-white'}`}
                  >
                    错题练习记录
                  </button>
                </div>

                {notebookModalView === 'questions' ? (
                  <>
                    <div className={`${workspaceSoftCardClass} mb-4 space-y-3 p-4`}>
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-900 dark:text-white">错题目录</p>
                          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">最新上传的题目排在最上方，题号沿用上传顺序。勾选后可直接生成一份错题练习。</p>
                        </div>
                        <span className="whitespace-nowrap rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                          {memberNotebookRecords.length}题
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="掌握状态筛选">
                        {([
                          { value: 'all', label: '全部' },
                          { value: 'pending', label: '未掌握' },
                          { value: 'mastered', label: '已掌握' },
                        ] as const).map((option) => {
                          const active = notebookMasteryFilter === option.value;
                          return (
                            <button
                              key={option.value}
                              type="button"
                              aria-pressed={active}
                              onClick={() => setNotebookMasteryFilter(option.value)}
                              className={`rounded-full px-3 py-1 text-xs font-semibold transition ${active ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-950' : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-300 dark:hover:text-white'}`}
                            >
                              {option.label}
                            </button>
                          );
                        })}
                        <span className="ml-auto whitespace-nowrap text-xs text-slate-500 dark:text-slate-400">
                          当前显示 {displayedNotebookRecords.length}题
                        </span>
                      </div>
                      {showNotebookTopicCategory ? (
                        <div className="space-y-2">
                          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">专题分类</p>
                          <div className="flex flex-wrap items-center gap-2" role="group" aria-label="小学专题筛选">
                            {notebookTopicSummaries.map((item) => {
                              const active = notebookTopicFilter === item.topicCategory;
                              return (
                                <button
                                  key={item.topicCategory}
                                  type="button"
                                  aria-pressed={active}
                                  onClick={() => setNotebookTopicFilter(item.topicCategory)}
                                  className={`rounded-full px-3 py-1 text-xs font-semibold transition ${active ? 'bg-sky-600 text-white dark:bg-sky-400 dark:text-slate-950' : 'border border-sky-100 bg-white text-sky-700 hover:border-sky-200 dark:border-sky-500/20 dark:bg-slate-950/60 dark:text-sky-300'}`}
                                >
                                  {item.topicCategory} · {item.count}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ) : null}
                      <div className="flex flex-col gap-3">
                        <p className="text-sm text-slate-500 dark:text-slate-400">已选择 {selectedPracticeCount} 题</p>
                        <button
                          type="button"
                          onClick={() => void handleCreatePracticeSheet()}
                          disabled={creatingPractice || selectedPracticeCount === 0}
                          className={workspacePrimaryButtonClass}
                        >
                          生成错题练习
                        </button>
                      </div>
                    </div>

                    <div className="space-y-2">
                      {displayedNotebookRecords.length === 0 ? (
                        <p className="rounded-xl border border-dashed border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-400">
                          当前筛选下没有匹配的错题。
                        </p>
                      ) : null}
                      {displayedNotebookRecords.map((item) => {
                        const active = item.id === selectedRecord?.id;
                        const questionNumber = memberNotebookQuestionNumberById.get(item.id) ?? 0;
                        const canSelect = canGenerateWrongQuestionPractice(item);
                        const canStartMasteryFollowupFromDirectory = canStartWrongQuestionMasteryFollowup(item);
                        const checked = effectiveSelectedPracticeRecordIds.includes(item.id);
                        return (
                          <div
                            key={item.id}
                            className={`flex items-start gap-3 rounded-xl border px-3 py-3 transition ${active ? 'border-sky-400 bg-sky-50/70 dark:bg-sky-500/10' : 'border-slate-200/80 bg-white dark:border-white/10 dark:bg-slate-950/60'}`}
                          >
                            <input
                              type="checkbox"
                              aria-label={`选择第 ${questionNumber} 题`}
                              checked={checked}
                              disabled={!canSelect}
                              onChange={(event) => handlePracticeRecordCheckedChange(item.id, (event.target as HTMLInputElement).checked)}
                              onChangeCapture={(event) => handlePracticeRecordCheckedChange(item.id, (event.target as HTMLInputElement).checked)}
                              className="mt-1 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
                            />
                            <button
                              type="button"
                              onClick={() => setSelectedId(item.id)}
                              className="min-w-0 flex-1 text-left"
                            >
                              <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
                                <span className="font-semibold text-slate-900 dark:text-white">第 {questionNumber} 题</span>
                                <span className="text-slate-500 dark:text-slate-400">{item.createdAt || '未记录时间'}</span>
                                <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${item.isMastered ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300' : 'border-slate-200 bg-white/80 text-slate-600 dark:border-white/10 dark:bg-slate-900 dark:text-slate-300'}`}>
                                  {item.isMastered ? '已掌握' : '未掌握'}
                                </span>
                                {isPrimarySchoolWrongQuestionRecord(item) ? (
                                  <span className="rounded-full border border-sky-100 bg-sky-50 px-2.5 py-1 text-[11px] font-semibold text-sky-700 dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-sky-300">
                                    {item.topicCategory || '未分类'}
                                  </span>
                                ) : null}
                              </div>
                              {!canSelect ? (
                                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                                  {item.isMastered
                                    ? '已掌握题目不会加入新的错题练习。'
                                    : item.source === 'ai_chat'
                                      ? 'AI 归档题需要先完成老师确认或补充后，才能加入错题练习。'
                                      : '当前题目还不能加入错题练习。'}
                                </p>
                              ) : null}
                            </button>
                            {canStartMasteryFollowupFromDirectory ? (
                              <button
                                type="button"
                                aria-label={`对第 ${questionNumber} 题开启掌握追问`}
                                onClick={() => void handleStartNotebookDirectoryMasteryFollowup(item)}
                                disabled={wrongQuestionChatSending}
                                className="shrink-0 rounded-full border border-sky-200 bg-white px-3 py-1.5 text-xs font-semibold text-sky-700 transition hover:border-sky-300 hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-sky-500/30 dark:bg-slate-950/70 dark:text-sky-300 dark:hover:bg-sky-500/10"
                              >
                                开启掌握追问
                              </button>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  </>
                ) : (
                  <div className={`${workspaceSoftCardClass} space-y-3 p-4`}>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">错题练习记录</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">查看这个学生已经生成过的错题练习，生成完成后可直接打开 PDF。</p>
                    <span className="whitespace-nowrap rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                      {practiceSheets.length}份记录
                    </span>
                  </div>
                )}
              </div>

              <div className="min-h-0 overflow-y-auto p-5">
                {practiceActionNotice && (
                  <div className="mb-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-300">
                    {practiceActionNotice}
                  </div>
                )}

                {practiceActionError && (
                  <div className="mb-4 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                    <AlertCircle size={16} />
                    {practiceActionError}
                  </div>
                )}

                {practiceHistoryError && notebookModalView === 'practice_history' && (
                  <div className="mb-4 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                    <AlertCircle size={16} />
                    {practiceHistoryError}
                  </div>
                )}

                {notebookModalView === 'questions' ? (
                  <>
                    {wrongQuestionChatPanel}
                    {detailHeader}

                    {detailError && (
                      <div className="mb-4 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                        <AlertCircle size={16} />
                        {detailError}
                      </div>
                    )}

                    {saveError && (
                      <div className="mb-4 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                        <AlertCircle size={16} />
                        {saveError}
                      </div>
                    )}

                    {pdfRefreshNotice && (
                      <div className="mb-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-300">
                        {pdfRefreshNotice}
                      </div>
                    )}

                    <div className="space-y-5">{detailPanel}</div>
                  </>
                ) : (
                  practiceHistoryPanel
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
