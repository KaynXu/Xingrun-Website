from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Iterable, Mapping, Optional


GRAPH_EVENT_SCHEMA_VERSION = "student_learning_event.v1"
GRAPH_EXTRACTOR_VERSION = "class_commentary.learning_graph.extractor.v1"
GRAPH_PROMPT_VERSION = "class_commentary.learning_graph.prompt.v2"
GRAPH_REGISTRY_VERSION = 1
GRAPH_EXTRACTION_MAX_ATTEMPTS = 4
GRAPH_SYNC_MAX_ATTEMPTS = 8
GRAPH_EXTRACTION_RETRY_DELAYS = (30, 120, 600, 1800)
CLASS_CURRICULUM_SCOPE_SCHEMA_VERSION = "class_curriculum_assignment.v2"
LEARNING_STATES = ("unknown", "weak", "developing", "secure", "mastered")
LEARNING_TRENDS = ("new_observation", "regressed", "stable", "improved")
STATE_RANK = {value: index for index, value in enumerate(LEARNING_STATES)}

_BUILTIN_KNOWLEDGE_POINTS = (
    {
        "knowledge_point_key": "math.quadratic_function_graph",
        "subject_key": "math",
        "canonical_name": "二次函数图像",
        "aliases": ["二次函数图像", "二次函数的图像", "quadratic function graph"],
        "parent_key": None,
    },
    {
        "knowledge_point_key": "math.derivative_basics",
        "subject_key": "math",
        "canonical_name": "导数基础",
        "aliases": ["导数基础", "导数的基础", "derivative basics"],
        "parent_key": None,
    },
)


class LearningGraphValidationError(ValueError):
    pass


class LearningGraphRetryConflict(ValueError):
    pass


class LearningGraphSnapshotIntegrityError(ValueError):
    pass


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: object) -> str:
    text = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _graph_sync_payload_hash(payload: Mapping[str, object]) -> str:
    # Supersession is represented by the newer event's immutable
    # previous_event_id edges. These two lifecycle projection fields can
    # legitimately change after an older event's outbox row was created and
    # are not consumed by the Semantica adapter.
    immutable_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"desired_status", "superseded_by_event_id"}
    }
    desired_status = str(payload.get("desired_status") or "")
    immutable_payload["graph_deleted"] = desired_status == "deleted" or (
        desired_status == "superseded"
        and not str(payload.get("superseded_by_event_id") or "").strip()
    )
    return content_hash(immutable_payload)


