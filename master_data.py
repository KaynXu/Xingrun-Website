import json
import sqlite3
from typing import Any, Iterable, Optional

import lesson_manager


WRONG_QUESTION_MAPPINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS wrong_question_mappings (
    record_id TEXT PRIMARY KEY,
    teacher_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
    teacher_name_snapshot TEXT DEFAULT '',
    class_name_snapshot TEXT DEFAULT '',
    subject_snapshot TEXT DEFAULT '',
    mapping_status TEXT NOT NULL DEFAULT 'unmapped',
    reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
)
"""

MASTER_DATA_AUDIT_LOG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS master_data_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    action TEXT NOT NULL,
    before_json TEXT NOT NULL,
    after_json TEXT NOT NULL,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
)
"""

WRONG_QUESTION_MAPPINGS_COLUMNS = [
    "record_id",
    "teacher_user_id",
    "class_id",
    "teacher_name_snapshot",
    "class_name_snapshot",
    "subject_snapshot",
    "mapping_status",
    "reviewed_by",
    "reviewed_at",
    "created_at",
    "updated_at",
]

MASTER_DATA_AUDIT_LOG_COLUMNS = [
    "id",
    "entity_type",
    "entity_key",
    "action",
    "before_json",
    "after_json",
    "actor_user_id",
    "created_at",
]

WRONG_QUESTION_MAPPINGS_FOREIGN_KEYS = {
    "teacher_user_id": "SET NULL",
    "class_id": "SET NULL",
    "reviewed_by": "SET NULL",
}

MASTER_DATA_AUDIT_LOG_FOREIGN_KEYS = {
    "actor_user_id": "SET NULL",
}

ALLOWED_MAPPING_STATUSES = {"mapped", "unmapped", "ambiguous", "needs_review"}


