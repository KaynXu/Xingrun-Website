from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional

from redis import Redis
from rq import Queue, Retry, Worker

import config_runtime

logger = logging.getLogger(__name__)


RESULT_TTL_SECONDS = 86400
FAILURE_TTL_SECONDS = 604800
RETRY_INTERVALS_SECONDS = [30, 120, 600]
CANDIDATE_RETRY_INTERVALS_SECONDS = [60, 300]
ACTIVE_RQ_STATUSES = {"queued", "started", "deferred", "scheduled"}


def _runtime_config(runtime_config: Optional[Mapping[str, object]] = None) -> dict:
    return dict(runtime_config if runtime_config is not None else config_runtime.get_runtime_config())


def memory_feature_enabled(runtime_config: Optional[Mapping[str, object]] = None) -> bool:
    return config_runtime.normalize_bool_flag(
        _runtime_config(runtime_config).get("class_commentary_memory_enabled")
    )


def get_class_commentary_memory_redis_connection(
    runtime_config: Optional[Mapping[str, object]] = None,
) -> Redis:
    config = _runtime_config(runtime_config)
    try:
        connect_timeout = max(1, int(config.get("redis_connect_timeout") or 5))
    except (TypeError, ValueError):
        connect_timeout = 5
    return Redis.from_url(
        str(config.get("redis_url") or "redis://127.0.0.1:6379/0"),
        socket_connect_timeout=connect_timeout,
    )


def get_class_commentary_memory_queue(
    *,
    runtime_config: Optional[Mapping[str, object]] = None,
    connection: Optional[Redis] = None,
) -> Queue:
    config = _runtime_config(runtime_config)
    return Queue(
        str(config.get("class_commentary_memory_queue") or "class_commentary_memory"),
        connection=connection or get_class_commentary_memory_redis_connection(config),
    )


def class_commentary_memory_queue_healthcheck(
    *,
    runtime_config: Optional[Mapping[str, object]] = None,
    connection: Optional[Redis] = None,
    queue: Optional[Queue] = None,
    worker_count_getter=None,
) -> dict:
    config = _runtime_config(runtime_config)
    if not memory_feature_enabled(config):
        return {
            "enabled": False,
            "healthy": False,
            "status": "disabled",
            "redis": False,
            "worker_count": 0,
        }
    try:
        redis_connection = connection or get_class_commentary_memory_redis_connection(config)
        redis_ready = bool(redis_connection.ping())
        target_queue = queue or get_class_commentary_memory_queue(
            runtime_config=config,
            connection=redis_connection,
        )
        counter = worker_count_getter or Worker.count
        worker_count = int(counter(connection=redis_connection, queue=target_queue))
    except Exception as exc:
        return {
            "enabled": True,
            "healthy": False,
            "status": "unavailable",
            "redis": False,
            "worker_count": 0,
            "error_type": exc.__class__.__name__,
        }
    healthy = redis_ready and worker_count >= 1
    return {
        "enabled": True,
        "healthy": healthy,
        "status": "ready" if healthy else "no_workers",
        "redis": redis_ready,
        "worker_count": worker_count,
    }


def _job_status(job: object) -> str:
    getter = getattr(job, "get_status", None)
    if callable(getter):
        try:
            return str(getter(refresh=False) or "")
        except TypeError:
            return str(getter() or "")
    return str(getattr(job, "status", "") or "")


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


def enqueue_class_commentary_memory_extraction_job(
    job: Mapping[str, object],
    *,
    queue: Queue,
    runtime_config: Optional[Mapping[str, object]] = None,
):
    from class_commentary_memory_jobs import process_class_commentary_memory_extraction_job

    config = _runtime_config(runtime_config)
    job_id = int(job["id"])
    attempt = int(job.get("attempt_count") or 0) + 1
    rq_job_id = f"cc-memory-extract-{job_id}-a{attempt}"
    return _enqueue_once(
        queue,
        process_class_commentary_memory_extraction_job,
        job_id,
        job_id=rq_job_id,
        job_timeout=int(config.get("class_commentary_memory_extraction_timeout") or 300),
        retry=Retry(max=3, interval=RETRY_INTERVALS_SECONDS),
        result_ttl=RESULT_TTL_SECONDS,
        failure_ttl=FAILURE_TTL_SECONDS,
    )


