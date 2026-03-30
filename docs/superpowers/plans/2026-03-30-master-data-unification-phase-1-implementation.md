# Master Data Unification Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first shippable phase of teacher and class master-data unification so SaaS owns canonical teacher and class identity, `智能错题` reads normalized names and mapping status from SaaS, and admins get a minimal review queue to resolve alias and record mismatches.

**Architecture:** Keep the existing Flask + SQLite app as the canonical home for teacher and class identity, but move new alias and wrong-question mapping logic into a focused `master_data.py` module instead of bloating `lesson_manager.py` further. Normalize wrong-question records on the SaaS backend before they reach React, then add one admin-only mapping page that resolves unresolved records and updates future matching behavior through centralized alias tables.

**Tech Stack:** Flask, SQLite, Python `unittest`, React 19, TypeScript, Vite, existing `smart_wrong_questions.py` proxy helpers

---

## Scope Check

The approved spec spans three rollout phases. This plan intentionally implements **Phase 1: Unified Read Path + Admin Mapping Workflow**. It does **not** force all new writes to persist canonical IDs across every producer yet. After this lands and proves stable, write a second plan for Phase 2 write-path hardening.

## File Structure

### SaaS Repo: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary`

- Create: `master_data.py`
  - Owns alias tables, wrong-question mapping tables, candidate suggestion helpers, mapping queue queries, and audit logging.
- Modify: `lesson_manager.py`
  - Registers the new master-data schema during `init_db()` and exposes existing user/class reads needed by `master_data.py`.
- Modify: `smart_wrong_questions.py`
  - Enriches downstream wrong-question records with canonical teacher/class display values plus `mapping_status`.
- Modify: `app.py`
  - Adds admin-only master-data mapping APIs and returns normalized wrong-question records to the frontend.
- Create: `tests/test_master_data_store.py`
  - Covers alias persistence, candidate suggestion, mapping resolution, and audit log writes at the data-layer level.
- Create: `tests/test_master_data_api.py`
  - Covers owner/admin permissions, mapping queue reads, alias updates, and wrong-question mapping resolution via Flask.
- Modify: `tests/test_smart_wrong_questions_api.py`
  - Locks the normalized wrong-question payload shape and mapping status behavior into the existing proxy regression suite.
- Create: `frontend/src/masterDataMappings.ts`
  - Defines frontend types and API wrappers for the mapping queue and resolution actions.
- Create: `frontend/src/MasterDataMappingsPage.tsx`
  - Implements the admin-only mapping queue with candidate confirmation, mapping resolution, and source-name visibility.
- Modify: `frontend/src/App.tsx`
  - Adds one admin-only navigation entry for the new page and threads the page into the existing shell.
- Modify: `frontend/src/workspace-navigation.test.ts`
  - Verifies only `owner` and `admin` see the master-data page.
- Modify: `frontend/src/smartWrongQuestions.ts`
  - Extends the record type to include canonical teacher/class fields and `mappingStatus`.
- Modify: `frontend/src/SmartWrongQuestionsPage.tsx`
  - Displays canonical names, snapshot names, and unresolved-mapping banners without changing the review-save workflow.
- Modify: `frontend/src/smart-wrong-questions.test.ts`
  - Covers normalization of canonical fields and unresolved mapping UI states.
- Create: `frontend/src/master-data-mappings.test.tsx`
  - Covers the new admin page helpers and page-level queue interactions.

### Not In This Plan

- No native mini-program UI rewrite
- No forced downstream mini-backend schema rewrite
- No consultation module migration yet
- No Phase 2 “new writes must persist canonical IDs everywhere” hardening

These boundaries keep the first implementation safe: the SaaS backend becomes the normalization point first, then Phase 2 can tighten write contracts after real records have been reconciled.

### Task 1: Add Central Master-Data Tables And Store Helpers

**Files:**
- Create: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/master_data.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/lesson_manager.py`
- Create: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/tests/test_master_data_store.py`

