# Targeted Weekly Practice Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `生成并下载一周练习包` flow that generates a class zip with one seven-day targeted wrong-question practice PDF per student.

**Architecture:** Add a practice-pack job layer above the existing wrong-question practice sheet machinery. The job stores class-level generation state, selects historical questions by topic or reason, uses AI to create same-reason variant questions when real questions are insufficient, renders per-student PDFs with an answer section, and zips successful PDFs for download. Keep the existing weekly followup endpoints available while the new UI uses the practice-pack endpoints.

**Tech Stack:** Flask, SQLite through `lesson_manager.py`, existing OpenAI-compatible helpers in `ai_processor.py`, browser PDF rendering through `pdf_engine.py` and `frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs`, React/Vite TypeScript tests, Python `unittest`.

---

## File Structure

- Create `tests/test_wrong_question_practice_packs.py`
  - Covers pack job storage, target matching, scheduling, API permissions, idempotency, worker success, worker partial failure, and zip download behavior.
- Modify `lesson_manager.py`
  - Add `wrong_question_practice_pack_jobs` and `wrong_question_practice_pack_job_students`.
  - Add pack job CRUD helpers.
  - Add targeted historical wrong-question candidate query helpers.
  - Add seven-day scheduling helpers.
- Modify `ai_processor.py`
  - Add prompts and normalization for same-reason variant question generation and review.
- Modify `tests/test_ai_processor_prompt.py`
  - Assert new prompts require same-reason variants, answer keys, key steps, and review checks.
- Modify `pdf_engine.py`
  - Extend practice-sheet PDF payload to include seven-day plan metadata and answer items.
- Modify `frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs`
  - Render daily sections and an answer section for practice-pack PDFs while preserving current single-sheet rendering.
- Modify `app.py`
  - Add practice-pack routes.
  - Add background worker helpers for pack generation.
  - Add class zip generation and download.
- Modify `frontend/src/smartWrongQuestions.ts`
  - Add practice-pack types, normalizers, and endpoint builders.
- Modify `frontend/src/SmartWrongQuestionsPage.tsx`
  - Replace the two weekly practice buttons with mode, target, volume controls and a single `生成并下载一周练习包` action.
  - Show job status, student results, download, and retry affordances.
- Modify `frontend/src/smart-wrong-questions.test.ts`
  - Cover path builders, response normalization, and the visible interaction strings.
- Modify `handoff.md`
  - Record implementation status, proof, and remaining manual smoke checks.

## Shared Constants

Use these exact values in Python and TypeScript:

```python
PRACTICE_PACK_MODE_OPTIONS = {"topic", "reason"}
PRACTICE_PACK_VOLUME_COUNTS = {"light": 5, "standard": 10, "intensive": 15}
PRACTICE_PACK_JOB_STATUSES = {"pending", "running", "ready", "partial_failed", "failed"}
PRACTICE_PACK_STUDENT_STATUSES = {"pending", "running", "ready", "skipped", "failed"}
```

```ts
const PRACTICE_PACK_MODES = ['topic', 'reason'] as const;
const PRACTICE_PACK_VOLUMES = ['light', 'standard', 'intensive'] as const;
```

Use these labels in the frontend:

```ts
const practicePackModeOptions = [
  { value: 'topic', label: '按专题/知识点' },
  { value: 'reason', label: '按错因' },
];

const practicePackVolumeOptions = [
  { value: 'light', label: '轻量 5题' },
  { value: 'standard', label: '标准 10题' },
  { value: 'intensive', label: '强化 15题' },
];
```

---

### Task 1: Pack Job Storage

**Files:**
- Create: `tests/test_wrong_question_practice_packs.py`
- Modify: `lesson_manager.py`

- [ ] **Step 1: Write failing storage tests**

Create `tests/test_wrong_question_practice_packs.py` with:

```python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager


class WrongQuestionPracticePackStorageTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.owner = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class("七年级 5 班", subject="数学", grade="七年级")
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner["id"])
        self.student = lesson_manager.create_student_for_class(self.class_id, "王睿博")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_get_and_find_active_pack_job(self):
        job = lesson_manager.create_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=self.owner["id"],
            mode="reason",
            target="去分母漏乘",
            volume="standard",
        )

        self.assertEqual(job["status"], "pending")
        self.assertEqual(job["mode"], "reason")
        self.assertEqual(job["target"], "去分母漏乘")
        self.assertEqual(job["volume"], "standard")
        self.assertEqual(job["requested_question_count"], 10)

        loaded = lesson_manager.get_wrong_question_practice_pack_job(job["id"])
        self.assertEqual(loaded["id"], job["id"])

        active = lesson_manager.find_active_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=self.owner["id"],
            mode="reason",
            target="去分母漏乘",
            volume="standard",
        )
        self.assertEqual(active["id"], job["id"])

    def test_pack_job_student_rows_are_serialized(self):
        job = lesson_manager.create_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=self.owner["id"],
            mode="topic",
            target="几何",
            volume="light",
        )
        saved = lesson_manager.upsert_wrong_question_practice_pack_job_student(
            job_id=job["id"],
            student_id=self.student["id"],
            student_name_snapshot="王睿博",
            status="ready",
            requested_question_count=5,
            real_question_count=3,
            variant_question_count=2,
            pdf_path="/tmp/wang.pdf",
            generation_error="",
        )

        loaded = lesson_manager.get_wrong_question_practice_pack_job(job["id"])
        self.assertEqual(saved["status"], "ready")
        self.assertEqual(len(loaded["students"]), 1)
        self.assertEqual(loaded["students"][0]["student_name_snapshot"], "王睿博")
        self.assertEqual(loaded["students"][0]["real_question_count"], 3)
        self.assertEqual(loaded["students"][0]["variant_question_count"], 2)

    def test_mark_pack_job_status_and_zip_path(self):
        job = lesson_manager.create_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=self.owner["id"],
            mode="topic",
            target="计算",
            volume="intensive",
        )
        updated = lesson_manager.mark_wrong_question_practice_pack_job_status(
            job["id"],
            status="ready",
            zip_path="/tmp/class.zip",
            generation_error="",
        )

        self.assertEqual(updated["status"], "ready")
        self.assertEqual(updated["zip_path"], "/tmp/class.zip")
        self.assertEqual(updated["requested_question_count"], 15)
```

- [ ] **Step 2: Run storage tests to verify failure**

Run:

```bash
python -m unittest tests.test_wrong_question_practice_packs.WrongQuestionPracticePackStorageTestCase -v
```

Expected: FAIL with missing helper names such as `create_wrong_question_practice_pack_job`.

- [ ] **Step 3: Add pack job tables**

In `lesson_manager.init_db()`, immediately after `wrong_question_practice_sheet_items`, add:

```python
        CREATE TABLE IF NOT EXISTS wrong_question_practice_pack_jobs (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id           INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            class_id                  INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            created_by                INTEGER NOT NULL REFERENCES users(id),
            mode                      TEXT NOT NULL,
            target                    TEXT NOT NULL DEFAULT '',
            volume                    TEXT NOT NULL,
            requested_question_count  INTEGER NOT NULL DEFAULT 0,
            status                    TEXT NOT NULL DEFAULT 'pending',
            zip_path                  TEXT NOT NULL DEFAULT '',
            generation_error          TEXT NOT NULL DEFAULT '',
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS wrong_question_practice_pack_job_students (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id                    INTEGER NOT NULL REFERENCES wrong_question_practice_pack_jobs(id) ON DELETE CASCADE,
            student_id                INTEGER NOT NULL REFERENCES students(id),
            student_name_snapshot     TEXT NOT NULL DEFAULT '',
            status                    TEXT NOT NULL DEFAULT 'pending',
            requested_question_count  INTEGER NOT NULL DEFAULT 0,
            real_question_count       INTEGER NOT NULL DEFAULT 0,
            variant_question_count    INTEGER NOT NULL DEFAULT 0,
            pdf_path                  TEXT NOT NULL DEFAULT '',
            generation_error          TEXT NOT NULL DEFAULT '',
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(job_id, student_id)
        );
```

Add indexes near the existing wrong-question indexes:

```python
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wrong_question_practice_pack_jobs_lookup
            ON wrong_question_practice_pack_jobs (
                organization_id,
                class_id,
                created_by,
                mode,
                target,
                volume,
                status,
                id
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wrong_question_practice_pack_students_job
            ON wrong_question_practice_pack_job_students (job_id, student_id)
            """
        )
```

- [ ] **Step 4: Add storage constants and serializers**

Near the wrong-question practice sheet helpers in `lesson_manager.py`, add:

```python
PRACTICE_PACK_MODE_OPTIONS = {"topic", "reason"}
PRACTICE_PACK_VOLUME_COUNTS = {"light": 5, "standard": 10, "intensive": 15}
PRACTICE_PACK_JOB_STATUSES = {"pending", "running", "ready", "partial_failed", "failed"}
PRACTICE_PACK_STUDENT_STATUSES = {"pending", "running", "ready", "skipped", "failed"}


def _normalize_practice_pack_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized not in PRACTICE_PACK_MODE_OPTIONS:
        raise ValueError("mode must be topic or reason")
    return normalized


def _normalize_practice_pack_volume(volume: str) -> str:
    normalized = str(volume or "").strip().lower()
    if normalized not in PRACTICE_PACK_VOLUME_COUNTS:
        raise ValueError("volume must be light, standard or intensive")
    return normalized


def _serialize_wrong_question_practice_pack_job_row(row: sqlite3.Row | None) -> Optional[dict]:
    if not row:
        return None
    payload = dict(row)
    payload["requested_question_count"] = int(payload.get("requested_question_count") or 0)
    return payload


def _serialize_wrong_question_practice_pack_student_row(row: sqlite3.Row | None) -> Optional[dict]:
    if not row:
        return None
    payload = dict(row)
    for key in ("requested_question_count", "real_question_count", "variant_question_count"):
        payload[key] = int(payload.get(key) or 0)
    return payload
```

