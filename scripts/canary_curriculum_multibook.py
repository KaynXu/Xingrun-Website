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
    get_graph_extraction_input,
    get_student_learning_graph_summary,
    list_dispatchable_graph_sync_operations,
    rebuild_semantica_graph,
)
from class_commentary_semantica import SemanticaGraphAdapter
from scripts.canary_class_commentary_semantica import (
    _create_revision_job,
    _insert_scope,
    _schema,
)


def _extractor(knowledge_point_key: str, quote: str, state: str):
    def extract(student_input: dict, _config: dict) -> dict:
        feedback = str(student_input["feedback_text"])
        start = feedback.index(quote)
        return {
            "schema_version": "student_learning_event.v1",
            "items": [
                {
                    "knowledge_point_key": knowledge_point_key,
                    "unmapped_candidate": None,
                    "observed_state": state,
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

    return extract


def _sync_all(config: dict, adapter: SemanticaGraphAdapter) -> None:
    while True:
        operations = list_dispatchable_graph_sync_operations(limit=100)
        if not operations:
            return
        for operation in operations:
            process_class_commentary_graph_sync_operation(
                int(operation["id"]), runtime_config=config, adapter=adapter
            )


def _insert_additional_lesson(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    teacher_id: int,
    class_id: int,
    task_id: int,
    generation_id: int,
    class_name: str,
    grade: str,
) -> None:
    _insert_scope(
        conn,
        organization_id=organization_id,
        teacher_id=teacher_id,
        class_id=class_id,
        task_id=task_id,
        generation_id=generation_id,
        class_name=class_name,
    )
    conn.execute(
        "UPDATE classes SET subject_key='math', grade=?, current_grade=? WHERE id=?",
        (grade, grade, class_id),
    )


def main() -> int:
    old_db_path = lesson_manager.DB_PATH
    try:
        with tempfile.TemporaryDirectory(prefix="xingrun-multibook-canary-") as temp_dir:
            root = Path(temp_dir)
            db_path = root / "multibook.sqlite3"
            graph_path = root / "multibook-semantica.json"
            lesson_manager.DB_PATH = db_path
            with lesson_manager.get_conn() as conn:
                _schema(conn)
                conn.execute("ALTER TABLE classes ADD COLUMN subject_key TEXT NOT NULL DEFAULT 'math'")
                conn.execute("ALTER TABLE classes ADD COLUMN grade TEXT NOT NULL DEFAULT ''")
                conn.execute("ALTER TABLE classes ADD COLUMN current_grade TEXT NOT NULL DEFAULT ''")
                _insert_additional_lesson(
                    conn,
                    organization_id=1,
                    teacher_id=11,
                    class_id=21,
                    task_id=31,
                    generation_id=41,
                    class_name="数学·九年级·7班",
                    grade="九年级",
                )
                _insert_additional_lesson(
                    conn,
                    organization_id=1,
                    teacher_id=11,
                    class_id=25,
                    task_id=35,
                    generation_id=45,
                    class_name="数学·九年级·8班",
                    grade="九年级",
                )
                _insert_additional_lesson(
                    conn,
                    organization_id=1,
                    teacher_id=11,
                    class_id=27,
                    task_id=37,
                    generation_id=47,
                    class_name="数学·七年级·1班",
                    grade="七年级",
                )
                _insert_additional_lesson(
                    conn,
                    organization_id=1,
                    teacher_id=11,
                    class_id=23,
                    task_id=33,
                    generation_id=43,
                    class_name="数学·一年级·1班",
                    grade="一年级",
                )
                curriculum_registry.ensure_curriculum_schema(conn)
                imported = curriculum_registry.import_curriculum_bundle(
                    conn, curriculum_registry.load_bundle(), actor_user_id=11
                )
                version_id = int(imported["version"]["id"])
                curriculum_registry.review_curriculum_version(
                    conn, version_id, actor_user_id=11
                )
                curriculum_registry.activate_curriculum_version(
                    conn, version_id, actor_user_id=11
                )
                grade_nine_scope = curriculum_registry.get_effective_class_curriculum_scope(
                    conn, 21
                )
                grade_seven_registry = curriculum_registry.get_extraction_registry(
                    conn, organization_id=1, class_id=27, subject_key="math"
                )
                ambiguous = curriculum_registry.resolve_curriculum_knowledge_point(
                    conn,
                    organization_id=1,
                    class_id=23,
                    subject_key="math",
                    value="比较数量",
                )
                upper = conn.execute(
                    "SELECT * FROM curriculum_nodes WHERE version_id=? AND upstream_id='math_9a_rjb_cpt1'",
                    (version_id,),
                ).fetchone()
                lower = conn.execute(
                    "SELECT * FROM curriculum_nodes WHERE version_id=? AND upstream_id='math_9b_rjb_cpt1'",
                    (version_id,),
                ).fetchone()
                upper_job = _create_revision_job(
                    conn,
                    revision_id=51,
                    organization_id=1,
                    task_id=31,
                    generation_id=41,
                    teacher_id=11,
                    revision_no=1,
                    student_id=101,
                    feedback_text="一元二次方程目前薄弱, 需要继续练习.",
                    confirmed_at="2026-08-11T10:00:00Z",
                )
                lower_job = _create_revision_job(
                    conn,
                    revision_id=52,
                    organization_id=1,
                    task_id=35,
                    generation_id=45,
                    teacher_id=11,
                    revision_no=2,
                    student_id=101,
                    feedback_text="反比例函数正在发展中, 能识别基本图象.",
                    confirmed_at="2026-08-11T11:00:00Z",
                )
                conn.execute(
                    "INSERT INTO students(id, organization_id, status) VALUES (202, 1, 'active')"
                )
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()

            expected_books = ["math_9a_rjb", "math_9b_rjb"]
            actual_books = [
                str(item["book_upstream_id"])
                for item in grade_nine_scope["books"]
            ]
            if actual_books != expected_books:
                raise AssertionError("grade nine did not infer both semester books")
            if grade_seven_registry["registry_metadata"]["count"] != 235:
                raise AssertionError("grade seven full registry was truncated")
            if ambiguous is not None:
                raise AssertionError("cross-book ambiguity did not fail closed")

            config = {
                "class_commentary_graph_enabled": True,
                "class_commentary_graph_store_path": str(graph_path),
                "class_commentary_graph_timeout": 30,
                "class_commentary_graph_extraction_timeout": 30,
                "class_commentary_graph_sync_timeout": 120,
                "class_commentary_provider": "canary",
                "class_commentary_model": "synthetic-no-provider-call",
            }
            upper_result = process_class_commentary_graph_extraction_job(
                upper_job,
                extractor=_extractor(
                    str(upper["node_key"]), "一元二次方程", "weak"
                ),
                dispatcher=lambda **_: {"enabled": True},
                runtime_config=config,
            )
            lower_result = process_class_commentary_graph_extraction_job(
                lower_job,
                extractor=_extractor(
                    str(lower["node_key"]), "反比例函数", "developing"
                ),
                dispatcher=lambda **_: {"enabled": True},
                runtime_config=config,
            )
            frozen_upper = get_graph_extraction_input(upper_job)
            frozen_lower = get_graph_extraction_input(lower_job)
            if not frozen_upper["integrity_valid"] or not frozen_lower["integrity_valid"]:
                raise AssertionError("multi-book frozen scopes failed integrity")

            adapter = SemanticaGraphAdapter(graph_path, timeout_seconds=30)
            _sync_all(config, adapter)
            summary_before = get_student_learning_graph_summary(
                organization_id=1,
                task_id=31,
                student_id=101,
                subject_key="math",
            )
            graph_before = adapter.scoped_snapshot(
                organization_id=1, student_id=101, subject_key="math"
            )
            student_b = adapter.scoped_snapshot(
                organization_id=1, student_id=202, subject_key="math"
            )
            if student_b["nodes"] or student_b["edges"]:
                raise AssertionError("same-organization student isolation failed")
            event_books = sorted(
                item["curriculum"]["path"][0]["name"]
                for item in summary_before["timeline"]
            )
            if event_books != ["九年级上册", "九年级下册"]:
                raise AssertionError("events did not preserve their resolved book provenance")

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
                operation_id, runtime_config=config, adapter=adapter
            )
            replay_hash = adapter.scoped_snapshot(
                organization_id=1, student_id=101, subject_key="math"
            )["hash"]
            if replay_hash != graph_before["hash"]:
                raise AssertionError("multi-book event replay was not idempotent")

            graph_path.unlink()
            rebuilt = rebuild_semantica_graph(adapter)
            graph_after = adapter.scoped_snapshot(
                organization_id=1, student_id=101, subject_key="math"
            )
            summary_after = get_student_learning_graph_summary(
                organization_id=1,
                task_id=31,
                student_id=101,
                subject_key="math",
            )
            context_hash_before = content_hash(canonical_json(summary_before))
            context_hash_after = content_hash(canonical_json(summary_after))
            if graph_after["hash"] != graph_before["hash"]:
                raise AssertionError("multi-book Semantica rebuild hash changed")
            if context_hash_after != context_hash_before:
                raise AssertionError("canonical multi-book context hash changed")
            if integrity != "ok" or foreign_keys:
                raise AssertionError("temporary SQLite integrity check failed")

            print(
                canonical_json(
                    {
                        "semantica_version": adapter.health()["semantica_version"],
                        "grade_nine_books": actual_books,
                        "grade_nine_registry_count": sum(
                            int(item["knowledge_point_count"])
                            for item in grade_nine_scope["books"]
                        ),
                        "grade_seven_registry_count": grade_seven_registry[
                            "registry_metadata"
                        ]["count"],
                        "ambiguous_term": "比较数量",
                        "ambiguous_term_failed_closed": True,
                        "event_books": event_books,
                        "upper_event_ids": upper_result["event_ids"],
                        "lower_event_ids": lower_result["event_ids"],
                        "student_b_isolated": True,
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
