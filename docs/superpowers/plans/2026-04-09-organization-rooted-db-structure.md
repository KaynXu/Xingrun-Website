# Organization-Rooted DB Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `organizations` the clear root of the SQLite schema by adding direct tenant ownership to `students` and `class_feedback_tasks`, then updating write paths, migration logic, and verification around that ownership.

**Architecture:** Keep the existing `lesson_manager.py` schema bootstrap style and implement this as an additive migration. Fresh databases should create the new columns with direct foreign keys from the start, while existing databases should be upgraded by `init_db()` through safe column-add + backfill logic. Creation paths should stop inferring tenant ownership late and instead write `organization_id` directly from the owning class.

**Tech Stack:** Python 3.12, SQLite, `unittest`, existing `lesson_manager.py` migration helpers

---

### Task 1: Lock the schema and migration outcome with red tests

**Files:**
- Create: `tests/test_organization_rooted_db_structure.py`
- Modify: `lesson_manager.py`
- Test: `tests/test_organization_rooted_db_structure.py`

- [ ] **Step 1: Write the failing schema-column test**

```python
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
            student_columns = {row["name"] for row in conn.execute("PRAGMA table_info(students)").fetchall()}
            task_columns = {row["name"] for row in conn.execute("PRAGMA table_info(class_feedback_tasks)").fetchall()}
            student_fk = {row["from"]: row["table"] for row in conn.execute("PRAGMA foreign_key_list(students)").fetchall()}
            task_fk = {row["from"]: row["table"] for row in conn.execute("PRAGMA foreign_key_list(class_feedback_tasks)").fetchall()}

        self.assertIn("organization_id", student_columns)
        self.assertIn("organization_id", task_columns)
        self.assertEqual(student_fk["organization_id"], "organizations")
        self.assertEqual(task_fk["organization_id"], "organizations")
```

- [ ] **Step 2: Write the failing backfill test for legacy rows**

```python
import sqlite3


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

        self.assertEqual(student_row["organization_id"], 1)
        self.assertEqual(task_row["organization_id"], 1)
```

- [ ] **Step 3: Run the focused test file to verify RED**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/org-rooted-db-structure && .venv/bin/python -m unittest tests.test_organization_rooted_db_structure -v`

Expected: FAIL because `students` and `class_feedback_tasks` do not yet expose or backfill `organization_id`.

- [ ] **Step 4: Write the minimal schema and migration implementation**

```python
def _backfill_student_organization_scope(conn: sqlite3.Connection, fallback_organization_id: int) -> None:
    _ensure_column(conn, "students", "organization_id", "INTEGER REFERENCES organizations(id)")
    conn.execute(
        """
        UPDATE students
        SET organization_id=COALESCE(
            organization_id,
            (
                SELECT c.organization_id
                FROM class_students cs
                JOIN classes c ON c.id = cs.class_id
                WHERE cs.student_id = students.id
                ORDER BY cs.id
                LIMIT 1
            ),
            ?
        )
        WHERE organization_id IS NULL
        """,
        (fallback_organization_id,),
    )


def _backfill_class_feedback_task_organization_scope(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "class_feedback_tasks", "organization_id", "INTEGER REFERENCES organizations(id)")
    conn.execute(
        """
        UPDATE class_feedback_tasks
        SET organization_id=COALESCE(
            organization_id,
            (SELECT c.organization_id FROM classes c WHERE c.id = class_feedback_tasks.class_id)
        )
        WHERE organization_id IS NULL
        """
    )
```

```python
CREATE TABLE IF NOT EXISTS students (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS class_feedback_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
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
    class_status_tags_json TEXT NOT NULL DEFAULT '[]',
    class_status_note TEXT NOT NULL DEFAULT '',
    parent_feedback_note TEXT NOT NULL DEFAULT '',
    teaching_focus_note TEXT NOT NULL DEFAULT '',
    next_stage_preview_note TEXT NOT NULL DEFAULT '',
    student_highlights_json TEXT NOT NULL DEFAULT '[]',
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    confirmed_at TEXT
);
```

- [ ] **Step 5: Call the helpers from `init_db()` after organization bootstrap**

```python
        _migrate_legacy_organization_scope(conn)
        _bootstrap_account_state(conn)
        default_org = _ensure_organization(conn, DEFAULT_ORGANIZATION_NAME)
        _backfill_student_organization_scope(conn, default_org["id"])
        _backfill_class_feedback_task_organization_scope(conn)