- [ ] **Step 5: Add storage helpers**

Add these helpers after `mark_wrong_question_practice_sheet_failed()`:

```python
def create_wrong_question_practice_pack_job(
    *,
    organization_id: int,
    class_id: int,
    created_by: int,
    mode: str,
    target: str,
    volume: str,
) -> dict:
    normalized_mode = _normalize_practice_pack_mode(mode)
    normalized_volume = _normalize_practice_pack_volume(volume)
    normalized_target = str(target or "").strip()
    if not normalized_target:
        raise ValueError("target is required")
    requested_question_count = PRACTICE_PACK_VOLUME_COUNTS[normalized_volume]
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO wrong_question_practice_pack_jobs (
                organization_id, class_id, created_by, mode, target, volume,
                requested_question_count, status, zip_path, generation_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', '', '')
            """,
            (
                int(organization_id or 0),
                int(class_id or 0),
                int(created_by or 0),
                normalized_mode,
                normalized_target,
                normalized_volume,
                requested_question_count,
            ),
        )
        row = conn.execute(
            "SELECT * FROM wrong_question_practice_pack_jobs WHERE id=?",
            (int(cursor.lastrowid),),
        ).fetchone()
    serialized = _serialize_wrong_question_practice_pack_job_row(row)
    return serialized if serialized is not None else {}


def get_wrong_question_practice_pack_job(job_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM wrong_question_practice_pack_jobs WHERE id=?",
            (int(job_id or 0),),
        ).fetchone()
        if not row:
            return None
        student_rows = conn.execute(
            """
            SELECT *
            FROM wrong_question_practice_pack_job_students
            WHERE job_id=?
            ORDER BY student_name_snapshot ASC, student_id ASC
            """,
            (int(job_id or 0),),
        ).fetchall()
    job = _serialize_wrong_question_practice_pack_job_row(row)
    if job is None:
        return None
    job["students"] = [
        item
        for item in (_serialize_wrong_question_practice_pack_student_row(student_row) for student_row in student_rows)
        if item is not None
    ]
    return job


def find_active_wrong_question_practice_pack_job(
    *,
    organization_id: int,
    class_id: int,
    created_by: int,
    mode: str,
    target: str,
    volume: str,
) -> Optional[dict]:
    normalized_mode = _normalize_practice_pack_mode(mode)
    normalized_volume = _normalize_practice_pack_volume(volume)
    normalized_target = str(target or "").strip()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM wrong_question_practice_pack_jobs
            WHERE organization_id=?
              AND class_id=?
              AND created_by=?
              AND mode=?
              AND target=?
              AND volume=?
              AND status IN ('pending', 'running', 'ready', 'partial_failed')
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                int(organization_id or 0),
                int(class_id or 0),
                int(created_by or 0),
                normalized_mode,
                normalized_target,
                normalized_volume,
            ),
        ).fetchone()
    if not row:
        return None
    return get_wrong_question_practice_pack_job(int(row["id"]))


def mark_wrong_question_practice_pack_job_status(
    job_id: int,
    *,
    status: str,
    zip_path: str = "",
    generation_error: str = "",
) -> Optional[dict]:
    normalized_status = str(status or "").strip()
    if normalized_status not in PRACTICE_PACK_JOB_STATUSES:
        raise ValueError("invalid practice pack job status")
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE wrong_question_practice_pack_jobs
            SET status=?, zip_path=?, generation_error=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (
                normalized_status,
                str(zip_path or "").strip(),
                str(generation_error or "").strip(),
                int(job_id or 0),
            ),
        )
    return get_wrong_question_practice_pack_job(job_id)


def upsert_wrong_question_practice_pack_job_student(
    *,
    job_id: int,
    student_id: int,
    student_name_snapshot: str,
    status: str,
    requested_question_count: int,
    real_question_count: int = 0,
    variant_question_count: int = 0,
    pdf_path: str = "",
    generation_error: str = "",
) -> dict:
    normalized_status = str(status or "").strip()
    if normalized_status not in PRACTICE_PACK_STUDENT_STATUSES:
        raise ValueError("invalid practice pack student status")
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO wrong_question_practice_pack_job_students (
                job_id, student_id, student_name_snapshot, status, requested_question_count,
                real_question_count, variant_question_count, pdf_path, generation_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id, student_id)
            DO UPDATE SET
                student_name_snapshot=excluded.student_name_snapshot,
                status=excluded.status,
                requested_question_count=excluded.requested_question_count,
                real_question_count=excluded.real_question_count,
                variant_question_count=excluded.variant_question_count,
                pdf_path=excluded.pdf_path,
                generation_error=excluded.generation_error,
                updated_at=datetime('now','localtime')
            """,
            (
                int(job_id or 0),
                int(student_id or 0),
                str(student_name_snapshot or "").strip(),
                normalized_status,
                int(requested_question_count or 0),
                int(real_question_count or 0),
                int(variant_question_count or 0),
                str(pdf_path or "").strip(),
                str(generation_error or "").strip(),
            ),
        )
        row = conn.execute(
            """
            SELECT *
            FROM wrong_question_practice_pack_job_students
            WHERE job_id=? AND student_id=?
            """,
            (int(job_id or 0), int(student_id or 0)),
        ).fetchone()
    serialized = _serialize_wrong_question_practice_pack_student_row(row)
    return serialized if serialized is not None else {}
```

- [ ] **Step 6: Run storage tests to verify pass**

Run:

```bash
python -m unittest tests.test_wrong_question_practice_packs.WrongQuestionPracticePackStorageTestCase -v
```

Expected: PASS.

- [ ] **Step 7: Commit storage**

Run:

```bash
git add lesson_manager.py tests/test_wrong_question_practice_packs.py
git commit -m "feat: add wrong question practice pack storage"
```

---

### Task 2: Targeted Candidate Selection and Seven-Day Scheduling

**Files:**
- Modify: `tests/test_wrong_question_practice_packs.py`
- Modify: `lesson_manager.py`

- [ ] **Step 1: Add failing candidate and schedule tests**

Append to `tests/test_wrong_question_practice_packs.py`:

```python
class WrongQuestionPracticePackCandidateTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.owner = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class("七年级 5 班", subject="数学", grade="七年级")
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner["id"])
        self.student = lesson_manager.create_student_for_class(self.class_id, "王睿博")
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-practice-pack-candidates")
        self.binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _record(self, *, topic_category: str, primary_error_type: str, reason: str, question_text: str):
        return lesson_manager.create_wechat_wrong_question_submission(
            binding_id=self.binding["id"],
            image_url=f"https://files.example.com/{topic_category}-{primary_error_type}.png",
            child_raw_reason_text=reason,
            primary_error_type=primary_error_type,
            secondary_error_summary=reason,
            topic_category=topic_category,
            recognition_status="recognized",
            question_text=question_text,
        )

    def test_topic_mode_selects_historical_matching_records_without_current_week_limit(self):
        geometry = self._record(
            topic_category="几何",
            primary_error_type="方法问题",
            reason="辅助线入口没找准",
            question_text="如图，证明角相等。",
        )
        self._record(
            topic_category="计算",
            primary_error_type="细节问题",
            reason="符号漏写",
            question_text="计算 -2+5。",
        )

        candidates = lesson_manager.list_targeted_wrong_question_practice_candidates(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            student_id=self.student["id"],
            mode="topic",
            target="几何",
            limit=10,
        )

        self.assertEqual([item["id"] for item in candidates], [geometry["id"]])

    def test_reason_mode_matches_specific_reason_and_does_not_cross_fill(self):
        denominator = self._record(
            topic_category="计算",
            primary_error_type="知识点问题",
            reason="解方程去分母时右边没有同乘",
            question_text="解方程 (x-1)/2=3。",
        )
        self._record(
            topic_category="计算",
            primary_error_type="审题问题",
            reason="题目问法看漏",
            question_text="求 x 的取值范围。",
        )

        candidates = lesson_manager.list_targeted_wrong_question_practice_candidates(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            student_id=self.student["id"],
            mode="reason",
            target="去分母",
            limit=10,
        )

        self.assertEqual([item["id"] for item in candidates], [denominator["id"]])

    def test_schedule_places_real_questions_before_variants_across_seven_days(self):
        items = [
            {"practice_item_id": "real-1", "item_type": "real"},
            {"practice_item_id": "real-2", "item_type": "real"},
            {"practice_item_id": "variant-1", "item_type": "variant"},
            {"practice_item_id": "variant-2", "item_type": "variant"},
            {"practice_item_id": "variant-3", "item_type": "variant"},
        ]

        schedule = lesson_manager.build_wrong_question_practice_pack_schedule(items, start_date="2026-05-20")

        self.assertEqual(len(schedule), 7)
        self.assertEqual(schedule[0]["date"], "2026-05-20")
        self.assertEqual(schedule[0]["items"][0]["practice_item_id"], "real-1")
        self.assertEqual(schedule[1]["items"][0]["practice_item_id"], "real-2")
        scheduled_ids = [
            item["practice_item_id"]
            for day in schedule
            for item in day["items"]
        ]
        self.assertEqual(scheduled_ids, ["real-1", "real-2", "variant-1", "variant-2", "variant-3"])
```

