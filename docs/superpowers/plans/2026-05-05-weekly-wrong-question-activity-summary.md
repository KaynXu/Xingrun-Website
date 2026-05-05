# Weekly Wrong Question Activity Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `super_owner`-only weekly activity summary inside the web `智能错题` page, listing active classes, teachers, and students from high to low by weekly wrong-question activity.

**Architecture:** Reuse the existing Flask + SQLite wrong-question data model and the existing web `智能错题` React page. Add one focused store helper in `lesson_manager.py`, expose it through a `super_owner` admin API in `app.py`, normalize the payload in `frontend/src/smartWrongQuestions.ts`, and render a compact read-only panel in `frontend/src/SmartWrongQuestionsPage.tsx`.

**Tech Stack:** Python 3, Flask, SQLite, unittest, Vite, React, TypeScript, `tsx --test`.

---

## File Structure

- Modify: `lesson_manager.py`
  - Add `list_weekly_wrong_question_activity_summary()`.
  - Keep aggregation in one store helper so Flask and tests share the same data contract.
- Modify: `app.py`
  - Import the new helper.
  - Add `GET /api/admin/wrong-question-activity-summary`.
  - Reuse `_require_super_owner()` and `_weekly_range()`.
- Create: `tests/test_weekly_wrong_question_activity_summary.py`
  - Cover store aggregation, sorting, organization filtering, permissions, and invalid week handling.
- Modify: `frontend/src/smartWrongQuestions.ts`
  - Add TypeScript interfaces, path builder, and response normalizer for the summary API.
- Modify: `frontend/src/SmartWrongQuestionsPage.tsx`
  - Add `super_owner`-only `本周数据总结` panel.
  - Load organization options through existing `/api/admin/organizations`.
  - Render three lists without strong ranking wording.
- Modify: `frontend/src/smart-wrong-questions.test.ts`
  - Cover the path builder, normalizer, and source wiring.
- Modify: `handoff.md`
  - Record that the implementation landed, remaining manual smoke, and proof script path.

## Data Contract

`GET /api/admin/wrong-question-activity-summary?week_start=2026-05-04&organization_id=3`

Response:

```json
{
  "week_start": "2026-05-04",
  "week_end": "2026-05-10",
  "class_items": [
    {
      "organization_id": 3,
      "organization_name": "星润",
      "class_id": 15,
      "class_name": "七年级5班",
      "weekly_question_count": 18,
      "uploading_student_count": 6,
      "latest_created_at": "2026-05-04 18:32:00"
    }
  ],
  "teacher_items": [
    {
      "organization_id": 3,
      "organization_name": "星润",
      "teacher_user_id": 9,
      "teacher_name": "王老师",
      "class_count": 2,
      "weekly_question_count": 31,
      "involved_student_count": 12,
      "pending_followup_count": 5
    }
  ],
  "student_items": [
    {
      "organization_id": 3,
      "organization_name": "星润",
      "class_id": 15,
      "class_name": "七年级5班",
      "student_id": 76,
      "student_name": "王睿博",
      "weekly_question_count": 7,
      "total_question_count": 24,
      "topic_categories": ["几何", "计算"],
      "latest_created_at": "2026-05-04 18:32:00"
    }
  ]
}
```

Counting rules:

- Weekly rows are `wrong_question_submissions` rows with `source='wechat_mp'`, `recognition_status='recognized'`, matching `created_at` week bounds, and present `organization_id/class_id/student_id`.
- Deleted rows are absent from the table and therefore excluded.
- Weekly activity counts include recognized rows even if a teacher later marks them mastered, because they still happened this week.
- `pending_followup_count` counts weekly rows with `archive_status='active'`.
- `total_question_count` counts all recognized rows for that student outside the week filter.

---

### Task 1: Add Store Aggregation

**Files:**
- Create: `tests/test_weekly_wrong_question_activity_summary.py`
- Modify: `lesson_manager.py`

- [x] **Step 1: Write failing store tests**

Create `tests/test_weekly_wrong_question_activity_summary.py` with this content:

