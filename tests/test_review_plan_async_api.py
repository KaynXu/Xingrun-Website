import gc
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module
import config_runtime
import lesson_manager
from app import app


class ReviewPlanAsyncApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app.test_client()
        self.owner_token = self._login_as_owner()

    def tearDown(self):
        gc.collect()
        self.temp_dir.cleanup()

    @staticmethod
    def _auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def _login_as_owner(self) -> str:
        login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(login.status_code, 200)
        payload = login.get_json()
        self.assertIsNotNone(payload)
        return payload["token"]

    @patch("app._start_review_plan_generation_thread")
    @patch("app.has_api_key", return_value=True)
    def test_post_review_plan_returns_202_and_creates_pending_lesson(
        self,
        _mock_has_api_key,
        mock_start_thread,
    ):
        response = self.client.post(
            "/api/review-plans",
            headers=self._auth_headers(self.owner_token),
            json={
                "date": "2026-04-09",
                "subject": "数学",
                "grade": "初二",
                "topic": "一次函数",
                "weak_points": "斜率判断",
                "summary_text": "课堂总结文本",
                "input_type": "text",
            },
        )

        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["status"], "pending")

        lesson_id = payload["id"]
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertIsNotNone(lesson)
        self.assertEqual(lesson["record_status"], "pending")
        self.assertEqual(lesson["generation_error"], "")
        self.assertEqual(lesson["summary"], "课堂总结文本")

        mock_start_thread.assert_called_once()
        self.assertEqual(mock_start_thread.call_args.kwargs["lesson_id"], lesson_id)

    @patch("app.finalize_ai_charge", return_value={})
    @patch("app.ensure_feature_credits_available")
    @patch("ai_processor.parse_and_generate_plan", side_effect=RuntimeError("boom"))
    def test_worker_marks_pending_lesson_failed_when_ai_generation_raises(
        self,
        _mock_generate,
        _mock_ensure_credits,
        _mock_finalize,
    ):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结文本",
            weak_points="斜率判断",
            class_id=0,
        )

        app_module._run_review_plan_generation_job(
            lesson_id=lesson_id,
            user={"id": 1, "organization_id": 1},
            lesson_date="2026-04-09",
            class_id=0,
            subject="数学",
            grade="初二",
            topic="一次函数",
            weak_points="斜率判断",
            raw_text="课堂总结文本",
            chat_provider="openai",
            chat_model="gpt-4o",
            request_key="test-request-key",
        )

        saved = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(saved["record_status"], "failed")
        self.assertIn("AI 生成失败", saved["generation_error"])
        self.assertIn("boom", saved["generation_error"])


if __name__ == "__main__":
    unittest.main()