- [ ] **Step 2: Run candidate tests to verify failure**

Run:

```bash
python -m unittest tests.test_wrong_question_practice_packs.WrongQuestionPracticePackCandidateTestCase -v
```

Expected: FAIL with missing `list_targeted_wrong_question_practice_candidates`.

- [ ] **Step 3: Add target matching helpers**

In `lesson_manager.py`, near `_is_wrong_question_candidate_for_week`, add:

```python
def _practice_pack_target_text(row: sqlite3.Row | dict) -> str:
    def value(key: str) -> str:
        if isinstance(row, sqlite3.Row):
            return str(row[key] or "") if key in row.keys() else ""
        return str(row.get(key) or "")

    return " ".join(
        part.strip()
        for part in (
            value("topic_category"),
            value("primary_error_type"),
            value("secondary_error_summary"),
            value("child_raw_reason_text"),
            value("child_reason_core_issue"),
            value("child_reason_key_omission"),
            value("child_reason_next_step"),
            value("teacher_comment"),
            value("question_text"),
        )
        if part.strip()
    )


def _practice_pack_record_matches_target(row: sqlite3.Row, *, mode: str, target: str) -> bool:
    normalized_mode = _normalize_practice_pack_mode(mode)
    normalized_target = str(target or "").strip()
    if not normalized_target:
        return False
    if normalized_mode == "topic":
        topic = normalize_primary_wrong_question_topic_category(str(row["topic_category"] or ""))
        return normalized_target in topic or topic in normalized_target or normalized_target in _practice_pack_target_text(row)
    return normalized_target in _practice_pack_target_text(row)
```

- [ ] **Step 4: Add candidate query**

Add:

```python
def list_targeted_wrong_question_practice_candidates(
    *,
    organization_id: int,
    class_id: int,
    student_id: int,
    mode: str,
    target: str,
    limit: int,
    reference_date: str = "",
) -> list[dict]:
    normalized_mode = _normalize_practice_pack_mode(mode)
    normalized_target = str(target or "").strip()
    if not normalized_target:
        return []
    reference = _parse_local_date(reference_date) or date.today()
    six_month_cutoff = reference - timedelta(days=183)
    six_month_cutoff_bound = f"{six_month_cutoff.isoformat()} 00:00:00"
    normalized_limit = max(1, int(limit or 1))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                wqs.*,
                c.name AS class_display_name,
                s.name AS student_name,
                u.display_name AS teacher_display_name
            FROM wrong_question_submissions wqs
            JOIN classes c ON c.id = wqs.class_id
            JOIN students s ON s.id = wqs.student_id
            JOIN users u ON u.id = wqs.teacher_user_id
            WHERE wqs.organization_id=?
              AND wqs.class_id=?
              AND wqs.student_id=?
              AND wqs.source='wechat_mp'
              AND wqs.recognition_status='recognized'
              AND wqs.created_at >= ?
            ORDER BY
              CASE WHEN wqs.archive_status='active' THEN 0 ELSE 1 END ASC,
              wqs.created_at DESC,
              wqs.id DESC
            """,
            (
                int(organization_id or 0),
                int(class_id or 0),
                int(student_id or 0),
                six_month_cutoff_bound,
            ),
        ).fetchall()
    matched = [
        dict(row)
        for row in rows
        if _practice_pack_record_matches_target(row, mode=normalized_mode, target=normalized_target)
    ]
    return matched[:normalized_limit]
```

- [ ] **Step 5: Add seven-day schedule helper**

Add:

```python
def build_wrong_question_practice_pack_schedule(items: list[dict], *, start_date: str) -> list[dict]:
    start = _parse_local_date(start_date) or date.today()
    ordered_items = list(items or [])
    real_items = [item for item in ordered_items if str(item.get("item_type") or "real") == "real"]
    variant_items = [item for item in ordered_items if str(item.get("item_type") or "real") == "variant"]
    merged = [*real_items, *variant_items]
    days = [
        {
            "day_index": index + 1,
            "date": (start + timedelta(days=index)).isoformat(),
            "items": [],
        }
        for index in range(7)
    ]
    for index, item in enumerate(merged):
        days[index % 7]["items"].append(item)
    return days
```

- [ ] **Step 6: Run candidate tests to verify pass**

Run:

```bash
python -m unittest tests.test_wrong_question_practice_packs.WrongQuestionPracticePackCandidateTestCase -v
```

Expected: PASS.

- [ ] **Step 7: Commit selection and schedule**

Run:

```bash
git add lesson_manager.py tests/test_wrong_question_practice_packs.py
git commit -m "feat: select targeted wrong question practice candidates"
```

---

### Task 3: AI Same-Reason Variant Generation and Review

**Files:**
- Modify: `ai_processor.py`
- Modify: `tests/test_ai_processor_prompt.py`
- Modify: `tests/test_wrong_question_practice_packs.py`

- [ ] **Step 1: Add prompt assertions**

Append to `tests/test_ai_processor_prompt.py`:

```python
def test_practice_pack_variant_prompt_requires_same_reason_questions():
    prompt = ai_processor.WRONG_QUESTION_PRACTICE_PACK_VARIANT_PROMPT
    self.assertIn("同错因变式题", prompt)
    self.assertIn("不跨错因", prompt)
    self.assertIn("标准答案", prompt)
    self.assertIn("关键步骤", prompt)
    self.assertIn("易错提醒", prompt)


def test_practice_pack_variant_review_prompt_checks_answer_and_target():
    prompt = ai_processor.WRONG_QUESTION_PRACTICE_PACK_VARIANT_REVIEW_PROMPT
    self.assertIn("题目可解", prompt)
    self.assertIn("答案一致", prompt)
    self.assertIn("目标错因", prompt)
    self.assertIn("结论：通过", prompt)
```

- [ ] **Step 2: Add normalization tests**

Append to `tests/test_wrong_question_practice_packs.py`:

```python
class WrongQuestionPracticePackAiNormalizationTestCase(unittest.TestCase):
    def test_normalize_variant_payload_requires_target_fields(self):
        payload = {
            "items": [
                {
                    "variant_id": "variant-1",
                    "source_record_id": "wechat-a",
                    "question_text": "解方程：x/2 + 1 = 3。",
                    "training_goal": "去分母时等式两边每一项同乘。",
                    "answer": "x=4",
                    "key_steps": ["两边同乘2", "x+2=6", "x=4"],
                    "pitfall_reminder": "不要只乘含分母的一边。",
                    "difficulty": "基础",
                }
            ]
        }

        normalized = ai_processor._normalize_wrong_question_practice_pack_variants(
            payload,
            expected_count=1,
            target="去分母",
        )

        self.assertEqual(normalized[0]["variant_id"], "variant-1")
        self.assertEqual(normalized[0]["answer"], "x=4")
        self.assertEqual(normalized[0]["key_steps"], ["两边同乘2", "x+2=6", "x=4"])

    def test_variant_review_passed_reads_first_conclusion_line(self):
        self.assertTrue(ai_processor._wrong_question_practice_pack_variant_review_passed("结论：通过\n题目可解。"))
        self.assertFalse(ai_processor._wrong_question_practice_pack_variant_review_passed("结论：不通过\n答案不一致。"))
```

- [ ] **Step 3: Run AI tests to verify failure**

Run:

```bash
python -m unittest tests.test_ai_processor_prompt tests.test_wrong_question_practice_packs.WrongQuestionPracticePackAiNormalizationTestCase -v
```

Expected: FAIL with missing prompt and normalization helper names.

- [ ] **Step 4: Add prompts**

In `ai_processor.py`, after `WRONG_QUESTION_PRACTICE_SHEET_PROMPT`, add:

```python
WRONG_QUESTION_PRACTICE_PACK_VARIANT_PROMPT = """你是错题练习变式题设计助手。
你会收到某个学生的真实错题、目标复习方向和需要补足的题数。请生成同错因变式题。

只返回 JSON，不要输出解释。
返回字段：
- items: array

items 每一项包含：
- variant_id: string，例如 variant-1
- source_record_id: string，参考的真实错题 ID
- question_text: string，新的练习题题面
- training_goal: string，本题训练目标
- answer: string，标准答案
- key_steps: array[string]，关键步骤
- pitfall_reminder: string，易错提醒
- difficulty: string，基础 / 中等 / 提升

严格规则：
1. 必须生成同错因变式题，不跨错因、不换训练目标。
2. 如果目标是去分母漏乘，题目必须考察等式两边每一项同乘。
3. 如果目标是符号、审题、步骤遗漏或粗心，题目必须专门触发该错误原因。
4. 题目必须可解，答案必须唯一且与关键步骤一致。
5. 不要在 question_text 里泄露答案、关键步骤或易错提醒。
6. 难度要贴近原题，不要明显超出学生当前学段。
7. 生成题数量必须等于 requested_count。"""

WRONG_QUESTION_PRACTICE_PACK_VARIANT_REVIEW_PROMPT = """你是错题练习变式题审稿老师。
请检查变式题是否可直接给学生练习。

检查项：
1. 题目可解。
2. 标准答案与题目一致。
3. 关键步骤能推出答案。
4. 题目确实考察目标错因。
5. 没有跨到其它错因。
6. 学生题面没有泄露答案。

第一行必须只写：
结论：通过
或
结论：不通过

后续再用一句话说明原因。"""
```

