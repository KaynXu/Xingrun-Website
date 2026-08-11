import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { resolve } from 'node:path';

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
} from './curriculumRegistry';
import { canOpenWorkspacePage } from './features/navigation/workspaceAccess';
import { getWorkspacePageFromPathname, getWorkspacePath } from './features/navigation/workspaceRoutes';

function createJsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => body,
  } as Response;
}

test('curriculum registry client keeps every operation inside the scoped class-commentary API', async () => {
  const originalFetch = globalThis.fetch;
  const calls: Array<{ path: string; options?: RequestInit }> = [];
  globalThis.fetch = (async (input: string | URL | Request, options?: RequestInit) => {
    const path = String(input);
    calls.push({ path, options });
    if (path.includes('/versions/3/')) return createJsonResponse({ version: { id: 3, status: 'reviewed' } });
    if (path.endsWith('/versions')) return createJsonResponse({ versions: [{ id: 3, status: 'active', version_key: 'pep-v1' }] });
    if (path.includes('/books?')) return createJsonResponse({ books: [{ id: 8, version_id: 3, canonical_name: '三年级上册', knowledge_point_count: 99 }] });
    if (path.includes('/catalog?')) return createJsonResponse({ items: [{ id: 11, version_id: 3, node_key: 'kp-11', node_type: 'Concept', canonical_name: '倍的认识', aliases: ['倍数'] }], page: 1, page_size: 30, total: 1 });
    if (path.includes('/nodes/11')) return createJsonResponse({ node: { id: 11, version_id: 3, node_key: 'kp-11', node_type: 'Concept', canonical_name: '倍的认识', path: [{ node_key: 'book-1', node_type: 'Book', name: '三年级上册' }], relations: { prerequisites: [], follow_ups: [], related: [], is_a: [] } } });
    if (path.includes('/classes/5/assignment') && options?.method === 'PUT') return createJsonResponse({ assignment: { id: 15, class_id: 5, version_id: 3, book_node_id: 8, book_name: '三年级上册', version_status: 'active' } });
    if (path.includes('/classes/5/assignment')) return createJsonResponse({ assignment: null });
    if (path.includes('/unmapped/candidate-1/actions')) return createJsonResponse({ result: { replayed: false } });
    if (path.includes('/unmapped?')) return createJsonResponse({ items: [{ candidate_id: 'candidate-1', candidate_text: '倍数关系', status: 'pending' }], page: 1, page_size: 30, total: 1 });
    if (path.includes('/proposals/4/review')) return createJsonResponse({ review: { id: 4 }, reprocessed: 1, failures: [] });
    if (path.includes('/proposals?')) return createJsonResponse({ items: [{ id: 4, canonical_name: '倍数关系', status: 'proposed' }] });
    throw new Error(`Unexpected request: ${path}`);
  }) as typeof fetch;

  try {
    const versions = await fetchCurriculumVersions();
    const books = await fetchCurriculumBooks(3);
    const catalog = await fetchCurriculumCatalog({ version_id: 3, stage_key: 'primary', query: '倍', page: 1 });
    const detail = await fetchCurriculumNodeDetail(11, 8);
    const assignment = await fetchCurriculumClassAssignment(5);
    const updated = await updateCurriculumClassAssignment(5, { version_id: 3, book_node_id: 8, expected_assignment_id: null, request_id: 'assign-1' });
    const unmapped = await fetchCurriculumUnmappedCandidates({ status: 'pending' });
    await submitCurriculumMappingAction('candidate-1', { action: 'map', target_knowledge_point_key: 'kp-11', request_id: 'mapping-1' });
    const proposals = await fetchCurriculumKnowledgePointProposals();
    const review = await reviewCurriculumKnowledgePointProposal(4, { approve: true, request_id: 'proposal-1' });
    await transitionCurriculumVersion(3, 'review');

    assert.equal(versions[0].version_key, 'pep-v1');
    assert.equal(books[0].knowledge_point_count, 99);
    assert.equal(catalog.items[0].aliases[0], '倍数');
    assert.equal(detail.path[0].name, '三年级上册');
    assert.equal(assignment, null);
    assert.equal(updated.book_name, '三年级上册');
    assert.equal(unmapped.items[0].candidate_text, '倍数关系');
    assert.equal(proposals[0].canonical_name, '倍数关系');
    assert.equal(review.reprocessed, 1);
    assert.ok(calls.every((call) => call.path.startsWith('/api/class-commentary/curriculum/')));
    assert.match(calls.find((call) => call.path.includes('/catalog?'))?.path || '', /version_id=3/);
    assert.match(calls.find((call) => call.path.includes('/catalog?'))?.path || '', /stage_key=primary/);
    assert.match(calls.find((call) => call.path.includes('/nodes/11'))?.path || '', /book_node_id=8/);
    assert.equal(calls.find((call) => call.path.includes('/classes/5/assignment') && call.options?.method === 'PUT')?.options?.method, 'PUT');
    assert.equal(calls.find((call) => call.path.includes('/unmapped/candidate-1/actions'))?.options?.method, 'POST');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('curriculum workspace route and configurable access stay explicit', () => {
  assert.equal(getWorkspacePath('curriculum-knowledge'), '/workspace/curriculum-knowledge');
  assert.equal(getWorkspacePageFromPathname('/workspace/curriculum-knowledge'), 'curriculum-knowledge');
  assert.equal(canOpenWorkspacePage({ role: 'member' }, 'curriculum-knowledge'), true);
  assert.equal(canOpenWorkspacePage({ role: 'admin', visible_pages: ['classes'] }, 'curriculum-knowledge'), false);
  assert.equal(canOpenWorkspacePage({ role: 'super_owner', visible_pages: ['curriculum-knowledge'] }, 'curriculum-knowledge'), true);
});

test('curriculum UI uses responsive no-overflow structures and role-gated lifecycle controls', () => {
  const pageSource = readFileSync(resolve(process.cwd(), 'src/features/curriculum/CurriculumKnowledgePage.tsx'), 'utf8');
  const sidebarSource = readFileSync(resolve(process.cwd(), 'src/features/navigation/Sidebar.tsx'), 'utf8');
  const contentSource = readFileSync(resolve(process.cwd(), 'src/features/navigation/WorkspacePageContent.tsx'), 'utf8');

  assert.match(pageSource, /min-w-0 space-y-6 overflow-x-hidden/);
  assert.match(pageSource, /grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-3/);
  assert.match(pageSource, /w-full shrink-0 sm:w-auto/);
  assert.match(pageSource, /isSuperOwner && selectedVersion/);
  assert.match(pageSource, /version_id: mappingCandidate\.curriculum_version_id/);
  assert.match(pageSource, /book_upstream_id: candidateBookUpstreamId/);
  assert.doesNotMatch(pageSource, /activeVersionId/);
  assert.match(pageSource, /role="tablist"/);
  assert.match(pageSource, /aria-selected=\{activeTab === 'catalog'\}/);
  assert.match(sidebarSource, /id: 'curriculum-knowledge'.*label: '课程知识点'/);
  assert.match(contentSource, /activeWorkspacePage === 'curriculum-knowledge'[\s\S]*<CurriculumKnowledgePage currentUser=\{currentUser\}/);
});
