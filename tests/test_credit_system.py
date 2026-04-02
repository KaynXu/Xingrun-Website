import gc
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import credit_manager
import lesson_manager


class CreditSystemServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.owner, _ = lesson_manager.authenticate_user("Kayn", "xingrun2026")

    def tearDown(self):
        gc.collect()
        self.temp_dir.cleanup()

    def test_credit_account_is_created_and_tracks_manual_credit_then_debit(self):
        overview = credit_manager.get_credit_overview(self.owner["organization_id"])
        self.assertEqual(overview["credit_balance"], 0)

        credit_manager.apply_manual_adjustment(
            organization_id=self.owner["organization_id"],
            actor_user_id=self.owner["id"],
            amount=120,
            note="seed credits for test",
        )
        credit_manager.record_ai_charge(
            organization_id=self.owner["organization_id"],
            user_id=self.owner["id"],
            feature_key="consultation_ai_parse",
            provider="openai",
            model="gpt-4o",
            input_tokens=120,
            output_tokens=40,
            credit_cost_final=6,
            source_record_type="consultation_batch",
            source_record_id=7,
            request_id="req-credit-seed",
        )

        updated = credit_manager.get_credit_overview(self.owner["organization_id"])
        self.assertEqual(updated["credit_balance"], 114)
        self.assertEqual(updated["total_recharged"], 120)
        self.assertEqual(updated["total_consumed"], 6)

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

