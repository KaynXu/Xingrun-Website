import contextlib
import hashlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import curriculum_registry
import lesson_manager
from scripts import manage_curriculum_registry


class CurriculumRegistryCliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template_dir = tempfile.TemporaryDirectory()
        cls.template_db = Path(cls.template_dir.name) / "curriculum-template.db"
        old_db = lesson_manager.DB_PATH
        try:
            lesson_manager.DB_PATH = cls.template_db
            lesson_manager.init_db()
            owner = lesson_manager.get_user_by_username("Kayn")
            with lesson_manager.get_conn() as conn:
                imported = curriculum_registry.import_curriculum_bundle(
                    conn,
                    curriculum_registry.load_bundle(),
                    actor_user_id=int(owner["id"]),
                )
            cls.version_id = int(imported["version"]["id"])
        finally:
            lesson_manager.DB_PATH = old_db

    @classmethod
    def tearDownClass(cls):
        cls.template_dir.cleanup()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.db_path = self.base / "test.db"
        with sqlite3.connect(self.template_db) as source, sqlite3.connect(
            self.db_path
        ) as destination:
            source.backup(destination)
        self.old_db = lesson_manager.DB_PATH
        lesson_manager.DB_PATH = self.db_path
        self.owner = lesson_manager.get_user_by_username("Kayn")
        with lesson_manager.get_conn() as conn:
            member = conn.execute(
                """
                INSERT INTO users (
                    username, password_hash, display_name, role, status,
                    organization_id
                ) VALUES (?, ?, ?, 'member', 'active', ?)
                """,
                (
                    "curriculum-cli-member",
                    lesson_manager.hash_password("member-password"),
                    "Curriculum CLI Member",
                    int(self.owner["organization_id"]),
                ),
            )
            self.member_id = int(member.lastrowid)

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        self.temp_dir.cleanup()

    def _run(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        caught = None
        status = None
        argv = ["manage_curriculum_registry.py", *map(str, args)]
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(
            stdout
        ), contextlib.redirect_stderr(stderr):
            try:
                status = manage_curriculum_registry.main()
            except BaseException as exc:  # Capture argparse exits and permission failures.
                caught = exc
        return status, stdout.getvalue(), stderr.getvalue(), caught

    @staticmethod
    def _json_after_runtime_output(stdout):
        start = stdout.find("{")
        if start < 0:
            raise AssertionError(f"missing JSON output: {stdout!r}")
        return json.loads(stdout[start:])

    def _schema_snapshot(self):
        with sqlite3.connect(self.db_path) as conn:
            schema_version = int(conn.execute("PRAGMA schema_version").fetchone()[0])
            schema = conn.execute(
                """
                SELECT type, name, tbl_name, sql
                FROM sqlite_master
                WHERE name NOT LIKE 'sqlite_%'
                ORDER BY type, name
                """
            ).fetchall()
        return schema_version, schema

    def test_database_commands_require_db_confirm_and_actor(self):
        status, _, stderr, caught = self._run("dry-run")
        self.assertIsNone(status)
        self.assertIsInstance(caught, SystemExit)
        self.assertEqual(caught.code, 2)
        self.assertIn("--db is required for database commands", stderr)

        status, _, stderr, caught = self._run("--db", self.db_path, "apply")
        self.assertIsNone(status)
        self.assertIsInstance(caught, SystemExit)
        self.assertEqual(caught.code, 2)
        self.assertIn(
            f"--confirm must equal {curriculum_registry.CURRICULUM_VERSION_KEY}",
            stderr,
        )

        status, _, stderr, caught = self._run(
            "--db",
            self.db_path,
            "--confirm",
            curriculum_registry.CURRICULUM_VERSION_KEY,
            "apply",
        )
        self.assertIsNone(status)
        self.assertIsInstance(caught, SystemExit)
        self.assertEqual(caught.code, 2)
        self.assertIn("--actor-user-id is required for database writes", stderr)
        self.assertEqual(
            list(self.base.glob("*.curriculum-backup-*")),
            [],
            "validation failures must happen before backup or mutation",
        )

    def test_non_super_owner_is_rejected(self):
        status, _, _, caught = self._run(
            "--db",
            self.db_path,
            "--confirm",
            curriculum_registry.CURRICULUM_VERSION_KEY,
            "--actor-user-id",
            self.member_id,
            "apply",
        )
        self.assertIsNone(status)
        self.assertIsInstance(caught, PermissionError)
        self.assertEqual(str(caught), "actor must be an active super owner")
        with sqlite3.connect(self.db_path) as conn:
            status = conn.execute(
                "SELECT status FROM curriculum_versions WHERE id=?",
                (self.version_id,),
            ).fetchone()[0]
        self.assertEqual(status, "draft")
        self.assertEqual(list(self.base.glob("*.curriculum-backup-*")), [])

    def test_dry_run_uses_read_only_connection_without_mtime_or_schema_changes(self):
        before_mtime = self.db_path.stat().st_mtime_ns
        before_hash = hashlib.sha256(self.db_path.read_bytes()).hexdigest()
        before_schema = self._schema_snapshot()
        before_sidecars = sorted(path.name for path in self.base.glob("test.db-*"))

        status, stdout, stderr, caught = self._run(
            "--db", self.db_path, "dry-run"
        )

        self.assertIsNone(caught)
        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertTrue(payload["installed"])
        self.assertEqual(payload["action"], "none")
        self.assertEqual(payload["bundle"]["node_total"], 2237)
        self.assertEqual(payload["bundle"]["edge_total"], 4007)
        self.assertEqual(self.db_path.stat().st_mtime_ns, before_mtime)
        self.assertEqual(
            hashlib.sha256(self.db_path.read_bytes()).hexdigest(), before_hash
        )
        self.assertEqual(self._schema_snapshot(), before_schema)
        self.assertEqual(
            sorted(path.name for path in self.base.glob("test.db-*")),
            before_sidecars,
        )

    def test_write_creates_verified_online_backup_and_reports_integrity(self):
        status, stdout, stderr, caught = self._run(
            "--db",
            self.db_path,
            "--confirm",
            curriculum_registry.CURRICULUM_VERSION_KEY,
            "--actor-user-id",
            int(self.owner["id"]),
            "apply",
        )

        self.assertIsNone(caught)
        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        payload = self._json_after_runtime_output(stdout)
        self.assertFalse(payload["changed"])
        self.assertEqual(
            payload["checks_before"],
            {"integrity_check": "ok", "foreign_key_check_count": 0},
        )
        self.assertEqual(
            payload["checks_after"],
            {"integrity_check": "ok", "foreign_key_check_count": 0},
        )
        backup_path = Path(payload["backup_path"])
        self.assertTrue(backup_path.is_file())
        self.assertEqual(backup_path.parent, self.db_path.resolve().parent)
        with sqlite3.connect(backup_path) as backup:
            self.assertEqual(backup.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(backup.execute("PRAGMA foreign_key_check").fetchall(), [])
            counts = backup.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM curriculum_nodes),
                    (SELECT COUNT(*) FROM curriculum_edges)
                """
            ).fetchone()
        self.assertEqual(counts, (2237, 4007))

        second_backup = manage_curriculum_registry._backup_database(str(self.db_path))
        self.assertNotEqual(backup_path, second_backup)
        self.assertTrue(second_backup.is_file())

    def test_atomic_write_preserves_existing_target_when_replace_fails(self):
        target = self.base / "atomic.json"
        target.write_bytes(b"original")
        with patch.object(
            manage_curriculum_registry.os,
            "replace",
            side_effect=OSError("injected replace failure"),
        ), self.assertRaisesRegex(OSError, "injected replace failure"):
            manage_curriculum_registry._atomic_write(target, b"replacement")
        self.assertEqual(target.read_bytes(), b"original")
        self.assertEqual(list(self.base.glob(".atomic.json.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