```python
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lesson_manager


class WeeklyWrongQuestionActivitySummaryStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        lesson_manager.DB_PATH = Path(self.temp_dir.name) / "xingrun.db"
        lesson_manager.init_db()

        org_request = lesson_manager.create_organization_request(
            "活跃汇总测试机构",
            "activity_owner",
            "活跃汇总负责人",
            "owner-pass",
            recovery_phone="13800000001",
        )
        super_owner = lesson_manager.get_user_by_username("Kayn")
        approved = lesson_manager.approve_organization_request(org_request["id"], super_owner["id"])
        self.organization_id = approved["organization"]["id"]
        self.owner_id = approved["owner"]["id"]

        self.class_a = lesson_manager.save_class(
            "五年级3班",
            subject="数学",
            grade="五年级",
            organization_id=self.organization_id,
        )
        self.class_b = lesson_manager.save_class(
            "六年级2班",
            subject="数学",
            grade="六年级",
            organization_id=self.organization_id,
        )
        lesson_manager.set_class_teacher_user_id(self.class_a, self.owner_id)
        lesson_manager.set_class_teacher_user_id(self.class_b, self.owner_id)
        self.alice = lesson_manager.create_student_for_class(self.class_a, "Alice")
        self.bob = lesson_manager.create_student_for_class(self.class_a, "Bob")
        self.cindy = lesson_manager.create_student_for_class(self.class_b, "Cindy")
        self.parent = lesson_manager.upsert_parent_wechat_account(openid="openid-activity")
        self.alice_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=self.parent["id"],
            class_id=self.class_a,
            student_id=self.alice["id"],
        )
        self.bob_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=self.parent["id"],
            class_id=self.class_a,
            student_id=self.bob["id"],
        )
        self.cindy_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=self.parent["id"],
            class_id=self.class_b,
            student_id=self.cindy["id"],
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _record(self, *, binding_id: int, created_at: str, topic_category: str, archive_status: str = "active"):
        record = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding_id,
            image_url=f"https://files.example.com/{binding_id}-{created_at}.png",
            recognition_status="recognized",
            topic_category=topic_category,
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE wrong_question_submissions SET created_at=?, archive_status=? WHERE id=?",
                (created_at, archive_status, record["id"]),
            )
        return record

    def test_activity_summary_lists_classes_teachers_and_students_from_high_to_low(self):
        self._record(binding_id=self.alice_binding["id"], created_at="2026-05-04 09:00:00", topic_category="几何")
        self._record(binding_id=self.alice_binding["id"], created_at="2026-05-04 10:00:00", topic_category="几何")
        self._record(binding_id=self.alice_binding["id"], created_at="2026-05-04 11:00:00", topic_category="计算")
        self._record(binding_id=self.bob_binding["id"], created_at="2026-05-05 12:00:00", topic_category="计算")
        self._record(binding_id=self.cindy_binding["id"], created_at="2026-05-06 13:00:00", topic_category="应用题", archive_status="archived")
        self._record(binding_id=self.cindy_binding["id"], created_at="2026-04-30 13:00:00", topic_category="几何")

        summary = lesson_manager.list_weekly_wrong_question_activity_summary(
            week_start_date="2026-05-04",
            week_end_date="2026-05-10",
        )

        self.assertEqual([item["class_name"] for item in summary["class_items"]], ["五年级3班", "六年级2班"])
        self.assertEqual(summary["class_items"][0]["weekly_question_count"], 4)
        self.assertEqual(summary["class_items"][0]["uploading_student_count"], 2)
        self.assertEqual(summary["class_items"][0]["latest_created_at"], "2026-05-05 12:00:00")

        self.assertEqual(len(summary["teacher_items"]), 1)
        teacher = summary["teacher_items"][0]
        self.assertEqual(teacher["teacher_name"], "活跃汇总负责人")
        self.assertEqual(teacher["class_count"], 2)
        self.assertEqual(teacher["weekly_question_count"], 5)
        self.assertEqual(teacher["involved_student_count"], 3)
        self.assertEqual(teacher["pending_followup_count"], 4)

        self.assertEqual([item["student_name"] for item in summary["student_items"]], ["Alice", "Cindy", "Bob"])
        self.assertEqual(summary["student_items"][0]["weekly_question_count"], 3)
        self.assertEqual(summary["student_items"][0]["total_question_count"], 3)
        self.assertEqual(summary["student_items"][0]["topic_categories"], ["几何", "计算"])
        self.assertEqual(summary["student_items"][1]["total_question_count"], 2)

    def test_activity_summary_filters_by_organization(self):
        self._record(binding_id=self.alice_binding["id"], created_at="2026-05-04 09:00:00", topic_category="几何")
        other_org_request = lesson_manager.create_organization_request(
            "另一个机构",
            "activity_other_owner",
            "另一个负责人",
            "owner-pass",
            recovery_phone="13800000002",
        )
        super_owner = lesson_manager.get_user_by_username("Kayn")
        other_approved = lesson_manager.approve_organization_request(other_org_request["id"], super_owner["id"])
        other_class = lesson_manager.save_class(
            "三年级1班",
            subject="数学",
            grade="三年级",
            organization_id=other_approved["organization"]["id"],
        )
        lesson_manager.set_class_teacher_user_id(other_class, other_approved["owner"]["id"])
        other_student = lesson_manager.create_student_for_class(other_class, "Other")
        other_parent = lesson_manager.upsert_parent_wechat_account(openid="openid-activity-other")
        other_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=other_parent["id"],
            class_id=other_class,
            student_id=other_student["id"],
        )
        self._record(binding_id=other_binding["id"], created_at="2026-05-04 10:00:00", topic_category="计算")

        summary = lesson_manager.list_weekly_wrong_question_activity_summary(
            week_start_date="2026-05-04",
            week_end_date="2026-05-10",
            organization_id=self.organization_id,
        )

        self.assertEqual([item["organization_id"] for item in summary["class_items"]], [self.organization_id])
        self.assertEqual([item["class_name"] for item in summary["class_items"]], ["五年级3班"])
        self.assertEqual([item["student_name"] for item in summary["student_items"]], ["Alice"])
```

