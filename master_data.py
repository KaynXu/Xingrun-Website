import json
import sqlite3
from typing import Any, Iterable, Optional

import lesson_manager


def ensure_schema(conn: sqlite3.Connection):
    conn.executescript(
        """
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
        );

        CREATE TABLE IF NOT EXISTS master_data_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            action TEXT NOT NULL,
            before_json TEXT NOT NULL,
            after_json TEXT NOT NULL,
            actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        """
    )


def normalize_alias(value) -> str:
    return "".join(str(value or "").strip().lower().split())


def list_user_aliases(user_id, conn=None) -> list[str]:
    should_close = conn is None
    if conn is None:
        conn = lesson_manager.get_conn()
    try:
        ensure_schema(conn)
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


def suggest_wrong_question_mapping(raw_record: dict[str, Any]) -> dict[str, Any]:
    teacher_name = str(raw_record.get("teacher_name") or "")
    class_name = str(raw_record.get("class_name") or "")
    subject = str(raw_record.get("subject") or "")

    with lesson_manager.get_conn() as conn:
        ensure_schema(conn)
        teacher_row = _find_user_match(conn, teacher_name)
        class_row = _find_class_match(conn, class_name, subject=subject)

        if class_row and not teacher_row and class_row["teacher_user_id"] is not None:
            teacher_row = _find_user_by_id(conn, class_row["teacher_user_id"])

        mapping_status = "mapped" if teacher_row and class_row else "unmapped"
        return {
            "record_id": raw_record.get("id"),
            "teacher_name_snapshot": teacher_name,
            "class_name_snapshot": class_name,
            "subject_snapshot": subject,
            "teacher_user_id": teacher_row["id"] if teacher_row else None,
            "class_id": class_row["id"] if class_row else None,
            "teacher_display_name": teacher_row["display_name"] if teacher_row else "",
            "class_display_name": class_row["name"] if class_row else "",
            "mapping_status": mapping_status,
        }


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
            mapping_status,
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
    return subject_matches or list(rows)


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