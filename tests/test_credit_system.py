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
