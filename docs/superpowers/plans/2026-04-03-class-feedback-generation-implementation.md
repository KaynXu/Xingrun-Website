# Class Feedback Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone `班级反馈生成` workflow that lets teachers choose a class plus arbitrary date range, review source material, add stage notes, generate class + per-student feedback drafts, edit them, and confirm final texts so only confirmed content becomes future AI memory.

**Architecture:** Reuse the existing class roster and class-management APIs as the canonical identity layer, but add a new `class_feedback_*` persistence slice in `lesson_manager.py` plus dedicated Flask endpoints in `app.py`. Keep the React integration thin by introducing a focused `ClassFeedbackGenerationWorkspace` page and a separate `classFeedbackGeneration.ts` data module, then wire it into `App.tsx` as a new top-level workspace entry beside the existing review/teacher-feedback flows.

**Tech Stack:** Flask, SQLite, unittest, OpenAI-compatible chat client, React 19, TypeScript, tsx test runner, Vite

---

## File Structure

- Modify: `lesson_manager.py`
  - Add `class_feedback_*` tables and store helpers.
  - Add period granularity derivation and previous-confirmed-baseline lookup.
- Modify: `ai_processor.py`
  - Add a dedicated generator for class-summary + per-student feedback bundle output.
- Modify: `app.py`
  - Add class-feedback endpoints, permission checks, task hydration, generate/save/confirm orchestration.
- Create: `tests/test_class_feedback_store.py`
  - Cover persistence, granularity, baseline lookup, and confirm-only memory semantics.
- Create: `tests/test_class_feedback_api.py`
  - Cover end-to-end task creation, teacher fallback snapshot, generate/save/confirm, and label-config APIs.
- Create: `frontend/src/classFeedbackGeneration.ts`
  - Hold types, built-in labels, payload builders, and API wrappers.
- Create: `frontend/src/ClassFeedbackGenerationWorkspace.tsx`
  - Render the standalone stage-feedback flow UI.
- Create: `frontend/src/class-feedback-generation.test.tsx`
  - Cover helpers and source-level page/workspace assertions.
- Modify: `frontend/src/App.tsx`
  - Add the new `班级反馈生成` workspace entry and wire the page state.
- Modify: `frontend/src/workspace-navigation.test.ts`
  - Assert the new entry is visible and routes into the correct workspace.
- Optional verify-only reads:
  - `frontend/package.json`
  - `frontend/src/TeacherFeedbackWorkspace.tsx`
  - `frontend/src/reviewGenerationTeacherFeedback.ts` (later removed in the 2026-04-09 batch-1 orphan cleanup)

### Task 1: Add Class Feedback Persistence With Baseline Lookup

**Files:**
- Create: `tests/test_class_feedback_store.py`
- Modify: `lesson_manager.py`

- [ ] **Step 1: Write the failing store tests**

Create `tests/test_class_feedback_store.py` with these focused tests:

```python
import unittest

import lesson_manager


class ClassFeedbackStoreTestCase(unittest.TestCase):
    def setUp(self):
        lesson_manager.init_db()

    def test_create_task_derives_granularity_and_teacher_snapshot(self):
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        owner = lesson_manager.create_user("plan_owner", "Owner", "pw123456")

        task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=None,
            teacher_name_snapshot="Owner",
            start_date="2026-04-03",
            end_date="2026-04-03",
            created_by=owner["id"],
        )

        self.assertEqual(task["period_length_days"], 1)
        self.assertEqual(task["period_granularity"], "daily")
        self.assertEqual(task["teacher_user_id"], None)
        self.assertEqual(task["teacher_name_snapshot"], "Owner")
        self.assertEqual(task["status"], "draft")

    def test_previous_confirmed_entry_prefers_same_granularity_before_falling_back(self):
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        teacher = lesson_manager.create_user("plan_teacher", "Teacher", "pw123456")
        student = lesson_manager.create_student_for_class(class_id, "张三")

        weekly_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=teacher["id"],
            teacher_name_snapshot="Teacher",
            start_date="2026-03-24",
            end_date="2026-03-30",
            created_by=teacher["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            weekly_task["id"],
            class_summary_ai_draft="班级周反馈",
            student_entries=[{"student_id": student["id"], "name": "张三", "ai_draft": "周反馈草稿"}],
        )
        lesson_manager.confirm_class_feedback_task(
            weekly_task["id"],
            class_summary_final_text="班级周反馈终稿",
            student_entries=[{"student_id": student["id"], "final_text": "周反馈终稿", "checked_at": "2026-03-30 20:00:00"}],
        )

        daily_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=teacher["id"],
            teacher_name_snapshot="Teacher",
            start_date="2026-04-01",
            end_date="2026-04-01",
            created_by=teacher["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            daily_task["id"],
            class_summary_ai_draft="班级日报",
            student_entries=[{"student_id": student["id"], "name": "张三", "ai_draft": "日报草稿"}],
        )
        lesson_manager.confirm_class_feedback_task(
            daily_task["id"],
            class_summary_final_text="班级日报终稿",
            student_entries=[{"student_id": student["id"], "final_text": "日报终稿", "checked_at": "2026-04-01 20:00:00"}],
        )

        match_daily = lesson_manager.find_previous_confirmed_class_feedback_entry(
            class_id=class_id,
            student_id=student["id"],
            period_granularity="daily",
            before_end_date="2026-04-03",
        )
        match_weekly = lesson_manager.find_previous_confirmed_class_feedback_entry(
            class_id=class_id,
            student_id=student["id"],
            period_granularity="weekly",
            before_end_date="2026-04-03",
        )

        self.assertEqual(match_daily["final_text"], "日报终稿")
        self.assertEqual(match_weekly["final_text"], "周反馈终稿")

    def test_only_confirmed_text_is_returned_as_memory_source(self):
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        teacher = lesson_manager.create_user("plan_teacher_2", "Teacher 2", "pw123456")
        student = lesson_manager.create_student_for_class(class_id, "李四")

        task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=teacher["id"],
            teacher_name_snapshot="Teacher 2",
            start_date="2026-04-02",
            end_date="2026-04-08",
            created_by=teacher["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            task["id"],
            class_summary_ai_draft="仅草稿",
            student_entries=[{"student_id": student["id"], "name": "李四", "ai_draft": "仅草稿学生"}],
        )

        self.assertIsNone(
            lesson_manager.find_previous_confirmed_class_feedback_entry(
                class_id=class_id,
                student_id=student["id"],
                period_granularity="weekly",
                before_end_date="2026-04-09",
            )
        )
```

