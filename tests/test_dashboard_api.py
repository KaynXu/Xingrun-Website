import gc
import tempfile
import unittest
from pathlib import Path

import config_runtime
import lesson_manager
from app import app


class DashboardApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app.test_client()

    def tearDown(self):
        gc.collect()
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def login_as_kayn(self) -> str:
        response = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        return payload["token"]

    def test_super_owner_dashboard_returns_platform_payload(self):
        token = self.login_as_kayn()

        response = self.client.get("/api/dashboard", headers=self.auth_headers(token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        platform = payload.get("platform")
        self.assertIsInstance(platform, dict)
        stat_labels = [item["label"] for item in platform["stats"]]
        self.assertIn("待咨询", stat_labels)
        self.assertNotIn("待反馈", stat_labels)


if __name__ == "__main__":
    unittest.main()
