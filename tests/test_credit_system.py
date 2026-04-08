import gc
import io
import sqlite3
import sys
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import credit_manager
import lesson_manager
import app as app_module
import xhs_open_platform


class CreditSystemServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.owner, _ = lesson_manager.authenticate_user("Kayn", "xingrun2026")
        if hasattr(app_module, "_AI_REQUEST_IN_FLIGHT"):
            app_module._AI_REQUEST_IN_FLIGHT.clear()
        if hasattr(app_module, "_AI_ORGANIZATION_IN_FLIGHT"):
            app_module._AI_ORGANIZATION_IN_FLIGHT.clear()

    def tearDown(self):
        if hasattr(app_module, "_AI_REQUEST_IN_FLIGHT"):
            app_module._AI_REQUEST_IN_FLIGHT.clear()
        if hasattr(app_module, "_AI_ORGANIZATION_IN_FLIGHT"):
            app_module._AI_ORGANIZATION_IN_FLIGHT.clear()
        gc.collect()
        self.temp_dir.cleanup()

    def _create_secondary_owner(self) -> dict:
        request = lesson_manager.create_organization_request(
            organization_name="Org Integrity Secondary",
            username="secondary_owner",
            display_name="Secondary Owner",
            password="secret123",
        )
        approved, _invite = lesson_manager.approve_organization_request(request["id"], self.owner["id"])
        return approved

    def test_credit_account_is_created_and_tracks_manual_credit_then_debit(self):
        overview = credit_manager.get_credit_overview(self.owner["organization_id"])
        self.assertEqual(overview["credit_balance"], 0)

        credit_manager.apply_manual_adjustment(
            organization_id=self.owner["organization_id"],
            actor_user_id=self.owner["id"],
            amount=120,
            note="seed credits for test",
        )
        credit_manager.apply_manual_adjustment(
            organization_id=self.owner["organization_id"],
            actor_user_id=self.owner["id"],
            amount=-20,
            note="manual debit for correction",
        )

        updated = credit_manager.get_credit_overview(self.owner["organization_id"])
        self.assertEqual(updated["credit_balance"], 100)
        self.assertEqual(updated["total_recharged"], 120)
        self.assertEqual(updated["total_consumed"], 20)

    def test_member_usage_summary_groups_by_user(self):
        member = lesson_manager.create_registration_request(
            username="member_credit",
            display_name="Credit Member",
            password="secret123",
            organization_name=self.owner["organization_name"],
        )
        approved = lesson_manager.approve_registration_request(member["id"], self.owner["id"])

        credit_manager.apply_manual_adjustment(
            organization_id=self.owner["organization_id"],
            actor_user_id=self.owner["id"],
            amount=100,
            note="seed balance",
        )
        credit_manager.record_ai_charge(
            organization_id=self.owner["organization_id"],
            user_id=approved["id"],
            feature_key="teacher_feedback_draft",
            provider="openai",
            model="gpt-4o",
            input_tokens=80,
            output_tokens=20,
            credit_cost_final=5,
            source_record_type="lesson",
            source_record_id=12,
            request_id="req-member-usage",
        )

        summary = credit_manager.list_member_usage_summary(self.owner["organization_id"])
        self.assertEqual(summary[0]["user_id"], approved["id"])
        self.assertEqual(summary[0]["credit_consumed"], 5)
        self.assertEqual(summary[0]["usage_count"], 1)

    def test_insufficient_balance_rolls_back_ai_usage_row(self):
        with self.assertRaises(ValueError):
            credit_manager.record_ai_charge(
                organization_id=self.owner["organization_id"],
                user_id=self.owner["id"],
                feature_key="consultation_ai_parse",
                provider="openai",
                model="gpt-4o",
                input_tokens=40,
                output_tokens=10,
                credit_cost_final=5,
                source_record_type="consultation_batch",
                source_record_id=99,
                request_id="req-insufficient-balance",
            )

        with lesson_manager.get_conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM ai_usage_ledger
                WHERE organization_id=? AND request_id=?
                """,
                (self.owner["organization_id"], "req-insufficient-balance"),
            ).fetchone()
        self.assertEqual(row["total"], 0)

    def test_cross_organization_user_and_operator_writes_are_rejected(self):
        secondary_owner = self._create_secondary_owner()

        with self.assertRaises(ValueError):
            credit_manager.apply_manual_adjustment(
                organization_id=self.owner["organization_id"],
                actor_user_id=secondary_owner["id"],
                amount=20,
                note="foreign operator should fail",
            )

        credit_manager.apply_manual_adjustment(
            organization_id=self.owner["organization_id"],
            actor_user_id=self.owner["id"],
            amount=30,
            note="seed balance",
        )

        with self.assertRaises(ValueError):
            credit_manager.record_ai_charge(
                organization_id=self.owner["organization_id"],
                user_id=secondary_owner["id"],
                feature_key="consultation_ai_parse",
                provider="openai",
                model="gpt-4o",
                input_tokens=80,
                output_tokens=20,
                credit_cost_final=6,
                source_record_type="consultation_batch",
                source_record_id=41,
                request_id="req-cross-org",
            )

        overview = credit_manager.get_credit_overview(self.owner["organization_id"])
        self.assertEqual(overview["credit_balance"], 30)
        self.assertEqual(overview["total_recharged"], 30)
        self.assertEqual(overview["total_consumed"], 0)

    def test_duplicate_request_id_is_idempotent_for_ai_charge(self):
        credit_manager.apply_manual_adjustment(
            organization_id=self.owner["organization_id"],
            actor_user_id=self.owner["id"],
            amount=50,
            note="seed balance for idempotency",
        )

        first = credit_manager.record_ai_charge(
            organization_id=self.owner["organization_id"],
            user_id=self.owner["id"],
            feature_key="teacher_feedback_draft",
            provider="openai",
            model="gpt-4o",
            input_tokens=70,
            output_tokens=30,
            credit_cost_final=5,
            source_record_type="lesson",
            source_record_id=66,
            request_id="req-idempotent-charge",
        )
        second = credit_manager.record_ai_charge(
            organization_id=self.owner["organization_id"],
            user_id=self.owner["id"],
            feature_key="teacher_feedback_draft",
            provider="openai",
            model="gpt-4o",
            input_tokens=70,
            output_tokens=30,
            credit_cost_final=5,
            source_record_type="lesson",
            source_record_id=66,
            request_id="req-idempotent-charge",
        )

        self.assertEqual(first["id"], second["id"])
        overview = credit_manager.get_credit_overview(self.owner["organization_id"])
        self.assertEqual(overview["credit_balance"], 45)
        self.assertEqual(overview["total_consumed"], 5)

        with lesson_manager.get_conn() as conn:
            usage_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM ai_usage_ledger
                WHERE organization_id=? AND request_id=?
                """,
                (self.owner["organization_id"], "req-idempotent-charge"),
            ).fetchone()
        self.assertEqual(usage_count["total"], 1)

    def test_duplicate_request_id_race_loser_returns_existing_row(self):
        credit_manager.apply_manual_adjustment(
            organization_id=self.owner["organization_id"],
            actor_user_id=self.owner["id"],
            amount=50,
            note="seed balance for race idempotency",
        )

        original_insert = lesson_manager._insert_ai_usage_row_with_conn
        inserted: dict[str, int] = {}

        def race_loser_insert(conn, **kwargs):
            row = original_insert(conn, **kwargs)
            inserted["id"] = row["id"]
            lesson_manager._insert_credit_ledger_entry_with_conn(
                conn,
                organization_id=self.owner["organization_id"],
                direction="debit",
                amount=5,
                source_type="ai_usage",
                source_id=str(row["id"]),
                note="teacher_feedback_draft",
                operator_user_id=self.owner["id"],
            )
            raise sqlite3.IntegrityError(
                "UNIQUE constraint failed: ai_usage_ledger.organization_id, ai_usage_ledger.request_id"
            )

        with patch("lesson_manager._insert_ai_usage_row_with_conn", side_effect=race_loser_insert):
            result = credit_manager.record_ai_charge(
                organization_id=self.owner["organization_id"],
                user_id=self.owner["id"],
                feature_key="teacher_feedback_draft",
                provider="openai",
                model="gpt-4o",
                input_tokens=60,
                output_tokens=20,
                credit_cost_final=5,
                source_record_type="lesson",
                source_record_id=77,
                request_id="req-concurrent-idempotent",
            )

        self.assertEqual(result["id"], inserted["id"])

        with lesson_manager.get_conn() as conn:
            usage_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM ai_usage_ledger
                WHERE organization_id=? AND request_id=?
                """,
                (self.owner["organization_id"], "req-concurrent-idempotent"),
            ).fetchone()
            debit_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM organization_credit_ledger
                WHERE organization_id=? AND source_type='ai_usage' AND note=?
                """,
                (self.owner["organization_id"], "teacher_feedback_draft"),
            ).fetchone()
        self.assertEqual(usage_count["total"], 1)
        self.assertEqual(debit_count["total"], 1)

    def test_claim_ai_request_identity_blocks_inflight_and_completed_duplicates(self):
        credit_manager.apply_manual_adjustment(
            organization_id=self.owner["organization_id"],
            actor_user_id=self.owner["id"],
            amount=50,
            note="seed balance for request identity claim",
        )
        request_id = "req-claim-idempotency"
        app_module._AI_REQUEST_IN_FLIGHT.clear()

        try:
            app_module._claim_ai_request_identity(
                organization_id=self.owner["organization_id"],
                request_id=request_id,
            )
            with self.assertRaises(app_module.DuplicateAiRequestError):
                app_module._claim_ai_request_identity(
                    organization_id=self.owner["organization_id"],
                    request_id=request_id,
                )

            app_module._release_ai_request_identity(request_id)

            credit_manager.record_ai_charge(
                organization_id=self.owner["organization_id"],
                user_id=self.owner["id"],
                feature_key="teacher_feedback_draft",
                provider="openai",
                model="gpt-4o",
                input_tokens=70,
                output_tokens=30,
                credit_cost_final=5,
                source_record_type="lesson",
                source_record_id=88,
                request_id=request_id,
            )

            with self.assertRaises(app_module.DuplicateAiRequestError):
                app_module._claim_ai_request_identity(
                    organization_id=self.owner["organization_id"],
                    request_id=request_id,
                )
        finally:
            app_module._release_ai_request_identity(request_id)
            app_module._AI_REQUEST_IN_FLIGHT.clear()


class CreditSystemApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app_module.app.test_client()
        login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(login.status_code, 200)
        payload = login.get_json()
        self.assertIsNotNone(payload)
        self.owner_token = payload["token"]
        self.owner_user = payload["user"]
        if hasattr(app_module, "_CREDIT_REDEEM_FAILURE_STATE"):
            app_module._CREDIT_REDEEM_FAILURE_STATE.clear()
        if hasattr(app_module, "_AI_REQUEST_IN_FLIGHT"):
            app_module._AI_REQUEST_IN_FLIGHT.clear()
        if hasattr(app_module, "_AI_ORGANIZATION_IN_FLIGHT"):
            app_module._AI_ORGANIZATION_IN_FLIGHT.clear()

    def tearDown(self):
        if hasattr(app_module, "_AI_REQUEST_IN_FLIGHT"):
            app_module._AI_REQUEST_IN_FLIGHT.clear()
        if hasattr(app_module, "_AI_ORGANIZATION_IN_FLIGHT"):
            app_module._AI_ORGANIZATION_IN_FLIGHT.clear()
        gc.collect()
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def _create_member_token(self) -> str:
        submit = self.client.post(
            "/api/register-request",
            json={
                "username": "member_credit_api",
                "display_name": "Member Credit Api",
                "password": "secret123",
                "organization_name": self.owner_user["organization_name"],
            },
        )
        self.assertEqual(submit.status_code, 201)

        pending = self.client.get(
            "/api/admin/registration-requests",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(pending.status_code, 200)
        pending_payload = pending.get_json()
        self.assertIsNotNone(pending_payload)
        request_id = None
        for item in pending_payload["items"]:
            if item["username"] == "member_credit_api":
                request_id = item["id"]
                break
        self.assertIsNotNone(request_id)

        approve = self.client.post(
            f"/api/admin/registration-requests/{request_id}/approve",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(approve.status_code, 200)

        login = self.client.post(
            "/api/login",
            json={"username": "member_credit_api", "password": "secret123"},
        )
        self.assertEqual(login.status_code, 200)
        login_payload = login.get_json()
        self.assertIsNotNone(login_payload)
        return login_payload["token"]

    @patch("app.fetch_xhs_order_for_redemption")
    def test_owner_can_redeem_paid_xhs_order_once(self, mock_fetch):
        mock_fetch.return_value = {
            "platform_order_id": "XHS-1001",
            "product_id": "sku-credit-300",
            "sku_id": "sku-credit-300",
            "product_name": "300 points pack",
            "paid_amount": 9900,
            "currency": "CNY",
            "buyer_masked_phone": "13800001234",
            "order_status": "paid",
            "credit_amount": 300,
            "raw_order_payload": {"status": "paid"},
        }

        redeem = self.client.post(
            "/api/credits/redeem/xhs",
            headers=self.auth_headers(self.owner_token),
            json={"platform_order_id": "XHS-1001", "phone_suffix": "1234"},
        )
        self.assertEqual(redeem.status_code, 200)
        payload = redeem.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["overview"]["credit_balance"], 300)

        duplicate = self.client.post(
            "/api/credits/redeem/xhs",
            headers=self.auth_headers(self.owner_token),
            json={"platform_order_id": "XHS-1001", "phone_suffix": "1234"},
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_redeem_requires_platform_order_and_phone_suffix(self):
        invalid_order = self.client.post(
            "/api/credits/redeem/xhs",
            headers=self.auth_headers(self.owner_token),
            json={"platform_order_id": "", "phone_suffix": "1234"},
        )
        invalid_suffix = self.client.post(
            "/api/credits/redeem/xhs",
            headers=self.auth_headers(self.owner_token),
            json={"platform_order_id": "XHS-REQ", "phone_suffix": "12"},
        )

        self.assertEqual(invalid_order.status_code, 400)
        self.assertEqual(invalid_suffix.status_code, 400)

    @patch("app.fetch_xhs_order_for_redemption")
    def test_redeem_verification_failures_are_normalized_and_throttled_per_owner_and_order(self, mock_fetch):
        mock_fetch.side_effect = [
            ValueError("order not found"),
            ValueError("order verification does not match phone suffix"),
            ValueError("order is not paid"),
            ValueError("order not found"),
        ]

        responses = []
        for _ in range(4):
            responses.append(
                self.client.post(
                    "/api/credits/redeem/xhs",
                    headers=self.auth_headers(self.owner_token),
                    json={"platform_order_id": "XHS-BRUTE-1", "phone_suffix": "9999"},
                )
            )

        self.assertEqual(responses[0].status_code, 422)
        self.assertEqual(responses[1].status_code, 422)
        self.assertEqual(responses[2].status_code, 422)
        self.assertEqual(responses[3].status_code, 429)
        self.assertEqual(responses[0].get_json()["error"], responses[1].get_json()["error"])
        self.assertEqual(responses[1].get_json()["error"], responses[2].get_json()["error"])

        other_order = self.client.post(
            "/api/credits/redeem/xhs",
            headers=self.auth_headers(self.owner_token),
            json={"platform_order_id": "XHS-BRUTE-2", "phone_suffix": "9999"},
        )
        self.assertEqual(other_order.status_code, 422)

    def test_credit_routes_require_owner_access(self):
        member_token = self._create_member_token()
        routes = [
            ("get", "/api/credits/overview", None),
            ("get", "/api/credits/ledger", None),
            ("get", "/api/credits/member-usage", None),
            ("get", "/api/credits/member-usage/1", None),
            ("post", "/api/credits/redeem/xhs", {"platform_order_id": "XHS-401", "phone_suffix": "1234"}),
        ]
        for method, route, body in routes:
            response = self.client.open(
                route,
                method=method.upper(),
                headers=self.auth_headers(member_token),
                json=body,
            )
            self.assertEqual(response.status_code, 403, route)

    @patch("app.parse_consultation_batch_text")
    def test_consultation_ai_parse_blocks_when_balance_is_insufficient(self, mock_parse):
        response = self.client.post(
            "/api/consultations/ai-parse",
            headers=self.auth_headers(self.owner_token),
            json={"raw_text": "张妈妈，五年级数学"},
        )

        self.assertEqual(response.status_code, 402)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertIn("积分不足", payload["error"])
        mock_parse.assert_not_called()

    @patch("app.generate_teacher_feedback_draft")
    def test_teacher_feedback_draft_records_ai_usage_and_deducts_balance(self, mock_feedback):
        credit_manager.apply_manual_adjustment(
            organization_id=self.owner_user["organization_id"],
            actor_user_id=self.owner_user["id"],
            amount=30,
            note="seed draft credits",
        )
        mock_feedback.return_value = (
            "反馈草稿",
            {
                "provider": "openai",
                "model": "gpt-4o",
                "input_tokens": 220,
                "output_tokens": 80,
            },
        )

        lesson_id = lesson_manager.save_lesson(
            date_str="2026-04-02",
            subject="数学",
            grade="五年级",
            topic="分数应用题",
            summary="课堂总结",
            weak_points="计算",
            plan={"days": [], "questions": []},
            pdf_path="",
            class_id=None,
        )

        response = self.client.post(
            f"/api/review-plans/{lesson_id}/feedback/draft",
            headers=self.auth_headers(self.owner_token),
            json={
                "students": [
                    {
                        "name": "王同学",
                        "selected_template_id": "active",
                        "remark": "认真参与课堂练习",
                    }
                ],
                "custom_templates": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["merged_text"], "反馈草稿")

        overview = self.client.get(
            "/api/credits/overview",
            headers=self.auth_headers(self.owner_token),
        ).get_json()
        ledger = self.client.get(
            "/api/credits/ledger",
            headers=self.auth_headers(self.owner_token),
        ).get_json()["items"]

        self.assertEqual(overview["credit_balance"], 28)
        self.assertEqual(ledger[0]["source_type"], "ai_usage")
        self.assertEqual(ledger[0]["note"], "teacher_feedback_draft")

    @patch("app.parse_consultation_batch_text")
    def test_consultation_ai_parse_duplicate_idempotency_header_skips_second_ai_call_and_charge(self, mock_parse):
        credit_manager.apply_manual_adjustment(
            organization_id=self.owner_user["organization_id"],
            actor_user_id=self.owner_user["id"],
            amount=20,
            note="seed parse credits",
        )
        mock_parse.return_value = (
            {"items": [], "warnings": []},
            {
                "provider": "openai",
                "model": "gpt-4o",
                "input_tokens": 120,
                "output_tokens": 40,
            },
        )
        headers = {
            **self.auth_headers(self.owner_token),
            "Idempotency-Key": "parse-dup-1",
        }

        first = self.client.post(
            "/api/consultations/ai-parse",
            headers=headers,
            json={"raw_text": "张妈妈，五年级数学"},
        )
        second = self.client.post(
            "/api/consultations/ai-parse",
            headers=headers,
            json={"raw_text": "张妈妈，五年级数学"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn("重复请求", second.get_json()["error"])
        self.assertEqual(mock_parse.call_count, 1)

        overview = self.client.get(
            "/api/credits/overview",
            headers=self.auth_headers(self.owner_token),
        ).get_json()
        self.assertEqual(overview["credit_balance"], 17)

        with lesson_manager.get_conn() as conn:
            usage_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM ai_usage_ledger
                WHERE organization_id=? AND feature_key='consultation_ai_parse'
                """,
                (self.owner_user["organization_id"],),
            ).fetchone()
        self.assertEqual(usage_count["total"], 1)

    @patch("app._ai_fallback_request_bucket", return_value=12345)
    @patch("app.parse_consultation_batch_text")
    def test_consultation_ai_parse_fallback_request_identity_skips_immediate_retry_and_charge(
        self,
        mock_parse,
        _mock_bucket,
    ):
        credit_manager.apply_manual_adjustment(
            organization_id=self.owner_user["organization_id"],
            actor_user_id=self.owner_user["id"],
            amount=20,
            note="seed fallback parse credits",
        )
        mock_parse.return_value = (
            {"items": [], "warnings": []},
            {
                "provider": "openai",
                "model": "gpt-4o",
                "input_tokens": 90,
                "output_tokens": 30,
            },
        )

        first = self.client.post(
            "/api/consultations/ai-parse",
            headers=self.auth_headers(self.owner_token),
            json={"raw_text": "李妈妈，四年级英语"},
        )
        second = self.client.post(
            "/api/consultations/ai-parse",
            headers=self.auth_headers(self.owner_token),
            json={"raw_text": "李妈妈，四年级英语"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn("重复请求", second.get_json()["error"])
        self.assertEqual(mock_parse.call_count, 1)

        overview = self.client.get(
            "/api/credits/overview",
            headers=self.auth_headers(self.owner_token),
        ).get_json()
        self.assertEqual(overview["credit_balance"], 17)

        with lesson_manager.get_conn() as conn:
            usage_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM ai_usage_ledger
                WHERE organization_id=? AND feature_key='consultation_ai_parse'
                """,
                (self.owner_user["organization_id"],),
            ).fetchone()
        self.assertEqual(usage_count["total"], 1)

    @patch("app.datetime")
    @patch("app._ai_fallback_request_bucket", side_effect=[12345, 54321])
    @patch("app.has_api_key", return_value=True)
    @patch("ai_processor.parse_and_generate_plan")
    @patch("ai_processor.transcribe_audio")
    def test_audio_upload_retry_uses_stable_identity_and_skips_second_transcription_charge(
        self,
        mock_transcribe,
        mock_generate_plan,
        _mock_has_api_key,
        _mock_bucket,
        mock_datetime,
    ):
        credit_manager.apply_manual_adjustment(
            organization_id=self.owner_user["organization_id"],
            actor_user_id=self.owner_user["id"],
            amount=40,
            note="seed audio retry credits",
        )
        mock_datetime.now.side_effect = [
            datetime(2026, 4, 3, 10, 0, 0),
            datetime(2026, 4, 3, 10, 0, 1),
        ]
        mock_transcribe.return_value = (
            "课堂录音整理",
            {
                "provider": "openai",
                "model": "whisper-1",
                "input_tokens": 0,
                "output_tokens": 0,
            },
        )
        mock_generate_plan.return_value = (
            {"days": [], "questions": []},
            {
                "provider": "openai",
                "model": "gpt-4o",
                "input_tokens": 120,
                "output_tokens": 40,
            },
        )

        def post_audio_retry():
            return self.client.post(
                "/api/review-plans",
                headers=self.auth_headers(self.owner_token),
                data={
                    "date": "2026-04-03",
                    "subject": "数学",
                    "grade": "五年级",
                    "topic": "方程",
                    "input_type": "audio",
                    "upload_file": (io.BytesIO(b"same-audio-upload"), "lesson.m4a"),
                },
                content_type="multipart/form-data",
            )

        first = post_audio_retry()
        second = post_audio_retry()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)
        self.assertIn("重复请求", second.get_json()["error"])
        self.assertEqual(mock_transcribe.call_count, 1)

        overview = self.client.get(
            "/api/credits/overview",
            headers=self.auth_headers(self.owner_token),
        ).get_json()
        self.assertEqual(overview["credit_balance"], 28)

        with lesson_manager.get_conn() as conn:
            audio_usage_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM ai_usage_ledger
                WHERE organization_id=? AND feature_key='audio_transcription'
                """,
                (self.owner_user["organization_id"],),
            ).fetchone()
            total_usage_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM ai_usage_ledger
                WHERE organization_id=?
                """,
                (self.owner_user["organization_id"],),
            ).fetchone()
        self.assertEqual(audio_usage_count["total"], 1)
        self.assertEqual(total_usage_count["total"], 2)

    @patch("app.datetime")
    @patch("app.has_api_key", return_value=True)
    @patch("ai_processor.parse_and_generate_plan")
    @patch("ai_processor.transcribe_audio")
    def test_audio_uploads_with_same_metadata_but_different_content_do_not_collide(
        self,
        mock_transcribe,
        mock_generate_plan,
        _mock_has_api_key,
        mock_datetime,
    ):
        credit_manager.apply_manual_adjustment(
            organization_id=self.owner_user["organization_id"],
            actor_user_id=self.owner_user["id"],
            amount=40,
            note="seed distinct audio upload credits",
        )
        mock_datetime.now.side_effect = [
            datetime(2026, 4, 3, 11, 0, 0),
            datetime(2026, 4, 3, 11, 0, 1),
        ]
        mock_transcribe.side_effect = [
            (
                "课堂录音整理 A",
                {
                    "provider": "openai",
                    "model": "whisper-1",
                    "input_tokens": 0,
                    "output_tokens": 0,
                },
            ),
            (
                "课堂录音整理 B",
                {
                    "provider": "openai",
                    "model": "whisper-1",
                    "input_tokens": 0,
                    "output_tokens": 0,
                },
            ),
        ]
        mock_generate_plan.return_value = (
            {"days": [], "questions": []},
            {
                "provider": "openai",
                "model": "gpt-4o",
                "input_tokens": 120,
                "output_tokens": 40,
            },
        )

        def post_audio_upload(audio_bytes: bytes):
            return self.client.post(
                "/api/review-plans",
                headers=self.auth_headers(self.owner_token),
                data={
                    "date": "2026-04-03",
                    "subject": "数学",
                    "grade": "五年级",
                    "topic": "方程",
                    "input_type": "audio",
                    "upload_file": (io.BytesIO(audio_bytes), "lesson.m4a"),
                },
                content_type="multipart/form-data",
            )

        first = post_audio_upload(b"audio-file-aa")
        second = post_audio_upload(b"audio-file-bb")

        self.assertEqual(len(b"audio-file-aa"), len(b"audio-file-bb"))
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(mock_transcribe.call_count, 2)

        overview = self.client.get(
            "/api/credits/overview",
            headers=self.auth_headers(self.owner_token),
        ).get_json()
        self.assertEqual(overview["credit_balance"], 16)

        with lesson_manager.get_conn() as conn:
            audio_usage_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM ai_usage_ledger
                WHERE organization_id=? AND feature_key='audio_transcription'
                """,
                (self.owner_user["organization_id"],),
            ).fetchone()
        self.assertEqual(audio_usage_count["total"], 2)

    @patch("app.has_api_key", return_value=True)
    @patch("pdf_engine.generate_monthly_pdf")
    @patch("ai_processor.generate_monthly_plan")
    def test_monthly_generate_pdf_failure_does_not_charge_and_retry_can_succeed(
        self,
        mock_generate_plan,
        mock_generate_pdf,
        _mock_has_api_key,
    ):
        credit_manager.apply_manual_adjustment(
            organization_id=self.owner_user["organization_id"],
            actor_user_id=self.owner_user["id"],
            amount=20,
            note="seed monthly retry credits",
        )
        lesson_manager.save_lesson(
            date_str="2026-04-08",
            subject="数学",
            grade="五年级",
            topic="分数",
            summary="课堂总结",
            weak_points="计算",
            plan={"days": [], "questions": []},
            pdf_path="",
            class_id=None,
        )
        mock_generate_plan.return_value = (
            {"days": [{"day": 1, "tasks": ["复习"]}], "questions": []},
            {
                "provider": "openai",
                "model": "gpt-4o",
                "input_tokens": 300,
                "output_tokens": 120,
            },
        )
        mock_generate_pdf.side_effect = [RuntimeError("pdf failed"), None]
        headers = {
            **self.auth_headers(self.owner_token),
            "Idempotency-Key": "monthly-pdf-retry",
        }

        first = self.client.post(
            "/api/monthly/generate",
            headers=headers,
            json={"month": "2026-04"},
        )

        self.assertEqual(first.status_code, 500)
        self.assertIn("pdf failed", first.get_json()["error"])

        overview_after_failure = self.client.get(
            "/api/credits/overview",
            headers=self.auth_headers(self.owner_token),
        ).get_json()
        self.assertEqual(overview_after_failure["credit_balance"], 20)

        with lesson_manager.get_conn() as conn:
            failed_usage_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM ai_usage_ledger
                WHERE organization_id=? AND feature_key='monthly_plan_generate'
                """,
                (self.owner_user["organization_id"],),
            ).fetchone()
        self.assertEqual(failed_usage_count["total"], 0)

        second = self.client.post(
            "/api/monthly/generate",
            headers=headers,
            json={"month": "2026-04"},
        )

        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.get_json()["ok"])
        self.assertEqual(mock_generate_plan.call_count, 2)
        self.assertEqual(mock_generate_pdf.call_count, 2)

        overview_after_success = self.client.get(
            "/api/credits/overview",
            headers=self.auth_headers(self.owner_token),
        ).get_json()
        self.assertEqual(overview_after_success["credit_balance"], 10)

        with lesson_manager.get_conn() as conn:
            success_usage_count = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM ai_usage_ledger
                WHERE organization_id=? AND feature_key='monthly_plan_generate'
                """,
                (self.owner_user["organization_id"],),
            ).fetchone()
        self.assertEqual(success_usage_count["total"], 1)

    @patch("app.parse_consultation_batch_text")
    def test_same_org_concurrent_ai_request_is_rejected_while_first_is_in_flight(self, mock_parse):
        credit_manager.apply_manual_adjustment(
            organization_id=self.owner_user["organization_id"],
            actor_user_id=self.owner_user["id"],
            amount=20,
            note="seed concurrent ai credits",
        )
        first_call_entered = threading.Event()
        release_first_call = threading.Event()

        def slow_parse(*_args, **_kwargs):
            if not first_call_entered.is_set():
                first_call_entered.set()
                release_first_call.wait(timeout=1.0)
            return (
                {"items": [], "warnings": []},
                {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "input_tokens": 90,
                    "output_tokens": 30,
                },
            )

        mock_parse.side_effect = slow_parse
        first_response: dict[str, object] = {}

        def run_first_request():
            with app_module.app.test_client() as client:
                first_response["response"] = client.post(
                    "/api/consultations/ai-parse",
                    headers={
                        **self.auth_headers(self.owner_token),
                        "Idempotency-Key": "concurrent-parse-1",
                    },
                    json={"raw_text": "张妈妈，五年级数学"},
                )

        first_thread = threading.Thread(target=run_first_request)
        first_thread.start()
        self.assertTrue(first_call_entered.wait(timeout=1.0))

        second = self.client.post(
            "/api/consultations/ai-parse",
            headers={
                **self.auth_headers(self.owner_token),
                "Idempotency-Key": "concurrent-parse-2",
            },
            json={"raw_text": "李妈妈，六年级英语"},
        )

        release_first_call.set()
        first_thread.join(timeout=1.0)

        self.assertIn("response", first_response)
        self.assertEqual(first_response["response"].status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn("机构", second.get_json()["error"])
        self.assertEqual(mock_parse.call_count, 1)

    @patch("ai_processor.parse_and_generate_plan")
    @patch("app.has_api_key", return_value=True)
    def test_lesson_generation_blocks_when_balance_cannot_cover_max_configured_charge(
        self,
        _mock_has_api_key,
        mock_generate_plan,
    ):
        credit_manager.apply_manual_adjustment(
            organization_id=self.owner_user["organization_id"],
            actor_user_id=self.owner_user["id"],
            amount=8,
            note="seed only base lesson credits",
        )

        response = self.client.post(
            "/api/review-plans",
            headers=self.auth_headers(self.owner_token),
            json={
                "date": "2026-04-02",
                "subject": "数学",
                "grade": "五年级",
                "topic": "应用题",
                "summary_text": "课堂总结",
                "input_type": "text",
            },
        )

        self.assertEqual(response.status_code, 402)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertIn("积分不足", payload["error"])
        mock_generate_plan.assert_not_called()

    @patch("app.fetch_xhs_order_for_redemption")
    def test_credit_center_read_apis_return_overview_ledger_member_summary_and_member_detail(self, mock_fetch):
        mock_fetch.return_value = {
            "platform_order_id": "XHS-2002",
            "product_id": "sku-credit-100",
            "sku_id": "sku-credit-100",
            "product_name": "100 points pack",
            "paid_amount": 3900,
            "currency": "CNY",
            "buyer_masked_phone": "13600005678",
            "order_status": "paid",
            "credit_amount": 100,
            "raw_order_payload": {"status": "paid"},
        }
        redeem = self.client.post(
            "/api/credits/redeem/xhs",
            headers=self.auth_headers(self.owner_token),
            json={"platform_order_id": "XHS-2002", "phone_suffix": "5678"},
        )
        self.assertEqual(redeem.status_code, 200)

        member_request = lesson_manager.create_registration_request(
            username="member_usage_api",
            display_name="Member Usage Api",
            password="secret123",
            organization_name=self.owner_user["organization_name"],
        )
        member_user = lesson_manager.approve_registration_request(member_request["id"], self.owner_user["id"])
        credit_manager.record_ai_charge(
            organization_id=self.owner_user["organization_id"],
            user_id=member_user["id"],
            feature_key="teacher_feedback_draft",
            provider="openai",
            model="gpt-4o",
            input_tokens=90,
            output_tokens=20,
            credit_cost_final=5,
            source_record_type="lesson",
            source_record_id=22,
            request_id="req-member-detail-api",
        )

        overview = self.client.get("/api/credits/overview", headers=self.auth_headers(self.owner_token))
        ledger = self.client.get("/api/credits/ledger", headers=self.auth_headers(self.owner_token))
        members = self.client.get("/api/credits/member-usage", headers=self.auth_headers(self.owner_token))
        member_details = self.client.get(
            f"/api/credits/member-usage/{member_user['id']}",
            headers=self.auth_headers(self.owner_token),
        )

        self.assertEqual(overview.status_code, 200)
        self.assertEqual(ledger.status_code, 200)
        self.assertEqual(members.status_code, 200)
        self.assertEqual(member_details.status_code, 200)

        overview_payload = overview.get_json()
        self.assertIsNotNone(overview_payload)
        self.assertEqual(overview_payload["credit_balance"], 95)

        ledger_payload = ledger.get_json()
        self.assertIsNotNone(ledger_payload)
        self.assertEqual(ledger_payload["items"][0]["source_type"], "ai_usage")
        self.assertEqual(ledger_payload["items"][1]["source_type"], "xhs_order_redeem")

        members_payload = members.get_json()
        self.assertIsNotNone(members_payload)
        member_ids = [item["user_id"] for item in members_payload["items"]]
        self.assertIn(member_user["id"], member_ids)

        details_payload = member_details.get_json()
        self.assertIsNotNone(details_payload)
        self.assertEqual(details_payload["items"][0]["feature_key"], "teacher_feedback_draft")
        self.assertEqual(details_payload["items"][0]["credit_cost_final"], 5)

    def test_member_usage_detail_is_scoped_to_owner_organization(self):
        request = lesson_manager.create_organization_request(
            organization_name="Cross Org Academy",
            username="cross_org_owner",
            display_name="Cross Org Owner",
            password="secret123",
        )
        other_owner, _invite = lesson_manager.approve_organization_request(request["id"], self.owner_user["id"])
        credit_manager.apply_manual_adjustment(
            organization_id=other_owner["organization_id"],
            actor_user_id=other_owner["id"],
            amount=50,
            note="seed cross org",
        )
        credit_manager.record_ai_charge(
            organization_id=other_owner["organization_id"],
            user_id=other_owner["id"],
            feature_key="teacher_feedback_draft",
            provider="openai",
            model="gpt-4o",
            input_tokens=60,
            output_tokens=20,
            credit_cost_final=5,
            source_record_type="lesson",
            source_record_id=31,
            request_id="req-cross-org-usage",
        )

        response = self.client.get(
            f"/api/credits/member-usage/{other_owner['id']}",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["items"], [])


class XhsOpenPlatformValidationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        config_runtime.CFG_PATH = self.base / "config.json"

    def tearDown(self):
        gc.collect()
        self.temp_dir.cleanup()

    @patch("xhs_open_platform._fetch_order_detail_from_xhs")
    def test_fetch_rejects_unsafe_xhs_base_url(self, mock_fetch):
        config_runtime.write_file_config(
            {
                "xhs_app_id": "app-id",
                "xhs_app_secret": "app-secret",
                "xhs_base_url": "https://evil.example.net",
            }
        )
        with self.assertRaises(RuntimeError):
            xhs_open_platform.fetch_xhs_order_for_redemption(
                platform_order_id="XHS-URL-1",
                phone_suffix="1234",
            )
        mock_fetch.assert_not_called()

    @patch("xhs_open_platform._fetch_order_detail_from_xhs")
    def test_fetch_allows_known_safe_xhs_domain(self, mock_fetch):
        config_runtime.write_file_config(
            {
                "xhs_app_id": "app-id",
                "xhs_app_secret": "app-secret",
                "xhs_base_url": "https://api.xiaohongshu.com",
            }
        )
        mock_fetch.return_value = {
            "order_status": "paid",
            "credit_amount": 30,
            "buyer_masked_phone": "18888881234",
        }

        payload = xhs_open_platform.fetch_xhs_order_for_redemption(
            platform_order_id="XHS-URL-2",
            phone_suffix="1234",
        )
        self.assertEqual(payload["order_status"], "paid")
