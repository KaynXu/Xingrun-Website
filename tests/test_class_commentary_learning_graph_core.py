import hashlib
import tempfile
import unittest
from pathlib import Path

import lesson_manager
import curriculum_registry
from class_commentary_graph_jobs import (
    process_class_commentary_graph_extraction_job,
    process_class_commentary_graph_sync_operation,
    run_class_commentary_graph_reconciliation,
)
from class_commentary_graph_retrieval import (
    ClassCommentaryStudentGraphRetrievalError,
    retrieve_isolated_student_graph_context,
    validate_isolated_student_graph_context_snapshot,
    validate_used_graph_evidence_refs,
)
from class_commentary_learning_graph import (
    canonical_json,
    content_hash,
    claim_graph_extraction_job,
    claim_graph_sync_operation,
    commit_graph_extraction,
    complete_graph_sync_operation,
    ensure_builtin_knowledge_points,
    fail_graph_sync_operation,
    get_graph_extraction_input,
    get_graph_sync_payload,
    get_student_learning_graph_summary,
    list_dispatchable_graph_sync_operations,
    list_trusted_graph_events,
    normalize_knowledge_point_alias,
    prepare_graph_cleanup_for_scope_conn,
    rebuild_semantica_graph,
    reconcile_class_commentary_graph_store,
    retry_graph_revision,
    resolve_graph_unmapped_candidate,
    resolve_knowledge_point,
)
from class_commentary_semantica import (
    SemanticaGraphAdapter,
    SemanticaGraphError,
    SemanticaGraphScopeError,
    SemanticaGraphUnavailableError,
)
from scripts.canary_class_commentary_semantica import (
    _create_revision_job,
    _insert_scope,
    _schema,
)


class ClassCommentaryLearningGraphCoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.old_db_path = lesson_manager.DB_PATH
        lesson_manager.DB_PATH = self.root / "graph-core.sqlite3"
        with lesson_manager.get_conn() as conn:
            _schema(conn)
            _insert_scope(
                conn,
                organization_id=1,
                teacher_id=11,
                class_id=21,
                task_id=31,
                generation_id=41,
                class_name="Graph Core",
            )
        self.config = {
            "class_commentary_graph_enabled": True,
            "class_commentary_graph_store_path": str(self.root / "graph.json"),
            "class_commentary_graph_timeout": 10,
            "class_commentary_graph_extraction_timeout": 30,
            "class_commentary_graph_sync_timeout": 30,
            "class_commentary_provider": "test-provider",
            "class_commentary_model": "test-model",
        }

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    def _job(
        self,
        *,
        revision_id,
        revision_no,
        feedback_text,
        confirmed_at,
        student_id=101,
        task_id=31,
        generation_id=41,
    ):
        with lesson_manager.get_conn() as conn:
            job_id = _create_revision_job(
                conn,
                revision_id=revision_id,
                organization_id=1,
                task_id=task_id,
                generation_id=generation_id,
                teacher_id=11,
                revision_no=revision_no,
                student_id=student_id,
                feedback_text=feedback_text,
                confirmed_at=confirmed_at,
            )
        return job_id

    @staticmethod
    def _extractor_for(
        *,
        state="weak",
        trend="new_observation",
        knowledge_point_key="math.quadratic_function_graph",
        unmapped_candidate=None,
        method="",
        next_step="",
        causal=False,
        quote_override=None,
        extra_fields=None,
    ):
        def extractor(student_input, _config):
            text = student_input["feedback_text"]
            quote = text if quote_override is None else quote_override
            item = {
                "knowledge_point_key": knowledge_point_key,
                "unmapped_candidate": unmapped_candidate,
                "observed_state": state,
                "reported_trend": trend,
                "evidence_quote": quote,
                "evidence_start_offset": 0,
                "evidence_end_offset": len(quote),
                "evidence_content_hash": hashlib.sha256(quote.encode()).hexdigest(),
                "teaching_methods": [method] if method else [],
                "next_steps": [next_step] if next_step else [],
                "teaching_method_causal_supported": causal,
                "teaching_method_causal_evidence": (
                    [
                        {
                            "method_text": method,
                            "evidence_quote": quote,
                            "evidence_start_offset": 0,
                            "evidence_end_offset": len(quote),
                            "evidence_content_hash": hashlib.sha256(quote.encode()).hexdigest(),
                        }
                    ]
                    if causal and method
                    else []
                ),
            }
            if extra_fields:
                item.update(extra_fields)
            return {"schema_version": "student_learning_event.v1", "items": [item]}

        return extractor

    def _run(self, job_id, extractor):
        return process_class_commentary_graph_extraction_job(
            job_id,
            extractor=extractor,
            dispatcher=lambda **_: {"enabled": True},
            runtime_config=self.config,
        )

    def _sync_all(self, adapter=None):
        adapter = adapter or SemanticaGraphAdapter(self.root / "graph.json")
        for operation in list_dispatchable_graph_sync_operations(limit=100):
            process_class_commentary_graph_sync_operation(
                int(operation["id"]),
                runtime_config=self.config,
                adapter=adapter,
            )
        return adapter

    def _install_multibook_registry(self, grade="九年级"):
        with lesson_manager.get_conn() as conn:
            columns = {
                str(row["name"])
                for row in conn.execute("PRAGMA table_info(classes)")
            }
            if "subject_key" not in columns:
                conn.execute(
                    "ALTER TABLE classes ADD COLUMN subject_key TEXT NOT NULL DEFAULT ''"
                )
            if "current_grade" not in columns:
                conn.execute(
                    "ALTER TABLE classes ADD COLUMN current_grade TEXT NOT NULL DEFAULT ''"
                )
            conn.execute(
                "UPDATE classes SET subject_key='math', current_grade=? WHERE id=21",
                (grade,),
            )
            imported = curriculum_registry.import_curriculum_bundle(
                conn,
                curriculum_registry.load_bundle(),
                actor_user_id=11,
            )
            version_id = int(imported["version"]["id"])
            curriculum_registry.review_curriculum_version(
                conn, version_id, actor_user_id=11
            )
            curriculum_registry.activate_curriculum_version(
                conn, version_id, actor_user_id=11
            )
        return version_id

    def test_registry_normalization_alias_and_subject_isolation(self):
        self.assertEqual(
            normalize_knowledge_point_alias("  QUADRATIC\u3000 FUNCTION   GRAPH "),
            "quadratic function graph",
        )
        with lesson_manager.get_conn() as conn:
            ensure_builtin_knowledge_points(conn, 1)
            math_match = resolve_knowledge_point(
                conn,
                organization_id=1,
                subject_key="math",
                value="  二次函数的图像 ",
            )
            physics_match = resolve_knowledge_point(
                conn,
                organization_id=1,
                subject_key="physics",
                value="二次函数的图像",
            )
        self.assertEqual(math_match["knowledge_point_key"], "math.quadratic_function_graph")
        self.assertIsNone(physics_match)

    def test_legacy_scalar_frozen_curriculum_snapshot_remains_valid(self):
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text="二次函数图像目前较薄弱.",
            confirmed_at="2026-08-11T10:00:00Z",
        )
        frozen = get_graph_extraction_input(job_id)
        self.assertTrue(frozen["integrity_valid"])
        self.assertIsNone(frozen["curriculum_assignment"])
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_graph_extraction_jobs
                SET curriculum_assignment_ids_snapshot_json='[999]',
                    curriculum_book_node_ids_snapshot_json='[999]',
                    curriculum_scope_hash='legacy-column-default-is-not-authoritative'
                WHERE id=?
                """,
                (job_id,),
            )
        self.assertTrue(get_graph_extraction_input(job_id)["integrity_valid"])

    def test_legacy_snapshot_fails_closed_on_generation_scope_tamper(self):
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text="二次函数图像目前较薄弱.",
            confirmed_at="2026-08-11T10:00:00Z",
        )
        self.assertTrue(get_graph_extraction_input(job_id)["integrity_valid"])
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "INSERT INTO classes(id, organization_id, name) VALUES (22, 1, 'Other Class')"
            )
            conn.execute(
                "UPDATE class_commentary_generations SET class_id=22 WHERE id=41"
            )
        self.assertFalse(get_graph_extraction_input(job_id)["integrity_valid"])

    def test_multibook_snapshot_uses_secondary_book_and_fails_closed_on_set_tamper(self):
        self._install_multibook_registry("九年级")
        text = "该知识点目前较薄弱."
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        frozen = get_graph_extraction_input(job_id)
        self.assertTrue(frozen["integrity_valid"])
        assignment = frozen["curriculum_assignment"]
        self.assertEqual(
            assignment["schema_version"], "class_curriculum_assignment.v2"
        )
        self.assertEqual(len(assignment["book_node_ids"]), 2)
        primary_book_id = int(assignment["primary_book_node_id"])
        eligible_keys = {
            str(item["knowledge_point_key"])
            for item in frozen["model_registry"]
        }
        secondary = next(
            item
            for item in frozen["registry"]
            if int(item["book_node_id"]) != primary_book_id
            and len(item["curriculum_book_node_ids"]) == 1
            and str(item["knowledge_point_key"]) in eligible_keys
        )
        result = self._run(
            job_id,
            self._extractor_for(
                knowledge_point_key=str(secondary["knowledge_point_key"])
            ),
        )
        self.assertEqual(result["status"], "extracted")
        with lesson_manager.get_conn() as conn:
            event = conn.execute(
                """
                SELECT curriculum_assignment_id, curriculum_book_node_id
                FROM class_commentary_student_learning_events
                WHERE extraction_job_id=?
                """,
                (job_id,),
            ).fetchone()
        self.assertIsNone(event["curriculum_assignment_id"])
        self.assertEqual(
            int(event["curriculum_book_node_id"]), int(secondary["book_node_id"])
        )

        tamper_job_id = self._job(
            revision_id=52,
            revision_no=2,
            feedback_text=text,
            confirmed_at="2026-08-11T10:05:00Z",
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_graph_extraction_jobs
                SET curriculum_book_node_ids_snapshot_json=?
                WHERE id=?
                """,
                (canonical_json([primary_book_id]), tamper_job_id),
            )
        self.assertFalse(get_graph_extraction_input(tamper_job_id)["integrity_valid"])

    def test_multibook_ambiguous_exact_key_and_unscoped_proposal_fail_closed(self):
        self._install_multibook_registry("一年级")
        text = "比较数量目前较薄弱."
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        frozen = get_graph_extraction_input(job_id)
        ambiguous = [
            item
            for item in frozen["registry"]
            if item["canonical_name"] == "比较数量"
        ]
        self.assertEqual(len(ambiguous), 2)
        self.assertTrue(
            {str(item["knowledge_point_key"]) for item in ambiguous}.isdisjoint(
                {
                    str(item["knowledge_point_key"])
                    for item in frozen["model_registry"]
                }
            )
        )
        result = self._run(
            job_id,
            self._extractor_for(
                knowledge_point_key=str(ambiguous[0]["knowledge_point_key"])
            ),
        )
        self.assertEqual(result["status"], "needs_mapping")
        with self.assertRaisesRegex(
            ValueError, "proposal requires a single frozen curriculum book"
        ):
            resolve_graph_unmapped_candidate(
                result["unmapped_candidate_ids"][0],
                organization_id=1,
                actor_user_id=11,
                request_id="ambiguous-proposal-without-book",
                action="propose_new",
                proposed_name="比较数量自定义观察点",
            )

    def test_unknown_knowledge_point_needs_mapping_and_never_enters_trusted_graph(self):
        text = "新的自定义知识点仍然薄弱."
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        result = self._run(
            job_id,
            self._extractor_for(
                knowledge_point_key=None,
                unmapped_candidate="新的自定义知识点",
            ),
        )
        self.assertEqual(result["status"], "needs_mapping")
        with lesson_manager.get_conn() as conn:
            counts = tuple(
                conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "class_commentary_graph_unmapped_candidates",
                    "class_commentary_student_learning_events",
                    "class_commentary_graph_sync_outbox",
                )
            )
        self.assertEqual(counts, (1, 0, 0))

    def test_server_identity_and_exact_evidence_fail_closed(self):
        text = "二次函数图像目前较薄弱."
        malicious_job = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        with self.assertRaisesRegex(ValueError, "item contract mismatch"):
            self._run(
                malicious_job,
                self._extractor_for(extra_fields={"student_id": 999}),
            )

        mismatch_job = self._job(
            revision_id=52,
            revision_no=2,
            feedback_text=text,
            confirmed_at="2026-08-11T11:00:00Z",
        )
        with self.assertRaisesRegex(ValueError, "does not match confirmed feedback"):
            self._run(
                mismatch_job,
                self._extractor_for(quote_override="伪造的证据"),
            )
        missing_hash_job = self._job(
            revision_id=53,
            revision_no=3,
            feedback_text=text,
            confirmed_at="2026-08-11T12:00:00Z",
        )
        with self.assertRaisesRegex(ValueError, "evidence content hash mismatch"):
            self._run(
                missing_hash_job,
                self._extractor_for(extra_fields={"evidence_content_hash": ""}),
            )
        with lesson_manager.get_conn() as conn:
            event_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_student_learning_events"
            ).fetchone()[0]
            statuses = [
                row["status"]
                for row in conn.execute(
                    "SELECT status FROM class_commentary_graph_extraction_jobs ORDER BY id"
                )
            ]
        self.assertEqual(event_count, 0)
        self.assertEqual(statuses, ["retry_wait", "retry_wait", "retry_wait"])

    def test_temporal_projection_supersession_causality_and_idempotent_sync(self):
        with lesson_manager.get_conn() as conn:
            _insert_scope(
                conn,
                organization_id=1,
                teacher_id=11,
                class_id=22,
                task_id=32,
                generation_id=42,
                class_name="Graph Core Later Lesson",
            )
        first_text = "二次函数图像目前较薄弱, 使用图像与参数联动练习."
        first_job = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=first_text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        self._run(
            first_job,
            self._extractor_for(
                state="weak",
                trend="improved",
                method="图像与参数联动练习",
                causal=True,
            ),
        )
        second_text = "二次函数图像已有改善, 图像与参数联动练习帮助理解. 下一步练习参数变化."
        second_job = self._job(
            revision_id=52,
            revision_no=1,
            feedback_text=second_text,
            confirmed_at="2026-08-11T11:00:00Z",
            task_id=32,
            generation_id=42,
        )
        self._run(
            second_job,
            self._extractor_for(
                state="developing",
                trend="improved",
                method="图像与参数联动练习",
                next_step="下一步练习参数变化",
                causal=True,
            ),
        )

        with lesson_manager.get_conn() as conn:
            events = conn.execute(
                """
                SELECT observed_state, state_before, previous_event_id,
                       improved_from_trusted_state, desired_status
                FROM class_commentary_student_learning_events
                ORDER BY confirmed_at
                """
            ).fetchall()
        self.assertIsNone(events[0]["state_before"])
        self.assertEqual(events[0]["improved_from_trusted_state"], 0)
        self.assertEqual(events[0]["desired_status"], "superseded")
        self.assertEqual(events[1]["state_before"], "weak")
        self.assertTrue(events[1]["previous_event_id"])
        self.assertEqual(events[1]["improved_from_trusted_state"], 1)

        adapter = self._sync_all()
        before = adapter.scoped_snapshot(
            organization_id=1,
            student_id=101,
            subject_key="math",
        )
        edge_types = [edge["type"] for edge in before["edges"]]
        self.assertEqual(edge_types.count("LED_TO"), 1)
        self.assertIn("SUPERSEDES", edge_types)
        self.assertIn("IMPROVED_FROM", edge_types)
        with lesson_manager.get_conn() as conn:
            operation_id = conn.execute(
                "SELECT id FROM class_commentary_graph_sync_outbox ORDER BY id LIMIT 1"
            ).fetchone()[0]
            conn.execute(
                "UPDATE class_commentary_graph_sync_outbox SET status='reconcile_needed' WHERE id=?",
                (operation_id,),
            )
        process_class_commentary_graph_sync_operation(
            operation_id,
            runtime_config=self.config,
            adapter=adapter,
        )
        after = adapter.scoped_snapshot(
            organization_id=1,
            student_id=101,
            subject_key="math",
        )
        self.assertEqual(after["hash"], before["hash"])
        summary = get_student_learning_graph_summary(
            organization_id=1,
            task_id=31,
            student_id=101,
            subject_key="math",
        )
        self.assertEqual(summary["organization_id"], 1)
        self.assertEqual(summary["current_states"][0]["state"], "developing")

    def test_causal_edge_requires_method_specific_supported_sentence(self):
        text = "使用图像法. 老师帮助纠正了书写错误, 但二次函数图像理解仍然薄弱."
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        self._run(
            job_id,
            self._extractor_for(method="图像法", causal=True),
        )
        with lesson_manager.get_conn() as conn:
            causal_supported = conn.execute(
                "SELECT causal_supported FROM class_commentary_learning_teaching_methods"
            ).fetchone()[0]
        self.assertEqual(causal_supported, 0)
        snapshot = self._sync_all().scoped_snapshot(
            organization_id=1,
            student_id=101,
            subject_key="math",
        )
        self.assertNotIn("LED_TO", {str(edge["type"]) for edge in snapshot["edges"]})

    def test_reconciliation_recovers_stale_lease_and_missing_sync(self):
        text = "二次函数图像目前较薄弱."
        stale_job = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        from class_commentary_learning_graph import claim_graph_extraction_job

        claim_graph_extraction_job(stale_job, claim_owner="crashed-worker", lease_seconds=60)
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE class_commentary_graph_extraction_jobs SET lease_until='2000-01-01T00:00:00Z' WHERE id=?",
                (stale_job,),
            )
        recovered = reconcile_class_commentary_graph_store()
        self.assertEqual(recovered["recovered_extraction_jobs"], 1)

        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE class_commentary_graph_extraction_jobs SET status='queued', next_attempt_at=NULL WHERE id=?",
                (stale_job,),
            )
        self._run(stale_job, self._extractor_for())
        with lesson_manager.get_conn() as conn:
            conn.execute("DELETE FROM class_commentary_graph_sync_outbox")
        repaired = reconcile_class_commentary_graph_store()
        self.assertEqual(repaired["created_missing_sync_operations"], 1)
        self.assertEqual(len(repaired["dispatchable_sync_operations"]), 1)

    def test_empty_extraction_preserves_trusted_event_and_pending_unmapped_candidate(self):
        first_text = "二次函数图像目前较薄弱."
        first_job = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=first_text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        self._run(first_job, self._extractor_for())
        second_job = self._job(
            revision_id=52,
            revision_no=2,
            feedback_text="本次修订删除了先前没有依据的知识点判断.",
            confirmed_at="2026-08-11T10:05:00Z",
        )
        self._run(
            second_job,
            lambda *_: {"schema_version": "student_learning_event.v1", "items": []},
        )
        with lesson_manager.get_conn() as conn:
            event = conn.execute(
                "SELECT desired_status, superseded_by_event_id FROM class_commentary_student_learning_events"
            ).fetchone()
            current_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_learning_state_current"
            ).fetchone()[0]
        self.assertEqual(event["desired_status"], "active")
        self.assertIsNone(event["superseded_by_event_id"])
        self.assertEqual(current_count, 1)

        third_text = "出现新的自定义知识点, 但尚未完成内部映射."
        third_job = self._job(
            revision_id=53,
            revision_no=3,
            feedback_text=third_text,
            confirmed_at="2026-08-11T10:10:00Z",
        )
        result = self._run(
            third_job,
            self._extractor_for(
                knowledge_point_key=None,
                unmapped_candidate="新的自定义知识点",
            ),
        )
        self.assertEqual(result["status"], "needs_mapping")
        fourth_job = self._job(
            revision_id=54,
            revision_no=4,
            feedback_text="修订后不保留该候选知识点.",
            confirmed_at="2026-08-11T10:15:00Z",
        )
        self._run(
            fourth_job,
            lambda *_: {"schema_version": "student_learning_event.v1", "items": []},
        )
        with lesson_manager.get_conn() as conn:
            candidate_statuses = [
                str(row["status"])
                for row in conn.execute(
                    "SELECT status FROM class_commentary_graph_unmapped_candidates"
                )
            ]
        self.assertEqual(candidate_statuses, ["pending"])

    def test_causal_gate_rejects_non_student_outcome_and_keeps_direct_learning_outcome(self):
        negative_text = "图像法帮助老师理解了系统设置, 学生仍然薄弱."
        negative_job = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=negative_text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        self._run(
            negative_job,
            self._extractor_for(method="图像法", causal=True),
        )
        positive_text = "图像与参数联动练习帮助理解"
        positive_job = self._job(
            revision_id=52,
            revision_no=2,
            feedback_text=positive_text,
            confirmed_at="2026-08-11T10:05:00Z",
        )
        self._run(
            positive_job,
            self._extractor_for(
                state="developing",
                trend="improved",
                method="图像与参数联动练习",
                causal=True,
            ),
        )
        with lesson_manager.get_conn() as conn:
            causal_flags = [
                int(row["causal_supported"])
                for row in conn.execute(
                    "SELECT causal_supported FROM class_commentary_learning_teaching_methods ORDER BY rowid"
                )
            ]
        self.assertEqual(causal_flags, [0, 1])

    def test_cleanup_tombstone_blocks_claimed_extraction_commit(self):
        text = "二次函数图像目前较薄弱."
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        claimed = claim_graph_extraction_job(job_id, claim_owner="claimed-before-delete")
        self.assertIsNotNone(claimed)
        with lesson_manager.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cleanup = prepare_graph_cleanup_for_scope_conn(
                conn,
                organization_id=1,
                student_id=101,
                actor_user_id=11,
                reason="student_deleted",
            )
        self.assertEqual(cleanup["event_count"], 0)
        frozen = get_graph_extraction_input(job_id)
        payload = self._extractor_for()(
            {"feedback_text": text, "subject_key": "math", "registry": frozen["registry"]},
            self.config,
        )
        candidate = dict(payload["items"][0])
        candidate["student_id"] = 101
        committed = commit_graph_extraction(
            job_id,
            claim_token=str(claimed["claim_token"]),
            candidates_by_student=[candidate],
            extractor_provider="test-provider",
            extractor_model="test-model",
        )
        self.assertEqual(committed["status"], "obsolete")
        with lesson_manager.get_conn() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_student_learning_events"
                ).fetchone()[0],
                0,
            )

    def test_outbox_payload_is_frozen_across_display_name_changes(self):
        text = "二次函数图像目前较薄弱."
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        self._run(job_id, self._extractor_for())
        operation = list_dispatchable_graph_sync_operations(limit=1)[0]
        frozen_before = get_graph_sync_payload(int(operation["id"]))
        with lesson_manager.get_conn() as conn:
            conn.execute("UPDATE classes SET name='Renamed Class' WHERE id=21")
            conn.execute(
                "UPDATE class_commentary_knowledge_points SET canonical_name='Renamed Point'"
            )
        frozen_after = get_graph_sync_payload(int(operation["id"]))
        self.assertTrue(frozen_after["integrity_valid"])
        self.assertEqual(frozen_after["event"], frozen_before["event"])

    def test_cleanup_failure_is_audited_and_missing_store_is_rebuilt(self):
        text = "二次函数图像目前较薄弱."
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        self._run(job_id, self._extractor_for())
        adapter = self._sync_all()
        adapter.store_path.unlink()
        recovered = run_class_commentary_graph_reconciliation(
            runtime_config=self.config,
            adapter=adapter,
            dispatcher=lambda **_: {"queued": True},
            scheduler=lambda **_: {"scheduled": True},
        )
        self.assertEqual(recovered["derived_recovery"]["event_count"], 1)
        self.assertTrue(adapter.health()["healthy"])

        with lesson_manager.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cleanup = prepare_graph_cleanup_for_scope_conn(
                conn,
                organization_id=1,
                student_id=101,
                actor_user_id=11,
                reason="student_deleted",
            )
            operation_id = int(cleanup["operation_ids"][0])
            conn.execute(
                "UPDATE class_commentary_graph_sync_outbox SET attempt_count=7 WHERE id=?",
                (operation_id,),
            )
        claimed = claim_graph_sync_operation(operation_id, claim_owner="failing-cleanup")
        self.assertEqual(int(claimed["attempt_count"]), 8)
        failed = fail_graph_sync_operation(
            operation_id,
            claim_token=str(claimed["claim_token"]),
            error="temporary backend failure",
        )
        self.assertEqual(failed["status"], "failed")
        with lesson_manager.get_conn() as conn:
            cleanup_row = conn.execute(
                "SELECT status, last_error FROM class_commentary_graph_cleanup_requests"
            ).fetchone()
        self.assertEqual(cleanup_row["status"], "failed")
        self.assertIn("temporary backend failure", cleanup_row["last_error"])

    def test_reconciliation_rebuilds_valid_but_empty_and_partial_store(self):
        first_job = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text="二次函数图像目前较薄弱.",
            confirmed_at="2026-08-11T10:00:00Z",
        )
        self._run(first_job, self._extractor_for())
        adapter = self._sync_all()
        expected_first = {
            str(event["event_id"]) for event in list_trusted_graph_events()
        }
        adapter.rebuild([])
        self.assertEqual(adapter.trusted_learning_event_ids(), set())
        empty_recovery = run_class_commentary_graph_reconciliation(
            runtime_config=self.config,
            adapter=adapter,
            dispatcher=lambda **_: {"queued": True},
            scheduler=lambda **_: {"scheduled": True},
        )
        self.assertEqual(empty_recovery["derived_recovery"]["event_count"], 1)
        self.assertEqual(adapter.trusted_learning_event_ids(), expected_first)

        second_job = self._job(
            revision_id=52,
            revision_no=2,
            feedback_text="二次函数图像已有改善, 当前正在发展中.",
            confirmed_at="2026-08-11T10:05:00Z",
        )
        self._run(
            second_job,
            self._extractor_for(state="developing", trend="improved"),
        )
        self._sync_all(adapter)
        canonical_events = list_trusted_graph_events()
        expected_all = {str(event["event_id"]) for event in canonical_events}
        adapter.apply_event({**canonical_events[0], "desired_status": "deleted"})
        self.assertNotEqual(adapter.trusted_learning_event_ids(), expected_all)
        partial_recovery = run_class_commentary_graph_reconciliation(
            runtime_config=self.config,
            adapter=adapter,
            dispatcher=lambda **_: {"queued": True},
            scheduler=lambda **_: {"scheduled": True},
        )
        self.assertEqual(partial_recovery["derived_recovery"]["event_count"], 2)
        self.assertEqual(adapter.trusted_learning_event_ids(), expected_all)

        adapter.apply_event(
            {
                **canonical_events[-1],
                "event_id": "unknown-derived-event",
                "evidence_id": "unknown-derived-evidence",
                "previous_event_id": None,
                "supersedes_event_id": None,
            }
        )
        unknown_recovery = run_class_commentary_graph_reconciliation(
            runtime_config=self.config,
            adapter=adapter,
            dispatcher=lambda **_: {"queued": True},
            scheduler=lambda **_: {"scheduled": True},
        )
        self.assertEqual(unknown_recovery["derived_recovery"]["unknown_event_count"], 1)
        self.assertEqual(adapter.trusted_learning_event_ids(), expected_all)

    def test_reconciliation_rebuilds_unreadable_store_from_sqlite(self):
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text="二次函数图像目前较薄弱.",
            confirmed_at="2026-08-11T10:00:00Z",
        )
        self._run(job_id, self._extractor_for())
        adapter = self._sync_all()
        expected = {str(event["event_id"]) for event in list_trusted_graph_events()}
        adapter.store_path.write_text("{not-json", encoding="utf-8")
        self.assertEqual(adapter.health()["error"], "store_unreadable")
        recovered = run_class_commentary_graph_reconciliation(
            runtime_config=self.config,
            adapter=adapter,
            dispatcher=lambda **_: {"queued": True},
            scheduler=lambda **_: {"scheduled": True},
        )
        self.assertEqual(recovered["derived_recovery"]["event_count"], 1)
        self.assertEqual(adapter.trusted_learning_event_ids(), expected)

    def test_reconciliation_recreates_missing_deleted_cleanup_outbox(self):
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text="二次函数图像目前较薄弱.",
            confirmed_at="2026-08-11T10:00:00Z",
        )
        self._run(job_id, self._extractor_for())
        adapter = self._sync_all()
        with lesson_manager.get_conn() as conn:
            cleanup = prepare_graph_cleanup_for_scope_conn(
                conn,
                organization_id=1,
                student_id=101,
                actor_user_id=11,
                reason="student_deleted",
            )
            conn.execute(
                "DELETE FROM class_commentary_graph_sync_outbox WHERE id=?",
                (int(cleanup["operation_ids"][0]),),
            )
        repaired = reconcile_class_commentary_graph_store()
        self.assertEqual(repaired["created_missing_sync_operations"], 1)
        operation = repaired["dispatchable_sync_operations"][0]
        frozen = get_graph_sync_payload(int(operation["id"]))
        self.assertEqual(frozen["event"]["desired_status"], "deleted")
        process_class_commentary_graph_sync_operation(
            int(operation["id"]),
            runtime_config=self.config,
            adapter=adapter,
        )
        self.assertEqual(
            adapter.scoped_snapshot(
                organization_id=1,
                student_id=101,
                subject_key="math",
            )["nodes"],
            [],
        )

    def test_rebuild_coordinates_with_an_already_claimed_sync(self):
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text="二次函数图像目前较薄弱.",
            confirmed_at="2026-08-11T10:00:00Z",
        )
        self._run(job_id, self._extractor_for())
        operation = list_dispatchable_graph_sync_operations(limit=1)[0]
        claimed = claim_graph_sync_operation(
            int(operation["id"]),
            claim_owner="claimed-before-rebuild",
        )
        adapter = SemanticaGraphAdapter(self.root / "rebuild-barrier.json")
        rebuilt = rebuild_semantica_graph(adapter)
        self.assertEqual(rebuilt["event_count"], 1)
        with lesson_manager.get_conn() as conn:
            status = conn.execute(
                "SELECT status FROM class_commentary_graph_sync_outbox WHERE id=?",
                (int(operation["id"]),),
            ).fetchone()[0]
        self.assertEqual(status, "running")
        frozen = get_graph_sync_payload(int(operation["id"]))
        applied = adapter.apply_event(frozen["event"])
        completed = complete_graph_sync_operation(
            int(operation["id"]),
            claim_token=str(claimed["claim_token"]),
            result_snapshot=applied,
        )
        self.assertEqual(completed["status"], "applied")

    def test_reconciliation_schedules_successor_even_when_cycle_fails(self):
        scheduled = []

        class FailingStore:
            def reconcile_class_commentary_graph_store(self, **_kwargs):
                raise RuntimeError("database temporarily unavailable")

        class HealthyAdapter:
            def health(self):
                return {"healthy": True}

        with self.assertRaisesRegex(RuntimeError, "temporarily unavailable"):
            run_class_commentary_graph_reconciliation(
                store=FailingStore(),
                runtime_config={"class_commentary_graph_enabled": True},
                adapter=HealthyAdapter(),
                dispatcher=lambda **_: {},
                scheduler=lambda **kwargs: scheduled.append(kwargs) or {"scheduled": True},
            )
        self.assertEqual(len(scheduled), 1)

    def test_human_retry_resets_exhausted_extraction_attempts(self):
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text="二次函数图像目前较薄弱.",
            confirmed_at="2026-08-11T10:00:00Z",
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_graph_extraction_jobs
                SET status='failed', attempt_count=4, last_error='exhausted'
                WHERE id=?
                """,
                (job_id,),
            )
        retried = retry_graph_revision(
            51,
            organization_id=1,
            actor_user_id=11,
            request_id="retry-exhausted-51",
        )
        self.assertEqual(retried["status"], "queued")
        self.assertEqual(int(retried["attempt_count"]), 0)
        self.assertIsNotNone(
            claim_graph_extraction_job(job_id, claim_owner="after-human-retry")
        )

    def test_reconciliation_repairs_only_explicit_missing_extraction_intent(self):
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text="二次函数图像目前较薄弱.",
            confirmed_at="2026-08-11T10:00:00Z",
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE class_commentary_revisions SET graph_extraction_requested=1 WHERE id=51"
            )
            conn.execute(
                "DELETE FROM class_commentary_graph_extraction_jobs WHERE id=?",
                (job_id,),
            )
        repaired = reconcile_class_commentary_graph_store()
        self.assertEqual(repaired["created_missing_extraction_jobs"], 1)
        self.assertEqual(len(repaired["dispatchable_extraction_jobs"]), 1)

    def test_out_of_order_extraction_reprojects_and_sync_recovers_missing_predecessor(self):
        with lesson_manager.get_conn() as conn:
            _insert_scope(
                conn,
                organization_id=1,
                teacher_id=11,
                class_id=22,
                task_id=32,
                generation_id=42,
                class_name="Graph Core Later Lesson",
            )
        older_text = "二次函数图像目前较薄弱."
        newer_text = "二次函数图像已有改善, 当前正在发展中."
        older_job = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=older_text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        newer_job = self._job(
            revision_id=52,
            revision_no=1,
            feedback_text=newer_text,
            confirmed_at="2026-08-11T11:00:00Z",
            task_id=32,
            generation_id=42,
        )
        self._run(
            newer_job,
            self._extractor_for(state="developing", trend="improved"),
        )
        adapter = self._sync_all()
        self._run(older_job, self._extractor_for(state="weak"))
        with lesson_manager.get_conn() as conn:
            newer = conn.execute(
                """
                SELECT state_before, previous_event_id, improved_from_trusted_state
                FROM class_commentary_student_learning_events WHERE revision_id=52
                """
            ).fetchone()
            operations = conn.execute(
                "SELECT id, event_id FROM class_commentary_graph_sync_outbox ORDER BY id"
            ).fetchall()
        self.assertEqual(newer["state_before"], "weak")
        self.assertTrue(newer["previous_event_id"])
        self.assertEqual(newer["improved_from_trusted_state"], 1)

        newer_operation_id = int(operations[0]["id"])
        with self.assertRaisesRegex(SemanticaGraphError, "endpoint is missing"):
            process_class_commentary_graph_sync_operation(
                newer_operation_id,
                runtime_config=self.config,
                adapter=adapter,
            )
        older_operation_id = int(operations[1]["id"])
        process_class_commentary_graph_sync_operation(
            older_operation_id,
            runtime_config=self.config,
            adapter=adapter,
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_graph_sync_outbox
                SET status='reconcile_needed', next_attempt_at=NULL
                WHERE id=?
                """,
                (newer_operation_id,),
            )
        process_class_commentary_graph_sync_operation(
            newer_operation_id,
            runtime_config=self.config,
            adapter=adapter,
        )
        snapshot = adapter.scoped_snapshot(
            organization_id=1, student_id=101, subject_key="math"
        )
        self.assertIn("IMPROVED_FROM", [edge["type"] for edge in snapshot["edges"]])

    def test_used_generation_evidence_is_returned_beyond_timeline_limit(self):
        with lesson_manager.get_conn() as conn:
            _insert_scope(
                conn,
                organization_id=1,
                teacher_id=11,
                class_id=22,
                task_id=32,
                generation_id=42,
                class_name="Graph Core Later Lesson",
            )
        first_job = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text="二次函数图像目前较薄弱.",
            confirmed_at="2026-08-11T10:00:00Z",
        )
        second_job = self._job(
            revision_id=52,
            revision_no=1,
            feedback_text="二次函数图像已有改善, 当前正在发展中.",
            confirmed_at="2026-08-11T11:00:00Z",
            task_id=32,
            generation_id=42,
        )
        self._run(first_job, self._extractor_for(state="weak"))
        self._run(
            second_job,
            self._extractor_for(state="developing", trend="improved"),
        )
        with lesson_manager.get_conn() as conn:
            older_evidence_ref = str(
                conn.execute(
                    """
                    SELECT evidence_id FROM class_commentary_learning_evidence
                    WHERE revision_id=51
                    """
                ).fetchone()[0]
            )
            conn.execute(
                """
                INSERT INTO class_commentary_student_generation_runs (
                    id, generation_id, organization_id, student_id,
                    used_graph_evidence_refs_json
                ) VALUES (71, 42, 1, 101, ?)
                """,
                (canonical_json([older_evidence_ref]),),
            )
        summary = get_student_learning_graph_summary(
            organization_id=1,
            task_id=32,
            student_id=101,
            subject_key="math",
            generation_id=42,
            event_limit=1,
        )
        self.assertNotEqual(
            summary["timeline"][0]["evidence"]["evidence_ref"],
            older_evidence_ref,
        )
        self.assertEqual(summary["used_graph_evidence_refs"], [older_evidence_ref])
        self.assertEqual(
            summary["used_graph_evidence"][0]["evidence_ref"],
            older_evidence_ref,
        )

    def test_student_cleanup_is_audited_and_removes_derived_graph(self):
        text = "二次函数图像目前较薄弱."
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text=text,
            confirmed_at="2026-08-11T10:00:00Z",
        )
        self._run(job_id, self._extractor_for())
        adapter = self._sync_all()
        before = adapter.scoped_snapshot(
            organization_id=1, student_id=101, subject_key="math"
        )
        self.assertTrue(before["nodes"])
        with lesson_manager.get_conn() as conn:
            cleanup = prepare_graph_cleanup_for_scope_conn(
                conn,
                organization_id=1,
                student_id=101,
                reason="test_student_delete",
            )
        self.assertEqual(cleanup["event_count"], 1)
        self.assertEqual(len(cleanup["operation_ids"]), 1)
        process_class_commentary_graph_sync_operation(
            cleanup["operation_ids"][0],
            runtime_config=self.config,
            adapter=adapter,
        )
        after = adapter.scoped_snapshot(
            organization_id=1, student_id=101, subject_key="math"
        )
        self.assertEqual(after["nodes"], [])
        self.assertEqual(after["edges"], [])
        with lesson_manager.get_conn() as conn:
            event = conn.execute(
                "SELECT desired_status FROM class_commentary_student_learning_events"
            ).fetchone()
            request = conn.execute(
                "SELECT status, applied_at FROM class_commentary_graph_cleanup_requests"
            ).fetchone()
            current_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_learning_state_current"
            ).fetchone()[0]
        self.assertEqual(event["desired_status"], "deleted")
        self.assertEqual(request["status"], "applied")
        self.assertTrue(request["applied_at"])
        self.assertEqual(current_count, 0)

    def test_organization_cleanup_is_audited_and_removes_derived_graph(self):
        job_id = self._job(
            revision_id=51,
            revision_no=1,
            feedback_text="二次函数图像目前较薄弱.",
            confirmed_at="2026-08-11T10:00:00Z",
        )
        self._run(job_id, self._extractor_for())
        adapter = self._sync_all()
        with lesson_manager.get_conn() as conn:
            cleanup = prepare_graph_cleanup_for_scope_conn(
                conn,
                organization_id=1,
                actor_user_id=11,
                reason="organization_delete",
            )
            conn.execute("UPDATE organizations SET status='inactive' WHERE id=1")
        self.assertEqual(cleanup["event_count"], 1)
        process_class_commentary_graph_sync_operation(
            cleanup["operation_ids"][0],
            runtime_config=self.config,
            adapter=adapter,
        )
        snapshot = adapter.scoped_snapshot(
            organization_id=1,
            student_id=101,
            subject_key="math",
        )
        self.assertEqual(snapshot["nodes"], [])
        with lesson_manager.get_conn() as conn:
            cleanup_row = conn.execute(
                "SELECT status, applied_at FROM class_commentary_graph_cleanup_requests"
            ).fetchone()
        self.assertEqual(cleanup_row["status"], "applied")
        self.assertTrue(cleanup_row["applied_at"])

    def test_semantica_scope_isolates_student_organization_and_subject(self):
        adapter = SemanticaGraphAdapter(self.root / "isolated-graph.json")

        def event(*, event_id, organization_id, student_id, subject_key):
            return {
                "event_id": event_id,
                "organization_id": organization_id,
                "student_id": student_id,
                "subject_key": subject_key,
                "lesson_id": 31,
                "revision_id": 51,
                "revision_no": 1,
                "confirmed_at": "2026-08-11T10:00:00Z",
                "knowledge_point_key": f"{subject_key}.point",
                "knowledge_point_name": f"{subject_key} point",
                "registry_version": 1,
                "observed_state": "weak",
                "reported_trend": "new_observation",
                "evidence_id": f"evidence-{event_id}",
                "evidence_quote": f"evidence for {event_id}",
                "evidence_content_hash": content_hash(f"evidence for {event_id}"),
                "evidence_start_offset": 0,
                "evidence_end_offset": len(f"evidence for {event_id}"),
                "teaching_methods": [],
                "next_steps": [],
                "desired_status": "active",
            }

        student_a_event = event(
            event_id="a", organization_id=1, student_id=101, subject_key="math"
        )
        adapter.apply_event(student_a_event)
        student_a_hash_before_other_scopes = adapter.scoped_snapshot(
            organization_id=1, student_id=101, subject_key="math"
        )["hash"]
        for payload in (
            event(event_id="b", organization_id=1, student_id=202, subject_key="math"),
            event(event_id="c", organization_id=2, student_id=101, subject_key="math"),
            event(event_id="d", organization_id=1, student_id=101, subject_key="physics"),
        ):
            adapter.apply_event(payload)
        snapshot = adapter.scoped_snapshot(
            organization_id=1, student_id=101, subject_key="math"
        )
        self.assertEqual(snapshot["hash"], student_a_hash_before_other_scopes)
        self.assertTrue(snapshot["edges"])
        self.assertTrue(
            all(
                (
                    int(edge["metadata"]["organization_id"]),
                    int(edge["metadata"]["student_id"]),
                    str(edge["metadata"]["subject_key"]),
                )
                == (1, 101, "math")
                for edge in snapshot["edges"]
            )
        )
        contents = {str(node.get("content") or "") for node in snapshot["nodes"]}
        self.assertIn("evidence for a", contents)
        self.assertNotIn("evidence for b", contents)
        self.assertNotIn("evidence for c", contents)
        self.assertNotIn("evidence for d", contents)
        adapter.apply_event({**student_a_event, "desired_status": "deleted"})
        self.assertEqual(
            adapter.scoped_snapshot(
                organization_id=1, student_id=101, subject_key="math"
            )["nodes"],
            [],
        )
        self.assertTrue(
            adapter.scoped_snapshot(
                organization_id=1, student_id=202, subject_key="math"
            )["nodes"]
        )

    def test_retrieval_degrades_only_for_unavailability_and_validates_scope_and_refs(self):
        scope = {"organization_id": 1, "student_id": 101, "subject_key": "math"}
        generation = {"organization_id": 1, "task_id": 31}
        class_context = {"subject_key": "math"}

        class Adapter:
            def scoped_snapshot(self, **query):
                return {**query, "hash": "semantica-hash", "nodes": [], "edges": []}

        summary = {
            **scope,
            "current_states": [],
            "timeline": [
                {
                    "event_ref": "event-1",
                    "knowledge_point_key": "math.quadratic_function_graph",
                    "knowledge_point_name": "二次函数图像",
                    "state": "weak",
                    "previous_state": None,
                    "trend": "new_observation",
                    "observed_at": "2026-08-11T10:00:00Z",
                    "evidence": {
                        "evidence_ref": "evidence-1",
                        "quote": "二次函数图像目前较薄弱.",
                        "lesson_id": 31,
                        "revision_id": 51,
                        "confirmed_at": "2026-08-11T10:00:00Z",
                    },
                    "teaching_methods": [],
                    "next_steps": [],
                }
            ],
        }
        context = retrieve_isolated_student_graph_context(
            generation=generation,
            student_id=101,
            class_context=class_context,
            runtime_config={
                "class_commentary_graph_enabled": True,
                "class_commentary_graph_retrieval_event_limit": 12,
                "class_commentary_graph_retrieval_char_limit": 4000,
            },
            graph_adapter=Adapter(),
            summary_loader=lambda **_: summary,
        )
        self.assertEqual(context["retrieval_status"], "ready")
        self.assertEqual(context["allowed_evidence_refs"], ["evidence-1"])
        validate_isolated_student_graph_context_snapshot(
            generation=generation,
            student_id=101,
            graph_context=context,
            class_context=class_context,
            summary_loader=lambda **_: summary,
        )
        self.assertEqual(
            validate_used_graph_evidence_refs(
                ["evidence-1", "evidence-1"],
                allowed_refs=context["allowed_evidence_refs"],
            ),
            ["evidence-1"],
        )
        with self.assertRaises(ClassCommentaryStudentGraphRetrievalError):
            validate_used_graph_evidence_refs(
                ["other-student-evidence"],
                allowed_refs=context["allowed_evidence_refs"],
            )
        with self.assertRaisesRegex(
            ClassCommentaryStudentGraphRetrievalError, "graph_scope_mismatch"
        ):
            retrieve_isolated_student_graph_context(
                generation=generation,
                student_id=101,
                class_context=class_context,
                runtime_config={"class_commentary_graph_enabled": True},
                graph_adapter=Adapter(),
                summary_loader=lambda **_: {**summary, "organization_id": 2},
            )

        class UnavailableAdapter:
            def scoped_snapshot(self, **_query):
                raise SemanticaGraphUnavailableError("temporarily unavailable")

        degraded = retrieve_isolated_student_graph_context(
            generation=generation,
            student_id=101,
            class_context=class_context,
            runtime_config={"class_commentary_graph_enabled": True},
            graph_adapter=UnavailableAdapter(),
        )
        self.assertEqual(degraded["retrieval_status"], "degraded")
        self.assertEqual(degraded["allowed_evidence_refs"], [])

        class ScopeCorruptionAdapter:
            def scoped_snapshot(self, **_query):
                raise SemanticaGraphScopeError("student graph object has invalid scope")

        with self.assertRaisesRegex(
            ClassCommentaryStudentGraphRetrievalError, "graph_scope_mismatch"
        ):
            retrieve_isolated_student_graph_context(
                generation=generation,
                student_id=101,
                class_context=class_context,
                runtime_config={"class_commentary_graph_enabled": True},
                graph_adapter=ScopeCorruptionAdapter(),
            )

        oversized_summary = {
            **summary,
            "current_states": [
                {
                    "knowledge_point_key": f"math.point.{index}",
                    "knowledge_point_name": "知识点" * 100,
                    "state": "developing",
                    "observed_at": f"2026-08-11T10:{index:02d}:00Z",
                }
                for index in range(20)
            ],
            "timeline": [
                {
                    **summary["timeline"][0],
                    "event_ref": f"event-{index}",
                    "evidence": {
                        **summary["timeline"][0]["evidence"],
                        "evidence_ref": f"evidence-{index}",
                        "quote": "证据" * 1000,
                    },
                    "teaching_methods": ["教学方法" * 100 for _ in range(10)],
                    "next_steps": ["下一步" * 100 for _ in range(10)],
                }
                for index in range(20)
            ],
        }
        bounded = retrieve_isolated_student_graph_context(
            generation=generation,
            student_id=101,
            class_context=class_context,
            runtime_config={
                "class_commentary_graph_enabled": True,
                "class_commentary_graph_retrieval_event_limit": 20,
                "class_commentary_graph_retrieval_char_limit": 10000,
                "class_commentary_graph_retrieval_token_limit": 1200,
            },
            graph_adapter=Adapter(),
            summary_loader=lambda **_: oversized_summary,
        )
        bounded_repeat = retrieve_isolated_student_graph_context(
            generation=generation,
            student_id=101,
            class_context=class_context,
            runtime_config={
                "class_commentary_graph_enabled": True,
                "class_commentary_graph_retrieval_event_limit": 20,
                "class_commentary_graph_retrieval_char_limit": 10000,
                "class_commentary_graph_retrieval_token_limit": 1200,
            },
            graph_adapter=Adapter(),
            summary_loader=lambda **_: oversized_summary,
        )
        self.assertLessEqual(len(canonical_json(bounded).encode("utf-8")), 1200)
        self.assertLess(len(bounded["current_states"]), 20)
        self.assertEqual(bounded_repeat, bounded)
        self.assertLessEqual(len(bounded["current_states"]), 8)
        self.assertLessEqual(len(bounded["recent_changes"]), 20)
        self.assertTrue(
            all(len(item["teaching_methods"]) <= 4 for item in bounded["recent_changes"])
        )
        self.assertTrue(
            all(len(item["next_steps"]) <= 4 for item in bounded["recent_changes"])
        )


if __name__ == "__main__":
    unittest.main()
