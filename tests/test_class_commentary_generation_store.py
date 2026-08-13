import copy
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

import lesson_manager
from class_commentary import (
    CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V4,
    CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3,
    CLASS_COMMENTARY_TEMPERATURE,
    build_class_commentary_chat_request,
)
from class_commentary_batch_context import (
    BATCH_ISOLATED_CONTEXT_SCHEMA_V1,
    build_batch_isolated_prompt_student_contexts,
    build_batch_isolated_teacher_style_memories,
)
from class_commentary_graph_retrieval import empty_isolated_student_graph_context
from class_commentary_memory_retrieval import empty_class_commentary_memory_context
from class_commentary_student_memory_v2 import (
    build_safe_class_context,
    build_student_current_evidence,
)
from class_commentary_feedback_schema import (
    CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
)


STRUCTURED_SCHEMA_VERSION = "class_commentary.student_feedback.v1"
STRUCTURED_ATTENDING_SCOPE_VERSION = "class_commentary.attending_roster_scope.v1"
STRUCTURED_PROMPT_VERSION = CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V4
STRUCTURED_RESPONSE_FORMAT = {"type": "json_object"}
STRUCTURED_MEMORY_MODE = (
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
)
STRUCTURED_MODEL_PARAMETERS = {"temperature": CLASS_COMMENTARY_TEMPERATURE}


class ClassCommentaryGenerationStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        lesson_manager.init_db()

        self.teacher = lesson_manager.get_user_by_username("Kayn")
        lesson_manager.insert_credit_ledger_entry(
            organization_id=self.teacher["organization_id"],
            direction="credit",
            amount=1000,
            source_type="test_setup",
            source_id="generation-store",
            operator_user_id=self.teacher["id"],
        )
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

    def _build_structured_batch_snapshots(self, selected_roster):
        transcript = lesson_manager.get_class_commentary_task(self.task["id"])[
            "confirmed_transcript_text"
        ]
        transcript_hash = hashlib.sha256(transcript.encode("utf-8")).hexdigest()
        class_context = build_safe_class_context(
            class_record={"id": self.class_id},
            subject_key="math",
        )
        student_contexts = []
        for item in selected_roster:
            student_id = item["student_id"]
            student_contexts.append(
                {
                    "student_id": student_id,
                    "class_context": copy.deepcopy(class_context),
                    "current_evidence_snapshot": build_student_current_evidence(
                        transcript=transcript,
                        transcript_hash=transcript_hash,
                        roster=selected_roster,
                        target_student_id=student_id,
                    ),
                    "memory_context": empty_class_commentary_memory_context(
                        student_history_memory_mode=STRUCTURED_MEMORY_MODE,
                    ),
                    "learning_graph": empty_isolated_student_graph_context(
                        organization_id=self.teacher["organization_id"],
                        student_id=student_id,
                        subject_key="math",
                        retrieval_status="empty",
                    ),
                }
            )
        structured_memory = {
            "schema_version": BATCH_ISOLATED_CONTEXT_SCHEMA_V1,
            "student_history_memory_mode": STRUCTURED_MEMORY_MODE,
            "teacher_style_memories": [],
            "student_contexts_by_id": student_contexts,
        }
        structured_prompt = build_class_commentary_chat_request(
            class_record=lesson_manager.get_class(self.class_id),
            students=[
                {"id": item["student_id"], "name": item["student_name"]}
                for item in selected_roster
            ],
            transcript_text=transcript,
            skill={
                "id": "generation-store-teacher",
                "name": "generation-store-teacher",
                "content": self.skill_content,
            },
            teacher_style_memories=(
                build_batch_isolated_teacher_style_memories(structured_memory)
            ),
            student_history_memories=[],
            feedback_schema_version=STRUCTURED_SCHEMA_VERSION,
            eligible_student_ids=[item["student_id"] for item in selected_roster],
            prompt_version=STRUCTURED_PROMPT_VERSION,
            response_format=copy.deepcopy(STRUCTURED_RESPONSE_FORMAT),
            student_history_memory_mode=STRUCTURED_MEMORY_MODE,
            student_contexts_by_id=(
                build_batch_isolated_prompt_student_contexts(structured_memory)
            ),
        )
        return structured_prompt, structured_memory

    def _reserve_structured(
        self,
        request_id,
        attending_roster=None,
        *,
        attending_roster_explicit=True,
    ):
        selected_roster = self.roster if attending_roster is None else attending_roster
        generation = lesson_manager.reserve_class_commentary_generation(
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
            attending_roster_explicit=attending_roster_explicit,
            structured_feedback_enabled=True,
            student_history_memory_mode=STRUCTURED_MEMORY_MODE,
            credit_hold_amount=10,
        )
        structured_prompt, structured_memory = self._build_structured_batch_snapshots(
            selected_roster
        )
        return lesson_manager.finalize_class_commentary_generation_execution_snapshot(
            generation["id"],
            prompt_payload=structured_prompt,
            memory_context=structured_memory,
        )

    def _generation_count(self):
        with lesson_manager.get_conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM class_commentary_generations WHERE task_id=?",
                (self.task["id"],),
            ).fetchone()[0]

    def _structured_row_counts(self):
        with lesson_manager.get_conn() as conn:
            return {
                "generations": conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_generations WHERE task_id=?",
                    (self.task["id"],),
                ).fetchone()[0],
                "student_runs": conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_student_generation_runs"
                ).fetchone()[0],
                "credit_holds": conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_student_generation_credit_holds"
                ).fetchone()[0],
                "generation_credit_holds": conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_generation_credit_holds"
                ).fetchone()[0],
            }

    def _insert_legacy_isolated_v2_generation(self, request_id):
        transcript = lesson_manager.get_class_commentary_task(self.task["id"])[
            "confirmed_transcript_text"
        ]
        transcript_hash = hashlib.sha256(transcript.encode("utf-8")).hexdigest()
        roster_json = self._canonical_json(self.roster)
        roster_hash = hashlib.sha256(roster_json.encode("utf-8")).hexdigest()
        eligible_ids = [item["student_id"] for item in self.roster]
        eligible_scope_hash = lesson_manager.build_class_commentary_eligible_scope_hash(
            transcript_hash=transcript_hash,
            roster_hash=roster_hash,
            eligible_student_ids=eligible_ids,
            matcher_version=CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
        )
        empty_json = self._canonical_json({})
        empty_hash = hashlib.sha256(empty_json.encode("utf-8")).hexdigest()
        model_parameters_json = self._canonical_json(STRUCTURED_MODEL_PARAMETERS)
        with lesson_manager.get_conn() as conn:
            task = conn.execute(
                "SELECT * FROM class_commentary_tasks WHERE id=?",
                (self.task["id"],),
            ).fetchone()
            generation_no = int(task["generation_seq"] or 0) + 1
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?,
                          'openai', 'legacy-test-model', ?, ?, ?, ?, ?, ?, 'ready',
                          strftime('%Y-%m-%dT%H:%M:%fZ','now'), ?, ?, ?, ?, ?, ?, '',
                          'runtime', 'complete', '[]', 'generating')
                """,
                (
                    self.teacher["organization_id"],
                    self.task["id"],
                    generation_no,
                    request_id,
                    "legacy-v2-request-payload-hash",
                    self.teacher["id"],
                    self.class_id,
                    "math",
                    int(task["confirmed_transcript_version"]),
                    transcript,
                    transcript_hash,
                    roster_json,
                    roster_hash,
                    self.skill_registry_id,
                    "generation-store-teacher",
                    self.skill_version_id,
                    self.skill_content,
                    hashlib.sha256(self.skill_content.encode("utf-8")).hexdigest(),
                    model_parameters_json,
                    CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
                    empty_json,
                    empty_hash,
                    empty_json,
                    empty_hash,
                    STRUCTURED_SCHEMA_VERSION,
                    self._canonical_json(eligible_ids),
                    eligible_scope_hash,
                    CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
                    self._canonical_json(STRUCTURED_RESPONSE_FORMAT),
                    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
                ),
            )
            generation_id = int(cursor.lastrowid)
            conn.execute(
                """
                UPDATE class_commentary_tasks
                SET generation_seq=?, latest_generation_id=?, status='generating',
                    generation_request_key=?
                WHERE id=?
                """,
                (generation_no, generation_id, request_id, self.task["id"]),
            )
            for roster_item in self.roster:
                student_id = int(roster_item["student_id"])
                run_request_id = f"{request_id}:student:{student_id}"
                run_cursor = conn.execute(
                    """
                    INSERT INTO class_commentary_student_generation_runs (
                        organization_id, generation_id, student_id,
                        student_name_snapshot, request_id, request_payload_hash,
                        prompt_version, memory_mode, eligible_student_ids_json,
                        eligible_student_scope_hash, student_mention_matcher_version,
                        current_evidence_snapshot_json, current_evidence_hash,
                        memory_context_snapshot_json, memory_context_hash,
                        provider, model, model_parameters_json,
                        prompt_payload_snapshot_json, prompt_payload_hash,
                        charge_request_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                              'openai', 'legacy-test-model', ?, ?, ?, ?)
                    """,
                    (
                        self.teacher["organization_id"],
                        generation_id,
                        student_id,
                        roster_item["student_name"],
                        run_request_id,
                        f"legacy-v2-run-{student_id}",
                        CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
                        CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
                        self._canonical_json(eligible_ids),
                        eligible_scope_hash,
                        CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
                        empty_json,
                        empty_hash,
                        empty_json,
                        empty_hash,
                        model_parameters_json,
                        empty_json,
                        empty_hash,
                        f"legacy-v2-charge-{student_id}",
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO class_commentary_student_generation_credit_holds (
                        student_run_id, organization_id, amount,
                        request_id, request_payload_hash
                    ) VALUES (?, ?, 7, ?, ?)
                    """,
                    (
                        int(run_cursor.lastrowid),
                        self.teacher["organization_id"],
                        f"legacy-v2-charge-{student_id}",
                        f"legacy-v2-run-{student_id}",
                    ),
                )
        return lesson_manager.get_class_commentary_generation(generation_id)

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
                "student_mention_matcher_version": (
                    STRUCTURED_ATTENDING_SCOPE_VERSION
                ),
            }
        )
        expected_request_hash = self._hash_json(
            {
                "attending_student_ids": expected_eligible_ids,
                "attending_roster_explicit": True,
                "class_name_snapshot": "课堂点评生成测试班",
                "confirmed_transcript_hash": expected_transcript_hash,
                "confirmed_transcript_version": 1,
                "credit_hold_amount_per_student": 0,
                "credit_hold_amount": 10,
                "eligible_student_ids": expected_eligible_ids,
                "eligible_student_scope_hash": expected_scope_hash,
                "feedback_schema_version": STRUCTURED_SCHEMA_VERSION,
                "model_name": "deepseek-chat",
                "model_parameters": STRUCTURED_MODEL_PARAMETERS,
                "model_provider": "deepseek",
                "prompt_version": STRUCTURED_PROMPT_VERSION,
                "privacy_roster_hash": self._hash_json(self.roster),
                "response_format": STRUCTURED_RESPONSE_FORMAT,
                "skill_registry_id": self.skill_registry_id,
                "skill_name_snapshot": "generation-store-teacher",
                "skill_version_id": self.skill_version_id,
                "student_history_memory_mode": STRUCTURED_MEMORY_MODE,
                "student_mention_matcher_version": (
                    STRUCTURED_ATTENDING_SCOPE_VERSION
                ),
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
            STRUCTURED_ATTENDING_SCOPE_VERSION,
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
            credit_hold_amount=10,
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

    def test_non_batch_v4_structured_contracts_are_rejected_without_writes(self):
        invalid_contracts = (
            (CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION, "disabled_v1"),
            (CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2, "disabled_v1"),
            (CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3, "disabled_v1"),
            (CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION, STRUCTURED_MEMORY_MODE),
            (CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2, STRUCTURED_MEMORY_MODE),
            (CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3, STRUCTURED_MEMORY_MODE),
            (STRUCTURED_PROMPT_VERSION, "disabled_v1"),
            (
                CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
                CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
            ),
        )
        for index, (prompt_version, memory_mode) in enumerate(invalid_contracts):
            with self.subTest(
                prompt_version=prompt_version,
                memory_mode=memory_mode,
            ):
                counts_before = self._structured_row_counts()
                task_before = lesson_manager.get_class_commentary_task(
                    self.task["id"]
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "structured generation mode and prompt version are invalid",
                ):
                    lesson_manager.reserve_class_commentary_generation(
                        task_id=self.task["id"],
                        generation_request_id=f"generation-request-old-{index}",
                        skill_registry_id=self.skill_registry_id,
                        attending_roster=self.roster,
                        model_provider="deepseek",
                        model_name="deepseek-chat",
                        model_parameters=STRUCTURED_MODEL_PARAMETERS,
                        prompt_version=prompt_version,
                        structured_feedback_enabled=True,
                        student_history_memory_mode=memory_mode,
                    )
                self.assertEqual(self._structured_row_counts(), counts_before)
                self.assertEqual(
                    lesson_manager.get_class_commentary_task(self.task["id"]),
                    task_before,
                )

    def test_legacy_isolated_v2_rows_remain_readable_and_idempotently_replayable(self):
        request_id = "generation-request-existing-legacy-v2"
        legacy = self._insert_legacy_isolated_v2_generation(request_id)
        generation_count = self._generation_count()
        with lesson_manager.get_conn() as conn:
            run_count = conn.execute(
                """
                SELECT COUNT(*) FROM class_commentary_student_generation_runs
                WHERE generation_id=?
                """,
                (legacy["id"],),
            ).fetchone()[0]

        read_back = lesson_manager.get_class_commentary_generation(legacy["id"])
        replayed = lesson_manager.reserve_class_commentary_generation(
            task_id=self.task["id"],
            generation_request_id=request_id,
            skill_registry_id=self.skill_registry_id,
            attending_roster=copy.deepcopy(self.roster),
            model_provider="openai",
            model_name="legacy-test-model",
            model_parameters=STRUCTURED_MODEL_PARAMETERS,
            prompt_version=CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
            attending_roster_explicit=True,
            structured_feedback_enabled=True,
            student_history_memory_mode=(
                CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2
            ),
            credit_hold_amount_per_student=7,
        )

        self.assertEqual(read_back["id"], legacy["id"])
        self.assertEqual(
            read_back["student_history_memory_mode"],
            CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
        )
        self.assertEqual(replayed["id"], legacy["id"])
        self.assertTrue(replayed["is_idempotent"])
        self.assertEqual(self._generation_count(), generation_count)
        with lesson_manager.get_conn() as conn:
            self.assertEqual(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM class_commentary_student_generation_runs
                    WHERE generation_id=?
                    """,
                    (legacy["id"],),
                ).fetchone()[0],
                run_count,
            )

    def test_legacy_isolated_v2_rows_remain_dispatchable_to_historical_worker(self):
        legacy = self._insert_legacy_isolated_v2_generation(
            "generation-request-existing-legacy-v2-worker"
        )
        runs = lesson_manager.list_class_commentary_student_generation_runs(
            legacy["id"]
        )

        self.assertEqual(len(runs), len(self.roster))
        self.assertEqual(
            [run["id"] for run in runs],
            [
                run["id"]
                for run in lesson_manager.list_dispatchable_class_commentary_student_generation_runs()
            ],
        )
        claimed = lesson_manager.claim_class_commentary_student_generation_run(
            runs[0]["id"],
            claim_owner="legacy-v2-worker-test",
        )
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["status"], "generating")
        self.assertTrue(claimed["claim_token"])

    def test_batch_v4_requires_explicit_attendance_and_complete_roster(self):
        count_before = self._generation_count()
        task_before = lesson_manager.get_class_commentary_task(self.task["id"])

        with self.assertRaisesRegex(ValueError, "scope must be explicit"):
            self._reserve_structured(
                "generation-request-v4-implicit-attendance",
                attending_roster_explicit=False,
            )

        self.assertEqual(self._generation_count(), count_before)
        self.assertEqual(
            lesson_manager.get_class_commentary_task(self.task["id"]),
            task_before,
        )

        lesson_manager.save_class_commentary_transcript(
            self.task["id"],
            "小王计算更稳了, 小李需要继续练习验算.",
        )
        generation = self._reserve_structured(
            "generation-request-v4-complete-attending-roster"
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
        self.assertEqual(generation["prompt_version"], STRUCTURED_PROMPT_VERSION)
        self.assertEqual(generation["attending_roster_explicit"], 1)
        self.assertEqual(generation["execution_snapshot_status"], "ready")

    def test_structured_completion_canonicalizes_roster_order_and_updates_task_atomically(self):
        generation = self._reserve_structured("generation-request-structured-complete")
        first_student_id = self.roster[0]["student_id"]
        second_student_id = self.roster[1]["student_id"]
        model_output = {
            "schema_version": STRUCTURED_SCHEMA_VERSION,
            "items": [
                {
                    "student_id": second_student_id,
                    "feedback_text": "今天验算步骤更完整, 整体计算过程更扎实.",
                },
                {
                    "student_id": first_student_id,
                    "feedback_text": "今天计算过程更稳定, 解题步骤表达得更清楚.",
                },
            ],
            "used_graph_evidence_refs_by_student": [
                {"student_id": first_student_id, "evidence_refs": []},
                {"student_id": second_student_id, "evidence_refs": []},
            ],
        }
        expected_envelope = {
            "schema_version": STRUCTURED_SCHEMA_VERSION,
            "items": [
                {
                    "student_id": first_student_id,
                    "feedback_text": "今天计算过程更稳定, 解题步骤表达得更清楚.",
                },
                {
                    "student_id": second_student_id,
                    "feedback_text": "今天验算步骤更完整, 整体计算过程更扎实.",
                },
            ],
        }
        expected_json = self._canonical_json(expected_envelope)
        expected_text = (
            "小王:\n今天计算过程更稳定, 解题步骤表达得更清楚.\n\n"
            "小李:\n今天验算步骤更完整, 整体计算过程更扎实."
        )

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
            "used_graph_evidence_refs_by_student": [
                {
                    "student_id": item["student_id"],
                    "evidence_refs": [],
                }
                for item in self.roster
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
            ". ".join(
                f'{item["student_name"]}今天课堂步骤更清楚'
                for item in roster
            )
            + ".",
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
            "used_graph_evidence_refs_by_student": [
                {"student_id": item["student_id"], "evidence_refs": []}
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
                "active_skill",
                {
                    **valid_prompt,
                    "messages": [
                        valid_prompt["messages"][0],
                        {
                            **valid_prompt["messages"][1],
                            "content": valid_prompt["messages"][1]["content"].replace(
                                self.skill_content,
                                "被篡改的 Active Skill",
                                1,
                            ),
                        },
                    ],
                },
            ),
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

    def test_batch_v4_execution_snapshot_rejects_missing_or_cross_scoped_contexts(self):
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=self.task["id"],
            generation_request_id="generation-request-batch-context-scope",
            skill_registry_id=self.skill_registry_id,
            attending_roster=self.roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters=STRUCTURED_MODEL_PARAMETERS,
            prompt_version=STRUCTURED_PROMPT_VERSION,
            attending_roster_explicit=True,
            structured_feedback_enabled=True,
            student_history_memory_mode=STRUCTURED_MEMORY_MODE,
            credit_hold_amount=10,
        )
        valid_prompt, valid_memory = self._build_structured_batch_snapshots(
            self.roster
        )
        generation_before = lesson_manager.get_class_commentary_generation(
            generation["id"]
        )

        missing_partition = copy.deepcopy(valid_memory)
        missing_partition["student_contexts_by_id"] = missing_partition[
            "student_contexts_by_id"
        ][:1]

        cross_scoped_graph = copy.deepcopy(valid_memory)
        cross_scoped_graph["student_contexts_by_id"][0]["learning_graph"][
            "student_id"
        ] = self.roster[1]["student_id"]

        disabled_memory = copy.deepcopy(valid_memory)
        disabled_memory["student_history_memory_mode"] = "disabled_v1"

        for label, memory_context in (
            ("missing_partition", missing_partition),
            ("cross_scoped_graph", cross_scoped_graph),
            ("disabled_memory", disabled_memory),
        ):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    lesson_manager.finalize_class_commentary_generation_execution_snapshot(
                        generation["id"],
                        prompt_payload=valid_prompt,
                        memory_context=memory_context,
                    )
                self.assertEqual(
                    lesson_manager.get_class_commentary_generation(generation["id"]),
                    generation_before,
                )

        finalized = lesson_manager.finalize_class_commentary_generation_execution_snapshot(
            generation["id"],
            prompt_payload=valid_prompt,
            memory_context=valid_memory,
        )
        self.assertEqual(finalized["execution_snapshot_status"], "ready")
        self.assertEqual(
            finalized["student_history_memory_mode"],
            STRUCTURED_MEMORY_MODE,
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

    def test_batch_response_snapshot_is_durable_and_rejects_conflicting_replay(self):
        generation = self._reserve_structured("batch-response-snapshot")
        self.assertEqual(generation["batch_provider_dispatch_status"], "pending")
        self.assertIsNone(generation["batch_provider_dispatch_started_at"])
        usage = {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "input_tokens": 120,
            "output_tokens": 80,
        }
        claimed = lesson_manager.claim_class_commentary_batch_generation(
            generation["id"],
            claim_owner="test-batch-response",
        )
        claim_token = claimed["batch_claim_token"]
        started = lesson_manager.mark_class_commentary_batch_provider_dispatch_started(
            generation["id"],
            claim_token=claim_token,
        )
        self.assertEqual(started["batch_provider_dispatch_status"], "started")
        self.assertTrue(started["batch_provider_dispatch_started_at"])

        first = lesson_manager.persist_class_commentary_batch_generation_response(
            generation["id"],
            response_text='{"schema_version":"class_commentary.student_feedback.v1"}',
            usage=usage,
            claim_token=claim_token,
        )
        repeated = lesson_manager.persist_class_commentary_batch_generation_response(
            generation["id"],
            response_text='{"schema_version":"class_commentary.student_feedback.v1"}',
            usage=usage,
            claim_token=claim_token,
        )

        self.assertEqual(repeated["batch_response_hash"], first["batch_response_hash"])
        self.assertEqual(
            lesson_manager.get_class_commentary_batch_generation_response(
                generation["id"]
            ),
            {
                "response_text": '{"schema_version":"class_commentary.student_feedback.v1"}',
                "usage": usage,
            },
        )
        with self.assertRaises(lesson_manager.ClassCommentaryGenerationRequestConflict):
            lesson_manager.persist_class_commentary_batch_generation_response(
                generation["id"],
                response_text="different response",
                usage=usage,
                claim_token=claim_token,
            )

    def test_batch_provider_dispatch_start_is_claim_fenced_and_one_way(self):
        generation = self._reserve_structured("batch-provider-dispatch-start")
        claimed = lesson_manager.claim_class_commentary_batch_generation(
            generation["id"],
            claim_owner="dispatch-worker",
        )
        claim_token = str(claimed["batch_claim_token"])

        with self.assertRaises(
            lesson_manager.ClassCommentaryGenerationRequestConflict
        ):
            lesson_manager.mark_class_commentary_batch_provider_dispatch_started(
                generation["id"],
                claim_token="stale-claim-token",
            )

        started = lesson_manager.mark_class_commentary_batch_provider_dispatch_started(
            generation["id"],
            claim_token=claim_token,
        )
        self.assertEqual(started["batch_provider_dispatch_status"], "started")
        self.assertTrue(started["batch_provider_dispatch_started_at"])

        with self.assertRaises(
            lesson_manager.ClassCommentaryGenerationRequestConflict
        ):
            lesson_manager.mark_class_commentary_batch_provider_dispatch_started(
                generation["id"],
                claim_token=claim_token,
            )

    def test_batch_response_requires_started_provider_dispatch(self):
        generation = self._reserve_structured(
            "batch-response-requires-started-dispatch"
        )
        claimed = lesson_manager.claim_class_commentary_batch_generation(
            generation["id"],
            claim_owner="response-before-dispatch",
        )

        with self.assertRaises(
            lesson_manager.ClassCommentaryGenerationRequestConflict
        ):
            lesson_manager.persist_class_commentary_batch_generation_response(
                generation["id"],
                response_text="provider response",
                usage={},
                claim_token=str(claimed["batch_claim_token"]),
            )

    def test_batch_terminal_failure_is_fenced_by_current_claim_token(self):
        generation = self._reserve_structured("batch-terminal-claim-fencing")
        first_claim = lesson_manager.claim_class_commentary_batch_generation(
            generation["id"],
            claim_owner="first-worker",
        )
        first_token = str(first_claim["batch_claim_token"])
        lesson_manager.release_class_commentary_batch_generation_claim(
            generation["id"],
            claim_token=first_token,
        )
        second_claim = lesson_manager.claim_class_commentary_batch_generation(
            generation["id"],
            claim_owner="second-worker",
        )
        second_token = str(second_claim["batch_claim_token"])

        with self.assertRaises(
            lesson_manager.ClassCommentaryGenerationRequestConflict
        ):
            lesson_manager.fail_class_commentary_batch_generation_terminal(
                generation["id"],
                claim_token=first_token,
                error_code="provider_timeout",
            )

        after_stale_worker = lesson_manager.get_class_commentary_generation(
            generation["id"]
        )
        hold_after_stale_worker = (
            lesson_manager.get_class_commentary_generation_credit_hold(
                generation["id"]
            )
        )
        self.assertEqual(after_stale_worker["status"], "generating")
        self.assertEqual(
            after_stale_worker["batch_claim_token"], second_token
        )
        self.assertEqual(hold_after_stale_worker["status"], "active")

        failed = lesson_manager.fail_class_commentary_batch_generation_terminal(
            generation["id"],
            claim_token=second_token,
            error_code="provider_timeout",
        )
        released_hold = lesson_manager.get_class_commentary_generation_credit_hold(
            generation["id"]
        )
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error_code"], "provider_timeout")
        self.assertIsNone(failed["batch_claim_token"])
        self.assertEqual(released_hold["status"], "released")

    def test_generic_failure_cannot_discard_ready_batch_snapshot(self):
        ready_generation = self._reserve_structured(
            "generic-fail-ready-batch-snapshot"
        )
        with self.assertRaises(
            lesson_manager.ClassCommentaryGenerationRequestConflict
        ):
            lesson_manager.fail_class_commentary_generation(
                ready_generation["id"],
                "unexpected_http_error",
            )
        ready_after = lesson_manager.get_class_commentary_generation(
            ready_generation["id"]
        )
        ready_hold = lesson_manager.get_class_commentary_generation_credit_hold(
            ready_generation["id"]
        )
        self.assertEqual(ready_after["status"], "generating")
        self.assertEqual(ready_after["execution_snapshot_status"], "ready")
        self.assertEqual(ready_hold["status"], "active")

    def test_generic_failure_cannot_discard_live_batch_claim(self):
        claimed_generation = self._reserve_structured(
            "generic-fail-live-batch-claim"
        )
        claimed = lesson_manager.claim_class_commentary_batch_generation(
            claimed_generation["id"],
            claim_owner="live-worker",
        )
        claim_token = str(claimed["batch_claim_token"])
        with self.assertRaises(
            lesson_manager.ClassCommentaryGenerationRequestConflict
        ):
            lesson_manager.fail_class_commentary_generation(
                claimed_generation["id"],
                "unexpected_http_error",
            )
        claimed_after = lesson_manager.get_class_commentary_generation(
            claimed_generation["id"]
        )
        claimed_hold = lesson_manager.get_class_commentary_generation_credit_hold(
            claimed_generation["id"]
        )
        self.assertEqual(claimed_after["status"], "generating")
        self.assertEqual(claimed_after["batch_claim_token"], claim_token)
        self.assertEqual(claimed_hold["status"], "active")

    def test_resumable_batch_lister_normalizes_datetime_to_iso_z(self):
        generation = self._reserve_structured("resumable-batch-datetime")
        claimed = lesson_manager.claim_class_commentary_batch_generation(
            generation["id"],
            claim_owner="expired-worker",
        )
        self.assertIsNotNone(claimed)
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET batch_claim_expires_at='2026-08-12T12:00:00.000000Z'
                WHERE id=?
                """,
                (generation["id"],),
            )

        resumable = lesson_manager.list_resumable_class_commentary_batch_generations(
            now=datetime(2026, 8, 12, 12, 0, 1, tzinfo=timezone.utc)
        )

        self.assertIn(generation["id"], [item["id"] for item in resumable])

    def test_resumable_batch_lister_includes_pending_execution_snapshot(self):
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=self.task["id"],
            generation_request_id="resumable-batch-pending-snapshot",
            skill_registry_id=self.skill_registry_id,
            attending_roster=self.roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters=STRUCTURED_MODEL_PARAMETERS,
            prompt_version=STRUCTURED_PROMPT_VERSION,
            attending_roster_explicit=True,
            structured_feedback_enabled=True,
            student_history_memory_mode=STRUCTURED_MEMORY_MODE,
            credit_hold_amount=10,
        )

        resumable = lesson_manager.list_resumable_class_commentary_batch_generations()

        self.assertEqual(generation["execution_snapshot_status"], "pending")
        self.assertEqual(generation["batch_provider_dispatch_status"], "pending")
        self.assertIn(generation["id"], [item["id"] for item in resumable])

    def test_resumable_batch_lister_includes_uncertain_provider_dispatches(self):
        started_generation = self._reserve_structured(
            "resumable-started-provider-dispatch"
        )
        started_claim = lesson_manager.claim_class_commentary_batch_generation(
            started_generation["id"],
            claim_owner="started-provider-worker",
        )
        lesson_manager.mark_class_commentary_batch_provider_dispatch_started(
            started_generation["id"],
            claim_token=str(started_claim["batch_claim_token"]),
        )
        lesson_manager.release_class_commentary_batch_generation_claim(
            started_generation["id"],
            claim_token=str(started_claim["batch_claim_token"]),
        )

        legacy_unknown_generation = self._reserve_structured(
            "resumable-legacy-unknown-provider-dispatch"
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET batch_provider_dispatch_status='legacy_unknown'
                WHERE id=?
                """,
                (legacy_unknown_generation["id"],),
            )

        resumable = lesson_manager.list_resumable_class_commentary_batch_generations()
        resumable_by_id = {item["id"]: item for item in resumable}

        self.assertEqual(
            resumable_by_id[started_generation["id"]][
                "batch_provider_dispatch_status"
            ],
            "started",
        )
        self.assertEqual(
            resumable_by_id[legacy_unknown_generation["id"]][
                "batch_provider_dispatch_status"
            ],
            "legacy_unknown",
        )

    def test_structured_reservation_requires_canonical_subject(self):
        with lesson_manager.get_conn() as conn:
            conn.execute("UPDATE classes SET subject_key='' WHERE id=?", (self.class_id,))

        with self.assertRaisesRegex(ValueError, "^class_commentary_subject_unavailable$"):
            self._reserve_structured("batch-subject-unavailable")
        self.assertEqual(self._generation_count(), 0)

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
