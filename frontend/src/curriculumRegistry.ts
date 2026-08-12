import { apiFetch } from './workspaceShared';

export type CurriculumVersionStatus = 'draft' | 'reviewed' | 'active' | 'deprecated';
export type CurriculumNodeType = 'Book' | 'Chapter' | 'Section' | 'Concept' | 'Skill';
export type CurriculumMappingAction = 'map' | 'add_alias' | 'propose_new' | 'reject';

export type CurriculumVersion = {
  id: number;
  package_id: number;
  package_key: string;
  curriculum_name: string;
  subject_key: string;
  publisher_name: string;
  edition_name: string;
  version_key: string;
  registry_version: number;
  status: CurriculumVersionStatus;
  source_dataset_revision: string;
  source_sha256: string;
  content_hash: string;
  data_license: string;
  node_count: number;
  edge_count: number;
  imported_at: string;
  reviewed_at: string;
  activated_at: string;
  deprecated_at: string;
};

export type CurriculumBook = {
  id: number;
  version_id: number;
  node_key: string;
  upstream_id: string;
  canonical_name: string;
  stage_key: string;
  grade_key: string;
  semester_key: string;
  knowledge_point_count: number;
};

export type CurriculumPathItem = {
  node_key: string;
  node_type: CurriculumNodeType;
  name: string;
};

export type CurriculumRelatedNode = {
  id: number;
  node_key: string;
  node_type: CurriculumNodeType;
  canonical_name: string;
};

export type CurriculumNode = {
  id: number;
  version_id: number;
  node_key: string;
  upstream_id: string;
  node_type: CurriculumNodeType;
  subject_key: string;
  canonical_name: string;
  description: string;
  aliases: string[];
  stage_key: string;
  grade_key: string;
  semester_key: string;
  book_upstream_id: string;
  source_locator: string;
  active: boolean;
};

export type CurriculumNodeDetail = CurriculumNode & {
  package_key: string;
  curriculum_name: string;
  publisher_name: string;
  edition_name: string;
  version_key: string;
  version_status: CurriculumVersionStatus;
  source_dataset_revision: string;
  source_sha256: string;
  data_license: string;
  path: CurriculumPathItem[];
  relations: {
    prerequisites: CurriculumRelatedNode[];
    follow_ups: CurriculumRelatedNode[];
    related: CurriculumRelatedNode[];
    is_a: CurriculumRelatedNode[];
  };
};

export type CurriculumCatalogQuery = {
  version_id: number;
  stage_key?: string;
  grade_key?: string;
  book_upstream_id?: string;
  chapter_upstream_id?: string;
  query?: string;
  node_type?: CurriculumNodeType | '';
  page?: number;
  page_size?: number;
};

export type CurriculumCatalogResult = {
  items: CurriculumNode[];
  page: number;
  page_size: number;
  total: number;
};

export type CurriculumClassAssignment = {
  schema_version: string;
  id: number;
  organization_id: number;
  class_id: number;
  class_name: string;
  subject_key: string;
  version_id: number;
  version_key: string;
  version_status: CurriculumVersionStatus;
  book_node_id: number;
  book_name: string;
  book_upstream_id: string;
  stage_key: string;
  grade_key: string;
  semester_key: string;
  curriculum_name: string;
  publisher_name: string;
  edition_name: string;
  assigned_at: string;
  note: string;
  assignment_mode: 'auto' | 'manual' | 'needs_review';
  inferred_grade: string;
  inferred_grade_key: string;
  inference_source: string;
  needs_review_reason: string;
  books: CurriculumAssignedBook[];
  primary_book_node_id: number | null;
  cas_token: string;
  scope_hash: string;
};

export type CurriculumAssignedBook = {
  assignment_id: number | null;
  book_node_id: number;
  book_name: string;
  book_upstream_id: string;
  stage_key: string;
  grade_key: string;
  semester_key: string;
  version_id: number;
  knowledge_point_count: number;
};

