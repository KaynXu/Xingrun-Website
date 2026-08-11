import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_runtime
import lesson_manager


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
            "student_history_memory_v2_max_credits_per_student": 10,
        }

    def test_kill_switch_on_reserves_async_runs_and_returns_safe_progress(self):
        with patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=self._enabled_capabilities(),
        ), patch.object(
            self.app_module, "has_class_commentary_api_key", return_value=True
        ), patch.object(
            self.app_module,
            "_dispatch_class_commentary_memory_best_effort",
            return_value={"enabled": True},
        ) as dispatch, patch.object(
            self.app_module, "generate_class_commentary_feedback"
        ) as synchronous_generator:
            response = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generate",
                headers=self.headers,
                json=self._request_payload(),
            )

        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertEqual(payload["status"], "generating")
        self.assertEqual(payload["student_history_memory_mode"], "isolated_v2")
        self.assertEqual(
            payload["prompt_version"], "class-commentary-student-feedback-isolated-v2"
        )
        self.assertEqual(
            payload["student_run_progress"],
            {
                "total": 2,
                "queued": 2,
                "generating": 0,
                "succeeded": 0,
                "failed": 0,
                "runs": [
                    {
                        "id": payload["student_run_progress"]["runs"][0]["id"],
                        "student_id": self.students[0]["id"],
                        "student_name": self.students[0]["name"],
                        "status": "queued",
                        "attempt_count": 0,
                        "memory_retrieval_status": "pending",
                        "charge_status": "pending",
                        "error_code": "",
                        "created_at": payload["student_run_progress"]["runs"][0]["created_at"],
                        "started_at": "",
                        "completed_at": "",
                    },
                    {
                        "id": payload["student_run_progress"]["runs"][1]["id"],
                        "student_id": self.students[1]["id"],
                        "student_name": self.students[1]["name"],
                        "status": "queued",
                        "attempt_count": 0,
                        "memory_retrieval_status": "pending",
                        "charge_status": "pending",
                        "error_code": "",
                        "created_at": payload["student_run_progress"]["runs"][1]["created_at"],
                        "started_at": "",
                        "completed_at": "",
                    },
                ],
            },
        )
        self.assertEqual(payload["student_feedback_items"], [])
        self.assertEqual(payload["generated_feedback_text"], "")
        self.assertNotIn("prompt_payload_snapshot_json", json.dumps(payload))
        self.assertNotIn("memory_context_snapshot_json", json.dumps(payload))
        dispatch.assert_called_once_with()
        synchronous_generator.assert_not_called()

        detail = self.client.get(
            f"/api/class-commentary/tasks/{self.task['id']}/generations/{payload['generation_id']}",
            headers=self.headers,
        )
        self.assertEqual(detail.status_code, 200)
        detail_payload = detail.get_json()
        for run in detail_payload["student_run_progress"]["runs"]:
            self.assertNotIn("prompt", run)
            self.assertNotIn("memory_context", run)
            self.assertNotIn("response_snapshot", run)

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

    def test_maximum_multi_student_credit_preflight_blocks_before_reservation(self):
        lesson_manager.insert_credit_ledger_entry(
            organization_id=self.user["organization_id"],
            direction="debit",
            amount=90,
            source_type="manual_adjustment",
            source_id="reduce-test-balance",
            note="leave ten credits",
            operator_user_id=self.user["id"],
        )
        with patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=self._enabled_capabilities(),
        ), patch.object(
            self.app_module, "has_class_commentary_api_key", return_value=True
        ), patch.object(
            self.app_module, "_dispatch_class_commentary_memory_best_effort"
        ) as dispatch:
            response = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generate",
                headers=self.headers,
                json=self._request_payload("insufficient-multi-student-credit"),
            )
        self.assertEqual(response.status_code, 402)
        with lesson_manager.get_conn() as conn:
            generation_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_generations WHERE task_id=?",
                (self.task["id"],),
            ).fetchone()[0]
        self.assertEqual(generation_count, 0)
        dispatch.assert_not_called()

    def test_kill_switch_off_keeps_disabled_v1_synchronous_contract(self):
        disabled_capabilities = {
            **self._enabled_capabilities(),
            "student_history_memory_v2_enabled": False,
        }
        model_output = json.dumps(
            {
                "schema_version": "class_commentary.student_feedback.v1",
                "items": [
                    {
                        "student_id": student["id"],
                        "feedback_text": "本节课有进步, 请继续练习.",
                    }
                    for student in self.students
                ],
            },
            ensure_ascii=False,
        )

        def fake_charge(**kwargs):
            result = kwargs["producer"]()
            return result[0] if isinstance(result, tuple) else result

        with patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=disabled_capabilities,
        ), patch.object(
            self.app_module, "has_class_commentary_api_key", return_value=True
        ), patch.object(
            self.app_module,
            "retrieve_class_commentary_memory_context",
            return_value={
                "records": [],
                "rendered_text": "",
                "student_history_memories": [],
                "teacher_style_memories": [],
                "student_history_memory_mode": "disabled_v1",
                "retrieval_status": "empty",
                "degraded_reason": "",
            },
        ), patch.object(
            self.app_module, "_run_ai_feature_with_charge", side_effect=fake_charge
        ), patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
            return_value=(
                model_output,
                {"provider": "openai", "model": "fake", "input_tokens": 5, "output_tokens": 5},
            ),
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generate",
                headers=self.headers,
                json=self._request_payload("kill-switch-off"),
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["student_history_memory_mode"], "disabled_v1")
        self.assertEqual(payload["student_run_progress"]["total"], 0)
        generate.assert_called_once()

    def test_failed_student_run_retry_api_is_idempotent_and_keeps_successes_untouched(self):
        with patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=self._enabled_capabilities(),
        ), patch.object(
            self.app_module, "has_class_commentary_api_key", return_value=True
        ), patch.object(
            self.app_module,
            "_dispatch_class_commentary_memory_best_effort",
            return_value={"enabled": True},
        ):
            created = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generate",
                headers=self.headers,
                json=self._request_payload("retry-api-generation"),
            ).get_json()
        generation_id = created["generation_id"]
        runs = lesson_manager.list_class_commentary_student_generation_runs(
            generation_id
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_student_generation_runs
                SET status='failed', error_code='provider_request_rejected',
                    completed_at='2026-01-01T00:00:00Z'
                WHERE id=?
                """,
                (runs[0]["id"],),
            )
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET status='failed', error_code='student_run_failed'
                WHERE id=?
                """,
                (generation_id,),
            )
            conn.execute(
                "UPDATE class_commentary_tasks SET status='failed' WHERE id=?",
                (self.task["id"],),
            )

        retry_payload = {
            "request_id": "retry-api-request",
            "student_ids": [runs[0]["student_id"]],
        }
        with patch.object(
            self.app_module,
            "_dispatch_class_commentary_memory_best_effort",
            return_value={"enabled": True},
        ) as dispatch:
            first = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generations/{generation_id}/student-runs/retry",
                headers=self.headers,
                json=retry_payload,
            )
            second = self.client.post(
                f"/api/class-commentary/tasks/{self.task['id']}/generations/{generation_id}/student-runs/retry",
                headers=self.headers,
                json=retry_payload,
            )
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 202)
        self.assertEqual(first.get_json()["student_run_progress"]["queued"], 2)
        after = lesson_manager.list_class_commentary_student_generation_runs(
            generation_id
        )
        self.assertEqual(after[0]["status"], "retry_wait")
        self.assertEqual(after[1]["status"], "queued")
        self.assertEqual(after[1]["attempt_count"], 0)
        self.assertEqual(dispatch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
