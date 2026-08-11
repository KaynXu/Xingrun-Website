import hashlib
import importlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_runtime
import curriculum_registry
import lesson_manager
from class_commentary import CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION
from class_commentary_learning_graph import (
    claim_graph_extraction_job,
    commit_graph_extraction,
    content_hash,
    get_student_learning_graph_summary,
    list_resumable_graph_mapping_actions,
    resolve_graph_unmapped_candidate,
)
from class_commentary_graph_jobs import run_class_commentary_graph_reconciliation


class CurriculumRegistryApiTest(unittest.TestCase):
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
        self.old_cfg = config_runtime.CFG_PATH
        lesson_manager.DB_PATH = self.db_path
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config(
            {
                "class_commentary_memory_enabled": True,
                "class_commentary_structured_feedback_enabled": True,
                "class_commentary_graph_enabled": True,
                "class_commentary_graph_store_path": str(self.base / "graph.json"),
                "colleague_skill_dir": str(self.base / "skills"),
            }
        )
        self.env_patcher = patch.dict(
            os.environ,
            {
                "XR_CLASS_COMMENTARY_MEMORY_ENABLED": "true",
                "XR_CLASS_COMMENTARY_STRUCTURED_FEEDBACK_ENABLED": "true",
                "XR_CLASS_COMMENTARY_GRAPH_ENABLED": "true",
            },
        )
        self.env_patcher.start()
        lesson_manager.init_db()

        self.app_module = importlib.import_module("app")
        self.client = self.app_module.app.test_client()
        self.owner, self.owner_headers = self._login("Kayn", "xingrun2026")
        self.organization_id = int(self.owner["organization_id"])

        self.member_id, self.member_headers = self._create_user(
            username="curriculum-member",
            role="member",
            organization_id=self.organization_id,
        )
        self.admin_id, self.admin_headers = self._create_user(
            username="curriculum-admin",
            role="admin",
            organization_id=self.organization_id,
        )
        with lesson_manager.get_conn() as conn:
            other_org = conn.execute(
                "INSERT INTO organizations (name) VALUES (?)",
                ("Other Curriculum Organization",),
            )
            self.other_organization_id = int(other_org.lastrowid)
        self.other_admin_id, self.other_admin_headers = self._create_user(
            username="other-curriculum-admin",
            role="admin",
            organization_id=self.other_organization_id,
        )

        self.class_id = lesson_manager.save_class(
            "Curriculum API Class",
            subject="数学",
            grade="三年级",
            organization_id=self.organization_id,
            teacher_user_id=self.member_id,
        )
        self.student = lesson_manager.create_student_for_class(
            self.class_id, "Curriculum Student"
        )
        self.other_class_id = lesson_manager.save_class(
            "Other Organization Class",
            subject="数学",
            grade="三年级",
            organization_id=self.other_organization_id,
            teacher_user_id=self.other_admin_id,
        )
        self.skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.organization_id,
            skill_id="curriculum-api-test-skill",
            actor_user_id=self.member_id,
            source_path=str(self.base / "curriculum-api-test.skill"),
            content="Observe one supported learning state and one next step.",
        )

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        config_runtime.CFG_PATH = self.old_cfg
        self.env_patcher.stop()
        self.temp_dir.cleanup()

    def _login(self, username, password):
        response = self.client.post(
            "/api/login", json={"username": username, "password": password}
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        return payload["user"], {"X-Auth-Token": payload["token"]}

    def _create_user(self, *, username, role, organization_id):
        password = "curriculum-pass-123"
        with lesson_manager.get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (
                    username, password_hash, display_name, role, status,
                    organization_id
                ) VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (
                    username,
                    lesson_manager.hash_password(password),
                    username,
                    role,
                    int(organization_id),
                ),
            )
        _, headers = self._login(username, password)
        return int(cursor.lastrowid), headers

    def _activate_registry(self):
        with lesson_manager.get_conn() as conn:
            version = curriculum_registry.get_curriculum_version(
                conn, self.version_id
            )
            if version["status"] == "draft":
                curriculum_registry.review_curriculum_version(
                    conn,
                    self.version_id,
                    actor_user_id=int(self.owner["id"]),
                )
                version = curriculum_registry.get_curriculum_version(
                    conn, self.version_id
                )
            if version["status"] == "reviewed":
                curriculum_registry.activate_curriculum_version(
                    conn,
                    self.version_id,
                    actor_user_id=int(self.owner["id"]),
                )

    def _book_pair_with_private_targets(self):
        with lesson_manager.get_conn() as conn:
            books = curriculum_registry.list_curriculum_books(conn, self.version_id)
            scopes = {}
            for book in books:
                rows = conn.execute(
                    """
                    SELECT node.node_key
                    FROM curriculum_book_nodes membership
                    JOIN curriculum_nodes node ON node.id=membership.node_id
                    WHERE membership.version_id=? AND membership.book_node_id=?
                      AND membership.membership_type='appears_in'
                      AND node.node_type IN ('Concept','Skill')
                    ORDER BY node.node_key
                    """,
                    (self.version_id, int(book["id"])),
                ).fetchall()
                scopes[int(book["id"])] = {str(row["node_key"]) for row in rows}
        for first in books:
            for second in books:
                if first["id"] == second["id"]:
                    continue
                first_only = sorted(scopes[int(first["id"])] - scopes[int(second["id"])])
                second_only = sorted(scopes[int(second["id"])] - scopes[int(first["id"])])
                if first_only and second_only:
                    return first, second, first_only[0], second_only[0]
        self.fail("full curriculum bundle has no independently scoped book pair")

    def _assign_book(self, book_id, *, expected_assignment_id=None, suffix="initial"):
        with lesson_manager.get_conn() as conn:
            return curriculum_registry.assign_curriculum_book(
                conn,
                organization_id=self.organization_id,
                class_id=self.class_id,
                version_id=self.version_id,
                book_node_id=int(book_id),
                actor_user_id=int(self.owner["id"]),
                request_id=f"curriculum-api-assignment-{suffix}",
                expected_assignment_id=expected_assignment_id,
            )

    @staticmethod
    def _canonical_json(value):
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    def _create_unmapped_candidate(self, *, suffix="candidate"):
        feedback_text = "未映射目标表现薄弱, 下一步需要有针对性的练习."
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.organization_id,
            class_id=self.class_id,
            teacher_user_id=self.member_id,
            audio_path="",
            audio_filename="Manual input",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"], f"{self.student['name']} {feedback_text}"
        )
        roster = [
            {
                "student_id": int(self.student["id"]),
                "student_name": str(self.student["name"]),
            }
        ]
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=task["id"],
            generation_request_id=f"curriculum-generation-{suffix}",
            skill_registry_id=int(self.skill["registry_id"]),
            attending_roster=roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-v1",
            prompt_payload={"messages": []},
            memory_context={"records": []},
        )
        generation = lesson_manager.complete_class_commentary_generation(
            generation["id"], f"{self.student['name']}: {feedback_text}"
        )
        structured = {
            "schema_version": "class_commentary.student_feedback.v1",
            "items": [
                {
                    "student_id": int(self.student["id"]),
                    "feedback_text": feedback_text,
                }
            ],
        }
        structured_json = self._canonical_json(structured)
        structured_hash = hashlib.sha256(structured_json.encode("utf-8")).hexdigest()
        scope_hash = lesson_manager.build_class_commentary_eligible_scope_hash(
            transcript_hash=generation["confirmed_transcript_hash"],
            roster_hash=generation["attending_roster_hash"],
            eligible_student_ids=[int(self.student["id"])],
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET feedback_schema_version='class_commentary.student_feedback.v1',
                    structured_feedback_json=?, structured_feedback_hash=?,
                    generated_feedback_text=?, eligible_student_ids_json=?,
                    eligible_student_scope_hash=?,
                    student_mention_matcher_version='class_commentary.student_name_matcher.v1',
                    response_format_json='{"type":"json_object"}',
                    student_history_memory_mode='disabled_v1', prompt_version=?
                WHERE id=?
                """,
                (
                    structured_json,
                    structured_hash,
                    f"{self.student['name']}:\n{feedback_text}",
                    self._canonical_json([int(self.student["id"])]),
                    scope_hash,
                    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
                    int(generation["id"]),
                ),
            )
        revision = lesson_manager.confirm_class_commentary_feedback(
            task_id=int(task["id"]),
            generation_id=int(generation["id"]),
            teacher_user_id=self.member_id,
            learn_requested=True,
            expected_draft_version=0,
            confirmation_request_id=f"curriculum-confirm-{suffix}",
            feedback_schema_version="class_commentary.student_feedback.v1",
            student_feedback_items=structured["items"],
            expected_latest_revision_id=None,
        )
        graph_job = revision["graph_job"]
        self.assertIsNotNone(graph_job)
        claimed = claim_graph_extraction_job(
            int(graph_job["id"]), claim_owner="curriculum-api-test"
        )
        self.assertIsNotNone(claimed)
        quote = "未映射目标"
        start = feedback_text.index(quote)
        result = commit_graph_extraction(
            int(graph_job["id"]),
            claim_token=str(claimed["claim_token"]),
            candidates_by_student=[
                {
                    "student_id": int(self.student["id"]),
                    "knowledge_point_key": None,
                    "unmapped_candidate": quote,
                    "observed_state": "weak",
                    "reported_trend": "new_observation",
                    "evidence_quote": quote,
                    "evidence_start_offset": start,
                    "evidence_end_offset": start + len(quote),
                    "evidence_content_hash": content_hash(quote),
                    "teaching_methods": [],
                    "next_steps": [],
                }
            ],
            extractor_provider="test",
            extractor_model="deterministic-test",
        )
        self.assertEqual(result["status"], "needs_mapping")
        self.assertEqual(len(result["unmapped_candidate_ids"]), 1)
        return {
            "candidate_id": result["unmapped_candidate_ids"][0],
            "job_id": int(graph_job["id"]),
            "revision_id": int(revision["id"]),
            "task_id": int(task["id"]),
        }

    def test_only_super_owner_can_run_registry_lifecycle(self):
        hidden = self.client.get(
            "/api/class-commentary/curriculum/versions",
            headers=self.member_headers,
        )
        self.assertEqual(hidden.status_code, 200)
        self.assertEqual(hidden.get_json()["versions"], [])

        for headers in (self.member_headers, self.admin_headers):
            denied = self.client.post(
                f"/api/class-commentary/curriculum/versions/{self.version_id}/review",
                headers=headers,
            )
            self.assertEqual(denied.status_code, 403)

        reviewed = self.client.post(
            f"/api/class-commentary/curriculum/versions/{self.version_id}/review",
            headers=self.owner_headers,
        )
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.get_json()["version"]["status"], "reviewed")

        activated = self.client.post(
            f"/api/class-commentary/curriculum/versions/{self.version_id}/activate",
            headers=self.owner_headers,
        )
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.get_json()["version"]["status"], "active")

        visible = self.client.get(
            "/api/class-commentary/curriculum/versions",
            headers=self.member_headers,
        )
        self.assertEqual(visible.status_code, 200)
        self.assertEqual(
            [item["id"] for item in visible.get_json()["versions"]],
            [self.version_id],
        )

    def test_member_reads_active_catalog_and_own_assignment_but_cannot_mutate(self):
        self._activate_registry()
        first_book, _, _, _ = self._book_pair_with_private_targets()
        assignment = self._assign_book(first_book["id"])
        candidate = self._create_unmapped_candidate(suffix="member")

        books = self.client.get(
            f"/api/class-commentary/curriculum/books?version_id={self.version_id}",
            headers=self.member_headers,
        )
        self.assertEqual(books.status_code, 200)
        self.assertEqual(len(books.get_json()["books"]), 23)
        catalog = self.client.get(
            (
                "/api/class-commentary/curriculum/catalog"
                f"?version_id={self.version_id}&book_upstream_id={first_book['upstream_id']}"
                "&node_type=Concept&page_size=10"
            ),
            headers=self.member_headers,
        )
        self.assertEqual(catalog.status_code, 200)
        self.assertGreater(catalog.get_json()["total"], 0)
        own_assignment = self.client.get(
            f"/api/class-commentary/curriculum/classes/{self.class_id}/assignment",
            headers=self.member_headers,
        )
        self.assertEqual(own_assignment.status_code, 200)
        self.assertEqual(
            own_assignment.get_json()["assignment"]["id"], assignment["id"]
        )
        inaccessible = self.client.get(
            f"/api/class-commentary/curriculum/classes/{self.other_class_id}/assignment",
            headers=self.member_headers,
        )
        self.assertEqual(inaccessible.status_code, 404)

        denied_assignment = self.client.put(
            f"/api/class-commentary/curriculum/classes/{self.class_id}/assignment",
            headers=self.member_headers,
            json={
                "version_id": self.version_id,
                "book_node_id": int(first_book["id"]),
                "expected_assignment_id": int(assignment["id"]),
                "request_id": "member-cannot-assign",
            },
        )
        self.assertEqual(denied_assignment.status_code, 403)
        for action in ("map", "reject"):
            denied = self.client.post(
                (
                    "/api/class-commentary/curriculum/unmapped/"
                    f"{candidate['candidate_id']}/actions"
                ),
                headers=self.member_headers,
                json={
                    "action": action,
                    "request_id": f"member-cannot-{action}",
                    "target_knowledge_point_key": "not-used",
                },
            )
            self.assertEqual(denied.status_code, 403)

        with patch.object(
            self.app_module,
            "_dispatch_class_commentary_graph_best_effort",
            return_value={"enabled": True},
        ):
            proposed = self.client.post(
                (
                    "/api/class-commentary/curriculum/unmapped/"
                    f"{candidate['candidate_id']}/actions"
                ),
                headers=self.member_headers,
                json={
                    "action": "propose_new",
                    "request_id": "member-proposal",
                    "proposed_name": "机构自定义知识点",
                },
            )
        self.assertEqual(proposed.status_code, 200)
        self.assertEqual(
            proposed.get_json()["result"]["action"]["status"], "pending_review"
        )

    def test_org_admin_cannot_cross_organization_boundaries(self):
        self._activate_registry()
        first_book, _, _, _ = self._book_pair_with_private_targets()
        self._assign_book(first_book["id"])
        candidate = self._create_unmapped_candidate(suffix="cross-org")

        blocked_assignment = self.client.get(
            f"/api/class-commentary/curriculum/classes/{self.class_id}/assignment",
            headers=self.other_admin_headers,
        )
        self.assertEqual(blocked_assignment.status_code, 404)
        blocked_action = self.client.post(
            (
                "/api/class-commentary/curriculum/unmapped/"
                f"{candidate['candidate_id']}/actions"
            ),
            headers=self.other_admin_headers,
            json={
                "action": "reject",
                "request_id": "cross-org-reject",
            },
        )
        self.assertEqual(blocked_action.status_code, 404)

        with patch.object(
            self.app_module,
            "_dispatch_class_commentary_graph_best_effort",
            return_value={"enabled": True},
        ):
            proposed = self.client.post(
                (
                    "/api/class-commentary/curriculum/unmapped/"
                    f"{candidate['candidate_id']}/actions"
                ),
                headers=self.member_headers,
                json={
                    "action": "propose_new",
                    "request_id": "cross-org-proposal-source",
                    "proposed_name": "仅本机构可见知识点",
                },
            )
        self.assertEqual(proposed.status_code, 200)
        with lesson_manager.get_conn() as conn:
            proposal_id = int(
                conn.execute(
                    """
                    SELECT id FROM curriculum_organization_knowledge_points
                    WHERE organization_id=? AND status='proposed'
                    """,
                    (self.organization_id,),
                ).fetchone()["id"]
            )
        cross_org_review = self.client.post(
            f"/api/class-commentary/curriculum/proposals/{proposal_id}/review",
            headers=self.other_admin_headers,
            json={
                "approve": False,
                "request_id": "cross-org-proposal-review",
            },
        )
        self.assertEqual(cross_org_review.status_code, 404)
        other_org_list = self.client.get(
            "/api/class-commentary/curriculum/proposals?status=proposed",
            headers=self.other_admin_headers,
        )
        self.assertEqual(other_org_list.status_code, 200)
        self.assertEqual(other_org_list.get_json()["proposals"], [])

    def test_mapping_uses_frozen_version_and_book_after_assignment_changes(self):
        self._activate_registry()
        old_book, new_book, old_only_key, new_only_key = (
            self._book_pair_with_private_targets()
        )
        old_assignment = self._assign_book(old_book["id"], suffix="old")
        candidate = self._create_unmapped_candidate(suffix="frozen")
        new_assignment = self._assign_book(
            new_book["id"],
            expected_assignment_id=int(old_assignment["id"]),
            suffix="new",
        )

        outside_frozen_scope = self.client.post(
            (
                "/api/class-commentary/curriculum/unmapped/"
                f"{candidate['candidate_id']}/actions"
            ),
            headers=self.admin_headers,
            json={
                "action": "map",
                "request_id": "map-current-book-target",
                "target_knowledge_point_key": new_only_key,
            },
        )
        self.assertEqual(outside_frozen_scope.status_code, 400)
        self.assertIn(
            "outside the assigned curriculum",
            outside_frozen_scope.get_json()["error"],
        )

        with patch.object(
            self.app_module,
            "_dispatch_class_commentary_graph_best_effort",
            return_value={"enabled": True},
        ):
            mapped = self.client.post(
                (
                    "/api/class-commentary/curriculum/unmapped/"
                    f"{candidate['candidate_id']}/actions"
                ),
                headers=self.admin_headers,
                json={
                    "action": "map",
                    "request_id": "map-frozen-book-target",
                    "target_knowledge_point_key": old_only_key,
                },
            )
        self.assertEqual(mapped.status_code, 200)
        result = mapped.get_json()["result"]
        self.assertEqual(result["candidate"]["status"], "mapped")
        self.assertEqual(
            result["candidate"]["resolved_knowledge_point_key"], old_only_key
        )
        with lesson_manager.get_conn() as conn:
            action_payload = json.loads(
                conn.execute(
                    """
                    SELECT payload_json FROM curriculum_mapping_actions
                    WHERE organization_id=? AND request_id=?
                    """,
                    (self.organization_id, "map-frozen-book-target"),
                ).fetchone()["payload_json"]
            )
            event = conn.execute(
                """
                SELECT curriculum_version_id, curriculum_book_node_id,
                       knowledge_point_key
                FROM class_commentary_student_learning_events
                WHERE extraction_job_id=?
                """,
                (candidate["job_id"],),
            ).fetchone()
            current_assignment = curriculum_registry.get_class_curriculum_assignment(
                conn, self.class_id
            )
        self.assertEqual(
            action_payload["curriculum_assignment_id"], int(old_assignment["id"])
        )
        self.assertEqual(
            action_payload["curriculum_book_node_id"], int(old_book["id"])
        )
        self.assertEqual(int(event["curriculum_version_id"]), self.version_id)
        self.assertEqual(int(event["curriculum_book_node_id"]), int(old_book["id"]))
        self.assertEqual(event["knowledge_point_key"], old_only_key)
        self.assertEqual(int(current_assignment["id"]), int(new_assignment["id"]))

    def test_approved_custom_point_replays_to_trusted_event_with_provenance(self):
        self._activate_registry()
        with lesson_manager.get_conn() as conn:
            book = curriculum_registry.list_curriculum_books(conn, self.version_id)[0]
        self._assign_book(book["id"], suffix="custom-proposal")
        candidate = self._create_unmapped_candidate(suffix="custom-proposal")

        proposed = self.client.post(
            f"/api/class-commentary/curriculum/unmapped/{candidate['candidate_id']}/actions",
            headers=self.member_headers,
            json={
                "action": "propose_new",
                "request_id": "custom-proposal-create",
                "proposed_name": "三年级自定义观察点",
            },
        )
        self.assertEqual(proposed.status_code, 200)
        proposals = self.client.get(
            "/api/class-commentary/curriculum/proposals?status=proposed",
            headers=self.admin_headers,
        )
        self.assertEqual(proposals.status_code, 200)
        proposal = proposals.get_json()["proposals"][0]

        with patch.object(
            self.app_module,
            "_dispatch_class_commentary_graph_best_effort",
            return_value={"enabled": True},
        ):
            reviewed = self.client.post(
                f"/api/class-commentary/curriculum/proposals/{proposal['id']}/review",
                headers=self.admin_headers,
                json={
                    "approve": True,
                    "request_id": "custom-proposal-approve",
                },
            )
        self.assertEqual(reviewed.status_code, 200)
        payload = reviewed.get_json()
        self.assertEqual(payload["failures"], [])
        self.assertEqual(len(payload["reprocessed"]), 1)
        self.assertEqual(payload["reprocessed"][0]["candidate"]["status"], "mapped")

        with lesson_manager.get_conn() as conn:
            event = conn.execute(
                """
                SELECT * FROM class_commentary_student_learning_events
                WHERE extraction_job_id=?
                """,
                (candidate["job_id"],),
            ).fetchone()
            current_count = conn.execute(
                """
                SELECT COUNT(*) FROM class_commentary_learning_state_current
                WHERE event_id=?
                """,
                (event["event_id"],),
            ).fetchone()[0]
            outbox_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_graph_sync_outbox WHERE event_id=?",
                (event["event_id"],),
            ).fetchone()[0]
        self.assertIsNone(event["curriculum_node_id"])
        self.assertEqual(
            int(event["organization_knowledge_point_id"]), int(proposal["id"])
        )
        self.assertEqual((current_count, outbox_count), (1, 1))
        summary = get_student_learning_graph_summary(
            organization_id=self.organization_id,
            task_id=candidate["task_id"],
            student_id=int(self.student["id"]),
            subject_key="math",
        )
        custom_context = summary["timeline"][0]["curriculum"]
        self.assertEqual(
            custom_context["organization_knowledge_point_id"], int(proposal["id"])
        )
        self.assertEqual(
            custom_context["path"][-1]["node_type"], "OrganizationKnowledgePoint"
        )

    def test_mapping_crash_after_event_commit_is_resumed_by_reconciliation(self):
        self._activate_registry()
        with lesson_manager.get_conn() as conn:
            book = curriculum_registry.list_curriculum_books(conn, self.version_id)[0]
        self._assign_book(book["id"], suffix="crash-recovery")
        candidate = self._create_unmapped_candidate(suffix="crash-recovery")
        with lesson_manager.get_conn() as conn:
            frozen = json.loads(
                conn.execute(
                    "SELECT curriculum_registry_snapshot_json FROM class_commentary_graph_extraction_jobs WHERE id=?",
                    (candidate["job_id"],),
                ).fetchone()[0]
            )
        target_key = str(frozen[0]["knowledge_point_key"])

        import class_commentary_learning_graph as graph_store

        original_commit = graph_store.commit_graph_extraction

        def commit_then_crash(*args, **kwargs):
            original_commit(*args, **kwargs)
            raise SystemExit("simulated process death after event commit")

        with patch.object(
            graph_store, "commit_graph_extraction", side_effect=commit_then_crash
        ):
            with self.assertRaises(SystemExit):
                resolve_graph_unmapped_candidate(
                    candidate["candidate_id"],
                    organization_id=self.organization_id,
                    actor_user_id=self.admin_id,
                    request_id="mapping-crash-window",
                    action="map",
                    target_knowledge_point_key=target_key,
                )
        with lesson_manager.get_conn() as conn:
            before = conn.execute(
                "SELECT status FROM class_commentary_graph_unmapped_candidates WHERE candidate_id=?",
                (candidate["candidate_id"],),
            ).fetchone()[0]
            event_count_before = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_student_learning_events WHERE extraction_job_id=?",
                (candidate["job_id"],),
            ).fetchone()[0]
        self.assertEqual(before, "pending")
        self.assertEqual(event_count_before, 1)
        self.assertEqual(len(list_resumable_graph_mapping_actions()), 1)

        class HealthyHashAdapter:
            def health(self):
                return {"healthy": True}

            def trusted_learning_event_ids(self):
                with lesson_manager.get_conn() as conn:
                    return {
                        str(row[0])
                        for row in conn.execute(
                            "SELECT event_id FROM class_commentary_student_learning_events"
                        )
                    }

            def store_hash(self):
                return "same"

            def expected_store_hash(self, _events, **_kwargs):
                return "same"

        reconciled = run_class_commentary_graph_reconciliation(
            runtime_config={
                "class_commentary_graph_enabled": True,
                "class_commentary_graph_reconcile_limit": 100,
            },
            adapter=HealthyHashAdapter(),
            dispatcher=lambda **_: {"dispatched": True},
            scheduler=lambda **_: {"scheduled": True},
        )
        self.assertEqual(reconciled["reconciliation"]["resumed_mapping_count"], 1)
        with lesson_manager.get_conn() as conn:
            after = conn.execute(
                "SELECT status FROM class_commentary_graph_unmapped_candidates WHERE candidate_id=?",
                (candidate["candidate_id"],),
            ).fetchone()[0]
            event_count_after = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_student_learning_events WHERE extraction_job_id=?",
                (candidate["job_id"],),
            ).fetchone()[0]
        self.assertEqual(after, "mapped")
        self.assertEqual(event_count_after, 1)

    def test_obsolete_mapping_never_marks_candidate_as_mapped(self):
        self._activate_registry()
        with lesson_manager.get_conn() as conn:
            book = curriculum_registry.list_curriculum_books(conn, self.version_id)[0]
        self._assign_book(book["id"], suffix="obsolete")
        candidate = self._create_unmapped_candidate(suffix="obsolete")
        with lesson_manager.get_conn() as conn:
            target_key = json.loads(
                conn.execute(
                    "SELECT curriculum_registry_snapshot_json FROM class_commentary_graph_extraction_jobs WHERE id=?",
                    (candidate["job_id"],),
                ).fetchone()[0]
            )[0]["knowledge_point_key"]
            conn.execute(
                "UPDATE students SET status='deleted' WHERE id=? AND organization_id=?",
                (int(self.student["id"]), self.organization_id),
            )
        with self.assertRaisesRegex(
            ValueError, "did not create a trusted learning event"
        ):
            resolve_graph_unmapped_candidate(
                candidate["candidate_id"],
                organization_id=self.organization_id,
                actor_user_id=self.admin_id,
                request_id="obsolete-mapping",
                action="map",
                target_knowledge_point_key=str(target_key),
            )
        with lesson_manager.get_conn() as conn:
            candidate_status = conn.execute(
                "SELECT status FROM class_commentary_graph_unmapped_candidates WHERE candidate_id=?",
                (candidate["candidate_id"],),
            ).fetchone()[0]
            action_status = conn.execute(
                "SELECT status FROM curriculum_mapping_actions WHERE request_id='obsolete-mapping'"
            ).fetchone()[0]
        self.assertEqual(candidate_status, "pending")
        self.assertEqual(action_status, "failed")


if __name__ == "__main__":
    unittest.main()
