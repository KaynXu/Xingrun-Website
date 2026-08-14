import unittest
from unittest.mock import Mock, patch

from class_commentary_memory_jobs import (
    process_class_commentary_memory_extraction_job,
    process_class_commentary_memory_operation,
    run_class_commentary_memory_reconciliation,
)
from class_commentary_memory_worker import run_worker


ENABLED_CONFIG = {
    "class_commentary_memory_enabled": True,
    "class_commentary_memory_operation_timeout": 120,
}


class FakeExtractionStore:
    def __init__(self, roster=None):
        self.claim_calls = 0
        self.commit_calls = 0
        self.status = "queued"
        self.roster = roster or [{"student_id": 7, "student_name": "林同学"}]
        self.committed_items = None

    def claim_class_commentary_memory_extraction_job(self, job_id, **kwargs):
        self.claim_calls += 1
        if self.status != "queued":
            return None
        self.status = "running"
        return {
            "id": job_id,
            "claim_token": "claim-1",
            "extraction_input_hash": "input-hash",
            "learning_evidence_hash": "evidence-hash",
        }

    def get_class_commentary_memory_extraction_input(self, job_id):
        return {
            "integrity_valid": True,
            "is_effective_revision": True,
            "extraction_input_hash": "input-hash",
            "learning_evidence_hash": "evidence-hash",
            "extraction_input": {
                "attending_roster": self.roster,
            },
        }

    def commit_class_commentary_memory_extraction(self, job_id, **kwargs):
        self.commit_calls += 1
        self.committed_items = kwargs.get("items")
        self.status = "extracted"
        return {
            "job": {"id": job_id, "status": "extracted"},
            "operations": [{"id": 31}],
        }

    def fail_class_commentary_memory_extraction_job(self, job_id, **kwargs):
        self.status = "retry_wait"
        return {"id": job_id, "status": self.status}


class FakeMemoryService:
    def __init__(self):
        self.by_operation_key = {}
        self.add_calls = 0

    def find_by_operation_key(self, operation_key, **scope):
        return self.by_operation_key.get(operation_key)

    def add_projection(self, *, memory_text, metadata):
        if metadata.get("status") != "active":
            raise AssertionError("projection status was not normalized")
        self.add_calls += 1
        item = {"id": "mem-1", "memory": memory_text, "metadata": dict(metadata)}
        self.by_operation_key[metadata["operation_key"]] = item
        return item

    def get(self, memory_id):
        return None

    def update(self, memory_id, **kwargs):
        raise AssertionError("update was not expected")

    def delete(self, memory_id):
        raise AssertionError("delete was not expected")


class FakeOperationStore:
    def __init__(self, *, eligible=True, complete_failures=0, desired_status="active"):
        self.eligible = eligible
        self.complete_failures = complete_failures
        self.desired_status = desired_status
        self.status = "pending"
        self.claim_count = 0
        self.mem0_memory_id = None

    def claim_class_commentary_memory_operation(self, operation_id, **kwargs):
        if not self.eligible or self.status not in {"pending", "reconcile_needed"}:
            return None
        self.claim_count += 1
        self.status = "running"
        return {
            "id": operation_id,
            "operation_type": "add",
            "operation_key": "cc-memory-9-v1-target",
            "lease_token": f"lease-{self.claim_count}",
            "mem0_memory_id": self.mem0_memory_id,
            "target_state": {
                "organization_id": 2,
                "memory_type": "teacher_style",
                "scope_skill_registry_id": 4,
                "memory_text": "Use shorter paragraphs.",
                "desired_status": self.desired_status,
            },
            "projection_metadata": {
                "organization_id": 2,
                "scope_skill_registry_id": 4,
                "student_id": None,
                "subject_key": None,
                "memory_type": "teacher_style",
                "generation_id": 5,
                "created_from_revision_id": 6,
                "memory_record_id": 9,
                "record_version": 1,
                "evidence_count": 1,
                "operation_key": "cc-memory-9-v1-target",
                "desired_status": self.desired_status,
                "confidence": 0.9,
                "occurred_at": "2026-07-14T15:00:00Z",
            },
        }

    def complete_class_commentary_memory_operation(self, operation_id, **kwargs):
        if self.complete_failures:
            self.complete_failures -= 1
            raise OSError("sqlite writeback unavailable")
        self.status = "applied"
        self.mem0_memory_id = kwargs.get("mem0_memory_id")
        return {"id": operation_id, "status": "applied"}

    def fail_class_commentary_memory_operation(self, operation_id, **kwargs):
        if kwargs.get("mem0_succeeded"):
            self.status = "reconcile_needed"
            self.mem0_memory_id = kwargs.get("mem0_memory_id")
        else:
            self.status = "retry_wait"
        return {"id": operation_id, "status": self.status}


class FakeStartedRegistry:
    def get_job_ids(self):
        return ["rq-active-1"]


class FakeReconciliationQueue:
    started_job_registry = FakeStartedRegistry()


