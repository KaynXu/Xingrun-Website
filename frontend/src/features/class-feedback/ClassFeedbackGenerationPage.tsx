import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { AlertCircle, CheckCheck, Copy, FileAudio, History, Sparkles, Upload } from 'lucide-react';

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import type { ClassItem, CurrentUser } from '../../appTypes';
import {
  areClassCommentaryStudentFeedbackItemsEqual,
  activateClassCommentarySkillVersion,
  buildClassCommentaryFeedbackWorkspaceKey,
  buildClassCommentaryRevisionPreviewKey,
  classCommentaryStatusLabel,
  CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
  createClassCommentarySkillCandidate,
  createClassCommentaryTask,
  createClassCommentaryTextTask,
  confirmClassCommentaryFeedback,
  deriveClassCommentaryStructuredFeedbackText,
  fetchClassCommentaryCapabilities,
  fetchClassCommentaryFeedbackDraft,
  fetchClassCommentaryFeedbackRevisions,
  fetchClassCommentaryGeneration,
  fetchClassCommentaryGenerations,
  fetchClassCommentaryRevisionMemories,
  fetchClassCommentarySkillEvolution,
  fetchClassCommentarySkills,
  fetchClassCommentaryTasks,
  fetchClassCommentaryTask,
  generateClassCommentaryFeedback,
  formatClassCommentaryStudentFeedback,
  isClassCommentaryFeedbackRecordInScope,
  isClassCommentaryTaskLatestSchemaCompatible,
  normalizeClassCommentaryFeedbackDraft,
  normalizeClassCommentaryFeedbackRevision,
  normalizeClassCommentaryGeneration,
  normalizeClassCommentaryTask,
  readClassCommentarySkillPreference,
  rollbackClassCommentarySkillVersion,
  retryClassCommentaryRevisionMemory,
  resolveClassCommentaryCopyText,
  resolveClassCommentaryStudentFeedbackItems,
  revokeClassCommentaryMemoryEvidence,
  saveClassCommentaryFeedbackDraft,
  saveClassCommentaryTranscript,
  shouldPollClassCommentaryTask,
  type ClassCommentarySkill,
  type ClassCommentarySkillCandidateBuildStatus,
  type ClassCommentaryCapabilities,
  type ClassCommentaryFeedbackDraft,
  type ClassCommentaryFeedbackRevision,
  type ClassCommentaryFeedbackWriteContent,
  type ClassCommentaryGeneration,
  type ClassCommentaryMemorySummary,
  type ClassCommentarySkillEligibility,
  type ClassCommentarySkillEvolution,
  type ClassCommentarySkillVersion,
  type ClassCommentaryTask,
  type ClassCommentaryStudentFeedbackItem,
  updateClassCommentaryScopedStudentFeedback,
  writeClassCommentarySkillPreference,
} from '../../classCommentary';
import {
  CLASS_COMMENTARY_NAVIGATION_REQUEST_EVENT,
  type ClassCommentaryNavigationRequestDetail,
} from '../../classCommentaryNavigationGuard';
import { ApiFetchError, apiFetch } from '../../workspaceShared';

type ClassFeedbackGenerationPageProps = {
  currentUser: CurrentUser;
};

type ClassFeedbackStudent = {
  id: number;
  name: string;
};

type GenerationEditorState = {
  workspaceKey: string;
  taskId: number;
  generationId: number;
  feedbackSchemaVersion: string;
  feedbackText: string;
  savedFeedbackText: string;
  studentOrder: number[];
  itemsByStudentId: Record<number, ClassCommentaryStudentFeedbackItem>;
  savedItemsByStudentId: Record<number, ClassCommentaryStudentFeedbackItem>;
  draft: ClassCommentaryFeedbackDraft | null;
  latestRevisionIdAtLoad: number | null;
};

type RevisionPreviewState = {
  revisionPreviewKey: string;
  revision: ClassCommentaryFeedbackRevision;
};

type PendingFeedbackTransition =
  | { kind: 'generation'; generationId: string }
  | { kind: 'task'; task: ClassCommentaryTask }
  | { kind: 'revision'; revision: ClassCommentaryFeedbackRevision }
  | { kind: 'create-task' }
  | { kind: 'generate' }
  | { kind: 'route'; proceed: () => void };

type StructuredDraftConflict = {
  workspaceKey: string;
  localText: string;
  localItems: ClassCommentaryStudentFeedbackItem[];
  serverDraft: ClassCommentaryFeedbackDraft;
  attemptedExpectedDraftVersion: number;
};

type PendingClassCommentaryRequest = {
  scopeKey: string;
  requestId: string;
};

const disabledClassCommentaryCapabilities: ClassCommentaryCapabilities = {
  memory_learning_enabled: false,
  skill_evolution_enabled: false,
  structured_feedback_enabled: false,
};