- [ ] **Step 2: Run the store tests to verify they fail**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_class_feedback_store.py
```

Expected: FAIL with `AttributeError` for missing `create_class_feedback_task`, `save_class_feedback_generation_result`, `confirm_class_feedback_task`, and `find_previous_confirmed_class_feedback_entry`.

- [ ] **Step 3: Implement the storage schema and helpers in `lesson_manager.py`**

Add the schema migration and the first helper set in `lesson_manager.py`:

```python
def _derive_class_feedback_period_fields(start_date: str, end_date: str) -> tuple[int, str]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    period_length_days = (end - start).days + 1
    if period_length_days <= 1:
        return period_length_days, "daily"
    if 6 <= period_length_days <= 8:
        return period_length_days, "weekly"
    return period_length_days, "custom"


def create_class_feedback_task(
    *,
    class_id: int,
    teacher_user_id: Optional[int],
    teacher_name_snapshot: str,
    start_date: str,
    end_date: str,
    created_by: int,
):
    period_length_days, period_granularity = _derive_class_feedback_period_fields(start_date, end_date)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO class_feedback_tasks (
                class_id, teacher_user_id, teacher_name_snapshot,
                start_date, end_date, period_length_days, period_granularity,
                status, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?)
            """,
            (
                class_id,
                teacher_user_id,
                teacher_name_snapshot,
                start_date,
                end_date,
                period_length_days,
                period_granularity,
                created_by,
            ),
        )
        task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return get_class_feedback_task(task_id)


def save_class_feedback_generation_result(task_id: int, class_summary_ai_draft: str, student_entries: list[dict]):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE class_feedback_tasks
            SET class_summary_ai_draft=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (class_summary_ai_draft, task_id),
        )
        conn.execute("DELETE FROM class_feedback_student_entries WHERE task_id=?", (task_id,))
        conn.executemany(
            """
            INSERT INTO class_feedback_student_entries (
                task_id, student_id, student_name_snapshot, ai_draft, final_text, checked_at
            ) VALUES (?, ?, ?, ?, '', NULL)
            """,
            [
                (
                    task_id,
                    item["student_id"],
                    item["name"],
                    item["ai_draft"],
                )
                for item in student_entries
            ],
        )
    return get_class_feedback_task(task_id)


def confirm_class_feedback_task(task_id: int, class_summary_final_text: str, student_entries: list[dict]):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE class_feedback_tasks
            SET class_summary_final_text=?, status='confirmed',
                confirmed_at=datetime('now','localtime'),
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (class_summary_final_text, task_id),
        )
        for item in student_entries:
            conn.execute(
                """
                UPDATE class_feedback_student_entries
                SET final_text=?, checked_at=?, updated_at=datetime('now','localtime')
                WHERE task_id=? AND student_id=?
                """,
                (item["final_text"], item["checked_at"], task_id, item["student_id"]),
            )
    return get_class_feedback_task(task_id)


def find_previous_confirmed_class_feedback_entry(*, class_id: int, student_id: int, period_granularity: str, before_end_date: str):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT e.*, t.period_granularity, t.end_date
            FROM class_feedback_student_entries e
            JOIN class_feedback_tasks t ON t.id = e.task_id
            WHERE t.class_id=?
              AND e.student_id=?
              AND t.status='confirmed'
              AND t.end_date < ?
              AND t.period_granularity=?
            ORDER BY t.end_date DESC, t.id DESC
            LIMIT 1
            """,
            (class_id, student_id, before_end_date, period_granularity),
        ).fetchone()
        if row:
            return dict(row)
        fallback = conn.execute(
            """
            SELECT e.*, t.period_granularity, t.end_date
            FROM class_feedback_student_entries e
            JOIN class_feedback_tasks t ON t.id = e.task_id
            WHERE t.class_id=?
              AND e.student_id=?
              AND t.status='confirmed'
              AND t.end_date < ?
            ORDER BY t.end_date DESC, t.id DESC
            LIMIT 1
            """,
            (class_id, student_id, before_end_date),
        ).fetchone()
    return dict(fallback) if fallback else None


