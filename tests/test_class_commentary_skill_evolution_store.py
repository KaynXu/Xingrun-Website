import datetime
import json
import os
import sqlite3
import tempfile
import unittest

import lesson_manager


class ClassCommentarySkillEvolutionStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        self.old_enabled = os.environ.get("XR_CLASS_COMMENTARY_MEMORY_ENABLED")
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        os.environ["XR_CLASS_COMMENTARY_MEMORY_ENABLED"] = "true"
        lesson_manager.init_db()
        self.teacher = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class(
            "Skill evolution store test",
            subject="数学",
            grade="七年级",
            organization_id=self.teacher["organization_id"],
            teacher_user_id=self.teacher["id"],
        )
        self.student = lesson_manager.create_student_for_class(
            self.class_id, "Student One"
        )
        self.roster = [
            {
                "student_id": self.student["id"],
                "student_name": self.student["name"],
            }
        ]
        self.skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.teacher["organization_id"],
            skill_id="skill-evolution-store",
            owner_teacher_user_id=self.teacher["id"],
            source_path="/skills/skill-evolution-store/SKILL.md",
            content="Write the classroom result first, then one concrete action.",
        )
        with lesson_manager.get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (
                    username, password_hash, display_name, role, status,
                    organization_id
                )
                VALUES ('other-skill-teacher', 'hash', 'Other Teacher',
                        'member', 'active', ?)
                """,
                (self.teacher["organization_id"],),
            )
            self.other_teacher_id = int(cursor.lastrowid)

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        if self.old_enabled is None:
            os.environ.pop("XR_CLASS_COMMENTARY_MEMORY_ENABLED", None)
        else:
            os.environ["XR_CLASS_COMMENTARY_MEMORY_ENABLED"] = self.old_enabled
        self.tmp.cleanup()

    def _create_sample(
        self,
        suffix,
        *,
        learn_requested=False,
        style_text=None,
        accepted_without_edit=False,
    ):
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.teacher["id"],
            audio_path=f"/tmp/skill-evolution-{suffix}.m4a",
            audio_filename=f"skill-evolution-{suffix}.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            f"Student One completed sample {suffix} and needs one next action.",
        )
        prompt_payload = {
            "messages": [
                {
                    "role": "user",
                    "content": f"Generate feedback for frozen sample {suffix}",
                }
            ]
        }
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=task["id"],
            generation_request_id=f"skill-evolution-generation-{suffix}",
            skill_registry_id=self.skill["registry_id"],
            attending_roster=self.roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-v1",
            prompt_payload=prompt_payload,
            memory_context={"records": []},
        )
        generated_text = f"Student One: sample {suffix} is improving."
        lesson_manager.complete_class_commentary_generation(
            generation["id"], generated_text
        )
        final_text = (
            generated_text
            if accepted_without_edit
            else f"Student One: sample {suffix} is improving; complete one check next."
        )
        revision = lesson_manager.confirm_class_commentary_feedback(
            task_id=task["id"],
            generation_id=generation["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text=final_text,
            learn_requested=learn_requested,
            expected_draft_version=0,
            confirmation_request_id=f"skill-evolution-confirm-{suffix}",
        )
        if style_text is not None:
            job = revision["memory_job"]
            claimed = lesson_manager.claim_class_commentary_memory_extraction_job(
                job["id"], claim_owner="skill-evolution-test"
            )
            self.assertIsNotNone(claimed)
            extraction = lesson_manager.commit_class_commentary_memory_extraction(
                job["id"],
                claim_token=claimed["claim_token"],
                items=[
                    {
                        "memory_type": "teacher_style",
                        "memory_text": style_text,
                        "confidence": 0.95,
                    }
                ],
            )
            self.assertEqual(extraction["job"]["status"], "extracted")
        return {
            "task": task,
            "generation": generation,
            "revision": revision,
            "prompt_payload": prompt_payload,
        }

    def _supported_samples(self):
        style = "End with exactly one concrete next action."
        samples = [
            self._create_sample(
                f"support-{index}", learn_requested=True, style_text=style
            )
            for index in range(3)
        ]
        samples.extend(
            self._create_sample(f"evaluation-{index}") for index in range(2)
        )
        return samples

    def _create_build(self, request_id="skill-candidate-request"):
        return lesson_manager.create_class_commentary_skill_candidate_build(
            organization_id=self.teacher["organization_id"],
            skill_id=self.skill["skill_id"],
            actor_user_id=self.teacher["id"],
            candidate_request_id=request_id,
            expected_active_version_id=self.skill["active_version_id"],
            min_effective_tasks=5,
            min_support_tasks=3,
        )

    def _complete_build(self, build):
        claimed = lesson_manager.claim_class_commentary_skill_candidate_build(
            build["id"], claim_owner="skill-candidate-worker"
        )
        self.assertIsNotNone(claimed)
        return lesson_manager.complete_class_commentary_skill_candidate_build(
            build["id"],
            claim_token=claimed["claim_token"],
            candidate_content=(
                "Write the classroom result first. End with exactly one concrete "
                "next action."
            ),
            evaluation_snapshot={
                "sample_count": 5,
                "student_fact_pollution_count": 0,
                "structure_pass_rate": 1.0,
            },
        )

    def test_schema_creates_candidate_tables_constraints_and_immutable_sources(self):
        with lesson_manager.get_conn() as conn:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            version_fks = conn.execute(
                "PRAGMA foreign_key_list(class_commentary_skill_versions)"
            ).fetchall()
        self.assertTrue(
            {
                "class_commentary_skill_candidate_builds",
                "class_commentary_skill_candidate_revisions",
                "class_commentary_skill_candidate_evidence",
            }.issubset(tables)
        )
        candidate_build_fk = next(
            row for row in version_fks if row["from"] == "candidate_build_id"
        )
        self.assertEqual(
            candidate_build_fk["table"],
            "class_commentary_skill_candidate_builds",
        )

        self._supported_samples()
        build = self._create_build()
        with lesson_manager.get_conn() as conn:
            frozen = conn.execute(
                """
                SELECT * FROM class_commentary_skill_candidate_revisions
                WHERE candidate_build_id=? LIMIT 1
                """,
                (build["id"],),
            ).fetchone()
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    UPDATE class_commentary_skill_candidate_revisions
                    SET revision_snapshot_hash='changed' WHERE id=?
                    """,
                    (frozen["id"],),
                )

    def test_eligibility_and_build_freeze_distinct_latest_effective_tasks(self):
        samples = self._supported_samples()
        eligibility = lesson_manager.get_class_commentary_skill_candidate_eligibility(
            organization_id=self.teacher["organization_id"],
            skill_id=self.skill["skill_id"],
            actor_user_id=self.teacher["id"],
            min_effective_tasks=5,
            min_support_tasks=3,
        )
        self.assertTrue(eligibility["eligible"])
        self.assertEqual(eligibility["effective_task_count"], 5)
        self.assertEqual(eligibility["supporting_task_count"], 3)

        build = self._create_build()
        self.assertEqual(build["status"], "queued")
        self.assertEqual(build["effective_task_count"], 5)
        self.assertEqual(build["supporting_task_count"], 3)
        self.assertEqual(
            {item["task_id"] for item in build["frozen_revisions"]},
            {item["task"]["id"] for item in samples},
        )
        self.assertEqual(len(build["frozen_revisions"]), 5)
        self.assertEqual(len(build["frozen_evidence"]), 3)
        self.assertEqual(len(build["source_snapshot_hash"]), 64)

        repeated = self._create_build()
        self.assertEqual(repeated["id"], build["id"])
        with self.assertRaises(
            lesson_manager.ClassCommentarySkillCandidateRequestConflict
        ):
            lesson_manager.create_class_commentary_skill_candidate_build(
                organization_id=self.teacher["organization_id"],
                skill_id=self.skill["skill_id"],
                actor_user_id=self.teacher["id"],
                candidate_request_id="skill-candidate-request",
                expected_active_version_id=self.skill["active_version_id"] + 999,
                min_effective_tasks=5,
                min_support_tasks=3,
            )
        with self.assertRaises(PermissionError):
            lesson_manager.get_class_commentary_skill_candidate_eligibility(
                organization_id=self.teacher["organization_id"],
                skill_id=self.skill["skill_id"],
                actor_user_id=self.other_teacher_id,
                min_effective_tasks=5,
                min_support_tasks=3,
            )

    def test_latest_no_learning_revision_blocks_fallback_to_old_style_evidence(self):
        sample = self._create_sample(
            "old-style",
            learn_requested=True,
            style_text="End with exactly one concrete next action.",
        )
        replacement = lesson_manager.confirm_class_commentary_feedback(
            task_id=sample["task"]["id"],
            generation_id=sample["generation"]["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text="Student One: latest final text without learning.",
            learn_requested=False,
            expected_draft_version=1,
            confirmation_request_id="skill-evolution-latest-no-learning",
        )
        eligibility = lesson_manager.get_class_commentary_skill_candidate_eligibility(
            organization_id=self.teacher["organization_id"],
            skill_id=self.skill["skill_id"],
            actor_user_id=self.teacher["id"],
            min_effective_tasks=1,
            min_support_tasks=1,
        )
        self.assertEqual(eligibility["effective_task_count"], 1)
        self.assertEqual(eligibility["supporting_task_count"], 0)
        self.assertFalse(eligibility["eligible"])
        with self.assertRaises(lesson_manager.ClassCommentarySkillCandidateNotReady):
            lesson_manager.create_class_commentary_skill_candidate_build(
                organization_id=self.teacher["organization_id"],
                skill_id=self.skill["skill_id"],
                actor_user_id=self.teacher["id"],
                candidate_request_id="no-fallback-candidate",
                expected_active_version_id=self.skill["active_version_id"],
                min_effective_tasks=1,
                min_support_tasks=1,
            )
        with lesson_manager.get_conn() as conn:
            frozen_count = conn.execute(
                "SELECT COUNT(*) AS value FROM class_commentary_skill_candidate_builds"
            ).fetchone()["value"]
            old_evidence = conn.execute(
                """
                SELECT status FROM class_commentary_memory_evidence
                WHERE revision_id=?
                """,
                (sample["revision"]["id"],),
            ).fetchone()
        self.assertEqual(int(frozen_count), 0)
        self.assertEqual(old_evidence["status"], "superseded")
        self.assertEqual(
            lesson_manager.get_class_commentary_revision(replacement["id"])["id"],
            replacement["id"],
        )

    def test_accepted_without_edit_never_counts_as_style_support(self):
        self._create_sample(
            "accepted",
            learn_requested=True,
            style_text="End with exactly one concrete next action.",
            accepted_without_edit=True,
        )
        eligibility = lesson_manager.get_class_commentary_skill_candidate_eligibility(
            organization_id=self.teacher["organization_id"],
            skill_id=self.skill["skill_id"],
            actor_user_id=self.teacher["id"],
            min_effective_tasks=1,
            min_support_tasks=1,
        )
        self.assertEqual(eligibility["effective_task_count"], 1)
        self.assertEqual(eligibility["supporting_task_count"], 0)
        self.assertFalse(eligibility["eligible"])

    def test_claim_retry_finalize_freezes_prompt_and_candidate_evaluation(self):
        samples = self._supported_samples()
        build = self._create_build()
        claimed = lesson_manager.claim_class_commentary_skill_candidate_build(
            build["id"],
            claim_owner="skill-candidate-worker",
            now="2026-07-14T12:00:00.000000Z",
        )
        self.assertEqual(claimed["attempt_count"], 1)
        self.assertIsNone(
            lesson_manager.claim_class_commentary_skill_candidate_build(
                build["id"],
                claim_owner="second-worker",
                now="2026-07-14T12:00:00.000000Z",
            )
        )
        failed = lesson_manager.fail_class_commentary_skill_candidate_build(
            build["id"],
            claim_token=claimed["claim_token"],
            error="temporary model failure",
            now=datetime.datetime(2026, 7, 14, 12, 0, 0),
        )
        self.assertEqual(failed["status"], "retry_wait")
        self.assertEqual(failed["next_attempt_at"], "2026-07-14T12:01:00.000000Z")
        self.assertIsNone(
            lesson_manager.claim_class_commentary_skill_candidate_build(
                build["id"],
                claim_owner="early-worker",
                now="2026-07-14T12:00:59.000000Z",
            )
        )
        retry_claim = lesson_manager.claim_class_commentary_skill_candidate_build(
            build["id"],
            claim_owner="retry-worker",
            now="2026-07-14T12:01:00.000000Z",
        )
        self.assertEqual(retry_claim["attempt_count"], 2)
        frozen_input = lesson_manager.get_class_commentary_skill_candidate_build_input(
            build["id"]
        )
        self.assertTrue(frozen_input["source_valid"])
        self.assertEqual(len(frozen_input["revision_samples"]), 5)
        prompt_by_task_id = {
            item["task_id"]: item["prompt_payload"]
            for item in frozen_input["revision_samples"]
        }
        self.assertEqual(
            prompt_by_task_id[samples[0]["task"]["id"]],
            samples[0]["prompt_payload"],
        )
        completed = lesson_manager.complete_class_commentary_skill_candidate_build(
            build["id"],
            claim_token=retry_claim["claim_token"],
            candidate_content="Use one concise result and one concrete next action.",
            evaluation_snapshot={
                "sample_count": 5,
                "student_fact_pollution_count": 0,
            },
        )
        self.assertEqual(completed["status"], "succeeded")
        self.assertIsNotNone(completed["candidate_version_id"])
        versions = lesson_manager.list_class_commentary_skill_versions_for_teacher(
            organization_id=self.teacher["organization_id"],
            skill_id=self.skill["skill_id"],
            actor_user_id=self.teacher["id"],
        )
        candidate = versions[0]
        self.assertEqual(candidate["version_kind"], "candidate")
        self.assertEqual(candidate["review_status"], "pending")
        self.assertEqual(candidate["evaluation_snapshot"]["sample_count"], 5)
        self.assertFalse(candidate["is_active"])
        with lesson_manager.get_conn() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    UPDATE class_commentary_skill_versions
                    SET content='mutated' WHERE id=?
                    """,
                    (candidate["id"],),
                )

    def test_finalize_marks_build_obsolete_when_frozen_revision_changes(self):
        samples = self._supported_samples()
        build = self._create_build()
        claimed = lesson_manager.claim_class_commentary_skill_candidate_build(
            build["id"], claim_owner="skill-candidate-worker"
        )
        changed = samples[0]
        lesson_manager.confirm_class_commentary_feedback(
            task_id=changed["task"]["id"],
            generation_id=changed["generation"]["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text="Student One: a newer effective final text.",
            learn_requested=False,
            expected_draft_version=1,
            confirmation_request_id="skill-source-changed-after-claim",
        )
        completed = lesson_manager.complete_class_commentary_skill_candidate_build(
            build["id"],
            claim_token=claimed["claim_token"],
            candidate_content="This candidate must not be saved.",
            evaluation_snapshot={"sample_count": 5},
        )
        self.assertEqual(completed["status"], "obsolete")
        self.assertEqual(completed["stale_reason"], "revision_not_effective")
        with lesson_manager.get_conn() as conn:
            candidate_count = conn.execute(
                """
                SELECT COUNT(*) AS value FROM class_commentary_skill_versions
                WHERE version_kind='candidate'
                """
            ).fetchone()["value"]
        self.assertEqual(int(candidate_count), 0)

    def test_prompt_snapshot_tampering_fails_candidate_integrity_gate(self):
        samples = self._supported_samples()
        build = self._create_build()
        claimed = lesson_manager.claim_class_commentary_skill_candidate_build(
            build["id"], claim_owner="skill-candidate-worker"
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET prompt_payload_snapshot_json=? WHERE id=?
                """,
                (
                    json.dumps(
                        {"messages": [{"role": "user", "content": "tampered"}]},
                        separators=(",", ":"),
                    ),
                    samples[0]["generation"]["id"],
                ),
            )
        completed = lesson_manager.complete_class_commentary_skill_candidate_build(
            build["id"],
            claim_token=claimed["claim_token"],
            candidate_content="This candidate must fail its frozen prompt integrity gate.",
            evaluation_snapshot={"sample_count": 5},
        )
        self.assertEqual(completed["status"], "obsolete")
        self.assertEqual(completed["stale_reason"], "revision_snapshot_mismatch")
        self.assertIsNone(completed["candidate_version_id"])

    def test_retry_limit_and_stale_running_recovery_reject_old_claim(self):
        self._supported_samples()
        build = self._create_build()
        first_claim = lesson_manager.claim_class_commentary_skill_candidate_build(
            build["id"],
            claim_owner="abandoned-worker",
            now="2026-07-14T12:00:00.000000Z",
        )
        recovered = lesson_manager.recover_stale_class_commentary_skill_candidate_builds(
            timeout_seconds=300,
            now=datetime.datetime(2026, 7, 14, 12, 7, 0),
        )
        self.assertEqual(recovered[0]["status"], "retry_wait")
        old_claim_result = lesson_manager.complete_class_commentary_skill_candidate_build(
            build["id"],
            claim_token=first_claim["claim_token"],
            candidate_content="An abandoned worker must not create this version.",
            evaluation_snapshot={"sample_count": 5},
        )
        self.assertEqual(old_claim_result["status"], "retry_wait")
        self.assertIsNone(old_claim_result["candidate_version_id"])

        second_claim = lesson_manager.claim_class_commentary_skill_candidate_build(
            build["id"],
            claim_owner="second-worker",
            now="2026-07-14T12:07:00.000000Z",
        )
        second_failure = lesson_manager.fail_class_commentary_skill_candidate_build(
            build["id"],
            claim_token=second_claim["claim_token"],
            error="second automatic attempt failed",
            now=datetime.datetime(2026, 7, 14, 12, 7, 0),
        )
        self.assertEqual(second_failure["status"], "retry_wait")
        self.assertEqual(
            second_failure["next_attempt_at"], "2026-07-14T12:12:00.000000Z"
        )
        third_claim = lesson_manager.claim_class_commentary_skill_candidate_build(
            build["id"],
            claim_owner="third-worker",
            now="2026-07-14T12:12:00.000000Z",
        )
        third_failure = lesson_manager.fail_class_commentary_skill_candidate_build(
            build["id"],
            claim_token=third_claim["claim_token"],
            error="third automatic attempt failed",
            now=datetime.datetime(2026, 7, 14, 12, 12, 0),
        )
        self.assertEqual(third_failure["status"], "failed")
        self.assertIsNone(third_failure["next_attempt_at"])
        self.assertEqual(
            lesson_manager.list_dispatchable_class_commentary_skill_candidate_builds(
                now="2026-07-15T12:12:00.000000Z"
            ),
            [],
        )

    def test_activation_is_idempotent_uses_cas_and_rollback_keeps_history(self):
        self._supported_samples()
        build = self._create_build()
        completed = self._complete_build(build)
        candidate_version_id = completed["candidate_version_id"]
        activated = lesson_manager.activate_class_commentary_skill_candidate_version(
            organization_id=self.teacher["organization_id"],
            skill_id=self.skill["skill_id"],
            actor_user_id=self.teacher["id"],
            version_id=candidate_version_id,
            activation_request_id="activate-candidate-v2",
            expected_active_version_id=self.skill["active_version_id"],
        )
        self.assertEqual(activated["reason"], "candidate_approved")
        self.assertEqual(activated["active_version_id"], candidate_version_id)
        replay = lesson_manager.activate_class_commentary_skill_candidate_version(
            organization_id=self.teacher["organization_id"],
            skill_id=self.skill["skill_id"],
            actor_user_id=self.teacher["id"],
            version_id=candidate_version_id,
            activation_request_id="activate-candidate-v2",
            expected_active_version_id=self.skill["active_version_id"],
        )
        self.assertEqual(replay["id"], activated["id"])
        with self.assertRaises(
            lesson_manager.ClassCommentarySkillActivationRequestConflict
        ):
            lesson_manager.activate_class_commentary_skill_candidate_version(
                organization_id=self.teacher["organization_id"],
                skill_id=self.skill["skill_id"],
                actor_user_id=self.teacher["id"],
                version_id=candidate_version_id,
                activation_request_id="activate-candidate-v2",
                expected_active_version_id=candidate_version_id,
            )
        with self.assertRaises(lesson_manager.ClassCommentarySkillVersionConflict):
            lesson_manager.rollback_class_commentary_skill_version(
                organization_id=self.teacher["organization_id"],
                skill_id=self.skill["skill_id"],
                actor_user_id=self.teacher["id"],
                version_id=candidate_version_id,
                activation_request_id="rollback-wrong-cas",
                expected_active_version_id=self.skill["active_version_id"],
            )
        rolled_back = lesson_manager.rollback_class_commentary_skill_version(
            organization_id=self.teacher["organization_id"],
            skill_id=self.skill["skill_id"],
            actor_user_id=self.teacher["id"],
            version_id=self.skill["active_version_id"],
            activation_request_id="rollback-to-v1",
            expected_active_version_id=candidate_version_id,
        )
        self.assertEqual(rolled_back["reason"], "rollback")
        self.assertEqual(
            rolled_back["active_version_id"], self.skill["active_version_id"]
        )
        versions = lesson_manager.list_class_commentary_skill_versions_for_teacher(
            organization_id=self.teacher["organization_id"],
            skill_id=self.skill["skill_id"],
            actor_user_id=self.teacher["id"],
        )
        self.assertEqual(len(versions), 2)
        self.assertEqual(
            next(item for item in versions if item["id"] == candidate_version_id)[
                "review_status"
            ],
            "approved",
        )
        with lesson_manager.get_conn() as conn:
            events = conn.execute(
                """
                SELECT reason FROM class_commentary_skill_activation_events
                WHERE skill_registry_id=? ORDER BY id
                """,
                (self.skill["registry_id"],),
            ).fetchall()
        self.assertEqual(
            [row["reason"] for row in events],
            ["initial_import", "candidate_approved", "rollback"],
        )
        old_activation_replay = lesson_manager.activate_class_commentary_skill_candidate_version(
            organization_id=self.teacher["organization_id"],
            skill_id=self.skill["skill_id"],
            actor_user_id=self.teacher["id"],
            version_id=candidate_version_id,
            activation_request_id="activate-candidate-v2",
            expected_active_version_id=self.skill["active_version_id"],
        )
        self.assertEqual(old_activation_replay["active_version_id"], candidate_version_id)
        self.assertEqual(
            old_activation_replay["current_active_version_id"],
            self.skill["active_version_id"],
        )

    def test_stale_candidate_cannot_activate_or_use_other_owner(self):
        samples = self._supported_samples()
        build = self._create_build()
        completed = self._complete_build(build)
        candidate_version_id = completed["candidate_version_id"]
        changed = samples[0]
        lesson_manager.confirm_class_commentary_feedback(
            task_id=changed["task"]["id"],
            generation_id=changed["generation"]["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text="Student One: source changed before activation.",
            learn_requested=False,
            expected_draft_version=1,
            confirmation_request_id="skill-source-changed-before-activation",
        )
        with self.assertRaises(lesson_manager.ClassCommentarySkillCandidateStale):
            lesson_manager.activate_class_commentary_skill_candidate_version(
                organization_id=self.teacher["organization_id"],
                skill_id=self.skill["skill_id"],
                actor_user_id=self.teacher["id"],
                version_id=candidate_version_id,
                activation_request_id="stale-candidate-activation",
                expected_active_version_id=self.skill["active_version_id"],
            )
        with self.assertRaises(PermissionError):
            lesson_manager.list_class_commentary_skill_versions_for_teacher(
                organization_id=self.teacher["organization_id"],
                skill_id=self.skill["skill_id"],
                actor_user_id=self.other_teacher_id,
            )
        versions = lesson_manager.list_class_commentary_skill_versions_for_teacher(
            organization_id=self.teacher["organization_id"],
            skill_id=self.skill["skill_id"],
            actor_user_id=self.teacher["id"],
        )
        candidate = next(
            item for item in versions if item["id"] == candidate_version_id
        )
        self.assertTrue(candidate["is_stale"])
        self.assertEqual(candidate["stale_reason"], "revision_not_effective")
        self.assertEqual(candidate["review_status"], "pending")
        active = lesson_manager.get_class_commentary_skill_for_teacher(
            self.teacher["organization_id"],
            self.teacher["id"],
            self.skill["skill_id"],
        )
        self.assertEqual(active["active_version_id"], self.skill["active_version_id"])


if __name__ == "__main__":
    unittest.main()