export type CurriculumUnmappedCandidate = {
  candidate_id: string;
  organization_id: number;
  extraction_job_id: number;
  student_id: number;
  student_name: string;
  subject_key: string;
  class_id: number;
  class_name: string;
  task_id: number;
  generation_id: number;
  revision_id: number;
  revision_no: number;
  curriculum_version_id: number;
  curriculum_book_node_id: number;
  book_upstream_id: string;
  book_name: string;
  version_key: string;
  candidate_text: string;
  normalized_candidate: string;
  status: string;
  resolved_knowledge_point_key: string;
  created_at: string;
  resolved_at: string;
};

export type CurriculumUnmappedResult = {
  items: CurriculumUnmappedCandidate[];
  page: number;
  page_size: number;
  total: number;
};

export type CurriculumMappingActionInput = {
  action: CurriculumMappingAction;
  target_knowledge_point_key?: string;
  proposed_name?: string;
  note?: string;
  request_id: string;
};

export type CurriculumAuditEvent = {
  id: number;
  action: string;
  target_type: string;
  target_key: string;
  actor_user_id: number;
  organization_id: number | null;
  class_id: number | null;
  note: string;
  created_at: string;
};

export type CurriculumKnowledgePointProposal = {
  id: number;
  organization_id: number;
  version_id: number;
  book_node_id: number;
  subject_key: string;
  knowledge_point_key: string;
  canonical_name: string;
  description: string;
  status: string;
  book_name: string;
  version_key: string;
  proposed_by_user_id: number;
  proposed_at: string;
  reviewed_by_user_id: number;
  reviewed_at: string;
  review_note: string;
};

export type CurriculumProposalReviewResult = {
  review: Record<string, unknown>;
  reprocessed: number;
  failures: Array<Record<string, unknown>>;
};

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value : value === null || value === undefined ? '' : String(value);
}