- [ ] **Step 5: Add normalization helpers**

In `ai_processor.py`, after `_normalize_wrong_question_practice_sheet_material`, add:

```python
def _normalize_wrong_question_practice_pack_variants(
    payload: dict,
    *,
    expected_count: int,
    target: str,
) -> list[dict]:
    raw_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list) or len(raw_items) != int(expected_count or 0):
        raise ValueError("wrong question practice pack variant generation failed")
    normalized = []
    for index, raw_item in enumerate(raw_items, start=1):
        source = raw_item if isinstance(raw_item, dict) else {}
        key_steps = source.get("key_steps")
        normalized_steps = [
            str(step or "").strip()
            for step in (key_steps if isinstance(key_steps, list) else [])
            if str(step or "").strip()
        ]
        item = {
            "variant_id": str(source.get("variant_id") or f"variant-{index}").strip(),
            "source_record_id": str(source.get("source_record_id") or "").strip(),
            "question_text": str(source.get("question_text") or "").strip(),
            "training_goal": str(source.get("training_goal") or "").strip(),
            "answer": str(source.get("answer") or "").strip(),
            "key_steps": normalized_steps,
            "pitfall_reminder": str(source.get("pitfall_reminder") or "").strip(),
            "difficulty": str(source.get("difficulty") or "基础").strip() or "基础",
        }
        if not item["question_text"] or not item["answer"] or not item["training_goal"] or not item["key_steps"]:
            raise ValueError("wrong question practice pack variant generation failed")
        if str(target or "").strip() and str(target or "").strip() not in item["training_goal"] and str(target or "").strip() not in item["pitfall_reminder"] and str(target or "").strip() not in item["question_text"]:
            raise ValueError("wrong question practice pack variant target mismatch")
        normalized.append(item)
    return normalized


def _wrong_question_practice_pack_variant_review_passed(review_text: str) -> bool:
    for line in str(review_text or "").splitlines():
        normalized = re.sub(r"\s+", "", line)
        if not normalized:
            continue
        return normalized.startswith("结论：通过") or normalized.startswith("结论:通过")
    return False
```

- [ ] **Step 6: Add generation and review functions**

Add after the normalization helpers:

```python
def generate_wrong_question_practice_pack_variants(
    *,
    student_name: str,
    class_name: str,
    mode: str,
    target: str,
    requested_count: int,
    source_records: list[dict],
    include_usage: bool = False,
):
    if int(requested_count or 0) <= 0:
        return ([], {}) if include_usage else []
    normalized_records = [
        {
            "id": str(record.get("id") or "").strip(),
            "question_text": str(record.get("question_text") or "").strip(),
            "topic_category": str(record.get("topic_category") or "").strip(),
            "primary_error_type": str(record.get("primary_error_type") or "").strip(),
            "secondary_error_summary": str(record.get("secondary_error_summary") or "").strip(),
            "child_reason_text": str(record.get("child_raw_reason_text") or "").strip(),
        }
        for record in (source_records or [])
    ]
    if not normalized_records:
        raise ValueError("source_records are required")
    client = _get_client()
    response = client.chat.completions.create(
        model=_get_structured_generation_model(),
        messages=[
            {"role": "system", "content": WRONG_QUESTION_PRACTICE_PACK_VARIANT_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "student_name": str(student_name or "").strip(),
                        "class_name": str(class_name or "").strip(),
                        "mode": str(mode or "").strip(),
                        "target": str(target or "").strip(),
                        "requested_count": int(requested_count or 0),
                        "source_records": normalized_records,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    payload = _loads_model_json(response.choices[0].message.content)
    normalized = _normalize_wrong_question_practice_pack_variants(
        payload,
        expected_count=int(requested_count or 0),
        target=str(target or "").strip(),
    )
    if include_usage:
        return normalized, _usage_dict(response)
    return normalized


def review_wrong_question_practice_pack_variant(
    *,
    mode: str,
    target: str,
    variant: dict,
    client=None,
) -> str:
    active_client = client or _get_client()
    response = active_client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": WRONG_QUESTION_PRACTICE_PACK_VARIANT_REVIEW_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "mode": str(mode or "").strip(),
                        "target": str(target or "").strip(),
                        "variant": variant,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0,
    )
    return str(response.choices[0].message.content or "").strip()
```

- [ ] **Step 7: Run AI tests to verify pass**

Run:

```bash
python -m unittest tests.test_ai_processor_prompt tests.test_wrong_question_practice_packs.WrongQuestionPracticePackAiNormalizationTestCase -v
```

Expected: PASS.

- [ ] **Step 8: Commit AI variant helpers**

Run:

```bash
git add ai_processor.py tests/test_ai_processor_prompt.py tests/test_wrong_question_practice_packs.py
git commit -m "feat: add practice pack variant prompts"
```

---

### Task 4: Practice Pack PDF Rendering

**Files:**
- Modify: `pdf_engine.py`
- Modify: `frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs`
- Modify: `tests/test_wrong_question_practice_packs.py`

- [ ] **Step 1: Add failing PDF payload test**

Append to `tests/test_wrong_question_practice_packs.py`:

```python
class WrongQuestionPracticePackPdfPayloadTestCase(unittest.TestCase):
    def test_browser_payload_keeps_daily_plan_and_answers(self):
        items = [
            {
                "practice_item_id": "real-1",
                "item_type": "real",
                "question_text_snapshot": "解方程 x+1=3。",
                "answer": "x=2",
                "key_steps": ["x=3-1", "x=2"],
                "pitfall_reminder": "移项后要变号。",
            }
        ]
        schedule = [{"day_index": 1, "date": "2026-05-20", "items": items}]

        payload_items = pdf_engine._build_browser_wrong_question_practice_items(items)
        self.assertEqual(payload_items[0]["practiceItemId"], "real-1")
        self.assertEqual(payload_items[0]["itemType"], "real")
        self.assertEqual(payload_items[0]["answer"], "x=2")
        self.assertEqual(payload_items[0]["keySteps"], ["x=3-1", "x=2"])
        self.assertEqual(payload_items[0]["pitfallReminder"], "移项后要变号。")

        payload_schedule = pdf_engine._build_browser_wrong_question_practice_schedule(schedule)
        self.assertEqual(payload_schedule[0]["dayIndex"], 1)
        self.assertEqual(payload_schedule[0]["items"][0]["practiceItemId"], "real-1")
```

- [ ] **Step 2: Run PDF payload test to verify failure**

Run:

```bash
python -m unittest tests.test_wrong_question_practice_packs.WrongQuestionPracticePackPdfPayloadTestCase -v
```

Expected: FAIL because `_build_browser_wrong_question_practice_schedule` does not exist and item fields are not mapped.

- [ ] **Step 3: Extend PDF payload mapping**

In `pdf_engine.py`, update `_build_browser_wrong_question_practice_items()` so each returned item includes:

```python
"practiceItemId": str(item.get("practice_item_id") or item.get("wrong_question_record_id") or "").strip(),
"itemType": str(item.get("item_type") or "real").strip() or "real",
"trainingGoal": str(item.get("training_goal") or "").strip(),
"answer": str(item.get("answer") or "").strip(),
"keySteps": [
    str(step or "").strip()
    for step in (item.get("key_steps") if isinstance(item.get("key_steps"), list) else [])
    if str(step or "").strip()
],
"pitfallReminder": str(item.get("pitfall_reminder") or "").strip(),
"scheduledDate": str(item.get("scheduled_date") or "").strip(),
```

Keep all existing fields that current practice PDFs use.

- [ ] **Step 4: Add schedule payload helper**

In `pdf_engine.py`, add:

```python
def _build_browser_wrong_question_practice_schedule(schedule: list[dict]) -> list[dict]:
    browser_days = []
    for day in schedule or []:
        if not isinstance(day, dict):
            continue
        browser_days.append(
            {
                "dayIndex": int(day.get("day_index") or 0),
                "date": str(day.get("date") or "").strip(),
                "items": _build_browser_wrong_question_practice_items(day.get("items") or []),
            }
        )
    return browser_days
```

- [ ] **Step 5: Extend PDF function signature**

Change `generate_wrong_question_practice_sheet_pdf()` and `_render_wrong_question_practice_sheet_pdf_via_browser()` to accept optional keyword-only arguments:

```python
schedule: list[dict] | None = None,
answer_items: list[dict] | None = None,
pack_meta: dict | None = None,
```

Add these keys to the JSON payload passed to the browser renderer:

```python
"schedule": _build_browser_wrong_question_practice_schedule(schedule or []),
"answerItems": _build_browser_wrong_question_practice_items(answer_items or items),
"packMeta": {
    "mode": str((pack_meta or {}).get("mode") or "").strip(),
    "target": str((pack_meta or {}).get("target") or "").strip(),
    "volume": str((pack_meta or {}).get("volume") or "").strip(),
    "generatedDate": str((pack_meta or {}).get("generated_date") or "").strip(),
},
```

- [ ] **Step 6: Update browser renderer**

In `frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs`, keep the current layout for payloads without `schedule`. For payloads with `schedule.length > 0`, render:

```js
const schedule = Array.isArray(payload.schedule) ? payload.schedule : [];
const answerItems = Array.isArray(payload.answerItems) ? payload.answerItems : [];
const hasSchedule = schedule.length > 0;
```