- [x] **Step 2: Run store tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_weekly_wrong_question_activity_summary -v
```

Expected: FAIL with `AttributeError: module 'lesson_manager' has no attribute 'list_weekly_wrong_question_activity_summary'`.

- [x] **Step 3: Implement the store helper**

Add this function near `list_weekly_wrong_question_followup_students()` in `lesson_manager.py`:

```python
def list_weekly_wrong_question_activity_summary(
    *,
    week_start_date: str,
    week_end_date: str,
    organization_id: int | None = None,
    limit: int = 10,
) -> dict:
    week_start_bound = f"{(week_start_date or '').strip()} 00:00:00"
    week_end_bound = f"{(week_end_date or '').strip()} 23:59:59"
    normalized_limit = max(1, int(limit or 10))
    normalized_organization_id = int(organization_id or 0)
    params: list[object] = [week_start_bound, week_end_bound]
    organization_clause = ""
    if normalized_organization_id:
        organization_clause = " AND wqs.organization_id=?"
        params.append(normalized_organization_id)

    with get_conn() as conn:
        weekly_rows = conn.execute(
            f"""
            SELECT
                wqs.id,
                wqs.organization_id,
                wqs.class_id,
                wqs.student_id,
                wqs.teacher_user_id,
                wqs.topic_category,
                wqs.archive_status,
                wqs.created_at,
                COALESCE(o.name, '') AS organization_name,
                COALESCE(c.name, '') AS class_name,
                COALESCE(s.name, '') AS student_name,
                COALESCE(u.display_name, '') AS teacher_name
            FROM wrong_question_submissions wqs
            JOIN classes c ON c.id = wqs.class_id
            JOIN students s ON s.id = wqs.student_id
            LEFT JOIN users u ON u.id = wqs.teacher_user_id
            LEFT JOIN organizations o ON o.id = wqs.organization_id
            WHERE wqs.source='wechat_mp'
              AND wqs.recognition_status='recognized'
              AND wqs.organization_id IS NOT NULL
              AND wqs.class_id IS NOT NULL
              AND wqs.student_id IS NOT NULL
              AND wqs.created_at >= ?
              AND wqs.created_at <= ?
              {organization_clause}
            ORDER BY wqs.created_at DESC, wqs.id DESC
            """,
            tuple(params),
        ).fetchall()

        total_params: list[object] = []
        total_organization_clause = ""
        if normalized_organization_id:
            total_organization_clause = " AND organization_id=?"
            total_params.append(normalized_organization_id)
        total_rows = conn.execute(
            f"""
            SELECT student_id, COUNT(*) AS total_question_count
            FROM wrong_question_submissions
            WHERE source='wechat_mp'
              AND recognition_status='recognized'
              AND student_id IS NOT NULL
              {total_organization_clause}
            GROUP BY student_id
            """,
            tuple(total_params),
        ).fetchall()

    total_by_student_id = {
        int(row["student_id"]): int(row["total_question_count"] or 0)
        for row in total_rows
    }
    class_summaries: dict[int, dict] = {}
    teacher_summaries: dict[int, dict] = {}
    student_summaries: dict[int, dict] = {}

    for row in weekly_rows:
        class_id = int(row["class_id"] or 0)
        student_id = int(row["student_id"] or 0)
        teacher_user_id = int(row["teacher_user_id"] or 0)
        organization_value = int(row["organization_id"] or 0)
        topic_category = normalize_primary_wrong_question_topic_category(str(row["topic_category"] or ""))
        created_at = str(row["created_at"] or "")

        class_summary = class_summaries.setdefault(
            class_id,
            {
                "organization_id": organization_value,
                "organization_name": str(row["organization_name"] or ""),
                "class_id": class_id,
                "class_name": str(row["class_name"] or ""),
                "weekly_question_count": 0,
                "uploading_student_ids": set(),
                "latest_created_at": created_at,
            },
        )
        class_summary["weekly_question_count"] += 1
        class_summary["uploading_student_ids"].add(student_id)
        if created_at > str(class_summary["latest_created_at"] or ""):
            class_summary["latest_created_at"] = created_at

        if teacher_user_id:
            teacher_summary = teacher_summaries.setdefault(
                teacher_user_id,
                {
                    "organization_id": organization_value,
                    "organization_name": str(row["organization_name"] or ""),
                    "teacher_user_id": teacher_user_id,
                    "teacher_name": str(row["teacher_name"] or ""),
                    "class_ids": set(),
                    "weekly_question_count": 0,
                    "student_ids": set(),
                    "pending_followup_count": 0,
                },
            )
            teacher_summary["weekly_question_count"] += 1
            teacher_summary["class_ids"].add(class_id)
            teacher_summary["student_ids"].add(student_id)
            if str(row["archive_status"] or "") == "active":
                teacher_summary["pending_followup_count"] += 1

        student_summary = student_summaries.setdefault(
            student_id,
            {
                "organization_id": organization_value,
                "organization_name": str(row["organization_name"] or ""),
                "class_id": class_id,
                "class_name": str(row["class_name"] or ""),
                "student_id": student_id,
                "student_name": str(row["student_name"] or ""),
                "weekly_question_count": 0,
                "total_question_count": total_by_student_id.get(student_id, 0),
                "topic_counts": {},
                "latest_created_at": created_at,
            },
        )
        student_summary["weekly_question_count"] += 1
        student_summary["topic_counts"][topic_category] = int(student_summary["topic_counts"].get(topic_category, 0)) + 1
        if created_at > str(student_summary["latest_created_at"] or ""):
            student_summary["latest_created_at"] = created_at

    class_items = []
    for item in class_summaries.values():
        class_items.append(
            {
                "organization_id": item["organization_id"],
                "organization_name": item["organization_name"],
                "class_id": item["class_id"],
                "class_name": item["class_name"],
                "weekly_question_count": item["weekly_question_count"],
                "uploading_student_count": len(item["uploading_student_ids"]),
                "latest_created_at": item["latest_created_at"],
            }
        )

    teacher_items = []
    for item in teacher_summaries.values():
        teacher_items.append(
            {
                "organization_id": item["organization_id"],
                "organization_name": item["organization_name"],
                "teacher_user_id": item["teacher_user_id"],
                "teacher_name": item["teacher_name"],
                "class_count": len(item["class_ids"]),
                "weekly_question_count": item["weekly_question_count"],
                "involved_student_count": len(item["student_ids"]),
                "pending_followup_count": item["pending_followup_count"],
            }
        )

    student_items = []
    for item in student_summaries.values():
        topic_categories = [
            topic
            for topic, _count in sorted(
                item["topic_counts"].items(),
                key=lambda pair: (-int(pair[1]), str(pair[0])),
            )[:3]
        ]
        student_items.append(
            {
                "organization_id": item["organization_id"],
                "organization_name": item["organization_name"],
                "class_id": item["class_id"],
                "class_name": item["class_name"],
                "student_id": item["student_id"],
                "student_name": item["student_name"],
                "weekly_question_count": item["weekly_question_count"],
                "total_question_count": item["total_question_count"],
                "topic_categories": topic_categories or [PRIMARY_WRONG_QUESTION_TOPIC_UNCLASSIFIED],
                "latest_created_at": item["latest_created_at"],
            }
        )

    class_items = sorted(
        class_items,
        key=lambda item: (
            -int(item["weekly_question_count"] or 0),
            -int(item["uploading_student_count"] or 0),
            str(item["latest_created_at"] or ""),
        ),
        reverse=False,
    )[:normalized_limit]
    teacher_items = sorted(
        teacher_items,
        key=lambda item: (
            -int(item["weekly_question_count"] or 0),
            -int(item["involved_student_count"] or 0),
            -int(item["pending_followup_count"] or 0),
            str(item["teacher_name"] or ""),
        ),
    )[:normalized_limit]
    student_items = sorted(
        student_items,
        key=lambda item: (
            -int(item["weekly_question_count"] or 0),
            -int(item["total_question_count"] or 0),
            str(item["latest_created_at"] or ""),
        ),
        reverse=False,
    )[:normalized_limit]

    return {
        "class_items": class_items,
        "teacher_items": teacher_items,
        "student_items": student_items,
    }
