import sys
import tempfile
import unittest
import importlib
import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager


class ClassFeedbackApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        app_module = importlib.import_module("app")
        self.client = app_module.app.test_client()

        login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(login.status_code, 200)
        payload = login.get_json()
        self.assertIsNotNone(payload)
        self.owner = payload["user"]
        self.owner_token = payload["token"]
        self.headers = {"X-Auth-Token": self.owner_token}

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_lesson(self, *, class_id: int, date_str: str, topic: str, summary: str) -> int:
        return lesson_manager.save_lesson(
            date_str=date_str,
            subject="英语",
            grade="六年级",
            topic=topic,
            summary=summary,
            weak_points="",
            plan={"lesson_info": {"topic": topic}, "questions": []},
            pdf_path="",
            class_id=class_id,
        )

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
        self.assertIsNotNone(payload)
        self.assertIsNone(payload["teacher_user_id"])
        self.assertEqual(payload["teacher_name_snapshot"], self.owner["display_name"])
        self.assertEqual(payload["period_granularity"], "daily")

    def test_create_task_accepts_weekly_structured_period_payload(self):
        class_id = lesson_manager.save_class("假期冲刺班", subject="英语", grade="六年级")
        lesson_manager.create_student_for_class(class_id, "张三")

        response = self.client.post(
            "/api/class-feedback/tasks",
            headers=self.headers,
            json={
                "class_id": class_id,
                "period_granularity": "weekly",
                "year": 2026,
                "week": 15,
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["period_granularity"], "weekly")
        self.assertEqual(payload["period_label"], lesson_manager.week_label("2026-W15"))
        self.assertEqual(payload["start_date"], "2026-04-06")
        self.assertEqual(payload["end_date"], "2026-04-12")

    def test_create_task_rejects_invalid_stage_name_in_structured_payload(self):
        class_id = lesson_manager.save_class("假期冲刺班", subject="英语", grade="六年级")
        lesson_manager.create_student_for_class(class_id, "张三")

        response = self.client.post(
            "/api/class-feedback/tasks",
            headers=self.headers,
            json={
                "class_id": class_id,
                "period_granularity": "stage",
                "year": 2026,
                "stage_name": "春学期",
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertIn("stage_name", payload["error"])

    def test_create_task_keeps_legacy_date_range_payload_compatible(self):
        class_id = lesson_manager.save_class("假期冲刺班", subject="英语", grade="六年级")
        lesson_manager.create_student_for_class(class_id, "张三")

        response = self.client.post(
            "/api/class-feedback/tasks",
            headers=self.headers,
            json={"class_id": class_id, "start_date": "2026-07-12", "end_date": "2026-07-12"},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["period_label"], "2026-07-12")

    @patch("app.generate_class_feedback_bundle")
    def test_generate_route_returns_class_summary_and_student_entries(self, generate_class_feedback_bundle):
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        student = lesson_manager.create_student_for_class(class_id, "张三")
        older_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=None,
            teacher_name_snapshot=self.owner["display_name"],
            start_date="2026-03-20",
            end_date="2026-03-26",
            created_by=self.owner["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            older_task["id"],
            class_summary_ai_draft="更早阶段草稿",
            student_entries=[{"student_id": student["id"], "name": "张三", "ai_draft": "更早阶段学生草稿"}],
        )
        lesson_manager.confirm_class_feedback_task(
            older_task["id"],
            class_summary_final_text="更早阶段正式班级反馈",
            student_entries=[
                {
                    "student_id": student["id"],
                    "final_text": "张三更早阶段反馈。",
                    "checked_at": "2026-03-26 20:00:00",
                }
            ],
        )
        previous_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=None,
            teacher_name_snapshot=self.owner["display_name"],
            start_date="2026-03-27",
            end_date="2026-04-02",
            created_by=self.owner["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            previous_task["id"],
            class_summary_ai_draft="上阶段草稿",
            student_entries=[{"student_id": student["id"], "name": "张三", "ai_draft": "上阶段学生草稿"}],
        )
        lesson_manager.confirm_class_feedback_task(
            previous_task["id"],
            class_summary_final_text="上阶段正式班级反馈",
            student_entries=[
                {
                    "student_id": student["id"],
                    "final_text": "张三上阶段表达更稳定。",
                    "checked_at": "2026-04-02 20:00:00",
                }
            ],
        )

        self._create_lesson(
            class_id=class_id,
            date_str="2026-04-05",
            topic="Week 1",
            summary="本周围绕阅读表达和句型迁移做训练。",
        )

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
                "class_status_note": "班级进入状态快，互动稳定。",
                "parent_feedback_note": "家长反馈在家愿意跟读。",
                "teaching_focus_note": "继续强化句型迁移。",
                "next_stage_preview_note": "下阶段加入长句表达。",
                "student_highlights": [
                    {"student_id": student["id"], "labels": ["进步明显"], "note": "主动表达增加"}
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["class_summary_ai_draft"], "本阶段班级整体状态稳定。")
        self.assertEqual(len(payload["student_entries"]), 1)
        self.assertEqual(payload["student_entries"][0]["ai_draft"], "张三这阶段开口更主动了。")

        generate_class_feedback_bundle.assert_called_once()
        context = generate_class_feedback_bundle.call_args.kwargs
        self.assertEqual(context["class_name"], "S01A1")
        self.assertEqual(context["teacher_name"], self.owner["display_name"])
        self.assertEqual(context["start_date"], "2026-04-03")
        self.assertEqual(context["end_date"], "2026-04-09")
        self.assertEqual(context["stage_notes"]["class_status_tags"], ["进入状态快"])
        self.assertEqual(context["stage_notes"]["class_status_note"], "班级进入状态快，互动稳定。")
        self.assertNotIn("lesson_feedbacks", context["stage_notes"])
        source_summary = json.loads(context["source_summary"])
        self.assertNotIn("lesson_feedbacks", source_summary)
        self.assertEqual(
            [item["class_summary_final_text"] for item in context["stage_notes"]["recent_confirmed_class_summaries"]],
            ["上阶段正式班级反馈", "更早阶段正式班级反馈"],
        )
        self.assertEqual(context["students"][0]["previous_baseline"]["final_text"], "张三上阶段表达更稳定。")
        self.assertEqual(context["students"][0]["stage_highlight"]["labels"], ["进步明显"])

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
                "student_entries": [
                    {
                        "student_id": student["id"],
                        "final_text": "正式学生反馈",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        reopened = self.client.get(f"/api/class-feedback/tasks/{task['id']}", headers=self.headers)
        self.assertEqual(reopened.status_code, 200)
        reopened_payload = reopened.get_json()
        self.assertIsNotNone(reopened_payload)
        self.assertEqual(reopened_payload["status"], "confirmed")
        self.assertRegex(
            reopened_payload["student_entries"][0]["checked_at"],
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$",
        )
        baseline = lesson_manager.find_previous_confirmed_class_feedback_entry(
            class_id=class_id,
            student_id=student["id"],
            period_granularity="weekly",
            before_end_date="2026-04-10",
        )
        self.assertIsNotNone(baseline)
        self.assertEqual(baseline["final_text"], "正式学生反馈")

    @patch("app.generate_class_feedback_bundle")
    def test_generate_rejects_confirmed_task_and_preserves_confirmed_content(self, generate_class_feedback_bundle):
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        student = lesson_manager.create_student_for_class(class_id, "张三")
        lesson_manager.save_lesson(
            date_str="2026-04-05",
            subject="英语",
            grade="六年级",
            topic="Week 1",
            summary="已有课堂记录。",
            weak_points="",
            plan={"lesson_info": {"topic": "Week 1"}, "questions": []},
            pdf_path="",
            class_id=class_id,
        )
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
        lesson_manager.confirm_class_feedback_task(
            task["id"],
            class_summary_final_text="正式班级反馈",
            student_entries=[
                {
                    "student_id": student["id"],
                    "final_text": "正式学生反馈",
                    "checked_at": "2026-04-09 20:00:00",
                }
            ],
        )

        response = self.client.post(
            f"/api/class-feedback/tasks/{task['id']}/generate",
            headers=self.headers,
            json={},
        )

        self.assertEqual(response.status_code, 409)
        generate_class_feedback_bundle.assert_not_called()
        refreshed = lesson_manager.get_class_feedback_task(task["id"])
        self.assertEqual(refreshed["status"], "confirmed")
        self.assertEqual(refreshed["class_summary_final_text"], "正式班级反馈")
        self.assertEqual(refreshed["student_entries"][0]["final_text"], "正式学生反馈")

    @patch("app.generate_class_feedback_bundle")
    def test_generate_rejects_ai_bundle_missing_roster_student(self, generate_class_feedback_bundle):
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        first_student = lesson_manager.create_student_for_class(class_id, "张三")
        second_student = lesson_manager.create_student_for_class(class_id, "李四")
        self._create_lesson(
            class_id=class_id,
            date_str="2026-04-05",
            topic="Week 1",
            summary="本周围绕阅读表达和句型迁移做训练。",
        )
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
                {"student_id": first_student["id"], "name": "张三", "text": "张三这阶段开口更主动了。"}
            ],
        }

        response = self.client.post(
            f"/api/class-feedback/tasks/{task['id']}/generate",
            headers=self.headers,
            json={},
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertIn("roster", payload["error"])
        refreshed = lesson_manager.get_class_feedback_task(task["id"])
        self.assertEqual(refreshed["class_summary_ai_draft"], "")
        self.assertEqual(refreshed["student_entries"], [])
        self.assertNotEqual(second_student["id"], first_student["id"])

    @patch("app.generate_class_feedback_bundle")
    def test_generate_rejects_empty_source_range_without_calling_ai(self, generate_class_feedback_bundle):
        class_id = lesson_manager.save_class("假期冲刺班", subject="英语", grade="六年级")
        lesson_manager.create_student_for_class(class_id, "张三")
        task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=None,
            teacher_name_snapshot=self.owner["display_name"],
            start_date="2026-07-12",
            end_date="2026-07-12",
            created_by=self.owner["id"],
        )

        response = self.client.post(
            f"/api/class-feedback/tasks/{task['id']}/generate",
            headers=self.headers,
            json={},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "所选时间范围内没有可用课次记录")
        generate_class_feedback_bundle.assert_not_called()

    @patch("app.generate_class_feedback_bundle")
    def test_generate_rejects_empty_roster_without_calling_ai(self, generate_class_feedback_bundle):
        class_id = lesson_manager.save_class("空班", subject="英语", grade="六年级")
        self._create_lesson(
            class_id=class_id,
            date_str="2026-04-05",
            topic="Week 1",
            summary="本周围绕阅读表达和句型迁移做训练。",
        )
        task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=None,
            teacher_name_snapshot=self.owner["display_name"],
            start_date="2026-04-03",
            end_date="2026-04-09",
            created_by=self.owner["id"],
        )

        response = self.client.post(
            f"/api/class-feedback/tasks/{task['id']}/generate",
            headers=self.headers,
            json={},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "当前班级还没有学生，无法生成课堂反馈")
        generate_class_feedback_bundle.assert_not_called()

    @patch("app.generate_class_feedback_bundle")
    def test_generate_round_trips_notes_and_highlights_via_get_task(self, generate_class_feedback_bundle):
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        student = lesson_manager.create_student_for_class(class_id, "张三")
        self._create_lesson(
            class_id=class_id,
            date_str="2026-04-05",
            topic="Week 1",
            summary="本周围绕阅读表达和句型迁移做训练。",
        )
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
        request_payload = {
            "class_status_tags": ["进入状态快", "开口更主动"],
            "class_status_note": "整体进入状态快。",
            "parent_feedback_note": "家长反馈打卡稳定。",
            "teaching_focus_note": "强化句型迁移。",
            "next_stage_preview_note": "加入长句表达。",
            "student_highlights": [
                {"student_id": student["id"], "labels": ["进步明显"], "note": "主动表达增加"}
            ],
        }

        response = self.client.post(
            f"/api/class-feedback/tasks/{task['id']}/generate",
            headers=self.headers,
            json=request_payload,
        )

        self.assertEqual(response.status_code, 200)
        reopened = self.client.get(f"/api/class-feedback/tasks/{task['id']}", headers=self.headers)
        self.assertEqual(reopened.status_code, 200)
        payload = reopened.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["class_status_tags"], ["进入状态快", "开口更主动"])
        self.assertEqual(payload["class_status_note"], "整体进入状态快。")
        self.assertEqual(payload["parent_feedback_note"], "家长反馈打卡稳定。")
        self.assertEqual(payload["teaching_focus_note"], "强化句型迁移。")
        self.assertEqual(payload["next_stage_preview_note"], "加入长句表达。")
        self.assertEqual(
            payload["student_highlights"],
            [{"student_id": student["id"], "labels": ["进步明显"], "note": "主动表达增加"}],
        )

    def test_draft_save_route_round_trips_class_summary_and_student_feedback_edits(self):
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        first_student = lesson_manager.create_student_for_class(class_id, "张三")
        second_student = lesson_manager.create_student_for_class(class_id, "李四")
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
            class_summary_ai_draft="AI 班级草稿",
            student_entries=[
                {"student_id": first_student["id"], "name": "张三", "ai_draft": "张三AI草稿"},
                {"student_id": second_student["id"], "name": "李四", "ai_draft": "李四AI草稿"},
            ],
        )

        response = self.client.post(
            f"/api/class-feedback/tasks/{task['id']}/draft",
            headers=self.headers,
            json={
                "class_summary_draft_text": "老师修改后的班级草稿",
                "student_entries": [
                    {"student_id": first_student["id"], "final_text": "张三修改稿"},
                    {"student_id": second_student["id"], "final_text": "李四修改稿"},
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        reopened = self.client.get(f"/api/class-feedback/tasks/{task['id']}", headers=self.headers)
        self.assertEqual(reopened.status_code, 200)
        payload = reopened.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["status"], "draft")
        self.assertEqual(payload["class_summary_ai_draft"], "老师修改后的班级草稿")
        self.assertEqual(payload["student_entries"][0]["final_text"], "张三修改稿")
        self.assertEqual(payload["student_entries"][1]["final_text"], "李四修改稿")
        self.assertIsNone(payload["student_entries"][0]["checked_at"])

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
        self.assertEqual(reloaded.status_code, 200)
        payload = reloaded.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["groups"][-1]["group"], "老师自定义")
        self.assertEqual(payload["groups"][-1]["labels"], ["假期每日打卡稳定"])


if __name__ == "__main__":
    unittest.main()
