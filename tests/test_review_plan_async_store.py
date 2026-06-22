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
        self.assertTrue(pending["has_version_generating"])

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
        self.assertFalse(saved["has_version_generating"])

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

    def test_fail_review_plan_version_records_error_without_current_pointer(self):
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
        )

        lesson_manager.fail_review_plan_version(version["id"], "AI 生成失败，请稍后重试")

        saved_version = lesson_manager.get_review_plan_version(version["id"])
        saved_lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(saved_version["status"], "failed")
        self.assertEqual(saved_version["generation_error"], "AI 生成失败，请稍后重试")
        self.assertIsNone(saved_lesson["current_review_plan_version_id"])
        self.assertFalse(saved_lesson["has_version_generating"])

    def test_new_generation_version_preserves_existing_current_until_ready(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="斜率判断",
            class_id=self.class_id,
        )
        first = lesson_manager.create_review_plan_version(
            lesson_id=lesson_id,
            status="generating",
            request_key="request-1",
            request_id="request-id-1",
        )
        lesson_manager.complete_review_plan_version(
            first["id"],
            plan={"lesson_info": {"topic": "旧计划"}, "days": []},
            pdf_path="/tmp/old.pdf",
        )

        second = lesson_manager.create_review_plan_version(
            lesson_id=lesson_id,
            status="generating",
            request_key="request-2",
            request_id="request-id-2",
        )

        saved = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(saved["current_review_plan_version_id"], first["id"])
        self.assertEqual(saved["current_version"]["id"], first["id"])
        self.assertEqual(saved["pdf_path"], "/tmp/old.pdf")
        self.assertTrue(saved["has_version_generating"])

        lesson_manager.complete_review_plan_version(
            second["id"],
            plan={"lesson_info": {"topic": "新计划"}, "days": []},
            pdf_path="/tmp/new.pdf",
        )

        updated = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(updated["current_review_plan_version_id"], second["id"])
        self.assertEqual(updated["current_version"]["id"], second["id"])
        self.assertEqual(updated["pdf_path"], "/tmp/new.pdf")
        self.assertFalse(updated["has_version_generating"])

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

    def test_set_current_review_plan_version_missing_version_raises(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="斜率判断",
            class_id=self.class_id,
        )

        with self.assertRaisesRegex(LookupError, "review plan version not found"):
            lesson_manager.set_current_review_plan_version(lesson_id, 999999)

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
