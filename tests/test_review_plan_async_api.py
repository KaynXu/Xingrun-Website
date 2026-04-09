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
        app_module._AI_REQUEST_IN_FLIGHT.clear()
        app_module._AI_ORGANIZATION_IN_FLIGHT.clear()
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
    @patch("app.ensure_feature_credits_available")
    @patch("app.has_api_key", return_value=True)
    def test_post_review_plan_returns_202_and_creates_pending_lesson(
        self,
        _mock_has_api_key,
        _mock_ensure_credits,
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
        thread_kwargs = mock_start_thread.call_args.kwargs
        self.assertEqual(thread_kwargs["lesson_id"], lesson_id)
        self.assertEqual(thread_kwargs["user"], {"id": 1, "organization_id": 1})
        self.assertEqual(thread_kwargs["chat_provider"], "openai")
        self.assertEqual(thread_kwargs["chat_model"], "gpt-4o")
        self.assertIn("request_key", thread_kwargs)
        self.assertNotIn("lesson_date", thread_kwargs)
        self.assertNotIn("class_id", thread_kwargs)
        self.assertNotIn("subject", thread_kwargs)
        self.assertNotIn("grade", thread_kwargs)
        self.assertNotIn("topic", thread_kwargs)
        self.assertNotIn("weak_points", thread_kwargs)
        self.assertNotIn("raw_text", thread_kwargs)

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app._current_ai_request_key", return_value="header:duplicate-review-plan")
    @patch("app.has_api_key", return_value=True)
    def test_post_review_plan_rejects_duplicate_request_key_before_creating_pending_lesson(
        self,
        _mock_has_api_key,
        _mock_request_key,
        _mock_ensure_credits,
        mock_start_thread,
    ):
        payload = {
            "date": "2026-04-09",
            "subject": "数学",
            "grade": "初二",
            "topic": "一次函数",
            "weak_points": "斜率判断",
            "summary_text": "课堂总结文本",
            "input_type": "text",
        }

        first = self.client.post(
            "/api/review-plans",
            headers=self._auth_headers(self.owner_token),
            json=payload,
        )
        second = self.client.post(
            "/api/review-plans",
            headers=self._auth_headers(self.owner_token),
            json=payload,
        )

        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 409)
        second_payload = second.get_json()
        self.assertIsNotNone(second_payload)
        self.assertIn("重复请求", second_payload["error"])
        self.assertEqual(len(lesson_manager.list_lessons()), 1)
        mock_start_thread.assert_called_once()

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app._current_ai_request_key", return_value="header:long-running-review-plan")
    @patch("app.has_api_key", return_value=True)
    def test_post_review_plan_duplicate_stays_blocked_after_execution_ttl_window(
        self,
        _mock_has_api_key,
        _mock_request_key,
        _mock_ensure_credits,
        mock_start_thread,
    ):
        original_execution_ttl = app_module._AI_REQUEST_IN_FLIGHT_TTL_SECONDS
        app_module._AI_REQUEST_IN_FLIGHT_TTL_SECONDS = 0.0
        try:
            payload = {
                "date": "2026-04-09",
                "subject": "数学",
                "grade": "初二",
                "topic": "一次函数",
                "weak_points": "斜率判断",
                "summary_text": "课堂总结文本",
                "input_type": "text",
            }

            first = self.client.post(
                "/api/review-plans",
                headers=self._auth_headers(self.owner_token),
                json=payload,
            )
            second = self.client.post(
                "/api/review-plans",
                headers=self._auth_headers(self.owner_token),
                json=payload,
            )
        finally:
            app_module._AI_REQUEST_IN_FLIGHT_TTL_SECONDS = original_execution_ttl

        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(len(lesson_manager.list_lessons()), 1)
        mock_start_thread.assert_called_once()

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available", side_effect=app_module.CreditBalanceError("积分不足，请先充值"))
    @patch("app.has_api_key", return_value=True)
    def test_post_review_plan_returns_402_when_credits_are_insufficient(
        self,
        _mock_has_api_key,
        _mock_ensure_credits,
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

        self.assertEqual(response.status_code, 402)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["error"], "积分不足，请先充值")
        self.assertEqual(lesson_manager.list_lessons(), [])
        mock_start_thread.assert_not_called()

    @patch("app._start_review_plan_generation_thread")
    @patch("app._current_ai_request_key", return_value="header:preflight-crash")
    @patch("app.ensure_feature_credits_available", side_effect=RuntimeError("db boom"))
    @patch("app.has_api_key", return_value=True)
    def test_post_review_plan_releases_request_identity_when_preflight_crashes(
        self,
        _mock_has_api_key,
        _mock_ensure_credits,
        _mock_request_key,
        mock_start_thread,
    ):
        payload = {
            "date": "2026-04-09",
            "subject": "数学",
            "grade": "初二",
            "topic": "一次函数",
            "weak_points": "斜率判断",
            "summary_text": "课堂总结文本",
            "input_type": "text",
        }

        first = self.client.post(
            "/api/review-plans",
            headers=self._auth_headers(self.owner_token),
            json=payload,
        )
        second = self.client.post(
            "/api/review-plans",
            headers=self._auth_headers(self.owner_token),
            json=payload,
        )

        self.assertEqual(first.status_code, 500)
        self.assertEqual(second.status_code, 500)
        self.assertEqual(lesson_manager.list_lessons(), [])
        mock_start_thread.assert_not_called()

    @patch("review_plan_templates.single_lesson_pdf.generate_single_lesson_pdf")
    @patch("ai_processor.parse_and_generate_plan")
    @patch("app._run_ai_feature_with_charge")
    def test_worker_uses_lesson_data_source_of_truth(
        self,
        mock_run_with_charge,
        mock_parse_and_generate_plan,
        mock_generate_pdf,
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

        expected_plan = {"lesson_info": {"topic": "一次函数"}, "days": []}
        mock_run_with_charge.side_effect = lambda **kwargs: kwargs["producer"]()
        mock_parse_and_generate_plan.return_value = expected_plan

        app_module._run_review_plan_generation_job(
            lesson_id=lesson_id,
            user={"id": 1, "organization_id": 1},
            chat_provider="openai",
            chat_model="gpt-4o",
            request_key="test-request-key",
        )

        saved = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(saved["record_status"], "ready")
        self.assertEqual(saved["plan"], expected_plan)
        self.assertEqual(mock_run_with_charge.call_args.kwargs["source_record_id"], lesson_id)
        mock_parse_and_generate_plan.assert_called_once_with(
            summary_text="课堂总结文本",
            subject="数学",
            grade="初二",
            topic="一次函数",
            weak_points="斜率判断",
            lesson_date="2026-04-09",
            include_usage=True,
        )
        mock_generate_pdf.assert_called_once()

    @patch("review_plan_templates.single_lesson_pdf.generate_single_lesson_pdf")
    @patch("ai_processor.parse_and_generate_plan")
    def test_worker_only_processes_pending_lessons(
        self,
        mock_parse_and_generate_plan,
        mock_generate_pdf,
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
        lesson_manager.mark_lesson_generation_succeeded(
            lesson_id,
            plan={"lesson_info": {"topic": "旧计划"}, "days": []},
            pdf_path="/tmp/existing.pdf",
        )

        app_module._run_review_plan_generation_job(
            lesson_id=lesson_id,
            user={"id": 1, "organization_id": 1},
            chat_provider="openai",
            chat_model="gpt-4o",
            request_key="test-request-key",
        )

        saved = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(saved["record_status"], "ready")
        self.assertEqual(saved["generation_error"], "")
        self.assertEqual(saved["pdf_path"], "/tmp/existing.pdf")
        mock_parse_and_generate_plan.assert_not_called()
        mock_generate_pdf.assert_not_called()

    @patch("app._run_ai_feature_with_charge", side_effect=RuntimeError("boom"))
    def test_worker_writes_sanitized_ai_error_message(
        self,
        _mock_run_with_charge,
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
            chat_provider="openai",
            chat_model="gpt-4o",
            request_key="test-request-key",
        )

        saved = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(saved["record_status"], "failed")
        self.assertEqual(saved["generation_error"], "AI 生成失败，请稍后重试")

    @patch("app._run_ai_feature_with_charge", side_effect=app_module.CreditBalanceError("积分不足，请先充值"))
    def test_worker_writes_credit_balance_error_message(
        self,
        _mock_run_with_charge,
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
            chat_provider="openai",
            chat_model="gpt-4o",
            request_key="test-request-key",
        )

        saved = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(saved["record_status"], "failed")
        self.assertEqual(saved["generation_error"], "积分不足，请先充值")

    @patch("review_plan_templates.single_lesson_pdf.generate_single_lesson_pdf", side_effect=RuntimeError("pdf boom"))
    @patch("app._run_ai_feature_with_charge", return_value={"lesson_info": {"topic": "一次函数"}, "days": []})
    def test_worker_writes_sanitized_pdf_error_message(
        self,
        _mock_run_with_charge,
        _mock_generate_pdf,
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
            chat_provider="openai",
            chat_model="gpt-4o",
            request_key="test-request-key",
        )

        saved = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(saved["record_status"], "failed")
        self.assertEqual(saved["generation_error"], "PDF 生成失败，请稍后重试")


if __name__ == "__main__":
    unittest.main()
