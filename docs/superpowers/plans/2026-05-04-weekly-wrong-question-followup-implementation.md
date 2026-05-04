# Weekly Wrong Question Followups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the weekly wrong-question followup assistant inside the existing web Smart Wrong Questions page, with natural parent-WeChat copy and class-level wrongbook PDF zip downloads.

**Architecture:** Keep the feature in the existing web app only. Use local `wrong_question_submissions` as the source of student/week summaries, cache generated parent messages in a new SQLite table, expose focused Flask endpoints, and render the assistant inside `SmartWrongQuestionsPage`. Generate class PDF zip files on demand from existing student wrongbook PDF refresh helpers.

**Tech Stack:** Flask, SQLite via `lesson_manager.py`, existing `ai_processor.py` OpenAI-compatible chat helpers, React/Vite TypeScript tests with `tsx`, Python `unittest`.

---

## File Structure

- Modify `lesson_manager.py`
  - Add `weekly_wrong_question_followup_messages`.
  - Add storage helpers for cached weekly parent-message text.
  - Add a query helper that groups local recognized active wrong questions by student for a class/week.
- Modify `ai_processor.py`
  - Add `WEEKLY_WRONG_QUESTION_FOLLOWUP_PROMPT`.
  - Add `generate_weekly_wrong_question_followup_message(...)`.
- Modify `app.py`
  - Add weekly followup list/message/zip routes.
  - Reuse `_filter_classes_for_user`, `_refresh_student_wrong_question_library_cache`, `_student_wrong_question_library_path`, `_can_access_wrong_question_record`, and `list_wrong_question_practice_sheets_for_student`.
- Create `tests/test_weekly_wrong_question_followups.py`
  - Cover storage, API permissions, AI message caching, and zip failure tolerance.
- Modify `frontend/src/smartWrongQuestions.ts`
  - Add types, normalizers, and path builders for weekly followups.
- Modify `frontend/src/SmartWrongQuestionsPage.tsx`
  - Add a web-only assistant view inside the existing Smart Wrong Questions page.
  - Add class/week controls, student cards, copy/regenerate buttons, and class zip download.
- Modify `frontend/src/smart-wrong-questions.test.ts`
  - Add focused tests for the web entry, copy action, regenerate action, and zip download path.
- Modify `handoff.md`
  - Record implementation status after the final verified commit.

---

### Task 1: Backend Storage and Weekly Summary Query

**Files:**
- Modify: `lesson_manager.py`
- Test: `tests/test_weekly_wrong_question_followups.py`

- [ ] **Step 1: Write failing storage/query tests**

Create `tests/test_weekly_wrong_question_followups.py` with this starting content:

```python
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager


class WeeklyWrongQuestionFollowupStorageTestCase(unittest.TestCase):
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
        self.student_a = lesson_manager.create_student_for_class(self.class_id, "王睿博")
        self.student_b = lesson_manager.create_student_for_class(self.class_id, "毛裕宁")
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-weekly-followup")
        self.binding_a = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student_a["id"],
        )
        self.binding_b = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student_b["id"],
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_weekly_summary_groups_active_recognized_records_by_student(self):
        record_a = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=self.binding_a["id"],
            image_url="https://files.example.com/a.png",
            child_raw_reason_text="第一步不知道找哪条辅助线",
            primary_error_type="方法问题",
            secondary_error_summary="几何读图第一步容易断",
            topic_category="几何",
            recognition_status="recognized",
            question_text="如图，证明角相等。",
        )
        archived_record = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=self.binding_a["id"],
            image_url="https://files.example.com/a-archived.png",
            topic_category="计算",
            recognition_status="recognized",
        )
        lesson_manager.set_wechat_wrong_question_archive_status(archived_record["id"], "archived")
        record_b = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=self.binding_b["id"],
            image_url="https://files.example.com/b.png",
            child_raw_reason_text="计算顺序看错",
            primary_error_type="细节问题",
            secondary_error_summary="运算优先级检查不稳定",
            topic_category="计算",
            recognition_status="recognized",
            question_text="计算 2+3*4。",
        )

        items = lesson_manager.list_weekly_wrong_question_followup_students(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            week_start_date="2026-05-04",
            week_end_date="2026-05-10",
        )

        self.assertEqual([item["student_name"] for item in items], ["毛裕宁", "王睿博"])
        by_student = {item["student_id"]: item for item in items}
        self.assertEqual(by_student[self.student_a["id"]]["weekly_question_count"], 1)
        self.assertEqual(by_student[self.student_a["id"]]["total_active_question_count"], 1)
        self.assertEqual(by_student[self.student_a["id"]]["topic_categories"], ["几何"])
        self.assertEqual(by_student[self.student_a["id"]]["representative_reason_summaries"], ["几何读图第一步容易断"])
        self.assertEqual(by_student[self.student_a["id"]]["source_record_ids"], [record_a["id"]])
        self.assertEqual(by_student[self.student_b["id"]]["source_record_ids"], [record_b["id"]])

    def test_upsert_weekly_followup_message_reuses_existing_row(self):
        saved = lesson_manager.upsert_weekly_wrong_question_followup_message(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            student_id=self.student_a["id"],
            teacher_user_id=self.owner["id"],
            week_start_date="2026-05-04",
            week_end_date="2026-05-10",
            style="warm",
            message_text="王睿博妈妈，我看了一下这周错题。",
            source_record_ids=["record-a", "record-b"],
            generated_by=self.owner["id"],
        )
        updated = lesson_manager.upsert_weekly_wrong_question_followup_message(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            student_id=self.student_a["id"],
            teacher_user_id=self.owner["id"],
            week_start_date="2026-05-04",
            week_end_date="2026-05-10",
            style="warm",
            message_text="王睿博妈妈，这周几何第一步还需要再收一下。",
            source_record_ids=["record-a"],
            generated_by=self.owner["id"],
        )
        loaded = lesson_manager.get_weekly_wrong_question_followup_message(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            student_id=self.student_a["id"],
            week_start_date="2026-05-04",
            style="warm",
        )

        self.assertEqual(saved["id"], updated["id"])
        self.assertEqual(loaded["message_text"], "王睿博妈妈，这周几何第一步还需要再收一下。")
        self.assertEqual(loaded["source_record_ids"], ["record-a"])
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m unittest tests.test_weekly_wrong_question_followups -v
```

Expected: FAIL because `list_weekly_wrong_question_followup_students`, `upsert_weekly_wrong_question_followup_message`, and `get_weekly_wrong_question_followup_message` do not exist.

- [ ] **Step 3: Add the SQLite table**

In `lesson_manager.init_db()`, after `wrong_question_practice_sheet_items`, add:

```python
        CREATE TABLE IF NOT EXISTS weekly_wrong_question_followup_messages (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id           INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            class_id                  INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            student_id                INTEGER NOT NULL REFERENCES students(id),
            teacher_user_id           INTEGER NOT NULL REFERENCES users(id),
            week_start_date           TEXT NOT NULL,
            week_end_date             TEXT NOT NULL,
            style                     TEXT NOT NULL DEFAULT 'warm',
            message_text              TEXT NOT NULL DEFAULT '',
            source_record_ids_json    TEXT NOT NULL DEFAULT '[]',
            generated_by              INTEGER REFERENCES users(id),
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(organization_id, class_id, student_id, week_start_date, style)
        );
```

Also add:

```python
        CREATE INDEX IF NOT EXISTS idx_weekly_followup_messages_class_week
        ON weekly_wrong_question_followup_messages(organization_id, class_id, week_start_date);
```

- [ ] **Step 4: Add storage helpers**

In `lesson_manager.py`, near the wrong-question practice sheet helpers, add:

```python
def _serialize_weekly_wrong_question_followup_message_row(row: sqlite3.Row | None) -> Optional[dict]:
    if not row:
        return None
    payload = dict(row)
    try:
        source_record_ids = json.loads(str(payload.get("source_record_ids_json") or "[]"))
    except json.JSONDecodeError:
        source_record_ids = []
    payload["source_record_ids"] = [str(item) for item in source_record_ids if str(item or "").strip()]
    payload.pop("source_record_ids_json", None)
    return payload


def get_weekly_wrong_question_followup_message(
    *,
    organization_id: int,
    class_id: int,
    student_id: int,
    week_start_date: str,
    style: str = "warm",
) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM weekly_wrong_question_followup_messages
            WHERE organization_id=? AND class_id=? AND student_id=? AND week_start_date=? AND style=?
            """,
            (organization_id, class_id, student_id, week_start_date, style or "warm"),
        ).fetchone()
    return _serialize_weekly_wrong_question_followup_message_row(row)


def upsert_weekly_wrong_question_followup_message(
    *,
    organization_id: int,
    class_id: int,
    student_id: int,
    teacher_user_id: int,
    week_start_date: str,
    week_end_date: str,
    style: str,
    message_text: str,
    source_record_ids: list[str],
    generated_by: int,
) -> dict:
    normalized_style = (style or "warm").strip() or "warm"
    normalized_source_ids = [str(item).strip() for item in source_record_ids if str(item or "").strip()]
    source_json = json.dumps(normalized_source_ids, ensure_ascii=False)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO weekly_wrong_question_followup_messages (
                organization_id, class_id, student_id, teacher_user_id,
                week_start_date, week_end_date, style, message_text,
                source_record_ids_json, generated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(organization_id, class_id, student_id, week_start_date, style)
            DO UPDATE SET
                teacher_user_id=excluded.teacher_user_id,
                week_end_date=excluded.week_end_date,
                message_text=excluded.message_text,
                source_record_ids_json=excluded.source_record_ids_json,
                generated_by=excluded.generated_by,
                updated_at=datetime('now','localtime')
            """,
            (
                organization_id,
                class_id,
                student_id,
                teacher_user_id,
                week_start_date,
                week_end_date,
                normalized_style,
                (message_text or "").strip(),
                source_json,
                generated_by,
            ),
        )
        row = conn.execute(
            """
            SELECT *
            FROM weekly_wrong_question_followup_messages
            WHERE organization_id=? AND class_id=? AND student_id=? AND week_start_date=? AND style=?
            """,
            (organization_id, class_id, student_id, week_start_date, normalized_style),
        ).fetchone()
    serialized = _serialize_weekly_wrong_question_followup_message_row(row)
    if serialized is None:
        raise RuntimeError("weekly followup message was not saved")
    return serialized
```

- [ ] **Step 5: Add the weekly grouped query**

In `lesson_manager.py`, add:

```python
def list_weekly_wrong_question_followup_students(
    *,
    organization_id: int,
    class_id: int,
    week_start_date: str,
    week_end_date: str,
) -> list[dict]:
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
              AND wqs.source='wechat_mp'
              AND wqs.recognition_status='recognized'
              AND wqs.archive_status='active'
              AND date(wqs.created_at) >= date(?)
              AND date(wqs.created_at) <= date(?)
            ORDER BY s.name COLLATE NOCASE ASC, wqs.created_at DESC, wqs.id DESC
            """,
            (organization_id, class_id, week_start_date, week_end_date),
        ).fetchall()
        total_rows = conn.execute(
            """
            SELECT student_id, COUNT(*) AS total_count
            FROM wrong_question_submissions
            WHERE organization_id=?
              AND class_id=?
              AND source='wechat_mp'
              AND recognition_status='recognized'
              AND archive_status='active'
            GROUP BY student_id
            """,
            (organization_id, class_id),
        ).fetchall()
    total_by_student = {int(row["student_id"]): int(row["total_count"] or 0) for row in total_rows}
    grouped: dict[int, dict] = {}
    for row in rows:
        student_id = int(row["student_id"])
        item = grouped.setdefault(
            student_id,
            {
                "organization_id": int(row["organization_id"]),
                "class_id": int(row["class_id"]),
                "class_name": str(row["class_display_name"] or ""),
                "student_id": student_id,
                "student_name": str(row["student_name"] or ""),
                "teacher_user_id": int(row["teacher_user_id"]),
                "teacher_name": str(row["teacher_display_name"] or ""),
                "weekly_question_count": 0,
                "total_active_question_count": total_by_student.get(student_id, 0),
                "topic_categories": [],
                "representative_reason_summaries": [],
                "latest_created_at": str(row["created_at"] or ""),
                "source_record_ids": [],
            },
        )
        item["weekly_question_count"] += 1
        item["source_record_ids"].append(str(row["id"]))
        topic = normalize_primary_wrong_question_topic_category(str(row["topic_category"] or ""))
        if topic and topic not in item["topic_categories"]:
            item["topic_categories"].append(topic)
        reason = str(row["secondary_error_summary"] or row["child_raw_reason_text"] or "").strip()
        if reason and reason not in item["representative_reason_summaries"] and len(item["representative_reason_summaries"]) < 3:
            item["representative_reason_summaries"].append(reason)
    return sorted(grouped.values(), key=lambda item: item["student_name"])
```

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
python -m unittest tests.test_weekly_wrong_question_followups -v
```

Expected: PASS for the two storage/query tests.

- [ ] **Step 7: Commit backend storage**

```bash
git add lesson_manager.py tests/test_weekly_wrong_question_followups.py
git commit -m "feat: add weekly wrong question followup storage"
```

---

### Task 2: AI Message Generation

**Files:**
- Modify: `ai_processor.py`
- Modify: `tests/test_weekly_wrong_question_followups.py`

- [ ] **Step 1: Add failing AI prompt test**

Append to `tests/test_weekly_wrong_question_followups.py`:

```python
from unittest.mock import Mock, patch
import ai_processor


