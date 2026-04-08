#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

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
import re
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
DEFAULT_DB_PATH = DATA_DIR / "xingrun.db"
LEGACY_DB_PATH = DATA_DIR / "lessons.db"
CFG_PATH   = BASE_DIR / "config.json"
CONSULTATIONS_CSV_PATH = DATA_DIR / "consultations.csv"
LEGACY_CONSULTATIONS_CSV_PATH = Path.home() / "咨询记录" / "consultations.csv"
DEFAULT_ORGANIZATION_NAME = "星润Starain"
OWNER_USERNAME = "kayn"
OWNER_DISPLAY_NAME = "平台管理员"
SUPER_OWNER_ROLE = "super_owner"
OWNER_ROLE = "owner"
ADMIN_ROLE = "admin"
MEMBER_ROLE = "member"
WECHAT_CHILD_REASON_INPUT_MODES = {"text", "voice"}
ORGANIZATION_REQUEST_PENDING = "pending"
ORGANIZATION_REQUEST_APPROVED = "approved"
ORGANIZATION_REQUEST_REJECTED = "rejected"
ORGANIZATION_INVITE_ACTIVE = "active"
ORGANIZATION_INVITE_REVOKED = "revoked"
CONSULTATION_TEACHERS_JSON_CANDIDATES = [
    DATA_DIR / "teachers.json",
    Path.home() / ".openclaw" / "workspace-wecom" / "teachers.json",
]
GRADE_NUMERAL_MAP = {
    1: "一",
    2: "二",
    3: "三",
    4: "四",
    5: "五",
    6: "六",
    7: "七",
    8: "八",
    9: "九",
    10: "十",
    11: "十一",
    12: "十二",
}
DEFAULT_CLASS_FEEDBACK_LABEL_GROUPS = [
    {"group": "课堂状态", "labels": ["进入状态快", "注意力更集中", "注意力波动", "开口更主动", "开口偏少"]},
    {"group": "学习表现", "labels": ["基础更稳", "知识点仍卡住", "纠错后保持更好", "完整表达有进步", "应用时还不稳定"]},
    {"group": "课后执行", "labels": ["作业完成更稳", "作业拖延", "复习配合度提升", "家长跟进较积极", "家庭练习不足"]},
    {"group": "阶段变化", "labels": ["进步明显", "有点回落", "变化不大", "情绪更稳定", "需要下阶段重点关注"]},
]
CONSULTATION_SOURCE_ALIASES = {
    "转介绍": {"转介绍", "介绍", "朋友介绍", "家长介绍", "熟人介绍", "亲友介绍", "老带新", "推荐介绍", "推荐"},
    "朋友圈": {"朋友圈", "微信朋友圈", "pyq"},
    "家长群": {"家长群", "微信群", "班级群", "群里", "社群"},
    "私信": {"私信", "微信私聊", "企微私聊", "单聊", "私聊"},
    "公众号": {"公众号", "微信公众号"},
    "小红书": {"小红书"},
    "抖音": {"抖音"},
    "视频号": {"视频号"},
    "校区到访": {"校区到访", "到访", "上门", "线下到访"},
    "其他": {"其他"},
}

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
    "来源渠道备注",
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
    "来源渠道备注",
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
    "source_channel_note": "来源渠道备注",
    "screenshot": "截图",
    "follow_up_status": "跟进状态",
    "follow_up_note": "跟进备注",
    "created_at": "录入时间",
    "updated_at": "最后更新",
}

DATA_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)


def _resolve_configured_db_path(raw_path: str | None, *, base_dir: Path) -> Optional[Path]:
    normalized_path = (raw_path or "").strip()
    if not normalized_path:
        return None
    configured_path = Path(normalized_path).expanduser()
    if not configured_path.is_absolute():
        configured_path = base_dir / configured_path
    return configured_path


def resolve_db_path(
    runtime_config: Optional[dict] = None,
    *,
    base_dir: Path = BASE_DIR,
    data_dir: Path = DATA_DIR,
) -> Path:
    resolved_runtime_config = runtime_config if runtime_config is not None else get_runtime_config()
    configured_path = _resolve_configured_db_path(
        resolved_runtime_config.get("db_path"),
        base_dir=base_dir,
    )
    if configured_path is not None:
        return configured_path

    preferred_path = data_dir / DEFAULT_DB_PATH.name
    legacy_path = data_dir / LEGACY_DB_PATH.name
    if preferred_path.exists():
        return preferred_path
    if legacy_path.exists():
        return legacy_path
    return preferred_path


DB_PATH = resolve_db_path()


def _normalize_username(username: str) -> str:
    return (username or "").strip()


def _is_owner_username(username: str) -> bool:
    return _normalize_username(username).casefold() == OWNER_USERNAME


def _is_super_owner_role(role: str) -> bool:
    return (role or "").strip() == SUPER_OWNER_ROLE


def _user_exists_with_username(conn: sqlite3.Connection, username: str, exclude_user_id: int = 0) -> bool:
    normalized_username = _normalize_username(username)
    if not normalized_username:
        return False
    query = "SELECT 1 FROM users WHERE lower(username)=lower(?)"
    params: list[object] = [normalized_username]
    if exclude_user_id:
        query += " AND id!=?"
        params.append(exclude_user_id)
    query += " LIMIT 1"
    return conn.execute(query, params).fetchone() is not None


def _pending_registration_exists(conn: sqlite3.Connection, username: str) -> bool:
    normalized_username = _normalize_username(username)
    if not normalized_username:
        return False
    return conn.execute(
        "SELECT 1 FROM registration_requests WHERE lower(username)=lower(?) AND status='pending' LIMIT 1",
        (normalized_username,),
    ).fetchone() is not None


def _organization_exists(conn: sqlite3.Connection, organization_name: str) -> bool:
    normalized_name = (organization_name or "").strip()
    if not normalized_name:
        return False
    return conn.execute(
        "SELECT 1 FROM organizations WHERE lower(name)=lower(?) LIMIT 1",
        (normalized_name,),
    ).fetchone() is not None


def _pending_organization_request_exists(conn: sqlite3.Connection, organization_name: str) -> bool:
    normalized_name = (organization_name or "").strip()
    if not normalized_name:
        return False
    return conn.execute(
        """
        SELECT 1
        FROM organization_requests
        WHERE lower(organization_name)=lower(?) AND status='pending'
        LIMIT 1
        """,
        (normalized_name,),
    ).fetchone() is not None


def _pending_organization_request_username_exists(conn: sqlite3.Connection, username: str) -> bool:
    normalized_username = _normalize_username(username)
    if not normalized_username:
        return False
    return conn.execute(
        """
        SELECT 1
        FROM organization_requests
        WHERE lower(username)=lower(?) AND status='pending'
        LIMIT 1
        """,
        (normalized_username,),
    ).fetchone() is not None


def _generate_invite_code(conn: sqlite3.Connection) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        invite_code = "".join(secrets.choice(alphabet) for _ in range(8))
        exists = conn.execute(
            "SELECT 1 FROM organization_invites WHERE invite_code=? LIMIT 1",
            (invite_code,),
        ).fetchone()
        if not exists:
            return invite_code


def _invite_link_from_token(token: str) -> str:
    return f"/join/{token}"


