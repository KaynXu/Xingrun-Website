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
        self.owner = lesson_manager.get_user_by_username("Kayn")

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

    def test_create_pending_lesson_persists_review_generation_resume_context(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="",
            weak_points="斜率判断",
            class_id=self.class_id,
            record_status="transcribing",
            created_by_user_id=7,
            review_audio_path="/tmp/lesson.m4a",
            review_audio_request_key="audio-key",
            review_request_key="request-key",
            review_request_id="request-id",
            review_chat_provider="deepseek",
            review_chat_model="deepseek-v4-flash",
            review_same_lesson_materials=["补充材料"],
        )

        saved = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(saved["created_by_user_id"], 7)
        self.assertEqual(saved["review_audio_path"], "/tmp/lesson.m4a")
        self.assertEqual(saved["review_audio_request_key"], "audio-key")
        self.assertEqual(saved["review_request_key"], "request-key")
        self.assertEqual(saved["review_request_id"], "request-id")
        self.assertEqual(saved["review_chat_provider"], "deepseek")
        self.assertEqual(saved["review_chat_model"], "deepseek-v4-flash")
        self.assertEqual(saved["review_same_lesson_materials"], ["补充材料"])

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

    def test_requeue_lesson_generation_preserves_existing_output_until_new_result_ready(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="斜率判断",
            class_id=self.class_id,
            plan={"lesson_info": {"topic": "旧计划"}, "days": []},
            pdf_path="/tmp/old.pdf",
            record_status="failed",
        )
        lesson_manager.mark_lesson_generation_failed(lesson_id, "旧错误")

        lesson_manager.requeue_lesson_generation(
            lesson_id,
            record_status="generating",
            review_request_key="regen-key",
            review_request_id="regen-id",
            review_chat_provider="openai",
            review_chat_model="gpt-5.4",
        )

        saved = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(saved["record_status"], "generating")
        self.assertEqual(saved["generation_error"], "")
        self.assertEqual(saved["pdf_path"], "/tmp/old.pdf")
        self.assertEqual(saved["plan"]["lesson_info"]["topic"], "旧计划")
        self.assertEqual(saved["review_request_key"], "regen-key")
        self.assertEqual(saved["review_request_id"], "regen-id")
        self.assertEqual(saved["review_chat_provider"], "openai")
        self.assertEqual(saved["review_chat_model"], "gpt-5.4")

    def test_mark_lesson_generation_succeeded_missing_raises(self):
        with self.assertRaisesRegex(LookupError, "lesson not found"):
            lesson_manager.mark_lesson_generation_succeeded(
                lesson_id=999999,
                plan={"dummy": "data"},
                pdf_path="/tmp/placeholder.pdf",
            )

    def test_mark_lesson_generation_failed_missing_raises(self):
        with self.assertRaisesRegex(LookupError, "lesson not found"):
            lesson_manager.mark_lesson_generation_failed(
                lesson_id=999999,
                error_message="failure",
            )

    def test_requeue_lesson_generation_missing_raises(self):
        with self.assertRaisesRegex(LookupError, "lesson not found"):
            lesson_manager.requeue_lesson_generation(999999)

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

    def test_mark_monthly_plan_job_succeeded_missing_raises(self):
        with self.assertRaisesRegex(LookupError, "monthly plan job not found"):
            lesson_manager.mark_monthly_plan_job_succeeded(
                job_id=999999,
                pdf_filename="ghost.pdf",
            )

    def test_mark_monthly_plan_job_failed_missing_raises(self):
        with self.assertRaisesRegex(LookupError, "monthly plan job not found"):
            lesson_manager.mark_monthly_plan_job_failed(
                job_id=999999,
                error_message="failure",
            )

    def test_create_monthly_plan_job_rejects_cross_organization_user(self):
        with lesson_manager.get_conn() as conn:
            other_org = lesson_manager._ensure_organization(conn, "第二机构")

        with self.assertRaisesRegex(ValueError, "does not belong to organization"):
            lesson_manager.create_monthly_plan_job(
                organization_id=other_org["id"],
                user_id=self.owner["id"],
                month_str="2026-04",
            )

    def test_delete_user_for_actor_removes_monthly_jobs(self):
        with lesson_manager.get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
                VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (
                    "member_async",
                    lesson_manager.hash_password("password123"),
                    "异步成员",
                    "member",
                    self.owner["organization_id"],
                ),
            )
            member_id = cur.lastrowid

        job = lesson_manager.create_monthly_plan_job(
            organization_id=self.owner["organization_id"],
            user_id=member_id,
            month_str="2026-04",
        )

        lesson_manager.delete_user_for_actor(self.owner, member_id)

        self.assertIsNone(lesson_manager.get_monthly_plan_job(job["id"]))

    def test_delete_organization_removes_monthly_jobs(self):
        with lesson_manager.get_conn() as conn:
            org = lesson_manager._ensure_organization(conn, "待删机构")
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
                VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (
                    "org_owner_async",
                    lesson_manager.hash_password("password123"),
                    "机构老师",
                    "owner",
                    org["id"],
                ),
            )
            user_id = cur.lastrowid

        job = lesson_manager.create_monthly_plan_job(
            organization_id=org["id"],
            user_id=user_id,
            month_str="2026-04",
        )

        lesson_manager.delete_organization(org["id"])

        self.assertIsNone(lesson_manager.get_monthly_plan_job(job["id"]))