def enqueue_class_commentary_memory_operation(
    operation: Mapping[str, object],
    *,
    queue: Queue,
    runtime_config: Optional[Mapping[str, object]] = None,
):
    from class_commentary_memory_jobs import process_class_commentary_memory_operation

    config = _runtime_config(runtime_config)
    operation_id = int(operation["id"])
    attempt = int(operation.get("attempt_count") or 0) + 1
    rq_job_id = f"cc-memory-operation-{operation_id}-a{attempt}"
    return _enqueue_once(
        queue,
        process_class_commentary_memory_operation,
        operation_id,
        job_id=rq_job_id,
        job_timeout=int(config.get("class_commentary_memory_operation_timeout") or 120),
        retry=Retry(max=3, interval=RETRY_INTERVALS_SECONDS),
        result_ttl=RESULT_TTL_SECONDS,
        failure_ttl=FAILURE_TTL_SECONDS,
    )


def enqueue_class_commentary_skill_candidate_build(
    build: Mapping[str, object],
    *,
    queue: Queue,
    runtime_config: Optional[Mapping[str, object]] = None,
):
    from class_commentary_memory_jobs import process_class_commentary_skill_candidate_build

    config = _runtime_config(runtime_config)
    build_id = int(build["id"])
    attempt = int(build.get("attempt_count") or 0) + 1
    rq_job_id = f"cc-skill-candidate-{build_id}-a{attempt}"
    return _enqueue_once(
        queue,
        process_class_commentary_skill_candidate_build,
        build_id,
        job_id=rq_job_id,
        job_timeout=int(config.get("skill_evolution_build_timeout") or 300),
        retry=Retry(max=2, interval=CANDIDATE_RETRY_INTERVALS_SECONDS),
        result_ttl=RESULT_TTL_SECONDS,
        failure_ttl=FAILURE_TTL_SECONDS,
    )


def enqueue_class_commentary_student_generation_run(
    run: Mapping[str, object],
    *,
    queue: Queue,
    runtime_config: Optional[Mapping[str, object]] = None,
    delay_seconds: int = 0,
):
    from class_commentary_student_generation_jobs import (
        process_class_commentary_student_generation_run,
    )

    config = _runtime_config(runtime_config)
    run_id = int(run["id"])
    attempt = int(run.get("attempt_count") or 0) + 1
    status = str(run.get("status") or "")
    if status == "response_received":
        marker_source = str(run.get("next_attempt_at") or run.get("response_hash") or "charge")
        marker = hashlib.sha256(marker_source.encode("utf-8")).hexdigest()[:12]
        rq_job_id = f"cc-student-generation-{run_id}-charge-{marker}"
    else:
        rq_job_id = f"cc-student-generation-{run_id}-a{attempt}"
    existing = queue.fetch_job(rq_job_id)
    if existing is not None and _job_status(existing) in ACTIVE_RQ_STATUSES:
        return existing, False
    if existing is not None:
        delete = getattr(existing, "delete", None)
        if callable(delete):
            delete()
        else:
            return existing, False
    enqueue_kwargs = {
        "job_id": rq_job_id,
        "job_timeout": int(
            config.get("class_commentary_student_generation_timeout") or 300
        ),
        "result_ttl": RESULT_TTL_SECONDS,
        "failure_ttl": FAILURE_TTL_SECONDS,
    }
    if int(delay_seconds) > 0:
        job = queue.enqueue_in(
            timedelta(seconds=max(1, int(delay_seconds))),
            process_class_commentary_student_generation_run,
            run_id,
            **enqueue_kwargs,
        )
    else:
        job = queue.enqueue(
            process_class_commentary_student_generation_run,
            run_id,
            **enqueue_kwargs,
        )
    return job, True


