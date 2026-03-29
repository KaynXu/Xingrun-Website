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


class AccountFlowTestCase(unittest.TestCase):
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
        login_payload = login.get_json()
        self.assertIsNotNone(login_payload)
        return login_payload

    def test_owner_seed_and_approval_flow(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_payload = owner_login.get_json()
        self.assertIsNotNone(owner_payload)
        owner_token = owner_payload["token"]

        me = self.client.get("/api/me", headers=self.auth_headers(owner_token))
        self.assertEqual(me.status_code, 200)
        me_payload = me.get_json()
        self.assertEqual(me_payload["username"], "Kayn")
        self.assertEqual(me_payload["role"], "owner")
        self.assertEqual(me_payload["organization_name"], "星润Starain")

        submit = self.client.post(
            "/api/register-request",
            json={
                "username": "teacher_a",
                "display_name": "Teacher A",
                "password": "secret123",
                "organization_name": "星润Starain",
            },
        )
        self.assertEqual(submit.status_code, 201)

        pending_login = self.client.post(
            "/api/login",
            json={"username": "teacher_a", "password": "secret123"},
        )
        self.assertEqual(pending_login.status_code, 401)

        pending_list = self.client.get(
            "/api/admin/registration-requests",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(pending_list.status_code, 200)
        pending_payload = pending_list.get_json()
        self.assertEqual(len(pending_payload["items"]), 1)
        request_id = pending_payload["items"][0]["id"]

        approve = self.client.post(
            f"/api/admin/registration-requests/{request_id}/approve",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(approve.status_code, 200)

        member_login = self.client.post(
            "/api/login",
            json={"username": "teacher_a", "password": "secret123"},
        )
        self.assertEqual(member_login.status_code, 200)
        member_payload = member_login.get_json()
        self.assertIsNotNone(member_payload)

        member_me = self.client.get(
            "/api/me",
            headers=self.auth_headers(member_payload["token"]),
        )
        self.assertEqual(member_me.status_code, 200)
        member_me_payload = member_me.get_json()
        self.assertEqual(member_me_payload["role"], "member")
        self.assertEqual(member_me_payload["organization_name"], "星润Starain")

    def test_anonymous_users_cannot_access_backend_apis(self):
        stats = self.client.get("/api/stats")
        self.assertEqual(stats.status_code, 401)

        classes = self.client.get("/api/classes")
        self.assertEqual(classes.status_code, 401)

    def test_admin_can_manage_classes_and_assign_member_assignments(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_payload = owner_login.get_json()
        self.assertIsNotNone(owner_payload)
        owner_token = owner_payload["token"]

        admin_payload = self.approve_user(
            owner_token=owner_token,
            username="admin_a",
            display_name="Admin A",
            password="adminpass123",
        )
        admin_token = admin_payload["token"]
        admin_me = self.client.get("/api/me", headers=self.auth_headers(admin_token))
        self.assertEqual(admin_me.status_code, 200)
        admin_me_payload = admin_me.get_json()
        self.assertIsNotNone(admin_me_payload)
        admin_id = admin_me_payload["id"]

        promote = self.client.put(
            f"/api/admin/users/{admin_id}/role",
            headers=self.auth_headers(owner_token),
            json={"role": "admin"},
        )
        self.assertEqual(promote.status_code, 200)

        member_payload = self.approve_user(
            owner_token=owner_token,
            username="member_a",
            display_name="Member A",
            password="memberpass123",
        )
        member_token = member_payload["token"]
        member_me = self.client.get("/api/me", headers=self.auth_headers(member_token))
        self.assertEqual(member_me.status_code, 200)
        member_me_payload = member_me.get_json()
        self.assertIsNotNone(member_me_payload)
        member_id = member_me_payload["id"]

        create_class = self.client.post(
            "/api/classes",
            headers=self.auth_headers(admin_token),
            json={
                "name": "六年级数学冲刺班",
                "subject": "数学",
                "grade": "六年级",
            },
        )
        self.assertEqual(create_class.status_code, 201)
        create_class_payload = create_class.get_json()
        self.assertIsNotNone(create_class_payload)
        class_id = create_class_payload["id"]

        assign_classes = self.client.put(
            f"/api/admin/users/{member_id}/classes",
            headers=self.auth_headers(admin_token),
            json={"class_ids": [class_id]},
        )
        self.assertEqual(assign_classes.status_code, 200)

        member_classes = self.client.get(
            f"/api/admin/users/{member_id}/classes",
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(member_classes.status_code, 200)
        member_classes_payload = member_classes.get_json()
        self.assertIsNotNone(member_classes_payload)
        self.assertEqual(member_classes_payload["class_ids"], [class_id])

        admin_pending_requests = self.client.get(
            "/api/admin/registration-requests",
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(admin_pending_requests.status_code, 403)

        admin_role_update = self.client.put(
            f"/api/admin/users/{member_id}/role",
            headers=self.auth_headers(admin_token),
            json={"role": "admin"},
        )
        self.assertEqual(admin_role_update.status_code, 403)

    def test_member_cannot_write_class_management_apis(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_payload = owner_login.get_json()
        self.assertIsNotNone(owner_payload)
        owner_token = owner_payload["token"]

        member_payload = self.approve_user(
            owner_token=owner_token,
            username="member_b",
            display_name="Member B",
            password="memberpass456",
        )
        member_token = member_payload["token"]

        create_class = self.client.post(
            "/api/classes",
            headers=self.auth_headers(member_token),
            json={
                "name": "六年级数学基础班",
                "subject": "数学",
                "grade": "六年级",
            },
        )
        self.assertEqual(create_class.status_code, 403)

        admin_users = self.client.get(
            "/api/admin/users",
            headers=self.auth_headers(member_token),
        )
        self.assertEqual(admin_users.status_code, 403)


if __name__ == "__main__":
    unittest.main()
