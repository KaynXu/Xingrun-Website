import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_runtime
import lesson_manager


class ClassCommentarySkillEvolutionApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.old_db = lesson_manager.DB_PATH
        self.old_cfg = config_runtime.CFG_PATH
        self.old_enabled = os.environ.get("XR_CLASS_COMMENTARY_MEMORY_ENABLED")
        lesson_manager.DB_PATH = self.base / "test.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        os.environ["XR_CLASS_COMMENTARY_MEMORY_ENABLED"] = "true"
        config_runtime.write_file_config(
            {
                "class_commentary_memory_enabled": True,
                "skill_evolution_min_effective_tasks": 5,
                "skill_evolution_min_support_tasks": 3,
            }
        )
        lesson_manager.init_db()
        self.app_module = importlib.import_module("app")
        self.capabilities_patcher = patch.object(
            self.app_module,
            "_class_commentary_memory_capabilities",
            return_value={
                "memory_learning_enabled": True,
                "skill_evolution_enabled": True,
            },
        )
        self.capabilities_patcher.start()
        self.addCleanup(self.capabilities_patcher.stop)
        self.client = self.app_module.app.test_client()
        self.owner, self.headers = self._login("Kayn", "xingrun2026")
        self.class_id = lesson_manager.save_class(
            "Skill evolution API class",
            subject="数学",
            grade="七年级",
            organization_id=self.owner["organization_id"],
            teacher_user_id=self.owner["id"],
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
            organization_id=self.owner["organization_id"],
            skill_id="skill-evolution-api",
            actor_user_id=self.owner["id"],
            source_path=str(self.base / "skill-evolution-api.skill"),
            content="Write the result first, then one concrete next action.",
        )

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        config_runtime.CFG_PATH = self.old_cfg
        if self.old_enabled is None:
            os.environ.pop("XR_CLASS_COMMENTARY_MEMORY_ENABLED", None)
        else:
            os.environ["XR_CLASS_COMMENTARY_MEMORY_ENABLED"] = self.old_enabled
        self.tmp.cleanup()

    def _login(self, username, password):
        response = self.client.post(
            "/api/login", json={"username": username, "password": password}
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        return payload["user"], {"X-Auth-Token": payload["token"]}

    def _create_user(self, *, username, organization_id):
        password = "memberpass123"
        with lesson_manager.get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (
                    username, password_hash, display_name, role, status,
                    organization_id
                )
                VALUES (?, ?, ?, 'member', 'active', ?)
                """,
                (
                    username,
                    lesson_manager.hash_password(password),
                    username,
                    organization_id,
                ),
            )
        user, headers = self._login(username, password)
        return int(cursor.lastrowid), user, headers

    def _create_sample(self, suffix, *, learn_requested=False, style_text=None):
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.owner["id"],
            audio_path=f"/tmp/skill-api-{suffix}.m4a",
            audio_filename=f"skill-api-{suffix}.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"], f"Student One completed frozen sample {suffix}."
        )
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=task["id"],
            generation_request_id=f"skill-api-generation-{suffix}",
            skill_registry_id=self.skill["registry_id"],
            attending_roster=self.roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-v1",
            prompt_payload={
                "messages": [
                    {
                        "role": "user",
                        "content": f"Generate frozen feedback {suffix}",
                    }
                ]
            },
            memory_context={"records": []},
        )
        generated_text = f"Student One: sample {suffix} improved."
        lesson_manager.complete_class_commentary_generation(
            generation["id"], generated_text
        )
        revision = lesson_manager.confirm_class_commentary_feedback(
            task_id=task["id"],
            generation_id=generation["id"],
            teacher_user_id=self.owner["id"],
            feedback_text=(
                f"Student One: sample {suffix} improved; complete one check next."
            ),
            learn_requested=learn_requested,
            expected_draft_version=0,
            confirmation_request_id=f"skill-api-confirm-{suffix}",
        )
        if style_text is not None:
            job = revision["memory_job"]
            claimed = lesson_manager.claim_class_commentary_memory_extraction_job(
                job["id"], claim_owner="skill-api-test"
            )
            lesson_manager.commit_class_commentary_memory_extraction(
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
        return {"task": task, "generation": generation, "revision": revision}

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

    def _candidate_path(self):
        return f"/api/class-commentary/skills/{self.skill['skill_id']}/candidates"

    def _versions_path(self):
        return f"/api/class-commentary/skills/{self.skill['skill_id']}/versions"

    def _skill_evolution_state(self):
        with lesson_manager.get_conn() as conn:
            registry = conn.execute(
                "SELECT active_version_id FROM class_commentary_skills WHERE id=?",
                (self.skill["registry_id"],),
            ).fetchone()
            return {
                "active_version_id": int(registry["active_version_id"]),
                "candidate_build_count": int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM class_commentary_skill_candidate_builds
                        WHERE skill_registry_id=?
                        """,
                        (self.skill["registry_id"],),
                    ).fetchone()[0]
                ),
                "version_count": int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM class_commentary_skill_versions
                        WHERE skill_registry_id=?
                        """,
                        (self.skill["registry_id"],),
                    ).fetchone()[0]
                ),
                "activation_event_count": int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM class_commentary_skill_activation_events
                        WHERE skill_registry_id=?
                        """,
                        (self.skill["registry_id"],),
                    ).fetchone()[0]
                ),
            }

    def _create_candidate(self, request_id="api-candidate-request"):
        with patch.object(
            self.app_module,
            "_dispatch_class_commentary_memory_best_effort",
            return_value={"enabled": True, "candidates": 1},
        ) as dispatch:
            response = self.client.post(
                self._candidate_path(),
                headers=self.headers,
                json={
                    "request_id": request_id,
                    "expected_active_version_id": self.skill["active_version_id"],
                },
            )
        dispatch.assert_called_once_with()
        return response

    def _complete_candidate(self, request_id="api-candidate-request"):
        response = self._create_candidate(request_id)
        self.assertEqual(response.status_code, 202)
        build = response.get_json()["build"]
        claimed = lesson_manager.claim_class_commentary_skill_candidate_build(
            build["id"], claim_owner="skill-api-worker"
        )
        completed = lesson_manager.complete_class_commentary_skill_candidate_build(
            build["id"],
            claim_token=claimed["claim_token"],
            candidate_content=(
                "Write the result first. End with exactly one concrete next action."
            ),
            evaluation_snapshot={
                "metrics": {
                    "current": {"acceptance_rate": 0.2},
                    "candidate": {"acceptance_rate": 0.8},
                },
                "known_risks": ["Short evidence window"],
                "failed_samples": [],
                "student_fact_pollution_count": 0,
            },
        )
        return completed

    def test_disabled_capability_blocks_all_mutations_without_database_writes(self):
        _, _, same_org_headers = self._create_user(
            username="disabled-capability-same-org",
            organization_id=self.owner["organization_id"],
        )
        before = self._skill_evolution_state()
        active_version_id = self.skill["active_version_id"]
        payload = {
            "request_id": "disabled-skill-evolution",
            "expected_active_version_id": active_version_id,
        }
        with patch.object(
            self.app_module,
            "_class_commentary_memory_capabilities",
            return_value={
                "memory_learning_enabled": False,
                "skill_evolution_enabled": False,
            },
        ) as capabilities, patch.object(
            self.app_module,
            "_dispatch_class_commentary_memory_best_effort",
        ) as dispatch:
            same_org_responses = [
                self.client.post(
                    self._candidate_path(), headers=same_org_headers, json=payload
                ),
                self.client.post(
                    f"{self._versions_path()}/{active_version_id}/activate",
                    headers=same_org_headers,
                    json=payload,
                ),
                self.client.post(
                    f"{self._versions_path()}/{active_version_id}/rollback",
                    headers=same_org_headers,
                    json=payload,
                ),
            ]
            for response in same_org_responses:
                self.assertEqual(response.status_code, 409)
                self.assertEqual(
                    response.get_json(), {"error": "skill_evolution_disabled"}
                )
            responses = [
                self.client.post(
                    self._candidate_path(), headers=self.headers, json=payload
                ),
                self.client.post(
                    f"{self._versions_path()}/{active_version_id}/activate",
                    headers=self.headers,
                    json=payload,
                ),
                self.client.post(
                    f"{self._versions_path()}/{active_version_id}/rollback",
                    headers=self.headers,
                    json=payload,
                ),
            ]
            self.assertEqual(capabilities.call_count, 6)
            dispatch.assert_not_called()

        for response in responses:
            self.assertEqual(response.status_code, 409)
            self.assertEqual(
                response.get_json(), {"error": "skill_evolution_disabled"}
            )
        self.assertEqual(self._skill_evolution_state(), before)

    def test_candidate_validation_not_ready_and_request_conflicts_are_safe(self):
        missing_request = self.client.post(
            self._candidate_path(),
            headers=self.headers,
            json={"expected_active_version_id": self.skill["active_version_id"]},
        )
        invalid_version = self.client.post(
            self._candidate_path(),
            headers=self.headers,
            json={"request_id": "invalid-version", "expected_active_version_id": True},
        )
        not_ready = self.client.post(
            self._candidate_path(),
            headers=self.headers,
            json={
                "request_id": "not-ready",
                "expected_active_version_id": self.skill["active_version_id"],
            },
        )
        self.assertEqual(missing_request.status_code, 400)
        self.assertEqual(missing_request.get_json()["error"], "request_id is required")
        self.assertEqual(invalid_version.status_code, 400)
        self.assertEqual(not_ready.status_code, 409)
        self.assertEqual(not_ready.get_json()["error"], "candidate_not_ready")
        self.assertEqual(not_ready.get_json()["effective_task_count"], 0)
        self.assertNotIn("last_error", not_ready.get_json())

        self._supported_samples()
        first = self._create_candidate("idempotent-candidate")
        replay = self._create_candidate("idempotent-candidate")
        self.assertEqual(first.status_code, 202)
        self.assertEqual(replay.status_code, 202)
        self.assertEqual(first.get_json()["build"]["id"], replay.get_json()["build"]["id"])
        conflict = self.client.post(
            self._candidate_path(),
            headers=self.headers,
            json={
                "request_id": "idempotent-candidate",
                "expected_active_version_id": self.skill["active_version_id"] + 999,
            },
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.get_json(), {"error": "candidate_request_conflict"})
        with lesson_manager.get_conn() as conn:
            build_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_skill_candidate_builds"
            ).fetchone()[0]
        self.assertEqual(build_count, 1)

    def test_get_versions_envelope_and_candidate_response_hide_internal_state(self):
        self._supported_samples()
        created = self._create_candidate()
        self.assertEqual(created.status_code, 202)
        build = created.get_json()["build"]
        self.assertEqual(build["status"], "queued")
        self.assertEqual(build["effective_task_count"], 5)
        self.assertEqual(build["supporting_task_count"], 3)
        self.assertEqual(len(build["frozen_revision_ids"]), 5)
        self.assertEqual(len(build["frozen_evidence_ids"]), 3)
        self.assertNotIn("claim_token", build)
        self.assertNotIn("claim_owner", build)
        self.assertNotIn("last_error", build)

        listed = self.client.get(self._versions_path(), headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        payload = listed.get_json()
        self.assertEqual(set(payload), {"skill", "versions", "candidate_builds", "eligibility"})
        self.assertEqual(payload["skill"]["active_version_id"], self.skill["active_version_id"])
        self.assertTrue(payload["eligibility"]["eligible"])
        self.assertEqual(payload["eligibility"]["min_supporting_tasks"], 3)
        self.assertEqual(payload["candidate_builds"][0]["id"], build["id"])
        self.assertEqual(len(payload["versions"]), 1)
        self.assertEqual(payload["versions"][0]["version_kind"], "imported")

        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_skill_candidate_builds
                SET status='failed', last_error='provider-secret-detail',
                    completed_at='2026-07-14T12:00:00.000000Z'
                WHERE id=?
                """,
                (build["id"],),
            )
        failed_payload = self.client.get(
            self._versions_path(), headers=self.headers
        ).get_json()["candidate_builds"][0]
        self.assertEqual(failed_payload["status"], "failed")
        self.assertNotIn("last_error", failed_payload)
        self.assertNotIn("provider-secret-detail", failed_payload["error_message"])

    def test_completed_candidate_version_returns_diff_evaluation_and_frozen_ids(self):
        self._supported_samples()
        completed = self._complete_candidate()
        listed = self.client.get(self._versions_path(), headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        payload = listed.get_json()
        candidate = payload["versions"][0]
        self.assertEqual(candidate["id"], completed["candidate_version_id"])
        self.assertEqual(candidate["base_content"], self.skill["content"])
        self.assertIn("version-1", candidate["content_diff"])
        self.assertIn("version-2", candidate["content_diff"])
        self.assertEqual(
            candidate["evaluation"]["candidate_metrics"]["acceptance_rate"],
            0.8,
        )
        self.assertFalse(candidate["is_active"])
        self.assertEqual(candidate["frozen_revision_count"], 5)
        self.assertEqual(candidate["frozen_evidence_count"], 3)
        self.assertEqual(len(candidate["frozen_revision_ids"]), 5)
        self.assertEqual(len(candidate["frozen_evidence_ids"]), 3)
        self.assertEqual(payload["candidate_builds"][0]["status"], "succeeded")
        self.assertNotIn("last_error", payload["candidate_builds"][0])

    def test_activate_idempotency_cas_and_rollback_response_envelopes(self):
        self._supported_samples()
        completed = self._complete_candidate()
        candidate_version_id = completed["candidate_version_id"]
        activate_path = (
            f"{self._versions_path()}/{candidate_version_id}/activate"
        )
        activation_body = {
            "request_id": "api-activate-candidate",
            "expected_active_version_id": self.skill["active_version_id"],
        }
        activated = self.client.post(
            activate_path, headers=self.headers, json=activation_body
        )
        replay = self.client.post(
            activate_path, headers=self.headers, json=activation_body
        )
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        payload = activated.get_json()
        self.assertEqual(set(payload), {"skill", "version", "activation_event"})
        self.assertEqual(payload["skill"]["active_version_id"], candidate_version_id)
        self.assertTrue(payload["version"]["is_active"])
        self.assertEqual(payload["version"]["review_status"], "approved")
        self.assertEqual(payload["activation_event"]["reason"], "candidate_approved")
        self.assertEqual(
            replay.get_json()["activation_event"]["id"],
            payload["activation_event"]["id"],
        )

        activation_conflict = self.client.post(
            activate_path,
            headers=self.headers,
            json={
                "request_id": "api-activate-candidate",
                "expected_active_version_id": candidate_version_id,
            },
        )
        self.assertEqual(activation_conflict.status_code, 409)
        self.assertEqual(
            activation_conflict.get_json(), {"error": "activation_request_conflict"}
        )

        wrong_cas = self.client.post(
            f"{self._versions_path()}/{candidate_version_id}/rollback",
            headers=self.headers,
            json={
                "request_id": "api-rollback-wrong-cas",
                "expected_active_version_id": self.skill["active_version_id"],
            },
        )
        self.assertEqual(wrong_cas.status_code, 409)
        self.assertEqual(wrong_cas.get_json(), {"error": "skill_version_conflict"})

        rolled_back = self.client.post(
            f"{self._versions_path()}/{self.skill['active_version_id']}/rollback",
            headers=self.headers,
            json={
                "request_id": "api-rollback-v1",
                "expected_active_version_id": candidate_version_id,
            },
        )
        self.assertEqual(rolled_back.status_code, 200)
        rollback_payload = rolled_back.get_json()
        self.assertEqual(
            rollback_payload["skill"]["active_version_id"],
            self.skill["active_version_id"],
        )
        self.assertEqual(rollback_payload["activation_event"]["reason"], "rollback")
        with lesson_manager.get_conn() as conn:
            event_count = conn.execute(
                """
                SELECT COUNT(*) FROM class_commentary_skill_activation_events
                WHERE skill_registry_id=?
                """,
                (self.skill["registry_id"],),
            ).fetchone()[0]
        self.assertEqual(event_count, 3)

    def test_stale_candidate_same_org_access_and_cross_org_isolation(self):
        samples = self._supported_samples()
        completed = self._complete_candidate()
        candidate_version_id = completed["candidate_version_id"]
        changed = samples[0]
        lesson_manager.confirm_class_commentary_feedback(
            task_id=changed["task"]["id"],
            generation_id=changed["generation"]["id"],
            teacher_user_id=self.owner["id"],
            feedback_text="Student One: a newer effective final text.",
            learn_requested=False,
            expected_draft_version=1,
            confirmation_request_id="api-stale-source",
        )
        stale = self.client.post(
            f"{self._versions_path()}/{candidate_version_id}/activate",
            headers=self.headers,
            json={
                "request_id": "api-stale-activation",
                "expected_active_version_id": self.skill["active_version_id"],
            },
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.get_json()["error"], "candidate_stale")
        self.assertEqual(stale.get_json()["stale_reason"], "revision_not_effective")

        _, _, member_headers = self._create_user(
            username="same-org-other-teacher",
            organization_id=self.owner["organization_id"],
        )
        with lesson_manager.get_conn() as conn:
            other_org_id = int(
                conn.execute(
                    "INSERT INTO organizations (name) VALUES ('Other API Org')"
                ).lastrowid
            )
        _, _, other_org_headers = self._create_user(
            username="other-org-teacher",
            organization_id=other_org_id,
        )
        same_org_list = self.client.get(self._versions_path(), headers=member_headers)
        self.assertEqual(same_org_list.status_code, 200)
        self.assertEqual(
            same_org_list.get_json()["skill"]["skill_id"],
            self.skill["skill_id"],
        )

        for headers in (other_org_headers,):
            listed = self.client.get(self._versions_path(), headers=headers)
            created = self.client.post(
                self._candidate_path(),
                headers=headers,
                json={
                    "request_id": "unauthorized-candidate",
                    "expected_active_version_id": self.skill["active_version_id"],
                },
            )
            activated = self.client.post(
                f"{self._versions_path()}/{candidate_version_id}/activate",
                headers=headers,
                json={
                    "request_id": "unauthorized-activation",
                    "expected_active_version_id": self.skill["active_version_id"],
                },
            )
            rolled_back = self.client.post(
                f"{self._versions_path()}/{self.skill['active_version_id']}/rollback",
                headers=headers,
                json={
                    "request_id": "unauthorized-rollback",
                    "expected_active_version_id": candidate_version_id,
                },
            )
            self.assertEqual(listed.status_code, 404)
            self.assertEqual(created.status_code, 404)
            self.assertEqual(activated.status_code, 404)
            self.assertEqual(rolled_back.status_code, 404)
            self.assertEqual(listed.get_json(), {"error": "not found"})
            self.assertEqual(created.get_json(), {"error": "not found"})
            self.assertEqual(activated.get_json(), {"error": "not found"})
            self.assertEqual(rolled_back.get_json(), {"error": "not found"})


if __name__ == "__main__":
    unittest.main()
