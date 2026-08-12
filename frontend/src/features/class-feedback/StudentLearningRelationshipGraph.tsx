import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MutableRefObject,
} from 'react';
import {
  Maximize2,
  Minus,
  Move,
  Plus,
  RotateCcw,
  Search,
  Target,
} from 'lucide-react';
import type Graph from 'graphology';
import type Sigma from 'sigma';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  type ClassCommentaryStudentGraphTimelineEvent,
  type ClassCommentaryStudentLearningGraphSummary,
} from '../../classCommentary';
import {
  formatStudentLearningGraphTime,
  studentLearningStateLabels,
  studentLearningTrendLabels,
} from './studentLearningGraphPresentation';

type GraphNodeKind =
  | 'student'
  | 'knowledge_point'
  | 'learning_state'
  | 'learning_event'
  | 'lesson'
  | 'evidence'
  | 'revision'
  | 'teaching_method'
  | 'next_step';

type GraphPosition = { x: number; y: number };

type LearningGraphNode = GraphPosition & {
  id: string;
  kind: GraphNodeKind;
  label: string;
  color: string;
  size: number;
  priority: number;
  eventRef: string;
  knowledgePointKey: string;
  current: boolean;
};

type LearningGraphEdge = {
  id: string;
  source: string;
  target: string;
  relation: string;
  label: string;
  emphasized: boolean;
};

export type StudentLearningRelationshipGraphModel = {
  nodes: LearningGraphNode[];
  edges: LearningGraphEdge[];
  defaultSelectedId: string;
};

type StudentLearningRelationshipGraphProps = {
  studentName: string;
  summary: ClassCommentaryStudentLearningGraphSummary;
  usedGraphEvidenceRefs: string[];
  positionStoreRef: MutableRefObject<Map<string, GraphPosition>>;
};

const nodeKindLabels: Record<GraphNodeKind, string> = {
  student: '学生',
  knowledge_point: '知识点',
  learning_state: '学习状态',
  learning_event: '学习变化',
  lesson: '课程',
  evidence: '证据',
  revision: '已确认反馈',
  teaching_method: '教学方法',
  next_step: '下一步',
};

const nodeKindColors: Record<GraphNodeKind, string> = {
  student: '#171717',
  knowledge_point: '#7c3aed',
  learning_state: '#16a34a',
  learning_event: '#0f766e',
  lesson: '#3b82f6',
  evidence: '#2563eb',
  revision: '#64748b',
  teaching_method: '#0891b2',
  next_step: '#ea580c',
};

const filterKinds: GraphNodeKind[] = [
  'knowledge_point',
  'learning_state',
  'lesson',
  'evidence',
];

const subjectLabels: Record<string, string> = {
  math: '数学',
  physics: '物理',
  chemistry: '化学',
  biology: '生物',
  english: '英语',
  chinese: '语文',
};

const relationLabels: Record<string, string> = {
  HAS_STATE: '学习状态',
  ABOUT_KNOWLEDGE_POINT: '关于知识点',
  OBSERVED_IN: '观察于',
  SUPPORTED_BY: '证据支持',
  FROM_REVISION: '来自反馈',
  FOR_STUDENT: '属于学生',
  TAUGHT_WITH: '使用方法',
  RECOMMENDS_NEXT: '建议下一步',
};