- [ ] **Step 1: Write a failing store test for alias persistence and wrong-question mapping suggestions**

```python
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lesson_manager
import master_data


class MasterDataStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        lesson_manager.DB_PATH = Path(self.temp_dir.name) / 'lessons.db'
        lesson_manager.init_db()
    self.owner = lesson_manager.get_user_by_username('Kayn')

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_user_alias_round_trip_and_wrong_question_suggestion(self):
        class_id = lesson_manager.save_class('六年级 1 班', subject='数学', grade='六年级')
      lesson_manager.set_class_teacher_user_id(class_id, self.owner['id'])

        master_data.set_user_aliases(
        actor_user_id=self.owner['id'],
        user_id=self.owner['id'],
        aliases=['Kayn 老师', 'Wendy Wang'],
        )
        master_data.set_class_aliases(
        actor_user_id=self.owner['id'],
            class_id=class_id,
            aliases=['六年级1班', 'G6 Math A'],
        )

        suggestion = master_data.suggest_wrong_question_mapping({
            'id': 'record-1',
            'teacher_name': 'Wendy Wang',
            'class_name': '六年级1班',
            'subject': '数学',
        })

        self.assertEqual(suggestion['mapping_status'], 'mapped')
  self.assertEqual(suggestion['teacher_user_id'], self.owner['id'])
        self.assertEqual(suggestion['class_id'], class_id)
  self.assertEqual(suggestion['teacher_display_name'], 'Kayn')
        self.assertEqual(suggestion['class_display_name'], '六年级 1 班')
```

- [ ] **Step 2: Run the new store test to confirm it fails because `master_data.py` and its schema do not exist yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_master_data_store -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'master_data'` or missing helper errors.

- [ ] **Step 3: Add the new schema and focused store helpers in `master_data.py`**

```python
import json
from typing import Any, Iterable, Optional

import lesson_manager


