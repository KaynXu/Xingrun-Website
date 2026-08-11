#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import curriculum_registry
import lesson_manager
from class_commentary_graph_jobs import (
    process_class_commentary_graph_extraction_job,
    process_class_commentary_graph_sync_operation,
)
from class_commentary_learning_graph import (
    canonical_json,
    content_hash,
    get_student_learning_graph_summary,
    list_dispatchable_graph_sync_operations,
    rebuild_semantica_graph,
    resolve_graph_unmapped_candidate,
)
from class_commentary_semantica import SemanticaGraphAdapter
from scripts.canary_class_commentary_semantica import (
    _create_revision_job,
    _insert_scope,
    _schema,
)


def _extractor_for(
    *, knowledge_point_key: str | None, unmapped_candidate: str | None
):
    def extractor(student_input: dict, _config: dict) -> dict:
        text = str(student_input["feedback_text"])
        quote = str(unmapped_candidate or "多位数乘一位数")
        start = text.index(quote)
        return {
            "schema_version": "student_learning_event.v1",
            "items": [
                {
                    "knowledge_point_key": knowledge_point_key,
                    "unmapped_candidate": unmapped_candidate,
                    "observed_state": "weak",
                    "reported_trend": "new_observation",
                    "evidence_quote": quote,
                    "evidence_start_offset": start,
                    "evidence_end_offset": start + len(quote),
                    "evidence_content_hash": hashlib.sha256(
                        quote.encode("utf-8")
                    ).hexdigest(),
                    "teaching_methods": [],
                    "next_steps": [],
                    "teaching_method_causal_supported": False,
                    "teaching_method_causal_evidence": [],
                }
            ],
        }

    return extractor


def _sync_all(config: dict, adapter: SemanticaGraphAdapter) -> None:
    while True:
        operations = list_dispatchable_graph_sync_operations(limit=100)
        if not operations:
            return
        for operation in operations:
            process_class_commentary_graph_sync_operation(
                int(operation["id"]),
                runtime_config=config,
                adapter=adapter,
            )