def _serialize_organization_invite(row: sqlite3.Row | None) -> Optional[dict]:
    if not row:
        return None
    invite_token = row["invite_token"]
    return {
        "id": row["id"],
        "organization_id": row["organization_id"],
        "organization_name": row["organization_name"],
        "invite_code": row["invite_code"],
        "invite_token": invite_token,
        "invite_link": _invite_link_from_token(invite_token),
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _revoke_active_invites(conn: sqlite3.Connection, organization_id: int) -> None:
    conn.execute(
        """
        UPDATE organization_invites
        SET status='revoked', revoked_at=datetime('now','localtime')
        WHERE organization_id=? AND status='active'
        """,
        (organization_id,),
    )


def _create_organization_invite(conn: sqlite3.Connection, organization_id: int, created_by: int) -> dict:
    invite_code = _generate_invite_code(conn)
    invite_token = secrets.token_urlsafe(24)
    cur = conn.execute(
        """
        INSERT INTO organization_invites (organization_id, invite_code, invite_token, status, created_by)
        VALUES (?, ?, ?, 'active', ?)
        """,
        (organization_id, invite_code, invite_token, created_by),
    )
    row = conn.execute(
        """
        SELECT oi.*, o.name AS organization_name
        FROM organization_invites oi
        JOIN organizations o ON o.id = oi.organization_id
        WHERE oi.id=?
        """,
        (cur.lastrowid,),
    ).fetchone()
    invite = _serialize_organization_invite(row)
    if invite is None:
        raise LookupError("invite not found")
    return invite


def _get_active_organization_invite_row_by_code(conn: sqlite3.Connection, invite_code: str):
    return conn.execute(
        """
        SELECT oi.*, o.name AS organization_name
        FROM organization_invites oi
        JOIN organizations o ON o.id = oi.organization_id
        WHERE oi.invite_code=? AND oi.status='active'
        LIMIT 1
        """,
        ((invite_code or "").strip(),),
    ).fetchone()


def _get_active_organization_invite_row_by_token(conn: sqlite3.Connection, invite_token: str):
    return conn.execute(
        """
        SELECT oi.*, o.name AS organization_name
        FROM organization_invites oi
        JOIN organizations o ON o.id = oi.organization_id
        WHERE oi.invite_token=? AND oi.status='active'
        LIMIT 1
        """,
        ((invite_token or "").strip(),),
    ).fetchone()
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
    normalized["年级"] = _normalize_consultation_grade(normalized.get("年级", ""))
    normalized["来源渠道"], normalized["来源渠道备注"] = _normalize_consultation_source_fields(
        normalized.get("来源渠道", ""),
        source_note=normalized.get("来源渠道备注", ""),
        parent_wechat_name=normalized.get("家长微信名", ""),
        child_name=normalized.get("孩子姓名", ""),
    )
    return normalized


def _normalize_consultation_grade(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    normalized = raw.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    normalized = re.sub(r"\s+", "", normalized)

    if re.fullmatch(r"[一二三四五六七八九十]{1,3}年级", normalized):
        return normalized
    if normalized in GRADE_NUMERAL_MAP.values():
        return f"{normalized}年级"

    match = re.fullmatch(r"(小学|小)([1-6])", normalized)
    if match:
        return f"{GRADE_NUMERAL_MAP[int(match.group(2))]}年级"
    match = re.fullmatch(r"(小学|小)([一二三四五六])", normalized)
    if match:
        return f"{match.group(2)}年级"

    match = re.fullmatch(r"([1-9]|10|11|12)年级?", normalized)
    if match:
        return f"{GRADE_NUMERAL_MAP[int(match.group(1))]}年级"

    match = re.fullmatch(r"(初|高)([1-3])", normalized)
    if match:
        return f"{match.group(1)}{GRADE_NUMERAL_MAP[int(match.group(2))]}"
    if re.fullmatch(r"(初|高)[一二三]", normalized):
        return normalized

    return raw


def _split_source_note(raw: str, matched_token: str) -> str:
    compact = re.sub(r"\s+", "", raw or "")
    if not compact or not matched_token:
        return ""
    note = compact.replace(matched_token, "", 1)
    return note.strip("：:，,、/\\-·()（）")


def _normalize_consultation_source_fields(
    value: str,
    *,
    source_note: str = "",
    parent_wechat_name: str = "",
    child_name: str = "",
) -> tuple[str, str]:
    raw = (value or "").strip()
    raw_note = (source_note or "").strip()
    if not raw:
        return "", raw_note
    compact = re.sub(r"\s+", "", raw)
    parent_compact = re.sub(r"\s+", "", (parent_wechat_name or "").strip())
    child_compact = re.sub(r"\s+", "", (child_name or "").strip())

    if compact and compact in {parent_compact, child_compact}:
        return "", ""

    for canonical, aliases in CONSULTATION_SOURCE_ALIASES.items():
        if compact == canonical or compact in aliases:
            return canonical, raw_note
    for canonical, aliases in CONSULTATION_SOURCE_ALIASES.items():
        if canonical in compact:
            return canonical, raw_note or _split_source_note(raw, canonical)
        for alias in aliases:
            if alias and alias in compact:
                return canonical, raw_note or _split_source_note(raw, alias)

    if re.fullmatch(r"[\u4e00-\u9fff]{2,6}", compact) and not any(keyword in compact for keyword in ("介绍", "群", "圈", "私", "号", "到访")):
        return "", ""
    if any(keyword in compact for keyword in ("妈妈", "爸爸", "家长", "老师")):
        return "", ""

    return raw, raw_note


def _normalize_consultation_source_channel(value: str, *, parent_wechat_name: str = "", child_name: str = "") -> str:
    source_channel, _ = _normalize_consultation_source_fields(
        value,
        parent_wechat_name=parent_wechat_name,
        child_name=child_name,
    )
    return source_channel


def clean_consultation_batch_input(raw_text: str) -> str:
    text = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned_lines: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if re.fullmatch(r"\[.*聊天记录.*\]", line):
            continue
        if re.fullmatch(r"[^：:\n]{1,20}\s+\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}", line):
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}", line):
            continue
        line = re.sub(r"\b\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}\b", "", line).strip()
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _load_consultation_teacher_aliases() -> dict[str, list[str]]:
    alias_map: dict[str, list[str]] = {}
    for teacher_file in CONSULTATION_TEACHERS_JSON_CANDIDATES:
        if not teacher_file.exists():
            continue
        try:
            aliases = json.loads(teacher_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for teacher_id, raw_aliases in aliases.items():
            teacher_key = str(teacher_id).strip()
            if not teacher_key:
                continue
            normalized_aliases: list[str] = []
            if isinstance(raw_aliases, list):
                normalized_aliases = [str(alias).strip() for alias in raw_aliases if str(alias).strip()]
            elif isinstance(raw_aliases, str):
                normalized_aliases = [alias.strip() for alias in raw_aliases.split(",") if alias.strip()]
            if not normalized_aliases:
                continue
            existing = alias_map.setdefault(teacher_key, [])
            for alias in normalized_aliases:
                if alias not in existing:
                    existing.append(alias)
    return alias_map


def _get_consultation_teacher_directory() -> dict[str, str]:
    alias_map = _load_consultation_teacher_aliases()
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
    for teacher_id, aliases in alias_map.items():
        teacher_key = teacher_id.lower()
        if not teacher_key:
            continue
        if aliases and teacher_key not in directory:
            directory[teacher_key] = aliases[0]
        if aliases:
            for alias in aliases:
                alias_key = alias.lower()
                if alias_key and alias_key not in directory:
                    directory[alias_key] = aliases[0]
    return directory


def list_consultation_teachers() -> list[dict]:
    alias_map = _load_consultation_teacher_aliases()
    teacher_entries: dict[str, dict] = {}

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT username, display_name
            FROM users
            WHERE status = 'active'
            ORDER BY display_name COLLATE NOCASE, username COLLATE NOCASE
            """
        ).fetchall()

    for row in rows:
        teacher_id = (row["username"] or "").strip()
        display_name = (row["display_name"] or "").strip()
        if not teacher_id:
            continue
        aliases = alias_map.get(teacher_id, [])
        merged_aliases: list[str] = []
        for alias in [display_name, *aliases]:
            normalized = alias.strip()
            if normalized and normalized not in merged_aliases:
                merged_aliases.append(normalized)
        teacher_entries[teacher_id] = {
            "teacher_id": teacher_id,
            "display_name": display_name or (merged_aliases[0] if merged_aliases else teacher_id),
            "aliases": merged_aliases,
        }

    for teacher_id, aliases in alias_map.items():
        if teacher_id in teacher_entries:
            entry = teacher_entries[teacher_id]
            for alias in aliases:
                if alias not in entry["aliases"]:
                    entry["aliases"].append(alias)
            if not entry["display_name"] and entry["aliases"]:
                entry["display_name"] = entry["aliases"][0]
            continue
        teacher_entries[teacher_id] = {
            "teacher_id": teacher_id,
            "display_name": aliases[0],
            "aliases": aliases[:],
        }

    return sorted(
        teacher_entries.values(),
        key=lambda item: ((item["display_name"] or item["teacher_id"]).lower(), item["teacher_id"].lower()),
    )


def _normalize_consultation_teacher_assignment(receiving_teacher: str, teacher_id: str = "") -> tuple[str, str]:
    teacher_value = (receiving_teacher or "").strip()
    teacher_id_value = (teacher_id or "").strip()
    if not teacher_value and not teacher_id_value:
        return "", ""

    for item in list_consultation_teachers():
        candidates = {item.get("teacher_id", "").strip().lower()}
        display_name = (item.get("display_name") or "").strip()
        if display_name:
            candidates.add(display_name.lower())
        for alias in item.get("aliases", []):
            alias_value = str(alias).strip().lower()
            if alias_value:
                candidates.add(alias_value)
        if teacher_value and teacher_value.lower() in candidates:
            return display_name or teacher_value, item.get("teacher_id", "")
        if teacher_id_value and teacher_id_value.lower() in candidates:
            return display_name or teacher_value or teacher_id_value, item.get("teacher_id", "")

    return teacher_value, teacher_id_value


def _serialize_consultation_row(row: dict, teacher_directory: Optional[dict[str, str]] = None) -> dict:
    serialized = dict(row)
    serialized["id"] = int(serialized["id"]) if serialized.get("id") else 0
    serialized["年级"] = _normalize_consultation_grade(serialized.get("年级", ""))
    serialized["来源渠道"], serialized["来源渠道备注"] = _normalize_consultation_source_fields(
        serialized.get("来源渠道", ""),
        source_note=serialized.get("来源渠道备注", ""),
        parent_wechat_name=serialized.get("家长微信名", ""),
        child_name=serialized.get("孩子姓名", ""),
    )
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


def _normalize_consultation_batch_fields(fields: Optional[dict]) -> dict[str, str]:
    if fields is None:
        fields = {}
    if not isinstance(fields, dict):
        raise ValueError("AI 解析返回了无效结果")
    updates = _extract_consultation_updates(fields or {})
    normalized: dict[str, str] = {}
    for api_field, csv_field in CONSULTATION_API_FIELD_MAP.items():
        if csv_field in CONSULTATION_EDITABLE_FIELDS and csv_field in updates:
            normalized[api_field] = updates[csv_field]

    if "grade" in normalized:
        normalized["grade"] = _normalize_consultation_grade(normalized.get("grade", ""))

    receiving_teacher, teacher_id = _normalize_consultation_teacher_assignment(
        normalized.get("receiving_teacher", ""),
        normalized.get("teacher_id", ""),
    )
    if receiving_teacher:
        normalized["receiving_teacher"] = receiving_teacher
    if teacher_id:
        normalized["teacher_id"] = teacher_id

    source_channel, source_note = _normalize_consultation_source_fields(
        normalized.get("source_channel", ""),
        source_note=normalized.get("source_channel_note", ""),
        parent_wechat_name=normalized.get("parent_wechat_name", ""),
        child_name=normalized.get("child_name", ""),
    )
    if source_channel or "source_channel" in normalized:
        normalized["source_channel"] = source_channel
    if source_note or "source_channel_note" in normalized:
        normalized["source_channel_note"] = source_note

    return normalized


def normalize_consultation_batch_parse_result(payload: Optional[dict]) -> dict:
    data = payload or {}
    if not isinstance(data, dict):
        raise ValueError("AI 解析返回了无效结果")

    raw_items = data.get("items", [])
    if not isinstance(raw_items, list):
        raise ValueError("AI 解析返回了无效结果")

    raw_warnings = data.get("warnings", [])
    if raw_warnings is None:
        raw_warnings = []
    if not isinstance(raw_warnings, list):
        raise ValueError("AI 解析返回了无效结果")

    items = []
    warnings = [
        str(item).strip()
        for item in raw_warnings
        if str(item).strip()
    ]
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise ValueError("AI 解析返回了无效结果")
        action = str(raw_item.get("action", "create")).strip().lower()
        target_id = raw_item.get("target_id")
        normalized_target_id = None
        if action == "update" and target_id not in (None, ""):
            try:
                normalized_target_id = int(target_id)
            except (TypeError, ValueError):
                normalized_target_id = None
        if normalized_target_id is None:
            action = "create"
        normalized_fields = _normalize_consultation_batch_fields(raw_item.get("fields"))
        if action == "update":
            normalized_fields = {
                field: value
                for field, value in normalized_fields.items()
                if value.strip() != ""
            }
            if not normalized_fields:
                warnings.append(
                    f"显式记录 ID {normalized_target_id} 的更新草稿已跳过，因为清洗后没有剩余有效字段。"
                )
                continue
        items.append(
            {
                "action": action,
                "target_id": normalized_target_id if action == "update" else None,
                "reason": str(raw_item.get("reason", "")).strip(),
                "fields": normalized_fields,
                "warnings": [
                    str(item).strip()
                    for item in (raw_item.get("warnings", []) if isinstance(raw_item.get("warnings", []), list) else [])
                    if str(item).strip()
                ],
            }
        )
    return {
        "items": items,
        "warnings": warnings,
    }


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


def list_consultations(query: str = "", organization_id: Optional[int] = None) -> list[dict]:
    teacher_directory = _get_consultation_teacher_directory()
    with get_conn() as conn:
        query_sql = "SELECT * FROM consultations"
        params: list[object] = []
        if organization_id is not None:
            query_sql += " WHERE organization_id=?"
            params.append(organization_id)
        query_sql += " ORDER BY updated_at DESC, created_at DESC, id DESC"
        rows = conn.execute(query_sql, params).fetchall()

    serialized_rows = [
        _consultation_storage_row_to_public_dict(row, teacher_directory)
        for row in rows
    ]
    keyword = (query or "").strip().lower()
    if keyword:
        serialized_rows = [
            row for row in serialized_rows
            if keyword in " ".join(row.get(field, "").lower() for field in CONSULTATION_FIELDNAMES)
        ]
    return serialized_rows


def get_consultation(consultation_id: int, organization_id: Optional[int] = None):
    teacher_directory = _get_consultation_teacher_directory()
    with get_conn() as conn:
        query_sql = "SELECT * FROM consultations WHERE id=?"
        params: list[object] = [consultation_id]
        if organization_id is not None:
            query_sql += " AND organization_id=?"
            params.append(organization_id)
        row = conn.execute(query_sql, params).fetchone()
    return _consultation_storage_row_to_public_dict(row, teacher_directory) if row else None


def create_consultation(data: dict, organization_id: int) -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_row = {field: "" for field in CONSULTATION_FIELDNAMES}
    new_row["录入时间"] = now
    new_row["最后更新"] = now
    for field, value in _extract_consultation_updates(data).items():
        new_row[field] = value
    if not new_row["日期"]:
        new_row["日期"] = str(date.today())
    stored = _consultation_row_to_storage(new_row, organization_id)
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO consultations (
                organization_id, date, parent_wechat_name, child_name, grade,
                receiving_teacher, teacher_id, consultation_subject, need_detail,
                source_channel, source_channel_note, screenshot, reminder_at,
                reminder_status, reminder_task_id, follow_up_status, follow_up_note,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                organization_id,
                stored["date"] or str(date.today()),
                stored["parent_wechat_name"],
                stored["child_name"],
                stored["grade"],
                stored["receiving_teacher"],
                stored["teacher_id"],
                stored["consultation_subject"],
                stored["need_detail"],
                stored["source_channel"],
                stored["source_channel_note"],
                stored["screenshot"],
                stored["reminder_at"],
                stored["reminder_status"],
                stored["reminder_task_id"],
                stored["follow_up_status"],
                stored["follow_up_note"],
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM consultations WHERE id=?", (cur.lastrowid,)).fetchone()
    return _consultation_storage_row_to_public_dict(row, _get_consultation_teacher_directory())


def update_consultation(consultation_id: int, data: dict, organization_id: Optional[int] = None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    teacher_directory = _get_consultation_teacher_directory()
    with get_conn() as conn:
        query_sql = "SELECT * FROM consultations WHERE id=?"
        params: list[object] = [consultation_id]
        if organization_id is not None:
            query_sql += " AND organization_id=?"
            params.append(organization_id)
        current = conn.execute(query_sql, params).fetchone()
        if not current:
            return None

        public_row = _consultation_storage_row_to_public_dict(current, teacher_directory)
        for field, value in _extract_consultation_updates(data).items():
            public_row[field] = value
        stored = _consultation_row_to_storage(public_row, current["organization_id"])
        conn.execute(
            """
            UPDATE consultations
            SET date=?,
                parent_wechat_name=?,
                child_name=?,
                grade=?,
                receiving_teacher=?,
                teacher_id=?,
                consultation_subject=?,
                need_detail=?,
                source_channel=?,
                source_channel_note=?,
                screenshot=?,
                follow_up_status=?,
                follow_up_note=?,
                updated_at=?
            WHERE id=?
            """,
            (
                stored["date"],
                stored["parent_wechat_name"],
                stored["child_name"],
                stored["grade"],
                stored["receiving_teacher"],
                stored["teacher_id"],
                stored["consultation_subject"],
                stored["need_detail"],
                stored["source_channel"],
                stored["source_channel_note"],
                stored["screenshot"],
                stored["follow_up_status"],
                stored["follow_up_note"],
                now,
                consultation_id,
            ),
        )
        updated = conn.execute("SELECT * FROM consultations WHERE id=?", (consultation_id,)).fetchone()
    return _consultation_storage_row_to_public_dict(updated, teacher_directory)


def delete_consultation(consultation_id: int, organization_id: Optional[int] = None) -> bool:
    with get_conn() as conn:
        query_sql = "DELETE FROM consultations WHERE id=?"
        params: list[object] = [consultation_id]
        if organization_id is not None:
            query_sql += " AND organization_id=?"
            params.append(organization_id)
        cur = conn.execute(query_sql, params)
    return cur.rowcount > 0


# ─── 数据库 ────────────────────────────────────────────────────────────────────
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column in columns:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _consultation_row_to_storage(row: dict, organization_id: int) -> dict[str, str | int]:
    teacher_directory = _get_consultation_teacher_directory()
    serialized = _serialize_consultation_row(row, teacher_directory)
    return {
        "organization_id": organization_id,
        "date": serialized.get("date", ""),
        "parent_wechat_name": serialized.get("parent_wechat_name", ""),
        "child_name": serialized.get("child_name", ""),
        "grade": serialized.get("grade", ""),
        "receiving_teacher": serialized.get("receiving_teacher", ""),
        "teacher_id": serialized.get("teacher_id", ""),
        "consultation_subject": serialized.get("consultation_subject", ""),
        "need_detail": serialized.get("need_detail", ""),
        "source_channel": serialized.get("source_channel", ""),
        "source_channel_note": serialized.get("source_channel_note", ""),
        "screenshot": serialized.get("screenshot", ""),
        "reminder_at": serialized.get("提醒时间", ""),
        "reminder_status": serialized.get("提醒状态", ""),
        "reminder_task_id": serialized.get("提醒任务ID", ""),
        "follow_up_status": serialized.get("follow_up_status", ""),
        "follow_up_note": serialized.get("follow_up_note", ""),
        "created_at": serialized.get("created_at", ""),
        "updated_at": serialized.get("updated_at", ""),
    }


def _consultation_storage_row_to_public_dict(
    row: sqlite3.Row | dict,
    teacher_directory: Optional[dict[str, str]] = None,
) -> dict:
    payload = dict(row)
    legacy_row = {field: "" for field in CONSULTATION_FIELDNAMES}
    legacy_row["id"] = str(payload.get("id") or "")
    legacy_row["日期"] = payload.get("date", "") or ""
    legacy_row["家长微信名"] = payload.get("parent_wechat_name", "") or ""
    legacy_row["孩子姓名"] = payload.get("child_name", "") or ""
    legacy_row["年级"] = payload.get("grade", "") or ""
    legacy_row["接待老师"] = payload.get("receiving_teacher", "") or ""
    legacy_row["老师ID"] = payload.get("teacher_id", "") or ""
    legacy_row["咨询科目"] = payload.get("consultation_subject", "") or ""
    legacy_row["具体需求"] = payload.get("need_detail", "") or ""
    legacy_row["来源渠道"] = payload.get("source_channel", "") or ""
    legacy_row["来源渠道备注"] = payload.get("source_channel_note", "") or ""
    legacy_row["截图"] = payload.get("screenshot", "") or ""
    legacy_row["提醒时间"] = payload.get("reminder_at", "") or ""
    legacy_row["提醒状态"] = payload.get("reminder_status", "") or ""
    legacy_row["提醒任务ID"] = payload.get("reminder_task_id", "") or ""
    legacy_row["跟进状态"] = payload.get("follow_up_status", "") or ""
    legacy_row["跟进备注"] = payload.get("follow_up_note", "") or ""
    legacy_row["录入时间"] = payload.get("created_at", "") or ""
    legacy_row["最后更新"] = payload.get("updated_at", "") or ""
    serialized = _serialize_consultation_row(legacy_row, teacher_directory)
    serialized["organization_id"] = payload.get("organization_id")
    return serialized


def _ensure_consultations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS consultations (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id      INTEGER NOT NULL REFERENCES organizations(id),
            date                 TEXT DEFAULT '',
            parent_wechat_name   TEXT DEFAULT '',
            child_name           TEXT DEFAULT '',
            grade                TEXT DEFAULT '',
            receiving_teacher    TEXT DEFAULT '',
            teacher_id           TEXT DEFAULT '',
            consultation_subject TEXT DEFAULT '',
            need_detail          TEXT DEFAULT '',
            source_channel       TEXT DEFAULT '',
            source_channel_note  TEXT DEFAULT '',
            screenshot           TEXT DEFAULT '',
            reminder_at          TEXT DEFAULT '',
            reminder_status      TEXT DEFAULT '',
            reminder_task_id     TEXT DEFAULT '',
            follow_up_status     TEXT DEFAULT '',
            follow_up_note       TEXT DEFAULT '',
            created_at           TEXT DEFAULT (datetime('now','localtime')),
            updated_at           TEXT DEFAULT (datetime('now','localtime'))
        )
        """
    )


def _migrate_legacy_organization_scope(conn: sqlite3.Connection) -> None:
    starain = _ensure_organization(conn, DEFAULT_ORGANIZATION_NAME)
    _ensure_column(conn, "classes", "organization_id", "INTEGER REFERENCES organizations(id)")
    _ensure_column(conn, "lessons", "organization_id", "INTEGER REFERENCES organizations(id)")
    _ensure_consultations_table(conn)

    conn.execute(
        "UPDATE classes SET organization_id=? WHERE organization_id IS NULL",
        (starain["id"],),
    )
    conn.execute(
        """
        UPDATE lessons
        SET organization_id=COALESCE(
            organization_id,
            (SELECT c.organization_id FROM classes c WHERE c.id = lessons.class_id),
            ?
        )
        WHERE organization_id IS NULL
        """,
        (starain["id"],),
    )

    consultation_count = conn.execute("SELECT COUNT(*) AS c FROM consultations").fetchone()["c"]
    if consultation_count:
        return

    legacy_rows = _read_consultation_rows()
    if not legacy_rows:
        return

    for row in legacy_rows:
        stored = _consultation_row_to_storage(row, starain["id"])
        conn.execute(
            """
            INSERT INTO consultations (
                id, organization_id, date, parent_wechat_name, child_name, grade,
                receiving_teacher, teacher_id, consultation_subject, need_detail,
                source_channel, source_channel_note, screenshot, reminder_at,
                reminder_status, reminder_task_id, follow_up_status, follow_up_note,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(row["id"]) if row.get("id") else None,
                stored["organization_id"],
                stored["date"],
                stored["parent_wechat_name"],
                stored["child_name"],
                stored["grade"],
                stored["receiving_teacher"],
                stored["teacher_id"],
                stored["consultation_subject"],
                stored["need_detail"],
                stored["source_channel"],
                stored["source_channel_note"],
                stored["screenshot"],
                stored["reminder_at"],
                stored["reminder_status"],
                stored["reminder_task_id"],
                stored["follow_up_status"],
                stored["follow_up_note"],
                stored["created_at"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                stored["updated_at"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS classes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER REFERENCES organizations(id),
            name         TEXT NOT NULL,
            subject      TEXT DEFAULT '',
            grade        TEXT DEFAULT '',
            teacher_name TEXT DEFAULT '',
            teacher_email TEXT DEFAULT '',
            created_at   TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS lessons (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER REFERENCES organizations(id),
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

        CREATE TABLE IF NOT EXISTS organization_requests (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_name TEXT NOT NULL,
            username          TEXT NOT NULL,
            password_hash     TEXT NOT NULL,
            display_name      TEXT NOT NULL,
            status            TEXT NOT NULL DEFAULT 'pending',
            reviewed_by       INTEGER REFERENCES users(id),
            reviewed_at       TEXT,
            created_at        TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS organization_invites (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            invite_code     TEXT NOT NULL UNIQUE,
            invite_token    TEXT NOT NULL UNIQUE,
            status          TEXT NOT NULL DEFAULT 'active',
            created_by      INTEGER REFERENCES users(id),
            revoked_at      TEXT,
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

        CREATE TABLE IF NOT EXISTS students (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS class_students (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id    INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            student_id  INTEGER NOT NULL REFERENCES students(id),
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(class_id, student_id)
        );

        CREATE TABLE IF NOT EXISTS class_invite_codes (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id     INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            class_id            INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            invite_code         TEXT NOT NULL UNIQUE,
            status              TEXT NOT NULL DEFAULT 'active',
            created_by_user_id  INTEGER REFERENCES users(id),
            expires_at          TEXT,
            revoked_at          TEXT,
            created_at          TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS parent_wechat_accounts (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            openid                TEXT NOT NULL UNIQUE,
            nickname_snapshot     TEXT NOT NULL DEFAULT '',
            avatar_url_snapshot   TEXT NOT NULL DEFAULT '',
            status                TEXT NOT NULL DEFAULT 'active',
            created_at            TEXT DEFAULT (datetime('now','localtime')),
            updated_at            TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS parent_student_bindings (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id           INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            parent_wechat_account_id  INTEGER NOT NULL REFERENCES parent_wechat_accounts(id) ON DELETE CASCADE,
            class_id                  INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            student_id                INTEGER NOT NULL REFERENCES students(id),
            teacher_user_id           INTEGER NOT NULL REFERENCES users(id),
            status                    TEXT NOT NULL DEFAULT 'active',
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(parent_wechat_account_id, class_id, student_id, status)
        );

        CREATE TABLE IF NOT EXISTS wrong_question_submissions (
            id                        TEXT PRIMARY KEY,
            organization_id           INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            source                    TEXT NOT NULL DEFAULT 'wechat_mp',
            parent_wechat_account_id  INTEGER NOT NULL REFERENCES parent_wechat_accounts(id) ON DELETE CASCADE,
            binding_id                INTEGER NOT NULL REFERENCES parent_student_bindings(id) ON DELETE CASCADE,
            class_id                  INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            student_id                INTEGER NOT NULL REFERENCES students(id),
            teacher_user_id           INTEGER NOT NULL REFERENCES users(id),
            image_url                 TEXT NOT NULL,
            parent_note               TEXT NOT NULL DEFAULT '',
            child_raw_reason_text     TEXT NOT NULL DEFAULT '',
            child_reason_input_mode   TEXT NOT NULL DEFAULT 'text',
            primary_error_type        TEXT NOT NULL DEFAULT '',
            secondary_error_summary   TEXT NOT NULL DEFAULT '',
            archive_status            TEXT NOT NULL DEFAULT 'active',
            archived_at               TEXT DEFAULT '',
            teacher_comment           TEXT NOT NULL DEFAULT '',
            status                    TEXT NOT NULL DEFAULT 'pending',
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS organization_credit_accounts (
            organization_id INTEGER PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
            credit_balance INTEGER NOT NULL DEFAULT 0,
            total_recharged INTEGER NOT NULL DEFAULT 0,
            total_consumed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS organization_credit_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            direction TEXT NOT NULL CHECK(direction IN ('credit','debit')),
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            source_id TEXT,
            note TEXT NOT NULL DEFAULT '',
            operator_user_id INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS xhs_order_redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'xiaohongshu',
            platform_order_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            sku_id TEXT NOT NULL DEFAULT '',
            product_name TEXT NOT NULL,
            paid_amount INTEGER NOT NULL,
            currency TEXT NOT NULL DEFAULT 'CNY',
            buyer_masked_phone TEXT NOT NULL DEFAULT '',
            order_status TEXT NOT NULL,
            redeem_status TEXT NOT NULL DEFAULT 'pending',
            credit_amount INTEGER NOT NULL,
            redeemed_organization_id INTEGER REFERENCES organizations(id),
            redeemed_by_user_id INTEGER REFERENCES users(id),
            redeemed_at TEXT,
            raw_order_payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(platform, platform_order_id)
        );

        CREATE TABLE IF NOT EXISTS ai_usage_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            feature_key TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            token_cost_raw REAL NOT NULL DEFAULT 0,
            credit_cost_final INTEGER NOT NULL,
            source_record_type TEXT NOT NULL,
            source_record_id TEXT NOT NULL,
            request_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_usage_ledger_org_request_id
        ON ai_usage_ledger (organization_id, request_id)
        WHERE request_id <> '';

        CREATE TABLE IF NOT EXISTS lesson_feedbacks (
            lesson_id           INTEGER PRIMARY KEY REFERENCES lessons(id) ON DELETE CASCADE,
            class_id            INTEGER REFERENCES classes(id) ON DELETE SET NULL,
            merged_text         TEXT DEFAULT '',
            student_index_json  TEXT DEFAULT '[]',
            editor_state_json   TEXT DEFAULT '{}',
            created_at          TEXT DEFAULT (datetime('now','localtime')),
            updated_at          TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS class_feedback_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            teacher_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            teacher_name_snapshot TEXT NOT NULL DEFAULT '',
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            period_length_days INTEGER NOT NULL DEFAULT 1,
            period_granularity TEXT NOT NULL DEFAULT 'daily',
            status TEXT NOT NULL DEFAULT 'draft',
            class_summary_ai_draft TEXT NOT NULL DEFAULT '',
            class_summary_final_text TEXT NOT NULL DEFAULT '',
            class_status_tags_json TEXT NOT NULL DEFAULT '[]',
            class_status_note TEXT NOT NULL DEFAULT '',
            parent_feedback_note TEXT NOT NULL DEFAULT '',
            teaching_focus_note TEXT NOT NULL DEFAULT '',
            next_stage_preview_note TEXT NOT NULL DEFAULT '',
            student_highlights_json TEXT NOT NULL DEFAULT '[]',
            created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            confirmed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS class_feedback_student_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES class_feedback_tasks(id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            student_name_snapshot TEXT NOT NULL DEFAULT '',
            ai_draft TEXT NOT NULL DEFAULT '',
            final_text TEXT NOT NULL DEFAULT '',
            checked_at TEXT,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS class_feedback_label_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            label_group TEXT NOT NULL,
            label_text TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            is_system_default INTEGER NOT NULL DEFAULT 0
        );
        """)
        import master_data

        master_data.ensure_schema(conn)
        # Safe migration: add class_id if not already present
        cols = [r[1] for r in conn.execute("PRAGMA table_info(lessons)").fetchall()]
        if "class_id" not in cols:
            conn.execute("ALTER TABLE lessons ADD COLUMN class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL")

        feedback_cols = [r[1] for r in conn.execute("PRAGMA table_info(lesson_feedbacks)").fetchall()]
        if feedback_cols:
            if "class_id" not in feedback_cols:
                conn.execute("ALTER TABLE lesson_feedbacks ADD COLUMN class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL")
            if "merged_text" not in feedback_cols:
                conn.execute("ALTER TABLE lesson_feedbacks ADD COLUMN merged_text TEXT DEFAULT ''")
            if "student_index_json" not in feedback_cols:
                conn.execute("ALTER TABLE lesson_feedbacks ADD COLUMN student_index_json TEXT DEFAULT '[]'")
            if "editor_state_json" not in feedback_cols:
                conn.execute("ALTER TABLE lesson_feedbacks ADD COLUMN editor_state_json TEXT DEFAULT '{}'")
            if "created_at" not in feedback_cols:
                conn.execute("ALTER TABLE lesson_feedbacks ADD COLUMN created_at TEXT DEFAULT (datetime('now','localtime'))")
        if "updated_at" not in feedback_cols:
            conn.execute("ALTER TABLE lesson_feedbacks ADD COLUMN updated_at TEXT DEFAULT (datetime('now','localtime'))")
        class_feedback_task_cols = [r[1] for r in conn.execute("PRAGMA table_info(class_feedback_tasks)").fetchall()]
        if class_feedback_task_cols:
            if "class_status_tags_json" not in class_feedback_task_cols:
                conn.execute("ALTER TABLE class_feedback_tasks ADD COLUMN class_status_tags_json TEXT NOT NULL DEFAULT '[]'")
            if "class_status_note" not in class_feedback_task_cols:
                conn.execute("ALTER TABLE class_feedback_tasks ADD COLUMN class_status_note TEXT NOT NULL DEFAULT ''")
            if "parent_feedback_note" not in class_feedback_task_cols:
                conn.execute("ALTER TABLE class_feedback_tasks ADD COLUMN parent_feedback_note TEXT NOT NULL DEFAULT ''")
            if "teaching_focus_note" not in class_feedback_task_cols:
                conn.execute("ALTER TABLE class_feedback_tasks ADD COLUMN teaching_focus_note TEXT NOT NULL DEFAULT ''")
            if "next_stage_preview_note" not in class_feedback_task_cols:
                conn.execute("ALTER TABLE class_feedback_tasks ADD COLUMN next_stage_preview_note TEXT NOT NULL DEFAULT ''")
            if "student_highlights_json" not in class_feedback_task_cols:
                conn.execute("ALTER TABLE class_feedback_tasks ADD COLUMN student_highlights_json TEXT NOT NULL DEFAULT '[]'")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_class_feedback_student_entries_task_student
            ON class_feedback_student_entries(task_id, student_id)
            """
        )
        conn.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS trg_class_feedback_tasks_teacher_binding_insert
            BEFORE INSERT ON class_feedback_tasks
            WHEN NEW.teacher_user_id IS NOT NULL
            BEGIN
                SELECT RAISE(ABORT, 'teacher_user_id must match class binding')
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM user_classes uc
                    WHERE uc.class_id = NEW.class_id
                      AND uc.user_id = NEW.teacher_user_id
                );
            END;

            CREATE TRIGGER IF NOT EXISTS trg_class_feedback_tasks_teacher_binding_update
            BEFORE UPDATE OF class_id, teacher_user_id ON class_feedback_tasks
            WHEN NEW.teacher_user_id IS NOT NULL
            BEGIN
                SELECT RAISE(ABORT, 'teacher_user_id must match class binding')
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM user_classes uc
                    WHERE uc.class_id = NEW.class_id
                      AND uc.user_id = NEW.teacher_user_id
                );
            END;

            CREATE TRIGGER IF NOT EXISTS trg_class_feedback_student_entries_roster_insert
            BEFORE INSERT ON class_feedback_student_entries
            BEGIN
                SELECT RAISE(ABORT, 'student_id must belong to task roster')
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM class_feedback_tasks t
                    JOIN class_students cs
                      ON cs.class_id = t.class_id
                     AND cs.student_id = NEW.student_id
                    WHERE t.id = NEW.task_id
                );
            END;

            CREATE TRIGGER IF NOT EXISTS trg_class_feedback_student_entries_roster_update
            BEFORE UPDATE OF task_id, student_id ON class_feedback_student_entries
            BEGIN
                SELECT RAISE(ABORT, 'student_id must belong to task roster')
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM class_feedback_tasks t
                    JOIN class_students cs
                      ON cs.class_id = t.class_id
                     AND cs.student_id = NEW.student_id
                    WHERE t.id = NEW.task_id
                );
            END;
            """
        )
        _migrate_legacy_organization_scope(conn)
        _bootstrap_account_state(conn)
        user_cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "last_login" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN last_login TEXT DEFAULT NULL")
        _ensure_column(conn, "wrong_question_submissions", "child_raw_reason_text", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "child_reason_input_mode", "TEXT NOT NULL DEFAULT 'text'")
        _ensure_column(conn, "wrong_question_submissions", "primary_error_type", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "secondary_error_summary", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "archive_status", "TEXT NOT NULL DEFAULT 'active'")
        _ensure_column(conn, "wrong_question_submissions", "archived_at", "TEXT DEFAULT ''")
    print(f"数据库已初始化：{DB_PATH}")


