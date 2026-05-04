from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lesson_manager
import ai_processor


class WeeklyWrongQuestionFollowupTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        lesson_manager.DB_PATH = Path(self.temp_dir.name) / "xingrun.db"
        lesson_manager.init_db()
        self.organization_id = 1
        self.teacher_user_id = 1
        self.class_id = lesson_manager.save_class(
            "六年级 1 班",
            subject="数学",
            grade="六年级",
            organization_id=self.organization_id,
        )
        lesson_manager.set_class_teacher_user_id(self.class_id, self.teacher_user_id)
        self.alice = lesson_manager.create_student_for_class(self.class_id, "Alice")
        self.bob = lesson_manager.create_student_for_class(self.class_id, "Bob")
        self.account = lesson_manager.upsert_parent_wechat_account(openid="openid-weekly-followup")
        self.alice_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=self.account["id"],
            class_id=self.class_id,
            student_id=self.alice["id"],
        )
        self.bob_binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=self.account["id"],
            class_id=self.class_id,
            student_id=self.bob["id"],
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _recognized_record(
        self,
        *,
        binding_id: int,
        image_url: str,
        created_at: str,
        topic_category: str = "计算",
        secondary_error_summary: str = "",
        child_raw_reason_text: str = "",
    ) -> dict:
        record = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding_id,
            image_url=image_url,
            recognition_status="recognized",
            topic_category=topic_category,
            secondary_error_summary=secondary_error_summary,
            child_raw_reason_text=child_raw_reason_text,
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE wrong_question_submissions SET created_at=? WHERE id=?",
                (created_at, record["id"]),
            )
        return record

    def test_list_weekly_wrong_question_followup_students_groups_active_recognized_records_by_student(self):
        alice_week_one = self._recognized_record(
            binding_id=self.alice_binding["id"],
            image_url="https://files.example.com/alice-1.png",
            created_at="2026-04-06 09:00:00",
            topic_category="计算",
            secondary_error_summary="分数通分漏乘分子",
        )
        alice_week_two = self._recognized_record(
            binding_id=self.alice_binding["id"],
            image_url="https://files.example.com/alice-2.png",
            created_at="2026-04-08 10:00:00",
            topic_category="应用题",
            child_raw_reason_text="没有圈出单位一",
        )
        self._recognized_record(
            binding_id=self.alice_binding["id"],
            image_url="https://files.example.com/alice-outside-week.png",
            created_at="2026-04-15 10:00:00",
            topic_category="几何",
            secondary_error_summary="辅助线思路不稳定",
        )
        archived = self._recognized_record(
            binding_id=self.alice_binding["id"],
            image_url="https://files.example.com/alice-archived.png",
            created_at="2026-04-09 10:00:00",
            topic_category="计算",
            secondary_error_summary="这条已掌握不应进入周跟进",
        )
        lesson_manager.set_wechat_wrong_question_archive_status(archived["id"], "archived")
        bob_week = self._recognized_record(
            binding_id=self.bob_binding["id"],
            image_url="https://files.example.com/bob-1.png",
            created_at="2026-04-07 11:00:00",
            topic_category="几何",
            secondary_error_summary="角度关系没有标完整",
        )
        lesson_manager.create_wechat_wrong_question_submission(
            binding_id=self.bob_binding["id"],
            image_url="https://files.example.com/bob-pending.png",
            recognition_status="pending",
            topic_category="计算",
        )

        students = lesson_manager.list_weekly_wrong_question_followup_students(
            organization_id=self.organization_id,
            class_id=self.class_id,
            week_start_date="2026-04-06",
            week_end_date="2026-04-12",
        )

        self.assertEqual([item["student_name"] for item in students], ["Alice", "Bob"])
        alice_summary = students[0]
        self.assertEqual(alice_summary["organization_id"], self.organization_id)
        self.assertEqual(alice_summary["class_id"], self.class_id)
        self.assertEqual(alice_summary["class_name"], "六年级 1 班")
        self.assertEqual(alice_summary["student_id"], self.alice["id"])
        self.assertEqual(alice_summary["teacher_user_id"], self.teacher_user_id)
        self.assertEqual(alice_summary["teacher_name"], "平台管理员")
        self.assertEqual(alice_summary["weekly_question_count"], 2)
        self.assertEqual(alice_summary["total_active_question_count"], 3)
        self.assertEqual(alice_summary["topic_categories"], ["应用题", "计算"])
        self.assertEqual(alice_summary["representative_reason_summaries"], ["没有圈出单位一", "分数通分漏乘分子"])
        self.assertEqual(alice_summary["latest_created_at"], "2026-04-08 10:00:00")
        self.assertEqual(alice_summary["source_record_ids"], [alice_week_two["id"], alice_week_one["id"]])

        bob_summary = students[1]
        self.assertEqual(bob_summary["weekly_question_count"], 1)
        self.assertEqual(bob_summary["total_active_question_count"], 1)
        self.assertEqual(bob_summary["source_record_ids"], [bob_week["id"]])

    def test_upsert_weekly_wrong_question_followup_message_reuses_row_and_round_trips_source_record_ids(self):
        first = lesson_manager.upsert_weekly_wrong_question_followup_message(
            organization_id=self.organization_id,
            class_id=self.class_id,
            student_id=self.alice["id"],
            teacher_user_id=self.teacher_user_id,
            week_start_date="2026-04-06",
            week_end_date="2026-04-12",
            style="warm",
            message_text="第一版话术",
            source_record_ids=["record-1", "record-2"],
            generated_by=self.teacher_user_id,
        )
        second = lesson_manager.upsert_weekly_wrong_question_followup_message(
            organization_id=self.organization_id,
            class_id=self.class_id,
            student_id=self.alice["id"],
            teacher_user_id=self.teacher_user_id,
            week_start_date="2026-04-06",
            week_end_date="2026-04-12",
            style="warm",
            message_text="更新后的话术",
            source_record_ids=["record-2", "record-3"],
            generated_by=self.teacher_user_id,
        )
        fetched = lesson_manager.get_weekly_wrong_question_followup_message(
            organization_id=self.organization_id,
            class_id=self.class_id,
            student_id=self.alice["id"],
            week_start_date="2026-04-06",
            style="warm",
        )

        self.assertEqual(second["id"], first["id"])
        self.assertEqual(second["message_text"], "更新后的话术")
        self.assertEqual(second["source_record_ids"], ["record-2", "record-3"])
        self.assertEqual(fetched["id"], first["id"])
        self.assertEqual(fetched["source_record_ids"], ["record-2", "record-3"])

    def test_deleting_teacher_referenced_by_followup_message_does_not_fail_fk(self):
        teacher_request = lesson_manager.create_registration_request(
            "weekly_teacher",
            "Weekly Teacher",
            "teacher-pass",
            recovery_phone="13800000000",
        )
        teacher = lesson_manager.approve_registration_request(teacher_request["id"], self.teacher_user_id)
        lesson_manager.upsert_weekly_wrong_question_followup_message(
            organization_id=self.organization_id,
            class_id=self.class_id,
            student_id=self.alice["id"],
            teacher_user_id=teacher["id"],
            week_start_date="2026-04-06",
            week_end_date="2026-04-12",
            style="warm",
            message_text="跟进话术",
            source_record_ids=["record-1"],
            generated_by=teacher["id"],
        )

        lesson_manager.delete_user_for_actor(
            lesson_manager.get_user_by_id(self.teacher_user_id),
            teacher["id"],
        )
        fetched = lesson_manager.get_weekly_wrong_question_followup_message(
            organization_id=self.organization_id,
            class_id=self.class_id,
            student_id=self.alice["id"],
            week_start_date="2026-04-06",
            style="warm",
        )

        self.assertIsNotNone(fetched)
        self.assertIsNone(fetched["teacher_user_id"])
        self.assertIsNone(fetched["generated_by"])

    def test_weekly_student_query_includes_full_boundary_days_and_has_matching_index(self):
        before_week = self._recognized_record(
            binding_id=self.alice_binding["id"],
            image_url="https://files.example.com/before-week.png",
            created_at="2026-04-05 23:59:59",
            topic_category="计算",
        )
        start_boundary = self._recognized_record(
            binding_id=self.alice_binding["id"],
            image_url="https://files.example.com/start-boundary.png",
            created_at="2026-04-06 00:00:00",
            topic_category="计算",
        )
        end_boundary = self._recognized_record(
            binding_id=self.alice_binding["id"],
            image_url="https://files.example.com/end-boundary.png",
            created_at="2026-04-12 23:59:59",
            topic_category="几何",
        )
        after_week = self._recognized_record(
            binding_id=self.alice_binding["id"],
            image_url="https://files.example.com/after-week.png",
            created_at="2026-04-13 00:00:00",
            topic_category="应用题",
        )

        students = lesson_manager.list_weekly_wrong_question_followup_students(
            organization_id=self.organization_id,
            class_id=self.class_id,
            week_start_date="2026-04-06",
            week_end_date="2026-04-12",
        )

        self.assertEqual(len(students), 1)
        self.assertEqual(students[0]["weekly_question_count"], 2)
        self.assertEqual(students[0]["source_record_ids"], [end_boundary["id"], start_boundary["id"]])
        self.assertNotIn(before_week["id"], students[0]["source_record_ids"])
        self.assertNotIn(after_week["id"], students[0]["source_record_ids"])
        with lesson_manager.get_conn() as conn:
            indexes = {
                row["name"]
                for row in conn.execute("PRAGMA index_list(wrong_question_submissions)").fetchall()
            }
        self.assertIn("idx_wrong_question_submissions_weekly_followup", indexes)