```

- [ ] **Step 6: Run the focused test file to verify GREEN**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/org-rooted-db-structure && .venv/bin/python -m unittest tests.test_organization_rooted_db_structure -v`

Expected: PASS with `Ran 2 tests` and `OK`.

- [ ] **Step 7: Commit**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/org-rooted-db-structure
git add lesson_manager.py tests/test_organization_rooted_db_structure.py
git commit -m "feat: add organization-rooted schema migration"
```

### Task 2: Update student writes to persist direct organization ownership

**Files:**
- Modify: `lesson_manager.py`
- Modify: `tests/test_class_feedback_store.py`
- Modify: `tests/test_organization_rooted_db_structure.py`
- Test: `tests/test_class_feedback_store.py`
- Test: `tests/test_organization_rooted_db_structure.py`

- [ ] **Step 1: Write the failing student-write tests**

```python
    def test_create_student_for_class_persists_class_organization_id(self):
        owner = self._owner()
        class_id = lesson_manager.save_class(
            "S01A1",
            subject="英语",
            grade="六年级",
            organization_id=owner["organization_id"],
        )

        student = lesson_manager.create_student_for_class(class_id, "张三")

        self.assertEqual(student["organization_id"], owner["organization_id"])
```

```python
    def test_student_backfill_rejects_cross_organization_class_links(self):
        with lesson_manager.get_conn() as conn:
            other_org = conn.execute(
                "INSERT INTO organizations (name) VALUES ('Second Org')"
            ).lastrowid
            conn.execute(
                "INSERT INTO classes (organization_id, name, subject, grade) VALUES (?, 'A 班', '数学', '六年级')",
                (other_org,),
            )
            conn.execute(
                "INSERT INTO students (id, name) VALUES (99, '冲突学生')"
            )
            conn.execute(
                "INSERT INTO class_students (class_id, student_id) VALUES (1, 99)"
            )
            conn.execute(
                "INSERT INTO class_students (class_id, student_id) VALUES (2, 99)"
            )

        with self.assertRaisesRegex(ValueError, "student organization scope conflict"):
            lesson_manager.init_db()
```

- [ ] **Step 2: Run the targeted tests to verify RED**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/org-rooted-db-structure && .venv/bin/python -m unittest tests.test_class_feedback_store.ClassFeedbackStoreTestCase.test_create_task_derives_granularity_and_teacher_snapshot tests.test_class_feedback_store.ClassFeedbackStoreTestCase.test_create_student_for_class_persists_class_organization_id tests.test_organization_rooted_db_structure.OrganizationRootedDBStructureTestCase.test_student_backfill_rejects_cross_organization_class_links -v`

Expected: FAIL because students are still inserted without explicit organization ownership and conflict detection does not yet exist.

- [ ] **Step 3: Implement the minimal student ownership write path**

```python
def create_student_for_class(class_id: int, raw_name: str):
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        class_row = conn.execute(
            "SELECT id, organization_id FROM classes WHERE id=?",
            (class_id,),
        ).fetchone()
        if not class_row:
            raise LookupError("class not found")

        student_name = _dedupe_student_name_in_class(class_id, raw_name, conn=conn)
        cur = conn.execute(
            "INSERT INTO students (organization_id, name) VALUES (?, ?)",
            (class_row["organization_id"], student_name),
        )
        student_id = cur.lastrowid
        conn.execute(
            "INSERT INTO class_students (class_id, student_id) VALUES (?, ?)",
            (class_id, student_id),
        )
        row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    return dict(row)
```

