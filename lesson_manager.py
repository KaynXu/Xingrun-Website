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
  python lesson_manager.py open --id 3                 # 用系统 PDF 查看器打开
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config_runtime import get_runtime_config
from class_commentary import (
    CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3,
    get_class_commentary_structured_prompt_contract,
    read_class_commentary_skill_package_content,
)
from class_commentary_feedback_schema import (
    CLASS_COMMENTARY_ATTENDING_ROSTER_SCOPE_V1,
    CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_DISABLED_V1,
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
    CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
    CLASS_COMMENTARY_STUDENT_NAME_MATCHER_V1,
    CLASS_COMMENTARY_STRUCTURED_RESPONSE_FORMAT,
    ClassCommentaryStudentScopeError,
    ClassCommentaryStructuredFeedbackValidationError,
    build_class_commentary_eligible_scope_hash,
    build_class_commentary_feedback_read_envelope,
    canonicalize_class_commentary_structured_feedback,
    canonicalize_class_commentary_structured_feedback_replay,
    match_class_commentary_eligible_student_ids,
    resolve_class_commentary_attending_roster_student_ids,
    validate_class_commentary_structured_generation_contract,
)
from class_commentary_memory_privacy import validate_class_commentary_memory_privacy
from class_commentary_student_memory_v2 import (
    CLASS_COMMENTARY_STUDENT_RUN_SCHEMA_V1,
    build_safe_class_context,
    build_student_current_evidence,
    canonical_hash as class_commentary_student_canonical_hash,
    canonical_json as class_commentary_student_canonical_json,
)
from review_plan_workflow.generation_options import (
    generation_options_summary,
    normalize_generation_options,
)
from review_plan_workflow.source_pack import build_lesson_source_pack_from_artifact

# ─── 路径配置 ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.resolve()
DATA_DIR   = BASE_DIR / "data"
PDF_DIR    = DATA_DIR / "pdfs"
DEFAULT_DB_PATH = DATA_DIR / "xingrun.db"
CFG_PATH   = BASE_DIR / "config.json"
DEFAULT_ORGANIZATION_NAME = "星润Starain"
OWNER_USERNAME = "kayn"
OWNER_DISPLAY_NAME = "平台管理员"
SUPER_OWNER_ROLE = "super_owner"
OWNER_ROLE = "owner"
ADMIN_ROLE = "admin"
MEMBER_ROLE = "member"
CONFIGURABLE_VISIBLE_PAGES = (
    "review-generation",
    "class-feedback-generation",
    "curriculum-knowledge",
    "consultation",
    "calendar",
    "smartWrongQuestions",
    "classes",
)
CLASS_SUBJECT_KEY_ALIASES = {
    "math": "math",
    "mathematics": "math",
    "数学": "math",
    "chinese": "chinese",
    "语文": "chinese",
    "english": "english",
    "英语": "english",
    "physics": "physics",
    "物理": "physics",
    "chemistry": "chemistry",
    "化学": "chemistry",
    "biology": "biology",
    "生物": "biology",
    "history": "history",
    "历史": "history",
    "geography": "geography",
    "地理": "geography",
    "politics": "politics",
    "政治": "politics",
    "science": "science",
    "科学": "science",
}
CLASS_COMMENTARY_LEARNING_EVIDENCE_SCHEMA_VERSION = "class-commentary-learning-evidence-v1"
CLASS_COMMENTARY_LEARNING_EVIDENCE_SELECTOR_VERSION = "class-commentary-learning-evidence-selector-v1"
CLASS_COMMENTARY_MEMORY_EXTRACTOR_VERSION = "class-commentary-memory-extractor-v1"
CLASS_COMMENTARY_MEMORY_SCHEMA_VERSION = "class-commentary-memory-v1"
CLASS_COMMENTARY_MEMORY_NORMALIZATION_VERSION = "class-commentary-memory-normalization-v1"
CLASS_COMMENTARY_SKILL_SELECTION_POLICY_VERSION = "class-commentary-skill-selection-v3"
WECHAT_CHILD_REASON_INPUT_MODES = {"text", "voice"}
PRIMARY_WRONG_QUESTION_TOPIC_UNCLASSIFIED = "未分类"
PRIMARY_WRONG_QUESTION_TOPIC_PRESETS = (
    PRIMARY_WRONG_QUESTION_TOPIC_UNCLASSIFIED,
    "计算",
    "经济",
    "浓度",
    "工程",
    "行程",
    "几何",
    "数论",
)
ORGANIZATION_REQUEST_PENDING = "pending"
ORGANIZATION_REQUEST_APPROVED = "approved"
ORGANIZATION_REQUEST_REJECTED = "rejected"
ORGANIZATION_INVITE_ACTIVE = "active"
ORGANIZATION_INVITE_REVOKED = "revoked"
CONSULTATION_TEACHERS_JSON_CANDIDATES = [
    DATA_DIR / "teachers.json",
    Path.home() / ".openclaw" / "workspace" / "teachers.json",
    Path.home() / ".openclaw" / "workspace-wecom" / "teachers.json",
]


def normalize_primary_wrong_question_topic_category(value: str = "") -> str:
    normalized = (value or "").strip()
    return normalized or PRIMARY_WRONG_QUESTION_TOPIC_UNCLASSIFIED


def is_primary_school_class_name(class_name: str, grade: str = "") -> bool:
    text = f"{class_name or ''} {grade or ''}"
    if re.search(r"(初中|高中|初[一二三123]|高[一二三123]|[七八九789]年级|十[一二]?年级|1[0-2]年级)", text):
        return False
    return bool(re.search(r"(小学|小[一二三四五六123456]|[一二三四五六123456]年级)", text))


def _normalize_topic_match_key(value: str) -> str:
    normalized = re.sub(r"[\s,，.。;；:：、\-_/\\（）()【】\[\]{}]+", "", (value or "").strip())
    for suffix in ("问题", "题", "类"):
        if normalized.endswith(suffix) and len(normalized) > len(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return normalized


def _topic_category_matches(candidate: str, query: str) -> bool:
    candidate_key = _normalize_topic_match_key(candidate)
    query_key = _normalize_topic_match_key(query)
    if not candidate_key or not query_key:
        return False
    if candidate_key == query_key:
        return True
    if len(candidate_key) >= 2 and candidate_key in query_key:
        return True
    return len(query_key) >= 2 and query_key in candidate_key


def _normalize_json_storage_value(
    value: object,
    *,
    field_name: str,
    default: str,
) -> str:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    text = str(value).strip()
    if not text:
        return default
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be valid JSON") from exc
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


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
CONSULTATION_FOLLOW_UP_STATUS_OPTIONS = ("待邀约", "跟进中", "已报班", "已劝退")
CONSULTATION_FLOW_STAGES = (
    "已加小客服微信",
    "已加对应教师微信",
    "正在沟通细节",
    "待测试",
    "待试听",
    "成功进班",
    "试听失败",
    "咨询结束",
)
CONSULTATION_DEFAULT_FLOW_STAGE = "已加小客服微信"
CONSULTATION_FLOW_STAGE_DERIVED_STATUS = {
    "已加小客服微信": "待跟进",
    "已加对应教师微信": "待跟进",
    "正在沟通细节": "正在跟进",
    "待测试": "正在跟进",
    "待试听": "正在跟进",
    "试听失败": "正在跟进",
    "成功进班": "完成",
    "咨询结束": "完成",
}
CONSULTATION_TERMINAL_STAGES = {"成功进班", "咨询结束"}
CONSULTATION_LEGACY_STATUS_STAGE_MAP = {
    "待邀约": "已加小客服微信",
    "跟进中": "正在沟通细节",
    "已报班": "成功进班",
    "已劝退": "咨询结束",
}
CONSULTATION_STAGE_API_FIELDS = {
    "flow_stage",
    "completed_stages",
    "stage_teacher_ids",
    "assigned_stage",
    "assignment_note",
    "customer_service_added",
    "customer_service_teacher",
    "customer_service_note",
    "communication_teacher_added",
    "communication_teacher_note",
    "test_taken",
    "test_teacher",
    "test_note",
    "test_images",
    "trial_teacher_added",
    "trial_teacher_note",
    "trial_taken",
    "trial_time_slot",
    "trial_class_id",
    "trial_class_manual",
    "trial_teacher",
    "trial_feedback",
    "teaching_teacher_added",
    "teaching_teacher",
    "teaching_teacher_note",
    "success_class_id",
    "success_class_manual",
    "enrollment_handoff_note",
    "student_profile_status",
    "student_profile_note",
    "failure_reason",
    "failure_note",
    "closing_result",
    "closed_by_user_id",
    "end_note",
}

CONSULTATION_STAGE_RESPONSIBILITY_LABELS = {
    "已加小客服微信": "客服",
    "已加对应教师微信": "沟通教师",
    "正在沟通细节": "沟通教师",
    "待测试": "测试教师",
    "待试听": "试听教师",
    "成功进班": "带课教师",
}
CONSULTATION_STAGE_FIELD_GROUPS = {
    "已加小客服微信": {"customer_service_added", "customer_service_teacher", "customer_service_note"},
    "已加对应教师微信": {"communication_teacher_added", "communication_teacher_note"},
    "正在沟通细节": {
        "communication_teacher_added",
        "communication_teacher_note",
        "receiving_teacher",
        "teacher_id",
        "follow_up_status",
        "follow_up_note",
        "接待老师",
        "老师ID",
        "跟进状态",
        "跟进备注",
    },
    "待测试": {"test_taken", "test_teacher", "test_note", "test_images"},
    "待试听": {
        "trial_teacher_added",
        "trial_teacher_note",
        "trial_taken",
        "trial_time_slot",
        "trial_class_id",
        "trial_class_manual",
        "trial_teacher",
        "trial_feedback",
    },
    "成功进班": {
        "success_class_id",
        "teaching_teacher_added",
        "teaching_teacher",
        "teaching_teacher_note",
        "success_class_manual",
        "enrollment_handoff_note",
        "student_profile_status",
        "student_profile_note",
    },
    "咨询结束": {"failure_reason", "failure_note", "closing_result", "closed_by_user_id", "end_note"},
}
COURSE_CALENDAR_TIME_BLOCKS = (
    "08:00-10:00",
    "10:00-12:00",
    "14:00-16:00",
    "16:00-18:00",
    "18:00-20:00",
    "20:00-22:00",
)
LEGACY_COURSE_CALENDAR_TIME_BLOCKS = {
    "13:00-15:00": "14:00-16:00",
    "15:00-17:00": "16:00-18:00",
    "17:00-19:00": "18:00-20:00",
    "19:00-21:00": "20:00-22:00",
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

CONSULTATION_SEARCH_EXACT_FIELDS = (
    "日期",
    "date",
    "家长微信名",
    "parent_wechat_name",
    "孩子姓名",
    "child_name",
    "接待老师",
    "receiving_teacher",
    "teacher_display_name",
    "咨询科目",
    "consultation_subject",
    "年级",
    "grade",
    "来源渠道",
    "source_channel",
    "来源渠道备注",
    "source_channel_note",
    "跟进状态",
    "follow_up_status",
    "flow_stage",
    "test_taken",
    "trial_taken",
    "trial_time_slot",
    "trial_teacher",
    "success_class_manual",
)
CONSULTATION_SEARCH_LONG_TEXT_FIELDS = (
    "具体需求",
    "need_detail",
    "trial_feedback",
    "customer_service_note",
    "communication_teacher_note",
    "test_note",
    "trial_teacher_note",
    "teaching_teacher_note",
    "enrollment_handoff_note",
    "student_profile_note",
    "failure_reason",
    "failure_note",
    "end_note",
    "跟进备注",
    "follow_up_note",
)
CONSULTATION_SEARCH_FIELDS = CONSULTATION_SEARCH_EXACT_FIELDS + CONSULTATION_SEARCH_LONG_TEXT_FIELDS

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

    return data_dir / DEFAULT_DB_PATH.name


DB_PATH = resolve_db_path()


def _normalize_username(username: str) -> str:
    return (username or "").strip()


def _is_owner_username(username: str) -> bool:
    return _normalize_username(username).casefold() == OWNER_USERNAME


def _is_super_owner_role(role: str) -> bool:
    return (role or "").strip() == SUPER_OWNER_ROLE


def get_default_visible_pages_for_role(role: str) -> list[str]:
    return list(CONFIGURABLE_VISIBLE_PAGES)


def normalize_visible_pages(raw_pages: object) -> list[str]:
    if not isinstance(raw_pages, list):
        raise ValueError("visible_pages must be a list")
    allowed = set(CONFIGURABLE_VISIBLE_PAGES)
    normalized = []
    seen = set()
    for page in raw_pages:
        if not isinstance(page, str) or page not in allowed:
            raise ValueError("visible_pages contains invalid page")
        if page not in seen:
            seen.add(page)
            normalized.append(page)
    return normalized


def _load_visible_pages_for_user(row) -> list[str]:
    keys = row.keys() if hasattr(row, "keys") else []
    if "visible_pages_json" not in keys or row["visible_pages_json"] in (None, ""):
        return get_default_visible_pages_for_role(row["role"])
    try:
        raw_pages = json.loads(row["visible_pages_json"])
        return normalize_visible_pages(raw_pages)
    except (TypeError, ValueError, json.JSONDecodeError):
        return get_default_visible_pages_for_role(row["role"])


def _normalize_recovery_phone(phone: str) -> str:
    return re.sub(r"\D+", "", phone or "")


def _normalize_security_answer(answer: str) -> str:
    return (answer or "").strip().casefold()


def _normalize_account_recovery(
    recovery_phone: str = "",
    security_question: str = "",
    security_answer: str = "",
) -> tuple[str, str, str]:
    normalized_phone = _normalize_recovery_phone(recovery_phone)
    normalized_question = (security_question or "").strip()
    normalized_answer = _normalize_security_answer(security_answer)

    if normalized_phone and not (6 <= len(normalized_phone) <= 20):
        raise ValueError("电话号码格式不正确")
    if (normalized_question and not normalized_answer) or (normalized_answer and not normalized_question):
        raise ValueError("密保问题和答案需要一起填写")
    if not normalized_phone and not (normalized_question and normalized_answer):
        raise ValueError("请设置找回密码方式：电话号码或密保问题")

    return normalized_phone, normalized_question, hash_password(normalized_answer) if normalized_answer else ""


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


def _normalize_alias_values(raw_aliases: object) -> list[str]:
    if isinstance(raw_aliases, list):
        return [str(alias).strip() for alias in raw_aliases if str(alias).strip()]
    if isinstance(raw_aliases, str):
        return [alias.strip() for alias in raw_aliases.split(",") if alias.strip()]
    return []


def _load_consultation_teacher_alias_records() -> dict[str, dict]:
    alias_records: dict[str, dict] = {}
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
            linked_username = ""
            if isinstance(raw_aliases, dict):
                display_name = str(raw_aliases.get("display_name") or "").strip()
                linked_username = str(raw_aliases.get("linked_username") or raw_aliases.get("username") or "").strip()
                normalized_aliases = _normalize_alias_values(raw_aliases.get("aliases"))
                if display_name and display_name not in normalized_aliases:
                    normalized_aliases.insert(0, display_name)
            else:
                normalized_aliases = _normalize_alias_values(raw_aliases)
            if not normalized_aliases:
                continue
            existing = alias_records.setdefault(
                teacher_key,
                {
                    "wecom_userid": teacher_key,
                    "display_name": normalized_aliases[0],
                    "aliases": [],
                    "linked_username": "",
                },
            )
            for alias in normalized_aliases:
                if alias not in existing["aliases"]:
                    existing["aliases"].append(alias)
            if linked_username and not existing["linked_username"]:
                existing["linked_username"] = linked_username
    return alias_records


def _get_teachers_json_path() -> Path:
    """Return the first existing teachers.json path, or fall back to data/teachers.json."""
    for candidate in CONSULTATION_TEACHERS_JSON_CANDIDATES:
        if candidate.exists():
            return candidate
    return CONSULTATION_TEACHERS_JSON_CANDIDATES[0]


def _save_teacher_alias_records(alias_records: dict[str, dict]) -> None:
    path = _get_teachers_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized: dict[str, object] = {}
    for teacher_id, record in sorted(alias_records.items(), key=lambda item: item[0].lower()):
        aliases = _normalize_alias_values(record.get("aliases"))
        display_name = str(record.get("display_name") or (aliases[0] if aliases else "")).strip()
        linked_username = str(record.get("linked_username") or "").strip()
        if display_name and display_name not in aliases:
            aliases.insert(0, display_name)
        if not aliases:
            continue
        if linked_username:
            serialized[teacher_id] = {
                "display_name": aliases[0],
                "aliases": aliases,
                "linked_username": linked_username,
            }
        else:
            serialized[teacher_id] = aliases
    path.write_text(json.dumps(serialized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_teacher_alias_entries() -> list[dict]:
    """Return raw alias entries from teachers.json as a list of dicts."""
    alias_records = _load_consultation_teacher_alias_records()
    entries = []
    for teacher_id, record in sorted(alias_records.items(), key=lambda x: x[0].lower()):
        aliases = record["aliases"]
        entries.append({
            "wecom_userid": teacher_id,
            "display_name": record.get("display_name") or (aliases[0] if aliases else teacher_id),
            "aliases": aliases,
            "linked_username": record.get("linked_username", ""),
        })
    return entries


def _resolve_active_username(username: str) -> str:
    username = username.strip()
    if not username:
        return ""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT username FROM users WHERE lower(username)=lower(?) AND status='active'",
            (username,),
        ).fetchone()
    return row["username"] if row else ""


def upsert_teacher_alias(
    wecom_userid: str,
    display_name: str,
    aliases: list[str] | None = None,
    linked_username: str = "",
) -> dict:
    """Create or update a teacher alias mapping. Returns the updated entry."""
    wecom_userid = wecom_userid.strip()
    display_name = display_name.strip()
    linked_username = linked_username.strip()
    if not wecom_userid:
        raise ValueError("企微ID不能为空")
    if not display_name:
        raise ValueError("中文名不能为空")
    if linked_username:
        linked_username = _resolve_active_username(linked_username)
        if not linked_username:
            raise ValueError("关联的网站成员不存在")
    alias_records = _load_consultation_teacher_alias_records()
    merged = [display_name]
    for a in (aliases or []):
        a = a.strip()
        if a and a not in merged:
            merged.append(a)
    alias_records[wecom_userid] = {
        "wecom_userid": wecom_userid,
        "display_name": display_name,
        "aliases": merged,
        "linked_username": linked_username,
    }
    _save_teacher_alias_records(alias_records)
    return {
        "wecom_userid": wecom_userid,
        "display_name": display_name,
        "aliases": merged,
        "linked_username": linked_username,
    }


def delete_teacher_alias(wecom_userid: str) -> bool:
    """Delete a teacher alias mapping. Returns True if deleted, False if not found."""
    wecom_userid = wecom_userid.strip()
    alias_records = _load_consultation_teacher_alias_records()
    if wecom_userid not in alias_records:
        return False
    del alias_records[wecom_userid]
    _save_teacher_alias_records(alias_records)
    return True


def _get_consultation_teacher_directory() -> dict[str, str]:
    alias_records = _load_consultation_teacher_alias_records()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT username, display_name
            FROM users
            WHERE status = 'active'
            """
        ).fetchall()
    directory: dict[str, str] = {}
    display_by_username: dict[str, str] = {}
    for row in rows:
        username = (row["username"] or "").strip()
        display_name = (row["display_name"] or "").strip()
        if username and display_name:
            display_by_username[username.lower()] = display_name
            directory[username.lower()] = display_name
        if display_name:
            directory[display_name.lower()] = display_name
    for teacher_id, record in alias_records.items():
        teacher_key = teacher_id.lower()
        if not teacher_key:
            continue
        linked_username = str(record.get("linked_username") or "").strip()
        aliases = record.get("aliases") or []
        display_name = (
            display_by_username.get(linked_username.lower())
            or str(record.get("display_name") or "").strip()
            or (aliases[0] if aliases else "")
        )
        if not display_name:
            continue
        for alias in [teacher_id, linked_username, *aliases]:
            alias_key = str(alias or "").strip().lower()
            if alias_key and alias_key not in directory:
                directory[alias_key] = display_name
    return directory


def resolve_teacher_username_to_user_id(username: str) -> Optional[int]:
    """Resolve a teacher username to the corresponding users.id."""
    if not username:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE username=? AND status='active'",
            (username,),
        ).fetchone()
    if row:
        return row["id"]
    _, resolved_username = _normalize_consultation_teacher_assignment("", username)
    if not resolved_username or resolved_username == username:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE username=? AND status='active'",
            (resolved_username,),
        ).fetchone()
    return row["id"] if row else None


def _consultation_teacher_identifiers_for_user(actor_user: dict) -> set[str]:
    username = str((actor_user or {}).get("username") or "").strip()
    identifiers = {username.lower()} if username else set()
    if not username:
        return identifiers
    for item in list_consultation_teachers():
        teacher_id = str(item.get("teacher_id") or "").strip()
        if teacher_id.lower() != username.lower():
            continue
        for value in [teacher_id, item.get("display_name"), *item.get("aliases", [])]:
            normalized = str(value or "").strip().lower()
            if normalized:
                identifiers.add(normalized)
        break
    return identifiers


def list_consultation_teachers() -> list[dict]:
    alias_records = _load_consultation_teacher_alias_records()
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

    # Build a case-insensitive lookup: lowercase(username) -> canonical teacher_id
    username_lower_map: dict[str, str] = {}
    # Build a display_name -> canonical teacher_id lookup for alias dedup
    display_name_lower_map: dict[str, str] = {}

    for row in rows:
        teacher_id = (row["username"] or "").strip()
        display_name = (row["display_name"] or "").strip()
        if not teacher_id:
            continue
        username_lower_map[teacher_id.lower()] = teacher_id
        if display_name:
            display_name_lower_map[display_name.lower()] = teacher_id
        aliases: list[str] = []
        for alias_key, record in alias_records.items():
            linked_username = str(record.get("linked_username") or "").strip()
            if alias_key.lower() == teacher_id.lower() or linked_username.lower() == teacher_id.lower():
                aliases.extend(record.get("aliases") or [])
                if alias_key.lower() != teacher_id.lower():
                    aliases.append(alias_key)
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

    for teacher_id, record in alias_records.items():
        aliases = record.get("aliases") or []
        linked_username = str(record.get("linked_username") or "").strip()
        linked_canonical = username_lower_map.get(linked_username.lower()) if linked_username else None
        if linked_canonical:
            continue
        # Case-insensitive match against DB usernames
        canonical = username_lower_map.get(teacher_id.lower())
        if canonical:
            entry = teacher_entries[canonical]
            for alias in aliases:
                if alias not in entry["aliases"]:
                    entry["aliases"].append(alias)
            if not entry["display_name"] and entry["aliases"]:
                entry["display_name"] = entry["aliases"][0]
            continue
        # Check if any alias matches an existing DB user's display_name
        matched_canonical = None
        for alias in aliases:
            matched_canonical = display_name_lower_map.get(alias.lower())
            if matched_canonical:
                break
        if matched_canonical:
            entry = teacher_entries[matched_canonical]
            for alias in [teacher_id, *aliases]:
                if alias not in entry["aliases"]:
                    entry["aliases"].append(alias)
            continue
        # Truly new teacher only from JSON
        teacher_entries[teacher_id] = {
            "teacher_id": teacher_id,
            "display_name": record.get("display_name") or aliases[0],
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


def _json_dict(value: object) -> dict:
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items() if str(key).strip() and str(item).strip()}
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return {str(key): str(item) for key, item in parsed.items() if str(key).strip() and str(item).strip()}
    return {}


def _normalize_consultation_flow_stage(value: object, legacy_status: str = "") -> str:
    stage = str(value or "").strip()
    if stage in CONSULTATION_FLOW_STAGES:
        return stage
    mapped = CONSULTATION_LEGACY_STATUS_STAGE_MAP.get((legacy_status or "").strip())
    return mapped or CONSULTATION_DEFAULT_FLOW_STAGE


def _normalize_consultation_completed_stages(value: object, current_stage: str) -> list[str]:
    seen = set()
    stages: list[str] = []
    for raw_stage in _json_list(value):
        stage = str(raw_stage or "").strip()
        if stage in CONSULTATION_FLOW_STAGES and stage not in seen:
            seen.add(stage)
            stages.append(stage)
    if current_stage and current_stage not in seen:
        stages.append(current_stage)
    return stages


def _derive_consultation_follow_up_status(flow_stage: str) -> str:
    return CONSULTATION_FLOW_STAGE_DERIVED_STATUS.get(flow_stage, "待跟进")


def _normalize_optional_int(value: object) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_consultation_stage_updates(data: Optional[dict]) -> dict:
    payload = data or {}
    updates: dict = {}
    for field in CONSULTATION_STAGE_API_FIELDS:
        if field in payload:
            updates[field] = payload.get(field)
    return updates


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


def _normalize_consultation_batch_fields(fields: Optional[dict]) -> tuple[dict[str, str], list[str]]:
    if fields is None:
        fields = {}
    if not isinstance(fields, dict):
        raise ValueError("AI 解析返回了无效结果")
    updates = _extract_consultation_updates(fields or {})
    normalized: dict[str, str] = {}
    warnings: list[str] = []
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

    if "follow_up_status" in normalized:
        follow_up_status = normalized.get("follow_up_status", "").strip()
        if not follow_up_status:
            normalized["follow_up_status"] = ""
        elif follow_up_status in CONSULTATION_FOLLOW_UP_STATUS_OPTIONS:
            normalized["follow_up_status"] = follow_up_status
        else:
            normalized.pop("follow_up_status", None)
            warnings.append(
                "已忽略不存在的跟进状态："
                f"{follow_up_status}。可选值仅支持：{'、'.join(CONSULTATION_FOLLOW_UP_STATUS_OPTIONS)}。"
            )

    return normalized, warnings


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
        normalized_fields, field_warnings = _normalize_consultation_batch_fields(raw_item.get("fields"))
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
                ] + field_warnings,
            }
        )
    return {
        "items": items,
        "warnings": warnings,
    }

def _consultation_search_value(row: dict, field: str) -> str:
    value = row.get(field, "")
    if isinstance(value, list):
        return " ".join(str(item or "") for item in value)
    return str(value or "")


def _consultation_search_exact_match(row: dict, normalized_keyword: str) -> bool:
    return any(
        _consultation_search_value(row, field).strip().casefold() == normalized_keyword
        for field in CONSULTATION_SEARCH_EXACT_FIELDS
    ) or any(
        normalized_keyword in _consultation_search_value(row, field).casefold()
        for field in CONSULTATION_SEARCH_LONG_TEXT_FIELDS
    )


def _consultation_search_fuzzy_match(row: dict, normalized_keyword: str) -> bool:
    return normalized_keyword in " ".join(
        _consultation_search_value(row, field).casefold()
        for field in CONSULTATION_SEARCH_FIELDS
    )


def _consultation_matches_search(row: dict, keyword: str, search_mode: str = "fuzzy") -> bool:
    normalized_keyword = (keyword or "").strip().casefold()
    if not normalized_keyword:
        return True
    if search_mode == "exact":
        return _consultation_search_exact_match(row, normalized_keyword)
    return _consultation_search_fuzzy_match(row, normalized_keyword)


def _consultation_search_rank(row: dict, keyword: str) -> Optional[int]:
    normalized_keyword = (keyword or "").strip().casefold()
    if not normalized_keyword:
        return 0
    if _consultation_search_exact_match(row, normalized_keyword):
        return 0
    if _consultation_search_fuzzy_match(row, normalized_keyword):
        return 1
    return None


def list_consultations(
    query: str = "",
    search_mode: str = "fuzzy",
    organization_id: Optional[int] = None,
    assigned_user_id: Optional[int] = None
) -> list[dict]:
    teacher_directory = _get_consultation_teacher_directory()
    with get_conn() as conn:
        query_sql = """
            SELECT c.*, u.display_name, u.username
            FROM consultations c
            LEFT JOIN users u ON c.assigned_user_id = u.id
        """
        params: list[object] = []
        conditions = []
        if organization_id is not None:
            conditions.append("c.organization_id=?")
            params.append(organization_id)
        if assigned_user_id is not None:
            conditions.append("c.assigned_user_id=?")
            params.append(assigned_user_id)
        
        if conditions:
            query_sql += " WHERE " + " AND ".join(conditions)
        
        query_sql += " ORDER BY c.updated_at DESC, c.created_at DESC, c.id DESC"
        rows = conn.execute(query_sql, params).fetchall()

    serialized_rows = [
        _consultation_storage_row_to_public_dict(row, teacher_directory)
        for row in rows
    ]
    keyword = (query or "").strip()
    if keyword:
        if search_mode == "exact":
            serialized_rows = [
                row for row in serialized_rows
                if _consultation_matches_search(row, keyword, search_mode)
            ]
        else:
            ranked_rows = []
            for row in serialized_rows:
                rank = _consultation_search_rank(row, keyword)
                if rank is not None:
                    ranked_rows.append((rank, row))
            serialized_rows = [row for _, row in sorted(ranked_rows, key=lambda item: item[0])]
    return serialized_rows


def _consultation_current_assignment_context_for_actor(row: dict, actor_user: dict) -> dict | None:
    identifiers = _consultation_teacher_identifiers_for_user(actor_user)
    matched_stage = ""
    matched_teacher_id = ""
    legacy_direct_assignment = False
    assigned_stage = str(row.get("assigned_stage") or "").strip()
    stage_teacher_ids = row.get("stage_teacher_ids") or {}
    if assigned_stage:
        assigned_teacher_id = str(stage_teacher_ids.get(assigned_stage) or "").strip()
        if assigned_teacher_id.lower() in identifiers:
            matched_stage = assigned_stage
            matched_teacher_id = assigned_teacher_id
    if not matched_stage:
        flow_stage = str(row.get("flow_stage") or "").strip()
        flow_teacher_id = str(stage_teacher_ids.get(flow_stage) or "").strip()
        if flow_teacher_id.lower() in identifiers:
            matched_stage = flow_stage
            matched_teacher_id = flow_teacher_id
    explicit_stage_teacher_id = ""
    if assigned_stage:
        explicit_stage_teacher_id = str(stage_teacher_ids.get(assigned_stage) or "").strip()
    if not explicit_stage_teacher_id:
        flow_stage = str(row.get("flow_stage") or "").strip()
        explicit_stage_teacher_id = str(stage_teacher_ids.get(flow_stage) or "").strip()
    if not matched_stage and not explicit_stage_teacher_id and row.get("assigned_user_id") == actor_user.get("id"):
        matched_stage = assigned_stage or str(row.get("flow_stage") or "").strip()
        legacy_direct_assignment = True
    if not matched_stage:
        return None

    teacher_directory = _get_consultation_teacher_directory()
    teacher_name = (
        teacher_directory.get(matched_teacher_id.lower())
        or str(actor_user.get("display_name") or actor_user.get("username") or "").strip()
    )
    responsibility_label = CONSULTATION_STAGE_RESPONSIBILITY_LABELS.get(matched_stage, "负责教师")
    return {
        "assigned_stage": matched_stage,
        "transfer_marker": "咨询转接",
        "current_responsibility": f"{responsibility_label}：{teacher_name}" if teacher_name else responsibility_label,
        "legacy_direct_assignment": legacy_direct_assignment,
    }


def _consultation_current_responsibility_context(row: dict) -> dict | None:
    stage_teacher_ids = row.get("stage_teacher_ids") or {}
    current_stage = str(row.get("assigned_stage") or row.get("flow_stage") or "").strip()
    current_teacher_id = str(stage_teacher_ids.get(current_stage) or "").strip() if current_stage else ""
    teacher_name = ""
    if current_teacher_id:
        teacher_name = _get_consultation_teacher_directory().get(current_teacher_id.lower()) or current_teacher_id
    elif row.get("assigned_user_id") is not None:
        teacher_name = str(row.get("display_name") or row.get("username") or "").strip()
    else:
        return None
    responsibility_label = CONSULTATION_STAGE_RESPONSIBILITY_LABELS.get(current_stage, "负责教师")
    return {
        "assigned_stage": current_stage,
        "transfer_marker": "咨询转接",
        "current_responsibility": f"{responsibility_label}：{teacher_name}" if teacher_name else responsibility_label,
        "legacy_direct_assignment": False,
    }


def _consultation_assignment_context_for_actor(row: dict, actor_user: dict) -> dict | None:
    context = _consultation_current_assignment_context_for_actor(row, actor_user)
    if context:
        return context

    identifiers = _consultation_teacher_identifiers_for_user(actor_user)
    stage_teacher_ids = row.get("stage_teacher_ids") or {}
    teacher_directory = _get_consultation_teacher_directory()
    for stage in CONSULTATION_FLOW_STAGES:
        teacher_id = str(stage_teacher_ids.get(stage) or "").strip()
        if teacher_id.lower() in identifiers:
            current_stage = str(row.get("assigned_stage") or row.get("flow_stage") or stage).strip()
            current_teacher_id = str(stage_teacher_ids.get(current_stage) or "").strip()
            current_teacher_name = (
                teacher_directory.get(current_teacher_id.lower())
                if current_teacher_id else ""
            )
            responsibility_label = CONSULTATION_STAGE_RESPONSIBILITY_LABELS.get(current_stage, "负责教师")
            return {
                "assigned_stage": current_stage,
                "transfer_marker": "咨询转接",
                "current_responsibility": f"{responsibility_label}：{current_teacher_name}" if current_teacher_name else responsibility_label,
                "legacy_direct_assignment": False,
                "historical_assignment": True,
            }

    for history_item in _json_list(row.get("responsibility_history")):
        if not isinstance(history_item, dict):
            continue
        if str(history_item.get("change_kind") or "transfer").strip() not in {"transfer", "reassign"}:
            continue
        historical_ids = {
            str(history_item.get("from_teacher_id") or "").strip().lower(),
            str(history_item.get("to_teacher_id") or "").strip().lower(),
        }
        if not identifiers.intersection({item for item in historical_ids if item}):
            continue
        current_stage = str(row.get("assigned_stage") or row.get("flow_stage") or history_item.get("stage") or "").strip()
        current_teacher_id = str(stage_teacher_ids.get(current_stage) or "").strip()
        current_teacher_name = teacher_directory.get(current_teacher_id.lower()) if current_teacher_id else ""
        responsibility_label = CONSULTATION_STAGE_RESPONSIBILITY_LABELS.get(current_stage, "负责教师")
        return {
            "assigned_stage": current_stage,
            "transfer_marker": "咨询转接",
            "current_responsibility": f"{responsibility_label}：{current_teacher_name}" if current_teacher_name else responsibility_label,
            "legacy_direct_assignment": False,
            "historical_assignment": True,
        }

    if row.get("assigned_user_id") == actor_user.get("id"):
        current_stage = str(row.get("assigned_stage") or row.get("flow_stage") or "").strip()
        current_teacher_id = str(stage_teacher_ids.get(current_stage) or "").strip()
        current_teacher_name = teacher_directory.get(current_teacher_id.lower()) if current_teacher_id else ""
        responsibility_label = CONSULTATION_STAGE_RESPONSIBILITY_LABELS.get(current_stage, "负责教师")
        return {
            "assigned_stage": current_stage,
            "transfer_marker": "咨询转接",
            "current_responsibility": f"{responsibility_label}：{current_teacher_name}" if current_teacher_name else responsibility_label,
            "legacy_direct_assignment": False,
            "historical_assignment": True,
        }

    return None


def _annotate_consultation_for_actor(row: dict, actor_user: dict) -> dict:
    annotated = dict(row)
    is_creator = annotated.get("created_by_user_id") == actor_user.get("id")
    context = _consultation_assignment_context_for_actor(annotated, actor_user)
    current_context = _consultation_current_assignment_context_for_actor(annotated, actor_user)
    current_responsibility_context = _consultation_current_responsibility_context(annotated)
    creator_current_access = bool(is_creator and (current_context or not current_responsibility_context))
    creator_transferred_away = bool(is_creator and not creator_current_access)
    if context:
        annotated.update(context)
    elif creator_transferred_away and current_responsibility_context:
        annotated.update(current_responsibility_context)
    is_transferred = bool(context) and not is_creator and not context.get("legacy_direct_assignment")
    annotated.pop("legacy_direct_assignment", None)
    annotated.pop("historical_assignment", None)
    annotated["is_transferred_consultation"] = is_transferred
    annotated["can_edit_consultation"] = bool(creator_current_access or current_context)
    if not is_transferred and not creator_transferred_away:
        annotated["transfer_marker"] = ""
        annotated["current_responsibility"] = ""
    return annotated


def _consultation_teacher_name_for_history(teacher_id: str, teacher_directory: dict[str, str]) -> str:
    teacher_id = str(teacher_id or "").strip()
    if not teacher_id:
        return ""
    return teacher_directory.get(teacher_id.lower()) or teacher_id


def _append_responsibility_history_for_stage_teacher_changes(
    current: dict,
    next_row: dict,
    teacher_directory: dict[str, str],
    change_kind: str = "reassign",
) -> dict:
    current_stage_teacher_ids = current.get("stage_teacher_ids") or {}
    next_stage_teacher_ids = next_row.get("stage_teacher_ids") or {}
    current_history = [
        item for item in _json_list(current.get("responsibility_history"))
        if isinstance(item, dict)
    ]
    history = list(current_history)
    note = str(next_row.get("assignment_note") or "").strip()
    for stage in CONSULTATION_FLOW_STAGES:
        from_teacher_id = str(current_stage_teacher_ids.get(stage) or "").strip()
        to_teacher_id = str(next_stage_teacher_ids.get(stage) or "").strip()
        if not from_teacher_id or not to_teacher_id or from_teacher_id == to_teacher_id:
            continue
        history.append({
            "stage": stage,
            "from_teacher_id": from_teacher_id,
            "from_teacher_name": _consultation_teacher_name_for_history(from_teacher_id, teacher_directory),
            "to_teacher_id": to_teacher_id,
            "to_teacher_name": _consultation_teacher_name_for_history(to_teacher_id, teacher_directory),
            "note": note,
            "change_kind": change_kind if change_kind in {"transfer", "reassign"} else "reassign",
        })
    if history != current_history:
        return {**next_row, "responsibility_history": history}
    return next_row


def get_consultation_for_actor(actor_user: dict, consultation_id: int):
    item = get_consultation(
        consultation_id,
        None if (actor_user or {}).get("role") == SUPER_OWNER_ROLE else actor_user.get("organization_id"),
    )
    if not item:
        return None
    if actor_user.get("role") != MEMBER_ROLE:
        return item
    is_creator = item.get("created_by_user_id") == actor_user.get("id")
    has_assignment = _consultation_assignment_context_for_actor(item, actor_user) is not None
    if not is_creator and not has_assignment:
        return None
    return _annotate_consultation_for_actor(item, actor_user)


def _stage_index(stage: str) -> int:
    try:
        return CONSULTATION_FLOW_STAGES.index(stage)
    except ValueError:
        return -1


def _values_equal_for_permission(left: object, right: object) -> bool:
    if isinstance(left, (dict, list)) or isinstance(right, (dict, list)):
        return left == right
    return str(left or "") == str(right or "")


def _api_field_current_value(current: dict, field: str) -> object:
    if field in current:
        return current.get(field)
    csv_field = CONSULTATION_API_FIELD_MAP.get(field)
    if csv_field:
        return current.get(csv_field)
    return current.get(field)


def _consultation_stage_for_edit_field(field: str) -> str:
    for stage, fields in CONSULTATION_STAGE_FIELD_GROUPS.items():
        if field in fields:
            return stage
    return ""


def _transferred_consultation_field_change_touches_prior_stage(field: str, assigned_index: int) -> bool:
    stage = _consultation_stage_for_edit_field(field)
    if not stage:
        return True
    stage_index = _stage_index(stage)
    return stage_index < 0 or stage_index < assigned_index


def _completed_stages_before_index(stages: object, assigned_index: int) -> set[str]:
    return {
        str(stage or "").strip()
        for stage in _json_list(stages)
        if 0 <= _stage_index(str(stage or "").strip()) < assigned_index
    }


def _transferred_consultation_update_touches_prior_stage(data: dict, current: dict, assigned_stage: str) -> bool:
    assigned_index = _stage_index(assigned_stage)
    if assigned_index < 0:
        return False
    for field in CONSULTATION_EDITABLE_FIELDS:
        if field in data and not _values_equal_for_permission(data.get(field), _api_field_current_value(current, field)):
            if _transferred_consultation_field_change_touches_prior_stage(field, assigned_index):
                return True
    for api_field in CONSULTATION_API_FIELD_MAP:
        if api_field in data and not _values_equal_for_permission(data.get(api_field), _api_field_current_value(current, api_field)):
            if _transferred_consultation_field_change_touches_prior_stage(api_field, assigned_index):
                return True
    for field in ("assigned_stage",):
        if field in data and not _values_equal_for_permission(data.get(field), current.get(field)):
            return True
    if "completed_stages" in data:
        current_prior = _completed_stages_before_index(current.get("completed_stages"), assigned_index)
        next_prior = _completed_stages_before_index(data.get("completed_stages"), assigned_index)
        if current_prior != next_prior:
            return True
    if "stage_teacher_ids" in data:
        current_stage_teacher_ids = current.get("stage_teacher_ids") or {}
        next_stage_teacher_ids = data.get("stage_teacher_ids") or {}
        for stage in CONSULTATION_FLOW_STAGES:
            stage_index = _stage_index(stage)
            if 0 <= stage_index < assigned_index:
                if str(current_stage_teacher_ids.get(stage) or "") != str(next_stage_teacher_ids.get(stage) or ""):
                    return True
    if "flow_stage" in data:
        next_stage = str(data.get("flow_stage") or "").strip()
        next_index = _stage_index(next_stage)
        if 0 <= next_index < assigned_index:
            return True
    for stage, fields in CONSULTATION_STAGE_FIELD_GROUPS.items():
        stage_index = _stage_index(stage)
        if stage_index < 0 or stage_index >= assigned_index:
            continue
        for field in fields:
            if field in data and not _values_equal_for_permission(data.get(field), current.get(field)):
                return True
    return False


def _preserve_transferred_prior_stage_teacher_ids(data: dict, current: dict, assigned_stage: str) -> dict:
    if "stage_teacher_ids" not in data:
        return data
    assigned_index = _stage_index(assigned_stage)
    if assigned_index < 0:
        return data
    incoming_stage_teacher_ids = _json_dict(data.get("stage_teacher_ids"))
    current_stage_teacher_ids = current.get("stage_teacher_ids") or {}
    merged_stage_teacher_ids = dict(incoming_stage_teacher_ids)
    for stage in CONSULTATION_FLOW_STAGES:
        stage_index = _stage_index(stage)
        if 0 <= stage_index < assigned_index and stage not in merged_stage_teacher_ids:
            current_teacher_id = str(current_stage_teacher_ids.get(stage) or "").strip()
            if current_teacher_id:
                merged_stage_teacher_ids[stage] = current_teacher_id
    return {**data, "stage_teacher_ids": merged_stage_teacher_ids}


def update_consultation_for_actor(actor_user: dict, consultation_id: int, data: dict):
    current = get_consultation_for_actor(actor_user, consultation_id)
    if not current:
        return None
    organization_id = None if actor_user.get("role") == SUPER_OWNER_ROLE else actor_user.get("organization_id")
    if actor_user.get("role") == MEMBER_ROLE and not current.get("can_edit_consultation"):
        raise PermissionError("只有当前责任教师可以编辑咨询")
    if actor_user.get("role") == MEMBER_ROLE and current.get("is_transferred_consultation"):
        if _consultation_current_assignment_context_for_actor(current, actor_user) is None:
            raise PermissionError("只有当前责任教师可以编辑转接咨询")
        assigned_stage = str(current.get("assigned_stage") or "").strip()
        data = _preserve_transferred_prior_stage_teacher_ids(data or {}, current, assigned_stage)
        if _transferred_consultation_update_touches_prior_stage(data or {}, current, assigned_stage):
            raise PermissionError("转接咨询只能编辑转接阶段及后续流程")
    change_kind = "transfer" if actor_user.get("role") == MEMBER_ROLE else "reassign"
    updated = update_consultation(consultation_id, data, organization_id, None, change_kind)
    if actor_user.get("role") == MEMBER_ROLE and updated:
        return _annotate_consultation_for_actor(updated, actor_user)
    return updated


def get_consultation(consultation_id: int, organization_id: Optional[int] = None):
    teacher_directory = _get_consultation_teacher_directory()
    with get_conn() as conn:
        query_sql = """
            SELECT c.*, u.display_name, u.username
            FROM consultations c
            LEFT JOIN users u ON c.assigned_user_id = u.id
            WHERE c.id=?
        """
        params: list[object] = [consultation_id]
        if organization_id is not None:
            query_sql += " AND c.organization_id=?"
            params.append(organization_id)
        row = conn.execute(query_sql, params).fetchone()
    return _consultation_storage_row_to_public_dict(row, teacher_directory) if row else None


def create_consultation(
    data: dict,
    organization_id: int,
    assigned_user_id: Optional[int] = None,
    created_by_user_id: Optional[int] = None,
) -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    required_fields = {
        "child_name": "学生姓名",
        "consultation_subject": "咨询科目",
        "grade": "咨询年级",
        "need_detail": "家长诉求",
        "receiving_teacher": "接待教师",
    }
    for api_field, label in required_fields.items():
        csv_field = CONSULTATION_API_FIELD_MAP[api_field]
        value = data.get(api_field, data.get(csv_field, "")) if isinstance(data, dict) else ""
        if not str(value or "").strip():
            raise ValueError(f"{label}不能为空")
    new_row = {field: "" for field in CONSULTATION_FIELDNAMES}
    new_row["录入时间"] = now
    new_row["最后更新"] = now
    for field, value in _extract_consultation_updates(data).items():
        new_row[field] = value
    new_row.update(_extract_consultation_stage_updates(data))
    new_row["_require_success_class"] = data.get("flow_stage") == "成功进班"
    if not new_row["日期"]:
        new_row["日期"] = str(date.today())
    stored = _consultation_row_to_storage(new_row, organization_id)
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO consultations (
                organization_id, assigned_user_id, created_by_user_id, date, parent_wechat_name, child_name, grade,
                consultation_subject, need_detail,
                source_channel, source_channel_note, screenshot, reminder_at,
                reminder_status, reminder_task_id, follow_up_status, follow_up_note,
                created_at, updated_at, flow_stage, completed_stages_json, stage_teacher_ids_json,
                assigned_stage, assignment_note, test_taken,
                customer_service_added, customer_service_teacher, customer_service_note,
                communication_teacher_added, communication_teacher_note, test_teacher,
                test_note, test_images_json, trial_teacher_added,
                trial_teacher_note, trial_taken, trial_time_slot, trial_class_id,
                trial_class_manual, trial_teacher, trial_feedback, success_class_id,
                teaching_teacher_added, teaching_teacher, teaching_teacher_note,
                success_class_manual, enrollment_handoff_note, student_profile_status,
                student_profile_note, failure_reason, failure_note, closing_result,
                closed_by_user_id, end_note, ended_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                organization_id,
                assigned_user_id,
                created_by_user_id,
                stored["date"] or str(date.today()),
                stored["parent_wechat_name"],
                stored["child_name"],
                stored["grade"],
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
                stored["flow_stage"],
                stored["completed_stages_json"],
                stored["stage_teacher_ids_json"],
                stored["assigned_stage"],
                stored["assignment_note"],
                stored["test_taken"],
                stored["customer_service_added"],
                stored["customer_service_teacher"],
                stored["customer_service_note"],
                stored["communication_teacher_added"],
                stored["communication_teacher_note"],
                stored["test_teacher"],
                stored["test_note"],
                stored["test_images_json"],
                stored["trial_teacher_added"],
                stored["trial_teacher_note"],
                stored["trial_taken"],
                stored["trial_time_slot"],
                stored["trial_class_id"],
                stored["trial_class_manual"],
                stored["trial_teacher"],
                stored["trial_feedback"],
                stored["success_class_id"],
                stored["teaching_teacher_added"],
                stored["teaching_teacher"],
                stored["teaching_teacher_note"],
                stored["success_class_manual"],
                stored["enrollment_handoff_note"],
                stored["student_profile_status"],
                stored["student_profile_note"],
                stored["failure_reason"],
                stored["failure_note"],
                stored["closing_result"],
                stored["closed_by_user_id"],
                stored["end_note"],
                stored["ended_at"],
            ),
        )
        row = conn.execute(
            """
            SELECT c.*, u.display_name, u.username
            FROM consultations c
            LEFT JOIN users u ON c.assigned_user_id = u.id
            WHERE c.id=?
            """,
            (cur.lastrowid,)
        ).fetchone()
    return _consultation_storage_row_to_public_dict(row, _get_consultation_teacher_directory())


def update_consultation(
    consultation_id: int,
    data: dict,
    organization_id: Optional[int] = None,
    assigned_user_id: Optional[int] = None,
    responsibility_change_kind: str = "reassign",
):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    teacher_directory = _get_consultation_teacher_directory()
    with get_conn() as conn:
        query_sql = """
            SELECT c.*, u.display_name, u.username
            FROM consultations c
            LEFT JOIN users u ON c.assigned_user_id = u.id
            WHERE c.id=?
        """
        params: list[object] = [consultation_id]
        if organization_id is not None:
            query_sql += " AND c.organization_id=?"
            params.append(organization_id)
        if assigned_user_id is not None:
            query_sql += " AND c.assigned_user_id=?"
            params.append(assigned_user_id)
        current = conn.execute(query_sql, params).fetchone()
        if not current:
            return None

        public_row = _consultation_storage_row_to_public_dict(current, teacher_directory)
        frozen_stage_fields = {}
        restore_from_end = bool(isinstance(data, dict) and data.get("restore_from_end"))
        if public_row.get("flow_stage") == "咨询结束" and not restore_from_end:
            frozen_stage_fields = {
                field: public_row.get(field)
                for field in CONSULTATION_STAGE_API_FIELDS
                if field != "end_note"
            }
        for field, value in _extract_consultation_updates(data).items():
            public_row[field] = value
        public_row.update(_extract_consultation_stage_updates(data))
        if frozen_stage_fields:
            public_row.update(frozen_stage_fields)
        public_row["_require_success_class"] = data.get("flow_stage") == "成功进班"
        if "flow_stage" not in data and ("follow_up_status" in data or "跟进状态" in data):
            legacy_status = data.get("follow_up_status") or data.get("跟进状态") or public_row.get("follow_up_status", "")
            public_row["flow_stage"] = _normalize_consultation_flow_stage("", legacy_status)
            public_row["completed_stages"] = [public_row["flow_stage"]]
        public_row = _append_responsibility_history_for_stage_teacher_changes(
            _consultation_storage_row_to_public_dict(current, teacher_directory),
            public_row,
            teacher_directory,
            responsibility_change_kind,
        )
        stored = _consultation_row_to_storage(public_row, current["organization_id"])
        
        # Get assigned_user_id from data if provided, otherwise keep existing
        if isinstance(data, dict) and "assigned_user_id" in data:
            assigned_user_id = data["assigned_user_id"]
        else:
            assigned_user_id = current["assigned_user_id"]
        
        conn.execute(
            """
            UPDATE consultations
            SET date=?,
                parent_wechat_name=?,
                child_name=?,
                grade=?,
                consultation_subject=?,
                need_detail=?,
                source_channel=?,
                source_channel_note=?,
                screenshot=?,
                follow_up_status=?,
                follow_up_note=?,
                assigned_user_id=?,
                flow_stage=?,
                completed_stages_json=?,
                stage_teacher_ids_json=?,
                responsibility_history_json=?,
                assigned_stage=?,
                assignment_note=?,
                test_taken=?,
                customer_service_added=?,
                customer_service_teacher=?,
                customer_service_note=?,
                communication_teacher_added=?,
                communication_teacher_note=?,
                test_teacher=?,
                test_note=?,
                test_images_json=?,
                trial_teacher_added=?,
                trial_teacher_note=?,
                trial_taken=?,
                trial_time_slot=?,
                trial_class_id=?,
                trial_class_manual=?,
                trial_teacher=?,
                trial_feedback=?,
                success_class_id=?,
                teaching_teacher_added=?,
                teaching_teacher=?,
                teaching_teacher_note=?,
                success_class_manual=?,
                enrollment_handoff_note=?,
                student_profile_status=?,
                student_profile_note=?,
                failure_reason=?,
                failure_note=?,
                closing_result=?,
                closed_by_user_id=?,
                end_note=?,
                ended_at=?,
                updated_at=?
            WHERE id=?
            """,
            (
                stored["date"],
                stored["parent_wechat_name"],
                stored["child_name"],
                stored["grade"],
                stored["consultation_subject"],
                stored["need_detail"],
                stored["source_channel"],
                stored["source_channel_note"],
                stored["screenshot"],
                stored["follow_up_status"],
                stored["follow_up_note"],
                assigned_user_id,
                stored["flow_stage"],
                stored["completed_stages_json"],
                stored["stage_teacher_ids_json"],
                stored["responsibility_history_json"],
                stored["assigned_stage"],
                stored["assignment_note"],
                stored["test_taken"],
                stored["customer_service_added"],
                stored["customer_service_teacher"],
                stored["customer_service_note"],
                stored["communication_teacher_added"],
                stored["communication_teacher_note"],
                stored["test_teacher"],
                stored["test_note"],
                stored["test_images_json"],
                stored["trial_teacher_added"],
                stored["trial_teacher_note"],
                stored["trial_taken"],
                stored["trial_time_slot"],
                stored["trial_class_id"],
                stored["trial_class_manual"],
                stored["trial_teacher"],
                stored["trial_feedback"],
                stored["success_class_id"],
                stored["teaching_teacher_added"],
                stored["teaching_teacher"],
                stored["teaching_teacher_note"],
                stored["success_class_manual"],
                stored["enrollment_handoff_note"],
                stored["student_profile_status"],
                stored["student_profile_note"],
                stored["failure_reason"],
                stored["failure_note"],
                stored["closing_result"],
                stored["closed_by_user_id"],
                stored["end_note"],
                stored["ended_at"],
                now,
                consultation_id,
            ),
        )
        updated = conn.execute(
            """
            SELECT c.*, u.display_name, u.username
            FROM consultations c
            LEFT JOIN users u ON c.assigned_user_id = u.id
            WHERE c.id=?
            """,
            (consultation_id,)
        ).fetchone()
    return _consultation_storage_row_to_public_dict(updated, teacher_directory)


def enter_consultation_class(
    consultation_id: int,
    payload: dict,
    organization_id: Optional[int] = None,
    actor_user_id: Optional[int] = None,
    member_user_id: Optional[int] = None,
) -> Optional[dict]:
    item = get_consultation(consultation_id, organization_id)
    if not item:
        return None
    update_assigned_user_id = member_user_id
    if member_user_id is not None and item.get("assigned_user_id") != member_user_id:
        member_user = get_user_by_id(member_user_id)
        if not member_user or _consultation_assignment_context_for_actor(item, member_user) is None:
            return None
        update_assigned_user_id = None

    mode = str((payload or {}).get("mode") or "existing").strip() or "existing"
    completed_stages = list(dict.fromkeys([*item.get("completed_stages", []), "成功进班", "咨询结束"]))
    teaching_teacher_id = str((payload or {}).get("teaching_teacher_id") or "").strip()
    teaching_teacher_name = str((payload or {}).get("teaching_teacher") or item.get("teaching_teacher") or "").strip()
    teaching_teacher_user_id = _normalize_optional_int((payload or {}).get("teaching_teacher_user_id"))
    if teaching_teacher_id and teaching_teacher_user_id is None:
        teaching_teacher_user_id = resolve_teacher_username_to_user_id(teaching_teacher_id)
    next_stage_teacher_ids = dict(item.get("stage_teacher_ids") or {})
    if teaching_teacher_id:
        next_stage_teacher_ids["成功进班"] = teaching_teacher_id
    elif teaching_teacher_user_id is not None:
        next_stage_teacher_ids["成功进班"] = str(teaching_teacher_user_id)
    update_payload: dict[str, object] = {
        "flow_stage": "咨询结束",
        "completed_stages": completed_stages,
        "closing_result": "success",
        "closed_by_user_id": actor_user_id,
        "stage_teacher_ids": next_stage_teacher_ids,
    }
    if teaching_teacher_name:
        update_payload.update({
            "teaching_teacher_added": "已添加",
            "teaching_teacher": teaching_teacher_name,
        })
    class_id: Optional[int] = None
    student = None

    if mode == "existing":
        class_id = _normalize_optional_int((payload or {}).get("class_id"))
        if class_id is None:
            raise ValueError("请选择转化班级")
        class_row = get_class(class_id)
        if not class_row or (organization_id is not None and class_row.get("organization_id") != organization_id):
            raise ValueError("转化班级不存在")
        student = create_student_for_class(class_id, str(item.get("child_name") or ""))
        backfill_subject = str((payload or {}).get("consultation_subject") or class_row.get("subject") or "").strip()
        backfill_grade = str((payload or {}).get("grade") or class_row.get("current_grade") or class_row.get("grade") or "").strip()
        update_payload.update({
            "success_class_id": class_id,
            "success_class_manual": "",
            "student_profile_status": "created",
        })
        if backfill_subject and not str(item.get("consultation_subject") or "").strip():
            update_payload["consultation_subject"] = backfill_subject
        if backfill_grade and not str(item.get("grade") or "").strip():
            update_payload["grade"] = backfill_grade
    elif mode == "quick_new_class":
        class_name = str((payload or {}).get("class_name") or "").strip()
        if not class_name:
            raise ValueError("班级名称不能为空")
        backfill_subject = str((payload or {}).get("subject") or item.get("consultation_subject") or "").strip()
        backfill_grade = str((payload or {}).get("grade") or (payload or {}).get("current_grade") or item.get("grade") or "").strip()
        class_id = save_class(
            class_name,
            subject=backfill_subject,
            grade=backfill_grade,
            class_type=str((payload or {}).get("class_type") or "group"),
            stage=str((payload or {}).get("stage") or ""),
            current_grade=str((payload or {}).get("current_grade") or backfill_grade),
            class_number=str((payload or {}).get("class_number") or ""),
            cohort_year=_normalize_optional_int((payload or {}).get("cohort_year")),
            show_cohort_year=bool((payload or {}).get("show_cohort_year")),
            is_bridge=bool((payload or {}).get("is_bridge")),
            bridge_target=str((payload or {}).get("bridge_target") or ""),
            content_track=str((payload or {}).get("content_track") or ""),
            teacher_name=teaching_teacher_name,
            teacher_user_id=teaching_teacher_user_id,
            organization_id=organization_id,
        )
        student = create_student_for_class(class_id, str(item.get("child_name") or ""))
        update_payload.update({
            "success_class_id": class_id,
            "success_class_manual": "",
            "student_profile_status": "created",
        })
        if backfill_subject and not str(item.get("consultation_subject") or "").strip():
            update_payload["consultation_subject"] = backfill_subject
        if backfill_grade and not str(item.get("grade") or "").strip():
            update_payload["grade"] = backfill_grade
    elif mode == "converted_without_class":
        update_payload.update({
            "success_class_id": None,
            "success_class_manual": "班级待补充",
            "student_profile_status": "needs_completion",
        })
    else:
        raise ValueError("mode must be existing, quick_new_class or converted_without_class")

    updated = update_consultation(
        consultation_id,
        update_payload,
        organization_id=organization_id,
        assigned_user_id=update_assigned_user_id,
    )
    if not updated:
        return None
    return {
        "item": updated,
        "class_id": class_id,
        "student": student,
    }


def delete_consultation(consultation_id: int, organization_id: Optional[int] = None) -> bool:
    with get_conn() as conn:
        query_sql = "DELETE FROM consultations WHERE id=?"
        params: list[object] = [consultation_id]
        if organization_id is not None:
            query_sql += " AND organization_id=?"
            params.append(organization_id)
        cur = conn.execute(query_sql, params)
    return cur.rowcount > 0


def append_consultation_test_image(
    consultation_id: int,
    image: dict,
    organization_id: Optional[int] = None,
    assigned_user_id: Optional[int] = None,
) -> Optional[dict]:
    with get_conn() as conn:
        query_sql = "SELECT * FROM consultations WHERE id=?"
        params: list[object] = [consultation_id]
        if organization_id is not None:
            query_sql += " AND organization_id=?"
            params.append(organization_id)
        if assigned_user_id is not None:
            query_sql += " AND assigned_user_id=?"
            params.append(assigned_user_id)
        row = conn.execute(query_sql, params).fetchone()
        if not row:
            return None
        images = _json_list(row["test_images_json"])
        images.append(image)
        conn.execute(
            "UPDATE consultations SET test_images_json=?, updated_at=datetime('now','localtime') WHERE id=?",
            (json.dumps(images, ensure_ascii=False), consultation_id),
        )
    return get_consultation(consultation_id, organization_id)


def append_consultation_test_image_for_actor(actor_user: dict, consultation_id: int, image: dict) -> Optional[dict]:
    current = get_consultation_for_actor(actor_user, consultation_id)
    if not current:
        return None
    images = [*(_json_list(current.get("test_images"))), image]
    return update_consultation_for_actor(actor_user, consultation_id, {"test_images": images})


def remove_consultation_test_image(
    consultation_id: int,
    image_index: int,
    organization_id: Optional[int] = None,
    assigned_user_id: Optional[int] = None,
) -> Optional[dict]:
    with get_conn() as conn:
        query_sql = "SELECT * FROM consultations WHERE id=?"
        params: list[object] = [consultation_id]
        if organization_id is not None:
            query_sql += " AND organization_id=?"
            params.append(organization_id)
        if assigned_user_id is not None:
            query_sql += " AND assigned_user_id=?"
            params.append(assigned_user_id)
        row = conn.execute(query_sql, params).fetchone()
        if not row:
            return None
        images = _json_list(row["test_images_json"])
        if image_index < 0 or image_index >= len(images):
            return None
        images.pop(image_index)
        conn.execute(
            "UPDATE consultations SET test_images_json=?, updated_at=datetime('now','localtime') WHERE id=?",
            (json.dumps(images, ensure_ascii=False), consultation_id),
        )
    return get_consultation(consultation_id, organization_id)


def remove_consultation_test_image_for_actor(actor_user: dict, consultation_id: int, image_index: int) -> Optional[dict]:
    current = get_consultation_for_actor(actor_user, consultation_id)
    if not current:
        return None
    images = _json_list(current.get("test_images"))
    if image_index < 0 or image_index >= len(images):
        return None
    next_images = [image for index, image in enumerate(images) if index != image_index]
    return update_consultation_for_actor(actor_user, consultation_id, {"test_images": next_images})


# ─── 数据库 ────────────────────────────────────────────────────────────────────
class _ManagedConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, factory=_ManagedConnection)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column in columns:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _ensure_class_commentary_skill_activation_reason_schema(
    conn: sqlite3.Connection,
) -> None:
    row = conn.execute(
        """
        SELECT sql FROM sqlite_master
        WHERE type='table' AND name='class_commentary_skill_activation_events'
        """
    ).fetchone()
    if not row or "'manifest_refresh'" in str(row["sql"] or ""):
        return
    conn.executescript(
        """
        BEGIN IMMEDIATE;
        DROP TRIGGER IF EXISTS trg_class_commentary_skill_activation_event_immutable;
        ALTER TABLE class_commentary_skill_activation_events
        RENAME TO class_commentary_skill_activation_events__legacy_reason;

        CREATE TABLE class_commentary_skill_activation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            skill_registry_id INTEGER NOT NULL REFERENCES class_commentary_skills(id) ON DELETE CASCADE,
            activation_request_id TEXT NOT NULL,
            activation_payload_hash TEXT NOT NULL,
            from_version_id INTEGER REFERENCES class_commentary_skill_versions(id),
            to_version_id INTEGER NOT NULL REFERENCES class_commentary_skill_versions(id),
            actor_user_id INTEGER NOT NULL REFERENCES users(id),
            reason TEXT NOT NULL,
            evaluation_snapshot_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(skill_registry_id, activation_request_id),
            CHECK(reason IN ('initial_import','candidate_approved','rollback','manifest_refresh'))
        );

        INSERT INTO class_commentary_skill_activation_events (
            id, organization_id, skill_registry_id, activation_request_id,
            activation_payload_hash, from_version_id, to_version_id,
            actor_user_id, reason, evaluation_snapshot_json, created_at
        )
        SELECT id, organization_id, skill_registry_id, activation_request_id,
               activation_payload_hash, from_version_id, to_version_id,
               actor_user_id, reason, evaluation_snapshot_json, created_at
        FROM class_commentary_skill_activation_events__legacy_reason;

        DROP TABLE class_commentary_skill_activation_events__legacy_reason;

        CREATE TRIGGER trg_class_commentary_skill_activation_event_immutable
        BEFORE UPDATE ON class_commentary_skill_activation_events
        BEGIN
            SELECT RAISE(ABORT, 'skill activation event is immutable');
        END;
        COMMIT;
        """
    )


def _ensure_class_commentary_structured_feedback_schema(conn: sqlite3.Connection) -> None:
    columns = {
        "class_commentary_generations": {
            "feedback_schema_version": "TEXT NOT NULL DEFAULT ''",
            "structured_feedback_json": "TEXT NOT NULL DEFAULT ''",
            "structured_feedback_hash": "TEXT NOT NULL DEFAULT ''",
            "eligible_student_ids_json": "TEXT NOT NULL DEFAULT '[]'",
            "eligible_student_scope_hash": "TEXT NOT NULL DEFAULT ''",
            "student_mention_matcher_version": "TEXT NOT NULL DEFAULT ''",
            "response_format_json": "TEXT NOT NULL DEFAULT '{}'",
            "student_history_memory_mode": "TEXT NOT NULL DEFAULT ''",
        },
        "class_commentary_feedback_drafts": {
            "feedback_schema_version": "TEXT NOT NULL DEFAULT ''",
            "structured_feedback_json": "TEXT NOT NULL DEFAULT ''",
        },
        "class_commentary_revisions": {
            "feedback_schema_version": "TEXT NOT NULL DEFAULT ''",
            "structured_feedback_json": "TEXT NOT NULL DEFAULT ''",
            "structured_feedback_hash": "TEXT NOT NULL DEFAULT ''",
        },
        "class_commentary_student_generation_runs": {
            "student_run_schema_version": (
                "TEXT NOT NULL DEFAULT 'class_commentary.student_generation_run.v1'"
            ),
            "eligible_student_ids_json": "TEXT NOT NULL DEFAULT '[]'",
            "eligible_student_scope_hash": "TEXT NOT NULL DEFAULT 'legacy_unavailable'",
            "student_mention_matcher_version": "TEXT NOT NULL DEFAULT 'legacy_unavailable'",
            "class_context_snapshot_json": "TEXT NOT NULL DEFAULT '{}'",
            "class_context_hash": (
                "TEXT NOT NULL DEFAULT '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'"
            ),
            "graph_context_snapshot_json": "TEXT NOT NULL DEFAULT '{}'",
            "graph_context_hash": (
                "TEXT NOT NULL DEFAULT '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'"
            ),
            "graph_allowed_evidence_refs_json": "TEXT NOT NULL DEFAULT '[]'",
            "graph_retrieval_status": "TEXT NOT NULL DEFAULT 'pending'",
            "used_graph_evidence_refs_json": "TEXT NOT NULL DEFAULT '[]'",
            "charge_usage_id": "INTEGER REFERENCES ai_usage_ledger(id) ON DELETE SET NULL",
        },
        "ai_usage_ledger": {
            "request_payload_hash": "TEXT NOT NULL DEFAULT ''",
        },
    }
    for table, table_columns in columns.items():
        for column, ddl in table_columns.items():
            _ensure_column(conn, table, column, ddl)


def canonicalize_class_subject_key(subject: object) -> Optional[str]:
    normalized = str(subject or "").strip().casefold()
    return CLASS_SUBJECT_KEY_ALIASES.get(normalized)


def _ensure_class_commentary_evolution_schema(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "classes", "subject_key", "TEXT")
    class_rows = conn.execute(
        "SELECT id, subject FROM classes WHERE subject_key IS NULL OR subject_key=''"
    ).fetchall()
    for class_row in class_rows:
        subject_key = canonicalize_class_subject_key(class_row["subject"])
        if subject_key:
            conn.execute(
                "UPDATE classes SET subject_key=? WHERE id=?",
                (subject_key, class_row["id"]),
            )
    _ensure_column(
        conn,
        "class_commentary_tasks",
        "confirmed_transcript_version",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(conn, "class_commentary_tasks", "final_feedback_text", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "class_commentary_tasks", "generation_seq", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "class_commentary_tasks", "feedback_confirmed_at", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "class_commentary_tasks", "feedback_revision_no", "INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        """
        UPDATE class_commentary_tasks
        SET confirmed_transcript_version=1
        WHERE confirmed_transcript_version=0
          AND confirmed_transcript_text<>''
        """
    )

    skill_columns = {
        str(row["name"])
        for row in conn.execute("PRAGMA table_info(class_commentary_skills)").fetchall()
    }
    if "owner_teacher_user_id" in skill_columns and "imported_by_user_id" not in skill_columns:
        conn.execute("DROP INDEX IF EXISTS idx_class_commentary_skills_owner")
        conn.execute(
            "ALTER TABLE class_commentary_skills "
            "RENAME COLUMN owner_teacher_user_id TO imported_by_user_id"
        )

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS class_commentary_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            skill_id TEXT NOT NULL,
            imported_by_user_id INTEGER NOT NULL REFERENCES users(id),
            source_type TEXT NOT NULL,
            source_path TEXT,
            source_content_hash TEXT NOT NULL,
            active_version_id INTEGER REFERENCES class_commentary_skill_versions(id),
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(organization_id, skill_id),
            CHECK(source_type IN ('external_skill_package','database')),
            CHECK(status IN ('active','disabled'))
        );

        CREATE TABLE IF NOT EXISTS class_commentary_skill_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            skill_registry_id INTEGER NOT NULL REFERENCES class_commentary_skills(id) ON DELETE CASCADE,
            version_no INTEGER NOT NULL,
            version_kind TEXT NOT NULL,
            candidate_build_id INTEGER REFERENCES class_commentary_skill_candidate_builds(id),
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            base_version_id INTEGER REFERENCES class_commentary_skill_versions(id),
            source_snapshot_hash TEXT,
            evaluation_snapshot_json TEXT NOT NULL DEFAULT '{}',
            evaluation_hash TEXT NOT NULL DEFAULT '',
            review_status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            reviewed_at TEXT,
            UNIQUE(skill_registry_id, version_no),
            UNIQUE(candidate_build_id),
            CHECK(version_kind IN ('imported','candidate')),
            CHECK(review_status IN ('not_required','pending','approved','rejected'))
        );

        CREATE TABLE IF NOT EXISTS class_commentary_skill_candidate_builds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            skill_registry_id INTEGER NOT NULL REFERENCES class_commentary_skills(id) ON DELETE CASCADE,
            requested_by_user_id INTEGER REFERENCES users(id),
            candidate_request_id TEXT NOT NULL,
            candidate_payload_hash TEXT NOT NULL,
            expected_active_version_id INTEGER NOT NULL REFERENCES class_commentary_skill_versions(id),
            base_version_id INTEGER NOT NULL REFERENCES class_commentary_skill_versions(id),
            source_cutoff_at TEXT NOT NULL,
            selection_policy_version TEXT NOT NULL,
            min_effective_tasks INTEGER NOT NULL,
            min_support_tasks INTEGER NOT NULL,
            source_snapshot_hash TEXT NOT NULL,
            effective_task_count INTEGER NOT NULL,
            supporting_task_count INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            claim_token TEXT,
            claim_owner TEXT,
            next_attempt_at TEXT,
            candidate_version_id INTEGER REFERENCES class_commentary_skill_versions(id),
            last_error TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            started_at TEXT,
            completed_at TEXT,
            UNIQUE(skill_registry_id, candidate_request_id),
            CHECK(candidate_request_id<>''),
            CHECK(candidate_payload_hash<>''),
            CHECK(selection_policy_version<>''),
            CHECK(source_snapshot_hash<>''),
            CHECK(min_effective_tasks >= 1),
            CHECK(min_support_tasks >= 1),
            CHECK(effective_task_count >= 0),
            CHECK(supporting_task_count >= 0),
            CHECK(attempt_count >= 0 AND attempt_count <= 3),
            CHECK(status IN ('queued','running','retry_wait','succeeded','failed','obsolete'))
        );

        CREATE TABLE IF NOT EXISTS class_commentary_skill_candidate_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            candidate_build_id INTEGER NOT NULL REFERENCES class_commentary_skill_candidate_builds(id) ON DELETE CASCADE,
            task_id INTEGER NOT NULL REFERENCES class_commentary_tasks(id) ON DELETE CASCADE,
            revision_id INTEGER NOT NULL REFERENCES class_commentary_revisions(id),
            sample_role TEXT NOT NULL,
            revision_snapshot_hash TEXT NOT NULL,
            selection_policy_version TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(candidate_build_id, task_id),
            CHECK(sample_role IN ('support','evaluation','support_and_evaluation')),
            CHECK(revision_snapshot_hash<>''),
            CHECK(selection_policy_version<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_skill_candidate_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            candidate_build_id INTEGER NOT NULL REFERENCES class_commentary_skill_candidate_builds(id) ON DELETE CASCADE,
            candidate_revision_id INTEGER NOT NULL REFERENCES class_commentary_skill_candidate_revisions(id) ON DELETE CASCADE,
            memory_evidence_id INTEGER NOT NULL REFERENCES class_commentary_memory_evidence(id),
            memory_record_id INTEGER NOT NULL REFERENCES class_commentary_memory_records(id),
            evidence_hash TEXT NOT NULL,
            record_version_at_selection INTEGER NOT NULL,
            evidence_status_at_selection TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(candidate_build_id, memory_evidence_id),
            UNIQUE(candidate_build_id, candidate_revision_id, memory_record_id),
            CHECK(evidence_hash<>''),
            CHECK(record_version_at_selection >= 1),
            CHECK(evidence_status_at_selection='active')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_skill_activation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            skill_registry_id INTEGER NOT NULL REFERENCES class_commentary_skills(id) ON DELETE CASCADE,
            activation_request_id TEXT NOT NULL,
            activation_payload_hash TEXT NOT NULL,
            from_version_id INTEGER REFERENCES class_commentary_skill_versions(id),
            to_version_id INTEGER NOT NULL REFERENCES class_commentary_skill_versions(id),
            actor_user_id INTEGER NOT NULL REFERENCES users(id),
            reason TEXT NOT NULL,
            evaluation_snapshot_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(skill_registry_id, activation_request_id),
            CHECK(reason IN ('initial_import','candidate_approved','rollback','manifest_refresh'))
        );

        CREATE TABLE IF NOT EXISTS class_commentary_generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            task_id INTEGER NOT NULL REFERENCES class_commentary_tasks(id) ON DELETE CASCADE,
            generation_no INTEGER NOT NULL,
            generation_request_id TEXT,
            generation_request_payload_hash TEXT,
            teacher_user_id INTEGER NOT NULL REFERENCES users(id),
            class_id INTEGER NOT NULL REFERENCES classes(id),
            subject_key TEXT,
            confirmed_transcript_version INTEGER NOT NULL DEFAULT 0,
            confirmed_transcript_snapshot TEXT NOT NULL DEFAULT '',
            confirmed_transcript_hash TEXT NOT NULL DEFAULT '',
            attending_roster_snapshot_json TEXT NOT NULL DEFAULT '[]',
            attending_roster_hash TEXT NOT NULL DEFAULT '',
            attending_roster_explicit INTEGER NOT NULL DEFAULT 0,
            skill_registry_id INTEGER REFERENCES class_commentary_skills(id),
            skill_id TEXT,
            skill_version_id INTEGER REFERENCES class_commentary_skill_versions(id),
            skill_content_snapshot TEXT NOT NULL DEFAULT '',
            skill_content_hash TEXT NOT NULL DEFAULT '',
            model_provider TEXT,
            model_name TEXT,
            model_parameters_json TEXT,
            prompt_version TEXT,
            prompt_payload_snapshot_json TEXT,
            prompt_payload_hash TEXT,
            memory_context_snapshot_json TEXT,
            memory_context_hash TEXT,
            execution_snapshot_status TEXT NOT NULL DEFAULT 'ready',
            execution_snapshot_finalized_at TEXT,
            feedback_schema_version TEXT NOT NULL DEFAULT '',
            structured_feedback_json TEXT NOT NULL DEFAULT '',
            structured_feedback_hash TEXT NOT NULL DEFAULT '',
            eligible_student_ids_json TEXT NOT NULL DEFAULT '[]',
            eligible_student_scope_hash TEXT NOT NULL DEFAULT '',
            student_mention_matcher_version TEXT NOT NULL DEFAULT '',
            response_format_json TEXT NOT NULL DEFAULT '{}',
            student_history_memory_mode TEXT NOT NULL DEFAULT '',
            generated_feedback_text TEXT NOT NULL DEFAULT '',
            origin TEXT NOT NULL,
            snapshot_completeness TEXT NOT NULL,
            missing_snapshot_fields_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL,
            error_code TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            completed_at TEXT,
            UNIQUE(task_id, generation_no),
            UNIQUE(task_id, generation_request_id),
            CHECK(origin IN ('runtime','legacy_migration')),
            CHECK(snapshot_completeness IN ('complete','partial')),
            CHECK(attending_roster_explicit IN (0,1)),
            CHECK(execution_snapshot_status IN ('pending','ready')),
            CHECK(status IN ('generating','succeeded','failed')),
            CHECK(
                (
                    origin='legacy_migration'
                    AND snapshot_completeness='partial'
                    AND missing_snapshot_fields_json<>'[]'
                )
                OR
                (
                    origin='runtime'
                    AND snapshot_completeness='complete'
                    AND generation_request_id IS NOT NULL
                    AND generation_request_id<>''
                    AND generation_request_payload_hash IS NOT NULL
                    AND generation_request_payload_hash<>''
                    AND confirmed_transcript_snapshot<>''
                    AND confirmed_transcript_hash<>''
                    AND attending_roster_hash<>''
                    AND skill_registry_id IS NOT NULL
                    AND skill_id IS NOT NULL
                    AND skill_id<>''
                    AND skill_version_id IS NOT NULL
                    AND skill_content_hash<>''
                    AND model_provider IS NOT NULL
                    AND model_provider<>''
                    AND model_name IS NOT NULL
                    AND model_name<>''
                    AND model_parameters_json IS NOT NULL
                    AND prompt_version IS NOT NULL
                    AND prompt_version<>''
                    AND prompt_payload_snapshot_json IS NOT NULL
                    AND prompt_payload_hash IS NOT NULL
                    AND prompt_payload_hash<>''
                    AND memory_context_snapshot_json IS NOT NULL
                    AND memory_context_hash IS NOT NULL
                    AND memory_context_hash<>''
                    AND missing_snapshot_fields_json='[]'
                )
            )
        );

        CREATE TABLE IF NOT EXISTS class_commentary_student_generation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            generation_id INTEGER NOT NULL REFERENCES class_commentary_generations(id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL,
            student_name_snapshot TEXT NOT NULL,
            request_id TEXT NOT NULL,
            request_payload_hash TEXT NOT NULL,
            student_run_schema_version TEXT NOT NULL DEFAULT 'class_commentary.student_generation_run.v1',
            prompt_version TEXT NOT NULL,
            memory_mode TEXT NOT NULL,
            eligible_student_ids_json TEXT NOT NULL DEFAULT '[]',
            eligible_student_scope_hash TEXT NOT NULL DEFAULT 'legacy_unavailable',
            student_mention_matcher_version TEXT NOT NULL DEFAULT 'legacy_unavailable',
            class_context_snapshot_json TEXT NOT NULL DEFAULT '{}',
            class_context_hash TEXT NOT NULL DEFAULT '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a',
            current_evidence_snapshot_json TEXT NOT NULL DEFAULT '{}',
            current_evidence_hash TEXT NOT NULL,
            memory_context_snapshot_json TEXT NOT NULL DEFAULT '{}',
            memory_context_hash TEXT NOT NULL,
            memory_retrieval_status TEXT NOT NULL DEFAULT 'pending',
            graph_context_snapshot_json TEXT NOT NULL DEFAULT '{}',
            graph_context_hash TEXT NOT NULL DEFAULT '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a',
            graph_allowed_evidence_refs_json TEXT NOT NULL DEFAULT '[]',
            graph_retrieval_status TEXT NOT NULL DEFAULT 'pending',
            used_graph_evidence_refs_json TEXT NOT NULL DEFAULT '[]',
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            model_parameters_json TEXT NOT NULL,
            prompt_payload_snapshot_json TEXT NOT NULL DEFAULT '{}',
            prompt_payload_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            claim_token TEXT,
            claim_owner TEXT,
            next_attempt_at TEXT,
            charge_request_key TEXT NOT NULL,
            charge_status TEXT NOT NULL DEFAULT 'pending',
            charge_usage_id INTEGER REFERENCES ai_usage_ledger(id) ON DELETE SET NULL,
            response_snapshot_json TEXT NOT NULL DEFAULT '{}',
            response_hash TEXT NOT NULL DEFAULT '',
            structured_feedback_json TEXT NOT NULL DEFAULT '',
            structured_feedback_hash TEXT NOT NULL DEFAULT '',
            error_code TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            started_at TEXT,
            completed_at TEXT,
            UNIQUE(generation_id, student_id),
            UNIQUE(organization_id, request_id),
            UNIQUE(organization_id, charge_request_key),
            CHECK(memory_mode IN ('isolated_v2')),
            CHECK(memory_retrieval_status IN ('pending','empty','ready','degraded','failed')),
            CHECK(graph_retrieval_status IN ('pending','disabled','empty','ready','degraded','failed')),
            CHECK(status IN ('queued','generating','retry_wait','response_received','succeeded','failed')),
            CHECK(charge_status IN ('pending','charged')),
            CHECK(attempt_count >= 0),
            CHECK(request_id<>''),
            CHECK(request_payload_hash<>''),
            CHECK(student_run_schema_version='class_commentary.student_generation_run.v1'),
            CHECK(eligible_student_scope_hash<>''),
            CHECK(student_mention_matcher_version<>''),
            CHECK(class_context_hash<>''),
            CHECK(current_evidence_hash<>''),
            CHECK(memory_context_hash<>''),
            CHECK(prompt_payload_hash<>''),
            CHECK(charge_request_key<>'')
        );

        CREATE INDEX IF NOT EXISTS idx_class_commentary_student_runs_generation_status
        ON class_commentary_student_generation_runs (generation_id, status, student_id);

        CREATE INDEX IF NOT EXISTS idx_class_commentary_student_runs_retry
        ON class_commentary_student_generation_runs (status, next_attempt_at, generation_id);

        CREATE TABLE IF NOT EXISTS class_commentary_student_generation_retry_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            generation_id INTEGER NOT NULL REFERENCES class_commentary_generations(id) ON DELETE CASCADE,
            actor_user_id INTEGER NOT NULL REFERENCES users(id),
            retry_request_id TEXT NOT NULL,
            retry_payload_hash TEXT NOT NULL,
            student_ids_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(organization_id, retry_request_id),
            CHECK(retry_request_id<>''),
            CHECK(retry_payload_hash<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_student_generation_credit_holds (
            student_run_id INTEGER PRIMARY KEY REFERENCES class_commentary_student_generation_runs(id) ON DELETE CASCADE,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            amount INTEGER NOT NULL,
            request_id TEXT NOT NULL,
            request_payload_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            usage_id INTEGER REFERENCES ai_usage_ledger(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            settled_at TEXT,
            released_at TEXT,
            UNIQUE(organization_id, request_id),
            CHECK(amount > 0),
            CHECK(request_id<>''),
            CHECK(request_payload_hash<>''),
            CHECK(status IN ('active','settled','released'))
        );

        CREATE INDEX IF NOT EXISTS idx_class_commentary_student_credit_holds_org_status
        ON class_commentary_student_generation_credit_holds (organization_id, status);

        CREATE TABLE IF NOT EXISTS class_commentary_feedback_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            task_id INTEGER NOT NULL REFERENCES class_commentary_tasks(id) ON DELETE CASCADE,
            generation_id INTEGER NOT NULL REFERENCES class_commentary_generations(id) ON DELETE CASCADE,
            teacher_user_id INTEGER NOT NULL REFERENCES users(id),
            based_on_revision_id INTEGER REFERENCES class_commentary_revisions(id) ON DELETE SET NULL,
            feedback_schema_version TEXT NOT NULL DEFAULT '',
            structured_feedback_json TEXT NOT NULL DEFAULT '',
            feedback_text TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            draft_version INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(task_id, generation_id, teacher_user_id),
            CHECK(draft_version >= 1)
        );

        CREATE TABLE IF NOT EXISTS class_commentary_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            task_id INTEGER NOT NULL REFERENCES class_commentary_tasks(id) ON DELETE CASCADE,
            generation_id INTEGER NOT NULL REFERENCES class_commentary_generations(id),
            teacher_user_id INTEGER NOT NULL REFERENCES users(id),
            revision_no INTEGER NOT NULL,
            confirmation_request_id TEXT NOT NULL,
            confirmation_payload_hash TEXT NOT NULL,
            previous_revision_id INTEGER REFERENCES class_commentary_revisions(id),
            confirmed_draft_version INTEGER NOT NULL DEFAULT 0,
            confirmed_draft_snapshot_json TEXT NOT NULL DEFAULT '{}',
            feedback_schema_version TEXT NOT NULL DEFAULT '',
            structured_feedback_json TEXT NOT NULL DEFAULT '',
            structured_feedback_hash TEXT NOT NULL DEFAULT '',
            final_feedback_text TEXT NOT NULL,
            generation_diff_json TEXT NOT NULL,
            previous_revision_diff_json TEXT,
            learning_evidence_schema_version TEXT NOT NULL,
            learning_evidence_selector_version TEXT NOT NULL,
            learning_evidence_snapshot_json TEXT NOT NULL,
            learning_evidence_source_refs_json TEXT NOT NULL,
            learning_evidence_hash TEXT NOT NULL,
            learning_evidence_captured_at TEXT NOT NULL,
            learning_evidence_completeness TEXT NOT NULL,
            learning_evidence_missing_sources_json TEXT NOT NULL,
            learn_requested INTEGER NOT NULL,
            accepted_without_edit INTEGER NOT NULL,
            unchanged_from_previous_revision INTEGER NOT NULL,
            confirmed_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(task_id, revision_no),
            UNIQUE(task_id, confirmation_request_id),
            CHECK(learning_evidence_completeness IN ('complete','partial','empty')),
            CHECK(learn_requested IN (0,1)),
            CHECK(accepted_without_edit IN (0,1)),
            CHECK(unchanged_from_previous_revision IN (0,1))
        );

        CREATE TABLE IF NOT EXISTS class_commentary_memory_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            created_from_revision_id INTEGER NOT NULL REFERENCES class_commentary_revisions(id),
            created_by_teacher_user_id INTEGER NOT NULL REFERENCES users(id),
            created_from_skill_registry_id INTEGER NOT NULL REFERENCES class_commentary_skills(id),
            scope_skill_registry_id INTEGER REFERENCES class_commentary_skills(id),
            student_id INTEGER REFERENCES students(id),
            subject_key TEXT,
            memory_type TEXT NOT NULL,
            memory_text TEXT NOT NULL,
            normalized_memory_text TEXT NOT NULL,
            normalization_version TEXT NOT NULL,
            memory_text_hash TEXT NOT NULL,
            scope_hash TEXT NOT NULL,
            canonical_key TEXT NOT NULL,
            creation_evidence_snapshot_json TEXT NOT NULL,
            confidence REAL NOT NULL,
            record_version INTEGER NOT NULL DEFAULT 1,
            mem0_memory_id TEXT,
            desired_status TEXT NOT NULL DEFAULT 'active',
            applied_status TEXT NOT NULL DEFAULT 'not_applied',
            superseded_by_id INTEGER REFERENCES class_commentary_memory_records(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            CHECK(memory_type IN ('teacher_style','student_fact')),
            CHECK(desired_status IN ('active','superseded','revoked','deleted')),
            CHECK(applied_status IN ('not_applied','active','superseded','revoked','deleted','unknown')),
            CHECK(confidence >= 0 AND confidence <= 1),
            CHECK(record_version >= 1),
            CHECK(memory_text<>''),
            CHECK(normalized_memory_text<>''),
            CHECK(
                (
                    memory_type='teacher_style'
                    AND scope_skill_registry_id IS NOT NULL
                    AND student_id IS NULL
                    AND subject_key IS NULL
                )
                OR
                (
                    memory_type='student_fact'
                    AND scope_skill_registry_id IS NULL
                    AND student_id IS NOT NULL
                    AND subject_key IS NOT NULL
                    AND subject_key<>''
                )
            )
        );

        CREATE TABLE IF NOT EXISTS class_commentary_memory_extraction_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            revision_id INTEGER NOT NULL REFERENCES class_commentary_revisions(id) ON DELETE CASCADE,
            request_key TEXT NOT NULL,
            extractor_version TEXT NOT NULL,
            memory_schema_version TEXT NOT NULL,
            extraction_input_hash TEXT NOT NULL,
            learning_evidence_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            started_at TEXT,
            claim_token TEXT,
            claim_owner TEXT,
            rq_job_id TEXT,
            enqueued_at TEXT,
            next_attempt_at TEXT,
            last_error TEXT,
            obsolete_reason TEXT,
            obsoleted_by_revision_id INTEGER REFERENCES class_commentary_revisions(id),
            obsoleted_at TEXT,
            result_summary_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            completed_at TEXT,
            UNIQUE(request_key),
            UNIQUE(revision_id, extractor_version, memory_schema_version),
            CHECK(status IN ('queued','running','retry_wait','extracted','failed','integrity_failed','obsolete')),
            CHECK(attempt_count >= 0 AND attempt_count <= 4),
            CHECK(request_key<>''),
            CHECK(extraction_input_hash<>''),
            CHECK(learning_evidence_hash<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_memory_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            memory_record_id INTEGER NOT NULL REFERENCES class_commentary_memory_records(id) ON DELETE CASCADE,
            revision_id INTEGER NOT NULL REFERENCES class_commentary_revisions(id) ON DELETE CASCADE,
            extraction_job_id INTEGER NOT NULL REFERENCES class_commentary_memory_extraction_jobs(id) ON DELETE CASCADE,
            source_teacher_user_id INTEGER NOT NULL REFERENCES users(id),
            source_skill_registry_id INTEGER NOT NULL REFERENCES class_commentary_skills(id),
            evidence_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(memory_record_id, revision_id, evidence_hash),
            CHECK(status IN ('active','revoked','superseded')),
            CHECK(evidence_hash<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_memory_evidence_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            evidence_id INTEGER NOT NULL REFERENCES class_commentary_memory_evidence(id) ON DELETE CASCADE,
            action TEXT NOT NULL,
            request_id TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            actor_user_id INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(evidence_id, request_id),
            CHECK(action IN ('revoke')),
            CHECK(request_id<>''),
            CHECK(payload_hash<>'')
        );

        CREATE TABLE IF NOT EXISTS class_commentary_memory_retry_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            scope_type TEXT NOT NULL,
            scope_id INTEGER NOT NULL,
            revision_id INTEGER REFERENCES class_commentary_revisions(id) ON DELETE CASCADE,
            request_id TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            actor_user_id INTEGER REFERENCES users(id),
            actor_service TEXT,
            extraction_job_id INTEGER REFERENCES class_commentary_memory_extraction_jobs(id) ON DELETE SET NULL,
            target_operation_ids_json TEXT NOT NULL DEFAULT '[]',
            previous_state_snapshot_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(organization_id, scope_type, scope_id, request_id),
            CHECK(scope_type IN ('revision','operation')),
            CHECK(request_id<>''),
            CHECK(payload_hash<>''),
            CHECK(
                (scope_type='revision' AND revision_id IS NOT NULL AND actor_user_id IS NOT NULL AND actor_service IS NULL)
                OR
                (scope_type='operation' AND actor_user_id IS NULL AND actor_service IS NOT NULL AND actor_service<>'')
            )
        );

        CREATE TABLE IF NOT EXISTS class_commentary_memory_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            extraction_job_id INTEGER REFERENCES class_commentary_memory_extraction_jobs(id) ON DELETE SET NULL,
            memory_record_id INTEGER NOT NULL REFERENCES class_commentary_memory_records(id) ON DELETE CASCADE,
            source_type TEXT NOT NULL,
            source_id INTEGER,
            cleanup_scope_type TEXT,
            cleanup_scope_id INTEGER,
            operation_type TEXT NOT NULL,
            operation_key TEXT NOT NULL,
            operation_version INTEGER NOT NULL,
            expected_record_version INTEGER NOT NULL,
            target_state_json TEXT NOT NULL,
            target_state_hash TEXT NOT NULL,
            mem0_memory_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            started_at TEXT,
            lease_token TEXT,
            lease_owner TEXT,
            lease_until TEXT,
            rq_job_id TEXT,
            enqueued_at TEXT,
            next_attempt_at TEXT,
            last_error TEXT,
            extractor_version TEXT NOT NULL,
            memory_schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            applied_at TEXT,
            UNIQUE(operation_key),
            UNIQUE(memory_record_id, operation_version),
            CHECK(source_type IN ('revision','evidence_event','cleanup','reconciliation')),
            CHECK(operation_type IN ('add','update','supersede','revoke','delete')),
            CHECK(status IN ('pending','running','applied','retry_wait','reconcile_needed','obsolete','failed')),
            CHECK(operation_version >= 1),
            CHECK(expected_record_version >= 1),
            CHECK(attempt_count >= 0 AND attempt_count <= 8),
            CHECK(operation_key<>''),
            CHECK(target_state_hash<>'')
        );

        CREATE UNIQUE INDEX IF NOT EXISTS uq_class_commentary_active_memory_item
        ON class_commentary_memory_records (
            organization_id, memory_type, scope_hash, canonical_key
        )
        WHERE desired_status='active';

        CREATE INDEX IF NOT EXISTS idx_class_commentary_memory_records_scope
        ON class_commentary_memory_records (
            organization_id, memory_type, scope_hash, desired_status, updated_at
        );

        CREATE INDEX IF NOT EXISTS idx_class_commentary_memory_evidence_revision
        ON class_commentary_memory_evidence (revision_id, status, id);

        CREATE INDEX IF NOT EXISTS idx_class_commentary_memory_evidence_record
        ON class_commentary_memory_evidence (memory_record_id, status, id);

        CREATE INDEX IF NOT EXISTS idx_class_commentary_memory_extraction_dispatch
        ON class_commentary_memory_extraction_jobs (status, next_attempt_at, created_at);

        CREATE INDEX IF NOT EXISTS idx_class_commentary_memory_operations_dispatch
        ON class_commentary_memory_operations (status, next_attempt_at, lease_until, created_at);

        CREATE INDEX IF NOT EXISTS idx_class_commentary_memory_operations_record
        ON class_commentary_memory_operations (memory_record_id, operation_version DESC);

        CREATE INDEX IF NOT EXISTS idx_class_commentary_generations_task_created
        ON class_commentary_generations (task_id, generation_no DESC);

        CREATE INDEX IF NOT EXISTS idx_class_commentary_revisions_task_confirmed
        ON class_commentary_revisions (task_id, revision_no DESC);

        CREATE INDEX IF NOT EXISTS idx_class_commentary_skills_organization_status
        ON class_commentary_skills (organization_id, status, skill_id);

        CREATE INDEX IF NOT EXISTS idx_class_commentary_skill_candidate_dispatch
        ON class_commentary_skill_candidate_builds (status, next_attempt_at, created_at);

        CREATE INDEX IF NOT EXISTS idx_class_commentary_skill_candidate_revision_source
        ON class_commentary_skill_candidate_revisions (revision_id, candidate_build_id);

        CREATE INDEX IF NOT EXISTS idx_class_commentary_skill_candidate_evidence_source
        ON class_commentary_skill_candidate_evidence (memory_evidence_id, candidate_build_id);

        CREATE TRIGGER IF NOT EXISTS trg_class_commentary_candidate_revision_immutable
        BEFORE UPDATE ON class_commentary_skill_candidate_revisions
        BEGIN
            SELECT RAISE(ABORT, 'candidate revision snapshot is immutable');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_class_commentary_candidate_evidence_immutable
        BEFORE UPDATE ON class_commentary_skill_candidate_evidence
        BEGIN
            SELECT RAISE(ABORT, 'candidate evidence snapshot is immutable');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_class_commentary_candidate_version_snapshot_immutable
        BEFORE UPDATE OF candidate_build_id, content, content_hash, base_version_id,
                         source_snapshot_hash, evaluation_snapshot_json, evaluation_hash
        ON class_commentary_skill_versions
        WHEN OLD.version_kind='candidate'
        BEGIN
            SELECT RAISE(ABORT, 'candidate version snapshot is immutable');
        END;


        CREATE TRIGGER IF NOT EXISTS trg_class_commentary_skill_activation_event_immutable
        BEFORE UPDATE ON class_commentary_skill_activation_events
        BEGIN
            SELECT RAISE(ABORT, 'skill activation event is immutable');
        END;
        """
    )
    _ensure_class_commentary_skill_activation_reason_schema(conn)

    _ensure_column(
        conn,
        "class_commentary_tasks",
        "latest_generation_id",
        "INTEGER REFERENCES class_commentary_generations(id) ON DELETE SET NULL",
    )
    _ensure_column(
        conn,
        "class_commentary_tasks",
        "latest_revision_id",
        "INTEGER REFERENCES class_commentary_revisions(id) ON DELETE SET NULL",
    )
    _ensure_column(
        conn,
        "class_commentary_generations",
        "attending_roster_explicit",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(
        conn,
        "class_commentary_generations",
        "execution_snapshot_status",
        "TEXT NOT NULL DEFAULT 'ready'",
    )
    _ensure_column(
        conn,
        "class_commentary_generations",
        "execution_snapshot_finalized_at",
        "TEXT",
    )
    _ensure_class_commentary_structured_feedback_schema(conn)
    _ensure_column(
        conn,
        "class_commentary_skill_candidate_builds",
        "requested_by_user_id",
        "INTEGER REFERENCES users(id)",
    )
    conn.executescript(
        """
        DROP TRIGGER IF EXISTS trg_class_commentary_candidate_build_source_immutable;
        CREATE TRIGGER trg_class_commentary_candidate_build_source_immutable
        BEFORE UPDATE OF organization_id, skill_registry_id, requested_by_user_id,
                         candidate_request_id, candidate_payload_hash,
                         expected_active_version_id, base_version_id,
                         source_cutoff_at, selection_policy_version,
                         min_effective_tasks, min_support_tasks,
                         source_snapshot_hash, effective_task_count,
                         supporting_task_count
        ON class_commentary_skill_candidate_builds
        BEGIN
            SELECT RAISE(ABORT, 'candidate build source snapshot is immutable');
        END;
        """
    )
    conn.execute(
        """
        UPDATE class_commentary_skill_candidate_builds
        SET status='obsolete', claim_token=NULL, claim_owner=NULL,
            next_attempt_at=NULL, last_error='selection_policy_changed',
            completed_at=COALESCE(completed_at, datetime('now','localtime'))
        WHERE selection_policy_version<>?
          AND (
              status IN ('queued','running','retry_wait')
              OR (
                  status='succeeded'
                  AND EXISTS (
                      SELECT 1
                      FROM class_commentary_skill_versions AS version
                      WHERE version.id=class_commentary_skill_candidate_builds.candidate_version_id
                        AND version.review_status='pending'
                  )
              )
          )
        """,
        (CLASS_COMMENTARY_SKILL_SELECTION_POLICY_VERSION,),
    )
    conn.execute(
        """
        UPDATE class_commentary_skill_versions
        SET review_status='rejected',
            reviewed_at=COALESCE(reviewed_at, datetime('now','localtime'))
        WHERE review_status='pending'
          AND candidate_build_id IN (
              SELECT id
              FROM class_commentary_skill_candidate_builds
              WHERE selection_policy_version<>?
          )
        """,
        (CLASS_COMMENTARY_SKILL_SELECTION_POLICY_VERSION,),
    )
    _ensure_column(
        conn,
        "class_commentary_revisions",
        "confirmed_draft_version",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(
        conn,
        "class_commentary_revisions",
        "confirmed_draft_snapshot_json",
        "TEXT NOT NULL DEFAULT '{}'",
    )
    _ensure_column(
        conn,
        "class_commentary_memory_operations",
        "cleanup_scope_type",
        "TEXT",
    )
    _ensure_column(
        conn,
        "class_commentary_memory_operations",
        "cleanup_scope_id",
        "INTEGER",
    )
    conn.execute(
        """
        UPDATE class_commentary_memory_operations
        SET cleanup_scope_type='legacy', cleanup_scope_id=source_id
        WHERE source_type='cleanup'
          AND cleanup_scope_type IS NULL
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_class_commentary_memory_cleanup_scope
        ON class_commentary_memory_operations (
            organization_id, source_type, cleanup_scope_type,
            cleanup_scope_id, status
        )
        """
    )

    legacy_tasks = conn.execute(
        """
        SELECT task.*, class.subject_key
        FROM class_commentary_tasks AS task
        JOIN classes AS class ON class.id = task.class_id
        WHERE feedback_text <> ''
          AND latest_generation_id IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM class_commentary_generations AS generation
              WHERE generation.task_id = task.id
                AND generation.origin = 'legacy_migration'
          )
        ORDER BY id
        """
    ).fetchall()
    for task in legacy_tasks:
        transcript_text = task["confirmed_transcript_text"] or ""
        transcript_hash = hashlib.sha256(transcript_text.encode("utf-8")).hexdigest()
        skill_content = task["skill_content_snapshot"] or ""
        skill_content_hash = hashlib.sha256(skill_content.encode("utf-8")).hexdigest()
        missing_snapshot_fields = [
            "generation_request_id",
            "generation_request_payload_hash",
            "attending_roster_snapshot_json",
            "attending_roster_hash",
            "skill_registry_id",
            "skill_version_id",
            "model_parameters_json",
            "prompt_version",
            "prompt_payload_snapshot_json",
            "prompt_payload_hash",
            "memory_context_snapshot_json",
            "memory_context_hash",
        ]
        if not transcript_text:
            missing_snapshot_fields.extend(
                ["confirmed_transcript_snapshot", "confirmed_transcript_hash"]
            )
        if not task["subject_key"]:
            missing_snapshot_fields.append("subject_key")
        if not task["skill_id"]:
            missing_snapshot_fields.append("skill_id")
        if not skill_content:
            missing_snapshot_fields.extend(["skill_content_snapshot", "skill_content_hash"])
        if not task["chat_provider"]:
            missing_snapshot_fields.append("model_provider")
        if not task["chat_model"]:
            missing_snapshot_fields.append("model_name")
        cursor = conn.execute(
            """
            INSERT INTO class_commentary_generations (
                organization_id,
                task_id,
                generation_no,
                teacher_user_id,
                class_id,
                subject_key,
                confirmed_transcript_version,
                confirmed_transcript_snapshot,
                confirmed_transcript_hash,
                attending_roster_snapshot_json,
                attending_roster_hash,
                skill_id,
                skill_content_snapshot,
                skill_content_hash,
                model_provider,
                model_name,
                generated_feedback_text,
                origin,
                snapshot_completeness,
                missing_snapshot_fields_json,
                status,
                completed_at
            )
            VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, '[]', '', ?, ?, ?, ?, ?, ?,
                    'legacy_migration', 'partial', ?, 'succeeded', ?)
            """,
            (
                task["organization_id"],
                task["id"],
                task["teacher_user_id"],
                task["class_id"],
                task["subject_key"] or None,
                task["confirmed_transcript_version"],
                transcript_text,
                transcript_hash,
                task["skill_id"] or None,
                skill_content,
                skill_content_hash,
                task["chat_provider"] or None,
                task["chat_model"] or None,
                task["feedback_text"],
                json.dumps(missing_snapshot_fields, ensure_ascii=False, separators=(",", ":")),
                task["updated_at"],
            ),
        )
        conn.execute(
            """
            UPDATE class_commentary_tasks
            SET latest_generation_id=?, generation_seq=1
            WHERE id=?
            """,
            (cursor.lastrowid, task["id"]),
        )


def _migrate_course_calendar_time_blocks(conn: sqlite3.Connection) -> None:
    for legacy_block, current_block in LEGACY_COURSE_CALENDAR_TIME_BLOCKS.items():
        conn.execute(
            "UPDATE OR IGNORE course_calendar_schedules SET time_block=? WHERE time_block=?",
            (current_block, legacy_block),
        )
        conn.execute("DELETE FROM course_calendar_schedules WHERE time_block=?", (legacy_block,))


def _drop_legacy_table_if_exists(conn: sqlite3.Connection, table: str) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    if row:
        conn.execute(f"DROP TABLE {table}")

def _rebuild_wrong_question_submissions_without_legacy_feedback_columns(conn: sqlite3.Connection) -> None:
    column_rows = conn.execute("PRAGMA table_info(wrong_question_submissions)").fetchall()
    columns = [row[1] for row in column_rows]
    notnull_by_column = {row[1]: row[3] for row in column_rows}
    needs_multisource_rebuild = bool(notnull_by_column.get("parent_wechat_account_id")) or bool(
        notnull_by_column.get("binding_id")
    )
    if "parent_note" not in columns and "teacher_comment" not in columns and not needs_multisource_rebuild:
        return

    copy_columns = [
        column
        for column in [
            "id",
            "organization_id",
            "source",
            "parent_wechat_account_id",
            "binding_id",
            "class_id",
            "student_id",
            "teacher_user_id",
            "image_url",
            "child_raw_reason_text",
            "child_reason_transcript",
            "child_reason_input_mode",
            "primary_error_type",
            "secondary_error_summary",
            "child_reason_core_issue",
            "child_reason_key_omission",
            "child_reason_next_step",
            "topic_category",
            "archive_status",
            "archived_at",
            "status",
            "recognition_status",
            "is_geometry",
            "image_rotation_degrees",
            "question_text",
            "question_text_edited",
            "question_text_source",
            "diagram_type",
            "diagram_spec_json",
            "recognition_error",
            "student_library_pdf_path",
            "ingestion_run_id",
            "chat_session_id",
            "question_structured_json",
            "knowledge_tags_json",
            "reflection_summary_json",
            "generation_metadata_json",
            "mastery_tracking_json",
            "needs_teacher_confirmation",
            "confirmation_reasons_json",
            "created_at",
            "updated_at",
        ]
        if column in columns
    ]

    conn.execute(
        """
        ALTER TABLE wrong_question_submissions
        RENAME TO wrong_question_submissions__legacy_feedback
        """
    )
    conn.execute(
        """
        CREATE TABLE wrong_question_submissions (
            id                        TEXT PRIMARY KEY,
            organization_id           INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            source                    TEXT NOT NULL DEFAULT 'wechat_mp',
            parent_wechat_account_id  INTEGER REFERENCES parent_wechat_accounts(id) ON DELETE CASCADE,
            binding_id                INTEGER REFERENCES parent_student_bindings(id) ON DELETE CASCADE,
            class_id                  INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            student_id                INTEGER NOT NULL REFERENCES students(id),
            teacher_user_id           INTEGER NOT NULL REFERENCES users(id),
            image_url                 TEXT NOT NULL,
            child_raw_reason_text     TEXT NOT NULL DEFAULT '',
            child_reason_transcript   TEXT NOT NULL DEFAULT '',
            child_reason_input_mode   TEXT NOT NULL DEFAULT 'text',
            primary_error_type        TEXT NOT NULL DEFAULT '',
            secondary_error_summary   TEXT NOT NULL DEFAULT '',
            child_reason_core_issue   TEXT NOT NULL DEFAULT '',
            child_reason_key_omission TEXT NOT NULL DEFAULT '',
            child_reason_next_step    TEXT NOT NULL DEFAULT '',
            topic_category            TEXT NOT NULL DEFAULT '未分类',
            archive_status            TEXT NOT NULL DEFAULT 'active',
            archived_at               TEXT DEFAULT '',
            status                    TEXT NOT NULL DEFAULT 'pending',
            recognition_status        TEXT NOT NULL DEFAULT 'pending',
            is_geometry               INTEGER NOT NULL DEFAULT 0,
            image_rotation_degrees    INTEGER NOT NULL DEFAULT 0,
            question_text             TEXT NOT NULL DEFAULT '',
            question_text_edited      INTEGER NOT NULL DEFAULT 0,
            question_text_source      TEXT NOT NULL DEFAULT 'ai',
            diagram_type              TEXT NOT NULL DEFAULT '',
            diagram_spec_json         TEXT NOT NULL DEFAULT '',
            recognition_error         TEXT NOT NULL DEFAULT '',
            student_library_pdf_path  TEXT NOT NULL DEFAULT '',
            ingestion_run_id          TEXT NOT NULL DEFAULT '',
            chat_session_id           TEXT NOT NULL DEFAULT '',
            question_structured_json  TEXT NOT NULL DEFAULT '',
            knowledge_tags_json       TEXT NOT NULL DEFAULT '[]',
            reflection_summary_json   TEXT NOT NULL DEFAULT '{}',
            generation_metadata_json  TEXT NOT NULL DEFAULT '{}',
            mastery_tracking_json     TEXT NOT NULL DEFAULT '{}',
            needs_teacher_confirmation INTEGER NOT NULL DEFAULT 0,
            confirmation_reasons_json TEXT NOT NULL DEFAULT '[]',
            confirmation_status      TEXT NOT NULL DEFAULT '',
            confirmation_reviewed_by INTEGER,
            confirmation_reviewed_at TEXT NOT NULL DEFAULT '',
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime'))
        )
        """
    )
    if copy_columns:
        quoted_columns = ", ".join(f'"{column}"' for column in copy_columns)
        conn.execute(
            f'INSERT INTO wrong_question_submissions ({quoted_columns}) '
            f'SELECT {quoted_columns} FROM "wrong_question_submissions__legacy_feedback"'
        )
    conn.execute("DROP TABLE wrong_question_submissions__legacy_feedback")


def _ensure_weekly_wrong_question_followup_messages_user_delete_policy(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(weekly_wrong_question_followup_messages)").fetchall()
    if not columns:
        return

    notnull_by_column = {row["name"]: row["notnull"] for row in columns}
    foreign_keys = conn.execute("PRAGMA foreign_key_list(weekly_wrong_question_followup_messages)").fetchall()
    user_delete_by_column = {
        row["from"]: row["on_delete"]
        for row in foreign_keys
        if row["table"] == "users"
    }
    if (
        notnull_by_column.get("teacher_user_id") == 0
        and user_delete_by_column.get("teacher_user_id") == "SET NULL"
        and user_delete_by_column.get("generated_by") == "SET NULL"
    ):
        return

    conn.execute(
        """
        ALTER TABLE weekly_wrong_question_followup_messages
        RENAME TO weekly_wrong_question_followup_messages__legacy_user_fk
        """
    )
    conn.execute(
        """
        CREATE TABLE weekly_wrong_question_followup_messages (
            id                            INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id               INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            class_id                      INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            student_id                    INTEGER NOT NULL REFERENCES students(id),
            teacher_user_id               INTEGER REFERENCES users(id) ON DELETE SET NULL,
            week_start_date               TEXT NOT NULL,
            week_end_date                 TEXT NOT NULL,
            style                         TEXT NOT NULL DEFAULT 'warm',
            message_text                  TEXT NOT NULL DEFAULT '',
            source_record_ids_json        TEXT NOT NULL DEFAULT '[]',
            source_sheet_id               INTEGER DEFAULT NULL REFERENCES wrong_question_practice_sheets(id) ON DELETE SET NULL,
            generated_by                  INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at                    TEXT DEFAULT (datetime('now','localtime')),
            updated_at                    TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(organization_id, class_id, student_id, week_start_date, style)
        )
        """
    )
    copy_columns = [
        column
        for column in [
            "id",
            "organization_id",
            "class_id",
            "student_id",
            "teacher_user_id",
            "week_start_date",
            "week_end_date",
            "style",
            "message_text",
            "source_record_ids_json",
            "source_sheet_id",
            "generated_by",
            "created_at",
            "updated_at",
        ]
        if column in notnull_by_column
    ]
    if copy_columns:
        quoted_columns = ", ".join(f'"{column}"' for column in copy_columns)
        conn.execute(
            f'INSERT INTO weekly_wrong_question_followup_messages ({quoted_columns}) '
            f'SELECT {quoted_columns} FROM "weekly_wrong_question_followup_messages__legacy_user_fk"'
        )
    conn.execute("DROP TABLE weekly_wrong_question_followup_messages__legacy_user_fk")


def _consultation_row_to_storage(row: dict, organization_id: int) -> dict[str, str | int]:
    teacher_directory = _get_consultation_teacher_directory()
    serialized = _serialize_consultation_row(row, teacher_directory)
    flow_stage = _normalize_consultation_flow_stage(row.get("flow_stage"), serialized.get("follow_up_status", ""))
    completed_stages = _normalize_consultation_completed_stages(row.get("completed_stages"), flow_stage)
    trial_class_id = _normalize_optional_int(row.get("trial_class_id"))
    success_class_id = _normalize_optional_int(row.get("success_class_id"))
    closed_by_user_id = _normalize_optional_int(row.get("closed_by_user_id"))
    success_class_manual = str(row.get("success_class_manual") or "").strip()
    if row.get("_require_success_class") and flow_stage == "成功进班" and not success_class_id and not success_class_manual:
        raise ValueError("成功进班必须选择或填写班级")
    existing_ended_at = str(row.get("ended_at") or "").strip()
    if flow_stage in CONSULTATION_TERMINAL_STAGES:
        ended_at = existing_ended_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        ended_at = ""
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
        "follow_up_status": _derive_consultation_follow_up_status(flow_stage),
        "follow_up_note": serialized.get("follow_up_note", ""),
        "created_at": serialized.get("created_at", ""),
        "updated_at": serialized.get("updated_at", ""),
        "flow_stage": flow_stage,
        "completed_stages_json": json.dumps(completed_stages, ensure_ascii=False),
        "stage_teacher_ids_json": json.dumps(_json_dict(row.get("stage_teacher_ids")), ensure_ascii=False),
        "responsibility_history_json": json.dumps(_json_list(row.get("responsibility_history")), ensure_ascii=False),
        "assigned_stage": str(row.get("assigned_stage") or "").strip(),
        "assignment_note": str(row.get("assignment_note") or "").strip(),
        "test_taken": str(row.get("test_taken") or ""),
        "customer_service_added": str(row.get("customer_service_added") or ""),
        "customer_service_teacher": str(row.get("customer_service_teacher") or ""),
        "customer_service_note": str(row.get("customer_service_note") or ""),
        "communication_teacher_added": str(row.get("communication_teacher_added") or ""),
        "communication_teacher_note": str(row.get("communication_teacher_note") or ""),
        "test_teacher": str(row.get("test_teacher") or ""),
        "test_note": str(row.get("test_note") or ""),
        "test_images_json": json.dumps(_json_list(row.get("test_images")), ensure_ascii=False),
        "trial_teacher_added": str(row.get("trial_teacher_added") or ""),
        "trial_teacher_note": str(row.get("trial_teacher_note") or ""),
        "trial_taken": str(row.get("trial_taken") or ""),
        "trial_time_slot": str(row.get("trial_time_slot") or ""),
        "trial_class_id": trial_class_id,
        "trial_class_manual": str(row.get("trial_class_manual") or ""),
        "trial_teacher": str(row.get("trial_teacher") or ""),
        "trial_feedback": str(row.get("trial_feedback") or ""),
        "success_class_id": success_class_id,
        "teaching_teacher_added": str(row.get("teaching_teacher_added") or ""),
        "teaching_teacher": str(row.get("teaching_teacher") or ""),
        "teaching_teacher_note": str(row.get("teaching_teacher_note") or ""),
        "success_class_manual": success_class_manual,
        "enrollment_handoff_note": str(row.get("enrollment_handoff_note") or ""),
        "student_profile_status": str(row.get("student_profile_status") or ""),
        "student_profile_note": str(row.get("student_profile_note") or ""),
        "failure_reason": str(row.get("failure_reason") or ""),
        "failure_note": str(row.get("failure_note") or ""),
        "closing_result": str(row.get("closing_result") or ""),
        "closed_by_user_id": closed_by_user_id,
        "end_note": str(row.get("end_note") or ""),
        "ended_at": ended_at,
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
    # Get receiving_teacher from JOIN result (users.display_name) or use empty string if unassigned
    legacy_row["接待老师"] = payload.get("display_name", "") or ""
    # Get teacher_id from JOIN result (users.username) or use empty string if unassigned
    legacy_row["老师ID"] = payload.get("username", "") or ""
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
    serialized["assigned_user_id"] = payload.get("assigned_user_id")
    serialized["created_by_user_id"] = payload.get("created_by_user_id")
    flow_stage = _normalize_consultation_flow_stage(payload.get("flow_stage"), payload.get("follow_up_status", ""))
    serialized["flow_stage"] = flow_stage
    serialized["completed_stages"] = _normalize_consultation_completed_stages(
        payload.get("completed_stages_json", "[]"),
        flow_stage,
    )
    serialized["stage_teacher_ids"] = _json_dict(payload.get("stage_teacher_ids_json", "{}"))
    serialized["responsibility_history"] = _json_list(payload.get("responsibility_history_json", "[]"))
    serialized["assigned_stage"] = payload.get("assigned_stage", "") or ""
    serialized["assignment_note"] = payload.get("assignment_note", "") or ""
    serialized["is_transferred_consultation"] = False
    serialized["can_edit_consultation"] = True
    serialized["transfer_marker"] = ""
    serialized["current_responsibility"] = ""
    serialized["follow_up_status"] = _derive_consultation_follow_up_status(flow_stage)
    serialized["test_taken"] = payload.get("test_taken", "") or ""
    serialized["customer_service_added"] = payload.get("customer_service_added", "") or ""
    serialized["customer_service_teacher"] = payload.get("customer_service_teacher", "") or ""
    serialized["customer_service_note"] = payload.get("customer_service_note", "") or ""
    serialized["communication_teacher_added"] = payload.get("communication_teacher_added", "") or ""
    serialized["communication_teacher_note"] = payload.get("communication_teacher_note", "") or ""
    serialized["test_teacher"] = payload.get("test_teacher", "") or ""
    serialized["test_note"] = payload.get("test_note", "") or ""
    serialized["test_images"] = _json_list(payload.get("test_images_json", "[]"))
    serialized["trial_teacher_added"] = payload.get("trial_teacher_added", "") or ""
    serialized["trial_teacher_note"] = payload.get("trial_teacher_note", "") or ""
    serialized["trial_taken"] = payload.get("trial_taken", "") or ""
    serialized["trial_time_slot"] = payload.get("trial_time_slot", "") or ""
    serialized["trial_class_id"] = payload.get("trial_class_id")
    serialized["trial_class_manual"] = payload.get("trial_class_manual", "") or ""
    serialized["trial_teacher"] = payload.get("trial_teacher", "") or ""
    serialized["trial_feedback"] = payload.get("trial_feedback", "") or ""
    serialized["success_class_id"] = payload.get("success_class_id")
    serialized["teaching_teacher_added"] = payload.get("teaching_teacher_added", "") or ""
    serialized["teaching_teacher"] = payload.get("teaching_teacher", "") or ""
    serialized["teaching_teacher_note"] = payload.get("teaching_teacher_note", "") or ""
    serialized["success_class_manual"] = payload.get("success_class_manual", "") or ""
    serialized["enrollment_handoff_note"] = payload.get("enrollment_handoff_note", "") or ""
    serialized["student_profile_status"] = payload.get("student_profile_status", "") or ""
    serialized["student_profile_note"] = payload.get("student_profile_note", "") or ""
    serialized["failure_reason"] = payload.get("failure_reason", "") or ""
    serialized["failure_note"] = payload.get("failure_note", "") or ""
    serialized["closing_result"] = payload.get("closing_result", "") or ""
    serialized["closed_by_user_id"] = payload.get("closed_by_user_id")
    serialized["end_note"] = payload.get("end_note", "") or ""
    serialized["ended_at"] = payload.get("ended_at", "") or ""
    return serialized


def _ensure_consultations_table(conn: sqlite3.Connection) -> None:
    # Check if old schema exists (without assigned_user_id column)
    try:
        cursor = conn.execute("PRAGMA table_info(consultations)")
        cols = {row[1] for row in cursor.fetchall()}
        if cols and 'assigned_user_id' not in cols:
            # Old schema, drop and rebuild
            conn.execute("DROP TABLE consultations")
    except Exception:
        pass  # Table doesn't exist, will create new one
    
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS consultations (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id      INTEGER NOT NULL REFERENCES organizations(id),
            assigned_user_id     INTEGER REFERENCES users(id),
            date                 TEXT DEFAULT '',
            parent_wechat_name   TEXT DEFAULT '',
            child_name           TEXT DEFAULT '',
            grade                TEXT DEFAULT '',
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
    _ensure_column(conn, "consultations", "flow_stage", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "completed_stages_json", "TEXT DEFAULT '[]'")
    _ensure_column(conn, "consultations", "stage_teacher_ids_json", "TEXT DEFAULT '{}'")
    _ensure_column(conn, "consultations", "responsibility_history_json", "TEXT DEFAULT '[]'")
    _ensure_column(conn, "consultations", "created_by_user_id", "INTEGER")
    _ensure_column(conn, "consultations", "assigned_stage", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "assignment_note", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "customer_service_added", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "customer_service_teacher", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "customer_service_note", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "communication_teacher_added", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "communication_teacher_note", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "test_taken", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "test_teacher", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "test_note", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "test_images_json", "TEXT DEFAULT '[]'")
    _ensure_column(conn, "consultations", "trial_teacher_added", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "trial_teacher_note", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "trial_taken", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "trial_time_slot", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "trial_class_id", "INTEGER")
    _ensure_column(conn, "consultations", "trial_class_manual", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "trial_teacher", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "trial_feedback", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "success_class_id", "INTEGER")
    _ensure_column(conn, "consultations", "teaching_teacher_added", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "teaching_teacher", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "teaching_teacher_note", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "success_class_manual", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "enrollment_handoff_note", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "student_profile_status", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "student_profile_note", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "failure_reason", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "failure_note", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "closing_result", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "closed_by_user_id", "INTEGER")
    _ensure_column(conn, "consultations", "end_note", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "ended_at", "TEXT DEFAULT ''")


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


def _backfill_student_organization_scope(conn: sqlite3.Connection, fallback_organization_id: int) -> None:
    _ensure_column(conn, "students", "organization_id", "INTEGER REFERENCES organizations(id)")
    conflicting_row = conn.execute(
        """
        SELECT cs.student_id
        FROM class_students cs
        JOIN classes c ON c.id = cs.class_id
        WHERE c.organization_id IS NOT NULL
        GROUP BY cs.student_id
        HAVING COUNT(DISTINCT c.organization_id) > 1
        LIMIT 1
        """
    ).fetchone()
    if conflicting_row:
        raise ValueError(
            f"student {conflicting_row['student_id']} links to multiple organizations via classes"
        )
    conn.execute(
        """
        UPDATE students
        SET organization_id=COALESCE(
            (
                SELECT MIN(c.organization_id)
                FROM class_students cs
                JOIN classes c ON c.id = cs.class_id
                WHERE cs.student_id = students.id
                  AND c.organization_id IS NOT NULL
            ),
            ?
        )
        WHERE organization_id IS NULL
        """,
        (fallback_organization_id,),
    )
    _enforce_students_organization_contract(conn)


def _has_strict_organization_fk(conn: sqlite3.Connection, table: str) -> bool:
    columns = {row["name"]: row for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    org_col = columns.get("organization_id")
    if not org_col or int(org_col["notnull"]) != 1:
        return False
    for row in conn.execute(f"PRAGMA foreign_key_list({table})").fetchall():
        if row["from"] == "organization_id":
            return row["table"] == "organizations" and (row["on_delete"] or "").upper() == "CASCADE"
    return False


def _enforce_students_organization_contract(conn: sqlite3.Connection) -> None:
    if _has_strict_organization_fk(conn, "students"):
        return
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS students__org_scope_legacy")
        conn.execute("ALTER TABLE students RENAME TO students__org_scope_legacy")
        conn.execute(
            """
	        CREATE TABLE students (
	            id              INTEGER PRIMARY KEY AUTOINCREMENT,
	            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
	            name            TEXT NOT NULL,
	            source          TEXT NOT NULL DEFAULT '',
	            parent_contact  TEXT NOT NULL DEFAULT '',
	            status          TEXT NOT NULL DEFAULT 'active',
	            archived_at     TEXT NOT NULL DEFAULT '',
	            created_at      TEXT DEFAULT (datetime('now','localtime'))
	        )
            """
        )
        conn.execute(
            """
	        INSERT INTO students (id, organization_id, name, source, parent_contact, status, archived_at, created_at)
	        SELECT id, organization_id, name, '', '', 'active', '', created_at
	        FROM students__org_scope_legacy
            """
        )
        conn.execute("DROP TABLE students__org_scope_legacy")
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


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
            class_id    INTEGER REFERENCES classes(id) ON DELETE SET NULL,
            current_review_plan_version_id INTEGER DEFAULT NULL,
            created_by_user_id INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            updated_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS review_plan_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id        INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
            version_id       INTEGER DEFAULT NULL REFERENCES review_plan_versions(id) ON DELETE CASCADE,
            organization_id  INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            trace_id         TEXT NOT NULL UNIQUE,
            status           TEXT NOT NULL DEFAULT 'running',
            subject          TEXT NOT NULL DEFAULT '',
            provider         TEXT NOT NULL DEFAULT '',
            model            TEXT NOT NULL DEFAULT '',
            prompt_version   TEXT NOT NULL DEFAULT '',
            style_version    TEXT NOT NULL DEFAULT '',
            schema_version   TEXT NOT NULL DEFAULT '',
            warnings_json    TEXT NOT NULL DEFAULT '[]',
            quality_review_json TEXT NOT NULL DEFAULT '{}',
            node_outputs_json TEXT NOT NULL DEFAULT '{}',
            logs_json        TEXT NOT NULL DEFAULT '[]',
            created_at       TEXT DEFAULT (datetime('now','localtime')),
            updated_at       TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS organizations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            status      TEXT NOT NULL DEFAULT 'active',
            deleted_at  TEXT NOT NULL DEFAULT '',
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
            visible_pages_json TEXT DEFAULT NULL,
            avatar_source   TEXT NOT NULL DEFAULT 'dicebear',
            avatar_seed     TEXT NOT NULL DEFAULT '',
            avatar_upload_path TEXT NOT NULL DEFAULT '',
            recovery_phone  TEXT NOT NULL DEFAULT '',
            security_question TEXT NOT NULL DEFAULT '',
            security_answer_hash TEXT NOT NULL DEFAULT '',
            initial_class_claim_completed INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS monthly_plan_jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            user_id         INTEGER NOT NULL REFERENCES users(id),
            month_str       TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',
            pdf_filename    TEXT NOT NULL DEFAULT '',
            generation_error TEXT NOT NULL DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now','localtime')),
            updated_at      TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS registration_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT NOT NULL,
            password_hash   TEXT NOT NULL,
            display_name    TEXT NOT NULL,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            status          TEXT NOT NULL DEFAULT 'pending',
            recovery_phone  TEXT NOT NULL DEFAULT '',
            security_question TEXT NOT NULL DEFAULT '',
            security_answer_hash TEXT NOT NULL DEFAULT '',
            reviewed_by     INTEGER REFERENCES users(id),
            reviewed_at     TEXT,
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_review_plan_runs_lesson_updated
        ON review_plan_runs(lesson_id, updated_at);
        CREATE TABLE IF NOT EXISTS organization_requests (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_name TEXT NOT NULL,
            username          TEXT NOT NULL,
            password_hash     TEXT NOT NULL,
            display_name      TEXT NOT NULL,
            status            TEXT NOT NULL DEFAULT 'pending',
            recovery_phone    TEXT NOT NULL DEFAULT '',
            security_question TEXT NOT NULL DEFAULT '',
            security_answer_hash TEXT NOT NULL DEFAULT '',
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

        CREATE TABLE IF NOT EXISTS student_accounts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            student_id      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            username        TEXT NOT NULL UNIQUE,
            password_hash   TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'active',
            created_at      TEXT DEFAULT (datetime('now','localtime')),
            last_login      TEXT,
            UNIQUE(student_id)
        );

        CREATE TABLE IF NOT EXISTS student_auth_sessions (
            token       TEXT PRIMARY KEY,
            account_id  INTEGER NOT NULL REFERENCES student_accounts(id) ON DELETE CASCADE,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS user_classes (
            user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, class_id)
        );

        CREATE TABLE IF NOT EXISTS course_calendar_schedules (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            class_id        INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            date            TEXT NOT NULL,
            time_block      TEXT NOT NULL,
            start_offset_minutes INTEGER NOT NULL DEFAULT 0,
            created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at      TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(class_id, date, time_block)
        );

        CREATE TABLE IF NOT EXISTS course_calendar_custom_items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            title           TEXT NOT NULL,
            time_range      TEXT NOT NULL,
            note            TEXT NOT NULL DEFAULT '',
            visibility      TEXT NOT NULL DEFAULT 'private',
            created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS course_calendar_custom_schedules (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            custom_item_id  INTEGER NOT NULL REFERENCES course_calendar_custom_items(id) ON DELETE CASCADE,
            date            TEXT NOT NULL,
            time_block      TEXT NOT NULL,
            start_offset_minutes INTEGER NOT NULL DEFAULT 0,
            created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at      TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(custom_item_id, date, time_block)
        );


	        CREATE TABLE IF NOT EXISTS students (
	            id              INTEGER PRIMARY KEY AUTOINCREMENT,
	            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
	            name            TEXT NOT NULL,
	            source          TEXT NOT NULL DEFAULT '',
	            parent_contact  TEXT NOT NULL DEFAULT '',
	            status          TEXT NOT NULL DEFAULT 'active',
	            archived_at     TEXT NOT NULL DEFAULT '',
	            created_at      TEXT DEFAULT (datetime('now','localtime'))
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
            parent_wechat_account_id  INTEGER REFERENCES parent_wechat_accounts(id) ON DELETE CASCADE,
            binding_id                INTEGER REFERENCES parent_student_bindings(id) ON DELETE CASCADE,
            class_id                  INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            student_id                INTEGER NOT NULL REFERENCES students(id),
            teacher_user_id           INTEGER NOT NULL REFERENCES users(id),
            image_url                 TEXT NOT NULL,
            child_raw_reason_text     TEXT NOT NULL DEFAULT '',
            child_reason_transcript   TEXT NOT NULL DEFAULT '',
            child_reason_input_mode   TEXT NOT NULL DEFAULT 'text',
            primary_error_type        TEXT NOT NULL DEFAULT '',
            secondary_error_summary   TEXT NOT NULL DEFAULT '',
            child_reason_core_issue   TEXT NOT NULL DEFAULT '',
            child_reason_key_omission TEXT NOT NULL DEFAULT '',
            child_reason_next_step    TEXT NOT NULL DEFAULT '',
            topic_category            TEXT NOT NULL DEFAULT '未分类',
            archive_status            TEXT NOT NULL DEFAULT 'active',
            archived_at               TEXT DEFAULT '',
            status                    TEXT NOT NULL DEFAULT 'pending',
            recognition_status        TEXT NOT NULL DEFAULT 'pending',
            is_geometry               INTEGER NOT NULL DEFAULT 0,
            image_rotation_degrees    INTEGER NOT NULL DEFAULT 0,
            question_text             TEXT NOT NULL DEFAULT '',
            question_text_edited      INTEGER NOT NULL DEFAULT 0,
            question_text_source      TEXT NOT NULL DEFAULT 'ai',
            diagram_type              TEXT NOT NULL DEFAULT '',
            diagram_spec_json         TEXT NOT NULL DEFAULT '',
            recognition_error         TEXT NOT NULL DEFAULT '',
            student_library_pdf_path  TEXT NOT NULL DEFAULT '',
            ingestion_run_id          TEXT NOT NULL DEFAULT '',
            chat_session_id           TEXT NOT NULL DEFAULT '',
            question_structured_json  TEXT NOT NULL DEFAULT '',
            knowledge_tags_json       TEXT NOT NULL DEFAULT '[]',
            reflection_summary_json   TEXT NOT NULL DEFAULT '{}',
            generation_metadata_json  TEXT NOT NULL DEFAULT '{}',
            mastery_tracking_json     TEXT NOT NULL DEFAULT '{}',
            needs_teacher_confirmation INTEGER NOT NULL DEFAULT 0,
            confirmation_reasons_json TEXT NOT NULL DEFAULT '[]',
            confirmation_status      TEXT NOT NULL DEFAULT '',
            confirmation_reviewed_by INTEGER,
            confirmation_reviewed_at TEXT NOT NULL DEFAULT '',
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS wrong_question_ingestion_runs (
            id                        TEXT PRIMARY KEY,
            organization_id           INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            source                    TEXT NOT NULL DEFAULT 'workspace',
            class_id                  INTEGER REFERENCES classes(id) ON DELETE CASCADE,
            student_id                INTEGER REFERENCES students(id),
            teacher_user_id           INTEGER REFERENCES users(id),
            parent_wechat_account_id  INTEGER REFERENCES parent_wechat_accounts(id) ON DELETE CASCADE,
            chat_session_id           TEXT NOT NULL DEFAULT '',
            status                    TEXT NOT NULL DEFAULT 'pending',
            current_step              TEXT NOT NULL DEFAULT 'uploaded',
            original_filename         TEXT NOT NULL DEFAULT '',
            mime_type                 TEXT NOT NULL DEFAULT '',
            error_message             TEXT NOT NULL DEFAULT '',
            metadata_json             TEXT NOT NULL DEFAULT '{}',
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS wrong_question_assets (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            ingestion_run_id          TEXT NOT NULL REFERENCES wrong_question_ingestion_runs(id) ON DELETE CASCADE,
            asset_role                TEXT NOT NULL,
            storage_path              TEXT NOT NULL DEFAULT '',
            file_url                  TEXT NOT NULL DEFAULT '',
            mime_type                 TEXT NOT NULL DEFAULT '',
            page_number               INTEGER NOT NULL DEFAULT 0,
            width                     INTEGER NOT NULL DEFAULT 0,
            height                    INTEGER NOT NULL DEFAULT 0,
            metadata_json             TEXT NOT NULL DEFAULT '{}',
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS wrong_question_chat_sessions (
            id                        TEXT PRIMARY KEY,
            organization_id           INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            ingestion_run_id          TEXT NOT NULL DEFAULT '' REFERENCES wrong_question_ingestion_runs(id) ON DELETE SET DEFAULT,
            class_id                  INTEGER REFERENCES classes(id) ON DELETE CASCADE,
            student_id                INTEGER REFERENCES students(id),
            teacher_user_id           INTEGER REFERENCES users(id),
            status                    TEXT NOT NULL DEFAULT 'active',
            current_stage             TEXT NOT NULL DEFAULT 'ask_why_wrong',
            summary_text              TEXT NOT NULL DEFAULT '',
            metadata_json             TEXT NOT NULL DEFAULT '{}',
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS wrong_question_chat_messages (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id                TEXT NOT NULL REFERENCES wrong_question_chat_sessions(id) ON DELETE CASCADE,
            role                      TEXT NOT NULL,
            stage                     TEXT NOT NULL DEFAULT '',
            content                   TEXT NOT NULL,
            metadata_json             TEXT NOT NULL DEFAULT '{}',
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS wechat_wrong_question_upload_tasks (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id           INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            parent_wechat_account_id  INTEGER NOT NULL REFERENCES parent_wechat_accounts(id) ON DELETE CASCADE,
            binding_id                INTEGER NOT NULL REFERENCES parent_student_bindings(id) ON DELETE CASCADE,
            class_id                  INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            student_id                INTEGER NOT NULL REFERENCES students(id),
            teacher_user_id           INTEGER NOT NULL REFERENCES users(id),
            image_url                 TEXT NOT NULL,
            child_raw_reason_text     TEXT NOT NULL DEFAULT '',
            child_reason_input_mode   TEXT NOT NULL DEFAULT 'text',
            child_reason_audio_url    TEXT NOT NULL DEFAULT '',
            topic_category            TEXT NOT NULL DEFAULT '未分类',
            status                    TEXT NOT NULL DEFAULT 'pending',
            ingestion_run_id          TEXT NOT NULL DEFAULT '',
            record_id                 TEXT NOT NULL DEFAULT '',
            error_message             TEXT NOT NULL DEFAULT '',
            retryable                 INTEGER NOT NULL DEFAULT 0,
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS wrong_question_practice_sheets (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id           INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            class_id                  INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            student_id                INTEGER NOT NULL REFERENCES students(id),
            teacher_user_id           INTEGER NOT NULL REFERENCES users(id),
            created_by                INTEGER NOT NULL REFERENCES users(id),
            student_name_snapshot     TEXT NOT NULL DEFAULT '',
            class_name_snapshot       TEXT NOT NULL DEFAULT '',
            teacher_name_snapshot     TEXT NOT NULL DEFAULT '',
            question_count            INTEGER NOT NULL DEFAULT 0,
            status                    TEXT NOT NULL DEFAULT 'pending',
            pdf_path                  TEXT NOT NULL DEFAULT '',
            generation_metadata_json  TEXT NOT NULL DEFAULT '{}',
            generation_error          TEXT NOT NULL DEFAULT '',
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS wrong_question_practice_sheet_items (
            id                            INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id                      INTEGER NOT NULL REFERENCES wrong_question_practice_sheets(id) ON DELETE CASCADE,
            question_order                INTEGER NOT NULL,
            wrong_question_record_id      TEXT NOT NULL DEFAULT '',
            source                        TEXT NOT NULL DEFAULT 'wechat_mp',
            is_geometry                   INTEGER NOT NULL DEFAULT 0,
            question_text_snapshot        TEXT NOT NULL DEFAULT '',
            image_url_snapshot            TEXT NOT NULL DEFAULT '',
            erased_image_url_snapshot     TEXT NOT NULL DEFAULT '',
            diagram_type_snapshot         TEXT NOT NULL DEFAULT '',
            diagram_spec_json_snapshot    TEXT NOT NULL DEFAULT '',
            child_reason_text_snapshot    TEXT NOT NULL DEFAULT '',
            child_reason_transcript_snapshot TEXT NOT NULL DEFAULT '',
            primary_error_type_snapshot   TEXT NOT NULL DEFAULT '',
            cause_note_snapshot           TEXT NOT NULL DEFAULT '',
            topic_category_snapshot       TEXT NOT NULL DEFAULT '',
            question_structured_snapshot_json TEXT NOT NULL DEFAULT '',
            knowledge_tags_snapshot_json  TEXT NOT NULL DEFAULT '[]',
            reflection_summary_snapshot_json TEXT NOT NULL DEFAULT '{}',
            ai_hint                       TEXT NOT NULL DEFAULT '',
            reason_blank_prompt           TEXT NOT NULL DEFAULT '',
            improvement_summary_prompt    TEXT NOT NULL DEFAULT '',
            structured_content_json       TEXT NOT NULL DEFAULT '{}',
            generation_metadata_json      TEXT NOT NULL DEFAULT '{}',
            created_at                    TEXT DEFAULT (datetime('now','localtime')),
            updated_at                    TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS wrong_question_practice_pack_jobs (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id           INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            class_id                  INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            created_by                INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            mode                      TEXT NOT NULL,
            target                    TEXT NOT NULL DEFAULT '',
            volume                    TEXT NOT NULL,
            requested_question_count  INTEGER NOT NULL DEFAULT 0,
            status                    TEXT NOT NULL DEFAULT 'pending',
            zip_path                  TEXT NOT NULL DEFAULT '',
            generation_error          TEXT NOT NULL DEFAULT '',
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS wrong_question_practice_pack_job_students (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id                    INTEGER NOT NULL REFERENCES wrong_question_practice_pack_jobs(id) ON DELETE CASCADE,
            student_id                INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            student_name_snapshot     TEXT NOT NULL DEFAULT '',
            status                    TEXT NOT NULL DEFAULT 'pending',
            requested_question_count  INTEGER NOT NULL DEFAULT 0,
            real_question_count       INTEGER NOT NULL DEFAULT 0,
            variant_question_count    INTEGER NOT NULL DEFAULT 0,
            pdf_path                  TEXT NOT NULL DEFAULT '',
            generation_error          TEXT NOT NULL DEFAULT '',
            created_at                TEXT DEFAULT (datetime('now','localtime')),
            updated_at                TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(job_id, student_id)
        );

        CREATE TABLE IF NOT EXISTS weekly_wrong_question_followup_messages (
            id                            INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id               INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            class_id                      INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            student_id                    INTEGER NOT NULL REFERENCES students(id),
            teacher_user_id               INTEGER REFERENCES users(id) ON DELETE SET NULL,
            week_start_date               TEXT NOT NULL,
            week_end_date                 TEXT NOT NULL,
            style                         TEXT NOT NULL DEFAULT 'warm',
            message_text                  TEXT NOT NULL DEFAULT '',
            source_record_ids_json        TEXT NOT NULL DEFAULT '[]',
            source_sheet_id               INTEGER DEFAULT NULL REFERENCES wrong_question_practice_sheets(id) ON DELETE SET NULL,
            generated_by                  INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at                    TEXT DEFAULT (datetime('now','localtime')),
            updated_at                    TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(organization_id, class_id, student_id, week_start_date, style)
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
            request_payload_hash TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_usage_ledger_org_request_id
        ON ai_usage_ledger (organization_id, request_id)
        WHERE request_id <> '';

        CREATE TABLE IF NOT EXISTS class_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            before_json TEXT NOT NULL DEFAULT '{}',
            after_json TEXT NOT NULL DEFAULT '{}',
            note TEXT NOT NULL DEFAULT '',
            actor_user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS student_class_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            before_json TEXT NOT NULL DEFAULT '{}',
            after_json TEXT NOT NULL DEFAULT '{}',
            note TEXT NOT NULL DEFAULT '',
            actor_user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS academic_year_promotion_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            academic_year_start INTEGER NOT NULL,
            job_type TEXT NOT NULL,
            effective_date TEXT NOT NULL,
            status TEXT NOT NULL,
            summary_json TEXT NOT NULL DEFAULT '{}',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(organization_id, academic_year_start, job_type)
        );
        """)
        import master_data

        master_data.ensure_schema(conn)
        _ensure_column(conn, "classes", "stage", "TEXT DEFAULT ''")
        _ensure_column(conn, "classes", "class_type", "TEXT DEFAULT 'group'")
        _ensure_column(conn, "classes", "current_grade", "TEXT DEFAULT ''")
        _ensure_column(conn, "classes", "class_number", "TEXT DEFAULT ''")
        _ensure_column(conn, "classes", "cohort_year", "INTEGER DEFAULT 0")
        _ensure_column(conn, "classes", "show_cohort_year", "INTEGER DEFAULT 1")
        _ensure_column(conn, "classes", "is_bridge", "INTEGER DEFAULT 0")
        _ensure_column(conn, "classes", "bridge_target", "TEXT DEFAULT ''")
        _ensure_column(conn, "classes", "content_track", "TEXT DEFAULT ''")
        _ensure_column(conn, "classes", "last_promoted_at", "TEXT DEFAULT ''")
        _ensure_column(conn, "classes", "lifecycle_status", "TEXT NOT NULL DEFAULT 'active'")
        _ensure_column(conn, "classes", "lifecycle_status_updated_at", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "organizations", "status", "TEXT NOT NULL DEFAULT 'active'")
        _ensure_column(conn, "organizations", "deleted_at", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "classes", "graduated_at", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "classes", "graduation_academic_year_start", "INTEGER NOT NULL DEFAULT 0")
        # Safe migration: add class_id if not already present
        cols = [r[1] for r in conn.execute("PRAGMA table_info(lessons)").fetchall()]
        if "class_id" not in cols:
            conn.execute("ALTER TABLE lessons ADD COLUMN class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL")

        old_feedback_tables = [
            "lesson_class_feedbacks",
            "class_feedback_tasks",
            "class_feedback_student_entries",
            "class_feedback_label_configs",
        ]
        old_feedback_tables.extend(
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'class_feedback_%'"
            ).fetchall()
        )
        for table_name in sorted(set(old_feedback_tables)):
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS class_commentary_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL REFERENCES organizations(id),
                class_id INTEGER NOT NULL REFERENCES classes(id),
                teacher_user_id INTEGER NOT NULL REFERENCES users(id),
                status TEXT NOT NULL DEFAULT 'uploaded',
                failure_stage TEXT NOT NULL DEFAULT '',
                audio_path TEXT NOT NULL DEFAULT '',
                audio_filename TEXT NOT NULL DEFAULT '',
                transcript_text TEXT NOT NULL DEFAULT '',
                raw_transcript_text TEXT NOT NULL DEFAULT '',
                roster_snapshot TEXT NOT NULL DEFAULT '',
                transcript_polish_error TEXT NOT NULL DEFAULT '',
                transcript_polished_at TEXT NOT NULL DEFAULT '',
                confirmed_transcript_text TEXT NOT NULL DEFAULT '',
                transcribed_at TEXT NOT NULL DEFAULT '',
                skill_id TEXT NOT NULL DEFAULT '',
                skill_name TEXT NOT NULL DEFAULT '',
                skill_path TEXT NOT NULL DEFAULT '',
                skill_content_snapshot TEXT NOT NULL DEFAULT '',
                feedback_text TEXT NOT NULL DEFAULT '',
                transcription_error TEXT NOT NULL DEFAULT '',
                generation_error TEXT NOT NULL DEFAULT '',
                transcription_request_key TEXT NOT NULL DEFAULT '',
                generation_request_key TEXT NOT NULL DEFAULT '',
                chat_provider TEXT NOT NULL DEFAULT '',
                chat_model TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                CHECK(status IN ('uploaded','transcribing','transcribed','generating','ready','failed')),
                CHECK(failure_stage IN ('','transcription','generation'))
            );

            CREATE INDEX IF NOT EXISTS idx_class_commentary_tasks_org_status
            ON class_commentary_tasks (organization_id, status, updated_at);

            CREATE INDEX IF NOT EXISTS idx_class_commentary_tasks_class
            ON class_commentary_tasks (class_id, updated_at);
            """
        )
        _ensure_column(conn, "class_commentary_tasks", "raw_transcript_text", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "class_commentary_tasks", "roster_snapshot", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "class_commentary_tasks", "transcript_polish_error", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "class_commentary_tasks", "transcript_polished_at", "TEXT NOT NULL DEFAULT ''")
        _ensure_class_commentary_evolution_schema(conn)
        from class_commentary_learning_graph import ensure_class_commentary_graph_schema

        ensure_class_commentary_graph_schema(conn)
        from curriculum_registry import ensure_curriculum_schema

        ensure_curriculum_schema(conn)
        _migrate_legacy_organization_scope(conn)
        _ensure_column(conn, "lessons", "created_by_user_id", "INTEGER NOT NULL DEFAULT 0")
        _ensure_review_plan_versions_schema(conn)
        _migrate_legacy_review_plan_columns(conn)
        _rebuild_lessons_without_review_plan_artifact_columns(conn)
        _bootstrap_account_state(conn)
        default_org = _ensure_organization(conn, DEFAULT_ORGANIZATION_NAME)
        _backfill_student_organization_scope(conn, default_org["id"])
        _ensure_column(conn, "wrong_question_submissions", "child_raw_reason_text", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "child_reason_transcript", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "child_reason_input_mode", "TEXT NOT NULL DEFAULT 'text'")
        _ensure_column(conn, "wrong_question_submissions", "primary_error_type", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "secondary_error_summary", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "child_reason_core_issue", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "child_reason_key_omission", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "child_reason_next_step", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "topic_category", "TEXT NOT NULL DEFAULT '未分类'")
        _ensure_column(conn, "wrong_question_submissions", "archive_status", "TEXT NOT NULL DEFAULT 'active'")
        _ensure_column(conn, "wrong_question_submissions", "archived_at", "TEXT DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "recognition_status", "TEXT NOT NULL DEFAULT 'pending'")
        _ensure_column(conn, "wrong_question_submissions", "is_geometry", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "wrong_question_submissions", "image_rotation_degrees", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "wrong_question_submissions", "question_text", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "question_text_edited", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "wrong_question_submissions", "question_text_source", "TEXT NOT NULL DEFAULT 'ai'")
        _ensure_column(conn, "wrong_question_submissions", "diagram_type", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "diagram_spec_json", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "recognition_error", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "student_library_pdf_path", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "ingestion_run_id", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "chat_session_id", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "question_structured_json", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "knowledge_tags_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "wrong_question_submissions", "reflection_summary_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "wrong_question_submissions", "generation_metadata_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "wrong_question_submissions", "mastery_tracking_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "wrong_question_submissions", "needs_teacher_confirmation", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "wrong_question_submissions", "confirmation_reasons_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "wrong_question_submissions", "confirmation_status", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "confirmation_reviewed_by", "INTEGER")
        _ensure_column(conn, "wrong_question_submissions", "confirmation_reviewed_at", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_ingestion_runs", "current_step", "TEXT NOT NULL DEFAULT 'uploaded'")
        _ensure_column(conn, "wrong_question_practice_sheets", "source_record_ids_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "wrong_question_practice_sheets", "generation_metadata_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "wrong_question_practice_sheet_items", "diagram_type_snapshot", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_practice_sheet_items", "erased_image_url_snapshot", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_practice_sheet_items", "diagram_spec_json_snapshot", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_practice_sheet_items", "child_reason_transcript_snapshot", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_practice_sheet_items", "topic_category_snapshot", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_practice_sheet_items", "question_structured_snapshot_json", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_practice_sheet_items", "knowledge_tags_snapshot_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "wrong_question_practice_sheet_items", "reflection_summary_snapshot_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "wrong_question_practice_sheet_items", "structured_content_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "wrong_question_practice_sheet_items", "generation_metadata_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "weekly_wrong_question_followup_messages", "source_sheet_id", "INTEGER DEFAULT NULL")
        _ensure_column(conn, "wechat_wrong_question_upload_tasks", "topic_category", "TEXT NOT NULL DEFAULT '未分类'")
        _ensure_column(conn, "wechat_wrong_question_upload_tasks", "ingestion_run_id", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wechat_wrong_question_upload_tasks", "retryable", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "course_calendar_schedules", "start_offset_minutes", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "course_calendar_custom_items", "note", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "course_calendar_custom_items", "visibility", "TEXT NOT NULL DEFAULT 'private'")
        _ensure_column(conn, "course_calendar_custom_schedules", "start_offset_minutes", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "students", "source", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "students", "parent_contact", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "students", "status", "TEXT NOT NULL DEFAULT 'active'")
        _ensure_column(conn, "students", "archived_at", "TEXT NOT NULL DEFAULT ''")
        _ensure_weekly_wrong_question_followup_messages_user_delete_policy(conn)
        _migrate_course_calendar_time_blocks(conn)
        _rebuild_wrong_question_submissions_without_legacy_feedback_columns(conn)
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_students_organization_name
            ON students (organization_id, name);

            CREATE INDEX IF NOT EXISTS idx_classes_organization_grade_subject_name
            ON classes (organization_id, grade, subject, name);

            CREATE INDEX IF NOT EXISTS idx_lessons_organization_class_date
            ON lessons (organization_id, class_id, date);

            CREATE INDEX IF NOT EXISTS idx_student_accounts_student
            ON student_accounts (student_id);

            CREATE INDEX IF NOT EXISTS idx_student_accounts_username_lower
            ON student_accounts (lower(username));

            CREATE INDEX IF NOT EXISTS idx_student_auth_sessions_account
            ON student_auth_sessions (account_id, created_at);

            CREATE INDEX IF NOT EXISTS idx_course_calendar_schedules_org_date
            ON course_calendar_schedules (organization_id, date, time_block);

            CREATE INDEX IF NOT EXISTS idx_consultations_organization_assigned_updated
            ON consultations (organization_id, assigned_user_id, updated_at);

            CREATE INDEX IF NOT EXISTS idx_wrong_question_submissions_organization_class_teacher_status
            ON wrong_question_submissions (organization_id, class_id, teacher_user_id, status);

            CREATE INDEX IF NOT EXISTS idx_wrong_question_submissions_weekly_followup
            ON wrong_question_submissions (
                organization_id, class_id, source, recognition_status, archive_status, created_at, student_id
            );

            CREATE INDEX IF NOT EXISTS idx_wrong_question_ingestion_runs_lookup
            ON wrong_question_ingestion_runs (organization_id, source, status, created_at);

            CREATE INDEX IF NOT EXISTS idx_wrong_question_assets_run_role
            ON wrong_question_assets (ingestion_run_id, asset_role, page_number, id);

            CREATE INDEX IF NOT EXISTS idx_wrong_question_chat_sessions_lookup
            ON wrong_question_chat_sessions (organization_id, class_id, student_id, status, updated_at);

            CREATE INDEX IF NOT EXISTS idx_wrong_question_chat_messages_session
            ON wrong_question_chat_messages (session_id, id);

            CREATE INDEX IF NOT EXISTS idx_wechat_wrong_question_upload_tasks_parent_status
            ON wechat_wrong_question_upload_tasks (parent_wechat_account_id, status, created_at);

            CREATE INDEX IF NOT EXISTS idx_wrong_question_practice_sheets_student_created
            ON wrong_question_practice_sheets (student_id, created_at, id);

            CREATE INDEX IF NOT EXISTS idx_wrong_question_practice_sheet_items_sheet_order
            ON wrong_question_practice_sheet_items (sheet_id, question_order, id);

            CREATE INDEX IF NOT EXISTS idx_wrong_question_practice_pack_jobs_lookup
            ON wrong_question_practice_pack_jobs (
                organization_id,
                class_id,
                created_by,
                mode,
                target,
                volume,
                status,
                id
            );

            CREATE INDEX IF NOT EXISTS idx_wrong_question_practice_pack_students_job
            ON wrong_question_practice_pack_job_students (job_id, student_id);

            CREATE INDEX IF NOT EXISTS idx_weekly_followup_messages_class_week
            ON weekly_wrong_question_followup_messages (organization_id, class_id, week_start_date);
            """
        )
        user_cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "last_login" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN last_login TEXT DEFAULT NULL")
        if "visible_pages_json" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN visible_pages_json TEXT DEFAULT NULL")
        if "avatar_source" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_source TEXT NOT NULL DEFAULT 'dicebear'")
        if "avatar_seed" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_seed TEXT NOT NULL DEFAULT ''")
        if "avatar_upload_path" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_upload_path TEXT NOT NULL DEFAULT ''")
        if "recovery_phone" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN recovery_phone TEXT NOT NULL DEFAULT ''")
        if "security_question" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN security_question TEXT NOT NULL DEFAULT ''")
        if "security_answer_hash" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN security_answer_hash TEXT NOT NULL DEFAULT ''")
        if "initial_class_claim_completed" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN initial_class_claim_completed INTEGER NOT NULL DEFAULT 0")
            conn.execute(
                """
                UPDATE users
                SET initial_class_claim_completed=1
                WHERE role!=? OR last_login IS NOT NULL
                """,
                (MEMBER_ROLE,),
            )
        registration_request_cols = [r[1] for r in conn.execute("PRAGMA table_info(registration_requests)").fetchall()]
        if "recovery_phone" not in registration_request_cols:
            conn.execute("ALTER TABLE registration_requests ADD COLUMN recovery_phone TEXT NOT NULL DEFAULT ''")
        if "security_question" not in registration_request_cols:
            conn.execute("ALTER TABLE registration_requests ADD COLUMN security_question TEXT NOT NULL DEFAULT ''")
        if "security_answer_hash" not in registration_request_cols:
            conn.execute("ALTER TABLE registration_requests ADD COLUMN security_answer_hash TEXT NOT NULL DEFAULT ''")
        organization_request_cols = [r[1] for r in conn.execute("PRAGMA table_info(organization_requests)").fetchall()]
        if "recovery_phone" not in organization_request_cols:
            conn.execute("ALTER TABLE organization_requests ADD COLUMN recovery_phone TEXT NOT NULL DEFAULT ''")
        if "security_question" not in organization_request_cols:
            conn.execute("ALTER TABLE organization_requests ADD COLUMN security_question TEXT NOT NULL DEFAULT ''")
        if "security_answer_hash" not in organization_request_cols:
            conn.execute("ALTER TABLE organization_requests ADD COLUMN security_answer_hash TEXT NOT NULL DEFAULT ''")
        _drop_legacy_table_if_exists(conn, "questions")
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


def _active_credit_hold_total_conn(
    conn: sqlite3.Connection,
    organization_id: int,
) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM class_commentary_student_generation_credit_holds
        WHERE organization_id=? AND status='active'
        """,
        (int(organization_id),),
    ).fetchone()
    return int(row["total"] or 0)


def get_active_credit_hold_total(organization_id: int) -> int:
    with get_conn() as conn:
        _ensure_credit_account_row(conn, organization_id)
        return _active_credit_hold_total_conn(conn, organization_id)


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
        available_before = balance_before - _active_credit_hold_total_conn(
            conn,
            organization_id,
        )
        if available_before < amount:
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
        conn.execute("BEGIN IMMEDIATE")
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
    request_payload_hash: str = "",
    token_cost_raw: float = 0.0,
) -> dict:
    _ensure_credit_account_row(conn, organization_id)
    _ensure_user_in_organization(conn, user_id, organization_id, "usage")

    total_tokens = max(0, int(input_tokens)) + max(0, int(output_tokens))
    normalized_request_id = (request_id or "").strip()
    normalized_payload_hash = str(request_payload_hash or "").strip()
    cur = conn.execute(
        """
        INSERT INTO ai_usage_ledger
            (organization_id, user_id, feature_key, provider, model, input_tokens, output_tokens, total_tokens,
             token_cost_raw, credit_cost_final, source_record_type, source_record_id,
             request_id, request_payload_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            normalized_payload_hash,
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
    request_payload_hash: str = "",
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
            request_payload_hash=request_payload_hash,
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
    request_payload_hash: str = "",
    token_cost_raw: float = 0.0,
    credit_hold_student_run_id: Optional[int] = None,
) -> dict:
    normalized_request_id = (request_id or "").strip()
    normalized_payload_hash = str(request_payload_hash or "").strip()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _ensure_credit_account_row(conn, organization_id)
        _ensure_user_in_organization(conn, user_id, organization_id, "usage")
        credit_hold = None
        if credit_hold_student_run_id is not None:
            credit_hold = conn.execute(
                """
                SELECT hold.*, run.charge_request_key
                FROM class_commentary_student_generation_credit_holds AS hold
                JOIN class_commentary_student_generation_runs AS run
                  ON run.id=hold.student_run_id
                WHERE hold.student_run_id=?
                """,
                (int(credit_hold_student_run_id),),
            ).fetchone()
            if (
                not credit_hold
                or int(credit_hold["organization_id"] or 0) != int(organization_id)
                or str(credit_hold["request_id"] or "") != normalized_request_id
                or str(credit_hold["charge_request_key"] or "")
                != normalized_request_id
                or str(source_record_type or "")
                != "class_commentary_student_generation_run"
                or str(source_record_id) != str(int(credit_hold_student_run_id))
            ):
                raise ValueError("student generation credit hold scope mismatch")

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
                if (
                    normalized_payload_hash
                    and str(existing["request_payload_hash"] or "")
                    != normalized_payload_hash
                ):
                    raise AiUsageRequestConflict(
                        "ai usage request_id was already used with a different payload"
                    )
                if credit_hold is not None and (
                    str(credit_hold["status"] or "") != "settled"
                    or int(credit_hold["usage_id"] or 0) != int(existing["id"])
                ):
                    raise ValueError("student generation credit hold settlement mismatch")
                return dict(existing)

        if credit_hold is not None:
            if str(credit_hold["status"] or "") != "active":
                raise ValueError("student generation credit hold is not active")
            if int(credit_hold["amount"] or 0) < int(credit_cost_final):
                raise ValueError("student generation credit hold is insufficient")

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
                request_payload_hash=normalized_payload_hash,
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
            if (
                normalized_payload_hash
                and str(existing["request_payload_hash"] or "")
                != normalized_payload_hash
            ):
                raise AiUsageRequestConflict(
                    "ai usage request_id was already used with a different payload"
                )
            if credit_hold is not None and (
                str(credit_hold["status"] or "") != "settled"
                or int(credit_hold["usage_id"] or 0) != int(existing["id"])
            ):
                raise ValueError("student generation credit hold settlement mismatch")
            return dict(existing)

        if credit_hold is not None:
            settled = conn.execute(
                """
                UPDATE class_commentary_student_generation_credit_holds
                SET status='settled', usage_id=?,
                    settled_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                    released_at=NULL
                WHERE student_run_id=? AND status='active' AND usage_id IS NULL
                """,
                (int(usage_row["id"]), int(credit_hold_student_run_id)),
            )
            if settled.rowcount != 1:
                raise ValueError("student generation credit hold settlement conflict")

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
    return [_class_row_to_dict(row) for row in rows]


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _requires_initial_class_claim(row) -> bool:
    if not row:
        return False
    keys = row.keys() if hasattr(row, "keys") else []
    if row["role"] != MEMBER_ROLE:
        return False
    if "initial_class_claim_completed" in keys and int(row["initial_class_claim_completed"] or 0):
        return False
    with get_conn() as conn:
        own_class = conn.execute(
            "SELECT 1 FROM user_classes WHERE user_id=? LIMIT 1",
            (row["id"],),
        ).fetchone()
        if own_class:
            return False
        unbound_class = conn.execute(
            """
            SELECT 1
            FROM classes c
            WHERE c.organization_id=?
              AND NOT EXISTS (
                  SELECT 1 FROM user_classes uc WHERE uc.class_id=c.id
              )
            LIMIT 1
            """,
            (row["organization_id"],),
        ).fetchone()
    return unbound_class is not None


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
        "visible_pages": _load_visible_pages_for_user(row),
        "avatar_source": row["avatar_source"] if "avatar_source" in keys else "dicebear",
        "avatar_seed": row["avatar_seed"] if "avatar_seed" in keys else "",
        "avatar_upload_url": (
            f"/api/profile-avatar-files/{row['avatar_upload_path']}"
            if "avatar_upload_path" in keys and str(row["avatar_upload_path"] or "").strip()
            else ""
        ),
        "requires_class_claim": _requires_initial_class_claim(row),
    }


def _class_names_from_csv(value: object) -> list[str]:
    return [
        class_name.strip()
        for class_name in str(value or "").split(",")
        if class_name.strip()
    ]


def _public_student_account_dict(row):
    if not row:
        return None
    keys = row.keys() if hasattr(row, "keys") else []
    return {
        "id": int(row["id"]),
        "username": row["username"],
        "status": row["status"],
        "organization_id": int(row["organization_id"]),
        "organization_name": row["organization_name"] if "organization_name" in keys else "",
        "student": {
            "id": int(row["student_id"]),
            "name": row["student_name"] if "student_name" in keys else "",
            "organization_id": int(row["student_organization_id"] if "student_organization_id" in keys else row["organization_id"]),
            "class_names": _class_names_from_csv(row["class_names"] if "class_names" in keys else ""),
            "class_count": int(row["class_count"] if "class_count" in keys and row["class_count"] is not None else 0),
        },
        "created_at": row["created_at"],
        "last_login": row["last_login"] if "last_login" in keys else None,
    }


def _student_account_select_sql(where_sql: str) -> str:
    return f"""
        SELECT
            sa.*,
            o.name AS organization_name,
            s.name AS student_name,
            s.organization_id AS student_organization_id,
            GROUP_CONCAT(DISTINCT c.name) AS class_names,
            COUNT(DISTINCT c.id) AS class_count
        FROM student_accounts sa
        JOIN organizations o ON o.id=sa.organization_id
        JOIN students s ON s.id=sa.student_id
        LEFT JOIN class_students cs ON cs.student_id=s.id
        LEFT JOIN classes c ON c.id=cs.class_id
        WHERE {where_sql}
        GROUP BY sa.id
        LIMIT 1
    """


def _fetch_student_account_row_by_id(conn: sqlite3.Connection, account_id: int):
    return conn.execute(
        _student_account_select_sql("sa.id=?"),
        (account_id,),
    ).fetchone()


def _fetch_student_account_row_by_username(conn: sqlite3.Connection, username: str):
    normalized_username = _normalize_username(username)
    return conn.execute(
        _student_account_select_sql("lower(sa.username)=lower(?)"),
        (normalized_username,),
    ).fetchone()


def _get_active_class_invite_by_code_row(conn: sqlite3.Connection, invite_code: str):
    normalized_code = (invite_code or "").strip()
    return conn.execute(
        """
        SELECT
            i.*,
            c.name AS class_name,
            c.subject AS class_subject,
            c.grade AS class_grade
        FROM class_invite_codes i
        JOIN classes c ON c.id=i.class_id
        WHERE upper(i.invite_code)=upper(?) AND i.status='active'
        ORDER BY i.id DESC
        LIMIT 1
        """,
        (normalized_code,),
    ).fetchone()


def get_active_class_invite_by_code(invite_code: str) -> Optional[dict]:
    with get_conn() as conn:
        row = _get_active_class_invite_by_code_row(conn, invite_code)
    return dict(row) if row else None


def preview_student_class_invite(invite_code: str) -> Optional[dict]:
    with get_conn() as conn:
        invite = _get_active_class_invite_by_code_row(conn, invite_code)
        if not invite:
            return None
        students = conn.execute(
            """
            SELECT s.*
            FROM class_students cs
            JOIN students s ON s.id=cs.student_id
            WHERE cs.class_id=?
            ORDER BY cs.id
            """,
            (invite["class_id"],),
        ).fetchall()
    return {
        "class": {
            "id": int(invite["class_id"]),
            "name": invite["class_name"],
            "subject": invite["class_subject"] or "",
            "grade": invite["class_grade"] or "",
            "organization_id": int(invite["organization_id"]),
        },
        "students": [dict(row) for row in students],
    }


def create_student_account_by_invite(
    *,
    invite_code: str,
    student_id: int,
    username: str,
    password: str,
) -> dict:
    normalized_username = _normalize_username(username)
    if not normalized_username:
        raise ValueError("username required")
    if len(password or "") < 6:
        raise ValueError("password too short")

    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        invite = _get_active_class_invite_by_code_row(conn, invite_code)
        if not invite:
            raise LookupError("invite not found")
        student_row = conn.execute(
            """
            SELECT s.*
            FROM class_students cs
            JOIN students s ON s.id=cs.student_id
            WHERE cs.class_id=? AND s.id=?
            LIMIT 1
            """,
            (invite["class_id"], int(student_id)),
        ).fetchone()
        if not student_row:
            raise LookupError("student not found")
        if _fetch_student_account_row_by_username(conn, normalized_username):
            raise ValueError("username exists")
        existing_student_account = conn.execute(
            "SELECT 1 FROM student_accounts WHERE student_id=? LIMIT 1",
            (int(student_id),),
        ).fetchone()
        if existing_student_account:
            raise ValueError("student account exists")
        cur = conn.execute(
            """
            INSERT INTO student_accounts (
                organization_id, student_id, username, password_hash, status
            ) VALUES (?, ?, ?, ?, 'active')
            """,
            (
                int(invite["organization_id"]),
                int(student_id),
                normalized_username,
                hash_password(password),
            ),
        )
        account_row = _fetch_student_account_row_by_id(conn, cur.lastrowid)
    return _public_student_account_dict(account_row)


def authenticate_student_account(username: str, password: str):
    normalized_username = _normalize_username(username)
    with get_conn() as conn:
        row = _fetch_student_account_row_by_username(conn, normalized_username)
        if not row:
            return None, "username or password incorrect"
        if row["status"] != "active":
            return None, "account disabled"
        if row["password_hash"] != hash_password(password):
            return None, "username or password incorrect"
        conn.execute(
            "UPDATE student_accounts SET last_login=datetime('now','localtime') WHERE id=?",
            (row["id"],),
        )
        row = _fetch_student_account_row_by_id(conn, row["id"])
    return _public_student_account_dict(row), None


def create_student_auth_session(account_id: int) -> str:
    token = secrets.token_hex(32)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO student_auth_sessions (token, account_id) VALUES (?, ?)",
            (token, int(account_id)),
        )
        conn.execute(
            """
            DELETE FROM student_auth_sessions
            WHERE account_id=? AND token NOT IN (
                SELECT token FROM student_auth_sessions
                WHERE account_id=?
                ORDER BY created_at DESC, token DESC
                LIMIT 10
            )
            """,
            (int(account_id), int(account_id)),
        )
    return token


def get_current_student_account(token: str):
    if not token:
        return None
    with get_conn() as conn:
        session = conn.execute(
            "SELECT account_id FROM student_auth_sessions WHERE token=?",
            (token,),
        ).fetchone()
        if not session:
            return None
        row = _fetch_student_account_row_by_id(conn, session["account_id"])
    return _public_student_account_dict(row)


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


REVIEW_PLAN_ACTIVE_STATUSES = {"pending", "queued", "processing", "transcribing", "generating"}
REVIEW_PLAN_READY_STATUS = "ready"
REVIEW_PLAN_FAILED_STATUS = "failed"
REVIEW_PLAN_FAILURE_NOTIFICATION_EVENT = "failed"
REVIEW_PLAN_LEGACY_ARTIFACT_COLUMNS = {
    "plan_json",
    "pdf_path",
    "record_status",
    "generation_error",
    "review_audio_path",
    "review_audio_request_key",
    "review_request_key",
    "review_request_id",
    "review_chat_provider",
    "review_chat_model",
    "review_same_lesson_materials_json",
}


def _review_plan_version_from_row(row) -> Optional[dict]:
    if not row:
        return None
    version = dict(row)
    try:
        version["plan"] = json.loads(version.get("plan_json") or "{}")
    except json.JSONDecodeError:
        version["plan"] = {}
    try:
        materials = json.loads(version.get("same_lesson_materials_json") or "[]")
    except json.JSONDecodeError:
        materials = []
    version["same_lesson_materials"] = materials if isinstance(materials, list) else []
    try:
        raw_options = json.loads(version.get("generation_options_json") or "{}")
        options_source = str((raw_options if isinstance(raw_options, dict) else {}).get("source") or "create")
        generation_options = normalize_generation_options(raw_options, source=options_source)
    except (TypeError, ValueError, json.JSONDecodeError):
        generation_options = normalize_generation_options(None)
    version["generation_options"] = generation_options
    version["generation_summary"] = generation_options_summary(generation_options)
    version["source_text"] = str(version.get("source_text") or "")
    version["cleaned_source_text"] = str(version.get("cleaned_source_text") or "")
    version["source_text_hash"] = str(version.get("source_text_hash") or "")
    version["source_brief"] = _load_review_plan_source_brief(version.get("source_brief_json"))
    version["source_pack"] = _load_review_plan_source_pack(version.get("source_pack_json"))
    return version


def _load_review_plan_generation_options(value: object | None) -> dict:
    try:
        raw_options = json.loads(str(value or "{}"))
        options_source = str((raw_options if isinstance(raw_options, dict) else {}).get("source") or "create")
        return normalize_generation_options(raw_options, source=options_source)
    except (TypeError, ValueError, json.JSONDecodeError):
        return normalize_generation_options(None)


def _review_plan_version_summary_from_row(row) -> Optional[dict]:
    if not row:
        return None
    version = dict(row)
    version["generation_options"] = _load_review_plan_generation_options(version.get("generation_options_json"))
    version["generation_summary"] = generation_options_summary(version["generation_options"])
    return version


def _lesson_columns(conn: sqlite3.Connection) -> set[str]:
    return {row["name"] for row in conn.execute("PRAGMA table_info(lessons)").fetchall()}


def _review_plan_version_columns(conn: sqlite3.Connection) -> set[str]:
    return {row["name"] for row in conn.execute("PRAGMA table_info(review_plan_versions)").fetchall()}


def _column_expr(columns: set[str], column: str, fallback_sql: str) -> str:
    return column if column in columns else fallback_sql


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _dump_review_plan_materials(value: Optional[list[str]]) -> str:
    try:
        return json.dumps(value or [], ensure_ascii=False)
    except TypeError:
        return "[]"


def _dump_generation_options(value: object | None, *, source: str = "create") -> str:
    try:
        options = normalize_generation_options(value, source=source)
    except ValueError:
        options = normalize_generation_options(None, source=source)
    return json.dumps(options, ensure_ascii=False)


def _dump_review_plan_source_brief(value: object | None) -> str:
    return _dump_review_plan_run_json(value, {})


def _load_review_plan_source_brief(value: object | None) -> dict:
    payload = _load_review_plan_run_json(value, {})
    return payload if isinstance(payload, dict) else {}


def _dump_review_plan_source_pack(value: object | None) -> str:
    return _dump_review_plan_run_json(value, {})


def _load_review_plan_source_pack(value: object | None) -> dict:
    payload = _load_review_plan_run_json(value, {})
    return payload if isinstance(payload, dict) else {}


def _ensure_review_plan_failure_notification_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS review_plan_notification_events (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            review_plan_version_id INTEGER NOT NULL REFERENCES review_plan_versions(id) ON DELETE CASCADE,
            event_type             TEXT NOT NULL,
            created_at             TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(review_plan_version_id, event_type)
        );

        CREATE TABLE IF NOT EXISTS review_plan_notification_receipts (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id                INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            review_plan_version_id INTEGER NOT NULL REFERENCES review_plan_versions(id) ON DELETE CASCADE,
            event_type             TEXT NOT NULL,
            seen_at                TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(user_id, review_plan_version_id, event_type)
        );

        CREATE INDEX IF NOT EXISTS idx_review_plan_notification_events_created
        ON review_plan_notification_events(event_type, created_at, id);

        CREATE INDEX IF NOT EXISTS idx_review_plan_notification_receipts_user
        ON review_plan_notification_receipts(user_id, event_type, review_plan_version_id);

        CREATE TRIGGER IF NOT EXISTS trg_review_plan_failed_notification_insert
        AFTER INSERT ON review_plan_versions
        WHEN NEW.status='failed'
        BEGIN
            INSERT OR IGNORE INTO review_plan_notification_events (review_plan_version_id, event_type)
            VALUES (NEW.id, 'failed');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_review_plan_failed_notification_update
        AFTER UPDATE OF status ON review_plan_versions
        WHEN NEW.status='failed' AND OLD.status<>'failed'
        BEGIN
            INSERT OR IGNORE INTO review_plan_notification_events (review_plan_version_id, event_type)
            VALUES (NEW.id, 'failed');
        END;
        """
    )


def _ensure_review_plan_versions_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS review_plan_versions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id        INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
            version_no       INTEGER NOT NULL,
            status           TEXT NOT NULL DEFAULT 'pending',
            plan_json        TEXT NOT NULL DEFAULT '',
            pdf_path         TEXT NOT NULL DEFAULT '',
            generation_error TEXT NOT NULL DEFAULT '',
            audio_path       TEXT NOT NULL DEFAULT '',
            audio_request_key TEXT NOT NULL DEFAULT '',
            request_key      TEXT NOT NULL DEFAULT '',
            request_id       TEXT NOT NULL DEFAULT '',
            chat_provider    TEXT NOT NULL DEFAULT '',
            chat_model       TEXT NOT NULL DEFAULT '',
            source_text      TEXT NOT NULL DEFAULT '',
            cleaned_source_text TEXT NOT NULL DEFAULT '',
            source_text_hash TEXT NOT NULL DEFAULT '',
            source_brief_json TEXT NOT NULL DEFAULT '{}',
            source_pack_json TEXT NOT NULL DEFAULT '{}',
            same_lesson_materials_json TEXT NOT NULL DEFAULT '[]',
            generation_options_json TEXT NOT NULL DEFAULT '{}',
            created_by_user_id INTEGER NOT NULL DEFAULT 0,
            completed_at     TEXT NOT NULL DEFAULT '',
            created_at       TEXT DEFAULT (datetime('now','localtime')),
            updated_at       TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(lesson_id, version_no)
        )
        """
    )
    _ensure_column(conn, "lessons", "current_review_plan_version_id", "INTEGER DEFAULT NULL")
    _ensure_column(conn, "lessons", "created_by_user_id", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "lessons", "updated_at", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "status", "TEXT NOT NULL DEFAULT 'pending'")
    _ensure_column(conn, "review_plan_versions", "plan_json", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "pdf_path", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "generation_error", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "audio_path", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "audio_request_key", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "request_key", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "request_id", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "chat_provider", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "chat_model", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "source_text", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "cleaned_source_text", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "source_text_hash", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "source_brief_json", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "review_plan_versions", "source_pack_json", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "review_plan_versions", "same_lesson_materials_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(conn, "review_plan_versions", "generation_options_json", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "review_plan_versions", "created_by_user_id", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "review_plan_versions", "completed_at", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "created_at", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "review_plan_versions", "updated_at", "TEXT NOT NULL DEFAULT ''")
    if _table_exists(conn, "review_plan_runs"):
        _ensure_column(conn, "review_plan_runs", "version_id", "INTEGER DEFAULT NULL")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_review_plan_runs_version_updated
            ON review_plan_runs(version_id, updated_at)
            """
        )
    _migrate_review_plan_generated_at_column(conn)
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_review_plan_versions_lesson_created
        ON review_plan_versions(lesson_id, created_at, id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_review_plan_versions_lesson_status_updated
        ON review_plan_versions(lesson_id, status, updated_at, id)
        """
    )
    conn.execute(
        """
        UPDATE review_plan_versions
        SET status='interrupted', updated_at=datetime('now','localtime')
        WHERE status IN ('pending', 'queued', 'processing', 'transcribing', 'generating')
          AND id NOT IN (
              SELECT MAX(id)
              FROM review_plan_versions
              WHERE status IN ('pending', 'queued', 'processing', 'transcribing', 'generating')
              GROUP BY lesson_id
          )
        """
    )
    conn.execute("DROP INDEX IF EXISTS idx_review_plan_versions_active")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_review_plan_versions_one_active
        ON review_plan_versions(lesson_id)
        WHERE status IN ('pending', 'queued', 'processing', 'transcribing', 'generating')
        """
    )
    _ensure_review_plan_failure_notification_schema(conn)


def list_unseen_review_plan_failure_notifications(user_id: int, limit: int = 100) -> list[dict]:
    safe_limit = max(1, min(500, int(limit or 100)))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT e.review_plan_version_id AS version_id,
                   e.created_at AS notification_created_at,
                   v.lesson_id,
                   v.version_no,
                   v.generation_error,
                   v.updated_at AS failed_at
            FROM review_plan_notification_events e
            JOIN review_plan_versions v ON v.id = e.review_plan_version_id
            LEFT JOIN review_plan_notification_receipts r
              ON r.user_id=?
             AND r.review_plan_version_id=e.review_plan_version_id
             AND r.event_type=e.event_type
            WHERE e.event_type=?
              AND v.status=?
              AND r.id IS NULL
            ORDER BY e.id DESC
            LIMIT ?
            """,
            (
                int(user_id),
                REVIEW_PLAN_FAILURE_NOTIFICATION_EVENT,
                REVIEW_PLAN_FAILED_STATUS,
                safe_limit,
            ),
        ).fetchall()
        return [dict(row) for row in rows]


def mark_review_plan_failure_notifications_seen(user_id: int, version_ids: list[int]) -> list[int]:
    normalized_version_ids = sorted({int(version_id) for version_id in version_ids if int(version_id or 0) > 0})
    if not normalized_version_ids:
        return []
    placeholders = ",".join("?" for _ in normalized_version_ids)
    with get_conn() as conn:
        user = conn.execute("SELECT id FROM users WHERE id=?", (int(user_id),)).fetchone()
        if not user:
            raise LookupError("user not found")
        rows = conn.execute(
            f"""
            SELECT e.review_plan_version_id
            FROM review_plan_notification_events e
            JOIN review_plan_versions v ON v.id=e.review_plan_version_id
            WHERE e.event_type=?
              AND v.status=?
              AND e.review_plan_version_id IN ({placeholders})
            ORDER BY e.review_plan_version_id
            """,
            [
                REVIEW_PLAN_FAILURE_NOTIFICATION_EVENT,
                REVIEW_PLAN_FAILED_STATUS,
                *normalized_version_ids,
            ],
        ).fetchall()
        eligible_version_ids = [int(row["review_plan_version_id"]) for row in rows]
        conn.executemany(
            """
            INSERT OR IGNORE INTO review_plan_notification_receipts (
                user_id,
                review_plan_version_id,
                event_type
            )
            VALUES (?, ?, ?)
            """,
            [
                (int(user_id), version_id, REVIEW_PLAN_FAILURE_NOTIFICATION_EVENT)
                for version_id in eligible_version_ids
            ],
        )
        return eligible_version_ids


def _migrate_review_plan_generated_at_column(conn: sqlite3.Connection) -> None:
    columns = _review_plan_version_columns(conn)
    if "generated_at" not in columns:
        return
    conn.execute(
        """
        UPDATE review_plan_versions
        SET completed_at=generated_at
        WHERE COALESCE(completed_at, '') = ''
          AND COALESCE(generated_at, '') <> ''
        """
    )
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS review_plan_versions__completed_at_rebuild")
        conn.execute(
            """
            CREATE TABLE review_plan_versions__completed_at_rebuild (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id        INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                version_no       INTEGER NOT NULL,
                status           TEXT NOT NULL DEFAULT 'pending',
                plan_json        TEXT NOT NULL DEFAULT '',
                pdf_path         TEXT NOT NULL DEFAULT '',
                generation_error TEXT NOT NULL DEFAULT '',
                audio_path       TEXT NOT NULL DEFAULT '',
                audio_request_key TEXT NOT NULL DEFAULT '',
                request_key      TEXT NOT NULL DEFAULT '',
                request_id       TEXT NOT NULL DEFAULT '',
                chat_provider    TEXT NOT NULL DEFAULT '',
                chat_model       TEXT NOT NULL DEFAULT '',
                source_text      TEXT NOT NULL DEFAULT '',
                cleaned_source_text TEXT NOT NULL DEFAULT '',
                source_text_hash TEXT NOT NULL DEFAULT '',
                source_brief_json TEXT NOT NULL DEFAULT '{}',
                source_pack_json TEXT NOT NULL DEFAULT '{}',
                same_lesson_materials_json TEXT NOT NULL DEFAULT '[]',
                generation_options_json TEXT NOT NULL DEFAULT '{}',
                created_by_user_id INTEGER NOT NULL DEFAULT 0,
                completed_at     TEXT NOT NULL DEFAULT '',
                created_at       TEXT DEFAULT (datetime('now','localtime')),
                updated_at       TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(lesson_id, version_no)
            )
            """
        )
        copy_columns = [
            "id",
            "lesson_id",
            "version_no",
            "status",
            "plan_json",
            "pdf_path",
            "generation_error",
            "audio_path",
            "audio_request_key",
            "request_key",
            "request_id",
            "chat_provider",
            "chat_model",
            "source_text",
            "cleaned_source_text",
            "source_text_hash",
            "source_brief_json",
            "source_pack_json",
            "same_lesson_materials_json",
            "generation_options_json",
            "created_by_user_id",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        source_columns = _review_plan_version_columns(conn)
        column_fallbacks = {
            "id": "NULL",
            "lesson_id": "0",
            "version_no": "1",
            "status": "'pending'",
            "source_text": "''",
            "cleaned_source_text": "''",
            "source_text_hash": "''",
            "source_brief_json": "'{}'",
            "source_pack_json": "'{}'",
            "same_lesson_materials_json": "'[]'",
            "generation_options_json": "'{}'",
            "created_by_user_id": "0",
            "completed_at": "''",
            "created_at": "datetime('now','localtime')",
            "updated_at": "datetime('now','localtime')",
        }
        select_exprs = [
            _column_expr(source_columns, column, column_fallbacks.get(column, "''"))
            for column in copy_columns
        ]
        conn.execute(
            f"""
            INSERT INTO review_plan_versions__completed_at_rebuild ({", ".join(copy_columns)})
            SELECT {", ".join(select_exprs)}
            FROM review_plan_versions
            """
        )
        conn.execute("DROP TABLE review_plan_versions")
        conn.execute("ALTER TABLE review_plan_versions__completed_at_rebuild RENAME TO review_plan_versions")
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_legacy_review_plan_columns(conn: sqlite3.Connection) -> None:
    columns = _lesson_columns(conn)
    if not (columns & REVIEW_PLAN_LEGACY_ARTIFACT_COLUMNS):
        return
    _ensure_review_plan_versions_schema(conn)
    record_status_expr = _column_expr(columns, "record_status", "'ready'")
    rows = conn.execute(
        f"""
        SELECT
            id AS lesson_id,
            {_column_expr(columns, "plan_json", "''")} AS plan_json,
            {_column_expr(columns, "pdf_path", "''")} AS pdf_path,
            {record_status_expr} AS record_status,
            {_column_expr(columns, "generation_error", "''")} AS generation_error,
            {_column_expr(columns, "review_audio_path", "''")} AS audio_path,
            {_column_expr(columns, "review_audio_request_key", "''")} AS audio_request_key,
            {_column_expr(columns, "review_request_key", "''")} AS request_key,
            {_column_expr(columns, "review_request_id", "''")} AS request_id,
            {_column_expr(columns, "review_chat_provider", "''")} AS chat_provider,
            {_column_expr(columns, "review_chat_model", "''")} AS chat_model,
            {_column_expr(columns, "review_same_lesson_materials_json", "'[]'")} AS same_lesson_materials_json,
            {_column_expr(columns, "created_by_user_id", "0")} AS created_by_user_id,
            {_column_expr(columns, "created_at", "datetime('now','localtime')")} AS created_at
        FROM lessons
        ORDER BY id
        """
    ).fetchall()
    for row in rows:
        lesson_id = int(row["lesson_id"])
        existing = conn.execute(
            "SELECT id, status FROM review_plan_versions WHERE lesson_id=? ORDER BY version_no LIMIT 1",
            (lesson_id,),
        ).fetchone()
        if existing:
            if existing["status"] == REVIEW_PLAN_READY_STATUS:
                conn.execute(
                    """
                    UPDATE lessons
                    SET current_review_plan_version_id=COALESCE(current_review_plan_version_id, ?)
                    WHERE id=?
                    """,
                    (existing["id"], lesson_id),
                )
            continue
        raw_status = str(row["record_status"] or REVIEW_PLAN_READY_STATUS).strip() or REVIEW_PLAN_READY_STATUS
        status = raw_status
        if raw_status == "expired":
            status = REVIEW_PLAN_FAILED_STATUS
        has_artifact = bool(str(row["plan_json"] or "").strip() or str(row["pdf_path"] or "").strip())
        has_error_state = raw_status in {REVIEW_PLAN_FAILED_STATUS, "expired"} or bool(
            str(row["generation_error"] or "").strip()
        )
        has_active_state = raw_status in REVIEW_PLAN_ACTIVE_STATUSES
        if not (has_artifact or has_error_state or has_active_state):
            continue
        completed_at = str(row["created_at"] or "") if status == REVIEW_PLAN_READY_STATUS else ""
        cur = conn.execute(
            """
            INSERT INTO review_plan_versions (
                lesson_id, version_no, status, plan_json, pdf_path, generation_error,
                audio_path, audio_request_key, request_key, request_id, chat_provider,
                chat_model, same_lesson_materials_json, created_by_user_id,
                generation_options_json, completed_at, created_at, updated_at
            )
            VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
            """,
            (
                lesson_id,
                status,
                str(row["plan_json"] or ""),
                str(row["pdf_path"] or ""),
                str(row["generation_error"] or ""),
                str(row["audio_path"] or ""),
                str(row["audio_request_key"] or ""),
                str(row["request_key"] or ""),
                str(row["request_id"] or ""),
                str(row["chat_provider"] or ""),
                str(row["chat_model"] or ""),
                str(row["same_lesson_materials_json"] or "[]"),
                int(row["created_by_user_id"] or 0),
                _dump_generation_options(None, source="legacy"),
                completed_at,
                str(row["created_at"] or ""),
            ),
        )
        if status == REVIEW_PLAN_READY_STATUS:
            conn.execute(
                "UPDATE lessons SET current_review_plan_version_id=? WHERE id=?",
                (cur.lastrowid, lesson_id),
            )


def _rebuild_lessons_without_review_plan_artifact_columns(conn: sqlite3.Connection) -> None:
    columns = _lesson_columns(conn)
    if not (columns & REVIEW_PLAN_LEGACY_ARTIFACT_COLUMNS):
        return
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS lessons__review_plan_artifact_rebuild")
        conn.execute(
            """
            CREATE TABLE lessons__review_plan_artifact_rebuild (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER REFERENCES organizations(id),
                date        TEXT NOT NULL,
                subject     TEXT,
                grade       TEXT,
                topic       TEXT,
                summary     TEXT,
                weak_points TEXT,
                class_id    INTEGER REFERENCES classes(id) ON DELETE SET NULL,
                current_review_plan_version_id INTEGER DEFAULT NULL,
                created_by_user_id INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now','localtime')),
                updated_at  TEXT DEFAULT (datetime('now','localtime'))
            )
            """
        )
        current_columns = _lesson_columns(conn)
        copy_columns = [
            "id",
            "organization_id",
            "date",
            "subject",
            "grade",
            "topic",
            "summary",
            "weak_points",
            "class_id",
            "current_review_plan_version_id",
            "created_by_user_id",
            "created_at",
            "updated_at",
        ]
        select_exprs = [
            _column_expr(current_columns, "id", "NULL"),
            _column_expr(current_columns, "organization_id", "NULL"),
            _column_expr(current_columns, "date", "date('now')"),
            _column_expr(current_columns, "subject", "''"),
            _column_expr(current_columns, "grade", "''"),
            _column_expr(current_columns, "topic", "''"),
            _column_expr(current_columns, "summary", "''"),
            _column_expr(current_columns, "weak_points", "''"),
            _column_expr(current_columns, "class_id", "NULL"),
            _column_expr(current_columns, "current_review_plan_version_id", "NULL"),
            _column_expr(current_columns, "created_by_user_id", "0"),
            _column_expr(current_columns, "created_at", "datetime('now','localtime')"),
            _column_expr(current_columns, "updated_at", "datetime('now','localtime')"),
        ]
        conn.execute(
            f"""
            INSERT INTO lessons__review_plan_artifact_rebuild ({", ".join(copy_columns)})
            SELECT {", ".join(select_exprs)}
            FROM lessons
            """
        )
        conn.execute("DROP TABLE lessons")
        conn.execute("ALTER TABLE lessons__review_plan_artifact_rebuild RENAME TO lessons")
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _get_review_plan_version_for_update(conn: sqlite3.Connection, version_id: int):
    return conn.execute(
        "SELECT * FROM review_plan_versions WHERE id=?",
        (int(version_id),),
    ).fetchone()


def _get_latest_active_review_plan_version_row(conn: sqlite3.Connection, lesson_id: int):
    placeholders = ", ".join("?" for _ in REVIEW_PLAN_ACTIVE_STATUSES)
    params: list[object] = [int(lesson_id), *sorted(REVIEW_PLAN_ACTIVE_STATUSES)]
    return conn.execute(
        f"""
        SELECT *
        FROM review_plan_versions
        WHERE lesson_id=? AND status IN ({placeholders})
        ORDER BY id DESC
        LIMIT 1
        """,
        params,
    ).fetchone()


def _get_latest_review_plan_version_row(conn: sqlite3.Connection, lesson_id: int):
    return conn.execute(
        """
        SELECT *
        FROM review_plan_versions
        WHERE lesson_id=?
        ORDER BY version_no DESC, id DESC
        LIMIT 1
        """,
        (int(lesson_id),),
    ).fetchone()


def _lesson_has_active_review_plan_version(conn: sqlite3.Connection, lesson_id: int) -> bool:
    return _get_latest_active_review_plan_version_row(conn, lesson_id) is not None


def create_review_plan_version(
    *,
    lesson_id: int,
    status: str = "pending",
    created_by_user_id: int = 0,
    audio_path: str = "",
    audio_request_key: str = "",
    request_key: str = "",
    request_id: str = "",
    chat_provider: str = "",
    chat_model: str = "",
    same_lesson_materials: Optional[list[str]] = None,
    generation_options: object | None = None,
    generation_options_source: str = "create",
) -> dict:
    normalized_status = str(status or "pending").strip() or "pending"
    with get_conn() as conn:
        lesson = conn.execute("SELECT id FROM lessons WHERE id=?", (int(lesson_id),)).fetchone()
        if not lesson:
            raise LookupError("lesson not found")
        if normalized_status in REVIEW_PLAN_ACTIVE_STATUSES:
            placeholders = ", ".join("?" for _ in REVIEW_PLAN_ACTIVE_STATUSES)
            conn.execute(
                f"""
                UPDATE review_plan_versions
                SET status='interrupted', updated_at=datetime('now','localtime')
                WHERE lesson_id=? AND status IN ({placeholders})
                """,
                (int(lesson_id), *sorted(REVIEW_PLAN_ACTIVE_STATUSES)),
            )
        row = conn.execute(
            "SELECT COALESCE(MAX(version_no), 0) + 1 AS next_version_no FROM review_plan_versions WHERE lesson_id=?",
            (int(lesson_id),),
        ).fetchone()
        version_no = int(row["next_version_no"] or 1)
        cur = conn.execute(
            """
            INSERT INTO review_plan_versions (
                lesson_id, version_no, status, created_by_user_id, audio_path,
                audio_request_key, request_key, request_id, chat_provider, chat_model,
                same_lesson_materials_json, generation_options_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(lesson_id),
                version_no,
                normalized_status,
                int(created_by_user_id or 0),
                str(audio_path or ""),
                str(audio_request_key or ""),
                str(request_key or ""),
                str(request_id or ""),
                str(chat_provider or ""),
                str(chat_model or ""),
                _dump_review_plan_materials(same_lesson_materials),
                _dump_generation_options(generation_options, source=generation_options_source),
            ),
        )
        if normalized_status == REVIEW_PLAN_READY_STATUS:
            conn.execute(
                "UPDATE lessons SET current_review_plan_version_id=?, updated_at=datetime('now','localtime') WHERE id=?",
                (cur.lastrowid, int(lesson_id)),
            )
        row = conn.execute(
            "SELECT * FROM review_plan_versions WHERE id=?",
            (cur.lastrowid,),
        ).fetchone()
        return _review_plan_version_from_row(row)


def update_review_plan_version_generation_options(version_id: int, generation_options: object | None) -> None:
    with get_conn() as conn:
        row = _get_review_plan_version_for_update(conn, version_id)
        if not row:
            raise LookupError("review plan version not found")
        conn.execute(
            """
            UPDATE review_plan_versions
            SET generation_options_json=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (
                _dump_generation_options(generation_options, source="regenerate"),
                int(version_id),
            ),
        )


def update_review_plan_version_source_artifact(
    version_id: int,
    *,
    source_text: str,
    cleaned_source_text: str,
    source_text_hash: str,
    source_brief: object,
    source_pack: object | None = None,
    source_type: str = "text",
) -> None:
    source_pack_payload = source_pack
    if source_pack_payload is None:
        source_pack_payload = build_lesson_source_pack_from_artifact(
            source_text=source_text,
            cleaned_source_text=cleaned_source_text,
            source_text_hash_value=source_text_hash,
            source_brief=source_brief,
            source_type=source_type,
        ).model_dump()
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE review_plan_versions
            SET source_text=?,
                cleaned_source_text=?,
                source_text_hash=?,
                source_brief_json=?,
                source_pack_json=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (
                str(source_text or ""),
                str(cleaned_source_text or ""),
                str(source_text_hash or ""),
                _dump_review_plan_source_brief(source_brief),
                _dump_review_plan_source_pack(source_pack_payload),
                int(version_id),
            ),
        )
        conn.commit()
    if cur.rowcount == 0:
        raise LookupError("review plan version not found")


def mark_review_plan_version_transcription_succeeded(version_id: int, *, summary: str) -> None:
    with get_conn() as conn:
        row = _get_review_plan_version_for_update(conn, version_id)
        if not row:
            raise LookupError("review plan version not found")
        conn.execute(
            """
            UPDATE lessons
            SET summary=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (summary, int(row["lesson_id"])),
        )
        conn.execute(
            """
            UPDATE review_plan_versions
            SET status='generating', generation_error='', updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (int(version_id),),
        )


def complete_review_plan_version(version_id: int, *, plan: dict, pdf_path: str) -> None:
    plan_json = json.dumps(plan or {}, ensure_ascii=False)
    with get_conn() as conn:
        row = _get_review_plan_version_for_update(conn, version_id)
        if not row:
            raise LookupError("review plan version not found")
        conn.execute(
            """
            UPDATE review_plan_versions
            SET status='ready',
                plan_json=?,
                pdf_path=?,
                generation_error='',
                completed_at=datetime('now','localtime'),
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (plan_json, str(pdf_path or ""), int(version_id)),
        )
        conn.execute(
            """
            UPDATE lessons
            SET current_review_plan_version_id=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (int(version_id), int(row["lesson_id"])),
        )


def update_review_plan_version_pdf_path(version_id: int, *, pdf_path: str) -> None:
    with get_conn() as conn:
        row = _get_review_plan_version_for_update(conn, version_id)
        if not row:
            raise LookupError("review plan version not found")
        conn.execute(
            """
            UPDATE review_plan_versions
            SET pdf_path=?,
                generation_error='',
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (str(pdf_path or ""), int(version_id)),
        )


def fail_review_plan_version(version_id: int, error_message: str) -> None:
    with get_conn() as conn:
        row = _get_review_plan_version_for_update(conn, version_id)
        if not row:
            raise LookupError("review plan version not found")
        conn.execute(
            """
            UPDATE review_plan_versions
            SET status='failed',
                generation_error=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (str(error_message or ""), int(version_id)),
        )


def get_review_plan_version(version_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM review_plan_versions WHERE id=?",
            (int(version_id),),
        ).fetchone()
        return _review_plan_version_from_row(row)


def get_review_plan_version_for_lesson(lesson_id: int, version_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM review_plan_versions WHERE id=? AND lesson_id=?",
            (int(version_id), int(lesson_id)),
        ).fetchone()
        return _review_plan_version_from_row(row)


def list_review_plan_versions(lesson_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM review_plan_versions
            WHERE lesson_id=?
            ORDER BY version_no DESC, id DESC
            """,
            (int(lesson_id),),
        ).fetchall()
        return [_review_plan_version_from_row(row) for row in rows]


def set_current_review_plan_version(lesson_id: int, version_id: int) -> None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM review_plan_versions WHERE id=? AND lesson_id=?",
            (int(version_id), int(lesson_id)),
        ).fetchone()
        if not row:
            raise LookupError("review plan version not found")
        if str(row["status"] or "") != REVIEW_PLAN_READY_STATUS:
            raise ValueError("review plan version must be ready")
        conn.execute(
            """
            UPDATE lessons
            SET current_review_plan_version_id=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (int(version_id), int(lesson_id)),
        )


def get_current_review_plan_version(lesson_id: int):
    with get_conn() as conn:
        lesson = conn.execute(
            "SELECT current_review_plan_version_id FROM lessons WHERE id=?",
            (int(lesson_id),),
        ).fetchone()
        if not lesson or not lesson["current_review_plan_version_id"]:
            return None
        row = conn.execute(
            "SELECT * FROM review_plan_versions WHERE id=? AND lesson_id=?",
            (int(lesson["current_review_plan_version_id"]), int(lesson_id)),
        ).fetchone()
        return _review_plan_version_from_row(row)


def lesson_has_active_review_plan_version(lesson_id: int) -> bool:
    with get_conn() as conn:
        return _lesson_has_active_review_plan_version(conn, lesson_id)


def _active_or_latest_version_for_lesson(conn: sqlite3.Connection, lesson_id: int):
    return _get_latest_active_review_plan_version_row(conn, lesson_id) or _get_latest_review_plan_version_row(conn, lesson_id)


def _ensure_compat_review_plan_version(
    conn: sqlite3.Connection,
    lesson_id: int,
    *,
    status: str = "generating",
    request_key: str = "",
    request_id: str = "",
    chat_provider: str = "",
    chat_model: str = "",
    generation_options: object | None = None,
    generation_options_source: str = "create",
) -> int:
    active = _get_latest_active_review_plan_version_row(conn, lesson_id)
    if active:
        if generation_options is not None:
            conn.execute(
                """
                UPDATE review_plan_versions
                SET generation_options_json=?,
                    updated_at=datetime('now','localtime')
                WHERE id=?
                """,
                (
                    _dump_generation_options(generation_options, source=generation_options_source),
                    int(active["id"]),
                ),
            )
        return int(active["id"])
    latest = conn.execute(
        "SELECT COALESCE(MAX(version_no), 0) + 1 AS next_version_no FROM review_plan_versions WHERE lesson_id=?",
        (int(lesson_id),),
    ).fetchone()
    cur = conn.execute(
        """
        INSERT INTO review_plan_versions (
            lesson_id, version_no, status, request_key, request_id, chat_provider, chat_model,
            generation_options_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(lesson_id),
            int(latest["next_version_no"] or 1),
            str(status or "generating"),
            str(request_key or ""),
            str(request_id or ""),
            str(chat_provider or ""),
            str(chat_model or ""),
            _dump_generation_options(generation_options, source=generation_options_source),
        ),
    )
    return int(cur.lastrowid)


def save_lesson(date_str: str, subject: str, grade: str, topic: str,
                summary: str, weak_points: str,
                plan: dict, pdf_path: str, class_id: int = 0) -> int:
    """保存一节课及其复习计划，返回 lesson_id。"""
    lesson_id = create_pending_lesson(
        date_str=date_str,
        subject=subject,
        grade=grade,
        topic=topic,
        summary=summary,
        weak_points=weak_points,
        class_id=class_id,
    )
    version = create_review_plan_version(lesson_id=lesson_id, status="generating")
    complete_review_plan_version(version["id"], plan=plan, pdf_path=pdf_path)
    return lesson_id


def create_pending_lesson(
    date_str: str,
    subject: str,
    grade: str,
    topic: str,
    summary: str,
    weak_points: str,
    class_id: int = 0,
    *,
    plan: Optional[dict] = None,
    pdf_path: str = "",
    record_status: str = "pending",
    created_by_user_id: int = 0,
    review_audio_path: str = "",
    review_audio_request_key: str = "",
    review_request_key: str = "",
    review_request_id: str = "",
    review_chat_provider: str = "",
    review_chat_model: str = "",
    review_same_lesson_materials: Optional[list[str]] = None,
    review_generation_options: object | None = None,
) -> int:
    """Create a lesson record in pending state before AI generation completes."""
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
               (date, subject, grade, topic, summary, weak_points, class_id, organization_id, created_by_user_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                date_str,
                subject,
                grade,
                topic,
                summary,
                weak_points,
                class_id if class_id else None,
                organization_id,
                int(created_by_user_id or 0),
            ),
        )
        lesson_id = int(cur.lastrowid)
        needs_runtime_version = any(
            str(value or "").strip()
            for value in (
                pdf_path,
                review_audio_path,
                review_audio_request_key,
                review_request_key,
                review_request_id,
                review_chat_provider,
                review_chat_model,
            )
        ) or record_status not in {"", "pending"} or bool(plan) or review_generation_options is not None
        if needs_runtime_version:
            status = str(record_status or "pending").strip() or "pending"
            version_id = _ensure_compat_review_plan_version(
                conn,
                lesson_id,
                status=status,
                request_key=review_request_key,
                request_id=review_request_id,
                chat_provider=review_chat_provider,
                chat_model=review_chat_model,
                generation_options=review_generation_options,
            )
            plan_json = json.dumps(plan or {}, ensure_ascii=False) if plan else ""
            if plan_json or pdf_path or review_audio_path or review_audio_request_key or review_same_lesson_materials:
                conn.execute(
                    """
                    UPDATE review_plan_versions
                    SET plan_json=?,
                        pdf_path=?,
                        audio_path=?,
                        audio_request_key=?,
                        same_lesson_materials_json=?,
                        completed_at=CASE
                            WHEN status='ready' AND (COALESCE(plan_json, '') <> '' OR COALESCE(pdf_path, '') <> '')
                            THEN COALESCE(NULLIF(completed_at, ''), datetime('now','localtime'))
                            ELSE completed_at
                        END,
                        updated_at=datetime('now','localtime')
                    WHERE id=?
                    """,
                    (
                        plan_json,
                        str(pdf_path or ""),
                        str(review_audio_path or ""),
                        str(review_audio_request_key or ""),
                        _dump_review_plan_materials(review_same_lesson_materials),
                        version_id,
                    ),
                )
            if status == REVIEW_PLAN_READY_STATUS and (plan_json or str(pdf_path or "").strip()):
                conn.execute(
                    """
                    UPDATE review_plan_versions
                    SET completed_at=COALESCE(NULLIF(completed_at, ''), datetime('now','localtime')),
                        updated_at=datetime('now','localtime')
                    WHERE id=?
                    """,
                    (version_id,),
                )
                conn.execute(
                    """
                    UPDATE lessons
                    SET current_review_plan_version_id=?, updated_at=datetime('now','localtime')
                    WHERE id=?
                    """,
                    (version_id, lesson_id),
                )
        return lesson_id


def mark_lesson_transcription_succeeded(lesson_id: int, *, summary: str) -> None:
    with get_conn() as conn:
        lesson = conn.execute("SELECT id FROM lessons WHERE id=?", (int(lesson_id),)).fetchone()
        if not lesson:
            raise LookupError("lesson not found")
        version_id = _ensure_compat_review_plan_version(conn, lesson_id, status="generating")
        conn.execute(
            """
            UPDATE lessons
            SET summary=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (summary, int(lesson_id)),
        )
        conn.execute(
            """
            UPDATE review_plan_versions
            SET status='generating', generation_error='', updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (version_id,),
        )


def mark_lesson_generation_succeeded(lesson_id: int, *, plan: dict, pdf_path: str) -> None:
    with get_conn() as conn:
        lesson = conn.execute("SELECT id FROM lessons WHERE id=?", (int(lesson_id),)).fetchone()
        if not lesson:
            raise LookupError("lesson not found")
        version_id = _ensure_compat_review_plan_version(conn, lesson_id, status="generating")
        plan_json = json.dumps(plan or {}, ensure_ascii=False)
        conn.execute(
            """
            UPDATE review_plan_versions
            SET plan_json=?,
                pdf_path=?,
                status='ready',
                generation_error='',
                completed_at=datetime('now','localtime'),
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (plan_json, str(pdf_path or ""), version_id),
        )
        conn.execute(
            """
            UPDATE lessons
            SET current_review_plan_version_id=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (version_id, int(lesson_id)),
        )


def mark_lesson_generation_failed(lesson_id: int, error_message: str) -> None:
    with get_conn() as conn:
        lesson = conn.execute("SELECT id FROM lessons WHERE id=?", (int(lesson_id),)).fetchone()
        if not lesson:
            raise LookupError("lesson not found")
        version_id = _ensure_compat_review_plan_version(conn, lesson_id, status="generating")
        conn.execute(
            """
            UPDATE review_plan_versions
            SET status='failed',
                generation_error=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (str(error_message or ""), version_id),
        )


def requeue_lesson_generation(
    lesson_id: int,
    *,
    record_status: str = "generating",
    review_request_key: str = "",
    review_request_id: str = "",
    review_chat_provider: str = "",
    review_chat_model: str = "",
) -> None:
    with get_conn() as conn:
        lesson = conn.execute("SELECT id FROM lessons WHERE id=?", (int(lesson_id),)).fetchone()
        if not lesson:
            raise LookupError("lesson not found")
        version_id = _ensure_compat_review_plan_version(
            conn,
            lesson_id,
            status=str(record_status or "generating"),
            request_key=review_request_key,
            request_id=review_request_id,
            chat_provider=review_chat_provider,
            chat_model=review_chat_model,
        )
        conn.execute(
            """
            UPDATE review_plan_versions
            SET status=?,
                generation_error='',
                request_key=?,
                request_id=?,
                chat_provider=?,
                chat_model=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (
                str(record_status or "generating"),
                str(review_request_key or ""),
                str(review_request_id or ""),
                str(review_chat_provider or ""),
                str(review_chat_model or ""),
                version_id,
            ),
        )


def _dump_review_plan_run_json(value: object, fallback: object) -> str:
    try:
        return json.dumps(value if value is not None else fallback, ensure_ascii=False)
    except TypeError:
        return json.dumps(fallback, ensure_ascii=False)


def _load_review_plan_run_json(value: object, fallback: object):
    try:
        parsed = json.loads(str(value or ""))
    except json.JSONDecodeError:
        return fallback
    return parsed


def save_review_plan_run(
    *,
    lesson_id: int,
    version_id: int = 0,
    organization_id: int,
    trace_id: str,
    status: str,
    subject: str = "",
    provider: str = "",
    model: str = "",
    prompt_version: str = "",
    style_version: str = "",
    schema_version: str = "",
    warnings: object = None,
    quality_review: object = None,
    node_outputs: object = None,
    logs: object = None,
) -> None:
    warnings_json = _dump_review_plan_run_json(warnings, [])
    quality_review_json = _dump_review_plan_run_json(quality_review, {})
    node_outputs_json = _dump_review_plan_run_json(node_outputs, {})
    logs_json = _dump_review_plan_run_json(logs, [])
    normalized_status = str(status or "running")
    normalized_version_id = int(version_id or 0) or None
    with get_conn() as conn:
        if normalized_status == "running":
            conn.execute(
                """
                UPDATE review_plan_runs
                SET status='interrupted',
                    updated_at=datetime('now','localtime')
                WHERE lesson_id=?
                  AND trace_id<>?
                  AND status='running'
                """,
                (
                    int(lesson_id),
                    str(trace_id or ""),
                ),
            )
        existing = conn.execute(
            "SELECT id FROM review_plan_runs WHERE trace_id=?",
            (str(trace_id or ""),),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE review_plan_runs
                SET lesson_id=?, version_id=?, organization_id=?, status=?, subject=?, provider=?, model=?,
                    prompt_version=?, style_version=?, schema_version=?, warnings_json=?,
                    quality_review_json=?, node_outputs_json=?, logs_json=?,
                    updated_at=datetime('now','localtime')
                WHERE trace_id=?
                """,
                (
                    int(lesson_id),
                    normalized_version_id,
                    int(organization_id),
                    normalized_status,
                    str(subject or ""),
                    str(provider or ""),
                    str(model or ""),
                    str(prompt_version or ""),
                    str(style_version or ""),
                    str(schema_version or ""),
                    warnings_json,
                    quality_review_json,
                    node_outputs_json,
                    logs_json,
                    str(trace_id or ""),
                ),
            )
            return
        conn.execute(
            """
            INSERT INTO review_plan_runs (
                lesson_id, version_id, organization_id, trace_id, status, subject, provider, model,
                prompt_version, style_version, schema_version, warnings_json,
                quality_review_json, node_outputs_json, logs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(lesson_id),
                normalized_version_id,
                int(organization_id),
                str(trace_id or ""),
                normalized_status,
                str(subject or ""),
                str(provider or ""),
                str(model or ""),
                str(prompt_version or ""),
                str(style_version or ""),
                str(schema_version or ""),
                warnings_json,
                quality_review_json,
                node_outputs_json,
                logs_json,
            ),
        )


def get_latest_review_plan_run_for_lesson(lesson_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM review_plan_runs
            WHERE lesson_id=?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (int(lesson_id),),
        ).fetchone()
        if not row:
            return None
        run = dict(row)
        run["warnings"] = _load_review_plan_run_json(run.get("warnings_json"), [])
        run["quality_review"] = _load_review_plan_run_json(run.get("quality_review_json"), {})
        run["node_outputs"] = _load_review_plan_run_json(run.get("node_outputs_json"), {})
        run["logs"] = _load_review_plan_run_json(run.get("logs_json"), [])
        return run


def get_latest_review_plan_run_for_version(version_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM review_plan_runs
            WHERE version_id=?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (int(version_id),),
        ).fetchone()
        if not row:
            return None
        run = dict(row)
        run["warnings"] = _load_review_plan_run_json(run.get("warnings_json"), [])
        run["quality_review"] = _load_review_plan_run_json(run.get("quality_review_json"), {})
        run["node_outputs"] = _load_review_plan_run_json(run.get("node_outputs_json"), {})
        run["logs"] = _load_review_plan_run_json(run.get("logs_json"), [])
        return run


def get_latest_completed_review_plan_quality_run_for_version(version_id: int) -> Optional[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM review_plan_runs
            WHERE version_id=?
              AND status='succeeded'
              AND quality_review_json IS NOT NULL
              AND quality_review_json<>''
              AND quality_review_json<>'{}'
            ORDER BY updated_at DESC, id DESC
            """,
            (int(version_id),),
        ).fetchall()
        for row in rows:
            run = dict(row)
            quality_review = _load_review_plan_run_json(run.get("quality_review_json"), {})
            if not isinstance(quality_review, dict) or not quality_review:
                continue
            run["warnings"] = _load_review_plan_run_json(run.get("warnings_json"), [])
            run["quality_review"] = quality_review
            run["node_outputs"] = _load_review_plan_run_json(run.get("node_outputs_json"), {})
            run["logs"] = _load_review_plan_run_json(run.get("logs_json"), [])
            return run
        return None


def _attach_review_plan_version_summary(conn: sqlite3.Connection, lesson: dict) -> dict:
    lesson_id = int(lesson.get("id") or 0)
    current_version = None
    current_version_id = lesson.get("current_review_plan_version_id")
    if current_version_id:
        current_version = _review_plan_version_from_row(
            conn.execute(
                "SELECT * FROM review_plan_versions WHERE id=? AND lesson_id=?",
                (int(current_version_id), lesson_id),
            ).fetchone()
        )
    active_version = _review_plan_version_from_row(_get_latest_active_review_plan_version_row(conn, lesson_id))
    latest_failed = _review_plan_version_from_row(
        conn.execute(
            """
            SELECT *
            FROM review_plan_versions
            WHERE lesson_id=? AND status='failed'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (lesson_id,),
        ).fetchone()
    )
    latest_version = active_version or current_version or _review_plan_version_from_row(
        _get_latest_review_plan_version_row(conn, lesson_id)
    )

    lesson["current_version"] = current_version
    lesson["active_version"] = active_version
    lesson["current_review_plan_version_id"] = current_version["id"] if current_version else None
    lesson["current_version_id"] = current_version["id"] if current_version else None
    lesson["current_version_no"] = current_version["version_no"] if current_version else None
    lesson["current_generated_at"] = current_version["completed_at"] if current_version else ""
    lesson["current_status"] = current_version["status"] if current_version else ""
    lesson["has_version_generating"] = active_version is not None
    lesson["active_version_status"] = active_version["status"] if active_version else ""
    lesson["active_version_created_at"] = active_version["created_at"] if active_version else ""
    lesson["latest_failed_version_id"] = latest_failed["id"] if latest_failed else None
    lesson["latest_generation_error"] = (
        (latest_failed or {}).get("generation_error")
        or (active_version or {}).get("generation_error")
        or ""
    )

    runtime_projection = active_version or current_version or latest_version
    lesson["plan_json"] = (current_version or {}).get("plan_json", "")
    lesson["plan"] = (current_version or {}).get("plan", {})
    lesson["pdf_path"] = (current_version or {}).get("pdf_path", "")
    if active_version:
        lesson["record_status"] = active_version.get("status") or "pending"
    elif current_version:
        lesson["record_status"] = current_version.get("status") or REVIEW_PLAN_READY_STATUS
    elif latest_version:
        lesson["record_status"] = latest_version.get("status") or REVIEW_PLAN_FAILED_STATUS
    else:
        lesson["record_status"] = "pending"
    lesson["generation_error"] = (
        (active_version or {}).get("generation_error")
        or (latest_failed or {}).get("generation_error")
        or (current_version or {}).get("generation_error")
        or ""
    )
    lesson["review_audio_path"] = (runtime_projection or {}).get("audio_path", "")
    lesson["review_audio_request_key"] = (runtime_projection or {}).get("audio_request_key", "")
    lesson["review_request_key"] = (runtime_projection or {}).get("request_key", "")
    lesson["review_request_id"] = (runtime_projection or {}).get("request_id", "")
    lesson["review_chat_provider"] = (runtime_projection or {}).get("chat_provider", "")
    lesson["review_chat_model"] = (runtime_projection or {}).get("chat_model", "")
    lesson["review_same_lesson_materials_json"] = (runtime_projection or {}).get("same_lesson_materials_json", "[]")
    lesson["review_same_lesson_materials"] = (runtime_projection or {}).get("same_lesson_materials", [])
    lesson["review_generation_options"] = (runtime_projection or {}).get("generation_options", normalize_generation_options(None))
    lesson["review_generation_summary"] = (runtime_projection or {}).get(
        "generation_summary",
        generation_options_summary(normalize_generation_options(None)),
    )
    return lesson


_REVIEW_PLAN_VERSION_LIST_COLUMNS = """
    id,
    lesson_id,
    version_no,
    status,
    pdf_path,
    generation_error,
    audio_path,
    audio_request_key,
    request_key,
    request_id,
    chat_provider,
    chat_model,
    same_lesson_materials_json,
    generation_options_json,
    created_by_user_id,
    completed_at,
    created_at,
    updated_at
"""


def _review_plan_version_summaries_by_id(conn: sqlite3.Connection, version_ids: list[int]) -> dict[int, dict]:
    unique_ids = sorted({int(version_id) for version_id in version_ids if int(version_id or 0) > 0})
    if not unique_ids:
        return {}
    placeholders = ",".join("?" for _ in unique_ids)
    rows = conn.execute(
        f"""
        SELECT {_REVIEW_PLAN_VERSION_LIST_COLUMNS}
        FROM review_plan_versions
        WHERE id IN ({placeholders})
        """,
        unique_ids,
    ).fetchall()
    summaries: dict[int, dict] = {}
    for row in rows:
        summary = _review_plan_version_summary_from_row(row)
        if summary:
            summaries[int(summary["id"])] = summary
    return summaries


def _review_plan_version_summaries_by_lesson(
    conn: sqlite3.Connection,
    lesson_ids: list[int],
    *,
    where_sql: str = "",
    order_sql: str = "created_at DESC, id DESC",
) -> dict[int, dict]:
    unique_ids = sorted({int(lesson_id) for lesson_id in lesson_ids if int(lesson_id or 0) > 0})
    if not unique_ids:
        return {}
    placeholders = ",".join("?" for _ in unique_ids)
    extra_where = f" AND {where_sql}" if where_sql else ""
    rows = conn.execute(
        f"""
        SELECT {_REVIEW_PLAN_VERSION_LIST_COLUMNS}
        FROM review_plan_versions v
        WHERE v.lesson_id IN ({placeholders})
          {extra_where}
          AND v.id = (
              SELECT x.id
              FROM review_plan_versions x
              WHERE x.lesson_id = v.lesson_id
                {extra_where.replace('v.', 'x.')}
              ORDER BY {order_sql.replace('v.', 'x.')}
              LIMIT 1
          )
        """,
        unique_ids,
    ).fetchall()
    summaries: dict[int, dict] = {}
    for row in rows:
        summary = _review_plan_version_summary_from_row(row)
        if summary:
            summaries[int(summary["lesson_id"])] = summary
    return summaries


def _fetch_user_display_summaries(conn: sqlite3.Connection, user_ids: list[int]) -> dict[int, dict]:
    unique_ids = sorted({int(user_id) for user_id in user_ids if int(user_id or 0) > 0})
    if not unique_ids:
        return {}
    placeholders = ",".join("?" for _ in unique_ids)
    rows = conn.execute(
        f"""
        SELECT id, username, display_name
        FROM users
        WHERE id IN ({placeholders})
        """,
        unique_ids,
    ).fetchall()
    return {int(row["id"]): dict(row) for row in rows}


def _attach_review_plan_version_summaries_bulk(conn: sqlite3.Connection, lessons: list[dict]) -> list[dict]:
    if not lessons:
        return lessons

    lesson_ids = [int(lesson.get("id") or 0) for lesson in lessons]
    current_version_ids = [int(lesson.get("current_review_plan_version_id") or 0) for lesson in lessons]
    current_by_id = _review_plan_version_summaries_by_id(conn, current_version_ids)
    active_by_lesson_id = _review_plan_version_summaries_by_lesson(
        conn,
        lesson_ids,
        where_sql="v.status IN ('pending', 'queued', 'processing', 'transcribing', 'generating')",
        order_sql="v.created_at DESC, v.id DESC",
    )
    failed_by_lesson_id = _review_plan_version_summaries_by_lesson(
        conn,
        lesson_ids,
        where_sql="v.status='failed'",
        order_sql="v.updated_at DESC, v.id DESC",
    )
    latest_by_lesson_id = _review_plan_version_summaries_by_lesson(
        conn,
        lesson_ids,
        order_sql="v.created_at DESC, v.id DESC",
    )
    users_by_id = _fetch_user_display_summaries(
        conn,
        [int(lesson.get("created_by_user_id") or 0) for lesson in lessons],
    )

    for lesson in lessons:
        lesson_id = int(lesson.get("id") or 0)
        current_version = current_by_id.get(int(lesson.get("current_review_plan_version_id") or 0))
        active_version = active_by_lesson_id.get(lesson_id)
        latest_failed = failed_by_lesson_id.get(lesson_id)
        latest_version = active_version or current_version or latest_by_lesson_id.get(lesson_id)
        runtime_projection = active_version or current_version or latest_version

        lesson["current_version"] = current_version
        lesson["active_version"] = active_version
        lesson["current_review_plan_version_id"] = current_version["id"] if current_version else None
        lesson["current_version_id"] = current_version["id"] if current_version else None
        lesson["current_version_no"] = current_version["version_no"] if current_version else None
        lesson["current_generated_at"] = current_version["completed_at"] if current_version else ""
        lesson["current_status"] = current_version["status"] if current_version else ""
        lesson["has_version_generating"] = active_version is not None
        lesson["active_version_status"] = active_version["status"] if active_version else ""
        lesson["active_version_created_at"] = active_version["created_at"] if active_version else ""
        lesson["latest_failed_version_id"] = latest_failed["id"] if latest_failed else None
        lesson["latest_generation_error"] = (
            (latest_failed or {}).get("generation_error")
            or (active_version or {}).get("generation_error")
            or ""
        )
        lesson["plan_json"] = ""
        lesson["plan"] = {}
        lesson["pdf_path"] = (current_version or {}).get("pdf_path", "")
        if active_version:
            lesson["record_status"] = active_version.get("status") or "pending"
        elif current_version:
            lesson["record_status"] = current_version.get("status") or REVIEW_PLAN_READY_STATUS
        elif latest_version:
            lesson["record_status"] = latest_version.get("status") or REVIEW_PLAN_FAILED_STATUS
        else:
            lesson["record_status"] = "pending"
        lesson["generation_error"] = (
            (active_version or {}).get("generation_error")
            or (latest_failed or {}).get("generation_error")
            or (current_version or {}).get("generation_error")
            or ""
        )
        lesson["review_audio_path"] = (runtime_projection or {}).get("audio_path", "")
        lesson["review_audio_request_key"] = (runtime_projection or {}).get("audio_request_key", "")
        lesson["review_request_key"] = (runtime_projection or {}).get("request_key", "")
        lesson["review_request_id"] = (runtime_projection or {}).get("request_id", "")
        lesson["review_chat_provider"] = (runtime_projection or {}).get("chat_provider", "")
        lesson["review_chat_model"] = (runtime_projection or {}).get("chat_model", "")
        lesson["review_same_lesson_materials_json"] = (runtime_projection or {}).get("same_lesson_materials_json", "[]")
        lesson["review_same_lesson_materials"] = []
        lesson["review_generation_options"] = (runtime_projection or {}).get("generation_options", normalize_generation_options(None))
        lesson["review_generation_summary"] = (runtime_projection or {}).get(
            "generation_summary",
            generation_options_summary(normalize_generation_options(None)),
        )

        creator = users_by_id.get(int(lesson.get("created_by_user_id") or 0), {})
        lesson["creator_display_name"] = str(creator.get("display_name") or creator.get("username") or "").strip()
        lesson["creator_username"] = str(creator.get("username") or "").strip()

    return lessons


def get_lesson(lesson_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        return _attach_review_plan_version_summary(conn, d)


def _normalize_pagination(page: int = 1, page_size: int = 50, max_page_size: int = 100) -> tuple[int, int, int]:
    safe_page = max(1, int(page or 1))
    safe_page_size = max(1, min(max_page_size, int(page_size or 50)))
    return safe_page, safe_page_size, (safe_page - 1) * safe_page_size


def _list_lessons_page(
    *,
    month_str: str = "",
    class_id: int = 0,
    class_scope: str = "all",
    organization_id: int | None = None,
    member_class_ids: list[int] | None = None,
    page: int = 1,
    page_size: int = 50,
    max_page_size: int = 100,
) -> dict:
    safe_page, safe_page_size, offset = _normalize_pagination(page, page_size, max_page_size=max_page_size)
    where_clauses: list[str] = []
    params: list[object] = []
    if organization_id is not None:
        where_clauses.append("l.organization_id=?")
        params.append(int(organization_id))
    if class_id:
        where_clauses.append("l.class_id=?")
        params.append(class_id)
    if member_class_ids is not None:
        class_ids = sorted({int(item) for item in member_class_ids if int(item or 0) > 0})
        if not class_ids:
            return {"items": [], "total": 0, "page": safe_page, "page_size": safe_page_size}
        placeholders = ",".join("?" for _ in class_ids)
        where_clauses.append(f"l.class_id IN ({placeholders})")
        params.extend(class_ids)
    if month_str:
        where_clauses.append("l.date LIKE ?")
        params.append(f"{month_str}%")
    lifecycle_clause = _lesson_class_lifecycle_where_clause(class_scope, "c", "l")
    if lifecycle_clause:
        where_clauses.append(lifecycle_clause)
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    with get_conn() as conn:
        total_row = conn.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM lessons l
            LEFT JOIN classes c ON c.id = l.class_id
            {where_sql}
            """,
            params,
        ).fetchone()
        rows = conn.execute(
            f"""
            SELECT l.*
            FROM lessons l
            LEFT JOIN classes c ON c.id = l.class_id
            LEFT JOIN review_plan_versions cv ON cv.id = l.current_review_plan_version_id
            {where_sql}
            ORDER BY COALESCE(NULLIF(cv.completed_at, ''), NULLIF(l.updated_at, ''), NULLIF(l.created_at, ''), NULLIF(l.date, '')) DESC,
                     l.id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, safe_page_size, offset],
        ).fetchall()
        items = _attach_review_plan_version_summaries_bulk(conn, [dict(r) for r in rows])
        return {
            "items": items,
            "total": int(total_row["total"] if total_row else 0),
            "page": safe_page,
            "page_size": safe_page_size,
        }


def list_lessons_page(
    month_str: str = "",
    class_id: int = 0,
    class_scope: str = "all",
    page: int = 1,
    page_size: int = 50,
    max_page_size: int = 100,
) -> dict:
    return _list_lessons_page(
        month_str=month_str,
        class_id=class_id,
        class_scope=class_scope,
        page=page,
        page_size=page_size,
        max_page_size=max_page_size,
    )


def list_lessons(month_str: str = "", class_id: int = 0, class_scope: str = "all") -> list:
    page = list_lessons_page(
        month_str=month_str,
        class_id=class_id,
        class_scope=class_scope,
        page=1,
        page_size=100000,
        max_page_size=100000,
    )
    return list(page["items"])


def delete_lesson(lesson_id: int):
    """Delete a lesson from the database."""
    with get_conn() as conn:
        conn.execute("DELETE FROM lessons WHERE id=?", (lesson_id,))


def create_monthly_plan_job(organization_id: int, user_id: int, month_str: str) -> dict:
    with get_conn() as conn:
        user_row = _fetch_user_row_by_id(conn, user_id)
        if not user_row:
            raise LookupError("user not found")
        if user_row["organization_id"] != organization_id:
            raise ValueError("user does not belong to organization")
        cur = conn.execute(
            """
            INSERT INTO monthly_plan_jobs
                (organization_id, user_id, month_str, status, pdf_filename, generation_error)
            VALUES (?, ?, ?, 'pending', '', '')
            """,
            (organization_id, user_id, month_str),
        )
        job_id = cur.lastrowid
    return get_monthly_plan_job(job_id)


def get_monthly_plan_job(job_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM monthly_plan_jobs WHERE id=?", (job_id,)).fetchone()
        return _class_row_to_dict(row) if row else None


def mark_monthly_plan_job_succeeded(job_id: int, *, pdf_filename: str) -> None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE monthly_plan_jobs
            SET status='ready',
                pdf_filename=?,
                generation_error='',
                updated_at=(datetime('now','localtime'))
            WHERE id=?
            """,
            (pdf_filename, job_id),
        )
        if cur.rowcount == 0:
            raise LookupError("monthly plan job not found")


def mark_monthly_plan_job_failed(job_id: int, error_message: str) -> None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE monthly_plan_jobs
            SET status='failed',
                generation_error=?,
                pdf_filename='',
                updated_at=(datetime('now','localtime'))
            WHERE id=?
            """,
            (error_message, job_id),
        )
        if cur.rowcount == 0:
            raise LookupError("monthly plan job not found")


def requeue_monthly_plan_job(job_id: int) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE monthly_plan_jobs
            SET status='pending',
                generation_error='',
                updated_at=(datetime('now','localtime'))
            WHERE id=? AND status='failed'
            """,
            (job_id,),
        )
        if cur.rowcount == 0:
            raise LookupError("monthly plan job not found or not in failed state")
    return get_monthly_plan_job(job_id)


# ─── 班级 CRUD ─────────────────────────────────────────────────────────────────
CLASS_STAGES = ("小奥", "初中", "高中")
CLASS_GRADE_ORDER = ("一年级", "二年级", "三年级", "四年级", "五年级", "六年级", "七年级", "八年级", "九年级", "高一", "高二", "高三")
CLASS_STAGE_GRADES = {
    "小奥": ("一年级", "二年级", "三年级", "四年级", "五年级", "六年级"),
    "初中": ("七年级", "八年级", "九年级"),
    "高中": ("高一", "高二", "高三"),
}
PROMOTION_NEXT_GRADE = {
    "一年级": "二年级",
    "二年级": "三年级",
    "三年级": "四年级",
    "四年级": "五年级",
    "五年级": "六年级",
    "六年级": "七年级",
    "七年级": "八年级",
    "八年级": "九年级",
    "九年级": "高一",
    "高一": "高二",
    "高二": "高三",
}
GRADUATION_GRADES = {"六年级", "九年级", "高三"}
CLASS_LIFECYCLE_ACTIVE = "active"
CLASS_LIFECYCLE_PENDING_GRADUATION = "pending_graduation"
CLASS_LIFECYCLE_GRADUATED = "graduated"
CLASS_LIFECYCLE_ARCHIVED = "archived"
CLASS_LIFECYCLE_HISTORY_STATUSES = {
    CLASS_LIFECYCLE_PENDING_GRADUATION,
    CLASS_LIFECYCLE_GRADUATED,
    CLASS_LIFECYCLE_ARCHIVED,
}
ANNUAL_GRADE_PROMOTION_JOB_TYPE = "annual_grade_promotion"


def normalize_class_grade(value: str) -> str:
    raw = str(value or "").strip()
    aliases = {
        "1年级": "一年级",
        "2年级": "二年级",
        "3年级": "三年级",
        "4年级": "四年级",
        "5年级": "五年级",
        "6年级": "六年级",
        "7年级": "七年级",
        "8年级": "八年级",
        "9年级": "九年级",
        "一年级": "一年级",
        "二年级": "二年级",
        "三年级": "三年级",
        "四年级": "四年级",
        "五年级": "五年级",
        "六年级": "六年级",
        "七年级": "七年级",
        "八年级": "八年级",
        "九年级": "九年级",
        "初一": "七年级",
        "初二": "八年级",
        "初三": "九年级",
        "高1": "高一",
        "高2": "高二",
        "高3": "高三",
    }
    return aliases.get(raw, raw)


def infer_class_stage(grade: str) -> str:
    normalized = normalize_class_grade(grade)
    for stage, grades in CLASS_STAGE_GRADES.items():
        if normalized in grades:
            return stage
    return ""


def current_school_year_start(today: str | None = None) -> int:
    date_value = datetime.strptime(today, "%Y-%m-%d").date() if today else date.today()
    return date_value.year if (date_value.month, date_value.day) >= (6, 30) else date_value.year - 1


def infer_cohort_year(grade: str, today: str | None = None) -> int:
    normalized = normalize_class_grade(grade)
    stage = infer_class_stage(normalized)
    grades = CLASS_STAGE_GRADES.get(stage, ())
    offset = grades.index(normalized) if normalized in grades else 0
    return current_school_year_start(today) - offset


def infer_cohort_year_for_stage(grade: str, stage: str, today: str | None = None) -> int:
    normalized = normalize_class_grade(grade)
    grade_order = [
        "一年级", "二年级", "三年级", "四年级", "五年级", "六年级",
        "七年级", "八年级", "九年级", "高一", "高二", "高三",
    ]
    if normalized not in grade_order:
        return infer_cohort_year(grade, today)
    normalized_stage = normalize_bridge_stage(stage)
    first_rank = 9 if normalized_stage == "高中" else 6 if normalized_stage == "初中" else 0
    return current_school_year_start(today) - (grade_order.index(normalized) - first_rank)


def normalize_bridge_stage(value: str) -> str:
    normalized = str(value or "").strip()
    if normalized in {"小学", "小奥", "小"}:
        return "小学"
    if normalized in {"初中", "初"}:
        return "初中"
    if normalized in {"高中", "高"}:
        return "高中"
    return ""


def default_bridge_to_stage(from_stage: str) -> str:
    normalized = normalize_bridge_stage(from_stage)
    if normalized == "初中":
        return "高中"
    if normalized == "高中":
        return "高中"
    return "初中"


def parse_bridge_target(bridge_target: str, fallback_stage: str) -> tuple[str, str]:
    fallback = normalize_bridge_stage(fallback_stage) or "小学"
    raw = str(bridge_target or "").strip().replace(" ", "")
    if not raw or raw == "默认下一学段":
        return fallback, default_bridge_to_stage(fallback)
    long_match = re.match(r"^(小学|小奥|小|初中|初|高中|高)衔接(小学|小奥|小|初中|初|高中|高)$", raw)
    if long_match:
        return normalize_bridge_stage(long_match.group(1)) or fallback, normalize_bridge_stage(long_match.group(2)) or default_bridge_to_stage(fallback)
    short_match = re.match(r"^(小|初|高)衔(小|初|高)$", raw)
    if short_match:
        return normalize_bridge_stage(short_match.group(1)) or fallback, normalize_bridge_stage(short_match.group(2)) or default_bridge_to_stage(fallback)
    if raw == "初中衔接":
        return fallback, "初中"
    if raw == "高中衔接":
        return fallback, "高中"
    return fallback, default_bridge_to_stage(fallback)


def serialize_bridge_target(from_stage: str, to_stage: str) -> str:
    normalized_from = normalize_bridge_stage(from_stage) or "小学"
    normalized_to = normalize_bridge_stage(to_stage) or default_bridge_to_stage(normalized_from)
    return f"{normalized_from}衔接{normalized_to}"


def bridge_short_label(bridge_target: str, fallback_stage: str) -> str:
    from_stage, to_stage = parse_bridge_target(bridge_target, fallback_stage)
    short_map = {"小学": "小", "初中": "初", "高中": "高"}
    return f"{short_map.get(from_stage, '')}衔{short_map.get(to_stage, '')}" or "衔接"


def cohort_stage_short_label(stage: str) -> str:
    short_map = {"小学": "小", "初中": "初", "高中": "高"}
    return short_map.get(normalize_bridge_stage(stage), "小")


def display_cohort_stage(stage: str, is_bridge: bool, bridge_target: str) -> str:
    if is_bridge:
        return parse_bridge_target(bridge_target, stage)[1]
    return normalize_bridge_stage(stage) or "小学"


def build_group_class_name(subject: str, cohort_year: int, current_grade: str, class_number: str, is_bridge: bool, show_cohort_year: bool = True, bridge_target: str = "", stage: str = "") -> str:
    suffix = f"·{bridge_short_label(bridge_target, stage)}" if is_bridge else ""
    subject_prefix = f"{subject.strip()}·" if subject and subject.strip() else ""
    cohort_prefix = f"{cohort_stage_short_label(display_cohort_stage(stage, is_bridge, bridge_target))}{cohort_year}级·" if show_cohort_year and cohort_year else ""
    return f"{subject_prefix}{cohort_prefix}{current_grade}·{str(class_number).strip()}班{suffix}"


def build_structured_class_name(subject: str, cohort_year: int, current_grade: str, class_number: str, is_bridge: bool, show_cohort_year: bool = True, bridge_target: str = "", stage: str = "") -> str:
    return build_group_class_name(subject, cohort_year, current_grade, class_number, is_bridge, show_cohort_year, bridge_target, stage)


def build_short_term_drill_class_name(subject: str, cohort_year: int, current_grade: str, is_bridge: bool, bridge_target: str = "", stage: str = "", show_cohort_year: bool = True) -> str:
    if not current_grade:
        return ""
    suffix = f"·{bridge_short_label(bridge_target, stage)}" if is_bridge else ""
    subject_prefix = f"{subject.strip()}·" if subject and subject.strip() else ""
    cohort_part = f"{cohort_stage_short_label(display_cohort_stage(stage, is_bridge, bridge_target))}{cohort_year}级·" if show_cohort_year and cohort_year else ""
    return f"{subject_prefix}{cohort_part}{current_grade}·短期刷题班{suffix}"


def build_small_class_name(class_type: str, current_grade: str, student_names: list[str], is_bridge: bool, bridge_target: str = "", stage: str = "", subject: str = "", cohort_year: int = 0, show_cohort_year: bool = True) -> str:
    normalized_names = [str(name or "").strip() for name in student_names if str(name or "").strip()]
    if not current_grade or not normalized_names:
        return ""
    if class_type == "1v1":
        name_part = normalized_names[0]
    else:
        name_part = "".join(name[:1] for name in normalized_names)
    suffix = f"·{bridge_short_label(bridge_target, stage)}" if is_bridge else ""
    subject_prefix = f"{subject.strip()}·" if subject and subject.strip() else ""
    cohort_part = f"·{cohort_stage_short_label(display_cohort_stage(stage, is_bridge, bridge_target))}{cohort_year}级" if show_cohort_year and cohort_year else ""
    return f"{subject_prefix}{class_type}{cohort_part}·{current_grade}·{name_part}{suffix}"


def _class_row_to_dict(row) -> dict:
    item = dict(row)
    item["current_grade"] = item.get("current_grade") or item.get("grade") or ""
    item["stage"] = item.get("stage") or infer_class_stage(item["current_grade"])
    item["class_type"] = item.get("class_type") or "group"
    item["class_number"] = str(item.get("class_number") or "")
    item["cohort_year"] = int(item.get("cohort_year") or 0)
    item["show_cohort_year"] = bool(item.get("show_cohort_year", 1))
    item["is_bridge"] = bool(item.get("is_bridge") or 0)
    item["bridge_target"] = item.get("bridge_target") or ""
    item["content_track"] = item.get("content_track") or ""
    item["last_promoted_at"] = item.get("last_promoted_at") or ""
    item["lifecycle_status"] = item.get("lifecycle_status") or CLASS_LIFECYCLE_ACTIVE
    item["lifecycle_status_updated_at"] = item.get("lifecycle_status_updated_at") or ""
    item["graduated_at"] = item.get("graduated_at") or ""
    item["graduation_academic_year_start"] = int(item.get("graduation_academic_year_start") or 0)
    if item["class_type"] == "group" and item["cohort_year"] and item["current_grade"] and item["class_number"]:
        item["name"] = build_group_class_name(
            item.get("subject") or "",
            item["cohort_year"],
            item["current_grade"],
            item["class_number"],
            item["is_bridge"],
            item["show_cohort_year"],
            item["bridge_target"],
            item["stage"],
        )
    return item


def _class_lifecycle_where_clause(scope: str, table_alias: str = "c") -> str:
    normalized_scope = (scope or "current").strip().lower()
    column = f"{table_alias}.lifecycle_status"
    if normalized_scope in {"all", "any"}:
        return ""
    if normalized_scope in {"history", "archived", "graduated"}:
        return f"COALESCE(NULLIF({column}, ''), '{CLASS_LIFECYCLE_ACTIVE}') != '{CLASS_LIFECYCLE_ACTIVE}'"
    return f"COALESCE(NULLIF({column}, ''), '{CLASS_LIFECYCLE_ACTIVE}') = '{CLASS_LIFECYCLE_ACTIVE}'"


def _lesson_class_lifecycle_where_clause(scope: str, class_alias: str = "c", lesson_alias: str = "l") -> str:
    normalized_scope = (scope or "current").strip().lower()
    column = f"{class_alias}.lifecycle_status"
    if normalized_scope in {"all", "any"}:
        return ""
    if normalized_scope in {"history", "archived", "graduated"}:
        return (
            f"COALESCE({lesson_alias}.class_id, 0) > 0 "
            f"AND COALESCE(NULLIF({column}, ''), '{CLASS_LIFECYCLE_ACTIVE}') != '{CLASS_LIFECYCLE_ACTIVE}'"
        )
    return (
        f"(COALESCE({lesson_alias}.class_id, 0) = 0 "
        f"OR COALESCE(NULLIF({column}, ''), '{CLASS_LIFECYCLE_ACTIVE}') = '{CLASS_LIFECYCLE_ACTIVE}')"
    )


def _build_class_payload(
    name: str,
    subject: str = "",
    grade: str = "",
    *,
    stage: str = "",
    current_grade: str = "",
    class_number: str = "",
    class_type: str = "group",
    student_names: list[str] | None = None,
    cohort_year: int | None = None,
    show_cohort_year: bool = False,
    is_bridge: bool = False,
    bridge_target: str = "",
    content_track: str = "",
    today: str | None = None,
) -> dict:
    normalized_grade = normalize_class_grade(current_grade or grade)
    normalized_stage = stage or infer_class_stage(normalized_grade)
    normalized_class_type = (class_type or "group").strip() or "group"
    normalized_class_number = str(class_number or "").strip()
    normalized_cohort_year = int(cohort_year or 0)
    normalized_bridge_target = serialize_bridge_target(*parse_bridge_target(bridge_target, normalized_stage)) if is_bridge else (bridge_target or "").strip()
    cohort_stage = parse_bridge_target(normalized_bridge_target, normalized_stage)[1] if is_bridge else normalized_stage
    if normalized_grade and not normalized_cohort_year:
        normalized_cohort_year = infer_cohort_year_for_stage(normalized_grade, cohort_stage, today)
    display_name = (name or "").strip()
    if normalized_class_type == "group" and normalized_grade and normalized_class_number and normalized_cohort_year:
        display_name = build_group_class_name(subject, normalized_cohort_year, normalized_grade, normalized_class_number, is_bridge, show_cohort_year, normalized_bridge_target, normalized_stage)
    elif normalized_class_type == "short_term_drill":
        display_name = build_short_term_drill_class_name(subject, normalized_cohort_year, normalized_grade, is_bridge, normalized_bridge_target, normalized_stage, show_cohort_year) or display_name
    elif normalized_class_type != "group":
        display_name = build_small_class_name(normalized_class_type, normalized_grade, student_names or [], is_bridge, normalized_bridge_target, normalized_stage, subject, normalized_cohort_year, show_cohort_year) or display_name
    return {
        "name": display_name,
        "class_type": normalized_class_type,
        "subject": (subject or "").strip(),
        "grade": normalized_grade or (grade or "").strip(),
        "stage": normalized_stage,
        "current_grade": normalized_grade,
        "class_number": normalized_class_number,
        "cohort_year": normalized_cohort_year,
        "show_cohort_year": 1 if show_cohort_year else 0,
        "is_bridge": 1 if is_bridge else 0,
        "bridge_target": normalized_bridge_target,
        "content_track": (content_track or parse_bridge_target(normalized_bridge_target, normalized_stage)[1] or "").strip(),
    }


def save_class(name: str, subject: str = "", grade: str = "",
               teacher_name: str = "", teacher_email: str = "", organization_id: Optional[int] = None,
               stage: str = "", current_grade: str = "", class_number: str = "",
               class_type: str = "group", student_ids: Optional[list[int]] = None,
               cohort_year: int | None = None, show_cohort_year: bool = False, is_bridge: bool = False, bridge_target: str = "",
               content_track: str = "", teacher_user_id: Optional[int] = None, today: str | None = None) -> int:
    normalized_student_ids = [int(student_id) for student_id in (student_ids or []) if int(student_id or 0) > 0]
    with get_conn() as conn:
        if organization_id is None:
            organization_id = _ensure_organization(conn, DEFAULT_ORGANIZATION_NAME)["id"]
        student_names: list[str] = []
        if normalized_student_ids:
            placeholders = ",".join("?" for _ in normalized_student_ids)
            rows = conn.execute(
                f"SELECT id, name FROM students WHERE organization_id=? AND id IN ({placeholders}) ORDER BY name",
                (organization_id, *normalized_student_ids),
            ).fetchall()
            if len(rows) != len(set(normalized_student_ids)):
                raise ValueError("invalid student_ids")
            student_names = [row["name"] for row in rows]
        payload = _build_class_payload(
            name,
            subject,
            grade,
            stage=stage,
            current_grade=current_grade,
            class_number=class_number,
            class_type=class_type,
            student_names=student_names,
            cohort_year=cohort_year,
            show_cohort_year=show_cohort_year,
            is_bridge=is_bridge,
            bridge_target=bridge_target,
            content_track=content_track,
            today=today,
        )
        cur = conn.execute(
            """
            INSERT INTO classes (
                organization_id, name, subject, subject_key, grade, teacher_name, teacher_email,
                stage, class_type, current_grade, class_number, cohort_year, show_cohort_year, is_bridge, bridge_target, content_track
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                organization_id, payload["name"], payload["subject"], canonicalize_class_subject_key(payload["subject"]),
                payload["grade"], teacher_name, teacher_email,
                payload["stage"], payload["class_type"], payload["current_grade"], payload["class_number"], payload["cohort_year"],
                payload["show_cohort_year"], payload["is_bridge"], payload["bridge_target"], payload["content_track"],
            )
        )
        class_id = cur.lastrowid
        for student_id in normalized_student_ids:
            conn.execute("INSERT OR IGNORE INTO class_students (class_id, student_id) VALUES (?, ?)", (class_id, student_id))
        if teacher_user_id is not None:
            conn.execute("INSERT INTO user_classes (user_id, class_id) VALUES (?, ?)", (teacher_user_id, class_id))
            _sync_class_teacher_metadata(conn, [class_id])
    record_class_history(class_id, "created", after=get_class(class_id))
    return class_id


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
        return _class_row_to_dict(row) if row else None


def list_classes(scope: str = "current"):
    lifecycle_clause = _class_lifecycle_where_clause(scope, "c")
    where_sql = f"WHERE {lifecycle_clause}" if lifecycle_clause else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT c.*, COUNT(DISTINCT l.id) as lesson_count,
                   COUNT(DISTINCT s_count.id) as student_count,
                   (
                       SELECT uc.user_id
                       FROM user_classes uc
                       WHERE uc.class_id = c.id
                       ORDER BY uc.user_id
                       LIMIT 1
                   ) AS teacher_user_id
            FROM classes c
            LEFT JOIN lessons l ON l.class_id = c.id
            LEFT JOIN class_students cs ON cs.class_id = c.id
            LEFT JOIN students s_count ON s_count.id = cs.student_id AND s_count.status='active'
            {where_sql}
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        ).fetchall()
        return [_class_row_to_dict(r) for r in rows]


def _remove_active_curriculum_assignments_for_class_scope_change(
    conn: sqlite3.Connection,
    *,
    class_id: int,
    before_subject_key: str,
    after_subject_key: str,
    before_grade: str,
    after_grade: str,
    actor_user_id: int | None,
) -> list[int]:
    subject_changed = str(before_subject_key or "") != str(after_subject_key or "")
    grade_changed = normalize_class_grade(before_grade) != normalize_class_grade(after_grade)
    if not subject_changed and not grade_changed:
        return []
    assignments = conn.execute(
        """
        SELECT assignment.*, version.package_id, version.version_key,
               book.canonical_name AS book_name, book.grade_key,
               book.semester_key
        FROM curriculum_class_assignments assignment
        JOIN curriculum_versions version ON version.id=assignment.version_id
        JOIN curriculum_nodes book ON book.id=assignment.book_node_id
        WHERE assignment.class_id=? AND assignment.status='active'
        ORDER BY assignment.id
        """,
        (int(class_id),),
    ).fetchall()
    if not assignments:
        return []
    ended_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    assignment_ids = [int(item["id"]) for item in assignments]
    placeholders = ",".join("?" for _ in assignment_ids)
    conn.execute(
        f"""
        UPDATE curriculum_class_assignments
        SET status='removed', ended_at=?
        WHERE id IN ({placeholders}) AND status='active'
        """,
        (ended_at, *assignment_ids),
    )
    from curriculum_registry import _audit as _audit_curriculum

    version_ids = {int(item["version_id"]) for item in assignments}
    package_ids = {int(item["package_id"]) for item in assignments}
    reasons = []
    if subject_changed:
        reasons.append("subject changed")
    if grade_changed:
        reasons.append("grade changed")
    _audit_curriculum(
        conn,
        action="remove_stale_class_assignments",
        target_type="class_curriculum",
        target_key=str(class_id),
        actor_user_id=actor_user_id,
        organization_id=int(assignments[0]["organization_id"]),
        package_id=next(iter(package_ids)) if len(package_ids) == 1 else None,
        version_id=next(iter(version_ids)) if len(version_ids) == 1 else None,
        class_id=int(class_id),
        before={"assignments": [dict(item) for item in assignments]},
        after={
            "status": "removed",
            "assignment_ids": assignment_ids,
            "subject_key": str(after_subject_key or ""),
            "grade": normalize_class_grade(after_grade),
        },
        note=f"Class {' and '.join(reasons)}; stale manual curriculum overrides were removed.",
    )
    return assignment_ids


def update_class(class_id: int, name: str, subject: str = "", grade: str = "",
                 teacher_name: Optional[str] = None, teacher_email: Optional[str] = None,
                 stage: str = "", current_grade: str = "", class_number: str = "",
                 class_type: str = "group",
                 cohort_year: int | None = None, show_cohort_year: bool | None = None, is_bridge: bool = False, bridge_target: str = "",
                 content_track: str = "", today: str | None = None,
                 actor_user_id: int | None = None):
    before = get_class(class_id)
    with get_conn() as conn:
        student_rows = conn.execute(
            """
            SELECT s.name
            FROM class_students cs
            JOIN students s ON s.id = cs.student_id
            WHERE cs.class_id=? AND s.status='active'
            ORDER BY s.name
            """,
            (class_id,),
        ).fetchall()
    payload = _build_class_payload(
        name,
        subject,
        grade,
        stage=stage or (before or {}).get("stage", ""),
        current_grade=current_grade or grade,
        class_number=class_number or (before or {}).get("class_number", ""),
        class_type=class_type or (before or {}).get("class_type", "group"),
        student_names=[row["name"] for row in student_rows],
        cohort_year=cohort_year if cohort_year is not None else (before or {}).get("cohort_year", 0),
        show_cohort_year=show_cohort_year if show_cohort_year is not None else (before or {}).get("show_cohort_year", True),
        is_bridge=is_bridge,
        bridge_target=bridge_target or (before or {}).get("bridge_target", ""),
        content_track=content_track or (before or {}).get("content_track", ""),
        today=today,
    )
    next_subject_key = canonicalize_class_subject_key(payload["subject"])
    with get_conn() as conn:
        bound_teacher_row = conn.execute(
            "SELECT user_id FROM user_classes WHERE class_id=? ORDER BY user_id LIMIT 1",
            (class_id,),
        ).fetchone()

        if bound_teacher_row:
            conn.execute(
                """
                UPDATE classes
                SET name=?, subject=?, subject_key=?, grade=?, teacher_email='', stage=?, class_type=?, current_grade=?,
                    class_number=?, cohort_year=?, show_cohort_year=?, is_bridge=?, bridge_target=?, content_track=?
                WHERE id=?
                """,
                (
                    payload["name"], payload["subject"], next_subject_key, payload["grade"],
                    payload["stage"], payload["class_type"], payload["current_grade"],
                    payload["class_number"], payload["cohort_year"], payload["show_cohort_year"], payload["is_bridge"], payload["bridge_target"],
                    payload["content_track"], class_id,
                )
            )
            _sync_class_teacher_metadata(conn, [class_id])
        else:
            conn.execute(
            """
            UPDATE classes
            SET name=?,
                subject=?,
                subject_key=?,
                grade=?,
                stage=?,
                class_type=?,
                current_grade=?,
                class_number=?,
                cohort_year=?,
                show_cohort_year=?,
                is_bridge=?,
                bridge_target=?,
                content_track=?,
                teacher_name=COALESCE(?, teacher_name),
                teacher_email=COALESCE(?, teacher_email)
            WHERE id=?
            """,
            (
                payload["name"], payload["subject"], next_subject_key, payload["grade"],
                payload["stage"], payload["class_type"], payload["current_grade"],
                payload["class_number"], payload["cohort_year"], payload["show_cohort_year"], payload["is_bridge"], payload["bridge_target"],
                payload["content_track"], teacher_name, teacher_email, class_id,
            )
            )
        _remove_active_curriculum_assignments_for_class_scope_change(
            conn,
            class_id=int(class_id),
            before_subject_key=str((before or {}).get("subject_key") or ""),
            after_subject_key=str(next_subject_key or ""),
            before_grade=str(
                (before or {}).get("current_grade") or (before or {}).get("grade") or ""
            ),
            after_grade=str(payload["current_grade"] or payload["grade"] or ""),
            actor_user_id=actor_user_id,
        )
    record_class_history(
        class_id,
        "updated",
        before=before,
        after=get_class(class_id),
        actor_user_id=actor_user_id,
    )


def record_class_history(class_id: int, action: str, before: dict | None = None, after: dict | None = None,
                         note: str = "", actor_user_id: int | None = None) -> None:
    cls = after if after and after.get("organization_id") else get_class(class_id)
    if not cls:
        return
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO class_history (organization_id, class_id, action, before_json, after_json, note, actor_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cls["organization_id"],
                class_id,
                action,
                json.dumps(before or {}, ensure_ascii=False),
                json.dumps(after or {}, ensure_ascii=False),
                note,
                actor_user_id,
            ),
        )


def list_class_history(class_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM class_history WHERE class_id=? ORDER BY created_at ASC, id ASC", (class_id,)).fetchall()
    return [dict(row) for row in rows]


def record_student_class_history(student_id: int, class_id: int, action: str, before: dict | None = None, after: dict | None = None,
                                 note: str = "", actor_user_id: int | None = None) -> None:
    cls = get_class(class_id)
    if not cls:
        return
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO student_class_history (organization_id, student_id, class_id, action, before_json, after_json, note, actor_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cls["organization_id"],
                student_id,
                class_id,
                action,
                json.dumps(before or {}, ensure_ascii=False),
                json.dumps(after or {}, ensure_ascii=False),
                note,
                actor_user_id,
            ),
        )


def list_student_class_history(student_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM student_class_history WHERE student_id=? ORDER BY created_at ASC, id ASC", (student_id,)).fetchall()
    return [dict(row) for row in rows]


def bridge_crosses_target_stage(current_grade: str, next_grade: str, bridge_target: str) -> bool:
    _, to_stage = parse_bridge_target(bridge_target, infer_class_stage(current_grade))
    if current_grade == "六年级" and next_grade == "七年级":
        return to_stage == "初中"
    if current_grade == "九年级" and next_grade == "高一":
        return to_stage == "高中"
    return False


def promote_classes_for_academic_year(today: str | None = None) -> dict:
    today_value = today or date.today().isoformat()
    academic_year_start = current_school_year_start(today_value)
    promoted_ids: list[int] = []
    pending_ids: list[int] = []
    skipped_ids: list[int] = []
    already_executed_org_ids: list[int] = []
    summary_by_org: dict[int, dict[str, int]] = {}
    history_events: list[tuple[int, str, dict | None, dict | None]] = []
    with get_conn() as conn:
        org_rows = conn.execute(
            """
            SELECT DISTINCT organization_id
            FROM classes
            WHERE organization_id IS NOT NULL
            ORDER BY organization_id
            """
        ).fetchall()
        for org_row in org_rows:
            existing = conn.execute(
                """
                SELECT id
                FROM academic_year_promotion_runs
                WHERE organization_id=? AND academic_year_start=? AND job_type=?
                """,
                (org_row["organization_id"], academic_year_start, ANNUAL_GRADE_PROMOTION_JOB_TYPE),
            ).fetchone()
            if existing:
                already_executed_org_ids.append(org_row["organization_id"])
        executable_org_ids = [
            row["organization_id"]
            for row in org_rows
            if row["organization_id"] not in already_executed_org_ids
        ]
        if not executable_org_ids:
            return {
                "promoted_ids": [],
                "pending_ids": [],
                "skipped_ids": [],
                "already_executed_org_ids": already_executed_org_ids,
            }
        summary_by_org = {
            org_id: {"promoted": 0, "pending_graduation": 0, "skipped_unknown_grade": 0}
            for org_id in executable_org_ids
        }

        placeholders = ", ".join("?" for _ in executable_org_ids)
        student_rows = conn.execute(
            f"""
            SELECT cs.class_id, s.name
            FROM class_students cs
            JOIN students s ON s.id = cs.student_id
            JOIN classes c ON c.id = cs.class_id
            WHERE c.organization_id IN ({placeholders}) AND s.status='active'
            ORDER BY cs.class_id, s.name
            """,
            executable_org_ids,
        ).fetchall()
        student_names_by_class: dict[int, list[str]] = {}
        for student_row in student_rows:
            student_names_by_class.setdefault(student_row["class_id"], []).append(student_row["name"])

        rows = conn.execute(
            f"""
            SELECT *
            FROM classes
            WHERE organization_id IN ({placeholders})
              AND COALESCE(NULLIF(lifecycle_status, ''), ?) = ?
            ORDER BY id
            """,
            (*executable_org_ids, CLASS_LIFECYCLE_ACTIVE, CLASS_LIFECYCLE_ACTIVE),
        ).fetchall()
        for row in rows:
            item = _class_row_to_dict(row)
            current_grade = normalize_class_grade(item.get("current_grade") or item.get("grade") or "")
            next_grade = PROMOTION_NEXT_GRADE.get(current_grade)
            is_bridge = bool(item.get("is_bridge"))
            crosses_bridge = bool(next_grade) and is_bridge and bridge_crosses_target_stage(current_grade, next_grade, item.get("bridge_target") or "")
            if current_grade in GRADUATION_GRADES and not crosses_bridge:
                pending_ids.append(item["id"])
                summary_by_org[item["organization_id"]]["pending_graduation"] += 1
                after = {
                    **item,
                    "lifecycle_status": CLASS_LIFECYCLE_PENDING_GRADUATION,
                    "lifecycle_status_updated_at": today_value,
                    "graduation_academic_year_start": academic_year_start,
                    "last_promoted_at": today_value,
                }
                conn.execute(
                    """
                    UPDATE classes
                    SET lifecycle_status=?, lifecycle_status_updated_at=?,
                        graduation_academic_year_start=?, last_promoted_at=?
                    WHERE id=?
                    """,
                    (
                        CLASS_LIFECYCLE_PENDING_GRADUATION,
                        today_value,
                        academic_year_start,
                        today_value,
                        item["id"],
                    ),
                )
                history_events.append((item["id"], "pending_graduation", item, after))
                continue
            if not next_grade:
                skipped_ids.append(item["id"])
                summary_by_org[item["organization_id"]]["skipped_unknown_grade"] += 1
                history_events.append((item["id"], "annual_promotion_skipped", item, {"reason": "unknown_grade", "grade": current_grade}))
                continue
            next_is_bridge = is_bridge and not crosses_bridge
            next_stage = infer_class_stage(next_grade)
            class_number = item.get("class_number") or ""
            next_bridge_target = item.get("bridge_target") or "" if next_is_bridge else ""
            next_content_track = item.get("content_track") or "" if next_is_bridge else ""
            next_cohort_year = (
                infer_cohort_year_for_stage(next_grade, next_stage, today_value)
                if crosses_bridge
                else item["cohort_year"] or infer_cohort_year_for_stage(next_grade, next_stage, today_value)
            )
            if item.get("class_type") == "group":
                next_name = build_group_class_name(
                    item.get("subject") or "",
                    next_cohort_year,
                    next_grade,
                    class_number,
                    next_is_bridge,
                    item.get("show_cohort_year", True),
                    next_bridge_target,
                    next_stage,
                ) if class_number else item["name"]
            else:
                next_name = build_small_class_name(
                    item.get("class_type") or "1v1",
                    next_grade,
                    student_names_by_class.get(item["id"], []),
                    next_is_bridge,
                    next_bridge_target,
                    next_stage,
                    item.get("subject") or "",
                    next_cohort_year,
                    item.get("show_cohort_year", True),
                ) or item["name"]
            conn.execute(
                """
                UPDATE classes
                SET grade=?, current_grade=?, stage=?, name=?, cohort_year=?, is_bridge=?,
                    bridge_target=?, content_track=?, last_promoted_at=?,
                    lifecycle_status=?, lifecycle_status_updated_at=?, graduation_academic_year_start=0
                WHERE id=?
                """,
                (
                    next_grade,
                    next_grade,
                    next_stage,
                    next_name,
                    next_cohort_year,
                    1 if next_is_bridge else 0,
                    next_bridge_target,
                    next_content_track,
                    today_value,
                    CLASS_LIFECYCLE_ACTIVE,
                    today_value,
                    item["id"],
                ),
            )
            _remove_active_curriculum_assignments_for_class_scope_change(
                conn,
                class_id=int(item["id"]),
                before_subject_key=str(item.get("subject_key") or ""),
                after_subject_key=str(item.get("subject_key") or ""),
                before_grade=current_grade,
                after_grade=next_grade,
                actor_user_id=None,
            )
            promoted_ids.append(item["id"])
            summary_by_org[item["organization_id"]]["promoted"] += 1
            history_events.append((item["id"], "annual_promoted", item, {"current_grade": next_grade, "name": next_name, "is_bridge": next_is_bridge}))

        for org_id in executable_org_ids:
            summary = {
                **summary_by_org[org_id],
                "effective_date": today_value,
            }
            conn.execute(
                """
                INSERT INTO academic_year_promotion_runs
                    (organization_id, academic_year_start, job_type, effective_date, status, summary_json, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    org_id,
                    academic_year_start,
                    ANNUAL_GRADE_PROMOTION_JOB_TYPE,
                    today_value,
                    "completed_with_skips" if summary["skipped_unknown_grade"] else "completed",
                    json.dumps(summary, ensure_ascii=False),
                    f"{today_value} annual grade promotion",
                ),
            )
    for class_id, action, before, after in history_events:
        record_class_history(class_id, action, before=before, after=after)
    return {
        "promoted_ids": promoted_ids,
        "pending_ids": pending_ids,
        "skipped_ids": skipped_ids,
        "already_executed_org_ids": already_executed_org_ids,
    }


def delete_class(class_id: int) -> dict:
    """Delete a class (lessons are kept but unlinked)."""
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        import master_data

        master_data.ensure_schema(conn)
        class_row = conn.execute(
            "SELECT id, organization_id FROM classes WHERE id=?",
            (class_id,),
        ).fetchone()
        if not class_row:
            raise LookupError("class not found")
        has_commentary_history = conn.execute(
            """
            SELECT 1
            FROM class_commentary_generations
            WHERE class_id=?
            LIMIT 1
            """,
            (class_id,),
        ).fetchone()
        if has_commentary_history:
            memory_cleanup = _prepare_class_commentary_memory_cleanup_for_scope_conn(
                conn,
                organization_id=int(class_row["organization_id"]),
                class_id=class_id,
            )
            conn.execute(
                """
                UPDATE classes
                SET lifecycle_status=?, lifecycle_status_updated_at=?
                WHERE id=?
                """,
                (
                    CLASS_LIFECYCLE_ARCHIVED,
                    _class_commentary_utc_timestamp(),
                    class_id,
                ),
            )
            return {
                "action": "archived",
                "class_id": class_id,
                "memory_cleanup": memory_cleanup,
            }
        conn.execute("UPDATE lessons SET class_id=NULL WHERE class_id=?", (class_id,))
        conn.execute("DELETE FROM class_commentary_tasks WHERE class_id=?", (class_id,))
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
        return {"action": "deleted", "class_id": class_id, "memory_cleanup": None}


def _normalize_course_calendar_date(date_str: str) -> str:
    normalized = str(date_str or "").strip()
    try:
        datetime.strptime(normalized, "%Y-%m-%d")
    except ValueError:
        raise ValueError("date must use YYYY-MM-DD")
    return normalized


def _normalize_course_calendar_time_block(time_block: str) -> str:
    normalized = str(time_block or "").strip()
    if normalized not in COURSE_CALENDAR_TIME_BLOCKS:
        raise ValueError("time_block is invalid")
    return normalized


def _normalize_course_calendar_start_offset_minutes(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("start_offset_minutes must be an integer")
    if value < -120 or value > 120:
        raise ValueError("start_offset_minutes must be between -120 and 120")
    return value


def _serialize_course_calendar_schedule_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    return {
        "id": item["id"],
        "organization_id": item["organization_id"],
        "class_id": item["class_id"],
        "date": item["date"],
        "time_block": item["time_block"],
        "start_offset_minutes": item["start_offset_minutes"],
        "created_by": item["created_by"],
        "created_at": item["created_at"],
        "class_name": item.get("class_name", ""),
        "subject": item.get("subject", ""),
        "grade": item.get("grade", ""),
        "teacher_name": item.get("teacher_name", ""),
        "teacher_email": item.get("teacher_email", ""),
        "teacher_user_id": item.get("teacher_user_id"),
    }


def _course_calendar_schedule_select_sql() -> str:
    return """
        SELECT s.*,
               c.name AS class_name,
               c.subject,
               c.grade,
               c.teacher_name,
               c.teacher_email,
               (
                   SELECT uc.user_id
                   FROM user_classes uc
                   WHERE uc.class_id = c.id
                   ORDER BY uc.user_id
                   LIMIT 1
               ) AS teacher_user_id
        FROM course_calendar_schedules s
        JOIN classes c ON c.id = s.class_id
    """


def get_course_calendar_schedule(schedule_id: int):
    with get_conn() as conn:
        row = conn.execute(
            f"{_course_calendar_schedule_select_sql()} WHERE s.id=?",
            (schedule_id,),
        ).fetchone()
        return _serialize_course_calendar_schedule_row(row) if row else None


def list_course_calendar_schedules_for_actor(actor_user: dict, start_date: str = "", end_date: str = "") -> list[dict]:
    normalized_start = _normalize_course_calendar_date(start_date) if start_date else ""
    normalized_end = _normalize_course_calendar_date(end_date) if end_date else ""
    if normalized_start and normalized_end and normalized_start > normalized_end:
        raise ValueError("start_date must be before or equal to end_date")

    query_sql = _course_calendar_schedule_select_sql()
    where_clauses = []
    params: list[object] = []

    if (actor_user or {}).get("role") != SUPER_OWNER_ROLE:
        where_clauses.append("s.organization_id=?")
        params.append(actor_user["organization_id"])

    where_clauses.append(f"COALESCE(NULLIF(c.lifecycle_status, ''), '{CLASS_LIFECYCLE_ACTIVE}') = '{CLASS_LIFECYCLE_ACTIVE}'")

    if (actor_user or {}).get("role") == MEMBER_ROLE:
        class_ids = get_user_class_ids(actor_user["id"])
        if not class_ids:
            return []
        placeholders = ", ".join("?" for _ in class_ids)
        where_clauses.append(f"s.class_id IN ({placeholders})")
        params.extend(class_ids)

    if normalized_start:
        where_clauses.append("s.date>=?")
        params.append(normalized_start)
    if normalized_end:
        where_clauses.append("s.date<=?")
        params.append(normalized_end)

    if where_clauses:
        query_sql += " WHERE " + " AND ".join(where_clauses)
    query_sql += " ORDER BY s.date ASC, s.time_block ASC, s.id ASC"

    with get_conn() as conn:
        rows = conn.execute(query_sql, params).fetchall()
        return [_serialize_course_calendar_schedule_row(row) for row in rows]


def create_course_calendar_schedule(*, class_id: int, date_str: str, time_block: str, created_by: Optional[int], start_offset_minutes: object = None):
    normalized_date = _normalize_course_calendar_date(date_str)
    normalized_time_block = _normalize_course_calendar_time_block(time_block)
    normalized_start_offset_minutes = _normalize_course_calendar_start_offset_minutes(start_offset_minutes)
    with get_conn() as conn:
        class_row = conn.execute(
            "SELECT id, organization_id, lifecycle_status FROM classes WHERE id=?",
            (class_id,),
        ).fetchone()
        if not class_row:
            raise LookupError("class not found")
        if (class_row["lifecycle_status"] or CLASS_LIFECYCLE_ACTIVE) != CLASS_LIFECYCLE_ACTIVE:
            raise ValueError("class is not active")

        conn.execute(
            """
            INSERT OR IGNORE INTO course_calendar_schedules
                (organization_id, class_id, date, time_block, start_offset_minutes, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                class_row["organization_id"],
                class_id,
                normalized_date,
                normalized_time_block,
                normalized_start_offset_minutes,
                created_by,
            ),
        )
        row = conn.execute(
            f"{_course_calendar_schedule_select_sql()} WHERE s.class_id=? AND s.date=? AND s.time_block=?",
            (class_id, normalized_date, normalized_time_block),
        ).fetchone()
        return _serialize_course_calendar_schedule_row(row)


def delete_course_calendar_schedule(schedule_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM course_calendar_schedules WHERE id=?", (schedule_id,))
        return cur.rowcount > 0


def _normalize_course_calendar_custom_item_title(value: object) -> str:
    title = str(value or "").strip()
    if not title:
        raise ValueError("title is required")
    if len(title) > 80:
        raise ValueError("title must be at most 80 characters")
    return title


def _normalize_course_calendar_custom_item_time_range(value: object) -> str:
    time_range = str(value or "").strip()
    if not time_range:
        raise ValueError("time_range is required")
    if len(time_range) > 40:
        raise ValueError("time_range must be at most 40 characters")
    return time_range


def _normalize_course_calendar_custom_item_note(value: object) -> str:
    note = str(value or "").strip()
    if len(note) > 500:
        raise ValueError("note must be at most 500 characters")
    return note


def _normalize_course_calendar_custom_item_visibility(value: object) -> str:
    visibility = str(value or "private").strip()
    if visibility not in {"private", "organization"}:
        raise ValueError("visibility is invalid")
    return visibility


def _serialize_course_calendar_custom_item_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    return {
        "id": item["id"],
        "organization_id": item["organization_id"],
        "title": item["title"],
        "time_range": item["time_range"],
        "note": item.get("note", ""),
        "visibility": item.get("visibility", "private"),
        "created_by": item.get("created_by"),
        "created_at": item.get("created_at"),
    }


def _can_delete_course_calendar_custom_item(actor_user: dict, item: dict) -> bool:
    if item.get("created_by") == actor_user.get("id"):
        return True
    if item.get("created_by") is None and actor_user.get("role") in {SUPER_OWNER_ROLE, OWNER_ROLE, ADMIN_ROLE}:
        return item.get("organization_id") == actor_user.get("organization_id")
    return False


def _can_access_course_calendar_custom_item(actor_user: dict, item: dict) -> bool:
    if actor_user.get("role") == SUPER_OWNER_ROLE:
        if item.get("visibility") == "organization":
            return item.get("organization_id") == actor_user.get("organization_id")
        return item.get("created_by") == actor_user.get("id")
    if item.get("organization_id") != actor_user.get("organization_id"):
        return False
    if actor_user.get("role") in {OWNER_ROLE, ADMIN_ROLE}:
        return item.get("created_by") == actor_user.get("id")
    return item.get("created_by") == actor_user.get("id") or item.get("visibility") == "organization"


def get_course_calendar_custom_item(item_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM course_calendar_custom_items WHERE id=?", (item_id,)).fetchone()
        return _serialize_course_calendar_custom_item_row(row) if row else None


def list_course_calendar_custom_items_for_actor(actor_user: dict) -> list[dict]:
    query_sql = "SELECT * FROM course_calendar_custom_items"
    params: list[object] = []
    if actor_user.get("role") == MEMBER_ROLE:
        query_sql += " WHERE organization_id=? AND (created_by=? OR visibility='organization')"
        params.extend([actor_user["organization_id"], actor_user["id"]])
    elif actor_user.get("role") == SUPER_OWNER_ROLE:
        query_sql += " WHERE created_by=? OR (organization_id=? AND visibility='organization')"
        params.extend([actor_user["id"], actor_user["organization_id"]])
    else:
        query_sql += " WHERE organization_id=? AND created_by=?"
        params.extend([actor_user["organization_id"], actor_user["id"]])
    query_sql += " ORDER BY created_at DESC, id DESC"

    with get_conn() as conn:
        rows = conn.execute(query_sql, params).fetchall()
        items = [_serialize_course_calendar_custom_item_row(row) for row in rows]
        for item in items:
            item["can_delete"] = _can_delete_course_calendar_custom_item(actor_user, item)
        return items


def create_course_calendar_custom_item(*, actor_user: dict, title: object, time_range: object, note: object = "", visibility: object = "private"):
    normalized_title = _normalize_course_calendar_custom_item_title(title)
    normalized_time_range = _normalize_course_calendar_custom_item_time_range(time_range)
    normalized_note = _normalize_course_calendar_custom_item_note(note)
    normalized_visibility = _normalize_course_calendar_custom_item_visibility(visibility)
    if actor_user.get("role") == MEMBER_ROLE and normalized_visibility != "private":
        raise PermissionError("members can only create private custom items")

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO course_calendar_custom_items
                (organization_id, title, time_range, note, visibility, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                actor_user["organization_id"],
                normalized_title,
                normalized_time_range,
                normalized_note,
                normalized_visibility,
                actor_user["id"],
            ),
        )
        row = conn.execute("SELECT * FROM course_calendar_custom_items WHERE id=?", (cur.lastrowid,)).fetchone()
        item = _serialize_course_calendar_custom_item_row(row)
        item["can_delete"] = True
        return item


def delete_course_calendar_custom_item(item_id: int) -> bool:
    with get_conn() as conn:
        conn.execute("DELETE FROM course_calendar_custom_schedules WHERE custom_item_id=?", (item_id,))
        cur = conn.execute("DELETE FROM course_calendar_custom_items WHERE id=?", (item_id,))
        return cur.rowcount > 0


def _serialize_course_calendar_custom_schedule_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    return {
        "id": item["id"],
        "organization_id": item["organization_id"],
        "custom_item_id": item["custom_item_id"],
        "date": item["date"],
        "time_block": item["time_block"],
        "start_offset_minutes": item["start_offset_minutes"],
        "created_by": item.get("created_by"),
        "created_at": item.get("created_at"),
        "title": item.get("title", ""),
        "time_range": item.get("time_range", ""),
        "note": item.get("note", ""),
        "visibility": item.get("visibility", "private"),
    }


def _course_calendar_custom_schedule_select_sql() -> str:
    return """
        SELECT s.*,
               i.title,
               i.time_range,
               i.note,
               i.visibility
        FROM course_calendar_custom_schedules s
        JOIN course_calendar_custom_items i ON i.id = s.custom_item_id
    """


def get_course_calendar_custom_schedule(schedule_id: int):
    with get_conn() as conn:
        row = conn.execute(
            f"{_course_calendar_custom_schedule_select_sql()} WHERE s.id=?",
            (schedule_id,),
        ).fetchone()
        return _serialize_course_calendar_custom_schedule_row(row) if row else None


def list_course_calendar_custom_schedules_for_actor(actor_user: dict, start_date: str = "", end_date: str = "") -> list[dict]:
    normalized_start = _normalize_course_calendar_date(start_date) if start_date else ""
    normalized_end = _normalize_course_calendar_date(end_date) if end_date else ""
    if normalized_start and normalized_end and normalized_start > normalized_end:
        raise ValueError("start_date must be before or equal to end_date")

    query_sql = _course_calendar_custom_schedule_select_sql()
    where_clauses = []
    params: list[object] = []
    if actor_user.get("role") == MEMBER_ROLE:
        where_clauses.append("s.organization_id=? AND (i.created_by=? OR i.visibility='organization')")
        params.extend([actor_user["organization_id"], actor_user["id"]])
    elif actor_user.get("role") == SUPER_OWNER_ROLE:
        where_clauses.append("i.created_by=? OR (s.organization_id=? AND i.visibility='organization')")
        params.extend([actor_user["id"], actor_user["organization_id"]])
    else:
        where_clauses.append("s.organization_id=? AND i.created_by=?")
        params.extend([actor_user["organization_id"], actor_user["id"]])

    if normalized_start:
        where_clauses.append("s.date>=?")
        params.append(normalized_start)
    if normalized_end:
        where_clauses.append("s.date<=?")
        params.append(normalized_end)

    query_sql += " WHERE " + " AND ".join(f"({clause})" for clause in where_clauses)
    query_sql += " ORDER BY s.date ASC, s.time_block ASC, s.id ASC"

    with get_conn() as conn:
        rows = conn.execute(query_sql, params).fetchall()
        return [_serialize_course_calendar_custom_schedule_row(row) for row in rows]


def create_course_calendar_custom_schedule(*, actor_user: dict, custom_item_id: int, date_str: str, time_block: str, start_offset_minutes: object = None):
    normalized_date = _normalize_course_calendar_date(date_str)
    normalized_time_block = _normalize_course_calendar_time_block(time_block)
    normalized_start_offset_minutes = _normalize_course_calendar_start_offset_minutes(start_offset_minutes)
    item = get_course_calendar_custom_item(custom_item_id)
    if not item:
        raise LookupError("custom item not found")
    if not _can_access_course_calendar_custom_item(actor_user, item):
        raise PermissionError("forbidden")

    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO course_calendar_custom_schedules
                (organization_id, custom_item_id, date, time_block, start_offset_minutes, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                item["organization_id"],
                custom_item_id,
                normalized_date,
                normalized_time_block,
                normalized_start_offset_minutes,
                actor_user["id"],
            ),
        )
        row = conn.execute(
            f"{_course_calendar_custom_schedule_select_sql()} WHERE s.custom_item_id=? AND s.date=? AND s.time_block=?",
            (custom_item_id, normalized_date, normalized_time_block),
        ).fetchone()
        return _serialize_course_calendar_custom_schedule_row(row)


def delete_course_calendar_custom_schedule(schedule_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM course_calendar_custom_schedules WHERE id=?", (schedule_id,))
        return cur.rowcount > 0


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
            WHERE cs.class_id=? AND s.status='active'
            ORDER BY cs.id
            """,
            (class_id,),
        ).fetchall()
    return [dict(row) for row in rows]


class ClassCommentarySkillImportConflict(ValueError):
    pass


class ClassCommentarySkillCandidateRequestConflict(ValueError):
    pass


class ClassCommentarySkillCandidateNotReady(ValueError):
    def __init__(
        self,
        *,
        effective_task_count: int,
        supporting_task_count: int,
        min_effective_tasks: int,
        min_support_tasks: int,
    ):
        super().__init__("candidate_not_ready")
        self.code = "candidate_not_ready"
        self.effective_task_count = int(effective_task_count)
        self.supporting_task_count = int(supporting_task_count)
        self.min_effective_tasks = int(min_effective_tasks)
        self.min_support_tasks = int(min_support_tasks)


class ClassCommentarySkillCandidateStale(ValueError):
    def __init__(self, reason: str):
        super().__init__("candidate_stale")
        self.code = "candidate_stale"
        self.reason = str(reason or "candidate_source_changed")


class ClassCommentarySkillVersionConflict(ValueError):
    def __init__(self):
        super().__init__("skill_version_conflict")
        self.code = "skill_version_conflict"


class ClassCommentarySkillActivationRequestConflict(ValueError):
    pass


class ClassCommentaryGenerationRequestConflict(ValueError):
    pass


class ClassCommentaryStudentGenerationRetryRequestConflict(ValueError):
    pass


class ClassCommentaryCreditReservationError(ValueError):
    pass


class AiUsageRequestConflict(ValueError):
    pass


class ClassCommentaryDraftVersionConflict(ValueError):
    def __init__(self, current_draft: Optional[dict]):
        super().__init__("draft_version_conflict")
        self.code = "draft_version_conflict"
        self.current_draft = current_draft


class ClassCommentaryRevisionVersionConflict(ValueError):
    def __init__(self, current_latest_revision: Optional[dict]):
        super().__init__("revision_version_conflict")
        self.code = "revision_version_conflict"
        self.current_latest_revision = current_latest_revision
        self.current_latest_revision_id = (
            int(current_latest_revision["id"])
            if current_latest_revision is not None
            else None
        )


class ClassCommentaryFeedbackSchemaMismatch(ValueError):
    def __init__(self):
        super().__init__("feedback_schema_mismatch")
        self.code = "feedback_schema_mismatch"


class ClassCommentaryFeedbackSchemaUnsupported(ValueError):
    def __init__(self):
        super().__init__("feedback_schema_unsupported")
        self.code = "feedback_schema_unsupported"


class ClassCommentaryFeedbackSchemaInvalid(ValueError):
    def __init__(self):
        super().__init__("feedback_schema_invalid")
        self.code = "feedback_schema_invalid"


class ClassCommentaryConfirmationRequestConflict(ValueError):
    pass


class ClassCommentaryMemoryNotEnabled(ValueError):
    def __init__(self):
        super().__init__("memory_not_enabled")
        self.code = "memory_not_enabled"


class ClassCommentaryMemoryEvidenceRequestConflict(ValueError):
    pass


class ClassCommentaryMemoryRetryRequestConflict(ValueError):
    pass


class ClassCommentaryMemoryRevisionNotRetryable(ValueError):
    def __init__(self):
        super().__init__("revision_not_retryable")
        self.code = "revision_not_retryable"


class ClassCommentaryMemoryEvidenceNotRevocable(ValueError):
    def __init__(self):
        super().__init__("evidence_not_revocable")
        self.code = "evidence_not_revocable"


def _class_commentary_canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _class_commentary_content_hash(value: object) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _read_class_commentary_skill_source(source_path: str) -> str:
    path = Path(str(source_path or "")).expanduser().resolve()
    if path.is_dir():
        content = read_class_commentary_skill_package_content(path)
    elif path.is_file():
        if path.name == "SKILL.md":
            content = read_class_commentary_skill_package_content(path.parent)
        else:
            content = path.read_text(encoding="utf-8").strip()
    else:
        raise ValueError("skill source_path not found")
    if not content:
        raise ValueError("skill content is empty")
    return content


def _class_commentary_skill_display_name(skill_id: str, source_path: str) -> str:
    path = Path(source_path)
    if path.is_dir():
        meta_path = path / "meta.json"
    elif path.name == "SKILL.md":
        meta_path = path.parent / "meta.json"
    else:
        meta_path = Path("")
    if meta_path and meta_path.is_file():
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            metadata = {}
        if isinstance(metadata, dict) and str(metadata.get("name") or "").strip():
            return str(metadata["name"]).strip()
    return skill_id


def _serialize_class_commentary_skill_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    source_path = str(item.get("source_path") or "")
    skill_id = str(item["skill_id"])
    return {
        "registry_id": int(item["registry_id"]),
        "id": skill_id,
        "skill_id": skill_id,
        "name": _class_commentary_skill_display_name(skill_id, source_path),
        "organization_id": int(item["organization_id"]),
        "imported_by_user_id": int(item["imported_by_user_id"]),
        "source_type": str(item["source_type"]),
        "source_path": source_path,
        "filename": Path(source_path).name if source_path else "",
        "source_content_hash": str(item["source_content_hash"]),
        "status": str(item["status"]),
        "active_version_id": int(item["active_version_id"]),
        "version_id": int(item["version_id"]),
        "version_no": int(item["version_no"]),
        "version_kind": str(item["version_kind"]),
        "content": str(item["content"]),
        "content_hash": str(item["content_hash"]),
        "updated_at": str(item["updated_at"] or ""),
    }


def _class_commentary_skill_select_sql() -> str:
    return """
        SELECT registry.id AS registry_id,
               registry.organization_id,
               registry.skill_id,
               registry.imported_by_user_id,
               registry.source_type,
               registry.source_path,
               registry.source_content_hash,
               registry.status,
               registry.active_version_id,
               registry.updated_at,
               version.id AS version_id,
               version.version_no,
               version.version_kind,
               version.content,
               version.content_hash
        FROM class_commentary_skills AS registry
        JOIN class_commentary_skill_versions AS version
          ON version.id = registry.active_version_id
         AND version.skill_registry_id = registry.id
         AND version.organization_id = registry.organization_id
    """


def _get_class_commentary_skill_for_organization_conn(
    conn: sqlite3.Connection,
    organization_id: int,
    skill_id: str,
):
    return conn.execute(
        f"""
        {_class_commentary_skill_select_sql()}
        WHERE registry.organization_id=?
          AND registry.skill_id=?
          AND registry.status='active'
        """,
        (organization_id, str(skill_id or "").strip()),
    ).fetchone()


def import_class_commentary_skill_manifest(
    *,
    organization_id: int,
    skill_id: str,
    actor_user_id: int,
    source_path: str,
    content: Optional[str] = None,
) -> dict:
    normalized_skill_id = str(skill_id or "").strip()
    if not normalized_skill_id or "/" in normalized_skill_id or "\\" in normalized_skill_id:
        raise ValueError("invalid skill_id")
    resolved_source_path = str(Path(str(source_path or "")).expanduser().absolute())
    source_content = str(content).strip() if content is not None else _read_class_commentary_skill_source(resolved_source_path)
    if not source_content:
        raise ValueError("skill content is empty")
    content_hash = _class_commentary_content_hash(source_content)
    activation_request_id = f"initial-import:{organization_id}:{normalized_skill_id}"
    activation_payload = {
        "organization_id": int(organization_id),
        "skill_id": normalized_skill_id,
        "source_content_hash": content_hash,
        "source_path": resolved_source_path,
    }
    activation_payload_hash = _class_commentary_content_hash(
        _class_commentary_canonical_json(activation_payload)
    )

    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        organization = conn.execute(
            "SELECT id FROM organizations WHERE id=?",
            (organization_id,),
        ).fetchone()
        if not organization:
            raise ValueError("organization not found")
        actor = conn.execute(
            "SELECT organization_id, status FROM users WHERE id=?",
            (actor_user_id,),
        ).fetchone()
        if not actor or int(actor["organization_id"] or 0) != int(organization_id):
            raise ValueError("skill import actor must belong to organization")
        if str(actor["status"] or "") != "active":
            raise ValueError("skill import actor must be active")

        existing = conn.execute(
            """
            SELECT id, imported_by_user_id, source_type, source_path,
                   source_content_hash, active_version_id, status
            FROM class_commentary_skills
            WHERE organization_id=? AND skill_id=?
            """,
            (organization_id, normalized_skill_id),
        ).fetchone()
        if existing:
            initial_version = conn.execute(
                """
                SELECT version_no, version_kind, content, content_hash, review_status
                FROM class_commentary_skill_versions
                WHERE skill_registry_id=? AND organization_id=? AND version_no=1
                """,
                (existing["id"], organization_id),
            ).fetchone()
            exact_match = bool(
                existing["source_type"] == "external_skill_package"
                and str(existing["source_path"] or "") == resolved_source_path
                and existing["source_content_hash"] == content_hash
                and existing["status"] == "active"
                and initial_version
                and initial_version["version_kind"] == "imported"
                and initial_version["content"] == source_content
                and initial_version["content_hash"] == content_hash
                and initial_version["review_status"] == "not_required"
            )
            if not exact_match:
                raise ClassCommentarySkillImportConflict("skill import conflicts with existing registry")
            row = _get_class_commentary_skill_for_organization_conn(
                conn,
                organization_id,
                normalized_skill_id,
            )
            if not row:
                raise ClassCommentarySkillImportConflict("existing skill registry is incomplete")
            return _serialize_class_commentary_skill_row(row)

        cursor = conn.execute(
            """
            INSERT INTO class_commentary_skills (
                organization_id, skill_id, imported_by_user_id, source_type,
                source_path, source_content_hash, active_version_id, status
            )
            VALUES (?, ?, ?, 'external_skill_package', ?, ?, NULL, 'active')
            """,
            (
                organization_id,
                normalized_skill_id,
                actor_user_id,
                resolved_source_path,
                content_hash,
            ),
        )
        registry_id = int(cursor.lastrowid)
        version_cursor = conn.execute(
            """
            INSERT INTO class_commentary_skill_versions (
                organization_id, skill_registry_id, version_no, version_kind,
                content, content_hash, evaluation_snapshot_json, evaluation_hash,
                review_status
            )
            VALUES (?, ?, 1, 'imported', ?, ?, '{}', '', 'not_required')
            """,
            (organization_id, registry_id, source_content, content_hash),
        )
        version_id = int(version_cursor.lastrowid)
        updated = conn.execute(
            """
            UPDATE class_commentary_skills
            SET active_version_id=?, updated_at=datetime('now','localtime')
            WHERE id=? AND active_version_id IS NULL
            """,
            (version_id, registry_id),
        )
        if updated.rowcount != 1:
            raise ClassCommentarySkillImportConflict("skill active version initialization failed")
        conn.execute(
            """
            INSERT INTO class_commentary_skill_activation_events (
                organization_id, skill_registry_id, activation_request_id,
                activation_payload_hash, from_version_id, to_version_id,
                actor_user_id, reason, evaluation_snapshot_json
            )
            VALUES (?, ?, ?, ?, NULL, ?, ?, 'initial_import', '{}')
            """,
            (
                organization_id,
                registry_id,
                activation_request_id,
                activation_payload_hash,
                version_id,
                actor_user_id,
            ),
        )
        row = _get_class_commentary_skill_for_organization_conn(
            conn,
            organization_id,
            normalized_skill_id,
        )
        if not row:
            raise ClassCommentarySkillImportConflict("skill registry import did not produce an active skill")
        return _serialize_class_commentary_skill_row(row)


def refresh_class_commentary_skill_manifest(
    *,
    organization_id: int,
    skill_id: str,
    actor_user_id: int,
    activation_request_id: str,
    expected_active_version_id: int,
) -> dict:
    normalized_request_id = str(activation_request_id or "").strip()
    if not normalized_request_id:
        raise ValueError("activation_request_id is required")
    try:
        expected_version_id = int(expected_active_version_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("expected_active_version_id must be an integer") from exc
    if expected_version_id <= 0:
        raise ValueError("expected_active_version_id must be positive")

    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        registry = _get_class_commentary_skill_registry_for_actor_conn(
            conn,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            skill_id=skill_id,
        )
        if str(registry["source_type"] or "") != "external_skill_package":
            raise ValueError("manifest refresh requires an external skill package")
        source_path = str(registry["source_path"] or "").strip()
        source_content = _read_class_commentary_skill_source(source_path)
        source_content_hash = _class_commentary_content_hash(source_content)
        payload_hash = _class_commentary_content_hash(
            _class_commentary_canonical_json(
                {
                    "expected_active_version_id": expected_version_id,
                    "organization_id": int(organization_id),
                    "reason": "manifest_refresh",
                    "skill_registry_id": int(registry["id"]),
                    "source_content_hash": source_content_hash,
                    "source_path": source_path,
                }
            )
        )
        existing_event = conn.execute(
            """
            SELECT * FROM class_commentary_skill_activation_events
            WHERE skill_registry_id=? AND activation_request_id=?
            """,
            (registry["id"], normalized_request_id),
        ).fetchone()
        if existing_event:
            if str(existing_event["activation_payload_hash"]) != payload_hash:
                raise ClassCommentarySkillActivationRequestConflict(
                    "activation request_id was already used with a different payload"
                )
            target_version = conn.execute(
                "SELECT * FROM class_commentary_skill_versions WHERE id=?",
                (existing_event["to_version_id"],),
            ).fetchone()
            skill_row = _get_class_commentary_skill_for_organization_conn(
                conn,
                organization_id,
                skill_id,
            )
            return {
                "changed": int(existing_event["from_version_id"] or 0)
                != int(existing_event["to_version_id"]),
                "skill": _serialize_class_commentary_skill_row(skill_row),
                "version": _serialize_class_commentary_skill_version_conn(
                    conn,
                    target_version,
                    active_version_id=int(registry["active_version_id"]),
                ),
                "activation_event": _serialize_class_commentary_skill_activation_event_conn(
                    conn, existing_event
                ),
            }

        active_version = conn.execute(
            """
            SELECT * FROM class_commentary_skill_versions
            WHERE id=? AND organization_id=? AND skill_registry_id=?
            """,
            (expected_version_id, organization_id, registry["id"]),
        ).fetchone()
        if (
            int(registry["active_version_id"] or 0) != expected_version_id
            or not active_version
        ):
            raise ClassCommentarySkillVersionConflict()
        if str(active_version["version_kind"] or "") != "imported":
            raise ValueError("manifest refresh requires an imported active version")

        changed = not (
            str(active_version["content"] or "") == source_content
            and str(active_version["content_hash"] or "") == source_content_hash
        )
        if not changed:
            raise ClassCommentarySkillImportConflict(
                "skill manifest already matches the active imported version"
            )
        next_version_no = int(
            conn.execute(
                """
                SELECT COALESCE(MAX(version_no), 0) + 1 AS version_no
                FROM class_commentary_skill_versions
                WHERE skill_registry_id=?
                """,
                (registry["id"],),
            ).fetchone()["version_no"]
        )
        version_cursor = conn.execute(
            """
            INSERT INTO class_commentary_skill_versions (
                organization_id, skill_registry_id, version_no, version_kind,
                content, content_hash, base_version_id, source_snapshot_hash,
                evaluation_snapshot_json, evaluation_hash, review_status
            )
            VALUES (?, ?, ?, 'imported', ?, ?, ?, ?, '{}', '', 'not_required')
            """,
            (
                organization_id,
                registry["id"],
                next_version_no,
                source_content,
                source_content_hash,
                expected_version_id,
                source_content_hash,
            ),
        )
        target_version_id = int(version_cursor.lastrowid)
        moved = conn.execute(
            """
            UPDATE class_commentary_skills
            SET active_version_id=?, source_content_hash=?,
                updated_at=datetime('now','localtime')
            WHERE id=? AND active_version_id=?
            """,
            (
                target_version_id,
                source_content_hash,
                registry["id"],
                expected_version_id,
            ),
        )
        if moved.rowcount != 1:
            raise ClassCommentarySkillVersionConflict()

        refresh_snapshot_json = _class_commentary_canonical_json(
            {
                "changed": changed,
                "from_content_hash": str(active_version["content_hash"] or ""),
                "source_content_hash": source_content_hash,
                "source_path": source_path,
            }
        )
        event_cursor = conn.execute(
            """
            INSERT INTO class_commentary_skill_activation_events (
                organization_id, skill_registry_id, activation_request_id,
                activation_payload_hash, from_version_id, to_version_id,
                actor_user_id, reason, evaluation_snapshot_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'manifest_refresh', ?)
            """,
            (
                organization_id,
                registry["id"],
                normalized_request_id,
                payload_hash,
                expected_version_id,
                target_version_id,
                actor_user_id,
                refresh_snapshot_json,
            ),
        )
        event = conn.execute(
            "SELECT * FROM class_commentary_skill_activation_events WHERE id=?",
            (event_cursor.lastrowid,),
        ).fetchone()
        target_version = conn.execute(
            "SELECT * FROM class_commentary_skill_versions WHERE id=?",
            (target_version_id,),
        ).fetchone()
        skill_row = _get_class_commentary_skill_for_organization_conn(
            conn,
            organization_id,
            skill_id,
        )
        return {
            "changed": changed,
            "skill": _serialize_class_commentary_skill_row(skill_row),
            "version": _serialize_class_commentary_skill_version_conn(
                conn,
                target_version,
                active_version_id=target_version_id,
            ),
            "activation_event": _serialize_class_commentary_skill_activation_event_conn(
                conn, event
            ),
        }


def list_class_commentary_skills_for_organization(organization_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            {_class_commentary_skill_select_sql()}
            WHERE registry.organization_id=?
              AND registry.status='active'
            ORDER BY registry.skill_id COLLATE NOCASE
            """,
            (organization_id,),
        ).fetchall()
    return [_serialize_class_commentary_skill_row(row) for row in rows]


def get_class_commentary_skill_for_organization(
    organization_id: int,
    skill_id: str,
) -> Optional[dict]:
    with get_conn() as conn:
        row = _get_class_commentary_skill_for_organization_conn(
            conn,
            organization_id,
            skill_id,
        )
    return _serialize_class_commentary_skill_row(row) if row else None


def _get_class_commentary_skill_registry_for_actor_conn(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    actor_user_id: int,
    skill_id: str,
) -> sqlite3.Row:
    normalized_skill_id = str(skill_id or "").strip()
    if not normalized_skill_id:
        raise ValueError("skill_id is required")
    registry = conn.execute(
        """
        SELECT registry.*, actor.organization_id AS actor_organization_id,
               actor.status AS actor_status
        FROM class_commentary_skills AS registry
        JOIN users AS actor ON actor.id=?
        WHERE registry.organization_id=? AND registry.skill_id=?
        """,
        (actor_user_id, organization_id, normalized_skill_id),
    ).fetchone()
    if not registry:
        raise LookupError("class commentary skill not found")
    if (
        int(registry["actor_organization_id"] or 0) != int(organization_id)
        or str(registry["actor_status"] or "") != "active"
        or str(registry["status"] or "") != "active"
    ):
        raise PermissionError("class commentary skill is not available")
    return registry


def _class_commentary_generation_revision_feedback_integrity_valid(
    generation: sqlite3.Row | dict,
    revision: sqlite3.Row | dict,
) -> bool:
    generation_source = dict(generation)
    revision_source = dict(revision)
    generation_schema = str(
        generation_source.get("feedback_schema_version") or ""
    )
    revision_schema = str(revision_source.get("feedback_schema_version") or "")
    if generation_schema != revision_schema:
        return False
    try:
        generation_envelope = build_class_commentary_feedback_read_envelope(
            schema_version=generation_schema,
            structured_json=generation_source.get("structured_feedback_json"),
            stored_hash=generation_source.get("structured_feedback_hash"),
            derived_text=generation_source.get("generated_feedback_text"),
            generation=generation_source,
        )
        revision_envelope = build_class_commentary_feedback_read_envelope(
            schema_version=revision_schema,
            structured_json=revision_source.get("structured_feedback_json"),
            stored_hash=revision_source.get("structured_feedback_hash"),
            derived_text=revision_source.get("final_feedback_text"),
            generation=generation_source,
        )
    except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
        return False
    statuses = {
        str(generation_envelope.get("feedback_schema_status") or ""),
        str(revision_envelope.get("feedback_schema_status") or ""),
    }
    if len(statuses) != 1 or not statuses.issubset({"plain_text", "supported"}):
        return False
    if not generation_schema:
        return not any(
            str(value or "")
            for value in (
                generation_source.get("structured_feedback_json"),
                generation_source.get("structured_feedback_hash"),
                revision_source.get("structured_feedback_json"),
                revision_source.get("structured_feedback_hash"),
            )
        )
    return True


def _class_commentary_revision_feedback_integrity_valid_conn(
    conn: sqlite3.Connection,
    *,
    revision_id: int,
    generation_id: int,
) -> bool:
    revision = conn.execute(
        "SELECT * FROM class_commentary_revisions WHERE id=?",
        (revision_id,),
    ).fetchone()
    generation = conn.execute(
        "SELECT * FROM class_commentary_generations WHERE id=?",
        (generation_id,),
    ).fetchone()
    return bool(
        revision
        and generation
        and _class_commentary_generation_revision_feedback_integrity_valid(
            generation,
            revision,
        )
    )


def _class_commentary_candidate_revision_source_snapshot(row: sqlite3.Row) -> dict:
    return {
        "task_id": int(row["task_id"]),
        "revision_id": int(row["revision_id"]),
        "revision_no": int(row["revision_no"]),
        "generation_id": int(row["generation_id"]),
        "generation_feedback_schema_version": str(
            row["generation_feedback_schema_version"] or ""
        ),
        "generation_structured_feedback_hash": str(
            row["generation_structured_feedback_hash"] or ""
        ),
        "revision_feedback_schema_version": str(
            row["revision_feedback_schema_version"] or ""
        ),
        "revision_structured_feedback_hash": str(
            row["revision_structured_feedback_hash"] or ""
        ),
        "generation_request_payload_hash": str(
            row["generation_request_payload_hash"] or ""
        ),
        "confirmed_transcript_hash": str(row["confirmed_transcript_hash"] or ""),
        "attending_roster_hash": str(row["attending_roster_hash"] or ""),
        "prompt_payload_hash": str(row["prompt_payload_hash"] or ""),
        "prompt_payload_snapshot_hash": _class_commentary_content_hash(
            row["prompt_payload_snapshot_json"]
        ),
        "skill_registry_id": int(row["skill_registry_id"]),
        "skill_version_id": int(row["skill_version_id"]),
        "skill_content_hash": str(row["skill_content_hash"] or ""),
        "generated_feedback_hash": _class_commentary_content_hash(
            row["generated_feedback_text"]
        ),
        "final_feedback_hash": _class_commentary_content_hash(
            row["final_feedback_text"]
        ),
        "generation_diff_hash": _class_commentary_content_hash(
            row["generation_diff_json"]
        ),
        "previous_revision_diff_hash": _class_commentary_content_hash(
            row["previous_revision_diff_json"]
        ),
        "learning_evidence_hash": str(row["learning_evidence_hash"] or ""),
        "learn_requested": bool(row["learn_requested"]),
        "accepted_without_edit": bool(row["accepted_without_edit"]),
        "unchanged_from_previous_revision": bool(
            row["unchanged_from_previous_revision"]
        ),
    }


def _class_commentary_candidate_revision_snapshot_hash(row: sqlite3.Row) -> str:
    return _class_commentary_content_hash(
        _class_commentary_canonical_json(
            _class_commentary_candidate_revision_source_snapshot(row)
        )
    )


def _class_commentary_candidate_effective_revision_rows_conn(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    skill_registry_id: int,
) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT task.id AS task_id,
               revision.id AS revision_id,
               revision.revision_no,
               revision.generation_id,
               revision.feedback_schema_version AS revision_feedback_schema_version,
               revision.structured_feedback_hash AS revision_structured_feedback_hash,
               revision.teacher_user_id AS revision_teacher_user_id,
               revision.final_feedback_text,
               revision.generation_diff_json,
               revision.previous_revision_diff_json,
               revision.learning_evidence_hash,
               revision.learn_requested,
               revision.accepted_without_edit,
               revision.unchanged_from_previous_revision,
               revision.confirmed_at,
               generation.organization_id AS generation_organization_id,
               generation.teacher_user_id AS generation_teacher_user_id,
               generation.feedback_schema_version AS generation_feedback_schema_version,
               generation.structured_feedback_hash AS generation_structured_feedback_hash,
               generation.generation_request_payload_hash,
               generation.confirmed_transcript_snapshot,
               generation.confirmed_transcript_hash,
               generation.attending_roster_snapshot_json,
               generation.attending_roster_hash,
               generation.prompt_payload_snapshot_json,
               generation.prompt_payload_hash,
               generation.skill_registry_id,
               generation.skill_id,
               generation.skill_version_id,
               generation.skill_content_snapshot,
               generation.skill_content_hash,
               generation.generated_feedback_text,
               generation.origin,
               generation.snapshot_completeness,
               generation.execution_snapshot_status,
               generation.status AS generation_status
        FROM class_commentary_tasks AS task
        JOIN class_commentary_revisions AS revision
          ON revision.id=task.latest_revision_id
         AND revision.task_id=task.id
        JOIN class_commentary_generations AS generation
          ON generation.id=revision.generation_id
         AND generation.task_id=task.id
        WHERE task.organization_id=?
          AND revision.organization_id=task.organization_id
          AND revision.teacher_user_id=task.teacher_user_id
          AND revision.learn_requested=1
          AND revision.accepted_without_edit=0
          AND generation.organization_id=task.organization_id
          AND generation.teacher_user_id=task.teacher_user_id
          AND generation.skill_registry_id=?
          AND generation.origin='runtime'
          AND generation.snapshot_completeness='complete'
          AND generation.execution_snapshot_status='ready'
          AND generation.status='succeeded'
        ORDER BY task.id
        """,
        (organization_id, skill_registry_id),
    ).fetchall()
    return [
        row
        for row in rows
        if _class_commentary_revision_feedback_integrity_valid_conn(
            conn,
            revision_id=int(row["revision_id"]),
            generation_id=int(row["generation_id"]),
        )
    ]


def _class_commentary_candidate_evidence_rows_conn(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    skill_registry_id: int,
    revision_ids: list[int],
) -> list[sqlite3.Row]:
    if not revision_ids:
        return []
    placeholders = ",".join("?" for _ in revision_ids)
    rows = conn.execute(
        f"""
        SELECT evidence.id AS memory_evidence_id,
               evidence.revision_id,
               evidence.memory_record_id,
               evidence.evidence_hash,
               evidence.status AS evidence_status,
               record.record_version,
               record.memory_text,
               record.memory_text_hash,
               record.desired_status AS record_desired_status
        FROM class_commentary_memory_evidence AS evidence
        JOIN class_commentary_memory_records AS record
          ON record.id=evidence.memory_record_id
         AND record.organization_id=evidence.organization_id
        JOIN class_commentary_revisions AS revision
          ON revision.id=evidence.revision_id
        WHERE evidence.organization_id=?
          AND evidence.revision_id IN ({placeholders})
          AND evidence.source_skill_registry_id=?
          AND evidence.source_teacher_user_id=revision.teacher_user_id
          AND evidence.status='active'
          AND revision.learn_requested=1
          AND revision.accepted_without_edit=0
          AND record.memory_type='teacher_style'
          AND record.scope_skill_registry_id=?
          AND record.desired_status='active'
        ORDER BY evidence.revision_id, evidence.memory_record_id, evidence.id DESC
        """,
        [
            organization_id,
            *revision_ids,
            skill_registry_id,
            skill_registry_id,
        ],
    ).fetchall()
    selected = []
    seen = set()
    for row in rows:
        key = (int(row["revision_id"]), int(row["memory_record_id"]))
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
    return selected


def _class_commentary_candidate_source_snapshot_hash(
    *,
    base_version_id: int,
    base_content_hash: str,
    selection_policy_version: str,
    min_effective_tasks: int,
    min_support_tasks: int,
    revisions: list[dict],
    evidence: list[dict],
) -> str:
    envelope = {
        "base_version": {
            "id": int(base_version_id),
            "content_hash": str(base_content_hash or ""),
        },
        "threshold_config": {
            "min_effective_tasks": int(min_effective_tasks),
            "min_support_tasks": int(min_support_tasks),
        },
        "selection_policy_version": str(selection_policy_version),
        "revisions": sorted(
            revisions,
            key=lambda item: (int(item["task_id"]), int(item["revision_id"])),
        ),
        "evidence": sorted(
            evidence,
            key=lambda item: (
                int(item["revision_id"]),
                int(item["memory_record_id"]),
                int(item["memory_evidence_id"]),
            ),
        ),
    }
    return _class_commentary_content_hash(_class_commentary_canonical_json(envelope))


def _serialize_class_commentary_skill_candidate_build_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    for field in (
        "id",
        "organization_id",
        "skill_registry_id",
        "expected_active_version_id",
        "base_version_id",
        "min_effective_tasks",
        "min_support_tasks",
        "effective_task_count",
        "supporting_task_count",
        "attempt_count",
    ):
        item[field] = int(item[field])
    if item.get("requested_by_user_id") is not None:
        item["requested_by_user_id"] = int(item["requested_by_user_id"])
    if item.get("candidate_version_id") is not None:
        item["candidate_version_id"] = int(item["candidate_version_id"])
    return item


def _get_class_commentary_skill_candidate_build_conn(
    conn: sqlite3.Connection,
    build_id: int,
) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM class_commentary_skill_candidate_builds WHERE id=?",
        (build_id,),
    ).fetchone()


def _class_commentary_candidate_source_status_conn(
    conn: sqlite3.Connection,
    build: sqlite3.Row,
    *,
    allow_candidate_active: bool = False,
) -> tuple[bool, str]:
    registry = conn.execute(
        "SELECT * FROM class_commentary_skills WHERE id=?",
        (build["skill_registry_id"],),
    ).fetchone()
    if not registry or int(registry["organization_id"]) != int(build["organization_id"]):
        return False, "registry_scope_mismatch"
    if str(build["selection_policy_version"] or "") != (
        CLASS_COMMENTARY_SKILL_SELECTION_POLICY_VERSION
    ):
        return False, "selection_policy_mismatch"
    if str(registry["status"] or "") != "active":
        return False, "registry_not_active"
    active_version_id = int(registry["active_version_id"] or 0)
    allowed_active_version_ids = {int(build["base_version_id"])}
    if allow_candidate_active and build["candidate_version_id"] is not None:
        allowed_active_version_ids.add(int(build["candidate_version_id"]))
    if active_version_id not in allowed_active_version_ids:
        return False, "base_version_changed"
    base_version = conn.execute(
        """
        SELECT * FROM class_commentary_skill_versions
        WHERE id=? AND organization_id=? AND skill_registry_id=?
        """,
        (
            build["base_version_id"],
            build["organization_id"],
            build["skill_registry_id"],
        ),
    ).fetchone()
    if not base_version:
        return False, "base_version_missing"
    revision_rows = conn.execute(
        """
        SELECT candidate_revision.id AS candidate_revision_id,
               candidate_revision.task_id,
               candidate_revision.revision_id,
               candidate_revision.revision_snapshot_hash,
               candidate_revision.sample_role,
               candidate_revision.selection_policy_version,
               task.latest_revision_id,
               revision.revision_no,
               revision.generation_id,
               revision.feedback_schema_version AS revision_feedback_schema_version,
               revision.structured_feedback_hash AS revision_structured_feedback_hash,
               revision.teacher_user_id AS revision_teacher_user_id,
               revision.final_feedback_text,
               revision.generation_diff_json,
               revision.previous_revision_diff_json,
               revision.learning_evidence_hash,
               revision.learn_requested,
               revision.accepted_without_edit,
               revision.unchanged_from_previous_revision,
               generation.organization_id AS generation_organization_id,
               generation.teacher_user_id AS generation_teacher_user_id,
               generation.feedback_schema_version AS generation_feedback_schema_version,
               generation.structured_feedback_hash AS generation_structured_feedback_hash,
               generation.generation_request_payload_hash,
               generation.confirmed_transcript_hash,
               generation.attending_roster_hash,
               generation.prompt_payload_snapshot_json,
               generation.prompt_payload_hash,
               generation.skill_registry_id,
               generation.skill_version_id,
               generation.skill_content_hash,
               generation.generated_feedback_text,
               generation.origin,
               generation.snapshot_completeness,
               generation.execution_snapshot_status,
               generation.status AS generation_status
        FROM class_commentary_skill_candidate_revisions AS candidate_revision
        JOIN class_commentary_tasks AS task ON task.id=candidate_revision.task_id
        JOIN class_commentary_revisions AS revision
          ON revision.id=candidate_revision.revision_id
         AND revision.task_id=candidate_revision.task_id
        JOIN class_commentary_generations AS generation
          ON generation.id=revision.generation_id
         AND generation.task_id=revision.task_id
        WHERE candidate_revision.candidate_build_id=?
        ORDER BY candidate_revision.task_id
        """,
        (build["id"],),
    ).fetchall()
    if len(revision_rows) != int(build["effective_task_count"]):
        return False, "frozen_revision_count_mismatch"
    revision_manifest = []
    candidate_revision_by_id = {}
    for row in revision_rows:
        candidate_revision_by_id[int(row["candidate_revision_id"])] = row
        if int(row["latest_revision_id"] or 0) != int(row["revision_id"]):
            return False, "revision_not_effective"
        if not _class_commentary_revision_feedback_integrity_valid_conn(
            conn,
            revision_id=int(row["revision_id"]),
            generation_id=int(row["generation_id"]),
        ):
            return False, "feedback_integrity_invalid"
        if (
            int(row["generation_organization_id"] or 0) != int(build["organization_id"])
            or int(row["revision_teacher_user_id"] or 0)
            != int(row["generation_teacher_user_id"] or 0)
            or int(row["skill_registry_id"] or 0) != int(build["skill_registry_id"])
            or str(row["origin"] or "") != "runtime"
            or str(row["snapshot_completeness"] or "") != "complete"
            or str(row["execution_snapshot_status"] or "") != "ready"
            or str(row["generation_status"] or "") != "succeeded"
            or int(row["learn_requested"] or 0) != 1
            or int(row["accepted_without_edit"] or 0) != 0
        ):
            return False, "revision_scope_mismatch"
        current_hash = _class_commentary_candidate_revision_snapshot_hash(row)
        if current_hash != str(row["revision_snapshot_hash"]):
            return False, "revision_snapshot_mismatch"
        if str(row["selection_policy_version"]) != str(
            build["selection_policy_version"]
        ):
            return False, "selection_policy_mismatch"
        revision_manifest.append(
            {
                "task_id": int(row["task_id"]),
                "revision_id": int(row["revision_id"]),
                "revision_snapshot_hash": current_hash,
                "sample_role": str(row["sample_role"]),
            }
        )
    evidence_rows = conn.execute(
        """
        SELECT candidate_evidence.candidate_revision_id,
               candidate_evidence.memory_evidence_id,
               candidate_evidence.memory_record_id,
               candidate_evidence.evidence_hash AS frozen_evidence_hash,
               candidate_evidence.record_version_at_selection,
               candidate_evidence.evidence_status_at_selection,
               evidence.revision_id,
               evidence.evidence_hash,
               evidence.status AS evidence_status,
               evidence.source_teacher_user_id,
               evidence.source_skill_registry_id,
               record.memory_type,
               record.scope_skill_registry_id,
               record.memory_text_hash,
               record.desired_status AS record_desired_status
        FROM class_commentary_skill_candidate_evidence AS candidate_evidence
        JOIN class_commentary_memory_evidence AS evidence
          ON evidence.id=candidate_evidence.memory_evidence_id
         AND evidence.memory_record_id=candidate_evidence.memory_record_id
        JOIN class_commentary_memory_records AS record
          ON record.id=candidate_evidence.memory_record_id
        WHERE candidate_evidence.candidate_build_id=?
        ORDER BY candidate_evidence.memory_evidence_id
        """,
        (build["id"],),
    ).fetchall()
    evidence_manifest = []
    supporting_tasks_by_record: dict[int, set[int]] = {}
    for row in evidence_rows:
        candidate_revision = candidate_revision_by_id.get(
            int(row["candidate_revision_id"])
        )
        if not candidate_revision or int(row["revision_id"]) != int(
            candidate_revision["revision_id"]
        ):
            return False, "supporting_evidence_revision_mismatch"
        if (
            str(row["evidence_status"] or "") != "active"
            or str(row["evidence_status_at_selection"] or "") != "active"
            or str(row["record_desired_status"] or "") != "active"
        ):
            return False, "supporting_evidence_not_active"
        if (
            str(row["evidence_hash"] or "")
            != str(row["frozen_evidence_hash"] or "")
            or str(row["memory_type"] or "") != "teacher_style"
            or int(row["scope_skill_registry_id"] or 0)
            != int(build["skill_registry_id"])
            or int(row["source_skill_registry_id"] or 0)
            != int(build["skill_registry_id"])
            or int(row["source_teacher_user_id"] or 0)
            != int(candidate_revision["revision_teacher_user_id"] or 0)
        ):
            return False, "supporting_evidence_scope_mismatch"
        memory_record_id = int(row["memory_record_id"])
        supporting_tasks_by_record.setdefault(memory_record_id, set()).add(
            int(candidate_revision["task_id"])
        )
        evidence_manifest.append(
            {
                "revision_id": int(row["revision_id"]),
                "memory_evidence_id": int(row["memory_evidence_id"]),
                "memory_record_id": memory_record_id,
                "evidence_hash": str(row["frozen_evidence_hash"]),
                "record_version_at_selection": int(
                    row["record_version_at_selection"]
                ),
                "memory_text_hash": str(row["memory_text_hash"] or ""),
            }
        )
    supporting_task_count = max(
        (len(task_ids) for task_ids in supporting_tasks_by_record.values()),
        default=0,
    )
    if supporting_task_count != int(build["supporting_task_count"]):
        return False, "supporting_task_count_mismatch"
    current_source_hash = _class_commentary_candidate_source_snapshot_hash(
        base_version_id=int(base_version["id"]),
        base_content_hash=str(base_version["content_hash"]),
        selection_policy_version=str(build["selection_policy_version"]),
        min_effective_tasks=int(build["min_effective_tasks"]),
        min_support_tasks=int(build["min_support_tasks"]),
        revisions=revision_manifest,
        evidence=evidence_manifest,
    )
    if current_source_hash != str(build["source_snapshot_hash"]):
        return False, "source_snapshot_mismatch"
    return True, ""


def _serialize_class_commentary_skill_candidate_build_conn(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
) -> dict:
    item = _serialize_class_commentary_skill_candidate_build_row(row)
    revision_rows = conn.execute(
        """
        SELECT id, task_id, revision_id, sample_role, revision_snapshot_hash,
               selection_policy_version, created_at
        FROM class_commentary_skill_candidate_revisions
        WHERE candidate_build_id=?
        ORDER BY task_id
        """,
        (row["id"],),
    ).fetchall()
    evidence_rows = conn.execute(
        """
        SELECT id, candidate_revision_id, memory_evidence_id, memory_record_id,
               evidence_hash, record_version_at_selection,
               evidence_status_at_selection, created_at
        FROM class_commentary_skill_candidate_evidence
        WHERE candidate_build_id=?
        ORDER BY memory_evidence_id
        """,
        (row["id"],),
    ).fetchall()
    source_valid, stale_reason = _class_commentary_candidate_source_status_conn(
        conn,
        row,
        allow_candidate_active=True,
    )
    item["frozen_revisions"] = [dict(source) for source in revision_rows]
    item["frozen_evidence"] = [dict(source) for source in evidence_rows]
    item["is_stale"] = not source_valid
    item["stale_reason"] = stale_reason
    return item


def get_class_commentary_skill_candidate_eligibility(
    *,
    organization_id: int,
    skill_id: str,
    actor_user_id: int,
    min_effective_tasks: Optional[int] = None,
    min_support_tasks: Optional[int] = None,
) -> dict:
    runtime = get_runtime_config()
    effective_threshold = int(
        min_effective_tasks
        if min_effective_tasks is not None
        else runtime["skill_evolution_min_effective_tasks"]
    )
    support_threshold = int(
        min_support_tasks
        if min_support_tasks is not None
        else runtime["skill_evolution_min_support_tasks"]
    )
    if effective_threshold < 1 or support_threshold < 1:
        raise ValueError("skill candidate thresholds must be positive")
    with get_conn() as conn:
        registry = _get_class_commentary_skill_registry_for_actor_conn(
            conn,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            skill_id=skill_id,
        )
        revision_rows = _class_commentary_candidate_effective_revision_rows_conn(
            conn,
            organization_id=organization_id,
            skill_registry_id=int(registry["id"]),
        )
        evidence_rows = _class_commentary_candidate_evidence_rows_conn(
            conn,
            organization_id=organization_id,
            skill_registry_id=int(registry["id"]),
            revision_ids=[int(row["revision_id"]) for row in revision_rows],
        )
    task_id_by_revision_id = {
        int(row["revision_id"]): int(row["task_id"]) for row in revision_rows
    }
    supporting_tasks_by_record: dict[int, set[int]] = {}
    for row in evidence_rows:
        supporting_tasks_by_record.setdefault(
            int(row["memory_record_id"]), set()
        ).add(task_id_by_revision_id[int(row["revision_id"])])
    supporting_task_count = max(
        (len(task_ids) for task_ids in supporting_tasks_by_record.values()),
        default=0,
    )
    effective_task_count = len(revision_rows)
    return {
        "skill_registry_id": int(registry["id"]),
        "active_version_id": int(registry["active_version_id"]),
        "eligible": effective_task_count >= effective_threshold,
        "effective_task_count": effective_task_count,
        "supporting_task_count": supporting_task_count,
        "min_effective_tasks": effective_threshold,
        "min_support_tasks": support_threshold,
    }


def create_class_commentary_skill_candidate_build(
    *,
    organization_id: int,
    skill_id: str,
    actor_user_id: int,
    candidate_request_id: str,
    expected_active_version_id: int,
    min_effective_tasks: Optional[int] = None,
    min_support_tasks: Optional[int] = None,
    selection_policy_version: str = CLASS_COMMENTARY_SKILL_SELECTION_POLICY_VERSION,
) -> dict:
    normalized_request_id = str(candidate_request_id or "").strip()
    if not normalized_request_id:
        raise ValueError("candidate_request_id is required")
    try:
        expected_version_id = int(expected_active_version_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("expected_active_version_id must be an integer") from exc
    if expected_version_id <= 0:
        raise ValueError("expected_active_version_id must be positive")
    runtime = get_runtime_config()
    effective_threshold = int(
        min_effective_tasks
        if min_effective_tasks is not None
        else runtime["skill_evolution_min_effective_tasks"]
    )
    support_threshold = int(
        min_support_tasks
        if min_support_tasks is not None
        else runtime["skill_evolution_min_support_tasks"]
    )
    normalized_policy = str(selection_policy_version or "").strip()
    if effective_threshold < 1 or support_threshold < 1:
        raise ValueError("skill candidate thresholds must be positive")
    if not normalized_policy:
        raise ValueError("selection_policy_version is required")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        registry = _get_class_commentary_skill_registry_for_actor_conn(
            conn,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            skill_id=skill_id,
        )
        payload_hash = _class_commentary_content_hash(
            _class_commentary_canonical_json(
                {
                    "expected_active_version_id": expected_version_id,
                    "organization_id": int(organization_id),
                    "skill_registry_id": int(registry["id"]),
                }
            )
        )
        existing = conn.execute(
            """
            SELECT * FROM class_commentary_skill_candidate_builds
            WHERE skill_registry_id=? AND candidate_request_id=?
            """,
            (registry["id"], normalized_request_id),
        ).fetchone()
        if existing:
            if str(existing["candidate_payload_hash"]) != payload_hash:
                raise ClassCommentarySkillCandidateRequestConflict(
                    "candidate request_id was already used with a different payload"
                )
            return _serialize_class_commentary_skill_candidate_build_conn(
                conn, existing
            )
        if int(registry["active_version_id"] or 0) != expected_version_id:
            raise ClassCommentarySkillVersionConflict()
        base_version = conn.execute(
            """
            SELECT * FROM class_commentary_skill_versions
            WHERE id=? AND organization_id=? AND skill_registry_id=?
            """,
            (expected_version_id, organization_id, registry["id"]),
        ).fetchone()
        if not base_version:
            raise ClassCommentarySkillVersionConflict()
        revision_rows = _class_commentary_candidate_effective_revision_rows_conn(
            conn,
            organization_id=organization_id,
            skill_registry_id=int(registry["id"]),
        )
        revision_ids = [int(row["revision_id"]) for row in revision_rows]
        evidence_rows = _class_commentary_candidate_evidence_rows_conn(
            conn,
            organization_id=organization_id,
            skill_registry_id=int(registry["id"]),
            revision_ids=revision_ids,
        )
        task_id_by_revision_id = {
            int(row["revision_id"]): int(row["task_id"]) for row in revision_rows
        }
        supporting_tasks_by_record: dict[int, set[int]] = {}
        supporting_revision_ids = set()
        for row in evidence_rows:
            revision_id = int(row["revision_id"])
            supporting_revision_ids.add(revision_id)
            supporting_tasks_by_record.setdefault(
                int(row["memory_record_id"]), set()
            ).add(task_id_by_revision_id[revision_id])
        supporting_task_count = max(
            (len(task_ids) for task_ids in supporting_tasks_by_record.values()),
            default=0,
        )
        effective_task_count = len(revision_rows)
        if effective_task_count < effective_threshold:
            raise ClassCommentarySkillCandidateNotReady(
                effective_task_count=effective_task_count,
                supporting_task_count=supporting_task_count,
                min_effective_tasks=effective_threshold,
                min_support_tasks=support_threshold,
            )
        revision_manifest = []
        revision_snapshot_hashes = {}
        for row in revision_rows:
            revision_id = int(row["revision_id"])
            snapshot_hash = _class_commentary_candidate_revision_snapshot_hash(row)
            revision_snapshot_hashes[revision_id] = snapshot_hash
            revision_manifest.append(
                {
                    "task_id": int(row["task_id"]),
                    "revision_id": revision_id,
                    "revision_snapshot_hash": snapshot_hash,
                    "sample_role": (
                        "support_and_evaluation"
                        if revision_id in supporting_revision_ids
                        else "evaluation"
                    ),
                }
            )
        evidence_manifest = [
            {
                "revision_id": int(row["revision_id"]),
                "memory_evidence_id": int(row["memory_evidence_id"]),
                "memory_record_id": int(row["memory_record_id"]),
                "evidence_hash": str(row["evidence_hash"]),
                "record_version_at_selection": int(row["record_version"]),
                "memory_text_hash": str(row["memory_text_hash"] or ""),
            }
            for row in evidence_rows
        ]
        source_snapshot_hash = _class_commentary_candidate_source_snapshot_hash(
            base_version_id=expected_version_id,
            base_content_hash=str(base_version["content_hash"]),
            selection_policy_version=normalized_policy,
            min_effective_tasks=effective_threshold,
            min_support_tasks=support_threshold,
            revisions=revision_manifest,
            evidence=evidence_manifest,
        )
        source_cutoff_at = _class_commentary_utc_timestamp()
        cursor = conn.execute(
            """
            INSERT INTO class_commentary_skill_candidate_builds (
                organization_id, skill_registry_id, requested_by_user_id,
                candidate_request_id,
                candidate_payload_hash, expected_active_version_id,
                base_version_id, source_cutoff_at, selection_policy_version,
                min_effective_tasks, min_support_tasks, source_snapshot_hash,
                effective_task_count, supporting_task_count, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued')
            """,
            (
                organization_id,
                registry["id"],
                actor_user_id,
                normalized_request_id,
                payload_hash,
                expected_version_id,
                expected_version_id,
                source_cutoff_at,
                normalized_policy,
                effective_threshold,
                support_threshold,
                source_snapshot_hash,
                effective_task_count,
                supporting_task_count,
            ),
        )
        build_id = int(cursor.lastrowid)
        candidate_revision_ids = {}
        for manifest in revision_manifest:
            candidate_revision = conn.execute(
                """
                INSERT INTO class_commentary_skill_candidate_revisions (
                    organization_id, candidate_build_id, task_id, revision_id,
                    sample_role, revision_snapshot_hash, selection_policy_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    organization_id,
                    build_id,
                    manifest["task_id"],
                    manifest["revision_id"],
                    manifest["sample_role"],
                    manifest["revision_snapshot_hash"],
                    normalized_policy,
                ),
            )
            candidate_revision_ids[int(manifest["revision_id"])] = int(
                candidate_revision.lastrowid
            )
        for row in evidence_rows:
            conn.execute(
                """
                INSERT INTO class_commentary_skill_candidate_evidence (
                    organization_id, candidate_build_id, candidate_revision_id,
                    memory_evidence_id, memory_record_id, evidence_hash,
                    record_version_at_selection, evidence_status_at_selection
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                (
                    organization_id,
                    build_id,
                    candidate_revision_ids[int(row["revision_id"])],
                    row["memory_evidence_id"],
                    row["memory_record_id"],
                    row["evidence_hash"],
                    row["record_version"],
                ),
            )
        build = _get_class_commentary_skill_candidate_build_conn(conn, build_id)
        return _serialize_class_commentary_skill_candidate_build_conn(conn, build)


def get_class_commentary_skill_candidate_build(
    build_id: int,
    *,
    organization_id: Optional[int] = None,
    actor_user_id: Optional[int] = None,
) -> Optional[dict]:
    with get_conn() as conn:
        build = _get_class_commentary_skill_candidate_build_conn(conn, build_id)
        if not build:
            return None
        if organization_id is not None and int(build["organization_id"]) != int(
            organization_id
        ):
            return None
        if actor_user_id is not None:
            actor = conn.execute(
                "SELECT organization_id, status FROM users WHERE id=?",
                (actor_user_id,),
            ).fetchone()
            if (
                not actor
                or int(actor["organization_id"] or 0) != int(build["organization_id"])
                or str(actor["status"] or "") != "active"
            ):
                raise PermissionError("class commentary skill is not available")
        return _serialize_class_commentary_skill_candidate_build_conn(conn, build)


def list_dispatchable_class_commentary_skill_candidate_builds(
    *,
    limit: int = 100,
    now: Optional[str] = None,
) -> list[dict]:
    current = now or _class_commentary_utc_timestamp()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM class_commentary_skill_candidate_builds
            WHERE attempt_count < 3
              AND (
                  status='queued'
                  OR (status='retry_wait' AND next_attempt_at<=?)
              )
            ORDER BY created_at, id
            LIMIT ?
            """,
            (current, max(1, min(int(limit), 500))),
        ).fetchall()
    return [
        _serialize_class_commentary_skill_candidate_build_row(row) for row in rows
    ]


def claim_class_commentary_skill_candidate_build(
    build_id: int,
    *,
    claim_owner: str,
    now: Optional[str] = None,
) -> Optional[dict]:
    normalized_owner = str(claim_owner or "").strip()
    if not normalized_owner:
        raise ValueError("claim_owner is required")
    current = now or _class_commentary_utc_timestamp()
    claim_token = secrets.token_hex(24)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        build = _get_class_commentary_skill_candidate_build_conn(conn, build_id)
        if not build:
            return None
        source_valid, stale_reason = _class_commentary_candidate_source_status_conn(
            conn, build
        )
        if not source_valid:
            conn.execute(
                """
                UPDATE class_commentary_skill_candidate_builds
                SET status='obsolete', claim_token=NULL, claim_owner=NULL,
                    next_attempt_at=NULL, last_error=?, completed_at=?
                WHERE id=? AND status IN ('queued','retry_wait','running')
                """,
                (stale_reason, current, build_id),
            )
            return None
        updated = conn.execute(
            """
            UPDATE class_commentary_skill_candidate_builds
            SET status='running', attempt_count=attempt_count + 1,
                claim_token=?, claim_owner=?, started_at=?,
                next_attempt_at=NULL, last_error=NULL, completed_at=NULL
            WHERE id=?
              AND attempt_count < 3
              AND (
                  status='queued'
                  OR (status='retry_wait' AND next_attempt_at<=?)
              )
            """,
            (claim_token, normalized_owner, current, build_id, current),
        )
        if updated.rowcount != 1:
            return None
        claimed = _get_class_commentary_skill_candidate_build_conn(conn, build_id)
        return _serialize_class_commentary_skill_candidate_build_row(claimed)


def get_class_commentary_skill_candidate_build_input(
    build_id: int,
) -> Optional[dict]:
    with get_conn() as conn:
        build = _get_class_commentary_skill_candidate_build_conn(conn, build_id)
        if not build:
            return None
        base_version = conn.execute(
            """
            SELECT * FROM class_commentary_skill_versions
            WHERE id=? AND organization_id=? AND skill_registry_id=?
            """,
            (
                build["base_version_id"],
                build["organization_id"],
                build["skill_registry_id"],
            ),
        ).fetchone()
        registry = conn.execute(
            """
            SELECT skill_id, source_path
            FROM class_commentary_skills
            WHERE id=? AND organization_id=?
            """,
            (build["skill_registry_id"], build["organization_id"]),
        ).fetchone()
        revision_rows = conn.execute(
            """
            SELECT candidate_revision.id AS candidate_revision_id,
                   candidate_revision.task_id,
                   candidate_revision.revision_id,
                   candidate_revision.sample_role,
                   candidate_revision.revision_snapshot_hash,
                   revision.revision_no,
                   revision.feedback_schema_version AS revision_feedback_schema_version,
                   revision.structured_feedback_hash AS revision_structured_feedback_hash,
                   revision.final_feedback_text,
                   revision.generation_diff_json,
                   revision.previous_revision_diff_json,
                   revision.learn_requested,
                   revision.accepted_without_edit,
                   revision.unchanged_from_previous_revision,
                   generation.id AS generation_id,
                   generation.feedback_schema_version AS generation_feedback_schema_version,
                   generation.structured_feedback_hash AS generation_structured_feedback_hash,
                   generation.confirmed_transcript_snapshot,
                   generation.attending_roster_snapshot_json,
                   generation.generated_feedback_text,
                   generation.prompt_payload_snapshot_json,
                   generation.prompt_payload_hash,
                   generation.skill_version_id,
                   generation.skill_content_hash
            FROM class_commentary_skill_candidate_revisions AS candidate_revision
            JOIN class_commentary_revisions AS revision
              ON revision.id=candidate_revision.revision_id
            JOIN class_commentary_generations AS generation
              ON generation.id=revision.generation_id
            WHERE candidate_revision.candidate_build_id=?
            ORDER BY candidate_revision.task_id
            """,
            (build_id,),
        ).fetchall()
        evidence_rows = conn.execute(
            """
            SELECT candidate_evidence.id AS candidate_evidence_id,
                   candidate_evidence.candidate_revision_id,
                   candidate_evidence.memory_evidence_id,
                   candidate_evidence.memory_record_id,
                   candidate_evidence.evidence_hash,
                   candidate_evidence.record_version_at_selection,
                   record.memory_text,
                   record.memory_text_hash
            FROM class_commentary_skill_candidate_evidence AS candidate_evidence
            JOIN class_commentary_memory_records AS record
              ON record.id=candidate_evidence.memory_record_id
            WHERE candidate_evidence.candidate_build_id=?
            ORDER BY candidate_evidence.memory_evidence_id
            """,
            (build_id,),
        ).fetchall()
        source_valid, stale_reason = _class_commentary_candidate_source_status_conn(
            conn, build
        )
    revision_samples = []
    for row in revision_rows:
        sample = dict(row)
        sample["attending_roster"] = _class_commentary_json_list(
            sample.pop("attending_roster_snapshot_json")
        )
        sample["generation_diff"] = _class_commentary_json_dict(
            sample.pop("generation_diff_json")
        )
        sample["prompt_payload"] = _class_commentary_json_dict(
            sample.pop("prompt_payload_snapshot_json")
        )
        previous_diff_json = sample.pop("previous_revision_diff_json")
        sample["previous_revision_diff"] = (
            _class_commentary_json_dict(previous_diff_json)
            if previous_diff_json
            else None
        )
        revision_samples.append(sample)
    return {
        "build": _serialize_class_commentary_skill_candidate_build_row(build),
        "skill": {
            "skill_id": str(registry["skill_id"]),
            "name": _class_commentary_skill_display_name(
                str(registry["skill_id"]),
                str(registry["source_path"] or ""),
            ),
        }
        if registry
        else None,
        "base_version": dict(base_version) if base_version else None,
        "revision_samples": revision_samples,
        "style_evidence": [dict(row) for row in evidence_rows],
        "source_valid": source_valid,
        "stale_reason": stale_reason,
    }


def fail_class_commentary_skill_candidate_build(
    build_id: int,
    *,
    claim_token: str,
    error: str,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    current_dt = now or datetime.now(timezone.utc)
    current = _class_commentary_utc_timestamp(current_dt)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        build = _get_class_commentary_skill_candidate_build_conn(conn, build_id)
        if not build:
            return None
        if str(build["status"]) != "running" or str(
            build["claim_token"] or ""
        ) != str(claim_token or ""):
            return _serialize_class_commentary_skill_candidate_build_row(build)
        source_valid, stale_reason = _class_commentary_candidate_source_status_conn(
            conn, build
        )
        attempt_count = int(build["attempt_count"] or 0)
        if not source_valid:
            status = "obsolete"
            next_attempt_at = None
            completed_at = current
            last_error = stale_reason
        elif attempt_count >= 3:
            status = "failed"
            next_attempt_at = None
            completed_at = current
            last_error = str(error or "")[:4000]
        else:
            status = "retry_wait"
            delay = (60, 300)[max(0, attempt_count - 1)]
            next_attempt_at = _class_commentary_utc_timestamp(
                current_dt + timedelta(seconds=delay)
            )
            completed_at = None
            last_error = str(error or "")[:4000]
        conn.execute(
            """
            UPDATE class_commentary_skill_candidate_builds
            SET status=?, claim_token=NULL, claim_owner=NULL,
                next_attempt_at=?, last_error=?, completed_at=?
            WHERE id=? AND status='running' AND claim_token=?
            """,
            (
                status,
                next_attempt_at,
                last_error,
                completed_at,
                build_id,
                claim_token,
            ),
        )
        failed = _get_class_commentary_skill_candidate_build_conn(conn, build_id)
        return _serialize_class_commentary_skill_candidate_build_row(failed)


def complete_class_commentary_skill_candidate_build(
    build_id: int,
    *,
    claim_token: str,
    candidate_content: str,
    evaluation_snapshot: dict,
) -> Optional[dict]:
    normalized_content = str(candidate_content or "").strip()
    if not normalized_content:
        raise ValueError("candidate_content is required")
    if not isinstance(evaluation_snapshot, dict):
        raise ValueError("evaluation_snapshot must be an object")
    evaluation_snapshot_json = _class_commentary_canonical_json(evaluation_snapshot)
    evaluation_hash = _class_commentary_content_hash(evaluation_snapshot_json)
    completed_at = _class_commentary_utc_timestamp()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        build = _get_class_commentary_skill_candidate_build_conn(conn, build_id)
        if not build:
            return None
        if str(build["status"]) != "running" or str(
            build["claim_token"] or ""
        ) != str(claim_token or ""):
            return _serialize_class_commentary_skill_candidate_build_conn(conn, build)
        source_valid, stale_reason = _class_commentary_candidate_source_status_conn(
            conn, build
        )
        if not source_valid:
            conn.execute(
                """
                UPDATE class_commentary_skill_candidate_builds
                SET status='obsolete', claim_token=NULL, claim_owner=NULL,
                    next_attempt_at=NULL, last_error=?, completed_at=?
                WHERE id=? AND status='running' AND claim_token=?
                """,
                (stale_reason, completed_at, build_id, claim_token),
            )
            obsolete = _get_class_commentary_skill_candidate_build_conn(
                conn, build_id
            )
            return _serialize_class_commentary_skill_candidate_build_conn(
                conn, obsolete
            )
        next_version_no = int(
            conn.execute(
                """
                SELECT COALESCE(MAX(version_no), 0) + 1 AS value
                FROM class_commentary_skill_versions
                WHERE skill_registry_id=?
                """,
                (build["skill_registry_id"],),
            ).fetchone()["value"]
        )
        version_cursor = conn.execute(
            """
            INSERT INTO class_commentary_skill_versions (
                organization_id, skill_registry_id, version_no, version_kind,
                candidate_build_id, content, content_hash, base_version_id,
                source_snapshot_hash, evaluation_snapshot_json, evaluation_hash,
                review_status
            )
            VALUES (?, ?, ?, 'candidate', ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                build["organization_id"],
                build["skill_registry_id"],
                next_version_no,
                build_id,
                normalized_content,
                _class_commentary_content_hash(normalized_content),
                build["base_version_id"],
                build["source_snapshot_hash"],
                evaluation_snapshot_json,
                evaluation_hash,
            ),
        )
        candidate_version_id = int(version_cursor.lastrowid)
        updated = conn.execute(
            """
            UPDATE class_commentary_skill_candidate_builds
            SET status='succeeded', candidate_version_id=?, claim_token=NULL,
                claim_owner=NULL, next_attempt_at=NULL, last_error=NULL,
                completed_at=?
            WHERE id=? AND status='running' AND claim_token=?
              AND candidate_version_id IS NULL
            """,
            (candidate_version_id, completed_at, build_id, claim_token),
        )
        if updated.rowcount != 1:
            raise ClassCommentarySkillVersionConflict()
        completed = _get_class_commentary_skill_candidate_build_conn(conn, build_id)
        return _serialize_class_commentary_skill_candidate_build_conn(conn, completed)


def recover_stale_class_commentary_skill_candidate_builds(
    *,
    timeout_seconds: int = 300,
    active_build_ids: Optional[set[int]] = None,
    now: Optional[datetime] = None,
) -> list[dict]:
    current_dt = now or datetime.now(timezone.utc)
    current = _class_commentary_utc_timestamp(current_dt)
    cutoff = _class_commentary_utc_timestamp(
        current_dt - timedelta(seconds=max(1, int(timeout_seconds)) + 60)
    )
    active_ids = {int(value) for value in (active_build_ids or set())}
    recovered_ids = []
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            """
            SELECT * FROM class_commentary_skill_candidate_builds
            WHERE status='running' AND started_at<=?
            ORDER BY id
            """,
            (cutoff,),
        ).fetchall()
        for build in rows:
            if int(build["id"]) in active_ids:
                continue
            source_valid, stale_reason = _class_commentary_candidate_source_status_conn(
                conn, build
            )
            if not source_valid:
                status = "obsolete"
                next_attempt_at = None
                error = stale_reason
                completed_at = current
            elif int(build["attempt_count"] or 0) >= 3:
                status = "failed"
                next_attempt_at = None
                error = "stale_running_attempt_limit"
                completed_at = current
            else:
                status = "retry_wait"
                next_attempt_at = current
                error = "stale_running_recovered"
                completed_at = None
            conn.execute(
                """
                UPDATE class_commentary_skill_candidate_builds
                SET status=?, claim_token=NULL, claim_owner=NULL,
                    next_attempt_at=?, last_error=?, completed_at=?
                WHERE id=? AND status='running' AND claim_token=?
                """,
                (
                    status,
                    next_attempt_at,
                    error,
                    completed_at,
                    build["id"],
                    build["claim_token"],
                ),
            )
            recovered_ids.append(int(build["id"]))
        if not recovered_ids:
            return []
        placeholders = ",".join("?" for _ in recovered_ids)
        recovered = conn.execute(
            f"""
            SELECT * FROM class_commentary_skill_candidate_builds
            WHERE id IN ({placeholders}) ORDER BY id
            """,
            recovered_ids,
        ).fetchall()
        return [
            _serialize_class_commentary_skill_candidate_build_row(row)
            for row in recovered
        ]


def _serialize_class_commentary_skill_version_conn(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    active_version_id: int,
) -> dict:
    item = dict(row)
    for field in (
        "id",
        "organization_id",
        "skill_registry_id",
        "version_no",
    ):
        item[field] = int(item[field])
    for field in ("candidate_build_id", "base_version_id"):
        if item.get(field) is not None:
            item[field] = int(item[field])
    item["is_active"] = int(item["id"]) == int(active_version_id)
    item["evaluation_snapshot"] = _class_commentary_json_dict(
        item.pop("evaluation_snapshot_json")
    )
    item["is_stale"] = False
    item["stale_reason"] = ""
    if item.get("candidate_build_id") is not None:
        build = _get_class_commentary_skill_candidate_build_conn(
            conn, int(item["candidate_build_id"])
        )
        if build:
            source_valid, stale_reason = _class_commentary_candidate_source_status_conn(
                conn,
                build,
                allow_candidate_active=True,
            )
            item["candidate_build"] = _serialize_class_commentary_skill_candidate_build_conn(
                conn, build
            )
            item["is_stale"] = not source_valid
            item["stale_reason"] = stale_reason
    return item


def list_class_commentary_skill_versions(
    *,
    organization_id: int,
    skill_id: str,
    actor_user_id: int,
) -> list[dict]:
    with get_conn() as conn:
        registry = _get_class_commentary_skill_registry_for_actor_conn(
            conn,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            skill_id=skill_id,
        )
        rows = conn.execute(
            """
            SELECT * FROM class_commentary_skill_versions
            WHERE organization_id=? AND skill_registry_id=?
            ORDER BY version_no DESC
            """,
            (organization_id, registry["id"]),
        ).fetchall()
        return [
            _serialize_class_commentary_skill_version_conn(
                conn,
                row,
                active_version_id=int(registry["active_version_id"]),
            )
            for row in rows
        ]


def _serialize_class_commentary_skill_activation_event_conn(
    conn: sqlite3.Connection,
    event: sqlite3.Row,
) -> dict:
    item = dict(event)
    for field in (
        "id",
        "organization_id",
        "skill_registry_id",
        "to_version_id",
        "actor_user_id",
    ):
        item[field] = int(item[field])
    if item.get("from_version_id") is not None:
        item["from_version_id"] = int(item["from_version_id"])
    item["evaluation_snapshot"] = _class_commentary_json_dict(
        item.pop("evaluation_snapshot_json")
    )
    registry = conn.execute(
        "SELECT active_version_id FROM class_commentary_skills WHERE id=?",
        (event["skill_registry_id"],),
    ).fetchone()
    item["active_version_id"] = int(event["to_version_id"])
    item["current_active_version_id"] = (
        int(registry["active_version_id"]) if registry else None
    )
    return item


def _change_class_commentary_skill_active_version(
    *,
    organization_id: int,
    skill_id: str,
    actor_user_id: int,
    version_id: int,
    activation_request_id: str,
    expected_active_version_id: int,
    reason: str,
) -> dict:
    normalized_request_id = str(activation_request_id or "").strip()
    if not normalized_request_id:
        raise ValueError("activation_request_id is required")
    try:
        target_version_id = int(version_id)
        expected_version_id = int(expected_active_version_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("version IDs must be integers") from exc
    if target_version_id <= 0 or expected_version_id <= 0:
        raise ValueError("version IDs must be positive")
    if reason not in {"candidate_approved", "rollback"}:
        raise ValueError("invalid skill activation reason")
    if reason == "rollback" and target_version_id == expected_version_id:
        raise ValueError("rollback target must differ from the active version")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        registry = _get_class_commentary_skill_registry_for_actor_conn(
            conn,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            skill_id=skill_id,
        )
        payload_hash = _class_commentary_content_hash(
            _class_commentary_canonical_json(
                {
                    "expected_active_version_id": expected_version_id,
                    "organization_id": int(organization_id),
                    "reason": reason,
                    "skill_registry_id": int(registry["id"]),
                    "to_version_id": target_version_id,
                }
            )
        )
        existing = conn.execute(
            """
            SELECT * FROM class_commentary_skill_activation_events
            WHERE skill_registry_id=? AND activation_request_id=?
            """,
            (registry["id"], normalized_request_id),
        ).fetchone()
        if existing:
            if str(existing["activation_payload_hash"]) != payload_hash:
                raise ClassCommentarySkillActivationRequestConflict(
                    "activation request_id was already used with a different payload"
                )
            return _serialize_class_commentary_skill_activation_event_conn(
                conn, existing
            )
        target_version = conn.execute(
            """
            SELECT * FROM class_commentary_skill_versions
            WHERE id=? AND organization_id=? AND skill_registry_id=?
            """,
            (target_version_id, organization_id, registry["id"]),
        ).fetchone()
        if not target_version:
            raise LookupError("class commentary skill version not found")
        evaluation_snapshot_json = str(
            target_version["evaluation_snapshot_json"] or "{}"
        )
        if reason == "candidate_approved":
            if (
                str(target_version["version_kind"]) != "candidate"
                or str(target_version["review_status"]) != "pending"
                or target_version["candidate_build_id"] is None
            ):
                raise ValueError("candidate version is not pending review")
            if _class_commentary_content_hash(evaluation_snapshot_json) != str(
                target_version["evaluation_hash"] or ""
            ):
                raise ClassCommentarySkillCandidateStale(
                    "evaluation_snapshot_mismatch"
                )
            build = _get_class_commentary_skill_candidate_build_conn(
                conn, int(target_version["candidate_build_id"])
            )
            if (
                not build
                or str(build["status"]) != "succeeded"
                or int(build["candidate_version_id"] or 0) != target_version_id
                or int(build["base_version_id"]) != expected_version_id
                or str(build["source_snapshot_hash"])
                != str(target_version["source_snapshot_hash"] or "")
            ):
                raise ClassCommentarySkillCandidateStale(
                    "candidate_build_mismatch"
                )
            source_valid, stale_reason = _class_commentary_candidate_source_status_conn(
                conn, build
            )
            if not source_valid:
                raise ClassCommentarySkillCandidateStale(stale_reason)
            reviewed_at = _class_commentary_utc_timestamp()
            reviewed = conn.execute(
                """
                UPDATE class_commentary_skill_versions
                SET review_status='approved', reviewed_at=?
                WHERE id=? AND review_status='pending'
                """,
                (reviewed_at, target_version_id),
            )
            if reviewed.rowcount != 1:
                raise ClassCommentarySkillVersionConflict()
        else:
            historical_activation = conn.execute(
                """
                SELECT 1 FROM class_commentary_skill_activation_events
                WHERE skill_registry_id=? AND to_version_id=?
                LIMIT 1
                """,
                (registry["id"], target_version_id),
            ).fetchone()
            if not historical_activation:
                raise ValueError("rollback target was never active")
        moved = conn.execute(
            """
            UPDATE class_commentary_skills
            SET active_version_id=?, updated_at=datetime('now','localtime')
            WHERE id=? AND active_version_id=?
            """,
            (target_version_id, registry["id"], expected_version_id),
        )
        if moved.rowcount != 1:
            raise ClassCommentarySkillVersionConflict()
        event_cursor = conn.execute(
            """
            INSERT INTO class_commentary_skill_activation_events (
                organization_id, skill_registry_id, activation_request_id,
                activation_payload_hash, from_version_id, to_version_id,
                actor_user_id, reason, evaluation_snapshot_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                organization_id,
                registry["id"],
                normalized_request_id,
                payload_hash,
                expected_version_id,
                target_version_id,
                actor_user_id,
                reason,
                evaluation_snapshot_json,
            ),
        )
        event = conn.execute(
            "SELECT * FROM class_commentary_skill_activation_events WHERE id=?",
            (event_cursor.lastrowid,),
        ).fetchone()
        return _serialize_class_commentary_skill_activation_event_conn(conn, event)


def activate_class_commentary_skill_candidate_version(
    *,
    organization_id: int,
    skill_id: str,
    actor_user_id: int,
    version_id: int,
    activation_request_id: str,
    expected_active_version_id: int,
) -> dict:
    return _change_class_commentary_skill_active_version(
        organization_id=organization_id,
        skill_id=skill_id,
        actor_user_id=actor_user_id,
        version_id=version_id,
        activation_request_id=activation_request_id,
        expected_active_version_id=expected_active_version_id,
        reason="candidate_approved",
    )


def rollback_class_commentary_skill_version(
    *,
    organization_id: int,
    skill_id: str,
    actor_user_id: int,
    version_id: int,
    activation_request_id: str,
    expected_active_version_id: int,
) -> dict:
    return _change_class_commentary_skill_active_version(
        organization_id=organization_id,
        skill_id=skill_id,
        actor_user_id=actor_user_id,
        version_id=version_id,
        activation_request_id=activation_request_id,
        expected_active_version_id=expected_active_version_id,
        reason="rollback",
    )


def _class_commentary_requested_roster_ids(attending_roster: object) -> list[int]:
    if not isinstance(attending_roster, list):
        raise ValueError("attending_roster must be a list")
    requested_ids: list[int] = []
    for item in attending_roster:
        if not isinstance(item, dict):
            raise ValueError("attending_roster items must be objects")
        try:
            student_id = int(item.get("student_id") or item.get("id") or 0)
        except (TypeError, ValueError):
            student_id = 0
        if student_id <= 0 or student_id in requested_ids:
            raise ValueError("attending_roster contains an invalid student")
        requested_ids.append(student_id)
    return requested_ids


def _normalize_class_commentary_attending_roster(
    conn: sqlite3.Connection,
    class_id: int,
    organization_id: int,
    attending_roster: object,
) -> list[dict]:
    requested_ids = _class_commentary_requested_roster_ids(attending_roster)
    if not requested_ids:
        return []
    placeholders = ",".join("?" for _ in requested_ids)
    rows = conn.execute(
        f"""
        SELECT student.id, student.name
        FROM class_students AS membership
        JOIN students AS student ON student.id = membership.student_id
        WHERE membership.class_id=?
          AND student.organization_id=?
          AND student.status='active'
          AND student.id IN ({placeholders})
        """,
        (class_id, organization_id, *requested_ids),
    ).fetchall()
    students_by_id = {int(row["id"]): str(row["name"] or "") for row in rows}
    if set(students_by_id) != set(requested_ids):
        raise ValueError("attending_roster contains a student outside the class")
    return [
        {"student_id": student_id, "student_name": students_by_id[student_id]}
        for student_id in requested_ids
    ]


def _serialize_class_commentary_generation_row(row: sqlite3.Row) -> dict:
    return dict(row)


def get_class_commentary_generation(generation_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (generation_id,),
        ).fetchone()
    return _serialize_class_commentary_generation_row(row) if row else None


def list_class_commentary_student_generation_runs(
    generation_id: int,
) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM class_commentary_student_generation_runs
            WHERE generation_id=?
            ORDER BY id
            """,
            (generation_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_class_commentary_student_generation_progress(
    generation_id: int,
) -> dict:
    runs = list_class_commentary_student_generation_runs(generation_id)
    counts = {
        "total": len(runs),
        "queued": 0,
        "generating": 0,
        "succeeded": 0,
        "failed": 0,
    }
    public_runs = []
    for run in runs:
        status = str(run.get("status") or "")
        if status in {"queued", "retry_wait"}:
            counts["queued"] += 1
        elif status in {"generating", "response_received"}:
            counts["generating"] += 1
        elif status == "succeeded":
            counts["succeeded"] += 1
        elif status == "failed":
            counts["failed"] += 1
        public_runs.append(
            {
                "id": int(run["id"]),
                "student_id": int(run["student_id"]),
                "student_name": str(run.get("student_name_snapshot") or ""),
                "status": status,
                "attempt_count": int(run.get("attempt_count") or 0),
                "memory_retrieval_status": str(
                    run.get("memory_retrieval_status") or "pending"
                ),
                "charge_status": str(run.get("charge_status") or "pending"),
                "error_code": str(run.get("error_code") or ""),
                "created_at": str(run.get("created_at") or ""),
                "started_at": str(run.get("started_at") or ""),
                "completed_at": str(run.get("completed_at") or ""),
            }
        )
    return {**counts, "runs": public_runs}


def get_class_commentary_student_generation_run(run_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM class_commentary_student_generation_runs WHERE id=?",
            (int(run_id),),
        ).fetchone()
    return dict(row) if row else None


def list_dispatchable_class_commentary_student_generation_runs(
    *,
    limit: int = 100,
    now: Optional[str] = None,
) -> list[dict]:
    current = str(now or _class_commentary_utc_timestamp())
    normalized_limit = max(1, min(int(limit), 500))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT run.*
            FROM class_commentary_student_generation_runs AS run
            JOIN class_commentary_generations AS generation
              ON generation.id=run.generation_id
            JOIN class_commentary_student_generation_credit_holds AS hold
              ON hold.student_run_id=run.id
            WHERE generation.status='generating'
              AND run.claim_token IS NULL
              AND (
                    (run.status='response_received' AND hold.status IN ('active','settled'))
                    OR (run.status<>'response_received' AND hold.status='active')
              )
              AND (
                    run.status='queued'
                    OR (
                        run.status IN ('retry_wait','response_received')
                        AND (run.next_attempt_at IS NULL OR run.next_attempt_at<=?)
                    )
              )
            ORDER BY run.generation_id, run.id
            LIMIT ?
            """,
            (current, normalized_limit),
        ).fetchall()
    return [dict(row) for row in rows]


def claim_class_commentary_student_generation_run(
    run_id: int,
    *,
    claim_owner: str,
    lease_seconds: int = 300,
) -> Optional[dict]:
    normalized_owner = str(claim_owner or "").strip()
    if not normalized_owner:
        raise ValueError("claim_owner is required")
    claim_token = secrets.token_urlsafe(24)
    lease_modifier = f"+{max(30, int(lease_seconds))} seconds"
    current = _class_commentary_utc_timestamp()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        run = conn.execute(
            """
            SELECT run.*, generation.status AS generation_status
            FROM class_commentary_student_generation_runs AS run
            JOIN class_commentary_generations AS generation
              ON generation.id=run.generation_id
            JOIN class_commentary_student_generation_credit_holds AS hold
              ON hold.student_run_id=run.id
            WHERE run.id=?
              AND (
                    (run.status='response_received' AND hold.status IN ('active','settled'))
                    OR (run.status<>'response_received' AND hold.status='active')
              )
            """,
            (int(run_id),),
        ).fetchone()
        if not run or str(run["generation_status"] or "") != "generating":
            return None
        status = str(run["status"] or "")
        if run["claim_token"] is not None:
            return None
        if status in {"queued", "retry_wait"}:
            if (
                status == "retry_wait"
                and run["next_attempt_at"] is not None
                and str(run["next_attempt_at"]) > current
            ):
                return None
            updated = conn.execute(
                """
                UPDATE class_commentary_student_generation_runs
                SET status='generating', attempt_count=attempt_count+1,
                    claim_token=?, claim_owner=?, error_code=NULL,
                    started_at=COALESCE(started_at, ?),
                    next_attempt_at=strftime('%Y-%m-%dT%H:%M:%fZ','now', ?)
                WHERE id=? AND status=? AND claim_token IS NULL
                """,
                (
                    claim_token,
                    normalized_owner,
                    current,
                    lease_modifier,
                    int(run_id),
                    status,
                ),
            )
        elif status == "response_received":
            if (
                run["next_attempt_at"] is not None
                and str(run["next_attempt_at"]) > current
            ):
                return None
            updated = conn.execute(
                """
                UPDATE class_commentary_student_generation_runs
                SET claim_token=?, claim_owner=?, error_code=NULL,
                    next_attempt_at=strftime('%Y-%m-%dT%H:%M:%fZ','now', ?)
                WHERE id=? AND status='response_received' AND claim_token IS NULL
                """,
                (claim_token, normalized_owner, lease_modifier, int(run_id)),
            )
        else:
            return None
        if updated.rowcount != 1:
            return None
        claimed = conn.execute(
            "SELECT * FROM class_commentary_student_generation_runs WHERE id=?",
            (int(run_id),),
        ).fetchone()
        return dict(claimed)


def validate_class_commentary_student_generation_access(run_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT run.organization_id, run.student_id,
                   generation.teacher_user_id, generation.class_id,
                   task.teacher_user_id AS task_teacher_user_id,
                   organization.status AS organization_status,
                   teacher.status AS teacher_status,
                   teacher.organization_id AS teacher_organization_id,
                   class.organization_id AS class_organization_id,
                   class.lifecycle_status AS class_lifecycle_status,
                   student.organization_id AS student_organization_id,
                   student.status AS student_status,
                   skill.status AS skill_status,
                   EXISTS(
                       SELECT 1 FROM user_classes
                       WHERE user_id=generation.teacher_user_id
                         AND class_id=generation.class_id
                   ) AS teacher_has_class,
                   EXISTS(
                       SELECT 1 FROM class_students
                       WHERE class_id=generation.class_id
                         AND student_id=run.student_id
                   ) AS student_in_class
            FROM class_commentary_student_generation_runs AS run
            JOIN class_commentary_generations AS generation
              ON generation.id=run.generation_id
            JOIN class_commentary_tasks AS task ON task.id=generation.task_id
            JOIN organizations AS organization ON organization.id=run.organization_id
            JOIN users AS teacher ON teacher.id=generation.teacher_user_id
            JOIN classes AS class ON class.id=generation.class_id
            JOIN students AS student ON student.id=run.student_id
            JOIN class_commentary_skills AS skill
              ON skill.id=generation.skill_registry_id
            WHERE run.id=?
            """,
            (int(run_id),),
        ).fetchone()
    if not row:
        return {"allowed": False, "reason": "student_run_scope_unavailable"}
    checks = (
        (str(row["organization_status"] or "") == "active", "organization_inactive"),
        (str(row["teacher_status"] or "") == "active", "teacher_inactive"),
        (
            int(row["teacher_organization_id"] or 0)
            == int(row["organization_id"]),
            "teacher_organization_mismatch",
        ),
        (
            int(row["class_organization_id"] or 0) == int(row["organization_id"]),
            "class_organization_mismatch",
        ),
        (
            str(row["class_lifecycle_status"] or "active") == "active",
            "class_inactive",
        ),
        (
            int(row["student_organization_id"] or 0)
            == int(row["organization_id"]),
            "student_organization_mismatch",
        ),
        (str(row["student_status"] or "") == "active", "student_inactive"),
        (str(row["skill_status"] or "") == "active", "skill_inactive"),
        (
            int(row["teacher_user_id"] or 0)
            == int(row["task_teacher_user_id"] or 0),
            "teacher_task_mismatch",
        ),
        (bool(row["teacher_has_class"]), "teacher_class_access_revoked"),
        (bool(row["student_in_class"]), "student_class_access_revoked"),
    )
    for allowed, reason in checks:
        if not allowed:
            return {"allowed": False, "reason": reason}
    return {"allowed": True, "reason": ""}


def finalize_class_commentary_student_generation_prompt(
    run_id: int,
    *,
    claim_token: str,
    memory_context: object,
    memory_retrieval_status: str,
    prompt_payload: object,
    graph_context: object = None,
    graph_retrieval_status: str = "empty",
    graph_allowed_evidence_refs: object = None,
) -> dict:
    normalized_status = str(memory_retrieval_status or "").strip()
    if normalized_status not in {"empty", "ready", "degraded"}:
        raise ValueError("student memory retrieval status is invalid")
    normalized_graph_status = str(graph_retrieval_status or "").strip()
    if normalized_graph_status not in {"disabled", "empty", "ready", "degraded"}:
        raise ValueError("student graph retrieval status is invalid")
    if graph_allowed_evidence_refs is None:
        normalized_graph_refs = []
    elif isinstance(graph_allowed_evidence_refs, list) and all(
        isinstance(value, str) and value for value in graph_allowed_evidence_refs
    ):
        normalized_graph_refs = list(dict.fromkeys(graph_allowed_evidence_refs))
    else:
        raise ValueError("student graph evidence allowlist is invalid")
    memory_json = class_commentary_student_canonical_json(memory_context)
    memory_hash = _class_commentary_content_hash(memory_json)
    graph_json = class_commentary_student_canonical_json(
        graph_context if graph_context is not None else {}
    )
    graph_hash = _class_commentary_content_hash(graph_json)
    graph_refs_json = class_commentary_student_canonical_json(normalized_graph_refs)
    prompt_json = class_commentary_student_canonical_json(prompt_payload)
    prompt_hash = _class_commentary_content_hash(prompt_json)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        run = conn.execute(
            "SELECT * FROM class_commentary_student_generation_runs WHERE id=?",
            (int(run_id),),
        ).fetchone()
        if not run:
            raise ValueError("student generation run not found")
        stored_memory_status = str(run["memory_retrieval_status"] or "pending")
        stored_graph_status = str(run["graph_retrieval_status"] or "pending")
        memory_finalized = stored_memory_status != "pending"
        graph_finalized = stored_graph_status != "pending"
        if memory_finalized and (
            str(run["memory_context_hash"] or "") != memory_hash
            or stored_memory_status != normalized_status
        ):
            raise ClassCommentaryGenerationRequestConflict(
                "student memory prompt is already finalized"
            )
        if graph_finalized and (
            str(run["graph_context_hash"] or "") != graph_hash
            or str(run["graph_allowed_evidence_refs_json"] or "") != graph_refs_json
            or stored_graph_status != normalized_graph_status
        ):
            raise ClassCommentaryGenerationRequestConflict(
                "student graph prompt is already finalized"
            )
        if memory_finalized and graph_finalized:
            if str(run["prompt_payload_hash"] or "") != prompt_hash:
                raise ClassCommentaryGenerationRequestConflict(
                    "student generation prompt is already finalized"
                )
            return dict(run)
        updated = conn.execute(
            """
            UPDATE class_commentary_student_generation_runs
            SET memory_context_snapshot_json=?, memory_context_hash=?,
                memory_retrieval_status=?, graph_context_snapshot_json=?,
                graph_context_hash=?, graph_allowed_evidence_refs_json=?,
                graph_retrieval_status=?, prompt_payload_snapshot_json=?,
                prompt_payload_hash=?
            WHERE id=? AND status='generating' AND claim_token=?
              AND memory_retrieval_status=?
              AND graph_retrieval_status=?
            """,
            (
                memory_json,
                memory_hash,
                normalized_status,
                graph_json,
                graph_hash,
                graph_refs_json,
                normalized_graph_status,
                prompt_json,
                prompt_hash,
                int(run_id),
                str(claim_token),
                stored_memory_status,
                stored_graph_status,
            ),
        )
        if updated.rowcount != 1:
            raise ClassCommentaryGenerationRequestConflict(
                "student generation prompt claim changed"
            )
        saved = conn.execute(
            "SELECT * FROM class_commentary_student_generation_runs WHERE id=?",
            (int(run_id),),
        ).fetchone()
        return dict(saved)


def persist_class_commentary_student_generation_response(
    run_id: int,
    *,
    claim_token: str,
    response_snapshot: object,
    structured_feedback_json: str,
    structured_feedback_hash: str,
    used_graph_evidence_refs: object = None,
) -> dict:
    response_json = class_commentary_student_canonical_json(response_snapshot)
    response_hash = _class_commentary_content_hash(response_json)
    normalized_structured_json = str(structured_feedback_json or "").strip()
    normalized_structured_hash = str(structured_feedback_hash or "").strip()
    if not normalized_structured_json or not normalized_structured_hash:
        raise ValueError("student generation structured response is required")
    if used_graph_evidence_refs is None:
        normalized_graph_refs = []
    elif isinstance(used_graph_evidence_refs, list) and all(
        isinstance(value, str) and value for value in used_graph_evidence_refs
    ):
        normalized_graph_refs = list(dict.fromkeys(used_graph_evidence_refs))
    else:
        raise ValueError("used graph evidence refs are invalid")
    used_graph_refs_json = class_commentary_student_canonical_json(
        normalized_graph_refs
    )
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        run = conn.execute(
            "SELECT * FROM class_commentary_student_generation_runs WHERE id=?",
            (int(run_id),),
        ).fetchone()
        if not run:
            raise ValueError("student generation run not found")
        if str(run["status"] or "") in {"response_received", "succeeded"}:
            if (
                str(run["response_hash"] or "") != response_hash
                or str(run["structured_feedback_hash"] or "")
                != normalized_structured_hash
                or str(run["used_graph_evidence_refs_json"] or "")
                != used_graph_refs_json
            ):
                raise ClassCommentaryGenerationRequestConflict(
                    "student generation response is already persisted"
                )
            return dict(run)
        updated = conn.execute(
            """
            UPDATE class_commentary_student_generation_runs
            SET status='response_received', response_snapshot_json=?,
                response_hash=?, structured_feedback_json=?,
                structured_feedback_hash=?, used_graph_evidence_refs_json=?,
                error_code=NULL, next_attempt_at=NULL
            WHERE id=? AND status='generating' AND claim_token=?
            """,
            (
                response_json,
                response_hash,
                normalized_structured_json,
                normalized_structured_hash,
                used_graph_refs_json,
                int(run_id),
                str(claim_token),
            ),
        )
        if updated.rowcount != 1:
            raise ClassCommentaryGenerationRequestConflict(
                "student generation response claim changed"
            )
        saved = conn.execute(
            "SELECT * FROM class_commentary_student_generation_runs WHERE id=?",
            (int(run_id),),
        ).fetchone()
        return dict(saved)


def complete_class_commentary_student_generation_run(
    run_id: int,
    *,
    claim_token: str,
    charge_usage_id: int,
) -> dict:
    with get_conn() as conn:
        updated = conn.execute(
            """
            UPDATE class_commentary_student_generation_runs
            SET status='succeeded', charge_status='charged', charge_usage_id=?,
                claim_token=NULL, claim_owner=NULL, next_attempt_at=NULL,
                error_code=NULL, completed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=? AND status='response_received' AND claim_token=?
              AND response_hash<>'' AND structured_feedback_hash<>''
              AND EXISTS (
                  SELECT 1
                  FROM class_commentary_student_generation_credit_holds AS hold
                  WHERE hold.student_run_id=class_commentary_student_generation_runs.id
                    AND hold.status='settled'
                    AND hold.usage_id=?
              )
            """,
            (
                int(charge_usage_id),
                int(run_id),
                str(claim_token),
                int(charge_usage_id),
            ),
        )
        if updated.rowcount != 1:
            run = conn.execute(
                "SELECT * FROM class_commentary_student_generation_runs WHERE id=?",
                (int(run_id),),
            ).fetchone()
            if run and str(run["status"] or "") == "succeeded":
                return dict(run)
            raise ClassCommentaryGenerationRequestConflict(
                "student generation charge claim changed"
            )
        saved = conn.execute(
            "SELECT * FROM class_commentary_student_generation_runs WHERE id=?",
            (int(run_id),),
        ).fetchone()
        return dict(saved)


def defer_class_commentary_student_generation_charge(
    run_id: int,
    *,
    claim_token: str,
    error_code: str,
    retry_after_seconds: int = 300,
) -> dict:
    modifier = f"+{max(30, int(retry_after_seconds))} seconds"
    with get_conn() as conn:
        updated = conn.execute(
            """
            UPDATE class_commentary_student_generation_runs
            SET claim_token=NULL, claim_owner=NULL, error_code=?,
                next_attempt_at=strftime('%Y-%m-%dT%H:%M:%fZ','now', ?)
            WHERE id=? AND status='response_received' AND claim_token=?
            """,
            (str(error_code or "charge_pending"), modifier, int(run_id), str(claim_token)),
        )
        if updated.rowcount != 1:
            raise ClassCommentaryGenerationRequestConflict(
                "student generation charge deferral claim changed"
            )
        saved = conn.execute(
            "SELECT * FROM class_commentary_student_generation_runs WHERE id=?",
            (int(run_id),),
        ).fetchone()
        return dict(saved)


def fail_class_commentary_student_generation_charge(
    run_id: int,
    *,
    claim_token: str,
    error_code: str,
) -> dict:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        updated = conn.execute(
            """
            UPDATE class_commentary_student_generation_runs
            SET status='failed', claim_token=NULL, claim_owner=NULL,
                next_attempt_at=NULL, error_code=?,
                completed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=? AND status='response_received' AND claim_token=?
              AND charge_status='pending'
            """,
            (str(error_code or "charge_failed"), int(run_id), str(claim_token)),
        )
        if updated.rowcount != 1:
            raise ClassCommentaryGenerationRequestConflict(
                "student generation charge failure claim changed"
            )
        conn.execute(
            """
            UPDATE class_commentary_student_generation_credit_holds
            SET status='released', released_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE student_run_id=? AND status='active'
            """,
            (int(run_id),),
        )
        saved = conn.execute(
            "SELECT * FROM class_commentary_student_generation_runs WHERE id=?",
            (int(run_id),),
        ).fetchone()
        return dict(saved)


def fail_class_commentary_student_generation_run(
    run_id: int,
    *,
    claim_token: str,
    error_code: str,
    retryable: bool,
    max_attempts: int = 3,
    retry_after_seconds: int = 30,
) -> dict:
    modifier = f"+{max(1, int(retry_after_seconds))} seconds"
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        run = conn.execute(
            "SELECT * FROM class_commentary_student_generation_runs WHERE id=?",
            (int(run_id),),
        ).fetchone()
        if not run:
            raise ValueError("student generation run not found")
        if str(run["status"] or "") in {"failed", "succeeded"}:
            return dict(run)
        if str(run["status"] or "") != "generating" or str(
            run["claim_token"] or ""
        ) != str(claim_token):
            raise ClassCommentaryGenerationRequestConflict(
                "student generation failure claim changed"
            )
        should_retry = bool(retryable) and int(run["attempt_count"] or 0) < max(
            1, int(max_attempts)
        )
        next_status = "retry_wait" if should_retry else "failed"
        conn.execute(
            """
            UPDATE class_commentary_student_generation_runs
            SET status=?, claim_token=NULL, claim_owner=NULL, error_code=?,
                next_attempt_at=CASE WHEN ?='retry_wait'
                    THEN strftime('%Y-%m-%dT%H:%M:%fZ','now', ?) ELSE NULL END,
                completed_at=CASE WHEN ?='failed'
                    THEN strftime('%Y-%m-%dT%H:%M:%fZ','now') ELSE NULL END,
                memory_retrieval_status=CASE
                    WHEN ?='failed' AND memory_retrieval_status='pending'
                         AND ? LIKE 'memory_%'
                    THEN 'failed' ELSE memory_retrieval_status END
            WHERE id=? AND status='generating' AND claim_token=?
            """,
            (
                next_status,
                str(error_code or "student_generation_failed"),
                next_status,
                modifier,
                next_status,
                next_status,
                str(error_code or ""),
                int(run_id),
                str(claim_token),
            ),
        )
        if next_status == "failed":
            conn.execute(
                """
                UPDATE class_commentary_student_generation_credit_holds
                SET status='released',
                    released_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                WHERE student_run_id=? AND status='active'
                """,
                (int(run_id),),
            )
        saved = conn.execute(
            "SELECT * FROM class_commentary_student_generation_runs WHERE id=?",
            (int(run_id),),
        ).fetchone()
        return dict(saved)


def recover_stale_class_commentary_student_generation_runs(
    *,
    now: Optional[str] = None,
    max_attempts: int = 3,
) -> list[int]:
    current = str(now or _class_commentary_utc_timestamp())
    normalized_max_attempts = max(1, int(max_attempts))
    failed_generation_ids: set[int] = set()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        stale_rows = conn.execute(
            """
            SELECT id, generation_id, status, attempt_count
            FROM class_commentary_student_generation_runs
            WHERE claim_token IS NOT NULL AND next_attempt_at IS NOT NULL
              AND next_attempt_at<=?
              AND status IN ('generating','response_received')
            ORDER BY id
            """,
            (current,),
        ).fetchall()
        for row in stale_rows:
            status = str(row["status"] or "")
            exhausted = (
                status == "generating"
                and int(row["attempt_count"] or 0) >= normalized_max_attempts
            )
            conn.execute(
                """
                UPDATE class_commentary_student_generation_runs
                SET status=?, claim_token=NULL, claim_owner=NULL,
                    next_attempt_at=?, error_code=?,
                    completed_at=CASE WHEN ?='failed'
                        THEN strftime('%Y-%m-%dT%H:%M:%fZ','now')
                        ELSE completed_at END
                WHERE id=? AND claim_token IS NOT NULL
                """,
                (
                    "failed"
                    if exhausted
                    else "retry_wait"
                    if status == "generating"
                    else "response_received",
                    None if exhausted else current,
                    "worker_lease_attempts_exhausted"
                    if exhausted
                    else "worker_lease_expired",
                    "failed" if exhausted else status,
                    int(row["id"]),
                ),
            )
            if exhausted:
                conn.execute(
                    """
                    UPDATE class_commentary_student_generation_credit_holds
                    SET status='released',
                        released_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                    WHERE student_run_id=? AND status='active'
                    """,
                    (int(row["id"]),),
                )
                failed_generation_ids.add(int(row["generation_id"]))
    for generation_id in sorted(failed_generation_ids):
        finalize_class_commentary_student_generation_parent(generation_id)
    return [int(row["id"]) for row in stale_rows]


def finalize_class_commentary_student_generation_parent(generation_id: int) -> dict:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        generation = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (int(generation_id),),
        ).fetchone()
        if not generation:
            raise ValueError("generation not found")
        if str(generation["student_history_memory_mode"] or "") != (
            CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2
        ):
            return _serialize_class_commentary_generation_row(generation)
        runs = conn.execute(
            """
            SELECT * FROM class_commentary_student_generation_runs
            WHERE generation_id=? ORDER BY id
            """,
            (int(generation_id),),
        ).fetchall()
        if not runs:
            raise ValueError("isolated generation has no student runs")
        statuses = [str(run["status"] or "") for run in runs]
        if any(
            status in {"queued", "generating", "retry_wait", "response_received"}
            for status in statuses
        ):
            return _serialize_class_commentary_generation_row(generation)
        if any(status == "failed" for status in statuses):
            if str(generation["status"] or "") == "generating":
                conn.execute(
                    """
                    UPDATE class_commentary_generations
                    SET status='failed', error_code='student_run_failed',
                        completed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                    WHERE id=? AND status='generating'
                    """,
                    (int(generation_id),),
                )
                conn.execute(
                    """
                    UPDATE class_commentary_tasks
                    SET status='failed', failure_stage='generation',
                        generation_error='student_run_failed',
                        updated_at=datetime('now','localtime')
                    WHERE id=? AND latest_generation_id=?
                    """,
                    (int(generation["task_id"]), int(generation_id)),
                )
        elif all(status == "succeeded" for status in statuses):
            roster = json.loads(str(generation["attending_roster_snapshot_json"] or "[]"))
            run_by_student = {int(run["student_id"]): run for run in runs}
            items = []
            for roster_item in roster:
                student_id = int(roster_item.get("student_id") or 0)
                run = run_by_student.get(student_id)
                if not run:
                    raise ValueError("isolated generation roster coverage mismatch")
                payload = json.loads(str(run["structured_feedback_json"] or "{}"))
                response_items = payload.get("items") if isinstance(payload, dict) else None
                if not isinstance(response_items, list) or len(response_items) != 1:
                    raise ValueError("isolated student response is invalid")
                items.append(dict(response_items[0]))
            aggregate = {
                "schema_version": CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
                "items": items,
            }
            canonical = canonicalize_class_commentary_structured_feedback(
                structured_feedback=class_commentary_student_canonical_json(aggregate),
                generation=dict(generation),
            )
            if str(generation["status"] or "") == "generating":
                conn.execute(
                    """
                    UPDATE class_commentary_generations
                    SET status='succeeded', structured_feedback_json=?,
                        structured_feedback_hash=?, generated_feedback_text=?,
                        error_code=NULL,
                        completed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                    WHERE id=? AND status='generating'
                    """,
                    (
                        canonical["structured_feedback_json"],
                        canonical["structured_feedback_hash"],
                        canonical["derived_feedback_text"],
                        int(generation_id),
                    ),
                )
                conn.execute(
                    """
                    UPDATE class_commentary_tasks
                    SET status='ready', failure_stage='', feedback_text=?,
                        generation_error='', transcription_error='',
                        updated_at=datetime('now','localtime')
                    WHERE id=? AND latest_generation_id=?
                      AND confirmed_transcript_version=?
                    """,
                    (
                        canonical["derived_feedback_text"],
                        int(generation["task_id"]),
                        int(generation_id),
                        int(generation["confirmed_transcript_version"]),
                    ),
                )
        saved = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (int(generation_id),),
        ).fetchone()
        return _serialize_class_commentary_generation_row(saved)


def retry_class_commentary_student_generation_runs(
    generation_id: int,
    *,
    actor_user_id: int,
    retry_request_id: str,
    student_ids: Optional[list[int]] = None,
) -> dict:
    normalized_request_id = str(retry_request_id or "").strip()
    if not normalized_request_id:
        raise ValueError("retry_request_id is required")
    requested_ids = (
        sorted({int(student_id) for student_id in student_ids})
        if student_ids is not None
        else None
    )
    if requested_ids is not None and any(student_id <= 0 for student_id in requested_ids):
        raise ValueError("student_ids is invalid")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        generation = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (int(generation_id),),
        ).fetchone()
        if not generation:
            raise ValueError("generation not found")
        if int(generation["teacher_user_id"] or 0) != int(actor_user_id):
            raise ValueError("generation is not owned by actor")
        if str(generation["student_history_memory_mode"] or "") != (
            CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2
        ):
            raise ValueError("generation does not support student run retry")
        existing = conn.execute(
            """
            SELECT * FROM class_commentary_student_generation_retry_events
            WHERE organization_id=? AND retry_request_id=?
            """,
            (int(generation["organization_id"]), normalized_request_id),
        ).fetchone()
        if existing:
            saved_ids = json.loads(str(existing["student_ids_json"] or "[]"))
            if int(existing["generation_id"] or 0) != int(generation_id) or (
                requested_ids is not None and requested_ids != saved_ids
            ):
                raise ClassCommentaryStudentGenerationRetryRequestConflict(
                    "student generation retry request_id conflict"
                )
            result = _serialize_class_commentary_generation_row(generation)
            result["is_idempotent"] = True
            result["retried_student_ids"] = saved_ids
            return result
        failed_rows = conn.execute(
            """
            SELECT * FROM class_commentary_student_generation_runs
            WHERE generation_id=? AND status='failed' ORDER BY id
            """,
            (int(generation_id),),
        ).fetchall()
        failed_ids = [int(row["student_id"]) for row in failed_rows]
        target_ids = requested_ids if requested_ids is not None else failed_ids
        if not target_ids or not set(target_ids).issubset(set(failed_ids)):
            raise ValueError("student generation retry target is not failed")
        placeholders = ",".join("?" for _ in target_ids)
        hold_rows = conn.execute(
            f"""
            SELECT hold.*
            FROM class_commentary_student_generation_credit_holds AS hold
            JOIN class_commentary_student_generation_runs AS run
              ON run.id=hold.student_run_id
            WHERE run.generation_id=? AND run.student_id IN ({placeholders})
            ORDER BY run.id
            """,
            (int(generation_id), *target_ids),
        ).fetchall()
        if (
            len(hold_rows) != len(target_ids)
            or any(str(hold["status"] or "") != "released" for hold in hold_rows)
        ):
            raise ValueError("student generation credit hold is not retryable")
        account = _ensure_credit_account_row(
            conn,
            int(generation["organization_id"]),
        )
        required_credits = sum(int(hold["amount"] or 0) for hold in hold_rows)
        available_credits = int(account["credit_balance"] or 0) - (
            _active_credit_hold_total_conn(
                conn,
                int(generation["organization_id"]),
            )
        )
        if available_credits < required_credits:
            raise ClassCommentaryCreditReservationError(
                "机构积分不足，请先充值后再使用 AI 功能"
            )
        payload = {
            "generation_id": int(generation_id),
            "student_ids": target_ids,
        }
        payload_hash = class_commentary_student_canonical_hash(payload)
        conn.execute(
            """
            INSERT INTO class_commentary_student_generation_retry_events (
                organization_id, generation_id, actor_user_id,
                retry_request_id, retry_payload_hash, student_ids_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(generation["organization_id"]),
                int(generation_id),
                int(actor_user_id),
                normalized_request_id,
                payload_hash,
                class_commentary_student_canonical_json(target_ids),
            ),
        )
        conn.execute(
            f"""
            UPDATE class_commentary_student_generation_credit_holds
            SET status='active', usage_id=NULL, settled_at=NULL, released_at=NULL
            WHERE student_run_id IN (
                SELECT id FROM class_commentary_student_generation_runs
                WHERE generation_id=? AND student_id IN ({placeholders})
            ) AND status='released'
            """,
            (int(generation_id), *target_ids),
        )
        conn.execute(
            f"""
            UPDATE class_commentary_student_generation_runs
            SET status=CASE WHEN response_hash<>'' AND structured_feedback_hash<>''
                    THEN 'response_received' ELSE 'retry_wait' END,
                claim_token=NULL, claim_owner=NULL,
                attempt_count=CASE
                    WHEN response_hash<>'' AND structured_feedback_hash<>''
                    THEN attempt_count ELSE 0 END,
                next_attempt_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                error_code=NULL, completed_at=NULL,
                memory_retrieval_status=CASE
                    WHEN memory_retrieval_status='failed' THEN 'pending'
                    ELSE memory_retrieval_status END,
                memory_context_snapshot_json=CASE
                    WHEN memory_retrieval_status='failed' THEN '{{}}'
                    ELSE memory_context_snapshot_json END,
                memory_context_hash=CASE
                    WHEN memory_retrieval_status='failed'
                    THEN '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'
                    ELSE memory_context_hash END,
                prompt_payload_snapshot_json=CASE
                    WHEN memory_retrieval_status='failed' THEN '{{}}'
                    ELSE prompt_payload_snapshot_json END,
                prompt_payload_hash=CASE
                    WHEN memory_retrieval_status='failed'
                    THEN '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'
                    ELSE prompt_payload_hash END
            WHERE generation_id=? AND status='failed'
              AND student_id IN ({placeholders})
            """,
            (int(generation_id), *target_ids),
        )
        conn.execute(
            """
            UPDATE class_commentary_generations
            SET status='generating', error_code=NULL, completed_at=NULL
            WHERE id=? AND status='failed'
            """,
            (int(generation_id),),
        )
        conn.execute(
            """
            UPDATE class_commentary_tasks
            SET status='generating', failure_stage='', generation_error='',
                updated_at=datetime('now','localtime')
            WHERE id=? AND latest_generation_id=?
            """,
            (int(generation["task_id"]), int(generation_id)),
        )
        saved = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (int(generation_id),),
        ).fetchone()
        result = _serialize_class_commentary_generation_row(saved)
        result["is_idempotent"] = False
        result["retried_student_ids"] = target_ids
        return result


def get_class_commentary_generation_by_request(
    task_id: int,
    generation_request_id: str,
) -> Optional[dict]:
    normalized_request_id = str(generation_request_id or "").strip()
    if not normalized_request_id:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM class_commentary_generations
            WHERE task_id=? AND generation_request_id=?
            """,
            (task_id, normalized_request_id),
        ).fetchone()
    return _serialize_class_commentary_generation_row(row) if row else None


def list_class_commentary_generations(task_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT generation.*,
                   CASE WHEN task.latest_generation_id = generation.id THEN 1 ELSE 0 END AS is_latest,
                   draft.id AS draft_id,
                   draft.draft_version,
                   draft.updated_at AS draft_updated_at,
                   (
                       SELECT revision.id
                       FROM class_commentary_revisions AS revision
                       WHERE revision.generation_id = generation.id
                       ORDER BY revision.revision_no DESC
                       LIMIT 1
                   ) AS latest_revision_id
            FROM class_commentary_generations AS generation
            JOIN class_commentary_tasks AS task ON task.id = generation.task_id
            LEFT JOIN class_commentary_feedback_drafts AS draft
              ON draft.task_id = generation.task_id
             AND draft.generation_id = generation.id
             AND draft.teacher_user_id = generation.teacher_user_id
            WHERE generation.task_id=?
            ORDER BY generation.generation_no DESC
            """,
            (task_id,),
        ).fetchall()
    return [_serialize_class_commentary_generation_row(row) for row in rows]


def _parse_class_commentary_structured_prompt_sections(user_content: object) -> tuple:
    prefixes = (
        "[CURRENT_TASK_FACTS]\n",
        "[ACTIVE_SKILL]\n",
        "[TEACHER_STYLE_MEMORIES]\n",
        "[OUTPUT_RULES]\n",
    )
    parts = str(user_content or "").split("\n\n")
    if len(parts) != len(prefixes) or any(
        not part.startswith(prefix)
        for part, prefix in zip(parts, prefixes)
    ):
        raise ValueError("structured generation prompt sections are invalid")
    try:
        current_task_facts = json.loads(parts[0][len(prefixes[0]):])
        active_skill = json.loads(parts[1][len(prefixes[1]):])
        teacher_style_memories = json.loads(parts[2][len(prefixes[2]):])
    except (TypeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("structured generation prompt sections are invalid") from exc
    return (
        current_task_facts,
        active_skill,
        teacher_style_memories,
        parts[3][len(prefixes[3]):],
    )


def _validate_class_commentary_generation_execution_contract(
    generation: dict | sqlite3.Row,
    *,
    prompt_payload: object,
    memory_context: object,
) -> None:
    generation_record = dict(generation)
    if str(generation_record["feedback_schema_version"] or "") != CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1:
        return
    validate_class_commentary_structured_generation_contract(generation_record)
    if not isinstance(prompt_payload, dict) or not isinstance(memory_context, dict):
        raise ValueError("structured generation execution snapshot is invalid")
    try:
        frozen_response_format = json.loads(
            str(generation_record["response_format_json"] or "{}")
        )
        model_parameters = json.loads(
            str(generation_record["model_parameters_json"] or "{}")
        )
        frozen_roster = json.loads(
            str(generation_record["attending_roster_snapshot_json"] or "[]")
        )
        eligible_student_ids = json.loads(
            str(generation_record["eligible_student_ids_json"] or "[]")
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("structured generation response format is invalid") from exc
    expected_keys = {
        "messages",
        "prompt_version",
        "response_format",
        "student_history_memory_mode",
        "temperature",
    }
    messages = prompt_payload.get("messages")
    structured_system_prompt, structured_output_rules = (
        get_class_commentary_structured_prompt_contract(
            str(generation_record["prompt_version"] or "")
        )
    )
    if (
        set(prompt_payload) != expected_keys
        or not isinstance(messages, list)
        or len(messages) != 2
        or messages[0] != {
            "role": "system",
            "content": structured_system_prompt,
        }
        or not isinstance(messages[1], dict)
        or set(messages[1]) != {"role", "content"}
        or messages[1].get("role") != "user"
    ):
        raise ValueError("structured generation execution prompt is invalid")
    (
        current_task_facts,
        active_skill,
        teacher_style_memories,
        output_rules,
    ) = _parse_class_commentary_structured_prompt_sections(
        messages[1].get("content")
    )
    if (
        not isinstance(frozen_roster, list)
        or not isinstance(eligible_student_ids, list)
        or not isinstance(model_parameters, dict)
        or set(model_parameters) != {"temperature"}
        or type(model_parameters.get("temperature")) not in {int, float}
        or type(prompt_payload.get("temperature")) not in {int, float}
        or float(prompt_payload["temperature"])
        != float(model_parameters["temperature"])
    ):
        raise ValueError("structured generation model parameters are invalid")
    roster_by_id = {
        int(item.get("student_id") or 0): str(item.get("student_name") or "")
        for item in frozen_roster
        if isinstance(item, dict) and type(item.get("student_id")) is int
    }
    expected_students = [
        {"id": student_id, "name": roster_by_id.get(student_id, "")}
        for student_id in eligible_student_ids
        if type(student_id) is int
    ]
    expected_output_rules = "\n".join(
        f"- {rule}" for rule in structured_output_rules
    )
    if (
        not isinstance(current_task_facts, dict)
        or set(current_task_facts)
        != {"class", "students", "transcript", "eligible_student_ids"}
        or not isinstance(current_task_facts.get("class"), dict)
        or set(current_task_facts["class"]) != {"id", "name"}
        or current_task_facts["class"].get("id")
        != int(generation_record["class_id"])
        or not isinstance(current_task_facts["class"].get("name"), str)
        or current_task_facts.get("students") != expected_students
        or current_task_facts.get("transcript")
        != str(generation_record["confirmed_transcript_snapshot"] or "")
        or current_task_facts.get("eligible_student_ids") != eligible_student_ids
        or not isinstance(active_skill, dict)
        or set(active_skill) != {"id", "name", "content"}
        or active_skill.get("id") != str(generation_record["skill_id"] or "")
        or not isinstance(active_skill.get("name"), str)
        or active_skill.get("content")
        != str(generation_record["skill_content_snapshot"] or "")
        or teacher_style_memories
        != memory_context.get("teacher_style_memories")
        or output_rules != expected_output_rules
    ):
        raise ValueError("structured generation prompt does not match reservation")
    if (
        str(prompt_payload.get("prompt_version") or "")
        != str(generation_record["prompt_version"] or "")
        or prompt_payload.get("response_format") != frozen_response_format
        or str(prompt_payload.get("student_history_memory_mode") or "")
        != str(generation_record["student_history_memory_mode"] or "")
        or str(memory_context.get("student_history_memory_mode") or "")
        != str(generation_record["student_history_memory_mode"] or "")
        or memory_context.get("student_history_memories") != []
    ):
        raise ValueError("structured generation execution snapshot does not match reservation")
    records = memory_context.get("records")
    if not isinstance(records, list) or any(
        isinstance(record, dict) and record.get("memory_type") == "student_fact"
        for record in records
    ):
        raise ValueError("structured generation student history memory is not disabled")


def _reserve_class_commentary_student_runs_conn(
    conn: sqlite3.Connection,
    *,
    generation_id: int,
    generation_request_id: str,
    organization_id: int,
    teacher_user_id: int,
    class_id: int,
    subject_key: str,
    attending_roster: list[dict],
    eligible_student_ids: list[int],
    eligible_student_scope_hash: str,
    student_mention_matcher_version: str,
    confirmed_transcript_snapshot: str,
    confirmed_transcript_hash: str,
    prompt_version: str,
    memory_mode: str,
    provider: str,
    model: str,
    model_parameters_json: str,
    credit_hold_amount_per_student: int,
) -> list[dict]:
    normalized_hold_amount = int(credit_hold_amount_per_student)
    if normalized_hold_amount <= 0:
        raise ValueError("student generation credit hold amount must be positive")
    account = _ensure_credit_account_row(conn, organization_id)
    active_holds = _active_credit_hold_total_conn(conn, organization_id)
    required_credits = normalized_hold_amount * len(attending_roster)
    if int(account["credit_balance"] or 0) - active_holds < required_credits:
        raise ClassCommentaryCreditReservationError(
            "机构积分不足，请先充值后再使用 AI 功能"
        )
    class_roster_rows = conn.execute(
        """
        SELECT student.id AS student_id, student.name AS student_name
        FROM class_students AS membership
        JOIN students AS student ON student.id=membership.student_id
        WHERE membership.class_id=?
          AND student.organization_id=?
          AND student.status='active'
        ORDER BY membership.id
        """,
        (class_id, organization_id),
    ).fetchall()
    privacy_roster = [dict(row) for row in class_roster_rows]
    class_context = build_safe_class_context(
        class_record={"id": int(class_id)},
        subject_key=subject_key,
    )
    class_context_json = class_commentary_student_canonical_json(class_context)
    class_context_hash = _class_commentary_content_hash(class_context_json)
    run_rows = []
    for roster_item in attending_roster:
        student_id = int(roster_item["student_id"])
        student_name = str(roster_item["student_name"])
        evidence_snapshot = build_student_current_evidence(
            transcript=confirmed_transcript_snapshot,
            transcript_hash=confirmed_transcript_hash,
            roster=privacy_roster,
            target_student_id=student_id,
            matcher_version=CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
        )
        evidence_hash = str(evidence_snapshot.pop("snapshot_hash"))
        request_payload = {
            "generation_id": int(generation_id),
            "student_id": student_id,
            "student_name": student_name,
            "student_run_schema_version": CLASS_COMMENTARY_STUDENT_RUN_SCHEMA_V1,
            "current_evidence_hash": evidence_hash,
            "class_context_hash": class_context_hash,
            "eligible_student_ids": list(eligible_student_ids),
            "eligible_student_scope_hash": eligible_student_scope_hash,
            "student_mention_matcher_version": student_mention_matcher_version,
            "prompt_version": prompt_version,
            "memory_mode": memory_mode,
            "provider": provider,
            "model": model,
            "model_parameters": json.loads(model_parameters_json),
        }
        request_payload_hash = class_commentary_student_canonical_hash(request_payload)
        request_id = f"{generation_request_id}:student:{student_id}"
        charge_request_key = _class_commentary_content_hash(
            f"{teacher_user_id}:{request_id}:{request_payload_hash}:class_commentary_generate"
        )
        empty_json = class_commentary_student_canonical_json({})
        empty_hash = _class_commentary_content_hash(empty_json)
        cursor = conn.execute(
            """
            INSERT INTO class_commentary_student_generation_runs (
                organization_id, generation_id, student_id,
                student_name_snapshot, request_id, request_payload_hash,
                student_run_schema_version, prompt_version, memory_mode,
                eligible_student_ids_json, eligible_student_scope_hash,
                student_mention_matcher_version,
                class_context_snapshot_json, class_context_hash,
                current_evidence_snapshot_json, current_evidence_hash,
                memory_context_snapshot_json, memory_context_hash,
                provider, model, model_parameters_json,
                prompt_payload_snapshot_json, prompt_payload_hash,
                charge_request_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                organization_id,
                generation_id,
                student_id,
                student_name,
                request_id,
                request_payload_hash,
                CLASS_COMMENTARY_STUDENT_RUN_SCHEMA_V1,
                prompt_version,
                memory_mode,
                class_commentary_student_canonical_json(eligible_student_ids),
                eligible_student_scope_hash,
                student_mention_matcher_version,
                class_context_json,
                class_context_hash,
                class_commentary_student_canonical_json(evidence_snapshot),
                evidence_hash,
                empty_json,
                empty_hash,
                provider,
                model,
                model_parameters_json,
                empty_json,
                empty_hash,
                charge_request_key,
            ),
        )
        row = conn.execute(
            "SELECT * FROM class_commentary_student_generation_runs WHERE id=?",
            (cursor.lastrowid,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO class_commentary_student_generation_credit_holds (
                student_run_id, organization_id, amount,
                request_id, request_payload_hash
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(cursor.lastrowid),
                organization_id,
                normalized_hold_amount,
                charge_request_key,
                request_payload_hash,
            ),
        )
        run_rows.append(dict(row))
    return run_rows


def reserve_class_commentary_generation(
    *,
    task_id: int,
    generation_request_id: str,
    skill_registry_id: int,
    attending_roster: list[dict],
    model_provider: str,
    model_name: str,
    model_parameters: object,
    prompt_version: str,
    prompt_payload: object = None,
    memory_context: object = None,
    attending_roster_explicit: bool = True,
    structured_feedback_enabled: bool = False,
    student_history_memory_mode: str = "",
    credit_hold_amount_per_student: int = 0,
) -> dict:
    normalized_request_id = str(generation_request_id or "").strip()
    normalized_provider = str(model_provider or "").strip()
    normalized_model = str(model_name or "").strip()
    normalized_prompt_version = str(prompt_version or "").strip()
    requested_memory_mode = str(student_history_memory_mode or "").strip()
    if not normalized_request_id:
        raise ValueError("generation_request_id is required")
    if not normalized_provider or not normalized_model or not normalized_prompt_version:
        raise ValueError("model_provider, model_name, and prompt_version are required")
    if not isinstance(attending_roster_explicit, bool):
        raise ValueError("attending_roster_explicit must be a boolean")
    if not isinstance(structured_feedback_enabled, bool):
        raise ValueError("structured_feedback_enabled must be a boolean")
    requested_roster_ids = sorted(
        _class_commentary_requested_roster_ids(attending_roster)
    )
    model_parameters_json = _class_commentary_canonical_json(model_parameters)
    execution_snapshot_status = (
        "ready" if prompt_payload is not None and memory_context is not None else "pending"
    )
    prompt_payload_json = _class_commentary_canonical_json(
        prompt_payload if prompt_payload is not None else {}
    )
    prompt_payload_hash = _class_commentary_content_hash(prompt_payload_json)
    memory_context_json = _class_commentary_canonical_json(
        memory_context if memory_context is not None else {}
    )
    memory_context_hash = _class_commentary_content_hash(memory_context_json)

    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            """
            SELECT *
            FROM class_commentary_generations
            WHERE task_id=? AND generation_request_id=?
            """,
            (task_id, normalized_request_id),
        ).fetchone()
        if existing:
            try:
                saved_roster = json.loads(
                    str(existing["attending_roster_snapshot_json"] or "[]")
                )
            except (TypeError, json.JSONDecodeError):
                saved_roster = []
            saved_roster_ids = sorted(
                int(item.get("student_id") or 0)
                for item in saved_roster
                if isinstance(item, dict) and int(item.get("student_id") or 0) > 0
            )
            frozen_memory_mode = str(
                existing["student_history_memory_mode"] or ""
            )
            isolated_model_changed = (
                frozen_memory_mode
                == CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2
                and (
                    str(existing["model_provider"] or "") != normalized_provider
                    or str(existing["model_name"] or "") != normalized_model
                    or str(existing["model_parameters_json"] or "")
                    != model_parameters_json
                )
            )
            isolated_hold_changed = False
            if frozen_memory_mode == CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2:
                hold_amounts = {
                    int(row["amount"] or 0)
                    for row in conn.execute(
                        """
                        SELECT hold.amount
                        FROM class_commentary_student_generation_credit_holds AS hold
                        JOIN class_commentary_student_generation_runs AS run
                          ON run.id=hold.student_run_id
                        WHERE run.generation_id=?
                        """,
                        (int(existing["id"]),),
                    ).fetchall()
                }
                isolated_hold_changed = hold_amounts != {
                    int(credit_hold_amount_per_student)
                }
            if (
                int(existing["skill_registry_id"] or 0) != int(skill_registry_id)
                or (
                    attending_roster_explicit
                    and saved_roster_ids != requested_roster_ids
                )
                or bool(existing["attending_roster_explicit"])
                != attending_roster_explicit
                or isolated_model_changed
                or isolated_hold_changed
            ):
                raise ClassCommentaryGenerationRequestConflict(
                    "generation request_id was already used with a different payload"
                )
            item = _serialize_class_commentary_generation_row(existing)
            item["is_idempotent"] = True
            return item

        task = conn.execute(
            """
            SELECT task.*, class.organization_id AS class_organization_id,
                   class.subject_key
            FROM class_commentary_tasks AS task
            JOIN classes AS class ON class.id = task.class_id
            WHERE task.id=?
            """,
            (task_id,),
        ).fetchone()
        if not task:
            raise ValueError("class commentary task not found")
        organization_id = int(task["organization_id"])
        teacher_user_id = int(task["teacher_user_id"])
        class_id = int(task["class_id"])
        if int(task["class_organization_id"]) != organization_id:
            raise ValueError("task organization does not match class")
        transcript_snapshot = str(task["confirmed_transcript_text"] or "").strip()
        transcript_version = int(task["confirmed_transcript_version"] or 0)
        if not transcript_snapshot or transcript_version <= 0:
            raise ValueError("confirmed transcript is required")
        transcript_hash = _class_commentary_content_hash(transcript_snapshot)

        registry = conn.execute(
            "SELECT skill_id FROM class_commentary_skills WHERE id=?",
            (skill_registry_id,),
        ).fetchone()
        skill = _get_class_commentary_skill_for_organization_conn(
            conn,
            organization_id,
            str(registry["skill_id"]) if registry else "",
        )
        if not skill or int(skill["registry_id"]) != int(skill_registry_id):
            raise ValueError("skill registry is not active in the task organization")
        skill_content = str(skill["content"])
        skill_content_hash = _class_commentary_content_hash(skill_content)
        if skill_content_hash != str(skill["content_hash"]):
            raise ValueError("skill content hash mismatch")

        roster_request = (
            attending_roster
            if structured_feedback_enabled
            else [{"student_id": student_id} for student_id in requested_roster_ids]
        )
        roster_snapshot = _normalize_class_commentary_attending_roster(
            conn,
            class_id,
            organization_id,
            roster_request,
        )
        roster_snapshot_json = _class_commentary_canonical_json(roster_snapshot)
        roster_hash = _class_commentary_content_hash(roster_snapshot_json)
        feedback_schema_version = ""
        eligible_student_ids: list[int] = []
        eligible_student_scope_hash = ""
        student_mention_matcher_version = ""
        response_format: dict = {}
        frozen_memory_mode = ""
        if structured_feedback_enabled:
            feedback_schema_version = CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1
            response_format = dict(CLASS_COMMENTARY_STRUCTURED_RESPONSE_FORMAT)
            frozen_memory_mode = (
                requested_memory_mode
                or CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_DISABLED_V1
            )
            if frozen_memory_mode == CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2:
                if normalized_prompt_version != CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2:
                    raise ValueError("isolated memory prompt version is invalid")
                if not attending_roster_explicit:
                    raise ValueError(
                        "isolated memory attending roster scope must be explicit"
                    )
                student_mention_matcher_version = (
                    CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2
                )
                eligible_student_ids = resolve_class_commentary_attending_roster_student_ids(
                    roster=roster_snapshot,
                )
            elif frozen_memory_mode != CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_DISABLED_V1:
                raise ValueError("structured feedback memory mode is invalid")
            elif normalized_prompt_version == CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION:
                student_mention_matcher_version = (
                    CLASS_COMMENTARY_STUDENT_NAME_MATCHER_V1
                )
                eligible_student_ids = match_class_commentary_eligible_student_ids(
                    transcript_text=transcript_snapshot,
                    roster=roster_snapshot,
                )
            elif normalized_prompt_version in {
                CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2,
                CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3,
            }:
                if not attending_roster_explicit:
                    raise ValueError(
                        "structured feedback attending roster scope must be explicit"
                    )
                student_mention_matcher_version = (
                    CLASS_COMMENTARY_ATTENDING_ROSTER_SCOPE_V1
                )
                eligible_student_ids = (
                    resolve_class_commentary_attending_roster_student_ids(
                        roster=roster_snapshot,
                    )
                )
            else:
                raise ValueError("structured feedback prompt version is invalid")
            eligible_student_scope_hash = build_class_commentary_eligible_scope_hash(
                transcript_hash=transcript_hash,
                roster_hash=roster_hash,
                eligible_student_ids=eligible_student_ids,
                matcher_version=student_mention_matcher_version,
            )
            if execution_snapshot_status == "ready":
                _validate_class_commentary_generation_execution_contract(
                    {
                        "class_id": class_id,
                        "attending_roster_hash": roster_hash,
                        "attending_roster_explicit": attending_roster_explicit,
                        "attending_roster_snapshot_json": roster_snapshot_json,
                        "confirmed_transcript_hash": transcript_hash,
                        "confirmed_transcript_snapshot": transcript_snapshot,
                        "eligible_student_ids_json": _class_commentary_canonical_json(
                            eligible_student_ids
                        ),
                        "eligible_student_scope_hash": eligible_student_scope_hash,
                        "feedback_schema_version": feedback_schema_version,
                        "model_parameters_json": model_parameters_json,
                        "prompt_version": normalized_prompt_version,
                        "response_format_json": _class_commentary_canonical_json(
                            response_format
                        ),
                        "student_history_memory_mode": frozen_memory_mode,
                        "student_mention_matcher_version": (
                            student_mention_matcher_version
                        ),
                        "skill_content_hash": skill_content_hash,
                        "skill_content_snapshot": skill_content,
                        "skill_id": str(skill["skill_id"]),
                    },
                    prompt_payload=prompt_payload,
                    memory_context=memory_context,
                )
        request_payload = {
            "attending_student_ids": [item["student_id"] for item in roster_snapshot],
            "attending_roster_explicit": attending_roster_explicit,
            "confirmed_transcript_hash": transcript_hash,
            "confirmed_transcript_version": transcript_version,
            "eligible_student_ids": eligible_student_ids,
            "eligible_student_scope_hash": eligible_student_scope_hash,
            "feedback_schema_version": feedback_schema_version,
            "model_name": normalized_model,
            "model_parameters": model_parameters,
            "model_provider": normalized_provider,
            "prompt_version": normalized_prompt_version,
            "response_format": response_format,
            "skill_registry_id": int(skill["registry_id"]),
            "skill_version_id": int(skill["version_id"]),
            "student_history_memory_mode": frozen_memory_mode,
            "student_mention_matcher_version": student_mention_matcher_version,
            "subject_key": task["subject_key"],
            "task_id": int(task_id),
            "credit_hold_amount_per_student": (
                int(credit_hold_amount_per_student)
                if frozen_memory_mode
                == CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2
                else 0
            ),
        }
        request_payload_hash = _class_commentary_content_hash(
            _class_commentary_canonical_json(request_payload)
        )
        generation_no = int(task["generation_seq"] or 0) + 1
        cursor = conn.execute(
            """
            INSERT INTO class_commentary_generations (
                organization_id, task_id, generation_no, generation_request_id,
                generation_request_payload_hash, teacher_user_id, class_id, subject_key,
                confirmed_transcript_version, confirmed_transcript_snapshot,
                confirmed_transcript_hash, attending_roster_snapshot_json,
                attending_roster_hash, attending_roster_explicit,
                skill_registry_id, skill_id, skill_version_id,
                skill_content_snapshot, skill_content_hash, model_provider, model_name,
                model_parameters_json, prompt_version, feedback_schema_version,
                eligible_student_ids_json, eligible_student_scope_hash,
                student_mention_matcher_version, response_format_json,
                student_history_memory_mode, prompt_payload_snapshot_json,
                prompt_payload_hash, memory_context_snapshot_json, memory_context_hash,
                execution_snapshot_status, execution_snapshot_finalized_at,
                generated_feedback_text, origin, snapshot_completeness,
                missing_snapshot_fields_json, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    '', 'runtime', 'complete', '[]', 'generating')
            """,
            (
                organization_id,
                task_id,
                generation_no,
                normalized_request_id,
                request_payload_hash,
                teacher_user_id,
                class_id,
                task["subject_key"],
                transcript_version,
                transcript_snapshot,
                transcript_hash,
                roster_snapshot_json,
                roster_hash,
                1 if attending_roster_explicit else 0,
                int(skill["registry_id"]),
                str(skill["skill_id"]),
                int(skill["version_id"]),
                skill_content,
                skill_content_hash,
                normalized_provider,
                normalized_model,
                model_parameters_json,
                normalized_prompt_version,
                feedback_schema_version,
                _class_commentary_canonical_json(eligible_student_ids),
                eligible_student_scope_hash,
                student_mention_matcher_version,
                _class_commentary_canonical_json(response_format),
                frozen_memory_mode,
                prompt_payload_json,
                prompt_payload_hash,
                memory_context_json,
                memory_context_hash,
                execution_snapshot_status,
                (
                    conn.execute(
                        "SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now') AS value"
                    ).fetchone()["value"]
                    if execution_snapshot_status == "ready"
                    else None
                ),
            ),
        )
        generation_id = int(cursor.lastrowid)
        if frozen_memory_mode == CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2:
            student_runs = _reserve_class_commentary_student_runs_conn(
                conn,
                generation_id=generation_id,
                generation_request_id=normalized_request_id,
                organization_id=organization_id,
                teacher_user_id=teacher_user_id,
                class_id=class_id,
                subject_key=str(task["subject_key"] or ""),
                attending_roster=roster_snapshot,
                eligible_student_ids=eligible_student_ids,
                eligible_student_scope_hash=eligible_student_scope_hash,
                student_mention_matcher_version=student_mention_matcher_version,
                confirmed_transcript_snapshot=transcript_snapshot,
                confirmed_transcript_hash=transcript_hash,
                prompt_version=normalized_prompt_version,
                memory_mode=frozen_memory_mode,
                provider=normalized_provider,
                model=normalized_model,
                model_parameters_json=model_parameters_json,
                credit_hold_amount_per_student=credit_hold_amount_per_student,
            )
            orchestration_snapshot = {
                "kind": "class_commentary.student_generation_orchestration.v1",
                "prompt_version": normalized_prompt_version,
                "student_run_ids": [int(run["id"]) for run in student_runs],
            }
            parent_memory_snapshot = {
                "student_history_memory_mode": frozen_memory_mode,
                "student_run_count": len(student_runs),
            }
            prompt_snapshot_json = _class_commentary_canonical_json(
                orchestration_snapshot
            )
            memory_snapshot_json = _class_commentary_canonical_json(
                parent_memory_snapshot
            )
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET prompt_payload_snapshot_json=?, prompt_payload_hash=?,
                    memory_context_snapshot_json=?, memory_context_hash=?,
                    execution_snapshot_status='ready',
                    execution_snapshot_finalized_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                WHERE id=? AND execution_snapshot_status='pending'
                """,
                (
                    prompt_snapshot_json,
                    _class_commentary_content_hash(prompt_snapshot_json),
                    memory_snapshot_json,
                    _class_commentary_content_hash(memory_snapshot_json),
                    generation_id,
                ),
            )
        updated = conn.execute(
            """
            UPDATE class_commentary_tasks
            SET generation_seq=?, latest_generation_id=?, status='generating',
                failure_stage='', skill_id=?, skill_name=?, skill_path=?,
                skill_content_snapshot=?, feedback_text='', generation_error='',
                transcription_error='',
                generation_request_key=?, chat_provider=?, chat_model=?,
                updated_at=datetime('now','localtime')
            WHERE id=? AND generation_seq=?
            """,
            (
                generation_no,
                generation_id,
                str(skill["skill_id"]),
                _class_commentary_skill_display_name(
                    str(skill["skill_id"]),
                    str(skill["source_path"] or ""),
                ),
                str(skill["source_path"]),
                skill_content,
                normalized_request_id,
                normalized_provider,
                normalized_model,
                task_id,
                int(task["generation_seq"] or 0),
            ),
        )
        if updated.rowcount != 1:
            raise ClassCommentaryGenerationRequestConflict("task generation sequence changed")
        row = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (generation_id,),
        ).fetchone()
        item = _serialize_class_commentary_generation_row(row)
        item["is_idempotent"] = False
        return item


def finalize_class_commentary_generation_execution_snapshot(
    generation_id: int,
    *,
    prompt_payload: object,
    memory_context: object,
) -> dict:
    prompt_payload_json = _class_commentary_canonical_json(prompt_payload)
    prompt_payload_hash = _class_commentary_content_hash(prompt_payload_json)
    memory_context_json = _class_commentary_canonical_json(memory_context)
    memory_context_hash = _class_commentary_content_hash(memory_context_json)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        generation = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (generation_id,),
        ).fetchone()
        if not generation:
            raise ValueError("generation not found")
        _validate_class_commentary_generation_execution_contract(
            generation,
            prompt_payload=prompt_payload,
            memory_context=memory_context,
        )
        if str(generation["execution_snapshot_status"] or "ready") == "ready":
            if (
                str(generation["prompt_payload_hash"] or "") != prompt_payload_hash
                or str(generation["memory_context_hash"] or "") != memory_context_hash
            ):
                raise ClassCommentaryGenerationRequestConflict(
                    "generation execution snapshot is already finalized"
                )
            return _serialize_class_commentary_generation_row(generation)
        if str(generation["status"]) != "generating":
            raise ValueError("generation is no longer generating")
        updated = conn.execute(
            """
            UPDATE class_commentary_generations
            SET prompt_payload_snapshot_json=?, prompt_payload_hash=?,
                memory_context_snapshot_json=?, memory_context_hash=?,
                execution_snapshot_status='ready',
                execution_snapshot_finalized_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=? AND status='generating' AND execution_snapshot_status='pending'
            """,
            (
                prompt_payload_json,
                prompt_payload_hash,
                memory_context_json,
                memory_context_hash,
                generation_id,
            ),
        )
        if updated.rowcount != 1:
            raise ClassCommentaryGenerationRequestConflict(
                "generation execution snapshot changed"
            )
        row = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (generation_id,),
        ).fetchone()
        return _serialize_class_commentary_generation_row(row)


def complete_class_commentary_generation(generation_id: int, feedback_text: str) -> dict:
    raw_feedback = str(feedback_text or "")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        generation = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (generation_id,),
        ).fetchone()
        if not generation:
            raise ValueError("generation not found")
        if generation["status"] != "generating":
            return _serialize_class_commentary_generation_row(generation)
        if str(generation["execution_snapshot_status"] or "ready") != "ready":
            raise ValueError("generation execution snapshot is not finalized")
        if str(generation["feedback_schema_version"] or ""):
            canonical = canonicalize_class_commentary_structured_feedback(
                structured_feedback=raw_feedback,
                generation=dict(generation),
            )
            normalized_feedback = str(canonical["derived_feedback_text"])
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET status='succeeded', structured_feedback_json=?,
                    structured_feedback_hash=?, generated_feedback_text=?,
                    error_code=NULL, completed_at=datetime('now','localtime')
                WHERE id=? AND status='generating'
                """,
                (
                    canonical["structured_feedback_json"],
                    canonical["structured_feedback_hash"],
                    normalized_feedback,
                    generation_id,
                ),
            )
        else:
            normalized_feedback = raw_feedback
            conn.execute(
                """
                UPDATE class_commentary_generations
                SET status='succeeded', generated_feedback_text=?, error_code=NULL,
                    completed_at=datetime('now','localtime')
                WHERE id=? AND status='generating'
                """,
                (normalized_feedback, generation_id),
            )
        conn.execute(
            """
            UPDATE class_commentary_tasks
            SET status='ready', failure_stage='', feedback_text=?, generation_error='',
                transcription_error='',
                updated_at=datetime('now','localtime')
            WHERE id=? AND latest_generation_id=? AND confirmed_transcript_version=?
            """,
            (
                normalized_feedback,
                generation["task_id"],
                generation_id,
                generation["confirmed_transcript_version"],
            ),
        )
        row = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (generation_id,),
        ).fetchone()
        return _serialize_class_commentary_generation_row(row)


def fail_class_commentary_generation(generation_id: int, error_code: str) -> dict:
    normalized_error = str(error_code or "generation_failed").strip() or "generation_failed"
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        generation = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (generation_id,),
        ).fetchone()
        if not generation:
            raise ValueError("generation not found")
        if generation["status"] != "generating":
            return _serialize_class_commentary_generation_row(generation)
        conn.execute(
            """
            UPDATE class_commentary_generations
            SET status='failed', error_code=?, completed_at=datetime('now','localtime')
            WHERE id=? AND status='generating'
            """,
            (normalized_error, generation_id),
        )
        conn.execute(
            """
            UPDATE class_commentary_tasks
            SET status='failed', failure_stage='generation', generation_error=?,
                updated_at=datetime('now','localtime')
            WHERE id=? AND latest_generation_id=? AND confirmed_transcript_version=?
            """,
            (
                normalized_error,
                generation["task_id"],
                generation_id,
                generation["confirmed_transcript_version"],
            ),
        )
        row = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (generation_id,),
        ).fetchone()
        return _serialize_class_commentary_generation_row(row)


def _serialize_class_commentary_feedback_draft_row(row: sqlite3.Row) -> dict:
    return dict(row)


_CLASS_COMMENTARY_FEEDBACK_UNSET = object()


def _class_commentary_feedback_record_envelope(
    record: sqlite3.Row | dict,
    generation: sqlite3.Row | dict,
    *,
    derived_text_field: str,
    structured_hash_field: str,
) -> dict:
    source = dict(record)
    return build_class_commentary_feedback_read_envelope(
        schema_version=source.get("feedback_schema_version"),
        structured_json=source.get("structured_feedback_json"),
        stored_hash=source.get(structured_hash_field),
        derived_text=source.get(derived_text_field),
        generation=dict(generation),
    )


def _require_class_commentary_feedback_record_writable(
    record: sqlite3.Row | dict,
    generation: sqlite3.Row | dict,
    *,
    derived_text_field: str,
    structured_hash_field: str,
    expected_schema_version: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
) -> dict:
    source = dict(record)
    envelope = _class_commentary_feedback_record_envelope(
        source,
        generation,
        derived_text_field=derived_text_field,
        structured_hash_field=structured_hash_field,
    )
    status = envelope["feedback_schema_status"]
    if status == "unsupported":
        raise ClassCommentaryFeedbackSchemaUnsupported()
    if status == "invalid":
        raise ClassCommentaryFeedbackSchemaInvalid()
    if status not in {"plain_text", "supported"}:
        raise ClassCommentaryFeedbackSchemaMismatch()
    if (
        expected_schema_version is not _CLASS_COMMENTARY_FEEDBACK_UNSET
        and str(source.get("feedback_schema_version") or "")
        != str(expected_schema_version or "")
    ):
        raise ClassCommentaryFeedbackSchemaMismatch()
    return envelope


def _prepare_class_commentary_feedback_write(
    generation: sqlite3.Row | dict,
    *,
    feedback_text: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
    feedback_schema_version: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
    student_feedback_items: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
) -> dict:
    generation_envelope = _require_class_commentary_feedback_record_writable(
        generation,
        generation,
        derived_text_field="generated_feedback_text",
        structured_hash_field="structured_feedback_hash",
    )
    structured_request = (
        feedback_schema_version is not _CLASS_COMMENTARY_FEEDBACK_UNSET
        or student_feedback_items is not _CLASS_COMMENTARY_FEEDBACK_UNSET
    )
    if generation_envelope["feedback_schema_status"] == "plain_text":
        if structured_request:
            raise ClassCommentaryFeedbackSchemaMismatch()
        if feedback_text is _CLASS_COMMENTARY_FEEDBACK_UNSET:
            raise ValueError("feedback_text is required")
        normalized_feedback = str(feedback_text or "")
        return {
            "feedback_schema_version": "",
            "structured_feedback_json": "",
            "structured_feedback_hash": "",
            "feedback_text": normalized_feedback,
            "content_hash": _class_commentary_content_hash(normalized_feedback),
        }
    if (
        feedback_text is not _CLASS_COMMENTARY_FEEDBACK_UNSET
        or feedback_schema_version is _CLASS_COMMENTARY_FEEDBACK_UNSET
        or student_feedback_items is _CLASS_COMMENTARY_FEEDBACK_UNSET
    ):
        raise ClassCommentaryFeedbackSchemaMismatch()
    canonical = canonicalize_class_commentary_structured_feedback(
        structured_feedback={
            "schema_version": feedback_schema_version,
            "items": student_feedback_items,
        },
        generation=dict(generation),
    )
    return {
        "feedback_schema_version": canonical["feedback_schema_version"],
        "structured_feedback_json": canonical["structured_feedback_json"],
        "structured_feedback_hash": canonical["structured_feedback_hash"],
        "feedback_text": canonical["derived_feedback_text"],
        "content_hash": canonical["structured_feedback_hash"],
    }


def _normalize_class_commentary_expected_latest_revision_id(value: object):
    if value is _CLASS_COMMENTARY_FEEDBACK_UNSET or value is None:
        return value
    if type(value) is not int or value <= 0:
        raise ValueError(
            "expected_latest_revision_id must be a positive integer or null"
        )
    return value


def _class_commentary_confirmation_payload_hash(
    *,
    task_id: int,
    generation_id: int,
    learn_requested: bool,
    expected_draft_version: int,
    expected_latest_revision_id: object,
    feedback_write: dict,
) -> str:
    payload = {
        "expected_draft_version": expected_draft_version,
        "generation_id": int(generation_id),
        "learn_requested": learn_requested,
        "task_id": int(task_id),
    }
    if feedback_write["feedback_schema_version"]:
        if expected_latest_revision_id is _CLASS_COMMENTARY_FEEDBACK_UNSET:
            raise ValueError("expected_latest_revision_id is required")
        payload.update(
            {
                "expected_latest_revision_id": expected_latest_revision_id,
                "feedback_schema_version": feedback_write[
                    "feedback_schema_version"
                ],
                "structured_feedback": json.loads(
                    feedback_write["structured_feedback_json"]
                ),
            }
        )
    else:
        payload["feedback_text"] = feedback_write["feedback_text"]
        if expected_latest_revision_id is not _CLASS_COMMENTARY_FEEDBACK_UNSET:
            payload["expected_latest_revision_id"] = expected_latest_revision_id
    return _class_commentary_content_hash(_class_commentary_canonical_json(payload))


def _prepare_class_commentary_confirmation_replay_feedback_write(
    revision: sqlite3.Row | dict,
    *,
    feedback_text: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
    feedback_schema_version: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
    student_feedback_items: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
) -> dict:
    source = dict(revision)
    stored_schema_version = str(source.get("feedback_schema_version") or "")
    structured_request = (
        feedback_schema_version is not _CLASS_COMMENTARY_FEEDBACK_UNSET
        or student_feedback_items is not _CLASS_COMMENTARY_FEEDBACK_UNSET
    )
    if not stored_schema_version:
        if structured_request or feedback_text is _CLASS_COMMENTARY_FEEDBACK_UNSET:
            raise ClassCommentaryFeedbackSchemaMismatch()
        normalized_feedback = str(feedback_text or "")
        return {
            "feedback_schema_version": "",
            "structured_feedback_json": "",
            "structured_feedback_hash": "",
            "feedback_text": normalized_feedback,
            "content_hash": _class_commentary_content_hash(normalized_feedback),
        }
    if (
        stored_schema_version != CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1
        or feedback_text is not _CLASS_COMMENTARY_FEEDBACK_UNSET
        or feedback_schema_version is _CLASS_COMMENTARY_FEEDBACK_UNSET
        or student_feedback_items is _CLASS_COMMENTARY_FEEDBACK_UNSET
    ):
        raise ClassCommentaryFeedbackSchemaMismatch()
    canonical = canonicalize_class_commentary_structured_feedback_replay(
        structured_feedback={
            "schema_version": feedback_schema_version,
            "items": student_feedback_items,
        },
        frozen_structured_feedback=source.get("structured_feedback_json"),
    )
    return {
        "feedback_schema_version": canonical["feedback_schema_version"],
        "structured_feedback_json": canonical["structured_feedback_json"],
        "structured_feedback_hash": canonical["structured_feedback_hash"],
        "feedback_text": str(source.get("final_feedback_text") or ""),
        "content_hash": canonical["structured_feedback_hash"],
    }


def _get_class_commentary_feedback_draft_conn(
    conn: sqlite3.Connection,
    task_id: int,
    generation_id: int,
    teacher_user_id: int,
):
    return conn.execute(
        """
        SELECT *
        FROM class_commentary_feedback_drafts
        WHERE task_id=? AND generation_id=? AND teacher_user_id=?
        """,
        (task_id, generation_id, teacher_user_id),
    ).fetchone()


def _validate_class_commentary_draft_scope(
    conn: sqlite3.Connection,
    task_id: int,
    generation_id: int,
    teacher_user_id: int,
    based_on_revision_id: Optional[int],
) -> sqlite3.Row:
    generation = conn.execute(
        """
        SELECT generation.*, task.teacher_user_id AS task_teacher_user_id,
               task.organization_id AS task_organization_id,
               task.class_id AS task_class_id
        FROM class_commentary_generations AS generation
        JOIN class_commentary_tasks AS task ON task.id = generation.task_id
        WHERE generation.id=? AND task.id=?
        """,
        (generation_id, task_id),
    ).fetchone()
    if not generation:
        raise ValueError("generation does not belong to task")
    if int(generation["teacher_user_id"]) != int(teacher_user_id):
        raise ValueError("generation is not owned by teacher")
    if int(generation["task_teacher_user_id"]) != int(teacher_user_id):
        raise ValueError("task is not owned by teacher")
    if int(generation["organization_id"]) != int(generation["task_organization_id"]):
        raise ValueError("generation organization does not match task")
    if int(generation["class_id"]) != int(generation["task_class_id"]):
        raise ValueError("generation class does not match task")
    if based_on_revision_id is not None:
        revision = conn.execute(
            """
            SELECT id
            FROM class_commentary_revisions
            WHERE id=? AND task_id=? AND generation_id=? AND teacher_user_id=?
            """,
            (based_on_revision_id, task_id, generation_id, teacher_user_id),
        ).fetchone()
        if not revision:
            raise ValueError("based_on_revision_id does not match draft scope")
    return generation


def get_class_commentary_feedback_draft(
    task_id: int,
    generation_id: int,
    teacher_user_id: int,
) -> Optional[dict]:
    with get_conn() as conn:
        _validate_class_commentary_draft_scope(
            conn,
            task_id,
            generation_id,
            teacher_user_id,
            None,
        )
        row = _get_class_commentary_feedback_draft_conn(
            conn,
            task_id,
            generation_id,
            teacher_user_id,
        )
    return _serialize_class_commentary_feedback_draft_row(row) if row else None


def save_class_commentary_feedback_draft(
    *,
    task_id: int,
    generation_id: int,
    teacher_user_id: int,
    expected_draft_version: int,
    based_on_revision_id: Optional[int] = None,
    feedback_text: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
    feedback_schema_version: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
    student_feedback_items: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
) -> dict:
    try:
        expected_version = int(expected_draft_version)
    except (TypeError, ValueError):
        raise ValueError("expected_draft_version must be an integer")
    if expected_version < 0:
        raise ValueError("expected_draft_version must be non-negative")
    normalized_based_on_revision_id = (
        int(based_on_revision_id) if based_on_revision_id is not None else None
    )
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        generation = _validate_class_commentary_draft_scope(
            conn,
            task_id,
            generation_id,
            teacher_user_id,
            normalized_based_on_revision_id,
        )
        feedback_write = _prepare_class_commentary_feedback_write(
            generation,
            feedback_text=feedback_text,
            feedback_schema_version=feedback_schema_version,
            student_feedback_items=student_feedback_items,
        )
        current = _get_class_commentary_feedback_draft_conn(
            conn,
            task_id,
            generation_id,
            teacher_user_id,
        )
        if current is not None:
            _require_class_commentary_feedback_record_writable(
                current,
                generation,
                derived_text_field="feedback_text",
                structured_hash_field="content_hash",
                expected_schema_version=feedback_write["feedback_schema_version"],
            )
        if current is None:
            if expected_version != 0:
                raise ClassCommentaryDraftVersionConflict(None)
            cursor = conn.execute(
                """
                INSERT INTO class_commentary_feedback_drafts (
                    organization_id, task_id, generation_id, teacher_user_id,
                    based_on_revision_id, feedback_schema_version,
                    structured_feedback_json, feedback_text, content_hash, draft_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    generation["organization_id"],
                    task_id,
                    generation_id,
                    teacher_user_id,
                    normalized_based_on_revision_id,
                    feedback_write["feedback_schema_version"],
                    feedback_write["structured_feedback_json"],
                    feedback_write["feedback_text"],
                    feedback_write["content_hash"],
                ),
            )
            row = conn.execute(
                "SELECT * FROM class_commentary_feedback_drafts WHERE id=?",
                (cursor.lastrowid,),
            ).fetchone()
            return _serialize_class_commentary_feedback_draft_row(row)
        if int(current["draft_version"]) != expected_version:
            raise ClassCommentaryDraftVersionConflict(
                _serialize_class_commentary_feedback_draft_row(current)
            )
        updated = conn.execute(
            """
            UPDATE class_commentary_feedback_drafts
            SET based_on_revision_id=?, feedback_schema_version=?,
                structured_feedback_json=?, feedback_text=?, content_hash=?,
                draft_version=draft_version + 1,
                updated_at=datetime('now','localtime')
            WHERE id=? AND draft_version=?
            """,
            (
                normalized_based_on_revision_id,
                feedback_write["feedback_schema_version"],
                feedback_write["structured_feedback_json"],
                feedback_write["feedback_text"],
                feedback_write["content_hash"],
                current["id"],
                expected_version,
            ),
        )
        if updated.rowcount != 1:
            latest = _get_class_commentary_feedback_draft_conn(
                conn,
                task_id,
                generation_id,
                teacher_user_id,
            )
            raise ClassCommentaryDraftVersionConflict(
                _serialize_class_commentary_feedback_draft_row(latest) if latest else None
            )
        row = conn.execute(
            "SELECT * FROM class_commentary_feedback_drafts WHERE id=?",
            (current["id"],),
        ).fetchone()
        return _serialize_class_commentary_feedback_draft_row(row)


def _class_commentary_feedback_diff(before_text: str, after_text: str) -> str:
    before = str(before_text or "")
    after = str(after_text or "")
    unified_diff = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )
    return _class_commentary_canonical_json(
        {
            "after_hash": _class_commentary_content_hash(after),
            "before_hash": _class_commentary_content_hash(before),
            "changed": before != after,
            "unified_diff": unified_diff,
        }
    )


def _class_commentary_memory_enabled() -> bool:
    return bool(get_runtime_config().get("class_commentary_memory_enabled"))


def _class_commentary_graph_enabled() -> bool:
    return bool(get_runtime_config().get("class_commentary_graph_enabled"))


def _class_commentary_utc_timestamp(value: Optional[datetime] = None) -> str:
    return (value or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _class_commentary_json_dict(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _class_commentary_json_list(value: object) -> list:
    if isinstance(value, list):
        return list(value)
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, json.JSONDecodeError):
        return []
    return list(parsed) if isinstance(parsed, list) else []


def _class_commentary_safe_text(value: object, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _capture_class_commentary_learning_evidence_conn(
    conn: sqlite3.Connection,
    generation: sqlite3.Row,
    *,
    learn_requested: bool,
    captured_at: str,
) -> dict:
    if not learn_requested:
        snapshot: dict = {}
        source_refs: list = []
        missing_sources: list = []
        completeness = "empty"
    else:
        roster = _class_commentary_json_list(generation["attending_roster_snapshot_json"])
        roster_ids = sorted(
            {
                int(item["student_id"])
                for item in roster
                if isinstance(item, dict) and item.get("student_id") is not None
            }
        )
        subject_key = str(generation["subject_key"] or "").strip()
        missing_sources = []
        rows: list[sqlite3.Row] = []
        if not subject_key:
            missing_sources.append(
                {"reason": "subject_key_unavailable", "source_type": "wrong_question_submission"}
            )
        if roster_ids and subject_key:
            for student_id in roster_ids:
                rows.extend(
                    conn.execute(
                        """
                        SELECT id, organization_id, class_id, student_id,
                               recognition_status, archive_status, topic_category,
                               knowledge_tags_json, primary_error_type,
                               secondary_error_summary, child_reason_core_issue,
                               child_reason_key_omission, child_reason_next_step,
                               reflection_summary_json, mastery_tracking_json, updated_at
                        FROM wrong_question_submissions
                        WHERE organization_id=?
                          AND class_id=?
                          AND student_id=?
                          AND recognition_status='recognized'
                          AND archive_status='active'
                          AND (
                              needs_teacher_confirmation=0
                              OR confirmation_status IN ('confirmed','not_required')
                          )
                        ORDER BY COALESCE(updated_at, '') DESC, id DESC
                        LIMIT 20
                        """,
                        (
                            int(generation["organization_id"]),
                            int(generation["class_id"]),
                            student_id,
                        ),
                    ).fetchall()
                )

        wrong_questions = []
        mastery_signals = []
        source_refs = []
        for row in rows:
            reflection = _class_commentary_json_dict(row["reflection_summary_json"])
            mastery = _class_commentary_json_dict(row["mastery_tracking_json"])
            knowledge_tags = [
                _class_commentary_safe_text(value, 80)
                for value in _class_commentary_json_list(row["knowledge_tags_json"])
                if isinstance(value, (str, int, float))
                and _class_commentary_safe_text(value, 80)
            ][:20]
            wrong_question = {
                "source_id": str(row["id"]),
                "student_id": int(row["student_id"]),
                "archive_status": str(row["archive_status"] or ""),
                "topic_category": _class_commentary_safe_text(row["topic_category"], 80),
                "knowledge_tags": knowledge_tags,
                "primary_error_type": _class_commentary_safe_text(row["primary_error_type"], 120),
                "secondary_error_summary": _class_commentary_safe_text(
                    row["secondary_error_summary"], 240
                ),
                "core_issue": _class_commentary_safe_text(row["child_reason_core_issue"], 240),
                "key_omission": _class_commentary_safe_text(row["child_reason_key_omission"], 240),
                "next_step": _class_commentary_safe_text(row["child_reason_next_step"], 240),
                "reflection_summary": {
                    key: reflection[key]
                    for key in (
                        "primary_error_type",
                        "secondary_error_summary",
                        "child_reason_core_issue",
                        "child_reason_key_omission",
                        "child_reason_next_step",
                    )
                    if key in reflection
                    and isinstance(reflection[key], (str, int, float, bool, type(None)))
                },
            }
            mastery_signal = {
                "source_id": str(row["id"]),
                "student_id": int(row["student_id"]),
                "archive_status": str(row["archive_status"] or ""),
                "practice_sheet_count": int(mastery.get("practice_sheet_count") or 0),
                "latest_practice_status": _class_commentary_safe_text(
                    mastery.get("latest_practice_status"), 80
                ),
                "followup_count": int(mastery.get("followup_count") or 0),
                "latest_followup_outcome": _class_commentary_safe_text(
                    mastery.get("latest_followup_outcome"), 80
                ),
                "latest_followup_summary": _class_commentary_safe_text(
                    mastery.get("latest_followup_summary"), 240
                ),
            }
            source_payload = {
                "wrong_question": wrong_question,
                "mastery_signal": mastery_signal,
            }
            source_content_hash = _class_commentary_content_hash(
                _class_commentary_canonical_json(source_payload)
            )
            wrong_questions.append(wrong_question)
            mastery_signals.append(mastery_signal)
            source_refs.append(
                {
                    "source_type": "wrong_question_submission",
                    "source_id": str(row["id"]),
                    "source_updated_at": str(row["updated_at"] or ""),
                    "source_content_hash": source_content_hash,
                }
            )

        wrong_questions.sort(key=lambda item: (item["student_id"], item["source_id"]))
        mastery_signals.sort(key=lambda item: (item["student_id"], item["source_id"]))
        source_refs.sort(key=lambda item: (item["source_type"], item["source_id"]))
        snapshot = {
            "scope": {
                "organization_id": int(generation["organization_id"]),
                "class_id": int(generation["class_id"]),
                "subject_key": subject_key,
                "student_ids": roster_ids,
            },
            "wrong_questions": wrong_questions,
            "mastery_signals": mastery_signals,
        }
        completeness = "partial" if missing_sources else ("complete" if rows else "empty")

    envelope = {
        "schema_version": CLASS_COMMENTARY_LEARNING_EVIDENCE_SCHEMA_VERSION,
        "selector_version": CLASS_COMMENTARY_LEARNING_EVIDENCE_SELECTOR_VERSION,
        "captured_at": captured_at,
        "snapshot": snapshot,
        "source_refs": source_refs,
        "completeness": completeness,
        "missing_sources": missing_sources,
    }
    return {
        **envelope,
        "hash": _class_commentary_content_hash(
            _class_commentary_canonical_json(envelope)
        ),
    }


def _class_commentary_extraction_input_hash(
    generation: sqlite3.Row | dict,
    revision: sqlite3.Row | dict,
) -> str:
    payload = {
        "generation_id": int(generation["id"]),
        "generated_feedback_text": str(generation["generated_feedback_text"] or ""),
        "confirmed_transcript_version": int(generation["confirmed_transcript_version"] or 0),
        "confirmed_transcript_hash": str(generation["confirmed_transcript_hash"] or ""),
        "attending_roster_hash": str(generation["attending_roster_hash"] or ""),
        "skill_registry_id": int(generation["skill_registry_id"]),
        "skill_version_id": int(generation["skill_version_id"]),
        "skill_content_hash": str(generation["skill_content_hash"] or ""),
        "revision_id": int(revision["id"]),
        "final_feedback_text": str(revision["final_feedback_text"] or ""),
        "generation_diff_json": str(revision["generation_diff_json"] or ""),
        "previous_revision_diff_json": str(revision["previous_revision_diff_json"] or ""),
        "learning_evidence_hash": str(revision["learning_evidence_hash"] or ""),
    }
    structured_identity = {
        "generation_feedback_schema_version": str(
            generation["feedback_schema_version"] or ""
        ),
        "generation_structured_feedback_hash": str(
            generation["structured_feedback_hash"] or ""
        ),
        "revision_feedback_schema_version": str(
            revision["feedback_schema_version"] or ""
        ),
        "revision_structured_feedback_hash": str(
            revision["structured_feedback_hash"] or ""
        ),
    }
    if any(structured_identity.values()):
        payload.update(structured_identity)
    return _class_commentary_content_hash(_class_commentary_canonical_json(payload))


def _recompute_class_commentary_learning_evidence_hash(
    revision: sqlite3.Row | dict,
) -> str:
    envelope = {
        "schema_version": str(revision["learning_evidence_schema_version"] or ""),
        "selector_version": str(revision["learning_evidence_selector_version"] or ""),
        "captured_at": str(revision["learning_evidence_captured_at"] or ""),
        "snapshot": _class_commentary_json_dict(
            revision["learning_evidence_snapshot_json"]
        ),
        "source_refs": _class_commentary_json_list(
            revision["learning_evidence_source_refs_json"]
        ),
        "completeness": str(revision["learning_evidence_completeness"] or ""),
        "missing_sources": _class_commentary_json_list(
            revision["learning_evidence_missing_sources_json"]
        ),
    }
    return _class_commentary_content_hash(_class_commentary_canonical_json(envelope))


def _class_commentary_generation_core_snapshot_integrity_valid(
    generation: sqlite3.Row | dict,
) -> bool:
    transcript_snapshot = str(generation["confirmed_transcript_snapshot"] or "")
    roster_snapshot_json = str(generation["attending_roster_snapshot_json"] or "")
    skill_content_snapshot = str(generation["skill_content_snapshot"] or "")
    return bool(
        _class_commentary_content_hash(transcript_snapshot)
        == str(generation["confirmed_transcript_hash"] or "")
        and _class_commentary_content_hash(roster_snapshot_json)
        == str(generation["attending_roster_hash"] or "")
        and _class_commentary_content_hash(skill_content_snapshot)
        == str(generation["skill_content_hash"] or "")
    )


def _class_commentary_memory_extraction_integrity_valid(
    job: sqlite3.Row | dict,
    revision: sqlite3.Row | dict,
    generation: sqlite3.Row | dict,
) -> bool:
    recomputed_learning_hash = _recompute_class_commentary_learning_evidence_hash(revision)
    return bool(
        str(revision["learning_evidence_hash"] or "") == recomputed_learning_hash
        and str(job["learning_evidence_hash"] or "") == recomputed_learning_hash
        and _class_commentary_generation_core_snapshot_integrity_valid(generation)
        and _class_commentary_generation_revision_feedback_integrity_valid(
            generation,
            revision,
        )
        and str(job["extraction_input_hash"] or "")
        == _class_commentary_extraction_input_hash(generation, revision)
    )


def _class_commentary_memory_learning_scope_status_conn(
    conn: sqlite3.Connection,
    task: sqlite3.Row | dict,
    generation: sqlite3.Row | dict,
) -> tuple[bool, str]:
    organization_id = int(generation["organization_id"] or 0)
    class_row = conn.execute(
        "SELECT organization_id, lifecycle_status FROM classes WHERE id=?",
        (generation["class_id"],),
    ).fetchone()
    if (
        not class_row
        or int(class_row["organization_id"] or 0) != organization_id
        or str(class_row["lifecycle_status"] or "active") != "active"
    ):
        return False, "class_not_active"
    teacher = conn.execute(
        "SELECT organization_id, status FROM users WHERE id=?",
        (generation["teacher_user_id"],),
    ).fetchone()
    if (
        not teacher
        or int(teacher["organization_id"] or 0) != organization_id
        or str(teacher["status"] or "") != "active"
    ):
        return False, "teacher_not_active"
    registry = conn.execute(
        """
        SELECT organization_id, status
        FROM class_commentary_skills
        WHERE id=?
        """,
        (generation["skill_registry_id"],),
    ).fetchone()
    if (
        not registry
        or int(registry["organization_id"] or 0) != organization_id
        or str(registry["status"] or "") != "active"
    ):
        return False, "skill_not_active"
    roster_ids = sorted(
        {
            int(item["student_id"])
            for item in _class_commentary_json_list(
                generation["attending_roster_snapshot_json"]
            )
            if isinstance(item, dict) and item.get("student_id") is not None
        }
    )
    if roster_ids:
        placeholders = ",".join("?" for _ in roster_ids)
        active_roster_count = conn.execute(
            f"""
            SELECT COUNT(DISTINCT student.id) AS value
            FROM students AS student
            JOIN class_students AS membership ON membership.student_id=student.id
            WHERE student.id IN ({placeholders})
              AND student.organization_id=?
              AND student.status='active'
              AND membership.class_id=?
            """,
            (*roster_ids, organization_id, generation["class_id"]),
        ).fetchone()["value"]
        if int(active_roster_count or 0) != len(roster_ids):
            return False, "roster_not_active"
    if (
        int(task["organization_id"] or 0) != organization_id
        or int(task["class_id"] or 0) != int(generation["class_id"] or 0)
        or int(task["teacher_user_id"] or 0)
        != int(generation["teacher_user_id"] or 0)
    ):
        return False, "task_scope_mismatch"
    return True, ""


def _class_commentary_memory_target_state(record: sqlite3.Row | dict) -> dict:
    return {
        "memory_record_id": int(record["id"]),
        "organization_id": int(record["organization_id"]),
        "memory_type": str(record["memory_type"]),
        "memory_text": str(record["memory_text"]),
        "record_version": int(record["record_version"]),
        "desired_status": str(record["desired_status"]),
        "scope_skill_registry_id": record["scope_skill_registry_id"],
        "student_id": record["student_id"],
        "subject_key": record["subject_key"],
        "scope_hash": str(record["scope_hash"]),
        "canonical_key": str(record["canonical_key"]),
    }


def _create_class_commentary_memory_operation_conn(
    conn: sqlite3.Connection,
    record: sqlite3.Row | dict,
    *,
    operation_type: str,
    source_type: str,
    source_id: Optional[int],
    extraction_job_id: Optional[int] = None,
    extractor_version: str = CLASS_COMMENTARY_MEMORY_EXTRACTOR_VERSION,
    memory_schema_version: str = CLASS_COMMENTARY_MEMORY_SCHEMA_VERSION,
    cleanup_scope_type: Optional[str] = None,
    cleanup_scope_id: Optional[int] = None,
) -> sqlite3.Row:
    if source_type == "cleanup":
        if cleanup_scope_type not in {
            "organization",
            "task",
            "class",
            "teacher",
            "student",
        }:
            raise ValueError("cleanup_scope_type is invalid")
        if cleanup_scope_id is None or int(cleanup_scope_id) <= 0:
            raise ValueError("cleanup_scope_id must be a positive integer")
        cleanup_scope_id = int(cleanup_scope_id)
        if source_id is None or int(source_id) != cleanup_scope_id:
            raise ValueError("cleanup source_id must match cleanup_scope_id")
    elif cleanup_scope_type is not None or cleanup_scope_id is not None:
        raise ValueError("cleanup scope is only valid for cleanup operations")
    target_state = _class_commentary_memory_target_state(record)
    source_revision = conn.execute(
        """
        SELECT revision.generation_id, revision.confirmed_at
        FROM class_commentary_revisions AS revision
        WHERE revision.id=?
        """,
        (record["created_from_revision_id"],),
    ).fetchone()
    evidence_count = conn.execute(
        """
        SELECT COUNT(*) AS value
        FROM class_commentary_memory_evidence
        WHERE memory_record_id=? AND status='active'
        """,
        (record["id"],),
    ).fetchone()["value"]
    target_state["projection_metadata"] = {
        "organization_id": int(record["organization_id"]),
        "scope_skill_registry_id": record["scope_skill_registry_id"],
        "student_id": record["student_id"],
        "subject_key": record["subject_key"],
        "memory_type": str(record["memory_type"]),
        "generation_id": int(source_revision["generation_id"]) if source_revision else None,
        "created_from_revision_id": int(record["created_from_revision_id"]),
        "memory_record_id": int(record["id"]),
        "record_version": int(record["record_version"]),
        "evidence_count": int(evidence_count or 0),
        "desired_status": str(record["desired_status"]),
        "confidence": float(record["confidence"]),
        "occurred_at": str(record["updated_at"] or record["created_at"] or ""),
    }
    target_state_json = _class_commentary_canonical_json(target_state)
    target_state_hash = _class_commentary_content_hash(target_state_json)
    operation_version = int(record["record_version"])
    operation_key = (
        f"cc-memory-{int(record['id'])}-v{operation_version}-{target_state_hash}"
    )
    existing = conn.execute(
        """
        SELECT * FROM class_commentary_memory_operations
        WHERE memory_record_id=? AND operation_version=?
        """,
        (int(record["id"]), operation_version),
    ).fetchone()
    if existing:
        if str(existing["operation_key"]) != operation_key:
            raise ClassCommentaryConfirmationRequestConflict(
                "memory operation version was already used with a different target"
            )
        if source_type == "cleanup" and (
            str(existing["cleanup_scope_type"] or "") != cleanup_scope_type
            or int(existing["cleanup_scope_id"] or 0) != cleanup_scope_id
        ):
            raise ClassCommentaryConfirmationRequestConflict(
                "memory operation version was already used by another cleanup scope"
            )
        return existing
    cursor = conn.execute(
        """
        INSERT INTO class_commentary_memory_operations (
            organization_id, extraction_job_id, memory_record_id,
            source_type, source_id, cleanup_scope_type, cleanup_scope_id,
            operation_type, operation_key,
            operation_version, expected_record_version,
            target_state_json, target_state_hash, mem0_memory_id,
            status, attempt_count, extractor_version, memory_schema_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)
        """,
        (
            int(record["organization_id"]),
            extraction_job_id,
            int(record["id"]),
            source_type,
            source_id,
            cleanup_scope_type,
            cleanup_scope_id,
            operation_type,
            operation_key,
            operation_version,
            operation_version,
            target_state_json,
            target_state_hash,
            record["mem0_memory_id"],
            extractor_version,
            memory_schema_version,
        ),
    )
    return conn.execute(
        "SELECT * FROM class_commentary_memory_operations WHERE id=?",
        (cursor.lastrowid,),
    ).fetchone()


def _advance_class_commentary_memory_record_projection_conn(
    conn: sqlite3.Connection,
    record_id: int,
    *,
    desired_status: Optional[str],
    operation_type: str,
    source_type: str,
    source_id: Optional[int],
    extraction_job_id: Optional[int] = None,
    extractor_version: str = CLASS_COMMENTARY_MEMORY_EXTRACTOR_VERSION,
    memory_schema_version: str = CLASS_COMMENTARY_MEMORY_SCHEMA_VERSION,
    cleanup_scope_type: Optional[str] = None,
    cleanup_scope_id: Optional[int] = None,
) -> sqlite3.Row:
    if desired_status is None:
        updated = conn.execute(
            """
            UPDATE class_commentary_memory_records
            SET record_version=record_version + 1,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (record_id,),
        )
    else:
        updated = conn.execute(
            """
            UPDATE class_commentary_memory_records
            SET desired_status=?, record_version=record_version + 1,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (desired_status, record_id),
        )
    if updated.rowcount != 1:
        raise ValueError("class commentary memory record not found")
    record = conn.execute(
        "SELECT * FROM class_commentary_memory_records WHERE id=?",
        (record_id,),
    ).fetchone()
    conn.execute(
        """
        UPDATE class_commentary_memory_operations
        SET status='obsolete', last_error='record_version_advanced',
            updated_at=datetime('now','localtime')
        WHERE memory_record_id=?
          AND expected_record_version<>?
          AND status IN ('pending','retry_wait','reconcile_needed','failed')
        """,
        (record_id, record["record_version"]),
    )
    return _create_class_commentary_memory_operation_conn(
        conn,
        record,
        operation_type=operation_type,
        source_type=source_type,
        source_id=source_id,
        extraction_job_id=extraction_job_id,
        extractor_version=extractor_version,
        memory_schema_version=memory_schema_version,
        cleanup_scope_type=cleanup_scope_type,
        cleanup_scope_id=cleanup_scope_id,
    )


def _create_class_commentary_memory_extraction_job_conn(
    conn: sqlite3.Connection,
    generation: sqlite3.Row,
    revision: sqlite3.Row,
) -> sqlite3.Row:
    extraction_input_hash = _class_commentary_extraction_input_hash(generation, revision)
    request_key = _class_commentary_content_hash(
        _class_commentary_canonical_json(
            {
                "revision_id": int(revision["id"]),
                "extraction_input_hash": extraction_input_hash,
                "extractor_version": CLASS_COMMENTARY_MEMORY_EXTRACTOR_VERSION,
                "memory_schema_version": CLASS_COMMENTARY_MEMORY_SCHEMA_VERSION,
            }
        )
    )
    conn.execute(
        """
        INSERT INTO class_commentary_memory_extraction_jobs (
            organization_id, revision_id, request_key, extractor_version,
            memory_schema_version, extraction_input_hash,
            learning_evidence_hash, status, attempt_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', 0)
        ON CONFLICT(revision_id, extractor_version, memory_schema_version) DO NOTHING
        """,
        (
            int(revision["organization_id"]),
            int(revision["id"]),
            request_key,
            CLASS_COMMENTARY_MEMORY_EXTRACTOR_VERSION,
            CLASS_COMMENTARY_MEMORY_SCHEMA_VERSION,
            extraction_input_hash,
            str(revision["learning_evidence_hash"]),
        ),
    )
    job = conn.execute(
        """
        SELECT * FROM class_commentary_memory_extraction_jobs
        WHERE revision_id=? AND extractor_version=? AND memory_schema_version=?
        """,
        (
            int(revision["id"]),
            CLASS_COMMENTARY_MEMORY_EXTRACTOR_VERSION,
            CLASS_COMMENTARY_MEMORY_SCHEMA_VERSION,
        ),
    ).fetchone()
    if not job or str(job["request_key"]) != request_key:
        raise ClassCommentaryConfirmationRequestConflict(
            "memory extraction job key conflict"
        )
    return job


def _supersede_class_commentary_memory_for_new_revision_conn(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    task_id: int,
    revision_id: int,
    captured_at: str,
) -> dict:
    obsoleted_jobs = conn.execute(
        """
        UPDATE class_commentary_memory_extraction_jobs
        SET status='obsolete', obsolete_reason='revision_superseded',
            obsoleted_by_revision_id=?, obsoleted_at=?, completed_at=?,
            updated_at=datetime('now','localtime')
        WHERE organization_id=?
          AND revision_id IN (
              SELECT id FROM class_commentary_revisions
              WHERE task_id=? AND id<>?
          )
          AND status IN ('queued','running','retry_wait','failed')
        """,
        (
            revision_id,
            captured_at,
            captured_at,
            organization_id,
            task_id,
            revision_id,
        ),
    ).rowcount
    evidence_rows = conn.execute(
        """
        SELECT evidence.id, evidence.memory_record_id
        FROM class_commentary_memory_evidence AS evidence
        JOIN class_commentary_revisions AS revision ON revision.id=evidence.revision_id
        WHERE evidence.organization_id=?
          AND revision.task_id=?
          AND revision.id<>?
          AND evidence.status='active'
        ORDER BY evidence.id
        """,
        (organization_id, task_id, revision_id),
    ).fetchall()
    evidence_ids = [int(row["id"]) for row in evidence_rows]
    record_ids = sorted({int(row["memory_record_id"]) for row in evidence_rows})
    if evidence_ids:
        placeholders = ",".join("?" for _ in evidence_ids)
        conn.execute(
            f"""
            UPDATE class_commentary_memory_evidence
            SET status='superseded', updated_at=datetime('now','localtime')
            WHERE id IN ({placeholders}) AND status='active'
            """,
            evidence_ids,
        )
    operation_ids = []
    for record_id in record_ids:
        active_count = conn.execute(
            """
            SELECT COUNT(*) AS value
            FROM class_commentary_memory_evidence
            WHERE memory_record_id=? AND status='active'
            """,
            (record_id,),
        ).fetchone()["value"]
        if int(active_count or 0) > 0:
            operation = _advance_class_commentary_memory_record_projection_conn(
                conn,
                record_id,
                desired_status=None,
                operation_type="update",
                source_type="revision",
                source_id=revision_id,
            )
            operation_ids.append(int(operation["id"]))
            continue
        current_record = conn.execute(
            """
            SELECT * FROM class_commentary_memory_records
            WHERE id=? AND organization_id=? AND desired_status='active'
            """,
            (record_id, organization_id),
        ).fetchone()
        if not current_record:
            continue
        operation = _advance_class_commentary_memory_record_projection_conn(
            conn,
            record_id,
            desired_status="superseded",
            operation_type="supersede",
            source_type="revision",
            source_id=revision_id,
        )
        operation_ids.append(int(operation["id"]))
    return {
        "obsoleted_job_count": int(obsoleted_jobs or 0),
        "superseded_evidence_ids": evidence_ids,
        "cleanup_operation_ids": operation_ids,
    }


def _serialize_class_commentary_revision_row(
    row: sqlite3.Row,
) -> dict:
    item = dict(row)
    confirmed_draft_version = int(item.get("confirmed_draft_version") or 0)
    confirmed_draft = None
    if confirmed_draft_version > 0:
        try:
            parsed = json.loads(str(item.get("confirmed_draft_snapshot_json") or "{}"))
        except (TypeError, json.JSONDecodeError):
            parsed = None
        if isinstance(parsed, dict) and parsed:
            confirmed_draft = parsed
    item["draft_version"] = confirmed_draft_version
    item["draft"] = confirmed_draft
    return item


def get_class_commentary_revision(revision_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM class_commentary_revisions WHERE id=?",
            (revision_id,),
        ).fetchone()
    return _serialize_class_commentary_revision_row(row) if row else None


def list_class_commentary_revisions(task_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM class_commentary_revisions
            WHERE task_id=?
            ORDER BY revision_no DESC
            """,
            (task_id,),
        ).fetchall()
    return [_serialize_class_commentary_revision_row(row) for row in rows]


def _normalize_class_commentary_confirmation_inputs(
    *,
    generation_id: object,
    learn_requested: object,
    expected_draft_version: object,
    expected_latest_revision_id: object,
) -> tuple[int, bool, int, object]:
    try:
        normalized_generation_id = int(generation_id)
    except (TypeError, ValueError):
        normalized_generation_id = 0
    if normalized_generation_id <= 0:
        raise ValueError("generation_id is required")
    if expected_draft_version is None:
        raise ValueError("expected_draft_version is required")
    try:
        expected_version = int(expected_draft_version)
    except (TypeError, ValueError):
        raise ValueError("expected_draft_version must be an integer")
    if expected_version < 0:
        raise ValueError("expected_draft_version must be non-negative")
    if not isinstance(learn_requested, bool):
        raise ValueError("learn must be a boolean")
    normalized_expected_latest_revision_id = (
        _normalize_class_commentary_expected_latest_revision_id(
            expected_latest_revision_id
        )
    )
    return (
        normalized_generation_id,
        learn_requested,
        expected_version,
        normalized_expected_latest_revision_id,
    )


def confirm_class_commentary_feedback(
    *,
    task_id: int,
    generation_id: object,
    teacher_user_id: int,
    learn_requested: object,
    expected_draft_version: object,
    confirmation_request_id: str,
    feedback_text: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
    feedback_schema_version: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
    student_feedback_items: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
    expected_latest_revision_id: object = _CLASS_COMMENTARY_FEEDBACK_UNSET,
) -> dict:
    normalized_request_id = str(confirmation_request_id or "").strip()
    if not normalized_request_id:
        raise ValueError("confirmation_request_id is required")

    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            """
            SELECT *
            FROM class_commentary_revisions
            WHERE task_id=? AND confirmation_request_id=?
            """,
            (task_id, normalized_request_id),
        ).fetchone()
        if existing:
            if int(existing["teacher_user_id"]) != int(teacher_user_id):
                raise ValueError("task is not owned by teacher")
            try:
                (
                    replay_generation_id,
                    replay_learn_requested,
                    replay_expected_version,
                    replay_expected_latest_revision_id,
                ) = _normalize_class_commentary_confirmation_inputs(
                    generation_id=generation_id,
                    learn_requested=learn_requested,
                    expected_draft_version=expected_draft_version,
                    expected_latest_revision_id=expected_latest_revision_id,
                )
                replay_feedback_write = (
                    _prepare_class_commentary_confirmation_replay_feedback_write(
                        existing,
                        feedback_text=feedback_text,
                        feedback_schema_version=feedback_schema_version,
                        student_feedback_items=student_feedback_items,
                    )
                )
                if (
                    replay_feedback_write["feedback_schema_version"]
                    and replay_expected_latest_revision_id
                    is _CLASS_COMMENTARY_FEEDBACK_UNSET
                ):
                    raise ValueError("expected_latest_revision_id is required")
                if (
                    not replay_feedback_write["feedback_schema_version"]
                    and not replay_feedback_write["feedback_text"].strip()
                ):
                    raise ValueError("feedback_text is required")
                replay_payload_hash = _class_commentary_confirmation_payload_hash(
                    task_id=task_id,
                    generation_id=replay_generation_id,
                    learn_requested=replay_learn_requested,
                    expected_draft_version=replay_expected_version,
                    expected_latest_revision_id=(
                        replay_expected_latest_revision_id
                    ),
                    feedback_write=replay_feedback_write,
                )
            except (
                ClassCommentaryFeedbackSchemaMismatch,
                ClassCommentaryStructuredFeedbackValidationError,
                TypeError,
                ValueError,
            ) as exc:
                raise ClassCommentaryConfirmationRequestConflict(
                    "confirmation request_id was already used with a different payload"
                ) from exc
            if str(existing["confirmation_payload_hash"]) != replay_payload_hash:
                raise ClassCommentaryConfirmationRequestConflict(
                    "confirmation request_id was already used with a different payload"
                )
            result = _serialize_class_commentary_revision_row(existing)
            job = conn.execute(
                """
                SELECT * FROM class_commentary_memory_extraction_jobs
                WHERE revision_id=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (existing["id"],),
            ).fetchone()
            result["memory_job"] = dict(job) if job else None
            from class_commentary_learning_graph import (
                get_graph_extraction_job_for_revision_conn,
            )

            result["graph_job"] = get_graph_extraction_job_for_revision_conn(
                conn,
                int(existing["id"]),
            )
            return result
        (
            generation_id,
            learn_requested,
            expected_version,
            normalized_expected_latest_revision_id,
        ) = _normalize_class_commentary_confirmation_inputs(
            generation_id=generation_id,
            learn_requested=learn_requested,
            expected_draft_version=expected_draft_version,
            expected_latest_revision_id=expected_latest_revision_id,
        )
        generation = _validate_class_commentary_draft_scope(
            conn,
            task_id,
            generation_id,
            teacher_user_id,
            None,
        )
        feedback_write = _prepare_class_commentary_feedback_write(
            generation,
            feedback_text=feedback_text,
            feedback_schema_version=feedback_schema_version,
            student_feedback_items=student_feedback_items,
        )
        if (
            feedback_write["feedback_schema_version"]
            and normalized_expected_latest_revision_id
            is _CLASS_COMMENTARY_FEEDBACK_UNSET
        ):
            raise ValueError("expected_latest_revision_id is required")
        if (
            not feedback_write["feedback_schema_version"]
            and not feedback_write["feedback_text"].strip()
        ):
            raise ValueError("feedback_text is required")
        confirmation_payload_hash = _class_commentary_confirmation_payload_hash(
            task_id=task_id,
            generation_id=generation_id,
            learn_requested=learn_requested,
            expected_draft_version=expected_version,
            expected_latest_revision_id=normalized_expected_latest_revision_id,
            feedback_write=feedback_write,
        )
        if str(generation["status"]) != "succeeded":
            raise ValueError("generation must be succeeded before confirmation")

        task = conn.execute(
            "SELECT * FROM class_commentary_tasks WHERE id=?",
            (task_id,),
        ).fetchone()
        if not task:
            raise ValueError("class commentary task not found")
        current_draft = _get_class_commentary_feedback_draft_conn(
            conn,
            task_id,
            generation_id,
            teacher_user_id,
        )
        if current_draft is not None:
            _require_class_commentary_feedback_record_writable(
                current_draft,
                generation,
                derived_text_field="feedback_text",
                structured_hash_field="content_hash",
                expected_schema_version=feedback_write["feedback_schema_version"],
            )
        if current_draft is None:
            if expected_version != 0:
                raise ClassCommentaryDraftVersionConflict(None)
        elif int(current_draft["draft_version"]) != expected_version:
            raise ClassCommentaryDraftVersionConflict(
                _serialize_class_commentary_feedback_draft_row(current_draft)
            )

        current_latest_revision_id = (
            int(task["latest_revision_id"])
            if task["latest_revision_id"] is not None
            else None
        )
        if (
            normalized_expected_latest_revision_id
            is not _CLASS_COMMENTARY_FEEDBACK_UNSET
            and normalized_expected_latest_revision_id
            != current_latest_revision_id
        ):
            current_latest_revision = None
            if current_latest_revision_id is not None:
                current_latest_row = conn.execute(
                    """
                    SELECT * FROM class_commentary_revisions
                    WHERE id=? AND task_id=?
                    """,
                    (current_latest_revision_id, task_id),
                ).fetchone()
                if not current_latest_row:
                    raise ValueError("task latest revision pointer is invalid")
                current_latest_revision = _serialize_class_commentary_revision_row(
                    current_latest_row
                )
            raise ClassCommentaryRevisionVersionConflict(
                current_latest_revision
            )
        if learn_requested and not _class_commentary_memory_enabled():
            raise ClassCommentaryMemoryNotEnabled()
        if learn_requested and (
            str(generation["origin"]) != "runtime"
            or str(generation["snapshot_completeness"]) != "complete"
            or str(generation["execution_snapshot_status"]) != "ready"
        ):
            raise ValueError("generation_snapshot_incomplete")

        previous_revision = None
        if task["latest_revision_id"] is not None:
            previous_revision = conn.execute(
                """
                SELECT *
                FROM class_commentary_revisions
                WHERE id=? AND task_id=?
                """,
                (task["latest_revision_id"], task_id),
            ).fetchone()
            if not previous_revision:
                raise ValueError("task latest revision pointer is invalid")
            previous_generation = conn.execute(
                "SELECT * FROM class_commentary_generations WHERE id=?",
                (previous_revision["generation_id"],),
            ).fetchone()
            if not previous_generation:
                raise ValueError("revision generation pointer is invalid")
            _require_class_commentary_feedback_record_writable(
                previous_revision,
                previous_generation,
                derived_text_field="final_feedback_text",
                structured_hash_field="structured_feedback_hash",
                expected_schema_version=(
                    _CLASS_COMMENTARY_FEEDBACK_UNSET
                    if feedback_write["feedback_schema_version"]
                    else ""
                ),
            )
        revision_no = int(task["feedback_revision_no"] or 0) + 1
        captured_at = conn.execute(
            "SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now') AS value"
        ).fetchone()["value"]
        learning_evidence = _capture_class_commentary_learning_evidence_conn(
            conn,
            generation,
            learn_requested=learn_requested,
            captured_at=captured_at,
        )
        generation_feedback = str(generation["generated_feedback_text"] or "")
        previous_feedback = (
            str(previous_revision["final_feedback_text"] or "")
            if previous_revision
            else ""
        )
        accepted_without_edit = (
            feedback_write["structured_feedback_hash"]
            == str(generation["structured_feedback_hash"] or "")
            if feedback_write["feedback_schema_version"]
            else feedback_write["feedback_text"] == generation_feedback
        )
        unchanged_from_previous_revision = bool(
            previous_revision
            and (
                feedback_write["structured_feedback_hash"]
                == str(previous_revision["structured_feedback_hash"] or "")
                if feedback_write["feedback_schema_version"]
                and str(previous_revision["feedback_schema_version"] or "")
                else feedback_write["feedback_text"] == previous_feedback
            )
        )
        cursor = conn.execute(
            """
            INSERT INTO class_commentary_revisions (
                organization_id, task_id, generation_id, teacher_user_id,
                revision_no, confirmation_request_id, confirmation_payload_hash,
                previous_revision_id, feedback_schema_version,
                structured_feedback_json, structured_feedback_hash,
                final_feedback_text, generation_diff_json,
                previous_revision_diff_json, learning_evidence_schema_version,
                learning_evidence_selector_version, learning_evidence_snapshot_json,
                learning_evidence_source_refs_json, learning_evidence_hash,
                learning_evidence_captured_at, learning_evidence_completeness,
                learning_evidence_missing_sources_json, learn_requested,
                accepted_without_edit, unchanged_from_previous_revision, confirmed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generation["organization_id"],
                task_id,
                generation_id,
                teacher_user_id,
                revision_no,
                normalized_request_id,
                confirmation_payload_hash,
                previous_revision["id"] if previous_revision else None,
                feedback_write["feedback_schema_version"],
                feedback_write["structured_feedback_json"],
                feedback_write["structured_feedback_hash"],
                feedback_write["feedback_text"],
                _class_commentary_feedback_diff(
                    generation_feedback,
                    feedback_write["feedback_text"],
                ),
                (
                    _class_commentary_feedback_diff(
                        previous_feedback,
                        feedback_write["feedback_text"],
                    )
                    if previous_revision
                    else None
                ),
                learning_evidence["schema_version"],
                learning_evidence["selector_version"],
                _class_commentary_canonical_json(learning_evidence["snapshot"]),
                _class_commentary_canonical_json(learning_evidence["source_refs"]),
                learning_evidence["hash"],
                captured_at,
                learning_evidence["completeness"],
                _class_commentary_canonical_json(learning_evidence["missing_sources"]),
                1 if learn_requested else 0,
                1 if accepted_without_edit else 0,
                1 if unchanged_from_previous_revision else 0,
                captured_at,
            ),
        )
        revision_id = int(cursor.lastrowid)
        if current_draft is None:
            draft_cursor = conn.execute(
                """
                INSERT INTO class_commentary_feedback_drafts (
                    organization_id, task_id, generation_id, teacher_user_id,
                    based_on_revision_id, feedback_schema_version,
                    structured_feedback_json, feedback_text, content_hash, draft_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    generation["organization_id"],
                    task_id,
                    generation_id,
                    teacher_user_id,
                    revision_id,
                    feedback_write["feedback_schema_version"],
                    feedback_write["structured_feedback_json"],
                    feedback_write["feedback_text"],
                    feedback_write["content_hash"],
                ),
            )
            draft_id = int(draft_cursor.lastrowid)
        else:
            updated = conn.execute(
                """
                UPDATE class_commentary_feedback_drafts
                SET based_on_revision_id=?, feedback_schema_version=?,
                    structured_feedback_json=?, feedback_text=?, content_hash=?,
                    draft_version=draft_version + 1,
                    updated_at=datetime('now','localtime')
                WHERE id=? AND draft_version=?
                """,
                (
                    revision_id,
                    feedback_write["feedback_schema_version"],
                    feedback_write["structured_feedback_json"],
                    feedback_write["feedback_text"],
                    feedback_write["content_hash"],
                    current_draft["id"],
                    expected_version,
                ),
            )
            if updated.rowcount != 1:
                latest = _get_class_commentary_feedback_draft_conn(
                    conn,
                    task_id,
                    generation_id,
                    teacher_user_id,
                )
                raise ClassCommentaryDraftVersionConflict(
                    _serialize_class_commentary_feedback_draft_row(latest) if latest else None
                )
            draft_id = int(current_draft["id"])
        updated_task = conn.execute(
            """
            UPDATE class_commentary_tasks
            SET feedback_revision_no=?, latest_revision_id=?,
                final_feedback_text=?, feedback_text=?, feedback_confirmed_at=?,
                updated_at=datetime('now','localtime')
            WHERE id=? AND feedback_revision_no=? AND latest_revision_id IS ?
            """,
            (
                revision_no,
                revision_id,
                feedback_write["feedback_text"],
                feedback_write["feedback_text"],
                captured_at,
                task_id,
                int(task["feedback_revision_no"] or 0),
                current_latest_revision_id,
            ),
        )
        if updated_task.rowcount != 1:
            raise ClassCommentaryConfirmationRequestConflict("task revision sequence changed")
        revision = conn.execute(
            "SELECT * FROM class_commentary_revisions WHERE id=?",
            (revision_id,),
        ).fetchone()
        draft = conn.execute(
            "SELECT * FROM class_commentary_feedback_drafts WHERE id=?",
            (draft_id,),
        ).fetchone()
        confirmed_draft = _serialize_class_commentary_feedback_draft_row(draft)
        revision_snapshot_updated = conn.execute(
            """
            UPDATE class_commentary_revisions
            SET confirmed_draft_version=?, confirmed_draft_snapshot_json=?
            WHERE id=? AND confirmed_draft_version=0
            """,
            (
                int(draft["draft_version"]),
                _class_commentary_canonical_json(confirmed_draft),
                revision_id,
            ),
        )
        if revision_snapshot_updated.rowcount != 1:
            raise ClassCommentaryConfirmationRequestConflict(
                "revision draft snapshot changed"
            )
        revision = conn.execute(
            "SELECT * FROM class_commentary_revisions WHERE id=?",
            (revision_id,),
        ).fetchone()
        _supersede_class_commentary_memory_for_new_revision_conn(
            conn,
            organization_id=int(generation["organization_id"]),
            task_id=task_id,
            revision_id=revision_id,
            captured_at=captured_at,
        )
        memory_job = None
        if learn_requested:
            memory_job = _create_class_commentary_memory_extraction_job_conn(
                conn,
                generation,
                revision,
            )
        graph_job = None
        if learn_requested and _class_commentary_graph_enabled():
            from class_commentary_learning_graph import create_graph_extraction_job_conn

            conn.execute(
                "UPDATE class_commentary_revisions SET graph_extraction_requested=1 WHERE id=?",
                (revision_id,),
            )
            revision = conn.execute(
                "SELECT * FROM class_commentary_revisions WHERE id=?",
                (revision_id,),
            ).fetchone()
            graph_job = create_graph_extraction_job_conn(
                conn,
                dict(generation),
                dict(revision),
            )
        result = _serialize_class_commentary_revision_row(revision)
        result["memory_job"] = dict(memory_job) if memory_job else None
        result["graph_job"] = dict(graph_job) if graph_job else None
        return result


def _serialize_class_commentary_memory_record(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    item["creation_evidence_snapshot"] = _class_commentary_json_dict(
        item.get("creation_evidence_snapshot_json")
    )
    return item


def _serialize_class_commentary_memory_job(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    item["result_summary"] = _class_commentary_json_dict(item.get("result_summary_json"))
    return item


def _serialize_class_commentary_memory_operation(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    item["target_state"] = _class_commentary_json_dict(item.get("target_state_json"))
    item["projection_metadata"] = _class_commentary_json_dict(
        item["target_state"].get("projection_metadata")
    )
    item["projection_metadata"]["operation_key"] = str(item.get("operation_key") or "")
    item["projection_metadata"]["status"] = str(
        item["projection_metadata"].get("desired_status")
        or item["target_state"].get("desired_status")
        or ""
    )
    return item


def get_class_commentary_memory_extraction_job(job_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM class_commentary_memory_extraction_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
    return _serialize_class_commentary_memory_job(row) if row else None


def get_class_commentary_memory_extraction_job_for_revision(
    revision_id: int,
) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM class_commentary_memory_extraction_jobs
            WHERE revision_id=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (revision_id,),
        ).fetchone()
    return _serialize_class_commentary_memory_job(row) if row else None


def list_dispatchable_class_commentary_memory_extraction_jobs(
    *,
    limit: int = 100,
    now: Optional[str] = None,
) -> list[dict]:
    current = now or _class_commentary_utc_timestamp()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT job.*
            FROM class_commentary_memory_extraction_jobs AS job
            JOIN class_commentary_revisions AS revision ON revision.id=job.revision_id
            JOIN class_commentary_tasks AS task ON task.id=revision.task_id
            WHERE task.latest_revision_id=job.revision_id
              AND job.attempt_count < 4
              AND (
                  job.status='queued'
                  OR (job.status='retry_wait' AND job.next_attempt_at<=?)
              )
            ORDER BY job.created_at, job.id
            LIMIT ?
            """,
            (current, max(1, min(int(limit), 500))),
        ).fetchall()
    return [_serialize_class_commentary_memory_job(row) for row in rows]


def mark_class_commentary_memory_extraction_job_enqueued(
    job_id: int,
    rq_job_id: str,
) -> Optional[dict]:
    normalized_rq_job_id = str(rq_job_id or "").strip()
    if not normalized_rq_job_id:
        raise ValueError("rq_job_id is required")
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_memory_extraction_jobs
            SET rq_job_id=?, enqueued_at=?, updated_at=datetime('now','localtime')
            WHERE id=? AND status IN ('queued','retry_wait')
            """,
            (normalized_rq_job_id, _class_commentary_utc_timestamp(), job_id),
        )
        row = conn.execute(
            "SELECT * FROM class_commentary_memory_extraction_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
    return _serialize_class_commentary_memory_job(row) if row else None


def claim_class_commentary_memory_extraction_job(
    job_id: int,
    *,
    claim_owner: str,
    rq_job_id: Optional[str] = None,
    now: Optional[str] = None,
) -> Optional[dict]:
    normalized_owner = str(claim_owner or "").strip()
    if not normalized_owner:
        raise ValueError("claim_owner is required")
    current = now or _class_commentary_utc_timestamp()
    claim_token = secrets.token_hex(24)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT job.*, revision.task_id, revision.generation_id,
                   revision.learning_evidence_hash AS revision_learning_evidence_hash,
                   task.latest_revision_id
            FROM class_commentary_memory_extraction_jobs AS job
            JOIN class_commentary_revisions AS revision ON revision.id=job.revision_id
            JOIN class_commentary_tasks AS task ON task.id=revision.task_id
            WHERE job.id=?
            """,
            (job_id,),
        ).fetchone()
        if not row:
            return None
        if int(row["latest_revision_id"] or 0) != int(row["revision_id"]):
            conn.execute(
                """
                UPDATE class_commentary_memory_extraction_jobs
                SET status='obsolete', obsolete_reason='revision_not_effective',
                    obsoleted_by_revision_id=?, obsoleted_at=?, completed_at=?,
                    updated_at=datetime('now','localtime')
                WHERE id=? AND status IN ('queued','retry_wait','running','failed')
                """,
                (row["latest_revision_id"], current, current, job_id),
            )
            return None
        revision = conn.execute(
            "SELECT * FROM class_commentary_revisions WHERE id=?",
            (row["revision_id"],),
        ).fetchone()
        generation = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (row["generation_id"],),
        ).fetchone()
        task = conn.execute(
            "SELECT * FROM class_commentary_tasks WHERE id=?",
            (row["task_id"],),
        ).fetchone()
        scope_active, obsolete_reason = _class_commentary_memory_learning_scope_status_conn(
            conn,
            task,
            generation,
        )
        if not scope_active:
            conn.execute(
                """
                UPDATE class_commentary_memory_extraction_jobs
                SET status='obsolete', obsolete_reason=?, obsoleted_at=?, completed_at=?,
                    claim_token=NULL, claim_owner=NULL, next_attempt_at=NULL,
                    updated_at=datetime('now','localtime')
                WHERE id=? AND status IN ('queued','retry_wait','running','failed')
                """,
                (obsolete_reason, current, current, job_id),
            )
            return None
        if not generation or not _class_commentary_memory_extraction_integrity_valid(
            row,
            revision,
            generation,
        ):
            conn.execute(
                """
                UPDATE class_commentary_memory_extraction_jobs
                SET status='integrity_failed', last_error='frozen_input_integrity_mismatch',
                    completed_at=?, updated_at=datetime('now','localtime')
                WHERE id=? AND status IN ('queued','retry_wait')
                """,
                (current, job_id),
            )
            return None
        updated = conn.execute(
            """
            UPDATE class_commentary_memory_extraction_jobs
            SET status='running', attempt_count=attempt_count + 1,
                started_at=?, claim_token=?, claim_owner=?, rq_job_id=COALESCE(?, rq_job_id),
                next_attempt_at=NULL, last_error=NULL,
                updated_at=datetime('now','localtime')
            WHERE id=?
              AND attempt_count < 4
              AND (
                  status='queued'
                  OR (status='retry_wait' AND next_attempt_at<=?)
              )
            """,
            (current, claim_token, normalized_owner, rq_job_id, job_id, current),
        )
        if updated.rowcount != 1:
            return None
        claimed = conn.execute(
            "SELECT * FROM class_commentary_memory_extraction_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        return _serialize_class_commentary_memory_job(claimed)


def fail_class_commentary_memory_extraction_job(
    job_id: int,
    *,
    claim_token: str,
    error: str,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    current_dt = now or datetime.now(timezone.utc)
    current = _class_commentary_utc_timestamp(current_dt)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = conn.execute(
            "SELECT * FROM class_commentary_memory_extraction_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if not job:
            return None
        if str(job["status"]) != "running" or str(job["claim_token"] or "") != str(
            claim_token or ""
        ):
            return _serialize_class_commentary_memory_job(job)
        attempt_count = int(job["attempt_count"] or 0)
        if attempt_count >= 4:
            status = "failed"
            next_attempt_at = None
            completed_at = current
        else:
            status = "retry_wait"
            delay = (30, 120, 600)[max(0, attempt_count - 1)]
            next_attempt_at = _class_commentary_utc_timestamp(
                current_dt + timedelta(seconds=delay)
            )
            completed_at = None
        conn.execute(
            """
            UPDATE class_commentary_memory_extraction_jobs
            SET status=?, next_attempt_at=?, last_error=?, completed_at=?,
                updated_at=datetime('now','localtime')
            WHERE id=? AND status='running' AND claim_token=?
            """,
            (
                status,
                next_attempt_at,
                str(error or "")[:4000],
                completed_at,
                job_id,
                claim_token,
            ),
        )
        updated_job = conn.execute(
            "SELECT * FROM class_commentary_memory_extraction_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        return _serialize_class_commentary_memory_job(updated_job)


def mark_class_commentary_memory_extraction_integrity_failed(
    job_id: int,
    *,
    claim_token: str,
    error: str,
) -> Optional[dict]:
    completed_at = _class_commentary_utc_timestamp()
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_memory_extraction_jobs
            SET status='integrity_failed', last_error=?, completed_at=?,
                updated_at=datetime('now','localtime')
            WHERE id=? AND status='running' AND claim_token=?
            """,
            (str(error or "")[:4000], completed_at, job_id, claim_token),
        )
        row = conn.execute(
            "SELECT * FROM class_commentary_memory_extraction_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
    return _serialize_class_commentary_memory_job(row) if row else None


def _normalize_class_commentary_memory_item(
    item: dict,
    *,
    generation: sqlite3.Row,
    roster_ids: set[int],
) -> dict:
    memory_type = str(item.get("memory_type") or "").strip()
    if memory_type not in {"teacher_style", "student_fact"}:
        raise ValueError("unsupported class commentary memory type")
    memory_text = _class_commentary_safe_text(item.get("memory_text"), 2000)
    if not memory_text:
        raise ValueError("memory_text is required")
    normalized_memory_text = re.sub(r"\s+", " ", memory_text).strip().casefold()
    try:
        confidence = float(item.get("confidence", 0.5))
    except (TypeError, ValueError):
        raise ValueError("memory confidence must be numeric")
    confidence = max(0.0, min(1.0, confidence))
    if memory_type == "teacher_style":
        scope_skill_registry_id = int(generation["skill_registry_id"])
        student_id = None
        subject_key = None
        scope = {
            "organization_id": int(generation["organization_id"]),
            "memory_type": memory_type,
            "scope_skill_registry_id": scope_skill_registry_id,
        }
    else:
        try:
            student_id = int(item.get("student_id"))
        except (TypeError, ValueError):
            raise ValueError("student_fact requires student_id")
        if student_id not in roster_ids:
            raise ValueError("student_fact student_id is outside frozen roster")
        subject_key = str(generation["subject_key"] or "").strip()
        if not subject_key:
            raise ValueError("student_fact requires canonical subject_key")
        scope_skill_registry_id = None
        scope = {
            "organization_id": int(generation["organization_id"]),
            "memory_type": memory_type,
            "student_id": student_id,
            "subject_key": subject_key,
        }
    canonical_key = _class_commentary_content_hash(
        _class_commentary_canonical_json(
            {
                "normalization_version": CLASS_COMMENTARY_MEMORY_NORMALIZATION_VERSION,
                "normalized_memory_text": normalized_memory_text,
            }
        )
    )
    return {
        "memory_type": memory_type,
        "memory_text": memory_text,
        "normalized_memory_text": normalized_memory_text,
        "memory_text_hash": _class_commentary_content_hash(memory_text),
        "scope_skill_registry_id": scope_skill_registry_id,
        "student_id": student_id,
        "subject_key": subject_key,
        "scope_hash": _class_commentary_content_hash(_class_commentary_canonical_json(scope)),
        "canonical_key": canonical_key,
        "confidence": confidence,
        "extractor_evidence": item.get("evidence") if isinstance(item.get("evidence"), dict) else {},
    }


def commit_class_commentary_memory_extraction(
    job_id: int,
    *,
    claim_token: str,
    items: list[dict],
    result_summary: Optional[dict] = None,
) -> dict:
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    completed_at = _class_commentary_utc_timestamp()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = conn.execute(
            "SELECT * FROM class_commentary_memory_extraction_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if not job:
            raise ValueError("class commentary memory extraction job not found")
        if str(job["status"]) != "running" or str(job["claim_token"] or "") != str(
            claim_token or ""
        ):
            return {
                "job": _serialize_class_commentary_memory_job(job),
                "records": [],
                "evidence": [],
                "operations": [],
            }
        revision = conn.execute(
            "SELECT * FROM class_commentary_revisions WHERE id=?",
            (job["revision_id"],),
        ).fetchone()
        generation = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (revision["generation_id"],),
        ).fetchone()
        task = conn.execute(
            "SELECT * FROM class_commentary_tasks WHERE id=?",
            (revision["task_id"],),
        ).fetchone()
        if int(task["latest_revision_id"] or 0) != int(revision["id"]):
            conn.execute(
                """
                UPDATE class_commentary_memory_extraction_jobs
                SET status='obsolete', obsolete_reason='commit_gate_revision_not_effective',
                    obsoleted_by_revision_id=?, obsoleted_at=?, completed_at=?,
                    updated_at=datetime('now','localtime')
                WHERE id=? AND status='running' AND claim_token=?
                """,
                (
                    task["latest_revision_id"],
                    completed_at,
                    completed_at,
                    job_id,
                    claim_token,
                ),
            )
            obsolete = conn.execute(
                "SELECT * FROM class_commentary_memory_extraction_jobs WHERE id=?",
                (job_id,),
            ).fetchone()
            return {
                "job": _serialize_class_commentary_memory_job(obsolete),
                "records": [],
                "evidence": [],
                "operations": [],
            }
        scope_active, obsolete_reason = _class_commentary_memory_learning_scope_status_conn(
            conn,
            task,
            generation,
        )
        if not scope_active:
            conn.execute(
                """
                UPDATE class_commentary_memory_extraction_jobs
                SET status='obsolete', obsolete_reason=?, obsoleted_at=?, completed_at=?,
                    claim_token=NULL, claim_owner=NULL, next_attempt_at=NULL,
                    updated_at=datetime('now','localtime')
                WHERE id=? AND status='running' AND claim_token=?
                """,
                (
                    f"commit_gate_{obsolete_reason}",
                    completed_at,
                    completed_at,
                    job_id,
                    claim_token,
                ),
            )
            obsolete = conn.execute(
                "SELECT * FROM class_commentary_memory_extraction_jobs WHERE id=?",
                (job_id,),
            ).fetchone()
            return {
                "job": _serialize_class_commentary_memory_job(obsolete),
                "records": [],
                "evidence": [],
                "operations": [],
            }
        if not _class_commentary_memory_extraction_integrity_valid(
            job,
            revision,
            generation,
        ):
            conn.execute(
                """
                UPDATE class_commentary_memory_extraction_jobs
                SET status='integrity_failed', last_error='frozen_input_hash_mismatch',
                    completed_at=?, updated_at=datetime('now','localtime')
                WHERE id=? AND status='running' AND claim_token=?
                """,
                (completed_at, job_id, claim_token),
            )
            failed = conn.execute(
                "SELECT * FROM class_commentary_memory_extraction_jobs WHERE id=?",
                (job_id,),
            ).fetchone()
            return {
                "job": _serialize_class_commentary_memory_job(failed),
                "records": [],
                "evidence": [],
                "operations": [],
            }
        roster_snapshot = _class_commentary_json_list(
            generation["attending_roster_snapshot_json"]
        )
        roster_ids = {
            int(item["student_id"])
            for item in roster_snapshot
            if isinstance(item, dict) and item.get("student_id") is not None
        }
        roster_names = [
            str(item.get("student_name") or "").strip()
            for item in roster_snapshot
            if isinstance(item, dict) and str(item.get("student_name") or "").strip()
        ]
        normalized_items_by_key: dict[tuple[str, str, str], dict] = {}
        for raw_item in items:
            if not isinstance(raw_item, dict):
                continue
            raw_evidence = (
                raw_item.get("evidence")
                if isinstance(raw_item.get("evidence"), dict)
                else {}
            )
            raw_support = raw_evidence.get("support")
            validate_class_commentary_memory_privacy(
                memory_text=raw_item.get("memory_text"),
                support=raw_support if isinstance(raw_support, list) else [],
                roster_names=roster_names,
            )
            normalized_item = _normalize_class_commentary_memory_item(
                raw_item,
                generation=generation,
                roster_ids=roster_ids,
            )
            normalized_key = (
                normalized_item["memory_type"],
                normalized_item["scope_hash"],
                normalized_item["canonical_key"],
            )
            existing_item = normalized_items_by_key.get(normalized_key)
            if not existing_item or normalized_item["confidence"] > existing_item["confidence"]:
                normalized_items_by_key[normalized_key] = normalized_item
        normalized_items = list(normalized_items_by_key.values())
        record_rows = []
        evidence_rows = []
        operation_rows = []
        for item in normalized_items:
            record = conn.execute(
                """
                SELECT * FROM class_commentary_memory_records
                WHERE organization_id=? AND memory_type=?
                  AND scope_hash=? AND canonical_key=? AND desired_status='active'
                """,
                (
                    generation["organization_id"],
                    item["memory_type"],
                    item["scope_hash"],
                    item["canonical_key"],
                ),
            ).fetchone()
            record_created = False
            if not record:
                creation_snapshot = {
                    "revision_id": int(revision["id"]),
                    "extraction_job_id": int(job["id"]),
                    "extraction_input_hash": str(job["extraction_input_hash"]),
                    "learning_evidence_hash": str(job["learning_evidence_hash"]),
                    "extractor_evidence": item["extractor_evidence"],
                }
                cursor = conn.execute(
                    """
                    INSERT INTO class_commentary_memory_records (
                        organization_id, created_from_revision_id,
                        created_by_teacher_user_id, created_from_skill_registry_id,
                        scope_skill_registry_id, student_id, subject_key,
                        memory_type, memory_text, normalized_memory_text,
                        normalization_version, memory_text_hash, scope_hash,
                        canonical_key, creation_evidence_snapshot_json,
                        confidence, record_version, desired_status, applied_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'active', 'not_applied')
                    """,
                    (
                        generation["organization_id"],
                        revision["id"],
                        revision["teacher_user_id"],
                        generation["skill_registry_id"],
                        item["scope_skill_registry_id"],
                        item["student_id"],
                        item["subject_key"],
                        item["memory_type"],
                        item["memory_text"],
                        item["normalized_memory_text"],
                        CLASS_COMMENTARY_MEMORY_NORMALIZATION_VERSION,
                        item["memory_text_hash"],
                        item["scope_hash"],
                        item["canonical_key"],
                        _class_commentary_canonical_json(creation_snapshot),
                        item["confidence"],
                    ),
                )
                record = conn.execute(
                    "SELECT * FROM class_commentary_memory_records WHERE id=?",
                    (cursor.lastrowid,),
                ).fetchone()
                record_created = True
            evidence_hash = _class_commentary_content_hash(
                _class_commentary_canonical_json(
                    {
                        "revision_id": int(revision["id"]),
                        "extraction_job_id": int(job["id"]),
                        "memory_record_id": int(record["id"]),
                        "memory_text_hash": item["memory_text_hash"],
                        "extractor_evidence": item["extractor_evidence"],
                    }
                )
            )
            evidence_insert = conn.execute(
                """
                INSERT INTO class_commentary_memory_evidence (
                    organization_id, memory_record_id, revision_id,
                    extraction_job_id, source_teacher_user_id,
                    source_skill_registry_id, evidence_hash, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                ON CONFLICT(memory_record_id, revision_id, evidence_hash) DO NOTHING
                """,
                (
                    generation["organization_id"],
                    record["id"],
                    revision["id"],
                    job["id"],
                    revision["teacher_user_id"],
                    generation["skill_registry_id"],
                    evidence_hash,
                ),
            )
            evidence = conn.execute(
                """
                SELECT * FROM class_commentary_memory_evidence
                WHERE memory_record_id=? AND revision_id=? AND evidence_hash=?
                """,
                (record["id"], revision["id"], evidence_hash),
            ).fetchone()
            if record_created:
                operation = _create_class_commentary_memory_operation_conn(
                    conn,
                    record,
                    operation_type="add",
                    source_type="revision",
                    source_id=int(revision["id"]),
                    extraction_job_id=int(job["id"]),
                    extractor_version=str(job["extractor_version"]),
                    memory_schema_version=str(job["memory_schema_version"]),
                )
                operation_rows.append(operation)
            elif evidence_insert.rowcount == 1:
                operation = _advance_class_commentary_memory_record_projection_conn(
                    conn,
                    int(record["id"]),
                    desired_status=None,
                    operation_type="update",
                    source_type="revision",
                    source_id=int(revision["id"]),
                    extraction_job_id=int(job["id"]),
                    extractor_version=str(job["extractor_version"]),
                    memory_schema_version=str(job["memory_schema_version"]),
                )
                operation_rows.append(operation)
                record = conn.execute(
                    "SELECT * FROM class_commentary_memory_records WHERE id=?",
                    (record["id"],),
                ).fetchone()
            record_rows.append(record)
            evidence_rows.append(evidence)
        summary = dict(result_summary or {})
        summary.update(
            {
                "item_count": len(normalized_items),
                "record_ids": sorted({int(row["id"]) for row in record_rows}),
                "evidence_ids": [int(row["id"]) for row in evidence_rows],
                "operation_ids": [int(row["id"]) for row in operation_rows],
            }
        )
        updated = conn.execute(
            """
            UPDATE class_commentary_memory_extraction_jobs
            SET status='extracted', result_summary_json=?, completed_at=?,
                updated_at=datetime('now','localtime')
            WHERE id=? AND status='running' AND claim_token=?
            """,
            (
                _class_commentary_canonical_json(summary),
                completed_at,
                job_id,
                claim_token,
            ),
        )
        if updated.rowcount != 1:
            raise ClassCommentaryConfirmationRequestConflict(
                "memory extraction claim changed during commit"
            )
        completed_job = conn.execute(
            "SELECT * FROM class_commentary_memory_extraction_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        return {
            "job": _serialize_class_commentary_memory_job(completed_job),
            "records": [_serialize_class_commentary_memory_record(row) for row in record_rows],
            "evidence": [dict(row) for row in evidence_rows],
            "operations": [
                _serialize_class_commentary_memory_operation(row) for row in operation_rows
            ],
        }


def get_class_commentary_memory_extraction_input(job_id: int) -> Optional[dict]:
    with get_conn() as conn:
        job = conn.execute(
            "SELECT * FROM class_commentary_memory_extraction_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if not job:
            return None
        revision = conn.execute(
            "SELECT * FROM class_commentary_revisions WHERE id=?",
            (job["revision_id"],),
        ).fetchone()
        generation = conn.execute(
            "SELECT * FROM class_commentary_generations WHERE id=?",
            (revision["generation_id"],),
        ).fetchone()
        task = conn.execute(
            "SELECT latest_revision_id FROM class_commentary_tasks WHERE id=?",
            (revision["task_id"],),
        ).fetchone()
    integrity_valid = bool(
        generation
        and _class_commentary_memory_extraction_integrity_valid(
            job,
            revision,
            generation,
        )
    )
    extraction_input = {
        "generation_id": int(generation["id"]),
        "revision_id": int(revision["id"]),
        "generated_feedback_text": str(generation["generated_feedback_text"] or ""),
        "final_feedback_text": str(revision["final_feedback_text"] or ""),
        "generation_diff": _class_commentary_json_dict(revision["generation_diff_json"]),
        "previous_revision_diff": (
            _class_commentary_json_dict(revision["previous_revision_diff_json"])
            if revision["previous_revision_diff_json"]
            else None
        ),
        "skill_snapshot": {
            "skill_registry_id": int(generation["skill_registry_id"]),
            "skill_version_id": int(generation["skill_version_id"]),
            "skill_id": str(generation["skill_id"] or ""),
            "content": str(generation["skill_content_snapshot"] or ""),
            "content_hash": str(generation["skill_content_hash"] or ""),
        },
        "attending_roster": _class_commentary_json_list(
            generation["attending_roster_snapshot_json"]
        ),
        "transcript": str(generation["confirmed_transcript_snapshot"] or ""),
        "subject_key": str(generation["subject_key"] or ""),
        "learning_evidence_snapshot": _class_commentary_json_dict(
            revision["learning_evidence_snapshot_json"]
        ),
        "learning_evidence_source_refs": _class_commentary_json_list(
            revision["learning_evidence_source_refs_json"]
        ),
    }
    return {
        "job": _serialize_class_commentary_memory_job(job),
        "extraction_input_hash": str(job["extraction_input_hash"] or ""),
        "learning_evidence_hash": str(job["learning_evidence_hash"] or ""),
        "revision": _serialize_class_commentary_revision_row(revision),
        "generation": _serialize_class_commentary_generation_row(generation),
        "extraction_input": extraction_input,
        **extraction_input,
        "is_effective_revision": int(task["latest_revision_id"] or 0)
        == int(revision["id"]),
        "integrity_valid": integrity_valid,
    }


def get_class_commentary_memory_operation(operation_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM class_commentary_memory_operations WHERE id=?",
            (operation_id,),
        ).fetchone()
    return _serialize_class_commentary_memory_operation(row) if row else None


def list_dispatchable_class_commentary_memory_operations(
    *,
    limit: int = 100,
    now: Optional[str] = None,
) -> list[dict]:
    current = now or _class_commentary_utc_timestamp()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT operation.*
            FROM class_commentary_memory_operations AS operation
            JOIN class_commentary_memory_records AS record
              ON record.id=operation.memory_record_id
            WHERE operation.expected_record_version=record.record_version
              AND operation.attempt_count < 8
              AND NOT EXISTS (
                  SELECT 1
                  FROM class_commentary_memory_operations AS running_operation
                  WHERE running_operation.memory_record_id=operation.memory_record_id
                    AND running_operation.status='running'
              )
              AND (
                  operation.status='pending'
                  OR (
                      operation.status IN ('retry_wait','reconcile_needed')
                      AND operation.next_attempt_at<=?
                  )
              )
            ORDER BY operation.created_at, operation.id
            LIMIT ?
            """,
            (current, max(1, min(int(limit), 500))),
        ).fetchall()
    return [_serialize_class_commentary_memory_operation(row) for row in rows]


def mark_class_commentary_memory_operation_enqueued(
    operation_id: int,
    rq_job_id: str,
) -> Optional[dict]:
    normalized_rq_job_id = str(rq_job_id or "").strip()
    if not normalized_rq_job_id:
        raise ValueError("rq_job_id is required")
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_memory_operations
            SET rq_job_id=?, enqueued_at=?, updated_at=datetime('now','localtime')
            WHERE id=? AND status IN ('pending','retry_wait','reconcile_needed')
            """,
            (normalized_rq_job_id, _class_commentary_utc_timestamp(), operation_id),
        )
        row = conn.execute(
            "SELECT * FROM class_commentary_memory_operations WHERE id=?",
            (operation_id,),
        ).fetchone()
    return _serialize_class_commentary_memory_operation(row) if row else None


def claim_class_commentary_memory_operation(
    operation_id: int,
    *,
    lease_owner: str,
    rq_job_id: Optional[str] = None,
    lease_seconds: int = 240,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    normalized_owner = str(lease_owner or "").strip()
    if not normalized_owner:
        raise ValueError("lease_owner is required")
    current_dt = now or datetime.now(timezone.utc)
    current = _class_commentary_utc_timestamp(current_dt)
    lease_until = _class_commentary_utc_timestamp(
        current_dt + timedelta(seconds=max(1, int(lease_seconds)))
    )
    lease_token = secrets.token_hex(24)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT operation.*, record.record_version AS current_record_version
            FROM class_commentary_memory_operations AS operation
            JOIN class_commentary_memory_records AS record
              ON record.id=operation.memory_record_id
            WHERE operation.id=?
            """,
            (operation_id,),
        ).fetchone()
        if not row:
            return None
        running_operation = conn.execute(
            """
            SELECT 1
            FROM class_commentary_memory_operations
            WHERE memory_record_id=? AND status='running' AND id<>?
            LIMIT 1
            """,
            (row["memory_record_id"], operation_id),
        ).fetchone()
        if running_operation:
            return None
        if int(row["expected_record_version"]) != int(row["current_record_version"]):
            conn.execute(
                """
                UPDATE class_commentary_memory_operations
                SET status='obsolete', last_error='record_version_mismatch',
                    updated_at=datetime('now','localtime')
                WHERE id=? AND status IN ('pending','retry_wait','reconcile_needed')
                """,
                (operation_id,),
            )
            return None
        target_state_json = str(row["target_state_json"] or "")
        if _class_commentary_content_hash(target_state_json) != str(row["target_state_hash"]):
            conn.execute(
                """
                UPDATE class_commentary_memory_operations
                SET status='failed', last_error='target_state_hash_mismatch',
                    updated_at=datetime('now','localtime')
                WHERE id=? AND status IN ('pending','retry_wait','reconcile_needed')
                """,
                (operation_id,),
            )
            return None
        updated = conn.execute(
            """
            UPDATE class_commentary_memory_operations
            SET status='running', attempt_count=attempt_count + 1,
                started_at=?, lease_token=?, lease_owner=?, lease_until=?,
                rq_job_id=COALESCE(?, rq_job_id), next_attempt_at=NULL,
                last_error=NULL, updated_at=datetime('now','localtime')
            WHERE id=?
              AND attempt_count < 8
              AND (
                  status='pending'
                  OR (
                      status IN ('retry_wait','reconcile_needed')
                      AND next_attempt_at<=?
                  )
              )
            """,
            (
                current,
                lease_token,
                normalized_owner,
                lease_until,
                rq_job_id,
                operation_id,
                current,
            ),
        )
        if updated.rowcount != 1:
            return None
        claimed = conn.execute(
            "SELECT * FROM class_commentary_memory_operations WHERE id=?",
            (operation_id,),
        ).fetchone()
        return _serialize_class_commentary_memory_operation(claimed)


def _record_stale_class_commentary_memory_external_apply_conn(
    conn: sqlite3.Connection,
    operation: sqlite3.Row,
    record: sqlite3.Row,
    *,
    lease_token: str,
    mem0_memory_id: str,
    applied_at: str,
    reason: str,
) -> sqlite3.Row:
    conn.execute(
        """
        UPDATE class_commentary_memory_operations
        SET status='obsolete', last_error=?,
            mem0_memory_id=COALESCE(NULLIF(?, ''), mem0_memory_id),
            applied_at=?, lease_token=NULL, lease_owner=NULL, lease_until=NULL,
            next_attempt_at=NULL, updated_at=datetime('now','localtime')
        WHERE id=? AND status='running' AND lease_token=?
        """,
        (
            reason,
            mem0_memory_id,
            applied_at,
            operation["id"],
            lease_token,
        ),
    )
    conn.execute(
        """
        UPDATE class_commentary_memory_records
        SET applied_status='unknown',
            mem0_memory_id=COALESCE(NULLIF(?, ''), mem0_memory_id),
            updated_at=datetime('now','localtime')
        WHERE id=? AND record_version=?
        """,
        (mem0_memory_id, record["id"], record["record_version"]),
    )
    current_operation = conn.execute(
        """
        SELECT * FROM class_commentary_memory_operations
        WHERE memory_record_id=? AND operation_version=?
        """,
        (record["id"], record["record_version"]),
    ).fetchone()
    if not current_operation:
        current_record = conn.execute(
            "SELECT * FROM class_commentary_memory_records WHERE id=?",
            (record["id"],),
        ).fetchone()
        operation_type = {
            "active": "update" if current_record["mem0_memory_id"] else "add",
            "superseded": "supersede",
            "revoked": "revoke",
            "deleted": "delete",
        }[str(current_record["desired_status"])]
        current_operation = _create_class_commentary_memory_operation_conn(
            conn,
            current_record,
            operation_type=operation_type,
            source_type="reconciliation",
            source_id=None,
        )
    if str(current_operation["status"]) != "running":
        conn.execute(
            """
            UPDATE class_commentary_memory_operations
            SET status='reconcile_needed', next_attempt_at=?,
                attempt_count=CASE WHEN status='failed' THEN 0 ELSE attempt_count END,
                mem0_memory_id=COALESCE(NULLIF(?, ''), mem0_memory_id),
                last_error='stale_external_apply_requires_reconciliation',
                lease_token=NULL, lease_owner=NULL, lease_until=NULL,
                updated_at=datetime('now','localtime')
            WHERE id=? AND status<>'running'
            """,
            (applied_at, mem0_memory_id, current_operation["id"]),
        )
    stale = conn.execute(
        "SELECT * FROM class_commentary_memory_operations WHERE id=?",
        (operation["id"],),
    ).fetchone()
    return stale


def complete_class_commentary_memory_operation(
    operation_id: int,
    *,
    lease_token: str,
    mem0_memory_id: Optional[str] = None,
    applied_status: Optional[str] = None,
    projection_metadata: Optional[dict] = None,
) -> Optional[dict]:
    applied_at = _class_commentary_utc_timestamp()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        operation = conn.execute(
            "SELECT * FROM class_commentary_memory_operations WHERE id=?",
            (operation_id,),
        ).fetchone()
        if not operation:
            return None
        if str(operation["status"]) != "running" or str(operation["lease_token"] or "") != str(
            lease_token or ""
        ):
            return _serialize_class_commentary_memory_operation(operation)
        record = conn.execute(
            "SELECT * FROM class_commentary_memory_records WHERE id=?",
            (operation["memory_record_id"],),
        ).fetchone()
        target = _class_commentary_json_dict(operation["target_state_json"])
        normalized_applied_status = str(
            applied_status or target.get("desired_status") or "unknown"
        )
        if normalized_applied_status not in {
            "active",
            "superseded",
            "revoked",
            "deleted",
            "unknown",
        }:
            raise ValueError("unsupported class commentary memory applied status")
        normalized_mem0_id = (
            str(mem0_memory_id).strip()
            if mem0_memory_id is not None
            else str(operation["mem0_memory_id"] or record["mem0_memory_id"] or "").strip()
        )
        if int(record["record_version"]) != int(operation["expected_record_version"]):
            stale = _record_stale_class_commentary_memory_external_apply_conn(
                conn,
                operation,
                record,
                lease_token=lease_token,
                mem0_memory_id=normalized_mem0_id,
                applied_at=applied_at,
                reason="record_version_mismatch_after_external_apply",
            )
            return _serialize_class_commentary_memory_operation(stale)
        conn.execute(
            """
            UPDATE class_commentary_memory_records
            SET applied_status=?, mem0_memory_id=NULLIF(?, ''),
                updated_at=datetime('now','localtime')
            WHERE id=? AND record_version=?
            """,
            (
                normalized_applied_status,
                normalized_mem0_id,
                record["id"],
                operation["expected_record_version"],
            ),
        )
        updated = conn.execute(
            """
            UPDATE class_commentary_memory_operations
            SET status='applied', mem0_memory_id=NULLIF(?, ''), applied_at=?,
                lease_until=NULL, updated_at=datetime('now','localtime')
            WHERE id=? AND status='running' AND lease_token=?
              AND expected_record_version=?
            """,
            (
                normalized_mem0_id,
                applied_at,
                operation_id,
                lease_token,
                record["record_version"],
            ),
        )
        if updated.rowcount != 1:
            raise ClassCommentaryConfirmationRequestConflict(
                "memory operation lease changed during completion"
            )
        completed = conn.execute(
            "SELECT * FROM class_commentary_memory_operations WHERE id=?",
            (operation_id,),
        ).fetchone()
        return _serialize_class_commentary_memory_operation(completed)


def fail_class_commentary_memory_operation(
    operation_id: int,
    *,
    lease_token: str,
    error: str,
    mem0_succeeded: bool = False,
    mem0_memory_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    current_dt = now or datetime.now(timezone.utc)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        operation = conn.execute(
            "SELECT * FROM class_commentary_memory_operations WHERE id=?",
            (operation_id,),
        ).fetchone()
        if not operation:
            return None
        if str(operation["status"]) != "running" or str(operation["lease_token"] or "") != str(
            lease_token or ""
        ):
            return _serialize_class_commentary_memory_operation(operation)
        record = conn.execute(
            "SELECT * FROM class_commentary_memory_records WHERE id=?",
            (operation["memory_record_id"],),
        ).fetchone()
        normalized_mem0_id = str(mem0_memory_id or operation["mem0_memory_id"] or "").strip()
        if int(record["record_version"]) != int(operation["expected_record_version"]):
            if mem0_succeeded:
                stale = _record_stale_class_commentary_memory_external_apply_conn(
                    conn,
                    operation,
                    record,
                    lease_token=lease_token,
                    mem0_memory_id=normalized_mem0_id,
                    applied_at=_class_commentary_utc_timestamp(current_dt),
                    reason="record_version_mismatch_after_external_apply_failure",
                )
            else:
                conn.execute(
                    """
                    UPDATE class_commentary_memory_operations
                    SET status='obsolete', last_error='record_version_mismatch_after_failure',
                        lease_token=NULL, lease_owner=NULL, lease_until=NULL,
                        next_attempt_at=NULL, updated_at=datetime('now','localtime')
                    WHERE id=? AND status='running' AND lease_token=?
                    """,
                    (operation_id, lease_token),
                )
                stale = conn.execute(
                    "SELECT * FROM class_commentary_memory_operations WHERE id=?",
                    (operation_id,),
                ).fetchone()
            return _serialize_class_commentary_memory_operation(stale)
        attempt_count = int(operation["attempt_count"] or 0)
        if mem0_succeeded:
            status = "reconcile_needed"
            next_attempt_at = _class_commentary_utc_timestamp(current_dt)
        elif attempt_count >= 8:
            status = "failed"
            next_attempt_at = None
        elif attempt_count <= 3:
            status = "retry_wait"
            delay = (30, 120, 600)[attempt_count - 1]
            next_attempt_at = _class_commentary_utc_timestamp(
                current_dt + timedelta(seconds=delay)
            )
        else:
            status = "reconcile_needed"
            delay = (3600, 7200, 14400, 21600)[attempt_count - 4]
            next_attempt_at = _class_commentary_utc_timestamp(
                current_dt + timedelta(seconds=delay)
            )
        conn.execute(
            """
            UPDATE class_commentary_memory_operations
            SET status=?, next_attempt_at=?, last_error=?, lease_until=NULL,
                mem0_memory_id=COALESCE(NULLIF(?, ''), mem0_memory_id),
                updated_at=datetime('now','localtime')
            WHERE id=? AND status='running' AND lease_token=?
            """,
            (
                status,
                next_attempt_at,
                str(error or "")[:4000],
                str(mem0_memory_id or "").strip(),
                operation_id,
                lease_token,
            ),
        )
        failed = conn.execute(
            "SELECT * FROM class_commentary_memory_operations WHERE id=?",
            (operation_id,),
        ).fetchone()
        return _serialize_class_commentary_memory_operation(failed)


def get_class_commentary_memory_records_by_ids(
    record_ids: list[int],
    organization_id: Optional[int] = None,
) -> list[dict]:
    normalized_ids = sorted({int(record_id) for record_id in record_ids})
    if not normalized_ids:
        return []
    placeholders = ",".join("?" for _ in normalized_ids)
    with get_conn() as conn:
        organization_filter = "AND record.organization_id=?" if organization_id is not None else ""
        params: list[object] = [*normalized_ids]
        if organization_id is not None:
            params.append(int(organization_id))
        rows = conn.execute(
            f"""
            SELECT record.*,
                   (
                       SELECT COUNT(*)
                       FROM class_commentary_memory_evidence AS evidence
                       WHERE evidence.memory_record_id=record.id
                         AND evidence.status='active'
                   ) AS active_evidence_count
            FROM class_commentary_memory_records AS record
            WHERE record.id IN ({placeholders}) {organization_filter}
            ORDER BY record.id
            """,
            params,
        ).fetchall()
        evidence_rows = conn.execute(
            f"""
            SELECT evidence.id, evidence.memory_record_id, evidence.revision_id,
                   evidence.evidence_hash, evidence.created_at
            FROM class_commentary_memory_evidence AS evidence
            JOIN class_commentary_memory_records AS record
              ON record.id=evidence.memory_record_id
            WHERE evidence.memory_record_id IN ({placeholders})
              AND evidence.status='active' {organization_filter}
            ORDER BY evidence.memory_record_id, evidence.created_at, evidence.id
            """,
            params,
        ).fetchall()
    evidence_by_record: dict[int, list[dict]] = {}
    for evidence in evidence_rows:
        evidence_by_record.setdefault(int(evidence["memory_record_id"]), []).append(
            {
                "evidence_id": int(evidence["id"]),
                "revision_id": int(evidence["revision_id"]),
                "evidence_hash": str(evidence["evidence_hash"]),
                "created_at": str(evidence["created_at"] or ""),
            }
        )
    records = []
    for row in rows:
        item = _serialize_class_commentary_memory_record(row)
        item["active_evidence"] = evidence_by_record.get(int(item["id"]), [])
        records.append(item)
    return records


def mark_class_commentary_memory_records_reconcile_needed(
    record_ids: list[int],
    reason: str,
    *,
    organization_id: int,
) -> list[dict]:
    normalized_ids = sorted({int(record_id) for record_id in record_ids})
    if not normalized_ids:
        return []
    current = _class_commentary_utc_timestamp()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for record_id in normalized_ids:
            record = conn.execute(
                """
                SELECT * FROM class_commentary_memory_records
                WHERE id=? AND organization_id=?
                """,
                (record_id, int(organization_id)),
            ).fetchone()
            if not record:
                continue
            operation = conn.execute(
                """
                SELECT * FROM class_commentary_memory_operations
                WHERE organization_id=? AND memory_record_id=? AND operation_version=?
                """,
                (int(organization_id), record_id, record["record_version"]),
            ).fetchone()
            if not operation:
                operation_type = {
                    "active": "update" if record["mem0_memory_id"] else "add",
                    "superseded": "supersede",
                    "revoked": "revoke",
                    "deleted": "delete",
                }[str(record["desired_status"])]
                operation = _create_class_commentary_memory_operation_conn(
                    conn,
                    record,
                    operation_type=operation_type,
                    source_type="reconciliation",
                    source_id=None,
                )
            conn.execute(
                """
                UPDATE class_commentary_memory_operations
                SET status='reconcile_needed', next_attempt_at=?, last_error=?,
                    updated_at=datetime('now','localtime')
                WHERE id=? AND status NOT IN ('running','obsolete')
                """,
                (current, str(reason or "reconciliation_requested")[:4000], operation["id"]),
            )
        placeholders = ",".join("?" for _ in normalized_ids)
        rows = conn.execute(
            f"""
            SELECT * FROM class_commentary_memory_operations
            WHERE organization_id=?
              AND memory_record_id IN ({placeholders})
              AND status='reconcile_needed'
            ORDER BY id
            """,
            (int(organization_id), *normalized_ids),
        ).fetchall()
    return [_serialize_class_commentary_memory_operation(row) for row in rows]


def list_class_commentary_memory_records_for_scope(
    *,
    organization_id: int,
    memory_type: Optional[str] = None,
    skill_registry_id: Optional[int] = None,
    student_ids: Optional[list[int]] = None,
    subject_key: Optional[str] = None,
    desired_status: str = "active",
    limit: int = 100,
) -> list[dict]:
    conditions = ["record.organization_id=?", "record.desired_status=?"]
    params: list[object] = [int(organization_id), str(desired_status)]
    if memory_type:
        conditions.append("record.memory_type=?")
        params.append(str(memory_type))
    if skill_registry_id is not None:
        conditions.append("record.scope_skill_registry_id=?")
        params.append(int(skill_registry_id))
    normalized_student_ids = sorted({int(value) for value in (student_ids or [])})
    if student_ids is not None:
        if not normalized_student_ids:
            return []
        placeholders = ",".join("?" for _ in normalized_student_ids)
        conditions.append(f"record.student_id IN ({placeholders})")
        params.extend(normalized_student_ids)
    if subject_key is not None:
        conditions.append("record.subject_key=?")
        params.append(str(subject_key))
    if desired_status == "active":
        conditions.append(
            "EXISTS (SELECT 1 FROM class_commentary_memory_evidence AS active_evidence "
            "WHERE active_evidence.memory_record_id=record.id "
            "AND active_evidence.status='active')"
        )
    params.append(max(1, min(int(limit), 500)))
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT record.*,
                   (
                       SELECT COUNT(*)
                       FROM class_commentary_memory_evidence AS evidence
                       WHERE evidence.memory_record_id=record.id
                         AND evidence.status='active'
                   ) AS active_evidence_count
            FROM class_commentary_memory_records AS record
            WHERE {' AND '.join(conditions)}
            ORDER BY record.updated_at DESC, record.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [_serialize_class_commentary_memory_record(row) for row in rows]


def list_class_commentary_revision_memories(
    revision_id: int,
    actor_user_id: Optional[int] = None,
) -> dict:
    with get_conn() as conn:
        revision = conn.execute(
            "SELECT * FROM class_commentary_revisions WHERE id=?",
            (revision_id,),
        ).fetchone()
        if not revision:
            raise ValueError("class commentary revision not found")
        if actor_user_id is not None and int(revision["teacher_user_id"]) != int(actor_user_id):
            raise ValueError("class commentary revision is not owned by actor")
        job = conn.execute(
            """
            SELECT * FROM class_commentary_memory_extraction_jobs
            WHERE revision_id=?
            ORDER BY id DESC LIMIT 1
            """,
            (revision_id,),
        ).fetchone()
        rows = conn.execute(
            """
            SELECT evidence.*, record.memory_type, record.memory_text,
                   record.student_id, record.subject_key,
                   record.scope_skill_registry_id, record.desired_status,
                   record.applied_status, record.record_version,
                   record.mem0_memory_id, record.confidence,
                   (
                       SELECT COUNT(*)
                       FROM class_commentary_memory_evidence AS active_evidence
                       WHERE active_evidence.memory_record_id=record.id
                         AND active_evidence.status='active'
                   ) AS active_evidence_count,
                   operation.id AS latest_operation_id,
                   operation.status AS latest_operation_status,
                   operation.last_error AS latest_operation_error
            FROM class_commentary_memory_evidence AS evidence
            JOIN class_commentary_memory_records AS record
              ON record.id=evidence.memory_record_id
            LEFT JOIN class_commentary_memory_operations AS operation
              ON operation.id=(
                  SELECT candidate.id
                  FROM class_commentary_memory_operations AS candidate
                  WHERE candidate.memory_record_id=record.id
                  ORDER BY candidate.operation_version DESC, candidate.id DESC
                  LIMIT 1
              )
            WHERE evidence.revision_id=?
            ORDER BY evidence.id
            """,
            (revision_id,),
        ).fetchall()
    return {
        "revision_id": int(revision_id),
        "learn_requested": bool(revision["learn_requested"]),
        "job": _serialize_class_commentary_memory_job(job) if job else None,
        "memories": [dict(row) for row in rows],
    }


def get_class_commentary_memory_evidence(evidence_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT evidence.*, revision.task_id, revision.generation_id,
                   revision.teacher_user_id, revision.learn_requested
            FROM class_commentary_memory_evidence AS evidence
            JOIN class_commentary_revisions AS revision
              ON revision.id=evidence.revision_id
            WHERE evidence.id=?
            """,
            (evidence_id,),
        ).fetchone()
    return dict(row) if row else None


def revoke_class_commentary_memory_evidence(
    evidence_id: int,
    *,
    actor_user_id: int,
    request_id: str,
) -> dict:
    normalized_request_id = str(request_id or "").strip()
    if not normalized_request_id:
        raise ValueError("request_id is required")
    payload_hash = _class_commentary_content_hash(
        _class_commentary_canonical_json(
            {"action": "revoke", "evidence_id": int(evidence_id)}
        )
    )
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        evidence = conn.execute(
            "SELECT * FROM class_commentary_memory_evidence WHERE id=?",
            (evidence_id,),
        ).fetchone()
        if not evidence:
            raise ValueError("class commentary memory evidence not found")
        if int(evidence["source_teacher_user_id"]) != int(actor_user_id):
            raise ClassCommentaryMemoryEvidenceNotRevocable()
        existing = conn.execute(
            """
            SELECT * FROM class_commentary_memory_evidence_events
            WHERE evidence_id=? AND request_id=?
            """,
            (evidence_id, normalized_request_id),
        ).fetchone()
        if existing:
            if str(existing["payload_hash"]) != payload_hash:
                raise ClassCommentaryMemoryEvidenceRequestConflict(
                    "memory evidence request_id was used with another payload"
                )
            operation = conn.execute(
                """
                SELECT * FROM class_commentary_memory_operations
                WHERE source_type='evidence_event' AND source_id=?
                ORDER BY id DESC LIMIT 1
                """,
                (existing["id"],),
            ).fetchone()
            record = conn.execute(
                "SELECT * FROM class_commentary_memory_records WHERE id=?",
                (evidence["memory_record_id"],),
            ).fetchone()
            return {
                "event": dict(existing),
                "evidence": dict(evidence),
                "record": _serialize_class_commentary_memory_record(record),
                "operation": (
                    _serialize_class_commentary_memory_operation(operation)
                    if operation
                    else None
                ),
            }
        if str(evidence["status"]) != "active":
            raise ClassCommentaryMemoryEvidenceNotRevocable()
        cursor = conn.execute(
            """
            INSERT INTO class_commentary_memory_evidence_events (
                organization_id, evidence_id, action, request_id,
                payload_hash, actor_user_id
            )
            VALUES (?, ?, 'revoke', ?, ?, ?)
            """,
            (
                evidence["organization_id"],
                evidence_id,
                normalized_request_id,
                payload_hash,
                actor_user_id,
            ),
        )
        event_id = int(cursor.lastrowid)
        conn.execute(
            """
            UPDATE class_commentary_memory_evidence
            SET status='revoked', updated_at=datetime('now','localtime')
            WHERE id=? AND status='active'
            """,
            (evidence_id,),
        )
        active_count = conn.execute(
            """
            SELECT COUNT(*) AS value
            FROM class_commentary_memory_evidence
            WHERE memory_record_id=? AND status='active'
            """,
            (evidence["memory_record_id"],),
        ).fetchone()["value"]
        operation = None
        if int(active_count or 0) == 0:
            record = conn.execute(
                """
                SELECT * FROM class_commentary_memory_records
                WHERE id=? AND desired_status='active'
                """,
                (evidence["memory_record_id"],),
            ).fetchone()
            if record:
                operation = _advance_class_commentary_memory_record_projection_conn(
                    conn,
                    int(record["id"]),
                    desired_status="revoked",
                    operation_type="revoke",
                    source_type="evidence_event",
                    source_id=event_id,
                )
        else:
            operation = _advance_class_commentary_memory_record_projection_conn(
                conn,
                int(evidence["memory_record_id"]),
                desired_status=None,
                operation_type="update",
                source_type="evidence_event",
                source_id=event_id,
            )
        event = conn.execute(
            "SELECT * FROM class_commentary_memory_evidence_events WHERE id=?",
            (event_id,),
        ).fetchone()
        updated_evidence = conn.execute(
            "SELECT * FROM class_commentary_memory_evidence WHERE id=?",
            (evidence_id,),
        ).fetchone()
        record = conn.execute(
            "SELECT * FROM class_commentary_memory_records WHERE id=?",
            (evidence["memory_record_id"],),
        ).fetchone()
        return {
            "event": dict(event),
            "evidence": dict(updated_evidence),
            "record": _serialize_class_commentary_memory_record(record),
            "operation": (
                _serialize_class_commentary_memory_operation(operation)
                if operation
                else None
            ),
        }


def retry_class_commentary_memory_revision(
    revision_id: int,
    *,
    actor_user_id: int,
    request_id: str,
) -> dict:
    normalized_request_id = str(request_id or "").strip()
    if not normalized_request_id:
        raise ValueError("request_id is required")
    payload_hash = _class_commentary_content_hash(
        _class_commentary_canonical_json(
            {"action": "memory_retry", "revision_id": int(revision_id)}
        )
    )
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        revision = conn.execute(
            "SELECT * FROM class_commentary_revisions WHERE id=?",
            (revision_id,),
        ).fetchone()
        if not revision:
            raise ValueError("class commentary revision not found")
        existing = conn.execute(
            """
            SELECT * FROM class_commentary_memory_retry_events
            WHERE organization_id=? AND scope_type='revision'
              AND scope_id=? AND request_id=?
            """,
            (revision["organization_id"], revision_id, normalized_request_id),
        ).fetchone()
        if existing:
            if str(existing["payload_hash"]) != payload_hash:
                raise ClassCommentaryMemoryRetryRequestConflict(
                    "memory retry request_id was used with another payload"
                )
            return dict(existing)
        task = conn.execute(
            "SELECT * FROM class_commentary_tasks WHERE id=?",
            (revision["task_id"],),
        ).fetchone()
        if (
            int(revision["teacher_user_id"]) != int(actor_user_id)
            or int(task["latest_revision_id"] or 0) != int(revision_id)
            or not bool(revision["learn_requested"])
        ):
            raise ClassCommentaryMemoryRevisionNotRetryable()
        job = conn.execute(
            """
            SELECT * FROM class_commentary_memory_extraction_jobs
            WHERE revision_id=? ORDER BY id DESC LIMIT 1
            """,
            (revision_id,),
        ).fetchone()
        retry_job = job if job and str(job["status"]) == "failed" else None
        operation_rows = conn.execute(
            """
            SELECT DISTINCT operation.*
            FROM class_commentary_memory_operations AS operation
            LEFT JOIN class_commentary_memory_evidence AS evidence
              ON evidence.memory_record_id=operation.memory_record_id
            WHERE operation.organization_id=?
              AND operation.status='failed'
              AND (
                  (operation.source_type='revision' AND operation.source_id=?)
                  OR evidence.revision_id=?
              )
            ORDER BY operation.id
            """,
            (revision["organization_id"], revision_id, revision_id),
        ).fetchall()
        if not retry_job and not operation_rows:
            raise ClassCommentaryMemoryRevisionNotRetryable()
        previous_state = {
            "extraction_job": dict(retry_job) if retry_job else None,
            "operations": [dict(row) for row in operation_rows],
        }
        target_operation_ids = [int(row["id"]) for row in operation_rows]
        cursor = conn.execute(
            """
            INSERT INTO class_commentary_memory_retry_events (
                organization_id, scope_type, scope_id, revision_id,
                request_id, payload_hash, actor_user_id,
                extraction_job_id, target_operation_ids_json,
                previous_state_snapshot_json
            )
            VALUES (?, 'revision', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                revision["organization_id"],
                revision_id,
                revision_id,
                normalized_request_id,
                payload_hash,
                actor_user_id,
                retry_job["id"] if retry_job else None,
                _class_commentary_canonical_json(target_operation_ids),
                _class_commentary_canonical_json(previous_state),
            ),
        )
        if retry_job:
            conn.execute(
                """
                UPDATE class_commentary_memory_extraction_jobs
                SET status='queued', attempt_count=0, started_at=NULL,
                    claim_token=NULL, claim_owner=NULL, rq_job_id=NULL,
                    enqueued_at=NULL, next_attempt_at=NULL, last_error=NULL,
                    completed_at=NULL, updated_at=datetime('now','localtime')
                WHERE id=? AND status='failed'
                """,
                (retry_job["id"],),
            )
        if target_operation_ids:
            placeholders = ",".join("?" for _ in target_operation_ids)
            conn.execute(
                f"""
                UPDATE class_commentary_memory_operations
                SET status='pending', attempt_count=0, started_at=NULL,
                    lease_token=NULL, lease_owner=NULL, lease_until=NULL,
                    rq_job_id=NULL, enqueued_at=NULL, next_attempt_at=NULL,
                    last_error=NULL, updated_at=datetime('now','localtime')
                WHERE id IN ({placeholders}) AND status='failed'
                """,
                target_operation_ids,
            )
        event = conn.execute(
            "SELECT * FROM class_commentary_memory_retry_events WHERE id=?",
            (cursor.lastrowid,),
        ).fetchone()
        return dict(event)


def _class_commentary_memory_cleanup_scope(
    *,
    organization_id: int,
    task_id: Optional[int] = None,
    class_id: Optional[int] = None,
    teacher_user_id: Optional[int] = None,
    student_id: Optional[int] = None,
) -> tuple[str, int]:
    scopes = [
        ("task", task_id),
        ("class", class_id),
        ("teacher", teacher_user_id),
        ("student", student_id),
    ]
    selected = [(scope_type, value) for scope_type, value in scopes if value is not None]
    if len(selected) > 1:
        raise ValueError("memory cleanup accepts exactly one scope")
    scope_type, raw_scope_id = (
        selected[0] if selected else ("organization", organization_id)
    )
    if isinstance(raw_scope_id, bool):
        raise ValueError("memory cleanup scope_id must be a positive integer")
    try:
        scope_id = int(raw_scope_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("memory cleanup scope_id must be a positive integer") from exc
    if scope_id <= 0:
        raise ValueError("memory cleanup scope_id must be a positive integer")
    return scope_type, scope_id


def _prepare_class_commentary_memory_cleanup_for_scope_conn(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    task_id: Optional[int] = None,
    class_id: Optional[int] = None,
    teacher_user_id: Optional[int] = None,
    student_id: Optional[int] = None,
) -> dict:
    scope_type, scope_id = _class_commentary_memory_cleanup_scope(
        organization_id=organization_id,
        task_id=task_id,
        class_id=class_id,
        teacher_user_id=teacher_user_id,
        student_id=student_id,
    )
    completed_at = _class_commentary_utc_timestamp()
    extraction_scope_sql = {
        "organization": "1=1",
        "task": "revision.task_id=?",
        "class": "generation.class_id=?",
        "teacher": "revision.teacher_user_id=?",
        "student": """
            EXISTS (
                SELECT 1
                FROM json_each(generation.attending_roster_snapshot_json) AS roster_item
                WHERE CAST(json_extract(roster_item.value, '$.student_id') AS INTEGER)=?
            )
        """,
    }[scope_type]
    extraction_scope_params = [] if scope_type == "organization" else [scope_id]
    extraction_job_rows = conn.execute(
        f"""
        SELECT job.id
        FROM class_commentary_memory_extraction_jobs AS job
        JOIN class_commentary_revisions AS revision ON revision.id=job.revision_id
        JOIN class_commentary_generations AS generation
          ON generation.id=revision.generation_id
        WHERE job.organization_id=?
          AND job.status IN ('queued','running','retry_wait','failed')
          AND {extraction_scope_sql}
        ORDER BY job.id
        """,
        [int(organization_id), *extraction_scope_params],
    ).fetchall()
    obsolete_extraction_job_ids = [int(row["id"]) for row in extraction_job_rows]
    if obsolete_extraction_job_ids:
        placeholders = ",".join("?" for _ in obsolete_extraction_job_ids)
        conn.execute(
            f"""
            UPDATE class_commentary_memory_extraction_jobs
            SET status='obsolete', obsolete_reason=?, obsoleted_at=?, completed_at=?,
                claim_token=NULL, claim_owner=NULL, next_attempt_at=NULL,
                updated_at=datetime('now','localtime')
            WHERE id IN ({placeholders})
              AND status IN ('queued','running','retry_wait','failed')
            """,
            (
                f"{scope_type}_cleanup",
                completed_at,
                completed_at,
                *obsolete_extraction_job_ids,
            ),
        )

    candidate_scope_sql = {
        "organization": "1=1",
        "teacher": "revision.teacher_user_id=?",
        "task": "candidate_revision.task_id=?",
        "class": "generation.class_id=?",
        "student": """
            EXISTS (
                SELECT 1
                FROM json_each(generation.attending_roster_snapshot_json) AS roster_item
                WHERE CAST(json_extract(roster_item.value, '$.student_id') AS INTEGER)=?
            )
        """,
    }[scope_type]
    candidate_scope_params = [] if scope_type == "organization" else [scope_id]
    candidate_build_rows = conn.execute(
        f"""
        SELECT DISTINCT build.id
        FROM class_commentary_skill_candidate_builds AS build
        LEFT JOIN class_commentary_skill_candidate_revisions AS candidate_revision
          ON candidate_revision.candidate_build_id=build.id
        LEFT JOIN class_commentary_revisions AS revision
          ON revision.id=candidate_revision.revision_id
        LEFT JOIN class_commentary_generations AS generation
          ON generation.id=revision.generation_id
        WHERE build.organization_id=?
          AND build.status IN ('queued','running','retry_wait','failed')
          AND {candidate_scope_sql}
        ORDER BY build.id
        """,
        [int(organization_id), *candidate_scope_params],
    ).fetchall()
    obsolete_candidate_build_ids = [int(row["id"]) for row in candidate_build_rows]
    if obsolete_candidate_build_ids:
        placeholders = ",".join("?" for _ in obsolete_candidate_build_ids)
        conn.execute(
            f"""
            UPDATE class_commentary_skill_candidate_builds
            SET status='obsolete', claim_token=NULL, claim_owner=NULL,
                next_attempt_at=NULL, last_error=?, completed_at=?
            WHERE id IN ({placeholders})
              AND status IN ('queued','running','retry_wait','failed')
            """,
            (
                f"{scope_type}_cleanup",
                completed_at,
                *obsolete_candidate_build_ids,
            ),
        )
    conditions = [
        "record.organization_id=?",
        "record.desired_status='active'",
        "evidence.status='active'",
    ]
    params: list[object] = [int(organization_id)]
    if scope_type == "task":
        conditions.append("revision.task_id=?")
        params.append(scope_id)
    elif scope_type == "class":
        conditions.append("generation.class_id=?")
        params.append(scope_id)
    elif scope_type == "teacher":
        conditions.append("evidence.source_teacher_user_id=?")
        params.append(scope_id)
    elif scope_type == "student":
        conditions.extend(
            ["record.memory_type='student_fact'", "record.student_id=?"]
        )
        params.append(scope_id)
    evidence_rows = conn.execute(
        f"""
        SELECT evidence.id AS evidence_id, record.id AS memory_record_id
        FROM class_commentary_memory_evidence AS evidence
        JOIN class_commentary_memory_records AS record
          ON record.id=evidence.memory_record_id
        JOIN class_commentary_revisions AS revision
          ON revision.id=evidence.revision_id
        JOIN class_commentary_generations AS generation
          ON generation.id=revision.generation_id
        WHERE {' AND '.join(conditions)}
        ORDER BY record.id, evidence.id
        """,
        params,
    ).fetchall()
    evidence_ids_by_record: dict[int, list[int]] = {}
    for row in evidence_rows:
        evidence_ids_by_record.setdefault(int(row["memory_record_id"]), []).append(
            int(row["evidence_id"])
        )
    operation_ids = []
    record_ids = []
    revoked_evidence_ids = []
    for record_id, evidence_ids in evidence_ids_by_record.items():
        placeholders = ",".join("?" for _ in evidence_ids)
        revoked = conn.execute(
            f"""
            UPDATE class_commentary_memory_evidence
            SET status='revoked', updated_at=datetime('now','localtime')
            WHERE id IN ({placeholders}) AND status='active'
            """,
            evidence_ids,
        )
        if revoked.rowcount != len(evidence_ids):
            raise RuntimeError("class commentary memory cleanup evidence changed")
        remaining_evidence_count = conn.execute(
            """
            SELECT COUNT(*) AS value
            FROM class_commentary_memory_evidence
            WHERE memory_record_id=? AND status='active'
            """,
            (record_id,),
        ).fetchone()["value"]
        operation = _advance_class_commentary_memory_record_projection_conn(
            conn,
            record_id,
            desired_status=None if remaining_evidence_count else "deleted",
            operation_type="update" if remaining_evidence_count else "delete",
            source_type="cleanup",
            source_id=scope_id,
            cleanup_scope_type=scope_type,
            cleanup_scope_id=scope_id,
        )
        record_ids.append(record_id)
        operation_ids.append(int(operation["id"]))
        revoked_evidence_ids.extend(evidence_ids)
    return {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "record_ids": record_ids,
        "evidence_ids": revoked_evidence_ids,
        "operation_ids": operation_ids,
        "obsolete_extraction_job_ids": obsolete_extraction_job_ids,
        "obsolete_candidate_build_ids": obsolete_candidate_build_ids,
    }


def prepare_class_commentary_memory_cleanup_for_scope(
    *,
    organization_id: int,
    task_id: Optional[int] = None,
    class_id: Optional[int] = None,
    teacher_user_id: Optional[int] = None,
    student_id: Optional[int] = None,
) -> dict:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        return _prepare_class_commentary_memory_cleanup_for_scope_conn(
            conn,
            organization_id=organization_id,
            task_id=task_id,
            class_id=class_id,
            teacher_user_id=teacher_user_id,
            student_id=student_id,
        )


def _prepare_class_commentary_organization_memory_cleanup_conn(
    conn: sqlite3.Connection,
    organization_id: int,
) -> dict:
    cleanup = _prepare_class_commentary_memory_cleanup_for_scope_conn(
        conn,
        organization_id=organization_id,
    )
    record_rows = conn.execute(
        """
        SELECT *
        FROM class_commentary_memory_records
        WHERE organization_id=?
          AND (desired_status<>'deleted' OR applied_status<>'deleted')
        ORDER BY id
        """,
        (organization_id,),
    ).fetchall()
    record_ids = set(int(value) for value in cleanup["record_ids"])
    operation_ids = set(int(value) for value in cleanup["operation_ids"])
    for record in record_rows:
        current_operation = conn.execute(
            """
            SELECT * FROM class_commentary_memory_operations
            WHERE memory_record_id=? AND operation_version=?
            """,
            (record["id"], record["record_version"]),
        ).fetchone()
        is_current_organization_cleanup = bool(
            str(record["desired_status"]) == "deleted"
            and current_operation
            and str(current_operation["source_type"]) == "cleanup"
            and str(current_operation["cleanup_scope_type"] or "") == "organization"
            and int(current_operation["cleanup_scope_id"] or 0) == int(organization_id)
        )
        if is_current_organization_cleanup:
            operation = current_operation
            if str(operation["status"]) in {"failed", "applied"}:
                conn.execute(
                    """
                    UPDATE class_commentary_memory_operations
                    SET status='reconcile_needed', next_attempt_at=?,
                        attempt_count=CASE WHEN status='failed' THEN 0 ELSE attempt_count END,
                        last_error='organization_cleanup_reconciliation',
                        updated_at=datetime('now','localtime')
                    WHERE id=? AND status IN ('failed','applied')
                    """,
                    (_class_commentary_utc_timestamp(), operation["id"]),
                )
                operation = conn.execute(
                    "SELECT * FROM class_commentary_memory_operations WHERE id=?",
                    (operation["id"],),
                ).fetchone()
        else:
            operation = _advance_class_commentary_memory_record_projection_conn(
                conn,
                int(record["id"]),
                desired_status="deleted",
                operation_type="delete",
                source_type="cleanup",
                source_id=organization_id,
                cleanup_scope_type="organization",
                cleanup_scope_id=organization_id,
            )
        record_ids.add(int(record["id"]))
        operation_ids.add(int(operation["id"]))
    return {
        **cleanup,
        "record_ids": sorted(record_ids),
        "operation_ids": sorted(operation_ids),
    }


def has_pending_class_commentary_memory_cleanup(
    *,
    organization_id: int,
    task_id: Optional[int] = None,
    class_id: Optional[int] = None,
    teacher_user_id: Optional[int] = None,
    student_id: Optional[int] = None,
) -> bool:
    scope_type, scope_id = _class_commentary_memory_cleanup_scope(
        organization_id=organization_id,
        task_id=task_id,
        class_id=class_id,
        teacher_user_id=teacher_user_id,
        student_id=student_id,
    )
    conditions = [
        "operation.organization_id=?",
        "operation.source_type='cleanup'",
        "operation.cleanup_scope_type=?",
        "operation.cleanup_scope_id=?",
        "operation.status<>'applied'",
        "operation.status<>'obsolete'",
    ]
    params: list[object] = [int(organization_id), scope_type, scope_id]
    with get_conn() as conn:
        row = conn.execute(
            f"""
            SELECT 1
            FROM class_commentary_memory_operations AS operation
            WHERE {' AND '.join(conditions)}
            LIMIT 1
            """,
            params,
        ).fetchone()
    return bool(row)


def recover_stale_class_commentary_memory_extraction_jobs(
    *,
    timeout_seconds: int = 300,
    active_rq_job_ids: Optional[set[str]] = None,
    now: Optional[datetime] = None,
) -> list[dict]:
    current_dt = now or datetime.now(timezone.utc)
    current = _class_commentary_utc_timestamp(current_dt)
    cutoff = _class_commentary_utc_timestamp(
        current_dt - timedelta(seconds=max(1, int(timeout_seconds)) + 60)
    )
    active_ids = {str(value) for value in (active_rq_job_ids or set())}
    recovered_ids = []
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            """
            SELECT job.*, task.latest_revision_id
            FROM class_commentary_memory_extraction_jobs AS job
            JOIN class_commentary_revisions AS revision ON revision.id=job.revision_id
            JOIN class_commentary_tasks AS task ON task.id=revision.task_id
            WHERE job.status='running' AND job.started_at<=?
            ORDER BY job.id
            """,
            (cutoff,),
        ).fetchall()
        for job in rows:
            if str(job["rq_job_id"] or "") in active_ids:
                continue
            if int(job["latest_revision_id"] or 0) != int(job["revision_id"]):
                status = "obsolete"
                obsolete_reason = "stale_running_revision_not_effective"
                completed_at = current
            elif int(job["attempt_count"] or 0) >= 4:
                status = "failed"
                obsolete_reason = None
                completed_at = current
            else:
                status = "retry_wait"
                obsolete_reason = None
                completed_at = None
            conn.execute(
                """
                UPDATE class_commentary_memory_extraction_jobs
                SET status=?, claim_token=NULL, claim_owner=NULL,
                    next_attempt_at=?, last_error='stale_running_recovered',
                    obsolete_reason=COALESCE(?, obsolete_reason),
                    obsoleted_by_revision_id=CASE WHEN ?='obsolete' THEN ? ELSE obsoleted_by_revision_id END,
                    obsoleted_at=CASE WHEN ?='obsolete' THEN ? ELSE obsoleted_at END,
                    completed_at=?, updated_at=datetime('now','localtime')
                WHERE id=? AND status='running' AND claim_token=?
                """,
                (
                    status,
                    current if status == "retry_wait" else None,
                    obsolete_reason,
                    status,
                    job["latest_revision_id"],
                    status,
                    current,
                    completed_at,
                    job["id"],
                    job["claim_token"],
                ),
            )
            recovered_ids.append(int(job["id"]))
        if not recovered_ids:
            return []
        placeholders = ",".join("?" for _ in recovered_ids)
        recovered = conn.execute(
            f"""
            SELECT * FROM class_commentary_memory_extraction_jobs
            WHERE id IN ({placeholders}) ORDER BY id
            """,
            recovered_ids,
        ).fetchall()
        return [_serialize_class_commentary_memory_job(row) for row in recovered]


def recover_stale_class_commentary_memory_operations(
    *,
    active_rq_job_ids: Optional[set[str]] = None,
    now: Optional[datetime] = None,
) -> list[dict]:
    current_dt = now or datetime.now(timezone.utc)
    current = _class_commentary_utc_timestamp(current_dt)
    active_ids = {str(value) for value in (active_rq_job_ids or set())}
    recovered_ids = []
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            """
            SELECT operation.*, record.record_version AS current_record_version
            FROM class_commentary_memory_operations AS operation
            JOIN class_commentary_memory_records AS record
              ON record.id=operation.memory_record_id
            WHERE operation.status='running' AND operation.lease_until<=?
            ORDER BY operation.id
            """,
            (current,),
        ).fetchall()
        for operation in rows:
            if str(operation["rq_job_id"] or "") in active_ids:
                continue
            if int(operation["expected_record_version"]) != int(
                operation["current_record_version"]
            ):
                status = "obsolete"
                next_attempt_at = None
                error = "expired_lease_record_version_mismatch"
            elif int(operation["attempt_count"] or 0) >= 8:
                status = "failed"
                next_attempt_at = None
                error = "expired_lease_attempt_limit"
            else:
                status = "reconcile_needed"
                next_attempt_at = current
                error = "expired_lease_recovered"
            conn.execute(
                """
                UPDATE class_commentary_memory_operations
                SET status=?, lease_token=NULL, lease_owner=NULL, lease_until=NULL,
                    next_attempt_at=?, last_error=?,
                    updated_at=datetime('now','localtime')
                WHERE id=? AND status='running' AND lease_token=?
                """,
                (
                    status,
                    next_attempt_at,
                    error,
                    operation["id"],
                    operation["lease_token"],
                ),
            )
            recovered_ids.append(int(operation["id"]))
        if not recovered_ids:
            return []
        placeholders = ",".join("?" for _ in recovered_ids)
        recovered = conn.execute(
            f"""
            SELECT * FROM class_commentary_memory_operations
            WHERE id IN ({placeholders}) ORDER BY id
            """,
            recovered_ids,
        ).fetchall()
        return [_serialize_class_commentary_memory_operation(row) for row in recovered]


def reconcile_class_commentary_memory_store(
    *,
    active_rq_job_ids: Optional[set[str]] = None,
    now: Optional[datetime] = None,
    limit: int = 100,
) -> dict:
    current_dt = now or datetime.now(timezone.utc)
    current = _class_commentary_utc_timestamp(current_dt)
    recovered_jobs = recover_stale_class_commentary_memory_extraction_jobs(
        active_rq_job_ids=active_rq_job_ids,
        now=current_dt,
    )
    recovered_operations = recover_stale_class_commentary_memory_operations(
        active_rq_job_ids=active_rq_job_ids,
        now=current_dt,
    )
    obsoleted_job_ids = []
    reconciled_record_ids = []
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        stale_jobs = conn.execute(
            """
            SELECT job.id, task.latest_revision_id
            FROM class_commentary_memory_extraction_jobs AS job
            JOIN class_commentary_revisions AS revision ON revision.id=job.revision_id
            JOIN class_commentary_tasks AS task ON task.id=revision.task_id
            WHERE job.status IN ('queued','retry_wait','failed')
              AND task.latest_revision_id<>job.revision_id
            ORDER BY job.id
            """
        ).fetchall()
        for job in stale_jobs:
            conn.execute(
                """
                UPDATE class_commentary_memory_extraction_jobs
                SET status='obsolete', obsolete_reason='reconciliation_revision_not_effective',
                    obsoleted_by_revision_id=?, obsoleted_at=?, completed_at=?,
                    updated_at=datetime('now','localtime')
                WHERE id=? AND status IN ('queued','retry_wait','failed')
                """,
                (job["latest_revision_id"], current, current, job["id"]),
            )
            obsoleted_job_ids.append(int(job["id"]))
        records = conn.execute(
            """
            SELECT * FROM class_commentary_memory_records
            WHERE desired_status<>applied_status
            ORDER BY id
            LIMIT ?
            """,
            (max(1, min(int(limit), 500)),),
        ).fetchall()
        for record in records:
            operation = conn.execute(
                """
                SELECT * FROM class_commentary_memory_operations
                WHERE memory_record_id=? AND operation_version=?
                """,
                (record["id"], record["record_version"]),
            ).fetchone()
            if not operation:
                operation_type = {
                    "active": "update" if record["mem0_memory_id"] else "add",
                    "superseded": "supersede",
                    "revoked": "revoke",
                    "deleted": "delete",
                }[str(record["desired_status"])]
                operation = _create_class_commentary_memory_operation_conn(
                    conn,
                    record,
                    operation_type=operation_type,
                    source_type="reconciliation",
                    source_id=None,
                )
            elif str(operation["status"]) == "applied":
                conn.execute(
                    """
                    UPDATE class_commentary_memory_operations
                    SET status='reconcile_needed', next_attempt_at=?,
                        last_error='projection_state_mismatch',
                        updated_at=datetime('now','localtime')
                    WHERE id=? AND status='applied'
                    """,
                    (current, operation["id"]),
                )
            reconciled_record_ids.append(int(record["id"]))
    dispatchable_jobs = list_dispatchable_class_commentary_memory_extraction_jobs(
        limit=limit,
        now=current,
    )
    dispatchable_operations = list_dispatchable_class_commentary_memory_operations(
        limit=limit,
        now=current,
    )
    return {
        "recovered_jobs": recovered_jobs,
        "recovered_operations": recovered_operations,
        "obsoleted_job_ids": obsoleted_job_ids,
        "reconciled_record_ids": reconciled_record_ids,
        "dispatchable_job_ids": [int(item["id"]) for item in dispatchable_jobs],
        "dispatchable_operation_ids": [
            int(item["id"]) for item in dispatchable_operations
        ],
    }


def _class_commentary_task_select_sql() -> str:
    return """
        SELECT t.*, c.name AS class_name
        FROM class_commentary_tasks t
        JOIN classes c ON c.id = t.class_id
    """


def _serialize_class_commentary_task_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    string_fields = (
        "status",
        "failure_stage",
        "audio_path",
        "audio_filename",
        "transcript_text",
        "raw_transcript_text",
        "roster_snapshot",
        "transcript_polish_error",
        "transcript_polished_at",
        "confirmed_transcript_text",
        "transcribed_at",
        "skill_id",
        "skill_name",
        "skill_path",
        "skill_content_snapshot",
        "feedback_text",
        "transcription_error",
        "generation_error",
        "transcription_request_key",
        "generation_request_key",
        "chat_provider",
        "chat_model",
        "created_at",
        "updated_at",
        "class_name",
    )
    for field_name in string_fields:
        item[field_name] = item.get(field_name) or ""
    return item


def get_class_commentary_task(task_id: int):
    with get_conn() as conn:
        row = conn.execute(
            f"""
            {_class_commentary_task_select_sql()}
            JOIN users AS task_teacher ON task_teacher.id=t.teacher_user_id
            WHERE t.id=?
              AND COALESCE(NULLIF(c.lifecycle_status, ''), 'active')='active'
              AND task_teacher.status='active'
            """,
            (task_id,),
        ).fetchone()
    return _serialize_class_commentary_task_row(row) if row else None


def list_class_commentary_tasks_for_organization(organization_id: int, limit: int = 30) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            {_class_commentary_task_select_sql()}
            JOIN users AS task_teacher ON task_teacher.id=t.teacher_user_id
            WHERE t.organization_id=?
              AND COALESCE(NULLIF(c.lifecycle_status, ''), 'active')='active'
              AND task_teacher.status='active'
            ORDER BY t.updated_at DESC, t.id DESC
            LIMIT ?
            """,
            (organization_id, max(1, min(int(limit or 30), 100))),
        ).fetchall()
    return [_serialize_class_commentary_task_row(row) for row in rows]


def list_class_commentary_tasks_for_classes(class_ids: list[int], limit: int = 30) -> list[dict]:
    normalized_class_ids = []
    seen_class_ids = set()
    for class_id in class_ids:
        normalized_class_id = int(class_id or 0)
        if normalized_class_id <= 0 or normalized_class_id in seen_class_ids:
            continue
        seen_class_ids.add(normalized_class_id)
        normalized_class_ids.append(normalized_class_id)
    if not normalized_class_ids:
        return []
    placeholders = ",".join("?" for _ in normalized_class_ids)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            {_class_commentary_task_select_sql()}
            JOIN users AS task_teacher ON task_teacher.id=t.teacher_user_id
            WHERE t.class_id IN ({placeholders})
              AND COALESCE(NULLIF(c.lifecycle_status, ''), 'active')='active'
              AND task_teacher.status='active'
            ORDER BY t.updated_at DESC, t.id DESC
            LIMIT ?
            """,
            (*normalized_class_ids, max(1, min(int(limit or 30), 100))),
        ).fetchall()
    return [_serialize_class_commentary_task_row(row) for row in rows]


def create_class_commentary_task(
    *,
    organization_id: int,
    class_id: int,
    teacher_user_id: int,
    audio_path: str,
    audio_filename: str,
    transcription_request_key: str = "",
):
    with get_conn() as conn:
        class_row = conn.execute(
            "SELECT organization_id FROM classes WHERE id=?",
            (class_id,),
        ).fetchone()
        if not class_row:
            raise ValueError("class not found")
        class_organization_id = int(class_row["organization_id"] or 0)
        if int(organization_id or 0) != class_organization_id:
            raise ValueError("organization_id must match class organization")
        teacher_row = conn.execute(
            "SELECT organization_id FROM users WHERE id=?",
            (teacher_user_id,),
        ).fetchone()
        if not teacher_row:
            raise ValueError("teacher_user_id not found")
        if int(teacher_row["organization_id"] or 0) != class_organization_id:
            raise ValueError("teacher_user_id must belong to class organization")
        cur = conn.execute(
            """
            INSERT INTO class_commentary_tasks (
                organization_id, class_id, teacher_user_id, audio_path, audio_filename, transcription_request_key
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                organization_id,
                class_id,
                teacher_user_id,
                audio_path or "",
                audio_filename or "",
                transcription_request_key or "",
            ),
        )
        task_id = cur.lastrowid
    return get_class_commentary_task(task_id)


def _update_class_commentary_task_failure_state(task_id: int, status: str, failure_stage: str, transcription_error: str, generation_error: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_tasks
            SET status=?, failure_stage=?, transcription_error=?, generation_error=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (status, failure_stage, transcription_error, generation_error, task_id),
        )
    return get_class_commentary_task(task_id)


def mark_class_commentary_task_transcribing(task_id: int):
    return _update_class_commentary_task_failure_state(task_id, "transcribing", "", "", "")


def mark_class_commentary_raw_transcription_succeeded(task_id: int, raw_transcript_text: str, roster_snapshot: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_tasks
            SET raw_transcript_text=?,
                roster_snapshot=?,
                transcript_text='',
                confirmed_transcript_text='',
                confirmed_transcript_version=0,
                transcript_polish_error='',
                transcript_polished_at='',
                transcription_error='',
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (raw_transcript_text or "", roster_snapshot or "", task_id),
        )
    return get_class_commentary_task(task_id)


def mark_class_commentary_transcript_polish_succeeded(task_id: int, polished_transcript_text: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_tasks
            SET status='transcribed',
                failure_stage='',
                transcript_text=?,
                confirmed_transcript_text=?,
                confirmed_transcript_version=1,
                transcribed_at=datetime('now','localtime'),
                transcript_polish_error='',
                transcript_polished_at=datetime('now','localtime'),
                transcription_error='',
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (polished_transcript_text or "", polished_transcript_text or "", task_id),
        )
    return get_class_commentary_task(task_id)


def mark_class_commentary_transcript_polish_failed(task_id: int, raw_transcript_text: str, error_message: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_tasks
            SET status='transcribed',
                failure_stage='',
                transcript_text=?,
                confirmed_transcript_text=?,
                confirmed_transcript_version=1,
                transcribed_at=datetime('now','localtime'),
                transcript_polish_error=?,
                transcript_polished_at='',
                transcription_error='',
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (raw_transcript_text or "", raw_transcript_text or "", error_message or "", task_id),
        )
    return get_class_commentary_task(task_id)


def mark_class_commentary_transcription_succeeded(task_id: int, transcript_text: str):
    mark_class_commentary_raw_transcription_succeeded(task_id, transcript_text or "", "")
    return mark_class_commentary_transcript_polish_succeeded(task_id, transcript_text or "")


def save_class_commentary_transcript(task_id: int, confirmed_transcript_text: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_tasks
            SET status='transcribed',
                failure_stage='',
                confirmed_transcript_text=?,
                confirmed_transcript_version=confirmed_transcript_version + 1,
                transcription_error='',
                generation_error='',
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (confirmed_transcript_text or "", task_id),
        )
    return get_class_commentary_task(task_id)


def mark_class_commentary_task_failed(task_id: int, failure_stage: str, error_message: str):
    normalized_stage = (failure_stage or "").strip()
    if normalized_stage == "transcription":
        return _update_class_commentary_task_failure_state(task_id, "failed", "transcription", error_message or "", "")
    if normalized_stage == "generation":
        return _update_class_commentary_task_failure_state(task_id, "failed", "generation", "", error_message or "")
    raise ValueError("failure_stage must be transcription or generation")


def list_students_for_organization(organization_id: int | None = None, include_archived: bool = False) -> list:
    with get_conn() as conn:
        if organization_id is None:
            organization_id = _ensure_organization(conn, DEFAULT_ORGANIZATION_NAME)["id"]
        status_sql = "" if include_archived else " AND status='active'"
        rows = conn.execute(
            f"""
            SELECT id, name, source, parent_contact, status, archived_at, created_at
            FROM students
            WHERE organization_id=?{status_sql}
            ORDER BY name COLLATE NOCASE, id
            """,
            (organization_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_duplicate_student_profiles(raw_name: str, organization_id: int | None = None, include_archived: bool = False) -> list[dict]:
    name = (raw_name or "").strip()
    if not name:
        return []
    with get_conn() as conn:
        if organization_id is None:
            organization_id = _ensure_organization(conn, DEFAULT_ORGANIZATION_NAME)["id"]
        status_sql = "" if include_archived else " AND status='active'"
        rows = conn.execute(
            f"""
            SELECT id, name, source, parent_contact, status, archived_at, created_at
            FROM students
            WHERE organization_id=? AND name=?{status_sql}
            ORDER BY id
            """,
            (organization_id, name),
        ).fetchall()
    return [dict(row) for row in rows]


def _format_student_study_duration(first_date: str, last_date: str) -> str:
    if not first_date or not last_date:
        return "暂未上课"
    try:
        first = datetime.strptime(first_date[:10], "%Y-%m-%d").date()
        last = datetime.strptime(last_date[:10], "%Y-%m-%d").date()
    except ValueError:
        return "暂未上课"
    month_delta = max(0, (last.year - first.year) * 12 + (last.month - first.month))
    years, months = divmod(month_delta, 12)
    if years and months:
        return f"{years}年{months}个月"
    if years:
        return f"{years}年"
    return f"{months}个月" if months else "不足1个月"


def _build_student_profile_from_row(conn: sqlite3.Connection, row) -> dict:
    student = dict(row)
    lesson_row = conn.execute(
        """
        SELECT MIN(l.date) AS first_lesson_date, MAX(l.date) AS last_lesson_date
        FROM class_students cs
        JOIN lessons l ON l.class_id = cs.class_id
        LEFT JOIN review_plan_versions current_v ON current_v.id=l.current_review_plan_version_id
        LEFT JOIN review_plan_versions latest_v ON latest_v.id = (
            SELECT rv.id
            FROM review_plan_versions rv
            WHERE rv.lesson_id=l.id
            ORDER BY rv.version_no DESC, rv.id DESC
            LIMIT 1
        )
        WHERE cs.student_id=? AND COALESCE(current_v.status, latest_v.status, 'ready') != 'failed'
        """,
        (student["id"],),
    ).fetchone()
    study_records = conn.execute(
        """
        SELECT
            c.id AS class_id,
            c.name AS class_name,
            c.class_type,
            c.subject,
            c.stage,
            c.current_grade,
            c.grade,
            c.teacher_name,
            COUNT(l.id) AS lesson_count,
            MIN(l.date) AS first_lesson_date,
            MAX(l.date) AS last_lesson_date
        FROM class_students cs
        JOIN classes c ON c.id = cs.class_id
        LEFT JOIN lessons l
          ON l.class_id = c.id
         AND COALESCE((
             SELECT current_rv.status
             FROM review_plan_versions current_rv
             WHERE current_rv.id=l.current_review_plan_version_id
             LIMIT 1
         ), (
             SELECT rv.status
             FROM review_plan_versions rv
             WHERE rv.lesson_id=l.id
             ORDER BY rv.version_no DESC, rv.id DESC
             LIMIT 1
         ), 'ready') != 'failed'
        WHERE cs.student_id=?
        GROUP BY c.id
        ORDER BY c.subject COLLATE NOCASE, c.id
        """,
        (student["id"],),
    ).fetchall()
    first_lesson_date = str(lesson_row["first_lesson_date"] or "") if lesson_row else ""
    last_lesson_date = str(lesson_row["last_lesson_date"] or "") if lesson_row else ""
    has_current_classes = bool(study_records)
    if has_current_classes:
        study_status = "在读"
    elif first_lesson_date:
        study_status = "暂停/待确认"
    else:
        study_status = "未排课"
    student.update({
        "source": student.get("source") or "",
        "parent_contact": student.get("parent_contact") or "",
        "status": student.get("status") or "active",
        "archived_at": student.get("archived_at") or "",
        "first_lesson_date": first_lesson_date,
        "last_lesson_date": last_lesson_date,
        "study_duration_label": _format_student_study_duration(first_lesson_date, last_lesson_date),
        "study_status": study_status,
        "study_records": [dict(item) for item in study_records],
        "history_items": list_student_class_history(int(student["id"])),
    })
    return student


def create_student_profile(raw_name: str, source: str = "", parent_contact: str = "", organization_id: int | None = None) -> dict:
    name = (raw_name or "").strip()
    if not name:
        raise ValueError("student name is required")
    with get_conn() as conn:
        if organization_id is None:
            organization_id = _ensure_organization(conn, DEFAULT_ORGANIZATION_NAME)["id"]
        cur = conn.execute(
            """
            INSERT INTO students (organization_id, name, source, parent_contact, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (organization_id, name, (source or "").strip(), (parent_contact or "").strip()),
        )
        row = conn.execute("SELECT * FROM students WHERE id=?", (cur.lastrowid,)).fetchone()
        return _build_student_profile_from_row(conn, row)


def _count_student_profile_references(conn: sqlite3.Connection, student_id: int) -> int:
    reference_tables = [
        "class_students",
        "student_class_history",
        "parent_student_bindings",
        "wrong_question_submissions",
        "wechat_wrong_question_upload_tasks",
        "wrong_question_practice_sheets",
        "wrong_question_practice_pack_job_students",
        "weekly_wrong_question_followup_messages",
        "class_commentary_memory_records",
        "class_commentary_student_generation_runs",
        "class_commentary_student_learning_events",
    ]
    total = 0
    for table in reference_tables:
        row = conn.execute(f"SELECT COUNT(*) AS total FROM {table} WHERE student_id=?", (student_id,)).fetchone()
        total += int(row["total"] or 0)
    return total


def delete_or_archive_student_profile(
    student_id: int,
    organization_id: int | None = None,
    actor_user_id: int | None = None,
) -> dict:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        params: list[object] = [student_id]
        scope_sql = ""
        if organization_id is not None:
            scope_sql = " AND organization_id=?"
            params.append(organization_id)
        row = conn.execute(f"SELECT * FROM students WHERE id=?{scope_sql}", tuple(params)).fetchone()
        if not row:
            raise LookupError("student not found")
        memory_cleanup = _prepare_class_commentary_memory_cleanup_for_scope_conn(
            conn,
            organization_id=int(row["organization_id"]),
            student_id=student_id,
        )
        from class_commentary_learning_graph import prepare_graph_cleanup_for_scope_conn

        graph_cleanup = prepare_graph_cleanup_for_scope_conn(
            conn,
            organization_id=int(row["organization_id"]),
            student_id=student_id,
            actor_user_id=actor_user_id,
            reason="student_profile_delete",
        )
        reference_count = _count_student_profile_references(conn, student_id)
        if reference_count == 0:
            conn.execute("DELETE FROM students WHERE id=?", (student_id,))
            return {
                "action": "deleted",
                "student_id": student_id,
                "reference_count": 0,
                "memory_cleanup": memory_cleanup,
                "graph_cleanup": graph_cleanup,
            }
        conn.execute(
            """
            UPDATE students
            SET status='archived', archived_at=datetime('now','localtime')
            WHERE id=?
            """,
            (student_id,),
        )
        archived_row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        return {
            "action": "archived",
            "student_id": student_id,
            "reference_count": reference_count,
            "student": _build_student_profile_from_row(conn, archived_row),
            "memory_cleanup": memory_cleanup,
            "graph_cleanup": graph_cleanup,
        }


def update_student_profile(student_id: int, raw_name: str, source: str = "", parent_contact: str = "", organization_id: int | None = None) -> dict:
    name = (raw_name or "").strip()
    if not name:
        raise ValueError("student name is required")
    with get_conn() as conn:
        params: list[object] = [name, (source or "").strip(), (parent_contact or "").strip(), student_id]
        scope_sql = ""
        if organization_id is not None:
            scope_sql = " AND organization_id=?"
            params.append(organization_id)
        cur = conn.execute(
            f"UPDATE students SET name=?, source=?, parent_contact=? WHERE id=?{scope_sql}",
            tuple(params),
        )
        if cur.rowcount == 0:
            raise LookupError("student not found")
        row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        return _build_student_profile_from_row(conn, row)


def get_student_profile(student_id: int, organization_id: int | None = None) -> dict | None:
    with get_conn() as conn:
        params: list[object] = [student_id]
        scope_sql = ""
        if organization_id is not None:
            scope_sql = " AND organization_id=?"
            params.append(organization_id)
        row = conn.execute(f"SELECT * FROM students WHERE id=?{scope_sql}", tuple(params)).fetchone()
        if not row:
            return None
        return _build_student_profile_from_row(conn, row)
_REVIEW_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def _load_review_plan_days(raw_plan_json: str) -> tuple[dict, list[dict]]:
    try:
        plan = json.loads(raw_plan_json or "{}")
    except json.JSONDecodeError:
        return {}, []
    if not isinstance(plan, dict):
        return {}, []
    days = plan.get("days")
    if not isinstance(days, list):
        return plan, []
    return plan, [day for day in days if isinstance(day, dict)]


def _extract_review_day_date(day_plan: dict) -> str:
    for key in ("review_date", "date", "target_date"):
        value = str(day_plan.get(key) or "").strip()
        if _REVIEW_DATE_PATTERN.fullmatch(value):
            return value
    for key in ("label", "title", "day_label"):
        match = _REVIEW_DATE_PATTERN.search(str(day_plan.get(key) or ""))
        if match:
            return match.group(0)
    return ""


def _extract_review_day_steps(day_plan: dict) -> list[str]:
    raw_steps = day_plan.get("steps")
    if not isinstance(raw_steps, list):
        raw_steps = day_plan.get("tasks")
    if not isinstance(raw_steps, list):
        raw_steps = day_plan.get("items")
    if not isinstance(raw_steps, list):
        return ["按本课复习计划完成当天复习"]

    steps: list[str] = []
    for raw_step in raw_steps:
        if isinstance(raw_step, str):
            text = raw_step.strip()
        elif isinstance(raw_step, dict):
            text = str(
                raw_step.get("title")
                or raw_step.get("text")
                or raw_step.get("content")
                or raw_step.get("prompt")
                or ""
            ).strip()
        else:
            text = ""
        if text:
            steps.append(text)
    return steps or ["按本课复习计划完成当天复习"]


def _extract_review_day_pdf_page(day_plan: dict, day_index: int) -> tuple[int, bool]:
    for key in ("pdf_page", "page", "start_page"):
        value = day_plan.get(key)
        if isinstance(value, bool):
            continue
        try:
            page = int(value)
        except (TypeError, ValueError):
            continue
        if page > 0:
            return page, False
    return max(1, 2 + int(day_index)), True


def _student_review_student_row(conn: sqlite3.Connection, student_id: int):
    return conn.execute(
        """
        SELECT
            s.id,
            s.name,
            s.organization_id,
            GROUP_CONCAT(DISTINCT c.name) AS class_names,
            COUNT(DISTINCT c.id) AS class_count
        FROM students s
        JOIN class_students cs ON cs.student_id=s.id
        JOIN classes c ON c.id=cs.class_id
        WHERE s.id=?
        GROUP BY s.id, s.name, s.organization_id
        """,
        (int(student_id),),
    ).fetchone()


def student_account_can_access_lesson(account: dict, lesson_id: int) -> bool:
    student_id = int(((account or {}).get("student") or {}).get("id") or 0)
    if not student_id:
        return False
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM lessons l
            JOIN class_students cs ON cs.class_id=l.class_id
            WHERE l.id=? AND cs.student_id=?
            LIMIT 1
            """,
            (int(lesson_id), student_id),
        ).fetchone()
    return row is not None


def list_student_review_tasks_for_student_account(account: dict, review_date: str) -> Optional[dict]:
    student_id = int(((account or {}).get("student") or {}).get("id") or 0)
    organization_id = int((account or {}).get("organization_id") or 0)
    if not student_id or not organization_id:
        return None
    with get_conn() as conn:
        student_row = _student_review_student_row(conn, student_id)
        if not student_row:
            return None

        rows = conn.execute(
            """
            SELECT
                l.*,
                v.plan_json AS current_plan_json,
                v.pdf_path AS current_pdf_path,
                c.name AS class_name,
                c.subject AS class_subject,
                c.grade AS class_grade
            FROM lessons l
            JOIN review_plan_versions v ON v.id=l.current_review_plan_version_id
            JOIN classes c ON c.id=l.class_id
            JOIN class_students cs ON cs.class_id=c.id
            WHERE cs.student_id=?
              AND c.organization_id=?
              AND l.current_review_plan_version_id IS NOT NULL
              AND COALESCE(v.plan_json, '') <> ''
              AND COALESCE(v.status, 'ready') = 'ready'
            ORDER BY l.date DESC, l.id DESC
            """,
            (student_id, organization_id),
        ).fetchall()

    tasks: list[dict] = []
    for row in rows:
        lesson = dict(row)
        plan, day_plans = _load_review_plan_days(str(lesson.get("current_plan_json") or ""))
        lesson_info = plan.get("lesson_info") if isinstance(plan.get("lesson_info"), dict) else {}
        for day_index, day_plan in enumerate(day_plans):
            if _extract_review_day_date(day_plan) != review_date:
                continue
            pdf_path = str(lesson.get("current_pdf_path") or "").strip()
            pdf_page, pdf_page_estimated = _extract_review_day_pdf_page(day_plan, day_index)
            lesson_id = int(lesson["id"])
            topic = str(lesson.get("topic") or lesson_info.get("topic") or "").strip()
            subject = str(lesson.get("subject") or lesson.get("class_subject") or lesson_info.get("subject") or "").strip()
            label = str(day_plan.get("label") or day_plan.get("title") or f"{review_date} 复习").strip()
            estimated_time = str(day_plan.get("time") or day_plan.get("estimated_time") or "").strip()
            tasks.append(
                {
                    "lesson_id": lesson_id,
                    "lesson_date": lesson.get("date") or "",
                    "lesson_subject": subject,
                    "lesson_topic": topic,
                    "class_id": lesson.get("class_id"),
                    "class_name": lesson.get("class_name") or "",
                    "review_label": label,
                    "estimated_time": estimated_time,
                    "steps": _extract_review_day_steps(day_plan),
                    "pdf_url": f"/api/student/pdf/{lesson_id}",
                    "pdf_download_url": f"/api/student/pdf/download/{lesson_id}",
                    "pdf_filename": Path(pdf_path).name if pdf_path else "",
                    "pdf_available": bool(pdf_path and Path(pdf_path).exists()),
                    "pdf_page": pdf_page,
                    "pdf_page_estimated": pdf_page_estimated,
                }
            )

    return {
        "date": review_date,
        "student": {
            "id": int(student_row["id"]),
            "name": student_row["name"],
            "organization_id": student_row["organization_id"],
            "class_names": _class_names_from_csv(student_row["class_names"]),
            "class_count": int(student_row["class_count"] or 0),
        },
        "tasks": tasks,
    }


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
    try:
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
    finally:
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
        class_row = conn.execute(
            "SELECT id, organization_id FROM classes WHERE id=?",
            (class_id,),
        ).fetchone()
        if not class_row:
            raise LookupError("class not found")
        if class_row["organization_id"] is None:
            raise ValueError("class organization is required")

        student_name = _dedupe_student_name_in_class(class_id, raw_name, conn=conn)
        cur = conn.execute(
            "INSERT INTO students (organization_id, name) VALUES (?, ?)",
            (class_row["organization_id"], student_name),
        )
        student_id = cur.lastrowid
        conn.execute(
            "INSERT INTO class_students (class_id, student_id) VALUES (?, ?)",
            (class_id, student_id),
        )
        row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    student = dict(row)
    record_class_history(class_id, "student_added", after={"student_id": student_id, "student_name": student["name"]})
    record_student_class_history(student_id, class_id, "joined", after={"class_id": class_id, "student_name": student["name"]})
    return student


def add_existing_student_to_class(class_id: int, student_id: int):
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        class_row = conn.execute(
            "SELECT id, organization_id, class_type FROM classes WHERE id=?",
            (class_id,),
        ).fetchone()
        if not class_row:
            raise LookupError("class not found")
        student_row = conn.execute(
            "SELECT * FROM students WHERE id=? AND organization_id=?",
            (student_id, class_row["organization_id"]),
        ).fetchone()
        if not student_row:
            raise LookupError("student not found")
        existing_row = conn.execute(
            "SELECT 1 FROM class_students WHERE class_id=? AND student_id=?",
            (class_id, student_id),
        ).fetchone()
        if existing_row:
            return dict(student_row)
        current_count = conn.execute(
            "SELECT COUNT(*) AS count FROM class_students WHERE class_id=?",
            (class_id,),
        ).fetchone()["count"]
        class_type = class_row["class_type"] or "group"
        small_class_limits = {"1v1": 1, "1v2": 2, "1v3": 3}
        limit = small_class_limits.get(class_type)
        if limit is not None and current_count >= limit:
            raise ValueError(f"当前班型最多 {limit} 名学员")
        conn.execute(
            "INSERT INTO class_students (class_id, student_id) VALUES (?, ?)",
            (class_id, student_id),
        )
    student = dict(student_row)
    record_class_history(class_id, "student_added", after={"student_id": student_id, "student_name": student["name"]})
    record_student_class_history(student_id, class_id, "joined", after={"class_id": class_id, "student_name": student["name"]})
    return student


def remove_student_from_class(class_id: int, student_id: int) -> bool:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE parent_student_bindings
            SET status='inactive', updated_at=datetime('now','localtime')
            WHERE class_id=? AND student_id=? AND status='active'
            """,
            (class_id, student_id),
        )
        student_row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        cur = conn.execute(
            "DELETE FROM class_students WHERE class_id=? AND student_id=?",
            (class_id, student_id),
        )
    removed = cur.rowcount > 0
    if removed:
        student = dict(student_row) if student_row else {"id": student_id}
        record_class_history(class_id, "student_removed", before={"student_id": student_id, "student_name": student.get("name", "")})
        record_student_class_history(student_id, class_id, "left", before={"class_id": class_id, "student_name": student.get("name", "")})
    return removed


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

    before = get_class(class_id)
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
    record_class_history(class_id, "teacher_changed", before=before, after=get_class(class_id))


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
            WHERE COALESCE(NULLIF(o.status, ''), 'active')='active'
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


def actor_can_manage_user_visible_pages(actor_user: dict, target_user: dict) -> bool:
    if not actor_user or not target_user:
        return False
    if actor_user.get("id") == target_user.get("id"):
        return False
    if actor_user.get("role") == SUPER_OWNER_ROLE:
        return target_user.get("role") != SUPER_OWNER_ROLE
    if actor_user.get("organization_id") != target_user.get("organization_id"):
        return False
    if actor_user.get("role") == OWNER_ROLE:
        return target_user.get("role") in {ADMIN_ROLE, MEMBER_ROLE}
    if actor_user.get("role") == ADMIN_ROLE:
        return target_user.get("role") == MEMBER_ROLE
    return False


def list_classes_for_actor(actor_user: dict, scope: str = "current") -> list[dict]:
    if (actor_user or {}).get("role") == SUPER_OWNER_ROLE:
        return list_classes(scope=scope)
    lifecycle_clause = _class_lifecycle_where_clause(scope, "c")
    where_clauses = ["c.organization_id=?"]
    if lifecycle_clause:
        where_clauses.append(lifecycle_clause)
    where_sql = " AND ".join(where_clauses)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
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
            WHERE {where_sql}
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """,
            (actor_user["organization_id"],),
        ).fetchall()
    return [dict(row) for row in rows]


def list_lessons_for_actor(actor_user: dict, month_str: str = "", class_id: int = 0, class_scope: str = "current") -> list[dict]:
    if (actor_user or {}).get("role") == SUPER_OWNER_ROLE:
        return list_lessons(month_str=month_str, class_id=class_id, class_scope=class_scope)
    lifecycle_clause = _lesson_class_lifecycle_where_clause(class_scope, "c", "l")
    with get_conn() as conn:
        query_sql = """
            SELECT l.*
            FROM lessons l
            LEFT JOIN classes c ON c.id = l.class_id
            WHERE l.organization_id=?
        """
        params: list[object] = [actor_user["organization_id"]]
        if class_id:
            query_sql += " AND l.class_id=?"
            params.append(class_id)
        if month_str:
            query_sql += " AND l.date LIKE ?"
            params.append(f"{month_str}%")
        if lifecycle_clause:
            query_sql += f" AND {lifecycle_clause}"
        query_sql += " ORDER BY l.created_at DESC, l.id DESC"
        rows = conn.execute(query_sql, params).fetchall()
        return [_attach_review_plan_version_summary(conn, dict(row)) for row in rows]


def list_lessons_page_for_actor(
    actor_user: dict,
    month_str: str = "",
    class_id: int = 0,
    class_scope: str = "current",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    if (actor_user or {}).get("role") == SUPER_OWNER_ROLE:
        return list_lessons_page(
            month_str=month_str,
            class_id=class_id,
            class_scope=class_scope,
            page=page,
            page_size=page_size,
        )
    if (actor_user or {}).get("role") in {OWNER_ROLE, ADMIN_ROLE}:
        return _list_lessons_page(
            month_str=month_str,
            class_id=class_id,
            class_scope=class_scope,
            organization_id=int(actor_user["organization_id"]),
            page=page,
            page_size=page_size,
        )
    return _list_lessons_page(
        month_str=month_str,
        class_id=class_id,
        class_scope=class_scope,
        organization_id=int(actor_user["organization_id"]),
        member_class_ids=get_user_class_ids(int(actor_user["id"])),
        page=page,
        page_size=page_size,
    )


def list_consultations_for_actor(
    actor_user: dict,
    query: str = "",
    search_mode: str = "fuzzy",
    scope: str = "current",
    ownership: str = "all",
) -> list[dict]:
    organization_id = None if (actor_user or {}).get("role") == SUPER_OWNER_ROLE else actor_user["organization_id"]
    if actor_user.get("role") == MEMBER_ROLE:
        normalized_scope = scope if scope in {"current", "history"} else "current"
        normalized_ownership = ownership if ownership in {"all", "created", "transferred"} else "all"
        rows = list_consultations(
            query=query,
            search_mode=search_mode,
            organization_id=organization_id,
        )
        visible_rows = []
        for row in rows:
            is_creator = row.get("created_by_user_id") == actor_user.get("id")
            current_assignment = _consultation_current_assignment_context_for_actor(row, actor_user)
            historical_assignment = _consultation_assignment_context_for_actor(row, actor_user)
            current_responsibility = _consultation_current_responsibility_context(row)
            creator_current_access = bool(is_creator and (current_assignment or not current_responsibility))
            if normalized_scope == "current":
                has_assignment = current_assignment is not None
                has_creator_visibility = creator_current_access
            else:
                has_assignment = historical_assignment is not None and current_assignment is None
                has_creator_visibility = bool(is_creator and not creator_current_access)
            if has_creator_visibility or has_assignment:
                if normalized_ownership == "created" and not is_creator:
                    continue
                if normalized_ownership == "transferred" and (is_creator or not historical_assignment):
                    continue
                visible_rows.append(_annotate_consultation_for_actor(row, actor_user))
        return visible_rows

    return list_consultations(
        query=query,
        search_mode=search_mode,
        organization_id=organization_id,
    )


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


def update_user_avatar_preferences(
    user_id: int,
    *,
    avatar_source: str,
    avatar_seed: str = "",
    avatar_upload_path: str = "",
):
    normalized_source = str(avatar_source or "").strip() or "dicebear"
    if normalized_source not in {"dicebear", "upload"}:
        raise ValueError("avatar_source is invalid")
    normalized_seed = str(avatar_seed or "").strip()
    normalized_upload_path = str(avatar_upload_path or "").strip()
    if normalized_source == "dicebear":
        normalized_upload_path = ""
    elif not normalized_upload_path:
        raise ValueError("avatar_upload_path is required")
    with get_conn() as conn:
        user_row = _fetch_user_row_by_id(conn, user_id)
        if not user_row:
            raise LookupError("user not found")
        conn.execute(
            "UPDATE users SET avatar_source=?, avatar_seed=?, avatar_upload_path=? WHERE id=?",
            (normalized_source, normalized_seed, normalized_upload_path, user_id),
        )
        updated = _fetch_user_row_by_id(conn, user_id)
    return _public_user_dict(updated)


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


def update_user_visible_pages_for_actor(actor_user: dict, target_user_id: int, visible_pages: object):
    normalized_pages = normalize_visible_pages(visible_pages)
    with get_conn() as conn:
        target_row = _fetch_user_row_by_id(conn, target_user_id)
        if not target_row:
            raise LookupError("user not found")
        target_user = _public_user_dict(target_row)
        if not actor_can_manage_user_visible_pages(actor_user, target_user):
            raise LookupError("user not found")
        conn.execute(
            "UPDATE users SET visible_pages_json=? WHERE id=?",
            (json.dumps(normalized_pages, ensure_ascii=False), target_user_id),
        )
        updated = _fetch_user_row_by_id(conn, target_user_id)
    return _public_user_dict(updated)


def delete_user_for_actor(actor_user: dict, target_user_id: int) -> dict:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
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
        has_commentary_history = conn.execute(
            """
            SELECT 1
            WHERE EXISTS (
                SELECT 1 FROM class_commentary_skills
                WHERE imported_by_user_id=?
            ) OR EXISTS (
                SELECT 1 FROM class_commentary_skill_activation_events
                WHERE actor_user_id=?
            ) OR EXISTS (
                SELECT 1 FROM class_commentary_skill_candidate_builds
                WHERE requested_by_user_id=?
            ) OR EXISTS (
                SELECT 1 FROM class_commentary_memory_records
                WHERE created_by_teacher_user_id=?
            ) OR EXISTS (
                SELECT 1 FROM class_commentary_memory_evidence
                WHERE source_teacher_user_id=?
            ) OR EXISTS (
                SELECT 1 FROM class_commentary_tasks
                WHERE teacher_user_id=?
                  AND (
                      latest_generation_id IS NOT NULL
                      OR latest_revision_id IS NOT NULL
                      OR generation_seq > 0
                      OR feedback_revision_no > 0
                      OR feedback_text<>''
                      OR final_feedback_text<>''
                  )
            ) OR EXISTS (
                SELECT 1 FROM class_commentary_generations
                WHERE teacher_user_id=?
            ) OR EXISTS (
                SELECT 1 FROM class_commentary_revisions
                WHERE teacher_user_id=?
            )
            """,
            (
                target_user_id,
                target_user_id,
                target_user_id,
                target_user_id,
                target_user_id,
                target_user_id,
                target_user_id,
                target_user_id,
            ),
        ).fetchone()
        memory_cleanup = None
        if has_commentary_history:
            memory_cleanup = _prepare_class_commentary_memory_cleanup_for_scope_conn(
                conn,
                organization_id=int(target_user["organization_id"]),
                teacher_user_id=target_user_id,
            )

        conn.execute("UPDATE registration_requests SET reviewed_by=NULL WHERE reviewed_by=?", (target_user_id,))
        conn.execute("UPDATE organization_requests SET reviewed_by=NULL WHERE reviewed_by=?", (target_user_id,))
        conn.execute("UPDATE organization_invites SET created_by=NULL WHERE created_by=?", (target_user_id,))
        conn.execute("UPDATE consultations SET assigned_user_id=NULL WHERE assigned_user_id=?", (target_user_id,))
        conn.execute("UPDATE course_calendar_schedules SET created_by=NULL WHERE created_by=?", (target_user_id,))
        conn.execute("UPDATE class_invite_codes SET created_by_user_id=NULL WHERE created_by_user_id=?", (target_user_id,))
        conn.execute("UPDATE organization_credit_ledger SET operator_user_id=NULL WHERE operator_user_id=?", (target_user_id,))
        conn.execute("UPDATE xhs_order_redemptions SET redeemed_by_user_id=NULL WHERE redeemed_by_user_id=?", (target_user_id,))
        conn.execute("UPDATE weekly_wrong_question_followup_messages SET teacher_user_id=NULL WHERE teacher_user_id=?", (target_user_id,))
        conn.execute("UPDATE weekly_wrong_question_followup_messages SET generated_by=NULL WHERE generated_by=?", (target_user_id,))
        conn.execute("DELETE FROM wrong_question_practice_pack_jobs WHERE created_by=?", (target_user_id,))
        conn.execute("DELETE FROM wrong_question_practice_sheets WHERE teacher_user_id=? OR created_by=?", (target_user_id, target_user_id))
        conn.execute("DELETE FROM wrong_question_submissions WHERE teacher_user_id=?", (target_user_id,))
        if not has_commentary_history:
            conn.execute(
                "DELETE FROM class_commentary_tasks WHERE teacher_user_id=?",
                (target_user_id,),
            )
        conn.execute("DELETE FROM parent_student_bindings WHERE teacher_user_id=?", (target_user_id,))
        conn.execute("DELETE FROM ai_usage_ledger WHERE user_id=?", (target_user_id,))
        conn.execute("DELETE FROM auth_sessions WHERE user_id=?", (target_user_id,))
        conn.execute("DELETE FROM monthly_plan_jobs WHERE user_id=?", (target_user_id,))
        conn.execute("DELETE FROM user_classes WHERE user_id=?", (target_user_id,))
        if has_commentary_history:
            conn.execute(
                "UPDATE users SET status='inactive' WHERE id=?",
                (target_user_id,),
            )
        else:
            conn.execute("DELETE FROM users WHERE id=?", (target_user_id,))

        if affected_class_ids:
            _sync_class_teacher_metadata(conn, affected_class_ids)
        return {
            "action": "deactivated" if has_commentary_history else "deleted",
            "user_id": target_user_id,
            "memory_cleanup": memory_cleanup,
        }


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


def reset_user_password_by_recovery(
    username: str,
    new_password: str,
    recovery_phone: str = "",
    security_question: str = "",
    security_answer: str = "",
) -> None:
    normalized_username = _normalize_username(username)
    if not normalized_username or not new_password:
        raise ValueError("请填写账号和新密码")
    if len(new_password) < 6:
        raise ValueError("新密码至少需要 6 位")

    normalized_phone = _normalize_recovery_phone(recovery_phone)
    normalized_question = (security_question or "").strip()
    normalized_answer = _normalize_security_answer(security_answer)

    with get_conn() as conn:
        row = _fetch_user_row_by_username(conn, normalized_username)
        if not row:
            raise ValueError("找回密码验证失败")
        phone_matched = bool(normalized_phone and row["recovery_phone"] and normalized_phone == row["recovery_phone"])
        security_matched = bool(
            normalized_question
            and normalized_answer
            and row["security_question"]
            and row["security_answer_hash"]
            and normalized_question == row["security_question"]
            and hash_password(normalized_answer) == row["security_answer_hash"]
        )
        if not phone_matched and not security_matched:
            raise ValueError("找回密码验证失败")
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (hash_password(new_password), row["id"]),
        )


def change_user_password(user_id: int, current_password: str, new_password: str) -> None:
    if not current_password or not new_password:
        raise ValueError("请填写当前密码和新密码")
    if len(new_password) < 6:
        raise ValueError("新密码至少需要 6 位")
    with get_conn() as conn:
        user_row = _fetch_user_row_by_id(conn, user_id)
        if not user_row:
            raise LookupError("user not found")
        if user_row["password_hash"] != hash_password(current_password):
            raise ValueError("当前密码不正确")
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (hash_password(new_password), user_id),
        )


def list_unbound_classes_for_user_claim(user_id: int) -> list[dict]:
    with get_conn() as conn:
        user_row = _fetch_user_row_by_id(conn, user_id)
        if not user_row:
            raise LookupError("user not found")
        rows = conn.execute(
            """
            SELECT c.*, COUNT(l.id) AS lesson_count, NULL AS teacher_user_id
            FROM classes c
            LEFT JOIN lessons l ON l.class_id = c.id
            WHERE c.organization_id=?
              AND NOT EXISTS (
                  SELECT 1 FROM user_classes uc WHERE uc.class_id=c.id
              )
            GROUP BY c.id
            ORDER BY c.created_at DESC, c.id DESC
            """,
            (user_row["organization_id"],),
        ).fetchall()
    return [dict(row) for row in rows]


def claim_classes_for_user(user_id: int, class_ids: list[int]) -> dict:
    if not isinstance(class_ids, list):
        raise ValueError("class_ids must be a list")

    normalized_class_ids = []
    seen = set()
    for raw_class_id in class_ids:
        if isinstance(raw_class_id, bool) or not isinstance(raw_class_id, int):
            raise ValueError("class_ids must be integers")
        if raw_class_id in seen:
            continue
        seen.add(raw_class_id)
        normalized_class_ids.append(raw_class_id)

    with get_conn() as conn:
        user_row = _fetch_user_row_by_id(conn, user_id)
        if not user_row:
            raise LookupError("user not found")
        if user_row["role"] != MEMBER_ROLE:
            raise ValueError("仅老师账号需要认领班级")

        unbound_rows = conn.execute(
            """
            SELECT c.id
            FROM classes c
            WHERE c.organization_id=?
              AND NOT EXISTS (
                  SELECT 1 FROM user_classes uc WHERE uc.class_id=c.id
              )
            ORDER BY c.id
            """,
            (user_row["organization_id"],),
        ).fetchall()
        unbound_ids = {row["id"] for row in unbound_rows}
        if not normalized_class_ids and unbound_ids:
            raise ValueError("请选择需要绑定的班级")

        for class_id in normalized_class_ids:
            if class_id not in unbound_ids:
                class_row = conn.execute("SELECT organization_id FROM classes WHERE id=?", (class_id,)).fetchone()
                if not class_row or class_row["organization_id"] != user_row["organization_id"]:
                    raise LookupError("class not found")
                raise ValueError("班级已绑定")
            conn.execute(
                "INSERT INTO user_classes (user_id, class_id) VALUES (?, ?)",
                (user_id, class_id),
            )
        if normalized_class_ids:
            _sync_class_teacher_metadata(conn, normalized_class_ids)
        conn.execute(
            "UPDATE users SET initial_class_claim_completed=1 WHERE id=?",
            (user_id,),
        )
        updated = _fetch_user_row_by_id(conn, user_id)
    return _public_user_dict(updated)


def create_organization_request(
    organization_name: str,
    username: str,
    display_name: str,
    password: str,
    recovery_phone: str = "",
    security_question: str = "",
    security_answer: str = "",
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
        normalized_phone, normalized_question, answer_hash = _normalize_account_recovery(
            recovery_phone=recovery_phone,
            security_question=security_question,
            security_answer=security_answer,
        )
        cur = conn.execute(
            """
            INSERT INTO organization_requests
                (organization_name, username, password_hash, display_name, status,
                 recovery_phone, security_question, security_answer_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_name,
                normalized_username,
                hash_password(password),
                normalized_display_name,
                ORGANIZATION_REQUEST_PENDING,
                normalized_phone,
                normalized_question,
                answer_hash,
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
            INSERT INTO users (
                username, password_hash, display_name, role, status, organization_id,
                recovery_phone, security_question, security_answer_hash
            )
            VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?)
            """,
            (
                req["username"],
                req["password_hash"],
                req["display_name"],
                OWNER_ROLE,
                org["id"],
                req["recovery_phone"],
                req["security_question"],
                req["security_answer_hash"],
            ),
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


def delete_organization(org_id: int, actor_user_id: int | None = None) -> dict:
    """Delete an organization and all its data. Cannot delete the default org."""
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        org_row = conn.execute(
            "SELECT id, name, status FROM organizations WHERE id=?",
            (org_id,),
        ).fetchone()
        if not org_row:
            raise LookupError("organization not found")
        if org_row["name"] == DEFAULT_ORGANIZATION_NAME:
            raise ValueError("不能删除默认机构")
        has_commentary_history = conn.execute(
            """
            SELECT 1
            WHERE EXISTS (
                SELECT 1 FROM class_commentary_skills WHERE organization_id=?
            ) OR EXISTS (
                SELECT 1 FROM class_commentary_memory_records WHERE organization_id=?
            ) OR EXISTS (
                SELECT 1 FROM class_commentary_tasks
                WHERE organization_id=?
                  AND (
                      latest_generation_id IS NOT NULL
                      OR latest_revision_id IS NOT NULL
                      OR generation_seq > 0
                      OR feedback_revision_no > 0
                      OR feedback_text<>''
                      OR final_feedback_text<>''
                  )
            ) OR EXISTS (
                SELECT 1 FROM class_commentary_generations WHERE organization_id=?
            ) OR EXISTS (
                SELECT 1 FROM class_commentary_revisions WHERE organization_id=?
            )
            """,
            (org_id, org_id, org_id, org_id, org_id),
        ).fetchone()
        if has_commentary_history:
            memory_cleanup = _prepare_class_commentary_organization_memory_cleanup_conn(
                conn,
                org_id,
            )
            from class_commentary_learning_graph import prepare_graph_cleanup_for_scope_conn

            graph_cleanup = prepare_graph_cleanup_for_scope_conn(
                conn,
                organization_id=org_id,
                actor_user_id=actor_user_id,
                reason="organization_delete",
            )
            deleted_at = _class_commentary_utc_timestamp()
            conn.execute(
                """
                UPDATE organizations
                SET status='inactive', deleted_at=?
                WHERE id=?
                """,
                (deleted_at, org_id),
            )
            conn.execute(
                "UPDATE users SET status='inactive' WHERE organization_id=?",
                (org_id,),
            )
            conn.execute(
                "UPDATE student_accounts SET status='inactive' WHERE organization_id=?",
                (org_id,),
            )
            conn.execute(
                """
                UPDATE students
                SET status='archived', archived_at=COALESCE(NULLIF(archived_at, ''), ?)
                WHERE organization_id=? AND status='active'
                """,
                (deleted_at, org_id),
            )
            conn.execute(
                """
                UPDATE classes
                SET lifecycle_status=?, lifecycle_status_updated_at=?
                WHERE organization_id=?
                """,
                (CLASS_LIFECYCLE_ARCHIVED, deleted_at, org_id),
            )
            conn.execute(
                """
                UPDATE class_commentary_skills
                SET status='disabled', updated_at=datetime('now','localtime')
                WHERE organization_id=? AND status='active'
                """,
                (org_id,),
            )
            conn.execute(
                """
                UPDATE organization_invites
                SET status='revoked', revoked_at=COALESCE(revoked_at, ?)
                WHERE organization_id=? AND status='active'
                """,
                (deleted_at, org_id),
            )
            conn.execute(
                """
                UPDATE class_invite_codes
                SET status='revoked', revoked_at=COALESCE(revoked_at, ?)
                WHERE organization_id=? AND status='active'
                """,
                (deleted_at, org_id),
            )
            conn.execute(
                """
                UPDATE parent_student_bindings
                SET status='revoked', updated_at=datetime('now','localtime')
                WHERE organization_id=? AND status='active'
                """,
                (org_id,),
            )
            conn.execute(
                """
                DELETE FROM student_auth_sessions
                WHERE account_id IN (
                    SELECT id FROM student_accounts WHERE organization_id=?
                )
                """,
                (org_id,),
            )
            conn.execute(
                """
                DELETE FROM auth_sessions
                WHERE user_id IN (SELECT id FROM users WHERE organization_id=?)
                """,
                (org_id,),
            )
            conn.execute(
                """
                DELETE FROM user_classes
                WHERE user_id IN (SELECT id FROM users WHERE organization_id=?)
                """,
                (org_id,),
            )
            return {
                "action": "deactivated",
                "organization_id": org_id,
                "memory_cleanup": memory_cleanup,
                "graph_cleanup": graph_cleanup,
            }
        conn.execute("DELETE FROM monthly_plan_jobs WHERE organization_id=?", (org_id,))
        conn.execute("DELETE FROM wrong_question_practice_pack_jobs WHERE organization_id=?", (org_id,))
        conn.execute("DELETE FROM class_commentary_tasks WHERE organization_id=?", (org_id,))
        # 1. lessons
        conn.execute("DELETE FROM lessons WHERE organization_id=?", (org_id,))
        # 2. user_classes and class_students (via classes)
        conn.execute(
            "DELETE FROM user_classes WHERE class_id IN (SELECT id FROM classes WHERE organization_id=?)",
            (org_id,),
        )
        conn.execute(
            "DELETE FROM class_students WHERE class_id IN (SELECT id FROM classes WHERE organization_id=?)",
            (org_id,),
        )
        conn.execute("DELETE FROM wrong_question_submissions WHERE organization_id=?", (org_id,))
        conn.execute("DELETE FROM parent_student_bindings WHERE organization_id=?", (org_id,))
        conn.execute("DELETE FROM students WHERE organization_id=?", (org_id,))
        # 3. classes
        conn.execute("DELETE FROM classes WHERE organization_id=?", (org_id,))
        # 4. consultations
        conn.execute("DELETE FROM consultations WHERE organization_id=?", (org_id,))
        # 5. registration_requests
        conn.execute("DELETE FROM registration_requests WHERE organization_id=?", (org_id,))
        # 6. organization_invites
        conn.execute("DELETE FROM organization_invites WHERE organization_id=?", (org_id,))
        # 7. auth_sessions (via users)
        conn.execute(
            "DELETE FROM auth_sessions WHERE user_id IN (SELECT id FROM users WHERE organization_id=?)",
            (org_id,),
        )
        # 8. user_classes (via users)
        conn.execute(
            "DELETE FROM user_classes WHERE user_id IN (SELECT id FROM users WHERE organization_id=?)",
            (org_id,),
        )
        # 9. ai_usage_ledger (via users, ON DELETE CASCADE but explicit for safety)
        conn.execute("DELETE FROM ai_usage_ledger WHERE organization_id=?", (org_id,))
        # 10. credit ledger and accounts (ON DELETE CASCADE but explicit)
        conn.execute("DELETE FROM organization_credit_ledger WHERE organization_id=?", (org_id,))
        conn.execute("DELETE FROM organization_credit_accounts WHERE organization_id=?", (org_id,))
        # 11. nullify xhs_order_redemptions references (nullable FK, no cascade)
        conn.execute(
            "UPDATE xhs_order_redemptions SET redeemed_organization_id=NULL WHERE redeemed_organization_id=?",
            (org_id,),
        )
        # 12. users
        conn.execute("DELETE FROM users WHERE organization_id=?", (org_id,))
        # 13. organization
        conn.execute("DELETE FROM organizations WHERE id=?", (org_id,))
        return {
            "action": "deleted",
            "organization_id": org_id,
            "memory_cleanup": None,
        }


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
                c.grade AS class_grade,
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


WECHAT_WRONG_QUESTION_UPLOAD_TASK_STATUSES = {"pending", "processing", "ready", "failed"}


def create_wechat_wrong_question_upload_task(
    *,
    binding_id: int,
    image_url: str,
    child_raw_reason_text: str,
    child_reason_input_mode: str = "text",
    child_reason_audio_url: str = "",
    topic_category: str = PRIMARY_WRONG_QUESTION_TOPIC_UNCLASSIFIED,
) -> dict:
    normalized_image_url = (image_url or "").strip()
    if not normalized_image_url:
        raise ValueError("image_url is required")
    normalized_reason_text = (child_raw_reason_text or "").strip()
    normalized_reason_input_mode = ((child_reason_input_mode or "text").strip() or "text").lower()
    if normalized_reason_input_mode not in WECHAT_CHILD_REASON_INPUT_MODES:
        raise ValueError("child_reason_input_mode must be text or voice")
    normalized_topic_category = normalize_primary_wrong_question_topic_category(topic_category)

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

        cursor = conn.execute(
            """
            INSERT INTO wechat_wrong_question_upload_tasks (
                organization_id, parent_wechat_account_id, binding_id,
                class_id, student_id, teacher_user_id, image_url,
                child_raw_reason_text, child_reason_input_mode, child_reason_audio_url,
                topic_category,
                status, ingestion_run_id, record_id, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', '', '', '')
            """,
            (
                binding_row["organization_id"],
                binding_row["parent_wechat_account_id"],
                binding_id,
                binding_row["class_id"],
                binding_row["student_id"],
                binding_row["teacher_user_id"],
                normalized_image_url,
                normalized_reason_text,
                normalized_reason_input_mode,
                (child_reason_audio_url or "").strip(),
                normalized_topic_category,
            ),
        )
        created = conn.execute(
            "SELECT * FROM wechat_wrong_question_upload_tasks WHERE id=?",
            (cursor.lastrowid,),
        ).fetchone()
    return dict(created) if created else {}


def get_wechat_wrong_question_upload_task(task_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM wechat_wrong_question_upload_tasks WHERE id=?",
            (int(task_id or 0),),
        ).fetchone()
    return dict(row) if row else None


def get_wechat_wrong_question_upload_task_for_openid(task_id: int, open_id: str) -> Optional[dict]:
    normalized_openid = (open_id or "").strip()
    if not normalized_openid:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT task.*
            FROM wechat_wrong_question_upload_tasks task
            JOIN parent_wechat_accounts pwa ON pwa.id = task.parent_wechat_account_id
            WHERE task.id=? AND pwa.openid=?
            """,
            (int(task_id or 0), normalized_openid),
        ).fetchone()
    return dict(row) if row else None


def update_wechat_wrong_question_upload_task(
    task_id: int,
    *,
    status: str,
    ingestion_run_id: str | None = None,
    record_id: str = "",
    error_message: str = "",
    retryable: Optional[bool] = None,
) -> Optional[dict]:
    normalized_status = (status or "").strip()
    if normalized_status not in WECHAT_WRONG_QUESTION_UPLOAD_TASK_STATUSES:
        raise ValueError("upload task status is invalid")

    with get_conn() as conn:
        assignments = [
            "status=?",
            "record_id=?",
            "error_message=?",
        ]
        params: list[object] = [
            normalized_status,
            (record_id or "").strip(),
            (error_message or "").strip(),
        ]
        if ingestion_run_id is not None:
            assignments.append("ingestion_run_id=?")
            params.append((ingestion_run_id or "").strip())
        if retryable is not None:
            assignments.append("retryable=?")
            params.append(1 if retryable else 0)
        conn.execute(
            f"""
            UPDATE wechat_wrong_question_upload_tasks
            SET {", ".join(assignments)},
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (*params, int(task_id or 0)),
        )
        refreshed = conn.execute(
            "SELECT * FROM wechat_wrong_question_upload_tasks WHERE id=?",
            (int(task_id or 0),),
        ).fetchone()
    return dict(refreshed) if refreshed else None


def create_wrong_question_ingestion_run(
    *,
    organization_id: int,
    source: str = "workspace",
    class_id: int | None = None,
    student_id: int | None = None,
    teacher_user_id: int | None = None,
    parent_wechat_account_id: int | None = None,
    chat_session_id: str = "",
    status: str = "pending",
    current_step: str = "",
    original_filename: str = "",
    mime_type: str = "",
    error_message: str = "",
    metadata_json: object = None,
) -> dict:
    normalized_source = (source or "workspace").strip() or "workspace"
    normalized_status = (status or "pending").strip() or "pending"
    normalized_current_step = (current_step or "").strip() or {
        "pending": "uploaded",
        "processing": "processing",
        "ocr_ready": "ocr_completed",
        "split_ready": "split_completed",
        "archived": "archived",
        "failed": "failed",
    }.get(normalized_status, "uploaded")
    record_id = f"wqrun-{secrets.token_hex(8)}"
    normalized_metadata_json = _normalize_json_storage_value(
        metadata_json,
        field_name="metadata_json",
        default="{}",
    )

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO wrong_question_ingestion_runs (
                id, organization_id, source, class_id, student_id, teacher_user_id,
                parent_wechat_account_id, chat_session_id, status, current_step, original_filename,
                mime_type, error_message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                int(organization_id or 0),
                normalized_source,
                int(class_id) if class_id is not None else None,
                int(student_id) if student_id is not None else None,
                int(teacher_user_id) if teacher_user_id is not None else None,
                int(parent_wechat_account_id) if parent_wechat_account_id is not None else None,
                (chat_session_id or "").strip(),
                normalized_status,
                normalized_current_step,
                (original_filename or "").strip(),
                (mime_type or "").strip(),
                (error_message or "").strip(),
                normalized_metadata_json,
            ),
        )
        created = conn.execute(
            "SELECT * FROM wrong_question_ingestion_runs WHERE id=?",
            (record_id,),
        ).fetchone()
    return dict(created) if created else {}


def get_wrong_question_ingestion_run(run_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM wrong_question_ingestion_runs WHERE id=?",
            ((run_id or "").strip(),),
        ).fetchone()
    return dict(row) if row else None


def update_wrong_question_ingestion_run(
    run_id: str,
    *,
    status: str | None = None,
    current_step: str | None = None,
    chat_session_id: str | None = None,
    error_message: str | None = None,
    metadata_json: object = None,
) -> Optional[dict]:
    assignments: list[str] = []
    params: list[object] = []
    if status is not None:
        assignments.append("status=?")
        params.append((status or "pending").strip() or "pending")
    if current_step is not None:
        assignments.append("current_step=?")
        params.append((current_step or "").strip() or "uploaded")
    if chat_session_id is not None:
        assignments.append("chat_session_id=?")
        params.append((chat_session_id or "").strip())
    if error_message is not None:
        assignments.append("error_message=?")
        params.append((error_message or "").strip())
    if metadata_json is not None:
        assignments.append("metadata_json=?")
        params.append(
            _normalize_json_storage_value(
                metadata_json,
                field_name="metadata_json",
                default="{}",
            )
        )
    if not assignments:
        return get_wrong_question_ingestion_run(run_id)

    with get_conn() as conn:
        conn.execute(
            f"""
            UPDATE wrong_question_ingestion_runs
            SET {", ".join(assignments)},
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (*params, (run_id or "").strip()),
        )
        refreshed = conn.execute(
            "SELECT * FROM wrong_question_ingestion_runs WHERE id=?",
            ((run_id or "").strip(),),
        ).fetchone()
    return dict(refreshed) if refreshed else None


def list_wrong_question_ingestion_runs(
    *,
    organization_id: int,
    source: str | None = None,
    status: str | None = None,
    class_id: int | None = None,
    student_id: int | None = None,
    teacher_user_id: int | None = None,
    chat_session_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    normalized_limit = max(1, min(int(limit or 50), 200))
    where_clauses = ["organization_id=?"]
    params: list[object] = [int(organization_id or 0)]
    if source is not None and str(source).strip():
        where_clauses.append("source=?")
        params.append(str(source).strip())
    if status is not None and str(status).strip():
        where_clauses.append("status=?")
        params.append(str(status).strip())
    if class_id is not None:
        where_clauses.append("class_id=?")
        params.append(int(class_id))
    if student_id is not None:
        where_clauses.append("student_id=?")
        params.append(int(student_id))
    if teacher_user_id is not None:
        where_clauses.append("teacher_user_id=?")
        params.append(int(teacher_user_id))
    if chat_session_id is not None and str(chat_session_id).strip():
        where_clauses.append("chat_session_id=?")
        params.append(str(chat_session_id).strip())

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM wrong_question_ingestion_runs
            WHERE {" AND ".join(where_clauses)}
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT ?
            """,
            (*params, normalized_limit),
        ).fetchall()
    return [dict(row) for row in rows]


def create_wrong_question_asset(
    *,
    ingestion_run_id: str,
    asset_role: str,
    storage_path: str = "",
    file_url: str = "",
    mime_type: str = "",
    page_number: int = 0,
    width: int = 0,
    height: int = 0,
    metadata_json: object = None,
) -> dict:
    normalized_run_id = (ingestion_run_id or "").strip()
    if not normalized_run_id:
        raise ValueError("ingestion_run_id is required")
    normalized_asset_role = (asset_role or "").strip()
    if not normalized_asset_role:
        raise ValueError("asset_role is required")
    normalized_metadata_json = _normalize_json_storage_value(
        metadata_json,
        field_name="metadata_json",
        default="{}",
    )

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO wrong_question_assets (
                ingestion_run_id, asset_role, storage_path, file_url, mime_type,
                page_number, width, height, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_run_id,
                normalized_asset_role,
                (storage_path or "").strip(),
                (file_url or "").strip(),
                (mime_type or "").strip(),
                int(page_number or 0),
                int(width or 0),
                int(height or 0),
                normalized_metadata_json,
            ),
        )
        created = conn.execute(
            "SELECT * FROM wrong_question_assets WHERE id=last_insert_rowid()",
        ).fetchone()
    return dict(created) if created else {}


def list_wrong_question_assets(ingestion_run_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM wrong_question_assets
            WHERE ingestion_run_id=?
            ORDER BY page_number ASC, id ASC
            """,
            ((ingestion_run_id or "").strip(),),
        ).fetchall()
    return [dict(row) for row in rows]


def _resolve_erased_wrong_question_image_url_for_record(
    conn: sqlite3.Connection,
    record: dict,
) -> str:
    for key in ("erased_image_url", "erased_image_url_snapshot", "clean_image_url"):
        direct_url = str(record.get(key) or "").strip()
        if direct_url:
            return direct_url

    ingestion_run_id = str(record.get("ingestion_run_id") or "").strip()
    if not ingestion_run_id:
        return ""

    row = conn.execute(
        """
        SELECT file_url, storage_path
        FROM wrong_question_assets
        WHERE ingestion_run_id=?
          AND asset_role IN ('erased_question_image', 'erased_upload', 'erased_image')
        ORDER BY page_number ASC, id DESC
        LIMIT 1
        """,
        (ingestion_run_id,),
    ).fetchone()
    if not row:
        return ""
    return str(row["file_url"] or row["storage_path"] or "").strip()


def create_wrong_question_chat_session(
    *,
    session_id: str,
    organization_id: int,
    ingestion_run_id: str = "",
    class_id: int | None = None,
    student_id: int | None = None,
    teacher_user_id: int | None = None,
    status: str = "active",
    current_stage: str = "ask_why_wrong",
    summary_text: str = "",
    metadata_json: object = None,
) -> dict:
    normalized_session_id = (session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("session_id is required")
    normalized_metadata_json = _normalize_json_storage_value(
        metadata_json,
        field_name="metadata_json",
        default="{}",
    )
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO wrong_question_chat_sessions (
                id, organization_id, ingestion_run_id, class_id, student_id,
                teacher_user_id, status, current_stage, summary_text, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_session_id,
                int(organization_id or 0),
                (ingestion_run_id or "").strip(),
                int(class_id) if class_id is not None else None,
                int(student_id) if student_id is not None else None,
                int(teacher_user_id) if teacher_user_id is not None else None,
                (status or "active").strip() or "active",
                (current_stage or "ask_why_wrong").strip() or "ask_why_wrong",
                (summary_text or "").strip(),
                normalized_metadata_json,
            ),
        )
        created = conn.execute(
            "SELECT * FROM wrong_question_chat_sessions WHERE id=?",
            (normalized_session_id,),
        ).fetchone()
    return dict(created) if created else {}


def get_wrong_question_chat_session(session_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM wrong_question_chat_sessions WHERE id=?",
            ((session_id or "").strip(),),
        ).fetchone()
    return dict(row) if row else None


def update_wrong_question_chat_session(
    session_id: str,
    *,
    ingestion_run_id: str | None = None,
    status: str | None = None,
    current_stage: str | None = None,
    summary_text: str | None = None,
    metadata_json: object = None,
) -> Optional[dict]:
    assignments: list[str] = []
    params: list[object] = []
    if ingestion_run_id is not None:
        assignments.append("ingestion_run_id=?")
        params.append((ingestion_run_id or "").strip())
    if status is not None:
        assignments.append("status=?")
        params.append((status or "active").strip() or "active")
    if current_stage is not None:
        assignments.append("current_stage=?")
        params.append((current_stage or "ask_why_wrong").strip() or "ask_why_wrong")
    if summary_text is not None:
        assignments.append("summary_text=?")
        params.append((summary_text or "").strip())
    if metadata_json is not None:
        assignments.append("metadata_json=?")
        params.append(
            _normalize_json_storage_value(
                metadata_json,
                field_name="metadata_json",
                default="{}",
            )
        )
    if not assignments:
        return get_wrong_question_chat_session(session_id)

    with get_conn() as conn:
        conn.execute(
            f"""
            UPDATE wrong_question_chat_sessions
            SET {", ".join(assignments)},
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (*params, (session_id or "").strip()),
        )
        refreshed = conn.execute(
            "SELECT * FROM wrong_question_chat_sessions WHERE id=?",
            ((session_id or "").strip(),),
        ).fetchone()
    return dict(refreshed) if refreshed else None


def create_wrong_question_chat_message(
    *,
    session_id: str,
    role: str,
    content: str,
    stage: str = "",
    metadata_json: object = None,
) -> dict:
    normalized_session_id = (session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("session_id is required")
    normalized_role = (role or "").strip().lower()
    if normalized_role not in {"user", "assistant", "system"}:
        raise ValueError("role must be user, assistant or system")
    normalized_content = (content or "").strip()
    if not normalized_content:
        raise ValueError("content is required")
    normalized_metadata_json = _normalize_json_storage_value(
        metadata_json,
        field_name="metadata_json",
        default="{}",
    )

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO wrong_question_chat_messages (
                session_id, role, stage, content, metadata_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                normalized_session_id,
                normalized_role,
                (stage or "").strip(),
                normalized_content,
                normalized_metadata_json,
            ),
        )
        created = conn.execute(
            "SELECT * FROM wrong_question_chat_messages WHERE id=last_insert_rowid()",
        ).fetchone()
    return dict(created) if created else {}


def list_wrong_question_chat_messages(session_id: str) -> list[dict]:
    normalized_session_id = (session_id or "").strip()
    if not normalized_session_id:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM wrong_question_chat_messages
            WHERE session_id=?
            ORDER BY id ASC
            """,
            (normalized_session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def _normalize_wrong_question_submission_fields(
    *,
    image_url: str,
    child_raw_reason_text: str = "",
    child_reason_transcript: str = "",
    child_reason_input_mode: str = "text",
    primary_error_type: str = "",
    secondary_error_summary: str = "",
    child_reason_core_issue: str = "",
    child_reason_key_omission: str = "",
    child_reason_next_step: str = "",
    topic_category: str = PRIMARY_WRONG_QUESTION_TOPIC_UNCLASSIFIED,
    recognition_status: str = "pending",
    is_geometry: bool = False,
    image_rotation_degrees: int = 0,
    question_text: str = "",
    question_text_source: str = "ai",
    diagram_type: str = "",
    diagram_spec: dict | None = None,
    diagram_spec_json: str = "",
    recognition_error: str = "",
    student_library_pdf_path: str = "",
    ingestion_run_id: str = "",
    chat_session_id: str = "",
    question_structured_json: object = None,
    knowledge_tags_json: object = None,
    reflection_summary_json: object = None,
    generation_metadata_json: object = None,
    needs_teacher_confirmation: bool = False,
    confirmation_reasons_json: object = None,
) -> dict:
    normalized_image_url = (image_url or "").strip()
    if not normalized_image_url:
        raise ValueError("image_url is required")
    normalized_reason_input_mode = ((child_reason_input_mode or "text").strip() or "text").lower()
    if normalized_reason_input_mode not in WECHAT_CHILD_REASON_INPUT_MODES:
        raise ValueError("child_reason_input_mode must be text or voice")
    normalized_topic_category = normalize_primary_wrong_question_topic_category(topic_category)
    try:
        normalized_image_rotation_degrees = int(image_rotation_degrees or 0)
    except (TypeError, ValueError):
        normalized_image_rotation_degrees = 0
    if normalized_image_rotation_degrees not in {0, 90, 180, 270}:
        normalized_image_rotation_degrees = 0
    normalized_diagram_type = str(diagram_type or "").strip()
    normalized_diagram_spec_json = str(diagram_spec_json or "").strip()
    if diagram_spec is not None:
        if isinstance(diagram_spec, dict) and diagram_spec:
            normalized_diagram_spec_json = json.dumps(diagram_spec, ensure_ascii=False, separators=(",", ":"))
            if not normalized_diagram_type:
                normalized_diagram_type = str(diagram_spec.get("type") or "").strip()
        else:
            normalized_diagram_spec_json = ""
    elif normalized_diagram_spec_json:
        try:
            parsed_diagram_spec = json.loads(normalized_diagram_spec_json)
        except json.JSONDecodeError:
            normalized_diagram_spec_json = ""
        else:
            if isinstance(parsed_diagram_spec, dict):
                normalized_diagram_spec_json = json.dumps(parsed_diagram_spec, ensure_ascii=False, separators=(",", ":"))
                if not normalized_diagram_type:
                    normalized_diagram_type = str(parsed_diagram_spec.get("type") or "").strip()
            else:
                normalized_diagram_spec_json = ""
    return {
        "image_url": normalized_image_url,
        "child_raw_reason_text": (child_raw_reason_text or "").strip(),
        "child_reason_transcript": (child_reason_transcript or child_raw_reason_text or "").strip(),
        "child_reason_input_mode": normalized_reason_input_mode,
        "primary_error_type": (primary_error_type or "").strip(),
        "secondary_error_summary": (secondary_error_summary or "").strip(),
        "child_reason_core_issue": (child_reason_core_issue or "").strip(),
        "child_reason_key_omission": (child_reason_key_omission or "").strip(),
        "child_reason_next_step": (child_reason_next_step or "").strip(),
        "topic_category": normalized_topic_category,
        "recognition_status": (recognition_status or "pending").strip() or "pending",
        "is_geometry": 1 if is_geometry else 0,
        "image_rotation_degrees": normalized_image_rotation_degrees,
        "question_text": (question_text or "").strip(),
        "question_text_source": (question_text_source or "ai").strip() or "ai",
        "diagram_type": normalized_diagram_type,
        "diagram_spec_json": normalized_diagram_spec_json,
        "recognition_error": (recognition_error or "").strip(),
        "student_library_pdf_path": (student_library_pdf_path or "").strip(),
        "ingestion_run_id": (ingestion_run_id or "").strip(),
        "chat_session_id": (chat_session_id or "").strip(),
        "question_structured_json": _normalize_json_storage_value(
            question_structured_json,
            field_name="question_structured_json",
            default="",
        ),
        "knowledge_tags_json": _normalize_json_storage_value(
            knowledge_tags_json,
            field_name="knowledge_tags_json",
            default="[]",
        ),
        "reflection_summary_json": _normalize_json_storage_value(
            reflection_summary_json,
            field_name="reflection_summary_json",
            default="{}",
        ),
        "generation_metadata_json": _normalize_json_storage_value(
            generation_metadata_json,
            field_name="generation_metadata_json",
            default="{}",
        ),
        "mastery_tracking_json": "{}",
        "needs_teacher_confirmation": 1 if needs_teacher_confirmation else 0,
        "confirmation_reasons_json": _normalize_json_storage_value(
            confirmation_reasons_json,
            field_name="confirmation_reasons_json",
            default="[]",
        ),
    }


def _create_wrong_question_submission_record(
    conn: sqlite3.Connection,
    *,
    source: str,
    organization_id: int,
    parent_wechat_account_id: int | None,
    binding_id: int | None,
    class_id: int,
    student_id: int,
    teacher_user_id: int,
    normalized_payload: dict,
) -> dict:
    source_prefix = {
        "wechat_mp": "wechat",
        "workspace": "workspace",
        "ai_chat": "aichat",
    }.get(source, "wq")
    record_id = f"{source_prefix}-{secrets.token_hex(8)}"
    conn.execute(
        """
        INSERT INTO wrong_question_submissions (
            id, organization_id, source, parent_wechat_account_id, binding_id,
            class_id, student_id, teacher_user_id, image_url,
            child_raw_reason_text, child_reason_transcript, child_reason_input_mode,
            primary_error_type, secondary_error_summary,
            child_reason_core_issue, child_reason_key_omission, child_reason_next_step,
            topic_category, archive_status, status,
            recognition_status, is_geometry, image_rotation_degrees, question_text, question_text_edited,
            question_text_source, diagram_type, diagram_spec_json, recognition_error, student_library_pdf_path,
            ingestion_run_id, chat_session_id, question_structured_json, knowledge_tags_json, reflection_summary_json, generation_metadata_json, mastery_tracking_json,
            needs_teacher_confirmation, confirmation_reasons_json,
            confirmation_status, confirmation_reviewed_by, confirmation_reviewed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 'pending', ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            int(organization_id or 0),
            source,
            int(parent_wechat_account_id) if parent_wechat_account_id is not None else None,
            int(binding_id) if binding_id is not None else None,
            int(class_id or 0),
            int(student_id or 0),
            int(teacher_user_id or 0),
            normalized_payload["image_url"],
            normalized_payload["child_raw_reason_text"],
            normalized_payload["child_reason_transcript"],
            normalized_payload["child_reason_input_mode"],
            normalized_payload["primary_error_type"],
            normalized_payload["secondary_error_summary"],
            normalized_payload["child_reason_core_issue"],
            normalized_payload["child_reason_key_omission"],
            normalized_payload["child_reason_next_step"],
            normalized_payload["topic_category"],
            normalized_payload["recognition_status"],
            normalized_payload["is_geometry"],
            normalized_payload["image_rotation_degrees"],
            normalized_payload["question_text"],
            normalized_payload["question_text_source"],
            normalized_payload["diagram_type"],
            normalized_payload["diagram_spec_json"],
            normalized_payload["recognition_error"],
            normalized_payload["student_library_pdf_path"],
            normalized_payload["ingestion_run_id"],
            normalized_payload["chat_session_id"],
            normalized_payload["question_structured_json"],
            normalized_payload["knowledge_tags_json"],
            normalized_payload["reflection_summary_json"],
            normalized_payload["generation_metadata_json"],
            normalized_payload["mastery_tracking_json"],
            normalized_payload["needs_teacher_confirmation"],
            normalized_payload["confirmation_reasons_json"],
            "pending" if normalized_payload["needs_teacher_confirmation"] else "not_required",
            None,
            "",
        ),
    )
    created = conn.execute(
        "SELECT * FROM wrong_question_submissions WHERE id=?",
        (record_id,),
    ).fetchone()
    return dict(created) if created else {}


def create_wrong_question_submission(
    *,
    source: str,
    image_url: str,
    organization_id: int | None = None,
    parent_wechat_account_id: int | None = None,
    binding_id: int | None = None,
    class_id: int | None = None,
    student_id: int | None = None,
    teacher_user_id: int | None = None,
    child_raw_reason_text: str = "",
    child_reason_transcript: str = "",
    child_reason_input_mode: str = "text",
    primary_error_type: str = "",
    secondary_error_summary: str = "",
    child_reason_core_issue: str = "",
    child_reason_key_omission: str = "",
    child_reason_next_step: str = "",
    topic_category: str = PRIMARY_WRONG_QUESTION_TOPIC_UNCLASSIFIED,
    recognition_status: str = "pending",
    is_geometry: bool = False,
    image_rotation_degrees: int = 0,
    question_text: str = "",
    question_text_source: str = "ai",
    diagram_type: str = "",
    diagram_spec: dict | None = None,
    diagram_spec_json: str = "",
    recognition_error: str = "",
    student_library_pdf_path: str = "",
    ingestion_run_id: str = "",
    chat_session_id: str = "",
    question_structured_json: object = None,
    knowledge_tags_json: object = None,
    reflection_summary_json: object = None,
    generation_metadata_json: object = None,
    needs_teacher_confirmation: bool = False,
    confirmation_reasons_json: object = None,
) -> dict:
    normalized_source = (source or "wechat_mp").strip() or "wechat_mp"
    normalized_payload = _normalize_wrong_question_submission_fields(
        image_url=image_url,
        child_raw_reason_text=child_raw_reason_text,
        child_reason_transcript=child_reason_transcript,
        child_reason_input_mode=child_reason_input_mode,
        primary_error_type=primary_error_type,
        secondary_error_summary=secondary_error_summary,
        child_reason_core_issue=child_reason_core_issue,
        child_reason_key_omission=child_reason_key_omission,
        child_reason_next_step=child_reason_next_step,
        topic_category=topic_category,
        recognition_status=recognition_status,
        is_geometry=is_geometry,
        image_rotation_degrees=image_rotation_degrees,
        question_text=question_text,
        question_text_source=question_text_source,
        diagram_type=diagram_type,
        diagram_spec=diagram_spec,
        diagram_spec_json=diagram_spec_json,
        recognition_error=recognition_error,
        student_library_pdf_path=student_library_pdf_path,
        ingestion_run_id=ingestion_run_id,
        chat_session_id=chat_session_id,
        question_structured_json=question_structured_json,
        knowledge_tags_json=knowledge_tags_json,
        reflection_summary_json=reflection_summary_json,
        generation_metadata_json=generation_metadata_json,
        needs_teacher_confirmation=needs_teacher_confirmation,
        confirmation_reasons_json=confirmation_reasons_json,
    )

    with get_conn() as conn:
        if normalized_source == "wechat_mp":
            if binding_id is None:
                raise ValueError("binding_id is required for wechat_mp source")
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
            return _create_wrong_question_submission_record(
                conn,
                source=normalized_source,
                organization_id=int(binding_row["organization_id"]),
                parent_wechat_account_id=int(binding_row["parent_wechat_account_id"]),
                binding_id=int(binding_row["id"]),
                class_id=int(binding_row["class_id"]),
                student_id=int(binding_row["student_id"]),
                teacher_user_id=int(binding_row["teacher_user_id"]),
                normalized_payload=normalized_payload,
            )

        required_field_values = {
            "organization_id": organization_id,
            "class_id": class_id,
            "student_id": student_id,
            "teacher_user_id": teacher_user_id,
        }
        missing_fields = [field_name for field_name, field_value in required_field_values.items() if field_value is None]
        if missing_fields:
            raise ValueError(f"missing required fields for {normalized_source} source: {', '.join(missing_fields)}")
        return _create_wrong_question_submission_record(
            conn,
            source=normalized_source,
            organization_id=int(organization_id or 0),
            parent_wechat_account_id=parent_wechat_account_id,
            binding_id=binding_id,
            class_id=int(class_id or 0),
            student_id=int(student_id or 0),
            teacher_user_id=int(teacher_user_id or 0),
            normalized_payload=normalized_payload,
        )


def create_wechat_wrong_question_submission(
    *,
    binding_id: int,
    image_url: str,
    child_raw_reason_text: str = "",
    child_reason_transcript: str = "",
    child_reason_input_mode: str = "text",
    primary_error_type: str = "",
    secondary_error_summary: str = "",
    child_reason_core_issue: str = "",
    child_reason_key_omission: str = "",
    child_reason_next_step: str = "",
    topic_category: str = PRIMARY_WRONG_QUESTION_TOPIC_UNCLASSIFIED,
    recognition_status: str = "pending",
    is_geometry: bool = False,
    image_rotation_degrees: int = 0,
    question_text: str = "",
    question_text_source: str = "ai",
    diagram_type: str = "",
    diagram_spec: dict | None = None,
    diagram_spec_json: str = "",
    recognition_error: str = "",
    student_library_pdf_path: str = "",
    ingestion_run_id: str = "",
    chat_session_id: str = "",
    question_structured_json: object = None,
    knowledge_tags_json: object = None,
    reflection_summary_json: object = None,
    generation_metadata_json: object = None,
    needs_teacher_confirmation: bool = False,
    confirmation_reasons_json: object = None,
) -> dict:
    return create_wrong_question_submission(
        source="wechat_mp",
        binding_id=binding_id,
        image_url=image_url,
        child_raw_reason_text=child_raw_reason_text,
        child_reason_transcript=child_reason_transcript,
        child_reason_input_mode=child_reason_input_mode,
        primary_error_type=primary_error_type,
        secondary_error_summary=secondary_error_summary,
        child_reason_core_issue=child_reason_core_issue,
        child_reason_key_omission=child_reason_key_omission,
        child_reason_next_step=child_reason_next_step,
        topic_category=topic_category,
        recognition_status=recognition_status,
        is_geometry=is_geometry,
        image_rotation_degrees=image_rotation_degrees,
        question_text=question_text,
        question_text_source=question_text_source,
        diagram_type=diagram_type,
        diagram_spec=diagram_spec,
        diagram_spec_json=diagram_spec_json,
        recognition_error=recognition_error,
        student_library_pdf_path=student_library_pdf_path,
        ingestion_run_id=ingestion_run_id,
        chat_session_id=chat_session_id,
        question_structured_json=question_structured_json,
        knowledge_tags_json=knowledge_tags_json,
        reflection_summary_json=reflection_summary_json,
        generation_metadata_json=generation_metadata_json,
        needs_teacher_confirmation=needs_teacher_confirmation,
        confirmation_reasons_json=confirmation_reasons_json,
    )


def update_wrong_question_submission_from_chat_archive(
    record_id: str,
    *,
    chat_session_id: str | None = None,
    child_raw_reason_text: str | None = None,
    child_reason_transcript: str | None = None,
    child_reason_core_issue: str | None = None,
    child_reason_next_step: str | None = None,
    topic_category: str | None = None,
    question_text: str | None = None,
    question_text_source: str | None = None,
    question_structured_json: object = None,
    knowledge_tags_json: object = None,
    reflection_summary_json: object = None,
    generation_metadata_json: object = None,
    needs_teacher_confirmation: bool | None = None,
    confirmation_reasons_json: object = None,
    preserve_existing_confirmation_review: bool = False,
) -> Optional[dict]:
    with get_conn() as conn:
        row = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        if not row:
            return None

        next_chat_session_id = (
            str(chat_session_id).strip()
            if chat_session_id is not None
            else str(row["chat_session_id"] or "").strip()
        )
        next_child_raw_reason_text = (
            str(child_raw_reason_text).strip()
            if child_raw_reason_text is not None
            else str(row["child_raw_reason_text"] or "").strip()
        )
        next_child_reason_transcript = (
            str(child_reason_transcript).strip()
            if child_reason_transcript is not None
            else str(row["child_reason_transcript"] or "").strip()
        )
        next_child_reason_core_issue = (
            str(child_reason_core_issue).strip()
            if child_reason_core_issue is not None
            else str(row["child_reason_core_issue"] or "").strip()
        )
        next_child_reason_next_step = (
            str(child_reason_next_step).strip()
            if child_reason_next_step is not None
            else str(row["child_reason_next_step"] or "").strip()
        )
        next_topic_category = normalize_primary_wrong_question_topic_category(
            topic_category if topic_category is not None else str(row["topic_category"] or "")
        )
        next_question_text = (
            str(question_text).strip()
            if question_text is not None
            else str(row["question_text"] or "").strip()
        )
        next_question_text_source = (
            str(question_text_source).strip()
            if question_text_source is not None
            else str(row["question_text_source"] or "").strip()
        ) or "ai"
        next_question_structured_json = (
            _normalize_json_storage_value(
                question_structured_json,
                field_name="question_structured_json",
                default="",
            )
            if question_structured_json is not None
            else str(row["question_structured_json"] or "")
        )
        next_knowledge_tags_json = (
            _normalize_json_storage_value(
                knowledge_tags_json,
                field_name="knowledge_tags_json",
                default="[]",
            )
            if knowledge_tags_json is not None
            else str(row["knowledge_tags_json"] or "[]")
        )
        next_reflection_summary_json = (
            _normalize_json_storage_value(
                reflection_summary_json,
                field_name="reflection_summary_json",
                default="{}",
            )
            if reflection_summary_json is not None
            else str(row["reflection_summary_json"] or "{}")
        )
        next_generation_metadata_json = (
            _normalize_json_storage_value(
                generation_metadata_json,
                field_name="generation_metadata_json",
                default="{}",
            )
            if generation_metadata_json is not None
            else str(row["generation_metadata_json"] or "{}")
        )
        next_confirmation_state = (
            bool(needs_teacher_confirmation)
            if needs_teacher_confirmation is not None
            else bool(row["needs_teacher_confirmation"])
        )
        next_confirmation_reasons_json = (
            _normalize_json_storage_value(
                confirmation_reasons_json,
                field_name="confirmation_reasons_json",
                default="[]",
            )
            if confirmation_reasons_json is not None
            else str(row["confirmation_reasons_json"] or "[]")
        )
        if not next_confirmation_state:
            next_confirmation_reasons_json = "[]"

        next_confirmation_status = str(row["confirmation_status"] or "").strip()
        if next_confirmation_status not in {"pending", "confirmed", "returned", "not_required"}:
            if bool(row["needs_teacher_confirmation"]):
                next_confirmation_status = "pending"
            elif row["confirmation_reviewed_by"] is not None or str(row["confirmation_reviewed_at"] or "").strip():
                next_confirmation_status = "confirmed"
            else:
                next_confirmation_status = "not_required"
        next_confirmation_reviewed_by = row["confirmation_reviewed_by"]
        next_confirmation_reviewed_at = str(row["confirmation_reviewed_at"] or "").strip()

        if next_confirmation_state:
            next_confirmation_status = "pending"
            next_confirmation_reviewed_by = None
            next_confirmation_reviewed_at = ""
        elif preserve_existing_confirmation_review and next_confirmation_status in {"confirmed", "not_required"}:
            next_confirmation_status = next_confirmation_status
        else:
            next_confirmation_status = "not_required"
            next_confirmation_reviewed_by = None
            next_confirmation_reviewed_at = ""

        conn.execute(
            """
            UPDATE wrong_question_submissions
            SET chat_session_id=?,
                child_raw_reason_text=?,
                child_reason_transcript=?,
                child_reason_core_issue=?,
                child_reason_next_step=?,
                topic_category=?,
                question_text=?,
                question_text_source=?,
                question_structured_json=?,
                knowledge_tags_json=?,
                reflection_summary_json=?,
                generation_metadata_json=?,
                needs_teacher_confirmation=?,
                confirmation_reasons_json=?,
                confirmation_status=?,
                confirmation_reviewed_by=?,
                confirmation_reviewed_at=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (
                next_chat_session_id,
                next_child_raw_reason_text,
                next_child_reason_transcript,
                next_child_reason_core_issue,
                next_child_reason_next_step,
                next_topic_category,
                next_question_text,
                next_question_text_source,
                next_question_structured_json,
                next_knowledge_tags_json,
                next_reflection_summary_json,
                next_generation_metadata_json,
                1 if next_confirmation_state else 0,
                next_confirmation_reasons_json,
                next_confirmation_status,
                next_confirmation_reviewed_by,
                next_confirmation_reviewed_at,
                record_id,
            ),
        )
        refreshed = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        return _serialize_wechat_wrong_question_submission_row(conn, refreshed)


WRONG_QUESTION_MASTERY_FOLLOWUP_OUTCOMES = {
    "still_confused",
    "needs_another_practice",
    "likely_mastered",
}
WRONG_QUESTION_MASTERY_TRACKING_FOLLOWUP_KEYS = (
    "followup_count",
    "latest_followup_session_id",
    "latest_followup_outcome",
    "latest_followup_completed_at",
    "latest_followup_summary",
)


def _normalize_wrong_question_mastery_followup_outcome(value: object) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized in WRONG_QUESTION_MASTERY_FOLLOWUP_OUTCOMES else ""


def _load_wrong_question_mastery_tracking_dict(raw_tracking: object) -> dict:
    if isinstance(raw_tracking, dict):
        return dict(raw_tracking)
    if isinstance(raw_tracking, str):
        try:
            parsed = json.loads(raw_tracking or "{}")
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _preserve_wrong_question_mastery_followup_tracking(existing_tracking: dict) -> dict:
    preserved: dict[str, object] = {}
    if not isinstance(existing_tracking, dict):
        return preserved
    for key in WRONG_QUESTION_MASTERY_TRACKING_FOLLOWUP_KEYS:
        if key in existing_tracking:
            preserved[key] = existing_tracking[key]
    return preserved


def update_wrong_question_submission_mastery_followup(
    record_id: str,
    *,
    session_id: str,
    outcome: str,
    summary_text: str,
) -> Optional[dict]:
    normalized_record_id = str(record_id or "").strip()
    normalized_session_id = str(session_id or "").strip()
    normalized_outcome = _normalize_wrong_question_mastery_followup_outcome(outcome)
    if not normalized_record_id or not normalized_session_id or not normalized_outcome:
        return None

    with get_conn() as conn:
        row = _fetch_wechat_wrong_question_submission_row_by_id(conn, normalized_record_id)
        if not row:
            return None

        tracking = _load_wrong_question_mastery_tracking_dict(row["mastery_tracking_json"])
        previous_session_id = str(tracking.get("latest_followup_session_id") or "").strip()
        try:
            followup_count = int(tracking.get("followup_count") or 0)
        except (TypeError, ValueError):
            followup_count = 0
        if previous_session_id != normalized_session_id:
            followup_count += 1
        elif followup_count <= 0:
            followup_count = 1

        tracking["followup_count"] = followup_count
        tracking["latest_followup_session_id"] = normalized_session_id
        tracking["latest_followup_outcome"] = normalized_outcome
        tracking["latest_followup_completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        normalized_summary_text = str(summary_text or "").strip()
        if normalized_summary_text:
            tracking["latest_followup_summary"] = normalized_summary_text
        else:
            tracking.pop("latest_followup_summary", None)

        conn.execute(
            """
            UPDATE wrong_question_submissions
            SET mastery_tracking_json=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (
                json.dumps(tracking, ensure_ascii=False, separators=(",", ":")),
                normalized_record_id,
            ),
        )
        refreshed = _fetch_wechat_wrong_question_submission_row_by_id(conn, normalized_record_id)
        return _serialize_wechat_wrong_question_submission_row(conn, refreshed)


def update_wechat_wrong_question_question_text(
    record_id: str,
    *,
    question_text: str,
    student_library_pdf_path: str,
) -> Optional[dict]:
    with get_conn() as conn:
        row = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        if not row:
            return None
        conn.execute(
            """
            UPDATE wrong_question_submissions
            SET question_text=?,
                question_text_edited=1,
                question_text_source='teacher',
                student_library_pdf_path=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (
                (question_text or "").strip(),
                (student_library_pdf_path or "").strip(),
                record_id,
            ),
        )
        refreshed = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        return _serialize_wechat_wrong_question_submission_row(conn, refreshed)


def _load_wrong_question_mastery_repeat_signal_counts(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
) -> dict:
    topic_category = normalize_primary_wrong_question_topic_category(str(row["topic_category"] or ""))
    if topic_category == PRIMARY_WRONG_QUESTION_TOPIC_UNCLASSIFIED:
        topic_category = ""
    error_type = str(row["primary_error_type"] or "").strip()
    counts = conn.execute(
        """
        SELECT
            SUM(CASE WHEN ?<>'' AND peer.topic_category=? THEN 1 ELSE 0 END) AS same_topic_active_count,
            SUM(CASE WHEN ?<>'' AND peer.primary_error_type=? THEN 1 ELSE 0 END) AS same_error_active_count,
            SUM(
                CASE
                    WHEN ((?<>'' AND peer.topic_category=?) OR (?<>'' AND peer.primary_error_type=?))
                    THEN 1
                    ELSE 0
                END
            ) AS repeated_active_count
        FROM wrong_question_submissions peer
        WHERE peer.student_id=?
          AND peer.id<>?
          AND peer.archive_status='active'
          AND peer.recognition_status='recognized'
        """,
        (
            topic_category,
            topic_category,
            error_type,
            error_type,
            topic_category,
            topic_category,
            error_type,
            error_type,
            int(row["student_id"] or 0),
            str(row["id"] or "").strip(),
        ),
    ).fetchone()
    return {
        "same_topic_active_count": int((counts["same_topic_active_count"] if counts else 0) or 0),
        "same_error_active_count": int((counts["same_error_active_count"] if counts else 0) or 0),
        "repeated_active_count": int((counts["repeated_active_count"] if counts else 0) or 0),
    }


def _build_wrong_question_mastery_assessment(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    mastery_tracking: dict,
    confirmation_status: str,
) -> dict:
    tracking = mastery_tracking if isinstance(mastery_tracking, dict) else {}
    repeat_counts = _load_wrong_question_mastery_repeat_signal_counts(conn, row)
    practice_sheet_count = int(tracking.get("practice_sheet_count") or 0)
    latest_practice_status = str(tracking.get("latest_practice_status") or "").strip()
    latest_practice_created_at = str(tracking.get("latest_practice_created_at") or "").strip()
    followup_count = int(tracking.get("followup_count") or 0)
    latest_followup_outcome = _normalize_wrong_question_mastery_followup_outcome(
        tracking.get("latest_followup_outcome")
    )
    latest_followup_completed_at = str(tracking.get("latest_followup_completed_at") or "").strip()
    is_manually_mastered = str(row["archive_status"] or "").strip() == "archived"
    followup_is_current = bool(
        latest_followup_outcome
        and (
            not latest_practice_created_at
            or latest_followup_completed_at >= latest_practice_created_at
        )
    )

    status = "monitor"
    label = "继续跟进"
    score = 2
    suggested_action = "follow_up"

    if confirmation_status == "returned":
        status = "returned_for_rework"
        label = "待补充"
        score = 0
        suggested_action = "continue_rework_chat"
    elif confirmation_status == "pending":
        status = "needs_teacher_review"
        label = "待老师确认"
        score = 0
        suggested_action = "teacher_review"
    elif is_manually_mastered and repeat_counts["repeated_active_count"] > 0:
        status = "relapsed"
        label = "疑似复发"
        score = 1
        suggested_action = "follow_up"
    elif is_manually_mastered:
        status = "mastered"
        label = "已掌握"
        score = 4
        suggested_action = "monitor"
    elif followup_is_current and latest_followup_outcome == "still_confused":
        status = "still_confused"
        label = "仍未掌握"
        score = 1
        suggested_action = "continue_follow_up"
    elif followup_is_current and latest_followup_outcome == "needs_another_practice":
        status = "needs_practice"
        label = "需要再练"
        score = 1
        suggested_action = "create_practice"
    elif followup_is_current and latest_followup_outcome == "likely_mastered":
        status = "likely_mastered"
        label = "大概率已掌握"
        score = 3
        suggested_action = "review_mastery"
    elif latest_practice_status in {"pending", "generating"}:
        status = "practice_in_progress"
        label = "练习生成中"
        score = 1
        suggested_action = "wait_practice"
    elif latest_practice_status == "failed":
        status = "needs_practice"
        label = "需重新出练习"
        score = 1
        suggested_action = "retry_practice"
    elif practice_sheet_count <= 0:
        status = "needs_practice"
        label = "需进入再练"
        score = 1
        suggested_action = "create_practice"
    elif repeat_counts["repeated_active_count"] > 0:
        status = "watch"
        label = "仍需观察"
        score = 2
        suggested_action = "follow_up"
    elif latest_practice_status in {"ready", "partial_failed"}:
        status = "ready_for_mastery_review"
        label = "待确认是否掌握"
        score = 3
        suggested_action = "review_mastery"

    evidence: list[str] = []
    if confirmation_status == "returned":
        evidence.append("老师已退回，需先补充后再确认。")
    elif confirmation_status == "pending":
        evidence.append("当前仍在老师复核队列中。")

    if is_manually_mastered:
        evidence.append("老师已手动标记为已掌握。")

    if practice_sheet_count > 0:
        evidence.append(f"已进入 {practice_sheet_count} 次再练链路。")
    else:
        evidence.append("还没有进入再练链路。")

    if followup_count > 0:
        evidence.append(f"已完成 {followup_count} 次掌握追问。")

    if latest_practice_status in {"ready", "partial_failed"}:
        evidence.append("最近一次再练已生成，可结合完成情况判断是否掌握。")
    elif latest_practice_status in {"pending", "generating"}:
        evidence.append("最近一次再练仍在生成中。")
    elif latest_practice_status == "failed":
        evidence.append("最近一次再练生成失败，需要重新发起。")

    if latest_followup_outcome == "still_confused":
        evidence.append("最近一次掌握追问结论：学生仍然卡在关键步骤。")
    elif latest_followup_outcome == "needs_another_practice":
        evidence.append("最近一次掌握追问结论：需要再来一轮同类练习。")
    elif latest_followup_outcome == "likely_mastered":
        evidence.append("最近一次掌握追问结论：学生大概率已经掌握。")

    if repeat_counts["same_topic_active_count"] > 0:
        evidence.append(f"同专题未掌握错题还有 {repeat_counts['same_topic_active_count']} 条。")
    if repeat_counts["same_error_active_count"] > 0:
        evidence.append(f"同错因未掌握错题还有 {repeat_counts['same_error_active_count']} 条。")

    return {
        "status": status,
        "label": label,
        "score": score,
        "suggested_action": suggested_action,
        "practice_sheet_count": practice_sheet_count,
        "latest_practice_status": latest_practice_status,
        "followup_count": followup_count,
        "latest_followup_outcome": latest_followup_outcome,
        "same_topic_active_count": repeat_counts["same_topic_active_count"],
        "same_error_active_count": repeat_counts["same_error_active_count"],
        "repeated_active_count": repeat_counts["repeated_active_count"],
        "manual_is_mastered": is_manually_mastered,
        "evidence": evidence,
    }


def _serialize_wechat_wrong_question_submission_row(
    conn: sqlite3.Connection,
    row: sqlite3.Row | None,
) -> Optional[dict]:
    if not row:
        return None

    payload = dict(row)
    payload.pop("parent_note", None)
    payload.pop("teacher_comment", None)
    payload["class_display_name"] = row["class_display_name"]
    payload["class_name_snapshot"] = row["class_display_name"]
    payload["student_name"] = row["student_name"]
    payload["teacher_display_name"] = row["teacher_display_name"]
    payload["teacher_name_snapshot"] = row["teacher_display_name"]
    payload["mapping_status"] = "mapped"
    payload["is_mastered"] = row["archive_status"] == "archived"
    payload["diagram_type"] = str(row["diagram_type"] or "")
    payload["diagram_spec_json"] = str(row["diagram_spec_json"] or "")
    try:
        diagram_spec = json.loads(payload["diagram_spec_json"]) if payload["diagram_spec_json"] else None
    except json.JSONDecodeError:
        diagram_spec = None
    payload["diagram_spec"] = diagram_spec if isinstance(diagram_spec, dict) else None
    try:
        question_structured = json.loads(str(row["question_structured_json"] or "")) if row["question_structured_json"] else None
    except json.JSONDecodeError:
        question_structured = None
    payload["question_structured"] = question_structured if isinstance(question_structured, dict) else None
    try:
        knowledge_tags = json.loads(str(row["knowledge_tags_json"] or "[]"))
    except json.JSONDecodeError:
        knowledge_tags = []
    normalized_knowledge_tags = [
        str(item or "").strip()
        for item in (knowledge_tags if isinstance(knowledge_tags, list) else [])
        if str(item or "").strip()
    ]
    try:
        confirmation_reasons = json.loads(str(row["confirmation_reasons_json"] or "[]"))
    except json.JSONDecodeError:
        confirmation_reasons = []
    normalized_confirmation_reasons = [
        str(item or "").strip()
        for item in (confirmation_reasons if isinstance(confirmation_reasons, list) else [])
        if str(item or "").strip()
    ]
    try:
        reflection_summary = json.loads(str(row["reflection_summary_json"] or "{}"))
    except json.JSONDecodeError:
        reflection_summary = {}
    if not isinstance(reflection_summary, dict):
        reflection_summary = {}
    if not reflection_summary:
        fallback_reflection_summary = {}
        child_raw_reason_text = str(row["child_raw_reason_text"] or "").strip()
        child_reason_core_issue = str(row["child_reason_core_issue"] or "").strip()
        child_reason_next_step = str(row["child_reason_next_step"] or "").strip()
        child_reason_transcript = str(row["child_reason_transcript"] or "").strip()
        if child_raw_reason_text:
            fallback_reflection_summary["why_wrong"] = child_raw_reason_text
        if child_reason_core_issue:
            fallback_reflection_summary["unknown_step"] = child_reason_core_issue
        if child_reason_next_step:
            fallback_reflection_summary["help_preference"] = child_reason_next_step
        if child_reason_transcript:
            fallback_reflection_summary["summary_text"] = child_reason_transcript
        answered_stages = []
        if child_raw_reason_text:
            answered_stages.append("ask_why_wrong")
        if child_reason_core_issue:
            answered_stages.append("ask_unknown_step")
        if child_reason_next_step:
            answered_stages.append("ask_help_mode")
        if answered_stages:
            fallback_reflection_summary["answered_stages"] = answered_stages
        if fallback_reflection_summary:
            fallback_reflection_summary["mode"] = "archive_reflection"
            fallback_reflection_summary["schema_version"] = "wrong_question_reflection_summary.v1"
            reflection_summary = fallback_reflection_summary
    try:
        generation_metadata = json.loads(str(row["generation_metadata_json"] or "{}"))
    except json.JSONDecodeError:
        generation_metadata = {}
    try:
        mastery_tracking = json.loads(str(row["mastery_tracking_json"] or "{}"))
    except json.JSONDecodeError:
        mastery_tracking = {}
    confirmation_status = str(row["confirmation_status"] or "").strip()
    if confirmation_status not in {"pending", "confirmed", "returned", "not_required"}:
        if row["needs_teacher_confirmation"]:
            confirmation_status = "pending"
        elif row["confirmation_reviewed_by"] is not None or str(row["confirmation_reviewed_at"] or "").strip():
            confirmation_status = "confirmed"
        else:
            confirmation_status = "not_required"
    payload["knowledge_tags"] = normalized_knowledge_tags
    payload["reflection_summary"] = reflection_summary
    payload["generation_metadata"] = generation_metadata if isinstance(generation_metadata, dict) else {}
    payload["mastery_tracking"] = mastery_tracking if isinstance(mastery_tracking, dict) else {}
    payload["mastery_assessment"] = _build_wrong_question_mastery_assessment(
        conn,
        row,
        payload["mastery_tracking"],
        confirmation_status,
    )
    payload["confirmation_reasons"] = normalized_confirmation_reasons
    payload["confirmation_status"] = confirmation_status
    payload["confirmation_reviewed_by"] = (
        int(row["confirmation_reviewed_by"])
        if row["confirmation_reviewed_by"] is not None
        else None
    )
    payload["confirmation_reviewed_at"] = str(row["confirmation_reviewed_at"] or "").strip()
    payload["confirmation_reviewer_name"] = str(row["confirmation_reviewer_display_name"] or "").strip()
    topic_category = normalize_primary_wrong_question_topic_category(str(row["topic_category"] or ""))
    payload["topic_category"] = topic_category
    payload["topicCategory"] = topic_category
    payload["is_primary_school"] = is_primary_school_class_name(
        str(row["class_display_name"] or ""),
        str(payload.get("grade") or ""),
    )
    payload["analysis"] = {
        "error_type": str(row["primary_error_type"] or ""),
        "selected_error_type": str(row["primary_error_type"] or ""),
        "student_note": str(row["secondary_error_summary"] or ""),
        "knowledge_points": normalized_knowledge_tags,
        "selected_knowledge_points": normalized_knowledge_tags,
        "core_issue": str(row["child_reason_core_issue"] or ""),
        "key_omission": str(row["child_reason_key_omission"] or ""),
        "next_step": str(row["child_reason_next_step"] or ""),
        "topic_category": topic_category,
        "topicCategory": topic_category,
    }
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
            c.grade AS grade,
            s.name AS student_name,
            u.display_name AS teacher_display_name,
            reviewer.display_name AS confirmation_reviewer_display_name
        FROM wrong_question_submissions wqs
        JOIN classes c ON c.id = wqs.class_id
        JOIN students s ON s.id = wqs.student_id
        JOIN users u ON u.id = wqs.teacher_user_id
        LEFT JOIN users reviewer ON reviewer.id = wqs.confirmation_reviewed_by
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
                c.grade AS grade,
                s.name AS student_name,
                u.display_name AS teacher_display_name,
                reviewer.display_name AS confirmation_reviewer_display_name
            FROM wrong_question_submissions wqs
            JOIN classes c ON c.id = wqs.class_id
            JOIN students s ON s.id = wqs.student_id
            JOIN users u ON u.id = wqs.teacher_user_id
            LEFT JOIN users reviewer ON reviewer.id = wqs.confirmation_reviewed_by
            ORDER BY wqs.created_at DESC, wqs.id DESC
            """
        ).fetchall()
        return [
            item
            for item in (
                _serialize_wechat_wrong_question_submission_row(conn, row)
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
                c.grade AS grade,
                s.name AS student_name,
                u.display_name AS teacher_display_name,
                reviewer.display_name AS confirmation_reviewer_display_name
            FROM wrong_question_submissions wqs
            JOIN classes c ON c.id = wqs.class_id
            JOIN students s ON s.id = wqs.student_id
            JOIN users u ON u.id = wqs.teacher_user_id
            LEFT JOIN users reviewer ON reviewer.id = wqs.confirmation_reviewed_by
            WHERE wqs.student_id=?
            ORDER BY wqs.created_at DESC, wqs.id DESC
            """,
            (student_id,),
        ).fetchall()
        return [
            item
            for item in (
                _serialize_wechat_wrong_question_submission_row(conn, row)
                for row in rows
            )
            if item is not None
        ]


def get_wechat_wrong_question_submission(record_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        return _serialize_wechat_wrong_question_submission_row(conn, row)


def list_wrong_question_submissions_for_chat_session(chat_session_id: str) -> list[dict]:
    normalized_session_id = (chat_session_id or "").strip()
    if not normalized_session_id:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                wqs.*,
                c.name AS class_display_name,
                c.grade AS grade,
                s.name AS student_name,
                u.display_name AS teacher_display_name,
                reviewer.display_name AS confirmation_reviewer_display_name
            FROM wrong_question_submissions wqs
            JOIN classes c ON c.id = wqs.class_id
            JOIN students s ON s.id = wqs.student_id
            JOIN users u ON u.id = wqs.teacher_user_id
            LEFT JOIN users reviewer ON reviewer.id = wqs.confirmation_reviewed_by
            WHERE wqs.chat_session_id=?
            ORDER BY wqs.created_at DESC, wqs.id DESC
            """,
            (normalized_session_id,),
        ).fetchall()
        return [
            item
            for item in (
                _serialize_wechat_wrong_question_submission_row(conn, row)
                for row in rows
            )
            if item is not None
        ]


def list_wrong_question_submissions_for_ingestion_run(ingestion_run_id: str) -> list[dict]:
    normalized_run_id = (ingestion_run_id or "").strip()
    if not normalized_run_id:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                wqs.*,
                c.name AS class_display_name,
                c.grade AS grade,
                s.name AS student_name,
                u.display_name AS teacher_display_name,
                reviewer.display_name AS confirmation_reviewer_display_name
            FROM wrong_question_submissions wqs
            JOIN classes c ON c.id = wqs.class_id
            JOIN students s ON s.id = wqs.student_id
            JOIN users u ON u.id = wqs.teacher_user_id
            LEFT JOIN users reviewer ON reviewer.id = wqs.confirmation_reviewed_by
            WHERE wqs.ingestion_run_id=?
            ORDER BY wqs.created_at DESC, wqs.id DESC
            """,
            (normalized_run_id,),
        ).fetchall()
        return [
            item
            for item in (
                _serialize_wechat_wrong_question_submission_row(conn, row)
                for row in rows
            )
            if item is not None
        ]


def list_student_wrong_question_library_records(student_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                wqs.*,
                c.name AS class_display_name,
                c.grade AS grade,
                s.name AS student_name,
                u.display_name AS teacher_display_name,
                reviewer.display_name AS confirmation_reviewer_display_name
            FROM wrong_question_submissions wqs
            JOIN classes c ON c.id = wqs.class_id
            JOIN students s ON s.id = wqs.student_id
            JOIN users u ON u.id = wqs.teacher_user_id
            LEFT JOIN users reviewer ON reviewer.id = wqs.confirmation_reviewed_by
            WHERE wqs.student_id=?
              AND wqs.recognition_status='recognized'
              AND wqs.archive_status='active'
            ORDER BY wqs.created_at DESC, wqs.id DESC
            """,
            (student_id,),
        ).fetchall()
        return [
            item
            for item in (
                _serialize_wechat_wrong_question_submission_row(conn, row)
                for row in rows
            )
            if item is not None
        ]


def attach_student_library_pdf_path(record_id: str, pdf_path: str) -> Optional[dict]:
    with get_conn() as conn:
        row = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        if not row:
            return None
        conn.execute(
            """
            UPDATE wrong_question_submissions
            SET student_library_pdf_path=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            ((pdf_path or "").strip(), record_id),
        )
        refreshed = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        return _serialize_wechat_wrong_question_submission_row(conn, refreshed)


def set_student_wrong_question_library_pdf_path(student_id: int, pdf_path: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE wrong_question_submissions
            SET student_library_pdf_path=?,
                updated_at=datetime('now','localtime')
            WHERE student_id=?
            """,
            ((pdf_path or "").strip(), student_id),
        )


def delete_wechat_wrong_question_submission(record_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        if not row:
            return None
        serialized = _serialize_wechat_wrong_question_submission_row(conn, row)
        conn.execute("DELETE FROM wrong_question_submissions WHERE id=?", (record_id,))
    return serialized


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
        return _serialize_wechat_wrong_question_submission_row(conn, refreshed)


def update_wechat_wrong_question_topic_category(record_id: str, *, topic_category: str) -> Optional[dict]:
    normalized_topic_category = normalize_primary_wrong_question_topic_category(topic_category)
    with get_conn() as conn:
        row = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        if not row:
            return None
        conn.execute(
            """
            UPDATE wrong_question_submissions
            SET topic_category=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (normalized_topic_category, record_id),
        )
        refreshed = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        return _serialize_wechat_wrong_question_submission_row(conn, refreshed)


def list_primary_topic_category_suggestions(
    *,
    organization_id: int,
    topic_category: str,
    limit: int = 5,
) -> list[str]:
    raw_query = (topic_category or "").strip()
    query = normalize_primary_wrong_question_topic_category(topic_category)
    if raw_query and query in PRIMARY_WRONG_QUESTION_TOPIC_PRESETS:
        return []

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT wqs.topic_category, c.name AS class_name, c.grade AS class_grade
            FROM wrong_question_submissions wqs
            JOIN classes c ON c.id = wqs.class_id
            WHERE wqs.organization_id=?
              AND COALESCE(wqs.topic_category, '') <> ''
            ORDER BY wqs.topic_category ASC
            """,
            (int(organization_id or 0),),
        ).fetchall()

    suggestions = []
    for row in rows:
        candidate = normalize_primary_wrong_question_topic_category(str(row["topic_category"] or ""))
        if candidate in PRIMARY_WRONG_QUESTION_TOPIC_PRESETS:
            continue
        if not is_primary_school_class_name(str(row["class_name"] or ""), str(row["class_grade"] or "")):
            continue
        if not candidate or (raw_query and (candidate == query or not _topic_category_matches(candidate, query))):
            continue
        suggestions.append(candidate)
        if len(suggestions) >= max(1, int(limit or 5)):
            break
    return suggestions


def save_wechat_wrong_question_review(record_id: str, payload: dict, *, reviewer_user_id: int | None = None) -> Optional[dict]:
    def normalize_reflection_summary(value: object) -> dict:
        source = value
        if isinstance(value, str):
            try:
                source = json.loads(value)
            except json.JSONDecodeError:
                source = {}
        if not isinstance(source, dict):
            return {}

        why_wrong = str(source.get("why_wrong") or source.get("whyWrong") or "").strip()
        unknown_step = str(source.get("unknown_step") or source.get("unknownStep") or "").strip()
        help_preference = str(source.get("help_preference") or source.get("helpPreference") or "").strip()
        mode = str(source.get("mode") or "").strip()
        summary_text = str(source.get("summary_text") or source.get("summaryText") or "").strip()
        session_entrypoint = str(source.get("session_entrypoint") or source.get("sessionEntrypoint") or "").strip()
        raw_answered_stages = source.get("answered_stages")
        if not isinstance(raw_answered_stages, list):
            raw_answered_stages = source.get("answeredStages")
        answered_stages = [
            str(item or "").strip()
            for item in (raw_answered_stages if isinstance(raw_answered_stages, list) else [])
            if str(item or "").strip()
        ]
        if not answered_stages:
            if why_wrong:
                answered_stages.append("ask_why_wrong")
            if unknown_step:
                answered_stages.append("ask_unknown_step")
            if help_preference:
                answered_stages.append("ask_help_mode")
        if not summary_text:
            parts: list[str] = []
            if why_wrong:
                parts.append(f"错因自述：{why_wrong}")
            if unknown_step:
                parts.append(f"卡点：{unknown_step}")
            if help_preference:
                parts.append(f"期望支持：{help_preference}")
            summary_text = "；".join(parts)
        if not any([summary_text, why_wrong, unknown_step, help_preference, answered_stages, mode, session_entrypoint]):
            return {}
        normalized = {
            "schema_version": "wrong_question_reflection_summary.v1",
            "mode": mode or "archive_reflection",
            "summary_text": summary_text,
            "answered_stages": answered_stages,
        }
        if why_wrong:
            normalized["why_wrong"] = why_wrong
        if unknown_step:
            normalized["unknown_step"] = unknown_step
        if help_preference:
            normalized["help_preference"] = help_preference
        if session_entrypoint:
            normalized["session_entrypoint"] = session_entrypoint
        return normalized

    raw_is_mastered = payload.get("is_mastered")
    normalized_is_mastered = bool(raw_is_mastered)
    if isinstance(raw_is_mastered, str):
        normalized_is_mastered = raw_is_mastered.strip().lower() in {"1", "true", "yes", "on"}

    def normalize_string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item or "").strip() for item in value if str(item or "").strip()]

    def normalize_optional_boolean(value: object) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return None

    has_selected_error_type = "selectedErrorType" in payload or "selected_error_type" in payload
    selected_error_type = str(
        payload.get("selectedErrorType")
        if "selectedErrorType" in payload
        else payload.get("selected_error_type")
        or ""
    ).strip()
    has_student_note = "studentNote" in payload or "student_note" in payload
    student_note = str(
        payload.get("studentNote")
        if "studentNote" in payload
        else payload.get("student_note")
        or ""
    ).strip()
    has_selected_knowledge_points = "selectedKnowledgePoints" in payload or "selected_knowledge_points" in payload
    selected_knowledge_points = normalize_string_list(
        payload.get("selectedKnowledgePoints")
        if "selectedKnowledgePoints" in payload
        else payload.get("selected_knowledge_points")
    )
    has_confirmation_state = "needs_teacher_confirmation" in payload or "needsTeacherConfirmation" in payload
    raw_confirmation_state = (
        payload.get("needs_teacher_confirmation")
        if "needs_teacher_confirmation" in payload
        else payload.get("needsTeacherConfirmation")
    )
    normalized_confirmation_state = normalize_optional_boolean(raw_confirmation_state)
    confirmation_reasons_payload = (
        payload.get("confirmation_reasons_json")
        if "confirmation_reasons_json" in payload
        else payload.get("confirmationReasons")
    )
    normalized_confirmation_reasons = normalize_string_list(confirmation_reasons_payload)
    has_reflection_summary = "reflection_summary_json" in payload or "reflectionSummary" in payload
    reflection_summary_payload = (
        payload.get("reflection_summary_json")
        if "reflection_summary_json" in payload
        else payload.get("reflectionSummary")
    )
    normalized_reflection_summary = normalize_reflection_summary(reflection_summary_payload)
    confirmation_action = str(
        payload.get("confirmation_action")
        if "confirmation_action" in payload
        else payload.get("confirmationAction")
        or ""
    ).strip()
    if confirmation_action not in {"", "save", "confirm", "edit_then_confirm", "return_for_rework"}:
        confirmation_action = ""

    with get_conn() as conn:
        row = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        if not row:
            return None
        if not has_selected_error_type:
            selected_error_type = str(row["primary_error_type"] or "").strip()
        if not has_student_note:
            student_note = str(row["secondary_error_summary"] or "").strip()
        if not has_selected_knowledge_points:
            try:
                existing_knowledge_tags = json.loads(str(row["knowledge_tags_json"] or "[]"))
            except json.JSONDecodeError:
                existing_knowledge_tags = []
            selected_knowledge_points = normalize_string_list(existing_knowledge_tags)
        try:
            existing_confirmation_reasons = json.loads(str(row["confirmation_reasons_json"] or "[]"))
        except json.JSONDecodeError:
            existing_confirmation_reasons = []
        existing_reflection_summary = normalize_reflection_summary(str(row["reflection_summary_json"] or "{}"))
        next_confirmation_state = bool(row["needs_teacher_confirmation"])
        next_confirmation_reasons = normalized_confirmation_reasons
        if has_confirmation_state and normalized_confirmation_state is not None:
            next_confirmation_state = normalized_confirmation_state
            if not next_confirmation_state:
                next_confirmation_reasons = []
        elif not normalized_confirmation_reasons:
            next_confirmation_reasons = normalize_string_list(existing_confirmation_reasons)

        next_confirmation_status = str(row["confirmation_status"] or "").strip()
        if next_confirmation_status not in {"pending", "confirmed", "returned", "not_required"}:
            if bool(row["needs_teacher_confirmation"]):
                next_confirmation_status = "pending"
            elif row["confirmation_reviewed_by"] is not None or str(row["confirmation_reviewed_at"] or "").strip():
                next_confirmation_status = "confirmed"
            else:
                next_confirmation_status = "not_required"
        next_confirmation_reviewed_by = int(row["confirmation_reviewed_by"]) if row["confirmation_reviewed_by"] is not None else None
        next_confirmation_reviewed_at = str(row["confirmation_reviewed_at"] or "").strip()
        reviewed_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if confirmation_action in {"confirm", "edit_then_confirm"}:
            next_confirmation_state = False
            next_confirmation_reasons = []
            next_confirmation_status = "confirmed"
            next_confirmation_reviewed_by = int(reviewer_user_id) if reviewer_user_id is not None else next_confirmation_reviewed_by
            next_confirmation_reviewed_at = reviewed_timestamp
        elif confirmation_action == "return_for_rework":
            next_confirmation_state = True
            if not next_confirmation_reasons:
                next_confirmation_reasons = normalize_string_list(existing_confirmation_reasons)
            next_confirmation_status = "returned"
            next_confirmation_reviewed_by = int(reviewer_user_id) if reviewer_user_id is not None else next_confirmation_reviewed_by
            next_confirmation_reviewed_at = reviewed_timestamp
        elif has_confirmation_state and normalized_confirmation_state is not None:
            if next_confirmation_state:
                next_confirmation_status = "returned" if next_confirmation_status == "returned" else "pending"
            else:
                next_confirmation_status = "confirmed"
                next_confirmation_reviewed_by = int(reviewer_user_id) if reviewer_user_id is not None else next_confirmation_reviewed_by
                next_confirmation_reviewed_at = reviewed_timestamp
        else:
            if next_confirmation_state:
                next_confirmation_status = next_confirmation_status if next_confirmation_status in {"pending", "returned"} else "pending"
            elif next_confirmation_status != "confirmed":
                next_confirmation_status = "not_required"
        next_reflection_summary = normalized_reflection_summary if has_reflection_summary else existing_reflection_summary
        if has_reflection_summary:
            next_child_reason_text = str(next_reflection_summary.get("why_wrong") or "").strip()
            next_child_reason_transcript = str(next_reflection_summary.get("summary_text") or "").strip()
            next_child_reason_core_issue = str(next_reflection_summary.get("unknown_step") or "").strip()
            next_child_reason_next_step = str(next_reflection_summary.get("help_preference") or "").strip()
        else:
            next_child_reason_text = str(
                next_reflection_summary.get("why_wrong")
                or row["child_raw_reason_text"]
                or ""
            ).strip()
            next_child_reason_transcript = str(
                next_reflection_summary.get("summary_text")
                or row["child_reason_transcript"]
                or ""
            ).strip()
            next_child_reason_core_issue = str(
                next_reflection_summary.get("unknown_step")
                or row["child_reason_core_issue"]
                or ""
            ).strip()
            next_child_reason_next_step = str(
                next_reflection_summary.get("help_preference")
                or row["child_reason_next_step"]
                or ""
            ).strip()
        conn.execute(
            """
            UPDATE wrong_question_submissions
            SET archive_status=?,
                archived_at=CASE WHEN ?='archived' THEN datetime('now','localtime') ELSE '' END,
                primary_error_type=?,
                secondary_error_summary=?,
                child_raw_reason_text=?,
                child_reason_transcript=?,
                child_reason_core_issue=?,
                child_reason_next_step=?,
                knowledge_tags_json=?,
                reflection_summary_json=?,
                needs_teacher_confirmation=?,
                confirmation_reasons_json=?,
                confirmation_status=?,
                confirmation_reviewed_by=?,
                confirmation_reviewed_at=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (
                "archived" if normalized_is_mastered else "active",
                "archived" if normalized_is_mastered else "active",
                selected_error_type,
                student_note,
                next_child_reason_text,
                next_child_reason_transcript,
                next_child_reason_core_issue,
                next_child_reason_next_step,
                json.dumps(selected_knowledge_points, ensure_ascii=False, separators=(",", ":")),
                json.dumps(next_reflection_summary, ensure_ascii=False, separators=(",", ":")),
                1 if next_confirmation_state else 0,
                json.dumps(next_confirmation_reasons, ensure_ascii=False, separators=(",", ":")),
                next_confirmation_status,
                next_confirmation_reviewed_by,
                next_confirmation_reviewed_at,
                record_id,
            ),
        )
        refreshed = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        return _serialize_wechat_wrong_question_submission_row(conn, refreshed)


def _serialize_weekly_wrong_question_followup_message_row(row: sqlite3.Row | None) -> Optional[dict]:
    if not row:
        return None
    payload = dict(row)
    try:
        source_record_ids = json.loads(payload.get("source_record_ids_json") or "[]")
    except json.JSONDecodeError:
        source_record_ids = []
    payload["source_record_ids"] = source_record_ids if isinstance(source_record_ids, list) else []
    payload["source_sheet_id"] = int(payload["source_sheet_id"]) if payload.get("source_sheet_id") is not None else None
    return payload


def get_weekly_wrong_question_followup_message(
    *,
    organization_id: int,
    class_id: int,
    student_id: int,
    week_start_date: str,
    style: str = "warm",
) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM weekly_wrong_question_followup_messages
            WHERE organization_id=?
              AND class_id=?
              AND student_id=?
              AND week_start_date=?
              AND style=?
            """,
            (
                int(organization_id or 0),
                int(class_id or 0),
                int(student_id or 0),
                (week_start_date or "").strip(),
                (style or "warm").strip() or "warm",
            ),
        ).fetchone()
    return _serialize_weekly_wrong_question_followup_message_row(row)


def upsert_weekly_wrong_question_followup_message(
    *,
    organization_id: int,
    class_id: int,
    student_id: int,
    teacher_user_id: int,
    week_start_date: str,
    week_end_date: str,
    style: str = "warm",
    message_text: str = "",
    source_record_ids: list[str] | None = None,
    source_sheet_id: int | None = None,
    generated_by: int | None = None,
) -> dict:
    normalized_style = (style or "warm").strip() or "warm"
    normalized_week_start = (week_start_date or "").strip()
    normalized_week_end = (week_end_date or "").strip()
    source_record_ids_json = json.dumps(
        [str(record_id) for record_id in (source_record_ids or [])],
        ensure_ascii=False,
    )
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO weekly_wrong_question_followup_messages (
                organization_id, class_id, student_id, teacher_user_id,
                week_start_date, week_end_date, style, message_text,
                source_record_ids_json, source_sheet_id, generated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(organization_id, class_id, student_id, week_start_date, style)
            DO UPDATE SET
                teacher_user_id=excluded.teacher_user_id,
                week_end_date=excluded.week_end_date,
                message_text=excluded.message_text,
                source_record_ids_json=excluded.source_record_ids_json,
                source_sheet_id=excluded.source_sheet_id,
                generated_by=excluded.generated_by,
                updated_at=datetime('now','localtime')
            """,
            (
                int(organization_id or 0),
                int(class_id or 0),
                int(student_id or 0),
                int(teacher_user_id or 0),
                normalized_week_start,
                normalized_week_end,
                normalized_style,
                (message_text or "").strip(),
                source_record_ids_json,
                int(source_sheet_id) if source_sheet_id is not None else None,
                generated_by,
            ),
        )
        row = conn.execute(
            """
            SELECT *
            FROM weekly_wrong_question_followup_messages
            WHERE organization_id=?
              AND class_id=?
              AND student_id=?
              AND week_start_date=?
              AND style=?
            """,
            (
                int(organization_id or 0),
                int(class_id or 0),
                int(student_id or 0),
                normalized_week_start,
                normalized_style,
            ),
        ).fetchone()
    return _serialize_weekly_wrong_question_followup_message_row(row) or {}


def _parse_local_date(value: str) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _is_recurring_wrong_question(row: sqlite3.Row | dict) -> bool:
    text = " ".join(
        str((row[key] if isinstance(row, sqlite3.Row) else row.get(key)) or "")
        for key in (
            "topic_category",
            "secondary_error_summary",
            "child_raw_reason_text",
            "child_reason_core_issue",
            "child_reason_key_omission",
            "child_reason_next_step",
        )
        if (key in row.keys() if isinstance(row, sqlite3.Row) else key in row)
    )
    return any(keyword in text for keyword in ("粗心", "符号", "审题", "步骤", "遗漏", "漏"))


def _is_wrong_question_candidate_for_week(row: sqlite3.Row, *, week_start: date, six_month_cutoff: date) -> bool:
    created_date = _parse_local_date(str(row["created_at"] or ""))
    if created_date is None or created_date < six_month_cutoff or created_date > week_start + timedelta(days=6):
        return False
    archive_status = str(row["archive_status"] or "active").strip() or "active"
    if archive_status != "archived":
        return True
    archived_date = _parse_local_date(str(row["archived_at"] or ""))
    if archived_date is None:
        return False
    interval_days = 30 if _is_recurring_wrong_question(row) else 60
    return archived_date <= week_start - timedelta(days=interval_days)


def _practice_pack_target_text(row: sqlite3.Row | dict) -> str:
    def value(key: str) -> str:
        if isinstance(row, sqlite3.Row):
            return str(row[key] or "") if key in row.keys() else ""
        return str(row.get(key) or "")

    return " ".join(
        part.strip()
        for part in (
            value("topic_category"),
            value("primary_error_type"),
            value("secondary_error_summary"),
            value("child_raw_reason_text"),
            value("child_reason_core_issue"),
            value("child_reason_key_omission"),
            value("child_reason_next_step"),
            value("teacher_comment"),
            value("question_text"),
        )
        if part.strip()
    )


def _practice_pack_reason_target_text(row: sqlite3.Row | dict) -> str:
    def value(key: str) -> str:
        if isinstance(row, sqlite3.Row):
            return str(row[key] or "") if key in row.keys() else ""
        return str(row.get(key) or "")

    return " ".join(
        part.strip()
        for part in (
            value("primary_error_type"),
            value("secondary_error_summary"),
            value("child_raw_reason_text"),
            value("child_reason_core_issue"),
            value("child_reason_key_omission"),
            value("child_reason_next_step"),
            value("teacher_comment"),
        )
        if part.strip()
    )


def _practice_pack_record_matches_target(row: sqlite3.Row, *, mode: str, target: str) -> bool:
    normalized_mode = _normalize_practice_pack_mode(mode)
    normalized_target = str(target or "").strip()
    if not normalized_target:
        return False
    if normalized_mode == "topic":
        topic = normalize_primary_wrong_question_topic_category(str(row["topic_category"] or ""))
        return normalized_target in topic or topic in normalized_target or normalized_target in _practice_pack_target_text(row)
    return normalized_target in _practice_pack_reason_target_text(row)


def _is_wrong_question_candidate_for_reference(row: sqlite3.Row, *, reference: date, six_month_cutoff: date) -> bool:
    created_date = _parse_local_date(str(row["created_at"] or ""))
    if created_date is None or created_date < six_month_cutoff or created_date > reference:
        return False
    archive_status = str(row["archive_status"] or "active").strip() or "active"
    if archive_status != "archived":
        return True
    archived_date = _parse_local_date(str(row["archived_at"] or ""))
    if archived_date is None:
        return False
    interval_days = 30 if _is_recurring_wrong_question(row) else 60
    return archived_date <= reference - timedelta(days=interval_days)


def _weekly_followup_reason_from_category(category: str, count: int, practiced_recently: bool) -> str:
    if practiced_recently:
        return f"{category}还有{count}道可练错题；如果其它分类不足，可以继续收这一类。"
    return f"{category}可练错题{count}道，且最近一周没有练过。"


def _serialize_weekly_followup_source_records(record_ids: list[str]) -> list[dict]:
    serialized_records: list[dict] = []
    seen_ids: set[str] = set()
    for record_id in record_ids:
        normalized_record_id = str(record_id or "").strip()
        if not normalized_record_id or normalized_record_id in seen_ids:
            continue
        seen_ids.add(normalized_record_id)
        record = get_wechat_wrong_question_submission(normalized_record_id)
        if record:
            serialized_records.append(record)
    return serialized_records


def _can_start_wrong_question_mastery_followup_record(record: object) -> bool:
    if not isinstance(record, dict):
        return False
    if str(record.get("source") or "").strip() != "ai_chat":
        return False
    confirmation_status = str(record.get("confirmation_status") or "").strip()
    if confirmation_status not in {"confirmed", "not_required"}:
        return False
    mastery_tracking = record.get("mastery_tracking") if isinstance(record.get("mastery_tracking"), dict) else {}
    mastery_assessment = record.get("mastery_assessment") if isinstance(record.get("mastery_assessment"), dict) else {}
    practice_sheet_count = int(
        mastery_tracking.get("practice_sheet_count")
        or mastery_assessment.get("practice_sheet_count")
        or 0
    )
    if practice_sheet_count <= 0:
        return False
    latest_practice_status = str(
        mastery_assessment.get("latest_practice_status")
        or mastery_tracking.get("latest_practice_status")
        or ""
    ).strip()
    return latest_practice_status not in {"pending", "generating"}


def _load_weekly_activity_summary_student_source_records(
    *,
    student_ids: list[int],
    organization_id: int | None = None,
) -> dict[int, list[dict]]:
    normalized_student_ids = [
        int(student_id)
        for student_id in student_ids
        if isinstance(student_id, int) and student_id > 0
    ]
    if not normalized_student_ids:
        return {}
    placeholders = ",".join("?" for _ in normalized_student_ids)
    params: list[object] = ["ai_chat", *normalized_student_ids]
    filters = [
        "source=?",
        f"student_id IN ({placeholders})",
    ]
    if organization_id is not None:
        filters.append("organization_id=?")
        params.append(int(organization_id or 0))
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT id, student_id
            FROM wrong_question_submissions
            WHERE {" AND ".join(filters)}
            ORDER BY created_at DESC, id DESC
            """,
            params,
        ).fetchall()
    source_records_by_student_id: dict[int, list[dict]] = {
        student_id: []
        for student_id in normalized_student_ids
    }
    for row in rows:
        student_id = int(row["student_id"] or 0)
        if student_id <= 0 or source_records_by_student_id.get(student_id):
            continue
        record = get_wechat_wrong_question_submission(str(row["id"] or "").strip())
        if record and _can_start_wrong_question_mastery_followup_record(record):
            source_records_by_student_id[student_id] = [record]
    return source_records_by_student_id


def list_weekly_wrong_question_followup_students(
    *,
    organization_id: int,
    class_id: int,
    week_start_date: str,
    week_end_date: str,
) -> list[dict]:
    week_start = _parse_local_date(week_start_date) or date.today()
    week_end = _parse_local_date(week_end_date) or week_start + timedelta(days=6)
    six_month_cutoff = week_end - timedelta(days=183)
    week_start_bound = f"{(week_start_date or '').strip()} 00:00:00"
    week_end_bound = f"{(week_end_date or '').strip()} 23:59:59"
    six_month_cutoff_bound = f"{six_month_cutoff.isoformat()} 00:00:00"
    with get_conn() as conn:
        student_rows = conn.execute(
            """
            SELECT
                c.name AS class_name,
                c.organization_id AS class_organization_id,
                uc.user_id AS class_teacher_user_id,
                u.display_name AS class_teacher_name,
                s.id AS student_id,
                s.name AS student_name,
                s.organization_id AS student_organization_id
            FROM class_students cs
            JOIN students s ON s.id = cs.student_id
            JOIN classes c ON c.id = cs.class_id
            LEFT JOIN user_classes uc ON uc.class_id = c.id
            LEFT JOIN users u ON u.id = uc.user_id
            WHERE c.organization_id=?
              AND c.id=?
            ORDER BY s.name ASC, s.id ASC, uc.user_id ASC
            """,
            (int(organization_id or 0), int(class_id or 0)),
        ).fetchall()
        sheet_rows = conn.execute(
            """
            SELECT *
            FROM wrong_question_practice_sheets
            WHERE organization_id=?
              AND class_id=?
              AND created_at >= ?
              AND created_at <= ?
            ORDER BY created_at DESC, id DESC
            """,
            (int(organization_id or 0), int(class_id or 0), week_start_bound, week_end_bound),
        ).fetchall()
        candidate_rows = conn.execute(
            """
            SELECT
                wqs.*,
                c.name AS class_name,
                s.name AS student_name,
                u.display_name AS teacher_name
            FROM wrong_question_submissions wqs
            JOIN classes c ON c.id = wqs.class_id
            JOIN students s ON s.id = wqs.student_id
            JOIN users u ON u.id = wqs.teacher_user_id
            WHERE wqs.organization_id=?
              AND wqs.class_id=?
              AND wqs.source IN ('wechat_mp', 'ai_chat')
              AND wqs.recognition_status='recognized'
              AND wqs.created_at >= ?
              AND wqs.created_at <= ?
            ORDER BY s.name ASC, wqs.created_at DESC, wqs.id DESC
            """,
            (
                int(organization_id or 0),
                int(class_id or 0),
                six_month_cutoff_bound,
                week_end_bound,
            ),
        ).fetchall()
        total_rows = conn.execute(
            """
            SELECT student_id, COUNT(*) AS total_active_question_count
            FROM wrong_question_submissions
            WHERE organization_id=?
              AND class_id=?
              AND source IN ('wechat_mp', 'ai_chat')
              AND recognition_status='recognized'
              AND archive_status='active'
            GROUP BY student_id
            """,
            (int(organization_id or 0), int(class_id or 0)),
        ).fetchall()
        item_rows = conn.execute(
            """
            SELECT
                item.*,
                wqs.topic_category,
                wqs.secondary_error_summary,
                wqs.child_raw_reason_text
            FROM wrong_question_practice_sheet_items item
            LEFT JOIN wrong_question_submissions wqs ON wqs.id = item.wrong_question_record_id
            WHERE item.sheet_id IN (
                SELECT id
                FROM wrong_question_practice_sheets
                WHERE organization_id=?
                  AND class_id=?
                  AND created_at >= ?
                  AND created_at <= ?
            )
            ORDER BY item.sheet_id ASC, item.question_order ASC, item.id ASC
            """,
            (int(organization_id or 0), int(class_id or 0), week_start_bound, week_end_bound),
        ).fetchall()

    total_count_by_student_id = {
        int(row["student_id"]): int(row["total_active_question_count"] or 0)
        for row in total_rows
    }
    items_by_sheet_id: dict[int, list[sqlite3.Row]] = {}
    for row in item_rows:
        items_by_sheet_id.setdefault(int(row["sheet_id"]), []).append(row)

    latest_sheet_by_student_id: dict[int, dict] = {}
    practiced_categories_by_student_id: dict[int, set[str]] = {}
    for row in sheet_rows:
        student_id = int(row["student_id"])
        sheet = _serialize_wrong_question_practice_sheet_row(row) or {}
        sheet_items = items_by_sheet_id.get(int(row["id"]), [])
        source_record_ids: list[str] = []
        categories: set[str] = set()
        reason_summaries: list[str] = []
        for item in sheet_items:
            record_id = str(item["wrong_question_record_id"] or "").strip()
            if record_id:
                source_record_ids.append(record_id)
            category = normalize_primary_wrong_question_topic_category(str(item["topic_category"] or item["primary_error_type_snapshot"] or ""))
            if category:
                categories.add(category)
            reason = str(item["cause_note_snapshot"] or item["secondary_error_summary"] or item["child_raw_reason_text"] or item["child_reason_text_snapshot"] or "").strip()
            if reason and len(reason_summaries) < 3:
                reason_summaries.append(reason)
        sheet["source_record_ids"] = source_record_ids
        sheet["topic_categories"] = sorted(categories)
        sheet["representative_reason_summaries"] = reason_summaries
        practiced_categories_by_student_id.setdefault(student_id, set()).update(categories)
        latest_sheet_by_student_id.setdefault(student_id, sheet)

    candidate_rows_by_student_id: dict[int, list[sqlite3.Row]] = {}
    for row in candidate_rows:
        if _is_wrong_question_candidate_for_week(row, week_start=week_start, six_month_cutoff=six_month_cutoff):
            candidate_rows_by_student_id.setdefault(int(row["student_id"]), []).append(row)

    seen_students: set[int] = set()
    students: list[dict] = []
    for row in student_rows:
        student_id = int(row["student_id"])
        if student_id in seen_students:
            continue
        seen_students.add(student_id)
        teacher_user_id = row["class_teacher_user_id"]
        teacher_name = row["class_teacher_name"] or "平台管理员"
        sheet = latest_sheet_by_student_id.get(student_id)
        candidates = candidate_rows_by_student_id.get(student_id, [])
        topic_categories: set[str] = set()
        reason_summaries: list[str] = []
        source_record_ids: list[str] = []
        for candidate in candidates:
            source_record_ids.append(str(candidate["id"]))
            category = normalize_primary_wrong_question_topic_category(str(candidate["topic_category"] or ""))
            if category:
                topic_categories.add(category)
            reason = str(candidate["secondary_error_summary"] or candidate["child_raw_reason_text"] or "").strip()
            if reason and len(reason_summaries) < 3:
                reason_summaries.append(reason)

        recommended_category = ""
        recommendation_reason = ""
        repeated_category = ""
        repeated_category_count = 0
        if candidates:
            grouped_by_category: dict[str, list[sqlite3.Row]] = {}
            for candidate in candidates:
                category = normalize_primary_wrong_question_topic_category(str(candidate["topic_category"] or ""))
                grouped_by_category.setdefault(category, []).append(candidate)
            practiced_categories = practiced_categories_by_student_id.get(student_id, set())
            ranked = sorted(
                grouped_by_category.items(),
                key=lambda item: (
                    1 if item[0] not in practiced_categories else 0,
                    len(item[1]),
                    min(str(row["created_at"] or "") for row in item[1]),
                    item[0],
                ),
                reverse=True,
            )
            if ranked:
                recommended_category, recommended_rows = ranked[0]
                recommendation_reason = _weekly_followup_reason_from_category(
                    recommended_category,
                    len(recommended_rows),
                    recommended_category in practiced_categories,
                )
            repeated_ranked = sorted(
                (
                    (category, len(rows))
                    for category, rows in grouped_by_category.items()
                    if len(rows) >= 2
                ),
                key=lambda item: (item[1], item[0]),
                reverse=True,
            )
            if repeated_ranked:
                repeated_category, repeated_category_count = repeated_ranked[0]

        if sheet:
            status = "has_practice_sheet"
            weekly_question_count = int(sheet.get("question_count") or 0)
            output_source_record_ids = sheet.get("source_record_ids") or []
            output_topic_categories = sheet.get("topic_categories") or []
            output_reasons = sheet.get("representative_reason_summaries") or []
            latest_created_at = sheet.get("created_at") or ""
        elif candidates:
            status = "needs_practice_sheet"
            weekly_question_count = len(candidates)
            output_source_record_ids = source_record_ids
            output_topic_categories = sorted(topic_categories)
            output_reasons = reason_summaries
            latest_created_at = str(candidates[0]["created_at"] or "")
        else:
            status = "no_practice_needed"
            weekly_question_count = 0
            output_source_record_ids = []
            output_topic_categories = []
            output_reasons = []
            latest_created_at = ""

        students.append(
            {
                "organization_id": int(row["class_organization_id"] or row["student_organization_id"] or organization_id or 0),
                "class_id": int(class_id or 0),
                "class_name": row["class_name"],
                "student_id": student_id,
                "student_name": row["student_name"],
                "teacher_user_id": int(teacher_user_id) if teacher_user_id is not None else 0,
                "teacher_name": teacher_name,
                "status": status,
                "practice_sheet": sheet,
                "weekly_question_count": weekly_question_count,
                "total_active_question_count": total_count_by_student_id.get(student_id, len(candidates)),
                "candidate_question_count": len(candidates),
                "candidate_record_ids": source_record_ids,
                "recommended_category": recommended_category,
                "recommendation_reason": recommendation_reason,
                "topic_categories": output_topic_categories,
                "representative_reason_summaries": output_reasons,
                "latest_created_at": latest_created_at,
                "source_record_ids": output_source_record_ids,
                "source_records": _serialize_weekly_followup_source_records(output_source_record_ids),
                "repeated_category": repeated_category,
                "repeated_category_count": repeated_category_count,
            }
        )
    return students


def list_weekly_wrong_question_activity_summary(
    *,
    week_start_date: str,
    week_end_date: str,
    organization_id: int | None = None,
    limit: int = 10,
) -> dict:
    week_start_bound = f"{(week_start_date or '').strip()} 00:00:00"
    week_end_bound = f"{(week_end_date or '').strip()} 23:59:59"
    normalized_limit = max(1, int(limit or 10))
    where_clauses = [
        "wqs.source='wechat_mp'",
        "wqs.recognition_status='recognized'",
        "wqs.created_at >= ?",
        "wqs.created_at <= ?",
        "wqs.organization_id IS NOT NULL",
        "wqs.class_id IS NOT NULL",
        "wqs.student_id IS NOT NULL",
    ]
    params: list[object] = [week_start_bound, week_end_bound]
    if organization_id is not None:
        where_clauses.append("wqs.organization_id=?")
        params.append(int(organization_id or 0))
    where_sql = " AND ".join(where_clauses)

    total_where_clauses = [
        "recognition_status='recognized'",
        "student_id IS NOT NULL",
    ]
    total_params: list[object] = []
    if organization_id is not None:
        total_where_clauses.append("organization_id=?")
        total_params.append(int(organization_id or 0))
    total_where_sql = " AND ".join(total_where_clauses)

    with get_conn() as conn:
        weekly_rows = conn.execute(
            f"""
            SELECT
                wqs.*,
                o.name AS organization_name,
                c.name AS class_name,
                s.name AS student_name,
                u.display_name AS teacher_name
            FROM wrong_question_submissions wqs
            JOIN organizations o ON o.id = wqs.organization_id
            JOIN classes c ON c.id = wqs.class_id
            JOIN students s ON s.id = wqs.student_id
            JOIN users u ON u.id = wqs.teacher_user_id
            WHERE {where_sql}
            ORDER BY wqs.created_at DESC, wqs.id DESC
            """,
            params,
        ).fetchall()
        total_rows = conn.execute(
            f"""
            SELECT student_id, COUNT(*) AS total_question_count
            FROM wrong_question_submissions
            WHERE {total_where_sql}
            GROUP BY student_id
            """,
            total_params,
        ).fetchall()

    total_count_by_student_id = {
        int(row["student_id"]): int(row["total_question_count"] or 0)
        for row in total_rows
    }
    class_items_by_id: dict[int, dict] = {}
    teacher_items_by_id: dict[int, dict] = {}
    student_items_by_id: dict[int, dict] = {}
    class_student_ids: dict[int, set[int]] = {}
    teacher_class_ids: dict[int, set[int]] = {}
    teacher_student_ids: dict[int, set[int]] = {}
    student_topic_counts: dict[int, dict[str, int]] = {}

    for row in weekly_rows:
        class_id_value = int(row["class_id"])
        teacher_user_id = int(row["teacher_user_id"])
        student_id_value = int(row["student_id"])
        created_at = str(row["created_at"] or "")

        class_item = class_items_by_id.setdefault(
            class_id_value,
            {
                "organization_id": row["organization_id"],
                "organization_name": row["organization_name"],
                "class_id": row["class_id"],
                "class_name": row["class_name"],
                "weekly_question_count": 0,
                "uploading_student_count": 0,
                "latest_created_at": created_at,
            },
        )
        class_item["weekly_question_count"] += 1
        if created_at > str(class_item["latest_created_at"] or ""):
            class_item["latest_created_at"] = created_at
        class_student_ids.setdefault(class_id_value, set()).add(student_id_value)

        teacher_item = teacher_items_by_id.setdefault(
            teacher_user_id,
            {
                "organization_id": row["organization_id"],
                "organization_name": row["organization_name"],
                "teacher_user_id": row["teacher_user_id"],
                "teacher_name": row["teacher_name"],
                "class_count": 0,
                "weekly_question_count": 0,
                "involved_student_count": 0,
                "pending_followup_count": 0,
                "latest_created_at": created_at,
            },
        )
        teacher_item["weekly_question_count"] += 1
        if str(row["archive_status"] or "") == "active":
            teacher_item["pending_followup_count"] += 1
        if created_at > str(teacher_item["latest_created_at"] or ""):
            teacher_item["latest_created_at"] = created_at
        teacher_class_ids.setdefault(teacher_user_id, set()).add(class_id_value)
        teacher_student_ids.setdefault(teacher_user_id, set()).add(student_id_value)

        student_item = student_items_by_id.setdefault(
            student_id_value,
            {
                "organization_id": row["organization_id"],
                "organization_name": row["organization_name"],
                "class_id": row["class_id"],
                "class_name": row["class_name"],
                "student_id": row["student_id"],
                "student_name": row["student_name"],
                "weekly_question_count": 0,
                "total_question_count": total_count_by_student_id.get(student_id_value, 0),
                "topic_categories": [],
                "latest_created_at": created_at,
            },
        )
        student_item["weekly_question_count"] += 1
        if created_at > str(student_item["latest_created_at"] or ""):
            student_item["latest_created_at"] = created_at
        topic_category = normalize_primary_wrong_question_topic_category(str(row["topic_category"] or ""))
        topic_counts = student_topic_counts.setdefault(student_id_value, {})
        topic_counts[topic_category] = topic_counts.get(topic_category, 0) + 1

    for class_id_value, item in class_items_by_id.items():
        item["uploading_student_count"] = len(class_student_ids.get(class_id_value, set()))
    for teacher_user_id, item in teacher_items_by_id.items():
        item["class_count"] = len(teacher_class_ids.get(teacher_user_id, set()))
        item["involved_student_count"] = len(teacher_student_ids.get(teacher_user_id, set()))
    student_source_records_by_id = _load_weekly_activity_summary_student_source_records(
        student_ids=list(student_items_by_id.keys()),
        organization_id=organization_id,
    )
    for student_id_value, item in student_items_by_id.items():
        topic_counts = student_topic_counts.get(student_id_value, {})
        item["topic_categories"] = [
            topic
            for topic, _count in sorted(
                topic_counts.items(),
                key=lambda topic_item: (-int(topic_item[1] or 0), str(topic_item[0] or "")),
            )[:3]
        ] or [PRIMARY_WRONG_QUESTION_TOPIC_UNCLASSIFIED]
        source_records = student_source_records_by_id.get(student_id_value) or []
        item["source_record_ids"] = [
            str(record.get("id") or "").strip()
            for record in source_records
            if str(record.get("id") or "").strip()
        ]
        item["source_records"] = source_records

    class_items = sorted(
        class_items_by_id.values(),
        key=lambda item: str(item["latest_created_at"] or ""),
        reverse=True,
    )
    class_items = sorted(
        class_items,
        key=lambda item: (
            -int(item["weekly_question_count"] or 0),
            -int(item["uploading_student_count"] or 0),
        ),
    )
    teacher_items = sorted(
        teacher_items_by_id.values(),
        key=lambda item: (
            -int(item["weekly_question_count"] or 0),
            -int(item["involved_student_count"] or 0),
            -int(item["pending_followup_count"] or 0),
            str(item["teacher_name"] or ""),
        ),
    )
    student_items = sorted(
        student_items_by_id.values(),
        key=lambda item: str(item["latest_created_at"] or ""),
        reverse=True,
    )
    student_items = sorted(
        student_items,
        key=lambda item: (
            -int(item["weekly_question_count"] or 0),
            -int(item["total_question_count"] or 0),
        ),
    )

    return {
        "class_items": class_items[:normalized_limit],
        "teacher_items": teacher_items[:normalized_limit],
        "student_items": student_items[:normalized_limit],
    }


def _serialize_wrong_question_practice_sheet_row(row: sqlite3.Row | None) -> Optional[dict]:
    if not row:
        return None
    payload = dict(row)
    payload["question_count"] = int(payload.get("question_count") or 0)
    try:
        source_record_ids = json.loads(str(payload.get("source_record_ids_json") or "[]"))
    except (TypeError, json.JSONDecodeError):
        source_record_ids = []
    payload["source_record_ids"] = [
        str(record_id).strip()
        for record_id in source_record_ids
        if str(record_id).strip()
    ] if isinstance(source_record_ids, list) else []
    try:
        payload["generation_metadata"] = (
            json.loads(str(payload.get("generation_metadata_json") or "{}"))
            if payload.get("generation_metadata_json")
            else {}
        )
    except (TypeError, json.JSONDecodeError):
        payload["generation_metadata"] = {}
    return payload


def _serialize_wrong_question_practice_sheet_item_row(row: sqlite3.Row | None) -> Optional[dict]:
    if not row:
        return None
    payload = dict(row)
    payload["question_order"] = int(payload.get("question_order") or 0)
    payload["is_geometry"] = bool(payload.get("is_geometry"))
    payload["child_reason_transcript_snapshot"] = str(payload.get("child_reason_transcript_snapshot") or "").strip()
    try:
        payload["question_structured_snapshot"] = (
            json.loads(str(payload.get("question_structured_snapshot_json") or ""))
            if payload.get("question_structured_snapshot_json")
            else None
        )
    except (TypeError, json.JSONDecodeError):
        payload["question_structured_snapshot"] = None
    if not isinstance(payload.get("question_structured_snapshot"), dict):
        payload["question_structured_snapshot"] = None
    try:
        knowledge_tags_snapshot = (
            json.loads(str(payload.get("knowledge_tags_snapshot_json") or "[]"))
            if payload.get("knowledge_tags_snapshot_json")
            else []
        )
    except (TypeError, json.JSONDecodeError):
        knowledge_tags_snapshot = []
    payload["knowledge_tags_snapshot"] = [
        str(item or "").strip()
        for item in (knowledge_tags_snapshot if isinstance(knowledge_tags_snapshot, list) else [])
        if str(item or "").strip()
    ]
    try:
        payload["reflection_summary_snapshot"] = (
            json.loads(str(payload.get("reflection_summary_snapshot_json") or "{}"))
            if payload.get("reflection_summary_snapshot_json")
            else {}
        )
    except (TypeError, json.JSONDecodeError):
        payload["reflection_summary_snapshot"] = {}
    if not isinstance(payload.get("reflection_summary_snapshot"), dict):
        payload["reflection_summary_snapshot"] = {}
    try:
        payload["structured_content"] = (
            json.loads(str(payload.get("structured_content_json") or "{}"))
            if payload.get("structured_content_json")
            else {}
        )
    except (TypeError, json.JSONDecodeError):
        payload["structured_content"] = {}
    try:
        payload["generation_metadata"] = (
            json.loads(str(payload.get("generation_metadata_json") or "{}"))
            if payload.get("generation_metadata_json")
            else {}
        )
    except (TypeError, json.JSONDecodeError):
        payload["generation_metadata"] = {}
    return payload


def _build_wrong_question_mastery_tracking_payload(
    conn: sqlite3.Connection,
    record_id: str,
) -> dict:
    existing_row = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
    existing_tracking = _load_wrong_question_mastery_tracking_dict(
        existing_row["mastery_tracking_json"] if existing_row else "{}"
    )
    payload = _preserve_wrong_question_mastery_followup_tracking(existing_tracking)
    rows = conn.execute(
        """
        SELECT
            sheet.id,
            sheet.status,
            sheet.pdf_path,
            sheet.created_at,
            item.topic_category_snapshot,
            item.primary_error_type_snapshot
        FROM wrong_question_practice_sheet_items item
        JOIN wrong_question_practice_sheets sheet ON sheet.id = item.sheet_id
        WHERE item.wrong_question_record_id=?
        ORDER BY sheet.created_at DESC, sheet.id DESC, item.question_order ASC, item.id ASC
        """,
        (str(record_id or "").strip(),),
    ).fetchall()
    if not rows:
        return payload

    unique_sheet_ids: list[int] = []
    seen_sheet_ids: set[int] = set()
    related_topic_categories: list[str] = []
    seen_topics: set[str] = set()
    related_error_types: list[str] = []
    seen_error_types: set[str] = set()

    for row in rows:
        sheet_id = int(row["id"])
        if sheet_id not in seen_sheet_ids:
            unique_sheet_ids.append(sheet_id)
            seen_sheet_ids.add(sheet_id)
        topic_category = normalize_primary_wrong_question_topic_category(str(row["topic_category_snapshot"] or ""))
        if topic_category and topic_category != PRIMARY_WRONG_QUESTION_TOPIC_UNCLASSIFIED and topic_category not in seen_topics:
            related_topic_categories.append(topic_category)
            seen_topics.add(topic_category)
        error_type = str(row["primary_error_type_snapshot"] or "").strip()
        if error_type and error_type not in seen_error_types:
            related_error_types.append(error_type)
            seen_error_types.add(error_type)

    latest = rows[0]
    payload.update({
        "practice_sheet_count": len(unique_sheet_ids),
        "latest_practice_sheet_id": int(latest["id"]),
        "latest_practice_status": str(latest["status"] or "").strip(),
        "latest_practice_created_at": str(latest["created_at"] or "").strip(),
        "latest_practice_pdf_path": str(latest["pdf_path"] or "").strip(),
        "related_topic_categories": related_topic_categories,
        "related_error_types": related_error_types,
    })
    return payload


def _refresh_wrong_question_submission_mastery_tracking(
    conn: sqlite3.Connection,
    record_id: str,
) -> None:
    normalized_record_id = str(record_id or "").strip()
    if not normalized_record_id:
        return
    payload = _build_wrong_question_mastery_tracking_payload(conn, normalized_record_id)
    conn.execute(
        """
        UPDATE wrong_question_submissions
        SET mastery_tracking_json=?,
            updated_at=datetime('now','localtime')
        WHERE id=?
        """,
        (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) if payload else "{}",
            normalized_record_id,
        ),
    )


PRACTICE_PACK_MODE_OPTIONS = {"topic", "reason"}
PRACTICE_PACK_VOLUME_COUNTS = {"light": 5, "standard": 10, "intensive": 15}
PRACTICE_PACK_JOB_STATUSES = {"pending", "running", "ready", "partial_failed", "failed"}
PRACTICE_PACK_STUDENT_STATUSES = {"pending", "running", "ready", "skipped", "failed"}


def _normalize_practice_pack_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized not in PRACTICE_PACK_MODE_OPTIONS:
        raise ValueError("mode must be topic or reason")
    return normalized


def _normalize_practice_pack_volume(volume: str) -> str:
    normalized = str(volume or "").strip().lower()
    if normalized not in PRACTICE_PACK_VOLUME_COUNTS:
        raise ValueError("volume must be light, standard or intensive")
    return normalized


def _serialize_wrong_question_practice_pack_job_row(row: sqlite3.Row | None) -> Optional[dict]:
    if not row:
        return None
    payload = dict(row)
    payload["requested_question_count"] = int(payload.get("requested_question_count") or 0)
    return payload


def _serialize_wrong_question_practice_pack_student_row(row: sqlite3.Row | None) -> Optional[dict]:
    if not row:
        return None
    payload = dict(row)
    for key in ("requested_question_count", "real_question_count", "variant_question_count"):
        payload[key] = int(payload.get(key) or 0)
    return payload


def list_targeted_wrong_question_practice_candidates(
    *,
    organization_id: int,
    class_id: int,
    student_id: int,
    mode: str,
    target: str,
    limit: int,
    reference_date: str = "",
) -> list[dict]:
    normalized_mode = _normalize_practice_pack_mode(mode)
    normalized_target = str(target or "").strip()
    if not normalized_target:
        return []
    reference = _parse_local_date(reference_date) or date.today()
    six_month_cutoff = reference - timedelta(days=183)
    six_month_cutoff_bound = f"{six_month_cutoff.isoformat()} 00:00:00"
    reference_end_bound = f"{reference.isoformat()} 23:59:59"
    normalized_limit = max(1, int(limit or 1))
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
            WHERE wqs.organization_id=?
              AND wqs.class_id=?
              AND wqs.student_id=?
              AND wqs.source='wechat_mp'
              AND wqs.recognition_status='recognized'
              AND wqs.created_at >= ?
              AND wqs.created_at <= ?
            ORDER BY
              CASE WHEN wqs.archive_status='active' THEN 0 ELSE 1 END ASC,
              wqs.created_at DESC,
              wqs.id DESC
            """,
            (
                int(organization_id or 0),
                int(class_id or 0),
                int(student_id or 0),
                six_month_cutoff_bound,
                reference_end_bound,
            ),
        ).fetchall()
    matched = [
        dict(row)
        for row in rows
        if _is_wrong_question_candidate_for_reference(row, reference=reference, six_month_cutoff=six_month_cutoff)
        and _practice_pack_record_matches_target(row, mode=normalized_mode, target=normalized_target)
    ]
    return matched[:normalized_limit]


def build_wrong_question_practice_pack_schedule(items: list[dict], *, start_date: str) -> list[dict]:
    start = _parse_local_date(start_date) or date.today()
    ordered_items = list(items or [])
    days = [
        {
            "day_index": index + 1,
            "date": (start + timedelta(days=index)).isoformat(),
            "items": [],
        }
        for index in range(7)
    ]
    for index, item in enumerate(ordered_items):
        days[index % 7]["items"].append(item)
    return days


def _fetch_wrong_question_practice_sheet_row_by_id(
    conn: sqlite3.Connection,
    sheet_id: int,
) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM wrong_question_practice_sheets
        WHERE id=?
        """,
        (sheet_id,),
    ).fetchone()


def create_pending_wrong_question_practice_sheet(
    *,
    created_by: int,
    selected_records: list[dict],
) -> dict:
    if not selected_records:
        raise ValueError("selected_records is required")

    first_record = selected_records[0]
    organization_id = int(first_record.get("organization_id") or 0)
    class_id = int(first_record.get("class_id") or 0)
    student_id = int(first_record.get("student_id") or 0)
    teacher_user_id = int(first_record.get("teacher_user_id") or 0)
    student_name_snapshot = str(first_record.get("student_name") or "").strip()
    class_name_snapshot = str(first_record.get("class_display_name") or "").strip()
    teacher_name_snapshot = str(first_record.get("teacher_display_name") or "").strip()

    if not organization_id or not class_id or not student_id or not teacher_user_id:
        raise ValueError("selected wrong question records are incomplete")

    for record in selected_records:
        if int(record.get("organization_id") or 0) != organization_id:
            raise ValueError("selected records must belong to the same organization")
        if int(record.get("class_id") or 0) != class_id:
            raise ValueError("selected records must belong to the same class")
        if int(record.get("student_id") or 0) != student_id:
            raise ValueError("selected records must belong to the same student")

    linked_record_ids = [
        str(record.get("id") or "").strip()
        for record in selected_records
        if str(record.get("id") or "").strip()
    ]
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO wrong_question_practice_sheets (
                organization_id,
                class_id,
                student_id,
                teacher_user_id,
                created_by,
                student_name_snapshot,
                class_name_snapshot,
                teacher_name_snapshot,
                question_count,
                status,
                pdf_path,
                source_record_ids_json,
                generation_metadata_json,
                generation_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', '', ?, '{}', '')
            """,
            (
                organization_id,
                class_id,
                student_id,
                teacher_user_id,
                int(created_by),
                student_name_snapshot,
                class_name_snapshot,
                teacher_name_snapshot,
                len(selected_records),
                json.dumps(linked_record_ids, ensure_ascii=False),
            ),
        )
        sheet_id = int(cursor.lastrowid)
        for index, record in enumerate(selected_records, start=1):
            linked_record_id = str(record.get("id") or "").strip()
            conn.execute(
                """
                INSERT INTO wrong_question_practice_sheet_items (
                    sheet_id,
                    question_order,
                    wrong_question_record_id,
                    source,
                    is_geometry,
                    question_text_snapshot,
                    image_url_snapshot,
                    erased_image_url_snapshot,
                    diagram_type_snapshot,
                    diagram_spec_json_snapshot,
                    child_reason_text_snapshot,
                    child_reason_transcript_snapshot,
                    primary_error_type_snapshot,
                    cause_note_snapshot,
                    topic_category_snapshot,
                    question_structured_snapshot_json,
                    knowledge_tags_snapshot_json,
                    reflection_summary_snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sheet_id,
                    index,
                    linked_record_id,
                    str(record.get("source") or "wechat_mp").strip() or "wechat_mp",
                    1 if bool(record.get("is_geometry")) else 0,
                    str(record.get("question_text") or "").strip(),
                    str(record.get("image_url") or "").strip(),
                    _resolve_erased_wrong_question_image_url_for_record(conn, record),
                    str(record.get("diagram_type") or "").strip(),
                    str(record.get("diagram_spec_json") or "").strip(),
                    str(record.get("child_raw_reason_text") or "").strip(),
                    str(record.get("child_reason_transcript") or "").strip(),
                    str(record.get("primary_error_type") or "").strip(),
                    str(record.get("secondary_error_summary") or "").strip(),
                    str(record.get("topic_category") or "").strip(),
                    _normalize_json_storage_value(
                        record.get("question_structured_json", record.get("question_structured")),
                        field_name="question_structured_snapshot_json",
                        default="",
                    ),
                    _normalize_json_storage_value(
                        record.get("knowledge_tags_json", record.get("knowledge_tags")),
                        field_name="knowledge_tags_snapshot_json",
                        default="[]",
                    ),
                    _normalize_json_storage_value(
                        record.get("reflection_summary_json", record.get("reflection_summary")),
                        field_name="reflection_summary_snapshot_json",
                        default="{}",
                    ),
                ),
            )
        for linked_record_id in linked_record_ids:
            _refresh_wrong_question_submission_mastery_tracking(conn, linked_record_id)
        saved = _fetch_wrong_question_practice_sheet_row_by_id(conn, sheet_id)
    serialized = _serialize_wrong_question_practice_sheet_row(saved)
    return serialized if serialized is not None else {}


def get_wrong_question_practice_sheet(sheet_id: int) -> Optional[dict]:
    with get_conn() as conn:
        sheet_row = _fetch_wrong_question_practice_sheet_row_by_id(conn, sheet_id)
        if not sheet_row:
            return None
        item_rows = conn.execute(
            """
            SELECT *
            FROM wrong_question_practice_sheet_items
            WHERE sheet_id=?
            ORDER BY question_order ASC, id ASC
            """,
            (sheet_id,),
        ).fetchall()
    serialized = _serialize_wrong_question_practice_sheet_row(sheet_row)
    if serialized is None:
        return None
    serialized["items"] = [
        item
        for item in (
            _serialize_wrong_question_practice_sheet_item_row(row)
            for row in item_rows
        )
        if item is not None
    ]
    return serialized


def list_wrong_question_practice_sheets_for_student(student_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM wrong_question_practice_sheets
            WHERE student_id=?
            ORDER BY created_at DESC, id DESC
            """,
            (student_id,),
        ).fetchall()
    return [
        item
        for item in (
            _serialize_wrong_question_practice_sheet_row(row)
            for row in rows
        )
        if item is not None
    ]


def delete_wrong_question_practice_sheet(sheet_id: int) -> Optional[dict]:
    with get_conn() as conn:
        sheet_row = _fetch_wrong_question_practice_sheet_row_by_id(conn, sheet_id)
        if not sheet_row:
            return None
        serialized = get_wrong_question_practice_sheet(sheet_id)
        linked_record_ids = [
            str(row["wrong_question_record_id"] or "").strip()
            for row in conn.execute(
                """
                SELECT wrong_question_record_id
                FROM wrong_question_practice_sheet_items
                WHERE sheet_id=?
                """,
                (sheet_id,),
            ).fetchall()
            if str(row["wrong_question_record_id"] or "").strip()
        ]
        conn.execute("DELETE FROM wrong_question_practice_sheets WHERE id=?", (sheet_id,))
        for linked_record_id in linked_record_ids:
            _refresh_wrong_question_submission_mastery_tracking(conn, linked_record_id)
    return serialized


def mark_wrong_question_practice_sheet_succeeded(
    sheet_id: int,
    *,
    generated_items: list[dict],
    pdf_path: str,
    generation_metadata: object = None,
) -> Optional[dict]:
    generated_item_by_record_id = {
        str(item.get("wrong_question_record_id") or "").strip(): item
        for item in (generated_items or [])
        if str(item.get("wrong_question_record_id") or "").strip()
    }

    linked_record_ids: list[str] = []
    with get_conn() as conn:
        sheet_row = _fetch_wrong_question_practice_sheet_row_by_id(conn, sheet_id)
        if not sheet_row:
            raise LookupError("wrong question practice sheet not found")
        item_rows = conn.execute(
            """
            SELECT id, wrong_question_record_id
            FROM wrong_question_practice_sheet_items
            WHERE sheet_id=?
            ORDER BY question_order ASC, id ASC
            """,
            (sheet_id,),
        ).fetchall()
        if len(generated_item_by_record_id) != len(item_rows):
            raise ValueError("generated_items do not match selected records")
        for row in item_rows:
            wrong_question_record_id = str(row["wrong_question_record_id"] or "").strip()
            generated = generated_item_by_record_id.get(wrong_question_record_id)
            if not generated:
                raise ValueError("generated_items do not match selected records")
            if wrong_question_record_id:
                linked_record_ids.append(wrong_question_record_id)
            conn.execute(
                """
                UPDATE wrong_question_practice_sheet_items
                SET ai_hint=?,
                    reason_blank_prompt=?,
                    improvement_summary_prompt=?,
                    structured_content_json=?,
                    generation_metadata_json=?,
                    updated_at=datetime('now','localtime')
                WHERE id=?
                """,
                (
                    str(generated.get("ai_hint") or "").strip(),
                    str(generated.get("reason_blank_prompt") or "").strip(),
                    str(generated.get("improvement_summary_prompt") or "").strip(),
                    _normalize_json_storage_value(
                        generated.get("structured_content_json", generated.get("structured_content")),
                        field_name="structured_content_json",
                        default="{}",
                    ),
                    _normalize_json_storage_value(
                        generated.get("generation_metadata_json", generated.get("generation_metadata")),
                        field_name="generation_metadata_json",
                        default="{}",
                    ),
                    row["id"],
                ),
            )
        conn.execute(
            """
            UPDATE wrong_question_practice_sheets
            SET status='ready',
                pdf_path=?,
                generation_metadata_json=?,
                generation_error='',
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (
                (pdf_path or "").strip(),
                _normalize_json_storage_value(
                    generation_metadata,
                    field_name="generation_metadata_json",
                    default="{}",
                ),
                sheet_id,
            ),
        )
        for linked_record_id in linked_record_ids:
            _refresh_wrong_question_submission_mastery_tracking(conn, linked_record_id)
    return get_wrong_question_practice_sheet(sheet_id)


def mark_wrong_question_practice_sheet_failed(sheet_id: int, error_message: str) -> Optional[dict]:
    with get_conn() as conn:
        sheet_row = _fetch_wrong_question_practice_sheet_row_by_id(conn, sheet_id)
        if not sheet_row:
            raise LookupError("wrong question practice sheet not found")
        linked_record_ids = [
            str(row["wrong_question_record_id"] or "").strip()
            for row in conn.execute(
                """
                SELECT wrong_question_record_id
                FROM wrong_question_practice_sheet_items
                WHERE sheet_id=?
                """,
                (sheet_id,),
            ).fetchall()
            if str(row["wrong_question_record_id"] or "").strip()
        ]
        conn.execute(
            """
            UPDATE wrong_question_practice_sheets
            SET status='failed',
                pdf_path='',
                generation_error=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (str(error_message or "").strip(), sheet_id),
        )
        for linked_record_id in linked_record_ids:
            _refresh_wrong_question_submission_mastery_tracking(conn, linked_record_id)
    return get_wrong_question_practice_sheet(sheet_id)


def create_wrong_question_practice_pack_job(
    *,
    organization_id: int,
    class_id: int,
    created_by: int,
    mode: str,
    target: str,
    volume: str,
) -> dict:
    normalized_mode = _normalize_practice_pack_mode(mode)
    normalized_volume = _normalize_practice_pack_volume(volume)
    normalized_target = str(target or "").strip()
    if not normalized_target:
        raise ValueError("target is required")
    requested_question_count = PRACTICE_PACK_VOLUME_COUNTS[normalized_volume]
    normalized_organization_id = int(organization_id or 0)
    normalized_class_id = int(class_id or 0)
    normalized_created_by = int(created_by or 0)
    with get_conn() as conn:
        class_row = conn.execute(
            "SELECT organization_id FROM classes WHERE id=?",
            (normalized_class_id,),
        ).fetchone()
        creator_row = conn.execute(
            "SELECT organization_id, role FROM users WHERE id=?",
            (normalized_created_by,),
        ).fetchone()
        if not class_row or not creator_row:
            raise ValueError("invalid practice pack scope")
        if int(class_row["organization_id"] or 0) != normalized_organization_id:
            raise ValueError("invalid practice pack scope")
        if (
            int(creator_row["organization_id"] or 0) != normalized_organization_id
            and str(creator_row["role"] or "") != SUPER_OWNER_ROLE
        ):
            raise ValueError("invalid practice pack scope")
        cursor = conn.execute(
            """
            INSERT INTO wrong_question_practice_pack_jobs (
                organization_id, class_id, created_by, mode, target, volume,
                requested_question_count, status, zip_path, generation_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', '', '')
            """,
            (
                normalized_organization_id,
                normalized_class_id,
                normalized_created_by,
                normalized_mode,
                normalized_target,
                normalized_volume,
                requested_question_count,
            ),
        )
        row = conn.execute(
            "SELECT * FROM wrong_question_practice_pack_jobs WHERE id=?",
            (int(cursor.lastrowid),),
        ).fetchone()
    serialized = _serialize_wrong_question_practice_pack_job_row(row)
    return serialized if serialized is not None else {}


def get_wrong_question_practice_pack_job(job_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM wrong_question_practice_pack_jobs WHERE id=?",
            (int(job_id or 0),),
        ).fetchone()
        if not row:
            return None
        student_rows = conn.execute(
            """
            SELECT *
            FROM wrong_question_practice_pack_job_students
            WHERE job_id=?
            ORDER BY student_name_snapshot ASC, student_id ASC
            """,
            (int(job_id or 0),),
        ).fetchall()
    job = _serialize_wrong_question_practice_pack_job_row(row)
    if job is None:
        return None
    job["students"] = [
        item
        for item in (_serialize_wrong_question_practice_pack_student_row(student_row) for student_row in student_rows)
        if item is not None
    ]
    return job


def list_wrong_question_practice_pack_jobs_for_class(
    *,
    organization_id: int,
    class_id: int,
    limit: int = 20,
) -> list[dict]:
    normalized_limit = max(1, min(int(limit or 20), 50))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM wrong_question_practice_pack_jobs
            WHERE organization_id=? AND class_id=?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (
                int(organization_id or 0),
                int(class_id or 0),
                normalized_limit,
            ),
        ).fetchall()
    return [
        job
        for job in (get_wrong_question_practice_pack_job(int(row["id"])) for row in rows)
        if job is not None
    ]


def find_active_wrong_question_practice_pack_job(
    *,
    organization_id: int,
    class_id: int,
    created_by: int,
    mode: str,
    target: str,
    volume: str,
) -> Optional[dict]:
    normalized_mode = _normalize_practice_pack_mode(mode)
    normalized_volume = _normalize_practice_pack_volume(volume)
    normalized_target = str(target or "").strip()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM wrong_question_practice_pack_jobs
            WHERE organization_id=?
              AND class_id=?
              AND created_by=?
              AND mode=?
              AND target=?
              AND volume=?
              AND status IN ('pending', 'running', 'ready', 'partial_failed')
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                int(organization_id or 0),
                int(class_id or 0),
                int(created_by or 0),
                normalized_mode,
                normalized_target,
                normalized_volume,
            ),
        ).fetchone()
    if not row:
        return None
    return get_wrong_question_practice_pack_job(int(row["id"]))


def mark_wrong_question_practice_pack_job_status(
    job_id: int,
    *,
    status: str,
    zip_path: str = "",
    generation_error: str = "",
) -> Optional[dict]:
    normalized_status = str(status or "").strip()
    if normalized_status not in PRACTICE_PACK_JOB_STATUSES:
        raise ValueError("invalid practice pack job status")
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE wrong_question_practice_pack_jobs
            SET status=?, zip_path=?, generation_error=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (
                normalized_status,
                str(zip_path or "").strip(),
                str(generation_error or "").strip(),
                int(job_id or 0),
            ),
        )
    return get_wrong_question_practice_pack_job(job_id)


def upsert_wrong_question_practice_pack_job_student(
    *,
    job_id: int,
    student_id: int,
    student_name_snapshot: str,
    status: str,
    requested_question_count: int,
    real_question_count: int = 0,
    variant_question_count: int = 0,
    pdf_path: str = "",
    generation_error: str = "",
) -> dict:
    normalized_status = str(status or "").strip()
    if normalized_status not in PRACTICE_PACK_STUDENT_STATUSES:
        raise ValueError("invalid practice pack student status")
    normalized_job_id = int(job_id or 0)
    normalized_student_id = int(student_id or 0)
    with get_conn() as conn:
        job_row = conn.execute(
            """
            SELECT organization_id, class_id
            FROM wrong_question_practice_pack_jobs
            WHERE id=?
            """,
            (normalized_job_id,),
        ).fetchone()
        student_row = conn.execute(
            """
            SELECT s.organization_id
            FROM students s
            JOIN class_students cs ON cs.student_id=s.id
            WHERE s.id=? AND cs.class_id=?
            """,
            (normalized_student_id, int(job_row["class_id"] or 0) if job_row else 0),
        ).fetchone()
        if not job_row or not student_row:
            raise ValueError("invalid practice pack student scope")
        if int(student_row["organization_id"] or 0) != int(job_row["organization_id"] or 0):
            raise ValueError("invalid practice pack student scope")
        conn.execute(
            """
            INSERT INTO wrong_question_practice_pack_job_students (
                job_id, student_id, student_name_snapshot, status, requested_question_count,
                real_question_count, variant_question_count, pdf_path, generation_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id, student_id)
            DO UPDATE SET
                student_name_snapshot=excluded.student_name_snapshot,
                status=excluded.status,
                requested_question_count=excluded.requested_question_count,
                real_question_count=excluded.real_question_count,
                variant_question_count=excluded.variant_question_count,
                pdf_path=excluded.pdf_path,
                generation_error=excluded.generation_error,
                updated_at=datetime('now','localtime')
            """,
            (
                normalized_job_id,
                normalized_student_id,
                str(student_name_snapshot or "").strip(),
                normalized_status,
                int(requested_question_count or 0),
                int(real_question_count or 0),
                int(variant_question_count or 0),
                str(pdf_path or "").strip(),
                str(generation_error or "").strip(),
            ),
        )
        row = conn.execute(
            """
            SELECT *
            FROM wrong_question_practice_pack_job_students
            WHERE job_id=? AND student_id=?
            """,
            (normalized_job_id, normalized_student_id),
        ).fetchone()
    serialized = _serialize_wrong_question_practice_pack_student_row(row)
    return serialized if serialized is not None else {}


def _create_member_from_invite_row(
    conn: sqlite3.Connection,
    invite_row: sqlite3.Row,
    username: str,
    display_name: str,
    password: str,
    recovery_phone: str = "",
    security_question: str = "",
    security_answer: str = "",
):
    normalized_username = _normalize_username(username)
    normalized_display_name = (display_name or "").strip()
    if not normalized_username or not normalized_display_name or not password:
        raise ValueError("join fields are required")
    normalized_phone, normalized_question, answer_hash = _normalize_account_recovery(
        recovery_phone=recovery_phone,
        security_question=security_question,
        security_answer=security_answer,
    )
    if _is_owner_username(normalized_username) or _user_exists_with_username(conn, normalized_username):
        raise ValueError("username already exists")
    if _pending_registration_exists(conn, normalized_username) or _pending_organization_request_username_exists(conn, normalized_username):
        raise ValueError("username already pending")
    cur = conn.execute(
        """
        INSERT INTO users (
            username, password_hash, display_name, role, status, organization_id,
            recovery_phone, security_question, security_answer_hash
        )
        VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """,
        (
            normalized_username,
            hash_password(password),
            normalized_display_name,
            MEMBER_ROLE,
            invite_row["organization_id"],
            normalized_phone,
            normalized_question,
            answer_hash,
        ),
    )
    user_row = _fetch_user_row_by_id(conn, cur.lastrowid)
    return _public_user_dict(user_row)


def join_organization_by_invite_code(
    invite_code: str,
    username: str,
    display_name: str,
    password: str,
    recovery_phone: str = "",
    security_question: str = "",
    security_answer: str = "",
):
    with get_conn() as conn:
        invite_row = _fetch_active_organization_invite_by_code(conn, invite_code)
        if not invite_row:
            raise LookupError("invite not found")
        return _create_member_from_invite_row(
            conn,
            invite_row,
            username,
            display_name,
            password,
            recovery_phone=recovery_phone,
            security_question=security_question,
            security_answer=security_answer,
        )


def join_organization_by_invite_link_token(
    invite_token: str,
    username: str,
    display_name: str,
    password: str,
    recovery_phone: str = "",
    security_question: str = "",
    security_answer: str = "",
):
    with get_conn() as conn:
        invite_row = _fetch_active_organization_invite_by_token(conn, invite_token)
        if not invite_row:
            raise LookupError("invite not found")
        return _create_member_from_invite_row(
            conn,
            invite_row,
            username,
            display_name,
            password,
            recovery_phone=recovery_phone,
            security_question=security_question,
            security_answer=security_answer,
        )


def create_registration_request(username: str, display_name: str, password: str,
                                organization_name: str = DEFAULT_ORGANIZATION_NAME,
                                recovery_phone: str = "",
                                security_question: str = "",
                                security_answer: str = ""):
    normalized_username = _normalize_username(username)
    with get_conn() as conn:
        org = _ensure_organization(conn, organization_name)
        if _is_owner_username(normalized_username) or _user_exists_with_username(conn, normalized_username):
            raise ValueError("用户名已存在")
        if _pending_registration_exists(conn, normalized_username):
            raise ValueError("该用户名已有待审批申请")
        normalized_phone, normalized_question, answer_hash = _normalize_account_recovery(
            recovery_phone=recovery_phone,
            security_question=security_question,
            security_answer=security_answer,
        )
        cur = conn.execute(
            """
            INSERT INTO registration_requests (
                username, password_hash, display_name, organization_id, status,
                recovery_phone, security_question, security_answer_hash
            )
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                normalized_username,
                hash_password(password),
                display_name,
                org["id"],
                normalized_phone,
                normalized_question,
                answer_hash,
            ),
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
            INSERT INTO users (
                username, password_hash, display_name, role, status, organization_id,
                recovery_phone, security_question, security_answer_hash
            )
            VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?)
            """,
            (
                req["username"],
                req["password_hash"],
                req["display_name"],
                MEMBER_ROLE,
                req["organization_id"],
                req["recovery_phone"],
                req["security_question"],
                req["security_answer_hash"],
            ),
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
        with get_conn() as attach_conn:
            d = _attach_review_plan_version_summary(attach_conn, d)
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

# ─── 命令：setup ───────────────────────────────────────────────────────────────
def cmd_setup(_args):
    init_db()
    # 读取或创建 config.json
    cfg = {}
    if CFG_PATH.exists():
        with open(CFG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)

    existing_key = cfg.get("deepseek_api_key", "")
    if existing_key:
        print(f"当前已有 API Key（前8位）：{existing_key[:8]}...")
        ans = input("是否重新设置？[y/N] ").strip().lower()
        if ans != "y":
            print("保持原有 API Key 不变。")
            return

    key = input("请输入你的 DeepSeek API Key（留空跳过）：").strip()
    if key:
        cfg["provider"] = "deepseek"
        cfg["deepseek_api_key"] = key
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"API Key 已保存到 {CFG_PATH}")
    else:
        print("跳过 API Key 设置（可后续手动编辑 config.json 或设置环境变量 DEEPSEEK_API_KEY）。")
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
    from review_plan_workflow.service import generate_single_lesson_review_plan
    plan = generate_single_lesson_review_plan(
        summary_text=raw_text,
        subject=subject,
        grade=grade,
        topic=topic,
        weak_points=weak_points,
        lesson_date=lesson_date,
    )

    # 4. 生成 PDF
    from review_plan_templates.single_lesson_pdf import build_single_lesson_pdf_filename, generate_single_lesson_pdf
    pdf_name = build_single_lesson_pdf_filename(plan)
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
    p_show = sub.add_parser("show", help="查看某节课详情")
    p_show.add_argument("--id", type=int, required=True, help="课程 ID")
    p_show.set_defaults(func=cmd_show)

    # monthly
    p_month = sub.add_parser("monthly", help="生成月度综合复习 PDF")
    p_month.add_argument("--month", help="月份 YYYY-MM（默认当月）")
    p_month.add_argument("--no-open", action="store_true", help="生成后不自动打开 PDF")
    p_month.set_defaults(func=cmd_monthly)

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
