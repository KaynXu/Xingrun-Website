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
        self.assertEqual(lesson_manager.get_class(class_id)["name"], "2025级·四年级·1班")

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

        self.assertEqual(updated["name"], "四年级·1班")
        self.assertEqual(updated["show_cohort_year"], False)


if __name__ == "__main__":
    unittest.main()
