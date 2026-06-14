# Smart Wrong Questions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an internal-only `智能错题` tab to the SaaS workspace so owners and admins can review wrong-question records, save teacher follow-up selections, and export PDF summaries while parents continue using the mini program entry.

**Architecture:** Keep the parent-facing mini program and its Node backend as the source of wrong-question records, but stop exposing that backend directly to the browser. Add a small SaaS-side proxy layer in Flask that validates existing `X-Auth-Token` sessions and forwards list/detail/review/export requests downstream. On the frontend, keep the current Vite + React workspace shell, add one new sidebar page, and implement the wrong-question UI in a dedicated component rather than expanding `App.tsx` further.

**Tech Stack:** Flask, Python `unittest`, standard-library `urllib`, React 19, TypeScript, Vite, Node `test`, Express

---

## File Structure

### SaaS Repo: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary`

- Create: `smart_wrong_questions.py`
  - Owns downstream service config, HTTP forwarding, payload normalization, and exported helpers for the Flask routes.
- Modify: `config_runtime.py`
  - Adds runtime config keys for downstream mini program backend base URL and teacher token.
- Modify: `app.py`
  - Adds authenticated internal `/api/wrong-questions*` routes and wires them to `smart_wrong_questions.py`.
- Create: `tests/test_smart_wrong_questions_api.py`
  - Covers auth, role gating, list/detail mapping, review save, and export proxy behavior.
- Create: `frontend/src/SmartWrongQuestionsPage.tsx`
  - Implements the workspace-native page UI, summary cards, filters, record list, detail panel, save flow, and export action.
- Create: `frontend/src/smartWrongQuestions.ts`
  - Defines frontend types, summary helpers, filter-query builder, and lightweight API wrappers.
- Create: `frontend/src/smart-wrong-questions.test.ts`
  - Covers pure helpers such as summary-card counts and filter query serialization.
- Modify: `frontend/src/App.tsx`
  - Adds the new page type, sidebar item, header title, and render branch for `智能错题`.
- Modify: `frontend/src/workspace-navigation.test.ts`
  - Locks the new tab into the workspace shell and verifies role-based visibility wiring.

### Mini Program Repo: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend`

- Modify: `src/index.ts`
  - Exports `createApp()`, keeps the current runtime startup, and adds one teacher-review save route.
- Create: `src/teacher-records.test.ts`
  - Covers the new teacher-review route and the existing list/PDF teacher APIs using a started app on an ephemeral port.

These boundaries keep the proxy logic, UI logic, and downstream service logic separate so future migration work can replace one layer at a time.

### Task 1: Add The Missing Downstream Teacher-Review Route In The Mini Program Backend

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend/src/index.ts`
- Create: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend/src/teacher-records.test.ts`

- [ ] **Step 1: Write a failing downstream test that proves teachers can update review selections through HTTP**

```ts
import test from 'node:test';
import assert from 'node:assert/strict';
import type { AddressInfo } from 'node:net';

import { createApp } from './index';
import { saveFeedback } from './feedback';

test('teacher selections endpoint updates a saved record', async () => {
  const roomId = 'ROOMX';
  const recordId = 'record-1';

  saveFeedback(roomId, {
    id: recordId,
    from: '家长A',
    studentNickname: '学生A',
    teacherName: '老师A',
    className: '六年级 1 班',
    subject: '数学',
    status: '有问题',
    note: '原始备注',
    imageUrl: 'http://localhost/files/example.png',
    time: '20:10',
    analysis: {
      questionCategory: '数学',
      errorType: '计算错误',
      knowledgePoints: ['分数运算'],
      isRepeatedMistake: '待确认',
      nextSteps: ['重做同类题'],
      teacherPriority: '待确认',
    },
  });

  const app = createApp();
  const server = app.listen(0);
  const port = (server.address() as AddressInfo).port;

  try {
    const response = await fetch(
      `http://127.0.0.1:${port}/api/teacher/records/${recordId}/selections?token=xingrun2024&roomId=${roomId}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          selectedErrorType: '审题问题',
          selectedKnowledgePoints: ['分数运算', '应用题条件提取'],
          selectedActions: ['需要复讲'],
          selectedReasons: ['步骤跳跃'],
          studentNote: '已要求重做',
        }),
      },
    );

    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.analysis.selectedErrorType, '审题问题');
    assert.deepEqual(payload.analysis.selectedKnowledgePoints, ['分数运算', '应用题条件提取']);
    assert.deepEqual(payload.analysis.selectedActions, ['需要复讲']);
    assert.equal(payload.analysis.studentNote, '已要求重做');
  } finally {
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
});
```

- [ ] **Step 2: Run the downstream Node test and confirm it fails because `createApp()` and the new route do not exist yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend && node --test --import tsx src/teacher-records.test.ts`

