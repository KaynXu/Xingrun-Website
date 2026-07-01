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
    PRIVATE_TRANSCRIPT_POLISH_FIELDS = {
        "raw_transcript_text",
        "roster_snapshot",
        "transcript_polish_error",
        "transcript_polished_at",
    }

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

    def assertPrivateTranscriptPolishFieldsHidden(self, payload: dict):
        for field_name in self.PRIVATE_TRANSCRIPT_POLISH_FIELDS:
            self.assertNotIn(field_name, payload)

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
        self.assertEqual(payload["tasks"][0]["transcript_text"], "")
        self.assertPrivateTranscriptPolishFieldsHidden(payload["tasks"][0])

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
        self.assertIn("自己的较旧记录", str(payload))

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
            }
        )
        class_id = self._create_class_with_student()
        (self.skill_dir / "teacher-a.skill").write_text("warm direct style", encoding="utf-8")
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")
        charged = []

        with patch.object(self.app_module, "has_class_commentary_api_key", return_value=True), \
             patch.object(
                 self.app_module,
                 "_run_ai_feature_with_charge",
                 side_effect=lambda **kwargs: charged.append(kwargs) or "小王:\n今天计算有进步.",
             ):
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
        self.assertEqual(charged[0]["provider"], "openai")
        self.assertEqual(charged[0]["model"], "gpt-5.5")
        stored = lesson_manager.get_class_commentary_task(task["id"])
        self.assertEqual(stored["chat_provider"], "openai")
        self.assertEqual(stored["chat_model"], "gpt-5.5")

    def test_generate_failure_returns_500_with_failed_task_payload(self):
        class_id = self._create_class_with_student()
        (self.skill_dir / "teacher-a.skill").write_text("warm direct style", encoding="utf-8")
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")

        with patch.object(self.app_module, "has_class_commentary_api_key", return_value=True), \
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
