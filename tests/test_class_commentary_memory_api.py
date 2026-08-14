import hashlib
import importlib
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

import class_commentary_batch_context
import config_runtime
import lesson_manager


BATCH_READY_CAPABILITIES = {
    "memory_learning_enabled": True,
    "skill_evolution_enabled": True,
    "structured_feedback_enabled": True,
    "student_history_memory_v2_enabled": True,
    "batch_isolated_v3_enabled": True,
    "class_commentary_generation_call_count": 1,
    "student_history_memory_v2_max_credits_per_student": 10,
    "graph_enabled": True,
    "graph_healthy": True,
    "graph_degraded": False,
}


class ClassCommentaryMemoryApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.old_db_path = lesson_manager.DB_PATH
        self.old_cfg_path = config_runtime.CFG_PATH
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        self.skill_dir = self.base / "skills"
        self.skill_dir.mkdir()
        config_runtime.write_file_config(
            {
                "class_commentary_memory_enabled": True,
                "class_commentary_structured_feedback_enabled": True,
                "colleague_skill_dir": str(self.skill_dir),
            }
        )
        lesson_manager.init_db()
        self.app_module = importlib.import_module("app")
        self.app_module._CLASS_COMMENTARY_MEMORY_HEALTH_CACHE.update(
            {"config_key": "", "expires_at": 0.0, "payload": None}
        )
        self.client = self.app_module.app.test_client()
        login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(login.status_code, 200)
        payload = login.get_json()
        self.owner = payload["user"]
        self.headers = {"X-Auth-Token": payload["token"]}
        lesson_manager.insert_credit_ledger_entry(
            organization_id=self.owner["organization_id"],
            direction="credit",
            amount=100,
            source_type="manual_adjustment",
            source_id="class-commentary-memory-api-tests",
            note="test credits",
            operator_user_id=self.owner["id"],
        )

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db_path
        config_runtime.CFG_PATH = self.old_cfg_path
        self.temp_dir.cleanup()

    def _create_scope(self):
        class_id = lesson_manager.save_class(
            "数学记忆测试班",
            subject="数学",
            grade="七年级",
            organization_id=self.owner["organization_id"],
            teacher_user_id=self.owner["id"],
        )
        student = lesson_manager.create_student_for_class(class_id, "小王")
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path="",
            audio_filename="手动输入",
        )
        task = lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            "小王这次绝对值分类讨论遗漏了边界条件.",
        )
        source_path = self.skill_dir / "memory-api.skill"
        source_path.write_text("先说结论, 再给建议.", encoding="utf-8")
        skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.owner["organization_id"],
            skill_id="memory-api",
            actor_user_id=self.owner["id"],
            source_path=str(source_path),
        )
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=task["id"],
            generation_request_id="memory-api-generation",
            skill_registry_id=skill["registry_id"],
            attending_roster=[
                {"student_id": student["id"], "student_name": student["name"]}
            ],
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-v1",
            prompt_payload={"messages": []},
            memory_context={"records": []},
        )
        generation = lesson_manager.complete_class_commentary_generation(
            generation["id"],
            "小王: 绝对值分类讨论需要补全边界条件.",
        )
        return class_id, student, task, skill, generation

    def _confirm_learning(self, task, generation, request_id="memory-api-confirm"):
        return self.client.post(
            f"/api/class-commentary/tasks/{task['id']}/feedback-confirmations",
            headers=self.headers,
            json={
                "generation_id": generation["id"],
                "feedback_text": "小王: 分类讨论先列边界, 再逐段核对.",
                "learn": True,
                "expected_draft_version": 0,
                "request_id": request_id,
            },
        )

    @contextmanager
    def _batch_runtime(self, *, student_id: int, context: dict):
        teacher_style = context["teacher_style_memories"][0]
        student_history = {
            "memory_record_id": 10,
            "mem0_memory_id": "student-memory-10",
            "record_version": 1,
            "created_from_revision_id": 7,
            "created_at": "2026-08-12T10:00:00Z",
            "memory_type": "student_fact",
            "memory_text": "历史上分类讨论容易遗漏边界条件.",
            "student_id": int(student_id),
            "subject_key": "数学",
        }
        memory_snapshot = {
            "records": [teacher_style, student_history],
            "rendered_text": "",
            "student_history_memories": [student_history],
            "teacher_style_memories": [teacher_style],
            "student_history_memory_mode": "batch_isolated_v3",
            "retrieval_status": "ready",
            "degraded_reason": "",
        }

        def graph_context(**kwargs):
            graph_snapshot = {
                "schema_version": "class_commentary.student_graph_context.v1",
                "organization_id": int(kwargs["generation"]["organization_id"]),
                "student_id": int(student_id),
                "subject_key": str(kwargs["class_context"]["subject_key"]),
                "retrieval_status": "ready",
                "current_states": [
                    {
                        "knowledge_point_key": "absolute-value-boundary",
                        "knowledge_point_name": "绝对值边界条件",
                        "state": "improving",
                        "observed_at": "2026-08-12T10:00:00Z",
                    }
                ],
                "recent_changes": [],
                "allowed_evidence_refs": ["graph-ref-memory-api"],
                "semantica_snapshot_hash": "semantica-memory-api",
            }
            canonical = json.dumps(
                graph_snapshot,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            return {
                **graph_snapshot,
                "snapshot_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            }

        with patch.object(
            self.app_module,
            "has_class_commentary_api_key",
            return_value=True,
        ), patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=BATCH_READY_CAPABILITIES,
        ), patch.object(
            class_commentary_batch_context,
            "retrieve_isolated_student_memory_context",
            return_value=memory_snapshot,
        ) as retrieve_memory, patch.object(
            class_commentary_batch_context,
            "retrieve_isolated_student_graph_context",
            side_effect=graph_context,
        ) as retrieve_graph, patch.object(
            class_commentary_batch_context,
            "validate_isolated_student_memory_context_snapshot",
        ), patch.object(
            class_commentary_batch_context,
            "validate_isolated_student_graph_context_snapshot",
        ):
            yield retrieve_memory, retrieve_graph

    def test_routine_capability_uses_worker_readiness_without_mem0_probe(self):
        memory_service = Mock()
        with patch.object(
            self.app_module,
            "_get_class_commentary_memory_service",
            return_value=memory_service,
        ), patch.object(
            self.app_module,
            "class_commentary_memory_queue_healthcheck",
            return_value={"enabled": True, "healthy": True, "status": "ready"},
        ):
            ready = self.app_module._class_commentary_memory_capabilities()

        self.assertEqual(
            ready,
            {"memory_learning_enabled": True, "skill_evolution_enabled": True},
        )
        memory_service.healthcheck.assert_not_called()

    def test_capability_requires_mem0_and_queue_health(self):
        memory_service = Mock()
        memory_service.healthcheck.return_value = {
            "enabled": True,
            "healthy": True,
            "status": "ready",
        }
        with patch.object(
            self.app_module,
            "_get_class_commentary_memory_service",
            return_value=memory_service,
        ), patch.object(
            self.app_module,
            "class_commentary_memory_queue_healthcheck",
            return_value={"enabled": True, "healthy": True, "status": "ready"},
        ):
            ready = self.app_module._class_commentary_memory_capabilities(force=True)
        self.assertEqual(
            ready,
            {"memory_learning_enabled": True, "skill_evolution_enabled": True},
        )

        with patch.object(
            self.app_module,
            "_get_class_commentary_memory_service",
            return_value=memory_service,
        ), patch.object(
            self.app_module,
            "class_commentary_memory_queue_healthcheck",
            return_value={"enabled": True, "healthy": False, "status": "no_workers"},
        ):
            unavailable = self.app_module._class_commentary_memory_capabilities(force=True)
        self.assertFalse(unavailable["memory_learning_enabled"])
        self.assertFalse(unavailable["skill_evolution_enabled"])

    def test_confirmation_survives_queue_failure_and_exposes_queued_summary(self):
        _, _, task, _, generation = self._create_scope()
        with patch.object(
            self.app_module,
            "dispatch_class_commentary_memory_work",
            side_effect=ConnectionError("redis unavailable"),
        ):
            response = self._confirm_learning(task, generation)

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["revision"]["learn_requested"])
        self.assertEqual(payload["memory"]["status"], "queued")
        revision_id = payload["revision"]["id"]
        saved = lesson_manager.get_class_commentary_revision(revision_id)
        job = lesson_manager.get_class_commentary_memory_extraction_job_for_revision(
            revision_id
        )
        self.assertIsNotNone(saved)
        self.assertEqual(job["status"], "queued")

    def test_memory_list_and_revoke_are_owner_scoped_and_idempotent(self):
        _, _, task, _, generation = self._create_scope()
        with patch.object(
            self.app_module,
            "_dispatch_class_commentary_memory_best_effort",
            return_value={"enabled": True},
        ):
            confirmation = self._confirm_learning(task, generation)
        revision_id = confirmation.get_json()["revision"]["id"]
        job = lesson_manager.get_class_commentary_memory_extraction_job_for_revision(
            revision_id
        )
        claimed = lesson_manager.claim_class_commentary_memory_extraction_job(
            job["id"],
            claim_owner="api-test",
        )
        committed = lesson_manager.commit_class_commentary_memory_extraction(
            job["id"],
            claim_token=claimed["claim_token"],
            items=[
                {
                    "memory_type": "teacher_style",
                    "memory_text": "建议先说结论, 再分点说明.",
                    "confidence": 0.9,
                    "evidence": {"support": ["老师终稿调整了表达顺序"]},
                }
            ],
        )
        evidence_id = committed["evidence"][0]["id"]

        listed = self.client.get(
            f"/api/class-commentary/revisions/{revision_id}/memories",
            headers=self.headers,
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["status"], "syncing")
        self.assertEqual(listed.get_json()["memories"][0]["evidence_id"], evidence_id)
        self.assertTrue(listed.get_json()["memories"][0]["can_revoke"])

        with patch.object(
            self.app_module,
            "_dispatch_class_commentary_memory_best_effort",
            return_value={"enabled": True},
        ):
            first = self.client.post(
                f"/api/class-commentary/memory-evidence/{evidence_id}/revoke",
                headers=self.headers,
                json={"request_id": "memory-api-revoke"},
            )
            replay = self.client.post(
                f"/api/class-commentary/memory-evidence/{evidence_id}/revoke",
                headers=self.headers,
                json={"request_id": "memory-api-revoke"},
            )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(
            first.get_json()["memory"]["memories"][0]["evidence_status"],
            "revoked",
        )
        with lesson_manager.get_conn() as conn:
            event_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_memory_evidence_events WHERE evidence_id=?",
                (evidence_id,),
            ).fetchone()[0]
        self.assertEqual(event_count, 1)

    def test_failed_revision_retry_is_idempotent(self):
        _, _, task, _, generation = self._create_scope()
        with patch.object(
            self.app_module,
            "_dispatch_class_commentary_memory_best_effort",
            return_value={"enabled": True},
        ):
            confirmation = self._confirm_learning(task, generation)
        revision_id = confirmation.get_json()["revision"]["id"]
        job = lesson_manager.get_class_commentary_memory_extraction_job_for_revision(
            revision_id
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE class_commentary_memory_extraction_jobs SET status='failed' WHERE id=?",
                (job["id"],),
            )

        with patch.object(
            self.app_module,
            "_dispatch_class_commentary_memory_best_effort",
            return_value={"enabled": True},
        ):
            first = self.client.post(
                f"/api/class-commentary/revisions/{revision_id}/memory-retry",
                headers=self.headers,
                json={"request_id": "memory-api-retry"},
            )
            replay = self.client.post(
                f"/api/class-commentary/revisions/{revision_id}/memory-retry",
                headers=self.headers,
                json={"request_id": "memory-api-retry"},
            )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.get_json()["memory"]["status"], "queued")
        with lesson_manager.get_conn() as conn:
            retry_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_memory_retry_events WHERE revision_id=?",
                (revision_id,),
            ).fetchone()[0]
        self.assertEqual(retry_count, 1)

    def test_generation_injects_retrieved_context_and_freezes_snapshot(self):
        class_id, student, task, skill, _ = self._create_scope()
        context = {
            "records": [
                {
                    "memory_record_id": 9,
                    "mem0_memory_id": "style-memory-9",
                    "record_version": 2,
                    "created_from_revision_id": 6,
                    "created_at": "2026-08-12T10:00:00Z",
                    "memory_type": "teacher_style",
                    "memory_text": "先说结论.",
                }
            ],
            "rendered_text": "Teacher style: 先说结论.",
            "student_history_memories": [],
            "teacher_style_memories": [
                {
                    "memory_record_id": 9,
                    "mem0_memory_id": "style-memory-9",
                    "record_version": 2,
                    "created_from_revision_id": 6,
                    "created_at": "2026-08-12T10:00:00Z",
                    "memory_type": "teacher_style",
                    "memory_text": "先说结论.",
                }
            ],
            "retrieval_status": "ready",
            "degraded_reason": "",
        }

        def fake_charge(**kwargs):
            result = kwargs["producer"]()
            return result[0] if isinstance(result, tuple) else result

        model_output = json.dumps(
            {
                "schema_version": "class_commentary.student_feedback.v1",
                "items": [
                    {
                        "student_id": int(student["id"]),
                        "feedback_text": "先补全分类边界, 再逐段核对🌱.",
                    }
                ],
                "used_graph_evidence_refs_by_student": [
                    {
                        "student_id": int(student["id"]),
                        "evidence_refs": ["graph-ref-memory-api"],
                    }
                ],
            },
            ensure_ascii=False,
        )

        with self._batch_runtime(
            student_id=int(student["id"]),
            context=context,
        ) as (retrieve_memory, retrieve_graph), patch.object(
            self.app_module,
            "_run_ai_feature_with_charge",
            side_effect=fake_charge,
        ), patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
            return_value=(model_output, {"input_tokens": 1, "output_tokens": 1}),
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    "request_id": "memory-api-rag-generation",
                    "skill_id": skill["skill_id"],
                    "attending_student_ids": [student["id"]],
                },
            )

        self.assertEqual(response.status_code, 200)
        retrieve_memory.assert_called_once()
        retrieve_graph.assert_called_once()
        self.assertEqual(retrieve_memory.call_args.kwargs["student_id"], student["id"])
        self.assertEqual(retrieve_graph.call_args.kwargs["student_id"], student["id"])
        generate.assert_called_once()
        chat_request = generate.call_args.kwargs["chat_request"]
        self.assertIn("先说结论.", json.dumps(chat_request, ensure_ascii=False))
        self.assertIn(
            "历史上分类讨论容易遗漏边界条件.",
            json.dumps(chat_request, ensure_ascii=False),
        )
        self.assertIn("绝对值边界条件", json.dumps(chat_request, ensure_ascii=False))
        saved = lesson_manager.get_class_commentary_generation(
            response.get_json()["generation_id"]
        )
        saved_context = json.loads(saved["memory_context_snapshot_json"])
        self.assertEqual(saved["student_history_memory_mode"], "batch_isolated_v3")
        self.assertEqual(
            saved_context["student_contexts_by_id"][0]["memory_context"]["records"],
            [
                context["teacher_style_memories"][0],
                retrieve_memory.return_value["student_history_memories"][0],
            ],
        )


if __name__ == "__main__":
    unittest.main()