def _ensure_credit_account_row(conn: sqlite3.Connection, organization_id: int) -> sqlite3.Row:
    org_row = conn.execute("SELECT id FROM organizations WHERE id=?", (organization_id,)).fetchone()
    if not org_row:
        raise LookupError("organization not found")

    conn.execute(
        """
        INSERT INTO organization_credit_accounts (organization_id)
        VALUES (?)
        ON CONFLICT(organization_id) DO NOTHING
        """,
        (organization_id,),
    )
    account_row = conn.execute(
        "SELECT * FROM organization_credit_accounts WHERE organization_id=?",
        (organization_id,),
    ).fetchone()
    if not account_row:
        raise LookupError("credit account not found")
    return account_row


def ensure_credit_account(organization_id: int) -> dict:
    with get_conn() as conn:
        return dict(_ensure_credit_account_row(conn, organization_id))


def _ensure_user_in_organization(conn: sqlite3.Connection, user_id: int, organization_id: int, label: str) -> None:
    row = conn.execute(
        "SELECT organization_id FROM users WHERE id=?",
        (user_id,),
    ).fetchone()
    if not row:
        raise LookupError(f"{label} user not found")
    if int(row["organization_id"]) != int(organization_id):
        raise ValueError(f"{label} user does not belong to organization")


def _insert_credit_ledger_entry_with_conn(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    direction: str,
    amount: int,
    source_type: str,
    source_id: str = "",
    note: str = "",
    operator_user_id: Optional[int] = None,
) -> dict:
    normalized_direction = (direction or "").strip().lower()
    if normalized_direction not in {"credit", "debit"}:
        raise ValueError("direction must be credit or debit")
    if amount <= 0:
        raise ValueError("amount must be positive")
    if operator_user_id is not None:
        _ensure_user_in_organization(conn, operator_user_id, organization_id, "operator")

    account_row = _ensure_credit_account_row(conn, organization_id)
    balance_before = int(account_row["credit_balance"] or 0)
    recharge_before = int(account_row["total_recharged"] or 0)
    consumed_before = int(account_row["total_consumed"] or 0)

    if normalized_direction == "credit":
        balance_after = balance_before + amount
        total_recharged = recharge_before + amount
        total_consumed = consumed_before
    else:
        if balance_before < amount:
            raise ValueError("insufficient credit balance")
        balance_after = balance_before - amount
        total_recharged = recharge_before
        total_consumed = consumed_before + amount

    conn.execute(
        """
        UPDATE organization_credit_accounts
        SET credit_balance=?,
            total_recharged=?,
            total_consumed=?,
            updated_at=datetime('now','localtime')
        WHERE organization_id=?
        """,
        (balance_after, total_recharged, total_consumed, organization_id),
    )
    cur = conn.execute(
        """
        INSERT INTO organization_credit_ledger
            (organization_id, direction, amount, balance_after, source_type, source_id, note, operator_user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id,
            normalized_direction,
            amount,
            balance_after,
            source_type,
            source_id,
            note,
            operator_user_id,
        ),
    )
    row = conn.execute(
        "SELECT * FROM organization_credit_ledger WHERE id=?",
        (cur.lastrowid,),
    ).fetchone()
    return dict(row) if row else {}


def insert_credit_ledger_entry(
    *,
    organization_id: int,
    direction: str,
    amount: int,
    source_type: str,
    source_id: str = "",
    note: str = "",
    operator_user_id: Optional[int] = None,
) -> dict:
    with get_conn() as conn:
        return _insert_credit_ledger_entry_with_conn(
            conn,
            organization_id=organization_id,
            direction=direction,
            amount=amount,
            source_type=source_type,
            source_id=source_id,
            note=note,
            operator_user_id=operator_user_id,
        )


def _insert_ai_usage_row_with_conn(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    user_id: int,
    feature_key: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    credit_cost_final: int,
    source_record_type: str,
    source_record_id: str,
    request_id: str,
    token_cost_raw: float = 0.0,
) -> dict:
    _ensure_credit_account_row(conn, organization_id)
    _ensure_user_in_organization(conn, user_id, organization_id, "usage")

    total_tokens = max(0, int(input_tokens)) + max(0, int(output_tokens))
    normalized_request_id = (request_id or "").strip()
    cur = conn.execute(
        """
        INSERT INTO ai_usage_ledger
            (organization_id, user_id, feature_key, provider, model, input_tokens, output_tokens, total_tokens,
             token_cost_raw, credit_cost_final, source_record_type, source_record_id, request_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id,
            user_id,
            feature_key,
            provider,
            model,
            max(0, int(input_tokens)),
            max(0, int(output_tokens)),
            total_tokens,
            float(token_cost_raw or 0.0),
            int(credit_cost_final),
            source_record_type,
            str(source_record_id),
            normalized_request_id,
        ),
    )
    row = conn.execute(
        "SELECT * FROM ai_usage_ledger WHERE id=?",
        (cur.lastrowid,),
    ).fetchone()
    return dict(row) if row else {}


