import io
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager


class ClassCommentaryApiTestCase(unittest.TestCase):
    def setUp(self):
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

    def tearDown(self):
        self.upload_patch.stop()
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

    def test_old_class_feedback_routes_are_removed(self):
        response = self.client.get("/api/class-feedback/labels", headers=self.headers)
        self.assertEqual(response.status_code, 404)

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

    def test_worker_success_moves_task_to_transcribed(self):
        class_id = self._create_class_with_student()
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )

        with patch.object(self.app_module, "_run_ai_feature_with_charge", return_value="小王今天计算有进步") as charge:
            self.app_module._run_class_commentary_transcription(
                task["id"],
                str(self.base / "audio.m4a"),
                {"id": self.owner["id"], "organization_id": self.owner["organization_id"]},
                "saved-audio-request-key",
            )

        saved = lesson_manager.get_class_commentary_task(task["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "transcribed")
        self.assertEqual(saved["transcript_text"], "小王今天计算有进步")
        self.assertEqual(charge.call_args.kwargs["request_key"], "saved-audio-request-key")

    def test_generate_saves_skill_snapshot_and_feedback(self):
        class_id = self._create_class_with_student()
        (self.skill_dir / "teacher-a.skill").write_text("warm direct style", encoding="utf-8")
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")

        with patch.object(self.app_module, "has_review_plan_api_key", return_value=True), \
             patch.object(self.app_module, "_run_ai_feature_with_charge", return_value="小王:\n今天计算有进步."):
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={"skill_id": "teacher-a"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["skill_id"], "teacher-a")
        self.assertEqual(payload["feedback_text"], "小王:\n今天计算有进步.")

    def test_generate_failure_returns_500_with_failed_task_payload(self):
        class_id = self._create_class_with_student()
        (self.skill_dir / "teacher-a.skill").write_text("warm direct style", encoding="utf-8")
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")

        with patch.object(self.app_module, "has_review_plan_api_key", return_value=True), \
             patch.object(self.app_module, "_run_ai_feature_with_charge", side_effect=RuntimeError("model timeout")):
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={"skill_id": "teacher-a"},
            )

        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["error"], "model timeout")
        self.assertEqual(payload["task"]["status"], "failed")
        self.assertEqual(payload["task"]["failure_stage"], "generation")
        self.assertEqual(payload["task"]["generation_error"], "model timeout")


if __name__ == "__main__":
    unittest.main()