def ensure_schema(conn: sqlite3.Connection):
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS user_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(user_id, normalized_alias)
        );

        CREATE INDEX IF NOT EXISTS idx_user_aliases_normalized_alias
        ON user_aliases(normalized_alias);

        CREATE TABLE IF NOT EXISTS class_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(class_id, normalized_alias)
        );

        CREATE INDEX IF NOT EXISTS idx_class_aliases_normalized_alias
        ON class_aliases(normalized_alias);

        {WRONG_QUESTION_MAPPINGS_TABLE_SQL};
        {MASTER_DATA_AUDIT_LOG_TABLE_SQL};
        """
    )
    _ensure_table_foreign_keys(
        conn,
        table_name="wrong_question_mappings",
        expected_actions=WRONG_QUESTION_MAPPINGS_FOREIGN_KEYS,
        create_table_sql=WRONG_QUESTION_MAPPINGS_TABLE_SQL,
        columns=WRONG_QUESTION_MAPPINGS_COLUMNS,
    )
    _ensure_table_foreign_keys(
        conn,
        table_name="master_data_audit_log",
        expected_actions=MASTER_DATA_AUDIT_LOG_FOREIGN_KEYS,
        create_table_sql=MASTER_DATA_AUDIT_LOG_TABLE_SQL,
        columns=MASTER_DATA_AUDIT_LOG_COLUMNS,
    )


def _ensure_table_foreign_keys(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    expected_actions: dict[str, str],
    create_table_sql: str,
    columns: list[str],
):
    if _get_foreign_key_actions(conn, table_name) == expected_actions:
        return

    temp_table_name = f"{table_name}__legacy_backup"
    quoted_columns = ", ".join(f'"{column}"' for column in columns)

    conn.execute(f'ALTER TABLE "{table_name}" RENAME TO "{temp_table_name}"')
    conn.execute(create_table_sql)
    conn.execute(
        f'INSERT INTO "{table_name}" ({quoted_columns}) '
        f'SELECT {quoted_columns} FROM "{temp_table_name}"'
    )
    conn.execute(f'DROP TABLE "{temp_table_name}"')


def _get_foreign_key_actions(conn: sqlite3.Connection, table_name: str) -> dict[str, str]:
    rows = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    return {row[3]: row[6] for row in rows}


def normalize_alias(value) -> str:
    return "".join(str(value or "").strip().lower().split())


def list_user_aliases(user_id, conn=None) -> list[str]:
    should_close = conn is None
    if conn is None:
        conn = lesson_manager.get_conn()
    try:
        ensure_schema(conn)
        _require_user(conn, user_id)
        rows = conn.execute(
            "SELECT alias FROM user_aliases WHERE user_id=? ORDER BY alias COLLATE NOCASE, id",
            (user_id,),
        ).fetchall()
        return [row["alias"] for row in rows]
    finally:
        if should_close:
            conn.close()


def set_user_aliases(*, actor_user_id: int, user_id: int, aliases: Iterable[str]) -> list[str]:
    normalized_aliases = _normalize_aliases(aliases)
    with lesson_manager.get_conn() as conn:
        ensure_schema(conn)
        _require_user(conn, user_id)
        before = list_user_aliases(user_id, conn=conn)
        conn.execute("DELETE FROM user_aliases WHERE user_id=?", (user_id,))
        for alias in normalized_aliases:
            conn.execute(
                "INSERT INTO user_aliases (user_id, alias, normalized_alias) VALUES (?, ?, ?)",
                (user_id, alias, normalize_alias(alias)),
            )
        _write_audit_log(
            conn,
            entity_type="user_aliases",
            entity_key=str(user_id),
            action="replace",
            before=before,
            after=normalized_aliases,
            actor_user_id=actor_user_id,
        )
        return normalized_aliases


def list_class_aliases(class_id, conn=None) -> list[str]:
    should_close = conn is None
    if conn is None:
        conn = lesson_manager.get_conn()
    try:
        ensure_schema(conn)
        _require_class(conn, class_id)
        rows = conn.execute(
            "SELECT alias FROM class_aliases WHERE class_id=? ORDER BY alias COLLATE NOCASE, id",
            (class_id,),
        ).fetchall()
        return [row["alias"] for row in rows]
    finally:
        if should_close:
            conn.close()


def set_class_aliases(*, actor_user_id: int, class_id: int, aliases: Iterable[str]) -> list[str]:
    normalized_aliases = _normalize_aliases(aliases)
    with lesson_manager.get_conn() as conn:
        ensure_schema(conn)
        _require_class(conn, class_id)
        before = list_class_aliases(class_id, conn=conn)
        conn.execute("DELETE FROM class_aliases WHERE class_id=?", (class_id,))
        for alias in normalized_aliases:
            conn.execute(
                "INSERT INTO class_aliases (class_id, alias, normalized_alias) VALUES (?, ?, ?)",
                (class_id, alias, normalize_alias(alias)),
            )
        _write_audit_log(
            conn,
            entity_type="class_aliases",
            entity_key=str(class_id),
            action="replace",
            before=before,
            after=normalized_aliases,
            actor_user_id=actor_user_id,
        )
        return normalized_aliases


def merge_user_alias(conn: sqlite3.Connection, user_id: int, alias: str) -> list[str]:
    ensure_schema(conn)
    _require_user(conn, user_id)
    cleaned_alias = (alias or "").strip()
    if not cleaned_alias:
        return list_user_aliases(user_id, conn=conn)
    conn.execute(
        "INSERT OR IGNORE INTO user_aliases (user_id, alias, normalized_alias) VALUES (?, ?, ?)",
        (user_id, cleaned_alias, normalize_alias(cleaned_alias)),
    )
    return list_user_aliases(user_id, conn=conn)


def merge_class_alias(conn: sqlite3.Connection, class_id: int, alias: str) -> list[str]:
    ensure_schema(conn)
    _require_class(conn, class_id)
    cleaned_alias = (alias or "").strip()
    if not cleaned_alias:
        return list_class_aliases(class_id, conn=conn)
    conn.execute(
        "INSERT OR IGNORE INTO class_aliases (class_id, alias, normalized_alias) VALUES (?, ?, ?)",
        (class_id, cleaned_alias, normalize_alias(cleaned_alias)),
    )
    return list_class_aliases(class_id, conn=conn)


def suggest_wrong_question_mapping(
    raw_record: dict[str, Any],
    conn: Optional[sqlite3.Connection] = None,
) -> dict[str, Any]:
    teacher_name = str(raw_record.get("teacher_name") or raw_record.get("teacherName") or "")
    class_name = str(raw_record.get("class_name") or raw_record.get("className") or "")
    subject = str(raw_record.get("subject") or "")

    should_close = conn is None
    if conn is None:
        conn = lesson_manager.get_conn()

    try:
        ensure_schema(conn)
        teacher_row = _find_user_match(conn, teacher_name)
        class_row = _find_class_match(conn, class_name, subject=subject)

        if class_row and not teacher_row and class_row["teacher_user_id"] is not None:
            teacher_row = _find_user_by_id(conn, class_row["teacher_user_id"])

        mapping_status = _suggest_mapping_status(teacher_row, class_row)
        return {
            "record_id": raw_record.get("id") or raw_record.get("record_id"),
            "teacher_name_snapshot": teacher_name,
            "class_name_snapshot": class_name,
            "subject_snapshot": subject,
            "teacher_user_id": teacher_row["id"] if teacher_row else None,
            "class_id": class_row["id"] if class_row else None,
            "teacher_display_name": teacher_row["display_name"] if teacher_row else "",
            "class_display_name": class_row["name"] if class_row else "",
            "mapping_status": mapping_status,
        }
    finally:
        if should_close:
            conn.close()


def normalize_wrong_question_record(
    raw_record: dict[str, Any],
    conn: Optional[sqlite3.Connection] = None,
) -> dict[str, Any]:
    normalized = dict(raw_record)
    record_id = str(raw_record.get("id") or raw_record.get("record_id") or "")
    teacher_name_snapshot = str(raw_record.get("teacher_name") or raw_record.get("teacherName") or "")
    class_name_snapshot = str(raw_record.get("class_name") or raw_record.get("className") or "")
    subject_snapshot = str(raw_record.get("subject") or "")

    if not record_id:
        normalized["teacher_user_id"] = None
        normalized["teacher_display_name"] = teacher_name_snapshot
        normalized["teacher_name_snapshot"] = teacher_name_snapshot
        normalized["class_id"] = None
        normalized["class_display_name"] = class_name_snapshot
        normalized["class_name_snapshot"] = class_name_snapshot
        normalized["mapping_status"] = "unmapped"
        return normalized

    should_close = conn is None
    if conn is None:
        conn = lesson_manager.get_conn()

    try:
        ensure_schema(conn)
        suggestion = suggest_wrong_question_mapping(raw_record, conn=conn)
        mapping = get_wrong_question_mapping(record_id, conn=conn)
        if not mapping:
            mapping = upsert_wrong_question_mapping(
                record_id,
                teacher_user_id=suggestion.get("teacher_user_id"),
                class_id=suggestion.get("class_id"),
                teacher_name_snapshot=suggestion.get("teacher_name_snapshot", teacher_name_snapshot),
                class_name_snapshot=suggestion.get("class_name_snapshot", class_name_snapshot),
                subject_snapshot=suggestion.get("subject_snapshot", subject_snapshot),
                mapping_status=suggestion.get("mapping_status", "unmapped"),
                conn=conn,
            )
        elif _should_auto_upgrade_wrong_question_mapping(mapping, suggestion, conn=conn):
            mapping = upsert_wrong_question_mapping(
                record_id,
                teacher_user_id=suggestion.get("teacher_user_id"),
                class_id=suggestion.get("class_id"),
                teacher_name_snapshot=suggestion.get("teacher_name_snapshot", teacher_name_snapshot),
                class_name_snapshot=suggestion.get("class_name_snapshot", class_name_snapshot),
                subject_snapshot=suggestion.get("subject_snapshot", subject_snapshot),
                mapping_status=suggestion.get("mapping_status", mapping.get("mapping_status") or "unmapped"),
                conn=conn,
            )
        elif _should_auto_refresh_wrong_question_mapping_snapshots(mapping, suggestion, conn=conn):
            mapping = upsert_wrong_question_mapping(
                record_id,
                teacher_user_id=mapping.get("teacher_user_id"),
                class_id=mapping.get("class_id"),
                teacher_name_snapshot=suggestion.get("teacher_name_snapshot", teacher_name_snapshot),
                class_name_snapshot=suggestion.get("class_name_snapshot", class_name_snapshot),
                subject_snapshot=suggestion.get("subject_snapshot", subject_snapshot),
                mapping_status=mapping.get("mapping_status") or "unmapped",
                conn=conn,
            )

        mapping = _present_wrong_question_mapping(mapping, conn=conn)

        normalized["teacher_user_id"] = mapping.get("teacher_user_id")
        normalized["teacher_display_name"] = (
            mapping.get("teacher_display_name")
            or mapping.get("teacher_name_snapshot")
            or teacher_name_snapshot
        )
        normalized["teacher_name_snapshot"] = (
            mapping.get("teacher_name_snapshot")
            or teacher_name_snapshot
        )
        normalized["class_id"] = mapping.get("class_id")
        normalized["class_display_name"] = (
            mapping.get("class_display_name")
            or mapping.get("class_name_snapshot")
            or class_name_snapshot
        )
        normalized["class_name_snapshot"] = (
            mapping.get("class_name_snapshot")
            or class_name_snapshot
        )
        normalized["mapping_status"] = mapping.get("mapping_status", "unmapped")
        return normalized
    finally:
        if should_close:
            conn.close()


def upsert_wrong_question_mapping(
    record_id: str,
    *,
    teacher_user_id: Optional[int] = None,
    class_id: Optional[int] = None,
    teacher_name_snapshot: str = "",
    class_name_snapshot: str = "",
    subject_snapshot: str = "",
    mapping_status: str = "unmapped",
    reviewed_by: Optional[int] = None,
    conn: Optional[sqlite3.Connection] = None,
):
    if conn is None:
        with lesson_manager.get_conn() as owned_conn:
            return upsert_wrong_question_mapping(
                record_id,
                teacher_user_id=teacher_user_id,
                class_id=class_id,
                teacher_name_snapshot=teacher_name_snapshot,
                class_name_snapshot=class_name_snapshot,
                subject_snapshot=subject_snapshot,
                mapping_status=mapping_status,
                reviewed_by=reviewed_by,
                conn=owned_conn,
            )

    ensure_schema(conn)
    if teacher_user_id is not None:
        _require_user(conn, teacher_user_id)
    if class_id is not None:
        _require_class(conn, class_id)
    if reviewed_by is not None:
        _require_user(conn, reviewed_by)
    normalized_status = _normalize_mapping_status(mapping_status)
    if normalized_status == "mapped":
        if teacher_user_id is None or class_id is None:
            raise ValueError("mapped status requires teacher_user_id and class_id")
        if not _is_valid_teacher_class_pair(conn, teacher_user_id, class_id):
            raise ValueError("teacher/class pair does not match canonical class binding")

    before = get_wrong_question_mapping(record_id, conn=conn)
    reviewed_at_expr = "datetime('now','localtime')" if reviewed_by is not None else "NULL"
    conn.execute(
        f"""
        INSERT INTO wrong_question_mappings (
            record_id,
            teacher_user_id,
            class_id,
            teacher_name_snapshot,
            class_name_snapshot,
            subject_snapshot,
            mapping_status,
            reviewed_by,
            reviewed_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, {reviewed_at_expr}, datetime('now','localtime'))
        ON CONFLICT(record_id) DO UPDATE SET
            teacher_user_id=excluded.teacher_user_id,
            class_id=excluded.class_id,
            teacher_name_snapshot=excluded.teacher_name_snapshot,
            class_name_snapshot=excluded.class_name_snapshot,
            subject_snapshot=excluded.subject_snapshot,
            mapping_status=excluded.mapping_status,
            reviewed_by=excluded.reviewed_by,
            reviewed_at={reviewed_at_expr},
            updated_at=datetime('now','localtime')
        """,
        (
            record_id,
            teacher_user_id,
            class_id,
            teacher_name_snapshot,
            class_name_snapshot,
            subject_snapshot,
            normalized_status,
            reviewed_by,
        ),
    )
    after = get_wrong_question_mapping(record_id, conn=conn)
    _write_audit_log(
        conn,
        entity_type="wrong_question_mapping",
        entity_key=record_id,
        action="upsert",
        before=before,
        after=after,
        actor_user_id=reviewed_by,
    )
    return after


def get_wrong_question_mapping(record_id: str, conn: Optional[sqlite3.Connection] = None):
    should_close = conn is None
    if conn is None:
        conn = lesson_manager.get_conn()
    try:
        ensure_schema(conn)
        row = conn.execute(
            """
            SELECT wqm.*, u.display_name AS teacher_display_name, c.name AS class_display_name
            FROM wrong_question_mappings wqm
            LEFT JOIN users u ON u.id = wqm.teacher_user_id
            LEFT JOIN classes c ON c.id = wqm.class_id
            WHERE wqm.record_id=?
            """,
            (record_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()


def list_wrong_question_mapping_queue(status: Optional[str] = None) -> list[dict[str, Any]]:
    with lesson_manager.get_conn() as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT wqm.*, u.display_name AS teacher_display_name, c.name AS class_display_name
            FROM wrong_question_mappings wqm
            LEFT JOIN users u ON u.id = wqm.teacher_user_id
            LEFT JOIN classes c ON c.id = wqm.class_id
            ORDER BY wqm.updated_at DESC, wqm.record_id DESC
            """
        ).fetchall()
        items = [_present_wrong_question_mapping(dict(row), conn=conn) for row in rows]
        if status:
            return [item for item in items if item.get("mapping_status") == status]
        return [item for item in items if not _is_final_wrong_question_mapping(item, conn=conn)]