Expected: FAIL with import or 404 errors for `createApp` and `/api/teacher/records/:recordId/selections`.

- [ ] **Step 3: Refactor the downstream backend entry so the Express app can be imported by tests**

```ts
export function createApp() {
  const app = express();
  app.use(express.json());
  app.use('/files', express.static(path.join(__dirname, '../../uploads')));

  app.get('/healthz', (_req, res) => {
    res.json({ ok: true, service: 'openclaw-wechat-bridge', timestamp: Date.now() });
  });

  // keep existing routes here

  return app;
}

const app = createApp();
const server = createServer(app);

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  server.listen(PORT, () => {
    console.log(`OpenClaw bridge listening on ${PORT}`);
  });
}
```

- [ ] **Step 4: Add the teacher-review save route that uses the existing `updateFeedbackSelections()` helper**

```ts
app.put('/api/teacher/records/:recordId/selections', (req, res) => {
  if (!checkTeacherToken(req.query.token)) {
    res.status(401).json({ error: 'unauthorized' });
    return;
  }

  const roomId = String(req.query.roomId || DEFAULT_ROOM_ID).toUpperCase();
  const recordId = String(req.params.recordId || '').trim();
  if (!recordId) {
    res.status(400).json({ error: 'recordId required' });
    return;
  }

  const updated = updateFeedbackSelections(roomId, recordId, {
    selectedErrorType: String(req.body?.selectedErrorType ?? '').trim(),
    selectedKnowledgePoints: Array.isArray(req.body?.selectedKnowledgePoints) ? req.body.selectedKnowledgePoints : [],
    knowledgePointConfirmed: Boolean(req.body?.knowledgePointConfirmed),
    selectedActions: Array.isArray(req.body?.selectedActions) ? req.body.selectedActions : [],
    selectedReasons: Array.isArray(req.body?.selectedReasons) ? req.body.selectedReasons : [],
    studentNote: String(req.body?.studentNote ?? '').trim(),
  });

  if (!updated) {
    res.status(404).json({ error: 'record not found' });
    return;
  }
  res.json(updated);
});
```

- [ ] **Step 5: Re-run the downstream Node test and confirm it passes**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend && node --test --import tsx src/teacher-records.test.ts`

Expected: PASS with the new teacher-review save route returning the updated record payload.

- [ ] **Step 6: Commit the downstream backend contract**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram
git add backend/src/index.ts backend/src/teacher-records.test.ts
git commit -m "feat: add teacher wrong question review api"
```

### Task 2: Add The SaaS Proxy Layer And Lock It With Backend Tests

**Files:**
- Create: `smart_wrong_questions.py`
- Modify: `config_runtime.py`
- Modify: `app.py`
- Create: `tests/test_smart_wrong_questions_api.py`

- [ ] **Step 1: Write a failing Flask test file for role gating and downstream proxy mapping**

