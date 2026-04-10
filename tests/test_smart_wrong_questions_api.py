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
import master_data
import smart_wrong_questions
from app import app


class FakeResponse:
    def __init__(self, raw: bytes, headers: dict[str, str] | None = None):
        self._raw = raw
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._raw


class SmartWrongQuestionsApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config(
            {
                "wrong_question_service_url": "http://wrong-question-service.local",
                "wrong_question_service_token": "teacher-token-1",
            }
        )
        lesson_manager.init_db()
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def approve_user(self, owner_token: str, username: str, display_name: str, password: str) -> dict:
        submit = self.client.post(
            "/api/register-request",
            json={
                "username": username,
                "display_name": display_name,
                "password": password,
                "organization_name": "星润Starain",
            },
        )
        self.assertEqual(submit.status_code, 201)

        pending_list = self.client.get(
            "/api/admin/registration-requests",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(pending_list.status_code, 200)
        pending_payload = pending_list.get_json()
        self.assertIsNotNone(pending_payload)

        request_id = None
        for item in pending_payload["items"]:
            if item["username"] == username:
                request_id = item["id"]
                break

        self.assertIsNotNone(request_id)

        approve = self.client.post(
            f"/api/admin/registration-requests/{request_id}/approve",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(approve.status_code, 200)

        login = self.client.post(
            "/api/login",
            json={"username": username, "password": password},
        )
        self.assertEqual(login.status_code, 200)
        payload = login.get_json()
        self.assertIsNotNone(payload)
        return payload

    def login_owner(self) -> dict:
        response = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        return payload

    def create_local_wechat_record(self, owner_id: int, organization_id: int | None = None, openid: str = "openid-local-1") -> dict:
        class_id = lesson_manager.save_class(
            "六年级 9 班",
            subject="数学",
            grade="六年级",
            organization_id=organization_id,
        )
        lesson_manager.set_class_teacher_user_id(class_id, owner_id)
        student = lesson_manager.create_student_for_class(class_id, "Alice")
        account = lesson_manager.upsert_parent_wechat_account(openid=openid)
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=class_id,
            student_id=student["id"],
        )
        return lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/local-record.png",
            parent_note="本地微信错题",
        )

    @patch("smart_wrong_questions.fetch_wrong_question_records")
    def test_member_can_access_wrong_question_routes_with_class_scope(self, fetch_wrong_question_records):
        owner_payload = self.login_owner()
        member_payload = self.approve_user(
            owner_token=owner_payload["token"],
            username="member_wrong_question",
            display_name="Member Wrong Question",
            password="member123",
        )
        member_id = member_payload["user"]["id"]
        class_id = lesson_manager.save_class("六年级 7 班", subject="数学", grade="六年级")
        lesson_manager.set_user_class_ids(member_id, [class_id])
        fetch_wrong_question_records.return_value = {
            "items": [
                {"id": "record-visible", "class_id": class_id, "student_name": "Alice"},
                {"id": "record-hidden", "class_id": class_id + 1, "student_name": "Bob"},
            ],
            "total": 2,
        }

        response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(member_payload["token"]),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual([item["id"] for item in payload["items"]], ["record-visible"])
        self.assertEqual(payload["summary"]["total_count"], 1)

    @patch("smart_wrong_questions.fetch_wrong_question_records")
    def test_staff_can_list_wrong_question_records(self, fetch_wrong_question_records):
        owner_payload = self.login_owner()
        fetch_wrong_question_records.return_value = {
            "items": [
                {
                    "id": "record-1",
                    "student_name": "Alice",
                    "subject": "Math",
                }
            ],
            "total": 1,
        }

        response = self.client.get(
            "/api/wrong-questions?studentName=Alice&page=1&pageSize=20&empty=",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total"], 1)
        self.assertEqual(response.get_json()["items"][0]["id"], "record-1")
        fetch_wrong_question_records.assert_called_once()
        forwarded_args = fetch_wrong_question_records.call_args.args[0]
        self.assertEqual(forwarded_args.get("studentName"), "Alice")
        self.assertEqual(forwarded_args.get("page"), "1")
        self.assertEqual(forwarded_args.get("pageSize"), "20")
        self.assertEqual(forwarded_args.get("empty"), "")

    @patch("smart_wrong_questions.fetch_wrong_question_records")
    def test_staff_wrong_question_list_returns_scoped_summary_counts(self, fetch_wrong_question_records):
        owner_payload = self.login_owner()
        fetch_wrong_question_records.return_value = {
            "items": [
                {
                    "id": "record-1",
                    "student_name": "Alice",
                    "class_name": "六年级 1 班",
                    "class_id": 101,
                    "analysis": {
                        "is_repeated_mistake": "是",
                        "teacher_priority": "高",
                    },
                },
                {
                    "id": "record-2",
                    "student_name": "Bob",
                    "class_name": "六年级 1 班",
                    "class_id": 101,
                    "analysis": {
                        "selected_error_type": "计算错误",
                    },
                },
                {
                    "id": "record-3",
                    "student_name": "Carol",
                    "class_name": "六年级 2 班",
                    "class_id": 202,
                    "analysis": {},
                },
            ],
            "total": 3,
        }

        response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(
            payload["summary"],
            {
                "total_count": 3,
                "repeated_mistake_count": 1,
                "high_priority_count": 1,
                "pending_review_count": 2,
                "unique_class_count": 2,
                "unique_student_count": 3,
            },
        )

    @patch("smart_wrong_questions.fetch_wrong_question_records")
    def test_staff_can_see_unmapped_org_records_in_global_workspace(self, fetch_wrong_question_records):
        owner_payload = self.login_owner()
        fetch_wrong_question_records.return_value = {
            "items": [
                {
                    "id": "record-unmapped",
                    "student_name": "Alice",
                    "teacher_user_id": None,
                    "class_id": None,
                    "mapping_status": "unmapped",
                }
            ],
            "total": 1,
        }

        response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["id"], "record-unmapped")

    @patch("smart_wrong_questions.fetch_wrong_question_records")
    def test_local_wechat_records_are_merged_into_workspace_list(self, fetch_wrong_question_records):
        owner_payload = self.login_owner()
        record = self.create_local_wechat_record(owner_payload["user"]["id"])
        fetch_wrong_question_records.return_value = {"items": [], "total": 0}

        response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        item = response.get_json()["items"][0]
        self.assertEqual(item["id"], record["id"])
        self.assertEqual(item["source"], "wechat_mp")
        self.assertEqual(item["class_id"], record["class_id"])
        self.assertEqual(item["student_id"], record["student_id"])
        self.assertEqual(item["teacher_user_id"], record["teacher_user_id"])

    @patch("smart_wrong_questions.fetch_wrong_question_records")
    def test_staff_global_workspace_excludes_other_organization_local_records(self, fetch_wrong_question_records):
        owner_payload = self.login_owner()
        with lesson_manager.get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
                VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (
                    "org_admin",
                    lesson_manager.hash_password("org-admin-123"),
                    "Org Admin",
                    "admin",
                    owner_payload["user"]["organization_id"],
                ),
            )
            admin_user_id = cur.lastrowid
        admin_token = lesson_manager.create_auth_session(admin_user_id)

        self.create_local_wechat_record(
            owner_payload["user"]["id"],
            owner_payload["user"]["organization_id"],
            "openid-local-owner-1",
        )

        with lesson_manager.get_conn() as conn:
            other_org = lesson_manager._ensure_organization(conn, "第二机构")
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
                VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (
                    "other_owner",
                    lesson_manager.hash_password("other-owner-123"),
                    "Other Owner",
                    "owner",
                    other_org["id"],
                ),
            )
            other_owner_id = cur.lastrowid
        other_owner_payload = {
            "user": {"id": other_owner_id, "organization_id": other_org["id"]},
            "token": lesson_manager.create_auth_session(other_owner_id),
        }
        self.create_local_wechat_record(
            other_owner_payload["user"]["id"],
            other_owner_payload["user"]["organization_id"],
            "openid-local-owner-2",
        )

        fetch_wrong_question_records.return_value = {"items": [], "total": 0}

        response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(admin_token),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["organization_id"], owner_payload["user"]["organization_id"])

    @patch("smart_wrong_questions.request.urlopen")
    def test_staff_list_payload_exposes_canonical_fields_after_backend_normalization(self, urlopen):
        owner_payload = self.login_owner()
        owner_id = owner_payload["user"]["id"]
        class_id = lesson_manager.save_class("六年级 1 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner_id)
        master_data.set_user_aliases(
            actor_user_id=owner_id,
            user_id=owner_id,
            aliases=["Kayn 老师"],
        )
        master_data.set_class_aliases(
            actor_user_id=owner_id,
            class_id=class_id,
            aliases=["六年级1班"],
        )
        urlopen.return_value = FakeResponse(
            json.dumps(
                {
                    "items": [
                        {
                            "id": "record-1",
                            "teacher_name": "Kayn 老师",
                            "class_name": "六年级1班",
                            "subject": "数学",
                            "student_name": "Alice",
                        }
                    ],
                    "total": 1,
                }
            ).encode("utf-8")
        )

        response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        item = response.get_json()["items"][0]
        self.assertEqual(item["teacher_user_id"], owner_id)
        self.assertEqual(item["teacher_display_name"], owner_payload["user"]["display_name"])
        self.assertEqual(item["teacher_name_snapshot"], "Kayn 老师")
        self.assertEqual(item["class_id"], class_id)
        self.assertEqual(item["class_display_name"], "六年级 1 班")
        self.assertEqual(item["class_name_snapshot"], "六年级1班")
        self.assertEqual(item["mapping_status"], "mapped")

    @patch("smart_wrong_questions.request.urlopen")
    def test_later_reads_upgrade_previously_unresolved_mapping_when_master_data_becomes_available(self, urlopen):
        owner_payload = self.login_owner()
        owner_id = owner_payload["user"]["id"]

        urlopen.return_value = FakeResponse(
            json.dumps(
                {
                    "items": [
                        {
                            "id": "record-upgrade-1",
                            "teacher_name": "Kayn 老师",
                            "class_name": "六年级3班",
                            "subject": "数学",
                            "student_name": "Alice",
                        }
                    ],
                    "total": 1,
                }
            ).encode("utf-8")
        )

        first_response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(first_response.status_code, 200)
        first_item = first_response.get_json()["items"][0]
        self.assertEqual(first_item["mapping_status"], "unmapped")
        self.assertEqual(first_item["teacher_user_id"], None)
        self.assertEqual(first_item["class_id"], None)

        first_mapping = master_data.get_wrong_question_mapping("record-upgrade-1")
        self.assertIsNotNone(first_mapping)
        self.assertEqual(first_mapping["mapping_status"], "unmapped")
        self.assertEqual(first_mapping["teacher_user_id"], None)
        self.assertEqual(first_mapping["class_id"], None)

        class_id = lesson_manager.save_class("六年级 3 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner_id)
        master_data.set_user_aliases(
            actor_user_id=owner_id,
            user_id=owner_id,
            aliases=["Kayn 老师"],
        )
        master_data.set_class_aliases(
            actor_user_id=owner_id,
            class_id=class_id,
            aliases=["六年级3班"],
        )

        second_response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(second_response.status_code, 200)
        second_item = second_response.get_json()["items"][0]
        self.assertEqual(second_item["mapping_status"], "mapped")
        self.assertEqual(second_item["teacher_user_id"], owner_id)
        self.assertEqual(second_item["teacher_display_name"], owner_payload["user"]["display_name"])
        self.assertEqual(second_item["class_id"], class_id)
        self.assertEqual(second_item["class_display_name"], "六年级 3 班")

        upgraded_mapping = master_data.get_wrong_question_mapping("record-upgrade-1")
        self.assertIsNotNone(upgraded_mapping)
        self.assertEqual(upgraded_mapping["mapping_status"], "mapped")
        self.assertEqual(upgraded_mapping["teacher_user_id"], owner_id)
        self.assertEqual(upgraded_mapping["class_id"], class_id)

    @patch("smart_wrong_questions.request.urlopen")
    def test_later_reads_degrade_stale_mapped_record_after_class_teacher_rebinding(self, urlopen):
        owner_payload = self.login_owner()
        owner_token = owner_payload["token"]
        owner_id = owner_payload["user"]["id"]
        replacement_teacher = self.approve_user(
            owner_token=owner_token,
            username="teacher_rebind",
            display_name="Teacher Rebind",
            password="teacher123",
        )
        replacement_teacher_id = replacement_teacher["user"]["id"]

        class_id = lesson_manager.save_class("六年级 6 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner_id)
        master_data.set_user_aliases(
            actor_user_id=owner_id,
            user_id=owner_id,
            aliases=["Kayn 老师"],
        )
        master_data.set_class_aliases(
            actor_user_id=owner_id,
            class_id=class_id,
            aliases=["六年级6班"],
        )
        urlopen.return_value = FakeResponse(
            json.dumps(
                {
                    "items": [
                        {
                            "id": "record-rebind-1",
                            "teacher_name": "Kayn 老师",
                            "class_name": "六年级6班",
                            "subject": "数学",
                            "student_name": "Alice",
                        }
                    ],
                    "total": 1,
                }
            ).encode("utf-8")
        )

        first_response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_token),
        )

        self.assertEqual(first_response.status_code, 200)
        first_item = first_response.get_json()["items"][0]
        self.assertEqual(first_item["mapping_status"], "mapped")
        self.assertEqual(first_item["teacher_user_id"], owner_id)
        self.assertEqual(first_item["teacher_display_name"], owner_payload["user"]["display_name"])
        self.assertEqual(first_item["class_id"], class_id)
        self.assertEqual(first_item["class_display_name"], "六年级 6 班")

        lesson_manager.set_class_teacher_user_id(class_id, replacement_teacher_id)

        second_response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_token),
        )

        self.assertEqual(second_response.status_code, 200)
        second_item = second_response.get_json()["items"][0]
        self.assertEqual(second_item["mapping_status"], "needs_review")
        self.assertIsNone(second_item["teacher_user_id"])
        self.assertEqual(second_item["teacher_display_name"], "Kayn 老师")
        self.assertIsNone(second_item["class_id"])
        self.assertEqual(second_item["class_display_name"], "六年级6班")

        persisted = master_data.get_wrong_question_mapping("record-rebind-1")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["mapping_status"], "mapped")
        self.assertEqual(persisted["teacher_user_id"], owner_id)
        self.assertEqual(persisted["class_id"], class_id)

    @patch("smart_wrong_questions.request.urlopen")
    def test_later_reads_refresh_snapshot_fields_even_when_mapping_stays_unresolved(self, urlopen):
        owner_payload = self.login_owner()
        urlopen.side_effect = [
            FakeResponse(
                json.dumps(
                    {
                        "items": [
                            {
                                "id": "record-refresh-1",
                                "teacher_name": "Kayn 老师",
                                "class_name": "六年级5班",
                                "subject": "数学",
                                "student_name": "Alice",
                            }
                        ],
                        "total": 1,
                    }
                ).encode("utf-8")
            ),
            FakeResponse(
                json.dumps(
                    {
                        "items": [
                            {
                                "id": "record-refresh-1",
                                "teacher_name": "Kayn 老师（代课）",
                                "class_name": "六年级五班-临时",
                                "subject": "数学提高",
                                "student_name": "Alice",
                            }
                        ],
                        "total": 1,
                    }
                ).encode("utf-8")
            ),
        ]

        first_response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(first_response.status_code, 200)
        first_item = first_response.get_json()["items"][0]
        self.assertEqual(first_item["mapping_status"], "unmapped")
        self.assertEqual(first_item["teacher_user_id"], None)
        self.assertEqual(first_item["class_id"], None)
        self.assertEqual(first_item["teacher_name_snapshot"], "Kayn 老师")
        self.assertEqual(first_item["class_name_snapshot"], "六年级5班")

        first_mapping = master_data.get_wrong_question_mapping("record-refresh-1")
        self.assertIsNotNone(first_mapping)
        self.assertEqual(first_mapping["mapping_status"], "unmapped")
        self.assertEqual(first_mapping["teacher_name_snapshot"], "Kayn 老师")
        self.assertEqual(first_mapping["class_name_snapshot"], "六年级5班")
        self.assertEqual(first_mapping["subject_snapshot"], "数学")

        second_response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(second_response.status_code, 200)
        second_item = second_response.get_json()["items"][0]
        self.assertEqual(second_item["mapping_status"], "unmapped")
        self.assertEqual(second_item["teacher_user_id"], None)
        self.assertEqual(second_item["class_id"], None)
        self.assertEqual(second_item["teacher_display_name"], "Kayn 老师（代课）")
        self.assertEqual(second_item["teacher_name_snapshot"], "Kayn 老师（代课）")
        self.assertEqual(second_item["class_display_name"], "六年级五班-临时")
        self.assertEqual(second_item["class_name_snapshot"], "六年级五班-临时")

        refreshed_mapping = master_data.get_wrong_question_mapping("record-refresh-1")
        self.assertIsNotNone(refreshed_mapping)
        self.assertEqual(refreshed_mapping["mapping_status"], "unmapped")
        self.assertEqual(refreshed_mapping["teacher_user_id"], None)
        self.assertEqual(refreshed_mapping["class_id"], None)
        self.assertEqual(refreshed_mapping["teacher_name_snapshot"], "Kayn 老师（代课）")
        self.assertEqual(refreshed_mapping["class_name_snapshot"], "六年级五班-临时")
        self.assertEqual(refreshed_mapping["subject_snapshot"], "数学提高")

    @patch("smart_wrong_questions.fetch_wrong_question_record")
    def test_staff_can_get_wrong_question_record_detail(self, fetch_wrong_question_record):
        owner_payload = self.login_owner()
        fetch_wrong_question_record.return_value = {
            "id": "record-42",
            "student_name": "Alice",
            "question_text": "2 + 2 = ?",
        }

        response = self.client.get(
            "/api/wrong-questions/record-42?studentName=Alice&subject=Math",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["id"], "record-42")
        fetch_wrong_question_record.assert_called_once()
        self.assertEqual(fetch_wrong_question_record.call_args.args[0], "record-42")
        forwarded_args = fetch_wrong_question_record.call_args.args[1]
        self.assertEqual(forwarded_args.get("studentName"), "Alice")
        self.assertEqual(forwarded_args.get("subject"), "Math")

    @patch("smart_wrong_questions.fetch_wrong_question_record")
    @patch("smart_wrong_questions.save_wrong_question_review")
    def test_local_wechat_records_support_detail_and_review(self, save_wrong_question_review, fetch_wrong_question_record):
        owner_payload = self.login_owner()
        record = self.create_local_wechat_record(owner_payload["user"]["id"])

        detail = self.client.get(
            f"/api/wrong-questions/{record['id']}",
            headers=self.auth_headers(owner_payload["token"]),
        )
        review = self.client.put(
            f"/api/wrong-questions/{record['id']}/review",
            headers=self.auth_headers(owner_payload["token"]),
            json={"is_mastered": True},
        )

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["id"], record["id"])
        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.get_json()["record"]["archive_status"], "archived")
        self.assertTrue(review.get_json()["record"]["is_mastered"])
        fetch_wrong_question_record.assert_not_called()
        save_wrong_question_review.assert_not_called()

    @patch("app._rebuild_student_wrong_question_library", return_value="/tmp/student-1.pdf")
    def test_local_wrong_question_review_can_update_question_text(self, _mock_rebuild):
        owner_payload = self.login_owner()
        record = self.create_local_wechat_record(owner_payload["user"]["id"])
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE wrong_question_submissions
                SET recognition_status='recognized',
                    question_text='原始 AI 文本',
                    question_text_source='ai'
                WHERE id=?
                """,
                (record["id"],),
            )

        response = self.client.put(
            f"/api/wrong-questions/{record['id']}/review",
            headers=self.auth_headers(owner_payload["token"]),
            json={
                "is_mastered": False,
                "question_text": "老师修正后的题目文本",
            },
        )

        self.assertEqual(response.status_code, 200)
        saved = response.get_json()["record"]
        self.assertEqual(saved["question_text"], "老师修正后的题目文本")
        self.assertEqual(saved["question_text_source"], "teacher")
        self.assertEqual(saved["student_library_pdf_path"], "/tmp/student-1.pdf")

    @patch("smart_wrong_questions.request.urlopen")
    def test_staff_detail_payload_exposes_canonical_fields_after_backend_normalization(self, urlopen):
        owner_payload = self.login_owner()
        owner_id = owner_payload["user"]["id"]
        class_id = lesson_manager.save_class("六年级 2 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner_id)
        master_data.set_user_aliases(
            actor_user_id=owner_id,
            user_id=owner_id,
            aliases=["Kayn 老师"],
        )
        master_data.set_class_aliases(
            actor_user_id=owner_id,
            class_id=class_id,
            aliases=["六年级2班"],
        )
        urlopen.return_value = FakeResponse(
            json.dumps(
                {
                    "id": "record-42",
                    "teacher_name": "Kayn 老师",
                    "class_name": "六年级2班",
                    "subject": "数学",
                    "student_name": "Alice",
                    "question_text": "2 + 2 = ?",
                }
            ).encode("utf-8")
        )

        response = self.client.get(
            "/api/wrong-questions/record-42",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["teacher_user_id"], owner_id)
        self.assertEqual(payload["teacher_display_name"], owner_payload["user"]["display_name"])
        self.assertEqual(payload["teacher_name_snapshot"], "Kayn 老师")
        self.assertEqual(payload["class_id"], class_id)
        self.assertEqual(payload["class_display_name"], "六年级 2 班")
        self.assertEqual(payload["class_name_snapshot"], "六年级2班")
        self.assertEqual(payload["mapping_status"], "mapped")

    @patch("smart_wrong_questions.request.urlopen")
    def test_wrong_question_list_accepts_downstream_records_key(self, mock_urlopen):
        owner_payload = self.login_owner()

        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
            {
                "roomId": "XINGRUN",
                "total": 1,
                "records": [
                    {
                        "id": "record-r1",
                        "studentName": "阿斯顿",
                        "teacherName": "曹老师",
                        "className": "八年级2班",
                        "analysis": {"questionCategory": "待确认"},
                    }
                ],
            }
        ).encode("utf-8")

        response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["id"], "record-r1")

    @patch("smart_wrong_questions.fetch_wrong_question_record")
    @patch("smart_wrong_questions.save_wrong_question_review")
    def test_staff_can_save_wrong_question_review(self, save_wrong_question_review, fetch_wrong_question_record):
        owner_payload = self.login_owner()
        fetch_wrong_question_record.return_value = {"id": "record-42", "teacher_user_id": owner_payload["user"]["id"]}
        save_wrong_question_review.return_value = {
            "ok": True,
            "record": {"id": "record-42", "teacher_comment": "需要重做"},
        }

        response = self.client.put(
            "/api/wrong-questions/record-42/review?teacherName=Kayn",
            headers=self.auth_headers(owner_payload["token"]),
            json={"teacher_comment": "需要重做", "mastery": "needs_practice"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        save_wrong_question_review.assert_called_once()
        self.assertEqual(save_wrong_question_review.call_args.args[0], "record-42")
        forwarded_args = save_wrong_question_review.call_args.args[1]
        forwarded_payload = save_wrong_question_review.call_args.args[2]
        self.assertEqual(forwarded_args.get("teacherName"), "Kayn")
        self.assertEqual(
            forwarded_payload,
            {"teacher_comment": "需要重做", "mastery": "needs_practice"},
        )

    @patch("smart_wrong_questions.fetch_wrong_question_records")
    def test_list_route_translates_non_config_proxy_errors(self, fetch_wrong_question_records):
        owner_payload = self.login_owner()
        fetch_wrong_question_records.side_effect = smart_wrong_questions.WrongQuestionProxyError(
            "下游服务不可用: timeout",
            502,
        )

        response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json(), {"error": "下游服务不可用: timeout"})

    def test_list_route_still_returns_local_wechat_records_when_service_is_unconfigured(self):
        owner_payload = self.login_owner()
        record = self.create_local_wechat_record(owner_payload["user"]["id"])
        config_runtime.write_file_config(
            {
                "wrong_question_service_url": "",
                "wrong_question_service_token": "",
            }
        )

        response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["total"], 1)
        self.assertEqual([item["id"] for item in payload["items"]], [record["id"]])
        self.assertEqual(payload["items"][0]["source"], "wechat_mp")

    @patch("smart_wrong_questions.fetch_wrong_question_record")
    @patch("smart_wrong_questions.save_wrong_question_review")
    def test_review_route_translates_downstream_proxy_errors(self, save_wrong_question_review, fetch_wrong_question_record):
        owner_payload = self.login_owner()
        fetch_wrong_question_record.return_value = {"id": "record-42", "teacher_user_id": owner_payload["user"]["id"]}
        save_wrong_question_review.side_effect = smart_wrong_questions.WrongQuestionProxyError(
            "下游服务不可用: timeout",
            502,
        )

        response = self.client.put(
            "/api/wrong-questions/record-42/review",
            headers=self.auth_headers(owner_payload["token"]),
            json={"teacher_comment": "需要重做"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json(), {"error": "下游服务不可用: timeout"})

    @patch("smart_wrong_questions.fetch_wrong_question_record")
    def test_detail_route_translates_downstream_proxy_errors(self, fetch_wrong_question_record):
        owner_payload = self.login_owner()
        fetch_wrong_question_record.side_effect = smart_wrong_questions.WrongQuestionProxyError(
            "记录不存在",
            404,
        )

        response = self.client.get(
            "/api/wrong-questions/record-missing",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "记录不存在"})

    @patch("smart_wrong_questions.request.urlopen")
    def test_malformed_downstream_json_becomes_proxy_error(self, urlopen):
        urlopen.return_value = FakeResponse(b"not-json")

        with self.assertRaises(smart_wrong_questions.WrongQuestionProxyError) as ctx:
            smart_wrong_questions.fetch_wrong_question_records({"studentName": "Alice"})

        self.assertEqual(str(ctx.exception), "下游服务返回了无效响应")
        self.assertEqual(ctx.exception.status_code, 502)

    @patch("smart_wrong_questions.request.urlopen")
    def test_list_route_translates_non_object_downstream_json_root(self, urlopen):
        owner_payload = self.login_owner()
        urlopen.return_value = FakeResponse(json.dumps([{"id": "record-1"}]).encode("utf-8"))

        response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json(), {"error": "下游服务返回了无效响应"})

    @patch("smart_wrong_questions.export_wrong_question_summary")
    def test_export_route_returns_pdf_attachment(self, export_wrong_question_summary):
        owner_payload = self.login_owner()
        export_wrong_question_summary.return_value = {
            "content": b"%PDF-1.4\nmock pdf\n",
            "filename": "wrong-question-summary.pdf",
        }

        response = self.client.get(
            "/api/wrong-questions/summary/export?studentName=Alice",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertIn(
            'attachment; filename=wrong-question-summary.pdf',
            response.headers.get("Content-Disposition", ""),
        )
        self.assertEqual(response.data, b"%PDF-1.4\nmock pdf\n")
        export_wrong_question_summary.assert_called_once()
        forwarded_args = export_wrong_question_summary.call_args.args[0]
        self.assertEqual(forwarded_args.get("studentName"), "Alice")

    @patch("smart_wrong_questions.export_wrong_question_summary")
    def test_export_route_translates_proxy_errors(self, export_wrong_question_summary):
        owner_payload = self.login_owner()
        export_wrong_question_summary.side_effect = smart_wrong_questions.WrongQuestionProxyError(
            "导出服务暂不可用",
            502,
        )

        response = self.client.get(
            "/api/wrong-questions/summary/export?studentName=Alice",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json(), {"error": "导出服务暂不可用"})


if __name__ == "__main__":
    unittest.main()