def ensure_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS user_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(user_id, normalized_alias)
        );

        CREATE TABLE IF NOT EXISTS class_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(class_id, normalized_alias)
        );

        CREATE TABLE IF NOT EXISTS wrong_question_mappings (
            record_id TEXT PRIMARY KEY,
            teacher_user_id INTEGER REFERENCES users(id),
            class_id INTEGER REFERENCES classes(id),
            teacher_name_snapshot TEXT DEFAULT '',
            class_name_snapshot TEXT DEFAULT '',
            subject_snapshot TEXT DEFAULT '',
            mapping_status TEXT NOT NULL DEFAULT 'unmapped',
            reviewed_by INTEGER REFERENCES users(id),
            reviewed_at TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS master_data_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            action TEXT NOT NULL,
            before_json TEXT NOT NULL,
            after_json TEXT NOT NULL,
            actor_user_id INTEGER REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        """
    )


def normalize_alias(value: str) -> str:
    return ''.join(str(value or '').strip().lower().split())


def set_user_aliases(*, actor_user_id: int, user_id: int, aliases: Iterable[str]) -> list[str]:
    normalized = sorted({alias.strip() for alias in aliases if alias and alias.strip()})
    with lesson_manager.get_conn() as conn:
        ensure_schema(conn)
        before = list_user_aliases(user_id, conn=conn)
        conn.execute('DELETE FROM user_aliases WHERE user_id=?', (user_id,))
        for alias in normalized:
            conn.execute(
                'INSERT INTO user_aliases (user_id, alias, normalized_alias) VALUES (?, ?, ?)',
                (user_id, alias, normalize_alias(alias)),
            )
        _write_audit_log(
            conn,
            entity_type='user_aliases',
            entity_key=str(user_id),
            action='replace',
            before=before,
            after=normalized,
            actor_user_id=actor_user_id,
        )
    return normalized
```

- [ ] **Step 4: Register the new schema during normal DB initialization**

```python
import master_data


def init_db():
    with get_conn() as conn:
        conn.executescript("""...existing schema...""")
        master_data.ensure_schema(conn)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(lessons)").fetchall()]
        if "class_id" not in cols:
            conn.execute("ALTER TABLE lessons ADD COLUMN class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL")
        _bootstrap_account_state(conn)
```

- [ ] **Step 5: Re-run the focused store test and the existing account regression to confirm the schema integrates cleanly**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_master_data_store tests.test_account_flow -v`

Expected: PASS for the new alias/mapping test and no regression in class/user account flows.

- [ ] **Step 6: Commit the store layer before wiring APIs**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add master_data.py lesson_manager.py tests/test_master_data_store.py
git commit -m "feat: add master data store helpers"
```

### Task 2: Add Admin APIs For Alias Management And Mapping Review

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/app.py`
- Create: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/tests/test_master_data_api.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/master_data.py`

- [ ] **Step 1: Write a failing Flask API test for the mapping queue and resolution endpoint**

```python
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lesson_manager
import master_data
from app import app


class MasterDataApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        lesson_manager.DB_PATH = Path(self.temp_dir.name) / 'lessons.db'
        lesson_manager.init_db()
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def auth_headers(self, token: str) -> dict[str, str]:
        return {'X-Auth-Token': token}

    def login_owner(self) -> str:
        response = self.client.post('/api/login', json={'username': 'Kayn', 'password': 'xingrun2026'})
        return response.get_json()['token']

    def test_owner_can_list_and_resolve_wrong_question_mappings(self):
        owner_token = self.login_owner()
        class_id = lesson_manager.save_class('六年级 1 班', subject='数学', grade='六年级')
        teacher_id = lesson_manager.get_current_user(owner_token)['id']
        lesson_manager.set_class_teacher_user_id(class_id, teacher_id)
        master_data.upsert_wrong_question_mapping(
            actor_user_id=teacher_id,
            record_id='record-1',
            teacher_name_snapshot='Kayn 老师',
            class_name_snapshot='六年级1班',
            subject_snapshot='数学',
            teacher_user_id=None,
            class_id=None,
            mapping_status='needs_review',
        )

        queue_response = self.client.get('/api/master-data/mappings/wrong-questions', headers=self.auth_headers(owner_token))
        self.assertEqual(queue_response.status_code, 200)
        payload = queue_response.get_json()
        self.assertEqual(payload['items'][0]['mapping_status'], 'needs_review')

        resolve_response = self.client.put(
            '/api/master-data/mappings/wrong-questions/record-1',
            headers=self.auth_headers(owner_token),
            json={'teacher_user_id': teacher_id, 'class_id': class_id, 'mapping_status': 'mapped'},
        )
        self.assertEqual(resolve_response.status_code, 200)
        self.assertEqual(resolve_response.get_json()['mapping_status'], 'mapped')
```

- [ ] **Step 2: Run the new Flask API test and confirm it fails because the master-data endpoints do not exist yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_master_data_api -v`

Expected: FAIL with 404 responses for `/api/master-data/mappings/wrong-questions`.

- [ ] **Step 3: Add queue and resolution helpers in `master_data.py` instead of putting SQL in the Flask routes**

```python
def list_wrong_question_mapping_queue(status: Optional[str] = None) -> list[dict[str, Any]]:
    with lesson_manager.get_conn() as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT m.record_id, m.teacher_name_snapshot, m.class_name_snapshot, m.subject_snapshot,
                   m.mapping_status, m.teacher_user_id, m.class_id,
                   u.display_name AS teacher_display_name,
                   c.name AS class_display_name
            FROM wrong_question_mappings m
            LEFT JOIN users u ON u.id = m.teacher_user_id
            LEFT JOIN classes c ON c.id = m.class_id
            WHERE (? IS NULL OR m.mapping_status = ?)
            ORDER BY CASE m.mapping_status WHEN 'needs_review' THEN 0 WHEN 'ambiguous' THEN 1 ELSE 2 END, m.updated_at DESC, m.record_id DESC
            """,
            (status, status),
        ).fetchall()
    return [dict(row) for row in rows]


