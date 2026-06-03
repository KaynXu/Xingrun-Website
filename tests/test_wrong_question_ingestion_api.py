from __future__ import annotations

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
from app import app


class WrongQuestionIngestionApiTestCase(unittest.TestCase):
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
            "六年级 2 班",
            subject="数学",
            grade="六年级",
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
            "other_ingestion_owner",
            "另一位负责人",
            "owner-pass",
            recovery_phone="13800000011",
        )
        super_owner = lesson_manager.get_user_by_username("Kayn")
        lesson_manager.approve_organization_request(request_row["id"], super_owner["id"])
        login = self.client.post(
            "/api/login",
            json={"username": "other_ingestion_owner", "password": "owner-pass"},
        )
        self.assertEqual(login.status_code, 200)
        return self.auth_headers(login.get_json()["token"])

    def test_create_ingestion_run_persists_assets_and_context(self):
        response = self.client.post(
            "/api/wrong-question-ingestions",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "source": "ai_chat",
                "class_id": self.class_id,
                "student_id": self.student["id"],
                "chat_session_id": "chat-session-101",
                "original_filename": "wrong-question.pdf",
                "mime_type": "application/pdf",
                "metadata": {"page_count": 2, "entrypoint": "chat"},
                "assets": [
                    {
                        "asset_role": "original_upload",
                        "storage_path": "/tmp/wrong-question.pdf",
                        "mime_type": "application/pdf",
                        "metadata": {"page_count": 2},
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        run = payload["run"]
        self.assertEqual(run["source"], "ai_chat")
        self.assertEqual(run["class_id"], self.class_id)
        self.assertEqual(run["student_id"], self.student["id"])
        self.assertEqual(run["teacher_user_id"], self.owner_id)
        self.assertEqual(run["chat_session_id"], "chat-session-101")
        self.assertEqual(run["current_step"], "uploaded")
        self.assertEqual(json.loads(run["metadata_json"]), {"page_count": 2, "entrypoint": "chat"})
        self.assertEqual(len(run["assets"]), 1)
        self.assertEqual(run["assets"][0]["asset_role"], "original_upload")
        self.assertEqual(run["assets"][0]["storage_path"], "/tmp/wrong-question.pdf")
        self.assertEqual(run["records"], [])

    def test_list_ingestion_runs_filters_and_enforces_scope(self):
        workspace_run = self.client.post(
            "/api/wrong-question-ingestions",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "source": "workspace",
                "class_id": self.class_id,
                "student_id": self.student["id"],
                "original_filename": "workspace.png",
                "mime_type": "image/png",
            },
        ).get_json()["run"]
        ai_chat_run = self.client.post(
            "/api/wrong-question-ingestions",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "source": "ai_chat",
                "class_id": self.class_id,
                "student_id": self.student["id"],
                "chat_session_id": "chat-session-list",
                "original_filename": "chat.png",
                "mime_type": "image/png",
            },
        ).get_json()["run"]
        self.client.post(
            f"/api/wrong-question-ingestions/{ai_chat_run['id']}/ocr",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={"metadata": {"ocr_engine": "mock"}},
        )

        visible = self.client.get(
            f"/api/wrong-question-ingestions?source=ai_chat&status=ocr_ready&chat_session_id=chat-session-list&class_id={self.class_id}",
            headers=self.auth_headers(self.owner_payload["token"]),
        )
        hidden = self.client.get(
            f"/api/wrong-question-ingestions?class_id={self.class_id}",
            headers=self._create_other_owner_headers(),
        )

        self.assertEqual(visible.status_code, 200)
        items = visible.get_json()["items"]
        self.assertEqual([item["id"] for item in items], [ai_chat_run["id"]])
        self.assertEqual(items[0]["current_step"], "ocr_completed")
        self.assertEqual(hidden.status_code, 403)
        self.assertEqual(workspace_run["current_step"], "uploaded")

    def test_get_ingestion_run_enforces_organization_scope(self):
        created = self.client.post(
            "/api/wrong-question-ingestions",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "source": "workspace",
                "class_id": self.class_id,
                "student_id": self.student["id"],
                "original_filename": "workspace.png",
                "mime_type": "image/png",
            },
        ).get_json()["run"]

        visible = self.client.get(
            f"/api/wrong-question-ingestions/{created['id']}",
            headers=self.auth_headers(self.owner_payload["token"]),
        )
        hidden = self.client.get(
            f"/api/wrong-question-ingestions/{created['id']}",
            headers=self._create_other_owner_headers(),
        )

        self.assertEqual(visible.status_code, 200)
        self.assertEqual(visible.get_json()["run"]["id"], created["id"])
        self.assertEqual(hidden.status_code, 404)

    def test_ocr_and_split_endpoints_update_status_and_append_assets(self):
        run = self.client.post(
            "/api/wrong-question-ingestions",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "source": "workspace",
                "class_id": self.class_id,
                "student_id": self.student["id"],
                "original_filename": "scan.pdf",
                "mime_type": "application/pdf",
            },
        ).get_json()["run"]

        ocr = self.client.post(
            f"/api/wrong-question-ingestions/{run['id']}/ocr",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "metadata": {"ocr_engine": "mock", "pages": 2},
                "assets": [
                    {
                        "asset_role": "ocr_page_image",
                        "storage_path": "/tmp/ocr-page-1.png",
                        "mime_type": "image/png",
                        "page_number": 1,
                        "metadata": {"page_index": 0},
                    }
                ],
            },
        )
        split = self.client.post(
            f"/api/wrong-question-ingestions/{run['id']}/split",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "metadata": {"split_groups": 1},
                "assets": [
                    {
                        "asset_role": "split_preview",
                        "storage_path": "/tmp/split-preview-1.png",
                        "mime_type": "image/png",
                        "page_number": 1,
                    }
                ],
            },
        )

        self.assertEqual(ocr.status_code, 200)
        self.assertEqual(ocr.get_json()["run"]["status"], "ocr_ready")
        self.assertEqual(ocr.get_json()["run"]["current_step"], "ocr_completed")
        self.assertEqual(split.status_code, 200)
        split_run = split.get_json()["run"]
        self.assertEqual(split_run["status"], "split_ready")
        self.assertEqual(split_run["current_step"], "split_completed")
        self.assertEqual([item["asset_role"] for item in split_run["assets"]], ["ocr_page_image", "split_preview"])
        self.assertEqual(json.loads(split_run["metadata_json"]), {"split_groups": 1})

    def test_archive_endpoint_creates_ai_chat_records_and_marks_run_archived(self):
        run = self.client.post(
            "/api/wrong-question-ingestions",
            headers=self.auth_headers(self.owner_payload["token"]),
            json={
                "source": "ai_chat",
                "class_id": self.class_id,
                "student_id": self.student["id"],
                "chat_session_id": "chat-session-archive",
                "original_filename": "wrong-question.png",
                "mime_type": "image/png",
            },
        ).get_json()["run"]

        with patch("app._rebuild_student_wrong_question_library", return_value="/tmp/student-archive.pdf") as rebuild_mock:
            response = self.client.post(
                f"/api/wrong-question-ingestions/{run['id']}/archive",
                headers=self.auth_headers(self.owner_payload["token"]),
                json={
                    "metadata": {"archived_from": "chat"},
                    "submissions": [
                        {
                            "source": "ai_chat",
                            "image_url": "https://files.example.com/archive-1.png",
                            "question_text": "解方程 $2x+5=17$。",
                            "recognition_status": "recognized",
                            "topic_category": "一元一次方程",
                            "question_structured_json": {"stem": "解方程 2x+5=17"},
                            "knowledge_tags_json": ["一元一次方程", "移项"],
                            "child_raw_reason_text": "我不知道为什么要先减 5",
                            "needs_teacher_confirmation": True,
                            "confirmation_reasons_json": ["student_confused_step"],
                        }
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["run"]["status"], "archived")
        self.assertEqual(payload["run"]["current_step"], "archived")
        self.assertEqual(json.loads(payload["run"]["metadata_json"]), {"archived_from": "chat"})
        self.assertEqual(len(payload["created_records"]), 1)
        record = payload["created_records"][0]
        self.assertEqual(record["source"], "ai_chat")
        self.assertEqual(record["ingestion_run_id"], run["id"])
        self.assertEqual(record["chat_session_id"], "chat-session-archive")
        self.assertEqual(record["recognition_status"], "recognized")
        self.assertEqual(record["student_library_pdf_path"], "/tmp/student-archive.pdf")
        rebuild_mock.assert_called_once_with(self.student["id"])

        library_records = lesson_manager.list_student_wrong_question_library_records(self.student["id"])
        self.assertEqual([item["id"] for item in library_records], [record["id"]])
        self.assertEqual(library_records[0]["source"], "ai_chat")
        self.assertEqual(library_records[0]["student_library_pdf_path"], "/tmp/student-archive.pdf")
        self.assertEqual(
            json.loads(library_records[0]["knowledge_tags_json"]),
            ["一元一次方程", "移项"],
        )


if __name__ == "__main__":
    unittest.main()