class FakeReconciliationStore:
    def __init__(self):
        self.active_rq_job_ids = None

    def reconcile_class_commentary_memory_store(self, **kwargs):
        self.active_rq_job_ids = kwargs.get("active_rq_job_ids")
        return {"recovered_operations": [9]}


class ClassCommentaryMemoryWorkerTests(unittest.TestCase):
    def test_duplicate_execution_only_one_claim_reaches_extractor(self):
        store = FakeExtractionStore()
        extractor = Mock(
            return_value={
                "items": [
                    {
                        "memory_type": "student_fact",
                        "student_name": "林同学",
                        "student_id_hint": 7,
                        "memory_text": "Needs to check the last calculation step.",
                        "confidence": 0.8,
                        "support": ["Teacher retained this reminder."],
                    }
                ]
            }
        )
        dispatcher = Mock(return_value={"operations": 1})

        first = process_class_commentary_memory_extraction_job(
            12,
            store=store,
            extractor=extractor,
            dispatcher=dispatcher,
            runtime_config=ENABLED_CONFIG,
        )
        second = process_class_commentary_memory_extraction_job(
            12,
            store=store,
            extractor=extractor,
            dispatcher=dispatcher,
            runtime_config=ENABLED_CONFIG,
        )

        self.assertEqual(first["status"], "extracted")
        self.assertEqual(second["status"], "not_claimed")
        self.assertEqual(store.claim_calls, 2)
        self.assertEqual(store.commit_calls, 1)
        extractor.assert_called_once()
        dispatcher.assert_called_once()

    def test_operation_waits_until_expired_lease_is_claimable(self):
        store = FakeOperationStore(eligible=False)
        service = FakeMemoryService()

        blocked = process_class_commentary_memory_operation(
            9,
            store=store,
            memory_service=service,
            runtime_config=ENABLED_CONFIG,
        )
        store.eligible = True
        applied = process_class_commentary_memory_operation(
            9,
            store=store,
            memory_service=service,
            runtime_config=ENABLED_CONFIG,
        )

        self.assertEqual(blocked["status"], "not_claimed")
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(service.add_calls, 1)

    def test_malicious_extractor_output_is_privacy_filtered_before_commit(self):
        store = FakeExtractionStore(
            roster=[
                {"student_id": 7, "student_name": "林同学"},
                {"student_id": 8, "student_name": "王同学"},
            ]
        )
        extractor = Mock(
            return_value={
                "items": [
                    {
                        "memory_type": "teacher_style",
                        "memory_text": "Write 林同学 first.",
                        "confidence": 1,
                        "support": ["The roster contains 林同学."],
                    },
                    {
                        "memory_type": "teacher_style",
                        "memory_text": "Contact the family at 13800138000.",
                        "confidence": 1,
                        "support": ["Phone number copied from the source."],
                    },
                    {
                        "memory_type": "student_fact",
                        "student_name": "林同学",
                        "student_id_hint": 7,
                        "memory_text": "林同学 should ask 王同学 for the answer.",
                        "confidence": 1,
                        "support": ["Both names were emitted by the model."],
                    },
                    {
                        "memory_type": "student_fact",
                        "student_name": "林同学",
                        "student_id_hint": 7,
                        "memory_text": "Needs to check the final calculation step.",
                        "confidence": 0.8,
                        "support": ["Parent email is secret@example.com."],
                    },
                    {
                        "memory_type": "student_fact",
                        "student_name": "林同学",
                        "student_id_hint": 7,
                        "memory_text": "林同学 needs to check the final calculation step.",
                        "confidence": 0.8,
                        "support": ["林同学 retained the reminder. " + "x" * 600],
                    },
                ]
            }
        )

        process_class_commentary_memory_extraction_job(
            12,
            store=store,
            extractor=extractor,
            dispatcher=Mock(return_value={}),
            runtime_config=ENABLED_CONFIG,
        )

        self.assertEqual(len(store.committed_items), 1)
        committed = store.committed_items[0]
        self.assertEqual(committed["student_id"], 7)
        self.assertIn("该学生", committed["memory_text"])
        self.assertNotIn("林同学", str(committed))
        self.assertNotIn("王同学", str(committed))
        self.assertNotIn("13800138000", str(committed))
        self.assertNotIn("secret@example.com", str(committed))
        self.assertLessEqual(len(committed["evidence"]["support"][0]), 500)

    def test_mem0_success_then_sqlite_failure_reconciles_without_second_add(self):
        store = FakeOperationStore(complete_failures=1)
        service = FakeMemoryService()

        with self.assertRaisesRegex(OSError, "sqlite writeback unavailable"):
            process_class_commentary_memory_operation(
                9,
                store=store,
                memory_service=service,
                runtime_config=ENABLED_CONFIG,
            )
        self.assertEqual(store.status, "reconcile_needed")
        second = process_class_commentary_memory_operation(
            9,
            store=store,
            memory_service=service,
            runtime_config=ENABLED_CONFIG,
        )

        self.assertEqual(second["status"], "applied")
        self.assertEqual(service.add_calls, 1)
        self.assertEqual(store.mem0_memory_id, "mem-1")

    def test_reconciled_add_with_memory_id_updates_instead_of_adding_duplicate(self):
        store = FakeOperationStore()
        store.mem0_memory_id = "mem-recovered"
        service = FakeMemoryService()
        service.update = Mock(return_value={})

        result = process_class_commentary_memory_operation(
            9,
            store=store,
            memory_service=service,
            runtime_config=ENABLED_CONFIG,
        )

        self.assertEqual(result["status"], "applied")
        self.assertEqual(service.add_calls, 0)
        service.update.assert_called_once()
        self.assertEqual(service.update.call_args.args[0], "mem-recovered")

    def test_revoked_record_without_projection_does_not_create_mem0_memory(self):
        store = FakeOperationStore(desired_status="revoked")
        service = FakeMemoryService()

        result = process_class_commentary_memory_operation(
            9,
            store=store,
            memory_service=service,
            runtime_config=ENABLED_CONFIG,
        )

        self.assertEqual(result["status"], "applied")
        self.assertEqual(service.add_calls, 0)

    @patch("class_commentary_memory_queue.dispatch_class_commentary_memory_work")
    @patch("class_commentary_memory_queue.ensure_class_commentary_memory_reconciliation_scheduled")
    def test_reconciliation_schedules_next_bucket_before_dispatch(self, ensure, dispatch):
        store = FakeReconciliationStore()
        queue = FakeReconciliationQueue()
        ensure.return_value = {"scheduled": True, "job_id": "next"}
        dispatch.return_value = {"operations": 1}

        result = run_class_commentary_memory_reconciliation(
            store=store,
            queue=queue,
            runtime_config=ENABLED_CONFIG,
        )

        self.assertEqual(result["status"], "completed")
        ensure.assert_called_once()
        dispatch.assert_called_once()
        self.assertEqual(store.active_rq_job_ids, ["rq-active-1"])

    def test_disabled_worker_does_not_connect_to_redis(self):
        worker_factory = Mock()

        result = run_worker(
            runtime_config={"class_commentary_memory_enabled": False},
            worker_factory=worker_factory,
        )

        self.assertEqual(result, 0)
        worker_factory.assert_not_called()

    @patch("class_commentary_memory_worker.ensure_class_commentary_memory_reconciliation_scheduled")
    @patch("class_commentary_memory_worker.get_class_commentary_memory_queue")
    def test_worker_uses_scheduler_and_dedicated_queue(self, get_queue, ensure_scheduled):
        connection = object()
        queue = object()
        get_queue.return_value = queue
        worker = Mock()
        worker_factory = Mock(return_value=worker)

        result = run_worker(
            runtime_config=ENABLED_CONFIG,
            connection=connection,
            worker_factory=worker_factory,
        )

        self.assertEqual(result, 0)
        get_queue.assert_called_once_with(runtime_config=ENABLED_CONFIG, connection=connection)
        ensure_scheduled.assert_called_once_with(queue=queue, runtime_config=ENABLED_CONFIG)
        worker_factory.assert_called_once_with([queue], connection=connection)
        worker.work.assert_called_once_with(with_scheduler=True)

    @patch("class_commentary_memory_worker.ensure_class_commentary_memory_reconciliation_scheduled")
    @patch("class_commentary_memory_worker.ensure_class_commentary_graph_reconciliation_scheduled")
    @patch("class_commentary_memory_worker.get_class_commentary_memory_queue")
    def test_worker_supports_graph_without_mem0(
        self,
        get_queue,
        ensure_graph_scheduled,
        ensure_memory_scheduled,
    ):
        config = {
            "class_commentary_memory_enabled": False,
            "class_commentary_graph_enabled": True,
        }
        connection = object()
        queue = object()
        get_queue.return_value = queue
        worker = Mock()
        worker_factory = Mock(return_value=worker)

        result = run_worker(
            runtime_config=config,
            connection=connection,
            worker_factory=worker_factory,
        )

        self.assertEqual(result, 0)
        get_queue.assert_called_once_with(runtime_config=config, connection=connection)
        ensure_memory_scheduled.assert_not_called()
        ensure_graph_scheduled.assert_called_once_with(
            queue=queue,
            runtime_config=config,
        )
        worker_factory.assert_called_once_with([queue], connection=connection)
        worker.work.assert_called_once_with(with_scheduler=True)

    @patch("class_commentary_memory_worker.ensure_class_commentary_memory_reconciliation_scheduled")
    @patch("class_commentary_memory_worker.get_class_commentary_memory_queue")
    def test_worker_survives_reconciliation_scheduling_failures(self, get_queue, ensure_scheduled):
        connection = object()
        queue = object()
        get_queue.return_value = queue
        ensure_scheduled.side_effect = ConnectionError("redis down")
        worker = Mock()
        worker_factory = Mock(return_value=worker)

        result = run_worker(
            runtime_config=ENABLED_CONFIG,
            connection=connection,
            worker_factory=worker_factory,
        )

        self.assertEqual(result, 0)
        worker_factory.assert_called_once_with([queue], connection=connection)
        worker.work.assert_called_once_with(with_scheduler=True)


if __name__ == "__main__":
    unittest.main()