def resolve_wrong_question_mapping(*, actor_user_id: int, record_id: str, teacher_user_id: Optional[int], class_id: Optional[int], mapping_status: str) -> dict[str, Any]:
    with lesson_manager.get_conn() as conn:
        ensure_schema(conn)
        before = conn.execute('SELECT * FROM wrong_question_mappings WHERE record_id=?', (record_id,)).fetchone()
        conn.execute(
            """
            UPDATE wrong_question_mappings
            SET teacher_user_id=?, class_id=?, mapping_status=?, reviewed_by=?,
                reviewed_at=datetime('now','localtime'), updated_at=datetime('now','localtime')
            WHERE record_id=?
            """,
            (teacher_user_id, class_id, mapping_status, actor_user_id, record_id),
        )
        after = conn.execute('SELECT * FROM wrong_question_mappings WHERE record_id=?', (record_id,)).fetchone()
          if after and teacher_user_id and after['teacher_name_snapshot']:
            merge_user_alias(conn, user_id=teacher_user_id, alias=after['teacher_name_snapshot'])
          if after and class_id and after['class_name_snapshot']:
            merge_class_alias(conn, class_id=class_id, alias=after['class_name_snapshot'])
        _write_audit_log(conn, 'wrong_question_mapping', record_id, 'resolve', dict(before or {}), dict(after or {}), actor_user_id)
        return dict(after)
```

- [ ] **Step 4: Add admin-only Flask routes for aliases and the wrong-question mapping queue**

```python
import master_data


@app.route('/api/master-data/mappings/wrong-questions', methods=['GET'])
def api_master_data_wrong_question_queue():
    user = require_role('owner', 'admin')
    if user is None:
        return jsonify({'error': '无权限'}), 403
    status = (request.args.get('status') or '').strip() or None
    return jsonify({'items': master_data.list_wrong_question_mapping_queue(status=status)})


@app.route('/api/master-data/mappings/wrong-questions/<record_id>', methods=['PUT'])
def api_master_data_wrong_question_resolve(record_id):
    user = require_role('owner', 'admin')
    if user is None:
        return jsonify({'error': '无权限'}), 403
    payload = request.json or {}
    resolved = master_data.resolve_wrong_question_mapping(
        actor_user_id=user['id'],
        record_id=record_id,
        teacher_user_id=payload.get('teacher_user_id'),
        class_id=payload.get('class_id'),
        mapping_status=payload.get('mapping_status', 'mapped'),
    )
    return jsonify(resolved)
```

- [ ] **Step 5: Re-run the API tests plus the existing wrong-question backend suite to verify permissions and payload shape**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_master_data_api tests.test_smart_wrong_questions_api -v`

Expected: PASS for the new queue workflow and no regression in existing wrong-question proxy routes.

- [ ] **Step 6: Commit the admin API layer**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add app.py master_data.py tests/test_master_data_api.py tests/test_smart_wrong_questions_api.py
git commit -m "feat: add master data mapping api"
```

### Task 3: Normalize Wrong-Question Records Through The Mapping Layer

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/master_data.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/smart_wrong_questions.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/tests/test_smart_wrong_questions_api.py`

- [ ] **Step 1: Extend the existing wrong-question backend tests to demand canonical fields and mapping status**

```python
    @patch('smart_wrong_questions.fetch_wrong_question_records')
    def test_staff_list_payload_exposes_canonical_teacher_and_mapping_status(self, fetch_wrong_question_records):
        owner_payload = self.login_owner()
        fetch_wrong_question_records.return_value = {
            'items': [
                {
                    'id': 'record-1',
                    'teacher_name': 'Kayn 老师',
                    'class_name': '六年级1班',
                    'subject': '数学',
                    'student_name': 'Alice',
                    'mapping_status': 'needs_review',
                    'teacher_display_name': 'Kayn',
                    'class_display_name': '六年级 1 班',
                }
            ],
            'total': 1,
        }

        response = self.client.get('/api/wrong-questions', headers=self.auth_headers(owner_payload['token']))

        self.assertEqual(response.status_code, 200)
        item = response.get_json()['items'][0]
        self.assertEqual(item['teacher_display_name'], 'Kayn')
        self.assertEqual(item['class_display_name'], '六年级 1 班')
        self.assertEqual(item['mapping_status'], 'needs_review')
        self.assertEqual(item['teacher_name_snapshot'], 'Kayn 老师')
```