def insert_ai_usage_row(
    *,
    organization_id: int,
    user_id: int,
    feature_key: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    credit_cost_final: int,
    source_record_type: str,
    source_record_id: str,
    request_id: str,
    token_cost_raw: float = 0.0,
) -> dict:
    with get_conn() as conn:
        return _insert_ai_usage_row_with_conn(
            conn,
            organization_id=organization_id,
            user_id=user_id,
            feature_key=feature_key,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            credit_cost_final=credit_cost_final,
            source_record_type=source_record_type,
            source_record_id=source_record_id,
            request_id=request_id,
            token_cost_raw=token_cost_raw,
        )


def insert_ai_usage_and_debit(
    *,
    organization_id: int,
    user_id: int,
    feature_key: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    credit_cost_final: int,
    source_record_type: str,
    source_record_id: str,
    request_id: str,
    token_cost_raw: float = 0.0,
) -> dict:
    normalized_request_id = (request_id or "").strip()
    with get_conn() as conn:
        _ensure_credit_account_row(conn, organization_id)
        _ensure_user_in_organization(conn, user_id, organization_id, "usage")

        if normalized_request_id:
            existing = conn.execute(
                """
                SELECT *
                FROM ai_usage_ledger
                WHERE organization_id=? AND request_id=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (organization_id, normalized_request_id),
            ).fetchone()
            if existing:
                return dict(existing)

        try:
            usage_row = _insert_ai_usage_row_with_conn(
                conn,
                organization_id=organization_id,
                user_id=user_id,
                feature_key=feature_key,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                credit_cost_final=credit_cost_final,
                source_record_type=source_record_type,
                source_record_id=source_record_id,
                request_id=normalized_request_id,
                token_cost_raw=token_cost_raw,
            )
        except sqlite3.IntegrityError:
            if not normalized_request_id:
                raise
            existing = conn.execute(
                """
                SELECT *
                FROM ai_usage_ledger
                WHERE organization_id=? AND request_id=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (organization_id, normalized_request_id),
            ).fetchone()
            if not existing:
                raise
            return dict(existing)

        _insert_credit_ledger_entry_with_conn(
            conn,
            organization_id=organization_id,
            direction="debit",
            amount=int(credit_cost_final),
            source_type="ai_usage",
            source_id=str(usage_row["id"]),
            note=feature_key,
            operator_user_id=user_id,
        )
        return usage_row


