import sys
import tempfile
import unittest
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager


class ClassFeedbackStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _owner(self):
        owner = lesson_manager.get_user_by_username("kayn")
        self.assertIsNotNone(owner)
        return owner

    def _create_member_user(self, username: str, display_name: str):
        owner = self._owner()
        request = lesson_manager.create_registration_request(username, display_name, "password-123")
        return lesson_manager.approve_registration_request(request["id"], owner["id"])

    def _insert_student_entry(
        self,
        *,
        task_id: int,
        student_id: int,
        student_name_snapshot: str,
        ai_draft: str = "",
        final_text: str = "",
        checked_at=None,
    ) -> None:
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO class_feedback_student_entries (
                    task_id, student_id, student_name_snapshot, ai_draft, final_text, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, student_id, student_name_snapshot, ai_draft, final_text, checked_at),
            )

    def _create_confirmed_feedback_entry(
        self,
        *,
        class_id: int,
        teacher_user_id: int,
        teacher_name_snapshot: str,
        student_id: int,
        student_name: str,
        start_date: str,
        end_date: str,
        final_text: str,
        checked_at: str,
    ):
        task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=teacher_user_id,
            teacher_name_snapshot=teacher_name_snapshot,
            start_date=start_date,
            end_date=end_date,
            created_by=teacher_user_id,
        )
        lesson_manager.save_class_feedback_generation_result(
            task["id"],
            class_summary_ai_draft=f"{student_name} 草稿",
            student_entries=[{"student_id": student_id, "name": student_name, "ai_draft": f"{student_name} 草稿"}],
        )
        lesson_manager.confirm_class_feedback_task(
            task["id"],
            class_summary_final_text=f"{student_name} 终稿",
            student_entries=[{"student_id": student_id, "final_text": final_text, "checked_at": checked_at}],
        )
        return lesson_manager.get_class_feedback_task(task["id"])

    def test_create_task_derives_granularity_and_teacher_snapshot(self):
        owner = self._owner()
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner["id"])

        task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            start_date="2026-04-03",
            end_date="2026-04-03",
            created_by=owner["id"],
        )

        self.assertEqual(task["class_id"], class_id)
        self.assertEqual(task["period_length_days"], 1)
        self.assertEqual(task["period_granularity"], "daily")
        self.assertEqual(task["teacher_user_id"], owner["id"])
        self.assertEqual(task["teacher_name_snapshot"], owner["display_name"])
        self.assertEqual(task["status"], "draft")
        self.assertEqual(task["student_entries"], [])

    def test_create_task_rejects_mismatched_teacher_binding(self):
        owner = self._owner()
        other_teacher = self._create_member_user("teacher-b", "Teacher B")
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner["id"])

        with self.assertRaises(ValueError):
            lesson_manager.create_class_feedback_task(
                class_id=class_id,
                teacher_user_id=other_teacher["id"],
                teacher_name_snapshot=other_teacher["display_name"],
                start_date="2026-04-03",
                end_date="2026-04-03",
                created_by=owner["id"],
            )

    def test_save_generation_result_rejects_cross_class_student_and_keeps_existing_entries(self):
        owner = self._owner()
        class_one_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        class_two_id = lesson_manager.save_class("S01A2", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_one_id, owner["id"])
        lesson_manager.set_class_teacher_user_id(class_two_id, owner["id"])
        class_one_student = lesson_manager.create_student_for_class(class_one_id, "张三")
        class_two_student = lesson_manager.create_student_for_class(class_two_id, "李四")

        task = lesson_manager.create_class_feedback_task(
            class_id=class_one_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            start_date="2026-04-03",
            end_date="2026-04-03",
            created_by=owner["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            task["id"],
            class_summary_ai_draft="原始草稿",
            student_entries=[{"student_id": class_one_student["id"], "name": "张三", "ai_draft": "张三草稿"}],
        )

        with self.assertRaises(ValueError):
            lesson_manager.save_class_feedback_generation_result(
                task["id"],
                class_summary_ai_draft="坏草稿",
                student_entries=[{"student_id": class_two_student["id"], "name": "李四", "ai_draft": "李四草稿"}],
            )

        refreshed_task = lesson_manager.get_class_feedback_task(task["id"])
        self.assertEqual(refreshed_task["class_summary_ai_draft"], "原始草稿")
        self.assertEqual(len(refreshed_task["student_entries"]), 1)
        self.assertEqual(refreshed_task["student_entries"][0]["student_id"], class_one_student["id"])
        self.assertEqual(refreshed_task["student_entries"][0]["ai_draft"], "张三草稿")

    def test_confirm_rejects_missing_student_and_keeps_task_in_draft(self):
        owner = self._owner()
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner["id"])
        class_one_student = lesson_manager.create_student_for_class(class_id, "张三")
        class_two_student = lesson_manager.create_student_for_class(class_id, "李四")

        task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            start_date="2026-04-04",
            end_date="2026-04-04",
            created_by=owner["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            task["id"],
            class_summary_ai_draft="待确认草稿",
            student_entries=[
                {"student_id": class_one_student["id"], "name": "张三", "ai_draft": "张三草稿"},
                {"student_id": class_two_student["id"], "name": "李四", "ai_draft": "李四草稿"},
            ],
        )

        with self.assertRaises(ValueError):
            lesson_manager.confirm_class_feedback_task(
                task["id"],
                class_summary_final_text="坏终稿",
                student_entries=[{"student_id": class_one_student["id"], "final_text": "张三终稿", "checked_at": "2026-04-04 20:00:00"}],
            )

        refreshed_task = lesson_manager.get_class_feedback_task(task["id"])
        self.assertEqual(refreshed_task["status"], "draft")
        self.assertEqual(len(refreshed_task["student_entries"]), 2)
        self.assertEqual(refreshed_task["student_entries"][0]["student_id"], class_one_student["id"])
        self.assertEqual(refreshed_task["student_entries"][0]["ai_draft"], "张三草稿")
        self.assertEqual(refreshed_task["student_entries"][0]["final_text"], "")
        self.assertEqual(refreshed_task["student_entries"][1]["student_id"], class_two_student["id"])
        self.assertEqual(refreshed_task["student_entries"][1]["ai_draft"], "李四草稿")
        self.assertEqual(refreshed_task["student_entries"][1]["final_text"], "")

    def test_save_generation_result_rejects_confirmed_task_and_preserves_final_text(self):
        owner = self._owner()
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner["id"])
        student = lesson_manager.create_student_for_class(class_id, "张三")

        task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            start_date="2026-04-04",
            end_date="2026-04-10",
            created_by=owner["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            task["id"],
            class_summary_ai_draft="初始草稿",
            student_entries=[{"student_id": student["id"], "name": "张三", "ai_draft": "初始学生草稿"}],
        )
        lesson_manager.confirm_class_feedback_task(
            task["id"],
            class_summary_final_text="正式班级反馈",
            student_entries=[{"student_id": student["id"], "final_text": "正式学生反馈", "checked_at": "2026-04-10 20:00:00"}],
        )

        with self.assertRaises(ValueError):
            lesson_manager.save_class_feedback_generation_result(
                task["id"],
                class_summary_ai_draft="重新生成草稿",
                student_entries=[{"student_id": student["id"], "name": "张三", "ai_draft": "重新生成学生草稿"}],
            )

        refreshed_task = lesson_manager.get_class_feedback_task(task["id"])
        self.assertEqual(refreshed_task["status"], "confirmed")
        self.assertEqual(refreshed_task["class_summary_final_text"], "正式班级反馈")
        self.assertEqual(refreshed_task["student_entries"][0]["final_text"], "正式学生反馈")

    def test_database_trigger_rejects_cross_class_student_entry(self):
        owner = self._owner()
        class_one_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        class_two_id = lesson_manager.save_class("S01A2", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_one_id, owner["id"])
        lesson_manager.set_class_teacher_user_id(class_two_id, owner["id"])
        class_one_student = lesson_manager.create_student_for_class(class_one_id, "张三")
        class_two_student = lesson_manager.create_student_for_class(class_two_id, "李四")

        task = lesson_manager.create_class_feedback_task(
            class_id=class_one_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            start_date="2026-04-04",
            end_date="2026-04-04",
            created_by=owner["id"],
        )

        with lesson_manager.get_conn() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO class_feedback_student_entries (
                        task_id, student_id, student_name_snapshot, ai_draft, final_text, checked_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (task["id"], class_two_student["id"], "李四", "跨班草稿", "", None),
                )

            conn.execute(
                """
                INSERT INTO class_feedback_student_entries (
                    task_id, student_id, student_name_snapshot, ai_draft, final_text, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task["id"], class_one_student["id"], "张三", "张三草稿", "", None),
            )
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO class_feedback_student_entries (
                        task_id, student_id, student_name_snapshot, ai_draft, final_text, checked_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (task["id"], class_one_student["id"], "张三", "重复草稿", "", None),
                )

    def test_database_trigger_rejects_mismatched_teacher_binding_on_task_insert(self):
        owner = self._owner()
        other_teacher = self._create_member_user("teacher-c", "Teacher C")
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner["id"])

        with lesson_manager.get_conn() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO class_feedback_tasks (
                        class_id, teacher_user_id, teacher_name_snapshot,
                        start_date, end_date, period_length_days, period_granularity,
                        status, class_summary_ai_draft, class_summary_final_text, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', '', '', ?)
                    """,
                    (
                        class_id,
                        other_teacher["id"],
                        other_teacher["display_name"],
                        "2026-04-04",
                        "2026-04-04",
                        1,
                        "daily",
                        owner["id"],
                    ),
                )

    def test_previous_confirmed_entry_prefers_same_granularity_before_falling_back(self):
        owner = self._owner()
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner["id"])
        student = lesson_manager.create_student_for_class(class_id, "张三")

        weekly_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            start_date="2026-03-24",
            end_date="2026-03-30",
            created_by=owner["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            weekly_task["id"],
            class_summary_ai_draft="班级周反馈",
            student_entries=[{"student_id": student["id"], "name": "张三", "ai_draft": "周反馈草稿"}],
        )
        lesson_manager.confirm_class_feedback_task(
            weekly_task["id"],
            class_summary_final_text="班级周反馈终稿",
            student_entries=[{"student_id": student["id"], "final_text": "周反馈终稿", "checked_at": "2026-03-30 20:00:00"}],
        )

        daily_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            start_date="2026-04-01",
            end_date="2026-04-01",
            created_by=owner["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            daily_task["id"],
            class_summary_ai_draft="班级日报",
            student_entries=[{"student_id": student["id"], "name": "张三", "ai_draft": "日报草稿"}],
        )
        lesson_manager.confirm_class_feedback_task(
            daily_task["id"],
            class_summary_final_text="班级日报终稿",
            student_entries=[{"student_id": student["id"], "final_text": "日报终稿", "checked_at": "2026-04-01 20:00:00"}],
        )

        custom_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            start_date="2026-04-02",
            end_date="2026-04-05",
            created_by=owner["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            custom_task["id"],
            class_summary_ai_draft="班级自定义反馈",
            student_entries=[{"student_id": student["id"], "name": "张三", "ai_draft": "自定义草稿"}],
        )
        lesson_manager.confirm_class_feedback_task(
            custom_task["id"],
            class_summary_final_text="班级自定义反馈终稿",
            student_entries=[{"student_id": student["id"], "final_text": "自定义终稿", "checked_at": "2026-04-05 20:00:00"}],
        )

        match_daily = lesson_manager.find_previous_confirmed_class_feedback_entry(
            class_id=class_id,
            student_id=student["id"],
            period_granularity="daily",
            before_end_date="2026-04-06",
        )
        match_weekly = lesson_manager.find_previous_confirmed_class_feedback_entry(
            class_id=class_id,
            student_id=student["id"],
            period_granularity="weekly",
            before_end_date="2026-04-06",
        )
        fallback_monthly = lesson_manager.find_previous_confirmed_class_feedback_entry(
            class_id=class_id,
            student_id=student["id"],
            period_granularity="monthly",
            before_end_date="2026-04-06",
        )

        self.assertEqual(match_daily["final_text"], "日报终稿")
        self.assertEqual(match_weekly["final_text"], "周反馈终稿")
        self.assertEqual(fallback_monthly["final_text"], "自定义终稿")

    def test_only_confirmed_text_is_returned_as_memory_source(self):
        owner = self._owner()
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner["id"])
        student = lesson_manager.create_student_for_class(class_id, "李四")

        task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            start_date="2026-04-02",
            end_date="2026-04-08",
            created_by=owner["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            task["id"],
            class_summary_ai_draft="仅草稿",
            student_entries=[{"student_id": student["id"], "name": "李四", "ai_draft": "仅草稿学生"}],
        )

        self.assertIsNone(
            lesson_manager.find_previous_confirmed_class_feedback_entry(
                class_id=class_id,
                student_id=student["id"],
                period_granularity="weekly",
                before_end_date="2026-04-09",
            )
        )

    def test_previous_confirmed_entry_skips_empty_final_text_and_missing_checked_at(self):
        owner = self._owner()
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner["id"])
        student = lesson_manager.create_student_for_class(class_id, "王五")

        valid_task = self._create_confirmed_feedback_entry(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            student_id=student["id"],
            student_name="王五",
            start_date="2026-03-20",
            end_date="2026-03-26",
            final_text="有效终稿",
            checked_at="2026-03-26 20:00:00",
        )

        empty_final_text_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            start_date="2026-03-27",
            end_date="2026-04-02",
            created_by=owner["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            empty_final_text_task["id"],
            class_summary_ai_draft="空终稿草稿",
            student_entries=[{"student_id": student["id"], "name": "王五", "ai_draft": "空终稿草稿"}],
        )
        lesson_manager.confirm_class_feedback_task(
            empty_final_text_task["id"],
            class_summary_final_text="空终稿班级反馈",
            student_entries=[{"student_id": student["id"], "final_text": "空终稿", "checked_at": "2026-03-27 20:00:00"}],
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE class_feedback_student_entries SET final_text='' WHERE task_id=?",
                (empty_final_text_task["id"],),
            )

        missing_checked_at_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            start_date="2026-04-03",
            end_date="2026-04-09",
            created_by=owner["id"],
        )
        lesson_manager.save_class_feedback_generation_result(
            missing_checked_at_task["id"],
            class_summary_ai_draft="缺签时间草稿",
            student_entries=[{"student_id": student["id"], "name": "王五", "ai_draft": "缺签时间草稿"}],
        )
        lesson_manager.confirm_class_feedback_task(
            missing_checked_at_task["id"],
            class_summary_final_text="缺签时间班级反馈",
            student_entries=[{"student_id": student["id"], "final_text": "缺签时间", "checked_at": "2026-03-28 20:00:00"}],
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE class_feedback_student_entries SET checked_at=NULL WHERE task_id=?",
                (missing_checked_at_task["id"],),
            )

        latest = lesson_manager.find_previous_confirmed_class_feedback_entry(
            class_id=class_id,
            student_id=student["id"],
            period_granularity="weekly",
            before_end_date="2026-04-10",
        )

        self.assertIsNotNone(latest)
        self.assertEqual(latest["task_id"], valid_task["id"])
        self.assertEqual(latest["final_text"], "有效终稿")
        self.assertEqual(latest["checked_at"], "2026-03-26 20:00:00")

    def test_label_config_round_trip_keeps_custom_group(self):
        owner = self._owner()

        default_groups = lesson_manager.list_class_feedback_label_configs(owner["id"])
        self.assertEqual(len(default_groups), 4)
        self.assertEqual(default_groups[0]["group"], "课堂状态")

        lesson_manager.save_class_feedback_label_configs(
            owner["id"],
            [
                {"group": "阶段变化", "labels": ["进步明显", "有点回落", "变化不大", "需要重点关注"]},
                {"group": "老师自定义", "labels": ["假期每日打卡稳定"]},
            ],
        )

        groups = lesson_manager.list_class_feedback_label_configs(owner["id"])
        self.assertEqual(groups[0]["group"], "阶段变化")
        self.assertEqual(groups[0]["labels"], ["进步明显", "有点回落", "变化不大", "需要重点关注"])
        self.assertEqual(groups[1]["group"], "老师自定义")
        self.assertEqual(groups[1]["labels"], ["假期每日打卡稳定"])

    def test_empty_label_config_explicitly_clears_custom_config_and_falls_back_to_defaults(self):
        owner = self._owner()

        lesson_manager.save_class_feedback_label_configs(
            owner["id"],
            [
                {"group": "阶段变化", "labels": ["进步明显", "有点回落"]},
                {"group": "老师自定义", "labels": ["假期每日打卡稳定"]},
            ],
        )
        self.assertEqual(len(lesson_manager.list_class_feedback_label_configs(owner["id"])), 2)

        lesson_manager.save_class_feedback_label_configs(owner["id"], [])

        default_groups = lesson_manager.list_class_feedback_label_configs(owner["id"])
        self.assertEqual(len(default_groups), 4)
        self.assertEqual(default_groups[0]["group"], "课堂状态")
        self.assertEqual(default_groups[0]["labels"], ["进入状态快", "注意力更集中", "注意力波动", "开口更主动", "开口偏少"])


if __name__ == "__main__":
    unittest.main()