def list_class_feedback_label_configs(owner_user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT label_group, label_text, sort_order
            FROM class_feedback_label_configs
            WHERE owner_user_id=? AND is_active=1
            ORDER BY label_group, sort_order, id
            """,
            (owner_user_id,),
        ).fetchall()
    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(row["label_group"], []).append(row["label_text"])
    if not grouped:
        return [
            {"group": "课堂状态", "labels": ["进入状态快", "注意力更集中", "注意力波动", "开口更主动", "开口偏少"]},
            {"group": "学习表现", "labels": ["基础更稳", "知识点仍卡住", "纠错后保持更好", "完整表达有进步", "应用时还不稳定"]},
            {"group": "课后执行", "labels": ["作业完成更稳", "作业拖延", "复习配合度提升", "家长跟进较积极", "家庭练习不足"]},
            {"group": "阶段变化", "labels": ["进步明显", "有点回落", "变化不大", "情绪更稳定", "需要下阶段重点关注"]},
        ]
    return [{"group": group, "labels": labels} for group, labels in grouped.items()]


def save_class_feedback_label_configs(owner_user_id: int, groups: list[dict]):
    with get_conn() as conn:
        conn.execute("DELETE FROM class_feedback_label_configs WHERE owner_user_id=?", (owner_user_id,))
        for group_index, group in enumerate(groups):
            label_group = (group.get("group") or "").strip()
            for label_index, label_text in enumerate(group.get("labels") or []):
                conn.execute(
                    """
                    INSERT INTO class_feedback_label_configs (
                        owner_user_id, label_group, label_text, sort_order, is_active, is_system_default
                    ) VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (
                        owner_user_id,
                        label_group,
                        str(label_text).strip(),
                        group_index * 100 + label_index,
                        0,
                    ),
                )
```

Also extend `init_db()` with the label-config table:

```python
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS class_feedback_label_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                label_group TEXT NOT NULL,
                label_text TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_system_default INTEGER NOT NULL DEFAULT 0
            )
            """
        )
```

Also extend `init_db()` with the two new tables:

```python
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS class_feedback_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                teacher_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                teacher_name_snapshot TEXT NOT NULL DEFAULT '',
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                period_length_days INTEGER NOT NULL DEFAULT 1,
                period_granularity TEXT NOT NULL DEFAULT 'daily',
                status TEXT NOT NULL DEFAULT 'draft',
                class_summary_ai_draft TEXT NOT NULL DEFAULT '',
                class_summary_final_text TEXT NOT NULL DEFAULT '',
                created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                confirmed_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS class_feedback_student_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL REFERENCES class_feedback_tasks(id) ON DELETE CASCADE,
                student_id INTEGER NOT NULL REFERENCES class_students(id) ON DELETE CASCADE,
                student_name_snapshot TEXT NOT NULL DEFAULT '',
                ai_draft TEXT NOT NULL DEFAULT '',
                final_text TEXT NOT NULL DEFAULT '',
                checked_at TEXT,
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            )
            """
        )
```

- [ ] **Step 4: Run the store tests to verify they pass**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_class_feedback_store.py
```

Expected: PASS with `3 passed`.

- [ ] **Step 5: Commit the persistence layer**

Run:

```bash
git add lesson_manager.py tests/test_class_feedback_store.py
git commit -m "feat: add class feedback persistence"
```

Expected: commit created with the new schema, task helpers, and store tests.

### Task 2: Add Class Feedback API, Label Config, And AI Generation

**Files:**
- Create: `tests/test_class_feedback_api.py`
- Modify: `app.py`
- Modify: `ai_processor.py`
- Verify context: `lesson_manager.py`

- [ ] **Step 1: Write the failing API tests**

Create `tests/test_class_feedback_api.py` with these initial endpoint tests:

