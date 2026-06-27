import os
import sqlite3
import tempfile
import unittest

import lesson_manager


class ClassCommentaryStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        lesson_manager.init_db()

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        self.tmp.cleanup()

    def test_schema_drops_old_feedback_tables_and_creates_new_table(self):
        with lesson_manager.get_conn() as conn:
            names = {
                row["name"]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
        self.assertIn("class_commentary_tasks", names)
        self.assertNotIn("lesson_class_feedbacks", names)
        self.assertNotIn("class_feedback_tasks", names)
        self.assertNotIn("class_feedback_student_entries", names)
        self.assertNotIn("class_feedback_label_configs", names)
        self.assertFalse(any(name.startswith("class_feedback_") for name in names))

    def test_task_lifecycle_keeps_empty_strings_in_serialized_task(self):
        class_id = lesson_manager.save_class("数学·七年级·4班", organization_id=1, teacher_user_id=1)
        task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/audio.m4a",
            audio_filename="audio.m4a",
            transcription_request_key="audio-key",
        )
        self.assertEqual(task["status"], "uploaded")
        self.assertEqual(task["failure_stage"], "")
        self.assertEqual(task["feedback_text"], "")

        transcribing = lesson_manager.mark_class_commentary_task_transcribing(task["id"])
        self.assertEqual(transcribing["status"], "transcribing")

        transcribed = lesson_manager.mark_class_commentary_transcription_succeeded(task["id"], "小王今天计算更稳了")
        self.assertEqual(transcribed["status"], "transcribed")
        self.assertEqual(transcribed["transcript_text"], "小王今天计算更稳了")
        self.assertEqual(transcribed["confirmed_transcript_text"], "小王今天计算更稳了")
        self.assertTrue(transcribed["transcribed_at"])

        confirmed = lesson_manager.save_class_commentary_transcript(task["id"], "小王今天计算更稳了, 回家继续练")
        self.assertEqual(confirmed["status"], "transcribed")
        self.assertEqual(confirmed["confirmed_transcript_text"], "小王今天计算更稳了, 回家继续练")

        generating = lesson_manager.save_class_commentary_generation_started(
            task["id"],
            skill_id="teacher-a",
            skill_name="Teacher A",
            skill_path="/skills/teacher-a.skill",
            skill_content_snapshot="style rules",
            generation_request_key="gen-key",
            chat_provider="deepseek",
            chat_model="deepseek-v4-pro",
        )
        self.assertEqual(generating["status"], "generating")
        self.assertEqual(generating["skill_id"], "teacher-a")

        ready = lesson_manager.save_class_commentary_generation_succeeded(task["id"], "小王:\n今天计算更稳了.")
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["failure_stage"], "")
        self.assertEqual(ready["generation_error"], "")
        self.assertEqual(ready["feedback_text"], "小王:\n今天计算更稳了.")

    def test_failed_generation_can_return_to_transcribed_by_saving_transcript(self):
        class_id = lesson_manager.save_class("数学·七年级·4班", organization_id=1, teacher_user_id=1)
        task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/audio.m4a",
            audio_filename="audio.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(task["id"], "小王需要再练计算")
        failed = lesson_manager.mark_class_commentary_task_failed(task["id"], "generation", "model timeout")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["failure_stage"], "generation")
        self.assertEqual(failed["generation_error"], "model timeout")

        recovered = lesson_manager.save_class_commentary_transcript(task["id"], "小王需要再练计算速度")
        self.assertEqual(recovered["status"], "transcribed")
        self.assertEqual(recovered["failure_stage"], "")
        self.assertEqual(recovered["generation_error"], "")

    def test_usable_states_clear_stale_transcription_error(self):
        class_id = lesson_manager.save_class("数学·七年级·6班", organization_id=1, teacher_user_id=1)
        task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/audio-2.m4a",
            audio_filename="audio-2.m4a",
        )
        failed = lesson_manager.mark_class_commentary_task_failed(task["id"], "transcription", "whisper timeout")
        self.assertEqual(failed["transcription_error"], "whisper timeout")

        recovered = lesson_manager.save_class_commentary_transcript(task["id"], "老师已修正转写")
        self.assertEqual(recovered["status"], "transcribed")
        self.assertEqual(recovered["transcription_error"], "")

        failed = lesson_manager.mark_class_commentary_task_failed(task["id"], "transcription", "retry later")
        self.assertEqual(failed["transcription_error"], "retry later")

        generating = lesson_manager.save_class_commentary_generation_started(
            task["id"],
            skill_id="teacher-b",
            skill_name="Teacher B",
            skill_path="/skills/teacher-b.skill",
            skill_content_snapshot="tone rules",
            generation_request_key="gen-key-2",
            chat_provider="deepseek",
            chat_model="deepseek-v4-pro",
        )
        self.assertEqual(generating["status"], "generating")
        self.assertEqual(generating["transcription_error"], "")

        failed = lesson_manager.mark_class_commentary_task_failed(task["id"], "transcription", "one more retry")
        self.assertEqual(failed["transcription_error"], "one more retry")

        ready = lesson_manager.save_class_commentary_generation_succeeded(task["id"], "反馈内容")
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["transcription_error"], "")

    def test_maintenance_flows_do_not_touch_deleted_class_feedback_tables(self):
        student = lesson_manager.create_student_profile("无引用学生", organization_id=1)
        result = lesson_manager.delete_or_archive_student_profile(student["id"], organization_id=1)
        self.assertEqual(result["action"], "deleted")

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("class-commentary-member", "hash", "Class Commentary Member", "member", "active", 1),
            )
            member_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO organizations (name)
                VALUES (?)
                """,
                ("Class Commentary Cleanup Org",),
            )
            org_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        actor_user = lesson_manager.get_user_by_username("Kayn")
        lesson_manager.delete_user_for_actor(actor_user, member_id)
        self.assertIsNone(lesson_manager.get_user_by_username("class-commentary-member"))

        lesson_manager.delete_organization(org_id)
        with lesson_manager.get_conn() as conn:
            org_row = conn.execute("SELECT id FROM organizations WHERE id=?", (org_id,)).fetchone()
        self.assertIsNone(org_row)


if __name__ == "__main__":
    unittest.main()
