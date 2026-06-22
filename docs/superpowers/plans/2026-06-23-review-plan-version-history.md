# Review Plan Version History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build versioned review plan generation so regeneration never overwrites the current usable PDF, and migrate generated artifacts out of `lessons`.

**Architecture:** `lessons` stores course metadata and points at one current generated version. `review_plan_versions` stores generation status, plan JSON, PDFs, request metadata, and version history. The Flask API serializes one lesson row per course for lists and exposes version-specific detail, preview, download, and rollback actions; the React UI keeps the list compact and opens a lightweight second-level detail view for versions.

**Tech Stack:** Python 3, Flask, SQLite, unittest/pytest, Vite, React, TypeScript, node:test, lucide-react.

---

## Source Spec

- `docs/superpowers/specs/2026-06-23-review-plan-version-history-design.md`

## File Structure

- Modify `lesson_manager.py`
  - Create and migrate `review_plan_versions`.
  - Remove generated-artifact columns from `lessons`.
  - Add focused version store helpers.
  - Keep `get_lesson()` and `list_lessons()` returning computed current-version fields so existing dashboard, student tasks, and PDF wrappers can move in small steps.

- Modify `app.py`
  - Import new version helpers.
  - Pass `version_id` through async review-plan jobs.
  - Serialize list/detail responses from current and active versions.
  - Add version preview/download and rollback endpoints.
  - Keep existing `/api/pdf/<lesson_id>` wrappers resolving through the current version.

- Modify `tests/test_review_plan_async_store.py`
  - Replace old `record_status/pdf_path` persistence assertions with version lifecycle assertions.

- Create `tests/test_review_plan_version_store.py`
  - Prove migration, idempotence, removed DB columns, current pointer behavior, and version helper behavior.

- Modify `tests/test_review_plan_async_api.py`
  - Prove create/regenerate/list/detail/download/rollback API behavior.

- Modify `tests/test_student_review_tasks_api.py`
  - Prove student review tasks read plan/PDF from the current version.

- Modify `frontend/src/reviewGenerationAsync.ts`
  - Normalize current-version and active-generation fields.
  - Update task state and progress helpers.

- Modify `frontend/src/reviewGenerationAsync.test.ts`
  - Replace old `pdf_path/record_status` helper tests with version-aware tests.

- Create `frontend/src/features/review-generation/reviewPlanVersions.ts`
  - Keep version labels, action availability, and URL helpers out of the page component.

- Create `frontend/src/features/review-generation/ReviewPlanDetailView.tsx`
  - Fetch lesson detail, render PDF preview, download, regenerate, version history, and rollback.

- Modify `frontend/src/features/review-generation/ReviewGenerationPage.tsx`
  - Keep list one row per lesson.
  - Add a details action and pass regeneration callbacks into the detail view.
  - Keep current PDF actions enabled while a new version is generating.

- Modify `frontend/src/review-generation-async.test.tsx`
  - Update source-level assertions for detail view, version URLs, and non-overwriting regeneration feedback.

- Modify `handoff.md`
  - Record completed implementation and remaining deployment step after verification.

## Task 1: Storage Migration Tests

**Files:**
- Create: `tests/test_review_plan_version_store.py`
- Modify: `tests/test_review_plan_async_store.py`

- [ ] **Step 1: Add migration and lifecycle tests**

Create `tests/test_review_plan_version_store.py` with this content:

```python
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import config_runtime
import lesson_manager


LEGACY_ARTIFACT_COLUMNS = {
    "plan_json",
    "pdf_path",
    "record_status",
    "generation_error",
    "review_audio_path",
    "review_audio_request_key",
    "review_request_key",
    "review_request_id",
    "review_chat_provider",
    "review_chat_model",
    "review_same_lesson_materials_json",
}


def _legacy_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER,
            date TEXT NOT NULL,
            subject TEXT,
            grade TEXT,
            topic TEXT,
            summary TEXT,
            weak_points TEXT,
            plan_json TEXT,
            pdf_path TEXT,
            class_id INTEGER,
            record_status TEXT NOT NULL DEFAULT 'ready',
            generation_error TEXT NOT NULL DEFAULT '',
            created_by_user_id INTEGER NOT NULL DEFAULT 0,
            review_audio_path TEXT NOT NULL DEFAULT '',
            review_audio_request_key TEXT NOT NULL DEFAULT '',
            review_request_key TEXT NOT NULL DEFAULT '',
            review_request_id TEXT NOT NULL DEFAULT '',
            review_chat_provider TEXT NOT NULL DEFAULT '',
            review_chat_model TEXT NOT NULL DEFAULT '',
            review_same_lesson_materials_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT DEFAULT '2026-04-09 10:00:00'
        );
        """
    )
    return conn


class ReviewPlanVersionMigrationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_migrates_ready_legacy_lesson_to_current_version_and_removes_columns(self):
        conn = _legacy_conn(lesson_manager.DB_PATH)
        plan = {"lesson_info": {"topic": "旧计划"}, "days": []}
        conn.execute(
            """
            INSERT INTO lessons (
                organization_id, date, subject, grade, topic, summary, weak_points,
                plan_json, pdf_path, record_status, generation_error, created_by_user_id,
                review_request_key, review_request_id, review_chat_provider, review_chat_model,
                review_same_lesson_materials_json
            )
            VALUES (1, '2026-04-09', '数学', '初二', '一次函数', '课堂总结', '斜率',
                    ?, '/tmp/legacy-ready.pdf', 'ready', '', 7,
                    'legacy-key', 'legacy-id', 'openai', 'gpt-5.4', ?)
            """,
            (
                json.dumps(plan, ensure_ascii=False),
                json.dumps(["补充材料"], ensure_ascii=False),
            ),
        )
        conn.commit()

        lesson_manager._ensure_review_plan_versions_schema(conn)
        lesson_manager._migrate_legacy_review_plan_columns(conn)
        lesson_manager._rebuild_lessons_without_review_plan_artifact_columns(conn)
        conn.commit()

        lesson_cols = {row["name"] for row in conn.execute("PRAGMA table_info(lessons)").fetchall()}
        self.assertFalse(LEGACY_ARTIFACT_COLUMNS & lesson_cols)
        self.assertIn("current_review_plan_version_id", lesson_cols)

        lesson = conn.execute("SELECT * FROM lessons WHERE id=1").fetchone()
        version = conn.execute("SELECT * FROM review_plan_versions WHERE lesson_id=1").fetchone()
        self.assertIsNotNone(version)
        self.assertEqual(version["version_no"], 1)
        self.assertEqual(version["status"], "ready")
        self.assertEqual(version["pdf_path"], "/tmp/legacy-ready.pdf")
        self.assertEqual(version["request_key"], "legacy-key")
        self.assertEqual(version["request_id"], "legacy-id")
        self.assertEqual(version["chat_provider"], "openai")
        self.assertEqual(version["chat_model"], "gpt-5.4")
        self.assertEqual(json.loads(version["same_lesson_materials_json"]), ["补充材料"])
        self.assertEqual(lesson["current_review_plan_version_id"], version["id"])

    def test_migrates_failed_legacy_lesson_without_current_pointer(self):
        conn = _legacy_conn(lesson_manager.DB_PATH)
        conn.execute(
            """
            INSERT INTO lessons (
                organization_id, date, subject, grade, topic, summary, weak_points,
                plan_json, pdf_path, record_status, generation_error, created_by_user_id
            )
            VALUES (1, '2026-04-09', '数学', '初二', '一次函数', '课堂总结', '斜率',
                    '', '', 'failed', 'AI 生成失败', 7)
            """
        )
        conn.commit()

        lesson_manager._ensure_review_plan_versions_schema(conn)
        lesson_manager._migrate_legacy_review_plan_columns(conn)
        lesson_manager._rebuild_lessons_without_review_plan_artifact_columns(conn)
        conn.commit()

        lesson = conn.execute("SELECT * FROM lessons WHERE id=1").fetchone()
        version = conn.execute("SELECT * FROM review_plan_versions WHERE lesson_id=1").fetchone()
        self.assertIsNotNone(version)
        self.assertEqual(version["status"], "failed")
        self.assertEqual(version["generation_error"], "AI 生成失败")
        self.assertIsNone(lesson["current_review_plan_version_id"])

    def test_migration_is_idempotent(self):
        conn = _legacy_conn(lesson_manager.DB_PATH)
        conn.execute(
            """
            INSERT INTO lessons (
                organization_id, date, subject, grade, topic, summary, weak_points,
                plan_json, pdf_path, record_status, generation_error, created_by_user_id
            )
            VALUES (1, '2026-04-09', '数学', '初二', '一次函数', '课堂总结', '斜率',
                    '{"days":[]}', '/tmp/legacy-ready.pdf', 'ready', '', 7)
            """
        )
        conn.commit()

        for _ in range(2):
            lesson_manager._ensure_review_plan_versions_schema(conn)
            lesson_manager._migrate_legacy_review_plan_columns(conn)
            lesson_manager._rebuild_lessons_without_review_plan_artifact_columns(conn)
            conn.commit()

        count = conn.execute("SELECT COUNT(*) AS count FROM review_plan_versions").fetchone()["count"]
        lesson = conn.execute("SELECT * FROM lessons WHERE id=1").fetchone()
        self.assertEqual(count, 1)
        self.assertEqual(lesson["current_review_plan_version_id"], 1)


class ReviewPlanVersionLifecycleTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = base / "xingrun.db"
        config_runtime.CFG_PATH = base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.class_id = lesson_manager.save_class("版本测试班", subject="数学", grade="初二")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_version_lifecycle_keeps_current_until_new_version_is_ready(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="斜率判断",
            class_id=self.class_id,
            created_by_user_id=7,
        )
        first = lesson_manager.create_review_plan_version(
            lesson_id=lesson_id,
            status="generating",
            request_key="request-1",
            request_id="request-id-1",
            chat_provider="openai",
            chat_model="gpt-5.4",
            created_by_user_id=7,
        )
        lesson_manager.complete_review_plan_version(
            first["id"],
            plan={"lesson_info": {"topic": "第一版"}, "days": []},
            pdf_path="/tmp/v1.pdf",
        )

        second = lesson_manager.create_review_plan_version(
            lesson_id=lesson_id,
            status="generating",
            request_key="request-2",
            request_id="request-id-2",
            chat_provider="openai",
            chat_model="gpt-5.4",
            created_by_user_id=7,
        )
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["current_review_plan_version_id"], first["id"])
        self.assertEqual(lesson["current_version"]["id"], first["id"])
        self.assertEqual(lesson["pdf_path"], "/tmp/v1.pdf")
        self.assertEqual(lesson["has_version_generating"], True)

        lesson_manager.fail_review_plan_version(second["id"], "第二版失败")
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["current_review_plan_version_id"], first["id"])
        self.assertEqual(lesson["latest_generation_error"], "第二版失败")

        lesson_manager.complete_review_plan_version(
            second["id"],
            plan={"lesson_info": {"topic": "第二版"}, "days": []},
            pdf_path="/tmp/v2.pdf",
        )
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["current_review_plan_version_id"], second["id"])
        self.assertEqual(lesson["current_version_no"], 2)
        self.assertEqual(lesson["pdf_path"], "/tmp/v2.pdf")

    def test_make_current_requires_ready_version_from_same_lesson(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="斜率判断",
            class_id=self.class_id,
            created_by_user_id=7,
        )
        ready = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        failed = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(ready["id"], plan={"days": []}, pdf_path="/tmp/ready.pdf")
        lesson_manager.fail_review_plan_version(failed["id"], "失败")

        with self.assertRaisesRegex(ValueError, "ready"):
            lesson_manager.set_current_review_plan_version(lesson_id, failed["id"])

        lesson_manager.set_current_review_plan_version(lesson_id, ready["id"])
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["current_review_plan_version_id"], ready["id"])
```