```python
from unittest.mock import patch

from tests.test_teacher_feedback_api import TeacherFeedbackApiTestCase
import lesson_manager


class ClassFeedbackApiTestCase(TeacherFeedbackApiTestCase):
    def test_create_task_uses_current_user_snapshot_when_class_has_no_teacher_binding(self):
        class_id = lesson_manager.save_class("假期冲刺班", subject="英语", grade="六年级")
        lesson_manager.create_student_for_class(class_id, "张三")

        response = self.client.post(
            "/api/class-feedback/tasks",
            headers=self.headers,
            json={"class_id": class_id, "start_date": "2026-07-12", "end_date": "2026-07-12"},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["teacher_user_id"], None)
        self.assertEqual(payload["teacher_name_snapshot"], self.owner["display_name"])
        self.assertEqual(payload["period_granularity"], "daily")

    @patch("app.generate_class_feedback_bundle")
    def test_generate_route_returns_class_summary_and_student_entries(self, generate_class_feedback_bundle):
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        student = lesson_manager.create_student_for_class(class_id, "张三")
        task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=None,
            teacher_name_snapshot=self.owner["display_name"],
            start_date="2026-04-03",
            end_date="2026-04-09",
            created_by=self.owner["id"],
        )

        generate_class_feedback_bundle.return_value = {
            "class_summary": "本阶段班级整体状态稳定。",
            "student_entries": [
                {"student_id": student["id"], "name": "张三", "text": "张三这阶段开口更主动了。"}
            ],
        }

        response = self.client.post(
            f"/api/class-feedback/tasks/{task['id']}/generate",
            headers=self.headers,
            json={
                "class_status_tags": ["进入状态快"],
                "student_highlights": [
                    {"student_id": student["id"], "labels": ["进步明显"], "note": "主动表达增加"}
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["class_summary_ai_draft"], "本阶段班级整体状态稳定。")
        self.assertEqual(payload["student_entries"][0]["ai_draft"], "张三这阶段开口更主动了。")

    def test_confirm_route_promotes_final_text_into_memory(self):
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        student = lesson_manager.create_student_for_class(class_id, "张三")
        task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=None,
            teacher_name_snapshot=self.owner["display_name"],
            start_date="2026-04-03",
            end_date="2026-04-09",
            created_by=self.owner["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            task["id"],
            class_summary_ai_draft="草稿班级反馈",
            student_entries=[{"student_id": student["id"], "name": "张三", "ai_draft": "草稿学生反馈"}],
        )

        response = self.client.post(
            f"/api/class-feedback/tasks/{task['id']}/confirm",
            headers=self.headers,
            json={
                "class_summary_final_text": "正式班级反馈",
                "student_entries": [{"student_id": student["id"], "final_text": "正式学生反馈", "checked_at": "2026-04-09 20:00:00"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        reopened = self.client.get(f"/api/class-feedback/tasks/{task['id']}", headers=self.headers)
        self.assertEqual(reopened.get_json()["status"], "confirmed")
        baseline = lesson_manager.find_previous_confirmed_class_feedback_entry(
            class_id=class_id,
            student_id=student["id"],
            period_granularity="weekly",
            before_end_date="2026-04-10",
        )
        self.assertEqual(baseline["final_text"], "正式学生反馈")

    def test_label_config_round_trip_keeps_custom_group(self):
        save = self.client.put(
            "/api/class-feedback/labels",
            headers=self.headers,
            json={
                "groups": [
                    {"group": "阶段变化", "labels": ["进步明显", "有点回落", "变化不大", "需要重点关注"]},
                    {"group": "老师自定义", "labels": ["假期每日打卡稳定"]},
                ]
            },
        )

        self.assertEqual(save.status_code, 200)
        reloaded = self.client.get("/api/class-feedback/labels", headers=self.headers)
        payload = reloaded.get_json()
        self.assertEqual(payload["groups"][-1]["group"], "老师自定义")
        self.assertEqual(payload["groups"][-1]["labels"], ["假期每日打卡稳定"])
```

- [ ] **Step 2: Run the API tests to verify they fail**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_class_feedback_api.py
```

Expected: FAIL with missing routes and missing `generate_class_feedback_bundle`.

- [ ] **Step 3: Implement the AI helper and Flask routes**

Add this generator helper to `ai_processor.py`:

```python
def generate_class_feedback_bundle(
    *,
    class_name: str,
    teacher_name: str,
    start_date: str,
    end_date: str,
    source_summary: str,
    stage_notes: dict,
    students: list[dict],
) -> dict:
    client = _get_client()
    model = _get_chat_model()
    system_prompt = (
        "你是一位负责教培班级反馈的老师助理。"
        "你必须先阅读资料，再输出一个 JSON："
        '{"class_summary":"...","student_entries":[{"student_id":1,"name":"张三","text":"..."}]}。'
        "只有在存在明确历史基线时，才允许使用“进步明显”“有点回落”“变化不大”等比较型表达。"
    )
    user_prompt = json.dumps(
        {
            "class_name": class_name,
            "teacher_name": teacher_name,
            "start_date": start_date,
            "end_date": end_date,
            "source_summary": source_summary,
            "stage_notes": stage_notes,
            "students": students,
        },
        ensure_ascii=False,
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)
```

Then add these routes to `app.py`:

```python
@app.route("/api/class-feedback/labels", methods=["GET"])
def api_class_feedback_labels_get():
    user = require_login()
    return jsonify({"groups": lesson_manager.list_class_feedback_label_configs(user["id"])})


@app.route("/api/class-feedback/labels", methods=["PUT"])
def api_class_feedback_labels_put():
    user = require_login()
    data = request.get_json(force=True) or {}
    groups = data.get("groups") or []
    lesson_manager.save_class_feedback_label_configs(user["id"], groups)
    return jsonify({"groups": lesson_manager.list_class_feedback_label_configs(user["id"])})


@app.route("/api/class-feedback/tasks", methods=["POST"])
def api_class_feedback_task_create():
    user = require_login()
    data = request.get_json(force=True) or {}
    class_id = int(data.get("class_id") or 0)
    start_date = (data.get("start_date") or "").strip()
    end_date = (data.get("end_date") or "").strip()
    class_record = lesson_manager.get_class(class_id)
    if not class_record:
        return jsonify({"error": "班级不存在"}), 404
    teacher_user_id = class_record.get("teacher_user_id")
    teacher_name_snapshot = (
        class_record.get("teacher_name")
        or user.get("display_name")
        or user.get("username")
        or "未命名老师"
    )
    task = lesson_manager.create_class_feedback_task(
        class_id=class_id,
        teacher_user_id=teacher_user_id,
        teacher_name_snapshot=teacher_name_snapshot,
        start_date=start_date,
        end_date=end_date,
        created_by=user["id"],
    )
    return jsonify(task), 201


