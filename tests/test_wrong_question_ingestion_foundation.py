from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lesson_manager


class WrongQuestionIngestionFoundationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        lesson_manager.DB_PATH = Path(self.temp_dir.name) / "xingrun.db"
        lesson_manager.init_db()
        self.owner = lesson_manager.get_user_by_username("Kayn")
        self.organization_id = self.owner["organization_id"]
        self.class_id = lesson_manager.save_class(
            "六年级 8 班",
            subject="数学",
            grade="六年级",
            organization_id=self.organization_id,
        )
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner["id"])
        self.student = lesson_manager.create_student_for_class(self.class_id, "Alice")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_db_rebuilds_wrong_question_submissions_for_multisource_support(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-migration-parent")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )

        with lesson_manager.get_conn() as conn:
            conn.execute("DROP TABLE wrong_question_submissions")
            conn.execute(
                """
                CREATE TABLE wrong_question_submissions (
                    id                        TEXT PRIMARY KEY,
                    organization_id           INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                    source                    TEXT NOT NULL DEFAULT 'wechat_mp',
                    parent_wechat_account_id  INTEGER NOT NULL REFERENCES parent_wechat_accounts(id) ON DELETE CASCADE,
                    binding_id                INTEGER NOT NULL REFERENCES parent_student_bindings(id) ON DELETE CASCADE,
                    class_id                  INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                    student_id                INTEGER NOT NULL REFERENCES students(id),
                    teacher_user_id           INTEGER NOT NULL REFERENCES users(id),
                    image_url                 TEXT NOT NULL,
                    status                    TEXT NOT NULL DEFAULT 'pending',
                    created_at                TEXT DEFAULT (datetime('now','localtime')),
                    updated_at                TEXT DEFAULT (datetime('now','localtime'))
                )
                """
            )
            conn.execute(
                """
                INSERT INTO wrong_question_submissions (
                    id, organization_id, source, parent_wechat_account_id, binding_id,
                    class_id, student_id, teacher_user_id, image_url, status
                ) VALUES (?, ?, 'wechat_mp', ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    "legacy-multisource-record",
                    self.organization_id,
                    account["id"],
                    binding["id"],
                    self.class_id,
                    self.student["id"],
                    self.owner["id"],
                    "https://files.example.com/legacy.png",
                ),
            )

        lesson_manager.init_db()

        with lesson_manager.get_conn() as conn:
            columns = {
                row["name"]: {"notnull": row["notnull"], "default": row["dflt_value"]}
                for row in conn.execute("PRAGMA table_info(wrong_question_submissions)").fetchall()
            }
            row = conn.execute(
                """
                SELECT
                    id,
                    parent_wechat_account_id,
                    binding_id,
                    ingestion_run_id,
                    chat_session_id,
                    question_structured_json,
                    knowledge_tags_json,
                    needs_teacher_confirmation,
                    confirmation_reasons_json
                FROM wrong_question_submissions
                WHERE id=?
                """,
                ("legacy-multisource-record",),
            ).fetchone()

        self.assertEqual(columns["parent_wechat_account_id"]["notnull"], 0)
        self.assertEqual(columns["binding_id"]["notnull"], 0)
        self.assertIn("ingestion_run_id", columns)
        self.assertIn("chat_session_id", columns)
        self.assertIn("question_structured_json", columns)
        self.assertIn("knowledge_tags_json", columns)
        self.assertIn("needs_teacher_confirmation", columns)
        self.assertIn("confirmation_reasons_json", columns)
        self.assertEqual(row["parent_wechat_account_id"], account["id"])
        self.assertEqual(row["binding_id"], binding["id"])
        self.assertEqual(row["ingestion_run_id"], "")
        self.assertEqual(row["chat_session_id"], "")
        self.assertEqual(row["question_structured_json"], "")
        self.assertEqual(row["knowledge_tags_json"], "[]")
        self.assertEqual(row["needs_teacher_confirmation"], 0)
        self.assertEqual(row["confirmation_reasons_json"], "[]")

    def test_create_workspace_and_ai_chat_submissions_without_wechat_binding(self):
        workspace_record = lesson_manager.create_wrong_question_submission(
            source="workspace",
            organization_id=self.organization_id,
            class_id=self.class_id,
            student_id=self.student["id"],
            teacher_user_id=self.owner["id"],
            image_url="https://files.example.com/workspace.png",
            recognition_status="recognized",
            question_text="解方程 $2x+3=9$。",
            question_structured_json={"stem": "解方程 2x+3=9", "subject": "math"},
            knowledge_tags_json=["一元一次方程", "移项"],
            ingestion_run_id="wqrun-workspace-1",
            needs_teacher_confirmation=True,
            confirmation_reasons_json=["ocr_low_confidence"],
        )
        ai_chat_record = lesson_manager.create_wrong_question_submission(
            source="ai_chat",
            organization_id=self.organization_id,
            class_id=self.class_id,
            student_id=self.student["id"],
            teacher_user_id=self.owner["id"],
            image_url="https://files.example.com/ai-chat.png",
            recognition_status="recognized",
            question_text="已知两点间距离公式，求坐标差。",
            knowledge_tags_json=["坐标系"],
            chat_session_id="chat-session-1",
        )
        lesson_manager.create_wrong_question_submission(
            source="workspace",
            organization_id=self.organization_id,
            class_id=self.class_id,
            student_id=self.student["id"],
            teacher_user_id=self.owner["id"],
            image_url="https://files.example.com/pending.png",
            recognition_status="pending",
        )

        library_records = lesson_manager.list_student_wrong_question_library_records(self.student["id"])

        self.assertEqual({item["id"] for item in library_records}, {workspace_record["id"], ai_chat_record["id"]})
        self.assertEqual({item["source"] for item in library_records}, {"workspace", "ai_chat"})
        with lesson_manager.get_conn() as conn:
            saved_workspace = conn.execute(
                """
                SELECT
                    parent_wechat_account_id,
                    binding_id,
                    ingestion_run_id,
                    chat_session_id,
                    question_structured_json,
                    knowledge_tags_json,
                    needs_teacher_confirmation,
                    confirmation_reasons_json
                FROM wrong_question_submissions
                WHERE id=?
                """,
                (workspace_record["id"],),
            ).fetchone()

        self.assertIsNone(saved_workspace["parent_wechat_account_id"])
        self.assertIsNone(saved_workspace["binding_id"])
        self.assertEqual(saved_workspace["ingestion_run_id"], "wqrun-workspace-1")
        self.assertEqual(saved_workspace["chat_session_id"], "")
        self.assertEqual(
            json.loads(saved_workspace["question_structured_json"]),
            {"stem": "解方程 2x+3=9", "subject": "math"},
        )
        self.assertEqual(
            json.loads(saved_workspace["knowledge_tags_json"]),
            ["一元一次方程", "移项"],
        )
        self.assertEqual(saved_workspace["needs_teacher_confirmation"], 1)
        self.assertEqual(
            json.loads(saved_workspace["confirmation_reasons_json"]),
            ["ocr_low_confidence"],
        )

    def test_create_ingestion_run_and_assets_persist_metadata(self):
        run = lesson_manager.create_wrong_question_ingestion_run(
            organization_id=self.organization_id,
            source="ai_chat",
            class_id=self.class_id,
            student_id=self.student["id"],
            teacher_user_id=self.owner["id"],
            chat_session_id="chat-session-2",
            original_filename="wrong-question.pdf",
            mime_type="application/pdf",
            metadata_json={"page_count": 3, "entrypoint": "chat"},
        )
        self.assertEqual(run["current_step"], "uploaded")

        updated_run = lesson_manager.update_wrong_question_ingestion_run(
            run["id"],
            status="ocr_ready",
            current_step="ocr_completed",
            error_message="",
            metadata_json={"page_count": 3, "entrypoint": "chat", "ocr": "pending-review"},
        )
        first_asset = lesson_manager.create_wrong_question_asset(
            ingestion_run_id=run["id"],
            asset_role="original_upload",
            storage_path="/tmp/wrong-question.pdf",
            mime_type="application/pdf",
            metadata_json={"page_count": 3},
        )
        second_asset = lesson_manager.create_wrong_question_asset(
            ingestion_run_id=run["id"],
            asset_role="ocr_page_image",
            storage_path="/tmp/wrong-question-page-1.png",
            mime_type="image/png",
            page_number=1,
            width=1200,
            height=1600,
            metadata_json={"page_index": 0},
        )

        fetched_run = lesson_manager.get_wrong_question_ingestion_run(run["id"])
        assets = lesson_manager.list_wrong_question_assets(run["id"])

        self.assertEqual(fetched_run["id"], run["id"])
        self.assertEqual(updated_run["status"], "ocr_ready")
        self.assertEqual(updated_run["current_step"], "ocr_completed")
        self.assertEqual(fetched_run["current_step"], "ocr_completed")
        self.assertEqual(
            json.loads(updated_run["metadata_json"]),
            {"page_count": 3, "entrypoint": "chat", "ocr": "pending-review"},
        )
        self.assertEqual([item["id"] for item in assets], [first_asset["id"], second_asset["id"]])
        self.assertEqual(assets[0]["asset_role"], "original_upload")
        self.assertEqual(assets[1]["asset_role"], "ocr_page_image")
        self.assertEqual(assets[1]["page_number"], 1)
        self.assertEqual(json.loads(assets[1]["metadata_json"]), {"page_index": 0})

    def test_list_ingestion_runs_filters_by_scope_and_status(self):
        pending_run = lesson_manager.create_wrong_question_ingestion_run(
            organization_id=self.organization_id,
            source="workspace",
            class_id=self.class_id,
            student_id=self.student["id"],
            teacher_user_id=self.owner["id"],
            status="pending",
            current_step="uploaded",
            original_filename="workspace-1.png",
        )
        archived_run = lesson_manager.create_wrong_question_ingestion_run(
            organization_id=self.organization_id,
            source="ai_chat",
            class_id=self.class_id,
            student_id=self.student["id"],
            teacher_user_id=self.owner["id"],
            status="archived",
            current_step="archived",
            chat_session_id="chat-session-filter",
            original_filename="chat-archive.png",
        )

        all_runs = lesson_manager.list_wrong_question_ingestion_runs(organization_id=self.organization_id, limit=10)
        archived_runs = lesson_manager.list_wrong_question_ingestion_runs(
            organization_id=self.organization_id,
            status="archived",
            source="ai_chat",
            chat_session_id="chat-session-filter",
            limit=10,
        )

        self.assertEqual({item["id"] for item in all_runs}, {pending_run["id"], archived_run["id"]})
        self.assertEqual([item["id"] for item in archived_runs], [archived_run["id"]])
        self.assertEqual(archived_runs[0]["current_step"], "archived")


if __name__ == "__main__":
    unittest.main()
