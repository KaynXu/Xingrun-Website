#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
复习计划管理系统 — 后端 / API 服务 (Flask)
启动方式：双击 start.command（macOS）或 start.bat（Windows）
前端地址：http://127.0.0.1:3000
后端地址：http://127.0.0.1:5001
"""

from __future__ import annotations

import difflib
import hashlib
import io
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import webbrowser
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from time import monotonic, sleep, time
from typing import Optional, Set

from flask import Flask, abort, redirect, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from config_runtime import (
    chat_model_for_provider,
    env_controlled_keys,
    get_runtime_config,
    load_file_config,
    normalize_chat_provider,
    normalize_reasoning_effort,
    normalize_temperature,
    resolve_class_commentary_model,
    resolve_class_commentary_provider,
    resolve_review_plan_model,
    resolve_review_plan_provider,
    resolve_review_plan_reasoning_effort,
    resolve_review_plan_writer_model,
    resolve_review_plan_writer_provider,
    write_file_config,
)
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
REVIEW_PLAN_AUDIO_MAX_BYTES = 100 * 1024 * 1024
REVIEW_PLAN_AUDIO_MAX_LABEL = "100MB"
PROFILE_AVATAR_MAX_BYTES = 4 * 1024 * 1024
PROFILE_AVATAR_MAX_LABEL = "4MB"
CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:8080", "http://127.0.0.1:8080",
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:3000", "http://127.0.0.1:3000",
]}})
logger = logging.getLogger(__name__)

_WRONG_QUESTION_PRACTICE_PDF_RETRY_DELAYS_SECONDS = (1, 3, 5)

# ─── 内部模块 ──────────────────────────────────────────────────────────────────
from lesson_manager import (
    ClassCommentaryConfirmationRequestConflict,
    ClassCommentaryDraftVersionConflict,
    ClassCommentaryFeedbackSchemaInvalid,
    ClassCommentaryFeedbackSchemaMismatch,
    ClassCommentaryFeedbackSchemaUnsupported,
    ClassCommentaryGenerationRequestConflict,
    ClassCommentaryTranscriptSnapshotConflict,
    ClassCommentaryCreditReservationError,
    ClassCommentaryStudentGenerationRetryRequestConflict,
    ClassCommentaryMemoryEvidenceNotRevocable,
    ClassCommentaryMemoryEvidenceRequestConflict,
    ClassCommentaryMemoryNotEnabled,
    ClassCommentaryMemoryRetryRequestConflict,
    ClassCommentaryMemoryRevisionNotRetryable,
    ClassCommentaryRevisionVersionConflict,
    ClassCommentarySkillActivationRequestConflict,
    ClassCommentarySkillCandidateNotReady,
    ClassCommentarySkillCandidateRequestConflict,
    ClassCommentarySkillCandidateStale,
    ClassCommentarySkillImportConflict,
    ClassCommentarySkillVersionConflict,
    activate_class_commentary_skill_candidate_version,
    actor_can_manage_user,
    attach_student_library_pdf_path,
    build_wrong_question_practice_pack_schedule,
    append_consultation_test_image_for_actor,
    remove_consultation_test_image_for_actor,
    clean_consultation_batch_input,
    DEFAULT_ORGANIZATION_NAME,
    approve_organization_request,
    approve_registration_request,
    authenticate_user,
    add_existing_student_to_class,
    authenticate_student_account,
    bind_parent_to_student,
    complete_review_plan_version,
    create_class_commentary_task,
    create_class_commentary_skill_candidate_build,
    complete_class_commentary_generation,
    confirm_class_commentary_feedback,
    create_review_plan_version,
    create_pending_lesson,
    create_pending_wrong_question_practice_sheet,
    create_wrong_question_asset,
    create_wrong_question_chat_message,
    create_wrong_question_chat_session,
    create_wrong_question_ingestion_run,
    create_wrong_question_submission,
    create_wrong_question_practice_pack_job,
    create_wechat_wrong_question_upload_task,
    create_organization_request,
    create_auth_session,
    create_student_account_by_invite,
    create_student_auth_session,
    create_consultation,
    create_course_calendar_custom_item,
    create_course_calendar_custom_schedule,
    create_course_calendar_schedule,
    create_registration_request,
    create_student_profile,
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
    delete_or_archive_student_profile,
    enter_consultation_class,
    find_active_wrong_question_practice_pack_job,
    fail_review_plan_version,
    get_class,
    get_class_commentary_task,
    get_class_commentary_feedback_draft,
    get_class_commentary_generation,
    get_class_commentary_generation_by_request,
    get_class_commentary_memory_evidence,
    get_class_commentary_revision,
    get_class_commentary_skill_candidate_build,
    get_class_commentary_skill_candidate_eligibility,
    get_class_commentary_skill_for_organization,
    get_class_teacher_user_id,
    get_conn,
    get_consultation,
    get_consultation_for_actor,
    get_course_calendar_custom_item,
    get_course_calendar_custom_schedule,
    get_course_calendar_schedule,
    get_current_user,
    get_current_student_account,
    get_current_review_plan_version,
    get_parent_student_binding,
    get_parent_student_binding_for_student,
    get_active_class_invite_by_code,
    get_or_create_active_class_invite,
    get_lesson,
    get_latest_review_plan_run_for_lesson,
    get_review_plan_version,
    get_review_plan_version_for_lesson,
    get_student_profile,
    get_wrong_question_chat_session,
    get_weekly_wrong_question_followup_message,
    get_wrong_question_practice_pack_job,
    get_wrong_question_practice_sheet,
    get_wrong_question_ingestion_run,
    get_or_create_active_organization_invite,
    get_organization_invite_by_token,
    get_registration_request,
    get_user_by_id,
    get_user_class_ids,
    get_latest_completed_review_plan_quality_run_for_version,
    init_db,
    list_all_users,
    list_class_history,
    list_class_commentary_tasks_for_classes,
    list_class_commentary_tasks_for_organization,
    list_class_commentary_generations,
    get_class_commentary_student_generation_progress,
    retry_class_commentary_student_generation_runs,
    list_class_commentary_revision_memories,
    list_class_commentary_revisions,
    list_class_commentary_skill_versions,
    list_class_commentary_skills_for_organization,
    import_class_commentary_skill_manifest,
    refresh_class_commentary_skill_manifest,
    list_class_teacher_bindings,
    list_classes,
    list_classes_for_actor,
    list_consultation_teachers,
    list_consultations_for_actor,
    list_course_calendar_custom_items_for_actor,
    list_course_calendar_custom_schedules_for_actor,
    list_course_calendar_schedules_for_actor,
    list_lessons,
    list_lessons_for_actor,
    list_lessons_page_for_actor,
    list_review_plan_versions,
    list_unseen_review_plan_failure_notifications,
    list_wrong_question_practice_sheets_for_student,
    list_wrong_question_practice_pack_jobs_for_class,
    list_targeted_wrong_question_practice_candidates,
    list_organizations,
    list_organization_requests,
    list_parent_student_bindings_for_openid,
    list_primary_topic_category_suggestions,
    list_duplicate_student_profiles,
    list_students_for_organization,
    list_student_wrong_question_library_records,
    list_wrong_question_chat_messages,
    list_wrong_question_ingestion_runs,
    list_wrong_question_submissions_for_chat_session,
    list_wrong_question_assets,
    list_wrong_question_submissions_for_ingestion_run,
    list_student_review_tasks_for_student_account,
    list_students_for_class,
    list_student_class_history,
    list_wechat_wrong_question_submissions_for_parent_student,
    list_wechat_wrong_question_submissions,
    list_weekly_wrong_question_activity_summary,
    list_weekly_wrong_question_followup_students,
    list_registration_requests_for_actor,
    list_unbound_classes_for_user_claim,
    list_users_for_actor,
    join_organization_by_invite_code,
    join_organization_by_invite_link_token,
    lesson_has_active_review_plan_version,
    normalize_consultation_batch_parse_result,
    preview_student_class_invite,
    reject_organization_request,
    reject_registration_request,
    retry_class_commentary_memory_revision,
    revoke_class_commentary_memory_evidence,
    rollback_class_commentary_skill_version,
    requeue_lesson_generation,
    reset_class_invite,
    reset_organization_invite,
    remove_student_from_class,
    save_class,
    save_class_commentary_feedback_draft,
    save_class_commentary_transcript,
    reserve_class_commentary_generation,
    fail_class_commentary_generation,
    mark_class_commentary_task_failed,
    mark_class_commentary_task_transcribing,
    mark_class_commentary_raw_transcription_succeeded,
    mark_class_commentary_transcription_succeeded,
    mark_class_commentary_transcript_polish_failed,
    mark_class_commentary_transcript_polish_succeeded,
    mark_review_plan_version_transcription_succeeded,
    mark_lesson_generation_failed,
    mark_lesson_generation_succeeded,
    mark_lesson_transcription_succeeded,
    mark_review_plan_failure_notifications_seen,
    mark_wrong_question_practice_pack_job_status,
    mark_wrong_question_practice_sheet_failed,
    mark_wrong_question_practice_sheet_succeeded,
    create_monthly_plan_job,
    get_monthly_plan_job,
    mark_monthly_plan_job_failed,
    mark_monthly_plan_job_succeeded,
    requeue_monthly_plan_job,
    set_class_teacher_user_id,
    set_current_review_plan_version,
    set_student_wrong_question_library_pdf_path,
    set_user_class_ids,
    set_wechat_wrong_question_archive_status,
    get_wechat_wrong_question_submission,
    get_wechat_wrong_question_upload_task_for_openid,
    save_wechat_wrong_question_review,
    update_wechat_wrong_question_upload_task,
    update_wechat_wrong_question_question_text,
    update_wechat_wrong_question_topic_category,
    update_wrong_question_submission_from_chat_archive,
    update_wrong_question_submission_mastery_followup,
    update_wrong_question_chat_session,
    update_wrong_question_ingestion_run,
    update_user_display_name_for_actor,
    update_user_visible_pages_for_actor,
    update_class,
    update_consultation,
    update_consultation_for_actor,
    update_student_profile,
    update_user_profile,
    resolve_teacher_username_to_user_id,
    update_user_role,
    upsert_wrong_question_practice_pack_job_student,
    upsert_weekly_wrong_question_followup_message,
    upsert_parent_wechat_account,
    get_teacher_alias_entries,
    upsert_teacher_alias,
    delete_teacher_alias,
    change_user_password,
    reset_user_password_by_recovery,
    student_account_can_access_lesson,
    update_review_plan_version_pdf_path,
    update_review_plan_version_source_artifact,
    update_user_avatar_preferences,
)
from ai_processor import generate_class_commentary_feedback, parse_consultation_batch_text, polish_class_commentary_transcript, polish_review_plan_transcript, transcribe_audio
from class_commentary import (
    CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V5,
    CLASS_COMMENTARY_PROMPT_VERSION,
    CLASS_COMMENTARY_TEMPERATURE,
    list_colleague_skills,
    load_colleague_skill,
    payload_to_json,
    sanitize_class_commentary_roster,
)
from class_commentary_feedback_schema import (
    CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3,
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
    ClassCommentaryStudentScopeError,
    ClassCommentaryStructuredFeedbackValidationError,
    build_class_commentary_feedback_read_envelope,
)
from class_commentary_memory import ClassCommentaryMemoryService
from class_commentary_memory_queue import (
    class_commentary_memory_queue_healthcheck,
    dispatch_class_commentary_memory_work,
)
from class_commentary_graph_queue import dispatch_class_commentary_graph_work
from class_commentary_learning_graph import (
    LearningGraphSnapshotIntegrityError,
    LearningGraphValidationError,
    LearningGraphRetryConflict,
    get_student_learning_graph_summary,
    list_graph_candidate_ids_for_proposal,
    list_graph_unmapped_candidates,
    resolve_graph_unmapped_candidate,
    retry_graph_revision,
)
from class_commentary_semantica import SemanticaGraphAdapter
import curriculum_registry
from class_commentary_batch_context import (
    ClassCommentaryBatchContextError,
    parse_frozen_batch_generation_inputs,
)
from class_commentary_student_memory_v2 import (
    content_hash as class_commentary_student_content_hash,
)
from class_commentary_batch_generation_jobs import (
    process_class_commentary_batch_generation,
)
import smart_wrong_questions
import master_data
from review_plan_workflow.generation_options import normalize_generation_options
from review_plan_workflow.schemas import normalize_final_review_plan
from review_plan_workflow.source_brief import build_deterministic_source_brief, clean_source_text, source_text_hash
from review_plan_workflow.source_pack import source_pack_needs_rebuild
from review_plan_workflow.transcript_polish import review_plan_transcript_source_text_hash
from wrong_question_upload_queue import enqueue_wechat_wrong_question_upload_task
from credit_manager import (
    CreditBalanceError,
    ensure_feature_credits_available,
    ensure_feature_credits_available_for_count,
    finalize_ai_charge,
    get_ai_usage_by_request_id,
    get_credit_overview,
    list_credit_ledger,
    list_member_usage_detail,
    list_member_usage_summary,
    max_configured_charge_for_feature,
    redeem_xhs_order,
)
from xhs_open_platform import fetch_xhs_order_for_redemption

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
_AI_ORGANIZATION_CONCURRENCY_LIMIT = 10
_AI_ORGANIZATION_IN_FLIGHT: dict[int, list[float]] = {}
_AI_ORGANIZATION_IN_FLIGHT_LOCK = threading.Lock()
_CLASS_COMMENTARY_MEMORY_HEALTH_TTL_SECONDS = 60.0
_CLASS_COMMENTARY_MEMORY_HEALTH_LOCK = threading.Lock()
_CLASS_COMMENTARY_MEMORY_HEALTH_CACHE: dict[str, object] = {
    "config_key": "",
    "expires_at": 0.0,
    "payload": None,
}
_CLASS_COMMENTARY_MEMORY_SERVICE_LOCK = threading.Lock()
_CLASS_COMMENTARY_MEMORY_SERVICE_KEY = ""
_CLASS_COMMENTARY_MEMORY_SERVICE: Optional[ClassCommentaryMemoryService] = None
WRONG_QUESTION_CHAT_ARCHIVE_SCHEMA_VERSION = "wrong_question_archive_schema.v1"
WRONG_QUESTION_CHAT_ARCHIVE_PROMPT_VERSION = "wrong_question_chat_prompt.2026-06-03"
WRONG_QUESTION_CHAT_ARCHIVE_TEMPLATE_VERSION = "wrong_question_chat_archive_template.2026-06-03"
WRONG_QUESTION_CHAT_ARCHIVE_RULE_VERSION = "wrong_question_chat_archive_rules.2026-06-03"
# ─── 工具函数 ──────────────────────────────────────────────────────────────────
def get_config():
    return get_runtime_config()


def _class_commentary_memory_config_key(config: dict) -> str:
    keys = (
        "class_commentary_memory_enabled",
        "class_commentary_memory_queue",
        "redis_url",
        "mem0_vector_provider",
        "mem0_qdrant_url",
        "mem0_qdrant_api_key",
        "mem0_collection_name",
        "mem0_embedder_provider",
        "mem0_embedder_model",
        "mem0_embedding_dims",
        "mem0_style_limit",
        "mem0_student_limit",
        "mem0_context_char_limit",
        "provider",
        "class_commentary_provider",
        "class_commentary_model",
        "class_commentary_openai_api_key",
        "class_commentary_openai_base_url",
        "openai_api_key",
        "openai_base_url",
        "openai_model",
        "deepseek_api_key",
        "deepseek_model",
    )
    payload = {key: config.get(key) for key in keys}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _get_class_commentary_memory_service(
    config: Optional[dict] = None,
) -> ClassCommentaryMemoryService:
    global _CLASS_COMMENTARY_MEMORY_SERVICE
    global _CLASS_COMMENTARY_MEMORY_SERVICE_KEY
    runtime = dict(config or get_config())
    config_key = _class_commentary_memory_config_key(runtime)
    with _CLASS_COMMENTARY_MEMORY_SERVICE_LOCK:
        if (
            _CLASS_COMMENTARY_MEMORY_SERVICE is None
            or _CLASS_COMMENTARY_MEMORY_SERVICE_KEY != config_key
        ):
            _CLASS_COMMENTARY_MEMORY_SERVICE = ClassCommentaryMemoryService(
                runtime_config=runtime
            )
            _CLASS_COMMENTARY_MEMORY_SERVICE_KEY = config_key
        return _CLASS_COMMENTARY_MEMORY_SERVICE


def _class_commentary_memory_capabilities(*, force: bool = False) -> dict:
    runtime = get_config()
    if not bool(runtime.get("class_commentary_memory_enabled")):
        return {
            "memory_learning_enabled": False,
            "skill_evolution_enabled": False,
        }
    config_key = _class_commentary_memory_config_key(runtime)
    now = monotonic()
    with _CLASS_COMMENTARY_MEMORY_HEALTH_LOCK:
        cached_payload = _CLASS_COMMENTARY_MEMORY_HEALTH_CACHE.get("payload")
        if (
            not force
            and _CLASS_COMMENTARY_MEMORY_HEALTH_CACHE.get("config_key") == config_key
            and float(_CLASS_COMMENTARY_MEMORY_HEALTH_CACHE.get("expires_at") or 0) > now
            and isinstance(cached_payload, dict)
        ):
            return dict(cached_payload)
    memory_health = _get_class_commentary_memory_service(runtime).healthcheck()
    queue_health = class_commentary_memory_queue_healthcheck(runtime_config=runtime)
    healthy = bool(memory_health.get("healthy")) and bool(
        queue_health.get("healthy")
    )
    payload = {
        "memory_learning_enabled": healthy,
        "skill_evolution_enabled": healthy,
    }
    with _CLASS_COMMENTARY_MEMORY_HEALTH_LOCK:
        _CLASS_COMMENTARY_MEMORY_HEALTH_CACHE.update(
            {
                "config_key": config_key,
                "expires_at": now + _CLASS_COMMENTARY_MEMORY_HEALTH_TTL_SECONDS,
                "payload": dict(payload),
            }
        )
    return payload


def _class_commentary_capabilities(*, force: bool = False) -> dict:
    memory_capabilities = _class_commentary_memory_capabilities(force=force)
    graph_capabilities = _class_commentary_graph_capabilities()
    runtime = get_config()
    batch_isolated_v3_enabled = bool(
        runtime.get("class_commentary_student_memory_v2_enabled")
        and runtime.get("class_commentary_structured_feedback_enabled")
        and memory_capabilities.get("memory_learning_enabled")
        and graph_capabilities.get("graph_enabled")
        and graph_capabilities.get("graph_healthy")
    )
    return {
        **memory_capabilities,
        **graph_capabilities,
        "structured_feedback_enabled": bool(
            runtime.get("class_commentary_structured_feedback_enabled")
        ),
        "student_history_memory_v2_enabled": batch_isolated_v3_enabled,
        "batch_isolated_v3_enabled": batch_isolated_v3_enabled,
        "class_commentary_generation_call_count": 1,
        "student_history_memory_v2_max_credits_per_student": (
            max_configured_charge_for_feature("class_commentary_generate")
        ),
    }


def _class_commentary_graph_capabilities() -> dict:
    runtime = get_config()
    enabled = bool(runtime.get("class_commentary_graph_enabled"))
    if not enabled:
        return {
            "graph_enabled": False,
            "graph_healthy": False,
            "graph_degraded": False,
        }
    adapter = SemanticaGraphAdapter(
        str(runtime.get("class_commentary_graph_store_path") or ""),
        timeout_seconds=int(runtime.get("class_commentary_graph_timeout") or 10),
    )
    graph_health = adapter.health()
    queue_health = class_commentary_memory_queue_healthcheck(
        runtime_config={**runtime, "class_commentary_memory_enabled": True}
    )
    healthy = bool(graph_health.get("healthy")) and bool(queue_health.get("healthy"))
    return {
        "graph_enabled": True,
        "graph_healthy": healthy,
        "graph_degraded": not healthy,
    }


def _dispatch_class_commentary_memory_best_effort() -> dict:
    try:
        return dispatch_class_commentary_memory_work(runtime_config=get_config())
    except Exception as exc:
        logger.warning(
            "class commentary memory dispatch unavailable: %s",
            type(exc).__name__,
        )
        return {
            "enabled": bool(get_config().get("class_commentary_memory_enabled")),
            "extractions": 0,
            "operations": 0,
            "errors": [type(exc).__name__],
        }


def _dispatch_class_commentary_graph_best_effort() -> dict:
    try:
        return dispatch_class_commentary_graph_work(runtime_config=get_config())
    except Exception as exc:
        logger.warning(
            "class commentary graph dispatch unavailable: %s",
            type(exc).__name__,
        )
        return {
            "enabled": bool(get_config().get("class_commentary_graph_enabled")),
            "extractions": 0,
            "sync_operations": 0,
            "errors": [type(exc).__name__],
        }


def _default_ai_provider_name() -> str:
    return normalize_chat_provider(get_config().get("provider", "deepseek"))


def _default_chat_model_name() -> str:
    return chat_model_for_provider(_default_ai_provider_name(), get_config())


def _review_plan_ai_provider_name() -> str:
    return resolve_review_plan_provider(get_config())


def _audio_transcription_provider_name() -> str:
    return str(get_config().get("audio_transcription_provider") or "local")


def _audio_transcription_model_name() -> str:
    if _audio_transcription_provider_name() == "tencent":
        return f"flash-{get_config().get('tencent_asr_engine_type') or '16k_zh'}"
    return "faster-whisper"


def _review_plan_chat_model_name(provider: str = "") -> str:
    provider = provider or _review_plan_ai_provider_name()
    return resolve_review_plan_model(get_config(), provider=provider)


def _class_commentary_ai_provider_name(fallback: str = "") -> str:
    return resolve_class_commentary_provider(get_config(), fallback=fallback)


def _class_commentary_chat_model_name(provider: str = "", fallback_model: str = "") -> str:
    return resolve_class_commentary_model(
        get_config(),
        provider=provider or _class_commentary_ai_provider_name(),
        fallback_model=fallback_model,
    )


def _class_commentary_openai_api_key() -> str:
    cfg = get_config()
    return str(
        cfg.get("class_commentary_openai_api_key")
        or cfg.get("openai_api_key")
        or os.environ.get("OPENAI_API_KEY", "")
    ).strip()


def _class_commentary_openai_base_url() -> str:
    cfg = get_config()
    return str(cfg.get("class_commentary_openai_base_url") or cfg.get("openai_base_url") or "").strip()


def _class_commentary_openai_headers() -> str:
    return str(get_config().get("class_commentary_openai_headers") or "").strip()


def _review_plan_reasoning_effort() -> str:
    provider = _review_plan_ai_provider_name()
    return resolve_review_plan_reasoning_effort(get_config(), provider=provider)


def _review_plan_writer_ai_provider_name() -> str:
    return resolve_review_plan_writer_provider(get_config())


def _review_plan_writer_chat_model_name() -> str:
    provider = _review_plan_writer_ai_provider_name()
    return resolve_review_plan_writer_model(get_config(), provider=provider)


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


def _normalize_wrong_question_generation_metadata(value: object) -> dict:
    payload = value
    if isinstance(value, str):
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            payload = {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(key): payload[key]
        for key in payload
        if isinstance(key, str)
    }


def _merge_wrong_question_generation_metadata(*parts: object) -> dict:
    merged: dict[str, object] = {}
    for part in parts:
        payload = _normalize_wrong_question_generation_metadata(part)
        for key, value in payload.items():
            if value in (None, "", [], {}):
                continue
            merged[key] = value
    return merged


def _build_wrong_question_archive_generation_metadata(
    *,
    archive_payload: dict,
    run: object = None,
    session_metadata: dict | None = None,
) -> dict:
    run_payload = run if isinstance(run, dict) else {}
    session_payload = session_metadata if isinstance(session_metadata, dict) else {}
    try:
        run_metadata = json.loads(str(run_payload.get("metadata_json") or "{}"))
    except json.JSONDecodeError:
        run_metadata = {}
    if not isinstance(run_metadata, dict):
        run_metadata = {}

    base = {
        "schema_version": WRONG_QUESTION_CHAT_ARCHIVE_SCHEMA_VERSION,
        "prompt_version": WRONG_QUESTION_CHAT_ARCHIVE_PROMPT_VERSION,
        "template_version": WRONG_QUESTION_CHAT_ARCHIVE_TEMPLATE_VERSION,
        "rule_version": WRONG_QUESTION_CHAT_ARCHIVE_RULE_VERSION,
        "provider": "local",
        "model_version": "local-guided-loop",
        "entrypoint": "wrong_question_chat_archive",
    }
    session_entrypoint = str(session_payload.get("entrypoint") or "").strip()
    if session_entrypoint in {"wrong_question_chat_rework", "wrong_question_chat_mastery_followup"}:
        base["entrypoint"] = session_entrypoint
    if str(run_payload.get("source") or "").strip():
        base["archive_source"] = str(run_payload.get("source") or "").strip()
    if str(run_metadata.get("entrypoint") or "").strip():
        base["ingestion_entrypoint"] = str(run_metadata.get("entrypoint") or "").strip()

    return _merge_wrong_question_generation_metadata(
        base,
        run_metadata.get("generation_metadata"),
        archive_payload.get("generation_metadata_json"),
        archive_payload.get("generation_metadata"),
    )


def _can_start_wrong_question_mastery_followup(record: object) -> bool:
    if not isinstance(record, dict):
        return False
    if str(record.get("source") or "").strip() != "ai_chat":
        return False
    confirmation_status = _normalize_wrong_question_confirmation_status(record)
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
    if latest_practice_status in {"pending", "generating"}:
        return False
    return True


def _build_wrong_question_chat_mastery_followup_prompt(record: dict) -> str:
    mastery_assessment = record.get("mastery_assessment") if isinstance(record.get("mastery_assessment"), dict) else {}
    mastery_tracking = record.get("mastery_tracking") if isinstance(record.get("mastery_tracking"), dict) else {}
    label = str(mastery_assessment.get("label") or "继续跟进").strip() or "继续跟进"
    practice_sheet_count = int(
        mastery_assessment.get("practice_sheet_count")
        or mastery_tracking.get("practice_sheet_count")
        or 0
    )
    evidence = [
        str(item or "").strip()
        for item in (mastery_assessment.get("evidence") or [])
        if str(item or "").strip()
    ]
    evidence_text = "；".join(evidence[:2])
    if evidence_text:
        evidence_text = f" 当前重点：{evidence_text}"
    return (
        f"这道题最近已经完成了 {practice_sheet_count} 次再练，系统当前判断是“{label}”。"
        f"{evidence_text}。"
        "我们继续沿同一条错题追问。先说说：做完最近一次再练后，你现在最有把握的是哪一步，最不确定的又是哪一步？"
    )


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


def _profile_avatar_upload_relative_path(user_id: int, original_filename: str) -> str:
    safe_filename = secure_filename(original_filename or "")
    suffix = Path(safe_filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        suffix = ".png"
    return f"profile-avatars/user-{int(user_id)}-{int(time() * 1000)}{suffix}"


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


def _build_review_plan_regenerate_request_id(*, user_id: int, lesson_id: int, request_key: str) -> str:
    return _build_ai_charge_request_id(
        user_id=user_id,
        feature_key="lesson_plan_generate",
        source_record_type="lesson_regenerate",
        source_record_id=lesson_id,
        request_key=request_key,
    )


def _find_existing_review_plan_lesson_for_request(*, organization_id: int, request_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT l.id
            FROM review_plan_versions v
            JOIN lessons l ON l.id=v.lesson_id
            WHERE v.request_id=? AND l.organization_id=?
            ORDER BY v.id DESC
            LIMIT 1
            """,
            (str(request_id or ""), int(organization_id)),
        ).fetchone()
    if row:
        return get_lesson(int(row["id"]))

    usage = get_ai_usage_by_request_id(
        organization_id=organization_id,
        request_id=request_id,
    )
    if not usage or usage.get("feature_key") != "lesson_plan_generate":
        return None
    if usage.get("source_record_type") != "lesson":
        return None
    try:
        lesson_id = int(str(usage.get("source_record_id") or "").strip())
    except ValueError:
        return None
    lesson = get_lesson(lesson_id)
    if not lesson or int(lesson.get("organization_id") or 0) != organization_id:
        return None
    return lesson


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
        for org_id, started_slots in list(_AI_ORGANIZATION_IN_FLIGHT.items()):
            active_slots = [
                started_at
                for started_at in started_slots
                if (now - started_at) <= _AI_REQUEST_IN_FLIGHT_TTL_SECONDS
            ]
            if active_slots:
                _AI_ORGANIZATION_IN_FLIGHT[org_id] = active_slots
            else:
                _AI_ORGANIZATION_IN_FLIGHT.pop(org_id, None)
        active_slots = list(_AI_ORGANIZATION_IN_FLIGHT.get(organization_id) or [])
        if len(active_slots) >= _AI_ORGANIZATION_CONCURRENCY_LIMIT:
            raise DuplicateAiRequestError(f"当前机构已有 {_AI_ORGANIZATION_CONCURRENCY_LIMIT} 个 AI 请求正在处理中，请稍后再试")
        active_slots.append(now)
        _AI_ORGANIZATION_IN_FLIGHT[organization_id] = active_slots


def _release_ai_organization_execution(organization_id: int) -> None:
    with _AI_ORGANIZATION_IN_FLIGHT_LOCK:
        active_slots = _AI_ORGANIZATION_IN_FLIGHT.get(organization_id)
        if not active_slots:
            return
        active_slots.pop()
        if active_slots:
            _AI_ORGANIZATION_IN_FLIGHT[organization_id] = active_slots
        else:
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
    organization_execution_claimed = False
    try:
        _claim_ai_organization_execution(organization_id)
        organization_execution_claimed = True
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
        if organization_execution_claimed:
            _release_ai_organization_execution(organization_id)
        if claim_request_identity:
            _release_ai_request_identity(request_id)


def _resume_class_commentary_batch_generation(
    *,
    generation: dict,
    user: dict,
) -> dict:
    frozen = parse_frozen_batch_generation_inputs(generation)
    def generator(**kwargs):
        return _call_ai_helper_with_usage(
            generate_class_commentary_feedback,
            class_record=frozen["class_record"],
            students=frozen["students"],
            transcript_text=frozen["transcript_text"],
            skill=frozen["skill"],
            provider=str(kwargs["provider"]),
            model=str(kwargs["model"]),
            chat_request=kwargs["chat_request"],
            openai_api_key=_class_commentary_openai_api_key(),
            openai_base_url=_class_commentary_openai_base_url(),
            openai_headers=_class_commentary_openai_headers(),
            request_id=str(kwargs["request_id"]),
            request_timeout=float(
                kwargs["runtime_config"].get(
                    "class_commentary_batch_generation_timeout"
                )
                or 300
            ),
            max_retries=0,
        )
    result = process_class_commentary_batch_generation(
        int(generation["id"]),
        runtime_config=get_config(),
        generator=generator,
        charge_finalizer=finalize_ai_charge,
        claim_owner=f"class-commentary-http:{int(user['id'])}",
        memory_service=_get_class_commentary_memory_service(),
    )
    refreshed = get_class_commentary_generation(int(generation["id"]))
    if refreshed is None:
        raise ValueError("generation not found")
    error_code = str(result.get("error_code") or "")
    if error_code == "structured_feedback_invalid" or error_code.startswith(
        "student_feedback_"
    ):
        raise ClassCommentaryStructuredFeedbackValidationError(error_code)
    return refreshed

def _get_or_create_compat_review_plan_version_for_job(
    *,
    lesson: dict,
    user: dict,
    chat_provider: str,
    chat_model: str,
    request_key: str | None = None,
    request_id: str | None = None,
    audio_path: str = "",
    audio_request_key: str | None = None,
    same_lesson_materials: list[str] | None = None,
    generation_options: object | None = None,
) -> dict | None:
    active_version = lesson.get("active_version")
    if isinstance(active_version, dict) and active_version.get("id"):
        return get_review_plan_version_for_lesson(int(lesson["id"]), int(active_version["id"]))
    record_status = str(lesson.get("record_status") or "").strip()
    if record_status not in {"pending", "transcribing", "generating"}:
        return None
    return create_review_plan_version(
        lesson_id=int(lesson["id"]),
        status=record_status,
        created_by_user_id=int(user.get("id") or 0),
        audio_path=audio_path or str(lesson.get("review_audio_path") or ""),
        audio_request_key=audio_request_key or str(lesson.get("review_audio_request_key") or ""),
        request_key=request_key or str(lesson.get("review_request_key") or ""),
        request_id=request_id or str(lesson.get("review_request_id") or ""),
        chat_provider=chat_provider or str(lesson.get("review_chat_provider") or ""),
        chat_model=chat_model or str(lesson.get("review_chat_model") or ""),
        same_lesson_materials=same_lesson_materials or lesson.get("review_same_lesson_materials") or [],
        generation_options=generation_options or lesson.get("review_generation_options"),
    )


def _review_plan_quality_failure_message(version_id: int) -> str:
    try:
        latest_run = get_latest_completed_review_plan_quality_run_for_version(version_id)
    except Exception:
        logger.exception("Failed to read review plan quality run for version %s", version_id)
        return ""
    if not latest_run:
        return ""

    quality = latest_run.get("quality_review")
    if not isinstance(quality, dict):
        return ""
    must_revise = quality.get("must_revise") is True
    failed = quality.get("passed") is False
    if not (must_revise or failed):
        return ""

    first_issue = ""
    issues = quality.get("issues")
    if isinstance(issues, list):
        severity_rank = {"high": 0, "medium": 1, "low": 2}
        ordered_issues = sorted(
            [issue for issue in issues if isinstance(issue, dict)],
            key=lambda item: severity_rank.get(str(item.get("severity") or "").strip().lower(), 3),
        )
        for issue in ordered_issues:
            if not isinstance(issue, dict):
                continue
            category = str(issue.get("category") or "").strip().lower()
            description = str(issue.get("description") or "").strip()
            readable = _review_plan_readable_quality_issue(category, description)
            if readable:
                first_issue = f"{readable.rstrip('。.')}。"
                break
    reason_text = f"原因：{first_issue}" if first_issue else ""
    return (
        "这次生成的复习计划不够完整，系统已先拦截，避免生成半成品文档。"
        f"{reason_text}"
        "请点击“重新生成”；如果再次失败，请补充课程主题、重点题型或本次要求。"
    )


def _review_plan_readable_quality_issue(category: str, description: str) -> str:
    text = description.strip()
    lowered = text.lower()
    if category == "schema" or "schema" in lowered or "review plan must include review days" in lowered:
        return "没有生成出完整的每日复习安排"
    if "复习日没有严格匹配" in text:
        return "生成结果没有按本次选择的复习日期安排"
    if "lesson_info.topic" in text or "空壳标题" in text:
        return "生成结果缺少明确的课程主题"
    if "全课覆盖清单" in text:
        return "生成结果缺少清晰的复习范围"
    if "模糊指代" in text:
        return "部分题目没有写完整题干"
    if "lesson_info" in lowered and "grade" in lowered:
        return "生成结果对课程信息的来源判断不清"
    if "teacher_emphasis" in lowered or "quotes" in lowered or "课堂原话" in text:
        return "生成结果包含没有课堂证据的老师原话"
    if "唯一可打印题目不足" in text:
        return text.replace("唯一可打印题目", "可直接给学生练习的题目").replace("PDF", "文档")
    if not text:
        return ""
    for technical in (
        "schema",
        "Schema",
        "Value error,",
        "lesson_info.topic",
        "`",
        "PDF",
    ):
        text = text.replace(technical, "文档" if technical == "PDF" else "")
    return " ".join(text.split())