Add visible sections:

```js
if (hasSchedule) {
  htmlParts.push(`<section class="pack-meta">复习方向：${escapeHtml(payload.packMeta?.target || '')}</section>`);
  for (const day of schedule) {
    htmlParts.push(`<section class="practice-day"><h2>第 ${Number(day.dayIndex || 0)} 天｜${escapeHtml(day.date || '')}</h2>`);
    for (const item of day.items || []) {
      htmlParts.push(renderPracticeItem(item));
    }
    htmlParts.push(`</section>`);
  }
  htmlParts.push(`<section class="answer-section"><h2>答案与关键步骤</h2>`);
  for (const item of answerItems) {
    htmlParts.push(`<article class="answer-card">`);
    htmlParts.push(`<h3>${escapeHtml(item.practiceItemId || '')}</h3>`);
    htmlParts.push(`<p><strong>答案：</strong>${escapeHtml(item.answer || '')}</p>`);
    htmlParts.push(`<ol>${(item.keySteps || []).map((step) => `<li>${escapeHtml(step)}</li>`).join('')}</ol>`);
    htmlParts.push(`<p><strong>易错提醒：</strong>${escapeHtml(item.pitfallReminder || '')}</p>`);
    htmlParts.push(`</article>`);
  }
  htmlParts.push(`</section>`);
}
```

Reuse the existing item renderer for the question area so current image and KaTeX behavior stays intact.

- [ ] **Step 7: Run PDF payload test**

Run:

```bash
python -m unittest tests.test_wrong_question_practice_packs.WrongQuestionPracticePackPdfPayloadTestCase -v
```

Expected: PASS.

- [ ] **Step 8: Commit PDF support**

Run:

```bash
git add pdf_engine.py frontend/scripts/renderWrongQuestionPracticeSheetPdf.mjs tests/test_wrong_question_practice_packs.py
git commit -m "feat: render scheduled practice pack pdfs"
```

---

### Task 5: Practice Pack Worker and Zip Generation

**Files:**
- Modify: `app.py`
- Modify: `tests/test_wrong_question_practice_packs.py`

- [ ] **Step 1: Add failing worker tests**

Append to `tests/test_wrong_question_practice_packs.py`:

```python
from unittest import mock


class WrongQuestionPracticePackWorkerTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        import app as app_module
        app_module.PDF_DIR = self.base / "pdfs"
        app_module.PDF_DIR.mkdir(parents=True, exist_ok=True)
        self.app_module = app_module
        self.owner = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class("七年级 5 班", subject="数学", grade="七年级")
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner["id"])
        self.student = lesson_manager.create_student_for_class(self.class_id, "王睿博")
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-pack-worker")
        self.binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        lesson_manager.create_wechat_wrong_question_submission(
            binding_id=self.binding["id"],
            image_url="https://files.example.com/equation.png",
            child_raw_reason_text="解方程去分母时右边没有同乘",
            primary_error_type="知识点问题",
            secondary_error_summary="去分母漏乘",
            topic_category="计算",
            recognition_status="recognized",
            question_text="解方程 (x-1)/2=3。",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @mock.patch("app.finalize_ai_charge")
    @mock.patch("app.ensure_feature_credits_available")
    @mock.patch("pdf_engine.generate_wrong_question_practice_sheet_pdf")
    @mock.patch("ai_processor.review_wrong_question_practice_pack_variant", return_value="结论：通过\n可用。")
    @mock.patch("ai_processor.generate_wrong_question_practice_pack_variants")
    @mock.patch("ai_processor.generate_wrong_question_practice_sheet_material")
    def test_worker_creates_student_pdf_and_zip(
        self,
        mock_material,
        mock_variants,
        mock_review,
        mock_pdf,
        mock_ensure,
        mock_finalize,
    ):
        mock_material.return_value = {
            "title": "王睿博 一周错题练习",
            "items": [
                {
                    "wrong_question_record_id": mock.ANY,
                    "ai_hint": "",
                    "reason_blank_prompt": "去分母检查\n两边都要同乘 ______。",
                    "improvement_summary_prompt": "下次提醒\n先找最小公倍数 ______。",
                }
            ],
        }
        mock_variants.return_value = [
            {
                "variant_id": "variant-1",
                "source_record_id": "source",
                "question_text": "解方程 x/2+1=3。",
                "training_goal": "去分母",
                "answer": "x=4",
                "key_steps": ["两边同乘2", "x+2=6", "x=4"],
                "pitfall_reminder": "等式两边每一项都要乘。",
                "difficulty": "基础",
            }
            for _ in range(9)
        ]

        def fake_pdf(**kwargs):
            output_path = Path(kwargs["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"%PDF-1.4 practice pack")
            return str(output_path)

        mock_pdf.side_effect = fake_pdf
        job = lesson_manager.create_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=self.owner["id"],
            mode="reason",
            target="去分母",
            volume="standard",
        )

        self.app_module._run_wrong_question_practice_pack_job(
            job_id=job["id"],
            user={"id": self.owner["id"], "organization_id": self.owner["organization_id"]},
        )

        saved = lesson_manager.get_wrong_question_practice_pack_job(job["id"])
        self.assertEqual(saved["status"], "ready")
        self.assertTrue(Path(saved["zip_path"]).exists())
        self.assertEqual(saved["students"][0]["status"], "ready")
        self.assertEqual(saved["students"][0]["real_question_count"], 1)
        self.assertEqual(saved["students"][0]["variant_question_count"], 9)
```

- [ ] **Step 2: Run worker test to verify failure**

Run:

```bash
python -m unittest tests.test_wrong_question_practice_packs.WrongQuestionPracticePackWorkerTestCase -v
```

Expected: FAIL because `_run_wrong_question_practice_pack_job` does not exist.

- [ ] **Step 3: Add output path helpers**

In `app.py`, near `_wrong_question_practice_sheet_pdf_path`, add:

```python
def _wrong_question_practice_pack_dir(job_id: int) -> Path:
    pack_dir = PDF_DIR / "wrong_question_practice_packs" / f"pack-{int(job_id or 0)}"
    pack_dir.mkdir(parents=True, exist_ok=True)
    return pack_dir


def _wrong_question_practice_pack_student_pdf_path(job_id: int, student_id: int) -> Path:
    return _wrong_question_practice_pack_dir(job_id) / f"student-{int(student_id or 0)}.pdf"


def _wrong_question_practice_pack_zip_path(job_id: int) -> Path:
    return _wrong_question_practice_pack_dir(job_id) / "practice-pack.zip"
```

- [ ] **Step 4: Add pack item builders**

In `app.py`, add:

```python
def _practice_pack_item_from_real_record(record: dict, index: int) -> dict:
    return {
        "practice_item_id": f"real-{index}",
        "item_type": "real",
        "wrong_question_record_id": str(record.get("id") or "").strip(),
        "question_order": index,
        "source": str(record.get("source") or "wechat_mp").strip() or "wechat_mp",
        "is_geometry": bool(record.get("is_geometry")),
        "question_text_snapshot": str(record.get("question_text") or "").strip(),
        "image_url_snapshot": str(record.get("image_url") or "").strip(),
        "child_reason_text_snapshot": str(record.get("child_raw_reason_text") or "").strip(),
        "primary_error_type_snapshot": str(record.get("primary_error_type") or "").strip(),
        "cause_note_snapshot": str(record.get("secondary_error_summary") or "").strip(),
    }


def _practice_pack_item_from_variant(variant: dict, index: int) -> dict:
    return {
        "practice_item_id": str(variant.get("variant_id") or f"variant-{index}").strip(),
        "item_type": "variant",
        "wrong_question_record_id": str(variant.get("source_record_id") or f"variant-{index}").strip(),
        "question_order": index,
        "source": "ai_variant",
        "is_geometry": False,
        "question_text_snapshot": str(variant.get("question_text") or "").strip(),
        "image_url_snapshot": "",
        "child_reason_text_snapshot": "",
        "primary_error_type_snapshot": "",
        "cause_note_snapshot": str(variant.get("training_goal") or "").strip(),
        "training_goal": str(variant.get("training_goal") or "").strip(),
        "answer": str(variant.get("answer") or "").strip(),
        "key_steps": list(variant.get("key_steps") or []),
        "pitfall_reminder": str(variant.get("pitfall_reminder") or "").strip(),
    }
```

- [ ] **Step 5: Add zip helper**

In `app.py`, add:

```python
def _build_wrong_question_practice_pack_zip(job: dict) -> str:
    zip_path = _wrong_question_practice_pack_zip_path(int(job["id"]))
    used_names: dict[str, int] = {}
    notes: list[str] = []
    successful_count = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for student in job.get("students") or []:
            student_name = str(student.get("student_name_snapshot") or "未命名").strip() or "未命名"
            if str(student.get("status") or "") != "ready":
                notes.append(f"{student_name}：{student.get('generation_error') or '未生成'}")
                continue
            pdf_path = Path(str(student.get("pdf_path") or ""))
            if not pdf_path.exists():
                notes.append(f"{student_name}：PDF 文件不存在")
                continue
            base_name = f"{_safe_archive_filename_part(student_name)}-一周错题练习"
            name_count = used_names.get(base_name, 0) + 1
            used_names[base_name] = name_count
            archive_name = f"{base_name}.pdf" if name_count == 1 else f"{base_name}-{name_count}.pdf"
            archive.write(pdf_path, archive_name)
            successful_count += 1
        if notes:
            archive.writestr("打包说明.txt", "\n".join(["以下学生未完整生成：", *notes]).encode("utf-8"))
    if successful_count <= 0:
        zip_path.unlink(missing_ok=True)
        raise RuntimeError("没有学生练习 PDF 生成成功")
    return str(zip_path)
```