class WeeklyWrongQuestionFollowupAiTestCase(unittest.TestCase):
    @patch("ai_processor._get_client")
    def test_generate_weekly_followup_message_requests_human_wechat_style(self, mock_get_client):
        response = type(
            "Response",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Message",
                                (),
                                {
                                    "content": "王睿博妈妈，我刚看了下孩子这周的错题，几何第一步还需要再收一下。"
                                },
                            )()
                        },
                    )()
                ],
                "usage": None,
            },
        )()
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = response
        mock_get_client.return_value = mock_client

        message = ai_processor.generate_weekly_wrong_question_followup_message(
            student_name="王睿博",
            class_name="七年级 5 班",
            teacher_name="Kayn",
            weekly_question_count=3,
            total_active_question_count=12,
            topic_categories=["几何", "计算"],
            representative_reason_summaries=["几何读图第一步容易断"],
            has_practice_sheet=True,
        )

        self.assertIn("王睿博妈妈", message)
        request_messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        joined = "\n".join(item["content"] for item in request_messages)
        self.assertIn("像老师真实发给家长的微信", joined)
        self.assertIn("不要写成报告", joined)
        self.assertIn("小程序", joined)
        self.assertIn("不提", joined)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m unittest tests.test_weekly_wrong_question_followups.WeeklyWrongQuestionFollowupAiTestCase -v
```

Expected: FAIL because `generate_weekly_wrong_question_followup_message` does not exist.

- [ ] **Step 3: Add AI prompt and function**

In `ai_processor.py`, near wrong question prompts, add:

```python
WEEKLY_WRONG_QUESTION_FOLLOWUP_PROMPT = """你是老师的微信沟通助手。
请把学生本周错题情况写成老师可以直接发给家长的微信私聊话术。

写作要求：
1. 像老师真实发给家长的微信，不要写成报告、通知、总结或 AI 文案。
2. 可以自然使用“我看了一下”“这块还有点卡”“下次课我会再带一下”。
3. 不要使用“本周错题主要集中在”“建议家长配合”“知识薄弱点”“提升能力”等报告腔。
4. 不把孩子说得太严重，也不要夸张表扬。
5. 控制在 2 到 3 小段，适合微信直接发送。
6. 不提小程序、系统、AI、后台、数据分析。
7. 如果信息不足，仍然写成温和、具体、可执行的一段老师话。
"""


def generate_weekly_wrong_question_followup_message(
    *,
    student_name: str,
    class_name: str,
    teacher_name: str,
    weekly_question_count: int,
    total_active_question_count: int,
    topic_categories: list[str],
    representative_reason_summaries: list[str],
    has_practice_sheet: bool,
) -> str:
    client = _get_client()
    payload = {
        "student_name": student_name,
        "class_name": class_name,
        "teacher_name": teacher_name,
        "weekly_question_count": weekly_question_count,
        "total_active_question_count": total_active_question_count,
        "topic_categories": topic_categories,
        "representative_reason_summaries": representative_reason_summaries,
        "has_practice_sheet": has_practice_sheet,
    }
    response = client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": WEEKLY_WRONG_QUESTION_FOLLOWUP_PROMPT},
            {
                "role": "user",
                "content": (
                    "请根据下面 JSON 写一段家长微信话术，只输出话术正文：\n"
                    + json.dumps(payload, ensure_ascii=False)
                ),
            },
        ],
        temperature=0.5,
    )
    message = response.choices[0].message.content.strip()
    if not message:
        raise ValueError("weekly wrong question followup message is empty")
    return message
```

- [ ] **Step 4: Run AI test**

Run:

```bash
python -m unittest tests.test_weekly_wrong_question_followups.WeeklyWrongQuestionFollowupAiTestCase -v
```

Expected: PASS.

- [ ] **Step 5: Commit AI generator**

```bash
git add ai_processor.py tests/test_weekly_wrong_question_followups.py
git commit -m "feat: add weekly followup message generator"
```

---

### Task 3: Flask Weekly Followup APIs

**Files:**
- Modify: `app.py`
- Modify: `tests/test_weekly_wrong_question_followups.py`

- [ ] **Step 1: Add failing API tests**

Append to `tests/test_weekly_wrong_question_followups.py`:

```python
from unittest.mock import patch
from app import app


class WeeklyWrongQuestionFollowupApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app.test_client()
        login = self.client.post("/api/login", json={"username": "Kayn", "password": "xingrun2026"})
        self.assertEqual(login.status_code, 200)
        self.token = login.get_json()["token"]
        self.owner = login.get_json()["user"]
        self.class_id = lesson_manager.save_class("七年级 5 班", subject="数学", grade="七年级")
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner["id"])
        self.student = lesson_manager.create_student_for_class(self.class_id, "王睿博")
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-weekly-api")
        self.binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        self.record = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=self.binding["id"],
            image_url="https://files.example.com/wrb.png",
            child_raw_reason_text="几何第一步不会找",
            primary_error_type="方法问题",
            secondary_error_summary="几何读图第一步容易断",
            topic_category="几何",
            recognition_status="recognized",
            question_text="如图，证明角相等。",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def auth_headers(self):
        return {"X-Auth-Token": self.token}

    def test_weekly_followup_list_returns_web_only_student_summaries(self):
        response = self.client.get(
            "/api/wrong-question-followups/weekly",
            headers=self.auth_headers(),
            query_string={"class_id": self.class_id, "week_start": "2026-05-04"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["class_id"], self.class_id)
        self.assertEqual(payload["week_start_date"], "2026-05-04")
        self.assertEqual(payload["week_end_date"], "2026-05-10")
        self.assertEqual(payload["items"][0]["student_name"], "王睿博")
        self.assertEqual(payload["items"][0]["message"], None)
        self.assertEqual(payload["items"][0]["source_record_ids"], [self.record["id"]])
        self.assertNotIn("miniprogram", payload)

    @patch("app.ai_processor.generate_weekly_wrong_question_followup_message")
    def test_generate_weekly_followup_message_caches_ai_text(self, mock_generate):
        mock_generate.return_value = "王睿博妈妈，我刚看了下孩子这周的错题，几何第一步还需要再收一下。"

        response = self.client.post(
            "/api/wrong-question-followups/weekly/messages",
            headers=self.auth_headers(),
            json={"class_id": self.class_id, "week_start": "2026-05-04", "student_id": self.student["id"]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["message"]["student_id"], self.student["id"])
        self.assertIn("王睿博妈妈", payload["message"]["message_text"])
        saved = lesson_manager.get_weekly_wrong_question_followup_message(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            student_id=self.student["id"],
            week_start_date="2026-05-04",
            style="warm",
        )
        self.assertEqual(saved["message_text"], payload["message"]["message_text"])
        mock_generate.assert_called_once()

    def test_weekly_followup_requires_class_access(self):
        other_class_id = lesson_manager.save_class("七年级 6 班", subject="数学", grade="七年级")
        response = self.client.get(
            "/api/wrong-question-followups/weekly",
            headers=self.auth_headers(),
            query_string={"class_id": other_class_id, "week_start": "2026-05-04"},
        )
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run API tests to verify failure**

Run:

```bash
python -m unittest tests.test_weekly_wrong_question_followups.WeeklyWrongQuestionFollowupApiTestCase -v
```

Expected: FAIL because the routes do not exist.

- [ ] **Step 3: Add date and response helpers in `app.py`**

Add near wrong-question helper functions:

```python
def _parse_week_start(raw_value: str) -> date:
    value = str(raw_value or "").strip()
    if not value:
        today = date.today()
        return today - timedelta(days=today.weekday())
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    return parsed - timedelta(days=parsed.weekday())


def _weekly_range(raw_week_start: str) -> tuple[str, str]:
    week_start = _parse_week_start(raw_week_start)
    week_end = week_start + timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


def _require_accessible_class(user: dict, class_id: int) -> Optional[dict]:
    cls = next((item for item in list_classes_for_actor(user) if int(item.get("id") or 0) == class_id), None)
    if cls and _filter_classes_for_user(user, [cls]):
        return cls
    return None
```

- [ ] **Step 4: Add serializer for weekly items**

Add in `app.py`:

```python
def _weekly_followup_item_payload(item: dict, message: Optional[dict]) -> dict:
    student_id = int(item["student_id"])
    return {
        "organization_id": int(item["organization_id"]),
        "class_id": int(item["class_id"]),
        "class_name": item["class_name"],
        "student_id": student_id,
        "student_name": item["student_name"],
        "teacher_user_id": int(item["teacher_user_id"]),
        "teacher_name": item["teacher_name"],
        "weekly_question_count": int(item["weekly_question_count"]),
        "total_active_question_count": int(item["total_active_question_count"]),
        "topic_categories": item["topic_categories"],
        "representative_reason_summaries": item["representative_reason_summaries"],
        "latest_created_at": item["latest_created_at"],
        "source_record_ids": item["source_record_ids"],
        "message": message,
        "student_library_pdf_url": f"/api/wechat/student-libraries/{student_id}",
    }
```

- [ ] **Step 5: Add list and message routes**

Add in `app.py` near `/api/wrong-questions` routes:

```python
@app.route("/api/wrong-question-followups/weekly", methods=["GET"])
def api_weekly_wrong_question_followups():
    user, error = _require_auth()
    if error:
        return error
    class_id = request.args.get("class_id", 0, type=int)
    if not class_id:
        return jsonify({"error": "class_id is required"}), 400
    cls = _require_accessible_class(user, class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    week_start_date, week_end_date = _weekly_range(request.args.get("week_start", ""))
    items = list_weekly_wrong_question_followup_students(
        organization_id=int(user["organization_id"]),
        class_id=class_id,
        week_start_date=week_start_date,
        week_end_date=week_end_date,
    )
    payload_items = []
    for item in items:
        message = get_weekly_wrong_question_followup_message(
            organization_id=int(user["organization_id"]),
            class_id=class_id,
            student_id=int(item["student_id"]),
            week_start_date=week_start_date,
            style="warm",
        )
        payload_items.append(_weekly_followup_item_payload(item, message))
    return jsonify({
        "class_id": class_id,
        "class_name": cls.get("name", ""),
        "week_start_date": week_start_date,
        "week_end_date": week_end_date,
        "items": payload_items,
        "total": len(payload_items),
    })


@app.route("/api/wrong-question-followups/weekly/messages", methods=["POST"])
def api_weekly_wrong_question_followup_message_create():
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    class_id = int(data.get("class_id") or 0)
    student_id = int(data.get("student_id") or 0)
    if not class_id or not student_id:
        return jsonify({"error": "class_id and student_id are required"}), 400
    cls = _require_accessible_class(user, class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    week_start_date, week_end_date = _weekly_range(data.get("week_start") or "")
    items = list_weekly_wrong_question_followup_students(
        organization_id=int(user["organization_id"]),
        class_id=class_id,
        week_start_date=week_start_date,
        week_end_date=week_end_date,
    )
    item = next((candidate for candidate in items if int(candidate["student_id"]) == student_id), None)
    if not item:
        return jsonify({"error": "student followup not found"}), 404
    has_practice_sheet = bool(list_wrong_question_practice_sheets_for_student(student_id))
    message_text = ai_processor.generate_weekly_wrong_question_followup_message(
        student_name=item["student_name"],
        class_name=item["class_name"],
        teacher_name=item["teacher_name"],
        weekly_question_count=int(item["weekly_question_count"]),
        total_active_question_count=int(item["total_active_question_count"]),
        topic_categories=item["topic_categories"],
        representative_reason_summaries=item["representative_reason_summaries"],
        has_practice_sheet=has_practice_sheet,
    )
    message = upsert_weekly_wrong_question_followup_message(
        organization_id=int(user["organization_id"]),
        class_id=class_id,
        student_id=student_id,
        teacher_user_id=int(item["teacher_user_id"]),
        week_start_date=week_start_date,
        week_end_date=week_end_date,
        style="warm",
        message_text=message_text,
        source_record_ids=item["source_record_ids"],
        generated_by=int(user["id"]),
    )
    return jsonify({"ok": True, "message": message})
```

Add imports from `lesson_manager` at the top of `app.py`:

```python
    get_weekly_wrong_question_followup_message,
    list_weekly_wrong_question_followup_students,
    upsert_weekly_wrong_question_followup_message,
```

- [ ] **Step 6: Run API tests**

Run:

```bash
python -m unittest tests.test_weekly_wrong_question_followups -v
```

Expected: PASS for storage, AI, and API tests.

- [ ] **Step 7: Commit API routes**

```bash
git add app.py tests/test_weekly_wrong_question_followups.py
git commit -m "feat: add weekly wrong question followup api"
```

---

### Task 4: Class PDF Zip Download

**Files:**
- Modify: `app.py`
- Modify: `tests/test_weekly_wrong_question_followups.py`

- [ ] **Step 1: Add failing zip tests**

Append to `WeeklyWrongQuestionFollowupApiTestCase`:

```python
    @patch("app._refresh_student_wrong_question_library_cache")
    def test_class_pdf_archive_downloads_zip_and_tolerates_student_failures(self, mock_refresh):
        pdf_a = self.base / "student-a.pdf"
        pdf_a.write_bytes(b"%PDF-1.4\nstudent a\n")
        mock_refresh.return_value = str(pdf_a)

        response = self.client.get(
            "/api/wrong-question-followups/weekly/class-pdf-archive",
            headers=self.auth_headers(),
            query_string={"class_id": self.class_id, "week_start": "2026-05-04"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        self.assertIn("attachment;", response.headers.get("Content-Disposition", ""))
        self.assertEqual(response.headers.get("X-XR-Archive-Success-Count"), "1")
        self.assertEqual(response.headers.get("X-XR-Archive-Failed-Count"), "0")
        self.assertGreater(len(response.data), 0)
        mock_refresh.assert_called_once_with(self.student["id"])
```

Add this second failure-tolerance test:

```python
    @patch("app._refresh_student_wrong_question_library_cache")
    def test_class_pdf_archive_records_failures_in_headers(self, mock_refresh):
        second_student = lesson_manager.create_student_for_class(self.class_id, "毛裕宁")
        second_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=self.binding["parent_wechat_account_id"],
            class_id=self.class_id,
            student_id=second_student["id"],
        )
        lesson_manager.create_wechat_wrong_question_submission(
            binding_id=second_binding["id"],
            image_url="https://files.example.com/my.png",
            topic_category="计算",
            recognition_status="recognized",
            question_text="计算 1+1。",
        )
        pdf_a = self.base / "student-a.pdf"
        pdf_a.write_bytes(b"%PDF-1.4\nstudent a\n")

        def fake_refresh(student_id):
            if student_id == self.student["id"]:
                return str(pdf_a)
            raise RuntimeError("pdf boom")

        mock_refresh.side_effect = fake_refresh
        response = self.client.get(
            "/api/wrong-question-followups/weekly/class-pdf-archive",
            headers=self.auth_headers(),
            query_string={"class_id": self.class_id, "week_start": "2026-05-04"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-XR-Archive-Success-Count"), "1")
        self.assertEqual(response.headers.get("X-XR-Archive-Failed-Count"), "1")
        self.assertIn("毛裕宁", response.headers.get("X-XR-Archive-Failed-Students", ""))
```

- [ ] **Step 2: Run zip tests to verify failure**

Run:

```bash
python -m unittest tests.test_weekly_wrong_question_followups.WeeklyWrongQuestionFollowupApiTestCase.test_class_pdf_archive_downloads_zip_and_tolerates_student_failures tests.test_weekly_wrong_question_followups.WeeklyWrongQuestionFollowupApiTestCase.test_class_pdf_archive_records_failures_in_headers -v
```

Expected: FAIL because the zip route does not exist.

- [ ] **Step 3: Add imports**

In `app.py`, add these imports:

```python
import io
import re
import zipfile
```

- [ ] **Step 4: Add zip filename helper**

In `app.py`, add:

```python
def _safe_archive_filename_part(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "-", str(value or "").strip())
    return cleaned or "未命名"
```

- [ ] **Step 5: Add the class zip route**

In `app.py`, add:

```python
@app.route("/api/wrong-question-followups/weekly/class-pdf-archive", methods=["GET"])
def api_weekly_wrong_question_followup_class_pdf_archive():
    user, error = _require_auth()
    if error:
        return error
    class_id = request.args.get("class_id", 0, type=int)
    if not class_id:
        return jsonify({"error": "class_id is required"}), 400
    cls = _require_accessible_class(user, class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    week_start_date, week_end_date = _weekly_range(request.args.get("week_start", ""))
    items = list_weekly_wrong_question_followup_students(
        organization_id=int(user["organization_id"]),
        class_id=class_id,
        week_start_date=week_start_date,
        week_end_date=week_end_date,
    )
    buffer = io.BytesIO()
    successes = []
    failures = []
    used_names: set[str] = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in items:
            student_id = int(item["student_id"])
            student_name = str(item["student_name"] or f"student-{student_id}")
            try:
                pdf_path_value = str(_refresh_student_wrong_question_library_cache(student_id) or "").strip()
                pdf_path = Path(pdf_path_value)
                if not pdf_path.exists():
                    raise FileNotFoundError(pdf_path_value)
                base_name = f"{_safe_archive_filename_part(student_name)}-错题本.pdf"
                arcname = base_name
                suffix = 2
                while arcname in used_names:
                    arcname = f"{_safe_archive_filename_part(student_name)}-{suffix}-错题本.pdf"
                    suffix += 1
                used_names.add(arcname)
                archive.write(pdf_path, arcname)
                successes.append(student_name)
            except Exception:
                logger.exception("Failed to add student %s wrongbook PDF to weekly archive", student_id)
                failures.append(student_name)
        if failures:
            archive.writestr("打包说明.txt", "以下学生错题本生成失败，可稍后重试：\n" + "\n".join(failures))
    buffer.seek(0)
    download_name = f"{_safe_archive_filename_part(str(cls.get('name') or '班级'))}-{week_start_date}-错题本合集.zip"
    response = send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=download_name,
    )
    response.headers["X-XR-Archive-Success-Count"] = str(len(successes))
    response.headers["X-XR-Archive-Failed-Count"] = str(len(failures))
    response.headers["X-XR-Archive-Failed-Students"] = ",".join(failures)
    return response
```

- [ ] **Step 6: Run zip tests**

Run:

```bash
python -m unittest tests.test_weekly_wrong_question_followups -v
```

Expected: PASS.

- [ ] **Step 7: Commit zip route**

```bash
git add app.py tests/test_weekly_wrong_question_followups.py
git commit -m "feat: add weekly wrongbook archive download"
```

---

### Task 5: Frontend Types and API Helpers

**Files:**
- Modify: `frontend/src/smartWrongQuestions.ts`
- Modify: `frontend/src/smart-wrong-questions.test.ts`

- [ ] **Step 1: Add failing helper tests**

In `frontend/src/smart-wrong-questions.test.ts`, add:

```ts
test('weekly followup path builders keep the feature web-only', () => {
  assert.equal(
    buildWeeklyWrongQuestionFollowupsPath(42, '2026-05-04'),
    '/api/wrong-question-followups/weekly?class_id=42&week_start=2026-05-04',
  );
  assert.equal(
    buildWeeklyWrongQuestionFollowupArchivePath(42, '2026-05-04'),
    '/api/wrong-question-followups/weekly/class-pdf-archive?class_id=42&week_start=2026-05-04',
  );
});

test('normalizeWeeklyWrongQuestionFollowupResponse preserves cached messages', () => {
  const payload = normalizeWeeklyWrongQuestionFollowupResponse({
    class_id: 42,
    class_name: '七年级 5 班',
    week_start_date: '2026-05-04',
    week_end_date: '2026-05-10',
    total: 1,
    items: [
      {
        student_id: 501,
        student_name: '王睿博',
        weekly_question_count: 3,
        total_active_question_count: 12,
        topic_categories: ['几何'],
        representative_reason_summaries: ['几何第一步容易断'],
        source_record_ids: ['record-a'],
        student_library_pdf_url: '/api/wechat/student-libraries/501',
        message: {
          id: 9,
          message_text: '王睿博妈妈，我刚看了下孩子这周错题。',
          source_record_ids: ['record-a'],
        },
      },
    ],
  });

  assert.equal(payload.items[0]?.studentName, '王睿博');
  assert.equal(payload.items[0]?.message?.messageText, '王睿博妈妈，我刚看了下孩子这周错题。');
  assert.equal(payload.items[0]?.studentLibraryPdfUrl, '/api/wechat/student-libraries/501');
});
```

Add imports:

```ts
  buildWeeklyWrongQuestionFollowupArchivePath,
  buildWeeklyWrongQuestionFollowupsPath,
  normalizeWeeklyWrongQuestionFollowupResponse,
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd frontend
npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: FAIL because the helper exports do not exist.

- [ ] **Step 3: Add types and normalizers**

In `frontend/src/smartWrongQuestions.ts`, add:

```ts
export type WeeklyWrongQuestionFollowupMessage = {
  id: number;
  messageText: string;
  sourceRecordIds: string[];
};

export type WeeklyWrongQuestionFollowupItem = {
  studentId: number;
  studentName: string;
  weeklyQuestionCount: number;
  totalActiveQuestionCount: number;
  topicCategories: string[];
  representativeReasonSummaries: string[];
  sourceRecordIds: string[];
  studentLibraryPdfUrl: string;
  message: WeeklyWrongQuestionFollowupMessage | null;
};

export type WeeklyWrongQuestionFollowupResponse = {
  classId: number;
  className: string;
  weekStartDate: string;
  weekEndDate: string;
  total: number;
  items: WeeklyWrongQuestionFollowupItem[];
};

function normalizeStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item ?? '').trim()).filter(Boolean) : [];
}