- [ ] **Step 2: Run the focused wrong-question test file and confirm it fails because canonical fields are not being injected yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_smart_wrong_questions_api -v`

Expected: FAIL with missing keys like `teacher_display_name` or `mapping_status`.

- [ ] **Step 3: Add one normalization helper that creates or reuses a mapping row and returns the enriched record**

```python
def normalize_wrong_question_record(raw_record: dict[str, Any]) -> dict[str, Any]:
    suggestion = suggest_wrong_question_mapping(raw_record)
    existing = get_wrong_question_mapping(str(raw_record.get('id') or ''))
    mapping = existing or upsert_wrong_question_mapping(
        actor_user_id=None,
        record_id=str(raw_record.get('id') or ''),
        teacher_name_snapshot=str(raw_record.get('teacher_name') or raw_record.get('teacherName') or ''),
        class_name_snapshot=str(raw_record.get('class_name') or raw_record.get('className') or ''),
        subject_snapshot=str(raw_record.get('subject') or ''),
        teacher_user_id=suggestion.get('teacher_user_id'),
        class_id=suggestion.get('class_id'),
        mapping_status=suggestion.get('mapping_status', 'unmapped'),
    )

    normalized = dict(raw_record)
    normalized['teacher_display_name'] = mapping.get('teacher_display_name') or mapping.get('teacher_name_snapshot') or ''
    normalized['teacher_name_snapshot'] = mapping.get('teacher_name_snapshot') or ''
    normalized['class_display_name'] = mapping.get('class_display_name') or mapping.get('class_name_snapshot') or ''
    normalized['class_name_snapshot'] = mapping.get('class_name_snapshot') or ''
    normalized['mapping_status'] = mapping.get('mapping_status', 'unmapped')
    normalized['teacher_user_id'] = mapping.get('teacher_user_id')
    normalized['class_id'] = mapping.get('class_id')
    return normalized
```

- [ ] **Step 4: Use the normalization helper inside `smart_wrong_questions.py` list and detail responses**

```python
import master_data


def fetch_wrong_question_records(query):
    payload = _request_downstream('/wrong-questions', query=query)
    items = payload.get('items') or []
    payload['items'] = [master_data.normalize_wrong_question_record(item) for item in items]
    return payload


def fetch_wrong_question_record(record_id, query):
    payload = _request_downstream(f'/wrong-questions/{_quote_record_id(record_id)}', query=query)
    return master_data.normalize_wrong_question_record(payload)
```

- [ ] **Step 5: Re-run backend regression to prove normalized wrong-question payloads stay stable**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_master_data_store tests.test_master_data_api tests.test_smart_wrong_questions_api -v`

Expected: PASS for store, API, and wrong-question normalization coverage.

- [ ] **Step 6: Commit the read-path normalization**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add master_data.py smart_wrong_questions.py tests/test_smart_wrong_questions_api.py
git commit -m "feat: normalize wrong question master data"
```

### Task 4: Add The Admin Mapping Queue Page In The SaaS Shell

**Files:**
- Create: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/masterDataMappings.ts`
- Create: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/MasterDataMappingsPage.tsx`
- Create: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/master-data-mappings.test.tsx`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/App.tsx`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Write a failing frontend test that demands an admin-only mapping page and queue fetch**

```tsx
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';

import { MasterDataMappingsPage } from './MasterDataMappingsPage';

test('master data page source keeps admin-only queue actions wired', async () => {
  const source = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');
  assert.match(source, /masterDataMappings/);
  assert.match(source, /主数据映射/);
});