- [ ] **Step 6: Add worker skeleton and generation flow**

In `app.py`, add:

```python
def _run_wrong_question_practice_pack_job(*, job_id: int, user: dict) -> None:
    job = get_wrong_question_practice_pack_job(job_id)
    if not job or str(job.get("status") or "") not in {"pending", "failed"}:
        return
    mark_wrong_question_practice_pack_job_status(job_id, status="running")
    requested_count = int(job.get("requested_question_count") or 0)
    successful = 0
    failed = 0
    try:
        students = list_students_for_class(int(job["class_id"]))
        for student in students:
            student_id = int(student["id"])
            student_name = str(student.get("name") or "").strip()
            upsert_wrong_question_practice_pack_job_student(
                job_id=job_id,
                student_id=student_id,
                student_name_snapshot=student_name,
                status="running",
                requested_question_count=requested_count,
            )
            try:
                real_records = list_targeted_wrong_question_practice_candidates(
                    organization_id=int(job["organization_id"]),
                    class_id=int(job["class_id"]),
                    student_id=student_id,
                    mode=str(job["mode"]),
                    target=str(job["target"]),
                    limit=requested_count,
                )
                if not real_records:
                    upsert_wrong_question_practice_pack_job_student(
                        job_id=job_id,
                        student_id=student_id,
                        student_name_snapshot=student_name,
                        status="skipped",
                        requested_question_count=requested_count,
                        generation_error="没有匹配方向的历史错题",
                    )
                    continue
                variant_count = max(0, requested_count - len(real_records))
                variants = []
                if variant_count:
                    variants = ai_processor.generate_wrong_question_practice_pack_variants(
                        student_name=student_name,
                        class_name=str(real_records[0].get("class_display_name") or ""),
                        mode=str(job["mode"]),
                        target=str(job["target"]),
                        requested_count=variant_count,
                        source_records=real_records,
                    )
                    reviewed_variants = []
                    for variant in variants:
                        review = ai_processor.review_wrong_question_practice_pack_variant(
                            mode=str(job["mode"]),
                            target=str(job["target"]),
                            variant=variant,
                        )
                        if ai_processor._wrong_question_practice_pack_variant_review_passed(review):
                            reviewed_variants.append(variant)
                    variants = reviewed_variants
                practice_items = []
                for index, record in enumerate(real_records, start=1):
                    practice_items.append(_practice_pack_item_from_real_record(record, index))
                for offset, variant in enumerate(variants, start=len(practice_items) + 1):
                    practice_items.append(_practice_pack_item_from_variant(variant, offset))
                schedule = build_wrong_question_practice_pack_schedule(
                    practice_items,
                    start_date=date.today().isoformat(),
                )
                material = ai_processor.generate_wrong_question_practice_sheet_material(
                    student_name=student_name,
                    class_name=str(real_records[0].get("class_display_name") or ""),
                    teacher_name=str(real_records[0].get("teacher_display_name") or ""),
                    items=practice_items,
                )
                generated_by_record_id = {
                    str(item.get("wrong_question_record_id") or "").strip(): item
                    for item in material.get("items") or []
                }
                merged_items = []
                for item in practice_items:
                    generated = generated_by_record_id.get(str(item.get("wrong_question_record_id") or "").strip()) or {}
                    merged_items.append(
                        {
                            **item,
                            "ai_hint": str(generated.get("ai_hint") or "").strip(),
                            "reason_blank_prompt": str(generated.get("reason_blank_prompt") or "").strip(),
                            "improvement_summary_prompt": str(generated.get("improvement_summary_prompt") or "").strip(),
                        }
                    )
                pdf_path = pdf_engine.generate_wrong_question_practice_sheet_pdf(
                    student_name=student_name,
                    class_name=str(real_records[0].get("class_display_name") or ""),
                    teacher_name=str(real_records[0].get("teacher_display_name") or ""),
                    title=f"{student_name} 一周错题练习",
                    items=merged_items,
                    output_path=str(_wrong_question_practice_pack_student_pdf_path(job_id, student_id)),
                    schedule=schedule,
                    answer_items=merged_items,
                    pack_meta={
                        "mode": job["mode"],
                        "target": job["target"],
                        "volume": job["volume"],
                        "generated_date": date.today().isoformat(),
                    },
                )
                upsert_wrong_question_practice_pack_job_student(
                    job_id=job_id,
                    student_id=student_id,
                    student_name_snapshot=student_name,
                    status="ready",
                    requested_question_count=requested_count,
                    real_question_count=len(real_records),
                    variant_question_count=len(variants),
                    pdf_path=pdf_path,
                    generation_error="" if len(practice_items) >= requested_count else "匹配题量不足，已按可用题生成",
                )
                successful += 1
            except Exception as exc:
                failed += 1
                upsert_wrong_question_practice_pack_job_student(
                    job_id=job_id,
                    student_id=student_id,
                    student_name_snapshot=student_name,
                    status="failed",
                    requested_question_count=requested_count,
                    generation_error=str(exc) or "生成失败",
                )
        refreshed = get_wrong_question_practice_pack_job(job_id) or {}
        zip_path = _build_wrong_question_practice_pack_zip(refreshed)
        mark_wrong_question_practice_pack_job_status(
            job_id,
            status="ready" if failed == 0 else "partial_failed",
            zip_path=zip_path,
            generation_error="" if failed == 0 else f"{failed} 名学生生成失败",
        )
    except Exception as exc:
        mark_wrong_question_practice_pack_job_status(
            job_id,
            status="failed",
            generation_error=str(exc) or "练习包生成失败",
        )


def _start_wrong_question_practice_pack_thread(**job_kwargs) -> None:
    threading.Thread(
        target=_run_wrong_question_practice_pack_job,
        kwargs=job_kwargs,
        daemon=True,
    ).start()
```

Add imports at the top of `app.py` for helpers introduced in `lesson_manager.py`:

```python
    build_wrong_question_practice_pack_schedule,
    create_wrong_question_practice_pack_job,
    find_active_wrong_question_practice_pack_job,
    get_wrong_question_practice_pack_job,
    list_targeted_wrong_question_practice_candidates,
    mark_wrong_question_practice_pack_job_status,
    upsert_wrong_question_practice_pack_job_student,
```

- [ ] **Step 7: Run worker tests**

Run:

```bash
python -m unittest tests.test_wrong_question_practice_packs.WrongQuestionPracticePackWorkerTestCase -v
```

Expected: PASS.

- [ ] **Step 8: Commit worker**

Run:

```bash
git add app.py tests/test_wrong_question_practice_packs.py
git commit -m "feat: generate wrong question practice pack jobs"
```

---

### Task 6: Practice Pack API

**Files:**
- Modify: `app.py`
- Modify: `tests/test_wrong_question_practice_packs.py`

- [ ] **Step 1: Add failing API tests**

Append to `tests/test_wrong_question_practice_packs.py`:

```python
class WrongQuestionPracticePackApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        import app as app_module
        app_module.app.config["TESTING"] = True
        app_module.PDF_DIR = self.base / "pdfs"
        app_module.PDF_DIR.mkdir(parents=True, exist_ok=True)
        self.app_module = app_module
        self.client = app_module.app.test_client()
        self.owner = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class("七年级 5 班", subject="数学", grade="七年级")
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner["id"])

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self):
        response = self.client.post("/api/login", json={"username": "Kayn", "password": "123456"})
        self.assertEqual(response.status_code, 200)

    @mock.patch("app.has_api_key", return_value=True)
    @mock.patch("app._start_wrong_question_practice_pack_thread")
    def test_post_pack_creates_or_reuses_job(self, mock_start, _mock_key):
        self.login()
        first = self.client.post(
            "/api/wrong-question-practice-packs",
            json={
                "class_id": self.class_id,
                "mode": "reason",
                "target": "去分母",
                "volume": "standard",
            },
        )
        second = self.client.post(
            "/api/wrong-question-practice-packs",
            json={
                "class_id": self.class_id,
                "mode": "reason",
                "target": "去分母",
                "volume": "standard",
            },
        )

        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.get_json()["job"]["id"], second.get_json()["job"]["id"])
        mock_start.assert_called_once()

    @mock.patch("app.has_api_key", return_value=True)
    def test_get_pack_and_download_ready_zip(self, _mock_key):
        self.login()
        job = lesson_manager.create_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=self.owner["id"],
            mode="topic",
            target="几何",
            volume="light",
        )
        zip_path = self.base / "ready.zip"
        zip_path.write_bytes(b"zip-bytes")
        lesson_manager.mark_wrong_question_practice_pack_job_status(
            job["id"],
            status="ready",
            zip_path=str(zip_path),
        )

        detail = self.client.get(f"/api/wrong-question-practice-packs/{job['id']}")
        download = self.client.get(f"/api/wrong-question-practice-packs/{job['id']}/download")

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["job"]["download_url"], f"/api/wrong-question-practice-packs/{job['id']}/download")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, b"zip-bytes")
```

- [ ] **Step 2: Run API tests to verify failure**

Run:

```bash
python -m unittest tests.test_wrong_question_practice_packs.WrongQuestionPracticePackApiTestCase -v
```

Expected: FAIL because routes do not exist.

