from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime as real_datetime
from pathlib import Path
from urllib.parse import quote
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
                "recovery_phone": "13800000000",
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
        )

    def create_local_wechat_binding(self, owner_id: int, organization_id: int | None = None, openid: str = "openid-local-practice") -> dict:
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
        return {
            "class_id": class_id,
            "student": student,
            "account": account,
            "binding": binding,
        }

    def create_recognized_local_wechat_record(self, binding_id: int, *, image_url: str, question_text: str, is_geometry: bool) -> dict:
        return lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding_id,
            image_url=image_url,
            child_raw_reason_text="我当时做题时有点急",
            primary_error_type="细节问题",
            secondary_error_summary="步骤检查不完整",
            recognition_status="recognized",
            is_geometry=is_geometry,
            question_text=question_text,
            question_text_source="teacher",
        )

    def test_summary_export_route_is_removed(self):
        owner_payload = self.login_owner()

        response = self.client.get(
            "/api/wrong-questions/summary/export?studentName=Alice",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 404)

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
    def test_staff_can_filter_wrong_question_records_by_confirmation_state(self, fetch_wrong_question_records):
        owner_payload = self.login_owner()
        fetch_wrong_question_records.return_value = {"items": [], "total": 0}
        class_id = lesson_manager.save_class(
            "六年级 9 班",
            subject="数学",
            grade="六年级",
            organization_id=owner_payload["user"]["organization_id"],
        )
        lesson_manager.set_class_teacher_user_id(class_id, owner_payload["user"]["id"])
        student = lesson_manager.create_student_for_class(class_id, "Queue Student")

        pending_record = lesson_manager.create_wrong_question_submission(
            source="ai_chat",
            organization_id=owner_payload["user"]["organization_id"],
            class_id=class_id,
            student_id=student["id"],
            teacher_user_id=owner_payload["user"]["id"],
            image_url="https://files.example.com/queue-pending.png",
            recognition_status="recognized",
            needs_teacher_confirmation=True,
            confirmation_reasons_json=["missing_question_text"],
        )
        confirmed_record = lesson_manager.create_wrong_question_submission(
            source="ai_chat",
            organization_id=owner_payload["user"]["organization_id"],
            class_id=class_id,
            student_id=student["id"],
            teacher_user_id=owner_payload["user"]["id"],
            image_url="https://files.example.com/queue-confirmed.png",
            recognition_status="recognized",
        )
        returned_record = lesson_manager.create_wrong_question_submission(
            source="ai_chat",
            organization_id=owner_payload["user"]["organization_id"],
            class_id=class_id,
            student_id=student["id"],
            teacher_user_id=owner_payload["user"]["id"],
            image_url="https://files.example.com/queue-returned.png",
            recognition_status="recognized",
            needs_teacher_confirmation=True,
            confirmation_reasons_json=["student_confused_step"],
        )

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE wrong_question_submissions
                SET confirmation_status='confirmed',
                    confirmation_reviewed_by=?,
                    confirmation_reviewed_at='2026-06-03 10:00:00'
                WHERE id=?
                """,
                (owner_payload["user"]["id"], confirmed_record["id"]),
            )
            conn.execute(
                """
                UPDATE wrong_question_submissions
                SET confirmation_status='returned',
                    confirmation_reviewed_by=?,
                    confirmation_reviewed_at='2026-06-03 11:00:00'
                WHERE id=?
                """,
                (owner_payload["user"]["id"], returned_record["id"]),
            )

        pending_response = self.client.get(
            "/api/wrong-questions?confirmationState=pending",
            headers=self.auth_headers(owner_payload["token"]),
        )
        self.assertEqual(pending_response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in pending_response.get_json()["items"]],
            [pending_record["id"]],
        )

        returned_response = self.client.get(
            "/api/wrong-questions?confirmationState=returned",
            headers=self.auth_headers(owner_payload["token"]),
        )
        self.assertEqual(returned_response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in returned_response.get_json()["items"]],
            [returned_record["id"]],
        )

        confirmed_response = self.client.get(
            "/api/wrong-questions?confirmationState=confirmed",
            headers=self.auth_headers(owner_payload["token"]),
        )
        self.assertEqual(confirmed_response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in confirmed_response.get_json()["items"]],
            [confirmed_record["id"]],
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
        self.assertNotIn("parent_note", detail.get_json())
        self.assertNotIn("teacher_comment", detail.get_json())
        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.get_json()["record"]["archive_status"], "archived")
        self.assertTrue(review.get_json()["record"]["is_mastered"])
        self.assertNotIn("parent_note", review.get_json()["record"])
        self.assertNotIn("teacher_comment", review.get_json()["record"])
        fetch_wrong_question_record.assert_not_called()
        save_wrong_question_review.assert_not_called()

    def test_local_wrong_question_detail_includes_archive_navigation_context(self):
        owner_payload = self.login_owner()
        class_id = lesson_manager.save_class(
            "六年级 8 班",
            subject="数学",
            grade="六年级",
            organization_id=owner_payload["user"]["organization_id"],
        )
        lesson_manager.set_class_teacher_user_id(class_id, owner_payload["user"]["id"])
        student = lesson_manager.create_student_for_class(class_id, "Alice")
        run = lesson_manager.create_wrong_question_ingestion_run(
            organization_id=owner_payload["user"]["organization_id"],
            source="ai_chat",
            class_id=class_id,
            student_id=student["id"],
            teacher_user_id=owner_payload["user"]["id"],
            chat_session_id="chat-session-record-detail",
            status="archived",
            current_step="archived",
        )
        lesson_manager.create_wrong_question_chat_session(
            session_id="chat-session-record-detail",
            organization_id=owner_payload["user"]["organization_id"],
            ingestion_run_id=run["id"],
            class_id=class_id,
            student_id=student["id"],
            teacher_user_id=owner_payload["user"]["id"],
            status="archived",
            current_stage="ready_to_archive",
            summary_text="错因自述：移项前没有先看清等式两边。",
        )
        lesson_manager.create_wrong_question_chat_message(
            session_id="chat-session-record-detail",
            role="assistant",
            stage="ask_unknown_step",
            content="你是在哪一步开始不确定的？",
        )
        lesson_manager.create_wrong_question_asset(
            ingestion_run_id=run["id"],
            asset_role="original_upload",
            storage_path="/tmp/archive-detail.png",
            file_url="/api/wrong-question-ingestion-assets/archive-detail.png",
            mime_type="image/png",
            page_number=1,
            metadata_json={"original_filename": "archive-detail.png"},
        )
        lesson_manager.create_wrong_question_asset(
            ingestion_run_id=run["id"],
            asset_role="ocr_page_image",
            storage_path="/tmp/archive-detail-ocr.png",
            mime_type="image/png",
            page_number=1,
            metadata_json={"page_index": 0},
        )
        record = lesson_manager.create_wrong_question_submission(
            source="ai_chat",
            organization_id=owner_payload["user"]["organization_id"],
            class_id=class_id,
            student_id=student["id"],
            teacher_user_id=owner_payload["user"]["id"],
            image_url="https://files.example.com/archive-detail.png",
            recognition_status="recognized",
            question_text="解方程 2x+5=17。",
            ingestion_run_id=run["id"],
            chat_session_id="chat-session-record-detail",
        )
        practice_sheet = lesson_manager.create_pending_wrong_question_practice_sheet(
            created_by=owner_payload["user"]["id"],
            selected_records=[record],
        )
        lesson_manager.mark_wrong_question_practice_sheet_succeeded(
            practice_sheet["id"],
            generated_items=[
                {
                    "wrong_question_record_id": record["id"],
                    "ai_hint": "先移项。",
                    "reason_blank_prompt": "这题我错在 ______。",
                    "improvement_summary_prompt": "下次先 ______。",
                },
            ],
            pdf_path="/tmp/archive-detail-practice.pdf",
        )

        detail = self.client.get(
            f"/api/wrong-questions/{record['id']}",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(detail.status_code, 200)
        payload = detail.get_json()
        self.assertEqual(payload["detail_url"], f"/api/wrong-questions/{record['id']}")
        self.assertEqual(payload["archive_context"]["ingestion_run_id"], run["id"])
        self.assertEqual(payload["archive_context"]["ingestion_run_url"], f"/api/wrong-question-ingestions/{run['id']}")
        self.assertEqual(payload["archive_context"]["chat_session_id"], "chat-session-record-detail")
        self.assertEqual(
            payload["archive_context"]["chat_session_url"],
            "/api/wrong-question-chats/chat-session-record-detail",
        )
        self.assertIsNotNone(payload["linked_ingestion_run"])
        self.assertEqual(payload["linked_ingestion_run"]["detail_url"], f"/api/wrong-question-ingestions/{run['id']}")
        self.assertEqual(payload["linked_ingestion_run"]["current_step"], "archived")
        self.assertEqual(
            [item["asset_role"] for item in payload["linked_ingestion_run"]["assets"]],
            ["original_upload", "ocr_page_image"],
        )
        self.assertIsNotNone(payload["linked_chat_session"])
        self.assertEqual(payload["linked_chat_session"]["detail_url"], "/api/wrong-question-chats/chat-session-record-detail")
        self.assertEqual(payload["linked_chat_session"]["summary_text"], "错因自述：移项前没有先看清等式两边。")
        self.assertEqual(len(payload["linked_chat_session"]["messages"]), 1)
        self.assertEqual(payload["linked_chat_session"]["messages"][0]["content"], "你是在哪一步开始不确定的？")
        self.assertEqual(payload["mastery_tracking"]["practice_sheet_count"], 1)
        self.assertEqual(payload["mastery_tracking"]["latest_practice_sheet_id"], practice_sheet["id"])
        self.assertEqual(payload["mastery_tracking"]["latest_practice_status"], "ready")
        self.assertEqual(payload["mastery_tracking"]["latest_practice_pdf_path"], "/tmp/archive-detail-practice.pdf")

    @patch("app._rebuild_student_wrong_question_library", return_value="/tmp/student-archive-detail.pdf")
    def test_local_ai_chat_review_can_update_archive_detail_fields(self, _mock_rebuild):
        owner_payload = self.login_owner()
        class_id = lesson_manager.save_class(
            "六年级 9 班",
            subject="数学",
            grade="六年级",
            organization_id=owner_payload["user"]["organization_id"],
        )
        lesson_manager.set_class_teacher_user_id(class_id, owner_payload["user"]["id"])
        student = lesson_manager.create_student_for_class(class_id, "Bob")
        run = lesson_manager.create_wrong_question_ingestion_run(
            organization_id=owner_payload["user"]["organization_id"],
            source="ai_chat",
            class_id=class_id,
            student_id=student["id"],
            teacher_user_id=owner_payload["user"]["id"],
            chat_session_id="chat-session-review-detail",
            status="archived",
            current_step="archived",
        )
        record = lesson_manager.create_wrong_question_submission(
            source="ai_chat",
            organization_id=owner_payload["user"]["organization_id"],
            class_id=class_id,
            student_id=student["id"],
            teacher_user_id=owner_payload["user"]["id"],
            image_url="https://files.example.com/archive-review.png",
            recognition_status="recognized",
            question_text="原始题干",
            ingestion_run_id=run["id"],
            chat_session_id="chat-session-review-detail",
            knowledge_tags_json=["移项"],
            needs_teacher_confirmation=True,
            confirmation_reasons_json=["missing_question_text"],
        )

        response = self.client.put(
            f"/api/wrong-questions/{record['id']}/review",
            headers=self.auth_headers(owner_payload["token"]),
            json={
                "selectedErrorType": "概念错误",
                "selectedKnowledgePoints": ["一元一次方程", "移项"],
                "studentNote": "老师已补齐知识点并确认题干。",
                "needs_teacher_confirmation": False,
                "confirmation_reasons_json": [],
                "question_text": "老师修正后的题干",
            },
        )

        self.assertEqual(response.status_code, 200)
        saved = response.get_json()["record"]
        self.assertEqual(saved["question_text"], "老师修正后的题干")
        self.assertEqual(saved["analysis"]["selected_error_type"], "概念错误")
        self.assertEqual(saved["analysis"]["knowledge_points"], ["一元一次方程", "移项"])
        self.assertFalse(saved["needs_teacher_confirmation"])
        self.assertEqual(saved["confirmation_reasons"], [])

        refreshed = lesson_manager.get_wechat_wrong_question_submission(record["id"])
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed["question_text"], "老师修正后的题干")
        self.assertEqual(json.loads(refreshed["knowledge_tags_json"]), ["一元一次方程", "移项"])
        self.assertEqual(refreshed["primary_error_type"], "概念错误")
        self.assertEqual(refreshed["secondary_error_summary"], "老师已补齐知识点并确认题干。")
        self.assertEqual(refreshed["question_text_source"], "teacher")
        self.assertEqual(refreshed["needs_teacher_confirmation"], 0)
        self.assertEqual(json.loads(refreshed["confirmation_reasons_json"]), [])
        self.assertEqual(refreshed["confirmation_status"], "confirmed")
        self.assertEqual(refreshed["confirmation_reviewed_by"], owner_payload["user"]["id"])
        self.assertTrue(refreshed["confirmation_reviewed_at"])

    @patch("app._rebuild_student_wrong_question_library", return_value="/tmp/student-archive-detail.pdf")
    def test_local_ai_chat_review_can_return_record_for_rework(self, _mock_rebuild):
        owner_payload = self.login_owner()
        class_id = lesson_manager.save_class(
            "六年级 9 班",
            subject="数学",
            grade="六年级",
            organization_id=owner_payload["user"]["organization_id"],
        )
        lesson_manager.set_class_teacher_user_id(class_id, owner_payload["user"]["id"])
        student = lesson_manager.create_student_for_class(class_id, "Bob")
        record = lesson_manager.create_wrong_question_submission(
            source="ai_chat",
            organization_id=owner_payload["user"]["organization_id"],
            class_id=class_id,
            student_id=student["id"],
            teacher_user_id=owner_payload["user"]["id"],
            image_url="https://files.example.com/archive-review-returned.png",
            recognition_status="recognized",
            question_text="原始题干",
            knowledge_tags_json=["移项"],
            needs_teacher_confirmation=True,
            confirmation_reasons_json=["student_confused_step"],
        )

        response = self.client.put(
            f"/api/wrong-questions/{record['id']}/review",
            headers=self.auth_headers(owner_payload["token"]),
            json={
                "selectedErrorType": "概念错误",
                "confirmation_action": "return_for_rework",
            },
        )

        self.assertEqual(response.status_code, 200)
        saved = response.get_json()["record"]
        self.assertTrue(saved["needs_teacher_confirmation"])
        self.assertEqual(saved["confirmation_status"], "returned")
        self.assertEqual(saved["confirmation_reviewer_name"], owner_payload["user"]["display_name"])

        refreshed = lesson_manager.get_wechat_wrong_question_submission(record["id"])
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed["confirmation_status"], "returned")
        self.assertEqual(refreshed["confirmation_reviewed_by"], owner_payload["user"]["id"])
        self.assertTrue(refreshed["confirmation_reviewed_at"])

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

    @patch("app._refresh_student_wrong_question_library_cache", return_value="/tmp/student-1.pdf")
    def test_staff_can_refresh_student_wrong_question_library_pdf(self, mock_refresh):
        owner_payload = self.login_owner()
        bundle = self.create_local_wechat_binding(owner_payload["user"]["id"], owner_payload["user"]["organization_id"])
        self.create_recognized_local_wechat_record(
            bundle["binding"]["id"],
            image_url="https://files.example.com/local-record.png",
            question_text="老师修正后的题目文本",
            is_geometry=False,
        )

        response = self.client.post(
            f"/api/wrong-question-student-libraries/{bundle['student']['id']}/refresh",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["student_id"], bundle["student"]["id"])
        self.assertEqual(payload["student_library_pdf_path"], "/tmp/student-1.pdf")
        self.assertEqual(payload["pdf_url"], f"/api/wechat/student-libraries/{bundle['student']['id']}")
        mock_refresh.assert_called_once_with(bundle["student"]["id"])

    @patch("app._refresh_student_wrong_question_library_cache")
    def test_member_cannot_refresh_unowned_student_wrong_question_library_pdf(self, mock_refresh):
        owner_payload = self.login_owner()
        bundle = self.create_local_wechat_binding(owner_payload["user"]["id"], owner_payload["user"]["organization_id"])
        self.create_recognized_local_wechat_record(
            bundle["binding"]["id"],
            image_url="https://files.example.com/local-record.png",
            question_text="老师修正后的题目文本",
            is_geometry=False,
        )
        member_payload = self.approve_user(owner_payload["token"], "member-pdf-refresh", "成员", "member-pass-1")

        response = self.client.post(
            f"/api/wrong-question-student-libraries/{bundle['student']['id']}/refresh",
            headers=self.auth_headers(member_payload["token"]),
        )

        self.assertEqual(response.status_code, 404)
        mock_refresh.assert_not_called()

    @patch("app.has_api_key", return_value=True)
    @patch("app._start_wrong_question_practice_generation_thread")
    def test_staff_can_create_pending_wrong_question_practice_sheet(self, mock_start_thread, _mock_has_api_key):
        owner_payload = self.login_owner()
        bundle = self.create_local_wechat_binding(owner_payload["user"]["id"], owner_payload["user"]["organization_id"])
        record_one = self.create_recognized_local_wechat_record(
            bundle["binding"]["id"],
            image_url="https://files.example.com/practice-1.png",
            question_text="计算 $2+3\\times4$ 的结果。",
            is_geometry=False,
        )
        record_two = self.create_recognized_local_wechat_record(
            bundle["binding"]["id"],
            image_url="https://files.example.com/practice-2.png",
            question_text="",
            is_geometry=True,
        )

        response = self.client.post(
            "/api/wrong-question-practice-sheets",
            headers=self.auth_headers(owner_payload["token"]),
            json={
                "student_id": bundle["student"]["id"],
                "wrong_question_ids": [record_one["id"], record_two["id"]],
            },
        )

        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["status"], "pending")

        saved = lesson_manager.get_wrong_question_practice_sheet(payload["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "pending")
        self.assertEqual(saved["question_count"], 2)
        self.assertEqual(
            [item["wrong_question_record_id"] for item in saved["items"]],
            [record_one["id"], record_two["id"]],
        )
        mock_start_thread.assert_called_once()
        self.assertEqual(mock_start_thread.call_args.kwargs["sheet_id"], payload["id"])

    @patch("app.has_api_key", return_value=True)
    @patch("app._start_wrong_question_practice_generation_thread")
    def test_staff_can_create_pending_wrong_question_practice_sheet_from_confirmed_ai_chat_record(self, mock_start_thread, _mock_has_api_key):
        owner_payload = self.login_owner()
        class_id = lesson_manager.save_class(
            "六年级 9 班",
            subject="数学",
            grade="六年级",
            organization_id=owner_payload["user"]["organization_id"],
        )
        lesson_manager.set_class_teacher_user_id(class_id, owner_payload["user"]["id"])
        student = lesson_manager.create_student_for_class(class_id, "Practice Chat Student")
        record = lesson_manager.create_wrong_question_submission(
            source="ai_chat",
            organization_id=owner_payload["user"]["organization_id"],
            class_id=class_id,
            student_id=student["id"],
            teacher_user_id=owner_payload["user"]["id"],
            image_url="https://files.example.com/practice-chat.png",
            recognition_status="recognized",
            question_text="解方程 $x+5=12$。",
            child_raw_reason_text="我移项时把符号看反了",
        )

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE wrong_question_submissions
                SET confirmation_status='confirmed',
                    confirmation_reviewed_by=?,
                    confirmation_reviewed_at='2026-06-03 12:00:00'
                WHERE id=?
                """,
                (owner_payload["user"]["id"], record["id"]),
            )

        response = self.client.post(
            "/api/wrong-question-practice-sheets",
            headers=self.auth_headers(owner_payload["token"]),
            json={
                "student_id": student["id"],
                "wrong_question_ids": [record["id"]],
            },
        )

        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["status"], "pending")

        saved = lesson_manager.get_wrong_question_practice_sheet(payload["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["question_count"], 1)
        self.assertEqual(saved["items"][0]["wrong_question_record_id"], record["id"])
        self.assertEqual(saved["items"][0]["source"], "ai_chat")
        self.assertEqual(saved["items"][0]["question_text_snapshot"], "解方程 $x+5=12$。")
        mock_start_thread.assert_called_once()
        self.assertEqual(mock_start_thread.call_args.kwargs["sheet_id"], payload["id"])

    @patch("app.has_api_key", return_value=True)
    @patch("app._start_wrong_question_practice_generation_thread")
    def test_staff_cannot_create_pending_wrong_question_practice_sheet_from_unconfirmed_ai_chat_record(self, mock_start_thread, _mock_has_api_key):
        owner_payload = self.login_owner()
        class_id = lesson_manager.save_class(
            "六年级 9 班",
            subject="数学",
            grade="六年级",
            organization_id=owner_payload["user"]["organization_id"],
        )
        lesson_manager.set_class_teacher_user_id(class_id, owner_payload["user"]["id"])
        student = lesson_manager.create_student_for_class(class_id, "Pending Chat Student")
        record = lesson_manager.create_wrong_question_submission(
            source="ai_chat",
            organization_id=owner_payload["user"]["organization_id"],
            class_id=class_id,
            student_id=student["id"],
            teacher_user_id=owner_payload["user"]["id"],
            image_url="https://files.example.com/practice-chat-pending.png",
            recognition_status="recognized",
            question_text="解方程 $x+7=11$。",
            needs_teacher_confirmation=True,
            confirmation_reasons_json=["missing_question_text"],
        )

        response = self.client.post(
            "/api/wrong-question-practice-sheets",
            headers=self.auth_headers(owner_payload["token"]),
            json={
                "student_id": student["id"],
                "wrong_question_ids": [record["id"]],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"],
            "selected ai chat records must be confirmed before generating practice",
        )
        mock_start_thread.assert_not_called()

    def test_staff_can_list_wrong_question_practice_sheets_for_student(self):
        owner_payload = self.login_owner()
        bundle = self.create_local_wechat_binding(owner_payload["user"]["id"], owner_payload["user"]["organization_id"])
        record = self.create_recognized_local_wechat_record(
            bundle["binding"]["id"],
            image_url="https://files.example.com/practice-history.png",
            question_text="计算 $7-3$ 的结果。",
            is_geometry=False,
        )
        sheet = lesson_manager.create_pending_wrong_question_practice_sheet(
            created_by=owner_payload["user"]["id"],
            selected_records=[lesson_manager.get_wechat_wrong_question_submission(record["id"])],
        )
        lesson_manager.mark_wrong_question_practice_sheet_succeeded(
            sheet["id"],
            generated_items=[
                {
                    "wrong_question_record_id": record["id"],
                    "ai_hint": "先看清运算符号，再回忆这一步该先做什么。",
                    "reason_blank_prompt": "这题我错在 ______，因为我忽略了 ______。",
                    "improvement_summary_prompt": "以后遇到同类题，我会先 ______，再 ______。",
                }
            ],
            pdf_path="/tmp/practice-history.pdf",
        )

        response = self.client.get(
            f"/api/wrong-question-practice-sheets?student_id={bundle['student']['id']}",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["id"], sheet["id"])
        self.assertEqual(payload["items"][0]["status"], "ready")
        self.assertEqual(payload["items"][0]["pdf_path"], "/tmp/practice-history.pdf")
        self.assertEqual(payload["items"][0]["question_count"], 1)

    def test_staff_can_preview_and_download_wrong_question_practice_pdf(self):
        owner_payload = self.login_owner()
        bundle = self.create_local_wechat_binding(owner_payload["user"]["id"], owner_payload["user"]["organization_id"])
        record = self.create_recognized_local_wechat_record(
            bundle["binding"]["id"],
            image_url="https://files.example.com/practice-pdf.png",
            question_text="计算 $8+5$ 的结果。",
            is_geometry=False,
        )
        sheet = lesson_manager.create_pending_wrong_question_practice_sheet(
            created_by=owner_payload["user"]["id"],
            selected_records=[lesson_manager.get_wechat_wrong_question_submission(record["id"])],
        )
        pdf_path = self.base / "practice-sheet.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")
        lesson_manager.mark_wrong_question_practice_sheet_succeeded(
            sheet["id"],
            generated_items=[
                {
                    "wrong_question_record_id": record["id"],
                    "ai_hint": "先列式，再核对结果。",
                    "reason_blank_prompt": "这题我错在 ______。",
                    "improvement_summary_prompt": "以后我会先 ______。",
                }
            ],
            pdf_path=str(pdf_path),
        )

        preview_response = self.client.get(
            f"/api/wrong-question-practice-sheets/{sheet['id']}/pdf",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response.mimetype, "application/pdf")
        self.assertEqual(preview_response.data, pdf_path.read_bytes())
        preview_response.close()

        with patch("app.datetime") as mock_datetime:
            mock_datetime.now.return_value = real_datetime(2026, 4, 25, 9, 30, 0)
            download_response = self.client.get(
                f"/api/wrong-question-practice-sheets/{sheet['id']}/pdf/download",
                headers=self.auth_headers(owner_payload["token"]),
            )

        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response.mimetype, "application/pdf")
        content_disposition = download_response.headers.get("Content-Disposition", "")
        self.assertIn("attachment;", content_disposition)
        self.assertIn(
            f"filename*=UTF-8''{quote('Alice练习单_2026-04-25.pdf')}",
            content_disposition,
        )
        self.assertEqual(download_response.data, pdf_path.read_bytes())
        download_response.close()

    def test_staff_can_delete_wrong_question_practice_sheet(self):
        owner_payload = self.login_owner()
        bundle = self.create_local_wechat_binding(owner_payload["user"]["id"], owner_payload["user"]["organization_id"])
        record = self.create_recognized_local_wechat_record(
            bundle["binding"]["id"],
            image_url="https://files.example.com/practice-delete.png",
            question_text="计算 $9-4$ 的结果。",
            is_geometry=False,
        )
        sheet = lesson_manager.create_pending_wrong_question_practice_sheet(
            created_by=owner_payload["user"]["id"],
            selected_records=[lesson_manager.get_wechat_wrong_question_submission(record["id"])],
        )
        pdf_path = self.base / "practice-delete.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")
        lesson_manager.mark_wrong_question_practice_sheet_succeeded(
            sheet["id"],
            generated_items=[
                {
                    "wrong_question_record_id": record["id"],
                    "ai_hint": "下次做这类题，先看清运算符号。",
                    "reason_blank_prompt": "这题我错在 ______，因为我忽略了 ______。",
                    "improvement_summary_prompt": "以后遇到同类题，我会先 ______，做完再 ______。",
                }
            ],
            pdf_path=str(pdf_path),
        )

        response = self.client.delete(
            f"/api/wrong-question-practice-sheets/{sheet['id']}",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["deleted_sheet_id"], sheet["id"])
        self.assertFalse(pdf_path.exists())
        self.assertIsNone(lesson_manager.get_wrong_question_practice_sheet(sheet["id"]))

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

if __name__ == "__main__":
    unittest.main()