def resolve_wrong_question_mapping(
    *,
    actor_user_id: int,
    record_id: str,
    teacher_user_id: Optional[int],
    class_id: Optional[int],
    mapping_status: Any,
):
    with lesson_manager.get_conn() as conn:
        ensure_schema(conn)
        _require_user(conn, actor_user_id)
        normalized_status = _normalize_mapping_status(mapping_status)
        if normalized_status == "mapped" and (teacher_user_id is None or class_id is None):
            raise ValueError("mapped status requires teacher_user_id and class_id")
        if teacher_user_id is not None:
            _require_user(conn, teacher_user_id)
        if class_id is not None:
            _require_class(conn, class_id)
        if normalized_status == "mapped" and not _is_valid_teacher_class_pair(conn, teacher_user_id, class_id):
            raise ValueError("teacher/class pair does not match canonical class binding")

        before = get_wrong_question_mapping(record_id, conn=conn)
        if not before:
            raise LookupError("wrong question mapping not found")

        conn.execute(
            """
            UPDATE wrong_question_mappings
            SET teacher_user_id=?,
                class_id=?,
                mapping_status=?,
                reviewed_by=?,
                reviewed_at=datetime('now','localtime'),
                updated_at=datetime('now','localtime')
            WHERE record_id=?
            """,
            (teacher_user_id, class_id, normalized_status, actor_user_id, record_id),
        )

        after = get_wrong_question_mapping(record_id, conn=conn)
        if after and _is_final_wrong_question_mapping(after, conn=conn) and after["teacher_name_snapshot"]:
            merge_user_alias(conn, user_id=teacher_user_id, alias=after["teacher_name_snapshot"])
        if after and _is_final_wrong_question_mapping(after, conn=conn) and after["class_name_snapshot"]:
            merge_class_alias(conn, class_id=class_id, alias=after["class_name_snapshot"])

        _write_audit_log(
            conn,
            entity_type="wrong_question_mapping",
            entity_key=record_id,
            action="resolve",
            before=before,
            after=after,
            actor_user_id=actor_user_id,
        )
        return after


