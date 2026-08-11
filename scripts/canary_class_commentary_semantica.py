#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import lesson_manager
from class_commentary_graph_jobs import (
    process_class_commentary_graph_extraction_job,
    process_class_commentary_graph_sync_operation,
)
from class_commentary_learning_graph import (
    canonical_json,
    content_hash,
    create_graph_extraction_job_conn,
    ensure_class_commentary_graph_schema,
    get_student_learning_graph_summary,
    list_dispatchable_graph_sync_operations,
    rebuild_semantica_graph,
)
from class_commentary_semantica import SemanticaGraphAdapter


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE organizations (id INTEGER PRIMARY KEY, status TEXT NOT NULL DEFAULT 'active');
        CREATE TABLE users (id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL);
        CREATE TABLE students (
            id INTEGER NOT NULL, organization_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            PRIMARY KEY(organization_id, id)
        );
        CREATE TABLE classes (id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, name TEXT NOT NULL);
        CREATE TABLE class_commentary_tasks (
            id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, class_id INTEGER NOT NULL,
            teacher_user_id INTEGER NOT NULL
        );
        CREATE TABLE class_commentary_generations (
            id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, task_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL, subject_key TEXT NOT NULL,
            attending_roster_snapshot_json TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE class_commentary_revisions (
            id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, task_id INTEGER NOT NULL,
            generation_id INTEGER NOT NULL, teacher_user_id INTEGER NOT NULL, revision_no INTEGER NOT NULL,
            confirmed_at TEXT NOT NULL, feedback_schema_version TEXT NOT NULL,
            structured_feedback_json TEXT NOT NULL, structured_feedback_hash TEXT NOT NULL,
            final_feedback_text TEXT NOT NULL, learn_requested INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE class_commentary_student_generation_runs (
            id INTEGER PRIMARY KEY, generation_id INTEGER NOT NULL, organization_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL
        );
        """
    )
    ensure_class_commentary_graph_schema(conn)


def _insert_scope(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    teacher_id: int,
    class_id: int,
    task_id: int,
    generation_id: int,
    class_name: str,
) -> None:
    conn.execute("INSERT OR IGNORE INTO organizations(id) VALUES (?)", (organization_id,))
    conn.execute(
        "INSERT OR IGNORE INTO users(id, organization_id) VALUES (?, ?)",
        (teacher_id, organization_id),
    )
    conn.execute(
        "INSERT INTO classes(id, organization_id, name) VALUES (?, ?, ?)",
        (class_id, organization_id, class_name),
    )
    conn.execute(
        "INSERT INTO class_commentary_tasks(id, organization_id, class_id, teacher_user_id) VALUES (?, ?, ?, ?)",
        (task_id, organization_id, class_id, teacher_id),
    )
    conn.execute(
        "INSERT INTO class_commentary_generations(id, organization_id, task_id, class_id, subject_key) VALUES (?, ?, ?, ?, 'math')",
        (generation_id, organization_id, task_id, class_id),
    )


def _create_revision_job(
    conn: sqlite3.Connection,
    *,
    revision_id: int,
    organization_id: int,
    task_id: int,
    generation_id: int,
    teacher_id: int,
    revision_no: int,
    student_id: int,
    feedback_text: str,
    confirmed_at: str,
) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO students(id, organization_id, status) VALUES (?, ?, 'active')",
        (student_id, organization_id),
    )
    structured = {
        "schema_version": "class_commentary.student_feedback.v1",
        "items": [{"student_id": student_id, "feedback_text": feedback_text}],
    }
    structured_json = canonical_json(structured)
    structured_hash = content_hash(structured_json)
    conn.execute(
        """
        INSERT INTO class_commentary_revisions (
            id, organization_id, task_id, generation_id, teacher_user_id, revision_no,
            confirmed_at, feedback_schema_version, structured_feedback_json,
            structured_feedback_hash, final_feedback_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'class_commentary.student_feedback.v1', ?, ?, ?)
        """,
        (
            revision_id,
            organization_id,
            task_id,
            generation_id,
            teacher_id,
            revision_no,
            confirmed_at,
            structured_json,
            structured_hash,
            feedback_text,
        ),
    )
    generation = dict(
        conn.execute("SELECT * FROM class_commentary_generations WHERE id=?", (generation_id,)).fetchone()
    )
    revision = dict(
        conn.execute("SELECT * FROM class_commentary_revisions WHERE id=?", (revision_id,)).fetchone()
    )
    return int(create_graph_extraction_job_conn(conn, generation, revision)["id"])


def _extractor(student_input: dict, _config: dict):
    text = student_input["feedback_text"]
    state = "developing" if "发展中" in text else "weak"
    trend = "improved" if "改善" in text else "new_observation"
    method = "图像与参数联动练习"
    next_step = "下一步练习参数变化" if "参数变化" in text else "下一步练习顶点与开口方向"
    return {
        "schema_version": "student_learning_event.v1",
        "items": [
            {
                "knowledge_point_key": "math.quadratic_function_graph",
                "unmapped_candidate": None,
                "observed_state": state,
                "reported_trend": trend,
                "evidence_quote": text,
                "evidence_start_offset": 0,
                "evidence_end_offset": len(text),
                "evidence_content_hash": hashlib.sha256(text.encode()).hexdigest(),
                "teaching_methods": [method],
                "next_steps": [next_step],
                "teaching_method_causal_supported": "帮助" in text,
                "teaching_method_causal_evidence": (
                    [
                        {
                            "method_text": method,
                            "evidence_quote": text,
                            "evidence_start_offset": 0,
                            "evidence_end_offset": len(text),
                            "evidence_content_hash": hashlib.sha256(text.encode()).hexdigest(),
                        }
                    ]
                    if "帮助" in text
                    else []
                ),
            }
        ],
    }


def _sync_all(config: dict, adapter: SemanticaGraphAdapter) -> None:
    while True:
        operations = list_dispatchable_graph_sync_operations(limit=100)
        if not operations:
            return
        for operation in operations:
            process_class_commentary_graph_sync_operation(
                int(operation["id"]), runtime_config=config, adapter=adapter
            )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="xingrun-semantica-canary-") as temp_dir:
        root = Path(temp_dir)
        db_path = root / "canary.sqlite3"
        graph_path = root / "canary-graph.json"
        lesson_manager.DB_PATH = db_path
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            _schema(conn)
            _insert_scope(
                conn,
                organization_id=1,
                teacher_id=11,
                class_id=21,
                task_id=31,
                generation_id=41,
                class_name="Canary A",
            )
            _insert_scope(
                conn,
                organization_id=1,
                teacher_id=11,
                class_id=25,
                task_id=35,
                generation_id=45,
                class_name="Canary A Later Lesson",
            )
            job_ids = [
                _create_revision_job(
                    conn,
                    revision_id=51,
                    organization_id=1,
                    task_id=31,
                    generation_id=41,
                    teacher_id=11,
                    revision_no=1,
                    student_id=101,
                    feedback_text="二次函数图像目前较薄弱，使用图像与参数联动练习。下一步练习顶点与开口方向。",
                    confirmed_at="2026-08-11T10:00:00Z",
                ),
                _create_revision_job(
                    conn,
                    revision_id=52,
                    organization_id=1,
                    task_id=35,
                    generation_id=45,
                    teacher_id=11,
                    revision_no=1,
                    student_id=101,
                    feedback_text="二次函数图像已有改善，当前正在发展中，使用图像与参数联动练习帮助理解。下一步练习参数变化。",
                    confirmed_at="2026-08-11T11:00:00Z",
                ),
                _create_revision_job(
                    conn,
                    revision_id=53,
                    organization_id=1,
                    task_id=31,
                    generation_id=41,
                    teacher_id=11,
                    revision_no=3,
                    student_id=202,
                    feedback_text="二次函数图像目前较薄弱，使用图像与参数联动练习。下一步练习顶点与开口方向。",
                    confirmed_at="2026-08-11T12:00:00Z",
                ),
            ]
            _insert_scope(
                conn,
                organization_id=2,
                teacher_id=12,
                class_id=22,
                task_id=32,
                generation_id=42,
                class_name="Canary Other Org",
            )
            job_ids.append(
                _create_revision_job(
                    conn,
                    revision_id=54,
                    organization_id=2,
                    task_id=32,
                    generation_id=42,
                    teacher_id=12,
                    revision_no=1,
                    student_id=101,
                    feedback_text="二次函数图像目前较薄弱，使用图像与参数联动练习。下一步练习顶点与开口方向。",
                    confirmed_at="2026-08-11T12:30:00Z",
                )
            )
            conn.commit()

        config = {
            "class_commentary_graph_enabled": True,
            "class_commentary_graph_store_path": str(graph_path),
            "class_commentary_graph_timeout": 10,
            "class_commentary_graph_extraction_timeout": 30,
            "class_commentary_graph_sync_timeout": 30,
            "class_commentary_provider": "canary",
            "class_commentary_model": "synthetic-no-provider-call",
        }
        for job_id in job_ids:
            process_class_commentary_graph_extraction_job(
                job_id,
                extractor=_extractor,
                dispatcher=lambda **_: {"enabled": True},
                runtime_config=config,
            )
        adapter = SemanticaGraphAdapter(graph_path)
        _sync_all(config, adapter)

        summary_before = get_student_learning_graph_summary(
            organization_id=1,
            task_id=31,
            student_id=101,
            subject_key="math",
        )
        states = [item["state"] for item in summary_before["timeline"]]
        assert states[:2] == ["weak", "developing"], states
        assert summary_before["timeline"][1]["previous_state"] == "weak"
        assert summary_before["timeline"][1]["trend"] == "improved"
        assert [
            item["evidence"]["revision_id"] for item in summary_before["timeline"][:2]
        ] == [51, 52]
        assert all(
            item["evidence"]["quote"]
            and content_hash(item["evidence"]["quote"])
            for item in summary_before["timeline"][:2]
        )
        assert all(item["teaching_methods"] for item in summary_before["timeline"][:2])
        assert all(item["next_steps"] for item in summary_before["timeline"][:2])
        with lesson_manager.get_conn() as conn:
            evidence_rows = conn.execute(
                """
                SELECT evidence.quote, evidence.content_hash, evidence.start_offset,
                       evidence.end_offset, evidence.revision_id,
                       revision.structured_feedback_json
                FROM class_commentary_learning_evidence AS evidence
                JOIN class_commentary_revisions AS revision ON revision.id=evidence.revision_id
                WHERE evidence.organization_id=1 AND evidence.student_id=101
                ORDER BY evidence.revision_id
                """
            ).fetchall()
        assert [int(row["revision_id"]) for row in evidence_rows] == [51, 52]
        assert all(content_hash(str(row["quote"])) == str(row["content_hash"]) for row in evidence_rows)
        assert all(
            str(row["quote"])
            in str(row["structured_feedback_json"])
            and int(row["end_offset"]) - int(row["start_offset"]) == len(str(row["quote"]))
            for row in evidence_rows
        )
        scoped_before = adapter.scoped_snapshot(
            organization_id=1, student_id=101, subject_key="math"
        )
        assert all(
            int((node.get("properties") or {}).get("student_id") or 101) == 101
            for node in scoped_before["nodes"]
        )
        assert all(
            (
                int((edge.get("metadata") or {}).get("organization_id") or 0),
                int((edge.get("metadata") or {}).get("student_id") or 0),
                str((edge.get("metadata") or {}).get("subject_key") or ""),
            )
            == (1, 101, "math")
            for edge in scoped_before["edges"]
        )
        edge_types = {str(edge["type"]) for edge in scoped_before["edges"]}
        assert {
            "SUPERSEDES",
            "IMPROVED_FROM",
            "TAUGHT_WITH",
            "LED_TO",
            "RECOMMENDS_NEXT",
        }.issubset(edge_types)
        student_b_snapshot = adapter.scoped_snapshot(
            organization_id=1, student_id=202, subject_key="math"
        )
        other_org_snapshot = adapter.scoped_snapshot(
            organization_id=2, student_id=101, subject_key="math"
        )
        assert student_b_snapshot["nodes"] and other_org_snapshot["nodes"]
        assert all(
            int((edge.get("metadata") or {}).get("student_id") or 0) == 202
            for edge in student_b_snapshot["edges"]
        )
        assert all(
            int((edge.get("metadata") or {}).get("organization_id") or 0) == 2
            for edge in other_org_snapshot["edges"]
        )

        with lesson_manager.get_conn() as conn:
            operation = conn.execute(
                "SELECT * FROM class_commentary_graph_sync_outbox ORDER BY id LIMIT 1"
            ).fetchone()
            conn.execute(
                "UPDATE class_commentary_graph_sync_outbox SET status='reconcile_needed' WHERE id=?",
                (int(operation["id"]),),
            )
        process_class_commentary_graph_sync_operation(
            int(operation["id"]), runtime_config=config, adapter=adapter
        )
        replay_snapshot = adapter.scoped_snapshot(
            organization_id=1, student_id=101, subject_key="math"
        )
        assert replay_snapshot["hash"] == scoped_before["hash"]

        graph_path.unlink()
        rebuild = rebuild_semantica_graph(adapter)
        scoped_after = adapter.scoped_snapshot(
            organization_id=1, student_id=101, subject_key="math"
        )
        summary_after = get_student_learning_graph_summary(
            organization_id=1,
            task_id=31,
            student_id=101,
            subject_key="math",
        )
        assert scoped_after["hash"] == scoped_before["hash"]
        assert content_hash(canonical_json(summary_after)) == content_hash(
            canonical_json(summary_before)
        )
        print(
            canonical_json(
                {
                    "semantica_version": adapter.health()["semantica_version"],
                    "states": states[:2],
                    "improved_from": True,
                    "evidence_count": len(summary_before["timeline"]),
                    "evidence_revision_ids": [51, 52],
                    "relationship_types_verified": sorted(edge_types),
                    "student_b_isolated": True,
                    "same_numeric_student_cross_org_isolated": True,
                    "idempotent_replay_hash": replay_snapshot["hash"],
                    "rebuild_hash": scoped_after["hash"],
                    "rebuild_event_count": rebuild["event_count"],
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