test('mapping queue page renders unresolved records', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({
    items: [
      {
        record_id: 'record-1',
        teacher_name_snapshot: 'Kayn 老师',
        class_name_snapshot: '六年级1班',
        subject_snapshot: '数学',
        mapping_status: 'needs_review',
      },
    ],
  })) as typeof fetch;

  render(<MasterDataMappingsPage currentUser={{ id: 1, role: 'admin', display_name: 'Admin' } as never} />);

  await waitFor(() => {
    assert.equal(screen.getByText('record-1').textContent, 'record-1');
  });
});
```

- [ ] **Step 2: Run the new frontend test and confirm it fails because the page and navigation branch do not exist yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/master-data-mappings.test.tsx src/workspace-navigation.test.ts`

Expected: FAIL with import errors for `MasterDataMappingsPage` and missing `masterDataMappings` page wiring.

- [ ] **Step 3: Add a small API helper module for the queue and resolve action**

```ts
export interface WrongQuestionMappingQueueItem {
  recordId: string;
  teacherNameSnapshot: string;
  classNameSnapshot: string;
  subjectSnapshot: string;
  mappingStatus: 'mapped' | 'unmapped' | 'ambiguous' | 'needs_review';
  teacherUserId?: number;
  classId?: number;
  teacherDisplayName?: string;
  classDisplayName?: string;
}

export async function fetchWrongQuestionMappingQueue(): Promise<WrongQuestionMappingQueueItem[]> {
  const response = await fetch('/api/master-data/mappings/wrong-questions');
  if (!response.ok) {
    throw new Error('Failed to load master data mapping queue');
  }
  const payload = await response.json() as { items?: unknown[] };
  return (payload.items ?? []).map(normalizeWrongQuestionMappingQueueItem);
}

export async function resolveWrongQuestionMapping(recordId: string, payload: { teacherUserId?: number; classId?: number; mappingStatus: string }) {
  const response = await fetch(`/api/master-data/mappings/wrong-questions/${encodeURIComponent(recordId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      teacher_user_id: payload.teacherUserId ?? null,
      class_id: payload.classId ?? null,
      mapping_status: payload.mappingStatus,
    }),
  });
  if (!response.ok) {
    throw new Error('Failed to resolve wrong question mapping');
  }
  return response.json();
}
```

- [ ] **Step 4: Add the admin-only page and shell navigation branch**

```tsx
type Page =
  | 'dashboard'
  | 'classes'
  | 'review-generation'
  | 'smartWrongQuestions'
  | 'masterDataMappings';

{(currentUser.role === 'owner' || currentUser.role === 'admin') && (
  <button onClick={() => setActivePage('masterDataMappings')}>
    主数据映射
  </button>
)}

{activePage === 'masterDataMappings' && <MasterDataMappingsPage currentUser={currentUser} />}
```

- [ ] **Step 5: Re-run the focused frontend suite and confirm the admin page is reachable only for owner/admin**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/master-data-mappings.test.tsx src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: PASS with the new page source checks and queue-render coverage.

- [ ] **Step 6: Commit the admin mapping page**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/masterDataMappings.ts frontend/src/MasterDataMappingsPage.tsx frontend/src/master-data-mappings.test.tsx frontend/src/App.tsx frontend/src/workspace-navigation.test.ts
git commit -m "feat: add master data mapping queue page"
```

