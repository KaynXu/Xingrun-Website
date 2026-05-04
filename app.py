#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
复习计划管理系统 — 后端 / API 服务 (Flask)
启动方式：双击 start.command（macOS）或 start.bat（Windows）
前端地址：http://127.0.0.1:3000
后端地址：http://127.0.0.1:5001
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import secrets
import threading
import urllib.error
import urllib.request
import webbrowser
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from time import monotonic, sleep
from typing import Optional, Set

from flask import Flask, abort, redirect, request, send_file, jsonify
from flask_cors import CORS
from config_runtime import env_controlled_keys, get_runtime_config, load_file_config, write_file_config
import ai_processor
import pdf_engine

# ─── 路径 ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.resolve()
DATA_DIR   = BASE_DIR / "data"
PDF_DIR    = DATA_DIR / "pdfs"
UPLOAD_DIR = DATA_DIR / "uploads"
CFG_PATH   = BASE_DIR / "config.json"

for _d in (DATA_DIR, PDF_DIR, UPLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ─── Flask ────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "review_plan_local_2026"
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB
CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:8080", "http://127.0.0.1:8080",
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:3000", "http://127.0.0.1:3000",
]}})
logger = logging.getLogger(__name__)

_WRONG_QUESTION_PRACTICE_PDF_RETRY_DELAYS_SECONDS = (1, 3, 5)

# ─── 内部模块 ──────────────────────────────────────────────────────────────────
from lesson_manager import (
    actor_can_manage_user,
    attach_student_library_pdf_path,
    clean_consultation_batch_input,
    DEFAULT_ORGANIZATION_NAME,
    approve_organization_request,
    approve_registration_request,
    authenticate_user,
    bind_parent_to_student,
    confirm_class_feedback_task,
    create_class_feedback_task,
    create_pending_lesson,
    create_pending_wrong_question_practice_sheet,
    create_wechat_wrong_question_upload_task,
    create_organization_request,
    create_student_for_class,
    create_auth_session,
    create_consultation,
    create_course_calendar_custom_item,
    create_course_calendar_custom_schedule,
    create_course_calendar_schedule,
    create_registration_request,
    claim_classes_for_user,
    delete_course_calendar_custom_item,
    delete_course_calendar_schedule,
    delete_wechat_wrong_question_submission,
    delete_wrong_question_practice_sheet,
    delete_user_for_actor,
    delete_consultation,
    delete_course_calendar_custom_schedule,
    delete_class as db_delete_class,
    delete_lesson as db_delete_lesson,
    delete_organization,
    find_previous_confirmed_class_feedback_entry,
    get_class,
    get_class_feedback_task,
    get_class_teacher_user_id,
    get_conn,
    get_consultation,
    get_course_calendar_custom_item,
    get_course_calendar_custom_schedule,
    get_course_calendar_schedule,
    get_current_user,
    get_parent_student_binding,
    get_parent_student_binding_for_student,
    get_or_create_active_class_invite,
    get_lesson,
    get_weekly_wrong_question_followup_message,
    get_wrong_question_practice_sheet,
    get_or_create_active_organization_invite,
    get_organization_invite_by_token,
    get_registration_request,
    get_user_by_id,
    get_user_class_ids,
    init_db,
    list_all_users,
    list_class_feedback_label_configs,
    list_class_teacher_bindings,
    list_classes,
    list_classes_for_actor,
    list_recent_confirmed_class_feedback_summaries,
    list_consultation_teachers,
    list_consultations_for_actor,
    list_course_calendar_custom_items_for_actor,
    list_course_calendar_custom_schedules_for_actor,
    list_course_calendar_schedules_for_actor,
    list_lessons,
    list_lessons_for_actor,
    list_wrong_question_practice_sheets_for_student,
    list_organizations,
    list_organization_requests,
    list_parent_student_bindings_for_openid,
    list_primary_topic_category_suggestions,
    list_student_wrong_question_library_records,
    list_students_for_class,
    list_wechat_wrong_question_submissions_for_parent_student,
    list_wechat_wrong_question_submissions,
    list_weekly_wrong_question_followup_students,
    list_registration_requests_for_actor,
    list_unbound_classes_for_user_claim,
    list_users_for_actor,
    join_organization_by_invite_code,
    join_organization_by_invite_link_token,
    normalize_consultation_batch_parse_result,
    reject_organization_request,
    reject_registration_request,
    reset_class_invite,
    reset_organization_invite,
    remove_student_from_class,
    save_class_feedback_generation_result,
    save_class_feedback_draft,
    save_class_feedback_label_configs,
    save_class_feedback_task_notes,
    save_class,
    mark_lesson_generation_failed,
    mark_lesson_generation_succeeded,
    mark_wrong_question_practice_sheet_failed,
    mark_wrong_question_practice_sheet_succeeded,
    create_monthly_plan_job,
    get_monthly_plan_job,
    mark_monthly_plan_job_failed,
    mark_monthly_plan_job_succeeded,
    requeue_monthly_plan_job,
    set_class_teacher_user_id,
    set_student_wrong_question_library_pdf_path,
    set_user_class_ids,
    set_wechat_wrong_question_archive_status,
    get_wechat_wrong_question_submission,
    get_wechat_wrong_question_upload_task_for_openid,
    save_wechat_wrong_question_review,
    update_wechat_wrong_question_upload_task,
    update_wechat_wrong_question_question_text,
    update_wechat_wrong_question_topic_category,
    update_user_display_name_for_actor,
    update_user_visible_pages_for_actor,
    update_class,
    update_consultation,
    update_user_profile,
    resolve_teacher_username_to_user_id,
    update_user_role,
    upsert_weekly_wrong_question_followup_message,
    upsert_parent_wechat_account,
    get_teacher_alias_entries,
    upsert_teacher_alias,
    delete_teacher_alias,
    reset_user_password_by_recovery,
)
from ai_processor import parse_consultation_batch_text
import smart_wrong_questions
import master_data
from wrong_question_upload_queue import enqueue_wechat_wrong_question_upload_task
from credit_manager import (
    CreditBalanceError,
    ensure_feature_credits_available,
    finalize_ai_charge,
    get_ai_usage_by_request_id,
    get_credit_overview,
    list_credit_ledger,
    list_member_usage_detail,
    list_member_usage_summary,
    redeem_xhs_order,
)
from xhs_open_platform import fetch_xhs_order_for_redemption
from ai_processor import generate_class_feedback_bundle

init_db()

_CREDIT_REDEEM_FAILURE_MAX_ATTEMPTS = 3
_CREDIT_REDEEM_FAILURE_LOCK_SECONDS = 300.0
_CREDIT_REDEEM_FAILURE_STATE: dict[tuple[int, str], dict[str, float | int]] = {}
_CREDIT_REDEEM_FAILURE_LOCK = threading.Lock()
_AI_REQUEST_IDEMPOTENCY_WINDOW_SECONDS = 60.0
_AI_REQUEST_IDENTITY_TTL_SECONDS = 7200.0
_AI_REQUEST_IN_FLIGHT_TTL_SECONDS = 300.0
_AI_REQUEST_IN_FLIGHT: dict[str, float] = {}
_AI_REQUEST_IN_FLIGHT_LOCK = threading.Lock()
_AI_ORGANIZATION_IN_FLIGHT: dict[int, float] = {}
_AI_ORGANIZATION_IN_FLIGHT_LOCK = threading.Lock()
_N1N_PRICING_CACHE_TTL_SECONDS = 900.0
_N1N_PRICING_CACHE: dict[str, object] = {"expires_at": 0.0, "payload": {}}
_N1N_PRICING_CACHE_LOCK = threading.Lock()


# ─── 工具函数 ──────────────────────────────────────────────────────────────────
def get_config():
    return get_runtime_config()


def _default_ai_provider_name() -> str:
    return str(get_config().get("provider", "deepseek") or "deepseek")


def _default_chat_model_name() -> str:
    cfg = get_config()
    provider = _default_ai_provider_name()
    if provider == "deepseek":
        return str(cfg.get("deepseek_model", "deepseek-chat") or "deepseek-chat")
    if provider == "mimo":
        return str(cfg.get("mimo_model", "MiMo-7B-RL") or "MiMo-7B-RL")
    if provider == "n1n":
        return str(cfg.get("n1n_model", "gpt-4o") or "gpt-4o")
    return "gpt-4o"


def _normalize_ai_usage_payload(usage: object, *, provider: str, model: str) -> dict:
    usage_payload = usage if isinstance(usage, dict) else {}
    return {
        "provider": str(usage_payload.get("provider", "") or provider),
        "model": str(usage_payload.get("model", "") or model),
        "input_tokens": max(0, int(usage_payload.get("input_tokens", 0) or 0)),
        "output_tokens": max(0, int(usage_payload.get("output_tokens", 0) or 0)),
    }


def _split_ai_result_with_usage(result: object, *, provider: str, model: str) -> tuple[object, dict]:
    if (
        isinstance(result, tuple)
        and len(result) == 2
        and isinstance(result[1], dict)
    ):
        return result[0], _normalize_ai_usage_payload(result[1], provider=provider, model=model)
    return result, _normalize_ai_usage_payload({}, provider=provider, model=model)