```python
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager
from app import app


class SmartWrongQuestionsApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        lesson_manager.DB_PATH = Path(self.temp_dir.name) / 'lessons.db'
        config_runtime.CFG_PATH = Path(self.temp_dir.name) / 'config.json'
        config_runtime.write_file_config({
            'wrong_question_service_url': 'http://wrong-question-service.local',
            'wrong_question_service_token': 'teacher-token-1',
        })
        lesson_manager.init_db()
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {'X-Auth-Token': token}

    def login_owner(self) -> str:
        response = self.client.post('/api/login', json={'username': 'Kayn', 'password': 'xingrun2026'})
        self.assertEqual(response.status_code, 200)
        return response.get_json()['token']

    def test_member_cannot_access_wrong_question_routes(self):
        owner_token = self.login_owner()
        self.client.post('/api/register-request', json={
            'username': 'member_wrong_question',
            'display_name': 'Member Wrong Question',
            'password': 'member123',
            'organization_name': '星润Starain',
        })
        pending = self.client.get('/api/admin/registration-requests', headers=self.auth_headers(owner_token)).get_json()
        request_id = pending['items'][0]['id']
        self.client.post(f'/api/admin/registration-requests/{request_id}/approve', headers=self.auth_headers(owner_token))
        member_login = self.client.post('/api/login', json={'username': 'member_wrong_question', 'password': 'member123'})
        member_token = member_login.get_json()['token']

        response = self.client.get('/api/wrong-questions', headers=self.auth_headers(member_token))
        self.assertEqual(response.status_code, 403)

    @patch('smart_wrong_questions.fetch_wrong_question_records')
    def test_staff_can_list_wrong_question_records(self, fetch_wrong_question_records):
        owner_token = self.login_owner()
        fetch_wrong_question_records.return_value = {
            'items': [
                {
                    'id': 'record-1',
                    'studentName': '学生A',
                    'subject': '数学',
                    'status': '有问题',
                    'teacherPriority': '需要复讲',
                    'time': '20:10',
                }
            ],
            'summary': {'todayCount': 1, 'pendingCount': 1, 'reteachCount': 1, 'followUpCount': 0},
        }

        response = self.client.get('/api/wrong-questions', headers=self.auth_headers(owner_token))
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['items'][0]['studentName'], '学生A')
        self.assertEqual(payload['summary']['reteachCount'], 1)
```

- [ ] **Step 2: Run the new Flask tests and confirm they fail because the proxy module and routes do not exist yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_smart_wrong_questions_api -v`

Expected: FAIL with import errors or missing `/api/wrong-questions` routes.

- [ ] **Step 3: Add runtime config keys for the downstream service URL and teacher token**

```python
ENV_VAR_MAP = {
    'provider': 'XR_PROVIDER',
    'openai_api_key': 'OPENAI_API_KEY',
    'deepseek_api_key': 'DEEPSEEK_API_KEY',
    'qwen_api_key': 'DASHSCOPE_API_KEY',
    'qwen_base_url': 'XR_QWEN_BASE_URL',
    'vision_model': 'XR_VISION_MODEL',
    'admin_username': 'XR_ADMIN_USERNAME',
    'admin_password_hash': 'XR_ADMIN_PASSWORD_HASH',
    'wrong_question_service_url': 'XR_WRONG_QUESTION_SERVICE_URL',
    'wrong_question_service_token': 'XR_WRONG_QUESTION_SERVICE_TOKEN',
}

DEFAULTS = {
    'provider': 'openai',
    'qwen_base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'vision_model': 'qwen-vl-max-latest',
    'deepseek_model': 'deepseek-chat',
    'wrong_question_service_url': '',
    'wrong_question_service_token': '',
}
```

- [ ] **Step 4: Add a focused proxy helper module that uses `urllib` and normalizes downstream responses**

```python
from __future__ import annotations

import json
from typing import Any
from urllib import error, parse, request

from config_runtime import get_runtime_config


class WrongQuestionProxyError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _service_config() -> tuple[str, str]:
    cfg = get_runtime_config()
    base_url = str(cfg.get('wrong_question_service_url', '')).strip().rstrip('/')
    token = str(cfg.get('wrong_question_service_token', '')).strip()
    if not base_url or not token:
        raise WrongQuestionProxyError('智能错题服务尚未配置', 503)
    return base_url, token


def _request_json(path: str, *, method: str = 'GET', query: dict[str, Any] | None = None, payload: dict[str, Any] | None = None, expect_binary: bool = False):
    base_url, token = _service_config()
    query = {k: v for k, v in (query or {}).items() if v not in (None, '', [])}
    query['token'] = token
    url = f"{base_url}{path}"
    if query:
        url = f"{url}?{parse.urlencode(query, doseq=True)}"

    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    req = request.Request(url, method=method, data=body, headers=headers)
    try:
        with request.urlopen(req, timeout=20) as response:
            raw = response.read()
            if expect_binary:
                return raw, response.headers.get_content_type()
            return json.loads(raw.decode('utf-8')) if raw else {}
    except error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise WrongQuestionProxyError(detail or '下游服务请求失败', exc.code) from exc
    except error.URLError as exc:
        raise WrongQuestionProxyError(f'下游服务不可用: {exc.reason}', 502) from exc
