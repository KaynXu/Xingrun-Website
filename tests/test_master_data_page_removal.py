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


class MasterDataPageRemovalApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
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

    def test_removed_master_data_page_routes_return_404_for_owner(self):
        owner_payload = self.login_owner()
        owner_token = owner_payload["token"]

        responses = [
            self.client.get(
                "/api/master-data/mappings/wrong-questions",
                headers=self.auth_headers(owner_token),
            ),
            self.client.put(
                "/api/master-data/mappings/wrong-questions/record-1",
                headers=self.auth_headers(owner_token),
                json={"mapping_status": "mapped"},
            ),
            self.client.get(
                "/api/master-data/users/1/aliases",
                headers=self.auth_headers(owner_token),
            ),
            self.client.put(
                "/api/master-data/users/1/aliases",
                headers=self.auth_headers(owner_token),
                json={"aliases": ["Kayn老师"]},
            ),
            self.client.get(
                "/api/master-data/classes/1/aliases",
                headers=self.auth_headers(owner_token),
            ),
            self.client.put(
                "/api/master-data/classes/1/aliases",
                headers=self.auth_headers(owner_token),
                json={"aliases": ["六年级1班"]},
            ),
        ]

        for response in responses:
            self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
