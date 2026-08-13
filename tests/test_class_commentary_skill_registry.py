import hashlib
import os
import tempfile
import unittest
from pathlib import Path

import lesson_manager


class ClassCommentarySkillRegistryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        lesson_manager.init_db()
        with lesson_manager.get_conn() as conn:
            org_one = conn.execute(
                "INSERT INTO organizations (name) VALUES (?)",
                ("Organization One",),
            )
            org_two = conn.execute(
                "INSERT INTO organizations (name) VALUES (?)",
                ("Organization Two",),
            )
            self.org_one_id = int(org_one.lastrowid)
            self.org_two_id = int(org_two.lastrowid)
            teacher_one = conn.execute(
                """
                INSERT INTO users (
                    username, password_hash, display_name, role, status, organization_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("teacher-one", "hash", "Teacher One", "member", "active", self.org_one_id),
            )
            teacher_two = conn.execute(
                """
                INSERT INTO users (
                    username, password_hash, display_name, role, status, organization_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("teacher-two", "hash", "Teacher Two", "member", "active", self.org_one_id),
            )
            teacher_other_org = conn.execute(
                """
                INSERT INTO users (
                    username, password_hash, display_name, role, status, organization_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "teacher-other-org",
                    "hash",
                    "Teacher Other Org",
                    "member",
                    "active",
                    self.org_two_id,
                ),
            )
            self.teacher_one_id = int(teacher_one.lastrowid)
            self.teacher_two_id = int(teacher_two.lastrowid)
            self.teacher_other_org_id = int(teacher_other_org.lastrowid)

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        self.tmp.cleanup()

    def _source_path(self, filename, content):
        path = Path(self.tmp.name) / filename
        path.write_text(content, encoding="utf-8")
        return path

    def _row_counts(self):
        with lesson_manager.get_conn() as conn:
            return {
                table: int(conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"])
                for table in (
                    "class_commentary_skills",
                    "class_commentary_skill_versions",
                    "class_commentary_skill_activation_events",
                )
            }

    def test_atomic_import_creates_registry_version_pointer_event_and_db_backed_content(self):
        content = "# Teacher One\nWarm and concise."
        source_path = self._source_path("teacher-one.skill", content)

        imported = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.org_one_id,
            skill_id="teacher-one",
            actor_user_id=self.teacher_one_id,
            source_path=str(source_path),
        )
        source_path.write_text("changed after import", encoding="utf-8")
        fetched = lesson_manager.get_class_commentary_skill_for_organization(
            self.org_one_id,
            "teacher-one",
        )

        with lesson_manager.get_conn() as conn:
            registry = conn.execute(
                "SELECT * FROM class_commentary_skills WHERE organization_id=? AND skill_id=?",
                (self.org_one_id, "teacher-one"),
            ).fetchone()
            version = conn.execute(
                "SELECT * FROM class_commentary_skill_versions WHERE skill_registry_id=?",
                (registry["id"],),
            ).fetchone()
            event = conn.execute(
                "SELECT * FROM class_commentary_skill_activation_events WHERE skill_registry_id=?",
                (registry["id"],),
            ).fetchone()

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.assertEqual(imported["registry_id"], registry["id"])
        self.assertEqual(imported["id"], "teacher-one")
        self.assertEqual(imported["skill_id"], "teacher-one")
        self.assertEqual(imported["content"], content)
        self.assertEqual(fetched["content"], content)
        self.assertEqual(registry["imported_by_user_id"], self.teacher_one_id)
        self.assertEqual(registry["source_type"], "external_skill_package")
        self.assertEqual(registry["source_path"], str(source_path))
        self.assertEqual(registry["source_content_hash"], content_hash)
        self.assertEqual(registry["active_version_id"], version["id"])
        self.assertEqual(version["organization_id"], self.org_one_id)
        self.assertEqual(version["version_no"], 1)
        self.assertEqual(version["version_kind"], "imported")
        self.assertEqual(version["content"], content)
        self.assertEqual(version["content_hash"], content_hash)
        self.assertEqual(version["review_status"], "not_required")
        self.assertIsNone(event["from_version_id"])
        self.assertEqual(event["to_version_id"], version["id"])
        self.assertEqual(event["actor_user_id"], self.teacher_one_id)
        self.assertEqual(event["reason"], "initial_import")
        self.assertTrue(event["activation_request_id"])
        self.assertTrue(event["activation_payload_hash"])

    def test_package_import_skips_companion_files_embedded_in_skill_md(self):
        package = Path(self.tmp.name) / "teacher-package"
        package.mkdir()
        work_content = "# Work Skill\nUse direct, actionable feedback."
        persona_content = "# Persona\nUse a warm parent-group voice."
        (package / "SKILL.md").write_text(
            "# Teacher Package\n\n## Part A\n"
            + work_content
            + "\n\n## Part B\n"
            + persona_content,
            encoding="utf-8",
        )
        (package / "work.md").write_text(work_content, encoding="utf-8")
        (package / "persona.md").write_text(persona_content, encoding="utf-8")

        imported = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.org_one_id,
            skill_id="teacher-package",
            actor_user_id=self.teacher_one_id,
            source_path=str(package / "SKILL.md"),
        )

        self.assertEqual(imported["content"].count(work_content), 1)
        self.assertEqual(imported["content"].count(persona_content), 1)
        self.assertNotIn("## work.md", imported["content"])
        self.assertNotIn("## persona.md", imported["content"])

    def test_package_import_freezes_nested_knowledge_examples_and_hash(self):
        package = Path(self.tmp.name) / "teacher-knowledge"
        messages = package / "knowledge" / "messages"
        messages.mkdir(parents=True)
        (package / "SKILL.md").write_text(
            "# Teacher Knowledge\nPreserve the colleague voice.", encoding="utf-8"
        )
        sample_content = (
            "学生这节课计算进步很明显[强].\n\n"
            "符号还要再检查, 课后把错题重做一遍[玫瑰]."
        )
        (messages / "feedback-samples.md").write_text(
            sample_content, encoding="utf-8"
        )

        imported = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.org_one_id,
            skill_id="teacher-knowledge",
            actor_user_id=self.teacher_one_id,
            source_path=str(package / "SKILL.md"),
        )

        expected_hash = hashlib.sha256(
            imported["content"].encode("utf-8")
        ).hexdigest()
        self.assertIn("## knowledge/messages/feedback-samples.md", imported["content"])
        self.assertIn(sample_content, imported["content"])
        self.assertEqual(imported["content_hash"], expected_hash)
        self.assertEqual(imported["source_content_hash"], expected_hash)

    def test_skill_display_name_ignores_symlinked_meta_json(self):
        package = Path(self.tmp.name) / "teacher-safe-meta"
        package.mkdir()
        skill_path = package / "SKILL.md"
        skill_path.write_text("Safe skill content", encoding="utf-8")
        outside_meta = Path(self.tmp.name) / "outside-meta.json"
        outside_meta.write_text('{"name": "Outside name"}', encoding="utf-8")
        (package / "meta.json").symlink_to(outside_meta)

        display_name = lesson_manager._class_commentary_skill_display_name(
            "teacher-safe-meta", str(skill_path)
        )

        self.assertEqual(display_name, "teacher-safe-meta")

    def test_manifest_refresh_creates_audited_imported_version_and_is_idempotent(self):
        package = Path(self.tmp.name) / "teacher-refresh"
        package.mkdir()
        work_content = "# Work Skill\nUse direct, actionable feedback."
        persona_content = "# Persona\nUse a warm parent-group voice."
        skill_path = package / "SKILL.md"
        skill_path.write_text("# Teacher Refresh", encoding="utf-8")
        (package / "work.md").write_text(work_content, encoding="utf-8")
        (package / "persona.md").write_text(persona_content, encoding="utf-8")
        imported = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.org_one_id,
            skill_id="teacher-refresh",
            actor_user_id=self.teacher_one_id,
            source_path=str(skill_path),
        )
        original_content = imported["content"]
        original_version_id = imported["active_version_id"]
        skill_path.write_text(
            "# Teacher Refresh\n\n## Part A\n"
            + work_content
            + "\n\n## Part B\n"
            + persona_content,
            encoding="utf-8",
        )

        refreshed = lesson_manager.refresh_class_commentary_skill_manifest(
            organization_id=self.org_one_id,
            skill_id="teacher-refresh",
            actor_user_id=self.teacher_one_id,
            activation_request_id="manifest-refresh-v1",
            expected_active_version_id=original_version_id,
        )
        counts_after_refresh = self._row_counts()
        replayed = lesson_manager.refresh_class_commentary_skill_manifest(
            organization_id=self.org_one_id,
            skill_id="teacher-refresh",
            actor_user_id=self.teacher_one_id,
            activation_request_id="manifest-refresh-v1",
            expected_active_version_id=original_version_id,
        )

        self.assertTrue(refreshed["changed"])
        self.assertEqual(replayed, refreshed)
        self.assertEqual(self._row_counts(), counts_after_refresh)
        self.assertEqual(refreshed["version"]["version_no"], 2)
        self.assertEqual(refreshed["version"]["version_kind"], "imported")
        self.assertEqual(refreshed["version"]["base_version_id"], original_version_id)
        self.assertEqual(refreshed["skill"]["active_version_id"], refreshed["version"]["id"])
        self.assertEqual(refreshed["activation_event"]["reason"], "manifest_refresh")
        self.assertEqual(
            refreshed["activation_event"]["from_version_id"],
            original_version_id,
        )
        self.assertEqual(
            refreshed["activation_event"]["to_version_id"],
            refreshed["version"]["id"],
        )
        self.assertEqual(refreshed["skill"]["content"].count(work_content), 1)
        self.assertEqual(refreshed["skill"]["content"].count(persona_content), 1)
        self.assertNotIn("## work.md", refreshed["skill"]["content"])
        self.assertNotIn("## persona.md", refreshed["skill"]["content"])
        with lesson_manager.get_conn() as conn:
            original_version = conn.execute(
                "SELECT * FROM class_commentary_skill_versions WHERE id=?",
                (original_version_id,),
            ).fetchone()
        self.assertEqual(original_version["content"], original_content)

        (package / "persona.md").write_text(
            persona_content + "\nUse one emoji.",
            encoding="utf-8",
        )
        with self.assertRaises(
            lesson_manager.ClassCommentarySkillActivationRequestConflict
        ):
            lesson_manager.refresh_class_commentary_skill_manifest(
                organization_id=self.org_one_id,
                skill_id="teacher-refresh",
                actor_user_id=self.teacher_one_id,
                activation_request_id="manifest-refresh-v1",
                expected_active_version_id=original_version_id,
            )
        self.assertEqual(self._row_counts(), counts_after_refresh)

    def test_manifest_refresh_stale_active_version_has_no_writes(self):
        source_path = self._source_path("teacher-stale.skill", "Original content")
        imported = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.org_one_id,
            skill_id="teacher-stale",
            actor_user_id=self.teacher_one_id,
            source_path=str(source_path),
        )
        counts_before = self._row_counts()

        with self.assertRaises(lesson_manager.ClassCommentarySkillImportConflict):
            lesson_manager.refresh_class_commentary_skill_manifest(
                organization_id=self.org_one_id,
                skill_id="teacher-stale",
                actor_user_id=self.teacher_one_id,
                activation_request_id="manifest-refresh-unchanged",
                expected_active_version_id=imported["active_version_id"],
            )
        self.assertEqual(self._row_counts(), counts_before)

        source_path.write_text("Updated content", encoding="utf-8")
        with self.assertRaises(lesson_manager.ClassCommentarySkillVersionConflict):
            lesson_manager.refresh_class_commentary_skill_manifest(
                organization_id=self.org_one_id,
                skill_id="teacher-stale",
                actor_user_id=self.teacher_one_id,
                activation_request_id="manifest-refresh-stale",
                expected_active_version_id=imported["active_version_id"] + 100,
            )

        self.assertEqual(self._row_counts(), counts_before)

    def test_repeat_import_is_idempotent_and_changed_content_conflicts_without_writes(self):
        content = "# Teacher One\nUse short sentences.\n"
        source_path = self._source_path("teacher-one.skill", content)
        manifest = {
            "organization_id": self.org_one_id,
            "skill_id": "teacher-one",
            "actor_user_id": self.teacher_one_id,
            "source_path": str(source_path),
            "content": content,
        }

        first = lesson_manager.import_class_commentary_skill_manifest(**manifest)
        counts_after_first = self._row_counts()
        repeated = lesson_manager.import_class_commentary_skill_manifest(**manifest)

        self.assertEqual(repeated, first)
        self.assertEqual(self._row_counts(), counts_after_first)
        with self.assertRaises(lesson_manager.ClassCommentarySkillImportConflict):
            lesson_manager.import_class_commentary_skill_manifest(
                **{**manifest, "content": "# Teacher One\nChanged content.\n"}
            )
        self.assertEqual(self._row_counts(), counts_after_first)

    def test_repeat_import_keeps_an_evolved_active_version(self):
        content = "# Teacher One\nUse short sentences.\n"
        source_path = self._source_path("teacher-one.skill", content)
        manifest = {
            "organization_id": self.org_one_id,
            "skill_id": "teacher-one",
            "actor_user_id": self.teacher_one_id,
            "source_path": str(source_path),
            "content": content,
        }
        imported = lesson_manager.import_class_commentary_skill_manifest(**manifest)
        evolved_content = content + "Prefer one concrete next step.\n"
        evolved_hash = hashlib.sha256(evolved_content.encode("utf-8")).hexdigest()
        with lesson_manager.get_conn() as conn:
            version = conn.execute(
                """
                INSERT INTO class_commentary_skill_versions (
                    organization_id, skill_registry_id, version_no, version_kind,
                    content, content_hash, review_status
                ) VALUES (?, ?, 2, 'candidate', ?, ?, 'approved')
                """,
                (
                    self.org_one_id,
                    imported["registry_id"],
                    evolved_content,
                    evolved_hash,
                ),
            )
            conn.execute(
                "UPDATE class_commentary_skills SET active_version_id=? WHERE id=?",
                (version.lastrowid, imported["registry_id"]),
            )
        counts_before_repeat = self._row_counts()

        repeated = lesson_manager.import_class_commentary_skill_manifest(**manifest)

        self.assertEqual(repeated["active_version_id"], version.lastrowid)
        self.assertEqual(repeated["content"], evolved_content)
        self.assertEqual(self._row_counts(), counts_before_repeat)

    def test_import_actor_must_share_organization_and_skill_lists_are_organization_scoped(self):
        source_one = self._source_path("teacher-one.skill", "Teacher one style")
        source_two = self._source_path("teacher-two.skill", "Teacher two style")
        source_other = self._source_path("teacher-other.skill", "Other organization style")

        with self.assertRaises(ValueError):
            lesson_manager.import_class_commentary_skill_manifest(
                organization_id=self.org_one_id,
                skill_id="wrong-owner",
                actor_user_id=self.teacher_other_org_id,
                source_path=str(source_other),
            )
        lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.org_one_id,
            skill_id="teacher-one",
            actor_user_id=self.teacher_one_id,
            source_path=str(source_one),
        )
        lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.org_one_id,
            skill_id="teacher-two",
            actor_user_id=self.teacher_two_id,
            source_path=str(source_two),
        )
        lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.org_two_id,
            skill_id="teacher-other",
            actor_user_id=self.teacher_other_org_id,
            source_path=str(source_other),
        )

        teacher_one_skills = lesson_manager.list_class_commentary_skills_for_organization(
            self.org_one_id,
        )
        teacher_two_skills = lesson_manager.list_class_commentary_skills_for_organization(
            self.org_one_id,
        )
        other_org_skills = lesson_manager.list_class_commentary_skills_for_organization(
            self.org_two_id,
        )

        self.assertEqual(
            [item["skill_id"] for item in teacher_one_skills],
            ["teacher-one", "teacher-two"],
        )
        self.assertEqual(teacher_two_skills, teacher_one_skills)
        self.assertEqual([item["skill_id"] for item in other_org_skills], ["teacher-other"])


if __name__ == "__main__":
    unittest.main()
