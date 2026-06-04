import gc
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager


class StudentProfileTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()

    def tearDown(self):
        gc.collect()
        self.temp_dir.cleanup()

    def test_create_student_profile_stores_source_and_parent_contact(self):
        student = lesson_manager.create_student_profile(
            " 张三 ",
            source="转介绍",
            parent_contact="妈妈微信 zhang",
        )

        self.assertEqual(student["name"], "张三")
        self.assertEqual(student["source"], "转介绍")
        self.assertEqual(student["parent_contact"], "妈妈微信 zhang")
        self.assertEqual(student["study_status"], "未排课")

        listed = lesson_manager.list_students_for_organization()
        self.assertEqual(listed[0]["id"], student["id"])
        self.assertEqual(listed[0]["source"], "转介绍")
        self.assertEqual(listed[0]["parent_contact"], "妈妈微信 zhang")

    def test_student_profile_details_include_study_duration_and_course_history(self):
        class_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade="七年级",
            stage="初中",
            current_grade="七年级",
            class_number="1",
        )
        student = lesson_manager.create_student_profile("李四", source="老生续报")
        lesson_manager.add_existing_student_to_class(class_id, student["id"])
        lesson_manager.save_lesson("2026-03-02", "数学", "七年级", "函数", "", "", {}, "", class_id)
        lesson_manager.save_lesson("2026-05-20", "数学", "七年级", "几何", "", "", {}, "", class_id)

        detail = lesson_manager.get_student_profile(student["id"])

        self.assertEqual(detail["study_status"], "在读")
        self.assertEqual(detail["first_lesson_date"], "2026-03-02")
        self.assertEqual(detail["last_lesson_date"], "2026-05-20")
        self.assertEqual(detail["study_duration_label"], "2个月")
        self.assertEqual(len(detail["study_records"]), 1)
        self.assertEqual(detail["study_records"][0]["class_id"], class_id)
        self.assertEqual(detail["study_records"][0]["subject"], "数学")
        self.assertEqual(detail["study_records"][0]["lesson_count"], 2)

    def test_delete_empty_student_profile_removes_record(self):
        student = lesson_manager.create_student_profile("误建学生")

        result = lesson_manager.delete_or_archive_student_profile(student["id"])

        self.assertEqual(result["action"], "deleted")
        self.assertIsNone(lesson_manager.get_student_profile(student["id"]))
        self.assertEqual(lesson_manager.list_students_for_organization(), [])

    def test_delete_linked_student_profile_archives_record_and_hides_from_default_list(self):
        class_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade="七年级",
            stage="初中",
            current_grade="七年级",
            class_number="1",
        )
        student = lesson_manager.create_student_profile("重复学生")
        lesson_manager.add_existing_student_to_class(class_id, student["id"])

        result = lesson_manager.delete_or_archive_student_profile(student["id"])

        self.assertEqual(result["action"], "archived")
        archived = lesson_manager.get_student_profile(student["id"])
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(lesson_manager.list_students_for_organization(), [])
        self.assertEqual(lesson_manager.list_classes()[0]["student_count"], 0)
        self.assertEqual(lesson_manager.list_students_for_organization(include_archived=True)[0]["id"], student["id"])

    def test_duplicate_student_profile_lookup_uses_trimmed_exact_name(self):
        first = lesson_manager.create_student_profile("张三")
        lesson_manager.create_student_profile("张三丰")
        lesson_manager.create_student_profile(" 张三 ")

        matches = lesson_manager.list_duplicate_student_profiles(" 张三 ")

        self.assertEqual([item["id"] for item in matches], [first["id"], first["id"] + 2])


if __name__ == "__main__":
    unittest.main()
