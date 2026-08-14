import io
import importlib
import hashlib
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager
import class_commentary_batch_context
from class_commentary import (
    CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V6,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
    build_class_commentary_chat_request,
)


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


class ClassCommentaryApiTestCase(unittest.TestCase):
    PRIVATE_TRANSCRIPT_POLISH_FIELDS = {
        "raw_transcript_text",
        "roster_snapshot",
        "transcript_polish_error",
        "transcript_polished_at",
    }

    def setUp(self):
        self.structured_env_patch = patch.dict(
            os.environ,
            {"XR_CLASS_COMMENTARY_STRUCTURED_FEEDBACK_ENABLED": ""},
            clear=False,
        )
        self.structured_env_patch.start()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.old_db_path = lesson_manager.DB_PATH
        self.old_cfg_path = config_runtime.CFG_PATH
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        self.skill_dir = self.base / "skills"
        self.skill_dir.mkdir(parents=True, exist_ok=True)
        config_runtime.write_file_config({"colleague_skill_dir": str(self.skill_dir)})
        lesson_manager.init_db()

        self.app_module = importlib.import_module("app")
        self.upload_patch = patch.object(self.app_module, "UPLOAD_DIR", self.base / "uploads")
        self.upload_patch.start()
        self.client = self.app_module.app.test_client()

        login = self.client.post("/api/login", json={"username": "Kayn", "password": "xingrun2026"})
        self.assertEqual(login.status_code, 200)
        payload = login.get_json()
        self.assertIsNotNone(payload)
        self.owner = payload["user"]
        self.owner_token = payload["token"]
        self.headers = {"X-Auth-Token": self.owner_token}
        lesson_manager.insert_credit_ledger_entry(
            organization_id=self.owner["organization_id"],
            direction="credit",
            amount=100,
            source_type="manual_adjustment",
            source_id="class-commentary-api-tests",
            note="test credits",
            operator_user_id=self.owner["id"],
        )

    def tearDown(self):
        self.upload_patch.stop()
        self.structured_env_patch.stop()
        lesson_manager.DB_PATH = self.old_db_path
        config_runtime.CFG_PATH = self.old_cfg_path
        self.temp_dir.cleanup()

    def _create_class_with_student(self) -> int:
        class_id = lesson_manager.save_class(
            "数学·七年级·4班",
            subject="数学",
            grade="七年级",
            organization_id=self.owner["organization_id"],
            teacher_user_id=self.owner["id"],
        )
        lesson_manager.create_student_for_class(class_id, "小王")
        return class_id

    def _create_transcribed_task(self, class_id: int, transcript: str) -> dict:
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )
        return lesson_manager.mark_class_commentary_transcription_succeeded(task["id"], transcript)

    def _create_member(self, username: str, password: str = "memberpass123") -> tuple[int, str]:
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    lesson_manager.hash_password(password),
                    username,
                    "member",
                    "active",
                    self.owner["organization_id"],
                ),
            )
            member_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        login = self.client.post("/api/login", json={"username": username, "password": password})
        self.assertEqual(login.status_code, 200)
        return member_id, login.get_json()["token"]

    def _register_skill(
        self,
        skill_id: str = "teacher-a",
        content: str = "warm direct style",
        owner_user_id=None,
    ):
        teacher_user_id = int(owner_user_id or self.owner["id"])
        source_path = self.skill_dir / f"{skill_id}.skill"
        source_path.write_text(content, encoding="utf-8")
        return lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.owner["organization_id"],
            skill_id=skill_id,
            actor_user_id=teacher_user_id,
            source_path=str(source_path),
        )

    def _configure_batch_generation(self, **overrides) -> None:
        config_runtime.write_file_config({
            "colleague_skill_dir": str(self.skill_dir),
            "class_commentary_structured_feedback_enabled": True,
            **overrides,
        })

    @staticmethod
    def _batch_model_output(
        students: list[dict],
        *,
        feedback_by_student_id: dict[int, str] | None = None,
        reverse_items: bool = False,
    ) -> str:
        feedback_by_student_id = feedback_by_student_id or {}
        ordered_students = list(reversed(students)) if reverse_items else students
        return json.dumps(
            {
                "schema_version": "class_commentary.student_feedback.v1",
                "items": [
                    {
                        "student_id": int(student["id"]),
                        "feedback_text": feedback_by_student_id.get(
                            int(student["id"]),
                            "今天的课堂步骤更清楚了🌱.\n\n"
                            "请继续检查一个具体问题🔍.\n\n"
                            "下次先写完整过程, 再独立验算一次✨.",
                        ),
                    }
                    for student in ordered_students
                ],
                "used_graph_evidence_refs_by_student": [
                    {
                        "student_id": int(student["id"]),
                        "evidence_refs": [f"graph-ref-{int(student['id'])}"],
                    }
                    for student in ordered_students
                ],
            },
            ensure_ascii=False,
        )

    @contextmanager
    def _batch_runtime(self):
        def memory_context(**kwargs):
            student_id = int(kwargs["student_id"])
            teacher_style = {
                "memory_record_id": 7100,
                "mem0_memory_id": "style-memory-7100",
                "record_version": 1,
                "created_from_revision_id": 31,
                "created_at": "2026-08-12T10:00:00Z",
                "memory_type": "teacher_style",
                "memory_text": "Use short sentences and a warm emoji rhythm.",
            }
            student_history = {
                "memory_record_id": 8000 + student_id,
                "mem0_memory_id": f"student-memory-{student_id}",
                "record_version": 1,
                "created_from_revision_id": 40 + student_id,
                "created_at": "2026-08-12T10:00:00Z",
                "memory_type": "student_fact",
                "memory_text": f"history-only-for-{student_id}",
                "student_id": student_id,
                "subject_key": str(kwargs["generation"]["subject_key"]),
            }
            return {
                "records": [teacher_style, student_history],
                "rendered_text": "",
                "student_history_memories": [student_history],
                "teacher_style_memories": [teacher_style],
                "retrieval_status": "ready",
                "degraded_reason": "",
                "student_history_memory_mode": "batch_isolated_v3",
            }

        def graph_context(**kwargs):
            student_id = int(kwargs["student_id"])
            context = {
                "schema_version": "class_commentary.student_graph_context.v1",
                "organization_id": int(kwargs["generation"]["organization_id"]),
                "student_id": student_id,
                "subject_key": str(kwargs["class_context"]["subject_key"]),
                "retrieval_status": "ready",
                "current_states": [
                    {
                        "knowledge_point_key": f"knowledge-{student_id}",
                        "knowledge_point_name": f"graph-only-for-{student_id}",
                        "state": "improving",
                        "observed_at": "2026-08-12T10:00:00Z",
                    }
                ],
                "recent_changes": [],
                "allowed_evidence_refs": [f"graph-ref-{student_id}"],
                "semantica_snapshot_hash": f"semantica-snapshot-{student_id}",
            }
            canonical = json.dumps(
                context,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            return {
                **context,
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
            side_effect=memory_context,
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
            yield {
                "retrieve_memory": retrieve_memory,
                "retrieve_graph": retrieve_graph,
            }

    def _create_succeeded_generation(
        self,
        task: dict,
        skill: dict,
        request_id: str = "generation-request-setup",
        feedback_text: str = "小王: 今天计算有进步.",
    ) -> dict:
        roster = [
            {"student_id": student["id"], "student_name": student["name"]}
            for student in lesson_manager.list_students_for_class(int(task["class_id"]))
        ]
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=int(task["id"]),
            generation_request_id=request_id,
            skill_registry_id=int(skill["registry_id"]),
            attending_roster=roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-v1",
            prompt_payload={"messages": [{"role": "user", "content": "生成课堂反馈"}]},
            memory_context={"records": [], "rendered_text": ""},
        )
        return lesson_manager.complete_class_commentary_generation(
            int(generation["id"]),
            feedback_text,
        )

    def _promote_generation_to_structured(
        self,
        generation: dict,
        feedback_by_student_id: dict[int, str],
    ) -> dict:
        generation = lesson_manager.get_class_commentary_generation(int(generation["id"]))
        roster = json.loads(generation["attending_roster_snapshot_json"])
        eligible_ids = [
            int(item["student_id"])
            for item in roster
            if int(item["student_id"]) in feedback_by_student_id
        ]
        names_by_id = {
            int(item["student_id"]): str(item["student_name"])
            for item in roster
        }
        structured_payload = {
            "schema_version": "class_commentary.student_feedback.v1",
            "items": [
                {
                    "student_id": student_id,
                    "feedback_text": feedback_by_student_id[student_id],
                }
                for student_id in eligible_ids
            ],
        }
        structured_json = json.dumps(
            structured_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        structured_hash = hashlib.sha256(structured_json.encode("utf-8")).hexdigest()
        derived_text = "\n\n".join(
            f"{names_by_id[student_id]}:\n{feedback_by_student_id[student_id]}"
            for student_id in eligible_ids
        )
        scope_hash = lesson_manager.build_class_commentary_eligible_scope_hash(
            transcript_hash=generation["confirmed_transcript_hash"],
            roster_hash=generation["attending_roster_hash"],
            eligible_student_ids=eligible_ids,
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
                    json.dumps(eligible_ids, separators=(",", ":")),
                    scope_hash,
                    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
                    generation["id"],
                ),
            )
        return lesson_manager.get_class_commentary_generation(int(generation["id"]))

    @staticmethod
    def _unwrap_payload(payload, key):
        nested = payload.get(key)
        return nested if isinstance(nested, dict) else payload

    def assertPrivateTranscriptPolishFieldsHidden(self, payload: dict):
        for field_name in self.PRIVATE_TRANSCRIPT_POLISH_FIELDS:
            self.assertNotIn(field_name, payload)

    def test_old_class_feedback_routes_are_removed(self):
        response = self.client.get("/api/class-feedback/labels", headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_structured_feedback_capability_defaults_false_and_accepts_config_or_env(self):
        env_name = "XR_CLASS_COMMENTARY_STRUCTURED_FEEDBACK_ENABLED"
        with patch.dict(os.environ, {env_name: ""}, clear=False):
            default_response = self.client.get(
                "/api/class-commentary/capabilities",
                headers=self.headers,
            )
            config_runtime.write_file_config({
                "colleague_skill_dir": str(self.skill_dir),
                "class_commentary_structured_feedback_enabled": True,
            })
            config_response = self.client.get(
                "/api/class-commentary/capabilities",
                headers=self.headers,
            )
            config_runtime.write_file_config({
                "colleague_skill_dir": str(self.skill_dir),
                "class_commentary_structured_feedback_enabled": False,
            })
            with patch.dict(os.environ, {env_name: "true"}, clear=False):
                env_response = self.client.get(
                    "/api/class-commentary/capabilities",
                    headers=self.headers,
                )

        self.assertEqual(default_response.status_code, 200)
        self.assertFalse(default_response.get_json()["structured_feedback_enabled"])
        self.assertEqual(config_response.status_code, 200)
        self.assertTrue(config_response.get_json()["structured_feedback_enabled"])
        self.assertEqual(env_response.status_code, 200)
        self.assertTrue(env_response.get_json()["structured_feedback_enabled"])

    def test_create_task_returns_transcribing_without_running_transcription_inline(self):
        class_id = self._create_class_with_student()
        started = {}

        def fake_start(task_id, audio_path, user, request_key):
            started["task_id"] = task_id
            started["audio_path"] = audio_path
            started["user_id"] = user["id"]
            started["request_key"] = request_key

        with patch.object(self.app_module, "_start_class_commentary_transcription_worker", fake_start):
            response = self.client.post(
                "/api/class-commentary/tasks",
                headers=self.headers,
                data={"class_id": str(class_id), "audio": (io.BytesIO(b"fake audio"), "lesson.m4a")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["status"], "transcribing")
        self.assertEqual(payload["audio_filename"], "lesson.m4a")
        self.assertEqual(started["task_id"], payload["id"])
        self.assertEqual(started["user_id"], self.owner["id"])
        self.assertTrue(started["request_key"])

    def test_worker_success_stores_raw_and_polished_transcript(self):
        class_id = self._create_class_with_student()
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )

        calls = []

        def fake_charge(**kwargs):
            calls.append(kwargs)
            if kwargs["feature_key"] == "class_commentary_transcribe":
                return "小汪今天绝对纸学得不错"
            if kwargs["feature_key"] == "class_commentary_transcript_polish":
                producer_result = kwargs["producer"]()
                self.assertEqual(producer_result[0], "小王今天绝对值学得不错")
                return producer_result[0]
            raise AssertionError(f"unexpected feature key: {kwargs['feature_key']}")

        with patch.object(self.app_module, "_run_ai_feature_with_charge", side_effect=fake_charge), \
             patch.object(self.app_module, "polish_class_commentary_transcript", return_value=("小王今天绝对值学得不错", {"provider": "test", "model": "chat"})) as polish:
            self.app_module._run_class_commentary_transcription(
                task["id"],
                str(self.base / "audio.m4a"),
                {"id": self.owner["id"], "organization_id": self.owner["organization_id"]},
                "saved-audio-request-key",
            )

        saved = lesson_manager.get_class_commentary_task(task["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "transcribed")
        self.assertEqual(saved["raw_transcript_text"], "小汪今天绝对纸学得不错")
        self.assertEqual(saved["transcript_text"], "小王今天绝对值学得不错")
        self.assertEqual(saved["confirmed_transcript_text"], "小王今天绝对值学得不错")
        self.assertEqual(saved["transcript_polish_error"], "")
        self.assertTrue(saved["transcript_polished_at"])
        self.assertIn('"name": "小王"', saved["roster_snapshot"])
        self.assertNotIn("parent_contact", saved["roster_snapshot"])
        self.assertEqual([call["feature_key"] for call in calls], ["class_commentary_transcribe", "class_commentary_transcript_polish"])
        self.assertEqual(calls[0]["request_key"], "saved-audio-request-key")
        self.assertEqual(calls[1]["request_key"], "saved-audio-request-key")
        self.assertEqual(calls[1]["source_record_type"], "class_commentary_transcript_polish")
        self.assertNotEqual(
            (calls[0]["feature_key"], calls[0]["source_record_type"], calls[0]["source_record_id"]),
            (calls[1]["feature_key"], calls[1]["source_record_type"], calls[1]["source_record_id"]),
        )
        polish.assert_called_once()

    def test_worker_polish_failure_falls_back_to_raw_transcript(self):
        class_id = self._create_class_with_student()
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )

        def fake_charge(**kwargs):
            if kwargs["feature_key"] == "class_commentary_transcribe":
                return "小汪今天绝对纸学得不错"
            if kwargs["feature_key"] == "class_commentary_transcript_polish":
                raise RuntimeError("polish timeout")
            raise AssertionError(f"unexpected feature key: {kwargs['feature_key']}")

        with patch.object(self.app_module, "_run_ai_feature_with_charge", side_effect=fake_charge):
            self.app_module._run_class_commentary_transcription(
                task["id"],
                str(self.base / "audio.m4a"),
                {"id": self.owner["id"], "organization_id": self.owner["organization_id"]},
                "saved-audio-request-key",
            )

        saved = lesson_manager.get_class_commentary_task(task["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "transcribed")
        self.assertEqual(saved["raw_transcript_text"], "小汪今天绝对纸学得不错")
        self.assertEqual(saved["transcript_text"], "小汪今天绝对纸学得不错")
        self.assertEqual(saved["confirmed_transcript_text"], "小汪今天绝对纸学得不错")
        self.assertEqual(saved["transcript_polish_error"], "polish timeout")
        self.assertEqual(saved["transcript_polished_at"], "")
        self.assertEqual(saved["failure_stage"], "")
        self.assertEqual(saved["transcription_error"], "")

    def test_raw_transcript_stays_private_until_polish_finishes(self):
        class_id = self._create_class_with_student()
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )
        transcribing = lesson_manager.mark_class_commentary_task_transcribing(task["id"])
        self.assertEqual(transcribing["status"], "transcribing")

        raw_saved = lesson_manager.mark_class_commentary_raw_transcription_succeeded(
            task["id"],
            "小汪今天计算有进步",
            '[{"id": 1, "name": "小王"}]',
        )

        self.assertEqual(raw_saved["status"], "transcribing")
        self.assertEqual(raw_saved["raw_transcript_text"], "小汪今天计算有进步")
        self.assertEqual(raw_saved["transcript_text"], "")
        self.assertEqual(raw_saved["confirmed_transcript_text"], "")

        response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["status"], "transcribing")
        self.assertEqual(payload["transcript_text"], "")
        self.assertEqual(payload["confirmed_transcript_text"], "")
        self.assertPrivateTranscriptPolishFieldsHidden(payload)

    def test_task_response_hides_private_transcript_polish_fields(self):
        class_id = self._create_class_with_student()
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )
        lesson_manager.mark_class_commentary_raw_transcription_succeeded(
            task["id"],
            "小汪今天计算有进步",
            '[{"id": 1, "name": "小王"}]',
        )
        lesson_manager.mark_class_commentary_transcript_polish_succeeded(
            task["id"],
            "小王今天计算有进步",
        )

        response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["transcript_text"], "小王今天计算有进步")
        self.assertEqual(payload["subject_key"], "math")
        self.assertPrivateTranscriptPolishFieldsHidden(payload)

    def test_task_list_returns_accessible_recent_history(self):
        class_id = self._create_class_with_student()
        older = self._create_transcribed_task(class_id, "小王今天计算有进步")
        newer = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "newer.m4a"),
            audio_filename="newer.m4a",
        )
        lesson_manager.mark_class_commentary_raw_transcription_succeeded(
            newer["id"],
            "小汪今天计算更稳",
            '[{"id": 1, "name": "小王"}]',
        )

        response = self.client.get("/api/class-commentary/tasks", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual([item["id"] for item in payload["tasks"][:2]], [newer["id"], older["id"]])
        self.assertEqual(payload["tasks"][0]["class_name"], "数学·七年级·4班")
        self.assertEqual(payload["tasks"][0]["subject_key"], "math")
        self.assertEqual(payload["tasks"][0]["transcript_text"], "")
        self.assertPrivateTranscriptPolishFieldsHidden(payload["tasks"][0])

    def test_task_response_keeps_unknown_class_subject_scope_empty(self):
        class_id = lesson_manager.save_class(
            "机器人·七年级·4班",
            subject="机器人",
            grade="七年级",
            organization_id=self.owner["organization_id"],
            teacher_user_id=self.owner["id"],
        )
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "robotics.m4a"),
            audio_filename="robotics.m4a",
        )

        response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["subject_key"], "")

    def test_task_list_for_member_hides_unassigned_class_history(self):
        assigned_class_id = self._create_class_with_student()
        unassigned_class_id = lesson_manager.save_class(
            "数学·八年级·8班",
            subject="数学",
            grade="八年级",
            organization_id=self.owner["organization_id"],
            teacher_user_id=self.owner["id"],
        )
        member_id, member_token = self._create_member("commentary_list_member")
        lesson_manager.set_class_teacher_user_id(assigned_class_id, member_id)
        assigned_task = self._create_transcribed_task(assigned_class_id, "分配班级内容")
        unassigned_task = self._create_transcribed_task(unassigned_class_id, "未分配班级内容")

        list_response = self.client.get(
            "/api/class-commentary/tasks",
            headers={"X-Auth-Token": member_token},
        )
        direct_response = self.client.get(
            f"/api/class-commentary/tasks/{unassigned_task['id']}",
            headers={"X-Auth-Token": member_token},
        )

        self.assertEqual(list_response.status_code, 200)
        payload = list_response.get_json()
        self.assertEqual([item["id"] for item in payload["tasks"]], [assigned_task["id"]])
        self.assertNotIn("未分配班级内容", str(payload))
        self.assertEqual(direct_response.status_code, 403)

    def test_task_list_for_member_limits_after_class_scope(self):
        assigned_class_id = self._create_class_with_student()
        unassigned_class_id = lesson_manager.save_class(
            "数学·九年级·9班",
            subject="数学",
            grade="九年级",
            organization_id=self.owner["organization_id"],
            teacher_user_id=self.owner["id"],
        )
        member_id, member_token = self._create_member("commentary_paged_member")
        lesson_manager.set_class_teacher_user_id(assigned_class_id, member_id)
        visible_task = self._create_transcribed_task(assigned_class_id, "自己的较旧记录")
        for index in range(31):
            self._create_transcribed_task(unassigned_class_id, f"其他班级新记录 {index}")

        response = self.client.get(
            "/api/class-commentary/tasks",
            headers={"X-Auth-Token": member_token},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual([item["id"] for item in payload["tasks"]], [visible_task["id"]])
        self.assertNotIn("自己的较旧记录", str(payload))
        self.assertNotIn("confirmed_transcript_text", payload["tasks"][0])

    def test_create_text_task_returns_transcribed_task_without_audio(self):
        class_id = self._create_class_with_student()

        response = self.client.post(
            "/api/class-commentary/tasks/text",
            headers=self.headers,
            json={
                "class_id": class_id,
                "confirmed_transcript_text": "小王今天计算有进步, 课堂回答更主动。",
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["status"], "transcribed")
        self.assertEqual(payload["subject_key"], "math")
        self.assertEqual(payload["audio_filename"], "手动输入")
        self.assertEqual(payload["transcript_text"], "小王今天计算有进步, 课堂回答更主动。")
        self.assertEqual(payload["confirmed_transcript_text"], "小王今天计算有进步, 课堂回答更主动。")
        self.assertPrivateTranscriptPolishFieldsHidden(payload)

    def test_manual_transcript_save_preserves_private_polish_fields(self):
        class_id = self._create_class_with_student()
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )
        lesson_manager.mark_class_commentary_raw_transcription_succeeded(
            task["id"],
            "小汪今天计算有进步",
            '[{"id": 1, "name": "小王"}]',
        )
        lesson_manager.mark_class_commentary_transcript_polish_failed(
            task["id"],
            "小汪今天计算有进步",
            "model timeout",
        )

        updated = lesson_manager.save_class_commentary_transcript(task["id"], "小王今天计算有进步")

        self.assertEqual(updated["confirmed_transcript_text"], "小王今天计算有进步")
        self.assertEqual(updated["raw_transcript_text"], "小汪今天计算有进步")
        self.assertEqual(updated["roster_snapshot"], '[{"id": 1, "name": "小王"}]')
        self.assertEqual(updated["transcript_polish_error"], "model timeout")
        self.assertEqual(updated["transcript_polished_at"], "")

    def test_worker_polish_billing_uses_default_provider_and_model_when_review_plan_config_differs(self):
        config_runtime.write_file_config(
            {
                "colleague_skill_dir": str(self.skill_dir),
                "provider": "deepseek",
                "deepseek_model": "deepseek-v4-pro",
                "review_plan_provider": "openai",
                "review_plan_model": "gpt-4.1-mini",
            }
        )
        class_id = self._create_class_with_student()
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )
        charged = []

        def fake_finalize_ai_charge(**kwargs):
            charged.append(kwargs)

        with patch.object(self.app_module, "ensure_feature_credits_available"), \
             patch.object(self.app_module, "finalize_ai_charge", side_effect=fake_finalize_ai_charge), \
             patch.object(
                 self.app_module,
                 "transcribe_audio",
                 return_value=("小汪今天绝对纸学得不错", {"provider": "local", "model": "faster-whisper"}),
             ), \
             patch.object(
                 self.app_module,
                 "polish_class_commentary_transcript",
                 return_value=("小王今天绝对值学得不错", {"input_tokens": 11, "output_tokens": 7}),
             ):
            self.app_module._run_class_commentary_transcription(
                task["id"],
                str(self.base / "audio.m4a"),
                {"id": self.owner["id"], "organization_id": self.owner["organization_id"]},
                "saved-audio-request-key",
            )

        polish_charge = next(
            item for item in charged
            if item["feature_key"] == "class_commentary_transcript_polish"
        )
        self.assertEqual(polish_charge["usage"]["provider"], "deepseek")
        self.assertEqual(polish_charge["usage"]["model"], "deepseek-v4-pro")

    def test_skill_list_syncs_configured_packages_and_is_shared_within_organization(self):
        owner_skill = self._register_skill(
            "owner-registry-style",
            "owner registry content",
        )
        member_id, member_token = self._create_member("commentary_skill_member")
        self._register_skill(
            "member-registry-style",
            "member registry content",
            owner_user_id=member_id,
        )
        package_dir = self.skill_dir / "filesystem-only"
        package_dir.mkdir()
        (package_dir / "SKILL.md").write_text("Package instructions", encoding="utf-8")
        (package_dir / "work.md").write_text("Assessment workflow", encoding="utf-8")
        (package_dir / "persona.md").write_text("Colleague persona", encoding="utf-8")
        knowledge_dir = package_dir / "knowledge" / "messages"
        knowledge_dir.mkdir(parents=True)
        (knowledge_dir / "feedback-samples.md").write_text(
            "Full feedback sample with [玫瑰].", encoding="utf-8"
        )
        (package_dir / "meta.json").write_text(
            json.dumps({"name": "曹曦临"}, ensure_ascii=False),
            encoding="utf-8",
        )

        owner_response = self.client.get(
            "/api/class-commentary/skills",
            headers=self.headers,
        )
        (package_dir / "work.md").write_text(
            "Changed after registry import",
            encoding="utf-8",
        )
        member_response = self.client.get(
            "/api/class-commentary/skills",
            headers={"X-Auth-Token": member_token},
        )

        self.assertEqual(owner_response.status_code, 200)
        self.assertEqual(member_response.status_code, 200)
        owner_skills = owner_response.get_json()["skills"]
        member_skills = member_response.get_json()["skills"]
        expected_ids = [
            "filesystem-only",
            "member-registry-style",
            "owner-registry-style",
        ]
        self.assertEqual([item["id"] for item in owner_skills], expected_ids)
        self.assertEqual(
            [item["id"] for item in member_skills],
            [item["id"] for item in owner_skills],
        )
        owner_skills = member_skills
        imported_owner = next(
            item for item in owner_skills if item["id"] == "owner-registry-style"
        )
        self.assertEqual(imported_owner["registry_id"], owner_skill["registry_id"])
        filesystem_skill = next(
            item for item in owner_skills if item["id"] == "filesystem-only"
        )
        self.assertGreater(filesystem_skill["registry_id"], 0)
        self.assertEqual(filesystem_skill["name"], "曹曦临")
        self.assertIn("Package instructions", filesystem_skill["content"])
        self.assertIn("Colleague persona", filesystem_skill["content"])
        self.assertIn("Full feedback sample with [玫瑰].", filesystem_skill["content"])
        self.assertIn("Changed after registry import", filesystem_skill["content"])
        self.assertNotIn("Assessment workflow", filesystem_skill["content"])

    def test_skill_sync_does_not_replace_an_active_candidate_version(self):
        package_path = self.skill_dir / "candidate-preserved.skill"
        package_path.write_text("Imported disk content", encoding="utf-8")
        imported = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.owner["organization_id"],
            skill_id="candidate-preserved",
            actor_user_id=self.owner["id"],
            source_path=str(package_path),
        )
        candidate_content = "Teacher-evolved candidate content"
        with lesson_manager.get_conn() as conn:
            next_version = int(
                conn.execute(
                    "SELECT MAX(version_no) + 1 FROM class_commentary_skill_versions WHERE skill_registry_id=?",
                    (int(imported["registry_id"]),),
                ).fetchone()[0]
            )
            cursor = conn.execute(
                """
                INSERT INTO class_commentary_skill_versions (
                    organization_id, skill_registry_id, version_no, version_kind,
                    content, content_hash, base_version_id, evaluation_snapshot_json,
                    evaluation_hash, review_status
                ) VALUES (?, ?, ?, 'candidate', ?, ?, ?, '{}', '', 'approved')
                """,
                (
                    int(self.owner["organization_id"]),
                    int(imported["registry_id"]),
                    next_version,
                    candidate_content,
                    hashlib.sha256(candidate_content.encode("utf-8")).hexdigest(),
                    int(imported["active_version_id"]),
                ),
            )
            candidate_version_id = int(cursor.lastrowid)
            conn.execute(
                "UPDATE class_commentary_skills SET active_version_id=? WHERE id=?",
                (candidate_version_id, int(imported["registry_id"])),
            )
        package_path.write_text("Disk content changed again", encoding="utf-8")

        response = self.client.get(
            "/api/class-commentary/skills",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        skill = next(
            item
            for item in response.get_json()["skills"]
            if item["id"] == "candidate-preserved"
        )
        self.assertEqual(skill["active_version_id"], candidate_version_id)
        self.assertEqual(skill["version_kind"], "candidate")
        self.assertEqual(skill["content"], candidate_content)

    def test_member_can_generate_with_colleague_skill_imported_by_another_user(self):
        self._configure_batch_generation()
        skill = self._register_skill(
            "colleague-cao-xi-lin",
            "Use Cao Xi Lin's distilled assessment structure.",
        )
        member_id, member_token = self._create_member("colleague_skill_user")
        class_id = lesson_manager.save_class(
            "Shared colleague skill class",
            subject="数学",
            grade="七年级",
            organization_id=self.owner["organization_id"],
            teacher_user_id=member_id,
        )
        student = lesson_manager.create_student_for_class(class_id, "小王")
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=member_id,
            audio_path=str(self.base / "member-audio.m4a"),
            audio_filename="member-audio.m4a",
        )
        task = lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            "小王今天计算更稳定",
        )

        def fake_charge(**kwargs):
            result = kwargs["producer"]()
            return result[0] if isinstance(result, tuple) else result

        with self._batch_runtime(), \
             patch.object(self.app_module, "_run_ai_feature_with_charge", side_effect=fake_charge), \
             patch.object(
                 self.app_module,
                 "generate_class_commentary_feedback",
                 return_value=(
                     self._batch_model_output([student]),
                     {"input_tokens": 3, "output_tokens": 2},
                 ),
             ):
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers={"X-Auth-Token": member_token},
                json={
                    "request_id": "member-uses-colleague-skill",
                    "skill_id": skill["skill_id"],
                    "attending_student_ids": [student["id"]],
                },
            )

        self.assertEqual(response.status_code, 200)
        generation = lesson_manager.get_class_commentary_generation(
            response.get_json()["generation_id"]
        )
        self.assertEqual(skill["imported_by_user_id"], self.owner["id"])
        self.assertEqual(generation["teacher_user_id"], member_id)
        self.assertEqual(generation["skill_registry_id"], skill["registry_id"])

    def test_structured_generate_freezes_scope_uses_partitioned_memory_and_graph_and_returns_canonical_feedback(self):
        self._configure_batch_generation()
        class_id = self._create_class_with_student()
        lesson_manager.create_student_for_class(class_id, "小李")
        lesson_manager.create_student_for_class(class_id, "小张")
        students = lesson_manager.list_students_for_class(class_id)
        students_by_name = {student["name"]: student for student in students}
        first_student = students_by_name["小王"]
        second_student = students_by_name["小李"]
        unselected_student = students_by_name["小张"]
        task = self._create_transcribed_task(
            class_id,
            "小李先完成计算. 小王随后补充了验算过程.",
        )
        skill = self._register_skill(
            "structured-style",
            "Use concise feedback and one concrete next action.",
        )
        selected_students = [first_student, second_student]
        structured_model_output = self._batch_model_output(
            selected_students,
            feedback_by_student_id={
                int(first_student["id"]): (
                    "今天验算意识更稳定, 解题过程表达得更清楚🌱."
                ),
                int(second_student["id"]): (
                    "今天计算步骤更完整, 整体课堂状态也很扎实✨.  \n"
                ),
            },
            reverse_items=True,
        )

        def fake_charge(**kwargs):
            result = kwargs["producer"]()
            return result[0] if isinstance(result, tuple) else result

        with self._batch_runtime() as runtime, patch.object(
            self.app_module,
            "_run_ai_feature_with_charge",
            side_effect=fake_charge,
        ), patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
            return_value=(
                structured_model_output,
                {"input_tokens": 3, "output_tokens": 2},
            ),
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    "request_id": "structured-generation-success",
                    "skill_id": skill["skill_id"],
                    "attending_student_ids": [
                        first_student["id"],
                        second_student["id"],
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        eligible_ids = [first_student["id"], second_student["id"]]
        expected_items = [
            {
                "student_id": first_student["id"],
                "student_name": "小王",
                "feedback_text": "今天验算意识更稳定, 解题过程表达得更清楚🌱.",
            },
            {
                "student_id": second_student["id"],
                "student_name": "小李",
                "feedback_text": "今天计算步骤更完整, 整体课堂状态也很扎实✨.",
            },
        ]
        expected_envelope = {
            "schema_version": "class_commentary.student_feedback.v1",
            "items": [
                {
                    "student_id": item["student_id"],
                    "feedback_text": item["feedback_text"],
                }
                for item in expected_items
            ],
        }
        expected_json = json.dumps(
            expected_envelope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        expected_hash = hashlib.sha256(expected_json.encode("utf-8")).hexdigest()
        expected_text = (
            "小王:\n今天验算意识更稳定, 解题过程表达得更清楚🌱.\n\n"
            "小李:\n今天计算步骤更完整, 整体课堂状态也很扎实✨."
        )
        self.assertEqual(payload["feedback_schema_version"], expected_envelope["schema_version"])
        self.assertEqual(payload["feedback_schema_status"], "supported")
        self.assertEqual(payload["student_feedback_items"], expected_items)
        self.assertEqual(payload["structured_feedback_hash"], expected_hash)
        self.assertEqual(payload["derived_feedback_text"], expected_text)
        self.assertEqual(payload["generated_feedback_text"], expected_text)
        self.assertEqual(payload["eligible_student_ids"], eligible_ids)
        self.assertTrue(payload["eligible_student_scope_hash"])
        self.assertEqual(
            payload["student_mention_matcher_version"],
            "class_commentary.student_evidence_fail_closed.v2",
        )
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["student_history_memory_mode"], "batch_isolated_v3")
        self.assertEqual(
            payload["prompt_version"],
            CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V6,
        )

        saved = lesson_manager.get_class_commentary_generation(payload["generation_id"])
        self.assertEqual(saved["structured_feedback_json"], expected_json)
        self.assertEqual(saved["structured_feedback_hash"], expected_hash)
        self.assertEqual(saved["generated_feedback_text"], expected_text)
        self.assertEqual(saved["attending_roster_explicit"], 1)
        self.assertEqual(
            saved["prompt_version"],
            CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V6,
        )
        self.assertEqual(
            json.loads(saved["prompt_payload_snapshot_json"])["prompt_version"],
            CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V6,
        )
        self.assertEqual(json.loads(saved["eligible_student_ids_json"]), eligible_ids)
        saved_roster = json.loads(saved["attending_roster_snapshot_json"])
        self.assertEqual(
            [item["student_id"] for item in saved_roster],
            eligible_ids,
        )
        saved_memory_context = json.loads(saved["memory_context_snapshot_json"])
        self.assertEqual(
            saved_memory_context["student_history_memory_mode"],
            "batch_isolated_v3",
        )
        self.assertEqual(
            [item["student_id"] for item in saved_memory_context["student_contexts_by_id"]],
            eligible_ids,
        )
        self.assertEqual(
            [call.kwargs["student_id"] for call in runtime["retrieve_memory"].call_args_list],
            eligible_ids,
        )
        self.assertEqual(
            [call.kwargs["student_id"] for call in runtime["retrieve_graph"].call_args_list],
            eligible_ids,
        )
        model_call = generate.call_args.kwargs
        self.assertEqual(
            [student["id"] for student in model_call["students"]],
            eligible_ids,
        )
        self.assertNotIn(
            unselected_student["id"],
            [student["id"] for student in model_call["students"]],
        )
        chat_request = model_call["chat_request"]
        self.assertEqual(chat_request["response_format"], {"type": "json_object"})
        self.assertEqual(chat_request["student_history_memory_mode"], "batch_isolated_v3")
        self.assertIn("Use short sentences", chat_request["messages"][1]["content"])
        self.assertIn("history-only-for", chat_request["messages"][1]["content"])
        self.assertIn("graph-only-for", chat_request["messages"][1]["content"])
        self.assertIn("emoji", chat_request["messages"][0]["content"])
        self.assertIn("[STUDENT_CONTEXTS_BY_ID]", chat_request["messages"][1]["content"])
        self.assertNotIn(
            "[STUDENT_HISTORY_MEMORIES]",
            chat_request["messages"][1]["content"],
        )

    def test_structured_generate_requires_explicit_attendance_without_reservation(self):
        config_runtime.write_file_config({
            "colleague_skill_dir": str(self.skill_dir),
            "class_commentary_structured_feedback_enabled": True,
        })
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, "今天没有点到学生姓名.")
        skill = self._register_skill("structured-precondition")

        with patch.object(
            self.app_module,
            "has_class_commentary_api_key",
            return_value=True,
        ), patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=BATCH_READY_CAPABILITIES,
        ), patch.object(
            self.app_module,
            "_run_ai_feature_with_charge",
        ) as charge, patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    "request_id": "structured-precondition-no-student",
                    "skill_id": skill["skill_id"],
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {"error": "attending_student_ids is required"},
        )
        with lesson_manager.get_conn() as conn:
            generation_count = conn.execute(
                "SELECT COUNT(*) AS count FROM class_commentary_generations WHERE task_id=?",
                (task["id"],),
            ).fetchone()["count"]
        self.assertEqual(generation_count, 0)
        unchanged_task = lesson_manager.get_class_commentary_task(task["id"])
        self.assertEqual(unchanged_task["status"], "transcribed")
        self.assertIsNone(unchanged_task["latest_generation_id"])
        charge.assert_not_called()
        generate.assert_not_called()

    def test_structured_generate_rejects_tampered_core_snapshot_before_model_call(self):
        config_runtime.write_file_config({
            "colleague_skill_dir": str(self.skill_dir),
            "class_commentary_structured_feedback_enabled": True,
        })
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, "小王今天完成了计算.")
        skill = self._register_skill("structured-tampered-snapshot")
        original_reserve = self.app_module.reserve_class_commentary_generation

        def reserve_then_tamper(**kwargs):
            generation = original_reserve(**kwargs)
            with lesson_manager.get_conn() as conn:
                conn.execute(
                    """
                    UPDATE class_commentary_generations
                    SET confirmed_transcript_snapshot='篡改后的转写'
                    WHERE id=?
                    """,
                    (generation["id"],),
                )
            return lesson_manager.get_class_commentary_generation(generation["id"])

        with patch.object(
            self.app_module,
            "has_class_commentary_api_key",
            return_value=True,
        ), patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=BATCH_READY_CAPABILITIES,
        ), patch.object(
            self.app_module,
            "reserve_class_commentary_generation",
            side_effect=reserve_then_tamper,
        ), patch.object(
            class_commentary_batch_context,
            "retrieve_isolated_student_memory_context",
        ) as retrieve_memory, patch.object(
            self.app_module,
            "_run_ai_feature_with_charge",
        ) as charge, patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    "request_id": "structured-tampered-core-snapshot",
                    "skill_id": skill["skill_id"],
                    "attending_student_ids": [
                        lesson_manager.list_students_for_class(class_id)[0]["id"]
                    ],
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json()["error"],
            "class_commentary_batch_memory_unavailable",
        )
        retrieve_memory.assert_not_called()
        charge.assert_not_called()
        generate.assert_not_called()
        saved = lesson_manager.get_class_commentary_generation(
            response.get_json()["generation_id"]
        )
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(
            saved["error_code"],
            "class_commentary_batch_context_unavailable",
        )

    def test_structured_generate_rejects_missing_student_output_without_raw_leak(self):
        self._configure_batch_generation()
        class_id = self._create_class_with_student()
        lesson_manager.create_student_for_class(class_id, "小李")
        students = lesson_manager.list_students_for_class(class_id)
        task = self._create_transcribed_task(
            class_id,
            "小王今天完成了计算. 小李需要继续练习验算.",
        )
        skill = self._register_skill("structured-invalid-model")
        raw_model_output = json.dumps(
            {
                "schema_version": "class_commentary.student_feedback.v1",
                "items": [
                    {
                        "student_id": students[0]["id"],
                        "feedback_text": "RAW_MODEL_SECRET: 只返回了一名学生.",
                    }
                ],
                "used_graph_evidence_refs_by_student": [
                    {
                        "student_id": student["id"],
                        "evidence_refs": [f"graph-ref-{student['id']}"],
                    }
                    for student in students
                ],
            },
            ensure_ascii=False,
        )

        def fake_charge(**kwargs):
            result = kwargs["producer"]()
            return result[0] if isinstance(result, tuple) else result

        with self._batch_runtime(), patch.object(
            self.app_module,
            "_run_ai_feature_with_charge",
            side_effect=fake_charge,
        ), patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
            return_value=(
                raw_model_output,
                {"input_tokens": 3, "output_tokens": 2},
            ),
        ):
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    "request_id": "structured-invalid-model-output",
                    "skill_id": skill["skill_id"],
                    "attending_student_ids": [
                        student["id"] for student in students
                    ],
                },
            )

        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertEqual(payload["error"], "student_feedback_coverage_mismatch")
        self.assertEqual(payload["generation_status"], "failed")
        self.assertEqual(
            payload["generation"]["error_code"],
            "student_feedback_coverage_mismatch",
        )
        self.assertEqual(payload["generation"]["generated_feedback_text"], "")
        self.assertEqual(payload["generation"]["student_feedback_items"], [])
        self.assertEqual(payload["generation"]["derived_feedback_text"], "")
        self.assertNotIn(raw_model_output, response.get_data(as_text=True))

        saved = lesson_manager.get_class_commentary_generation(payload["generation_id"])
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["error_code"], "student_feedback_coverage_mismatch")
        self.assertEqual(saved["structured_feedback_json"], "")
        self.assertEqual(saved["structured_feedback_hash"], "")
        self.assertEqual(saved["generated_feedback_text"], "")
        self.assertNotIn(raw_model_output, json.dumps(saved, ensure_ascii=False))
        failed_task = lesson_manager.get_class_commentary_task(task["id"])
        self.assertEqual(
            failed_task["generation_error"],
            "student_feedback_coverage_mismatch",
        )
        self.assertNotIn(raw_model_output, json.dumps(failed_task, ensure_ascii=False))

    def test_generate_requires_request_id_and_is_idempotent_from_registry_snapshot(self):
        self._configure_batch_generation()
        class_id = self._create_class_with_student()
        second_student = lesson_manager.create_student_for_class(class_id, "小李")
        students = lesson_manager.list_students_for_class(class_id)
        task = self._create_transcribed_task(
            class_id,
            "小王今天计算有进步. 小李今天计算有进步.",
        )
        registry_content = "registry content is authoritative"
        skill = self._register_skill("teacher-a", registry_content)
        Path(skill["source_path"]).write_text(
            "filesystem content changed after import",
            encoding="utf-8",
        )
        request_payload = {
            "request_id": "generation-api-idempotent",
            "skill_id": "teacher-a",
            "attending_student_ids": [student["id"] for student in students],
        }
        with self._batch_runtime(), \
             patch.object(
                 self.app_module,
                 "finalize_ai_charge",
                 wraps=self.app_module.finalize_ai_charge,
             ) as charge, \
             patch.object(
                 self.app_module,
                 "generate_class_commentary_feedback",
                 return_value=(
                     self._batch_model_output(students),
                     {"input_tokens": 3, "output_tokens": 2},
                 ),
             ) as generate:
            missing_request = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    "skill_id": "teacher-a",
                    "attending_student_ids": request_payload["attending_student_ids"],
                },
            )
            first = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json=request_payload,
            )
            repeated = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json=request_payload,
            )
            omitted_attendance = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    "request_id": request_payload["request_id"],
                    "skill_id": request_payload["skill_id"],
                },
            )
            changed_payload = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    **request_payload,
                    "attending_student_ids": [second_student["id"]],
                },
            )

        self.assertEqual(missing_request.status_code, 400)
        self.assertEqual(missing_request.get_json()["error"], "request_id is required")
        self.assertEqual(first.status_code, 200)
        first_payload = first.get_json()
        self.assertIsInstance(first_payload["generation_id"], int)
        self.assertEqual(first_payload["status"], "succeeded")
        self.assertEqual(first_payload["task_status"], "ready")
        self.assertEqual(first_payload["generation_status"], "succeeded")
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.get_json()["generation_id"], first_payload["generation_id"])
        self.assertEqual(repeated.get_json()["generation_status"], "succeeded")
        self.assertEqual(omitted_attendance.status_code, 409)
        self.assertEqual(changed_payload.status_code, 409)
        charge.assert_called_once()
        generate.assert_called_once()
        self.assertEqual(
            generate.call_args.kwargs["skill"]["content"],
            "filesystem content changed after import",
        )
        saved = lesson_manager.get_class_commentary_generation(first_payload["generation_id"])
        self.assertEqual(saved["skill_registry_id"], skill["registry_id"])
        self.assertEqual(
            saved["skill_content_snapshot"],
            "filesystem content changed after import",
        )
        self.assertEqual(saved["student_history_memory_mode"], "batch_isolated_v3")
        self.assertEqual(
            saved["prompt_version"],
            CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V6,
        )

    def test_batch_charge_retry_reuses_persisted_response_without_provider_recall(self):
        self._configure_batch_generation()
        class_id = self._create_class_with_student()
        students = lesson_manager.list_students_for_class(class_id)
        task = self._create_transcribed_task(
            class_id,
            "小王今天计算有进步.",
        )
        skill = self._register_skill("batch-charge-retry")
        request_payload = {
            "request_id": "batch-charge-retry-request",
            "skill_id": skill["skill_id"],
            "attending_student_ids": [student["id"] for student in students],
        }
        real_finalize = self.app_module.finalize_ai_charge

        with self._batch_runtime(), patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
            return_value=(
                self._batch_model_output(students),
                {"input_tokens": 3, "output_tokens": 2},
            ),
        ) as generate, patch.object(
            self.app_module,
            "finalize_ai_charge",
            side_effect=[RuntimeError("charge storage unavailable")],
        ):
            first = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json=request_payload,
            )

        self.assertEqual(first.status_code, 500)
        first_payload = first.get_json()
        generation_id = int(first_payload["generation_id"])
        pending = lesson_manager.get_class_commentary_generation(generation_id)
        self.assertEqual(pending["status"], "generating")
        self.assertTrue(pending["batch_response_hash"])
        self.assertEqual(pending["batch_charge_status"], "pending")
        generate.assert_called_once()

        with self._batch_runtime(), patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
        ) as generate_again, patch.object(
            self.app_module,
            "finalize_ai_charge",
            side_effect=real_finalize,
        ):
            repeated = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json=request_payload,
            )

        self.assertEqual(repeated.status_code, 200)
        generate_again.assert_not_called()
        settled = lesson_manager.get_class_commentary_generation(generation_id)
        self.assertEqual(settled["status"], "succeeded")
        self.assertEqual(settled["batch_charge_status"], "charged")
        self.assertGreater(int(settled["batch_charge_usage_id"] or 0), 0)

    def test_historical_disabled_v1_request_remains_readable_and_idempotent(self):
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")
        skill = self._register_skill("historical-disabled-v1")
        student = lesson_manager.list_students_for_class(class_id)[0]
        historical = self._promote_generation_to_structured(
            self._create_succeeded_generation(
                task,
                skill,
                request_id="historical-disabled-v1-request",
            ),
            {int(student["id"]): "历史点评仍可读取🌱."},
        )
        unavailable = {
            **BATCH_READY_CAPABILITIES,
            "batch_isolated_v3_enabled": False,
            "graph_healthy": False,
            "graph_degraded": True,
        }

        with patch.object(
            self.app_module,
            "has_class_commentary_api_key",
            return_value=False,
        ), patch.object(
            self.app_module,
            "_class_commentary_capabilities",
            return_value=unavailable,
        ) as capabilities, patch.object(
            self.app_module,
            "reserve_class_commentary_generation",
        ) as reserve, patch.object(
            self.app_module,
            "_run_ai_feature_with_charge",
        ) as charge, patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    "request_id": "historical-disabled-v1-request",
                    "skill_id": skill["skill_id"],
                    "attending_student_ids": [student["id"]],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["generation_id"], historical["id"])
        self.assertEqual(payload["student_history_memory_mode"], "disabled_v1")
        self.assertEqual(payload["student_feedback_items"][0]["student_id"], student["id"])
        self.assertEqual(payload["student_feedback_items"][0]["feedback_text"], "历史点评仍可读取🌱.")
        capabilities.assert_not_called()
        reserve.assert_not_called()
        charge.assert_not_called()
        generate.assert_not_called()

    def test_generate_in_flight_same_request_returns_reserved_generation_without_model_call(self):
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")
        skill = self._register_skill("in-flight-style", "in-flight registry content")
        class_record = lesson_manager.get_class(class_id)
        students = lesson_manager.list_students_for_class(class_id)
        provider = self.app_module._class_commentary_ai_provider_name(
            fallback=self.app_module._default_ai_provider_name()
        )
        model = self.app_module._class_commentary_chat_model_name(
            provider,
            fallback_model=self.app_module._default_chat_model_name(),
        )
        chat_request = build_class_commentary_chat_request(
            class_record=class_record,
            students=students,
            transcript_text=task["confirmed_transcript_text"],
            skill=skill,
            teacher_style_memories=[],
            student_history_memories=[],
        )
        request_id = "generation-api-in-flight-idempotent"
        reserved = lesson_manager.reserve_class_commentary_generation(
            task_id=task["id"],
            generation_request_id=request_id,
            skill_registry_id=skill["registry_id"],
            attending_roster=[
                {"student_id": student["id"], "student_name": student["name"]}
                for student in students
            ],
            model_provider=provider,
            model_name=model,
            model_parameters={"temperature": chat_request["temperature"]},
            prompt_version=self.app_module.CLASS_COMMENTARY_PROMPT_VERSION,
            prompt_payload=chat_request,
            memory_context={
                "records": [],
                "rendered_text": "",
                "student_history_memories": [],
                "teacher_style_memories": [],
            },
            attending_roster_explicit=False,
        )

        with patch.object(self.app_module, "has_class_commentary_api_key", return_value=True), \
             patch.object(self.app_module, "_run_ai_feature_with_charge") as charge, \
             patch.object(self.app_module, "generate_class_commentary_feedback") as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={"request_id": request_id, "skill_id": skill["skill_id"]},
            )

        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertEqual(payload["generation_id"], reserved["id"])
        self.assertEqual(payload["generation_status"], "generating")
        charge.assert_not_called()
        generate.assert_not_called()

    def test_generate_rejects_transcript_change_before_reservation(self):
        self._configure_batch_generation()
        original_transcript = "小王今天计算有进步"
        reserved_transcript = "小王今天计算有进步, 新增要求是继续验算"
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, original_transcript)
        self._register_skill("reserved-prompt-style", "reserved prompt content")
        real_reserve = lesson_manager.reserve_class_commentary_generation

        def reserve_after_transcript_edit(**kwargs):
            lesson_manager.save_class_commentary_transcript(task["id"], reserved_transcript)
            return real_reserve(**kwargs)

        def fake_charge(**kwargs):
            result = kwargs["producer"]()
            return result[0] if isinstance(result, tuple) else result

        students = lesson_manager.list_students_for_class(class_id)
        with patch.object(
            self.app_module,
            "reserve_class_commentary_generation",
            side_effect=reserve_after_transcript_edit,
        ), self._batch_runtime(), patch.object(
            self.app_module,
            "_run_ai_feature_with_charge",
            side_effect=fake_charge,
        ), patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
            return_value=(
                self._batch_model_output(students),
                {"input_tokens": 3, "output_tokens": 2},
            ),
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    "request_id": "generation-reserved-prompt",
                    "skill_id": "reserved-prompt-style",
                    "attending_student_ids": [student["id"] for student in students],
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json(), {"error": "confirmed_transcript_changed"})
        generate.assert_not_called()
        with lesson_manager.get_conn() as conn:
            generation_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_generations WHERE task_id=?",
                (int(task["id"]),),
            ).fetchone()[0]
        self.assertEqual(generation_count, 0)

    def test_generation_history_lists_summaries_and_returns_owner_detail(self):
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")
        skill = self._register_skill("history-style", "history registry content")
        first = self._create_succeeded_generation(
            task,
            skill,
            request_id="generation-history-first",
            feedback_text="第一版反馈",
        )
        second = self._create_succeeded_generation(
            task,
            skill,
            request_id="generation-history-second",
            feedback_text="第二版反馈",
        )

        list_response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}/generations",
            headers=self.headers,
        )
        detail_response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}/generations/{first['id']}",
            headers=self.headers,
        )

        self.assertEqual(list_response.status_code, 200)
        summaries = list_response.get_json()["generations"]
        self.assertEqual(
            [item["id"] for item in summaries],
            [second["id"], first["id"]],
        )
        self.assertEqual([item["status"] for item in summaries], ["succeeded", "succeeded"])
        self.assertEqual(detail_response.status_code, 200)
        detail = self._unwrap_payload(detail_response.get_json(), "generation")
        self.assertEqual(detail["id"], first["id"])
        self.assertEqual(detail["generation_request_id"], "generation-history-first")
        self.assertEqual(detail["confirmed_transcript_snapshot"], "小王今天计算有进步")
        self.assertEqual(detail["skill_content_snapshot"], "history registry content")
        self.assertEqual(detail["generated_feedback_text"], "第一版反馈")
        self.assertEqual(detail["feedback_schema_version"], "")
        self.assertEqual(detail["feedback_schema_status"], "plain_text")
        self.assertEqual(detail["student_feedback_items"], [])
        self.assertEqual(detail["structured_feedback_hash"], "")
        self.assertEqual(detail["derived_feedback_text"], "第一版反馈")
        self.assertTrue(detail["writable"])
        self.assertEqual(summaries[0]["feedback_schema_status"], "plain_text")
        self.assertEqual(summaries[0]["derived_feedback_text"], "第二版反馈")

    def test_common_read_envelope_supports_v1_and_fails_closed_for_unknown_or_corrupt_rows(self):
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")
        skill = self._register_skill("structured-read-style", "structured read content")
        generation = self._create_succeeded_generation(task, skill)
        roster = json.loads(generation["attending_roster_snapshot_json"])
        student_id = int(roster[0]["student_id"])
        student_name = str(roster[0]["student_name"])
        feedback_text = "今天课堂计算更稳定, 下一步继续加强验算."
        derived_text = f"{student_name}:\n{feedback_text}"
        structured_payload = {
            "schema_version": "class_commentary.student_feedback.v1",
            "items": [{"student_id": student_id, "feedback_text": feedback_text}],
        }
        structured_json = json.dumps(
            structured_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        structured_hash = hashlib.sha256(structured_json.encode("utf-8")).hexdigest()
        eligible_ids = [student_id]
        eligible_scope_json = json.dumps(
            {
                "attending_roster_hash": generation["attending_roster_hash"],
                "confirmed_transcript_hash": generation["confirmed_transcript_hash"],
                "eligible_student_ids": eligible_ids,
                "student_mention_matcher_version": (
                    "class_commentary.student_name_matcher.v1"
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        eligible_scope_hash = hashlib.sha256(
            eligible_scope_json.encode("utf-8")
        ).hexdigest()
        revision = lesson_manager.confirm_class_commentary_feedback(
            task_id=task["id"],
            generation_id=generation["id"],
            teacher_user_id=self.owner["id"],
            feedback_text=derived_text,
            learn_requested=False,
            expected_draft_version=0,
            confirmation_request_id="structured-read-confirmation",
        )
        draft_id = int(revision["draft"]["id"])
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET feedback_schema_version=?, structured_feedback_json=?,
                    structured_feedback_hash=?, eligible_student_ids_json=?,
                    eligible_student_scope_hash=?,
                    student_mention_matcher_version='class_commentary.student_name_matcher.v1',
                    response_format_json='{"type":"json_object"}',
                    student_history_memory_mode='disabled_v1',
                    prompt_version=?, generated_feedback_text=?
                WHERE id=?
                """,
                (
                    structured_payload["schema_version"],
                    structured_json,
                    structured_hash,
                    json.dumps(eligible_ids, separators=(",", ":")),
                    eligible_scope_hash,
                    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
                    derived_text,
                    generation["id"],
                ),
            )
            conn.execute(
                """
                UPDATE class_commentary_feedback_drafts
                SET feedback_schema_version=?, structured_feedback_json=?,
                    content_hash=?, feedback_text=?
                WHERE id=?
                """,
                (
                    structured_payload["schema_version"],
                    structured_json,
                    structured_hash,
                    derived_text,
                    draft_id,
                ),
            )
            conn.execute(
                """
                UPDATE class_commentary_revisions
                SET feedback_schema_version=?, structured_feedback_json=?,
                    structured_feedback_hash=?, final_feedback_text=?
                WHERE id=?
                """,
                (
                    structured_payload["schema_version"],
                    structured_json,
                    structured_hash,
                    derived_text,
                    revision["id"],
                ),
            )
            conn.execute("UPDATE students SET name='改名后学生' WHERE id=?", (student_id,))

        generations_url = f"/api/class-commentary/tasks/{task['id']}/generations"
        generation_url = f"{generations_url}/{generation['id']}"
        draft_url = f"{generation_url}/feedback-draft"
        revisions_url = f"/api/class-commentary/tasks/{task['id']}/feedback-revisions"
        generation_list = self.client.get(generations_url, headers=self.headers).get_json()["generations"]
        generation_detail = self.client.get(generation_url, headers=self.headers).get_json()
        draft_detail = self.client.get(draft_url, headers=self.headers).get_json()["draft"]
        revision_detail = self.client.get(revisions_url, headers=self.headers).get_json()["revisions"][0]

        expected_item = {
            "student_id": student_id,
            "student_name": student_name,
            "feedback_text": feedback_text,
        }
        for record in (generation_list[0], generation_detail, draft_detail, revision_detail):
            with self.subTest(record_id=record["id"]):
                self.assertEqual(record["feedback_schema_status"], "supported")
                self.assertEqual(record["student_feedback_items"], [expected_item])
                self.assertEqual(record["structured_feedback_hash"], structured_hash)
                self.assertEqual(record["derived_feedback_text"], derived_text)
                self.assertTrue(record["writable"])

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET feedback_schema_version='future.student-feedback.v2',
                    structured_feedback_json='not-json', structured_feedback_hash='future-hash'
                WHERE id=?
                """,
                (generation["id"],),
            )
            conn.execute(
                """
                UPDATE class_commentary_feedback_drafts
                SET feedback_schema_version='future.student-feedback.v2',
                    structured_feedback_json='not-json', content_hash='future-hash'
                WHERE id=?
                """,
                (draft_id,),
            )
            conn.execute(
                """
                UPDATE class_commentary_revisions
                SET feedback_schema_version='future.student-feedback.v2',
                    structured_feedback_json='not-json', structured_feedback_hash='future-hash'
                WHERE id=?
                """,
                (revision["id"],),
            )

        unknown_records = (
            self.client.get(generations_url, headers=self.headers).get_json()["generations"][0],
            self.client.get(generation_url, headers=self.headers).get_json(),
            self.client.get(draft_url, headers=self.headers).get_json()["draft"],
            self.client.get(revisions_url, headers=self.headers).get_json()["revisions"][0],
        )
        for record in unknown_records:
            with self.subTest(unknown_record_id=record["id"]):
                self.assertEqual(record["feedback_schema_status"], "unsupported")
                self.assertEqual(record["student_feedback_items"], [])
                self.assertEqual(record["derived_feedback_text"], derived_text)
                self.assertFalse(record["writable"])

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET feedback_schema_version=' ', structured_feedback_json='',
                    structured_feedback_hash=''
                WHERE id=?
                """,
                (generation["id"],),
            )
        whitespace_schema_record = self.client.get(
            generation_url,
            headers=self.headers,
        ).get_json()
        self.assertEqual(whitespace_schema_record["feedback_schema_version"], " ")
        self.assertEqual(whitespace_schema_record["feedback_schema_status"], "unsupported")
        self.assertFalse(whitespace_schema_record["writable"])

        corrupt_cases = (
            ("{", structured_hash, derived_text),
            (structured_json, "bad-hash", derived_text),
            (structured_json, structured_hash, "tampered derived text"),
        )
        for corrupt_json, corrupt_hash, corrupt_text in corrupt_cases:
            with lesson_manager.get_conn() as conn:
                conn.execute(
                    """
                    UPDATE class_commentary_generations
                    SET feedback_schema_version='class_commentary.student_feedback.v1',
                        structured_feedback_json=?, structured_feedback_hash=?,
                        generated_feedback_text=?
                    WHERE id=?
                    """,
                    (corrupt_json, corrupt_hash, corrupt_text, generation["id"]),
                )
            corrupt_record = self.client.get(generation_url, headers=self.headers).get_json()
            self.assertEqual(corrupt_record["feedback_schema_status"], "invalid")
            self.assertEqual(corrupt_record["student_feedback_items"], [])
            self.assertFalse(corrupt_record["writable"])

    def test_nonempty_schema_rejects_legacy_writes_without_mutating_feedback_state(self):
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")
        skill = self._register_skill("structured-write-floor", "structured write floor")
        generation = self._create_succeeded_generation(task, skill)
        roster = json.loads(generation["attending_roster_snapshot_json"])
        student_id = int(roster[0]["student_id"])
        student_name = str(roster[0]["student_name"])
        feedback_text = "今天课堂计算更稳定."
        derived_text = f"{student_name}:\n{feedback_text}"
        structured_payload = {
            "schema_version": "class_commentary.student_feedback.v1",
            "items": [{"student_id": student_id, "feedback_text": feedback_text}],
        }
        structured_json = json.dumps(
            structured_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        structured_hash = hashlib.sha256(structured_json.encode("utf-8")).hexdigest()
        eligible_ids = [student_id]
        eligible_scope_json = json.dumps(
            {
                "attending_roster_hash": generation["attending_roster_hash"],
                "confirmed_transcript_hash": generation["confirmed_transcript_hash"],
                "eligible_student_ids": eligible_ids,
                "student_mention_matcher_version": (
                    "class_commentary.student_name_matcher.v1"
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        eligible_scope_hash = hashlib.sha256(
            eligible_scope_json.encode("utf-8")
        ).hexdigest()
        draft_url = (
            f"/api/class-commentary/tasks/{task['id']}/generations/"
            f"{generation['id']}/feedback-draft"
        )
        confirmation_url = f"/api/class-commentary/tasks/{task['id']}/feedback-confirmations"
        plain_draft_payload = {"feedback_text": derived_text, "expected_draft_version": 0}
        plain_confirmation_payload = {
            "generation_id": generation["id"],
            "feedback_text": derived_text,
            "learn": False,
            "expected_draft_version": 0,
            "request_id": "compatibility-floor-write",
        }

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET feedback_schema_version='future.student-feedback.v2',
                    structured_feedback_json='future-json', structured_feedback_hash='future-hash',
                    generated_feedback_text=?
                WHERE id=?
                """,
                (derived_text, generation["id"]),
            )
        unknown_draft = self.client.put(draft_url, headers=self.headers, json=plain_draft_payload)
        unknown_confirmation = self.client.post(
            confirmation_url,
            headers=self.headers,
            json=plain_confirmation_payload,
        )
        self.assertEqual(unknown_draft.status_code, 409)
        self.assertEqual(unknown_draft.get_json(), {"error": "feedback_schema_unsupported"})
        self.assertEqual(unknown_confirmation.status_code, 409)
        self.assertEqual(unknown_confirmation.get_json(), {"error": "feedback_schema_unsupported"})

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET feedback_schema_version=' ', structured_feedback_json='',
                    structured_feedback_hash=''
                WHERE id=?
                """,
                (generation["id"],),
            )
        whitespace_draft = self.client.put(
            draft_url,
            headers=self.headers,
            json=plain_draft_payload,
        )
        self.assertEqual(whitespace_draft.status_code, 409)
        self.assertEqual(
            whitespace_draft.get_json(),
            {"error": "feedback_schema_unsupported"},
        )

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET feedback_schema_version='class_commentary.student_feedback.v1',
                    structured_feedback_json='{}', structured_feedback_hash='bad-hash',
                    eligible_student_ids_json=?
                WHERE id=?
                """,
                (json.dumps([student_id]), generation["id"]),
            )
        invalid_draft = self.client.put(draft_url, headers=self.headers, json=plain_draft_payload)
        invalid_confirmation = self.client.post(
            confirmation_url,
            headers=self.headers,
            json={**plain_confirmation_payload, "request_id": "compatibility-floor-invalid"},
        )
        self.assertEqual(invalid_draft.status_code, 409)
        self.assertEqual(invalid_draft.get_json(), {"error": "feedback_schema_invalid"})
        self.assertEqual(invalid_confirmation.status_code, 409)
        self.assertEqual(invalid_confirmation.get_json(), {"error": "feedback_schema_invalid"})

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET structured_feedback_json=?, structured_feedback_hash=?,
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
                    json.dumps(eligible_ids, separators=(",", ":")),
                    eligible_scope_hash,
                    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
                    generation["id"],
                ),
            )
        supported_draft = self.client.put(draft_url, headers=self.headers, json=plain_draft_payload)
        supported_confirmation = self.client.post(
            confirmation_url,
            headers=self.headers,
            json={**plain_confirmation_payload, "request_id": "compatibility-floor-supported"},
        )
        self.assertEqual(supported_draft.status_code, 400)
        self.assertEqual(supported_draft.get_json(), {"error": "feedback_schema_mismatch"})
        self.assertEqual(supported_confirmation.status_code, 400)
        self.assertEqual(supported_confirmation.get_json(), {"error": "feedback_schema_mismatch"})

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET feedback_schema_version='', structured_feedback_json='',
                    structured_feedback_hash='', eligible_student_ids_json='[]'
                WHERE id=?
                """,
                (generation["id"],),
            )
        structured_request = {
            "feedback_schema_version": structured_payload["schema_version"],
            "student_feedback_items": structured_payload["items"],
            "expected_draft_version": 0,
        }
        self.assertEqual(
            self.client.put(draft_url, headers=self.headers, json=structured_request).get_json(),
            {"error": "feedback_schema_mismatch"},
        )
        self.assertEqual(
            self.client.post(
                confirmation_url,
                headers=self.headers,
                json={
                    **structured_request,
                    "generation_id": generation["id"],
                    "learn": False,
                    "request_id": "compatibility-floor-structured-body",
                },
            ).get_json(),
            {"error": "feedback_schema_mismatch"},
        )
        with lesson_manager.get_conn() as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM class_commentary_feedback_drafts WHERE task_id=?",
                (task["id"],),
            ).fetchone()[0], 0)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM class_commentary_revisions WHERE task_id=?",
                (task["id"],),
            ).fetchone()[0], 0)
        current_task = lesson_manager.get_class_commentary_task(task["id"])
        self.assertIsNone(current_task["latest_revision_id"])
        self.assertEqual(current_task["final_feedback_text"], "")

    def test_generation_feedback_draft_get_put_uses_cas(self):
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")
        skill = self._register_skill("draft-api-style", "draft registry content")
        generation = self._create_succeeded_generation(task, skill)
        draft_url = (
            f"/api/class-commentary/tasks/{task['id']}/generations/"
            f"{generation['id']}/feedback-draft"
        )

        created_response = self.client.put(
            draft_url,
            headers=self.headers,
            json={"feedback_text": "草稿第一版", "expected_draft_version": 0},
        )
        read_response = self.client.get(draft_url, headers=self.headers)
        updated_response = self.client.put(
            draft_url,
            headers=self.headers,
            json={"feedback_text": "草稿第二版", "expected_draft_version": 1},
        )
        stale_response = self.client.put(
            draft_url,
            headers=self.headers,
            json={"feedback_text": "旧标签页覆盖", "expected_draft_version": 1},
        )

        self.assertEqual(created_response.status_code, 200)
        created = self._unwrap_payload(created_response.get_json(), "draft")
        self.assertEqual(created["feedback_text"], "草稿第一版")
        self.assertEqual(created["draft_version"], 1)
        self.assertEqual(created["feedback_schema_status"], "plain_text")
        self.assertEqual(created["student_feedback_items"], [])
        self.assertEqual(created["derived_feedback_text"], "草稿第一版")
        self.assertTrue(created["writable"])
        self.assertEqual(read_response.status_code, 200)
        read_draft = self._unwrap_payload(read_response.get_json(), "draft")
        self.assertEqual(read_draft["feedback_text"], "草稿第一版")
        self.assertEqual(read_draft["draft_version"], 1)
        self.assertEqual(updated_response.status_code, 200)
        updated = self._unwrap_payload(updated_response.get_json(), "draft")
        self.assertEqual(updated["feedback_text"], "草稿第二版")
        self.assertEqual(updated["draft_version"], 2)
        self.assertEqual(stale_response.status_code, 409)
        conflict = stale_response.get_json()
        self.assertEqual(set(conflict), {"error", "current_draft"})
        self.assertEqual(conflict["error"], "draft_version_conflict")
        self.assertEqual(conflict["current_draft"]["feedback_text"], "草稿第二版")
        self.assertEqual(conflict["current_draft"]["draft_version"], 2)
        self.assertEqual(conflict["current_draft"]["feedback_schema_status"], "plain_text")
        self.assertEqual(conflict["current_draft"]["derived_feedback_text"], "草稿第二版")

    def test_structured_feedback_draft_api_canonicalizes_and_returns_safe_conflicts(self):
        class_id = self._create_class_with_student()
        lesson_manager.create_student_for_class(class_id, "小李")
        task = self._create_transcribed_task(class_id, "小李完成计算, 小王补充验算.")
        skill = self._register_skill("structured-draft-api", "structured draft api")
        generation = self._create_succeeded_generation(task, skill)
        roster = json.loads(generation["attending_roster_snapshot_json"])
        students_by_name = {str(item["student_name"]): item for item in roster}
        first_id = int(students_by_name["小王"]["student_id"])
        second_id = int(students_by_name["小李"]["student_id"])
        generation = self._promote_generation_to_structured(
            generation,
            {
                first_id: "计算过程更稳定.",
                second_id: "验算意识有进步.",
            },
        )
        draft_url = (
            f"/api/class-commentary/tasks/{task['id']}/generations/"
            f"{generation['id']}/feedback-draft"
        )
        created_response = self.client.put(
            draft_url,
            headers=self.headers,
            json={
                "feedback_schema_version": "class_commentary.student_feedback.v1",
                "student_feedback_items": [
                    {"student_id": second_id, "feedback_text": "继续主动验算.  \n"},
                    {"student_id": first_id, "feedback_text": "计算表达更清晰."},
                ],
                "expected_draft_version": 0,
                "based_on_revision_id": None,
            },
        )
        self.assertEqual(created_response.status_code, 200)
        created = created_response.get_json()["draft"]
        self.assertEqual(created["feedback_schema_status"], "supported")
        self.assertEqual(
            created["student_feedback_items"],
            [
                {
                    "student_id": first_id,
                    "student_name": "小王",
                    "feedback_text": "计算表达更清晰.",
                },
                {
                    "student_id": second_id,
                    "student_name": "小李",
                    "feedback_text": "继续主动验算.",
                },
            ],
        )
        self.assertEqual(
            created["derived_feedback_text"],
            "小王:\n计算表达更清晰.\n\n小李:\n继续主动验算.",
        )
        self.assertEqual(created["feedback_text"], created["derived_feedback_text"])
        self.assertEqual(created["content_hash"], created["structured_feedback_hash"])

        updated_response = self.client.put(
            draft_url,
            headers=self.headers,
            json={
                "feedback_schema_version": "class_commentary.student_feedback.v1",
                "student_feedback_items": [
                    {"student_id": first_id, "feedback_text": "计算表达稳定."},
                    {"student_id": second_id, "feedback_text": "继续主动验算."},
                ],
                "expected_draft_version": 1,
            },
        )
        self.assertEqual(updated_response.status_code, 200)
        current = updated_response.get_json()["draft"]
        self.assertEqual(current["draft_version"], 2)
        stale_response = self.client.put(
            draft_url,
            headers=self.headers,
            json={
                "feedback_schema_version": "class_commentary.student_feedback.v1",
                "student_feedback_items": [
                    {"student_id": first_id, "feedback_text": "旧标签页内容."},
                    {"student_id": second_id, "feedback_text": "继续主动验算."},
                ],
                "expected_draft_version": 1,
            },
        )
        self.assertEqual(stale_response.status_code, 409)
        self.assertEqual(stale_response.get_json()["current_draft"], current)

        unsafe_name_response = self.client.put(
            draft_url,
            headers=self.headers,
            json={
                "feedback_schema_version": "class_commentary.student_feedback.v1",
                "student_feedback_items": [
                    {
                        "student_id": first_id,
                        "student_name": "客户端姓名",
                        "feedback_text": "不能信任客户端姓名.",
                    },
                    {"student_id": second_id, "feedback_text": "继续主动验算."},
                ],
                "expected_draft_version": 2,
            },
        )
        self.assertEqual(unsafe_name_response.status_code, 400)
        self.assertEqual(
            unsafe_name_response.get_json(),
            {"error": "structured_feedback_invalid"},
        )
        unknown_student_response = self.client.put(
            draft_url,
            headers=self.headers,
            json={
                "feedback_schema_version": "class_commentary.student_feedback.v1",
                "student_feedback_items": [
                    {"student_id": 999999, "feedback_text": "不应泄露的正文."},
                    {"student_id": second_id, "feedback_text": "继续主动验算."},
                ],
                "expected_draft_version": 2,
            },
        )
        self.assertEqual(unknown_student_response.status_code, 400)
        self.assertEqual(
            unknown_student_response.get_json(),
            {
                "error": "student_feedback_unknown_student",
                "student_id": 999999,
                "field": "student_id",
            },
        )
        self.assertNotIn("不应泄露的正文", unknown_student_response.get_data(as_text=True))
        mixed_response = self.client.put(
            draft_url,
            headers=self.headers,
            json={
                "feedback_schema_version": "class_commentary.student_feedback.v1",
                "student_feedback_items": [],
                "feedback_text": "第二来源",
                "expected_draft_version": 2,
            },
        )
        self.assertEqual(mixed_response.status_code, 400)
        self.assertEqual(mixed_response.get_json(), {"error": "feedback_schema_mismatch"})
        read_response = self.client.get(draft_url, headers=self.headers)
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.get_json()["draft"], current)

    def test_feedback_confirmation_contract_is_idempotent_and_memory_is_disabled(self):
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")
        skill = self._register_skill("confirmation-api-style", "confirmation registry content")
        generation = self._create_succeeded_generation(task, skill)
        confirmation_url = f"/api/class-commentary/tasks/{task['id']}/feedback-confirmations"
        confirmation_payload = {
            "generation_id": generation["id"],
            "feedback_text": "小王: 计算更稳定, 建议继续验算.",
            "learn": False,
            "expected_draft_version": 0,
            "request_id": "confirmation-api-idempotent",
        }

        first_response = self.client.post(
            confirmation_url,
            headers=self.headers,
            json=confirmation_payload,
        )
        repeated_response = self.client.post(
            confirmation_url,
            headers=self.headers,
            json=confirmation_payload,
        )
        changed_response = self.client.post(
            confirmation_url,
            headers=self.headers,
            json={**confirmation_payload, "feedback_text": "同一请求的不同终稿"},
        )
        learning_response = self.client.post(
            confirmation_url,
            headers=self.headers,
            json={
                **confirmation_payload,
                "request_id": "confirmation-api-learning-disabled",
                "expected_draft_version": 1,
                "learn": True,
            },
        )
        revisions_response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}/feedback-revisions",
            headers=self.headers,
        )
        draft_response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}/generations/"
            f"{generation['id']}/feedback-draft",
            headers=self.headers,
        )

        self.assertEqual(first_response.status_code, 200)
        first_revision = self._unwrap_payload(first_response.get_json(), "revision")
        revision_id = int(first_revision.get("revision_id") or first_revision["id"])
        self.assertEqual(first_revision["generation_id"], generation["id"])
        self.assertFalse(first_revision["learn_requested"])
        self.assertEqual(first_revision["draft_version"], 1)
        self.assertEqual(first_revision["confirmed_draft_version"], 1)
        self.assertEqual(first_revision["feedback_schema_status"], "plain_text")
        self.assertEqual(first_revision["derived_feedback_text"], confirmation_payload["feedback_text"])
        self.assertEqual(first_response.get_json()["latest_revision_id"], revision_id)
        self.assertEqual(first_response.get_json()["latest_revision_no"], 1)
        self.assertEqual(first_response.get_json()["draft"]["feedback_schema_status"], "plain_text")
        self.assertEqual(repeated_response.status_code, 200)
        repeated_revision = self._unwrap_payload(repeated_response.get_json(), "revision")
        self.assertEqual(
            int(repeated_revision.get("revision_id") or repeated_revision["id"]),
            revision_id,
        )
        self.assertEqual(changed_response.status_code, 409)
        self.assertEqual(learning_response.status_code, 409)
        self.assertEqual(learning_response.get_json(), {"error": "memory_not_enabled"})
        self.assertEqual(revisions_response.status_code, 200)
        revisions = revisions_response.get_json()["revisions"]
        self.assertEqual(len(revisions), 1)
        self.assertEqual(int(revisions[0].get("revision_id") or revisions[0]["id"]), revision_id)
        self.assertEqual(draft_response.status_code, 200)
        draft = self._unwrap_payload(draft_response.get_json(), "draft")
        self.assertEqual(draft["draft_version"], 1)
        self.assertEqual(draft["based_on_revision_id"], revision_id)
        self.assertEqual(draft["feedback_text"], confirmation_payload["feedback_text"])
        self.assertEqual(draft["feedback_schema_status"], "plain_text")
        self.assertEqual(draft["derived_feedback_text"], confirmation_payload["feedback_text"])

    def test_structured_confirmation_api_enforces_task_cas_and_replays_original_snapshot(self):
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")
        skill = self._register_skill("structured-confirm-api", "structured confirm api")
        first_generation = self._promote_generation_to_structured(
            self._create_succeeded_generation(
                task,
                skill,
                request_id="structured-confirm-generation-first",
            ),
            {
                int(lesson_manager.list_students_for_class(class_id)[0]["id"]): (
                    "计算过程更稳定."
                )
            },
        )
        student_id = json.loads(first_generation["eligible_student_ids_json"])[0]
        confirmation_url = f"/api/class-commentary/tasks/{task['id']}/feedback-confirmations"
        first_payload = {
            "generation_id": first_generation["id"],
            "feedback_schema_version": "class_commentary.student_feedback.v1",
            "student_feedback_items": [
                {"student_id": student_id, "feedback_text": "老师确认第一版.  \n"}
            ],
            "learn": False,
            "expected_draft_version": 0,
            "expected_latest_revision_id": None,
            "request_id": "structured-confirm-api-first",
        }
        missing_task_cas = self.client.post(
            confirmation_url,
            headers=self.headers,
            json={key: value for key, value in first_payload.items() if key != "expected_latest_revision_id"},
        )
        self.assertEqual(missing_task_cas.status_code, 400)
        self.assertEqual(
            missing_task_cas.get_json(),
            {"error": "expected_latest_revision_id is required"},
        )
        mixed_body = self.client.post(
            confirmation_url,
            headers=self.headers,
            json={**first_payload, "feedback_text": "第二来源"},
        )
        self.assertEqual(mixed_body.status_code, 400)
        self.assertEqual(mixed_body.get_json(), {"error": "feedback_schema_mismatch"})

        first_response = self.client.post(
            confirmation_url,
            headers=self.headers,
            json=first_payload,
        )
        self.assertEqual(first_response.status_code, 200)
        first = first_response.get_json()
        first_revision_id = int(first["revision_id"])
        self.assertEqual(first["revision"]["feedback_schema_status"], "supported")
        self.assertEqual(first["revision"]["final_feedback_text"], "小王:\n老师确认第一版.")
        self.assertEqual(first["revision"]["confirmed_draft_version"], 1)
        self.assertEqual(first["draft"]["draft_version"], 1)
        self.assertEqual(
            first["draft"]["student_feedback_items"],
            first["revision"]["student_feedback_items"],
        )

        first_draft_url = (
            f"/api/class-commentary/tasks/{task['id']}/generations/"
            f"{first_generation['id']}/feedback-draft"
        )
        later_draft_response = self.client.put(
            first_draft_url,
            headers=self.headers,
            json={
                "feedback_schema_version": "class_commentary.student_feedback.v1",
                "student_feedback_items": [
                    {"student_id": student_id, "feedback_text": "确认后尚未确认的草稿."}
                ],
                "expected_draft_version": 1,
                "based_on_revision_id": first_revision_id,
            },
        )
        self.assertEqual(later_draft_response.status_code, 200)
        self.assertEqual(later_draft_response.get_json()["draft_version"], 2)

        second_generation = self._promote_generation_to_structured(
            self._create_succeeded_generation(
                task,
                skill,
                request_id="structured-confirm-generation-second",
                feedback_text="小王: 新生成反馈.",
            ),
            {student_id: "新生成反馈."},
        )
        second_payload = {
            "generation_id": second_generation["id"],
            "feedback_schema_version": "class_commentary.student_feedback.v1",
            "student_feedback_items": [
                {"student_id": student_id, "feedback_text": "老师确认第二版."}
            ],
            "learn": False,
            "expected_draft_version": 0,
            "expected_latest_revision_id": first_revision_id,
            "request_id": "structured-confirm-api-second",
        }
        second_response = self.client.post(
            confirmation_url,
            headers=self.headers,
            json=second_payload,
        )
        self.assertEqual(second_response.status_code, 200)
        second = second_response.get_json()
        second_revision_id = int(second["revision_id"])

        replay_response = self.client.post(
            confirmation_url,
            headers=self.headers,
            json={
                **first_payload,
                "student_feedback_items": [
                    {"student_id": student_id, "feedback_text": "老师确认第一版."}
                ],
            },
        )
        self.assertEqual(replay_response.status_code, 200)
        replay = replay_response.get_json()
        self.assertEqual(replay["revision"], first["revision"])
        self.assertEqual(replay["draft"], first["draft"])

        changed_replay = self.client.post(
            confirmation_url,
            headers=self.headers,
            json={
                **first_payload,
                "student_feedback_items": [
                    {"student_id": student_id, "feedback_text": "同 key 的不同终稿."}
                ],
            },
        )
        self.assertEqual(changed_replay.status_code, 409)
        self.assertEqual(
            changed_replay.get_json(),
            {"error": "confirmation_request_conflict"},
        )
        malformed_replay = self.client.post(
            confirmation_url,
            headers=self.headers,
            json={
                "request_id": first_payload["request_id"],
                "generation_id": "not-an-id",
                "learn": "not-a-boolean",
                "expected_draft_version": None,
                "feedback_text": "mixed source",
                "feedback_schema_version": "class_commentary.student_feedback.v1",
            },
        )
        self.assertEqual(malformed_replay.status_code, 409)
        self.assertEqual(
            malformed_replay.get_json(),
            {"error": "confirmation_request_conflict"},
        )
        task_conflict = self.client.post(
            confirmation_url,
            headers=self.headers,
            json={
                **first_payload,
                "student_feedback_items": [
                    {"student_id": student_id, "feedback_text": "基于旧 revision 的终稿."}
                ],
                "expected_draft_version": 2,
                "expected_latest_revision_id": first_revision_id,
                "request_id": "structured-confirm-api-stale-task",
            },
        )
        self.assertEqual(task_conflict.status_code, 409)
        conflict = task_conflict.get_json()
        self.assertEqual(conflict["error"], "revision_version_conflict")
        self.assertEqual(conflict["current_latest_revision_id"], second_revision_id)
        self.assertEqual(conflict["current_latest_revision"], second["revision"])
        self.assertEqual(
            self.client.get(first_draft_url, headers=self.headers).get_json()["draft"][
                "draft_version"
            ],
            2,
        )
        revisions = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}/feedback-revisions",
            headers=self.headers,
        ).get_json()["revisions"]
        self.assertEqual([item["id"] for item in revisions], [second_revision_id, first_revision_id])
        for revision in revisions:
            self.assertEqual(revision["feedback_schema_status"], "supported")
            self.assertTrue(revision["student_feedback_items"])
            self.assertTrue(revision["structured_feedback_hash"])
            self.assertEqual(revision["derived_feedback_text"], revision["final_feedback_text"])
            self.assertGreaterEqual(revision["confirmed_draft_version"], 1)

    def test_confirmation_replay_returns_first_transaction_snapshot_after_draft_changes(self):
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")
        skill = self._register_skill("confirmation-replay-style", "confirmation replay content")
        generation = self._create_succeeded_generation(task, skill)
        confirmation_url = f"/api/class-commentary/tasks/{task['id']}/feedback-confirmations"
        draft_url = (
            f"/api/class-commentary/tasks/{task['id']}/generations/"
            f"{generation['id']}/feedback-draft"
        )
        confirmation_payload = {
            "generation_id": generation["id"],
            "feedback_text": "小王: 计算更稳定, 建议继续验算.",
            "learn": False,
            "expected_draft_version": 0,
            "request_id": "confirmation-api-original-transaction-snapshot",
        }

        first_response = self.client.post(
            confirmation_url,
            headers=self.headers,
            json=confirmation_payload,
        )
        self.assertEqual(first_response.status_code, 200)
        first_payload = first_response.get_json()
        first_revision = self._unwrap_payload(first_payload, "revision")
        first_revision_id = int(first_revision.get("revision_id") or first_revision["id"])
        self.assertEqual(first_revision["draft_version"], 1)
        self.assertEqual(first_payload["draft"]["draft_version"], 1)

        later_draft_response = self.client.put(
            draft_url,
            headers=self.headers,
            json={
                "feedback_text": "小王: 这是确认后尚未再次确认的草稿.",
                "expected_draft_version": 1,
                "based_on_revision_id": first_revision_id,
            },
        )
        self.assertEqual(later_draft_response.status_code, 200)
        self.assertEqual(later_draft_response.get_json()["draft_version"], 2)

        replayed_response = self.client.post(
            confirmation_url,
            headers=self.headers,
            json=confirmation_payload,
        )

        self.assertEqual(replayed_response.status_code, 200)
        replayed_payload = replayed_response.get_json()
        self.assertEqual(replayed_payload["revision"], first_payload["revision"])
        self.assertEqual(replayed_payload["draft"], first_payload["draft"])

        live_draft_response = self.client.get(draft_url, headers=self.headers)
        self.assertEqual(live_draft_response.status_code, 200)
        live_draft = self._unwrap_payload(live_draft_response.get_json(), "draft")
        self.assertEqual(live_draft["draft_version"], 2)
        self.assertEqual(live_draft["feedback_text"], "小王: 这是确认后尚未再次确认的草稿.")

    def test_class_access_without_task_ownership_cannot_mutate_or_view_generation_detail(self):
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")
        skill = self._register_skill("owner-only-style", "owner only registry content")
        generation = self._create_succeeded_generation(task, skill)
        member_id, member_token = self._create_member("commentary_non_owner_member")
        lesson_manager.set_class_teacher_user_id(class_id, member_id)
        member_headers = {"X-Auth-Token": member_token}

        task_response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}",
            headers=member_headers,
        )
        with patch.object(self.app_module, "has_class_commentary_api_key", return_value=True), \
             patch.object(self.app_module, "_run_ai_feature_with_charge") as charge:
            generate_response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=member_headers,
                json={
                    "request_id": "non-owner-generate",
                    "skill_id": "owner-only-style",
                },
            )
        detail_response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}/generations/{generation['id']}",
            headers=member_headers,
        )
        generation_list_response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}/generations",
            headers=member_headers,
        )
        revision_list_response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}/feedback-revisions",
            headers=member_headers,
        )
        draft_get_response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}/generations/"
            f"{generation['id']}/feedback-draft",
            headers=member_headers,
        )
        draft_put_response = self.client.put(
            f"/api/class-commentary/tasks/{task['id']}/generations/"
            f"{generation['id']}/feedback-draft",
            headers=member_headers,
            json={"feedback_text": "越权草稿", "expected_draft_version": 0},
        )
        confirm_response = self.client.post(
            f"/api/class-commentary/tasks/{task['id']}/feedback-confirmations",
            headers=member_headers,
            json={
                "generation_id": generation["id"],
                "feedback_text": "越权终稿",
                "learn": False,
                "expected_draft_version": 0,
                "request_id": "non-owner-confirmation",
            },
        )

        self.assertEqual(task_response.status_code, 200)
        self.assertEqual(generate_response.status_code, 403)
        charge.assert_not_called()
        self.assertEqual(detail_response.status_code, 403)
        self.assertEqual(generation_list_response.status_code, 403)
        self.assertEqual(revision_list_response.status_code, 403)
        self.assertEqual(draft_get_response.status_code, 403)
        self.assertEqual(draft_put_response.status_code, 403)
        self.assertEqual(confirm_response.status_code, 403)
        self.assertEqual(lesson_manager.list_class_commentary_revisions(task["id"]), [])

    def test_super_owner_can_read_other_teacher_history_but_cannot_mutate_it(self):
        class_id = self._create_class_with_student()
        member_id, _ = self._create_member("commentary_history_teacher")
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=member_id,
            audio_path=str(self.base / "other-teacher.m4a"),
            audio_filename="other-teacher.m4a",
        )
        task = lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            "小王今天计算有进步",
        )
        skill = self._register_skill(
            "super-owner-read-style",
            "super owner read registry content",
            owner_user_id=member_id,
        )
        generation = self._create_succeeded_generation(task, skill)
        draft = lesson_manager.save_class_commentary_feedback_draft(
            task_id=task["id"],
            generation_id=generation["id"],
            teacher_user_id=member_id,
            feedback_text="其他老师的草稿",
            expected_draft_version=0,
        )
        lesson_manager.confirm_class_commentary_feedback(
            task_id=task["id"],
            generation_id=generation["id"],
            teacher_user_id=member_id,
            feedback_text="其他老师的终稿",
            learn_requested=False,
            expected_draft_version=draft["draft_version"],
            confirmation_request_id="other-teacher-confirmation",
        )
        task_url = f"/api/class-commentary/tasks/{task['id']}"
        generation_url = f"{task_url}/generations/{generation['id']}"
        draft_url = f"{generation_url}/feedback-draft"

        list_response = self.client.get("/api/class-commentary/tasks", headers=self.headers)
        task_response = self.client.get(task_url, headers=self.headers)
        generations_response = self.client.get(f"{task_url}/generations", headers=self.headers)
        generation_response = self.client.get(generation_url, headers=self.headers)
        draft_response = self.client.get(draft_url, headers=self.headers)
        revisions_response = self.client.get(f"{task_url}/feedback-revisions", headers=self.headers)

        listed_task = next(
            item for item in list_response.get_json()["tasks"] if item["id"] == task["id"]
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(listed_task["confirmed_transcript_text"], "小王今天计算有进步")
        self.assertEqual(task_response.status_code, 200)
        self.assertEqual(task_response.get_json()["feedback_text"], "其他老师的终稿")
        self.assertEqual(generations_response.status_code, 200)
        self.assertEqual(generation_response.status_code, 200)
        self.assertEqual(
            generation_response.get_json()["confirmed_transcript_snapshot"],
            "小王今天计算有进步",
        )
        self.assertEqual(draft_response.status_code, 200)
        self.assertEqual(draft_response.get_json()["feedback_text"], "其他老师的终稿")
        self.assertEqual(revisions_response.status_code, 200)
        self.assertEqual(revisions_response.get_json()["revisions"][0]["final_feedback_text"], "其他老师的终稿")

        with patch.object(self.app_module, "has_class_commentary_api_key", return_value=True), \
             patch.object(self.app_module, "_run_ai_feature_with_charge") as charge:
            generate_response = self.client.post(
                f"{task_url}/generate",
                headers=self.headers,
                json={"request_id": "super-owner-generate", "skill_id": skill["skill_id"]},
            )
        transcript_response = self.client.put(
            f"{task_url}/transcript",
            headers=self.headers,
            json={"confirmed_transcript_text": "管理员越权修改"},
        )
        draft_put_response = self.client.put(
            draft_url,
            headers=self.headers,
            json={"feedback_text": "管理员越权草稿", "expected_draft_version": 2},
        )
        confirmation_response = self.client.post(
            f"{task_url}/feedback-confirmations",
            headers=self.headers,
            json={
                "generation_id": generation["id"],
                "feedback_text": "管理员越权终稿",
                "learn": False,
                "expected_draft_version": 2,
                "request_id": "super-owner-confirmation",
            },
        )

        self.assertEqual(generate_response.status_code, 403)
        charge.assert_not_called()
        self.assertEqual(transcript_response.status_code, 403)
        self.assertEqual(draft_put_response.status_code, 403)
        self.assertEqual(confirmation_response.status_code, 403)

    def test_class_access_without_task_ownership_only_returns_public_final_summary(self):
        transcript = "小王今天计算有进步, 但还要继续验算."
        generated_feedback = "AI 原稿: 小王计算有进步."
        final_feedback = "老师终稿: 小王计算更稳定, 请继续验算."
        class_id = self._create_class_with_student()
        task = self._create_transcribed_task(class_id, transcript)
        skill = self._register_skill("public-summary-style", "public summary style")
        generation = self._create_succeeded_generation(
            task,
            skill,
            request_id="generation-public-summary",
            feedback_text=generated_feedback,
        )
        lesson_manager.confirm_class_commentary_feedback(
            task_id=task["id"],
            generation_id=generation["id"],
            teacher_user_id=self.owner["id"],
            feedback_text=final_feedback,
            learn_requested=False,
            expected_draft_version=0,
            confirmation_request_id="confirmation-public-summary",
        )
        member_id, member_token = self._create_member("commentary_public_summary_member")
        lesson_manager.set_class_teacher_user_id(class_id, member_id)
        member_headers = {"X-Auth-Token": member_token}

        detail_response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}",
            headers=member_headers,
        )
        list_response = self.client.get(
            "/api/class-commentary/tasks",
            headers=member_headers,
        )

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(list_response.status_code, 200)
        detail = detail_response.get_json()
        listed = next(
            item
            for item in list_response.get_json()["tasks"]
            if item["id"] == task["id"]
        )
        for payload in (detail, listed):
            self.assertEqual(payload["final_feedback_text"], final_feedback)
            self.assertNotIn("transcript_text", payload)
            self.assertNotIn("confirmed_transcript_text", payload)
            self.assertNotIn("feedback_text", payload)
            serialized = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn(transcript, serialized)
            self.assertNotIn(generated_feedback, serialized)

    def test_generate_saves_skill_snapshot_and_feedback(self):
        config_runtime.write_file_config(
            {
                "colleague_skill_dir": str(self.skill_dir),
                "provider": "deepseek",
                "deepseek_model": "deepseek-v4-pro",
                "class_commentary_provider": "openai",
                "class_commentary_model": "gpt-5.5",
                "class_commentary_openai_api_key": "sk-class-test",
                "class_commentary_openai_base_url": "https://api.iiiiitoken.com",
                "class_commentary_openai_headers": '{"X-Trace":"aimami"}',
                "class_commentary_structured_feedback_enabled": True,
            }
        )
        class_id = self._create_class_with_student()
        self._register_skill("teacher-a", "warm direct style")
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")
        students = lesson_manager.list_students_for_class(class_id)
        model_output = self._batch_model_output(students)
        charged = []

        with self._batch_runtime(), \
             patch.object(
                 self.app_module,
                 "generate_class_commentary_feedback",
                 return_value=(model_output, {"input_tokens": 3, "output_tokens": 2}),
             ), patch.object(
                 self.app_module,
                 "finalize_ai_charge",
                 wraps=self.app_module.finalize_ai_charge,
             ) as charge:
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    "request_id": "generation-provider-config",
                    "skill_id": "teacher-a",
                    "attending_student_ids": [student["id"] for student in students],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertIsInstance(payload["generation_id"], int)
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["task_status"], "ready")
        self.assertEqual(payload["generation_status"], "succeeded")
        self.assertEqual(payload["skill_id"], "teacher-a")
        expected_feedback = payload["derived_feedback_text"]
        self.assertIn("🌱", expected_feedback)
        self.assertEqual(payload["feedback_text"], expected_feedback)
        self.assertEqual(
            payload["generation"]["generated_feedback_text"],
            expected_feedback,
        )
        charged.append(charge.call_args.kwargs)
        self.assertEqual(charged[0]["usage"]["provider"], "openai")
        self.assertEqual(charged[0]["usage"]["model"], "gpt-5.5")
        stored = lesson_manager.get_class_commentary_task(task["id"])
        self.assertEqual(stored["status"], "ready")
        self.assertEqual(stored["feedback_text"], expected_feedback)
        self.assertEqual(stored["chat_provider"], "openai")
        self.assertEqual(stored["chat_model"], "gpt-5.5")

    def test_generate_filters_students_to_attending_roster(self):
        self._configure_batch_generation()
        class_id = lesson_manager.save_class(
            "数学·七年级·5班",
            subject="数学",
            grade="七年级",
            organization_id=self.owner["organization_id"],
            teacher_user_id=self.owner["id"],
        )
        present_student = lesson_manager.create_student_for_class(class_id, "小王")
        absent_student = lesson_manager.create_student_for_class(class_id, "小李")
        another_present_student = lesson_manager.create_student_for_class(class_id, "小张")
        self._register_skill("teacher-a", "warm direct style")
        task = self._create_transcribed_task(
            class_id,
            "小王今天计算有进步. 小张今天计算有进步.",
        )

        def fake_charge(**kwargs):
            result = kwargs["producer"]()
            return result[0] if isinstance(result, tuple) else result

        selected_students = [present_student, another_present_student]
        with self._batch_runtime(), \
             patch.object(self.app_module, "_run_ai_feature_with_charge", side_effect=fake_charge), \
             patch.object(
                 self.app_module,
                 "generate_class_commentary_feedback",
                 return_value=(
                     self._batch_model_output(selected_students),
                     {"input_tokens": 3, "output_tokens": 2},
                 ),
             ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    "request_id": "generation-attending-roster",
                    "skill_id": "teacher-a",
                    "attending_student_ids": [present_student["id"], another_present_student["id"]],
                },
            )

        self.assertEqual(response.status_code, 200)
        generate.assert_called_once()
        sent_students = generate.call_args.kwargs["students"]
        self.assertEqual([student["id"] for student in sent_students], [present_student["id"], another_present_student["id"]])
        self.assertNotIn(absent_student["id"], [student["id"] for student in sent_students])

    def test_generate_failure_fails_closed_without_provider_replay(self):
        self._configure_batch_generation()
        class_id = self._create_class_with_student()
        self._register_skill("teacher-a", "warm direct style")
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")
        students = lesson_manager.list_students_for_class(class_id)

        with self._batch_runtime(), \
             patch.object(
                 self.app_module,
                 "generate_class_commentary_feedback",
                 side_effect=RuntimeError("model timeout"),
             ):
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    "request_id": "generation-model-timeout",
                    "skill_id": "teacher-a",
                    "attending_student_ids": [student["id"] for student in students],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["task"]["status"], "failed")
        self.assertEqual(payload["generation_status"], "failed")
        saved = lesson_manager.get_class_commentary_generation(
            int(payload["generation_id"])
        )
        self.assertEqual(saved["batch_attempt_count"], 1)
        self.assertEqual(saved["error_code"], "provider_timeout")
        provider_failure = lesson_manager.get_class_commentary_batch_provider_failure(
            int(payload["generation_id"])
        )
        self.assertEqual(
            provider_failure["exception_type"],
            "builtins.RuntimeError",
        )
        self.assertEqual(provider_failure["result_state"], "unknown")
        self.assertEqual(
            payload["generation"]["provider_failure"],
            provider_failure,
        )
        hold = lesson_manager.get_class_commentary_generation_credit_hold(
            int(payload["generation_id"])
        )
        self.assertEqual(hold["status"], "released")


if __name__ == "__main__":
    unittest.main()
