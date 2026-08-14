from datetime import datetime, timezone
import unittest

from class_commentary_graph_queue import (
    enqueue_class_commentary_graph_extraction_job,
    enqueue_class_commentary_graph_sync_operation,
)
from class_commentary_memory_queue import (
    class_commentary_memory_queue_healthcheck,
    dispatch_class_commentary_memory_work,
    enqueue_class_commentary_student_generation_run,
    enqueue_class_commentary_skill_candidate_build,
    enqueue_class_commentary_memory_extraction_job,
    ensure_class_commentary_memory_reconciliation_scheduled,
)


ENABLED_CONFIG = {
    "class_commentary_memory_enabled": True,
    "class_commentary_memory_extraction_timeout": 300,
    "class_commentary_memory_operation_timeout": 120,
    "class_commentary_memory_reconcile_interval": 600,
}


class FakeJob:
    def __init__(self, job_id, status="queued"):
        self.id = job_id
        self.status = status
        self.deleted = False

    def get_status(self, refresh=False):
        return self.status

    def delete(self):
        self.deleted = True


class FakeQueue:
    def __init__(self):
        self.jobs = {}
        self.enqueue_calls = []
        self.enqueue_in_calls = []

    def fetch_job(self, job_id):
        job = self.jobs.get(job_id)
        return None if job is not None and job.deleted else job

    def enqueue(self, function, *args, job_id, **kwargs):
        job = FakeJob(job_id)
        self.jobs[job_id] = job
        self.enqueue_calls.append((function, args, job_id, kwargs))
        return job

    def enqueue_in(self, delay, function, *args, job_id, **kwargs):
        job = FakeJob(job_id, status="scheduled")
        self.jobs[job_id] = job
        self.enqueue_in_calls.append((delay, function, args, job_id, kwargs))
        return job


class DisabledStore:
    def __getattr__(self, name):
        raise AssertionError(f"disabled dispatcher called store method {name}")


class FailingRedis:
    def ping(self):
        raise RuntimeError("redis://user:secret@private-host:6379/0")


class ReadyRedis:
    def ping(self):
        return True