```

- [x] **Step 4: Run store tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_weekly_wrong_question_activity_summary -v
```

Expected: PASS.

- [x] **Step 5: Commit store aggregation**

Run:

```bash
git add lesson_manager.py tests/test_weekly_wrong_question_activity_summary.py
git commit -m "feat: add weekly wrong question activity aggregation"
```

---

### Task 2: Add Super Admin API

**Files:**
- Modify: `app.py`
- Modify: `tests/test_weekly_wrong_question_activity_summary.py`

- [x] **Step 1: Write failing API tests**

Append this class to `tests/test_weekly_wrong_question_activity_summary.py`:

```python
class WeeklyWrongQuestionActivitySummaryApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        lesson_manager.DB_PATH = Path(self.temp_dir.name) / "xingrun.db"
        lesson_manager.init_db()

        import app as app_module

        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()
        super_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(super_login.status_code, 200)
        self.super_headers = {"X-Auth-Token": super_login.get_json()["token"]}

        org_request = lesson_manager.create_organization_request(
            "活跃 API 测试机构",
            "activity_api_owner",
            "活跃 API 负责人",
            "owner-pass",
            recovery_phone="13800000003",
        )
        super_owner = lesson_manager.get_user_by_username("Kayn")
        approved = lesson_manager.approve_organization_request(org_request["id"], super_owner["id"])
        self.organization_id = approved["organization"]["id"]
        self.owner_id = approved["owner"]["id"]
        owner_login = self.client.post(
            "/api/login",
            json={"username": "activity_api_owner", "password": "owner-pass"},
        )
        self.assertEqual(owner_login.status_code, 200)
        self.owner_headers = {"X-Auth-Token": owner_login.get_json()["token"]}

        self.class_id = lesson_manager.save_class(
            "五年级3班",
            subject="数学",
            grade="五年级",
            organization_id=self.organization_id,
        )
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner_id)
        student = lesson_manager.create_student_for_class(self.class_id, "Alice")
        parent = lesson_manager.upsert_parent_wechat_account(openid="openid-activity-api")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=parent["id"],
            class_id=self.class_id,
            student_id=student["id"],
        )
        record = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/activity-api.png",
            recognition_status="recognized",
            topic_category="计算",
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE wrong_question_submissions SET created_at=? WHERE id=?",
                ("2026-05-04 09:00:00", record["id"]),
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_super_owner_can_get_weekly_activity_summary(self):
        response = self.client.get(
            "/api/admin/wrong-question-activity-summary?week_start=2026-05-04",
            headers=self.super_headers,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["week_start"], "2026-05-04")
        self.assertEqual(payload["week_end"], "2026-05-10")
        self.assertEqual(payload["class_items"][0]["class_name"], "五年级3班")
        self.assertEqual(payload["student_items"][0]["student_name"], "Alice")

    def test_activity_summary_supports_organization_filter(self):
        response = self.client.get(
            f"/api/admin/wrong-question-activity-summary?week_start=2026-05-04&organization_id={self.organization_id}",
            headers=self.super_headers,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual([item["organization_id"] for item in payload["class_items"]], [self.organization_id])

    def test_non_super_owner_cannot_get_activity_summary(self):
        response = self.client.get(
            "/api/admin/wrong-question-activity-summary?week_start=2026-05-04",
            headers=self.owner_headers,
        )

        self.assertEqual(response.status_code, 403)

    def test_activity_summary_rejects_invalid_week_start(self):
        response = self.client.get(
            "/api/admin/wrong-question-activity-summary?week_start=not-a-date",
            headers=self.super_headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "week_start must be YYYY-MM-DD")
```

- [x] **Step 2: Run API tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_weekly_wrong_question_activity_summary -v
```

Expected: FAIL with `404` for `/api/admin/wrong-question-activity-summary`.

- [x] **Step 3: Wire the helper into Flask**

In `app.py`, add `list_weekly_wrong_question_activity_summary` to the existing `lesson_manager` import list.

Add this route after `api_admin_organizations()`:

```python
@app.route("/api/admin/wrong-question-activity-summary", methods=["GET"])
def api_admin_wrong_question_activity_summary():
    _, error = _require_super_owner()
    if error:
        return error
    try:
        week_start_date, week_end_date = _weekly_range(request.args.get("week_start", ""))
    except ValueError:
        return jsonify({"error": "week_start must be YYYY-MM-DD"}), 400

    organization_id = request.args.get("organization_id", 0, type=int)
    summary = list_weekly_wrong_question_activity_summary(
        week_start_date=week_start_date,
        week_end_date=week_end_date,
        organization_id=organization_id if organization_id else None,
    )
    return jsonify(
        {
            "week_start": week_start_date,
            "week_end": week_end_date,
            "class_items": summary["class_items"],
            "teacher_items": summary["teacher_items"],
            "student_items": summary["student_items"],
        }
    )
