import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  ChevronRight,
  GitBranch,
  Link2,
  RefreshCw,
  Search,
} from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import type { ClassItem, CurrentUser } from '../../appTypes';
import {
  fetchCurriculumBooks,
  fetchCurriculumCatalog,
  fetchCurriculumClassAssignment,
  fetchCurriculumNodeDetail,
  fetchCurriculumKnowledgePointProposals,
  fetchCurriculumUnmappedCandidates,
  fetchCurriculumVersions,
  submitCurriculumMappingAction,
  reviewCurriculumKnowledgePointProposal,
  transitionCurriculumVersion,
  updateCurriculumClassAssignment,
  type CurriculumBook,
  type CurriculumCatalogResult,
  type CurriculumClassAssignment,
  type CurriculumMappingAction,
  type CurriculumKnowledgePointProposal,
  type CurriculumNode,
  type CurriculumNodeDetail,
  type CurriculumNodeType,
  type CurriculumUnmappedCandidate,
  type CurriculumUnmappedResult,
  type CurriculumVersion,
  type CurriculumVersionStatus,
} from '../../curriculumRegistry';
import {
  apiFetch,
  cn,
  workspaceCardClass,
  workspaceFieldClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSectionTextClass,
  workspaceSectionTitleClass,
} from '../../workspaceShared';

type CurriculumTab = 'catalog' | 'unmapped';
type LoadState = 'loading' | 'ready' | 'empty' | 'error';

const versionStatusLabels: Record<CurriculumVersionStatus, string> = {
  draft: '草稿',
  reviewed: '已审核',
  active: '使用中',
  deprecated: '已停用',
};

const nodeTypeLabels: Record<CurriculumNodeType, string> = {
  Book: '教材',
  Chapter: '章节',
  Section: '小节',
  Concept: '概念',
  Skill: '技能',
};

const stageLabels: Record<string, string> = {
  primary: '小学',
  junior: '初中',
  senior: '高中',
};

const gradeLabels: Record<string, string> = {
  '1': '一年级',
  '2': '二年级',
  '3': '三年级',
  '4': '四年级',
  '5': '五年级',
  '6': '六年级',
  '7': '七年级',
  '8': '八年级',
  '9': '九年级',
  '10': '高一',
  '11': '高二',
  '12': '高三',
};

const mappingActionLabels: Record<CurriculumMappingAction, string> = {
  map: '匹配到知识点',
  add_alias: '匹配并保存别名',
  propose_new: '提议新知识点',
  reject: '忽略这条内容',
};

