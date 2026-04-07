from __future__ import annotations

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


class WeChatParentUploadApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({"wechat_service_token": "wechat-service-token"})
        lesson_manager.init_db()
        self.client = app.test_client()

        self.owner_payload = self.login_owner()
        self.owner_id = self.owner_payload["user"]["id"]
        self.class_id = lesson_manager.save_class(
            "六年级 1 班",
            subject="数学",
            grade="六年级",
            organization_id=self.owner_payload["user"]["organization_id"],
        )
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner_id)
        self.student = lesson_manager.create_student_for_class(self.class_id, "Alice")
        self.invite = lesson_manager.get_or_create_active_class_invite(self.class_id, self.owner_id)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    @staticmethod
    def service_headers() -> dict[str, str]:
        return {"X-Wechat-Service-Token": "wechat-service-token"}

    def login_owner(self) -> dict:
        response = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        return payload

    def test_owner_can_view_and_reset_class_invite(self):
        invite = self.client.get(
            f"/api/classes/{self.class_id}/invite",
            headers=self.auth_headers(self.owner_payload["token"]),
        )
        reset = self.client.post(
            f"/api/classes/{self.class_id}/invite/reset",
            headers=self.auth_headers(self.owner_payload["token"]),
        )

        self.assertEqual(invite.status_code, 200)
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(invite.get_json()["class_id"], self.class_id)
        self.assertNotEqual(invite.get_json()["invite_code"], reset.get_json()["invite_code"])

    def test_wechat_service_can_login_bind_and_upload(self):
        login = self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.get_json()["account"]["openid"], "openid-1")

        bind_preview = self.client.post(
            "/api/wechat/bind-class",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "invite_code": self.invite["invite_code"]},
        )
        self.assertEqual(bind_preview.status_code, 200)
        self.assertEqual(bind_preview.get_json()["class_id"], self.class_id)
        self.assertEqual(bind_preview.get_json()["students"][0]["name"], "Alice")

        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)
        binding = bind.get_json()["binding"]

        upload = self.client.post(
            "/api/wechat/wrong-questions",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "binding_id": binding["id"],
                "image_url": "https://files.example.com/record.png",
                "parent_note": "今天订正后还是错",
            },
        )

        self.assertEqual(upload.status_code, 201)
        record = upload.get_json()["record"]
        self.assertEqual(record["source"], "wechat_mp")
        self.assertEqual(record["teacher_user_id"], self.owner_id)
        self.assertEqual(record["class_id"], self.class_id)
        self.assertEqual(record["student_id"], self.student["id"])

    def test_wechat_service_can_fetch_latest_parent_bindings(self):
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)

        bindings = self.client.get(
            "/api/wechat/bindings",
            headers=self.service_headers(),
            query_string={"open_id": "openid-1"},
        )

        self.assertEqual(bindings.status_code, 200)
        payload = bindings.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["bindings"]), 1)
        self.assertEqual(payload["bindings"][0]["class_name"], "六年级 1 班")
        self.assertEqual(payload["bindings"][0]["student_name"], "Alice")
        self.assertEqual(payload["bindings"][0]["teacher_name"], "平台管理员")

    def test_wechat_service_upload_requires_reason_payload(self):
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)
        binding = bind.get_json()["binding"]

        upload = self.client.post(
            "/api/wechat/wrong-questions",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "binding_id": binding["id"],
                "image_url": "https://files.example.com/record.png",
                "child_raw_reason_text": "我忘记了等式两边同时乘一样的数字",
                "child_reason_input_mode": "voice",
                "primary_error_type": "计算问题",
                "secondary_error_summary": "等式两边没有同时乘相同的数字",
            },
        )

        self.assertEqual(upload.status_code, 201)
        record = upload.get_json()["record"]
        self.assertEqual(record["child_raw_reason_text"], "我忘记了等式两边同时乘一样的数字")
        self.assertEqual(record["child_reason_input_mode"], "voice")
        self.assertEqual(record["primary_error_type"], "计算问题")
        self.assertEqual(record["secondary_error_summary"], "等式两边没有同时乘相同的数字")

    def test_parent_child_library_lists_only_bound_student_records(self):
        second_student = lesson_manager.create_student_for_class(self.class_id, "Bob")

        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        first_binding_response = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(first_binding_response.status_code, 200)
        first_binding = first_binding_response.get_json()["binding"]

        second_binding_response = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": second_student["id"],
            },
        )
        self.assertEqual(second_binding_response.status_code, 200)
        second_binding = second_binding_response.get_json()["binding"]

        first_upload = self.client.post(
            "/api/wechat/wrong-questions",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "binding_id": first_binding["id"],
                "image_url": "https://files.example.com/record-1.png",
            },
        )
        self.assertEqual(first_upload.status_code, 201)

        second_upload = self.client.post(
            "/api/wechat/wrong-questions",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "binding_id": second_binding["id"],
                "image_url": "https://files.example.com/record-2.png",
            },
        )
        self.assertEqual(second_upload.status_code, 201)

        response = self.client.get(
            f"/api/wechat/children/{self.student['id']}/wrong-questions",
            headers=self.service_headers(),
            query_string={"open_id": "openid-1"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["student_id"], self.student["id"])
        self.assertEqual(payload["items"][0]["id"], first_upload.get_json()["record"]["id"])

    def test_parent_child_library_returns_404_for_different_parent_open_id(self):
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-2", "nickname_snapshot": "Bob 妈妈"},
        )

        response = self.client.get(
            f"/api/wechat/children/{self.student['id']}/wrong-questions",
            headers=self.service_headers(),
            query_string={"open_id": "openid-2"},
        )

        self.assertEqual(response.status_code, 404)

    def test_parent_child_library_returns_404_for_unbound_student(self):
        unbound_student = lesson_manager.create_student_for_class(self.class_id, "Bob")
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)

        response = self.client.get(
            f"/api/wechat/children/{unbound_student['id']}/wrong-questions",
            headers=self.service_headers(),
            query_string={"open_id": "openid-1"},
        )

        self.assertEqual(response.status_code, 404)

if __name__ == "__main__":
    unittest.main()