- [ ] **Step 3: Add serializer and access check**

In `app.py`, add:

```python
def _serialize_wrong_question_practice_pack_job_for_response(job: object) -> Optional[dict]:
    if not isinstance(job, dict):
        return None
    serialized = dict(job)
    serialized["download_url"] = ""
    if str(serialized.get("zip_path") or "").strip() and str(serialized.get("status") or "") in {"ready", "partial_failed"}:
        serialized["download_url"] = f"/api/wrong-question-practice-packs/{serialized['id']}/download"
    return serialized


def _can_access_wrong_question_practice_pack_job(user: dict, job: object) -> bool:
    if user.get("role") == "super_owner":
        return True
    if not isinstance(job, dict):
        return False
    if user.get("role") in {"owner", "admin"}:
        return int(job.get("organization_id") or 0) == int(user.get("organization_id") or 0)
    return int(job.get("class_id") or 0) in set(get_user_class_ids(user["id"]))
```

- [ ] **Step 4: Add API routes**

In `app.py`, before `/api/wrong-question-followups/weekly`, add:

```python
@app.route("/api/wrong-question-practice-packs", methods=["POST"])
def api_wrong_question_practice_pack_create():
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    if not has_api_key():
        return jsonify({"error": "系统 API Key 未配置，请联系管理员"}), 400
    try:
        class_id = int(data.get("class_id") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "class_id must be numeric"}), 400
    if not class_id:
        return jsonify({"error": "class_id is required"}), 400
    cls = _require_accessible_class(user, class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    mode = str(data.get("mode") or "").strip()
    target = str(data.get("target") or "").strip()
    volume = str(data.get("volume") or "").strip()
    if mode not in {"topic", "reason"}:
        return jsonify({"error": "mode must be topic or reason"}), 400
    if volume not in {"light", "standard", "intensive"}:
        return jsonify({"error": "volume must be light, standard or intensive"}), 400
    if not target:
        return jsonify({"error": "target is required"}), 400
    organization_id = int(cls.get("organization_id") or user.get("organization_id") or 0)
    existing = find_active_wrong_question_practice_pack_job(
        organization_id=organization_id,
        class_id=class_id,
        created_by=int(user["id"]),
        mode=mode,
        target=target,
        volume=volume,
    )
    if existing:
        return jsonify({"job": _serialize_wrong_question_practice_pack_job_for_response(existing), "reused": True}), 200
    job = create_wrong_question_practice_pack_job(
        organization_id=organization_id,
        class_id=class_id,
        created_by=int(user["id"]),
        mode=mode,
        target=target,
        volume=volume,
    )
    _start_wrong_question_practice_pack_thread(
        job_id=int(job["id"]),
        user={"id": int(user["id"]), "organization_id": organization_id},
    )
    return jsonify({"job": _serialize_wrong_question_practice_pack_job_for_response(job), "reused": False}), 202


@app.route("/api/wrong-question-practice-packs/<int:job_id>", methods=["GET"])
def api_wrong_question_practice_pack_detail(job_id: int):
    user, error = _require_auth()
    if error:
        return error
    job = get_wrong_question_practice_pack_job(job_id)
    if not job or not _can_access_wrong_question_practice_pack_job(user, job):
        return jsonify({"error": "not found"}), 404
    return jsonify({"job": _serialize_wrong_question_practice_pack_job_for_response(job)})


@app.route("/api/wrong-question-practice-packs/<int:job_id>/download", methods=["GET"])
def api_wrong_question_practice_pack_download(job_id: int):
    user, error = _require_auth()
    if error:
        return error
    job = get_wrong_question_practice_pack_job(job_id)
    if not job or not _can_access_wrong_question_practice_pack_job(user, job):
        return jsonify({"error": "not found"}), 404
    if str(job.get("status") or "") not in {"ready", "partial_failed"}:
        return jsonify({"error": "practice pack is not ready"}), 409
    zip_path = Path(str(job.get("zip_path") or ""))
    if not zip_path.exists():
        return jsonify({"error": "zip not found"}), 404
    cls = get_class(int(job.get("class_id") or 0)) or {}
    download_name = (
        f"{_safe_archive_filename_part(str(cls.get('name') or '班级'))}"
        f"-{datetime.now().strftime('%Y-%m-%d')}-一周错题练习包.zip"
    )
    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=download_name,
    )
```

- [ ] **Step 5: Run API tests**

Run:

```bash
python -m unittest tests.test_wrong_question_practice_packs.WrongQuestionPracticePackApiTestCase -v
```

Expected: PASS.

- [ ] **Step 6: Commit API**

Run:

```bash
git add app.py tests/test_wrong_question_practice_packs.py
git commit -m "feat: expose wrong question practice pack api"
```

---

### Task 7: Frontend Models and UI

**Files:**
- Modify: `frontend/src/smartWrongQuestions.ts`
- Modify: `frontend/src/SmartWrongQuestionsPage.tsx`
- Modify: `frontend/src/smart-wrong-questions.test.ts`

- [ ] **Step 1: Add failing frontend model tests**

Append to `frontend/src/smart-wrong-questions.test.ts`:

```ts
test('builds practice pack API paths', () => {
  assert.equal(buildWrongQuestionPracticePackCreatePath(), '/api/wrong-question-practice-packs');
  assert.equal(buildWrongQuestionPracticePackDetailPath(42), '/api/wrong-question-practice-packs/42');
  assert.equal(buildWrongQuestionPracticePackDownloadPath(42), '/api/wrong-question-practice-packs/42/download');
});

test('normalizes practice pack job response', () => {
  const normalized = normalizeWrongQuestionPracticePackJobResponse({
    job: {
      id: 7,
      status: 'partial_failed',
      mode: 'reason',
      target: '去分母',
      volume: 'standard',
      requested_question_count: 10,
      download_url: '/api/wrong-question-practice-packs/7/download',
      students: [
        {
          student_id: 1,
          student_name_snapshot: '王睿博',
          status: 'ready',
          real_question_count: 3,
          variant_question_count: 7,
        },
      ],
    },
  });

  assert.equal(normalized.job?.id, 7);
  assert.equal(normalized.job?.status, 'partial_failed');
  assert.equal(normalized.job?.students[0]?.variantQuestionCount, 7);
});
```

- [ ] **Step 2: Run frontend model tests to verify failure**

Run:

```bash
cd frontend && npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: FAIL with missing exports.

- [ ] **Step 3: Add TypeScript types and normalizer**

In `frontend/src/smartWrongQuestions.ts`, add:

```ts
export type WrongQuestionPracticePackMode = 'topic' | 'reason';
export type WrongQuestionPracticePackVolume = 'light' | 'standard' | 'intensive';

export type WrongQuestionPracticePackStudent = {
  studentId: number;
  studentNameSnapshot: string;
  status: string;
  requestedQuestionCount: number;
  realQuestionCount: number;
  variantQuestionCount: number;
  pdfPath: string;
  generationError: string;
};

export type WrongQuestionPracticePackJob = {
  id: number;
  status: string;
  mode: WrongQuestionPracticePackMode | string;
  target: string;
  volume: WrongQuestionPracticePackVolume | string;
  requestedQuestionCount: number;
  downloadUrl: string;
  generationError: string;
  students: WrongQuestionPracticePackStudent[];
};

export function normalizeWrongQuestionPracticePackJobResponse(payload: unknown): { job: WrongQuestionPracticePackJob | null; reused: boolean } {
  const source = isObjectRecord(payload) ? payload : {};
  const rawJob = isObjectRecord(source.job) ? source.job : null;
  if (!rawJob) {
    return { job: null, reused: Boolean(source.reused) };
  }
  const rawStudents = Array.isArray(rawJob.students) ? rawJob.students : [];
  return {
    reused: Boolean(source.reused),
    job: {
      id: pickNumberValue(rawJob, ['id']) ?? 0,
      status: String(rawJob.status ?? ''),
      mode: String(rawJob.mode ?? ''),
      target: String(rawJob.target ?? ''),
      volume: String(rawJob.volume ?? ''),
      requestedQuestionCount: pickNumberValue(rawJob, ['requested_question_count', 'requestedQuestionCount']) ?? 0,
      downloadUrl: String(rawJob.download_url ?? rawJob.downloadUrl ?? ''),
      generationError: String(rawJob.generation_error ?? rawJob.generationError ?? ''),
      students: rawStudents.filter(isObjectRecord).map((student) => ({
        studentId: pickNumberValue(student, ['student_id', 'studentId']) ?? 0,
        studentNameSnapshot: String(student.student_name_snapshot ?? student.studentNameSnapshot ?? ''),
        status: String(student.status ?? ''),
        requestedQuestionCount: pickNumberValue(student, ['requested_question_count', 'requestedQuestionCount']) ?? 0,
        realQuestionCount: pickNumberValue(student, ['real_question_count', 'realQuestionCount']) ?? 0,
        variantQuestionCount: pickNumberValue(student, ['variant_question_count', 'variantQuestionCount']) ?? 0,
        pdfPath: String(student.pdf_path ?? student.pdfPath ?? ''),
        generationError: String(student.generation_error ?? student.generationError ?? ''),
      })),
    },
  };
}
```

- [ ] **Step 4: Add endpoint builders**

In `frontend/src/smartWrongQuestions.ts`, add:

```ts
export function buildWrongQuestionPracticePackCreatePath(): string {
  return '/api/wrong-question-practice-packs';
}

