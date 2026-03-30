import sys
import tempfile
import sqlite3
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

    def _approve_user(self, username: str, display_name: str, password: str):
        request_row = lesson_manager.create_registration_request(
            username=username,
            display_name=display_name,
            password=password,
        )
        return lesson_manager.approve_registration_request(request_row["id"], self.owner["id"])

    def _count_rows(self, table_name: str, where_clause: str = "", params=()):
        query = f"SELECT COUNT(*) AS count FROM {table_name}"
        if where_clause:
            query = f"{query} WHERE {where_clause}"
        with lesson_manager.get_conn() as conn:
            row = conn.execute(query, params).fetchone()
        return row["count"]

    def _create_legacy_master_data_schema(self):
        conn = sqlite3.connect(lesson_manager.DB_PATH)
        try:
            conn.executescript(
                """
                PRAGMA foreign_keys = OFF;

                CREATE TABLE classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    subject TEXT DEFAULT '',
                    grade TEXT DEFAULT '',
                    teacher_name TEXT DEFAULT '',
                    teacher_email TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    subject TEXT,
                    grade TEXT,
                    topic TEXT,
                    summary TEXT,
                    weak_points TEXT,
                    plan_json TEXT,
                    pdf_path TEXT,
                    class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lesson_id INTEGER NOT NULL,
                    question TEXT,
                    answer TEXT,
                    category TEXT,
                    day_num INTEGER,
                    FOREIGN KEY (lesson_id) REFERENCES lessons(id)
                );

                CREATE TABLE organizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    status TEXT NOT NULL DEFAULT 'active',
                    organization_id INTEGER NOT NULL REFERENCES organizations(id),
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE registration_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    organization_id INTEGER NOT NULL REFERENCES organizations(id),
                    status TEXT NOT NULL DEFAULT 'pending',
                    reviewed_by INTEGER REFERENCES users(id),
                    reviewed_at TEXT,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE auth_sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE user_classes (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                    PRIMARY KEY (user_id, class_id)
                );

                CREATE TABLE user_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    alias TEXT NOT NULL,
                    normalized_alias TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    UNIQUE(user_id, normalized_alias)
                );

                CREATE INDEX idx_user_aliases_normalized_alias
                ON user_aliases(normalized_alias);

                CREATE TABLE class_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                    alias TEXT NOT NULL,
                    normalized_alias TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    UNIQUE(class_id, normalized_alias)
                );

                CREATE INDEX idx_class_aliases_normalized_alias
                ON class_aliases(normalized_alias);

                CREATE TABLE wrong_question_mappings (
                    record_id TEXT PRIMARY KEY,
                    teacher_user_id INTEGER REFERENCES users(id),
                    class_id INTEGER REFERENCES classes(id),
                    teacher_name_snapshot TEXT DEFAULT '',
                    class_name_snapshot TEXT DEFAULT '',
                    subject_snapshot TEXT DEFAULT '',
                    mapping_status TEXT NOT NULL DEFAULT 'unmapped',
                    reviewed_by INTEGER REFERENCES users(id),
                    reviewed_at TEXT,
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    updated_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE master_data_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_key TEXT NOT NULL,
                    action TEXT NOT NULL,
                    before_json TEXT NOT NULL,
                    after_json TEXT NOT NULL,
                    actor_user_id INTEGER REFERENCES users(id),
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                PRAGMA foreign_keys = ON;
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _get_foreign_key_actions(self, table_name: str) -> dict[str, str]:
        with lesson_manager.get_conn() as conn:
            rows = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
        return {row[3]: row[6] for row in rows}

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

    def test_normalize_wrong_question_record_keeps_conflicting_pair_non_final(self):
        other_teacher = self._approve_user(
            username="teacher_conflict",
            display_name="Teacher Conflict",
            password="teacher123",
        )
        class_id = lesson_manager.save_class("六年级 冲刺班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, self.owner["id"])

        master_data.set_user_aliases(
            actor_user_id=self.owner["id"],
            user_id=other_teacher["id"],
            aliases=["Conflict Teacher"],
        )
        master_data.set_class_aliases(
            actor_user_id=self.owner["id"],
            class_id=class_id,
            aliases=["Sprint Math"],
        )

        normalized = master_data.normalize_wrong_question_record(
            {
                "id": "record-conflict-1",
                "teacher_name": "Conflict Teacher",
                "class_name": "Sprint Math",
                "subject": "数学",
            }
        )

        self.assertEqual(normalized["teacher_user_id"], other_teacher["id"])
        self.assertEqual(normalized["class_id"], class_id)
        self.assertEqual(normalized["mapping_status"], "needs_review")

        persisted = master_data.get_wrong_question_mapping("record-conflict-1")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["teacher_user_id"], other_teacher["id"])
        self.assertEqual(persisted["class_id"], class_id)
        self.assertEqual(persisted["mapping_status"], "needs_review")

    def test_normalize_wrong_question_record_does_not_fall_back_to_name_only_class_match_when_subject_conflicts(self):
        class_id = lesson_manager.save_class("六年级 冲刺班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, self.owner["id"])

        master_data.set_user_aliases(
            actor_user_id=self.owner["id"],
            user_id=self.owner["id"],
            aliases=["Kayn 老师"],
        )
        master_data.set_class_aliases(
            actor_user_id=self.owner["id"],
            class_id=class_id,
            aliases=["Sprint Math"],
        )

        normalized = master_data.normalize_wrong_question_record(
            {
                "id": "record-subject-conflict-1",
                "teacher_name": "Kayn 老师",
                "class_name": "Sprint Math",
                "subject": "英语",
            }
        )

        self.assertEqual(normalized["teacher_user_id"], self.owner["id"])
        self.assertEqual(normalized["teacher_display_name"], "Kayn")
        self.assertIsNone(normalized["class_id"])
        self.assertEqual(normalized["class_display_name"], "Sprint Math")
        self.assertEqual(normalized["mapping_status"], "unmapped")

        persisted = master_data.get_wrong_question_mapping("record-subject-conflict-1")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["teacher_user_id"], self.owner["id"])
        self.assertIsNone(persisted["class_id"])
        self.assertEqual(persisted["mapping_status"], "unmapped")

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

    def test_delete_class_requeues_invalidated_mapped_wrong_question_mapping(self):
        class_id = lesson_manager.save_class("六年级 5 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, self.owner["id"])

        master_data.upsert_wrong_question_mapping(
            "record-repair-1",
            teacher_user_id=self.owner["id"],
            class_id=class_id,
            teacher_name_snapshot="Kayn 老师",
            class_name_snapshot="六年级5班",
            subject_snapshot="数学",
            mapping_status="mapped",
            reviewed_by=self.owner["id"],
        )

        lesson_manager.delete_class(class_id)

        mapping = master_data.get_wrong_question_mapping("record-repair-1")
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["mapping_status"], "needs_review")
        self.assertIsNone(mapping["class_id"])
        self.assertEqual(mapping["teacher_user_id"], self.owner["id"])
        self.assertIsNone(mapping["reviewed_by"])

        queue = master_data.list_wrong_question_mapping_queue()
        self.assertEqual([item["record_id"] for item in queue], ["record-repair-1"])
        self.assertEqual(queue[0]["mapping_status"], "needs_review")

    def test_resolve_wrong_question_mapping_non_final_status_does_not_merge_aliases(self):
        other_teacher = self._approve_user(
            username="teacher_review_only",
            display_name="Teacher Review",
            password="teacher123",
        )
        class_id = lesson_manager.save_class("六年级 提高班", subject="数学", grade="六年级")

        master_data.upsert_wrong_question_mapping(
            "record-review-only",
            teacher_name_snapshot="Review Alias Teacher",
            class_name_snapshot="Review Alias Class",
            subject_snapshot="数学",
            mapping_status="needs_review",
        )

        resolved = master_data.resolve_wrong_question_mapping(
            actor_user_id=self.owner["id"],
            record_id="record-review-only",
            teacher_user_id=other_teacher["id"],
            class_id=class_id,
            mapping_status="needs_review",
        )

        self.assertEqual(resolved["mapping_status"], "needs_review")
        self.assertEqual(master_data.list_user_aliases(other_teacher["id"]), [])
        self.assertEqual(master_data.list_class_aliases(class_id), [])

    def test_init_db_migrates_legacy_master_data_foreign_keys(self):
        self.temp_dir.cleanup()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})

        self._create_legacy_master_data_schema()

        self.assertEqual(
            self._get_foreign_key_actions("wrong_question_mappings"),
            {
                "reviewed_by": "NO ACTION",
                "class_id": "NO ACTION",
                "teacher_user_id": "NO ACTION",
            },
        )
        self.assertEqual(
            self._get_foreign_key_actions("master_data_audit_log"),
            {"actor_user_id": "NO ACTION"},
        )

        lesson_manager.init_db()

        self.assertEqual(
            self._get_foreign_key_actions("wrong_question_mappings"),
            {
                "reviewed_by": "SET NULL",
                "class_id": "SET NULL",
                "teacher_user_id": "SET NULL",
            },
        )
        self.assertEqual(
            self._get_foreign_key_actions("master_data_audit_log"),
            {"actor_user_id": "SET NULL"},
        )


if __name__ == "__main__":
    unittest.main()