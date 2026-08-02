import os
import re
import sqlite3
import tempfile
import unittest

import lesson_manager


class ClassCommentaryStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        lesson_manager.init_db()

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        self.tmp.cleanup()

    def _table_names(self):
        with lesson_manager.get_conn() as conn:
            return {
                row["name"]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }

    def _column_names(self, table_name):
        with lesson_manager.get_conn() as conn:
            return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}

    def _column_metadata(self, table_name):
        with lesson_manager.get_conn() as conn:
            return {
                row["name"]: dict(row)
                for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            }

    def _unique_column_sets(self, table_name):
        with lesson_manager.get_conn() as conn:
            indexes = conn.execute(f"PRAGMA index_list({table_name})").fetchall()
            return {
                tuple(
                    row["name"]
                    for row in conn.execute(f"PRAGMA index_info({index['name']})").fetchall()
                )
                for index in indexes
                if index["unique"]
            }

    def _foreign_key_targets(self, table_name):
        with lesson_manager.get_conn() as conn:
            return {
                (row["from"], row["table"], row["to"])
                for row in conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
            }

    def _table_sql(self, table_name):
        with lesson_manager.get_conn() as conn:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
        self.assertIsNotNone(row, table_name)
        return row["sql"]

    def _check_values(self, table_name, column_name):
        table_sql = self._table_sql(table_name)
        match = re.search(
            rf"CHECK\s*\(\s*{re.escape(column_name)}\s+IN\s*\((.*?)\)\s*\)",
            table_sql,
            flags=re.IGNORECASE | re.DOTALL,
        )
        self.assertIsNotNone(match, f"{table_name}.{column_name} must have an IN CHECK")
        return {
            value.strip().strip("'")
            for value in match.group(1).split(",")
        }

    def _reserve_runtime_generation(self, task: dict, skill_id: str, content: str) -> dict:
        skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=int(task["organization_id"]),
            skill_id=skill_id,
            actor_user_id=int(task["teacher_user_id"]),
            source_path=f"/tmp/{skill_id}.skill",
            content=content,
        )
        return lesson_manager.reserve_class_commentary_generation(
            task_id=int(task["id"]),
            generation_request_id=f"generation-{skill_id}",
            skill_registry_id=int(skill["registry_id"]),
            attending_roster=[],
            model_provider="deepseek",
            model_name="deepseek-v4-pro",
            model_parameters={"temperature": 0.55},
            prompt_version="class-commentary-v1",
            prompt_payload={"messages": [], "temperature": 0.55},
            memory_context={"records": []},
        )

    def test_phase_one_v3_schema_columns_are_exact(self):
        expected_columns = {
            "class_commentary_skills": {
                "id",
                "organization_id",
                "skill_id",
                "imported_by_user_id",
                "source_type",
                "source_path",
                "source_content_hash",
                "active_version_id",
                "status",
                "created_at",
                "updated_at",
            },
            "class_commentary_skill_versions": {
                "id",
                "organization_id",
                "skill_registry_id",
                "version_no",
                "version_kind",
                "candidate_build_id",
                "content",
                "content_hash",
                "base_version_id",
                "source_snapshot_hash",
                "evaluation_snapshot_json",
                "evaluation_hash",
                "review_status",
                "created_at",
                "reviewed_at",
            },
            "class_commentary_skill_activation_events": {
                "id",
                "organization_id",
                "skill_registry_id",
                "activation_request_id",
                "activation_payload_hash",
                "from_version_id",
                "to_version_id",
                "actor_user_id",
                "reason",
                "evaluation_snapshot_json",
                "created_at",
            },
            "class_commentary_generations": {
                "id",
                "organization_id",
                "task_id",
                "generation_no",
                "generation_request_id",
                "generation_request_payload_hash",
                "teacher_user_id",
                "class_id",
                "subject_key",
                "confirmed_transcript_version",
                "confirmed_transcript_snapshot",
                "confirmed_transcript_hash",
                "attending_roster_snapshot_json",
                "attending_roster_hash",
                "attending_roster_explicit",
                "skill_registry_id",
                "skill_id",
                "skill_version_id",
                "skill_content_snapshot",
                "skill_content_hash",
                "model_provider",
                "model_name",
                "model_parameters_json",
                "prompt_version",
                "prompt_payload_snapshot_json",
                "prompt_payload_hash",
                "memory_context_snapshot_json",
                "memory_context_hash",
                "execution_snapshot_status",
                "execution_snapshot_finalized_at",
                "feedback_schema_version",
                "structured_feedback_json",
                "structured_feedback_hash",
                "eligible_student_ids_json",
                "eligible_student_scope_hash",
                "student_mention_matcher_version",
                "response_format_json",
                "student_history_memory_mode",
                "generated_feedback_text",
                "origin",
                "snapshot_completeness",
                "missing_snapshot_fields_json",
                "status",
                "error_code",
                "created_at",
                "completed_at",
            },
            "class_commentary_feedback_drafts": {
                "id",
                "organization_id",
                "task_id",
                "generation_id",
                "teacher_user_id",
                "based_on_revision_id",
                "feedback_schema_version",
                "structured_feedback_json",
                "feedback_text",
                "content_hash",
                "draft_version",
                "created_at",
                "updated_at",
            },
            "class_commentary_revisions": {
                "id",
                "organization_id",
                "task_id",
                "generation_id",
                "teacher_user_id",
                "revision_no",
                "confirmation_request_id",
                "confirmation_payload_hash",
                "previous_revision_id",
                "confirmed_draft_version",
                "confirmed_draft_snapshot_json",
                "feedback_schema_version",
                "structured_feedback_json",
                "structured_feedback_hash",
                "final_feedback_text",
                "generation_diff_json",
                "previous_revision_diff_json",
                "learning_evidence_schema_version",
                "learning_evidence_selector_version",
                "learning_evidence_snapshot_json",
                "learning_evidence_source_refs_json",
                "learning_evidence_hash",
                "learning_evidence_captured_at",
                "learning_evidence_completeness",
                "learning_evidence_missing_sources_json",
                "learn_requested",
                "accepted_without_edit",
                "unchanged_from_previous_revision",
                "confirmed_at",
            },
        }

        for table_name, columns in expected_columns.items():
            with self.subTest(table=table_name):
                self.assertEqual(self._column_names(table_name), columns)

    def test_structured_feedback_columns_are_additive_with_safe_defaults(self):
        expected_defaults = {
            "class_commentary_generations": {
                "feedback_schema_version": "''",
                "structured_feedback_json": "''",
                "structured_feedback_hash": "''",
                "eligible_student_ids_json": "'[]'",
                "eligible_student_scope_hash": "''",
                "student_mention_matcher_version": "''",
                "response_format_json": "'{}'",
                "student_history_memory_mode": "''",
            },
            "class_commentary_feedback_drafts": {
                "feedback_schema_version": "''",
                "structured_feedback_json": "''",
            },
            "class_commentary_revisions": {
                "feedback_schema_version": "''",
                "structured_feedback_json": "''",
                "structured_feedback_hash": "''",
            },
        }

        for table_name, columns in expected_defaults.items():
            metadata = self._column_metadata(table_name)
            for column_name, expected_default in columns.items():
                with self.subTest(table=table_name, column=column_name):
                    self.assertEqual(metadata[column_name]["notnull"], 1)
                    self.assertEqual(metadata[column_name]["dflt_value"], expected_default)

    def test_init_db_adds_structured_feedback_columns_without_backfilling_legacy_rows(self):
        class_id = lesson_manager.save_class(
            "兼容迁移班",
            organization_id=1,
            teacher_user_id=1,
        )
        task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/compatibility-floor.m4a",
            audio_filename="compatibility-floor.m4a",
        )
        task = lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            "小王本节课计算稳定",
        )
        generation = self._reserve_runtime_generation(
            task,
            "compatibility-floor-style",
            "compatibility floor style",
        )
        lesson_manager.complete_class_commentary_generation(
            generation["id"],
            "小王: 本节课计算稳定.",
        )
        draft = lesson_manager.save_class_commentary_feedback_draft(
            task_id=task["id"],
            generation_id=generation["id"],
            teacher_user_id=1,
            feedback_text="小王: 老师草稿.",
            expected_draft_version=0,
        )
        revision = lesson_manager.confirm_class_commentary_feedback(
            task_id=task["id"],
            generation_id=generation["id"],
            teacher_user_id=1,
            feedback_text="小王: 老师终稿.",
            learn_requested=False,
            expected_draft_version=draft["draft_version"],
            confirmation_request_id="compatibility-floor-confirmation",
        )
        columns_to_drop = {
            "class_commentary_generations": [
                "feedback_schema_version",
                "structured_feedback_json",
                "structured_feedback_hash",
                "eligible_student_ids_json",
                "eligible_student_scope_hash",
                "student_mention_matcher_version",
                "response_format_json",
                "student_history_memory_mode",
            ],
            "class_commentary_feedback_drafts": [
                "feedback_schema_version",
                "structured_feedback_json",
            ],
            "class_commentary_revisions": [
                "feedback_schema_version",
                "structured_feedback_json",
                "structured_feedback_hash",
            ],
        }
        with lesson_manager.get_conn() as conn:
            for table_name, column_names in columns_to_drop.items():
                for column_name in column_names:
                    conn.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")

        lesson_manager.init_db()
        lesson_manager.init_db()

        with lesson_manager.get_conn() as conn:
            migrated_generation = dict(conn.execute(
                "SELECT * FROM class_commentary_generations WHERE id=?",
                (generation["id"],),
            ).fetchone())
            migrated_draft = dict(conn.execute(
                "SELECT * FROM class_commentary_feedback_drafts WHERE id=?",
                (draft["id"],),
            ).fetchone())
            migrated_revision = dict(conn.execute(
                "SELECT * FROM class_commentary_revisions WHERE id=?",
                (revision["id"],),
            ).fetchone())

        self.assertEqual(migrated_generation["generated_feedback_text"], "小王: 本节课计算稳定.")
        self.assertEqual(migrated_generation["feedback_schema_version"], "")
        self.assertEqual(migrated_generation["structured_feedback_json"], "")
        self.assertEqual(migrated_generation["eligible_student_ids_json"], "[]")
        self.assertEqual(migrated_generation["response_format_json"], "{}")
        self.assertEqual(migrated_draft["feedback_text"], "小王: 老师终稿.")
        self.assertEqual(migrated_draft["feedback_schema_version"], "")
        self.assertEqual(migrated_draft["structured_feedback_json"], "")
        self.assertEqual(migrated_revision["final_feedback_text"], "小王: 老师终稿.")
        self.assertEqual(migrated_revision["feedback_schema_version"], "")
        self.assertEqual(migrated_revision["structured_feedback_json"], "")
        self.assertEqual(migrated_revision["structured_feedback_hash"], "")

    def test_phase_one_v3_schema_has_documented_unique_constraints(self):
        expected_unique_columns = {
            "class_commentary_skills": {
                ("organization_id", "skill_id"),
            },
            "class_commentary_skill_versions": {
                ("skill_registry_id", "version_no"),
                ("candidate_build_id",),
            },
            "class_commentary_skill_activation_events": {
                ("skill_registry_id", "activation_request_id"),
            },
            "class_commentary_generations": {
                ("task_id", "generation_no"),
                ("task_id", "generation_request_id"),
            },
            "class_commentary_feedback_drafts": {
                ("task_id", "generation_id", "teacher_user_id"),
            },
            "class_commentary_revisions": {
                ("task_id", "revision_no"),
                ("task_id", "confirmation_request_id"),
            },
        }

        for table_name, expected in expected_unique_columns.items():
            with self.subTest(table=table_name):
                self.assertTrue(expected.issubset(self._unique_column_sets(table_name)))

    def test_phase_one_v3_schema_has_registry_and_version_foreign_keys(self):
        expected_foreign_keys = {
            "class_commentary_skills": {
                ("organization_id", "organizations", "id"),
                ("imported_by_user_id", "users", "id"),
                ("active_version_id", "class_commentary_skill_versions", "id"),
            },
            "class_commentary_skill_versions": {
                ("organization_id", "organizations", "id"),
                ("skill_registry_id", "class_commentary_skills", "id"),
                ("base_version_id", "class_commentary_skill_versions", "id"),
            },
            "class_commentary_skill_activation_events": {
                ("organization_id", "organizations", "id"),
                ("skill_registry_id", "class_commentary_skills", "id"),
                ("from_version_id", "class_commentary_skill_versions", "id"),
                ("to_version_id", "class_commentary_skill_versions", "id"),
                ("actor_user_id", "users", "id"),
            },
            "class_commentary_generations": {
                ("organization_id", "organizations", "id"),
                ("task_id", "class_commentary_tasks", "id"),
                ("teacher_user_id", "users", "id"),
                ("class_id", "classes", "id"),
                ("skill_registry_id", "class_commentary_skills", "id"),
                ("skill_version_id", "class_commentary_skill_versions", "id"),
            },
            "class_commentary_feedback_drafts": {
                ("organization_id", "organizations", "id"),
                ("task_id", "class_commentary_tasks", "id"),
                ("generation_id", "class_commentary_generations", "id"),
                ("teacher_user_id", "users", "id"),
                ("based_on_revision_id", "class_commentary_revisions", "id"),
            },
            "class_commentary_revisions": {
                ("organization_id", "organizations", "id"),
                ("task_id", "class_commentary_tasks", "id"),
                ("generation_id", "class_commentary_generations", "id"),
                ("teacher_user_id", "users", "id"),
                ("previous_revision_id", "class_commentary_revisions", "id"),
            },
        }

        for table_name, expected in expected_foreign_keys.items():
            with self.subTest(table=table_name):
                self.assertTrue(expected.issubset(self._foreign_key_targets(table_name)))

        task_columns = self._column_metadata("class_commentary_tasks")
        self.assertTrue(
            {
                "confirmed_transcript_version",
                "final_feedback_text",
                "latest_generation_id",
                "latest_revision_id",
                "generation_seq",
                "feedback_confirmed_at",
                "feedback_revision_no",
            }.issubset(task_columns)
        )
        self.assertEqual(task_columns["latest_generation_id"]["notnull"], 0)
        self.assertEqual(task_columns["latest_revision_id"]["notnull"], 0)
        task_foreign_keys = self._foreign_key_targets("class_commentary_tasks")
        self.assertIn(
            ("latest_generation_id", "class_commentary_generations", "id"),
            task_foreign_keys,
        )
        self.assertIn(
            ("latest_revision_id", "class_commentary_revisions", "id"),
            task_foreign_keys,
        )

        class_columns = self._column_metadata("classes")
        self.assertIn("subject_key", class_columns)
        self.assertEqual(class_columns["subject_key"]["notnull"], 0)

    def test_phase_one_v3_schema_has_documented_check_constraints(self):
        expected_check_values = {
            ("class_commentary_skills", "source_type"): {
                "external_skill_package",
                "database",
            },
            ("class_commentary_skills", "status"): {"active", "disabled"},
            ("class_commentary_skill_versions", "version_kind"): {
                "imported",
                "candidate",
            },
            ("class_commentary_skill_versions", "review_status"): {
                "not_required",
                "pending",
                "approved",
                "rejected",
            },
            ("class_commentary_skill_activation_events", "reason"): {
                "initial_import",
                "candidate_approved",
                "rollback",
            },
            ("class_commentary_generations", "origin"): {
                "runtime",
                "legacy_migration",
            },
            ("class_commentary_generations", "snapshot_completeness"): {
                "complete",
                "partial",
            },
            ("class_commentary_generations", "attending_roster_explicit"): {
                "0",
                "1",
            },
            ("class_commentary_generations", "execution_snapshot_status"): {
                "pending",
                "ready",
            },
            ("class_commentary_generations", "status"): {
                "generating",
                "succeeded",
                "failed",
            },
            ("class_commentary_revisions", "learning_evidence_completeness"): {
                "complete",
                "partial",
                "empty",
            },
            ("class_commentary_revisions", "learn_requested"): {"0", "1"},
            ("class_commentary_revisions", "accepted_without_edit"): {"0", "1"},
            ("class_commentary_revisions", "unchanged_from_previous_revision"): {
                "0",
                "1",
            },
        }

        for (table_name, column_name), expected in expected_check_values.items():
            with self.subTest(table=table_name, column=column_name):
                self.assertEqual(self._check_values(table_name, column_name), expected)

        draft_sql = self._table_sql("class_commentary_feedback_drafts")
        self.assertRegex(
            draft_sql,
            r"(?i)CHECK\s*\(\s*draft_version\s*>=\s*1\s*\)",
        )

    def test_init_db_creates_class_commentary_evolution_schema_idempotently(self):
        expected_tables = {
            "class_commentary_skills",
            "class_commentary_skill_versions",
            "class_commentary_skill_activation_events",
            "class_commentary_generations",
            "class_commentary_feedback_drafts",
            "class_commentary_revisions",
        }
        expected_task_columns = {
            "confirmed_transcript_version",
            "final_feedback_text",
            "latest_generation_id",
            "latest_revision_id",
            "generation_seq",
            "feedback_confirmed_at",
            "feedback_revision_no",
        }

        table_names = self._table_names()
        class_columns = self._column_names("classes")
        task_columns = self._column_names("class_commentary_tasks")
        self.assertTrue(expected_tables.issubset(table_names))
        self.assertIn("subject_key", class_columns)
        self.assertTrue(expected_task_columns.issubset(task_columns))

        lesson_manager.init_db()

        self.assertEqual(self._table_names(), table_names)
        self.assertEqual(self._column_names("classes"), class_columns)
        self.assertEqual(self._column_names("class_commentary_tasks"), task_columns)

    def test_init_db_renames_legacy_skill_owner_without_rewriting_history(self):
        class_id = lesson_manager.save_class(
            "Skill owner migration class",
            subject="数学",
            organization_id=1,
            teacher_user_id=1,
        )
        task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/skill-owner-migration.m4a",
            audio_filename="skill-owner-migration.m4a",
        )
        task = lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            "Migration transcript snapshot",
        )
        generation = self._reserve_runtime_generation(
            task,
            "skill-owner-migration",
            "Preserve one concrete next action.",
        )
        lesson_manager.complete_class_commentary_generation(
            generation["id"],
            "Migration AI draft",
        )
        revision = lesson_manager.confirm_class_commentary_feedback(
            task_id=task["id"],
            generation_id=generation["id"],
            teacher_user_id=1,
            feedback_text="Migration teacher final",
            learn_requested=False,
            expected_draft_version=0,
            confirmation_request_id="skill-owner-migration-confirm",
        )

        def history_snapshot():
            with lesson_manager.get_conn() as conn:
                return {
                    "registry": dict(conn.execute(
                        """
                        SELECT id, organization_id, skill_id, source_type, source_path,
                               source_content_hash, active_version_id, status, created_at, updated_at
                        FROM class_commentary_skills WHERE id=?
                        """,
                        (generation["skill_registry_id"],),
                    ).fetchone()),
                    "version": dict(conn.execute(
                        "SELECT * FROM class_commentary_skill_versions WHERE id=?",
                        (generation["skill_version_id"],),
                    ).fetchone()),
                    "generation": dict(conn.execute(
                        "SELECT * FROM class_commentary_generations WHERE id=?",
                        (generation["id"],),
                    ).fetchone()),
                    "revision": dict(conn.execute(
                        "SELECT * FROM class_commentary_revisions WHERE id=?",
                        (revision["id"],),
                    ).fetchone()),
                }

        before = history_snapshot()
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "ALTER TABLE class_commentary_skills "
                "RENAME COLUMN imported_by_user_id TO owner_teacher_user_id"
            )
            conn.execute(
                """
                CREATE INDEX idx_class_commentary_skills_owner
                ON class_commentary_skills (organization_id, owner_teacher_user_id, status)
                """
            )

        lesson_manager.init_db()
        lesson_manager.init_db()

        self.assertIn("imported_by_user_id", self._column_names("class_commentary_skills"))
        self.assertNotIn("owner_teacher_user_id", self._column_names("class_commentary_skills"))
        self.assertEqual(history_snapshot(), before)
        with lesson_manager.get_conn() as conn:
            registry = conn.execute(
                "SELECT imported_by_user_id FROM class_commentary_skills WHERE id=?",
                (generation["skill_registry_id"],),
            ).fetchone()
            owner_index = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_class_commentary_skills_owner'"
            ).fetchone()
            foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        self.assertEqual(registry["imported_by_user_id"], 1)
        self.assertIsNone(owner_index)
        self.assertEqual(foreign_key_errors, [])

    def test_init_db_adds_confirmation_snapshot_columns_without_faking_legacy_draft(self):
        class_id = lesson_manager.save_class(
            "迁移确认快照班",
            subject="数学",
            organization_id=1,
            teacher_user_id=1,
        )
        task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/legacy-confirmation.m4a",
            audio_filename="legacy-confirmation.m4a",
        )
        task = lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            "小王计算更稳定",
        )
        generation = self._reserve_runtime_generation(
            task,
            "legacy-confirmation-style",
            "legacy confirmation style",
        )
        lesson_manager.complete_class_commentary_generation(
            generation["id"],
            "AI 原稿",
        )
        revision = lesson_manager.confirm_class_commentary_feedback(
            task_id=task["id"],
            generation_id=generation["id"],
            teacher_user_id=1,
            feedback_text="老师终稿",
            learn_requested=False,
            expected_draft_version=0,
            confirmation_request_id="legacy-confirmation-request",
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "ALTER TABLE class_commentary_revisions DROP COLUMN confirmed_draft_version"
            )
            conn.execute(
                "ALTER TABLE class_commentary_revisions DROP COLUMN confirmed_draft_snapshot_json"
            )

        lesson_manager.init_db()
        lesson_manager.init_db()

        migrated = lesson_manager.get_class_commentary_revision(revision["id"])
        metadata = self._column_metadata("class_commentary_revisions")
        self.assertEqual(metadata["confirmed_draft_version"]["notnull"], 1)
        self.assertEqual(metadata["confirmed_draft_version"]["dflt_value"], "0")
        self.assertEqual(metadata["confirmed_draft_snapshot_json"]["notnull"], 1)
        self.assertEqual(metadata["confirmed_draft_snapshot_json"]["dflt_value"], "'{}'")
        self.assertEqual(migrated["draft_version"], 0)
        self.assertIsNone(migrated["draft"])

    def test_init_db_backfills_only_controlled_class_subject_aliases(self):
        math_class_id = lesson_manager.save_class(
            "迁移数学班",
            subject="数学",
            organization_id=1,
            teacher_user_id=1,
        )
        unknown_class_id = lesson_manager.save_class(
            "迁移机器人班",
            subject="机器人",
            organization_id=1,
            teacher_user_id=1,
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE classes SET subject_key=NULL WHERE id IN (?, ?)",
                (math_class_id, unknown_class_id),
            )

        lesson_manager.init_db()

        with lesson_manager.get_conn() as conn:
            subject_keys = {
                row["id"]: row["subject_key"]
                for row in conn.execute(
                    "SELECT id, subject_key FROM classes WHERE id IN (?, ?)",
                    (math_class_id, unknown_class_id),
                ).fetchall()
            }
        self.assertEqual(subject_keys[math_class_id], "math")
        self.assertIsNone(subject_keys[unknown_class_id])

    def test_init_db_backfills_confirmed_transcript_version_from_existing_text_once(self):
        class_id = lesson_manager.save_class(
            "转写版本迁移班",
            subject="数学",
            organization_id=1,
            teacher_user_id=1,
        )
        confirmed_task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/confirmed-version.m4a",
            audio_filename="confirmed-version.m4a",
        )
        empty_task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/empty-version.m4a",
            audio_filename="empty-version.m4a",
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_tasks
                SET confirmed_transcript_text=?, confirmed_transcript_version=0
                WHERE id=?
                """,
                ("已确认的历史转写", confirmed_task["id"]),
            )
            conn.execute(
                """
                UPDATE class_commentary_tasks
                SET confirmed_transcript_text='', confirmed_transcript_version=0
                WHERE id=?
                """,
                (empty_task["id"],),
            )

        lesson_manager.init_db()
        lesson_manager.init_db()

        with lesson_manager.get_conn() as conn:
            versions = {
                row["id"]: row["confirmed_transcript_version"]
                for row in conn.execute(
                    """
                    SELECT id, confirmed_transcript_version
                    FROM class_commentary_tasks
                    WHERE id IN (?, ?)
                    """,
                    (confirmed_task["id"], empty_task["id"]),
                ).fetchall()
            }
        self.assertEqual(versions[confirmed_task["id"]], 1)
        self.assertEqual(versions[empty_task["id"]], 0)

    def test_explicit_transcript_confirmation_increments_version_on_every_call(self):
        class_id = lesson_manager.save_class(
            "转写确认版本班",
            subject="数学",
            organization_id=1,
            teacher_user_id=1,
        )
        task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/transcript-version.m4a",
            audio_filename="transcript-version.m4a",
        )
        self.assertEqual(task["confirmed_transcript_version"], 0)

        first_confirmation = lesson_manager.save_class_commentary_transcript(
            task["id"],
            "小王今天计算更稳了",
        )
        repeated_confirmation = lesson_manager.save_class_commentary_transcript(
            task["id"],
            "小王今天计算更稳了",
        )
        edited_confirmation = lesson_manager.save_class_commentary_transcript(
            task["id"],
            "小王今天计算更稳了, 继续练习验算",
        )

        self.assertEqual(first_confirmation["confirmed_transcript_version"], 1)
        self.assertEqual(repeated_confirmation["confirmed_transcript_version"], 2)
        self.assertEqual(edited_confirmation["confirmed_transcript_version"], 3)
        self.assertEqual(
            edited_confirmation["confirmed_transcript_text"],
            "小王今天计算更稳了, 继续练习验算",
        )

    def test_init_db_migrates_legacy_feedback_to_one_partial_generation_once(self):
        class_id = lesson_manager.save_class("数学·七年级·迁移班", organization_id=1, teacher_user_id=1)
        task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/legacy-feedback.m4a",
            audio_filename="legacy-feedback.m4a",
        )
        legacy_feedback = "小王:\n计算过程清晰, 继续保持."
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE class_commentary_tasks SET status='ready', feedback_text=? WHERE id=?",
                (legacy_feedback, task["id"]),
            )

        lesson_manager.init_db()

        with lesson_manager.get_conn() as conn:
            generations = conn.execute(
                """
                SELECT id, task_id, generation_no, status, origin,
                       snapshot_completeness, generated_feedback_text
                FROM class_commentary_generations
                WHERE task_id=?
                ORDER BY id
                """,
                (task["id"],),
            ).fetchall()
            migrated_task = conn.execute(
                "SELECT latest_generation_id FROM class_commentary_tasks WHERE id=?",
                (task["id"],),
            ).fetchone()

        self.assertEqual(len(generations), 1)
        generation = generations[0]
        self.assertEqual(generation["task_id"], task["id"])
        self.assertEqual(generation["generation_no"], 1)
        self.assertEqual(generation["status"], "succeeded")
        self.assertEqual(generation["origin"], "legacy_migration")
        self.assertEqual(generation["snapshot_completeness"], "partial")
        self.assertEqual(generation["generated_feedback_text"], legacy_feedback)
        self.assertEqual(migrated_task["latest_generation_id"], generation["id"])

        lesson_manager.init_db()

        with lesson_manager.get_conn() as conn:
            generations_after_second_init = conn.execute(
                "SELECT id FROM class_commentary_generations WHERE task_id=? ORDER BY id",
                (task["id"],),
            ).fetchall()
            latest_generation_id = conn.execute(
                "SELECT latest_generation_id FROM class_commentary_tasks WHERE id=?",
                (task["id"],),
            ).fetchone()["latest_generation_id"]
        self.assertEqual([row["id"] for row in generations_after_second_init], [generation["id"]])
        self.assertEqual(latest_generation_id, generation["id"])

    def test_init_db_drops_legacy_feedback_tables_and_keeps_them_gone_on_second_run(self):
        with lesson_manager.get_conn() as conn:
            conn.executescript(
                """
                CREATE TABLE lesson_class_feedbacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lesson_id INTEGER
                );
                CREATE TABLE class_feedback_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_id INTEGER,
                    teacher_user_id INTEGER
                );
                CREATE TABLE class_feedback_student_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    student_id INTEGER
                );
                CREATE TABLE class_feedback_label_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_user_id INTEGER
                );
                CREATE TABLE class_feedback_shadow_table (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                );
                """
            )

        lesson_manager.init_db()
        names = self._table_names()
        self.assertIn("class_commentary_tasks", names)
        self.assertNotIn("lesson_class_feedbacks", names)
        self.assertNotIn("class_feedback_tasks", names)
        self.assertNotIn("class_feedback_student_entries", names)
        self.assertNotIn("class_feedback_label_configs", names)
        self.assertFalse(any(name.startswith("class_feedback_") for name in names))

        lesson_manager.init_db()
        names = self._table_names()
        self.assertIn("class_commentary_tasks", names)
        self.assertNotIn("lesson_class_feedbacks", names)
        self.assertNotIn("class_feedback_tasks", names)
        self.assertNotIn("class_feedback_student_entries", names)
        self.assertNotIn("class_feedback_label_configs", names)
        self.assertFalse(any(name.startswith("class_feedback_") for name in names))

    def test_task_lifecycle_keeps_empty_strings_in_serialized_task(self):
        class_id = lesson_manager.save_class("数学·七年级·4班", organization_id=1, teacher_user_id=1)
        task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/audio.m4a",
            audio_filename="audio.m4a",
            transcription_request_key="audio-key",
        )
        self.assertEqual(task["status"], "uploaded")
        self.assertEqual(task["failure_stage"], "")
        self.assertEqual(task["feedback_text"], "")

        transcribing = lesson_manager.mark_class_commentary_task_transcribing(task["id"])
        self.assertEqual(transcribing["status"], "transcribing")

        transcribed = lesson_manager.mark_class_commentary_transcription_succeeded(task["id"], "小王今天计算更稳了")
        self.assertEqual(transcribed["status"], "transcribed")
        self.assertEqual(transcribed["transcript_text"], "小王今天计算更稳了")
        self.assertEqual(transcribed["confirmed_transcript_text"], "小王今天计算更稳了")
        self.assertTrue(transcribed["transcribed_at"])

        confirmed = lesson_manager.save_class_commentary_transcript(task["id"], "小王今天计算更稳了, 回家继续练")
        self.assertEqual(confirmed["status"], "transcribed")
        self.assertEqual(confirmed["confirmed_transcript_text"], "小王今天计算更稳了, 回家继续练")

        generation = self._reserve_runtime_generation(
            confirmed,
            "teacher-a",
            "style rules",
        )
        generating = lesson_manager.get_class_commentary_task(task["id"])
        self.assertEqual(generating["status"], "generating")
        self.assertEqual(generating["skill_id"], "teacher-a")

        lesson_manager.complete_class_commentary_generation(
            generation["id"],
            "小王:\n今天计算更稳了.",
        )
        ready = lesson_manager.get_class_commentary_task(task["id"])
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["failure_stage"], "")
        self.assertEqual(ready["generation_error"], "")
        self.assertEqual(ready["feedback_text"], "小王:\n今天计算更稳了.")

    def test_list_class_commentary_tasks_for_organization_returns_recent_first(self):
        class_id = lesson_manager.save_class("数学·七年级·4班", organization_id=1, teacher_user_id=1)
        with lesson_manager.get_conn() as conn:
            conn.execute("INSERT INTO organizations (name) VALUES (?)", ("Other Org",))
            other_org_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("other-teacher", "hash", "Other Teacher", "member", "active", other_org_id),
            )
            other_teacher_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        other_class_id = lesson_manager.save_class("数学·八年级·1班", organization_id=other_org_id, teacher_user_id=other_teacher_id)
        first = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/first.m4a",
            audio_filename="first.m4a",
        )
        second = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/second.m4a",
            audio_filename="second.m4a",
        )
        lesson_manager.create_class_commentary_task(
            organization_id=other_org_id,
            class_id=other_class_id,
            teacher_user_id=other_teacher_id,
            audio_path="/tmp/other.m4a",
            audio_filename="other.m4a",
        )

        items = lesson_manager.list_class_commentary_tasks_for_organization(1, limit=10)

        self.assertEqual([item["id"] for item in items], [second["id"], first["id"]])
        self.assertEqual(items[0]["class_name"], "数学·七年级·4班")

    def test_failed_generation_can_return_to_transcribed_by_saving_transcript(self):
        class_id = lesson_manager.save_class("数学·七年级·4班", organization_id=1, teacher_user_id=1)
        task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/audio.m4a",
            audio_filename="audio.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(task["id"], "小王需要再练计算")
        failed = lesson_manager.mark_class_commentary_task_failed(task["id"], "generation", "model timeout")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["failure_stage"], "generation")
        self.assertEqual(failed["generation_error"], "model timeout")

        recovered = lesson_manager.save_class_commentary_transcript(task["id"], "小王需要再练计算速度")
        self.assertEqual(recovered["status"], "transcribed")
        self.assertEqual(recovered["failure_stage"], "")
        self.assertEqual(recovered["generation_error"], "")

    def test_usable_states_clear_stale_transcription_error(self):
        class_id = lesson_manager.save_class("数学·七年级·6班", organization_id=1, teacher_user_id=1)
        task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/audio-2.m4a",
            audio_filename="audio-2.m4a",
        )
        failed = lesson_manager.mark_class_commentary_task_failed(task["id"], "transcription", "whisper timeout")
        self.assertEqual(failed["transcription_error"], "whisper timeout")

        recovered = lesson_manager.save_class_commentary_transcript(task["id"], "老师已修正转写")
        self.assertEqual(recovered["status"], "transcribed")
        self.assertEqual(recovered["transcription_error"], "")

        failed = lesson_manager.mark_class_commentary_task_failed(task["id"], "transcription", "retry later")
        self.assertEqual(failed["transcription_error"], "retry later")

        generation = self._reserve_runtime_generation(
            recovered,
            "teacher-b",
            "tone rules",
        )
        generating = lesson_manager.get_class_commentary_task(task["id"])
        self.assertEqual(generating["status"], "generating")
        self.assertEqual(generating["transcription_error"], "")

        failed = lesson_manager.mark_class_commentary_task_failed(task["id"], "transcription", "one more retry")
        self.assertEqual(failed["transcription_error"], "one more retry")

        lesson_manager.complete_class_commentary_generation(generation["id"], "反馈内容")
        ready = lesson_manager.get_class_commentary_task(task["id"])
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["transcription_error"], "")

    def test_maintenance_flows_do_not_touch_deleted_class_feedback_tables(self):
        student = lesson_manager.create_student_profile("无引用学生", organization_id=1)
        result = lesson_manager.delete_or_archive_student_profile(student["id"], organization_id=1)
        self.assertEqual(result["action"], "deleted")

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("class-commentary-member", "hash", "Class Commentary Member", "member", "active", 1),
            )
            member_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO organizations (name)
                VALUES (?)
                """,
                ("Class Commentary Cleanup Org",),
            )
            org_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        actor_user = lesson_manager.get_user_by_username("Kayn")
        lesson_manager.delete_user_for_actor(actor_user, member_id)
        self.assertIsNone(lesson_manager.get_user_by_username("class-commentary-member"))

        lesson_manager.delete_organization(org_id)
        with lesson_manager.get_conn() as conn:
            org_row = conn.execute("SELECT id FROM organizations WHERE id=?", (org_id,)).fetchone()
        self.assertIsNone(org_row)

    def test_delete_class_removes_commentary_tasks_before_deleting_class(self):
        class_id = lesson_manager.save_class("数学·七年级·8班", organization_id=1, teacher_user_id=1)
        task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=1,
            audio_path="/tmp/delete-class-audio.m4a",
            audio_filename="delete-class-audio.m4a",
        )

        try:
            lesson_manager.delete_class(class_id)
        except sqlite3.IntegrityError as exc:
            self.fail(f"delete_class raised IntegrityError: {exc}")

        with lesson_manager.get_conn() as conn:
            class_row = conn.execute("SELECT id FROM classes WHERE id=?", (class_id,)).fetchone()
            task_row = conn.execute("SELECT id FROM class_commentary_tasks WHERE id=?", (task["id"],)).fetchone()
        self.assertIsNone(class_row)
        self.assertIsNone(task_row)

    def test_delete_user_for_actor_removes_commentary_tasks_before_deleting_teacher(self):
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("commentary-teacher", "hash", "Commentary Teacher", "member", "active", 1),
            )
            teacher_user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        class_id = lesson_manager.save_class("数学·七年级·9班", organization_id=1, teacher_user_id=teacher_user_id)
        task = lesson_manager.create_class_commentary_task(
            organization_id=1,
            class_id=class_id,
            teacher_user_id=teacher_user_id,
            audio_path="/tmp/delete-user-audio.m4a",
            audio_filename="delete-user-audio.m4a",
        )

        actor_user = lesson_manager.get_user_by_username("Kayn")
        try:
            lesson_manager.delete_user_for_actor(actor_user, teacher_user_id)
        except sqlite3.IntegrityError as exc:
            self.fail(f"delete_user_for_actor raised IntegrityError: {exc}")

        with lesson_manager.get_conn() as conn:
            user_row = conn.execute("SELECT id FROM users WHERE id=?", (teacher_user_id,)).fetchone()
            task_row = conn.execute("SELECT id FROM class_commentary_tasks WHERE id=?", (task["id"],)).fetchone()
        self.assertIsNone(user_row)
        self.assertIsNone(task_row)


if __name__ == "__main__":
    unittest.main()
