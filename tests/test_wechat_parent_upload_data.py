from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lesson_manager


class WeChatParentUploadDataTestCase(unittest.TestCase):
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

    def test_class_invite_is_reused_until_reset(self):
        first = lesson_manager.get_or_create_active_class_invite(self.class_id, self.owner_id)
        second = lesson_manager.get_or_create_active_class_invite(self.class_id, self.owner_id)
        reset = lesson_manager.reset_class_invite(self.class_id, self.owner_id)

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["class_id"], self.class_id)
        self.assertNotEqual(first["invite_code"], reset["invite_code"])
        self.assertEqual(reset["status"], "active")

    def test_parent_binding_and_submission_store_canonical_ids(self):
        account = lesson_manager.upsert_parent_wechat_account(
            openid="openid-parent-1",
            nickname_snapshot="Alice 妈妈",
            avatar_url_snapshot="https://example.com/avatar.png",
        )
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        submission = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/wrong-question.png",
            parent_note="请老师看一下这题",
        )

        self.assertEqual(binding["teacher_user_id"], self.owner_id)
        self.assertEqual(submission["class_id"], self.class_id)
        self.assertEqual(submission["student_id"], self.student["id"])
        self.assertEqual(submission["teacher_user_id"], self.owner_id)
        self.assertEqual(submission["source"], "wechat_mp")
        self.assertEqual(submission["status"], "pending")

    def test_wrong_question_submission_stores_reason_and_archive_fields(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )

        submission = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/wrong-question.png",
            parent_note="这题又错了",
            child_raw_reason_text="我忘了等式两边同时乘一样的数字",
            child_reason_input_mode="voice",
            primary_error_type="计算问题",
            secondary_error_summary="等式两边没有同时乘相同的数字",
        )

        self.assertEqual(submission["primary_error_type"], "计算问题")
        self.assertEqual(submission["secondary_error_summary"], "等式两边没有同时乘相同的数字")
        self.assertEqual(submission["child_raw_reason_text"], "我忘了等式两边同时乘一样的数字")
        self.assertEqual(submission["child_reason_input_mode"], "voice")
        self.assertEqual(submission["archive_status"], "active")

    def test_list_parent_bindings_for_openid_returns_current_display_fields(self):
        account = lesson_manager.upsert_parent_wechat_account(
            openid="openid-parent-1",
            nickname_snapshot="Alice 妈妈",
        )
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )

        items = lesson_manager.list_parent_student_bindings_for_openid("openid-parent-1")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], binding["id"])
        self.assertEqual(items[0]["class_id"], self.class_id)
        self.assertEqual(items[0]["class_name"], "六年级 1 班")
        self.assertEqual(items[0]["student_id"], self.student["id"])
        self.assertEqual(items[0]["student_name"], "Alice")
        self.assertEqual(items[0]["teacher_user_id"], self.owner_id)
        self.assertEqual(items[0]["teacher_name"], "平台管理员")


if __name__ == "__main__":
    unittest.main()
