import datetime
import os
import tempfile
import unittest

import lesson_manager


class ClassCommentaryMemoryStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        self.old_enabled = os.environ.get("XR_CLASS_COMMENTARY_MEMORY_ENABLED")
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        os.environ["XR_CLASS_COMMENTARY_MEMORY_ENABLED"] = "true"
        lesson_manager.init_db()
        self.teacher = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class(
            "记忆事实层测试班",
            subject="数学",
            grade="七年级",
            organization_id=self.teacher["organization_id"],
            teacher_user_id=self.teacher["id"],
        )
        self.student = lesson_manager.create_student_for_class(self.class_id, "小王")
        self.roster = [
            {"student_id": self.student["id"], "student_name": self.student["name"]}
        ]
        self.skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.teacher["organization_id"],
            skill_id="memory-store-teacher",
            owner_teacher_user_id=self.teacher["id"],
            source_path="/skills/memory-store-teacher/SKILL.md",
            content="先写课堂表现, 再给一条具体建议.",
        )
        self.task, self.generation = self._create_task_and_generation("first")

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        if self.old_enabled is None:
            os.environ.pop("XR_CLASS_COMMENTARY_MEMORY_ENABLED", None)
        else:
            os.environ["XR_CLASS_COMMENTARY_MEMORY_ENABLED"] = self.old_enabled
        self.tmp.cleanup()

    def _create_task_and_generation(self, suffix, *, class_id=None):
        target_class_id = int(class_id or self.class_id)
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=target_class_id,
            teacher_user_id=self.teacher["id"],
            audio_path=f"/tmp/memory-store-{suffix}.m4a",
            audio_filename=f"memory-store-{suffix}.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            "小王这次计算更稳, 但仍要坚持验算.",
        )
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=task["id"],
            generation_request_id=f"memory-generation-{suffix}",
            skill_registry_id=self.skill["registry_id"],
            attending_roster=self.roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-v1",
            prompt_payload={"messages": [{"role": "user", "content": "生成反馈"}]},
            memory_context={"records": [], "rendered_text": ""},
        )
        lesson_manager.complete_class_commentary_generation(
            generation["id"],
            "小王: 计算更稳, 请继续验算.",
        )
        return task, generation

    def _confirm(self, request_id, *, learn=True, expected_draft_version=0, text=None):
        return lesson_manager.confirm_class_commentary_feedback(
            task_id=self.task["id"],
            generation_id=self.generation["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text=text or "小王: 计算更稳, 每道题完成后主动验算.",
            learn_requested=learn,
            expected_draft_version=expected_draft_version,
            confirmation_request_id=request_id,
        )

    def _extract(self, revision, items):
        job = lesson_manager.get_class_commentary_memory_extraction_job_for_revision(
            revision["id"]
        )
        claimed = lesson_manager.claim_class_commentary_memory_extraction_job(
            job["id"], claim_owner="test-worker", rq_job_id=f"rq-{job['id']}"
        )
        self.assertIsNotNone(claimed)
        return lesson_manager.commit_class_commentary_memory_extraction(
            job["id"], claim_token=claimed["claim_token"], items=items
        )

    def test_schema_creates_six_memory_fact_tables_and_constraints(self):
        expected = {
            "class_commentary_memory_records",
            "class_commentary_memory_evidence",
            "class_commentary_memory_evidence_events",
            "class_commentary_memory_extraction_jobs",
            "class_commentary_memory_retry_events",
            "class_commentary_memory_operations",
        }
        with lesson_manager.get_conn() as conn:
            actual = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            index = conn.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE type='index' AND name='uq_class_commentary_active_memory_item'
                """
            ).fetchone()
            organization_fk = conn.execute(
                "PRAGMA foreign_key_list(class_commentary_memory_records)"
            ).fetchall()
            operation_columns = {
                row["name"]
                for row in conn.execute(
                    "PRAGMA table_info(class_commentary_memory_operations)"
                ).fetchall()
            }
            cleanup_scope_index = conn.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type='index'
                  AND name='idx_class_commentary_memory_cleanup_scope'
                """
            ).fetchone()
        self.assertTrue(expected.issubset(actual))
        self.assertIn("WHERE desired_status='active'", index["sql"])
        org_rel = next(row for row in organization_fk if row["from"] == "organization_id")
        self.assertEqual(org_rel["on_delete"], "NO ACTION")
        self.assertTrue({"cleanup_scope_type", "cleanup_scope_id"}.issubset(operation_columns))
        self.assertIsNotNone(cleanup_scope_index)

    def test_confirmation_claim_commit_and_operation_apply_are_item_scoped(self):
        revision = self._confirm("memory-confirm-first")
        job = revision["memory_job"]
        self.assertEqual(job["status"], "queued")
        frozen = lesson_manager.get_class_commentary_memory_extraction_input(job["id"])
        self.assertTrue(frozen["integrity_valid"])
        self.assertTrue(frozen["is_effective_revision"])
        self.assertEqual(frozen["attending_roster"], self.roster)

        result = self._extract(
            revision,
            [
                {
                    "memory_type": "teacher_style",
                    "memory_text": "结尾给出一条可执行的练习建议",
                    "confidence": 0.9,
                },
                {
                    "memory_type": "student_fact",
                    "student_id": self.student["id"],
                    "memory_text": "验算习惯仍需持续巩固",
                    "confidence": 0.8,
                },
            ],
        )
        self.assertEqual(result["job"]["status"], "extracted")
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(len(result["evidence"]), 2)
        self.assertEqual(len(result["operations"]), 2)

        style_records = lesson_manager.list_class_commentary_memory_records_for_scope(
            organization_id=self.teacher["organization_id"],
            memory_type="teacher_style",
            skill_registry_id=self.skill["registry_id"],
        )
        student_records = lesson_manager.list_class_commentary_memory_records_for_scope(
            organization_id=self.teacher["organization_id"],
            memory_type="student_fact",
            student_ids=[self.student["id"]],
            subject_key="math",
        )
        self.assertEqual(len(style_records), 1)
        self.assertEqual(len(student_records), 1)
        self.assertEqual(style_records[0]["active_evidence_count"], 1)

        operation = result["operations"][0]
        claimed_operation = lesson_manager.claim_class_commentary_memory_operation(
            operation["id"],
            lease_owner="operation-worker",
            rq_job_id="operation-rq",
        )
        self.assertEqual(claimed_operation["status"], "running")
        self.assertEqual(claimed_operation["projection_metadata"]["evidence_count"], 1)
        self.assertEqual(
            claimed_operation["projection_metadata"]["operation_key"],
            claimed_operation["operation_key"],
        )
        self.assertEqual(claimed_operation["projection_metadata"]["status"], "active")
        applied = lesson_manager.complete_class_commentary_memory_operation(
            operation["id"],
            lease_token=claimed_operation["lease_token"],
            mem0_memory_id="mem0-1",
        )
        self.assertEqual(applied["status"], "applied")
        record = lesson_manager.get_class_commentary_memory_records_by_ids(
            [operation["memory_record_id"]]
        )[0]
        self.assertEqual(record["applied_status"], "active")
        self.assertEqual(record["mem0_memory_id"], "mem0-1")

    def test_reconciliation_marker_cannot_mutate_a_foreign_organization_record(self):
        revision = self._confirm("memory-confirm-reconcile-scope")
        result = self._extract(
            revision,
            [
                {
                    "memory_type": "teacher_style",
                    "memory_text": "结尾给出一条可执行建议",
                    "confidence": 0.9,
                }
            ],
        )
        operation = result["operations"][0]

        marked = lesson_manager.mark_class_commentary_memory_records_reconcile_needed(
            [operation["memory_record_id"]],
            "untrusted_mem0_metadata",
            organization_id=self.teacher["organization_id"] + 999,
        )

        self.assertEqual(marked, [])
        with lesson_manager.get_conn() as conn:
            unchanged = conn.execute(
                "SELECT status, last_error FROM class_commentary_memory_operations WHERE id=?",
                (operation["id"],),
            ).fetchone()
        self.assertEqual(unchanged["status"], "pending")
        self.assertIsNone(unchanged["last_error"])

    def test_stale_running_add_is_serialized_and_reconciled_to_latest_projection(self):
        revision = self._confirm("memory-confirm-operation-race")
        result = self._extract(
            revision,
            [
                {
                    "memory_type": "teacher_style",
                    "memory_text": "结尾给出一条可执行建议",
                    "confidence": 0.9,
                }
            ],
        )
        stale_operation = result["operations"][0]
        claimed_stale = lesson_manager.claim_class_commentary_memory_operation(
            stale_operation["id"],
            lease_owner="delayed-operation-worker",
        )
        self.assertEqual(claimed_stale["status"], "running")

        revoked = lesson_manager.revoke_class_commentary_memory_evidence(
            result["evidence"][0]["id"],
            actor_user_id=self.teacher["id"],
            request_id="revoke-while-add-running",
        )
        latest_operation = revoked["operation"]
        self.assertEqual(
            lesson_manager.get_class_commentary_memory_operation(stale_operation["id"])[
                "status"
            ],
            "running",
        )
        self.assertNotIn(
            latest_operation["id"],
            [
                operation["id"]
                for operation in lesson_manager.list_dispatchable_class_commentary_memory_operations()
            ],
        )
        self.assertIsNone(
            lesson_manager.claim_class_commentary_memory_operation(
                latest_operation["id"],
                lease_owner="latest-operation-worker",
            )
        )

        completed_stale = lesson_manager.complete_class_commentary_memory_operation(
            stale_operation["id"],
            lease_token=claimed_stale["lease_token"],
            mem0_memory_id="mem0-race",
            applied_status="active",
        )
        self.assertEqual(completed_stale["status"], "obsolete")
        self.assertEqual(completed_stale["mem0_memory_id"], "mem0-race")
        self.assertIsNotNone(completed_stale["applied_at"])
        self.assertIsNone(completed_stale["lease_token"])

        record = lesson_manager.get_class_commentary_memory_records_by_ids(
            [stale_operation["memory_record_id"]]
        )[0]
        self.assertEqual(record["desired_status"], "revoked")
        self.assertEqual(record["applied_status"], "unknown")
        self.assertEqual(record["mem0_memory_id"], "mem0-race")
        reconciled_operation = lesson_manager.get_class_commentary_memory_operation(
            latest_operation["id"]
        )
        self.assertEqual(reconciled_operation["status"], "reconcile_needed")
        self.assertEqual(reconciled_operation["mem0_memory_id"], "mem0-race")
        self.assertIn(
            latest_operation["id"],
            [
                operation["id"]
                for operation in lesson_manager.list_dispatchable_class_commentary_memory_operations()
            ],
        )

        claimed_latest = lesson_manager.claim_class_commentary_memory_operation(
            latest_operation["id"],
            lease_owner="latest-operation-worker",
        )
        self.assertEqual(claimed_latest["status"], "running")
        completed_latest = lesson_manager.complete_class_commentary_memory_operation(
            latest_operation["id"],
            lease_token=claimed_latest["lease_token"],
            mem0_memory_id="mem0-race",
            applied_status="revoked",
        )
        self.assertEqual(completed_latest["status"], "applied")
        final_record = lesson_manager.get_class_commentary_memory_records_by_ids(
            [stale_operation["memory_record_id"]]
        )[0]
        self.assertEqual(final_record["desired_status"], "revoked")
        self.assertEqual(final_record["applied_status"], "revoked")

    def test_rev2_confirmation_obsoletes_claimed_rev1_and_commit_gate_writes_nothing(self):
        revision1 = self._confirm("memory-confirm-r1")
        job1 = revision1["memory_job"]
        claimed1 = lesson_manager.claim_class_commentary_memory_extraction_job(
            job1["id"], claim_owner="delayed-worker"
        )

        revision2 = self._confirm(
            "memory-confirm-r2",
            expected_draft_version=1,
            text="小王: 计算进步明显, 下一步独立复核关键步骤.",
        )
        self.assertEqual(revision2["memory_job"]["status"], "queued")
        stale = lesson_manager.commit_class_commentary_memory_extraction(
            job1["id"],
            claim_token=claimed1["claim_token"],
            items=[
                {
                    "memory_type": "teacher_style",
                    "memory_text": "这条延迟结果不得写入",
                }
            ],
        )
        self.assertEqual(stale["job"]["status"], "obsolete")
        with lesson_manager.get_conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS value FROM class_commentary_memory_evidence"
            ).fetchone()["value"]
        self.assertEqual(count, 0)
        with self.assertRaises(lesson_manager.ClassCommentaryMemoryRevisionNotRetryable):
            lesson_manager.retry_class_commentary_memory_revision(
                revision1["id"],
                actor_user_id=self.teacher["id"],
                request_id="retry-obsolete-r1",
            )

    def test_rev2_without_learning_supersedes_rev1_evidence_and_creates_cleanup_operation(self):
        revision1 = self._confirm("memory-confirm-extracted-r1")
        extracted = self._extract(
            revision1,
            [
                {
                    "memory_type": "teacher_style",
                    "memory_text": "建议必须具体到下一步动作",
                }
            ],
        )
        record_id = extracted["records"][0]["id"]
        revision2 = self._confirm(
            "memory-confirm-no-learn-r2",
            learn=False,
            expected_draft_version=1,
            text="小王: 计算已经稳定.",
        )
        self.assertIsNone(revision2["memory_job"])
        record = lesson_manager.get_class_commentary_memory_records_by_ids([record_id])[0]
        self.assertEqual(record["desired_status"], "superseded")
        self.assertEqual(record["record_version"], 2)
        memories = lesson_manager.list_class_commentary_revision_memories(
            revision1["id"], actor_user_id=self.teacher["id"]
        )
        self.assertEqual(memories["memories"][0]["status"], "superseded")
        operation = lesson_manager.get_class_commentary_memory_operation(
            memories["memories"][0]["latest_operation_id"]
        )
        self.assertEqual(operation["operation_type"], "supersede")
        self.assertEqual(operation["expected_record_version"], 2)

    def test_failed_job_explicit_retry_is_idempotent_and_uses_same_frozen_job(self):
        revision = self._confirm("memory-confirm-retry")
        job = revision["memory_job"]
        for attempt in range(4):
            claimed = lesson_manager.claim_class_commentary_memory_extraction_job(
                job["id"],
                claim_owner=f"worker-{attempt}",
                now=f"2026-07-14T00:0{attempt}:00.000000Z",
            )
            self.assertIsNotNone(claimed)
            failed = lesson_manager.fail_class_commentary_memory_extraction_job(
                job["id"],
                claim_token=claimed["claim_token"],
                error="extractor unavailable",
                now=datetime.datetime(2026, 7, 14, 0, attempt, 0),
            )
            if attempt < 3:
                with lesson_manager.get_conn() as conn:
                    conn.execute(
                        """
                        UPDATE class_commentary_memory_extraction_jobs
                        SET next_attempt_at='2026-07-14T00:00:00.000000Z'
                        WHERE id=?
                        """,
                        (job["id"],),
                    )
        self.assertEqual(failed["status"], "failed")
        event = lesson_manager.retry_class_commentary_memory_revision(
            revision["id"],
            actor_user_id=self.teacher["id"],
            request_id="retry-latest-revision",
        )
        replay = lesson_manager.retry_class_commentary_memory_revision(
            revision["id"],
            actor_user_id=self.teacher["id"],
            request_id="retry-latest-revision",
        )
        self.assertEqual(event, replay)
        reset = lesson_manager.get_class_commentary_memory_extraction_job(job["id"])
        self.assertEqual(reset["status"], "queued")
        self.assertEqual(reset["attempt_count"], 0)
        self.assertEqual(reset["extraction_input_hash"], job["extraction_input_hash"])

    def test_cleanup_marks_active_record_deleted_and_requires_applied_delete(self):
        revision = self._confirm("memory-confirm-cleanup")
        result = self._extract(
            revision,
            [
                {
                    "memory_type": "student_fact",
                    "student_id": self.student["id"],
                    "memory_text": "验算仍需提醒",
                }
            ],
        )
        cleanup = lesson_manager.prepare_class_commentary_memory_cleanup_for_scope(
            organization_id=self.teacher["organization_id"],
            task_id=self.task["id"],
        )
        self.assertEqual(cleanup["record_ids"], [result["records"][0]["id"]])
        self.assertEqual(cleanup["evidence_ids"], [result["evidence"][0]["id"]])
        self.assertEqual(cleanup["scope_type"], "task")
        self.assertEqual(cleanup["scope_id"], self.task["id"])
        self.assertTrue(
            lesson_manager.has_pending_class_commentary_memory_cleanup(
                organization_id=self.teacher["organization_id"],
                task_id=self.task["id"],
            )
        )
        record = lesson_manager.get_class_commentary_memory_records_by_ids(
            cleanup["record_ids"]
        )[0]
        operation = lesson_manager.get_class_commentary_memory_operation(
            cleanup["operation_ids"][0]
        )
        self.assertEqual(record["desired_status"], "deleted")
        self.assertEqual(operation["operation_type"], "delete")
        self.assertEqual(operation["expected_record_version"], 2)
        self.assertEqual(operation["cleanup_scope_type"], "task")
        self.assertEqual(operation["cleanup_scope_id"], self.task["id"])
        self.assertEqual(operation["projection_metadata"]["evidence_count"], 0)
        with lesson_manager.get_conn() as conn:
            evidence_status = conn.execute(
                "SELECT status FROM class_commentary_memory_evidence WHERE id=?",
                (result["evidence"][0]["id"],),
            ).fetchone()["status"]
        self.assertEqual(evidence_status, "revoked")

        replay = lesson_manager.prepare_class_commentary_memory_cleanup_for_scope(
            organization_id=self.teacher["organization_id"],
            task_id=self.task["id"],
        )
        self.assertEqual(replay["record_ids"], [])
        self.assertEqual(replay["evidence_ids"], [])
        self.assertEqual(replay["operation_ids"], [])
        replay_record = lesson_manager.get_class_commentary_memory_records_by_ids(
            cleanup["record_ids"]
        )[0]
        self.assertEqual(replay_record["record_version"], 2)

    def test_task_cleanup_preserves_shared_record_until_last_active_evidence(self):
        memory_text = "建议必须具体到下一步动作"
        revision1 = self._confirm("memory-cleanup-shared-first")
        result1 = self._extract(
            revision1,
            [{"memory_type": "teacher_style", "memory_text": memory_text}],
        )
        task2, generation2 = self._create_task_and_generation("cleanup-shared-second")
        revision2 = lesson_manager.confirm_class_commentary_feedback(
            task_id=task2["id"],
            generation_id=generation2["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text="小王: 继续把下一步动作写清楚.",
            learn_requested=True,
            expected_draft_version=0,
            confirmation_request_id="memory-cleanup-shared-second",
        )
        result2 = self._extract(
            revision2,
            [{"memory_type": "teacher_style", "memory_text": memory_text}],
        )
        record_id = result1["records"][0]["id"]
        self.assertEqual(result2["records"][0]["id"], record_id)

        first_cleanup = lesson_manager.prepare_class_commentary_memory_cleanup_for_scope(
            organization_id=self.teacher["organization_id"],
            task_id=self.task["id"],
        )
        first_record = lesson_manager.get_class_commentary_memory_records_by_ids(
            [record_id]
        )[0]
        first_operation = lesson_manager.get_class_commentary_memory_operation(
            first_cleanup["operation_ids"][0]
        )
        self.assertEqual(first_cleanup["evidence_ids"], [result1["evidence"][0]["id"]])
        self.assertEqual(first_record["desired_status"], "active")
        self.assertEqual(first_record["record_version"], 3)
        self.assertEqual(first_record["active_evidence_count"], 1)
        self.assertEqual(first_operation["operation_type"], "update")
        self.assertEqual(first_operation["projection_metadata"]["evidence_count"], 1)
        self.assertEqual(first_operation["cleanup_scope_type"], "task")
        self.assertEqual(first_operation["cleanup_scope_id"], self.task["id"])

        retrievable = lesson_manager.list_class_commentary_memory_records_for_scope(
            organization_id=self.teacher["organization_id"],
            memory_type="teacher_style",
            skill_registry_id=self.skill["registry_id"],
        )
        self.assertEqual([row["id"] for row in retrievable], [record_id])
        with lesson_manager.get_conn() as conn:
            evidence_statuses = {
                int(row["id"]): str(row["status"])
                for row in conn.execute(
                    """
                    SELECT id, status FROM class_commentary_memory_evidence
                    WHERE memory_record_id=? ORDER BY id
                    """,
                    (record_id,),
                ).fetchall()
            }
        self.assertEqual(evidence_statuses[result1["evidence"][0]["id"]], "revoked")
        self.assertEqual(evidence_statuses[result2["evidence"][0]["id"]], "active")

        replay = lesson_manager.prepare_class_commentary_memory_cleanup_for_scope(
            organization_id=self.teacher["organization_id"],
            task_id=self.task["id"],
        )
        self.assertEqual(replay["record_ids"], [])
        self.assertEqual(
            lesson_manager.get_class_commentary_memory_records_by_ids([record_id])[0][
                "record_version"
            ],
            3,
        )

        last_cleanup = lesson_manager.prepare_class_commentary_memory_cleanup_for_scope(
            organization_id=self.teacher["organization_id"],
            task_id=task2["id"],
        )
        last_record = lesson_manager.get_class_commentary_memory_records_by_ids(
            [record_id]
        )[0]
        last_operation = lesson_manager.get_class_commentary_memory_operation(
            last_cleanup["operation_ids"][0]
        )
        self.assertEqual(last_cleanup["evidence_ids"], [result2["evidence"][0]["id"]])
        self.assertEqual(last_record["desired_status"], "deleted")
        self.assertEqual(last_record["record_version"], 4)
        self.assertEqual(last_record["active_evidence_count"], 0)
        self.assertEqual(last_operation["operation_type"], "delete")
        self.assertEqual(last_operation["projection_metadata"]["evidence_count"], 0)
        self.assertFalse(
            lesson_manager.has_pending_class_commentary_memory_cleanup(
                organization_id=self.teacher["organization_id"],
                task_id=self.task["id"],
            )
        )
        self.assertTrue(
            lesson_manager.has_pending_class_commentary_memory_cleanup(
                organization_id=self.teacher["organization_id"],
                task_id=task2["id"],
            )
        )

    def test_student_cleanup_targets_student_records_and_scope_ids_do_not_collide(self):
        revision = self._confirm("memory-cleanup-student")
        result = self._extract(
            revision,
            [
                {
                    "memory_type": "student_fact",
                    "student_id": self.student["id"],
                    "memory_text": "验算仍需提醒",
                },
                {
                    "memory_type": "teacher_style",
                    "memory_text": "结尾保留一条具体建议",
                },
            ],
        )
        student_record = next(
            row for row in result["records"] if row["memory_type"] == "student_fact"
        )
        style_record = next(
            row for row in result["records"] if row["memory_type"] == "teacher_style"
        )

        cleanup = lesson_manager.prepare_class_commentary_memory_cleanup_for_scope(
            organization_id=self.teacher["organization_id"],
            student_id=self.student["id"],
        )
        self.assertEqual(cleanup["scope_type"], "student")
        self.assertEqual(cleanup["scope_id"], self.student["id"])
        self.assertEqual(cleanup["record_ids"], [student_record["id"]])
        student_after = lesson_manager.get_class_commentary_memory_records_by_ids(
            [student_record["id"]]
        )[0]
        style_after = lesson_manager.get_class_commentary_memory_records_by_ids(
            [style_record["id"]]
        )[0]
        operation = lesson_manager.get_class_commentary_memory_operation(
            cleanup["operation_ids"][0]
        )
        self.assertEqual(student_after["desired_status"], "deleted")
        self.assertEqual(style_after["desired_status"], "active")
        self.assertEqual(operation["cleanup_scope_type"], "student")
        self.assertEqual(operation["cleanup_scope_id"], self.student["id"])
        self.assertTrue(
            lesson_manager.has_pending_class_commentary_memory_cleanup(
                organization_id=self.teacher["organization_id"],
                student_id=self.student["id"],
            )
        )
        self.assertFalse(
            lesson_manager.has_pending_class_commentary_memory_cleanup(
                organization_id=self.teacher["organization_id"],
                task_id=self.student["id"],
            )
        )
        self.assertFalse(
            lesson_manager.has_pending_class_commentary_memory_cleanup(
                organization_id=self.teacher["organization_id"],
                class_id=self.student["id"],
            )
        )

    def test_class_and_teacher_cleanup_use_their_own_active_evidence_scope(self):
        memory_text = "建议结尾必须落到可执行动作"
        revision1 = self._confirm("memory-cleanup-class-first")
        result1 = self._extract(
            revision1,
            [{"memory_type": "teacher_style", "memory_text": memory_text}],
        )
        class2_id = lesson_manager.save_class(
            "记忆事实层第二测试班",
            subject="数学",
            grade="七年级",
            organization_id=self.teacher["organization_id"],
            teacher_user_id=self.teacher["id"],
            student_ids=[self.student["id"]],
        )
        task2, generation2 = self._create_task_and_generation(
            "cleanup-class-second",
            class_id=class2_id,
        )
        revision2 = lesson_manager.confirm_class_commentary_feedback(
            task_id=task2["id"],
            generation_id=generation2["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text="小王: 请继续落实下一步动作.",
            learn_requested=True,
            expected_draft_version=0,
            confirmation_request_id="memory-cleanup-class-second",
        )
        result2 = self._extract(
            revision2,
            [{"memory_type": "teacher_style", "memory_text": memory_text}],
        )
        record_id = result1["records"][0]["id"]
        self.assertEqual(result2["records"][0]["id"], record_id)

        class_cleanup = lesson_manager.prepare_class_commentary_memory_cleanup_for_scope(
            organization_id=self.teacher["organization_id"],
            class_id=self.class_id,
        )
        class_operation = lesson_manager.get_class_commentary_memory_operation(
            class_cleanup["operation_ids"][0]
        )
        after_class = lesson_manager.get_class_commentary_memory_records_by_ids(
            [record_id]
        )[0]
        self.assertEqual(class_cleanup["evidence_ids"], [result1["evidence"][0]["id"]])
        self.assertEqual(class_operation["cleanup_scope_type"], "class")
        self.assertEqual(class_operation["cleanup_scope_id"], self.class_id)
        self.assertEqual(class_operation["operation_type"], "update")
        self.assertEqual(after_class["desired_status"], "active")
        self.assertEqual(after_class["active_evidence_count"], 1)

        teacher_cleanup = lesson_manager.prepare_class_commentary_memory_cleanup_for_scope(
            organization_id=self.teacher["organization_id"],
            teacher_user_id=self.teacher["id"],
        )
        teacher_operation = lesson_manager.get_class_commentary_memory_operation(
            teacher_cleanup["operation_ids"][0]
        )
        after_teacher = lesson_manager.get_class_commentary_memory_records_by_ids(
            [record_id]
        )[0]
        self.assertEqual(
            teacher_cleanup["evidence_ids"],
            [result2["evidence"][0]["id"]],
        )
        self.assertEqual(teacher_operation["cleanup_scope_type"], "teacher")
        self.assertEqual(teacher_operation["cleanup_scope_id"], self.teacher["id"])
        self.assertEqual(teacher_operation["operation_type"], "delete")
        self.assertEqual(after_teacher["desired_status"], "deleted")
        self.assertEqual(after_teacher["active_evidence_count"], 0)

    def test_commit_boundary_rejects_roster_names_and_private_information(self):
        revision = self._confirm("memory-confirm-private-boundary")
        job = revision["memory_job"]
        claimed = lesson_manager.claim_class_commentary_memory_extraction_job(
            job["id"],
            claim_owner="untrusted-internal-caller",
        )
        with self.assertRaisesRegex(ValueError, "private information|roster name"):
            lesson_manager.commit_class_commentary_memory_extraction(
                job["id"],
                claim_token=claimed["claim_token"],
                items=[
                    {
                        "memory_type": "teacher_style",
                        "memory_text": "小王家长手机号是 13800138000",
                        "confidence": 0.9,
                        "evidence": {"support": ["请按这个联系方式提醒"]},
                    }
                ],
            )
        with lesson_manager.get_conn() as conn:
            record_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_memory_records"
            ).fetchone()[0]
        self.assertEqual(record_count, 0)

    def test_shared_record_updates_evidence_count_and_revokes_only_after_last_source(self):
        memory_text = "建议必须具体到下一步动作"
        revision1 = self._confirm("memory-confirm-shared-first")
        result1 = self._extract(
            revision1,
            [{"memory_type": "teacher_style", "memory_text": memory_text}],
        )
        task2, generation2 = self._create_task_and_generation("second-shared")
        revision2 = lesson_manager.confirm_class_commentary_feedback(
            task_id=task2["id"],
            generation_id=generation2["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text="小王: 继续把下一步动作写清楚.",
            learn_requested=True,
            expected_draft_version=0,
            confirmation_request_id="memory-confirm-shared-second",
        )
        result2 = self._extract(
            revision2,
            [{"memory_type": "teacher_style", "memory_text": memory_text}],
        )
        self.assertEqual(result2["records"][0]["id"], result1["records"][0]["id"])
        self.assertEqual(result2["records"][0]["record_version"], 2)
        self.assertEqual(result2["operations"][0]["operation_type"], "update")
        self.assertEqual(
            result2["operations"][0]["projection_metadata"]["evidence_count"], 2
        )

        first_revoke = lesson_manager.revoke_class_commentary_memory_evidence(
            result1["evidence"][0]["id"],
            actor_user_id=self.teacher["id"],
            request_id="revoke-shared-first-source",
        )
        self.assertEqual(first_revoke["record"]["desired_status"], "active")
        self.assertEqual(first_revoke["record"]["record_version"], 3)
        self.assertEqual(first_revoke["operation"]["operation_type"], "update")
        self.assertEqual(
            first_revoke["operation"]["projection_metadata"]["evidence_count"], 1
        )
        second_revoke = lesson_manager.revoke_class_commentary_memory_evidence(
            result2["evidence"][0]["id"],
            actor_user_id=self.teacher["id"],
            request_id="revoke-shared-second-source",
        )
        self.assertEqual(second_revoke["record"]["desired_status"], "revoked")
        self.assertEqual(second_revoke["record"]["record_version"], 4)
        self.assertEqual(second_revoke["operation"]["operation_type"], "revoke")
        self.assertEqual(
            second_revoke["operation"]["projection_metadata"]["evidence_count"], 0
        )


if __name__ == "__main__":
    unittest.main()
