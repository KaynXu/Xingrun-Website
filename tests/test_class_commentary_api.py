import io
import importlib
import json
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
        self.assertEqual(member_skills, owner_skills)
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
        self.assertIn("Assessment workflow", filesystem_skill["content"])
        self.assertIn("Colleague persona", filesystem_skill["content"])
        self.assertNotIn("Changed after registry import", filesystem_skill["content"])

    def test_member_can_generate_with_colleague_skill_imported_by_another_user(self):
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

        with patch.object(self.app_module, "has_class_commentary_api_key", return_value=True), \
             patch.object(self.app_module, "_run_ai_feature_with_charge", side_effect=fake_charge), \
             patch.object(
                 self.app_module,
                 "generate_class_commentary_feedback",
                 return_value=("小王: 今天计算更稳定.", {"input_tokens": 3, "output_tokens": 2}),
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

    def test_generate_requires_request_id_and_is_idempotent_from_registry_snapshot(self):
        class_id = self._create_class_with_student()
        second_student = lesson_manager.create_student_for_class(class_id, "小李")
        students = lesson_manager.list_students_for_class(class_id)
        task = self._create_transcribed_task(class_id, "小王和小李今天计算有进步")
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
        charge_calls = []

        def fake_charge(**kwargs):
            charge_calls.append(kwargs)
            result = kwargs["producer"]()
            return result[0] if isinstance(result, tuple) else result

        with patch.object(self.app_module, "has_class_commentary_api_key", return_value=True), \
             patch.object(self.app_module, "_run_ai_feature_with_charge", side_effect=fake_charge), \
             patch.object(
                 self.app_module,
                 "generate_class_commentary_feedback",
                 return_value=("数据库快照生成结果", {"input_tokens": 3, "output_tokens": 2}),
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
        self.assertEqual(len(charge_calls), 1)
        generate.assert_called_once()
        self.assertEqual(generate.call_args.kwargs["skill"]["content"], registry_content)
        saved = lesson_manager.get_class_commentary_generation(first_payload["generation_id"])
        self.assertEqual(saved["skill_registry_id"], skill["registry_id"])
        self.assertEqual(saved["skill_content_snapshot"], registry_content)

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
        chat_request = self.app_module.build_class_commentary_chat_request(
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

    def test_generate_builds_and_persists_prompt_from_reserved_transcript_snapshot(self):
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

        with patch.object(
            self.app_module,
            "reserve_class_commentary_generation",
            side_effect=reserve_after_transcript_edit,
        ), patch.object(
            self.app_module,
            "has_class_commentary_api_key",
            return_value=True,
        ), patch.object(
            self.app_module,
            "_run_ai_feature_with_charge",
            side_effect=fake_charge,
        ), patch.object(
            self.app_module,
            "generate_class_commentary_feedback",
            return_value=("基于冻结转写的反馈", {"input_tokens": 3, "output_tokens": 2}),
        ) as generate:
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={
                    "request_id": "generation-reserved-prompt",
                    "skill_id": "reserved-prompt-style",
                },
            )

        self.assertEqual(response.status_code, 200)
        generation_id = response.get_json()["generation_id"]
        saved = lesson_manager.get_class_commentary_generation(generation_id)
        actual_chat_request = generate.call_args.kwargs["chat_request"]
        self.assertEqual(generate.call_args.kwargs["transcript_text"], reserved_transcript)
        self.assertIn(reserved_transcript, actual_chat_request["messages"][1]["content"])
        self.assertNotIn(original_transcript + "\"", actual_chat_request["messages"][1]["content"])
        self.assertEqual(saved["confirmed_transcript_snapshot"], reserved_transcript)
        self.assertEqual(saved["execution_snapshot_status"], "ready")
        self.assertEqual(
            json.loads(saved["prompt_payload_snapshot_json"]),
            actual_chat_request,
        )

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
            }
        )
        class_id = self._create_class_with_student()
        self._register_skill("teacher-a", "warm direct style")
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
                json={"request_id": "generation-provider-config", "skill_id": "teacher-a"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertIsInstance(payload["generation_id"], int)
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["task_status"], "ready")
        self.assertEqual(payload["generation_status"], "succeeded")
        self.assertEqual(payload["skill_id"], "teacher-a")
        self.assertEqual(payload["feedback_text"], "小王:\n今天计算有进步.")
        self.assertEqual(
            payload["generation"]["generated_feedback_text"],
            "小王:\n今天计算有进步.",
        )
        self.assertEqual(charged[0]["provider"], "openai")
        self.assertEqual(charged[0]["model"], "gpt-5.5")
        stored = lesson_manager.get_class_commentary_task(task["id"])
        self.assertEqual(stored["status"], "ready")
        self.assertEqual(stored["feedback_text"], "小王:\n今天计算有进步.")
        self.assertEqual(stored["chat_provider"], "openai")
        self.assertEqual(stored["chat_model"], "gpt-5.5")

    def test_generate_filters_students_to_attending_roster(self):
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
        task = self._create_transcribed_task(class_id, "小王和小张今天计算有进步")

        def fake_charge(**kwargs):
            result = kwargs["producer"]()
            return result[0] if isinstance(result, tuple) else result

        with patch.object(self.app_module, "has_class_commentary_api_key", return_value=True), \
             patch.object(self.app_module, "_run_ai_feature_with_charge", side_effect=fake_charge), \
             patch.object(self.app_module, "generate_class_commentary_feedback", return_value=("到课反馈", {"input_tokens": 3, "output_tokens": 2})) as generate:
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

    def test_generate_failure_returns_500_with_failed_task_payload(self):
        class_id = self._create_class_with_student()
        self._register_skill("teacher-a", "warm direct style")
        task = self._create_transcribed_task(class_id, "小王今天计算有进步")

        with patch.object(self.app_module, "has_class_commentary_api_key", return_value=True), \
             patch.object(self.app_module, "_run_ai_feature_with_charge", side_effect=RuntimeError("model timeout")):
            response = self.client.post(
                f"/api/class-commentary/tasks/{task['id']}/generate",
                headers=self.headers,
                json={"request_id": "generation-model-timeout", "skill_id": "teacher-a"},
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
