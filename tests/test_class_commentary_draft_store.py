import hashlib
import os
import tempfile
import unittest

import lesson_manager


class ClassCommentaryDraftStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        lesson_manager.init_db()

        self.teacher = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class(
            "课堂点评草稿测试班",
            subject="数学",
            grade="七年级",
            organization_id=self.teacher["organization_id"],
            teacher_user_id=self.teacher["id"],
        )
        first_student = lesson_manager.create_student_for_class(self.class_id, "小王")
        second_student = lesson_manager.create_student_for_class(self.class_id, "小李")
        self.roster = [
            {"student_id": first_student["id"], "student_name": first_student["name"]},
            {"student_id": second_student["id"], "student_name": second_student["name"]},
        ]
        self.task = self._create_task("draft-store")
        imported = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.teacher["organization_id"],
            skill_id="draft-store-teacher",
            actor_user_id=self.teacher["id"],
            source_path="/skills/draft-store-teacher/SKILL.md",
            content="先写学生表现, 再给一条可执行建议.",
        )
        self.skill_registry_id = imported["registry_id"]
        self.generation_a = self._create_generation(self.task, "generation-a", "生成稿 A")
        self.generation_b = self._create_generation(self.task, "generation-b", "生成稿 B")

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        self.tmp.cleanup()

    def _create_task(self, key):
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.teacher["id"],
            audio_path=f"/tmp/{key}.m4a",
            audio_filename=f"{key}.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            "小王计算更稳了, 小李需要继续练习验算.",
        )
        return lesson_manager.get_class_commentary_task(task["id"])

    def _create_generation(self, task, request_id, feedback_text):
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=task["id"],
            generation_request_id=request_id,
            skill_registry_id=self.skill_registry_id,
            attending_roster=self.roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-v1",
            prompt_payload={"messages": [{"role": "user", "content": "生成课堂点评"}]},
            memory_context={"records": [], "rendered_text": ""},
        )
        return lesson_manager.complete_class_commentary_generation(generation["id"], feedback_text)

    def _insert_revision(self, generation, request_id):
        with lesson_manager.get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO class_commentary_revisions (
                    organization_id, task_id, generation_id, teacher_user_id,
                    revision_no, confirmation_request_id, confirmation_payload_hash,
                    final_feedback_text, generation_diff_json,
                    learning_evidence_schema_version, learning_evidence_selector_version,
                    learning_evidence_snapshot_json, learning_evidence_source_refs_json,
                    learning_evidence_hash, learning_evidence_captured_at,
                    learning_evidence_completeness, learning_evidence_missing_sources_json,
                    learn_requested, accepted_without_edit, unchanged_from_previous_revision
                )
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, '{}', 'v1', 'v1', '{}', '[]', ?, ?,
                        'empty', '[]', 0, 0, 0)
                """,
                (
                    self.teacher["organization_id"],
                    self.task["id"],
                    generation["id"],
                    self.teacher["id"],
                    request_id,
                    hashlib.sha256(request_id.encode("utf-8")).hexdigest(),
                    "已确认反馈",
                    hashlib.sha256(b"{}").hexdigest(),
                    "2026-07-14T00:00:00Z",
                ),
            )
            return int(cursor.lastrowid)

    def test_initial_save_and_update_increment_version_and_refresh_hash(self):
        self.assertIsNone(
            lesson_manager.get_class_commentary_feedback_draft(
                self.task["id"], self.generation_a["id"], self.teacher["id"]
            )
        )

        first_text = "小王: 今天计算更稳了."
        first = lesson_manager.save_class_commentary_feedback_draft(
            task_id=self.task["id"],
            generation_id=self.generation_a["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text=first_text,
            expected_draft_version=0,
        )
        self.assertEqual(first["draft_version"], 1)
        self.assertEqual(first["feedback_text"], first_text)
        self.assertEqual(
            first["content_hash"],
            hashlib.sha256(first_text.encode("utf-8")).hexdigest(),
        )

        second_text = "小王: 今天计算更稳了, 继续保持验算."
        second = lesson_manager.save_class_commentary_feedback_draft(
            task_id=self.task["id"],
            generation_id=self.generation_a["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text=second_text,
            expected_draft_version=1,
        )
        self.assertEqual(second["draft_version"], 2)
        self.assertEqual(second["feedback_text"], second_text)
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(
            second["content_hash"],
            hashlib.sha256(second_text.encode("utf-8")).hexdigest(),
        )

    def test_stale_expected_version_returns_current_draft_without_overwrite(self):
        lesson_manager.save_class_commentary_feedback_draft(
            task_id=self.task["id"],
            generation_id=self.generation_a["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text="小王: 今天计算更稳了.",
            expected_draft_version=0,
        )
        current_text = "小王: 今天计算更稳了, 继续保持验算."
        current_draft = lesson_manager.save_class_commentary_feedback_draft(
            task_id=self.task["id"],
            generation_id=self.generation_a["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text=current_text,
            expected_draft_version=1,
        )

        with self.assertRaises(lesson_manager.ClassCommentaryDraftVersionConflict) as raised:
            lesson_manager.save_class_commentary_feedback_draft(
                task_id=self.task["id"],
                generation_id=self.generation_a["id"],
                teacher_user_id=self.teacher["id"],
                feedback_text="旧标签页不应覆盖的新文本",
                expected_draft_version=1,
            )
        self.assertEqual(raised.exception.code, "draft_version_conflict")
        self.assertEqual(raised.exception.current_draft, current_draft)
        saved = lesson_manager.get_class_commentary_feedback_draft(
            self.task["id"], self.generation_a["id"], self.teacher["id"]
        )
        self.assertEqual(saved, current_draft)
        self.assertEqual(saved["feedback_text"], current_text)

    def test_generation_drafts_are_independent_and_scope_mismatches_are_rejected(self):
        draft_a = lesson_manager.save_class_commentary_feedback_draft(
            task_id=self.task["id"],
            generation_id=self.generation_a["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text="A 的草稿",
            expected_draft_version=0,
        )
        self.assertIsNone(
            lesson_manager.get_class_commentary_feedback_draft(
                self.task["id"], self.generation_b["id"], self.teacher["id"]
            )
        )
        draft_b = lesson_manager.save_class_commentary_feedback_draft(
            task_id=self.task["id"],
            generation_id=self.generation_b["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text="B 的草稿",
            expected_draft_version=0,
        )
        updated_a = lesson_manager.save_class_commentary_feedback_draft(
            task_id=self.task["id"],
            generation_id=self.generation_a["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text="A 的第二版草稿",
            expected_draft_version=1,
        )

        saved_a = lesson_manager.get_class_commentary_feedback_draft(
            self.task["id"], self.generation_a["id"], self.teacher["id"]
        )
        saved_b = lesson_manager.get_class_commentary_feedback_draft(
            self.task["id"], self.generation_b["id"], self.teacher["id"]
        )
        self.assertNotEqual(draft_a["id"], draft_b["id"])
        self.assertEqual(saved_a["id"], updated_a["id"])
        self.assertEqual(saved_a["draft_version"], 2)
        self.assertEqual(saved_a["feedback_text"], "A 的第二版草稿")
        self.assertEqual(saved_b["draft_version"], 1)
        self.assertEqual(saved_b["feedback_text"], "B 的草稿")

        other_task = self._create_task("other-task")
        other_generation = self._create_generation(
            other_task, "other-task-generation", "其他任务生成稿"
        )
        with lesson_manager.get_conn() as conn:
            other_teacher = conn.execute(
                """
                INSERT INTO users (
                    username, password_hash, display_name, role, status, organization_id
                ) VALUES (?, ?, ?, 'member', 'active', ?)
                """,
                (
                    "draft-store-other-teacher",
                    "hash",
                    "Other Teacher",
                    self.teacher["organization_id"],
                ),
            )
            other_teacher_id = int(other_teacher.lastrowid)

        with self.assertRaisesRegex(ValueError, "generation does not belong to task"):
            lesson_manager.save_class_commentary_feedback_draft(
                task_id=self.task["id"],
                generation_id=other_generation["id"],
                teacher_user_id=self.teacher["id"],
                feedback_text="不应保存",
                expected_draft_version=0,
            )
        with self.assertRaisesRegex(ValueError, "generation is not owned by teacher"):
            lesson_manager.save_class_commentary_feedback_draft(
                task_id=self.task["id"],
                generation_id=self.generation_a["id"],
                teacher_user_id=other_teacher_id,
                feedback_text="不应保存",
                expected_draft_version=0,
            )

        mismatched_revision_id = self._insert_revision(
            self.generation_b, "revision-for-generation-b"
        )
        with self.assertRaisesRegex(
            ValueError, "based_on_revision_id does not match draft scope"
        ):
            lesson_manager.save_class_commentary_feedback_draft(
                task_id=self.task["id"],
                generation_id=self.generation_a["id"],
                teacher_user_id=self.teacher["id"],
                feedback_text="不能基于其他 generation 的 revision",
                expected_draft_version=2,
                based_on_revision_id=mismatched_revision_id,
            )

        with lesson_manager.get_conn() as conn:
            draft_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_feedback_drafts"
            ).fetchone()[0]
        self.assertEqual(draft_count, 2)
        self.assertEqual(
            lesson_manager.get_class_commentary_feedback_draft(
                self.task["id"], self.generation_a["id"], self.teacher["id"]
            )["feedback_text"],
            "A 的第二版草稿",
        )
        self.assertEqual(
            lesson_manager.get_class_commentary_feedback_draft(
                self.task["id"], self.generation_b["id"], self.teacher["id"]
            )["feedback_text"],
            "B 的草稿",
        )


if __name__ == "__main__":
    unittest.main()