class WeeklyWrongQuestionFollowupAiTestCase(unittest.TestCase):
    def test_generate_weekly_wrong_question_followup_message_uses_teacher_wechat_prompt(self):
        client = mock.Mock()
        client.chat.completions.create.return_value.choices = [
            mock.Mock(
                message=mock.Mock(
                    content="王睿博妈妈，我刚看了下孩子这周的错题，几何第一步还需要再收一下。"
                )
            )
        ]

        with mock.patch("ai_processor._get_client", return_value=client):
            message = ai_processor.generate_weekly_wrong_question_followup_message(
                student_name="王睿博",
                class_name="七年级 5 班",
                teacher_name="Kayn",
                weekly_question_count=3,
                total_active_question_count=12,
                topic_categories=["几何", "计算"],
                representative_reason_summaries=["几何读图第一步容易断"],
                has_practice_sheet=True,
            )

        self.assertIn("王睿博妈妈", message)
        call_kwargs = client.chat.completions.create.call_args.kwargs
        sent_messages = call_kwargs["messages"]
        sent_prompt = "\n".join(str(item["content"]) for item in sent_messages)
        self.assertIn("像老师真实发给家长的微信", sent_prompt)
        self.assertIn("不要写成报告", sent_prompt)
        self.assertIn("小程序", sent_prompt)
        self.assertIn("不提", sent_prompt)


if __name__ == "__main__":
    unittest.main()
