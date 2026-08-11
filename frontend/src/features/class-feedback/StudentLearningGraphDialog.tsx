import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, BookMarked, BookOpen, ChevronRight, RefreshCw, TrendingUp } from 'lucide-react';

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import {
  fetchClassCommentaryStudentLearningGraph,
  isClassCommentaryMutationOutcomeAmbiguous,
  isClassCommentaryStudentLearningGraphSummaryInScope,
  retryClassCommentaryRevisionLearningGraph,
  type ClassCommentaryGraphLearningStatus,
  type ClassCommentaryLearningTrend,
  type ClassCommentaryObservedLearningState,
  type ClassCommentaryStudentGraphEvidence,
  type ClassCommentaryStudentGraphCurriculumContext,
  type ClassCommentaryStudentLearningGraphSummary,
} from '../../classCommentary';

export type StudentLearningGraphStudent = {
  id: number;
  name: string;
};

type StudentLearningGraphDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  taskId: number;
  generationId: number;
  revisionId: number;
  subjectKey: string;
  student: StudentLearningGraphStudent | null;
  graphHealthy: boolean;
  graphDegraded: boolean;
  usedGraphEvidenceRefs: string[];
};

type LoadState = 'idle' | 'loading' | 'ready' | 'unavailable';

type PendingRetryRequest = {
  scopeKey: string;
  requestId: string;
};

const learningStateLabels: Record<ClassCommentaryObservedLearningState, string> = {
  unknown: '持续观察',
  weak: '需要巩固',
  developing: '正在发展',
  secure: '已经掌握',
  mastered: '熟练掌握',
};

const trendLabels: Record<ClassCommentaryLearningTrend, string> = {
  new_observation: '新观察',
  regressed: '需要关注',
  stable: '保持稳定',
  improved: '有所进步',
};

const syncStatusLabels: Record<ClassCommentaryGraphLearningStatus, string> = {
  pending: '学习中',
  learned: '已学习',
  needs_mapping: '待匹配知识点',
  failed: '学习失败',
};