```

- [ ] **Step 5: Add internal Flask routes that reuse existing staff auth helpers and call the proxy module**

```python
from smart_wrong_questions import (
    WrongQuestionProxyError,
    export_wrong_question_summary,
    fetch_wrong_question_record,
    fetch_wrong_question_records,
    save_wrong_question_review,
)


@app.route('/api/wrong-questions', methods=['GET'])
def api_wrong_questions_list():
    _, error = _require_staff()
    if error:
        return error
    try:
        return jsonify(fetch_wrong_question_records(request.args))
    except WrongQuestionProxyError as exc:
        return jsonify({'error': str(exc)}), exc.status_code


@app.route('/api/wrong-questions/<record_id>', methods=['GET'])
def api_wrong_question_detail(record_id):
    _, error = _require_staff()
    if error:
        return error
    try:
        return jsonify(fetch_wrong_question_record(record_id, request.args))
    except WrongQuestionProxyError as exc:
        return jsonify({'error': str(exc)}), exc.status_code


@app.route('/api/wrong-questions/<record_id>/review', methods=['PUT'])
def api_wrong_question_review_save(record_id):
    _, error = _require_staff()
    if error:
        return error
    try:
        return jsonify(save_wrong_question_review(record_id, request.args, request.json or {}))
    except WrongQuestionProxyError as exc:
        return jsonify({'error': str(exc)}), exc.status_code
```

- [ ] **Step 6: Add the export route that returns a PDF download instead of JSON**

```python
@app.route('/api/wrong-questions/summary/export', methods=['GET'])
def api_wrong_question_summary_export():
    _, error = _require_staff()
    if error:
        return error
    try:
        pdf_bytes, filename = export_wrong_question_summary(request.args)
    except WrongQuestionProxyError as exc:
        return jsonify({'error': str(exc)}), exc.status_code
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )
```

- [ ] **Step 7: Re-run the Flask proxy tests and confirm they pass**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_smart_wrong_questions_api -v`

Expected: PASS with owners/staff allowed, members denied, and downstream payloads surfaced through `/api/wrong-questions*`.

- [ ] **Step 8: Commit the SaaS proxy layer**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add config_runtime.py app.py smart_wrong_questions.py tests/test_smart_wrong_questions_api.py
git commit -m "feat: add smart wrong questions proxy api"
```

### Task 3: Add The Workspace Tab And Smart Wrong Questions Page With Frontend Red Tests First

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/SmartWrongQuestionsPage.tsx`
- Create: `frontend/src/smartWrongQuestions.ts`
- Create: `frontend/src/smart-wrong-questions.test.ts`
- Modify: `frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Write a failing workspace-navigation assertion that locks the new tab into the shell**

```ts
test('workspace navigation wires smart wrong questions into owner and admin shells', () => {
  assert.match(appSource, /type Page = 'dashboard' \| 'input' \| 'library' \| 'consultation' \| 'calendar' \| 'classes' \| 'smartWrongQuestions' \| 'accounts' \| 'settings';/);
  assert.match(appSource, /currentUser\.role === 'owner' \|\| currentUser\.role === 'admin'[\s\S]*id: 'smartWrongQuestions'[\s\S]*label: '智能错题'/);
  assert.match(appSource, /smartWrongQuestions: '智能错题'/);
  assert.match(appSource, /activePage === 'smartWrongQuestions'[\s\S]*<SmartWrongQuestionsPage currentUser=\{currentUser\}/);
});
```

- [ ] **Step 2: Write a failing pure-helper test for summary counts and filter serialization**

```ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { buildWrongQuestionQuery, summarizeWrongQuestionRecords } from './smartWrongQuestions';

test('summarizeWrongQuestionRecords counts pending reteach and follow-up records', () => {
  const summary = summarizeWrongQuestionRecords([
    { id: '1', status: '有问题', analysis: { teacherPriority: '需要复讲' } },
    { id: '2', status: '未完成', analysis: { teacherPriority: '需要单独跟进' } },
  ] as any);

  assert.equal(summary.todayCount, 2);
  assert.equal(summary.pendingCount, 2);
  assert.equal(summary.reteachCount, 1);
  assert.equal(summary.followUpCount, 1);
});