def list_member_usage_summary_rows(organization_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                u.id AS user_id,
                u.display_name AS display_name,
                COALESCE(SUM(a.credit_cost_final), 0) AS credit_consumed,
                COUNT(a.id) AS usage_count,
                MAX(a.created_at) AS last_used_at
            FROM ai_usage_ledger a
            JOIN users u ON u.id = a.user_id
            WHERE a.organization_id=?
            GROUP BY u.id, u.display_name
            ORDER BY credit_consumed DESC, usage_count DESC, u.id ASC
            """,
            (organization_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _public_user_dict(row):
    if not row:
        return None
    keys = row.keys() if hasattr(row, 'keys') else []
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
        "status": row["status"],
        "organization_id": row["organization_id"],
        "organization_name": row["organization_name"],
        "created_at": row["created_at"],
        "last_login": row["last_login"] if "last_login" in keys else None,
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
        WHERE lower(u.username)=lower(?)
        ORDER BY CASE WHEN lower(u.username)=lower(?) THEN 0 ELSE 1 END, u.id
        LIMIT 1
        """,
        (_normalize_username(username), _normalize_username(username)),
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


def _organization_exists(conn: sqlite3.Connection, organization_name: str) -> bool:
    normalized_name = (organization_name or "").strip()
    if not normalized_name:
        return False
    return conn.execute(
        "SELECT 1 FROM organizations WHERE lower(name)=lower(?) LIMIT 1",
        (normalized_name,),
    ).fetchone() is not None


def _pending_organization_request_exists(conn: sqlite3.Connection, organization_name: str) -> bool:
    normalized_name = (organization_name or "").strip()
    if not normalized_name:
        return False
    return conn.execute(
        """
        SELECT 1
        FROM organization_requests
        WHERE lower(organization_name)=lower(?) AND status=?
        LIMIT 1
        """,
        (normalized_name, ORGANIZATION_REQUEST_PENDING),
    ).fetchone() is not None


def _pending_organization_request_username_exists(conn: sqlite3.Connection, username: str) -> bool:
    normalized_username = _normalize_username(username)
    if not normalized_username:
        return False
    return conn.execute(
        """
        SELECT 1
        FROM organization_requests
        WHERE lower(username)=lower(?) AND status=?
        LIMIT 1
        """,
        (normalized_username, ORGANIZATION_REQUEST_PENDING),
    ).fetchone() is not None


def _generate_invite_code(length: int = 8) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _fetch_organization_invite_row_by_id(conn: sqlite3.Connection, invite_id: int):
    return conn.execute(
        """
        SELECT oi.*, o.name AS organization_name
        FROM organization_invites oi
        JOIN organizations o ON o.id = oi.organization_id
        WHERE oi.id=?
        """,
        (invite_id,),
    ).fetchone()


def _fetch_active_organization_invite(conn: sqlite3.Connection, organization_id: int):
    return conn.execute(
        """
        SELECT oi.*, o.name AS organization_name
        FROM organization_invites oi
        JOIN organizations o ON o.id = oi.organization_id
        WHERE oi.organization_id=? AND oi.status=?
        ORDER BY oi.created_at DESC, oi.id DESC
        LIMIT 1
        """,
        (organization_id, ORGANIZATION_INVITE_ACTIVE),
    ).fetchone()


def _fetch_active_organization_invite_by_code(conn: sqlite3.Connection, invite_code: str):
    normalized_code = (invite_code or "").strip().upper()
    if not normalized_code:
        return None
    return conn.execute(
        """
        SELECT oi.*, o.name AS organization_name
        FROM organization_invites oi
        JOIN organizations o ON o.id = oi.organization_id
        WHERE upper(oi.invite_code)=upper(?) AND oi.status=?
        LIMIT 1
        """,
        (normalized_code, ORGANIZATION_INVITE_ACTIVE),
    ).fetchone()


def _fetch_active_organization_invite_by_token(conn: sqlite3.Connection, invite_token: str):
    normalized_token = (invite_token or "").strip()
    if not normalized_token:
        return None
    return conn.execute(
        """
        SELECT oi.*, o.name AS organization_name
        FROM organization_invites oi
        JOIN organizations o ON o.id = oi.organization_id
        WHERE oi.invite_token=? AND oi.status=?
        LIMIT 1
        """,
        (normalized_token, ORGANIZATION_INVITE_ACTIVE),
    ).fetchone()


def _public_invite_dict(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "organization_id": row["organization_id"],
        "organization_name": row["organization_name"],
        "invite_code": row["invite_code"],
        "invite_token": row["invite_token"],
        "status": row["status"],
        "created_by": row["created_by"],
        "revoked_at": row["revoked_at"],
        "created_at": row["created_at"],
    }


def _revoke_active_organization_invites(conn: sqlite3.Connection, organization_id: int) -> None:
    conn.execute(
        """
        UPDATE organization_invites
        SET status=?, revoked_at=datetime('now','localtime')
        WHERE organization_id=? AND status=?
        """,
        (ORGANIZATION_INVITE_REVOKED, organization_id, ORGANIZATION_INVITE_ACTIVE),
    )


def _create_organization_invite(conn: sqlite3.Connection, organization_id: int, created_by: int):
    for _ in range(20):
        invite_code = _generate_invite_code()
        invite_token = secrets.token_urlsafe(24)
        try:
            cur = conn.execute(
                """
                INSERT INTO organization_invites
                    (organization_id, invite_code, invite_token, status, created_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (organization_id, invite_code, invite_token, ORGANIZATION_INVITE_ACTIVE, created_by),
            )
            row = _fetch_organization_invite_row_by_id(conn, cur.lastrowid)
            return _public_invite_dict(row)
        except sqlite3.IntegrityError:
            continue
    raise ValueError("failed to generate invite")


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
        WHERE u.role='owner' OR lower(u.username) IN (lower(?), lower(?))
        ORDER BY CASE WHEN lower(u.username)=lower(?) THEN 0 WHEN u.role='owner' THEN 1 ELSE 2 END, u.id
        LIMIT 1
        """,
        (OWNER_USERNAME, old_username, OWNER_USERNAME),
    ).fetchone()
    owner_hash = configured_hash or (owner["password_hash"] if owner else "") or hash_password("xingrun2026")
    if owner:
        # Preserve display_name if the admin has customised it; only reset to default when it still equals the old default.
        kept_display_name = owner["display_name"] if owner["display_name"] else OWNER_DISPLAY_NAME
        conn.execute(
            """
            UPDATE users
            SET username=?, password_hash=?, role=?, status='active', organization_id=?
            WHERE id=?
            """,
            (OWNER_USERNAME, owner_hash, SUPER_OWNER_ROLE, org["id"], owner["id"]),
        )
    else:
        kept_display_name = OWNER_DISPLAY_NAME
        conn.execute(
            """
            INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
            VALUES (?, ?, ?, ?, 'active', ?)
            """,
            (OWNER_USERNAME, owner_hash, kept_display_name, SUPER_OWNER_ROLE, org["id"]),
        )


def save_lesson(date_str: str, subject: str, grade: str, topic: str,
                summary: str, weak_points: str,
                plan: dict, pdf_path: str, class_id: int = 0) -> int:
    """保存一节课及其复习计划，返回 lesson_id。"""
    with get_conn() as conn:
        organization_id = None
        if class_id:
            class_row = conn.execute(
                "SELECT organization_id FROM classes WHERE id=?",
                (class_id,),
            ).fetchone()
            organization_id = class_row["organization_id"] if class_row else None
        if organization_id is None:
            organization_id = _ensure_organization(conn, DEFAULT_ORGANIZATION_NAME)["id"]
        cur = conn.execute(
            """INSERT INTO lessons
               (date, subject, grade, topic, summary, weak_points, plan_json, pdf_path, class_id, organization_id)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (date_str, subject, grade, topic, summary, weak_points,
             json.dumps(plan, ensure_ascii=False), pdf_path,
             class_id if class_id else None, organization_id)
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
                "SELECT * FROM lessons WHERE class_id=? AND date LIKE ? ORDER BY created_at DESC, id DESC",
                (class_id, f"{month_str}%")
            ).fetchall()
        elif class_id:
            rows = conn.execute(
                "SELECT * FROM lessons WHERE class_id=? ORDER BY created_at DESC, id DESC",
                (class_id,)
            ).fetchall()
        elif month_str:
            rows = conn.execute(
                "SELECT * FROM lessons WHERE date LIKE ? ORDER BY created_at DESC, id DESC",
                (f"{month_str}%",)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM lessons ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def delete_lesson(lesson_id: int):
    """Delete a lesson and its associated questions from the database."""
    with get_conn() as conn:
        conn.execute("DELETE FROM questions WHERE lesson_id=?", (lesson_id,))
        conn.execute("DELETE FROM lessons WHERE id=?", (lesson_id,))


# ─── 班级 CRUD ─────────────────────────────────────────────────────────────────
def save_class(name: str, subject: str = "", grade: str = "",
               teacher_name: str = "", teacher_email: str = "", organization_id: Optional[int] = None) -> int:
    with get_conn() as conn:
        if organization_id is None:
            organization_id = _ensure_organization(conn, DEFAULT_ORGANIZATION_NAME)["id"]
        cur = conn.execute(
            """
            INSERT INTO classes (organization_id, name, subject, grade, teacher_name, teacher_email)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (organization_id, name, subject, grade, teacher_name, teacher_email)
        )
        return cur.lastrowid


def _sync_class_teacher_metadata(conn: sqlite3.Connection, class_ids: list[int]) -> None:
    normalized_class_ids = []
    seen_class_ids = set()
    for class_id in class_ids:
        if class_id in seen_class_ids:
            continue
        seen_class_ids.add(class_id)
        normalized_class_ids.append(class_id)

    for class_id in normalized_class_ids:
        row = conn.execute(
            """
            SELECT u.display_name
            FROM user_classes uc
            JOIN users u ON u.id = uc.user_id
            WHERE uc.class_id=?
            ORDER BY uc.user_id
            LIMIT 1
            """,
            (class_id,),
        ).fetchone()
        teacher_name = (row["display_name"] if row else "") or ""
        conn.execute(
            "UPDATE classes SET teacher_name=?, teacher_email='' WHERE id=?",
            (teacher_name, class_id),
        )


def get_class(class_id: int):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT c.*, (
                SELECT uc.user_id
                FROM user_classes uc
                WHERE uc.class_id = c.id
                ORDER BY uc.user_id
                LIMIT 1
            ) AS teacher_user_id
            FROM classes c
            WHERE c.id=?
            """,
            (class_id,),
        ).fetchone()
        return dict(row) if row else None


def list_classes():
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.*, COUNT(l.id) as lesson_count,
                   (
                       SELECT uc.user_id
                       FROM user_classes uc
                       WHERE uc.class_id = c.id
                       ORDER BY uc.user_id
                       LIMIT 1
                   ) AS teacher_user_id
            FROM classes c
            LEFT JOIN lessons l ON l.class_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def update_class(class_id: int, name: str, subject: str = "", grade: str = "",
                 teacher_name: Optional[str] = None, teacher_email: Optional[str] = None):
    with get_conn() as conn:
        bound_teacher_row = conn.execute(
            "SELECT user_id FROM user_classes WHERE class_id=? ORDER BY user_id LIMIT 1",
            (class_id,),
        ).fetchone()

        if bound_teacher_row:
            conn.execute(
                "UPDATE classes SET name=?, subject=?, grade=?, teacher_email='' WHERE id=?",
                (name, subject, grade, class_id)
            )
            _sync_class_teacher_metadata(conn, [class_id])
            return

        conn.execute(
            """
            UPDATE classes
            SET name=?,
                subject=?,
                grade=?,
                teacher_name=COALESCE(?, teacher_name),
                teacher_email=COALESCE(?, teacher_email)
            WHERE id=?
            """,
            (name, subject, grade, teacher_name, teacher_email, class_id)
        )


def delete_class(class_id: int):
    """Delete a class (lessons are kept but unlinked)."""
    with get_conn() as conn:
        import master_data

        master_data.ensure_schema(conn)
        conn.execute("UPDATE lessons SET class_id=NULL WHERE class_id=?", (class_id,))
        conn.execute(
            """
            UPDATE wrong_question_mappings
            SET class_id=NULL,
                mapping_status=CASE
                    WHEN teacher_user_id IS NOT NULL THEN 'needs_review'
                    ELSE 'unmapped'
                END,
                reviewed_by=NULL,
                reviewed_at=NULL,
                updated_at=datetime('now','localtime')
            WHERE class_id=?
            """,
            (class_id,),
        )
        conn.execute("DELETE FROM user_classes WHERE class_id=?", (class_id,))
        conn.execute("DELETE FROM classes WHERE id=?", (class_id,))


def get_student(student_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    return dict(row) if row else None


def list_students_for_class(class_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.*
            FROM class_students cs
            JOIN students s ON s.id = cs.student_id
            WHERE cs.class_id=?
            ORDER BY cs.id
            """,
            (class_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def _dedupe_student_name_in_class(
    class_id: int,
    raw_name: str,
    conn: Optional[sqlite3.Connection] = None,
) -> str:
    base_name = (raw_name or "").strip()
    if not base_name:
        raise ValueError("student name is required")

    owns_conn = False
    if conn is None:
        conn = get_conn()
        owns_conn = True
    rows = conn.execute(
        """
        SELECT s.name
        FROM class_students cs
        JOIN students s ON s.id = cs.student_id
        WHERE cs.class_id=?
        ORDER BY cs.id
        """,
        (class_id,),
    ).fetchall()
    existing_names = [row["name"] for row in rows]
    if owns_conn:
        conn.close()

    if base_name not in existing_names:
        return base_name

    suffix_pattern = re.compile(rf"^{re.escape(base_name)}（(\d+)）$")
    max_suffix = 1
    for name in existing_names:
        if name == base_name:
            continue
        matched = suffix_pattern.match(name or "")
        if matched:
            max_suffix = max(max_suffix, int(matched.group(1)))
    return f"{base_name}（{max_suffix + 1}）"


def create_student_for_class(class_id: int, raw_name: str):
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        class_row = conn.execute("SELECT id FROM classes WHERE id=?", (class_id,)).fetchone()
        if not class_row:
            raise LookupError("class not found")

        student_name = _dedupe_student_name_in_class(class_id, raw_name, conn=conn)
        cur = conn.execute("INSERT INTO students (name) VALUES (?)", (student_name,))
        student_id = cur.lastrowid
        conn.execute(
            "INSERT INTO class_students (class_id, student_id) VALUES (?, ?)",
            (class_id, student_id),
        )
        row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    return dict(row)


def remove_student_from_class(class_id: int, student_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM class_students WHERE class_id=? AND student_id=?",
            (class_id, student_id),
        )
    return cur.rowcount > 0


def _derive_class_feedback_period_fields(start_date: str, end_date: str) -> tuple[int, str]:
    start = date.fromisoformat((start_date or "").strip())
    end = date.fromisoformat((end_date or "").strip())
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    period_length_days = (end - start).days + 1
    if period_length_days <= 1:
        return period_length_days, "daily"
    if 6 <= period_length_days <= 8:
        return period_length_days, "weekly"
    return period_length_days, "custom"


def _load_json_list(value) -> list:
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _normalize_class_feedback_student_highlights(
    *,
    task_row: sqlite3.Row,
    conn: sqlite3.Connection,
    student_highlights: list[dict] | None,
) -> list[dict]:
    if student_highlights is None:
        student_highlights = []
    if not isinstance(student_highlights, list):
        raise ValueError("student_highlights must be a list")

    roster_by_id = _get_class_feedback_student_roster(conn, task_row["class_id"])
    normalized_highlights: list[dict] = []
    seen_student_ids: set[int] = set()
    for item in student_highlights:
        if not isinstance(item, dict):
            raise ValueError("student_highlights must contain objects")
        student_id = item.get("student_id")
        if isinstance(student_id, bool) or not isinstance(student_id, int):
            raise ValueError("student_highlights.student_id must be an integer")
        if student_id in seen_student_ids:
            continue
        if student_id not in roster_by_id:
            raise ValueError("student_highlights must belong to class roster")
        labels = []
        for label in item.get("labels") or []:
            normalized_label = str(label or "").strip()
            if normalized_label:
                labels.append(normalized_label)
        normalized_highlights.append(
            {
                "student_id": student_id,
                "labels": labels,
                "note": str(item.get("note") or "").strip(),
            }
        )
        seen_student_ids.add(student_id)
    return normalized_highlights


def _normalize_class_feedback_task_notes(
    *,
    task_row: sqlite3.Row,
    conn: sqlite3.Connection,
    class_status_tags: list[str] | None,
    class_status_note: str,
    parent_feedback_note: str,
    teaching_focus_note: str,
    next_stage_preview_note: str,
    student_highlights: list[dict] | None,
) -> dict:
    normalized_tags = [
        str(tag or "").strip()
        for tag in (class_status_tags or [])
        if str(tag or "").strip()
    ]
    return {
        "class_status_tags": normalized_tags,
        "class_status_note": str(class_status_note or "").strip(),
        "parent_feedback_note": str(parent_feedback_note or "").strip(),
        "teaching_focus_note": str(teaching_focus_note or "").strip(),
        "next_stage_preview_note": str(next_stage_preview_note or "").strip(),
        "student_highlights": _normalize_class_feedback_student_highlights(
            task_row=task_row,
            conn=conn,
            student_highlights=student_highlights,
        ),
    }


def _ensure_class_feedback_student_entries_cover_current_roster(
    *,
    task_row: sqlite3.Row,
    conn: sqlite3.Connection,
    normalized_student_entries: list[dict],
) -> None:
    roster_student_ids = sorted(_get_class_feedback_student_roster(conn, task_row["class_id"]).keys())
    if not roster_student_ids:
        raise ValueError("当前班级还没有学生，无法生成课堂反馈")
    provided_student_ids = sorted(item["student_id"] for item in normalized_student_entries)
    if provided_student_ids != roster_student_ids:
        raise ValueError("student_entries must match current class roster")


def _serialize_class_feedback_task_row(row: sqlite3.Row, student_entries: Optional[list[dict]] = None) -> dict:
    task = dict(row)
    task["class_status_tags"] = _load_json_list(task.get("class_status_tags_json"))
    task["student_highlights"] = _load_json_list(task.get("student_highlights_json"))
    task.pop("class_status_tags_json", None)
    task.pop("student_highlights_json", None)
    task["class_status_note"] = task.get("class_status_note") or ""
    task["parent_feedback_note"] = task.get("parent_feedback_note") or ""
    task["teaching_focus_note"] = task.get("teaching_focus_note") or ""
    task["next_stage_preview_note"] = task.get("next_stage_preview_note") or ""
    task["student_entries"] = student_entries or []
    return task


def _load_class_feedback_task_row(conn: sqlite3.Connection, task_id: int):
    task_row = conn.execute(
        "SELECT * FROM class_feedback_tasks WHERE id=?",
        (task_id,),
    ).fetchone()
    if not task_row:
        raise LookupError("class feedback task not found")
    return task_row


def _get_class_feedback_student_roster(conn: sqlite3.Connection, class_id: int) -> dict[int, dict]:
    rows = conn.execute(
        """
        SELECT s.id, s.name
        FROM class_students cs
        JOIN students s ON s.id = cs.student_id
        WHERE cs.class_id=?
        ORDER BY cs.id
        """,
        (class_id,),
    ).fetchall()
    return {row["id"]: dict(row) for row in rows}


def _validate_class_feedback_teacher_binding(
    conn: sqlite3.Connection,
    *,
    class_id: int,
    teacher_user_id: Optional[int],
) -> None:
    if teacher_user_id is None:
        return
    row = conn.execute(
        """
        SELECT user_id
        FROM user_classes
        WHERE class_id=?
        ORDER BY user_id
        LIMIT 1
        """,
        (class_id,),
    ).fetchone()
    bound_teacher_user_id = row["user_id"] if row else None
    if bound_teacher_user_id != teacher_user_id:
        raise ValueError("teacher_user_id does not match class binding")


def _get_class_feedback_task_student_ids(conn: sqlite3.Connection, task_id: int) -> list[int]:
    rows = conn.execute(
        """
        SELECT student_id
        FROM class_feedback_student_entries
        WHERE task_id=?
        ORDER BY student_id, id
        """,
        (task_id,),
    ).fetchall()
    return [row["student_id"] for row in rows]


def _normalize_class_feedback_student_entries(
    *,
    task_row: sqlite3.Row,
    conn: sqlite3.Connection,
    student_entries: list[dict] | None,
    require_final_text: bool = False,
    require_checked_at: bool = False,
) -> list[dict]:
    if student_entries is None:
        student_entries = []
    if not isinstance(student_entries, list):
        raise ValueError("student_entries must be a list")

    roster_by_id = _get_class_feedback_student_roster(conn, task_row["class_id"])
    normalized_entries: list[dict] = []
    for item in student_entries:
        if not isinstance(item, dict):
            raise ValueError("student_entries must contain objects")
        student_id = item.get("student_id")
        if isinstance(student_id, bool) or not isinstance(student_id, int):
            raise ValueError("student_id must be an integer")
        roster_student = roster_by_id.get(student_id)
        if not roster_student:
            raise ValueError("student must belong to class roster")

        name_snapshot = (item.get("name") or roster_student["name"] or "").strip()
        ai_draft = item.get("ai_draft", "") or ""
        final_text = item.get("final_text", "") or ""
        checked_at = item.get("checked_at")
        if require_final_text:
            final_text = final_text.strip()
            if not final_text:
                raise ValueError("final_text is required")
        if require_checked_at:
            if checked_at is None:
                raise ValueError("checked_at is required")
            checked_at = str(checked_at).strip()
            if not checked_at:
                raise ValueError("checked_at is required")

        normalized_entries.append(
            {
                "student_id": student_id,
                "student_name_snapshot": name_snapshot,
                "ai_draft": ai_draft,
                "final_text": final_text,
                "checked_at": checked_at,
            }
        )
    return normalized_entries


def get_class_feedback_task(task_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM class_feedback_tasks WHERE id=?",
            (task_id,),
        ).fetchone()
        if not row:
            return None
        student_rows = conn.execute(
            """
            SELECT *
            FROM class_feedback_student_entries
            WHERE task_id=?
            ORDER BY id
            """,
            (task_id,),
        ).fetchall()
    student_entries = [dict(student_row) for student_row in student_rows]
    return _serialize_class_feedback_task_row(row, student_entries)


def create_class_feedback_task(
    *,
    class_id: int,
    teacher_user_id: Optional[int],
    teacher_name_snapshot: str,
    start_date: str,
    end_date: str,
    created_by: int,
):
    teacher_name_snapshot = (teacher_name_snapshot or "").strip()
    if not teacher_name_snapshot:
        raise ValueError("teacher_name_snapshot is required")
    period_length_days, period_granularity = _derive_class_feedback_period_fields(start_date, end_date)
    with get_conn() as conn:
        class_row = conn.execute("SELECT id FROM classes WHERE id=?", (class_id,)).fetchone()
        if not class_row:
            raise LookupError("class not found")
        creator_row = conn.execute("SELECT id FROM users WHERE id=?", (created_by,)).fetchone()
        if not creator_row:
            raise LookupError("user not found")
        if teacher_user_id is not None:
            teacher_row = conn.execute("SELECT id FROM users WHERE id=?", (teacher_user_id,)).fetchone()
            if not teacher_row:
                raise LookupError("user not found")
            _validate_class_feedback_teacher_binding(
                conn,
                class_id=class_id,
                teacher_user_id=teacher_user_id,
            )
        cur = conn.execute(
            """
            INSERT INTO class_feedback_tasks (
                class_id, teacher_user_id, teacher_name_snapshot,
                start_date, end_date, period_length_days, period_granularity,
                status, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?)
            """,
            (
                class_id,
                teacher_user_id,
                teacher_name_snapshot,
                start_date,
                end_date,
                period_length_days,
                period_granularity,
                created_by,
            ),
        )
        task_id = cur.lastrowid
    return get_class_feedback_task(task_id)


def save_class_feedback_generation_result(task_id: int, class_summary_ai_draft: str, student_entries: list[dict]):
    with get_conn() as conn:
        task_row = _load_class_feedback_task_row(conn, task_id)
        if task_row["status"] == "confirmed":
            raise ValueError("confirmed tasks cannot be regenerated")
        normalized_student_entries = _normalize_class_feedback_student_entries(
            task_row=task_row,
            conn=conn,
            student_entries=student_entries,
        )
        _ensure_class_feedback_student_entries_cover_current_roster(
            task_row=task_row,
            conn=conn,
            normalized_student_entries=normalized_student_entries,
        )
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE class_feedback_tasks
            SET class_summary_ai_draft=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (class_summary_ai_draft or "", task_id),
        )
        conn.execute("DELETE FROM class_feedback_student_entries WHERE task_id=?", (task_id,))
        for item in normalized_student_entries:
            conn.execute(
                """
                INSERT INTO class_feedback_student_entries (
                    task_id, student_id, student_name_snapshot, ai_draft, final_text, checked_at
                ) VALUES (?, ?, ?, ?, '', NULL)
                """,
                (
                    task_id,
                    item["student_id"],
                    item["student_name_snapshot"],
                    item["ai_draft"],
                ),
            )
    return get_class_feedback_task(task_id)


def save_class_feedback_draft(task_id: int, class_summary_draft_text: str, student_entries: list[dict]):
    with get_conn() as conn:
        task_row = _load_class_feedback_task_row(conn, task_id)
        if task_row["status"] == "confirmed":
            raise ValueError("confirmed tasks cannot be edited as draft")
        normalized_student_entries = _normalize_class_feedback_student_entries(
            task_row=task_row,
            conn=conn,
            student_entries=student_entries,
        )
        _ensure_class_feedback_student_entries_cover_current_roster(
            task_row=task_row,
            conn=conn,
            normalized_student_entries=normalized_student_entries,
        )
        existing_entries = {
            row["student_id"]: dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM class_feedback_student_entries
                WHERE task_id=?
                """,
                (task_id,),
            ).fetchall()
        }
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE class_feedback_tasks
            SET class_summary_ai_draft=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (class_summary_draft_text or "", task_id),
        )
        for item in normalized_student_entries:
            existing_entry = existing_entries.get(item["student_id"])
            if existing_entry:
                conn.execute(
                    """
                    UPDATE class_feedback_student_entries
                    SET student_name_snapshot=?,
                        ai_draft=?,
                        final_text=?,
                        updated_at=datetime('now','localtime')
                    WHERE task_id=? AND student_id=?
                    """,
                    (
                        item["student_name_snapshot"],
                        existing_entry.get("ai_draft") or "",
                        item["final_text"],
                        task_id,
                        item["student_id"],
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO class_feedback_student_entries (
                        task_id, student_id, student_name_snapshot, ai_draft, final_text, checked_at
                    ) VALUES (?, ?, ?, '', ?, NULL)
                    """,
                    (
                        task_id,
                        item["student_id"],
                        item["student_name_snapshot"],
                        item["final_text"],
                    ),
                )
    return get_class_feedback_task(task_id)


def confirm_class_feedback_task(task_id: int, class_summary_final_text: str, student_entries: list[dict]):
    with get_conn() as conn:
        task_row = _load_class_feedback_task_row(conn, task_id)
        normalized_student_entries = _normalize_class_feedback_student_entries(
            task_row=task_row,
            conn=conn,
            student_entries=student_entries,
            require_final_text=True,
        )
        roster_by_id = _get_class_feedback_student_roster(conn, task_row["class_id"])
        _ensure_class_feedback_student_entries_cover_current_roster(
            task_row=task_row,
            conn=conn,
            normalized_student_entries=normalized_student_entries,
        )
        conn.execute("BEGIN IMMEDIATE")
        checked_at_value = conn.execute(
            "SELECT datetime('now','localtime') AS checked_at"
        ).fetchone()["checked_at"]
        if roster_by_id:
            placeholders = ",".join("?" for _ in roster_by_id)
            conn.execute(
                f"DELETE FROM class_feedback_student_entries WHERE task_id=? AND student_id NOT IN ({placeholders})",
                (task_id, *roster_by_id.keys()),
            )
        else:
            conn.execute("DELETE FROM class_feedback_student_entries WHERE task_id=?", (task_id,))
        conn.execute(
            """
            UPDATE class_feedback_tasks
            SET class_summary_final_text=?, status='confirmed',
                confirmed_at=datetime('now','localtime'),
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (class_summary_final_text or "", task_id),
        )
        for item in normalized_student_entries:
            updated = conn.execute(
                """
                UPDATE class_feedback_student_entries
                SET final_text=?, checked_at=?, updated_at=datetime('now','localtime')
                WHERE task_id=? AND student_id=?
                """,
                (
                    item["final_text"],
                    checked_at_value,
                    task_id,
                    item["student_id"],
                ),
            )
            if updated.rowcount == 0:
                conn.execute(
                    """
                    INSERT INTO class_feedback_student_entries (
                        task_id, student_id, student_name_snapshot, ai_draft, final_text, checked_at
                    ) VALUES (?, ?, ?, '', ?, ?)
                    """,
                    (
                        task_id,
                        item["student_id"],
                        roster_by_id[item["student_id"]]["name"],
                        item["final_text"],
                        checked_at_value,
                    ),
                )
    return get_class_feedback_task(task_id)


def save_class_feedback_task_notes(
    task_id: int,
    *,
    class_status_tags: list[str] | None,
    class_status_note: str = "",
    parent_feedback_note: str = "",
    teaching_focus_note: str = "",
    next_stage_preview_note: str = "",
    student_highlights: list[dict] | None = None,
):
    with get_conn() as conn:
        task_row = _load_class_feedback_task_row(conn, task_id)
        normalized_notes = _normalize_class_feedback_task_notes(
            task_row=task_row,
            conn=conn,
            class_status_tags=class_status_tags,
            class_status_note=class_status_note,
            parent_feedback_note=parent_feedback_note,
            teaching_focus_note=teaching_focus_note,
            next_stage_preview_note=next_stage_preview_note,
            student_highlights=student_highlights,
        )
        conn.execute(
            """
            UPDATE class_feedback_tasks
            SET class_status_tags_json=?,
                class_status_note=?,
                parent_feedback_note=?,
                teaching_focus_note=?,
                next_stage_preview_note=?,
                student_highlights_json=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (
                json.dumps(normalized_notes["class_status_tags"], ensure_ascii=False),
                normalized_notes["class_status_note"],
                normalized_notes["parent_feedback_note"],
                normalized_notes["teaching_focus_note"],
                normalized_notes["next_stage_preview_note"],
                json.dumps(normalized_notes["student_highlights"], ensure_ascii=False),
                task_id,
            ),
        )
    return get_class_feedback_task(task_id)


def find_previous_confirmed_class_feedback_entry(*, class_id: int, student_id: int, period_granularity: str, before_end_date: str):
    with get_conn() as conn:
        same_granularity_row = conn.execute(
            """
            SELECT
                t.id AS task_id,
                t.class_id,
                t.teacher_user_id,
                t.teacher_name_snapshot,
                t.start_date,
                t.end_date,
                t.period_length_days,
                t.period_granularity,
                t.status,
                t.class_summary_final_text,
                t.created_by,
                t.created_at,
                t.updated_at,
                t.confirmed_at,
                e.id AS entry_id,
                e.student_id,
                e.student_name_snapshot,
                e.ai_draft,
                e.final_text,
                e.checked_at,
                e.updated_at AS entry_updated_at
            FROM class_feedback_student_entries e
            JOIN class_feedback_tasks t ON t.id = e.task_id
            WHERE t.class_id=?
              AND e.student_id=?
              AND t.status='confirmed'
              AND t.end_date < ?
              AND t.period_granularity=?
              AND trim(coalesce(e.final_text, '')) <> ''
              AND e.checked_at IS NOT NULL
              AND trim(coalesce(e.checked_at, '')) <> ''
            ORDER BY t.end_date DESC, t.id DESC, e.id DESC
            LIMIT 1
            """,
            (class_id, student_id, before_end_date, period_granularity),
        ).fetchone()
        if same_granularity_row:
            return dict(same_granularity_row)

        fallback_row = conn.execute(
            """
            SELECT
                t.id AS task_id,
                t.class_id,
                t.teacher_user_id,
                t.teacher_name_snapshot,
                t.start_date,
                t.end_date,
                t.period_length_days,
                t.period_granularity,
                t.status,
                t.class_summary_final_text,
                t.created_by,
                t.created_at,
                t.updated_at,
                t.confirmed_at,
                e.id AS entry_id,
                e.student_id,
                e.student_name_snapshot,
                e.ai_draft,
                e.final_text,
                e.checked_at,
                e.updated_at AS entry_updated_at
            FROM class_feedback_student_entries e
            JOIN class_feedback_tasks t ON t.id = e.task_id
            WHERE t.class_id=?
              AND e.student_id=?
              AND t.status='confirmed'
              AND t.end_date < ?
              AND trim(coalesce(e.final_text, '')) <> ''
              AND e.checked_at IS NOT NULL
              AND trim(coalesce(e.checked_at, '')) <> ''
            ORDER BY t.end_date DESC, t.id DESC, e.id DESC
            LIMIT 1
            """,
            (class_id, student_id, before_end_date),
        ).fetchone()
    return dict(fallback_row) if fallback_row else None


def list_recent_confirmed_class_feedback_summaries(*, class_id: int, before_end_date: str, limit: int = 3) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                class_id,
                teacher_user_id,
                teacher_name_snapshot,
                start_date,
                end_date,
                period_length_days,
                period_granularity,
                class_summary_final_text,
                confirmed_at
            FROM class_feedback_tasks
            WHERE class_id=?
              AND status='confirmed'
              AND end_date < ?
              AND trim(coalesce(class_summary_final_text, '')) <> ''
            ORDER BY end_date DESC, id DESC
            LIMIT ?
            """,
            (class_id, before_end_date, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def list_class_feedback_label_configs(owner_user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT label_group, label_text, sort_order
            FROM class_feedback_label_configs
            WHERE owner_user_id=? AND is_active=1
            ORDER BY sort_order ASC, id ASC
            """,
            (owner_user_id,),
    ).fetchall()
    if not rows:
        return [
            {"group": item["group"], "labels": list(item["labels"])}
            for item in DEFAULT_CLASS_FEEDBACK_LABEL_GROUPS
        ]

    grouped: list[dict] = []
    current_group = None
    current_labels: list[str] = []
    for row in rows:
        label_group = row["label_group"]
        label_text = row["label_text"]
        if current_group != label_group:
            if current_group is not None:
                grouped.append({"group": current_group, "labels": current_labels})
            current_group = label_group
            current_labels = [label_text]
        else:
            current_labels.append(label_text)
    if current_group is not None:
        grouped.append({"group": current_group, "labels": current_labels})
    return grouped


