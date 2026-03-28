#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
复习计划管理系统 — 主入口 CLI

用法：
  python lesson_manager.py setup                       # 初始化数据库 & 设置 API Key
  python lesson_manager.py add --file summary.txt      # 从文本文件添加课堂总结
  python lesson_manager.py add --audio recording.m4a   # 从录音文件添加
  python lesson_manager.py add --text "..."            # 直接粘贴课堂总结
  python lesson_manager.py list                        # 列出所有课程
  python lesson_manager.py show --id 3                 # 查看某节课详情
  python lesson_manager.py monthly --month 2026-03     # 生成月度复习 PDF
  python lesson_manager.py quiz                        # 输出全部题库（终端）
  python lesson_manager.py quiz --month 2026-03        # 某月题库
  python lesson_manager.py open --id 3                 # 用系统 PDF 查看器打开
"""

import argparse
import csv
import hashlib
import json
import os
import secrets
import sqlite3
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
import shutil
from typing import Optional

from config_runtime import get_runtime_config

# ─── 路径配置 ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.resolve()
DATA_DIR   = BASE_DIR / "data"
PDF_DIR    = DATA_DIR / "pdfs"
DB_PATH    = DATA_DIR / "lessons.db"
CFG_PATH   = BASE_DIR / "config.json"
CONSULTATIONS_CSV_PATH = DATA_DIR / "consultations.csv"
LEGACY_CONSULTATIONS_CSV_PATH = Path.home() / "咨询记录" / "consultations.csv"
DEFAULT_ORGANIZATION_NAME = "星润Starain"
OWNER_USERNAME = "Kayn"
OWNER_DISPLAY_NAME = "Kayn"
CONSULTATION_TEACHERS_JSON_CANDIDATES = [
    DATA_DIR / "teachers.json",
    Path.home() / ".openclaw" / "workspace-wecom" / "teachers.json",
]

CONSULTATION_FIELDNAMES = [
    "id",
    "日期",
    "家长微信名",
    "孩子姓名",
    "年级",
    "接待老师",
    "老师ID",
    "咨询科目",
    "具体需求",
    "来源渠道",
    "截图",
    "提醒时间",
    "提醒状态",
    "提醒任务ID",
    "跟进状态",
    "跟进备注",
    "录入时间",
    "最后更新",
]
CONSULTATION_EDITABLE_FIELDS = {
    "日期",
    "家长微信名",
    "孩子姓名",
    "年级",
    "接待老师",
    "老师ID",
    "咨询科目",
    "具体需求",
    "来源渠道",
    "截图",
    "跟进状态",
    "跟进备注",
}

CONSULTATION_API_FIELD_MAP = {
    "date": "日期",
    "parent_wechat_name": "家长微信名",
    "child_name": "孩子姓名",
    "grade": "年级",
    "receiving_teacher": "接待老师",
    "teacher_id": "老师ID",
    "consultation_subject": "咨询科目",
    "need_detail": "具体需求",
    "source_channel": "来源渠道",
    "screenshot": "截图",
    "follow_up_status": "跟进状态",
    "follow_up_note": "跟进备注",
    "created_at": "录入时间",
    "updated_at": "最后更新",
}

DATA_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)


def _ensure_consultations_csv() -> Path:
    if not CONSULTATIONS_CSV_PATH.exists() and LEGACY_CONSULTATIONS_CSV_PATH.exists():
        CONSULTATIONS_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(LEGACY_CONSULTATIONS_CSV_PATH), str(CONSULTATIONS_CSV_PATH))

    if not CONSULTATIONS_CSV_PATH.exists():
        CONSULTATIONS_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONSULTATIONS_CSV_PATH.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=CONSULTATION_FIELDNAMES)
            writer.writeheader()
    return CONSULTATIONS_CSV_PATH


def _normalize_consultation_row(row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    normalized = {}
    for field in CONSULTATION_FIELDNAMES:
        value = row.get(field, "")
        normalized[field] = "" if value is None else str(value)
    return normalized


def _get_consultation_teacher_directory() -> dict[str, str]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT username, display_name
            FROM users
            WHERE status = 'active'
            """
        ).fetchall()
    directory: dict[str, str] = {}
    for row in rows:
        username = (row["username"] or "").strip()
        display_name = (row["display_name"] or "").strip()
        if username and display_name:
            directory[username.lower()] = display_name
        if display_name:
            directory[display_name.lower()] = display_name
    for teacher_file in CONSULTATION_TEACHERS_JSON_CANDIDATES:
        if not teacher_file.exists():
            continue
        try:
            aliases = json.loads(teacher_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for teacher_id, raw_aliases in aliases.items():
            teacher_key = str(teacher_id).strip().lower()
            if not teacher_key or teacher_key in directory:
                continue
            normalized_aliases: list[str] = []
            if isinstance(raw_aliases, list):
                normalized_aliases = [str(alias).strip() for alias in raw_aliases if str(alias).strip()]
            elif isinstance(raw_aliases, str):
                normalized_aliases = [alias.strip() for alias in raw_aliases.split(",") if alias.strip()]
            if normalized_aliases:
                directory[teacher_key] = normalized_aliases[0]
    return directory


def _serialize_consultation_row(row: dict, teacher_directory: Optional[dict[str, str]] = None) -> dict:
    serialized = dict(row)
    serialized["id"] = int(serialized["id"]) if serialized.get("id") else 0
    for api_field, csv_field in CONSULTATION_API_FIELD_MAP.items():
        serialized[api_field] = serialized.get(csv_field, "")
    teacher_directory = teacher_directory or {}
    receiving_teacher = (serialized.get("接待老师") or "").strip()
    teacher_id = (serialized.get("老师ID") or "").strip()
    serialized["teacher_display_name"] = (
        teacher_directory.get(receiving_teacher.lower())
        or teacher_directory.get(teacher_id.lower())
        or ""
    )
    return serialized


def _extract_consultation_updates(data: Optional[dict]) -> dict[str, str]:
    payload = data or {}
    updates: dict[str, str] = {}
    for field in CONSULTATION_EDITABLE_FIELDS:
        if field in payload:
            value = payload.get(field, "")
            updates[field] = "" if value is None else str(value)
    for api_field, csv_field in CONSULTATION_API_FIELD_MAP.items():
        if csv_field not in CONSULTATION_EDITABLE_FIELDS:
            continue
        if api_field in payload:
            value = payload.get(api_field, "")
            updates[csv_field] = "" if value is None else str(value)
    return updates


def _read_consultation_rows() -> list[dict]:
    path = _ensure_consultations_csv()
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return [_normalize_consultation_row(row) for row in csv.DictReader(fh)]


def _write_consultation_rows(rows: list[dict]) -> None:
    path = _ensure_consultations_csv()
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=CONSULTATION_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(_normalize_consultation_row(row))


def list_consultations(query: str = "") -> list[dict]:
    rows = _read_consultation_rows()
    teacher_directory = _get_consultation_teacher_directory()
    rows.sort(
        key=lambda row: (
            row.get("最后更新", "") or row.get("录入时间", "") or row.get("日期", ""),
            row.get("id", ""),
        ),
        reverse=True,
    )
    keyword = (query or "").strip().lower()
    if keyword:
        rows = [
            row for row in rows
            if keyword in " ".join(row.get(field, "").lower() for field in CONSULTATION_FIELDNAMES)
        ]
    return [_serialize_consultation_row(row, teacher_directory) for row in rows]


def get_consultation(consultation_id: int):
    teacher_directory = _get_consultation_teacher_directory()
    target_id = str(consultation_id)
    for row in _read_consultation_rows():
        if row["id"] == target_id:
            return _serialize_consultation_row(row, teacher_directory)
    return None


def create_consultation(data: dict) -> dict:
    rows = _read_consultation_rows()
    next_id = max((int(row["id"]) for row in rows if row.get("id")), default=0) + 1
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_row = {field: "" for field in CONSULTATION_FIELDNAMES}
    new_row["id"] = str(next_id)
    new_row["录入时间"] = now
    new_row["最后更新"] = now
    for field, value in _extract_consultation_updates(data).items():
        new_row[field] = value
    if not new_row["日期"]:
        new_row["日期"] = str(date.today())
    rows.append(new_row)
    _write_consultation_rows(rows)
    return _serialize_consultation_row(new_row, _get_consultation_teacher_directory())


def update_consultation(consultation_id: int, data: dict):
    rows = _read_consultation_rows()
    target_id = str(consultation_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updated_row = None
    updates = _extract_consultation_updates(data)
    for row in rows:
        if row["id"] != target_id:
            continue
        for field, value in updates.items():
            row[field] = value
        row["最后更新"] = now
        updated_row = row
        break
    if updated_row is None:
        return None
    _write_consultation_rows(rows)
    return _serialize_consultation_row(updated_row, _get_consultation_teacher_directory())


def delete_consultation(consultation_id: int) -> bool:
    rows = _read_consultation_rows()
    target_id = str(consultation_id)
    filtered_rows = [row for row in rows if row["id"] != target_id]
    if len(filtered_rows) == len(rows):
        return False
    _write_consultation_rows(filtered_rows)
    return True


# ─── 数据库 ────────────────────────────────────────────────────────────────────
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS classes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            subject      TEXT DEFAULT '',
            grade        TEXT DEFAULT '',
            teacher_name TEXT DEFAULT '',
            teacher_email TEXT DEFAULT '',
            created_at   TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS lessons (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            subject     TEXT,
            grade       TEXT,
            topic       TEXT,
            summary     TEXT,
            weak_points TEXT,
            plan_json   TEXT,
            pdf_path    TEXT,
            class_id    INTEGER REFERENCES classes(id) ON DELETE SET NULL,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS questions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id  INTEGER NOT NULL,
            question   TEXT,
            answer     TEXT,
            category   TEXT,
            day_num    INTEGER,
            FOREIGN KEY (lesson_id) REFERENCES lessons(id)
        );

        CREATE TABLE IF NOT EXISTS organizations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT NOT NULL UNIQUE,
            password_hash   TEXT NOT NULL,
            display_name    TEXT NOT NULL,
            role            TEXT NOT NULL DEFAULT 'member',
            status          TEXT NOT NULL DEFAULT 'active',
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS registration_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT NOT NULL,
            password_hash   TEXT NOT NULL,
            display_name    TEXT NOT NULL,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            status          TEXT NOT NULL DEFAULT 'pending',
            reviewed_by     INTEGER REFERENCES users(id),
            reviewed_at     TEXT,
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS auth_sessions (
            token       TEXT PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS user_classes (
            user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, class_id)
        );
        """)
        # Safe migration: add class_id if not already present
        cols = [r[1] for r in conn.execute("PRAGMA table_info(lessons)").fetchall()]
        if "class_id" not in cols:
            conn.execute("ALTER TABLE lessons ADD COLUMN class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL")
        _bootstrap_account_state(conn)
    print(f"数据库已初始化：{DB_PATH}")


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _public_user_dict(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
        "status": row["status"],
        "organization_id": row["organization_id"],
        "organization_name": row["organization_name"],
        "created_at": row["created_at"],
    }


def _ensure_organization(conn: sqlite3.Connection, name: str = DEFAULT_ORGANIZATION_NAME) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM organizations WHERE name=?", (name,)).fetchone()
    if row:
        return row
    cur = conn.execute("INSERT INTO organizations (name) VALUES (?)", (name,))
    return conn.execute("SELECT * FROM organizations WHERE id=?", (cur.lastrowid,)).fetchone()


def _fetch_user_row_by_username(conn: sqlite3.Connection, username: str):
    return conn.execute(
        """
        SELECT u.*, o.name AS organization_name
        FROM users u
        JOIN organizations o ON o.id = u.organization_id
        WHERE u.username=?
        """,
        (username,),
    ).fetchone()


def _fetch_user_row_by_id(conn: sqlite3.Connection, user_id: int):
    return conn.execute(
        """
        SELECT u.*, o.name AS organization_name
        FROM users u
        JOIN organizations o ON o.id = u.organization_id
        WHERE u.id=?
        """,
        (user_id,),
    ).fetchone()


def _bootstrap_account_state(conn: sqlite3.Connection) -> None:
    runtime_cfg = get_runtime_config()
    org = _ensure_organization(conn, DEFAULT_ORGANIZATION_NAME)
    old_username = (runtime_cfg.get("admin_username") or "admin").strip() or "admin"
    configured_hash = (runtime_cfg.get("admin_password_hash") or "").strip()
    owner = conn.execute(
        """
        SELECT u.*, o.name AS organization_name
        FROM users u
        JOIN organizations o ON o.id = u.organization_id
        WHERE u.role='owner' OR u.username IN (?, ?)
        ORDER BY CASE WHEN u.username=? THEN 0 WHEN u.role='owner' THEN 1 ELSE 2 END, u.id
        LIMIT 1
        """,
        (OWNER_USERNAME, old_username, OWNER_USERNAME),
    ).fetchone()
    owner_hash = configured_hash or (owner["password_hash"] if owner else "") or hash_password("xingrun2026")
    if owner:
        conn.execute(
            """
            UPDATE users
            SET username=?, password_hash=?, display_name=?, role='owner', status='active', organization_id=?
            WHERE id=?
            """,
            (OWNER_USERNAME, owner_hash, OWNER_DISPLAY_NAME, org["id"], owner["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
            VALUES (?, ?, ?, 'owner', 'active', ?)
            """,
            (OWNER_USERNAME, owner_hash, OWNER_DISPLAY_NAME, org["id"]),
        )


def save_lesson(date_str: str, subject: str, grade: str, topic: str,
                summary: str, weak_points: str,
                plan: dict, pdf_path: str, class_id: int = 0) -> int:
    """保存一节课及其复习计划，返回 lesson_id。"""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO lessons
               (date, subject, grade, topic, summary, weak_points, plan_json, pdf_path, class_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (date_str, subject, grade, topic, summary, weak_points,
             json.dumps(plan, ensure_ascii=False), pdf_path,
             class_id if class_id else None)
        )
        lesson_id = cur.lastrowid

        # 保存题库
        questions = plan.get("questions", [])
        for q in questions:
            conn.execute(
                "INSERT INTO questions (lesson_id, question, answer, category, day_num) "
                "VALUES (?,?,?,?,?)",
                (lesson_id, q.get("question"), q.get("answer"),
                 q.get("category"), q.get("day", 0))
            )
    return lesson_id


def get_lesson(lesson_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("plan_json"):
            d["plan"] = json.loads(d["plan_json"])
        return d


def list_lessons(month_str: str = "", class_id: int = 0) -> list:
    with get_conn() as conn:
        if class_id and month_str:
            rows = conn.execute(
                "SELECT * FROM lessons WHERE class_id=? AND date LIKE ? ORDER BY date",
                (class_id, f"{month_str}%")
            ).fetchall()
        elif class_id:
            rows = conn.execute(
                "SELECT * FROM lessons WHERE class_id=? ORDER BY date DESC",
                (class_id,)
            ).fetchall()
        elif month_str:
            rows = conn.execute(
                "SELECT * FROM lessons WHERE date LIKE ? ORDER BY date",
                (f"{month_str}%",)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM lessons ORDER BY date DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def delete_lesson(lesson_id: int):
    """Delete a lesson and its associated questions from the database."""
    with get_conn() as conn:
        conn.execute("DELETE FROM questions WHERE lesson_id=?", (lesson_id,))
        conn.execute("DELETE FROM lessons WHERE id=?", (lesson_id,))


# ─── 班级 CRUD ─────────────────────────────────────────────────────────────────
def save_class(name: str, subject: str = "", grade: str = "",
               teacher_name: str = "", teacher_email: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO classes (name, subject, grade, teacher_name, teacher_email) VALUES (?,?,?,?,?)",
            (name, subject, grade, teacher_name, teacher_email)
        )
        return cur.lastrowid


def get_class(class_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        return dict(row) if row else None


def list_classes():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.*, COUNT(l.id) as lesson_count FROM classes c "
            "LEFT JOIN lessons l ON l.class_id = c.id "
            "GROUP BY c.id ORDER BY c.created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def update_class(class_id: int, name: str, subject: str = "", grade: str = "",
                 teacher_name: str = "", teacher_email: str = ""):
    with get_conn() as conn:
        conn.execute(
            "UPDATE classes SET name=?, subject=?, grade=?, teacher_name=?, teacher_email=? WHERE id=?",
            (name, subject, grade, teacher_name, teacher_email, class_id)
        )


def delete_class(class_id: int):
    """Delete a class (lessons are kept but unlinked)."""
    with get_conn() as conn:
        conn.execute("UPDATE lessons SET class_id=NULL WHERE class_id=?", (class_id,))
        conn.execute("DELETE FROM classes WHERE id=?", (class_id,))


# ─── 用户-班级关联 ──────────────────────────────────────────────────────────────
def list_all_users() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT u.*, o.name AS organization_name
            FROM users u
            JOIN organizations o ON o.id = u.organization_id
            WHERE u.status = 'active'
            ORDER BY CASE WHEN u.role='owner' THEN 0 ELSE 1 END, u.display_name
            """
        ).fetchall()
        return [_public_user_dict(row) for row in rows]


def get_user_class_ids(user_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT class_id FROM user_classes WHERE user_id=?", (user_id,)
        ).fetchall()
        return [r["class_id"] for r in rows]


def set_user_class_ids(user_id: int, class_ids: list):
    with get_conn() as conn:
        conn.execute("DELETE FROM user_classes WHERE user_id=?", (user_id,))
        for cid in class_ids:
            conn.execute(
                "INSERT OR IGNORE INTO user_classes (user_id, class_id) VALUES (?, ?)",
                (user_id, cid)
            )


# ─── 账号 / 机构 / 审批 ────────────────────────────────────────────────────────
def get_current_user(token: str):
    if not token:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT u.*, o.name AS organization_name
            FROM auth_sessions s
            JOIN users u ON u.id = s.user_id
            JOIN organizations o ON o.id = u.organization_id
            WHERE s.token=?
            """,
            (token,),
        ).fetchone()
    return _public_user_dict(row)


def get_user_by_username(username: str):
    with get_conn() as conn:
        row = _fetch_user_row_by_username(conn, username)
    return _public_user_dict(row)


def create_auth_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO auth_sessions (token, user_id) VALUES (?, ?)",
            (token, user_id),
        )
        conn.execute(
            """
            DELETE FROM auth_sessions
            WHERE user_id=? AND token NOT IN (
                SELECT token FROM auth_sessions
                WHERE user_id=?
                ORDER BY created_at DESC, token DESC
                LIMIT 10
            )
            """,
            (user_id, user_id),
        )
    return token


def authenticate_user(username: str, password: str):
    with get_conn() as conn:
        row = _fetch_user_row_by_username(conn, username)
        if not row:
            pending = conn.execute(
                "SELECT 1 FROM registration_requests WHERE username=? AND status='pending' LIMIT 1",
                (username,),
            ).fetchone()
            if pending:
                return None, "该账号申请正在等待审批"
            return None, "用户名或密码错误"
        if row["status"] != "active":
            return None, "账号未启用"
        if row["password_hash"] != hash_password(password):
            return None, "用户名或密码错误"
    return _public_user_dict(row), None


def create_registration_request(username: str, display_name: str, password: str,
                                organization_name: str = DEFAULT_ORGANIZATION_NAME):
    with get_conn() as conn:
        org = _ensure_organization(conn, organization_name)
        existing_user = conn.execute(
            "SELECT 1 FROM users WHERE username=? LIMIT 1",
            (username,),
        ).fetchone()
        if existing_user:
            raise ValueError("用户名已存在")
        existing_pending = conn.execute(
            "SELECT 1 FROM registration_requests WHERE username=? AND status='pending' LIMIT 1",
            (username,),
        ).fetchone()
        if existing_pending:
            raise ValueError("该用户名已有待审批申请")
        cur = conn.execute(
            """
            INSERT INTO registration_requests (username, password_hash, display_name, organization_id, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (username, hash_password(password), display_name, org["id"]),
        )
        row = conn.execute(
            """
            SELECT rr.*, o.name AS organization_name
            FROM registration_requests rr
            JOIN organizations o ON o.id = rr.organization_id
            WHERE rr.id=?
            """,
            (cur.lastrowid,),
        ).fetchone()
    return dict(row)


def list_registration_requests(status: str = "pending") -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT rr.*, o.name AS organization_name
            FROM registration_requests rr
            JOIN organizations o ON o.id = rr.organization_id
            WHERE rr.status=?
            ORDER BY rr.created_at ASC, rr.id ASC
            """,
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


def approve_registration_request(request_id: int, reviewer_id: int):
    with get_conn() as conn:
        req = conn.execute(
            """
            SELECT rr.*, o.name AS organization_name
            FROM registration_requests rr
            JOIN organizations o ON o.id = rr.organization_id
            WHERE rr.id=?
            """,
            (request_id,),
        ).fetchone()
        if not req:
            raise LookupError("申请不存在")
        if req["status"] != "pending":
            raise ValueError("该申请已处理")
        existing_user = conn.execute(
            "SELECT 1 FROM users WHERE username=? LIMIT 1",
            (req["username"],),
        ).fetchone()
        if existing_user:
            raise ValueError("用户名已存在")
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
            VALUES (?, ?, ?, 'member', 'active', ?)
            """,
            (req["username"], req["password_hash"], req["display_name"], req["organization_id"]),
        )
        conn.execute(
            """
            UPDATE registration_requests
            SET status='approved', reviewed_by=?, reviewed_at=datetime('now','localtime')
            WHERE id=?
            """,
            (reviewer_id, request_id),
        )
        user_row = _fetch_user_row_by_id(conn, cur.lastrowid)
    return _public_user_dict(user_row)


def reject_registration_request(request_id: int, reviewer_id: int) -> None:
    with get_conn() as conn:
        req = conn.execute(
            "SELECT * FROM registration_requests WHERE id=?",
            (request_id,),
        ).fetchone()
        if not req:
            raise LookupError("申请不存在")
        if req["status"] != "pending":
            raise ValueError("该申请已处理")
        conn.execute(
            """
            UPDATE registration_requests
            SET status='rejected', reviewed_by=?, reviewed_at=datetime('now','localtime')
            WHERE id=?
            """,
            (reviewer_id, request_id),
        )


def get_lessons_by_week(class_id: int, week_str: str) -> list:
    """Return lessons for a class in a given ISO week string 'YYYY-WXX'."""
    from datetime import datetime, timedelta
    year, wk = int(week_str.split("-W")[0]), int(week_str.split("-W")[1])
    monday = datetime.fromisocalendar(year, wk, 1)
    sunday = monday + timedelta(days=6)
    mon_s = monday.strftime("%Y-%m-%d")
    sun_s = sunday.strftime("%Y-%m-%d")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM lessons WHERE class_id=? AND date >= ? AND date <= ? ORDER BY date",
            (class_id, mon_s, sun_s)
        ).fetchall()
    lessons = []
    for r in rows:
        d = dict(r)
        if d.get("plan_json"):
            d["plan"] = json.loads(d["plan_json"])
        lessons.append(d)
    return lessons


def get_class_weeks(class_id: int) -> list:
    """Return sorted list of ISO week strings for which a class has lessons."""
    from datetime import datetime
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT date FROM lessons WHERE class_id=? ORDER BY date DESC",
            (class_id,)
        ).fetchall()
    weeks = []
    seen = set()
    for r in rows:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d")
            y, w, _ = d.isocalendar()
            ws = f"{y}-W{w:02d}"
            if ws not in seen:
                seen.add(ws)
                weeks.append(ws)
        except Exception:
            pass
    return weeks


def week_label(week_str: str) -> str:
    """Return display label like '2026年第12周（03月23日—03月29日）'."""
    from datetime import datetime, timedelta
    year, wk = int(week_str.split("-W")[0]), int(week_str.split("-W")[1])
    monday = datetime.fromisocalendar(year, wk, 1)
    sunday = monday + timedelta(days=6)
    return f"{year}年第{wk}周（{monday.strftime('%m月%d日')}—{sunday.strftime('%m月%d日')}）"


def get_questions(lesson_id: int = 0, month_str: str = "") -> list[dict]:
    with get_conn() as conn:
        if lesson_id:
            rows = conn.execute(
                "SELECT * FROM questions WHERE lesson_id=? ORDER BY category, id",
                (lesson_id,)
            ).fetchall()
        elif month_str:
            rows = conn.execute(
                """SELECT q.* FROM questions q
                   JOIN lessons l ON q.lesson_id = l.id
                   WHERE l.date LIKE ?
                   ORDER BY q.category, q.id""",
                (f"{month_str}%",)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM questions ORDER BY lesson_id, category, id"
            ).fetchall()
        return [dict(r) for r in rows]


# ─── 命令：setup ───────────────────────────────────────────────────────────────
def cmd_setup(_args):
    init_db()
    # 读取或创建 config.json
    cfg = {}
    if CFG_PATH.exists():
        with open(CFG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)

    existing_key = cfg.get("openai_api_key", "")
    if existing_key:
        print(f"当前已有 API Key（前8位）：{existing_key[:8]}...")
        ans = input("是否重新设置？[y/N] ").strip().lower()
        if ans != "y":
            print("保持原有 API Key 不变。")
            return

    key = input("请输入你的 OpenAI API Key（留空跳过）：").strip()
    if key:
        cfg["openai_api_key"] = key
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"API Key 已保存到 {CFG_PATH}")
    else:
        print("跳过 API Key 设置（可后续手动编辑 config.json 或设置环境变量 OPENAI_API_KEY）。")
    print("\n初始化完成！可以开始使用了。")


# ─── 命令：add ────────────────────────────────────────────────────────────────
def cmd_add(args):
    # 1. 获取原始文本
    raw_text = ""
    if args.audio:
        from ai_processor import transcribe_audio
        raw_text = transcribe_audio(args.audio)
        print("\n【转录结果预览（前300字）】")
        print(raw_text[:300])
        print("..." if len(raw_text) > 300 else "")
    elif args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"文件不存在：{p}")
            sys.exit(1)
        raw_text = p.read_text(encoding="utf-8")
    elif args.text:
        raw_text = args.text
    else:
        print("请通过 --text、--file 或 --audio 提供课堂总结。")
        sys.exit(1)

    # 2. 元信息（命令行优先，否则从文本中提取）
    lesson_date = args.date or str(date.today())
    subject     = args.subject or _extract_field(raw_text, "科目") or "数学"
    grade       = args.grade   or _extract_field(raw_text, "年级") or ""
    topic       = args.topic   or _extract_field(raw_text, "本节课主题") or ""
    weak_points = args.weak    or _extract_field(raw_text, "学生薄弱点") or ""

    print(f"\n课程信息：{lesson_date} | {subject} | {grade} | {topic}")

    # 3. AI 生成复习计划
    from ai_processor import parse_and_generate_plan
    plan = parse_and_generate_plan(
        summary_text=raw_text,
        subject=subject,
        grade=grade,
        topic=topic,
        weak_points=weak_points,
        lesson_date=lesson_date,
    )

    # 4. 生成 PDF
    from pdf_engine import generate_lesson_pdf
    safe_topic = topic.replace("/", "-").replace(" ", "_")[:30] if topic else "课程"
    pdf_name = f"{lesson_date}_{subject}_{safe_topic}.pdf"
    pdf_path = str(PDF_DIR / pdf_name)
    generate_lesson_pdf(plan, pdf_path)
    print(f"PDF 已生成：{pdf_path}")

    # 5. 存库
    lesson_id = save_lesson(
        date_str=lesson_date,
        subject=subject,
        grade=grade,
        topic=topic,
        summary=raw_text,
        weak_points=weak_points,
        plan=plan,
        pdf_path=pdf_path,
    )
    print(f"课程已保存（ID={lesson_id}）")

    # 6. 自动打开 PDF
    if not args.no_open:
        _open_pdf(pdf_path)


def _extract_field(text: str, field: str) -> str:
    """从结构化文本中提取字段值（支持常见格式）。"""
    import re
    pattern = rf"(?:^|\n)\s*{re.escape(field)}\s*[：:]\s*(.+)"
    m = re.search(pattern, text)
    return m.group(1).strip() if m else ""


# ─── 命令：list ───────────────────────────────────────────────────────────────
def cmd_list(args):
    month = args.month or ""
    lessons = list_lessons(month)
    if not lessons:
        print("暂无课程记录。")
        return
    print(f"\n{'ID':>4}  {'日期':^12}  {'科目':^8}  {'年级':^6}  {'主题'}")
    print("─" * 70)
    for l in lessons:
        print(f"{l['id']:>4}  {l['date']:^12}  {l['subject'] or '':^8}  "
              f"{l['grade'] or '':^6}  {l['topic'] or ''}")
    print(f"\n共 {len(lessons)} 条记录")


# ─── 命令：show ───────────────────────────────────────────────────────────────
def cmd_show(args):
    lesson = get_lesson(args.id)
    if not lesson:
        print(f"未找到 ID={args.id} 的课程。")
        sys.exit(1)
    print(f"\n【课程详情 ID={lesson['id']}】")
    print(f"日期：{lesson['date']}  科目：{lesson['subject']}  "
          f"年级：{lesson['grade']}  主题：{lesson['topic']}")
    print(f"薄弱点：{lesson['weak_points'] or '无'}")
    print(f"PDF：{lesson['pdf_path'] or '无'}")

    qs = get_questions(lesson_id=args.id)
    if qs:
        print(f"\n题库（共 {len(qs)} 题）：")
        for q in qs:
            print(f"  [{q['category']}] Q: {q['question']}")
            print(f"           A: {q['answer']}")


# ─── 命令：monthly ────────────────────────────────────────────────────────────
def cmd_monthly(args):
    month = args.month or datetime.now().strftime("%Y-%m")
    lessons = list_lessons(month)
    if not lessons:
        print(f"没有找到 {month} 的课程记录。请先用 add 命令添加课程。")
        sys.exit(1)

    print(f"\n找到 {month} 的 {len(lessons)} 节课：")
    for l in lessons:
        print(f"  {l['date']}  {l['subject']}  {l['topic']}")

    # 准备 AI 所需数据
    lesson_dicts = []
    for l in lessons:
        lesson_dicts.append({
            "date":        l["date"],
            "subject":     l["subject"] or "",
            "grade":       l["grade"] or "",
            "topic":       l["topic"] or "",
            "summary":     l["summary"] or "",
            "weak_points": l["weak_points"] or "",
        })

    from ai_processor import generate_monthly_plan
    plan = generate_monthly_plan(lesson_dicts, month)

    from pdf_engine import generate_monthly_pdf
    pdf_name = f"{month}_月度综合复习.pdf"
    pdf_path = str(PDF_DIR / pdf_name)
    generate_monthly_pdf(plan, pdf_path)
    print(f"月度复习 PDF 已生成：{pdf_path}")

    if not args.no_open:
        _open_pdf(pdf_path)


# ─── 命令：quiz ───────────────────────────────────────────────────────────────
def cmd_quiz(args):
    lesson_id = getattr(args, "id", 0) or 0
    month     = args.month or ""
    questions = get_questions(lesson_id=lesson_id, month_str=month)

    if not questions:
        print("题库为空。")
        return

    # 按 category 分组输出
    cats: dict[str, list] = {}
    for q in questions:
        cats.setdefault(q["category"] or "综合", []).append(q)

    label = f"月份 {month}" if month else (f"课程 ID={lesson_id}" if lesson_id else "全部")
    print(f"\n📚 题库（{label}，共 {len(questions)} 题）\n")
    for cat, qs in cats.items():
        print(f"▶ {cat}（{len(qs)} 题）")
        for q in qs:
            print(f"  Q: {q['question']}")
            if args.show_answers:
                print(f"  A: {q['answer']}")
            else:
                print(f"  A: （隐藏，用 --show-answers 查看）")
        print()


# ─── 命令：open ───────────────────────────────────────────────────────────────
def cmd_open(args):
    lesson = get_lesson(args.id)
    if not lesson:
        print(f"未找到 ID={args.id} 的课程。")
        sys.exit(1)
    pdf = lesson.get("pdf_path")
    if not pdf or not Path(pdf).exists():
        print(f"该课程的 PDF 不存在：{pdf}")
        sys.exit(1)
    _open_pdf(pdf)


def _open_pdf(path: str):
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", path], check=True)
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", path], check=True)
        else:
            os.startfile(path)
    except Exception as e:
        print(f"无法自动打开 PDF：{e}\n请手动打开：{path}")


# ─── CLI 定义 ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="lesson_manager",
        description="课后复习计划管理系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python lesson_manager.py setup
  python lesson_manager.py add --file 今天总结.txt --subject 数学 --grade 初二
  python lesson_manager.py add --audio 录音.m4a
  python lesson_manager.py list
  python lesson_manager.py show --id 1
  python lesson_manager.py monthly --month 2026-03
  python lesson_manager.py quiz --month 2026-03 --show-answers
  python lesson_manager.py open --id 1
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # setup
    p_setup = sub.add_parser("setup", help="初始化数据库 & 设置 API Key")
    p_setup.set_defaults(func=cmd_setup)

    # add
    p_add = sub.add_parser("add", help="添加一节课（文本/文件/录音）")
    src = p_add.add_mutually_exclusive_group(required=True)
    src.add_argument("--text",  help="直接输入课堂总结文本")
    src.add_argument("--file",  help="课堂总结文本文件路径")
    src.add_argument("--audio", help="课堂录音文件路径（mp3/m4a/wav等）")
    p_add.add_argument("--date",    help="上课日期 YYYY-MM-DD（默认今天）")
    p_add.add_argument("--subject", help="科目（如：数学）")
    p_add.add_argument("--grade",   help="年级（如：初二）")
    p_add.add_argument("--topic",   help="本节课主题")
    p_add.add_argument("--weak",    help="学生薄弱点")
    p_add.add_argument("--no-open", action="store_true", help="生成后不自动打开 PDF")
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = sub.add_parser("list", help="列出课程记录")
    p_list.add_argument("--month", help="按月筛选 YYYY-MM")
    p_list.set_defaults(func=cmd_list)

    # show
    p_show = sub.add_parser("show", help="查看某节课详情及题库")
    p_show.add_argument("--id", type=int, required=True, help="课程 ID")
    p_show.set_defaults(func=cmd_show)

    # monthly
    p_month = sub.add_parser("monthly", help="生成月度综合复习 PDF")
    p_month.add_argument("--month", help="月份 YYYY-MM（默认当月）")
    p_month.add_argument("--no-open", action="store_true", help="生成后不自动打开 PDF")
    p_month.set_defaults(func=cmd_monthly)

    # quiz
    p_quiz = sub.add_parser("quiz", help="查看题库")
    p_quiz.add_argument("--id",    type=int, default=0, help="按课程 ID 筛选")
    p_quiz.add_argument("--month", help="按月筛选 YYYY-MM")
    p_quiz.add_argument("--show-answers", action="store_true", help="显示答案")
    p_quiz.set_defaults(func=cmd_quiz)

    # open
    p_open = sub.add_parser("open", help="用 PDF 查看器打开某节课的复习讲义")
    p_open.add_argument("--id", type=int, required=True, help="课程 ID")
    p_open.set_defaults(func=cmd_open)

    args = parser.parse_args()
    
    # 非 setup 命令自动确保 DB 存在
    if args.command != "setup":
        if not DB_PATH.exists():
            print("数据库不存在，正在自动初始化...")
            init_db()
        
    args.func(args)


if __name__ == "__main__":
    main()
