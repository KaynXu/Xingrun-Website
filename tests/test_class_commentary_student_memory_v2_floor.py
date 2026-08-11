import hashlib
import json
import os
import tempfile
import unittest

import config_runtime
import lesson_manager
from class_commentary import (
    CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3,
)
from class_commentary_feedback_schema import (
    CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V1,
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
    build_class_commentary_eligible_scope_hash,
    canonicalize_class_commentary_structured_feedback,
    validate_class_commentary_structured_generation_contract,
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
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.teacher["id"],
            audio_path="/tmp/student-memory-v2-floor.m4a",
            audio_filename="student-memory-v2-floor.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            "学生甲今天计算稳定. 学生乙需要检查符号.",
        )
        skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.teacher["organization_id"],
            skill_id="student-memory-v2-floor",
            actor_user_id=self.teacher["id"],
            source_path="/tmp/student-memory-v2-floor.skill",
            content="先肯定, 再给一个行动建议.",
        )
        roster = [
            {"student_id": item["id"], "student_name": item["name"]}
            for item in self.students
        ]
        self.generation = lesson_manager.reserve_class_commentary_generation(
            task_id=task["id"],
            generation_request_id="student-memory-v2-floor",
            skill_registry_id=skill["registry_id"],
            attending_roster=roster,
            model_provider="openai",
            model_name="test-model",
            model_parameters={"temperature": 0.55},
            prompt_version=CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3,
            attending_roster_explicit=True,
            structured_feedback_enabled=True,
        )
        eligible_ids = [item["id"] for item in self.students]
        scope_hash = build_class_commentary_eligible_scope_hash(
            transcript_hash=self.generation["confirmed_transcript_hash"],
            roster_hash=self.generation["attending_roster_hash"],
            eligible_student_ids=eligible_ids,
            matcher_version=CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V1,
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET prompt_version=?, student_mention_matcher_version=?,
                    student_history_memory_mode=?, eligible_student_scope_hash=?
                WHERE id=?
                """,
                (
                    CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
                    CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V1,
                    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
                    scope_hash,
                    self.generation["id"],
                ),
            )
        self.generation = lesson_manager.get_class_commentary_generation(
            self.generation["id"]
        )

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        self.tmp.cleanup()

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
            empty_hash = hashlib.sha256(b"{}").hexdigest()
            conn.execute(
                """
                INSERT INTO class_commentary_student_generation_runs (
                    organization_id, generation_id, student_id,
                    student_name_snapshot, request_id, request_payload_hash,
                    prompt_version, memory_mode,
                    current_evidence_snapshot_json, current_evidence_hash,
                    memory_context_snapshot_json, memory_context_hash,
                    provider, model, model_parameters_json,
                    prompt_payload_snapshot_json, prompt_payload_hash,
                    charge_request_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, '{}', ?, ?, ?, '{}', '{}', ?, ?)
                """,
                (
                    self.teacher["organization_id"],
                    self.generation["id"],
                    self.students[0]["id"],
                    self.students[0]["name"],
                    "run-request-1",
                    "request-hash-1",
                    CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
                    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
                    empty_hash,
                    empty_hash,
                    "openai",
                    "test-model",
                    empty_hash,
                    "charge-key-1",
                ),
            )
        progress = lesson_manager.get_class_commentary_student_generation_progress(
            self.generation["id"]
        )
        self.assertEqual(progress["total"], 1)
        self.assertEqual(progress["queued"], 1)
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
