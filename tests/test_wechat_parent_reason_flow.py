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
from app import app


class WeChatParentReasonFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
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
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
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
        submission = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/wrong-question.png",
            child_raw_reason_text="孩子说是计算粗心",
            primary_error_type="计算问题",
            secondary_error_summary="抄错了符号",
        )
        self.record_id = submission["id"]

    def tearDown(self):
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


if __name__ == "__main__":
    unittest.main()
