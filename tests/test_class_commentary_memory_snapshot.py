import hashlib
import json
import os
import tempfile
import unittest

import lesson_manager
from class_commentary import CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION


class ClassCommentaryMemorySnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        self.old_enabled = os.environ.get("XR_CLASS_COMMENTARY_MEMORY_ENABLED")
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        os.environ["XR_CLASS_COMMENTARY_MEMORY_ENABLED"] = "true"
        lesson_manager.init_db()
        self.teacher = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class(
            "记忆快照测试班",
            subject="数学",
            grade="七年级",
            organization_id=self.teacher["organization_id"],
            teacher_user_id=self.teacher["id"],
        )
        self.student = lesson_manager.create_student_for_class(self.class_id, "小王")
        self.other_student = lesson_manager.create_student_for_class(self.class_id, "小李")
        self.skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.teacher["organization_id"],
            skill_id="memory-snapshot-teacher",
            actor_user_id=self.teacher["id"],
            source_path="/skills/memory-snapshot-teacher/SKILL.md",
            content="课堂表现和建议都要有证据.",
        )
        self.task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.teacher["id"],
            audio_path="/tmp/memory-snapshot.m4a",
            audio_filename="memory-snapshot.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            self.task["id"], "小王对分式计算更熟练, 验算仍需加强."
        )
        self.roster = [
            {"student_id": self.student["id"], "student_name": self.student["name"]}
        ]
        self.generation = lesson_manager.reserve_class_commentary_generation(
            task_id=self.task["id"],
            generation_request_id="memory-snapshot-generation",
            skill_registry_id=self.skill["registry_id"],
            attending_roster=self.roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-v1",
            prompt_payload={"messages": [{"role": "user", "content": "生成反馈"}]},
            memory_context={"records": [], "rendered_text": ""},
        )
        lesson_manager.complete_class_commentary_generation(
            self.generation["id"], "小王: 分式计算更熟练, 继续练习验算."
        )

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        if self.old_enabled is None:
            os.environ.pop("XR_CLASS_COMMENTARY_MEMORY_ENABLED", None)
        else:
            os.environ["XR_CLASS_COMMENTARY_MEMORY_ENABLED"] = self.old_enabled
        self.tmp.cleanup()

    def _insert_wrong_question(self, record_id, student_id, *, question, topic="分式"):
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO wrong_question_submissions (
                    id, organization_id, class_id, student_id, teacher_user_id,
                    image_url, recognition_status, archive_status, status,
                    question_text, topic_category, primary_error_type,
                    secondary_error_summary, child_reason_core_issue,
                    child_reason_key_omission, child_reason_next_step,
                    knowledge_tags_json, reflection_summary_json,
                    mastery_tracking_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, '/tmp/question.png', 'recognized', 'active',
                        'ready', ?, ?, '计算错误', '通分后符号处理不稳',
                        '负号处理容易遗漏', '没有逐项检查符号', '完成后反向代入验算',
                        '["分式","符号"]', ?, ?, '2026-07-14 10:00:00')
                """,
                (
                    record_id,
                    self.teacher["organization_id"],
                    self.class_id,
                    student_id,
                    self.teacher["id"],
                    question,
                    topic,
                    json.dumps(
                        {"child_reason_next_step": "完成后反向代入验算"},
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "practice_sheet_count": 2,
                            "latest_practice_status": "ready",
                            "followup_count": 1,
                            "latest_followup_outcome": "still_confused",
                            "latest_followup_summary": "负号位置仍会出错",
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

    def _confirm(self, request_id, *, learn=True):
        return lesson_manager.confirm_class_commentary_feedback(
            task_id=self.task["id"],
            generation_id=self.generation["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text="小王: 分式计算更熟练, 每题完成后反向代入验算.",
            learn_requested=learn,
            expected_draft_version=0,
            confirmation_request_id=request_id,
        )

    def _confirm_structured(self, request_id):
        generation = lesson_manager.get_class_commentary_generation(self.generation["id"])
        student_id = int(self.student["id"])
        generated_feedback = "分式计算更熟练, 继续练习验算."
        payload = {
            "schema_version": "class_commentary.student_feedback.v1",
            "items": [
                {"student_id": student_id, "feedback_text": generated_feedback}
            ],
        }
        structured_json = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        structured_hash = hashlib.sha256(structured_json.encode("utf-8")).hexdigest()
        derived_text = f"{self.student['name']}:\n{generated_feedback}"
        scope_hash = lesson_manager.build_class_commentary_eligible_scope_hash(
            transcript_hash=generation["confirmed_transcript_hash"],
            roster_hash=generation["attending_roster_hash"],
            eligible_student_ids=[student_id],
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET feedback_schema_version='class_commentary.student_feedback.v1',
                    structured_feedback_json=?, structured_feedback_hash=?,
                    generated_feedback_text=?, eligible_student_ids_json=?,
                    eligible_student_scope_hash=?,
                    student_mention_matcher_version='class_commentary.student_name_matcher.v1',
                    response_format_json='{"type":"json_object"}',
                    student_history_memory_mode='disabled_v1', prompt_version=?
                WHERE id=?
                """,
                (
                    structured_json,
                    structured_hash,
                    derived_text,
                    json.dumps([student_id], separators=(",", ":")),
                    scope_hash,
                    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
                    generation["id"],
                ),
            )
        self.generation = lesson_manager.get_class_commentary_generation(
            self.generation["id"]
        )
        return lesson_manager.confirm_class_commentary_feedback(
            task_id=self.task["id"],
            generation_id=self.generation["id"],
            teacher_user_id=self.teacher["id"],
            feedback_schema_version="class_commentary.student_feedback.v1",
            student_feedback_items=[
                {
                    "student_id": student_id,
                    "feedback_text": "分式计算更熟练, 每题完成后反向代入验算.",
                }
            ],
            learn_requested=True,
            expected_draft_version=0,
            expected_latest_revision_id=None,
            confirmation_request_id=request_id,
        )

    def test_confirmation_freezes_only_roster_learning_evidence_and_survives_source_change(self):
        self._insert_wrong_question(
            "snapshot-roster", self.student["id"], question="化简 (x^2-1)/(x-1)"
        )
        self._insert_wrong_question(
            "snapshot-outside", self.other_student["id"], question="这条不应进入快照"
        )
        revision = self._confirm("snapshot-confirm-freeze")
        snapshot = json.loads(revision["learning_evidence_snapshot_json"])
        refs = json.loads(revision["learning_evidence_source_refs_json"])
        self.assertEqual(revision["learning_evidence_completeness"], "complete")
        self.assertEqual(snapshot["scope"]["student_ids"], [self.student["id"]])
        self.assertEqual(
            [item["source_id"] for item in snapshot["wrong_questions"]],
            ["snapshot-roster"],
        )
        self.assertEqual(refs[0]["source_id"], "snapshot-roster")
        self.assertIn("source_updated_at", refs[0])
        self.assertIn("source_content_hash", refs[0])
        self.assertNotIn("question_summary", snapshot["wrong_questions"][0])
        self.assertNotIn("化简 (x^2-1)/(x-1)", revision["learning_evidence_snapshot_json"])
        self.assertEqual(snapshot["wrong_questions"][0]["knowledge_tags"], ["分式", "符号"])
        original_hash = revision["learning_evidence_hash"]

        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE wrong_question_submissions SET primary_error_type='已被后来修改' WHERE id='snapshot-roster'"
            )
            conn.execute("DELETE FROM wrong_question_submissions WHERE id='snapshot-outside'")
        frozen = lesson_manager.get_class_commentary_memory_extraction_input(
            revision["memory_job"]["id"]
        )
        self.assertTrue(frozen["integrity_valid"])
        self.assertEqual(
            frozen["learning_evidence_snapshot"]["wrong_questions"][0]["primary_error_type"],
            "计算错误",
        )
        self.assertEqual(frozen["job"]["learning_evidence_hash"], original_hash)

    def test_confirmation_replay_after_source_change_keeps_original_snapshot_and_job(self):
        self._insert_wrong_question(
            "snapshot-idempotent", self.student["id"], question="原始错题摘要"
        )
        first = self._confirm("snapshot-confirm-idempotent")
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE wrong_question_submissions SET topic_category='变化后的摘要' WHERE id='snapshot-idempotent'"
            )
        replay = self._confirm("snapshot-confirm-idempotent")
        self.assertEqual(replay["id"], first["id"])
        self.assertEqual(replay["learning_evidence_hash"], first["learning_evidence_hash"])
        self.assertEqual(
            replay["learning_evidence_snapshot_json"],
            first["learning_evidence_snapshot_json"],
        )
        self.assertEqual(replay["memory_job"]["id"], first["memory_job"]["id"])

    def test_selector_excludes_unreviewed_and_archived_sources_and_caps_each_student_at_twenty(self):
        for index in range(22):
            self._insert_wrong_question(
                f"snapshot-cap-{index:02d}",
                self.student["id"],
                question=f"不会保存的题干 {index}",
                topic=f"专题{index}",
            )
            with lesson_manager.get_conn() as conn:
                conn.execute(
                    "UPDATE wrong_question_submissions SET updated_at=? WHERE id=?",
                    (f"2026-07-14 10:{index:02d}:00", f"snapshot-cap-{index:02d}"),
                )
        self._insert_wrong_question(
            "snapshot-pending", self.student["id"], question="待确认记录"
        )
        self._insert_wrong_question(
            "snapshot-archived", self.student["id"], question="已归档记录"
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE wrong_question_submissions
                SET needs_teacher_confirmation=1, confirmation_status='pending',
                    updated_at='2026-07-14 11:00:00'
                WHERE id='snapshot-pending'
                """
            )
            conn.execute(
                """
                UPDATE wrong_question_submissions
                SET archive_status='archived', updated_at='2026-07-14 11:01:00'
                WHERE id='snapshot-archived'
                """
            )
        revision = self._confirm("snapshot-confirm-selector-cap")
        snapshot = json.loads(revision["learning_evidence_snapshot_json"])
        source_ids = [item["source_id"] for item in snapshot["wrong_questions"]]
        self.assertEqual(len(source_ids), 20)
        self.assertNotIn("snapshot-cap-00", source_ids)
        self.assertNotIn("snapshot-cap-01", source_ids)
        self.assertNotIn("snapshot-pending", source_ids)
        self.assertNotIn("snapshot-archived", source_ids)
        self.assertNotIn("不会保存的题干", revision["learning_evidence_snapshot_json"])

    def test_no_learning_uses_canonical_empty_snapshot_and_creates_no_job(self):
        self._insert_wrong_question(
            "snapshot-no-learn", self.student["id"], question="不学习时不应冻结"
        )
        revision = self._confirm("snapshot-confirm-no-learn", learn=False)
        self.assertEqual(json.loads(revision["learning_evidence_snapshot_json"]), {})
        self.assertEqual(json.loads(revision["learning_evidence_source_refs_json"]), [])
        self.assertEqual(revision["learning_evidence_completeness"], "empty")
        self.assertIsNone(revision["memory_job"])

    def test_tampered_learning_hash_becomes_terminal_integrity_failure(self):
        self._insert_wrong_question(
            "snapshot-tamper", self.student["id"], question="用于完整性检查"
        )
        revision = self._confirm("snapshot-confirm-tamper")
        job_id = revision["memory_job"]["id"]
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE class_commentary_revisions SET learning_evidence_hash='tampered' WHERE id=?",
                (revision["id"],),
            )
        claimed = lesson_manager.claim_class_commentary_memory_extraction_job(
            job_id, claim_owner="integrity-worker"
        )
        self.assertIsNone(claimed)
        job = lesson_manager.get_class_commentary_memory_extraction_job(job_id)
        self.assertEqual(job["status"], "integrity_failed")
        with self.assertRaises(lesson_manager.ClassCommentaryMemoryRevisionNotRetryable):
            lesson_manager.retry_class_commentary_memory_revision(
                revision["id"],
                actor_user_id=self.teacher["id"],
                request_id="retry-integrity-failed",
            )

    def test_tampered_snapshot_content_with_unchanged_hash_is_rejected(self):
        self._insert_wrong_question(
            "snapshot-content-tamper", self.student["id"], question="用于快照内容检查"
        )
        revision = self._confirm("snapshot-confirm-content-tamper")
        job_id = revision["memory_job"]["id"]
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_revisions
                SET learning_evidence_snapshot_json='{"tampered":true}'
                WHERE id=?
                """,
                (revision["id"],),
            )
        frozen = lesson_manager.get_class_commentary_memory_extraction_input(job_id)
        self.assertFalse(frozen["integrity_valid"])
        self.assertIsNone(
            lesson_manager.claim_class_commentary_memory_extraction_job(
                job_id, claim_owner="snapshot-integrity-worker"
            )
        )
        self.assertEqual(
            lesson_manager.get_class_commentary_memory_extraction_job(job_id)["status"],
            "integrity_failed",
        )

    def test_tampered_generation_core_snapshot_is_rejected(self):
        revision = self._confirm("snapshot-confirm-generation-tamper")
        job_id = revision["memory_job"]["id"]
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET confirmed_transcript_snapshot='篡改后的转写'
                WHERE id=?
                """,
                (self.generation["id"],),
            )
        frozen = lesson_manager.get_class_commentary_memory_extraction_input(job_id)
        self.assertFalse(frozen["integrity_valid"])
        self.assertIsNone(
            lesson_manager.claim_class_commentary_memory_extraction_job(
                job_id, claim_owner="generation-integrity-worker"
            )
        )
        self.assertEqual(
            lesson_manager.get_class_commentary_memory_extraction_job(job_id)["status"],
            "integrity_failed",
        )

    def test_structured_extraction_validates_both_envelopes_without_exposing_json(self):
        revision = self._confirm_structured("snapshot-confirm-structured-integrity")
        job_id = int(revision["memory_job"]["id"])
        frozen = lesson_manager.get_class_commentary_memory_extraction_input(job_id)
        self.assertTrue(frozen["integrity_valid"])
        extraction_input = frozen["extraction_input"]
        self.assertEqual(
            extraction_input["final_feedback_text"],
            "小王:\n分式计算更熟练, 每题完成后反向代入验算.",
        )
        extractor_payload = json.dumps(extraction_input, ensure_ascii=False)
        self.assertNotIn("structured_feedback_json", extractor_payload)
        self.assertNotIn("structured_feedback_hash", extractor_payload)
        self.assertNotIn("feedback_schema_version", extractor_payload)
        self.assertNotIn("student_feedback_items", extractor_payload)

        with lesson_manager.get_conn() as conn:
            generation_row = dict(conn.execute(
                "SELECT * FROM class_commentary_generations WHERE id=?",
                (self.generation["id"],),
            ).fetchone())
            revision_row = dict(conn.execute(
                "SELECT * FROM class_commentary_revisions WHERE id=?",
                (revision["id"],),
            ).fetchone())
        original_input_hash = lesson_manager._class_commentary_extraction_input_hash(
            generation_row,
            revision_row,
        )
        changed_revision_identity = dict(revision_row)
        changed_revision_identity["structured_feedback_hash"] = "changed-hash"
        self.assertNotEqual(
            original_input_hash,
            lesson_manager._class_commentary_extraction_input_hash(
                generation_row,
                changed_revision_identity,
            ),
        )

        tamper_cases = (
            (
                "class_commentary_generations",
                self.generation["id"],
                "structured_feedback_json",
                '{"tampered":true}',
                generation_row["structured_feedback_json"],
            ),
            (
                "class_commentary_generations",
                self.generation["id"],
                "structured_feedback_hash",
                "tampered-hash",
                generation_row["structured_feedback_hash"],
            ),
            (
                "class_commentary_generations",
                self.generation["id"],
                "generated_feedback_text",
                "篡改后的 generation derived text",
                generation_row["generated_feedback_text"],
            ),
            (
                "class_commentary_generations",
                self.generation["id"],
                "feedback_schema_version",
                "future.student-feedback.v2",
                generation_row["feedback_schema_version"],
            ),
            (
                "class_commentary_revisions",
                revision["id"],
                "structured_feedback_json",
                '{"tampered":true}',
                revision_row["structured_feedback_json"],
            ),
            (
                "class_commentary_revisions",
                revision["id"],
                "structured_feedback_hash",
                "tampered-hash",
                revision_row["structured_feedback_hash"],
            ),
            (
                "class_commentary_revisions",
                revision["id"],
                "final_feedback_text",
                "篡改后的 revision derived text",
                revision_row["final_feedback_text"],
            ),
            (
                "class_commentary_revisions",
                revision["id"],
                "feedback_schema_version",
                "future.student-feedback.v2",
                revision_row["feedback_schema_version"],
            ),
        )
        for table, row_id, column, tampered_value, original_value in tamper_cases:
            with self.subTest(table=table, column=column):
                with lesson_manager.get_conn() as conn:
                    conn.execute(
                        f"UPDATE {table} SET {column}=? WHERE id=?",
                        (tampered_value, row_id),
                    )
                self.assertFalse(
                    lesson_manager.get_class_commentary_memory_extraction_input(job_id)[
                        "integrity_valid"
                    ]
                )
                with lesson_manager.get_conn() as conn:
                    conn.execute(
                        f"UPDATE {table} SET {column}=? WHERE id=?",
                        (original_value, row_id),
                    )
                self.assertTrue(
                    lesson_manager.get_class_commentary_memory_extraction_input(job_id)[
                        "integrity_valid"
                    ]
                )


if __name__ == "__main__":
    unittest.main()
