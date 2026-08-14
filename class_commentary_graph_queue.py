from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping, Optional

from rq import Queue, Retry

import config_runtime
from class_commentary_learning_graph import (
    GRAPH_EXTRACTION_MAX_ATTEMPTS,
    GRAPH_SYNC_MAX_ATTEMPTS,
    graph_extraction_retry_delay,
    graph_sync_retry_delay,
)
from class_commentary_memory_queue import (
    ACTIVE_RQ_STATUSES,
    FAILURE_TTL_SECONDS,
    RESULT_TTL_SECONDS,
    _job_status,
    get_class_commentary_memory_queue,
)


# RQ schedules retries at whole-second precision, while the SQLite retry gate
# records milliseconds. Keep each queue retry one second behind the audited DB
# backoff and start at the job's next database attempt.
GRAPH_RQ_RETRY_SAFETY_SECONDS = 1
GRAPH_RQ_MAX_INLINE_RETRIES = 3


def _graph_rq_retry_policy(
    *,
    attempt_count: int,
    max_attempts: int,
    delay_for_attempt: Callable[[int], int],
) -> Optional[Retry]:
    initial_attempt = int(attempt_count) + 1
    retry_count = min(
        GRAPH_RQ_MAX_INLINE_RETRIES,
        max(0, int(max_attempts) - initial_attempt),
    )
    if retry_count == 0:
        return None
    intervals = [
        int(delay_for_attempt(initial_attempt + offset))
        + GRAPH_RQ_RETRY_SAFETY_SECONDS
        for offset in range(retry_count)
    ]
    return Retry(max=retry_count, interval=intervals)


def _runtime_config(runtime_config: Optional[Mapping[str, object]] = None) -> dict:
    return dict(runtime_config if runtime_config is not None else config_runtime.get_runtime_config())


def graph_feature_enabled(runtime_config: Optional[Mapping[str, object]] = None) -> bool:
    return config_runtime.normalize_bool_flag(
        _runtime_config(runtime_config).get("class_commentary_graph_enabled")
    )


def _enqueue_once(queue: Queue, function, *args, job_id: str, **kwargs):
    existing = queue.fetch_job(job_id)
    if existing is not None and _job_status(existing) in ACTIVE_RQ_STATUSES:
        return existing, False
    if existing is not None:
        delete = getattr(existing, "delete", None)
        if callable(delete):
            delete()
        else:
            return existing, False
    return queue.enqueue(function, *args, job_id=job_id, **kwargs), True


def enqueue_class_commentary_graph_extraction_job(
    job: Mapping[str, object], *, queue: Queue, runtime_config=None
):
    from class_commentary_graph_jobs import process_class_commentary_graph_extraction_job

    config = _runtime_config(runtime_config)
    job_id = int(job["id"])
    attempt_count = int(job.get("attempt_count") or 0)
    attempt = attempt_count + 1
    checkpoint_count = int(job.get("checkpoint_count") or 0)
    return _enqueue_once(
        queue,
        process_class_commentary_graph_extraction_job,
        job_id,
        job_id=f"cc-graph-extract-{job_id}-p{checkpoint_count}-a{attempt}",
        job_timeout=int(config.get("class_commentary_graph_extraction_timeout") or 300),
        retry=_graph_rq_retry_policy(
            attempt_count=attempt_count,
            max_attempts=GRAPH_EXTRACTION_MAX_ATTEMPTS,
            delay_for_attempt=graph_extraction_retry_delay,
        ),
        result_ttl=RESULT_TTL_SECONDS,
        failure_ttl=FAILURE_TTL_SECONDS,
    )


