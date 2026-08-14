from __future__ import annotations

import logging
from typing import Mapping, Optional

from rq import Worker

import config_runtime
from class_commentary_memory_queue import (
    ensure_class_commentary_memory_reconciliation_scheduled,
    get_class_commentary_memory_queue,
    get_class_commentary_memory_redis_connection,
    memory_feature_enabled,
)
from class_commentary_graph_queue import (
    ensure_class_commentary_graph_reconciliation_scheduled,
    graph_feature_enabled,
)

logger = logging.getLogger(__name__)


def run_worker(
    *,
    runtime_config: Optional[Mapping[str, object]] = None,
    connection=None,
    worker_factory=Worker,
) -> int:
    config = dict(
        runtime_config if runtime_config is not None else config_runtime.get_runtime_config()
    )
    memory_enabled = memory_feature_enabled(config)
    graph_enabled = graph_feature_enabled(config)
    if not memory_enabled and not graph_enabled:
        return 0
    redis_connection = connection or get_class_commentary_memory_redis_connection(config)
    queue = get_class_commentary_memory_queue(
        runtime_config=config,
        connection=redis_connection,
    )
    if memory_enabled:
        try:
            ensure_class_commentary_memory_reconciliation_scheduled(
                queue=queue,
                runtime_config=config,
            )
        except Exception as exc:
            # Redis may be briefly unreachable at startup; the RQ work loop
            # reconnects on its own, so keep the worker alive and let the
            # next reconciliation window reschedule.
            logger.warning(
                "class commentary memory reconciliation could not be scheduled at startup: %s",
                type(exc).__name__,
            )
    if graph_enabled:
        try:
            ensure_class_commentary_graph_reconciliation_scheduled(
                queue=queue,
                runtime_config=config,
            )
        except Exception as exc:
            logger.warning(
                "class commentary graph reconciliation could not be scheduled at startup: %s",
                type(exc).__name__,
            )
    worker = worker_factory([queue], connection=redis_connection)
    worker.work(with_scheduler=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_worker())