function stableHash(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

function shortenGraphLabel(value: string, limit = 22): string {
  const normalized = value.trim().replace(/\s+/g, ' ');
  return normalized.length > limit ? `${normalized.slice(0, limit)}...` : normalized;
}

function compareEvents(
  left: ClassCommentaryStudentGraphTimelineEvent,
  right: ClassCommentaryStudentGraphTimelineEvent,
): number {
  const timeDifference = Date.parse(left.observed_at) - Date.parse(right.observed_at);
  if (Number.isFinite(timeDifference) && timeDifference !== 0) {
    return timeDifference;
  }
  return left.event_ref.localeCompare(right.event_ref);
}

function createTypePositions(count: number, anchor: GraphPosition, spread: GraphPosition): GraphPosition[] {
  if (count <= 1) {
    return [anchor];
  }
  return Array.from({ length: count }, (_, index) => {
    const centeredIndex = index - (count - 1) / 2;
    return {
      x: anchor.x + spread.x * centeredIndex,
      y: anchor.y + spread.y * centeredIndex,
    };
  });
}

function assignDeterministicPositions(nodes: LearningGraphNode[]): void {
  const layout: Record<GraphNodeKind, { anchor: GraphPosition; spread: GraphPosition }> = {
    student: { anchor: { x: 0, y: 0 }, spread: { x: 0, y: 0 } },
    knowledge_point: { anchor: { x: -2.2, y: 1.45 }, spread: { x: 0.25, y: 1.55 } },
    learning_state: { anchor: { x: -1.1, y: -1.55 }, spread: { x: 1.15, y: -0.2 } },
    learning_event: { anchor: { x: 1.65, y: 0.15 }, spread: { x: 0.2, y: 1.45 } },
    lesson: { anchor: { x: 3.65, y: 1.8 }, spread: { x: 0.2, y: 1.25 } },
    evidence: { anchor: { x: 4.15, y: -0.1 }, spread: { x: 0.25, y: 1.3 } },
    revision: { anchor: { x: 3.2, y: -2.2 }, spread: { x: 1.05, y: -0.15 } },
    teaching_method: { anchor: { x: 1.7, y: 2.65 }, spread: { x: 1.15, y: 0.15 } },
    next_step: { anchor: { x: 1.25, y: -2.9 }, spread: { x: 1.2, y: -0.1 } },
  };

  for (const kind of Object.keys(layout) as GraphNodeKind[]) {
    const matchingNodes = nodes
      .filter((node) => node.kind === kind)
      .sort((left, right) => left.id.localeCompare(right.id));
    const positions = createTypePositions(matchingNodes.length, layout[kind].anchor, layout[kind].spread);
    matchingNodes.forEach((node, index) => Object.assign(node, positions[index]));
  }
}

export function buildStudentLearningRelationshipGraphModel(
  studentName: string,
  summary: ClassCommentaryStudentLearningGraphSummary,
): StudentLearningRelationshipGraphModel {
  const nodes = new Map<string, LearningGraphNode>();
  const edges = new Map<string, LearningGraphEdge>();
  const events = [...summary.timeline].sort(compareEvents);

  const addNode = (
    id: string,
    kind: GraphNodeKind,
    label: string,
    options: Partial<Pick<LearningGraphNode, 'eventRef' | 'knowledgePointKey' | 'current'>> = {},
  ) => {
    if (nodes.has(id)) {
      return;
    }
    const sizeByKind: Record<GraphNodeKind, number> = {
      student: 17,
      knowledge_point: 15,
      learning_state: options.current ? 13 : 10,
      learning_event: 10,
      lesson: 9,
      evidence: 9,
      revision: 8,
      teaching_method: 9,
      next_step: 9,
    };
    const priorityByKind: Record<GraphNodeKind, number> = {
      student: 100,
      knowledge_point: 95,
      learning_state: options.current ? 90 : 72,
      learning_event: 68,
      next_step: 58,
      teaching_method: 54,
      lesson: 46,
      evidence: 42,
      revision: 34,
    };
    nodes.set(id, {
      id,
      kind,
      label,
      color: nodeKindColors[kind],
      size: sizeByKind[kind],
      priority: priorityByKind[kind],
      eventRef: options.eventRef || '',
      knowledgePointKey: options.knowledgePointKey || '',
      current: Boolean(options.current),
      x: 0,
      y: 0,
    });
  };

  const addEdge = (source: string, target: string, relation: string) => {
    const id = `${relation}:${source}:${target}`;
    if (!nodes.has(source) || !nodes.has(target) || edges.has(id)) {
      return;
    }
    edges.set(id, {
      id,
      source,
      target,
      relation,
      label: relationLabels[relation] || relation,
      emphasized: false,
    });
  };

  addNode('student', 'student', studentName || '当前学生');

  const currentStateNodeByKnowledgePoint = new Map<string, string>();

  for (const state of summary.current_states) {
    const knowledgePointId = `knowledge:${state.knowledge_point_key}`;
    addNode(knowledgePointId, 'knowledge_point', state.knowledge_point_name, {
      knowledgePointKey: state.knowledge_point_key,
    });
    const matchingEvent = [...events].reverse().find((event) => (
      event.knowledge_point_key === state.knowledge_point_key && event.state === state.state
    ));
    const stateNodeId = matchingEvent
      ? `state:${matchingEvent.event_ref}`
      : `current-state:${state.knowledge_point_key}`;
    addNode(stateNodeId, 'learning_state', studentLearningStateLabels[state.state], {
      eventRef: matchingEvent?.event_ref,
      knowledgePointKey: state.knowledge_point_key,
      current: true,
    });
    currentStateNodeByKnowledgePoint.set(state.knowledge_point_key, stateNodeId);
    addEdge('student', stateNodeId, 'HAS_STATE');
    addEdge(stateNodeId, knowledgePointId, 'ABOUT_KNOWLEDGE_POINT');
  }

  for (const event of events) {
    const knowledgePointId = `knowledge:${event.knowledge_point_key}`;
    const eventNodeId = `event:${event.event_ref}`;
    const stateNodeId = `state:${event.event_ref}`;
    const lessonNodeId = `lesson:${event.evidence.lesson_id}`;
    const evidenceNodeId = `evidence:${event.evidence.evidence_ref}`;
    const revisionNodeId = `revision:${event.evidence.revision_id}`;
    const isCurrent = currentStateNodeByKnowledgePoint.get(event.knowledge_point_key) === stateNodeId;

    addNode(knowledgePointId, 'knowledge_point', event.knowledge_point_name, {
      eventRef: event.event_ref,
      knowledgePointKey: event.knowledge_point_key,
    });
    addNode(eventNodeId, 'learning_event', studentLearningTrendLabels[event.trend], {
      eventRef: event.event_ref,
      knowledgePointKey: event.knowledge_point_key,
    });
    addNode(stateNodeId, 'learning_state', studentLearningStateLabels[event.state], {
      eventRef: event.event_ref,
      knowledgePointKey: event.knowledge_point_key,
      current: isCurrent,
    });
    addNode(lessonNodeId, 'lesson', event.evidence.lesson_name || '已确认课程', {
      eventRef: event.event_ref,
      knowledgePointKey: event.knowledge_point_key,
    });
    addNode(evidenceNodeId, 'evidence', event.evidence.quote, {
      eventRef: event.event_ref,
      knowledgePointKey: event.knowledge_point_key,
    });
    addNode(revisionNodeId, 'revision', `第 ${event.evidence.revision_no} 次已确认反馈`, {
      eventRef: event.event_ref,
      knowledgePointKey: event.knowledge_point_key,
    });

    addEdge(eventNodeId, stateNodeId, 'HAS_STATE');
    addEdge(eventNodeId, lessonNodeId, 'OBSERVED_IN');
    addEdge(eventNodeId, knowledgePointId, 'ABOUT_KNOWLEDGE_POINT');
    addEdge(eventNodeId, evidenceNodeId, 'SUPPORTED_BY');
    addEdge(evidenceNodeId, revisionNodeId, 'FROM_REVISION');
    addEdge(revisionNodeId, 'student', 'FOR_STUDENT');

    event.teaching_methods.forEach((method) => {
      const methodNodeId = `method:${stableHash(method)}`;
      addNode(methodNodeId, 'teaching_method', method, {
        eventRef: event.event_ref,
        knowledgePointKey: event.knowledge_point_key,
      });
      addEdge(eventNodeId, methodNodeId, 'TAUGHT_WITH');
    });
    event.next_steps.forEach((nextStep, index) => {
      const nextStepNodeId = `next:${event.event_ref}:${index}:${stableHash(nextStep)}`;
      addNode(nextStepNodeId, 'next_step', nextStep, {
        eventRef: event.event_ref,
        knowledgePointKey: event.knowledge_point_key,
      });
      addEdge(eventNodeId, nextStepNodeId, 'RECOMMENDS_NEXT');
    });

    // The scoped summary exposes the previous state value, but not the canonical
    // previous state node reference. Keep the old event visible without inventing
    // a relationship that the response cannot prove.
  }

  const nodeList = [...nodes.values()];
  assignDeterministicPositions(nodeList);
  const firstCurrentState = summary.current_states[0];
  const defaultSelectedId = firstCurrentState
    ? `knowledge:${firstCurrentState.knowledge_point_key}`
    : nodeList.find((node) => node.kind === 'knowledge_point')?.id || 'student';
  return { nodes: nodeList, edges: [...edges.values()], defaultSelectedId };
}

function findSelectedEvent(
  node: LearningGraphNode | undefined,
  summary: ClassCommentaryStudentLearningGraphSummary,
): ClassCommentaryStudentGraphTimelineEvent | null {
  if (!node) {
    return null;
  }
  if (node.eventRef) {
    const exactEvent = summary.timeline.find((event) => event.event_ref === node.eventRef);
    if (exactEvent) {
      return exactEvent;
    }
  }
  if (node.knowledgePointKey) {
    return [...summary.timeline]
      .filter((event) => event.knowledge_point_key === node.knowledgePointKey)
      .sort(compareEvents)
      .at(-1) || null;
  }
  return [...summary.timeline].sort(compareEvents).at(-1) || null;
}

function GraphEvidenceInspector({
  selectedNode,
  summary,
  usedEvidenceRefs,
}: {
  selectedNode: LearningGraphNode | undefined;
  summary: ClassCommentaryStudentLearningGraphSummary;
  usedEvidenceRefs: Set<string>;
}) {
  const selectedEvent = findSelectedEvent(selectedNode, summary);
  const currentState = summary.current_states.find((state) => (
    state.knowledge_point_key === (selectedNode?.knowledgePointKey || selectedEvent?.knowledge_point_key)
  ));
  const visibleState = selectedEvent?.state || currentState?.state;
  const previousState = selectedEvent?.previous_state;
  const curriculum = selectedEvent?.curriculum || currentState?.curriculum;
  const curriculumPath = curriculum?.path.map((item) => item.name).filter(Boolean) || [];

  return (
    <aside className="min-h-0 overflow-y-auto border-t bg-background px-4 py-4 lg:border-t-0 lg:border-l" data-testid="student-learning-graph-inspector" aria-live="polite">
      <p className="text-[11px] tracking-wide text-muted-foreground">
        当前选择 · {selectedNode ? nodeKindLabels[selectedNode.kind] : '学习记录'}
      </p>
      <h3 className="mt-1 break-words text-base font-semibold text-foreground">
        {selectedNode?.label || selectedEvent?.knowledge_point_name || '学生成长轨迹'}
      </h3>

      {visibleState ? (
        <div className="mt-5 space-y-2">
          <p className="text-xs text-muted-foreground">当前状态</p>
          <Badge variant="outline">{studentLearningStateLabels[visibleState]}</Badge>
        </div>
      ) : null}

      {selectedEvent ? (
        <>
          <div className="mt-5 space-y-2">
            <p className="text-xs text-muted-foreground">最近变化</p>
            <p className="text-sm font-medium text-foreground">
              {previousState
                ? `${studentLearningStateLabels[previousState]} -> ${studentLearningStateLabels[selectedEvent.state]}`
                : studentLearningTrendLabels[selectedEvent.trend]}
            </p>
          </div>

          <div className="mt-5 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">证据</p>
              {usedEvidenceRefs.has(selectedEvent.evidence.evidence_ref) ? (
                <Badge variant="secondary">本次生成已参考</Badge>
              ) : null}
            </div>
            <blockquote className="rounded-r-lg border-l-2 border-blue-400 bg-blue-50 px-3 py-2.5 text-sm leading-6 text-foreground">
              {selectedEvent.evidence.quote}
            </blockquote>
            <p className="text-[11px] text-muted-foreground">
              {selectedEvent.evidence.lesson_name} · 第 {selectedEvent.evidence.revision_no} 次已确认反馈
            </p>
            <p className="text-[11px] text-muted-foreground">
              {formatStudentLearningGraphTime(selectedEvent.evidence.confirmed_at)}
            </p>
          </div>

          {selectedEvent.teaching_methods.length ? (
            <div className="mt-5 space-y-2">
              <p className="text-xs text-muted-foreground">本次使用的教学方法</p>
              <div className="flex flex-wrap gap-2">
                {selectedEvent.teaching_methods.map((method) => (
                  <Badge key={method} variant="outline">{method}</Badge>
                ))}
              </div>
            </div>
          ) : null}

          {selectedEvent.next_steps.length ? (
            <div className="mt-5 space-y-2">
              <p className="text-xs text-muted-foreground">下一步建议</p>
              <div className="space-y-2">
                {selectedEvent.next_steps.map((nextStep) => (
                  <p key={nextStep} className="flex items-start gap-2 rounded-lg bg-orange-50 px-3 py-2.5 text-sm leading-5 text-orange-900">
                    <Target className="mt-0.5 size-4 shrink-0" />
                    <span>{nextStep}</span>
                  </p>
                ))}
              </div>
            </div>
          ) : null}
        </>
      ) : (
        <p className="mt-5 text-sm leading-6 text-muted-foreground">
          点击知识点、状态或证据节点, 可以查看对应的已确认反馈.
        </p>
      )}

      {curriculumPath.length ? (
        <div className="mt-5 border-t pt-4">
          <p className="text-xs text-muted-foreground">课程位置</p>
          <p className="mt-2 break-words text-xs leading-5 text-foreground">
            {curriculumPath.join(' · ')}
          </p>
        </div>
      ) : null}

      {curriculum?.prerequisites.length ? (
        <p className="mt-3 break-words text-xs leading-5 text-muted-foreground">
          前置知识: {curriculum.prerequisites.map((item) => item.canonical_name).join('、')}
        </p>
      ) : null}
      {curriculum?.follow_ups.length ? (
        <p className="mt-2 break-words text-xs leading-5 text-muted-foreground">
          后续知识: {curriculum.follow_ups.map((item) => item.canonical_name).join('、')}
        </p>
      ) : null}

      <p className="mt-6 border-t pt-4 text-[11px] text-muted-foreground">
        只显示当前学生 · {subjectLabels[summary.subject_key] || '当前科目'} · 已确认反馈
      </p>
    </aside>
  );
}

function LearningGraphCanvas({
  model,
  selectedId,
  onSelectedIdChange,
  positionStoreRef,
}: {
  model: StudentLearningRelationshipGraphModel;
  selectedId: string;
  onSelectedIdChange: (nodeId: string) => void;
  positionStoreRef: MutableRefObject<Map<string, GraphPosition>>;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<Sigma | null>(null);
  const graphRef = useRef<Graph | null>(null);
  const hoveredIdRef = useRef('');
  const selectedIdRef = useRef(selectedId);
  const searchRef = useRef('');
  const visibleKindsRef = useRef(new Set<GraphNodeKind>(Object.keys(nodeKindLabels) as GraphNodeKind[]));
  const [search, setSearch] = useState('');
  const [visibleKinds, setVisibleKinds] = useState(visibleKindsRef.current);
  const [graphError, setGraphError] = useState('');
  const [ready, setReady] = useState(false);

  selectedIdRef.current = selectedId;
  searchRef.current = search;
  visibleKindsRef.current = visibleKinds;

  useEffect(() => {
    let cancelled = false;
    let renderer: Sigma | null = null;
    let finishDragging = () => {};
    let cleanupDragging = () => {};

    const mountGraph = async () => {
      if (!containerRef.current) {
        return;
      }
      if (typeof WebGLRenderingContext === 'undefined') {
        setGraphError('当前浏览器无法显示关系图, 可以切换到成长轨迹查看相同记录.');
        return;
      }

      try {
        const [{ default: GraphConstructor }, { default: SigmaConstructor }, { EdgeArrowProgram }] = await Promise.all([
          import('graphology'),
          import('sigma'),
          import('sigma/rendering'),
        ]);
        if (cancelled || !containerRef.current) {
          return;
        }

        const graph = new GraphConstructor({ multi: true, type: 'directed' });
        for (const node of model.nodes) {
          const storedPosition = positionStoreRef.current.get(node.id);
          graph.addNode(node.id, {
            ...node,
            fullLabel: node.label,
            label: shortenGraphLabel(node.label),
            x: storedPosition?.x ?? node.x,
            y: storedPosition?.y ?? node.y,
          });
        }
        for (const edge of model.edges) {
          graph.addEdgeWithKey(edge.id, edge.source, edge.target, {
            ...edge,
            type: 'arrow',
            color: edge.emphasized ? '#16a34a' : '#cbd5e1',
            size: edge.emphasized ? 2.2 : 1.1,
          });
        }

        renderer = new SigmaConstructor(graph, containerRef.current, {
          allowInvalidContainer: false,
          defaultEdgeType: 'arrow',
          edgeProgramClasses: { arrow: EdgeArrowProgram },
          hideEdgesOnMove: false,
          hideLabelsOnMove: false,
          labelDensity: 0.8,
          labelGridCellSize: 118,
          labelRenderedSizeThreshold: 7,
          minCameraRatio: 0.28,
          maxCameraRatio: 4,
          renderEdgeLabels: true,
          stagePadding: 42,
          zIndex: true,
          nodeReducer: (nodeId, data) => {
            const currentSearch = searchRef.current.trim().toLocaleLowerCase('zh-CN');
            const matchesSearch = !currentSearch
              || String(data.fullLabel || data.label || '').toLocaleLowerCase('zh-CN').includes(currentSearch);
            const isVisible = visibleKindsRef.current.has(data.kind as GraphNodeKind) && matchesSearch;
            const focusedNodeId = hoveredIdRef.current || selectedIdRef.current;
            const isFocused = nodeId === focusedNodeId;
            const isNeighbor = Boolean(focusedNodeId && graph.areNeighbors(nodeId, focusedNodeId));
            const isDimmed = Boolean(focusedNodeId && !isFocused && !isNeighbor);
            return {
              ...data,
              color: isDimmed ? '#d4d4d8' : data.color,
              forceLabel: isFocused,
              hidden: !isVisible,
              highlighted: isFocused,
              label: isDimmed ? null : data.label,
              size: isFocused ? Number(data.size) * 1.3 : data.size,
              zIndex: isFocused ? 20 : isNeighbor ? 10 : data.priority,
            };
          },
          edgeReducer: (edgeId, data) => {
            const focusedNodeId = hoveredIdRef.current || selectedIdRef.current;
            const [source, target] = graph.extremities(edgeId);
            const isConnected = !focusedNodeId || source === focusedNodeId || target === focusedNodeId;
            return {
              ...data,
              color: isConnected ? data.color : '#e5e7eb',
              forceLabel: Boolean(focusedNodeId && isConnected),
              hidden: false,
              label: isConnected ? data.label : '',
              size: isConnected ? data.size : 0.45,
              zIndex: isConnected ? 5 : 1,
            };
          },
        });
        graphRef.current = graph;
        rendererRef.current = renderer;

        let draggedNode = '';
        let draggedNodeMoved = false;
        let dragStartViewportPosition: GraphPosition | null = null;
        let clearDraggedNodeMovedTimer: number | null = null;
        const stopDragging = () => {
          const shouldClearMovedGuard = draggedNodeMoved;
          draggedNode = '';
          dragStartViewportPosition = null;
          renderer?.getCamera().enable();
          if (containerRef.current) {
            containerRef.current.style.cursor = 'grab';
          }
          if (shouldClearMovedGuard) {
            if (clearDraggedNodeMovedTimer !== null) {
              window.clearTimeout(clearDraggedNodeMovedTimer);
            }
            clearDraggedNodeMovedTimer = window.setTimeout(() => {
              draggedNodeMoved = false;
              clearDraggedNodeMovedTimer = null;
            }, 0);
          }
        };
        finishDragging = stopDragging;
        cleanupDragging = () => {
          if (clearDraggedNodeMovedTimer !== null) {
            window.clearTimeout(clearDraggedNodeMovedTimer);
            clearDraggedNodeMovedTimer = null;
          }
          draggedNode = '';
          draggedNodeMoved = false;
          dragStartViewportPosition = null;
        };

        renderer.on('downNode', ({ node, event }) => {
          if (clearDraggedNodeMovedTimer !== null) {
            window.clearTimeout(clearDraggedNodeMovedTimer);
            clearDraggedNodeMovedTimer = null;
          }
          draggedNode = node;
          draggedNodeMoved = false;
          dragStartViewportPosition = { x: event.x, y: event.y };
          if (!renderer?.getCustomBBox()) {
            renderer?.setCustomBBox(renderer.getBBox());
          }
          event.preventSigmaDefault();
          event.original.preventDefault();
          event.original.stopPropagation();
          renderer?.getCamera().disable();
          if (containerRef.current) {
            containerRef.current.style.cursor = 'grabbing';
          }
        });
        renderer.on('moveBody', ({ event }) => {
          if (!draggedNode || !renderer) {
            return;
          }
          event.preventSigmaDefault();
          event.original.preventDefault();
          event.original.stopPropagation();
          if (
            dragStartViewportPosition
            && Math.hypot(
              event.x - dragStartViewportPosition.x,
              event.y - dragStartViewportPosition.y,
            ) < 4
          ) {
            return;
          }
          draggedNodeMoved = true;
          const position = renderer.viewportToGraph(event);
          graph.mergeNodeAttributes(draggedNode, position);
          positionStoreRef.current.set(draggedNode, position);
        });
        renderer.on('clickNode', ({ node, event }) => {
          if (draggedNodeMoved) {
            draggedNodeMoved = false;
            event.preventSigmaDefault();
            return;
          }
          onSelectedIdChange(node);
        });
        renderer.on('enterNode', ({ node }) => {
          hoveredIdRef.current = node;
          if (containerRef.current) {
            containerRef.current.style.cursor = 'grab';
          }
          renderer?.refresh();
        });
        renderer.on('leaveNode', () => {
          hoveredIdRef.current = '';
          if (containerRef.current && !draggedNode) {
            containerRef.current.style.cursor = 'default';
          }
          renderer?.refresh();
        });
        renderer.on('upNode', stopDragging);
        renderer.on('upStage', stopDragging);
        window.addEventListener('blur', finishDragging);

        setReady(true);
        setGraphError('');
        window.requestAnimationFrame(() => {
          if (!cancelled) {
            void renderer?.getCamera().animatedReset({ duration: 250 });
          }
        });
      } catch (error) {
        if (!cancelled) {
          setGraphError(error instanceof Error ? error.message : '关系图加载失败');
        }
      }
    };

    void mountGraph();
    return () => {
      cancelled = true;
      window.removeEventListener('blur', finishDragging);
      cleanupDragging();
      renderer?.getCamera().enable();
      renderer?.kill();
      rendererRef.current = null;
      graphRef.current = null;
      setReady(false);
    };
  }, [model, onSelectedIdChange, positionStoreRef]);

  useEffect(() => {
    rendererRef.current?.refresh();
  }, [search, selectedId, visibleKinds]);

  function toggleKind(kind: GraphNodeKind) {
    setVisibleKinds((current) => {
      const next = new Set(current);
      if (next.has(kind)) {
        next.delete(kind);
      } else {
        next.add(kind);
      }
      return next;
    });
  }

  function resetLayout() {
    const graph = graphRef.current;
    const renderer = rendererRef.current;
    if (!graph || !renderer) {
      return;
    }
    positionStoreRef.current.clear();
    for (const node of model.nodes) {
      graph.mergeNodeAttributes(node.id, { x: node.x, y: node.y });
    }
    renderer.setCustomBBox(null);
    renderer.refresh();
    void renderer.getCamera().animatedReset({ duration: 250 });
  }

  function fitGraph() {
    const renderer = rendererRef.current;
    if (!renderer) {
      return;
    }
    renderer.setCustomBBox(null);
    renderer.refresh();
    void renderer.getCamera().animatedReset({ duration: 200 });
  }

  function handleKeyboard(event: ReactKeyboardEvent<HTMLDivElement>) {
    const renderer = rendererRef.current;
    if (!renderer || event.target !== event.currentTarget) {
      return;
    }
    const camera = renderer.getCamera();
    const movement = (event.shiftKey ? 0.15 : 0.06) * camera.getState().ratio;
    if (event.key === '+' || event.key === '=') {
      event.preventDefault();
      void camera.animatedZoom({ duration: 120 });
    } else if (event.key === '-') {
      event.preventDefault();
      void camera.animatedUnzoom({ duration: 120 });
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight' || event.key === 'ArrowUp' || event.key === 'ArrowDown') {
      event.preventDefault();
      camera.updateState(({ x, y }) => ({
        x: x + (event.key === 'ArrowLeft' ? -movement : event.key === 'ArrowRight' ? movement : 0),
        y: y + (event.key === 'ArrowUp' ? -movement : event.key === 'ArrowDown' ? movement : 0),
      }));
    }
  }

  return (
    <div className="relative min-h-0 overflow-hidden bg-muted/15" data-testid="student-learning-relationship-graph">
      <div className="pointer-events-none absolute inset-x-3 top-3 z-10 flex flex-wrap items-center gap-2">
        <label className="pointer-events-auto relative w-56 max-w-[45%]">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="搜索知识点或证据"
            className="h-9 bg-background/95 pl-8 shadow-sm"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="搜索知识点或证据"
          />
        </label>
        <div className="pointer-events-auto order-last flex w-full flex-nowrap gap-1.5 overflow-x-auto pb-1 sm:order-none sm:w-auto sm:flex-wrap sm:overflow-visible sm:pb-0">
          {filterKinds.map((kind) => (
            <Button
              key={kind}
              type="button"
              size="sm"
              variant={visibleKinds.has(kind) ? 'outline' : 'ghost'}
              className="h-9 bg-background/95 px-2.5 text-xs shadow-sm"
              aria-pressed={visibleKinds.has(kind)}
              onClick={() => toggleKind(kind)}
            >
              <span className="size-2 rounded-full" style={{ backgroundColor: nodeKindColors[kind] }} />
              {nodeKindLabels[kind]}
            </Button>
          ))}
        </div>
        <div className="pointer-events-auto ml-auto flex gap-1 rounded-lg border bg-background/95 p-1 shadow-sm">
          <Button type="button" size="icon-sm" variant="ghost" aria-label="放大关系图" onClick={() => void rendererRef.current?.getCamera().animatedZoom({ duration: 150 })}>
            <Plus />
          </Button>
          <Button type="button" size="icon-sm" variant="ghost" aria-label="缩小关系图" onClick={() => void rendererRef.current?.getCamera().animatedUnzoom({ duration: 150 })}>
            <Minus />
          </Button>
          <Button type="button" size="icon-sm" variant="ghost" aria-label="适合画布" title="适合画布" onClick={fitGraph}>
            <Maximize2 />
          </Button>
          <Button type="button" size="icon-sm" variant="ghost" aria-label="恢复默认布局" title="恢复默认布局" onClick={resetLayout}>
            <RotateCcw />
          </Button>
        </div>
      </div>

      <div
        ref={containerRef}
        className="absolute inset-0 touch-none outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
        data-testid="student-learning-sigma-canvas"
        role="application"
        aria-label={`学生学习关系图. ${model.nodes.length} 个节点, ${model.edges.length} 条关系. 可拖动节点, 拖动画布, 使用滚轮或加减键缩放.`}
        aria-describedby="student-learning-graph-help"
        tabIndex={0}
        onKeyDown={handleKeyboard}
        onWheel={(event) => event.stopPropagation()}
      />
      <p id="student-learning-graph-help" className="sr-only">
        标签会自动减少拥挤. 选中或悬停节点会突出相邻关系, 也可以拖动节点手动拉开重叠文字.
      </p>
      <ul className="sr-only" aria-label="关系图节点列表">
        {model.nodes.map((node) => <li key={node.id}>{nodeKindLabels[node.kind]}: {node.label}</li>)}
      </ul>

      {!ready && !graphError ? (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
          正在整理学习关系...
        </div>
      ) : null}
      {graphError ? (
        <div className="absolute inset-0 flex items-center justify-center px-8 text-center text-sm text-muted-foreground" data-testid="student-learning-relationship-graph-error">
          {graphError}
        </div>
      ) : null}

      <div className="pointer-events-none absolute bottom-3 left-3 z-10 flex max-w-[calc(100%-1.5rem)] flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border bg-background/90 px-2.5 py-2 text-[10px] text-muted-foreground shadow-sm">
        <span className="flex items-center gap-1"><Move className="size-3" />拖动节点可避开重叠</span>
        {(['student', 'knowledge_point', 'learning_state', 'lesson', 'evidence', 'next_step'] as GraphNodeKind[]).map((kind) => (
          <span key={kind} className="flex items-center gap-1">
            <span className="size-2 rounded-full" style={{ backgroundColor: nodeKindColors[kind] }} />
            {nodeKindLabels[kind]}
          </span>
        ))}
      </div>
    </div>
  );
}

export function StudentLearningRelationshipGraph({
  studentName,
  summary,
  usedGraphEvidenceRefs,
  positionStoreRef,
}: StudentLearningRelationshipGraphProps) {
  const model = useMemo(
    () => buildStudentLearningRelationshipGraphModel(studentName, summary),
    [studentName, summary],
  );
  const [selectedId, setSelectedId] = useState(model.defaultSelectedId);
  const selectedNode = model.nodes.find((node) => node.id === selectedId)
    || model.nodes.find((node) => node.id === model.defaultSelectedId)
    || model.nodes[0];
  const allowedEvidenceRefs = useMemo(() => new Set(
    usedGraphEvidenceRefs.length ? usedGraphEvidenceRefs : summary.used_graph_evidence_refs,
  ), [summary.used_graph_evidence_refs, usedGraphEvidenceRefs]);

  useEffect(() => {
    setSelectedId(model.defaultSelectedId);
  }, [model.defaultSelectedId]);

  return (
    <div className="grid h-full min-h-0 grid-cols-1 grid-rows-[minmax(360px,1fr)_minmax(0,240px)] lg:grid-cols-[minmax(0,1fr)_310px] lg:grid-rows-1" data-testid="student-learning-relationship-view">
      <LearningGraphCanvas
        model={model}
        selectedId={selectedId}
        onSelectedIdChange={setSelectedId}
        positionStoreRef={positionStoreRef}
      />
      <GraphEvidenceInspector
        selectedNode={selectedNode}
        summary={summary}
        usedEvidenceRefs={allowedEvidenceRefs}
      />
    </div>
  );
}