export function normalizeWeeklyWrongQuestionFollowupResponse(payload: unknown): WeeklyWrongQuestionFollowupResponse {
  const source = isObjectRecord(payload) ? payload : {};
  const rawItems = Array.isArray(source.items) ? source.items : [];
  return {
    classId: Number(source.class_id ?? source.classId ?? 0),
    className: String(source.class_name ?? source.className ?? ''),
    weekStartDate: String(source.week_start_date ?? source.weekStartDate ?? ''),
    weekEndDate: String(source.week_end_date ?? source.weekEndDate ?? ''),
    total: Number(source.total ?? rawItems.length),
    items: rawItems.filter(isObjectRecord).map((item) => {
      const rawMessage = isObjectRecord(item.message) ? item.message : null;
      return {
        studentId: Number(item.student_id ?? item.studentId ?? 0),
        studentName: String(item.student_name ?? item.studentName ?? ''),
        weeklyQuestionCount: Number(item.weekly_question_count ?? item.weeklyQuestionCount ?? 0),
        totalActiveQuestionCount: Number(item.total_active_question_count ?? item.totalActiveQuestionCount ?? 0),
        topicCategories: normalizeStringList(item.topic_categories ?? item.topicCategories),
        representativeReasonSummaries: normalizeStringList(item.representative_reason_summaries ?? item.representativeReasonSummaries),
        sourceRecordIds: normalizeStringList(item.source_record_ids ?? item.sourceRecordIds),
        studentLibraryPdfUrl: String(item.student_library_pdf_url ?? item.studentLibraryPdfUrl ?? ''),
        message: rawMessage
          ? {
              id: Number(rawMessage.id ?? 0),
              messageText: String(rawMessage.message_text ?? rawMessage.messageText ?? ''),
              sourceRecordIds: normalizeStringList(rawMessage.source_record_ids ?? rawMessage.sourceRecordIds),
            }
          : null,
      };
    }),
  };
}
```

The current `frontend/src/smartWrongQuestions.ts` already defines `isObjectRecord`. If this helper is moved before implementation begins, keep exactly one copy with this body:

```ts
function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
```

- [ ] **Step 4: Add path builders**

In `frontend/src/smartWrongQuestions.ts`, add:

```ts
export function buildWeeklyWrongQuestionFollowupsPath(classId: number, weekStartDate: string): string {
  return `/api/wrong-question-followups/weekly?class_id=${encodeURIComponent(String(classId))}&week_start=${encodeURIComponent(weekStartDate)}`;
}