export function buildWrongQuestionPracticePackDetailPath(jobId: number): string {
  return `/api/wrong-question-practice-packs/${encodeURIComponent(String(jobId))}`;
}

export function buildWrongQuestionPracticePackDownloadPath(jobId: number): string {
  return `/api/wrong-question-practice-packs/${encodeURIComponent(String(jobId))}/download`;
}
```

- [ ] **Step 5: Update SmartWrongQuestionsPage state and handlers**

In `frontend/src/SmartWrongQuestionsPage.tsx`, import the new builders and normalizer. Add state:

```ts
const [practicePackMode, setPracticePackMode] = useState<'topic' | 'reason'>('topic');
const [practicePackTarget, setPracticePackTarget] = useState('');
const [practicePackVolume, setPracticePackVolume] = useState<'light' | 'standard' | 'intensive'>('standard');
const [practicePackJob, setPracticePackJob] = useState<WrongQuestionPracticePackJob | null>(null);
const [practicePackGenerating, setPracticePackGenerating] = useState(false);
```

Add handler:

```ts
const handleGeneratePracticePack = async () => {
  if (!activeWeeklyFollowupClassId) {
    setWeeklyFollowupError('请选择班级。');
    setWeeklyFollowupNotice('');
    return;
  }
  if (!practicePackTarget.trim()) {
    setWeeklyFollowupError('请输入具体复习方向。');
    setWeeklyFollowupNotice('');
    return;
  }
  setPracticePackGenerating(true);
  setWeeklyFollowupError('');
  setWeeklyFollowupNotice('');
  try {
    const response = await apiFetch<unknown>(buildWrongQuestionPracticePackCreatePath(), {
      method: 'POST',
      body: JSON.stringify({
        class_id: activeWeeklyFollowupClassId,
        mode: practicePackMode,
        target: practicePackTarget.trim(),
        volume: practicePackVolume,
      }),
    });
    const normalized = normalizeWrongQuestionPracticePackJobResponse(response);
    setPracticePackJob(normalized.job);
    if (normalized.job?.downloadUrl) {
      globalThis.window?.open?.(buildWrongQuestionAuthedPath(normalized.job.downloadUrl), '_blank', 'noopener,noreferrer');
      setWeeklyFollowupNotice('练习包已生成，正在打开下载。');
    } else {
      setWeeklyFollowupNotice(normalized.reused ? '已有同条件练习包正在生成，完成后可下载。' : '正在生成，完成后可下载。');
    }
  } catch (error) {
    setWeeklyFollowupError(error instanceof Error ? error.message : '一周练习包生成失败');
  } finally {
    setPracticePackGenerating(false);
  }
};
```

Add a polling helper only if a job has no `downloadUrl`:

```ts
const handleRefreshPracticePackJob = async () => {
  if (!practicePackJob?.id) {
    return;
  }
  const response = await apiFetch<unknown>(buildWrongQuestionPracticePackDetailPath(practicePackJob.id));
  const normalized = normalizeWrongQuestionPracticePackJobResponse(response);
  setPracticePackJob(normalized.job);
};
```

- [ ] **Step 6: Replace the two old buttons in the weekly panel**

In the `weeklyFollowupOpen` panel, keep `查看跟进清单` but replace `批量生成未生成学生练习` and `下载本周练习合集` with:

```tsx
<label className="space-y-2 text-sm">
  <span className="text-slate-500 dark:text-slate-400">复习方向类型</span>
  <select value={practicePackMode} onChange={(event) => setPracticePackMode(event.target.value as 'topic' | 'reason')} className={workspaceFieldClass}>
    <option value="topic">按专题/知识点</option>
    <option value="reason">按错因</option>
  </select>
</label>
<label className="space-y-2 text-sm">
  <span className="text-slate-500 dark:text-slate-400">具体方向</span>
  <input value={practicePackTarget} onChange={(event) => setPracticePackTarget(event.target.value)} className={workspaceFieldClass} placeholder="例如：去分母漏乘" />
</label>
<label className="space-y-2 text-sm">
  <span className="text-slate-500 dark:text-slate-400">题量档位</span>
  <select value={practicePackVolume} onChange={(event) => setPracticePackVolume(event.target.value as 'light' | 'standard' | 'intensive')} className={workspaceFieldClass}>
    <option value="light">轻量 5题</option>
    <option value="standard">标准 10题</option>
    <option value="intensive">强化 15题</option>
  </select>
</label>
<button type="button" onClick={() => void handleGeneratePracticePack()} disabled={practicePackGenerating} className={workspacePrimaryButtonClass}>
  {practicePackGenerating ? '正在提交' : '生成并下载一周练习包'}
</button>
```

Below notices, add a compact job card:

```tsx
{practicePackJob ? (
  <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm dark:border-white/10 dark:bg-slate-950/60">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p className="font-semibold text-slate-900 dark:text-white">一周练习包：{practicePackJob.target}</p>
        <p className="mt-1 text-slate-500 dark:text-slate-400">状态：{practicePackJob.status}｜题量：{practicePackJob.requestedQuestionCount}题</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => void handleRefreshPracticePackJob()} className={workspaceSecondaryButtonClass}>刷新状态</button>
        {practicePackJob.downloadUrl ? (
          <a href={buildWrongQuestionAuthedPath(practicePackJob.downloadUrl)} target="_blank" rel="noreferrer" className={workspacePrimaryButtonClass}>下载练习包</a>
        ) : null}
      </div>
    </div>
  </div>
) : null}
```

- [ ] **Step 7: Run frontend tests**

Run:

```bash
cd frontend && npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: PASS.

- [ ] **Step 8: Commit frontend**

Run:

```bash
git add frontend/src/smartWrongQuestions.ts frontend/src/SmartWrongQuestionsPage.tsx frontend/src/smart-wrong-questions.test.ts
git commit -m "feat: add practice pack frontend controls"
```

---

### Task 8: Final Verification and Handoff

**Files:**
- Modify: `handoff.md`

- [ ] **Step 1: Run backend practice pack tests**

Run:

```bash
python -m unittest tests.test_wrong_question_practice_packs -v
```

Expected: PASS.

- [ ] **Step 2: Run related existing backend tests**

Run:

```bash
python -m unittest tests.test_wrong_question_practice_async_api tests.test_weekly_wrong_question_followups tests.test_smart_wrong_questions_api -v
```

Expected: PASS.

- [ ] **Step 3: Run AI prompt tests**

Run:

```bash
python -m unittest tests.test_ai_processor_prompt -v
```

Expected: PASS.

- [ ] **Step 4: Run frontend focused tests**

Run:

```bash
cd frontend && npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: PASS.

- [ ] **Step 5: Run frontend full tests and build**

Run:

```bash
cd frontend && npm test
cd frontend && npm run build
```

Expected: PASS. Existing chunk-size warnings are acceptable if build exits 0.

- [ ] **Step 6: Run syntax and whitespace checks**

Run:

```bash
python -m py_compile app.py lesson_manager.py ai_processor.py pdf_engine.py
git diff --check
```

Expected: both commands exit 0.

- [ ] **Step 7: Update handoff**

Add one current-status bullet to `handoff.md`:

```markdown
- 2026-05-19 已完成“定向一周错题练习包”本地实现：网页智能错题新增 `生成并下载一周练习包`，支持按专题/知识点或错因选择目标、轻量/标准/强化题量档位，后台异步生成班级 practice pack job；每个学生优先使用历史真实错题，不足时 AI 生成同错因变式题并审稿，PDF 排到未来 7 天并附答案页，整班成功 PDF 打成 zip 下载。proof 已通过：后端 practice pack tests、相关错题回归、AI prompt tests、前端 focused tests、frontend full tests、frontend build、py_compile 和 git diff --check。
```

Add one next-step bullet:

```markdown
- 定向一周错题练习包下一步建议用真实 owner/admin 账号 smoke：选择一个有历史错题的班级，分别按 `按专题/知识点：几何` 和 `按错因：去分母漏乘` 生成标准 10 题练习包，确认生成状态、zip 下载、每个学生 PDF 的 7 天安排、AI 变式题质量和答案页符合老师实际发放需求。
```

- [ ] **Step 8: Commit verification handoff**

Run:

```bash
git add handoff.md
git commit -m "docs: record targeted practice pack implementation"
```

- [ ] **Step 9: Merge implementation branch back to develop**

Before merging, run:

```bash
git fetch --all --prune
git rev-list --left-right --count develop...origin/develop
```

Expected for a normal local-only implementation branch: `2 0` or another output where local `develop` is only ahead by already intentional local commits and not behind origin.

Then run:

```bash
git switch develop
git merge --no-ff feature/targeted-weekly-practice-pack-20260519 -m "Merge branch 'feature/targeted-weekly-practice-pack-20260519' into develop"
git branch -d feature/targeted-weekly-practice-pack-20260519
git status --short --branch
```

Expected: branch is `develop`, feature branch deleted, only ignored or pre-existing runtime files remain untracked.

## Plan Self-Review

- Spec coverage: storage, target selection, AI same-reason variants, review, seven-day schedule, PDF answer pages, zip generation, hybrid async API, frontend controls, idempotency, and verification are each mapped to tasks.
- Placeholder scan: this plan contains no unresolved placeholder markers or unspecified implementation slots.
- Type consistency: Python uses `mode`, `target`, `volume`, `requested_question_count`, `real_question_count`, `variant_question_count`; TypeScript normalizes the same snake_case fields into camelCase UI properties.
