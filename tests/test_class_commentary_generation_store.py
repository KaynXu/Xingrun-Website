import copy
import hashlib
import json
import os
import tempfile
import unittest

import lesson_manager
from class_commentary import (
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3,
    CLASS_COMMENTARY_TEMPERATURE,
    build_class_commentary_chat_request,
)


STRUCTURED_SCHEMA_VERSION = "class_commentary.student_feedback.v1"
STRUCTURED_MATCHER_VERSION = "class_commentary.student_name_matcher.v1"
STRUCTURED_ATTENDING_SCOPE_VERSION = "class_commentary.attending_roster_scope.v1"
STRUCTURED_PROMPT_VERSION = CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION
STRUCTURED_PROMPT_VERSION_V2 = CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2
STRUCTURED_PROMPT_VERSION_V3 = CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3
STRUCTURED_RESPONSE_FORMAT = {"type": "json_object"}
STRUCTURED_MEMORY_MODE = "disabled_v1"
STRUCTURED_MODEL_PARAMETERS = {"temperature": CLASS_COMMENTARY_TEMPERATURE}


class ClassCommentaryGenerationStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        lesson_manager.init_db()

        self.teacher = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class(
            "课堂点评生成测试班",
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
        self.transcript = "小王计算更稳了, 小李需要继续练习验算."
        self.task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.teacher["id"],
            audio_path="/tmp/class-commentary-generation.m4a",
            audio_filename="class-commentary-generation.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            self.task["id"],
            self.transcript,
        )

        self.skill_content = "先写学生本次表现, 再给一条可执行建议."
        imported = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.teacher["organization_id"],
            skill_id="generation-store-teacher",
            actor_user_id=self.teacher["id"],
            source_path="/skills/generation-store-teacher/SKILL.md",
            content=self.skill_content,
        )
        self.skill_registry_id = imported["registry_id"]
        self.skill_version_id = imported["active_version_id"]
        self.model_parameters = {"temperature": 0.2, "top_p": 0.9}
        self.prompt_payload = {
            "messages": [
                {"role": "system", "content": "按课堂点评规范生成反馈."},
                {"role": "user", "content": self.transcript},
            ],
            "response_format": "text",
        }
        self.memory_context = {
            "records": [
                {
                    "memory_id": "mem-1",
                    "scope": "student",
                    "student_id": first_student["id"],
                    "text": "上次建议加强验算.",
                }
            ],
            "rendered_text": "历史参考: 上次建议加强验算.",
        }

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        self.tmp.cleanup()

    @staticmethod
    def _canonical_json(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _hash_json(cls, value):
        return hashlib.sha256(cls._canonical_json(value).encode("utf-8")).hexdigest()

    def _reserve(
        self,
        request_id,
        attending_roster=None,
        *,
        attending_roster_explicit=True,
    ):
        return lesson_manager.reserve_class_commentary_generation(
            task_id=self.task["id"],
            generation_request_id=request_id,
            skill_registry_id=self.skill_registry_id,
            attending_roster=self.roster if attending_roster is None else attending_roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters=self.model_parameters,
            prompt_version="class-commentary-v1",
            prompt_payload=self.prompt_payload,
            memory_context=self.memory_context,
            attending_roster_explicit=attending_roster_explicit,
        )

    def _reserve_structured(self, request_id, attending_roster=None):
        selected_roster = self.roster if attending_roster is None else attending_roster
        structured_memory = {
            "records": [],
            "rendered_text": "",
            "student_history_memories": [],
            "teacher_style_memories": [],
            "student_history_memory_mode": STRUCTURED_MEMORY_MODE,
        }
        structured_prompt = build_class_commentary_chat_request(
            class_record=lesson_manager.get_class(self.class_id),
            students=[
                {"id": item["student_id"], "name": item["student_name"]}
                for item in selected_roster
            ],
            transcript_text=lesson_manager.get_class_commentary_task(
                self.task["id"]
            )["confirmed_transcript_text"],
            skill={
                "id": "generation-store-teacher",
                "name": "",
                "content": self.skill_content,
            },
            teacher_style_memories=[],
            student_history_memories=[],
            feedback_schema_version=STRUCTURED_SCHEMA_VERSION,
            eligible_student_ids=[item["student_id"] for item in selected_roster],
            prompt_version=STRUCTURED_PROMPT_VERSION,
            response_format=copy.deepcopy(STRUCTURED_RESPONSE_FORMAT),
            student_history_memory_mode=STRUCTURED_MEMORY_MODE,
        )
        return lesson_manager.reserve_class_commentary_generation(
            task_id=self.task["id"],
            generation_request_id=request_id,
            skill_registry_id=self.skill_registry_id,
            attending_roster=(
                self.roster if attending_roster is None else attending_roster
            ),
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters=STRUCTURED_MODEL_PARAMETERS,
            prompt_version=STRUCTURED_PROMPT_VERSION,
            prompt_payload=structured_prompt,
            memory_context=structured_memory,
            structured_feedback_enabled=True,
        )

    def _generation_count(self):
        with lesson_manager.get_conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM class_commentary_generations WHERE task_id=?",
                (self.task["id"],),
            ).fetchone()[0]

    def test_reservation_freezes_complete_snapshots_and_moves_task_pointer(self):
        expected_roster = copy.deepcopy(self.roster)
        expected_prompt_payload = copy.deepcopy(self.prompt_payload)
        expected_memory_context = copy.deepcopy(self.memory_context)

        reserved = self._reserve("generation-request-1")
        task_after_reservation = lesson_manager.get_class_commentary_task(self.task["id"])

        self.assertEqual(reserved["generation_no"], 1)
        self.assertEqual(task_after_reservation["generation_seq"], 1)
        self.assertEqual(task_after_reservation["latest_generation_id"], reserved["id"])
        self.assertEqual(task_after_reservation["status"], "generating")

        self.roster[0]["student_name"] = "被调用方修改的姓名"
        self.prompt_payload["messages"][0]["content"] = "被调用方修改的 prompt"
        self.memory_context["rendered_text"] = "被调用方修改的 memory"
        lesson_manager.save_class_commentary_transcript(self.task["id"], "后来修改的转写")

        saved = lesson_manager.get_class_commentary_generation(reserved["id"])
        with lesson_manager.get_conn() as conn:
            row = dict(
                conn.execute(
                    "SELECT * FROM class_commentary_generations WHERE id=?",
                    (reserved["id"],),
                ).fetchone()
            )

        self.assertEqual(saved["id"], reserved["id"])
        self.assertEqual(row["organization_id"], self.teacher["organization_id"])
        self.assertEqual(row["teacher_user_id"], self.teacher["id"])
        self.assertEqual(row["class_id"], self.class_id)
        self.assertEqual(row["subject_key"], "math")
        self.assertEqual(row["confirmed_transcript_version"], 1)
        self.assertEqual(row["confirmed_transcript_snapshot"], self.transcript)
        self.assertEqual(
            row["confirmed_transcript_hash"],
            hashlib.sha256(self.transcript.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(row["attending_roster_snapshot_json"], self._canonical_json(expected_roster))
        self.assertEqual(row["attending_roster_hash"], self._hash_json(expected_roster))
        self.assertEqual(row["attending_roster_explicit"], 1)
        self.assertEqual(row["skill_registry_id"], self.skill_registry_id)
        self.assertEqual(row["skill_id"], "generation-store-teacher")
        self.assertEqual(row["skill_version_id"], self.skill_version_id)
        self.assertEqual(row["skill_content_snapshot"], self.skill_content)
        self.assertEqual(
            row["skill_content_hash"],
            hashlib.sha256(self.skill_content.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(row["model_provider"], "deepseek")
        self.assertEqual(row["model_name"], "deepseek-chat")
        self.assertEqual(row["model_parameters_json"], self._canonical_json(self.model_parameters))
        self.assertEqual(row["prompt_version"], "class-commentary-v1")
        self.assertEqual(row["prompt_payload_snapshot_json"], self._canonical_json(expected_prompt_payload))
        self.assertEqual(row["prompt_payload_hash"], self._hash_json(expected_prompt_payload))
        self.assertEqual(row["memory_context_snapshot_json"], self._canonical_json(expected_memory_context))
        self.assertEqual(row["memory_context_hash"], self._hash_json(expected_memory_context))
        self.assertRegex(row["generation_request_payload_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(row["origin"], "runtime")
        self.assertEqual(row["snapshot_completeness"], "complete")
        self.assertEqual(json.loads(row["missing_snapshot_fields_json"]), [])
        self.assertEqual(row["status"], "generating")
        self.assertEqual(row["generated_feedback_text"], "")

    def test_structured_reservation_freezes_contract_hashes_in_requested_roster_order(self):
        expected_roster = list(reversed(copy.deepcopy(self.roster)))
        expected_eligible_ids = [item["student_id"] for item in expected_roster]
        expected_roster_hash = self._hash_json(expected_roster)
        expected_transcript_hash = hashlib.sha256(
            self.transcript.encode("utf-8")
        ).hexdigest()
        expected_scope_hash = self._hash_json(
            {
                "attending_roster_hash": expected_roster_hash,
                "confirmed_transcript_hash": expected_transcript_hash,
                "eligible_student_ids": expected_eligible_ids,
                "student_mention_matcher_version": STRUCTURED_MATCHER_VERSION,
            }
        )
        expected_request_hash = self._hash_json(
            {
                "attending_student_ids": expected_eligible_ids,
                "attending_roster_explicit": True,
                "confirmed_transcript_hash": expected_transcript_hash,
                "confirmed_transcript_version": 1,
                "credit_hold_amount_per_student": 0,
                "eligible_student_ids": expected_eligible_ids,
                "eligible_student_scope_hash": expected_scope_hash,
                "feedback_schema_version": STRUCTURED_SCHEMA_VERSION,
                "model_name": "deepseek-chat",
                "model_parameters": STRUCTURED_MODEL_PARAMETERS,
                "model_provider": "deepseek",
                "prompt_version": STRUCTURED_PROMPT_VERSION,
                "response_format": STRUCTURED_RESPONSE_FORMAT,
                "skill_registry_id": self.skill_registry_id,
                "skill_version_id": self.skill_version_id,
                "student_history_memory_mode": STRUCTURED_MEMORY_MODE,
                "student_mention_matcher_version": STRUCTURED_MATCHER_VERSION,
                "subject_key": "math",
                "task_id": self.task["id"],
            }
        )

        reserved = self._reserve_structured(
            "generation-request-structured-contract",
            attending_roster=expected_roster,
        )

        with lesson_manager.get_conn() as conn:
            row = dict(
                conn.execute(
                    "SELECT * FROM class_commentary_generations WHERE id=?",
                    (reserved["id"],),
                ).fetchone()
            )
        self.assertEqual(
            row["attending_roster_snapshot_json"],
            self._canonical_json(expected_roster),
        )
        self.assertEqual(row["attending_roster_hash"], expected_roster_hash)
        self.assertEqual(row["feedback_schema_version"], STRUCTURED_SCHEMA_VERSION)
        self.assertEqual(
            json.loads(row["eligible_student_ids_json"]),
            expected_eligible_ids,
        )
        self.assertEqual(row["eligible_student_scope_hash"], expected_scope_hash)
        self.assertEqual(
            row["student_mention_matcher_version"],
            STRUCTURED_MATCHER_VERSION,
        )
        self.assertEqual(
            row["response_format_json"],
            self._canonical_json(STRUCTURED_RESPONSE_FORMAT),
        )
        self.assertEqual(
            row["student_history_memory_mode"],
            STRUCTURED_MEMORY_MODE,
        )
        self.assertEqual(row["generation_request_payload_hash"], expected_request_hash)

    def test_structured_reservation_replay_ignores_later_capability_change(self):
        first = self._reserve_structured(
            "generation-request-structured-capability-freeze"
        )

        repeated = lesson_manager.reserve_class_commentary_generation(
            task_id=self.task["id"],
            generation_request_id="generation-request-structured-capability-freeze",
            skill_registry_id=self.skill_registry_id,
            attending_roster=copy.deepcopy(self.roster),
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters=self.model_parameters,
            prompt_version="class-commentary-v1",
            structured_feedback_enabled=False,
        )

        self.assertEqual(repeated["id"], first["id"])
        self.assertTrue(repeated["is_idempotent"])
        self.assertEqual(
            repeated["feedback_schema_version"],
            STRUCTURED_SCHEMA_VERSION,
        )
        self.assertEqual(
            json.loads(repeated["response_format_json"]),
            STRUCTURED_RESPONSE_FORMAT,
        )
        self.assertEqual(
            repeated["student_history_memory_mode"],
            STRUCTURED_MEMORY_MODE,
        )

    def test_structured_v3_reservation_uses_complete_roster_for_asr_name_variants(self):
        asr_transcript = "小汪计算更稳了, 小黎需要继续练习验算."
        lesson_manager.save_class_commentary_transcript(
            self.task["id"],
            asr_transcript,
        )

        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=self.task["id"],
            generation_request_id="generation-request-v3-asr-names",
            skill_registry_id=self.skill_registry_id,
            attending_roster=self.roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters=STRUCTURED_MODEL_PARAMETERS,
            prompt_version=STRUCTURED_PROMPT_VERSION_V3,
            structured_feedback_enabled=True,
        )

        expected_ids = [item["student_id"] for item in self.roster]
        self.assertEqual(
            json.loads(generation["eligible_student_ids_json"]),
            expected_ids,
        )
        self.assertEqual(
            generation["student_mention_matcher_version"],
            STRUCTURED_ATTENDING_SCOPE_VERSION,
        )
        self.assertEqual(
            generation["prompt_version"],
            STRUCTURED_PROMPT_VERSION_V3,
        )
        self.assertEqual(generation["attending_roster_explicit"], 1)
        self.assertEqual(generation["execution_snapshot_status"], "pending")

        structured_memory = {
            "records": [],
            "rendered_text": "",
            "student_history_memories": [],
            "teacher_style_memories": [],
            "student_history_memory_mode": STRUCTURED_MEMORY_MODE,
        }
        structured_prompt = build_class_commentary_chat_request(
            class_record=lesson_manager.get_class(self.class_id),
            students=[
                {"id": item["student_id"], "name": item["student_name"]}
                for item in self.roster
            ],
            transcript_text=asr_transcript,
            skill={
                "id": "generation-store-teacher",
                "name": "",
                "content": self.skill_content,
            },
            teacher_style_memories=[],
            student_history_memories=[],
            feedback_schema_version=STRUCTURED_SCHEMA_VERSION,
            eligible_student_ids=expected_ids,
            prompt_version=STRUCTURED_PROMPT_VERSION_V3,
            response_format=copy.deepcopy(STRUCTURED_RESPONSE_FORMAT),
            student_history_memory_mode=STRUCTURED_MEMORY_MODE,
        )
        finalized = (
            lesson_manager.finalize_class_commentary_generation_execution_snapshot(
                generation["id"],
                prompt_payload=structured_prompt,
                memory_context=structured_memory,
            )
        )
        self.assertEqual(finalized["execution_snapshot_status"], "ready")

    def test_structured_v2_reservation_requires_explicit_attendance(self):
        count_before = self._generation_count()
        task_before = lesson_manager.get_class_commentary_task(self.task["id"])

        with self.assertRaisesRegex(ValueError, "scope must be explicit"):
            lesson_manager.reserve_class_commentary_generation(
                task_id=self.task["id"],
                generation_request_id="generation-request-v2-implicit-attendance",
                skill_registry_id=self.skill_registry_id,
                attending_roster=self.roster,
                model_provider="deepseek",
                model_name="deepseek-chat",
                model_parameters=STRUCTURED_MODEL_PARAMETERS,
                prompt_version=STRUCTURED_PROMPT_VERSION_V2,
                attending_roster_explicit=False,
                structured_feedback_enabled=True,
            )

        self.assertEqual(self._generation_count(), count_before)
        self.assertEqual(
            lesson_manager.get_class_commentary_task(self.task["id"]),
            task_before,
        )

    def test_structured_reservation_scope_failures_do_not_insert_or_mutate_task(self):
        lesson_manager.save_class_commentary_transcript(
            self.task["id"],
            "今天没有点到任何学生姓名.",
        )
        task_before_no_eligible = lesson_manager.get_class_commentary_task(
            self.task["id"]
        )
        count_before_no_eligible = self._generation_count()

        with self.assertRaises(lesson_manager.ClassCommentaryStudentScopeError) as caught:
            self._reserve_structured("generation-request-no-eligible")

        self.assertEqual(caught.exception.code, "student_feedback_no_eligible_students")
        self.assertEqual(self._generation_count(), count_before_no_eligible)
        self.assertEqual(
            lesson_manager.get_class_commentary_task(self.task["id"]),
            task_before_no_eligible,
        )

        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE students SET name=? WHERE id=?",
                ("Ａ 同学", self.roster[0]["student_id"]),
            )
            conn.execute(
                "UPDATE students SET name=? WHERE id=?",
                ("A 同学", self.roster[1]["student_id"]),
            )
        lesson_manager.save_class_commentary_transcript(
            self.task["id"],
            "A 同学今天回答了问题.",
        )
        task_before_ambiguous = lesson_manager.get_class_commentary_task(
            self.task["id"]
        )
        count_before_ambiguous = self._generation_count()

        with self.assertRaises(lesson_manager.ClassCommentaryStudentScopeError) as caught:
            self._reserve_structured("generation-request-ambiguous")

        self.assertEqual(caught.exception.code, "student_roster_name_ambiguous")
        self.assertEqual(self._generation_count(), count_before_ambiguous)
        self.assertEqual(
            lesson_manager.get_class_commentary_task(self.task["id"]),
            task_before_ambiguous,
        )

    def test_structured_completion_canonicalizes_roster_order_and_updates_task_atomically(self):
        generation = self._reserve_structured("generation-request-structured-complete")
        first_student_id = self.roster[0]["student_id"]
        second_student_id = self.roster[1]["student_id"]
        model_output = {
            "schema_version": STRUCTURED_SCHEMA_VERSION,
            "items": [
                {
                    "student_id": second_student_id,
                    "feedback_text": "验算步骤更完整.",
                },
                {
                    "student_id": first_student_id,
                    "feedback_text": "计算过程更稳定.",
                },
            ],
        }
        expected_envelope = {
            "schema_version": STRUCTURED_SCHEMA_VERSION,
            "items": [
                {
                    "student_id": first_student_id,
                    "feedback_text": "计算过程更稳定.",
                },
                {
                    "student_id": second_student_id,
                    "feedback_text": "验算步骤更完整.",
                },
            ],
        }
        expected_json = self._canonical_json(expected_envelope)
        expected_text = "小王:\n计算过程更稳定.\n\n小李:\n验算步骤更完整."

        completed = lesson_manager.complete_class_commentary_generation(
            generation["id"],
            json.dumps(model_output, ensure_ascii=False),
        )
        task = lesson_manager.get_class_commentary_task(self.task["id"])

        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(completed["feedback_schema_version"], STRUCTURED_SCHEMA_VERSION)
        self.assertEqual(completed["structured_feedback_json"], expected_json)
        self.assertEqual(completed["structured_feedback_hash"], self._hash_json(expected_envelope))
        self.assertEqual(completed["generated_feedback_text"], expected_text)
        self.assertEqual(task["latest_generation_id"], generation["id"])
        self.assertEqual(task["status"], "ready")
        self.assertEqual(task["feedback_text"], expected_text)
        self.assertEqual(task["generation_error"], "")

    def test_invalid_structured_completion_does_not_write_partial_generation_or_task_state(self):
        generation = self._reserve_structured("generation-request-structured-invalid")
        generation_before = lesson_manager.get_class_commentary_generation(
            generation["id"]
        )
        task_before = lesson_manager.get_class_commentary_task(self.task["id"])
        incomplete_output = {
            "schema_version": STRUCTURED_SCHEMA_VERSION,
            "items": [
                {
                    "student_id": self.roster[0]["student_id"],
                    "feedback_text": "计算过程更稳定.",
                }
            ],
        }

        with self.assertRaises(
            lesson_manager.ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            lesson_manager.complete_class_commentary_generation(
                generation["id"],
                json.dumps(incomplete_output, ensure_ascii=False),
            )

        self.assertEqual(caught.exception.code, "student_feedback_coverage_mismatch")
        self.assertEqual(
            lesson_manager.get_class_commentary_generation(generation["id"]),
            generation_before,
        )
        self.assertEqual(
            lesson_manager.get_class_commentary_task(self.task["id"]),
            task_before,
        )

    def test_aggregate_limit_failure_does_not_write_partial_generation_or_task_state(self):
        for index in range(3, 17):
            lesson_manager.create_student_for_class(
                self.class_id,
                f"扩展学生{index:02d}",
            )
        roster = [
            {"student_id": student["id"], "student_name": student["name"]}
            for student in lesson_manager.list_students_for_class(self.class_id)
        ]
        lesson_manager.save_class_commentary_transcript(
            self.task["id"],
            " ".join(item["student_name"] for item in roster),
        )
        generation = self._reserve_structured(
            "generation-request-structured-total-limit",
            attending_roster=roster,
        )
        generation_before = lesson_manager.get_class_commentary_generation(
            generation["id"]
        )
        task_before = lesson_manager.get_class_commentary_task(self.task["id"])
        oversized_output = {
            "schema_version": STRUCTURED_SCHEMA_VERSION,
            "items": [
                {
                    "student_id": item["student_id"],
                    "feedback_text": "a" * 1999,
                }
                for item in roster
            ],
        }

        with self.assertRaises(
            lesson_manager.ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            lesson_manager.complete_class_commentary_generation(
                generation["id"],
                json.dumps(oversized_output, ensure_ascii=False),
            )

        self.assertEqual(caught.exception.code, "student_feedback_too_long")
        self.assertEqual(caught.exception.limit, 30000)
        self.assertEqual(
            lesson_manager.get_class_commentary_generation(generation["id"]),
            generation_before,
        )
        self.assertEqual(
            lesson_manager.get_class_commentary_task(self.task["id"]),
            task_before,
        )

    def test_same_request_is_idempotent_and_changed_roster_conflicts(self):
        first = self._reserve("generation-request-idempotent")
        repeated = self._reserve(
            "generation-request-idempotent",
            attending_roster=copy.deepcopy(self.roster),
        )

        self.assertEqual(repeated["id"], first["id"])
        self.assertEqual(
            lesson_manager.get_class_commentary_generation(first["id"])["id"],
            first["id"],
        )
        with self.assertRaises(lesson_manager.ClassCommentaryGenerationRequestConflict):
            self._reserve(
                "generation-request-idempotent",
                attending_roster=[copy.deepcopy(self.roster[0])],
            )

        task = lesson_manager.get_class_commentary_task(self.task["id"])
        with lesson_manager.get_conn() as conn:
            generation_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_generations WHERE task_id=?",
                (self.task["id"],),
            ).fetchone()[0]
        self.assertEqual(generation_count, 1)
        self.assertEqual(task["generation_seq"], 1)
        self.assertEqual(task["latest_generation_id"], first["id"])

    def test_implicit_roster_replay_ignores_later_live_roster_changes(self):
        first = self._reserve(
            "generation-request-implicit-roster",
            attending_roster_explicit=False,
        )
        lesson_manager.create_student_for_class(self.class_id, "后来加入的学生")
        changed_roster = [
            {"student_id": student["id"], "student_name": student["name"]}
            for student in lesson_manager.list_students_for_class(self.class_id)
        ]

        repeated = self._reserve(
            "generation-request-implicit-roster",
            attending_roster=changed_roster,
            attending_roster_explicit=False,
        )

        self.assertEqual(repeated["id"], first["id"])
        self.assertTrue(repeated["is_idempotent"])
        self.assertEqual(self._generation_count(), 1)

    def test_plain_reservation_keeps_legacy_student_id_roster_order(self):
        reversed_roster = list(reversed(self.roster))

        generation = self._reserve(
            "generation-request-plain-roster-order",
            attending_roster=reversed_roster,
        )

        frozen_roster = json.loads(generation["attending_roster_snapshot_json"])
        self.assertEqual(
            [item["student_id"] for item in frozen_roster],
            sorted(item["student_id"] for item in reversed_roster),
        )

    def test_same_request_ignores_later_prompt_and_memory_results(self):
        original_prompt = copy.deepcopy(self.prompt_payload)
        original_memory = copy.deepcopy(self.memory_context)
        first = self._reserve("generation-request-frozen-base-input")

        self.prompt_payload["messages"][1]["content"] = "后来重新组装的 prompt"
        self.memory_context = {
            "records": [{"memory_id": "mem-later", "text": "后来检索到的记忆"}],
            "rendered_text": "后来检索到的记忆",
        }

        repeated = self._reserve("generation-request-frozen-base-input")

        self.assertEqual(repeated["id"], first["id"])
        self.assertTrue(repeated["is_idempotent"])
        saved = lesson_manager.get_class_commentary_generation(first["id"])
        self.assertEqual(
            json.loads(saved["prompt_payload_snapshot_json"]),
            original_prompt,
        )
        self.assertEqual(
            json.loads(saved["memory_context_snapshot_json"]),
            original_memory,
        )

    def test_structured_execution_snapshot_rejects_prompt_or_temperature_drift(self):
        generation = self._reserve_structured(
            "generation-request-structured-execution-drift"
        )
        saved = lesson_manager.get_class_commentary_generation(generation["id"])
        valid_prompt = json.loads(saved["prompt_payload_snapshot_json"])
        valid_memory = json.loads(saved["memory_context_snapshot_json"])
        mutations = (
            ("messages", {**valid_prompt, "messages": []}),
            (
                "eligible_ids",
                {
                    **valid_prompt,
                    "messages": [
                        valid_prompt["messages"][0],
                        {
                            **valid_prompt["messages"][1],
                            "content": valid_prompt["messages"][1]["content"].replace(
                                '"eligible_student_ids": [',
                                '"eligible_student_ids": [999,',
                                1,
                            ),
                        },
                    ],
                },
            ),
            ("temperature", {**valid_prompt, "temperature": 0.1}),
        )

        for label, prompt_payload in mutations:
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    lesson_manager.finalize_class_commentary_generation_execution_snapshot(
                        generation["id"],
                        prompt_payload=prompt_payload,
                        memory_context=valid_memory,
                    )

        self.assertEqual(
            lesson_manager.get_class_commentary_generation(generation["id"]),
            saved,
        )

    def test_pending_execution_snapshot_can_only_be_finalized_once_before_completion(self):
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=self.task["id"],
            generation_request_id="generation-request-pending-execution",
            skill_registry_id=self.skill_registry_id,
            attending_roster=self.roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters=self.model_parameters,
            prompt_version="class-commentary-v1",
        )
        self.assertEqual(generation["execution_snapshot_status"], "pending")
        with self.assertRaisesRegex(ValueError, "not finalized"):
            lesson_manager.complete_class_commentary_generation(
                generation["id"],
                "不能提前完成",
            )

        finalized = lesson_manager.finalize_class_commentary_generation_execution_snapshot(
            generation["id"],
            prompt_payload=self.prompt_payload,
            memory_context=self.memory_context,
        )
        repeated = lesson_manager.finalize_class_commentary_generation_execution_snapshot(
            generation["id"],
            prompt_payload=copy.deepcopy(self.prompt_payload),
            memory_context=copy.deepcopy(self.memory_context),
        )

        self.assertEqual(finalized["execution_snapshot_status"], "ready")
        self.assertTrue(finalized["execution_snapshot_finalized_at"])
        self.assertEqual(repeated["id"], finalized["id"])
        with self.assertRaises(lesson_manager.ClassCommentaryGenerationRequestConflict):
            lesson_manager.finalize_class_commentary_generation_execution_snapshot(
                generation["id"],
                prompt_payload={"messages": []},
                memory_context=self.memory_context,
            )
        completed = lesson_manager.complete_class_commentary_generation(
            generation["id"],
            "冻结后完成",
        )
        self.assertEqual(completed["status"], "succeeded")

    def test_same_request_returns_original_after_skill_and_roster_change(self):
        first = self._reserve("generation-request-later-scope-change")
        removed_student_id = self.roster[-1]["student_id"]
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE class_commentary_skills SET status='disabled' WHERE id=?",
                (self.skill_registry_id,),
            )
            conn.execute(
                "DELETE FROM class_students WHERE class_id=? AND student_id=?",
                (self.class_id, removed_student_id),
            )

        repeated = self._reserve(
            "generation-request-later-scope-change",
            attending_roster=copy.deepcopy(self.roster),
        )

        self.assertEqual(repeated["id"], first["id"])
        self.assertTrue(repeated["is_idempotent"])
        with lesson_manager.get_conn() as conn:
            generation_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_generations WHERE task_id=?",
                (self.task["id"],),
            ).fetchone()[0]
        self.assertEqual(generation_count, 1)

    def test_terminal_updates_are_sealed_and_late_completion_keeps_latest_generation(self):
        first = self._reserve("generation-request-first")
        second = self._reserve("generation-request-second")

        lesson_manager.complete_class_commentary_generation(first["id"], "第一版反馈")
        first_completed = lesson_manager.get_class_commentary_generation(first["id"])
        task_after_late_completion = lesson_manager.get_class_commentary_task(self.task["id"])

        self.assertEqual(first_completed["status"], "succeeded")
        self.assertEqual(first_completed["generated_feedback_text"], "第一版反馈")
        self.assertTrue(first_completed["completed_at"])
        self.assertEqual(task_after_late_completion["generation_seq"], 2)
        self.assertEqual(task_after_late_completion["latest_generation_id"], second["id"])
        self.assertEqual(task_after_late_completion["status"], "generating")
        self.assertEqual(task_after_late_completion["feedback_text"], "")

        lesson_manager.complete_class_commentary_generation(first["id"], "不应覆盖的反馈")
        first_after_repeated_completion = lesson_manager.get_class_commentary_generation(first["id"])
        self.assertEqual(first_after_repeated_completion["generated_feedback_text"], "第一版反馈")
        self.assertEqual(first_after_repeated_completion["completed_at"], first_completed["completed_at"])

        lesson_manager.fail_class_commentary_generation(second["id"], "provider_timeout")
        failed = lesson_manager.get_class_commentary_generation(second["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error_code"], "provider_timeout")
        self.assertEqual(failed["generated_feedback_text"], "")
        self.assertTrue(failed["completed_at"])

        lesson_manager.complete_class_commentary_generation(second["id"], "失败后不应写入")
        failed_after_completion_attempt = lesson_manager.get_class_commentary_generation(second["id"])
        task_after_completion_attempt = lesson_manager.get_class_commentary_task(self.task["id"])
        self.assertEqual(failed_after_completion_attempt["status"], "failed")
        self.assertEqual(failed_after_completion_attempt["error_code"], "provider_timeout")
        self.assertEqual(failed_after_completion_attempt["generated_feedback_text"], "")
        self.assertEqual(failed_after_completion_attempt["completed_at"], failed["completed_at"])
        self.assertEqual(task_after_completion_attempt["latest_generation_id"], second["id"])
        self.assertEqual(task_after_completion_attempt["status"], "failed")
        self.assertEqual(task_after_completion_attempt["generation_error"], "provider_timeout")

    def test_completion_after_transcript_change_does_not_update_task_cache(self):
        generation = self._reserve("generation-request-before-transcript-edit")
        edited_transcript = "小王计算更稳了, 新增要求是继续检查书写步骤."
        task_after_edit = lesson_manager.save_class_commentary_transcript(
            self.task["id"],
            edited_transcript,
        )

        completed = lesson_manager.complete_class_commentary_generation(
            generation["id"],
            "基于旧转写生成的反馈",
        )
        task_after_completion = lesson_manager.get_class_commentary_task(self.task["id"])

        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(completed["generated_feedback_text"], "基于旧转写生成的反馈")
        self.assertEqual(task_after_edit["confirmed_transcript_version"], 2)
        self.assertEqual(task_after_completion["confirmed_transcript_version"], 2)
        self.assertEqual(task_after_completion["confirmed_transcript_text"], edited_transcript)
        self.assertEqual(task_after_completion["status"], "transcribed")
        self.assertEqual(task_after_completion["feedback_text"], "")


if __name__ == "__main__":
    unittest.main()
