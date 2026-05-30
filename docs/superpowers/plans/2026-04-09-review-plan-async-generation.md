# Review Plan Async Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert single-lesson and monthly review-plan generation from synchronous requests into async task flows so the configured high-quality chat model can stay enabled without blocking the UI.

**Architecture:** Single-lesson generation will reuse `lessons` rows as the task shell by introducing explicit `record_status` and `generation_error` persistence plus a background worker in `app.py`. Monthly generation will use a minimal dedicated `monthly_plan_jobs` table because there is no natural `lesson` record to attach to. Frontend work will stop awaiting long-running `POST` requests, instead refreshing/polling list or job detail state until records move from `pending` to `ready` or `failed`.

**Tech Stack:** Flask, SQLite, Python threads, React, Vite, unittest

---

### Task 1: Persist Async Status For Lessons And Monthly Jobs

**Files:**
- Modify: `lesson_manager.py`
- Create: `tests/test_review_plan_async_store.py`

- [ ] **Step 1: Write the failing storage tests**

```python
import tempfile
import unittest
from pathlib import Path

import config_runtime
import lesson_manager


class ReviewPlanAsyncStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = base / "xingrun.db"
        config_runtime.CFG_PATH = base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.class_id = lesson_manager.save_class("异步测试班", subject="数学", grade="初二")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_pending_lesson_and_mark_ready(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="斜率判断",
            class_id=self.class_id,
        )

        pending = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(pending["record_status"], "pending")
        self.assertEqual(pending["generation_error"], "")

        lesson_manager.mark_lesson_generation_succeeded(
            lesson_id,
            plan={"lesson_info": {"topic": "一次函数"}, "days": []},
            pdf_path="/tmp/example.pdf",
        )

        saved = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(saved["record_status"], "ready")
        self.assertEqual(saved["pdf_path"], "/tmp/example.pdf")
        self.assertEqual(saved["generation_error"], "")

    def test_mark_lesson_generation_failed_records_error(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="斜率判断",
            class_id=self.class_id,
        )

        lesson_manager.mark_lesson_generation_failed(lesson_id, "AI 生成失败，请稍后重试")

        saved = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(saved["record_status"], "failed")
        self.assertEqual(saved["generation_error"], "AI 生成失败，请稍后重试")

    def test_create_monthly_plan_job_and_mark_ready(self):
        job = lesson_manager.create_monthly_plan_job(
            organization_id=1,
            user_id=1,
            month_str="2026-04",
        )

        self.assertEqual(job["status"], "pending")

        lesson_manager.mark_monthly_plan_job_succeeded(job["id"], pdf_filename="2026-04_月度综合复习.pdf")
        saved = lesson_manager.get_monthly_plan_job(job["id"])
        self.assertEqual(saved["status"], "ready")
        self.assertEqual(saved["pdf_filename"], "2026-04_月度综合复习.pdf")
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `/tmp/xingrun-proof-venv/bin/python -m unittest tests.test_review_plan_async_store -v`

Expected: `AttributeError` for missing helpers such as `create_pending_lesson`, `mark_lesson_generation_failed`, or missing persisted columns like `record_status`.

- [ ] **Step 3: Add lesson/job schema and helpers in `lesson_manager.py`**

```python
def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER REFERENCES organizations(id),
                date TEXT NOT NULL,
                subject TEXT,
                grade TEXT,
                topic TEXT,
                summary TEXT,
                weak_points TEXT,
                plan_json TEXT,
                pdf_path TEXT,
                class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
                record_status TEXT NOT NULL DEFAULT 'ready',
                generation_error TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS monthly_plan_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL REFERENCES organizations(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                month_str TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                pdf_filename TEXT NOT NULL DEFAULT '',
                generation_error TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );
            """
        )
        _ensure_column(conn, "lessons", "record_status", "TEXT NOT NULL DEFAULT 'ready'")
        _ensure_column(conn, "lessons", "generation_error", "TEXT NOT NULL DEFAULT ''")


def create_pending_lesson(...):
    return _insert_lesson(..., record_status="pending", generation_error="")


def mark_lesson_generation_succeeded(lesson_id: int, *, plan: dict, pdf_path: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE lessons
            SET plan_json=?, pdf_path=?, record_status='ready', generation_error=''
            WHERE id=?
            """,
            (json.dumps(plan, ensure_ascii=False), pdf_path, lesson_id),
        )