- [ ] **Step 2: Run migration tests and confirm they fail**

Run:

```bash
python -m pytest tests/test_review_plan_version_store.py -q
```

Expected: failures naming missing helpers such as `_ensure_review_plan_versions_schema` or `create_review_plan_version`.

- [ ] **Step 3: Update existing async store tests to version names**

In `tests/test_review_plan_async_store.py`, replace the old lesson-output assertions with version assertions:

```python
    def test_create_pending_lesson_and_complete_version(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="斜率判断",
            class_id=self.class_id,
        )
        version = lesson_manager.create_review_plan_version(
            lesson_id=lesson_id,
            status="generating",
            request_key="request-key",
            request_id="request-id",
        )

        pending = lesson_manager.get_lesson(lesson_id)
        self.assertIsNone(pending["current_review_plan_version_id"])
        self.assertEqual(pending["has_version_generating"], True)

        lesson_manager.complete_review_plan_version(
            version["id"],
            plan={"lesson_info": {"topic": "一次函数"}, "days": []},
            pdf_path="/tmp/example.pdf",
        )

        saved = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(saved["current_review_plan_version_id"], version["id"])
        self.assertEqual(saved["current_status"], "ready")
        self.assertEqual(saved["current_version"]["pdf_path"], "/tmp/example.pdf")
        self.assertEqual(saved["pdf_path"], "/tmp/example.pdf")
```

Replace `test_create_pending_lesson_persists_review_generation_resume_context` with:

```python
    def test_review_plan_version_persists_generation_resume_context(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="",
            weak_points="斜率判断",
            class_id=self.class_id,
            created_by_user_id=7,
        )
        version = lesson_manager.create_review_plan_version(
            lesson_id=lesson_id,
            status="transcribing",
            created_by_user_id=7,
            audio_path="/tmp/lesson.m4a",
            audio_request_key="audio-key",
            request_key="request-key",
            request_id="request-id",
            chat_provider="deepseek",
            chat_model="deepseek-v4-flash",
            same_lesson_materials=["补充材料"],
        )

        saved = lesson_manager.get_review_plan_version(version["id"])
        self.assertEqual(saved["created_by_user_id"], 7)
        self.assertEqual(saved["audio_path"], "/tmp/lesson.m4a")
        self.assertEqual(saved["audio_request_key"], "audio-key")
        self.assertEqual(saved["request_key"], "request-key")
        self.assertEqual(saved["request_id"], "request-id")
        self.assertEqual(saved["chat_provider"], "deepseek")
        self.assertEqual(saved["chat_model"], "deepseek-v4-flash")
        self.assertEqual(saved["same_lesson_materials"], ["补充材料"])
```

Replace missing-row tests with:

```python
    def test_complete_review_plan_version_missing_raises(self):
        with self.assertRaisesRegex(LookupError, "review plan version not found"):
            lesson_manager.complete_review_plan_version(
                version_id=999999,
                plan={"dummy": "data"},
                pdf_path="/tmp/placeholder.pdf",
            )

    def test_fail_review_plan_version_missing_raises(self):
        with self.assertRaisesRegex(LookupError, "review plan version not found"):
            lesson_manager.fail_review_plan_version(
                version_id=999999,
                error_message="failure",
            )
```

- [ ] **Step 4: Run the updated store test and confirm expected failures**

Run:

```bash
python -m pytest tests/test_review_plan_version_store.py tests/test_review_plan_async_store.py -q
```

Expected: failures only from missing version helpers or old functions still being referenced by implementation.

- [ ] **Step 5: Commit failing tests**

```bash
git add tests/test_review_plan_version_store.py tests/test_review_plan_async_store.py
git commit -m "test: specify review plan version storage"
```

Expected: commit succeeds with only tests changed.

## Task 2: Storage Implementation

**Files:**
- Modify: `lesson_manager.py`

- [ ] **Step 1: Add constants and row helpers near existing lesson functions**

Add this block above `save_lesson()` in `lesson_manager.py`:

```python
REVIEW_PLAN_ACTIVE_STATUSES = {"pending", "queued", "processing", "transcribing", "generating"}
REVIEW_PLAN_READY_STATUS = "ready"
REVIEW_PLAN_FAILED_STATUS = "failed"
REVIEW_PLAN_LEGACY_ARTIFACT_COLUMNS = {
    "plan_json",
    "pdf_path",
    "record_status",
    "generation_error",
    "review_audio_path",
    "review_audio_request_key",
    "review_request_key",
    "review_request_id",
    "review_chat_provider",
    "review_chat_model",
    "review_same_lesson_materials_json",
}


def _review_plan_version_from_row(row) -> Optional[dict]:
    if not row:
        return None
    version = dict(row)
    try:
        version["plan"] = json.loads(version.get("plan_json") or "{}")
    except json.JSONDecodeError:
        version["plan"] = {}
    try:
        materials = json.loads(version.get("same_lesson_materials_json") or "[]")
    except json.JSONDecodeError:
        materials = []
    version["same_lesson_materials"] = materials if isinstance(materials, list) else []
    return version


def _lesson_columns(conn: sqlite3.Connection) -> set[str]:
    return {row["name"] for row in conn.execute("PRAGMA table_info(lessons)").fetchall()}


def _column_expr(columns: set[str], column: str, fallback_sql: str) -> str:
    return column if column in columns else fallback_sql
```

- [ ] **Step 2: Replace the `lessons` table definition in `init_db()`**

In the `CREATE TABLE IF NOT EXISTS lessons` block, remove generated-artifact columns and use this shape:

```sql
        CREATE TABLE IF NOT EXISTS lessons (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER REFERENCES organizations(id),
            date        TEXT NOT NULL,
            subject     TEXT,
            grade       TEXT,
            topic       TEXT,
            summary     TEXT,
            weak_points TEXT,
            class_id    INTEGER REFERENCES classes(id) ON DELETE SET NULL,
            current_review_plan_version_id INTEGER DEFAULT NULL,
            created_by_user_id INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            updated_at  TEXT DEFAULT (datetime('now','localtime'))
        );
```

- [ ] **Step 3: Add schema and migration helpers below `init_db()` helper functions**

Add this implementation in `lesson_manager.py` before `save_lesson()`:

```python
def _ensure_review_plan_versions_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS review_plan_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
            version_no INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'generating',
            plan_json TEXT NOT NULL DEFAULT '{}',
            pdf_path TEXT NOT NULL DEFAULT '',
            generation_error TEXT NOT NULL DEFAULT '',
            request_key TEXT NOT NULL DEFAULT '',
            request_id TEXT NOT NULL DEFAULT '',
            chat_provider TEXT NOT NULL DEFAULT '',
            chat_model TEXT NOT NULL DEFAULT '',
            audio_path TEXT NOT NULL DEFAULT '',
            audio_request_key TEXT NOT NULL DEFAULT '',
            same_lesson_materials_json TEXT NOT NULL DEFAULT '[]',
            created_by_user_id INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            completed_at TEXT DEFAULT '',
            UNIQUE(lesson_id, version_no)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_review_plan_versions_lesson_status ON review_plan_versions(lesson_id, status, version_no)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_review_plan_versions_lesson_created ON review_plan_versions(lesson_id, created_at, id)"
    )
    columns = _lesson_columns(conn)
    if "current_review_plan_version_id" not in columns:
        conn.execute("ALTER TABLE lessons ADD COLUMN current_review_plan_version_id INTEGER DEFAULT NULL")
    if "created_by_user_id" not in columns:
        conn.execute("ALTER TABLE lessons ADD COLUMN created_by_user_id INTEGER NOT NULL DEFAULT 0")
    if "updated_at" not in columns:
        conn.execute("ALTER TABLE lessons ADD COLUMN updated_at TEXT DEFAULT (datetime('now','localtime'))")


def _migrate_legacy_review_plan_columns(conn: sqlite3.Connection) -> None:
    columns = _lesson_columns(conn)
    if not (REVIEW_PLAN_LEGACY_ARTIFACT_COLUMNS & columns):
        return
    rows = conn.execute("SELECT * FROM lessons ORDER BY id").fetchall()
    for row in rows:
        lesson = dict(row)
        lesson_id = int(lesson["id"])
        existing = conn.execute(
            "SELECT id FROM review_plan_versions WHERE lesson_id=? AND version_no=1",
            (lesson_id,),
        ).fetchone()
        status = str(lesson.get("record_status") or "").strip() or "ready"
        plan_json = str(lesson.get("plan_json") or "").strip()
        pdf_path = str(lesson.get("pdf_path") or "").strip()
        generation_error = str(lesson.get("generation_error") or "").strip()
        has_legacy_state = bool(plan_json or pdf_path or generation_error or status in REVIEW_PLAN_ACTIVE_STATUSES or status == REVIEW_PLAN_FAILED_STATUS)
        if not existing and has_legacy_state:
            completed_at = str(lesson.get("updated_at") or lesson.get("created_at") or "").strip() if status == REVIEW_PLAN_READY_STATUS else ""
            cur = conn.execute(
                """
                INSERT INTO review_plan_versions (
                    lesson_id, version_no, status, plan_json, pdf_path, generation_error,
                    request_key, request_id, chat_provider, chat_model,
                    audio_path, audio_request_key, same_lesson_materials_json,
                    created_by_user_id, created_at, completed_at
                )
                VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lesson_id,
                    status,
                    plan_json or "{}",
                    pdf_path,
                    generation_error,
                    str(lesson.get("review_request_key") or ""),
                    str(lesson.get("review_request_id") or ""),
                    str(lesson.get("review_chat_provider") or ""),
                    str(lesson.get("review_chat_model") or ""),
                    str(lesson.get("review_audio_path") or ""),
                    str(lesson.get("review_audio_request_key") or ""),
                    str(lesson.get("review_same_lesson_materials_json") or "[]"),
                    int(lesson.get("created_by_user_id") or 0),
                    str(lesson.get("created_at") or ""),
                    completed_at,
                ),
            )
            version_id = int(cur.lastrowid)
        else:
            version_id = int(existing["id"]) if existing else 0
        if status == REVIEW_PLAN_READY_STATUS and version_id:
            conn.execute(
                """
                UPDATE lessons
                SET current_review_plan_version_id=COALESCE(current_review_plan_version_id, ?)
                WHERE id=?
                """,
                (version_id, lesson_id),
            )


def _rebuild_lessons_without_review_plan_artifact_columns(conn: sqlite3.Connection) -> None:
    columns = _lesson_columns(conn)
    if not (REVIEW_PLAN_LEGACY_ARTIFACT_COLUMNS & columns):
        return
    conn.execute(
        """
        CREATE TABLE lessons_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER REFERENCES organizations(id),
            date TEXT NOT NULL,
            subject TEXT,
            grade TEXT,
            topic TEXT,
            summary TEXT,
            weak_points TEXT,
            class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
            current_review_plan_version_id INTEGER DEFAULT NULL,
            created_by_user_id INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
        """
    )
    source = _lesson_columns(conn)
    conn.execute(
        f"""
        INSERT INTO lessons_new (
            id, organization_id, date, subject, grade, topic, summary, weak_points,
            class_id, current_review_plan_version_id, created_by_user_id, created_at, updated_at
        )
        SELECT
            id,
            {_column_expr(source, "organization_id", "NULL")},
            date,
            {_column_expr(source, "subject", "''")},
            {_column_expr(source, "grade", "''")},
            {_column_expr(source, "topic", "''")},
            {_column_expr(source, "summary", "''")},
            {_column_expr(source, "weak_points", "''")},
            {_column_expr(source, "class_id", "NULL")},
            {_column_expr(source, "current_review_plan_version_id", "NULL")},
            {_column_expr(source, "created_by_user_id", "0")},
            {_column_expr(source, "created_at", "datetime('now','localtime')")},
            {_column_expr(source, "updated_at", _column_expr(source, "created_at", "datetime('now','localtime')"))}
        FROM lessons
        """
    )
    conn.execute("DROP TABLE lessons")
    conn.execute("ALTER TABLE lessons_new RENAME TO lessons")
```