def _fetch_n1n_pricing_payload() -> dict:
    req = urllib.request.Request(
        "https://api.n1n.ai/api/pricing_new",
        headers={"User-Agent": "Xingrun-Summary/1.0"},
    )
    with urllib.request.urlopen(req, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or not payload.get("data"):
        raise RuntimeError("invalid n1n pricing payload")
    return payload


def _get_cached_n1n_pricing_payload(force_refresh: bool = False) -> dict:
    now = monotonic()
    with _N1N_PRICING_CACHE_LOCK:
        cached_payload = _N1N_PRICING_CACHE.get("payload")
        expires_at = float(_N1N_PRICING_CACHE.get("expires_at") or 0.0)
        if not force_refresh and isinstance(cached_payload, dict) and now < expires_at:
            return cached_payload

    fresh_payload = _fetch_n1n_pricing_payload()
    with _N1N_PRICING_CACHE_LOCK:
        _N1N_PRICING_CACHE["payload"] = fresh_payload
        _N1N_PRICING_CACHE["expires_at"] = now + _N1N_PRICING_CACHE_TTL_SECONDS
    return fresh_payload


def _build_n1n_model_pricing_lookup(*, payload: dict, group_name: str) -> dict[str, dict[str, float | int | str]]:
    group_ratio_map = payload.get("group_ratio") if isinstance(payload.get("group_ratio"), dict) else {}
    group_ratio = float(group_ratio_map.get(group_name, 1.0) or 1.0)
    # Match n1n pricing page display: model_ratio is multiplied by this constant before group ratio.
    base_multiplier = 1.2

    result: dict[str, dict[str, float | int | str]] = {}
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        model_name = str(item.get("model_name") or "").strip()
        if not model_name:
            continue
        quota_type = int(item.get("quota_type") or 0)
        model_price = float(item.get("model_price") or 0.0)
        model_ratio = float(item.get("model_ratio") or 0.0)
        completion_ratio = float(item.get("completion_ratio") or 0.0)
        input_usd_per_m = model_ratio * base_multiplier * group_ratio if quota_type == 0 else 0.0
        output_usd_per_m = input_usd_per_m * completion_ratio if quota_type == 0 else 0.0
        result[model_name] = {
            "quota_type": quota_type,
            "group_name": group_name,
            "group_ratio": group_ratio,
            "input_usd_per_m": input_usd_per_m,
            "output_usd_per_m": output_usd_per_m,
            "flat_model_price_usd": model_price,
        }
    return result


class DuplicateAiRequestError(RuntimeError):
    pass


def _normalize_request_payload_for_fingerprint(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _normalize_request_payload_for_fingerprint(value[key])
            for key in sorted(value)
        }
    if isinstance(value, list):
        return [_normalize_request_payload_for_fingerprint(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_request_payload_for_fingerprint(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _uploaded_file_size(file_storage) -> int:
    content_length = getattr(file_storage, "content_length", None)
    if content_length not in (None, ""):
        try:
            return max(0, int(content_length))
        except (TypeError, ValueError):
            pass
    stream = getattr(file_storage, "stream", None)
    if not stream or not hasattr(stream, "tell") or not hasattr(stream, "seek"):
        return 0
    try:
        position = stream.tell()
        stream.seek(0, os.SEEK_END)
        size = max(0, int(stream.tell() or 0))
        stream.seek(position)
        return size
    except (OSError, ValueError):
        return 0


def _uploaded_file_content_fingerprint(file_storage) -> str:
    stream = getattr(file_storage, "stream", None)
    if not stream or not hasattr(stream, "tell") or not hasattr(stream, "seek"):
        return ""
    try:
        position = stream.tell()
        stream.seek(0)
        digest = hashlib.sha256()
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            digest.update(chunk)
        stream.seek(position)
        return digest.hexdigest()
    except (OSError, ValueError):
        return ""


def _request_payload_fingerprint(*, include_file_content: bool = False) -> str:
    payload: dict[str, object] = {
        "method": request.method,
        "path": request.path,
    }
    if request.is_json:
        payload["json"] = _normalize_request_payload_for_fingerprint(request.get_json(silent=True))
    if request.form:
        payload["form"] = {
            key: [_normalize_request_payload_for_fingerprint(item) for item in request.form.getlist(key)]
            for key in sorted(request.form.keys())
        }
    if request.files:
        files_payload = []
        for field_name in sorted(request.files.keys()):
            for storage in request.files.getlist(field_name):
                files_payload.append(
                    {
                        "field": field_name,
                        "filename": str(getattr(storage, "filename", "") or ""),
                        "content_type": str(getattr(storage, "content_type", "") or ""),
                        "size": _uploaded_file_size(storage),
                        "content_sha256": (
                            _uploaded_file_content_fingerprint(storage)
                            if include_file_content
                            else ""
                        ),
                    }
                )
        payload["files"] = files_payload
    serialized = json.dumps(
        _normalize_request_payload_for_fingerprint(payload),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _ai_fallback_request_bucket() -> int:
    return int(monotonic() // _AI_REQUEST_IDEMPOTENCY_WINDOW_SECONDS)


def _current_ai_request_key() -> str:
    request_key = str(request.environ.get("_credit_request_key") or "").strip()
    if request_key:
        return request_key
    header_key = (
        request.headers.get("X-Request-Id", "").strip()
        or request.headers.get("Idempotency-Key", "").strip()
    )
    payload_fingerprint = _request_payload_fingerprint()
    if header_key:
        request_key = f"header:{header_key}:{payload_fingerprint}"
    else:
        request_key = f"fallback:{_ai_fallback_request_bucket()}:{payload_fingerprint}"
    request.environ["_credit_request_key"] = request_key
    return request_key


def _current_audio_upload_request_key() -> str:
    request_key = str(request.environ.get("_credit_request_key") or "").strip()
    if request_key:
        return request_key
    header_key = (
        request.headers.get("X-Request-Id", "").strip()
        or request.headers.get("Idempotency-Key", "").strip()
    )
    payload_fingerprint = _request_payload_fingerprint(include_file_content=True)
    if header_key:
        request_key = f"header:{header_key}:{payload_fingerprint}"
    else:
        request_key = f"audio-fallback:{payload_fingerprint}"
    request.environ["_credit_request_key"] = request_key
    return request_key


def _build_ai_charge_request_id(
    *,
    user_id: int,
    feature_key: str,
    source_record_type: str,
    source_record_id: int | str,
    request_key: str | None = None,
) -> str:
    raw_value = (
        f"{user_id}:{request_key or _current_ai_request_key()}:"
        f"{feature_key}:{source_record_type}:{source_record_id}"
    )
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def _build_review_plan_request_id(*, user_id: int, request_key: str) -> str:
    return _build_ai_charge_request_id(
        user_id=user_id,
        feature_key="lesson_plan_generate",
        source_record_type="lesson_request",
        source_record_id="pending",
        request_key=request_key,
    )


def _claim_ai_request_identity(*, organization_id: int, request_id: str) -> None:
    now = monotonic()
    with _AI_REQUEST_IN_FLIGHT_LOCK:
        expired = [
            key
            for key, started_at in _AI_REQUEST_IN_FLIGHT.items()
            if (now - started_at) > _AI_REQUEST_IDENTITY_TTL_SECONDS
        ]
        for key in expired:
            _AI_REQUEST_IN_FLIGHT.pop(key, None)
        if request_id in _AI_REQUEST_IN_FLIGHT:
            raise DuplicateAiRequestError("重复请求正在处理中，请勿重复提交")
        existing_usage = get_ai_usage_by_request_id(
            organization_id=organization_id,
            request_id=request_id,
        )
        if existing_usage:
            raise DuplicateAiRequestError("重复请求已处理，请勿重复提交")
        _AI_REQUEST_IN_FLIGHT[request_id] = now


def _release_ai_request_identity(request_id: str) -> None:
    with _AI_REQUEST_IN_FLIGHT_LOCK:
        _AI_REQUEST_IN_FLIGHT.pop(request_id, None)


def _claim_ai_organization_execution(organization_id: int) -> None:
    now = monotonic()
    with _AI_ORGANIZATION_IN_FLIGHT_LOCK:
        expired = [
            org_id
            for org_id, started_at in _AI_ORGANIZATION_IN_FLIGHT.items()
            if (now - started_at) > _AI_REQUEST_IN_FLIGHT_TTL_SECONDS
        ]
        for org_id in expired:
            _AI_ORGANIZATION_IN_FLIGHT.pop(org_id, None)
        if organization_id in _AI_ORGANIZATION_IN_FLIGHT:
            raise DuplicateAiRequestError("当前机构已有 AI 请求正在处理中，请稍后再试")
        _AI_ORGANIZATION_IN_FLIGHT[organization_id] = now


def _release_ai_organization_execution(organization_id: int) -> None:
    with _AI_ORGANIZATION_IN_FLIGHT_LOCK:
        _AI_ORGANIZATION_IN_FLIGHT.pop(organization_id, None)


def _call_ai_helper_with_usage(helper, /, *args, **kwargs):
    try:
        return helper(*args, include_usage=True, **kwargs)
    except TypeError as exc:
        if "include_usage" not in str(exc):
            raise
        return helper(*args, **kwargs)


def _run_ai_feature_with_charge(
    *,
    user: dict,
    feature_key: str,
    source_record_type: str,
    source_record_id: int | str,
    producer,
    provider: str,
    model: str,
    after_success=None,
    request_key: str | None = None,
    request_id: str | None = None,
    claim_request_identity: bool = True,
):
    organization_id = int(user["organization_id"])
    request_id = request_id or _build_ai_charge_request_id(
        user_id=int(user["id"]),
        feature_key=feature_key,
        source_record_type=source_record_type,
        source_record_id=source_record_id,
        request_key=request_key,
    )
    if claim_request_identity:
        _claim_ai_request_identity(
            organization_id=organization_id,
            request_id=request_id,
        )
    try:
        _claim_ai_organization_execution(organization_id)
        ensure_feature_credits_available(
            organization_id=organization_id,
            feature_key=feature_key,
        )
        result = producer()
        business_value, usage = _split_ai_result_with_usage(result, provider=provider, model=model)
        if after_success is not None:
            after_success(business_value)
        finalize_ai_charge(
            organization_id=organization_id,
            user_id=int(user["id"]),
            feature_key=feature_key,
            usage=usage,
            source_record_type=source_record_type,
            source_record_id=source_record_id,
            request_id=request_id,
        )
        return business_value
    finally:
        _release_ai_organization_execution(organization_id)
        if claim_request_identity:
            _release_ai_request_identity(request_id)


def _run_review_plan_generation_job(
    *,
    lesson_id: int,
    user: dict,
    chat_provider: str,
    chat_model: str,
    request_key: str | None = None,
    request_id: str | None = None,
) -> None:
    try:
        lesson = get_lesson(lesson_id)
        if not lesson:
            logger.warning("Review plan generation skipped: lesson %s not found", lesson_id)
            return
        if lesson.get("record_status") != "pending":
            logger.info(
                "Review plan generation skipped for lesson %s with status %s",
                lesson_id,
                lesson.get("record_status"),
            )
            return

        lesson_date = str(lesson.get("date") or "")
        subject = str(lesson.get("subject") or "")
        grade = str(lesson.get("grade") or "")
        topic = str(lesson.get("topic") or "")
        weak_points = str(lesson.get("weak_points") or "")
        raw_text = str(lesson.get("summary") or "")

        from ai_processor import parse_and_generate_plan
        try:
            plan = _run_ai_feature_with_charge(
                user=user,
                feature_key="lesson_plan_generate",
                source_record_type="lesson",
                source_record_id=lesson_id,
                producer=lambda: _call_ai_helper_with_usage(
                    parse_and_generate_plan,
                    summary_text=raw_text,
                    subject=subject,
                    grade=grade,
                    topic=topic,
                    weak_points=weak_points,
                    lesson_date=lesson_date,
                ),
                provider=chat_provider,
                model=chat_model,
                request_key=request_key,
                request_id=request_id,
                claim_request_identity=request_id is None,
            )
        except DuplicateAiRequestError as exc:
            logger.exception("Review plan AI request rejected for lesson %s", lesson_id)
            try:
                mark_lesson_generation_failed(lesson_id, str(exc))
            except LookupError:
                logger.exception("Failed to mark lesson %s as failed after duplicate request", lesson_id)
            return
        except CreditBalanceError as exc:
            logger.exception("Review plan credit preflight failed for lesson %s", lesson_id)
            try:
                mark_lesson_generation_failed(lesson_id, str(exc))
            except LookupError:
                logger.exception("Failed to mark lesson %s as failed after credit error", lesson_id)
            return
        except Exception:
            logger.exception("Review plan AI generation failed for lesson %s", lesson_id)
            try:
                mark_lesson_generation_failed(lesson_id, "AI 生成失败，请稍后重试")
            except LookupError:
                logger.exception("Failed to mark lesson %s as failed after AI error", lesson_id)
            return

        from review_plan_templates.single_lesson_pdf import generate_single_lesson_pdf
        try:
            safe = (topic or "课程").replace("/", "-").replace(" ", "_")[:28]
            pdf_name = f"{lesson_date}_{subject}_{safe}.pdf"
            pdf_path = str(PDF_DIR / pdf_name)
            generate_single_lesson_pdf(plan, pdf_path)
        except Exception:
            logger.exception("Review plan PDF generation failed for lesson %s", lesson_id)
            try:
                mark_lesson_generation_failed(lesson_id, "PDF 生成失败，请稍后重试")
            except LookupError:
                logger.exception("Failed to mark lesson %s as failed after PDF error", lesson_id)
            return

        try:
            mark_lesson_generation_succeeded(
                lesson_id,
                plan=plan,
                pdf_path=pdf_path,
            )
        except LookupError:
            logger.exception("Failed to mark lesson %s as ready", lesson_id)
    finally:
        if request_id is not None:
            _release_ai_request_identity(request_id)


def _start_review_plan_generation_thread(**job_kwargs) -> None:
    threading.Thread(
        target=_run_review_plan_generation_job,
        kwargs=job_kwargs,
        daemon=True,
    ).start()


def _run_wrong_question_practice_generation_job(
    *,
    sheet_id: int,
    user: dict,
) -> None:
    try:
        sheet = get_wrong_question_practice_sheet(sheet_id)
        if not sheet or sheet.get("status") != "pending":
            logger.info("Wrong question practice generation skipped for sheet %s", sheet_id)
            return

        organization_id = int(user["organization_id"])
        feature_key = "wrong_question_practice_generate"
        provider = _default_ai_provider_name()
        model = _default_chat_model_name()
        request_id = _build_ai_charge_request_id(
            user_id=int(user["id"]),
            feature_key=feature_key,
            source_record_type="wrong_question_practice_sheet",
            source_record_id=sheet_id,
            request_key=f"wrong-question-practice:{sheet_id}",
        )
        request_identity_claimed = False
        organization_execution_claimed = False
        try:
            try:
                _claim_ai_request_identity(
                    organization_id=organization_id,
                    request_id=request_id,
                )
                request_identity_claimed = True
                _claim_ai_organization_execution(organization_id)
                organization_execution_claimed = True
                ensure_feature_credits_available(
                    organization_id=organization_id,
                    feature_key=feature_key,
                )
                generated_result = _call_ai_helper_with_usage(
                    ai_processor.generate_wrong_question_practice_sheet_material,
                    student_name=str(sheet.get("student_name_snapshot") or ""),
                    class_name=str(sheet.get("class_name_snapshot") or ""),
                    teacher_name=str(sheet.get("teacher_name_snapshot") or ""),
                    items=sheet.get("items") or [],
                )
                generated, usage = _split_ai_result_with_usage(
                    generated_result,
                    provider=provider,
                    model=model,
                )
            except DuplicateAiRequestError as exc:
                logger.exception("Wrong question practice AI request rejected for sheet %s", sheet_id)
                try:
                    mark_wrong_question_practice_sheet_failed(sheet_id, str(exc))
                except LookupError:
                    logger.exception("Failed to mark wrong question practice sheet %s as failed", sheet_id)
                return
            except CreditBalanceError as exc:
                logger.exception("Wrong question practice credit preflight failed for sheet %s", sheet_id)
                try:
                    mark_wrong_question_practice_sheet_failed(sheet_id, str(exc))
                except LookupError:
                    logger.exception("Failed to mark wrong question practice sheet %s as failed", sheet_id)
                return
            except Exception:
                logger.exception("Wrong question practice AI generation failed for sheet %s", sheet_id)
                try:
                    mark_wrong_question_practice_sheet_failed(sheet_id, "AI 生成失败，请稍后重试")
                except LookupError:
                    logger.exception("Failed to mark wrong question practice sheet %s as failed", sheet_id)
                return
            finally:
                if organization_execution_claimed:
                    _release_ai_organization_execution(organization_id)
                    organization_execution_claimed = False

            generated_items = generated.get("items") if isinstance(generated, dict) else None
            if not isinstance(generated_items, list) or not generated_items:
                mark_wrong_question_practice_sheet_failed(sheet_id, "AI 生成失败，请稍后重试")
                return

            generated_item_by_record_id = {
                str(item.get("wrong_question_record_id") or "").strip(): item
                for item in generated_items
                if isinstance(item, dict) and str(item.get("wrong_question_record_id") or "").strip()
            }
            merged_items = []
            for item in sheet.get("items") or []:
                if not isinstance(item, dict):
                    continue
                record_id = str(item.get("wrong_question_record_id") or "").strip()
                generated_item = generated_item_by_record_id.get(record_id)
                if not generated_item:
                    mark_wrong_question_practice_sheet_failed(sheet_id, "AI 生成失败，请稍后重试")
                    return
                merged_items.append(
                    {
                        **item,
                        "ai_hint": str(generated_item.get("ai_hint") or "").strip(),
                        "reason_blank_prompt": str(generated_item.get("reason_blank_prompt") or "").strip(),
                        "improvement_summary_prompt": str(generated_item.get("improvement_summary_prompt") or "").strip(),
                    }
                )

            title = str((generated or {}).get("title") or "").strip() or f"{sheet.get('student_name_snapshot') or '学生'} 错题练习"
            output_path = str(_wrong_question_practice_sheet_pdf_path(sheet_id))

            pdf_path = ""
            pdf_generation_succeeded = False
            total_pdf_attempts = len(_WRONG_QUESTION_PRACTICE_PDF_RETRY_DELAYS_SECONDS) + 1
            for attempt in range(total_pdf_attempts):
                try:
                    pdf_path = pdf_engine.generate_wrong_question_practice_sheet_pdf(
                        student_name=str(sheet.get("student_name_snapshot") or ""),
                        class_name=str(sheet.get("class_name_snapshot") or ""),
                        teacher_name=str(sheet.get("teacher_name_snapshot") or ""),
                        title=title,
                        items=merged_items,
                        output_path=output_path,
                    )
                    pdf_generation_succeeded = True
                    break
                except Exception:
                    logger.exception(
                        "Wrong question practice PDF generation failed for sheet %s (attempt %s/%s)",
                        sheet_id,
                        attempt + 1,
                        total_pdf_attempts,
                    )
                    if attempt >= total_pdf_attempts - 1:
                        mark_wrong_question_practice_sheet_failed(sheet_id, "PDF 生成失败，请稍后重试")
                        return
                    try:
                        Path(output_path).unlink(missing_ok=True)
                    except OSError:
                        logger.exception(
                            "Failed to remove partial wrong question practice PDF for sheet %s",
                            sheet_id,
                        )
                    sleep(_WRONG_QUESTION_PRACTICE_PDF_RETRY_DELAYS_SECONDS[attempt])

            if not pdf_generation_succeeded:
                mark_wrong_question_practice_sheet_failed(sheet_id, "PDF 生成失败，请稍后重试")
                return

            try:
                finalize_ai_charge(
                    organization_id=organization_id,
                    user_id=int(user["id"]),
                    feature_key=feature_key,
                    usage=usage,
                    source_record_type="wrong_question_practice_sheet",
                    source_record_id=sheet_id,
                    request_id=request_id,
                )
            except CreditBalanceError as exc:
                logger.exception("Wrong question practice charge finalization failed for sheet %s", sheet_id)
                try:
                    mark_wrong_question_practice_sheet_failed(sheet_id, str(exc))
                except LookupError:
                    logger.exception("Failed to mark wrong question practice sheet %s as failed", sheet_id)
                return
            except Exception:
                logger.exception("Wrong question practice charge finalization failed for sheet %s", sheet_id)
                try:
                    mark_wrong_question_practice_sheet_failed(sheet_id, "AI 生成失败，请稍后重试")
                except LookupError:
                    logger.exception("Failed to mark wrong question practice sheet %s as failed", sheet_id)
                return

            mark_wrong_question_practice_sheet_succeeded(
                sheet_id,
                generated_items=generated_items,
                pdf_path=str(pdf_path or "").strip(),
            )
        finally:
            if organization_execution_claimed:
                _release_ai_organization_execution(organization_id)
            if request_identity_claimed:
                _release_ai_request_identity(request_id)
    except Exception:
        logger.exception("Wrong question practice generation failed for sheet %s", sheet_id)
        try:
            mark_wrong_question_practice_sheet_failed(sheet_id, "AI 生成失败，请稍后重试")
        except LookupError:
            logger.exception("Failed to mark wrong question practice sheet %s as failed", sheet_id)


def _start_wrong_question_practice_generation_thread(**job_kwargs) -> None:
    threading.Thread(
        target=_run_wrong_question_practice_generation_job,
        kwargs=job_kwargs,
        daemon=True,
    ).start()


def _run_monthly_plan_generation_job(
    *,
    job_id: int,
    user: dict,
    month_str: str,
    lesson_dicts: list[dict],
    chat_provider: str,
    chat_model: str,
) -> None:
    try:
        job = get_monthly_plan_job(job_id)
        if not job or job.get("status") != "pending":
            logger.info("Monthly plan generation skipped for job %s", job_id)
            return

        from ai_processor import generate_monthly_plan
        organization_id = int(user["organization_id"])
        request_id = _build_ai_charge_request_id(
            user_id=int(user["id"]),
            feature_key="monthly_plan_generate",
            source_record_type="monthly_plan",
            source_record_id=job_id,
            request_key=f"monthly-job:{job_id}",
        )
        request_identity_claimed = False
        organization_execution_claimed = False
        try:
            _claim_ai_request_identity(
                organization_id=organization_id,
                request_id=request_id,
            )
            request_identity_claimed = True
            _claim_ai_organization_execution(organization_id)
            organization_execution_claimed = True
            ensure_feature_credits_available(
                organization_id=organization_id,
                feature_key="monthly_plan_generate",
            )
            result = _call_ai_helper_with_usage(
                generate_monthly_plan,
                lesson_dicts,
                month_str,
            )
            plan, usage = _split_ai_result_with_usage(
                result,
                provider=chat_provider,
                model=chat_model,
            )
        except DuplicateAiRequestError as exc:
            logger.exception("Monthly plan AI request rejected for job %s", job_id)
            try:
                mark_monthly_plan_job_failed(job_id, str(exc))
            except LookupError:
                logger.exception("Failed to mark monthly job %s as failed", job_id)
            return
        except CreditBalanceError as exc:
            logger.exception("Monthly plan credit preflight failed for job %s", job_id)
            try:
                mark_monthly_plan_job_failed(job_id, str(exc))
            except LookupError:
                logger.exception("Failed to mark monthly job %s as failed", job_id)
            return
        except Exception:
            logger.exception("Monthly plan AI generation failed for job %s", job_id)
            try:
                mark_monthly_plan_job_failed(job_id, "AI 生成失败，请稍后重试")
            except LookupError:
                logger.exception("Failed to mark monthly job %s as failed", job_id)
            return
        finally:
            if organization_execution_claimed:
                _release_ai_organization_execution(organization_id)

        try:
            from pdf_engine import generate_monthly_pdf

            try:
                pdf_name = f"{month_str}_月度综合复习.pdf"
                generate_monthly_pdf(plan, str(PDF_DIR / pdf_name))
            except Exception:
                logger.exception("Monthly plan PDF generation failed for job %s", job_id)
                try:
                    mark_monthly_plan_job_failed(job_id, "PDF 生成失败，请稍后重试")
                except LookupError:
                    logger.exception("Failed to mark monthly job %s as failed", job_id)
                return

            try:
                finalize_ai_charge(
                    organization_id=organization_id,
                    user_id=int(user["id"]),
                    feature_key="monthly_plan_generate",
                    usage=usage,
                    source_record_type="monthly_plan",
                    source_record_id=job_id,
                    request_id=request_id,
                )
                mark_monthly_plan_job_succeeded(job_id, pdf_filename=pdf_name)
            except CreditBalanceError as exc:
                logger.exception("Monthly plan charge finalization failed for job %s", job_id)
                try:
                    mark_monthly_plan_job_failed(job_id, str(exc))
                except LookupError:
                    logger.exception("Failed to mark monthly job %s as failed", job_id)
            except Exception:
                logger.exception("Monthly plan charge finalization failed for job %s", job_id)
                try:
                    mark_monthly_plan_job_failed(job_id, "AI 生成失败，请稍后重试")
                except LookupError:
                    logger.exception("Failed to mark monthly job %s as failed", job_id)
        finally:
            if request_identity_claimed:
                _release_ai_request_identity(request_id)
    except Exception:
        logger.exception("Unexpected error in monthly plan generation job %s", job_id)


def _start_monthly_plan_generation_thread(**job_kwargs) -> None:
    threading.Thread(
        target=_run_monthly_plan_generation_job,
        kwargs=job_kwargs,
        daemon=True,
    ).start()


def has_api_key():
    cfg = get_config()
    provider = cfg.get("provider", "deepseek")
    if provider == "deepseek":
        key = cfg.get("deepseek_api_key", "") or os.environ.get("DEEPSEEK_API_KEY", "")
    elif provider == "mimo":
        key = cfg.get("mimo_api_key", "") or os.environ.get("MIMO_API_KEY", "")
    elif provider == "n1n":
        key = cfg.get("n1n_api_key", "") or os.environ.get("N1N_API_KEY", "")
    else:
        key = cfg.get("openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
    return bool(key.strip())


def _extract_field(text, field):
    m = re.search(rf"(?:^|\n)\s*{re.escape(field)}\s*[：:]\s*(.+)", text)
    return m.group(1).strip() if m else ""


def _get_all_months():
    lessons = list_lessons()
    return sorted(
        set(l["date"][:7] for l in lessons if l.get("date")), reverse=True
    )


def _get_monthly_pdfs():
    """返回 {month_str: filename} 的已有月度 PDF 列表。"""
    result = {}
    for p in PDF_DIR.glob("????-??_月度综合复习.pdf"):
        m = re.match(r"(\d{4}-\d{2})_月度综合复习\.pdf", p.name)
        if m:
            result[m.group(1)] = p.name
    return result


@app.route("/")
def index():
    return redirect(_browser_url(), code=302)


# ─── PDF 查看 / 下载 ────────────────────────────────────────────────────────────
@app.route("/pdf/<int:lesson_id>")
@app.route("/api/pdf/<int:lesson_id>")
def serve_pdf(lesson_id):
    if request.path.startswith("/api/"):
        user, error = _require_auth()
        if error:
            return error
    else:
        user = None
    lesson = get_lesson(lesson_id)
    if not lesson:
        abort(404)
    if user is not None and not _can_access_lesson(user, lesson):
        abort(404)
    pdf_path = lesson.get("pdf_path", "")
    if not pdf_path or not Path(pdf_path).exists():
        abort(404)
    return send_file(pdf_path, mimetype="application/pdf",
                     download_name=Path(pdf_path).name)


@app.route("/pdf/download/<int:lesson_id>")
@app.route("/api/pdf/download/<int:lesson_id>")
def download_pdf(lesson_id):
    if request.path.startswith("/api/"):
        user, error = _require_auth()
        if error:
            return error
    else:
        user = None
    lesson = get_lesson(lesson_id)
    if not lesson:
        abort(404)
    if user is not None and not _can_access_lesson(user, lesson):
        abort(404)
    pdf_path = lesson.get("pdf_path", "")
    if not pdf_path or not Path(pdf_path).exists():
        abort(404)
    return send_file(pdf_path, as_attachment=True,
                     download_name=Path(pdf_path).name)


@app.route("/pdf/answer/<int:lesson_id>")
@app.route("/api/pdf/answer/<int:lesson_id>")
def serve_answer_pdf(lesson_id):
    lesson = get_lesson(lesson_id)
    if not lesson:
        abort(404)
    pdf_path = lesson.get("pdf_path", "")
    if not pdf_path:
        abort(404)
    answer_path = pdf_path.replace(".pdf", "_答案版.pdf")
    if not Path(answer_path).exists():
        abort(404)
    return send_file(answer_path, mimetype="application/pdf",
                     download_name=Path(answer_path).name)


@app.route("/pdf/download/answer/<int:lesson_id>")
@app.route("/api/pdf/download/answer/<int:lesson_id>")
def download_answer_pdf(lesson_id):
    lesson = get_lesson(lesson_id)
    if not lesson:
        abort(404)
    pdf_path = lesson.get("pdf_path", "")
    if not pdf_path:
        abort(404)
    answer_path = pdf_path.replace(".pdf", "_答案版.pdf")
    if not Path(answer_path).exists():
        abort(404)
    return send_file(answer_path, as_attachment=True,
                     download_name=Path(answer_path).name)


# ─── JSON API ──────────────────────────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    user, error = authenticate_user(username=username, password=password)
    if not user:
        return jsonify({"error": error}), 401
    token = create_auth_session(user["id"])
    return jsonify({"token": token, "user": user})


def _is_recovery_setup_error(message: str) -> bool:
    return "找回密码" in message or "电话号码" in message or "密保" in message


@app.route("/api/password-reset", methods=["POST"])
def api_password_reset():
    data = request.json or {}
    username = data.get("username", "").strip()
    new_password = data.get("new_password", "").strip()
    try:
        reset_user_password_by_recovery(
            username=username,
            new_password=new_password,
            recovery_phone=(data.get("recovery_phone") or "").strip(),
            security_question=(data.get("security_question") or "").strip(),
            security_answer=(data.get("security_answer") or "").strip(),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True})


@app.route("/api/register-request", methods=["POST"])
def api_register_request():
    data = request.json or {}
    username = data.get("username", "").strip()
    display_name = data.get("display_name", "").strip()
    password = data.get("password", "").strip()
    organization_name = data.get("organization_name", "").strip() or DEFAULT_ORGANIZATION_NAME

    if not username or not display_name or not password:
        return jsonify({"error": "请填写完整的注册信息"}), 400
    if len(password) < 6:
        return jsonify({"error": "密码至少需要 6 位"}), 400
    if organization_name != DEFAULT_ORGANIZATION_NAME:
        return jsonify({"error": "当前仅支持加入星润Starain"}), 400
    try:
        item = create_registration_request(
            username=username,
            display_name=display_name,
            password=password,
            organization_name=organization_name,
            recovery_phone=(data.get("recovery_phone") or "").strip(),
            security_question=(data.get("security_question") or "").strip(),
            security_answer=(data.get("security_answer") or "").strip(),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400 if _is_recovery_setup_error(str(exc)) else 409
    return jsonify({"id": item["id"], "status": item["status"]}), 201


@app.route("/api/organization-requests", methods=["POST"])
def api_organization_request_create():
    data = request.json or {}
    organization_name = data.get("organization_name", "").strip()
    username = data.get("username", "").strip()
    display_name = data.get("display_name", "").strip()
    password = data.get("password", "").strip()

    if not organization_name or not username or not display_name or not password:
        return jsonify({"error": "organization_name, username, display_name and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400
    try:
        item = create_organization_request(
            organization_name=organization_name,
            username=username,
            display_name=display_name,
            password=password,
            recovery_phone=(data.get("recovery_phone") or "").strip(),
            security_question=(data.get("security_question") or "").strip(),
            security_answer=(data.get("security_answer") or "").strip(),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400 if _is_recovery_setup_error(str(exc)) else 409
    return jsonify({"id": item["id"], "status": item["status"]}), 201


@app.route("/api/invite/<invite_token>", methods=["GET"])
def api_invite_preview(invite_token: str):
    invite = get_organization_invite_by_token(invite_token)
    if not invite:
        return jsonify({"error": "invite not found"}), 404
    return jsonify({"organization_name": invite["organization_name"]})


@app.route("/api/join-by-invite-code", methods=["POST"])
def api_join_by_invite_code():
    data = request.json or {}
    invite_code = data.get("invite_code", "").strip()
    username = data.get("username", "").strip()
    display_name = data.get("display_name", "").strip()
    password = data.get("password", "").strip()
    if not invite_code or not username or not display_name or not password:
        return jsonify({"error": "invite_code, username, display_name and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400
    try:
        user = join_organization_by_invite_code(
            invite_code=invite_code,
            username=username,
            display_name=display_name,
            password=password,
            recovery_phone=(data.get("recovery_phone") or "").strip(),
            security_question=(data.get("security_question") or "").strip(),
            security_answer=(data.get("security_answer") or "").strip(),
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400 if _is_recovery_setup_error(str(exc)) else 409
    return jsonify({"user": user}), 201


@app.route("/api/join-by-invite-link/<invite_token>", methods=["POST"])
def api_join_by_invite_link(invite_token: str):
    data = request.json or {}
    username = data.get("username", "").strip()
    display_name = data.get("display_name", "").strip()
    password = data.get("password", "").strip()
    if not username or not display_name or not password:
        return jsonify({"error": "username, display_name and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400
    try:
        user = join_organization_by_invite_link_token(
            invite_token=invite_token,
            username=username,
            display_name=display_name,
            password=password,
            recovery_phone=(data.get("recovery_phone") or "").strip(),
            security_question=(data.get("security_question") or "").strip(),
            security_answer=(data.get("security_answer") or "").strip(),
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400 if _is_recovery_setup_error(str(exc)) else 409
    return jsonify({"user": user}), 201


def _require_auth():
    token = (
        request.headers.get("X-Auth-Token", "").strip()
        or request.args.get("token", "").strip()
    )
    user = get_current_user(token)
    if not user:
        return None, (jsonify({"error": "未授权"}), 401)
    return user, None


def _require_staff():
    user, error = _require_auth()
    if error:
        return None, error
    if user.get("role") not in {"super_owner", "owner", "admin"}:
        return None, (jsonify({"error": "无权限"}), 403)
    return user, None


def _require_owner():
    user, error = _require_auth()
    if error:
        return None, error
    if user.get("role") not in {"super_owner", "owner"}:
        return None, (jsonify({"error": "无权限"}), 403)
    return user, None


def _require_super_owner():
    user, error = _require_auth()
    if error:
        return None, error
    if user.get("role") != "super_owner":
        return None, (jsonify({"error": "无权限"}), 403)
    return user, None


def _require_wechat_service():
    expected = str(get_runtime_config().get("wechat_service_token", "")).strip()
    provided = request.headers.get("X-Wechat-Service-Token", "").strip()
    if not expected or provided != expected:
        return None, (jsonify({"error": "unauthorized"}), 401)
    return {"service": "wechat"}, None


def _organization_invite_response_payload(invite: dict) -> dict:
    join_path = f"/join/{invite['invite_token']}"
    base_url = request.url_root.rstrip("/")
    return {
        "organization_name": invite["organization_name"],
        "invite_code": invite["invite_code"],
        "invite_link": f"{base_url}{join_path}",
        "join_path": join_path,
    }


def _can_access_wrong_question_record(
    user,
    record: object,
    owned_class_ids: Optional[Set[int]] = None,
    allowed_user_ids: Optional[Set[int]] = None,
) -> bool:
    if user.get("role") == "super_owner":
        return True
    if not isinstance(record, dict):
        return False

    if user.get("role") in {"owner", "admin"}:
        scoped_class_ids = owned_class_ids
        if scoped_class_ids is None:
            scoped_class_ids = {item["id"] for item in list_classes_for_actor(user)}
        scoped_user_ids = allowed_user_ids
        if scoped_user_ids is None:
            scoped_user_ids = {item["id"] for item in list_users_for_actor(user)}
        teacher_user_id = record.get("teacher_user_id")
        if isinstance(teacher_user_id, int) and teacher_user_id in scoped_user_ids:
            return True
        class_id = record.get("class_id")
        return isinstance(class_id, int) and class_id in scoped_class_ids

    teacher_user_id = record.get("teacher_user_id")
    if isinstance(teacher_user_id, int) and teacher_user_id == user.get("id"):
        return True

    class_id = record.get("class_id")
    if isinstance(class_id, int):
        member_class_ids = owned_class_ids
        if member_class_ids is None:
            member_class_ids = set(get_user_class_ids(user["id"]))
        return class_id in member_class_ids

    return False


def _summarize_wrong_question_records(items: list[dict]) -> dict[str, int]:
    summary = {
        "total_count": 0,
        "repeated_mistake_count": 0,
        "high_priority_count": 0,
        "pending_review_count": 0,
        "unique_class_count": 0,
        "unique_student_count": 0,
    }
    class_keys: set[str] = set()
    student_keys: set[str] = set()

    for item in items:
        analysis = item.get("analysis") if isinstance(item.get("analysis"), dict) else {}
        summary["total_count"] += 1

        class_name = str(item.get("class_name") or item.get("className") or "").strip()
        class_id = item.get("class_id") if item.get("class_id") is not None else item.get("classId")
        if class_id is not None:
            class_keys.add(str(class_id))
        elif class_name:
            class_keys.add(class_name)

        student_name = str(item.get("student_name") or item.get("studentName") or "").strip()
        if student_name:
            student_keys.add(student_name)

        repeated_mistake = str(
            analysis.get("is_repeated_mistake")
            or analysis.get("isRepeatedMistake")
            or ""
        ).strip()
        if repeated_mistake and repeated_mistake != "否":
            summary["repeated_mistake_count"] += 1

        teacher_priority = str(
            analysis.get("teacher_priority")
            or analysis.get("teacherPriority")
            or ""
        ).strip()
        if teacher_priority == "高":
            summary["high_priority_count"] += 1

        selected_error_type = str(
            analysis.get("selected_error_type")
            or analysis.get("selectedErrorType")
            or ""
        ).strip()
        if not selected_error_type:
            summary["pending_review_count"] += 1

    summary["unique_class_count"] = len(class_keys)
    summary["unique_student_count"] = len(student_keys)

    return summary


def _filter_wrong_question_items_for_user(user, items: object) -> list[dict]:
    if not isinstance(items, list):
        return []
    if user.get("role") == "super_owner":
        return [item for item in items if isinstance(item, dict)]
    if user.get("role") in {"owner", "admin"}:
        user_organization_id = user.get("organization_id")

        def _normalize_organization_id(value):
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                stripped = value.strip()
                if stripped.isdigit():
                    return int(stripped)
            return None

        return [
            item
            for item in items
            if isinstance(item, dict)
            and (
                _normalize_organization_id(item.get("organization_id")) is None
                or _normalize_organization_id(item.get("organization_id")) == user_organization_id
            )
        ]

    owned_class_ids = set(get_user_class_ids(user["id"]))
    return [
        item
        for item in items
        if isinstance(item, dict) and _can_access_wrong_question_record(user, item, owned_class_ids)
    ]


def _filter_classes_for_user(user, classes: list[dict]) -> list[dict]:
    if user.get("role") == "super_owner":
        return classes
    if user.get("role") in {"owner", "admin"}:
        return [
            item
            for item in classes
            if item.get("organization_id") == user.get("organization_id")
        ]

    owned_class_ids = set(get_user_class_ids(user["id"]))
    return [item for item in classes if item.get("id") in owned_class_ids]


def _parse_week_start(raw_value: str) -> date:
    value = str(raw_value or "").strip()
    selected = date.today() if not value else date.fromisoformat(value)
    return selected - timedelta(days=selected.weekday())


def _weekly_range(raw_week_start: str) -> tuple[str, str]:
    week_start = _parse_week_start(raw_week_start)
    week_end = week_start + timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


def _safe_archive_filename_part(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "-", str(value or "")).strip()
    return cleaned or "未命名"


def _require_accessible_class(user: dict, class_id: int) -> Optional[dict]:
    cls = get_class(class_id)
    if not cls:
        return None
    scoped = _filter_classes_for_user(user, [cls])
    return scoped[0] if scoped else None


def _weekly_followup_message_payload(message: Optional[dict]) -> Optional[dict]:
    if not isinstance(message, dict):
        return None
    payload = dict(message)
    payload.pop("source_record_ids_json", None)
    return payload


def _weekly_followup_item_payload(item: dict, message: Optional[dict]) -> dict:
    source_record_ids = [
        str(record_id).strip()
        for record_id in item.get("source_record_ids", [])
        if str(record_id or "").strip()
    ]
    student_id = int(item.get("student_id") or 0)
    return {
        "organization_id": item.get("organization_id"),
        "class_id": item.get("class_id"),
        "class_name": item.get("class_name"),
        "student_id": item.get("student_id"),
        "student_name": item.get("student_name"),
        "teacher_user_id": item.get("teacher_user_id"),
        "teacher_name": item.get("teacher_name"),
        "weekly_question_count": item.get("weekly_question_count"),
        "total_active_question_count": item.get("total_active_question_count"),
        "topic_categories": item.get("topic_categories") or [],
        "representative_reason_summaries": item.get("representative_reason_summaries") or [],
        "latest_created_at": item.get("latest_created_at"),
        "source_record_ids": source_record_ids,
        "message": _weekly_followup_message_payload(message),
        "student_library_pdf_url": f"/api/wechat/student-libraries/{student_id}",
    }


def _serialize_lesson_for_response(lesson: object) -> Optional[dict]:
    if not isinstance(lesson, dict):
        return None
    serialized = dict(lesson)
    pdf_path = serialized.get("pdf_path", "")
    if not pdf_path or not Path(pdf_path).exists():
        serialized["pdf_path"] = ""
    return serialized


def _serialize_lessons_for_response(lessons: object) -> list[dict]:
    if not isinstance(lessons, list):
        return []
    serialized_lessons = []
    for lesson in lessons:
        serialized = _serialize_lesson_for_response(lesson)
        if serialized is not None:
            serialized_lessons.append(serialized)
    return serialized_lessons


def _serialize_wrong_question_practice_sheet_for_response(sheet: object) -> Optional[dict]:
    if not isinstance(sheet, dict):
        return None
    serialized = dict(sheet)
    if serialized.get("pdf_path"):
        serialized["pdf_url"] = f"/api/wrong-question-practice-sheets/{serialized['id']}/pdf"
        serialized["download_url"] = f"/api/wrong-question-practice-sheets/{serialized['id']}/pdf/download"
    return serialized


def _serialize_wrong_question_practice_sheets_for_response(items: object) -> list[dict]:
    if not isinstance(items, list):
        return []
    serialized_items = []
    for item in items:
        serialized = _serialize_wrong_question_practice_sheet_for_response(item)
        if serialized is not None:
            serialized_items.append(serialized)
    return serialized_items


def _safe_pdf_download_filename_part(value: object, fallback: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(value or "").strip())
    safe = re.sub(r"\s+", "_", safe).strip("._ ")
    return safe or fallback


def _wrong_question_practice_sheet_download_name(sheet: object) -> str:
    student_name = "学生"
    if isinstance(sheet, dict):
        student_name = _safe_pdf_download_filename_part(sheet.get("student_name_snapshot"), "学生")
    export_date = datetime.now().strftime("%Y-%m-%d")
    return f"{student_name}练习单_{export_date}.pdf"


def _can_access_lesson(user, lesson: object, owned_class_ids: Optional[Set[int]] = None) -> bool:
    if user.get("role") == "super_owner":
        return True
    if not isinstance(lesson, dict):
        return False
    if user.get("role") in {"owner", "admin"}:
        return lesson.get("organization_id") == user.get("organization_id")

    class_id = lesson.get("class_id")
    if not isinstance(class_id, int):
        return False

    member_class_ids = owned_class_ids
    if member_class_ids is None:
        member_class_ids = set(get_user_class_ids(user["id"]))
    return class_id in member_class_ids


def _filter_lessons_for_user(user, lessons: object) -> list[dict]:
    if not isinstance(lessons, list):
        return []
    if user.get("role") == "super_owner":
        return [item for item in lessons if isinstance(item, dict)]
    if user.get("role") in {"owner", "admin"}:
        return [
            item
            for item in lessons
            if isinstance(item, dict) and item.get("organization_id") == user.get("organization_id")
        ]

    owned_class_ids = set(get_user_class_ids(user["id"]))
    return [
        item
        for item in lessons
        if isinstance(item, dict) and _can_access_lesson(user, item, owned_class_ids)
    ]


def _can_access_wrong_question_practice_sheet(user, sheet: object, owned_class_ids: Optional[Set[int]] = None) -> bool:
    if user.get("role") == "super_owner":
        return True
    if not isinstance(sheet, dict):
        return False
    if user.get("role") in {"owner", "admin"}:
        return sheet.get("organization_id") == user.get("organization_id")

    class_id = sheet.get("class_id")
    if not isinstance(class_id, int):
        return False
    member_class_ids = owned_class_ids
    if member_class_ids is None:
        member_class_ids = set(get_user_class_ids(user["id"]))
    return class_id in member_class_ids


def _filter_wrong_question_practice_sheets_for_user(user, sheets: object) -> list[dict]:
    if not isinstance(sheets, list):
        return []
    if user.get("role") == "super_owner":
        return [item for item in sheets if isinstance(item, dict)]
    if user.get("role") in {"owner", "admin"}:
        return [
            item
            for item in sheets
            if isinstance(item, dict) and item.get("organization_id") == user.get("organization_id")
        ]

    owned_class_ids = set(get_user_class_ids(user["id"]))
    return [
        item
        for item in sheets
        if isinstance(item, dict) and _can_access_wrong_question_practice_sheet(user, item, owned_class_ids)
    ]


def _get_accessible_class_or_error(user: dict, class_id: int):
    cls = get_class(class_id)
    if not cls:
        return None, (jsonify({"error": "not found"}), 404)
    if _filter_classes_for_user(user, [cls]):
        return cls, None
    return None, (jsonify({"error": "forbidden"}), 403)


def _get_json_object_payload():
    if not request.is_json:
        return {}, None
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "request body must be a JSON object"}), 400)
    return data, None

def _get_parent_wechat_account_by_openid(open_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM parent_wechat_accounts WHERE openid=?",
            (open_id,),
        ).fetchone()
    return dict(row) if row else None


def _get_active_class_invite_by_code(invite_code: str):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM class_invite_codes
            WHERE invite_code=? AND status='active'
            ORDER BY id DESC
            LIMIT 1
            """,
            (invite_code,),
        ).fetchone()
    return dict(row) if row else None
def _credit_redeem_failure_key(user_id: int, platform_order_id: str) -> tuple[int, str]:
    return (int(user_id), str(platform_order_id or "").strip().lower())


def _is_credit_redeem_attempt_blocked(user_id: int, platform_order_id: str) -> bool:
    now = monotonic()
    key = _credit_redeem_failure_key(user_id, platform_order_id)
    with _CREDIT_REDEEM_FAILURE_LOCK:
        state = _CREDIT_REDEEM_FAILURE_STATE.get(key)
        if not state:
            return False
        last_failure_at = float(state.get("last_failure_at") or 0.0)
        if (now - last_failure_at) > _CREDIT_REDEEM_FAILURE_LOCK_SECONDS:
            _CREDIT_REDEEM_FAILURE_STATE.pop(key, None)
            return False
        return int(state.get("failures") or 0) >= _CREDIT_REDEEM_FAILURE_MAX_ATTEMPTS


def _record_credit_redeem_failure(user_id: int, platform_order_id: str) -> None:
    now = monotonic()
    key = _credit_redeem_failure_key(user_id, platform_order_id)
    with _CREDIT_REDEEM_FAILURE_LOCK:
        state = _CREDIT_REDEEM_FAILURE_STATE.get(key)
        if not state or (now - float(state.get("last_failure_at") or 0.0)) > _CREDIT_REDEEM_FAILURE_LOCK_SECONDS:
            _CREDIT_REDEEM_FAILURE_STATE[key] = {"failures": 1, "last_failure_at": now}
            return
        state["failures"] = int(state.get("failures") or 0) + 1
        state["last_failure_at"] = now


def _reset_credit_redeem_failure(user_id: int, platform_order_id: str) -> None:
    key = _credit_redeem_failure_key(user_id, platform_order_id)
    with _CREDIT_REDEEM_FAILURE_LOCK:
        _CREDIT_REDEEM_FAILURE_STATE.pop(key, None)


@app.route("/api/credits/overview", methods=["GET"])
def api_credit_overview():
    user, error = _require_owner()
    if error:
        return error
    return jsonify(get_credit_overview(user["organization_id"]))


@app.route("/api/credits/ledger", methods=["GET"])
def api_credit_ledger():
    user, error = _require_owner()
    if error:
        return error
    limit = request.args.get("limit", "100")
    try:
        items = list_credit_ledger(user["organization_id"], limit=int(limit))
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be a positive integer"}), 400
    return jsonify({"items": items})


@app.route("/api/credits/member-usage", methods=["GET"])
def api_credit_member_usage():
    user, error = _require_owner()
    if error:
        return error
    return jsonify({"items": list_member_usage_summary(user["organization_id"])})


@app.route("/api/credits/member-usage/<int:user_id>", methods=["GET"])
def api_credit_member_usage_detail(user_id: int):
    user, error = _require_owner()
    if error:
        return error
    return jsonify({"items": list_member_usage_detail(user["organization_id"], user_id)})


@app.route("/api/credits/pricing/n1n", methods=["GET"])
def api_credit_pricing_n1n():
    user, error = _require_owner()
    if error:
        return error
    cfg = get_config()
    if str(cfg.get("provider", "") or "").strip().lower() != "n1n":
        return jsonify({"provider": str(cfg.get("provider", "") or ""), "group": "default", "cny_per_usd": 1.0, "items": {}})

    group_name = str(request.args.get("group", "default") or "default").strip() or "default"
    models_query = str(request.args.get("models", "") or "").strip()
    requested_models = {
        part.strip()
        for part in models_query.split(",")
        if part.strip()
    }
    try:
        payload = _get_cached_n1n_pricing_payload()
    except (RuntimeError, ValueError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return jsonify({"error": "unable to load n1n pricing"}), 502

    pricing_lookup = _build_n1n_model_pricing_lookup(payload=payload, group_name=group_name)
    if requested_models:
        pricing_lookup = {
            model_name: pricing_lookup[model_name]
            for model_name in requested_models
            if model_name in pricing_lookup
        }

    return jsonify({
        "provider": "n1n",
        "group": group_name,
        "cny_per_usd": 1.0,
        "items": pricing_lookup,
    })


@app.route("/api/credits/redeem/xhs", methods=["POST"])
def api_credit_redeem_xhs():
    user, error = _require_owner()
    if error:
        return error
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return payload_error
    platform_order_id = str(data.get("platform_order_id", "")).strip()
    phone_suffix = str(data.get("phone_suffix", "")).strip()
    if not platform_order_id or not phone_suffix:
        return jsonify({"error": "platform_order_id and phone_suffix are required"}), 400
    if len(phone_suffix) != 4 or not phone_suffix.isdigit():
        return jsonify({"error": "platform_order_id and phone_suffix are required"}), 400
    if _is_credit_redeem_attempt_blocked(user["id"], platform_order_id):
        return jsonify({"error": "too many failed redemption attempts, please try later"}), 429

    try:
        order_payload = fetch_xhs_order_for_redemption(
            platform_order_id=platform_order_id,
            phone_suffix=phone_suffix,
        )
        result = redeem_xhs_order(
            organization_id=user["organization_id"],
            actor_user_id=user["id"],
            platform_order_id=platform_order_id,
            phone_suffix=phone_suffix,
            order_payload=order_payload,
        )
        _reset_credit_redeem_failure(user["id"], platform_order_id)
    except ValueError as exc:
        if str(exc) == "order already redeemed":
            return jsonify({"error": str(exc)}), 409
        _record_credit_redeem_failure(user["id"], platform_order_id)
        return jsonify({"error": "unable to verify order for redemption"}), 422
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify(result)


def _get_accessible_class_feedback_task_or_error(user: dict, task_id: int):
    task = get_class_feedback_task(task_id)
    if not task:
        return None, (jsonify({"error": "not found"}), 404)

    _, error = _get_accessible_class_or_error(user, task["class_id"])
    if error:
        return None, error
    return task, None


def _normalize_class_feedback_student_highlights(items: object) -> dict[int, dict]:
    if not isinstance(items, list):
        return {}

    normalized: dict[int, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        student_id = item.get("student_id")
        if not isinstance(student_id, int):
            continue
        labels = [
            str(label or "").strip()
            for label in (item.get("labels") or [])
            if str(label or "").strip()
        ]
        normalized[student_id] = {
            "labels": labels,
            "note": str(item.get("note") or "").strip(),
        }
    return normalized


def _normalize_class_feedback_notes_payload(task: dict, data: dict) -> dict:
    existing_highlights = _normalize_class_feedback_student_highlights(task.get("student_highlights"))
    student_highlights = (
        _normalize_class_feedback_student_highlights(data.get("student_highlights"))
        if "student_highlights" in data
        else existing_highlights
    )
    class_status_tags = (
        [
            str(tag or "").strip()
            for tag in (data.get("class_status_tags") or [])
            if str(tag or "").strip()
        ]
        if "class_status_tags" in data
        else list(task.get("class_status_tags") or [])
    )
    return {
        "class_status_tags": class_status_tags,
        "class_status_note": (
            str(data.get("class_status_note") or "").strip()
            if "class_status_note" in data
            else str(task.get("class_status_note") or "").strip()
        ),
        "parent_feedback_note": (
            str(data.get("parent_feedback_note") or "").strip()
            if "parent_feedback_note" in data
            else str(task.get("parent_feedback_note") or "").strip()
        ),
        "teaching_focus_note": (
            str(data.get("teaching_focus_note") or "").strip()
            if "teaching_focus_note" in data
            else str(task.get("teaching_focus_note") or "").strip()
        ),
        "next_stage_preview_note": (
            str(data.get("next_stage_preview_note") or "").strip()
            if "next_stage_preview_note" in data
            else str(task.get("next_stage_preview_note") or "").strip()
        ),
        "student_highlights": [
            {"student_id": student_id, **highlight}
            for student_id, highlight in student_highlights.items()
        ],
    }


def _build_class_feedback_generation_context(task: dict, user: dict) -> dict:
    cls = get_class(task["class_id"]) or {}
    all_lessons = list_lessons(class_id=task["class_id"])
    source_lessons = []
    for lesson in all_lessons:
        lesson_date = str(lesson.get("date") or "").strip()
        if not lesson_date or lesson_date < task["start_date"] or lesson_date > task["end_date"]:
            continue

        source_lessons.append(
            {
                "lesson_id": lesson["id"],
                "date": lesson_date,
                "topic": lesson.get("topic") or "",
                "summary": lesson.get("summary") or "",
                "weak_points": lesson.get("weak_points") or "",
            }
        )

    if not source_lessons:
        raise ValueError("所选时间范围内没有可用课次记录")

    student_highlights_by_id = _normalize_class_feedback_student_highlights(task.get("student_highlights"))
    recent_confirmed_summaries = list_recent_confirmed_class_feedback_summaries(
        class_id=task["class_id"],
        before_end_date=task["end_date"],
        limit=3,
    )
    students = []
    for roster_student in list_students_for_class(task["class_id"]):
        baseline = find_previous_confirmed_class_feedback_entry(
            class_id=task["class_id"],
            student_id=roster_student["id"],
            period_granularity=task["period_granularity"],
            before_end_date=task["end_date"],
        )
        students.append(
            {
                "student_id": roster_student["id"],
                "name": roster_student["name"],
                "stage_highlight": student_highlights_by_id.get(
                    roster_student["id"],
                    {"labels": [], "note": ""},
                ),
                "previous_baseline": baseline,
            }
        )

    if not students:
        raise ValueError("当前班级还没有学生，无法生成课堂反馈")

    source_summary = json.dumps(
        {
            "class_name": cls.get("name") or "",
            "date_range": {"start_date": task["start_date"], "end_date": task["end_date"]},
            "lessons": source_lessons,
        },
        ensure_ascii=False,
    )

    return {
        "class_name": cls.get("name") or "",
        "teacher_name": task.get("teacher_name_snapshot")
        or cls.get("teacher_name")
        or user.get("display_name")
        or user.get("username")
        or "",
        "start_date": task["start_date"],
        "end_date": task["end_date"],
        "source_summary": source_summary,
        "stage_notes": {
            "class_status_tags": list(task.get("class_status_tags") or []),
            "class_status_note": str(task.get("class_status_note") or ""),
            "parent_feedback_note": str(task.get("parent_feedback_note") or ""),
            "teaching_focus_note": str(task.get("teaching_focus_note") or ""),
            "next_stage_preview_note": str(task.get("next_stage_preview_note") or ""),
            "student_highlights": list(task.get("student_highlights") or []),
            "recent_confirmed_class_summaries": recent_confirmed_summaries,
        },
        "students": students,
    }


@app.route("/api/me", methods=["GET"])
def api_me():
    user, error = _require_auth()
    if error:
        return error
    return jsonify(user)


@app.route("/api/me/unbound-classes", methods=["GET"])
def api_me_unbound_classes():
    user, error = _require_auth()
    if error:
        return error
    try:
        items = list_unbound_classes_for_user_claim(user["id"])
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"items": items})


@app.route("/api/me/claim-classes", methods=["POST"])
def api_me_claim_classes():
    user, error = _require_auth()
    if error:
        return error
    data = request.json or {}
    class_ids = data.get("class_ids", [])
    try:
        updated_user = claim_classes_for_user(user["id"], class_ids)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"ok": True, "user": updated_user})


@app.route("/api/profile", methods=["PUT"])
def api_profile_update():
    user, error = _require_auth()
    if error:
        return error
    data = request.json or {}
    new_username = data.get("username", "").strip()
    new_display_name = data.get("display_name", "").strip()
    if not new_username or not new_display_name:
        return jsonify({"error": "账号和姓名不能为空"}), 400
    try:
        update_user_profile(user["id"], new_username, new_display_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"ok": True})


@app.route("/api/admin/organization-requests", methods=["GET"])
def api_admin_organization_requests():
    _, error = _require_super_owner()
    if error:
        return error
    return jsonify({"items": list_organization_requests()})


@app.route("/api/admin/organization-requests/<int:request_id>/approve", methods=["POST"])
def api_admin_organization_request_approve(request_id: int):
    user, error = _require_super_owner()
    if error:
        return error
    try:
        approved_user, invite = approve_organization_request(request_id=request_id, reviewer_id=user["id"])
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify(
        {
            "ok": True,
            "user": approved_user,
            "invite": _organization_invite_response_payload(invite),
        }
    )


@app.route("/api/admin/organization-requests/<int:request_id>/reject", methods=["POST"])
def api_admin_organization_request_reject(request_id: int):
    user, error = _require_super_owner()
    if error:
        return error
    try:
        reject_organization_request(request_id=request_id, reviewer_id=user["id"])
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"ok": True})


@app.route("/api/organization/invite", methods=["GET"])
def api_organization_invite_get():
    user, error = _require_owner()
    if error:
        return error
    try:
        invite = get_or_create_active_organization_invite(
            organization_id=user["organization_id"],
            actor_user_id=user["id"],
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_organization_invite_response_payload(invite))


@app.route("/api/organization/invite/reset", methods=["POST"])
def api_organization_invite_reset():
    user, error = _require_owner()
    if error:
        return error
    try:
        invite = reset_organization_invite(
            organization_id=user["organization_id"],
            actor_user_id=user["id"],
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_organization_invite_response_payload(invite))


@app.route("/api/admin/registration-requests", methods=["GET"])
def api_admin_registration_requests():
    user, error = _require_owner()
    if error:
        return error
    return jsonify({"items": list_registration_requests_for_actor(user, "pending")})


@app.route("/api/admin/registration-requests/<int:request_id>/approve", methods=["POST"])
def api_admin_registration_request_approve(request_id):
    user, error = _require_owner()
    if error:
        return error
    registration_request = get_registration_request(request_id)
    if not registration_request:
        return jsonify({"error": "申请不存在"}), 404
    if (
        user.get("role") != "super_owner"
        and registration_request.get("organization_id") != user.get("organization_id")
    ):
        return jsonify({"error": "申请不存在"}), 404
    try:
        approved = approve_registration_request(request_id=request_id, reviewer_id=user["id"])
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"ok": True, "user": approved})


@app.route("/api/admin/registration-requests/<int:request_id>/reject", methods=["POST"])
def api_admin_registration_request_reject(request_id):
    user, error = _require_owner()
    if error:
        return error
    registration_request = get_registration_request(request_id)
    if not registration_request:
        return jsonify({"error": "申请不存在"}), 404
    if (
        user.get("role") != "super_owner"
        and registration_request.get("organization_id") != user.get("organization_id")
    ):
        return jsonify({"error": "申请不存在"}), 404
    try:
        reject_registration_request(request_id=request_id, reviewer_id=user["id"])
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"ok": True})


@app.route("/api/admin/users", methods=["GET"])
def api_admin_users():
    user, error = _require_staff()
    if error:
        return error
    users = list_users_for_actor(user)
    is_super = user.get("role") == "super_owner"
    def _user_row(u):
        row = {
            "id": u["id"],
            "username": u.get("username"),
            "name": u["display_name"],
            "org": u["organization_name"],
            "role": u["role"],
            "visible_pages": u.get("visible_pages", []),
        }
        if is_super:
            row["last_login"] = u.get("last_login")
        return row
    return jsonify([_user_row(u) for u in users])


@app.route("/api/admin/member-binding-summary", methods=["GET"])
def api_admin_member_binding_summary():
    user, error = _require_staff()
    if error:
        return error
    return jsonify({"items": master_data.list_member_binding_summaries(actor_user=user)})


@app.route("/api/admin/organizations", methods=["GET"])
def api_admin_organizations():
    _, error = _require_super_owner()
    if error:
        return error
    return jsonify({"items": list_organizations()})


@app.route("/api/admin/organizations/<int:org_id>", methods=["DELETE"])
def api_admin_organization_delete(org_id: int):
    _, error = _require_super_owner()
    if error:
        return error
    try:
        delete_organization(org_id)
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"ok": True})


@app.route("/api/admin/users/<int:user_id>/role", methods=["PUT"])
def api_admin_user_role_set(user_id):
    user, error = _require_owner()
    if error:
        return error
    data = request.json or {}
    role = data.get("role")
    if role not in ("super_owner", "owner", "admin", "member"):
        return jsonify({"error": "role must be super_owner, owner, admin or member"}), 400
    if role in ("super_owner", "owner") and user.get("role") != "super_owner":
        return jsonify({"error": "无权限"}), 403
    target_user = get_user_by_id(user_id)
    if not target_user:
        return jsonify({"error": "user not found"}), 404
    if user.get("role") != "super_owner" and not actor_can_manage_user(user, target_user):
        return jsonify({"error": "user not found"}), 404
    try:
        update_user_role(user_id, role)
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        if str(exc) == "super owner role is fixed":
            return jsonify({"error": str(exc)}), 409
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True})


@app.route("/api/admin/users/<int:user_id>/visible-pages", methods=["PUT"])
def api_admin_user_visible_pages_set(user_id):
    user, error = _require_staff()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    try:
        updated_user = update_user_visible_pages_for_actor(user, user_id, data.get("visible_pages"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({
        "ok": True,
        "user": {
            "id": updated_user["id"],
            "name": updated_user["display_name"],
            "org": updated_user["organization_name"],
            "role": updated_user["role"],
            "visible_pages": updated_user.get("visible_pages", []),
        },
    })


@app.route("/api/admin/users/<int:user_id>/classes", methods=["GET"])
def api_admin_user_classes_get(user_id):
    user, error = _require_staff()
    if error:
        return error
    target_user = get_user_by_id(user_id)
    if not target_user:
        return jsonify({"error": "user not found"}), 404
    if user.get("role") != "super_owner" and target_user.get("organization_id") != user.get("organization_id"):
        return jsonify({"error": "user not found"}), 404
    return jsonify({"class_ids": get_user_class_ids(user_id)})


@app.route("/api/admin/users/<int:user_id>/classes", methods=["PUT"])
def api_admin_user_classes_set(user_id):
    user, error = _require_staff()
    if error:
        return error
    data = request.json or {}
    class_ids = data.get("class_ids", [])
    if not isinstance(class_ids, list):
        return jsonify({"error": "class_ids must be a list"}), 400
    target_user = get_user_by_id(user_id)
    if not target_user:
        return jsonify({"error": "user not found"}), 404
    if user.get("role") != "super_owner" and target_user.get("organization_id") != user.get("organization_id"):
        return jsonify({"error": "user not found"}), 404
    if user.get("role") != "super_owner":
        for class_id in class_ids:
            cls = get_class(class_id)
            if not cls:
                return jsonify({"error": f"class not found: {class_id}"}), 404
            if cls.get("organization_id") != user.get("organization_id"):
                return jsonify({"error": "class not found"}), 404
    try:
        set_user_class_ids(user_id, class_ids)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"ok": True})


@app.route("/api/admin/users/<int:user_id>/profile", methods=["PUT"])
def api_admin_user_profile_update(user_id):
    user, error = _require_owner()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    display_name = (data.get("display_name") or "").strip()
    try:
        updated_user = update_user_display_name_for_actor(user, user_id, display_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"ok": True, "user": updated_user})


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
def api_admin_user_delete(user_id):
    user, error = _require_owner()
    if error:
        return error
    try:
        delete_user_for_actor(user, user_id)
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"ok": True})


@app.route("/api/wrong-question-followups/weekly", methods=["GET"])
def api_weekly_wrong_question_followups():
    user, error = _require_auth()
    if error:
        return error
    class_id = request.args.get("class_id", 0, type=int)
    if not class_id:
        return jsonify({"error": "class_id is required"}), 400
    cls = _require_accessible_class(user, class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    organization_id = int(cls.get("organization_id") or user.get("organization_id") or 0)
    try:
        week_start_date, week_end_date = _weekly_range(request.args.get("week_start", ""))
    except ValueError:
        return jsonify({"error": "week_start must be YYYY-MM-DD"}), 400

    items = list_weekly_wrong_question_followup_students(
        organization_id=organization_id,
        class_id=class_id,
        week_start_date=week_start_date,
        week_end_date=week_end_date,
    )
    payload_items = []
    for item in items:
        message = get_weekly_wrong_question_followup_message(
            organization_id=organization_id,
            class_id=class_id,
            student_id=int(item.get("student_id") or 0),
            week_start_date=week_start_date,
            style="warm",
        )
        payload_items.append(_weekly_followup_item_payload(item, message))

    return jsonify(
        {
            "class_id": class_id,
            "class_name": cls.get("name"),
            "week_start_date": week_start_date,
            "week_end_date": week_end_date,
            "items": payload_items,
            "total": len(payload_items),
        }
    )


@app.route("/api/wrong-question-followups/weekly/class-pdf-archive", methods=["GET"])
def api_weekly_wrong_question_followup_class_pdf_archive():
    user, error = _require_auth()
    if error:
        return error
    class_id = request.args.get("class_id", 0, type=int)
    if not class_id:
        return jsonify({"error": "class_id is required"}), 400
    cls = _require_accessible_class(user, class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    organization_id = int(cls.get("organization_id") or user.get("organization_id") or 0)
    try:
        week_start_date, week_end_date = _weekly_range(request.args.get("week_start", ""))
    except ValueError:
        return jsonify({"error": "week_start must be YYYY-MM-DD"}), 400

    items = list_weekly_wrong_question_followup_students(
        organization_id=organization_id,
        class_id=class_id,
        week_start_date=week_start_date,
        week_end_date=week_end_date,
    )
    buffer = io.BytesIO()
    successful_count = 0
    failed_student_names = []
    used_filenames: dict[str, int] = {}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in items:
            student_id = int(item.get("student_id") or 0)
            student_name = str(item.get("student_name") or "").strip() or "未命名"
            try:
                refreshed_pdf_path = _refresh_student_wrong_question_library_cache(student_id)
                pdf_path = Path(str(refreshed_pdf_path or ""))
                if not pdf_path.exists():
                    raise FileNotFoundError(str(pdf_path))
                base_name = f"{_safe_archive_filename_part(student_name)}-错题本"
                name_count = used_filenames.get(base_name, 0) + 1
                used_filenames[base_name] = name_count
                archive_name = f"{base_name}.pdf" if name_count == 1 else f"{base_name}-{name_count}.pdf"
                archive.write(pdf_path, archive_name)
                successful_count += 1
            except Exception:
                logger.exception("Failed to add weekly wrong question library pdf to archive")
                failed_student_names.append(student_name)
        if failed_student_names:
            notes = ["以下学生错题本 PDF 打包失败：", *failed_student_names]
            archive.writestr("打包说明.txt", "\n".join(notes).encode("utf-8"))
    buffer.seek(0)

    download_name = (
        f"{_safe_archive_filename_part(str(cls.get('name') or '班级'))}"
        f"-{week_start_date}-错题本合集.zip"
    )
    response = send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=download_name,
    )
    response.headers["X-XR-Archive-Success-Count"] = str(successful_count)
    response.headers["X-XR-Archive-Failed-Count"] = str(len(failed_student_names))
    return response


@app.route("/api/wrong-question-followups/weekly/messages", methods=["POST"])
def api_weekly_wrong_question_followup_message_create():
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    try:
        class_id = int(data.get("class_id") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "class_id must be numeric"}), 400
    try:
        student_id = int(data.get("student_id") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "student_id must be numeric"}), 400
    if not class_id:
        return jsonify({"error": "class_id is required"}), 400
    if not student_id:
        return jsonify({"error": "student_id is required"}), 400
    cls = _require_accessible_class(user, class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    organization_id = int(cls.get("organization_id") or user.get("organization_id") or 0)
    try:
        week_start_date, week_end_date = _weekly_range(str(data.get("week_start") or ""))
    except ValueError:
        return jsonify({"error": "week_start must be YYYY-MM-DD"}), 400

    items = list_weekly_wrong_question_followup_students(
        organization_id=organization_id,
        class_id=class_id,
        week_start_date=week_start_date,
        week_end_date=week_end_date,
    )
    item = next((entry for entry in items if int(entry.get("student_id") or 0) == student_id), None)
    if not item:
        return jsonify({"error": "not found"}), 404

    practice_sheets = list_wrong_question_practice_sheets_for_student(student_id)
    message_text = ai_processor.generate_weekly_wrong_question_followup_message(
        student_name=str(item.get("student_name") or ""),
        class_name=str(item.get("class_name") or ""),
        teacher_name=str(item.get("teacher_name") or ""),
        weekly_question_count=int(item.get("weekly_question_count") or 0),
        total_active_question_count=int(item.get("total_active_question_count") or 0),
        topic_categories=item.get("topic_categories") or [],
        representative_reason_summaries=item.get("representative_reason_summaries") or [],
        has_practice_sheet=bool(practice_sheets),
    )
    message = upsert_weekly_wrong_question_followup_message(
        organization_id=organization_id,
        class_id=class_id,
        student_id=student_id,
        teacher_user_id=int(item.get("teacher_user_id") or 0),
        week_start_date=week_start_date,
        week_end_date=week_end_date,
        style="warm",
        message_text=message_text,
        source_record_ids=item.get("source_record_ids") or [],
        generated_by=int(user["id"]),
    )
    return jsonify({"ok": True, "message": _weekly_followup_message_payload(message)})


@app.route("/api/wrong-questions", methods=["GET"])
def api_wrong_questions_list():
    user, error = _require_auth()
    if error:
        return error
    try:
        payload = smart_wrong_questions.fetch_wrong_question_records(request.args)
    except smart_wrong_questions.WrongQuestionProxyError as exc:
        if exc.status_code == 503 and str(exc) == "智能错题服务尚未配置":
            payload = {"items": [], "total": 0}
        else:
            return jsonify({"error": str(exc)}), exc.status_code

    local_items = list_wechat_wrong_question_submissions()
    merged_items = [*local_items, *payload.get("items", [])]
    scoped_items = _filter_wrong_question_items_for_user(user, merged_items)
    payload["items"] = scoped_items
    payload["total"] = len(scoped_items)
    payload["summary"] = _summarize_wrong_question_records(scoped_items)
    return jsonify(payload)


@app.route("/api/wrong-questions/<record_id>", methods=["GET"])
def api_wrong_question_detail(record_id):
    user, error = _require_auth()
    if error:
        return error
    local_record = get_wechat_wrong_question_submission(record_id)
    if local_record:
        if not _can_access_wrong_question_record(user, local_record):
            return jsonify({"error": "not found"}), 404
        return jsonify(local_record)
    try:
        record = smart_wrong_questions.fetch_wrong_question_record(record_id, request.args)
    except smart_wrong_questions.WrongQuestionProxyError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    if not _can_access_wrong_question_record(user, record):
        return jsonify({"error": "not found"}), 404
    return jsonify(record)


@app.route("/api/wrong-questions/<record_id>", methods=["DELETE"])
def api_wrong_question_delete(record_id):
    user, error = _require_auth()
    if error:
        return error

    local_record = get_wechat_wrong_question_submission(record_id)
    if not local_record or not _can_access_wrong_question_record(user, local_record):
        return jsonify({"error": "not found"}), 404

    student_id = int(local_record["student_id"])
    pdf_path = _student_wrong_question_library_path(student_id)
    deleted_record = delete_wechat_wrong_question_submission(record_id)
    if not deleted_record:
        return jsonify({"error": "not found"}), 404

    pdf_path.unlink(missing_ok=True)
    remaining_records = list_student_wrong_question_library_records(student_id)
    next_pdf_path = ""
    if remaining_records:
        next_pdf_path = _refresh_student_wrong_question_library_cache(student_id)
    else:
        _refresh_student_wrong_question_library_cache(student_id)

    return jsonify(
        {
            "ok": True,
            "deleted_record_id": record_id,
            "student_id": student_id,
            "next_student_library_pdf_path": next_pdf_path,
        }
    )


@app.route("/api/wrong-questions/<record_id>/review", methods=["PUT"])
def api_wrong_question_review_save(record_id):
    user, error = _require_auth()
    if error:
        return error
    local_record = get_wechat_wrong_question_submission(record_id)
    if local_record:
        if not _can_access_wrong_question_record(user, local_record):
            return jsonify({"error": "not found"}), 404
        saved_record = save_wechat_wrong_question_review(record_id, request.json or {})
        if not saved_record:
            return jsonify({"error": "not found"}), 404
        question_text = str(((request.json or {}).get("question_text") or "")).strip()
        if question_text and not local_record.get("is_geometry"):
            saved_record = update_wechat_wrong_question_question_text(
                record_id,
                question_text=question_text,
                student_library_pdf_path=str(local_record.get("student_library_pdf_path") or ""),
            )
        pdf_path = _refresh_student_wrong_question_library_cache(local_record["student_id"])
        saved_record = attach_student_library_pdf_path(record_id, pdf_path)
        return jsonify({"ok": True, "record": saved_record})
    try:
        record = smart_wrong_questions.fetch_wrong_question_record(record_id, request.args)
        if not _can_access_wrong_question_record(user, record):
            return jsonify({"error": "not found"}), 404
        return jsonify(
            smart_wrong_questions.save_wrong_question_review(record_id, request.args, request.json or {})
        )
    except smart_wrong_questions.WrongQuestionProxyError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@app.route("/api/wrong-questions/<record_id>/topic-category", methods=["PUT"])
def api_wrong_question_topic_category_save(record_id):
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    local_record = get_wechat_wrong_question_submission(record_id)
    if not local_record or not _can_access_wrong_question_record(user, local_record):
        return jsonify({"error": "not found"}), 404

    saved_record = update_wechat_wrong_question_topic_category(
        record_id,
        topic_category=(data.get("topic_category") or data.get("topicCategory") or "").strip(),
    )
    if not saved_record:
        return jsonify({"error": "not found"}), 404
    _refresh_student_wrong_question_library_cache(local_record["student_id"])
    saved_record = get_wechat_wrong_question_submission(record_id)
    return jsonify({"ok": True, "record": saved_record})


@app.route("/api/wrong-questions/<record_id>/archive", methods=["PUT"])
def api_wrong_question_archive_save(record_id):
    user, error = _require_staff()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    local_record = get_wechat_wrong_question_submission(record_id)
    if not local_record or not _can_access_wrong_question_record(user, local_record):
        return jsonify({"error": "not found"}), 404

    try:
        saved_record = set_wechat_wrong_question_archive_status(
            record_id,
            (data.get("archive_status") or "").strip() or "active",
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not saved_record:
        return jsonify({"error": "not found"}), 404
    _refresh_student_wrong_question_library_cache(local_record["student_id"])
    saved_record = get_wechat_wrong_question_submission(record_id)
    return jsonify({"ok": True, "record": saved_record})


@app.route("/api/wrong-question-student-libraries/<int:student_id>/refresh", methods=["POST"])
def api_wrong_question_student_library_refresh(student_id: int):
    user, error = _require_auth()
    if error:
        return error

    records = list_student_wrong_question_library_records(student_id)
    if not records:
        return jsonify({"error": "student library pdf not found"}), 404
    if not any(_can_access_wrong_question_record(user, record) for record in records):
        return jsonify({"error": "not found"}), 404

    pdf_path = _refresh_student_wrong_question_library_cache(student_id)
    return jsonify(
        {
            "ok": True,
            "student_id": student_id,
            "student_library_pdf_path": pdf_path,
            "pdf_url": f"/api/wechat/student-libraries/{student_id}",
        }
    )


@app.route("/api/wrong-question-practice-sheets", methods=["POST"])
def api_wrong_question_practice_sheet_create():
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    if not has_api_key():
        return jsonify({"error": "系统 API Key 未配置，请联系管理员"}), 400

    student_id = int(data.get("student_id") or 0)
    wrong_question_ids = data.get("wrong_question_ids")
    if not student_id:
        return jsonify({"error": "student_id is required"}), 400
    if not isinstance(wrong_question_ids, list) or not wrong_question_ids:
        return jsonify({"error": "wrong_question_ids is required"}), 400

    selected_records = []
    for raw_record_id in wrong_question_ids:
        record_id = str(raw_record_id or "").strip()
        if not record_id:
            return jsonify({"error": "wrong_question_ids contains an invalid record id"}), 400
        record = get_wechat_wrong_question_submission(record_id)
        if not record or not _can_access_wrong_question_record(user, record):
            return jsonify({"error": "not found"}), 404
        if int(record.get("student_id") or 0) != student_id:
            return jsonify({"error": "selected records must belong to the same student"}), 400
        if str(record.get("source") or "") != "wechat_mp":
            return jsonify({"error": "selected records must be local wrong questions"}), 400
        if str(record.get("recognition_status") or "") != "recognized":
            return jsonify({"error": "selected records must be recognized before generating practice"}), 400
        if str(record.get("archive_status") or "").strip() == "archived":
            return jsonify({"error": "selected records must stay active before generating practice"}), 400
        selected_records.append(record)

    try:
        sheet = create_pending_wrong_question_practice_sheet(
            created_by=int(user["id"]),
            selected_records=selected_records,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    _start_wrong_question_practice_generation_thread(
        sheet_id=int(sheet["id"]),
        user={
            "id": int(user["id"]),
            "organization_id": int(user["organization_id"]),
        },
    )
    return jsonify({"id": sheet["id"], "status": "pending"}), 202


@app.route("/api/wrong-question-practice-sheets", methods=["GET"])
def api_wrong_question_practice_sheets_list():
    user, error = _require_auth()
    if error:
        return error

    student_id = request.args.get("student_id", 0, type=int)
    if not student_id:
        return jsonify({"error": "student_id is required"}), 400

    items = list_wrong_question_practice_sheets_for_student(student_id)
    scoped_items = _filter_wrong_question_practice_sheets_for_user(user, items)
    return jsonify({
        "items": _serialize_wrong_question_practice_sheets_for_response(scoped_items),
        "total": len(scoped_items),
    })


@app.route("/api/wrong-question-practice-sheets/<int:sheet_id>", methods=["GET"])
def api_wrong_question_practice_sheet_detail(sheet_id: int):
    user, error = _require_auth()
    if error:
        return error
    sheet = get_wrong_question_practice_sheet(sheet_id)
    if not sheet or not _can_access_wrong_question_practice_sheet(user, sheet):
        return jsonify({"error": "not found"}), 404
    serialized = _serialize_wrong_question_practice_sheet_for_response(sheet)
    if serialized is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(serialized)


@app.route("/api/wrong-question-practice-sheets/<int:sheet_id>", methods=["DELETE"])
def api_wrong_question_practice_sheet_delete(sheet_id: int):
    user, error = _require_auth()
    if error:
        return error
    sheet = get_wrong_question_practice_sheet(sheet_id)
    if not sheet or not _can_access_wrong_question_practice_sheet(user, sheet):
        return jsonify({"error": "not found"}), 404

    pdf_path_value = str(sheet.get("pdf_path") or "").strip()
    pdf_path = Path(pdf_path_value) if pdf_path_value else None
    deleted_sheet = delete_wrong_question_practice_sheet(sheet_id)
    if not deleted_sheet:
        return jsonify({"error": "not found"}), 404

    if pdf_path:
        pdf_path.unlink(missing_ok=True)
    return jsonify({"ok": True, "deleted_sheet_id": sheet_id})


@app.route("/api/wrong-question-practice-sheets/<int:sheet_id>/pdf", methods=["GET"])
def api_wrong_question_practice_sheet_pdf_preview(sheet_id: int):
    user, error = _require_auth()
    if error:
        return error
    sheet = get_wrong_question_practice_sheet(sheet_id)
    if not sheet or not _can_access_wrong_question_practice_sheet(user, sheet):
        return jsonify({"error": "not found"}), 404
    pdf_path = Path(str(sheet.get("pdf_path") or "").strip())
    if not pdf_path or not pdf_path.exists():
        return jsonify({"error": "pdf not found"}), 404
    return send_file(pdf_path, mimetype="application/pdf", download_name=pdf_path.name)


@app.route("/api/wrong-question-practice-sheets/<int:sheet_id>/pdf/download", methods=["GET"])
def api_wrong_question_practice_sheet_pdf_download(sheet_id: int):
    user, error = _require_auth()
    if error:
        return error
    sheet = get_wrong_question_practice_sheet(sheet_id)
    if not sheet or not _can_access_wrong_question_practice_sheet(user, sheet):
        return jsonify({"error": "not found"}), 404
    pdf_path = Path(str(sheet.get("pdf_path") or "").strip())
    if not pdf_path or not pdf_path.exists():
        return jsonify({"error": "pdf not found"}), 404
    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=_wrong_question_practice_sheet_download_name(sheet),
    )


@app.route("/api/consultations", methods=["GET"])
def api_consultations_list():
    user, error = _require_auth()
    if error:
        return error
    return jsonify(list_consultations_for_actor(user, query=request.args.get("q", "")))


@app.route("/api/consultations/ai-parse", methods=["POST"])
def api_consultation_ai_parse():
    user, error = _require_auth()
    if error:
        return error

    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400

    raw_text = str(payload.get("raw_text", "")).strip()
    if not raw_text:
        return jsonify({"error": "raw_text is required"}), 400

    cleaned_text = clean_consultation_batch_input(raw_text)
    if not cleaned_text:
        return jsonify({"error": "raw_text is empty after cleanup"}), 400

    provider = _default_ai_provider_name()
    model = _default_chat_model_name()

    def _produce_consultation_parse():
        parsed_result = _call_ai_helper_with_usage(parse_consultation_batch_text, cleaned_text)
        parsed_payload, usage = _split_ai_result_with_usage(
            parsed_result,
            provider=provider,
            model=model,
        )
        normalized_payload = normalize_consultation_batch_parse_result(parsed_payload)
        return normalized_payload, usage

    try:
        normalized = _run_ai_feature_with_charge(
            user=user,
            feature_key="consultation_ai_parse",
            source_record_type="consultation_batch",
            source_record_id=hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()[:16],
            producer=_produce_consultation_parse,
            provider=provider,
            model=model,
        )
    except DuplicateAiRequestError as exc:
        return jsonify({"error": str(exc)}), 409
    except CreditBalanceError as exc:
        return jsonify({"error": str(exc)}), 402
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 502
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:
        return jsonify({"error": f"AI 解析失败：{exc}"}), 502

    return jsonify(normalized)


@app.route("/api/consultation-teachers", methods=["GET"])
def api_consultation_teachers():
    _, error = _require_auth()
    if error:
        return error
    return jsonify(list_consultation_teachers())


# ---------- Teacher Alias Mapping (teachers.json CRUD) ----------


def _normalize_teacher_alias_linked_username(actor_user: dict, raw_username: str) -> str:
    username = (raw_username or "").strip()
    if not username:
        return ""
    allowed_users = list_users_for_actor(actor_user)
    for candidate in allowed_users:
        candidate_username = (candidate.get("username") or "").strip()
        if candidate_username and candidate_username.lower() == username.lower() and candidate.get("role") != "super_owner":
            return candidate_username
    raise ValueError("关联的网站成员不存在")


@app.route("/api/teacher-aliases", methods=["GET"])
def api_teacher_aliases_list():
    _, error = _require_owner()
    if error:
        return error
    return jsonify(get_teacher_alias_entries())


@app.route("/api/teacher-aliases", methods=["POST"])
def api_teacher_aliases_create():
    user, error = _require_owner()
    if error:
        return error
    body = request.json or {}
    wecom_userid = (body.get("wecom_userid") or "").strip()
    display_name = (body.get("display_name") or "").strip()
    aliases = body.get("aliases") or []
    if not wecom_userid or not display_name:
        return jsonify({"error": "企微ID和中文名为必填项"}), 400
    try:
        linked_username = _normalize_teacher_alias_linked_username(user, body.get("linked_username") or "")
        entry = upsert_teacher_alias(wecom_userid, display_name, aliases, linked_username=linked_username)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(entry), 201


@app.route("/api/teacher-aliases/<path:wecom_userid>", methods=["PUT"])
def api_teacher_aliases_update(wecom_userid):
    user, error = _require_owner()
    if error:
        return error
    body = request.json or {}
    display_name = (body.get("display_name") or "").strip()
    aliases = body.get("aliases") or []
    if not display_name:
        return jsonify({"error": "中文名为必填项"}), 400
    try:
        linked_username = _normalize_teacher_alias_linked_username(user, body.get("linked_username") or "")
        entry = upsert_teacher_alias(wecom_userid, display_name, aliases, linked_username=linked_username)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(entry)


@app.route("/api/teacher-aliases/<path:wecom_userid>", methods=["DELETE"])
def api_teacher_aliases_delete(wecom_userid):
    _, error = _require_owner()
    if error:
        return error
    if not delete_teacher_alias(wecom_userid):
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/consultations/<int:consultation_id>", methods=["GET"])
def api_consultation_get(consultation_id):
    user, error = _require_auth()
    if error:
        return error
    item = get_consultation(
        consultation_id,
        None if user.get("role") == "super_owner" else user.get("organization_id"),
    )
    if not item:
        return jsonify({"error": "not found"}), 404
    return jsonify(item)


@app.route("/api/consultations", methods=["POST"])
def api_consultation_create():
    user, error = _require_auth()
    if error:
        return error
    assigned_user_id = None
    if request.json and isinstance(request.json, dict):
        assigned_user_id = request.json.get("assigned_user_id")
        if assigned_user_id is None and request.json.get("teacher_id"):
            assigned_user_id = resolve_teacher_username_to_user_id(request.json["teacher_id"])
    item = create_consultation(request.json or {}, user["organization_id"], assigned_user_id=assigned_user_id)
    return jsonify(item), 201


@app.route("/api/consultations/<int:consultation_id>", methods=["PUT"])
def api_consultation_update(consultation_id):
    user, error = _require_staff()
    if error:
        return error
    data = request.json or {}
    if isinstance(data, dict) and "teacher_id" in data:
        resolved = resolve_teacher_username_to_user_id(data["teacher_id"])
        if resolved is not None:
            data["assigned_user_id"] = resolved
        elif not data["teacher_id"]:
            data["assigned_user_id"] = None
    item = update_consultation(
        consultation_id,
        data,
        None if user.get("role") == "super_owner" else user.get("organization_id"),
    )
    if not item:
        return jsonify({"error": "not found"}), 404
    return jsonify(item)


@app.route("/api/consultations/<int:consultation_id>", methods=["DELETE"])
def api_consultation_delete(consultation_id):
    user, error = _require_staff()
    if error:
        return error
    deleted = delete_consultation(
        consultation_id,
        None if user.get("role") == "super_owner" else user.get("organization_id"),
    )
    if not deleted:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/stats")
def api_stats():
    user, error = _require_auth()
    if error:
        return error
    month_now = datetime.now().strftime("%Y-%m")
    all_lessons = list_lessons_for_actor(user)
    total_pdfs = sum(1 for l in all_lessons if l.get("pdf_path") and Path(l["pdf_path"]).exists())
    return jsonify({
        "total_lessons": len(all_lessons),
        "month_lessons": len(list_lessons_for_actor(user, month_str=month_now)),
        "total_pdfs": total_pdfs,
    })


@app.route("/api/classes", methods=["GET"])
def api_classes_list():
    user, error = _require_auth()
    if error:
        return error
    return jsonify(list_classes_for_actor(user) if user.get("role") in {"super_owner", "owner", "admin"} else _filter_classes_for_user(user, list_classes()))


@app.route("/api/course-calendar/schedules", methods=["GET"])
def api_course_calendar_schedules_list():
    user, error = _require_auth()
    if error:
        return error
    try:
        items = list_course_calendar_schedules_for_actor(
            user,
            start_date=(request.args.get("start_date") or "").strip(),
            end_date=(request.args.get("end_date") or "").strip(),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": items})


@app.route("/api/course-calendar/schedules", methods=["POST"])
def api_course_calendar_schedule_create():
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    class_id = data.get("class_id")
    if isinstance(class_id, bool) or not isinstance(class_id, int):
        return jsonify({"error": "class_id must be an integer"}), 400
    _, class_error = _get_accessible_class_or_error(user, class_id)
    if class_error:
        return class_error
    try:
        item = create_course_calendar_schedule(
            class_id=class_id,
            date_str=(data.get("date") or "").strip(),
            time_block=(data.get("time_block") or "").strip(),
            start_offset_minutes=data.get("start_offset_minutes"),
            created_by=user["id"],
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"item": item}), 201


@app.route("/api/course-calendar/schedules/<int:schedule_id>", methods=["DELETE"])
def api_course_calendar_schedule_delete(schedule_id):
    user, error = _require_auth()
    if error:
        return error
    item = get_course_calendar_schedule(schedule_id)
    if not item:
        return jsonify({"error": "not found"}), 404
    _, class_error = _get_accessible_class_or_error(user, item["class_id"])
    if class_error:
        return class_error
    removed = delete_course_calendar_schedule(schedule_id)
    return jsonify({"ok": True, "removed": removed})


@app.route("/api/course-calendar/custom-items", methods=["GET"])
def api_course_calendar_custom_items_list():
    user, error = _require_auth()
    if error:
        return error
    return jsonify({"items": list_course_calendar_custom_items_for_actor(user)})


@app.route("/api/course-calendar/custom-items", methods=["POST"])
def api_course_calendar_custom_item_create():
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    try:
        item = create_course_calendar_custom_item(
            actor_user=user,
            title=data.get("title"),
            time_range=data.get("time_range"),
            note=data.get("note") or "",
            visibility=data.get("visibility") or "private",
        )
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"item": item}), 201


@app.route("/api/course-calendar/custom-items/<int:item_id>", methods=["DELETE"])
def api_course_calendar_custom_item_delete(item_id):
    user, error = _require_auth()
    if error:
        return error
    item = get_course_calendar_custom_item(item_id)
    if not item:
        return jsonify({"error": "not found"}), 404
    is_creator = item.get("created_by") == user.get("id")
    is_legacy_staff_item = (
        item.get("created_by") is None
        and user.get("role") in {"super_owner", "owner", "admin"}
        and item.get("organization_id") == user.get("organization_id")
    )
    if not (is_creator or is_legacy_staff_item):
        return jsonify({"error": "forbidden"}), 403
    removed = delete_course_calendar_custom_item(item_id)
    return jsonify({"ok": True, "removed": removed})


@app.route("/api/course-calendar/custom-schedules", methods=["GET"])
def api_course_calendar_custom_schedules_list():
    user, error = _require_auth()
    if error:
        return error
    try:
        items = list_course_calendar_custom_schedules_for_actor(
            user,
            start_date=(request.args.get("start_date") or "").strip(),
            end_date=(request.args.get("end_date") or "").strip(),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": items})


@app.route("/api/course-calendar/custom-schedules", methods=["POST"])
def api_course_calendar_custom_schedule_create():
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    custom_item_id = data.get("custom_item_id")
    if isinstance(custom_item_id, bool) or not isinstance(custom_item_id, int):
        return jsonify({"error": "custom_item_id must be an integer"}), 400
    try:
        item = create_course_calendar_custom_schedule(
            actor_user=user,
            custom_item_id=custom_item_id,
            date_str=(data.get("date") or "").strip(),
            time_block=(data.get("time_block") or "").strip(),
            start_offset_minutes=data.get("start_offset_minutes"),
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"item": item}), 201


@app.route("/api/course-calendar/custom-schedules/<int:schedule_id>", methods=["DELETE"])
def api_course_calendar_custom_schedule_delete(schedule_id):
    user, error = _require_auth()
    if error:
        return error
    item = get_course_calendar_custom_schedule(schedule_id)
    if not item:
        return jsonify({"error": "not found"}), 404
    visible = list_course_calendar_custom_schedules_for_actor(user, start_date=item["date"], end_date=item["date"])
    if not any(schedule["id"] == schedule_id for schedule in visible):
        return jsonify({"error": "forbidden"}), 403
    removed = delete_course_calendar_custom_schedule(schedule_id)
    return jsonify({"ok": True, "removed": removed})


@app.route("/api/classes", methods=["POST"])
def api_class_create():
    user, error = _require_staff()
    if error:
        return error
    data = request.json or {}
    name = (data.get("name") or "").strip()
    subject = (data.get("subject") or "").strip()
    grade = (data.get("grade") or "").strip()
    if not name:
        return jsonify({"error": "班级名称不能为空"}), 400
    if not subject:
        return jsonify({"error": "学科不能为空"}), 400
    cid = save_class(
        name=name,
        subject=subject,
        grade=grade,
        teacher_name=data.get("teacher_name", "").strip(),
        teacher_email=data.get("teacher_email", "").strip(),
        organization_id=user.get("organization_id"),
    )
    return jsonify({"id": cid, "name": name}), 201


@app.route("/api/classes/teacher-bindings", methods=["GET"])
def api_class_teacher_bindings_list():
    _, error = _require_staff()
    if error:
        return error
    return jsonify({"teacher_bindings": list_class_teacher_bindings()})


@app.route("/api/classes/<int:class_id>", methods=["GET"])
def api_class_get(class_id):
    user, error = _require_auth()
    if error:
        return error
    cls = get_class(class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    if not _filter_classes_for_user(user, [cls]):
        return jsonify({"error": "forbidden"}), 403
    lessons = list_lessons_for_actor(user, class_id=class_id)
    return jsonify({**cls, "lessons": _serialize_lessons_for_response(lessons)})


@app.route("/api/classes/<int:class_id>/invite", methods=["GET"])
def api_class_invite_get(class_id):
    user, error = _require_auth()
    if error:
        return error
    cls, error = _get_accessible_class_or_error(user, class_id)
    if error:
        return error
    invite = get_or_create_active_class_invite(cls["id"], user["id"])
    return jsonify(invite)


@app.route("/api/classes/<int:class_id>/invite/reset", methods=["POST"])
def api_class_invite_reset(class_id):
    user, error = _require_auth()
    if error:
        return error
    cls, error = _get_accessible_class_or_error(user, class_id)
    if error:
        return error
    invite = reset_class_invite(cls["id"], user["id"])
    return jsonify(invite)


@app.route("/api/classes/<int:class_id>/students", methods=["GET"])
def api_class_students_list(class_id):
    user, error = _require_auth()
    if error:
        return error
    _, error = _get_accessible_class_or_error(user, class_id)
    if error:
        return error
    return jsonify({"students": list_students_for_class(class_id)})


@app.route("/api/classes/<int:class_id>/students", methods=["POST"])
def api_class_students_create(class_id):
    user, error = _require_auth()
    if error:
        return error
    _, error = _get_accessible_class_or_error(user, class_id)
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    requested_name = (data.get("name") or "").strip()
    if not requested_name:
        return jsonify({"error": "student name is required"}), 400
    student = create_student_for_class(class_id, requested_name)
    return jsonify({
        "student": student,
        "requested_name": requested_name,
        "deduplicated": student["name"] != requested_name,
    }), 201


@app.route("/api/classes/<int:class_id>/students/<int:student_id>", methods=["DELETE"])
def api_class_students_delete(class_id, student_id):
    user, error = _require_auth()
    if error:
        return error
    _, error = _get_accessible_class_or_error(user, class_id)
    if error:
        return error
    removed = remove_student_from_class(class_id, student_id)
    return jsonify({"ok": True, "removed": removed})


@app.route("/api/classes/<int:class_id>/teacher", methods=["PUT"])
def api_class_teacher_set(class_id):
    user, error = _require_staff()
    if error:
        return error
    _, class_error = _get_accessible_class_or_error(user, class_id)
    if class_error:
        return class_error
    data = request.json or {}
    teacher_user_id = data.get("teacher_user_id")
    if teacher_user_id is not None and user.get("role") != "super_owner":
        teacher_user = get_user_by_id(teacher_user_id)
        if not teacher_user or teacher_user.get("organization_id") != user.get("organization_id"):
            return jsonify({"error": "user not found"}), 404
    try:
        set_class_teacher_user_id(class_id, teacher_user_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LookupError as exc:
        message = str(exc)
        status_code = 404 if message in {"class not found", "user not found"} else 400
        return jsonify({"error": message}), status_code
    return jsonify({"ok": True, "teacher_user_id": get_class_teacher_user_id(class_id)})


@app.route("/api/wechat/login", methods=["POST"])
def api_wechat_login():
    _, error = _require_wechat_service()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    open_id = (data.get("open_id") or "").strip()
    if not open_id:
        return jsonify({"error": "open_id is required"}), 400

    account = upsert_parent_wechat_account(
        openid=open_id,
        nickname_snapshot=(data.get("nickname_snapshot") or "").strip(),
        avatar_url_snapshot=(data.get("avatar_url_snapshot") or "").strip(),
    )
    return jsonify({"account": account})


@app.route("/api/wechat/bind-class", methods=["POST"])
def api_wechat_bind_class():
    _, error = _require_wechat_service()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    open_id = (data.get("open_id") or "").strip()
    invite_code = (data.get("invite_code") or "").strip()
    if not open_id or not invite_code:
        return jsonify({"error": "open_id and invite_code are required"}), 400

    account = _get_parent_wechat_account_by_openid(open_id)
    if not account:
        return jsonify({"error": "parent wechat account not found"}), 404

    invite = _get_active_class_invite_by_code(invite_code)
    if not invite:
        return jsonify({"error": "invite not found"}), 404

    cls = get_class(invite["class_id"])
    if not cls:
        return jsonify({"error": "class not found"}), 404

    teacher_user_id = get_class_teacher_user_id(cls["id"])
    teacher = get_user_by_id(teacher_user_id) if teacher_user_id else None
    return jsonify(
        {
            "account_id": account["id"],
            "class_id": cls["id"],
            "class_name": cls["name"],
            "teacher_user_id": teacher_user_id,
            "teacher_display_name": teacher.get("display_name") if teacher else "",
            "students": list_students_for_class(cls["id"]),
        }
    )


@app.route("/api/wechat/bind-student", methods=["POST"])
def api_wechat_bind_student():
    _, error = _require_wechat_service()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    open_id = (data.get("open_id") or "").strip()
    class_id = int(data.get("class_id") or 0)
    student_id = int(data.get("student_id") or 0)
    if not open_id or not class_id or not student_id:
        return jsonify({"error": "open_id, class_id and student_id are required"}), 400

    account = _get_parent_wechat_account_by_openid(open_id)
    if not account:
        return jsonify({"error": "parent wechat account not found"}), 404

    try:
        binding = bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=class_id,
            student_id=student_id,
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"binding": binding})


@app.route("/api/wechat/bindings", methods=["GET"])
def api_wechat_bindings_list():
    _, error = _require_wechat_service()
    if error:
        return error

    open_id = (request.args.get("open_id") or "").strip()
    if not open_id:
        return jsonify({"error": "open_id is required"}), 400

    account = _get_parent_wechat_account_by_openid(open_id)
    if not account:
        return jsonify({"error": "parent wechat account not found"}), 404

    return jsonify({"bindings": list_parent_student_bindings_for_openid(open_id)})

@app.route("/api/wechat/reason-transcriptions", methods=["POST"])
def api_wechat_reason_transcriptions_create():
    _, error = _require_wechat_service()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    audio_url = (data.get("audio_url") or "").strip()
    if not audio_url:
        return jsonify({"error": "audio_url is required"}), 400

    try:
        return jsonify(ai_processor.transcribe_child_reason_audio(audio_url))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc), "retryable": True}), 502


def _student_wrong_question_library_path(student_id: int) -> Path:
    library_dir = PDF_DIR / "wrong_question_libraries"
    library_dir.mkdir(parents=True, exist_ok=True)
    return library_dir / f"student-{student_id}.pdf"


def _wrong_question_practice_sheet_pdf_path(sheet_id: int) -> Path:
    practice_dir = PDF_DIR / "wrong_question_practice_sheets"
    practice_dir.mkdir(parents=True, exist_ok=True)
    return practice_dir / f"sheet-{sheet_id}.pdf"


def _parse_student_wrong_question_library_updated_at(value: str) -> Optional[datetime]:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _student_wrong_question_library_pdf_is_stale(records: list[dict], pdf_path: Path) -> bool:
    if not pdf_path.exists():
        return True

    latest_updated_at = None
    for record in records:
        parsed_updated_at = _parse_student_wrong_question_library_updated_at(record.get("updated_at") or "")
        if parsed_updated_at is None:
            continue
        if latest_updated_at is None or parsed_updated_at > latest_updated_at:
            latest_updated_at = parsed_updated_at

    if latest_updated_at is None:
        return True

    return latest_updated_at > datetime.fromtimestamp(pdf_path.stat().st_mtime)


def _rebuild_student_wrong_question_library(student_id: int) -> str:
    records = list_student_wrong_question_library_records(student_id)
    if not records:
        raise ValueError("student wrong question library has no records")
    output_path = _student_wrong_question_library_path(student_id)
    return pdf_engine.generate_student_wrong_question_library_pdf(
        student_name=str(records[0].get("student_name") or ""),
        class_name=str(records[0].get("class_display_name") or ""),
        records=records,
        output_path=str(output_path),
    )


def _refresh_student_wrong_question_library_cache(student_id: int) -> str:
    records = list_student_wrong_question_library_records(student_id)
    output_path = _student_wrong_question_library_path(student_id)
    if not records:
        output_path.unlink(missing_ok=True)
        set_student_wrong_question_library_pdf_path(student_id, "")
        return ""

    pdf_path = str(_rebuild_student_wrong_question_library(student_id) or "").strip()
    set_student_wrong_question_library_pdf_path(student_id, pdf_path)
    return pdf_path


_WECHAT_UPLOAD_TASK_STALE_SECONDS = 15 * 60


def _parse_wechat_upload_task_time(value: object) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None


def _is_wechat_upload_task_stale(task: dict) -> bool:
    if str(task.get("status") or "") not in {"pending", "processing"}:
        return False
    updated_at = _parse_wechat_upload_task_time(task.get("updated_at") or task.get("created_at"))
    if not updated_at:
        return False
    return (datetime.now() - updated_at).total_seconds() >= _WECHAT_UPLOAD_TASK_STALE_SECONDS


def _wechat_wrong_question_upload_task_parent_error_message(task: dict, record_status: str) -> str:
    if str(task.get("status") or "") != "failed":
        return ""
    if record_status == "recognized":
        return "错题已保存，PDF 暂时生成失败，请稍后再查看。"
    if record_status == "failed":
        return "错题处理失败，原图已保留，老师稍后可查看。"
    if bool(task.get("retryable")):
        return "上传任务暂时无法完成，请稍后重试。"
    return "上传任务处理失败，请稍后查看。"


def _wechat_wrong_question_upload_task_payload(task: dict) -> dict:
    payload = dict(task)
    status = str(payload.get("status") or "pending").strip() or "pending"
    payload["state"] = status
    payload["retryable"] = bool(payload.get("retryable"))
    payload["is_stale"] = _is_wechat_upload_task_stale(payload)
    payload["record_missing"] = False
    payload["record_status"] = ""
    payload["parent_error_message"] = ""
    payload["maintainer_error_detail"] = ""

    record_id = str(payload.get("record_id") or "").strip()
    record = get_wechat_wrong_question_submission(record_id) if record_id else None
    if record:
        payload["record_status"] = str(record.get("recognition_status") or "").strip()
    elif status == "ready" and record_id:
        payload["state"] = "missing_record"
        payload["record_missing"] = True
        payload["retryable"] = True

    if status == "failed":
        payload["maintainer_error_detail"] = str(payload.get("error_message") or "").strip()
        payload["parent_error_message"] = _wechat_wrong_question_upload_task_parent_error_message(
            payload,
            str(payload.get("record_status") or ""),
        )

    return payload


@app.route("/api/wechat/wrong-questions", methods=["POST"])
def api_wechat_wrong_questions_create():
    _, error = _require_wechat_service()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    open_id = (data.get("open_id") or "").strip()
    binding_id = int(data.get("binding_id") or 0)
    image_url = (data.get("image_url") or "").strip()
    child_raw_reason_text = (data.get("child_raw_reason_text") or "").strip()
    child_reason_input_mode = (data.get("child_reason_input_mode") or "text").strip() or "text"
    child_reason_audio_url = (data.get("child_reason_audio_url") or "").strip()
    topic_category = (data.get("topic_category") or data.get("topicCategory") or "").strip()
    if not open_id or not binding_id or not image_url:
        return jsonify({"error": "open_id, binding_id and image_url are required"}), 400

    account = _get_parent_wechat_account_by_openid(open_id)
    if not account:
        return jsonify({"error": "parent wechat account not found"}), 404

    binding = get_parent_student_binding(binding_id)
    if not binding or binding.get("parent_wechat_account_id") != account["id"]:
        return jsonify({"error": "binding not found"}), 404

    try:
        task = create_wechat_wrong_question_upload_task(
            binding_id=binding_id,
            image_url=image_url,
            child_raw_reason_text=child_raw_reason_text,
            child_reason_input_mode=child_reason_input_mode,
            child_reason_audio_url=child_reason_audio_url,
            topic_category=topic_category,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404

    try:
        enqueue_wechat_wrong_question_upload_task(task["id"])
    except Exception as exc:
        failed_task = update_wechat_wrong_question_upload_task(
            task["id"],
            status="failed",
            error_message=str(exc),
            retryable=True,
        )
        return jsonify(
            {
                "error": "上传任务暂时无法入队，请稍后重试",
                "retryable": True,
                "task": _wechat_wrong_question_upload_task_payload(failed_task or task),
            }
        ), 502

    return jsonify(
        {
            "task": _wechat_wrong_question_upload_task_payload(task),
            "student_library_pdf_url": f"/api/wechat/student-libraries/{binding['student_id']}",
        }
    ), 202


@app.route("/api/wechat/wrong-question-upload-tasks/<int:task_id>", methods=["GET"])
def api_wechat_wrong_question_upload_task_get(task_id: int):
    _, error = _require_wechat_service()
    if error:
        return error
    open_id = (request.args.get("open_id") or "").strip()
    if not open_id:
        return jsonify({"error": "open_id is required"}), 400
    task = get_wechat_wrong_question_upload_task_for_openid(task_id, open_id)
    if not task:
        return jsonify({"error": "task not found"}), 404
    return jsonify({"task": _wechat_wrong_question_upload_task_payload(task)})


@app.route("/api/wechat/wrong-questions/<record_id>/topic-category", methods=["PUT"])
def api_wechat_wrong_question_topic_category_save(record_id: str):
    _, error = _require_wechat_service()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    open_id = (data.get("open_id") or "").strip()
    topic_category = (data.get("topic_category") or data.get("topicCategory") or "").strip()
    if not open_id:
        return jsonify({"error": "open_id is required"}), 400

    account = _get_parent_wechat_account_by_openid(open_id)
    if not account:
        return jsonify({"error": "parent wechat account not found"}), 404

    local_record = get_wechat_wrong_question_submission(record_id)
    if not local_record:
        return jsonify({"error": "not found"}), 404
    binding = get_parent_student_binding_for_student(account["id"], int(local_record.get("student_id") or 0))
    if not binding:
        return jsonify({"error": "not found"}), 404

    saved_record = update_wechat_wrong_question_topic_category(record_id, topic_category=topic_category)
    if not saved_record:
        return jsonify({"error": "not found"}), 404
    _refresh_student_wrong_question_library_cache(local_record["student_id"])
    saved_record = get_wechat_wrong_question_submission(record_id)
    return jsonify({"ok": True, "record": saved_record})


@app.route("/api/wechat/primary-topic-category-suggestions", methods=["GET"])
def api_wechat_primary_topic_category_suggestions():
    _, error = _require_wechat_service()
    if error:
        return error
    open_id = (request.args.get("open_id") or "").strip()
    topic_category = (request.args.get("topic_category") or request.args.get("topicCategory") or "").strip()
    if not open_id:
        return jsonify({"error": "open_id is required"}), 400
    account = _get_parent_wechat_account_by_openid(open_id)
    if not account:
        return jsonify({"error": "parent wechat account not found"}), 404
    bindings = list_parent_student_bindings_for_openid(open_id)
    if not bindings:
        return jsonify({"items": []})
    organization_id = int(bindings[0].get("organization_id") or 0)
    return jsonify({
        "items": list_primary_topic_category_suggestions(
            organization_id=organization_id,
            topic_category=topic_category,
        )
    })


@app.route("/api/wechat/reason-classifications", methods=["POST"])
def api_wechat_reason_classifications():
    _, error = _require_wechat_service()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    child_reason_text = (data.get("child_reason_text") or "").strip()
    if not child_reason_text:
        return jsonify({"error": "child_reason_text is required"}), 400

    try:
        result = ai_processor.classify_wrong_question_reason(child_reason_text)
    except ValueError as exc:
        return jsonify({"error": str(exc), "retryable": True}), 422
    except Exception as exc:
        return jsonify({"error": str(exc), "retryable": True}), 502

    return jsonify({
        "display_text": result.get("display_text") or child_reason_text,
        "primary_error_type": result["primary_error_type"],
        "secondary_error_summary": result["secondary_error_summary"],
        "core_issue": result.get("core_issue") or "",
        "key_omission": result.get("key_omission") or "",
        "next_step": result.get("next_step") or "",
    })


@app.route("/api/wechat/children/<int:student_id>/wrong-questions", methods=["GET"])
def api_wechat_child_wrong_questions(student_id):
    _, error = _require_wechat_service()
    if error:
        return error

    open_id = (request.args.get("open_id") or "").strip()
    if not open_id:
        return jsonify({"error": "open_id is required"}), 400

    account = _get_parent_wechat_account_by_openid(open_id)
    if not account:
        return jsonify({"error": "parent wechat account not found"}), 404

    binding = get_parent_student_binding_for_student(account["id"], student_id)
    if not binding:
        return jsonify({"error": "binding not found"}), 404

    items = list_wechat_wrong_question_submissions_for_parent_student(
        parent_wechat_account_id=account["id"],
        student_id=student_id,
    )
    return jsonify({"items": items, "total": len(items)})


@app.route("/api/wechat/children/<int:student_id>/wrong-question-library", methods=["GET"])
def api_wechat_child_wrong_question_library(student_id):
    _, error = _require_wechat_service()
    if error:
        return error

    open_id = (request.args.get("open_id") or "").strip()
    if not open_id:
        return jsonify({"error": "open_id is required"}), 400

    account = _get_parent_wechat_account_by_openid(open_id)
    if not account:
        return jsonify({"error": "parent wechat account not found"}), 404

    binding = get_parent_student_binding_for_student(account["id"], student_id)
    if not binding:
        return jsonify({"error": "binding not found"}), 404

    items = list_student_wrong_question_library_records(student_id)
    latest_updated_at = str(items[0].get("updated_at") or "") if items else ""
    return jsonify(
        {
            "student_id": student_id,
            "pdf_url": f"/api/wechat/student-libraries/{student_id}",
            "updated_at": latest_updated_at,
            "total_items": len(items),
        }
    )


@app.route("/api/wechat/student-libraries/<int:student_id>", methods=["GET"])
def api_wechat_student_library_pdf(student_id):
    records = list_student_wrong_question_library_records(student_id)
    if not records:
        return jsonify({"error": "student library pdf not found"}), 404
    pdf_path = _student_wrong_question_library_path(student_id)
    if _student_wrong_question_library_pdf_is_stale(records, pdf_path):
        rebuilt_pdf_path = _refresh_student_wrong_question_library_cache(student_id)
        pdf_path = Path(rebuilt_pdf_path) if rebuilt_pdf_path else pdf_path
    if not pdf_path.exists():
        return jsonify({"error": "student library pdf not found"}), 404
    return send_file(pdf_path, mimetype="application/pdf", download_name=pdf_path.name)


@app.route("/api/classes/<int:class_id>", methods=["PUT"])
def api_class_update(class_id):
    user, error = _require_staff()
    if error:
        return error
    cls = get_class(class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    if not _filter_classes_for_user(user, [cls]):
        return jsonify({"error": "forbidden"}), 403
    data = request.json or {}
    name = (data.get("name") or "").strip()
    subject = (data.get("subject") or "").strip()
    grade = (data.get("grade") or "").strip()
    if not name:
        return jsonify({"error": "班级名称不能为空"}), 400
    if not subject:
        return jsonify({"error": "学科不能为空"}), 400
    teacher_name = None
    if "teacher_name" in data:
        teacher_name = (data.get("teacher_name") or "").strip()
    teacher_email = None
    if "teacher_email" in data:
        teacher_email = (data.get("teacher_email") or "").strip()
    update_class(
        class_id=class_id,
        name=name,
        subject=subject,
        grade=grade,
        teacher_name=teacher_name,
        teacher_email=teacher_email,
    )
    return jsonify({"ok": True})


@app.route("/api/classes/<int:class_id>", methods=["DELETE"])
def api_class_delete(class_id):
    user, error = _require_staff()
    if error:
        return error
    cls = get_class(class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    if not _filter_classes_for_user(user, [cls]):
        return jsonify({"error": "forbidden"}), 403
    db_delete_class(class_id)
    return jsonify({"ok": True})


@app.route("/api/review-plans", methods=["GET"])
def api_lessons_list():
    user, error = _require_auth()
    if error:
        return error
    month = request.args.get("month", "")
    class_id = request.args.get("class_id", 0, type=int)
    lessons = list_lessons_for_actor(
        user,
        month_str=month if month else "",
        class_id=class_id if class_id else 0,
    )
    return jsonify(_serialize_lessons_for_response(_filter_lessons_for_user(user, lessons)))


@app.route("/api/review-plans/<int:lesson_id>", methods=["GET"])
def api_lesson_get(lesson_id):
    user, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        return jsonify({"error": "not found"}), 404
    serialized_lesson = _serialize_lesson_for_response(lesson)
    if serialized_lesson is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(serialized_lesson)


@app.route("/api/review-plans/<int:lesson_id>", methods=["DELETE"])
def api_lesson_delete(lesson_id):
    user, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        return jsonify({"error": "not found"}), 404
    pdf_path = lesson.get("pdf_path", "")
    if pdf_path and Path(pdf_path).exists():
        Path(pdf_path).unlink(missing_ok=True)
    db_delete_lesson(lesson_id)
    return jsonify({"ok": True})


@app.route("/api/review-plans", methods=["POST"])
def api_lesson_create():
    user, error = _require_auth()
    if error:
        return error
    if not has_api_key():
        return jsonify({"error": "系统 API Key 未配置，请联系管理员"}), 400
    
    if request.is_json:
        data = request.json or {}
    else:
        data = request.form or {}
        
    lesson_date = data.get("date") or str(date.today())
    class_id = int(data.get("class_id") or 0)
    if not class_id and user.get("role") == "member":
        return jsonify({"error": "请选择班级后再生成复习记录"}), 400

    cls = None
    if class_id:
        cls, class_error = _get_accessible_class_or_error(user, class_id)
        if class_error:
            return class_error

    subject     = data.get("subject", "").strip() or (cls["subject"] if cls else "")
    grade       = data.get("grade", "").strip() or (cls["grade"] if cls else "")
    topic       = data.get("topic", "").strip()
    weak_points = data.get("weak_points", "").strip()
    
    input_type = data.get("input_type", "text")
    raw_text = ""
    chat_provider = _default_ai_provider_name()
    chat_model = _default_chat_model_name()
    
    if input_type == "text" or request.is_json:
        raw_text = data.get("summary_text", "").strip()
        if not raw_text:
            return jsonify({"error": "请填写课堂总结内容"}), 400
    else:
        file = request.files.get("upload_file")
        if not file or not file.filename:
            return jsonify({"error": "请上传音频或文本文件"}), 400
        
        ext = Path(file.filename).suffix.lower()
        if ext in {".mp3", ".m4a", ".mp4", ".wav", ".ogg", ".webm", ".flac"}:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = UPLOAD_DIR / f"audio_{ts}{ext}"
            file.save(str(save_path))
            
            if save_path.stat().st_size > 25 * 1024 * 1024:
                save_path.unlink(missing_ok=True)
                return jsonify({"error": "音频文件过大（最大 25MB）"}), 400
                
            try:
                from ai_processor import transcribe_audio
                raw_text = _run_ai_feature_with_charge(
                    user=user,
                    feature_key="audio_transcription",
                    source_record_type="lesson_upload",
                    source_record_id=f"upload:{_request_payload_fingerprint(include_file_content=True)}",
                    producer=lambda: _call_ai_helper_with_usage(transcribe_audio, str(save_path)),
                    provider="local",
                    model="faster-whisper-base",
                    request_key=_current_audio_upload_request_key(),
                )
            except DuplicateAiRequestError as exc:
                save_path.unlink(missing_ok=True)
                return jsonify({"error": str(exc)}), 409
            except CreditBalanceError as exc:
                save_path.unlink(missing_ok=True)
                return jsonify({"error": str(exc)}), 402
            except Exception as e:
                save_path.unlink(missing_ok=True)
                return jsonify({"error": f"音频转录失败：{e}"}), 500
            save_path.unlink(missing_ok=True)
        elif ext in {".txt", ".md", ".text"}:
            raw_text = file.read().decode("utf-8", errors="replace")
        else:
            return jsonify({"error": f"不支持的文件格式 {ext}"}), 400

    if not raw_text:
        return jsonify({"error": "提取的总结内容为空"}), 400

    request_key = _current_ai_request_key()
    request_id = _build_review_plan_request_id(
        user_id=int(user["id"]),
        request_key=request_key,
    )
    request_identity_claimed = False
    try:
        _claim_ai_request_identity(
            organization_id=int(user["organization_id"]),
            request_id=request_id,
        )
        request_identity_claimed = True
        ensure_feature_credits_available(
            organization_id=int(user["organization_id"]),
            feature_key="lesson_plan_generate",
        )
    except DuplicateAiRequestError as exc:
        return jsonify({"error": str(exc)}), 409
    except CreditBalanceError as exc:
        if request_identity_claimed:
            _release_ai_request_identity(request_id)
        return jsonify({"error": str(exc)}), 402
    except Exception:
        if request_identity_claimed:
            _release_ai_request_identity(request_id)
        raise

    lesson_id = 0
    try:
        lesson_id = create_pending_lesson(
            date_str=lesson_date,
            subject=subject,
            grade=grade,
            topic=topic,
            summary=raw_text,
            weak_points=weak_points,
            class_id=class_id,
        )
        _start_review_plan_generation_thread(
            lesson_id=lesson_id,
            user={
                "id": int(user["id"]),
                "organization_id": int(user["organization_id"]),
            },
            chat_provider=chat_provider,
            chat_model=chat_model,
            request_key=request_key,
            request_id=request_id,
        )
    except Exception:
        if lesson_id:
            db_delete_lesson(lesson_id)
        if request_identity_claimed:
            _release_ai_request_identity(request_id)
        raise
    return jsonify({"id": lesson_id, "success": True, "status": "pending"}), 202


@app.route("/api/class-feedback/labels", methods=["GET"])
def api_class_feedback_labels_get():
    user, error = _require_auth()
    if error:
        return error
    return jsonify({"groups": list_class_feedback_label_configs(user["id"])})


@app.route("/api/class-feedback/labels", methods=["PUT"])
def api_class_feedback_labels_put():
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    groups = data.get("groups")
    if not isinstance(groups, list):
        groups = []
    try:
        save_class_feedback_label_configs(user["id"], groups)
    except LookupError:
        return jsonify({"error": "not found"}), 404
    return jsonify({"groups": list_class_feedback_label_configs(user["id"])})


@app.route("/api/class-feedback/tasks", methods=["POST"])
def api_class_feedback_task_create():
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    class_id = data.get("class_id")
    if isinstance(class_id, bool) or not isinstance(class_id, int):
        return jsonify({"error": "class_id must be an integer"}), 400
    cls, error = _get_accessible_class_or_error(user, class_id)
    if error:
        return error

    start_date = str(data.get("start_date") or "").strip()
    end_date = str(data.get("end_date") or "").strip()
    period_granularity = str(data.get("period_granularity") or "").strip()
    anchor_date = str(data.get("anchor_date") or "").strip()
    year = data.get("year")
    week = data.get("week")
    month = data.get("month")
    stage_name = str(data.get("stage_name") or "").strip()
    if not period_granularity and start_date and start_date == end_date:
        period_granularity = "daily"
        anchor_date = anchor_date or start_date
    teacher_name_snapshot = (
        str(cls.get("teacher_name") or "").strip()
        or str(user.get("display_name") or "").strip()
        or str(user.get("username") or "").strip()
        or "未命名老师"
    )

    try:
        task = create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=cls.get("teacher_user_id"),
            teacher_name_snapshot=teacher_name_snapshot,
            start_date=start_date,
            end_date=end_date,
            period_granularity=period_granularity or None,
            anchor_date=anchor_date or None,
            year=year,
            week=week,
            month=month,
            stage_name=stage_name or None,
            created_by=user["id"],
        )
    except LookupError:
        return jsonify({"error": "not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(task), 201


@app.route("/api/class-feedback/tasks/<int:task_id>", methods=["GET"])
def api_class_feedback_task_get(task_id: int):
    user, error = _require_auth()
    if error:
        return error
    task, error = _get_accessible_class_feedback_task_or_error(user, task_id)
    if error:
        return error
    return jsonify(task)


@app.route("/api/class-feedback/tasks/<int:task_id>/generate", methods=["POST"])
def api_class_feedback_generate(task_id: int):
    user, error = _require_auth()
    if error:
        return error
    task, error = _get_accessible_class_feedback_task_or_error(user, task_id)
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    if task.get("status") == "confirmed":
        return jsonify({"error": "已确认任务不能重新生成，请先创建新任务"}), 409

    provider = _default_ai_provider_name()
    model = _default_chat_model_name()

    try:
        notes_payload = _normalize_class_feedback_notes_payload(task, data)
        task = save_class_feedback_task_notes(task_id, **notes_payload)
        context = _build_class_feedback_generation_context(task, user)
        bundle = _run_ai_feature_with_charge(
            user=user,
            feature_key="class_feedback_generate",
            source_record_type="class_feedback_task",
            source_record_id=task_id,
            producer=lambda: _call_ai_helper_with_usage(
                generate_class_feedback_bundle,
                **context,
            ),
            provider=provider,
            model=model,
        )
        student_entries = []
        for item in bundle.get("student_entries") or []:
            if not isinstance(item, dict):
                continue
            student_id = item.get("student_id")
            if not isinstance(student_id, int):
                continue
            student_entries.append(
                {
                    "student_id": student_id,
                    "name": str(item.get("name") or "").strip(),
                    "ai_draft": str(item.get("text") or "").strip(),
                }
            )
        saved_task = save_class_feedback_generation_result(
            task_id,
            class_summary_ai_draft=str(bundle.get("class_summary") or "").strip(),
            student_entries=student_entries,
        )
    except DuplicateAiRequestError as exc:
        return jsonify({"error": str(exc)}), 409
    except CreditBalanceError as exc:
        return jsonify({"error": str(exc)}), 402
    except LookupError:
        return jsonify({"error": "not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("Class feedback generation failed for task %s", task_id)
        return jsonify({"error": "生成课堂反馈时发生错误，请稍后重试"}), 500
    return jsonify(saved_task)


@app.route("/api/class-feedback/tasks/<int:task_id>/draft", methods=["POST"])
def api_class_feedback_save_draft(task_id: int):
    user, error = _require_auth()
    if error:
        return error
    _, error = _get_accessible_class_feedback_task_or_error(user, task_id)
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    try:
        draft_task = save_class_feedback_draft(
            task_id,
            class_summary_draft_text=str(data.get("class_summary_draft_text") or "").strip(),
            student_entries=data.get("student_entries") or [],
        )
    except LookupError:
        return jsonify({"error": "not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("Class feedback draft save failed for task %s", task_id)
        return jsonify({"error": "保存课堂反馈草稿时发生错误，请稍后重试"}), 500
    return jsonify(draft_task)


@app.route("/api/class-feedback/tasks/<int:task_id>/confirm", methods=["POST"])
def api_class_feedback_confirm(task_id: int):
    user, error = _require_auth()
    if error:
        return error
    _, error = _get_accessible_class_feedback_task_or_error(user, task_id)
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    try:
        confirmed_task = confirm_class_feedback_task(
            task_id,
            class_summary_final_text=str(data.get("class_summary_final_text") or "").strip(),
            student_entries=data.get("student_entries") or [],
        )
    except LookupError:
        return jsonify({"error": "not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("Class feedback confirm failed for task %s", task_id)
        return jsonify({"error": "确认课堂反馈时发生错误，请稍后重试"}), 500
    return jsonify(confirmed_task)


@app.route("/api/monthly", methods=["GET"])
def api_monthly_list():
    _, error = _require_auth()
    if error:
        return error
    months = _get_all_months()
    monthly_pdfs = _get_monthly_pdfs()
    return jsonify({
        "months": [{"month": m, "count": len(list_lessons(m)),
                    "has_pdf": m in monthly_pdfs} for m in months]
    })


@app.route("/api/monthly/generate", methods=["POST"])
def api_monthly_generate():
    user, error = _require_auth()
    if error:
        return error
    if not has_api_key():
        return jsonify({"error": "请先在设置页面填入 API Key"}), 400
    data = request.json or {}
    month_str = data.get("month") or datetime.now().strftime("%Y-%m")
    lessons = list_lessons(month_str)
    if not lessons:
        return jsonify({"error": f"{month_str} 没有课程记录"}), 400
    lesson_dicts = [{"date": l["date"], "subject": l["subject"] or "",
                     "grade": l["grade"] or "", "topic": l["topic"] or "",
                     "summary": (l["summary"] or "")[:800],
                     "weak_points": l["weak_points"] or ""} for l in lessons]
    provider = _default_ai_provider_name()
    model = _default_chat_model_name()

    job = create_monthly_plan_job(
        organization_id=int(user["organization_id"]),
        user_id=int(user["id"]),
        month_str=month_str,
    )
    _start_monthly_plan_generation_thread(
        job_id=job["id"],
        user={"id": int(user["id"]), "organization_id": int(user["organization_id"])},
        month_str=month_str,
        lesson_dicts=lesson_dicts,
        chat_provider=provider,
        chat_model=model,
    )
    return jsonify({"id": job["id"], "status": "pending"}), 202


@app.route("/api/monthly/jobs/<int:job_id>", methods=["GET"])
def api_monthly_job_get(job_id: int):
    user, error = _require_auth()
    if error:
        return error
    job = get_monthly_plan_job(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job)


@app.route("/api/monthly/jobs/<int:job_id>/retry", methods=["POST"])
def api_monthly_job_retry(job_id: int):
    user, error = _require_auth()
    if error:
        return error
    if not has_api_key():
        return jsonify({"error": "请先在设置页面填入 API Key"}), 400
    job = get_monthly_plan_job(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    if job["status"] != "failed":
        return jsonify({"error": "只有失败的任务才能重试"}), 400
    requeued = requeue_monthly_plan_job(job_id)
    month_str = requeued["month_str"]
    lessons = list_lessons(month_str)
    lesson_dicts = [{"date": l["date"], "subject": l["subject"] or "",
                     "grade": l["grade"] or "", "topic": l["topic"] or "",
                     "summary": (l["summary"] or "")[:800],
                     "weak_points": l["weak_points"] or ""} for l in lessons]
    provider = _default_ai_provider_name()
    model = _default_chat_model_name()
    _start_monthly_plan_generation_thread(
        job_id=requeued["id"],
        user={"id": int(user["id"]), "organization_id": int(user["organization_id"])},
        month_str=month_str,
        lesson_dicts=lesson_dicts,
        chat_provider=provider,
        chat_model=model,
    )
    return jsonify({"id": requeued["id"], "status": "pending"}), 202


@app.route("/api/analyze", methods=["POST"])
def api_analyze_text():
    _, error = _require_auth()
    if error:
        return error
    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "请提供文本内容"}), 400
    try:
        from ai_processor import _get_client, _get_chat_model
        client = _get_client()
        resp = client.chat.completions.create(
            model=_get_chat_model(),
            messages=[
                {"role": "system", "content": (
                    "你是教学助手。根据课堂笔记提取关键信息，以JSON格式返回，"
                    "包含三个字段：subject（科目，如语文/数学/英语等，若无法判断则为空字符串）、"
                    "topic（本节课主题，简短概括，不超过20字）、"
                    "weak_points（学生薄弱点，若无明显提及则为空字符串）。只返回JSON，不要其他文字。"
                )},
                {"role": "user", "content": f"课堂笔记：\n{text}"},
            ],
            temperature=0.3,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        result = json.loads(raw)
        return jsonify({
            "subject": result.get("subject", ""),
            "topic": result.get("topic", ""),
            "weak_points": result.get("weak_points", ""),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    _, error = _require_auth()
    if error:
        return error
    cfg = get_config()
    controlled_keys = env_controlled_keys()
    def _mask(k):
        return (k[:4] + "..." + k[-4:]) if len(k) > 8 else ("*" * len(k) if k else "")
    return jsonify({
        "provider": cfg.get("provider", "deepseek"),
        "openai_set": bool(cfg.get("openai_api_key")),
        "openai_masked": _mask(cfg.get("openai_api_key", "")),
        "deepseek_set": bool(cfg.get("deepseek_api_key")),
        "deepseek_masked": _mask(cfg.get("deepseek_api_key", "")),
        "mimo_set": bool(cfg.get("mimo_api_key")),
        "mimo_masked": _mask(cfg.get("mimo_api_key", "")),
        "mimo_base_url": cfg.get("mimo_base_url", ""),
        "n1n_set": bool(cfg.get("n1n_api_key")),
        "n1n_masked": _mask(cfg.get("n1n_api_key", "")),
        "n1n_base_url": cfg.get("n1n_base_url", "https://api.n1n.ai/v1"),
        "controlled_keys": sorted(controlled_keys),
    })


@app.route("/api/settings", methods=["POST"])
def api_settings_save():
    _, error = _require_auth()
    if error:
        return error
    cfg = load_file_config()
    data = request.json or {}
    controlled_keys = env_controlled_keys()
    if "provider" in data and "provider" not in controlled_keys:
        cfg["provider"] = data["provider"].strip()
    for key in ("openai_api_key", "deepseek_api_key", "mimo_api_key", "mimo_base_url", "n1n_api_key", "n1n_base_url"):
        if data.get(key) and key not in controlled_keys:
            cfg[key] = data[key].strip()
    write_file_config(cfg)
    return jsonify({"ok": True, "controlled_keys": sorted(controlled_keys)})


# ─── 启动 ──────────────────────────────────────────────────────────────────────
def _open_browser():
    import time
    time.sleep(1.5)
    webbrowser.open(_browser_url())


def _browser_url() -> str:
    return os.environ.get("XR_BROWSER_URL", "http://127.0.0.1:3000").strip() or "http://127.0.0.1:3000"


def _should_open_browser() -> bool:
    raw = os.environ.get("XR_OPEN_BROWSER", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _startup_browser_message() -> str:
    if _should_open_browser():
        return f"  浏览器即将自动打开：{_browser_url()}"
    return f"  未自动打开浏览器；前端页面入口：{_browser_url()}"


if __name__ == "__main__":
    init_db()
    if _should_open_browser():
        threading.Thread(target=_open_browser, daemon=True).start()
    print("\n" + "=" * 50)
    print("  📚 复习计划管理系统已启动")
    print(_startup_browser_message())
    print("  后端地址：http://127.0.0.1:5001")
    print("  按 Ctrl+C 关闭程序")
    print("=" * 50 + "\n")
    app.run(host="127.0.0.1", port=5001, debug=False)
