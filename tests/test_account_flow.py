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


if __name__ == "__main__":
    unittest.main()