function formatLearningGraphTime(value: string): string {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function createGraphRetryRequestId(): string {
  const randomId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `graph-retry-${randomId}`;
}

function syncStatusVariant(status: ClassCommentaryGraphLearningStatus): 'destructive' | 'outline' | 'secondary' {
  if (status === 'failed') {
    return 'destructive';
  }
  return status === 'learned' ? 'secondary' : 'outline';
}

function learningStateVariant(state: ClassCommentaryObservedLearningState): 'outline' | 'secondary' {
  return state === 'secure' || state === 'mastered' ? 'secondary' : 'outline';
}

function CurriculumContextBlock({
  curriculum,
  compact = false,
}: {
  curriculum: ClassCommentaryStudentGraphCurriculumContext;
  compact?: boolean;
}) {
  const path = curriculum.path.map((item) => item.name).filter(Boolean);
  const sourceVersion = curriculum.source.version_key || curriculum.source.dataset_revision;
  return (
    <div className="mt-2 min-w-0 space-y-2 rounded-lg bg-muted/45 px-3 py-2.5" data-testid="student-learning-curriculum-context">
      {path.length ? (
        <div className="flex min-w-0 flex-wrap items-center gap-1 text-xs text-muted-foreground">
          {path.map((name, index) => (
            <span key={`${name}-${index}`} className="contents">
              {index > 0 ? <ChevronRight className="size-3 shrink-0" /> : null}
              <span className="max-w-full break-words">{name}</span>
            </span>
          ))}
        </div>
      ) : null}
      {!compact && curriculum.prerequisites.length ? (
        <p className="break-words text-xs text-muted-foreground">
          前置知识: {curriculum.prerequisites.map((item) => item.canonical_name).join('、')}
        </p>
      ) : null}
      {!compact && curriculum.follow_ups.length ? (
        <p className="break-words text-xs text-muted-foreground">
          后续知识: {curriculum.follow_ups.map((item) => item.canonical_name).join('、')}
        </p>
      ) : null}
      {sourceVersion ? (
        <p className="break-all text-[11px] text-muted-foreground">
          课程版本: {sourceVersion}{curriculum.source.license ? ` · ${curriculum.source.license}` : ''}
        </p>
      ) : null}
    </div>
  );
}

export function StudentLearningGraphDialog({
  open,
  onOpenChange,
  taskId,
  generationId,
  revisionId,
  subjectKey,
  student,
  graphHealthy,
  graphDegraded,
  usedGraphEvidenceRefs,
}: StudentLearningGraphDialogProps) {
  const [loadState, setLoadState] = useState<LoadState>('idle');
  const [summary, setSummary] = useState<ClassCommentaryStudentLearningGraphSummary | null>(null);
  const [loadError, setLoadError] = useState('');
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [retrying, setRetrying] = useState(false);
  const loadRequestTokenRef = useRef(0);
  const retryRequestTokenRef = useRef(0);
  const retryRequestRef = useRef<PendingRetryRequest | null>(null);
  const studentId = student?.id || 0;
  const scopeKey = `${taskId}:${generationId}:${studentId}:${subjectKey}`;
  const currentScopeKeyRef = useRef(scopeKey);
  currentScopeKeyRef.current = scopeKey;

  useEffect(() => {
    const requestToken = ++loadRequestTokenRef.current;
    ++retryRequestTokenRef.current;
    let cancelled = false;
    let pollTimer: number | undefined;
    let pollingDelayMs = 2000;

    setRetrying(false);
    if (!open || studentId <= 0 || taskId <= 0 || generationId <= 0) {
      setLoadState('idle');
      setSummary(null);
      setLoadError('');
      return () => {
        cancelled = true;
      };
    }
    if (!subjectKey.trim()) {
      setLoadState('unavailable');
      setSummary(null);
      setLoadError('课程科目范围缺失, 无法安全加载学生成长轨迹');
      return () => {
        cancelled = true;
      };
    }

    setLoadState('loading');
    setSummary(null);
    setLoadError('');

    const loadSummary = async () => {
      try {
        const nextSummary = await fetchClassCommentaryStudentLearningGraph(
          taskId,
          studentId,
          generationId,
        );
        if (
          cancelled
          || requestToken !== loadRequestTokenRef.current
          || currentScopeKeyRef.current !== scopeKey
        ) {
          return;
        }
        if (!isClassCommentaryStudentLearningGraphSummaryInScope(
          nextSummary,
          taskId,
          studentId,
          subjectKey,
        )) {
          throw new Error('学习轨迹响应范围不一致');
        }
        setSummary(nextSummary);
        setLoadState('ready');
        setLoadError('');
        pollingDelayMs = 2000;
        if (nextSummary.sync_status === 'pending') {
          pollTimer = window.setTimeout(loadSummary, pollingDelayMs);
        }
      } catch (error) {
        if (
          !cancelled
          && requestToken === loadRequestTokenRef.current
          && currentScopeKeyRef.current === scopeKey
        ) {
          setLoadState('unavailable');
          setLoadError(error instanceof Error ? error.message : '学生成长轨迹暂时不可用');
        }
      }
    };

    void loadSummary();
    return () => {
      cancelled = true;
      if (pollTimer !== undefined) {
        window.clearTimeout(pollTimer);
      }
    };
  }, [generationId, open, refreshVersion, scopeKey, studentId, subjectKey, taskId]);

  const usedEvidence = useMemo(() => {
    if (!summary) {
      return [];
    }
    const evidenceByRef = new Map<string, ClassCommentaryStudentGraphEvidence>();
    for (const event of summary.timeline) {
      evidenceByRef.set(event.evidence.evidence_ref, event.evidence);
    }
    for (const evidence of summary.used_graph_evidence) {
      evidenceByRef.set(evidence.evidence_ref, evidence);
    }
    const allowedRefs = usedGraphEvidenceRefs.length
      ? usedGraphEvidenceRefs
      : summary.used_graph_evidence_refs;
    const seenRefs = new Set<string>();
    return allowedRefs.flatMap((evidenceRef) => {
      if (seenRefs.has(evidenceRef)) {
        return [];
      }
      seenRefs.add(evidenceRef);
      const evidence = evidenceByRef.get(evidenceRef);
      return evidence ? [evidence] : [];
    });
  }, [summary, usedGraphEvidenceRefs]);

  function handleReload() {
    setRefreshVersion((current) => current + 1);
  }

  async function handleRetryLearning() {
    if (!summary?.can_retry || revisionId <= 0 || retrying || studentId <= 0) {
      return;
    }
    const retryToken = ++retryRequestTokenRef.current;
    const retryScopeKey = `${scopeKey}:${revisionId}`;
    const retryRequest = retryRequestRef.current?.scopeKey === retryScopeKey
      ? retryRequestRef.current
      : { scopeKey: retryScopeKey, requestId: createGraphRetryRequestId() };
    retryRequestRef.current = retryRequest;
    setRetrying(true);
    setLoadError('');
    try {
      await retryClassCommentaryRevisionLearningGraph(
        revisionId,
        retryRequest.requestId,
      );
      const nextSummary = await fetchClassCommentaryStudentLearningGraph(
        taskId,
        studentId,
        generationId,
      );
      if (
        retryToken !== retryRequestTokenRef.current
        || currentScopeKeyRef.current !== scopeKey
      ) {
        return;
      }
      if (!isClassCommentaryStudentLearningGraphSummaryInScope(
          nextSummary,
          taskId,
          studentId,
          subjectKey,
        )) {
        throw new Error('学习轨迹响应范围不一致');
      }
      retryRequestRef.current = null;
      setSummary(nextSummary);
      setLoadState('ready');
      if (nextSummary.sync_status === 'pending') {
        setRefreshVersion((current) => current + 1);
      }
    } catch (error) {
      if (
        retryToken !== retryRequestTokenRef.current
        || currentScopeKeyRef.current !== scopeKey
      ) {
        return;
      }
      if (!isClassCommentaryMutationOutcomeAmbiguous(error)) {
        retryRequestRef.current = null;
      }
      setLoadError(error instanceof Error ? error.message : '重试学习失败');
    } finally {
      if (
        retryToken === retryRequestTokenRef.current
        && currentScopeKeyRef.current === scopeKey
      ) {
        setRetrying(false);
      }
    }
  }

  const hasLearningHistory = Boolean(summary?.current_states.length || summary?.timeline.length);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] sm:max-w-3xl" data-testid="student-learning-graph-dialog">
        <DialogHeader>
          <DialogTitle>{student ? `${student.name}的学生成长轨迹` : '学生成长轨迹'}</DialogTitle>
          <DialogDescription>
            查看已确认课堂反馈中有证据支持的知识点状态, 变化和下一步.
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="h-[min(70vh,680px)] overflow-hidden">
          <div className="flex flex-col gap-4 pr-3 pb-2">
            {loadState === 'loading' ? (
              <div className="flex flex-col gap-3" data-testid="student-learning-graph-loading">
                <Skeleton className="h-6 w-28" />
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-40 w-full" />
              </div>
            ) : null}

            {loadState === 'unavailable' ? (
              <Alert variant="destructive" data-testid="student-learning-graph-unavailable">
                <AlertCircle className="size-4" />
                <AlertTitle>成长轨迹暂时不可用</AlertTitle>
                <AlertDescription className="flex flex-col items-start gap-3">
                  <span>{loadError || '请稍后重新加载.'}</span>
                  <Button type="button" size="sm" variant="outline" onClick={handleReload}>
                    <RefreshCw data-icon="inline-start" />
                    重新加载
                  </Button>
                </AlertDescription>
              </Alert>
            ) : null}

            {loadState === 'ready' && summary ? (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="size-4 text-muted-foreground" />
                    <span className="text-sm font-medium text-foreground">学习同步状态</span>
                  </div>
                  <Badge variant={syncStatusVariant(summary.sync_status)}>
                    {syncStatusLabels[summary.sync_status]}
                  </Badge>
                </div>

                {graphDegraded || !graphHealthy ? (
                  <Alert data-testid="student-learning-graph-degraded">
                    <AlertCircle className="size-4" />
                    <AlertTitle>成长轨迹服务当前降级</AlertTitle>
                    <AlertDescription>
                      已显示服务器确认的安全范围数据. 新变化可能需要稍后同步.
                    </AlertDescription>
                  </Alert>
                ) : null}

                {summary.curriculum_assignment ? (
                  <div className="min-w-0 rounded-lg border border-border/70 bg-muted/30 px-3 py-3" data-testid="student-learning-curriculum-assignment">
                    <div className="flex min-w-0 items-start gap-2">
                      <BookMarked className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                      <div className="min-w-0">
                        <p className="break-words text-sm font-medium text-foreground">
                          {summary.curriculum_assignment.book_name}
                        </p>
                        <p className="mt-1 break-words text-xs text-muted-foreground">
                          {[
                            summary.curriculum_assignment.curriculum_name,
                            summary.curriculum_assignment.publisher_name,
                            summary.curriculum_assignment.edition_name,
                          ].filter(Boolean).join(' · ')}
                        </p>
                        <p className="mt-1 break-all text-[11px] text-muted-foreground">
                          课程版本: {summary.curriculum_assignment.version_key || summary.curriculum_assignment.source_dataset_revision}
                          {summary.curriculum_assignment.data_license ? ` · ${summary.curriculum_assignment.data_license}` : ''}
                        </p>
                      </div>
                    </div>
                  </div>
                ) : null}

                {summary.error ? (
                  <p className="text-xs text-muted-foreground">
                    同步服务记录了错误, 已确认反馈不会丢失. 请稍后重试.
                  </p>
                ) : null}

                {summary.sync_status === 'needs_mapping' ? (
                  <Alert data-testid="student-learning-graph-needs-mapping">
                    <BookOpen className="size-4" />
                    <AlertTitle>有内容等待匹配知识点</AlertTitle>
                    <AlertDescription>
                      这部分内容尚未进入可信成长轨迹, 已有学习记录不会受影响.
                    </AlertDescription>
                  </Alert>
                ) : null}

                {summary.sync_status === 'failed' ? (
                  <Alert variant="destructive" data-testid="student-learning-graph-failed">
                    <AlertCircle className="size-4" />
                    <AlertTitle>本次学习同步失败</AlertTitle>
                    <AlertDescription className="flex flex-col items-start gap-3">
                      <span>已确认的课堂反馈仍然安全保存, 可以稍后重试.</span>
                      {summary.can_retry && revisionId > 0 ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={retrying}
                          onClick={() => void handleRetryLearning()}
                        >
                          <RefreshCw data-icon="inline-start" />
                          {retrying ? '重试中' : '重试学习'}
                        </Button>
                      ) : null}
                    </AlertDescription>
                  </Alert>
                ) : null}

                {!hasLearningHistory ? (
                  <div
                    className="rounded-lg border border-dashed border-border/70 px-4 py-8 text-center"
                    data-testid="student-learning-graph-empty"
                  >
                    <p className="text-sm font-medium text-foreground">还没有可展示的学习记录</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      确认并学习包含可信知识点证据的课堂反馈后, 这里会显示成长变化.
                    </p>
                  </div>
                ) : (
                  <>
                    <section className="flex flex-col gap-3" aria-labelledby="student-learning-current-state-title">
                      <h3 id="student-learning-current-state-title" className="text-sm font-medium text-foreground">
                        当前知识点状态
                      </h3>
                      <div className="grid gap-2 sm:grid-cols-2">
                        {summary.current_states.map((state) => (
                          <div key={state.knowledge_point_key} className="rounded-lg border border-border/70 px-3 py-2.5">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="text-sm font-medium text-foreground">{state.knowledge_point_name}</span>
                              <Badge variant={learningStateVariant(state.state)}>
                                {learningStateLabels[state.state]}
                              </Badge>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">
                              最近确认于 {formatLearningGraphTime(state.observed_at)}
                            </p>
                            {state.curriculum ? <CurriculumContextBlock curriculum={state.curriculum} compact /> : null}
                          </div>
                        ))}
                      </div>
                    </section>

                    <Separator />

                    <section className="flex flex-col gap-3" aria-labelledby="student-learning-timeline-title">
                      <h3 id="student-learning-timeline-title" className="text-sm font-medium text-foreground">
                        状态变化
                      </h3>
                      <ol className="flex flex-col gap-3">
                        {summary.timeline.map((event) => (
                          <li key={event.event_ref} className="rounded-lg border border-border/70 px-3 py-3">
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <div className="flex flex-col gap-1">
                                <span className="text-sm font-medium text-foreground">{event.knowledge_point_name}</span>
                                <span className="text-xs text-muted-foreground">
                                  {formatLearningGraphTime(event.observed_at)}
                                </span>
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                <Badge variant="outline">{trendLabels[event.trend]}</Badge>
                                <Badge variant={learningStateVariant(event.state)}>
                                  {event.previous_state
                                    ? `${learningStateLabels[event.previous_state]} -> ${learningStateLabels[event.state]}`
                                    : learningStateLabels[event.state]}
                                </Badge>
                              </div>
                            </div>

                            {event.trend === 'improved' && !event.previous_state ? (
                              <p className="mt-2 text-xs text-muted-foreground">
                                本次反馈报告有进步, 但没有可信旧状态可用于比较.
                              </p>
                            ) : null}

                            {event.curriculum ? <CurriculumContextBlock curriculum={event.curriculum} /> : null}

                            {event.teaching_methods.length ? (
                              <div className="mt-3 flex flex-col gap-1.5">
                                <span className="text-xs font-medium text-foreground">本次使用的教学方法</span>
                                <div className="flex flex-wrap gap-2">
                                  {event.teaching_methods.map((method) => (
                                    <Badge key={method} variant="outline">{method}</Badge>
                                  ))}
                                </div>
                              </div>
                            ) : null}

                            {event.next_steps.length ? (
                              <div className="mt-3 flex flex-col gap-1.5">
                                <span className="text-xs font-medium text-foreground">下一步建议</span>
                                <ul className="list-disc space-y-1 pl-5 text-sm text-foreground">
                                  {event.next_steps.map((nextStep) => <li key={nextStep}>{nextStep}</li>)}
                                </ul>
                              </div>
                            ) : null}

                            <Accordion type="single" collapsible className="mt-3 rounded-lg border border-border/70 px-3">
                              <AccordionItem value="evidence">
                                <AccordionTrigger>
                                  查看第 {event.evidence.revision_no} 次已确认反馈证据
                                </AccordionTrigger>
                                <AccordionContent className="flex flex-col gap-2">
                                  <p className="text-xs text-muted-foreground">
                                    {event.evidence.lesson_name} · {formatLearningGraphTime(event.evidence.confirmed_at)}
                                  </p>
                                  <blockquote className="border-l-2 border-border pl-3 text-sm text-foreground">
                                    {event.evidence.quote}
                                  </blockquote>
                                </AccordionContent>
                              </AccordionItem>
                            </Accordion>
                          </li>
                        ))}
                      </ol>
                    </section>
                  </>
                )}

                <Separator />

                <section className="flex flex-col gap-3" aria-labelledby="student-learning-used-evidence-title">
                  <h3 id="student-learning-used-evidence-title" className="text-sm font-medium text-foreground">
                    本次生成参考了
                  </h3>
                  {usedEvidence.length ? (
                    <div className="flex flex-col gap-2">
                      {usedEvidence.map((evidence) => (
                        <div key={evidence.evidence_ref} className="rounded-lg border border-border/70 px-3 py-2.5">
                          <p className="text-sm font-medium text-foreground">
                            {evidence.lesson_name} · 第 {evidence.revision_no} 次已确认反馈
                          </p>
                          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{evidence.quote}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      本次生成没有引用可展示的历史证据.
                    </p>
                  )}
                </section>
              </>
            ) : null}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
