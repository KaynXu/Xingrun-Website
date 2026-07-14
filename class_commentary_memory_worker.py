from __future__ import annotations

from typing import Mapping, Optional

from rq import Worker

import config_runtime
from class_commentary_memory_queue import (
    ensure_class_commentary_memory_reconciliation_scheduled,
    get_class_commentary_memory_queue,
    get_class_commentary_memory_redis_connection,
    memory_feature_enabled,
)


def run_worker(
    *,
    runtime_config: Optional[Mapping[str, object]] = None,
    connection=None,
    worker_factory=Worker,
) -> int:
    config = dict(
        runtime_config if runtime_config is not None else config_runtime.get_runtime_config()
    )
    if not memory_feature_enabled(config):
        return 0
    redis_connection = connection or get_class_commentary_memory_redis_connection(config)
    queue = get_class_commentary_memory_queue(
        runtime_config=config,
        connection=redis_connection,
    )
    ensure_class_commentary_memory_reconciliation_scheduled(
        queue=queue,
        runtime_config=config,
    )
    worker = worker_factory([queue], connection=redis_connection)
    worker.work(with_scheduler=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_worker())