@app.route("/api/class-feedback/tasks/<int:task_id>/generate", methods=["POST"])
def api_class_feedback_generate(task_id):
    user = require_login()
    task = lesson_manager.get_class_feedback_task(task_id)
    if not task:
        return jsonify({"error": "反馈任务不存在"}), 404
    data = request.get_json(force=True) or {}
    hydrated = _build_class_feedback_generation_context(task, data, user)
    bundle = generate_class_feedback_bundle(**hydrated)
    saved = lesson_manager.save_class_feedback_generation_result(
        task_id,
        class_summary_ai_draft=bundle.get("class_summary", ""),
        student_entries=[
            {
                "student_id": item["student_id"],
                "name": item["name"],
                "ai_draft": item["text"],
            }
            for item in bundle.get("student_entries", [])
        ],
    )
    return jsonify(saved)


@app.route("/api/class-feedback/tasks/<int:task_id>/confirm", methods=["POST"])
def api_class_feedback_confirm(task_id):
    user = require_login()
    task = lesson_manager.get_class_feedback_task(task_id)
    if not task:
        return jsonify({"error": "反馈任务不存在"}), 404
    data = request.get_json(force=True) or {}
    confirmed = lesson_manager.confirm_class_feedback_task(
        task_id,
        class_summary_final_text=(data.get("class_summary_final_text") or "").strip(),
        student_entries=data.get("student_entries") or [],
    )
    return jsonify(confirmed)
```

Implement `_build_class_feedback_generation_context()` in `app.py` so it:

- collects source lessons inside the selected date range
- pulls current roster students
- attaches previous confirmed baseline text per student via `find_previous_confirmed_class_feedback_entry()`
- packages class notes and per-student highlights

- [ ] **Step 4: Run the API tests to verify they pass**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_class_feedback_api.py
```

Expected: PASS with `4 passed`.

- [ ] **Step 5: Commit the backend API slice**

Run:

```bash
git add app.py ai_processor.py tests/test_class_feedback_api.py
git commit -m "feat: add class feedback api flow"
```

Expected: commit created with routes, AI helper, and API tests.

### Task 3: Build Frontend Data Helpers And The Standalone Workspace

**Files:**
- Create: `frontend/src/classFeedbackGeneration.ts`
- Create: `frontend/src/ClassFeedbackGenerationWorkspace.tsx`
- Create: `frontend/src/class-feedback-generation.test.tsx`

- [ ] **Step 1: Write the failing frontend helper and workspace tests**

Create `frontend/src/class-feedback-generation.test.tsx`:

```tsx
import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import {
  defaultStageLabelGroups,
  buildClassFeedbackConfirmPayload,
  type ClassFeedbackStudentCard,
} from './classFeedbackGeneration';
import { ClassFeedbackGenerationWorkspace } from './ClassFeedbackGenerationWorkspace';

test('defaultStageLabelGroups exposes the built-in grouped labels', () => {
  assert.equal(defaultStageLabelGroups.length, 4);
  assert.equal(defaultStageLabelGroups[0]?.group, '课堂状态');
  assert.match(defaultStageLabelGroups[3]?.labels.join(','), /进步明显/);
});

test('buildClassFeedbackConfirmPayload keeps final class summary and checked student entries', () => {
  const payload = buildClassFeedbackConfirmPayload({
    classSummaryFinalText: '正式班级反馈',
    students: [
      {
        studentId: 1,
        name: '张三',
        aiDraft: '草稿',
        finalText: '正式反馈',
        checked: true,
      },
    ],
  });

  assert.equal(payload.class_summary_final_text, '正式班级反馈');
  assert.deepEqual(payload.student_entries, [
    { student_id: 1, final_text: '正式反馈', checked_at: 'CHECKED_ON_CONFIRM' },
  ]);
});

test('ClassFeedbackGenerationWorkspace renders source summary, stage notes, class summary, and student cards', () => {
  const students: ClassFeedbackStudentCard[] = [
    {
      studentId: 1,
      name: '张三',
      aiDraft: '草稿反馈',
      finalText: '草稿反馈',
      checked: false,
      sourceSummary: '2 节课次记录 + 1 条阶段备注',
      highlights: [],
    },
  ];

  const markup = renderToStaticMarkup(
    <ClassFeedbackGenerationWorkspace
      classNameLabel="S01A1"
      teacherNameLabel="王老师"
      sourceSummaryItems={['已命中 2 节课次记录', '1 名学生资料完整']}
      labelGroups={defaultStageLabelGroups}
      students={students}
      classSummaryText="班级反馈草稿"
      statusMessage="已生成 1 名学生反馈"
      isGenerating={false}
      isSaving={false}
      isConfirming={false}
      onClassSummaryChange={() => undefined}
      onStageNoteChange={() => undefined}
      onHighlightToggle={() => undefined}
      onHighlightNoteChange={() => undefined}
      onStudentFinalTextChange={() => undefined}
      onStudentCheckedChange={() => undefined}
      onAddStudent={() => undefined}
      onGenerate={() => undefined}
      onCopyClassSummary={() => undefined}
      onCopyAllStudents={() => undefined}
      onConfirm={() => undefined}
    />,
  );

  assert.match(markup, /班级反馈生成/);
  assert.match(markup, /资料摘要/);
  assert.match(markup, /阶段备注/);
  assert.match(markup, /班级总评/);
  assert.match(markup, /张三/);
  assert.match(markup, /确认本次反馈/);
});
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run:

```bash
cd frontend && npx tsx --test src/class-feedback-generation.test.tsx
```

Expected: FAIL because the new module and component do not exist yet.

- [ ] **Step 3: Implement the frontend data module and workspace component**

Create `frontend/src/classFeedbackGeneration.ts`:

```ts
export interface StageLabelGroup {
  group: string;
  labels: string[];
}

