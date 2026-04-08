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

    def test_wrong_question_submission_rejects_unknown_child_reason_input_mode(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )

        with self.assertRaises(ValueError) as ctx:
            lesson_manager.create_wechat_wrong_question_submission(
                binding_id=binding["id"],
                image_url="https://files.example.com/wrong-question.png",
                child_reason_input_mode="typing",
            )

        self.assertEqual(str(ctx.exception), "child_reason_input_mode must be text or voice")

    def test_list_wechat_wrong_question_submissions_for_parent_student_scopes_records(self):
        primary_account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        primary_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=primary_account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        target = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=primary_binding["id"],
            image_url="https://files.example.com/target.png",
        )

        other_student = lesson_manager.create_student_for_class(self.class_id, "Bob")
        other_student_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=primary_account["id"],
            class_id=self.class_id,
            student_id=other_student["id"],
        )
        lesson_manager.create_wechat_wrong_question_submission(
            binding_id=other_student_binding["id"],
            image_url="https://files.example.com/other-student.png",
        )

        other_account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-2")
        other_account_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=other_account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        lesson_manager.create_wechat_wrong_question_submission(
            binding_id=other_account_binding["id"],
            image_url="https://files.example.com/other-parent.png",
        )

        items = lesson_manager.list_wechat_wrong_question_submissions_for_parent_student(
            parent_wechat_account_id=primary_account["id"],
            student_id=self.student["id"],
        )

        self.assertEqual([item["id"] for item in items], [target["id"]])
        self.assertEqual(items[0]["parent_wechat_account_id"], primary_account["id"])
        self.assertEqual(items[0]["student_id"], self.student["id"])

    def test_remove_student_from_class_hides_active_parent_binding_from_mini_program(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )

        removed = lesson_manager.remove_student_from_class(self.class_id, self.student["id"])
        bindings = lesson_manager.list_parent_student_bindings_for_openid("openid-parent-1")

        self.assertTrue(removed)
        self.assertEqual(bindings, [])
        with lesson_manager.get_conn() as conn:
            row = conn.execute(
                "SELECT status FROM parent_student_bindings WHERE id=?",
                (binding["id"],),
            ).fetchone()
        self.assertEqual(row["status"], "inactive")

    def test_init_db_migrates_legacy_wrong_question_rows_with_default_reason_and_archive_fields(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )

        with lesson_manager.get_conn() as conn:
            conn.execute("DROP TABLE wrong_question_submissions")
            conn.execute(
                """
                CREATE TABLE wrong_question_submissions (
                    id                        TEXT PRIMARY KEY,
                    organization_id           INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                    source                    TEXT NOT NULL DEFAULT 'wechat_mp',
                    parent_wechat_account_id  INTEGER NOT NULL REFERENCES parent_wechat_accounts(id) ON DELETE CASCADE,
                    binding_id                INTEGER NOT NULL REFERENCES parent_student_bindings(id) ON DELETE CASCADE,
                    class_id                  INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                    student_id                INTEGER NOT NULL REFERENCES students(id),
                    teacher_user_id           INTEGER NOT NULL REFERENCES users(id),
                    image_url                 TEXT NOT NULL,
                    parent_note               TEXT NOT NULL DEFAULT '',
                    teacher_comment           TEXT NOT NULL DEFAULT '',
                    status                    TEXT NOT NULL DEFAULT 'pending',
                    created_at                TEXT DEFAULT (datetime('now','localtime')),
                    updated_at                TEXT DEFAULT (datetime('now','localtime'))
                )
                """
            )
            conn.execute(
                """
                INSERT INTO wrong_question_submissions (
                    id, organization_id, source, parent_wechat_account_id, binding_id,
                    class_id, student_id, teacher_user_id, image_url, parent_note,
                    teacher_comment, status
                ) VALUES (?, ?, 'wechat_mp', ?, ?, ?, ?, ?, ?, ?, '', 'pending')
                """,
                (
                    "legacy-record-1",
                    binding["organization_id"],
                    binding["parent_wechat_account_id"],
                    binding["id"],
                    binding["class_id"],
                    binding["student_id"],
                    binding["teacher_user_id"],
                    "https://files.example.com/legacy.png",
                    "旧记录",
                ),
            )

        lesson_manager.init_db()

        with lesson_manager.get_conn() as conn:
            columns = {
                row["name"]: row["dflt_value"]
                for row in conn.execute("PRAGMA table_info(wrong_question_submissions)").fetchall()
            }
            row = conn.execute(
                """
                SELECT
                    child_raw_reason_text,
                    child_reason_input_mode,
                    primary_error_type,
                    secondary_error_summary,
                    archive_status,
                    archived_at
                FROM wrong_question_submissions
                WHERE id=?
                """,
                ("legacy-record-1",),
            ).fetchone()

        self.assertIn("child_raw_reason_text", columns)
        self.assertIn("child_reason_input_mode", columns)
        self.assertIn("primary_error_type", columns)
        self.assertIn("secondary_error_summary", columns)
        self.assertIn("archive_status", columns)
        self.assertIn("archived_at", columns)
        self.assertEqual(row["child_raw_reason_text"], "")
        self.assertEqual(row["child_reason_input_mode"], "text")
        self.assertEqual(row["primary_error_type"], "")
        self.assertEqual(row["secondary_error_summary"], "")
        self.assertEqual(row["archive_status"], "active")
        self.assertEqual(row["archived_at"], "")

if __name__ == "__main__":
    unittest.main()
