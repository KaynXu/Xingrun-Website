import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager
import master_data
from app import app


class MasterDataApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app.test_client()

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

    def approve_user(
        self,
        owner_token: str,
        username: str,
        display_name: str,
        password: str,
    ) -> dict:
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

    def test_owner_can_list_queue_and_resolve_mapping(self):
        owner_payload = self.login_owner()
        owner_token = owner_payload["token"]
        owner_id = owner_payload["user"]["id"]

        class_id = lesson_manager.save_class("六年级 1 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner_id)

        master_data.upsert_wrong_question_mapping(
            "record-1",
            teacher_name_snapshot="Kayn 老师",
            class_name_snapshot="六年级1班",
            subject_snapshot="数学",
            mapping_status="needs_review",
        )

        queue_response = self.client.get(
            "/api/master-data/mappings/wrong-questions",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(queue_response.status_code, 200)
        queue_payload = queue_response.get_json()
        self.assertIsNotNone(queue_payload)
        self.assertEqual(len(queue_payload["items"]), 1)
        self.assertEqual(queue_payload["items"][0]["record_id"], "record-1")
        self.assertEqual(queue_payload["items"][0]["mapping_status"], "needs_review")
        self.assertEqual(queue_payload["items"][0]["teacher_user_id"], None)
        self.assertEqual(queue_payload["items"][0]["class_id"], None)

        resolve_response = self.client.put(
            "/api/master-data/mappings/wrong-questions/record-1",
            headers=self.auth_headers(owner_token),
            json={
                "teacher_user_id": owner_id,
                "class_id": class_id,
                "mapping_status": "mapped",
            },
        )
        self.assertEqual(resolve_response.status_code, 200)
        resolved_payload = resolve_response.get_json()
        self.assertIsNotNone(resolved_payload)
        self.assertEqual(resolved_payload["record_id"], "record-1")
        self.assertEqual(resolved_payload["teacher_user_id"], owner_id)
        self.assertEqual(resolved_payload["class_id"], class_id)
        self.assertEqual(resolved_payload["mapping_status"], "mapped")
        self.assertEqual(resolved_payload["teacher_display_name"], "Kayn")
        self.assertEqual(resolved_payload["class_display_name"], "六年级 1 班")

        user_aliases = self.client.get(
            f"/api/master-data/users/{owner_id}/aliases",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(user_aliases.status_code, 200)
        self.assertIn("Kayn 老师", user_aliases.get_json()["aliases"])

        class_aliases = self.client.get(
            f"/api/master-data/classes/{class_id}/aliases",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(class_aliases.status_code, 200)
        self.assertIn("六年级1班", class_aliases.get_json()["aliases"])

        queue_after_resolve = self.client.get(
            "/api/master-data/mappings/wrong-questions",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(queue_after_resolve.status_code, 200)
        self.assertEqual(queue_after_resolve.get_json()["items"], [])

    def test_member_gets_403_on_queue_and_resolve(self):
        owner_payload = self.login_owner()
        owner_token = owner_payload["token"]
        member_payload = self.approve_user(
            owner_token=owner_token,
            username="member_mapping",
            display_name="Member Mapping",
            password="member123",
        )
        member_token = member_payload["token"]

        master_data.upsert_wrong_question_mapping(
            "record-member-1",
            teacher_name_snapshot="Unknown Teacher",
            class_name_snapshot="Unknown Class",
            subject_snapshot="数学",
            mapping_status="needs_review",
        )

        queue_response = self.client.get(
            "/api/master-data/mappings/wrong-questions",
            headers=self.auth_headers(member_token),
        )
        self.assertEqual(queue_response.status_code, 403)
        self.assertEqual(queue_response.get_json()["error"], "无权限")

        resolve_response = self.client.put(
            "/api/master-data/mappings/wrong-questions/record-member-1",
            headers=self.auth_headers(member_token),
            json={"mapping_status": "mapped"},
        )
        self.assertEqual(resolve_response.status_code, 403)
        self.assertEqual(resolve_response.get_json()["error"], "无权限")

    def test_owner_can_read_and_write_user_aliases(self):
        owner_payload = self.login_owner()
        owner_token = owner_payload["token"]
        owner_id = owner_payload["user"]["id"]

        get_empty = self.client.get(
            f"/api/master-data/users/{owner_id}/aliases",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(get_empty.status_code, 200)
        self.assertEqual(get_empty.get_json()["aliases"], [])

        update_response = self.client.put(
            f"/api/master-data/users/{owner_id}/aliases",
            headers=self.auth_headers(owner_token),
            json={"aliases": ["Kayn 老师", "Wendy Wang", "Kayn 老师", " "]},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.get_json()["aliases"], ["Kayn 老师", "Wendy Wang"])

        get_updated = self.client.get(
            f"/api/master-data/users/{owner_id}/aliases",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(get_updated.status_code, 200)
        self.assertEqual(get_updated.get_json()["aliases"], ["Kayn 老师", "Wendy Wang"])

    def test_owner_can_read_and_write_class_aliases(self):
        owner_payload = self.login_owner()
        owner_token = owner_payload["token"]
        class_id = lesson_manager.save_class("六年级 2 班", subject="数学", grade="六年级")

        get_empty = self.client.get(
            f"/api/master-data/classes/{class_id}/aliases",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(get_empty.status_code, 200)
        self.assertEqual(get_empty.get_json()["aliases"], [])

        update_response = self.client.put(
            f"/api/master-data/classes/{class_id}/aliases",
            headers=self.auth_headers(owner_token),
            json={"aliases": ["六年级2班", "G6 Math B", "六年级2班"]},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.get_json()["aliases"], ["G6 Math B", "六年级2班"])

        get_updated = self.client.get(
            f"/api/master-data/classes/{class_id}/aliases",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(get_updated.status_code, 200)
        self.assertEqual(get_updated.get_json()["aliases"], ["G6 Math B", "六年级2班"])


if __name__ == "__main__":
    unittest.main()