def save_class_feedback_label_configs(owner_user_id: int, groups: list[dict]):
    normalized_groups = []
    for group_index, group in enumerate(groups or []):
        if not isinstance(group, dict):
            continue
        label_group = (group.get("group") or "").strip()
        if not label_group:
            continue
        labels = []
        for label_index, label_text in enumerate(group.get("labels") or []):
            normalized_label = str(label_text or "").strip()
            if not normalized_label:
                continue
            labels.append((label_index, normalized_label))
        normalized_groups.append((group_index, label_group, labels))

    with get_conn() as conn:
        user_row = conn.execute("SELECT id FROM users WHERE id=?", (owner_user_id,)).fetchone()
        if not user_row:
            raise LookupError("user not found")
        conn.execute(
            "DELETE FROM class_feedback_label_configs WHERE owner_user_id=?",
            (owner_user_id,),
        )
        if not normalized_groups:
            return [
                {"group": item["group"], "labels": list(item["labels"])}
                for item in DEFAULT_CLASS_FEEDBACK_LABEL_GROUPS
            ]
        for group_index, label_group, labels in normalized_groups:
            for label_index, label_text in labels:
                conn.execute(
                    """
                    INSERT INTO class_feedback_label_configs (
                        owner_user_id, label_group, label_text, sort_order, is_active, is_system_default
                    ) VALUES (?, ?, ?, ?, 1, 0)
                    """,
                    (
                        owner_user_id,
                        label_group,
                        label_text,
                        group_index * 100 + label_index,
                    ),
                )


def save_lesson_feedback(
    lesson_id: int,
    class_id: int,
    merged_text: str,
    student_index: list,
    editor_state: dict,
) -> dict:
    with get_conn() as conn:
        lesson_row = conn.execute(
            "SELECT id, class_id FROM lessons WHERE id=?",
            (lesson_id,),
        ).fetchone()
        if not lesson_row:
            raise LookupError("lesson not found")
        lesson_class_id = lesson_row["class_id"]
        conn.execute(
            """
            INSERT INTO lesson_feedbacks
                (lesson_id, class_id, merged_text, student_index_json, editor_state_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))
            ON CONFLICT(lesson_id) DO UPDATE SET
                class_id=excluded.class_id,
                merged_text=excluded.merged_text,
                student_index_json=excluded.student_index_json,
                editor_state_json=excluded.editor_state_json,
                updated_at=datetime('now','localtime')
            """,
            (
                lesson_id,
                lesson_class_id if lesson_class_id else None,
                merged_text or "",
                json.dumps(student_index or [], ensure_ascii=False),
                json.dumps(editor_state or {}, ensure_ascii=False),
            ),
        )
        row = conn.execute(
            "SELECT * FROM lesson_feedbacks WHERE lesson_id=?",
            (lesson_id,),
        ).fetchone()
    feedback = dict(row)
    feedback["student_index"] = json.loads(feedback.get("student_index_json") or "[]")
    feedback["editor_state"] = json.loads(feedback.get("editor_state_json") or "{}")
    return feedback


def get_lesson_feedback(lesson_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM lesson_feedbacks WHERE lesson_id=?",
            (lesson_id,),
        ).fetchone()
    if not row:
        return None
    feedback = dict(row)
    feedback["student_index"] = json.loads(feedback.get("student_index_json") or "[]")
    feedback["editor_state"] = json.loads(feedback.get("editor_state_json") or "{}")
    return feedback


def build_lesson_feedback_editor_state(lesson_id: int) -> dict:
    lesson = get_lesson(lesson_id)
    if not lesson:
        raise LookupError("lesson not found")
    saved_feedback = get_lesson_feedback(lesson_id) or {}
    class_id = lesson.get("class_id")

    roster = list_students_for_class(class_id) if class_id else []
    roster_by_id = {student["id"]: student for student in roster}
    saved_editor_state = saved_feedback.get("editor_state") or {}
    saved_students = saved_editor_state.get("students")
    if not isinstance(saved_students, list):
        saved_students = []
    saved_by_student_id = {
        item.get("student_id"): item
        for item in saved_students
        if isinstance(item, dict) and item.get("student_id") is not None
    }

    hydrated_students = []
    for student in roster:
        saved_student_state = saved_by_student_id.get(student["id"], {})
        hydrated_students.append(
            {
                "student_id": student["id"],
                "name": student["name"],
                "selected_template_id": saved_student_state.get("selected_template_id", "") or "",
                "remark": saved_student_state.get("remark", "") or "",
            }
        )

    custom_templates = saved_editor_state.get("custom_templates")
    if not isinstance(custom_templates, list):
        custom_templates = []
    saved_student_index = saved_feedback.get("student_index")
    if not isinstance(saved_student_index, list):
        saved_student_index = []
    filtered_student_index = []
    for item in saved_student_index:
        if not isinstance(item, dict):
            continue
        student_id = item.get("student_id")
        if student_id in roster_by_id:
            filtered_student_index.append(
                {
                    "student_id": student_id,
                    "name": roster_by_id[student_id]["name"],
                }
            )

    return {
        "lesson_id": lesson_id,
        "class_id": class_id,
        "merged_text": saved_feedback.get("merged_text", "") or "",
        "student_index": filtered_student_index,
        "students": hydrated_students,
        "custom_templates": custom_templates,
        "updated_at": saved_feedback.get("updated_at"),
    }
def get_class_teacher_user_id(class_id: int) -> Optional[int]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id FROM user_classes WHERE class_id=? ORDER BY user_id LIMIT 1",
            (class_id,),
        ).fetchone()
        return row["user_id"] if row else None


def list_class_teacher_bindings() -> dict[int, Optional[int]]:
    with get_conn() as conn:
        class_rows = conn.execute("SELECT id FROM classes ORDER BY id").fetchall()
        binding_rows = conn.execute(
            "SELECT class_id, user_id FROM user_classes ORDER BY class_id, user_id"
        ).fetchall()

    bindings = {row["id"]: None for row in class_rows}
    for row in binding_rows:
        class_id = row["class_id"]
        if class_id in bindings and bindings[class_id] is None:
            bindings[class_id] = row["user_id"]
    return bindings


def set_class_teacher_user_id(class_id: int, teacher_user_id: Optional[int]):
    if teacher_user_id is not None and (isinstance(teacher_user_id, bool) or not isinstance(teacher_user_id, int)):
        raise ValueError("teacher_user_id must be an integer or null")

    with get_conn() as conn:
        class_row = conn.execute("SELECT id FROM classes WHERE id=?", (class_id,)).fetchone()
        if not class_row:
            raise LookupError("class not found")

        if teacher_user_id is not None:
            user_row = _fetch_user_row_by_id(conn, teacher_user_id)
            if not user_row:
                raise LookupError("user not found")

        conn.execute("DELETE FROM user_classes WHERE class_id=?", (class_id,))
        if teacher_user_id is not None:
            conn.execute(
                "INSERT INTO user_classes (user_id, class_id) VALUES (?, ?)",
                (teacher_user_id, class_id),
            )
        _sync_class_teacher_metadata(conn, [class_id])


# ─── 用户-班级关联 ──────────────────────────────────────────────────────────────
def list_all_users() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT u.*, o.name AS organization_name
            FROM users u
            JOIN organizations o ON o.id = u.organization_id
            WHERE u.status = 'active'
            ORDER BY CASE WHEN u.role=? THEN 0 WHEN u.role=? THEN 1 ELSE 2 END, u.display_name
            """
            ,
            (SUPER_OWNER_ROLE, OWNER_ROLE),
        ).fetchall()
        return [_public_user_dict(row) for row in rows]


def get_user_by_id(user_id: int):
    with get_conn() as conn:
        row = _fetch_user_row_by_id(conn, user_id)
    return _public_user_dict(row)


def list_users_for_actor(actor_user: dict) -> list[dict]:
    if (actor_user or {}).get("role") == SUPER_OWNER_ROLE:
        return list_all_users()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT u.*, o.name AS organization_name
            FROM users u
            JOIN organizations o ON o.id = u.organization_id
            WHERE u.status='active' AND u.organization_id=?
            ORDER BY CASE WHEN u.role=? THEN 0 WHEN u.role=? THEN 1 ELSE 2 END, u.display_name
            """,
            (actor_user["organization_id"], OWNER_ROLE, ADMIN_ROLE),
        ).fetchall()
    return [_public_user_dict(row) for row in rows]


def list_registration_requests_for_actor(actor_user: dict, status: str = "pending") -> list[dict]:
    if (actor_user or {}).get("role") == SUPER_OWNER_ROLE:
        return list_registration_requests(status)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT rr.*, o.name AS organization_name
            FROM registration_requests rr
            JOIN organizations o ON o.id = rr.organization_id
            WHERE rr.status=? AND rr.organization_id=?
            ORDER BY rr.created_at ASC, rr.id ASC
            """,
            (status, actor_user["organization_id"]),
        ).fetchall()
    return [dict(row) for row in rows]


def get_registration_request(request_id: int):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT rr.*, o.name AS organization_name
            FROM registration_requests rr
            JOIN organizations o ON o.id = rr.organization_id
            WHERE rr.id=?
            """,
            (request_id,),
        ).fetchone()
    return dict(row) if row else None