export function buildWeeklyWrongQuestionFollowupArchivePath(classId: number, weekStartDate: string): string {
  return `/api/wrong-question-followups/weekly/class-pdf-archive?class_id=${encodeURIComponent(String(classId))}&week_start=${encodeURIComponent(weekStartDate)}`;
}

export function buildWeeklyWrongQuestionFollowupMessagePath(): string {
  return '/api/wrong-question-followups/weekly/messages';
}
```

- [ ] **Step 5: Run frontend helper tests**

Run:

```bash
cd frontend
npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit frontend helpers**

```bash
git add frontend/src/smartWrongQuestions.ts frontend/src/smart-wrong-questions.test.ts
git commit -m "feat: add weekly followup frontend model"
```

---

### Task 6: Web Smart Wrong Questions UI

**Files:**
- Modify: `frontend/src/SmartWrongQuestionsPage.tsx`
- Modify: `frontend/src/smart-wrong-questions.test.ts`

- [ ] **Step 1: Add failing UI tests**

Append to `frontend/src/smart-wrong-questions.test.ts`:

```ts
test('SmartWrongQuestionsPage exposes weekly followup assistant inside the web smart wrong questions page', async () => {
  const fetchCalls: SmartWrongQuestionFetchCall[] = [];
  const root = createRoot(container);
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    fetchCalls.push({ input, init });
    if (input === '/api/classes') {
      return createJsonResponse([{ id: 42, name: '七年级 5 班', subject: '数学', teacher_user_id: 7 }]);
    }
    if (input === '/api/classes/42/students') {
      return createJsonResponse({ students: [{ id: 501, name: '王睿博' }] });
    }
    if (input === '/api/admin/users') {
      return createJsonResponse([{ id: 7, name: 'Kayn' }]);
    }
    if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
      return createJsonResponse({ items: [], summary: { total_count: 0 } });
    }
    if (input === '/api/wrong-question-followups/weekly?class_id=42&week_start=2026-05-04') {
      return createJsonResponse({
        class_id: 42,
        class_name: '七年级 5 班',
        week_start_date: '2026-05-04',
        week_end_date: '2026-05-10',
        total: 1,
        items: [
          {
            student_id: 501,
            student_name: '王睿博',
            weekly_question_count: 3,
            total_active_question_count: 12,
            topic_categories: ['几何'],
            representative_reason_summaries: ['几何第一步容易断'],
            source_record_ids: ['record-a'],
            student_library_pdf_url: '/api/wechat/student-libraries/501',
            message: {
              id: 9,
              message_text: '王睿博妈妈，我刚看了下孩子这周错题。',
              source_record_ids: ['record-a'],
            },
          },
        ],
      });
    }
    throw new Error(`Unexpected fetch: ${String(input)}`);
  }) as typeof fetch;

  await act(async () => {
    root.render(React.createElement(SmartWrongQuestionsPage, {
      currentUser: { display_name: 'Kayn', organization_name: '星润Starain', role: 'owner' },
    }));
  });

  fireEvent.click(screen.getByRole('button', { name: '每周跟进' }));
  await selectNotebookClass(container, '42');
  fireEvent.change(screen.getByLabelText('周次'), { target: { value: '2026-05-04' } });
  fireEvent.click(screen.getByRole('button', { name: '查看跟进清单' }));

  assert.match(container.textContent ?? '', /网页智能错题/);
  assert.match(container.textContent ?? '', /王睿博妈妈，我刚看了下孩子这周错题。/);
  assert.ok(fetchCalls.some((call) => call.input === '/api/wrong-question-followups/weekly?class_id=42&week_start=2026-05-04'));

  root.unmount();
});
```

