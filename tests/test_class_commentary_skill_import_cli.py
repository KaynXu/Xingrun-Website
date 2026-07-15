import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import lesson_manager
from scripts import import_class_commentary_skills


class ClassCommentarySkillImportCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_manifest(self, payload, filename="manifest.json"):
        path = self.root / filename
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _run_main(self, manifest_path):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = import_class_commentary_skills.main([str(manifest_path)])
        return status, stdout.getvalue(), stderr.getvalue()

    def test_array_manifest_resolves_relative_path_and_preserves_explicit_absolute_path(self):
        absolute_path = str(self.root / "absolute.skill")
        manifest_path = self._write_manifest(
            [
                {
                    "organization_id": 1,
                    "skill_id": "relative",
                    "actor_user_id": 11,
                    "source_path": "skills/relative.skill",
                },
                {
                    "organization_id": 2,
                    "skill_id": "absolute",
                    "actor_user_id": 22,
                    "source_path": absolute_path,
                },
            ]
        )
        imported_results = [
            {"registry_id": 101, "active_version_id": 201},
            {"registry_id": 102, "active_version_id": 202},
        ]

        with mock.patch.object(lesson_manager, "init_db") as init_db, mock.patch.object(
            lesson_manager,
            "import_class_commentary_skill_manifest",
            side_effect=imported_results,
        ) as import_skill:
            status, stdout, stderr = self._run_main(manifest_path)

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        init_db.assert_called_once_with()
        self.assertEqual(
            import_skill.call_args_list,
            [
                mock.call(
                    organization_id=1,
                    skill_id="relative",
                    actor_user_id=11,
                    source_path=str((self.root / "skills/relative.skill").resolve()),
                ),
                mock.call(
                    organization_id=2,
                    skill_id="absolute",
                    actor_user_id=22,
                    source_path=absolute_path,
                ),
            ],
        )
        self.assertEqual(
            json.loads(stdout),
            {
                "ok": True,
                "count": 2,
                "skills": [
                    {
                        "organization_id": 1,
                        "skill_id": "relative",
                        "actor_user_id": 11,
                        "registry_id": 101,
                        "active_version_id": 201,
                    },
                    {
                        "organization_id": 2,
                        "skill_id": "absolute",
                        "actor_user_id": 22,
                        "registry_id": 102,
                        "active_version_id": 202,
                    },
                ],
            },
        )
        self.assertNotIn(": ", stdout)

    def test_object_manifest_imports_through_real_registry_function(self):
        old_db = lesson_manager.DB_PATH
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        try:
            lesson_manager.init_db()
            with lesson_manager.get_conn() as conn:
                organization = conn.execute(
                    "INSERT INTO organizations (name) VALUES (?)",
                    ("Organization",),
                )
                organization_id = int(organization.lastrowid)
                teacher = conn.execute(
                    """
                    INSERT INTO users (
                        username, password_hash, display_name, role, status, organization_id
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    ("teacher", "hash", "Teacher", "member", "active", organization_id),
                )
                teacher_id = int(teacher.lastrowid)
            source_path = self.root / "skills" / "teacher.skill"
            source_path.parent.mkdir()
            source_path.write_text("# Teacher style\nConcise feedback.", encoding="utf-8")
            manifest_path = self._write_manifest(
                {
                    "skills": [
                        {
                            "organization_id": organization_id,
                            "skill_id": "teacher-style",
                            "actor_user_id": teacher_id,
                            "source_path": "skills/teacher.skill",
                        }
                    ]
                }
            )

            status, stdout, stderr = self._run_main(manifest_path)
            stored = lesson_manager.get_class_commentary_skill_for_organization(
                organization_id,
                "teacher-style",
            )
        finally:
            lesson_manager.DB_PATH = old_db

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout)["count"], 1)
        self.assertEqual(stored["source_path"], str(source_path.resolve()))
        self.assertEqual(stored["content"], "# Teacher style\nConcise feedback.")

    def test_entire_manifest_shape_is_validated_before_database_or_import_calls(self):
        manifest_path = self._write_manifest(
            [
                {
                    "organization_id": 1,
                    "skill_id": "valid",
                    "actor_user_id": 11,
                    "source_path": "valid.skill",
                },
                {
                    "organization_id": 1,
                    "skill_id": "missing-source",
                    "actor_user_id": 11,
                },
            ]
        )

        with mock.patch.object(lesson_manager, "init_db") as init_db, mock.patch.object(
            lesson_manager,
            "import_class_commentary_skill_manifest",
        ) as import_skill:
            status, stdout, stderr = self._run_main(manifest_path)

        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        init_db.assert_not_called()
        import_skill.assert_not_called()
        self.assertEqual(json.loads(stderr)["error"], "invalid_manifest")
        self.assertIn("source_path", json.loads(stderr)["message"])

    def test_conflict_returns_nonzero_compact_json(self):
        manifest_path = self._write_manifest(
            {
                "skills": [
                    {
                        "organization_id": 1,
                        "skill_id": "conflict",
                        "actor_user_id": 11,
                        "source_path": "conflict.skill",
                    }
                ]
            }
        )

        with mock.patch.object(lesson_manager, "init_db"), mock.patch.object(
            lesson_manager,
            "import_class_commentary_skill_manifest",
            side_effect=lesson_manager.ClassCommentarySkillImportConflict("already registered"),
        ):
            status, stdout, stderr = self._run_main(manifest_path)

        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(
            json.loads(stderr),
            {"ok": False, "error": "conflict", "message": "already registered"},
        )
        self.assertNotIn(": ", stderr)


if __name__ == "__main__":
    unittest.main()
