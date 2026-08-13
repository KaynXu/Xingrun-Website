import json
import os
import tempfile
import unittest

import config_runtime
import lesson_manager
from class_commentary import (
    CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
)
from class_commentary_feedback_schema import (
    CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
    build_class_commentary_eligible_scope_hash,
    canonicalize_class_commentary_structured_feedback,
    validate_class_commentary_structured_generation_contract,
)
from class_commentary_student_memory_v2 import (
    build_safe_class_context,
    build_student_current_evidence,
    canonical_hash,
    canonical_json,
    content_hash,
)


class ClassCommentaryStudentMemoryV2FloorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        lesson_manager.init_db()
        self.teacher = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class(
            "隔离记忆兼容测试班",
            subject="数学",
            grade="七年级",
            organization_id=self.teacher["organization_id"],
            teacher_user_id=self.teacher["id"],
        )
        self.students = [
            lesson_manager.create_student_for_class(self.class_id, "学生甲"),
            lesson_manager.create_student_for_class(self.class_id, "学生乙"),
        ]
        self.task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.teacher["id"],
            audio_path="/tmp/student-memory-v2-floor.m4a",
            audio_filename="student-memory-v2-floor.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            self.task["id"],
            "学生甲今天计算稳定. 学生乙需要检查符号.",
        )
        self.skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.teacher["organization_id"],
            skill_id="student-memory-v2-floor",
            actor_user_id=self.teacher["id"],
            source_path="/tmp/student-memory-v2-floor.skill",
            content="先肯定, 再给一个行动建议.",
        )
        lesson_manager.insert_credit_ledger_entry(
            organization_id=self.teacher["organization_id"],
            direction="credit",
            amount=10,
            source_type="manual_adjustment",
            source_id="student-memory-v2-floor",
            note="test credits",
            operator_user_id=self.teacher["id"],
        )
        self.generation = self._insert_legacy_isolated_v2_generation()

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        self.tmp.cleanup()

    def _insert_legacy_isolated_v2_generation(self):
        transcript = "学生甲今天计算稳定. 学生乙需要检查符号."
        transcript_hash = content_hash(transcript)
        roster = [
            {"student_id": item["id"], "student_name": item["name"]}
            for item in self.students
        ]
        roster_json = canonical_json(roster)
        roster_hash = content_hash(roster_json)
        eligible_ids = [item["student_id"] for item in roster]
        scope_hash = build_class_commentary_eligible_scope_hash(
            transcript_hash=transcript_hash,
            roster_hash=roster_hash,
            eligible_student_ids=eligible_ids,
            matcher_version=CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
        )
        model_parameters = {"temperature": 0.55}
        model_parameters_json = canonical_json(model_parameters)
        empty_json = canonical_json({})
        empty_hash = content_hash(empty_json)
        skill_content = "先肯定, 再给一个行动建议."
        class_context_json = canonical_json(
            build_safe_class_context(
                class_record={"id": self.class_id},
                subject_key="math",
            )
        )
        class_context_hash = content_hash(class_context_json)
        with lesson_manager.get_conn() as conn:
            task = conn.execute(
                "SELECT * FROM class_commentary_tasks WHERE id=?",
                (self.task["id"],),
            ).fetchone()
            cursor = conn.execute(
                """
                INSERT INTO class_commentary_generations (
                    organization_id, task_id, generation_no,
                    generation_request_id, generation_request_payload_hash,
                    teacher_user_id, class_id, subject_key,
                    confirmed_transcript_version, confirmed_transcript_snapshot,
                    confirmed_transcript_hash, attending_roster_snapshot_json,
                    attending_roster_hash, attending_roster_explicit,
                    skill_registry_id, skill_id, skill_version_id,
                    skill_content_snapshot, skill_content_hash,
                    model_provider, model_name, model_parameters_json,
                    prompt_version, prompt_payload_snapshot_json,
                    prompt_payload_hash, memory_context_snapshot_json,
                    memory_context_hash, execution_snapshot_status,
                    execution_snapshot_finalized_at, feedback_schema_version,
                    eligible_student_ids_json, eligible_student_scope_hash,
                    student_mention_matcher_version, response_format_json,
                    student_history_memory_mode, generated_feedback_text,
                    origin, snapshot_completeness, missing_snapshot_fields_json,
                    status
                ) VALUES (?, ?, 1, ?, ?, ?, ?, 'math', ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?,
                          'openai', 'test-model', ?, ?, ?, ?, ?, ?, 'ready',
                          strftime('%Y-%m-%dT%H:%M:%fZ','now'), ?, ?, ?, ?, ?, ?, '',
                          'runtime', 'complete', '[]', 'generating')
                """,
                (
                    self.teacher["organization_id"],
                    self.task["id"],
                    "student-memory-v2-floor",
                    content_hash("student-memory-v2-floor-payload"),
                    self.teacher["id"],
                    self.class_id,
                    int(task["confirmed_transcript_version"]),
                    transcript,
                    transcript_hash,
                    roster_json,
                    roster_hash,
                    self.skill["registry_id"],
                    "student-memory-v2-floor",
                    self.skill["active_version_id"],
                    skill_content,
                    content_hash(skill_content),
                    model_parameters_json,
                    CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
                    empty_json,
                    empty_hash,
                    empty_json,
                    empty_hash,
                    "class_commentary.student_feedback.v1",
                    canonical_json(eligible_ids),
                    scope_hash,
                    CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
                    canonical_json({"type": "json_object"}),
                    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
                ),
            )
            generation_id = int(cursor.lastrowid)
            conn.execute(
                """
                UPDATE class_commentary_tasks
                SET generation_seq=1, latest_generation_id=?, status='generating',
                    generation_request_key='student-memory-v2-floor'
                WHERE id=?
                """,
                (generation_id, self.task["id"]),
            )
            for roster_item in roster:
                student_id = int(roster_item["student_id"])
                evidence = build_student_current_evidence(
                    transcript=transcript,
                    transcript_hash=transcript_hash,
                    roster=roster,
                    target_student_id=student_id,
                    matcher_version=CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
                )
                evidence_hash = str(evidence.pop("snapshot_hash"))
                run_payload_hash = canonical_hash(
                    {"generation_id": generation_id, "student_id": student_id}
                )
                request_id = f"student-memory-v2-floor:student:{student_id}"
                charge_key = content_hash(f"floor:{request_id}:{run_payload_hash}")
                run_cursor = conn.execute(
                    """
                    INSERT INTO class_commentary_student_generation_runs (
                        organization_id, generation_id, student_id,
                        student_name_snapshot, request_id, request_payload_hash,
                        prompt_version, memory_mode, eligible_student_ids_json,
                        eligible_student_scope_hash, student_mention_matcher_version,
                        class_context_snapshot_json, class_context_hash,
                        current_evidence_snapshot_json, current_evidence_hash,
                        memory_context_snapshot_json, memory_context_hash,
                        provider, model, model_parameters_json,
                        prompt_payload_snapshot_json, prompt_payload_hash,
                        charge_request_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                              'openai', 'test-model', ?, ?, ?, ?)
                    """,
                    (
                        self.teacher["organization_id"],
                        generation_id,
                        student_id,
                        roster_item["student_name"],
                        request_id,
                        run_payload_hash,
                        CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
                        CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
                        canonical_json(eligible_ids),
                        scope_hash,
                        CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
                        class_context_json,
                        class_context_hash,
                        canonical_json(evidence),
                        evidence_hash,
                        empty_json,
                        empty_hash,
                        model_parameters_json,
                        empty_json,
                        empty_hash,
                        charge_key,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO class_commentary_student_generation_credit_holds (
                        student_run_id, organization_id, amount,
                        request_id, request_payload_hash
                    ) VALUES (?, ?, 1, ?, ?)
                    """,
                    (
                        int(run_cursor.lastrowid),
                        self.teacher["organization_id"],
                        charge_key,
                        run_payload_hash,
                    ),
                )
        return lesson_manager.get_class_commentary_generation(generation_id)

    def test_kill_switch_defaults_off(self):
        self.assertFalse(
            config_runtime.DEFAULTS["class_commentary_student_memory_v2_enabled"]
        )

    def test_forward_schema_and_progress_are_available(self):
        with lesson_manager.get_conn() as conn:
            columns = {
                row["name"]
                for row in conn.execute(
                    "PRAGMA table_info(class_commentary_student_generation_runs)"
                ).fetchall()
            }
            self.assertTrue(
                {
                    "generation_id",
                    "student_id",
                    "request_id",
                    "request_payload_hash",
                    "memory_context_snapshot_json",
                    "charge_request_key",
                    "response_snapshot_json",
                    "structured_feedback_hash",
                    "attempt_count",
                }.issubset(columns)
            )
        progress = lesson_manager.get_class_commentary_student_generation_progress(
            self.generation["id"]
        )
        self.assertEqual(progress["total"], len(self.students))
        self.assertEqual(progress["queued"], len(self.students))
        self.assertNotIn("prompt_payload_snapshot_json", progress["runs"][0])
        self.assertNotIn("memory_context_snapshot_json", progress["runs"][0])

    def test_isolated_result_remains_readable(self):
        validate_class_commentary_structured_generation_contract(self.generation)
        payload = {
            "schema_version": "class_commentary.student_feedback.v1",
            "items": [
                {"student_id": item["id"], "feedback_text": f"{item['name']}, 继续保持."}
                for item in self.students
            ],
        }
        canonical = canonicalize_class_commentary_structured_feedback(
            structured_feedback=json.dumps(payload, ensure_ascii=False),
            generation=self.generation,
        )
        self.assertEqual(
            [item["student_id"] for item in canonical["student_feedback_items"]],
            [item["id"] for item in self.students],
        )


if __name__ == "__main__":
    unittest.main()