```

- [x] **Step 4: Run backend focused tests**

Run:

```bash
python3 -m unittest tests.test_weekly_wrong_question_activity_summary tests.test_weekly_wrong_question_followups -v
```

Expected: PASS.

- [x] **Step 5: Commit API layer**

Run:

```bash
git add app.py tests/test_weekly_wrong_question_activity_summary.py
git commit -m "feat: expose weekly activity summary API"
```

---

### Task 3: Add Frontend Data Model

**Files:**
- Modify: `frontend/src/smartWrongQuestions.ts`
- Modify: `frontend/src/smart-wrong-questions.test.ts`

- [x] **Step 1: Write failing model tests**

Add imports in `frontend/src/smart-wrong-questions.test.ts`:

```typescript
  buildWeeklyWrongQuestionActivitySummaryPath,
  normalizeWeeklyWrongQuestionActivitySummaryResponse,
```

Add these tests near the existing weekly followup tests:

```typescript
test('weekly activity summary path builder supports optional organization filtering', () => {
  assert.equal(
    buildWeeklyWrongQuestionActivitySummaryPath('2026-05-04'),
    '/api/admin/wrong-question-activity-summary?week_start=2026-05-04',
  );
  assert.equal(
    buildWeeklyWrongQuestionActivitySummaryPath('2026-05-04', 12),
    '/api/admin/wrong-question-activity-summary?week_start=2026-05-04&organization_id=12',
  );
});

test('normalizeWeeklyWrongQuestionActivitySummaryResponse preserves class teacher and student lists', () => {
  const normalized = normalizeWeeklyWrongQuestionActivitySummaryResponse({
    week_start: '2026-05-04',
    week_end: '2026-05-10',
    class_items: [
      {
        organization_id: 1,
        organization_name: '星润',
        class_id: 15,
        class_name: '五年级3班',
        weekly_question_count: 18,
        uploading_student_count: 6,
        latest_created_at: '2026-05-04 18:32:00',
      },
    ],
    teacher_items: [
      {
        organization_id: 1,
        organization_name: '星润',
        teacher_user_id: 9,
        teacher_name: '王老师',
        class_count: 2,
        weekly_question_count: 31,
        involved_student_count: 12,
        pending_followup_count: 5,
      },
    ],
    student_items: [
      {
        organization_id: 1,
        organization_name: '星润',
        class_id: 15,
        class_name: '七年级5班',
        student_id: 76,
        student_name: '王睿博',
        weekly_question_count: 7,
        total_question_count: 24,
        topic_categories: ['几何', '计算'],
        latest_created_at: '2026-05-04 18:32:00',
      },
    ],
  });

  assert.equal(normalized.weekStart, '2026-05-04');
  assert.equal(normalized.weekEnd, '2026-05-10');
  assert.equal(normalized.classItems[0]?.className, '五年级3班');
  assert.equal(normalized.classItems[0]?.uploadingStudentCount, 6);
  assert.equal(normalized.teacherItems[0]?.pendingFollowupCount, 5);
  assert.equal(normalized.studentItems[0]?.topicCategories.join('、'), '几何、计算');
});
```

- [x] **Step 2: Run frontend model tests to verify they fail**

Run:

```bash
cd frontend && npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: FAIL with missing exports from `smartWrongQuestions.ts`.

- [x] **Step 3: Add interfaces, path builder, and normalizer**

In `frontend/src/smartWrongQuestions.ts`, add these interfaces near the weekly followup interfaces:

```typescript
export interface WeeklyWrongQuestionActivityClassItem {
  organizationId: number;
  organizationName: string;
  classId: number;
  className: string;
  weeklyQuestionCount: number;
  uploadingStudentCount: number;
  latestCreatedAt: string;
}

export interface WeeklyWrongQuestionActivityTeacherItem {
  organizationId: number;
  organizationName: string;
  teacherUserId: number;
  teacherName: string;
  classCount: number;
  weeklyQuestionCount: number;
  involvedStudentCount: number;
  pendingFollowupCount: number;
}

export interface WeeklyWrongQuestionActivityStudentItem {
  organizationId: number;
  organizationName: string;
  classId: number;
  className: string;
  studentId: number;
  studentName: string;
  weeklyQuestionCount: number;
  totalQuestionCount: number;
  topicCategories: string[];
  latestCreatedAt: string;
}

export interface WeeklyWrongQuestionActivitySummary {
  weekStart: string;
  weekEnd: string;
  classItems: WeeklyWrongQuestionActivityClassItem[];
  teacherItems: WeeklyWrongQuestionActivityTeacherItem[];
  studentItems: WeeklyWrongQuestionActivityStudentItem[];
}
```

Add these functions near the weekly followup path builders:

```typescript
export function buildWeeklyWrongQuestionActivitySummaryPath(weekStartDate: string, organizationId?: number | null): string {
  const params = new URLSearchParams({ week_start: weekStartDate });
  if (typeof organizationId === 'number' && Number.isFinite(organizationId) && organizationId > 0) {
    params.set('organization_id', String(organizationId));
  }
  return `/api/admin/wrong-question-activity-summary?${params.toString()}`;
}

export function normalizeWeeklyWrongQuestionActivitySummaryResponse(payload: unknown): WeeklyWrongQuestionActivitySummary {
  const source = isObjectRecord(payload) ? payload : {};
  const rawClassItems = Array.isArray(source.class_items) ? source.class_items : [];
  const rawTeacherItems = Array.isArray(source.teacher_items) ? source.teacher_items : [];
  const rawStudentItems = Array.isArray(source.student_items) ? source.student_items : [];
  return {
    weekStart: String(source.week_start ?? source.weekStart ?? ''),
    weekEnd: String(source.week_end ?? source.weekEnd ?? ''),
    classItems: rawClassItems.filter(isObjectRecord).map((item) => ({
      organizationId: pickNumberValue(item, ['organization_id', 'organizationId']) ?? 0,
      organizationName: String(item.organization_name ?? item.organizationName ?? ''),
      classId: pickNumberValue(item, ['class_id', 'classId']) ?? 0,
      className: String(item.class_name ?? item.className ?? ''),
      weeklyQuestionCount: pickNumberValue(item, ['weekly_question_count', 'weeklyQuestionCount']) ?? 0,
      uploadingStudentCount: pickNumberValue(item, ['uploading_student_count', 'uploadingStudentCount']) ?? 0,
      latestCreatedAt: String(item.latest_created_at ?? item.latestCreatedAt ?? ''),
    })),
    teacherItems: rawTeacherItems.filter(isObjectRecord).map((item) => ({
      organizationId: pickNumberValue(item, ['organization_id', 'organizationId']) ?? 0,
      organizationName: String(item.organization_name ?? item.organizationName ?? ''),
      teacherUserId: pickNumberValue(item, ['teacher_user_id', 'teacherUserId']) ?? 0,
      teacherName: String(item.teacher_name ?? item.teacherName ?? ''),
      classCount: pickNumberValue(item, ['class_count', 'classCount']) ?? 0,
      weeklyQuestionCount: pickNumberValue(item, ['weekly_question_count', 'weeklyQuestionCount']) ?? 0,
      involvedStudentCount: pickNumberValue(item, ['involved_student_count', 'involvedStudentCount']) ?? 0,
      pendingFollowupCount: pickNumberValue(item, ['pending_followup_count', 'pendingFollowupCount']) ?? 0,
    })),
    studentItems: rawStudentItems.filter(isObjectRecord).map((item) => ({
      organizationId: pickNumberValue(item, ['organization_id', 'organizationId']) ?? 0,
      organizationName: String(item.organization_name ?? item.organizationName ?? ''),
      classId: pickNumberValue(item, ['class_id', 'classId']) ?? 0,
      className: String(item.class_name ?? item.className ?? ''),
      studentId: pickNumberValue(item, ['student_id', 'studentId']) ?? 0,
      studentName: String(item.student_name ?? item.studentName ?? ''),
      weeklyQuestionCount: pickNumberValue(item, ['weekly_question_count', 'weeklyQuestionCount']) ?? 0,
      totalQuestionCount: pickNumberValue(item, ['total_question_count', 'totalQuestionCount']) ?? 0,
      topicCategories: normalizeStringList(item.topic_categories ?? item.topicCategories),
      latestCreatedAt: String(item.latest_created_at ?? item.latestCreatedAt ?? ''),
    })),
  };
}
```

- [x] **Step 4: Run frontend model tests to verify they pass**

Run:

```bash
cd frontend && npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: PASS.

- [x] **Step 5: Commit frontend model**

Run:

```bash
git add frontend/src/smartWrongQuestions.ts frontend/src/smart-wrong-questions.test.ts
git commit -m "feat: add weekly activity summary frontend model"
```

---

### Task 4: Render Super Admin Panel

**Files:**
- Modify: `frontend/src/SmartWrongQuestionsPage.tsx`
- Modify: `frontend/src/smart-wrong-questions.test.ts`

- [x] **Step 1: Write failing page wiring tests**

Add these source wiring assertions to `frontend/src/smart-wrong-questions.test.ts`:

```typescript
test('SmartWrongQuestionsPage wires super owner weekly activity summary without strong ranking copy', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /本周数据总结/);
  assert.match(pageSource, /buildWeeklyWrongQuestionActivitySummaryPath/);
  assert.match(pageSource, /normalizeWeeklyWrongQuestionActivitySummaryResponse/);
  assert.match(pageSource, /currentUser\.role === 'super_owner'/);
  assert.match(pageSource, /本周活跃班级/);
  assert.match(pageSource, /本周活跃老师/);
  assert.match(pageSource, /本周活跃学生/);
  assert.doesNotMatch(pageSource, /第 1 名|榜首|冠军/);
});
```

- [x] **Step 2: Run page wiring tests to verify they fail**

Run:

```bash
cd frontend && npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: FAIL because `SmartWrongQuestionsPage.tsx` does not yet import the activity summary helpers or render `本周数据总结`.

- [x] **Step 3: Add imports and local types**

In `frontend/src/SmartWrongQuestionsPage.tsx`, add these imports from `./smartWrongQuestions`:

```typescript
  buildWeeklyWrongQuestionActivitySummaryPath,
  normalizeWeeklyWrongQuestionActivitySummaryResponse,
  type WeeklyWrongQuestionActivitySummary,
```

Add this type near the existing filter option types:

```typescript
type WrongQuestionOrganizationOption = {
  id: number;
  name: string;
};
```

- [x] **Step 4: Add state and loader**

Inside `SmartWrongQuestionsPage`, add state near the weekly followup state:

```typescript
  const canViewWeeklyActivitySummary = currentUser.role === 'super_owner';
  const [weeklyActivityOpen, setWeeklyActivityOpen] = useState(false);
  const [weeklyActivityWeekStart, setWeeklyActivityWeekStart] = useState(getCurrentMondayDateInputValue);
  const [weeklyActivityOrganizationId, setWeeklyActivityOrganizationId] = useState<number | null>(null);
  const [weeklyActivitySummary, setWeeklyActivitySummary] = useState<WeeklyWrongQuestionActivitySummary | null>(null);
  const [weeklyActivityLoading, setWeeklyActivityLoading] = useState(false);
  const [weeklyActivityError, setWeeklyActivityError] = useState('');
  const [weeklyActivityNotice, setWeeklyActivityNotice] = useState('');
  const [organizationOptions, setOrganizationOptions] = useState<WrongQuestionOrganizationOption[]>([]);
```