def list_organizations() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                o.id,
                o.name,
                o.created_at,
                COUNT(DISTINCT CASE WHEN u.status='active' THEN u.id END) AS member_count,
                COUNT(DISTINCT CASE WHEN u.status='active' AND u.role=? THEN u.id END) AS owner_count,
                COUNT(DISTINCT c.id) AS class_count,
                COUNT(DISTINCT l.id) AS lesson_count
            FROM organizations o
            LEFT JOIN users u ON u.organization_id = o.id
            LEFT JOIN classes c ON c.organization_id = o.id
            LEFT JOIN lessons l ON l.organization_id = o.id
            GROUP BY o.id
            ORDER BY CASE WHEN o.name=? THEN 0 ELSE 1 END, o.created_at ASC, o.id ASC
            """,
            (OWNER_ROLE, DEFAULT_ORGANIZATION_NAME),
        ).fetchall()
    return [dict(row) for row in rows]


def actor_can_manage_user(actor_user: dict, target_user: dict) -> bool:
    if not actor_user or not target_user:
        return False
    if actor_user.get("id") == target_user.get("id"):
        return False
    if actor_user.get("role") == SUPER_OWNER_ROLE:
        return target_user.get("role") != SUPER_OWNER_ROLE
    if actor_user.get("role") != OWNER_ROLE:
        return False
    if actor_user.get("organization_id") != target_user.get("organization_id"):
        return False
    return target_user.get("role") in {ADMIN_ROLE, MEMBER_ROLE}


def list_classes_for_actor(actor_user: dict) -> list[dict]:
    if (actor_user or {}).get("role") == SUPER_OWNER_ROLE:
        return list_classes()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.*, COUNT(l.id) as lesson_count,
                   (
                       SELECT uc.user_id
                       FROM user_classes uc
                       WHERE uc.class_id = c.id
                       ORDER BY uc.user_id
                       LIMIT 1
                   ) AS teacher_user_id
            FROM classes c
            LEFT JOIN lessons l ON l.class_id = c.id
            WHERE c.organization_id=?
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """,
            (actor_user["organization_id"],),
        ).fetchall()
    return [dict(row) for row in rows]


def list_lessons_for_actor(actor_user: dict, month_str: str = "", class_id: int = 0) -> list[dict]:
    if (actor_user or {}).get("role") == SUPER_OWNER_ROLE:
        return list_lessons(month_str=month_str, class_id=class_id)
    with get_conn() as conn:
        query_sql = "SELECT * FROM lessons WHERE organization_id=?"
        params: list[object] = [actor_user["organization_id"]]
        if class_id:
            query_sql += " AND class_id=?"
            params.append(class_id)
        if month_str:
            query_sql += " AND date LIKE ?"
            params.append(f"{month_str}%")
        query_sql += " ORDER BY created_at DESC, id DESC"
        rows = conn.execute(query_sql, params).fetchall()
    return [dict(row) for row in rows]


def list_consultations_for_actor(actor_user: dict, query: str = "") -> list[dict]:
    organization_id = None if (actor_user or {}).get("role") == SUPER_OWNER_ROLE else actor_user["organization_id"]
    return list_consultations(query=query, organization_id=organization_id)


def get_user_class_ids(user_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT class_id FROM user_classes WHERE user_id=? ORDER BY class_id", (user_id,)
        ).fetchall()
        return [r["class_id"] for r in rows]


def set_user_class_ids(user_id: int, class_ids: list):
    if not isinstance(class_ids, list):
        raise ValueError("class_ids must be a list")

    normalized_class_ids = []
    seen_class_ids = set()
    for class_id in class_ids:
        if isinstance(class_id, bool) or not isinstance(class_id, int):
            raise ValueError("class_ids must contain integers")
        if class_id in seen_class_ids:
            continue
        seen_class_ids.add(class_id)
        normalized_class_ids.append(class_id)

    with get_conn() as conn:
        if not _fetch_user_row_by_id(conn, user_id):
            raise LookupError("user not found")

        previous_class_ids = [
            row["class_id"]
            for row in conn.execute(
                "SELECT class_id FROM user_classes WHERE user_id=?",
                (user_id,),
            ).fetchall()
        ]

        if normalized_class_ids:
            placeholders = ", ".join("?" for _ in normalized_class_ids)
            rows = conn.execute(
                f"SELECT id FROM classes WHERE id IN ({placeholders})",
                normalized_class_ids,
            ).fetchall()
            existing_class_ids = {row["id"] for row in rows}
            for class_id in normalized_class_ids:
                if class_id not in existing_class_ids:
                    raise LookupError(f"class not found: {class_id}")

        conn.execute("DELETE FROM user_classes WHERE user_id=?", (user_id,))
        for class_id in normalized_class_ids:
            conn.execute(
                "DELETE FROM user_classes WHERE class_id=?",
                (class_id,),
            )
            conn.execute(
                "INSERT INTO user_classes (user_id, class_id) VALUES (?, ?)",
                (user_id, class_id),
            )
        _sync_class_teacher_metadata(conn, previous_class_ids + normalized_class_ids)


def update_user_profile(user_id: int, new_username: str, new_display_name: str):
    normalized_username = _normalize_username(new_username)
    normalized_display_name = new_display_name.strip()
    with get_conn() as conn:
        user_row = _fetch_user_row_by_id(conn, user_id)
        if not user_row:
            raise LookupError("user not found")
        if _is_super_owner_role(user_row["role"]):
            if normalized_username.casefold() != OWNER_USERNAME:
                raise ValueError("最高权限账号用户名固定为 kayn")
            normalized_username = OWNER_USERNAME
        elif _is_owner_username(normalized_username):
            raise ValueError("用户名已存在")
        if _user_exists_with_username(conn, normalized_username, exclude_user_id=user_id):
            raise ValueError("用户名已被占用")
        conn.execute(
            "UPDATE users SET username=?, display_name=? WHERE id=?",
            (normalized_username, normalized_display_name, user_id)
        )
        class_rows = conn.execute(
            "SELECT class_id FROM user_classes WHERE user_id=?",
            (user_id,),
        ).fetchall()
        _sync_class_teacher_metadata(conn, [row["class_id"] for row in class_rows])


def update_user_display_name_for_actor(actor_user: dict, target_user_id: int, display_name: str):
    normalized_display_name = (display_name or "").strip()
    if not normalized_display_name:
        raise ValueError("display_name is required")
    with get_conn() as conn:
        target_row = _fetch_user_row_by_id(conn, target_user_id)
        if not target_row:
            raise LookupError("user not found")
        target_user = _public_user_dict(target_row)
        if not actor_can_manage_user(actor_user, target_user):
            raise LookupError("user not found")
        conn.execute(
            "UPDATE users SET display_name=? WHERE id=?",
            (normalized_display_name, target_user_id),
        )
        class_rows = conn.execute(
            "SELECT class_id FROM user_classes WHERE user_id=?",
            (target_user_id,),
        ).fetchall()
        _sync_class_teacher_metadata(conn, [row["class_id"] for row in class_rows])
        updated = _fetch_user_row_by_id(conn, target_user_id)
    return _public_user_dict(updated)


