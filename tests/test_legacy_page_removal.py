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


class LegacyPageRemovalTestCase(unittest.TestCase):
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

    def test_root_redirects_to_react_frontend(self):
        response = self.client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "http://127.0.0.1:3000")

    def test_removed_legacy_template_pages_return_404(self):
        responses = [
            self.client.get("/add"),
            self.client.get("/lessons"),
            self.client.get("/classes"),
            self.client.get("/classes/new"),
            self.client.get("/monthly"),
            self.client.get("/quiz"),
            self.client.get("/settings"),
        ]

        for response in responses:
            self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