Add this effect near the existing option-loading effect:

```typescript
  useEffect(() => {
    if (!canViewWeeklyActivitySummary) {
      return;
    }
    let active = true;
    (async () => {
      try {
        const response = await apiFetch<{ items: Array<{ id: number; name: string }> }>('/api/admin/organizations');
        if (!active) {
          return;
        }
        setOrganizationOptions((response.items ?? []).map((item) => ({
          id: Number(item.id),
          name: String(item.name ?? ''),
        })).filter((item) => item.id > 0 && item.name.trim()));
      } catch (loadOrganizationsError) {
        console.error(loadOrganizationsError);
      }
    })();

    return () => {
      active = false;
    };
  }, [canViewWeeklyActivitySummary]);
```

Add this reset effect near the weekly followup reset effect:

```typescript
  useEffect(() => {
    setWeeklyActivitySummary(null);
    setWeeklyActivityNotice('');
    setWeeklyActivityError('');
  }, [weeklyActivityWeekStart, weeklyActivityOrganizationId]);
```

Add this loader near `handleLoadWeeklyFollowups`:

```typescript
  const handleLoadWeeklyActivitySummary = useCallback(async () => {
    if (!canViewWeeklyActivitySummary) {
      return;
    }
    setWeeklyActivityLoading(true);
    setWeeklyActivityError('');
    setWeeklyActivityNotice('');
    try {
      const response = await apiFetch<unknown>(
        buildWeeklyWrongQuestionActivitySummaryPath(weeklyActivityWeekStart, weeklyActivityOrganizationId),
      );
      const normalized = normalizeWeeklyWrongQuestionActivitySummaryResponse(response);
      setWeeklyActivitySummary(normalized);
      const totalRows = normalized.classItems.length + normalized.teacherItems.length + normalized.studentItems.length;
      setWeeklyActivityNotice(totalRows > 0 ? '本周活跃数据已更新。' : '本周暂无错题活跃数据。');
    } catch (loadActivityError) {
      setWeeklyActivityError(loadActivityError instanceof Error ? loadActivityError.message : '本周数据总结加载失败');
    } finally {
      setWeeklyActivityLoading(false);
    }
  }, [canViewWeeklyActivitySummary, weeklyActivityOrganizationId, weeklyActivityWeekStart]);
```

- [x] **Step 5: Render the button and panel**

Inside the action button group that currently renders `每周跟进`, add this button before `每周跟进`:

```tsx
            {canViewWeeklyActivitySummary && (
              <button
                type="button"
                onClick={() => setWeeklyActivityOpen((current) => !current)}
                className={workspaceSecondaryButtonClass}
              >
                本周数据总结
              </button>
            )}
```

Render this panel before the existing `weeklyFollowupOpen` panel:

```tsx
        {canViewWeeklyActivitySummary && weeklyActivityOpen && (
          <div className={`${workspaceSoftCardClass} space-y-4 p-4`}>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">超级管理员</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">本周数据总结</p>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">周次</span>
                  <input
                    aria-label="本周数据总结周次"
                    type="date"
                    value={weeklyActivityWeekStart}
                    onChange={(event) => setWeeklyActivityWeekStart(event.target.value)}
                    className={workspaceFieldClass}
                  />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">机构</span>
                  <select
                    aria-label="本周数据总结机构"
                    value={weeklyActivityOrganizationId ?? ''}
                    onChange={(event) => setWeeklyActivityOrganizationId(event.target.value ? Number(event.target.value) : null)}
                    className={workspaceFieldClass}
                  >
                    <option value="">全部机构</option>
                    {organizationOptions.map((item) => (
                      <option key={item.id} value={item.id}>{item.name}</option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() => void handleLoadWeeklyActivitySummary()}
                  disabled={weeklyActivityLoading}
                  className={workspacePrimaryButtonClass}
                >
                  {weeklyActivityLoading ? '正在加载' : '查看本周数据'}
                </button>
              </div>
            </div>

            {weeklyActivityError && (
              <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                <AlertCircle size={16} />
                {weeklyActivityError}
              </div>
            )}

            {weeklyActivityNotice && (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-300">
                {weeklyActivityNotice}
              </div>
            )}

            {weeklyActivitySummary && (
              <div className="grid gap-4 xl:grid-cols-3">
                <section className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-slate-950/60">
                  <h5 className="text-base font-semibold text-slate-900 dark:text-white">本周活跃班级</h5>
                  <div className="mt-3 space-y-3">
                    {weeklyActivitySummary.classItems.length > 0 ? weeklyActivitySummary.classItems.map((item) => (
                      <div key={item.classId} className="rounded-xl border border-slate-100 p-3 text-sm dark:border-white/10">
                        <p className="font-semibold text-slate-900 dark:text-white">{item.className}</p>
                        <p className="mt-1 text-slate-500 dark:text-slate-400">{item.weeklyQuestionCount} 道，{item.uploadingStudentCount} 名学生上传</p>
                        <p className="mt-1 text-xs text-slate-400">{item.organizationName}｜最近上传 {item.latestCreatedAt || '暂无'}</p>
                      </div>
                    )) : (
                      <p className="text-sm text-slate-500 dark:text-slate-400">本周暂无错题活跃数据</p>
                    )}
                  </div>
                </section>

                <section className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-slate-950/60">
                  <h5 className="text-base font-semibold text-slate-900 dark:text-white">本周活跃老师</h5>
                  <div className="mt-3 space-y-3">
                    {weeklyActivitySummary.teacherItems.length > 0 ? weeklyActivitySummary.teacherItems.map((item) => (
                      <div key={item.teacherUserId} className="rounded-xl border border-slate-100 p-3 text-sm dark:border-white/10">
                        <p className="font-semibold text-slate-900 dark:text-white">{item.teacherName}</p>
                        <p className="mt-1 text-slate-500 dark:text-slate-400">负责班级本周新增 {item.weeklyQuestionCount} 道，涉及 {item.involvedStudentCount} 名学生</p>
                        <p className="mt-1 text-xs text-slate-400">{item.organizationName}｜{item.classCount} 个班级，待跟进 {item.pendingFollowupCount} 条</p>
                      </div>
                    )) : (
                      <p className="text-sm text-slate-500 dark:text-slate-400">本周暂无错题活跃数据</p>
                    )}
                  </div>
                </section>

                <section className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-slate-950/60">
                  <h5 className="text-base font-semibold text-slate-900 dark:text-white">本周活跃学生</h5>
                  <div className="mt-3 space-y-3">
                    {weeklyActivitySummary.studentItems.length > 0 ? weeklyActivitySummary.studentItems.map((item) => (
                      <div key={item.studentId} className="rounded-xl border border-slate-100 p-3 text-sm dark:border-white/10">
                        <p className="font-semibold text-slate-900 dark:text-white">{item.studentName}｜{item.className}</p>
                        <p className="mt-1 text-slate-500 dark:text-slate-400">本周新增 {item.weeklyQuestionCount} 道，错题本共 {item.totalQuestionCount} 道</p>
                        <p className="mt-1 text-xs text-slate-400">{item.organizationName}｜主要专题：{item.topicCategories.join('、') || '未分类'}</p>
                      </div>
                    )) : (
                      <p className="text-sm text-slate-500 dark:text-slate-400">本周暂无错题活跃数据</p>
                    )}
                  </div>
                </section>
              </div>
            )}
          </div>
        )}
```

