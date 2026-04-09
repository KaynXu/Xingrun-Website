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


class MonthlyPlanAsyncApiTestCase(unittest.TestCase):
    """Tests for async monthly review plan generation (Task 4)."""

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

    def _seed_lesson_for_month(self, month: str = "2026-04"):
        """Create a ready lesson so the monthly endpoint has data to work with."""
        lesson_manager.save_lesson(
            date_str=f"{month}-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="斜率判断",
            plan={"lesson_info": {"topic": "一次函数"}, "days": []},
            pdf_path="",
            class_id=0,
        )

    # ------------------------------------------------------------------
    # POST /api/monthly/generate -> 202 + pending job
    # ------------------------------------------------------------------

    @patch("app._start_monthly_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app.has_api_key", return_value=True)
    def test_monthly_generate_returns_202_with_pending_job(
        self,
        _mock_has_key,
        _mock_credits,
        mock_start_thread,
    ):
        self._seed_lesson_for_month("2026-04")

        response = self.client.post(
            "/api/monthly/generate",
            headers=self._auth_headers(self.owner_token),
            json={"month": "2026-04"},
        )

        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["status"], "pending")
        self.assertIn("id", payload)

        job = lesson_manager.get_monthly_plan_job(payload["id"])
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "pending")
        mock_start_thread.assert_called_once()

    # ------------------------------------------------------------------
    # GET /api/monthly/jobs/<id>
    # ------------------------------------------------------------------

    def test_monthly_job_detail_returns_job(self):
        job = lesson_manager.create_monthly_plan_job(
            organization_id=1, user_id=1, month_str="2026-04",
        )

        response = self.client.get(
            f"/api/monthly/jobs/{job['id']}",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["id"], job["id"])
        self.assertEqual(payload["status"], "pending")

    def test_monthly_job_detail_returns_404_for_missing_job(self):
        response = self.client.get(
            "/api/monthly/jobs/99999",
            headers=self._auth_headers(self.owner_token),
        )
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # POST /api/monthly/jobs/<id>/retry
    # ------------------------------------------------------------------

    @patch("app._start_monthly_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app.has_api_key", return_value=True)
    def test_monthly_retry_requeues_failed_job(
        self,
        _mock_has_key,
        _mock_credits,
        mock_start_thread,
    ):
        job = lesson_manager.create_monthly_plan_job(
            organization_id=1, user_id=1, month_str="2026-04",
        )
        lesson_manager.mark_monthly_plan_job_failed(job["id"], "AI 生成失败，请稍后重试")

        response = self.client.post(
            f"/api/monthly/jobs/{job['id']}/retry",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 202)
        refreshed = lesson_manager.get_monthly_plan_job(job["id"])
        self.assertEqual(refreshed["status"], "pending")
        self.assertEqual(refreshed["generation_error"], "")
        mock_start_thread.assert_called_once()

    def test_monthly_retry_rejects_non_failed_job(self):
        job = lesson_manager.create_monthly_plan_job(
            organization_id=1, user_id=1, month_str="2026-04",
        )

        response = self.client.post(
            f"/api/monthly/jobs/{job['id']}/retry",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
