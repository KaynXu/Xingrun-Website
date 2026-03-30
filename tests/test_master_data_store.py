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

    def _count_rows(self, table_name: str, where_clause: str = "", params=()):
        query = f"SELECT COUNT(*) AS count FROM {table_name}"
        if where_clause:
            query = f"{query} WHERE {where_clause}"
        with lesson_manager.get_conn() as conn:
            row = conn.execute(query, params).fetchone()
        return row["count"]

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

    def test_foreign_keys_are_enabled_and_class_aliases_cascade_on_delete(self):
        with lesson_manager.get_conn() as conn:
            pragma_row = conn.execute("PRAGMA foreign_keys").fetchone()
        self.assertEqual(pragma_row[0], 1)

        class_id = lesson_manager.save_class("六年级 2 班", subject="数学", grade="六年级")
        master_data.set_class_aliases(
            actor_user_id=self.owner["id"],
            class_id=class_id,
            aliases=["六年级2班", "G6 Math B"],
        )

        self.assertEqual(
            self._count_rows("class_aliases", "class_id=?", (class_id,)),
            2,
        )

        lesson_manager.delete_class(class_id)

        self.assertEqual(
            self._count_rows("class_aliases", "class_id=?", (class_id,)),
            0,
        )

    def test_upsert_wrong_question_mapping_persists_mapping_and_audit_log(self):
        class_id = lesson_manager.save_class("六年级 3 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, self.owner["id"])

        mapping = master_data.upsert_wrong_question_mapping(
            "record-42",
            teacher_user_id=self.owner["id"],
            class_id=class_id,
            teacher_name_snapshot="Kayn 老师",
            class_name_snapshot="六年级3班",
            subject_snapshot="数学",
            mapping_status="mapped",
            reviewed_by=self.owner["id"],
        )

        self.assertEqual(mapping["record_id"], "record-42")
        self.assertEqual(mapping["teacher_user_id"], self.owner["id"])
        self.assertEqual(mapping["class_id"], class_id)
        self.assertEqual(mapping["mapping_status"], "mapped")
        self.assertEqual(mapping["teacher_display_name"], "Kayn")
        self.assertEqual(mapping["class_display_name"], "六年级 3 班")

        persisted = master_data.get_wrong_question_mapping("record-42")
        self.assertEqual(persisted["record_id"], "record-42")
        self.assertEqual(persisted["teacher_name_snapshot"], "Kayn 老师")
        self.assertEqual(persisted["class_name_snapshot"], "六年级3班")
        self.assertEqual(persisted["subject_snapshot"], "数学")

        with lesson_manager.get_conn() as conn:
            audit_row = conn.execute(
                """
                SELECT entity_type, entity_key, action, before_json, after_json, actor_user_id
                FROM master_data_audit_log
                WHERE entity_type=? AND entity_key=?
                ORDER BY id DESC
                LIMIT 1
                """,
                ("wrong_question_mapping", "record-42"),
            ).fetchone()

        self.assertIsNotNone(audit_row)
        self.assertEqual(audit_row["entity_type"], "wrong_question_mapping")
        self.assertEqual(audit_row["entity_key"], "record-42")
        self.assertEqual(audit_row["action"], "upsert")
        self.assertEqual(audit_row["actor_user_id"], self.owner["id"])
        self.assertEqual(audit_row["before_json"], "null")
        self.assertIn('"mapping_status": "mapped"', audit_row["after_json"])
        self.assertIn(f'"class_id": {class_id}', audit_row["after_json"])

    def test_delete_class_clears_wrong_question_mapping_class_reference(self):
        class_id = lesson_manager.save_class("六年级 4 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, self.owner["id"])

        master_data.upsert_wrong_question_mapping(
            "record-99",
            teacher_user_id=self.owner["id"],
            class_id=class_id,
            teacher_name_snapshot="Kayn 老师",
            class_name_snapshot="六年级4班",
            subject_snapshot="数学",
            mapping_status="mapped",
            reviewed_by=self.owner["id"],
        )

        lesson_manager.delete_class(class_id)

        mapping = master_data.get_wrong_question_mapping("record-99")
        self.assertIsNotNone(mapping)
        self.assertIsNone(mapping["class_id"])
        self.assertEqual(mapping["class_name_snapshot"], "六年级4班")


if __name__ == "__main__":
    unittest.main()