function numberValue(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function booleanValue(value: unknown): boolean {
  return value === true || value === 1 || value === '1';
}

function stringArrayValue(value: unknown): string[] {
  return Array.isArray(value) ? value.map(stringValue).filter(Boolean) : [];
}

function normalizeNodeType(value: unknown): CurriculumNodeType {
  const nodeType = stringValue(value) as CurriculumNodeType;
  return ['Book', 'Chapter', 'Section', 'Concept', 'Skill'].includes(nodeType) ? nodeType : 'Concept';
}

function normalizeVersionStatus(value: unknown): CurriculumVersionStatus {
  const status = stringValue(value) as CurriculumVersionStatus;
  return ['draft', 'reviewed', 'active', 'deprecated'].includes(status) ? status : 'draft';
}

function normalizeVersion(value: unknown): CurriculumVersion {
  const source = recordValue(value);
  return {
    id: numberValue(source.id),
    package_id: numberValue(source.package_id),
    package_key: stringValue(source.package_key),
    curriculum_name: stringValue(source.curriculum_name),
    subject_key: stringValue(source.subject_key),
    publisher_name: stringValue(source.publisher_name),
    edition_name: stringValue(source.edition_name),
    version_key: stringValue(source.version_key),
    registry_version: numberValue(source.registry_version),
    status: normalizeVersionStatus(source.status),
    source_dataset_revision: stringValue(source.source_dataset_revision),
    source_sha256: stringValue(source.source_sha256),
    content_hash: stringValue(source.content_hash),
    data_license: stringValue(source.data_license),
    node_count: numberValue(source.node_count),
    edge_count: numberValue(source.edge_count),
    imported_at: stringValue(source.imported_at),
    reviewed_at: stringValue(source.reviewed_at),
    activated_at: stringValue(source.activated_at),
    deprecated_at: stringValue(source.deprecated_at),
  };
}

function normalizeBook(value: unknown): CurriculumBook {
  const source = recordValue(value);
  return {
    id: numberValue(source.id),
    version_id: numberValue(source.version_id),
    node_key: stringValue(source.node_key),
    upstream_id: stringValue(source.upstream_id),
    canonical_name: stringValue(source.canonical_name),
    stage_key: stringValue(source.stage_key),
    grade_key: stringValue(source.grade_key),
    semester_key: stringValue(source.semester_key),
    knowledge_point_count: numberValue(source.knowledge_point_count),
  };
}

function normalizeNode(value: unknown): CurriculumNode {
  const source = recordValue(value);
  return {
    id: numberValue(source.id),
    version_id: numberValue(source.version_id),
    node_key: stringValue(source.node_key),
    upstream_id: stringValue(source.upstream_id),
    node_type: normalizeNodeType(source.node_type),
    subject_key: stringValue(source.subject_key),
    canonical_name: stringValue(source.canonical_name),
    description: stringValue(source.description),
    aliases: stringArrayValue(source.aliases),
    stage_key: stringValue(source.stage_key),
    grade_key: stringValue(source.grade_key),
    semester_key: stringValue(source.semester_key),
    book_upstream_id: stringValue(source.book_upstream_id),
    source_locator: stringValue(source.source_locator),
    active: source.active === undefined ? true : booleanValue(source.active),
  };
}

function normalizeRelatedNode(value: unknown): CurriculumRelatedNode {
  const source = recordValue(value);
  return {
    id: numberValue(source.id),
    node_key: stringValue(source.node_key),
    node_type: normalizeNodeType(source.node_type),
    canonical_name: stringValue(source.canonical_name),
  };
}

function normalizePathItem(value: unknown): CurriculumPathItem {
  const source = recordValue(value);
  return {
    node_key: stringValue(source.node_key),
    node_type: normalizeNodeType(source.node_type),
    name: stringValue(source.name),
  };
}

function normalizeAssignment(value: unknown): CurriculumClassAssignment | null {
  const source = recordValue(value);
  if (!numberValue(source.class_id)) {
    return null;
  }
  const books = (Array.isArray(source.books) ? source.books : []).map((value) => {
    const book = recordValue(value);
    return {
      assignment_id: numberValue(book.assignment_id) || null,
      book_node_id: numberValue(book.book_node_id),
      book_name: stringValue(book.book_name),
      book_upstream_id: stringValue(book.book_upstream_id),
      stage_key: stringValue(book.stage_key),
      grade_key: stringValue(book.grade_key),
      semester_key: stringValue(book.semester_key),
      version_id: numberValue(book.version_id),
      knowledge_point_count: numberValue(book.knowledge_point_count),
    };
  });
  const legacyBook = numberValue(source.book_node_id) > 0 && books.length === 0 ? [{
    assignment_id: numberValue(source.id) || null,
    book_node_id: numberValue(source.book_node_id),
    book_name: stringValue(source.book_name),
    book_upstream_id: stringValue(source.book_upstream_id),
    stage_key: stringValue(source.stage_key),
    grade_key: stringValue(source.grade_key),
    semester_key: stringValue(source.semester_key),
    version_id: numberValue(source.version_id),
    knowledge_point_count: 0,
  }] : [];
  const normalizedBooks = books.length ? books : legacyBook;
  return {
    id: numberValue(source.id),
    organization_id: numberValue(source.organization_id),
    class_id: numberValue(source.class_id),
    class_name: stringValue(source.class_name),
    subject_key: stringValue(source.subject_key),
    version_id: numberValue(source.version_id),
    version_key: stringValue(source.version_key),
    version_status: normalizeVersionStatus(source.version_status),
    book_node_id: numberValue(source.book_node_id),
    book_name: stringValue(source.book_name),
    book_upstream_id: stringValue(source.book_upstream_id),
    stage_key: stringValue(source.stage_key),
    grade_key: stringValue(source.grade_key),
    semester_key: stringValue(source.semester_key),
    curriculum_name: stringValue(source.curriculum_name),
    publisher_name: stringValue(source.publisher_name),
    edition_name: stringValue(source.edition_name),
    assigned_at: stringValue(source.assigned_at),
    note: stringValue(source.note),
    schema_version: stringValue(source.schema_version) || 'class_curriculum_assignment.v1',
    assignment_mode: (['auto', 'manual', 'needs_review'].includes(stringValue(source.assignment_mode))
      ? stringValue(source.assignment_mode)
      : normalizedBooks.length ? 'manual' : 'needs_review') as CurriculumClassAssignment['assignment_mode'],
    inferred_grade: stringValue(source.inferred_grade),
    inferred_grade_key: stringValue(source.inferred_grade_key),
    inference_source: stringValue(source.inference_source),
    needs_review_reason: stringValue(source.needs_review_reason),
    books: normalizedBooks,
    primary_book_node_id: numberValue(source.primary_book_node_id) || null,
    cas_token: stringValue(source.cas_token),
    scope_hash: stringValue(source.scope_hash),
  };
}

function normalizeUnmappedCandidate(value: unknown): CurriculumUnmappedCandidate {
  const source = recordValue(value);
  const assignment = recordValue(source.curriculum_assignment);
  return {
    candidate_id: stringValue(source.candidate_id),
    organization_id: numberValue(source.organization_id),
    extraction_job_id: numberValue(source.extraction_job_id),
    student_id: numberValue(source.student_id),
    student_name: stringValue(source.student_name),
    subject_key: stringValue(source.subject_key),
    class_id: numberValue(source.class_id),
    class_name: stringValue(source.class_name),
    task_id: numberValue(source.task_id),
    generation_id: numberValue(source.generation_id),
    revision_id: numberValue(source.revision_id),
    revision_no: numberValue(source.revision_no),
    curriculum_version_id: numberValue(source.curriculum_version_id || assignment.version_id),
    curriculum_book_node_id: numberValue(source.curriculum_book_node_id || assignment.book_node_id),
    book_upstream_id: stringValue(source.book_upstream_id || assignment.book_upstream_id),
    book_name: stringValue(source.book_name || assignment.book_name),
    version_key: stringValue(source.version_key || assignment.version_key),
    candidate_text: stringValue(source.candidate_text),
    normalized_candidate: stringValue(source.normalized_candidate),
    status: stringValue(source.status),
    resolved_knowledge_point_key: stringValue(source.resolved_knowledge_point_key),
    created_at: stringValue(source.created_at),
    resolved_at: stringValue(source.resolved_at),
  };
}

function appendQueryValue(params: URLSearchParams, key: string, value: string | number | undefined): void {
  if (value !== undefined && value !== '') {
    params.set(key, String(value));
  }
}

export async function fetchCurriculumVersions(): Promise<CurriculumVersion[]> {
  const payload = await apiFetch<{ versions?: unknown[] }>('/api/class-commentary/curriculum/versions');
  return (Array.isArray(payload.versions) ? payload.versions : []).map(normalizeVersion);
}

export async function fetchCurriculumBooks(versionId: number): Promise<CurriculumBook[]> {
  const payload = await apiFetch<{ books?: unknown[] }>(
    `/api/class-commentary/curriculum/books?version_id=${encodeURIComponent(String(versionId))}`,
  );
  return (Array.isArray(payload.books) ? payload.books : []).map(normalizeBook);
}

export async function fetchCurriculumCatalog(query: CurriculumCatalogQuery): Promise<CurriculumCatalogResult> {
  const params = new URLSearchParams();
  appendQueryValue(params, 'version_id', query.version_id);
  appendQueryValue(params, 'stage_key', query.stage_key);
  appendQueryValue(params, 'grade_key', query.grade_key);
  appendQueryValue(params, 'book_upstream_id', query.book_upstream_id);
  appendQueryValue(params, 'chapter_upstream_id', query.chapter_upstream_id);
  appendQueryValue(params, 'query', query.query);
  appendQueryValue(params, 'node_type', query.node_type);
  appendQueryValue(params, 'page', query.page ?? 1);
  appendQueryValue(params, 'page_size', query.page_size ?? 30);
  const payload = await apiFetch<Record<string, unknown>>(`/api/class-commentary/curriculum/catalog?${params}`);
  const source = recordValue(payload.catalog || payload);
  return {
    items: (Array.isArray(source.items) ? source.items : []).map(normalizeNode),
    page: Math.max(1, numberValue(source.page) || 1),
    page_size: Math.max(1, numberValue(source.page_size) || 30),
    total: Math.max(0, numberValue(source.total)),
  };
}

export async function fetchCurriculumNodeDetail(nodeId: number, bookNodeId?: number): Promise<CurriculumNodeDetail> {
  const suffix = bookNodeId && bookNodeId > 0
    ? `?book_node_id=${encodeURIComponent(String(bookNodeId))}`
    : '';
  const payload = await apiFetch<Record<string, unknown>>(
    `/api/class-commentary/curriculum/nodes/${encodeURIComponent(String(nodeId))}${suffix}`,
  );
  const source = recordValue(payload.node || payload);
  const node = normalizeNode(source);
  const relations = recordValue(source.relations);
  return {
    ...node,
    package_key: stringValue(source.package_key),
    curriculum_name: stringValue(source.curriculum_name),
    publisher_name: stringValue(source.publisher_name),
    edition_name: stringValue(source.edition_name),
    version_key: stringValue(source.version_key),
    version_status: normalizeVersionStatus(source.version_status),
    source_dataset_revision: stringValue(source.source_dataset_revision),
    source_sha256: stringValue(source.source_sha256),
    data_license: stringValue(source.data_license),
    path: (Array.isArray(source.path) ? source.path : []).map(normalizePathItem),
    relations: {
      prerequisites: (Array.isArray(relations.prerequisites) ? relations.prerequisites : []).map(normalizeRelatedNode),
      follow_ups: (Array.isArray(relations.follow_ups) ? relations.follow_ups : []).map(normalizeRelatedNode),
      related: (Array.isArray(relations.related) ? relations.related : []).map(normalizeRelatedNode),
      is_a: (Array.isArray(relations.is_a) ? relations.is_a : []).map(normalizeRelatedNode),
    },
  };
}

export async function fetchCurriculumClassAssignment(classId: number): Promise<CurriculumClassAssignment | null> {
  const payload = await apiFetch<Record<string, unknown>>(
    `/api/class-commentary/curriculum/classes/${encodeURIComponent(String(classId))}/assignment`,
  );
  return normalizeAssignment(payload.assignment || payload);
}

export async function updateCurriculumClassAssignment(
  classId: number,
  input: {
    version_id: number;
    book_node_ids: number[];
    primary_book_node_id?: number | null;
    request_id: string;
    expected_cas_token: string;
    note?: string;
  },
): Promise<CurriculumClassAssignment> {
  const payload = await apiFetch<Record<string, unknown>>(
    `/api/class-commentary/curriculum/classes/${encodeURIComponent(String(classId))}/assignment`,
    { method: 'PUT', body: JSON.stringify(input) },
  );
  const assignment = normalizeAssignment(payload.assignment || payload);
  if (!assignment) {
    throw new Error('教材分配响应无效');
  }
  return assignment;
}

export async function resetCurriculumClassAssignmentToAuto(
  classId: number,
  input: {
    expected_cas_token: string;
    request_id: string;
    note?: string;
  },
): Promise<CurriculumClassAssignment> {
  const payload = await apiFetch<Record<string, unknown>>(
    `/api/class-commentary/curriculum/classes/${encodeURIComponent(String(classId))}/assignment`,
    {
      method: 'PUT',
      body: JSON.stringify({ ...input, assignment_mode: 'auto' }),
    },
  );
  const assignment = normalizeAssignment(payload.assignment || payload);
  if (!assignment) {
    throw new Error('教材自动匹配响应无效');
  }
  return assignment;
}

export async function fetchCurriculumUnmappedCandidates(input: {
  page?: number;
  page_size?: number;
  status?: string;
} = {}): Promise<CurriculumUnmappedResult> {
  const params = new URLSearchParams();
  appendQueryValue(params, 'page', input.page ?? 1);
  appendQueryValue(params, 'page_size', input.page_size ?? 30);
  appendQueryValue(params, 'status', input.status ?? 'pending');
  const payload = await apiFetch<Record<string, unknown>>(`/api/class-commentary/curriculum/unmapped?${params}`);
  return {
    items: (Array.isArray(payload.items) ? payload.items : []).map(normalizeUnmappedCandidate),
    page: Math.max(1, numberValue(payload.page) || 1),
    page_size: Math.max(1, numberValue(payload.page_size) || 30),
    total: Math.max(0, numberValue(payload.total)),
  };
}

export async function submitCurriculumMappingAction(
  candidateId: string,
  input: CurriculumMappingActionInput,
): Promise<Record<string, unknown>> {
  const payload = await apiFetch<Record<string, unknown>>(
    `/api/class-commentary/curriculum/unmapped/${encodeURIComponent(candidateId)}/actions`,
    { method: 'POST', body: JSON.stringify(input) },
  );
  return recordValue(payload.result || payload);
}

export async function fetchCurriculumAudit(): Promise<CurriculumAuditEvent[]> {
  const payload = await apiFetch<{ events?: unknown[] }>('/api/class-commentary/curriculum/audit');
  return (Array.isArray(payload.events) ? payload.events : []).map((value) => {
    const source = recordValue(value);
    return {
      id: numberValue(source.id),
      action: stringValue(source.action),
      target_type: stringValue(source.target_type),
      target_key: stringValue(source.target_key),
      actor_user_id: numberValue(source.actor_user_id),
      organization_id: source.organization_id === null ? null : numberValue(source.organization_id),
      class_id: source.class_id === null ? null : numberValue(source.class_id),
      note: stringValue(source.note),
      created_at: stringValue(source.created_at),
    };
  });
}

export async function fetchCurriculumKnowledgePointProposals(
  status = 'proposed',
): Promise<CurriculumKnowledgePointProposal[]> {
  const payload = await apiFetch<Record<string, unknown>>(
    `/api/class-commentary/curriculum/proposals?status=${encodeURIComponent(status)}`,
  );
  const items = Array.isArray(payload.items)
    ? payload.items
    : Array.isArray(payload.proposals)
      ? payload.proposals
      : [];
  return items.map((value) => {
    const source = recordValue(value);
    return {
      id: numberValue(source.id),
      organization_id: numberValue(source.organization_id),
      version_id: numberValue(source.version_id),
      book_node_id: numberValue(source.book_node_id),
      subject_key: stringValue(source.subject_key),
      knowledge_point_key: stringValue(source.knowledge_point_key),
      canonical_name: stringValue(source.canonical_name),
      description: stringValue(source.description),
      status: stringValue(source.status),
      book_name: stringValue(source.book_name),
      version_key: stringValue(source.version_key),
      proposed_by_user_id: numberValue(source.proposed_by_user_id),
      proposed_at: stringValue(source.proposed_at),
      reviewed_by_user_id: numberValue(source.reviewed_by_user_id),
      reviewed_at: stringValue(source.reviewed_at),
      review_note: stringValue(source.review_note),
    };
  });
}

export async function reviewCurriculumKnowledgePointProposal(
  proposalId: number,
  input: { approve: boolean; request_id: string; note?: string },
): Promise<CurriculumProposalReviewResult> {
  const payload = await apiFetch<Record<string, unknown>>(
    `/api/class-commentary/curriculum/proposals/${encodeURIComponent(String(proposalId))}/review`,
    { method: 'POST', body: JSON.stringify(input) },
  );
  const source = recordValue(payload.result || payload);
  return {
    review: recordValue(source.review),
    reprocessed: numberValue(source.reprocessed),
    failures: Array.isArray(source.failures) ? source.failures.map(recordValue) : [],
  };
}

export async function transitionCurriculumVersion(
  versionId: number,
  action: 'review' | 'activate' | 'rollback',
): Promise<CurriculumVersion> {
  const payload = await apiFetch<Record<string, unknown>>(
    `/api/class-commentary/curriculum/versions/${encodeURIComponent(String(versionId))}/${action}`,
    { method: 'POST', body: JSON.stringify({}) },
  );
  return normalizeVersion(payload.version || payload);
}
