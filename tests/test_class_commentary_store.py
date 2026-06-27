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


if __name__ == "__main__":
    unittest.main()