function formatTime(value: string): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function createRequestId(prefix: string): string {
  const randomId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${randomId}`;
}

function versionStatusVariant(status: CurriculumVersionStatus): 'outline' | 'secondary' {
  return status === 'active' ? 'secondary' : 'outline';
}

function pageCount(result: Pick<CurriculumCatalogResult | CurriculumUnmappedResult, 'total' | 'page_size'>): number {
  return Math.max(1, Math.ceil(result.total / Math.max(1, result.page_size)));
}

function ErrorState({ message, onRetry, testId }: { message: string; onRetry: () => void; testId: string }) {
  return (
    <Alert variant="destructive" data-testid={testId}>
      <AlertCircle className="size-4" />
      <AlertTitle>内容暂时无法加载</AlertTitle>
      <AlertDescription className="flex flex-col items-start gap-3">
        <span>{message || '请稍后再试.'}</span>
        <Button type="button" size="sm" variant="outline" onClick={onRetry}>
          <RefreshCw data-icon="inline-start" />
          重新加载
        </Button>
      </AlertDescription>
    </Alert>
  );
}

function EmptyState({ title, description, testId }: { title: string; description: string; testId: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-sky-200 px-4 py-12 text-center dark:border-white/10" data-testid={testId}>
      <BookOpenCheck className="mx-auto size-7 text-sky-500" />
      <p className="mt-3 text-sm font-semibold text-slate-900 dark:text-white">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-xs leading-5 text-slate-500 dark:text-slate-400">{description}</p>
    </div>
  );
}

export function CurriculumKnowledgePage({ currentUser }: { currentUser: CurrentUser }) {
  const [activeTab, setActiveTab] = useState<CurriculumTab>('catalog');
  const [versions, setVersions] = useState<CurriculumVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState(0);
  const [books, setBooks] = useState<CurriculumBook[]>([]);
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [initialState, setInitialState] = useState<LoadState>('loading');
  const [initialError, setInitialError] = useState('');
  const [initialReload, setInitialReload] = useState(0);
  const initialRequestRef = useRef(0);

  const [queryInput, setQueryInput] = useState('');
  const [appliedQuery, setAppliedQuery] = useState('');
  const [stageKey, setStageKey] = useState('');
  const [gradeKey, setGradeKey] = useState('');
  const [bookUpstreamId, setBookUpstreamId] = useState('');
  const [nodeType, setNodeType] = useState<CurriculumNodeType | ''>('');
  const [catalogPage, setCatalogPage] = useState(1);
  const [catalog, setCatalog] = useState<CurriculumCatalogResult>({ items: [], page: 1, page_size: 30, total: 0 });
  const [catalogState, setCatalogState] = useState<LoadState>('loading');
  const [catalogError, setCatalogError] = useState('');
  const [catalogReload, setCatalogReload] = useState(0);
  const catalogRequestRef = useRef(0);

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailState, setDetailState] = useState<LoadState>('loading');
  const [detail, setDetail] = useState<CurriculumNodeDetail | null>(null);
  const [detailTarget, setDetailTarget] = useState<{ nodeId: number; bookNodeId?: number } | null>(null);
  const [detailError, setDetailError] = useState('');
  const detailRequestRef = useRef(0);

  const [selectedClassId, setSelectedClassId] = useState(0);
  const [assignment, setAssignment] = useState<CurriculumClassAssignment | null>(null);
  const [assignmentBookId, setAssignmentBookId] = useState(0);
  const [assignmentState, setAssignmentState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [assignmentError, setAssignmentError] = useState('');
  const [assignmentSaving, setAssignmentSaving] = useState(false);
  const [assignmentSuccess, setAssignmentSuccess] = useState('');
  const assignmentRequestRef = useRef(0);

  const [unmappedStatus, setUnmappedStatus] = useState('pending');
  const [unmappedPage, setUnmappedPage] = useState(1);
  const [unmapped, setUnmapped] = useState<CurriculumUnmappedResult>({ items: [], page: 1, page_size: 30, total: 0 });
  const [unmappedState, setUnmappedState] = useState<LoadState>('loading');
  const [unmappedError, setUnmappedError] = useState('');
  const [unmappedReload, setUnmappedReload] = useState(0);
  const unmappedRequestRef = useRef(0);

  const [mappingCandidate, setMappingCandidate] = useState<CurriculumUnmappedCandidate | null>(null);
  const [mappingAction, setMappingAction] = useState<CurriculumMappingAction>('map');
  const [mappingTargetKey, setMappingTargetKey] = useState('');
  const [mappingProposedName, setMappingProposedName] = useState('');
  const [mappingNote, setMappingNote] = useState('');
  const [mappingSearchInput, setMappingSearchInput] = useState('');
  const [mappingSearchResults, setMappingSearchResults] = useState<CurriculumNode[]>([]);
  const [mappingSearching, setMappingSearching] = useState(false);
  const [mappingSubmitting, setMappingSubmitting] = useState(false);
  const [mappingError, setMappingError] = useState('');
  const [mappingSuccess, setMappingSuccess] = useState('');

  const [proposals, setProposals] = useState<CurriculumKnowledgePointProposal[]>([]);
  const [proposalsLoading, setProposalsLoading] = useState(false);
  const [proposalBusyId, setProposalBusyId] = useState(0);
  const [proposalError, setProposalError] = useState('');
  const [proposalSuccess, setProposalSuccess] = useState('');

  const [lifecycleBusy, setLifecycleBusy] = useState(false);
  const [lifecycleError, setLifecycleError] = useState('');
  const [lifecycleSuccess, setLifecycleSuccess] = useState('');

  const selectedVersion = useMemo(
    () => versions.find((version) => version.id === selectedVersionId) || null,
    [selectedVersionId, versions],
  );
  const mathClasses = useMemo(() => classes.filter((item) => (
    item.subject_key === 'math' || item.subject === 'math' || item.subject === '数学'
  )), [classes]);
  const isSuperOwner = currentUser.role === 'super_owner';
  const canManageCurriculum = currentUser.role !== 'member';
  const canReviewProposals = canManageCurriculum;
  const availableMappingActions: CurriculumMappingAction[] = canManageCurriculum
    ? ['map', 'add_alias', 'propose_new', 'reject']
    : ['propose_new'];

  const loadInitial = useCallback(async () => {
    const requestToken = ++initialRequestRef.current;
    setInitialState('loading');
    setInitialError('');
    try {
      const [nextVersions, nextClasses] = await Promise.all([
        fetchCurriculumVersions(),
        apiFetch<ClassItem[]>('/api/classes'),
      ]);
      if (requestToken !== initialRequestRef.current) return;
      setVersions(nextVersions);
      setClasses(nextClasses);
      setSelectedVersionId((current) => {
        if (nextVersions.some((version) => version.id === current)) return current;
        return nextVersions.find((version) => version.status === 'active')?.id || nextVersions[0]?.id || 0;
      });
      const nextMathClasses = nextClasses.filter((item) => (
        item.subject_key === 'math' || item.subject === 'math' || item.subject === '数学'
      ));
      setSelectedClassId((current) => {
        if (nextMathClasses.some((item) => item.id === current)) return current;
        return nextMathClasses[0]?.id || 0;
      });
      setInitialState(nextVersions.length ? 'ready' : 'empty');
    } catch (error) {
      if (requestToken !== initialRequestRef.current) return;
      setInitialState('error');
      setInitialError(error instanceof Error ? error.message : '课程知识点加载失败');
    }
  }, []);

  useEffect(() => {
    void loadInitial();
  }, [initialReload, loadInitial]);

  useEffect(() => {
    let cancelled = false;
    setBooks([]);
    setBookUpstreamId('');
    if (selectedVersionId <= 0) return undefined;
    void fetchCurriculumBooks(selectedVersionId)
      .then((nextBooks) => {
        if (!cancelled) setBooks(nextBooks);
      })
      .catch(() => {
        if (!cancelled) setBooks([]);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedVersionId]);

  useEffect(() => {
    if (initialState !== 'ready' || selectedVersionId <= 0 || activeTab !== 'catalog') return;
    const requestToken = ++catalogRequestRef.current;
    setCatalogState('loading');
    setCatalogError('');
    void fetchCurriculumCatalog({
      version_id: selectedVersionId,
      stage_key: stageKey,
      grade_key: gradeKey,
      book_upstream_id: bookUpstreamId,
      query: appliedQuery,
      node_type: nodeType,
      page: catalogPage,
      page_size: 30,
    })
      .then((result) => {
        if (requestToken !== catalogRequestRef.current) return;
        setCatalog(result);
        setCatalogState(result.items.length ? 'ready' : 'empty');
      })
      .catch((error) => {
        if (requestToken !== catalogRequestRef.current) return;
        setCatalogState('error');
        setCatalogError(error instanceof Error ? error.message : '课程目录加载失败');
      });
  }, [activeTab, appliedQuery, bookUpstreamId, catalogPage, catalogReload, gradeKey, initialState, nodeType, selectedVersionId, stageKey]);

  useEffect(() => {
    const requestToken = ++assignmentRequestRef.current;
    setAssignment(null);
    setAssignmentBookId(0);
    setAssignmentError('');
    setAssignmentSuccess('');
    if (selectedClassId <= 0) {
      setAssignmentState('idle');
      return;
    }
    setAssignmentState('loading');
    void fetchCurriculumClassAssignment(selectedClassId)
      .then((result) => {
        if (requestToken !== assignmentRequestRef.current) return;
        setAssignment(result);
        setAssignmentBookId(result?.book_node_id || 0);
        if (result?.version_id) {
          setSelectedVersionId(result.version_id);
        }
        setAssignmentState('ready');
      })
      .catch((error) => {
        if (requestToken !== assignmentRequestRef.current) return;
        setAssignmentState('error');
        setAssignmentError(error instanceof Error ? error.message : '班级教材加载失败');
      });
  }, [selectedClassId]);

  useEffect(() => {
    if (activeTab !== 'unmapped') return;
    const requestToken = ++unmappedRequestRef.current;
    setUnmappedState('loading');
    setUnmappedError('');
    void fetchCurriculumUnmappedCandidates({ page: unmappedPage, page_size: 30, status: unmappedStatus })
      .then((result) => {
        if (requestToken !== unmappedRequestRef.current) return;
        setUnmapped(result);
        setUnmappedState(result.items.length ? 'ready' : 'empty');
      })
      .catch((error) => {
        if (requestToken !== unmappedRequestRef.current) return;
        setUnmappedState('error');
        setUnmappedError(error instanceof Error ? error.message : '待匹配内容加载失败');
      });
  }, [activeTab, unmappedPage, unmappedReload, unmappedStatus]);

  useEffect(() => {
    let cancelled = false;
    if (activeTab !== 'unmapped' || !canReviewProposals) {
      setProposals([]);
      return undefined;
    }
    setProposalsLoading(true);
    setProposalError('');
    void fetchCurriculumKnowledgePointProposals('proposed')
      .then((items) => {
        if (!cancelled) setProposals(items);
      })
      .catch((error) => {
        if (!cancelled) setProposalError(error instanceof Error ? error.message : '新知识点提议加载失败');
      })
      .finally(() => {
        if (!cancelled) setProposalsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeTab, canReviewProposals, unmappedReload]);

  async function openNodeDetail(node: Pick<CurriculumNode, 'id' | 'book_upstream_id'>) {
    const requestToken = ++detailRequestRef.current;
    const bookNodeId = books.find((book) => book.upstream_id === node.book_upstream_id)?.id;
    setDetailTarget({ nodeId: node.id, bookNodeId });
    setDetailOpen(true);
    setDetailState('loading');
    setDetail(null);
    setDetailError('');
    try {
      const nextDetail = await fetchCurriculumNodeDetail(node.id, bookNodeId);
      if (requestToken !== detailRequestRef.current) return;
      setDetail(nextDetail);
      setDetailState('ready');
    } catch (error) {
      if (requestToken !== detailRequestRef.current) return;
      setDetailState('error');
      setDetailError(error instanceof Error ? error.message : '知识点详情加载失败');
    }
  }

  async function saveAssignment() {
    if (selectedClassId <= 0 || selectedVersionId <= 0 || assignmentBookId <= 0 || assignmentSaving) return;
    setAssignmentSaving(true);
    setAssignmentError('');
    setAssignmentSuccess('');
    try {
      const result = await updateCurriculumClassAssignment(selectedClassId, {
        version_id: selectedVersionId,
        book_node_id: assignmentBookId,
        request_id: createRequestId('curriculum-assignment'),
        expected_assignment_id: assignment?.id || null,
      });
      setAssignment(result);
      setAssignmentSuccess(`已将 ${result.book_name} 分配给 ${result.class_name || '当前班级'}`);
    } catch (error) {
      setAssignmentError(error instanceof Error ? error.message : '教材分配失败');
    } finally {
      setAssignmentSaving(false);
    }
  }

  async function runLifecycleAction(action: 'review' | 'activate' | 'rollback') {
    if (!selectedVersion || !isSuperOwner || lifecycleBusy) return;
    setLifecycleBusy(true);
    setLifecycleError('');
    setLifecycleSuccess('');
    try {
      const result = await transitionCurriculumVersion(selectedVersion.id, action);
      setVersions((current) => current.map((version) => (
        version.id === result.id
          ? result
          : action === 'activate' && version.package_id === result.package_id && version.status === 'active'
            ? { ...version, status: 'deprecated' }
            : version
      )));
      setLifecycleSuccess(action === 'review' ? '课程版本已审核' : action === 'activate' ? '课程版本已启用' : '课程版本已回滚');
    } catch (error) {
      setLifecycleError(error instanceof Error ? error.message : '课程版本操作失败');
    } finally {
      setLifecycleBusy(false);
    }
  }

  function openMapping(candidate: CurriculumUnmappedCandidate) {
    setMappingCandidate(candidate);
    setMappingAction(canManageCurriculum ? 'map' : 'propose_new');
    setMappingTargetKey('');
    setMappingProposedName(candidate.candidate_text);
    setMappingNote('');
    setMappingSearchInput(candidate.candidate_text);
    setMappingSearchResults([]);
    setMappingError('');
  }

  async function searchMappingTargets() {
    if (!mappingCandidate || !mappingSearchInput.trim() || mappingSearching) return;
    if (mappingCandidate.curriculum_version_id <= 0 || mappingCandidate.curriculum_book_node_id <= 0) {
      setMappingError('该内容缺少确认时冻结的教材范围, 为保护课程隔离不能搜索匹配目标');
      return;
    }
    setMappingSearching(true);
    setMappingError('');
    try {
      let candidateBookUpstreamId = mappingCandidate.book_upstream_id;
      if (!candidateBookUpstreamId) {
        const candidateBooks = await fetchCurriculumBooks(mappingCandidate.curriculum_version_id);
        candidateBookUpstreamId = candidateBooks.find((book) => book.id === mappingCandidate.curriculum_book_node_id)?.upstream_id || '';
      }
      if (!candidateBookUpstreamId) {
        throw new Error('无法验证该内容确认时冻结的教材范围');
      }
      const result = await fetchCurriculumCatalog({
        version_id: mappingCandidate.curriculum_version_id,
        book_upstream_id: candidateBookUpstreamId,
        query: mappingSearchInput.trim(),
        page: 1,
        page_size: 12,
      });
      setMappingSearchResults(result.items.filter((item) => item.node_type === 'Concept' || item.node_type === 'Skill'));
    } catch (error) {
      setMappingError(error instanceof Error ? error.message : '匹配候选搜索失败');
    } finally {
      setMappingSearching(false);
    }
  }

  async function submitMapping() {
    if (!mappingCandidate || mappingSubmitting) return;
    if (!canManageCurriculum && mappingAction !== 'propose_new') {
      setMappingError('当前账号只能提议新知识点');
      return;
    }
    if ((mappingAction === 'map' || mappingAction === 'add_alias') && !mappingTargetKey.trim()) {
      setMappingError('请先选择一个受控知识点');
      return;
    }
    if (mappingAction === 'propose_new' && !mappingProposedName.trim()) {
      setMappingError('请输入拟新增的知识点名称');
      return;
    }
    setMappingSubmitting(true);
    setMappingError('');
    try {
      await submitCurriculumMappingAction(mappingCandidate.candidate_id, {
        action: mappingAction,
        target_knowledge_point_key: mappingTargetKey.trim(),
        proposed_name: mappingProposedName.trim(),
        note: mappingNote.trim(),
        request_id: createRequestId('curriculum-mapping'),
      });
      setMappingCandidate(null);
      setMappingSuccess(mappingAction === 'propose_new' ? '新知识点提议已提交审核' : '待匹配内容已处理');
      setUnmappedReload((current) => current + 1);
    } catch (error) {
      setMappingError(error instanceof Error ? error.message : '待匹配内容处理失败');
    } finally {
      setMappingSubmitting(false);
    }
  }

  async function reviewProposal(proposal: CurriculumKnowledgePointProposal, approve: boolean) {
    if (!canReviewProposals || proposalBusyId) return;
    setProposalBusyId(proposal.id);
    setProposalError('');
    setProposalSuccess('');
    try {
      const result = await reviewCurriculumKnowledgePointProposal(proposal.id, {
        approve,
        request_id: createRequestId('curriculum-proposal-review'),
      });
      setProposals((current) => current.filter((item) => item.id !== proposal.id));
      setProposalSuccess(approve
        ? `已启用 ${proposal.canonical_name}, 并重处理 ${result.reprocessed} 条待匹配内容`
        : `已拒绝 ${proposal.canonical_name}`);
      if (approve && result.reprocessed > 0) {
        setUnmappedReload((current) => current + 1);
      }
    } catch (error) {
      setProposalError(error instanceof Error ? error.message : '新知识点提议审核失败');
    } finally {
      setProposalBusyId(0);
    }
  }

  const filteredBooks = books.filter((book) => (
    (!stageKey || book.stage_key === stageKey) && (!gradeKey || book.grade_key === gradeKey)
  ));

  return (
    <div className={cn(workspacePageClass, 'min-w-0 space-y-6 overflow-x-hidden')} data-testid="curriculum-knowledge-page">
      <header className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-sky-600 dark:text-sky-400">
            <GitBranch className="size-4" />
            受控课程知识库
          </div>
          <h1 className={cn(workspaceSectionTitleClass, 'mt-2')}>课程知识点</h1>
          <p className={cn(workspaceSectionTextClass, 'mt-2 max-w-3xl')}>
            按教材查看可信知识点、前置关系和章节路径, 并处理课堂反馈中尚未匹配的内容.
          </p>
        </div>
        {selectedVersion ? (
          <div className="flex max-w-full flex-wrap items-center gap-2">
            <Badge variant={versionStatusVariant(selectedVersion.status)}>{versionStatusLabels[selectedVersion.status]}</Badge>
            <span className="max-w-full truncate text-xs text-slate-500 dark:text-slate-400">{selectedVersion.version_key}</span>
          </div>
        ) : null}
      </header>

      <div className="flex min-w-0 gap-1 overflow-x-auto rounded-2xl border border-sky-100 bg-white/80 p-1.5 dark:border-white/10 dark:bg-white/5" role="tablist" aria-label="课程知识点页面">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'catalog'}
          className={cn('min-h-10 shrink-0 rounded-xl px-4 text-sm font-semibold transition', activeTab === 'catalog' ? 'bg-sky-600 text-white shadow-sm' : 'text-slate-600 hover:bg-sky-50 dark:text-slate-300 dark:hover:bg-white/5')}
          onClick={() => setActiveTab('catalog')}
        >
          课程知识点
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'unmapped'}
          className={cn('min-h-10 shrink-0 rounded-xl px-4 text-sm font-semibold transition', activeTab === 'unmapped' ? 'bg-sky-600 text-white shadow-sm' : 'text-slate-600 hover:bg-sky-50 dark:text-slate-300 dark:hover:bg-white/5')}
          onClick={() => setActiveTab('unmapped')}
        >
          待匹配内容
        </button>
      </div>

      {initialState === 'loading' ? (
        <div className="grid gap-4 sm:grid-cols-2" data-testid="curriculum-page-loading">
          <Skeleton className="h-44 rounded-3xl" />
          <Skeleton className="h-44 rounded-3xl" />
        </div>
      ) : null}

      {initialState === 'error' ? (
        <ErrorState message={initialError} onRetry={() => setInitialReload((current) => current + 1)} testId="curriculum-page-error" />
      ) : null}

      {initialState === 'empty' ? (
        <EmptyState title="尚未安装课程知识库" description="课程版本导入并激活后, 这里会显示教材和知识点目录." testId="curriculum-page-empty" />
      ) : null}

      {initialState === 'ready' && activeTab === 'catalog' ? (
        <div className="min-w-0 space-y-6" role="tabpanel">
          <Card className={cn(workspaceCardClass, 'min-w-0')}>
            <CardHeader>
              <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <CardTitle>课程版本与教材</CardTitle>
                  <CardDescription className="mt-1 break-words">
                    {selectedVersion ? `${selectedVersion.curriculum_name} · ${selectedVersion.publisher_name} · ${selectedVersion.edition_name}` : '请选择课程版本'}
                  </CardDescription>
                </div>
                {isSuperOwner && selectedVersion ? (
                  <div className="flex max-w-full flex-wrap gap-2" data-testid="curriculum-lifecycle-controls">
                    {selectedVersion.status === 'draft' ? (
                      <Button type="button" size="sm" variant="outline" disabled={lifecycleBusy} onClick={() => void runLifecycleAction('review')}>审核版本</Button>
                    ) : null}
                    {selectedVersion.status === 'reviewed' ? (
                      <Button type="button" size="sm" disabled={lifecycleBusy} onClick={() => void runLifecycleAction('activate')}>启用版本</Button>
                    ) : null}
                    {selectedVersion.status === 'deprecated' && selectedVersion.reviewed_at ? (
                      <Button type="button" size="sm" variant="outline" disabled={lifecycleBusy} onClick={() => void runLifecycleAction('rollback')}>回滚到此版本</Button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="min-w-0 space-y-4">
              <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <label className="min-w-0 space-y-1.5 text-xs font-semibold text-slate-600 dark:text-slate-300">
                  <span>课程版本</span>
                  <select className={cn(workspaceFieldClass, 'min-w-0')} value={selectedVersionId || ''} onChange={(event) => { setSelectedVersionId(Number(event.target.value)); setCatalogPage(1); }}>
                    {versions.map((version) => <option key={version.id} value={version.id}>{version.version_key} · {versionStatusLabels[version.status]}</option>)}
                  </select>
                </label>
                <div className="rounded-2xl bg-sky-50 px-4 py-3 dark:bg-sky-500/10">
                  <p className="text-xs text-slate-500 dark:text-slate-400">知识点</p>
                  <p className="mt-1 text-xl font-bold text-slate-900 dark:text-white">{selectedVersion?.node_count || catalog.total}</p>
                </div>
                <div className="rounded-2xl bg-sky-50 px-4 py-3 dark:bg-sky-500/10">
                  <p className="text-xs text-slate-500 dark:text-slate-400">教材册数</p>
                  <p className="mt-1 text-xl font-bold text-slate-900 dark:text-white">{books.length}</p>
                </div>
                <div className="min-w-0 rounded-2xl bg-sky-50 px-4 py-3 dark:bg-sky-500/10">
                  <p className="text-xs text-slate-500 dark:text-slate-400">数据来源</p>
                  <p className="mt-1 truncate text-sm font-semibold text-slate-900 dark:text-white" title={selectedVersion?.source_dataset_revision}>{selectedVersion?.source_dataset_revision || '-'}</p>
                  <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">第三方 K12-KGraph · {selectedVersion?.data_license || '-'}</p>
                </div>
              </div>
              {lifecycleSuccess ? <p className="text-sm text-emerald-600" role="status">{lifecycleSuccess}</p> : null}
              {lifecycleError ? <p className="text-sm text-red-600" role="alert">{lifecycleError}</p> : null}
            </CardContent>
          </Card>

          <Card className={cn(workspaceCardClass, 'min-w-0')}>
            <CardHeader>
              <CardTitle>班级教材分配</CardTitle>
              <CardDescription>课堂反馈只会使用该班级已分配教材中的受控知识点.</CardDescription>
            </CardHeader>
            <CardContent className="min-w-0 space-y-4">
              <div className="grid min-w-0 gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)_auto] lg:items-end">
                <label className="min-w-0 space-y-1.5 text-xs font-semibold text-slate-600 dark:text-slate-300">
                  <span>班级</span>
                  <select className={workspaceFieldClass} value={selectedClassId || ''} onChange={(event) => setSelectedClassId(Number(event.target.value))}>
                    <option value="">请选择数学班级</option>
                    {mathClasses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label className="min-w-0 space-y-1.5 text-xs font-semibold text-slate-600 dark:text-slate-300">
                  <span>教材</span>
                  <select className={workspaceFieldClass} value={assignmentBookId || ''} onChange={(event) => setAssignmentBookId(Number(event.target.value))} disabled={assignmentState === 'loading' || !canManageCurriculum}>
                    <option value="">请选择教材</option>
                    {books.map((book) => <option key={book.id} value={book.id}>{book.canonical_name} · {book.knowledge_point_count} 个知识点</option>)}
                  </select>
                </label>
                {canManageCurriculum ? (
                  <button type="button" className={cn(workspacePrimaryButtonClass, 'w-full lg:w-auto')} disabled={assignmentSaving || assignmentBookId <= 0 || selectedClassId <= 0 || selectedVersion?.status !== 'active'} onClick={() => void saveAssignment()}>
                    {assignmentSaving ? '保存中' : '保存分配'}
                  </button>
                ) : null}
              </div>
              {assignmentState === 'loading' ? <Skeleton className="h-5 w-52" /> : null}
              {assignment ? <p className="break-words text-xs text-slate-500 dark:text-slate-400">当前: {assignment.book_name} · 分配于 {formatTime(assignment.assigned_at)}</p> : null}
              {selectedVersion?.status !== 'active' ? <p className="text-xs text-amber-600 dark:text-amber-300">当前版本仅用于查看历史, 只有使用中的数学课程版本可以分配给班级.</p> : null}
              {assignmentSuccess ? <p className="text-sm text-emerald-600" role="status">{assignmentSuccess}</p> : null}
              {assignmentError ? <p className="text-sm text-red-600" role="alert">{assignmentError}</p> : null}
            </CardContent>
          </Card>

          <Card className={cn(workspaceCardClass, 'min-w-0')}>
            <CardHeader>
              <CardTitle>知识点目录</CardTitle>
              <CardDescription>搜索名称或精确别名, 并按学段、年级和教材缩小范围.</CardDescription>
            </CardHeader>
            <CardContent className="min-w-0 space-y-5">
              <form className="grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-6" onSubmit={(event) => { event.preventDefault(); setCatalogPage(1); setAppliedQuery(queryInput.trim()); }}>
                <label className="min-w-0 space-y-1.5 sm:col-span-2 lg:col-span-2">
                  <span className="sr-only">搜索知识点</span>
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
                    <Input value={queryInput} onChange={(event) => setQueryInput(event.target.value)} placeholder="搜索知识点或别名" className="h-11 min-w-0 pl-9" />
                  </div>
                </label>
                <select aria-label="学段" className={workspaceFieldClass} value={stageKey} onChange={(event) => { setStageKey(event.target.value); setGradeKey(''); setBookUpstreamId(''); setCatalogPage(1); }}>
                  <option value="">全部学段</option>
                  <option value="primary">小学</option>
                  <option value="junior">初中</option>
                  <option value="senior">高中</option>
                </select>
                <select aria-label="年级" className={workspaceFieldClass} value={gradeKey} onChange={(event) => { setGradeKey(event.target.value); setBookUpstreamId(''); setCatalogPage(1); }}>
                  <option value="">全部年级</option>
                  {Array.from(new Set(books.filter((book) => !stageKey || book.stage_key === stageKey).map((book) => book.grade_key))).filter(Boolean).map((grade) => <option key={grade} value={grade}>{gradeLabels[grade] || `${grade} 年级`}</option>)}
                </select>
                <select aria-label="教材" className={workspaceFieldClass} value={bookUpstreamId} onChange={(event) => { setBookUpstreamId(event.target.value); setCatalogPage(1); }}>
                  <option value="">全部教材</option>
                  {filteredBooks.map((book) => <option key={book.id} value={book.upstream_id}>{book.canonical_name}</option>)}
                </select>
                <select aria-label="内容类型" className={workspaceFieldClass} value={nodeType} onChange={(event) => { setNodeType(event.target.value as CurriculumNodeType | ''); setCatalogPage(1); }}>
                  <option value="">全部类型</option>
                  <option value="Chapter">章节</option>
                  <option value="Section">小节</option>
                  <option value="Concept">概念</option>
                  <option value="Skill">技能</option>
                </select>
                <button type="submit" className={cn(workspaceSecondaryButtonClass, 'w-full sm:col-span-2 lg:col-span-1')}>搜索</button>
              </form>

              {catalogState === 'loading' ? (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="curriculum-catalog-loading">
                  {Array.from({ length: 6 }, (_, index) => <Skeleton key={index} className="h-36 rounded-2xl" />)}
                </div>
              ) : null}
              {catalogState === 'error' ? <ErrorState message={catalogError} onRetry={() => setCatalogReload((current) => current + 1)} testId="curriculum-catalog-error" /> : null}
              {catalogState === 'empty' ? <EmptyState title="没有找到匹配的知识点" description="可以清空搜索词或调整教材、年级和类型筛选." testId="curriculum-catalog-empty" /> : null}
              {catalogState === 'ready' ? (
                <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="curriculum-catalog-success">
                  {catalog.items.map((node) => (
                    <button key={node.id} type="button" className="group min-w-0 rounded-2xl border border-sky-100 bg-white/85 p-4 text-left transition hover:-translate-y-0.5 hover:border-sky-300 hover:shadow-lg dark:border-white/10 dark:bg-white/5" onClick={() => void openNodeDetail(node)}>
                      <div className="flex min-w-0 items-start justify-between gap-3">
                        <div className="min-w-0">
                          <Badge variant="outline">{nodeTypeLabels[node.node_type]}</Badge>
                          <p className="mt-2 break-words text-sm font-semibold text-slate-900 dark:text-white">{node.canonical_name}</p>
                        </div>
                        <ChevronRight className="mt-1 size-4 shrink-0 text-slate-400 transition group-hover:translate-x-0.5" />
                      </div>
                      <p className="mt-2 line-clamp-2 break-words text-xs leading-5 text-slate-500 dark:text-slate-400">{node.description || (node.aliases.length ? `别名: ${node.aliases.join('、')}` : '查看章节路径和关联知识点')}</p>
                      <p className="mt-3 truncate text-[11px] text-slate-400">{stageLabels[node.stage_key] || node.stage_key} {gradeLabels[node.grade_key] || node.grade_key}</p>
                    </button>
                  ))}
                </div>
              ) : null}

              {catalog.total > 0 ? (
                <div className="flex min-w-0 flex-col gap-3 border-t border-sky-100 pt-4 sm:flex-row sm:items-center sm:justify-between dark:border-white/10">
                  <p className="text-xs text-slate-500 dark:text-slate-400">共 {catalog.total} 条, 第 {catalog.page} / {pageCount(catalog)} 页</p>
                  <div className="flex gap-2">
                    <Button type="button" variant="outline" size="sm" disabled={catalog.page <= 1 || catalogState === 'loading'} onClick={() => setCatalogPage((current) => Math.max(1, current - 1))}><ArrowLeft data-icon="inline-start" />上一页</Button>
                    <Button type="button" variant="outline" size="sm" disabled={catalog.page >= pageCount(catalog) || catalogState === 'loading'} onClick={() => setCatalogPage((current) => current + 1)}>下一页<ArrowRight data-icon="inline-end" /></Button>
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {initialState === 'ready' && activeTab === 'unmapped' ? (
        <Card className={cn(workspaceCardClass, 'min-w-0')} role="tabpanel">
          <CardHeader>
            <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <CardTitle>待匹配内容</CardTitle>
                <CardDescription className="mt-1">模型无法安全映射的内容会停留在这里, 不会进入可信学生成长轨迹.</CardDescription>
              </div>
              <select aria-label="匹配状态" className={cn(workspaceFieldClass, 'sm:w-40')} value={unmappedStatus} onChange={(event) => { setUnmappedStatus(event.target.value); setUnmappedPage(1); }}>
                <option value="pending">待处理</option>
                <option value="mapped">已匹配</option>
                <option value="dismissed">已忽略</option>
              </select>
            </div>
          </CardHeader>
          <CardContent className="min-w-0 space-y-4">
            {canReviewProposals ? (
              <section className="min-w-0 space-y-3 rounded-2xl border border-sky-100 bg-sky-50/55 p-4 dark:border-white/10 dark:bg-sky-500/5" data-testid="curriculum-proposal-review-section">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white">待审核的新知识点提议</h3>
                  <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">审核通过后才会成为机构内受控知识点, 并确定性重处理关联内容.</p>
                </div>
                {proposalsLoading ? <Skeleton className="h-20 rounded-xl" /> : null}
                {proposals.map((proposal) => (
                  <article key={proposal.id} className="min-w-0 rounded-xl border border-sky-100 bg-white p-3 dark:border-white/10 dark:bg-white/5">
                    <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className="break-words text-sm font-semibold text-slate-900 dark:text-white">{proposal.canonical_name}</p>
                        <p className="mt-1 break-words text-xs text-slate-500 dark:text-slate-400">{proposal.book_name || '已分配教材'}{proposal.version_key ? ` · ${proposal.version_key}` : ''}</p>
                        {proposal.description ? <p className="mt-1 break-words text-xs text-slate-500 dark:text-slate-400">{proposal.description}</p> : null}
                      </div>
                      <div className="flex w-full shrink-0 gap-2 sm:w-auto">
                        <Button type="button" size="sm" variant="outline" className="flex-1 sm:flex-none" disabled={proposalBusyId > 0} onClick={() => void reviewProposal(proposal, false)}>拒绝</Button>
                        <Button type="button" size="sm" className="flex-1 sm:flex-none" disabled={proposalBusyId > 0} onClick={() => void reviewProposal(proposal, true)}>审核并启用</Button>
                      </div>
                    </div>
                  </article>
                ))}
                {!proposalsLoading && proposals.length === 0 ? <p className="text-xs text-slate-500 dark:text-slate-400">当前没有待审核的新知识点提议.</p> : null}
                {proposalSuccess ? <p className="text-sm text-emerald-600" role="status">{proposalSuccess}</p> : null}
                {proposalError ? <p className="text-sm text-red-600" role="alert">{proposalError}</p> : null}
              </section>
            ) : null}
            {mappingSuccess ? (
              <Alert data-testid="curriculum-mapping-success">
                <CheckCircle2 className="size-4" />
                <AlertTitle>处理成功</AlertTitle>
                <AlertDescription>{mappingSuccess}</AlertDescription>
              </Alert>
            ) : null}
            {unmappedState === 'loading' ? (
              <div className="space-y-3" data-testid="curriculum-unmapped-loading">
                <Skeleton className="h-32 rounded-2xl" />
                <Skeleton className="h-32 rounded-2xl" />
              </div>
            ) : null}
            {unmappedState === 'error' ? <ErrorState message={unmappedError} onRetry={() => setUnmappedReload((current) => current + 1)} testId="curriculum-unmapped-error" /> : null}
            {unmappedState === 'empty' ? <EmptyState title="没有待匹配内容" description="当前筛选范围内的课堂反馈内容都已处理." testId="curriculum-unmapped-empty" /> : null}
            {unmappedState === 'ready' ? (
              <div className="space-y-3" data-testid="curriculum-unmapped-success">
                {unmapped.items.map((candidate) => (
                  <article key={candidate.candidate_id} className="min-w-0 rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-white/5">
                    <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="outline">{candidate.status === 'pending' ? '待处理' : candidate.status}</Badge>
                          {candidate.class_name ? <span className="text-xs text-slate-500 dark:text-slate-400">{candidate.class_name}</span> : null}
                        </div>
                        <p className="mt-2 break-words text-sm font-semibold text-slate-900 dark:text-white">{candidate.candidate_text}</p>
                        <p className="mt-2 break-words text-xs text-slate-500 dark:text-slate-400">来自第 {candidate.revision_no} 次已确认反馈 · {formatTime(candidate.created_at)}</p>
                        {candidate.book_name ? <p className="mt-1 break-words text-[11px] text-slate-400">教材范围: {candidate.book_name}{candidate.version_key ? ` · ${candidate.version_key}` : ''}</p> : null}
                      </div>
                      {candidate.status === 'pending' ? <Button type="button" size="sm" className="w-full shrink-0 sm:w-auto" onClick={() => openMapping(candidate)}>{canManageCurriculum ? '开始匹配' : '提议知识点'}</Button> : null}
                    </div>
                  </article>
                ))}
              </div>
            ) : null}
            {unmapped.total > 0 ? (
              <div className="flex min-w-0 flex-col gap-3 border-t border-sky-100 pt-4 sm:flex-row sm:items-center sm:justify-between dark:border-white/10">
                <p className="text-xs text-slate-500 dark:text-slate-400">共 {unmapped.total} 条, 第 {unmapped.page} / {pageCount(unmapped)} 页</p>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" disabled={unmapped.page <= 1} onClick={() => setUnmappedPage((current) => Math.max(1, current - 1))}>上一页</Button>
                  <Button type="button" variant="outline" size="sm" disabled={unmapped.page >= pageCount(unmapped)} onClick={() => setUnmappedPage((current) => current + 1)}>下一页</Button>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Dialog open={detailOpen} onOpenChange={(open) => { setDetailOpen(open); if (!open) ++detailRequestRef.current; }}>
        <DialogContent className="max-h-[90vh] min-w-0 sm:max-w-2xl" data-testid="curriculum-node-detail-dialog">
          <DialogHeader>
            <DialogTitle>{detail?.canonical_name || '知识点详情'}</DialogTitle>
            <DialogDescription>查看教材章节路径、前置知识和后续学习方向.</DialogDescription>
          </DialogHeader>
          <ScrollArea className="h-[min(70vh,640px)] overflow-hidden">
            <div className="min-w-0 space-y-5 pr-3 pb-2">
              {detailState === 'loading' ? <div className="space-y-3"><Skeleton className="h-7 w-44" /><Skeleton className="h-24 w-full" /><Skeleton className="h-36 w-full" /></div> : null}
              {detailState === 'error' ? <ErrorState message={detailError} onRetry={() => detailTarget && void openNodeDetail({ id: detailTarget.nodeId, book_upstream_id: books.find((book) => book.id === detailTarget.bookNodeId)?.upstream_id || '' })} testId="curriculum-detail-error" /> : null}
              {detailState === 'ready' && detail ? (
                <>
                  <div className="flex flex-wrap gap-2">
                    <Badge>{nodeTypeLabels[detail.node_type]}</Badge>
                    <Badge variant="outline">{detail.curriculum_name}</Badge>
                    <Badge variant="outline">第三方 K12-KGraph</Badge>
                    <Badge variant="outline">{detail.data_license}</Badge>
                  </div>
                  {detail.description ? <p className="break-words text-sm leading-6 text-slate-700 dark:text-slate-200">{detail.description}</p> : null}
                  <section className="space-y-2">
                    <h3 className="text-sm font-semibold text-slate-900 dark:text-white">教材章节路径</h3>
                    <div className="flex min-w-0 flex-wrap items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300">
                      {detail.path.map((item, index) => (
                        <span key={item.node_key} className="contents">
                          {index > 0 ? <ChevronRight className="size-3.5 shrink-0 text-slate-400" /> : null}
                          <span className="max-w-full break-words rounded-lg bg-sky-50 px-2 py-1 dark:bg-sky-500/10">{item.name}</span>
                        </span>
                      ))}
                    </div>
                  </section>
                  <Separator />
                  <div className="grid min-w-0 gap-4 sm:grid-cols-2">
                    <section className="min-w-0 space-y-2">
                      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-white"><Link2 className="size-4" />前置知识</h3>
                      {detail.relations.prerequisites.length ? <ul className="space-y-2">{detail.relations.prerequisites.map((item) => <li key={item.node_key} className="break-words rounded-xl bg-slate-50 px-3 py-2 text-xs dark:bg-white/5">{item.canonical_name}</li>)}</ul> : <p className="text-xs text-slate-500">暂无明确前置知识.</p>}
                    </section>
                    <section className="min-w-0 space-y-2">
                      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-white"><GitBranch className="size-4" />后续知识</h3>
                      {detail.relations.follow_ups.length ? <ul className="space-y-2">{detail.relations.follow_ups.map((item) => <li key={item.node_key} className="break-words rounded-xl bg-slate-50 px-3 py-2 text-xs dark:bg-white/5">{item.canonical_name}</li>)}</ul> : <p className="text-xs text-slate-500">暂无明确后续知识.</p>}
                    </section>
                  </div>
                  {detail.aliases.length ? <section className="space-y-2"><h3 className="text-sm font-semibold text-slate-900 dark:text-white">精确别名</h3><div className="flex flex-wrap gap-2">{detail.aliases.map((alias) => <Badge key={alias} variant="outline">{alias}</Badge>)}</div></section> : null}
                  <div className="min-w-0 rounded-xl bg-slate-50 px-3 py-2 text-[11px] leading-5 text-slate-500 dark:bg-white/5 dark:text-slate-400">
                    <p className="break-all">课程版本: {detail.version_key}</p>
                    <p className="break-all">数据修订: {detail.source_dataset_revision}</p>
                  </div>
                </>
              ) : null}
            </div>
          </ScrollArea>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(mappingCandidate)} onOpenChange={(open) => { if (!open && !mappingSubmitting) setMappingCandidate(null); }}>
        <DialogContent className="max-h-[90vh] min-w-0 sm:max-w-2xl" data-testid="curriculum-mapping-dialog">
          <DialogHeader>
            <DialogTitle>匹配课程知识点</DialogTitle>
            <DialogDescription className="break-words">原始内容: {mappingCandidate?.candidate_text}</DialogDescription>
          </DialogHeader>
          <ScrollArea className="h-[min(68vh,620px)] overflow-hidden">
            <div className="min-w-0 space-y-5 pr-3 pb-2">
              <fieldset className="min-w-0 space-y-2">
                <legend className="text-sm font-semibold text-slate-900 dark:text-white">处理方式</legend>
                <div className="grid min-w-0 gap-2 sm:grid-cols-2">
                  {availableMappingActions.map((action) => (
                    <button key={action} type="button" className={cn('min-w-0 rounded-xl border px-3 py-2 text-left text-sm transition', mappingAction === action ? 'border-sky-500 bg-sky-50 text-sky-800 dark:bg-sky-500/10 dark:text-sky-200' : 'border-slate-200 text-slate-600 hover:border-sky-300 dark:border-white/10 dark:text-slate-300')} aria-pressed={mappingAction === action} onClick={() => { setMappingAction(action); setMappingError(''); }}>
                      {mappingActionLabels[action]}
                    </button>
                  ))}
                </div>
              </fieldset>

              {mappingAction === 'map' || mappingAction === 'add_alias' ? (
                <div className="min-w-0 space-y-3">
                  <label className="block min-w-0 space-y-1.5 text-sm font-semibold text-slate-900 dark:text-white">
                    <span>搜索受控知识点</span>
                    <div className="flex min-w-0 flex-col gap-2 sm:flex-row">
                      <Input className="min-w-0" value={mappingSearchInput} onChange={(event) => setMappingSearchInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); void searchMappingTargets(); } }} />
                      <Button type="button" variant="outline" className="shrink-0" disabled={mappingSearching || !mappingSearchInput.trim()} onClick={() => void searchMappingTargets()}>{mappingSearching ? '搜索中' : '搜索'}</Button>
                    </div>
                  </label>
                  {mappingTargetKey ? <p className="break-all rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">已选择: {mappingTargetKey}</p> : null}
                  <div className="grid min-w-0 gap-2 sm:grid-cols-2">
                    {mappingSearchResults.map((node) => (
                      <button key={node.id} type="button" className={cn('min-w-0 rounded-xl border px-3 py-2 text-left', mappingTargetKey === node.node_key ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-500/10' : 'border-slate-200 dark:border-white/10')} onClick={() => setMappingTargetKey(node.node_key)}>
                        <p className="break-words text-sm font-semibold text-slate-900 dark:text-white">{node.canonical_name}</p>
                        <p className="mt-1 break-all text-[11px] text-slate-500">{node.node_key}</p>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {mappingAction === 'propose_new' ? (
                <label className="block min-w-0 space-y-1.5 text-sm font-semibold text-slate-900 dark:text-white">
                  <span>拟新增知识点名称</span>
                  <Input value={mappingProposedName} onChange={(event) => setMappingProposedName(event.target.value)} />
                  <span className="block text-xs font-normal text-slate-500">提议需要审核, 不会立即进入可信图谱.</span>
                </label>
              ) : null}

              <label className="block min-w-0 space-y-1.5 text-sm font-semibold text-slate-900 dark:text-white">
                <span>处理备注 (可选)</span>
                <Textarea value={mappingNote} onChange={(event) => setMappingNote(event.target.value)} className="min-h-20 resize-y" />
              </label>
              {mappingError ? <Alert variant="destructive"><AlertCircle className="size-4" /><AlertTitle>无法提交</AlertTitle><AlertDescription>{mappingError}</AlertDescription></Alert> : null}
            </div>
          </ScrollArea>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={mappingSubmitting} onClick={() => setMappingCandidate(null)}>取消</Button>
            <Button type="button" disabled={mappingSubmitting} onClick={() => void submitMapping()}>{mappingSubmitting ? '提交中' : '确认处理'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="sr-only" aria-live="polite">
        {initialState === 'loading' ? '正在加载课程知识点' : ''}
        {catalogState === 'loading' ? '正在加载知识点目录' : ''}
        {unmappedState === 'loading' ? '正在加载待匹配内容' : ''}
      </div>
    </div>
  );
}
