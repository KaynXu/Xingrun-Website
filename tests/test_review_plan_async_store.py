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
        self.assertEqual(saved.get("pdf_path"), "/tmp/example.pdf")
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