- [ ] **Step 4: Call migration helpers from `init_db()`**

Replace the old lesson artifact `_ensure_column()` calls:

```python
        _ensure_column(conn, "lessons", "record_status", "TEXT NOT NULL DEFAULT 'ready'")
        _ensure_column(conn, "lessons", "generation_error", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "lessons", "review_audio_path", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "lessons", "review_audio_request_key", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "lessons", "review_request_key", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "lessons", "review_request_id", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "lessons", "review_chat_provider", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "lessons", "review_chat_model", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "lessons", "review_same_lesson_materials_json", "TEXT NOT NULL DEFAULT '[]'")
```

with:

```python
        _ensure_review_plan_versions_schema(conn)
        _migrate_legacy_review_plan_columns(conn)
        _rebuild_lessons_without_review_plan_artifact_columns(conn)
```

Keep this metadata column call because it remains on `lessons`:

```python
        _ensure_column(conn, "lessons", "created_by_user_id", "INTEGER NOT NULL DEFAULT 0")
```

- [ ] **Step 5: Rewrite `save_lesson()` to create a ready version**

Replace `save_lesson()` with:

```python
def save_lesson(date_str: str, subject: str, grade: str, topic: str,
                summary: str, weak_points: str,
                plan: dict, pdf_path: str, class_id: int = 0) -> int:
    lesson_id = create_pending_lesson(
        date_str=date_str,
        subject=subject,
        grade=grade,
        topic=topic,
        summary=summary,
        weak_points=weak_points,
        class_id=class_id,
        created_by_user_id=0,
    )
    version = create_review_plan_version(lesson_id=lesson_id, status="generating")
    complete_review_plan_version(version["id"], plan=plan, pdf_path=pdf_path)
    return lesson_id
```

- [ ] **Step 6: Simplify `create_pending_lesson()`**

Keep only lesson metadata arguments in the insert. Retain the function signature temporarily so callers can be updated without a single large edit, but ignore old artifact arguments after moving them to `create_review_plan_version()`:

```python
        cur = conn.execute(
            """INSERT INTO lessons
               (date, subject, grade, topic, summary, weak_points,
                class_id, organization_id, created_by_user_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                date_str,
                subject,
                grade,
                topic,
                summary,
                weak_points,
                class_id if class_id else None,
                organization_id,
                int(created_by_user_id or 0),
            ),
        )
```

- [ ] **Step 7: Add focused version store functions**

Add these public helpers below `create_pending_lesson()`:

```python
def create_review_plan_version(
    *,
    lesson_id: int,
    status: str = "generating",
    request_key: str = "",
    request_id: str = "",
    chat_provider: str = "",
    chat_model: str = "",
    audio_path: str = "",
    audio_request_key: str = "",
    same_lesson_materials: Optional[list[str]] = None,
    created_by_user_id: int = 0,
) -> dict:
    normalized_status = str(status or "generating").strip() or "generating"
    materials_json = json.dumps(same_lesson_materials or [], ensure_ascii=False)
    with get_conn() as conn:
        lesson = conn.execute("SELECT id FROM lessons WHERE id=?", (int(lesson_id),)).fetchone()
        if not lesson:
            raise LookupError("lesson not found")
        active = conn.execute(
            """
            SELECT id FROM review_plan_versions
            WHERE lesson_id=? AND status IN ('pending', 'queued', 'processing', 'transcribing', 'generating')
            LIMIT 1
            """,
            (int(lesson_id),),
        ).fetchone()
        if active:
            raise ValueError("review plan version already generating")
        row = conn.execute(
            "SELECT COALESCE(MAX(version_no), 0) + 1 AS next_version_no FROM review_plan_versions WHERE lesson_id=?",
            (int(lesson_id),),
        ).fetchone()
        version_no = int(row["next_version_no"] or 1)
        cur = conn.execute(
            """
            INSERT INTO review_plan_versions (
                lesson_id, version_no, status, request_key, request_id, chat_provider, chat_model,
                audio_path, audio_request_key, same_lesson_materials_json, created_by_user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(lesson_id),
                version_no,
                normalized_status,
                str(request_key or ""),
                str(request_id or ""),
                str(chat_provider or ""),
                str(chat_model or ""),
                str(audio_path or ""),
                str(audio_request_key or ""),
                materials_json,
                int(created_by_user_id or 0),
            ),
        )
        conn.execute("UPDATE lessons SET updated_at=datetime('now','localtime') WHERE id=?", (int(lesson_id),))
        return get_review_plan_version(int(cur.lastrowid))


def mark_review_plan_version_transcription_succeeded(version_id: int, *, summary: str) -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT lesson_id FROM review_plan_versions WHERE id=?", (int(version_id),)).fetchone()
        if not row:
            raise LookupError("review plan version not found")
        conn.execute(
            """
            UPDATE review_plan_versions
            SET status='generating', generation_error=''
            WHERE id=?
            """,
            (int(version_id),),
        )
        conn.execute(
            "UPDATE lessons SET summary=?, updated_at=datetime('now','localtime') WHERE id=?",
            (summary, int(row["lesson_id"])),
        )


def complete_review_plan_version(version_id: int, *, plan: dict, pdf_path: str) -> None:
    plan_json = json.dumps(plan or {}, ensure_ascii=False)
    with get_conn() as conn:
        row = conn.execute("SELECT lesson_id FROM review_plan_versions WHERE id=?", (int(version_id),)).fetchone()
        if not row:
            raise LookupError("review plan version not found")
        lesson_id = int(row["lesson_id"])
        conn.execute(
            """
            UPDATE review_plan_versions
            SET status='ready', plan_json=?, pdf_path=?, generation_error='', completed_at=datetime('now','localtime')
            WHERE id=?
            """,
            (plan_json, str(pdf_path or ""), int(version_id)),
        )
        conn.execute(
            """
            UPDATE lessons
            SET current_review_plan_version_id=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (int(version_id), lesson_id),
        )


def fail_review_plan_version(version_id: int, error_message: str) -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT lesson_id FROM review_plan_versions WHERE id=?", (int(version_id),)).fetchone()
        if not row:
            raise LookupError("review plan version not found")
        conn.execute(
            """
            UPDATE review_plan_versions
            SET status='failed', generation_error=?, completed_at=datetime('now','localtime')
            WHERE id=?
            """,
            (str(error_message or "").strip(), int(version_id)),
        )
        conn.execute(
            "UPDATE lessons SET updated_at=datetime('now','localtime') WHERE id=?",
            (int(row["lesson_id"]),),
        )


def get_review_plan_version(version_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM review_plan_versions WHERE id=?", (int(version_id),)).fetchone()
        return _review_plan_version_from_row(row)


def get_review_plan_version_for_lesson(lesson_id: int, version_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM review_plan_versions WHERE id=? AND lesson_id=?",
            (int(version_id), int(lesson_id)),
        ).fetchone()
        return _review_plan_version_from_row(row)


def list_review_plan_versions(lesson_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM review_plan_versions
            WHERE lesson_id=?
            ORDER BY version_no DESC, id DESC
            """,
            (int(lesson_id),),
        ).fetchall()
        return [version for version in (_review_plan_version_from_row(row) for row in rows) if version is not None]


def set_current_review_plan_version(lesson_id: int, version_id: int) -> None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, lesson_id, status FROM review_plan_versions WHERE id=? AND lesson_id=?",
            (int(version_id), int(lesson_id)),
        ).fetchone()
        if not row:
            raise LookupError("review plan version not found")
        if str(row["status"] or "") != "ready":
            raise ValueError("review plan version must be ready")
        conn.execute(
            """
            UPDATE lessons
            SET current_review_plan_version_id=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (int(version_id), int(lesson_id)),
        )


def get_current_review_plan_version(lesson_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT v.*
            FROM lessons l
            JOIN review_plan_versions v ON v.id=l.current_review_plan_version_id
            WHERE l.id=?
            """,
            (int(lesson_id),),
        ).fetchone()
        return _review_plan_version_from_row(row)


def lesson_has_active_review_plan_version(lesson_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM review_plan_versions
            WHERE lesson_id=? AND status IN ('pending', 'queued', 'processing', 'transcribing', 'generating')
            LIMIT 1
            """,
            (int(lesson_id),),
        ).fetchone()
        return row is not None
```

- [ ] **Step 8: Replace old mark/requeue helpers with compatibility wrappers**

Replace `mark_lesson_transcription_succeeded`, `mark_lesson_generation_succeeded`, `mark_lesson_generation_failed`, and `requeue_lesson_generation` bodies with wrappers that find the newest active version and delegate:

```python
def _latest_active_review_plan_version_for_lesson(conn: sqlite3.Connection, lesson_id: int):
    return conn.execute(
        """
        SELECT * FROM review_plan_versions
        WHERE lesson_id=? AND status IN ('pending', 'queued', 'processing', 'transcribing', 'generating')
        ORDER BY version_no DESC, id DESC
        LIMIT 1
        """,
        (int(lesson_id),),
    ).fetchone()
```

