import hashlib
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_runtime
import lesson_manager


class ClassCommentaryTranscriptReservationCasTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.old_db_path = lesson_manager.DB_PATH
        self.old_cfg_path = config_runtime.CFG_PATH
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        self.skill_dir = self.base / "skills"
        self.skill_dir.mkdir(parents=True, exist_ok=True)
        config_runtime.write_file_config(
            {
                "colleague_skill_dir": str(self.skill_dir),
                "class_commentary_structured_feedback_enabled": True,
            }
        )
        lesson_manager.init_db()

        self.teacher = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class(
            "转录快照并发测试班",
            subject="数学",
            grade="七年级",
            organization_id=self.teacher["organization_id"],
            teacher_user_id=self.teacher["id"],
        )
        self.student = lesson_manager.create_student_for_class(
            self.class_id, "小王"
        )
        self.roster = [
            {
                "student_id": int(self.student["id"]),
                "student_name": str(self.student["name"]),
            }
        ]
        created_task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.teacher["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )
        self.initial_transcript = "小王今天计算更稳了。"
        self.task = lesson_manager.mark_class_commentary_transcription_succeeded(
            created_task["id"], self.initial_transcript
        )
        imported = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.teacher["organization_id"],
            skill_id="transcript-cas-teacher",
            actor_user_id=self.teacher["id"],
            source_path=str(self.skill_dir / "transcript-cas-teacher.skill"),
            content="先写本次表现, 再给具体建议。",
        )
        self.skill_registry_id = int(imported["registry_id"])

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db_path
        config_runtime.CFG_PATH = self.old_cfg_path
        self.tmp.cleanup()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _reserve(self, request_id: str, *, version: int, transcript_hash: str):
        return lesson_manager.reserve_class_commentary_generation(
            task_id=int(self.task["id"]),
            generation_request_id=request_id,
            skill_registry_id=self.skill_registry_id,
            attending_roster=self.roster,
            model_provider="openai",
            model_name="gpt-test",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-v1",
            attending_roster_explicit=True,
            expected_confirmed_transcript_version=version,
            expected_confirmed_transcript_hash=transcript_hash,
        )

    def _generation_count(self) -> int:
        with lesson_manager.get_conn() as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_generations WHERE task_id=?",
                    (int(self.task["id"]),),
                ).fetchone()[0]
            )

    def test_stale_version_and_hash_fail_before_any_generation_write(self):
        before = lesson_manager.get_class_commentary_task(int(self.task["id"]))
        updated_transcript = "小王今天计算和验算都更稳了。"
        updated = lesson_manager.save_class_commentary_transcript(
            int(self.task["id"]), updated_transcript
        )

        with self.assertRaises(
            lesson_manager.ClassCommentaryTranscriptSnapshotConflict
        ) as raised:
            self._reserve(
                "stale-transcript-request",
                version=int(before["confirmed_transcript_version"]),
                transcript_hash=self._hash(self.initial_transcript),
            )

        self.assertEqual(raised.exception.code, "confirmed_transcript_changed")
        after = lesson_manager.get_class_commentary_task(int(self.task["id"]))
        self.assertEqual(self._generation_count(), 0)
        self.assertEqual(after["generation_seq"], before["generation_seq"])
        self.assertEqual(after["latest_generation_id"], before["latest_generation_id"])
        self.assertEqual(
            after["confirmed_transcript_version"],
            updated["confirmed_transcript_version"],
        )

    def test_current_version_and_hash_freeze_the_exact_snapshot(self):
        current = lesson_manager.get_class_commentary_task(int(self.task["id"]))

        generation = self._reserve(
            "current-transcript-request",
            version=int(current["confirmed_transcript_version"]),
            transcript_hash=self._hash(self.initial_transcript),
        )

        self.assertEqual(self._generation_count(), 1)
        self.assertEqual(
            generation["confirmed_transcript_version"],
            current["confirmed_transcript_version"],
        )
        self.assertEqual(
            generation["confirmed_transcript_snapshot"], self.initial_transcript
        )
        self.assertEqual(
            generation["confirmed_transcript_hash"],
            self._hash(self.initial_transcript),
        )


class ClassCommentaryTranscriptReservationCasApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.old_db_path = lesson_manager.DB_PATH
        self.old_cfg_path = config_runtime.CFG_PATH
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        self.skill_dir = self.base / "skills"
        self.skill_dir.mkdir(parents=True, exist_ok=True)
        config_runtime.write_file_config(
            {
                "colleague_skill_dir": str(self.skill_dir),
                "class_commentary_structured_feedback_enabled": True,
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
        self.teacher = payload["user"]
        self.headers = {"X-Auth-Token": payload["token"]}
        lesson_manager.insert_credit_ledger_entry(
            organization_id=self.teacher["organization_id"],
            direction="credit",
            amount=100,
            source_type="manual_adjustment",
            source_id="class-commentary-transcript-cas-api-tests",
            note="test credits",
            operator_user_id=self.teacher["id"],
        )
        self.class_id = lesson_manager.save_class(
            "转录快照路由并发测试班",
            subject="数学",
            grade="七年级",
            organization_id=self.teacher["organization_id"],
            teacher_user_id=self.teacher["id"],
        )
        self.student = lesson_manager.create_student_for_class(
            self.class_id, "小王"
        )
        created_task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.teacher["id"],
            audio_path=str(self.base / "route-audio.m4a"),
            audio_filename="route-audio.m4a",
        )
        self.task = lesson_manager.mark_class_commentary_transcription_succeeded(
            created_task["id"], "小王今天计算更稳了。"
        )
        lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.teacher["organization_id"],
            skill_id="route-transcript-cas-teacher",
            actor_user_id=self.teacher["id"],
            source_path=str(self.skill_dir / "route-transcript-cas-teacher.skill"),
            content="先写本次表现, 再给具体建议。",
        )

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db_path
        config_runtime.CFG_PATH = self.old_cfg_path
        self.tmp.cleanup()

    def test_route_returns_409_without_charge_when_transcript_changes_before_reservation(self):
        real_reserve = lesson_manager.reserve_class_commentary_generation

        def mutate_then_reserve(**kwargs):
            lesson_manager.save_class_commentary_transcript(
                int(self.task["id"]), "小王今天计算和验算都更稳了。"
            )
            return real_reserve(**kwargs)

        capabilities = {
            "memory_learning_enabled": True,
            "structured_feedback_enabled": True,
            "student_history_memory_v2_enabled": True,
            "batch_isolated_v3_enabled": True,
            "class_commentary_generation_call_count": 1,
            "graph_enabled": True,
            "graph_healthy": True,
            "graph_degraded": False,
        }
        with patch.object(
            self.app_module, "has_class_commentary_api_key", return_value=True
        ), patch.object(
            self.app_module, "_class_commentary_capabilities", return_value=capabilities
        ), patch.object(
            self.app_module,
            "reserve_class_commentary_generation",
            side_effect=mutate_then_reserve,
        ), patch.object(
            self.app_module, "_run_ai_feature_with_charge"
        ) as charge, patch.object(
            self.app_module, "generate_class_commentary_feedback"
        ) as provider:
            response = self.client.post(
                f"/api/class-commentary/tasks/{int(self.task['id'])}/generate",
                headers=self.headers,
                json={
                    "request_id": "route-transcript-race",
                    "skill_id": "route-transcript-cas-teacher",
                    "attending_student_ids": [int(self.student["id"])],
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json(), {"error": "confirmed_transcript_changed"})
        charge.assert_not_called()
        provider.assert_not_called()
        with lesson_manager.get_conn() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_generations WHERE task_id=?",
                    (int(self.task["id"]),),
                ).fetchone()[0],
                0,
            )
        current = lesson_manager.get_class_commentary_task(int(self.task["id"]))
        self.assertEqual(current["generation_seq"], 0)
        self.assertIsNone(current["latest_generation_id"])


if __name__ == "__main__":
    unittest.main()