```python
def _backfill_student_organization_scope(conn: sqlite3.Connection, fallback_organization_id: int) -> None:
    _ensure_column(conn, "students", "organization_id", "INTEGER REFERENCES organizations(id)")
    conflict_rows = conn.execute(
        """
        SELECT cs.student_id
        FROM class_students cs
        JOIN classes c ON c.id = cs.class_id
        GROUP BY cs.student_id
        HAVING COUNT(DISTINCT c.organization_id) > 1
        """
    ).fetchall()
    if conflict_rows:
        raise ValueError("student organization scope conflict")
    conn.execute(
        """
        UPDATE students
        SET organization_id=COALESCE(
            organization_id,
            (
                SELECT c.organization_id
                FROM class_students cs
                JOIN classes c ON c.id = cs.class_id
                WHERE cs.student_id = students.id
                ORDER BY cs.id
                LIMIT 1
            ),
            ?
        )
        WHERE organization_id IS NULL
        """,
        (fallback_organization_id,),
    )
```

- [ ] **Step 4: Strengthen returned assertions in the class feedback tests**

```python
        self.assertEqual(task["class_id"], class_id)
        self.assertEqual(task["organization_id"], owner["organization_id"])
        self.assertEqual(task["period_length_days"], 1)
```

- [ ] **Step 5: Run the targeted tests to verify GREEN**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/org-rooted-db-structure && .venv/bin/python -m unittest tests.test_class_feedback_store.ClassFeedbackStoreTestCase.test_create_task_derives_granularity_and_teacher_snapshot tests.test_class_feedback_store.ClassFeedbackStoreTestCase.test_create_student_for_class_persists_class_organization_id tests.test_organization_rooted_db_structure.OrganizationRootedDBStructureTestCase.test_student_backfill_rejects_cross_organization_class_links -v`

Expected: PASS with `Ran 3 tests` and `OK`.

- [ ] **Step 6: Commit**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/org-rooted-db-structure
git add lesson_manager.py tests/test_class_feedback_store.py tests/test_organization_rooted_db_structure.py
git commit -m "feat: persist student organization ownership"
```

### Task 3: Persist `organization_id` on class feedback tasks and guard cross-org writes

**Files:**
- Modify: `lesson_manager.py`
- Modify: `tests/test_class_feedback_store.py`
- Modify: `tests/test_organization_rooted_db_structure.py`
- Test: `tests/test_class_feedback_store.py`
- Test: `tests/test_organization_rooted_db_structure.py`

- [ ] **Step 1: Write the failing feedback-task tests**

```python
    def test_create_task_persists_class_organization_id(self):
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

        self.assertEqual(task["organization_id"], owner["organization_id"])
```

```python
    def test_create_task_rejects_creator_from_other_organization(self):
        owner = self._owner()
        with lesson_manager.get_conn() as conn:
            second_org_id = conn.execute(
                "INSERT INTO organizations (name) VALUES ('Org B')"
            ).lastrowid
            conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
                VALUES ('other-owner', 'hash', 'Other Owner', 'owner', 'active', ?)
                """,
                (second_org_id,),
            )
            other_owner_id = conn.execute(
                "SELECT id FROM users WHERE username='other-owner'"
            ).fetchone()["id"]

        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner["id"])

        with self.assertRaisesRegex(ValueError, "created_by does not belong to class organization"):
            lesson_manager.create_class_feedback_task(
                class_id=class_id,
                teacher_user_id=owner["id"],
                teacher_name_snapshot=owner["display_name"],
                start_date="2026-04-03",
                end_date="2026-04-03",
                created_by=other_owner_id,
            )
```

