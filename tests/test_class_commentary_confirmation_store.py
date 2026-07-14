import hashlib
import json
import os
import tempfile
import unittest

import lesson_manager


class ClassCommentaryConfirmationStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        lesson_manager.init_db()

        self.teacher = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class(
            "课堂点评确认测试班",
            subject="数学",
            grade="七年级",
            organization_id=self.teacher["organization_id"],
            teacher_user_id=self.teacher["id"],
        )
        student = lesson_manager.create_student_for_class(self.class_id, "小王")
        self.roster = [{"student_id": student["id"], "student_name": student["name"]}]
        self.task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.teacher["id"],
            audio_path="/tmp/class-commentary-confirmation.m4a",
            audio_filename="class-commentary-confirmation.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            self.task["id"],
            "小王计算更稳了, 需要继续练习验算.",
        )
        imported = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.teacher["organization_id"],
            skill_id="confirmation-store-teacher",
            owner_teacher_user_id=self.teacher["id"],
            source_path="/skills/confirmation-store-teacher/SKILL.md",
            content="先写学生本次表现, 再给一条可执行建议.",
        )
        self.generated_feedback = "小王: 计算过程更稳定, 继续保持."
        self.generation = lesson_manager.reserve_class_commentary_generation(
            task_id=self.task["id"],
            generation_request_id="confirmation-generation-request",
            skill_registry_id=imported["registry_id"],
            attending_roster=self.roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-v1",
            prompt_payload={"messages": [{"role": "user", "content": "生成课堂反馈"}]},
            memory_context={"records": [], "rendered_text": ""},
        )
        lesson_manager.complete_class_commentary_generation(
            self.generation["id"],
            self.generated_feedback,
        )

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        self.tmp.cleanup()

    @staticmethod
    def _canonical_json(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _hash_json(cls, value):
        return hashlib.sha256(cls._canonical_json(value).encode("utf-8")).hexdigest()

    def _confirm(
        self,
        feedback_text,
        request_id,
        expected_draft_version=0,
        learn_requested=False,
        task_id=None,
        generation_id=None,
    ):
        return lesson_manager.confirm_class_commentary_feedback(
            task_id=self.task["id"] if task_id is None else task_id,
            generation_id=self.generation["id"] if generation_id is None else generation_id,
            teacher_user_id=self.teacher["id"],
            feedback_text=feedback_text,
            learn_requested=learn_requested,
            expected_draft_version=expected_draft_version,
            confirmation_request_id=request_id,
        )

    def _revision_rows(self, task_id=None):
        with lesson_manager.get_conn() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM class_commentary_revisions WHERE task_id=? ORDER BY revision_no",
                    (self.task["id"] if task_id is None else task_id,),
                ).fetchall()
            ]

    def _draft_row(self, task_id=None, generation_id=None):
        with lesson_manager.get_conn() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM class_commentary_feedback_drafts
                WHERE task_id=? AND generation_id=? AND teacher_user_id=?
                """,
                (
                    self.task["id"] if task_id is None else task_id,
                    self.generation["id"] if generation_id is None else generation_id,
                    self.teacher["id"],
                ),
            ).fetchone()
        return dict(row) if row else None

    def test_confirm_without_learning_atomically_creates_revision_draft_and_task_state(self):
        final_feedback = "小王: 计算过程更稳定, 建议每次完成后主动验算."
        self._confirm(final_feedback, "confirmation-request-1")

        revisions = self._revision_rows()
        draft = self._draft_row()
        task = lesson_manager.get_class_commentary_task(self.task["id"])
        generation = lesson_manager.get_class_commentary_generation(self.generation["id"])

        self.assertEqual(len(revisions), 1)
        revision = revisions[0]
        self.assertEqual(revision["organization_id"], self.teacher["organization_id"])
        self.assertEqual(revision["task_id"], self.task["id"])
        self.assertEqual(revision["generation_id"], self.generation["id"])
        self.assertEqual(revision["teacher_user_id"], self.teacher["id"])
        self.assertEqual(revision["revision_no"], 1)
        self.assertEqual(revision["confirmation_request_id"], "confirmation-request-1")
        self.assertRegex(revision["confirmation_payload_hash"], r"^[0-9a-f]{64}$")
        self.assertIsNone(revision["previous_revision_id"])
        self.assertEqual(revision["final_feedback_text"], final_feedback)
        self.assertTrue(json.loads(revision["generation_diff_json"]))
        self.assertIsNone(revision["previous_revision_diff_json"])
        self.assertEqual(revision["learn_requested"], 0)
        self.assertEqual(revision["accepted_without_edit"], 0)
        self.assertEqual(revision["unchanged_from_previous_revision"], 0)

        snapshot = json.loads(revision["learning_evidence_snapshot_json"])
        source_refs = json.loads(revision["learning_evidence_source_refs_json"])
        missing_sources = json.loads(revision["learning_evidence_missing_sources_json"])
        self.assertFalse(snapshot)
        self.assertEqual(source_refs, [])
        self.assertEqual(missing_sources, [])
        self.assertEqual(revision["learning_evidence_completeness"], "empty")
        self.assertEqual(
            revision["learning_evidence_snapshot_json"],
            self._canonical_json(snapshot),
        )
        empty_envelope = {
            "schema_version": revision["learning_evidence_schema_version"],
            "selector_version": revision["learning_evidence_selector_version"],
            "captured_at": revision["learning_evidence_captured_at"],
            "snapshot": snapshot,
            "source_refs": source_refs,
            "completeness": "empty",
            "missing_sources": missing_sources,
        }
        self.assertEqual(revision["learning_evidence_hash"], self._hash_json(empty_envelope))

        self.assertEqual(draft["feedback_text"], final_feedback)
        self.assertEqual(
            draft["content_hash"],
            hashlib.sha256(final_feedback.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(draft["draft_version"], 1)
        self.assertEqual(draft["based_on_revision_id"], revision["id"])
        self.assertEqual(task["final_feedback_text"], final_feedback)
        self.assertEqual(task["feedback_text"], final_feedback)
        self.assertEqual(task["latest_revision_id"], revision["id"])
        self.assertEqual(task["feedback_revision_no"], 1)
        self.assertTrue(task["feedback_confirmed_at"])
        self.assertEqual(generation["generated_feedback_text"], self.generated_feedback)

    def test_same_request_is_idempotent_and_changed_payload_conflicts_without_new_row(self):
        final_feedback = "小王: 计算稳定, 继续练习验算."
        self._confirm(final_feedback, "confirmation-request-idempotent")
        first_revision = self._revision_rows()[0]
        first_draft = self._draft_row()

        self._confirm(final_feedback, "confirmation-request-idempotent")
        with self.assertRaises(lesson_manager.ClassCommentaryConfirmationRequestConflict):
            self._confirm(
                "小王: 改成另一份终稿.",
                "confirmation-request-idempotent",
            )
        with self.assertRaises(lesson_manager.ClassCommentaryConfirmationRequestConflict):
            self._confirm(
                final_feedback,
                "confirmation-request-idempotent",
                expected_draft_version=1,
            )

        self.assertEqual(self._revision_rows(), [first_revision])
        self.assertEqual(self._draft_row(), first_draft)
        task = lesson_manager.get_class_commentary_task(self.task["id"])
        self.assertEqual(task["latest_revision_id"], first_revision["id"])
        self.assertEqual(task["feedback_revision_no"], 1)
        self.assertEqual(task["final_feedback_text"], final_feedback)

    def test_idempotent_replay_returns_original_confirmation_draft_snapshot_after_later_edit(self):
        final_feedback = "小王: 计算稳定, 继续练习验算."
        request_id = "confirmation-request-original-draft-snapshot"

        first_result = self._confirm(final_feedback, request_id)
        first_revision_id = first_result["id"]
        first_draft_snapshot = dict(first_result["draft"])
        self.assertEqual(first_result["draft_version"], 1)
        self.assertEqual(first_draft_snapshot["draft_version"], 1)
        self.assertEqual(first_draft_snapshot["feedback_text"], final_feedback)

        later_draft = lesson_manager.save_class_commentary_feedback_draft(
            task_id=self.task["id"],
            generation_id=self.generation["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text="小王: 这是确认后继续编辑但尚未再次确认的草稿.",
            expected_draft_version=1,
            based_on_revision_id=first_revision_id,
        )
        self.assertEqual(later_draft["draft_version"], 2)

        replayed_result = self._confirm(final_feedback, request_id)

        self.assertEqual(replayed_result["id"], first_revision_id)
        self.assertEqual(replayed_result["draft_version"], 1)
        self.assertEqual(replayed_result["draft"], first_draft_snapshot)
        self.assertEqual(len(self._revision_rows()), 1)
        self.assertEqual(self._draft_row()["draft_version"], 2)
        self.assertEqual(
            self._draft_row()["feedback_text"],
            "小王: 这是确认后继续编辑但尚未再次确认的草稿.",
        )

    def test_stale_draft_conflict_rolls_back_then_next_valid_confirmation_links_revision_diff(self):
        self._confirm(
            self.generated_feedback,
            "confirmation-request-first-revision",
        )
        first_revision = self._revision_rows()[0]
        first_draft = self._draft_row()
        task_before_conflict = lesson_manager.get_class_commentary_task(self.task["id"])

        with self.assertRaises(lesson_manager.ClassCommentaryDraftVersionConflict):
            self._confirm(
                "小王: 旧标签页试图覆盖新草稿.",
                "confirmation-request-stale-draft",
                expected_draft_version=0,
            )

        self.assertEqual(self._revision_rows(), [first_revision])
        self.assertEqual(self._draft_row(), first_draft)
        task_after_conflict = lesson_manager.get_class_commentary_task(self.task["id"])
        self.assertEqual(task_after_conflict["latest_revision_id"], task_before_conflict["latest_revision_id"])
        self.assertEqual(task_after_conflict["feedback_revision_no"], 1)
        self.assertEqual(task_after_conflict["final_feedback_text"], self.generated_feedback)

        revised_feedback = "小王: 计算过程更稳定, 每次完成后再验算一次."
        self._confirm(
            revised_feedback,
            "confirmation-request-second-revision",
            expected_draft_version=1,
        )
        first_after_second_confirmation, second_revision = self._revision_rows()
        self.assertEqual(first_after_second_confirmation, first_revision)
        self.assertEqual(second_revision["revision_no"], 2)
        self.assertEqual(second_revision["previous_revision_id"], first_revision["id"])
        self.assertTrue(json.loads(second_revision["generation_diff_json"]))
        self.assertTrue(json.loads(second_revision["previous_revision_diff_json"]))
        self.assertEqual(first_revision["accepted_without_edit"], 1)
        self.assertEqual(first_revision["unchanged_from_previous_revision"], 0)
        self.assertEqual(second_revision["accepted_without_edit"], 0)
        self.assertEqual(second_revision["unchanged_from_previous_revision"], 0)
        second_draft = self._draft_row()
        self.assertEqual(second_draft["draft_version"], 2)
        self.assertEqual(second_draft["based_on_revision_id"], second_revision["id"])
        self.assertEqual(second_draft["feedback_text"], revised_feedback)

    def test_learning_is_not_enabled_for_runtime_or_legacy_partial_generation(self):
        with self.assertRaises(lesson_manager.ClassCommentaryMemoryNotEnabled) as runtime_error:
            self._confirm(
                self.generated_feedback,
                "confirmation-request-runtime-learning",
                learn_requested=True,
            )
        self.assertEqual(runtime_error.exception.code, "memory_not_enabled")

        legacy_task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.teacher["id"],
            audio_path="/tmp/class-commentary-legacy-confirmation.m4a",
            audio_filename="class-commentary-legacy-confirmation.m4a",
        )
        legacy_feedback = "小王: 历史课堂反馈."
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE class_commentary_tasks SET status='ready', feedback_text=? WHERE id=?",
                (legacy_feedback, legacy_task["id"]),
            )
        lesson_manager.init_db()
        with lesson_manager.get_conn() as conn:
            legacy_generation = dict(
                conn.execute(
                    "SELECT * FROM class_commentary_generations WHERE task_id=?",
                    (legacy_task["id"],),
                ).fetchone()
            )
        self.assertEqual(legacy_generation["origin"], "legacy_migration")
        self.assertEqual(legacy_generation["snapshot_completeness"], "partial")

        with self.assertRaises(lesson_manager.ClassCommentaryMemoryNotEnabled) as legacy_error:
            self._confirm(
                legacy_feedback,
                "confirmation-request-legacy-learning",
                learn_requested=True,
                task_id=legacy_task["id"],
                generation_id=legacy_generation["id"],
            )
        self.assertEqual(legacy_error.exception.code, "memory_not_enabled")
        self.assertEqual(self._revision_rows(), [])
        self.assertEqual(self._revision_rows(legacy_task["id"]), [])
        self.assertIsNone(self._draft_row())
        self.assertIsNone(self._draft_row(legacy_task["id"], legacy_generation["id"]))


if __name__ == "__main__":
    unittest.main()