def _normalize_mapping_status(mapping_status: Any) -> str:
    if not isinstance(mapping_status, str):
        raise ValueError("invalid mapping_status")
    normalized_status = mapping_status.strip()
    if not normalized_status:
        raise ValueError("mapping_status is required")
    if normalized_status not in ALLOWED_MAPPING_STATUSES:
        raise ValueError("invalid mapping_status")
    return normalized_status


def _should_auto_upgrade_wrong_question_mapping(
    existing_mapping: dict[str, Any],
    suggestion: dict[str, Any],
    *,
    conn: sqlite3.Connection,
) -> bool:
    if existing_mapping.get("reviewed_by") is not None:
        return False
    if _is_final_wrong_question_mapping(existing_mapping, conn=conn):
        return False
    return _mapping_resolution_rank(suggestion, conn=conn) > _mapping_resolution_rank(existing_mapping, conn=conn)


def _should_auto_refresh_wrong_question_mapping_snapshots(
    existing_mapping: dict[str, Any],
    suggestion: dict[str, Any],
    *,
    conn: sqlite3.Connection,
) -> bool:
    if existing_mapping.get("reviewed_by") is not None:
        return False
    if _is_final_wrong_question_mapping(existing_mapping, conn=conn):
        return False
    return any(
        (existing_mapping.get(field) or "") != (suggestion.get(field) or "")
        for field in (
            "teacher_name_snapshot",
            "class_name_snapshot",
            "subject_snapshot",
        )
    )


