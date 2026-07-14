import os
import tempfile
import unittest

import lesson_manager


class ClassCommentaryMemoryLifecycleDeleteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        self.old_enabled = os.environ.get("XR_CLASS_COMMENTARY_MEMORY_ENABLED")
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        os.environ["XR_CLASS_COMMENTARY_MEMORY_ENABLED"] = "true"
        lesson_manager.init_db()
        self.actor = lesson_manager.get_user_by_username("Kayn")

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        if self.old_enabled is None:
            os.environ.pop("XR_CLASS_COMMENTARY_MEMORY_ENABLED", None)
        else:
            os.environ["XR_CLASS_COMMENTARY_MEMORY_ENABLED"] = self.old_enabled
        self.tmp.cleanup()

    def _create_teacher(self, organization_id, username):
        with lesson_manager.get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (
                    username, password_hash, display_name, role, status, organization_id
                ) VALUES (?, ?, ?, 'owner', 'active', ?)
                """,
                (
                    username,
                    lesson_manager.hash_password("password123"),
                    username,
                    organization_id,
                ),
            )
            user_id = int(cursor.lastrowid)
        return lesson_manager.get_user_by_id(user_id)

    def _create_confirmed_generation(self, teacher, skill_id):
        class_id = lesson_manager.save_class(
            f"{skill_id} class",
            subject="Math",
            grade="Grade 7",
            organization_id=teacher["organization_id"],
            teacher_user_id=teacher["id"],
        )
        student = lesson_manager.create_student_for_class(class_id, f"{skill_id} student")
        skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=teacher["organization_id"],
            skill_id=skill_id,
            owner_teacher_user_id=teacher["id"],
            source_path=f"/skills/{skill_id}/SKILL.md",
            content="Start with progress and end with one concrete next step.",
        )
        task = lesson_manager.create_class_commentary_task(
            organization_id=teacher["organization_id"],
            class_id=class_id,
            teacher_user_id=teacher["id"],
            audio_path=f"/tmp/{skill_id}.m4a",
            audio_filename=f"{skill_id}.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            "The student is making steady progress.",
        )
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=task["id"],
            generation_request_id=f"{skill_id}-generation",
            skill_registry_id=skill["registry_id"],
            attending_roster=[
                {"student_id": student["id"], "student_name": student["name"]}
            ],
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-v1",
            prompt_payload={"messages": []},
            memory_context={"records": [], "rendered_text": ""},
        )
        lesson_manager.complete_class_commentary_generation(
            generation["id"],
            "The student made progress and should check the final step.",
        )
        revision = lesson_manager.confirm_class_commentary_feedback(
            task_id=task["id"],
            generation_id=generation["id"],
            teacher_user_id=teacher["id"],
            feedback_text="The student made progress. Check the final step next.",
            learn_requested=True,
            expected_draft_version=0,
            confirmation_request_id=f"{skill_id}-confirmation",
        )
        return class_id, student, skill, task, revision

    def _create_legacy_audit_history(self, teacher, history_key):
        class_id = lesson_manager.save_class(
            f"{history_key} class",
            subject="Math",
            grade="Grade 7",
            organization_id=teacher["organization_id"],
            teacher_user_id=teacher["id"],
        )
        task = lesson_manager.create_class_commentary_task(
            organization_id=teacher["organization_id"],
            class_id=class_id,
            teacher_user_id=teacher["id"],
            audio_path=f"/tmp/{history_key}.m4a",
            audio_filename=f"{history_key}.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            "Legacy transcript snapshot.",
        )
        with lesson_manager.get_conn() as conn:
            generation_cursor = conn.execute(
                """
                INSERT INTO class_commentary_generations (
                    organization_id, task_id, generation_no, teacher_user_id,
                    class_id, subject_key, confirmed_transcript_version,
                    confirmed_transcript_snapshot, confirmed_transcript_hash,
                    attending_roster_snapshot_json, attending_roster_hash,
                    generated_feedback_text, origin, snapshot_completeness,
                    missing_snapshot_fields_json, status, completed_at
                )
                VALUES (?, ?, 1, ?, ?, 'math', 1, ?, ?, '[]', '', ?,
                        'legacy_migration', 'partial', '["skill_registry_id"]',
                        'succeeded', datetime('now','localtime'))
                """,
                (
                    teacher["organization_id"],
                    task["id"],
                    teacher["id"],
                    class_id,
                    "Legacy transcript snapshot.",
                    f"{history_key}-transcript-hash",
                    "Legacy generated feedback.",
                ),
            )
            generation_id = int(generation_cursor.lastrowid)
            revision_cursor = conn.execute(
                """
                INSERT INTO class_commentary_revisions (
                    organization_id, task_id, generation_id, teacher_user_id,
                    revision_no, confirmation_request_id,
                    confirmation_payload_hash, final_feedback_text,
                    generation_diff_json, learning_evidence_schema_version,
                    learning_evidence_selector_version,
                    learning_evidence_snapshot_json,
                    learning_evidence_source_refs_json, learning_evidence_hash,
                    learning_evidence_captured_at,
                    learning_evidence_completeness,
                    learning_evidence_missing_sources_json, learn_requested,
                    accepted_without_edit, unchanged_from_previous_revision
                )
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, '[]', 'legacy-v1',
                        'legacy-v1', '{}', '[]', ?,
                        strftime('%Y-%m-%dT%H:%M:%fZ','now'), 'empty', '[]',
                        0, 1, 0)
                """,
                (
                    teacher["organization_id"],
                    task["id"],
                    generation_id,
                    teacher["id"],
                    f"{history_key}-confirmation",
                    f"{history_key}-confirmation-hash",
                    "Legacy generated feedback.",
                    f"{history_key}-learning-evidence-hash",
                ),
            )
            revision_id = int(revision_cursor.lastrowid)
            conn.execute(
                """
                UPDATE class_commentary_tasks
                SET latest_generation_id=?, latest_revision_id=?, generation_seq=1,
                    feedback_revision_no=1, feedback_text=?, final_feedback_text=?
                WHERE id=?
                """,
                (
                    generation_id,
                    revision_id,
                    "Legacy generated feedback.",
                    "Legacy generated feedback.",
                    task["id"],
                ),
            )
        return class_id, task["id"], generation_id, revision_id

    def test_class_delete_archives_history_and_obsoletes_claimed_learning_job(self):
        class_id, _, _, task, revision = self._create_confirmed_generation(
            self.actor,
            "class-lifecycle-delete",
        )
        job = revision["memory_job"]
        claimed = lesson_manager.claim_class_commentary_memory_extraction_job(
            job["id"],
            claim_owner="delayed-class-delete-worker",
        )

        result = lesson_manager.delete_class(class_id)
        delayed = lesson_manager.commit_class_commentary_memory_extraction(
            job["id"],
            claim_token=claimed["claim_token"],
            items=[
                {
                    "memory_type": "teacher_style",
                    "memory_text": "This delayed style must not be stored",
                    "confidence": 0.9,
                }
            ],
        )

        self.assertEqual(result["action"], "archived")
        self.assertEqual(result["memory_cleanup"]["obsolete_extraction_job_ids"], [job["id"]])
        self.assertEqual(lesson_manager.get_class(class_id)["lifecycle_status"], "archived")
        self.assertIsNone(lesson_manager.get_class_commentary_task(task["id"]))
        self.assertEqual(delayed["job"]["status"], "obsolete")
        self.assertEqual(delayed["records"], [])

    def test_user_with_owned_skill_is_deactivated_without_breaking_audit_fks(self):
        teacher = self._create_teacher(self.actor["organization_id"], "memory-delete-user")
        skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=teacher["organization_id"],
            skill_id="user-lifecycle-delete",
            owner_teacher_user_id=teacher["id"],
            source_path="/skills/user-lifecycle-delete/SKILL.md",
            content="Use concise feedback.",
        )
        token = lesson_manager.create_auth_session(teacher["id"])

        result = lesson_manager.delete_user_for_actor(self.actor, teacher["id"])

        self.assertEqual(result["action"], "deactivated")
        self.assertEqual(lesson_manager.get_user_by_id(teacher["id"])["status"], "inactive")
        self.assertIsNone(lesson_manager.get_current_user(token))
        self.assertNotIn(
            teacher["id"],
            [user["id"] for user in lesson_manager.list_users_for_actor(self.actor)],
        )
        with lesson_manager.get_conn() as conn:
            registry = conn.execute(
                "SELECT status FROM class_commentary_skills WHERE id=?",
                (skill["registry_id"],),
            ).fetchone()
        self.assertEqual(registry["status"], "disabled")

    def test_user_with_only_generation_revision_history_is_deactivated(self):
        teacher = self._create_teacher(self.actor["organization_id"], "legacy-audit-user")
        _, task_id, generation_id, revision_id = self._create_legacy_audit_history(
            teacher,
            "legacy-audit-user",
        )
        with lesson_manager.get_conn() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_skills WHERE owner_teacher_user_id=?",
                    (teacher["id"],),
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_memory_records WHERE created_by_teacher_user_id=?",
                    (teacher["id"],),
                ).fetchone()[0],
                0,
            )

        result = lesson_manager.delete_user_for_actor(self.actor, teacher["id"])

        self.assertEqual(result["action"], "deactivated")
        self.assertEqual(lesson_manager.get_user_by_id(teacher["id"])["status"], "inactive")
        with lesson_manager.get_conn() as conn:
            self.assertIsNotNone(
                conn.execute(
                    "SELECT id FROM class_commentary_tasks WHERE id=?",
                    (task_id,),
                ).fetchone()
            )
            self.assertIsNotNone(
                conn.execute(
                    "SELECT id FROM class_commentary_generations WHERE id=?",
                    (generation_id,),
                ).fetchone()
            )
            self.assertIsNotNone(
                conn.execute(
                    "SELECT id FROM class_commentary_revisions WHERE id=?",
                    (revision_id,),
                ).fetchone()
            )

    def test_organization_delete_forces_revoked_projection_to_deleted_idempotently(self):
        with lesson_manager.get_conn() as conn:
            organization = lesson_manager._ensure_organization(
                conn,
                "Memory lifecycle delete organization",
            )
        teacher = self._create_teacher(organization["id"], "memory-delete-org-owner")
        class_id, _, _, task, revision = self._create_confirmed_generation(
            teacher,
            "organization-lifecycle-delete",
        )
        job = revision["memory_job"]
        claimed_job = lesson_manager.claim_class_commentary_memory_extraction_job(
            job["id"],
            claim_owner="organization-delete-extractor",
        )
        extracted = lesson_manager.commit_class_commentary_memory_extraction(
            job["id"],
            claim_token=claimed_job["claim_token"],
            items=[
                {
                    "memory_type": "teacher_style",
                    "memory_text": "End with one concrete next step",
                    "confidence": 0.9,
                }
            ],
        )
        add_operation = extracted["operations"][0]
        claimed_add = lesson_manager.claim_class_commentary_memory_operation(
            add_operation["id"],
            lease_owner="organization-delete-memory-worker",
        )
        lesson_manager.complete_class_commentary_memory_operation(
            add_operation["id"],
            lease_token=claimed_add["lease_token"],
            mem0_memory_id="mem-org-delete",
            applied_status="active",
        )
        revoked = lesson_manager.revoke_class_commentary_memory_evidence(
            extracted["evidence"][0]["id"],
            actor_user_id=teacher["id"],
            request_id="revoke-before-organization-delete",
        )
        claimed_revoke = lesson_manager.claim_class_commentary_memory_operation(
            revoked["operation"]["id"],
            lease_owner="organization-delete-memory-worker",
        )
        lesson_manager.complete_class_commentary_memory_operation(
            revoked["operation"]["id"],
            lease_token=claimed_revoke["lease_token"],
            mem0_memory_id="mem-org-delete",
            applied_status="revoked",
        )

        result = lesson_manager.delete_organization(organization["id"])
        record = lesson_manager.get_class_commentary_memory_records_by_ids(
            [extracted["records"][0]["id"]]
        )[0]
        operation = lesson_manager.get_class_commentary_memory_operation(
            result["memory_cleanup"]["operation_ids"][0]
        )
        version_before_repeat = record["record_version"]
        operation_count_before_repeat = len(
            lesson_manager.list_dispatchable_class_commentary_memory_operations()
        )
        repeated = lesson_manager.delete_organization(organization["id"])
        repeated_record = lesson_manager.get_class_commentary_memory_records_by_ids(
            [record["id"]]
        )[0]

        self.assertEqual(result["action"], "deactivated")
        self.assertEqual(repeated["action"], "deactivated")
        self.assertEqual(record["desired_status"], "deleted")
        self.assertEqual(operation["cleanup_scope_type"], "organization")
        self.assertEqual(operation["cleanup_scope_id"], organization["id"])
        self.assertEqual(repeated_record["record_version"], version_before_repeat)
        self.assertEqual(
            len(lesson_manager.list_dispatchable_class_commentary_memory_operations()),
            operation_count_before_repeat,
        )
        self.assertEqual(lesson_manager.get_class(class_id)["lifecycle_status"], "archived")
        self.assertIsNone(lesson_manager.get_class_commentary_task(task["id"]))
        with lesson_manager.get_conn() as conn:
            org_row = conn.execute(
                "SELECT status FROM organizations WHERE id=?",
                (organization["id"],),
            ).fetchone()
        self.assertEqual(org_row["status"], "inactive")
        self.assertNotIn(
            organization["id"],
            [item["id"] for item in lesson_manager.list_organizations()],
        )

    def test_organization_with_only_generation_revision_history_is_deactivated(self):
        with lesson_manager.get_conn() as conn:
            organization = lesson_manager._ensure_organization(
                conn,
                "Legacy audit organization",
            )
        teacher = self._create_teacher(organization["id"], "legacy-audit-org-owner")
        _, task_id, generation_id, revision_id = self._create_legacy_audit_history(
            teacher,
            "legacy-audit-organization",
        )
        with lesson_manager.get_conn() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_skills WHERE organization_id=?",
                    (organization["id"],),
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_memory_records WHERE organization_id=?",
                    (organization["id"],),
                ).fetchone()[0],
                0,
            )

        result = lesson_manager.delete_organization(organization["id"])

        self.assertEqual(result["action"], "deactivated")
        with lesson_manager.get_conn() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT status FROM organizations WHERE id=?",
                    (organization["id"],),
                ).fetchone()["status"],
                "inactive",
            )
            self.assertIsNotNone(
                conn.execute(
                    "SELECT id FROM class_commentary_tasks WHERE id=?",
                    (task_id,),
                ).fetchone()
            )
            self.assertIsNotNone(
                conn.execute(
                    "SELECT id FROM class_commentary_generations WHERE id=?",
                    (generation_id,),
                ).fetchone()
            )
            self.assertIsNotNone(
                conn.execute(
                    "SELECT id FROM class_commentary_revisions WHERE id=?",
                    (revision_id,),
                ).fetchone()
            )


if __name__ == "__main__":
    unittest.main()