Add a source-level guard test:

```ts
test('SmartWrongQuestionsPage weekly followup source stays web-only without mini program teacher entry text', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');
  assert.match(pageSource, /每周跟进/);
  assert.match(pageSource, /buildWeeklyWrongQuestionFollowupArchivePath/);
  assert.doesNotMatch(pageSource, /小程序老师端/);
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd frontend
npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: FAIL because UI is not present.

- [ ] **Step 3: Import weekly helpers and types**

In `frontend/src/SmartWrongQuestionsPage.tsx`, extend imports from `./smartWrongQuestions`:

```ts
  buildWeeklyWrongQuestionFollowupArchivePath,
  buildWeeklyWrongQuestionFollowupMessagePath,
  buildWeeklyWrongQuestionFollowupsPath,
  normalizeWeeklyWrongQuestionFollowupResponse,
  type WeeklyWrongQuestionFollowupItem,
```

- [ ] **Step 4: Add view state**

Inside `SmartWrongQuestionsPage`, add:

```ts
  const [weeklyFollowupOpen, setWeeklyFollowupOpen] = useState(false);
  const [weeklyFollowupWeekStart, setWeeklyFollowupWeekStart] = useState(() => {
    const now = new Date();
    const day = now.getDay() || 7;
    const monday = new Date(now);
    monday.setDate(now.getDate() - day + 1);
    return monday.toISOString().slice(0, 10);
  });
  const [weeklyFollowupItems, setWeeklyFollowupItems] = useState<WeeklyWrongQuestionFollowupItem[]>([]);
  const [weeklyFollowupLoading, setWeeklyFollowupLoading] = useState(false);
  const [weeklyFollowupError, setWeeklyFollowupError] = useState('');
  const [weeklyFollowupNotice, setWeeklyFollowupNotice] = useState('');
  const [weeklyFollowupGeneratingStudentId, setWeeklyFollowupGeneratingStudentId] = useState<number | null>(null);
```

- [ ] **Step 5: Add loader/generator/copy handlers**

Inside `SmartWrongQuestionsPage`, add:

```ts
  const loadWeeklyFollowups = useCallback(async () => {
    const classId = selectedClassId ?? selectedStaffClassOption?.id ?? null;
    if (!classId) {
      setWeeklyFollowupError('请先选择班级');
      return;
    }
    setWeeklyFollowupLoading(true);
    setWeeklyFollowupError('');
    try {
      const response = await apiFetch<unknown>(buildWeeklyWrongQuestionFollowupsPath(classId, weeklyFollowupWeekStart));
      const normalized = normalizeWeeklyWrongQuestionFollowupResponse(response);
      setWeeklyFollowupItems(normalized.items);
      setWeeklyFollowupNotice(normalized.items.length > 0 ? `已加载 ${normalized.items.length} 名学生的本周跟进` : '本周暂无需要跟进的错题');
    } catch (err) {
      setWeeklyFollowupError(err instanceof Error ? err.message : '加载每周跟进失败');
    } finally {
      setWeeklyFollowupLoading(false);
    }
  }, [selectedClassId, selectedStaffClassOption?.id, weeklyFollowupWeekStart]);

  const generateWeeklyFollowupMessage = useCallback(async (studentId: number) => {
    const classId = selectedClassId ?? selectedStaffClassOption?.id ?? null;
    if (!classId) {
      return;
    }
    setWeeklyFollowupGeneratingStudentId(studentId);
    setWeeklyFollowupError('');
    try {
      const response = await apiFetch<{ message: { id: number; message_text: string; source_record_ids: string[] } }>(
        buildWeeklyWrongQuestionFollowupMessagePath(),
        {
          method: 'POST',
          body: JSON.stringify({ class_id: classId, week_start: weeklyFollowupWeekStart, student_id: studentId }),
        },
      );
      setWeeklyFollowupItems((current) => current.map((item) => (
        item.studentId === studentId
          ? {
              ...item,
              message: {
                id: response.message.id,
                messageText: response.message.message_text,
                sourceRecordIds: response.message.source_record_ids ?? [],
              },
            }
          : item
      )));
      setWeeklyFollowupNotice('文案已生成');
    } catch (err) {
      setWeeklyFollowupError(err instanceof Error ? err.message : '生成文案失败');
    } finally {
      setWeeklyFollowupGeneratingStudentId(null);
    }
  }, [selectedClassId, selectedStaffClassOption?.id, weeklyFollowupWeekStart]);

  const copyWeeklyFollowupMessage = useCallback(async (messageText: string) => {
    await navigator.clipboard.writeText(messageText);
    setWeeklyFollowupNotice('已复制，可以直接发给家长');
  }, []);
```

In the UI test file setup, ensure clipboard exists before rendering:

```ts
Object.assign(navigator, {
  clipboard: {
    writeText: async () => undefined,
  },
});
```

- [ ] **Step 6: Add class zip handler**

Inside `SmartWrongQuestionsPage`, add:

```ts
  const openWeeklyFollowupArchive = useCallback(() => {
    const classId = selectedClassId ?? selectedStaffClassOption?.id ?? null;
    if (!classId) {
      setWeeklyFollowupError('请先选择班级');
      return;
    }
    window.open(buildWrongQuestionAuthedPath(buildWeeklyWrongQuestionFollowupArchivePath(classId, weeklyFollowupWeekStart)), '_blank', 'noopener,noreferrer');
  }, [selectedClassId, selectedStaffClassOption?.id, weeklyFollowupWeekStart]);
