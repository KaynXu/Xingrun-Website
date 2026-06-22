import gc
import io
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
import credit_manager
import lesson_manager
from app import app
from tests.review_plan_test_utils import valid_single_lesson_plan


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

    def test_get_review_plans_includes_creator_display_name(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结文本",
            weak_points="斜率判断",
            created_by_user_id=1,
        )

        response = self.client.get(
            "/api/review-plans",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        lesson = next(item for item in payload if item["id"] == lesson_id)
        self.assertEqual(lesson["creator_display_name"], lesson_manager.get_user_by_id(1)["display_name"])
        self.assertEqual(lesson["creator_username"], lesson_manager.get_user_by_id(1)["username"])

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app.has_review_plan_api_key", return_value=True)
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
        version_id = payload["version_id"]
        lesson = lesson_manager.get_lesson(lesson_id)
        version = lesson_manager.get_review_plan_version(version_id)
        self.assertIsNotNone(lesson)
        self.assertIsNotNone(version)
        self.assertEqual(version["status"], "generating")
        self.assertEqual(version["lesson_id"], lesson_id)
        self.assertEqual(lesson["summary"], "课堂总结文本")

        mock_start_thread.assert_called_once()
        thread_kwargs = mock_start_thread.call_args.kwargs
        self.assertEqual(thread_kwargs["lesson_id"], lesson_id)
        self.assertEqual(thread_kwargs["version_id"], version_id)
        self.assertEqual(thread_kwargs["user"], {"id": 1, "organization_id": 1})
        self.assertEqual(thread_kwargs["chat_provider"], "deepseek")
        self.assertEqual(thread_kwargs["chat_model"], "deepseek-v4-pro")
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
    @patch("app.has_review_plan_api_key", return_value=True)
    def test_post_review_plan_uses_review_plan_model_override(
        self,
        _mock_has_api_key,
        _mock_ensure_credits,
        mock_start_thread,
    ):
        config_runtime.write_file_config({
            "review_plan_provider": "openai",
            "review_plan_model": "gpt-4.1",
            "review_plan_reasoning_effort": "high",
            "openai_model": "gpt-5.4",
            "openai_base_url": "https://api.iiiiitoken.com/v1",
        })

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
        version = lesson_manager.get_review_plan_version(payload["version_id"])
        self.assertIsNotNone(version)
        self.assertEqual(version["chat_provider"], "openai")
        self.assertEqual(version["chat_model"], "gpt-4.1")
        thread_kwargs = mock_start_thread.call_args.kwargs
        self.assertEqual(thread_kwargs["chat_provider"], "openai")
        self.assertEqual(thread_kwargs["chat_model"], "gpt-4.1")

    def test_settings_api_exposes_openai_base_url_and_review_plan_reasoning_effort(self):
        config_runtime.write_file_config(
            {
                "review_plan_provider": "openai",
                "review_plan_model": "gpt-5.4",
                "review_plan_reasoning_effort": "high",
                "review_plan_temperature": 0.22,
                "openai_model": "gpt-5.4",
                "openai_base_url": "https://api.iiiiitoken.com/v1",
                "review_plan_writer_temperature": 0.36,
                "review_plan_repair_temperature": 0.1,
                "review_plan_reviewer_temperature": 0.08,
            }
        )

        response = self.client.get(
            "/api/settings",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["review_plan_provider"], "openai")
        self.assertEqual(payload["review_plan_model"], "gpt-5.4")
        self.assertEqual(payload["review_plan_reasoning_effort"], "high")
        self.assertEqual(payload["review_plan_temperature"], 0.22)
        self.assertEqual(payload["review_plan_writer_temperature"], 0.36)
        self.assertEqual(payload["review_plan_repair_temperature"], 0.1)
        self.assertEqual(payload["review_plan_reviewer_temperature"], 0.08)
        self.assertEqual(payload["openai_model"], "gpt-5.4")
        self.assertEqual(payload["openai_base_url"], "https://api.iiiiitoken.com/v1")

    def test_settings_api_saves_review_plan_node_temperatures(self):
        response = self.client.post(
            "/api/settings",
            headers=self._auth_headers(self.owner_token),
            json={
                "review_plan_provider": "openai",
                "review_plan_model": "gpt-5.4",
                "review_plan_reasoning_effort": "high",
                "review_plan_temperature": "0.24",
                "review_plan_writer_provider": "deepseek",
                "review_plan_writer_model": "deepseek-v4-pro",
                "review_plan_writer_temperature": "0.37",
                "review_plan_repair_temperature": "-1",
                "review_plan_reviewer_temperature": "2.5",
            },
        )

        self.assertEqual(response.status_code, 200)
        cfg = config_runtime.get_runtime_config()
        self.assertEqual(cfg["review_plan_provider"], "openai")
        self.assertEqual(cfg["review_plan_model"], "gpt-5.4")
        self.assertEqual(cfg["review_plan_reasoning_effort"], "high")
        self.assertEqual(cfg["review_plan_temperature"], 0.24)
        self.assertEqual(cfg["review_plan_writer_provider"], "deepseek")
        self.assertEqual(cfg["review_plan_writer_model"], "deepseek-v4-pro")
        self.assertEqual(cfg["review_plan_writer_temperature"], 0.37)
        self.assertEqual(cfg["review_plan_repair_temperature"], 0.0)
        self.assertEqual(cfg["review_plan_reviewer_temperature"], 2.0)

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app.has_review_plan_api_key", return_value=True)
    @patch("ai_processor.transcribe_audio", side_effect=AssertionError("audio transcription must run in worker"))
    def test_post_audio_review_plan_returns_202_before_transcription(
        self,
        mock_transcribe_audio,
        _mock_has_api_key,
        _mock_ensure_credits,
        mock_start_thread,
    ):
        response = self.client.post(
            "/api/review-plans",
            headers=self._auth_headers(self.owner_token),
            data={
                "date": "2026-04-09",
                "subject": "数学",
                "grade": "初二",
                "topic": "一次函数",
                "weak_points": "斜率判断",
                "input_type": "audio",
                "upload_file": (io.BytesIO(b"fake audio bytes"), "lesson.m4a"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["status"], "transcribing")

        lesson = lesson_manager.get_lesson(payload["id"])
        self.assertIsNotNone(lesson)
        self.assertEqual(lesson["summary"], "")
        self.assertEqual(lesson["created_by_user_id"], 1)
        version = lesson_manager.get_review_plan_version(payload["version_id"])
        self.assertIsNotNone(version)
        self.assertEqual(version["status"], "transcribing")
        self.assertTrue(version["audio_path"])
        self.assertTrue(version["audio_request_key"])
        self.assertTrue(version["request_key"])
        self.assertTrue(version["request_id"])
        self.assertEqual(version["chat_provider"], "deepseek")
        self.assertEqual(version["chat_model"], "deepseek-v4-pro")

        mock_transcribe_audio.assert_not_called()
        mock_start_thread.assert_called_once()
        thread_kwargs = mock_start_thread.call_args.kwargs
        self.assertEqual(thread_kwargs["lesson_id"], payload["id"])
        self.assertEqual(thread_kwargs["version_id"], payload["version_id"])
        self.assertIn("audio_path", thread_kwargs)
        self.assertIn("audio_request_key", thread_kwargs)

    def test_review_plan_audio_upload_limit_covers_large_class_recordings(self):
        self.assertGreaterEqual(app_module.REVIEW_PLAN_AUDIO_MAX_BYTES, 100 * 1024 * 1024)
        self.assertEqual(app_module.REVIEW_PLAN_AUDIO_MAX_LABEL, "100MB")

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app.has_review_plan_api_key", return_value=True)
    def test_post_review_plan_merges_same_lesson_materials_into_summary(
        self,
        _mock_has_api_key,
        _mock_ensure_credits,
        _mock_start_thread,
    ):
        response = self.client.post(
            "/api/review-plans",
            headers=self._auth_headers(self.owner_token),
            json={
                "date": "2026-04-09",
                "subject": "数学",
                "grade": "高二",
                "topic": "立体几何",
                "summary_text": "第一段：翻折问题和平面化。",
                "same_lesson_materials": [
                    "第二段：线面角、点到平面距离和法向量。",
                    "第三段：高考题条件翻译和例题1到5。",
                ],
                "input_type": "text",
            },
        )

        self.assertEqual(response.status_code, 202)
        lesson = lesson_manager.get_lesson(response.get_json()["id"])
        self.assertIn("【主课堂材料】", lesson["summary"])
        self.assertIn("第一段：翻折问题和平面化。", lesson["summary"])
        self.assertIn("【同一节课补充材料 1】", lesson["summary"])
        self.assertIn("第二段：线面角、点到平面距离和法向量。", lesson["summary"])
        self.assertIn("【同一节课补充材料 2】", lesson["summary"])
        self.assertIn("第三段：高考题条件翻译和例题1到5。", lesson["summary"])

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app._current_ai_request_key", return_value="header:regenerate-review-plan")
    @patch("app.has_review_plan_api_key", return_value=True)
    def test_regenerate_review_plan_creates_new_version_without_overwriting_current(
        self,
        _mock_has_api_key,
        _mock_request_key,
        _mock_ensure_credits,
        mock_start_thread,
    ):
        config_runtime.write_file_config({
            "review_plan_provider": "openai",
            "review_plan_model": "gpt-5.4",
        })
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结文本",
            weak_points="斜率判断",
            created_by_user_id=1,
        )
        first = lesson_manager.create_review_plan_version(
            lesson_id=lesson_id,
            status="generating",
            same_lesson_materials=["补充材料"],
        )
        lesson_manager.complete_review_plan_version(
            first["id"],
            plan={"lesson_info": {"topic": "旧计划"}, "days": []},
            pdf_path="/tmp/old-review.pdf",
        )

        response = self.client.post(
            f"/api/review-plans/{lesson_id}/regenerate",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["id"], lesson_id)
        self.assertEqual(payload["status"], "generating")
        self.assertNotEqual(payload["version_id"], first["id"])

        lesson = lesson_manager.get_lesson(lesson_id)
        second = lesson_manager.get_review_plan_version(payload["version_id"])
        self.assertEqual(second["lesson_id"], lesson_id)
        self.assertEqual(lesson["current_review_plan_version_id"], first["id"])
        self.assertEqual(lesson["pdf_path"], "/tmp/old-review.pdf")
        self.assertEqual(lesson["plan"]["lesson_info"]["topic"], "旧计划")
        self.assertEqual(second["status"], "generating")
        self.assertEqual(second["chat_provider"], "openai")
        self.assertEqual(second["chat_model"], "gpt-5.4")
        self.assertTrue(second["request_id"])

        mock_start_thread.assert_called_once()
        thread_kwargs = mock_start_thread.call_args.kwargs
        self.assertEqual(thread_kwargs["lesson_id"], lesson_id)
        self.assertEqual(thread_kwargs["version_id"], second["id"])
        self.assertEqual(thread_kwargs["user"], {"id": 1, "organization_id": 1})
        self.assertEqual(thread_kwargs["chat_provider"], "openai")
        self.assertEqual(thread_kwargs["chat_model"], "gpt-5.4")
        self.assertEqual(thread_kwargs["request_key"], "header:regenerate-review-plan")
        self.assertEqual(thread_kwargs["request_id"], second["request_id"])
        self.assertEqual(thread_kwargs["same_lesson_materials"], ["补充材料"])

    def test_review_plan_list_uses_current_version_fields_and_time(self):
        first_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="第一课",
            summary="课堂总结",
            weak_points="",
            created_by_user_id=1,
        )
        first_version = lesson_manager.create_review_plan_version(lesson_id=first_id, status="generating")
        lesson_manager.complete_review_plan_version(
            first_version["id"],
            plan={"days": []},
            pdf_path="/tmp/first.pdf",
        )
        second_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-10",
            subject="数学",
            grade="初二",
            topic="第二课",
            summary="课堂总结",
            weak_points="",
            created_by_user_id=1,
        )
        second_version = lesson_manager.create_review_plan_version(lesson_id=second_id, status="generating")
        lesson_manager.complete_review_plan_version(
            second_version["id"],
            plan={"days": []},
            pdf_path="/tmp/second.pdf",
        )

        response = self.client.get(
            "/api/review-plans",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        by_id = {item["id"]: item for item in payload}
        self.assertIn(second_id, by_id)
        self.assertEqual(by_id[first_id]["current_version_id"], first_version["id"])
        self.assertEqual(by_id[first_id]["current_version_no"], 1)
        self.assertEqual(by_id[first_id]["current_status"], "ready")
        saved_first_version = lesson_manager.get_review_plan_version(first_version["id"])
        self.assertEqual(by_id[first_id]["current_generated_at"], saved_first_version["completed_at"])
        self.assertIn(
            f"/api/review-plans/{first_id}/versions/{first_version['id']}/pdf",
            by_id[first_id]["current_pdf_url"],
        )

    def test_review_plan_detail_returns_versions_newest_first(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="",
            created_by_user_id=1,
        )
        first = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(
            first["id"],
            plan={"lesson_info": {"topic": "第一版"}, "days": []},
            pdf_path="/tmp/v1.pdf",
        )
        second = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.fail_review_plan_version(second["id"], "第二版失败")

        response = self.client.get(
            f"/api/review-plans/{lesson_id}",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["current_version_id"], first["id"])
        self.assertEqual([version["id"] for version in payload["versions"]], [second["id"], first["id"]])
        self.assertEqual(payload["versions"][0]["status"], "failed")
        self.assertEqual(payload["versions"][1]["status"], "ready")

    def test_make_current_switches_to_ready_old_version(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="",
            created_by_user_id=1,
        )
        first = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(
            first["id"],
            plan={"lesson_info": {"topic": "第一版"}, "days": []},
            pdf_path="/tmp/v1.pdf",
        )
        second = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(
            second["id"],
            plan={"lesson_info": {"topic": "第二版"}, "days": []},
            pdf_path="/tmp/v2.pdf",
        )

        response = self.client.post(
            f"/api/review-plans/{lesson_id}/versions/{first['id']}/make-current",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["current_version_id"], first["id"])
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["current_review_plan_version_id"], first["id"])

    def test_version_pdf_preview_and_download_use_specific_version(self):
        requested_pdf_path = self.base / "requested-version.pdf"
        current_pdf_path = self.base / "current-version.pdf"
        requested_bytes = b"%PDF-1.4\nrequested version pdf\n%%EOF\n"
        current_bytes = b"%PDF-1.4\ncurrent version pdf\n%%EOF\n"
        requested_pdf_path.write_bytes(requested_bytes)
        current_pdf_path.write_bytes(current_bytes)
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="",
            created_by_user_id=1,
        )
        requested_version = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(
            requested_version["id"],
            plan={"lesson_info": {"topic": "请求版"}, "days": []},
            pdf_path=str(requested_pdf_path),
        )
        current_version = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(
            current_version["id"],
            plan={"lesson_info": {"topic": "当前版"}, "days": []},
            pdf_path=str(current_pdf_path),
        )
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["current_review_plan_version_id"], current_version["id"])

        preview = self.client.get(
            f"/api/review-plans/{lesson_id}/versions/{requested_version['id']}/pdf",
            headers=self._auth_headers(self.owner_token),
        )
        download = self.client.get(
            f"/api/review-plans/{lesson_id}/versions/{requested_version['id']}/download",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.mimetype, "application/pdf")
        self.assertEqual(preview.data, requested_bytes)
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download.headers.get("Content-Disposition", ""))
        self.assertEqual(download.data, requested_bytes)
        preview.close()
        download.close()

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app.has_review_plan_api_key", return_value=True)
    def test_regenerate_review_plan_rejects_in_progress_lesson(
        self,
        _mock_has_api_key,
        _mock_ensure_credits,
        mock_start_thread,
    ):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结文本",
            weak_points="斜率判断",
            record_status="generating",
            created_by_user_id=1,
        )

        response = self.client.post(
            f"/api/review-plans/{lesson_id}/regenerate",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("正在生成中", response.get_json()["error"])
        mock_start_thread.assert_not_called()

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app.has_review_plan_api_key", return_value=True)
    def test_regenerate_review_plan_requires_existing_summary(
        self,
        _mock_has_api_key,
        _mock_ensure_credits,
        mock_start_thread,
    ):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="",
            weak_points="斜率判断",
            record_status="failed",
            created_by_user_id=1,
        )

        response = self.client.post(
            f"/api/review-plans/{lesson_id}/regenerate",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("缺少课堂内容", response.get_json()["error"])
        mock_start_thread.assert_not_called()

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available", side_effect=app_module.CreditBalanceError("积分不足，请先充值"))
    @patch("app.has_review_plan_api_key", return_value=True)
    def test_regenerate_review_plan_keeps_old_status_when_credits_are_insufficient(
        self,
        _mock_has_api_key,
        _mock_ensure_credits,
        mock_start_thread,
    ):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结文本",
            weak_points="斜率判断",
            pdf_path="/tmp/old-review.pdf",
            record_status="ready",
            created_by_user_id=1,
        )

        response = self.client.post(
            f"/api/review-plans/{lesson_id}/regenerate",
            headers=self._auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.get_json()["error"], "积分不足，请先充值")
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["record_status"], "ready")
        self.assertEqual(lesson["pdf_path"], "/tmp/old-review.pdf")
        mock_start_thread.assert_not_called()

    @patch("review_plan_templates.single_lesson_pdf.generate_single_lesson_pdf")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app._current_ai_request_key", return_value="header:processed-review-plan")
    @patch("app.has_review_plan_api_key", return_value=True)
    def test_post_review_plan_returns_existing_lesson_for_processed_duplicate(
        self,
        _mock_has_api_key,
        _mock_request_key,
        _mock_ensure_credits,
        mock_start_thread,
        mock_generate_plan_json,
        _mock_generate_pdf,
    ):
        expected_plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        mock_generate_plan_json.return_value = (
            expected_plan,
            {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "input_tokens": 120,
                "output_tokens": 40,
            },
        )
        credit_manager.apply_manual_adjustment(
            organization_id=1,
            actor_user_id=1,
            amount=40,
            note="seed duplicate retry credits",
        )
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
        self.assertEqual(first.status_code, 202)
        lesson_id = first.get_json()["id"]
        app_module._run_review_plan_generation_job(**mock_start_thread.call_args.kwargs)

        second = self.client.post(
            "/api/review-plans",
            headers=self._auth_headers(self.owner_token),
            json=payload,
        )

        self.assertEqual(second.status_code, 202)
        second_payload = second.get_json()
        self.assertEqual(second_payload["id"], lesson_id)
        self.assertTrue(second_payload["duplicate"])
        self.assertEqual(second_payload["status"], "ready")
        self.assertEqual(mock_start_thread.call_count, 1)

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app._current_ai_request_key", return_value="header:duplicate-review-plan")
    @patch("app.has_review_plan_api_key", return_value=True)
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
    @patch("app.has_review_plan_api_key", return_value=True)
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
    @patch("app.has_review_plan_api_key", return_value=True)
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
    @patch("app.has_review_plan_api_key", return_value=True)
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
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("app._run_ai_feature_with_charge")
    def test_worker_uses_lesson_data_source_of_truth(
        self,
        mock_run_with_charge,
        mock_generate_plan_json,
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

        expected_plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        mock_run_with_charge.side_effect = lambda **kwargs: kwargs["producer"]()
        mock_generate_plan_json.return_value = (
            expected_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 1, "output_tokens": 1},
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
        self.assertEqual(saved["plan"]["lesson_info"]["topic"], expected_plan["lesson_info"]["topic"])
        self.assertEqual(saved["plan"]["lesson_info"]["grade"], expected_plan["lesson_info"]["grade"])
        self.assertEqual(saved["plan"]["lesson_info"]["date"], "2026-04-09")
        self.assertEqual(len(saved["plan"]["days"]), len(expected_plan["days"]))
        self.assertEqual(mock_run_with_charge.call_args.kwargs["source_record_id"], lesson_id)
        mock_generate_plan_json.assert_called_once()
        generation_kwargs = mock_generate_plan_json.call_args.kwargs
        self.assertEqual(generation_kwargs["provider"], "deepseek")
        self.assertEqual(generation_kwargs["model"], "deepseek-v4-pro")
        self.assertIn("课堂总结文本", generation_kwargs["user_message"])
        self.assertIn("本节课主题：一次函数", generation_kwargs["user_message"])
        mock_generate_pdf.assert_called_once()

    @patch("review_plan_templates.single_lesson_pdf.generate_single_lesson_pdf")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_worker_only_processes_pending_lessons(
        self,
        mock_generate_plan_json,
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
        mock_generate_plan_json.assert_not_called()
        mock_generate_pdf.assert_not_called()

    @patch("app._start_review_plan_generation_thread")
    def test_startup_recovery_requeues_interrupted_audio_review_plan(self, mock_start_thread):
        audio_path = self.base / "lesson.m4a"
        audio_path.write_bytes(b"audio")
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="",
            weak_points="斜率判断",
            class_id=0,
            record_status="transcribing",
            created_by_user_id=1,
            review_audio_path=str(audio_path),
            review_audio_request_key="audio-key",
            review_request_key="request-key",
            review_request_id="request-id",
            review_chat_provider="deepseek",
            review_chat_model="deepseek-v4-flash",
            review_same_lesson_materials=["补充材料"],
        )

        recovered = app_module._recover_interrupted_review_plan_jobs()

        self.assertEqual(recovered, 1)
        mock_start_thread.assert_called_once()
        thread_kwargs = mock_start_thread.call_args.kwargs
        self.assertEqual(thread_kwargs["lesson_id"], lesson_id)
        self.assertEqual(thread_kwargs["user"], {"id": 1, "organization_id": 1})
        self.assertEqual(thread_kwargs["chat_provider"], "deepseek")
        self.assertEqual(thread_kwargs["chat_model"], "deepseek-v4-flash")
        self.assertEqual(thread_kwargs["request_key"], "request-key")
        self.assertEqual(thread_kwargs["request_id"], "request-id")
        self.assertEqual(thread_kwargs["audio_path"], str(audio_path))
        self.assertEqual(thread_kwargs["audio_request_key"], "audio-key")
        self.assertEqual(thread_kwargs["same_lesson_materials"], ["补充材料"])
        self.assertIn("request-id", app_module._AI_REQUEST_IN_FLIGHT)

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
