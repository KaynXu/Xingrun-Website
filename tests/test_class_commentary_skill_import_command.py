import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "import_class_commentary_skills.py"
SPEC = importlib.util.spec_from_file_location("import_class_commentary_skills", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params):
        if "FROM organizations" in sql:
            return Mock(fetchone=lambda: {"id": params[0]})
        return Mock(
            fetchone=lambda: {"organization_id": 2, "status": "active"}
        )


class ClassCommentarySkillImportCommandTests(unittest.TestCase):
    def test_manifest_requires_explicit_owner_and_resolves_relative_skill_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = root / "teacher-style"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Skill", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "skills": [
                            {
                                "organization_id": 2,
                                "skill_id": "teacher-style",
                                "actor_user_id": 7,
                                "source_path": "teacher-style",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            items = MODULE.load_skill_manifest(manifest)

        self.assertEqual(items[0]["actor_user_id"], 7)
        self.assertEqual(items[0]["source_path"], str(skill_dir.resolve()))

    def test_check_mode_validates_without_importing(self):
        importer = Mock()
        with patch.object(MODULE, "load_skill_manifest", return_value=[{"id": 1}]), patch.object(
            MODULE, "validate_skill_actors"
        ) as validate, patch.object(
            MODULE.lesson_manager,
            "import_class_commentary_skill_manifest",
            importer,
        ):
            result = MODULE.import_skill_manifest(Path("manifest.json"), check_only=True)

        validate.assert_called_once_with([{"id": 1}])
        importer.assert_not_called()
        self.assertEqual(result, {"checked": 1, "imported": 0, "skills": []})

    def test_import_passes_only_explicit_manifest_scope(self):
        item = {
            "organization_id": 2,
            "skill_id": "teacher-style",
            "actor_user_id": 7,
            "source_path": "/skills/teacher-style",
        }
        importer = Mock(
            return_value={
                "registry_id": 11,
                "organization_id": 2,
                "skill_id": "teacher-style",
                "actor_user_id": 7,
                "active_version_id": 12,
            }
        )
        with patch.object(MODULE, "load_skill_manifest", return_value=[item]), patch.object(
            MODULE, "validate_skill_actors"
        ), patch.object(
            MODULE.lesson_manager,
            "import_class_commentary_skill_manifest",
            importer,
        ):
            result = MODULE.import_skill_manifest(Path("manifest.json"))

        importer.assert_called_once_with(**item)
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["skills"][0]["registry_id"], 11)

    def test_manifest_rejects_unknown_fields_and_duplicate_skill_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_file = root / "SKILL.md"
            skill_file.write_text("# Skill", encoding="utf-8")
            base = {
                "organization_id": 2,
                "skill_id": "teacher-style",
                "actor_user_id": 7,
                "source_path": "SKILL.md",
            }
            unknown = root / "unknown.json"
            unknown.write_text(
                json.dumps({"skills": [{**base, "owner_name": "inferred"}]}),
                encoding="utf-8",
            )
            duplicate = root / "duplicate.json"
            duplicate.write_text(
                json.dumps({"skills": [base, base]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "exactly"):
                MODULE.load_skill_manifest(unknown)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                MODULE.load_skill_manifest(duplicate)


if __name__ == "__main__":
    unittest.main()