def _present_wrong_question_mapping(
    mapping: Optional[dict[str, Any]],
    *,
    conn: sqlite3.Connection,
) -> Optional[dict[str, Any]]:
    if mapping is None or _is_final_wrong_question_mapping(mapping, conn=conn):
        return mapping

    if mapping.get("mapping_status") != "mapped":
        return mapping

    presented_mapping = dict(mapping)
    presented_mapping["teacher_user_id"] = None
    presented_mapping["class_id"] = None
    presented_mapping["teacher_display_name"] = presented_mapping.get("teacher_name_snapshot") or ""
    presented_mapping["class_display_name"] = presented_mapping.get("class_name_snapshot") or ""
    presented_mapping["mapping_status"] = "needs_review"
    return presented_mapping


def _is_final_wrong_question_mapping(
    mapping: dict[str, Any],
    *,
    conn: Optional[sqlite3.Connection] = None,
) -> bool:
    return (
        mapping.get("mapping_status") == "mapped"
        and mapping.get("teacher_user_id") is not None
        and mapping.get("class_id") is not None
        and (
            conn is None
            or _is_valid_teacher_class_pair(
                conn,
                mapping.get("teacher_user_id"),
                mapping.get("class_id"),
            )
        )
    )


def _mapping_resolution_rank(
    mapping: dict[str, Any],
    *,
    conn: Optional[sqlite3.Connection] = None,
) -> tuple[int, int, int]:
    return (
        1 if _is_final_wrong_question_mapping(mapping, conn=conn) else 0,
        1 if mapping.get("class_id") is not None else 0,
        1 if mapping.get("teacher_user_id") is not None else 0,
    )