```

- [ ] **Step 7: Add the web-only assistant UI**

Near the Smart Wrong Questions header controls, add a button:

```tsx
<button
  type="button"
  className={workspaceSecondaryButtonClass}
  onClick={() => setWeeklyFollowupOpen((value) => !value)}
>
  每周跟进
</button>
```

Below the existing filter/summary area, render:

```tsx
{weeklyFollowupOpen && (
  <section className={`${workspaceCardClass} mt-4 p-5`}>
    <div className="flex flex-wrap items-end gap-3">
      <div>
        <label className="text-xs font-semibold text-slate-500" htmlFor="weekly-followup-week-start">周次</label>
        <input
          id="weekly-followup-week-start"
          aria-label="周次"
          type="date"
          className={workspaceFieldClass}
          value={weeklyFollowupWeekStart}
          onChange={(event) => setWeeklyFollowupWeekStart(event.target.value)}
        />
      </div>
      <button type="button" className={workspacePrimaryButtonClass} onClick={() => void loadWeeklyFollowups()} disabled={weeklyFollowupLoading}>
        {weeklyFollowupLoading ? '加载中...' : '查看跟进清单'}
      </button>
      <button type="button" className={workspaceSecondaryButtonClass} onClick={openWeeklyFollowupArchive}>
        下载本班错题本合集
      </button>
    </div>
    <p className="mt-3 text-sm text-slate-500">网页智能错题内使用，老师复制后发微信给家长。</p>
    {weeklyFollowupError && <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{weeklyFollowupError}</div>}
    {weeklyFollowupNotice && <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{weeklyFollowupNotice}</div>}
    <div className="mt-4 grid gap-3">
      {weeklyFollowupItems.map((item) => (
        <article key={item.studentId} className={`${workspaceSoftCardClass} p-4`}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold text-slate-900 dark:text-white">{item.studentName}</h3>
              <p className="mt-1 text-sm text-slate-500">本周 {item.weeklyQuestionCount} 题 · 错题本共 {item.totalActiveQuestionCount} 题 · {item.topicCategories.join('、') || '未分类'}</p>
            </div>
            <a className={workspaceSecondaryButtonClass} href={buildWrongQuestionAuthedPath(item.studentLibraryPdfUrl)} target="_blank" rel="noreferrer">
              查看错题本
            </a>
          </div>
          <div className="mt-3 rounded-lg bg-white/80 p-3 text-sm leading-relaxed text-slate-700 dark:bg-slate-950/30 dark:text-slate-200">
            {item.message?.messageText || '还没有生成微信话术。'}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className={workspacePrimaryButtonClass} disabled={!item.message?.messageText} onClick={() => item.message?.messageText && void copyWeeklyFollowupMessage(item.message.messageText)}>
              复制给家长
            </button>
            <button type="button" className={workspaceSecondaryButtonClass} disabled={weeklyFollowupGeneratingStudentId === item.studentId} onClick={() => void generateWeeklyFollowupMessage(item.studentId)}>
              {item.message ? '重新生成' : '生成文案'}
            </button>
          </div>
        </article>
      ))}
    </div>
  </section>
)}
```

Use the existing `workspaceCardClass`, `workspaceSoftCardClass`, `workspaceFieldClass`, `workspacePrimaryButtonClass`, and `workspaceSecondaryButtonClass` imports already present in `SmartWrongQuestionsPage.tsx`.

- [ ] **Step 8: Run frontend UI tests**

Run:

```bash
cd frontend
npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: PASS.

- [ ] **Step 9: Commit web UI**

```bash
git add frontend/src/SmartWrongQuestionsPage.tsx frontend/src/smart-wrong-questions.test.ts
git commit -m "feat: add weekly followup assistant ui"
```

---

### Task 7: Full Verification and Handoff

**Files:**
- Modify: `handoff.md`

- [ ] **Step 1: Run backend focused verification**

Run:

```bash
python -m unittest tests.test_weekly_wrong_question_followups tests.test_wrong_question_practice_async_api tests.test_wechat_parent_upload_api -v
```

Expected: PASS. When a historical unrelated suite failure appears, stop and record the exact failing test name, assertion, and command output before narrowing proof.

- [ ] **Step 2: Run frontend focused verification**

Run:

```bash
cd frontend
npx tsx --test src/smart-wrong-questions.test.ts
npm run build
```

Expected: PASS and production build succeeds.

- [ ] **Step 3: Run diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only intended tracked files changed.

- [ ] **Step 4: Update `handoff.md`**

Add this current-status bullet near the top:

```markdown
- 2026-05-04 已实现网页智能错题内“每周错题跟进助手”：老师可按班级/周次查看本周有错题的学生，生成/复制更像老师真人微信的家长沟通话术，打开单个学生错题本 PDF，并下载本班学生错题本 zip 合集。功能不包含小程序老师端、不做小程序订阅消息推送、不做家长已读或学生打卡。
```

- [ ] **Step 5: Commit final handoff**

```bash
git add handoff.md
git commit -m "docs: record weekly followup implementation"
```

- [ ] **Step 6: Confirm branch freshness before merging**

Run:

```bash
git fetch origin
git rev-list --left-right --count origin/develop...HEAD
```

Expected: `0 N`, where `N` is the number of implementation commits on this branch. When the left number is not `0`, rebase onto `origin/develop` and rerun focused verification.

- [ ] **Step 7: Merge back to `develop`, push, and clean worktree**

Run from the implementation worktree first:

```bash
git push origin HEAD:develop
```

Then run from the main repository:

```bash
git worktree remove /Users/xiaodi/Desktop/xingrun.web-weekly-followup-implementation
git branch -D feature/weekly-wrong-question-followup-implementation
```

When the implementation branch/worktree names differ from the names above, substitute those exact names in the cleanup command. Do not merge to `master`.

---

## Self-Review

Spec coverage:

- Web Smart Wrong Questions entry: Task 6.
- No mini program teacher endpoint/entry: Tasks 3 and 6 tests.
- Student weekly list by class/week: Tasks 1 and 3.
- Natural WeChat copy generation and regeneration: Tasks 2, 3, and 6.
- Single student PDF access: Task 6 uses existing `student_library_pdf_url`.
- Class zip download: Task 4 and Task 6.
- Permission scope: Task 3.
- No read receipts, push, check-ins, or automatic group send: no task creates those surfaces.

Placeholder scan: no red-flag placeholder wording or unspecified error-handling steps remain.

Type consistency:

- Backend JSON uses snake_case.
- Frontend normalizer converts to camelCase.
- Message cache uses `style='warm'` consistently.
