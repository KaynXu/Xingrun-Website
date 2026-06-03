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

    def _create_other_owner_headers(self) -> dict[str, str]:
        request_row = lesson_manager.create_organization_request(
            "另一个错题机构",
            "other_chat_owner",
            "另一位负责人",
            "owner-pass",
            recovery_phone="13800000012",
        )
        super_owner = lesson_manager.get_user_by_username("Kayn")
        lesson_manager.approve_organization_request(request_row["id"], super_owner["id"])
        login = self.client.post(
            "/api/login",
            json={"username": "other_chat_owner", "password": "owner-pass"},
        )
        self.assertEqual(login.status_code, 200)
        return self.auth_headers(login.get_json()["token"])

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
        self.assertFalse(payload["archive"]["idempotent_reuse"])
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
        self.assertEqual(record["generation_metadata"]["schema_version"], "wrong_question_archive_schema.v1")
        self.assertEqual(record["generation_metadata"]["prompt_version"], "wrong_question_chat_prompt.2026-06-03")
        self.assertEqual(record["generation_metadata"]["model_version"], "local-guided-loop")

        saved_session = lesson_manager.get_wrong_question_chat_session("chat-session-guided")
        self.assertIsNotNone(saved_session)
        self.assertEqual(saved_session["status"], "archived")
        self.assertIn("错因自述", saved_session["summary_text"])
        saved_run = lesson_manager.get_wrong_question_ingestion_run(run["id"])
        self.assertEqual(saved_run["status"], "archived")
        self.assertEqual(saved_run["chat_session_id"], "chat-session-guided")

        library_records = lesson_manager.list_student_wrong_question_library_records(self.student["id"])
        self.assertEqual([item["id"] for item in library_records], [record["id"]])

        retried = self.client.post(
            "/api/wrong-question-chats/chat-session-guided/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我再点一次提交，应该复用已有归档"},
        )
        self.assertEqual(retried.status_code, 200)
        retried_payload = retried.get_json()
        self.assertFalse(retried_payload["archive"]["created"])
        self.assertTrue(retried_payload["archive"]["idempotent_reuse"])
        self.assertEqual(retried_payload["assistant_message"], None)
        self.assertEqual(retried_payload["archive"]["record"]["id"], record["id"])
        self.assertEqual(len(retried_payload["session"]["messages"]), 7)
        self.assertEqual(
            len(lesson_manager.list_wrong_question_submissions_for_chat_session("chat-session-guided")),
            1,
        )

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
        self.assertEqual(record["generation_metadata"]["archive_source"], "ai_chat")
        self.assertEqual(payload["session"]["status"], "archived")

    def test_chat_detail_returns_messages_records_and_enforces_scope(self):
        run = self._create_ai_chat_run(
            chat_session_id="chat-session-detail",
            file_url="https://files.example.com/chat-detail.png",
        )

        opening = self.client.post(
            "/api/wrong-question-chats/chat-session-detail/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "ingestion_run_id": run["id"],
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(opening.status_code, 200)

        reflected = self.client.post(
            "/api/wrong-question-chats/chat-session-detail/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我没想清楚为什么要先化简"},
        )
        self.assertEqual(reflected.status_code, 200)

        visible = self.client.get(
            "/api/wrong-question-chats/chat-session-detail",
            headers=self.auth_headers(self.owner_payload["token"]),
        )
        hidden = self.client.get(
            "/api/wrong-question-chats/chat-session-detail",
            headers=self._create_other_owner_headers(),
        )

        self.assertEqual(visible.status_code, 200)
        payload = visible.get_json()
        self.assertEqual(payload["session"]["id"], "chat-session-detail")
        self.assertEqual(payload["session"]["ingestion_run_id"], run["id"])
        self.assertEqual(payload["session"]["current_stage"], "ask_unknown_step")
        self.assertEqual(payload["session"]["detail_url"], "/api/wrong-question-chats/chat-session-detail")
        self.assertEqual(payload["session"]["stream_url"], "/api/wrong-question-chats/chat-session-detail/stream")
        self.assertEqual(len(payload["session"]["messages"]), 3)
        self.assertEqual(payload["session"]["messages"][0]["role"], "assistant")
        self.assertEqual(payload["session"]["messages"][1]["role"], "user")
        self.assertEqual(payload["session"]["records"], [])
        self.assertEqual(
            lesson_manager.get_wrong_question_ingestion_run(run["id"])["current_step"],
            "chat_reflection",
        )
        self.assertEqual(hidden.status_code, 404)

    def test_chat_detail_records_include_archive_navigation_context(self):
        run = self._create_ai_chat_run(
            chat_session_id="chat-session-linked-record",
            file_url="https://files.example.com/chat-linked-record.png",
        )

        self.client.post(
            "/api/wrong-question-chats/chat-session-linked-record/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "ingestion_run_id": run["id"],
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.client.post(
            "/api/wrong-question-chats/chat-session-linked-record/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我不知道为什么要先减 5"},
        )
        self.client.post(
            "/api/wrong-question-chats/chat-session-linked-record/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我卡在移项为什么变号"},
        )
        archived = self.client.post(
            "/api/wrong-question-chats/chat-session-linked-record/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "message": "先给提示",
                "archive_payload": {
                    "question_text": "解方程 2x+5=17。",
                    "knowledge_tags_json": ["一元一次方程"],
                },
            },
        )
        self.assertEqual(archived.status_code, 200)

        detail = self.client.get(
            "/api/wrong-question-chats/chat-session-linked-record",
            headers=self.auth_headers(self.owner_payload["token"]),
        )
        self.assertEqual(detail.status_code, 200)
        record = detail.get_json()["session"]["records"][0]
        self.assertEqual(record["archive_context"]["ingestion_run_id"], run["id"])
        self.assertEqual(record["archive_context"]["ingestion_run_url"], f"/api/wrong-question-ingestions/{run['id']}")
        self.assertEqual(record["archive_context"]["chat_session_id"], "chat-session-linked-record")
        self.assertEqual(
            record["archive_context"]["chat_session_url"],
            "/api/wrong-question-chats/chat-session-linked-record",
        )

    def test_returned_record_can_reopen_chat_and_update_same_archive_record(self):
        run = self._create_ai_chat_run(
            chat_session_id="chat-session-rework-origin",
            file_url="https://files.example.com/chat-rework-origin.png",
        )

        self.client.post(
            "/api/wrong-question-chats/chat-session-rework-origin/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "ingestion_run_id": run["id"],
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.client.post(
            "/api/wrong-question-chats/chat-session-rework-origin/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我只知道自己算错了，但还说不清楚哪里错"},
        )
        self.client.post(
            "/api/wrong-question-chats/chat-session-rework-origin/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我还没想明白到底是哪一步开始卡住"},
        )
        archived = self.client.post(
            "/api/wrong-question-chats/chat-session-rework-origin/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "message": "先给我一点提示",
                "archive_payload": {
                    "question_text": "",
                    "knowledge_tags_json": [],
                },
            },
        )
        self.assertEqual(archived.status_code, 200)
        original_record = archived.get_json()["archive"]["record"]
        self.assertEqual(original_record["needs_teacher_confirmation"], 1)

        returned = self.client.put(
            f"/api/wrong-questions/{original_record['id']}/review",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "needs_teacher_confirmation": True,
                "confirmation_reasons_json": ["knowledge_tags_unconfirmed", "student_confused_step"],
                "confirmation_action": "return_for_rework",
            },
        )
        self.assertEqual(returned.status_code, 200)
        self.assertEqual(returned.get_json()["record"]["confirmation_status"], "returned")

        reopened = self.client.post(
            f"/api/wrong-questions/{original_record['id']}/reopen-chat",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={},
        )
        self.assertEqual(reopened.status_code, 200)
        reopened_payload = reopened.get_json()
        self.assertTrue(reopened_payload["created"])
        self.assertFalse(reopened_payload["reused_active_session"])
        reopened_session = reopened_payload["session"]
        reopened_session_id = reopened_session["id"]
        self.assertNotEqual(reopened_session_id, "chat-session-rework-origin")
        self.assertEqual(reopened_session["status"], "active")
        self.assertEqual(reopened_session["current_stage"], "ask_why_wrong")
        self.assertEqual(len(reopened_session["messages"]), 1)
        self.assertIn("老师刚把这道题退回补充", reopened_session["messages"][0]["content"])
        self.assertEqual(reopened_payload["run"]["chat_session_id"], reopened_session_id)
        self.assertEqual(reopened_payload["run"]["current_step"], "chat_reflection")

        reopened_again = self.client.post(
            f"/api/wrong-questions/{original_record['id']}/reopen-chat",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={},
        )
        self.assertEqual(reopened_again.status_code, 200)
        self.assertFalse(reopened_again.get_json()["created"])
        self.assertTrue(reopened_again.get_json()["reused_active_session"])
        self.assertEqual(reopened_again.get_json()["session"]["id"], reopened_session_id)

        self.client.post(
            f"/api/wrong-question-chats/{reopened_session_id}/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "这次我知道是自己没先看清移项为什么变号"},
        )
        self.client.post(
            f"/api/wrong-question-chats/{reopened_session_id}/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我卡在移项时符号变化和等式两边同时处理"},
        )
        finalized = self.client.post(
            f"/api/wrong-question-chats/{reopened_session_id}/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "message": "先给提示，再让我自己试一次",
                "archive_payload": {
                    "question_text": "解方程 2x+5=17。",
                    "topic_category": "一元一次方程",
                    "knowledge_tags_json": ["一元一次方程", "移项"],
                },
            },
        )
        self.assertEqual(finalized.status_code, 200)
        finalized_payload = finalized.get_json()
        self.assertTrue(finalized_payload["archive"]["created"])
        self.assertTrue(finalized_payload["archive"]["updated_existing_record"])
        final_record = finalized_payload["archive"]["record"]
        self.assertEqual(final_record["id"], original_record["id"])
        self.assertEqual(final_record["chat_session_id"], reopened_session_id)
        self.assertEqual(final_record["question_text"], "解方程 2x+5=17。")
        self.assertEqual(json.loads(final_record["knowledge_tags_json"]), ["一元一次方程", "移项"])
        self.assertEqual(final_record["needs_teacher_confirmation"], 0)
        self.assertEqual(final_record["confirmation_status"], "not_required")
        self.assertEqual(
            len(lesson_manager.list_student_wrong_question_library_records(self.student["id"])),
            1,
        )

        retried_old_session = self.client.post(
            "/api/wrong-question-chats/chat-session-rework-origin/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我误点了旧会话"},
        )
        self.assertEqual(retried_old_session.status_code, 200)
        self.assertTrue(retried_old_session.get_json()["archive"]["idempotent_reuse"])
        self.assertEqual(retried_old_session.get_json()["archive"]["record"]["id"], original_record["id"])

    def test_confirmed_record_can_open_mastery_followup_chat_and_update_same_archive_record(self):
        run = self._create_ai_chat_run(
            chat_session_id="chat-session-followup-origin",
            file_url="https://files.example.com/chat-followup-origin.png",
        )

        self.client.post(
            "/api/wrong-question-chats/chat-session-followup-origin/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "ingestion_run_id": run["id"],
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.client.post(
            "/api/wrong-question-chats/chat-session-followup-origin/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我当时不知道为什么要先减 5"},
        )
        self.client.post(
            "/api/wrong-question-chats/chat-session-followup-origin/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我卡在移项时不知道为什么符号会变"},
        )
        archived = self.client.post(
            "/api/wrong-question-chats/chat-session-followup-origin/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "message": "先给提示，再让我自己复盘",
                "archive_payload": {
                    "question_text": "解方程 2x+5=17。",
                    "topic_category": "一元一次方程",
                    "knowledge_tags_json": ["一元一次方程", "移项"],
                },
            },
        )
        self.assertEqual(archived.status_code, 200)
        original_record = archived.get_json()["archive"]["record"]
        self.assertEqual(original_record["confirmation_status"], "not_required")

        practice_sheet = lesson_manager.create_pending_wrong_question_practice_sheet(
            created_by=self.owner_id,
            selected_records=[lesson_manager.get_wechat_wrong_question_submission(original_record["id"])],
        )
        lesson_manager.mark_wrong_question_practice_sheet_succeeded(
            practice_sheet["id"],
            generated_items=[
                {
                    "wrong_question_record_id": original_record["id"],
                    "ai_hint": "先看等式两边。",
                    "reason_blank_prompt": "这题我错在 ______。",
                    "improvement_summary_prompt": "下次先 ______。",
                },
            ],
            pdf_path="/tmp/followup-mastery.pdf",
        )

        followup = self.client.post(
            f"/api/wrong-questions/{original_record['id']}/followup-chat",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={},
        )
        self.assertEqual(followup.status_code, 200)
        followup_payload = followup.get_json()
        self.assertTrue(followup_payload["created"])
        self.assertFalse(followup_payload["reused_active_session"])
        followup_session = followup_payload["session"]
        followup_session_id = followup_session["id"]
        self.assertEqual(followup_session["status"], "active")
        self.assertEqual(followup_session["current_stage"], "ask_why_wrong")
        self.assertEqual(len(followup_session["messages"]), 1)
        self.assertIn("最近已经完成了 1 次再练", followup_session["messages"][0]["content"])
        self.assertEqual(followup_payload["run"]["chat_session_id"], followup_session_id)

        followup_again = self.client.post(
            f"/api/wrong-questions/{original_record['id']}/followup-chat",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={},
        )
        self.assertEqual(followup_again.status_code, 200)
        self.assertFalse(followup_again.get_json()["created"])
        self.assertTrue(followup_again.get_json()["reused_active_session"])
        self.assertEqual(followup_again.get_json()["session"]["id"], followup_session_id)

        self.client.post(
            f"/api/wrong-question-chats/{followup_session_id}/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我现在最稳的是先看等式两边，最不稳的是移项后符号变化"},
        )
        self.client.post(
            f"/api/wrong-question-chats/{followup_session_id}/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"message": "我还是会在变号时迟疑，不确定什么时候需要同步处理另一边"},
        )
        finalized = self.client.post(
            f"/api/wrong-question-chats/{followup_session_id}/stream",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "message": "先给我一点提示，我再试一次",
                "archive_payload": {
                    "knowledge_tags_json": ["一元一次方程", "移项", "等式性质"],
                },
            },
        )
        self.assertEqual(finalized.status_code, 200)
        finalized_payload = finalized.get_json()
        self.assertTrue(finalized_payload["archive"]["created"])
        self.assertTrue(finalized_payload["archive"]["updated_existing_record"])
        final_record = finalized_payload["archive"]["record"]
        self.assertEqual(final_record["id"], original_record["id"])
        self.assertEqual(final_record["chat_session_id"], followup_session_id)
        self.assertEqual(final_record["question_text"], "解方程 2x+5=17。")
        self.assertEqual(json.loads(final_record["knowledge_tags_json"]), ["一元一次方程", "移项", "等式性质"])
        self.assertEqual(final_record["confirmation_status"], "not_required")
        self.assertEqual(final_record["generation_metadata"]["entrypoint"], "wrong_question_chat_mastery_followup")
        self.assertEqual(
            len(lesson_manager.list_student_wrong_question_library_records(self.student["id"])),
            1,
        )


if __name__ == "__main__":
    unittest.main()