- [x] **Step 6: Run focused frontend tests**

Run:

```bash
cd frontend && npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: PASS.

- [x] **Step 7: Commit page UI**

Run:

```bash
git add frontend/src/SmartWrongQuestionsPage.tsx frontend/src/smart-wrong-questions.test.ts
git commit -m "feat: render weekly activity summary panel"
```

---

### Task 5: Final Verification And Handoff

**Files:**
- Modify: `handoff.md`

- [x] **Step 1: Run full focused proof through a temporary script**

Create and run this temporary script outside the repo:

```bash
tmp_script=/tmp/xingrun_weekly_activity_summary_proof.sh
cat > "$tmp_script" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /Users/xiaodi/Desktop/xingrun.web

echo "[1/6] backend activity summary tests"
python3 -m unittest tests.test_weekly_wrong_question_activity_summary -v

echo "[2/6] related weekly followup backend tests"
python3 -m unittest tests.test_weekly_wrong_question_followups -v

echo "[3/6] frontend smart wrong questions tests"
cd frontend
npx tsx --test src/smart-wrong-questions.test.ts

echo "[4/6] frontend full test suite"
npm test

echo "[5/6] frontend build"
npm run build

echo "[6/6] diff whitespace check"
cd ..
git diff --check

echo "proof passed"
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected: all six sections pass and the last line is `proof passed`.

- [x] **Step 2: Update handoff**

Add this bullet near the top of `handoff.md`:

```markdown
- 2026-05-05 已完成超级管理员“本周错题活跃数据总结”：新增 `GET /api/admin/wrong-question-activity-summary`，仅 `super_owner` 可访问；网页智能错题新增 `本周数据总结` 面板，可按周次和机构查看本周活跃班级、活跃老师、活跃学生，列表按数量从多到少自然列举，不显示强排名文案。proof `/tmp/xingrun_weekly_activity_summary_proof.sh` 已通过：后端活动汇总测试、每周跟进回归、前端智能错题测试、frontend full test、frontend build、`git diff --check`。
```

Replace the current next-step bullet about reviewing `2026-05-04-weekly-wrong-question-activity-summary-design.md` with:

```markdown
- 超级管理员本周错题活跃数据总结下一步建议用真实 `super_owner` 账号手工 smoke：打开网页智能错题，展开 `本周数据总结`，切换本周/上周和某个机构，确认班级、老师、学生三块列表的数量与后台数据一致，且页面没有“第 1 名”“榜首”等强排名口吻。
```

- [x] **Step 3: Re-run proof after handoff edit**

Run:

```bash
/tmp/xingrun_weekly_activity_summary_proof.sh
```

Expected: PASS.

- [x] **Step 4: Commit final handoff**

Run:

```bash
git add handoff.md
git commit -m "docs: update weekly activity summary handoff"
```

- [ ] **Step 5: Merge back to develop and clean branch**

Run:

```bash
git switch develop
git fetch origin
git rev-list --left-right --count develop...origin/develop
```

Expected: `0	0`. If the output is not `0	0`, stop and refresh `develop` before merging.

Run:

```bash
git merge --no-ff feature/weekly-wrong-question-activity-summary -m "Merge branch 'feature/weekly-wrong-question-activity-summary' into develop"
git branch -d feature/weekly-wrong-question-activity-summary
git push origin develop
git status --short --branch
```

Expected: `develop` is synchronized with `origin/develop`. Runtime-only untracked files may remain visible if they existed before the work; do not add them.

## Self-Review

- Spec coverage: Task 1 covers the three aggregation lists and sorting rules; Task 2 covers the `super_owner` API, week parsing, and organization filter; Task 3 covers frontend data normalization; Task 4 covers the web `智能错题` entry, week selector, organization selector, three read-only lists, empty state, and no strong ranking copy; Task 5 covers verification and handoff.
- Placeholder scan: The plan contains concrete files, commands, expected outputs, and code snippets for every implementation task.
- Type consistency: Backend snake_case response fields are normalized to frontend camelCase fields in Task 3 and consumed with those camelCase names in Task 4.