def _run_review_plan_generation_job(
    *,
    lesson_id: int,
    version_id: int = 0,
    user: dict,
    chat_provider: str,
    chat_model: str,
    request_key: str | None = None,
    request_id: str | None = None,
    audio_path: str = "",
    audio_request_key: str | None = None,
    same_lesson_materials: list[str] | None = None,
    generation_options: object | None = None,
) -> None:
    try:
        lesson = get_lesson(lesson_id)
        if not lesson:
            logger.warning("Review plan generation skipped: lesson %s not found", lesson_id)
            return
        if version_id:
            version = get_review_plan_version_for_lesson(lesson_id, version_id)
        else:
            version = _get_or_create_compat_review_plan_version_for_job(
                lesson=lesson,
                user=user,
                chat_provider=chat_provider,
                chat_model=chat_model,
                request_key=request_key,
                request_id=request_id,
                audio_path=audio_path,
                audio_request_key=audio_request_key,
                same_lesson_materials=same_lesson_materials,
                generation_options=generation_options,
            )
            version_id = int((version or {}).get("id") or 0)
        if not version:
            logger.warning(
                "Review plan generation skipped: version %s for lesson %s not found or inactive",
                version_id,
                lesson_id,
            )
            return
        generation_options = normalize_generation_options(
            generation_options or version.get("generation_options"),
            source=str((version.get("generation_options") or {}).get("source") or "create"),
        )

        record_status = str(version.get("status") or "")
        if record_status == "transcribing":
            audio_file_path = Path(audio_path or str(version.get("audio_path") or "")) if (audio_path or version.get("audio_path")) else None
            if not audio_file_path:
                fail_review_plan_version(version_id, "音频转录失败，请重新上传")
                return
            try:
                from ai_processor import polish_review_plan_transcript, transcribe_audio
                transcription = _run_ai_feature_with_charge(
                    user=user,
                    feature_key="audio_transcription",
                    source_record_type="lesson_upload",
                    source_record_id=f"upload:{lesson_id}",
                    producer=lambda: _call_ai_helper_with_usage(transcribe_audio, str(audio_file_path)),
                    provider=_audio_transcription_provider_name(),
                    model=_audio_transcription_model_name(),
                    request_key=audio_request_key or str(version.get("audio_request_key") or "") or request_key,
                )
                raw_transcription = str(transcription or "").strip()
                if not raw_transcription:
                    fail_review_plan_version(version_id, "音频转录失败，请稍后重试")
                    return
                raw_source_text_hash = review_plan_transcript_source_text_hash(raw_transcription)
                source_brief_snapshot = version.get("source_brief") or {}
                update_review_plan_version_source_artifact(
                    version_id,
                    source_text=raw_transcription,
                    cleaned_source_text=raw_transcription,
                    source_text_hash=raw_source_text_hash,
                    source_brief=source_brief_snapshot,
                    source_type="transcript",
                )
                transcript_for_generation = raw_transcription
                try:
                    polish_provider = _review_plan_ai_provider_name()
                    polish_model = _review_plan_chat_model_name(polish_provider)
                    polished_text = _run_ai_feature_with_charge(
                        user=user,
                        feature_key="review_plan_transcript_polish",
                        source_record_type="review_plan_transcript_polish",
                        source_record_id=version_id or lesson_id,
                        producer=lambda: _call_ai_helper_with_usage(
                            polish_review_plan_transcript,
                            raw_transcript_text=raw_transcription,
                            subject=str(lesson.get("subject") or ""),
                            grade=str(lesson.get("grade") or ""),
                            topic=str(lesson.get("topic") or ""),
                            teacher_requirements=str((generation_options or {}).get("user_requirements") or ""),
                            provider=polish_provider,
                            model=polish_model,
                        ),
                        provider=polish_provider,
                        model=polish_model,
                        request_key=request_key,
                        claim_request_identity=False,
                    )
                    polished_text = str(polished_text or "").strip()
                    if not polished_text:
                        raise ValueError("review plan transcript polish returned empty text")
                    transcript_for_generation = polished_text
                except Exception as polish_exc:
                    logger.warning(
                        "Review plan transcript polish failed for lesson %s version %s: %s",
                        lesson_id,
                        version_id,
                        polish_exc,
                    )
                merged_summary = _merge_review_plan_materials(
                    transcript_for_generation,
                    same_lesson_materials or version.get("same_lesson_materials") or [],
                )
                update_review_plan_version_source_artifact(
                    version_id,
                    source_text=raw_transcription,
                    cleaned_source_text=merged_summary,
                    source_text_hash=raw_source_text_hash,
                    source_brief=source_brief_snapshot,
                    source_type="transcript",
                )
                mark_review_plan_version_transcription_succeeded(version_id, summary=merged_summary)
                lesson = get_lesson(lesson_id)
                version = get_review_plan_version_for_lesson(lesson_id, version_id)
                if not lesson or not version:
                    logger.warning("Review plan generation skipped after transcription: lesson %s not found", lesson_id)
                    return
                record_status = str(version.get("status") or "")
            except DuplicateAiRequestError as exc:
                logger.exception("Review plan audio transcription request rejected for lesson %s", lesson_id)
                try:
                    fail_review_plan_version(version_id, str(exc))
                except LookupError:
                    logger.exception("Failed to mark lesson %s as failed after duplicate transcription request", lesson_id)
                return
            except CreditBalanceError as exc:
                logger.exception("Review plan audio transcription credit preflight failed for lesson %s", lesson_id)
                try:
                    fail_review_plan_version(version_id, str(exc))
                except LookupError:
                    logger.exception("Failed to mark lesson %s as failed after transcription credit error", lesson_id)
                return
            except Exception:
                logger.exception("Review plan audio transcription failed for lesson %s", lesson_id)
                try:
                    fail_review_plan_version(version_id, "音频转录失败，请稍后重试")
                except LookupError:
                    logger.exception("Failed to mark lesson %s as failed after transcription error", lesson_id)
                return
            finally:
                if audio_file_path:
                    audio_file_path.unlink(missing_ok=True)

        if record_status not in {"pending", "generating"}:
            logger.info(
                "Review plan generation skipped for lesson %s with status %s",
                lesson_id,
                version.get("status"),
            )
            return

        lesson_date = str(lesson.get("date") or "")
        subject = str(lesson.get("subject") or "")
        grade = str(lesson.get("grade") or "")
        topic = str(lesson.get("topic") or "")
        weak_points = str(lesson.get("weak_points") or "")
        raw_text = str(lesson.get("summary") or "")
        version_cleaned_source_text = str((version or {}).get("cleaned_source_text") or "").strip()
        version_source_text = str((version or {}).get("source_text") or "").strip()
        source_text_for_generation = version_cleaned_source_text or version_source_text or raw_text
        source_snapshot_text = version_source_text or source_text_for_generation
        expected_source_hash = str((version or {}).get("source_text_hash") or "").strip() or source_text_hash(source_snapshot_text)
        expected_cleaned_hash = source_text_hash(version_cleaned_source_text or clean_source_text(source_text_for_generation))

        if version_id and (
            not str((version or {}).get("source_text_hash") or "").strip()
            or source_pack_needs_rebuild(
                (version or {}).get("source_pack"),
                raw_source_hash=expected_source_hash,
                cleaned_source_hash=expected_cleaned_hash,
            )
        ):
            source_brief = build_deterministic_source_brief(
                raw_text=source_text_for_generation,
                subject=subject,
                topic=topic,
                weak_points=weak_points,
                user_requirements=str((generation_options or {}).get("user_requirements") or ""),
            )
            update_review_plan_version_source_artifact(
                version_id,
                source_text=source_snapshot_text,
                cleaned_source_text=source_brief.cleaned_text,
                source_text_hash=source_brief.source_text_hash,
                source_brief=source_brief.model_dump(),
                source_type=str(((version or {}).get("source_pack") or {}).get("source_type") or "text"),
            )
            version = get_review_plan_version_for_lesson(lesson_id, version_id)

        from review_plan_workflow.service import generate_single_lesson_review_plan
        try:
            plan = _run_ai_feature_with_charge(
                user=user,
                feature_key="lesson_plan_generate",
                source_record_type="lesson",
                source_record_id=lesson_id,
                producer=lambda: _call_ai_helper_with_usage(
                    generate_single_lesson_review_plan,
                    summary_text=source_text_for_generation,
                    subject=subject,
                    grade=grade,
                    topic=topic,
                    weak_points=weak_points,
                    lesson_date=lesson_date,
                    generation_options=generation_options,
                    source_pack=(version or {}).get("source_pack"),
                    provider=chat_provider,
                    model=chat_model,
                    lesson_id=lesson_id,
                    version_id=version_id,
                    organization_id=int(user["organization_id"]),
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
                fail_review_plan_version(version_id, str(exc))
            except LookupError:
                logger.exception("Failed to mark lesson %s as failed after duplicate request", lesson_id)
            return
        except CreditBalanceError as exc:
            logger.exception("Review plan credit preflight failed for lesson %s", lesson_id)
            try:
                fail_review_plan_version(version_id, str(exc))
            except LookupError:
                logger.exception("Failed to mark lesson %s as failed after credit error", lesson_id)
            return
        except Exception:
            logger.exception("Review plan AI generation failed for lesson %s", lesson_id)
            try:
                fail_review_plan_version(version_id, "AI 生成失败，请稍后重试")
            except LookupError:
                logger.exception("Failed to mark lesson %s as failed after AI error", lesson_id)
            return
        if isinstance(plan, tuple) and len(plan) == 2 and isinstance(plan[1], dict):
            plan = plan[0]

        quality_error = _review_plan_quality_failure_message(version_id)
        if quality_error:
            logger.warning("Review plan quality gate blocked lesson %s: %s", lesson_id, quality_error)
            try:
                fail_review_plan_version(version_id, quality_error)
            except LookupError:
                logger.exception("Failed to mark lesson %s as failed after quality gate error", lesson_id)
            return

        try:
            pdf_path = _render_review_plan_version_pdf(lesson_id=lesson_id, version=version, plan=plan)
        except Exception:
            logger.exception("Review plan PDF generation failed for lesson %s", lesson_id)
            try:
                fail_review_plan_version(version_id, "PDF 生成失败，请稍后重试")
            except LookupError:
                logger.exception("Failed to mark lesson %s as failed after PDF error", lesson_id)
            return

        try:
            complete_review_plan_version(
                version_id,
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


def _render_review_plan_version_pdf(*, lesson_id: int, version: dict, plan: dict) -> str:
    from review_plan_templates.single_lesson_pdf import build_single_lesson_pdf_filename, generate_single_lesson_pdf

    version_suffix = version.get("version_no") or version.get("id") or "latest"
    pdf_name = build_single_lesson_pdf_filename(plan, suffix=f"{lesson_id}-v{version_suffix}")
    pdf_path = str(PDF_DIR / pdf_name)
    generate_single_lesson_pdf(plan, pdf_path)
    return pdf_path


def _run_class_commentary_transcription(task_id: int, audio_path: str, user: dict, request_key: str) -> None:
    try:
        transcription = _run_ai_feature_with_charge(
            user=user,
            feature_key="class_commentary_transcribe",
            source_record_type="class_commentary_task",
            source_record_id=task_id,
            provider=_audio_transcription_provider_name(),
            model=_audio_transcription_model_name(),
            producer=lambda: _call_ai_helper_with_usage(transcribe_audio, audio_path),
            request_key=request_key,
            claim_request_identity=False,
        )
        raw_text = str(transcription or "").strip()
        if not raw_text:
            raise ValueError("transcription returned empty text")

        task = get_class_commentary_task(task_id)
        if not task:
            raise LookupError("class commentary task not found")
        cls = get_class(int(task["class_id"]))
        if not cls:
            raise LookupError("class not found")
        class_students = list_students_for_class(int(task["class_id"]))
        sanitized_roster = sanitize_class_commentary_roster(class_students)
        roster_snapshot = payload_to_json({"students": sanitized_roster})
        mark_class_commentary_raw_transcription_succeeded(task_id, raw_text, roster_snapshot)

        try:
            chat_provider = _class_commentary_ai_provider_name(fallback=_default_ai_provider_name())
            chat_model = _class_commentary_chat_model_name(chat_provider, fallback_model=_default_chat_model_name())
            polished_text = _run_ai_feature_with_charge(
                user=user,
                feature_key="class_commentary_transcript_polish",
                source_record_type="class_commentary_transcript_polish",
                source_record_id=task_id,
                provider=chat_provider,
                model=chat_model,
                producer=lambda: _call_ai_helper_with_usage(
                    polish_class_commentary_transcript,
                    class_record=cls,
                    students=sanitized_roster,
                    raw_transcript_text=raw_text,
                    provider=chat_provider,
                    model=chat_model,
                    openai_api_key=_class_commentary_openai_api_key(),
                    openai_base_url=_class_commentary_openai_base_url(),
                    openai_headers=_class_commentary_openai_headers(),
                ),
                request_key=request_key,
                claim_request_identity=False,
            )
            polished_text = str(polished_text or "").strip()
            if not polished_text:
                raise ValueError("transcript polish returned empty text")
            mark_class_commentary_transcript_polish_succeeded(task_id, polished_text)
        except Exception as polish_exc:
            mark_class_commentary_transcript_polish_failed(task_id, raw_text, str(polish_exc))
    except Exception as exc:
        mark_class_commentary_task_failed(task_id, "transcription", str(exc))


def _start_class_commentary_transcription_worker(task_id: int, audio_path: str, user: dict, request_key: str) -> None:
    threading.Thread(
        target=_run_class_commentary_transcription,
        args=(task_id, audio_path, user, request_key),
        daemon=True,
    ).start()


def _recover_interrupted_review_plan_jobs() -> int:
    recovered_count = 0
    for lesson in list_lessons():
        user_id = int(lesson.get("created_by_user_id") or 0)
        user = get_user_by_id(user_id) if user_id else None
        if not user:
            logger.warning("Review plan recovery skipped for lesson %s: missing user", lesson.get("id"))
            continue
        for version in list_review_plan_versions(int(lesson["id"])):
            record_status = str(version.get("status") or "").strip()
            if record_status not in {"pending", "transcribing", "generating"}:
                continue
            audio_path = str(version.get("audio_path") or "").strip()
            if record_status == "transcribing" and (not audio_path or not Path(audio_path).exists()):
                fail_review_plan_version(int(version["id"]), "音频转录中断，请重新上传")
                continue
            request_id = str(version.get("request_id") or "").strip()
            if request_id:
                try:
                    _claim_ai_request_identity(
                        organization_id=int(user["organization_id"]),
                        request_id=request_id,
                    )
                except DuplicateAiRequestError:
                    logger.warning("Review plan recovery skipped for duplicate request %s", request_id)
                    fail_review_plan_version(int(version["id"]), "生成任务已中断，请重新生成")
                    continue
            _start_review_plan_generation_thread(
                lesson_id=int(lesson["id"]),
                version_id=int(version["id"]),
                user={
                    "id": int(user["id"]),
                    "organization_id": int(user["organization_id"]),
                },
                chat_provider=str(version.get("chat_provider") or "") or _default_ai_provider_name(),
                chat_model=str(version.get("chat_model") or "") or _default_chat_model_name(),
                request_key=str(version.get("request_key") or ""),
                request_id=request_id or None,
                audio_path=audio_path,
                audio_request_key=str(version.get("audio_request_key") or ""),
                same_lesson_materials=version.get("same_lesson_materials") or [],
                generation_options=version.get("generation_options"),
            )
            recovered_count += 1
    return recovered_count


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
                        "structured_content": (
                            generated_item.get("structured_content")
                            if isinstance(generated_item.get("structured_content"), dict)
                            else {}
                        ),
                        "generation_metadata": _merge_wrong_question_generation_metadata(
                            generated.get("generation_metadata"),
                            generated_item.get("generation_metadata"),
                        ),
                        "answer": str(generated_item.get("answer") or item.get("answer") or "").strip(),
                        "key_steps": (
                            generated_item.get("key_steps")
                            if isinstance(generated_item.get("key_steps"), list)
                            else item.get("key_steps", [])
                        ),
                        "pitfall_reminder": str(
                            generated_item.get("pitfall_reminder") or item.get("pitfall_reminder") or ""
                        ).strip(),
                    }
                )

            title = str((generated or {}).get("title") or "").strip() or f"{sheet.get('student_name_snapshot') or '学生'} 错题练习"
            output_path = str(_wrong_question_practice_sheet_pdf_path(sheet_id))
            from wrong_question_upload_worker import ensure_erased_wrong_question_images_for_practice_items

            pdf_items = ensure_erased_wrong_question_images_for_practice_items(merged_items)

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
                        items=pdf_items,
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
                generation_metadata=generated.get("generation_metadata"),
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


def _practice_pack_item_from_real_record(record: dict, index: int) -> dict:
    record_id = str(record.get("id") or "").strip()
    return {
        "practice_item_id": f"real-{record_id or index}",
        "item_type": "real",
        "wrong_question_record_id": record_id,
        "question_order": int(index),
        "source": str(record.get("source") or "wechat_mp").strip() or "wechat_mp",
        "is_geometry": bool(record.get("is_geometry")),
        "question_text_snapshot": str(record.get("question_text") or "").strip(),
        "image_url_snapshot": str(record.get("image_url") or "").strip(),
        "diagram_type_snapshot": str(record.get("diagram_type") or "").strip(),
        "diagram_spec_json_snapshot": str(record.get("diagram_spec_json") or "").strip(),
        "child_reason_text_snapshot": str(record.get("child_raw_reason_text") or "").strip(),
        "child_reason_transcript_snapshot": str(record.get("child_reason_transcript") or "").strip(),
        "primary_error_type_snapshot": str(record.get("primary_error_type") or "").strip(),
        "cause_note_snapshot": str(record.get("secondary_error_summary") or "").strip(),
        "topic_category_snapshot": str(record.get("topic_category") or "").strip(),
        "question_structured_snapshot_json": record.get("question_structured_json", record.get("question_structured")),
        "knowledge_tags_snapshot_json": record.get("knowledge_tags_json", record.get("knowledge_tags")),
        "reflection_summary_snapshot_json": record.get("reflection_summary_json", record.get("reflection_summary")),
    }


def _practice_pack_item_from_variant(variant: dict, index: int) -> dict:
    variant_id = str(variant.get("variant_id") or f"variant-{index}").strip()
    practice_item_id = f"variant-{variant_id or index}"
    key_steps = variant.get("key_steps") if isinstance(variant.get("key_steps"), list) else []
    return {
        "practice_item_id": practice_item_id,
        "item_type": "variant",
        "wrong_question_record_id": practice_item_id,
        "question_order": int(index),
        "source": "ai_variant",
        "is_geometry": bool(variant.get("is_geometry")),
        "question_text_snapshot": str(variant.get("question_text") or "").strip(),
        "image_url_snapshot": "",
        "child_reason_text_snapshot": "",
        "primary_error_type_snapshot": str(variant.get("training_goal") or "").strip(),
        "cause_note_snapshot": str(variant.get("pitfall_reminder") or "").strip(),
        "question_structured_snapshot_json": "",
        "knowledge_tags_snapshot_json": [],
        "reflection_summary_snapshot_json": {},
        "variant_id": variant_id,
        "source_record_id": str(variant.get("source_record_id") or "").strip(),
        "training_goal": str(variant.get("training_goal") or "").strip(),
        "answer": str(variant.get("answer") or "").strip(),
        "key_steps": [str(step or "").strip() for step in key_steps if str(step or "").strip()],
        "pitfall_reminder": str(variant.get("pitfall_reminder") or "").strip(),
    }


def _build_wrong_question_practice_pack_zip(job: dict) -> dict:
    job_id = int(job.get("id") or 0)
    zip_path = _wrong_question_practice_pack_zip_path(job_id)
    temp_zip_path = zip_path.with_suffix(f"{zip_path.suffix}.tmp")
    notes: list[str] = []
    written_count = 0
    used_names: set[str] = set()

    try:
        zip_path.unlink(missing_ok=True)
        temp_zip_path.unlink(missing_ok=True)
        with zipfile.ZipFile(temp_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index, student in enumerate(job.get("students") or [], start=1):
                student_name = str(student.get("student_name_snapshot") or "学生").strip() or "学生"
                status = str(student.get("status") or "").strip()
                pdf_path_value = str(student.get("pdf_path") or "").strip()
                pdf_path = Path(pdf_path_value) if pdf_path_value else None
                if status == "ready" and pdf_path is not None and pdf_path.is_file():
                    safe_name = _safe_pdf_download_filename_part(student_name, f"student-{student.get('student_id') or index}")
                    archive_name = f"{index:02d}-{safe_name}.pdf"
                    if archive_name in used_names:
                        archive_name = f"{index:02d}-{safe_name}-{student.get('student_id') or index}.pdf"
                    used_names.add(archive_name)
                    archive.write(pdf_path, archive_name)
                    written_count += 1
                    warning = str(student.get("generation_error") or "").strip()
                    if warning:
                        notes.append(f"{student_name}：{warning}")
                    continue

                error_message = str(student.get("generation_error") or "").strip()
                if status == "ready":
                    error_message = "PDF 文件缺失"
                else:
                    error_message = error_message or "未生成"
                notes.append(f"{student_name}：{error_message}")

            if written_count <= 0:
                raise RuntimeError("没有可打包的学生练习 PDF")
            if notes:
                archive.writestr("打包说明.txt", "\n".join(notes) + "\n")
        temp_zip_path.replace(zip_path)
    except Exception:
        temp_zip_path.unlink(missing_ok=True)
        zip_path.unlink(missing_ok=True)
        raise

    return {"zip_path": str(zip_path), "has_partial": bool(notes)}


def _run_wrong_question_practice_pack_job(*, job_id: int, user: dict) -> None:
    try:
        job = get_wrong_question_practice_pack_job(job_id)
        if not job or job.get("status") not in {"pending", "failed"}:
            logger.info("Wrong question practice pack generation skipped for job %s", job_id)
            return

        mark_wrong_question_practice_pack_job_status(job_id, status="running", zip_path="", generation_error="")
        class_row = get_class(int(job.get("class_id") or 0)) or {}
        class_name = str(class_row.get("name") or "").strip()
        teacher_name = str(user.get("display_name") or user.get("username") or "").strip()
        requested_count = int(job.get("requested_question_count") or 0)
        any_partial = False

        for student in list_students_for_class(int(job.get("class_id") or 0)):
            student_id = int(student.get("id") or 0)
            student_name = str(student.get("name") or "").strip() or "学生"
            upsert_wrong_question_practice_pack_job_student(
                job_id=job_id,
                student_id=student_id,
                student_name_snapshot=student_name,
                status="running",
                requested_question_count=requested_count,
            )
            try:
                real_candidates = list_targeted_wrong_question_practice_candidates(
                    organization_id=int(job.get("organization_id") or 0),
                    class_id=int(job.get("class_id") or 0),
                    student_id=student_id,
                    mode=str(job.get("mode") or ""),
                    target=str(job.get("target") or ""),
                    limit=requested_count,
                )
                if not real_candidates:
                    any_partial = True
                    upsert_wrong_question_practice_pack_job_student(
                        job_id=job_id,
                        student_id=student_id,
                        student_name_snapshot=student_name,
                        status="skipped",
                        requested_question_count=requested_count,
                        generation_error="没有匹配方向的历史错题",
                    )
                    continue

                missing_count = max(0, requested_count - len(real_candidates))
                variants: list[dict] = []
                variant_generation_warning = ""
                if missing_count > 0:
                    try:
                        generated_variants = ai_processor.generate_wrong_question_practice_pack_variants(
                            student_name=student_name,
                            class_name=class_name,
                            mode=str(job.get("mode") or ""),
                            target=str(job.get("target") or ""),
                            requested_count=missing_count,
                            source_records=real_candidates,
                        )
                        for variant in generated_variants or []:
                            review_text = ai_processor.review_wrong_question_practice_pack_variant(
                                mode=str(job.get("mode") or ""),
                                target=str(job.get("target") or ""),
                                variant=variant,
                            )
                            if ai_processor._wrong_question_practice_pack_variant_review_passed(review_text):
                                variants.append(variant)
                            if len(variants) >= missing_count:
                                break
                    except Exception as exc:
                        any_partial = True
                        variant_generation_warning = "AI 补题失败，已按可用题生成"
                        logger.warning(
                            "Wrong question practice pack variant generation failed for job %s student %s: %s",
                            job_id,
                            student_id,
                            exc,
                        )

                practice_items = [
                    _practice_pack_item_from_real_record(record, index)
                    for index, record in enumerate(real_candidates, start=1)
                ]
                variant_items = [
                    _practice_pack_item_from_variant(variant, len(practice_items) + index)
                    for index, variant in enumerate(variants, start=1)
                ]
                practice_items.extend(variant_items)
                generated = ai_processor.generate_wrong_question_practice_sheet_material(
                    student_name=student_name,
                    class_name=class_name,
                    teacher_name=teacher_name,
                    items=practice_items,
                )
                generated_items = generated.get("items") if isinstance(generated, dict) else []
                generated_by_id = {
                    str(item.get("wrong_question_record_id") or "").strip(): item
                    for item in generated_items
                    if isinstance(item, dict)
                }
                merged_items = []
                for item in practice_items:
                    generated_item = generated_by_id.get(str(item.get("wrong_question_record_id") or "").strip(), {})
                    merged_items.append(
                        {
                            **item,
                            "ai_hint": str(generated_item.get("ai_hint") or "").strip(),
                            "reason_blank_prompt": str(generated_item.get("reason_blank_prompt") or "").strip(),
                            "improvement_summary_prompt": str(generated_item.get("improvement_summary_prompt") or "").strip(),
                            "structured_content": (
                                generated_item.get("structured_content")
                                if isinstance(generated_item.get("structured_content"), dict)
                                else {}
                            ),
                            "answer": str(generated_item.get("answer") or item.get("answer") or "").strip(),
                            "key_steps": (
                                generated_item.get("key_steps")
                                if isinstance(generated_item.get("key_steps"), list)
                                else item.get("key_steps", [])
                            ),
                            "pitfall_reminder": str(
                                generated_item.get("pitfall_reminder") or item.get("pitfall_reminder") or ""
                            ).strip(),
                        }
                    )
                schedule = build_wrong_question_practice_pack_schedule(
                    merged_items,
                    start_date=date.today().isoformat(),
                )
                warning = ""
                if len(merged_items) < requested_count:
                    any_partial = True
                    warning = variant_generation_warning or "匹配题量不足，已按可用题生成"
                title = str((generated or {}).get("title") or "").strip() or f"{student_name} 一周错题练习"
                pdf_path = pdf_engine.generate_wrong_question_practice_sheet_pdf(
                    student_name=student_name,
                    class_name=class_name,
                    teacher_name=teacher_name,
                    title=title,
                    items=merged_items,
                    output_path=str(_wrong_question_practice_pack_student_pdf_path(job_id, student_id)),
                    schedule=schedule,
                    answer_items=merged_items,
                    pack_meta={
                        "mode": str(job.get("mode") or ""),
                        "target": str(job.get("target") or ""),
                        "volume": str(job.get("volume") or ""),
                        "requested_question_count": requested_count,
                    },
                )
                upsert_wrong_question_practice_pack_job_student(
                    job_id=job_id,
                    student_id=student_id,
                    student_name_snapshot=student_name,
                    status="ready",
                    requested_question_count=requested_count,
                    real_question_count=len(practice_items) - len(variant_items),
                    variant_question_count=len(variant_items),
                    pdf_path=str(pdf_path or "").strip(),
                    generation_error=warning,
                )
            except Exception as exc:
                any_partial = True
                logger.exception("Wrong question practice pack student generation failed for job %s student %s", job_id, student_id)
                upsert_wrong_question_practice_pack_job_student(
                    job_id=job_id,
                    student_id=student_id,
                    student_name_snapshot=student_name,
                    status="failed",
                    requested_question_count=requested_count,
                    generation_error=str(exc) or "生成失败",
                )

        refreshed_job = get_wrong_question_practice_pack_job(job_id) or {}
        try:
            zip_result = _build_wrong_question_practice_pack_zip(refreshed_job)
        except Exception as exc:
            logger.exception("Wrong question practice pack zip generation failed for job %s", job_id)
            mark_wrong_question_practice_pack_job_status(
                job_id,
                status="failed",
                zip_path="",
                generation_error=str(exc) or "打包失败",
            )
            return

        refreshed_students = refreshed_job.get("students") or []
        final_status = "partial_failed" if any_partial or bool(zip_result.get("has_partial")) or any(
            str(student.get("status") or "") != "ready" for student in refreshed_students
        ) else "ready"
        mark_wrong_question_practice_pack_job_status(
            job_id,
            status=final_status,
            zip_path=str(zip_result.get("zip_path") or ""),
            generation_error="",
        )
    except Exception as exc:
        logger.exception("Wrong question practice pack generation failed for job %s", job_id)
        try:
            mark_wrong_question_practice_pack_job_status(
                job_id,
                status="failed",
                zip_path="",
                generation_error=str(exc) or "生成失败",
            )
        except LookupError:
            logger.exception("Failed to mark wrong question practice pack job %s as failed", job_id)


def _start_wrong_question_practice_pack_thread(**job_kwargs) -> None:
    threading.Thread(
        target=_run_wrong_question_practice_pack_job,
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


def _has_api_key_for_provider(provider: str) -> bool:
    cfg = get_config()
    if provider == "deepseek":
        key = cfg.get("deepseek_api_key", "") or os.environ.get("DEEPSEEK_API_KEY", "")
    else:
        key = cfg.get("openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
    return bool(key.strip())


def has_api_key():
    return _has_api_key_for_provider(_default_ai_provider_name())


def has_review_plan_api_key():
    providers = {_review_plan_ai_provider_name(), _review_plan_writer_ai_provider_name()}
    return all(_has_api_key_for_provider(provider) for provider in providers)


def has_class_commentary_api_key():
    provider = _class_commentary_ai_provider_name(fallback=_default_ai_provider_name())
    if provider == "openai":
        return bool(_class_commentary_openai_api_key())
    return _has_api_key_for_provider(provider)


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
def _get_ready_review_plan_version_pdf_path(lesson_id: int, version_id: int | None = None) -> str:
    version = (
        get_review_plan_version_for_lesson(lesson_id, version_id)
        if version_id
        else get_current_review_plan_version(lesson_id)
    )
    if not version or str(version.get("status") or "") != "ready":
        return ""
    pdf_path = str(version.get("pdf_path") or "")
    if not pdf_path or not Path(pdf_path).exists():
        return ""
    return pdf_path


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
    pdf_path = _get_ready_review_plan_version_pdf_path(lesson_id)
    if not pdf_path:
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
    pdf_path = _get_ready_review_plan_version_pdf_path(lesson_id)
    if not pdf_path:
        abort(404)
    return send_file(pdf_path, as_attachment=True,
                     download_name=Path(pdf_path).name)


@app.route("/api/student/pdf/<int:lesson_id>")
def serve_student_pdf(lesson_id):
    account, error = _require_student_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not student_account_can_access_lesson(account, lesson_id):
        abort(404)
    pdf_path = _get_ready_review_plan_version_pdf_path(lesson_id)
    if not pdf_path:
        abort(404)
    return send_file(pdf_path, mimetype="application/pdf", download_name=Path(pdf_path).name)


@app.route("/api/student/pdf/download/<int:lesson_id>")
def download_student_pdf(lesson_id):
    account, error = _require_student_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not student_account_can_access_lesson(account, lesson_id):
        abort(404)
    pdf_path = _get_ready_review_plan_version_pdf_path(lesson_id)
    if not pdf_path:
        abort(404)
    return send_file(pdf_path, as_attachment=True, download_name=Path(pdf_path).name)


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


@app.route("/api/student/class-invite/<invite_code>", methods=["GET"])
def api_student_class_invite_preview(invite_code):
    payload = preview_student_class_invite(invite_code)
    if not payload:
        return jsonify({"error": "invite not found"}), 404
    return jsonify(payload)


@app.route("/api/student/register", methods=["POST"])
def api_student_register():
    data, error = _get_json_object_payload()
    if error:
        return error
    raw_student_id = data.get("student_id")
    if isinstance(raw_student_id, bool) or not isinstance(raw_student_id, int):
        return jsonify({"error": "student_id required"}), 400
    try:
        account = create_student_account_by_invite(
            invite_code=(data.get("invite_code") or "").strip(),
            student_id=raw_student_id,
            username=(data.get("username") or "").strip(),
            password=(data.get("password") or "").strip(),
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        status_code = 409 if str(exc) in {"username exists", "student account exists"} else 400
        return jsonify({"error": str(exc)}), status_code
    token = create_student_auth_session(account["id"])
    return jsonify({"token": token, "account": account}), 201


@app.route("/api/student/login", methods=["POST"])
def api_student_login():
    data, error = _get_json_object_payload()
    if error:
        return error
    account, message = authenticate_student_account(
        username=(data.get("username") or "").strip(),
        password=(data.get("password") or "").strip(),
    )
    if not account:
        return jsonify({"error": message}), 401
    token = create_student_auth_session(account["id"])
    return jsonify({"token": token, "account": account})


@app.route("/api/student/me", methods=["GET"])
def api_student_me():
    account, error = _require_student_auth()
    if error:
        return error
    return jsonify({"account": account})


@app.route("/api/student/review-tasks", methods=["GET"])
def api_student_review_tasks():
    account, error = _require_student_auth()
    if error:
        return error
    raw_date = str(request.args.get("date") or date.today().isoformat()).strip()
    try:
        date.fromisoformat(raw_date)
    except ValueError:
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    payload = list_student_review_tasks_for_student_account(account, raw_date)
    if payload is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(payload)


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


def _require_student_auth():
    token = (
        request.headers.get("X-Student-Auth-Token", "").strip()
        or request.args.get("token", "").strip()
    )
    account = get_current_student_account(token)
    if not account:
        return None, (jsonify({"error": "unauthorized"}), 401)
    return account, None


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


def _normalize_wrong_question_confirmation_status(record: object) -> str:
    if not isinstance(record, dict):
        return "not_required"
    status = str(record.get("confirmation_status") or record.get("confirmationStatus") or "").strip()
    if status in {"pending", "confirmed", "returned", "not_required"}:
        return status
    needs_teacher_confirmation = record.get("needs_teacher_confirmation")
    if needs_teacher_confirmation is None:
        needs_teacher_confirmation = record.get("needsTeacherConfirmation")
    if isinstance(needs_teacher_confirmation, str):
        needs_teacher_confirmation = needs_teacher_confirmation.strip().lower() in {"1", "true", "yes", "on"}
    elif isinstance(needs_teacher_confirmation, (int, float)):
        needs_teacher_confirmation = bool(needs_teacher_confirmation)
    elif not isinstance(needs_teacher_confirmation, bool):
        needs_teacher_confirmation = False
    if needs_teacher_confirmation:
        return "pending"
    if (
        record.get("confirmation_reviewed_at")
        or record.get("confirmationReviewedAt")
        or record.get("confirmation_reviewed_by") is not None
        or record.get("confirmationReviewedBy") is not None
    ):
        return "confirmed"
    return "not_required"


def _filter_wrong_question_items_by_confirmation_state(items: list[dict], raw_confirmation_state: str) -> list[dict]:
    confirmation_state = (raw_confirmation_state or "").strip()
    if confirmation_state not in {"pending", "confirmed", "returned"}:
        return items
    return [
        item
        for item in items
        if _normalize_wrong_question_confirmation_status(item) == confirmation_state
    ]


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
    source_records = [
        serialized
        for serialized in (
            _serialize_wrong_question_record_for_response(record, include_archive_context=True)
            for record in (item.get("source_records") or [])
        )
        if serialized is not None
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
        "status": item.get("status") or "no_practice_needed",
        "practice_sheet": _serialize_wrong_question_practice_sheet_for_response(item.get("practice_sheet")),
        "weekly_question_count": item.get("weekly_question_count"),
        "total_active_question_count": item.get("total_active_question_count"),
        "candidate_question_count": item.get("candidate_question_count") or 0,
        "candidate_record_ids": item.get("candidate_record_ids") or [],
        "recommended_category": item.get("recommended_category") or "",
        "recommendation_reason": item.get("recommendation_reason") or "",
        "topic_categories": item.get("topic_categories") or [],
        "representative_reason_summaries": item.get("representative_reason_summaries") or [],
        "latest_created_at": item.get("latest_created_at"),
        "source_record_ids": source_record_ids,
        "source_records": source_records,
        "repeated_category": item.get("repeated_category") or "",
        "repeated_category_count": int(item.get("repeated_category_count") or 0),
        "message": _weekly_followup_message_payload(message),
        "student_library_pdf_url": f"/api/wechat/student-libraries/{student_id}",
    }


def _weekly_activity_student_item_payload(item: dict) -> dict:
    source_record_ids = [
        str(record_id).strip()
        for record_id in item.get("source_record_ids", [])
        if str(record_id or "").strip()
    ]
    source_records = [
        serialized
        for serialized in (
            _serialize_wrong_question_record_for_response(record, include_archive_context=True)
            for record in (item.get("source_records") or [])
        )
        if serialized is not None
    ]
    return {
        "organization_id": item.get("organization_id"),
        "organization_name": item.get("organization_name"),
        "class_id": item.get("class_id"),
        "class_name": item.get("class_name"),
        "student_id": item.get("student_id"),
        "student_name": item.get("student_name"),
        "weekly_question_count": item.get("weekly_question_count"),
        "total_question_count": item.get("total_question_count"),
        "topic_categories": item.get("topic_categories") or [],
        "latest_created_at": item.get("latest_created_at"),
        "source_record_ids": source_record_ids,
        "source_records": source_records,
    }


def _review_plan_preview_text(value: object, limit: int = 240) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _serialize_review_plan_math_blocks(plan: dict) -> list[dict]:
    blocks: list[dict] = []
    knowledge_sections = plan.get("knowledge_sections") if isinstance(plan.get("knowledge_sections"), dict) else {}
    raw_blocks = plan.get("math_blocks") if isinstance(plan.get("math_blocks"), list) else knowledge_sections.get("math_blocks")
    if not isinstance(raw_blocks, list):
        return []
    for index, block in enumerate(raw_blocks[:40]):
        if not isinstance(block, dict):
            continue
        latex = _review_plan_preview_text(block.get("latex") or block.get("formula") or block.get("text"), 500)
        if not latex:
            continue
        block_id = _review_plan_preview_text(block.get("id") or block.get("key") or f"math_{index + 1}", 80)
        blocks.append(
            {
                "id": block_id,
                "latex": latex,
                "display": block.get("display") is True,
            }
        )
    return blocks


def _serialize_review_plan_preview_question(item: object, question_type: str) -> Optional[dict]:
    if not isinstance(item, dict):
        return None
    question = _review_plan_preview_text(item.get("question") or item.get("stem") or item.get("text"), 300)
    answer = _review_plan_preview_text(item.get("answer"), 160)
    if not question and not answer:
        return None
    options = item.get("options") if isinstance(item.get("options"), list) else []
    return {
        "type": question_type,
        "question": question,
        "options": [_review_plan_preview_text(option, 160) for option in options[:6] if str(option or "").strip()],
        "answer": answer,
    }


def _serialize_review_plan_current_preview(plan: object) -> dict:
    if not isinstance(plan, dict) or not plan:
        return {}
    try:
        normalized = normalize_final_review_plan(plan)
    except Exception:
        normalized = plan
    lesson_info = normalized.get("lesson_info") if isinstance(normalized.get("lesson_info"), dict) else {}
    days_payload: list[dict] = []
    for day in normalized.get("days", []) if isinstance(normalized.get("days"), list) else []:
        if not isinstance(day, dict):
            continue
        questions: list[dict] = []
        for blank in day.get("blanks", []) if isinstance(day.get("blanks"), list) else []:
            question = _serialize_review_plan_preview_question(blank, "blank")
            if question:
                questions.append(question)
        for choice in day.get("choices", []) if isinstance(day.get("choices"), list) else []:
            question = _serialize_review_plan_preview_question(choice, "choice")
            if question:
                questions.append(question)
        days_payload.append(
            {
                "day": day.get("day") or day.get("offset") or "",
                "label": _review_plan_preview_text(day.get("label") or day.get("day_label") or day.get("title"), 80),
                "goal": _review_plan_preview_text(day.get("goal"), 180),
                "focus": _review_plan_preview_text(day.get("focus"), 180),
                "questions": questions[:12],
            }
        )
    return {
        "title": _review_plan_preview_text(lesson_info.get("topic") or normalized.get("title") or normalized.get("plan_title"), 120),
        "summary": _review_plan_preview_text(normalized.get("weak_points_summary") or normalized.get("lesson_summary"), 300),
        "math_blocks": _serialize_review_plan_math_blocks(normalized),
        "days": days_payload[:7],
    }


def _serialize_review_plan_version_for_response(lesson_id: int, version: object) -> Optional[dict]:
    if not isinstance(version, dict):
        return None
    serialized = dict(version)
    serialized.pop("plan_json", None)
    serialized.pop("generation_options_json", None)
    pdf_path = str(serialized.get("pdf_path") or "")
    is_ready = str(serialized.get("status") or "") == "ready"
    pdf_exists = bool(pdf_path and Path(pdf_path).exists())
    serialized["pdf_available"] = pdf_exists
    serialized["pdf_url"] = (
        f"/api/review-plans/{lesson_id}/versions/{serialized['id']}/pdf"
        if is_ready and pdf_exists
        else ""
    )
    serialized["download_url"] = (
        f"/api/review-plans/{lesson_id}/versions/{serialized['id']}/download"
        if is_ready and pdf_exists
        else ""
    )
    if not pdf_exists:
        serialized["pdf_path"] = ""
    return serialized


def _serialize_lesson_for_response(
    lesson: object,
    *,
    include_versions: bool = False,
    include_runtime: bool = False,
) -> Optional[dict]:
    if not isinstance(lesson, dict):
        return None
    serialized = dict(lesson)
    lesson_id = int(serialized.get("id") or 0)
    current_version = serialized.get("current_version")
    if not isinstance(current_version, dict):
        current_version = get_current_review_plan_version(lesson_id) if lesson_id else None
    serialized["current_version"] = _serialize_review_plan_version_for_response(
        lesson_id,
        current_version,
    ) if current_version else None
    serialized["current_version_id"] = current_version.get("id") if current_version else None
    serialized["current_review_plan_version_id"] = serialized["current_version_id"]
    serialized["current_version_no"] = current_version.get("version_no") if current_version else None
    serialized["current_status"] = current_version.get("status") if current_version else ""
    serialized["current_generated_at"] = current_version.get("completed_at") if current_version else ""
    current_pdf_path = str((current_version or {}).get("pdf_path") or "")
    current_pdf_exists = bool(current_pdf_path and Path(current_pdf_path).exists())
    serialized["current_pdf_url"] = (
        f"/api/review-plans/{lesson_id}/versions/{current_version['id']}/pdf"
        if current_version and str(current_version.get("status") or "") == "ready" and current_pdf_exists
        else ""
    )
    serialized["current_download_url"] = (
        f"/api/review-plans/{lesson_id}/versions/{current_version['id']}/download"
        if current_version and str(current_version.get("status") or "") == "ready" and current_pdf_exists
        else ""
    )
    serialized["current_plan_preview"] = (
        _serialize_review_plan_current_preview(current_version.get("plan"))
        if include_versions and current_version
        else {}
    )
    serialized["pdf_path"] = current_pdf_path if current_pdf_exists else ""
    if include_runtime:
        try:
            latest_run = get_latest_review_plan_run_for_lesson(lesson_id)
        except Exception:
            latest_run = None
        if latest_run:
            serialized["trace_id"] = latest_run.get("trace_id", "")
            serialized["workflow_warnings"] = latest_run.get("warnings", [])
            serialized["quality_review"] = latest_run.get("quality_review", {})
            serialized["prompt_version"] = latest_run.get("prompt_version", "")
            serialized["style_version"] = latest_run.get("style_version", "")
    creator_user_id = int(serialized.get("created_by_user_id") or 0)
    creator = None
    if creator_user_id and not (serialized.get("creator_display_name") or serialized.get("creator_username")):
        creator = get_user_by_id(creator_user_id)
    serialized["creator_display_name"] = str(
        serialized.get("creator_display_name")
        or (creator or {}).get("display_name")
        or (creator or {}).get("username")
        or ""
    ).strip()
    serialized["creator_username"] = str(
        serialized.get("creator_username")
        or (creator or {}).get("username")
        or ""
    ).strip()
    if include_versions:
        serialized["versions"] = [
            item
            for item in (
                _serialize_review_plan_version_for_response(lesson_id, version)
                for version in list_review_plan_versions(lesson_id)
            )
            if item is not None
        ]
    return serialized


def _serialize_lessons_for_response(lessons: object) -> list[dict]:
    if not isinstance(lessons, list):
        return []
    serialized_lessons = []
    for lesson in lessons:
        serialized = _serialize_lesson_for_response(lesson)
        if serialized is not None:
            serialized_lessons.append(serialized)
    return sorted(
        serialized_lessons,
        key=lambda item: (
            _dashboard_item_datetime(item, "current_generated_at", "updated_at", "created_at", "date"),
            int(item.get("id") or 0),
        ),
        reverse=True,
    )


def _serialize_review_plan_failure_notification(user: dict, notification: object) -> Optional[dict]:
    if not isinstance(notification, dict):
        return None
    lesson = get_lesson(int(notification.get("lesson_id") or 0))
    if not lesson or not _can_access_lesson(user, lesson):
        return None
    serialized = _serialize_lesson_for_response(lesson)
    if serialized is None:
        return None
    version_id = int(notification.get("version_id") or 0)
    generation_error = str(notification.get("generation_error") or "")
    serialized.update(
        {
            "notification_version_id": version_id,
            "notification_created_at": str(notification.get("notification_created_at") or ""),
            "latest_failed_version_id": version_id,
            "latest_failed_version_no": int(notification.get("version_no") or 0),
            "latest_failed_at": str(notification.get("failed_at") or ""),
            "latest_generation_error": generation_error,
            "generation_error": generation_error,
            "record_status": "failed",
            "has_version_generating": False,
            "active_version_status": "",
            "active_version_created_at": "",
            "current_status": "",
            "current_pdf_url": "",
            "current_download_url": "",
            "pdf_path": "",
        }
    )
    return serialized


def _serialize_class_commentary_task_for_response(
    task: dict,
    *,
    include_private: bool = False,
) -> dict:
    item = {
        "id": int(task["id"]),
        "organization_id": int(task["organization_id"]),
        "class_id": int(task["class_id"]),
        "class_name": str(task.get("class_name") or ""),
        "teacher_user_id": int(task["teacher_user_id"]),
        "status": str(task.get("status") or ""),
        "final_feedback_text": str(task.get("final_feedback_text") or ""),
        "feedback_confirmed_at": str(task.get("feedback_confirmed_at") or ""),
        "created_at": str(task.get("created_at") or ""),
        "updated_at": str(task.get("updated_at") or ""),
    }
    if not include_private:
        return item
    item.update({
        "failure_stage": str(task.get("failure_stage") or ""),
        "audio_filename": str(task.get("audio_filename") or ""),
        "transcript_text": str(task.get("transcript_text") or ""),
        "confirmed_transcript_text": str(task.get("confirmed_transcript_text") or ""),
        "confirmed_transcript_version": int(task.get("confirmed_transcript_version") or 0),
        "transcribed_at": str(task.get("transcribed_at") or ""),
        "skill_id": str(task.get("skill_id") or ""),
        "skill_name": str(task.get("skill_name") or ""),
        "skill_filename": Path(str(task.get("skill_path") or "")).name if task.get("skill_path") else "",
        "feedback_text": str(task.get("feedback_text") or ""),
        "latest_generation_id": int(task.get("latest_generation_id") or 0) or None,
        "latest_revision_id": int(task.get("latest_revision_id") or 0) or None,
        "generation_seq": int(task.get("generation_seq") or 0),
        "feedback_revision_no": int(task.get("feedback_revision_no") or 0),
        "transcription_error": str(task.get("transcription_error") or ""),
        "generation_error": str(task.get("generation_error") or ""),
    })
    return item


def _class_commentary_json_value(value: object, fallback: object):
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except (TypeError, json.JSONDecodeError):
        return fallback


def _class_commentary_structured_feedback_error_payload(
    exc: ClassCommentaryStructuredFeedbackValidationError,
) -> dict:
    payload = {"error": exc.code}
    if exc.student_id is not None:
        payload["student_id"] = int(exc.student_id)
    if exc.field:
        payload["field"] = str(exc.field)
    if exc.limit is not None:
        payload["limit"] = int(exc.limit)
    return payload


def _class_commentary_feedback_read_envelope(
    record: dict,
    *,
    derived_text_field: str,
    structured_hash_field: str,
    generation: Optional[dict] = None,
    allow_empty_generation_payload: bool = False,
) -> dict:
    schema_version = str(record.get("feedback_schema_version") or "")
    if (
        generation is None
        and schema_version == CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1
    ):
        generation_id = int(record.get("generation_id") or 0)
        if generation_id > 0:
            generation = get_class_commentary_generation(generation_id)
    return build_class_commentary_feedback_read_envelope(
        schema_version=schema_version,
        structured_json=record.get("structured_feedback_json"),
        stored_hash=record.get(structured_hash_field),
        derived_text=record.get(derived_text_field),
        generation=generation,
        allow_empty_generation_payload=allow_empty_generation_payload,
    )


def _serialize_class_commentary_generation_for_response(
    generation: dict,
    *,
    include_private_snapshots: bool = False,
) -> dict:
    feedback_envelope = _class_commentary_feedback_read_envelope(
        generation,
        derived_text_field="generated_feedback_text",
        structured_hash_field="structured_feedback_hash",
        generation=generation,
        allow_empty_generation_payload=True,
    )
    student_run_progress = get_class_commentary_student_generation_progress(
        int(generation["id"])
    )
    item = {
        "id": int(generation["id"]),
        "generation_id": int(generation["id"]),
        "organization_id": int(generation["organization_id"]),
        "task_id": int(generation["task_id"]),
        "generation_no": int(generation["generation_no"]),
        "generation_request_id": str(generation.get("generation_request_id") or ""),
        "teacher_user_id": int(generation["teacher_user_id"]),
        "class_id": int(generation["class_id"]),
        "subject_key": generation.get("subject_key"),
        "attending_roster_explicit": bool(
            generation.get("attending_roster_explicit")
        ),
        "skill_registry_id": int(generation.get("skill_registry_id") or 0) or None,
        "skill_id": str(generation.get("skill_id") or ""),
        "skill_version_id": int(generation.get("skill_version_id") or 0) or None,
        "model_provider": str(generation.get("model_provider") or ""),
        "model_name": str(generation.get("model_name") or ""),
        "prompt_version": str(generation.get("prompt_version") or ""),
        "generated_feedback_text": str(generation.get("generated_feedback_text") or ""),
        "origin": str(generation.get("origin") or ""),
        "snapshot_completeness": str(generation.get("snapshot_completeness") or ""),
        "execution_snapshot_status": str(
            generation.get("execution_snapshot_status") or "ready"
        ),
        "execution_snapshot_finalized_at": str(
            generation.get("execution_snapshot_finalized_at") or ""
        ),
        "eligible_student_ids": _class_commentary_json_value(
            generation.get("eligible_student_ids_json"),
            [],
        ),
        "eligible_student_scope_hash": str(
            generation.get("eligible_student_scope_hash") or ""
        ),
        "student_mention_matcher_version": str(
            generation.get("student_mention_matcher_version") or ""
        ),
        "response_format": _class_commentary_json_value(
            generation.get("response_format_json"),
            {},
        ),
        "student_history_memory_mode": str(
            generation.get("student_history_memory_mode") or ""
        ),
        "student_run_progress": student_run_progress,
        "missing_snapshot_fields": _class_commentary_json_value(
            generation.get("missing_snapshot_fields_json"),
            [],
        ),
        "status": str(generation.get("status") or ""),
        "error_code": generation.get("error_code"),
        "created_at": str(generation.get("created_at") or ""),
        "completed_at": str(generation.get("completed_at") or ""),
        "is_latest": bool(generation.get("is_latest")),
        "latest_revision_id": int(generation.get("latest_revision_id") or 0) or None,
        "has_draft": bool(generation.get("draft_id")),
        "draft_version": int(generation.get("draft_version") or 0),
        "draft_updated_at": str(generation.get("draft_updated_at") or ""),
        **feedback_envelope,
    }
    if include_private_snapshots:
        item.update(
            {
                "generation_request_payload_hash": str(
                    generation.get("generation_request_payload_hash") or ""
                ),
                "confirmed_transcript_version": int(
                    generation.get("confirmed_transcript_version") or 0
                ),
                "confirmed_transcript_snapshot": str(
                    generation.get("confirmed_transcript_snapshot") or ""
                ),
                "confirmed_transcript_hash": str(
                    generation.get("confirmed_transcript_hash") or ""
                ),
                "attending_roster_snapshot": _class_commentary_json_value(
                    generation.get("attending_roster_snapshot_json"),
                    [],
                ),
                "attending_roster_hash": str(generation.get("attending_roster_hash") or ""),
                "skill_content_snapshot": str(generation.get("skill_content_snapshot") or ""),
                "skill_content_hash": str(generation.get("skill_content_hash") or ""),
                "model_parameters": _class_commentary_json_value(
                    generation.get("model_parameters_json"),
                    {},
                ),
                "prompt_payload_snapshot": _class_commentary_json_value(
                    generation.get("prompt_payload_snapshot_json"),
                    {},
                ),
                "prompt_payload_hash": str(generation.get("prompt_payload_hash") or ""),
                "memory_context_snapshot": _class_commentary_json_value(
                    generation.get("memory_context_snapshot_json"),
                    {},
                ),
                "memory_context_hash": str(generation.get("memory_context_hash") or ""),
            }
        )
    return item


def _serialize_class_commentary_draft_for_response(
    draft: Optional[dict],
    *,
    generation: Optional[dict] = None,
) -> dict:
    if not draft:
        return {
            "draft": None,
            "draft_version": 0,
        }
    feedback_envelope = _class_commentary_feedback_read_envelope(
        draft,
        derived_text_field="feedback_text",
        structured_hash_field="content_hash",
        generation=generation,
    )
    serialized = {
        "id": int(draft["id"]),
        "organization_id": int(draft["organization_id"]),
        "task_id": int(draft["task_id"]),
        "generation_id": int(draft["generation_id"]),
        "teacher_user_id": int(draft["teacher_user_id"]),
        "based_on_revision_id": int(draft.get("based_on_revision_id") or 0) or None,
        "feedback_text": str(draft.get("feedback_text") or ""),
        "content_hash": str(draft.get("content_hash") or ""),
        "draft_version": int(draft["draft_version"]),
        "created_at": str(draft.get("created_at") or ""),
        "updated_at": str(draft.get("updated_at") or ""),
        **feedback_envelope,
    }
    return {**serialized, "draft": serialized}


def _serialize_class_commentary_revision_for_response(
    revision: dict,
    *,
    generation: Optional[dict] = None,
) -> dict:
    feedback_envelope = _class_commentary_feedback_read_envelope(
        revision,
        derived_text_field="final_feedback_text",
        structured_hash_field="structured_feedback_hash",
        generation=generation,
    )
    confirmed_draft_version = int(revision.get("confirmed_draft_version") or 0)
    return {
        "id": int(revision["id"]),
        "organization_id": int(revision["organization_id"]),
        "task_id": int(revision["task_id"]),
        "generation_id": int(revision["generation_id"]),
        "teacher_user_id": int(revision["teacher_user_id"]),
        "revision_no": int(revision["revision_no"]),
        "previous_revision_id": int(revision.get("previous_revision_id") or 0) or None,
        "final_feedback_text": str(revision.get("final_feedback_text") or ""),
        "generation_diff": _class_commentary_json_value(
            revision.get("generation_diff_json"),
            {},
        ),
        "previous_revision_diff": _class_commentary_json_value(
            revision.get("previous_revision_diff_json"),
            None,
        ),
        "learn_requested": bool(revision.get("learn_requested")),
        "accepted_without_edit": bool(revision.get("accepted_without_edit")),
        "unchanged_from_previous_revision": bool(
            revision.get("unchanged_from_previous_revision")
        ),
        "learning_evidence_completeness": str(
            revision.get("learning_evidence_completeness") or ""
        ),
        "confirmed_at": str(revision.get("confirmed_at") or ""),
        "confirmed_draft_version": confirmed_draft_version,
        "draft_version": int(revision.get("draft_version") or confirmed_draft_version),
        **feedback_envelope,
    }


def _serialize_class_commentary_memory_summary(
    raw_summary: dict,
    *,
    actor_user_id: int,
) -> dict:
    revision_id = int(raw_summary.get("revision_id") or 0)
    revision = get_class_commentary_revision(revision_id) if revision_id else None
    generation = (
        get_class_commentary_generation(int(revision["generation_id"]))
        if revision
        else None
    )
    student_names = {
        int(item.get("student_id") or 0): str(item.get("student_name") or "")
        for item in _class_commentary_json_value(
            (generation or {}).get("attending_roster_snapshot_json"),
            [],
        )
        if isinstance(item, dict) and int(item.get("student_id") or 0) > 0
    }
    job = raw_summary.get("job") if isinstance(raw_summary.get("job"), dict) else None
    job_status = str((job or {}).get("status") or "")
    raw_memories = [
        item for item in raw_summary.get("memories", []) if isinstance(item, dict)
    ]
    operation_statuses = {
        str(item.get("latest_operation_status") or "")
        for item in raw_memories
        if item.get("latest_operation_status")
    }
    learn_requested = bool(raw_summary.get("learn_requested"))
    retryable = False
    error = ""
    if not learn_requested:
        status = "not_requested"
    elif job_status in {"queued", "retry_wait"}:
        status = "queued"
    elif job_status == "running":
        status = "extracting"
    elif job_status == "obsolete":
        status = "obsolete"
    elif job_status in {"failed", "integrity_failed"}:
        status = "failed"
        retryable = job_status == "failed"
        error = (
            "学习任务失败, 可以重试."
            if retryable
            else "学习记录校验失败, 已停止自动重试."
        )
    elif job_status == "extracted":
        failed_operations = operation_statuses & {"failed"}
        pending_operations = operation_statuses & {
            "pending",
            "running",
            "retry_wait",
            "reconcile_needed",
        }
        applied_count = sum(
            1
            for item in raw_memories
            if str(item.get("desired_status") or "")
            == str(item.get("applied_status") or "")
        )
        if failed_operations:
            status = "partial" if applied_count else "failed"
            retryable = True
            error = "部分记忆同步失败, 可以重试."
        elif pending_operations:
            status = "syncing"
        else:
            status = "complete"
    else:
        status = "queued"

    memories = []
    for item in raw_memories:
        student_id = int(item.get("student_id") or 0) or None
        evidence_status = str(item.get("status") or "active")
        if evidence_status not in {"active", "revoked", "superseded"}:
            evidence_status = "active"
        memories.append(
            {
                "id": int(item.get("memory_record_id") or 0),
                "evidence_id": int(item.get("id") or 0),
                "memory_type": str(item.get("memory_type") or "teacher_style"),
                "memory_text": str(item.get("memory_text") or ""),
                "student_id": student_id,
                "student_name": student_names.get(student_id or 0, ""),
                "confidence": float(item.get("confidence") or 0),
                "evidence_status": evidence_status,
                "active_evidence_count": int(item.get("active_evidence_count") or 0),
                "operation_status": str(item.get("latest_operation_status") or ""),
                "can_revoke": evidence_status == "active"
                and int(item.get("source_teacher_user_id") or 0) == int(actor_user_id),
            }
        )
    return {
        "revision_id": revision_id,
        "status": status,
        "retryable": retryable,
        "extraction_status": job_status,
        "error": error,
        "memories": memories,
    }


_CLASS_COMMENTARY_SKILL_STALE_REASONS = {
    "base_version_changed",
    "base_version_missing",
    "frozen_revision_count_mismatch",
    "registry_scope_mismatch",
    "revision_not_effective",
    "revision_scope_mismatch",
    "revision_snapshot_mismatch",
    "selection_policy_mismatch",
    "source_snapshot_mismatch",
    "supporting_evidence_not_active",
    "supporting_evidence_revision_mismatch",
    "supporting_evidence_scope_mismatch",
    "supporting_task_count_mismatch",
}


def _class_commentary_safe_skill_stale_reason(value: object) -> str:
    reason = str(value or "").strip()
    if not reason:
        return ""
    if reason in _CLASS_COMMENTARY_SKILL_STALE_REASONS:
        return reason
    return "candidate_source_changed"


def _serialize_class_commentary_skill_for_evolution(skill: dict) -> dict:
    return {
        "registry_id": int(skill.get("registry_id") or 0),
        "id": str(skill.get("skill_id") or skill.get("id") or ""),
        "skill_id": str(skill.get("skill_id") or skill.get("id") or ""),
        "name": str(skill.get("name") or skill.get("skill_id") or ""),
        "organization_id": int(skill.get("organization_id") or 0),
        "can_manage_evolution": True,
        "status": str(skill.get("status") or ""),
        "active_version_id": int(skill.get("active_version_id") or 0) or None,
        "version_id": int(skill.get("version_id") or 0) or None,
        "version_no": int(skill.get("version_no") or 0),
        "version_kind": str(skill.get("version_kind") or ""),
        "content": str(skill.get("content") or ""),
        "content_hash": str(skill.get("content_hash") or ""),
        "updated_at": str(skill.get("updated_at") or ""),
    }


def _serialize_class_commentary_skill_candidate_build_for_response(
    build: dict,
) -> dict:
    frozen_revisions = [
        item
        for item in build.get("frozen_revisions", [])
        if isinstance(item, dict)
    ]
    frozen_evidence = [
        item for item in build.get("frozen_evidence", []) if isinstance(item, dict)
    ]
    status = str(build.get("status") or "failed")
    if status not in {
        "queued",
        "running",
        "retry_wait",
        "succeeded",
        "failed",
        "obsolete",
    }:
        status = "failed"
    stale_reason = _class_commentary_safe_skill_stale_reason(
        build.get("stale_reason")
    )
    is_stale = bool(build.get("is_stale")) or status == "obsolete"
    if is_stale and not stale_reason:
        stale_reason = "candidate_source_changed"
    error_message = ""
    if status == "failed":
        error_message = "候选生成失败, 请重新生成."
    elif status == "obsolete":
        error_message = "候选依据已变化, 请基于最新证据重新生成."
    return {
        "id": int(build.get("id") or 0),
        "expected_active_version_id": int(
            build.get("expected_active_version_id") or 0
        ),
        "base_version_id": int(build.get("base_version_id") or 0),
        "candidate_version_id": int(build.get("candidate_version_id") or 0)
        or None,
        "effective_task_count": int(build.get("effective_task_count") or 0),
        "supporting_task_count": int(build.get("supporting_task_count") or 0),
        "min_effective_tasks": int(build.get("min_effective_tasks") or 0),
        "min_supporting_tasks": int(build.get("min_support_tasks") or 0),
        "status": status,
        "error_message": error_message,
        "can_retry": status in {"failed", "obsolete"},
        "is_terminal": status in {"succeeded", "failed", "obsolete"},
        "is_stale": is_stale,
        "stale_reason": stale_reason,
        "source_cutoff_at": str(build.get("source_cutoff_at") or ""),
        "selection_policy_version": str(
            build.get("selection_policy_version") or ""
        ),
        "frozen_task_ids": sorted(
            {
                int(item.get("task_id") or 0)
                for item in frozen_revisions
                if int(item.get("task_id") or 0) > 0
            }
        ),
        "frozen_revision_ids": sorted(
            {
                int(item.get("revision_id") or 0)
                for item in frozen_revisions
                if int(item.get("revision_id") or 0) > 0
            }
        ),
        "frozen_evidence_ids": sorted(
            {
                int(item.get("memory_evidence_id") or 0)
                for item in frozen_evidence
                if int(item.get("memory_evidence_id") or 0) > 0
            }
        ),
        "frozen_memory_record_ids": sorted(
            {
                int(item.get("memory_record_id") or 0)
                for item in frozen_evidence
                if int(item.get("memory_record_id") or 0) > 0
            }
        ),
        "frozen_revision_count": len(frozen_revisions),
        "frozen_evidence_count": len(frozen_evidence),
        "created_at": str(build.get("created_at") or ""),
        "started_at": str(build.get("started_at") or ""),
        "completed_at": str(build.get("completed_at") or ""),
    }


def _class_commentary_skill_content_diff(
    base_content: str,
    content: str,
    *,
    base_version_no: int,
    version_no: int,
) -> str:
    if not base_content:
        return ""
    return "\n".join(
        difflib.unified_diff(
            base_content.splitlines(),
            content.splitlines(),
            fromfile=f"version-{base_version_no}",
            tofile=f"version-{version_no}",
            lineterm="",
        )
    )


def _serialize_class_commentary_skill_evaluation_for_response(
    evaluation: dict,
) -> dict:
    metrics = evaluation.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    current_metrics = evaluation.get("current_metrics")
    if not isinstance(current_metrics, dict):
        current_metrics = metrics.get("current") or metrics.get("base") or {}
    candidate_metrics = evaluation.get("candidate_metrics")
    if not isinstance(candidate_metrics, dict):
        candidate_metrics = metrics.get("candidate") or {}
    known_risks = [
        str(item).strip()
        for item in evaluation.get("known_risks", [])
        if str(item).strip()
    ]
    change_summary = [
        str(item).strip()
        for item in evaluation.get("change_summary", [])
        if str(item).strip()
    ]
    failed_samples = [
        str(item).strip()
        for item in evaluation.get("failed_samples", [])
        if isinstance(item, str) and item.strip()
    ]
    if not failed_samples:
        for sample in evaluation.get("samples", []):
            if not isinstance(sample, dict):
                continue
            failed = (
                sample.get("candidate_roster_consistent") is False
                or sample.get("candidate_plain_text_valid") is False
                or sample.get("candidate_structure_valid") is False
                or int(sample.get("candidate_unsupported_fact_count") or 0) > 0
            )
            if failed:
                failed_samples.append(
                    f"task-{int(sample.get('task_id') or 0)}-revision-{int(sample.get('revision_id') or 0)}"
                )
    return {
        "current_metrics": current_metrics,
        "candidate_metrics": candidate_metrics,
        "change_summary": change_summary,
        "known_risks": known_risks,
        "failed_samples": failed_samples,
        "failed_sample_count": len(failed_samples),
    }


def _serialize_class_commentary_skill_versions_for_response(
    versions: list[dict],
    *,
    active_version_id: int,
) -> list[dict]:
    by_id = {
        int(version.get("id") or 0): version
        for version in versions
        if isinstance(version, dict)
    }
    serialized = []
    for version in versions:
        candidate_build = (
            version.get("candidate_build")
            if isinstance(version.get("candidate_build"), dict)
            else None
        )
        safe_build = (
            _serialize_class_commentary_skill_candidate_build_for_response(
                candidate_build
            )
            if candidate_build
            else None
        )
        base_version_id = int(version.get("base_version_id") or 0) or None
        base_version = by_id.get(base_version_id or 0)
        base_content = str((base_version or {}).get("content") or "")
        content = str(version.get("content") or "")
        evaluation = version.get("evaluation_snapshot")
        if not isinstance(evaluation, dict):
            evaluation = _class_commentary_json_value(
                version.get("evaluation_snapshot_json"),
                {},
            )
        if not isinstance(evaluation, dict):
            evaluation = {}
        serialized_evaluation = (
            _serialize_class_commentary_skill_evaluation_for_response(evaluation)
        )
        frozen_revision_ids = (
            list(safe_build["frozen_revision_ids"]) if safe_build else []
        )
        frozen_evidence_ids = (
            list(safe_build["frozen_evidence_ids"]) if safe_build else []
        )
        stale_reason = _class_commentary_safe_skill_stale_reason(
            version.get("stale_reason")
        )
        serialized.append(
            {
                "id": int(version.get("id") or 0),
                "organization_id": int(version.get("organization_id") or 0),
                "skill_registry_id": int(version.get("skill_registry_id") or 0),
                "version_no": int(version.get("version_no") or 0),
                "version_kind": str(version.get("version_kind") or "imported"),
                "candidate_build_id": int(version.get("candidate_build_id") or 0)
                or None,
                "content": content,
                "content_hash": str(version.get("content_hash") or ""),
                "base_version_id": base_version_id,
                "base_content": base_content,
                "content_diff": _class_commentary_skill_content_diff(
                    base_content,
                    content,
                    base_version_no=int((base_version or {}).get("version_no") or 0),
                    version_no=int(version.get("version_no") or 0),
                ),
                "evaluation": serialized_evaluation,
                "evaluation_snapshot": serialized_evaluation,
                "review_status": str(version.get("review_status") or "not_required"),
                "is_active": int(version.get("id") or 0)
                == int(active_version_id),
                "is_stale": bool(version.get("is_stale")),
                "stale_reason": stale_reason,
                "effective_task_count": int(
                    (safe_build or {}).get("effective_task_count") or 0
                ),
                "supporting_task_count": int(
                    (safe_build or {}).get("supporting_task_count") or 0
                ),
                "frozen_revision_count": len(frozen_revision_ids),
                "frozen_evidence_count": len(frozen_evidence_ids),
                "frozen_revision_ids": frozen_revision_ids,
                "frozen_evidence_ids": frozen_evidence_ids,
                "candidate_build": safe_build,
                "created_at": str(version.get("created_at") or ""),
                "reviewed_at": str(version.get("reviewed_at") or ""),
            }
        )
    return serialized


def _serialize_class_commentary_skill_activation_event_for_response(
    event: dict,
) -> dict:
    return {
        "id": int(event.get("id") or 0),
        "from_version_id": int(event.get("from_version_id") or 0) or None,
        "to_version_id": int(event.get("to_version_id") or 0),
        "active_version_id": int(event.get("active_version_id") or 0) or None,
        "current_active_version_id": int(
            event.get("current_active_version_id") or 0
        )
        or None,
        "reason": str(event.get("reason") or ""),
        "created_at": str(event.get("created_at") or ""),
    }


def _serialize_class_commentary_generation_result(task: dict, generation: dict) -> dict:
    task_payload = _serialize_class_commentary_task_for_response(
        task,
        include_private=True,
    )
    generation_payload = _serialize_class_commentary_generation_for_response(generation)
    payload = {
        **task_payload,
        **generation_payload,
        "task": task_payload,
        "generation": generation_payload,
        "task_status": task_payload["status"],
        "generation_status": generation_payload["status"],
    }
    return payload


_DASHBOARD_PENDING_REVIEW_STATUSES = {"pending", "queued", "processing", "transcribing", "generating"}
_DASHBOARD_TERMINAL_CONSULTATION_STAGES = {"成功进班", "试听失败", "咨询结束"}


def _dashboard_can_open_page(user: dict, page: str) -> bool:
    if page in {"dashboard", "settings"}:
        return True
    visible_pages = user.get("visible_pages")
    if not isinstance(visible_pages, list):
        return True
    return page in visible_pages


def _dashboard_parse_datetime(value: object) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.replace(" ", "T")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _dashboard_item_datetime(item: dict, *field_names: str) -> datetime:
    for field_name in field_names:
        parsed = _dashboard_parse_datetime(item.get(field_name))
        if parsed is not None:
            return parsed
    return datetime.fromtimestamp(0)


def _dashboard_sort_desc(items: list[dict], *field_names: str) -> list[dict]:
    return sorted(
        items,
        key=lambda item: (_dashboard_item_datetime(item, *field_names), int(item.get("id") or 0)),
        reverse=True,
    )


def _dashboard_get_today_classes(user: dict) -> list[dict]:
    role = str(user.get("role") or "")
    if role in {"super_owner", "owner", "admin"}:
        return list_classes_for_actor(user)
    return _filter_classes_for_user(user, list_classes())


def _dashboard_get_lessons(user: dict) -> list[dict]:
    lessons = list_lessons_for_actor(user)
    return _dashboard_sort_desc(
        _serialize_lessons_for_response(_filter_lessons_for_user(user, lessons)),
        "created_at",
        "date",
    )


def _dashboard_get_open_consultations(user: dict) -> list[dict]:
    consultations = list_consultations_for_actor(user, query="", search_mode="fuzzy")
    return [
        item
        for item in consultations
        if isinstance(item, dict)
        and str(item.get("flow_stage") or "").strip() not in _DASHBOARD_TERMINAL_CONSULTATION_STAGES
    ]


def _dashboard_get_today_schedules(user: dict, today_iso: str) -> list[dict]:
    items = list_course_calendar_schedules_for_actor(
        user,
        start_date=today_iso,
        end_date=today_iso,
    )
    return _dashboard_sort_desc(items, "created_at", "date")


def _dashboard_get_week_start_iso(today_value: date) -> str:
    return (today_value - timedelta(days=today_value.weekday())).isoformat()


def _dashboard_review_state(lesson: dict) -> str:
    status = str(lesson.get("record_status") or "").strip()
    if status in _DASHBOARD_PENDING_REVIEW_STATUSES:
        return "pending"
    if status in {"failed", "expired"}:
        return "failed"
    if str(lesson.get("pdf_path") or "").strip():
        return "ready"
    if status == "ready":
        return "missing-output"
    return "empty"


def _dashboard_review_status_label(lesson: dict) -> str:
    status = str(lesson.get("record_status") or "").strip()
    if status == "transcribing":
        return "转写中"
    if status == "generating":
        return "生成中"
    if status in {"pending", "queued", "processing"}:
        return "排队中"
    if status in {"failed", "expired"}:
        return "失败"
    if _dashboard_review_state(lesson) == "ready":
        return "已完成"
    return "待处理"


def _dashboard_time_label(schedule: dict) -> str:
    raw = str(schedule.get("time_block") or "").strip()
    if "-" in raw:
        return raw.split("-", 1)[0].strip()
    return raw or "--:--"


def _dashboard_class_name(value: object, fallback: str = "未命名班级") -> str:
    text = str(value or "").strip()
    return text or fallback


def _dashboard_lesson_title(lesson: dict, class_name_by_id: dict[int, str]) -> str:
    class_name = class_name_by_id.get(int(lesson.get("class_id") or 0), "")
    topic = str(lesson.get("topic") or "").strip()
    subject = str(lesson.get("subject") or "").strip()
    if class_name and topic:
        return f"{class_name} · {topic}"
    if class_name and subject:
        return f"{class_name} · {subject}"
    return topic or class_name or subject or f"复习资料 #{lesson.get('id')}"


def _dashboard_lesson_meta(lesson: dict, class_name_by_id: dict[int, str]) -> str:
    lesson_date = str(lesson.get("date") or "").strip()
    class_name = class_name_by_id.get(int(lesson.get("class_id") or 0), "")
    parts = [part for part in (lesson_date, class_name) if part]
    return " · ".join(parts) or f"记录 #{lesson.get('id')}"


def _dashboard_schedule_detail(schedule: dict) -> str:
    teacher_name = str(schedule.get("teacher_name") or "").strip()
    subject = str(schedule.get("subject") or "").strip()
    parts = [part for part in (teacher_name, subject) if part]
    return " · ".join(parts) or "查看课程安排"


def _dashboard_build_member_payload(user: dict) -> dict:
    today_value = date.today()
    today_iso = today_value.isoformat()
    week_start_iso = _dashboard_get_week_start_iso(today_value)

    classes = _dashboard_get_today_classes(user)
    class_name_by_id = {
        int(item.get("id") or 0): _dashboard_class_name(item.get("name"))
        for item in classes
        if int(item.get("id") or 0) > 0
    }
    lessons = _dashboard_get_lessons(user)
    open_consultations = _dashboard_get_open_consultations(user)
    today_schedules = _dashboard_get_today_schedules(user, today_iso)
    pending_lessons = [
        lesson
        for lesson in lessons
        if _dashboard_review_state(lesson) in {"pending", "failed", "missing-output"}
    ]
    ready_lessons = [lesson for lesson in lessons if _dashboard_review_state(lesson) == "ready"]
    week_ready_lessons = [
        lesson
        for lesson in ready_lessons
        if week_start_iso <= str(lesson.get("created_at") or "")[:10] <= today_iso
    ]

    today_queue: list[dict] = []
    for lesson in pending_lessons[:2]:
        today_queue.append(
            {
                "page": "review-generation",
                "title": _dashboard_lesson_title(lesson, class_name_by_id),
                "meta": _dashboard_lesson_meta(lesson, class_name_by_id),
                "status": _dashboard_review_status_label(lesson),
                "action": "进入",
            }
        )
    if open_consultations and _dashboard_can_open_page(user, "consultation") and len(today_queue) < 3:
        earliest = min(open_consultations, key=lambda item: str(item.get("date") or "9999-12-31"))
        today_queue.append(
            {
                "page": "consultation",
                "title": f"待跟进咨询 {len(open_consultations)} 条",
                "meta": f"{str(earliest.get('date') or '').strip() or today_iso} 起有咨询待处理",
                "status": "待跟进",
                "action": "进入",
            }
        )
    if today_schedules and _dashboard_can_open_page(user, "calendar") and len(today_queue) < 3:
        first_schedule = today_schedules[0]
        today_queue.append(
            {
                "page": "calendar",
                "title": f"今天排课 {len(today_schedules)} 节",
                "meta": _dashboard_class_name(first_schedule.get("class_name")),
                "status": "已排课",
                "action": "查看",
            }
        )

    recent_outputs = [
        {
            "page": "review-generation",
            "title": _dashboard_lesson_title(lesson, class_name_by_id),
            "meta": _dashboard_lesson_meta(lesson, class_name_by_id),
            "status": _dashboard_review_status_label(lesson),
        }
        for lesson in [item for item in lessons if _dashboard_review_state(item) != "empty"][:4]
    ]

    weekly_stats = [
        {"label": "本周资料", "value": str(len(week_ready_lessons)), "note": "本周生成完成"},
        {"label": "待处理复习", "value": str(len(pending_lessons)), "note": "含转写中和失败记录"},
        {"label": "待跟进咨询", "value": str(len(open_consultations)), "note": "当前未结束咨询"},
    ]

    schedule = [
        {
            "time": _dashboard_time_label(item),
            "title": _dashboard_class_name(item.get("class_name")),
            "detail": _dashboard_schedule_detail(item),
            "page": "calendar",
            "action": "查看日历",
        }
        for item in today_schedules[:4]
        if _dashboard_can_open_page(user, "calendar")
    ]

    return {
        "todayQueue": today_queue,
        "recentOutputs": recent_outputs,
        "weeklyStats": weekly_stats,
        "schedule": schedule,
    }


def _dashboard_build_organization_payload(user: dict) -> dict:
    today_value = date.today()
    today_iso = today_value.isoformat()
    week_start_iso = _dashboard_get_week_start_iso(today_value)
    can_open_accounts = _dashboard_can_open_page(user, "accounts")
    can_open_credit = _dashboard_can_open_page(user, "credit")

    classes = _dashboard_get_today_classes(user)
    class_name_by_id = {
        int(item.get("id") or 0): _dashboard_class_name(item.get("name"))
        for item in classes
        if int(item.get("id") or 0) > 0
    }
    lessons = _dashboard_get_lessons(user)
    open_consultations = _dashboard_get_open_consultations(user)
    today_schedules = _dashboard_get_today_schedules(user, today_iso)
    pending_lessons = [
        lesson
        for lesson in lessons
        if _dashboard_review_state(lesson) in {"pending", "failed", "missing-output"}
    ]
    week_ready_lessons = [
        lesson
        for lesson in lessons
        if _dashboard_review_state(lesson) == "ready"
        and week_start_iso <= str(lesson.get("created_at") or "")[:10] <= today_iso
    ]
    pending_registrations = list_registration_requests_for_actor(user, "pending") if can_open_accounts else []
    credit_overview = get_credit_overview(int(user["organization_id"])) if can_open_credit else None
    credit_balance = int(credit_overview.get("credit_balance") or 0) if isinstance(credit_overview, dict) else None

    pending_items: list[dict] = []
    if pending_registrations:
        pending_items.append(
            {
                "page": "accounts",
                "title": f"待审批账号 {len(pending_registrations)} 条",
                "meta": "新成员申请还没处理",
                "status": "待审批",
                "action": "进入",
            }
        )
    if pending_lessons:
        pending_items.append(
            {
                "page": "review-generation",
                "title": f"待处理复习资料 {len(pending_lessons)} 份",
                "meta": "包含转写中、生成中和失败记录",
                "status": "待处理",
                "action": "进入",
            }
        )
    if credit_balance is not None and can_open_credit and credit_balance <= 20:
        pending_items.append(
            {
                "page": "credit",
                "title": f"积分余额 {credit_balance}",
                "meta": "额度较低，可能影响后续 AI 生成。",
                "status": "低余额",
                "action": "查看",
            }
        )
    if open_consultations and _dashboard_can_open_page(user, "consultation"):
        pending_items.append(
            {
                "page": "consultation",
                "title": f"待跟进咨询 {len(open_consultations)} 条",
                "meta": "按日期顺序继续处理",
                "status": "待跟进",
                "action": "进入",
            }
        )
    if today_schedules:
        target_page = "calendar" if _dashboard_can_open_page(user, "calendar") else "classes"
        pending_items.append(
            {
                "page": target_page,
                "title": f"今天排课 {len(today_schedules)} 节",
                "meta": "查看今天班级安排",
                "status": "已排课",
                "action": "查看",
            }
        )

    pending_by_class_id = {
        int(lesson.get("class_id") or 0): lesson
        for lesson in pending_lessons
        if int(lesson.get("class_id") or 0) > 0
    }
    class_rows = []
    for schedule in today_schedules[:6]:
        class_id = int(schedule.get("class_id") or 0)
        linked_lesson = pending_by_class_id.get(class_id)
        if linked_lesson is not None:
            row_page = "review-generation"
            row_status = _dashboard_review_status_label(linked_lesson)
        else:
            row_page = "calendar" if _dashboard_can_open_page(user, "calendar") else "classes"
            row_status = "已排课"
        class_rows.append(
            {
                "name": _dashboard_class_name(schedule.get("class_name"), fallback=class_name_by_id.get(class_id, "未命名班级")),
                "schedule": _dashboard_time_label(schedule),
                "teacher": str(schedule.get("teacher_name") or "").strip() or "未分配",
                "status": row_status,
                "page": row_page,
            }
        )

    stats = [
        {"label": "今日排课", "value": str(len(today_schedules)), "note": "今天课程安排"},
        {"label": "待处理复习", "value": str(len(pending_lessons)), "note": "待完成资料记录"},
        {"label": "待跟进咨询", "value": str(len(open_consultations)), "note": "当前未结束咨询"},
        {"label": "本周资料", "value": str(len(week_ready_lessons)), "note": "本周已完成资料"},
        (
            {
                "label": "积分余额",
                "value": str(credit_balance),
                "note": "当前机构可用额度",
            }
            if credit_balance is not None
            else {
                "label": "待审批账号" if can_open_accounts else "本周资料",
                "value": str(len(pending_registrations) if can_open_accounts else len(week_ready_lessons)),
                "note": "机构成员申请" if can_open_accounts else "本周已完成资料",
            }
        ),
    ]

    return {
        "pendingItems": pending_items[:4],
        "stats": stats,
        "classRows": class_rows,
    }


def _dashboard_build_platform_payload(user: dict) -> dict:
    today_value = date.today()
    today_iso = today_value.isoformat()
    week_start_iso = _dashboard_get_week_start_iso(today_value)

    organizations = list_organizations()
    lessons = _dashboard_get_lessons(user)
    users = list_users_for_actor(user)
    open_consultations = _dashboard_get_open_consultations(user)
    pending_registration_requests = list_registration_requests_for_actor(user, "pending")
    pending_organization_requests = list_organization_requests()

    members_by_org: dict[int, int] = {}
    for item in users:
        organization_id = int(item.get("organization_id") or 0)
        if organization_id <= 0:
            continue
        members_by_org[organization_id] = members_by_org.get(organization_id, 0) + 1

    today_output_by_org: dict[int, int] = {}
    week_output_by_org: dict[int, int] = {}
    for lesson in lessons:
        organization_id = int(lesson.get("organization_id") or 0)
        if organization_id <= 0 or _dashboard_review_state(lesson) != "ready":
            continue
        created_date = str(lesson.get("created_at") or "")[:10]
        if created_date == today_iso:
            today_output_by_org[organization_id] = today_output_by_org.get(organization_id, 0) + 1
        if week_start_iso <= created_date <= today_iso:
            week_output_by_org[organization_id] = week_output_by_org.get(organization_id, 0) + 1

    pending_registration_by_org: dict[int, int] = {}
    for request_item in pending_registration_requests:
        organization_id = int(request_item.get("organization_id") or 0)
        if organization_id <= 0:
            continue
        pending_registration_by_org[organization_id] = pending_registration_by_org.get(organization_id, 0) + 1

    pending_consultations_by_org: dict[int, int] = {}
    for item in open_consultations:
        organization_id = int(item.get("organization_id") or 0)
        if organization_id <= 0:
            continue
        pending_consultations_by_org[organization_id] = pending_consultations_by_org.get(organization_id, 0) + 1

    low_credit_by_org: dict[int, int] = {}
    for organization in organizations:
        organization_id = int(organization.get("id") or 0)
        if organization_id <= 0:
            continue
        overview = get_credit_overview(organization_id)
        credit_balance = int(overview.get("credit_balance") or 0)
        if credit_balance <= 20:
            low_credit_by_org[organization_id] = credit_balance

    attention_items: list[dict] = []
    if pending_organization_requests:
        attention_items.append(
            {
                "organization": "机构开通申请",
                "issue": f"当前有 {len(pending_organization_requests)} 条新机构申请待处理。",
                "status": "待审批",
                "page": "accounts",
                "action": "进入",
            }
        )

    organizations_by_pending = sorted(
        organizations,
        key=lambda item: (
            pending_registration_by_org.get(int(item.get("id") or 0), 0),
            today_output_by_org.get(int(item.get("id") or 0), 0),
        ),
        reverse=True,
    )
    for organization in organizations_by_pending:
        organization_id = int(organization.get("id") or 0)
        pending_count = pending_registration_by_org.get(organization_id, 0)
        if pending_count <= 0:
            continue
        attention_items.append(
            {
                "organization": _dashboard_class_name(organization.get("name"), fallback="机构"),
                "issue": f"有 {pending_count} 条成员账号申请待处理。",
                "status": "待审批",
                "page": "accounts",
                "action": "进入",
            }
        )
        if len(attention_items) >= 4:
            break

    if len(attention_items) < 4:
        consultation_organizations = sorted(
            organizations,
            key=lambda item: pending_consultations_by_org.get(int(item.get("id") or 0), 0),
            reverse=True,
        )
        for organization in consultation_organizations:
            organization_id = int(organization.get("id") or 0)
            consultation_count = pending_consultations_by_org.get(organization_id, 0)
            if consultation_count <= 0:
                continue
            attention_items.append(
                {
                    "organization": _dashboard_class_name(organization.get("name"), fallback="机构"),
                    "issue": f"有 {consultation_count} 条咨询待继续跟进。",
                    "status": "待咨询",
                    "page": "consultation",
                    "action": "进入",
                }
            )
            if len(attention_items) >= 4:
                break

    if len(attention_items) < 4:
        low_credit_organizations = sorted(
            organizations,
            key=lambda item: low_credit_by_org.get(int(item.get("id") or 0), 999999),
        )
        for organization in low_credit_organizations:
            organization_id = int(organization.get("id") or 0)
            credit_balance = low_credit_by_org.get(organization_id)
            if credit_balance is None:
                continue
            attention_items.append(
                {
                    "organization": _dashboard_class_name(organization.get("name"), fallback="机构"),
                    "issue": f"当前积分余额 {credit_balance}，建议尽快处理。",
                    "status": "低余额",
                    "page": "credit",
                    "action": "查看",
                }
            )
            if len(attention_items) >= 4:
                break

    if len(attention_items) < 4:
        quiet_organizations = [
            organization
            for organization in organizations
            if week_output_by_org.get(int(organization.get("id") or 0), 0) == 0
            and int(organization.get("member_count") or 0) > 0
        ]
        for organization in quiet_organizations[: 4 - len(attention_items)]:
            attention_items.append(
                {
                    "organization": _dashboard_class_name(organization.get("name"), fallback="机构"),
                    "issue": "最近 7 天没有新增复习资料。",
                    "status": "需查看",
                    "page": "review-generation",
                    "action": "查看",
                }
            )

    total_pending_approvals = len(pending_organization_requests) + len(pending_registration_requests)
    priority_items = []
    if total_pending_approvals:
        priority_items.append(
            {
                "title": "先处理审批",
                "detail": f"当前共有 {total_pending_approvals} 条申请待处理。",
                "page": "accounts",
            }
        )
    if attention_items:
        primary_attention = attention_items[0]
        priority_items.append(
            {
                "title": f"再看 {primary_attention['organization']}",
                "detail": str(primary_attention.get("issue") or ""),
                "page": primary_attention["page"],
            }
        )
    priority_items.append(
        {
            "title": "最后看机构班级",
            "detail": f"当前共有 {sum(int(item.get('class_count') or 0) for item in organizations)} 个班级。",
            "page": "classes",
        }
    )

    stats = [
        {"label": "机构数", "value": str(len(organizations)), "note": "当前在库机构"},
        {"label": "待审批", "value": str(total_pending_approvals), "note": "机构申请和成员申请"},
        {"label": "待咨询", "value": str(sum(pending_consultations_by_org.values())), "note": "当前未结束咨询"},
        {"label": "低余额机构", "value": str(len(low_credit_by_org)), "note": "余额 20 及以下"},
    ]

    organization_rows = []
    for organization in organizations_by_pending:
        organization_id = int(organization.get("id") or 0)
        pending_count = pending_registration_by_org.get(organization_id, 0)
        today_output_count = today_output_by_org.get(organization_id, 0)
        week_output_count = week_output_by_org.get(organization_id, 0)
        consultation_count = pending_consultations_by_org.get(organization_id, 0)
        credit_balance = low_credit_by_org.get(organization_id)
        if pending_count > 0:
            status = f"待审批 {pending_count}"
        elif consultation_count > 0:
            status = f"待咨询 {consultation_count}"
        elif credit_balance is not None:
            status = f"余额 {credit_balance}"
        elif today_output_count > 0:
            status = f"今日资料 {today_output_count}"
        else:
            status = f"本周资料 {week_output_count}"
        organization_rows.append(
            {
                "organization": _dashboard_class_name(organization.get("name"), fallback="机构"),
                "teachers": str(members_by_org.get(organization_id, int(organization.get("member_count") or 0))),
                "outputs": str(today_output_count),
                "approvals": str(pending_count),
                "status": status,
                "page": "accounts" if pending_count > 0 else ("consultation" if consultation_count > 0 else ("credit" if credit_balance is not None else ("review-generation" if today_output_count > 0 or week_output_count > 0 else "classes"))),
            }
        )

    return {
        "attentionItems": attention_items,
        "stats": stats,
        "organizationRows": organization_rows[:8],
        "priorityItems": priority_items[:3],
    }


def _serialize_wrong_question_practice_sheet_for_response(sheet: object) -> Optional[dict]:
    if not isinstance(sheet, dict):
        return None
    serialized = dict(sheet)
    if serialized.get("pdf_path"):
        serialized["pdf_url"] = f"/api/wrong-question-practice-sheets/{serialized['id']}/pdf"
        serialized["download_url"] = f"/api/wrong-question-practice-sheets/{serialized['id']}/pdf/download"
    return serialized


def _serialize_wrong_question_practice_pack_job_for_response(job: object) -> Optional[dict]:
    if not isinstance(job, dict):
        return None
    serialized = dict(job)
    serialized["download_url"] = ""
    zip_path_value = str(serialized.get("zip_path") or "").strip()
    zip_path = Path(zip_path_value) if zip_path_value else None
    if zip_path is not None and zip_path.is_file() and str(serialized.get("status") or "") in {"ready", "partial_failed"}:
        serialized["download_url"] = f"/api/wrong-question-practice-packs/{serialized['id']}/download"
    return serialized


def _serialize_wrong_question_ingestion_run_link_for_response(run: object) -> Optional[dict]:
    if not isinstance(run, dict):
        return None
    serialized = {
        "id": str(run.get("id") or "").strip(),
        "source": str(run.get("source") or "").strip(),
        "status": str(run.get("status") or "").strip(),
        "current_step": str(run.get("current_step") or "").strip(),
        "chat_session_id": str(run.get("chat_session_id") or "").strip(),
    }
    serialized["detail_url"] = (
        f"/api/wrong-question-ingestions/{serialized['id']}" if serialized["id"] else ""
    )
    return serialized


def _serialize_wrong_question_chat_session_link_for_response(session: object) -> Optional[dict]:
    if not isinstance(session, dict):
        return None
    serialized = {
        "id": str(session.get("id") or "").strip(),
        "status": str(session.get("status") or "").strip(),
        "current_stage": str(session.get("current_stage") or "").strip(),
        "summary_text": str(session.get("summary_text") or "").strip(),
        "ingestion_run_id": str(session.get("ingestion_run_id") or "").strip(),
    }
    normalized_session_id = serialized["id"]
    serialized["detail_url"] = (
        f"/api/wrong-question-chats/{normalized_session_id}" if normalized_session_id else ""
    )
    serialized["stream_url"] = (
        f"/api/wrong-question-chats/{normalized_session_id}/stream" if normalized_session_id else ""
    )
    return serialized


def _serialize_wrong_question_record_for_response(
    record: object,
    *,
    include_archive_context: bool = False,
) -> Optional[dict]:
    if not isinstance(record, dict):
        return None
    serialized = dict(record)
    record_id = str(serialized.get("id") or "").strip()
    ingestion_run_id = str(serialized.get("ingestion_run_id") or "").strip()
    chat_session_id = str(serialized.get("chat_session_id") or "").strip()
    serialized["detail_url"] = f"/api/wrong-questions/{record_id}" if record_id else ""
    serialized["archive_context"] = {
        "source": str(serialized.get("source") or "").strip(),
        "ingestion_run_id": ingestion_run_id,
        "ingestion_run_url": (
            f"/api/wrong-question-ingestions/{ingestion_run_id}" if ingestion_run_id else ""
        ),
        "chat_session_id": chat_session_id,
        "chat_session_url": f"/api/wrong-question-chats/{chat_session_id}" if chat_session_id else "",
    }
    serialized["generation_metadata"] = _merge_wrong_question_generation_metadata(
        serialized.get("generation_metadata"),
        serialized.get("generation_metadata_json"),
    )
    if include_archive_context:
        serialized["linked_ingestion_run"] = _serialize_wrong_question_ingestion_run_for_response(
            get_wrong_question_ingestion_run(ingestion_run_id) if ingestion_run_id else None
        )
        serialized["linked_chat_session"] = _serialize_wrong_question_chat_session_for_response(
            get_wrong_question_chat_session(chat_session_id) if chat_session_id else None
        )
    return serialized


def _serialize_wrong_question_records_for_response(records: object) -> list[dict]:
    if not isinstance(records, list):
        return []
    serialized_records = []
    for item in records:
        serialized = _serialize_wrong_question_record_for_response(item)
        if serialized is not None:
            serialized_records.append(serialized)
    return serialized_records


def _serialize_wrong_question_ingestion_run_for_response(run: object) -> Optional[dict]:
    if not isinstance(run, dict):
        return None
    serialized = dict(run)
    serialized["detail_url"] = (
        f"/api/wrong-question-ingestions/{serialized['id']}" if serialized.get("id") else ""
    )
    serialized["assets"] = list_wrong_question_assets(str(serialized.get("id") or ""))
    serialized["records"] = _serialize_wrong_question_records_for_response(
        list_wrong_question_submissions_for_ingestion_run(str(serialized.get("id") or ""))
    )
    return serialized


def _serialize_wrong_question_chat_session_for_response(session: object) -> Optional[dict]:
    if not isinstance(session, dict):
        return None
    serialized = dict(session)
    normalized_session_id = str(serialized.get("id") or "").strip()
    serialized["detail_url"] = f"/api/wrong-question-chats/{normalized_session_id}" if normalized_session_id else ""
    serialized["stream_url"] = (
        f"/api/wrong-question-chats/{normalized_session_id}/stream" if normalized_session_id else ""
    )
    serialized["messages"] = list_wrong_question_chat_messages(str(serialized.get("id") or ""))
    serialized["records"] = _serialize_wrong_question_records_for_response(
        list_wrong_question_submissions_for_chat_session(str(serialized.get("id") or ""))
    )
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


def _can_access_wrong_question_practice_pack_job(user: dict, job: object) -> bool:
    if user.get("role") == "super_owner":
        return True
    if not isinstance(job, dict):
        return False
    if user.get("role") in {"owner", "admin"}:
        return int(job.get("organization_id") or 0) == int(user.get("organization_id") or 0)
    return int(job.get("class_id") or 0) in set(get_user_class_ids(user["id"]))


def _can_access_wrong_question_chat_session(user: dict, session: object, owned_class_ids: Optional[Set[int]] = None) -> bool:
    if user.get("role") == "super_owner":
        return True
    if not isinstance(session, dict):
        return False
    if user.get("role") in {"owner", "admin"}:
        return int(session.get("organization_id") or 0) == int(user.get("organization_id") or 0)

    teacher_user_id = session.get("teacher_user_id")
    if isinstance(teacher_user_id, int) and teacher_user_id == user.get("id"):
        return True

    class_id = session.get("class_id")
    if not isinstance(class_id, int):
        return False
    member_class_ids = owned_class_ids
    if member_class_ids is None:
        member_class_ids = set(get_user_class_ids(user["id"]))
    return class_id in member_class_ids


def _can_access_wrong_question_ingestion_run(user: dict, run: object, owned_class_ids: Optional[Set[int]] = None) -> bool:
    if user.get("role") == "super_owner":
        return True
    if not isinstance(run, dict):
        return False
    if user.get("role") in {"owner", "admin"}:
        return int(run.get("organization_id") or 0) == int(user.get("organization_id") or 0)

    teacher_user_id = run.get("teacher_user_id")
    if isinstance(teacher_user_id, int) and teacher_user_id == user.get("id"):
        return True

    class_id = run.get("class_id")
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


def _get_accessible_class_commentary_task_or_error(user: dict, task_id: int):
    task = get_class_commentary_task(task_id)
    if not task:
        return None, (jsonify({"error": "not found"}), 404)
    _, error = _get_accessible_class_or_error(user, int(task["class_id"]))
    if error:
        return None, error
    return task, None


def _get_owned_class_commentary_task_or_error(user: dict, task_id: int):
    task, error = _get_accessible_class_commentary_task_or_error(user, task_id)
    if error:
        return None, error
    if int(task["organization_id"]) != int(user.get("organization_id") or 0):
        return None, (jsonify({"error": "forbidden"}), 403)
    if int(task["teacher_user_id"]) != int(user.get("id") or 0):
        return None, (jsonify({"error": "forbidden"}), 403)
    return task, None


def _get_readable_class_commentary_task_or_error(user: dict, task_id: int):
    task, error = _get_accessible_class_commentary_task_or_error(user, task_id)
    if error:
        return None, error
    if int(task["organization_id"]) != int(user.get("organization_id") or 0):
        return None, (jsonify({"error": "forbidden"}), 403)
    if (
        int(task["teacher_user_id"]) != int(user.get("id") or 0)
        and user.get("role") != "super_owner"
    ):
        return None, (jsonify({"error": "forbidden"}), 403)
    return task, None


def _get_owned_class_commentary_revision_or_error(user: dict, revision_id: int):
    revision = get_class_commentary_revision(revision_id)
    if not revision:
        return None, None, (jsonify({"error": "not found"}), 404)
    task, error = _get_owned_class_commentary_task_or_error(
        user,
        int(revision["task_id"]),
    )
    if error:
        return None, None, error
    if int(revision["teacher_user_id"]) != int(user.get("id") or 0):
        return None, None, (jsonify({"error": "forbidden"}), 403)
    return revision, task, None


def _sync_configured_class_commentary_skills(user: dict) -> list[dict]:
    organization_id = int(user.get("organization_id") or 0)
    actor_user_id = int(user.get("id") or 0)
    skill_dir = str(get_runtime_config().get("colleague_skill_dir") or "").strip()
    if not skill_dir:
        return list_class_commentary_skills_for_organization(organization_id)
    registered_by_id = {
        str(item["skill_id"]): item
        for item in list_class_commentary_skills_for_organization(organization_id)
    }
    for item in list_colleague_skills(skill_dir):
        skill_id = str(item.get("id") or "").strip()
        if not skill_id:
            continue
        package = load_colleague_skill(skill_dir, skill_id)
        registered = registered_by_id.get(skill_id)
        if registered:
            if (
                str(registered.get("source_type") or "")
                != "external_skill_package"
                or str(registered.get("version_kind") or "") != "imported"
                or str(registered.get("content_hash") or "")
                == hashlib.sha256(
                    str(package.get("content") or "").encode("utf-8")
                ).hexdigest()
            ):
                continue
            try:
                refreshed = refresh_class_commentary_skill_manifest(
                    organization_id=organization_id,
                    skill_id=skill_id,
                    actor_user_id=actor_user_id,
                    activation_request_id=(
                        f"manifest-refresh:{organization_id}:{skill_id}:"
                        f"{hashlib.sha256(str(package.get('content') or '').encode('utf-8')).hexdigest()}"
                    ),
                    expected_active_version_id=int(registered["active_version_id"]),
                )
            except (
                ClassCommentarySkillActivationRequestConflict,
                ClassCommentarySkillImportConflict,
                ClassCommentarySkillVersionConflict,
            ):
                continue
            registered_by_id[skill_id] = dict(refreshed["skill"])
            continue
        try:
            imported = import_class_commentary_skill_manifest(
                organization_id=organization_id,
                skill_id=skill_id,
                actor_user_id=actor_user_id,
                source_path=str(package["path"]),
            )
        except ClassCommentarySkillImportConflict:
            pass
        else:
            registered_by_id[skill_id] = imported
    return list_class_commentary_skills_for_organization(organization_id)


def _get_accessible_class_commentary_skill_or_error(user: dict, skill_id: str):
    skill = get_class_commentary_skill_for_organization(
        int(user.get("organization_id") or 0),
        str(skill_id or "").strip(),
    )
    if not skill:
        return None, (jsonify({"error": "not found"}), 404)
    return skill, None


def _list_class_commentary_skill_candidate_builds_for_response(
    *,
    skill: dict,
    user: dict,
) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id FROM class_commentary_skill_candidate_builds
            WHERE organization_id=? AND skill_registry_id=?
            ORDER BY id DESC
            """,
            (user["organization_id"], skill["registry_id"]),
        ).fetchall()
    builds = []
    for row in rows:
        build = get_class_commentary_skill_candidate_build(
            int(row["id"]),
            organization_id=int(user["organization_id"]),
            actor_user_id=int(user["id"]),
        )
        if build:
            builds.append(
                _serialize_class_commentary_skill_candidate_build_for_response(build)
            )
    return builds


def _class_commentary_skill_evolution_envelope(
    *,
    skill: dict,
    user: dict,
) -> dict:
    versions = list_class_commentary_skill_versions(
        organization_id=int(user["organization_id"]),
        skill_id=str(skill["skill_id"]),
        actor_user_id=int(user["id"]),
    )
    active_version_id = int(skill.get("active_version_id") or 0)
    serialized_versions = _serialize_class_commentary_skill_versions_for_response(
        versions,
        active_version_id=active_version_id,
    )
    eligibility = get_class_commentary_skill_candidate_eligibility(
        organization_id=int(user["organization_id"]),
        skill_id=str(skill["skill_id"]),
        actor_user_id=int(user["id"]),
    )
    if bool(eligibility.get("eligible")):
        eligibility_reason = ""
    else:
        eligibility_reason = "insufficient_effective_tasks"
    return {
        "skill": _serialize_class_commentary_skill_for_evolution(skill),
        "versions": serialized_versions,
        "candidate_builds": _list_class_commentary_skill_candidate_builds_for_response(
            skill=skill,
            user=user,
        ),
        "eligibility": {
            "eligible": bool(eligibility.get("eligible")),
            "reason": eligibility_reason,
            "effective_task_count": int(
                eligibility.get("effective_task_count") or 0
            ),
            "supporting_task_count": int(
                eligibility.get("supporting_task_count") or 0
            ),
            "min_effective_tasks": int(
                eligibility.get("min_effective_tasks") or 0
            ),
            "min_supporting_tasks": int(
                eligibility.get("min_support_tasks") or 0
            ),
        },
    }


def _class_commentary_skill_activation_envelope(
    *,
    skill_id: str,
    version_id: int,
    activation_event: dict,
    user: dict,
) -> dict:
    skill = get_class_commentary_skill_for_organization(
        int(user["organization_id"]),
        skill_id,
    )
    if not skill:
        raise LookupError("class commentary skill not found")
    versions = list_class_commentary_skill_versions(
        organization_id=int(user["organization_id"]),
        skill_id=skill_id,
        actor_user_id=int(user["id"]),
    )
    serialized_versions = _serialize_class_commentary_skill_versions_for_response(
        versions,
        active_version_id=int(skill.get("active_version_id") or 0),
    )
    version = next(
        (item for item in serialized_versions if int(item["id"]) == int(version_id)),
        None,
    )
    if not version:
        raise LookupError("class commentary skill version not found")
    return {
        "skill": _serialize_class_commentary_skill_for_evolution(skill),
        "version": version,
        "activation_event": _serialize_class_commentary_skill_activation_event_for_response(
            activation_event
        ),
    }


def _class_commentary_skill_evolution_error_response(exc: Exception):
    if isinstance(exc, ClassCommentarySkillCandidateRequestConflict):
        return jsonify({"error": "candidate_request_conflict"}), 409
    if isinstance(exc, ClassCommentarySkillActivationRequestConflict):
        return jsonify({"error": "activation_request_conflict"}), 409
    if isinstance(exc, ClassCommentarySkillCandidateNotReady):
        return jsonify(
            {
                "error": exc.code,
                "effective_task_count": exc.effective_task_count,
                "supporting_task_count": exc.supporting_task_count,
                "min_effective_tasks": exc.min_effective_tasks,
                "min_supporting_tasks": exc.min_support_tasks,
            }
        ), 409
    if isinstance(exc, ClassCommentarySkillCandidateStale):
        return jsonify(
            {
                "error": exc.code,
                "stale_reason": _class_commentary_safe_skill_stale_reason(
                    exc.reason
                ),
            }
        ), 409
    if isinstance(exc, ClassCommentarySkillVersionConflict):
        return jsonify({"error": exc.code}), 409
    if isinstance(exc, (LookupError, PermissionError)):
        return jsonify({"error": "not found"}), 404
    return jsonify({"error": "invalid_skill_evolution_state"}), 409


def _require_class_commentary_skill_evolution_capability():
    capabilities = _class_commentary_memory_capabilities()
    if not bool(capabilities.get("skill_evolution_enabled")):
        return jsonify({"error": "skill_evolution_disabled"}), 409
    return None


def _class_commentary_skill_change_request_payload():
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return None, None, payload_error
    request_id = str((data or {}).get("request_id") or "").strip()
    if not request_id:
        return None, None, (jsonify({"error": "request_id is required"}), 400)
    raw_expected_version_id = (data or {}).get("expected_active_version_id")
    if isinstance(raw_expected_version_id, bool):
        return None, None, (
            jsonify({"error": "expected_active_version_id must be a positive integer"}),
            400,
        )
    try:
        expected_version_id = int(raw_expected_version_id)
    except (TypeError, ValueError):
        expected_version_id = 0
    if expected_version_id <= 0:
        return None, None, (
            jsonify({"error": "expected_active_version_id must be a positive integer"}),
            400,
        )
    return request_id, expected_version_id, None


def _parse_class_commentary_attending_student_ids(data: dict):
    raw_student_ids = data.get("attending_student_ids")
    if raw_student_ids is None:
        return None, None
    if not isinstance(raw_student_ids, list):
        return None, (jsonify({"error": "attending_student_ids must be a list"}), 400)

    selected_ids: set[int] = set()
    for raw_student_id in raw_student_ids:
        if isinstance(raw_student_id, bool):
            return None, (jsonify({"error": "attending_student_ids must contain student ids"}), 400)
        try:
            student_id = int(raw_student_id)
        except (TypeError, ValueError):
            return None, (jsonify({"error": "attending_student_ids must contain student ids"}), 400)
        if student_id <= 0:
            return None, (jsonify({"error": "attending_student_ids must contain student ids"}), 400)
        selected_ids.add(student_id)

    if not selected_ids:
        return None, (jsonify({"error": "attending_student_ids is required"}), 400)
    return selected_ids, None


def _filter_class_commentary_students_by_attendance(class_students: list[dict], data: dict):
    selected_ids, selected_ids_error = _parse_class_commentary_attending_student_ids(data)
    if selected_ids_error:
        return [], selected_ids_error
    if selected_ids is None:
        return class_students, None

    class_student_ids = {int(student.get("id") or 0) for student in class_students}
    if not selected_ids.issubset(class_student_ids):
        return [], (jsonify({"error": "attending_student_ids must belong to class"}), 400)
    return [
        student
        for student in class_students
        if int(student.get("id") or 0) in selected_ids
    ], None


def _member_can_read_student_profile(user: dict, student_id: int) -> bool:
    if user.get("role") != "member":
        return True
    for class_id in get_user_class_ids(user["id"]):
        if any(student.get("id") == student_id for student in list_students_for_class(class_id)):
            return True
    return False


def _get_json_object_payload():
    if not request.is_json:
        return {}, None
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "request body must be a JSON object"}), 400)
    return data, None


def _create_wrong_question_assets_from_payload(run_id: str, assets_payload: object) -> list[dict]:
    if assets_payload is None:
        return []
    if not isinstance(assets_payload, list):
        raise ValueError("assets must be a list")
    created_assets: list[dict] = []
    for raw_asset in assets_payload:
        if not isinstance(raw_asset, dict):
            raise ValueError("assets must contain objects")
        created_assets.append(
            create_wrong_question_asset(
                ingestion_run_id=run_id,
                asset_role=str(raw_asset.get("asset_role") or raw_asset.get("role") or "").strip(),
                storage_path=str(raw_asset.get("storage_path") or "").strip(),
                file_url=str(raw_asset.get("file_url") or "").strip(),
                mime_type=str(raw_asset.get("mime_type") or "").strip(),
                page_number=int(raw_asset.get("page_number") or 0),
                width=int(raw_asset.get("width") or 0),
                height=int(raw_asset.get("height") or 0),
                metadata_json=raw_asset.get("metadata"),
            )
        )
    return created_assets


def _normalize_wrong_question_ingestion_record_payloads(submissions_payload: object) -> list[dict]:
    if not isinstance(submissions_payload, list) or not submissions_payload:
        raise ValueError("submissions must be a non-empty list")
    normalized_items: list[dict] = []
    for raw_item in submissions_payload:
        if not isinstance(raw_item, dict):
            raise ValueError("submissions must contain objects")
        normalized_items.append(raw_item)
    return normalized_items


_WRONG_QUESTION_CHAT_NEXT_STAGE = {
    "ask_why_wrong": "ask_unknown_step",
    "ask_unknown_step": "ask_help_mode",
    "ask_help_mode": "ready_to_archive",
    "ready_to_archive": "ready_to_archive",
}

_WRONG_QUESTION_CHAT_CONFIRMATION_REASON_LABELS = {
    "missing_image_asset": "缺少原始图片",
    "missing_question_text": "题目文本还不完整",
    "knowledge_tags_unconfirmed": "知识点还没确认",
    "student_confused_step": "学生卡点描述还不够清楚",
}

_WRONG_QUESTION_CHAT_ASSISTANT_PROMPTS = {
    "ask_why_wrong": "先一起复盘一下。你觉得这题错在哪里，是没读懂题、不会列式，还是算到一半卡住了？",
    "ask_unknown_step": "收到。具体是哪一步最不确定？是审题、列式、计算，还是某个知识点没想明白？",
    "ask_help_mode": "明白了。接下来你更希望我先给一点提示，还是先带你完整复盘一遍？",
    "ready_to_archive": "好，我会把这次错因、卡点和接下来的复习建议整理进错题库，后面我们可以继续追问这道题。",
}


def _wrong_question_chat_prompt_for_stage(stage: str) -> str:
    normalized_stage = (stage or "ask_why_wrong").strip() or "ask_why_wrong"
    return _WRONG_QUESTION_CHAT_ASSISTANT_PROMPTS.get(
        normalized_stage,
        _WRONG_QUESTION_CHAT_ASSISTANT_PROMPTS["ask_why_wrong"],
    )


def _load_wrong_question_chat_session_metadata(session: object) -> dict:
    if not isinstance(session, dict):
        return {}
    try:
        metadata = json.loads(str(session.get("metadata_json") or "{}"))
    except json.JSONDecodeError:
        metadata = {}
    return metadata if isinstance(metadata, dict) else {}


def _build_wrong_question_chat_rework_prompt(record: dict) -> str:
    return _build_wrong_question_chat_rework_prompt_for_stage(record, "ask_why_wrong", {})


def _build_wrong_question_chat_reflection_seed(record: dict) -> dict:
    if not isinstance(record, dict):
        return {}
    reflection_summary = record.get("reflection_summary")
    if not isinstance(reflection_summary, dict):
        reflection_summary = {}
    seed = {}
    why_wrong = str(
        reflection_summary.get("why_wrong")
        or record.get("child_raw_reason_text")
        or ""
    ).strip()
    unknown_step = str(
        reflection_summary.get("unknown_step")
        or record.get("child_reason_core_issue")
        or ""
    ).strip()
    help_preference = str(
        reflection_summary.get("help_preference")
        or record.get("child_reason_next_step")
        or ""
    ).strip()
    if why_wrong:
        seed["why_wrong"] = why_wrong
    if unknown_step:
        seed["unknown_step"] = unknown_step
    if help_preference:
        seed["help_preference"] = help_preference
    return seed


def _infer_wrong_question_chat_stage_from_reflection_seed(reflection_seed: dict) -> str:
    normalized_seed = reflection_seed if isinstance(reflection_seed, dict) else {}
    if not str(normalized_seed.get("why_wrong") or "").strip():
        return "ask_why_wrong"
    if not str(normalized_seed.get("unknown_step") or "").strip():
        return "ask_unknown_step"
    if not str(normalized_seed.get("help_preference") or "").strip():
        return "ask_help_mode"
    return "ask_why_wrong"


def _build_wrong_question_chat_rework_prompt_for_stage(record: dict, stage: str, reflection_seed: dict) -> str:
    reason_labels = [
        _WRONG_QUESTION_CHAT_CONFIRMATION_REASON_LABELS.get(reason, reason)
        for reason in (record.get("confirmation_reasons") or [])
        if str(reason or "").strip()
    ]
    reasons_text = f"老师刚把这道题退回补充，主要还想再确认：{'、'.join(reason_labels)}。" if reason_labels else "老师希望你再补充一下这道错题。"
    normalized_seed = reflection_seed if isinstance(reflection_seed, dict) else {}
    why_wrong = str(normalized_seed.get("why_wrong") or "").strip()
    unknown_step = str(normalized_seed.get("unknown_step") or "").strip()
    help_preference = str(normalized_seed.get("help_preference") or "").strip()
    if stage == "ask_unknown_step":
        if why_wrong:
            return (
                f"{reasons_text} 目前我们先保留你已经说明的错因：{why_wrong}。"
                "这次继续沿着同一条错题补充一下，你具体卡在了哪一步，或者哪个知识点还没有真正想明白？"
            )
        return f"{reasons_text} 你具体卡在了哪一步，或者哪个知识点还没有真正想明白？"
    if stage == "ask_help_mode":
        context_bits = []
        if why_wrong:
            context_bits.append(f"错因是“{why_wrong}”")
        if unknown_step:
            context_bits.append(f"卡点是“{unknown_step}”")
        if context_bits:
            return (
                f"{reasons_text} 现在我们已经补到 {'，'.join(context_bits)}。"
                "接下来你更希望我怎么帮你，是先给一点提示，还是先带你完整复盘一遍？"
            )
        return f"{reasons_text} 接下来你更希望我怎么帮你，是先给一点提示，还是先带你完整复盘一遍？"
    if why_wrong or unknown_step or help_preference:
        summary_bits = []
        if why_wrong:
            summary_bits.append(f"上次你提到错因是“{why_wrong}”")
        if unknown_step:
            summary_bits.append(f"卡点是“{unknown_step}”")
        if help_preference:
            summary_bits.append(f"希望的帮助方式是“{help_preference}”")
        return (
            f"{reasons_text} 我们先沿着同一条错题继续。{'，'.join(summary_bits)}。"
            "如果现在你想更准确地补充真正的错因，可以先从这里继续说。"
        )
    return f"{reasons_text} 我们先沿着同一条错题继续。你这次最想补清楚的错因或卡点是什么？"


def _load_wrong_question_chat_reflection_seed(session_metadata: dict) -> dict:
    if not isinstance(session_metadata, dict):
        return {}
    seed = session_metadata.get("reflection_seed")
    if not isinstance(seed, dict):
        return {}
    reflection = {}
    why_wrong = str(seed.get("why_wrong") or "").strip()
    unknown_step = str(seed.get("unknown_step") or "").strip()
    help_preference = str(seed.get("help_preference") or "").strip()
    if why_wrong:
        reflection["why_wrong"] = why_wrong
    if unknown_step:
        reflection["unknown_step"] = unknown_step
    if help_preference:
        reflection["help_preference"] = help_preference
    return reflection


def _collect_wrong_question_chat_reflection(messages: list[dict], reflection_seed: dict | None = None) -> dict:
    reflection = {
        "why_wrong": str((reflection_seed or {}).get("why_wrong") or "").strip(),
        "unknown_step": str((reflection_seed or {}).get("unknown_step") or "").strip(),
        "help_preference": str((reflection_seed or {}).get("help_preference") or "").strip(),
    }
    for item in messages:
        if not isinstance(item, dict) or str(item.get("role") or "") != "user":
            continue
        stage = str(item.get("stage") or "").strip()
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if stage == "ask_why_wrong":
            reflection["why_wrong"] = content
        elif stage == "ask_unknown_step":
            reflection["unknown_step"] = content
        elif stage == "ask_help_mode":
            reflection["help_preference"] = content
    return reflection


def _summarize_wrong_question_chat_reflection(reflection: dict) -> str:
    parts = []
    why_wrong = str(reflection.get("why_wrong") or "").strip()
    unknown_step = str(reflection.get("unknown_step") or "").strip()
    help_preference = str(reflection.get("help_preference") or "").strip()
    if why_wrong:
        parts.append(f"错因自述：{why_wrong}")
    if unknown_step:
        parts.append(f"卡点：{unknown_step}")
    if help_preference:
        parts.append(f"期望支持：{help_preference}")
    return "；".join(parts)


def _infer_wrong_question_chat_reflection_mode(session_metadata: dict) -> str:
    if not isinstance(session_metadata, dict):
        return "archive_reflection"
    if str(session_metadata.get("followup_record_id") or "").strip():
        return "mastery_followup"
    if str(session_metadata.get("rework_record_id") or "").strip():
        return "teacher_rework"
    return "archive_reflection"


def _build_wrong_question_chat_reflection_summary(
    reflection: dict,
    summary_text: str,
    session_metadata: dict,
) -> dict:
    normalized_reflection = reflection if isinstance(reflection, dict) else {}
    answered_stages = []
    why_wrong = str(normalized_reflection.get("why_wrong") or "").strip()
    unknown_step = str(normalized_reflection.get("unknown_step") or "").strip()
    help_preference = str(normalized_reflection.get("help_preference") or "").strip()
    if why_wrong:
        answered_stages.append("ask_why_wrong")
    if unknown_step:
        answered_stages.append("ask_unknown_step")
    if help_preference:
        answered_stages.append("ask_help_mode")
    reflection_summary = {
        "schema_version": "wrong_question_reflection_summary.v1",
        "mode": _infer_wrong_question_chat_reflection_mode(session_metadata),
        "summary_text": str(summary_text or "").strip(),
        "answered_stages": answered_stages,
    }
    if why_wrong:
        reflection_summary["why_wrong"] = why_wrong
    if unknown_step:
        reflection_summary["unknown_step"] = unknown_step
    if help_preference:
        reflection_summary["help_preference"] = help_preference
    entrypoint = str(session_metadata.get("entrypoint") or "").strip() if isinstance(session_metadata, dict) else ""
    if entrypoint:
        reflection_summary["session_entrypoint"] = entrypoint
    return reflection_summary


def _resolve_wrong_question_archive_image_url(run: object, archive_payload: dict) -> str:
    direct_image_url = str(archive_payload.get("image_url") or "").strip()
    if direct_image_url:
        return direct_image_url
    if isinstance(run, dict):
        for asset in reversed(list_wrong_question_assets(str(run.get("id") or ""))):
            if not isinstance(asset, dict):
                continue
            candidate = str(asset.get("file_url") or asset.get("storage_path") or "").strip()
            if candidate:
                return candidate
    return ""


def _infer_wrong_question_confirmation_state(*, archive_payload: dict, reflection: dict, image_url: str) -> tuple[bool, list[str]]:
    reasons = []
    for item in archive_payload.get("confirmation_reasons_json") or []:
        reason = str(item or "").strip()
        if reason and reason not in reasons:
            reasons.append(reason)
    if not image_url:
        reasons.append("missing_image_asset")
    if not str(archive_payload.get("question_text") or "").strip():
        reasons.append("missing_question_text")
    knowledge_tags = archive_payload.get("knowledge_tags_json")
    if not isinstance(knowledge_tags, list) or not any(str(item or "").strip() for item in knowledge_tags):
        reasons.append("knowledge_tags_unconfirmed")
    if not str(reflection.get("unknown_step") or "").strip():
        reasons.append("student_confused_step")
    needs_teacher_confirmation = bool(archive_payload.get("needs_teacher_confirmation")) or bool(reasons)
    return needs_teacher_confirmation, reasons

def _get_parent_wechat_account_by_openid(open_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM parent_wechat_accounts WHERE openid=?",
            (open_id,),
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
    return jsonify({"ok": True, "user": get_user_by_id(user["id"])})


@app.route("/api/profile/avatar", methods=["PUT"])
def api_profile_avatar_update():
    user, error = _require_auth()
    if error:
        return error
    data = request.json or {}
    avatar_source = str(data.get("avatar_source") or "").strip() or "dicebear"
    avatar_seed = str(data.get("avatar_seed") or "").strip()
    try:
        updated_user = update_user_avatar_preferences(
            user["id"],
            avatar_source=avatar_source,
            avatar_seed=avatar_seed,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"ok": True, "user": updated_user})


@app.route("/api/profile/avatar-upload", methods=["POST"])
def api_profile_avatar_upload():
    user, error = _require_auth()
    if error:
        return error
    avatar_file = request.files.get("avatar")
    if not avatar_file or not avatar_file.filename:
        return jsonify({"error": "请先选择头像图片"}), 400
    mime_type = str(getattr(avatar_file, "mimetype", "") or "").lower()
    if not mime_type.startswith("image/"):
        return jsonify({"error": "仅支持上传图片文件"}), 400
    file_size = _uploaded_file_size(avatar_file)
    if file_size > PROFILE_AVATAR_MAX_BYTES:
        return jsonify({"error": f"头像图片不能超过 {PROFILE_AVATAR_MAX_LABEL}"}), 400

    profile_avatar_dir = UPLOAD_DIR / "profile-avatars"
    profile_avatar_dir.mkdir(parents=True, exist_ok=True)
    for existing in profile_avatar_dir.glob(f"user-{int(user['id'])}-*"):
        existing.unlink(missing_ok=True)

    relative_path = _profile_avatar_upload_relative_path(user["id"], avatar_file.filename)
    save_path = UPLOAD_DIR / relative_path
    avatar_file.save(save_path)

    try:
        updated_user = update_user_avatar_preferences(
            user["id"],
            avatar_source="upload",
            avatar_upload_path=relative_path,
        )
    except (LookupError, ValueError) as exc:
        save_path.unlink(missing_ok=True)
        status_code = 404 if isinstance(exc, LookupError) else 400
        return jsonify({"error": str(exc)}), status_code
    return jsonify({"ok": True, "user": updated_user})


@app.route("/api/profile/password", methods=["PUT"])
def api_profile_password_update():
    user, error = _require_auth()
    if error:
        return error
    data = request.json or {}
    current_password = str(data.get("current_password") or "")
    new_password = str(data.get("new_password") or "")
    try:
        change_user_password(user["id"], current_password, new_password)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
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
            "avatar_source": u.get("avatar_source", "dicebear"),
            "avatar_seed": u.get("avatar_seed", ""),
            "avatar_upload_url": u.get("avatar_upload_url", ""),
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


@app.route("/api/admin/wrong-question-activity-summary", methods=["GET"])
def api_admin_wrong_question_activity_summary():
    _, error = _require_super_owner()
    if error:
        return error
    try:
        week_start_date, week_end_date = _weekly_range(request.args.get("week_start", ""))
    except ValueError:
        return jsonify({"error": "week_start must be YYYY-MM-DD"}), 400

    organization_id = request.args.get("organization_id", 0, type=int)
    summary = list_weekly_wrong_question_activity_summary(
        week_start_date=week_start_date,
        week_end_date=week_end_date,
        organization_id=organization_id if organization_id else None,
    )
    return jsonify(
        {
            "week_start": week_start_date,
            "week_end": week_end_date,
            "class_items": summary["class_items"],
            "teacher_items": summary["teacher_items"],
            "student_items": [
                _weekly_activity_student_item_payload(item)
                for item in summary["student_items"]
            ],
        }
    )


@app.route("/api/admin/organizations/<int:org_id>", methods=["DELETE"])
def api_admin_organization_delete(org_id: int):
    user, error = _require_super_owner()
    if error:
        return error
    try:
        result = delete_organization(org_id, actor_user_id=int(user["id"]))
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    if result.get("action") == "deleted":
        return jsonify({"ok": True})
    memory_cleanup = result.pop("memory_cleanup", None)
    if isinstance(memory_cleanup, dict) and memory_cleanup.get("operation_ids"):
        _dispatch_class_commentary_memory_best_effort()
    graph_cleanup = result.pop("graph_cleanup", None)
    if isinstance(graph_cleanup, dict) and graph_cleanup.get("operation_ids"):
        _dispatch_class_commentary_graph_best_effort()
    return jsonify({"ok": True, **result})


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
        result = delete_user_for_actor(user, user_id)
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    if result.get("action") == "deleted":
        return jsonify({"ok": True})
    memory_cleanup = result.pop("memory_cleanup", None)
    if isinstance(memory_cleanup, dict) and memory_cleanup.get("operation_ids"):
        _dispatch_class_commentary_memory_best_effort()
    return jsonify({"ok": True, **result})


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
            student_name = str(item.get("student_name") or "").strip() or "未命名"
            sheet = item.get("practice_sheet") if isinstance(item.get("practice_sheet"), dict) else None
            if not sheet:
                continue
            try:
                if str(sheet.get("status") or "") != "ready":
                    raise FileNotFoundError(str(sheet.get("pdf_path") or ""))
                pdf_path = Path(str(sheet.get("pdf_path") or ""))
                if not pdf_path.exists():
                    raise FileNotFoundError(str(pdf_path))
                base_name = f"{_safe_archive_filename_part(student_name)}-错题练习"
                name_count = used_filenames.get(base_name, 0) + 1
                used_filenames[base_name] = name_count
                archive_name = f"{base_name}.pdf" if name_count == 1 else f"{base_name}-{name_count}.pdf"
                archive.write(pdf_path, archive_name)
                successful_count += 1
            except Exception:
                logger.exception("Failed to add weekly wrong question practice pdf to archive")
                failed_student_names.append(student_name)
        if failed_student_names:
            notes = ["以下学生错题练习 PDF 打包失败：", *failed_student_names]
            archive.writestr("打包说明.txt", "\n".join(notes).encode("utf-8"))
    buffer.seek(0)

    download_name = (
        f"{_safe_archive_filename_part(str(cls.get('name') or '班级'))}"
        f"-{week_start_date}-错题练习合集.zip"
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


def _weekly_followup_item_for_student(items: list[dict], student_id: int) -> Optional[dict]:
    for item in items:
        if int(item.get("student_id") or 0) == int(student_id or 0):
            return item
    return None


def _create_weekly_followup_practice_sheet_from_item(user: dict, item: dict) -> dict:
    record_ids = [str(record_id or "").strip() for record_id in (item.get("candidate_record_ids") or [])]
    selected_records = []
    for record_id in record_ids:
        if not record_id:
            continue
        record = get_wechat_wrong_question_submission(record_id)
        if record:
            selected_records.append(record)
    if not selected_records:
        raise ValueError("no practice candidates")
    sheet = create_pending_wrong_question_practice_sheet(
        created_by=int(user["id"]),
        selected_records=selected_records,
    )
    _start_wrong_question_practice_generation_thread(
        sheet_id=int(sheet["id"]),
        user={
            "id": int(user["id"]),
            "organization_id": int(user["organization_id"]),
        },
    )
    return sheet


@app.route("/api/wrong-question-followups/weekly/practice-sheets", methods=["POST"])
def api_weekly_wrong_question_followup_practice_sheet_create():
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    if not has_api_key():
        return jsonify({"error": "系统 API Key 未配置，请联系管理员"}), 400
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
        week_start_date, week_end_date = _weekly_range(data.get("week_start", ""))
    except ValueError:
        return jsonify({"error": "week_start must be YYYY-MM-DD"}), 400

    items = list_weekly_wrong_question_followup_students(
        organization_id=organization_id,
        class_id=class_id,
        week_start_date=week_start_date,
        week_end_date=week_end_date,
    )
    item = _weekly_followup_item_for_student(items, student_id)
    if not item:
        return jsonify({"error": "student followup not found"}), 404
    if item.get("status") != "needs_practice_sheet":
        return jsonify({"error": "student does not need a weekly practice sheet"}), 409
    try:
        sheet = _create_weekly_followup_practice_sheet_from_item(user, item)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({
        "id": sheet["id"],
        "status": sheet["status"],
        "student_id": sheet["student_id"],
        "sheet": _serialize_wrong_question_practice_sheet_for_response(sheet),
    }), 202


@app.route("/api/wrong-question-followups/weekly/practice-sheets/batch", methods=["POST"])
def api_weekly_wrong_question_followup_practice_sheet_batch_create():
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    if not has_api_key():
        return jsonify({"error": "系统 API Key 未配置，请联系管理员"}), 400
    try:
        class_id = int(data.get("class_id") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "class_id must be numeric"}), 400
    if not class_id:
        return jsonify({"error": "class_id is required"}), 400
    cls = _require_accessible_class(user, class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    organization_id = int(cls.get("organization_id") or user.get("organization_id") or 0)
    try:
        week_start_date, week_end_date = _weekly_range(data.get("week_start", ""))
    except ValueError:
        return jsonify({"error": "week_start must be YYYY-MM-DD"}), 400

    items = list_weekly_wrong_question_followup_students(
        organization_id=organization_id,
        class_id=class_id,
        week_start_date=week_start_date,
        week_end_date=week_end_date,
    )
    created_items = []
    skipped_count = 0
    for item in items:
        if item.get("status") != "needs_practice_sheet":
            skipped_count += 1
            continue
        try:
            sheet = _create_weekly_followup_practice_sheet_from_item(user, item)
        except ValueError:
            skipped_count += 1
            continue
        created_items.append({
            "id": sheet["id"],
            "status": sheet["status"],
            "student_id": sheet["student_id"],
            "sheet": _serialize_wrong_question_practice_sheet_for_response(sheet),
        })
    return jsonify({
        "items": created_items,
        "created_count": len(created_items),
        "skipped_count": skipped_count,
    }), 202


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
    sheet = item.get("practice_sheet") if isinstance(item.get("practice_sheet"), dict) else None
    if item.get("status") != "has_practice_sheet" or not sheet or str(sheet.get("status") or "") != "ready":
        return jsonify({"error": "weekly practice sheet is required"}), 409

    message_text = ai_processor.generate_weekly_wrong_question_followup_message(
        student_name=str(item.get("student_name") or ""),
        class_name=str(item.get("class_name") or ""),
        teacher_name=str(item.get("teacher_name") or ""),
        weekly_question_count=int(item.get("weekly_question_count") or 0),
        total_active_question_count=int(item.get("total_active_question_count") or 0),
        topic_categories=item.get("topic_categories") or [],
        representative_reason_summaries=item.get("representative_reason_summaries") or [],
        has_practice_sheet=True,
        practice_sheet_question_count=int(sheet.get("question_count") or item.get("weekly_question_count") or 0),
        practice_sheet_topic_categories=sheet.get("topic_categories") or item.get("topic_categories") or [],
        practice_sheet_reason_summaries=sheet.get("representative_reason_summaries") or item.get("representative_reason_summaries") or [],
        practice_sheet_item_summaries=sheet.get("representative_reason_summaries") or item.get("representative_reason_summaries") or [],
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
        source_sheet_id=int(sheet.get("id") or 0),
        generated_by=int(user["id"]),
    )
    return jsonify({"ok": True, "message": _weekly_followup_message_payload(message)})


@app.route("/api/wrong-questions", methods=["GET"])
def api_wrong_questions_list():
    user, error = _require_auth()
    if error:
        return error
    forwarded_args = request.args.copy()
    forwarded_args.pop("confirmationState", None)
    forwarded_args.pop("confirmation_state", None)
    try:
        payload = smart_wrong_questions.fetch_wrong_question_records(forwarded_args)
    except smart_wrong_questions.WrongQuestionProxyError as exc:
        if exc.status_code == 503 and str(exc) == "智能错题服务尚未配置":
            payload = {"items": [], "total": 0}
        else:
            return jsonify({"error": str(exc)}), exc.status_code

    local_items = list_wechat_wrong_question_submissions()
    merged_items = [*local_items, *payload.get("items", [])]
    scoped_items = _filter_wrong_question_items_for_user(user, merged_items)
    scoped_items = _filter_wrong_question_items_by_confirmation_state(
        scoped_items,
        str(request.args.get("confirmationState") or request.args.get("confirmation_state") or ""),
    )
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
        return jsonify(_serialize_wrong_question_record_for_response(local_record, include_archive_context=True))
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
        saved_record = save_wechat_wrong_question_review(
            record_id,
            request.json or {},
            reviewer_user_id=int(user["id"]),
        )
        if not saved_record:
            return jsonify({"error": "not found"}), 404
        question_text = str(((request.json or {}).get("question_text") or "")).strip()
        if question_text:
            saved_record = update_wechat_wrong_question_question_text(
                record_id,
                question_text=question_text,
                student_library_pdf_path=str(local_record.get("student_library_pdf_path") or ""),
            )
        pdf_path = _refresh_student_wrong_question_library_cache(local_record["student_id"])
        saved_record = attach_student_library_pdf_path(record_id, pdf_path)
        return jsonify(
            {
                "ok": True,
                "record": _serialize_wrong_question_record_for_response(
                    saved_record,
                    include_archive_context=True,
                ),
            }
        )
    try:
        record = smart_wrong_questions.fetch_wrong_question_record(record_id, request.args)
        if not _can_access_wrong_question_record(user, record):
            return jsonify({"error": "not found"}), 404
        return jsonify(
            smart_wrong_questions.save_wrong_question_review(record_id, request.args, request.json or {})
        )
    except smart_wrong_questions.WrongQuestionProxyError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@app.route("/api/wrong-questions/<record_id>/reopen-chat", methods=["POST"])
def api_wrong_question_reopen_chat(record_id):
    user, error = _require_auth()
    if error:
        return error

    local_record = get_wechat_wrong_question_submission(record_id)
    if not local_record or not _can_access_wrong_question_record(user, local_record):
        return jsonify({"error": "not found"}), 404
    if str(local_record.get("source") or "").strip() != "ai_chat":
        return jsonify({"error": "only ai_chat records can reopen chat"}), 400

    confirmation_status = _normalize_wrong_question_confirmation_status(local_record)
    if confirmation_status != "returned":
        return jsonify({"error": "record is not waiting for rework"}), 400

    run = get_wrong_question_ingestion_run(str(local_record.get("ingestion_run_id") or "").strip())
    if run and not _can_access_wrong_question_ingestion_run(user, run):
        return jsonify({"error": "not found"}), 404

    if run:
        latest_session_id = str(run.get("chat_session_id") or "").strip()
        if latest_session_id:
            latest_session = get_wrong_question_chat_session(latest_session_id)
            latest_metadata = _load_wrong_question_chat_session_metadata(latest_session)
            if (
                latest_session
                and _can_access_wrong_question_chat_session(user, latest_session)
                and str(latest_session.get("status") or "").strip() == "active"
                and str(latest_metadata.get("rework_record_id") or "").strip() == str(local_record.get("id") or "").strip()
            ):
                return jsonify(
                    {
                        "ok": True,
                        "created": False,
                        "reused_active_session": True,
                        "session": _serialize_wrong_question_chat_session_for_response(latest_session),
                        "run": _serialize_wrong_question_ingestion_run_for_response(run),
                    }
                )

    new_session_id = f"chat-rework-{record_id[:8]}-{secrets.token_hex(4)}"
    previous_session_id = str(local_record.get("chat_session_id") or "").strip()
    reflection_seed = _build_wrong_question_chat_reflection_seed(local_record)
    initial_stage = _infer_wrong_question_chat_stage_from_reflection_seed(reflection_seed)
    session = create_wrong_question_chat_session(
        session_id=new_session_id,
        organization_id=int(local_record.get("organization_id") or user.get("organization_id") or 0),
        ingestion_run_id=str(local_record.get("ingestion_run_id") or "").strip(),
        class_id=int(local_record.get("class_id") or 0) or None,
        student_id=int(local_record.get("student_id") or 0) or None,
        teacher_user_id=int(local_record.get("teacher_user_id") or user["id"]) or None,
        current_stage=initial_stage,
        metadata_json={
            "entrypoint": "wrong_question_chat_rework",
            "rework_record_id": record_id,
            "previous_chat_session_id": previous_session_id,
            "reflection_seed": reflection_seed,
        },
    )
    create_wrong_question_chat_message(
        session_id=new_session_id,
        role="assistant",
        stage=initial_stage,
        content=_build_wrong_question_chat_rework_prompt_for_stage(local_record, initial_stage, reflection_seed),
    )
    if run:
        refreshed_run = update_wrong_question_ingestion_run(
            run["id"],
            status="active",
            current_step="chat_reflection",
            chat_session_id=new_session_id,
            error_message="",
        )
        if refreshed_run:
            run = refreshed_run

    serialized_session = _serialize_wrong_question_chat_session_for_response(
        get_wrong_question_chat_session(new_session_id)
    )
    return jsonify(
        {
            "ok": True,
            "created": True,
            "reused_active_session": False,
            "session": serialized_session,
            "run": _serialize_wrong_question_ingestion_run_for_response(run),
        }
    )


@app.route("/api/wrong-questions/<record_id>/followup-chat", methods=["POST"])
def api_wrong_question_followup_chat(record_id):
    user, error = _require_auth()
    if error:
        return error

    local_record = get_wechat_wrong_question_submission(record_id)
    if not local_record or not _can_access_wrong_question_record(user, local_record):
        return jsonify({"error": "not found"}), 404
    if not _can_start_wrong_question_mastery_followup(local_record):
        return jsonify({"error": "record is not ready for mastery followup"}), 400

    run = get_wrong_question_ingestion_run(str(local_record.get("ingestion_run_id") or "").strip())
    if run and not _can_access_wrong_question_ingestion_run(user, run):
        return jsonify({"error": "not found"}), 404

    if run:
        latest_session_id = str(run.get("chat_session_id") or "").strip()
        if latest_session_id:
            latest_session = get_wrong_question_chat_session(latest_session_id)
            latest_metadata = _load_wrong_question_chat_session_metadata(latest_session)
            if (
                latest_session
                and _can_access_wrong_question_chat_session(user, latest_session)
                and str(latest_session.get("status") or "").strip() == "active"
                and str(latest_metadata.get("followup_record_id") or "").strip() == str(local_record.get("id") or "").strip()
            ):
                return jsonify(
                    {
                        "ok": True,
                        "created": False,
                        "reused_active_session": True,
                        "session": _serialize_wrong_question_chat_session_for_response(latest_session),
                        "run": _serialize_wrong_question_ingestion_run_for_response(run),
                    }
                )

    new_session_id = f"chat-followup-{record_id[:8]}-{secrets.token_hex(4)}"
    previous_session_id = str(local_record.get("chat_session_id") or "").strip()
    session = create_wrong_question_chat_session(
        session_id=new_session_id,
        organization_id=int(local_record.get("organization_id") or user.get("organization_id") or 0),
        ingestion_run_id=str(local_record.get("ingestion_run_id") or "").strip(),
        class_id=int(local_record.get("class_id") or 0) or None,
        student_id=int(local_record.get("student_id") or 0) or None,
        teacher_user_id=int(local_record.get("teacher_user_id") or user["id"]) or None,
        metadata_json={
            "entrypoint": "wrong_question_chat_mastery_followup",
            "followup_kind": "mastery_check",
            "followup_record_id": record_id,
            "previous_chat_session_id": previous_session_id,
        },
    )
    create_wrong_question_chat_message(
        session_id=new_session_id,
        role="assistant",
        stage="ask_why_wrong",
        content=_build_wrong_question_chat_mastery_followup_prompt(local_record),
    )
    if run:
        refreshed_run = update_wrong_question_ingestion_run(
            run["id"],
            status="active",
            current_step="chat_reflection",
            chat_session_id=new_session_id,
            error_message="",
        )
        if refreshed_run:
            run = refreshed_run

    serialized_session = _serialize_wrong_question_chat_session_for_response(
        get_wrong_question_chat_session(new_session_id)
    )
    return jsonify(
        {
            "ok": True,
            "created": True,
            "reused_active_session": False,
            "session": serialized_session,
            "run": _serialize_wrong_question_ingestion_run_for_response(run),
        }
    )


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


@app.route("/api/wrong-question-ingestions", methods=["GET"])
def api_wrong_question_ingestion_list():
    user, error = _require_auth()
    if error:
        return error

    try:
        class_id = int(request.args.get("class_id") or 0)
    except (TypeError, ValueError):
        class_id = 0
    try:
        student_id = int(request.args.get("student_id") or 0)
    except (TypeError, ValueError):
        student_id = 0
    try:
        teacher_user_id = int(request.args.get("teacher_user_id") or 0)
    except (TypeError, ValueError):
        teacher_user_id = 0
    try:
        limit = int(request.args.get("limit") or 50)
    except (TypeError, ValueError):
        limit = 50

    source = str(request.args.get("source") or "").strip()
    status = str(request.args.get("status") or "").strip()
    chat_session_id = str(request.args.get("chat_session_id") or "").strip()

    organization_id = int(user.get("organization_id") or 0)
    if class_id:
        cls, class_error = _get_accessible_class_or_error(user, class_id)
        if class_error:
            return class_error
        organization_id = int(cls.get("organization_id") or organization_id)

    runs = list_wrong_question_ingestion_runs(
        organization_id=organization_id,
        source=source or None,
        status=status or None,
        class_id=class_id or None,
        student_id=student_id or None,
        teacher_user_id=teacher_user_id or None,
        chat_session_id=chat_session_id or None,
        limit=limit,
    )
    visible_runs = [
        serialized
        for serialized in (
            _serialize_wrong_question_ingestion_run_for_response(run)
            for run in runs
            if _can_access_wrong_question_ingestion_run(user, run)
        )
        if serialized is not None
    ]
    return jsonify({"items": visible_runs})


@app.route("/api/wrong-question-ingestions", methods=["POST"])
def api_wrong_question_ingestion_create():
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    source = str(data.get("source") or "workspace").strip() or "workspace"
    if source not in {"workspace", "ai_chat", "wechat_mp"}:
        return jsonify({"error": "source must be workspace, ai_chat or wechat_mp"}), 400

    class_id = int(data.get("class_id") or 0)
    student_id = int(data.get("student_id") or 0)
    if not class_id or not student_id:
        return jsonify({"error": "class_id and student_id are required"}), 400
    cls, class_error = _get_accessible_class_or_error(user, class_id)
    if class_error:
        return class_error

    class_students = list_students_for_class(class_id)
    if not any(int(item.get("id") or 0) == student_id for item in class_students):
        return jsonify({"error": "student not found in class"}), 404

    teacher_user_id = int(data.get("teacher_user_id") or get_class_teacher_user_id(class_id) or user["id"])
    teacher_user = get_user_by_id(teacher_user_id)
    if not teacher_user:
        return jsonify({"error": "teacher user not found"}), 404
    if user.get("role") != "super_owner" and teacher_user.get("organization_id") != user.get("organization_id"):
        return jsonify({"error": "teacher user not found"}), 404

    try:
        run = create_wrong_question_ingestion_run(
            organization_id=int(cls.get("organization_id") or user.get("organization_id") or 0),
            source=source,
            class_id=class_id,
            student_id=student_id,
            teacher_user_id=teacher_user_id,
            parent_wechat_account_id=data.get("parent_wechat_account_id"),
            chat_session_id=str(data.get("chat_session_id") or "").strip(),
            status=str(data.get("status") or "pending").strip() or "pending",
            current_step=str(data.get("current_step") or "").strip(),
            original_filename=str(data.get("original_filename") or "").strip(),
            mime_type=str(data.get("mime_type") or "").strip(),
            error_message=str(data.get("error_message") or "").strip(),
            metadata_json=data.get("metadata"),
        )
        _create_wrong_question_assets_from_payload(run["id"], data.get("assets"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    created = _serialize_wrong_question_ingestion_run_for_response(get_wrong_question_ingestion_run(run["id"]))
    return jsonify({"run": created}), 201


@app.route("/api/wrong-question-ingestions/<run_id>/assets/upload", methods=["POST"])
def api_wrong_question_ingestion_asset_upload(run_id: str):
    user, error = _require_auth()
    if error:
        return error

    run = get_wrong_question_ingestion_run(run_id)
    if not run or not _can_access_wrong_question_ingestion_run(user, run):
        return jsonify({"error": "not found"}), 404

    upload_items = request.files.getlist("files")
    if not upload_items:
        single_file = request.files.get("file")
        if single_file is not None:
            upload_items = [single_file]
    upload_items = [item for item in upload_items if item and item.filename]
    if not upload_items:
        return jsonify({"error": "at least one file is required"}), 400

    allowed_suffixes = {".png", ".jpg", ".jpeg", ".webp"}
    created_assets = []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for index, file_storage in enumerate(upload_items):
        original_filename = str(file_storage.filename or "").strip()
        suffix = Path(original_filename).suffix.lower()
        if suffix not in allowed_suffixes:
            return jsonify({"error": "只支持 png、jpg、jpeg、webp 图片"}), 400
        safe_filename = secure_filename(original_filename) or f"wrong-question-{index + 1}{suffix}"
        filename = (
            f"wrong-question-ingestion-{run_id}-{int(time() * 1000)}-{index + 1}-{safe_filename}"
        )
        save_path = UPLOAD_DIR / filename
        file_storage.save(save_path)
        created_assets.append(
            create_wrong_question_asset(
                ingestion_run_id=run_id,
                asset_role="original_upload",
                storage_path=str(save_path),
                file_url=f"/api/wrong-question-ingestion-assets/{filename}",
                mime_type=str(file_storage.mimetype or "").strip() or "image/png",
                page_number=index + 1,
                metadata_json={
                    "original_filename": original_filename,
                    "upload_index": index,
                },
            )
        )

    updated = update_wrong_question_ingestion_run(
        run_id,
        status=str(run.get("status") or "pending").strip() or "pending",
        current_step="uploaded",
    ) or run
    serialized = _serialize_wrong_question_ingestion_run_for_response(updated)
    return jsonify({"ok": True, "run": serialized, "assets": created_assets}), 201


@app.route("/api/wrong-question-ingestions/<run_id>", methods=["GET"])
def api_wrong_question_ingestion_detail(run_id: str):
    user, error = _require_auth()
    if error:
        return error
    run = get_wrong_question_ingestion_run(run_id)
    if not run or not _can_access_wrong_question_ingestion_run(user, run):
        return jsonify({"error": "not found"}), 404
    serialized = _serialize_wrong_question_ingestion_run_for_response(run)
    if serialized is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"run": serialized})


@app.route("/api/wrong-question-ingestions/<run_id>/ocr", methods=["POST"])
def api_wrong_question_ingestion_ocr(run_id: str):
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    run = get_wrong_question_ingestion_run(run_id)
    if not run or not _can_access_wrong_question_ingestion_run(user, run):
        return jsonify({"error": "not found"}), 404
    try:
        _create_wrong_question_assets_from_payload(run_id, data.get("assets"))
        updated = update_wrong_question_ingestion_run(
            run_id,
            status=str(data.get("status") or "ocr_ready").strip() or "ocr_ready",
            current_step=str(data.get("current_step") or "ocr_completed").strip() or "ocr_completed",
            chat_session_id=str(data.get("chat_session_id") or run.get("chat_session_id") or "").strip(),
            error_message=str(data.get("error_message") or "").strip(),
            metadata_json=data.get("metadata"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "run": _serialize_wrong_question_ingestion_run_for_response(updated)})


@app.route("/api/wrong-question-ingestions/<run_id>/split", methods=["POST"])
def api_wrong_question_ingestion_split(run_id: str):
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    run = get_wrong_question_ingestion_run(run_id)
    if not run or not _can_access_wrong_question_ingestion_run(user, run):
        return jsonify({"error": "not found"}), 404
    try:
        _create_wrong_question_assets_from_payload(run_id, data.get("assets"))
        updated = update_wrong_question_ingestion_run(
            run_id,
            status=str(data.get("status") or "split_ready").strip() or "split_ready",
            current_step=str(data.get("current_step") or "split_completed").strip() or "split_completed",
            error_message=str(data.get("error_message") or "").strip(),
            metadata_json=data.get("metadata"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "run": _serialize_wrong_question_ingestion_run_for_response(updated)})


@app.route("/api/wrong-question-ingestions/<run_id>/archive", methods=["POST"])
def api_wrong_question_ingestion_archive(run_id: str):
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    run = get_wrong_question_ingestion_run(run_id)
    if not run or not _can_access_wrong_question_ingestion_run(user, run):
        return jsonify({"error": "not found"}), 404

    existing_records = list_wrong_question_submissions_for_ingestion_run(run_id)
    if existing_records:
        updated = update_wrong_question_ingestion_run(
            run_id,
            status="archived",
            current_step="archived",
            error_message="",
        ) or run
        return jsonify(
            {
                "ok": True,
                "created": False,
                "idempotent_reuse": True,
                "run": _serialize_wrong_question_ingestion_run_for_response(updated),
                "created_records": _serialize_wrong_question_records_for_response(existing_records),
            }
        )

    try:
        submissions = _normalize_wrong_question_ingestion_record_payloads(data.get("submissions"))
        created_records = []
        student_id = int(run.get("student_id") or 0)
        for item in submissions:
            record_source = str(item.get("source") or run.get("source") or "workspace").strip() or "workspace"
            if record_source == "wechat_mp" and not item.get("binding_id"):
                return jsonify({"error": "binding_id is required when archiving wechat_mp submissions"}), 400
            created_records.append(
                create_wrong_question_submission(
                    source=record_source,
                    organization_id=int(run.get("organization_id") or 0),
                    parent_wechat_account_id=item.get("parent_wechat_account_id") or run.get("parent_wechat_account_id"),
                    binding_id=item.get("binding_id"),
                    class_id=int(run.get("class_id") or 0),
                    student_id=int(run.get("student_id") or 0),
                    teacher_user_id=int(item.get("teacher_user_id") or run.get("teacher_user_id") or user["id"]),
                    image_url=str(item.get("image_url") or "").strip(),
                    child_raw_reason_text=str(item.get("child_raw_reason_text") or "").strip(),
                    child_reason_transcript=str(item.get("child_reason_transcript") or "").strip(),
                    child_reason_input_mode=str(item.get("child_reason_input_mode") or "text").strip() or "text",
                    primary_error_type=str(item.get("primary_error_type") or "").strip(),
                    secondary_error_summary=str(item.get("secondary_error_summary") or "").strip(),
                    child_reason_core_issue=str(item.get("child_reason_core_issue") or "").strip(),
                    child_reason_key_omission=str(item.get("child_reason_key_omission") or "").strip(),
                    child_reason_next_step=str(item.get("child_reason_next_step") or "").strip(),
                    topic_category=str(item.get("topic_category") or item.get("topicCategory") or "").strip(),
                    recognition_status=str(item.get("recognition_status") or "recognized").strip() or "recognized",
                    is_geometry=bool(item.get("is_geometry")),
                    image_rotation_degrees=int(item.get("image_rotation_degrees") or 0),
                    question_text=str(item.get("question_text") or "").strip(),
                    question_text_source=str(item.get("question_text_source") or "ai").strip() or "ai",
                    diagram_type=str(item.get("diagram_type") or "").strip(),
                    diagram_spec=item.get("diagram_spec"),
                    diagram_spec_json=str(item.get("diagram_spec_json") or "").strip(),
                    recognition_error=str(item.get("recognition_error") or "").strip(),
                    student_library_pdf_path=str(item.get("student_library_pdf_path") or "").strip(),
                    ingestion_run_id=run_id,
                    chat_session_id=str(item.get("chat_session_id") or run.get("chat_session_id") or "").strip(),
                    question_structured_json=item.get("question_structured_json"),
                    knowledge_tags_json=item.get("knowledge_tags_json"),
                    reflection_summary_json=item.get("reflection_summary_json", item.get("reflection_summary")),
                    generation_metadata_json=item.get("generation_metadata_json", item.get("generation_metadata")),
                    needs_teacher_confirmation=bool(item.get("needs_teacher_confirmation")),
                    confirmation_reasons_json=item.get("confirmation_reasons_json"),
                )
            )
        pdf_path = _refresh_student_wrong_question_library_cache(student_id) if student_id and created_records else ""
        if pdf_path:
            created_records = [
                attach_student_library_pdf_path(str(record.get("id") or ""), pdf_path) or record
                for record in created_records
            ]
        created_records = [
            serialized_record or record
            for record in created_records
            for serialized_record in [_serialize_wrong_question_record_for_response(record)]
        ]
        _create_wrong_question_assets_from_payload(run_id, data.get("assets"))
        updated = update_wrong_question_ingestion_run(
            run_id,
            status=str(data.get("status") or "archived").strip() or "archived",
            current_step=str(data.get("current_step") or "archived").strip() or "archived",
            error_message=str(data.get("error_message") or "").strip(),
            metadata_json=data.get("metadata"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404

    return jsonify(
        {
            "ok": True,
            "created": True,
            "idempotent_reuse": False,
            "run": _serialize_wrong_question_ingestion_run_for_response(updated),
            "created_records": created_records,
        }
    )


@app.route("/api/wrong-question-chats/<session_id>/stream", methods=["POST"])
def api_wrong_question_chat_stream(session_id: str):
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return jsonify({"error": "session_id is required"}), 400

    archive_payload = data.get("archive_payload")
    if archive_payload is None:
        archive_payload = {}
    if not isinstance(archive_payload, dict):
        return jsonify({"error": "archive_payload must be an object"}), 400

    session = get_wrong_question_chat_session(normalized_session_id)
    run = None
    if session:
        if not _can_access_wrong_question_chat_session(user, session):
            return jsonify({"error": "not found"}), 404
    else:
        requested_run_id = str(data.get("ingestion_run_id") or "").strip()
        if requested_run_id:
            run = get_wrong_question_ingestion_run(requested_run_id)
            if not run or not _can_access_wrong_question_ingestion_run(user, run):
                return jsonify({"error": "ingestion run not found"}), 404
        class_id = int(data.get("class_id") or (run.get("class_id") if isinstance(run, dict) else 0) or 0)
        student_id = int(data.get("student_id") or (run.get("student_id") if isinstance(run, dict) else 0) or 0)
        if not class_id or not student_id:
            return jsonify({"error": "class_id and student_id are required"}), 400
        cls, class_error = _get_accessible_class_or_error(user, class_id)
        if class_error:
            return class_error
        class_students = list_students_for_class(class_id)
        if not any(int(item.get("id") or 0) == student_id for item in class_students):
            return jsonify({"error": "student not found in class"}), 404

        teacher_user_id = int(
            data.get("teacher_user_id")
            or (run.get("teacher_user_id") if isinstance(run, dict) else 0)
            or get_class_teacher_user_id(class_id)
            or user["id"]
        )
        teacher_user = get_user_by_id(teacher_user_id)
        if not teacher_user:
            return jsonify({"error": "teacher user not found"}), 404
        if user.get("role") != "super_owner" and teacher_user.get("organization_id") != user.get("organization_id"):
            return jsonify({"error": "teacher user not found"}), 404

        session = create_wrong_question_chat_session(
            session_id=normalized_session_id,
            organization_id=int(cls.get("organization_id") or user.get("organization_id") or 0),
            ingestion_run_id=str((run or {}).get("id") or "").strip(),
            class_id=class_id,
            student_id=student_id,
            teacher_user_id=teacher_user_id,
            metadata_json={"entrypoint": "wrong_question_chat"},
        )
        if isinstance(run, dict):
            updated_run = update_wrong_question_ingestion_run(
                run["id"],
                chat_session_id=normalized_session_id,
                current_step="chat_reflection",
            )
            if updated_run:
                run = updated_run

    if not isinstance(session, dict):
        return jsonify({"error": "chat session unavailable"}), 500

    if not isinstance(run, dict) and str(session.get("ingestion_run_id") or "").strip():
        run = get_wrong_question_ingestion_run(str(session.get("ingestion_run_id") or "").strip())

    existing_records = list_wrong_question_submissions_for_chat_session(normalized_session_id)
    session_metadata = _load_wrong_question_chat_session_metadata(session)
    archived_record = None
    archived_record_id = str(session_metadata.get("archived_record_id") or "").strip()
    if archived_record_id:
        archived_record = get_wechat_wrong_question_submission(archived_record_id)
    if str(session.get("status") or "").strip() == "archived" and (existing_records or archived_record):
        archived_reference_record = existing_records[0] if existing_records else archived_record
        updated_run = run
        if isinstance(run, dict):
            updated_run = update_wrong_question_ingestion_run(
                run["id"],
                status="archived",
                current_step="archived",
                chat_session_id=normalized_session_id,
                error_message="",
            ) or run
        serialized = _serialize_wrong_question_chat_session_for_response(
            update_wrong_question_chat_session(
                normalized_session_id,
                status="archived",
                current_stage="ready_to_archive",
            )
            or get_wrong_question_chat_session(normalized_session_id)
        )
        return jsonify(
            {
                "ok": True,
                "session": serialized,
                "assistant_message": None,
                "archive": {
                    "created": False,
                    "idempotent_reuse": True,
                    "record": _serialize_wrong_question_record_for_response(archived_reference_record),
                },
                "run": _serialize_wrong_question_ingestion_run_link_for_response(updated_run),
            }
        )

    message = str(data.get("message") or "").strip()
    if str(data.get("message_role") or "user").strip() not in {"", "user"}:
        return jsonify({"error": "message_role must be user"}), 400

    existing_messages = list_wrong_question_chat_messages(normalized_session_id)
    current_stage = str(session.get("current_stage") or "ask_why_wrong").strip() or "ask_why_wrong"

    if not existing_messages and not message:
        assistant_message = create_wrong_question_chat_message(
            session_id=normalized_session_id,
            role="assistant",
            stage=current_stage,
            content=_wrong_question_chat_prompt_for_stage(current_stage),
        )
        serialized = _serialize_wrong_question_chat_session_for_response(get_wrong_question_chat_session(normalized_session_id))
        return jsonify({"ok": True, "session": serialized, "assistant_message": assistant_message, "archive": None})

    if not message:
        return jsonify({"error": "message is required"}), 400

    create_wrong_question_chat_message(
        session_id=normalized_session_id,
        role="user",
        stage=current_stage,
        content=message,
    )
    messages = list_wrong_question_chat_messages(normalized_session_id)
    reflection = _collect_wrong_question_chat_reflection(
        messages,
        _load_wrong_question_chat_reflection_seed(session_metadata),
    )
    summary_text = _summarize_wrong_question_chat_reflection(reflection)
    reflection_summary = _build_wrong_question_chat_reflection_summary(
        reflection,
        summary_text,
        session_metadata,
    )
    next_stage = _WRONG_QUESTION_CHAT_NEXT_STAGE.get(current_stage, "ready_to_archive")
    assistant_message = create_wrong_question_chat_message(
        session_id=normalized_session_id,
        role="assistant",
        stage=next_stage,
        content=_wrong_question_chat_prompt_for_stage(next_stage),
    )

    session_metadata["reflection"] = reflection
    session_metadata["reflection_summary"] = reflection_summary

    archive_result = None
    should_finalize = bool(data.get("finalize_archive")) or current_stage == "ask_help_mode"
    if should_finalize:
        if existing_records:
            archive_result = {
                "created": False,
                "idempotent_reuse": True,
                "record": _serialize_wrong_question_record_for_response(existing_records[0]),
            }
            session_metadata["archived_record_id"] = existing_records[0]["id"]
            session = update_wrong_question_chat_session(
                normalized_session_id,
                status="archived",
                current_stage="ready_to_archive",
                summary_text=summary_text,
                metadata_json=session_metadata,
            ) or session
        else:
            image_url = _resolve_wrong_question_archive_image_url(run, archive_payload)
            if not image_url:
                return jsonify({"error": "missing image asset for archive"}), 400
            rework_record_id = str(session_metadata.get("rework_record_id") or "").strip()
            followup_record_id = str(session_metadata.get("followup_record_id") or "").strip()
            linked_record_id = rework_record_id or followup_record_id
            effective_archive_payload = dict(archive_payload)
            if linked_record_id:
                linked_record = get_wechat_wrong_question_submission(linked_record_id)
                if linked_record:
                    if "question_text" not in effective_archive_payload:
                        effective_archive_payload["question_text"] = str(linked_record.get("question_text") or "").strip()
                    if "knowledge_tags_json" not in effective_archive_payload:
                        try:
                            effective_archive_payload["knowledge_tags_json"] = json.loads(
                                str(linked_record.get("knowledge_tags_json") or "[]")
                            )
                        except json.JSONDecodeError:
                            effective_archive_payload["knowledge_tags_json"] = linked_record.get("knowledge_tags") or []
            needs_teacher_confirmation, confirmation_reasons = _infer_wrong_question_confirmation_state(
                archive_payload=effective_archive_payload,
                reflection=reflection,
                image_url=image_url,
            )
            confirmation_reasons_json = confirmation_reasons or archive_payload.get("confirmation_reasons_json") or []
            generation_metadata = _build_wrong_question_archive_generation_metadata(
                archive_payload=archive_payload,
                run=run,
                session_metadata=session_metadata,
            )
            archived_record = None
            if linked_record_id:
                archived_record = update_wrong_question_submission_from_chat_archive(
                    linked_record_id,
                    chat_session_id=normalized_session_id,
                    child_raw_reason_text=str(reflection.get("why_wrong") or "").strip(),
                    child_reason_transcript=summary_text,
                    child_reason_core_issue=str(reflection.get("unknown_step") or "").strip(),
                    child_reason_next_step=str(reflection.get("help_preference") or "").strip(),
                    topic_category=(
                        str(archive_payload.get("topic_category") or archive_payload.get("topicCategory") or "").strip()
                        if ("topic_category" in archive_payload or "topicCategory" in archive_payload)
                        else None
                    ),
                    question_text=(
                        str(archive_payload.get("question_text") or "").strip()
                        if "question_text" in archive_payload
                        else None
                    ),
                    question_text_source=(
                        str(archive_payload.get("question_text_source") or "ai").strip() or "ai"
                        if "question_text_source" in archive_payload
                        else None
                    ),
                    question_structured_json=archive_payload.get("question_structured_json")
                    if "question_structured_json" in archive_payload
                    else None,
                    knowledge_tags_json=archive_payload.get("knowledge_tags_json")
                    if "knowledge_tags_json" in archive_payload
                    else None,
                    reflection_summary_json=reflection_summary,
                    generation_metadata_json=generation_metadata,
                    needs_teacher_confirmation=needs_teacher_confirmation,
                    confirmation_reasons_json=confirmation_reasons_json,
                    preserve_existing_confirmation_review=bool(followup_record_id and not rework_record_id),
                )
            if archived_record is None:
                archived_record = create_wrong_question_submission(
                    source="ai_chat",
                    organization_id=int(session.get("organization_id") or 0),
                    class_id=int(session.get("class_id") or 0),
                    student_id=int(session.get("student_id") or 0),
                    teacher_user_id=int(session.get("teacher_user_id") or user["id"]),
                    image_url=image_url,
                    child_raw_reason_text=str(reflection.get("why_wrong") or "").strip(),
                    child_reason_transcript=summary_text,
                    child_reason_core_issue=str(reflection.get("unknown_step") or "").strip(),
                    child_reason_next_step=str(reflection.get("help_preference") or "").strip(),
                    topic_category=str(archive_payload.get("topic_category") or archive_payload.get("topicCategory") or "").strip(),
                    recognition_status=str(archive_payload.get("recognition_status") or "recognized").strip() or "recognized",
                    question_text=str(archive_payload.get("question_text") or "").strip(),
                    question_text_source=str(archive_payload.get("question_text_source") or "ai").strip() or "ai",
                    ingestion_run_id=str(session.get("ingestion_run_id") or "").strip(),
                    chat_session_id=normalized_session_id,
                    question_structured_json=archive_payload.get("question_structured_json"),
                    knowledge_tags_json=archive_payload.get("knowledge_tags_json"),
                    reflection_summary_json=reflection_summary,
                    generation_metadata_json=generation_metadata,
                    needs_teacher_confirmation=needs_teacher_confirmation,
                    confirmation_reasons_json=confirmation_reasons_json,
                )
            if archived_record and followup_record_id and not rework_record_id:
                mastery_followup_outcome = str(
                    archive_payload.get("mastery_followup_outcome")
                    or archive_payload.get("masteryFollowupOutcome")
                    or ""
                ).strip()
                if mastery_followup_outcome:
                    refreshed_record = update_wrong_question_submission_mastery_followup(
                        archived_record["id"],
                        session_id=normalized_session_id,
                        outcome=mastery_followup_outcome,
                        summary_text=summary_text,
                    )
                    if refreshed_record is not None:
                        archived_record = refreshed_record
            student_id = int(session.get("student_id") or 0)
            pdf_path = _refresh_student_wrong_question_library_cache(student_id) if student_id else ""
            if pdf_path:
                archived_record = attach_student_library_pdf_path(archived_record["id"], pdf_path) or archived_record
            session_metadata["archived_record_id"] = archived_record["id"]
            archive_result = {
                "created": True,
                "updated_existing_record": bool(linked_record_id),
                "idempotent_reuse": False,
                "record": _serialize_wrong_question_record_for_response(archived_record),
            }
            session = update_wrong_question_chat_session(
                normalized_session_id,
                status="archived",
                current_stage="ready_to_archive",
                summary_text=summary_text,
                metadata_json=session_metadata,
            ) or session
            if isinstance(run, dict):
                updated_run = update_wrong_question_ingestion_run(
                    run["id"],
                    status="archived",
                    current_step="archived",
                    chat_session_id=normalized_session_id,
                )
                if updated_run:
                    run = updated_run
    else:
        session = update_wrong_question_chat_session(
            normalized_session_id,
            current_stage=next_stage,
            summary_text=summary_text,
            metadata_json=session_metadata,
        ) or session

    serialized = _serialize_wrong_question_chat_session_for_response(get_wrong_question_chat_session(normalized_session_id))
    return jsonify(
        {
            "ok": True,
            "session": serialized,
            "assistant_message": assistant_message,
            "archive": archive_result,
        }
    )


@app.route("/api/wrong-question-chats/<session_id>", methods=["GET"])
def api_wrong_question_chat_detail(session_id: str):
    user, error = _require_auth()
    if error:
        return error
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return jsonify({"error": "session_id is required"}), 400
    session = get_wrong_question_chat_session(normalized_session_id)
    if not session or not _can_access_wrong_question_chat_session(user, session):
        return jsonify({"error": "not found"}), 404
    serialized = _serialize_wrong_question_chat_session_for_response(session)
    if serialized is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"session": serialized})


@app.route("/api/wrong-question-ingestion-assets/<path:filename>", methods=["GET"])
def api_wrong_question_ingestion_asset_file(filename: str):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/api/profile-avatar-files/<path:filename>", methods=["GET"])
def api_profile_avatar_file(filename: str):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/api/wrong-question-practice-packs", methods=["GET"])
def api_wrong_question_practice_pack_list():
    user, error = _require_auth()
    if error:
        return error
    try:
        class_id = int(request.args.get("class_id") or 0)
    except (TypeError, ValueError):
        class_id = 0
    if not class_id:
        return jsonify({"error": "class_id is required"}), 400
    cls = _require_accessible_class(user, class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    jobs = list_wrong_question_practice_pack_jobs_for_class(
        organization_id=int(cls.get("organization_id") or user.get("organization_id") or 0),
        class_id=class_id,
    )
    return jsonify({
        "items": [
            serialized
            for serialized in (_serialize_wrong_question_practice_pack_job_for_response(job) for job in jobs)
            if serialized is not None
        ]
    })


@app.route("/api/wrong-question-practice-packs", methods=["POST"])
def api_wrong_question_practice_pack_create():
    user, error = _require_auth()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    if not has_api_key():
        return jsonify({"error": "系统 API Key 未配置，请联系管理员"}), 400

    try:
        class_id = int(data.get("class_id") or 0)
    except (TypeError, ValueError):
        class_id = 0
    mode = str(data.get("mode") or "").strip().lower()
    target = str(data.get("target") or "").strip()
    volume = str(data.get("volume") or "").strip().lower()
    if not class_id:
        return jsonify({"error": "class_id is required"}), 400
    cls = _require_accessible_class(user, class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    if mode not in {"topic", "reason"}:
        return jsonify({"error": "mode must be topic or reason"}), 400
    if volume not in {"light", "standard", "intensive"}:
        return jsonify({"error": "volume must be light, standard or intensive"}), 400
    if not target:
        return jsonify({"error": "target is required"}), 400

    organization_id = int(cls.get("organization_id") or user.get("organization_id") or 0)
    try:
        existing_job = find_active_wrong_question_practice_pack_job(
            organization_id=organization_id,
            class_id=class_id,
            created_by=int(user["id"]),
            mode=mode,
            target=target,
            volume=volume,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if existing_job:
        serialized = _serialize_wrong_question_practice_pack_job_for_response(existing_job)
        if serialized is None:
            return jsonify({"error": "not found"}), 404
        return jsonify({"job": serialized, "reused": True}), 200

    try:
        job = create_wrong_question_practice_pack_job(
            organization_id=organization_id,
            class_id=class_id,
            created_by=int(user["id"]),
            mode=mode,
            target=target,
            volume=volume,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    _start_wrong_question_practice_pack_thread(
        job_id=int(job["id"]),
        user={
            "id": int(user["id"]),
            "organization_id": organization_id,
            "display_name": user.get("display_name") or user.get("username") or "",
        },
    )
    serialized = _serialize_wrong_question_practice_pack_job_for_response(job)
    return jsonify({"job": serialized, "reused": False}), 202


@app.route("/api/wrong-question-practice-packs/<int:job_id>", methods=["GET"])
def api_wrong_question_practice_pack_detail(job_id: int):
    user, error = _require_auth()
    if error:
        return error
    job = get_wrong_question_practice_pack_job(job_id)
    if not job or not _can_access_wrong_question_practice_pack_job(user, job):
        return jsonify({"error": "not found"}), 404
    serialized = _serialize_wrong_question_practice_pack_job_for_response(job)
    if serialized is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"job": serialized})


@app.route("/api/wrong-question-practice-packs/<int:job_id>/download", methods=["GET"])
def api_wrong_question_practice_pack_download(job_id: int):
    user, error = _require_auth()
    if error:
        return error
    job = get_wrong_question_practice_pack_job(job_id)
    if not job or not _can_access_wrong_question_practice_pack_job(user, job):
        return jsonify({"error": "not found"}), 404
    if str(job.get("status") or "") not in {"ready", "partial_failed"}:
        return jsonify({"error": "practice pack is not ready"}), 409
    zip_path = Path(str(job.get("zip_path") or "").strip())
    if not zip_path or not zip_path.is_file():
        return jsonify({"error": "zip not found"}), 404

    cls = get_class(int(job.get("class_id") or 0)) or {}
    class_name = _safe_pdf_download_filename_part(cls.get("name"), f"class-{job.get('class_id') or job_id}")
    export_date = datetime.now().strftime("%Y-%m-%d")
    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{class_name}错题练习包_{export_date}.zip",
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
        record_source = str(record.get("source") or "").strip()
        if record_source not in {"wechat_mp", "ai_chat"}:
            return jsonify({"error": "selected records must be local wrong questions"}), 400
        if str(record.get("recognition_status") or "") != "recognized":
            return jsonify({"error": "selected records must be recognized before generating practice"}), 400
        if str(record.get("archive_status") or "").strip() == "archived":
            return jsonify({"error": "selected records must stay active before generating practice"}), 400
        if record_source == "ai_chat":
            confirmation_status = _normalize_wrong_question_confirmation_status(record)
            if confirmation_status not in {"confirmed", "not_required"}:
                return jsonify({"error": "selected ai chat records must be confirmed before generating practice"}), 400
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
    return jsonify(list_consultations_for_actor(
        user,
        query=request.args.get("q", ""),
        search_mode=request.args.get("search_mode", "fuzzy"),
        scope=request.args.get("scope", "current"),
        ownership=request.args.get("ownership", "all"),
    ))


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
    item = get_consultation_for_actor(user, consultation_id)
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
    try:
        item = create_consultation(
            request.json or {},
            user["organization_id"],
            assigned_user_id=assigned_user_id,
            created_by_user_id=user["id"],
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(item), 201


@app.route("/api/consultations/<int:consultation_id>", methods=["PUT"])
def api_consultation_update(consultation_id):
    user, error = _require_auth()
    if error:
        return error
    data = request.json or {}
    if isinstance(data, dict) and "teacher_id" in data:
        resolved = resolve_teacher_username_to_user_id(data["teacher_id"])
        if resolved is not None:
            data["assigned_user_id"] = resolved
        elif not data["teacher_id"]:
            data["assigned_user_id"] = None
    try:
        item = update_consultation_for_actor(user, consultation_id, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    if not item:
        return jsonify({"error": "not found"}), 404
    return jsonify(item)


@app.route("/api/consultations/<int:consultation_id>/enter-class", methods=["POST"])
def api_consultation_enter_class(consultation_id):
    user, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    try:
        result = enter_consultation_class(
            consultation_id=consultation_id,
            payload=payload,
            organization_id=None if user.get("role") == "super_owner" else user.get("organization_id"),
            actor_user_id=user["id"],
            member_user_id=user["id"] if user.get("role") == "member" else None,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not result:
        return jsonify({"error": "not found"}), 404
    return jsonify(result)


@app.route("/api/consultations/<int:consultation_id>/test-images", methods=["POST"])
def api_consultation_test_image_upload(consultation_id):
    user, error = _require_auth()
    if error:
        return error
    image = request.files.get("image")
    if image is None or not image.filename:
        return jsonify({"error": "image is required"}), 400
    suffix = Path(image.filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        return jsonify({"error": "只支持 png、jpg、jpeg、webp 图片"}), 400
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_filename = image.filename
    filename = f"consultation-test-{consultation_id}-{int(time() * 1000)}-{secure_filename(original_filename)}"
    save_path = UPLOAD_DIR / filename
    image.save(save_path)
    image_payload = {
        "url": f"/api/consultation-test-images/{filename}",
        "filename": original_filename,
    }
    try:
        item = append_consultation_test_image_for_actor(user, consultation_id, image_payload)
    except PermissionError as exc:
        save_path.unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 403
    if not item:
        save_path.unlink(missing_ok=True)
        return jsonify({"error": "not found"}), 404
    return jsonify({"image": image_payload, "item": item}), 201


@app.route("/api/consultations/<int:consultation_id>/test-images/<int:image_index>", methods=["DELETE"])
def api_consultation_test_image_delete(consultation_id, image_index):
    user, error = _require_auth()
    if error:
        return error
    try:
        item = remove_consultation_test_image_for_actor(user, consultation_id, image_index)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    if not item:
        return jsonify({"error": "not found"}), 404
    return jsonify({"item": item})


@app.route("/api/consultation-test-images/<path:filename>", methods=["GET"])
def api_consultation_test_image_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


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


@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    user, error = _require_auth()
    if error:
        return error

    role = str(user.get("role") or "")
    payload = {"role": role}
    if role == "member":
        payload["member"] = _dashboard_build_member_payload(user)
    elif role in {"owner", "admin"}:
        payload["organization"] = _dashboard_build_organization_payload(user)
    else:
        payload["platform"] = _dashboard_build_platform_payload(user)
    return jsonify(payload)


@app.route("/api/classes", methods=["GET"])
def api_classes_list():
    user, error = _require_auth()
    if error:
        return error
    scope = (request.args.get("scope") or "current").strip().lower()
    if scope not in {"current", "history", "all"}:
        return jsonify({"error": "scope must be current, history, or all"}), 400
    if user.get("role") in {"super_owner", "owner", "admin"}:
        return jsonify(list_classes_for_actor(user, scope=scope))
    return jsonify(_filter_classes_for_user(user, list_classes(scope=scope)))


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
    class_number = (data.get("class_number") or "").strip()
    current_grade = (data.get("current_grade") or grade).strip()
    class_type = (data.get("class_type") or "group").strip() or "group"
    student_ids = data.get("student_ids") or []
    if not isinstance(student_ids, list):
        return jsonify({"error": "student_ids must be a list"}), 400
    if class_type == "group" and not name and not class_number:
        return jsonify({"error": "班级名称不能为空"}), 400
    if class_type in {"1v1", "1v2", "1v3"} and not student_ids:
        return jsonify({"error": "请选择学员"}), 400
    if not subject:
        return jsonify({"error": "学科不能为空"}), 400
    try:
        cid = save_class(
            name=name,
            subject=subject,
            grade=grade,
            teacher_name=data.get("teacher_name", "").strip(),
            teacher_email=data.get("teacher_email", "").strip(),
            organization_id=user.get("organization_id"),
            stage=(data.get("stage") or "").strip(),
            current_grade=current_grade,
            class_number=class_number,
            class_type=class_type,
            student_ids=student_ids,
            cohort_year=data.get("cohort_year"),
            show_cohort_year=bool(data.get("show_cohort_year", False)),
            is_bridge=bool(data.get("is_bridge")),
            bridge_target=(data.get("bridge_target") or "").strip(),
            content_track=(data.get("content_track") or "").strip(),
            teacher_user_id=data.get("teacher_user_id"),
        )
    except ValueError:
        return jsonify({"error": "请选择本机构学员"}), 400
    cls = get_class(cid)
    return jsonify({"id": cid, "name": cls["name"] if cls else name}), 201


@app.route("/api/students", methods=["GET"])
def api_students_list():
    user, error = _require_staff()
    if error:
        return error
    include_archived = str(request.args.get("include_archived") or "").strip().lower() in {"1", "true", "yes"}
    return jsonify({"students": list_students_for_organization(user.get("organization_id"), include_archived=include_archived)})


@app.route("/api/students/duplicates", methods=["GET"])
def api_students_duplicates():
    user, error = _require_staff()
    if error:
        return error
    name = request.args.get("name") or ""
    return jsonify({"students": list_duplicate_student_profiles(name, user.get("organization_id"))})


@app.route("/api/students", methods=["POST"])
def api_students_create():
    user, error = _require_staff()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    try:
        student = create_student_profile(
            data.get("name") or "",
            source=data.get("source") or "",
            parent_contact=data.get("parent_contact") or "",
            organization_id=user.get("organization_id"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"student": student}), 201


@app.route("/api/students/<int:student_id>", methods=["GET"])
def api_student_profile_get(student_id):
    user, error = _require_auth()
    if error:
        return error
    student = get_student_profile(student_id, user.get("organization_id"))
    if not student:
        return jsonify({"error": "not found"}), 404
    if not _member_can_read_student_profile(user, student_id):
        return jsonify({"error": "forbidden"}), 403
    return jsonify({"student": student})


@app.route("/api/students/<int:student_id>", methods=["PUT"])
def api_student_profile_update(student_id):
    user, error = _require_staff()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    try:
        student = update_student_profile(
            student_id,
            data.get("name") or "",
            source=data.get("source") or "",
            parent_contact=data.get("parent_contact") or "",
            organization_id=user.get("organization_id"),
        )
    except LookupError:
        return jsonify({"error": "not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"student": student})


@app.route("/api/students/<int:student_id>", methods=["DELETE"])
def api_student_profile_delete(student_id):
    user, error = _require_staff()
    if error:
        return error
    try:
        result = delete_or_archive_student_profile(
            student_id,
            user.get("organization_id"),
            actor_user_id=int(user["id"]),
        )
    except LookupError:
        return jsonify({"error": "not found"}), 404
    memory_cleanup = result.pop("memory_cleanup", {}) or {}
    if memory_cleanup.get("operation_ids"):
        _dispatch_class_commentary_memory_best_effort()
    graph_cleanup = result.pop("graph_cleanup", {}) or {}
    if graph_cleanup.get("operation_ids"):
        _dispatch_class_commentary_graph_best_effort()
    return jsonify(result)


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
    if user.get("role") == "member":
        return jsonify({"error": "forbidden"}), 403
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
    if user.get("role") == "member":
        return jsonify({"error": "forbidden"}), 403
    _, error = _get_accessible_class_or_error(user, class_id)
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    student_id = int(data.get("student_id") or 0)
    if not student_id:
        return jsonify({"error": "请选择已有学员"}), 400
    try:
        student = add_existing_student_to_class(class_id, student_id)
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({
        "student": student,
        "requested_name": student["name"],
        "deduplicated": False,
    }), 201


@app.route("/api/classes/<int:class_id>/students/<int:student_id>", methods=["DELETE"])
def api_class_students_delete(class_id, student_id):
    user, error = _require_auth()
    if error:
        return error
    if user.get("role") == "member":
        return jsonify({"error": "forbidden"}), 403
    _, error = _get_accessible_class_or_error(user, class_id)
    if error:
        return error
    removed = remove_student_from_class(class_id, student_id)
    return jsonify({"ok": True, "removed": removed})


@app.route("/api/classes/<int:class_id>/history", methods=["GET"])
def api_class_history(class_id):
    user, error = _require_auth()
    if error:
        return error
    _, error = _get_accessible_class_or_error(user, class_id)
    if error:
        return error
    return jsonify({"items": list_class_history(class_id)})


@app.route("/api/students/<int:student_id>/class-history", methods=["GET"])
def api_student_class_history(student_id):
    user, error = _require_auth()
    if error:
        return error
    visible_items = []
    for item in list_student_class_history(student_id):
        cls, class_error = _get_accessible_class_or_error(user, int(item["class_id"]))
        if cls and not class_error:
            visible_items.append(item)
    return jsonify({"items": visible_items})


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

    invite = get_active_class_invite_by_code(invite_code)
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


def _wrong_question_practice_pack_dir(job_id: int) -> Path:
    pack_dir = PDF_DIR / "wrong_question_practice_packs" / f"pack-{job_id}"
    pack_dir.mkdir(parents=True, exist_ok=True)
    return pack_dir


def _wrong_question_practice_pack_student_pdf_path(job_id: int, student_id: int) -> Path:
    return _wrong_question_practice_pack_dir(job_id) / f"student-{student_id}.pdf"


def _wrong_question_practice_pack_zip_path(job_id: int) -> Path:
    return _wrong_question_practice_pack_dir(job_id) / "practice-pack.zip"


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
    class_number = (data.get("class_number") or "").strip()
    current_grade = (data.get("current_grade") or grade).strip()
    class_type = (data.get("class_type") or cls.get("class_type") or "group").strip() or "group"
    if class_type == "group" and not name and not class_number:
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
        stage=(data.get("stage") or "").strip(),
        current_grade=current_grade,
        class_number=class_number,
        class_type=class_type,
        cohort_year=data.get("cohort_year"),
        show_cohort_year=bool(data.get("show_cohort_year", False)),
        is_bridge=bool(data.get("is_bridge")),
        bridge_target=(data.get("bridge_target") or "").strip(),
        content_track=(data.get("content_track") or "").strip(),
        actor_user_id=int(user["id"]),
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
    result = db_delete_class(class_id)
    if result.get("action") == "deleted":
        return jsonify({"ok": True})
    memory_cleanup = result.pop("memory_cleanup", None)
    if isinstance(memory_cleanup, dict) and memory_cleanup.get("operation_ids"):
        _dispatch_class_commentary_memory_best_effort()
    return jsonify({"ok": True, **result})


@app.route("/api/review-plans", methods=["GET"])
def api_lessons_list():
    user, error = _require_auth()
    if error:
        return error
    month = request.args.get("month", "")
    class_id = request.args.get("class_id", 0, type=int)
    scope = (request.args.get("scope") or "current").strip().lower()
    if scope not in {"current", "history", "all"}:
        return jsonify({"error": "scope must be current, history, or all"}), 400
    page = request.args.get("page", 1, type=int) or 1
    page_size = request.args.get("page_size", 12, type=int) or 12
    if page < 1:
        return jsonify({"error": "page must be greater than 0"}), 400
    if page_size < 1 or page_size > 100:
        return jsonify({"error": "page_size must be between 1 and 100"}), 400
    result = list_lessons_page_for_actor(
        user,
        month_str=month if month else "",
        class_id=class_id if class_id else 0,
        class_scope=scope,
        page=page,
        page_size=page_size,
    )
    return jsonify({
        "items": _serialize_lessons_for_response(result.get("items", [])),
        "total": int(result.get("total") or 0),
        "page": int(result.get("page") or page),
        "page_size": int(result.get("page_size") or page_size),
    })


@app.route("/api/review-plans/failure-notifications", methods=["GET"])
def api_review_plan_failure_notifications_list():
    user, error = _require_auth()
    if error:
        return error
    items = []
    for notification in list_unseen_review_plan_failure_notifications(int(user["id"]), limit=500):
        serialized = _serialize_review_plan_failure_notification(user, notification)
        if serialized is not None:
            items.append(serialized)
    return jsonify({"items": items})


@app.route("/api/review-plans/failure-notifications/seen", methods=["POST"])
def api_review_plan_failure_notifications_seen():
    user, error = _require_auth()
    if error:
        return error
    payload = request.json if request.is_json else {}
    raw_version_ids = payload.get("version_ids") if isinstance(payload, dict) else None
    if not isinstance(raw_version_ids, list) or len(raw_version_ids) > 100:
        return jsonify({"error": "version_ids must be a list with at most 100 items"}), 400
    if any(isinstance(version_id, bool) or not isinstance(version_id, int) or version_id <= 0 for version_id in raw_version_ids):
        return jsonify({"error": "version_ids must contain positive integers"}), 400
    version_ids = sorted(set(raw_version_ids))
    for version_id in version_ids:
        version = get_review_plan_version(version_id)
        lesson = get_lesson(int((version or {}).get("lesson_id") or 0))
        if not version or str(version.get("status") or "") != "failed" or not lesson or not _can_access_lesson(user, lesson):
            return jsonify({"error": "not found"}), 404
    seen_version_ids = mark_review_plan_failure_notifications_seen(int(user["id"]), version_ids)
    return jsonify({"seen_version_ids": seen_version_ids})


@app.route("/api/review-plans/<int:lesson_id>", methods=["GET"])
def api_lesson_get(lesson_id):
    user, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        return jsonify({"error": "not found"}), 404
    serialized_lesson = _serialize_lesson_for_response(lesson, include_versions=True, include_runtime=True)
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
    for version in list_review_plan_versions(lesson_id):
        pdf_path = str(version.get("pdf_path") or "")
        if pdf_path and Path(pdf_path).exists():
            Path(pdf_path).unlink(missing_ok=True)
    db_delete_lesson(lesson_id)
    return jsonify({"ok": True})


@app.route("/api/review-plans/<int:lesson_id>/versions/<int:version_id>/pdf", methods=["GET"])
def api_review_plan_version_pdf(lesson_id, version_id):
    user, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        abort(404)
    pdf_path = _get_ready_review_plan_version_pdf_path(lesson_id, version_id)
    if not pdf_path:
        abort(404)
    return send_file(pdf_path, mimetype="application/pdf", download_name=Path(pdf_path).name)


@app.route("/api/review-plans/<int:lesson_id>/versions/<int:version_id>/download", methods=["GET"])
def api_review_plan_version_download(lesson_id, version_id):
    user, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        abort(404)
    pdf_path = _get_ready_review_plan_version_pdf_path(lesson_id, version_id)
    if not pdf_path:
        abort(404)
    return send_file(pdf_path, as_attachment=True, download_name=Path(pdf_path).name)


@app.route("/api/review-plans/<int:lesson_id>/versions/<int:version_id>/rerender-pdf", methods=["POST"])
def api_review_plan_version_rerender_pdf(lesson_id, version_id):
    user, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        return jsonify({"error": "not found"}), 404
    version = get_review_plan_version_for_lesson(lesson_id, version_id)
    if not version:
        return jsonify({"error": "not found"}), 404
    if str(version.get("status") or "") != "ready":
        return jsonify({"error": "只有已生成的版本可以重新渲染 PDF"}), 400
    plan = version.get("plan") if isinstance(version.get("plan"), dict) else {}
    if not plan:
        return jsonify({"error": "当前版本缺少复习计划内容，无法重新渲染 PDF"}), 400
    try:
        pdf_path = _render_review_plan_version_pdf(lesson_id=lesson_id, version=version, plan=plan)
        update_review_plan_version_pdf_path(version_id, pdf_path=pdf_path)
    except Exception:
        logger.exception("Review plan PDF rerender failed for lesson %s version %s", lesson_id, version_id)
        return jsonify({"error": "PDF 重新渲染失败，请稍后重试"}), 500
    lesson = get_lesson(lesson_id)
    serialized_lesson = _serialize_lesson_for_response(lesson, include_versions=True)
    if serialized_lesson is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(serialized_lesson)


@app.route("/api/review-plans/<int:lesson_id>/versions/<int:version_id>/make-current", methods=["POST"])
def api_review_plan_version_make_current(lesson_id, version_id):
    user, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        return jsonify({"error": "not found"}), 404
    version = get_review_plan_version_for_lesson(lesson_id, version_id)
    if not version:
        return jsonify({"error": "not found"}), 404
    if str(version.get("status") or "") != "ready":
        return jsonify({"error": "review plan version must be ready"}), 400
    pdf_path = str(version.get("pdf_path") or "")
    if not pdf_path or not Path(pdf_path).exists():
        return jsonify({"error": "当前版本的 PDF 文件不存在，无法设为当前版本"}), 400
    try:
        set_current_review_plan_version(lesson_id, version_id)
    except LookupError:
        return jsonify({"error": "not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    lesson = get_lesson(lesson_id)
    serialized_lesson = _serialize_lesson_for_response(lesson, include_versions=True)
    if serialized_lesson is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(serialized_lesson)


@app.route("/api/review-plans/<int:lesson_id>/regenerate", methods=["POST"])
def api_lesson_regenerate(lesson_id):
    user, error = _require_auth()
    if error:
        return error
    if not has_review_plan_api_key():
        return jsonify({"error": "系统 API Key 未配置，请联系管理员"}), 400

    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        return jsonify({"error": "not found"}), 404

    if lesson_has_active_review_plan_version(lesson_id):
        return jsonify({"error": "这份复习计划正在生成中，请稍后再试"}), 409

    raw_text = str(lesson.get("summary") or "").strip()
    if not raw_text:
        return jsonify({"error": "这份记录缺少课堂内容，无法重新生成"}), 400
    current_version = get_current_review_plan_version(lesson_id)
    current_source_text = str((current_version or {}).get("source_text") or "").strip()
    cleaned_source_text = str((current_version or {}).get("cleaned_source_text") or "").strip()
    source_text_hash_value = str((current_version or {}).get("source_text_hash") or "").strip()
    source_brief = (current_version or {}).get("source_brief") or {}
    has_source_artifact = bool(current_source_text or cleaned_source_text or source_text_hash_value or source_brief)
    source_text = current_source_text or raw_text
    generation_options, generation_options_error = _extract_generation_options_or_error(
        request.json if request.is_json else (request.form or {}),
        source="regenerate",
        fallback=(current_version or {}).get("generation_options"),
    )
    if generation_options_error:
        return generation_options_error

    organization_id = int(user["organization_id"])
    request_key = _current_ai_request_key()
    request_id = _build_review_plan_regenerate_request_id(
        user_id=int(user["id"]),
        lesson_id=lesson_id,
        request_key=request_key,
    )
    chat_provider = _review_plan_ai_provider_name()
    chat_model = _review_plan_chat_model_name()
    request_identity_claimed = False
    try:
        _claim_ai_request_identity(
            organization_id=organization_id,
            request_id=request_id,
        )
        request_identity_claimed = True
        ensure_feature_credits_available(
            organization_id=organization_id,
            feature_key="lesson_plan_generate",
        )
        version = create_review_plan_version(
            lesson_id=lesson_id,
            status="generating",
            created_by_user_id=int(user["id"]),
            request_key=request_key,
            request_id=request_id,
            chat_provider=chat_provider,
            chat_model=chat_model,
            same_lesson_materials=(current_version or {}).get("same_lesson_materials") or [],
            generation_options=generation_options,
            generation_options_source="regenerate",
        )
        if has_source_artifact:
            update_review_plan_version_source_artifact(
                int(version["id"]),
                source_text=source_text,
                cleaned_source_text=cleaned_source_text,
                source_text_hash=source_text_hash_value,
                source_brief=source_brief,
                source_type=str(((current_version or {}).get("source_pack") or {}).get("source_type") or "text"),
            )
            version = get_review_plan_version_for_lesson(lesson_id, int(version["id"])) or version
        _start_review_plan_generation_thread(
            lesson_id=lesson_id,
            version_id=int(version["id"]),
            user={
                "id": int(user["id"]),
                "organization_id": organization_id,
            },
            chat_provider=chat_provider,
            chat_model=chat_model,
            request_key=request_key,
            request_id=str(version.get("request_id") or request_id),
            same_lesson_materials=version.get("same_lesson_materials") or [],
            generation_options=version.get("generation_options"),
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

    return jsonify({"id": lesson_id, "version_id": int(version["id"]), "success": True, "status": "generating"}), 202


def _extract_same_lesson_materials(data) -> list[str]:
    raw_values: list[object] = []
    if hasattr(data, "getlist"):
        raw_values.extend(data.getlist("same_lesson_materials"))
    else:
        value = data.get("same_lesson_materials") if isinstance(data, dict) else None
        if isinstance(value, list):
            raw_values.extend(value)
        elif value is not None:
            raw_values.append(value)

    materials: list[str] = []
    for value in raw_values:
        if isinstance(value, str):
            pieces = [value]
        else:
            pieces = [str(value)]
        for piece in pieces:
            text = piece.strip()
            if text:
                materials.append(text)
    return materials


def _extract_generation_options_payload(data) -> object | None:
    if hasattr(data, "get") and data.get("generation_options") not in (None, ""):
        return data.get("generation_options")
    if not isinstance(data, dict) and not hasattr(data, "get"):
        return None

    payload: dict[str, object] = {}
    for key in ("schedule_mode", "daily_count", "user_requirements"):
        value = data.get(key)
        if value not in (None, ""):
            payload[key] = value
    if hasattr(data, "getlist"):
        values = [value for value in data.getlist("review_days") if value not in (None, "")]
        if values:
            payload["review_days"] = values if len(values) > 1 else values[0]
    else:
        value = data.get("review_days") if isinstance(data, dict) else None
        if value not in (None, ""):
            payload["review_days"] = value
    return payload or None


def _extract_generation_options_or_error(data, *, source: str, fallback: object | None = None):
    payload = _extract_generation_options_payload(data)
    try:
        return normalize_generation_options(payload if payload is not None else fallback, source=source), None
    except ValueError as exc:
        return None, (jsonify({"error": f"生成设置无效：{_readable_generation_options_error(str(exc))}"}), 400)


def _readable_generation_options_error(message: str) -> str:
    if "review_days must not be empty" in message:
        return "请至少填写一个复习日期点，例如 1,3,7"
    if "review_days must contain positive integers" in message:
        return "复习日期点只能填写 1 到 30 之间的正整数"
    if "review_days can contain at most" in message:
        return "自定义复习日期最多填写 30 个"
    if "review_days must be a list or comma string" in message:
        return "复习日期点请用逗号分隔，例如 1,3,7"
    if "daily_count must be a positive integer" in message:
        return "连续生成天数请填写 1 到 30 之间的正整数"
    if "daily_count must be at most" in message:
        return "连续生成天数最多 30 天"
    if "schedule_mode must be" in message:
        return "请选择有效的生成节奏"
    if "generation_options must be valid JSON" in message:
        return "生成设置格式不正确，请刷新页面后重试"
    return message or "请检查生成设置"


def _merge_review_plan_materials(primary_text: str, same_lesson_materials: list[str]) -> str:
    primary = (primary_text or "").strip()
    materials = [item.strip() for item in same_lesson_materials if item and item.strip()]
    if not materials:
        return primary
    sections = [f"【主课堂材料】\n{primary}"] if primary else []
    for index, material in enumerate(materials, start=1):
        sections.append(f"【同一节课补充材料 {index}】\n{material}")
    return "\n\n".join(sections).strip()


@app.route("/api/review-plans", methods=["POST"])
def api_lesson_create():
    user, error = _require_auth()
    if error:
        return error
    if not has_review_plan_api_key():
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
    same_lesson_materials = _extract_same_lesson_materials(data)
    generation_options, generation_options_error = _extract_generation_options_or_error(data, source="create")
    if generation_options_error:
        return generation_options_error
    
    input_type = data.get("input_type", "text")
    raw_text = ""
    audio_path = ""
    audio_request_key = None
    response_status = "pending"
    version_status = "generating"
    chat_provider = _review_plan_ai_provider_name()
    chat_model = _review_plan_chat_model_name()
    
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
            audio_request_key = _current_audio_upload_request_key()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            save_path = UPLOAD_DIR / f"audio_{ts}{ext}"
            file.save(str(save_path))
            
            if save_path.stat().st_size > REVIEW_PLAN_AUDIO_MAX_BYTES:
                save_path.unlink(missing_ok=True)
                return jsonify({"error": f"音频文件过大（最大 {REVIEW_PLAN_AUDIO_MAX_LABEL}）"}), 400
            audio_path = str(save_path)
            response_status = "transcribing"
            version_status = "transcribing"
        elif ext in {".txt", ".md", ".text"}:
            raw_text = file.read().decode("utf-8", errors="replace")
        else:
            return jsonify({"error": f"不支持的文件格式 {ext}"}), 400

    raw_text = _merge_review_plan_materials(raw_text, same_lesson_materials)
    if not raw_text and not audio_path:
        return jsonify({"error": "提取的总结内容为空"}), 400

    request_key = _current_ai_request_key()
    request_id = _build_review_plan_request_id(
        user_id=int(user["id"]),
        request_key=request_key,
    )
    request_identity_claimed = False
    organization_id = int(user["organization_id"])
    try:
        _claim_ai_request_identity(
            organization_id=organization_id,
            request_id=request_id,
        )
        request_identity_claimed = True
        ensure_feature_credits_available(
            organization_id=organization_id,
            feature_key="lesson_plan_generate",
        )
    except DuplicateAiRequestError as exc:
        if "已处理" in str(exc):
            existing_lesson = _find_existing_review_plan_lesson_for_request(
                organization_id=organization_id,
                request_id=request_id,
            )
            if existing_lesson:
                if audio_path:
                    Path(audio_path).unlink(missing_ok=True)
                status = str(existing_lesson.get("record_status") or "").strip()
                if not status:
                    status = "ready" if str(existing_lesson.get("pdf_path") or "").strip() else "pending"
                return jsonify({
                    "id": existing_lesson["id"],
                    "version_id": existing_lesson.get("current_version_id") or (existing_lesson.get("active_version") or {}).get("id"),
                    "success": True,
                    "status": status,
                    "duplicate": True,
                }), 202
        if audio_path:
            Path(audio_path).unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 409
    except CreditBalanceError as exc:
        if audio_path:
            Path(audio_path).unlink(missing_ok=True)
        if request_identity_claimed:
            _release_ai_request_identity(request_id)
        return jsonify({"error": str(exc)}), 402
    except Exception:
        if audio_path:
            Path(audio_path).unlink(missing_ok=True)
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
            created_by_user_id=int(user["id"]),
        )
        version = create_review_plan_version(
            lesson_id=lesson_id,
            status=version_status,
            created_by_user_id=int(user["id"]),
            audio_path=audio_path,
            audio_request_key=audio_request_key or "",
            request_key=request_key,
            request_id=request_id,
            chat_provider=chat_provider,
            chat_model=chat_model,
            same_lesson_materials=same_lesson_materials,
            generation_options=generation_options,
            generation_options_source="create",
        )
        _start_review_plan_generation_thread(
            lesson_id=lesson_id,
            version_id=int(version["id"]),
            user={
                "id": int(user["id"]),
                "organization_id": int(user["organization_id"]),
            },
            chat_provider=chat_provider,
            chat_model=chat_model,
            request_key=request_key,
            request_id=request_id,
            audio_path=audio_path,
            audio_request_key=audio_request_key,
            same_lesson_materials=same_lesson_materials,
            generation_options=generation_options,
        )
    except Exception:
        if lesson_id:
            db_delete_lesson(lesson_id)
        if audio_path:
            Path(audio_path).unlink(missing_ok=True)
        if request_identity_claimed:
            _release_ai_request_identity(request_id)
        raise
    return jsonify({"id": lesson_id, "version_id": int(version["id"]), "success": True, "status": response_status}), 202


@app.route("/api/class-commentary/skills", methods=["GET"])
def api_class_commentary_skills():
    user, error = _require_auth()
    if error:
        return error
    skills = _sync_configured_class_commentary_skills(user)
    capabilities = _class_commentary_capabilities()
    return jsonify({
        "skills": skills,
        "configured": bool(skills),
        "capabilities": capabilities,
    })


@app.route(
    "/api/class-commentary/skills/<string:skill_id>/versions",
    methods=["GET"],
)
def api_class_commentary_skill_versions(skill_id: str):
    user, error = _require_auth()
    if error:
        return error
    skill, skill_error = _get_accessible_class_commentary_skill_or_error(user, skill_id)
    if skill_error:
        return skill_error
    try:
        return jsonify(
            _class_commentary_skill_evolution_envelope(skill=skill, user=user)
        )
    except Exception as exc:
        if isinstance(
            exc,
            (
                ClassCommentarySkillCandidateRequestConflict,
                ClassCommentarySkillActivationRequestConflict,
                ClassCommentarySkillCandidateNotReady,
                ClassCommentarySkillCandidateStale,
                ClassCommentarySkillVersionConflict,
                LookupError,
                PermissionError,
                ValueError,
            ),
        ):
            return _class_commentary_skill_evolution_error_response(exc)
        raise


@app.route(
    "/api/class-commentary/skills/<string:skill_id>/candidates",
    methods=["POST"],
)
def api_class_commentary_skill_candidates(skill_id: str):
    user, error = _require_auth()
    if error:
        return error
    _, skill_error = _get_accessible_class_commentary_skill_or_error(user, skill_id)
    if skill_error:
        return skill_error
    capability_error = _require_class_commentary_skill_evolution_capability()
    if capability_error:
        return capability_error
    request_id, expected_version_id, payload_error = (
        _class_commentary_skill_change_request_payload()
    )
    if payload_error:
        return payload_error
    try:
        build = create_class_commentary_skill_candidate_build(
            organization_id=int(user["organization_id"]),
            skill_id=skill_id,
            actor_user_id=int(user["id"]),
            candidate_request_id=request_id,
            expected_active_version_id=expected_version_id,
        )
    except Exception as exc:
        if isinstance(
            exc,
            (
                ClassCommentarySkillCandidateRequestConflict,
                ClassCommentarySkillCandidateNotReady,
                ClassCommentarySkillVersionConflict,
                LookupError,
                PermissionError,
                ValueError,
            ),
        ):
            return _class_commentary_skill_evolution_error_response(exc)
        raise
    _dispatch_class_commentary_memory_best_effort()
    return jsonify(
        {
            "build": _serialize_class_commentary_skill_candidate_build_for_response(
                build
            )
        }
    ), 202


@app.route(
    "/api/class-commentary/skills/<string:skill_id>/versions/<int:version_id>/activate",
    methods=["POST"],
)
def api_class_commentary_skill_version_activate(skill_id: str, version_id: int):
    user, error = _require_auth()
    if error:
        return error
    _, skill_error = _get_accessible_class_commentary_skill_or_error(user, skill_id)
    if skill_error:
        return skill_error
    capability_error = _require_class_commentary_skill_evolution_capability()
    if capability_error:
        return capability_error
    request_id, expected_version_id, payload_error = (
        _class_commentary_skill_change_request_payload()
    )
    if payload_error:
        return payload_error
    try:
        event = activate_class_commentary_skill_candidate_version(
            organization_id=int(user["organization_id"]),
            skill_id=skill_id,
            actor_user_id=int(user["id"]),
            version_id=version_id,
            activation_request_id=request_id,
            expected_active_version_id=expected_version_id,
        )
        payload = _class_commentary_skill_activation_envelope(
            skill_id=skill_id,
            version_id=version_id,
            activation_event=event,
            user=user,
        )
    except Exception as exc:
        if isinstance(
            exc,
            (
                ClassCommentarySkillActivationRequestConflict,
                ClassCommentarySkillCandidateStale,
                ClassCommentarySkillVersionConflict,
                LookupError,
                PermissionError,
                ValueError,
            ),
        ):
            return _class_commentary_skill_evolution_error_response(exc)
        raise
    return jsonify(payload)


@app.route(
    "/api/class-commentary/skills/<string:skill_id>/versions/<int:version_id>/rollback",
    methods=["POST"],
)
def api_class_commentary_skill_version_rollback(skill_id: str, version_id: int):
    user, error = _require_auth()
    if error:
        return error
    _, skill_error = _get_accessible_class_commentary_skill_or_error(user, skill_id)
    if skill_error:
        return skill_error
    capability_error = _require_class_commentary_skill_evolution_capability()
    if capability_error:
        return capability_error
    request_id, expected_version_id, payload_error = (
        _class_commentary_skill_change_request_payload()
    )
    if payload_error:
        return payload_error
    try:
        event = rollback_class_commentary_skill_version(
            organization_id=int(user["organization_id"]),
            skill_id=skill_id,
            actor_user_id=int(user["id"]),
            version_id=version_id,
            activation_request_id=request_id,
            expected_active_version_id=expected_version_id,
        )
        payload = _class_commentary_skill_activation_envelope(
            skill_id=skill_id,
            version_id=version_id,
            activation_event=event,
            user=user,
        )
    except Exception as exc:
        if isinstance(
            exc,
            (
                ClassCommentarySkillActivationRequestConflict,
                ClassCommentarySkillVersionConflict,
                LookupError,
                PermissionError,
                ValueError,
            ),
        ):
            return _class_commentary_skill_evolution_error_response(exc)
        raise
    return jsonify(payload)


@app.route("/api/class-commentary/capabilities", methods=["GET"])
def api_class_commentary_capabilities():
    _, error = _require_auth()
    if error:
        return error
    return jsonify(_class_commentary_capabilities())


def _curriculum_version_response(version: dict) -> dict:
    result = dict(version)
    for field in ("source_counts_json", "import_counts_json"):
        try:
            result[field.removesuffix("_json")] = json.loads(str(result.pop(field, "{}")))
        except json.JSONDecodeError:
            result[field.removesuffix("_json")] = {}
    return result


def _curriculum_error_response(exc: Exception):
    if isinstance(exc, LookupError):
        return jsonify({"error": "not found"}), 404
    if isinstance(exc, (curriculum_registry.CurriculumConflictError, LearningGraphRetryConflict)):
        return jsonify({"error": str(exc)}), 409
    if isinstance(exc, (curriculum_registry.CurriculumValidationError, LearningGraphValidationError, ValueError)):
        return jsonify({"error": str(exc)}), 400
    raise exc


def _curriculum_version_for_user(user: dict, version_id: int) -> Optional[dict]:
    with get_conn() as conn:
        version = curriculum_registry.get_curriculum_version(conn, version_id)
    if not version:
        return None
    if str(version.get("status") or "") != "active" and user.get("role") != "super_owner":
        return None
    return version


@app.route("/api/class-commentary/curriculum/versions", methods=["GET"])
def api_class_commentary_curriculum_versions():
    user, error = _require_auth()
    if error:
        return error
    with get_conn() as conn:
        versions = curriculum_registry.list_curriculum_versions(conn)
    if user.get("role") != "super_owner":
        versions = [item for item in versions if str(item.get("status") or "") == "active"]
    return jsonify({"versions": [_curriculum_version_response(item) for item in versions]})


@app.route("/api/class-commentary/curriculum/versions/diff", methods=["GET"])
def api_class_commentary_curriculum_version_diff():
    user, error = _require_super_owner()
    if error:
        return error
    from_version_id = request.args.get("from_version_id", type=int) or 0
    to_version_id = request.args.get("to_version_id", type=int) or 0
    if from_version_id <= 0 or to_version_id <= 0:
        return jsonify({"error": "from_version_id and to_version_id are required"}), 400
    try:
        with get_conn() as conn:
            result = curriculum_registry.diff_curriculum_versions(
                conn, from_version_id, to_version_id
            )
    except Exception as exc:
        return _curriculum_error_response(exc)
    return jsonify({"diff": result})


@app.route(
    "/api/class-commentary/curriculum/versions/<int:version_id>/<string:action>",
    methods=["POST"],
)
def api_class_commentary_curriculum_version_action(version_id: int, action: str):
    user, error = _require_super_owner()
    if error:
        return error
    if action not in {"review", "activate", "rollback"}:
        return jsonify({"error": "not found"}), 404
    try:
        with get_conn() as conn:
            if action == "review":
                version = curriculum_registry.review_curriculum_version(
                    conn, version_id, actor_user_id=int(user["id"])
                )
            elif action == "activate":
                version = curriculum_registry.activate_curriculum_version(
                    conn, version_id, actor_user_id=int(user["id"])
                )
            else:
                version = curriculum_registry.rollback_curriculum_version(
                    conn, version_id, actor_user_id=int(user["id"])
                )
    except Exception as exc:
        return _curriculum_error_response(exc)
    return jsonify({"version": _curriculum_version_response(version)})


@app.route("/api/class-commentary/curriculum/books", methods=["GET"])
def api_class_commentary_curriculum_books():
    user, error = _require_auth()
    if error:
        return error
    version_id = request.args.get("version_id", type=int) or 0
    if version_id <= 0 or not _curriculum_version_for_user(user, version_id):
        return jsonify({"error": "not found"}), 404
    with get_conn() as conn:
        books = curriculum_registry.list_curriculum_books(conn, version_id)
    return jsonify({"books": books})


@app.route("/api/class-commentary/curriculum/catalog", methods=["GET"])
def api_class_commentary_curriculum_catalog():
    user, error = _require_auth()
    if error:
        return error
    version_id = request.args.get("version_id", type=int) or 0
    if version_id <= 0 or not _curriculum_version_for_user(user, version_id):
        return jsonify({"error": "not found"}), 404
    try:
        with get_conn() as conn:
            result = curriculum_registry.list_curriculum_nodes(
                conn,
                version_id=version_id,
                stage_key=str(request.args.get("stage_key") or "").strip(),
                grade_key=str(request.args.get("grade_key") or "").strip(),
                book_upstream_id=str(request.args.get("book_upstream_id") or "").strip(),
                chapter_upstream_id=str(request.args.get("chapter_upstream_id") or "").strip(),
                query=str(request.args.get("query") or "").strip(),
                node_type=str(request.args.get("node_type") or "").strip(),
                page=request.args.get("page", type=int) or 1,
                page_size=request.args.get("page_size", type=int) or 50,
            )
    except Exception as exc:
        return _curriculum_error_response(exc)
    return jsonify(result)


@app.route("/api/class-commentary/curriculum/nodes/<int:node_id>", methods=["GET"])
def api_class_commentary_curriculum_node(node_id: int):
    user, error = _require_auth()
    if error:
        return error
    book_node_id = request.args.get("book_node_id", type=int) or None
    with get_conn() as conn:
        node = curriculum_registry.get_curriculum_node_detail(
            conn, node_id, book_node_id=book_node_id
        )
    if not node or not _curriculum_version_for_user(user, int(node["version_id"])):
        return jsonify({"error": "not found"}), 404
    return jsonify({"node": node})


@app.route(
    "/api/class-commentary/curriculum/classes/<int:class_id>/assignment",
    methods=["GET", "PUT"],
)
def api_class_commentary_curriculum_class_assignment(class_id: int):
    user, error = _require_auth()
    if error:
        return error
    cls = _require_accessible_class(user, class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    if request.method == "GET":
        with get_conn() as conn:
            assignment = curriculum_registry.get_effective_class_curriculum_scope(conn, class_id)
        return jsonify({"assignment": assignment})
    if user.get("role") not in {"super_owner", "owner", "admin"}:
        return jsonify({"error": "无权限"}), 403
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return payload_error
    try:
        version_id = int((data or {}).get("version_id") or 0)
        raw_expected = (data or {}).get("expected_assignment_id")
        expected_assignment_id = int(raw_expected) if raw_expected not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({"error": "assignment identifiers must be integers"}), 400
    request_id = str((data or {}).get("request_id") or "").strip()
    try:
        with get_conn() as conn:
            if str((data or {}).get("assignment_mode") or "") == "auto":
                assignment = curriculum_registry.reset_class_curriculum_to_auto(
                    conn,
                    organization_id=int(user["organization_id"]),
                    class_id=class_id,
                    actor_user_id=int(user["id"]),
                    request_id=request_id,
                    expected_cas_token=str((data or {}).get("expected_cas_token") or ""),
                    note=str((data or {}).get("note") or "").strip(),
                )
            elif isinstance((data or {}).get("book_node_ids"), list):
                assignment = curriculum_registry.replace_class_curriculum_books(
                    conn,
                    organization_id=int(user["organization_id"]),
                    class_id=class_id,
                    version_id=version_id,
                    book_node_ids=(data or {}).get("book_node_ids") or [],
                    primary_book_node_id=(data or {}).get("primary_book_node_id"),
                    actor_user_id=int(user["id"]),
                    request_id=request_id,
                    expected_cas_token=str((data or {}).get("expected_cas_token") or ""),
                    note=str((data or {}).get("note") or "").strip(),
                )
            else:
                assignment = curriculum_registry.assign_curriculum_book(
                    conn,
                    organization_id=int(user["organization_id"]),
                    class_id=class_id,
                    version_id=version_id,
                    book_node_id=int((data or {}).get("book_node_id") or 0),
                    actor_user_id=int(user["id"]),
                    request_id=request_id,
                    expected_assignment_id=expected_assignment_id,
                    note=str((data or {}).get("note") or "").strip(),
                )
    except Exception as exc:
        return _curriculum_error_response(exc)
    return jsonify({"assignment": assignment})


@app.route("/api/class-commentary/curriculum/unmapped", methods=["GET"])
def api_class_commentary_curriculum_unmapped():
    user, error = _require_auth()
    if error:
        return error
    allowed_class_ids = None
    if user.get("role") not in {"super_owner", "owner", "admin"}:
        allowed_class_ids = get_user_class_ids(int(user["id"]))
    try:
        result = list_graph_unmapped_candidates(
            organization_id=int(user["organization_id"]),
            allowed_class_ids=allowed_class_ids,
            status=str(request.args.get("status") or "pending"),
            page=request.args.get("page", type=int) or 1,
            page_size=request.args.get("page_size", type=int) or 50,
        )
    except Exception as exc:
        return _curriculum_error_response(exc)
    return jsonify(result)


@app.route(
    "/api/class-commentary/curriculum/unmapped/<string:candidate_id>/actions",
    methods=["POST"],
)
def api_class_commentary_curriculum_unmapped_action(candidate_id: str):
    user, error = _require_auth()
    if error:
        return error
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return payload_error
    action = str((data or {}).get("action") or "").strip()
    if user.get("role") not in {"super_owner", "owner", "admin"} and action != "propose_new":
        return jsonify({"error": "无权限"}), 403
    with get_conn() as conn:
        candidate_scope = conn.execute(
            """
            SELECT generation.class_id
            FROM class_commentary_graph_unmapped_candidates candidate
            JOIN class_commentary_graph_extraction_jobs job ON job.id=candidate.extraction_job_id
            JOIN class_commentary_generations generation ON generation.id=job.generation_id
            WHERE candidate.candidate_id=? AND candidate.organization_id=?
            """,
            (candidate_id, int(user["organization_id"])),
        ).fetchone()
    if not candidate_scope or not _require_accessible_class(user, int(candidate_scope["class_id"])):
        return jsonify({"error": "not found"}), 404
    try:
        result = resolve_graph_unmapped_candidate(
            candidate_id,
            organization_id=int(user["organization_id"]),
            actor_user_id=int(user["id"]),
            request_id=str((data or {}).get("request_id") or "").strip(),
            action=action,
            target_knowledge_point_key=str((data or {}).get("target_knowledge_point_key") or "").strip(),
            proposed_name=str((data or {}).get("proposed_name") or "").strip(),
            note=str((data or {}).get("note") or "").strip(),
        )
    except Exception as exc:
        return _curriculum_error_response(exc)
    _dispatch_class_commentary_graph_best_effort()
    return jsonify({"result": result})


@app.route("/api/class-commentary/curriculum/audit", methods=["GET"])
def api_class_commentary_curriculum_audit():
    user, error = _require_staff()
    if error:
        return error
    with get_conn() as conn:
        events = curriculum_registry.list_curriculum_audit_events(
            conn,
            organization_id=int(user["organization_id"]),
            include_global=user.get("role") == "super_owner",
            limit=request.args.get("limit", type=int) or 200,
        )
    return jsonify({"events": events})


@app.route("/api/class-commentary/curriculum/proposals", methods=["GET"])
def api_class_commentary_curriculum_proposals():
    user, error = _require_staff()
    if error:
        return error
    try:
        with get_conn() as conn:
            proposals = curriculum_registry.list_organization_knowledge_point_proposals(
                conn,
                organization_id=int(user["organization_id"]),
                status=str(request.args.get("status") or "proposed"),
            )
    except Exception as exc:
        return _curriculum_error_response(exc)
    return jsonify({"proposals": proposals})


@app.route(
    "/api/class-commentary/curriculum/proposals/<int:proposal_id>/review",
    methods=["POST"],
)
def api_class_commentary_curriculum_proposal_review(proposal_id: int):
    user, error = _require_staff()
    if error:
        return error
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return payload_error
    if not isinstance((data or {}).get("approve"), bool):
        return jsonify({"error": "approve must be a boolean"}), 400
    request_id = str((data or {}).get("request_id") or "").strip()
    try:
        with get_conn() as conn:
            review = curriculum_registry.review_organization_knowledge_point_proposal(
                conn,
                organization_id=int(user["organization_id"]),
                proposal_id=proposal_id,
                actor_user_id=int(user["id"]),
                request_id=request_id,
                approve=bool((data or {})["approve"]),
                note=str((data or {}).get("note") or "").strip(),
            )
    except sqlite3.IntegrityError:
        return jsonify({"error": "proposal alias conflicts with an existing mapping"}), 409
    except Exception as exc:
        return _curriculum_error_response(exc)
    reprocessed = []
    failures = []
    proposal = review.get("proposal") or {}
    if bool((data or {})["approve"]):
        proposal_key = str(proposal.get("knowledge_point_key") or "")
        for candidate_id in list_graph_candidate_ids_for_proposal(
            organization_id=int(user["organization_id"]), proposal_key=proposal_key
        ):
            try:
                result = resolve_graph_unmapped_candidate(
                    candidate_id,
                    organization_id=int(user["organization_id"]),
                    actor_user_id=int(user["id"]),
                    request_id=f"{request_id}:candidate:{candidate_id[:16]}",
                    action="map",
                    target_knowledge_point_key=proposal_key,
                    note="Approved organization knowledge point replay",
                )
                reprocessed.append(result)
            except Exception as exc:
                logger.warning(
                    "Curriculum proposal replay failed candidate=%s error=%s",
                    candidate_id[:16],
                    exc.__class__.__name__,
                )
                failures.append({"candidate_id": candidate_id, "error": exc.__class__.__name__})
    _dispatch_class_commentary_graph_best_effort()
    return jsonify(
        {"review": review, "reprocessed": reprocessed, "failures": failures}
    ), (207 if failures else 200)


@app.route("/api/class-commentary/tasks", methods=["POST"])
def api_class_commentary_tasks_create():
    user, error = _require_auth()
    if error:
        return error
    try:
        class_id = int(request.form.get("class_id") or 0)
    except (TypeError, ValueError):
        class_id = 0
    if class_id <= 0:
        return jsonify({"error": "class_id is required"}), 400
    cls, class_error = _get_accessible_class_or_error(user, class_id)
    if class_error:
        return class_error
    audio = request.files.get("audio")
    if not audio or not audio.filename:
        return jsonify({"error": "audio is required"}), 400
    ext = Path(audio.filename).suffix.lower()
    if ext not in {".mp3", ".m4a", ".mp4", ".wav", ".ogg", ".webm", ".flac"}:
        return jsonify({"error": f"unsupported audio format: {ext}"}), 400
    upload_dir = UPLOAD_DIR / "class-commentary"
    upload_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    save_path = upload_dir / f"commentary_{ts}{ext}"
    audio.save(str(save_path))
    task = create_class_commentary_task(
        organization_id=int(user["organization_id"]),
        class_id=int(cls["id"]),
        teacher_user_id=int(user["id"]),
        audio_path=str(save_path),
        audio_filename=audio.filename,
        transcription_request_key=_current_audio_upload_request_key(),
    )
    task = mark_class_commentary_task_transcribing(int(task["id"]))
    _start_class_commentary_transcription_worker(
        int(task["id"]),
        str(save_path),
        {"id": int(user["id"]), "organization_id": int(user["organization_id"])},
        str(task.get("transcription_request_key") or ""),
    )
    return jsonify(
        _serialize_class_commentary_task_for_response(task, include_private=True)
    ), 202


@app.route("/api/class-commentary/tasks/text", methods=["POST"])
def api_class_commentary_tasks_create_text():
    user, error = _require_auth()
    if error:
        return error
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return payload_error
    try:
        class_id = int((data or {}).get("class_id") or 0)
    except (TypeError, ValueError):
        class_id = 0
    if class_id <= 0:
        return jsonify({"error": "class_id is required"}), 400
    cls, class_error = _get_accessible_class_or_error(user, class_id)
    if class_error:
        return class_error
    confirmed_transcript_text = str((data or {}).get("confirmed_transcript_text") or "").strip()
    if not confirmed_transcript_text:
        return jsonify({"error": "confirmed_transcript_text is required"}), 400
    task = create_class_commentary_task(
        organization_id=int(user["organization_id"]),
        class_id=int(cls["id"]),
        teacher_user_id=int(user["id"]),
        audio_path="",
        audio_filename="手动输入",
        transcription_request_key="",
    )
    task = mark_class_commentary_transcription_succeeded(int(task["id"]), confirmed_transcript_text)
    return jsonify(
        _serialize_class_commentary_task_for_response(task, include_private=True)
    ), 201


@app.route("/api/class-commentary/tasks", methods=["GET"])
def api_class_commentary_tasks_list():
    user, error = _require_auth()
    if error:
        return error
    if user.get("role") == "member":
        tasks = list_class_commentary_tasks_for_classes(get_user_class_ids(int(user["id"])), limit=30)
    else:
        tasks = list_class_commentary_tasks_for_organization(int(user["organization_id"]), limit=30)
    visible_tasks = [
        _serialize_class_commentary_task_for_response(
            task,
            include_private=(
                int(task["organization_id"]) == int(user["organization_id"])
                and (
                    int(task["teacher_user_id"]) == int(user["id"])
                    or user.get("role") == "super_owner"
                )
            ),
        )
        for task in tasks
    ]
    return jsonify({"tasks": visible_tasks})


@app.route("/api/class-commentary/tasks/<int:task_id>", methods=["GET"])
def api_class_commentary_task_get(task_id: int):
    user, error = _require_auth()
    if error:
        return error
    task, task_error = _get_accessible_class_commentary_task_or_error(user, task_id)
    if task_error:
        return task_error
    return jsonify(
        _serialize_class_commentary_task_for_response(
            task,
            include_private=(
                int(task["organization_id"]) == int(user["organization_id"])
                and (
                    int(task["teacher_user_id"]) == int(user["id"])
                    or user.get("role") == "super_owner"
                )
            ),
        )
    )


@app.route("/api/class-commentary/tasks/<int:task_id>/generations", methods=["GET"])
def api_class_commentary_generations_list(task_id: int):
    user, error = _require_auth()
    if error:
        return error
    task, task_error = _get_readable_class_commentary_task_or_error(user, task_id)
    if task_error:
        return task_error
    generations = list_class_commentary_generations(int(task["id"]))
    return jsonify({
        "generations": [
            _serialize_class_commentary_generation_for_response(generation)
            for generation in generations
        ]
    })


@app.route(
    "/api/class-commentary/tasks/<int:task_id>/generations/<int:generation_id>",
    methods=["GET"],
)
def api_class_commentary_generation_get(task_id: int, generation_id: int):
    user, error = _require_auth()
    if error:
        return error
    task, task_error = _get_readable_class_commentary_task_or_error(user, task_id)
    if task_error:
        return task_error
    generation = get_class_commentary_generation(generation_id)
    if not generation or int(generation["task_id"]) != int(task["id"]):
        return jsonify({"error": "not found"}), 404
    return jsonify(
        _serialize_class_commentary_generation_for_response(
            generation,
            include_private_snapshots=True,
        )
    )


@app.route(
    "/api/class-commentary/tasks/<int:task_id>/generations/<int:generation_id>/student-runs/retry",
    methods=["POST"],
)
def api_class_commentary_student_generation_retry(
    task_id: int,
    generation_id: int,
):
    user, error = _require_auth()
    if error:
        return error
    task, task_error = _get_owned_class_commentary_task_or_error(user, task_id)
    if task_error:
        return task_error
    generation = get_class_commentary_generation(generation_id)
    if not generation or int(generation["task_id"]) != int(task["id"]):
        return jsonify({"error": "not found"}), 404
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return payload_error
    request_id = str((data or {}).get("request_id") or "").strip()
    if not request_id:
        return jsonify({"error": "request_id is required"}), 400
    raw_student_ids = (data or {}).get("student_ids")
    if raw_student_ids is not None and not isinstance(raw_student_ids, list):
        return jsonify({"error": "student_ids must be a list"}), 400
    try:
        retried = retry_class_commentary_student_generation_runs(
            generation_id,
            actor_user_id=int(user["id"]),
            retry_request_id=request_id,
            student_ids=raw_student_ids,
        )
    except ClassCommentaryCreditReservationError as exc:
        return jsonify({"error": str(exc)}), 402
    except ClassCommentaryStudentGenerationRetryRequestConflict:
        return jsonify({"error": "student_generation_retry_request_conflict"}), 409
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    _dispatch_class_commentary_memory_best_effort()
    current_task = get_class_commentary_task(int(task["id"]))
    return jsonify(
        _serialize_class_commentary_generation_result(current_task, retried)
    ), 202


@app.route(
    "/api/class-commentary/tasks/<int:task_id>/generations/<int:generation_id>/feedback-draft",
    methods=["GET"],
)
def api_class_commentary_feedback_draft_get(task_id: int, generation_id: int):
    user, error = _require_auth()
    if error:
        return error
    task, task_error = _get_readable_class_commentary_task_or_error(user, task_id)
    if task_error:
        return task_error
    try:
        draft = get_class_commentary_feedback_draft(
            int(task["id"]),
            generation_id,
            int(task["teacher_user_id"]),
        )
    except LearningGraphSnapshotIntegrityError:
        return jsonify({"error": "generation_graph_snapshot_invalid"}), 409
    except ValueError:
        return jsonify({"error": "not found"}), 404
    return jsonify(_serialize_class_commentary_draft_for_response(draft))


@app.route(
    "/api/class-commentary/tasks/<int:task_id>/generations/<int:generation_id>/feedback-draft",
    methods=["PUT"],
)
def api_class_commentary_feedback_draft_put(task_id: int, generation_id: int):
    user, error = _require_auth()
    if error:
        return error
    task, task_error = _get_owned_class_commentary_task_or_error(user, task_id)
    if task_error:
        return task_error
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return payload_error
    structured_request = (
        "feedback_schema_version" in (data or {})
        or "student_feedback_items" in (data or {})
    )
    if structured_request and (
        "feedback_text" in (data or {})
        or "feedback_schema_version" not in (data or {})
        or "student_feedback_items" not in (data or {})
    ):
        return jsonify({"error": "feedback_schema_mismatch"}), 400
    if "expected_draft_version" not in (data or {}):
        return jsonify({"error": "expected_draft_version is required"}), 400
    based_on_revision_id = (data or {}).get("based_on_revision_id")
    feedback_kwargs = (
        {
            "feedback_schema_version": (data or {}).get("feedback_schema_version"),
            "student_feedback_items": (data or {}).get("student_feedback_items"),
        }
        if structured_request
        else {"feedback_text": str((data or {}).get("feedback_text") or "")}
    )
    try:
        draft = save_class_commentary_feedback_draft(
            task_id=int(task["id"]),
            generation_id=generation_id,
            teacher_user_id=int(user["id"]),
            expected_draft_version=(data or {}).get("expected_draft_version"),
            based_on_revision_id=(
                int(based_on_revision_id) if based_on_revision_id is not None else None
            ),
            **feedback_kwargs,
        )
    except ClassCommentaryDraftVersionConflict as exc:
        return jsonify({
            "error": exc.code,
            "current_draft": (
                _serialize_class_commentary_draft_for_response(exc.current_draft)["draft"]
                if exc.current_draft
                else None
            ),
        }), 409
    except ClassCommentaryFeedbackSchemaUnsupported as exc:
        return jsonify({"error": exc.code}), 409
    except ClassCommentaryFeedbackSchemaInvalid as exc:
        return jsonify({"error": exc.code}), 409
    except ClassCommentaryFeedbackSchemaMismatch as exc:
        return jsonify({"error": exc.code}), 400
    except ClassCommentaryStructuredFeedbackValidationError as exc:
        return jsonify(_class_commentary_structured_feedback_error_payload(exc)), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_serialize_class_commentary_draft_for_response(draft))


@app.route("/api/class-commentary/tasks/<int:task_id>/feedback-confirmations", methods=["POST"])
def api_class_commentary_feedback_confirm(task_id: int):
    user, error = _require_auth()
    if error:
        return error
    task, task_error = _get_owned_class_commentary_task_or_error(user, task_id)
    if task_error:
        return task_error
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return payload_error
    request_id = str((data or {}).get("request_id") or "").strip()
    if not request_id:
        return jsonify({"error": "request_id is required"}), 400
    feedback_kwargs = {
        key: (data or {}).get(key)
        for key in (
            "feedback_text",
            "feedback_schema_version",
            "student_feedback_items",
        )
        if key in (data or {})
    }
    expected_latest_kwargs = (
        {
            "expected_latest_revision_id": (data or {}).get(
                "expected_latest_revision_id"
            )
        }
        if "expected_latest_revision_id" in (data or {})
        else {}
    )
    try:
        revision = confirm_class_commentary_feedback(
            task_id=int(task["id"]),
            generation_id=(data or {}).get("generation_id"),
            teacher_user_id=int(user["id"]),
            learn_requested=(data or {}).get("learn"),
            expected_draft_version=(data or {}).get("expected_draft_version"),
            confirmation_request_id=request_id,
            **feedback_kwargs,
            **expected_latest_kwargs,
        )
    except ClassCommentaryMemoryNotEnabled as exc:
        return jsonify({"error": exc.code}), 409
    except ClassCommentaryConfirmationRequestConflict:
        return jsonify({"error": "confirmation_request_conflict"}), 409
    except ClassCommentaryDraftVersionConflict as exc:
        return jsonify({
            "error": exc.code,
            "current_draft": (
                _serialize_class_commentary_draft_for_response(exc.current_draft)["draft"]
                if exc.current_draft
                else None
            ),
        }), 409
    except ClassCommentaryRevisionVersionConflict as exc:
        return jsonify({
            "error": exc.code,
            "current_latest_revision_id": exc.current_latest_revision_id,
            "current_latest_revision": (
                _serialize_class_commentary_revision_for_response(
                    exc.current_latest_revision
                )
                if exc.current_latest_revision
                else None
            ),
        }), 409
    except ClassCommentaryFeedbackSchemaUnsupported as exc:
        return jsonify({"error": exc.code}), 409
    except ClassCommentaryFeedbackSchemaInvalid as exc:
        return jsonify({"error": exc.code}), 409
    except ClassCommentaryFeedbackSchemaMismatch as exc:
        return jsonify({"error": exc.code}), 400
    except ClassCommentaryStructuredFeedbackValidationError as exc:
        return jsonify(_class_commentary_structured_feedback_error_payload(exc)), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    memory_summary = None
    if bool(get_config().get("class_commentary_memory_enabled")):
        _dispatch_class_commentary_memory_best_effort()
    if bool((data or {}).get("learn")) and bool(
        get_config().get("class_commentary_graph_enabled")
    ):
        _dispatch_class_commentary_graph_best_effort()
    if bool((data or {}).get("learn")):
        memory_summary = _serialize_class_commentary_memory_summary(
            list_class_commentary_revision_memories(
                int(revision["id"]),
                actor_user_id=int(user["id"]),
            ),
            actor_user_id=int(user["id"]),
        )
    serialized = _serialize_class_commentary_revision_for_response(revision)
    serialized_draft = _serialize_class_commentary_draft_for_response(
        revision.get("draft") if isinstance(revision.get("draft"), dict) else None,
        generation=get_class_commentary_generation(int(revision["generation_id"])),
    )["draft"]
    response_payload = {
        **serialized,
        "revision_id": serialized["id"],
        "latest_revision_id": serialized["id"],
        "latest_revision_no": serialized["revision_no"],
        "revision": serialized,
        "draft": serialized_draft,
    }
    if memory_summary is not None:
        response_payload["memory"] = memory_summary
    return jsonify(response_payload)


@app.route("/api/class-commentary/tasks/<int:task_id>/feedback-revisions", methods=["GET"])
def api_class_commentary_feedback_revisions(task_id: int):
    user, error = _require_auth()
    if error:
        return error
    task, task_error = _get_readable_class_commentary_task_or_error(user, task_id)
    if task_error:
        return task_error
    revisions = list_class_commentary_revisions(int(task["id"]))
    return jsonify({
        "revisions": [
            _serialize_class_commentary_revision_for_response(revision)
            for revision in revisions
        ]
    })


@app.route(
    "/api/class-commentary/tasks/<int:task_id>/students/<int:student_id>/learning-graph",
    methods=["GET"],
)
def api_class_commentary_student_learning_graph(task_id: int, student_id: int):
    user, error = _require_auth()
    if error:
        return error
    task, task_error = _get_owned_class_commentary_task_or_error(user, task_id)
    if task_error:
        return task_error
    if not bool(get_config().get("class_commentary_graph_enabled")):
        return jsonify({"error": "learning_graph_not_enabled"}), 409
    class_row = get_class(int(task["class_id"]))
    if (
        not class_row
        or int(class_row.get("organization_id") or 0)
        != int(user.get("organization_id") or 0)
    ):
        return jsonify({"error": "not found"}), 404
    class_student_ids = {
        int(student.get("id") or 0)
        for student in list_students_for_class(int(task["class_id"]))
    }
    if int(student_id) not in class_student_ids:
        return jsonify({"error": "not found"}), 404
    subject_key = str(class_row.get("subject_key") or "").strip()
    if not subject_key:
        return jsonify({"error": "class_subject_not_supported"}), 409

    generation_id = None
    raw_generation_id = request.args.get("generation_id")
    if raw_generation_id is not None:
        try:
            generation_id = int(raw_generation_id)
        except (TypeError, ValueError):
            return jsonify({"error": "generation_id must be an integer"}), 400
        if generation_id <= 0:
            return jsonify({"error": "generation_id must be positive"}), 400
        generation = get_class_commentary_generation(generation_id)
        if (
            not generation
            or int(generation.get("task_id") or 0) != int(task["id"])
            or int(generation.get("organization_id") or 0)
            != int(user.get("organization_id") or 0)
        ):
            return jsonify({"error": "not found"}), 404
        try:
            roster = json.loads(
                str(generation.get("attending_roster_snapshot_json") or "[]")
            )
        except json.JSONDecodeError:
            return jsonify({"error": "generation_scope_invalid"}), 409
        roster_student_ids = {
            int(item.get("student_id") or 0)
            for item in roster
            if isinstance(item, dict)
        }
        if int(student_id) not in roster_student_ids:
            return jsonify({"error": "not found"}), 404
        generation_subject_key = str(generation.get("subject_key") or "").strip()
        if not generation_subject_key:
            return jsonify({"error": "generation_subject_not_supported"}), 409
        subject_key = generation_subject_key

    try:
        summary = get_student_learning_graph_summary(
            organization_id=int(user["organization_id"]),
            task_id=int(task["id"]),
            student_id=int(student_id),
            subject_key=subject_key,
            generation_id=generation_id,
            event_limit=int(
                get_config().get("class_commentary_graph_retrieval_event_limit") or 24
            ),
        )
    except ValueError:
        return jsonify({"error": "not found"}), 404
    return jsonify({"learning_graph": summary})


@app.route(
    "/api/class-commentary/revisions/<int:revision_id>/graph-retry",
    methods=["POST"],
)
def api_class_commentary_revision_graph_retry(revision_id: int):
    user, error = _require_auth()
    if error:
        return error
    _, _, revision_error = _get_owned_class_commentary_revision_or_error(
        user,
        revision_id,
    )
    if revision_error:
        return revision_error
    if not bool(get_config().get("class_commentary_graph_enabled")):
        return jsonify({"error": "learning_graph_not_enabled"}), 409
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return payload_error
    request_id = str((data or {}).get("request_id") or "").strip()
    if not request_id:
        return jsonify({"error": "request_id is required"}), 400
    with get_conn() as conn:
        prior = conn.execute(
            """
            SELECT revision_id
            FROM class_commentary_graph_retry_events
            WHERE organization_id=? AND request_id=?
            """,
            (int(user["organization_id"]), request_id),
        ).fetchone()
    if prior and int(prior["revision_id"]) != int(revision_id):
        return jsonify({"error": "graph_retry_request_conflict"}), 409
    try:
        job = retry_graph_revision(
            revision_id,
            organization_id=int(user["organization_id"]),
            actor_user_id=int(user["id"]),
            request_id=request_id,
        )
    except LearningGraphRetryConflict:
        return jsonify({"error": "graph_retry_request_conflict"}), 409
    except ValueError:
        return jsonify({"error": "not found"}), 404
    dispatch = _dispatch_class_commentary_graph_best_effort()
    return jsonify({"graph_job": job, "dispatch": dispatch})


@app.route(
    "/api/class-commentary/revisions/<int:revision_id>/memories",
    methods=["GET"],
)
def api_class_commentary_revision_memories(revision_id: int):
    user, error = _require_auth()
    if error:
        return error
    _, _, revision_error = _get_owned_class_commentary_revision_or_error(
        user,
        revision_id,
    )
    if revision_error:
        return revision_error
    try:
        summary = list_class_commentary_revision_memories(
            revision_id,
            actor_user_id=int(user["id"]),
        )
    except ValueError:
        return jsonify({"error": "not found"}), 404
    return jsonify(
        _serialize_class_commentary_memory_summary(
            summary,
            actor_user_id=int(user["id"]),
        )
    )


@app.route(
    "/api/class-commentary/revisions/<int:revision_id>/memory-retry",
    methods=["POST"],
)
def api_class_commentary_revision_memory_retry(revision_id: int):
    user, error = _require_auth()
    if error:
        return error
    _, _, revision_error = _get_owned_class_commentary_revision_or_error(
        user,
        revision_id,
    )
    if revision_error:
        return revision_error
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return payload_error
    request_id = str((data or {}).get("request_id") or "").strip()
    if not request_id:
        return jsonify({"error": "request_id is required"}), 400
    try:
        retry_class_commentary_memory_revision(
            revision_id,
            actor_user_id=int(user["id"]),
            request_id=request_id,
        )
    except ClassCommentaryMemoryRetryRequestConflict:
        return jsonify({"error": "memory_retry_request_conflict"}), 409
    except ClassCommentaryMemoryRevisionNotRetryable as exc:
        return jsonify({"error": exc.code}), 409
    except ValueError:
        return jsonify({"error": "not found"}), 404
    _dispatch_class_commentary_memory_best_effort()
    summary = list_class_commentary_revision_memories(
        revision_id,
        actor_user_id=int(user["id"]),
    )
    return jsonify(
        {
            "memory": _serialize_class_commentary_memory_summary(
                summary,
                actor_user_id=int(user["id"]),
            )
        }
    )


@app.route(
    "/api/class-commentary/memory-evidence/<int:evidence_id>/revoke",
    methods=["POST"],
)
def api_class_commentary_memory_evidence_revoke(evidence_id: int):
    user, error = _require_auth()
    if error:
        return error
    evidence = get_class_commentary_memory_evidence(evidence_id)
    if not evidence:
        return jsonify({"error": "not found"}), 404
    _, _, revision_error = _get_owned_class_commentary_revision_or_error(
        user,
        int(evidence["revision_id"]),
    )
    if revision_error:
        return revision_error
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return payload_error
    request_id = str((data or {}).get("request_id") or "").strip()
    if not request_id:
        return jsonify({"error": "request_id is required"}), 400
    try:
        revoke_class_commentary_memory_evidence(
            evidence_id,
            actor_user_id=int(user["id"]),
            request_id=request_id,
        )
    except ClassCommentaryMemoryEvidenceRequestConflict:
        return jsonify({"error": "memory_evidence_request_conflict"}), 409
    except ClassCommentaryMemoryEvidenceNotRevocable as exc:
        return jsonify({"error": exc.code}), 409
    except ValueError:
        return jsonify({"error": "not found"}), 404
    _dispatch_class_commentary_memory_best_effort()
    summary = list_class_commentary_revision_memories(
        int(evidence["revision_id"]),
        actor_user_id=int(user["id"]),
    )
    return jsonify(
        {
            "memory": _serialize_class_commentary_memory_summary(
                summary,
                actor_user_id=int(user["id"]),
            )
        }
    )


@app.route("/api/class-commentary/tasks/<int:task_id>/transcript", methods=["PUT"])
def api_class_commentary_task_update_transcript(task_id: int):
    user, error = _require_auth()
    if error:
        return error
    task, task_error = _get_owned_class_commentary_task_or_error(user, task_id)
    if task_error:
        return task_error
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return payload_error
    confirmed_transcript_text = str((data or {}).get("confirmed_transcript_text") or "").strip()
    if not confirmed_transcript_text:
        return jsonify({"error": "confirmed_transcript_text is required"}), 400
    updated_task = save_class_commentary_transcript(int(task["id"]), confirmed_transcript_text)
    return jsonify(
        _serialize_class_commentary_task_for_response(
            updated_task,
            include_private=True,
        )
    )


@app.route("/api/class-commentary/tasks/<int:task_id>/generate", methods=["POST"])
def api_class_commentary_task_generate(task_id: int):
    user, error = _require_auth()
    if error:
        return error
    task, task_error = _get_owned_class_commentary_task_or_error(user, task_id)
    if task_error:
        return task_error
    data, payload_error = _get_json_object_payload()
    if payload_error:
        return payload_error
    request_id = str((data or {}).get("request_id") or "").strip()
    if not request_id:
        return jsonify({"error": "request_id is required"}), 400
    skill_id = str((data or {}).get("skill_id") or "").strip()
    if not skill_id:
        return jsonify({"error": "skill_id is required"}), 400

    existing_generation = get_class_commentary_generation_by_request(
        int(task["id"]),
        request_id,
    )
    if existing_generation:
        selected_ids, selected_ids_error = _parse_class_commentary_attending_student_ids(
            data or {}
        )
        if selected_ids_error:
            return selected_ids_error
        saved_roster = _class_commentary_json_value(
            existing_generation.get("attending_roster_snapshot_json"),
            [],
        )
        saved_student_ids = {
            int(item.get("student_id") or 0)
            for item in saved_roster
            if isinstance(item, dict) and int(item.get("student_id") or 0) > 0
        }
        if (
            str(existing_generation.get("skill_id") or "") != skill_id
            or bool(existing_generation.get("attending_roster_explicit"))
            != ("attending_student_ids" in (data or {}))
            or (selected_ids is not None and selected_ids != saved_student_ids)
        ):
            return jsonify({"error": "generation_request_conflict"}), 409
        resume_existing_batch = bool(
            existing_generation["status"] == "generating"
            and str(existing_generation.get("student_history_memory_mode") or "")
            == CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
        )
        if resume_existing_batch:
            try:
                existing_generation = _resume_class_commentary_batch_generation(
                    generation=existing_generation,
                    user=user,
                )
            except CreditBalanceError as exc:
                current_task = get_class_commentary_task(int(task["id"]))
                return jsonify({
                    "error": str(exc),
                    "task": _serialize_class_commentary_task_for_response(
                        current_task,
                        include_private=True,
                    ),
                    "generation": _serialize_class_commentary_generation_for_response(
                        existing_generation
                    ),
                    "generation_id": int(existing_generation["id"]),
                    "generation_status": str(existing_generation["status"]),
                }), 402
        current_task = get_class_commentary_task(int(task["id"]))
        status_code = 202 if existing_generation["status"] == "generating" else 200
        return jsonify(
            _serialize_class_commentary_generation_result(
                current_task,
                existing_generation,
            )
        ), status_code

    if not has_class_commentary_api_key():
        return jsonify({"error": "系统 API Key 未配置, 请联系管理员"}), 400
    if str(task.get("status") or "") not in {"transcribed", "failed", "ready", "generating"}:
        return jsonify({"error": "task must be transcribed before generation"}), 400
    confirmed_transcript_text = str(task.get("confirmed_transcript_text") or "").strip()
    if not confirmed_transcript_text:
        return jsonify({"error": "confirmed transcript is required before generation"}), 400
    confirmed_transcript_version = int(task.get("confirmed_transcript_version") or 0)
    confirmed_transcript_hash = class_commentary_student_content_hash(
        confirmed_transcript_text
    )
    cls = get_class(int(task["class_id"]))
    if not cls:
        return jsonify({"error": "not found"}), 404
    current_class_students = list_students_for_class(int(task["class_id"]))
    structured_feedback_enabled = bool(
        get_config().get("class_commentary_structured_feedback_enabled")
    )
    if not structured_feedback_enabled:
        return jsonify({"error": "class_commentary_batch_memory_unavailable"}), 503
    if (
        "attending_student_ids" not in (data or {})
    ):
        return jsonify({"error": "attending_student_ids is required"}), 400
    class_students, attendance_error = _filter_class_commentary_students_by_attendance(
        current_class_students,
        data or {},
    )
    if attendance_error:
        return attendance_error
    try:
        ensure_feature_credits_available_for_count(
            organization_id=int(user["organization_id"]),
            feature_key="class_commentary_generate",
            call_count=1,
        )
    except CreditBalanceError as exc:
        return jsonify({"error": str(exc)}), 402
    generation_capabilities = _class_commentary_capabilities(force=True)
    if not generation_capabilities.get("batch_isolated_v3_enabled"):
        return jsonify({"error": "class_commentary_batch_memory_unavailable"}), 503
    _sync_configured_class_commentary_skills(user)
    skill = get_class_commentary_skill_for_organization(
        int(user["organization_id"]),
        skill_id,
    )
    if not skill:
        return jsonify({"error": "skill not found"}), 404
    chat_provider = _class_commentary_ai_provider_name(fallback=_default_ai_provider_name())
    chat_model = _class_commentary_chat_model_name(chat_provider, fallback_model=_default_chat_model_name())
    prompt_version = (
        CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V5
        if structured_feedback_enabled
        else CLASS_COMMENTARY_PROMPT_VERSION
    )
    attending_roster = [
        {
            "student_id": int(student["id"]),
            "student_name": str(student.get("name") or ""),
        }
        for student in class_students
    ]
    try:
        generation = reserve_class_commentary_generation(
            task_id=int(task["id"]),
            generation_request_id=request_id,
            skill_registry_id=int(skill["registry_id"]),
            attending_roster=attending_roster,
            model_provider=chat_provider,
            model_name=chat_model,
            model_parameters={"temperature": CLASS_COMMENTARY_TEMPERATURE},
            prompt_version=prompt_version,
            attending_roster_explicit="attending_student_ids" in (data or {}),
            structured_feedback_enabled=structured_feedback_enabled,
            student_history_memory_mode=(
                CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
                if structured_feedback_enabled
                else ""
            ),
            credit_hold_amount_per_student=0,
            credit_hold_amount=max_configured_charge_for_feature(
                "class_commentary_generate"
            ),
            expected_confirmed_transcript_version=confirmed_transcript_version,
            expected_confirmed_transcript_hash=confirmed_transcript_hash,
        )
    except ClassCommentaryCreditReservationError as exc:
        return jsonify({"error": str(exc)}), 402
    except ClassCommentaryStudentScopeError as exc:
        return jsonify({"error": exc.code}), 400
    except ClassCommentaryGenerationRequestConflict:
        return jsonify({"error": "generation_request_conflict"}), 409
    except ClassCommentaryTranscriptSnapshotConflict as exc:
        return jsonify({"error": exc.code}), 409
    except ValueError as exc:
        if str(exc) == "class_commentary_subject_unavailable":
            return jsonify({"error": str(exc)}), 400
        raise
    if generation.get("is_idempotent"):
        if (
            generation["status"] == "generating"
            and str(generation.get("student_history_memory_mode") or "")
            == CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
        ):
            generation = _resume_class_commentary_batch_generation(
                generation=generation,
                user=user,
            )
        current_task = get_class_commentary_task(int(task["id"]))
        status_code = 202 if generation["status"] == "generating" else 200
        return jsonify(
            _serialize_class_commentary_generation_result(current_task, generation)
        ), status_code
    if str(generation.get("student_history_memory_mode") or "") == (
        CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2
    ):
        _dispatch_class_commentary_memory_best_effort()
        current_task = get_class_commentary_task(int(task["id"]))
        return jsonify(
            _serialize_class_commentary_generation_result(
                current_task,
                generation,
            )
        ), 202
    try:
        completed_generation = _resume_class_commentary_batch_generation(
            generation=generation,
            user=user,
        )
        ready_task = get_class_commentary_task(int(task["id"]))
        status_code = 202 if completed_generation["status"] == "generating" else 200
        return jsonify(
            _serialize_class_commentary_generation_result(ready_task, completed_generation)
        ), status_code
    except ClassCommentaryBatchContextError:
        logger.warning(
            "class commentary batch context unavailable generation_id=%s",
            int(generation["id"]),
        )
        failed_generation = fail_class_commentary_generation(
            int(generation["id"]),
            "class_commentary_batch_context_unavailable",
        )
        failed_task = get_class_commentary_task(int(task["id"]))
        return jsonify({
            "error": "class_commentary_batch_memory_unavailable",
            "task": _serialize_class_commentary_task_for_response(
                failed_task,
                include_private=True,
            ),
            "generation": _serialize_class_commentary_generation_for_response(
                failed_generation
            ),
            "generation_id": int(failed_generation["id"]),
            "generation_status": str(failed_generation["status"]),
        }), 503
    except CreditBalanceError as exc:
        logger.warning(
            "class commentary batch charge pending generation_id=%s",
            int(generation["id"]),
        )
        pending_generation = get_class_commentary_generation(int(generation["id"]))
        pending_task = get_class_commentary_task(int(task["id"]))
        return jsonify({
            "error": str(exc),
            "task": _serialize_class_commentary_task_for_response(
                pending_task,
                include_private=True,
            ),
            "generation": _serialize_class_commentary_generation_for_response(
                pending_generation
            ),
            "generation_id": int(pending_generation["id"]),
            "generation_status": str(pending_generation["status"]),
        }), 402
    except ClassCommentaryStructuredFeedbackValidationError as exc:
        logger.warning(
            "class commentary structured feedback validation failed generation_id=%s reason=%s",
            int(generation["id"]),
            exc.reason,
        )
        failed_generation = get_class_commentary_generation(int(generation["id"]))
        failed_task = get_class_commentary_task(int(task["id"]))
        return jsonify({
            "error": "structured_feedback_invalid",
            "task": _serialize_class_commentary_task_for_response(
                failed_task,
                include_private=True,
            ),
            "generation": _serialize_class_commentary_generation_for_response(
                failed_generation
            ),
            "generation_id": int(failed_generation["id"]),
            "generation_status": str(failed_generation["status"]),
        }), 500
    except Exception as exc:
        latest_generation = get_class_commentary_generation(int(generation["id"]))
        durable_progress = bool(
            latest_generation
            and (
                str(latest_generation.get("execution_snapshot_status") or "")
                == "ready"
                or str(latest_generation.get("batch_response_hash") or "")
                or str(latest_generation.get("batch_charge_status") or "")
                == "charged"
            )
        )
        failed_generation = (
            latest_generation
            if durable_progress
            else fail_class_commentary_generation(
                int(generation["id"]),
                str(exc),
            )
        )
        failed_task = get_class_commentary_task(int(task["id"]))
        return jsonify({
            "error": str(exc),
            "task": _serialize_class_commentary_task_for_response(
                failed_task,
                include_private=True,
            ),
            "generation": _serialize_class_commentary_generation_for_response(
                failed_generation
            ),
            "generation_id": int(failed_generation["id"]),
            "generation_status": str(failed_generation["status"]),
        }), 500


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
        "review_plan_provider": cfg.get("review_plan_provider", ""),
        "review_plan_model": cfg.get("review_plan_model", ""),
        "review_plan_reasoning_effort": cfg.get("review_plan_reasoning_effort", ""),
        "review_plan_temperature": cfg.get("review_plan_temperature", 0.25),
        "review_plan_writer_provider": cfg.get("review_plan_writer_provider", "deepseek"),
        "review_plan_writer_model": cfg.get("review_plan_writer_model", ""),
        "review_plan_writer_temperature": cfg.get("review_plan_writer_temperature", 0.35),
        "review_plan_repair_temperature": cfg.get("review_plan_repair_temperature", 0.1),
        "review_plan_reviewer_temperature": cfg.get("review_plan_reviewer_temperature", 0.1),
        "openai_set": bool(cfg.get("openai_api_key")),
        "openai_masked": _mask(cfg.get("openai_api_key", "")),
        "openai_model": cfg.get("openai_model", "gpt-4o"),
        "openai_base_url": cfg.get("openai_base_url", ""),
        "deepseek_set": bool(cfg.get("deepseek_api_key")),
        "deepseek_masked": _mask(cfg.get("deepseek_api_key", "")),
        "qwen_set": bool(cfg.get("qwen_api_key")),
        "qwen_masked": _mask(cfg.get("qwen_api_key", "")),
        "qwen_base_url": cfg.get("qwen_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
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
        cfg["provider"] = normalize_chat_provider(data["provider"])
    if "review_plan_provider" in data and "review_plan_provider" not in controlled_keys:
        cfg["review_plan_provider"] = normalize_chat_provider(data["review_plan_provider"]) if str(data["review_plan_provider"] or "").strip() else ""
    if "review_plan_model" in data and "review_plan_model" not in controlled_keys:
        cfg["review_plan_model"] = str(data["review_plan_model"] or "").strip()
    if "review_plan_reasoning_effort" in data and "review_plan_reasoning_effort" not in controlled_keys:
        cfg["review_plan_reasoning_effort"] = normalize_reasoning_effort(data["review_plan_reasoning_effort"])
    if "review_plan_temperature" in data and "review_plan_temperature" not in controlled_keys:
        cfg["review_plan_temperature"] = normalize_temperature(data["review_plan_temperature"], 0.25)
    if "review_plan_writer_provider" in data and "review_plan_writer_provider" not in controlled_keys:
        cfg["review_plan_writer_provider"] = normalize_chat_provider(data["review_plan_writer_provider"] or "deepseek")
    if "review_plan_writer_model" in data and "review_plan_writer_model" not in controlled_keys:
        cfg["review_plan_writer_model"] = str(data["review_plan_writer_model"] or "").strip()
    if "review_plan_writer_temperature" in data and "review_plan_writer_temperature" not in controlled_keys:
        cfg["review_plan_writer_temperature"] = normalize_temperature(data["review_plan_writer_temperature"], 0.35)
    if "review_plan_repair_temperature" in data and "review_plan_repair_temperature" not in controlled_keys:
        cfg["review_plan_repair_temperature"] = normalize_temperature(data["review_plan_repair_temperature"], 0.1)
    if "review_plan_reviewer_temperature" in data and "review_plan_reviewer_temperature" not in controlled_keys:
        cfg["review_plan_reviewer_temperature"] = normalize_temperature(data["review_plan_reviewer_temperature"], 0.1)
    for key in ("openai_api_key", "openai_model", "openai_base_url", "deepseek_api_key", "qwen_api_key", "qwen_base_url"):
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
    recovered_review_jobs = _recover_interrupted_review_plan_jobs()
    if recovered_review_jobs:
        print(f"  已恢复 {recovered_review_jobs} 个未完成复习计划任务")
    if _should_open_browser():
        threading.Thread(target=_open_browser, daemon=True).start()
    print("\n" + "=" * 50)
    print("  📚 复习计划管理系统已启动")
    print(_startup_browser_message())
    print("  后端地址：http://127.0.0.1:5001")
    print("  按 Ctrl+C 关闭程序")
    print("=" * 50 + "\n")
    app.run(host="127.0.0.1", port=5001, debug=False)