### Task 5: Show Canonical Names And Mapping Status Inside 智能错题

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/smartWrongQuestions.ts`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/SmartWrongQuestionsPage.tsx`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/smart-wrong-questions.test.ts`

- [ ] **Step 1: Write a failing frontend helper test for canonical teacher/class fields and unresolved status messaging**

```ts
test('normalizeWrongQuestionRecord keeps canonical and snapshot identity side by side', () => {
  const record = normalizeWrongQuestionRecord({
    id: 'record-1',
    student_name: 'Alice',
    teacher_name: 'Kayn 老师',
    teacher_display_name: 'Kayn',
    class_name: '六年级1班',
    class_display_name: '六年级 1 班',
    mapping_status: 'needs_review',
    subject: '数学',
    analysis: {},
  });

  assert.equal(record.teacherName, 'Kayn');
  assert.equal(record.teacherNameSnapshot, 'Kayn 老师');
  assert.equal(record.className, '六年级 1 班');
  assert.equal(record.classNameSnapshot, '六年级1班');
  assert.equal(record.mappingStatus, 'needs_review');
});
```

- [ ] **Step 2: Run the smart-wrong-questions test file and confirm it fails because the extended fields do not exist yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/smart-wrong-questions.test.ts`

Expected: FAIL with missing properties such as `teacherNameSnapshot` and `mappingStatus`.

- [ ] **Step 3: Extend the wrong-question frontend model to carry canonical and snapshot identity separately**

```ts
export interface WrongQuestionRecord {
  id: string;
  studentName: string;
  className: string;
  classNameSnapshot: string;
  classId?: number;
  subject: string;
  teacherName: string;
  teacherNameSnapshot: string;
  teacherUserId?: number;
  mappingStatus: 'mapped' | 'unmapped' | 'ambiguous' | 'needs_review';
  createdAt: string;
  imageUrl?: string;
  analysis: WrongQuestionAnalysis;
}

export function normalizeWrongQuestionRecord(rawRecord: unknown, fallbackIndex = 0): WrongQuestionRecord {
  const source = isObjectRecord(rawRecord) ? rawRecord : {};
  return {
    id: typeof source.id === 'string' || typeof source.id === 'number' ? String(source.id) : `wrong-question-${fallbackIndex}`,
    studentName: pickStringValue(source, ['studentName', 'student_name', 'studentNickname', 'student_nickname']),
    className: pickStringValue(source, ['classDisplayName', 'class_display_name', 'className', 'class_name']),
    classNameSnapshot: pickStringValue(source, ['classNameSnapshot', 'class_name_snapshot', 'className', 'class_name']),
    classId: pickNumberValue(source, ['classId', 'class_id']) ?? undefined,
    subject: pickStringValue(source, ['subject']),
    teacherName: pickStringValue(source, ['teacherDisplayName', 'teacher_display_name', 'teacherName', 'teacher_name']),
    teacherNameSnapshot: pickStringValue(source, ['teacherNameSnapshot', 'teacher_name_snapshot', 'teacherName', 'teacher_name']),
    teacherUserId: pickNumberValue(source, ['teacherUserId', 'teacher_user_id']) ?? undefined,
    mappingStatus: (pickStringValue(source, ['mappingStatus', 'mapping_status']) || 'unmapped') as WrongQuestionRecord['mappingStatus'],
    createdAt: pickStringValue(source, ['createdAt', 'created_at']),
    imageUrl: pickStringValue(source, ['imageUrl', 'image_url']) || undefined,
    analysis: normalizeWrongQuestionAnalysis(source.analysis),
  };
}
```

- [ ] **Step 4: Surface the canonical-vs-snapshot distinction and unresolved banner in `SmartWrongQuestionsPage.tsx`**

```tsx
{selectedRecord.mappingStatus !== 'mapped' && (
  <div className="rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
    这条记录的老师或班级还没有完成主数据映射，当前优先展示标准名称，同时保留原始提交名称供核对。
  </div>
)}

<div className="grid gap-3 md:grid-cols-2">
  <div>
    <span className="text-slate-500">老师</span>
    <p className="font-semibold text-slate-900">{selectedRecord.teacherName || '待映射'}</p>
    {selectedRecord.teacherNameSnapshot && selectedRecord.teacherNameSnapshot !== selectedRecord.teacherName && (
      <p className="text-xs text-slate-500">原始名称：{selectedRecord.teacherNameSnapshot}</p>
    )}
  </div>
  <div>
    <span className="text-slate-500">班级</span>
    <p className="font-semibold text-slate-900">{selectedRecord.className || '待映射'}</p>
    {selectedRecord.classNameSnapshot && selectedRecord.classNameSnapshot !== selectedRecord.className && (
      <p className="text-xs text-slate-500">原始名称：{selectedRecord.classNameSnapshot}</p>
    )}
  </div>
</div>
```

