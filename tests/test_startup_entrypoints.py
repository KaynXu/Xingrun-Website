from pathlib import Path
from unittest.mock import patch
import unittest

import app as backend_app


ROOT = Path(__file__).resolve().parents[1]


class StartupEntrypointsTestCase(unittest.TestCase):
    def test_run_backend_disables_browser_auto_open_by_default(self):
        script = (ROOT / "scripts" / "run_backend.sh").read_text(encoding="utf-8")
        self.assertIn("XR_OPEN_BROWSER", script)
        self.assertRegex(script, r"XR_OPEN_BROWSER.*0")

    def test_launcher_scripts_do_not_open_backend_url_directly(self):
        start_command = (ROOT / "start.command").read_text(encoding="utf-8")
        start_bat = (ROOT / "start.bat").read_text(encoding="utf-8")

        self.assertNotIn('open "http://127.0.0.1:5001"', start_command)
        self.assertNotIn("start http://127.0.0.1:5001", start_bat)
        self.assertIn("3000", start_command)
        self.assertIn("3000", start_bat)

    def test_readme_clarifies_backend_only_shortcuts_and_frontend_entry(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("3000", readme)
        self.assertIn("5001", readme)
        self.assertIn("前端需要单独启动", readme)
        self.assertIn("3000 才是开发态页面入口", readme)
        self.assertIn("start.command", readme)
        self.assertIn("仅启动后端", readme)

    def test_app_startup_message_matches_browser_setting(self):
        with patch.dict("os.environ", {"XR_OPEN_BROWSER": "0", "XR_BROWSER_URL": "http://127.0.0.1:3000"}):
            message = backend_app._startup_browser_message()
            self.assertIn("前端页面入口", message)
            self.assertNotIn("即将自动打开", message)

        with patch.dict("os.environ", {"XR_OPEN_BROWSER": "1", "XR_BROWSER_URL": "http://127.0.0.1:3000"}):
            message = backend_app._startup_browser_message()
            self.assertIn("浏览器即将自动打开", message)
            self.assertIn("http://127.0.0.1:3000", message)


if __name__ == "__main__":
    unittest.main()