def main() -> int:
    old_db_path = lesson_manager.DB_PATH
    try:
        with tempfile.TemporaryDirectory(prefix="xingrun-pep-math-canary-") as temp_dir:
            root = Path(temp_dir)
            db_path = root / "pep-canary.sqlite3"
            graph_path = root / "pep-canary-semantica.json"
            lesson_manager.DB_PATH = db_path
            with lesson_manager.get_conn() as conn:
                _schema(conn)
                conn.execute(
                    "ALTER TABLE classes ADD COLUMN subject_key TEXT NOT NULL DEFAULT 'math'"
                )
                _insert_scope(
                    conn,
                    organization_id=1,
                    teacher_id=11,
                    class_id=21,
                    task_id=31,
                    generation_id=41,
                    class_name="三年级数学 Canary",
                )
                curriculum_registry.ensure_curriculum_schema(conn)
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
                book = conn.execute(
                    """
                    SELECT * FROM curriculum_nodes
                    WHERE version_id=? AND upstream_id='math_3a_rjb'
                    """,
                    (version_id,),
                ).fetchone()
                assignment = curriculum_registry.assign_curriculum_book(
                    conn,
                    organization_id=1,
                    class_id=21,
                    version_id=version_id,
                    book_node_id=int(book["id"]),
                    actor_user_id=11,
                    request_id="pep-canary-assignment",
                    expected_assignment_id=None,
                )
                target = conn.execute(
                    """
                    SELECT * FROM curriculum_nodes
                    WHERE version_id=? AND upstream_id='math_3a_rjb_cpt20'
                    """,
                    (version_id,),
                ).fetchone()
                mapping_target = conn.execute(
                    """
                    SELECT * FROM curriculum_nodes
                    WHERE version_id=? AND upstream_id='math_3a_rjb_skl11'
                    """,
                    (version_id,),
                ).fetchone()
                direct_job = _create_revision_job(
                    conn,
                    revision_id=51,
                    organization_id=1,
                    task_id=31,
                    generation_id=41,
                    teacher_id=11,
                    revision_no=1,
                    student_id=101,
                    feedback_text="多位数乘一位数目前薄弱, 需要分步练习.",
                    confirmed_at="2026-08-11T10:00:00Z",
                )
                unknown_job = _create_revision_job(
                    conn,
                    revision_id=52,
                    organization_id=1,
                    task_id=31,
                    generation_id=41,
                    teacher_id=11,
                    revision_no=2,
                    student_id=101,
                    feedback_text="估算策略辨析仍需加强.",
                    confirmed_at="2026-08-11T11:00:00Z",
                )
                conn.execute(
                    "INSERT INTO students(id, organization_id, status) VALUES (202, 1, 'active')"
                )

            config = {
                "class_commentary_graph_enabled": True,
                "class_commentary_graph_store_path": str(graph_path),
                "class_commentary_graph_timeout": 30,
                "class_commentary_graph_extraction_timeout": 30,
                "class_commentary_graph_sync_timeout": 120,
                "class_commentary_provider": "canary",
                "class_commentary_model": "synthetic-no-provider-call",
            }
            direct_result = process_class_commentary_graph_extraction_job(
                direct_job,
                extractor=_extractor_for(
                    knowledge_point_key=str(target["node_key"]),
                    unmapped_candidate=None,
                ),
                dispatcher=lambda **_: {"enabled": True},
                runtime_config=config,
            )
            unknown_result = process_class_commentary_graph_extraction_job(
                unknown_job,
                extractor=_extractor_for(
                    knowledge_point_key=None,
                    unmapped_candidate="估算策略辨析",
                ),
                dispatcher=lambda **_: {"enabled": True},
                runtime_config=config,
            )
            if unknown_result["status"] != "needs_mapping":
                raise AssertionError("unknown candidate did not enter needs_mapping")
            mapped = resolve_graph_unmapped_candidate(
                unknown_result["unmapped_candidate_ids"][0],
                organization_id=1,
                actor_user_id=11,
                request_id="pep-canary-map",
                action="map",
                target_knowledge_point_key=str(mapping_target["node_key"]),
            )
            if mapped["candidate"]["status"] != "mapped":
                raise AssertionError("mapped candidate was not deterministically replayed")

            with lesson_manager.get_conn() as conn:
                catalog = curriculum_registry.list_curriculum_nodes(
                    conn,
                    version_id=version_id,
                    book_upstream_id="math_3a_rjb",
                    query="多位数乘一位数",
                    page=1,
                    page_size=20,
                )
                detail = curriculum_registry.get_curriculum_node_detail(
                    conn,
                    int(target["id"]),
                    book_node_id=int(book["id"]),
                )
                ambiguous = curriculum_registry.resolve_curriculum_knowledge_point(
                    conn,
                    organization_id=1,
                    class_id=21,
                    subject_key="math",
                    value="估算",
                )
                other_book_membership = conn.execute(
                    """
                    SELECT COUNT(DISTINCT book.upstream_id)
                    FROM curriculum_book_nodes membership
                    JOIN curriculum_nodes book ON book.id=membership.book_node_id
                    WHERE membership.node_id=? AND membership.membership_type='appears_in'
                      AND book.upstream_id<>'math_3a_rjb'
                    """,
                    (int(target["id"]),),
                ).fetchone()[0]
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
            catalog_target = next(
                (
                    item
                    for item in catalog["items"]
                    if str(item["node_key"]) == str(target["node_key"])
                ),
                None,
            )
            if catalog["total"] < 1 or not catalog_target or not detail or len(detail["path"]) < 3:
                raise AssertionError("third-grade hierarchy or search canary failed")
            if not any(detail["relations"].values()):
                raise AssertionError("third-grade relationship canary failed")
            if ambiguous is not None or int(other_book_membership) != 0:
                raise AssertionError("grade/book isolation did not fail closed")

            adapter = SemanticaGraphAdapter(graph_path, timeout_seconds=30)
            _sync_all(config, adapter)
            summary_before = get_student_learning_graph_summary(
                organization_id=1,
                task_id=31,
                student_id=101,
                subject_key="math",
            )
            student_b = get_student_learning_graph_summary(
                organization_id=1,
                task_id=31,
                student_id=202,
                subject_key="math",
            )
            if student_b["current_states"] or student_b["timeline"]:
                raise AssertionError("student isolation failed")
            graph_before = adapter.scoped_snapshot(
                organization_id=1,
                student_id=101,
                subject_key="math",
            )
            student_b_graph = adapter.scoped_snapshot(
                organization_id=1,
                student_id=202,
                subject_key="math",
            )
            if student_b_graph["nodes"] or student_b_graph["edges"]:
                raise AssertionError("Semantica student isolation failed")
            health = adapter.health()
            if (
                health.get("curriculum_node_count") != 2237
                or health.get("curriculum_edge_count") != 4007
            ):
                raise AssertionError("complete curriculum was not written through Semantica")

            with lesson_manager.get_conn() as conn:
                operation_id = int(
                    conn.execute(
                        "SELECT id FROM class_commentary_graph_sync_outbox ORDER BY id LIMIT 1"
                    ).fetchone()[0]
                )
                conn.execute(
                    "UPDATE class_commentary_graph_sync_outbox SET status='reconcile_needed' WHERE id=?",
                    (operation_id,),
                )
            process_class_commentary_graph_sync_operation(
                operation_id,
                runtime_config=config,
                adapter=adapter,
            )
            replay_hash = adapter.scoped_snapshot(
                organization_id=1,
                student_id=101,
                subject_key="math",
            )["hash"]
            if replay_hash != graph_before["hash"]:
                raise AssertionError("Semantica event replay was not idempotent")

            graph_path.unlink()
            rebuilt = rebuild_semantica_graph(adapter)
            graph_after = adapter.scoped_snapshot(
                organization_id=1,
                student_id=101,
                subject_key="math",
            )
            summary_after = get_student_learning_graph_summary(
                organization_id=1,
                task_id=31,
                student_id=101,
                subject_key="math",
            )
            if graph_after["hash"] != graph_before["hash"]:
                raise AssertionError("Semantica rebuild graph hash changed")
            context_hash_before = content_hash(canonical_json(summary_before))
            context_hash_after = content_hash(canonical_json(summary_after))
            if context_hash_after != context_hash_before:
                raise AssertionError("canonical student context hash changed after rebuild")
            if integrity != "ok" or foreign_keys:
                raise AssertionError("temporary SQLite integrity check failed")

            print(
                canonical_json(
                    {
                        "source_revision": curriculum_registry.SOURCE_DATASET_REVISION,
                        "source_sha256": curriculum_registry.SOURCE_SHA256,
                        "assignment_id": int(assignment["id"]),
                        "book": str(book["canonical_name"]),
                        "catalog_match": str(catalog_target["canonical_name"]),
                        "path": [item["name"] for item in detail["path"]],
                        "relationship_count": sum(
                            len(items) for items in detail["relations"].values()
                        ),
                        "direct_event_ids": direct_result["event_ids"],
                        "unknown_status": unknown_result["status"],
                        "mapped_event_ids": mapped["reprocess"]["event_ids"],
                        "student_b_isolated": True,
                        "curriculum_node_count": health["curriculum_node_count"],
                        "curriculum_edge_count": health["curriculum_edge_count"],
                        "idempotent_replay_hash": replay_hash,
                        "rebuild_hash": graph_after["hash"],
                        "canonical_context_hash": context_hash_after,
                        "rebuild_event_count": rebuilt["event_count"],
                        "integrity_check": integrity,
                        "foreign_key_check_count": len(foreign_keys),
                    }
                )
            )
        return 0
    finally:
        lesson_manager.DB_PATH = old_db_path


if __name__ == "__main__":
    raise SystemExit(main())
