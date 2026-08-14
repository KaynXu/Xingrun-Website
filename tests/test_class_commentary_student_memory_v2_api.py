import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_runtime
import lesson_manager
import class_commentary_batch_context
from class_commentary_batch_context import ClassCommentaryBatchContextError
from class_commentary_graph_retrieval import empty_isolated_student_graph_context
from class_commentary_memory_retrieval import empty_class_commentary_memory_context


class ClassCommentaryStudentMemoryV2ApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.old_db = lesson_manager.DB_PATH
        self.old_cfg = config_runtime.CFG_PATH
        self.env_patch = patch.dict(
            os.environ,
            {
                "XR_CLASS_COMMENTARY_STRUCTURED_FEEDBACK_ENABLED": "",
                "XR_CLASS_COMMENTARY_STUDENT_MEMORY_V2_ENABLED": "",
                "XR_CLASS_COMMENTARY_MEMORY_ENABLED": "",
            },
            clear=False,
        )
        self.env_patch.start()
        lesson_manager.DB_PATH = self.base / "test.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        self.skill_dir = self.base / "skills"
        self.skill_dir.mkdir()
        config_runtime.write_file_config(
            {
                "colleague_skill_dir": str(self.skill_dir),
                "class_commentary_structured_feedback_enabled": True,
                "class_commentary_student_memory_v2_enabled": True,
                "class_commentary_memory_enabled": True,
            }
        )
        lesson_manager.init_db()
        self.app_module = importlib.import_module("app")
        self.client = self.app_module.app.test_client()
        login = self.client.post(
            "/api/login", json={"username": "Kayn", "password": "xingrun2026"}
        )
        self.assertEqual(login.status_code, 200)
        payload = login.get_json()
        self.user = payload["user"]
        self.headers = {"X-Auth-Token": payload["token"]}
        self.class_id = lesson_manager.save_class(
            "isolated v2 api class",
            subject="数学",
            grade="七年级",
            organization_id=self.user["organization_id"],
            teacher_user_id=self.user["id"],
        )
        self.students = [
            lesson_manager.create_student_for_class(self.class_id, name)
            for name in ("学生甲", "学生乙")
        ]
        self.task = lesson_manager.create_class_commentary_task(
            organization_id=self.user["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.user["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            self.task["id"], "学生甲移项清楚。学生乙能主动验算。"
        )
        self.skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.user["organization_id"],
            skill_id="isolated-v2-api",
            actor_user_id=self.user["id"],
            source_path=str(self.skill_dir / "isolated-v2-api.skill"),
            content="先描述证据, 再给行动建议.",
        )
        lesson_manager.insert_credit_ledger_entry(
            organization_id=self.user["organization_id"],
            direction="credit",
            amount=100,
            source_type="manual_adjustment",
            source_id="isolated-v2-api",
            note="test credits",
            operator_user_id=self.user["id"],
        )

    def tearDown(self):
        self.env_patch.stop()
        lesson_manager.DB_PATH = self.old_db
        config_runtime.CFG_PATH = self.old_cfg
        self.tmp.cleanup()

    def _request_payload(self, request_id="isolated-v2-api-generation"):
        return {
            "request_id": request_id,
            "skill_id": self.skill["skill_id"],
            "attending_student_ids": [item["id"] for item in self.students],
        }

    @staticmethod
    def _enabled_capabilities():
        return {
            "memory_learning_enabled": True,
            "skill_evolution_enabled": True,
            "structured_feedback_enabled": True,
            "student_history_memory_v2_enabled": True,
            "batch_isolated_v3_enabled": True,
            "class_commentary_generation_call_count": 1,
            "student_history_memory_v2_max_credits_per_student": 10,
        }

    def test_batch_isolated_v3_retrieves_each_student_and_calls_provider_once(self):
        model_output = json.dumps(
            {
                "schema_version": "class_commentary.student_feedback.v1",
                "items": [
                    {
                        "student_id": student["id"],
                        "feedback_text": (
                            f"{student['name']}, 你今天的步骤更清楚了🌱。\n\n"
                            "需要继续检查符号问题🔍。\n\n"
                            "下次先写完整过程, 再独立验算一次✨。"
                        ),
                    }
                    for student in self.students
                ],
                "used_graph_evidence_refs_by_student": [
                    {"student_id": student["id"], "evidence_refs": []}
                    for student in self.students
                ],
            },
            ensure_ascii=False,
        )

        def fake_charge(**kwargs):
            result = kwargs["producer"]()
            return result[0] if isinstance(result, tuple) else result

        memory_student_ids = []
        graph_student_ids = []

        def fake_memory_retrieval(**kwargs):
            student_id = int(kwargs["student_id"])
            memory_student_ids.append(student_id)
            context = empty_class_commentary_memory_context(
                student_history_memory_mode="batch_isolated_v3"
            )
            context["retrieval_status"] = "ready"
            context["teacher_style_memories"] = []
            context["student_history_memories"] = []
            context["records"] = []
            return context

        def fake_graph_retrieval(**kwargs):
            student_id = int(kwargs["student_id"])
            graph_student_ids.append(student_id)
            return empty_isolated_student_graph_context(
                organization_id=int(kwargs["generation"]["organization_id"]),
                student_id=student_id,
                subject_key=str(kwargs["class_context"]["subject_key"]),
                retrieval_status="empty",
            )

        with patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=self._enabled_capabilities(),
        ), patch.object(
            self.app_module, "has_class_commentary_api_key", return_value=True
        ), patch.object(
            class_commentary_batch_context,
            "retrieve_isolated_student_memory_context",
            side_effect=fake_memory_retrieval,
        ), patch.object(
            class_commentary_batch_context,
            "retrieve_isolated_student_graph_context",
            side_effect=fake_graph_retrieval,
        ), patch.object(
            class_commentary_batch_context,
            "validate_isolated_student_memory_context_snapshot",
        ), patch.object(
            class_commentary_batch_context,
            "validate_isolated_student_graph_context_snapshot",
        ), patch.object(
            self.app_module, "_run_ai_feature_with_charge", side_effect=fake_charge
        ), patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
            return_value=(
                model_output,
                {
                    "provider": "openai",
                    "model": "fake",
                    "input_tokens": 5,
                    "output_tokens": 20,
                },
            ),
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generate",
                headers=self.headers,
                json=self._request_payload(),
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["student_history_memory_mode"], "batch_isolated_v3")
        self.assertEqual(
            payload["prompt_version"],
            "class-commentary-student-feedback-batch-isolated-v5",
        )
        self.assertEqual(payload["student_run_progress"]["total"], 0)
        self.assertEqual(
            [item["student_id"] for item in payload["student_feedback_items"]],
            [student["id"] for student in self.students],
        )
        self.assertTrue(
            all("🌱" in item["feedback_text"] for item in payload["student_feedback_items"])
        )
        self.assertNotIn("prompt_payload_snapshot_json", json.dumps(payload))
        self.assertNotIn("memory_context_snapshot_json", json.dumps(payload))
        generate.assert_called_once()
        self.assertEqual(memory_student_ids, [student["id"] for student in self.students])
        self.assertEqual(graph_student_ids, [student["id"] for student in self.students])
        chat_request = generate.call_args.kwargs["chat_request"]
        self.assertEqual(chat_request["student_history_memory_mode"], "batch_isolated_v3")
        self.assertNotIn(
            "[STUDENT_HISTORY_MEMORIES]",
            chat_request["messages"][1]["content"],
        )
        self.assertIn("2-4 short paragraphs", chat_request["messages"][1]["content"])
        self.assertIn("emoji", chat_request["messages"][0]["content"])
        self.assertIn("[STUDENT_CONTEXTS_BY_ID]", chat_request["messages"][1]["content"])

        detail = self.client.get(
            f"/api/class-commentary/tasks/{self.task['id']}/generations/{payload['generation_id']}",
            headers=self.headers,
        )
        self.assertEqual(detail.status_code, 200)

    def test_capabilities_expose_call_cost_impact_without_private_context(self):
        with patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=self._enabled_capabilities(),
        ):
            response = self.client.get(
                "/api/class-commentary/capabilities", headers=self.headers
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["student_history_memory_v2_max_credits_per_student"],
            10,
        )
        self.assertTrue(
            response.get_json()["student_history_memory_v2_enabled"]
        )

    def test_unavailable_batch_memory_fails_before_reservation_and_provider(self):
        unavailable_capabilities = {
            **self._enabled_capabilities(),
            "student_history_memory_v2_enabled": False,
            "batch_isolated_v3_enabled": False,
        }
        with patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=unavailable_capabilities,
        ), patch.object(
            self.app_module, "has_class_commentary_api_key", return_value=True
        ), patch.object(self.app_module, "reserve_class_commentary_generation") as reserve, \
             patch.object(self.app_module, "generate_class_commentary_feedback") as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generate",
                headers=self.headers,
                json=self._request_payload("batch-memory-unavailable"),
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json()["error"],
            "class_commentary_batch_memory_unavailable",
        )
        reserve.assert_not_called()
        generate.assert_not_called()

    def test_insufficient_credits_fail_before_batch_context_and_reservation(self):
        lesson_manager.insert_credit_ledger_entry(
            organization_id=self.user["organization_id"],
            direction="debit",
            amount=91,
            source_type="manual_adjustment",
            source_id="batch-v4-preflight",
            note="leave fewer than the maximum credits for one class generation",
            operator_user_id=self.user["id"],
        )
        with lesson_manager.get_conn() as conn:
            before = {
                "generations": conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_generations"
                ).fetchone()[0],
                "runs": conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_student_generation_runs"
                ).fetchone()[0],
                "holds": conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_student_generation_credit_holds"
                ).fetchone()[0],
            }

        real_preflight = self.app_module.ensure_feature_credits_available_for_count
        with patch.object(
            self.app_module,
            "ensure_feature_credits_available_for_count",
            wraps=real_preflight,
        ) as preflight, patch.object(
            self.app_module, "has_class_commentary_api_key", return_value=True
        ), patch.object(
            self.app_module, "_class_commentary_capabilities"
        ) as capabilities, patch.object(
            self.app_module, "reserve_class_commentary_generation"
        ) as reserve, patch.object(
            class_commentary_batch_context,
            "retrieve_isolated_student_memory_context",
        ) as retrieve_memory, patch.object(
            class_commentary_batch_context,
            "retrieve_isolated_student_graph_context",
        ) as retrieve_graph, patch.object(
            self.app_module, "_run_ai_feature_with_charge"
        ) as charge, patch.object(
            self.app_module, "generate_class_commentary_feedback"
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generate",
                headers=self.headers,
                json=self._request_payload("batch-v4-insufficient-credits"),
            )

        self.assertEqual(response.status_code, 402)
        self.assertEqual(
            response.get_json(),
            {"error": "机构积分不足，请先充值后再使用 AI 功能"},
        )
        preflight.assert_called_once_with(
            organization_id=self.user["organization_id"],
            feature_key="class_commentary_generate",
            call_count=1,
        )
        capabilities.assert_not_called()
        reserve.assert_not_called()
        retrieve_memory.assert_not_called()
        retrieve_graph.assert_not_called()
        charge.assert_not_called()
        generate.assert_not_called()
        with lesson_manager.get_conn() as conn:
            after = {
                "generations": conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_generations"
                ).fetchone()[0],
                "runs": conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_student_generation_runs"
                ).fetchone()[0],
                "holds": conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_student_generation_credit_holds"
                ).fetchone()[0],
            }
        self.assertEqual(after, before)

    def test_asr_name_variants_reach_v5_provider_with_complete_rosters(self):
        lesson_manager.mark_class_commentary_transcription_succeeded(
            self.task["id"], "刘峰峰今天移项步骤更清楚.张玉空验算更主动."
        )
        absent_student = lesson_manager.create_student_for_class(
            self.class_id,
            "王小明",
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE students SET name=? WHERE id=?",
                ("刘鹏鹏", self.students[0]["id"]),
            )
            conn.execute(
                "UPDATE students SET name=? WHERE id=?",
                ("张玉坤", self.students[1]["id"]),
            )
        model_output = json.dumps(
            {
                "schema_version": "class_commentary.student_feedback.v1",
                "items": [
                    {
                        "student_id": self.students[0]["id"],
                        "feedback_text": "刘鹏鹏, 你今天移项步骤更清楚了.课后把符号再检查一遍.",
                    },
                    {
                        "student_id": self.students[1]["id"],
                        "feedback_text": "张玉坤, 你今天能主动验算.下次继续写全验算过程.",
                    },
                ],
                "used_graph_evidence_refs_by_student": [
                    {"student_id": student["id"], "evidence_refs": []}
                    for student in self.students
                ],
            },
            ensure_ascii=False,
        )

        def fake_memory_retrieval(**_kwargs):
            return empty_class_commentary_memory_context(
                student_history_memory_mode="batch_isolated_v3"
            )

        def fake_graph_retrieval(**kwargs):
            return empty_isolated_student_graph_context(
                organization_id=int(kwargs["generation"]["organization_id"]),
                student_id=int(kwargs["student_id"]),
                subject_key=str(kwargs["class_context"]["subject_key"]),
                retrieval_status="empty",
            )

        with patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=self._enabled_capabilities(),
        ), patch.object(
            self.app_module, "has_class_commentary_api_key", return_value=True
        ), patch.object(
            class_commentary_batch_context,
            "retrieve_isolated_student_memory_context",
            side_effect=fake_memory_retrieval,
        ), patch.object(
            class_commentary_batch_context,
            "retrieve_isolated_student_graph_context",
            side_effect=fake_graph_retrieval,
        ), patch.object(
            class_commentary_batch_context,
            "validate_isolated_student_memory_context_snapshot",
        ), patch.object(
            class_commentary_batch_context,
            "validate_isolated_student_graph_context_snapshot",
        ), patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
            return_value=(
                model_output,
                {
                    "provider": "openai",
                    "model": "fake",
                    "input_tokens": 5,
                    "output_tokens": 20,
                },
            ),
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generate",
                headers=self.headers,
                json=self._request_payload("asr-name-variants-v5"),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "succeeded")
        generate.assert_called_once()
        chat_request = generate.call_args.kwargs["chat_request"]
        self.assertEqual(
            chat_request["prompt_version"],
            "class-commentary-student-feedback-batch-isolated-v5",
        )
        user_prompt = chat_request["messages"][1]["content"]
        current_facts = json.loads(
            user_prompt.split("[CURRENT_TASK_FACTS]\n", 1)[1].split(
                "\n\n[ACTIVE_SKILL]\n",
                1,
            )[0]
        )
        self.assertIn("刘峰峰今天移项步骤更清楚", user_prompt)
        self.assertIn('"name": "刘鹏鹏"', user_prompt)
        self.assertIn('"name": "张玉坤"', user_prompt)
        self.assertEqual(
            current_facts["official_course_roster"],
            [
                {"id": self.students[0]["id"], "name": "刘鹏鹏"},
                {"id": self.students[1]["id"], "name": "张玉坤"},
                {"id": absent_student["id"], "name": "王小明"},
            ],
        )
        self.assertIn('"official_course_roster"', user_prompt)
        self.assertIn('"eligible_student_ids"', user_prompt)
        self.assertIn('"verified_fragments": []', user_prompt)
        self.assertNotIn('"verified_fragments": [\n', user_prompt)

    def test_graph_failure_after_capability_gate_fails_generation_without_provider(self):
        with patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=self._enabled_capabilities(),
        ), patch.object(
            self.app_module, "has_class_commentary_api_key", return_value=True
        ), patch.object(
            class_commentary_batch_context,
            "build_batch_generation_execution_snapshot",
            side_effect=ClassCommentaryBatchContextError(
                "batch_context_retrieval_failed"
            ),
        ), patch.object(
            self.app_module, "_run_ai_feature_with_charge"
        ) as charge, patch.object(
            self.app_module, "generate_class_commentary_feedback"
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generate",
                headers=self.headers,
                json=self._request_payload("batch-graph-runtime-failure"),
            )

        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        self.assertEqual(
            payload["error"], "class_commentary_batch_memory_unavailable"
        )
        self.assertEqual(payload["generation_status"], "failed")
        self.assertEqual(
            payload["generation"]["error_code"],
            "class_commentary_batch_context_unavailable",
        )
        self.assertNotIn("batch_context_retrieval_failed", response.get_data(as_text=True))
        charge.assert_not_called()
        generate.assert_not_called()

    def test_http_provider_timeout_fails_closed_without_provider_replay(self):
        def fake_memory_retrieval(**_kwargs):
            context = empty_class_commentary_memory_context(
                student_history_memory_mode="batch_isolated_v3"
            )
            context["retrieval_status"] = "ready"
            return context

        def fake_graph_retrieval(**kwargs):
            return empty_isolated_student_graph_context(
                organization_id=int(kwargs["generation"]["organization_id"]),
                student_id=int(kwargs["student_id"]),
                subject_key=str(kwargs["class_context"]["subject_key"]),
                retrieval_status="empty",
            )

        with patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=self._enabled_capabilities(),
        ), patch.object(
            self.app_module, "has_class_commentary_api_key", return_value=True
        ), patch.object(
            class_commentary_batch_context,
            "retrieve_isolated_student_memory_context",
            side_effect=fake_memory_retrieval,
        ), patch.object(
            class_commentary_batch_context,
            "retrieve_isolated_student_graph_context",
            side_effect=fake_graph_retrieval,
        ), patch.object(
            class_commentary_batch_context,
            "validate_isolated_student_memory_context_snapshot",
        ), patch.object(
            class_commentary_batch_context,
            "validate_isolated_student_graph_context_snapshot",
        ), patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
            side_effect=TimeoutError("provider timed out"),
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generate",
                headers=self.headers,
                json=self._request_payload("batch-http-provider-timeout"),
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["generation_status"], "failed")
        generation = lesson_manager.get_class_commentary_generation(
            payload["generation_id"]
        )
        hold = lesson_manager.get_class_commentary_generation_credit_hold(
            payload["generation_id"]
        )
        self.assertEqual(generation["status"], "failed")
        self.assertEqual(generation["error_code"], "provider_timeout")
        provider_failure = lesson_manager.get_class_commentary_batch_provider_failure(
            payload["generation_id"]
        )
        self.assertEqual(provider_failure["result_state"], "unknown")
        self.assertEqual(
            provider_failure["exception_type"],
            "builtins.TimeoutError",
        )
        self.assertEqual(generation["batch_attempt_count"], 1)
        self.assertIsNone(generation["batch_claim_token"])
        self.assertEqual(hold["status"], "released")
        self.assertNotIn(
            payload["generation_id"],
            [
                item["id"]
                for item in lesson_manager.list_resumable_class_commentary_batch_generations()
            ],
        )
        generate.assert_called_once()

    def test_error_after_execution_snapshot_is_ready_keeps_generation_resumable(self):
        def fail_after_snapshot_ready(*, generation, user):
            self.assertEqual(int(user["id"]), int(self.user["id"]))
            with lesson_manager.get_conn() as conn:
                conn.execute(
                    """
                    UPDATE class_commentary_generations
                    SET execution_snapshot_status='ready',
                        execution_snapshot_finalized_at='2026-08-13T00:00:00.000Z'
                    WHERE id=?
                    """,
                    (int(generation["id"]),),
                )
            raise RuntimeError("post-snapshot processing failed")

        real_fail_generation = self.app_module.fail_class_commentary_generation
        with patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=self._enabled_capabilities(),
        ), patch.object(
            self.app_module, "has_class_commentary_api_key", return_value=True
        ), patch.object(
            self.app_module,
            "_resume_class_commentary_batch_generation",
            side_effect=fail_after_snapshot_ready,
        ), patch.object(
            self.app_module,
            "fail_class_commentary_generation",
            wraps=real_fail_generation,
        ) as fail_generation:
            response = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generate",
                headers=self.headers,
                json=self._request_payload("batch-ready-snapshot-error"),
            )

        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertEqual(payload["error"], "post-snapshot processing failed")
        self.assertEqual(payload["generation_status"], "generating")
        self.assertEqual(
            payload["generation"]["execution_snapshot_status"], "ready"
        )
        generation = lesson_manager.get_class_commentary_generation(
            payload["generation_id"]
        )
        hold = lesson_manager.get_class_commentary_generation_credit_hold(
            payload["generation_id"]
        )
        self.assertEqual(generation["status"], "generating")
        self.assertEqual(generation["execution_snapshot_status"], "ready")
        self.assertEqual(hold["status"], "active")
        fail_generation.assert_not_called()

    def test_pending_batch_recovery_uses_frozen_generation_snapshots_only(self):
        frozen_transcript = str(
            lesson_manager.get_class_commentary_task(self.task["id"])[
                "confirmed_transcript_text"
            ]
        )
        frozen_roster = [
            {"student_id": item["id"], "student_name": item["name"]}
            for item in self.students
        ]
        frozen_skill_content = "先描述证据, 再给行动建议."
        request_id = "pending-batch-frozen-recovery"
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=self.task["id"],
            generation_request_id=request_id,
            skill_registry_id=self.skill["registry_id"],
            attending_roster=frozen_roster,
            model_provider="openai",
            model_name="frozen-model",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-student-feedback-batch-isolated-v4",
            attending_roster_explicit=True,
            structured_feedback_enabled=True,
            student_history_memory_mode="batch_isolated_v3",
            credit_hold_amount=self.app_module.max_configured_charge_for_feature(
                "class_commentary_generate"
            ),
        )
        self.assertEqual(generation["execution_snapshot_status"], "pending")
        frozen_class_name = generation["class_name_snapshot"]
        frozen_skill_name = generation["skill_name_snapshot"]

        live_transcript = "LIVE TRANSCRIPT: 这不是冻结时确认的课堂内容."
        lesson_manager.save_class_commentary_transcript(
            self.task["id"], live_transcript
        )
        removed_student = self.students[-1]
        lesson_manager.remove_student_from_class(
            self.class_id, removed_student["id"]
        )
        live_student = lesson_manager.create_student_for_class(
            self.class_id, "LIVE STUDENT"
        )
        lesson_manager.update_class(
            class_id=self.class_id,
            name="LIVE CLASS: 不得用于已冻结 generation.",
            subject="数学",
            grade="七年级",
            class_type="group",
            actor_user_id=self.user["id"],
        )
        source_path = Path(self.skill["source_path"])
        source_path.write_text(
            "LIVE SKILL: 不得用于已冻结 generation.", encoding="utf-8"
        )
        refreshed_skill = lesson_manager.refresh_class_commentary_skill_manifest(
            organization_id=self.user["organization_id"],
            skill_id=self.skill["skill_id"],
            actor_user_id=self.user["id"],
            activation_request_id="pending-recovery-live-skill-refresh",
            expected_active_version_id=self.skill["active_version_id"],
        )
        self.assertNotEqual(
            refreshed_skill["skill"]["active_version_id"],
            generation["skill_version_id"],
        )

        model_output = json.dumps(
            {
                "schema_version": "class_commentary.student_feedback.v1",
                "items": [
                    {
                        "student_id": item["id"],
                        "feedback_text": (
                            f"{item['name']}, 你今天的步骤很清楚🌱。\n\n"
                            "继续检查符号和计算细节🔍。\n\n"
                            "下次先写完整过程, 再独立验算一次✨。"
                        ),
                    }
                    for item in self.students
                ],
                "used_graph_evidence_refs_by_student": [
                    {"student_id": item["id"], "evidence_refs": []}
                    for item in self.students
                ],
            },
            ensure_ascii=False,
        )

        def fake_memory_retrieval(**_kwargs):
            context = empty_class_commentary_memory_context(
                student_history_memory_mode="batch_isolated_v3"
            )
            context["retrieval_status"] = "ready"
            return context

        def fake_graph_retrieval(**kwargs):
            return empty_isolated_student_graph_context(
                organization_id=int(kwargs["generation"]["organization_id"]),
                student_id=int(kwargs["student_id"]),
                subject_key=str(kwargs["class_context"]["subject_key"]),
                retrieval_status="empty",
            )

        with patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=self._enabled_capabilities(),
        ), patch.object(
            self.app_module, "has_class_commentary_api_key", return_value=True
        ), patch.object(
            self.app_module, "_sync_configured_class_commentary_skills"
        ), patch.object(
            class_commentary_batch_context,
            "retrieve_isolated_student_memory_context",
            side_effect=fake_memory_retrieval,
        ), patch.object(
            class_commentary_batch_context,
            "retrieve_isolated_student_graph_context",
            side_effect=fake_graph_retrieval,
        ), patch.object(
            class_commentary_batch_context,
            "validate_isolated_student_memory_context_snapshot",
        ), patch.object(
            class_commentary_batch_context,
            "validate_isolated_student_graph_context_snapshot",
        ), patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
            return_value=(
                model_output,
                {
                    "provider": "openai",
                    "model": "frozen-model",
                    "input_tokens": 20,
                    "output_tokens": 40,
                },
            ),
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generate",
                headers=self.headers,
                json={
                    "request_id": request_id,
                    "skill_id": self.skill["skill_id"],
                    "attending_student_ids": [
                        item["id"] for item in self.students
                    ],
                },
            )

        self.assertEqual(
            response.status_code,
            200,
            response.get_data(as_text=True),
        )
        payload = response.get_json()
        self.assertEqual(payload["generation_id"], generation["id"])
        self.assertEqual(payload["generation_status"], "succeeded")
        generate.assert_called_once()
        provider_kwargs = generate.call_args.kwargs
        self.assertEqual(provider_kwargs["transcript_text"], frozen_transcript)
        self.assertEqual(
            provider_kwargs["students"],
            [
                {"id": item["id"], "name": item["name"]}
                for item in self.students
            ],
        )
        self.assertEqual(
            provider_kwargs["skill"]["content"], frozen_skill_content
        )
        self.assertEqual(provider_kwargs["class_record"]["name"], frozen_class_name)
        self.assertEqual(provider_kwargs["skill"]["name"], frozen_skill_name)
        self.assertEqual(provider_kwargs["request_timeout"], 300.0)
        self.assertEqual(provider_kwargs["max_retries"], 0)
        frozen_prompt_text = json.dumps(
            provider_kwargs["chat_request"], ensure_ascii=False
        )
        self.assertNotIn(live_transcript, frozen_prompt_text)
        self.assertNotIn("LIVE SKILL", frozen_prompt_text)
        self.assertNotIn(live_student["name"], frozen_prompt_text)
        self.assertNotIn("LIVE CLASS", frozen_prompt_text)
        saved = lesson_manager.get_class_commentary_generation(generation["id"])
        self.assertEqual(saved["confirmed_transcript_snapshot"], frozen_transcript)
        self.assertEqual(saved["skill_content_snapshot"], frozen_skill_content)
        self.assertEqual(
            [
                item["student_id"]
                for item in json.loads(saved["attending_roster_snapshot_json"])
            ],
            [item["id"] for item in self.students],
        )


if __name__ == "__main__":
    unittest.main()