- [ ] **Step 2: Run the targeted tests to verify RED**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/org-rooted-db-structure && .venv/bin/python -m unittest tests.test_class_feedback_store.ClassFeedbackStoreTestCase.test_create_task_persists_class_organization_id tests.test_organization_rooted_db_structure.OrganizationRootedDBStructureTestCase.test_create_task_rejects_creator_from_other_organization -v`

Expected: FAIL because `create_class_feedback_task()` does not yet insert or validate task organization ownership.

- [ ] **Step 3: Implement the minimal task ownership write path**

```python
def create_class_feedback_task(
    *,
    class_id: int,
    teacher_user_id: Optional[int],
    teacher_name_snapshot: str,
    start_date: str,
    end_date: str,
    created_by: int,
):
    teacher_name_snapshot = (teacher_name_snapshot or "").strip()
    if not teacher_name_snapshot:
        raise ValueError("teacher_name_snapshot is required")
    period_length_days, period_granularity = _derive_class_feedback_period_fields(start_date, end_date)
    with get_conn() as conn:
        class_row = conn.execute(
            "SELECT id, organization_id FROM classes WHERE id=?",
            (class_id,),
        ).fetchone()
        if not class_row:
            raise LookupError("class not found")
        creator_row = conn.execute(
            "SELECT id, organization_id FROM users WHERE id=?",
            (created_by,),
        ).fetchone()
        if not creator_row:
            raise LookupError("user not found")
        if int(creator_row["organization_id"]) != int(class_row["organization_id"]):
            raise ValueError("created_by does not belong to class organization")
        if teacher_user_id is not None:
            teacher_row = conn.execute(
                "SELECT id, organization_id FROM users WHERE id=?",
                (teacher_user_id,),
            ).fetchone()
            if not teacher_row:
                raise LookupError("user not found")
            if int(teacher_row["organization_id"]) != int(class_row["organization_id"]):
                raise ValueError("teacher_user_id does not belong to class organization")
            _validate_class_feedback_teacher_binding(
                conn,
                class_id=class_id,
                teacher_user_id=teacher_user_id,
            )
        cur = conn.execute(
            """
            INSERT INTO class_feedback_tasks (
                organization_id, class_id, teacher_user_id, teacher_name_snapshot,
                start_date, end_date, period_length_days, period_granularity,
                status, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)
            """,
            (
                class_row["organization_id"],
                class_id,
                teacher_user_id,
                teacher_name_snapshot,
                start_date,
                end_date,
                period_length_days,
                period_granularity,
                created_by,
            ),
        )
        task_id = cur.lastrowid
    return get_class_feedback_task(task_id)
```

- [ ] **Step 4: Run the targeted tests to verify GREEN**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/org-rooted-db-structure && .venv/bin/python -m unittest tests.test_class_feedback_store.ClassFeedbackStoreTestCase.test_create_task_persists_class_organization_id tests.test_organization_rooted_db_structure.OrganizationRootedDBStructureTestCase.test_create_task_rejects_creator_from_other_organization -v`

Expected: PASS with `Ran 2 tests` and `OK`.

- [ ] **Step 5: Commit**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/org-rooted-db-structure
git add lesson_manager.py tests/test_class_feedback_store.py tests/test_organization_rooted_db_structure.py
git commit -m "feat: scope class feedback tasks to organizations"
```

### Task 4: Add organization-leading indexes and final regression coverage

**Files:**
- Modify: `lesson_manager.py`
- Modify: `tests/test_organization_rooted_db_structure.py`
- Test: `tests/test_organization_rooted_db_structure.py`
- Test: `tests/test_class_feedback_store.py`
- Test: `tests/test_account_flow.py`

- [ ] **Step 1: Write the failing index and organization-deletion tests**

```python
    def test_init_db_creates_organization_root_indexes(self):
        with lesson_manager.get_conn() as conn:
            indexes = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%organization_%'"
                ).fetchall()
            }

        self.assertIn("idx_students_organization_name", indexes)
        self.assertIn("idx_class_feedback_tasks_organization_status_updated", indexes)