def mark_lesson_generation_failed(lesson_id: int, error_message: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE lessons
            SET record_status='failed', generation_error=?
            WHERE id=?
            """,
            (error_message, lesson_id),
        )
```

- [ ] **Step 4: Run the storage tests to verify they pass**

Run: `/tmp/xingrun-proof-venv/bin/python -m unittest tests.test_review_plan_async_store -v`

Expected:

```text
Ran 3 tests in ...

OK
```

- [ ] **Step 5: Commit**

```bash
git add lesson_manager.py tests/test_review_plan_async_store.py
git commit -m "feat: persist async review generation state"
```

### Task 2: Convert Single-Lesson Review Generation To Async Backend

**Files:**
- Modify: `app.py`
- Modify: `lesson_manager.py`
- Create: `tests/test_review_plan_async_api.py`

- [ ] **Step 1: Write the failing API tests for async lesson creation**

```python
import importlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_runtime
import lesson_manager


class ReviewPlanAsyncApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = base / "xingrun.db"
        config_runtime.CFG_PATH = base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.app_module = importlib.import_module("app")
        self.client = self.app_module.app.test_client()
        login = self.client.post("/api/login", json={"username": "Kayn", "password": "xingrun2026"})
        payload = login.get_json()
        self.headers = {"X-Auth-Token": payload["token"]}
        self.class_id = lesson_manager.save_class("异步测试班", subject="数学", grade="初二")

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("app._start_review_plan_generation_thread")
    def test_post_review_plan_returns_202_and_creates_pending_lesson(self, start_thread):
        response = self.client.post(
            "/api/review-plans",
            headers=self.headers,
            json={
                "class_id": self.class_id,
                "date": "2026-04-09",
                "subject": "数学",
                "topic": "一次函数",
                "weak_points": "斜率判断",
                "summary_text": "课堂总结",
            },
        )

        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertEqual(payload["status"], "pending")
        lesson = lesson_manager.get_lesson(payload["id"])
        self.assertEqual(lesson["record_status"], "pending")
        start_thread.assert_called_once()

    def test_review_plan_worker_marks_failed_when_ai_raises(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="斜率判断",
            class_id=self.class_id,
        )

        with patch("ai_processor.parse_and_generate_plan", side_effect=RuntimeError("boom")):
            self.app_module._run_review_plan_generation_job(
                lesson_id=lesson_id,
                user_id=1,
                organization_id=1,
                request_id="test-request",
                feature_key="lesson_plan_generate",
                source_record_id="draft:test",
            )

        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["record_status"], "failed")
        self.assertIn("AI 生成失败", lesson["generation_error"])
```

- [ ] **Step 2: Run the async lesson API tests to verify they fail**

Run: `/tmp/xingrun-proof-venv/bin/python -m unittest tests.test_review_plan_async_api -v`

Expected: `AssertionError` on `201 != 202` and missing worker helpers such as `_start_review_plan_generation_thread`.

- [ ] **Step 3: Add the background-worker backend flow**

```python
def _start_review_plan_generation_thread(*, lesson_id: int, user: dict, request_id: str, source_record_id: str) -> None:
    worker = threading.Thread(
        target=_run_review_plan_generation_job,
        kwargs={
            "lesson_id": lesson_id,
            "user_id": int(user["id"]),
            "organization_id": int(user["organization_id"]),
            "request_id": request_id,
            "feature_key": "lesson_plan_generate",
            "source_record_id": source_record_id,
        },
        daemon=True,
    )
    worker.start()


def _run_review_plan_generation_job(...):
    try:
        _claim_ai_request_identity(organization_id=organization_id, request_id=request_id)
        _claim_ai_organization_execution(organization_id)
        ensure_feature_credits_available(organization_id=organization_id, feature_key=feature_key)
        lesson = get_lesson(lesson_id)
        plan_result = _call_ai_helper_with_usage(
            parse_and_generate_plan,
            summary_text=lesson["summary"] or "",
            subject=lesson["subject"] or "",
            grade=lesson["grade"] or "",
            topic=lesson["topic"] or "",
            weak_points=lesson["weak_points"] or "",
            lesson_date=lesson["date"] or "",
        )
        plan, usage = _split_ai_result_with_usage(plan_result, provider=_default_ai_provider_name(), model=_default_chat_model_name())
        pdf_path = str(PDF_DIR / pdf_name)
        generate_single_lesson_pdf(plan, pdf_path)
        mark_lesson_generation_succeeded(lesson_id, plan=plan, pdf_path=pdf_path)
        finalize_ai_charge(...)
    except CreditBalanceError as exc:
        mark_lesson_generation_failed(lesson_id, str(exc))
    except Exception:
        logger.exception("Review plan generation failed for lesson %s", lesson_id)
        mark_lesson_generation_failed(lesson_id, "AI 生成失败，请稍后重试")
    finally:
        _release_ai_organization_execution(organization_id)
        _release_ai_request_identity(request_id)


@app.route("/api/review-plans", methods=["POST"])
def api_lesson_create():
    ...
    lesson_id = create_pending_lesson(...)
    _start_review_plan_generation_thread(...)
    return jsonify({"id": lesson_id, "success": True, "status": "pending"}), 202
```

- [ ] **Step 4: Run the async lesson API tests to verify they pass**

Run: `/tmp/xingrun-proof-venv/bin/python -m unittest tests.test_review_plan_async_api -v`

Expected:

```text
Ran 2 tests in ...

OK
```

- [ ] **Step 5: Commit**

```bash
git add app.py lesson_manager.py tests/test_review_plan_async_api.py
git commit -m "feat: make lesson review generation async"
```

### Task 3: Surface Pending/Failed Review Lessons In The Frontend

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/courseCalendarData.ts`
- Create: `frontend/src/review-generation-async.test.tsx`

- [ ] **Step 1: Write the failing frontend tests**

```tsx
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

describe('review generation async flow', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('refreshes review history until a pending lesson becomes ready', async () => {
    const responses = [
      [{ id: 1, date: '2026-04-09', subject: '数学', grade: '初二', topic: '一次函数', summary: '课堂总结', weak_points: '斜率判断', pdf_path: '', class_id: 1, created_at: '2026-04-09 10:00:00', record_status: 'pending', generation_error: '' }],
      [{ id: 1, date: '2026-04-09', subject: '数学', grade: '初二', topic: '一次函数', summary: '课堂总结', weak_points: '斜率判断', pdf_path: '/tmp/example.pdf', class_id: 1, created_at: '2026-04-09 10:00:00', record_status: 'ready', generation_error: '' }],
    ];

    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: async () => responses.shift(),
      } as Response),
    ) as typeof fetch;

    render(<ReviewDocumentHistory refreshToken={1} />);

    expect(await screen.findByText('生成中')).toBeInTheDocument();
    vi.advanceTimersByTime(3_000);
    await waitFor(() => expect(screen.getByText('已生成')).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run: `npm --prefix frontend test -- review-generation-async.test.tsx`

Expected: fail because `Lesson` does not expose `record_status`/`generation_error` and history cards do not render pending/failed badges.

- [ ] **Step 3: Implement pending/failed UI and polling**

```tsx
interface Lesson {
  id: number;
  date: string;
  subject: string;
  grade: string;
  topic: string;
  summary: string;
  weak_points: string;
  pdf_path: string;
  class_id: number | null;
  created_at: string;
  record_status?: string;
  generation_error?: string;
}

const hasPendingLesson = lessons.some((lesson) => lesson.record_status === 'pending');

useEffect(() => {
  if (!hasPendingLesson) {
    return;
  }
  const timer = window.setInterval(() => {
    void load();
  }, 3000);
  return () => window.clearInterval(timer);
}, [hasPendingLesson, load]);

const statusLabel = lesson.record_status === 'pending'
  ? '生成中'
  : lesson.record_status === 'failed'
    ? '生成失败'
    : lesson.pdf_path
      ? '已生成'
      : '无 PDF';
```

- [ ] **Step 4: Run the frontend tests to verify they pass**

Run: `npm --prefix frontend test -- review-generation-async.test.tsx course-calendar-data.test.ts`

Expected:

```text
✓ review-generation-async.test.tsx
✓ course-calendar-data.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/courseCalendarData.ts frontend/src/review-generation-async.test.tsx
git commit -m "feat: show async review generation status in frontend"
```

### Task 4: Add Monthly Plan Async Jobs And Retry Endpoints

**Files:**
- Modify: `app.py`
- Modify: `lesson_manager.py`
- Create: `tests/test_monthly_plan_async_api.py`

- [ ] **Step 1: Write the failing monthly async tests**

```python
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_runtime
import lesson_manager


class MonthlyPlanAsyncApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = base / "xingrun.db"
        config_runtime.CFG_PATH = base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.app_module = importlib.import_module("app")
        self.client = self.app_module.app.test_client()
        login = self.client.post("/api/login", json={"username": "Kayn", "password": "xingrun2026"})
        payload = login.get_json()
        self.headers = {"X-Auth-Token": payload["token"]}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_monthly_generate_returns_pending_job(self):
        lesson_manager.save_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="斜率判断",
            plan={"lesson_info": {"topic": "一次函数"}, "days": []},
            pdf_path="",
            class_id=0,
        )

        with patch("app._start_monthly_plan_generation_thread") as start_thread:
            response = self.client.post("/api/monthly/generate", headers=self.headers, json={"month": "2026-04"})

        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertEqual(payload["status"], "pending")
        start_thread.assert_called_once()

    def test_monthly_retry_requeues_failed_job(self):
        job = lesson_manager.create_monthly_plan_job(organization_id=1, user_id=1, month_str="2026-04")
        lesson_manager.mark_monthly_plan_job_failed(job["id"], "AI 生成失败，请稍后重试")

        response = self.client.post(f"/api/monthly/jobs/{job['id']}/retry", headers=self.headers)

        self.assertEqual(response.status_code, 202)
        refreshed = lesson_manager.get_monthly_plan_job(job["id"])
        self.assertEqual(refreshed["status"], "pending")
        self.assertEqual(refreshed["generation_error"], "")
```

- [ ] **Step 2: Run the monthly async tests to verify they fail**

Run: `/tmp/xingrun-proof-venv/bin/python -m unittest tests.test_monthly_plan_async_api -v`

Expected: fail on `200 != 202` and missing endpoints like `/api/monthly/jobs/<id>/retry`.

- [ ] **Step 3: Implement monthly job creation, worker, detail, and retry**

```python
@app.route("/api/monthly/generate", methods=["POST"])
def api_monthly_generate():
    ...
    job = create_monthly_plan_job(
        organization_id=int(user["organization_id"]),
        user_id=int(user["id"]),
        month_str=month_str,
    )
    _start_monthly_plan_generation_thread(job_id=job["id"], user=user)
    return jsonify({"id": job["id"], "status": "pending"}), 202


@app.route("/api/monthly/jobs/<int:job_id>", methods=["GET"])
def api_monthly_job_get(job_id: int):
    ...
    return jsonify(job)


@app.route("/api/monthly/jobs/<int:job_id>/retry", methods=["POST"])
def api_monthly_job_retry(job_id: int):
    ...
    requeued = requeue_monthly_plan_job(job_id)
    _start_monthly_plan_generation_thread(job_id=job_id, user=user)
    return jsonify({"id": requeued["id"], "status": "pending"}), 202
```

- [ ] **Step 4: Run the monthly async tests to verify they pass**

Run: `/tmp/xingrun-proof-venv/bin/python -m unittest tests.test_monthly_plan_async_api -v`

Expected:

```text
Ran 2 tests in ...

OK
```

- [ ] **Step 5: Commit**

```bash
git add app.py lesson_manager.py tests/test_monthly_plan_async_api.py
git commit -m "feat: make monthly review generation async"
```

### Task 5: Remove Temporary `gpt-4o` Fallback And Verify End-To-End Behavior

**Files:**
- Modify: `ai_processor.py`
- Modify: `tests/test_ai_processor_prompt.py`
- Modify: `handoff.md`

- [ ] **Step 1: Write the failing regression update**

```python
class AiProcessorPromptTestCase(unittest.TestCase):
    def test_parse_and_generate_plan_uses_configured_model_after_async_rollout(self):
        fake_client = _FakeClient({"lesson_info": {}, "days": [], "weekly_review_prompts": []})
        with patch(
            "ai_processor._load_config",
            return_value={
                "provider": "deepseek",
                "deepseek_model": "deepseek-chat",
                "deepseek_api_key": "test-key",
            },
        ), patch("ai_processor._get_client", return_value=fake_client):
            ai_processor.parse_and_generate_plan("课堂总结")

        self.assertEqual(fake_client.chat.completions.last_kwargs["model"], "deepseek-chat")
```

- [ ] **Step 2: Run the regression tests to verify they fail**

Run: `/tmp/xingrun-proof-venv/bin/python -m unittest tests.test_ai_processor_prompt -v`

Expected: fail because `_get_structured_generation_model()` still rewrites `gpt-5.4` to `gpt-4o`.

- [ ] **Step 3: Remove the temporary fallback and keep only the configured model**

```python
def _get_chat_model() -> str:
    cfg = _load_config()
    provider = cfg.get("provider", "openai")
    ...


def parse_and_generate_plan(...):
    response = client.chat.completions.create(
        model=_get_chat_model(),
        ...
    )
```

- [ ] **Step 4: Run the final verification bundle**

Run:

```bash
/tmp/xingrun-proof-venv/bin/python -m unittest \
  tests.test_review_plan_async_store \
  tests.test_review_plan_async_api \
  tests.test_monthly_plan_async_api \
  tests.test_ai_processor_prompt -v

npm --prefix frontend test -- review-generation-async.test.tsx course-calendar-data.test.ts
```

Expected:

```text
OK
✓ review-generation-async.test.tsx
✓ course-calendar-data.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add ai_processor.py tests/test_ai_processor_prompt.py handoff.md
git commit -m "fix: restore gpt-5 review generation on async flow"
```

## Self-Review

- **Spec coverage:** Covered single-lesson async storage and worker flow (Tasks 1-3), monthly async jobs (Task 4), and post-rollout removal of the temporary `gpt-4o` fallback (Task 5).
- **Placeholder scan:** No `TODO`/`TBD` placeholders remain; each task has explicit files, tests, commands, and commit boundaries.
- **Type consistency:** Plan uses `record_status`, `generation_error`, `monthly_plan_jobs`, `create_pending_lesson`, and monthly job helpers consistently across tasks.