Then:

```python
def mark_lesson_generation_failed(lesson_id: int, error_message: str) -> None:
    with get_conn() as conn:
        version = _latest_active_review_plan_version_for_lesson(conn, lesson_id)
    if not version:
        raise LookupError("review plan version not found")
    fail_review_plan_version(int(version["id"]), error_message)
```

Keep wrappers only for downstream callers that are not part of this review-plan feature. New review-plan code in `app.py` will call the version helpers directly.

- [ ] **Step 9: Enrich `get_lesson()` and `list_lessons()` from versions**

Add:

```python
def _attach_review_plan_version_summary(conn: sqlite3.Connection, lesson: dict) -> dict:
    lesson_id = int(lesson.get("id") or 0)
    current = conn.execute(
        """
        SELECT * FROM review_plan_versions
        WHERE id=?
        """,
        (int(lesson.get("current_review_plan_version_id") or 0),),
    ).fetchone()
    active = conn.execute(
        """
        SELECT * FROM review_plan_versions
        WHERE lesson_id=? AND status IN ('pending', 'queued', 'processing', 'transcribing', 'generating')
        ORDER BY version_no DESC, id DESC
        LIMIT 1
        """,
        (lesson_id,),
    ).fetchone()
    latest_failed = conn.execute(
        """
        SELECT * FROM review_plan_versions
        WHERE lesson_id=? AND status='failed'
        ORDER BY version_no DESC, id DESC
        LIMIT 1
        """,
        (lesson_id,),
    ).fetchone()
    current_version = _review_plan_version_from_row(current)
    active_version = _review_plan_version_from_row(active)
    failed_version = _review_plan_version_from_row(latest_failed)
    lesson["current_version"] = current_version
    lesson["active_version"] = active_version
    lesson["current_review_plan_version_id"] = current_version["id"] if current_version else None
    lesson["current_version_id"] = current_version["id"] if current_version else None
    lesson["current_version_no"] = current_version["version_no"] if current_version else None
    lesson["current_generated_at"] = (current_version or {}).get("completed_at") or ""
    lesson["current_status"] = (current_version or {}).get("status") or ""
    lesson["has_version_generating"] = active_version is not None
    lesson["active_version_status"] = (active_version or {}).get("status") or ""
    lesson["active_version_created_at"] = (active_version or {}).get("created_at") or ""
    lesson["latest_generation_error"] = (failed_version or {}).get("generation_error") or ""
    lesson["plan_json"] = (current_version or {}).get("plan_json") or ""
    lesson["plan"] = (current_version or {}).get("plan") or {}
    lesson["pdf_path"] = (current_version or {}).get("pdf_path") or ""
    lesson["record_status"] = lesson["active_version_status"] or lesson["current_status"] or ((failed_version or {}).get("status") or "")
    lesson["generation_error"] = lesson["latest_generation_error"]
    return lesson
```

Update `get_lesson()` to call `_attach_review_plan_version_summary(conn, dict(row))`. Update `list_lessons()` and `list_lessons_for_actor()` to attach the summary to each row before returning.

- [ ] **Step 10: Update student review task query**

In `list_student_review_tasks_for_student_account()`, replace:

```sql
              AND COALESCE(l.plan_json, '') <> ''
              AND COALESCE(l.record_status, 'ready') = 'ready'
```

with:

```sql
              AND l.current_review_plan_version_id IS NOT NULL
```

and select current version fields:

```sql
                v.plan_json AS current_plan_json,
                v.pdf_path AS current_pdf_path
```

from:

```sql
            JOIN review_plan_versions v ON v.id=l.current_review_plan_version_id
```

Then replace `lesson.get("plan_json")` and `lesson.get("pdf_path")` reads in that function with `current_plan_json` and `current_pdf_path`.

- [ ] **Step 11: Run store tests**

Run:

```bash
python -m pytest tests/test_review_plan_version_store.py tests/test_review_plan_async_store.py tests/test_student_review_tasks_api.py -q
```

Expected: all selected tests pass.

- [ ] **Step 12: Commit storage implementation**

```bash
git add lesson_manager.py tests/test_review_plan_version_store.py tests/test_review_plan_async_store.py tests/test_student_review_tasks_api.py
git commit -m "feat: store review plan versions"
```

Expected: commit succeeds with migration, store helpers, and store tests.

## Task 3: Backend API Tests

**Files:**
- Modify: `tests/test_review_plan_async_api.py`

- [ ] **Step 1: Update create tests for version output**

In `test_post_review_plan_returns_202_and_creates_pending_lesson`, replace lesson status assertions with:

```python
        lesson_id = payload["id"]
        version_id = payload["version_id"]
        lesson = lesson_manager.get_lesson(lesson_id)
        version = lesson_manager.get_review_plan_version(version_id)
        self.assertIsNotNone(lesson)
        self.assertIsNotNone(version)
        self.assertEqual(version["status"], "generating")
        self.assertEqual(version["lesson_id"], lesson_id)
        self.assertEqual(lesson["summary"], "课堂总结文本")

        mock_start_thread.assert_called_once()
        thread_kwargs = mock_start_thread.call_args.kwargs
        self.assertEqual(thread_kwargs["lesson_id"], lesson_id)
        self.assertEqual(thread_kwargs["version_id"], version_id)
```

- [ ] **Step 2: Update model override test**

Replace the old `lesson["review_chat_provider"]` assertions with:

```python
        version = lesson_manager.get_review_plan_version(payload["version_id"])
        self.assertIsNotNone(version)
        self.assertEqual(version["chat_provider"], "openai")
        self.assertEqual(version["chat_model"], "gpt-4.1")
```

- [ ] **Step 3: Update audio create test**

Replace old lesson audio context assertions with:

```python
        version = lesson_manager.get_review_plan_version(payload["version_id"])
        self.assertIsNotNone(version)
        self.assertEqual(version["status"], "transcribing")
        self.assertTrue(version["audio_path"])
        self.assertTrue(version["audio_request_key"])
        self.assertTrue(version["request_key"])
        self.assertTrue(version["request_id"])
        self.assertEqual(version["chat_provider"], "deepseek")
        self.assertEqual(version["chat_model"], "deepseek-v4-pro")
```

- [ ] **Step 4: Replace regenerate test**

Replace `test_regenerate_review_plan_requeues_existing_lesson` with:

```python
    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app._current_ai_request_key", return_value="header:regenerate-review-plan")
    @patch("app.has_review_plan_api_key", return_value=True)
    def test_regenerate_review_plan_creates_new_version_without_overwriting_current(
        self,
        _mock_has_api_key,
        _mock_request_key,
        _mock_ensure_credits,
        mock_start_thread,
    ):
        config_runtime.write_file_config({
            "review_plan_provider": "openai",
            "review_plan_model": "gpt-5.4",
        })
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结文本",
            weak_points="斜率判断",
            created_by_user_id=1,
        )
        first = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(
            first["id"],
            plan={"lesson_info": {"topic": "旧计划"}, "days": []},
            pdf_path="/tmp/old-review.pdf",
        )

        response = self.client.post(
            f"/api/review-plans/{lesson_id}/regenerate",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertEqual(payload["id"], lesson_id)
        self.assertEqual(payload["status"], "generating")
        self.assertGreater(payload["version_id"], first["id"])

        lesson = lesson_manager.get_lesson(lesson_id)
        second = lesson_manager.get_review_plan_version(payload["version_id"])
        self.assertEqual(lesson["current_review_plan_version_id"], first["id"])
        self.assertEqual(lesson["pdf_path"], "/tmp/old-review.pdf")
        self.assertEqual(second["status"], "generating")
        self.assertEqual(second["chat_provider"], "openai")
        self.assertEqual(second["chat_model"], "gpt-5.4")
        self.assertTrue(second["request_id"])

        mock_start_thread.assert_called_once()
        thread_kwargs = mock_start_thread.call_args.kwargs
        self.assertEqual(thread_kwargs["lesson_id"], lesson_id)
        self.assertEqual(thread_kwargs["version_id"], second["id"])
        self.assertEqual(thread_kwargs["request_key"], "header:regenerate-review-plan")
        self.assertEqual(thread_kwargs["request_id"], second["request_id"])
```

- [ ] **Step 5: Add list/detail/rollback/download API tests**

Add these tests to `tests/test_review_plan_async_api.py`:

```python
    def test_review_plan_list_uses_current_version_fields_and_time(self):
        first_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="第一课",
            summary="课堂总结",
            weak_points="",
            created_by_user_id=1,
        )
        first_version = lesson_manager.create_review_plan_version(lesson_id=first_id, status="generating")
        lesson_manager.complete_review_plan_version(first_version["id"], plan={"days": []}, pdf_path="/tmp/first.pdf")
        second_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-10",
            subject="数学",
            grade="初二",
            topic="第二课",
            summary="课堂总结",
            weak_points="",
            created_by_user_id=1,
        )
        second_version = lesson_manager.create_review_plan_version(lesson_id=second_id, status="generating")
        lesson_manager.complete_review_plan_version(second_version["id"], plan={"days": []}, pdf_path="/tmp/second.pdf")

        response = self.client.get("/api/review-plans", headers=self._auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        by_id = {item["id"]: item for item in payload}
        self.assertEqual(by_id[first_id]["current_version_id"], first_version["id"])
        self.assertEqual(by_id[first_id]["current_version_no"], 1)
        self.assertEqual(by_id[first_id]["current_status"], "ready")
        self.assertIn(f"/api/review-plans/{first_id}/versions/{first_version['id']}/pdf", by_id[first_id]["current_pdf_url"])
        self.assertIn("current_generated_at", by_id[first_id])

    def test_review_plan_detail_returns_versions_newest_first(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="",
            created_by_user_id=1,
        )
        first = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(first["id"], plan={"lesson_info": {"topic": "第一版"}, "days": []}, pdf_path="/tmp/v1.pdf")
        second = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.fail_review_plan_version(second["id"], "第二版失败")

        response = self.client.get(f"/api/review-plans/{lesson_id}", headers=self._auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["current_version_id"], first["id"])
        self.assertEqual([version["id"] for version in payload["versions"]], [second["id"], first["id"]])
        self.assertEqual(payload["versions"][0]["status"], "failed")
        self.assertEqual(payload["versions"][1]["status"], "ready")

    def test_make_current_switches_to_ready_old_version(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="",
            created_by_user_id=1,
        )
        first = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(first["id"], plan={"lesson_info": {"topic": "第一版"}, "days": []}, pdf_path="/tmp/v1.pdf")
        second = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(second["id"], plan={"lesson_info": {"topic": "第二版"}, "days": []}, pdf_path="/tmp/v2.pdf")

        response = self.client.post(
            f"/api/review-plans/{lesson_id}/versions/{first['id']}/make-current",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["current_version_id"], first["id"])
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["current_review_plan_version_id"], first["id"])

    def test_version_pdf_preview_and_download_use_specific_version(self):
        pdf_path = self.base / "specific-version.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nversion pdf\n%%EOF\n")
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="",
            created_by_user_id=1,
        )
        version = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(version["id"], plan={"days": []}, pdf_path=str(pdf_path))

        preview = self.client.get(
            f"/api/review-plans/{lesson_id}/versions/{version['id']}/pdf",
            headers=self._auth_headers(self.owner_token),
        )
        download = self.client.get(
            f"/api/review-plans/{lesson_id}/versions/{version['id']}/download",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.mimetype, "application/pdf")
        self.assertEqual(preview.data, pdf_path.read_bytes())
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download.headers.get("Content-Disposition", ""))
        preview.close()
        download.close()
```

