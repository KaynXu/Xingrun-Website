from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager
import app as app_module
from app import app


class WeChatParentReasonFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        lesson_manager.init_db()
        self.organization_id = 1
        self.owner_id = 1
        self.class_id = lesson_manager.save_class(
            "六年级 1 班",
            subject="数学",
            grade="六年级",
            organization_id=self.organization_id,
        )
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner_id)
        self.student = lesson_manager.create_student_for_class(self.class_id, "Alice")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_set_wechat_wrong_question_archive_status_round_trips_archived_and_active(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        submission = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/wrong-question.png",
        )

        archived = lesson_manager.set_wechat_wrong_question_archive_status(
            submission["id"],
            "archived",
        )

        self.assertEqual(archived["id"], submission["id"])
        self.assertEqual(archived["archive_status"], "archived")
        self.assertTrue(archived["archived_at"])
        archived_at = archived["archived_at"]

        reactivated = lesson_manager.set_wechat_wrong_question_archive_status(
            submission["id"],
            "active",
        )

        self.assertEqual(reactivated["id"], submission["id"])
        self.assertEqual(reactivated["archive_status"], "active")
        self.assertEqual(reactivated["archived_at"], "")
        self.assertTrue(archived_at)


class WeChatParentArchiveApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        self.original_pdf_dir = app_module.PDF_DIR
        app_module.PDF_DIR = self.base / "pdfs"
        app_module.PDF_DIR.mkdir(parents=True, exist_ok=True)
        lesson_manager.init_db()
        self.client = app.test_client()
        self.owner_payload = self.login_owner()
        self.class_id = lesson_manager.save_class(
            "六年级 1 班",
            subject="数学",
            grade="六年级",
            organization_id=self.owner_payload["user"]["organization_id"],
        )
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner_payload["user"]["id"])
        self.student = lesson_manager.create_student_for_class(self.class_id, "Alice")
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        self.binding_id = binding["id"]
        submission = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/wrong-question.png",
            child_raw_reason_text="孩子说是计算粗心",
            primary_error_type="计算问题",
            secondary_error_summary="抄错了符号",
        )
        self.record_id = submission["id"]

    def tearDown(self):
        app_module.PDF_DIR = self.original_pdf_dir
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def login_owner(self) -> dict:
        response = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        return payload

    def test_staff_can_archive_wechat_wrong_question(self):
        archive = self.client.put(
            f"/api/wrong-questions/{self.record_id}/archive",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"archive_status": "archived"},
        )

        self.assertEqual(archive.status_code, 200)
        payload = archive.get_json()
        self.assertIsNotNone(payload)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["record"]["id"], self.record_id)
        self.assertEqual(payload["record"]["archive_status"], "archived")
        self.assertTrue(payload["record"]["archived_at"])

    def test_non_staff_cannot_archive_wechat_wrong_question(self):
        with lesson_manager.get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
                VALUES (?, ?, ?, 'member', 'active', ?)
                """,
                ("member_archive", "hash", "Member Archive", self.owner_payload["user"]["organization_id"]),
            )
            member_id = cur.lastrowid
        member_token = lesson_manager.create_auth_session(member_id)

        archive = self.client.put(
            f"/api/wrong-questions/{self.record_id}/archive",
            headers=self.auth_headers(member_token),
            json={"archive_status": "archived"},
        )

        self.assertEqual(archive.status_code, 403)

    def test_staff_gets_404_when_archiving_missing_local_record(self):
        archive = self.client.put(
            "/api/wrong-questions/wechat-missing-record/archive",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"archive_status": "archived"},
        )

        self.assertEqual(archive.status_code, 404)

    def test_visible_user_can_delete_local_wrong_question_and_rebuild_pdf(self):
        library_dir = app_module.PDF_DIR / "wrong_question_libraries"
        library_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = library_dir / f"student-{self.student['id']}.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nold pdf\n")

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE wrong_question_submissions
                SET recognition_status='recognized',
                    question_text='第一题',
                    question_text_source='ai',
                    student_library_pdf_path=?
                WHERE id=?
                """,
                (str(pdf_path), self.record_id),
            )

        second = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=self.binding_id,
            image_url="https://files.example.com/wrong-question-2.png",
            child_raw_reason_text="第二题",
            primary_error_type="计算问题",
            secondary_error_summary="第二题备注",
            recognition_status="recognized",
            question_text="第二题题干",
            question_text_source="ai",
            student_library_pdf_path=str(pdf_path),
        )

        with patch("app._rebuild_student_wrong_question_library", return_value=str(pdf_path)) as rebuild:
            response = self.client.delete(
                f"/api/wrong-questions/{self.record_id}",
                headers=self.auth_headers(self.owner_payload["token"]),
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["deleted_record_id"], self.record_id)
        self.assertEqual(payload["student_id"], self.student["id"])
        self.assertEqual(payload["next_student_library_pdf_path"], str(pdf_path))
        self.assertIsNone(lesson_manager.get_wechat_wrong_question_submission(self.record_id))
        remaining = lesson_manager.get_wechat_wrong_question_submission(second["id"])
        self.assertIsNotNone(remaining)
        self.assertEqual(remaining["student_library_pdf_path"], str(pdf_path))
        rebuild.assert_called_once_with(self.student["id"])

    def test_delete_last_local_wrong_question_removes_pdf_without_rebuild(self):
        library_dir = app_module.PDF_DIR / "wrong_question_libraries"
        library_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = library_dir / f"student-{self.student['id']}.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nold pdf\n")

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE wrong_question_submissions
                SET recognition_status='recognized',
                    question_text='最后一题',
                    question_text_source='ai',
                    student_library_pdf_path=?
                WHERE id=?
                """,
                (str(pdf_path), self.record_id),
            )

        with patch("app._rebuild_student_wrong_question_library") as rebuild:
            response = self.client.delete(
                f"/api/wrong-questions/{self.record_id}",
                headers=self.auth_headers(self.owner_payload["token"]),
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["next_student_library_pdf_path"], "")
        self.assertFalse(pdf_path.exists())
        self.assertIsNone(lesson_manager.get_wechat_wrong_question_submission(self.record_id))
        rebuild.assert_not_called()

    def test_student_library_pdf_endpoint_rebuilds_before_serving_cached_file(self):
        library_dir = app_module.PDF_DIR / "wrong_question_libraries"
        library_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = library_dir / f"student-{self.student['id']}.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nold pdf\n")

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE wrong_question_submissions
                SET recognition_status='recognized',
                    question_text='已知函数 $f(x)=x^2$',
                    question_text_source='ai',
                    student_library_pdf_path=?
                WHERE id=?
                """,
                (str(pdf_path), self.record_id),
            )
        os.utime(
            pdf_path,
            (
                datetime(2026, 4, 16, 13, 14, 0).timestamp(),
                datetime(2026, 4, 16, 13, 14, 0).timestamp(),
            ),
        )

        def rebuild_library(student_id: int) -> str:
            self.assertEqual(student_id, self.student["id"])
            pdf_path.write_bytes(b"%PDF-1.4\nrebuilt pdf\n")
            return str(pdf_path)

        with patch("app._rebuild_student_wrong_question_library", side_effect=rebuild_library) as rebuild:
            response = self.client.get(f"/api/wechat/student-libraries/{self.student['id']}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertEqual(response.data, b"%PDF-1.4\nrebuilt pdf\n")
        rebuild.assert_called_once_with(self.student["id"])

    def test_student_library_pdf_endpoint_serves_cached_file_when_pdf_is_fresh(self):
        library_dir = app_module.PDF_DIR / "wrong_question_libraries"
        library_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = library_dir / f"student-{self.student['id']}.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nfresh cached pdf\n")

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE wrong_question_submissions
                SET recognition_status='recognized',
                    question_text='已知函数 $f(x)=x^2$',
                    question_text_source='ai',
                    student_library_pdf_path=?,
                    updated_at='2026-04-16 13:14:23'
                WHERE id=?
                """,
                (str(pdf_path), self.record_id),
            )
        os.utime(
            pdf_path,
            (
                datetime(2026, 4, 16, 13, 15, 0).timestamp(),
                datetime(2026, 4, 16, 13, 15, 0).timestamp(),
            ),
        )

        with patch("app._rebuild_student_wrong_question_library") as rebuild:
            response = self.client.get(f"/api/wechat/student-libraries/{self.student['id']}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertEqual(response.data, b"%PDF-1.4\nfresh cached pdf\n")
        rebuild.assert_not_called()

    def test_visible_member_can_delete_local_wrong_question(self):
        with lesson_manager.get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
                VALUES (?, ?, ?, 'member', 'active', ?)
                """,
                (
                    "member_delete",
                    lesson_manager.hash_password("member-delete-123"),
                    "Member Delete",
                    self.owner_payload["user"]["organization_id"],
                ),
            )
            member_id = cur.lastrowid
        lesson_manager.set_user_class_ids(member_id, [self.class_id])
        member_token = lesson_manager.create_auth_session(member_id)

        response = self.client.delete(
            f"/api/wrong-questions/{self.record_id}",
            headers=self.auth_headers(member_token),
        )

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
