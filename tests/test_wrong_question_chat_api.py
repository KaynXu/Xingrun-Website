from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager
from app import app


class WrongQuestionChatApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app.test_client()

        self.owner_payload = self.login_owner()
        self.owner_id = self.owner_payload["user"]["id"]
        self.organization_id = self.owner_payload["user"]["organization_id"]
        self.class_id = lesson_manager.save_class(
            "七年级 3 班",
            subject="数学",
            grade="七年级",
            organization_id=self.organization_id,
        )
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner_id)
        self.student = lesson_manager.create_student_for_class(self.class_id, "Alice")

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def login_owner(self) -> dict:
        response = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        return payload

    def _create_ai_chat_run(self, *, chat_session_id: str, file_url: str = "", storage_path: str = "") -> dict:
        response = self.client.post(
            "/api/wrong-question-ingestions",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "source": "ai_chat",
                "class_id": self.class_id,
                "student_id": self.student["id"],
                "chat_session_id": chat_session_id,
                "original_filename": "wrong-question.png",
                "mime_type": "image/png",
                "assets": [
                    {
                        "asset_role": "original_upload",
                        "file_url": file_url,
                        "storage_path": storage_path,
                        "mime_type": "image/png",
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()["run"]

    def test_stream_guides_reflection_then_archives_into_library(self):
        run = self._create_ai_chat_run(
            chat_session_id="chat-session-guided",
            file_url="https://files.example.com/chat-guided.png",
        )

        opening = self.client.post(
            "/api/wrong-question-chats/chat-session-guided/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "ingestion_run_id": run["id"],
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(opening.status_code, 200)
        self.assertEqual(opening.get_json()["assistant_message"]["stage"], "ask_why_wrong")

        turn_one = self.client.post(
            "/api/wrong-question-chats/chat-session-guided/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我不知道为什么要先减 5"},
        )
        self.assertEqual(turn_one.status_code, 200)
        self.assertEqual(turn_one.get_json()["assistant_message"]["stage"], "ask_unknown_step")

        turn_two = self.client.post(
            "/api/wrong-question-chats/chat-session-guided/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我卡在移项这一步，不知道符号为什么会变"},
        )
        self.assertEqual(turn_two.status_code, 200)
        self.assertEqual(turn_two.get_json()["assistant_message"]["stage"], "ask_help_mode")

        turn_three = self.client.post(
            "/api/wrong-question-chats/chat-session-guided/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "message": "先给我一点提示，再带我完整复盘",
                "archive_payload": {
                    "question_text": "解方程 2x+5=17。",
                    "topic_category": "一元一次方程",
                    "question_structured_json": {"stem": "解方程 2x+5=17"},
                    "knowledge_tags_json": ["一元一次方程", "移项"],
                },
            },
        )

        self.assertEqual(turn_three.status_code, 200)
        payload = turn_three.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["archive"]["created"])
        self.assertEqual(payload["assistant_message"]["stage"], "ready_to_archive")
        self.assertEqual(payload["session"]["status"], "archived")
        self.assertEqual(payload["session"]["current_stage"], "ready_to_archive")
        self.assertEqual(len(payload["session"]["messages"]), 7)
        self.assertEqual(len(payload["session"]["records"]), 1)

        record = payload["archive"]["record"]
        self.assertEqual(record["source"], "ai_chat")
        self.assertEqual(record["ingestion_run_id"], run["id"])
        self.assertEqual(record["chat_session_id"], "chat-session-guided")
        self.assertEqual(record["child_raw_reason_text"], "我不知道为什么要先减 5")
        self.assertEqual(record["child_reason_core_issue"], "我卡在移项这一步，不知道符号为什么会变")
        self.assertEqual(record["child_reason_next_step"], "先给我一点提示，再带我完整复盘")
        self.assertEqual(record["question_text"], "解方程 2x+5=17。")
        self.assertEqual(json.loads(record["knowledge_tags_json"]), ["一元一次方程", "移项"])
        self.assertEqual(record["needs_teacher_confirmation"], 0)

        saved_session = lesson_manager.get_wrong_question_chat_session("chat-session-guided")
        self.assertIsNotNone(saved_session)
        self.assertEqual(saved_session["status"], "archived")
        self.assertIn("错因自述", saved_session["summary_text"])
        saved_run = lesson_manager.get_wrong_question_ingestion_run(run["id"])
        self.assertEqual(saved_run["status"], "archived")
        self.assertEqual(saved_run["chat_session_id"], "chat-session-guided")

        library_records = lesson_manager.list_student_wrong_question_library_records(self.student["id"])
        self.assertEqual([item["id"] for item in library_records], [record["id"]])

    def test_stream_marks_teacher_confirmation_when_archive_context_is_incomplete(self):
        run = self._create_ai_chat_run(
            chat_session_id="chat-session-needs-review",
            storage_path="/tmp/chat-needs-review.png",
        )

        turn_one = self.client.post(
            "/api/wrong-question-chats/chat-session-needs-review/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "ingestion_run_id": run["id"],
                "class_id": self.class_id,
                "student_id": self.student["id"],
                "message": "我就是不知道为什么错了",
            },
        )
        self.assertEqual(turn_one.status_code, 200)
        self.assertEqual(turn_one.get_json()["assistant_message"]["stage"], "ask_unknown_step")

        turn_two = self.client.post(
            "/api/wrong-question-chats/chat-session-needs-review/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我感觉是列式这里没跟上"},
        )
        self.assertEqual(turn_two.status_code, 200)
        self.assertEqual(turn_two.get_json()["assistant_message"]["stage"], "ask_help_mode")

        turn_three = self.client.post(
            "/api/wrong-question-chats/chat-session-needs-review/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "message": "先给提示",
                "archive_payload": {
                    "knowledge_tags_json": [],
                },
            },
        )

        self.assertEqual(turn_three.status_code, 200)
        payload = turn_three.get_json()
        record = payload["archive"]["record"]
        self.assertEqual(record["image_url"], "/tmp/chat-needs-review.png")
        self.assertEqual(record["needs_teacher_confirmation"], 1)
        self.assertEqual(
            json.loads(record["confirmation_reasons_json"]),
            ["missing_question_text", "knowledge_tags_unconfirmed"],
        )
        self.assertEqual(payload["session"]["status"], "archived")


if __name__ == "__main__":
    unittest.main()