export interface ClassFeedbackStudentCard {
  studentId: number;
  name: string;
  aiDraft: string;
  finalText: string;
  checked: boolean;
  sourceSummary: string;
  highlights: Array<{ label: string; selected: boolean; note: string }>;
}

export const defaultStageLabelGroups: StageLabelGroup[] = [
  { group: '课堂状态', labels: ['进入状态快', '注意力更集中', '注意力波动', '开口更主动', '开口偏少'] },
  { group: '学习表现', labels: ['基础更稳', '知识点仍卡住', '纠错后保持更好', '完整表达有进步', '应用时还不稳定'] },
  { group: '课后执行', labels: ['作业完成更稳', '作业拖延', '复习配合度提升', '家长跟进较积极', '家庭练习不足'] },
  { group: '阶段变化', labels: ['进步明显', '有点回落', '变化不大', '情绪更稳定', '需要下阶段重点关注'] },
];

export function buildClassFeedbackConfirmPayload(input: {
  classSummaryFinalText: string;
  students: ClassFeedbackStudentCard[];
}) {
  return {
    class_summary_final_text: input.classSummaryFinalText,
    student_entries: input.students.map((student) => ({
      student_id: student.studentId,
      final_text: student.finalText,
      checked_at: student.checked ? 'CHECKED_ON_CONFIRM' : null,
    })),
  };
}

async function callApiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const { apiFetch } = await import('./App');
  return apiFetch<T>(path, options);
}

export const loadClassFeedbackLabels = () =>
  callApiFetch<{ groups: StageLabelGroup[] }>('/api/class-feedback/labels');

export const saveClassFeedbackLabels = (groups: StageLabelGroup[]) =>
  callApiFetch<{ groups: StageLabelGroup[] }>('/api/class-feedback/labels', {
    method: 'PUT',
    body: JSON.stringify({ groups }),
  });
```

Create `frontend/src/ClassFeedbackGenerationWorkspace.tsx`:

```tsx
import React from 'react';

import type { ClassFeedbackStudentCard, StageLabelGroup } from './classFeedbackGeneration';

