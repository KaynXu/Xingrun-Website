import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { AlertCircle, CheckCheck, Copy, FileAudio, History, Sparkles, Upload } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
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
  classCommentaryStatusLabel,
  createClassCommentaryTask,
  createClassCommentaryTextTask,
  confirmClassCommentaryFeedback,
  fetchClassCommentaryCapabilities,
  fetchClassCommentaryFeedbackDraft,
  fetchClassCommentaryFeedbackRevisions,
  fetchClassCommentaryGeneration,
  fetchClassCommentaryGenerations,
  fetchClassCommentarySkills,
  fetchClassCommentaryTasks,
  fetchClassCommentaryTask,
  generateClassCommentaryFeedback,
  isClassCommentaryFeedbackRecordInScope,
  readClassCommentarySkillPreference,
  resolveClassCommentaryCopyText,
  saveClassCommentaryFeedbackDraft,
  saveClassCommentaryTranscript,
  shouldPollClassCommentaryTask,
  type ClassCommentarySkill,
  type ClassCommentaryCapabilities,
  type ClassCommentaryFeedbackDraft,
  type ClassCommentaryFeedbackRevision,
  type ClassCommentaryGeneration,
  type ClassCommentaryTask,
  writeClassCommentarySkillPreference,
} from '../../classCommentary';
import { ApiFetchError, apiFetch } from '../../workspaceShared';

type ClassFeedbackGenerationPageProps = {
  currentUser: CurrentUser;
};

type ClassFeedbackStudent = {
  id: number;
  name: string;
};

type GenerationEditorState = {
  feedbackText: string;
  savedFeedbackText: string;
  draft: ClassCommentaryFeedbackDraft | null;
};

const disabledClassCommentaryCapabilities: ClassCommentaryCapabilities = {
  memory_learning_enabled: false,
  skill_evolution_enabled: false,
};

