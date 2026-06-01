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


class ClassStructuredNameTestCase(unittest.TestCase):
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

    def test_structured_name_can_hide_or_show_cohort_year(self):
        class_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade="四年级",
            stage="小奥",
            current_grade="四年级",
            class_number="1",
            cohort_year=2025,
            show_cohort_year=True,
        )
        self.assertEqual(lesson_manager.get_class(class_id)["name"], "数学·2025级·四年级·1班")

        lesson_manager.update_class(
            class_id,
            "",
            subject="数学",
            grade="四年级",
            stage="小奥",
            current_grade="四年级",
            class_number="1",
            cohort_year=2025,
            show_cohort_year=False,
        )
        updated = lesson_manager.get_class(class_id)

        self.assertEqual(updated["name"], "数学·四年级·1班")
        self.assertEqual(updated["show_cohort_year"], False)

    def test_small_class_name_uses_existing_students(self):
        roster_class_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade="七年级",
            stage="初中",
            current_grade="七年级",
            class_number="9",
            cohort_year=2025,
        )
        student_a = lesson_manager.create_student_for_class(roster_class_id, "张三")["id"]
        student_b = lesson_manager.create_student_for_class(roster_class_id, "李四")["id"]

        class_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade="七年级",
            stage="初中",
            current_grade="七年级",
            class_type="1v2",
            student_ids=[student_a, student_b],
        )
        small_class = lesson_manager.get_class(class_id)

        self.assertEqual(small_class["name"], "张李·1v2·七年级")
        self.assertEqual(small_class["class_type"], "1v2")
        self.assertEqual(small_class["class_number"], "")


if __name__ == "__main__":
    unittest.main()