def delete_user_for_actor(actor_user: dict, target_user_id: int) -> None:
    with get_conn() as conn:
        target_row = _fetch_user_row_by_id(conn, target_user_id)
        if not target_row:
            raise LookupError("user not found")
        target_user = _public_user_dict(target_row)
        if not actor_can_manage_user(actor_user, target_user):
            raise LookupError("user not found")

        class_rows = conn.execute(
            "SELECT class_id FROM user_classes WHERE user_id=?",
            (target_user_id,),
        ).fetchall()
        affected_class_ids = [row["class_id"] for row in class_rows]

        conn.execute("UPDATE registration_requests SET reviewed_by=NULL WHERE reviewed_by=?", (target_user_id,))
        conn.execute("UPDATE organization_requests SET reviewed_by=NULL WHERE reviewed_by=?", (target_user_id,))
        conn.execute("UPDATE organization_invites SET created_by=NULL WHERE created_by=?", (target_user_id,))
        conn.execute("UPDATE organization_credit_ledger SET operator_user_id=NULL WHERE operator_user_id=?", (target_user_id,))
        conn.execute("UPDATE xhs_order_redemptions SET redeemed_by_user_id=NULL WHERE redeemed_by_user_id=?", (target_user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (target_user_id,))

        if affected_class_ids:
            _sync_class_teacher_metadata(conn, affected_class_ids)


def update_user_role(user_id: int, role: str):
    if role not in {SUPER_OWNER_ROLE, OWNER_ROLE, ADMIN_ROLE, MEMBER_ROLE}:
        raise ValueError("role must be super_owner, owner, admin or member")
    with get_conn() as conn:
        user_row = _fetch_user_row_by_id(conn, user_id)
        if not user_row:
            raise LookupError("user not found")
        if _is_super_owner_role(user_row["role"]):
            raise ValueError("super owner role is fixed")
        conn.execute(
            "UPDATE users SET role=? WHERE id=?",
            (role, user_id)
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
    normalized_username = _normalize_username(username)
    with get_conn() as conn:
        row = _fetch_user_row_by_username(conn, normalized_username)
        if not row:
            if _pending_registration_exists(conn, normalized_username):
                return None, "该账号申请正在等待审批"
            return None, "用户名或密码错误"
        if row["status"] != "active":
            return None, "账号未启用"
        if row["password_hash"] != hash_password(password):
            return None, "用户名或密码错误"
        conn.execute(
            "UPDATE users SET last_login = datetime('now','localtime') WHERE id = ?",
            (row["id"],),
        )
    return _public_user_dict(row), None


def create_organization_request(
    organization_name: str,
    username: str,
    display_name: str,
    password: str,
):
    normalized_name = (organization_name or "").strip()
    normalized_username = _normalize_username(username)
    normalized_display_name = (display_name or "").strip()
    if not normalized_name or not normalized_username or not normalized_display_name or not password:
        raise ValueError("organization request fields are required")
    with get_conn() as conn:
        if _organization_exists(conn, normalized_name) or _pending_organization_request_exists(conn, normalized_name):
            raise ValueError("organization already exists")
        if _is_owner_username(normalized_username) or _user_exists_with_username(conn, normalized_username):
            raise ValueError("username already exists")
        if _pending_registration_exists(conn, normalized_username) or _pending_organization_request_username_exists(conn, normalized_username):
            raise ValueError("username already pending")
        cur = conn.execute(
            """
            INSERT INTO organization_requests
                (organization_name, username, password_hash, display_name, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                normalized_name,
                normalized_username,
                hash_password(password),
                normalized_display_name,
                ORGANIZATION_REQUEST_PENDING,
            ),
        )
        row = conn.execute(
            "SELECT * FROM organization_requests WHERE id=?",
            (cur.lastrowid,),
        ).fetchone()
    return dict(row)


def list_organization_requests(status: str = ORGANIZATION_REQUEST_PENDING) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM organization_requests
            WHERE status=?
            ORDER BY created_at ASC, id ASC
            """,
            (status,),
        ).fetchall()
    return [dict(row) for row in rows]


def approve_organization_request(request_id: int, reviewer_id: int):
    with get_conn() as conn:
        req = conn.execute(
            "SELECT * FROM organization_requests WHERE id=?",
            (request_id,),
        ).fetchone()
        if not req:
            raise LookupError("organization request not found")
        if req["status"] != ORGANIZATION_REQUEST_PENDING:
            raise ValueError("organization request already handled")
        if _organization_exists(conn, req["organization_name"]):
            raise ValueError("organization already exists")
        if _is_owner_username(req["username"]) or _user_exists_with_username(conn, req["username"]):
            raise ValueError("username already exists")

        org = _ensure_organization(conn, req["organization_name"])
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
            VALUES (?, ?, ?, ?, 'active', ?)
            """,
            (req["username"], req["password_hash"], req["display_name"], OWNER_ROLE, org["id"]),
        )
        conn.execute(
            """
            UPDATE organization_requests
            SET status=?, reviewed_by=?, reviewed_at=datetime('now','localtime')
            WHERE id=?
            """,
            (ORGANIZATION_REQUEST_APPROVED, reviewer_id, request_id),
        )
        _revoke_active_organization_invites(conn, org["id"])
        invite = _create_organization_invite(conn, org["id"], reviewer_id)
        user_row = _fetch_user_row_by_id(conn, cur.lastrowid)
    return _public_user_dict(user_row), invite


def reject_organization_request(request_id: int, reviewer_id: int) -> None:
    with get_conn() as conn:
        req = conn.execute(
            "SELECT * FROM organization_requests WHERE id=?",
            (request_id,),
        ).fetchone()
        if not req:
            raise LookupError("organization request not found")
        if req["status"] != ORGANIZATION_REQUEST_PENDING:
            raise ValueError("organization request already handled")
        conn.execute(
            """
            UPDATE organization_requests
            SET status=?, reviewed_by=?, reviewed_at=datetime('now','localtime')
            WHERE id=?
            """,
            (ORGANIZATION_REQUEST_REJECTED, reviewer_id, request_id),
        )


def delete_organization(org_id: int) -> None:
    """Delete an organization and all its data. Cannot delete the default org."""
    with get_conn() as conn:
        org_row = conn.execute("SELECT id, name FROM organizations WHERE id=?", (org_id,)).fetchone()
        if not org_row:
            raise LookupError("organization not found")
        if org_row["name"] == DEFAULT_ORGANIZATION_NAME:
            raise ValueError("不能删除默认机构")
        # 1. questions (via lessons)
        conn.execute(
            "DELETE FROM questions WHERE lesson_id IN (SELECT id FROM lessons WHERE organization_id=?)",
            (org_id,),
        )
        # 2. lessons
        conn.execute("DELETE FROM lessons WHERE organization_id=?", (org_id,))
        # 3. user_classes and class_students (via classes)
        conn.execute(
            "DELETE FROM user_classes WHERE class_id IN (SELECT id FROM classes WHERE organization_id=?)",
            (org_id,),
        )
        conn.execute(
            "DELETE FROM class_students WHERE class_id IN (SELECT id FROM classes WHERE organization_id=?)",
            (org_id,),
        )
        # 4. classes
        conn.execute("DELETE FROM classes WHERE organization_id=?", (org_id,))
        # 5. consultations
        conn.execute("DELETE FROM consultations WHERE organization_id=?", (org_id,))
        # 6. registration_requests
        conn.execute("DELETE FROM registration_requests WHERE organization_id=?", (org_id,))
        # 7. organization_invites
        conn.execute("DELETE FROM organization_invites WHERE organization_id=?", (org_id,))
        # 8. auth_sessions (via users)
        conn.execute(
            "DELETE FROM auth_sessions WHERE user_id IN (SELECT id FROM users WHERE organization_id=?)",
            (org_id,),
        )
        # 9. user_classes (via users)
        conn.execute(
            "DELETE FROM user_classes WHERE user_id IN (SELECT id FROM users WHERE organization_id=?)",
            (org_id,),
        )
        # 10. ai_usage_ledger (via users, ON DELETE CASCADE but explicit for safety)
        conn.execute("DELETE FROM ai_usage_ledger WHERE organization_id=?", (org_id,))
        # 11. credit ledger and accounts (ON DELETE CASCADE but explicit)
        conn.execute("DELETE FROM organization_credit_ledger WHERE organization_id=?", (org_id,))
        conn.execute("DELETE FROM organization_credit_accounts WHERE organization_id=?", (org_id,))
        # 12. nullify xhs_order_redemptions references (nullable FK, no cascade)
        conn.execute(
            "UPDATE xhs_order_redemptions SET redeemed_organization_id=NULL WHERE redeemed_organization_id=?",
            (org_id,),
        )
        # 13. users
        conn.execute("DELETE FROM users WHERE organization_id=?", (org_id,))
        # 14. organization
        conn.execute("DELETE FROM organizations WHERE id=?", (org_id,))


def get_or_create_active_organization_invite(organization_id: int, actor_user_id: int):
    with get_conn() as conn:
        org_row = conn.execute("SELECT id FROM organizations WHERE id=?", (organization_id,)).fetchone()
        if not org_row:
            raise LookupError("organization not found")
        invite_row = _fetch_active_organization_invite(conn, organization_id)
        if invite_row:
            return _public_invite_dict(invite_row)
        return _create_organization_invite(conn, organization_id, actor_user_id)


def reset_organization_invite(organization_id: int, actor_user_id: int):
    with get_conn() as conn:
        org_row = conn.execute("SELECT id FROM organizations WHERE id=?", (organization_id,)).fetchone()
        if not org_row:
            raise LookupError("organization not found")
        _revoke_active_organization_invites(conn, organization_id)
        return _create_organization_invite(conn, organization_id, actor_user_id)


def get_organization_invite_by_token(invite_token: str):
    with get_conn() as conn:
        row = _fetch_active_organization_invite_by_token(conn, invite_token)
    return _public_invite_dict(row)


def _get_class_invite_row(conn: sqlite3.Connection, class_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM class_invite_codes
        WHERE class_id=? AND status='active'
        ORDER BY id DESC
        LIMIT 1
        """,
        (class_id,),
    ).fetchone()


def get_or_create_active_class_invite(class_id: int, actor_user_id: int) -> dict:
    with get_conn() as conn:
        class_row = conn.execute(
            "SELECT id, organization_id FROM classes WHERE id=?",
            (class_id,),
        ).fetchone()
        if not class_row:
            raise LookupError("class not found")

        invite_row = _get_class_invite_row(conn, class_id)
        if invite_row:
            return dict(invite_row)

        invite_code = secrets.token_hex(3).upper()
        conn.execute(
            """
            INSERT INTO class_invite_codes (
                organization_id, class_id, invite_code, status, created_by_user_id
            ) VALUES (?, ?, ?, 'active', ?)
            """,
            (class_row["organization_id"], class_id, invite_code, actor_user_id),
        )
        created = _get_class_invite_row(conn, class_id)
    return dict(created) if created else {}


def reset_class_invite(class_id: int, actor_user_id: int) -> dict:
    with get_conn() as conn:
        class_row = conn.execute(
            "SELECT id, organization_id FROM classes WHERE id=?",
            (class_id,),
        ).fetchone()
        if not class_row:
            raise LookupError("class not found")

        conn.execute(
            """
            UPDATE class_invite_codes
            SET status='revoked', revoked_at=datetime('now','localtime')
            WHERE class_id=? AND status='active'
            """,
            (class_id,),
        )
        invite_code = secrets.token_hex(3).upper()
        conn.execute(
            """
            INSERT INTO class_invite_codes (
                organization_id, class_id, invite_code, status, created_by_user_id
            ) VALUES (?, ?, ?, 'active', ?)
            """,
            (class_row["organization_id"], class_id, invite_code, actor_user_id),
        )
        created = _get_class_invite_row(conn, class_id)
    return dict(created) if created else {}


def upsert_parent_wechat_account(
    *,
    openid: str,
    nickname_snapshot: str = "",
    avatar_url_snapshot: str = "",
) -> dict:
    normalized_openid = (openid or "").strip()
    if not normalized_openid:
        raise ValueError("openid is required")

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM parent_wechat_accounts WHERE openid=?",
            (normalized_openid,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE parent_wechat_accounts
                SET nickname_snapshot=?, avatar_url_snapshot=?, updated_at=datetime('now','localtime')
                WHERE id=?
                """,
                (nickname_snapshot.strip(), avatar_url_snapshot.strip(), existing["id"]),
            )
            refreshed = conn.execute(
                "SELECT * FROM parent_wechat_accounts WHERE id=?",
                (existing["id"],),
            ).fetchone()
            return dict(refreshed) if refreshed else {}

        conn.execute(
            """
            INSERT INTO parent_wechat_accounts (
                openid, nickname_snapshot, avatar_url_snapshot, status
            ) VALUES (?, ?, ?, 'active')
            """,
            (normalized_openid, nickname_snapshot.strip(), avatar_url_snapshot.strip()),
        )
        created = conn.execute(
            "SELECT * FROM parent_wechat_accounts WHERE openid=?",
            (normalized_openid,),
        ).fetchone()
    return dict(created) if created else {}


def bind_parent_to_student(*, parent_wechat_account_id: int, class_id: int, student_id: int) -> dict:
    with get_conn() as conn:
        account_row = conn.execute(
            "SELECT id FROM parent_wechat_accounts WHERE id=?",
            (parent_wechat_account_id,),
        ).fetchone()
        if not account_row:
            raise LookupError("parent wechat account not found")

        class_row = conn.execute(
            "SELECT id, organization_id FROM classes WHERE id=?",
            (class_id,),
        ).fetchone()
        if not class_row:
            raise LookupError("class not found")

        student_row = conn.execute(
            """
            SELECT s.id
            FROM class_students cs
            JOIN students s ON s.id = cs.student_id
            WHERE cs.class_id=? AND s.id=?
            """,
            (class_id, student_id),
        ).fetchone()
        if not student_row:
            raise LookupError("student not found")

        teacher_user_id = get_class_teacher_user_id(class_id)
        if teacher_user_id is None:
            raise ValueError("class teacher is required")

        existing = conn.execute(
            """
            SELECT *
            FROM parent_student_bindings
            WHERE parent_wechat_account_id=? AND class_id=? AND student_id=? AND status='active'
            LIMIT 1
            """,
            (parent_wechat_account_id, class_id, student_id),
        ).fetchone()
        if existing:
            return dict(existing)

        conn.execute(
            """
            INSERT INTO parent_student_bindings (
                organization_id, parent_wechat_account_id, class_id, student_id, teacher_user_id, status
            ) VALUES (?, ?, ?, ?, ?, 'active')
            """,
            (
                class_row["organization_id"],
                parent_wechat_account_id,
                class_id,
                student_id,
                teacher_user_id,
            ),
        )
        created = conn.execute(
            """
            SELECT *
            FROM parent_student_bindings
            WHERE parent_wechat_account_id=? AND class_id=? AND student_id=? AND status='active'
            LIMIT 1
            """,
            (parent_wechat_account_id, class_id, student_id),
        ).fetchone()
    return dict(created) if created else {}


def get_parent_student_binding(binding_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM parent_student_bindings
            WHERE id=? AND status='active'
            """,
            (binding_id,),
        ).fetchone()
    return dict(row) if row else None


def get_parent_student_binding_for_student(parent_wechat_account_id: int, student_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM parent_student_bindings
            WHERE parent_wechat_account_id=? AND student_id=? AND status='active'
            ORDER BY id DESC
            LIMIT 1
            """,
            (parent_wechat_account_id, student_id),
        ).fetchone()
    return dict(row) if row else None


def list_parent_student_bindings_for_openid(open_id: str) -> list[dict]:
    normalized_openid = (open_id or "").strip()
    if not normalized_openid:
        return []

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                psb.*,
                c.name AS class_name,
                s.name AS student_name,
                u.display_name AS teacher_name
            FROM parent_student_bindings psb
            JOIN parent_wechat_accounts pwa ON pwa.id = psb.parent_wechat_account_id
            JOIN classes c ON c.id = psb.class_id
            JOIN students s ON s.id = psb.student_id
            LEFT JOIN users u ON u.id = psb.teacher_user_id
            WHERE pwa.openid=? AND psb.status='active'
            ORDER BY psb.id DESC
            """,
            (normalized_openid,),
        ).fetchall()
    return [dict(row) for row in rows]

def create_wechat_wrong_question_submission(
    *,
    binding_id: int,
    image_url: str,
    parent_note: str = "",
    child_raw_reason_text: str = "",
    child_reason_input_mode: str = "text",
    primary_error_type: str = "",
    secondary_error_summary: str = "",
) -> dict:
    normalized_image_url = (image_url or "").strip()
    if not normalized_image_url:
        raise ValueError("image_url is required")
    normalized_reason_input_mode = ((child_reason_input_mode or "text").strip() or "text").lower()
    if normalized_reason_input_mode not in WECHAT_CHILD_REASON_INPUT_MODES:
        raise ValueError("child_reason_input_mode must be text or voice")

    with get_conn() as conn:
        binding_row = conn.execute(
            """
            SELECT *
            FROM parent_student_bindings
            WHERE id=? AND status='active'
            """,
            (binding_id,),
        ).fetchone()
        if not binding_row:
            raise LookupError("binding not found")

        record_id = f"wechat-{secrets.token_hex(8)}"
        conn.execute(
            """
            INSERT INTO wrong_question_submissions (
                id, organization_id, source, parent_wechat_account_id, binding_id,
                class_id, student_id, teacher_user_id, image_url, parent_note,
                child_raw_reason_text, child_reason_input_mode,
                primary_error_type, secondary_error_summary, archive_status, status
            ) VALUES (?, ?, 'wechat_mp', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 'pending')
            """,
            (
                record_id,
                binding_row["organization_id"],
                binding_row["parent_wechat_account_id"],
                binding_id,
                binding_row["class_id"],
                binding_row["student_id"],
                binding_row["teacher_user_id"],
                normalized_image_url,
                (parent_note or "").strip(),
                (child_raw_reason_text or "").strip(),
                normalized_reason_input_mode,
                (primary_error_type or "").strip(),
                (secondary_error_summary or "").strip(),
            ),
        )
        created = conn.execute(
            "SELECT * FROM wrong_question_submissions WHERE id=?",
            (record_id,),
        ).fetchone()
    return dict(created) if created else {}


def _serialize_wechat_wrong_question_submission_row(row: sqlite3.Row | None) -> Optional[dict]:
    if not row:
        return None

    payload = dict(row)
    payload["class_display_name"] = row["class_display_name"]
    payload["class_name_snapshot"] = row["class_display_name"]
    payload["student_name"] = row["student_name"]
    payload["teacher_display_name"] = row["teacher_display_name"]
    payload["teacher_name_snapshot"] = row["teacher_display_name"]
    payload["mapping_status"] = "mapped"
    payload["analysis"] = {}
    return payload


def _fetch_wechat_wrong_question_submission_row_by_id(
    conn: sqlite3.Connection,
    record_id: str,
) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            wqs.*,
            c.name AS class_display_name,
            s.name AS student_name,
            u.display_name AS teacher_display_name
        FROM wrong_question_submissions wqs
        JOIN classes c ON c.id = wqs.class_id
        JOIN students s ON s.id = wqs.student_id
        JOIN users u ON u.id = wqs.teacher_user_id
        WHERE wqs.id=?
        """,
        (record_id,),
    ).fetchone()


def list_wechat_wrong_question_submissions() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                wqs.*,
                c.name AS class_display_name,
                s.name AS student_name,
                u.display_name AS teacher_display_name
            FROM wrong_question_submissions wqs
            JOIN classes c ON c.id = wqs.class_id
            JOIN students s ON s.id = wqs.student_id
            JOIN users u ON u.id = wqs.teacher_user_id
            ORDER BY wqs.created_at DESC, wqs.id DESC
            """
        ).fetchall()
    return [
        item
        for item in (
            _serialize_wechat_wrong_question_submission_row(row)
            for row in rows
        )
        if item is not None
    ]


def list_wechat_wrong_question_submissions_for_parent_student(
    *,
    parent_wechat_account_id: int,
    student_id: int,
) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                wqs.*,
                c.name AS class_display_name,
                s.name AS student_name,
                u.display_name AS teacher_display_name
            FROM wrong_question_submissions wqs
            JOIN classes c ON c.id = wqs.class_id
            JOIN students s ON s.id = wqs.student_id
            JOIN users u ON u.id = wqs.teacher_user_id
            WHERE wqs.parent_wechat_account_id=? AND wqs.student_id=?
            ORDER BY wqs.created_at DESC, wqs.id DESC
            """,
            (parent_wechat_account_id, student_id),
        ).fetchall()
    return [
        item
        for item in (
            _serialize_wechat_wrong_question_submission_row(row)
            for row in rows
        )
        if item is not None
    ]


def get_wechat_wrong_question_submission(record_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
    return _serialize_wechat_wrong_question_submission_row(row)


def set_wechat_wrong_question_archive_status(record_id: str, archive_status: str) -> Optional[dict]:
    normalized_status = (archive_status or "").strip() or "active"
    if normalized_status not in {"active", "archived"}:
        raise ValueError("archive_status must be active or archived")

    with get_conn() as conn:
        row = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        if not row:
            return None
        conn.execute(
            """
            UPDATE wrong_question_submissions
            SET archive_status=?,
                archived_at=CASE WHEN ?='archived' THEN datetime('now','localtime') ELSE '' END,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (normalized_status, normalized_status, record_id),
        )
        refreshed = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
    return _serialize_wechat_wrong_question_submission_row(refreshed)


def save_wechat_wrong_question_review(record_id: str, payload: dict) -> Optional[dict]:
    teacher_comment = str(payload.get("teacher_comment") or "").strip()
    status = str(payload.get("status") or "").strip() or "pending"

    with get_conn() as conn:
        row = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        if not row:
            return None
        conn.execute(
            """
            UPDATE wrong_question_submissions
            SET teacher_comment=?, status=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (teacher_comment, status, record_id),
        )
        refreshed = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
    return _serialize_wechat_wrong_question_submission_row(refreshed)


def _create_member_from_invite_row(
    conn: sqlite3.Connection,
    invite_row: sqlite3.Row,
    username: str,
    display_name: str,
    password: str,
):
    normalized_username = _normalize_username(username)
    normalized_display_name = (display_name or "").strip()
    if not normalized_username or not normalized_display_name or not password:
        raise ValueError("join fields are required")
    if _is_owner_username(normalized_username) or _user_exists_with_username(conn, normalized_username):
        raise ValueError("username already exists")
    if _pending_registration_exists(conn, normalized_username) or _pending_organization_request_username_exists(conn, normalized_username):
        raise ValueError("username already pending")
    cur = conn.execute(
        """
        INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
        VALUES (?, ?, ?, ?, 'active', ?)
        """,
        (
            normalized_username,
            hash_password(password),
            normalized_display_name,
            MEMBER_ROLE,
            invite_row["organization_id"],
        ),
    )
    user_row = _fetch_user_row_by_id(conn, cur.lastrowid)
    return _public_user_dict(user_row)


def join_organization_by_invite_code(invite_code: str, username: str, display_name: str, password: str):
    with get_conn() as conn:
        invite_row = _fetch_active_organization_invite_by_code(conn, invite_code)
        if not invite_row:
            raise LookupError("invite not found")
        return _create_member_from_invite_row(conn, invite_row, username, display_name, password)


def join_organization_by_invite_link_token(invite_token: str, username: str, display_name: str, password: str):
    with get_conn() as conn:
        invite_row = _fetch_active_organization_invite_by_token(conn, invite_token)
        if not invite_row:
            raise LookupError("invite not found")
        return _create_member_from_invite_row(conn, invite_row, username, display_name, password)


def create_registration_request(username: str, display_name: str, password: str,
                                organization_name: str = DEFAULT_ORGANIZATION_NAME):
    normalized_username = _normalize_username(username)
    with get_conn() as conn:
        org = _ensure_organization(conn, organization_name)
        if _is_owner_username(normalized_username) or _user_exists_with_username(conn, normalized_username):
            raise ValueError("用户名已存在")
        if _pending_registration_exists(conn, normalized_username):
            raise ValueError("该用户名已有待审批申请")
        cur = conn.execute(
            """
            INSERT INTO registration_requests (username, password_hash, display_name, organization_id, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (normalized_username, hash_password(password), display_name, org["id"]),
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
        if _is_owner_username(req["username"]) or _user_exists_with_username(conn, req["username"]):
            raise ValueError("用户名已存在")
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
            VALUES (?, ?, ?, ?, 'active', ?)
            """,
            (req["username"], req["password_hash"], req["display_name"], MEMBER_ROLE, req["organization_id"]),
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
    from review_plan_templates.single_lesson_pdf import generate_single_lesson_pdf
    safe_topic = topic.replace("/", "-").replace(" ", "_")[:30] if topic else "课程"
    pdf_name = f"{lesson_date}_{subject}_{safe_topic}.pdf"
    pdf_path = str(PDF_DIR / pdf_name)
    generate_single_lesson_pdf(plan, pdf_path)
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