- [ ] **Step 5: Run the focused frontend regression, then the full frontend safety checks**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/smart-wrong-questions.test.ts src/master-data-mappings.test.tsx src/workspace-navigation.test.ts src/account-card.test.tsx && npm run lint && npm run build`

Expected: PASS for helper and page tests, `tsc --noEmit`, and the production build. Existing chunk-size warnings may remain non-blocking.

- [ ] **Step 6: Commit the wrong-question UI normalization**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/smartWrongQuestions.ts frontend/src/SmartWrongQuestionsPage.tsx frontend/src/smart-wrong-questions.test.ts
git commit -m "feat: surface canonical wrong question identities"
```

### Task 6: Final Verification And Documentation Cleanup

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/handoff.md`
- Optional docs-only touch if behavior changed during implementation: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/docs/superpowers/specs/2026-03-30-master-data-unification-design.md`

- [ ] **Step 1: Run the backend verification bundle from a temporary script so proof is copyable**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
tmp_script=$(mktemp)
printf '%s\n' \
  '#!/bin/zsh' \
  'set -e' \
  '/Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_master_data_store tests.test_master_data_api tests.test_smart_wrong_questions_api tests.test_account_flow -v' \
  > "$tmp_script"
chmod +x "$tmp_script"
"$tmp_script"
rm "$tmp_script"
```

Expected: PASS for the new master-data suites and the existing account/wrong-question regressions.

- [ ] **Step 2: Run the frontend verification bundle from a temporary script so proof is copyable**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend
tmp_script=$(mktemp)
printf '%s\n' \
  '#!/bin/zsh' \
  'set -e' \
  'npx tsx --test src/master-data-mappings.test.tsx src/smart-wrong-questions.test.ts src/workspace-navigation.test.ts src/account-card.test.tsx' \
  'npm run lint' \
  'npm run build' \
  > "$tmp_script"
chmod +x "$tmp_script"
"$tmp_script"
rm "$tmp_script"
```

Expected: PASS for the focused React tests, TypeScript check, and build.

- [ ] **Step 3: Update `handoff.md` with completed master-data phase-1 scope, proof commands, and any deferred Phase 2 write-path work**

```md
补充记录（2026-03-30，主数据统一 phase 1 完成）
- 已上线范围：主数据 alias/mapping 存储层、admin 映射队列、智能错题 canonical 展示
- 未完成范围：Phase 2 新写入强约束、mini backend 持久化 canonical id、咨询模块接入
- proof：
  - backend unittest bundle 通过
  - frontend focused tests / lint / build 通过
```

- [ ] **Step 4: Commit any repo-scoped follow-up docs, but do not try to commit `handoff.md` from inside the repo**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git status --short
# handoff.md lives outside this git repo, so update it but do not stage it here.
if git status --short docs/superpowers/specs/2026-03-30-master-data-unification-design.md | grep -q .; then
  git add docs/superpowers/specs/2026-03-30-master-data-unification-design.md
  git commit -m "docs: sync master data phase 1 notes"
fi
```

## Self-Review Checklist

- Spec coverage: Phase 1 requirements are covered by Task 1 store/schema, Task 2 admin APIs, Task 3 read-path normalization, Task 4 admin queue UI, and Task 5 wrong-question display updates.
- Placeholder scan: This plan intentionally avoids `TODO`, `TBD`, and “handle appropriately” filler; each task names exact files, commands, and target code.
- Type consistency: Backend uses `teacher_user_id`, `class_id`, and `mapping_status`; frontend consumes the same fields as `teacherUserId`, `classId`, and `mappingStatus` via explicit normalization.
