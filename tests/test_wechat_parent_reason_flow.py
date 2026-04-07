from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lesson_manager


class WeChatParentReasonFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        lesson_manager.DB_PATH = Path(self.temp_dir.name) / "lessons.db"
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


if __name__ == "__main__":
    unittest.main()
