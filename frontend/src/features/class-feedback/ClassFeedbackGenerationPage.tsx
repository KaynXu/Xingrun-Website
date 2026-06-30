import { useEffect, useState, type ChangeEvent } from 'react';
import { AlertCircle, CheckCheck, Copy, FileAudio, Sparkles, Upload } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
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
  fetchClassCommentarySkills,
  fetchClassCommentaryTasks,
  fetchClassCommentaryTask,
  generateClassCommentaryFeedback,
  saveClassCommentaryTranscript,
  shouldPollClassCommentaryTask,
  type ClassCommentarySkill,
  type ClassCommentaryTask,
} from '../../classCommentary';
import { apiFetch } from '../../workspaceShared';

type ClassFeedbackGenerationPageProps = {
  currentUser: CurrentUser;
};

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

export function ClassFeedbackGenerationPage({ currentUser: _currentUser }: ClassFeedbackGenerationPageProps) {
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [skills, setSkills] = useState<ClassCommentarySkill[]>([]);
  const [historyTasks, setHistoryTasks] = useState<ClassCommentaryTask[]>([]);
  const [selectedClassId, setSelectedClassId] = useState('');
  const [selectedSkillId, setSelectedSkillId] = useState('');
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [task, setTask] = useState<ClassCommentaryTask | null>(null);
  const [confirmedTranscript, setConfirmedTranscript] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoadingInitial(true);
    Promise.all([
      apiFetch<ClassItem[]>('/api/classes'),
      fetchClassCommentarySkills(),
      fetchClassCommentaryTasks(),
    ])
      .then(([nextClasses, nextSkills, nextHistoryTasks]) => {
        if (cancelled) {
          return;
        }
        setClasses(nextClasses);
        setSkills(nextSkills);
        setHistoryTasks(nextHistoryTasks);
        setSelectedClassId((currentValue) => currentValue || (nextClasses[0] ? String(nextClasses[0].id) : ''));
        setSelectedSkillId((currentValue) => currentValue || (nextSkills[0]?.id || ''));
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
  }, []);

  useEffect(() => {
    if (!task || !shouldPollClassCommentaryTask(task.status)) {
      return;
    }
    const timer = window.setInterval(() => {
      fetchClassCommentaryTask(task.id)
        .then((nextTask) => {
          setTask(nextTask);
          setHistoryTasks((current) => mergeHistoryTask(current, nextTask));
          setConfirmedTranscript(nextTask.confirmed_transcript_text || nextTask.transcript_text || '');
        })
        .catch((error) => {
          setErrorMessage(error instanceof Error ? error.message : '刷新任务状态失败');
        });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [task?.id, task?.status]);

  const selectedClass = classes.find((item) => String(item.id) === selectedClassId) || null;
  const selectedSkill = skills.find((item) => item.id === selectedSkillId) || null;
  const taskErrorMessage = getTaskErrorMessage(task, errorMessage);
  const taskProgress = getTaskProgress(task, uploadProgress);
  const trimmedConfirmedTranscript = confirmedTranscript.trim();
  const persistedTranscript = (task?.confirmed_transcript_text || task?.transcript_text || '').trim();
  const hasTranscriptText = Boolean(trimmedConfirmedTranscript);
  const transcriptDirty = Boolean(task) && trimmedConfirmedTranscript !== persistedTranscript;
  const canUseTranscript = canUseTranscriptState(task);
  const canCreateTask = !loadingInitial && !busy && Boolean(selectedClassId && audioFile);
  const canSaveTranscript = !busy && canUseTranscript && hasTranscriptText;
  const canGenerate = !busy && canUseTranscript && hasTranscriptText && Boolean(task && selectedSkillId);

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
    if (!task || !selectedSkillId) {
      setErrorMessage('请选择同事风格后再生成');
      return;
    }
    if (!trimmedConfirmedTranscript) {
      setErrorMessage('请先确认转写文本');
      return;
    }
    setBusy(true);
    setErrorMessage('');
    try {
      const savedTask = transcriptDirty
        ? await saveClassCommentaryTranscript(task.id, trimmedConfirmedTranscript)
        : task;
      setTask(savedTask);
      setHistoryTasks((current) => mergeHistoryTask(current, savedTask));
      setConfirmedTranscript(savedTask.confirmed_transcript_text || savedTask.transcript_text || '');
      const nextTask = await generateClassCommentaryFeedback(savedTask.id, selectedSkillId);
      setTask(nextTask);
      setHistoryTasks((current) => mergeHistoryTask(current, nextTask));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '生成失败');
    } finally {
      setBusy(false);
    }
  }

  async function handleCopy() {
    if (!task?.feedback_text) {
      return;
    }
    await navigator.clipboard.writeText(task.feedback_text);
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
    setTask(nextTask);
    setSelectedClassId(String(nextTask.class_id));
    setSelectedSkillId(nextTask.skill_id || selectedSkillId);
    setConfirmedTranscript(nextTask.confirmed_transcript_text || nextTask.transcript_text || '');
    setErrorMessage('');
    setCopied(false);
  }

  return (
    <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 px-4 py-6 sm:px-6 lg:px-8">
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
                    <Select value={selectedClassId || undefined} onValueChange={setSelectedClassId}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="请选择班级" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          {classes.map((item) => (
                            <SelectItem key={item.id} value={String(item.id)}>
                              {item.name}
                            </SelectItem>
                          ))}
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex flex-col gap-2">
                    <p className="text-sm font-medium text-foreground">同事风格</p>
                    <Select value={selectedSkillId || undefined} onValueChange={setSelectedSkillId}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="请选择风格" />
                      </SelectTrigger>
                      <SelectContent>
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
                    <Upload className="size-4" />
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
                <div className="flex items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={task?.status === 'failed' ? 'destructive' : 'outline'}>
                      {task ? classCommentaryStatusLabel(task.status) : '未创建任务'}
                    </Badge>
                    {task?.feedback_text ? <Badge variant="secondary">可复制</Badge> : null}
                  </div>
                  <Button type="button" variant="outline" onClick={handleCopy} disabled={!task?.feedback_text}>
                    {copied ? <CheckCheck className="size-4" /> : <Copy className="size-4" />}
                    复制结果
                  </Button>
                </div>
                <ScrollArea className="h-64 rounded-lg border border-border/70">
                  <pre className="min-h-full whitespace-pre-wrap px-3 py-3 text-sm leading-6 text-foreground">
                    {task?.feedback_text || '生成完成后, 这里会显示可直接复制发送的反馈文本。'}
                  </pre>
                </ScrollArea>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>生成历史</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingInitial ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : historyTasks.length ? (
            <ScrollArea className="h-72 rounded-lg border border-border/70">
              <div className="flex flex-col">
                {historyTasks.map((historyTask, index) => (
                  <div key={historyTask.id}>
                    <button
                      type="button"
                      className="flex w-full flex-col gap-2 px-3 py-3 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      onClick={() => handleSelectHistoryTask(historyTask)}
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
                    </button>
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
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>转写确认</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Textarea
            value={confirmedTranscript}
            onChange={(event) => setConfirmedTranscript(event.target.value)}
            placeholder="上传并转写后, 请在这里确认或修订文本。"
            className="min-h-56"
            disabled={loadingInitial || (!task && !confirmedTranscript)}
          />
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              保存确认文本后, 再按所选同事风格生成反馈包。
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
    </div>
  );
}