```

```python
    def test_delete_organization_removes_direct_owned_students_and_feedback_tasks(self):
        with lesson_manager.get_conn() as conn:
            org_id = conn.execute(
                "INSERT INTO organizations (name) VALUES ('Delete Me Org')"
            ).lastrowid
            conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
                VALUES ('delete-owner', 'hash', 'Delete Owner', 'owner', 'active', ?)
                """,
                (org_id,),
            )
            owner_id = conn.execute(
                "SELECT id FROM users WHERE username='delete-owner'"
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO classes (organization_id, name, subject, grade) VALUES (?, 'Delete Class', '数学', '六年级')",
                (org_id,),
            )
            class_id = conn.execute("SELECT id FROM classes WHERE name='Delete Class'").fetchone()["id"]
            conn.execute(
                "INSERT INTO user_classes (user_id, class_id) VALUES (?, ?)",
                (owner_id, class_id),
            )
            conn.execute(
                "INSERT INTO students (organization_id, name) VALUES (?, 'Delete Student')",
                (org_id,),
            )
            student_id = conn.execute(
                "SELECT id FROM students WHERE name='Delete Student'"
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO class_students (class_id, student_id) VALUES (?, ?)",
                (class_id, student_id),
            )
            conn.execute(
                """
                INSERT INTO class_feedback_tasks (
                    organization_id, class_id, teacher_user_id, teacher_name_snapshot,
                    start_date, end_date, period_length_days, period_granularity,
                    status, created_by
                ) VALUES (?, ?, ?, 'Delete Owner', '2026-04-03', '2026-04-03', 1, 'daily', 'draft', ?)
                """,
                (org_id, class_id, owner_id, owner_id),
            )

        lesson_manager.delete_organization(org_id)

        with lesson_manager.get_conn() as conn:
            student_count = conn.execute(
                "SELECT COUNT(*) AS c FROM students WHERE organization_id=?",
                (org_id,),
            ).fetchone()["c"]
            task_count = conn.execute(
                "SELECT COUNT(*) AS c FROM class_feedback_tasks WHERE organization_id=?",
                (org_id,),
            ).fetchone()["c"]

        self.assertEqual(student_count, 0)
        self.assertEqual(task_count, 0)
```

- [ ] **Step 2: Run the focused regression suite to verify RED**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/org-rooted-db-structure && .venv/bin/python -m unittest tests.test_organization_rooted_db_structure.OrganizationRootedDBStructureTestCase.test_init_db_creates_organization_root_indexes tests.test_organization_rooted_db_structure.OrganizationRootedDBStructureTestCase.test_delete_organization_removes_direct_owned_students_and_feedback_tasks -v`

Expected: FAIL because the new indexes do not exist yet and deletion behavior has not been explicitly verified against the direct-owned rows.

- [ ] **Step 3: Add the minimal indexes and any deletion cleanup needed**

```python
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_students_organization_name
            ON students(organization_id, name);

            CREATE INDEX IF NOT EXISTS idx_classes_organization_grade_subject_name
            ON classes(organization_id, grade, subject, name);

            CREATE INDEX IF NOT EXISTS idx_lessons_organization_class_date
            ON lessons(organization_id, class_id, date);

            CREATE INDEX IF NOT EXISTS idx_consultations_organization_assigned_updated
            ON consultations(organization_id, assigned_user_id, updated_at);

            CREATE INDEX IF NOT EXISTS idx_class_feedback_tasks_organization_status_updated
            ON class_feedback_tasks(organization_id, status, updated_at);

            CREATE INDEX IF NOT EXISTS idx_wrong_question_submissions_organization_class_teacher_status
            ON wrong_question_submissions(organization_id, class_id, teacher_user_id, status);
            """
        )
```

```python
        conn.execute(
            "DELETE FROM class_feedback_tasks WHERE organization_id=?",
            (org_id,),
        )
        conn.execute(
            "DELETE FROM students WHERE organization_id=?",
            (org_id,),
        )
```

- [ ] **Step 4: Run the full verification bundle**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/org-rooted-db-structure && .venv/bin/python -m unittest tests.test_organization_rooted_db_structure tests.test_class_feedback_store tests.test_db_path_resolution tests.test_account_flow -v`

Expected: all new organization-rooted tests pass; any remaining failures should match the current known baseline in `tests.test_master_data_store` only if that module is intentionally excluded.

- [ ] **Step 5: Commit**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/org-rooted-db-structure
git add lesson_manager.py tests/test_organization_rooted_db_structure.py tests/test_class_feedback_store.py
git commit -m "feat: add organization-rooted indexes and regressions"
```

## Notes For Execution

- Use `.venv/bin/python` inside the worktree created at `/Users/ark.mini/Desktop/Xingrun-Website/.worktrees/org-rooted-db-structure`.
- Do not touch the unrelated `tests.test_master_data_store` red tests in this feature unless the organization-rooted work makes one of them move unexpectedly.
- Keep `data/xingrun.db`, generated PDFs, and `__pycache__` out of commits.