test('buildWrongQuestionQuery serializes only active filters', () => {
  assert.equal(
    buildWrongQuestionQuery({ studentName: '学生A', subject: '数学', status: '' }),
    'studentName=%E5%AD%A6%E7%94%9FA&subject=%E6%95%B0%E5%AD%A6',
  );
});
```

- [ ] **Step 3: Run the focused frontend tests and confirm they fail because the new page and helpers do not exist yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/smart-wrong-questions.test.ts`

Expected: FAIL on missing `smartWrongQuestions` page wiring and missing helper module exports.

- [ ] **Step 4: Add a small frontend helper module for types, summary cards, and query building**

```ts
export type WrongQuestionAnalysis = {
  teacherPriority?: '普通' | '需要复讲' | '需要单独跟进' | '待确认';
  selectedErrorType?: string;
  selectedKnowledgePoints?: string[];
  selectedActions?: string[];
  selectedReasons?: string[];
  studentNote?: string;
};

export type WrongQuestionRecord = {
  id: string;
  studentName: string;
  className?: string;
  subject: string;
  status: string;
  time: string;
  note?: string;
  imageUrl?: string;
  analysis?: WrongQuestionAnalysis;
};

export function summarizeWrongQuestionRecords(records: WrongQuestionRecord[]) {
  return {
    todayCount: records.length,
    pendingCount: records.filter((item) => item.status !== '已完成').length,
    reteachCount: records.filter((item) => item.analysis?.teacherPriority === '需要复讲').length,
    followUpCount: records.filter((item) => item.analysis?.teacherPriority === '需要单独跟进').length,
  };
}

export function buildWrongQuestionQuery(filters: Record<string, string>) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value.trim()) params.set(key, value.trim());
  });
  return params.toString();
}
```

- [ ] **Step 5: Implement the new page component as a dedicated workspace module**

```tsx
export function SmartWrongQuestionsPage({ currentUser }: { currentUser: CurrentUser }) {
  const [filters, setFilters] = useState({ studentName: '', className: '', subject: '', status: '', teacherPriority: '' });
  const [items, setItems] = useState<WrongQuestionRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string>('');
  const [detail, setDetail] = useState<WrongQuestionRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadList = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const query = buildWrongQuestionQuery(filters);
      const payload = await apiFetch<{ items: WrongQuestionRecord[] }>(`/api/wrong-questions${query ? `?${query}` : ''}`);
      setItems(payload.items || []);
      if (!selectedId && payload.items?.length) {
        setSelectedId(payload.items[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '智能错题列表加载失败');
    } finally {
      setLoading(false);
    }
  }, [filters, selectedId]);

  useEffect(() => {
    loadList().catch(() => undefined);
  }, [loadList]);

  return <div className={workspacePageClass}>{/* summary cards, filters, list, detail */}</div>;
}
```

- [ ] **Step 6: Wire the new page into the existing workspace shell**

```ts
type Page = 'dashboard' | 'input' | 'library' | 'consultation' | 'calendar' | 'classes' | 'smartWrongQuestions' | 'accounts' | 'settings';
```

```ts
...(currentUser.role === 'owner' || currentUser.role === 'admin'
  ? [{ id: 'smartWrongQuestions', icon: AlertCircle, label: '智能错题' }]
  : []),
```

```ts
const pageTitle: Record<Page, string> = {
  dashboard: '工作台',
  input: '添加课程',
  library: '课程列表',
  consultation: '咨询记录',
  calendar: '课程日历',
  classes: '班级管理',
  smartWrongQuestions: '智能错题',
  accounts: '账号审批',
  settings: '系统设置',
};
```

```tsx
{activePage === 'smartWrongQuestions' && (currentUser.role === 'owner' || currentUser.role === 'admin') && (
  <SmartWrongQuestionsPage currentUser={currentUser} />
)}
```

