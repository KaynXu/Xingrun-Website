import hashlib
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import config_runtime
import lesson_manager
from class_commentary import CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION


class ClassCommentaryLearningGraphApiTest(unittest.TestCase):
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
                "class_commentary_graph_enabled": True,
                "class_commentary_graph_store_path": str(self.base / "graph.json"),
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

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db_path
        config_runtime.CFG_PATH = self.old_cfg_path
        self.temp_dir.cleanup()

    @staticmethod
    def _canonical_json(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _create_scope(self, suffix="one"):
        class_id = lesson_manager.save_class(
            f"图谱测试班-{suffix}",
            subject="数学",
            grade="七年级",
            organization_id=self.owner["organization_id"],
            teacher_user_id=self.owner["id"],
        )
        student = lesson_manager.create_student_for_class(class_id, f"学生甲-{suffix}")
        other_student = lesson_manager.create_student_for_class(
            class_id,
            f"学生乙-{suffix}",
        )
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path="",
            audio_filename="手动输入",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            f"{student['name']}的二次函数图像理解有所改善.",
        )
        source_path = self.skill_dir / f"graph-api-{suffix}.skill"
        source_path.write_text("先写观察, 再给下一步.", encoding="utf-8")
        skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.owner["organization_id"],
            skill_id=f"graph-api-{suffix}",
            actor_user_id=self.owner["id"],
            source_path=str(source_path),
        )
        roster = [{"student_id": student["id"], "student_name": student["name"]}]
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=task["id"],
            generation_request_id=f"graph-api-generation-{suffix}",
            skill_registry_id=skill["registry_id"],
            attending_roster=roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-v1",
            prompt_payload={"messages": []},
            memory_context={"records": []},
        )
        feedback_text = "二次函数图像由薄弱进展到发展中, 下一步练习图像与参数联动."
        generation = lesson_manager.complete_class_commentary_generation(
            generation["id"],
            f"{student['name']}: {feedback_text}",
        )
        structured = {
            "schema_version": "class_commentary.student_feedback.v1",
            "items": [{"student_id": student["id"], "feedback_text": feedback_text}],
        }
        structured_json = self._canonical_json(structured)
        structured_hash = hashlib.sha256(structured_json.encode("utf-8")).hexdigest()
        scope_hash = lesson_manager.build_class_commentary_eligible_scope_hash(
            transcript_hash=generation["confirmed_transcript_hash"],
            roster_hash=generation["attending_roster_hash"],
            eligible_student_ids=[student["id"]],
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET feedback_schema_version='class_commentary.student_feedback.v1',
                    structured_feedback_json=?, structured_feedback_hash=?,
                    generated_feedback_text=?,
                    eligible_student_ids_json=?, eligible_student_scope_hash=?,
                    student_mention_matcher_version='class_commentary.student_name_matcher.v1',
                    response_format_json='{"type":"json_object"}',
                    student_history_memory_mode='disabled_v1', prompt_version=?
                WHERE id=?
                """,
                (
                    structured_json,
                    structured_hash,
                    f"{student['name']}:\n{feedback_text}",
                    self._canonical_json([student["id"]]),
                    scope_hash,
                    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
                    generation["id"],
                ),
            )
        return {
            "class_id": class_id,
            "student": student,
            "other_student": other_student,
            "task": lesson_manager.get_class_commentary_task(task["id"]),
            "generation": lesson_manager.get_class_commentary_generation(generation["id"]),
            "feedback_text": feedback_text,
        }

    def _confirm(self, scope, *, learn=True, request_id="graph-confirm"):
        return self.client.post(
            f"/api/class-commentary/tasks/{scope['task']['id']}/feedback-confirmations",
            headers=self.headers,
            json={
                "generation_id": scope["generation"]["id"],
                "feedback_schema_version": "class_commentary.student_feedback.v1",
                "student_feedback_items": [
                    {
                        "student_id": scope["student"]["id"],
                        "feedback_text": scope["feedback_text"],
                    }
                ],
                "learn": learn,
                "expected_draft_version": 0,
                "expected_latest_revision_id": None,
                "request_id": request_id,
            },
        )

    def test_schema_confirmation_and_replay_create_one_graph_job(self):
        scope = self._create_scope()
        with patch.object(
            self.app_module,
            "_dispatch_class_commentary_memory_best_effort",
            return_value={"enabled": True},
        ), patch.object(
            self.app_module,
            "_dispatch_class_commentary_graph_best_effort",
            return_value={"enabled": True},
        ):
            first = self._confirm(scope)
            replay = self._confirm(scope)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        revision_id = first.get_json()["revision_id"]
        self.assertEqual(replay.get_json()["revision_id"], revision_id)
        with lesson_manager.get_conn() as conn:
            revision_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_revisions WHERE task_id=?",
                (scope["task"]["id"],),
            ).fetchone()[0]
            memory_jobs = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_memory_extraction_jobs WHERE revision_id=?",
                (revision_id,),
            ).fetchone()[0]
            graph_jobs = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_graph_extraction_jobs WHERE revision_id=?",
                (revision_id,),
            ).fetchone()[0]
        self.assertEqual((revision_count, memory_jobs, graph_jobs), (1, 1, 1))

    def test_confirmation_without_learning_has_no_graph_job(self):
        scope = self._create_scope("no-learn")
        response = self._confirm(scope, learn=False, request_id="graph-no-learn")
        self.assertEqual(response.status_code, 200)
        revision_id = response.get_json()["revision_id"]
        with lesson_manager.get_conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_graph_extraction_jobs WHERE revision_id=?",
                (revision_id,),
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_raw_transcript_and_unconfirmed_draft_never_create_graph_work(self):
        scope = self._create_scope("unconfirmed")
        lesson_manager.save_class_commentary_feedback_draft(
            task_id=scope["task"]["id"],
            generation_id=scope["generation"]["id"],
            teacher_user_id=self.owner["id"],
            expected_draft_version=0,
            feedback_schema_version="class_commentary.student_feedback.v1",
            student_feedback_items=[
                {
                    "student_id": scope["student"]["id"],
                    "feedback_text": scope["feedback_text"],
                }
            ],
        )
        with lesson_manager.get_conn() as conn:
            counts = tuple(
                conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "class_commentary_revisions",
                    "class_commentary_graph_extraction_jobs",
                    "class_commentary_student_learning_events",
                )
            )
        self.assertEqual(counts, (0, 0, 0))

    def test_graph_dispatch_failure_does_not_rollback_confirmation(self):
        scope = self._create_scope("dispatch-failure")
        with patch.object(
            self.app_module,
            "dispatch_class_commentary_graph_work",
            side_effect=ConnectionError("redis unavailable"),
        ), patch.object(
            self.app_module,
            "_dispatch_class_commentary_memory_best_effort",
            return_value={"enabled": True},
        ):
            response = self._confirm(
                scope,
                request_id="graph-dispatch-failure",
            )
        self.assertEqual(response.status_code, 200)
        revision_id = response.get_json()["revision_id"]
        with lesson_manager.get_conn() as conn:
            job = conn.execute(
                "SELECT status FROM class_commentary_graph_extraction_jobs WHERE revision_id=?",
                (revision_id,),
            ).fetchone()
        self.assertEqual(job["status"], "queued")

    def test_summary_enforces_task_student_and_generation_scope(self):
        scope = self._create_scope("summary")
        expected = {
            "organization_id": self.owner["organization_id"],
            "task_id": scope["task"]["id"],
            "student_id": scope["student"]["id"],
            "subject_key": "math",
            "sync_status": "pending",
            "can_retry": True,
            "error": "",
            "current_states": [],
            "timeline": [],
            "used_graph_evidence_refs": [],
        }
        with patch.object(
            self.app_module,
            "get_student_learning_graph_summary",
            return_value=expected,
        ) as summary:
            response = self.client.get(
                f"/api/class-commentary/tasks/{scope['task']['id']}/students/"
                f"{scope['student']['id']}/learning-graph?generation_id={scope['generation']['id']}",
                headers=self.headers,
            )
            out_of_roster = self.client.get(
                f"/api/class-commentary/tasks/{scope['task']['id']}/students/"
                f"{scope['other_student']['id']}/learning-graph?generation_id={scope['generation']['id']}",
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["learning_graph"], expected)
        self.assertEqual(out_of_roster.status_code, 404)
        summary.assert_called_once_with(
            organization_id=self.owner["organization_id"],
            task_id=scope["task"]["id"],
            student_id=scope["student"]["id"],
            subject_key="math",
            generation_id=scope["generation"]["id"],
            event_limit=24,
        )

    def test_retry_is_owned_validated_and_idempotent(self):
        scope = self._create_scope("retry")
        with patch.object(
            self.app_module,
            "_dispatch_class_commentary_memory_best_effort",
            return_value={"enabled": True},
        ), patch.object(
            self.app_module,
            "_dispatch_class_commentary_graph_best_effort",
            return_value={"enabled": True},
        ):
            confirmation = self._confirm(scope, request_id="graph-retry-confirm")
            revision_id = confirmation.get_json()["revision_id"]
            missing_request = self.client.post(
                f"/api/class-commentary/revisions/{revision_id}/graph-retry",
                headers=self.headers,
                json={},
            )
            first = self.client.post(
                f"/api/class-commentary/revisions/{revision_id}/graph-retry",
                headers=self.headers,
                json={"request_id": "graph-retry-request"},
            )
            replay = self.client.post(
                f"/api/class-commentary/revisions/{revision_id}/graph-retry",
                headers=self.headers,
                json={"request_id": "graph-retry-request"},
            )

        self.assertEqual(missing_request.status_code, 400)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.get_json()["graph_job"]["id"], replay.get_json()["graph_job"]["id"])
        with lesson_manager.get_conn() as conn:
            retry_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_graph_retry_events WHERE request_id=?",
                ("graph-retry-request",),
            ).fetchone()[0]
        self.assertEqual(retry_count, 1)

    def test_graph_capabilities_and_no_public_explorer(self):
        adapter = Mock()
        adapter.readiness.return_value = {"healthy": True}
        with patch.object(
            self.app_module,
            "SemanticaGraphAdapter",
            return_value=adapter,
        ), patch.object(
            self.app_module,
            "class_commentary_memory_queue_healthcheck",
            return_value={"healthy": True},
        ):
            healthy = self.app_module._class_commentary_graph_capabilities()
        adapter.readiness.assert_called_once_with()
        adapter.health.assert_not_called()
        adapter.readiness.return_value = {"healthy": False}
        with patch.object(
            self.app_module,
            "SemanticaGraphAdapter",
            return_value=adapter,
        ), patch.object(
            self.app_module,
            "class_commentary_memory_queue_healthcheck",
            return_value={"healthy": True},
        ):
            degraded = self.app_module._class_commentary_graph_capabilities()
        adapter.health.return_value = {"healthy": True}
        with patch.object(
            self.app_module,
            "SemanticaGraphAdapter",
            return_value=adapter,
        ), patch.object(
            self.app_module,
            "class_commentary_memory_queue_healthcheck",
            return_value={"healthy": True},
        ):
            forced = self.app_module._class_commentary_graph_capabilities(force=True)

        self.assertEqual(
            healthy,
            {"graph_enabled": True, "graph_healthy": True, "graph_degraded": False},
        )
        self.assertEqual(
            degraded,
            {"graph_enabled": True, "graph_healthy": False, "graph_degraded": True},
        )
        self.assertEqual(
            forced,
            {"graph_enabled": True, "graph_healthy": True, "graph_degraded": False},
        )
        adapter.health.assert_called_once_with()
        explorer = self.client.get(
            "/api/class-commentary/graph-explorer",
            headers=self.headers,
        )
        arbitrary_query = self.client.post(
            "/api/class-commentary/graph-query",
            headers=self.headers,
            json={"query": "MATCH (n) RETURN n"},
        )
        self.assertEqual(explorer.status_code, 404)
        self.assertEqual(arbitrary_query.status_code, 404)

    def test_student_run_persists_graph_snapshot_allowlist_and_used_refs(self):
        scope = self._create_scope("student-run")
        empty_hash = hashlib.sha256(b"{}").hexdigest()
        with lesson_manager.get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO class_commentary_student_generation_runs (
                    organization_id, generation_id, student_id,
                    student_name_snapshot, request_id, request_payload_hash,
                    prompt_version, memory_mode,
                    current_evidence_snapshot_json, current_evidence_hash,
                    memory_context_snapshot_json, memory_context_hash,
                    provider, model, model_parameters_json,
                    prompt_payload_snapshot_json, prompt_payload_hash,
                    status, claim_token, claim_owner, charge_request_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, '{}', ?, ?, ?, '{}',
                          '{}', ?, 'generating', ?, ?, ?)
                """,
                (
                    self.owner["organization_id"],
                    scope["generation"]["id"],
                    scope["student"]["id"],
                    scope["student"]["name"],
                    "graph-student-run",
                    "graph-student-run-hash",
                    "class-commentary-student-memory-v2",
                    "isolated_v2",
                    empty_hash,
                    empty_hash,
                    "openai",
                    "test-model",
                    empty_hash,
                    "graph-student-run-claim",
                    "test-worker",
                    "graph-student-run-charge",
                ),
            )
            run_id = int(cursor.lastrowid)
            conn.execute(
                """
                UPDATE class_commentary_student_generation_runs
                SET memory_retrieval_status='empty',
                    memory_context_snapshot_json='{}', memory_context_hash=?,
                    graph_retrieval_status='pending'
                WHERE id=?
                """,
                (empty_hash, run_id),
            )
        graph_context = {
            "organization_id": self.owner["organization_id"],
            "student_id": scope["student"]["id"],
            "subject_key": "math",
            "allowed_evidence_refs": ["evidence:test:1"],
        }
        finalized = lesson_manager.finalize_class_commentary_student_generation_prompt(
            run_id,
            claim_token="graph-student-run-claim",
            memory_context={},
            memory_retrieval_status="empty",
            graph_context=graph_context,
            graph_retrieval_status="ready",
            graph_allowed_evidence_refs=["evidence:test:1"],
            prompt_payload={"messages": []},
        )
        structured_json = self._canonical_json(
            {
                "schema_version": "class_commentary.student_feedback.v1",
                "items": [
                    {
                        "student_id": scope["student"]["id"],
                        "feedback_text": "继续练习图像与参数联动.",
                    }
                ],
            }
        )
        structured_hash = hashlib.sha256(structured_json.encode("utf-8")).hexdigest()
        persisted = lesson_manager.persist_class_commentary_student_generation_response(
            run_id,
            claim_token="graph-student-run-claim",
            response_snapshot={"response_text": structured_json},
            structured_feedback_json=structured_json,
            structured_feedback_hash=structured_hash,
            used_graph_evidence_refs=["evidence:test:1"],
        )

        self.assertEqual(finalized["graph_retrieval_status"], "ready")
        self.assertEqual(
            json.loads(finalized["graph_context_snapshot_json"]),
            graph_context,
        )
        self.assertEqual(
            json.loads(finalized["graph_allowed_evidence_refs_json"]),
            ["evidence:test:1"],
        )
        self.assertEqual(
            json.loads(persisted["used_graph_evidence_refs_json"]),
            ["evidence:test:1"],
        )


if __name__ == "__main__":
    unittest.main()