export function ClassFeedbackGenerationWorkspace(props: {
  classNameLabel: string;
  teacherNameLabel: string;
  sourceSummaryItems: string[];
  labelGroups: StageLabelGroup[];
  students: ClassFeedbackStudentCard[];
  classSummaryText: string;
  statusMessage: string;
  isGenerating: boolean;
  isSaving: boolean;
  isConfirming: boolean;
  onClassSummaryChange: (value: string) => void;
  onStageNoteChange: (key: string, value: string) => void;
  onHighlightToggle: (studentId: number, label: string) => void;
  onHighlightNoteChange: (studentId: number, value: string) => void;
  onStudentFinalTextChange: (studentId: number, value: string) => void;
  onStudentCheckedChange: (studentId: number, checked: boolean) => void;
  onAddStudent: (name: string) => void | Promise<void>;
  onGenerate: () => void | Promise<void>;
  onCopyClassSummary: () => void | Promise<void>;
  onCopyAllStudents: () => void | Promise<void>;
  onConfirm: () => void | Promise<void>;
}) {
  return (
    <section className="space-y-6">
      <header className="rounded-[28px] border border-sky-100/80 bg-white/92 p-5 shadow-[0_18px_70px_rgba(15,23,42,0.06)]">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Class Feedback</p>
        <h3 className="mt-3 text-2xl font-semibold text-slate-900">班级反馈生成</h3>
        <p className="mt-2 text-sm text-slate-500">{props.classNameLabel} · {props.teacherNameLabel}</p>
        <p className="mt-2 text-sm text-slate-500">{props.statusMessage}</p>
      </header>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.86fr)_minmax(0,1.14fr)]">
        <section className="rounded-[28px] border border-sky-100/80 bg-white/92 p-5">
          <h4 className="text-lg font-semibold text-slate-900">资料摘要</h4>
          <ul className="mt-4 space-y-2 text-sm text-slate-600">
            {props.sourceSummaryItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>

          <h4 className="mt-6 text-lg font-semibold text-slate-900">阶段备注</h4>
          <textarea
            className="mt-3 min-h-[120px] w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm"
            placeholder="补充本阶段班级整体状态、家长共性反馈、教学重点与下阶段预告"
            onChange={(event) => props.onStageNoteChange('class_status_note', event.target.value)}
          />
        </section>

        <section className="rounded-[28px] border border-sky-100/80 bg-white/92 p-5">
          <div className="flex items-center justify-between gap-3">
            <h4 className="text-lg font-semibold text-slate-900">班级总评</h4>
            <button type="button" onClick={() => void props.onCopyClassSummary()} className="rounded-full bg-sky-500 px-4 py-2 text-sm font-medium text-white">
              复制班级总评
            </button>
          </div>
          <textarea
            value={props.classSummaryText}
            onChange={(event) => props.onClassSummaryChange(event.target.value)}
            className="mt-3 min-h-[160px] w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm leading-7"
          />

          <div className="mt-6 flex items-center gap-3">
            <button type="button" onClick={() => void props.onGenerate()} className="rounded-2xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white">
              {props.isGenerating ? '生成中...' : '生成阶段反馈草稿'}
            </button>
            <button type="button" onClick={() => void props.onCopyAllStudents()} className="rounded-2xl bg-sky-50 px-5 py-3 text-sm font-semibold text-sky-700">
              复制全部学生反馈
            </button>
            <button type="button" onClick={() => void props.onConfirm()} className="rounded-2xl bg-emerald-500 px-5 py-3 text-sm font-semibold text-white">
              {props.isConfirming ? '确认中...' : '确认本次反馈'}
            </button>
          </div>

          <div className="mt-6 space-y-4">
            {props.students.map((student) => (
              <article key={student.studentId} className="rounded-[22px] border border-slate-100 bg-slate-50/70 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-base font-semibold text-slate-900">{student.name}</p>
                    <p className="mt-1 text-xs text-slate-500">{student.sourceSummary}</p>
                  </div>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={student.checked}
                      onChange={(event) => props.onStudentCheckedChange(student.studentId, event.target.checked)}
                    />
                    标记已检查
                  </label>
                </div>
                <textarea
                  value={student.finalText}
                  onChange={(event) => props.onStudentFinalTextChange(student.studentId, event.target.value)}
                  className="mt-3 min-h-[120px] w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm leading-7"
                />
              </article>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run the frontend tests to verify they pass**

Run:

```bash
cd frontend && npx tsx --test src/class-feedback-generation.test.tsx
```

Expected: PASS with `3 passed`.

- [ ] **Step 5: Commit the frontend workspace foundation**

Run:

```bash
git add frontend/src/classFeedbackGeneration.ts frontend/src/ClassFeedbackGenerationWorkspace.tsx frontend/src/class-feedback-generation.test.tsx
git commit -m "feat: add class feedback workspace foundation"
```

Expected: commit created with the new frontend model, UI shell, and tests.

### Task 4: Wire The New Workspace Into `App.tsx`

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/workspace-navigation.test.ts`
- Modify: `frontend/src/class-feedback-generation.test.tsx`
- Verify context: `frontend/src/reviewGenerationTeacherFeedback.ts` (later removed in the 2026-04-09 batch-1 orphan cleanup)

- [ ] **Step 1: Write the failing navigation and source-wiring assertions**

Add these tests:

```tsx
// frontend/src/workspace-navigation.test.ts
test('workspace navigation source exposes the class feedback generation entry', () => {
  const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');
  assert.match(appSource, /label:\s*'班级反馈生成'/);
});

// frontend/src/class-feedback-generation.test.tsx
import { readFileSync } from 'node:fs';
const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

test('App source wires the standalone class feedback page and existing class/student APIs', () => {
  assert.match(appSource, /const \[activeClassFeedbackTaskId, setActiveClassFeedbackTaskId\] = useState<number \| null>\(null\);/);
  assert.match(appSource, /apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(appSource, /await apiFetch\('\/api\/class-feedback\/tasks'/);
  assert.match(appSource, /await createClassStudent\(selectedClassId, name\);/);
  assert.match(appSource, /<ClassFeedbackGenerationWorkspace/);
});
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run:

```bash
cd frontend && npx tsx --test src/class-feedback-generation.test.tsx src/workspace-navigation.test.ts
```

Expected: FAIL because `App.tsx` does not yet expose the new workspace state or entry.

- [ ] **Step 3: Implement the page state and workspace registration in `frontend/src/App.tsx`**

Add the new imports and state:

```tsx
import { ClassFeedbackGenerationWorkspace } from './ClassFeedbackGenerationWorkspace';
import {
  buildClassFeedbackConfirmPayload,
  defaultStageLabelGroups,
  type ClassFeedbackStudentCard,
} from './classFeedbackGeneration';

const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
const [activeClassFeedbackTaskId, setActiveClassFeedbackTaskId] = useState<number | null>(null);
const [classFeedbackStudents, setClassFeedbackStudents] = useState<ClassFeedbackStudentCard[]>([]);
const [classFeedbackSummary, setClassFeedbackSummary] = useState('');
const [classFeedbackStatusMessage, setClassFeedbackStatusMessage] = useState('先选择班级和时间范围，再汇总阶段素材。');
```

Register the new workspace entry near the existing page list:

```tsx
{
  id: 'class-feedback-generation',
  label: '班级反馈生成',
  description: '按时间范围生成班级总评与学生个性化反馈',
}
```

Add the core task-create and generate handlers:

```tsx
const handleCreateClassFeedbackTask = useCallback(async (selectedClassId: number, startDate: string, endDate: string) => {
  const created = await apiFetch<{
    id: number;
    teacher_name_snapshot: string;
    period_granularity: string;
  }>('/api/class-feedback/tasks', {
    method: 'POST',
    body: JSON.stringify({ class_id: selectedClassId, start_date: startDate, end_date: endDate }),
  });
  setActiveClassFeedbackTaskId(created.id);
  setClassFeedbackStatusMessage(`已创建反馈任务，按 ${created.period_granularity} 粒度准备资料。`);
}, []);

const handleGenerateClassFeedback = useCallback(async (stageNotes: Record<string, string>) => {
  if (!activeClassFeedbackTaskId) return;
  const generated = await apiFetch<{
    class_summary_ai_draft: string;
    student_entries: Array<{ student_id: number; student_name_snapshot: string; ai_draft: string }>;
  }>(`/api/class-feedback/tasks/${activeClassFeedbackTaskId}/generate`, {
    method: 'POST',
    body: JSON.stringify(stageNotes),
  });
  setClassFeedbackSummary(generated.class_summary_ai_draft ?? '');
  setClassFeedbackStudents(
    generated.student_entries.map((item) => ({
      studentId: item.student_id,
      name: item.student_name_snapshot,
      aiDraft: item.ai_draft,
      finalText: item.ai_draft,
      checked: false,
      sourceSummary: '已汇总本阶段素材',
      highlights: [],
    })),
  );
}, [activeClassFeedbackTaskId]);
```

Render the new page branch:

```tsx
{activeWorkspace === 'class-feedback-generation' ? (
  <ClassFeedbackGenerationWorkspace
    classNameLabel={selectedClass?.name ?? '未选择班级'}
    teacherNameLabel={selectedClass?.teacher_name || currentUser.display_name}
    sourceSummaryItems={classFeedbackSourceSummary}
    labelGroups={defaultStageLabelGroups}
    students={classFeedbackStudents}
    classSummaryText={classFeedbackSummary}
    statusMessage={classFeedbackStatusMessage}
    isGenerating={isGeneratingClassFeedback}
    isSaving={isSavingClassFeedback}
    isConfirming={isConfirmingClassFeedback}
    onClassSummaryChange={setClassFeedbackSummary}
    onStageNoteChange={handleStageNoteChange}
    onHighlightToggle={handleHighlightToggle}
    onHighlightNoteChange={handleHighlightNoteChange}
    onStudentFinalTextChange={handleStudentFinalTextChange}
    onStudentCheckedChange={handleStudentCheckedChange}
    onAddStudent={async (name) => {
      if (!selectedClassId) return;
      await createClassStudent(selectedClassId, name);
      await reloadClassFeedbackRoster(selectedClassId);
    }}
    onGenerate={handleGenerateClassFeedback}
    onCopyClassSummary={handleCopyClassFeedbackSummary}
    onCopyAllStudents={handleCopyAllClassFeedbackStudents}
    onConfirm={handleConfirmClassFeedback}
  />
) : null}
```

- [ ] **Step 4: Run the frontend tests and build to verify the integration**

Run:

```bash
cd frontend && npx tsx --test src/class-feedback-generation.test.tsx src/workspace-navigation.test.ts
cd frontend && npm run build
```

Expected:

- source-level tests PASS
- Vite build completes successfully

- [ ] **Step 5: Commit the page integration**

Run:

```bash
git add frontend/src/App.tsx frontend/src/workspace-navigation.test.ts frontend/src/class-feedback-generation.test.tsx
git commit -m "feat: wire class feedback generation page"
```

Expected: commit created with the new workspace entry and page wiring.

### Task 5: Run Focused Verification Across Backend And Frontend

**Files:**
- Verify only: `tests/test_class_feedback_store.py`
- Verify only: `tests/test_class_feedback_api.py`
- Verify only: `frontend/src/class-feedback-generation.test.tsx`
- Verify only: `frontend/src/workspace-navigation.test.ts`
- Verify only: `frontend/dist` (generated output)

- [ ] **Step 1: Run the backend regression set**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_class_feedback_store.py tests/test_class_feedback_api.py
```

Expected: PASS with all class-feedback persistence and API tests green.

- [ ] **Step 2: Run the focused frontend regression set**

Run:

```bash
cd frontend && npx tsx --test src/class-feedback-generation.test.tsx src/workspace-navigation.test.ts
```

Expected: PASS with the new workspace source assertions and helper tests green.

- [ ] **Step 3: Build the frontend bundle**

Run:

```bash
cd frontend && npm run build
```

Expected: successful Vite production build with no TypeScript errors.

- [ ] **Step 4: Smoke-check the task status transitions through the API**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_class_feedback_api.py -k "teacher_snapshot or confirm_route"
```

Expected: PASS proving draft-task creation and confirm-to-memory behavior both still work after the full integration.

- [ ] **Step 5: Commit the final verification checkpoint**

Run:

```bash
git status --short
git commit --allow-empty -m "chore: verify class feedback generation"
```

Expected:

- `git status --short` shows either a clean tree or only intentional generated files ignored by git
- final checkpoint commit exists so later debugging has a known-good verification point
