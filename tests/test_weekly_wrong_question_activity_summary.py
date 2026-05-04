from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lesson_manager


class WeeklyWrongQuestionActivitySummaryStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        lesson_manager.DB_PATH = Path(self.temp_dir.name) / "xingrun.db"
        lesson_manager.init_db()

        org_request = lesson_manager.create_organization_request(
            "活跃汇总测试机构",
            "activity_owner",
            "活跃汇总负责人",
            "owner-pass",
            recovery_phone="13800000001",
        )
        super_owner = lesson_manager.get_user_by_username("Kayn")
        owner, _invite = lesson_manager.approve_organization_request(org_request["id"], super_owner["id"])
        self.organization_id = owner["organization_id"]
        self.owner_id = owner["id"]

        self.class_a = lesson_manager.save_class(
            "五年级3班",
            subject="数学",
            grade="五年级",
            organization_id=self.organization_id,
        )
        self.class_b = lesson_manager.save_class(
            "六年级2班",
            subject="数学",
            grade="六年级",
            organization_id=self.organization_id,
        )
        lesson_manager.set_class_teacher_user_id(self.class_a, self.owner_id)
        lesson_manager.set_class_teacher_user_id(self.class_b, self.owner_id)
        self.alice = lesson_manager.create_student_for_class(self.class_a, "Alice")
        self.bob = lesson_manager.create_student_for_class(self.class_a, "Bob")
        self.cindy = lesson_manager.create_student_for_class(self.class_b, "Cindy")
        self.parent = lesson_manager.upsert_parent_wechat_account(openid="openid-activity")
        self.alice_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=self.parent["id"],
            class_id=self.class_a,
            student_id=self.alice["id"],
        )
        self.bob_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=self.parent["id"],
            class_id=self.class_a,
            student_id=self.bob["id"],
        )
        self.cindy_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=self.parent["id"],
            class_id=self.class_b,
            student_id=self.cindy["id"],
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _record(self, *, binding_id: int, created_at: str, topic_category: str, archive_status: str = "active"):
        record = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding_id,
            image_url=f"https://files.example.com/{binding_id}-{created_at}.png",
            recognition_status="recognized",
            topic_category=topic_category,
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE wrong_question_submissions SET created_at=?, archive_status=? WHERE id=?",
                (created_at, archive_status, record["id"]),
            )
        return record

    def test_activity_summary_lists_classes_teachers_and_students_from_high_to_low(self):
        self._record(binding_id=self.alice_binding["id"], created_at="2026-05-04 09:00:00", topic_category="几何")
        self._record(binding_id=self.alice_binding["id"], created_at="2026-05-04 10:00:00", topic_category="几何")
        self._record(binding_id=self.alice_binding["id"], created_at="2026-05-04 11:00:00", topic_category="计算")
        self._record(binding_id=self.bob_binding["id"], created_at="2026-05-05 12:00:00", topic_category="计算")
        self._record(binding_id=self.cindy_binding["id"], created_at="2026-05-06 13:00:00", topic_category="应用题", archive_status="archived")
        self._record(binding_id=self.cindy_binding["id"], created_at="2026-04-30 13:00:00", topic_category="几何")

        summary = lesson_manager.list_weekly_wrong_question_activity_summary(
            week_start_date="2026-05-04",
            week_end_date="2026-05-10",
        )

        self.assertEqual([item["class_name"] for item in summary["class_items"]], ["五年级3班", "六年级2班"])
        self.assertEqual(summary["class_items"][0]["organization_name"], "活跃汇总测试机构")
        self.assertNotIn("teacher_user_id", summary["class_items"][0])
        self.assertNotIn("teacher_name", summary["class_items"][0])
        self.assertNotIn("pending_followup_count", summary["class_items"][0])
        self.assertEqual(summary["class_items"][0]["weekly_question_count"], 4)
        self.assertEqual(summary["class_items"][0]["uploading_student_count"], 2)
        self.assertEqual(summary["class_items"][0]["latest_created_at"], "2026-05-05 12:00:00")

        self.assertEqual(len(summary["teacher_items"]), 1)
        teacher = summary["teacher_items"][0]
        self.assertEqual(teacher["organization_name"], "活跃汇总测试机构")
        self.assertEqual(teacher["teacher_name"], "活跃汇总负责人")
        self.assertEqual(teacher["class_count"], 2)
        self.assertEqual(teacher["weekly_question_count"], 5)
        self.assertEqual(teacher["involved_student_count"], 3)
        self.assertEqual(teacher["pending_followup_count"], 4)

        self.assertEqual([item["student_name"] for item in summary["student_items"]], ["Alice", "Cindy", "Bob"])
        self.assertEqual(summary["student_items"][0]["organization_name"], "活跃汇总测试机构")
        self.assertNotIn("teacher_user_id", summary["student_items"][0])
        self.assertNotIn("teacher_name", summary["student_items"][0])
        self.assertNotIn("pending_followup_count", summary["student_items"][0])
        self.assertEqual(summary["student_items"][0]["weekly_question_count"], 3)
        self.assertEqual(summary["student_items"][0]["total_question_count"], 3)
        self.assertEqual(summary["student_items"][0]["topic_categories"], ["几何", "计算"])
        self.assertEqual(summary["student_items"][1]["total_question_count"], 2)

    def test_activity_summary_student_topics_are_top_three_by_weekly_frequency(self):
        for index in range(4):
            self._record(
                binding_id=self.alice_binding["id"],
                created_at=f"2026-05-04 09:0{index}:00",
                topic_category="几何",
            )
        for index in range(3):
            self._record(
                binding_id=self.alice_binding["id"],
                created_at=f"2026-05-04 10:0{index}:00",
                topic_category="计算",
            )
        for index in range(2):
            self._record(
                binding_id=self.alice_binding["id"],
                created_at=f"2026-05-04 11:0{index}:00",
                topic_category="应用题",
            )
        self._record(binding_id=self.alice_binding["id"], created_at="2026-05-04 12:00:00", topic_category="行程")

        summary = lesson_manager.list_weekly_wrong_question_activity_summary(
            week_start_date="2026-05-04",
            week_end_date="2026-05-10",
        )

        self.assertEqual(summary["student_items"][0]["topic_categories"], ["几何", "计算", "应用题"])

    def test_activity_summary_total_question_count_includes_non_wechat_recognized_history(self):
        self._record(binding_id=self.alice_binding["id"], created_at="2026-05-04 09:00:00", topic_category="几何")
        manual_history = self._record(
            binding_id=self.alice_binding["id"],
            created_at="2026-04-30 09:00:00",
            topic_category="计算",
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE wrong_question_submissions SET source='manual' WHERE id=?",
                (manual_history["id"],),
            )

        summary = lesson_manager.list_weekly_wrong_question_activity_summary(
            week_start_date="2026-05-04",
            week_end_date="2026-05-10",
        )

        self.assertEqual(summary["student_items"][0]["student_name"], "Alice")
        self.assertEqual(summary["student_items"][0]["weekly_question_count"], 1)
        self.assertEqual(summary["student_items"][0]["total_question_count"], 2)

    def test_activity_summary_filters_by_organization(self):
        self._record(binding_id=self.alice_binding["id"], created_at="2026-05-04 09:00:00", topic_category="几何")
        other_org_request = lesson_manager.create_organization_request(
            "另一个机构",
            "activity_other_owner",
            "另一个负责人",
            "owner-pass",
            recovery_phone="13800000002",
        )
        super_owner = lesson_manager.get_user_by_username("Kayn")
        other_owner, _invite = lesson_manager.approve_organization_request(other_org_request["id"], super_owner["id"])
        other_class = lesson_manager.save_class(
            "三年级1班",
            subject="数学",
            grade="三年级",
            organization_id=other_owner["organization_id"],
        )
        lesson_manager.set_class_teacher_user_id(other_class, other_owner["id"])
        other_student = lesson_manager.create_student_for_class(other_class, "Other")
        other_parent = lesson_manager.upsert_parent_wechat_account(openid="openid-activity-other")
        other_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=other_parent["id"],
            class_id=other_class,
            student_id=other_student["id"],
        )
        self._record(binding_id=other_binding["id"], created_at="2026-05-04 10:00:00", topic_category="计算")

        summary = lesson_manager.list_weekly_wrong_question_activity_summary(
            week_start_date="2026-05-04",
            week_end_date="2026-05-10",
            organization_id=self.organization_id,
        )

        self.assertEqual([item["organization_id"] for item in summary["class_items"]], [self.organization_id])
        self.assertEqual([item["class_name"] for item in summary["class_items"]], ["五年级3班"])
        self.assertEqual([item["student_name"] for item in summary["student_items"]], ["Alice"])
