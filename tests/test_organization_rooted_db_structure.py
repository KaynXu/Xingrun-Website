import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager


class OrganizationRootedDBStructureTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_db_adds_direct_organization_columns_to_students_and_feedback_tasks(self):
        with lesson_manager.get_conn() as conn:
            student_columns = {
                row["name"]: row for row in conn.execute("PRAGMA table_info(students)").fetchall()
            }
            task_columns = {
                row["name"]: row for row in conn.execute("PRAGMA table_info(class_feedback_tasks)").fetchall()
            }
            student_fk = {
                row["from"]: row for row in conn.execute("PRAGMA foreign_key_list(students)").fetchall()
            }
            task_fk = {
                row["from"]: row for row in conn.execute("PRAGMA foreign_key_list(class_feedback_tasks)").fetchall()
            }

        self.assertIn("organization_id", student_columns)
        self.assertIn("organization_id", task_columns)
        self.assertEqual(student_columns["organization_id"]["notnull"], 1)
        self.assertEqual(task_columns["organization_id"]["notnull"], 1)
        self.assertEqual(student_fk["organization_id"]["table"], "organizations")
        self.assertEqual(task_fk["organization_id"]["table"], "organizations")
        self.assertEqual(student_fk["organization_id"]["on_delete"], "CASCADE")
        self.assertEqual(task_fk["organization_id"]["on_delete"], "CASCADE")

    def test_init_db_backfills_student_and_feedback_task_organization_scope(self):
        conn = sqlite3.connect(lesson_manager.DB_PATH)
        try:
            conn.executescript(
                """
                DROP TABLE IF EXISTS class_feedback_tasks;
                DROP TABLE IF EXISTS class_students;
                DROP TABLE IF EXISTS students;
                DROP TABLE IF EXISTS user_classes;
                DROP TABLE IF EXISTS classes;
                DROP TABLE IF EXISTS users;
                DROP TABLE IF EXISTS organizations;

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

                CREATE TABLE classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER REFERENCES organizations(id),
                    name TEXT NOT NULL,
                    subject TEXT DEFAULT '',
                    grade TEXT DEFAULT '',
                    teacher_name TEXT DEFAULT '',
                    teacher_email TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE class_students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                    student_id INTEGER NOT NULL REFERENCES students(id),
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    UNIQUE(class_id, student_id)
                );

                CREATE TABLE user_classes (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                    PRIMARY KEY (user_id, class_id)
                );

                CREATE TABLE class_feedback_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                    teacher_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    teacher_name_snapshot TEXT NOT NULL DEFAULT '',
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    period_length_days INTEGER NOT NULL DEFAULT 1,
                    period_granularity TEXT NOT NULL DEFAULT 'daily',
                    status TEXT NOT NULL DEFAULT 'draft',
                    class_summary_ai_draft TEXT NOT NULL DEFAULT '',
                    class_summary_final_text TEXT NOT NULL DEFAULT '',
                    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    updated_at TEXT DEFAULT (datetime('now','localtime')),
                    confirmed_at TEXT
                );

                INSERT INTO organizations (id, name) VALUES (1, 'Test Org');
                INSERT INTO users (id, username, password_hash, display_name, role, status, organization_id)
                VALUES (1, 'teacher', 'hash', 'Teacher', 'owner', 'active', 1);
                INSERT INTO classes (id, organization_id, name, subject, grade)
                VALUES (1, 1, '六年级 1 班', '数学', '六年级');
                INSERT INTO students (id, name) VALUES (1, '张三');
                INSERT INTO class_students (class_id, student_id) VALUES (1, 1);
                INSERT INTO user_classes (user_id, class_id) VALUES (1, 1);
                INSERT INTO class_feedback_tasks (
                    id, class_id, teacher_user_id, teacher_name_snapshot,
                    start_date, end_date, period_length_days, period_granularity,
                    status, class_summary_ai_draft, class_summary_final_text, created_by
                ) VALUES (
                    1, 1, 1, 'Teacher', '2026-04-01', '2026-04-01', 1, 'daily',
                    'draft', '', '', 1
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

        lesson_manager.init_db()

        with lesson_manager.get_conn() as conn:
            student_row = conn.execute("SELECT organization_id FROM students WHERE id=1").fetchone()
            task_row = conn.execute("SELECT organization_id FROM class_feedback_tasks WHERE id=1").fetchone()
            student_columns = {
                row["name"]: row for row in conn.execute("PRAGMA table_info(students)").fetchall()
            }
            task_columns = {
                row["name"]: row for row in conn.execute("PRAGMA table_info(class_feedback_tasks)").fetchall()
            }
            student_fk = {
                row["from"]: row for row in conn.execute("PRAGMA foreign_key_list(students)").fetchall()
            }
            task_fk = {
                row["from"]: row for row in conn.execute("PRAGMA foreign_key_list(class_feedback_tasks)").fetchall()
            }

        self.assertEqual(student_row["organization_id"], 1)
        self.assertEqual(task_row["organization_id"], 1)
        self.assertEqual(student_columns["organization_id"]["notnull"], 1)
        self.assertEqual(task_columns["organization_id"]["notnull"], 1)
        self.assertEqual(student_fk["organization_id"]["table"], "organizations")
        self.assertEqual(task_fk["organization_id"]["table"], "organizations")
        self.assertEqual(student_fk["organization_id"]["on_delete"], "CASCADE")
        self.assertEqual(task_fk["organization_id"]["on_delete"], "CASCADE")


if __name__ == "__main__":
    unittest.main()
