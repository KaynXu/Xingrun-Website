import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager


class TeacherFeedbackStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_student_for_class_appends_in_class_suffix_only_inside_the_same_class(self):
        class_a = lesson_manager.save_class("初二数学A班", subject="数学", grade="初二")
        class_b = lesson_manager.save_class("初二数学B班", subject="数学", grade="初二")

        first = lesson_manager.create_student_for_class(class_a, "张三")
        second = lesson_manager.create_student_for_class(class_a, "张三")
        third_same_class = lesson_manager.create_student_for_class(class_a, "张三")
        third = lesson_manager.create_student_for_class(class_b, "张三")

        self.assertEqual(first["name"], "张三")
        self.assertEqual(second["name"], "张三（2）")
        self.assertEqual(third_same_class["name"], "张三（3）")
        self.assertEqual(third["name"], "张三")

    def test_remove_student_from_class_unbinds_mapping_without_deleting_student_row(self):
        class_id = lesson_manager.save_class("初三数学班", subject="数学", grade="初三")
        student = lesson_manager.create_student_for_class(class_id, "陈然")

        removed = lesson_manager.remove_student_from_class(class_id, student["id"])
        removed_again = lesson_manager.remove_student_from_class(class_id, student["id"])

        self.assertTrue(removed)
        self.assertFalse(removed_again)
        self.assertEqual(lesson_manager.list_students_for_class(class_id), [])
        self.assertEqual(lesson_manager.get_student(student["id"])["name"], "陈然")

    def test_build_lesson_feedback_editor_state_keeps_current_roster_and_blanks_new_students(self):
        class_id = lesson_manager.save_class("高一数学尖子班", subject="数学", grade="高一")
        lesson_id = lesson_manager.save_lesson(
            date_str="2026-04-02",
            subject="数学",
            grade="高一",
            topic="函数图像",
            summary="课堂笔记",
            weak_points="",
            plan={"lesson_info": {"topic": "函数图像"}},
            pdf_path="",
            class_id=class_id,
        )

        student_a = lesson_manager.create_student_for_class(class_id, "张晨")
        student_b = lesson_manager.create_student_for_class(class_id, "李好")
        lesson_manager.save_lesson_feedback(
            lesson_id=lesson_id,
            class_id=class_id,
            merged_text="张晨：已编辑反馈",
            student_index=[
                {"student_id": student_a["id"], "name": "张晨"},
                {"student_id": student_b["id"], "name": "李好"},
            ],
            editor_state={
                "students": [
                    {
                        "student_id": student_a["id"],
                        "selected_template_id": "active",
                        "remark": "表达很完整",
                    },
                    {
                        "student_id": student_b["id"],
                        "selected_template_id": "review-soon",
                        "remark": "",
                    },
                ],
                "custom_templates": [{"id": "custom-1", "label": "回家复述", "guidance": "先复述再做题"}],
            },
        )

        lesson_manager.remove_student_from_class(class_id, student_b["id"])
        lesson_manager.create_student_for_class(class_id, "王可")

        hydrated = lesson_manager.build_lesson_feedback_editor_state(lesson_id)

        self.assertEqual(hydrated["merged_text"], "张晨：已编辑反馈")
        self.assertEqual(hydrated["student_index"], [{"student_id": student_a["id"], "name": "张晨"}])
        self.assertEqual([item["name"] for item in hydrated["students"]], ["张晨", "王可"])
        self.assertEqual(hydrated["students"][0]["selected_template_id"], "active")
        self.assertEqual(hydrated["students"][1]["selected_template_id"], "")
        self.assertEqual(hydrated["students"][1]["remark"], "")
        self.assertEqual(hydrated["custom_templates"][0]["label"], "回家复述")
        self.assertTrue(hydrated["updated_at"])

    def test_build_lesson_feedback_editor_state_ignores_stale_feedback_class_id_and_uses_lesson_class(self):
        class_a = lesson_manager.save_class("高二数学A班", subject="数学", grade="高二")
        class_b = lesson_manager.save_class("高二数学B班", subject="数学", grade="高二")
        lesson_id = lesson_manager.save_lesson(
            date_str="2026-04-02",
            subject="数学",
            grade="高二",
            topic="数列",
            summary="课堂笔记",
            weak_points="",
            plan={"lesson_info": {"topic": "数列"}},
            pdf_path="",
            class_id=class_a,
        )

        student_a = lesson_manager.create_student_for_class(class_a, "甲同学")
        lesson_manager.create_student_for_class(class_b, "乙同学")
        lesson_manager.save_lesson_feedback(
            lesson_id=lesson_id,
            class_id=class_b,
            merged_text="测试",
            student_index=[{"student_id": student_a["id"], "name": "甲同学"}],
            editor_state={"students": [], "custom_templates": []},
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE lesson_feedbacks SET class_id=? WHERE lesson_id=?",
                (class_b, lesson_id),
            )

        hydrated = lesson_manager.build_lesson_feedback_editor_state(lesson_id)

        self.assertEqual(hydrated["class_id"], class_a)
        self.assertEqual([item["name"] for item in hydrated["students"]], ["甲同学"])

    def test_build_lesson_feedback_editor_state_raises_lookup_error_when_lesson_missing(self):
        with self.assertRaises(LookupError) as ctx:
            lesson_manager.build_lesson_feedback_editor_state(999999)
        self.assertEqual(str(ctx.exception), "lesson not found")

    def test_save_lesson_feedback_overwrites_the_same_lesson_row(self):
        class_id = lesson_manager.save_class("初一数学班", subject="数学", grade="初一")
        lesson_id = lesson_manager.save_lesson(
            date_str="2026-04-02",
            subject="数学",
            grade="初一",
            topic="方程复习",
            summary="课堂笔记",
            weak_points="",
            plan={"lesson_info": {"topic": "方程复习"}},
            pdf_path="",
            class_id=class_id,
        )

        first_saved = lesson_manager.save_lesson_feedback(
            lesson_id=lesson_id,
            class_id=class_id,
            merged_text="第一次",
            student_index=[{"student_id": 1, "name": "张三"}],
            editor_state={
                "students": [{"student_id": 1, "selected_template_id": "", "remark": "第一次备注"}],
                "custom_templates": [{"id": "custom-a", "label": "第一次", "guidance": "第一版"}],
            },
        )
        second_saved = lesson_manager.save_lesson_feedback(
            lesson_id=lesson_id,
            class_id=class_id,
            merged_text="第二次",
            student_index=[{"student_id": 1, "name": "张三"}],
            editor_state={
                "students": [{"student_id": 1, "selected_template_id": "active", "remark": "第二次备注"}],
                "custom_templates": [{"id": "custom-b", "label": "第二次", "guidance": "第二版"}],
            },
        )

        self.assertEqual(first_saved["merged_text"], "第一次")
        self.assertEqual(second_saved["merged_text"], "第二次")
        saved = lesson_manager.get_lesson_feedback(lesson_id)
        self.assertEqual(saved["merged_text"], "第二次")
        self.assertEqual(saved["editor_state"]["custom_templates"][0]["label"], "第二次")
        self.assertEqual(saved["editor_state"]["students"][0]["remark"], "第二次备注")
        with lesson_manager.get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM lesson_feedbacks WHERE lesson_id=?",
                (lesson_id,),
            ).fetchone()
        self.assertEqual(row["count"], 1)


if __name__ == "__main__":
    unittest.main()