- [ ] **Step 6: Run API tests and confirm expected failures**

Run:

```bash
python -m pytest tests/test_review_plan_async_api.py -q
```

Expected: failures naming missing response keys, missing `version_id`, and missing version routes.

- [ ] **Step 7: Commit API tests**

```bash
git add tests/test_review_plan_async_api.py
git commit -m "test: specify review plan version APIs"
```

Expected: commit succeeds with API tests only.

## Task 4: Backend API Implementation

**Files:**
- Modify: `app.py`
- Modify: `lesson_manager.py`

- [ ] **Step 1: Update `lesson_manager` imports in `app.py`**

Add these names to the `from lesson_manager import (...)` block:

```python
    complete_review_plan_version,
    create_review_plan_version,
    fail_review_plan_version,
    get_current_review_plan_version,
    get_review_plan_version,
    get_review_plan_version_for_lesson,
    lesson_has_active_review_plan_version,
    list_review_plan_versions,
    mark_review_plan_version_transcription_succeeded,
    set_current_review_plan_version,
```

- [ ] **Step 2: Change worker signature to accept `version_id`**

Change `_run_review_plan_generation_job()` signature:

```python
def _run_review_plan_generation_job(
    *,
    lesson_id: int,
    version_id: int,
    user: dict,
    chat_provider: str,
    chat_model: str,
    request_key: str | None = None,
    request_id: str | None = None,
    audio_path: str = "",
    audio_request_key: str | None = None,
    same_lesson_materials: list[str] | None = None,
) -> None:
```

At the start of the job, load the version:

```python
        version = get_review_plan_version_for_lesson(lesson_id, version_id)
        if not version:
            logger.warning("Review plan generation skipped: version %s for lesson %s not found", version_id, lesson_id)
            return
        record_status = str(version.get("status") or "")
```

- [ ] **Step 3: Move transcription state writes to the version**

Inside the transcription block, replace `mark_lesson_generation_failed(...)` calls with:

```python
fail_review_plan_version(version_id, "音频转录失败，请重新上传")
```

After successful transcription, replace `mark_lesson_transcription_succeeded(...)` with:

```python
mark_review_plan_version_transcription_succeeded(version_id, summary=merged_summary)
lesson = get_lesson(lesson_id)
version = get_review_plan_version_for_lesson(lesson_id, version_id)
record_status = str((version or {}).get("status") or "")
```

- [ ] **Step 4: Move AI/PDF failure and success writes to the version**

Replace worker failure calls:

```python
mark_lesson_generation_failed(lesson_id, "AI 生成失败，请稍后重试")
```

with:

```python
fail_review_plan_version(version_id, "AI 生成失败，请稍后重试")
```

Build version-specific PDF names:

```python
version_no = int((version or {}).get("version_no") or 0)
pdf_name = build_single_lesson_pdf_filename(plan, suffix=f"{lesson_id}-v{version_no or version_id}")
```

Replace success call:

```python
complete_review_plan_version(
    version_id,
    plan=plan,
    pdf_path=pdf_path,
)
```

- [ ] **Step 5: Recover interrupted version jobs**

Rewrite `_recover_interrupted_review_plan_jobs()` to iterate versions:

```python
def _recover_interrupted_review_plan_jobs() -> int:
    recovered_count = 0
    for lesson in list_lessons():
        versions = list_review_plan_versions(int(lesson["id"]))
        active_versions = [
            version for version in versions
            if str(version.get("status") or "").strip() in {"pending", "transcribing", "generating"}
        ]
        for version in active_versions:
            user_id = int(version.get("created_by_user_id") or lesson.get("created_by_user_id") or 0)
            user = get_user_by_id(user_id) if user_id else None
            if not user:
                logger.warning("Review plan recovery skipped for version %s: missing user", version.get("id"))
                continue
            audio_path = str(version.get("audio_path") or "").strip()
            if version.get("status") == "transcribing" and (not audio_path or not Path(audio_path).exists()):
                fail_review_plan_version(int(version["id"]), "音频转录中断，请重新上传")
                continue
            request_id = str(version.get("request_id") or "").strip()
            if request_id:
                try:
                    _claim_ai_request_identity(
                        organization_id=int(user["organization_id"]),
                        request_id=request_id,
                    )
                except DuplicateAiRequestError:
                    logger.warning("Review plan recovery skipped for duplicate request %s", request_id)
                    continue
            _start_review_plan_generation_thread(
                lesson_id=int(lesson["id"]),
                version_id=int(version["id"]),
                user={"id": int(user["id"]), "organization_id": int(user["organization_id"])},
                chat_provider=str(version.get("chat_provider") or "") or _default_ai_provider_name(),
                chat_model=str(version.get("chat_model") or "") or _default_chat_model_name(),
                request_key=str(version.get("request_key") or ""),
                request_id=request_id or None,
                audio_path=audio_path,
                audio_request_key=str(version.get("audio_request_key") or ""),
                same_lesson_materials=version.get("same_lesson_materials") or [],
            )
            recovered_count += 1
    return recovered_count
```

- [ ] **Step 6: Update response serializers**

Replace `_serialize_lesson_for_response()` body with version-aware fields:

```python
def _serialize_review_plan_version_for_response(lesson_id: int, version: object) -> Optional[dict]:
    if not isinstance(version, dict):
        return None
    pdf_path = str(version.get("pdf_path") or "").strip()
    pdf_available = bool(pdf_path and Path(pdf_path).exists())
    version_id = int(version.get("id") or 0)
    payload = dict(version)
    payload["pdf_available"] = pdf_available
    payload["pdf_url"] = f"/api/review-plans/{lesson_id}/versions/{version_id}/pdf" if pdf_available else ""
    payload["download_url"] = f"/api/review-plans/{lesson_id}/versions/{version_id}/download" if pdf_available else ""
    payload.pop("plan_json", None)
    return payload


def _serialize_lesson_for_response(lesson: object, *, include_versions: bool = False) -> Optional[dict]:
    if not isinstance(lesson, dict):
        return None
    serialized = dict(lesson)
    lesson_id = int(serialized.get("id") or 0)
    current_version = serialized.get("current_version") or get_current_review_plan_version(lesson_id)
    serialized_current = _serialize_review_plan_version_for_response(lesson_id, current_version)
    serialized["current_version"] = serialized_current
    serialized["current_version_id"] = (serialized_current or {}).get("id")
    serialized["current_version_no"] = (serialized_current or {}).get("version_no")
    serialized["current_status"] = (serialized_current or {}).get("status") or ""
    serialized["current_generated_at"] = (serialized_current or {}).get("completed_at") or ""
    serialized["current_pdf_url"] = (serialized_current or {}).get("pdf_url") or ""
    serialized["current_download_url"] = (serialized_current or {}).get("download_url") or ""
    serialized["pdf_path"] = str((current_version or {}).get("pdf_path") or "").strip() if serialized["current_pdf_url"] else ""
    if include_versions:
        versions = list_review_plan_versions(lesson_id)
        serialized["versions"] = [
            item for item in (
                _serialize_review_plan_version_for_response(lesson_id, version)
                for version in versions
            )
            if item is not None
        ]
    try:
        latest_run = get_latest_review_plan_run_for_lesson(lesson_id)
    except Exception:
        latest_run = None
    if latest_run:
        serialized["trace_id"] = latest_run.get("trace_id", "")
        serialized["workflow_warnings"] = latest_run.get("warnings", [])
        serialized["quality_review"] = latest_run.get("quality_review", {})
        serialized["prompt_version"] = latest_run.get("prompt_version", "")
        serialized["style_version"] = latest_run.get("style_version", "")
    creator_user_id = int(serialized.get("created_by_user_id") or 0)
    creator = get_user_by_id(creator_user_id) if creator_user_id else None
    serialized["creator_display_name"] = str((creator or {}).get("display_name") or (creator or {}).get("username") or "").strip()
    serialized["creator_username"] = str((creator or {}).get("username") or "").strip()
    return serialized
```

Update `api_lesson_get()` to call:

```python
serialized_lesson = _serialize_lesson_for_response(lesson, include_versions=True)
```

- [ ] **Step 7: Sort review plan list by current generated time**

In `_serialize_lessons_for_response()`, sort serialized rows:

```python
    return sorted(
        serialized_lessons,
        key=lambda item: (
            _dashboard_item_datetime(item, "current_generated_at", "updated_at", "created_at", "date"),
            int(item.get("id") or 0),
        ),
        reverse=True,
    )
```

- [ ] **Step 8: Update create endpoint to create version 1**

After `create_pending_lesson(...)`, add:

```python
        version = create_review_plan_version(
            lesson_id=lesson_id,
            status=initial_record_status if initial_record_status in {"transcribing", "generating"} else "generating",
            created_by_user_id=int(user["id"]),
            audio_path=audio_path,
            audio_request_key=audio_request_key or "",
            request_key=request_key,
            request_id=request_id,
            chat_provider=chat_provider,
            chat_model=chat_model,
            same_lesson_materials=same_lesson_materials,
        )
```

Pass `version_id=int(version["id"])` into `_start_review_plan_generation_thread(...)`.

Return:

```python
    return jsonify({
        "id": lesson_id,
        "version_id": int(version["id"]),
        "success": True,
        "status": version["status"],
    }), 202
```

- [ ] **Step 9: Update duplicate processed request lookup**

Replace `_find_existing_review_plan_lesson_for_request()` logic so it searches `review_plan_versions.request_id` and returns the joined lesson. Use:

```sql
SELECT l.*
FROM lessons l
JOIN review_plan_versions v ON v.lesson_id=l.id
WHERE l.organization_id=? AND v.request_id=?
ORDER BY v.id DESC
LIMIT 1
```

When returning a duplicate create response, compute status from the active/current version:

```python
status = str(existing_lesson.get("active_version_status") or existing_lesson.get("current_status") or "").strip()
```

- [ ] **Step 10: Update regenerate endpoint**

Replace the old `record_status` guard with:

```python
    if lesson_has_active_review_plan_version(lesson_id):
        return jsonify({"error": "这份复习计划正在生成中，请稍后再试"}), 409
```

