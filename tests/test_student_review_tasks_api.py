import gc
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module
import config_runtime
import lesson_manager
from app import app


class StudentReviewTasksApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app.test_client()
        self.owner_payload = self._login_as_owner()

    def tearDown(self):
        app_module._AI_REQUEST_IN_FLIGHT.clear()
        app_module._AI_ORGANIZATION_IN_FLIGHT.clear()
        gc.collect()
        self.temp_dir.cleanup()

    def _login_as_owner(self) -> dict:
        login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(login.status_code, 200)
        payload = login.get_json()
        self.assertIsNotNone(payload)
        return payload

    def _create_student_with_review_plan(self, *, class_name="华老师小课", student_name="袁玲轩"):
        class_id = lesson_manager.save_class(class_name, subject="数学", grade="初中")
        student = lesson_manager.create_student_for_class(class_id, student_name)
        invite = lesson_manager.get_or_create_active_class_invite(class_id, self.owner_payload["user"]["id"])
        pdf_path = self.base / f"student-review-{student['id']}.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n% student review proof\n")
        plan = {
            "lesson_info": {"subject": "数学", "topic": "二次函数最值"},
            "days": [
                {
                    "day": 1,
                    "label": "课后第1天复习 (2026-06-03)",
                    "time": "10-20分钟",
                    "steps": [
                        {"title": "复习目标: 回忆二次函数最值问题的整体框架"},
                        {"title": "完成填空主任务"},
                    ],
                },
                {
                    "day": 2,
                    "label": "课后第2天复习 (2026-06-04)",
                    "time": "10-20分钟",
                    "pdf_page": 8,
                    "steps": [{"title": "巩固表示线段的具体方法"}],
                },
            ],
        }
        lesson_id = lesson_manager.save_lesson(
            date_str="2026-06-02",
            subject="数学",
            grade="初中",
            topic="二次函数最值",
            summary="课堂总结",
            weak_points="表示线段",
            plan=plan,
            pdf_path=str(pdf_path),
            class_id=class_id,
        )
        return {
            "class_id": class_id,
            "student": student,
            "invite": invite,
            "lesson_id": lesson_id,
        }

    def _register_student(self, fixture: dict, *, username="yuanlx", password="student123") -> dict:
        response = self.client.post(
            "/api/student/register",
            json={
                "invite_code": fixture["invite"]["invite_code"],
                "student_id": fixture["student"]["id"],
                "username": username,
                "password": password,
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertIn("token", payload)
        return payload

    def test_student_can_preview_invite_register_login_and_load_profile(self):
        fixture = self._create_student_with_review_plan()

        preview = self.client.get(f"/api/student/class-invite/{fixture['invite']['invite_code']}")
        self.assertEqual(preview.status_code, 200)
        preview_payload = preview.get_json()
        self.assertIsNotNone(preview_payload)
        self.assertEqual(preview_payload["class"]["name"], "华老师小课")
        self.assertEqual(preview_payload["students"][0]["name"], "袁玲轩")

        registered = self._register_student(fixture)
        self.assertEqual(registered["account"]["username"], "yuanlx")
        self.assertEqual(registered["account"]["student"]["name"], "袁玲轩")
        self.assertIn("华老师小课", registered["account"]["student"]["class_names"])

        me = self.client.get(
            "/api/student/me",
            headers={"X-Student-Auth-Token": registered["token"]},
        )
        self.assertEqual(me.status_code, 200)
        me_payload = me.get_json()
        self.assertIsNotNone(me_payload)
        self.assertEqual(me_payload["account"]["student"]["id"], fixture["student"]["id"])

        login = self.client.post(
            "/api/student/login",
            json={"username": "yuanlx", "password": "student123"},
        )
        self.assertEqual(login.status_code, 200)
        login_payload = login.get_json()
        self.assertIsNotNone(login_payload)
        self.assertEqual(login_payload["account"]["student"]["name"], "袁玲轩")
        self.assertIn("token", login_payload)

        duplicate = self.client.post(
            "/api/student/register",
            json={
                "invite_code": fixture["invite"]["invite_code"],
                "student_id": fixture["student"]["id"],
                "username": "yuan-other",
                "password": "student123",
            },
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_student_review_tasks_use_bound_student_and_student_pdf_routes(self):
        fixture = self._create_student_with_review_plan()
        other_fixture = self._create_student_with_review_plan(class_name="别的班", student_name="别的学生")
        registered = self._register_student(fixture)

        response = self.client.get(
            "/api/student/review-tasks?date=2026-06-03",
            headers={"X-Student-Auth-Token": registered["token"]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["date"], "2026-06-03")
        self.assertEqual(payload["student"]["name"], "袁玲轩")
        self.assertEqual(len(payload["tasks"]), 1)
        task = payload["tasks"][0]
        self.assertEqual(task["lesson_id"], fixture["lesson_id"])
        self.assertNotEqual(task["lesson_id"], other_fixture["lesson_id"])
        self.assertEqual(task["pdf_url"], f"/api/student/pdf/{fixture['lesson_id']}")
        self.assertEqual(task["pdf_download_url"], f"/api/student/pdf/download/{fixture['lesson_id']}")
        self.assertTrue(task["pdf_available"])
        self.assertEqual(task["pdf_page"], 2)
        self.assertTrue(task["pdf_page_estimated"])
        self.assertEqual(task["steps"][0], "复习目标: 回忆二次函数最值问题的整体框架")

    def test_student_review_tasks_use_explicit_pdf_page_when_plan_has_one(self):
        fixture = self._create_student_with_review_plan()
        registered = self._register_student(fixture)

        response = self.client.get(
            "/api/student/review-tasks?date=2026-06-04",
            headers={"X-Student-Auth-Token": registered["token"]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["tasks"]), 1)
        task = payload["tasks"][0]
        self.assertEqual(task["pdf_page"], 8)
        self.assertFalse(task["pdf_page_estimated"])

    def test_student_pdf_requires_bound_student_scope(self):
        fixture = self._create_student_with_review_plan()
        other_fixture = self._create_student_with_review_plan(class_name="别的班", student_name="别的学生")
        registered = self._register_student(fixture)

        own_pdf = self.client.get(f"/api/student/pdf/{fixture['lesson_id']}?token={registered['token']}")
        self.assertEqual(own_pdf.status_code, 200)
        own_pdf.close()

        other_pdf = self.client.get(f"/api/student/pdf/{other_fixture['lesson_id']}?token={registered['token']}")
        self.assertEqual(other_pdf.status_code, 404)
        other_pdf.close()

    def test_student_register_rejects_student_outside_invite_class(self):
        fixture = self._create_student_with_review_plan()
        other_fixture = self._create_student_with_review_plan(class_name="别的班", student_name="别的学生")

        response = self.client.post(
            "/api/student/register",
            json={
                "invite_code": fixture["invite"]["invite_code"],
                "student_id": other_fixture["student"]["id"],
                "username": "wrong-student",
                "password": "student123",
            },
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