class ClassCommentaryMemoryQueueTests(unittest.TestCase):
    def test_graph_retries_follow_the_current_database_attempt(self):
        queue = FakeQueue()

        enqueue_class_commentary_graph_extraction_job(
            {"id": 7, "attempt_count": 1, "checkpoint_count": 2},
            queue=queue,
            runtime_config={"class_commentary_graph_extraction_timeout": 300},
        )
        enqueue_class_commentary_graph_sync_operation(
            {"id": 9, "attempt_count": 1},
            queue=queue,
            runtime_config={"class_commentary_graph_sync_timeout": 120},
        )

        self.assertEqual(len(queue.enqueue_calls), 2)
        extraction_retry = queue.enqueue_calls[0][3]["retry"]
        sync_retry = queue.enqueue_calls[1][3]["retry"]
        self.assertEqual(extraction_retry.max, 2)
        self.assertEqual(extraction_retry.intervals, [121, 601])
        self.assertEqual(sync_retry.max, 3)
        self.assertEqual(sync_retry.intervals, [61, 121, 241])

    def test_duplicate_enqueue_keeps_one_rq_job_for_one_attempt(self):
        queue = FakeQueue()
        job = {"id": 17, "attempt_count": 1}

        first, first_created = enqueue_class_commentary_memory_extraction_job(
            job, queue=queue, runtime_config=ENABLED_CONFIG
        )
        second, second_created = enqueue_class_commentary_memory_extraction_job(
            job, queue=queue, runtime_config=ENABLED_CONFIG
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertIs(first, second)
        self.assertEqual(first.id, "cc-memory-extract-17-a2")
        self.assertEqual(len(queue.enqueue_calls), 1)
        kwargs = queue.enqueue_calls[0][3]
        self.assertEqual(kwargs["job_timeout"], 300)
        self.assertEqual(kwargs["retry"].max, 3)
        self.assertEqual(kwargs["retry"].intervals, [30, 120, 600])

    def test_disabled_dispatcher_is_a_safe_noop(self):
        result = dispatch_class_commentary_memory_work(
            store=DisabledStore(),
            queue=FakeQueue(),
            runtime_config={"class_commentary_memory_enabled": False},
        )

        self.assertEqual(
            result,
            {
                "enabled": False,
                "extractions": 0,
                "operations": 0,
                "candidates": 0,
                "student_generations": 0,
                "errors": [],
            },
        )

    def test_student_run_enqueue_is_idempotent_and_supports_delayed_retry(self):
        queue = FakeQueue()
        config = {
            **ENABLED_CONFIG,
            "class_commentary_student_generation_timeout": 240,
        }
        run = {"id": 41, "attempt_count": 1, "status": "retry_wait"}

        first, first_created = enqueue_class_commentary_student_generation_run(
            run,
            queue=queue,
            runtime_config=config,
            delay_seconds=90,
        )
        second, second_created = enqueue_class_commentary_student_generation_run(
            run,
            queue=queue,
            runtime_config=config,
            delay_seconds=90,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertIs(first, second)
        self.assertEqual(first.id, "cc-student-generation-41-a2")
        self.assertEqual(len(queue.enqueue_in_calls), 1)
        delay, _, args, _, kwargs = queue.enqueue_in_calls[0]
        self.assertEqual(int(delay.total_seconds()), 90)
        self.assertEqual(args, (41,))
        self.assertEqual(kwargs["job_timeout"], 240)

    def test_candidate_build_uses_dedicated_timeout_and_retry_schedule(self):
        queue = FakeQueue()

        first, first_created = enqueue_class_commentary_skill_candidate_build(
            {"id": 23, "attempt_count": 1},
            queue=queue,
            runtime_config=ENABLED_CONFIG,
        )
        second, second_created = enqueue_class_commentary_skill_candidate_build(
            {"id": 23, "attempt_count": 1},
            queue=queue,
            runtime_config=ENABLED_CONFIG,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertIs(first, second)
        self.assertEqual(first.id, "cc-skill-candidate-23-a2")
        kwargs = queue.enqueue_calls[0][3]
        self.assertEqual(kwargs["job_timeout"], 300)
        self.assertEqual(kwargs["retry"].max, 2)
        self.assertEqual(kwargs["retry"].intervals, [60, 300])

    def test_reconciliation_schedule_is_idempotent_per_time_bucket(self):
        queue = FakeQueue()
        now = datetime(2026, 7, 14, 15, 3, tzinfo=timezone.utc)

        first = ensure_class_commentary_memory_reconciliation_scheduled(
            queue=queue, runtime_config=ENABLED_CONFIG, now=now
        )
        second = ensure_class_commentary_memory_reconciliation_scheduled(
            queue=queue, runtime_config=ENABLED_CONFIG, now=now
        )

        self.assertTrue(first["scheduled"])
        self.assertFalse(second["scheduled"])
        self.assertEqual(first["job_id"], "cc-memory-reconcile-20260714151000")
        self.assertEqual(len(queue.enqueue_in_calls), 1)
        delay, _, args, _, kwargs = queue.enqueue_in_calls[0]
        self.assertEqual(args, ())
        self.assertEqual(kwargs["job_timeout"], 300)
        self.assertEqual(kwargs["retry"].max, 5)
        self.assertEqual(kwargs["retry"].intervals, [60, 120, 300, 600, 1200])

    def test_queue_healthcheck_requires_redis_and_a_worker(self):
        ready = class_commentary_memory_queue_healthcheck(
            runtime_config=ENABLED_CONFIG,
            connection=ReadyRedis(),
            queue=FakeQueue(),
            worker_count_getter=lambda **kwargs: 1,
        )
        no_worker = class_commentary_memory_queue_healthcheck(
            runtime_config=ENABLED_CONFIG,
            connection=ReadyRedis(),
            queue=FakeQueue(),
            worker_count_getter=lambda **kwargs: 0,
        )

        self.assertTrue(ready["healthy"])
        self.assertEqual(ready["status"], "ready")
        self.assertFalse(no_worker["healthy"])
        self.assertEqual(no_worker["status"], "no_workers")

    def test_queue_healthcheck_does_not_raise_or_leak_redis_url(self):
        result = class_commentary_memory_queue_healthcheck(
            runtime_config=ENABLED_CONFIG,
            connection=FailingRedis(),
            queue=FakeQueue(),
        )

        self.assertFalse(result["healthy"])
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("secret", str(result))
        self.assertEqual(result["error_type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
