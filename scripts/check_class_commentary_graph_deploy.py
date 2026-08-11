#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config_runtime
from class_commentary_graph_queue import ensure_class_commentary_graph_reconciliation_scheduled
from class_commentary_learning_graph import rebuild_semantica_graph
from class_commentary_memory_queue import (
    class_commentary_memory_queue_healthcheck,
    get_class_commentary_memory_queue,
    get_class_commentary_memory_redis_connection,
)
from class_commentary_semantica import SemanticaGraphAdapter


def validate_rebuild_health(rebuild: dict, health: dict) -> None:
    if not health.get("healthy"):
        raise SystemExit("Semantica graph healthcheck failed")
    count_fields = (
        "event_count",
        "node_count",
        "edge_count",
        "curriculum_node_count",
        "curriculum_edge_count",
    )
    mismatches = [
        field
        for field in count_fields
        if int(health.get(field) or 0) != int(rebuild.get(field) or 0)
    ]
    if mismatches:
        raise SystemExit(
            "Semantica rebuild health count mismatch: " + ", ".join(mismatches)
        )
    if str(health.get("store_hash") or "") != str(rebuild.get("store_hash") or ""):
        raise SystemExit("Semantica rebuild store hash mismatch")


def main() -> int:
    config = config_runtime.get_runtime_config()
    if not config.get("class_commentary_graph_enabled"):
        raise SystemExit("XR_CLASS_COMMENTARY_GRAPH_ENABLED is not enabled")
    if config.get("class_commentary_graph_explorer_enabled"):
        raise SystemExit("XR_CLASS_COMMENTARY_GRAPH_EXPLORER_ENABLED must remain disabled")
    store_path = Path(str(config.get("class_commentary_graph_store_path") or ""))
    if not store_path.is_absolute():
        raise SystemExit("XR_CLASS_COMMENTARY_GRAPH_STORE_PATH must be an absolute path")
    store_path.parent.mkdir(parents=True, exist_ok=True)
    probe = store_path.parent / f".{store_path.name}.write-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
    finally:
        probe.unlink(missing_ok=True)
    adapter = SemanticaGraphAdapter(
        store_path,
        timeout_seconds=int(config.get("class_commentary_graph_timeout") or 10),
    )
    rebuild = rebuild_semantica_graph(adapter)
    health = adapter.health()
    health["store_hash"] = adapter.store_hash()
    validate_rebuild_health(rebuild, health)
    redis_connection = get_class_commentary_memory_redis_connection(config)
    queue = get_class_commentary_memory_queue(
        runtime_config=config,
        connection=redis_connection,
    )
    queue_health = class_commentary_memory_queue_healthcheck(
        runtime_config={**config, "class_commentary_memory_enabled": True},
        connection=redis_connection,
        queue=queue,
    )
    if not queue_health.get("healthy"):
        raise SystemExit("Graph Redis/RQ healthcheck failed")
    schedule = ensure_class_commentary_graph_reconciliation_scheduled(
        queue=queue,
        runtime_config=config,
    )
    print(
        json.dumps(
            {
                "graph": "ready",
                "semantica_version": health.get("semantica_version"),
                "event_count": health.get("event_count"),
                "curriculum_node_count": health.get("curriculum_node_count"),
                "curriculum_edge_count": health.get("curriculum_edge_count"),
                "rebuild_event_count": rebuild.get("event_count"),
                "rq_worker_count": queue_health.get("worker_count"),
                "reconciliation_job_id": schedule.get("job_id"),
                "explorer_enabled": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