function createClassCommentaryRequestId(prefix: string): string {
  const randomId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${randomId}`;
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
    return task.generation_error || '生成失败';
  }
  return '任务失败';
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

function mergeHistoryTask(historyTasks: ClassCommentaryTask[], nextTask: ClassCommentaryTask): ClassCommentaryTask[] {
  return [nextTask, ...historyTasks.filter((item) => item.id !== nextTask.id)].slice(0, 30);
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
  const [generationEditors, setGenerationEditors] = useState<Record<number, GenerationEditorState>>({});
  const [feedbackRevisions, setFeedbackRevisions] = useState<ClassCommentaryFeedbackRevision[]>([]);
  const [loadingGenerationId, setLoadingGenerationId] = useState<number | null>(null);
  const [capabilities, setCapabilities] = useState<ClassCommentaryCapabilities>(disabledClassCommentaryCapabilities);
  const [draftConflict, setDraftConflict] = useState<{
    localText: string;
    serverDraft: ClassCommentaryFeedbackDraft;
  } | null>(null);
  const generationLoadRequestTokenRef = useRef(0);
  const feedbackMutationActiveRef = useRef(false);
  const feedbackMutationTokenRef = useRef(0);
  const currentTaskIdRef = useRef<number | null>(null);
  const selectedGenerationIdRef = useRef('');

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
    setGenerationEditors({});
    setLoadingGenerationId(null);
    setDraftConflict(null);
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
      fetchClassCommentaryCapabilities(),
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
          setGenerationEditors({});
          return;
        }
        const cachedTarget = generationEditors[targetGeneration.id];
        if (
          selectedGenerationIdRef.current === String(targetGeneration.id)
          && cachedTarget
          && (!cachedTarget.draft || isClassCommentaryFeedbackRecordInScope(
            cachedTarget.draft,
            taskId,
            targetGeneration.id,
          ))
        ) {
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
        setGenerationEditors({});
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
        const nextText = resolveClassCommentaryCopyText(nextDraft, latestRevision, generationDetail)
          || task.feedback_text
          || '';
        setFeedbackEditorText(nextText);
        setFeedbackDraft(nextDraft);
        setGenerationEditors({
          [targetGenerationId]: {
            feedbackText: nextText,
            savedFeedbackText: nextDraft?.feedback_text || nextText,
            draft: nextDraft,
          },
        });
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
            setGenerationEditors({});
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
  const selectedRevision = feedbackRevisions.find((item) => item.id === task?.latest_revision_id
    && item.generation_id === selectedGeneration?.id) || null;
  const selectedEditorState = selectedGeneration ? generationEditors[selectedGeneration.id] : undefined;
  const generationLoading = loadingGenerationId !== null;
  const copyText = resolveClassCommentaryCopyText(
    feedbackDraft,
    selectedRevision,
    selectedGeneration,
    generationLoading,
  );
  const taskErrorMessage = getTaskErrorMessage(task, errorMessage);
  const taskProgress = getTaskProgress(task, uploadProgress);
  const trimmedConfirmedTranscript = confirmedTranscript.trim();
  const persistedTranscript = (task?.confirmed_transcript_text || task?.transcript_text || '').trim();
  const hasTranscriptText = Boolean(trimmedConfirmedTranscript);
  const transcriptDirty = Boolean(task) && trimmedConfirmedTranscript !== persistedTranscript;
  const canUseTranscript = canUseTranscriptState(task);
  const canCreateManualTextTask = !task || task.status === 'uploaded' || task.status === 'transcribing';
  const canCreateTask = !loadingInitial && !busy && !generationLoading && Boolean(selectedClassId && audioFile);
  const canSaveTranscript = !busy && !generationLoading && canUseTranscript && hasTranscriptText;
  const canGenerate = !busy && !generationLoading && !loadingClassStudents && hasTranscriptText && Boolean(selectedClassId && selectedSkillId) && (canUseTranscript || canCreateManualTextTask) && (!classStudents.length || attendingStudentIds.length > 0);
  const canSaveFeedbackDraft = !busy
    && !generationLoading
    && selectedGeneration?.status === 'succeeded'
    && Boolean(feedbackEditorText.trim())
    && feedbackEditorText !== (selectedEditorState?.savedFeedbackText || '');
  const canConfirmFeedback = !busy
    && !generationLoading
    && selectedGeneration?.status === 'succeeded'
    && Boolean(feedbackEditorText.trim());
  const attendanceListHeight = Math.min(224, Math.max(32, classStudents.length * 40 - 8));

  async function handleCreateTask() {
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

  async function handleGenerate() {
    if (!selectedClassId || !selectedSkillId) {
      setErrorMessage('请选择同事风格后再生成');
      return;
    }
    if (!trimmedConfirmedTranscript) {
      setErrorMessage('请先确认转写文本');
      return;
    }
    if (classStudents.length && !attendingStudentIds.length) {
      setErrorMessage('请选择到课学生');
      return;
    }
    setBusy(true);
    setErrorMessage('');
    try {
      const savedTask = task && canUseTranscript
        ? (transcriptDirty ? await saveClassCommentaryTranscript(task.id, trimmedConfirmedTranscript) : task)
        : await createClassCommentaryTextTask(Number(selectedClassId), trimmedConfirmedTranscript);
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
      setFeedbackEditorText(nextGeneration.generated_feedback_text);
      setGenerationEditors((current) => ({
        ...current,
        [nextGeneration.id]: {
          feedbackText: nextGeneration.generated_feedback_text,
          savedFeedbackText: nextGeneration.generated_feedback_text,
          draft: null,
        },
      }));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '生成失败');
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
    window.setTimeout(() => setCopied(false), 1600);
  }

  async function handleGenerationChange(nextGenerationId: string) {
    if (!task || busy || generationLoading) {
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
    const numericPreviousGenerationId = Number(previousGenerationId);
    if (numericPreviousGenerationId > 0) {
      setGenerationEditors((current) => ({
        ...current,
        [numericPreviousGenerationId]: {
          feedbackText: feedbackEditorText,
          savedFeedbackText: current[numericPreviousGenerationId]?.savedFeedbackText || feedbackEditorText,
          draft: feedbackDraft,
        },
      }));
    }
    setSelectedGenerationId(nextGenerationId);
    const cached = generationEditors[numericGenerationId];
    if (cached) {
      setFeedbackEditorText(cached.feedbackText);
      setFeedbackDraft(cached.draft);
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
      const nextText = resolveClassCommentaryCopyText(draft, revision, generation);
      setFeedbackEditorText(nextText);
      setFeedbackDraft(draft);
      setGenerationEditors((current) => ({
        ...current,
        [numericGenerationId]: {
          feedbackText: nextText,
          savedFeedbackText: draft?.feedback_text || nextText,
          draft,
        },
      }));
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

  async function handleSaveFeedbackDraft() {
    if (!task || !selectedGeneration) {
      return;
    }
    const mutationTaskId = task.id;
    const mutationGenerationId = selectedGeneration.id;
    const mutationFeedbackText = feedbackEditorText;
    const mutationToken = ++feedbackMutationTokenRef.current;
    feedbackMutationActiveRef.current = true;
    setBusy(true);
    setErrorMessage('');
    try {
      const nextDraft = await saveClassCommentaryFeedbackDraft(
        mutationTaskId,
        mutationGenerationId,
        mutationFeedbackText,
        feedbackDraft?.draft_version || 0,
        feedbackDraft?.based_on_revision_id || null,
      );
      if (!isCurrentFeedbackMutation(mutationTaskId, mutationGenerationId, mutationToken)) {
        return;
      }
      if (!isClassCommentaryFeedbackRecordInScope(nextDraft, mutationTaskId, mutationGenerationId)) {
        throw new Error('草稿响应范围不一致');
      }
      setFeedbackDraft(nextDraft);
      setGenerationEditors((current) => ({
        ...current,
        [mutationGenerationId]: {
          feedbackText: mutationFeedbackText,
          savedFeedbackText: mutationFeedbackText,
          draft: nextDraft,
        },
      }));
      setGenerations((current) => current.map((item) => item.id === mutationGenerationId
        ? { ...item, has_draft: true, draft_version: nextDraft.draft_version }
        : item));
    } catch (error) {
      if (!isCurrentFeedbackMutation(mutationTaskId, mutationGenerationId, mutationToken)) {
        return;
      }
      if (error instanceof ApiFetchError && error.status === 409 && error.payload?.error === 'draft_version_conflict') {
        const currentDraft = error.payload.current_draft as ClassCommentaryFeedbackDraft | undefined;
        if (currentDraft && isClassCommentaryFeedbackRecordInScope(currentDraft, mutationTaskId, mutationGenerationId)) {
          setDraftConflict({
            localText: mutationFeedbackText,
            serverDraft: currentDraft,
          });
        } else {
          setErrorMessage('服务器草稿范围不一致');
        }
      } else {
        setErrorMessage(error instanceof Error ? error.message : '保存草稿失败');
      }
    } finally {
      if (isCurrentFeedbackMutation(mutationTaskId, mutationGenerationId, mutationToken)) {
        feedbackMutationActiveRef.current = false;
        setBusy(false);
      }
    }
  }

  async function handleConfirmFeedback(learn: boolean) {
    if (!task || !selectedGeneration) {
      return;
    }
    const mutationTaskId = task.id;
    const mutationGenerationId = selectedGeneration.id;
    const mutationFeedbackText = feedbackEditorText;
    const mutationToken = ++feedbackMutationTokenRef.current;
    feedbackMutationActiveRef.current = true;
    setBusy(true);
    setErrorMessage('');
    try {
      const { revision, draft: nextDraft } = await confirmClassCommentaryFeedback(
        mutationTaskId,
        mutationGenerationId,
        mutationFeedbackText,
        learn,
        feedbackDraft?.draft_version || 0,
        createClassCommentaryRequestId('confirmation'),
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
      setFeedbackRevisions((current) => [revision, ...current.filter((item) => item.id !== revision.id)]);
      setFeedbackEditorText(nextDraft.feedback_text);
      setFeedbackDraft(nextDraft);
      setGenerationEditors((current) => ({
        ...current,
        [mutationGenerationId]: {
          feedbackText: nextDraft.feedback_text,
          savedFeedbackText: revision.final_feedback_text,
          draft: nextDraft,
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
      if (!isCurrentFeedbackMutation(mutationTaskId, mutationGenerationId, mutationToken)) {
        return;
      }
      if (error instanceof ApiFetchError && error.status === 409 && error.payload?.error === 'draft_version_conflict') {
        const currentDraft = error.payload.current_draft as ClassCommentaryFeedbackDraft | undefined;
        if (currentDraft && isClassCommentaryFeedbackRecordInScope(currentDraft, mutationTaskId, mutationGenerationId)) {
          setDraftConflict({
            localText: mutationFeedbackText,
            serverDraft: currentDraft,
          });
        } else {
          setErrorMessage('服务器草稿范围不一致');
        }
      } else {
        setErrorMessage(error instanceof Error ? error.message : '确认终稿失败');
      }
    } finally {
      if (isCurrentFeedbackMutation(mutationTaskId, mutationGenerationId, mutationToken)) {
        feedbackMutationActiveRef.current = false;
        setBusy(false);
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
    setGenerationEditors((current) => ({
      ...current,
      [conflictGenerationId]: {
        feedbackText: draftConflict.serverDraft.feedback_text,
        savedFeedbackText: draftConflict.serverDraft.feedback_text,
        draft: draftConflict.serverDraft,
      },
    }));
    setGenerations((current) => current.map((item) => item.id === conflictGenerationId
      ? {
        ...item,
        has_draft: true,
        draft_version: draftConflict.serverDraft.draft_version,
      }
      : item));
    if (selectedGenerationIdRef.current === String(conflictGenerationId)) {
      setFeedbackEditorText(draftConflict.serverDraft.feedback_text);
      setFeedbackDraft(draftConflict.serverDraft);
    }
    setDraftConflict(null);
  }

  async function handleCopyLocalDraft() {
    if (!draftConflict) {
      return;
    }
    await navigator.clipboard.writeText(draftConflict.localText);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  function handleAudioChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0] || null;
    setAudioFile(nextFile);
    setUploadProgress(0);
    setCopied(false);
    setErrorMessage('');
  }

  function handleSelectHistoryTask(nextTask: ClassCommentaryTask) {
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
            <p className="text-sm text-muted-foreground">上传录音, 确认转写, 选择同事风格后生成可复制反馈文本.</p>
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
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertTitle>处理失败</AlertTitle>
          <AlertDescription>{taskErrorMessage}</AlertDescription>
        </Alert>
      ) : null}

      {!loadingInitial && (!classes.length || !skills.length) ? (
        <Alert>
          <AlertCircle className="size-4" />
          <AlertTitle>配置未完成</AlertTitle>
          <AlertDescription>
            {!classes.length ? '当前没有可用班级。' : '当前没有可用同事风格。'}
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <Card>
          <CardHeader>
            <CardTitle>上传与任务</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
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
                      <Select value={selectedClassId || undefined} onValueChange={setSelectedClassId}>
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
                    <p className="text-sm font-medium text-foreground">同事风格</p>
                    <Select value={selectedSkillId || undefined} onValueChange={handleSkillChange}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="请选择风格" />
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
                  <Button type="button" onClick={handleCreateTask} disabled={!canCreateTask}>
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
                    <div className="rounded-lg border border-border/70 px-3 py-2">转写 {task?.status === 'transcribing' || task?.status === 'transcribed' || task?.status === 'generating' || task?.status === 'ready' ? '进行中' : '未开始'}</div>
                    <div className="rounded-lg border border-border/70 px-3 py-2">生成 {task?.status === 'generating' || task?.status === 'ready' ? '进行中' : '未开始'}</div>
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
                    <p className="text-xs text-muted-foreground">风格</p>
                    <p className="mt-1 text-sm font-medium text-foreground">{task?.skill_name || selectedSkill?.name || '-'}</p>
                  </div>
                </div>
                <Separator />
                <div className="flex flex-col gap-2">
                  <p className="text-sm font-medium text-foreground">生成版本</p>
                  <Select value={selectedGenerationId || undefined} onValueChange={handleGenerationChange} disabled={busy || generationLoading}>
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
                    {feedbackDraft ? <Badge variant="secondary">草稿 v{feedbackDraft.draft_version}</Badge> : null}
                    {selectedRevision ? <Badge variant="secondary">已确认第 {selectedRevision.revision_no} 版</Badge> : null}
                  </div>
                  <Button type="button" variant="outline" onClick={handleCopy} disabled={generationLoading || !copyText}>
                    {copied ? <CheckCheck data-icon="inline-start" /> : <Copy data-icon="inline-start" />}
                    复制结果
                  </Button>
                </div>
                <Textarea
                  value={feedbackEditorText}
                  onChange={(event) => setFeedbackEditorText(event.target.value)}
                  placeholder="生成完成后, 这里会显示可修改并确认的反馈文本。"
                  className="min-h-64"
                  disabled={busy || generationLoading || !selectedGeneration || selectedGeneration.status !== 'succeeded'}
                />
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <Button type="button" variant="outline" onClick={handleSaveFeedbackDraft} disabled={!canSaveFeedbackDraft}>
                    保存草稿
                  </Button>
                  <Button type="button" variant="outline" onClick={() => handleConfirmFeedback(false)} disabled={!canConfirmFeedback}>
                    确认但不学习
                  </Button>
                  <Button type="button" onClick={() => handleConfirmFeedback(true)} disabled={!canConfirmFeedback || !capabilities.memory_learning_enabled}>
                    确认并学习
                  </Button>
                </div>
                {!capabilities.memory_learning_enabled ? (
                  <p className="text-xs text-muted-foreground">记忆学习功能尚未启用, 仍可正常保存草稿或确认终稿。</p>
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
                          <span>第 {revision.revision_no} 版 · {revision.learn_requested ? '已请求学习' : '未学习'}</span>
                          <span>{formatClassCommentaryTime(revision.confirmed_at)}</span>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                ) : (
                  <p className="text-xs text-muted-foreground">确认终稿后会在这里留下记录。</p>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>转写确认</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Textarea
            value={confirmedTranscript}
            onChange={(event) => setConfirmedTranscript(event.target.value)}
            placeholder="可直接输入课堂记录, 也可以上传并转写后在这里确认或修订文本。"
            className="min-h-56"
            disabled={loadingInitial}
          />
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              可直接输入文本生成反馈包; 已有录音任务时也可以先保存确认文本。
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" onClick={handleSaveTranscript} disabled={!canSaveTranscript}>
                保存转写
              </Button>
              <Button type="button" onClick={handleGenerate} disabled={!canGenerate}>
                生成反馈包
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Dialog open={Boolean(draftConflict)} onOpenChange={handleDraftConflictOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>草稿版本冲突</DialogTitle>
            <DialogDescription>
              服务器上已有更新的草稿。你可以加载服务器版本, 或先复制当前页面中的本地内容。
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
    </div>
  );
}