def _suggest_mapping_status(teacher_row, class_row) -> str:
    if not teacher_row or not class_row:
        return "unmapped"
    if class_row["teacher_user_id"] is not None and class_row["teacher_user_id"] == teacher_row["id"]:
        return "mapped"
    return "needs_review"


def _is_valid_teacher_class_pair(
    conn: sqlite3.Connection,
    teacher_user_id: Optional[int],
    class_id: Optional[int],
) -> bool:
    if teacher_user_id is None or class_id is None:
        return False
    bound_teacher_user_id = lesson_manager.get_class_teacher_user_id(class_id)
    return bound_teacher_user_id is not None and bound_teacher_user_id == teacher_user_id


def _write_audit_log(
    conn: sqlite3.Connection,
    *,
    entity_type: str,
    entity_key: str,
    action: str,
    before: Any,
    after: Any,
    actor_user_id: Optional[int],
):
    ensure_schema(conn)
    conn.execute(
        """
        INSERT INTO master_data_audit_log (
            entity_type,
            entity_key,
            action,
            before_json,
            after_json,
            actor_user_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            entity_type,
            entity_key,
            action,
            json.dumps(before, ensure_ascii=False, sort_keys=True),
            json.dumps(after, ensure_ascii=False, sort_keys=True),
            actor_user_id,
        ),
    )


def _normalize_aliases(aliases: Iterable[str]) -> list[str]:
    unique_aliases = {}
    for alias in aliases:
        if not isinstance(alias, str):
            raise ValueError("aliases must contain only strings")
        cleaned_alias = (alias or "").strip()
        normalized = normalize_alias(cleaned_alias)
        if not normalized:
            continue
        unique_aliases[normalized] = cleaned_alias
    return sorted(unique_aliases.values(), key=lambda value: value.lower())


def _find_user_match(conn: sqlite3.Connection, raw_name: str):
    normalized_name = normalize_alias(raw_name)
    if not normalized_name:
        return None

    alias_rows = conn.execute(
        """
        SELECT u.id, u.username, u.display_name
        FROM user_aliases ua
        JOIN users u ON u.id = ua.user_id
        WHERE ua.normalized_alias=? AND u.status='active'
        ORDER BY u.id
        """,
        (normalized_name,),
    ).fetchall()
    if len(alias_rows) == 1:
        return alias_rows[0]
    if len(alias_rows) > 1:
        return None

    rows = conn.execute(
        "SELECT id, username, display_name FROM users WHERE status='active' ORDER BY id"
    ).fetchall()
    matches = [
        row for row in rows
        if normalize_alias(row["username"]) == normalized_name
        or normalize_alias(row["display_name"]) == normalized_name
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _find_class_match(conn: sqlite3.Connection, raw_name: str, *, subject: str):
    normalized_name = normalize_alias(raw_name)
    normalized_subject = normalize_alias(subject)
    if not normalized_name:
        return None

    alias_rows = conn.execute(
        """
        SELECT c.id, c.name, c.subject,
               (
                   SELECT uc.user_id
                   FROM user_classes uc
                   WHERE uc.class_id = c.id
                   ORDER BY uc.user_id
                   LIMIT 1
               ) AS teacher_user_id
        FROM class_aliases ca
        JOIN classes c ON c.id = ca.class_id
        WHERE ca.normalized_alias=?
        ORDER BY c.id
        """,
        (normalized_name,),
    ).fetchall()
    alias_matches = _filter_classes_by_subject(alias_rows, normalized_subject)
    if len(alias_matches) == 1:
        return alias_matches[0]
    if len(alias_matches) > 1:
        return None

    rows = conn.execute(
        """
        SELECT c.id, c.name, c.subject,
               (
                   SELECT uc.user_id
                   FROM user_classes uc
                   WHERE uc.class_id = c.id
                   ORDER BY uc.user_id
                   LIMIT 1
               ) AS teacher_user_id
        FROM classes c
        ORDER BY c.id
        """
    ).fetchall()
    matches = [row for row in rows if normalize_alias(row["name"]) == normalized_name]
    matches = _filter_classes_by_subject(matches, normalized_subject)
    if len(matches) == 1:
        return matches[0]
    return None


def _filter_classes_by_subject(rows, normalized_subject: str):
    if not normalized_subject:
        return list(rows)
    subject_matches = [row for row in rows if normalize_alias(row["subject"]) == normalized_subject]
    return subject_matches


def _find_user_by_id(conn: sqlite3.Connection, user_id: int):
    return conn.execute(
        "SELECT id, username, display_name FROM users WHERE id=?",
        (user_id,),
    ).fetchone()


def _require_user(conn: sqlite3.Connection, user_id: int):
    row = _find_user_by_id(conn, user_id)
    if not row:
        raise LookupError("user not found")
    return row


def _require_class(conn: sqlite3.Connection, class_id: int):
    row = conn.execute("SELECT id, name FROM classes WHERE id=?", (class_id,)).fetchone()
    if not row:
        raise LookupError("class not found")
    return row