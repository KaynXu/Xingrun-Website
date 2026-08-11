#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config_runtime
from class_commentary_learning_graph import list_trusted_graph_events, rebuild_semantica_graph
from class_commentary_semantica import SemanticaGraphAdapter


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild the derived Semantica class-commentary graph from canonical SQLite events."
    )
    parser.add_argument("--store-path", default="")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    config = config_runtime.get_runtime_config()
    store_path = str(args.store_path or config.get("class_commentary_graph_store_path") or "").strip()
    if not store_path:
        raise SystemExit("class commentary graph store path is required")
    events = list_trusted_graph_events()
    if not args.confirm:
        print(f"dry-run: {len(events)} trusted event(s) would rebuild {store_path}")
        return 0
    result = rebuild_semantica_graph(
        SemanticaGraphAdapter(
            store_path,
            timeout_seconds=int(config.get("class_commentary_graph_timeout") or 10),
        )
    )
    print(
        f"rebuilt: events={result['event_count']} nodes={result['node_count']} "
        f"edges={result['edge_count']} store_hash={result['store_hash']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