def dispatch_class_commentary_memory_work(
    *,
    store=None,
    queue: Optional[Queue] = None,
    runtime_config: Optional[Mapping[str, object]] = None,
    limit: int = 100,
) -> dict:
    config = _runtime_config(runtime_config)
    if not memory_feature_enabled(config):
        return {
            "enabled": False,
            "extractions": 0,
            "operations": 0,
            "candidates": 0,
            "student_generations": 0,
            "errors": [],
        }

    if store is None:
        import lesson_manager as store

    target_queue = queue or get_class_commentary_memory_queue(runtime_config=config)
    result = {
        "enabled": True,
        "extractions": 0,
        "operations": 0,
        "candidates": 0,
        "student_generations": 0,
        "errors": [],
    }
    extraction_jobs = store.list_dispatchable_class_commentary_memory_extraction_jobs(limit=limit)
    operations = store.list_dispatchable_class_commentary_memory_operations(limit=limit)
    candidate_lister = getattr(
        store,
        "list_dispatchable_class_commentary_skill_candidate_builds",
        None,
    )
    candidates = candidate_lister(limit=limit) if callable(candidate_lister) else []
    student_run_lister = getattr(
        store,
        "list_dispatchable_class_commentary_student_generation_runs",
        None,
    )
    student_runs = (
        student_run_lister(limit=limit) if callable(student_run_lister) else []
    )

    for run in student_runs:
        try:
            _, created = enqueue_class_commentary_student_generation_run(
                run,
                queue=target_queue,
                runtime_config=config,
            )
            result["student_generations"] += int(created)
        except Exception as exc:
            logger.warning(
                "class commentary student generation run %s could not be enqueued: %s",
                run["id"],
                type(exc).__name__,
            )
            result["errors"].append(
                f"student_generation:{int(run['id'])}:{exc.__class__.__name__}"
            )

    for job in extraction_jobs:
        try:
            rq_job, created = enqueue_class_commentary_memory_extraction_job(
                job,
                queue=target_queue,
                runtime_config=config,
            )
            store.mark_class_commentary_memory_extraction_job_enqueued(
                int(job["id"]), str(rq_job.id)
            )
            result["extractions"] += int(created)
        except Exception as exc:
            logger.warning(
                "class commentary memory extraction job %s could not be enqueued: %s",
                job["id"],
                type(exc).__name__,
            )
            result["errors"].append(
                f"extraction:{int(job['id'])}:{exc.__class__.__name__}"
            )

    for operation in operations:
        try:
            rq_job, created = enqueue_class_commentary_memory_operation(
                operation,
                queue=target_queue,
                runtime_config=config,
            )
            store.mark_class_commentary_memory_operation_enqueued(
                int(operation["id"]), str(rq_job.id)
            )
            result["operations"] += int(created)
        except Exception as exc:
            logger.warning(
                "class commentary memory operation %s could not be enqueued: %s",
                operation["id"],
                type(exc).__name__,
            )
            result["errors"].append(
                f"operation:{int(operation['id'])}:{exc.__class__.__name__}"
            )
    for build in candidates:
        try:
            _, created = enqueue_class_commentary_skill_candidate_build(
                build,
                queue=target_queue,
                runtime_config=config,
            )
            result["candidates"] += int(created)
        except Exception as exc:
            logger.warning(
                "class commentary skill candidate build %s could not be enqueued: %s",
                build["id"],
                type(exc).__name__,
            )
            result["errors"].append(
                f"candidate:{int(build['id'])}:{exc.__class__.__name__}"
            )
    return result


def _next_reconciliation_bucket(now: datetime, interval_seconds: int) -> datetime:
    normalized = now.astimezone(timezone.utc)
    timestamp = int(normalized.timestamp())
    next_timestamp = ((timestamp // interval_seconds) + 1) * interval_seconds
    return datetime.fromtimestamp(next_timestamp, tz=timezone.utc)


def ensure_class_commentary_memory_reconciliation_scheduled(
    *,
    queue: Optional[Queue] = None,
    runtime_config: Optional[Mapping[str, object]] = None,
    now: Optional[datetime] = None,
) -> dict:
    config = _runtime_config(runtime_config)
    if not memory_feature_enabled(config):
        return {"enabled": False, "scheduled": False, "job_id": None}

    from class_commentary_memory_jobs import run_class_commentary_memory_reconciliation

    target_queue = queue or get_class_commentary_memory_queue(runtime_config=config)
    interval = max(60, int(config.get("class_commentary_memory_reconcile_interval") or 600))
    current = now or datetime.now(timezone.utc)
    bucket = _next_reconciliation_bucket(current, interval)
    rq_job_id = f"cc-memory-reconcile-{bucket.strftime('%Y%m%d%H%M%S')}"
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
        max(bucket - current.astimezone(timezone.utc), timedelta(seconds=1)),
        run_class_commentary_memory_reconciliation,
        job_id=rq_job_id,
        job_timeout=int(
            config.get("class_commentary_memory_reconcile_timeout") or 300
        ),
        retry=Retry(max=5, interval=[60, 120, 300, 600, 1200]),
        result_ttl=RESULT_TTL_SECONDS,
        failure_ttl=FAILURE_TTL_SECONDS,
    )
    return {"enabled": True, "scheduled": True, "job_id": rq_job_id}
