import sys
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