After credit preflight, create a new version:

```python
        previous_version = get_current_review_plan_version(lesson_id)
        version = create_review_plan_version(
            lesson_id=lesson_id,
            status="generating",
            request_key=request_key,
            request_id=request_id,
            chat_provider=chat_provider,
            chat_model=chat_model,
            same_lesson_materials=(previous_version or {}).get("same_lesson_materials") or [],
            created_by_user_id=int(user["id"]),
        )
```

Pass `version_id=int(version["id"])` to the thread and return:

```python
    return jsonify({
        "id": lesson_id,
        "version_id": int(version["id"]),
        "success": True,
        "status": version["status"],
    }), 202
```

- [ ] **Step 11: Add version PDF routes and wrappers**

Add:

```python
def _send_review_plan_version_pdf(lesson_id: int, version_id: int, *, as_attachment: bool):
    user, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        abort(404)
    version = get_review_plan_version_for_lesson(lesson_id, version_id)
    if not version or str(version.get("status") or "") != "ready":
        abort(404)
    pdf_path = str(version.get("pdf_path") or "").strip()
    if not pdf_path or not Path(pdf_path).exists():
        abort(404)
    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=as_attachment,
        download_name=Path(pdf_path).name,
    )


@app.route("/api/review-plans/<int:lesson_id>/versions/<int:version_id>/pdf", methods=["GET"])
def api_review_plan_version_pdf_preview(lesson_id: int, version_id: int):
    return _send_review_plan_version_pdf(lesson_id, version_id, as_attachment=False)


@app.route("/api/review-plans/<int:lesson_id>/versions/<int:version_id>/download", methods=["GET"])
def api_review_plan_version_pdf_download(lesson_id: int, version_id: int):
    return _send_review_plan_version_pdf(lesson_id, version_id, as_attachment=True)
```

Update `serve_pdf()` and `download_pdf()` to resolve:

```python
    current_version = get_current_review_plan_version(lesson_id)
    if not current_version:
        abort(404)
    pdf_path = str(current_version.get("pdf_path") or "").strip()
```

- [ ] **Step 12: Add rollback endpoint**

Add:

```python
@app.route("/api/review-plans/<int:lesson_id>/versions/<int:version_id>/make-current", methods=["POST"])
def api_review_plan_version_make_current(lesson_id: int, version_id: int):
    user, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        return jsonify({"error": "not found"}), 404
    try:
        set_current_review_plan_version(lesson_id, version_id)
    except LookupError:
        return jsonify({"error": "not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    updated = get_lesson(lesson_id)
    return jsonify(_serialize_lesson_for_response(updated, include_versions=True))
```

- [ ] **Step 13: Delete all version PDFs when deleting a lesson**

In `api_lesson_delete()`, replace the single `pdf_path` unlink with:

```python
    for version in list_review_plan_versions(lesson_id):
        pdf_path = str(version.get("pdf_path") or "").strip()
        if pdf_path and Path(pdf_path).exists():
            Path(pdf_path).unlink(missing_ok=True)
```

- [ ] **Step 14: Update student PDF routes**

Update `/api/student/pdf/<lesson_id>` and `/api/student/pdf/download/<lesson_id>` to resolve through `get_current_review_plan_version(lesson_id)` and read that version's `pdf_path`.

- [ ] **Step 15: Run backend API tests**

Run:

```bash
python -m pytest tests/test_review_plan_version_store.py tests/test_review_plan_async_store.py tests/test_review_plan_async_api.py tests/test_student_review_tasks_api.py -q
```

Expected: all selected backend tests pass.

- [ ] **Step 16: Commit backend API implementation**

```bash
git add app.py lesson_manager.py tests/test_review_plan_async_api.py tests/test_student_review_tasks_api.py
git commit -m "feat: expose review plan version APIs"
```

Expected: commit succeeds with backend implementation and tests.

## Task 5: Frontend State Tests

**Files:**
- Modify: `frontend/src/reviewGenerationAsync.test.ts`

- [ ] **Step 1: Replace old normalization and status tests**

Update `frontend/src/reviewGenerationAsync.test.ts` to use this version-aware payload:

```ts
test('normalizeReviewLessonsResponse keeps current version and active generation fields', () => {
  const lessons = normalizeReviewLessonsResponse([
    {
      id: 12,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '一元一次方程',
      summary: '课堂摘要',
      weak_points: '移项',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      current_version_id: 31,
      current_version_no: 2,
      current_generated_at: '2026-05-02T12:30:00',
      current_pdf_url: '/api/review-plans/12/versions/31/pdf',
      current_download_url: '/api/review-plans/12/versions/31/download',
      current_status: 'ready',
      has_version_generating: true,
      active_version_status: 'generating',
      active_version_created_at: '2026-05-02T12:35:00',
      latest_generation_error: '',
    },
    { id: 'bad' },
  ]);

  assert.equal(lessons.length, 1);
  assert.equal(lessons[0]?.id, 12);
  assert.equal(lessons[0]?.current_version_id, 31);
  assert.equal(lessons[0]?.current_version_no, 2);
  assert.equal(lessons[0]?.current_pdf_url, '/api/review-plans/12/versions/31/pdf');
  assert.equal(lessons[0]?.has_version_generating, true);
});
```

Replace state tests with:

```ts
test('review lesson state keeps current output available while a new version generates', () => {
  const lesson = normalizeReviewLessonsResponse([
    {
      id: 13,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      current_version_id: 41,
      current_version_no: 1,
      current_pdf_url: '/api/review-plans/13/versions/41/pdf',
      current_download_url: '/api/review-plans/13/versions/41/download',
      current_status: 'ready',
      has_version_generating: true,
      active_version_status: 'generating',
      active_version_created_at: '2026-05-02T12:20:00',
    },
  ])[0];

  assert.ok(lesson);
  assert.equal(hasReviewLessonOutput(lesson), true);
  assert.equal(getReviewLessonTaskState(lesson), 'pending');
  assert.equal(isReviewLessonPending(lesson), true);
  assert.equal(getReviewLessonTaskMessage(lesson), '正在生成新版，当前 PDF 可继续使用');
});
```

Add failed-with-current test:

```ts
test('failed regeneration does not hide current output', () => {
  const lesson = normalizeReviewLessonsResponse([
    {
      id: 14,
      date: '2026-05-02',
      subject: '数学',
      grade: '七年级',
      topic: '整式',
      summary: '课堂摘要',
      weak_points: '',
      class_id: 3,
      created_at: '2026-05-02T12:00:00',
      current_version_id: 41,
      current_version_no: 1,
      current_pdf_url: '/api/review-plans/14/versions/41/pdf',
      current_download_url: '/api/review-plans/14/versions/41/download',
      current_status: 'ready',
      has_version_generating: false,
      latest_generation_error: '第二版失败',
    },
  ])[0];

  assert.ok(lesson);
  assert.equal(getReviewLessonTaskState(lesson), 'ready');
  assert.equal(getReviewLessonTaskMessage(lesson), '');
  assert.equal(hasReviewLessonOutput(lesson), true);
});
```

- [ ] **Step 2: Run frontend state tests and confirm expected failures**

Run:

```bash
npm --prefix frontend run test -- src/reviewGenerationAsync.test.ts
```

Expected: failures for missing `current_version_id`, `current_pdf_url`, and pending-new-version message behavior.

- [ ] **Step 3: Commit frontend failing state tests**

```bash
git add frontend/src/reviewGenerationAsync.test.ts
git commit -m "test: specify review plan version frontend state"
```

Expected: commit succeeds with frontend test changes only.

## Task 6: Frontend State Implementation

**Files:**
- Modify: `frontend/src/reviewGenerationAsync.ts`

- [ ] **Step 1: Replace `ReviewLessonRecord` shape**

Update the interface:

```ts
export interface ReviewLessonRecord {
  id: number;
  date: string;
  subject: string;
  grade: string;
  topic: string;
  summary: string;
  weak_points: string;
  class_id: number | null;
  created_at: string;
  updated_at?: string;
  created_by_user_id?: number | null;
  creator_display_name?: string;
  creator_username?: string;
  current_version_id: number | null;
  current_version_no: number | null;
  current_generated_at: string;
  current_pdf_url: string;
  current_download_url: string;
  current_status: string;
  has_version_generating: boolean;
  active_version_status: string;
  active_version_created_at: string;
  latest_generation_error: string;
  pdf_path: string;
  record_status?: string;
  generation_error?: string;
}
```

- [ ] **Step 2: Add boolean and date pickers**

Add:

```ts
function pickBoolean(value: unknown): boolean {
  return value === true;
}
```

- [ ] **Step 3: Update normalizer**

Inside `normalizeReviewLessonsResponse()`, map new fields:

```ts
      current_version_id: pickNullableNumber(item.current_version_id),
      current_version_no: pickNullableNumber(item.current_version_no),
      current_generated_at: pickString(item.current_generated_at),
      current_pdf_url: pickString(item.current_pdf_url),
      current_download_url: pickString(item.current_download_url),
      current_status: pickString(item.current_status),
      has_version_generating: pickBoolean(item.has_version_generating),
      active_version_status: pickString(item.active_version_status),
      active_version_created_at: pickString(item.active_version_created_at),
      latest_generation_error: pickString(item.latest_generation_error),
      pdf_path: pickString(item.pdf_path),
```

- [ ] **Step 4: Update output and state helpers**

Replace `hasReviewLessonOutput()`:

```ts
export function hasReviewLessonOutput(
  lesson: Pick<ReviewLessonRecord, 'current_pdf_url' | 'current_download_url' | 'pdf_path'>,
): boolean {
  return Boolean(
    lesson.current_pdf_url.trim()
    || lesson.current_download_url.trim()
    || lesson.pdf_path.trim(),
  );
}
```

Replace `getReviewLessonTaskState()`:

```ts
export function getReviewLessonTaskState(
  lesson: Pick<ReviewLessonRecord, 'has_version_generating' | 'active_version_status' | 'current_status' | 'current_pdf_url' | 'current_download_url' | 'pdf_path' | 'latest_generation_error'>,
): ReviewLessonTaskState {
  if (lesson.has_version_generating || ['pending', 'queued', 'processing', 'transcribing', 'generating'].includes(lesson.active_version_status.trim())) {
    return 'pending';
  }
  if (hasReviewLessonOutput(lesson)) {
    return 'ready';
  }
  if (lesson.latest_generation_error.trim()) {
    return 'failed';
  }
  if (lesson.current_status.trim() === 'ready') {
    return 'missing-output';
  }
  return 'empty';
}
```

Replace `getReviewLessonTaskMessage()` pending branch:

```ts
  if (state === 'pending') {
    const status = lesson.active_version_status?.trim() ?? '';
    const hasCurrentOutput = hasReviewLessonOutput(lesson);
    if (status === 'transcribing') {
      return hasCurrentOutput ? '新版录音转写中，当前 PDF 可继续使用' : '录音已上传，正在转写';
    }
    if (hasCurrentOutput) {
      return '正在生成新版，当前 PDF 可继续使用';
    }
    return '正在生成复习计划，可离开页面';
  }
```

