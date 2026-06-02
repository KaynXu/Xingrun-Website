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
        self.owner_token = self._login_as_owner()
        self.headers = {"X-Auth-Token": self.owner_token}

    def tearDown(self):
        app_module._AI_REQUEST_IN_FLIGHT.clear()
        app_module._AI_ORGANIZATION_IN_FLIGHT.clear()
        gc.collect()
        self.temp_dir.cleanup()

    def _login_as_owner(self) -> str:
        login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(login.status_code, 200)
        payload = login.get_json()
        self.assertIsNotNone(payload)
        return payload["token"]

    def _create_student_with_review_plan(self):
        class_id = lesson_manager.save_class("华老师小课", subject="数学", grade="初中")
        student = lesson_manager.create_student_for_class(class_id, "袁玲轩")
        pdf_path = self.base / "student-review.pdf"
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
        return student, lesson_id

    def test_student_review_tasks_returns_only_requested_date_with_pdf_metadata(self):
        student, lesson_id = self._create_student_with_review_plan()

        response = self.client.get(
            f"/api/student-review-tasks?student_id={student['id']}&date=2026-06-03",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["date"], "2026-06-03")
        self.assertEqual(payload["student"]["name"], "袁玲轩")
        self.assertEqual(len(payload["tasks"]), 1)
        task = payload["tasks"][0]
        self.assertEqual(task["lesson_id"], lesson_id)
        self.assertEqual(task["lesson_topic"], "二次函数最值")
        self.assertEqual(task["pdf_url"], f"/api/pdf/{lesson_id}")
        self.assertEqual(task["pdf_download_url"], f"/api/pdf/download/{lesson_id}")
        self.assertTrue(task["pdf_available"])
        self.assertEqual(task["pdf_page"], 2)
        self.assertTrue(task["pdf_page_estimated"])
        self.assertEqual(task["steps"][0], "复习目标: 回忆二次函数最值问题的整体框架")

    def test_student_review_tasks_uses_explicit_pdf_page_when_plan_has_one(self):
        student, _lesson_id = self._create_student_with_review_plan()

        response = self.client.get(
            f"/api/student-review-tasks?student_id={student['id']}&date=2026-06-04",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["tasks"]), 1)
        task = payload["tasks"][0]
        self.assertEqual(task["pdf_page"], 8)
        self.assertFalse(task["pdf_page_estimated"])

    def test_student_review_task_students_lists_accessible_students(self):
        student, _lesson_id = self._create_student_with_review_plan()

        response = self.client.get("/api/student-review-tasks/students", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["items"][0]["id"], student["id"])
        self.assertEqual(payload["items"][0]["name"], "袁玲轩")
        self.assertIn("华老师小课", payload["items"][0]["class_names"])


if __name__ == "__main__":
    unittest.main()