def normalize_knowledge_point_alias(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(normalized.split()).casefold()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def graph_extraction_retry_delay(attempt_count: int) -> int:
    attempt_index = min(
        max(int(attempt_count) - 1, 0),
        len(GRAPH_EXTRACTION_RETRY_DELAYS) - 1,
    )
    return GRAPH_EXTRACTION_RETRY_DELAYS[attempt_index]


def graph_sync_retry_delay(attempt_count: int) -> int:
    return min(3600, 30 * (2 ** max(int(attempt_count) - 1, 0)))


def _conn():
    import lesson_manager

    return lesson_manager.get_conn()


def _json_object(value: object) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _json_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _positive_int_list(value: object) -> Optional[list[int]]:
    if not isinstance(value, list):
        return None
    result = []
    for item in value:
        try:
            normalized = int(item)
        except (TypeError, ValueError):
            return None
        if normalized <= 0 or normalized in result:
            return None
        result.append(normalized)
    return sorted(result)


def _curriculum_scope_v2_hash(assignment: Mapping[str, object]) -> str:
    return content_hash(
        {
            "schema_version": CLASS_CURRICULUM_SCOPE_SCHEMA_VERSION,
            "class_id": int(assignment.get("class_id") or 0),
            "organization_id": int(assignment.get("organization_id") or 0),
            "subject_key": str(assignment.get("subject_key") or ""),
            "assignment_mode": str(
                assignment.get("assignment_mode") or "needs_review"
            ),
            "inferred_grade_key": str(assignment.get("inferred_grade_key") or ""),
            "version_id": int(assignment.get("version_id") or 0),
            "book_node_ids": sorted(
                int(value) for value in assignment.get("book_node_ids") or []
            ),
            "assignment_ids": sorted(
                int(value) for value in assignment.get("assignment_ids") or []
            ),
            "primary_book_node_id": int(
                assignment.get("primary_book_node_id") or 0
            ),
        }
    )


def _frozen_curriculum_scope_valid(
    row: Mapping[str, object],
    assignment: Mapping[str, object],
    *,
    class_id: int,
    organization_id: int,
    subject_key: str,
    registry: Iterable[Mapping[str, object]],
) -> bool:
    schema_version = str(assignment.get("schema_version") or "")
    scalar_valid = (
        int(assignment.get("id") or 0)
        == int(row["curriculum_assignment_id"] or 0)
        and int(assignment.get("version_id") or 0)
        == int(row["curriculum_version_id"] or 0)
        and int(assignment.get("book_node_id") or 0)
        == int(row["curriculum_book_node_id"] or 0)
    )
    # Jobs created before multi-book scopes had no explicit snapshot schema.
    if schema_version == "":
        return scalar_valid
    if schema_version != CLASS_CURRICULUM_SCOPE_SCHEMA_VERSION or not scalar_valid:
        return False

    assignment_ids = _positive_int_list(assignment.get("assignment_ids"))
    book_ids = _positive_int_list(assignment.get("book_node_ids"))
    stored_assignment_ids = _positive_int_list(
        _json_list(row["curriculum_assignment_ids_snapshot_json"])
    )
    stored_book_ids = _positive_int_list(
        _json_list(row["curriculum_book_node_ids_snapshot_json"])
    )
    books = assignment.get("books")
    if (
        assignment_ids is None
        or book_ids is None
        or stored_assignment_ids is None
        or stored_book_ids is None
        or not isinstance(books, list)
        or not book_ids
        or assignment_ids != stored_assignment_ids
        or book_ids != stored_book_ids
        or int(assignment.get("class_id") or 0) != int(class_id)
        or int(assignment.get("organization_id") or 0) != int(organization_id)
        or str(assignment.get("subject_key") or "") != str(subject_key)
    ):
        return False

    book_rows = [dict(item) for item in books if isinstance(item, Mapping)]
    if len(book_rows) != len(books):
        return False
    books_book_ids = _positive_int_list(
        [int(item.get("book_node_id") or 0) for item in book_rows]
    )
    books_assignment_ids = _positive_int_list(
        [
            int(item.get("assignment_id") or 0)
            for item in book_rows
            if int(item.get("assignment_id") or 0)
        ]
    )
    primary_book_id = int(assignment.get("primary_book_node_id") or 0)
    if (
        books_book_ids != book_ids
        or books_assignment_ids != assignment_ids
        or primary_book_id not in book_ids
        or int(assignment.get("book_node_id") or 0) != primary_book_id
    ):
        return False
    primary_assignment_id = next(
        (
            int(item.get("assignment_id") or 0)
            for item in book_rows
            if int(item.get("book_node_id") or 0) == primary_book_id
        ),
        0,
    )
    if int(assignment.get("id") or 0) != primary_assignment_id:
        return False

    scope_hash = str(assignment.get("scope_hash") or "")
    if (
        not scope_hash
        or scope_hash != str(assignment.get("cas_token") or "")
        or scope_hash != str(row["curriculum_scope_hash"] or "")
        or scope_hash != _curriculum_scope_v2_hash(assignment)
    ):
        return False

    assigned_books = set(book_ids)
    for item in registry:
        item_book_ids = _positive_int_list(
            item.get("curriculum_book_node_ids")
            if isinstance(item, Mapping)
            else None
        )
        if item_book_ids is None:
            item_book_id = int(item.get("book_node_id") or 0)
            item_book_ids = [item_book_id] if item_book_id else []
        preferred_book_id = int(item.get("book_node_id") or 0)
        if (
            not item_book_ids
            or not set(item_book_ids).issubset(assigned_books)
            or preferred_book_id not in item_book_ids
        ):
            return False
    return True


def _frozen_assignment_id_for_book(
    assignment: Mapping[str, object], book_node_id: int
) -> int:
    if (
        str(assignment.get("schema_version") or "")
        != CLASS_CURRICULUM_SCOPE_SCHEMA_VERSION
    ):
        return int(assignment.get("id") or 0)
    for item in assignment.get("books") or []:
        if (
            isinstance(item, Mapping)
            and int(item.get("book_node_id") or 0) == int(book_node_id)
        ):
            return int(item.get("assignment_id") or 0)
    return 0


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def ensure_class_commentary_graph_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS class_commentary_knowledge_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            knowledge_point_key TEXT NOT NULL,
            subject_key TEXT NOT NULL,
            canonical_name TEXT NOT NULL,
            parent_key TEXT,
            registry_version INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(organization_id, knowledge_point_key),
            CHECK(active IN (0,1)),
            CHECK(registry_version >= 1),
            CHECK(knowledge_point_key<>''),
            CHECK(subject_key<>''),
            CHECK(canonical_name<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_knowledge_point_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            knowledge_point_id INTEGER NOT NULL REFERENCES class_commentary_knowledge_points(id) ON DELETE CASCADE,
            subject_key TEXT NOT NULL,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            registry_version INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(organization_id, subject_key, normalized_alias),
            CHECK(alias<>''),
            CHECK(normalized_alias<>''),
            CHECK(registry_version >= 1)
        );

        CREATE TABLE IF NOT EXISTS class_commentary_graph_extraction_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            revision_id INTEGER NOT NULL REFERENCES class_commentary_revisions(id) ON DELETE CASCADE,
            task_id INTEGER NOT NULL REFERENCES class_commentary_tasks(id) ON DELETE CASCADE,
            generation_id INTEGER NOT NULL REFERENCES class_commentary_generations(id) ON DELETE CASCADE,
            request_key TEXT NOT NULL,
            extractor_version TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            event_schema_version TEXT NOT NULL,
            registry_version INTEGER NOT NULL,
            extraction_input_hash TEXT NOT NULL,
            source_revision_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            claim_token TEXT,
            claim_owner TEXT,
            lease_until TEXT,
            rq_job_id TEXT,
            enqueued_at TEXT,
            next_attempt_at TEXT,
            last_error TEXT,
            result_summary_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            started_at TEXT,
            completed_at TEXT,
            UNIQUE(request_key),
            UNIQUE(revision_id, extractor_version, event_schema_version),
            CHECK(status IN ('queued','running','retry_wait','extracted','needs_mapping','failed','integrity_failed','obsolete')),
            CHECK(attempt_count >= 0 AND attempt_count <= 4),
            CHECK(request_key<>''),
            CHECK(extraction_input_hash<>''),
            CHECK(source_revision_hash<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_graph_extraction_student_checkpoints (
            extraction_job_id INTEGER NOT NULL REFERENCES class_commentary_graph_extraction_jobs(id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL,
            extraction_input_hash TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            usage_json TEXT NOT NULL DEFAULT '{}',
            checkpoint_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            PRIMARY KEY(extraction_job_id, student_id),
            CHECK(student_id > 0),
            CHECK(extraction_input_hash<>''),
            CHECK(payload_json<>''),
            CHECK(checkpoint_hash<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_graph_unmapped_candidates (
            candidate_id TEXT PRIMARY KEY,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            extraction_job_id INTEGER NOT NULL REFERENCES class_commentary_graph_extraction_jobs(id) ON DELETE CASCADE,
            revision_id INTEGER NOT NULL REFERENCES class_commentary_revisions(id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL,
            subject_key TEXT NOT NULL,
            candidate_text TEXT NOT NULL,
            normalized_candidate TEXT NOT NULL,
            evidence_quote TEXT NOT NULL,
            evidence_start_offset INTEGER NOT NULL,
            evidence_end_offset INTEGER NOT NULL,
            evidence_content_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            resolved_at TEXT,
            resolved_knowledge_point_key TEXT,
            UNIQUE(extraction_job_id, student_id, subject_key, normalized_candidate, evidence_content_hash),
            CHECK(status IN ('pending','mapped','dismissed')),
            CHECK(candidate_text<>''),
            CHECK(normalized_candidate<>''),
            CHECK(evidence_end_offset > evidence_start_offset)
        );

        CREATE TABLE IF NOT EXISTS class_commentary_graph_revision_scopes (
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            task_id INTEGER NOT NULL REFERENCES class_commentary_tasks(id) ON DELETE CASCADE,
            generation_id INTEGER NOT NULL REFERENCES class_commentary_generations(id) ON DELETE CASCADE,
            revision_id INTEGER NOT NULL REFERENCES class_commentary_revisions(id) ON DELETE CASCADE,
            revision_no INTEGER NOT NULL,
            extraction_job_id INTEGER NOT NULL REFERENCES class_commentary_graph_extraction_jobs(id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL,
            subject_key TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            PRIMARY KEY(revision_id, student_id, subject_key),
            CHECK(revision_no >= 1),
            CHECK(student_id > 0),
            CHECK(subject_key<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_student_learning_events (
            event_id TEXT PRIMARY KEY,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL,
            subject_key TEXT NOT NULL,
            lesson_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL REFERENCES class_commentary_tasks(id) ON DELETE CASCADE,
            generation_id INTEGER NOT NULL REFERENCES class_commentary_generations(id) ON DELETE CASCADE,
            revision_id INTEGER NOT NULL REFERENCES class_commentary_revisions(id) ON DELETE CASCADE,
            revision_no INTEGER NOT NULL,
            extraction_job_id INTEGER NOT NULL REFERENCES class_commentary_graph_extraction_jobs(id) ON DELETE CASCADE,
            knowledge_point_key TEXT NOT NULL,
            observed_state TEXT NOT NULL,
            reported_trend TEXT NOT NULL,
            state_before TEXT,
            previous_event_id TEXT REFERENCES class_commentary_student_learning_events(event_id),
            improved_from_trusted_state INTEGER NOT NULL DEFAULT 0,
            confirmed_teacher_user_id INTEGER NOT NULL REFERENCES users(id),
            confirmed_at TEXT NOT NULL,
            source_revision_hash TEXT NOT NULL,
            extractor_provider TEXT NOT NULL,
            extractor_model TEXT NOT NULL,
            extractor_prompt_version TEXT NOT NULL,
            event_schema_version TEXT NOT NULL,
            registry_version INTEGER NOT NULL,
            desired_status TEXT NOT NULL DEFAULT 'active',
            superseded_by_event_id TEXT REFERENCES class_commentary_student_learning_events(event_id),
            supersedes_event_id TEXT REFERENCES class_commentary_student_learning_events(event_id),
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(revision_id, student_id, subject_key, knowledge_point_key),
            CHECK(observed_state IN ('unknown','weak','developing','secure','mastered')),
            CHECK(reported_trend IN ('new_observation','regressed','stable','improved')),
            CHECK(state_before IS NULL OR state_before IN ('unknown','weak','developing','secure','mastered')),
            CHECK(improved_from_trusted_state IN (0,1)),
            CHECK(desired_status IN ('active','superseded','deleted')),
            CHECK(event_id<>''),
            CHECK(subject_key<>''),
            CHECK(knowledge_point_key<>''),
            CHECK(source_revision_hash<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_learning_evidence (
            evidence_id TEXT PRIMARY KEY,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            event_id TEXT NOT NULL REFERENCES class_commentary_student_learning_events(event_id) ON DELETE CASCADE,
            revision_id INTEGER NOT NULL REFERENCES class_commentary_revisions(id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL,
            subject_key TEXT NOT NULL,
            quote TEXT NOT NULL,
            start_offset INTEGER NOT NULL,
            end_offset INTEGER NOT NULL,
            content_hash TEXT NOT NULL,
            source_revision_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(event_id),
            CHECK(quote<>''),
            CHECK(end_offset > start_offset),
            CHECK(content_hash<>''),
            CHECK(source_revision_hash<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_learning_teaching_methods (
            method_id TEXT PRIMARY KEY,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            event_id TEXT NOT NULL REFERENCES class_commentary_student_learning_events(event_id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL,
            subject_key TEXT NOT NULL,
            method_text TEXT NOT NULL,
            causal_supported INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(event_id, method_text),
            CHECK(causal_supported IN (0,1)),
            CHECK(method_text<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_learning_next_steps (
            next_step_id TEXT PRIMARY KEY,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            event_id TEXT NOT NULL REFERENCES class_commentary_student_learning_events(event_id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL,
            subject_key TEXT NOT NULL,
            next_step_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(event_id, next_step_text),
            CHECK(status IN ('confirmed','completed','dismissed')),
            CHECK(next_step_text<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_learning_state_current (
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL,
            subject_key TEXT NOT NULL,
            knowledge_point_key TEXT NOT NULL,
            event_id TEXT NOT NULL REFERENCES class_commentary_student_learning_events(event_id) ON DELETE CASCADE,
            observed_state TEXT NOT NULL,
            confirmed_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            PRIMARY KEY(organization_id, student_id, subject_key, knowledge_point_key),
            CHECK(observed_state IN ('unknown','weak','developing','secure','mastered'))
        );

        CREATE TABLE IF NOT EXISTS class_commentary_graph_sync_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            event_id TEXT NOT NULL REFERENCES class_commentary_student_learning_events(event_id) ON DELETE CASCADE,
            operation_key TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            claim_token TEXT,
            claim_owner TEXT,
            lease_until TEXT,
            rq_job_id TEXT,
            enqueued_at TEXT,
            next_attempt_at TEXT,
            last_error TEXT,
            result_snapshot_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            applied_at TEXT,
            UNIQUE(operation_key),
            UNIQUE(event_id),
            CHECK(status IN ('pending','running','applied','retry_wait','reconcile_needed','failed','obsolete')),
            CHECK(attempt_count >= 0 AND attempt_count <= 8),
            CHECK(operation_key<>''),
            CHECK(payload_hash<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_graph_retry_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            revision_id INTEGER NOT NULL REFERENCES class_commentary_revisions(id) ON DELETE CASCADE,
            extraction_job_id INTEGER REFERENCES class_commentary_graph_extraction_jobs(id) ON DELETE SET NULL,
            request_id TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            actor_user_id INTEGER NOT NULL REFERENCES users(id),
            previous_state_snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(organization_id, revision_id, request_id),
            CHECK(request_id<>''),
            CHECK(payload_hash<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_graph_cleanup_requests (
            request_key TEXT PRIMARY KEY,
            organization_id INTEGER NOT NULL,
            student_id INTEGER,
            actor_user_id INTEGER,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            event_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            applied_at TEXT,
            CHECK(status IN ('pending','applied','failed')),
            CHECK(event_count >= 0),
            CHECK(reason<>'')
        );

        CREATE INDEX IF NOT EXISTS idx_class_commentary_graph_extraction_dispatch
        ON class_commentary_graph_extraction_jobs(status, next_attempt_at, created_at);
        CREATE INDEX IF NOT EXISTS idx_class_commentary_graph_sync_dispatch
        ON class_commentary_graph_sync_outbox(status, next_attempt_at, lease_until, created_at);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_class_commentary_graph_retry_request
        ON class_commentary_graph_retry_events(organization_id, request_id);
        CREATE INDEX IF NOT EXISTS idx_class_commentary_learning_event_scope
        ON class_commentary_student_learning_events(organization_id, student_id, subject_key, confirmed_at, event_id);
        CREATE INDEX IF NOT EXISTS idx_class_commentary_graph_unmapped_scope
        ON class_commentary_graph_unmapped_candidates(organization_id, student_id, subject_key, status);
        CREATE INDEX IF NOT EXISTS idx_class_commentary_graph_revision_scope
        ON class_commentary_graph_revision_scopes(
            organization_id, student_id, subject_key, task_id, revision_no
        );
        """
    )
    student_run_columns = {
        "graph_context_snapshot_json": "TEXT NOT NULL DEFAULT '{}'",
        "graph_context_hash": "TEXT NOT NULL DEFAULT ''",
        "graph_allowed_evidence_refs_json": "TEXT NOT NULL DEFAULT '[]'",
        "graph_retrieval_status": "TEXT NOT NULL DEFAULT 'pending'",
        "used_graph_evidence_refs_json": "TEXT NOT NULL DEFAULT '[]'",
    }
    for column, ddl in student_run_columns.items():
        _ensure_column(conn, "class_commentary_student_generation_runs", column, ddl)
    for column, ddl in {
        "used_graph_evidence_refs_by_student_json": "TEXT NOT NULL DEFAULT '{}'",
        "used_graph_evidence_refs_by_student_hash": "TEXT NOT NULL DEFAULT ''",
    }.items():
        _ensure_column(conn, "class_commentary_generations", column, ddl)
    _ensure_column(conn, "class_commentary_graph_extraction_jobs", "started_at", "TEXT")
    _ensure_column(conn, "class_commentary_graph_cleanup_requests", "actor_user_id", "INTEGER")
    _ensure_column(conn, "class_commentary_graph_sync_outbox", "payload_json", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(
        conn,
        "class_commentary_student_learning_events",
        "supersedes_event_id",
        "TEXT REFERENCES class_commentary_student_learning_events(event_id)",
    )
    for column, ddl in {
        "curriculum_assignment_id": "INTEGER",
        "curriculum_version_id": "INTEGER",
        "curriculum_book_node_id": "INTEGER",
        "curriculum_registry_snapshot_hash": "TEXT NOT NULL DEFAULT ''",
        "curriculum_registry_snapshot_json": "TEXT NOT NULL DEFAULT '[]'",
        "curriculum_content_hash": "TEXT NOT NULL DEFAULT ''",
        "curriculum_assignment_snapshot_json": "TEXT NOT NULL DEFAULT '{}'",
        "curriculum_assignment_ids_snapshot_json": "TEXT NOT NULL DEFAULT '[]'",
        "curriculum_book_node_ids_snapshot_json": "TEXT NOT NULL DEFAULT '[]'",
        "curriculum_scope_hash": "TEXT NOT NULL DEFAULT ''",
    }.items():
        _ensure_column(conn, "class_commentary_graph_extraction_jobs", column, ddl)
    for column, ddl in {
        "curriculum_assignment_id": "INTEGER",
        "curriculum_version_id": "INTEGER",
        "curriculum_node_id": "INTEGER",
        "organization_knowledge_point_id": "INTEGER",
        "curriculum_book_node_id": "INTEGER",
        "curriculum_package_key": "TEXT NOT NULL DEFAULT ''",
        "curriculum_version_key": "TEXT NOT NULL DEFAULT ''",
        "curriculum_source_revision": "TEXT NOT NULL DEFAULT ''",
        "curriculum_content_hash": "TEXT NOT NULL DEFAULT ''",
        "curriculum_node_content_hash": "TEXT NOT NULL DEFAULT ''",
        "knowledge_point_name_snapshot": "TEXT NOT NULL DEFAULT ''",
    }.items():
        _ensure_column(conn, "class_commentary_student_learning_events", column, ddl)
    _ensure_column(
        conn,
        "class_commentary_graph_unmapped_candidates",
        "candidate_payload_json",
        "TEXT NOT NULL DEFAULT '{}'",
    )
    _ensure_column(
        conn,
        "class_commentary_revisions",
        "graph_extraction_requested",
        "INTEGER NOT NULL DEFAULT 0 CHECK(graph_extraction_requested IN (0,1))",
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO class_commentary_graph_revision_scopes (
            organization_id, task_id, generation_id, revision_id, revision_no,
            extraction_job_id, student_id, subject_key
        )
        SELECT DISTINCT organization_id, task_id, generation_id, revision_id,
               revision_no, extraction_job_id, student_id, subject_key
        FROM class_commentary_student_learning_events
        """
    )


def register_knowledge_point(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    subject_key: str,
    knowledge_point_key: str,
    canonical_name: str,
    aliases: Iterable[str],
    parent_key: Optional[str] = None,
    registry_version: int = GRAPH_REGISTRY_VERSION,
    active: bool = True,
) -> dict:
    subject_key = str(subject_key).strip()
    knowledge_point_key = str(knowledge_point_key).strip()
    canonical_name = str(canonical_name).strip()
    if not subject_key or not knowledge_point_key or not canonical_name:
        raise ValueError("knowledge point identity is required")
    conn.execute(
        """
        INSERT INTO class_commentary_knowledge_points (
            organization_id, knowledge_point_key, subject_key, canonical_name,
            parent_key, registry_version, active
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(organization_id, knowledge_point_key) DO UPDATE SET
            subject_key=excluded.subject_key,
            canonical_name=excluded.canonical_name,
            parent_key=excluded.parent_key,
            registry_version=excluded.registry_version,
            active=excluded.active,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
        """,
        (
            int(organization_id),
            knowledge_point_key,
            subject_key,
            canonical_name,
            str(parent_key).strip() if parent_key else None,
            int(registry_version),
            1 if active else 0,
        ),
    )
    row = conn.execute(
        "SELECT * FROM class_commentary_knowledge_points WHERE organization_id=? AND knowledge_point_key=?",
        (int(organization_id), knowledge_point_key),
    ).fetchone()
    alias_values = [canonical_name, *list(aliases)]
    for alias in alias_values:
        alias_text = str(alias or "").strip()
        normalized = normalize_knowledge_point_alias(alias_text)
        if not alias_text or not normalized:
            continue
        conn.execute(
            """
            INSERT INTO class_commentary_knowledge_point_aliases (
                organization_id, knowledge_point_id, subject_key, alias,
                normalized_alias, registry_version
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(organization_id, subject_key, normalized_alias) DO UPDATE SET
                knowledge_point_id=excluded.knowledge_point_id,
                alias=excluded.alias,
                registry_version=excluded.registry_version
            """,
            (
                int(organization_id),
                int(row["id"]),
                subject_key,
                alias_text,
                normalized,
                int(registry_version),
            ),
        )
    return dict(row)


def ensure_builtin_knowledge_points(conn: sqlite3.Connection, organization_id: int) -> None:
    for item in _BUILTIN_KNOWLEDGE_POINTS:
        register_knowledge_point(conn, organization_id=int(organization_id), **item)


def resolve_knowledge_point(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    subject_key: str,
    value: object,
    class_id: Optional[int] = None,
) -> Optional[dict]:
    text = str(value or "").strip()
    if not text:
        return None
    if class_id is not None:
        from curriculum_registry import (
            get_class_curriculum_assignment,
            resolve_curriculum_knowledge_point,
        )

        curriculum_match = resolve_curriculum_knowledge_point(
            conn,
            organization_id=int(organization_id),
            class_id=int(class_id),
            subject_key=str(subject_key).strip(),
            value=text,
        )
        if curriculum_match:
            return curriculum_match
        if get_class_curriculum_assignment(conn, int(class_id)):
            return None
    row = conn.execute(
        """
        SELECT * FROM class_commentary_knowledge_points
        WHERE organization_id=? AND subject_key=? AND knowledge_point_key=? AND active=1
        """,
        (int(organization_id), str(subject_key).strip(), text),
    ).fetchone()
    if row:
        return dict(row)
    alias = conn.execute(
        """
        SELECT kp.*
        FROM class_commentary_knowledge_point_aliases AS alias
        JOIN class_commentary_knowledge_points AS kp ON kp.id=alias.knowledge_point_id
        WHERE alias.organization_id=? AND alias.subject_key=?
          AND alias.normalized_alias=? AND kp.active=1
        """,
        (
            int(organization_id),
            str(subject_key).strip(),
            normalize_knowledge_point_alias(text),
        ),
    ).fetchone()
    return dict(alias) if alias else None


def create_graph_extraction_job_conn(
    conn: sqlite3.Connection,
    generation: Mapping[str, object],
    revision: Mapping[str, object],
) -> dict:
    generation = dict(generation)
    revision = dict(revision)
    organization_id = int(generation["organization_id"])
    ensure_builtin_knowledge_points(conn, organization_id)
    from curriculum_registry import ensure_curriculum_schema, get_extraction_registry

    ensure_curriculum_schema(conn)
    curriculum_registry = get_extraction_registry(
        conn,
        organization_id=organization_id,
        class_id=int(generation["class_id"]),
        subject_key=str(generation.get("subject_key") or ""),
    )
    curriculum_assignment = curriculum_registry.get("assignment") or {}
    curriculum_items = curriculum_registry.get("registry") or []
    if curriculum_assignment:
        registry_snapshot = list(curriculum_items)
    else:
        registry_rows = conn.execute(
            """
            SELECT kp.knowledge_point_key, kp.subject_key, kp.canonical_name,
                   kp.parent_key, kp.registry_version,
                   COALESCE(json_group_array(alias.alias), '[]') AS aliases_json
            FROM class_commentary_knowledge_points AS kp
            LEFT JOIN class_commentary_knowledge_point_aliases AS alias
              ON alias.knowledge_point_id=kp.id
            WHERE kp.organization_id=? AND kp.subject_key=? AND kp.active=1
            GROUP BY kp.id ORDER BY kp.knowledge_point_key
            """,
            (organization_id, str(generation.get("subject_key") or "")),
        ).fetchall()
        registry_snapshot = [
            {
                "knowledge_point_key": item["knowledge_point_key"],
                "subject_key": item["subject_key"],
                "canonical_name": item["canonical_name"],
                "parent_key": item["parent_key"],
                "registry_version": item["registry_version"],
                "aliases": _json_list(item["aliases_json"]),
            }
            for item in registry_rows
        ]
    curriculum_snapshot_hash = content_hash(registry_snapshot)
    revision_id = int(revision["id"])
    task_id = int(revision["task_id"])
    generation_id = int(revision["generation_id"])
    source_revision_hash = str(revision.get("structured_feedback_hash") or "").strip()
    if not source_revision_hash:
        source_revision_hash = content_hash(str(revision.get("final_feedback_text") or ""))
    extraction_identity = {
        "revision_id": revision_id,
        "source_revision_hash": source_revision_hash,
        "extractor_version": GRAPH_EXTRACTOR_VERSION,
        "prompt_version": GRAPH_PROMPT_VERSION,
        "event_schema_version": GRAPH_EVENT_SCHEMA_VERSION,
        "registry_version": GRAPH_REGISTRY_VERSION,
        "curriculum_assignment_id": int(curriculum_assignment.get("id") or 0),
        "curriculum_version_id": int(curriculum_assignment.get("version_id") or 0),
        "curriculum_book_node_id": int(curriculum_assignment.get("book_node_id") or 0),
        "curriculum_assignment_ids": sorted(
            int(value) for value in curriculum_assignment.get("assignment_ids") or []
        ),
        "curriculum_book_node_ids": sorted(
            int(value) for value in curriculum_assignment.get("book_node_ids") or []
        ),
        "curriculum_scope_hash": str(curriculum_assignment.get("scope_hash") or ""),
        "curriculum_registry_snapshot_hash": curriculum_snapshot_hash,
        "curriculum_content_hash": str(curriculum_assignment.get("content_hash") or ""),
    }
    extraction_input_hash = content_hash(extraction_identity)
    request_key = f"class-commentary-graph-extract:{content_hash(extraction_identity)}"
    conn.execute(
        """
        INSERT OR IGNORE INTO class_commentary_graph_extraction_jobs (
            organization_id, revision_id, task_id, generation_id, request_key,
            extractor_version, prompt_version, event_schema_version,
            registry_version, extraction_input_hash, source_revision_hash,
            curriculum_assignment_id, curriculum_version_id,
            curriculum_book_node_id, curriculum_registry_snapshot_hash,
            curriculum_registry_snapshot_json, curriculum_content_hash,
            curriculum_assignment_snapshot_json,
            curriculum_assignment_ids_snapshot_json,
            curriculum_book_node_ids_snapshot_json, curriculum_scope_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id,
            revision_id,
            task_id,
            generation_id,
            request_key,
            GRAPH_EXTRACTOR_VERSION,
            GRAPH_PROMPT_VERSION,
            GRAPH_EVENT_SCHEMA_VERSION,
            GRAPH_REGISTRY_VERSION,
            extraction_input_hash,
            source_revision_hash,
            int(curriculum_assignment.get("id") or 0) or None,
            int(curriculum_assignment.get("version_id") or 0) or None,
            int(curriculum_assignment.get("book_node_id") or 0) or None,
            curriculum_snapshot_hash,
            canonical_json(registry_snapshot),
            str(curriculum_assignment.get("content_hash") or ""),
            canonical_json(curriculum_assignment),
            canonical_json(sorted(int(value) for value in curriculum_assignment.get("assignment_ids") or [])),
            canonical_json(sorted(int(value) for value in curriculum_assignment.get("book_node_ids") or [])),
            str(curriculum_assignment.get("scope_hash") or ""),
        ),
    )
    row = conn.execute(
        "SELECT * FROM class_commentary_graph_extraction_jobs WHERE request_key=?",
        (request_key,),
    ).fetchone()
    if not row:
        raise RuntimeError("graph extraction job was not created")
    return dict(row)


def get_graph_extraction_job_for_revision_conn(
    conn: sqlite3.Connection, revision_id: int
) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT * FROM class_commentary_graph_extraction_jobs
        WHERE revision_id=? ORDER BY id DESC LIMIT 1
        """,
        (int(revision_id),),
    ).fetchone()
    return dict(row) if row else None


def get_graph_extraction_job(job_id: int) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM class_commentary_graph_extraction_jobs WHERE id=?", (int(job_id),)
        ).fetchone()
    return dict(row) if row else None


def list_dispatchable_graph_extraction_jobs(limit: int = 100) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT job.*,
                   (
                       SELECT COUNT(*)
                       FROM class_commentary_graph_extraction_student_checkpoints checkpoint
                       WHERE checkpoint.extraction_job_id=job.id
                         AND checkpoint.extraction_input_hash=job.extraction_input_hash
                   ) AS checkpoint_count
            FROM class_commentary_graph_extraction_jobs job
            WHERE job.status='queued'
               OR (job.status='retry_wait' AND (job.next_attempt_at IS NULL OR job.next_attempt_at<=strftime('%Y-%m-%dT%H:%M:%fZ','now')))
            ORDER BY job.created_at, job.id LIMIT ?
            """,
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    return [dict(row) for row in rows]


def _graph_extraction_checkpoint_hash(
    *,
    job_id: int,
    student_id: int,
    extraction_input_hash: str,
    payload: Mapping[str, object],
    usage: Mapping[str, object],
) -> str:
    return content_hash(
        {
            "extraction_job_id": int(job_id),
            "student_id": int(student_id),
            "extraction_input_hash": str(extraction_input_hash),
            "payload": dict(payload),
            "usage": dict(usage),
        }
    )


def list_graph_extraction_student_checkpoints(
    job_id: int, *, extraction_input_hash: str
) -> list[dict]:
    expected_input_hash = str(extraction_input_hash or "")
    if not expected_input_hash:
        raise LearningGraphSnapshotIntegrityError(
            "graph extraction checkpoint input hash is missing"
        )
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM class_commentary_graph_extraction_student_checkpoints
            WHERE extraction_job_id=?
            ORDER BY student_id
            """,
            (int(job_id),),
        ).fetchall()
    checkpoints = []
    for row in rows:
        snapshot = dict(row)
        if str(snapshot.get("extraction_input_hash") or "") != expected_input_hash:
            raise LearningGraphSnapshotIntegrityError(
                "graph extraction checkpoint input hash mismatch"
            )
        try:
            payload = json.loads(str(snapshot.get("payload_json") or ""))
            usage = json.loads(str(snapshot.get("usage_json") or "{}"))
        except json.JSONDecodeError as exc:
            raise LearningGraphSnapshotIntegrityError(
                "graph extraction checkpoint JSON is invalid"
            ) from exc
        if not isinstance(payload, Mapping) or not isinstance(usage, Mapping):
            raise LearningGraphSnapshotIntegrityError(
                "graph extraction checkpoint payload is invalid"
            )
        expected_checkpoint_hash = _graph_extraction_checkpoint_hash(
            job_id=int(job_id),
            student_id=int(snapshot["student_id"]),
            extraction_input_hash=expected_input_hash,
            payload=payload,
            usage=usage,
        )
        if str(snapshot.get("checkpoint_hash") or "") != expected_checkpoint_hash:
            raise LearningGraphSnapshotIntegrityError(
                "graph extraction checkpoint hash mismatch"
            )
        checkpoints.append(
            {
                "student_id": int(snapshot["student_id"]),
                "payload": dict(payload),
                "usage": dict(usage),
                "checkpoint_hash": expected_checkpoint_hash,
            }
        )
    return checkpoints


def save_graph_extraction_student_checkpoint(
    job_id: int,
    *,
    claim_token: str,
    student_id: int,
    extraction_input_hash: str,
    payload: Mapping[str, object],
    usage: Optional[Mapping[str, object]] = None,
) -> dict:
    frozen = get_graph_extraction_input(int(job_id))
    expected_input_hash = str(extraction_input_hash or "")
    if (
        not frozen
        or frozen.get("integrity_valid") is not True
        or str(frozen.get("extraction_input_hash") or "") != expected_input_hash
    ):
        raise LearningGraphSnapshotIntegrityError(
            "graph extraction checkpoint input failed integrity"
        )
    frozen_student_ids = {
        int(item["student_id"])
        for item in frozen.get("student_feedback_items") or []
    }
    if int(student_id) not in frozen_student_ids:
        raise LearningGraphSnapshotIntegrityError(
            "graph extraction checkpoint student is outside frozen scope"
        )
    normalized_payload = dict(payload)
    normalized_usage = dict(usage or {})
    payload_json = canonical_json(normalized_payload)
    usage_json = canonical_json(normalized_usage)
    checkpoint_hash = _graph_extraction_checkpoint_hash(
        job_id=int(job_id),
        student_id=int(student_id),
        extraction_input_hash=expected_input_hash,
        payload=normalized_payload,
        usage=normalized_usage,
    )
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = conn.execute(
            "SELECT * FROM class_commentary_graph_extraction_jobs WHERE id=?",
            (int(job_id),),
        ).fetchone()
        if (
            not job
            or str(job["status"] or "") != "running"
            or str(job["claim_token"] or "") != str(claim_token)
            or str(job["extraction_input_hash"] or "") != expected_input_hash
        ):
            raise ValueError("graph extraction checkpoint claim is stale")
        conn.execute(
            """
            INSERT OR IGNORE INTO class_commentary_graph_extraction_student_checkpoints (
                extraction_job_id, student_id, extraction_input_hash,
                payload_json, usage_json, checkpoint_hash
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(job_id),
                int(student_id),
                expected_input_hash,
                payload_json,
                usage_json,
                checkpoint_hash,
            ),
        )
        row = conn.execute(
            """
            SELECT * FROM class_commentary_graph_extraction_student_checkpoints
            WHERE extraction_job_id=? AND student_id=?
            """,
            (int(job_id), int(student_id)),
        ).fetchone()
        if not row or str(row["checkpoint_hash"] or "") != checkpoint_hash:
            raise LearningGraphSnapshotIntegrityError(
                "graph extraction checkpoint conflicts with persisted state"
            )
    return {
        "student_id": int(student_id),
        "payload": normalized_payload,
        "usage": normalized_usage,
        "checkpoint_hash": checkpoint_hash,
    }


def continue_graph_extraction_job(
    job_id: int,
    *,
    claim_token: str,
    completed_student_count: int,
    total_student_count: int,
) -> dict:
    completed_count = int(completed_student_count)
    total_count = int(total_student_count)
    if completed_count <= 0 or completed_count >= total_count:
        raise ValueError("graph extraction continuation progress is invalid")
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = conn.execute(
            "SELECT * FROM class_commentary_graph_extraction_jobs WHERE id=?",
            (int(job_id),),
        ).fetchone()
        if (
            not job
            or str(job["status"] or "") != "running"
            or str(job["claim_token"] or "") != str(claim_token)
        ):
            raise ValueError("graph extraction continuation claim is stale")
        persisted_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM class_commentary_graph_extraction_student_checkpoints
                WHERE extraction_job_id=? AND extraction_input_hash=?
                """,
                (int(job_id), str(job["extraction_input_hash"])),
            ).fetchone()[0]
        )
        if persisted_count != completed_count:
            raise LearningGraphSnapshotIntegrityError(
                "graph extraction continuation checkpoint count mismatch"
            )
        result_summary = {
            "checkpointed_student_count": completed_count,
            "student_count": total_count,
        }
        conn.execute(
            """
            UPDATE class_commentary_graph_extraction_jobs
            SET status='queued', attempt_count=0, claim_token=NULL,
                claim_owner=NULL, lease_until=NULL, rq_job_id=NULL,
                enqueued_at=NULL, next_attempt_at=NULL, last_error=NULL,
                result_summary_json=?, completed_at=NULL,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=? AND claim_token=? AND status='running'
            """,
            (canonical_json(result_summary), int(job_id), str(claim_token)),
        )
        row = conn.execute(
            "SELECT * FROM class_commentary_graph_extraction_jobs WHERE id=?",
            (int(job_id),),
        ).fetchone()
    return dict(row)


def list_dispatchable_graph_sync_operations(limit: int = 100) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM class_commentary_graph_sync_outbox
            WHERE status IN ('pending','reconcile_needed')
               OR (status='retry_wait' AND (next_attempt_at IS NULL OR next_attempt_at<=strftime('%Y-%m-%dT%H:%M:%fZ','now')))
            ORDER BY created_at, id LIMIT ?
            """,
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    return [dict(row) for row in rows]


def mark_graph_job_enqueued(job_id: int, rq_job_id: str) -> None:
    with _conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_graph_extraction_jobs
            SET rq_job_id=?, enqueued_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=? AND status IN ('queued','retry_wait')
            """,
            (str(rq_job_id), int(job_id)),
        )


def mark_graph_sync_enqueued(operation_id: int, rq_job_id: str) -> None:
    with _conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_graph_sync_outbox
            SET rq_job_id=?, enqueued_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=? AND status IN ('pending','retry_wait','reconcile_needed')
            """,
            (str(rq_job_id), int(operation_id)),
        )


def claim_graph_extraction_job(
    job_id: int, *, claim_owner: str, rq_job_id: Optional[str] = None, lease_seconds: int = 600
) -> Optional[dict]:
    token = str(uuid.uuid4())
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        updated = conn.execute(
            """
            UPDATE class_commentary_graph_extraction_jobs
            SET status='running', attempt_count=attempt_count+1,
                claim_token=?, claim_owner=?, rq_job_id=COALESCE(?, rq_job_id),
                lease_until=strftime('%Y-%m-%dT%H:%M:%fZ','now', ?),
                started_at=COALESCE(started_at, strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=? AND attempt_count<? AND (
                status='queued' OR
                (status='retry_wait' AND (next_attempt_at IS NULL OR next_attempt_at<=strftime('%Y-%m-%dT%H:%M:%fZ','now')))
            )
            """,
            (
                token,
                str(claim_owner),
                rq_job_id,
                f"+{max(1, int(lease_seconds))} seconds",
                int(job_id),
                GRAPH_EXTRACTION_MAX_ATTEMPTS,
            ),
        )
        if updated.rowcount != 1:
            return None
        row = conn.execute(
            "SELECT * FROM class_commentary_graph_extraction_jobs WHERE id=?", (int(job_id),)
        ).fetchone()
    return dict(row)


def claim_graph_sync_operation(
    operation_id: int, *, claim_owner: str, rq_job_id: Optional[str] = None, lease_seconds: int = 300
) -> Optional[dict]:
    token = str(uuid.uuid4())
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        updated = conn.execute(
            """
            UPDATE class_commentary_graph_sync_outbox
            SET status='running', attempt_count=attempt_count+1,
                claim_token=?, claim_owner=?, rq_job_id=COALESCE(?, rq_job_id),
                lease_until=strftime('%Y-%m-%dT%H:%M:%fZ','now', ?),
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=? AND attempt_count<? AND (
                status IN ('pending','reconcile_needed') OR
                (status='retry_wait' AND (next_attempt_at IS NULL OR next_attempt_at<=strftime('%Y-%m-%dT%H:%M:%fZ','now')))
            )
            """,
            (
                token,
                str(claim_owner),
                rq_job_id,
                f"+{max(1, int(lease_seconds))} seconds",
                int(operation_id),
                GRAPH_SYNC_MAX_ATTEMPTS,
            ),
        )
        if updated.rowcount != 1:
            return None
        row = conn.execute(
            "SELECT * FROM class_commentary_graph_sync_outbox WHERE id=?", (int(operation_id),)
        ).fetchone()
    return dict(row)


def get_graph_extraction_input(job_id: int) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT job.*, revision.revision_no, revision.teacher_user_id,
                   revision.organization_id AS revision_organization_id,
                   revision.task_id AS revision_task_id,
                   revision.generation_id AS revision_generation_id,
                   revision.confirmed_at, revision.feedback_schema_version,
                   revision.structured_feedback_json, revision.structured_feedback_hash,
                   revision.final_feedback_text,
                   generation.organization_id AS generation_organization_id,
                   generation.task_id AS generation_task_id,
                   generation.subject_key,
                   generation.class_id, generation.attending_roster_snapshot_json,
                   task.organization_id AS task_organization_id,
                   task.class_id AS task_class_id,
                   class.organization_id AS class_organization_id,
                   class.name AS class_name
            FROM class_commentary_graph_extraction_jobs AS job
            JOIN class_commentary_revisions AS revision ON revision.id=job.revision_id
            JOIN class_commentary_generations AS generation ON generation.id=job.generation_id
            JOIN class_commentary_tasks AS task ON task.id=job.task_id
            JOIN classes AS class ON class.id=generation.class_id
            WHERE job.id=?
            """,
            (int(job_id),),
        ).fetchone()
        if not row:
            return None
        ensure_builtin_knowledge_points(conn, int(row["organization_id"]))
        from curriculum_registry import ensure_curriculum_schema

        ensure_curriculum_schema(conn)
        frozen_registry = _json_list(row["curriculum_registry_snapshot_json"])
        frozen_version = None
        if int(row["curriculum_version_id"] or 0):
            frozen_version = conn.execute(
                """
                SELECT version.content_hash, version.version_key,
                       version.source_dataset_revision, version.source_sha256,
                       package.package_key
                FROM curriculum_versions version
                JOIN curriculum_packages package ON package.id=version.package_id
                WHERE version.id=?
                """,
                (int(row["curriculum_version_id"]),),
            ).fetchone()
    structured = _json_object(row["structured_feedback_json"])
    items = structured.get("items") if isinstance(structured.get("items"), list) else []
    safe_items = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        try:
            student_id = int(item.get("student_id"))
        except (TypeError, ValueError):
            continue
        feedback_text = str(item.get("feedback_text") or "")
        if student_id > 0 and feedback_text.strip():
            safe_items.append({"student_id": student_id, "feedback_text": feedback_text})
    result = dict(row)
    result["student_feedback_items"] = safe_items
    result["registry"] = frozen_registry
    alias_owners: dict[str, set[str]] = {}
    for item in frozen_registry:
        if not isinstance(item, Mapping):
            continue
        key = str(item.get("knowledge_point_key") or "")
        for value in [item.get("canonical_name"), *(item.get("aliases") or [])]:
            normalized = normalize_knowledge_point_alias(value)
            if normalized:
                alias_owners.setdefault(normalized, set()).add(key)
    compact_registry = []
    ambiguous_keys = {
        key
        for owners in alias_owners.values()
        if len(owners) != 1
        for key in owners
    }
    for item in frozen_registry:
        if not isinstance(item, Mapping):
            continue
        canonical_name = str(item.get("canonical_name") or "")
        canonical_normalized = normalize_knowledge_point_alias(canonical_name)
        if (
            str(item.get("knowledge_point_key") or "") in ambiguous_keys
            or len(alias_owners.get(canonical_normalized, set())) != 1
        ):
            continue
        compact_registry.append(
            {
                "knowledge_point_key": str(item.get("knowledge_point_key") or ""),
                "canonical_name": canonical_name,
                "aliases": [
                    str(alias)
                    for alias in item.get("aliases") or []
                    if len(
                        alias_owners.get(normalize_knowledge_point_alias(alias), set())
                    ) == 1
                ],
            }
        )
    result["model_registry"] = compact_registry
    frozen_assignment = _json_object(row["curriculum_assignment_snapshot_json"])
    result["curriculum_assignment"] = frozen_assignment or None
    if isinstance(frozen_assignment, Mapping):
        org_scope_book_ids = {
            int(value)
            for value in (frozen_assignment.get("book_node_ids") or [])
            if value
        } or {int(frozen_assignment.get("book_node_id") or 0)}
        org_scope_book_ids.discard(0)
        if org_scope_book_ids:
            placeholders = ",".join("?" for _ in org_scope_book_ids)
            try:
                with _conn() as conn:
                    org_rows = conn.execute(
                        f"""
                        SELECT knowledge_point_key, canonical_name
                        FROM curriculum_organization_knowledge_points
                        WHERE organization_id=? AND version_id=?
                          AND book_node_id IN ({placeholders})
                          AND subject_key=? AND status='active'
                        ORDER BY knowledge_point_key
                        """,
                        (
                            int(row["organization_id"] or 0),
                            int(frozen_assignment.get("version_id") or 0),
                            *sorted(org_scope_book_ids),
                            str(frozen_assignment.get("subject_key") or ""),
                        ),
                    ).fetchall()
            except sqlite3.OperationalError:
                org_rows = []
            existing_keys = {
                str(item["knowledge_point_key"]) for item in result["model_registry"]
            }
            for item in org_rows:
                key = str(item["knowledge_point_key"])
                if key in existing_keys:
                    continue
                result["model_registry"].append(
                    {
                        "knowledge_point_key": key,
                        "canonical_name": str(item["canonical_name"] or ""),
                        "aliases": [],
                    }
                )
    result["lesson_id"] = int(row["task_id"])
    result["lesson_name"] = f"{str(row['class_name'] or '').strip()} 课堂反馈".strip()
    identity_scope_valid = (
        int(row["revision_organization_id"] or 0)
        == int(row["organization_id"] or 0)
        == int(row["generation_organization_id"] or 0)
        == int(row["task_organization_id"] or 0)
        == int(row["class_organization_id"] or 0)
        and int(row["revision_task_id"] or 0) == int(row["task_id"] or 0)
        and int(row["generation_task_id"] or 0) == int(row["task_id"] or 0)
        and int(row["task_class_id"] or 0) == int(row["class_id"] or 0)
        and int(row["revision_generation_id"] or 0)
        == int(row["generation_id"] or 0)
    )
    scope_valid = _frozen_curriculum_scope_valid(
        row,
        frozen_assignment,
        class_id=int(row["class_id"]),
        organization_id=int(row["organization_id"]),
        subject_key=str(row["subject_key"] or ""),
        registry=frozen_registry,
    )
    result["integrity_valid"] = (
        str(row["source_revision_hash"])
        == (str(row["structured_feedback_hash"] or "") or content_hash(str(row["final_feedback_text"] or "")))
        and str(row["curriculum_registry_snapshot_hash"] or "") == content_hash(frozen_registry)
        and identity_scope_valid
        and scope_valid
        and (
            not int(row["curriculum_version_id"] or 0)
            or (
                frozen_version is not None
                and str(frozen_version["content_hash"] or "")
                == str(row["curriculum_content_hash"] or "")
            )
        )
    )
    return result


def _validated_quote(candidate: Mapping[str, object], feedback_text: str) -> tuple[str, int, int, str]:
    quote = str(candidate.get("evidence_quote") or "")
    try:
        start = int(candidate.get("evidence_start_offset"))
        end = int(candidate.get("evidence_end_offset"))
    except (TypeError, ValueError) as exc:
        raise LearningGraphValidationError("evidence offsets are invalid") from exc
    if not quote or start < 0 or end <= start or end > len(feedback_text):
        raise LearningGraphValidationError("evidence span is invalid")
    if feedback_text[start:end] != quote:
        raise LearningGraphValidationError("evidence quote does not match confirmed feedback")
    quote_hash = content_hash(quote)
    supplied_hash = str(candidate.get("evidence_content_hash") or "")
    if not supplied_hash or supplied_hash != quote_hash:
        raise LearningGraphValidationError("evidence content hash mismatch")
    return quote, start, end, quote_hash


def _resolve_frozen_knowledge_point(
    conn: sqlite3.Connection,
    *,
    frozen: Mapping[str, object],
    value: object,
    allow_active_organization_target: bool = False,
    require_model_eligible: bool = False,
) -> Optional[dict]:
    text = str(value or "").strip()
    if not text:
        return None
    registry = [dict(item) for item in frozen.get("registry") or [] if isinstance(item, Mapping)]
    exact = [item for item in registry if str(item.get("knowledge_point_key") or "") == text]
    if not exact:
        normalized = normalize_knowledge_point_alias(text)
        exact = [
            item
            for item in registry
            if normalized
            and normalized
            in {
                normalize_knowledge_point_alias(item.get("canonical_name")),
                *(normalize_knowledge_point_alias(alias) for alias in item.get("aliases") or []),
            }
        ]
    assignment = frozen.get("curriculum_assignment")
    unique = {str(item.get("knowledge_point_key") or ""): item for item in exact}
    if require_model_eligible and unique:
        eligible_keys = {
            str(item.get("knowledge_point_key") or "")
            for item in frozen.get("model_registry") or []
            if isinstance(item, Mapping)
        }
        unique = {key: item for key, item in unique.items() if key in eligible_keys}
    if not unique and allow_active_organization_target and isinstance(assignment, Mapping):
        assigned_book_ids = {
            int(value) for value in assignment.get("book_node_ids") or []
        } or {int(assignment.get("book_node_id") or 0)}
        assigned_book_ids.discard(0)
        if not assigned_book_ids:
            raise LearningGraphValidationError("frozen curriculum book scope is invalid")
        placeholders = ",".join("?" for _ in assigned_book_ids)
        custom = conn.execute(
            f"""
            SELECT * FROM curriculum_organization_knowledge_points
            WHERE organization_id=? AND version_id=?
              AND book_node_id IN ({placeholders})
              AND subject_key=? AND knowledge_point_key=? AND status='active'
            """,
            (
                int(assignment.get("organization_id") or 0),
                int(assignment.get("version_id") or 0),
                *sorted(assigned_book_ids),
                str(assignment.get("subject_key") or ""),
                text,
            ),
        ).fetchone()
        if custom:
            custom_snapshot = {
                "knowledge_point_key": str(custom["knowledge_point_key"]),
                "canonical_name": str(custom["canonical_name"]),
                "registry_version": int(assignment.get("stable_registry_version") or 0),
                "curriculum_node_id": 0,
                "organization_knowledge_point_id": int(custom["id"]),
                "book_node_id": int(custom["book_node_id"]),
                "node_content_hash": content_hash(
                    {
                        "knowledge_point_key": custom["knowledge_point_key"],
                        "canonical_name": custom["canonical_name"],
                        "description": custom["description"],
                    }
                ),
            }
            unique[str(custom["knowledge_point_key"])] = custom_snapshot
    if len(unique) != 1:
        return None
    snapshot = dict(next(iter(unique.values())))
    if not isinstance(assignment, Mapping):
        snapshot["registry_version"] = int(snapshot.get("registry_version") or GRAPH_REGISTRY_VERSION)
        return snapshot
    if int(snapshot.get("organization_knowledge_point_id") or 0):
        snapshot_book_id = int(snapshot.get("book_node_id") or 0)
        if not snapshot_book_id and (
            str(assignment.get("schema_version") or "")
            != CLASS_CURRICULUM_SCOPE_SCHEMA_VERSION
        ):
            snapshot_book_id = int(assignment.get("book_node_id") or 0)
        assigned_book_ids = {
            int(value) for value in assignment.get("book_node_ids") or []
        } or {int(assignment.get("book_node_id") or 0)}
        if snapshot_book_id not in assigned_book_ids:
            raise LearningGraphValidationError("frozen curriculum book scope is invalid")
        result = dict(snapshot)
        result.update(
            {
                "curriculum_version_id": int(assignment.get("version_id") or 0),
                "book_node_id": snapshot_book_id,
                "curriculum_content_hash": str(assignment.get("content_hash") or ""),
            }
        )
        return result
    node_id = int(snapshot.get("curriculum_node_id") or 0)
    snapshot_book_ids = _positive_int_list(snapshot.get("curriculum_book_node_ids"))
    snapshot_book_id = int(snapshot.get("book_node_id") or 0)
    if not snapshot_book_id and snapshot_book_ids and len(snapshot_book_ids) == 1:
        snapshot_book_id = snapshot_book_ids[0]
    if not snapshot_book_id and (
        str(assignment.get("schema_version") or "")
        != CLASS_CURRICULUM_SCOPE_SCHEMA_VERSION
    ):
        snapshot_book_id = int(assignment.get("book_node_id") or 0)
    assigned_book_ids = {
        int(value) for value in assignment.get("book_node_ids") or []
    } or {int(assignment.get("book_node_id") or 0)}
    if (
        snapshot_book_id not in assigned_book_ids
        or (
            snapshot_book_ids is not None
            and not set(snapshot_book_ids).issubset(assigned_book_ids)
        )
    ):
        raise LearningGraphValidationError("frozen curriculum book scope is invalid")
    row = conn.execute(
        """
        SELECT node.* FROM curriculum_nodes node
        JOIN curriculum_book_nodes membership ON membership.node_id=node.id
          AND membership.version_id=node.version_id
        WHERE node.id=? AND node.version_id=? AND node.node_key=?
          AND membership.book_node_id=?
          AND membership.membership_type='appears_in'
          AND node.node_type IN ('Concept','Skill')
        """,
        (
            node_id,
            int(assignment.get("version_id") or 0),
            str(snapshot.get("knowledge_point_key") or ""),
            snapshot_book_id,
        ),
    ).fetchone()
    if not row:
        raise LearningGraphValidationError("frozen curriculum knowledge point is unavailable")
    result = dict(row)
    result.update(
        {
            "knowledge_point_key": str(snapshot["knowledge_point_key"]),
            "canonical_name": str(snapshot["canonical_name"]),
            "registry_version": int(assignment.get("stable_registry_version") or 0),
            "curriculum_node_id": node_id,
            "curriculum_version_id": int(assignment.get("version_id") or 0),
            "book_node_id": snapshot_book_id,
            "curriculum_content_hash": str(assignment.get("content_hash") or ""),
            "node_content_hash": str(snapshot.get("node_content_hash") or ""),
        }
    )
    return result


def _supported_texts(raw_values: object, feedback_text: str, *, limit: int) -> list[str]:
    if not isinstance(raw_values, list):
        return []
    result = []
    for value in raw_values[:limit]:
        text = str(value.get("text") if isinstance(value, Mapping) else value).strip()
        if text and text in feedback_text and text not in result:
            result.append(text)
    return result


def _method_causal_supported(
    method: str,
    quote: str,
    *,
    requested: bool,
    knowledge_point_name: str,
    observed_state: str,
    reported_trend: str,
) -> bool:
    if not requested or not method or method not in quote:
        return False
    causal_pattern = re.compile(
        rf"{re.escape(method)}\s*(?:后|的使用|练习)?\s*(?:直接)?"
        r"(?:帮助|促进|使得|使|让|导致|带来|led\s+to|resulted\s+in)",
        re.IGNORECASE,
    )
    match = causal_pattern.search(quote)
    if match is None:
        return False
    outcome_text = quote[match.end() :].casefold()
    outcome_clause = re.split(r"[，,。.!?！？；;]", outcome_text, maxsplit=1)[0].strip()
    if not outcome_clause or re.match(
        r"^(?:老师|教师|家长|系统|平台|管理员|配置|设置|工具|我们|本人)",
        outcome_clause,
    ):
        return False
    state_markers = {
        "unknown": ("状态", "表现"),
        "weak": ("薄弱", "较弱", "weak"),
        "developing": ("发展中", "逐步", "developing"),
        "secure": ("稳固", "稳定掌握", "secure"),
        "mastered": ("熟练掌握", "精通", "mastered"),
    }.get(str(observed_state), ())
    trend_markers = {
        "new_observation": ("表现", "状态"),
        "regressed": ("退步", "下降", "regressed"),
        "stable": ("稳定", "保持", "stable"),
        "improved": ("改善", "提升", "进步", "improved"),
    }.get(str(reported_trend), ())
    learning_markers = tuple(
        marker.casefold()
        for marker in (
            "理解",
            "掌握",
            "表现",
            "状态",
            *state_markers,
            *trend_markers,
        )
        if marker
    )
    direct_learning_outcome = re.match(
        r"^(?:(?:学生|该生|孩子|学员|他|她)(?:的)?\s*)?"
        r"(?:(?:已经|已|正在|逐步|明显|更|更加|更好地|进一步|开始|"
        r"能够|可以|基本|较好地|稳定地|熟练地)\s*)*"
        r"(?:理解|掌握|表现|状态)",
        outcome_clause,
    )
    knowledge_point = str(knowledge_point_name or "").strip().casefold()
    return bool(direct_learning_outcome) or bool(
        knowledge_point
        and knowledge_point in outcome_clause
        and any(marker in outcome_clause for marker in learning_markers)
    )


def _validated_method_causal_quotes(
    candidate: Mapping[str, object],
    feedback_text: str,
) -> dict[str, str]:
    if not bool(candidate.get("teaching_method_causal_supported")):
        return {}
    raw_items = candidate.get("teaching_method_causal_evidence")
    if not isinstance(raw_items, list):
        raise LearningGraphValidationError("teaching method causal evidence is invalid")
    result: dict[str, str] = {}
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            raise LearningGraphValidationError("teaching method causal evidence is invalid")
        method_text = str(raw_item.get("method_text") or "").strip()
        if not method_text:
            raise LearningGraphValidationError("teaching method causal evidence is invalid")
        quote, _, _, _ = _validated_quote(raw_item, feedback_text)
        if method_text not in quote or method_text in result:
            raise LearningGraphValidationError("teaching method causal evidence is invalid")
        result[method_text] = quote
    return result


def _reproject_learning_state_conn(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    student_id: int,
    subject_key: str,
    knowledge_point_key: str,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT * FROM class_commentary_student_learning_events
        WHERE organization_id=? AND student_id=? AND subject_key=?
          AND knowledge_point_key=? AND desired_status<>'deleted'
        ORDER BY confirmed_at, revision_no, event_id
        """,
        (int(organization_id), int(student_id), str(subject_key), str(knowledge_point_key)),
    ).fetchall()
    if not rows:
        conn.execute(
            """
            DELETE FROM class_commentary_learning_state_current
            WHERE organization_id=? AND student_id=? AND subject_key=? AND knowledge_point_key=?
            """,
            (int(organization_id), int(student_id), str(subject_key), str(knowledge_point_key)),
        )
        return []
    event_ids = [str(row["event_id"]) for row in rows]
    rows_by_task: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        rows_by_task.setdefault(int(row["task_id"]), []).append(row)
    previous = None
    for index, row in enumerate(rows):
        next_row = rows[index + 1] if index + 1 < len(rows) else None
        correction_candidates = [
            candidate
            for candidate in rows_by_task.get(int(row["task_id"]), [])
            if int(candidate["revision_no"]) < int(row["revision_no"])
        ]
        correction_previous = correction_candidates[-1] if correction_candidates else None
        state_before = str(previous["observed_state"]) if previous is not None else None
        previous_event_id = str(previous["event_id"]) if previous is not None else None
        improved_from = bool(
            previous is not None
            and str(row["reported_trend"]) == "improved"
            and STATE_RANK[str(row["observed_state"])]
            > STATE_RANK[str(previous["observed_state"])]
        )
        conn.execute(
            """
            UPDATE class_commentary_student_learning_events
            SET desired_status=?, superseded_by_event_id=?,
                state_before=?, previous_event_id=?, improved_from_trusted_state=?,
                supersedes_event_id=?
            WHERE event_id=?
            """,
            (
                "superseded" if next_row is not None else "active",
                str(next_row["event_id"]) if next_row is not None else None,
                state_before,
                previous_event_id,
                1 if improved_from else 0,
                str(correction_previous["event_id"]) if correction_previous else None,
                str(row["event_id"]),
            ),
        )
        previous = row
    latest = rows[-1]
    conn.execute(
        """
        INSERT INTO class_commentary_learning_state_current (
            organization_id, student_id, subject_key, knowledge_point_key,
            event_id, observed_state, confirmed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(organization_id, student_id, subject_key, knowledge_point_key)
        DO UPDATE SET event_id=excluded.event_id,
                      observed_state=excluded.observed_state,
                      confirmed_at=excluded.confirmed_at,
                      updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
        """,
        (
            int(organization_id),
            int(student_id),
            str(subject_key),
            str(knowledge_point_key),
            str(latest["event_id"]),
            str(latest["observed_state"]),
            str(latest["confirmed_at"]),
        ),
    )
    return event_ids


def _student_graph_scope_active_conn(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    student_id: int,
) -> bool:
    organization = conn.execute(
        "SELECT status FROM organizations WHERE id=?",
        (int(organization_id),),
    ).fetchone()
    student = conn.execute(
        "SELECT organization_id, status FROM students WHERE id=? AND organization_id=?",
        (int(student_id), int(organization_id)),
    ).fetchone()
    if (
        not organization
        or str(organization["status"] or "") != "active"
        or not student
        or int(student["organization_id"] or 0) != int(organization_id)
        or str(student["status"] or "") != "active"
    ):
        return False
    cleanup = conn.execute(
        """
        SELECT 1 FROM class_commentary_graph_cleanup_requests
        WHERE organization_id=? AND (student_id IS NULL OR student_id=?)
        LIMIT 1
        """,
        (int(organization_id), int(student_id)),
    ).fetchone()
    return cleanup is None


def commit_graph_extraction(
    job_id: int,
    *,
    claim_token: str,
    candidates_by_student: Iterable[Mapping[str, object]],
    extractor_provider: str,
    extractor_model: str,
    usage: Optional[Mapping[str, object]] = None,
    allow_active_organization_targets: bool = False,
    require_model_eligible: Optional[bool] = None,
) -> dict:
    frozen = get_graph_extraction_input(int(job_id))
    if not frozen or not frozen.get("integrity_valid"):
        raise LearningGraphValidationError("graph extraction input failed integrity")
    feedback_by_student = {
        int(item["student_id"]): str(item["feedback_text"])
        for item in frozen["student_feedback_items"]
    }
    normalized_candidates = [dict(item) for item in candidates_by_student if isinstance(item, Mapping)]
    trusted_events = []
    unmapped = []
    touched_projections = set()
    seen_trusted_observations = set()
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = conn.execute(
            "SELECT * FROM class_commentary_graph_extraction_jobs WHERE id=?",
            (int(job_id),),
        ).fetchone()
        if not job or str(job["status"]) != "running" or str(job["claim_token"]) != str(claim_token):
            raise ValueError("graph extraction claim is stale")
        subject_key = str(frozen.get("subject_key") or "").strip()
        active_feedback_by_student = {
            student_id: feedback_text
            for student_id, feedback_text in feedback_by_student.items()
            if _student_graph_scope_active_conn(
                conn,
                organization_id=int(job["organization_id"]),
                student_id=student_id,
            )
        }
        inactive_student_ids = sorted(
            set(feedback_by_student).difference(active_feedback_by_student)
        )
        if not active_feedback_by_student:
            result_summary = {
                "trusted_event_count": 0,
                "unmapped_candidate_count": 0,
                "obsolete_student_ids": inactive_student_ids,
                "usage": dict(usage or {}),
            }
            conn.execute(
                """
                UPDATE class_commentary_graph_extraction_jobs
                SET status='obsolete', result_summary_json=?, claim_token=NULL,
                    claim_owner=NULL, lease_until=NULL,
                    last_error='graph extraction scope is no longer active',
                    completed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                    updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                WHERE id=? AND claim_token=? AND status='running'
                """,
                (canonical_json(result_summary), int(job_id), str(claim_token)),
            )
            return {
                "status": "obsolete",
                "event_ids": [],
                "unmapped_candidate_ids": [],
            }
        for student_id in sorted(active_feedback_by_student):
            conn.execute(
                """
                INSERT OR IGNORE INTO class_commentary_graph_revision_scopes (
                    organization_id, task_id, generation_id, revision_id,
                    revision_no, extraction_job_id, student_id, subject_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(job["organization_id"]),
                    int(job["task_id"]),
                    int(job["generation_id"]),
                    int(job["revision_id"]),
                    int(frozen["revision_no"]),
                    int(job_id),
                    int(student_id),
                    subject_key,
                ),
            )
            existing_kps = conn.execute(
                """
                SELECT DISTINCT knowledge_point_key
                FROM class_commentary_student_learning_events
                WHERE organization_id=? AND task_id=? AND student_id=?
                  AND subject_key=? AND desired_status<>'deleted'
                """,
                (
                    int(job["organization_id"]),
                    int(job["task_id"]),
                    int(student_id),
                    subject_key,
                ),
            ).fetchall()
            touched_projections.update(
                (
                    int(job["organization_id"]),
                    int(student_id),
                    subject_key,
                    str(row["knowledge_point_key"]),
                )
                for row in existing_kps
            )
        for candidate in normalized_candidates:
            try:
                student_id = int(candidate.get("student_id"))
            except (TypeError, ValueError):
                continue
            feedback_text = active_feedback_by_student.get(student_id)
            if feedback_text is None:
                continue
            quote, start, end, quote_hash = _validated_quote(candidate, feedback_text)
            raw_kp = candidate.get("knowledge_point_key")
            raw_unmapped = candidate.get("unmapped_candidate")
            resolved = _resolve_frozen_knowledge_point(
                conn,
                frozen=frozen,
                value=raw_kp or raw_unmapped,
                allow_active_organization_target=allow_active_organization_targets,
                require_model_eligible=(
                    require_model_eligible
                    if require_model_eligible is not None
                    else not allow_active_organization_targets
                ),
            )
            if not resolved:
                candidate_text = str(raw_unmapped or raw_kp or "").strip()
                if not candidate_text:
                    continue
                candidate_id = content_hash(
                    [job_id, student_id, subject_key, normalize_knowledge_point_alias(candidate_text), quote_hash]
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO class_commentary_graph_unmapped_candidates (
                        candidate_id, organization_id, extraction_job_id, revision_id,
                        student_id, subject_key, candidate_text, normalized_candidate,
                        evidence_quote, evidence_start_offset, evidence_end_offset,
                        evidence_content_hash, candidate_payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate_id,
                        int(job["organization_id"]),
                        int(job_id),
                        int(job["revision_id"]),
                        student_id,
                        subject_key,
                        candidate_text,
                        normalize_knowledge_point_alias(candidate_text),
                        quote,
                        start,
                        end,
                        quote_hash,
                        canonical_json(candidate),
                    ),
                )
                unmapped.append(candidate_id)
                continue
            state = str(candidate.get("observed_state") or "").strip()
            trend = str(candidate.get("reported_trend") or "new_observation").strip()
            if state not in LEARNING_STATES or trend not in LEARNING_TRENDS:
                raise LearningGraphValidationError("learning state or trend is invalid")
            kp_key = str(resolved["knowledge_point_key"])
            observation_key = (student_id, subject_key, kp_key)
            if observation_key in seen_trusted_observations:
                raise LearningGraphValidationError(
                    "duplicate knowledge point observation for confirmed revision"
                )
            seen_trusted_observations.add(observation_key)
            curriculum_assignment = frozen.get("curriculum_assignment") or {}
            resolved_book_id = int(resolved.get("book_node_id") or 0)
            resolved_assignment_id = _frozen_assignment_id_for_book(
                curriculum_assignment, resolved_book_id
            )
            if (
                str(curriculum_assignment.get("schema_version") or "")
                == CLASS_CURRICULUM_SCOPE_SCHEMA_VERSION
                and not resolved_assignment_id
                and curriculum_assignment.get("assignment_ids")
            ):
                raise LearningGraphValidationError(
                    "frozen curriculum assignment scope is invalid"
                )
            event_identity = {
                "schema_version": GRAPH_EVENT_SCHEMA_VERSION,
                "organization_id": int(job["organization_id"]),
                "student_id": student_id,
                "subject_key": subject_key,
                "revision_id": int(job["revision_id"]),
                "knowledge_point_key": kp_key,
                "observed_state": state,
                "evidence_content_hash": quote_hash,
            }
            event_id = content_hash(event_identity)
            conn.execute(
                """
                INSERT OR IGNORE INTO class_commentary_student_learning_events (
                    event_id, organization_id, student_id, subject_key, lesson_id,
                    task_id, generation_id, revision_id, revision_no, extraction_job_id,
                    knowledge_point_key, observed_state, reported_trend, state_before,
                    previous_event_id, improved_from_trusted_state,
                    confirmed_teacher_user_id, confirmed_at, source_revision_hash,
                    extractor_provider, extractor_model, extractor_prompt_version,
                    event_schema_version, registry_version, curriculum_assignment_id,
                    curriculum_version_id, curriculum_node_id,
                    organization_knowledge_point_id, curriculum_book_node_id,
                    curriculum_package_key, curriculum_version_key,
                    curriculum_source_revision, curriculum_content_hash,
                    curriculum_node_content_hash, knowledge_point_name_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    int(job["organization_id"]),
                    student_id,
                    subject_key,
                    int(frozen["lesson_id"]),
                    int(job["task_id"]),
                    int(job["generation_id"]),
                    int(job["revision_id"]),
                    int(frozen["revision_no"]),
                    int(job_id),
                    kp_key,
                    state,
                    trend,
                    None,
                    None,
                    0,
                    int(frozen["teacher_user_id"]),
                    str(frozen["confirmed_at"]),
                    str(job["source_revision_hash"]),
                    str(extractor_provider),
                    str(extractor_model),
                    str(job["prompt_version"]),
                    str(job["event_schema_version"]),
                    int(resolved["registry_version"]),
                    resolved_assignment_id or None,
                    int(resolved.get("curriculum_version_id") or 0) or None,
                    int(resolved.get("curriculum_node_id") or 0) or None,
                    int(resolved.get("organization_knowledge_point_id") or 0) or None,
                    resolved_book_id or int(job["curriculum_book_node_id"] or 0) or None,
                    str((frozen.get("curriculum_assignment") or {}).get("package_key") or ""),
                    str((frozen.get("curriculum_assignment") or {}).get("version_key") or ""),
                    str((frozen.get("curriculum_assignment") or {}).get("source_dataset_revision") or ""),
                    str(resolved.get("curriculum_content_hash") or ""),
                    str(resolved.get("node_content_hash") or ""),
                    str(resolved["canonical_name"]),
                ),
            )
            evidence_id = content_hash(["evidence", event_id, quote_hash, start, end])
            conn.execute(
                """
                INSERT OR IGNORE INTO class_commentary_learning_evidence (
                    evidence_id, organization_id, event_id, revision_id, student_id,
                    subject_key, quote, start_offset, end_offset, content_hash,
                    source_revision_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    int(job["organization_id"]),
                    event_id,
                    int(job["revision_id"]),
                    student_id,
                    subject_key,
                    quote,
                    start,
                    end,
                    quote_hash,
                    str(job["source_revision_hash"]),
                ),
            )
            methods = _supported_texts(candidate.get("teaching_methods"), feedback_text, limit=8)
            causal_requested = bool(candidate.get("teaching_method_causal_supported"))
            causal_quotes = _validated_method_causal_quotes(candidate, feedback_text)
            if causal_requested and set(causal_quotes).difference(methods):
                raise LearningGraphValidationError(
                    "causal evidence references an unsupported teaching method"
                )
            for method in methods:
                method_id = content_hash(["method", event_id, method])
                causal_supported = _method_causal_supported(
                    method,
                    causal_quotes.get(method, ""),
                    requested=causal_requested and method in causal_quotes,
                    knowledge_point_name=str(resolved["canonical_name"]),
                    observed_state=state,
                    reported_trend=trend,
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO class_commentary_learning_teaching_methods (
                        method_id, organization_id, event_id, student_id, subject_key,
                        method_text, causal_supported
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (method_id, int(job["organization_id"]), event_id, student_id, subject_key, method, 1 if causal_supported else 0),
                )
            next_steps = _supported_texts(candidate.get("next_steps"), feedback_text, limit=8)
            for next_step in next_steps:
                next_step_id = content_hash(["next-step", event_id, next_step])
                conn.execute(
                    """
                    INSERT OR IGNORE INTO class_commentary_learning_next_steps (
                        next_step_id, organization_id, event_id, student_id,
                        subject_key, next_step_text
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (next_step_id, int(job["organization_id"]), event_id, student_id, subject_key, next_step),
                )
            touched_projections.add(
                (int(job["organization_id"]), student_id, subject_key, kp_key)
            )
            trusted_events.append(event_id)
        sync_event_ids = set(trusted_events)
        for organization_id, student_id, subject_key, kp_key in sorted(touched_projections):
            sync_event_ids.update(
                _reproject_learning_state_conn(
                    conn,
                    organization_id=organization_id,
                    student_id=student_id,
                    subject_key=subject_key,
                    knowledge_point_key=kp_key,
                )
            )
        for event_id in sorted(sync_event_ids):
            payload = _graph_event_payload_conn(conn, event_id)
            operation_key = f"class-commentary-graph-sync:{event_id}"
            payload_hash = _graph_sync_payload_hash(payload)
            conn.execute(
                """
                INSERT INTO class_commentary_graph_sync_outbox (
                    organization_id, event_id, operation_key, payload_json, payload_hash
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    status=CASE
                        WHEN class_commentary_graph_sync_outbox.payload_hash<>excluded.payload_hash
                        THEN 'reconcile_needed'
                        ELSE class_commentary_graph_sync_outbox.status
                    END,
                    payload_json=excluded.payload_json,
                    payload_hash=excluded.payload_hash,
                    claim_token=CASE
                        WHEN class_commentary_graph_sync_outbox.payload_hash<>excluded.payload_hash
                        THEN NULL ELSE class_commentary_graph_sync_outbox.claim_token END,
                    claim_owner=CASE
                        WHEN class_commentary_graph_sync_outbox.payload_hash<>excluded.payload_hash
                        THEN NULL ELSE class_commentary_graph_sync_outbox.claim_owner END,
                    lease_until=CASE
                        WHEN class_commentary_graph_sync_outbox.payload_hash<>excluded.payload_hash
                        THEN NULL ELSE class_commentary_graph_sync_outbox.lease_until END,
                    next_attempt_at=CASE
                        WHEN class_commentary_graph_sync_outbox.payload_hash<>excluded.payload_hash
                        THEN NULL ELSE class_commentary_graph_sync_outbox.next_attempt_at END,
                    last_error=CASE
                        WHEN class_commentary_graph_sync_outbox.payload_hash<>excluded.payload_hash
                        THEN NULL ELSE class_commentary_graph_sync_outbox.last_error END,
                    updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                """,
                (
                    int(job["organization_id"]),
                    event_id,
                    operation_key,
                    canonical_json(payload),
                    payload_hash,
                ),
            )
        pending_unmapped_rows = conn.execute(
            """
            SELECT candidate_id FROM class_commentary_graph_unmapped_candidates
            WHERE extraction_job_id=? AND status='pending' ORDER BY candidate_id
            """,
            (int(job_id),),
        ).fetchall()
        pending_unmapped = [str(row["candidate_id"]) for row in pending_unmapped_rows]
        status = "needs_mapping" if pending_unmapped else "extracted"
        result_summary = {
            "trusted_event_count": len(set(trusted_events)),
            "unmapped_candidate_count": len(set(pending_unmapped)),
            "unsafe_unstructured_revision": not bool(feedback_by_student),
            "obsolete_student_ids": inactive_student_ids,
            "usage": dict(usage or {}),
        }
        conn.execute(
            """
            UPDATE class_commentary_graph_extraction_jobs
            SET status=?, result_summary_json=?, claim_token=NULL, claim_owner=NULL,
                lease_until=NULL, last_error=NULL,
                completed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=? AND claim_token=? AND status='running'
            """,
            (status, canonical_json(result_summary), int(job_id), str(claim_token)),
        )
    return {
        "status": status,
        "event_ids": sorted(set(trusted_events)),
        "unmapped_candidate_ids": sorted(set(pending_unmapped)),
    }


def mark_graph_extraction_integrity_failed(job_id: int, *, claim_token: str, error: str) -> None:
    with _conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_graph_extraction_jobs
            SET status='integrity_failed', last_error=?, claim_token=NULL,
                claim_owner=NULL, lease_until=NULL,
                completed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=? AND claim_token=? AND status='running'
            """,
            (str(error)[:1000], int(job_id), str(claim_token)),
        )


def fail_graph_extraction_job(job_id: int, *, claim_token: str, error: str) -> dict:
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = conn.execute(
            "SELECT * FROM class_commentary_graph_extraction_jobs WHERE id=?", (int(job_id),)
        ).fetchone()
        if not job or str(job["claim_token"] or "") != str(claim_token):
            raise ValueError("graph extraction claim is stale")
        retryable = int(job["attempt_count"]) < GRAPH_EXTRACTION_MAX_ATTEMPTS
        delay = graph_extraction_retry_delay(int(job["attempt_count"]))
        status = "retry_wait" if retryable else "failed"
        conn.execute(
            """
            UPDATE class_commentary_graph_extraction_jobs
            SET status=?, last_error=?, claim_token=NULL, claim_owner=NULL,
                lease_until=NULL,
                next_attempt_at=CASE WHEN ?='retry_wait' THEN strftime('%Y-%m-%dT%H:%M:%fZ','now', ?) ELSE NULL END,
                completed_at=CASE WHEN ?='failed' THEN strftime('%Y-%m-%dT%H:%M:%fZ','now') ELSE NULL END,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=?
            """,
            (status, str(error)[:1000], status, f"+{delay} seconds", status, int(job_id)),
        )
        row = conn.execute(
            "SELECT * FROM class_commentary_graph_extraction_jobs WHERE id=?", (int(job_id),)
        ).fetchone()
    return dict(row)


def _curriculum_context_for_event_conn(
    conn: sqlite3.Connection, event: Mapping[str, object]
) -> Optional[dict]:
    from curriculum_registry import (
        curriculum_context_for_organization_knowledge_point,
        get_curriculum_node_detail,
    )

    curriculum_node_id = int(event.get("curriculum_node_id") or 0)
    book_node_id = int(event.get("curriculum_book_node_id") or 0)
    if curriculum_node_id:
        detail = get_curriculum_node_detail(
            conn,
            curriculum_node_id,
            book_node_id=book_node_id or None,
        )
        if not detail:
            return None
        return {
            "curriculum_node_id": curriculum_node_id,
            "organization_knowledge_point_id": None,
            "knowledge_point_key": str(detail["node_key"]),
            "knowledge_point_kind": str(detail["node_type"]),
            "path": detail["path"],
            "prerequisites": detail["relations"]["prerequisites"],
            "follow_ups": detail["relations"]["follow_ups"],
            "related": detail["relations"]["related"],
            "source": {
                "package_key": str(detail["package_key"]),
                "version_key": str(detail["version_key"]),
                "dataset_revision": str(detail["source_dataset_revision"]),
                "source_sha256": str(detail["source_sha256"]),
                "content_hash": str(event.get("curriculum_content_hash") or ""),
                "license": str(detail["data_license"]),
            },
        }
    organization_knowledge_point_id = int(
        event.get("organization_knowledge_point_id") or 0
    )
    if not organization_knowledge_point_id or not book_node_id:
        return None
    return curriculum_context_for_organization_knowledge_point(
        conn,
        organization_id=int(event.get("organization_id") or 0),
        organization_knowledge_point_id=organization_knowledge_point_id,
        book_node_id=book_node_id,
    )


def _graph_event_payload_conn(conn: sqlite3.Connection, event_id: str) -> dict:
    row = conn.execute(
        """
        SELECT event.*, evidence.evidence_id, evidence.quote AS evidence_quote,
               evidence.start_offset AS evidence_start_offset,
               evidence.end_offset AS evidence_end_offset,
               evidence.content_hash AS evidence_content_hash,
               COALESCE(NULLIF(event.knowledge_point_name_snapshot,''),
                        curriculum_kp.canonical_name, kp.canonical_name,
                        event.knowledge_point_key) AS knowledge_point_name,
               class.name AS class_name
        FROM class_commentary_student_learning_events AS event
        JOIN class_commentary_learning_evidence AS evidence ON evidence.event_id=event.event_id
        LEFT JOIN class_commentary_knowledge_points AS kp
          ON kp.organization_id=event.organization_id
         AND kp.knowledge_point_key=event.knowledge_point_key
        LEFT JOIN curriculum_nodes AS curriculum_kp
          ON curriculum_kp.id=event.curriculum_node_id
        JOIN class_commentary_generations AS generation ON generation.id=event.generation_id
        JOIN classes AS class ON class.id=generation.class_id
        WHERE event.event_id=?
        """,
        (str(event_id),),
    ).fetchone()
    if not row:
        raise ValueError("learning event not found")
    methods = conn.execute(
        "SELECT method_text AS text, causal_supported FROM class_commentary_learning_teaching_methods WHERE event_id=? ORDER BY method_id",
        (str(event_id),),
    ).fetchall()
    next_steps = conn.execute(
        "SELECT next_step_text AS text, status FROM class_commentary_learning_next_steps WHERE event_id=? ORDER BY next_step_id",
        (str(event_id),),
    ).fetchall()
    payload = dict(row)
    payload["lesson_name"] = f"{str(row['class_name'] or '').strip()} 课堂反馈".strip()
    payload["teaching_methods"] = [dict(item) for item in methods]
    payload["next_steps"] = [dict(item) for item in next_steps]
    payload["curriculum_context"] = _curriculum_context_for_event_conn(conn, payload)
    supersedes_event_id = str(row["supersedes_event_id"] or "").strip()
    if supersedes_event_id:
        supersedes = conn.execute(
            "SELECT observed_state FROM class_commentary_student_learning_events WHERE event_id=?",
            (supersedes_event_id,),
        ).fetchone()
        if not supersedes:
            raise ValueError("superseded learning event not found")
        payload["supersedes_state"] = str(supersedes["observed_state"])
    return payload


def get_graph_sync_payload(operation_id: int) -> Optional[dict]:
    with _conn() as conn:
        operation = conn.execute(
            "SELECT * FROM class_commentary_graph_sync_outbox WHERE id=?", (int(operation_id),)
        ).fetchone()
        if not operation:
            return None
        payload = _json_object(operation["payload_json"])
    result = dict(operation)
    result["event"] = payload
    result["integrity_valid"] = str(operation["payload_hash"]) == _graph_sync_payload_hash(payload)
    return result


def complete_graph_sync_operation(
    operation_id: int, *, claim_token: str, result_snapshot: Mapping[str, object]
) -> dict:
    with _conn() as conn:
        updated = conn.execute(
            """
            UPDATE class_commentary_graph_sync_outbox
            SET status='applied', result_snapshot_json=?, claim_token=NULL,
                claim_owner=NULL, lease_until=NULL, last_error=NULL,
                applied_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=? AND claim_token=? AND status='running'
            """,
            (canonical_json(dict(result_snapshot)), int(operation_id), str(claim_token)),
        )
        if updated.rowcount != 1:
            raise ValueError("graph sync claim is stale")
        row = conn.execute(
            "SELECT * FROM class_commentary_graph_sync_outbox WHERE id=?", (int(operation_id),)
        ).fetchone()
        conn.execute(
            """
            UPDATE class_commentary_graph_cleanup_requests AS cleanup
            SET status='applied', last_error=NULL,
                applied_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE cleanup.status='pending'
              AND NOT EXISTS (
                  SELECT 1
                  FROM class_commentary_student_learning_events AS event
                  JOIN class_commentary_graph_sync_outbox AS outbox
                    ON outbox.event_id=event.event_id
                  WHERE event.organization_id=cleanup.organization_id
                    AND (cleanup.student_id IS NULL OR event.student_id=cleanup.student_id)
                    AND event.desired_status='deleted'
                    AND outbox.status<>'applied'
              )
            """
        )
    return dict(row)


def fail_graph_sync_operation(operation_id: int, *, claim_token: str, error: str) -> dict:
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        operation = conn.execute(
            "SELECT * FROM class_commentary_graph_sync_outbox WHERE id=?", (int(operation_id),)
        ).fetchone()
        if not operation or str(operation["claim_token"] or "") != str(claim_token):
            raise ValueError("graph sync claim is stale")
        retryable = int(operation["attempt_count"]) < GRAPH_SYNC_MAX_ATTEMPTS
        delay = graph_sync_retry_delay(int(operation["attempt_count"]))
        status = "retry_wait" if retryable else "failed"
        conn.execute(
            """
            UPDATE class_commentary_graph_sync_outbox
            SET status=?, last_error=?, claim_token=NULL, claim_owner=NULL,
                lease_until=NULL,
                next_attempt_at=CASE WHEN ?='retry_wait' THEN strftime('%Y-%m-%dT%H:%M:%fZ','now', ?) ELSE NULL END,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=?
            """,
            (status, str(error)[:1000], status, f"+{delay} seconds", int(operation_id)),
        )
        if status == "failed":
            conn.execute(
                """
                UPDATE class_commentary_graph_cleanup_requests AS cleanup
                SET status='failed', last_error=?,
                    updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                WHERE cleanup.status='pending'
                  AND EXISTS (
                      SELECT 1
                      FROM class_commentary_student_learning_events AS event
                      WHERE event.event_id=?
                        AND event.desired_status='deleted'
                        AND event.organization_id=cleanup.organization_id
                        AND (cleanup.student_id IS NULL OR event.student_id=cleanup.student_id)
                  )
                """,
                (str(error)[:1000], str(operation["event_id"])),
            )
        row = conn.execute(
            "SELECT * FROM class_commentary_graph_sync_outbox WHERE id=?", (int(operation_id),)
        ).fetchone()
    return dict(row)


def _list_trusted_graph_events_conn(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT event_id FROM class_commentary_student_learning_events
        WHERE desired_status<>'deleted'
        ORDER BY confirmed_at, revision_no, event_id
        """
    ).fetchall()
    return [_graph_event_payload_conn(conn, str(row["event_id"])) for row in rows]


def list_trusted_graph_events() -> list[dict]:
    with _conn() as conn:
        return _list_trusted_graph_events_conn(conn)


def _semantica_curriculum_snapshot_conn(conn: sqlite3.Connection) -> dict:
    from curriculum_registry import build_semantica_curriculum_snapshot

    return build_semantica_curriculum_snapshot(conn)


def get_semantica_curriculum_snapshot() -> dict:
    with _conn() as conn:
        return _semantica_curriculum_snapshot_conn(conn)


def rebuild_semantica_graph(adapter) -> dict:
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        events = _list_trusted_graph_events_conn(conn)
        curriculum_snapshot = _semantica_curriculum_snapshot_conn(conn)
        result = adapter.rebuild(
            events,
            curriculum_snapshot=curriculum_snapshot,
        )
        result["curriculum_node_count"] = int(curriculum_snapshot["node_count"])
        result["curriculum_edge_count"] = int(curriculum_snapshot["edge_count"])
        result["curriculum_content_hash"] = str(curriculum_snapshot["content_hash"])
        conn.execute(
            """
            UPDATE class_commentary_graph_sync_outbox
            SET status='applied', claim_token=NULL, claim_owner=NULL, lease_until=NULL,
                last_error=NULL, applied_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE event_id IN (
                SELECT event_id FROM class_commentary_student_learning_events
            )
              AND status<>'running'
            """
        )
        conn.execute(
            """
            UPDATE class_commentary_graph_cleanup_requests AS cleanup
            SET status='applied', last_error=NULL,
                applied_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE cleanup.status IN ('pending','failed')
              AND NOT EXISTS (
                  SELECT 1
                  FROM class_commentary_student_learning_events AS event
                  JOIN class_commentary_graph_sync_outbox AS outbox
                    ON outbox.event_id=event.event_id
                  WHERE event.organization_id=cleanup.organization_id
                    AND (cleanup.student_id IS NULL OR event.student_id=cleanup.student_id)
                    AND event.desired_status='deleted'
                    AND outbox.status<>'applied'
              )
            """
        )
    return result


def prepare_graph_cleanup_for_scope_conn(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    student_id: Optional[int] = None,
    actor_user_id: Optional[int] = None,
    reason: str,
) -> dict:
    organization_id = int(organization_id)
    scoped_student_id = int(student_id) if student_id is not None else None
    scoped_actor_user_id = int(actor_user_id) if actor_user_id is not None else None
    reason = str(reason or "").strip()
    if organization_id <= 0 or not reason:
        raise ValueError("graph cleanup scope and reason are required")
    params: list[object] = [organization_id]
    student_sql = ""
    if scoped_student_id is not None:
        student_sql = " AND student_id=?"
        params.append(scoped_student_id)
    rows = conn.execute(
        f"""
        SELECT event_id FROM class_commentary_student_learning_events
        WHERE organization_id=?{student_sql} AND desired_status<>'deleted'
        ORDER BY event_id
        """,
        tuple(params),
    ).fetchall()
    event_ids = [str(row["event_id"]) for row in rows]
    request_key = "class-commentary-graph-cleanup:" + content_hash(
        [organization_id, scoped_student_id or "*", reason]
    )
    status = "pending" if event_ids else "applied"
    conn.execute(
        """
        INSERT INTO class_commentary_graph_cleanup_requests (
            request_key, organization_id, student_id, actor_user_id, reason, status,
            event_count, applied_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CASE WHEN ?='applied' THEN strftime('%Y-%m-%dT%H:%M:%fZ','now') END)
        ON CONFLICT(request_key) DO UPDATE SET
            actor_user_id=COALESCE(excluded.actor_user_id, class_commentary_graph_cleanup_requests.actor_user_id),
            status=excluded.status,
            event_count=excluded.event_count,
            last_error=NULL,
            applied_at=excluded.applied_at,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
        """,
        (
            request_key,
            organization_id,
            scoped_student_id,
            scoped_actor_user_id,
            reason,
            status,
            len(event_ids),
            status,
        ),
    )
    if not event_ids:
        return {"request_key": request_key, "operation_ids": [], "event_count": 0}
    placeholders = ",".join("?" for _ in event_ids)
    conn.execute(
        f"""
        UPDATE class_commentary_student_learning_events
        SET desired_status='deleted', superseded_by_event_id=NULL
        WHERE event_id IN ({placeholders})
        """,
        tuple(event_ids),
    )
    conn.execute(
        f"DELETE FROM class_commentary_learning_state_current WHERE organization_id=?{student_sql}",
        tuple(params),
    )
    operation_ids = []
    for event_id in event_ids:
        payload = _graph_event_payload_conn(conn, event_id)
        payload_hash = _graph_sync_payload_hash(payload)
        conn.execute(
            """
            INSERT INTO class_commentary_graph_sync_outbox (
                organization_id, event_id, operation_key, payload_json, payload_hash, status
            ) VALUES (?, ?, ?, ?, ?, 'reconcile_needed')
            ON CONFLICT(event_id) DO UPDATE SET
                payload_json=excluded.payload_json,
                payload_hash=excluded.payload_hash,
                status='reconcile_needed',
                claim_token=NULL, claim_owner=NULL, lease_until=NULL,
                next_attempt_at=NULL, last_error=NULL,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            """,
            (
                organization_id,
                event_id,
                f"class-commentary-graph-sync:{event_id}",
                canonical_json(payload),
                payload_hash,
            ),
        )
        operation_ids.append(
            int(
                conn.execute(
                    "SELECT id FROM class_commentary_graph_sync_outbox WHERE event_id=?",
                    (event_id,),
                ).fetchone()["id"]
            )
        )
    return {
        "request_key": request_key,
        "operation_ids": operation_ids,
        "event_count": len(event_ids),
    }


def reconcile_class_commentary_graph_store(
    *,
    limit: int = 100,
    auto_map_enabled: Optional[bool] = None,
    actor_user_id: int = 1,
) -> dict:
    recovered_jobs = 0
    recovered_sync = 0
    created_sync = 0
    created_extraction = 0
    if auto_map_enabled is None:
        from config_runtime import get_runtime_config

        auto_map_enabled = bool(
            get_runtime_config().get("class_commentary_graph_auto_map_enabled", True)
        )
    auto_map_candidates: list[tuple[str, int]] = []
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        missing_extractions = conn.execute(
            """
            SELECT revision.id AS revision_id, revision.generation_id
            FROM class_commentary_revisions AS revision
            WHERE revision.learn_requested=1
              AND revision.graph_extraction_requested=1
              AND NOT EXISTS (
                  SELECT 1 FROM class_commentary_graph_extraction_jobs AS job
                  WHERE job.revision_id=revision.id
              )
            ORDER BY revision.confirmed_at, revision.id LIMIT ?
            """,
            (max(1, min(int(limit), 500)),),
        ).fetchall()
        for missing_revision in missing_extractions:
            revision = conn.execute(
                "SELECT * FROM class_commentary_revisions WHERE id=?",
                (int(missing_revision["revision_id"]),),
            ).fetchone()
            generation = conn.execute(
                "SELECT * FROM class_commentary_generations WHERE id=?",
                (int(missing_revision["generation_id"]),),
            ).fetchone()
            if revision and generation:
                create_graph_extraction_job_conn(
                    conn,
                    dict(generation),
                    dict(revision),
                )
                created_extraction += 1
        recovered_jobs = conn.execute(
            """
            UPDATE class_commentary_graph_extraction_jobs
            SET status=CASE WHEN attempt_count<? THEN 'retry_wait' ELSE 'failed' END,
                claim_token=NULL, claim_owner=NULL, lease_until=NULL,
                next_attempt_at=CASE WHEN attempt_count<?
                    THEN strftime('%Y-%m-%dT%H:%M:%fZ','now') ELSE NULL END,
                last_error='stale extraction lease recovered',
                completed_at=CASE WHEN attempt_count>=?
                    THEN strftime('%Y-%m-%dT%H:%M:%fZ','now') ELSE completed_at END,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE status='running' AND lease_until<strftime('%Y-%m-%dT%H:%M:%fZ','now')
            """,
            (
                GRAPH_EXTRACTION_MAX_ATTEMPTS,
                GRAPH_EXTRACTION_MAX_ATTEMPTS,
                GRAPH_EXTRACTION_MAX_ATTEMPTS,
            ),
        ).rowcount
        recovered_sync = conn.execute(
            """
            UPDATE class_commentary_graph_sync_outbox
            SET status=CASE WHEN attempt_count<? THEN 'reconcile_needed' ELSE 'failed' END,
                claim_token=NULL, claim_owner=NULL, lease_until=NULL,
                last_error='stale graph sync lease recovered',
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE status='running' AND lease_until<strftime('%Y-%m-%dT%H:%M:%fZ','now')
            """,
            (GRAPH_SYNC_MAX_ATTEMPTS,),
        ).rowcount
        conn.execute(
            """
            UPDATE class_commentary_graph_cleanup_requests AS cleanup
            SET status='failed', last_error='stale graph sync exhausted retries',
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE cleanup.status='pending'
              AND EXISTS (
                  SELECT 1
                  FROM class_commentary_student_learning_events AS event
                  JOIN class_commentary_graph_sync_outbox AS outbox
                    ON outbox.event_id=event.event_id
                  WHERE event.organization_id=cleanup.organization_id
                    AND (cleanup.student_id IS NULL OR event.student_id=cleanup.student_id)
                    AND event.desired_status='deleted'
                    AND outbox.status='failed'
              )
            """
        )
        missing = conn.execute(
            """
            SELECT event_id, organization_id
            FROM class_commentary_student_learning_events AS event
            WHERE NOT EXISTS (
                SELECT 1 FROM class_commentary_graph_sync_outbox AS outbox
                WHERE outbox.event_id=event.event_id
              )
            ORDER BY event.confirmed_at, event.event_id LIMIT ?
            """,
            (max(1, min(int(limit), 500)),),
        ).fetchall()
        for row in missing:
            payload = _graph_event_payload_conn(conn, str(row["event_id"]))
            conn.execute(
                """
                INSERT INTO class_commentary_graph_sync_outbox (
                    organization_id, event_id, operation_key, payload_json, payload_hash, status
                ) VALUES (?, ?, ?, ?, ?, 'reconcile_needed')
                """,
                (
                    int(row["organization_id"]),
                    str(row["event_id"]),
                    f"class-commentary-graph-sync:{row['event_id']}",
                    canonical_json(payload),
                    _graph_sync_payload_hash(payload),
                ),
            )
            created_sync += 1
        if auto_map_enabled:
            auto_map_candidates = [
                (str(row["candidate_id"]), int(row["organization_id"]))
                for row in conn.execute(
                    "SELECT candidate_id, organization_id "
                    "FROM class_commentary_graph_unmapped_candidates "
                    "WHERE status='pending' ORDER BY created_at, candidate_id LIMIT ?",
                    (max(1, min(int(limit), 500)),),
                ).fetchall()
            ]
    auto_mapped: list[dict] = []
    auto_mapping_failures: list[dict] = []
    for pending_id, pending_org_id in auto_map_candidates:
        try:
            auto_mapped.append(
                auto_resolve_graph_unmapped_candidate(
                    pending_id,
                    organization_id=pending_org_id,
                    actor_user_id=int(actor_user_id),
                )
            )
        except Exception as exc:
            auto_mapping_failures.append(
                {"candidate_id": pending_id, "error": exc.__class__.__name__}
            )
    return {
        "created_missing_extraction_jobs": created_extraction,
        "recovered_extraction_jobs": recovered_jobs,
        "recovered_sync_operations": recovered_sync,
        "created_missing_sync_operations": created_sync,
        "dispatchable_extraction_jobs": list_dispatchable_graph_extraction_jobs(limit),
        "dispatchable_sync_operations": list_dispatchable_graph_sync_operations(limit),
        "auto_mapped_candidate_ids": [item.get("candidate_id") or item.get("action", {}).get("candidate_id") or "" for item in auto_mapped],
        "auto_mapped_count": len(auto_mapped),
        "auto_mapping_failure_count": len(auto_mapping_failures),
    }


def retry_graph_revision(
    revision_id: int, *, organization_id: int, actor_user_id: int, request_id: str
) -> dict:
    request_id = str(request_id or "").strip()
    if not request_id:
        raise ValueError("request_id is required")
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        prior = conn.execute(
            """
            SELECT revision_id FROM class_commentary_graph_retry_events
            WHERE organization_id=? AND request_id=?
            """,
            (int(organization_id), request_id),
        ).fetchone()
        if prior and int(prior["revision_id"]) != int(revision_id):
            raise LearningGraphRetryConflict("graph_retry_request_conflict")
        job = conn.execute(
            """
            SELECT job.* FROM class_commentary_graph_extraction_jobs AS job
            JOIN class_commentary_revisions AS revision ON revision.id=job.revision_id
            WHERE job.revision_id=? AND revision.organization_id=?
            ORDER BY job.id DESC LIMIT 1
            """,
            (int(revision_id), int(organization_id)),
        ).fetchone()
        if not job:
            raise ValueError("graph extraction job not found")
        snapshot = dict(job)
        payload_hash = content_hash([revision_id, request_id, snapshot.get("status")])
        conn.execute(
            """
            INSERT OR IGNORE INTO class_commentary_graph_retry_events (
                organization_id, revision_id, extraction_job_id, request_id,
                payload_hash, actor_user_id, previous_state_snapshot_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (int(organization_id), int(revision_id), int(job["id"]), request_id, payload_hash, int(actor_user_id), canonical_json(snapshot)),
        )
        if str(job["status"]) not in {"extracted", "needs_mapping"}:
            conn.execute(
                """
                UPDATE class_commentary_graph_extraction_jobs
                SET status='queued', attempt_count=0, next_attempt_at=NULL, last_error=NULL,
                    claim_token=NULL, claim_owner=NULL, lease_until=NULL,
                    updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                WHERE id=?
                """,
                (int(job["id"]),),
            )
        conn.execute(
            """
            UPDATE class_commentary_graph_sync_outbox
            SET status='reconcile_needed', attempt_count=0,
                claim_token=NULL, claim_owner=NULL, lease_until=NULL,
                next_attempt_at=NULL, last_error=NULL,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE event_id IN (
                SELECT event_id FROM class_commentary_student_learning_events WHERE revision_id=?
            ) AND status<>'applied'
            """,
            (int(revision_id),),
        )
        conn.execute(
            """
            UPDATE class_commentary_graph_cleanup_requests AS cleanup
            SET status='pending', last_error=NULL, applied_at=NULL,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE cleanup.status='failed'
              AND EXISTS (
                  SELECT 1
                  FROM class_commentary_student_learning_events AS event
                  WHERE event.revision_id=? AND event.desired_status='deleted'
                    AND event.organization_id=cleanup.organization_id
                    AND (cleanup.student_id IS NULL OR event.student_id=cleanup.student_id)
              )
            """,
            (int(revision_id),),
        )
        row = conn.execute(
            "SELECT * FROM class_commentary_graph_extraction_jobs WHERE id=?", (int(job["id"]),)
        ).fetchone()
    return dict(row)


def _resume_graph_mapping_action(
    *,
    action_id: int,
    candidate_id: str,
    organization_id: int,
    request_id: str,
) -> dict:
    mapping_claim_token = f"mapping:{content_hash([organization_id, request_id])}"
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT candidate.*, action.payload_json, action.status AS action_status
            FROM class_commentary_graph_unmapped_candidates candidate
            JOIN curriculum_mapping_actions action
              ON action.organization_id=candidate.organization_id
             AND action.candidate_id=candidate.candidate_id
            WHERE action.id=? AND candidate.candidate_id=?
              AND candidate.organization_id=?
            """,
            (int(action_id), str(candidate_id), int(organization_id)),
        ).fetchone()
        if not row:
            raise LookupError("mapping action not found")
        if str(row["status"]) == "mapped" and str(row["action_status"]) == "applied":
            action = conn.execute(
                "SELECT * FROM curriculum_mapping_actions WHERE id=?", (int(action_id),)
            ).fetchone()
            return {"action": dict(action), "candidate": dict(row), "reprocess": None, "replayed": True}
        action_payload = _json_object(row["payload_json"])
        target_key = str(action_payload.get("target_knowledge_point_key") or "").strip()
        raw_payload = _json_object(row["candidate_payload_json"])
        if not target_key or not raw_payload:
            raise LearningGraphValidationError("mapping replay payload is incomplete")
        frozen = get_graph_extraction_input(int(row["extraction_job_id"]))
        if not frozen or not frozen.get("integrity_valid"):
            raise LearningGraphValidationError("mapping replay frozen input is invalid")
        target = _resolve_frozen_knowledge_point(
            conn,
            frozen=frozen,
            value=target_key,
            allow_active_organization_target=True,
        )
        if (
            not target
            or str(target.get("knowledge_point_key") or "") != target_key
            or int(target.get("curriculum_node_id") or 0)
            != int(action_payload.get("target_curriculum_node_id") or 0)
            or int(target.get("organization_knowledge_point_id") or 0)
            != int(action_payload.get("target_organization_knowledge_point_id") or 0)
            or str(target.get("node_content_hash") or "")
            != str(action_payload.get("target_node_content_hash") or "")
        ):
            raise LearningGraphValidationError("mapping replay target is no longer valid")
        raw_payload["knowledge_point_key"] = target_key
        raw_payload["unmapped_candidate"] = None
        job_id = int(row["extraction_job_id"])
        conn.execute("BEGIN IMMEDIATE")
        updated = conn.execute(
            """
            UPDATE class_commentary_graph_extraction_jobs
            SET status='running', claim_token=?, claim_owner='curriculum-mapping',
                lease_until=strftime('%Y-%m-%dT%H:%M:%fZ','now','+5 minutes'),
                last_error=NULL, completed_at=NULL,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=? AND (
                status IN ('needs_mapping','extracted','retry_wait','failed')
                OR (status='running' AND claim_owner='curriculum-mapping')
            )
            """,
            (mapping_claim_token, job_id),
        )
        if updated.rowcount != 1:
            raise LearningGraphRetryConflict("mapping replay job is busy")
        conn.execute(
            "UPDATE curriculum_mapping_actions SET status='approved' WHERE id=?",
            (int(action_id),),
        )
        existing_event = conn.execute(
            """
            SELECT 1 FROM class_commentary_student_learning_events
            WHERE organization_id=? AND revision_id=? AND student_id=?
              AND knowledge_point_key=? AND desired_status<>'deleted'
            LIMIT 1
            """,
            (
                int(organization_id),
                int(row["revision_id"]),
                int(raw_payload.get("student_id") or 0),
                target_key,
            ),
        ).fetchone()
        if existing_event:
            # 幂等守卫：同一 (revision, student, kp) 观察已存在（如批量映射重复提交），
            # 只标记候选已映射，不重复写入学习事件。
            conn.execute(
                """
                UPDATE class_commentary_graph_unmapped_candidates
                SET status='mapped', resolved_at=?, resolved_knowledge_point_key=?
                WHERE candidate_id=? AND status='pending'
                """,
                (_utc_now(), target_key, candidate_id),
            )
            conn.execute(
                "UPDATE curriculum_mapping_actions SET status='applied' WHERE id=?",
                (int(action_id),),
            )
            pending = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM class_commentary_graph_unmapped_candidates
                    WHERE extraction_job_id=? AND status='pending'
                    """,
                    (job_id,),
                ).fetchone()[0]
            )
            conn.execute(
                """
                UPDATE class_commentary_graph_extraction_jobs
                SET status=?, claim_token=NULL, claim_owner=NULL, lease_until=NULL,
                    completed_at=CASE WHEN ?=0 THEN COALESCE(completed_at, ?) ELSE completed_at END
                WHERE id=? AND claim_owner='curriculum-mapping'
                """,
                (
                    "extracted" if not pending else "needs_mapping",
                    pending,
                    _utc_now(),
                    job_id,
                ),
            )
            action = conn.execute(
                "SELECT * FROM curriculum_mapping_actions WHERE id=?", (int(action_id),)
            ).fetchone()
            candidate = conn.execute(
                "SELECT * FROM class_commentary_graph_unmapped_candidates WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            return {
                "action": dict(action),
                "candidate": dict(candidate),
                "reprocess": None,
                "replayed": True,
                "skipped_duplicate": True,
            }
    try:
        committed = commit_graph_extraction(
            job_id,
            claim_token=mapping_claim_token,
            candidates_by_student=[raw_payload],
            extractor_provider="human-mapping",
            extractor_model="deterministic-replay",
            usage={"mapping_action_id": int(action_id)},
            allow_active_organization_targets=True,
        )
        if not committed.get("event_ids"):
            raise LearningGraphValidationError(
                "mapping replay did not create a trusted learning event"
            )
    except Exception:
        with _conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_graph_extraction_jobs
                SET status='needs_mapping', claim_token=NULL, claim_owner=NULL,
                    lease_until=NULL WHERE id=? AND claim_owner='curriculum-mapping'
                """,
                (job_id,),
            )
            conn.execute(
                "UPDATE curriculum_mapping_actions SET status='failed' WHERE id=?",
                (int(action_id),),
            )
        raise
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE class_commentary_graph_unmapped_candidates
            SET status='mapped', resolved_at=?, resolved_knowledge_point_key=?
            WHERE candidate_id=? AND status='pending'
            """,
            (_utc_now(), target_key, candidate_id),
        )
        conn.execute(
            "UPDATE curriculum_mapping_actions SET status='applied' WHERE id=?",
            (int(action_id),),
        )
        pending = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM class_commentary_graph_unmapped_candidates
                WHERE extraction_job_id=? AND status='pending'
                """,
                (job_id,),
            ).fetchone()[0]
        )
        if not pending:
            conn.execute(
                """
                UPDATE class_commentary_graph_extraction_jobs
                SET status='extracted', claim_token=NULL, claim_owner=NULL,
                    lease_until=NULL, completed_at=COALESCE(completed_at, ?)
                WHERE id=? AND status='needs_mapping'
                """,
                (_utc_now(), job_id),
            )
        action = conn.execute(
            "SELECT * FROM curriculum_mapping_actions WHERE id=?", (int(action_id),)
        ).fetchone()
        candidate = conn.execute(
            "SELECT * FROM class_commentary_graph_unmapped_candidates WHERE candidate_id=?",
            (candidate_id,),
        ).fetchone()
    return {
        "action": dict(action),
        "candidate": dict(candidate),
        "reprocess": committed,
        "replayed": str(row["action_status"]) != "approved",
    }


def list_resumable_graph_mapping_actions(limit: int = 100) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT action.id, action.organization_id, action.candidate_id,
                   action.request_id, action.status
            FROM curriculum_mapping_actions action
            JOIN class_commentary_graph_unmapped_candidates candidate
              ON candidate.organization_id=action.organization_id
             AND candidate.candidate_id=action.candidate_id
            WHERE action.action_type IN ('map','add_alias')
              AND action.status IN ('approved','failed')
              AND candidate.status='pending'
            ORDER BY action.id LIMIT ?
            """,
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    return [dict(row) for row in rows]


def resume_graph_mapping_action(action_id: int) -> dict:
    with _conn() as conn:
        action = conn.execute(
            "SELECT * FROM curriculum_mapping_actions WHERE id=?",
            (int(action_id),),
        ).fetchone()
    if not action:
        raise LookupError("mapping action not found")
    return _resume_graph_mapping_action(
        action_id=int(action["id"]),
        candidate_id=str(action["candidate_id"]),
        organization_id=int(action["organization_id"]),
        request_id=str(action["request_id"]),
    )


def resolve_graph_unmapped_candidate(
    candidate_id: str,
    *,
    organization_id: int,
    actor_user_id: int,
    request_id: str,
    action: str,
    target_knowledge_point_key: str = "",
    proposed_name: str = "",
    note: str = "",
) -> dict:
    candidate_id = str(candidate_id or "").strip()
    request_id = str(request_id or "").strip()
    action = str(action or "").strip()
    if not candidate_id or not request_id:
        raise LearningGraphValidationError("candidate_id and request_id are required")
    if action not in {"map", "add_alias", "propose_new", "reject"}:
        raise LearningGraphValidationError("mapping action is invalid")
    action_payload = {
        "candidate_id": candidate_id,
        "action": action,
        "target_knowledge_point_key": str(target_knowledge_point_key or "").strip(),
        "proposed_name": str(proposed_name or "").strip(),
        "note": str(note or "").strip(),
    }
    action_hash = content_hash(action_payload)
    mapping_claim_token = f"mapping:{content_hash([organization_id, request_id])}"
    reprocess_job_id = None
    candidate_payload = None
    resume_action_id = None
    replay_response = None
    with _conn() as conn:
        replay = conn.execute(
            "SELECT * FROM curriculum_mapping_actions WHERE organization_id=? AND request_id=?",
            (int(organization_id), request_id),
        ).fetchone()
        if replay:
            replay_payload = _json_object(replay["payload_json"])
            if str(replay_payload.get("action_hash") or "") != action_hash:
                raise LearningGraphRetryConflict("mapping request replay differs")
            candidate = conn.execute(
                "SELECT * FROM class_commentary_graph_unmapped_candidates WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            if str(replay["action_type"]) in {"map", "add_alias"} and str(replay["status"]) in {
                "approved",
                "failed",
            }:
                resume_action_id = int(replay["id"])
            else:
                replay_response = {
                    "action": dict(replay),
                    "candidate": dict(candidate) if candidate else None,
                    "replayed": True,
                }
    if resume_action_id is not None:
        return _resume_graph_mapping_action(
            action_id=resume_action_id,
            candidate_id=candidate_id,
            organization_id=int(organization_id),
            request_id=request_id,
        )
    if replay_response is not None:
        return replay_response
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        candidate = conn.execute(
            """
            SELECT candidate.*, job.status AS job_status, job.task_id, job.generation_id,
                   job.curriculum_assignment_id, job.curriculum_version_id,
                   job.curriculum_book_node_id, job.curriculum_content_hash,
                   job.curriculum_registry_snapshot_hash,
                   job.curriculum_registry_snapshot_json,
                   job.curriculum_assignment_snapshot_json,
                   job.curriculum_assignment_ids_snapshot_json,
                   job.curriculum_book_node_ids_snapshot_json,
                   job.curriculum_scope_hash,
                   generation.class_id
            FROM class_commentary_graph_unmapped_candidates candidate
            JOIN class_commentary_graph_extraction_jobs job ON job.id=candidate.extraction_job_id
            JOIN class_commentary_generations generation ON generation.id=job.generation_id
            WHERE candidate.candidate_id=? AND candidate.organization_id=?
            """,
            (candidate_id, int(organization_id)),
        ).fetchone()
        if not candidate:
            raise LookupError("unmapped candidate not found")
        if str(candidate["status"]) != "pending":
            raise LearningGraphRetryConflict("unmapped candidate is no longer pending")
        frozen_registry = _json_list(candidate["curriculum_registry_snapshot_json"])
        frozen_assignment = _json_object(candidate["curriculum_assignment_snapshot_json"])
        scope_valid = _frozen_curriculum_scope_valid(
            candidate,
            frozen_assignment,
            class_id=int(candidate["class_id"]),
            organization_id=int(organization_id),
            subject_key=str(candidate["subject_key"] or ""),
            registry=frozen_registry,
        )
        if (
            str(candidate["curriculum_registry_snapshot_hash"] or "")
            != content_hash(frozen_registry)
            or not scope_valid
            or int(frozen_assignment.get("organization_id") or 0)
            != int(organization_id)
            or str(frozen_assignment.get("content_hash") or "")
            != str(candidate["curriculum_content_hash"] or "")
        ):
            raise LearningGraphValidationError("frozen curriculum mapping scope is invalid")
        frozen = {
            "registry": frozen_registry,
            "curriculum_assignment": frozen_assignment or None,
        }
        action_payload.update(
            {
                "curriculum_assignment_id": int(candidate["curriculum_assignment_id"] or 0),
                "curriculum_version_id": int(candidate["curriculum_version_id"] or 0),
                "curriculum_book_node_id": int(candidate["curriculum_book_node_id"] or 0),
                "curriculum_assignment_ids": _json_list(
                    candidate["curriculum_assignment_ids_snapshot_json"]
                ),
                "curriculum_book_node_ids": _json_list(
                    candidate["curriculum_book_node_ids_snapshot_json"]
                ),
                "curriculum_scope_hash": str(candidate["curriculum_scope_hash"] or ""),
                "curriculum_registry_snapshot_hash": str(
                    candidate["curriculum_registry_snapshot_hash"] or ""
                ),
                "candidate_status_before": str(candidate["status"]),
            }
        )
        now = _utc_now()
        if action == "reject":
            conn.execute(
                "UPDATE class_commentary_graph_unmapped_candidates SET status='dismissed', resolved_at=? WHERE candidate_id=?",
                (now, candidate_id),
            )
            status = "applied"
        elif action == "propose_new":
            proposal_name = str(proposed_name or candidate["candidate_text"] or "").strip()
            if not proposal_name:
                raise LearningGraphValidationError("proposed knowledge point name is required")
            assignment = frozen_assignment
            if not assignment:
                raise LearningGraphValidationError("candidate has no frozen curriculum assignment")
            book_ids = _positive_int_list(assignment.get("book_node_ids"))
            if (
                str(assignment.get("schema_version") or "")
                == CLASS_CURRICULUM_SCOPE_SCHEMA_VERSION
                and (book_ids is None or len(book_ids) != 1)
            ):
                # 多教材班级: 冻结范围含多本书时, 用抽取任务自己选定的主教材
                # 作为新建机构知识点的归属书, 不再要求人工指定.
                job_book_id = int(candidate["curriculum_book_node_id"] or 0)
                if job_book_id <= 0:
                    raise LearningGraphValidationError(
                        "proposal requires a single frozen curriculum book"
                    )
                book_ids = [job_book_id]
            proposal_book_id = (
                book_ids[0]
                if book_ids
                else int(assignment.get("book_node_id") or 0)
            )
            if not proposal_book_id:
                raise LearningGraphValidationError(
                    "candidate has no frozen curriculum book"
                )
            proposal_key = f"org.{int(organization_id)}.custom.{content_hash([assignment['version_id'], proposal_book_id, normalize_knowledge_point_alias(proposal_name)])[:24]}"
            conn.execute(
                """
                INSERT OR IGNORE INTO curriculum_organization_knowledge_points (
                    organization_id, version_id, book_node_id, subject_key,
                    knowledge_point_key, canonical_name, description, status,
                    proposed_by_user_id, proposed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'proposed', ?, ?)
                """,
                (
                    int(organization_id), int(assignment["version_id"]),
                    proposal_book_id, str(candidate["subject_key"]),
                    proposal_key, proposal_name, str(note or ""), int(actor_user_id), now,
                ),
            )
            action_payload["proposal_key"] = proposal_key
            status = "pending_review"
        else:
            target = _resolve_frozen_knowledge_point(
                conn,
                frozen=frozen,
                value=str(target_knowledge_point_key or ""),
                allow_active_organization_target=True,
            )
            if not target or str(target["knowledge_point_key"]) != str(target_knowledge_point_key):
                raise LearningGraphValidationError("mapping target is outside the assigned curriculum")
            if action == "add_alias":
                try:
                    conn.execute(
                        """
                        INSERT INTO curriculum_organization_aliases (
                            organization_id, version_id, book_node_id, subject_key,
                            curriculum_node_id, alias, normalized_alias, status,
                            created_by_user_id, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                        """,
                        (
                            int(organization_id), int(target["curriculum_version_id"]),
                            int(target["book_node_id"]), str(candidate["subject_key"]),
                            int(target["curriculum_node_id"]), str(candidate["candidate_text"]),
                            str(candidate["normalized_candidate"]), int(actor_user_id), now,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise LearningGraphRetryConflict("organization alias conflicts with an existing mapping") from exc
            raw_payload = _json_object(candidate["candidate_payload_json"])
            if not raw_payload:
                raise LearningGraphValidationError("unmapped candidate has no replay payload")
            raw_payload["knowledge_point_key"] = str(target["knowledge_point_key"])
            raw_payload["unmapped_candidate"] = None
            action_payload.update(
                {
                    "target_curriculum_node_id": int(target.get("curriculum_node_id") or 0),
                    "target_organization_knowledge_point_id": int(
                        target.get("organization_knowledge_point_id") or 0
                    ),
                    "target_node_content_hash": str(target.get("node_content_hash") or ""),
                    "candidate_status_after": "mapped",
                }
            )
            candidate_payload = raw_payload
            reprocess_job_id = int(candidate["extraction_job_id"])
            conn.execute(
                """
                UPDATE class_commentary_graph_extraction_jobs
                SET status='running', claim_token=?, claim_owner='curriculum-mapping',
                    lease_until=strftime('%Y-%m-%dT%H:%M:%fZ','now','+5 minutes'),
                    last_error=NULL, completed_at=NULL,
                    updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                WHERE id=? AND status IN ('needs_mapping','extracted')
                """,
                (mapping_claim_token, reprocess_job_id),
            )
            status = "approved"
        cursor = conn.execute(
            """
            INSERT INTO curriculum_mapping_actions (
                organization_id, candidate_id, request_id, action_type, status,
                target_knowledge_point_key, proposed_name, note, actor_user_id,
                payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(organization_id), candidate_id, request_id, action, status,
                str(target_knowledge_point_key or "") or None, str(proposed_name or ""),
                str(note or ""), int(actor_user_id),
                canonical_json({**action_payload, "action_hash": action_hash}), now,
            ),
        )
        action_id = int(cursor.lastrowid)
        if action == "reject":
            pending = int(conn.execute(
                "SELECT COUNT(*) FROM class_commentary_graph_unmapped_candidates WHERE extraction_job_id=? AND status='pending'",
                (int(candidate["extraction_job_id"]),),
            ).fetchone()[0])
            if not pending:
                conn.execute(
                    "UPDATE class_commentary_graph_extraction_jobs SET status='extracted' WHERE id=? AND status='needs_mapping'",
                    (int(candidate["extraction_job_id"]),),
                )
    if reprocess_job_id and candidate_payload:
        return _resume_graph_mapping_action(
            action_id=action_id,
            candidate_id=candidate_id,
            organization_id=int(organization_id),
            request_id=request_id,
        )
    committed = None
    with _conn() as conn:
        action_row = conn.execute("SELECT * FROM curriculum_mapping_actions WHERE id=?", (action_id,)).fetchone()
        candidate_row = conn.execute(
            "SELECT * FROM class_commentary_graph_unmapped_candidates WHERE candidate_id=?",
            (candidate_id,),
        ).fetchone()
    return {
        "action": dict(action_row),
        "candidate": dict(candidate_row),
        "reprocess": committed,
        "replayed": False,
    }


def auto_resolve_graph_unmapped_candidate(
    candidate_id: str,
    *,
    organization_id: int,
    actor_user_id: int,
    note: str = "自动映射",
) -> dict:
    """确定性自动清积压: 优先映射到同机构同名活跃机构知识点, 否则按候选名
    自动提案机构知识点并激活 (归属任务主教材), 再完成映射.
    全程写入 curriculum_mapping_actions 审计, request_id 由候选 id 派生, 幂等可重放.
    """
    candidate_id = str(candidate_id or "").strip()
    if not candidate_id:
        raise LearningGraphValidationError("candidate_id is required")
    with _conn() as conn:
        candidate = conn.execute(
            "SELECT * FROM class_commentary_graph_unmapped_candidates "
            "WHERE candidate_id=? AND organization_id=?",
            (candidate_id, int(organization_id)),
        ).fetchone()
    if not candidate:
        raise LookupError("unmapped candidate not found")
    if str(candidate["status"]) != "pending":
        return {"status": "skipped", "candidate_id": candidate_id, "reason": "not_pending"}
    name = str(candidate["candidate_text"] or "").strip()
    if not name:
        raise LearningGraphValidationError("candidate has no text")
    base_request_id = f"auto-map:{content_hash([organization_id, candidate_id])[:24]}"

    with _conn() as conn:
        match = conn.execute(
            "SELECT knowledge_point_key FROM curriculum_organization_knowledge_points "
            "WHERE organization_id=? AND status='active' AND canonical_name=? LIMIT 1",
            (int(organization_id), name),
        ).fetchone()
    if match:
        try:
            return resolve_graph_unmapped_candidate(
                candidate_id,
                organization_id=int(organization_id),
                actor_user_id=int(actor_user_id),
                request_id=base_request_id,
                action="map",
                target_knowledge_point_key=str(match["knowledge_point_key"]),
                note=note,
            )
        except LearningGraphValidationError:
            pass  # 同名知识点不在本次冻结范围, 落回自动提案

    try:
        resolve_graph_unmapped_candidate(
            candidate_id,
            organization_id=int(organization_id),
            actor_user_id=int(actor_user_id),
            request_id=base_request_id + "-p",
            action="propose_new",
            proposed_name=name,
            note=note,
        )
    except LearningGraphRetryConflict:
        pass  # 重放: 提案动作已存在
    with _conn() as conn:
        action = conn.execute(
            "SELECT * FROM curriculum_mapping_actions WHERE organization_id=? AND request_id=?",
            (int(organization_id), base_request_id + "-p"),
        ).fetchone()
        if not action:
            raise LearningGraphValidationError("auto proposal action is missing")
        key = str(_json_object(action["payload_json"]).get("proposal_key") or "").strip()
        if not key:
            raise LearningGraphValidationError("auto proposal key is missing")
        proposal = conn.execute(
            "SELECT * FROM curriculum_organization_knowledge_points WHERE knowledge_point_key=?",
            (key,),
        ).fetchone()
        if not proposal:
            raise LearningGraphValidationError("auto proposal row is missing")
        if str(proposal["status"]) == "proposed":
            from curriculum_registry import review_organization_knowledge_point_proposal

            review_organization_knowledge_point_proposal(
                conn,
                organization_id=int(organization_id),
                proposal_id=int(proposal["id"]),
                actor_user_id=int(actor_user_id),
                request_id=base_request_id + "-r",
                approve=True,
                note=note,
            )
        elif str(proposal["status"]) != "active":
            raise LearningGraphValidationError(
                f"auto proposal has unexpected status {proposal['status']}"
            )
    return resolve_graph_unmapped_candidate(
        candidate_id,
        organization_id=int(organization_id),
        actor_user_id=int(actor_user_id),
        request_id=base_request_id + "-m",
        action="map",
        target_knowledge_point_key=key,
        note=note,
    )


def list_graph_unmapped_candidates(
    *,
    organization_id: int,
    allowed_class_ids: Optional[Iterable[int]] = None,
    status: str = "pending",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    status = str(status or "pending").strip()
    if status not in {"pending", "mapped", "dismissed", "all"}:
        raise LearningGraphValidationError("unmapped candidate status is invalid")
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), 100))
    class_ids = None
    if allowed_class_ids is not None:
        class_ids = sorted({int(class_id) for class_id in allowed_class_ids if int(class_id) > 0})
        if not class_ids:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
    conditions = ["candidate.organization_id=?"]
    params: list[object] = [int(organization_id)]
    if status != "all":
        conditions.append("candidate.status=?")
        params.append(status)
    if class_ids is not None:
        placeholders = ",".join("?" for _ in class_ids)
        conditions.append(f"generation.class_id IN ({placeholders})")
        params.extend(class_ids)
    where_sql = " AND ".join(conditions)
    with _conn() as conn:
        total = int(
            conn.execute(
                f"""
                SELECT COUNT(*)
                FROM class_commentary_graph_unmapped_candidates candidate
                JOIN class_commentary_graph_extraction_jobs job
                  ON job.id=candidate.extraction_job_id
                JOIN class_commentary_generations generation
                  ON generation.id=job.generation_id
                WHERE {where_sql}
                """,
                params,
            ).fetchone()[0]
        )
        rows = conn.execute(
            f"""
            SELECT candidate.*, generation.class_id, class.name AS class_name,
                   student.name AS student_name, revision.revision_no,
                   revision.confirmed_at,
                   job.curriculum_version_id, job.curriculum_book_node_id,
                   job.curriculum_assignment_snapshot_json,
                   job.curriculum_registry_snapshot_hash,
                   action.action_type AS latest_action_type,
                   action.status AS latest_action_status,
                   action.created_at AS latest_action_at
            FROM class_commentary_graph_unmapped_candidates candidate
            JOIN class_commentary_graph_extraction_jobs job
              ON job.id=candidate.extraction_job_id
            JOIN class_commentary_generations generation
              ON generation.id=job.generation_id
            JOIN classes class ON class.id=generation.class_id
            JOIN students student ON student.id=candidate.student_id
            JOIN class_commentary_revisions revision ON revision.id=candidate.revision_id
            LEFT JOIN curriculum_mapping_actions action ON action.id=(
                SELECT latest.id FROM curriculum_mapping_actions latest
                WHERE latest.organization_id=candidate.organization_id
                  AND latest.candidate_id=candidate.candidate_id
                ORDER BY latest.id DESC LIMIT 1
            )
            WHERE {where_sql}
            ORDER BY candidate.created_at DESC, candidate.candidate_id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, page_size, (page - 1) * page_size),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["curriculum_assignment"] = _json_object(
            item.pop("curriculum_assignment_snapshot_json", "{}")
        )
        item.pop("candidate_payload_json", None)
        items.append(item)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_graph_candidate_ids_for_proposal(
    *, organization_id: int, proposal_key: str
) -> list[str]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT action.candidate_id, action.payload_json
            FROM curriculum_mapping_actions action
            JOIN class_commentary_graph_unmapped_candidates candidate
              ON candidate.candidate_id=action.candidate_id
            WHERE action.organization_id=? AND action.action_type='propose_new'
              AND candidate.status='pending'
            ORDER BY action.id
            """,
            (int(organization_id),),
        ).fetchall()
    return [
        str(row["candidate_id"])
        for row in rows
        if str(_json_object(row["payload_json"]).get("proposal_key") or "")
        == str(proposal_key)
    ]


def get_student_learning_graph_summary(
    *,
    organization_id: int,
    task_id: int,
    student_id: int,
    subject_key: str,
    generation_id: Optional[int] = None,
    event_limit: int = 24,
) -> dict:
    subject_key = str(subject_key or "").strip()
    with _conn() as conn:
        task = conn.execute(
            "SELECT * FROM class_commentary_tasks WHERE id=? AND organization_id=?",
            (int(task_id), int(organization_id)),
        ).fetchone()
        if not task:
            raise ValueError("class commentary task not found")
        from curriculum_registry import get_class_curriculum_assignment

        curriculum_assignment = get_class_curriculum_assignment(conn, int(task["class_id"]))
        current_rows = conn.execute(
            """
            SELECT current.*,
                   COALESCE(NULLIF(event.knowledge_point_name_snapshot,''),
                            curriculum_kp.canonical_name, kp.canonical_name,
                            current.knowledge_point_key) AS canonical_name,
                   event.curriculum_node_id, event.organization_knowledge_point_id,
                   event.curriculum_book_node_id, event.curriculum_content_hash
            FROM class_commentary_learning_state_current AS current
            JOIN class_commentary_student_learning_events AS event
              ON event.event_id=current.event_id
            LEFT JOIN class_commentary_knowledge_points AS kp
              ON kp.organization_id=current.organization_id
             AND kp.knowledge_point_key=current.knowledge_point_key
            LEFT JOIN curriculum_nodes AS curriculum_kp
              ON curriculum_kp.id=event.curriculum_node_id
            WHERE current.organization_id=? AND current.student_id=? AND current.subject_key=?
            ORDER BY canonical_name, current.knowledge_point_key
            """,
            (int(organization_id), int(student_id), subject_key),
        ).fetchall()
        event_rows = conn.execute(
            """
            SELECT event.*, evidence.evidence_id, evidence.quote,
                   COALESCE(NULLIF(event.knowledge_point_name_snapshot,''),
                            curriculum_kp.canonical_name, kp.canonical_name,
                            event.knowledge_point_key) AS canonical_name,
                   class.name AS class_name, generation.class_id
            FROM class_commentary_student_learning_events AS event
            JOIN class_commentary_learning_evidence AS evidence ON evidence.event_id=event.event_id
            LEFT JOIN class_commentary_knowledge_points AS kp
              ON kp.organization_id=event.organization_id
             AND kp.knowledge_point_key=event.knowledge_point_key
            LEFT JOIN curriculum_nodes AS curriculum_kp
              ON curriculum_kp.id=event.curriculum_node_id
            JOIN class_commentary_generations AS generation ON generation.id=event.generation_id
            JOIN classes AS class ON class.id=generation.class_id
            WHERE event.organization_id=? AND event.student_id=? AND event.subject_key=?
              AND (
                  event.desired_status='active' OR
                  (event.desired_status='superseded' AND event.superseded_by_event_id IS NOT NULL)
              )
            ORDER BY event.confirmed_at DESC, event.event_id DESC LIMIT ?
            """,
            (int(organization_id), int(student_id), subject_key, max(1, min(int(event_limit), 100))),
        ).fetchall()
        latest_revision = conn.execute(
            """
            SELECT job.status, job.last_error
            FROM class_commentary_graph_extraction_jobs AS job
            JOIN class_commentary_revisions AS revision ON revision.id=job.revision_id
            WHERE revision.task_id=? AND revision.organization_id=?
            ORDER BY revision.revision_no DESC, job.id DESC LIMIT 1
            """,
            (int(task_id), int(organization_id)),
        ).fetchone()
        sync_rows = conn.execute(
            """
            SELECT outbox.status, outbox.last_error
            FROM class_commentary_student_learning_events AS event
            LEFT JOIN class_commentary_graph_sync_outbox AS outbox
              ON outbox.event_id=event.event_id
            WHERE event.organization_id=? AND event.student_id=? AND event.subject_key=?
              AND event.desired_status<>'deleted'
            ORDER BY event.confirmed_at DESC, event.event_id DESC
            """,
            (int(organization_id), int(student_id), subject_key),
        ).fetchall()
        used_refs = []
        if generation_id is not None:
            run = conn.execute(
                """
                SELECT used_graph_evidence_refs_json
                FROM class_commentary_student_generation_runs
                WHERE generation_id=? AND organization_id=? AND student_id=?
                """,
                (int(generation_id), int(organization_id), int(student_id)),
            ).fetchone()
            if run:
                used_refs = [str(value) for value in _json_list(run["used_graph_evidence_refs_json"])]
            if not run:
                generation_refs = conn.execute(
                    """
                    SELECT used_graph_evidence_refs_by_student_json,
                           used_graph_evidence_refs_by_student_hash
                    FROM class_commentary_generations
                    WHERE id=? AND organization_id=?
                    """,
                    (int(generation_id), int(organization_id)),
                ).fetchone()
                refs_by_student = {}
                if generation_refs:
                    refs_json = str(
                        generation_refs[
                            "used_graph_evidence_refs_by_student_json"
                        ]
                        or "{}"
                    )
                    refs_hash = str(
                        generation_refs[
                            "used_graph_evidence_refs_by_student_hash"
                        ]
                        or ""
                    )
                    if refs_hash and content_hash(refs_json) != refs_hash:
                        raise LearningGraphSnapshotIntegrityError(
                            "generation_graph_evidence_refs_hash_mismatch"
                        )
                    refs_by_student = _json_object(refs_json)
                used_refs = [
                    str(value)
                    for value in _json_list(refs_by_student.get(str(int(student_id))))
                ]
        used_evidence_by_ref = {}
        if used_refs:
            placeholders = ",".join("?" for _ in used_refs)
            used_evidence_rows = conn.execute(
                f"""
                SELECT evidence.evidence_id, evidence.quote, event.lesson_id,
                       event.revision_id, event.revision_no, event.confirmed_at,
                       class.name AS class_name
                FROM class_commentary_learning_evidence AS evidence
                JOIN class_commentary_student_learning_events AS event
                  ON event.event_id=evidence.event_id
                JOIN class_commentary_generations AS generation
                  ON generation.id=event.generation_id
                JOIN classes AS class ON class.id=generation.class_id
                WHERE evidence.evidence_id IN ({placeholders})
                  AND event.organization_id=? AND event.student_id=?
                  AND event.subject_key=? AND event.desired_status<>'deleted'
                """,
                (
                    *used_refs,
                    int(organization_id),
                    int(student_id),
                    subject_key,
                ),
            ).fetchall()
            used_evidence_by_ref = {
                str(row["evidence_id"]): {
                    "evidence_ref": str(row["evidence_id"]),
                    "quote": str(row["quote"]),
                    "lesson_id": int(row["lesson_id"]),
                    "lesson_name": f"{str(row['class_name'] or '').strip()} 课堂反馈".strip(),
                    "revision_id": int(row["revision_id"]),
                    "revision_no": int(row["revision_no"]),
                    "confirmed_at": str(row["confirmed_at"]),
                }
                for row in used_evidence_rows
            }
        timeline = []
        for row in reversed(event_rows):
            methods = conn.execute(
                "SELECT method_text FROM class_commentary_learning_teaching_methods WHERE event_id=? ORDER BY method_id",
                (str(row["event_id"]),),
            ).fetchall()
            next_steps = conn.execute(
                "SELECT next_step_text FROM class_commentary_learning_next_steps WHERE event_id=? AND status='confirmed' ORDER BY next_step_id",
                (str(row["event_id"]),),
            ).fetchall()
            curriculum_context = _curriculum_context_for_event_conn(conn, dict(row))
            timeline.append(
                {
                    "event_ref": str(row["event_id"]),
                    "knowledge_point_key": str(row["knowledge_point_key"]),
                    "knowledge_point_name": str(row["canonical_name"]),
                    "state": str(row["observed_state"]),
                    "previous_state": str(row["state_before"]) if row["state_before"] is not None else None,
                    "trend": str(row["reported_trend"]),
                    "observed_at": str(row["confirmed_at"]),
                    "evidence": {
                        "evidence_ref": str(row["evidence_id"]),
                        "quote": str(row["quote"]),
                        "lesson_id": int(row["lesson_id"]),
                        "lesson_name": f"{str(row['class_name'] or '').strip()} 课堂反馈".strip(),
                        "revision_id": int(row["revision_id"]),
                        "revision_no": int(row["revision_no"]),
                        "confirmed_at": str(row["confirmed_at"]),
                    },
                    "teaching_methods": [str(item["method_text"]) for item in methods],
                    "next_steps": [str(item["next_step_text"]) for item in next_steps],
                    "curriculum": curriculum_context,
                }
            )
        pending_mapping = conn.execute(
            """
            SELECT COUNT(*) AS count FROM class_commentary_graph_unmapped_candidates
            WHERE organization_id=? AND student_id=? AND subject_key=? AND status='pending'
            """,
            (int(organization_id), int(student_id), subject_key),
        ).fetchone()["count"]
        curriculum_detail_by_scope = {}
        for row in [*current_rows, *event_rows]:
            node_id = int(row["curriculum_node_id"] or 0)
            custom_id = int(row["organization_knowledge_point_id"] or 0)
            book_node_id = int(row["curriculum_book_node_id"] or 0)
            detail_key = (node_id, custom_id, book_node_id)
            if (node_id or custom_id) and detail_key not in curriculum_detail_by_scope:
                curriculum_detail_by_scope[detail_key] = _curriculum_context_for_event_conn(
                    conn, dict(row)
                )
        current_state_items = []
        for row in current_rows:
            detail = curriculum_detail_by_scope.get(
                (
                    int(row["curriculum_node_id"] or 0),
                    int(row["organization_knowledge_point_id"] or 0),
                    int(row["curriculum_book_node_id"] or 0),
                )
            )
            current_state_items.append(
                {
                    "knowledge_point_key": str(row["knowledge_point_key"]),
                    "knowledge_point_name": str(row["canonical_name"]),
                    "state": str(row["observed_state"]),
                    "observed_at": str(row["confirmed_at"]),
                    "curriculum": (
                        {
                            "path": detail["path"],
                            "prerequisites": detail["prerequisites"],
                            "follow_ups": detail["follow_ups"],
                            "source": detail["source"],
                        }
                        if detail
                        else None
                    ),
                }
            )
    raw_status = str(latest_revision["status"] if latest_revision else "")
    if int(pending_mapping or 0) > 0:
        sync_status = "needs_mapping"
    elif raw_status in {"failed", "integrity_failed"}:
        sync_status = "failed"
    elif any(str(row["status"] or "") == "failed" for row in sync_rows):
        sync_status = "failed"
    elif raw_status in {"queued", "running", "retry_wait"} or any(
        str(row["status"] or "") != "applied" for row in sync_rows
    ):
        sync_status = "pending"
    else:
        sync_status = "learned"
    graph_error = next(
        (
            str(row["last_error"] or "")
            for row in sync_rows
            if str(row["last_error"] or "")
        ),
        "",
    )
    return {
        "organization_id": int(organization_id),
        "task_id": int(task_id),
        "student_id": int(student_id),
        "subject_key": subject_key,
        "curriculum_assignment": curriculum_assignment,
        "sync_status": sync_status,
        "can_retry": sync_status in {"failed", "pending"},
        "error": (
            str(latest_revision["last_error"] or "") if latest_revision else ""
        )
        or graph_error,
        "current_states": current_state_items,
        "timeline": timeline,
        "used_graph_evidence_refs": used_refs,
        "used_graph_evidence": [
            used_evidence_by_ref[evidence_ref]
            for evidence_ref in used_refs
            if evidence_ref in used_evidence_by_ref
        ],
    }