def enqueue_class_commentary_graph_sync_operation(
    operation: Mapping[str, object], *, queue: Queue, runtime_config=None
):
    from class_commentary_graph_jobs import process_class_commentary_graph_sync_operation

    config = _runtime_config(runtime_config)
    operation_id = int(operation["id"])
    attempt_count = int(operation.get("attempt_count") or 0)
    attempt = attempt_count + 1
    return _enqueue_once(
        queue,
        process_class_commentary_graph_sync_operation,
        operation_id,
        job_id=f"cc-graph-sync-{operation_id}-a{attempt}",
        job_timeout=int(config.get("class_commentary_graph_sync_timeout") or 120),
        retry=_graph_rq_retry_policy(
            attempt_count=attempt_count,
            max_attempts=GRAPH_SYNC_MAX_ATTEMPTS,
            delay_for_attempt=graph_sync_retry_delay,
        ),
        result_ttl=RESULT_TTL_SECONDS,
        failure_ttl=FAILURE_TTL_SECONDS,
    )


def dispatch_class_commentary_graph_work(
    *, store=None, queue: Optional[Queue] = None, runtime_config=None, limit: int = 100
) -> dict:
    config = _runtime_config(runtime_config)
    if not graph_feature_enabled(config):
        return {"enabled": False, "extractions": 0, "sync_operations": 0, "errors": []}
    if store is None:
        import class_commentary_learning_graph as store
    target_queue = queue or get_class_commentary_memory_queue(runtime_config=config)
    result = {"enabled": True, "extractions": 0, "sync_operations": 0, "errors": []}
    for job in store.list_dispatchable_graph_extraction_jobs(limit=limit):
        try:
            rq_job, created = enqueue_class_commentary_graph_extraction_job(
                job, queue=target_queue, runtime_config=config
            )
            store.mark_graph_job_enqueued(int(job["id"]), str(rq_job.id))
            result["extractions"] += int(created)
        except Exception as exc:
            result["errors"].append(f"extraction:{int(job['id'])}:{exc.__class__.__name__}")
    for operation in store.list_dispatchable_graph_sync_operations(limit=limit):
        try:
            rq_job, created = enqueue_class_commentary_graph_sync_operation(
                operation, queue=target_queue, runtime_config=config
            )
            store.mark_graph_sync_enqueued(int(operation["id"]), str(rq_job.id))
            result["sync_operations"] += int(created)
        except Exception as exc:
            result["errors"].append(f"sync:{int(operation['id'])}:{exc.__class__.__name__}")
    return result


def ensure_class_commentary_graph_reconciliation_scheduled(
    *, queue: Optional[Queue] = None, runtime_config=None, now: Optional[datetime] = None
) -> dict:
    config = _runtime_config(runtime_config)
    if not graph_feature_enabled(config):
        return {"enabled": False, "scheduled": False, "job_id": None}
    from class_commentary_graph_jobs import run_class_commentary_graph_reconciliation

    target_queue = queue or get_class_commentary_memory_queue(runtime_config=config)
    interval = max(60, int(config.get("class_commentary_graph_reconcile_interval") or 600))
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    next_timestamp = ((int(current.timestamp()) // interval) + 1) * interval
    bucket = datetime.fromtimestamp(next_timestamp, tz=timezone.utc)
    rq_job_id = f"cc-graph-reconcile-{bucket.strftime('%Y%m%d%H%M%S')}"
    existing = target_queue.fetch_job(rq_job_id)
    if existing is not None and _job_status(existing) in ACTIVE_RQ_STATUSES:
        return {"enabled": True, "scheduled": False, "job_id": rq_job_id}
    if existing is not None:
        delete = getattr(existing, "delete", None)
        if callable(delete):
            delete()
        else:
            return {"enabled": True, "scheduled": False, "job_id": rq_job_id}
    target_queue.enqueue_in(
        max(bucket - current, timedelta(seconds=1)),
        run_class_commentary_graph_reconciliation,
        job_id=rq_job_id,
        job_timeout=int(config.get("class_commentary_graph_reconcile_timeout") or 300),
        retry=Retry(max=5, interval=[60, 120, 300, 600, 1200]),
        result_ttl=RESULT_TTL_SECONDS,
        failure_ttl=FAILURE_TTL_SECONDS,
    )
    return {"enabled": True, "scheduled": True, "job_id": rq_job_id}
