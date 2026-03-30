import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager
import master_data


class MasterDataStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.owner = lesson_manager.get_user_by_username("Kayn")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_alias_round_trip_and_wrong_question_mapping_suggestion(self):
        class_id = lesson_manager.save_class("六年级 1 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, self.owner["id"])

        master_data.set_user_aliases(
            actor_user_id=self.owner["id"],
            user_id=self.owner["id"],
            aliases=["Kayn 老师", "Wendy Wang"],
        )
        master_data.set_class_aliases(
            actor_user_id=self.owner["id"],
            class_id=class_id,
            aliases=["六年级1班", "G6 Math A"],
        )

        self.assertEqual(
            master_data.list_user_aliases(self.owner["id"]),
            ["Kayn 老师", "Wendy Wang"],
        )
        self.assertEqual(
            master_data.list_class_aliases(class_id),
            ["G6 Math A", "六年级1班"],
        )

        suggestion = master_data.suggest_wrong_question_mapping(
            {
                "id": "record-1",
                "teacher_name": "Wendy Wang",
                "class_name": "六年级1班",
                "subject": "数学",
            }
        )

        self.assertEqual(suggestion["mapping_status"], "mapped")
        self.assertEqual(suggestion["teacher_user_id"], self.owner["id"])
        self.assertEqual(suggestion["class_id"], class_id)
        self.assertEqual(suggestion["teacher_display_name"], "Kayn")
        self.assertEqual(suggestion["class_display_name"], "六年级 1 班")


if __name__ == "__main__":
    unittest.main()