function createClassCommentaryRequestId(prefix: string): string {
  const randomId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${randomId}`;
}

function claimClassCommentaryRequest(
  currentRequest: PendingClassCommentaryRequest | null,
  scopeKey: string,
  prefix: string,
): PendingClassCommentaryRequest {
  if (currentRequest?.scopeKey === scopeKey) {
    return currentRequest;
  }
  return {
    scopeKey,
    requestId: createClassCommentaryRequestId(prefix),
  };
}

function settleClassCommentaryRequest(
  currentRequest: PendingClassCommentaryRequest | null,
  requestId: string,
  serverResponded: boolean,
): PendingClassCommentaryRequest | null {
  if (!serverResponded || currentRequest?.requestId !== requestId) {
    return currentRequest;
  }
  return null;
}

function canUseTranscriptState(task: ClassCommentaryTask | null): boolean {
  if (!task) {
    return false;
  }
  return task.status === 'transcribed' || task.status === 'ready' || task.status === 'failed';
}

function getTaskProgress(task: ClassCommentaryTask | null, uploadProgress: number): number {
  if (!task) {
    return uploadProgress;
  }
  if (task.status === 'uploaded') {
    return Math.max(uploadProgress, 18);
  }
  if (task.status === 'transcribing') {
    return 52;
  }
  if (task.status === 'transcribed') {
    return 68;
  }
  if (task.status === 'generating') {
    return 86;
  }
  return 100;
}

function getTaskErrorMessage(task: ClassCommentaryTask | null, errorMessage: string): string {
  if (errorMessage) {
    return errorMessage;
  }
  if (!task || task.status !== 'failed') {
    return '';
  }
  if (task.failure_stage === 'transcription') {
    return task.transcription_error || '转写失败';
  }
  if (task.failure_stage === 'generation') {
    if (task.generation_error === 'structured_feedback_invalid') {
      return '反馈结构校验失败, 请重新生成';
    }
    return task.generation_error || '生成失败';
  }
  return '任务失败';
}

function getClassCommentaryGenerationErrorMessage(error: unknown): string {
  if (error instanceof ApiFetchError) {
    if (error.payload?.error === 'structured_feedback_invalid') {
      return '反馈结构校验失败, 请重新生成';
    }
    if (error.payload?.error === 'attending_student_ids is required') {
      return '请至少选择一名到课学生后重新生成';
    }
    if (error.payload?.error === 'student_feedback_no_eligible_students') {
      return '没有可生成的到课学生, 请检查到课名单后重新生成';
    }
    if (error.payload?.error === 'student_roster_name_ambiguous') {
      return '到课名单存在无法区分的重名, 请调整到课名单后重新生成';
    }
  }
  return error instanceof Error ? error.message : '生成失败';
}

function formatClassCommentaryTime(value: string): string {
  if (!value) {
    return '-';
  }
  const parsed = new Date(value.replace(' ', 'T'));
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function classCommentaryMemoryStatusLabel(status: ClassCommentaryMemorySummary['status']): string {
  return {
    not_requested: '未请求学习',
    queued: '等待学习',
    extracting: '提取中',
    syncing: '写入记忆中',
    complete: '学习完成',
    partial: '部分完成',
    failed: '学习失败',
    obsolete: '已被新版取代',
  }[status];
}

function classCommentarySkillCandidateStatusLabel(status: ClassCommentarySkillCandidateBuildStatus): string {
  return {
    queued: '等待整理',
    running: '整理中',
    retry_wait: '稍后重试',
    succeeded: '新调整已整理',
    failed: '整理失败',
    obsolete: '需要重新整理',
  }[status];
}

function classCommentarySkillEligibilityMessage(eligibility: ClassCommentarySkillEligibility): string {
  const currentCount = Math.max(0, eligibility.effective_task_count);
  const requiredCount = Math.max(1, eligibility.min_effective_tasks);
  if (eligibility.eligible) {
    return `已积累 ${currentCount}/${requiredCount} 次有效修改, 可以让 AI 整理一次更新.`;
  }
  if (eligibility.reason === 'insufficient_effective_tasks' || eligibility.reason === 'not_enough_effective_tasks') {
    const remainingCount = Math.max(0, requiredCount - currentCount);
    return `已积累 ${currentCount}/${requiredCount} 次有效修改, 还需要 ${remainingCount} 个不同课堂的真实修改.`;
  }
  if (eligibility.reason === 'insufficient_supporting_tasks' || eligibility.reason === 'not_enough_supporting_tasks') {
    return `已积累 ${currentCount}/${requiredCount} 次有效修改, 整理规则更新后即可继续.`;
  }
  if (eligibility.reason === 'candidate_in_progress' || eligibility.reason === 'build_in_progress') {
    return 'AI 正在整理这次更新, 完成前无需重复操作.';
  }
  if (eligibility.reason === 'active_version_missing') {
    return '当前同事测评风格暂时不可用.';
  }
  return '继续确认并学习修改, AI 会在规律足够稳定后开放整理.';
}

function classCommentarySkillStaleMessage(reason: string): string {
  return {
    base_version_changed: '正在使用的版本已经变化, 请基于最新版本重新整理.',
    revision_not_effective: '这次建议参考的反馈已有新版, 请重新整理.',
    supporting_evidence_not_active: '这次建议参考的修改已被撤销或取代, 请重新整理.',
    source_snapshot_mismatch: '这次建议的依据已变化, 请重新整理.',
  }[reason] || '这次建议已经过期, 请重新整理后再使用.';
}

function classCommentarySkillActionError(error: unknown, fallback: string): string {
  if (error instanceof ApiFetchError) {
    if (error.payload?.error === 'candidate_stale') {
      return '这次建议已经过期, 请重新整理.';
    }
    if (error.payload?.error === 'skill_version_conflict' || error.payload?.error === 'active_version_conflict') {
      return '正在使用的版本已经变化, 请刷新后重试.';
    }
    if (error.payload?.error === 'candidate_not_ready') {
      return '目前积累的有效修改还不够, 暂时不能整理更新.';
    }
  }
  return error instanceof Error ? error.message : fallback;
}

function mergeHistoryTask(historyTasks: ClassCommentaryTask[], nextTask: ClassCommentaryTask): ClassCommentaryTask[] {
  return [nextTask, ...historyTasks.filter((item) => item.id !== nextTask.id)].slice(0, 30);
}

function cloneStudentFeedbackItems(items: ClassCommentaryStudentFeedbackItem[]): ClassCommentaryStudentFeedbackItem[] {
  return items.map((item) => ({ ...item }));
}

function indexStudentFeedbackItems(
  items: ClassCommentaryStudentFeedbackItem[],
): Record<number, ClassCommentaryStudentFeedbackItem> {
  return Object.fromEntries(items.map((item) => [item.student_id, { ...item }]));
}

function orderedStudentFeedbackItems(
  editor: GenerationEditorState,
  saved = false,
): ClassCommentaryStudentFeedbackItem[] {
  const itemsByStudentId = saved ? editor.savedItemsByStudentId : editor.itemsByStudentId;
  return editor.studentOrder
    .map((studentId) => itemsByStudentId[studentId])
    .filter((item): item is ClassCommentaryStudentFeedbackItem => Boolean(item));
}

function createGenerationEditorState(
  taskId: number,
  generation: ClassCommentaryGeneration,
  draft: ClassCommentaryFeedbackDraft | null,
  revision: ClassCommentaryFeedbackRevision | null,
  latestRevisionIdAtLoad: number | null,
): GenerationEditorState {
  const items = resolveClassCommentaryStudentFeedbackItems(draft, revision, generation);
  const feedbackText = items.length
    ? deriveClassCommentaryStructuredFeedbackText(items)
    : resolveClassCommentaryCopyText(draft, revision, generation);
  return {
    workspaceKey: buildClassCommentaryFeedbackWorkspaceKey(taskId, generation.id),
    taskId,
    generationId: generation.id,
    feedbackSchemaVersion: generation.feedback_schema_version,
    feedbackText,
    savedFeedbackText: feedbackText,
    studentOrder: items.map((item) => item.student_id),
    itemsByStudentId: indexStudentFeedbackItems(items),
    savedItemsByStudentId: indexStudentFeedbackItems(items),
    draft,
    latestRevisionIdAtLoad,
  };
}

function isGenerationEditorDirty(editor: GenerationEditorState | undefined): boolean {
  if (!editor) {
    return false;
  }
  if (editor.feedbackSchemaVersion === CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1) {
    return !areClassCommentaryStudentFeedbackItemsEqual(
      orderedStudentFeedbackItems(editor),
      orderedStudentFeedbackItems(editor, true),
    );
  }
  return editor.feedbackText !== editor.savedFeedbackText;
}

function buildFeedbackWriteContent(editor: GenerationEditorState): ClassCommentaryFeedbackWriteContent {
  if (editor.feedbackSchemaVersion !== CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1) {
    return editor.feedbackText;
  }
  return {
    feedback_schema_version: CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
    student_feedback_items: orderedStudentFeedbackItems(editor).map((item) => ({
      student_id: item.student_id,
      feedback_text: item.feedback_text,
    })),
  };
}

function classCommentaryStudentFeedbackErrorMessage(errorCode: string, limit?: number): string {
  if (errorCode === 'student_feedback_empty') {
    return '反馈内容不能为空.';
  }
  if (errorCode === 'student_feedback_too_long') {
    return limit ? `反馈内容不能超过 ${limit} 个字.` : '反馈内容过长, 请精简后重试.';
  }
  if (errorCode === 'student_feedback_cross_student_reference') {
    return '这段反馈提到了另一名学生, 请核对后重试.';
  }
  return '这段反馈未通过校验, 请核对后重试.';
}

export function ClassFeedbackGenerationPage({ currentUser }: ClassFeedbackGenerationPageProps) {
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [skills, setSkills] = useState<ClassCommentarySkill[]>([]);
  const [historyTasks, setHistoryTasks] = useState<ClassCommentaryTask[]>([]);
  const [classStudents, setClassStudents] = useState<ClassFeedbackStudent[]>([]);
  const [attendingStudentIds, setAttendingStudentIds] = useState<number[]>([]);
  const [selectedClassId, setSelectedClassId] = useState('');
  const [selectedSkillId, setSelectedSkillId] = useState('');
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [task, setTask] = useState<ClassCommentaryTask | null>(null);
  const [confirmedTranscript, setConfirmedTranscript] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [loadingClassStudents, setLoadingClassStudents] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [copied, setCopied] = useState(false);
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [generations, setGenerations] = useState<ClassCommentaryGeneration[]>([]);
  const [selectedGenerationId, setSelectedGenerationId] = useState('');
  const [feedbackEditorText, setFeedbackEditorText] = useState('');
  const [feedbackDraft, setFeedbackDraft] = useState<ClassCommentaryFeedbackDraft | null>(null);
  const [generationEditors, setGenerationEditors] = useState<Record<string, GenerationEditorState>>({});
  const [feedbackRevisions, setFeedbackRevisions] = useState<ClassCommentaryFeedbackRevision[]>([]);
  const [revisionPreview, setRevisionPreview] = useState<RevisionPreviewState | null>(null);
  const [expandedStudentIds, setExpandedStudentIds] = useState<string[]>([]);
  const [copiedStudentId, setCopiedStudentId] = useState<number | null>(null);
  const [copyNotice, setCopyNotice] = useState('');
  const [studentFeedbackErrors, setStudentFeedbackErrors] = useState<Record<number, string>>({});
  const [pendingFeedbackTransition, setPendingFeedbackTransition] = useState<PendingFeedbackTransition | null>(null);
  const [revisionMemorySummary, setRevisionMemorySummary] = useState<ClassCommentaryMemorySummary | null>(null);
  const [memoryLoadError, setMemoryLoadError] = useState('');
  const [memoryRefreshVersion, setMemoryRefreshVersion] = useState(0);
  const [memoryActionKey, setMemoryActionKey] = useState('');
  const [skillEvolutionDialogOpen, setSkillEvolutionDialogOpen] = useState(false);
  const [skillEvolution, setSkillEvolution] = useState<ClassCommentarySkillEvolution | null>(null);
  const [selectedSkillVersionId, setSelectedSkillVersionId] = useState('');
  const [skillEvolutionLoadError, setSkillEvolutionLoadError] = useState('');
  const [skillEvolutionActionError, setSkillEvolutionActionError] = useState('');
  const [skillEvolutionActionKey, setSkillEvolutionActionKey] = useState('');
  const [skillEvolutionRefreshVersion, setSkillEvolutionRefreshVersion] = useState(0);
  const [loadingGenerationId, setLoadingGenerationId] = useState<number | null>(null);
  const [capabilities, setCapabilities] = useState<ClassCommentaryCapabilities>(disabledClassCommentaryCapabilities);
  const [draftConflict, setDraftConflict] = useState<StructuredDraftConflict | null>(null);
  const [revisionConflict, setRevisionConflict] = useState<{
    workspaceKey: string;
    currentLatestRevision: ClassCommentaryFeedbackRevision | null;
    currentLatestRevisionId: number | null;
  } | null>(null);
  const generationLoadRequestTokenRef = useRef(0);
  const feedbackMutationActiveRef = useRef(false);
  const feedbackMutationTokenRef = useRef(0);
  const currentTaskIdRef = useRef<number | null>(null);
  const selectedGenerationIdRef = useRef('');
  const memoryLoadRequestTokenRef = useRef(0);
  const memoryActionRequestTokenRef = useRef(0);
  const skillEvolutionLoadRequestTokenRef = useRef(0);
  const skillEvolutionActionRequestTokenRef = useRef(0);
  const confirmationRequestRef = useRef<PendingClassCommentaryRequest | null>(null);
  const memoryRetryRequestRef = useRef<PendingClassCommentaryRequest | null>(null);
  const memoryRevokeRequestRef = useRef<PendingClassCommentaryRequest | null>(null);
  const skillCandidateRequestRef = useRef<PendingClassCommentaryRequest | null>(null);
  const skillActivateRequestRef = useRef<PendingClassCommentaryRequest | null>(null);
  const skillRollbackRequestRef = useRef<PendingClassCommentaryRequest | null>(null);
  const feedbackDirtyRef = useRef(false);
  const copyNoticeTimerRef = useRef<number | null>(null);

  useEffect(() => () => {
    if (copyNoticeTimerRef.current !== null) {
      window.clearTimeout(copyNoticeTimerRef.current);
    }
  }, []);

  function showCopyNotice(message: string) {
    if (copyNoticeTimerRef.current !== null) {
      window.clearTimeout(copyNoticeTimerRef.current);
    }
    setCopyNotice(message);
    copyNoticeTimerRef.current = window.setTimeout(() => {
      setCopyNotice('');
      copyNoticeTimerRef.current = null;
    }, 2400);
  }

  function resetFeedbackVersionState(nextTaskId: number | null, releaseBusy = false) {
    generationLoadRequestTokenRef.current += 1;
    feedbackMutationActiveRef.current = false;
    feedbackMutationTokenRef.current += 1;
    currentTaskIdRef.current = nextTaskId;
    selectedGenerationIdRef.current = '';
    setGenerations([]);
    setSelectedGenerationId('');
    setFeedbackEditorText('');
    setFeedbackDraft(null);
    setFeedbackRevisions([]);
    setRevisionPreview(null);
    setExpandedStudentIds([]);
    setCopiedStudentId(null);
    setCopyNotice('');
    setStudentFeedbackErrors({});
    memoryLoadRequestTokenRef.current += 1;
    memoryActionRequestTokenRef.current += 1;
    setRevisionMemorySummary(null);
    setMemoryLoadError('');
    setMemoryRefreshVersion(0);
    setMemoryActionKey('');
    confirmationRequestRef.current = null;
    memoryRetryRequestRef.current = null;
    memoryRevokeRequestRef.current = null;
    setLoadingGenerationId(null);
    setDraftConflict(null);
    setRevisionConflict(null);
    if (releaseBusy) {
      setBusy(false);
    }
  }

  function isCurrentFeedbackMutation(taskId: number, generationId: number, mutationToken: number): boolean {
    return feedbackMutationTokenRef.current === mutationToken
      && currentTaskIdRef.current === taskId
      && selectedGenerationIdRef.current === String(generationId);
  }

  useEffect(() => {
    let cancelled = false;
    setLoadingInitial(true);
    Promise.all([
      apiFetch<ClassItem[]>('/api/classes'),
      fetchClassCommentarySkills(),
      fetchClassCommentaryTasks(),
      fetchClassCommentaryCapabilities().catch(() => disabledClassCommentaryCapabilities),
    ])
      .then(([nextClasses, nextSkills, nextHistoryTasks, nextCapabilities]) => {
        if (cancelled) {
          return;
        }
        setClasses(nextClasses);
        setSkills(nextSkills);
        setHistoryTasks(nextHistoryTasks);
        setCapabilities(nextCapabilities);
        setSelectedClassId((currentValue) => currentValue || (nextClasses[0] ? String(nextClasses[0].id) : ''));
        setSelectedSkillId((currentValue) => currentValue || readClassCommentarySkillPreference(currentUser, nextSkills) || (nextSkills[0]?.id || ''));
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : '加载失败');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingInitial(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [currentUser.id, currentUser.organization_id]);

  useEffect(() => {
    skillEvolutionLoadRequestTokenRef.current += 1;
    skillEvolutionActionRequestTokenRef.current += 1;
    setSkillEvolutionDialogOpen(false);
    setSkillEvolution(null);
    setSelectedSkillVersionId('');
    setSkillEvolutionLoadError('');
    setSkillEvolutionActionError('');
    setSkillEvolutionActionKey('');
    setSkillEvolutionRefreshVersion(0);
    skillCandidateRequestRef.current = null;
    skillActivateRequestRef.current = null;
    skillRollbackRequestRef.current = null;
  }, [capabilities.skill_evolution_enabled, selectedSkillId]);

  useEffect(() => {
    if (!selectedClassId) {
      setClassStudents([]);
      setAttendingStudentIds([]);
      return;
    }
    let cancelled = false;
    setLoadingClassStudents(true);
    apiFetch<{ students: ClassFeedbackStudent[] }>(`/api/classes/${encodeURIComponent(selectedClassId)}/students`)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        const nextStudents = Array.isArray(payload.students) ? payload.students : [];
        setClassStudents(nextStudents);
        setAttendingStudentIds(nextStudents.map((item) => item.id));
      })
      .catch((error) => {
        if (!cancelled) {
          setClassStudents([]);
          setAttendingStudentIds([]);
          setErrorMessage(error instanceof Error ? error.message : '加载学生名单失败');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingClassStudents(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedClassId]);

  useEffect(() => {
    if (!task || !shouldPollClassCommentaryTask(task.status)) {
      return;
    }
    const polledTaskId = task.id;
    const timer = window.setInterval(() => {
      fetchClassCommentaryTask(polledTaskId)
        .then((nextTask) => {
          if (currentTaskIdRef.current !== polledTaskId) {
            return;
          }
          setTask(nextTask);
          setHistoryTasks((current) => mergeHistoryTask(current, nextTask));
          setConfirmedTranscript(nextTask.confirmed_transcript_text || nextTask.transcript_text || '');
        })
        .catch((error) => {
          if (currentTaskIdRef.current === polledTaskId) {
            setErrorMessage(error instanceof Error ? error.message : '刷新任务状态失败');
          }
        });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [task?.id, task?.status]);

  useEffect(() => {
    if (!task) {
      resetFeedbackVersionState(null);
      return;
    }
    if (currentTaskIdRef.current !== task.id) {
      resetFeedbackVersionState(task.id);
    }
    let cancelled = false;
    const taskId = task.id;
    const requestToken = ++generationLoadRequestTokenRef.current;
    let targetGenerationId: number | null = null;
    setLoadingGenerationId(null);
    Promise.all([
      fetchClassCommentaryGenerations(taskId),
      fetchClassCommentaryFeedbackRevisions(taskId),
    ])
      .then(async ([nextGenerations, nextRevisions]) => {
        if (
          cancelled
          || requestToken !== generationLoadRequestTokenRef.current
          || currentTaskIdRef.current !== taskId
        ) {
          return;
        }
        if (
          nextGenerations.some((item) => !isClassCommentaryFeedbackRecordInScope(item, taskId, item.id))
          || nextRevisions.some((item) => !isClassCommentaryFeedbackRecordInScope(
            item,
            taskId,
            item.generation_id,
          ))
        ) {
          throw new Error('反馈版本响应范围不一致');
        }
        setGenerations(nextGenerations);
        setFeedbackRevisions(nextRevisions);
        const targetGeneration = nextGenerations.find((item) => item.id === task.latest_generation_id)
          || nextGenerations[0]
          || null;
        if (!targetGeneration) {
          selectedGenerationIdRef.current = '';
          setSelectedGenerationId('');
          setFeedbackEditorText(task.final_feedback_text || task.feedback_text || '');
          setFeedbackDraft(null);
          return;
        }
        const targetWorkspaceKey = buildClassCommentaryFeedbackWorkspaceKey(taskId, targetGeneration.id);
        const cachedTarget = generationEditors[targetWorkspaceKey];
        if (
          cachedTarget
          && (!cachedTarget.draft || isClassCommentaryFeedbackRecordInScope(
            cachedTarget.draft,
            taskId,
            targetGeneration.id,
          ))
        ) {
          selectedGenerationIdRef.current = String(targetGeneration.id);
          setSelectedGenerationId(String(targetGeneration.id));
          setFeedbackEditorText(cachedTarget.feedbackText);
          setFeedbackDraft(cachedTarget.draft);
          setExpandedStudentIds([]);
          setLoadingGenerationId(null);
          return;
        }
        if (feedbackMutationActiveRef.current) {
          return;
        }
        targetGenerationId = targetGeneration.id;
        feedbackMutationTokenRef.current += 1;
        selectedGenerationIdRef.current = String(targetGenerationId);
        setSelectedGenerationId(String(targetGenerationId));
        setFeedbackEditorText('');
        setFeedbackDraft(null);
        setLoadingGenerationId(targetGenerationId);
        const [generationDetail, nextDraft] = await Promise.all([
          fetchClassCommentaryGeneration(taskId, targetGenerationId),
          fetchClassCommentaryFeedbackDraft(taskId, targetGenerationId),
        ]);
        if (
          cancelled
          || requestToken !== generationLoadRequestTokenRef.current
          || currentTaskIdRef.current !== taskId
          || selectedGenerationIdRef.current !== String(targetGenerationId)
        ) {
          return;
        }
        if (
          !isClassCommentaryFeedbackRecordInScope(generationDetail, taskId, targetGenerationId)
          || (nextDraft && !isClassCommentaryFeedbackRecordInScope(nextDraft, taskId, targetGenerationId))
        ) {
          throw new Error('生成版本响应范围不一致');
        }
        const latestRevision = nextRevisions.find((item) => item.generation_id === targetGenerationId) || null;
        const nextEditor = createGenerationEditorState(
          taskId,
          generationDetail,
          nextDraft,
          latestRevision,
          task.latest_revision_id,
        );
        if (!nextEditor.feedbackText && !generationDetail.feedback_schema_version) {
          nextEditor.feedbackText = task.feedback_text || '';
          nextEditor.savedFeedbackText = nextEditor.feedbackText;
        }
        setFeedbackEditorText(nextEditor.feedbackText);
        setFeedbackDraft(nextDraft);
        setGenerationEditors((current) => ({
          ...current,
          [nextEditor.workspaceKey]: nextEditor,
        }));
        setExpandedStudentIds([]);
      })
      .catch((error) => {
        if (
          !cancelled
          && requestToken === generationLoadRequestTokenRef.current
          && currentTaskIdRef.current === taskId
        ) {
          if (targetGenerationId === null || selectedGenerationIdRef.current === String(targetGenerationId)) {
            selectedGenerationIdRef.current = '';
            setSelectedGenerationId('');
            setFeedbackEditorText('');
            setFeedbackDraft(null);
          }
          setErrorMessage(error instanceof Error ? error.message : '加载反馈版本失败');
        }
      })
      .finally(() => {
        if (
          !cancelled
          && requestToken === generationLoadRequestTokenRef.current
          && currentTaskIdRef.current === taskId
        ) {
          setLoadingGenerationId(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [task?.id, task?.latest_generation_id]);

  const selectedClass = classes.find((item) => String(item.id) === selectedClassId) || null;
  const selectedSkill = skills.find((item) => item.id === selectedSkillId) || null;
  const selectedGeneration = generations.find((item) => String(item.id) === selectedGenerationId) || null;
  const taskLatestRevision = feedbackRevisions.find((item) => item.id === task?.latest_revision_id) || null;
  const selectedRevision = taskLatestRevision?.generation_id === selectedGeneration?.id
    ? taskLatestRevision
    : null;
  const selectedWorkspaceKey = task && selectedGeneration
    ? buildClassCommentaryFeedbackWorkspaceKey(task.id, selectedGeneration.id)
    : '';
  const selectedEditorState = selectedWorkspaceKey ? generationEditors[selectedWorkspaceKey] : undefined;
  const previewRevision = revisionPreview?.revision || null;
  const displayedRevision = previewRevision || selectedRevision;
  const generationLoading = loadingGenerationId !== null;
  const isTaskReadOnly = Boolean(task && task.teacher_user_id !== currentUser.id);
  const feedbackSchemaStatuses = [
    ...(previewRevision ? [] : [
      selectedGeneration?.feedback_schema_status,
      feedbackDraft?.feedback_schema_status,
      taskLatestRevision?.feedback_schema_status,
    ]),
    displayedRevision?.feedback_schema_status,
  ].filter((status): status is NonNullable<typeof status> => Boolean(status));
  const feedbackSchemaMismatch = !previewRevision && Boolean(
    selectedGeneration
    && (
      (feedbackDraft && feedbackDraft.feedback_schema_version !== selectedGeneration.feedback_schema_version)
      || !isClassCommentaryTaskLatestSchemaCompatible(
        selectedGeneration.feedback_schema_version,
        taskLatestRevision?.feedback_schema_version || '',
      )
    ),
  );
  const feedbackSchemaReadOnly = feedbackSchemaMismatch
    || feedbackSchemaStatuses.some((status) => status === 'unsupported' || status === 'invalid');
  const feedbackSchemaNotice = feedbackSchemaStatuses.includes('invalid')
    ? '反馈数据完整性校验失败, 当前仅可查看和复制现有内容.'
    : feedbackSchemaStatuses.includes('unsupported')
      ? '当前版本暂不支持编辑, 可查看和复制现有内容.'
      : feedbackSchemaMismatch
        ? '反馈格式不一致, 当前仅可查看和复制现有内容.'
      : '';
  const persistedCopyText = resolveClassCommentaryCopyText(
    feedbackDraft,
    selectedRevision,
    selectedGeneration,
    generationLoading,
  );
  const displayedStudentFeedbackItems = previewRevision?.feedback_schema_status === 'supported'
    ? previewRevision.student_feedback_items
    : selectedEditorState ? orderedStudentFeedbackItems(selectedEditorState) : [];
  const structuredFeedbackMode = selectedGeneration?.feedback_schema_status === 'supported'
    && selectedGeneration.feedback_schema_version === CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1
    && !feedbackSchemaReadOnly;
  const previewStructuredFeedbackMode = previewRevision?.feedback_schema_status === 'supported'
    && previewRevision.feedback_schema_version === CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1;
  const feedbackDirty = isGenerationEditorDirty(selectedEditorState);
  const localEditorCopyText = selectedEditorState
    ? selectedEditorState.feedbackSchemaVersion === CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1
      ? deriveClassCommentaryStructuredFeedbackText(orderedStudentFeedbackItems(selectedEditorState))
      : selectedEditorState.feedbackText
    : feedbackEditorText;
  const copyText = generationLoading
    ? ''
    : previewRevision
      ? previewRevision.derived_feedback_text || previewRevision.final_feedback_text
      : structuredFeedbackMode
        ? deriveClassCommentaryStructuredFeedbackText(displayedStudentFeedbackItems)
        : feedbackEditorText || persistedCopyText;
  const currentContentConfirmed = Boolean(previewRevision) || Boolean(
    selectedRevision
    && selectedEditorState
    && (structuredFeedbackMode
      ? areClassCommentaryStudentFeedbackItemsEqual(
        orderedStudentFeedbackItems(selectedEditorState),
        selectedRevision.feedback_schema_status === 'supported'
          ? selectedRevision.student_feedback_items
          : [],
      )
      : selectedEditorState.feedbackText === selectedRevision.final_feedback_text),
  );
  const taskErrorMessage = getTaskErrorMessage(task, errorMessage);
  const taskStatusMessage = errorMessage === '已同步最新终稿版本, 本地修改仍保留. 请重新确认.';
  const taskProgress = getTaskProgress(task, uploadProgress);
  const trimmedConfirmedTranscript = confirmedTranscript.trim();
  const persistedTranscript = (task?.confirmed_transcript_text || task?.transcript_text || '').trim();
  const hasTranscriptText = Boolean(trimmedConfirmedTranscript);
  const transcriptDirty = Boolean(task) && trimmedConfirmedTranscript !== persistedTranscript;
  const transcriptStatusLabel = task?.status === 'uploaded' || task?.status === 'transcribing'
    ? '转写中'
    : transcriptDirty
      ? '未保存'
      : persistedTranscript
        ? '已保存'
        : hasTranscriptText
          ? '可生成'
          : '待输入';
  const canUseTranscript = canUseTranscriptState(task);
  const canCreateManualTextTask = !task || task.status === 'uploaded' || task.status === 'transcribing';
  const canCreateTask = !loadingInitial && !busy && !generationLoading && Boolean(selectedClassId && audioFile);
  const canSaveTranscript = !isTaskReadOnly && !busy && !generationLoading && canUseTranscript && hasTranscriptText;
  const attendanceReadyForGeneration = capabilities.structured_feedback_enabled
    ? attendingStudentIds.length > 0
    : !classStudents.length || attendingStudentIds.length > 0;
  const canGenerate = !isTaskReadOnly && !busy && !generationLoading && !loadingClassStudents && hasTranscriptText && Boolean(selectedClassId && selectedSkillId) && (canUseTranscript || canCreateManualTextTask) && attendanceReadyForGeneration;
  const hasSucceededGeneration = selectedGeneration?.status === 'succeeded';
  const feedbackContentValid = structuredFeedbackMode
    ? Boolean(
      selectedEditorState?.studentOrder.length
      && orderedStudentFeedbackItems(selectedEditorState).every((item) => Boolean(item.feedback_text.trim())),
    )
    : Boolean(feedbackEditorText.trim());
  const localEditorContentValid = selectedEditorState?.feedbackSchemaVersion === CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1
    ? Boolean(
      selectedEditorState.studentOrder.length
      && orderedStudentFeedbackItems(selectedEditorState).every((item) => Boolean(item.feedback_text.trim())),
    )
    : Boolean(selectedEditorState?.feedbackText.trim());
  const canSaveFeedbackDraft = !isTaskReadOnly
    && !feedbackSchemaReadOnly
    && !revisionPreview
    && !busy
    && !generationLoading
    && selectedGeneration?.status === 'succeeded'
    && feedbackContentValid
    && feedbackDirty;
  const canConfirmFeedback = !isTaskReadOnly
    && !feedbackSchemaReadOnly
    && !revisionPreview
    && !busy
    && !generationLoading
    && selectedGeneration?.status === 'succeeded'
    && feedbackContentValid;
  const canSavePendingFeedbackTransition = !isTaskReadOnly
    && !feedbackSchemaReadOnly
    && !busy
    && !generationLoading
    && selectedGeneration?.status === 'succeeded'
    && localEditorContentValid
    && feedbackDirty;
  const attendanceListHeight = Math.min(224, Math.max(32, classStudents.length * 40 - 8));
  const activeSkillVersion = skillEvolution?.versions.find((version) => version.is_active)
    || skillEvolution?.versions.find((version) => version.id === skillEvolution.skill.active_version_id)
    || null;
  const selectedSkillVersion = skillEvolution?.versions.find(
    (version) => String(version.id) === selectedSkillVersionId,
  ) || null;
  const latestSkillCandidateBuild = skillEvolution?.candidate_builds[0] || null;
  const skillCandidateBuildInProgress = Boolean(
    skillEvolution?.candidate_builds.some((build) => !build.is_terminal),
  );
  const expectedActiveSkillVersionId = skillEvolution?.skill.active_version_id
    || activeSkillVersion?.id
    || 0;
  const canCreateSkillCandidate = Boolean(
    skillEvolution?.eligibility.eligible
    && skillEvolution?.skill.can_manage_evolution !== false
    && expectedActiveSkillVersionId > 0
    && !skillCandidateBuildInProgress
    && !skillEvolutionActionKey,
  );
  const canActivateSkillVersion = Boolean(
    selectedSkillVersion
    && selectedSkillVersion.version_kind === 'candidate'
    && skillEvolution?.skill.can_manage_evolution !== false
    && selectedSkillVersion.review_status === 'pending'
    && !selectedSkillVersion.is_active
    && !selectedSkillVersion.is_stale
    && expectedActiveSkillVersionId > 0
    && !skillEvolutionActionKey,
  );
  const canRollbackSkillVersion = Boolean(
    selectedSkillVersion
    && skillEvolution?.skill.can_manage_evolution !== false
    && !selectedSkillVersion.is_active
    && (selectedSkillVersion.review_status === 'approved' || selectedSkillVersion.review_status === 'not_required')
    && expectedActiveSkillVersionId > 0
    && !skillEvolutionActionKey,
  );

  useEffect(() => {
    feedbackDirtyRef.current = feedbackDirty;
  }, [feedbackDirty]);

  useEffect(() => {
    const handleNavigationRequest = (rawEvent: Event) => {
      if (!feedbackDirtyRef.current) {
        return;
      }
      const event = rawEvent as CustomEvent<ClassCommentaryNavigationRequestDetail>;
      if (typeof event.detail?.proceed !== 'function') {
        return;
      }
      event.preventDefault();
      setPendingFeedbackTransition((current) => current || {
        kind: 'route',
        proceed: event.detail.proceed,
      });
    };
    window.addEventListener(CLASS_COMMENTARY_NAVIGATION_REQUEST_EVENT, handleNavigationRequest as EventListener);
    return () => {
      window.removeEventListener(CLASS_COMMENTARY_NAVIGATION_REQUEST_EVENT, handleNavigationRequest as EventListener);
    };
  }, []);

  useEffect(() => {
    if (!feedbackDirty) {
      return undefined;
    }
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [feedbackDirty]);

  useEffect(() => {
    const revisionId = selectedRevision?.id || 0;
    const requestToken = ++memoryLoadRequestTokenRef.current;
    let cancelled = false;
    let pollTimer: number | undefined;
    let pollingDelayMs = 2000;
    if (isTaskReadOnly || !capabilities.memory_learning_enabled || !selectedRevision?.learn_requested || revisionId <= 0) {
      setRevisionMemorySummary(null);
      setMemoryLoadError('');
      return () => {
        cancelled = true;
      };
    }

    setRevisionMemorySummary((current) => current?.revision_id === revisionId ? current : null);
    setMemoryLoadError('');

    const loadMemorySummary = async () => {
      try {
        const summary = await fetchClassCommentaryRevisionMemories(revisionId);
        if (cancelled || requestToken !== memoryLoadRequestTokenRef.current) {
          return;
        }
        setRevisionMemorySummary(summary);
        setMemoryLoadError('');
        pollingDelayMs = 2000;
        if (['queued', 'extracting', 'syncing'].includes(summary.status)) {
          pollTimer = window.setTimeout(loadMemorySummary, pollingDelayMs);
        }
      } catch {
        if (!cancelled && requestToken === memoryLoadRequestTokenRef.current) {
          setMemoryLoadError('学习状态暂时不可用, 正在重试');
          pollingDelayMs = Math.min(pollingDelayMs * 2, 30000);
          pollTimer = window.setTimeout(loadMemorySummary, pollingDelayMs);
        }
      }
    };

    void loadMemorySummary();
    return () => {
      cancelled = true;
      if (pollTimer !== undefined) {
        window.clearTimeout(pollTimer);
      }
    };
  }, [
    capabilities.memory_learning_enabled,
    isTaskReadOnly,
    memoryRefreshVersion,
    selectedRevision?.id,
    selectedRevision?.learn_requested,
  ]);

  useEffect(() => {
    const requestToken = ++skillEvolutionLoadRequestTokenRef.current;
    let cancelled = false;
    let pollTimer: number | undefined;
    let pollingDelayMs = 2000;
    if (!capabilities.skill_evolution_enabled || !skillEvolutionDialogOpen || !selectedSkillId) {
      return () => {
        cancelled = true;
      };
    }

    setSkillEvolutionLoadError('');

    const loadSkillEvolution = async () => {
      try {
        const nextEvolution = await fetchClassCommentarySkillEvolution(selectedSkillId);
        if (cancelled || requestToken !== skillEvolutionLoadRequestTokenRef.current) {
          return;
        }
        setSkillEvolution(nextEvolution);
        setSkillEvolutionLoadError('');
        setSelectedSkillVersionId((currentValue) => {
          const currentVersion = nextEvolution.versions.find((version) => String(version.id) === currentValue);
          const pendingCandidate = nextEvolution.versions.find((version) => (
            version.version_kind === 'candidate'
            && version.review_status === 'pending'
            && !version.is_stale
          ));
          const latestBuild = nextEvolution.candidate_builds[0] || null;
          if (
            pendingCandidate
            && (!currentVersion || (
              currentVersion.is_active
              && latestBuild?.candidate_version_id === pendingCandidate.id
            ))
          ) {
            return String(pendingCandidate.id);
          }
          if (currentVersion) {
            return currentValue;
          }
          const activeVersion = nextEvolution.versions.find((version) => version.is_active)
            || nextEvolution.versions.find((version) => version.id === nextEvolution.skill.active_version_id)
            || nextEvolution.versions[0];
          return activeVersion ? String(activeVersion.id) : '';
        });
        pollingDelayMs = 2000;
        if (nextEvolution.candidate_builds.some((build) => !build.is_terminal)) {
          pollTimer = window.setTimeout(loadSkillEvolution, pollingDelayMs);
        }
      } catch {
        if (!cancelled && requestToken === skillEvolutionLoadRequestTokenRef.current) {
          setSkillEvolutionLoadError('风格版本暂时不可用, 正在重试');
          pollingDelayMs = Math.min(pollingDelayMs * 2, 30000);
          pollTimer = window.setTimeout(loadSkillEvolution, pollingDelayMs);
        }
      }
    };

    void loadSkillEvolution();
    return () => {
      cancelled = true;
      if (pollTimer !== undefined) {
        window.clearTimeout(pollTimer);
      }
    };
  }, [
    capabilities.skill_evolution_enabled,
    selectedSkillId,
    skillEvolutionDialogOpen,
    skillEvolutionRefreshVersion,
  ]);

  async function handleCreateTask(skipDirtyGuard = false) {
    if (feedbackDirty && !skipDirtyGuard) {
      setPendingFeedbackTransition({ kind: 'create-task' });
      return;
    }
    if (!selectedClassId || !audioFile) {
      setErrorMessage('请选择班级并上传录音');
      return;
    }
    setBusy(true);
    setErrorMessage('');
    setUploadProgress(0);
    setCopied(false);
    try {
      const nextTask = await createClassCommentaryTask(Number(selectedClassId), audioFile, setUploadProgress);
      resetFeedbackVersionState(nextTask.id);
      setTask(nextTask);
      setHistoryTasks((current) => mergeHistoryTask(current, nextTask));
      setConfirmedTranscript(nextTask.confirmed_transcript_text || nextTask.transcript_text || '');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '上传失败');
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveTranscript() {
    if (!task) {
      return;
    }
    if (!confirmedTranscript.trim()) {
      setErrorMessage('请先确认转写文本');
      return;
    }
    setBusy(true);
    setErrorMessage('');
    try {
      const nextTask = await saveClassCommentaryTranscript(task.id, confirmedTranscript.trim());
      setTask(nextTask);
      setHistoryTasks((current) => mergeHistoryTask(current, nextTask));
      setConfirmedTranscript(nextTask.confirmed_transcript_text || nextTask.transcript_text || '');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '保存转写失败');
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerate(skipDirtyGuard = false) {
    if (feedbackDirty && !skipDirtyGuard) {
      setPendingFeedbackTransition({ kind: 'generate' });
      return;
    }
    if (!selectedClassId || !selectedSkillId) {
      setErrorMessage('请选择同事测评风格后再生成');
      return;
    }
    if (!trimmedConfirmedTranscript) {
      setErrorMessage('请先确认转写文本');
      return;
    }
    if (
      !attendingStudentIds.length
      && (capabilities.structured_feedback_enabled || classStudents.length)
    ) {
      setErrorMessage('请选择到课学生');
      return;
    }
    setBusy(true);
    setErrorMessage('');
    let generationTaskId = task?.id || 0;
    try {
      const savedTask = task && canUseTranscript
        ? (transcriptDirty ? await saveClassCommentaryTranscript(task.id, trimmedConfirmedTranscript) : task)
        : await createClassCommentaryTextTask(Number(selectedClassId), trimmedConfirmedTranscript);
      generationTaskId = savedTask.id;
      if (currentTaskIdRef.current !== savedTask.id) {
        resetFeedbackVersionState(savedTask.id);
      }
      setTask(savedTask);
      setHistoryTasks((current) => mergeHistoryTask(current, savedTask));
      setConfirmedTranscript(savedTask.confirmed_transcript_text || savedTask.transcript_text || '');
      const result = await generateClassCommentaryFeedback(
        savedTask.id,
        selectedSkillId,
        attendingStudentIds,
        createClassCommentaryRequestId('generation'),
      );
      const nextTask = result.task;
      const nextGeneration = result.generation;
      if (
        nextTask.id !== savedTask.id
        || !isClassCommentaryFeedbackRecordInScope(nextGeneration, savedTask.id, nextGeneration.id)
      ) {
        throw new Error('生成响应范围不一致');
      }
      setTask(nextTask);
      setHistoryTasks((current) => mergeHistoryTask(current, nextTask));
      setGenerations((current) => [nextGeneration, ...current.filter((item) => item.id !== nextGeneration.id)]);
      generationLoadRequestTokenRef.current += 1;
      feedbackMutationTokenRef.current += 1;
      selectedGenerationIdRef.current = String(nextGeneration.id);
      setSelectedGenerationId(String(nextGeneration.id));
      setFeedbackDraft(null);
      setLoadingGenerationId(null);
      const nextEditor = createGenerationEditorState(
        savedTask.id,
        nextGeneration,
        null,
        null,
        nextTask.latest_revision_id,
      );
      setFeedbackEditorText(nextEditor.feedbackText);
      setGenerationEditors((current) => ({
        ...current,
        [nextEditor.workspaceKey]: nextEditor,
      }));
      setRevisionPreview(null);
      setExpandedStudentIds([]);
      setCopiedStudentId(null);
      setCopyNotice('');
      setStudentFeedbackErrors({});
    } catch (error) {
      if (error instanceof ApiFetchError) {
        const rawFailedTask = error.payload.task;
        const rawFailedGeneration = error.payload.generation;
        if (
          rawFailedTask && typeof rawFailedTask === 'object'
          && rawFailedGeneration && typeof rawFailedGeneration === 'object'
        ) {
          const failedTask = normalizeClassCommentaryTask(
            rawFailedTask as Record<string, unknown>,
          );
          const failedGeneration = normalizeClassCommentaryGeneration(
            rawFailedGeneration as Record<string, unknown>,
          );
          if (
            failedTask.id === generationTaskId
            && failedGeneration.task_id === generationTaskId
            && failedGeneration.id > 0
          ) {
            setTask(failedTask);
            setHistoryTasks((current) => mergeHistoryTask(current, failedTask));
            setGenerations((current) => [
              failedGeneration,
              ...current.filter((item) => item.id !== failedGeneration.id),
            ]);
            selectedGenerationIdRef.current = String(failedGeneration.id);
            setSelectedGenerationId(String(failedGeneration.id));
            setFeedbackDraft(null);
            const failedEditor = createGenerationEditorState(
              generationTaskId,
              failedGeneration,
              null,
              null,
              failedTask.latest_revision_id,
            );
            setFeedbackEditorText(failedEditor.feedbackText);
            setGenerationEditors((current) => ({
              ...current,
              [failedEditor.workspaceKey]: failedEditor,
            }));
            setRevisionPreview(null);
            setExpandedStudentIds([]);
          }
        }
      }
      setErrorMessage(getClassCommentaryGenerationErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function handleCopy() {
    if (generationLoading || !copyText) {
      return;
    }
    await navigator.clipboard.writeText(copyText);
    setCopied(true);
    showCopyNotice(currentContentConfirmed
      ? '已复制已确认内容.'
      : '已复制未确认内容, 发送前请再次检查.');
    window.setTimeout(() => setCopied(false), 1600);
  }

  async function handleCopyStudent(studentId: number) {
    const item = displayedStudentFeedbackItems.find((candidate) => candidate.student_id === studentId);
    if (!item) {
      return;
    }
    await navigator.clipboard.writeText(formatClassCommentaryStudentFeedback(item));
    setCopiedStudentId(studentId);
    showCopyNotice(currentContentConfirmed
      ? '已复制已确认内容.'
      : '已复制未确认内容, 发送前请再次检查.');
    window.setTimeout(() => setCopiedStudentId((current) => current === studentId ? null : current), 1600);
  }

  function handlePlainFeedbackChange(nextText: string) {
    setFeedbackEditorText(nextText);
    setCopied(false);
    setCopyNotice('');
    if (!selectedWorkspaceKey) {
      return;
    }
    setGenerationEditors((current) => {
      const editor = current[selectedWorkspaceKey];
      return editor ? {
        ...current,
        [selectedWorkspaceKey]: {
          ...editor,
          feedbackText: nextText,
        },
      } : current;
    });
  }

  function handleStudentFeedbackChange(studentId: number, nextText: string) {
    if (!selectedEditorState || !selectedWorkspaceKey || revisionPreview) {
      return;
    }
    const currentItem = selectedEditorState.itemsByStudentId[studentId];
    if (!currentItem) {
      return;
    }
    const nextItemsByStudentId = {
      ...selectedEditorState.itemsByStudentId,
      [studentId]: { ...currentItem, feedback_text: nextText },
    };
    const nextItems = selectedEditorState.studentOrder
      .map((orderedStudentId) => nextItemsByStudentId[orderedStudentId])
      .filter((item): item is ClassCommentaryStudentFeedbackItem => Boolean(item));
    setGenerationEditors((current) => {
      const nextEditors = updateClassCommentaryScopedStudentFeedback(
        current,
        selectedWorkspaceKey,
        studentId,
        nextText,
      );
      const nextEditor = nextEditors[selectedWorkspaceKey];
      return nextEditor ? {
        ...nextEditors,
        [selectedWorkspaceKey]: {
          ...nextEditor,
          feedbackText: deriveClassCommentaryStructuredFeedbackText(orderedStudentFeedbackItems(nextEditor)),
        },
      } : current;
    });
    setFeedbackEditorText(deriveClassCommentaryStructuredFeedbackText(nextItems));
    setCopiedStudentId((current) => current === studentId ? null : current);
    setCopied(false);
    setCopyNotice('');
    setStudentFeedbackErrors((current) => {
      if (!current[studentId]) {
        return current;
      }
      const next = { ...current };
      delete next[studentId];
      return next;
    });
  }

  async function handleGenerationChange(nextGenerationId: string, skipDirtyGuard = false) {
    if (!task || busy || generationLoading) {
      return;
    }
    if (nextGenerationId === selectedGenerationId) {
      return;
    }
    if (feedbackDirty && !skipDirtyGuard) {
      setPendingFeedbackTransition({ kind: 'generation', generationId: nextGenerationId });
      return;
    }
    const taskId = task.id;
    const numericGenerationId = Number(nextGenerationId);
    const generationSummary = generations.find((item) => item.id === numericGenerationId) || null;
    if (
      !generationSummary
      || !isClassCommentaryFeedbackRecordInScope(generationSummary, taskId, numericGenerationId)
    ) {
      setErrorMessage('生成版本范围不一致');
      return;
    }
    const previousGenerationId = selectedGenerationId;
    const previousEditorText = feedbackEditorText;
    const previousDraft = feedbackDraft;
    const requestToken = ++generationLoadRequestTokenRef.current;
    feedbackMutationTokenRef.current += 1;
    selectedGenerationIdRef.current = nextGenerationId;
    memoryLoadRequestTokenRef.current += 1;
    setRevisionMemorySummary(null);
    setMemoryLoadError('');
    setRevisionPreview(null);
    setCopied(false);
    setCopiedStudentId(null);
    setCopyNotice('');
    setStudentFeedbackErrors({});
    setSelectedGenerationId(nextGenerationId);
    const nextWorkspaceKey = buildClassCommentaryFeedbackWorkspaceKey(taskId, numericGenerationId);
    const cached = generationEditors[nextWorkspaceKey];
    if (cached) {
      setFeedbackEditorText(cached.feedbackText);
      setFeedbackDraft(cached.draft);
      setExpandedStudentIds([]);
      setLoadingGenerationId(null);
      return;
    }
    setFeedbackEditorText('');
    setFeedbackDraft(null);
    setLoadingGenerationId(numericGenerationId);
    setErrorMessage('');
    try {
      const [generation, draft] = await Promise.all([
        fetchClassCommentaryGeneration(taskId, numericGenerationId),
        fetchClassCommentaryFeedbackDraft(taskId, numericGenerationId),
      ]);
      if (
        requestToken !== generationLoadRequestTokenRef.current
        || currentTaskIdRef.current !== taskId
        || selectedGenerationIdRef.current !== nextGenerationId
      ) {
        return;
      }
      if (
        !isClassCommentaryFeedbackRecordInScope(generation, taskId, numericGenerationId)
        || (draft && !isClassCommentaryFeedbackRecordInScope(draft, taskId, numericGenerationId))
      ) {
        throw new Error('生成版本响应范围不一致');
      }
      const revision = feedbackRevisions.find((item) => item.generation_id === numericGenerationId) || null;
      const nextEditor = createGenerationEditorState(
        taskId,
        generation,
        draft,
        revision,
        task.latest_revision_id,
      );
      setFeedbackEditorText(nextEditor.feedbackText);
      setFeedbackDraft(draft);
      setGenerationEditors((current) => ({
        ...current,
        [nextWorkspaceKey]: nextEditor,
      }));
      setExpandedStudentIds([]);
    } catch (error) {
      if (
        requestToken === generationLoadRequestTokenRef.current
        && currentTaskIdRef.current === taskId
        && selectedGenerationIdRef.current === nextGenerationId
      ) {
        selectedGenerationIdRef.current = previousGenerationId;
        setSelectedGenerationId(previousGenerationId);
        setFeedbackEditorText(previousEditorText);
        setFeedbackDraft(previousDraft);
        setErrorMessage(error instanceof Error ? error.message : '加载生成版本失败');
      }
    } finally {
      if (
        requestToken === generationLoadRequestTokenRef.current
        && currentTaskIdRef.current === taskId
      ) {
        setLoadingGenerationId(null);
      }
    }
  }

  function handleStudentFeedbackApiError(error: unknown): boolean {
    if (!(error instanceof ApiFetchError) || !selectedEditorState) {
      return false;
    }
    const studentId = Number(error.payload?.student_id || 0);
    if (!studentId || !selectedEditorState.itemsByStudentId[studentId]) {
      return false;
    }
    const message = classCommentaryStudentFeedbackErrorMessage(
      String(error.payload?.error || ''),
      Number(error.payload?.limit || 0) || undefined,
    );
    setStudentFeedbackErrors((current) => ({ ...current, [studentId]: message }));
    setExpandedStudentIds((current) => current.includes(String(studentId))
      ? current
      : [...current, String(studentId)]);
    window.requestAnimationFrame(() => {
      const textarea = document.getElementById(
        `class-commentary-student-feedback-${selectedEditorState.taskId}-${selectedEditorState.generationId}-${studentId}`,
      );
      textarea?.scrollIntoView({ block: 'center' });
      textarea?.focus();
    });
    return true;
  }

  async function handleSaveFeedbackDraft(): Promise<boolean> {
    if (!task || !selectedGeneration || !selectedEditorState) {
      return false;
    }
    const mutationTaskId = task.id;
    const mutationGenerationId = selectedGeneration.id;
    const mutationEditor = selectedEditorState;
    const mutationWorkspaceKey = mutationEditor.workspaceKey;
    const mutationFeedbackText = mutationEditor.feedbackText;
    const mutationItems = cloneStudentFeedbackItems(orderedStudentFeedbackItems(mutationEditor));
    const mutationContent = buildFeedbackWriteContent(mutationEditor);
    const expectedDraftVersion = mutationEditor.draft?.draft_version || 0;
    const mutationToken = ++feedbackMutationTokenRef.current;
    feedbackMutationActiveRef.current = true;
    setBusy(true);
    setErrorMessage('');
    setStudentFeedbackErrors({});
    let saved = false;
    try {
      const nextDraft = await saveClassCommentaryFeedbackDraft(
        mutationTaskId,
        mutationGenerationId,
        mutationContent,
        expectedDraftVersion,
        mutationEditor.draft?.based_on_revision_id || null,
      );
      if (!isCurrentFeedbackMutation(mutationTaskId, mutationGenerationId, mutationToken)) {
        return false;
      }
      if (!isClassCommentaryFeedbackRecordInScope(nextDraft, mutationTaskId, mutationGenerationId)) {
        throw new Error('草稿响应范围不一致');
      }
      const savedItems = nextDraft.feedback_schema_status === 'supported'
        ? cloneStudentFeedbackItems(nextDraft.student_feedback_items)
        : mutationItems;
      const savedText = nextDraft.feedback_schema_status === 'supported'
        ? deriveClassCommentaryStructuredFeedbackText(savedItems)
        : nextDraft.feedback_text || mutationFeedbackText;
      const nextEditor: GenerationEditorState = {
        ...mutationEditor,
        feedbackText: savedText,
        savedFeedbackText: savedText,
        studentOrder: savedItems.map((item) => item.student_id),
        itemsByStudentId: indexStudentFeedbackItems(savedItems),
        savedItemsByStudentId: indexStudentFeedbackItems(savedItems),
        draft: nextDraft,
      };
      setFeedbackDraft(nextDraft);
      setFeedbackEditorText(savedText);
      setGenerationEditors((current) => ({
        ...current,
        [mutationWorkspaceKey]: nextEditor,
      }));
      setGenerations((current) => current.map((item) => item.id === mutationGenerationId
        ? { ...item, has_draft: true, draft_version: nextDraft.draft_version }
        : item));
      saved = true;
    } catch (error) {
      if (!isCurrentFeedbackMutation(mutationTaskId, mutationGenerationId, mutationToken)) {
        return false;
      }
      if (error instanceof ApiFetchError && error.status === 409 && error.payload?.error === 'draft_version_conflict') {
        const rawCurrentDraft = error.payload.current_draft;
        const currentDraft = rawCurrentDraft && typeof rawCurrentDraft === 'object'
          ? normalizeClassCommentaryFeedbackDraft(rawCurrentDraft as Record<string, unknown>)
          : null;
        if (currentDraft && isClassCommentaryFeedbackRecordInScope(currentDraft, mutationTaskId, mutationGenerationId)) {
          setDraftConflict({
            workspaceKey: mutationWorkspaceKey,
            localText: mutationFeedbackText,
            localItems: mutationItems,
            serverDraft: currentDraft,
            attemptedExpectedDraftVersion: expectedDraftVersion,
          });
        } else {
          setErrorMessage('服务器草稿范围不一致');
        }
      } else if (!handleStudentFeedbackApiError(error)) {
        setErrorMessage(error instanceof Error ? error.message : '保存草稿失败');
      }
    } finally {
      if (isCurrentFeedbackMutation(mutationTaskId, mutationGenerationId, mutationToken)) {
        feedbackMutationActiveRef.current = false;
        setBusy(false);
      }
    }
    return saved;
  }

  async function handleConfirmFeedback(learn: boolean) {
    if (!task || !selectedGeneration || !selectedEditorState) {
      return;
    }
    const mutationTaskId = task.id;
    const mutationGenerationId = selectedGeneration.id;
    const mutationEditor = selectedEditorState;
    const mutationWorkspaceKey = mutationEditor.workspaceKey;
    const mutationFeedbackText = mutationEditor.feedbackText;
    const mutationItems = cloneStudentFeedbackItems(orderedStudentFeedbackItems(mutationEditor));
    const mutationContent = buildFeedbackWriteContent(mutationEditor);
    const expectedDraftVersion = mutationEditor.draft?.draft_version || 0;
    const expectedLatestRevisionId = mutationEditor.latestRevisionIdAtLoad;
    const confirmationRequest = claimClassCommentaryRequest(
      confirmationRequestRef.current,
      JSON.stringify({
        taskId: mutationTaskId,
        generationId: mutationGenerationId,
        content: mutationContent,
        learn,
        expectedDraftVersion,
        expectedLatestRevisionId,
      }),
      'confirmation',
    );
    confirmationRequestRef.current = confirmationRequest;
    const mutationToken = ++feedbackMutationTokenRef.current;
    feedbackMutationActiveRef.current = true;
    setBusy(true);
    setErrorMessage('');
    setStudentFeedbackErrors({});
    try {
      const { revision, draft: nextDraft } = await confirmClassCommentaryFeedback(
        mutationTaskId,
        mutationGenerationId,
        mutationContent,
        learn,
        expectedDraftVersion,
        confirmationRequest.requestId,
        expectedLatestRevisionId,
      );
      confirmationRequestRef.current = settleClassCommentaryRequest(
        confirmationRequestRef.current,
        confirmationRequest.requestId,
        true,
      );
      if (!isCurrentFeedbackMutation(mutationTaskId, mutationGenerationId, mutationToken)) {
        return;
      }
      if (
        !isClassCommentaryFeedbackRecordInScope(revision, mutationTaskId, mutationGenerationId)
        || !isClassCommentaryFeedbackRecordInScope(nextDraft, mutationTaskId, mutationGenerationId)
      ) {
        throw new Error('确认响应范围不一致');
      }
      const confirmedItems = nextDraft.feedback_schema_status === 'supported'
        ? cloneStudentFeedbackItems(nextDraft.student_feedback_items)
        : mutationItems;
      const confirmedText = nextDraft.feedback_schema_status === 'supported'
        ? deriveClassCommentaryStructuredFeedbackText(confirmedItems)
        : nextDraft.feedback_text || mutationFeedbackText;
      setFeedbackRevisions((current) => [revision, ...current.filter((item) => item.id !== revision.id)]);
      setFeedbackEditorText(confirmedText);
      setFeedbackDraft(nextDraft);
      setGenerationEditors((current) => ({
        ...current,
        [mutationWorkspaceKey]: {
          ...mutationEditor,
          feedbackText: confirmedText,
          savedFeedbackText: confirmedText,
          studentOrder: confirmedItems.map((item) => item.student_id),
          itemsByStudentId: indexStudentFeedbackItems(confirmedItems),
          savedItemsByStudentId: indexStudentFeedbackItems(confirmedItems),
          draft: nextDraft,
          latestRevisionIdAtLoad: revision.id,
        },
      }));
      setGenerations((current) => current.map((item) => item.id === mutationGenerationId
        ? {
          ...item,
          has_draft: true,
          draft_version: nextDraft.draft_version,
          latest_revision_id: revision.id,
        }
        : item));
      setTask((current) => current?.id === mutationTaskId ? {
        ...current,
        feedback_text: revision.final_feedback_text,
        final_feedback_text: revision.final_feedback_text,
        latest_revision_id: revision.id,
        feedback_revision_no: revision.revision_no,
        feedback_confirmed_at: revision.confirmed_at,
      } : current);
    } catch (error) {
      confirmationRequestRef.current = settleClassCommentaryRequest(
        confirmationRequestRef.current,
        confirmationRequest.requestId,
        error instanceof ApiFetchError,
      );
      if (!isCurrentFeedbackMutation(mutationTaskId, mutationGenerationId, mutationToken)) {
        return;
      }
      if (error instanceof ApiFetchError && error.status === 409 && error.payload?.error === 'draft_version_conflict') {
        const rawCurrentDraft = error.payload.current_draft;
        const currentDraft = rawCurrentDraft && typeof rawCurrentDraft === 'object'
          ? normalizeClassCommentaryFeedbackDraft(rawCurrentDraft as Record<string, unknown>)
          : null;
        if (currentDraft && isClassCommentaryFeedbackRecordInScope(currentDraft, mutationTaskId, mutationGenerationId)) {
          setDraftConflict({
            workspaceKey: mutationWorkspaceKey,
            localText: mutationFeedbackText,
            localItems: mutationItems,
            serverDraft: currentDraft,
            attemptedExpectedDraftVersion: expectedDraftVersion,
          });
        } else {
          setErrorMessage('服务器草稿范围不一致');
        }
      } else if (error instanceof ApiFetchError && error.status === 409 && error.payload?.error === 'revision_version_conflict') {
        const rawCurrentLatestRevision = error.payload.current_latest_revision;
        const currentLatestRevision = rawCurrentLatestRevision && typeof rawCurrentLatestRevision === 'object'
          ? normalizeClassCommentaryFeedbackRevision(rawCurrentLatestRevision as Record<string, unknown>)
          : null;
        const rawCurrentLatestRevisionId = error.payload.current_latest_revision_id;
        const currentLatestRevisionId = rawCurrentLatestRevisionId === null
          ? null
          : Number(rawCurrentLatestRevisionId || currentLatestRevision?.id || 0) || null;
        if (
          (currentLatestRevision && currentLatestRevision.task_id !== mutationTaskId)
          || (currentLatestRevision && currentLatestRevisionId !== currentLatestRevision.id)
        ) {
          setErrorMessage('服务器终稿范围不一致');
        } else {
          setRevisionConflict({
            workspaceKey: mutationWorkspaceKey,
            currentLatestRevision,
            currentLatestRevisionId,
          });
        }
      } else if (!handleStudentFeedbackApiError(error)) {
        setErrorMessage(error instanceof Error ? error.message : '确认终稿失败');
      }
    } finally {
      if (isCurrentFeedbackMutation(mutationTaskId, mutationGenerationId, mutationToken)) {
        feedbackMutationActiveRef.current = false;
        setBusy(false);
      }
    }
  }

  async function handleRetryRevisionMemory() {
    if (!selectedRevision || memoryActionKey) {
      return;
    }
    const revisionId = selectedRevision.id;
    const loadRequestToken = memoryLoadRequestTokenRef.current;
    const actionRequestToken = ++memoryActionRequestTokenRef.current;
    const retryRequest = claimClassCommentaryRequest(
      memoryRetryRequestRef.current,
      String(revisionId),
      'memory-retry',
    );
    memoryRetryRequestRef.current = retryRequest;
    setMemoryActionKey('retry');
    setErrorMessage('');
    try {
      const summary = await retryClassCommentaryRevisionMemory(
        revisionId,
        retryRequest.requestId,
      );
      memoryRetryRequestRef.current = settleClassCommentaryRequest(
        memoryRetryRequestRef.current,
        retryRequest.requestId,
        true,
      );
      if (
        actionRequestToken === memoryActionRequestTokenRef.current
        && loadRequestToken === memoryLoadRequestTokenRef.current
      ) {
        setRevisionMemorySummary(summary);
        setMemoryRefreshVersion((current) => current + 1);
      }
    } catch (error) {
      memoryRetryRequestRef.current = settleClassCommentaryRequest(
        memoryRetryRequestRef.current,
        retryRequest.requestId,
        error instanceof ApiFetchError,
      );
      if (actionRequestToken === memoryActionRequestTokenRef.current) {
        setErrorMessage(error instanceof Error ? error.message : '重试学习失败');
      }
    } finally {
      if (actionRequestToken === memoryActionRequestTokenRef.current) {
        setMemoryActionKey('');
      }
    }
  }

  async function handleRevokeMemoryEvidence(evidenceId: number) {
    if (evidenceId <= 0 || memoryActionKey) {
      return;
    }
    const loadRequestToken = memoryLoadRequestTokenRef.current;
    const actionRequestToken = ++memoryActionRequestTokenRef.current;
    const revokeRequest = claimClassCommentaryRequest(
      memoryRevokeRequestRef.current,
      String(evidenceId),
      'memory-revoke',
    );
    memoryRevokeRequestRef.current = revokeRequest;
    setMemoryActionKey(`revoke-${evidenceId}`);
    setErrorMessage('');
    try {
      const summary = await revokeClassCommentaryMemoryEvidence(
        evidenceId,
        revokeRequest.requestId,
      );
      memoryRevokeRequestRef.current = settleClassCommentaryRequest(
        memoryRevokeRequestRef.current,
        revokeRequest.requestId,
        true,
      );
      if (
        actionRequestToken === memoryActionRequestTokenRef.current
        && loadRequestToken === memoryLoadRequestTokenRef.current
      ) {
        setRevisionMemorySummary(summary);
        setMemoryRefreshVersion((current) => current + 1);
      }
    } catch (error) {
      memoryRevokeRequestRef.current = settleClassCommentaryRequest(
        memoryRevokeRequestRef.current,
        revokeRequest.requestId,
        error instanceof ApiFetchError,
      );
      if (actionRequestToken === memoryActionRequestTokenRef.current) {
        setErrorMessage(error instanceof Error ? error.message : '撤销学习来源失败');
      }
    } finally {
      if (actionRequestToken === memoryActionRequestTokenRef.current) {
        setMemoryActionKey('');
      }
    }
  }

  function handleSkillEvolutionOpenChange(open: boolean) {
    setSkillEvolutionDialogOpen(open);
    setSkillEvolutionLoadError('');
    setSkillEvolutionActionError('');
    if (open) {
      setSkillEvolutionRefreshVersion((current) => current + 1);
      return;
    }
    skillEvolutionLoadRequestTokenRef.current += 1;
    skillEvolutionActionRequestTokenRef.current += 1;
    setSkillEvolutionActionKey('');
  }

  async function handleCreateSkillCandidate() {
    if (!selectedSkill || !skillEvolution || !canCreateSkillCandidate) {
      return;
    }
    const skillId = selectedSkill.id;
    const expectedActiveVersionId = expectedActiveSkillVersionId;
    const candidateRequest = claimClassCommentaryRequest(
      skillCandidateRequestRef.current,
      JSON.stringify({ skillId, expectedActiveVersionId }),
      'skill-candidate',
    );
    skillCandidateRequestRef.current = candidateRequest;
    const actionRequestToken = ++skillEvolutionActionRequestTokenRef.current;
    setSkillEvolutionActionKey('candidate');
    setSkillEvolutionActionError('');
    try {
      const build = await createClassCommentarySkillCandidate(
        skillId,
        expectedActiveVersionId,
        candidateRequest.requestId,
      );
      skillCandidateRequestRef.current = settleClassCommentaryRequest(
        skillCandidateRequestRef.current,
        candidateRequest.requestId,
        true,
      );
      if (actionRequestToken === skillEvolutionActionRequestTokenRef.current) {
        setSkillEvolution((current) => current?.skill.id === skillId ? {
          ...current,
          candidate_builds: [build, ...current.candidate_builds.filter((item) => item.id !== build.id)],
        } : current);
        if (build.candidate_version_id) {
          setSelectedSkillVersionId(String(build.candidate_version_id));
        }
        setSkillEvolutionRefreshVersion((current) => current + 1);
      }
    } catch (error) {
      skillCandidateRequestRef.current = settleClassCommentaryRequest(
        skillCandidateRequestRef.current,
        candidateRequest.requestId,
        error instanceof ApiFetchError,
      );
      if (actionRequestToken === skillEvolutionActionRequestTokenRef.current) {
        setSkillEvolutionActionError(classCommentarySkillActionError(error, '整理更新失败'));
      }
    } finally {
      if (actionRequestToken === skillEvolutionActionRequestTokenRef.current) {
        setSkillEvolutionActionKey('');
      }
    }
  }

  async function handleChangeSkillVersion(action: 'activate' | 'rollback') {
    if (
      !selectedSkill
      || !selectedSkillVersion
      || (action === 'activate' ? !canActivateSkillVersion : !canRollbackSkillVersion)
    ) {
      return;
    }
    const skillId = selectedSkill.id;
    const versionId = selectedSkillVersion.id;
    const expectedActiveVersionId = expectedActiveSkillVersionId;
    const requestRef = action === 'activate' ? skillActivateRequestRef : skillRollbackRequestRef;
    const versionRequest = claimClassCommentaryRequest(
      requestRef.current,
      JSON.stringify({ action, skillId, versionId, expectedActiveVersionId }),
      `skill-${action}`,
    );
    requestRef.current = versionRequest;
    const actionRequestToken = ++skillEvolutionActionRequestTokenRef.current;
    setSkillEvolutionActionKey(`${action}-${versionId}`);
    setSkillEvolutionActionError('');
    try {
      const result = action === 'activate'
        ? await activateClassCommentarySkillVersion(
          skillId,
          versionId,
          expectedActiveVersionId,
          versionRequest.requestId,
        )
        : await rollbackClassCommentarySkillVersion(
          skillId,
          versionId,
          expectedActiveVersionId,
          versionRequest.requestId,
        );
      requestRef.current = settleClassCommentaryRequest(
        requestRef.current,
        versionRequest.requestId,
        true,
      );
      if (actionRequestToken === skillEvolutionActionRequestTokenRef.current) {
        const nextActiveVersionId = result.skill?.active_version_id
          || result.activation_event.current_active_version_id
          || 0;
        setSkillEvolution((current) => current?.skill.id === skillId ? {
          ...current,
          skill: {
            ...current.skill,
            active_version_id: nextActiveVersionId || current.skill.active_version_id,
          },
          versions: current.versions.map((version) => ({
            ...version,
            is_active: nextActiveVersionId > 0
              ? version.id === nextActiveVersionId
              : version.is_active,
            review_status: action === 'activate' && version.id === versionId
              ? 'approved'
              : version.review_status,
          })),
        } : current);
        setSkillEvolutionRefreshVersion((current) => current + 1);
      }
    } catch (error) {
      requestRef.current = settleClassCommentaryRequest(
        requestRef.current,
        versionRequest.requestId,
        error instanceof ApiFetchError,
      );
      if (actionRequestToken === skillEvolutionActionRequestTokenRef.current) {
        setSkillEvolutionActionError(classCommentarySkillActionError(
          error,
          action === 'activate' ? '使用更新失败' : '恢复版本失败',
        ));
        if (error instanceof ApiFetchError) {
          setSkillEvolutionRefreshVersion((current) => current + 1);
        }
      }
    } finally {
      if (actionRequestToken === skillEvolutionActionRequestTokenRef.current) {
        setSkillEvolutionActionKey('');
      }
    }
  }

  function handleDraftConflictOpenChange(open: boolean) {
    if (!open) {
      setDraftConflict(null);
    }
  }

  function handleLoadServerDraft() {
    if (!draftConflict) {
      return;
    }
    const conflictGenerationId = draftConflict.serverDraft.generation_id;
    if (
      currentTaskIdRef.current !== draftConflict.serverDraft.task_id
      || !isClassCommentaryFeedbackRecordInScope(
        draftConflict.serverDraft,
        draftConflict.serverDraft.task_id,
        conflictGenerationId,
      )
    ) {
      setDraftConflict(null);
      setErrorMessage('服务器草稿范围不一致');
      return;
    }
    const conflictWorkspaceKey = buildClassCommentaryFeedbackWorkspaceKey(
      draftConflict.serverDraft.task_id,
      conflictGenerationId,
    );
    if (conflictWorkspaceKey !== draftConflict.workspaceKey) {
      setDraftConflict(null);
      setErrorMessage('服务器草稿范围不一致');
      return;
    }
    const serverItems = draftConflict.serverDraft.feedback_schema_status === 'supported'
      ? cloneStudentFeedbackItems(draftConflict.serverDraft.student_feedback_items)
      : [];
    const serverText = serverItems.length
      ? deriveClassCommentaryStructuredFeedbackText(serverItems)
      : draftConflict.serverDraft.feedback_text;
    setGenerationEditors((current) => {
      const editor = current[conflictWorkspaceKey];
      if (!editor) {
        return current;
      }
      return {
        ...current,
        [conflictWorkspaceKey]: {
          ...editor,
          feedbackText: serverText,
          savedFeedbackText: serverText,
          studentOrder: serverItems.map((item) => item.student_id),
          itemsByStudentId: indexStudentFeedbackItems(serverItems),
          savedItemsByStudentId: indexStudentFeedbackItems(serverItems),
          draft: draftConflict.serverDraft,
        },
      };
    });
    setGenerations((current) => current.map((item) => item.id === conflictGenerationId
      ? {
        ...item,
        has_draft: true,
        draft_version: draftConflict.serverDraft.draft_version,
      }
      : item));
    if (
      currentTaskIdRef.current === draftConflict.serverDraft.task_id
      && selectedGenerationIdRef.current === String(conflictGenerationId)
    ) {
      setFeedbackEditorText(serverText);
      setFeedbackDraft(draftConflict.serverDraft);
      setExpandedStudentIds([]);
    }
    setDraftConflict(null);
  }

  async function handleCopyLocalDraft() {
    if (!draftConflict) {
      return;
    }
    const localCopyText = draftConflict.localItems.length
      ? deriveClassCommentaryStructuredFeedbackText(draftConflict.localItems)
      : draftConflict.localText;
    await navigator.clipboard.writeText(localCopyText);
    setCopied(true);
    showCopyNotice('已复制未确认内容, 发送前请再次检查.');
    window.setTimeout(() => setCopied(false), 1600);
  }

  function handleAudioChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0] || null;
    setAudioFile(nextFile);
    setUploadProgress(0);
    setCopied(false);
    setErrorMessage('');
  }

  function selectHistoryTask(nextTask: ClassCommentaryTask) {
    const nextSkillId = nextTask.skill_id || selectedSkillId;
    resetFeedbackVersionState(nextTask.id, true);
    setTask(nextTask);
    setSelectedClassId(String(nextTask.class_id));
    setSelectedSkillId(nextSkillId);
    writeClassCommentarySkillPreference(currentUser, nextSkillId);
    setConfirmedTranscript(nextTask.confirmed_transcript_text || nextTask.transcript_text || '');
    setErrorMessage('');
    setCopied(false);
    setHistoryDialogOpen(false);
  }

  function handleSelectHistoryTask(nextTask: ClassCommentaryTask, skipDirtyGuard = false) {
    if (task?.id === nextTask.id) {
      setHistoryDialogOpen(false);
      return;
    }
    if (feedbackDirty && !skipDirtyGuard) {
      setHistoryDialogOpen(false);
      setPendingFeedbackTransition({ kind: 'task', task: nextTask });
      return;
    }
    selectHistoryTask(nextTask);
  }

  function handleOpenRevisionPreview(
    revision: ClassCommentaryFeedbackRevision,
    skipDirtyGuard = false,
  ) {
    if (!task || revision.task_id !== task.id) {
      setErrorMessage('修订版本范围不一致');
      return;
    }
    if (feedbackDirty && !skipDirtyGuard) {
      setPendingFeedbackTransition({ kind: 'revision', revision });
      return;
    }
    setRevisionPreview({
      revisionPreviewKey: buildClassCommentaryRevisionPreviewKey(task.id, revision.id),
      revision,
    });
    setExpandedStudentIds([]);
    setCopied(false);
    setCopiedStudentId(null);
    setCopyNotice('');
    setStudentFeedbackErrors({});
  }

  function handleReturnFromRevisionPreview() {
    setRevisionPreview(null);
    setExpandedStudentIds([]);
    setCopied(false);
    setCopiedStudentId(null);
    setCopyNotice('');
  }

  function discardCurrentEditorChanges() {
    if (!selectedEditorState || !selectedWorkspaceKey) {
      return;
    }
    const restoredItems = cloneStudentFeedbackItems(orderedStudentFeedbackItems(selectedEditorState, true));
    const restoredText = selectedEditorState.feedbackSchemaVersion === CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1
      ? deriveClassCommentaryStructuredFeedbackText(restoredItems)
      : selectedEditorState.savedFeedbackText;
    setGenerationEditors((current) => ({
      ...current,
      [selectedWorkspaceKey]: {
        ...selectedEditorState,
        feedbackText: restoredText,
        itemsByStudentId: indexStudentFeedbackItems(restoredItems),
      },
    }));
    setFeedbackEditorText(restoredText);
  }

  function performPendingFeedbackTransition(transition: PendingFeedbackTransition) {
    setPendingFeedbackTransition(null);
    if (transition.kind === 'generation') {
      void handleGenerationChange(transition.generationId, true);
      return;
    }
    if (transition.kind === 'task') {
      handleSelectHistoryTask(transition.task, true);
      return;
    }
    if (transition.kind === 'revision') {
      handleOpenRevisionPreview(transition.revision, true);
      return;
    }
    if (transition.kind === 'create-task') {
      void handleCreateTask(true);
      return;
    }
    if (transition.kind === 'generate') {
      void handleGenerate(true);
      return;
    }
    transition.proceed();
  }

  async function handleSaveAndContinueTransition() {
    if (!pendingFeedbackTransition) {
      return;
    }
    const transition = pendingFeedbackTransition;
    if (revisionPreview) {
      setRevisionPreview(null);
    }
    if (await handleSaveFeedbackDraft()) {
      performPendingFeedbackTransition(transition);
    }
  }

  async function handleCopyPendingLocalContent() {
    if (!localEditorCopyText) {
      return;
    }
    await navigator.clipboard.writeText(localEditorCopyText);
    showCopyNotice('已复制未确认内容, 发送前请再次检查.');
  }

  function handleDiscardAndContinueTransition() {
    if (!pendingFeedbackTransition) {
      return;
    }
    const transition = pendingFeedbackTransition;
    discardCurrentEditorChanges();
    performPendingFeedbackTransition(transition);
  }

  function handleRevisionConflictOpenChange(open: boolean) {
    if (!open) {
      setRevisionConflict(null);
    }
  }

  function handlePreviewConflictingRevision() {
    if (!revisionConflict?.currentLatestRevision) {
      return;
    }
    handleOpenRevisionPreview(revisionConflict.currentLatestRevision, true);
    setRevisionConflict(null);
  }

  function handleAcknowledgeRevisionConflict() {
    if (!revisionConflict) {
      return;
    }
    const conflictEditor = generationEditors[revisionConflict.workspaceKey];
    const latestRevision = revisionConflict.currentLatestRevision;
    if (
      !conflictEditor
      || conflictEditor.taskId !== currentTaskIdRef.current
      || (latestRevision && latestRevision.task_id !== conflictEditor.taskId)
    ) {
      setRevisionConflict(null);
      setErrorMessage('服务器终稿范围不一致');
      return;
    }
    setGenerationEditors((current) => {
      const editor = current[revisionConflict.workspaceKey];
      if (!editor || editor.taskId !== conflictEditor.taskId) {
        return current;
      }
      return {
        ...current,
        [revisionConflict.workspaceKey]: {
          ...editor,
          latestRevisionIdAtLoad: revisionConflict.currentLatestRevisionId,
        },
      };
    });
    if (latestRevision) {
      setFeedbackRevisions((current) => [
        latestRevision,
        ...current.filter((item) => item.id !== latestRevision.id),
      ]);
    }
    setTask((current) => current?.id === conflictEditor.taskId ? {
      ...current,
      latest_revision_id: revisionConflict.currentLatestRevisionId,
      ...(latestRevision ? {
        final_feedback_text: latestRevision.final_feedback_text,
        feedback_revision_no: latestRevision.revision_no,
        feedback_confirmed_at: latestRevision.confirmed_at,
      } : {}),
    } : current);
    setRevisionConflict(null);
    setErrorMessage('已同步最新终稿版本, 本地修改仍保留. 请重新确认.');
  }

  function handleSkillChange(nextSkillId: string) {
    setSelectedSkillId(nextSkillId);
    writeClassCommentarySkillPreference(currentUser, nextSkillId);
  }

  function handleToggleAttendingStudent(studentId: number, checked: boolean) {
    setAttendingStudentIds((current) => {
      if (checked) {
        return current.includes(studentId) ? current : [...current, studentId];
      }
      return current.filter((item) => item !== studentId);
    });
  }

  const showStructuredFeedbackEditor = previewRevision
    ? previewStructuredFeedbackMode
    : structuredFeedbackMode;
  const structuredFeedbackAccordion = showStructuredFeedbackEditor ? (
    <Accordion
      type="multiple"
      value={expandedStudentIds}
      onValueChange={setExpandedStudentIds}
      className="rounded-lg border border-border/70 px-3"
    >
      {displayedStudentFeedbackItems.map((item) => {
        const textareaId = `class-commentary-student-feedback-${task?.id || 0}-${selectedGeneration?.id || 0}-${item.student_id}`;
        const errorId = `${textareaId}-error`;
        const itemError = studentFeedbackErrors[item.student_id] || '';
        const savedItem = selectedEditorState?.savedItemsByStudentId[item.student_id];
        const itemDirty = !revisionPreview && savedItem?.feedback_text !== item.feedback_text;
        return (
          <AccordionItem key={item.student_id} value={String(item.student_id)}>
            <AccordionTrigger>
              <span className="flex min-w-0 items-center gap-2 pr-3">
                <span className="truncate">{item.student_name}</span>
                {revisionPreview ? (
                  <Badge variant="secondary">已确认</Badge>
                ) : itemDirty ? (
                  <Badge variant="outline">已修改</Badge>
                ) : null}
              </span>
            </AccordionTrigger>
            <AccordionContent className="flex flex-col gap-3">
              <label htmlFor={textareaId} className="text-sm font-medium text-foreground">
                {item.student_name}反馈内容
              </label>
              <Textarea
                id={textareaId}
                value={item.feedback_text}
                onChange={(event) => handleStudentFeedbackChange(item.student_id, event.target.value)}
                className="min-h-32 resize-y field-sizing-fixed"
                readOnly={Boolean(revisionPreview) || isTaskReadOnly || busy}
                aria-invalid={Boolean(itemError)}
                aria-describedby={itemError ? errorId : undefined}
              />
              {itemError ? (
                <p id={errorId} className="text-xs text-destructive">{itemError}</p>
              ) : null}
              <div className="flex justify-end">
                <Button type="button" variant="outline" size="sm" onClick={() => handleCopyStudent(item.student_id)}>
                  {copiedStudentId === item.student_id
                    ? <CheckCheck data-icon="inline-start" />
                    : <Copy data-icon="inline-start" />}
                  {copiedStudentId === item.student_id ? '已复制' : '复制该学生'}
                </Button>
              </div>
            </AccordionContent>
          </AccordionItem>
        );
      })}
    </Accordion>
  ) : null;

  return (
    <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">课堂反馈</Badge>
            {task ? <Badge variant="secondary">{classCommentaryStatusLabel(task.status)}</Badge> : null}
            {copied ? <Badge>已复制</Badge> : null}
          </div>
          <div className="flex flex-col gap-1">
            <h2 className="text-xl font-semibold tracking-tight text-foreground">课堂录音反馈包</h2>
            <p className="text-sm text-muted-foreground">上传录音, 确认转写, 选择同事的测评风格后生成可复制反馈文本.</p>
          </div>
        </div>
        <Dialog open={historyDialogOpen} onOpenChange={setHistoryDialogOpen}>
          <DialogTrigger asChild>
            <Button type="button" variant="outline" disabled={busy || generationLoading}>
              <History data-icon="inline-start" />
              生成历史
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>生成历史</DialogTitle>
              <DialogDescription>查看最近生成记录, 点击一条载入对应转写和反馈结果.</DialogDescription>
            </DialogHeader>
            {loadingInitial ? (
              <div className="flex flex-col gap-3">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : historyTasks.length ? (
              <ScrollArea className="h-[60vh] rounded-lg border border-border/70">
                <div className="flex flex-col">
                  {historyTasks.map((historyTask, index) => (
                    <div key={historyTask.id}>
                      <Button
                        type="button"
                        variant="ghost"
                        className="h-auto w-full flex-col items-stretch gap-2 whitespace-normal rounded-none px-3 py-3 text-left"
                        onClick={() => handleSelectHistoryTask(historyTask)}
                        disabled={busy || generationLoading}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex min-w-0 items-center gap-2">
                            <span className="truncate text-sm font-medium text-foreground">{historyTask.class_name || '未命名班级'}</span>
                            <Badge variant={historyTask.status === 'failed' ? 'destructive' : historyTask.status === 'ready' ? 'secondary' : 'outline'}>
                              {classCommentaryStatusLabel(historyTask.status)}
                            </Badge>
                          </div>
                          <span className="text-xs text-muted-foreground">{formatClassCommentaryTime(historyTask.updated_at || historyTask.created_at)}</span>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <span className="truncate">{historyTask.skill_name || '未选择风格'}</span>
                          <span>{historyTask.audio_filename || '未记录文件名'}</span>
                        </div>
                      </Button>
                      {index < historyTasks.length - 1 ? <Separator /> : null}
                    </div>
                  ))}
                </div>
              </ScrollArea>
            ) : (
              <div className="rounded-lg border border-border/70 px-3 py-6 text-sm text-muted-foreground">
                最近还没有生成记录
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {taskErrorMessage ? (
        <Alert variant={taskStatusMessage ? 'default' : 'destructive'}>
          {taskStatusMessage ? <CheckCheck className="size-4" /> : <AlertCircle className="size-4" />}
          <AlertTitle>{taskStatusMessage ? '版本已同步' : '处理失败'}</AlertTitle>
          <AlertDescription>{taskErrorMessage}</AlertDescription>
        </Alert>
      ) : null}

      {isTaskReadOnly ? (
        <Alert>
          <AlertCircle className="size-4" />
          <AlertTitle>只读查看</AlertTitle>
          <AlertDescription>这是其他老师的课堂反馈记录, 你可以查看和复制结果, 修改和 AI 学习仍由原老师完成.</AlertDescription>
        </Alert>
      ) : null}

      {!loadingInitial && (!classes.length || !skills.length) ? (
        <Alert>
          <AlertCircle className="size-4" />
          <AlertTitle>配置未完成</AlertTitle>
          <AlertDescription>
            {!classes.length ? '当前没有可用班级。' : '当前没有可用同事测评风格。'}
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <Card>
          <CardHeader>
            <CardTitle>上传与任务</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col gap-4">
            {loadingInitial ? (
              <div className="flex flex-col gap-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : (
              <>
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                  <div className="flex flex-col gap-2">
                    <p className="text-sm font-medium text-foreground">班级</p>
                    <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                      <Select value={selectedClassId} onValueChange={setSelectedClassId}>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="请选择班级" />
                        </SelectTrigger>
                        <SelectContent position="popper" className="max-h-72">
                          <SelectGroup>
                            {classes.map((item) => (
                              <SelectItem key={item.id} value={String(item.id)}>
                                {item.name}
                              </SelectItem>
                            ))}
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                      <Popover>
                        <PopoverTrigger asChild>
                          <Button type="button" variant="outline" disabled={!selectedClassId || busy}>
                            到课学生
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent align="end" className="w-72">
                          <PopoverHeader>
                            <PopoverTitle>到课学生</PopoverTitle>
                            <PopoverDescription>
                              {loadingClassStudents ? '名单加载中' : classStudents.length ? `已到 ${attendingStudentIds.length}/${classStudents.length}` : '暂无学生名单'}
                            </PopoverDescription>
                          </PopoverHeader>
                          {loadingClassStudents ? (
                            <div className="flex flex-col gap-2">
                              <Skeleton className="h-8 w-full" />
                              <Skeleton className="h-8 w-full" />
                            </div>
                          ) : classStudents.length ? (
                            <>
                              <div className="flex items-center gap-2">
                                <Button type="button" size="xs" variant="outline" onClick={() => setAttendingStudentIds(classStudents.map((item) => item.id))} disabled={busy}>
                                  全选
                                </Button>
                                <Button type="button" size="xs" variant="outline" onClick={() => setAttendingStudentIds([])} disabled={busy}>
                                  清空
                                </Button>
                              </div>
                              <ScrollArea className="max-h-56 overflow-hidden" style={{ height: attendanceListHeight }}>
                                <div className="flex flex-col gap-2 pr-2">
                                  {classStudents.map((student) => (
                                    <label key={student.id} className="flex min-h-8 items-center gap-2 text-sm text-foreground">
                                      <Checkbox
                                        checked={attendingStudentIds.includes(student.id)}
                                        onCheckedChange={(checked) => handleToggleAttendingStudent(student.id, checked === true)}
                                        disabled={busy}
                                      />
                                      <span className="min-w-0 truncate">{student.name}</span>
                                    </label>
                                  ))}
                                </div>
                              </ScrollArea>
                            </>
                          ) : null}
                        </PopoverContent>
                      </Popover>
                    </div>
                  </div>
                  <div className="flex flex-col gap-2">
                    <p className="text-sm font-medium text-foreground">同事测评风格</p>
                    <Select value={selectedSkillId} onValueChange={handleSkillChange}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="请选择同事" />
                      </SelectTrigger>
                      <SelectContent position="popper" className="max-h-72">
                        <SelectGroup>
                          {skills.map((item) => (
                            <SelectItem key={item.id} value={item.id}>
                              {item.name}
                            </SelectItem>
                          ))}
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <p className="text-sm font-medium text-foreground">课堂录音</p>
                  <Input
                    type="file"
                    accept="audio/*,.mp3,.m4a,.mp4,.wav,.ogg,.webm,.flac"
                    onChange={handleAudioChange}
                    disabled={busy}
                  />
                  <p className="text-xs text-muted-foreground">
                    {audioFile ? `已选择: ${audioFile.name}` : '支持常见音频和录屏导出的音频文件。'}
                  </p>
                </div>

                <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                  <div className="flex min-h-8 flex-wrap items-center gap-2 rounded-lg border border-border/70 px-3 py-2">
                    <FileAudio className="size-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">
                      {selectedClass ? selectedClass.name : '未选择班级'}
                    </span>
                    {selectedSkill ? <Badge variant="outline">{selectedSkill.name}</Badge> : null}
                  </div>
                  <Button type="button" onClick={() => void handleCreateTask()} disabled={!canCreateTask}>
                    <Upload data-icon="inline-start" />
                    上传并转写
                  </Button>
                </div>

                <Separator />

                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <Sparkles className="size-4 text-muted-foreground" />
                      <span className="text-sm font-medium text-foreground">任务进度</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {task ? classCommentaryStatusLabel(task.status) : busy ? '上传中' : '待开始'}
                    </span>
                  </div>
                  <Progress value={taskProgress} />
                  <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
                    <div className="rounded-lg border border-border/70 px-3 py-2">上传 {Math.max(uploadProgress, task ? 100 : 0)}%</div>
                    <div className="rounded-lg border border-border/70 px-3 py-2">
                      转写 {task?.status === 'transcribing' ? '进行中' : task?.status === 'transcribed' || task?.status === 'generating' || task?.status === 'ready' ? '已完成' : '未开始'}
                    </div>
                    <div className="rounded-lg border border-border/70 px-3 py-2">
                      生成 {task?.status === 'generating' ? '进行中' : task?.status === 'ready' ? '已完成' : '未开始'}
                    </div>
                  </div>
                </div>

                <Separator />

                <div className="flex flex-1 flex-col gap-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-foreground">转写确认</p>
                    <Badge variant="outline">{transcriptStatusLabel}</Badge>
                  </div>
                  <Textarea
                    value={confirmedTranscript}
                    onChange={(event) => setConfirmedTranscript(event.target.value)}
                    placeholder="可直接输入课堂记录, 也可以上传并转写后在这里确认或修订文本."
                    className="min-h-56 flex-1 resize-none field-sizing-fixed"
                    disabled={loadingInitial || isTaskReadOnly}
                  />
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm text-muted-foreground">
                      {hasSucceededGeneration && !transcriptDirty
                        ? '转写已保存, 修改后可重新生成反馈包.'
                        : '可直接输入文本生成反馈包; 已有录音任务时也可以先保存确认文本.'}
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button type="button" variant="outline" onClick={handleSaveTranscript} disabled={!canSaveTranscript}>
                        保存转写
                      </Button>
                      <Button
                        type="button"
                        variant={hasSucceededGeneration ? 'outline' : 'default'}
                        onClick={() => void handleGenerate()}
                        disabled={!canGenerate}
                      >
                        {hasSucceededGeneration ? '重新生成' : '生成反馈包'}
                      </Button>
                    </div>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>反馈结果</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {loadingInitial ? (
              <div className="flex flex-col gap-3">
                <Skeleton className="h-5 w-28" />
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-8 w-28" />
              </div>
            ) : (
              <>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="rounded-lg border border-border/70 px-3 py-2">
                    <p className="text-xs text-muted-foreground">班级</p>
                    <p className="mt-1 text-sm font-medium text-foreground">{task?.class_name || selectedClass?.name || '-'}</p>
                  </div>
                  <div className="rounded-lg border border-border/70 px-3 py-2">
                    <p className="text-xs text-muted-foreground">同事测评风格</p>
                    <p className="mt-1 text-sm font-medium text-foreground">{task?.skill_name || selectedSkill?.name || '-'}</p>
                  </div>
                </div>
                <Separator />
                <div className="flex flex-col gap-2">
                  <p className="text-sm font-medium text-foreground">生成版本</p>
                  <Select value={selectedGenerationId} onValueChange={handleGenerationChange} disabled={busy || generationLoading}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="请选择生成版本" />
                    </SelectTrigger>
                    <SelectContent position="popper" className="max-h-72">
                      <SelectGroup>
                        {generations.map((generation) => (
                          <SelectItem key={generation.id} value={String(generation.id)}>
                            第 {generation.generation_no} 次 · {formatClassCommentaryTime(generation.completed_at || generation.created_at)}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={selectedGeneration?.status === 'failed' ? 'destructive' : 'outline'}>
                      {selectedGeneration?.status === 'succeeded' ? '已生成' : selectedGeneration?.status === 'failed' ? '失败' : selectedGeneration ? '生成中' : '未创建任务'}
                    </Badge>
                    {!revisionPreview && feedbackDraft ? <Badge variant="secondary">草稿 v{feedbackDraft.draft_version}</Badge> : null}
                    {revisionPreview ? (
                      <Badge variant="secondary">已确认第 {revisionPreview.revision.revision_no} 版</Badge>
                    ) : selectedRevision ? (
                      <Badge variant="secondary">已确认第 {selectedRevision.revision_no} 版</Badge>
                    ) : null}
                    {feedbackDirty ? <Badge variant="outline">当前编辑未保存</Badge> : null}
                    {!currentContentConfirmed ? <Badge variant="outline">未确认</Badge> : null}
                  </div>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    {revisionPreview ? (
                      <Button type="button" variant="outline" onClick={handleReturnFromRevisionPreview}>
                        返回当前编辑
                      </Button>
                    ) : null}
                    <Button type="button" variant="outline" onClick={handleCopy} disabled={generationLoading || !copyText}>
                      {copied ? <CheckCheck data-icon="inline-start" /> : <Copy data-icon="inline-start" />}
                      {showStructuredFeedbackEditor ? '复制全部' : '复制结果'}
                    </Button>
                  </div>
                </div>
                {showStructuredFeedbackEditor ? (
                  displayedStudentFeedbackItems.length >= 5 ? (
                    <ScrollArea
                      className="h-[clamp(280px,55vh,480px)] overflow-hidden sm:h-[clamp(320px,60vh,560px)]"
                      data-testid="structured-feedback-scroll-area"
                    >
                      <div className="pr-3 pb-2">{structuredFeedbackAccordion}</div>
                    </ScrollArea>
                  ) : structuredFeedbackAccordion
                ) : (
                  <Textarea
                    value={previewRevision ? previewRevision.final_feedback_text : feedbackEditorText}
                    onChange={(event) => handlePlainFeedbackChange(event.target.value)}
                    placeholder="生成完成后, 这里会显示可修改并确认的反馈文本."
                    className="min-h-64"
                    readOnly={Boolean(revisionPreview) || isTaskReadOnly || feedbackSchemaReadOnly}
                    disabled={!isTaskReadOnly && !revisionPreview && (busy || generationLoading || !selectedGeneration || selectedGeneration.status !== 'succeeded')}
                  />
                )}
                {feedbackSchemaNotice ? (
                  <p className="text-xs text-muted-foreground">{feedbackSchemaNotice}</p>
                ) : null}
                {copyNotice ? (
                  <Alert
                    role="status"
                    aria-live="polite"
                    aria-atomic="true"
                    data-testid="copy-notice-toast"
                    className="fixed right-4 bottom-4 z-50 w-[calc(100%-2rem)] max-w-sm shadow-lg"
                  >
                    <CheckCheck className="size-4" />
                    <AlertTitle>复制成功</AlertTitle>
                    <AlertDescription>{copyNotice}</AlertDescription>
                  </Alert>
                ) : null}
                {!revisionPreview ? (
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <Button type="button" variant="outline" onClick={handleSaveFeedbackDraft} disabled={!canSaveFeedbackDraft}>
                      保存草稿
                    </Button>
                    <Button type="button" variant="outline" onClick={() => handleConfirmFeedback(false)} disabled={!canConfirmFeedback}>
                      确认但不学习
                    </Button>
                    <Button type="button" onClick={() => handleConfirmFeedback(true)} disabled={!canConfirmFeedback || !capabilities.memory_learning_enabled}>
                      确认并让 AI 学习修改
                    </Button>
                  </div>
                ) : null}
                {!revisionPreview && !capabilities.memory_learning_enabled ? (
                  <p className="text-xs text-muted-foreground">记忆学习功能尚未启用, 仍可正常保存草稿或确认终稿.</p>
                ) : null}
                {!revisionPreview && !isTaskReadOnly && capabilities.memory_learning_enabled && selectedRevision?.learn_requested ? (
                  <>
                    <Separator />
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-foreground">本次学到的内容</p>
                        {revisionMemorySummary ? (
                          <Badge variant={revisionMemorySummary.status === 'failed' ? 'destructive' : revisionMemorySummary.status === 'complete' ? 'secondary' : 'outline'}>
                            {classCommentaryMemoryStatusLabel(revisionMemorySummary.status)}
                          </Badge>
                        ) : memoryLoadError ? (
                          <Badge variant="outline">暂不可用</Badge>
                        ) : (
                          <Badge variant="outline">读取中</Badge>
                        )}
                      </div>
                      {memoryLoadError || revisionMemorySummary?.error ? (
                        <p className="text-xs text-muted-foreground">{memoryLoadError || revisionMemorySummary?.error}</p>
                      ) : null}
                      {revisionMemorySummary?.memories.length ? (
                        <div className="flex flex-col gap-2">
                          {revisionMemorySummary.memories.map((memory) => (
                            <div key={memory.evidence_id} className="flex items-start justify-between gap-3 rounded-lg border border-border/70 px-3 py-2">
                              <div className="flex min-w-0 flex-col gap-1">
                                <div className="flex flex-wrap items-center gap-2">
                                  <Badge variant="outline">
                                    {memory.memory_type === 'teacher_style'
                                      ? `对 ${selectedSkill?.name || '该同事'}测评风格的调整`
                                      : '学生情况'}
                                  </Badge>
                                  {memory.student_name ? <span className="text-xs text-muted-foreground">{memory.student_name}</span> : null}
                                  {memory.evidence_status !== 'active' ? <Badge variant="secondary">已撤销来源</Badge> : null}
                                </div>
                                <p className="text-sm text-foreground">{memory.memory_text}</p>
                                <p className="text-xs text-muted-foreground">当前有效来源 {memory.active_evidence_count} 条</p>
                              </div>
                              {memory.can_revoke && memory.evidence_status === 'active' ? (
                                <AlertDialog>
                                  <AlertDialogTrigger asChild>
                                    <Button
                                      type="button"
                                      size="xs"
                                      variant="outline"
                                      disabled={Boolean(memoryActionKey)}
                                    >
                                      {memoryActionKey === `revoke-${memory.evidence_id}` ? '撤销中' : '撤销我的来源'}
                                    </Button>
                                  </AlertDialogTrigger>
                                  <AlertDialogContent>
                                    <AlertDialogHeader>
                                      <AlertDialogTitle>撤销这条学习来源?</AlertDialogTitle>
                                      <AlertDialogDescription>
                                        撤销后, 这次修改将不再作为后续反馈的学习依据.
                                      </AlertDialogDescription>
                                    </AlertDialogHeader>
                                    <AlertDialogFooter>
                                      <AlertDialogCancel>取消</AlertDialogCancel>
                                      <AlertDialogAction
                                        variant="destructive"
                                        onClick={() => handleRevokeMemoryEvidence(memory.evidence_id)}
                                      >
                                        确认撤销
                                      </AlertDialogAction>
                                    </AlertDialogFooter>
                                  </AlertDialogContent>
                                </AlertDialog>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      ) : revisionMemorySummary && !['queued', 'extracting', 'syncing'].includes(revisionMemorySummary.status) ? (
                        <p className="text-xs text-muted-foreground">本次没有形成可复用记忆.</p>
                      ) : null}
                      {revisionMemorySummary?.retryable ? (
                        <div className="flex justify-end">
                          <Button
                            type="button"
                            size="xs"
                            variant="outline"
                            disabled={Boolean(memoryActionKey)}
                            onClick={handleRetryRevisionMemory}
                          >
                            {memoryActionKey === 'retry' ? '重试中' : '重试学习'}
                          </Button>
                        </div>
                      ) : null}
                    </div>
                  </>
                ) : null}
                {capabilities.skill_evolution_enabled && selectedSkill ? (
                  <>
                    <Separator />
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex flex-col gap-1">
                        <p className="text-sm font-medium text-foreground">{selectedSkill.name}的测评风格</p>
                        <p className="text-xs text-muted-foreground">查看 AI 从大家的确认修改中整理出的风格更新.</p>
                      </div>
                      <Dialog open={skillEvolutionDialogOpen} onOpenChange={handleSkillEvolutionOpenChange}>
                        <DialogTrigger asChild>
                          <Button type="button" size="xs" variant="outline">查看风格更新</Button>
                        </DialogTrigger>
                        <DialogContent className="max-h-[90vh] sm:max-w-3xl">
                          <DialogHeader>
                            <DialogTitle>{selectedSkill.name}的测评风格</DialogTitle>
                            <DialogDescription>
                              AI 会从大家使用这个同事测评风格时确认的修改中整理可复用的调整.
                            </DialogDescription>
                          </DialogHeader>
                          <ScrollArea className="h-[70vh] overflow-hidden">
                            <div className="flex flex-col gap-4 pr-3">
                              <Alert>
                                <Sparkles />
                                <AlertTitle>更新不会自动使用</AlertTitle>
                                <AlertDescription>
                                  你确认使用后, 新生成的课堂反馈才会采用这次调整. 已有反馈不会被改写.
                                </AlertDescription>
                              </Alert>
                              {skillEvolutionLoadError ? (
                                <Alert>
                                  <AlertCircle />
                                  <AlertTitle>读取暂时不可用</AlertTitle>
                                  <AlertDescription>{skillEvolutionLoadError}</AlertDescription>
                                </Alert>
                              ) : null}
                              {skillEvolutionActionError ? (
                                <Alert variant="destructive">
                                  <AlertCircle />
                                  <AlertTitle>操作未完成</AlertTitle>
                                  <AlertDescription>{skillEvolutionActionError}</AlertDescription>
                                </Alert>
                              ) : null}
                              {!skillEvolution ? (
                                <div className="flex flex-col gap-3">
                                  <Skeleton className="h-20 w-full" />
                                  <Skeleton className="h-9 w-full" />
                                  <Skeleton className="h-48 w-full" />
                                </div>
                              ) : (
                                <>
                                  <div className="flex flex-col gap-3 rounded-lg border border-border/70 p-3">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <div className="flex flex-wrap items-center gap-2">
                                        <Badge variant={skillEvolution.eligibility.eligible ? 'secondary' : 'outline'}>
                                          {`有效修改 ${skillEvolution.eligibility.effective_task_count}/${skillEvolution.eligibility.min_effective_tasks}`}
                                        </Badge>
                                      </div>
                                      <Button
                                        type="button"
                                        size="xs"
                                        onClick={handleCreateSkillCandidate}
                                        disabled={!canCreateSkillCandidate}
                                      >
                                        {skillEvolutionActionKey === 'candidate'
                                          ? '整理中'
                                          : latestSkillCandidateBuild?.status === 'failed' && latestSkillCandidateBuild.can_retry
                                            ? '重新整理'
                                            : '整理一次更新'}
                                      </Button>
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                      {classCommentarySkillEligibilityMessage(skillEvolution.eligibility)}
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                      每个课堂只计最新一次确认并学习的真实修改, 原样确认不计入.
                                    </p>
                                  </div>

                                  {latestSkillCandidateBuild ? (
                                    <div className="flex flex-col gap-2 rounded-lg border border-border/70 p-3">
                                      <div className="flex flex-wrap items-center gap-2">
                                        <span className="text-sm font-medium text-foreground">最近一次整理</span>
                                        <Badge variant={latestSkillCandidateBuild.status === 'failed' ? 'destructive' : 'outline'}>
                                          {classCommentarySkillCandidateStatusLabel(latestSkillCandidateBuild.status)}
                                        </Badge>
                                        {latestSkillCandidateBuild.is_stale ? <Badge variant="secondary">需要重新整理</Badge> : null}
                                      </div>
                                      {latestSkillCandidateBuild.error_message ? (
                                        <p className="text-xs text-muted-foreground">{latestSkillCandidateBuild.error_message}</p>
                                      ) : null}
                                    </div>
                                  ) : null}

                                  {skillEvolution.versions.length ? (
                                    <>
                                      <div className="flex flex-col gap-2">
                                        <p className="text-sm font-medium text-foreground">选择风格版本</p>
                                        <Select value={selectedSkillVersionId} onValueChange={setSelectedSkillVersionId}>
                                          <SelectTrigger className="w-full">
                                            <SelectValue placeholder="请选择要查看的版本" />
                                          </SelectTrigger>
                                          <SelectContent position="popper" className="max-h-72">
                                            <SelectGroup>
                                              {skillEvolution.versions.map((version) => (
                                                <SelectItem key={version.id} value={String(version.id)}>
                                                  第 {version.version_no} 版 - {version.is_active
                                                    ? '正在使用'
                                                    : version.review_status === 'pending'
                                                      ? '等待确认'
                                                      : version.version_kind === 'candidate'
                                                        ? '历史更新'
                                                        : '最初版本'}
                                                </SelectItem>
                                              ))}
                                            </SelectGroup>
                                          </SelectContent>
                                        </Select>
                                      </div>

                                      {selectedSkillVersion ? (
                                        <div className="flex flex-col gap-4">
                                          <div className="flex flex-wrap items-center gap-2">
                                            <Badge variant="outline">第 {selectedSkillVersion.version_no} 版</Badge>
                                            {selectedSkillVersion.is_active ? <Badge variant="secondary">正在使用</Badge> : null}
                                            {selectedSkillVersion.review_status === 'pending' ? <Badge variant="outline">等待确认</Badge> : null}
                                            {selectedSkillVersion.is_stale ? <Badge variant="destructive">需要重新整理</Badge> : null}
                                          </div>

                                          {selectedSkillVersion.is_stale ? (
                                            <Alert variant="destructive">
                                              <AlertCircle />
                                              <AlertTitle>这次建议已经过期</AlertTitle>
                                              <AlertDescription>
                                                {classCommentarySkillStaleMessage(selectedSkillVersion.stale_reason)}
                                              </AlertDescription>
                                            </Alert>
                                          ) : null}

                                          <Alert>
                                            <Sparkles />
                                            <AlertTitle>
                                              {selectedSkillVersion.version_kind === 'candidate'
                                                ? '本次建议的调整'
                                                : '当前正在使用'}
                                            </AlertTitle>
                                            <AlertDescription>
                                              {selectedSkillVersion.evaluation.change_summary.length ? (
                                                <div className="flex flex-col gap-1">
                                                  {selectedSkillVersion.evaluation.change_summary.map((change) => (
                                                    <p key={change}>· {change}</p>
                                                  ))}
                                                </div>
                                              ) : (
                                                <p>
                                                  {selectedSkillVersion.version_kind === 'candidate'
                                                    ? '这次更新暂无可展示的说明.'
                                                    : `后续生成会继续使用${selectedSkill.name}的这版测评风格.`}
                                                </p>
                                              )}
                                            </AlertDescription>
                                          </Alert>

                                          {selectedSkillVersion.evaluation.known_risks.length
                                            || selectedSkillVersion.evaluation.failed_sample_count > 0 ? (
                                              <Alert variant="destructive">
                                                <AlertCircle />
                                                <AlertTitle>自动检查需要留意</AlertTitle>
                                                <AlertDescription>
                                                  <div className="flex flex-col gap-1">
                                                    {selectedSkillVersion.evaluation.known_risks.map((risk) => (
                                                      <p key={`risk-${risk}`}>{risk}</p>
                                                    ))}
                                                    {selectedSkillVersion.evaluation.failed_sample_count > 0 ? (
                                                      <p>有 {selectedSkillVersion.evaluation.failed_sample_count} 条历史反馈检查未通过.</p>
                                                    ) : null}
                                                  </div>
                                                </AlertDescription>
                                              </Alert>
                                            ) : null}

                                          <div className="flex flex-wrap justify-end gap-2">
                                            {selectedSkillVersion.version_kind === 'candidate'
                                              && selectedSkillVersion.review_status === 'pending'
                                              && !selectedSkillVersion.is_active
                                              && !selectedSkillVersion.is_stale ? (
                                                <AlertDialog>
                                                  <AlertDialogTrigger asChild>
                                                    <Button type="button" disabled={!canActivateSkillVersion}>
                                                      {skillEvolutionActionKey === `activate-${selectedSkillVersion.id}`
                                                        ? '使用中'
                                                        : '使用这次更新'}
                                                    </Button>
                                                  </AlertDialogTrigger>
                                                  <AlertDialogContent>
                                                    <AlertDialogHeader>
                                                      <AlertDialogTitle>使用这次风格更新?</AlertDialogTitle>
                                                      <AlertDialogDescription>
                                                        确认后, 新生成的课堂反馈会使用第 {selectedSkillVersion.version_no} 版. 已有反馈不会被改写.
                                                      </AlertDialogDescription>
                                                    </AlertDialogHeader>
                                                    <AlertDialogFooter>
                                                      <AlertDialogCancel>取消</AlertDialogCancel>
                                                      <AlertDialogAction onClick={() => handleChangeSkillVersion('activate')}>
                                                        确认使用
                                                      </AlertDialogAction>
                                                    </AlertDialogFooter>
                                                  </AlertDialogContent>
                                                </AlertDialog>
                                              ) : null}
                                            {!selectedSkillVersion.is_active
                                              && (selectedSkillVersion.review_status === 'approved'
                                                || selectedSkillVersion.review_status === 'not_required') ? (
                                                  <AlertDialog>
                                                    <AlertDialogTrigger asChild>
                                                      <Button type="button" variant="outline" disabled={!canRollbackSkillVersion}>
                                                        {skillEvolutionActionKey === `rollback-${selectedSkillVersion.id}`
                                                          ? '恢复中'
                                                          : `恢复使用第 ${selectedSkillVersion.version_no} 版`}
                                                      </Button>
                                                    </AlertDialogTrigger>
                                                    <AlertDialogContent>
                                                      <AlertDialogHeader>
                                                        <AlertDialogTitle>恢复使用这个历史版本?</AlertDialogTitle>
                                                        <AlertDialogDescription>
                                                          确认后, 新生成的课堂反馈会重新使用第 {selectedSkillVersion.version_no} 版. 已有反馈不会被改写.
                                                        </AlertDialogDescription>
                                                      </AlertDialogHeader>
                                                      <AlertDialogFooter>
                                                        <AlertDialogCancel>取消</AlertDialogCancel>
                                                        <AlertDialogAction onClick={() => handleChangeSkillVersion('rollback')}>
                                                          确认恢复
                                                        </AlertDialogAction>
                                                      </AlertDialogFooter>
                                                    </AlertDialogContent>
                                                  </AlertDialog>
                                                ) : null}
                                          </div>
                                        </div>
                                      ) : null}
                                    </>
                                  ) : (
                                    <p className="text-xs text-muted-foreground">当前还没有可查看的风格更新.</p>
                                  )}
                                </>
                              )}
                            </div>
                          </ScrollArea>
                        </DialogContent>
                      </Dialog>
                    </div>
                  </>
                ) : null}
                <Separator />
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-foreground">修订记录</p>
                  <Badge variant="outline">{feedbackRevisions.length} 条</Badge>
                </div>
                {feedbackRevisions.length ? (
                  <ScrollArea className="h-32 overflow-hidden">
                    <div className="flex flex-col gap-2 pr-2">
                      {feedbackRevisions.map((revision) => (
                        <div key={revision.id} className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenRevisionPreview(revision)}
                          >
                            查看第 {revision.revision_no} 版 · {revision.learn_requested ? '已请求学习' : '未学习'}
                          </Button>
                          <span>{formatClassCommentaryTime(revision.confirmed_at)}</span>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                ) : (
                  <p className="text-xs text-muted-foreground">确认终稿后会在这里留下记录.</p>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={Boolean(draftConflict)} onOpenChange={handleDraftConflictOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>草稿版本冲突</DialogTitle>
            <DialogDescription>
              服务器上已有更新的草稿. 你可以加载服务器版本, 或先复制当前页面中的本地内容.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleCopyLocalDraft}>
              复制本地内容
            </Button>
            <Button type="button" onClick={handleLoadServerDraft}>
              加载服务器版本
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(pendingFeedbackTransition)}
        onOpenChange={(open) => {
          if (!open) {
            setPendingFeedbackTransition(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>有未保存的反馈修改</DialogTitle>
            <DialogDescription>
              {revisionPreview ? '你正在查看历史终稿, 当前编辑仍有未保存修改. ' : ''}
              保存整份草稿后继续, 或先复制当前编辑的本地内容. 放弃会丢掉当前这份未保存修改.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-wrap">
            <Button type="button" variant="outline" onClick={() => setPendingFeedbackTransition(null)}>
              取消
            </Button>
            <Button type="button" variant="outline" onClick={handleCopyPendingLocalContent}>
              复制本地内容
            </Button>
            <Button type="button" variant="destructive" onClick={handleDiscardAndContinueTransition}>
              放弃并切换
            </Button>
            <Button type="button" onClick={handleSaveAndContinueTransition} disabled={!canSavePendingFeedbackTransition}>
              保存草稿
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(revisionConflict)} onOpenChange={handleRevisionConflictOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>终稿版本已更新</DialogTitle>
            <DialogDescription>
              另一处已经确认了更新的终稿. 当前本地修改仍然保留, 请先查看最新版本或关闭后重试.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleCopy}>
              复制本地内容
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={handlePreviewConflictingRevision}
              disabled={!revisionConflict?.currentLatestRevision}
            >
              查看最新终稿
            </Button>
            <Button type="button" onClick={handleAcknowledgeRevisionConflict}>
              同步版本并保留本地修改
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