- [ ] **Step 7: Re-run the focused frontend tests and confirm they pass**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/smart-wrong-questions.test.ts`

Expected: PASS with the new page wiring and helper behavior.

- [ ] **Step 8: Commit the page shell and helper layer**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/App.tsx frontend/src/SmartWrongQuestionsPage.tsx frontend/src/smartWrongQuestions.ts frontend/src/smart-wrong-questions.test.ts frontend/src/workspace-navigation.test.ts
git commit -m "feat: add smart wrong questions workspace tab"
```

### Task 4: Connect Detail Save And Export Flows, Then Run Full Verification

**Files:**
- Modify: `frontend/src/SmartWrongQuestionsPage.tsx`
- Modify: `frontend/src/smart-wrong-questions.test.ts`
- Modify: `tests/test_smart_wrong_questions_api.py`

- [ ] **Step 1: Add a failing frontend helper test for preserving unsaved review state on save failure**

```ts
test('buildWrongQuestionQuery leaves export filters reusable after save failures', () => {
  assert.equal(
    buildWrongQuestionQuery({ studentName: '学生A', teacherPriority: '需要复讲' }),
    'studentName=%E5%AD%A6%E7%94%9FA&teacherPriority=%E9%9C%80%E8%A6%81%E5%A4%8D%E8%AE%B2',
  );
});
```

- [ ] **Step 2: Add the review-save and export actions to the detail panel**

```tsx
const handleSaveReview = async () => {
  if (!detail) return;
  setSaving(true);
  setSaveError('');
  try {
    const updated = await apiFetch<WrongQuestionRecord>(`/api/wrong-questions/${detail.id}/review`, {
      method: 'PUT',
      body: JSON.stringify(reviewDraft),
      headers: { 'Content-Type': 'application/json' },
    });
    setDetail(updated);
  } catch (err) {
    setSaveError(err instanceof Error ? err.message : '保存失败，未同步到服务器');
  } finally {
    setSaving(false);
  }
};

const handleExport = () => {
  const query = buildWrongQuestionQuery(filters);
  window.open(`/api/wrong-questions/summary/export${query ? `?${query}` : ''}`, '_blank', 'noopener,noreferrer');
};
```

- [ ] **Step 3: Add a backend test that verifies export returns PDF content type for staff users**

```python
@patch('smart_wrong_questions.export_wrong_question_summary')
def test_staff_can_export_wrong_question_pdf(self, export_wrong_question_summary):
    owner_token = self.login_owner()
    export_wrong_question_summary.return_value = (b'%PDF-1.4 mock', 'wrong-question-summary.pdf')

    response = self.client.get('/api/wrong-questions/summary/export', headers=self.auth_headers(owner_token))

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.headers['Content-Type'], 'application/pdf')
    self.assertIn('wrong-question-summary.pdf', response.headers['Content-Disposition'])
```

- [ ] **Step 4: Run the backend and frontend targeted suites after the detail actions are connected**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_smart_wrong_questions_api -v`

Expected: PASS with review save and export coverage included.

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/smart-wrong-questions.test.ts`

Expected: PASS with helper/export assertions and no regressions in page wiring.

- [ ] **Step 5: Run the final frontend typecheck/build proof for the shipped tab**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npm run lint && npm run build`

Expected: `tsc --noEmit` passes and the production build succeeds, with at most the existing chunk-size warning.

- [ ] **Step 6: Commit the completed end-to-end SaaS integration**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/SmartWrongQuestionsPage.tsx frontend/src/smartWrongQuestions.ts frontend/src/smart-wrong-questions.test.ts tests/test_smart_wrong_questions_api.py
git commit -m "feat: ship smart wrong questions workspace"
```

## Self-Review

- **Spec coverage:** The plan covers the confirmed dual-entry model, the internal-only `智能错题` tab, the SaaS proxy architecture, owner/admin gating, list/detail/review/export flows, and the explicit first-release scope boundary that excludes chat-room reconstruction and login unification.
- **Placeholder scan:** No unresolved placeholder markers remain. Each task includes exact files, commands, expected outcomes, and code to anchor the implementation.
- **Type consistency:** The plan uses one shared frontend page key `smartWrongQuestions`, one backend route family `/api/wrong-questions*`, and one downstream review route `/api/teacher/records/:recordId/selections`. The helper/type names stay consistent across tasks.
