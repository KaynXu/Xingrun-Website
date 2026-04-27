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
        lesson_manager.DB_PATH = Path(self.temp_dir.name) / "xingrun.db"
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

    def test_get_conn_context_manager_closes_connection(self):
        with lesson_manager.get_conn() as conn:
            row = conn.execute("SELECT 1 AS value").fetchone()

        self.assertEqual(row["value"], 1)
        with self.assertRaisesRegex(Exception, "closed"):
            conn.execute("SELECT 1")

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
        )

        self.assertEqual(binding["teacher_user_id"], self.owner_id)
        self.assertEqual(submission["class_id"], self.class_id)
        self.assertEqual(submission["student_id"], self.student["id"])
        self.assertEqual(submission["teacher_user_id"], self.owner_id)
        self.assertEqual(submission["source"], "wechat_mp")
        self.assertEqual(submission["status"], "pending")

    def test_wrong_question_submission_table_removes_legacy_feedback_columns(self):
        with lesson_manager.get_conn() as conn:
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(wrong_question_submissions)").fetchall()
            }

        self.assertNotIn("parent_note", columns)
        self.assertNotIn("teacher_comment", columns)

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

    def test_save_wechat_wrong_question_review_only_updates_mastery_state(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        submission = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/wrong-question.png",
            child_raw_reason_text="我把减号看成了加号",
            primary_error_type="审题不清",
            secondary_error_summary="把运算符号看错了。",
        )

        saved = lesson_manager.save_wechat_wrong_question_review(
            submission["id"],
            {
                "is_mastered": True,
                "teacher_comment": "旧字段不该再生效",
                "status": "reviewed",
            },
        )

        self.assertEqual(saved["archive_status"], "archived")
        self.assertNotEqual(saved["archived_at"], "")
        self.assertNotIn("teacher_comment", saved)
        self.assertEqual(saved["status"], "pending")

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
        other_student_record = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=other_student_binding["id"],
            image_url="https://files.example.com/other-student.png",
        )

        other_account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-2")
        other_account_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=other_account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        other_parent_record = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=other_account_binding["id"],
            image_url="https://files.example.com/other-parent.png",
        )

        items = lesson_manager.list_wechat_wrong_question_submissions_for_parent_student(
            parent_wechat_account_id=primary_account["id"],
            student_id=self.student["id"],
        )

        item_ids = {item["id"] for item in items}
        self.assertEqual(item_ids, {target["id"], other_parent_record["id"]})
        self.assertNotIn(other_student_record["id"], item_ids)
        self.assertEqual({item["student_id"] for item in items}, {self.student["id"]})

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
        self.assertNotIn("parent_note", columns)
        self.assertNotIn("teacher_comment", columns)
        self.assertEqual(row["child_raw_reason_text"], "")
        self.assertEqual(row["child_reason_input_mode"], "text")
        self.assertEqual(row["primary_error_type"], "")
        self.assertEqual(row["secondary_error_summary"], "")
        self.assertEqual(row["archive_status"], "active")
        self.assertEqual(row["archived_at"], "")

    def test_wrong_question_submission_stores_recognition_and_library_fields(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )

        submission = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/wrong-question.png",
            recognition_status="recognized",
            is_geometry=False,
            question_text="计算 $2+3\\times4$ 的结果。",
            question_text_source="ai",
            student_library_pdf_path="/tmp/student-1.pdf",
        )

        self.assertEqual(submission["recognition_status"], "recognized")
        self.assertEqual(submission["is_geometry"], 0)
        self.assertEqual(submission["question_text"], "计算 $2+3\\times4$ 的结果。")
        self.assertEqual(submission["question_text_source"], "ai")
        self.assertEqual(submission["student_library_pdf_path"], "/tmp/student-1.pdf")

    def test_update_local_question_text_marks_teacher_source(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        submission = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/wrong-question.png",
            recognition_status="recognized",
            is_geometry=False,
            question_text="原始 AI 文本",
            question_text_source="ai",
        )

        updated = lesson_manager.update_wechat_wrong_question_question_text(
            submission["id"],
            question_text="老师修正后的题目文本",
            student_library_pdf_path="/tmp/student-1.pdf",
        )

        self.assertEqual(updated["question_text"], "老师修正后的题目文本")
        self.assertEqual(updated["question_text_source"], "teacher")
        self.assertEqual(updated["question_text_edited"], 1)
        self.assertEqual(updated["student_library_pdf_path"], "/tmp/student-1.pdf")

    def test_create_wechat_wrong_question_upload_task_stores_payload_and_scope(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )

        task = lesson_manager.create_wechat_wrong_question_upload_task(
            binding_id=binding["id"],
            image_url="https://files.example.com/wrong-question.png",
            child_raw_reason_text="我把单位换算漏掉了",
            child_reason_input_mode="voice",
            child_reason_audio_url="https://files.example.com/reason.m4a",
        )

        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["binding_id"], binding["id"])
        self.assertEqual(task["parent_wechat_account_id"], account["id"])
        self.assertEqual(task["student_id"], self.student["id"])
        self.assertEqual(task["image_url"], "https://files.example.com/wrong-question.png")
        self.assertEqual(task["child_raw_reason_text"], "我把单位换算漏掉了")
        self.assertEqual(task["child_reason_input_mode"], "voice")
        self.assertEqual(task["child_reason_audio_url"], "https://files.example.com/reason.m4a")
        self.assertEqual(task["record_id"], "")
        self.assertEqual(task["error_message"], "")

    def test_create_wechat_wrong_question_upload_task_allows_image_only_submission(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )

        task = lesson_manager.create_wechat_wrong_question_upload_task(
            binding_id=binding["id"],
            image_url="https://files.example.com/wrong-question.png",
            child_raw_reason_text="",
        )

        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["child_raw_reason_text"], "")
        self.assertEqual(task["child_reason_audio_url"], "")

    def test_update_wechat_wrong_question_upload_task_status(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        task = lesson_manager.create_wechat_wrong_question_upload_task(
            binding_id=binding["id"],
            image_url="https://files.example.com/wrong-question.png",
            child_raw_reason_text="我看漏了题目条件",
        )

        updated = lesson_manager.update_wechat_wrong_question_upload_task(
            task["id"],
            status="ready",
            record_id="wechat-record-1",
            error_message="",
        )

        self.assertEqual(updated["status"], "ready")
        self.assertEqual(updated["record_id"], "wechat-record-1")
        self.assertEqual(updated["error_message"], "")

    def test_get_wechat_wrong_question_upload_task_for_parent_scopes_by_openid(self):
        primary_account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
        primary_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=primary_account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        task = lesson_manager.create_wechat_wrong_question_upload_task(
            binding_id=primary_binding["id"],
            image_url="https://files.example.com/wrong-question.png",
            child_raw_reason_text="我看漏了题目条件",
        )
        other_account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-2")
        other_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=other_account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        lesson_manager.create_wechat_wrong_question_upload_task(
            binding_id=other_binding["id"],
            image_url="https://files.example.com/other.png",
            child_raw_reason_text="我算错了",
        )

        visible = lesson_manager.get_wechat_wrong_question_upload_task_for_openid(
            task["id"],
            "openid-parent-1",
        )
        hidden = lesson_manager.get_wechat_wrong_question_upload_task_for_openid(
            task["id"],
            "openid-parent-2",
        )

        self.assertIsNotNone(visible)
        self.assertEqual(visible["id"], task["id"])
        self.assertIsNone(hidden)

if __name__ == "__main__":
    unittest.main()