- [ ] **Step 5: Update progress helper to use active version start time**

Change progress input type to include:

```ts
Pick<ReviewLessonRecord, 'active_version_status' | 'active_version_created_at' | 'has_version_generating' | 'current_pdf_url' | 'current_download_url' | 'pdf_path' | 'created_at' | 'latest_generation_error' | 'current_status'>
```

Then set:

```ts
  const status = lesson.active_version_status?.trim() ?? '';
```

and:

```ts
  const startedAtMs = options.startedAtMs ?? parseStartedAtMs(lesson.active_version_created_at || lesson.created_at);
```

- [ ] **Step 6: Run frontend state tests**

Run:

```bash
npm --prefix frontend run test -- src/reviewGenerationAsync.test.ts
```

Expected: selected frontend state tests pass.

- [ ] **Step 7: Commit frontend state implementation**

```bash
git add frontend/src/reviewGenerationAsync.ts frontend/src/reviewGenerationAsync.test.ts
git commit -m "feat: normalize review plan version state"
```

Expected: commit succeeds with state helpers and tests.

## Task 7: Frontend Detail UI Tests

**Files:**
- Modify: `frontend/src/review-generation-async.test.tsx`

- [ ] **Step 1: Update source assertions for detail view and version actions**

Replace the old regenerate immediate feedback assertion:

```ts
  assert.match(reviewGenerationSource, /record_status: nextStatus, generation_error: ''/);
```

with:

```ts
  assert.match(reviewGenerationSource, /has_version_generating: true/);
  assert.match(reviewGenerationSource, /active_version_status: nextStatus/);
```

Add:

```ts
test('review history opens lightweight version detail view', () => {
  assert.match(reviewGenerationSource, /selectedDetailLessonId/);
  assert.match(reviewGenerationSource, /<ReviewPlanDetailView/);
  assert.match(reviewGenerationSource, /title="详情"/);
  assert.match(reviewGenerationSource, /onBack=\{\(\) => setSelectedDetailLessonId\(null\)\}/);
});

test('review plan detail source fetches versions and can make a ready version current', () => {
  const detailSource = readFileSync(new URL('./features/review-generation/ReviewPlanDetailView.tsx', import.meta.url), 'utf8');
  assert.match(detailSource, /apiFetch<unknown>\(`\/api\/review-plans\/\$\{lessonId\}`\)/);
  assert.match(detailSource, /\/api\/review-plans\/\$\{lessonId\}\/versions\/\$\{version\.id\}\/make-current/);
  assert.match(detailSource, /current_pdf_url/);
  assert.match(detailSource, /版本历史/);
  assert.match(detailSource, /iframe/);
});
```

- [ ] **Step 2: Run source tests and confirm expected failures**

Run:

```bash
npm --prefix frontend run test -- src/review-generation-async.test.tsx
```

Expected: failures for missing `ReviewPlanDetailView` and source strings.

- [ ] **Step 3: Commit detail UI failing tests**

```bash
git add frontend/src/review-generation-async.test.tsx
git commit -m "test: specify review plan version detail UI"
```

Expected: commit succeeds with source tests only.

## Task 8: Frontend Detail UI Implementation

**Files:**
- Create: `frontend/src/features/review-generation/reviewPlanVersions.ts`
- Create: `frontend/src/features/review-generation/ReviewPlanDetailView.tsx`
- Modify: `frontend/src/features/review-generation/ReviewGenerationPage.tsx`

- [ ] **Step 1: Create version helper module**

Create `frontend/src/features/review-generation/reviewPlanVersions.ts`:

```ts
import { buildAuthedPath } from '../../workspaceShared';

export type ReviewPlanVersionStatus = 'transcribing' | 'generating' | 'ready' | 'failed' | string;

export interface ReviewPlanVersionRecord {
  id: number;
  lesson_id: number;
  version_no: number;
  status: ReviewPlanVersionStatus;
  generation_error: string;
  created_at: string;
  completed_at: string;
  pdf_available: boolean;
  pdf_url: string;
  download_url: string;
}

export interface ReviewPlanDetailRecord {
  id: number;
  date: string;
  subject: string;
  grade: string;
  topic: string;
  summary: string;
  weak_points: string;
  current_version_id: number | null;
  current_version_no: number | null;
  current_generated_at: string;
  current_pdf_url: string;
  current_download_url: string;
  current_status: string;
  has_version_generating: boolean;
  active_version_status: string;
  latest_generation_error: string;
  versions: ReviewPlanVersionRecord[];
}

export function normalizeReviewPlanDetail(payload: unknown): ReviewPlanDetailRecord | null {
  if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
    return null;
  }
  const record = payload as Record<string, unknown>;
  if (typeof record.id !== 'number' || !Number.isFinite(record.id)) {
    return null;
  }
  const versions = Array.isArray(record.versions)
    ? record.versions.flatMap((item) => {
      if (typeof item !== 'object' || item === null || Array.isArray(item)) {
        return [];
      }
      const version = item as Record<string, unknown>;
      if (typeof version.id !== 'number' || typeof version.version_no !== 'number') {
        return [];
      }
      return [{
        id: version.id,
        lesson_id: typeof version.lesson_id === 'number' ? version.lesson_id : record.id,
        version_no: version.version_no,
        status: typeof version.status === 'string' ? version.status : '',
        generation_error: typeof version.generation_error === 'string' ? version.generation_error : '',
        created_at: typeof version.created_at === 'string' ? version.created_at : '',
        completed_at: typeof version.completed_at === 'string' ? version.completed_at : '',
        pdf_available: version.pdf_available === true,
        pdf_url: typeof version.pdf_url === 'string' ? version.pdf_url : '',
        download_url: typeof version.download_url === 'string' ? version.download_url : '',
      }];
    })
    : [];
  return {
    id: record.id,
    date: typeof record.date === 'string' ? record.date : '',
    subject: typeof record.subject === 'string' ? record.subject : '',
    grade: typeof record.grade === 'string' ? record.grade : '',
    topic: typeof record.topic === 'string' ? record.topic : '',
    summary: typeof record.summary === 'string' ? record.summary : '',
    weak_points: typeof record.weak_points === 'string' ? record.weak_points : '',
    current_version_id: typeof record.current_version_id === 'number' ? record.current_version_id : null,
    current_version_no: typeof record.current_version_no === 'number' ? record.current_version_no : null,
    current_generated_at: typeof record.current_generated_at === 'string' ? record.current_generated_at : '',
    current_pdf_url: typeof record.current_pdf_url === 'string' ? record.current_pdf_url : '',
    current_download_url: typeof record.current_download_url === 'string' ? record.current_download_url : '',
    current_status: typeof record.current_status === 'string' ? record.current_status : '',
    has_version_generating: record.has_version_generating === true,
    active_version_status: typeof record.active_version_status === 'string' ? record.active_version_status : '',
    latest_generation_error: typeof record.latest_generation_error === 'string' ? record.latest_generation_error : '',
    versions,
  };
}

export function getReviewPlanVersionLabel(version: Pick<ReviewPlanVersionRecord, 'status'>): string {
  if (version.status === 'ready') {
    return '已生成';
  }
  if (version.status === 'failed') {
    return '失败';
  }
  if (version.status === 'transcribing') {
    return '转写中';
  }
  return '生成中';
}

export function canMakeReviewPlanVersionCurrent(
  detail: Pick<ReviewPlanDetailRecord, 'current_version_id'>,
  version: Pick<ReviewPlanVersionRecord, 'id' | 'status'>,
): boolean {
  return version.status === 'ready' && version.id !== detail.current_version_id;
}

export function authedReviewPlanUrl(path: string): string {
  return buildAuthedPath(path);
}
```

- [ ] **Step 2: Create detail view component**

Create `frontend/src/features/review-generation/ReviewPlanDetailView.tsx`:

```tsx
import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, Download, Eye, RefreshCw, RotateCcw } from 'lucide-react';

import { apiFetch, cn, workspacePrimaryButtonClass, workspaceSecondaryButtonClass } from '../../workspaceShared';
import {
  authedReviewPlanUrl,
  canMakeReviewPlanVersionCurrent,
  getReviewPlanVersionLabel,
  normalizeReviewPlanDetail,
  type ReviewPlanDetailRecord,
  type ReviewPlanVersionRecord,
} from './reviewPlanVersions';

type ReviewPlanDetailViewProps = {
  lessonId: number;
  onBack: () => void;
  onChanged: () => void;
  onRegenerate: () => Promise<void>;
};

function versionTimeLabel(version: ReviewPlanVersionRecord): string {
  return version.completed_at || version.created_at || '-';
}

export function ReviewPlanDetailView({ lessonId, onBack, onChanged, onRegenerate }: ReviewPlanDetailViewProps) {
  const [detail, setDetail] = useState<ReviewPlanDetailRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [actingVersionId, setActingVersionId] = useState<number | null>(null);
  const [error, setError] = useState('');

  const load = useCallback((quiet = false) => {
    if (!quiet) {
      setLoading(true);
    }
    setError('');
    return apiFetch<unknown>(`/api/review-plans/${lessonId}`)
      .then((payload) => {
        const next = normalizeReviewPlanDetail(payload);
        if (!next) {
          throw new Error('复习计划详情格式异常');
        }
        setDetail(next);
      })
      .catch((nextError) => {
        setError(nextError instanceof Error ? nextError.message : '详情加载失败');
      })
      .finally(() => {
        if (!quiet) {
          setLoading(false);
        }
      });
  }, [lessonId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleMakeCurrent = async (version: ReviewPlanVersionRecord) => {
    setActingVersionId(version.id);
    try {
      await apiFetch(`/api/review-plans/${lessonId}/versions/${version.id}/make-current`, { method: 'POST' });
      await load(true);
      onChanged();
    } finally {
      setActingVersionId(null);
    }
  };

  const handleRegenerate = async () => {
    await onRegenerate();
    await load(true);
  };

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200/70 bg-white p-6 text-sm text-slate-500 dark:border-white/10 dark:bg-slate-950 dark:text-slate-300">
        正在加载详情
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="rounded-2xl border border-slate-200/70 bg-white p-6 dark:border-white/10 dark:bg-slate-950">
        <button type="button" onClick={onBack} className={workspaceSecondaryButtonClass}>
          <ArrowLeft size={16} /> 返回
        </button>
        <p className="mt-4 text-sm text-rose-600 dark:text-rose-300">{error || '复习计划不存在'}</p>
      </div>
    );
  }

  const currentPdfUrl = detail.current_pdf_url ? authedReviewPlanUrl(detail.current_pdf_url) : '';
  const currentDownloadUrl = detail.current_download_url ? authedReviewPlanUrl(detail.current_download_url) : '';

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button type="button" onClick={onBack} className={workspaceSecondaryButtonClass}>
          <ArrowLeft size={16} /> 返回
        </button>
        <button type="button" onClick={() => void handleRegenerate()} className={workspacePrimaryButtonClass}>
          <RefreshCw size={16} /> 重新生成
        </button>
      </div>

      <section className="rounded-2xl border border-slate-200/70 bg-white p-5 dark:border-white/10 dark:bg-slate-950">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400 dark:text-slate-500">{detail.subject} · {detail.grade}</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-950 dark:text-white">{detail.topic || '复习计划'}</h3>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              当前版本 V{detail.current_version_no ?? '-'} · {detail.current_generated_at || '暂无生成时间'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {currentPdfUrl && (
              <a href={currentPdfUrl} target="_blank" rel="noreferrer" className={workspaceSecondaryButtonClass}>
                <Eye size={16} /> 预览
              </a>
            )}
            {currentDownloadUrl && (
              <a href={currentDownloadUrl} className={workspaceSecondaryButtonClass}>
                <Download size={16} /> 下载
              </a>
            )}
          </div>
        </div>

        {currentPdfUrl ? (
          <iframe
            title="复习计划 PDF 预览"
            src={currentPdfUrl}
            className="mt-5 h-[68vh] w-full rounded-xl border border-slate-200/70 bg-slate-50 dark:border-white/10 dark:bg-slate-900"
          />
        ) : (
          <div className="mt-5 rounded-xl border border-dashed border-slate-300 px-4 py-10 text-center text-sm text-slate-500 dark:border-white/15 dark:text-slate-400">
            当前版本没有可预览的 PDF
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200/70 bg-white p-5 dark:border-white/10 dark:bg-slate-950">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-950 dark:text-white">版本历史</h3>
          {detail.has_version_generating && <span className="text-sm text-amber-600 dark:text-amber-300">正在生成新版</span>}
        </div>
        <div className="divide-y divide-slate-200/70 dark:divide-white/10">
          {detail.versions.map((version) => {
            const isCurrent = version.id === detail.current_version_id;
            const canMakeCurrent = canMakeReviewPlanVersionCurrent(detail, version);
            return (
              <div key={version.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    V{version.version_no}
                    <span className={cn('ml-2 text-xs font-medium', isCurrent ? 'text-sky-600 dark:text-sky-300' : 'text-slate-500 dark:text-slate-400')}>
                      {isCurrent ? '当前版本' : getReviewPlanVersionLabel(version)}
                    </span>
                  </p>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{versionTimeLabel(version)}</p>
                  {version.status === 'failed' && (
                    <p className="mt-1 text-xs text-rose-600 dark:text-rose-300">{version.generation_error || '生成失败'}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {version.pdf_available && version.pdf_url && (
                    <a href={authedReviewPlanUrl(version.pdf_url)} target="_blank" rel="noreferrer" className={workspaceSecondaryButtonClass}>
                      <Eye size={16} /> 预览
                    </a>
                  )}
                  {version.pdf_available && version.download_url && (
                    <a href={authedReviewPlanUrl(version.download_url)} className={workspaceSecondaryButtonClass}>
                      <Download size={16} /> 下载
                    </a>
                  )}
                  {canMakeCurrent && (
                    <button
                      type="button"
                      onClick={() => void handleMakeCurrent(version)}
                      disabled={actingVersionId === version.id}
                      className={workspaceSecondaryButtonClass}
                    >
                      <RotateCcw size={16} /> 设为当前
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Import detail view in page**

Update `ReviewGenerationPage.tsx` imports:

```tsx
import { CheckCircle2, Download, Eye, FileText, Info, PlusCircle, RefreshCw, Trash2, X } from 'lucide-react';
import { ReviewPlanDetailView } from './ReviewPlanDetailView';
```

- [ ] **Step 4: Add selected detail state**

Inside `ReviewDocumentHistory`, add:

```tsx
  const [selectedDetailLessonId, setSelectedDetailLessonId] = useState<number | null>(null);
```

Before the history list return content, add:

```tsx
  if (selectedDetailLessonId !== null) {
    const selectedLesson = lessons.find((lesson) => lesson.id === selectedDetailLessonId) ?? null;
    return (
      <ReviewPlanDetailView
        lessonId={selectedDetailLessonId}
        onBack={() => setSelectedDetailLessonId(null)}
        onChanged={() => void load(true)}
        onRegenerate={() => selectedLesson ? handleRegenerate(selectedLesson) : Promise.resolve()}
      />
    );
  }
```

- [ ] **Step 5: Update date label and actions**

Change `getLessonDateTimeLabel()` to prefer current generation time:

```tsx
  const timestamp = lesson.current_generated_at || lesson.created_at;
```

Change list preview/download links:

```tsx
href={buildAuthedPath(lesson.current_pdf_url)}
```

and:

```tsx
href={buildAuthedPath(lesson.current_download_url)}
```

Add details button before regenerate:

```tsx
                      <button
                        type="button"
                        onClick={() => setSelectedDetailLessonId(lesson.id)}
                        className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200/80 bg-white text-slate-500 transition-colors hover:border-slate-300 hover:text-slate-900 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white"
                        title="详情"
                        aria-label="详情"
                      >
                        <Info size={16} />
                      </button>
```

- [ ] **Step 6: Update regenerate optimistic state**

Replace the optimistic state update with:

```tsx
      setLessons((current) => current.map((item) => (
        item.id === lesson.id
          ? {
            ...item,
            has_version_generating: true,
            active_version_status: nextStatus,
            active_version_created_at: new Date(startedAtMs).toISOString(),
            latest_generation_error: '',
          }
          : item
      )));
```

- [ ] **Step 7: Run frontend tests and typecheck**

Run:

```bash
npm --prefix frontend run test -- src/reviewGenerationAsync.test.ts src/review-generation-async.test.tsx
npm --prefix frontend run lint
```

Expected: selected tests and `tsc --noEmit` pass.

- [ ] **Step 8: Commit frontend UI**

```bash
git add frontend/src/reviewGenerationAsync.ts frontend/src/reviewGenerationAsync.test.ts frontend/src/review-generation-async.test.tsx frontend/src/features/review-generation/ReviewGenerationPage.tsx frontend/src/features/review-generation/ReviewPlanDetailView.tsx frontend/src/features/review-generation/reviewPlanVersions.ts
git commit -m "feat: add review plan version detail UI"
```

Expected: commit succeeds with frontend implementation and tests.

## Task 9: Cleanup, Full Verification, And Handoff

**Files:**
- Modify: `handoff.md`

- [ ] **Step 1: Search for stale DB field assumptions**

Run:

```bash
rg -n "lessons\\.(plan_json|pdf_path|record_status|generation_error|review_audio_path|review_request_key|review_request_id|review_chat_provider|review_chat_model|review_same_lesson_materials_json)|INSERT INTO lessons[\\s\\S]{0,200}(plan_json|pdf_path|record_status)" app.py lesson_manager.py tests frontend/src
```

Expected: no SQL reads/writes against removed `lessons` artifact columns. Plain response compatibility keys like `lesson["pdf_path"]` may remain only when they come from `get_lesson()` computed version fields.

- [ ] **Step 2: Add a proof script**

Create `/tmp/proof_review_plan_version_history_20260623.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /Users/xiaodi/Desktop/01_星润与复习计划/xingrun.web

echo "== branch =="
git branch --show-current

echo "== status =="
git status --short --branch

echo "== backend tests =="
python -m pytest \
  tests/test_review_plan_version_store.py \
  tests/test_review_plan_async_store.py \
  tests/test_review_plan_async_api.py \
  tests/test_student_review_tasks_api.py \
  -q

echo "== frontend focused tests =="
npm --prefix frontend run test -- \
  src/reviewGenerationAsync.test.ts \
  src/review-generation-async.test.tsx

echo "== frontend typecheck =="
npm --prefix frontend run lint

echo "== stale lessons artifact SQL scan =="
if rg -n "lessons\\.(plan_json|pdf_path|record_status|generation_error|review_audio_path|review_request_key|review_request_id|review_chat_provider|review_chat_model|review_same_lesson_materials_json)|INSERT INTO lessons[\\s\\S]{0,200}(plan_json|pdf_path|record_status)" app.py lesson_manager.py tests frontend/src; then
  echo "stale SQL references found"
  exit 1
else
  echo "no stale lessons artifact SQL references"
fi

echo "== diff stat =="
git diff --stat HEAD
```

Run:

```bash
bash /tmp/proof_review_plan_version_history_20260623.sh
```

Expected: backend tests pass, frontend focused tests pass, frontend typecheck passes, stale SQL scan prints `no stale lessons artifact SQL references`.

- [ ] **Step 3: Update `handoff.md`**

Add one top `当前状态` line:

```markdown
- 2026-06-23 已完成“复习计划版本历史与重新生成不覆盖”实现：`lessons` 已通过迁移移除旧生成产物字段，生成产物进入 `review_plan_versions`；新建/重新生成会创建版本，成功自动切当前版，失败保留旧当前版；列表显示当前版本生成时间，详情页支持 PDF 预览、下载、版本历史和设为当前。验证脚本：`/tmp/proof_review_plan_version_history_20260623.sh`。
```

- [ ] **Step 4: Commit cleanup and handoff**

```bash
git add handoff.md
git commit -m "docs: record review plan version history handoff"
```

Expected: commit succeeds.

- [ ] **Step 5: Merge back to develop after all tests pass**

Run:

```bash
git fetch origin
git checkout develop
git rev-list --left-right --count origin/develop...develop
git merge --ff-only origin/develop
git merge --no-ff codex/review-plan-version-history-design
```

Expected: `origin/develop...develop` prints `0 0` before merge or `git merge --ff-only origin/develop` fast-forwards local develop. Feature merge completes without conflicts.

- [ ] **Step 6: Run proof on `develop`**

Run:

```bash
bash /tmp/proof_review_plan_version_history_20260623.sh
```

Expected: all checks pass on `develop`.

- [ ] **Step 7: Push develop**

```bash
git push origin develop
```

Expected: `develop` is pushed to GitHub. Do not merge to `master` in this task.

- [ ] **Step 8: Delete merged feature branch**

Run:

```bash
git branch -d codex/review-plan-version-history-design
```

Expected: local branch deletes after successful merge. If a remote feature branch exists, delete it with `git push origin --delete codex/review-plan-version-history-design`.

## Self-Review

- Spec coverage: storage migration, regeneration as new version, old current PDF during generation, failed regeneration preserving current, list current generated time, lightweight detail page, rollback, delete all version PDFs, and removed `lessons` artifact columns are each mapped to tasks.
- Placeholder scan: this plan contains concrete file paths, commands, snippets, and expected outputs; it avoids unresolved placeholders.
- Type consistency: backend uses `version_id`, `current_version_id`, `current_version_no`, `current_generated_at`, `has_version_generating`, `active_version_status`, and `latest_generation_error`; frontend uses the same names.
